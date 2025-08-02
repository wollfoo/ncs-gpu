# utils.py

import logging
import subprocess
import functools
import time
import psutil
import pynvml
import threading
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Helper ghi log JSON cho tính năng GPU
# ---------------------------------------------------------------------------
# Telemetry functionality has been removed
def log_gpu_feature(*_args, **_kwargs):  # type: ignore
    """Telemetry logging functionality has been removed"""
    pass

###############################################################################
#                           DECORATOR retry (đồng bộ)                          #
###############################################################################
def retry(exception_to_check: Any, tries: int = 4, delay: float = 3.0, backoff: float = 2.0):
    """
    Decorator đồng bộ để retry một hàm nếu gặp exception cụ thể.

    :param exception_to_check: Exception hoặc tuple exceptions cần bắt để retry.
    :param tries: Số lần thử (int).
    :param delay: Thời gian chờ ban đầu giữa các lần thử (float, tính bằng giây).
    :param backoff: Hệ số nhân thời gian chờ (float).
    :return: Giá trị hàm nếu thành công, hoặc raise exception nếu hết tries.
    """
    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exception_to_check as e:
                    logging.getLogger(__name__).warning(
                        f"Lỗi '{e}' xảy ra trong '{func.__name__}'. "
                        f"Thử lại sau {mdelay} giây..."
                    )
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)
        return wrapper_retry
    return decorator_retry

###############################################################################
#                           LỚP GPUManager (Singleton)                         #
###############################################################################
class GPUManager:
    """
    Lớp Singleton quản lý GPU bằng NVML, cung cấp các phương thức lấy và điều chỉnh
    thông số GPU như power limit, xung nhịp, mức sử dụng GPU, v.v.

    Attributes:
        gpu_initialized (bool): Đánh dấu NVML đã được khởi tạo hay chưa.
        gpu_count (int): Số lượng GPU có trong hệ thống (nếu NVML init thành công).
        logger (logging.Logger): Đối tượng logger.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """
        Tạo (hoặc trả về) instance singleton của GPUManager.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(GPUManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Khởi tạo GPUManager, đảm bảo chỉ chạy 1 lần cho singleton.
        """
        if getattr(self, '_initialized', False):
            return
        self._initialized = True

        self.gpu_initialized = False
        self.logger = logging.getLogger(__name__)
        self.gpu_count = 0

    def initialize(self) -> bool:
        """
        Khởi tạo NVML đồng bộ. Nếu thành công, đánh dấu gpu_initialized = True.

        :return: True nếu NVML init thành công, ngược lại False.
        """
        try:
            pynvml.nvmlInit()
            self.gpu_count = pynvml.nvmlDeviceGetCount()
            self.gpu_initialized = True
            self.logger.info(f"NVML khởi tạo thành công. Phát hiện {self.gpu_count} GPU.")
            return True
        except pynvml.NVMLError as e:
            self.gpu_initialized = False
            self.logger.warning(f"Không thể khởi tạo NVML: {e}. GPUManager sẽ vô hiệu.")
            return False
        except Exception as e:
            self.gpu_initialized = False
            self.logger.error(f"Lỗi không xác định khi khởi tạo GPUManager: {e}")
            return False

    def shutdown_nvml(self) -> None:
        """
        Giải phóng NVML nếu đã khởi tạo. Đồng bộ.
        """
        if self.gpu_initialized:
            try:
                pynvml.nvmlShutdown()
                self.logger.info("NVML đã được đóng thành công.")
                self.gpu_initialized = False
            except pynvml.NVMLError as e:
                self.logger.error(f"Lỗi khi đóng NVML: {e}")

    def get_total_gpu_memory(self) -> float:
        """
        Lấy tổng dung lượng bộ nhớ của tất cả GPU (MB).

        :return: Dung lượng (MB). Trả về 0.0 nếu lỗi hoặc chưa init.
        """
        if not self.gpu_initialized:
            return 0.0
        total_memory = 0.0
        try:
            for i in range(self.gpu_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_memory += mem_info.total / (1024**2)
            return total_memory
        except pynvml.NVMLError as e:
            self.logger.error(f"Lỗi khi lấy tổng bộ nhớ GPU: {e}")
            return 0.0

    def get_used_gpu_memory(self) -> float:
        """
        Lấy tổng bộ nhớ GPU đang sử dụng (MB).

        :return: Dung lượng đang sử dụng (MB). Trả về 0.0 nếu lỗi hoặc chưa init.
        """
        if not self.gpu_initialized:
            return 0.0
        used_memory = 0.0
        try:
            for i in range(self.gpu_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                used_memory += mem_info.used / (1024**2)
            return used_memory
        except pynvml.NVMLError as e:
            self.logger.error(f"Lỗi khi lấy bộ nhớ GPU đã sử dụng: {e}")
            return 0.0

    @retry(pynvml.NVMLError, tries=3, delay=2, backoff=2)
    def set_gpu_power_limit(self, gpu_index: int, power_limit_w: int) -> bool:
        """
        Đặt power limit cho GPU, có cơ chế retry nếu gặp NVML error.

        :param gpu_index: Chỉ số GPU.
        :param power_limit_w: Power limit (W).
        :return: True nếu set thành công, ngược lại raise exception.
        """
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            power_limit_mw = power_limit_w * 1000
            pynvml.nvmlDeviceSetPowerManagementLimit(handle, power_limit_mw)
            self.logger.info(f"Đặt power limit GPU {gpu_index} = {power_limit_w}W.")
            # ----- JSON log -----
            log_gpu_feature(
                feature="gpu_optimization",
                state="updated",
                parameters={"gpu_index": gpu_index, "power_limit_w": power_limit_w},
                message=f"Đặt power limit GPU {gpu_index} = {power_limit_w}W",
            )
            return True
        except pynvml.NVMLError as e:
            self.logger.error(f"Lỗi khi đặt power limit GPU {gpu_index}: {e}")
            log_gpu_feature(
                feature="gpu_optimization",
                state="error",
                parameters={"gpu_index": gpu_index, "power_limit_w": power_limit_w},
                error_code="NVML_ERR",
                message=str(e),
            )
            raise
        except Exception as e:
            self.logger.error(f"Lỗi bất ngờ set power limit GPU {gpu_index}: {e}")
            log_gpu_feature(
                feature="gpu_optimization",
                state="error",
                parameters={"gpu_index": gpu_index, "power_limit_w": power_limit_w},
                error_code="POWER_ERR",
                message=str(e),
            )
            raise

    def get_gpu_power_limit(self, gpu_index: int) -> Optional[float]:
        """
        Lấy power limit hiện tại của GPU (W).

        :param gpu_index: Chỉ số GPU.
        :return: Power limit (float) hoặc None nếu lỗi.
        """
        if not self.gpu_initialized:
            self.logger.error("GPU chưa init. Không thể lấy power limit.")
            return None
        if gpu_index < 0 or gpu_index >= self.gpu_count:
            self.logger.error(f"GPU index {gpu_index} không hợp lệ, chỉ có {self.gpu_count} GPU.")
            return None
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            power_limit_mw = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
            power_limit_w = power_limit_mw / 1000
            self.logger.debug(f"GPU {gpu_index} power limit = {power_limit_w}W.")
            return power_limit_w
        except pynvml.NVMLError as e:
            self.logger.error(f"Lỗi NVML get power limit GPU {gpu_index}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Lỗi get power limit GPU {gpu_index}: {e}")
            return None

    def get_gpu_temperature(self, gpu_index: int) -> Optional[float]:
        """
        Lấy nhiệt độ GPU (°C).

        :param gpu_index: Chỉ số GPU.
        :return: Nhiệt độ (°C), hoặc None nếu lỗi.
        """
        if not self.gpu_initialized:
            self.logger.error("Chưa init NVML. Không thể lấy nhiệt độ.")
            return None
        if gpu_index < 0 or gpu_index >= self.gpu_count:
            self.logger.error(f"GPU index {gpu_index} không hợp lệ.")
            return None
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            self.logger.debug(f"Nhiệt độ GPU {gpu_index} = {temperature}°C.")
            return float(temperature)
        except pynvml.NVMLError as e:
            self.logger.error(f"Lỗi NVML khi lấy nhiệt độ GPU {gpu_index}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Lỗi khi lấy nhiệt độ GPU {gpu_index}: {e}")
            return None

    def get_gpu_utilization(self, gpu_index: int) -> Optional[Dict[str, float]]:
        """
        Lấy GPU utilization (phần trăm GPU, phần trăm memory).

        :param gpu_index: Chỉ số GPU.
        :return: Dict {'gpu_util_percent', 'memory_util_percent'} hoặc None nếu lỗi.
        """
        if not self.gpu_initialized:
            self.logger.error("Chưa init GPU. Không thể lấy utilization.")
            return None
        if gpu_index < 0 or gpu_index >= self.gpu_count:
            self.logger.error(f"GPU index {gpu_index} không hợp lệ.")
            return None
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            return {
                'gpu_util_percent': float(utilization.gpu),
                'memory_util_percent': float(utilization.memory)
            }
        except pynvml.NVMLError as e:
            self.logger.error(f"Lỗi NVML get utilization GPU {gpu_index}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Lỗi khi get utilization GPU {gpu_index}: {e}")
            return None

    def set_gpu_clocks(self, gpu_index: int, sm_clock: int, mem_clock: int) -> bool:
        """
        Khóa xung nhịp SM và Memory cho GPU bằng lệnh nvidia-smi.

        :param gpu_index: Chỉ số GPU.
        :param sm_clock: Mức SM clock (MHz).
        :param mem_clock: Mức Memory clock (MHz).
        :return: True nếu đặt thành công, False nếu lỗi.
        """
        if not self.gpu_initialized:
            self.logger.error("Chưa init GPU. Không thể set xung nhịp.")
            return False
        if gpu_index < 0 or gpu_index >= self.gpu_count:
            self.logger.error(f"GPU index {gpu_index} không hợp lệ.")
            return False
        try:
            cmd_sm = ['nvidia-smi', '-i', str(gpu_index), f'--lock-gpu-clocks={sm_clock}']
            subprocess.run(cmd_sm, check=True)

            cmd_mem = ['nvidia-smi', '-i', str(gpu_index), f'--lock-memory-clocks={mem_clock}']
            subprocess.run(cmd_mem, check=True)
            self.logger.debug(f"Đặt SM={sm_clock}MHz, MEM={mem_clock}MHz cho GPU={gpu_index}.")
            log_gpu_feature(
                feature="gpu_optimization",
                state="updated",
                parameters={
                    "gpu_index": gpu_index,
                    "sm_clock_mhz": sm_clock,
                    "mem_clock_mhz": mem_clock,
                },
                message=f"Đặt clock GPU {gpu_index}: SM={sm_clock}, MEM={mem_clock}",
            )
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Lỗi nvidia-smi khi set xung nhịp GPU {gpu_index}: {e}")
            log_gpu_feature(
                feature="gpu_optimization",
                state="error",
                parameters={
                    "gpu_index": gpu_index,
                    "sm_clock_mhz": sm_clock,
                    "mem_clock_mhz": mem_clock,
                },
                error_code="CLOCK_ERR",
                message=str(e),
            )
            return False
        except Exception as e:
            self.logger.error(f"Lỗi set xung nhịp GPU {gpu_index}: {e}")
            log_gpu_feature(
                feature="gpu_optimization",
                state="error",
                parameters={
                    "gpu_index": gpu_index,
                    "sm_clock_mhz": sm_clock,
                    "mem_clock_mhz": mem_clock,
                },
                error_code="CLOCK_ERR",
                message=str(e),
            )
            return False

    def control_fan_speed(self, gpu_index: int, increase_percentage: float) -> bool:
        """
        Điều chỉnh tốc độ quạt GPU qua nvidia-settings.

        :param gpu_index: Chỉ số GPU.
        :param increase_percentage: Mức tăng quạt (%).
        :return: True nếu thành công, False nếu lỗi.
        """
        try:
            cmd = [
                'nvidia-settings',
                '-a', f'[fan:{gpu_index}]/GPUFanControlState=1',
                '-a', f'[fan:{gpu_index}]/GPUTargetFanSpeed={int(increase_percentage)}'
            ]
            subprocess.run(cmd, check=True)
            self.logger.debug(f"Tăng fan GPU {gpu_index}={increase_percentage}%.")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Lỗi khi điều chỉnh quạt GPU {gpu_index}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi khi điều chỉnh quạt GPU {gpu_index}: {e}")
            return False

    def calculate_desired_power_limit(self, gpu_index: int, throttle_percentage: float) -> Optional[int]:
        """
        Tính power limit mới cho GPU dựa trên throttle_percentage.

        :param gpu_index: Chỉ số GPU.
        :param throttle_percentage: Tỷ lệ giảm (0..100).
        :return: Power limit mới (W), hoặc None nếu lỗi.
        """
        try:
            current_power_limit = self.get_gpu_power_limit(gpu_index)
            if current_power_limit is None:
                self.logger.warning(f"Không lấy được power limit GPU {gpu_index}, mặc định=100W.")
                current_power_limit = 100.0
            desired_limit = int(round(current_power_limit * (1 - throttle_percentage / 100.0)))
            self.logger.debug(f"Power limit mới GPU={gpu_index}={desired_limit}W (throttle={throttle_percentage}%).")
            return desired_limit
        except Exception as e:
            self.logger.error(f"Lỗi calculate_desired_power_limit GPU={gpu_index}: {e}")
            return None

    def restore_resources(self, pid: int, gpu_settings: Dict[int, Dict[str, Any]]) -> bool:
        """
        Khôi phục cài đặt GPU (power limit, clocks) dựa trên gpu_settings đã lưu.

        :param pid: PID liên quan (chỉ để log).
        :param gpu_settings: Dict GPU index -> { 'power_limit_w':..., 'sm_clock_mhz':..., 'mem_clock_mhz':... }
        :return: True nếu khôi phục thành công, False nếu có lỗi.
        """
        try:
            restored_all = True
            for gpu_index, settings in gpu_settings.items():
                original_power_limit_w = settings.get('power_limit_w')
                if original_power_limit_w is not None:
                    ok_power = self.set_gpu_power_limit(gpu_index, int(original_power_limit_w))
                    if ok_power:
                        self.logger.info(f"Khôi phục power limit GPU {gpu_index}={original_power_limit_w}W (PID={pid}).")
                    else:
                        self.logger.error(f"Không thể khôi phục power limit GPU {gpu_index} (PID={pid}).")
                        restored_all = False

                original_sm = settings.get('sm_clock_mhz')
                original_mem = settings.get('mem_clock_mhz')
                if original_sm and original_mem:
                    ok_clocks = self.set_gpu_clocks(gpu_index, int(original_sm), int(original_mem))
                    if ok_clocks:
                        self.logger.info(f"Khôi phục xung nhịp GPU {gpu_index}, SM={original_sm}, MEM={original_mem} (PID={pid}).")
                    else:
                        self.logger.error(f"Không thể khôi phục xung nhịp GPU {gpu_index} (PID={pid}).")
                        restored_all = False

            self.logger.info(f"Khôi phục GPU cho PID={pid} hoàn tất.")
            return restored_all
        except Exception as e:
            self.logger.error(f"Lỗi khôi phục GPU PID={pid}: {e}")
            return False

###############################################################################
#                           LỚP MiningProcess                                  #
###############################################################################
class MiningProcess:
    """
    Lớp đại diện cho một tiến trình khai thác tiền điện tử (hoặc AI),
    cung cấp thông tin về CPU usage, GPU usage, RAM, Disk I/O, Network I/O, v.v.

    Attributes:
        pid (int): PID tiến trình.
        name (str): Tên tiến trình.
        priority (int): Độ ưu tiên của tiến trình.
        network_interface (str): Giao diện mạng (default='eth0').
        logger (logging.Logger): Logger để ghi log.
        is_cloaked (bool): Cờ đánh dấu tiến trình đã được cloaking.
        gpu_manager (GPUManager): Đối tượng quản lý GPU (singleton).
        gpu_initialized (bool): Đánh dấu GPU đã init hay chưa.

        cpu_usage (float): % sử dụng CPU hiện tại.
        gpu_usage (float): % sử dụng GPU hiện tại.
        memory_usage (float): % sử dụng RAM hiện tại.
        disk_io (float): Lưu lượng Disk I/O (MB) kể từ lần cập nhật trước.
        network_io (float): Lưu lượng Network I/O (MB) kể từ lần cập nhật trước.
        mark (int): Mark để sử dụng với iptables (VD: PID % 65535).
        _prev_bytes_sent (Optional[int]): Lưu bytes_sent cũ để tính chênh lệch.
        _prev_bytes_recv (Optional[int]): Lưu bytes_recv cũ để tính chênh lệch.
    """

    def __init__(
        self,
        pid: int,
        name: str,
        is_gpu: bool = False,
        priority: int = 1,
        network_interface: str = 'eth0',
        logger: Optional[logging.Logger] = None
    ):
        """
        ✅ ENHANCED: Khởi tạo MiningProcess với classification metadata.

        :param pid: PID của tiến trình.
        :param name: Tên tiến trình.
        :param is_gpu: Cờ đánh dấu tiến trình GPU (bool).
        :param priority: Độ ưu tiên (int).
        :param network_interface: Tên giao diện mạng (str).
        :param logger: Đối tượng Logger (nếu None => tạo logger mặc định).
        """
        self.pid = pid
        self.name = name
        self.priority = priority
        self.cpu_usage = 0.0
        self.gpu_usage = 0.0
        self.memory_usage = 0.0
        self.disk_io = 0.0
        self.network_io = 0.0
        self.mark = pid % 65535
        self.network_interface = network_interface
        self._prev_bytes_sent: Optional[int] = None
        self._prev_bytes_recv: Optional[int] = None
        self.is_cloaked = False
        self.logger = logger or logging.getLogger(__name__)

        # GPUManager (singleton)
        self.gpu_manager = GPUManager()
        self.gpu_initialized = self.gpu_manager.gpu_initialized
        
        # ✅ ENHANCED: Classification metadata system
        self._is_gpu = is_gpu
        self.process_type = 'GPU' if is_gpu else 'CPU'
        
        # 🎯 HARDWARE CLASSIFICATION
        self.hardware_classification = {
            'is_gpu_process': is_gpu,
            'requires_nvml': is_gpu,
            'resource_requirements': self._determine_resource_requirements(is_gpu),
            'optimization_profile': self._get_optimization_profile(is_gpu),
            'hardware_affinity': 'compute_intensive' if is_gpu else 'general_purpose'
        }
        
        # 🚀 STRATEGY OPTIMIZATION HINTS
        self.strategy_hints = {
            'preferred_cgroup_config': 'gpu_intensive' if is_gpu else 'cpu_balanced',
            'stealth_requirements': 'high' if is_gpu else 'medium',
            'resource_limits': self._calculate_resource_limits(is_gpu),
            'priority_class': 'high_performance' if is_gpu else 'balanced',
            'cloaking_aggressiveness': 'aggressive' if is_gpu else 'moderate'
        }
        
        # 📊 METADATA TRACKING
        self.classification_metadata = {
            'classification_time': time.time(),
            'classification_source': 'constructor',
            'confidence_score': 1.0,  # High confidence from explicit parameter
            'auto_detected': False,  # Explicitly set via parameter
            'fallback_classification': self._fallback_classification_check()
        }

    def is_gpu_process(self) -> bool:
        """
        ✅ ENHANCED: Kiểm tra process type từ classification metadata.

        :return: True nếu process được classified là GPU, False nếu CPU.
        """
        return self._is_gpu
    
    def get_process_type(self) -> str:
        """
        ✅ NEW: Get classified process type.
        
        :return: 'GPU' hoặc 'CPU' based on classification.
        """
        return self.process_type
    
    def get_hardware_classification(self) -> Dict[str, Any]:
        """
        ✅ NEW: Get hardware classification metadata.
        
        :return: Dictionary chứa hardware classification data.
        """
        return self.hardware_classification.copy()
    
    def get_strategy_hints(self) -> Dict[str, Any]:
        """
        ✅ NEW: Get optimization hints for strategies.
        
        :return: Dictionary chứa strategy optimization hints.
        """
        return self.strategy_hints.copy()
    
    def get_classification_metadata(self) -> Dict[str, Any]:
        """
        ✅ NEW: Get classification metadata và tracking info.
        
        :return: Dictionary chứa classification metadata.
        """
        return self.classification_metadata.copy()
    
    def _determine_resource_requirements(self, is_gpu: bool) -> Dict[str, Any]:
        """
        ✅ HELPER: Determine resource requirements based on process type.
        
        :param is_gpu: Process type indicator.
        :return: Resource requirements dictionary.
        """
        if is_gpu:
            return {
                'memory_intensive': True,
                'compute_intensive': True,
                'bandwidth_requirements': 'high',
                'thermal_impact': 'significant',
                'power_consumption': 'high'
            }
        else:
            return {
                'memory_intensive': False,
                'compute_intensive': 'moderate',
                'bandwidth_requirements': 'medium',
                'thermal_impact': 'minimal',
                'power_consumption': 'low'
            }
    
    def _get_optimization_profile(self, is_gpu: bool) -> str:
        """
        ✅ HELPER: Get optimization profile for process type.
        
        :param is_gpu: Process type indicator.
        :return: Optimization profile string.
        """
        return 'gpu_compute_optimized' if is_gpu else 'cpu_general_purpose'
    
    def _calculate_resource_limits(self, is_gpu: bool) -> Dict[str, Any]:
        """
        ✅ HELPER: Calculate appropriate resource limits.
        
        :param is_gpu: Process type indicator.
        :return: Resource limits dictionary.
        """
        if is_gpu:
            return {
                'cpu_limit_percent': 80,  # Allow high CPU for GPU processes
                'memory_limit_mb': 6144,  # Optimized memory limit for GPU mining (TARGET: 6144MB)
                'nice_priority': -5,      # Higher priority
                'oom_score_adj': -500     # Lower OOM score
            }
        else:
            return {
                'cpu_limit_percent': 60,  # More conservative CPU limit
                'memory_limit_mb': 4096,  # Standard memory limit for non-GPU processes
                'nice_priority': 10,      # Lower priority
                'oom_score_adj': 0        # Default OOM score
            }
    
    def _fallback_classification_check(self) -> Dict[str, Any]:
        """
        ✅ HELPER: Fallback classification dựa trên process name.
        
        :return: Fallback classification results.
        """
        gpu_keywords = ['inference-cuda', 'gpu', 'cuda', 'nvidia']
        name_based_gpu = any(keyword in self.name.lower() for keyword in gpu_keywords)
        
        return {
            'name_based_classification': 'GPU' if name_based_gpu else 'CPU',
            'matches_explicit': name_based_gpu == self._is_gpu,
            'confidence': 0.8 if name_based_gpu else 0.6
        }

    def get_gpu_usage(self) -> float:
        """
        Tính % GPU usage theo tổng bộ nhớ GPU.

        :return: Tỷ lệ sử dụng GPU (0..100).
        """
        if not self.gpu_manager.gpu_initialized:
            return 0.0
        try:
            total_gpu_memory = self.gpu_manager.get_total_gpu_memory()
            used_gpu_memory = self.gpu_manager.get_used_gpu_memory()
            if total_gpu_memory > 0:
                return (used_gpu_memory / total_gpu_memory) * 100.0
            else:
                self.logger.warning("Tổng bộ nhớ GPU không hợp lệ (=0).")
                return 0.0
        except Exception as e:
            self.logger.error(f"Lỗi khi get_gpu_usage: {e}")
            return 0.0

    def update_resource_usage(self) -> None:
        """
        Cập nhật CPU usage, Memory usage, Disk I/O, Network I/O, GPU usage (nếu có).
        Đồng bộ, không sử dụng async/await.
        """
        try:
            proc = psutil.Process(self.pid)

            # Lấy % CPU (interval=0.1 giây)
            self.cpu_usage = proc.cpu_percent(interval=0.1)
            self.memory_usage = proc.memory_percent()

            io_counters = proc.io_counters()
            self.disk_io = max((io_counters.read_bytes + io_counters.write_bytes) / (1024 * 1024), 0.0)

            net_io_all = psutil.net_io_counters(pernic=True)
            if self.network_interface in net_io_all:
                current_bytes_sent = net_io_all[self.network_interface].bytes_sent
                current_bytes_recv = net_io_all[self.network_interface].bytes_recv

                if self._prev_bytes_sent is not None and self._prev_bytes_recv is not None:
                    sent_diff = max(current_bytes_sent - self._prev_bytes_sent, 0)
                    recv_diff = max(current_bytes_recv - self._prev_bytes_recv, 0)
                    self.network_io = (sent_diff + recv_diff) / (1024 * 1024)
                else:
                    self.network_io = 0.0

                self._prev_bytes_sent = current_bytes_sent
                self._prev_bytes_recv = current_bytes_recv
            else:
                self.logger.warning(
                    f"Giao diện mạng '{self.network_interface}' không tìm thấy cho PID={self.pid}."
                )
                self.network_io = 0.0

            if self.gpu_initialized and self.is_gpu_process():
                self.gpu_usage = self.get_gpu_usage()
            else:
                self.gpu_usage = 0.0

            self.logger.debug(
                f"[MiningProcess update] {self.name} (PID={self.pid}): "
                f"CPU={self.cpu_usage}%, GPU={self.gpu_usage}%, RAM={self.memory_usage}%, "
                f"DiskIO={self.disk_io}MB, NetIO={self.network_io}MB."
            )
        except psutil.NoSuchProcess:
            self.logger.error(f"Tiến trình {self.name} (PID={self.pid}) không tồn tại.")
            self.cpu_usage = self.memory_usage = self.disk_io = self.network_io = self.gpu_usage = 0.0
        except Exception as e:
            self.logger.error(f"Lỗi update_resource_usage PID={self.pid}: {e}")
            self.cpu_usage = self.memory_usage = self.disk_io = self.network_io = self.gpu_usage = 0.0

    def reset_network_io(self) -> None:
        """
        Reset thống kê về Network I/O (bytes_sent, bytes_recv).
        """
        self._prev_bytes_sent = None
        self._prev_bytes_recv = None
        self.network_io = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """
        Trả về dict chứa thông tin resource usage và trạng thái tiến trình.

        :return: Từ điển thông tin (Dict[str, Any]).
        """
        try:
            return {
                'pid': self.pid,
                'name': self.name,
                'priority': int(self.priority) if isinstance(self.priority, int) else 1,
                'cpu_usage_percent': float(self.cpu_usage),
                'memory_usage_percent': float(self.memory_usage),
                'gpu_usage_percent': float(self.gpu_usage),
                'disk_io_mb': float(self.disk_io),
                'network_bandwidth_mb': float(self.network_io),
                'mark': self.mark,
                'network_interface': self.network_interface,
                'is_cloaked': self.is_cloaked
            }
        except Exception as e:
            self.logger.error(f"Lỗi to_dict PID={self.pid}: {e}")
            return {}
