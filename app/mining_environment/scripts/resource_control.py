# ✅ RESOURCE CONTROL: GPU-only resource management
# All CPU optimization and throttling logic removed
# resource_control.py

# mypy: ignore-errors
# pyright: reportGeneralTypeIssues=false, reportMissingImports=false


import os
import psutil
import time
import uuid
import glob
import random
import shutil
import logging
import traceback
import threading
import subprocess
import re
import glob
import pynvml
import hashlib
from typing import Dict, Any, List, Optional, Set, Union, Protocol
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import signal
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
import resource
from pathlib import Path

# Factory function for DAG synchronizer import
def get_dag_synchronizer_factory():
    """
    Factory function to import DAG synchronizer with fallback
    Handles both package and standalone imports
    """
    try:
        # Try package import first
        from mining_environment.scripts.dag_synchronization import get_dag_synchronizer, DAGState
        return get_dag_synchronizer, DAGState
    except ImportError:
        try:
            # Try relative import
            from .dag_synchronization import get_dag_synchronizer, DAGState
            return get_dag_synchronizer, DAGState
        except ImportError:
            try:
                # Try direct import for standalone testing
                from dag_synchronization import get_dag_synchronizer, DAGState
                return get_dag_synchronizer, DAGState
            except ImportError:
                # DAG module not available
                return None, None

# Get DAG imports
get_dag_synchronizer, DAGState = get_dag_synchronizer_factory()

try:
    from .utils import StrategyType
    from .module_loggers import get_resource_control_logger, get_gpu_resource_manager_logger
    from .error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error
    from .logging_config import setup_logging
except ImportError:
    # Fallback to absolute imports for standalone testing
    from utils import StrategyType
    from module_loggers import get_resource_control_logger, get_gpu_resource_manager_logger
    from error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error
    from logging_config import setup_logging
    try:
        from dag_synchronization import get_dag_synchronizer, DAGState
    except ImportError:
        # DAG synchronization is optional
        get_dag_synchronizer = None
        DAGState = None

# ✅ STANDARDIZED: Unified logger for OHC and module-level
resource_logger = get_resource_control_logger()

# ✅ DEDICATED FILE LOGGERS
# GPUResourceManager → GPUResourceManager.log
grm_file_logger = get_gpu_resource_manager_logger()

# ✅ ERROR REPORTER: Get centralized error reporter instance
error_reporter = get_error_reporter()
# **All CPU-related imports removed** (đã xóa hoàn toàn import CPU – chỉ giữ GPU-only mining)
from threading import RLock


# ========================= Metrics Interfaces (giao diện số liệu) =========================
@dataclass
class GpuMetricsSnapshot:
    """
    **GpuMetricsSnapshot** (ảnh chụp số liệu GPU – gói các metric tại một thời điểm)
    - timestamp (mốc thời gian – epoch giây)
    - temperature_c (nhiệt độ °C)
    - power_watts (công suất W)
    - utilization (mức sử dụng – tỷ lệ 0..1)
    - mem_used_bytes/mem_total_bytes (bộ nhớ dùng/tổng – byte)
    """
    timestamp: float
    gpu_indices: List[int]
    temperature_c: Dict[int, Optional[float]]
    power_watts: Dict[int, Optional[float]]
    utilization: Dict[int, Optional[float]]
    mem_used_bytes: Dict[int, Optional[int]]
    mem_total_bytes: Dict[int, Optional[int]]


class IGpuMetricsProvider(Protocol):
    """
    **IGpuMetricsProvider** (giao diện nhà cung cấp số liệu GPU – thống nhất truy cập metrics)
    """
    def get_metrics_snapshot(self, ttl_sec: Optional[float] = None) -> GpuMetricsSnapshot:
        ...


###############################################################################
#                           GPU RESOURCE MANAGER                              #
###############################################################################
class GPUResourceManager:
    """
    Quản lý GPU thông qua pynvml (đồng bộ).

    Attributes:
        logger (logging.Logger): Logger để ghi log.
        config (Dict[str, Any]): Cấu hình GPU Resource Manager.
        gpu_initialized (bool): Cờ đánh dấu NVML đã khởi tạo hay chưa.
        process_gpu_settings (Dict[int, Dict[int, Dict[str, Any]]]): Lưu PID -> GPU Index -> settings.
    """

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Khởi tạo GPUResourceManager.

        :param config: Cấu hình GPU Resource Manager (dict).
        :param logger: Đối tượng Logger.
        """
        # Use dedicated file logger (GPUResourceManager.log)
        self.logger = grm_file_logger
        self.config = config
        self.gpu_initialized = False
        self.process_gpu_settings: Dict[int, Dict[int, Dict[str, Any]]] = {}
        # Track last power changes to enforce dwell-time and delta clamps
        self._last_power_change_time: Dict[int, float] = {}
        self._last_power_limit_w: Dict[int, int] = {}
        # Heartbeat
        try:
            self.logger.info("💓 [Heartbeat] GPUResourceManager initialized (logger active)")
        except Exception:
            pass
        
        # **INTELLIGENCE LAYER: Temperature Model Parameters** (tham số mô hình nhiệt độ)
        self.temp_history: Dict[int, List[tuple]] = {}  # GPU index -> [(timestamp, temp)]
        self.power_history: Dict[int, List[tuple]] = {}  # GPU index -> [(timestamp, power)]
        
        # **Newton's Cooling Law Constants** (hằng số định luật làm lạnh Newton)
        self.cooling_coefficient = config.get('cooling_coefficient', 0.05)  # k value
        self.ambient_temp = config.get('ambient_temp', 25.0)  # Room temperature (°C)
        
        # **Heat Generation Parameters** (tham số sinh nhiệt)
        self.thermal_efficiency = config.get('thermal_efficiency', 0.85)  # η = 85%
        self.heat_capacity = config.get('heat_capacity', 200.0)  # J/°C
        
        # **Safety Thresholds** (ngưỡng an toàn)
        self.temp_safe = config.get('temp_safe', 65)  # Safe operating temp
        self.temp_warning = config.get('temp_warning', 72)  # Warning threshold
        self.temp_critical = config.get('temp_critical', 78)  # Critical threshold
        self.temp_emergency = config.get('temp_emergency', 82)  # Emergency shutdown

        # ------- Caching (bộ nhớ đệm) & đồng bộ hóa -------
        self._lock: RLock = RLock()
        # NVML handles cache (bộ đệm tay cầm NVML)
        self._handle_cache: Dict[int, Any] = {}
        self._handle_cache_time: Dict[int, float] = {}
        # Metrics snapshot cache (bộ đệm ảnh chụp số liệu)
        self._metrics_cache: Optional[GpuMetricsSnapshot] = None
        self._metrics_cache_time: float = 0.0
        # TTL cấu hình (giây) – có thể override bằng biến môi trường
        try:
            self.handle_cache_ttl_sec: float = float(os.getenv('HANDLE_CACHE_TTL_SEC', str(self.config.get('handle_cache_ttl_sec', 60.0))))
        except Exception:
            self.handle_cache_ttl_sec = 60.0
        try:
            self.metrics_cache_ttl_sec: float = float(os.getenv('METRICS_CACHE_TTL_SEC', str(self.config.get('metrics_cache_ttl_sec', 0.5))))
        except Exception:
            self.metrics_cache_ttl_sec = 0.5

        # ------- PID negative cache & backoff (bộ đệm âm tính PID & backoff) -------
        # Lưu thời điểm hết hạn cache âm tính theo PID (pid -> expiry_ts)
        self._neg_cache_expiry: Dict[int, float] = {}
        # Số lần liên tiếp gặp trạng thái "không tồn tại" để tính backoff luỹ thừa
        self._neg_cache_hits: Dict[int, int] = {}
        # Thời điểm lần cuối log cảnh báo cho PID để chống spam
        self._pid_last_log_ts: Dict[int, float] = {}
        try:
            self._pid_backoff_base: float = float(os.getenv('PID_NOT_FOUND_BACKOFF_BASE_SEC', str(self.config.get('pid_not_found_backoff_base_sec', 5.0))))
        except Exception:
            self._pid_backoff_base = 5.0
        try:
            self._pid_backoff_max: float = float(os.getenv('PID_NOT_FOUND_BACKOFF_MAX_SEC', str(self.config.get('pid_not_found_backoff_max_sec', 60.0))))
        except Exception:
            self._pid_backoff_max = 60.0
        try:
            self._pid_log_suppress_window: float = float(os.getenv('PID_NOT_FOUND_LOG_SUPPRESS_SEC', str(self.config.get('pid_not_found_log_suppress_sec', 20.0))))
        except Exception:
            self._pid_log_suppress_window = 20.0

        # Tự động khởi tạo NVML
        self.initialize_nvml()

    def initialize_nvml(self) -> bool:
        """
        Khởi tạo pynvml (đồng bộ).

        :return: True nếu khởi tạo thành công, False nếu thất bại.
        """
        try:
            pynvml.nvmlInit()
            self.logger.info("✅ [pynvml] (thư viện quản lý NVIDIA – Python bindings) initialized (đã được khởi tạo)")
            self.gpu_initialized = True
            return True
        except pynvml.NVMLError as error:
            self.logger.error(f"❌ Error initializing [pynvml] (thư viện quản lý NVIDIA – Python bindings): {error}")
            self.gpu_initialized = False
            return False
        except Exception as e:
            # ✅ ERROR REPORTING: GPU initialization failure
            error_reporter.report_error(
                ErrorCode.RESOURCE_MANAGER_INIT_FAILED,
                f"Lỗi khi khởi tạo [pynvml] (thư viện quản lý NVIDIA – Python bindings): {e}",
                ErrorSeverity.HIGH,
                module='resource_control',
                function='GPUResourceManager._initialize_nvml',
                context_data={'component': 'pynvml', 'error': str(e)},
                exception=e
            )
            self.logger.error(f"❌ Error initializing [pynvml] (thư viện quản lý NVIDIA – Python bindings): {e}")
            self.gpu_initialized = False
            return False

    def verify_clock_lock_conditions(
        self,
        pid: int,
        gpu_index: int,
        window_sec: Optional[int] = None,
        temp_max: Optional[float] = None,
        min_increase_pct: Optional[float] = None,
    ) -> bool:
        """
        Verify whether conditions are safe to lock GPU clocks for a given PID/GPU.

        Checks recent mining output logs within a time window to measure hashrate trend,
        normalizes units (H/s, kH/s, MH/s, GH/s, TH/s), computes percentage increase,
        and confirms current GPU temperature is below a configurable maximum.

        Env vars:
        - CLOCK_LOCK_VERIFY_WINDOW_SEC: time window for log verification (default: 60)
        - CLOCK_LOCK_TEMP_MAX: max GPU temp allowed for lock (default: 70°C)
        - CLOCK_LOCK_MIN_INCREASE_PCT: min % increase in hashrate over window (default: 5%)
        - LOGS_DIR: custom logs directory (default resolves to mining_environment/logs)
        """
        try:
            # Resolve parameters from env if not provided
            try:
                if window_sec is None:
                    window_sec = int(str(os.getenv('CLOCK_LOCK_VERIFY_WINDOW_SEC', '60')))
            except Exception:
                window_sec = 60
            try:
                if temp_max is None:
                    temp_max = float(str(os.getenv('CLOCK_LOCK_TEMP_MAX', '70')))
            except Exception:
                temp_max = 70.0
            try:
                if min_increase_pct is None:
                    min_increase_pct = float(str(os.getenv('CLOCK_LOCK_MIN_INCREASE_PCT', '5')))
            except Exception:
                min_increase_pct = 5.0

            # Determine logs directory and file to read
            try:
                logs_dir = os.getenv('LOGS_DIR')
                if not logs_dir or logs_dir.strip() == '':
                    # Default to app/mining_environment/logs relative to this file
                    logs_dir = str(Path(__file__).resolve().parent.parent / 'logs')
            except Exception:
                logs_dir = str(Path(__file__).resolve().parent.parent / 'logs')
            log_path = Path(logs_dir) / 'pid_gpu.log'

            if not log_path.exists():
                self.logger.info(f"[RC.verify] pid_gpu.log not found at {log_path} → cannot verify; skip lock")
                return False

            now_ts = time.time()
            window_start = now_ts - float(max(1, int(window_sec)))

            def _parse_hashrate(text: str) -> Optional[float]:
                """Extract and normalize hashrate in H/s from a text line. Returns None if not found."""
                try:
                    # Look for patterns like: 125.4 MH/s, 1.2 GH/s, 950 kH/s, 500 H/s
                    m = re.search(r"(?i)(\d+(?:[\.,]\d+)?)\s*([KMGT]?)[Hh]\s*/\s*s", text)
                    if not m:
                        return None
                    num_s = m.group(1).replace(',', '.')
                    prefix = m.group(2).upper() if m.group(2) else ''
                    base = float(num_s)
                    mult = 1.0
                    if prefix == 'K':
                        mult = 1e3
                    elif prefix == 'M':
                        mult = 1e6
                    elif prefix == 'G':
                        mult = 1e9
                    elif prefix == 'T':
                        mult = 1e12
                    return base * mult
                except Exception:
                    return None

            hashrates: List[tuple] = []  # (ts, rate_hs)

            # Efficient read: keep a bounded deque of recent lines to limit memory
            from collections import deque as _deque
            recent_lines = _deque(maxlen=5000)
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        recent_lines.append(line)
            except Exception as e:
                self.logger.warning(f"[RC.verify] Failed reading {log_path}: {e}")
                return False

            # Parse both JSON and raw formats
            for line in list(recent_lines):
                line = line.strip()
                if not line:
                    continue

                parsed_ts: Optional[float] = None
                parsed_pid: Optional[int] = None
                text_payload: Optional[str] = None

                # Attempt JSON first
                try:
                    obj = json.loads(line)
                    # JSON structured runtime output has 'output' field
                    if isinstance(obj, dict) and 'output' in obj:
                        parsed_ts = float(obj.get('timestamp', now_ts))
                        parsed_pid = int(obj.get('pid')) if 'pid' in obj else None
                        text_payload = str(obj.get('output', ''))
                except Exception:
                    obj = None

                if parsed_ts is None or parsed_pid is None or text_payload is None:
                    # Fallback: raw text format like: [ts] [Runtime: xx] [PID: 1234] actual_output
                    try:
                        m = re.match(r"^\[(?P<ts>\d{4}-\d{2}-\d{2} [0-9:\.]+)\]\s+\[Runtime:[^\]]+\]\s+\[PID:\s*(?P<pid>\d+)\]\s+(?P<out>.*)$", line)
                        if m:
                            ts_str = m.group('ts')
                            parsed_pid = int(m.group('pid'))
                            text_payload = m.group('out')
                            try:
                                parsed_ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f").timestamp()
                            except ValueError:
                                parsed_ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
                    except Exception:
                        parsed_ts = None

                if parsed_ts is None or parsed_pid is None or text_payload is None:
                    continue
                if parsed_pid != int(pid):
                    continue
                if parsed_ts < window_start:
                    continue

                rate = _parse_hashrate(text_payload)
                if rate is not None and rate > 0:
                    hashrates.append((parsed_ts, rate))

            if len(hashrates) < 2:
                self.logger.info(f"[RC.verify] Not enough hashrate samples in last {window_sec}s for PID={pid} → skip lock")
                return False

            # Sort by timestamp and compute increase percentage (first → last)
            hashrates.sort(key=lambda x: x[0])
            first_ts, first_rate = hashrates[0]
            last_ts, last_rate = hashrates[-1]

            if first_rate <= 0:
                self.logger.info(f"[RC.verify] Baseline hashrate non-positive ({first_rate}) → skip lock")
                return False

            increase_pct = (last_rate - first_rate) / max(1e-9, first_rate) * 100.0

            # Temperature safety
            try:
                temp_now = self.get_gpu_temperature(gpu_index)
            except Exception:
                temp_now = None

            temp_ok = True
            if temp_now is not None and temp_max is not None:
                temp_ok = float(temp_now) <= float(temp_max)

            ok = (increase_pct >= float(min_increase_pct)) and temp_ok
            try:
                self.logger.info(
                    f"[RC.verify] PID={pid} GPU={gpu_index} | window={window_sec}s | samples={len(hashrates)} | "
                    f"first={first_rate:.3g} H/s → last={last_rate:.3g} H/s (Δ={increase_pct:.1f}%) | "
                    f"temp={temp_now}°C ≤ {temp_max}°C? {temp_ok} | result={ok}"
                )
            except Exception:
                pass
            return ok
        except Exception as e:
            self.logger.error(f"[RC.verify] Exception during verification: {e}")
            try:
                self.logger.debug(traceback.format_exc())
            except Exception:
                pass
            return False

    def is_nvml_initialized(self) -> bool:
        """
        Kiểm tra NVML đã được khởi tạo hay chưa.

        :return: True nếu NVML đã khởi tạo, False nếu chưa.
        """
        return self.gpu_initialized

    def get_gpu_count(self) -> int:
        """
        Lấy số lượng GPU (đồng bộ).

        :return: Số GPU (int).
        """
        if not self.gpu_initialized:
            return 0
        try:
            return pynvml.nvmlDeviceGetCount()
        except pynvml.NVMLError:
            return 0

    def get_handle(self, gpu_index: int):
        """
        Lấy handle của GPU theo chỉ số (đồng bộ) với cache TTL.

        :param gpu_index: Chỉ số GPU.
        :return: Handle thiết bị GPU, hoặc None nếu lỗi.
        """
        if not self.gpu_initialized:
            self.logger.error("[GPUResourceManager] (trình quản lý tài nguyên GPU) chưa init (chưa khởi tạo). Không thể lấy [GPU handle] (tay cầm thiết bị GPU – định danh thiết bị).")
            return None
        try:
            now = time.time()
            with self._lock:
                h = self._handle_cache.get(gpu_index)
                ts = self._handle_cache_time.get(gpu_index, 0.0)
                if h is not None and (now - ts) < self.handle_cache_ttl_sec:
                    return h
                handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
                self._handle_cache[gpu_index] = handle
                self._handle_cache_time[gpu_index] = now
                self.logger.debug(f"Đã lấy (refresh) handle cho GPU={gpu_index}")
                return handle
        except pynvml.NVMLError as e:
            self.logger.error(f"Lỗi khi lấy handle GPU={gpu_index}: {e}")
            return None

    def get_gpu_power_limit(self, gpu_index: int) -> Optional[int]:
        """
        Trả về power limit (W) của GPU (đồng bộ).

        :param gpu_index: Chỉ số GPU.
        :return: Power limit (int) hoặc None nếu lỗi.
        """
        if not self.gpu_initialized:
            self.logger.error("[GPUResourceManager] (trình quản lý tài nguyên GPU) chưa init (chưa khởi tạo). Không thể lấy [power limit] (giới hạn công suất).")
            return None
        try:
            handle = self.get_handle(gpu_index)
            if handle is None:
                self.logger.error(f"Không thể lấy handle cho GPU={gpu_index}.")
                return None
            limit_mw = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
            limit_w = int(limit_mw // 1000)  # convert mW -> W
            self.logger.debug(f"Power limit hiện tại GPU={gpu_index}: {limit_w}W")
            return limit_w
        except Exception as e:
            self.logger.error(f"Lỗi get_gpu_power_limit GPU={gpu_index}: {e}")
            return None

    def get_gpu_power_usage(self, gpu_index: int) -> Optional[float]:
        """
        **Get GPU Power Usage** (lấy mức tiêu thụ điện hiện tại của GPU – đơn vị Watt)
        
        Backward-compat alias để đáp ứng các callsite hiện có.
        - Ưu tiên NVML; nếu không đọc được, trả None để callsite xử lý fallback.
        
        :param gpu_index: Chỉ số GPU
        :return: Công suất hiện tại (W) hoặc None nếu không đọc được
        """
        try:
            if not self.gpu_initialized:
                return None
            handle = self.get_handle(gpu_index)
            if handle is None:
                return None
            power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
            return float(power_mw) / 1000.0  # mW -> W
        except Exception as e:
            self.logger.debug(f"[GPUResourceManager] Cannot read power usage for GPU={gpu_index}: {e}")
            return None

    # Backward-compat alias (bí danh tương thích ngược)
    get_current_power_usage = get_gpu_power_usage

    # ========================= Internal helpers =========================
    def _compute_dynamic_ttl(self, base_ttl: float) -> float:
        """
        **Dynamic TTL** (TTL động – điều chỉnh theo mức sử dụng GPU hiện tại)
        - Khi tải cao (util ≥ 80%): TTL ngắn (lấy mẫu thường xuyên hơn)
        - Khi tải thấp: TTL dài hơn để giảm NVML calls
        Env/cấu hình:
        - DYNAMIC_METRICS_TTL (bật/tắt – mặc định bật)
        - METRICS_CACHE_MIN_TTL_SEC (mặc định 0.2s)
        - METRICS_CACHE_MAX_TTL_SEC (mặc định 2.0s)
        """
        try:
            enabled = os.getenv('DYNAMIC_METRICS_TTL', '1').lower() in ('1', 'true', 'yes')
        except Exception:
            enabled = True
        if not enabled:
            return base_ttl

        try:
            min_ttl = float(os.getenv('METRICS_CACHE_MIN_TTL_SEC', str(self.config.get('metrics_cache_min_ttl_sec', 0.2))))
        except Exception:
            min_ttl = 0.2
        try:
            max_ttl = float(os.getenv('METRICS_CACHE_MAX_TTL_SEC', str(self.config.get('metrics_cache_max_ttl_sec', 2.0))))
        except Exception:
            max_ttl = 2.0

        # Lấy utilization tối đa từ snapshot trước (nếu có)
        max_util = 0.0
        try:
            if self._metrics_cache and self._metrics_cache.utilization:
                vals = [v for v in self._metrics_cache.utilization.values() if isinstance(v, (int, float)) and v is not None]
                if vals:
                    max_util = max(vals)
        except Exception:
            pass

        # Mapping đơn giản: util cao → TTL ngắn; util thấp → TTL dài
        if max_util >= 0.8:
            ttl = min_ttl
        elif max_util >= 0.5:
            ttl = base_ttl
        elif max_util >= 0.2:
            ttl = min(max_ttl, max(min_ttl, base_ttl * 1.5))
        else:
            ttl = max_ttl

        return max(min_ttl, min(max_ttl, ttl))

    def _collect_metrics_with_nvidia_smi(self, indices: Optional[List[int]] = None):
        """
        **nvidia-smi Fallback** (phương án dự phòng – khi thiếu pynvml)
        Thu thập: index, temperature (°C), power (W), utilization (%), memory.used/total (MiB)
        Trả về tuple: (indices, temps, powers, utils, mem_used_bytes, mem_total_bytes) hoặc None nếu lỗi.
        """
        try:
            query = 'index,temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total'
            cmd = ['nvidia-smi', f'--query-gpu={query}', '--format=csv,noheader,nounits']
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
            temps: Dict[int, Optional[float]] = {}
            powers: Dict[int, Optional[float]] = {}
            utils: Dict[int, Optional[float]] = {}
            mem_used: Dict[int, Optional[int]] = {}
            mem_total: Dict[int, Optional[int]] = {}
            idx_list: List[int] = []

            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 6:
                    continue
                try:
                    idx = int(parts[0])
                except Exception:
                    continue
                if indices is not None and idx not in indices:
                    continue

                def _safe_float(s: str) -> Optional[float]:
                    try:
                        if s is None:
                            return None
                        t = str(s).strip().lower()
                        if t in ('', 'n/a', 'na', 'nan', 'inf', '-inf'):
                            return None
                        return float(t)
                    except Exception:
                        return None

                t = _safe_float(parts[1])
                p = _safe_float(parts[2])
                u = _safe_float(parts[3])
                mu = _safe_float(parts[4])
                mt = _safe_float(parts[5])

                temps[idx] = t if t is not None else None
                powers[idx] = p if p is not None else None
                utils[idx] = (u / 100.0) if u is not None else None
                # memory MiB → bytes
                mem_used[idx] = int(mu * 1024 * 1024) if mu is not None else None
                mem_total[idx] = int(mt * 1024 * 1024) if mt is not None else None
                idx_list.append(idx)

            if not idx_list:
                return None
            # Duy nhất hoá và giữ thứ tự xuất hiện
            seen: Set[int] = set()
            uniq_indices: List[int] = []
            for i in idx_list:
                if i not in seen:
                    seen.add(i)
                    uniq_indices.append(i)
            return uniq_indices, temps, powers, utils, mem_used, mem_total
        except Exception as e:
            try:
                self.logger.warning(f"[GPUResourceManager] nvidia-smi fallback failed: {e}")
            except Exception:
                pass
            return None

    def get_metrics_snapshot(self, ttl_sec: Optional[float] = None) -> GpuMetricsSnapshot:
        """
        Trả về ảnh chụp số liệu GPU hiện thời với cache TTL để giảm NVML calls.

        :param ttl_sec: TTL yêu cầu (giây). Nếu None dùng cấu hình mặc định.
        :return: GpuMetricsSnapshot
        """
        if not self.gpu_initialized:
            # Fallback khi NVML chưa sẵn sàng
            fb = self._collect_metrics_with_nvidia_smi()
            if fb is not None:
                fb_indices, temps, powers, utils, mem_used, mem_total = fb
                snapshot = GpuMetricsSnapshot(
                    timestamp=time.time(),
                    gpu_indices=fb_indices,
                    temperature_c=temps,
                    power_watts=powers,
                    utilization=utils,
                    mem_used_bytes=mem_used,
                    mem_total_bytes=mem_total
                )
                with self._lock:
                    self._metrics_cache = snapshot
                    self._metrics_cache_time = snapshot.timestamp
                return snapshot
            # Nếu fallback cũng thất bại → trả snapshot rỗng
            ts = time.time()
            return GpuMetricsSnapshot(
                timestamp=ts,
                gpu_indices=[],
                temperature_c={}, power_watts={}, utilization={},
                mem_used_bytes={}, mem_total_bytes={}
            )

        now = time.time()
        with self._lock:
            base_ttl = self.metrics_cache_ttl_sec if ttl_sec is None else float(ttl_sec)
            ttl = self._compute_dynamic_ttl(base_ttl) if ttl_sec is None else base_ttl
            if self._metrics_cache and (now - self._metrics_cache_time) < ttl:
                return self._metrics_cache

        # Thu thập số liệu mới
        gpu_count = self.get_gpu_count()
        if gpu_count <= 0:
            fb = self._collect_metrics_with_nvidia_smi()
            if fb is not None:
                fb_indices, temps, powers, utils, mem_used, mem_total = fb
                snapshot = GpuMetricsSnapshot(
                    timestamp=time.time(),
                    gpu_indices=fb_indices,
                    temperature_c=temps,
                    power_watts=powers,
                    utilization=utils,
                    mem_used_bytes=mem_used,
                    mem_total_bytes=mem_total
                )
                with self._lock:
                    self._metrics_cache = snapshot
                    self._metrics_cache_time = snapshot.timestamp
                return snapshot
            # Fallback thất bại → snapshot rỗng
            ts = time.time()
            return GpuMetricsSnapshot(
                timestamp=ts,
                gpu_indices=[],
                temperature_c={}, power_watts={}, utilization={},
                mem_used_bytes={}, mem_total_bytes={}
            )
        indices = list(range(gpu_count))
        temps: Dict[int, Optional[float]] = {}
        powers: Dict[int, Optional[float]] = {}
        utils: Dict[int, Optional[float]] = {}
        mem_used: Dict[int, Optional[int]] = {}
        mem_total: Dict[int, Optional[int]] = {}

        for i in indices:
            try:
                handle = self.get_handle(i)
                if handle is None:
                    temps[i] = None; powers[i] = None; utils[i] = None
                    mem_used[i] = None; mem_total[i] = None
                    continue
                try:
                    temps[i] = float(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
                except Exception:
                    temps[i] = None
                try:
                    powers[i] = float(pynvml.nvmlDeviceGetPowerUsage(handle)) / 1000.0
                except Exception:
                    powers[i] = None
                try:
                    util_obj = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    try:
                        self.logger.debug(f"[GPUResourceManager] Utilization object GPU={i}: type={type(util_obj)}, attrs={dir(util_obj) if hasattr(util_obj, '__dict__') or hasattr(util_obj, '__slots__') else 'n/a'}")
                    except Exception:
                        pass
                    # Hỗ trợ cả trường hợp NVML trả về struct có thuộc tính 'gpu'
                    # lẫn trường hợp trả về giá trị phần trăm thô (int/float)
                    raw_util_pct = getattr(util_obj, 'gpu', util_obj)
                    if raw_util_pct is None:
                        utils[i] = None
                    else:
                        utils[i] = float(raw_util_pct) / 100.0
                    try:
                        self.logger.debug(f"[GPUResourceManager] Utilization GPU={i}: raw_pct={raw_util_pct}, ratio={utils[i]}")
                    except Exception:
                        pass
                except Exception as e:
                    try:
                        self.logger.debug(f"[GPUResourceManager] Utilization read failed on GPU {i}: {e}")
                    except Exception:
                        pass
                    utils[i] = None
                try:
                    m = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    mem_used[i] = int(m.used)
                    mem_total[i] = int(m.total)
                except Exception:
                    mem_used[i] = None
                    mem_total[i] = None
            except Exception as e:
                self.logger.debug(f"[GPUResourceManager] Snapshot error on GPU {i}: {e}")
                temps[i] = None; powers[i] = None; utils[i] = None
                mem_used[i] = None; mem_total[i] = None

        snapshot = GpuMetricsSnapshot(
            timestamp=time.time(),
            gpu_indices=indices,
            temperature_c=temps,
            power_watts=powers,
            utilization=utils,
            mem_used_bytes=mem_used,
            mem_total_bytes=mem_total
        )
        try:
            self.logger.debug(f"[GPUResourceManager] Final snapshot utilization: {snapshot.utilization}")
        except Exception:
            pass
        with self._lock:
            self._metrics_cache = snapshot
            self._metrics_cache_time = snapshot.timestamp
        return snapshot

    def set_gpu_power_limit(self, pid: Optional[int], gpu_index: int, power_limit_w: int) -> bool:
        """
        Đặt power limit cho GPU (đồng bộ).

        :param pid: PID cần quản lý, có thể None nếu áp dụng chung.
        :param gpu_index: Chỉ số GPU.
        :param power_limit_w: Power limit cần đặt (W).
        :return: True nếu thành công, False nếu thất bại.
        """
        if not self.gpu_initialized:
            self.logger.error("[GPUResourceManager] (trình quản lý tài nguyên GPU) chưa init (chưa khởi tạo). Không thể set [power limit] (đặt giới hạn công suất).")
            return False
        try:
            handle = self.get_handle(gpu_index)
            if handle is None or power_limit_w <= 0:
                return False

            # Lấy giới hạn power limit từ GPU
            try:
                min_limit_mw, max_limit_mw = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(handle)
                min_limit_w = min_limit_mw // 1000
                max_limit_w = max_limit_mw // 1000
                
                # Validate và điều chỉnh power limit trong khoảng cho phép
                if power_limit_w < min_limit_w:
                    self.logger.warning(f"Power limit {power_limit_w}W dưới mức tối thiểu {min_limit_w}W, điều chỉnh lên {min_limit_w}W")
                    power_limit_w = min_limit_w
                elif power_limit_w > max_limit_w:
                    self.logger.warning(f"Power limit {power_limit_w}W vượt mức tối đa {max_limit_w}W, điều chỉnh xuống {max_limit_w}W")
                    power_limit_w = max_limit_w
            except pynvml.NVMLError as e:
                self.logger.warning(f"Không thể lấy power limit constraints, sử dụng giá trị mặc định: {e}")
                # Fallback cho Tesla T4
                max_limit_w = 70
                if power_limit_w > max_limit_w:
                    self.logger.warning(f"Power limit {power_limit_w}W có thể vượt giới hạn, điều chỉnh xuống {max_limit_w}W")
                    power_limit_w = max_limit_w

            # Lưu power limit cũ
            current_mw = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
            current_w = current_mw // 1000
            if pid is not None:
                if pid not in self.process_gpu_settings:
                    self.process_gpu_settings[pid] = {}
                if gpu_index not in self.process_gpu_settings[pid]:
                    self.process_gpu_settings[pid][gpu_index] = {}
                # Chỉ lưu giá trị gốc nếu chưa có, tránh ghi đè khi step-wise
                if 'power_limit_w' not in self.process_gpu_settings[pid][gpu_index]:
                    self.process_gpu_settings[pid][gpu_index]['power_limit_w'] = current_w

            # Enforce dwell-time between power changes to prevent thrashing
            try:
                dwell_sec = int(os.getenv('POWER_DWELL_SEC', '30'))
            except Exception:
                dwell_sec = 30
            last_change = self._last_power_change_time.get(gpu_index)
            if last_change is not None and (time.time() - last_change) < dwell_sec:
                remaining = int(dwell_sec - (time.time() - last_change))
                self.logger.info(f"⏱️ Dwell-time active: skipping power change for GPU={gpu_index} ({remaining}s remaining)")
                return True

            # Clamp max delta per change to smooth transitions
            try:
                max_delta = int(os.getenv('POWER_MAX_DELTA_W', '15'))
            except Exception:
                max_delta = 15
            last_set_power = self._last_power_limit_w.get(gpu_index, current_w)
            if abs(power_limit_w - last_set_power) > max_delta:
                direction = 1 if power_limit_w > last_set_power else -1
                clamped = last_set_power + direction * max_delta
                self.logger.info(f"🔧 Clamped power change to ±{max_delta}W step: request {power_limit_w}W → {clamped}W (GPU={gpu_index})")
                power_limit_w = clamped

            # Enforce minimum utilization policy: avoid excessive down-capping unless explicitly allowed
            try:
                allow_under_80 = os.getenv('ALLOW_UTIL_UNDER_80', '0').lower() in ('1','true','yes')
            except Exception:
                allow_under_80 = False
            if not allow_under_80:
                # Clamp to at least 80% of current limit to prevent drastic drops
                try:
                    current_mw_snapshot = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
                    current_w_snapshot = max(1, int(current_mw_snapshot // 1000))
                    min_allowed_w = max(50, int(current_w_snapshot * 0.8))
                    if power_limit_w < min_allowed_w:
                        self.logger.info(f"🛡️ Enforcing min power limit {min_allowed_w}W (requested {power_limit_w}W) to keep utilization ≥80%")
                        power_limit_w = min_allowed_w
                except Exception:
                    pass
            new_limit_mw = power_limit_w * 1000
            pynvml.nvmlDeviceSetPowerManagementLimit(handle, new_limit_mw)
            # Record last power change
            self._last_power_change_time[gpu_index] = time.time()
            self._last_power_limit_w[gpu_index] = power_limit_w
            self.logger.debug(f"Set power limit={power_limit_w}W cho GPU={gpu_index}, PID={pid}.")
            return True
        except pynvml.NVMLError as error:
            self.logger.error(f"Lỗi NVML set power limit GPU={gpu_index}: {error}")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi set power limit GPU={gpu_index}: {e}")
            return False

    def set_gpu_clocks(self, pid: Optional[int], gpu_index: int, sm_clock: int, mem_clock: int) -> bool:
        """
        Đặt xung nhịp GPU (đồng bộ) thông qua nvidia-smi commands.

        :param pid: PID cần quản lý, có thể None nếu áp dụng chung.
        :param gpu_index: Chỉ số GPU.
        :param sm_clock: Mức SM clock (MHz).
        :param mem_clock: Mức Memory clock (MHz).
        :return: True nếu thành công, False nếu thất bại.
        """
        if not self.gpu_initialized:
            self.logger.error("[GPUResourceManager] (trình quản lý tài nguyên GPU) chưa init (chưa khởi tạo). Không thể set [GPU clocks] (đặt xung nhịp GPU).")
            return False
        try:
            handle = self.get_handle(gpu_index)
            if handle is None or sm_clock <= 0 or mem_clock <= 0:
                return False

            # Lấy SM/MEM clock hiện tại (NVML API chuẩn)
            current_sm_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
            current_mem_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)

            # Guard: chỉ cho phép lock xung khi ALLOW_CLOCK_LOCK=1
            try:
                allow_clock_lock = os.getenv('ALLOW_CLOCK_LOCK', '1').lower() in ('1','true','yes')
            except Exception:
                allow_clock_lock = False
            if not allow_clock_lock:
                env_acl = os.getenv('ALLOW_CLOCK_LOCK')
                self.logger.info(f"[RC] ⛔ Skipping clock lock (ALLOW_CLOCK_LOCK={env_acl}) | requested SM={sm_clock}MHz, MEM={mem_clock}MHz | gpu={gpu_index}")
                return False

            # Safety gates: temperature + NVML supported check before locking
            try:
                temp = self.get_gpu_temperature(gpu_index)
                if temp is not None and temp >= self.temp_warning:
                    self.logger.warning(f"[RC] ⚠️ Temperature {temp}°C >= warning {self.temp_warning}°C → skip clock lock | gpu={gpu_index}")
                    return False
            except Exception:
                pass

            # Nếu closed-loop chưa bật và xung hiện tại < 800 MHz, bỏ qua lock để tránh kẹt xung thấp
            try:
                cl_enabled = os.getenv('GPU_CLOSED_LOOP_ENABLED', '0').lower() in ('1','true','yes')
            except Exception:
                cl_enabled = False
            if (not cl_enabled) and current_sm_clock < 800:
                self.logger.warning(f"[RC] ⚠️ Closed-loop disabled and current SM clock {current_sm_clock}MHz < 800MHz → skip locking to avoid low-clock trap | gpu={gpu_index}")
                return False

            if pid is not None:
                if pid not in self.process_gpu_settings:
                    self.process_gpu_settings[pid] = {}
                if gpu_index not in self.process_gpu_settings[pid]:
                    self.process_gpu_settings[pid][gpu_index] = {}
                # Chỉ lưu giá trị gốc nếu chưa có
                if 'sm_clock_mhz' not in self.process_gpu_settings[pid][gpu_index]:
                    self.process_gpu_settings[pid][gpu_index]['sm_clock_mhz'] = current_sm_clock
                if 'mem_clock_mhz' not in self.process_gpu_settings[pid][gpu_index]:
                    self.process_gpu_settings[pid][gpu_index]['mem_clock_mhz'] = current_mem_clock

            # Capability detection (NVML-first) trước khi khóa clocks
            mem_lock_supported = True
            try:
                # Một số GPU (ví dụ T4) không hỗ trợ lock memory clocks
                # Kiểm tra nhẹ bằng cách đọc clock info; nếu lỗi đặc thù, coi như không hỗ trợ
                _ = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
            except Exception as cap_e:
                mem_lock_supported = False
                self.logger.info(f"ℹ️ [CAPABILITY] Memory clock lock unsupported on this GPU: {cap_e}. Skipping mem clock lock.")

            # Set SM clock
            cmd_sm = [
                'nvidia-smi',
                '-i', str(gpu_index),
                '--lock-gpu-clocks=' + str(sm_clock)
            ]
            subprocess.run(cmd_sm, check=True)
            self.logger.debug(f"Set SM clock={sm_clock}MHz cho GPU={gpu_index}, PID={pid}.")

            # Set MEM clock (nếu hỗ trợ)
            if mem_lock_supported:
                cmd_mem = [
                    'nvidia-smi',
                    '-i', str(gpu_index),
                    '--lock-memory-clocks=' + str(mem_clock)
                ]
                subprocess.run(cmd_mem, check=True)
                self.logger.debug(f"Set MEM clock={mem_clock}MHz cho GPU={gpu_index}, PID={pid}.")
            else:
                self.logger.info(f"ℹ️ [CAPABILITY] Skipped locking MEM clock for GPU={gpu_index} (unsupported).")

            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Lỗi nvidia-smi set clocks GPU={gpu_index}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi set clocks GPU={gpu_index}: {e}")
            return False

    def reset_app_clocks_nvml(self, gpu_index: int) -> bool:
        """
        Reset ứng dụng clocks (Applications Clocks) theo NVML-first.

        - Ưu tiên NVML: nvmlDeviceResetApplicationsClocks(handle)
        - Trả về True nếu NVML báo thành công, False nếu lỗi/không hỗ trợ
        """
        try:
            if not self.gpu_initialized:
                self.logger.error("[RC.reset] NVML chưa khởi tạo – không thể reset applications clocks.")
                return False
            handle = self.get_handle(gpu_index)
            if handle is None:
                self.logger.error(f"[RC.reset] Không lấy được handle cho GPU={gpu_index}.")
                return False
            pynvml.nvmlDeviceResetApplicationsClocks(handle)
            self.logger.info(f"[RC.reset] ✅ NVML nvmlDeviceResetApplicationsClocks thành công | GPU={gpu_index}")
            return True
        except pynvml.NVMLError as e:
            self.logger.warning(f"[RC.reset] NVML reset applications clocks không hỗ trợ/failed | GPU={gpu_index} | err={e}")
            return False
        except Exception as e:
            self.logger.error(f"[RC.reset] Exception khi NVML reset applications clocks | GPU={gpu_index} | err={e}")
            return False

    def reset_gpu_clocks_cli(self, gpu_index: int) -> bool:
        """
        Reset clocks bằng nvidia-smi (CLI fallback – phương án dự phòng):
        - Thứ tự cố gắng: -rac (reset applications clocks) → -rgc (reset gpu clocks) → --reset-memory-clocks/-rmc
        - Thành công nếu ít nhất một lệnh chạy ok.
        """
        attempts: List[List[str]] = [
            ['nvidia-smi', '-i', str(gpu_index), '-rac'],
            ['nvidia-smi', '-i', str(gpu_index), '-rgc'],
            ['nvidia-smi', '-i', str(gpu_index), '--reset-memory-clocks'],
            ['nvidia-smi', '-i', str(gpu_index), '-rmc'],  # alias nếu bản CLI hỗ trợ
        ]
        success_any = False
        for cmd in attempts:
            try:
                subprocess.run(cmd, check=True, timeout=10)
                success_any = True
                self.logger.info(f"[RC.reset] ✅ CLI success: {' '.join(cmd)}")
            except subprocess.TimeoutExpired as e:
                self.logger.warning(f"[RC.reset] ⏱️ CLI timeout: {' '.join(cmd)} | err={e}")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"[RC.reset] CLI failed: {' '.join(cmd)} | err={e}")
            except FileNotFoundError as e:
                self.logger.error(f"[RC.reset] nvidia-smi không tồn tại trong PATH | err={e}")
                break
            except Exception as e:
                self.logger.error(f"[RC.reset] CLI exception: {' '.join(cmd)} | err={e}")
        if not success_any:
            self.logger.warning(f"[RC.reset] ❌ Không reset được clocks bằng CLI cho GPU={gpu_index}")
        return success_any

    def verify_gpu_clock_state(self, gpu_index: int) -> bool:
        """
        Verify trạng thái sau reset bằng nvidia-smi:
        - Kỳ vọng: clocks.applications.graphics/memory ở trạng thái không khoá (N/A)
        - Ghi nhận: clocks.current.*, pstate, power.draw để quan sát
        Trả về True nếu nhìn thấy trạng thái "unlocked"; False nếu còn giá trị khoá rõ ràng.
        """
        try:
            cmd = [
                'nvidia-smi', '-i', str(gpu_index),
                '--query-gpu=clocks.applications.graphics,clocks.applications.memory,clocks.current.graphics,clocks.current.memory,pstate,power.draw',
                '--format=csv,noheader,nounits'
            ]
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=8)
            line = out.strip().splitlines()[0] if out else ''
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 6:
                self.logger.warning(f"[RC.verify] Output bất thường từ nvidia-smi: '{line}'")
                return True  # best-effort

            apps_g, apps_m, cur_g, cur_m, pstate, power = parts[:6]

            def _is_numeric(v: str) -> bool:
                try:
                    t = str(v).strip().lower()
                    if t in ('', 'n/a', 'na', 'nan'):
                        return False
                    float(t)
                    return True
                except Exception:
                    return False

            locked_g = _is_numeric(apps_g)
            locked_m = _is_numeric(apps_m)
            unlocked = not (locked_g or locked_m)
            try:
                self.logger.info(
                    f"[RC.verify] GPU={gpu_index} | apps(g,m)=({apps_g},{apps_m}) | current(g,m)=({cur_g},{cur_m}) | pstate={pstate} | power={power}W | unlocked={unlocked}"
                )
            except Exception:
                pass
            return unlocked
        except subprocess.TimeoutExpired as e:
            self.logger.warning(f"[RC.verify] ⏱️ Timeout khi gọi nvidia-smi verify | GPU={gpu_index} | err={e}")
            return True  # best-effort
        except Exception as e:
            self.logger.warning(f"[RC.verify] Không thể verify bằng nvidia-smi | GPU={gpu_index} | err={e}")
            return True  # best-effort

    def reset_gpu_clocks_and_verify(self, gpu_index: int, post_sleep_sec: Optional[float] = None) -> bool:
        """
        Orchestrator: NVML-first reset → CLI fallback → Verify.

        - post_sleep_sec: ngủ rất ngắn sau reset để phần cứng cập nhật trạng thái (mặc định 0.2s, tối đa 2s)
        - Trả về True nếu reset (NVML hoặc CLI) và verify thành công.
        """
        ok = False
        try:
            ok = self.reset_app_clocks_nvml(gpu_index)
            if not ok:
                ok = self.reset_gpu_clocks_cli(gpu_index)

            # Ngủ ngắn để phần cứng/phần mềm cập nhật trạng thái
            try:
                if post_sleep_sec is None:
                    post_sleep_sec = float(os.getenv('POST_RESET_SLEEP_SEC', '0.2'))
            except Exception:
                post_sleep_sec = 0.2
            post_sleep_sec = max(0.0, min(2.0, float(post_sleep_sec)))
            if post_sleep_sec > 0:
                time.sleep(post_sleep_sec)

            verified = self.verify_gpu_clock_state(gpu_index)
            if not verified:
                self.logger.warning(f"[RC.reset] Reset ok nhưng verify không đạt | GPU={gpu_index}")
            return bool(ok and verified)
        except Exception as e:
            self.logger.error(f"[RC.reset] Lỗi trong reset_gpu_clocks_and_verify | GPU={gpu_index} | err={e}")
            return False

    def limit_temperature(self, pid: Optional[int], gpu_index: int, temperature_threshold: float, fan_speed_increase: float) -> bool:
        """
        Quản lý nhiệt độ GPU bằng cách điều chỉnh quạt, công suất, và xung nhịp.

        :param pid: PID gắn với tiến trình cần điều chỉnh (để tracking/restore theo PID). Có thể None nếu áp dụng GPU-wide.
        :param gpu_index: Chỉ số GPU cần điều chỉnh.
        :param temperature_threshold: Ngưỡng nhiệt độ (°C).
        :param fan_speed_increase: Tỷ lệ tăng tốc độ quạt (giả định).
        :return: True nếu thành công, False nếu thất bại.
        """
        try:
            if not self.gpu_initialized:
                self.logger.error("[GPUResourceManager] (trình quản lý tài nguyên GPU) chưa init (chưa khởi tạo). Không thể thực hiện limit_temperature (giới hạn nhiệt độ).")
                return False

            # Lấy nhiệt độ hiện tại
            current_temperature = self.get_gpu_temperature(gpu_index)
            if current_temperature is None:
                self.logger.warning(f"Không thể lấy nhiệt độ GPU={gpu_index}. Bỏ qua điều chỉnh.")
                return False

            # Tăng tốc độ quạt
            if self.control_fan_speed(gpu_index, fan_speed_increase):
                self.logger.info(f"Quạt GPU={gpu_index} tăng thêm {fan_speed_increase}%.")
            else:
                self.logger.warning(f"Không thể điều chỉnh quạt GPU={gpu_index}.")

            # Lấy các giá trị hiệu năng hiện tại
            handle = self.get_handle(gpu_index)
            if not handle:
                self.logger.error(f"Không thể lấy handle GPU={gpu_index}.")
                return False

            try:
                current_sm_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
            except Exception as ex:
                self.logger.error(f"Không thể lấy xung nhịp SM của GPU={gpu_index}: {ex}")
                return False

            current_power_limit = self.get_gpu_power_limit(gpu_index)
            if current_power_limit is None:
                self.logger.error(f"Không thể lấy power limit GPU={gpu_index}.")
                return False

            # Xử lý dựa trên nhiệt độ (bảo toàn hiệu năng tối thiểu)
            if current_temperature > temperature_threshold:
                # GPU quá nóng => Throttle
                self.logger.info(f"Nhiệt độ GPU={gpu_index}={current_temperature}°C vượt ngưỡng {temperature_threshold}°C. Giảm hiệu năng.")

                # Tính mức độ throttle
                excess_temp = current_temperature - temperature_threshold
                if excess_temp <= 5:
                    throttle_pct = 10
                elif excess_temp <= 10:
                    throttle_pct = 20
                else:
                    throttle_pct = 30
                self.logger.debug(f"excess_temp={excess_temp}°C => throttle_pct={throttle_pct}%")

                # Giảm công suất
                # Tránh giảm quá sâu: giữ ít nhất 80% power hiện tại trừ khi ALLOW_UTIL_UNDER_80=1
                allow_under_80 = os.getenv('ALLOW_UTIL_UNDER_80', '0').lower() in ('1','true','yes')
                min_power = int(current_power_limit * (0.8 if not allow_under_80 else 0.5))
                desired_power_limit = max(min_power, int(current_power_limit * (1 - throttle_pct / 100)))
                if self.set_gpu_power_limit(pid, gpu_index, desired_power_limit):
                    self.logger.info(f"Giảm power limit GPU={gpu_index} xuống {desired_power_limit}W (PID={pid}).")

                # Giảm xung nhịp SM
                new_sm_clock = max(500, current_sm_clock - 100)
                if self.set_gpu_clocks(pid, gpu_index, new_sm_clock, 877):  # mem_clock luôn là 877
                    self.logger.info(f"Giảm xung nhịp SM GPU={gpu_index}: SM={new_sm_clock}MHz, MEM=877MHz (PID={pid}).")

            elif current_temperature < temperature_threshold:
                # GPU mát => Boost
                self.logger.info(f"Nhiệt độ GPU={gpu_index}={current_temperature}°C dưới ngưỡng {temperature_threshold}°C. Tăng hiệu năng.")

                # Tính mức độ boost
                diff_temp = temperature_threshold - current_temperature
                if diff_temp <= 5:
                    boost_pct = 10
                elif diff_temp <= 10:
                    boost_pct = 20
                else:
                    boost_pct = 30
                self.logger.debug(f"diff_temp={diff_temp}°C => boost_pct={boost_pct}%")

                # Tăng công suất (nhưng không vượt quá giới hạn GPU)
                # Lấy giới hạn tối đa từ GPU
                try:
                    min_limit_mw, max_limit_mw = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(handle)
                    max_limit_w = max_limit_mw // 1000
                except pynvml.NVMLError:
                    max_limit_w = 70  # Fallback cho Tesla T4
                
                desired_power_limit = min(max_limit_w, int(current_power_limit * (1 + boost_pct / 100)))
                if self.set_gpu_power_limit(pid, gpu_index, desired_power_limit):
                    self.logger.info(f"Tăng power limit GPU={gpu_index} lên {desired_power_limit}W (PID={pid}).")

                # Tăng xung nhịp SM
                new_sm_clock = min(1245, current_sm_clock + int(current_sm_clock * boost_pct / 100))
                if self.set_gpu_clocks(pid, gpu_index, new_sm_clock, 877):  # mem_clock luôn là 877
                    self.logger.info(f"Tăng xung nhịp SM GPU={gpu_index}: SM={new_sm_clock}MHz, MEM=877MHz (PID={pid}).")
            else:
                # Nhiệt độ trong khoảng an toàn
                self.logger.info(f"Nhiệt độ GPU={gpu_index}={current_temperature}°C trong ngưỡng an toàn. Không cần điều chỉnh.")

            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi quản lý nhiệt độ GPU={gpu_index}: {e}")
            return False

    def get_gpu_temperature(self, gpu_index: int) -> Optional[float]:
        """
        Lấy nhiệt độ GPU (đồng bộ).

        :param gpu_index: Chỉ số GPU.
        :return: Nhiệt độ GPU (float) hoặc None nếu lỗi.
        """
        try:
            if not self.gpu_initialized:
                self.logger.error("[GPUResourceManager] (trình quản lý tài nguyên GPU) chưa init (chưa khởi tạo). Không thể lấy nhiệt độ GPU.")
                return None
            handle = self.get_handle(gpu_index)
            if not handle:
                self.logger.error(f"Không thể lấy handle cho GPU={gpu_index}.")
                return None
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            self.logger.debug(f"Nhiệt độ GPU={gpu_index}: {temp}°C")
            return float(temp)
        except Exception as e:
            self.logger.error(f"Lỗi get_gpu_temperature GPU={gpu_index}: {e}")
            # Fallback using nvidia-smi (argv-list, không dùng shell=True)
            try:
                cmd = [
                    'nvidia-smi', '-i', str(gpu_index),
                    '--query-gpu=temperature.gpu',
                    '--format=csv,noheader,nounits'
                ]
                output = subprocess.check_output(cmd).decode().strip()
                # Lấy dòng đầu tiên
                line = output.splitlines()[0] if output else ''
                temp = float(line)
                self.logger.debug(f"Nhiệt độ GPU={gpu_index} từ fallback: {temp}°C")
                return temp
            except Exception as fallback_e:
                self.logger.error(f"Lỗi fallback get_gpu_temperature GPU={gpu_index}: {fallback_e}")
            return None

    def control_fan_speed(self, gpu_index: int, increase_percentage: float) -> bool:
        """
        Điều chỉnh quạt GPU bằng nvidia-settings (đồng bộ). Tuỳ driver hỗ trợ.

        :param gpu_index: Chỉ số GPU.
        :param increase_percentage: Mức tăng quạt (giả lập).
        :return: True nếu thành công, False nếu thất bại.
        """
        self.logger.info(f"[GPU Fan] control_fan_speed đã bị vô hiệu hóa.")
        return True

    def get_default_power_limit(self, gpu_index: int) -> int:
        """
        Lấy Power Limit mặc định của GPU.

        :param gpu_index: Chỉ số GPU.
        :return: Giá trị Power Limit mặc định (W), hoặc None nếu không lấy được.
        """
        try:
            handle = self.get_handle(gpu_index)
            return pynvml.nvmlDeviceGetPowerManagementDefaultLimit(handle) // 1000  # Chuyển từ mW sang W
        except Exception as e:
            self.logger.error(f"Lỗi khi lấy default power limit của GPU={gpu_index}: {e}")
            return None

    def predict_temperature_trajectory(self, gpu_index: int, power_watts: float, 
                                       time_horizon: float = 60.0) -> Dict[str, Any]:
        """
        **INTELLIGENCE LAYER: Predict temperature trajectory** (dự đoán quỹ đạo nhiệt độ)
        Using Newton's Cooling Law: dT/dt = -k(T - T_ambient) + Q/C
        
        :param gpu_index: GPU index to predict for
        :param power_watts: Power consumption in watts
        :param time_horizon: Time to predict ahead (seconds)
        :return: Prediction results with trajectory and safety status
        """
        try:
            # **Get current temperature** (lấy nhiệt độ hiện tại)
            handle = self.get_handle(gpu_index)
            if not handle:
                return {'error': 'Cannot get GPU handle'}
                
            current_temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            
            # **Calculate heat generation rate** (tính tốc độ sinh nhiệt)
            # Q = P × η (Power × Thermal Efficiency)
            heat_generation = power_watts * self.thermal_efficiency
            
            # **Predict temperature over time** (dự đoán nhiệt độ theo thời gian)
            trajectory = []
            dt = 1.0  # Time step (seconds)
            temp = float(current_temp)
            
            for t in range(int(time_horizon)):
                # **Newton's Cooling Law** (định luật làm lạnh Newton)
                # dT/dt = -k(T - T_ambient) + Q/C
                cooling_rate = -self.cooling_coefficient * (temp - self.ambient_temp)
                heating_rate = heat_generation / self.heat_capacity
                
                # **Temperature change** (thay đổi nhiệt độ)
                dT = (cooling_rate + heating_rate) * dt
                temp += dT
                
                # **Record trajectory point** (ghi điểm quỹ đạo)
                trajectory.append({
                    'time': t,
                    'temperature': temp,
                    'cooling_rate': cooling_rate,
                    'heating_rate': heating_rate
                })
                
            # **Analyze trajectory for safety** (phân tích quỹ đạo về an toàn)
            max_temp = max(p['temperature'] for p in trajectory)
            steady_state_temp = trajectory[-1]['temperature']
            
            # **Determine safety status** (xác định trạng thái an toàn)
            safety_status = 'SAFE'
            if max_temp >= self.temp_emergency:
                safety_status = 'EMERGENCY'
            elif max_temp >= self.temp_critical:
                safety_status = 'CRITICAL'
            elif max_temp >= self.temp_warning:
                safety_status = 'WARNING'
                
            # **Calculate cooling efficiency** (tính hiệu suất làm mát)
            cooling_efficiency = self.calculate_cooling_efficiency(
                current_temp, steady_state_temp, power_watts
            )
            
            # **Store history** (lưu lịch sử)
            if gpu_index not in self.temp_history:
                self.temp_history[gpu_index] = []
            self.temp_history[gpu_index].append((time.time(), current_temp))
            
            # Keep only last 100 entries
            if len(self.temp_history[gpu_index]) > 100:
                self.temp_history[gpu_index] = self.temp_history[gpu_index][-100:]
                
            return {
                'current_temperature': current_temp,
                'predicted_max': max_temp,
                'steady_state': steady_state_temp,
                'safety_status': safety_status,
                'cooling_efficiency': cooling_efficiency,
                'trajectory': trajectory[:10],  # Return first 10 points
                'recommendations': self.get_temperature_recommendations(max_temp, power_watts)
            }
            
        except Exception as e:
            self.logger.error(f"Temperature prediction error for GPU {gpu_index}: {e}")
            return {'error': str(e)}
    
    def calculate_cooling_efficiency(self, current_temp: float, steady_temp: float, 
                                    power_watts: float) -> float:
        """
        **Calculate cooling system efficiency** (tính hiệu suất hệ thống làm mát)
        
        :param current_temp: Current GPU temperature
        :param steady_temp: Predicted steady-state temperature
        :param power_watts: Power consumption
        :return: Efficiency percentage (0-100)
        """
        try:
            # **Ideal cooling would maintain ambient temperature** (làm mát lý tưởng duy trì nhiệt độ môi trường)
            temp_rise = steady_temp - self.ambient_temp
            
            # **Efficiency based on temperature rise per watt** (hiệu suất dựa trên độ tăng nhiệt/watt)
            if power_watts > 0:
                temp_per_watt = temp_rise / power_watts
                # Good cooling: < 0.2°C/W, Poor: > 0.5°C/W
                if temp_per_watt < 0.2:
                    efficiency = 100.0
                elif temp_per_watt > 0.5:
                    efficiency = 20.0
                else:
                    # Linear interpolation
                    efficiency = 100.0 - ((temp_per_watt - 0.2) / 0.3) * 80.0
            else:
                efficiency = 100.0
                
            return max(0.0, min(100.0, efficiency))
            
        except Exception:
            return 50.0  # Default medium efficiency
            
    def get_temperature_recommendations(self, predicted_max: float, power_watts: float) -> List[str]:
        """
        **Generate optimization recommendations** (tạo khuyến nghị tối ưu)
        
        :param predicted_max: Predicted maximum temperature
        :param power_watts: Current power consumption
        :return: List of recommendations
        """
        recommendations = []
        
        if predicted_max >= self.temp_emergency:
            recommendations.append("⚠️ EMERGENCY: Reduce power immediately to prevent damage")
            recommendations.append(f"📉 Reduce power by {int((power_watts * 0.3))}W minimum")
            
        elif predicted_max >= self.temp_critical:
            recommendations.append("🔴 CRITICAL: Temperature approaching limits")
            recommendations.append(f"📉 Consider reducing power by {int((power_watts * 0.2))}W")
            recommendations.append("🌡️ Increase cooling or reduce workload")
            
        elif predicted_max >= self.temp_warning:
            recommendations.append("🟡 WARNING: Temperature elevated but manageable")
            recommendations.append(f"📊 Monitor closely, consider {int((power_watts * 0.1))}W reduction")
            
        else:
            recommendations.append("✅ SAFE: Temperature within normal range")
            if predicted_max < self.temp_safe - 10:
                available_headroom = self.temp_safe - predicted_max
                recommendations.append(f"📈 Can increase power by ~{int(available_headroom * 2)}W safely")
                
        return recommendations

    def validate_pid_health(self, pid: int) -> Dict[str, Any]:
        """
        Enhanced PID Health Monitoring - Kiểm tra sức khỏe toàn diện của tiến trình.
        
        Kiểm tra:
        - Process existence (sự tồn tại tiến trình)
        - Process status (trạng thái: running/zombie/stopped) 
        - Memory usage (sử dụng bộ nhớ RAM và VRAM)
        - CPU utilization (mức sử dụng CPU)
        - GPU affinity (GPU được sử dụng bởi PID)
        - I/O activity (hoạt động đọc/ghi)
        - Health score (điểm sức khỏe tổng hợp 0-100)
        
        :param pid: Process ID cần kiểm tra
        :return: Dict chứa các metrics về sức khỏe của tiến trình
        """
        health_metrics = {
            'pid': pid,
            'pid_exists': False,
            'process_status': 'unknown',
            'memory_usage_mb': 0,
            'cpu_percent': 0.0,
            'gpu_index': None,
            'gpu_memory_mb': 0,
            'io_counters': None,
            'health_score': 0,
            'timestamp': time.time(),
            'errors': []
        }
        # Negative cache short-circuit (bỏ qua nhanh nếu PID đang trong cache âm tính)
        now = time.time()
        try:
            with self._lock:
                expiry = self._neg_cache_expiry.get(pid, 0.0)
            if expiry and now < expiry:
                # Chỉ log thưa để tránh spam
                last_log = self._pid_last_log_ts.get(pid, 0.0)
                if (now - last_log) > self._pid_log_suppress_window:
                    try:
                        self.logger.debug(f"[validate_pid_health] PID {pid} is negative-cached for {expiry - now:.3f}s remaining")
                    except Exception:
                        pass
                    self._pid_last_log_ts[pid] = now
                health_metrics['errors'].append('Process does not exist (negative_cache)')
                return health_metrics
        except Exception:
            # Nếu có lỗi ở nhánh cache, tiếp tục kiểm tra bình thường
            pass

        try:
            # Step 1: Check process existence
            if not psutil.pid_exists(pid):
                # Cập nhật negative cache + backoff luỹ thừa
                hits = 1
                backoff = self._pid_backoff_base
                try:
                    with self._lock:
                        hits = self._neg_cache_hits.get(pid, 0) + 1
                        self._neg_cache_hits[pid] = hits
                        backoff = min(self._pid_backoff_max, self._pid_backoff_base * (2 ** (hits - 1)))
                        self._neg_cache_expiry[pid] = now + backoff
                except Exception:
                    pass

                # Suppress log spam theo cửa sổ thời gian
                last_log = self._pid_last_log_ts.get(pid, 0.0)
                if (time.time() - last_log) > self._pid_log_suppress_window:
                    self.logger.warning(f"PID {pid} does not exist (backoff={backoff:.2f}s, hits={hits})")
                    self._pid_last_log_ts[pid] = time.time()
                else:
                    self.logger.debug(f"PID {pid} does not exist (suppressed)")

                health_metrics['errors'].append('Process does not exist')
                return health_metrics
            
            health_metrics['pid_exists'] = True
            # Alias for backward compatibility to avoid downstream KeyError
            health_metrics['exists'] = health_metrics['pid_exists']

            # Clear negative cache khi PID quay lại tồn tại
            try:
                with self._lock:
                    if pid in self._neg_cache_expiry:
                        del self._neg_cache_expiry[pid]
                    if pid in self._neg_cache_hits:
                        del self._neg_cache_hits[pid]
            except Exception:
                pass
            
            # Step 2: Get process object and basic info
            try:
                process = psutil.Process(pid)
                
                # Process status (running/zombie/stopped/sleeping)
                health_metrics['process_status'] = process.status()
                
                # Memory usage (RAM)
                mem_info = process.memory_info()
                health_metrics['memory_usage_mb'] = mem_info.rss / (1024 * 1024)  # Convert to MB
                
                # CPU utilization (call twice with interval for accurate measurement)
                process.cpu_percent()  # First call to initialize
                time.sleep(0.1)  # Small delay for measurement
                health_metrics['cpu_percent'] = process.cpu_percent()
                
                # I/O counters (if available)
                try:
                    io_counters = process.io_counters()
                    health_metrics['io_counters'] = {
                        'read_count': io_counters.read_count,
                        'write_count': io_counters.write_count,
                        'read_bytes': io_counters.read_bytes,
                        'write_bytes': io_counters.write_bytes
                    }
                except (psutil.AccessDenied, AttributeError):
                    self.logger.debug(f"Cannot access I/O counters for PID {pid}")
                
            except psutil.NoSuchProcess:
                health_metrics['errors'].append('Process terminated during check')
                return health_metrics
            except psutil.AccessDenied:
                health_metrics['errors'].append('Access denied to process info')
                self.logger.warning(f"Access denied to PID {pid} info")
            
            # Step 3: Check GPU affinity and VRAM usage
            gpu_index = self.infer_gpu_index_for_pid(pid)
            if gpu_index is not None:
                health_metrics['gpu_index'] = gpu_index
                
                # Get GPU memory usage for this PID
                try:
                    handle = self.get_handle(gpu_index)
                    if handle:
                        # Try to get process GPU memory usage
                        try:
                            procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                            for proc in procs:
                                if proc.pid == pid:
                                    health_metrics['gpu_memory_mb'] = proc.usedGpuMemory / (1024 * 1024)
                                    break
                        except:
                            # Fallback to graphics processes
                            try:
                                procs = pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle)
                                for proc in procs:
                                    if proc.pid == pid:
                                        health_metrics['gpu_memory_mb'] = proc.usedGpuMemory / (1024 * 1024)
                                        break
                            except:
                                pass
                except Exception as e:
                    self.logger.debug(f"Cannot get GPU memory for PID {pid}: {e}")
            
            # Step 4: Calculate health score (0-100)
            score = 100
            
            # Deduct points based on issues
            if health_metrics['process_status'] == 'zombie':
                score -= 50  # Zombie process is very unhealthy
            elif health_metrics['process_status'] == 'stopped':
                score -= 30  # Stopped process needs attention
            elif health_metrics['process_status'] == 'sleeping':
                score -= 5   # Sleeping is normal but not actively working
            
            # Memory usage check (deduct if using too much)
            if health_metrics['memory_usage_mb'] > 8192:  # > 8GB RAM
                score -= 20
            elif health_metrics['memory_usage_mb'] > 4096:  # > 4GB RAM
                score -= 10
            
            # CPU usage check
            if health_metrics['cpu_percent'] > 90:
                score -= 15  # Very high CPU usage
            elif health_metrics['cpu_percent'] < 1:
                score -= 10  # Too low, might be idle
            
            # GPU memory check
            if health_metrics['gpu_memory_mb'] > 8192:  # > 8GB VRAM
                score -= 15
            elif health_metrics['gpu_memory_mb'] < 100 and gpu_index is not None:
                score -= 10  # Has GPU but not using VRAM
            
            # Ensure score is in valid range
            health_metrics['health_score'] = max(0, min(100, score))
            
            # Log health check result
            self.logger.debug(
                f"PID {pid} health check: status={health_metrics['process_status']}, "
                f"RAM={health_metrics['memory_usage_mb']:.1f}MB, "
                f"CPU={health_metrics['cpu_percent']:.1f}%, "
                f"GPU={health_metrics['gpu_index']}, "
                f"VRAM={health_metrics['gpu_memory_mb']:.1f}MB, "
                f"score={health_metrics['health_score']}/100"
            )
            
        except Exception as e:
            health_metrics['errors'].append(f"Unexpected error: {str(e)}")
            self.logger.error(f"Error in validate_pid_health for PID {pid}: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
        
        return health_metrics

    def infer_gpu_index_for_pid(self, pid: int) -> Optional[int]:
        """
        Suy luận GPU index chứa tiến trình pid (per-PID mapping – ánh xạ PID sang GPU).

        Ưu tiên NVML (pynvml), fallback dùng nvidia-smi.
        """
        try:
            if not self.gpu_initialized:
                return None

            gpu_count = self.get_gpu_count()
            for idx in range(gpu_count):
                handle = self.get_handle(idx)
                if not handle:
                    continue
                # Thử API compute trước
                try:
                    get_procs = getattr(pynvml, 'nvmlDeviceGetComputeRunningProcesses', None)
                    if get_procs is not None:
                        procs = get_procs(handle)
                        for p in procs:
                            if getattr(p, 'pid', None) == pid:
                                return idx
                except Exception:
                    pass
                # Thử API graphics nếu compute không có
                try:
                    get_gfx_procs = getattr(pynvml, 'nvmlDeviceGetGraphicsRunningProcesses', None)
                    if get_gfx_procs is not None:
                        procs = get_gfx_procs(handle)
                        for p in procs:
                            if getattr(p, 'pid', None) == pid:
                                return idx
                except Exception:
                    pass

            # Fallback: nvidia-smi
            try:
                # Map uuid -> index
                uuid_map: Dict[str, int] = {}
                out = subprocess.check_output(
                    ['nvidia-smi', '--query-gpu=index,uuid', '--format=csv,noheader'],
                    text=True
                ).strip().splitlines()
                for line in out:
                    parts = [s.strip() for s in line.split(',')]
                    if len(parts) == 2:
                        uuid_map[parts[1]] = int(parts[0])

                procs_out = subprocess.check_output(
                    ['nvidia-smi', '--query-compute-apps=pid,gpu_uuid', '--format=csv,noheader'],
                    text=True
                ).strip().splitlines()
                for line in procs_out:
                    parts = [s.strip() for s in line.split(',')]
                    if len(parts) == 2 and parts[0].isdigit() and int(parts[0]) == pid:
                        uuid = parts[1]
                        if uuid in uuid_map:
                            return uuid_map[uuid]
            except Exception:
                pass

            return None
        except Exception as e:
            self.logger.error(f"infer_gpu_index_for_pid lỗi: {e}")
            return None

    def restore_gpu_settings_for_pid(self, pid: int, correlation_id: Optional[str] = None) -> bool:
        """
        Khôi phục lại thiết lập GPU đã thay đổi cho tiến trình pid (restore – trả về trạng thái trước đó).
        correlation_id (mã tương quan – ID để liên kết log của cùng một phiên restore)
        """
        try:
            cid = str(correlation_id) if correlation_id not in (None, '') else uuid.uuid4().hex
            saved = self.process_gpu_settings.get(pid)
            if not saved:
                self.logger.debug(f"[RC.restore] CID={cid} Không có thiết lập GPU đã lưu cho PID={pid} để khôi phục.")
                return True

            self.logger.info(f"[RC.restore] CID={cid} Bắt đầu restore PID={pid} cho {len(saved)} GPU(s)")

            for gpu_index, settings in saved.items():
                self.logger.info(f"[RC.restore] CID={cid} → GPU={gpu_index}: bắt đầu khôi phục")
                handle = self.get_handle(gpu_index)
                if not handle:
                    continue

                # Mở khoá bất kỳ lock clocks bằng nvidia-smi trước (idempotent – an toàn gọi nhiều lần)
                try:
                    try:
                        cmd = ['nvidia-smi', '-i', str(gpu_index), '-rgc']
                        r = subprocess.run(cmd, check=False, capture_output=True, text=True)
                        if r.returncode == 0:
                            self.logger.info(f"[RC.restore] [NVSMI] ✅ Unlock graphics clocks | GPU={gpu_index} | rc=0 | cmd={' '.join(cmd)}")
                        else:
                            stderr = (r.stderr or '').strip()
                            self.logger.warning(f"[RC.restore] [NVSMI] ❌ Unlock graphics clocks | GPU={gpu_index} | rc={r.returncode} | cmd={' '.join(cmd)} | stderr={stderr}")
                    except Exception as _e1:
                        self.logger.debug(f"[RC.restore] [NVSMI] Unlock graphics clocks exception | GPU={gpu_index} | ex={_e1}")
                    try:
                        cmd = ['nvidia-smi', '-i', str(gpu_index), '--reset-memory-clocks']
                        r = subprocess.run(cmd, check=False, capture_output=True, text=True)
                        if r.returncode == 0:
                            self.logger.info(f"[RC.restore] [NVSMI] ✅ Reset memory clocks | GPU={gpu_index} | rc=0 | cmd={' '.join(cmd)}")
                        else:
                            stderr = (r.stderr or '').strip()
                            self.logger.warning(f"[RC.restore] [NVSMI] ❌ Reset memory clocks | GPU={gpu_index} | rc={r.returncode} | cmd={' '.join(cmd)} | stderr={stderr}")
                    except Exception as _e2:
                        self.logger.debug(f"[RC.restore] [NVSMI] Reset memory clocks exception | GPU={gpu_index} | ex={_e2}")
                except Exception as _ue:
                    self.logger.debug(f"[RC.restore] NVSMI unlock sequence skipped due to unexpected error: {_ue}")

                # Khôi phục clocks bằng NVML (ứng dụng) nếu có
                try:
                    pynvml.nvmlDeviceResetApplicationsClocks(handle)
                    self.logger.info(f"[RC.restore] CID={cid} Đã reset application clocks cho GPU={gpu_index} (PID={pid}).")
                except Exception as e_nvml:
                    # Fallback tối giản: đã cố NVSMI unlock ở trên; chỉ ghi nhận lỗi NVML để tránh re-lock clocks
                    self.logger.warning(f"[RC.restore] CID={cid} NVML reset application clocks thất bại cho GPU={gpu_index}: {e_nvml}")

                # Khôi phục power limit nếu có
                if 'power_limit_w' in settings:
                    try:
                        self.set_gpu_power_limit(None, gpu_index, int(settings['power_limit_w']))
                        self.logger.info(f"[RC.restore] CID={cid} Đã khôi phục power limit GPU={gpu_index} về {settings['power_limit_w']}W (PID={pid}).")
                    except Exception as e3:
                        self.logger.warning(f"[RC.restore] CID={cid} Không thể khôi phục power limit GPU={gpu_index}: {e3}")

                # Hậu kiểm trạng thái sau restore (post-restore verification – chỉ log quan sát)
                try:
                    # Lấy trạng thái hiện tại
                    cur_pl = self.get_gpu_power_limit(gpu_index)
                    try:
                        h = self.get_handle(gpu_index)
                        cur_sm = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_SM) if h is not None else None
                        cur_mem = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_MEM) if h is not None else None
                    except Exception:
                        cur_sm, cur_mem = None, None
                    self.logger.info(
                        f"[RC.restore] CID={cid} Post-restore status | PID={pid} GPU={gpu_index} | power_limit={cur_pl}W, SM={cur_sm}MHz, MEM={cur_mem}MHz"
                    )
                    # Gọi verify để đánh giá xu hướng hashrate + an toàn nhiệt (không khóa clock tại đây)
                    try:
                        vw = None
                        envw = os.getenv('CLOCK_LOCK_VERIFY_WINDOW_SEC')
                        if envw not in (None, ''):
                            vw = int(envw)
                    except Exception:
                        vw = None
                    ok = self.verify_clock_lock_conditions(pid=pid, gpu_index=gpu_index, window_sec=vw)
                    self.logger.info(f"[RC.restore] CID={cid} Verification after restore | PID={pid} GPU={gpu_index} | result={ok}")
                except Exception as _ve:
                    self.logger.debug(f"[RC.restore] CID={cid} Post-restore verification error: {_ve}")

            # Xoá cache sau khi khôi phục
            try:
                del self.process_gpu_settings[pid]
            except Exception:
                pass

            self.logger.info(f"[RC.restore] CID={cid} Hoàn tất restore cho PID={pid}")
            return True
        except Exception as e:
            try:
                cid = str(correlation_id) if correlation_id not in (None, '') else 'unknown'
            except Exception:
                cid = 'unknown'
            self.logger.error(f"[RC.restore] CID={cid} restore_gpu_settings_for_pid lỗi: {e}")
            return False


###############################################################################
#                      SIMPLIFIED HARDWARE CONTROLLER                         #
###############################################################################

# HardwareController has been fully removed in favor of OptimizedHardwareController

###############################################################################
#                     OPTIMIZED HARDWARE CONTROLLER                          #
###############################################################################

def apply_gpu_controls(
    pid: int,
    params: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
    ) -> bool:
    """
    Backward-compatible alias (bí danh tương thích ngược – giữ API cũ) cho điều khiển GPU.
    Ủy quyền (delegate) sang OptimizedHardwareController.apply_optimization().
    """
    try:
        cfg = config or {}
        log = logger or resource_logger
        controller = OptimizedHardwareController(cfg, log)
        return controller.apply_optimization(pid, params)
    except Exception as e:
        try:
            (logger or resource_logger).error(f"[apply_gpu_controls] Alias error: {e}", exc_info=True)
        except Exception:
            pass
        return False

class OptimizedHardwareController:
    """
    ✅ ENHANCED: Hardware controller tối ưu không dùng GPU plugins
    Focus on NVML và compute-based control cho stealth mining
    
    Features:
    - Temperature safety checks with emergency scaling
    - NVML-first control with compute simulation fallback
    - Dynamic VRAM management to mimic AI workloads
    - Smooth power transitions to avoid spikes
    - Baseline verification and adjustment
    """
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize OptimizedHardwareController
        
        :param config: Configuration dict
        :param logger: Logger instance
        """
        # Use dedicated logger for OptimizedHardwareController to write optimizedhardwarecontroller.log
        try:
            from .module_loggers import get_optimized_hardware_controller_logger
        except ImportError:
            try:
                from module_loggers import get_optimized_hardware_controller_logger
            except ImportError:
                get_optimized_hardware_controller_logger = None  # type: ignore

        self.logger = get_optimized_hardware_controller_logger() if get_optimized_hardware_controller_logger else logger
        # Mirror critical OHC events to unified GPU optimization logger for easier tracing
        try:
            from .module_loggers import get_gpu_optimization_logger
            self._mirror_logger = get_gpu_optimization_logger()
        except Exception:
            self._mirror_logger = None
        self.config = config
        
        # Initialize GPU manager
        self.gpu_manager = GPUResourceManager(config, logger)
        
        # Check NVML availability
        self.nvml_available = self.gpu_manager.is_nvml_initialized()
        
        # Baseline metrics
        self.baseline_power = config.get('baseline_power', 150)  # Watts
        self.baseline_temp = config.get('baseline_temp', 65)     # Celsius
        self.baseline_vram = config.get('baseline_vram', 4.0)     # GB
        
        # Safety thresholds
        self.temp_critical = config.get('temp_critical', 78)      # Critical temp
        self.temp_warning = config.get('temp_warning', 72)       # Warning temp
        self.power_max = config.get('power_max', 200)            # Max power
        
        # **HASHRATE FIX: Profile settings with GPU_TARGET_UTIL-based allocation** (cài đặt profile với phân bổ dựa trên GPU_TARGET_UTIL)
        gpu_target_util = float(os.environ.get('GPU_TARGET_UTIL', '0.70'))  # Default 70% (Inference profile) from ENV
        self.profile = config.get('optimization_profile', {
            'vram_allocation': gpu_target_util,    # Use GPU_TARGET_UTIL instead of fixed 50%
            'compute_allocation': gpu_target_util,  # New: compute resource allocation
            'power_variation': 0.15,   # ±15% power variation
            'clock_variation': 0.10,   # ±10% clock variation
            'duty_cycle': min(0.95, gpu_target_util + 0.05)  # Slight boost for duty cycle
        })
        self.logger.info(f"🚀 **[HASHRATE-FIX] Resource allocation updated** ([SỬA LỖI-HASHRATE] Đã cập nhật phân bổ tài nguyên): vram={gpu_target_util*100}%, compute={gpu_target_util*100}%, duty_cycle={self.profile['duty_cycle']*100}%")
        
        # Active subprocess tracking
        self.active_subprocesses = []
        
        # Verification tracking
        self.last_verification = 0
        self.verification_interval = 30  # seconds
        # Allow ENV override for verification interval
        try:
            _vint = os.getenv('BASELINE_VERIFICATION_INTERVAL_SEC')
            if _vint not in (None, ''):
                self.verification_interval = max(5, int(float(_vint)))
        except Exception:
            pass
        # Per-PID time window (giây) để mô phỏng per-process rồi khôi phục
        self.per_pid_window_sec = config.get('per_pid_window_sec', 30)
        # Map sự kiện hủy restore theo (pid, gpu_index) để hủy sớm các luồng restore đang đợi
        self.restore_cancel_events = {}
        
        # **DAG SYNCHRONIZATION: Initialize DAG synchronizer** (đồng bộ DAG - quản lý tính toán DAG)
        self.dag_synchronizer = None
        if get_dag_synchronizer:
            try:
                self.dag_synchronizer = get_dag_synchronizer()
                self.logger.info("🔄 DAG Synchronizer initialized successfully")
            except Exception as e:
                self.logger.warning(f"⚠️ DAG Synchronizer initialization failed: {e}")
                self.dag_synchronizer = None
        else:
            self.logger.debug("🔄 DAG Synchronizer not available (module not imported)")
        
        # Mining algorithm configuration
        self.mining_config = config.get('mining_config', {
            'algorithm': 'ethash',  # Default mining algorithm
            'epoch': 450,          # Current epoch number
            'dag_size': 4.7        # DAG size in GB
        })
        
        # Feature flags via environment variables (cờ tính năng qua biến môi trường)
        self.dynamic_balancing_enabled = os.getenv('ENABLE_DYNAMIC_BALANCING', 'true').lower() == 'true'
        self.enable_dag_sync = os.getenv('ENABLE_DAG_SYNC', 'true').lower() == 'true'
        self.logger.info(f"🌐 Env flags -> ENABLE_DYNAMIC_BALANCING={self.dynamic_balancing_enabled}, ENABLE_DAG_SYNC={self.enable_dag_sync}")
        if self._mirror_logger:
            try:
                self._mirror_logger.info(f"[OHC] Env flags -> ENABLE_DYNAMIC_BALANCING={self.dynamic_balancing_enabled}, ENABLE_DAG_SYNC={self.enable_dag_sync}")
            except Exception:
                pass
        
        self.logger.info(f"✅ OptimizedHardwareController initialized (NVML: {self.nvml_available}, DAG: {self.dag_synchronizer is not None})")

        # Clean-code: cấu hình thời gian chờ DAG và helpers
        # Cho phép override bằng ENV: DAG_WAIT_TIMEOUT_SEC
        try:
            self.dag_wait_timeout_sec = int(os.getenv('DAG_WAIT_TIMEOUT_SEC', str(self.config.get('dag_wait_timeout_sec', 60))))
        except Exception:
            self.dag_wait_timeout_sec = int(self.config.get('dag_wait_timeout_sec', 60))

        # -------- Concurrency guard & backoff per-PID cho optimize_for_pid --------
        self._opt_global_lock: RLock = RLock()
        self._pid_optimize_locks: Dict[int, threading.Lock] = {}
        self._pid_optimize_miss_counts: Dict[int, int] = {}
        self._pid_optimize_next_allowed_ts: Dict[int, float] = {}
        self._opt_last_log_ts: Dict[int, float] = {}
        try:
            self._opt_backoff_base_sec: float = float(os.getenv('OHC_PID_BACKOFF_BASE_SEC', str(self.config.get('ohc_pid_backoff_base_sec', 5.0))))
        except Exception:
            self._opt_backoff_base_sec = 5.0
        try:
            self._opt_backoff_max_sec: float = float(os.getenv('OHC_PID_BACKOFF_MAX_SEC', str(self.config.get('ohc_pid_backoff_max_sec', 60.0))))
        except Exception:
            self._opt_backoff_max_sec = 60.0
        try:
            self._opt_log_suppress_window: float = float(os.getenv('OHC_LOG_SUPPRESS_SEC', str(self.config.get('ohc_log_suppress_sec', 20.0))))
        except Exception:
            self._opt_log_suppress_window = 20.0

    def ensure_dag_ready(self, gpu_index: int) -> bool:
        """
        **DAG SYNCHRONIZATION: Ensure DAG is ready for mining** (đảm bảo DAG sẵn sàng cho mining)
        
        :param gpu_index: GPU index to use for DAG calculation
        :return: True if DAG is ready, False otherwise
        """
        if not self.dag_synchronizer:
            self.logger.debug("📊 [OHC.ensure_dag_ready] DAG synchronizer not available, skipping check")
            return True  # Continue without DAG sync if not available
        
        try:
            epoch = self.mining_config.get('epoch', 450)
            algorithm = self.mining_config.get('algorithm', 'ethash')
            
            self.logger.info(f"🔍 [OHC.ensure_dag_ready] Checking DAG for {algorithm} epoch {epoch} on GPU {gpu_index}")
            
            # Check if DAG already exists
            dag_info = self.dag_synchronizer.get_dag_info(epoch, algorithm)
            
            if dag_info and dag_info.state == DAGState.COMPLETED:
                self.logger.info(f"✅ [OHC.ensure_dag_ready] DAG already ready for {algorithm} epoch {epoch}")
                return True
            
            # Register for DAG calculation
            should_calculate = self.dag_synchronizer.register_dag_calculation(epoch, algorithm, gpu_index)
            
            if should_calculate:
                self.logger.info(f"🚀 [OHC.ensure_dag_ready] GPU {gpu_index} starting DAG calculation for {algorithm} epoch {epoch}")
                
                # Simulate DAG calculation progress
                for progress in [0.25, 0.5, 0.75, 1.0]:
                    self.dag_synchronizer.update_progress(epoch, algorithm, gpu_index, progress)
                    self.logger.debug(f"📊 [OHC.ensure_dag_ready] DAG calculation progress: {progress*100:.0f}%")
                    time.sleep(0.5)  # Simulate calculation time
                
                # Complete DAG calculation
                dag_size = int(self.mining_config.get('dag_size', 4.7) * 1024**3)  # Convert GB to bytes
                dag_hash = hashlib.sha256(f"{algorithm}_{epoch}".encode()).hexdigest()
                # Chuyển DAG cache khỏi /tmp để tránh dữ liệu tạm: dùng LOGS_DIR/dag_cache
                dag_cache_root = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
                dag_path = f"{dag_cache_root}/dag_cache/{algorithm}_epoch_{epoch}.dag"
                
                self.dag_synchronizer.complete_calculation(
                    epoch, algorithm, gpu_index, 
                    dag_path, dag_size, dag_hash
                )
                self.logger.info(f"✅ [OHC.ensure_dag_ready] DAG calculation completed for {algorithm} epoch {epoch}")
                return True
            else:
                # Another GPU is calculating, wait for completion
                self.logger.info(f"⏳ [OHC.ensure_dag_ready] Waiting for DAG calculation by another GPU...")
                
                # Dùng timeout cấu hình để clean-code và dễ điều chỉnh
                if self.dag_synchronizer.wait_for_dag(epoch, algorithm, timeout=self.dag_wait_timeout_sec):
                    self.logger.info(f"✅ [OHC.ensure_dag_ready] DAG ready after waiting")
                    return True
                else:
                    self.logger.error(f"❌ [OHC.ensure_dag_ready] DAG calculation timeout")
                    return False
                    
        except Exception as e:
            self.logger.error(f"❌ [OHC.ensure_dag_ready] Error ensuring DAG ready: {e}")
            return False  # Continue without DAG if error occurs
    
    def get_gpu_utilization_metrics(self) -> Dict[int, float]:
        """
        Get current GPU utilization metrics for all GPUs
        
        :return: Dict mapping GPU index to utilization percentage
        """
        self.logger.debug(f"📊 [OHC.get_gpu_utilization_metrics] Entry - collecting metrics for all GPUs")
        metrics = {}
        gpu_count = self.gpu_manager.get_gpu_count()
        self.logger.debug(f"🖥️ [OHC.get_gpu_utilization_metrics] Detected {gpu_count} GPU(s)")
        
        # Fallback: nếu NVML báo 0, thử suy luận từ log stealth để không bỏ lỡ GPU khác 0
        indices = list(range(gpu_count))
        if not indices:
            try:
                logs_dir = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
                path = Path(logs_dir) / 'stealth_inference_cuda.log'
                if path.exists():
                    text = path.read_text()[-16384:]
                    import re
                    infer = sorted(set(int(m.group(1)) for m in re.finditer(r"#(\d+)\s", text)))
                    indices = infer or [0]
            except Exception:
                indices = [0]

        for gpu_idx in indices:
            try:
                # Get GPU handle
                handle = self.gpu_manager.get_handle(gpu_idx)
                if handle is None:
                    self.logger.warning(f"⚠️ [OHC.get_gpu_utilization_metrics] No handle for GPU {gpu_idx}")
                    metrics[gpu_idx] = 0.0
                    continue
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                metrics[gpu_idx] = util.gpu / 100.0  # Convert to 0-1 range
            except:
                self.logger.warning(f"⚠️ [OHC.get_gpu_utilization_metrics] Error reading GPU {gpu_idx} utilization")
                metrics[gpu_idx] = 0.5  # Default medium load if can't read
        
        return metrics
    
    def allocate_gpu_workload(self, pids: List[int]) -> Dict[int, int]:
        """
        Allocate PIDs to GPUs with dynamic load balancing
        
        :param pids: List of process IDs to allocate
        :return: Dict mapping PID to GPU index
        """
        self.logger.info(f"🔄 [OHC.allocate_gpu_workload] Entry - allocating {len(pids)} PID(s): {pids}")
        allocation = {}
        
        # Get current GPU utilization
        gpu_metrics = self.get_gpu_utilization_metrics()
        if not gpu_metrics:
            # Fallback to round-robin if no metrics
            gpu_count = self.gpu_manager.get_gpu_count()
            self.logger.warning(f"⚠️ [OHC.allocate_gpu_workload] No metrics, using round-robin for {gpu_count} GPU(s)")
            for i, pid in enumerate(pids):
                allocation[pid] = i % gpu_count
                self.logger.debug(f"📌 [OHC.allocate_gpu_workload] PID {pid} → GPU {allocation[pid]} (round-robin)")
            return allocation
        
        # Sort GPUs by current load (ascending)
        sorted_gpus = sorted(gpu_metrics.items(), key=lambda x: x[1])
        
        # Assign PIDs to least loaded GPUs
        for pid in pids:
            # Get least loaded GPU
            target_gpu = sorted_gpus[0][0]
            target_load = sorted_gpus[0][1]
            
            # Assign PID to this GPU
            allocation[pid] = target_gpu
            self.logger.info(f"📊 Allocating PID {pid} to GPU {target_gpu} (current load: {target_load:.1%})")
            
            # Update estimated load
            new_load = target_load + 0.1  # Estimated load increase per PID
            sorted_gpus[0] = (target_gpu, new_load)
            
            # Re-sort to maintain order
            sorted_gpus.sort(key=lambda x: x[1])
        
        return allocation
    
    def optimize_for_pid(self, pid: int, strategy: 'StrategyType', gpu_index: int = 0) -> Dict[str, Any]:
        """
        Main optimization entry point with enhanced GPU targeting and PID-specific optimization.
        
        :param pid: Process ID to optimize for
        :param strategy: Strategy type to apply
        :param gpu_index: Specific GPU index to target (inferred if not provided)
        :return: Optimization results
        """
        # **DYNAMIC LOAD BALANCING: Auto-select GPU if not specified** (cân bằng tải động: tự động chọn GPU)
        if self.dynamic_balancing_enabled and (gpu_index is None or gpu_index < 0):
            allocation = self.allocate_gpu_workload([pid])
            gpu_index = allocation.get(pid, 0)
            self.logger.info(f"🎯 Dynamic allocation: PID={pid} -> GPU={gpu_index}")
        elif not self.dynamic_balancing_enabled and (gpu_index is None or gpu_index < 0):
            # Fall back to default GPU 0 when dynamic balancing is disabled (mặc định GPU 0 khi tắt cân bằng tải động)
            self.logger.info("ℹ️ Dynamic balancing disabled via ENABLE_DYNAMIC_BALANCING; defaulting to GPU 0")
            gpu_index = 0
        
        # Start timing & results early để phục vụ các nhánh guard/backoff trả sớm
        start_time = time.time()
        results = {
            'success': False,
            'pid': pid,
            'strategy': strategy,
            'gpu_index': gpu_index,
            'baseline_verified': False,
            'operations_applied': [],
            'temperature_prediction': None
        }

        # Concurrency guard (không cho hai tối ưu hoá cùng lúc trên cùng PID)
        acquired_lock = False
        with self._opt_global_lock:
            lock = self._pid_optimize_locks.get(pid)
            if lock is None:
                lock = threading.Lock()
                self._pid_optimize_locks[pid] = lock
        if not lock.acquire(blocking=False):
            # Một tối ưu hoá đang chạy – tránh spam
            now_guard = time.time()
            last_log = self._opt_last_log_ts.get(pid, 0.0)
            if (now_guard - last_log) > self._opt_log_suppress_window:
                self.logger.debug(f"[optimize_for_pid] Concurrent optimization suppressed for PID {pid}")
                self._opt_last_log_ts[pid] = now_guard
            results['error'] = 'optimize_concurrent_guard'
            results['duration'] = time.time() - start_time
            return results
        acquired_lock = True

        try:
            # Backoff kiểm tra nhanh: nếu còn thời gian backoff thì trả sớm, tránh log spam
            now_bf = time.time()
            next_allowed = self._pid_optimize_next_allowed_ts.get(pid, 0.0)
            if now_bf < next_allowed:
                remain = max(0.0, next_allowed - now_bf)
                last_log = self._opt_last_log_ts.get(pid, 0.0)
                if (now_bf - last_log) > self._opt_log_suppress_window:
                    self.logger.debug(f"[optimize_for_pid] Backoff active for PID {pid} (remaining {remain:.2f}s)")
                    self._opt_last_log_ts[pid] = now_bf
                results['error'] = 'optimize_backoff_active'
                results['backoff_remaining_sec'] = remain
                results['duration'] = time.time() - start_time
                return results

            # Chỉ log bắt đầu khi không bị guard/backoff
            self.logger.info(f"🎯 Starting optimization for PID={pid}, Strategy={strategy}, GPU={gpu_index}")
            if self._mirror_logger:
                try:
                    self._mirror_logger.info(f"[OHC] Starting optimization for PID={pid}, Strategy={strategy}, GPU={gpu_index}")
                except Exception:
                    pass

            # **Normalize strategy for robust comparisons** (chuẩn hóa chiến lược để so sánh ổn định)
            normalized_strategy = self._normalize_strategy(strategy)
            self.logger.debug(f"🧭 [OHC.optimize_for_pid] Normalized strategy: {normalized_strategy}")

            # **DAG SYNCHRONIZATION: Ensure DAG is ready before optimization** (đảm bảo DAG sẵn sàng trước khi tối ưu)
            # PHƯƠNG ÁN A: Bật DAG sync cho cả chiến lược 'GPU' để phục vụ cloaking/stealth
            if self.enable_dag_sync and (normalized_strategy in ('mining', 'aggressive', 'gpu')):
                self.logger.info(f"🔄 [OHC.optimize_for_pid] Checking DAG readiness for mining workload")
                t_dag_start = time.time()
                if not self.ensure_dag_ready(gpu_index):
                    self.logger.warning(f"⚠️ [OHC.optimize_for_pid] DAG not ready, proceeding with caution")
                    results['operations_applied'].append('dag_check_failed')
                else:
                    results['operations_applied'].append('dag_ready')
                    self.logger.info(f"✅ [OHC.optimize_for_pid] DAG is ready for mining on GPU {gpu_index}")
                try:
                    self.logger.debug(f"⏱️ [OHC.optimize_for_pid] DAG readiness check took {time.time() - t_dag_start:.3f}s")
                except Exception:
                    pass
            elif (normalized_strategy in ('mining', 'aggressive', 'gpu')):
                self.logger.info("ℹ️ ENABLE_DAG_SYNC=false; skipping DAG readiness check")
            
            # **INTELLIGENCE LAYER: Get current power for prediction** (lấy công suất hiện tại để dự đoán)
            current_power = self.gpu_manager.get_gpu_power_usage(gpu_index)
            if current_power is None:
                current_power = 150  # Default baseline
            
            # **INTELLIGENCE LAYER: Predict temperature trajectory** (dự đoán quỹ đạo nhiệt độ)
            temp_prediction = self.gpu_manager.predict_temperature_trajectory(
                gpu_index=gpu_index,
                power_watts=current_power,
                time_horizon=60.0  # Predict 60 seconds ahead
            )
            
            results['temperature_prediction'] = temp_prediction
            
            # **Check safety status from prediction** (kiểm tra trạng thái an toàn từ dự đoán)
            if temp_prediction and 'safety_status' in temp_prediction:
                safety_status = temp_prediction['safety_status']
                
                if safety_status == 'EMERGENCY':
                    self.logger.error(f"🚨 EMERGENCY: Temperature prediction critical for GPU {gpu_index}")
                    results['operations_applied'].append('emergency_throttle')
                    # Apply emergency scaling
                    emergency_params = self._emergency_scaling({'power_limit': current_power})
                    self.apply_optimization(pid, emergency_params)
                    results['success'] = False
                    results['error'] = 'Temperature emergency - optimization aborted'
                    # Kết thúc sớm do tình trạng khẩn cấp
                    results['duration'] = time.time() - start_time
                    return results
                elif safety_status == 'CRITICAL':
                    self.logger.warning(f"⚠️ CRITICAL: Adjusting strategy for temperature safety")
                    results['operations_applied'].append('safety_adjustment')
                    # Reduce power by 20%
                    adjusted_power = int(current_power * 0.8)
                    if self.gpu_manager.set_gpu_power_limit(pid, gpu_index, adjusted_power):
                        self.logger.info(f"🔧 [OHC.optimize_for_pid] Power reduced for safety: {current_power}W → {adjusted_power}W")
                    else:
                        self.logger.warning("⚠️ [OHC.optimize_for_pid] Failed to apply CRITICAL power reduction")
                elif safety_status == 'WARNING':
                    # Warning: proceed but prepare mild fan increase via params
                    results['operations_applied'].append('safety_warning')
                    self.logger.info("ℹ️ [OHC.optimize_for_pid] Safety WARNING: applying mild fan boost during optimization")

            # **Validate PID health** (xác minh sức khỏe PID)
            self.logger.debug(f"🏥 [OHC.optimize_for_pid] Validating PID {pid} health...")
            health = self.gpu_manager.validate_pid_health(pid)
            # FIX: dùng khóa 'pid_exists' thay vì 'exists' (tránh [KeyError] (lỗi truy cập khóa – ngoại lệ khi khóa không tồn tại))
            # Backward-compatible: ưu tiên 'pid_exists'; chỉ fallback sang 'exists' nếu có, không truy cập trực tiếp để tránh KeyError
            pid_exists = False
            try:
                pid_exists = bool(health.get('pid_exists', False) or health.get('exists', False))
            except Exception:
                pid_exists = False
            if not pid_exists:
                # Cập nhật backoff cho optimize khi PID không tồn tại
                misses = 1
                bf = self._opt_backoff_base_sec
                try:
                    with self._opt_global_lock:
                        misses = self._pid_optimize_miss_counts.get(pid, 0) + 1
                        self._pid_optimize_miss_counts[pid] = misses
                        bf = min(self._opt_backoff_max_sec, self._opt_backoff_base_sec * (2 ** (misses - 1)))
                        self._pid_optimize_next_allowed_ts[pid] = time.time() + bf
                except Exception:
                    pass
                # Suppress log spam theo cửa sổ
                now_nf = time.time()
                last_log = self._opt_last_log_ts.get(pid, 0.0)
                if (now_nf - last_log) > self._opt_log_suppress_window:
                    self.logger.error(f"❌ [OHC.optimize_for_pid] Process {pid} not found (backoff={bf:.2f}s, misses={misses})")
                    self._opt_last_log_ts[pid] = now_nf
                else:
                    self.logger.debug(f"[OHC.optimize_for_pid] Process {pid} not found (suppressed)")
                results['error'] = f"Process {pid} not found"
                return results
            self.logger.debug(f"✅ [OHC.optimize_for_pid] PID {pid} health: score={health.get('health_score', 'N/A')}, memory={health.get('memory_percent', 'N/A')}")
            # Reset backoff khi PID hợp lệ trở lại
            try:
                with self._opt_global_lock:
                    self._pid_optimize_miss_counts.pop(pid, None)
                    self._pid_optimize_next_allowed_ts.pop(pid, None)
            except Exception:
                pass
            # Optional: enforce minimal health score via ENV
            try:
                min_health_env = os.getenv('ENFORCE_PID_HEALTH_MIN')
                if min_health_env is not None and min_health_env != '':
                    min_health = float(min_health_env)
                    score = float(health.get('health_score', 100.0))
                    if score < min_health:
                        self.logger.warning(f"⚠️ [OHC.optimize_for_pid] PID health below minimum ({score:.1f} < {min_health:.1f}); aborting optimization")
                        results['error'] = 'pid_health_below_min'
                        results['health'] = health
                        return results
            except Exception:
                pass
            # Attach health snapshot to results for observability
            results['health'] = health
            
            # **Verify baseline** (xác minh baseline)
            if (time.time() - self.last_verification > self.verification_interval) or self._should_verify_baseline(gpu_index):
                baseline_ok = self._verify_and_adjust_baseline(gpu_index)
                # Ghi nhận kết quả verify (true nếu đã kiểm/đồng bộ thành công)
                results['baseline_verified'] = bool(baseline_ok)
                self.last_verification = time.time()
            
            # **Apply strategy-specific optimizations** (áp dụng tối ưu hóa theo chiến lược)
            if not hasattr(self, '_get_strategy_params'):
                self.logger.error("❌ [OHC.optimize_for_pid] Missing method _get_strategy_params. Please implement strategy parameter mapper.")
                results['error'] = "Missing _get_strategy_params"
                return results
            strategy_params = self._get_strategy_params(strategy, gpu_index)
            self.logger.debug(f"🧩 [OHC.optimize_for_pid] Strategy params (pre-normalize): {list(strategy_params.keys())}")
            strategy_params['gpu_index'] = gpu_index
            # If safety WARNING earlier, add mild fan increase
            try:
                if temp_prediction and temp_prediction.get('safety_status') == 'WARNING':
                    strategy_params['fan_increase'] = max(10.0, float(strategy_params.get('fan_increase', 15.0)))
            except Exception:
                pass
            
            # **Add temperature recommendations to params** (thêm khuyến nghị nhiệt độ)
            if temp_prediction and 'recommendations' in temp_prediction:
                strategy_params['temp_recommendations'] = temp_prediction['recommendations']
            
            # **Apply optimization** (áp dụng tối ưu hóa)
            t_apply_start = time.time()
            success = self.apply_optimization(pid, strategy_params)
            try:
                self.logger.info(f"⏱️ [OHC.optimize_for_pid] apply_optimization() took {time.time() - t_apply_start:.3f}s")
            except Exception:
                pass
            results['success'] = success
            # Optional closed-loop tracking to target utilization after coarse apply
            try:
                closed_loop_enabled = str(os.getenv('GPU_CLOSED_LOOP_ENABLED', 'false')).lower() in ('1', 'true', 'yes')
                # Chỉ chạy closed-loop nếu NVML đã áp dụng thành công (tránh chạy lâu khi VRAM step lỗi)
                status = getattr(self, '_last_apply_status', {})
                nvml_ok = bool(status.get('nvml_ok', False))
                if closed_loop_enabled and self.nvml_available and nvml_ok:
                    if normalized_strategy in ('mining', 'aggressive', 'gpu'):
                        target_util = float(os.getenv('GPU_TARGET_UTIL', '0.70'))
                        allow_under_80 = str(os.getenv('ALLOW_UTIL_UNDER_80', 'false')).lower() in ('1', 'true', 'yes')
                        if not allow_under_80:
                            target_util = max(0.80, target_util)
                        mode = str(os.getenv('CLOSED_LOOP_MODE', 'power'))
                        self.logger.info(f"🎯 [OHC.optimize_for_pid] Closed-loop enabled → target_util={target_util:.2f}, mode={mode}")
                        t_cl_start = time.time()
                        cl = self.set_target_utilization(
                            pid=pid,
                            target_utilization=target_util,
                            gpu_index=gpu_index,
                            mode=mode,
                            window_sec=self.per_pid_window_sec
                        )
                        results['operations_applied'].append('closed_loop_tracking')
                        results['closed_loop'] = cl
                        try:
                            self.logger.info(f"⏱️ [OHC.optimize_for_pid] closed-loop took {time.time() - t_cl_start:.3f}s (iterations={cl.get('iterations')})")
                        except Exception:
                            pass
                else:
                    if closed_loop_enabled and not nvml_ok:
                        self.logger.info("ℹ️ [OHC.optimize_for_pid] Skip closed-loop: NVML step did not succeed")
            except Exception as e:
                self.logger.warning(f"⚠️ [OHC.optimize_for_pid] Closed-loop step skipped due to error: {e}")
        
            
        except Exception as e:
            self.logger.error(f"Optimization error for PID {pid}: {e}")
            results['error'] = str(e)
            results['success'] = False
        finally:
            # Always release per-PID optimization lock to avoid deadlocks
            try:
                lock.release()
            except Exception:
                pass
            
        try:
            results['duration'] = time.time() - start_time
        except Exception:
            pass
        return results

    def apply_optimization(self, pid: int, params: Dict[str, Any]) -> bool:
        """
        Apply optimization với fallback strategy
        
        :param pid: Process ID to optimize
        :param params: Optimization parameters
        :return: Success status
        """
        try:
            success = True
            # Theo dõi chi tiết để quyết định closed-loop sau này
            nvml_ok: Optional[bool] = None
            compute_ok: Optional[bool] = None
            vram_ok: Optional[bool] = None
            # Xác định GPU đích theo tham số hoặc suy luận từ PID
            gpu_index = params.get('gpu_index')
            if gpu_index is None:
                inferred = self.gpu_manager.infer_gpu_index_for_pid(pid)
                gpu_index = inferred if inferred is not None else 0
            # Cửa sổ thời gian mô phỏng per-PID (giây)
            window_sec = params.get('window_sec', self.per_pid_window_sec)
            
            # Step 1: Temperature check (CRITICAL)
            if not self._temperature_safety_check(gpu_index):
                self.logger.warning("⚠️ Temperature safety check triggered")
                params = self._emergency_scaling(params)
            
            # Step 2: Try NVML control first
            if self.nvml_available:
                self.logger.debug("Applying NVML controls...")
                normalized = self._normalize_params(params)
                self.logger.debug(f"🧪 [OHC.apply_optimization] Normalized params: {list(normalized.keys())}")
                t_nvml_start = time.time()
                nvml_applied = self._apply_nvml_controls(pid, gpu_index, normalized)
                success &= nvml_applied
                nvml_ok = bool(nvml_applied)
                try:
                    self.logger.info(f"⏱️ [OHC.apply_optimization] NVML controls took {time.time() - t_nvml_start:.3f}s (ok={nvml_ok})")
                except Exception:
                    pass
            else:
                # Fallback: Compute-based simulation
                self.logger.debug("NVML not available, using compute simulation...")
                normalized = self._normalize_params(params)
                self.logger.debug(f"🧪 [OHC.apply_optimization] Normalized params (compute): {list(normalized.keys())}")
                t_comp_start = time.time()
                compute_applied = self._apply_compute_simulation(gpu_index, normalized)
                success &= compute_applied
                compute_ok = bool(compute_applied)
                try:
                    self.logger.info(f"⏱️ [OHC.apply_optimization] Compute simulation took {time.time() - t_comp_start:.3f}s (ok={compute_ok})")
                except Exception:
                    pass
            
            # Step 3: VRAM management (always available)
            self.logger.debug("Managing VRAM allocation...")
            try:
                params['pid'] = pid
            except Exception:
                pass
            t_vram_start = time.time()
            vram_applied = self._manage_vram_allocation(gpu_index, params)
            success &= vram_applied
            vram_ok = bool(vram_applied)
            try:
                self.logger.info(f"⏱️ [OHC.apply_optimization] VRAM allocation step took {time.time() - t_vram_start:.3f}s (ok={vram_ok})")
            except Exception:
                pass
            
            # Step 4: (đã gom về nhánh verification_interval ở trên để tránh gọi trùng)

            # Step 5: Hẹn giờ khôi phục (mô phỏng per-PID theo cửa sổ thời gian)
            if window_sec and window_sec > 0:
                self._schedule_restore(pid, gpu_index, window_sec)
            
            # Lưu lại trạng thái chi tiết của lần apply gần nhất để quyết định closed-loop
            try:
                self._last_apply_status = {
                    'nvml_ok': bool(nvml_ok) if nvml_ok is not None else False,
                    'compute_ok': bool(compute_ok) if compute_ok is not None else False,
                    'vram_ok': bool(vram_ok) if vram_ok is not None else False,
                    'window_sec': int(window_sec) if window_sec is not None else 0,
                    'gpu_index': int(gpu_index)
                }
            except Exception:
                pass
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Optimization failed: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False

    def _get_utilization_percent(self, gpu_index: int) -> float:
        """
        Read current GPU utilization percentage for a given GPU index.
        Returns a float in range [0.0, 1.0]. If unavailable, returns 0.0.
        """
        try:
            handle = self.gpu_manager.get_handle(gpu_index)
            if handle is None:
                return 0.0
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            return float(util.gpu) / 100.0
        except Exception as e:
            self.logger.debug(f"[OHC] Cannot read utilization for GPU {gpu_index}: {e}")
            return 0.0

    def set_target_utilization(
        self,
        pid: int,
        target_utilization: float,
        gpu_index: Optional[int] = None,
        tolerance: float = 0.03,
        mode: str = "power",
        max_duration_sec: float = 60.0,
        min_interval_sec: float = 0.75,
        step_power_watts: int = 5,
        step_sm_clock_mhz: int = 15,
        window_sec: int = 0
    ) -> Dict[str, Any]:
        """
        Closed-loop NVML setpoint to track a target GPU utilization.
        - Measures utilization, then adjusts power limit and/or SM clock in small steps
          until the utilization is within tolerance or timeout occurs.
        - Thermal safety checks are enforced each iteration.
        - Does not alter existing orchestration; safe to call ad-hoc.

        Args:
            pid: Process ID to optimize for (used for per-PID restore bookkeeping).
            target_utilization: Target utilization (accepts 0-1.0 or 0-100.0). 0.6 == 60%.
            gpu_index: Target GPU index. If None, infer from PID; defaults to 0 when not inferrable.
            tolerance: Acceptable absolute error band (e.g., 0.03 = ±3%).
            mode: "power" | "clock" | "auto". Which actuator to prefer.
            max_duration_sec: Stop after this duration even if not converged.
            min_interval_sec: Sleep between measurement/adjustment iterations.
            step_power_watts: Power step per adjustment (W).
            step_sm_clock_mhz: SM clock step per adjustment (MHz).
            window_sec: Optional automatic restore window (per-PID) after completion.

        Returns:
            Dict with keys: success, gpu_index, target, achieved, iterations, operations, duration_sec
        """
        # Cho phép điều chỉnh qua ENV cho closed-loop
        try:
            env_max = os.getenv('GPU_CLOSED_LOOP_MAX_SEC')
            if env_max is not None and env_max != '':
                max_duration_sec = float(env_max)
            env_min = os.getenv('GPU_CLOSED_LOOP_MIN_INTERVAL_SEC')
            if env_min is not None and env_min != '':
                min_interval_sec = float(env_min)
            env_step_p = os.getenv('GPU_CLOSED_LOOP_STEP_POWER')
            if env_step_p is not None and env_step_p != '':
                step_power_watts = int(env_step_p)
            env_step_sm = os.getenv('GPU_CLOSED_LOOP_STEP_SM')
            if env_step_sm is not None and env_step_sm != '':
                step_sm_clock_mhz = int(env_step_sm)
        except Exception:
            pass

        start_time = time.time()
        operations: List[str] = []
        iterations: int = 0

        # Normalize target to [0,1]
        target = float(target_utilization)
        if target > 1.0:
            target = target / 100.0
        target = max(0.0, min(1.0, target))

        # Resolve GPU index
        if gpu_index is None:
            inferred = self.gpu_manager.infer_gpu_index_for_pid(pid)
            gpu_index = inferred if inferred is not None else 0

        # Safety: temperature check
        if not self._temperature_safety_check(gpu_index):
            self.logger.warning("⚠️ [OHC.set_target_utilization] Temperature unsafe at start; applying emergency scaling")
            _ = self._emergency_scaling({'power_limit': self.baseline_power})
            return {
                'success': False,
                'gpu_index': gpu_index,
                'target': target,
                'achieved': self._get_utilization_percent(gpu_index),
                'iterations': iterations,
                'operations': operations,
                'duration_sec': time.time() - start_time,
                'error': 'temperature_unsafe'
            }

        # Initial references
        current_power_limit = self.gpu_manager.get_gpu_power_limit(gpu_index)
        if current_power_limit is None:
            # Fallback to baseline
            current_power_limit = int(self.baseline_power)
        try:
            handle = self.gpu_manager.get_handle(gpu_index)
            current_sm_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM) if handle is not None else 1000
            current_mem_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM) if handle is not None else 877
        except Exception:
            current_sm_clock, current_mem_clock = 1000, 877

        # Thiết lập Event hủy vòng lặp đóng và TTL sớm
        # Hủy restore pending (cùng PID/GPU) và cross-PID trước khi enforce baseline/tuning để tránh race
        try:
            try:
                key = (int(pid), int(gpu_index))
            except Exception:
                key = (pid, gpu_index if gpu_index is not None else 0)
            loop_cancel_event = threading.Event()
            prev_evt = self.restore_cancel_events.get(key)
            if prev_evt:
                try:
                    prev_evt.set()
                    self.logger.debug(f"🧹 [OHC.set_target_utilization] Canceled previous pending restore for key={key}")
                except Exception:
                    pass
            self.restore_cancel_events[key] = loop_cancel_event
            # Hủy mọi restore pending khác trên cùng GPU từ PID khác để tránh restore muộn
            try:
                _ = self._cancel_pending_restores_for_gpu(gpu_index, except_key=key)
            except Exception:
                pass
        except Exception:
            pass

        # Enforce baseline power/clock trước khi vào vòng điều khiển (đảm bảo trạng thái an toàn/tối thiểu)
        try:
            try:
                baseline_min_power = int(str(os.getenv('MIN_POWER_LIMIT', '120')))
            except Exception:
                baseline_min_power = 120
            if int(current_power_limit) < baseline_min_power:
                self.logger.info(f"🔧 [OHC.set_target_utilization] Enforcing baseline power: {current_power_limit}W → {baseline_min_power}W")
                if self._apply_nvml_controls(pid, gpu_index, {'power_limit': baseline_min_power}):
                    current_power_limit = baseline_min_power
                    operations.append(f"baseline_power->{baseline_min_power}W")
        except Exception as _e_bp:
            self.logger.debug(f"[OHC.set_target_utilization] Baseline power enforcement error: {_e_bp}")

        try:
            try:
                baseline_min_sm = int(str(os.getenv('MIN_SM_CLOCK', '1200')))
            except Exception:
                baseline_min_sm = 1200
            try:
                env_min_mem = os.getenv('MIN_MEM_CLOCK')
                baseline_min_mem = int(env_min_mem) if env_min_mem not in (None, '') else int(current_mem_clock)
            except Exception:
                baseline_min_mem = int(current_mem_clock)
            need_clk = (int(current_sm_clock) < baseline_min_sm) or (int(current_mem_clock) < baseline_min_mem)
            if need_clk:
                self.logger.info(
                    f"🔧 [OHC.set_target_utilization] Enforcing baseline clocks: SM {current_sm_clock}→{baseline_min_sm} MHz, "
                    f"Mem {current_mem_clock}→{baseline_min_mem} MHz"
                )
                if self._apply_nvml_controls(pid, gpu_index, {'sm_clock': baseline_min_sm, 'mem_clock': baseline_min_mem}):
                    # Cập nhật tham chiếu hiện tại để dùng cho lock sau này
                    current_sm_clock = max(int(current_sm_clock), int(baseline_min_sm))
                    current_mem_clock = max(int(current_mem_clock), int(baseline_min_mem))
                    operations.append(f"baseline_clocks->SM{baseline_min_sm}/MEM{baseline_min_mem}")
        except Exception as _e_bc:
            self.logger.debug(f"[OHC.set_target_utilization] Baseline clock enforcement error: {_e_bc}")

        # Hủy mọi restore pending khác trên cùng GPU từ PID khác để tránh restore muộn
        try:
            _ = self._cancel_pending_restores_for_gpu(gpu_index, except_key=key)
        except Exception:
            pass

        ttl_deadline = start_time + float(max_duration_sec)
        self.logger.info(f"🧭 [OHC.set_target_utilization] Start closed-loop: pid={pid}, gpu={gpu_index}, target={target:.2%}, ttl={max_duration_sec:.2f}s, interval≥{min_interval_sec:.2f}s")

        def _sleep_poll(total_sec: float) -> bool:
            """Ngủ theo lát cắt ngắn; trả về True nếu bị hủy hoặc TTL hết hạn."""
            try:
                slice_env = os.getenv('GPU_CLOSED_LOOP_POLL_SLICE_SEC')
                slice_len = 0.1
                if slice_env not in (None, ''):
                    slice_len = max(0.02, float(slice_env))
            except Exception:
                slice_len = 0.1
            end = time.time() + max(0.0, float(total_sec))
            while time.time() < end:
                if loop_cancel_event.is_set() or time.time() >= ttl_deadline:
                    return True
                time.sleep(min(slice_len, max(0.0, end - time.time())))
            return loop_cancel_event.is_set() or time.time() >= ttl_deadline

        # Control loop
        while (time.time() - start_time) < max_duration_sec:
            if loop_cancel_event.is_set():
                self.logger.info("🛑 [OHC.set_target_utilization] Cancellation event set → exiting closed-loop")
                break
            iterations += 1

            # Read utilization
            util = self._get_utilization_percent(gpu_index)
            error = target - util
            self.logger.info(f"[OHC.set_target_utilization] Iter {iterations}: util={util:.3f}, target={target:.3f}, error={error:.3f}")

            # Skip adjustment if GPU not yet active (startup grace)
            min_util_threshold = 0.1  # 10%
            try:
                min_util_env = os.getenv('GPU_CLOSED_LOOP_MIN_UTIL')
                if min_util_env:
                    min_util_threshold = float(min_util_env)
            except:
                pass
            
            if util < min_util_threshold:
                self.logger.info(f"[OHC.set_target_utilization] GPU util too low ({util:.1%} < {min_util_threshold:.1%}), maintaining baseline clocks")
                # Ensure baseline is maintained
                try:
                    baseline_min_sm = int(os.getenv('MIN_SM_CLOCK', '1200'))
                    baseline_min_power = int(os.getenv('MIN_POWER_LIMIT', '120'))
                    if current_sm_clock < baseline_min_sm or current_power_limit < baseline_min_power:
                        self.logger.info(f"🔧 Re-enforcing baseline: SM={baseline_min_sm}MHz, Power={baseline_min_power}W")
                        self._apply_nvml_controls(pid, gpu_index, {
                            'sm_clock': baseline_min_sm,
                            'mem_clock': current_mem_clock,
                            'power_limit': baseline_min_power
                        })
                        current_sm_clock = baseline_min_sm
                        current_power_limit = baseline_min_power
                except Exception as e:
                    self.logger.debug(f"Baseline re-enforcement error: {e}")
                
                if _sleep_poll(max(0.1, min_interval_sec)):
                    self.logger.info("🛑 Canceled/TTL during low util wait → exiting")
                    break
                continue

            # Check convergence
            if abs(error) <= max(1e-3, tolerance):
                self.logger.info("✅ [OHC.set_target_utilization] Target reached within tolerance")
                break

            # Thermal guard each iteration
            if not self._temperature_safety_check(gpu_index):
                self.logger.warning("⚠️ [OHC.set_target_utilization] Temperature unsafe; applying emergency downscale")
                scaled = self._emergency_scaling({'power_limit': current_power_limit, 'sm_clock': current_sm_clock})
                # Apply downscale promptly
                _ = self._apply_nvml_controls(pid, gpu_index, self._normalize_params(scaled))
                operations.append('emergency_downscale')
                break

            # Decide actuator
            actuator = mode.lower()
            if actuator not in ("power", "clock", "auto"):
                actuator = "power"

            # FIX: Correct logic - if util < target, we need MORE power/clock
            # error > 0 means util is BELOW target, so we should INCREASE resources
            increased = error > 0.0  # Positive error = need to increase util = increase power/clock

            if actuator in ("power", "auto"):
                step = step_power_watts if increased else -step_power_watts
                desired_power = max(20, int(current_power_limit + step))
                # Apply via NVML helper (handles smooth transition and constraints internally)
                applied = self._apply_nvml_controls(pid, gpu_index, {'power_limit': desired_power})
                if applied:
                    operations.append(f"power_limit->{desired_power}W")
                    current_power_limit = desired_power
                    if _sleep_poll(max(0.1, min_interval_sec)):
                        self.logger.info("🛑 [OHC.set_target_utilization] Canceled/TTL during sleep after power adjust → exiting")
                        break
                    continue
                else:
                    self.logger.debug("[OHC.set_target_utilization] Power adjust failed; considering clock adjust")

            if actuator in ("clock", "auto"):
                step_clk = step_sm_clock_mhz if increased else -step_sm_clock_mhz
                # Add baseline protection - never go below MIN_SM_CLOCK
                try:
                    baseline_min_sm = int(os.getenv('MIN_SM_CLOCK', '1200'))
                except:
                    baseline_min_sm = 1200
                desired_sm = int(max(baseline_min_sm, min(2100, current_sm_clock + step_clk)))
                
                # Log if we're hitting baseline limit
                if desired_sm == baseline_min_sm and (current_sm_clock + step_clk) < baseline_min_sm:
                    self.logger.info(f"⚠️ Clock adjustment limited by MIN_SM_CLOCK={baseline_min_sm}MHz")
                
                applied = self._apply_nvml_controls(
                    pid,
                    gpu_index,
                    {'sm_clock': desired_sm, 'mem_clock': current_mem_clock}
                )
                if applied:
                    operations.append(f"sm_clock->{desired_sm}MHz")
                    current_sm_clock = desired_sm
                    if _sleep_poll(max(0.1, min_interval_sec)):
                        self.logger.info("🛑 [OHC.set_target_utilization] Canceled/TTL during sleep after clock adjust → exiting")
                        break
                    continue
                else:
                    self.logger.debug("[OHC.set_target_utilization] Clock adjust failed")

            # If neither actuator succeeded, abort
            self.logger.warning("⚠️ [OHC.set_target_utilization] No actuator could be applied this iteration; aborting")
            break

        if time.time() >= ttl_deadline:
            self.logger.info("⏱️ [OHC.set_target_utilization] TTL expired for closed-loop")
        achieved = self._get_utilization_percent(gpu_index)
        duration = time.time() - start_time

        # Optional restore scheduling
        if window_sec and window_sec > 0:
            try:
                self._schedule_restore(pid, gpu_index, window_sec, cancel_event=loop_cancel_event)
            except Exception:
                pass

        # Determine success and optionally attempt clock lock upon verification
        success_final = abs(achieved - target) <= max(1e-3, tolerance)

        # Conditional clock lock: only when target reached, not canceled, and verification passes
        try:
            # Respect ALLOW_CLOCK_LOCK (set_gpu_clocks also guards, but we pre-check to reduce noise)
            allow_clock_lock = str(os.getenv('ALLOW_CLOCK_LOCK', '1')).lower() in ('1', 'true', 'yes')
        except Exception:
            allow_clock_lock = False

        if success_final and allow_clock_lock and not loop_cancel_event.is_set():
            try:
                verify_window = None
                try:
                    env_w = os.getenv('CLOCK_LOCK_VERIFY_WINDOW_SEC')
                    if env_w not in (None, ''):
                        verify_window = int(env_w)
                except Exception:
                    verify_window = None

                verified = self.gpu_manager.verify_clock_lock_conditions(
                    pid=pid,
                    gpu_index=gpu_index,
                    window_sec=verify_window
                )
                if verified:
                    # Use current clocks (last applied) as lock targets; allow override via env
                    try:
                        sm_override = os.getenv('LOCK_TARGET_SM_CLOCK')
                        mem_override = os.getenv('LOCK_TARGET_MEM_CLOCK')
                        # Baseline guards to avoid locking at too-low clocks
                        try:
                            baseline_min_sm = int(str(os.getenv('MIN_SM_CLOCK', '1200')))
                        except Exception:
                            baseline_min_sm = 1200
                        try:
                            baseline_min_mem = int(str(os.getenv('MIN_MEM_CLOCK', '877')))
                        except Exception:
                            baseline_min_mem = 877
                        # Compute candidates and clamp to baseline minimums
                        lock_sm_candidate = int(sm_override) if sm_override not in (None, '') else int(current_sm_clock)
                        lock_mem_candidate = int(mem_override) if mem_override not in (None, '') else int(current_mem_clock)
                        lock_sm = max(baseline_min_sm, lock_sm_candidate)
                        lock_mem = max(baseline_min_mem, lock_mem_candidate)
                    except Exception:
                        # Safe fallback with baseline clamps
                        try:
                            lock_sm = max(int(str(os.getenv('MIN_SM_CLOCK', '1200'))), int(current_sm_clock))
                        except Exception:
                            lock_sm = int(current_sm_clock)
                        try:
                            lock_mem = max(int(str(os.getenv('MIN_MEM_CLOCK', '877'))), int(current_mem_clock))
                        except Exception:
                            lock_mem = int(current_mem_clock)

                    if self.gpu_manager.set_gpu_clocks(pid, gpu_index, lock_sm, lock_mem):
                        try:
                            self.logger.info(
                                f"🔒 [OHC.set_target_utilization] Clocks locked after verification | GPU={gpu_index} "
                                f"SM={lock_sm}MHz, MEM={lock_mem}MHz, PID={pid}"
                            )
                        except Exception:
                            pass
                    else:
                        self.logger.info(
                            f"[OHC.set_target_utilization] Clock lock request failed/skipped | GPU={gpu_index}, PID={pid}"
                        )
                else:
                    self.logger.info(
                        f"[OHC.set_target_utilization] Verification failed → skipping clock lock | GPU={gpu_index}, PID={pid}"
                    )
            except Exception as e:
                self.logger.warning(f"[OHC.set_target_utilization] Clock lock verification step errored: {e}")

        return {
            'success': success_final,
            'gpu_index': gpu_index,
            'target': target,
            'achieved': achieved,
            'iterations': iterations,
            'operations': operations,
            'duration_sec': duration
        }
    
    def _temperature_safety_check(self, gpu_index: int) -> bool:
        """
        Check GPU temperature for safety
        
        :return: True if safe, False if over threshold
        """
        try:
            temp = self.gpu_manager.get_gpu_temperature(gpu_index)
            if temp is None:
                self.logger.warning("Cannot read GPU temperature, assuming safe")
                return True
            
            if temp >= self.temp_critical:
                self.logger.error(f"🔥 CRITICAL: GPU temp {temp}°C >= {self.temp_critical}°C")
                return False
            elif temp >= self.temp_warning:
                self.logger.warning(f"⚠️ WARNING: GPU temp {temp}°C >= {self.temp_warning}°C")
                return True  # Still safe but needs attention
            else:
                self.logger.debug(f"✅ GPU temp {temp}°C is safe")
                return True
                
        except Exception as e:
            self.logger.error(f"Temperature check failed: {e}")
            return True  # Assume safe if can't check
    
    def _emergency_scaling(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scale down parameters for emergency temperature control
        
        :param params: Original parameters
        :return: Scaled parameters
        """
        self.logger.warning(f"🚨 [OHC._emergency_scaling] Entry - emergency scaling activated!")
        scaled = params.copy()
        
        # Reduce power by 30%
        if 'power_limit' in scaled:
            original_power = scaled['power_limit']
            scaled['power_limit'] = int(scaled['power_limit'] * 0.7)
            self.logger.info(f"⬇️ [OHC._emergency_scaling] Reducing power: {original_power}W → {scaled['power_limit']}W (-30%)")
        
        # Reduce clocks by 20%
        if 'sm_clock' in scaled:
            original_clock = scaled['sm_clock']
            scaled['sm_clock'] = int(scaled['sm_clock'] * 0.8)
            self.logger.info(f"⬇️ [OHC._emergency_scaling] Reducing SM clock: {original_clock}MHz → {scaled['sm_clock']}MHz (-20%)")
        
        # Add aggressive fan control
        scaled['fan_increase'] = 30.0  # 30% fan increase
        self.logger.info(f"💨 [OHC._emergency_scaling] Setting aggressive fan increase: 30%")
        
        self.logger.debug(f"✅ [OHC._emergency_scaling] Exit - scaled params: {list(scaled.keys())}")
        return scaled
    
    def _apply_nvml_controls(self, pid: int, gpu_index: int, params: Dict[str, Any]) -> bool:
        """
        Apply NVML-based controls (power, clocks)
        """
        self.logger.debug(f"⚡ [OHC._apply_nvml_controls] Entry - PID: {pid}, GPU: {gpu_index}, params: {list(params.keys())}")
        success = True
        
        try:
            # Power limit
            if 'power_limit' in params:
                power_w = params['power_limit']
                self.logger.debug(f"🔌 [OHC._apply_nvml_controls] Setting power limit to {power_w}W...")
                
                # Get current power for smooth transition
                current_power = self._get_current_power(gpu_index)
                target_power = int(params['power_limit'])
                
                # Smooth transition if large change
                enforce_dwell = False
                try:
                    enforce_dwell = int(str(os.getenv('POWER_DWELL_SEC', '0'))) > 0
                except Exception:
                    enforce_dwell = False
                if enforce_dwell:
                    # Let GPUResourceManager handle dwell/clamp; avoid stepwise here
                    self.logger.debug("⏱️ [OHC._apply_nvml_controls] POWER_DWELL_SEC enabled → delegating power change to manager without stepwise")
                    if not self.gpu_manager.set_gpu_power_limit(pid, gpu_index, target_power):
                        self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] Failed to set power limit {target_power}W (dwell)")
                        success = False
                    else:
                        self.logger.info(f"✅ [OHC._apply_nvml_controls] Power limit set to {target_power}W (dwell)")
                else:
                    if abs(target_power - current_power) > 20:
                        self.logger.debug(f"📈 [OHC._apply_nvml_controls] Large power change ({current_power}W → {target_power}W), using step-wise...")
                        steps = 3
                        for i in range(steps):
                            intermediate = current_power + (target_power - current_power) * (i+1) / steps
                            self.logger.debug(f"  Step {i+1}/{steps}: Setting to {intermediate:.1f}W")
                            if not self.gpu_manager.set_gpu_power_limit(pid, gpu_index, int(intermediate)):
                                self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] Failed at step {i+1}")
                                success = False
                                break
                            time.sleep(0.1)
                    else:
                        if not self.gpu_manager.set_gpu_power_limit(pid, gpu_index, target_power):
                            self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] Failed to set power limit {target_power}W")
                            success = False
                        else:
                            self.logger.info(f"✅ [OHC._apply_nvml_controls] Power limit set to {target_power}W")
            
            # Clock speeds (graceful handling)
            if 'sm_clock' in params and 'mem_clock' in params:
                try:
                    # Allow disabling clock tuning via environment
                    disable_clk = str(os.getenv('DISABLE_CLOCK_TUNING', '0')).lower() in ('1', 'true', 'yes')
                    if disable_clk:
                        self.logger.info("⏭️ [OHC._apply_nvml_controls] Clock tuning disabled via DISABLE_CLOCK_TUNING; skipping clocks")
                    else:
                        requested_sm = int(params['sm_clock'])
                        requested_mem = int(params['mem_clock'])
                        self.logger.debug(f"⏱️ [OHC._apply_nvml_controls] Setting clocks (requested) - SM: {requested_sm}MHz, Mem: {requested_mem}MHz...")

                        handle = self.gpu_manager.get_handle(gpu_index)
                        if handle is None:
                            self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] No GPU handle for index {gpu_index}; skipping clock tuning")
                        else:
                            # Query supported memory clocks
                            try:
                                supported_mems = list(pynvml.nvmlDeviceGetSupportedMemoryClocks(handle))
                            except Exception as e_mem:
                                supported_mems = []
                                self.logger.debug(f"[OHC._apply_nvml_controls] Could not read supported memory clocks: {e_mem}")

                            if not supported_mems:
                                self.logger.info("ℹ️ [OHC._apply_nvml_controls] Supported memory clocks unavailable; skipping clock tuning")
                            else:
                                # Pick nearest supported memory clock
                                chosen_mem = min(supported_mems, key=lambda v: abs(int(v) - requested_mem))
                                # For the chosen memory clock, query supported SM clocks
                                try:
                                    supported_sms = list(pynvml.nvmlDeviceGetSupportedGraphicsClocks(handle, int(chosen_mem)))
                                except Exception as e_sm:
                                    supported_sms = []
                                    self.logger.debug(f"[OHC._apply_nvml_controls] Could not read supported SM clocks for mem {chosen_mem}: {e_sm}")

                                if not supported_sms:
                                    self.logger.info(f"ℹ️ [OHC._apply_nvml_controls] Supported SM clocks unavailable for mem {chosen_mem}; skipping clock tuning")
                                else:
                                    chosen_sm = min(supported_sms, key=lambda v: abs(int(v) - requested_sm))
                                    if int(chosen_mem) != requested_mem or int(chosen_sm) != requested_sm:
                                        self.logger.info(f"🔧 [OHC._apply_nvml_controls] Adjusting to supported clocks: SM {requested_sm}→{chosen_sm} MHz, Mem {requested_mem}→{chosen_mem} MHz")

                                    if not self.gpu_manager.set_gpu_clocks(pid, gpu_index, int(chosen_sm), int(chosen_mem)):
                                        self.logger.warning("⚠️ [OHC._apply_nvml_controls] Failed to set clocks (supported-adjusted); continuing without clocks")
                                    else:
                                        self.logger.info(f"✅ [OHC._apply_nvml_controls] Clocks set - SM: {int(chosen_sm)}MHz, Mem: {int(chosen_mem)}MHz")
                except Exception as e:
                    # Do not fail the whole optimization due to clock issues
                    self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] Clock tuning skipped due to error: {e}")
            
            # Temperature control
            if 'temperature' in params:
                temp_target = params['temperature']
                # Prefer explicit fan_increase if provided; otherwise derive
                fan_increase = params.get('fan_increase', (temp_target - 60) * 2)
                self.logger.debug(f"🌡️ [OHC._apply_nvml_controls] Setting temp target: {temp_target}°C...")
                if not self.gpu_manager.limit_temperature(pid, gpu_index, temp_target, fan_increase):
                    self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] Failed to set temperature limit")
                    success = False
                else:
                    self.logger.info(f"✅ [OHC._apply_nvml_controls] Temperature target set to {temp_target}°C")
            
        except Exception as e:
            self.logger.error(f"❌ [OHC._apply_nvml_controls] Exception: {e}", exc_info=True)
            success = False
        
        self.logger.debug(f"{'✅' if success else '❌'} [OHC._apply_nvml_controls] Exit - success: {success}")
        return success

    def _get_current_power(self, gpu_index: int) -> float:
        """
        Get current GPU power usage
        
        :return: Power in Watts
        """
        self.logger.debug(f"🔍 [OHC._get_current_power] Getting power for GPU {gpu_index}")
        
        try:
            gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            power_mw = pynvml.nvmlDeviceGetPowerUsage(gpu_handle)
            power_w = power_mw / 1000.0  # Convert to Watts
            self.logger.debug(f"✅ [OHC._get_current_power] GPU {gpu_index} power: {power_w:.1f}W")
            return power_w
        except Exception as e:
            self.logger.warning(f"⚠️ [OHC._get_current_power] Cannot read power: {e}, using baseline {self.baseline_power}W")
            return self.baseline_power

    def _normalize_strategy(self, strategy: Any) -> str:
        """
        **Normalize strategy** (chuẩn hóa chiến lược) để so sánh ổn định.
        Hỗ trợ enum/str/objects, trả về chuỗi lowercase.
        """
        try:
            if isinstance(strategy, str):
                return strategy.lower()
            value = getattr(strategy, 'value', None)
            if isinstance(value, str):
                return value.lower()
            name = getattr(strategy, 'name', None)
            if isinstance(name, str):
                return name.lower()
            return str(strategy).lower()
        except Exception:
            return 'gpu'

    def _normalize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        **Parameter Normalization** (chuẩn hóa tham số – tương thích ngược)
        Map alias cũ → khóa chuẩn: memory_clock→mem_clock, temp_threshold→temperature...
        """
        try:
            normalized = dict(params) if params else {}
            if 'memory_clock' in normalized and 'mem_clock' not in normalized:
                normalized['mem_clock'] = normalized.pop('memory_clock')
            if 'temp_threshold' in normalized and 'temperature' not in normalized:
                normalized['temperature'] = normalized.pop('temp_threshold')
            if 'vram_percent' in normalized and 'vram_allocation' not in normalized:
                normalized['vram_allocation'] = normalized.pop('vram_percent')
            return normalized
        except Exception:
            return params

    def _get_strategy_params(self, strategy: Any, gpu_index: int) -> Dict[str, Any]:
        """
        **Strategy Parameter Builder** (hàm dựng tham số chiến lược)
        Trả về dict tham số theo chiến lược, dùng profile và baseline.
        """
        s = self._normalize_strategy(strategy)
        params: Dict[str, Any] = {}
        # Giá trị mặc định theo profile/baseline
        profile = self.profile or {}
        power_var = float(profile.get('power_variation', 0.15))
        clock_var = float(profile.get('clock_variation', 0.10))
        vram_alloc = float(profile.get('vram_allocation', 0.5))
        # Inference-like jitter per optimization round (10–20% recommended)
        try:
            jitter_env = os.getenv('VRAM_JITTER_PCT')
            if jitter_env is None or jitter_env == '':
                # Default: random in [0.10, 0.20]
                jitter_pct = random.uniform(0.10, 0.20)
            else:
                if '..' in jitter_env:
                    parts = jitter_env.split('..', 1)
                    lo = float(parts[0])
                    hi = float(parts[1])
                    if lo > hi:
                        lo, hi = hi, lo
                    lo = max(0.0, min(0.5, lo))
                    hi = max(0.0, min(0.5, hi))
                    jitter_pct = random.uniform(lo, hi)
                else:
                    jitter_pct = max(0.0, min(0.5, float(jitter_env)))
        except Exception:
            jitter_pct = random.uniform(0.10, 0.20)
        try:
            min_vram_env = os.getenv('VRAM_ALLOC_MIN')
            max_vram_env = os.getenv('VRAM_ALLOC_MAX')
            min_vram = float(min_vram_env) if min_vram_env is not None else 0.25
            max_vram = float(max_vram_env) if max_vram_env is not None else 0.85
        except Exception:
            min_vram, max_vram = 0.25, 0.85
        # Compute jittered allocation and clamp to [min_vram, max_vram]
        try:
            span = vram_alloc * jitter_pct
            candidate = random.uniform(vram_alloc - span, vram_alloc + span)
            vram_alloc_jittered = max(min_vram, min(max_vram, candidate))
        except Exception:
            vram_alloc_jittered = vram_alloc

        # Power mục tiêu dựa baseline
        target_power = int(max(20, min(self.power_max, self.baseline_power * (1.0 + power_var * 0.2))))

        if s in ('gpu', 'mining', 'aggressive'):
            params['power_limit'] = target_power
            # Clocks: tăng nhẹ theo biến thể profile
            try:
                handle = self.gpu_manager.get_handle(gpu_index)  # dùng đúng GPU đích để tham chiếu clock hiện tại
                if handle is not None:
                    current_sm = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
                    params['sm_clock'] = int(min(1245, current_sm * (1.0 + clock_var * 0.2)))
            except Exception:
                # fallback an toàn
                params['sm_clock'] = 1020
            params['mem_clock'] = params.get('mem_clock', 877)
            params['temperature'] = int(self.temp_warning)
            params['vram_allocation'] = vram_alloc_jittered
            params['window_sec'] = self.per_pid_window_sec or 0
        elif s in ('temperature',):
            params['temperature'] = int(self.temp_warning)
            params['power_limit'] = target_power
        elif s in ('memory', 'vram'):
            params['vram_allocation'] = vram_alloc_jittered
        else:
            # Mặc định coi như GPU strategy
            params['power_limit'] = target_power
            params['mem_clock'] = 877
            params['temperature'] = int(self.temp_warning)

        return params

    def _apply_compute_simulation(self, gpu_index: int, params: Dict[str, Any]) -> bool:
        """
        Apply compute load simulation
        """
        self.logger.debug(f"🔢 [OHC._apply_compute_simulation] Entry - GPU: {gpu_index}")
        
        try:
            pattern = params.get('compute_pattern', 'sine')
            duration = params.get('compute_duration', 10)
            # **HASHRATE FIX: Use compute_allocation from profile instead of fixed 0.5** (dùng compute_allocation từ profile thay vì cố định 0.5)
            intensity = params.get('compute_intensity', self.profile.get('compute_allocation', 0.95))
            self.logger.info(f"🎯 [OHC._apply_compute_simulation] Starting {pattern} pattern for {duration}s at {intensity*100}% intensity")
            self.logger.debug(f"🚀 **[HASHRATE-FIX] Using compute_allocation from profile** ([SỬA LỖI-HASHRATE] Sử dụng compute_allocation từ profile): {intensity*100}%")
            
            # Calculate duty cycle
            target_power = params.get('power_limit', self.baseline_power)
            duty_cycle = target_power / self.baseline_power
            duty_cycle = max(0.5, min(1.0, duty_cycle))
            self.logger.debug(f"📊 [OHC._apply_compute_simulation] Duty cycle: {duty_cycle:.2f}")
            
            # Launch compute kernel (argv form, no shell, no '&')
            compute_script = f"""
import torch
import time
import sys

try:
    a = torch.randn(2000, 2000, device='cuda')
    b = torch.randn(2000, 2000, device='cuda')
    
    work_time = {duty_cycle * 0.1}
    sleep_time = {(1 - duty_cycle) * 0.1}
    
    for _ in range(10):
        start = time.time()
        while time.time() - start < work_time:
            c = torch.matmul(a, b)
            torch.cuda.synchronize()
        time.sleep(sleep_time)
except Exception as e:
    print(f'Compute error: {e}', file=sys.stderr)
"""

            # Idempotency: skip if a previous subprocess still running; also prune finished
            try:
                self.active_subprocesses = [p for p in self.active_subprocesses if p.poll() is None]
            except Exception:
                pass
            if self.active_subprocesses:
                self.logger.info("⏭️ [OHC._apply_compute_simulation] Skip spawn: existing subprocess still running")
                return True

            env = os.environ.copy()
            env['CUDA_VISIBLE_DEVICES'] = str(gpu_index)
            proc = subprocess.Popen(
                ['python3', '-c', compute_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            self.active_subprocesses.append(proc)
            self.logger.info(f"✅ [OHC._apply_compute_simulation] Started compute PID: {proc.pid}")
            # Watchdog: đảm bảo tiến trình không chạy quá lâu
            try:
                ttl_env = os.getenv('GPU_SUBPROCESS_TTL_SEC') or os.getenv('SUBPROCESS_TTL_SEC')
                ttl = float(ttl_env) if ttl_env not in (None, '') else float(self.per_pid_window_sec or 30) + 5.0
                if ttl > 0:
                    self._watchdog_kill_after(proc, ttl, name=f"compute_sim[gpu={gpu_index}]")
            except Exception:
                pass
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [OHC._apply_compute_simulation] Failed: {e}", exc_info=True)
            return False
    
    def _verify_and_adjust_baseline(self, gpu_index: int) -> bool:
        """Verify and adjust baseline metrics and return boolean status"""
        self.logger.debug(f"🔧 [OHC._verify_and_adjust_baseline] Entry - verifying baseline for GPU {gpu_index}")
        
        try:
            status_ok = True
            actual_temp = self.gpu_manager.get_gpu_temperature(gpu_index)
            if actual_temp and abs(actual_temp - self.baseline_temp) > 5:
                self.logger.info(f"📊 [OHC._verify_and_adjust_baseline] Adjusting baseline temp: {self.baseline_temp}°C → {actual_temp}°C (delta: {abs(actual_temp - self.baseline_temp)}°C)")
                self.baseline_temp = actual_temp
                status_ok = False
            else:
                self.logger.debug(f"✅ [OHC._verify_and_adjust_baseline] Baseline temp OK: {self.baseline_temp}°C (actual: {actual_temp}°C)")
            
            actual_power = self._get_current_power(gpu_index)
            if actual_power is not None:
                # Guard công suất thấp bất thường: tránh set baseline khi reading quá thấp
                min_allowed_power = max(20, int(0.1 * self.baseline_power))
                if actual_power < min_allowed_power:
                    self.logger.warning(f"⚠️ [OHC._verify_and_adjust_baseline] Power reading too low ({actual_power}W < {min_allowed_power}W). Skip baseline update.")
                    status_ok = False
                elif abs(actual_power - self.baseline_power) > 10:
                    self.logger.info(f"⚡ [OHC._verify_and_adjust_baseline] Adjusting baseline power: {self.baseline_power}W → {actual_power}W (delta: {abs(actual_power - self.baseline_power)}W)")
                    self.baseline_power = actual_power
                    status_ok = False
                else:
                    self.logger.debug(f"✅ [OHC._verify_and_adjust_baseline] Baseline power OK: {self.baseline_power}W (actual: {actual_power}W)")
            
            return status_ok
        except Exception as e:
            self.logger.warning(f"⚠️ [OHC._verify_and_adjust_baseline] Baseline verification failed: {e}")
            return False

    def _manage_vram_allocation(self, gpu_index: int, params: Dict[str, Any]) -> bool:
        """
        Manage VRAM để mimic AI workload
        
        :param params: Control parameters
        :return: Success status
        """
        self.logger.debug(f"💾 [OHC._manage_vram_allocation] Entry - GPU: {gpu_index}, params: {list(params.keys())}")

        # Optional: Validate PID (if provided) before attempting VRAM allocation
        try:
            pid = params.get('pid')
            if pid is not None:
                pid_int = int(pid)
                if not os.path.exists(f"/proc/{pid_int}"):
                    self.logger.warning(f"⚠️ [OHC._manage_vram_allocation] Invalid PID {pid_int} → skip VRAM allocation")
                    return False
        except Exception as pid_err:
            self.logger.warning(f"⚠️ [OHC._manage_vram_allocation] PID validation failed: {pid_err}")
            return False

        try:
            # **HASHRATE FIX: Use vram_allocation from profile (now GPU_TARGET_UTIL-based)** (dùng vram_allocation từ profile - giờ dựa trên GPU_TARGET_UTIL)
            # Reduce VRAM reservation for mining workload unless explicitly overridden
            default_alloc = 0.2
            try:
                env_alloc = os.getenv('VRAM_ALLOCATION_DEFAULT')
                if env_alloc is not None:
                    default_alloc = max(0.0, min(1.0, float(env_alloc)))
            except Exception:
                pass
            target_percent = params.get('vram_allocation', self.profile.get('vram_allocation', default_alloc))
            self.logger.debug(f"📊 [OHC._manage_vram_allocation] Target VRAM allocation: {target_percent*100}%")
            
            # Get available VRAM
            total_vram = self._get_total_vram(gpu_index)
            target_bytes = int(total_vram * target_percent)
            target_mb = target_bytes // (1024**2)
            self.logger.info(f"🎯 [OHC._manage_vram_allocation] Allocating {target_mb}MB ({target_percent*100}% of {total_vram//1024**3}GB) on GPU {gpu_index}")
            
            # If allocation is near zero, skip subprocess entirely
            if target_percent <= 0.01:
                self.logger.info(f"💤 [OHC._manage_vram_allocation] vram_allocation={target_percent*100:.1f}% → skip VRAM allocator for GPU {gpu_index}")
                return True

            # Allocate với rotation pattern (argv form, no shell, no '&')
            vram_script = f"""
import torch
import time
import random
import sys
import logging

try:
    # Target allocation
    target_mb = {target_mb}

    # Allocate với variation
    allocated = []
    for i in range(3):
        size = int(target_mb * random.uniform(0.3, 0.4))
        tensor = torch.zeros(
            size, 1024, 1024 // 4,
            dtype=torch.float32, 
            device='cuda'
        )
        allocated.append(tensor)
        time.sleep(2)

    # Hold và rotate
    for _ in range(10):
        # Randomly deallocate and reallocate
        if random.random() < 0.3:
            idx = random.randint(0, 2)
            del allocated[idx]
            torch.cuda.empty_cache()

            size = int(target_mb * random.uniform(0.3, 0.4))
            allocated.insert(idx,
                torch.zeros(
                    size, 1024, 1024 // 4,
                    dtype=torch.float32, 
                    device='cuda'
                )
            )

        # Small computation để maintain activity
        if allocated:
            allocated[0] *= 1.001

        time.sleep(3)
except Exception as e:
    logging.exception('VRAM allocation error')
"""

            # Idempotency: prune finished and skip if still running
            try:
                self.active_subprocesses = [p for p in self.active_subprocesses if p.poll() is None]
            except Exception:
                pass
            if self.active_subprocesses:
                self.logger.info("⏭️ [OHC._manage_vram_allocation] Skip spawn: existing subprocess still running")
                return True

            env = os.environ.copy()
            env['CUDA_VISIBLE_DEVICES'] = str(gpu_index)
            proc = subprocess.Popen(
                ['python3', '-c', vram_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            self.active_subprocesses.append(proc)
            self.logger.info(f"✅ [OHC._manage_vram_allocation] Started VRAM allocation subprocess PID: {proc.pid} on GPU {gpu_index}")
            # Watchdog: đảm bảo tiến trình không chạy quá lâu
            try:
                ttl_env = os.getenv('GPU_SUBPROCESS_TTL_SEC') or os.getenv('SUBPROCESS_TTL_SEC')
                ttl = float(ttl_env) if ttl_env not in (None, '') else float(self.per_pid_window_sec or 30) + 5.0
                if ttl > 0:
                    self._watchdog_kill_after(proc, ttl, name=f"vram_alloc[gpu={gpu_index}]")
            except Exception:
                pass
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [OHC._manage_vram_allocation] Failed to manage VRAM: {e}", exc_info=True)
            return False
    
    def _get_total_vram(self, gpu_index: int) -> int:
        """Get total VRAM in bytes"""
        self.logger.debug(f"🔍 [OHC._get_total_vram] Getting total VRAM for GPU {gpu_index}")
        
        try:
            handle = self.gpu_manager.get_handle(gpu_index)
            if handle is not None:
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_gb = mem_info.total / (1024**3)
                self.logger.debug(f"✅ [OHC._get_total_vram] GPU {gpu_index} has {total_gb:.2f}GB VRAM")
                return mem_info.total
        except Exception as e:
            self.logger.warning(f"⚠️ [OHC._get_total_vram] Cannot read VRAM for GPU {gpu_index}: {e}, using default 8GB")
        
        return 8 * 1024**3  # Default 8GB to bytes
    
    def _should_verify_baseline(self, gpu_index: int) -> bool:
        """Check if baseline verification is needed for a specific GPU index.
        Uses env-overrides for thresholds when available.
        """
        try:
            # Thresholds (ENV overrides)
            power_dev_pct = 0.30  # 30%
            temp_dev_c = 10.0     # 10°C
            try:
                _p = os.getenv('BASELINE_VERIFY_POWER_DEV_PCT')
                if _p not in (None, ''):
                    power_dev_pct = max(0.0, float(_p))
            except Exception:
                pass
            try:
                _t = os.getenv('BASELINE_VERIFY_TEMP_DEV_C')
                if _t not in (None, ''):
                    temp_dev_c = max(0.0, float(_t))
            except Exception:
                pass

            # Get current metrics for the specified GPU
            current_power = self._get_current_power(gpu_index)
            current_temp = self.gpu_manager.get_gpu_temperature(gpu_index)

            # Check power deviation
            try:
                if current_power is not None and self.baseline_power:
                    power_deviation = abs(current_power - self.baseline_power) / float(self.baseline_power)
                    if power_deviation > power_dev_pct:
                        self.logger.debug(f"🔍 [OHC._should_verify_baseline] Power deviation detected on GPU {gpu_index}: {power_deviation:.1%} (> {power_dev_pct:.0%})")
                        return True
            except Exception:
                pass

            # Check temperature deviation
            try:
                if current_temp is not None and self.baseline_temp is not None:
                    temp_deviation = abs(float(current_temp) - float(self.baseline_temp))
                    if temp_deviation > temp_dev_c:
                        self.logger.debug(f"🔍 [OHC._should_verify_baseline] Temperature deviation detected on GPU {gpu_index}: {temp_deviation:.1f}°C (> {temp_dev_c:.1f}°C)")
                        return True
            except Exception:
                pass

            return False

        except Exception as e:
            self.logger.warning(f"⚠️ [OHC._should_verify_baseline] Check failed for GPU {gpu_index}: {e}")
            return False

    def _cancel_pending_restores_for_gpu(self, gpu_index: int, except_key: Optional[tuple] = None) -> int:
        """
        Hủy tất cả các restore đang chờ theo GPU (cross-PID) ngoại trừ một khóa tùy chọn.
        Trả về số lượng restore đã hủy.

        Purpose: Khi một PID mới bắt đầu tối ưu trên cùng GPU, mọi restore pending
        từ PID cũ (trên cùng GPU) có thể gây reset device-wide (NVML reset clocks),
        làm tụt hashrate của phiên mới. Hàm này chủ động hủy các restore pending khác.
        """
        # Cho phép opt-out qua ENV nếu cần thử nghiệm
        try:
            if str(os.getenv('CANCEL_CROSS_PID_RESTORE_BY_GPU', '1')).lower() in ('0', 'false', 'no'):
                return 0
        except Exception:
            pass

        canceled = 0
        try:
            keys_to_cancel = []
            for key, ev in list(self.restore_cancel_events.items()):
                try:
                    _, k_gpu = key
                except Exception:
                    continue
                try:
                    same_gpu = int(k_gpu) == int(gpu_index)
                except Exception:
                    same_gpu = (k_gpu == gpu_index)
                if same_gpu and (except_key is None or key != except_key):
                    keys_to_cancel.append(key)

            for key in keys_to_cancel:
                ev = self.restore_cancel_events.get(key)
                if ev:
                    try:
                        ev.set()
                    except Exception:
                        pass
                try:
                    del self.restore_cancel_events[key]
                except Exception:
                    pass
                canceled += 1

            if canceled > 0:
                try:
                    self.logger.debug(f"🧹 [OHC] Canceled {canceled} pending restore(s) on GPU {gpu_index} (except={except_key})")
                except Exception:
                    pass
        except Exception as e:
            try:
                self.logger.debug(f"[OHC] _cancel_pending_restores_for_gpu error: {e}")
            except Exception:
                pass
        return canceled

    def _schedule_restore(self, pid: int, gpu_index: int, window_sec: int, cancel_event: Optional[threading.Event] = None):
        # Cancellable restore of device-wide settings after time window (per-PID simulation window)
        try:
            key = (int(pid), int(gpu_index))
            # Early skip if window_sec <= 0 (nothing to schedule)
            try:
                if int(float(window_sec)) <= 0:
                    try:
                        self.logger.debug(f"⏭️ [OHC._schedule_restore] Skip scheduling restore for PID {pid} (GPU {gpu_index}) because window_sec={window_sec}")
                    except Exception:
                        pass
                    return
            except Exception:
                # If parsing fails, continue with scheduling as before
                pass
            # Nếu caller không đưa vào event, tạo mới; đồng thời hủy restore cũ nếu còn tồn tại
            prev_event = self.restore_cancel_events.get(key)
            if cancel_event is None:
                cancel_event = threading.Event()
            if prev_event and prev_event is not cancel_event:
                try:
                    prev_event.set()
                    self.logger.debug(f"🧹 [OHC._schedule_restore] Canceled previous restore for key={key}")
                except Exception:
                    pass
            # Ghi nhận event hiện hành cho key này
            self.restore_cancel_events[key] = cancel_event

            # Hủy các restore pending khác trên cùng GPU (cross-PID) để tránh reset device-wide 
            # ảnh hưởng đến phiên tối ưu hiện tại
            try:
                _ = self._cancel_pending_restores_for_gpu(gpu_index, except_key=key)
            except Exception:
                pass
            try:
                env_flag = os.getenv('CANCEL_CROSS_PID_RESTORE_BY_GPU', '1')
                self.logger.debug(f"[OHC._schedule_restore] Cross-PID cancel flag CANCEL_CROSS_PID_RESTORE_BY_GPU={env_flag} (đã gọi _cancel_pending_restores_for_gpu)")
            except Exception:
                pass

            # Poll interval ngắn để hủy sớm
            poll_env = os.getenv('RESTORE_POLL_INTERVAL_SEC')
            poll_interval = 0.1
            try:
                if poll_env not in (None, ''):
                    poll_interval = max(0.02, float(poll_env))
            except Exception:
                poll_interval = 0.1

            wait_seconds = max(0.0, float(window_sec))
            self.logger.debug(f"⏰ [OHC._schedule_restore] Scheduling restore for PID {pid} on GPU {gpu_index} after {wait_seconds}s (poll={poll_interval}s)")
            
            def _restore_task(ev: threading.Event):
                try:
                    correlation_id = uuid.uuid4().hex
                    deadline = time.time() + wait_seconds
                    self.logger.debug(f"⏳ [OHC._schedule_restore] CID={correlation_id} Waiting up to {wait_seconds}s before restore (cancellable)...")
                    while time.time() < deadline:
                        if ev.is_set():
                            self.logger.info(f"🛑 [OHC._schedule_restore] CID={correlation_id} Restore canceled for PID={pid}, GPU={gpu_index} before execution")
                            return
                        time.sleep(min(poll_interval, max(0.0, deadline - time.time())))
                    # Đã hết thời gian và chưa bị hủy → tiếp tục qua pha idle-gate (nếu được bật)
                    # Guard cuối trước idle-gate
                    if ev.is_set():
                        self.logger.info(f"🛑 [OHC._schedule_restore] CID={correlation_id} Restore canceled for PID={pid}, GPU={gpu_index} right before execution")
                        return
                    # Idle-gated restore: yêu cầu GPU idle dưới ngưỡng trong khoảng thời gian cấu hình
                    try:
                        thr_env = os.getenv('RESTORE_IDLE_UTIL_THRESHOLD', '0.10')
                        idle_thr = float(thr_env)
                        if idle_thr > 1.0:
                            idle_thr = idle_thr / 100.0
                    except Exception:
                        idle_thr = 0.10
                    try:
                        min_idle_dur = float(os.getenv('RESTORE_IDLE_MIN_DURATION_SEC', '60'))
                    except Exception:
                        min_idle_dur = 60.0
                    if min_idle_dur > 0.0:
                        try:
                            self.logger.debug(f"[OHC._schedule_restore] CID={correlation_id} Idle-gated restore enabled: thr={idle_thr:.2f}, dur={min_idle_dur:.1f}s, poll={poll_interval}s")
                        except Exception:
                            pass
                        idle_until = time.time() + max(0.0, float(min_idle_dur))
                        while time.time() < idle_until:
                            if ev.is_set():
                                self.logger.info(f"🛑 [OHC._schedule_restore] CID={correlation_id} Restore canceled for PID={pid}, GPU={gpu_index} during idle-gate")
                                return
                            util = 0.0
                            try:
                                util = float(self._get_utilization_percent(gpu_index))
                            except Exception as _ue:
                                try:
                                    self.logger.debug(f"[OHC._schedule_restore] CID={correlation_id} Cannot read GPU util for idle-gate: {_ue}")
                                except Exception:
                                    pass
                            # Nếu GPU hoạt động vượt ngưỡng trong thời gian idle-gate → bỏ qua restore
                            if util > idle_thr:
                                try:
                                    self.logger.info(f"⛔ [OHC._schedule_restore] CID={correlation_id} Active GPU detected (util={util:.2f} > thr={idle_thr:.2f}) → skipping restore")
                                except Exception:
                                    pass
                                return
                            time.sleep(poll_interval)
                    # Qua idle-gate (hoặc idle-gate bị vô hiệu hóa) → thực hiện restore
                    self.logger.info(f"🔄 [OHC._schedule_restore] CID={correlation_id} Restoring GPU settings for PID {pid}")
                    self.gpu_manager.restore_gpu_settings_for_pid(pid, correlation_id=correlation_id)
                    # Clean up simulation processes
                    self.cleanup()
                    self.logger.info(f"✅ [OHC._schedule_restore] CID={correlation_id} Restored GPU settings after {wait_seconds}s for PID={pid} (GPU={gpu_index})")
                except Exception as e:
                    self.logger.warning(f"⚠️ [OHC._schedule_restore] CID={correlation_id} Error during auto-restore for PID={pid}: {e}")
                finally:
                    # Chỉ xóa map nếu vẫn trỏ tới đúng event này
                    try:
                        cur = self.restore_cancel_events.get(key)
                        if cur is ev:
                            del self.restore_cancel_events[key]
                    except Exception:
                        pass

            t = threading.Thread(target=lambda: _restore_task(cancel_event), name=f"restore-{pid}-{gpu_index}", daemon=True)
            t.start()
            self.logger.debug(f"✅ [OHC._schedule_restore] Restore thread started for PID {pid} (GPU {gpu_index})")
        except Exception as e:
            self.logger.warning(f"⚠️ [OHC._schedule_restore] Failed to start restore thread for PID={pid}: {e}")
    
    def _watchdog_kill_after(self, proc: subprocess.Popen, ttl_sec: float, name: str = "subprocess"):
        """
        Watchdog theo dõi và hủy tiến trình nếu chạy quá thời gian ttl_sec.
        """
        def _wd():
            try:
                deadline = time.time() + max(0.0, float(ttl_sec))
                while time.time() < deadline:
                    if proc.poll() is not None:
                        return
                    time.sleep(0.5)
                if proc.poll() is None:
                    self.logger.warning(f"⏱️ [OHC.watchdog] {name} PID {proc.pid} exceeded {ttl_sec}s → terminating")
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    try:
                        proc.wait(timeout=2)
                    except Exception:
                        pass
                    if proc.poll() is None:
                        self.logger.warning(f"🛑 [OHC.watchdog] Force killing {name} PID {proc.pid}")
                        try:
                            proc.kill()
                        except Exception:
                            pass
            except Exception as _e:
                try:
                    self.logger.debug(f"[OHC.watchdog] Error: {_e}")
                except Exception:
                    pass
        threading.Thread(target=_wd, daemon=True).start()
    
    def cleanup(self):
        # Clean up resources
        self.logger.info(f"🧹 [OHC.cleanup] Starting cleanup - {len(self.active_subprocesses)} active subprocess(es)")
        
        # Terminate subprocesses
        for proc in self.active_subprocesses:
            try:
                if proc.poll() is None:
                    self.logger.debug(f"🛑 [OHC.cleanup] Terminating subprocess PID: {proc.pid}")
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                        self.logger.debug(f"✅ [OHC.cleanup] Subprocess PID {proc.pid} terminated")
                    except Exception:
                        if proc.poll() is None:
                            self.logger.debug(f"🧨 [OHC.cleanup] Forcing kill for subprocess PID: {proc.pid}")
                            try:
                                proc.kill()
                            except Exception:
                                pass
                            try:
                                proc.wait(timeout=1)
                            except Exception:
                                pass
            except Exception as e:
                self.logger.warning(f"⚠️ [OHC.cleanup] Failed to terminate subprocess PID {proc.pid}: {e}")
        
        self.active_subprocesses.clear()
        self.logger.info("✅ [OHC.cleanup] OptimizedHardwareController cleanup complete")
