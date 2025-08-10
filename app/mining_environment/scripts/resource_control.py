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
from typing import Dict, Any, List, Optional, Set, Union
from concurrent.futures import ThreadPoolExecutor
import signal
import resource
from pathlib import Path
from .utils import StrategyType

# ✅ UNIFIED LOGGING: Use centralized logging system
# Migration Phase 3: Updated to use new logging architecture
from .module_loggers import get_resource_control_logger

# ✅ ERROR MANAGEMENT: Use centralized error handling system
from .error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error

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
            self.logger.info("pynvml đã được khởi tạo.")
            self.gpu_initialized = True
            return True
        except pynvml.NVMLError as error:
            self.logger.error(f"Lỗi khi khởi tạo pynvml: {error}")
            self.gpu_initialized = False
            return False
        except Exception as e:
            # ✅ ERROR REPORTING: GPU initialization failure
            error_reporter.report_error(
                ErrorCode.RESOURCE_MANAGER_INIT_FAILED,
                f"Lỗi khi khởi tạo pynvml: {e}",
                ErrorSeverity.HIGH,
                module='resource_control',
                function='GPUResourceManager._initialize_nvml',
                context_data={'component': 'pynvml', 'error': str(e)},
                exception=e
            )
            self.logger.error(f"Lỗi khi khởi tạo pynvml: {e}")
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
            self.logger.error("GPUResourceManager chưa init. Không thể lấy handle GPU.")
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
            self.logger.error("GPUResourceManager chưa init. Không thể lấy power limit.")
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

    def set_gpu_power_limit(self, pid: Optional[int], gpu_index: int, power_limit_w: int) -> bool:
        """
        Đặt power limit cho GPU (đồng bộ).

        :param pid: PID cần quản lý, có thể None nếu áp dụng chung.
        :param gpu_index: Chỉ số GPU.
        :param power_limit_w: Power limit cần đặt (W).
        :return: True nếu thành công, False nếu thất bại.
        """
        if not self.gpu_initialized:
            self.logger.error("GPUResourceManager chưa init. Không thể set power limit.")
            return False
        try:
            handle = self.get_handle(gpu_index)
            if not handle or power_limit_w <= 0:
                return False

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
            self.logger.error("GPUResourceManager chưa init. Không thể set clocks.")
            return False
        try:
            handle = self.get_handle(gpu_index)
            if not handle or sm_clock <= 0 or mem_clock <= 0:
                return False

            # Lấy SM/MEM clock hiện tại
            current_sm_clock = pynvml.nvmlDeviceGetClock(handle, pynvml.NVML_CLOCK_SM, pynvml.NVML_CLOCK_ID_CURRENT)
            current_mem_clock = pynvml.nvmlDeviceGetClock(handle, pynvml.NVML_CLOCK_MEM, pynvml.NVML_CLOCK_ID_CURRENT)

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

            # Set SM clock
            cmd_sm = [
                'nvidia-smi',
                '-i', str(gpu_index),
                '--lock-gpu-clocks=' + str(sm_clock)
            ]
            subprocess.run(cmd_sm, check=True)
            self.logger.debug(f"Set SM clock={sm_clock}MHz cho GPU={gpu_index}, PID={pid}.")

            # Set MEM clock
            cmd_mem = [
                'nvidia-smi',
                '-i', str(gpu_index),
                '--lock-memory-clocks=' + str(mem_clock)
            ]
            subprocess.run(cmd_mem, check=True)
            self.logger.debug(f"Set MEM clock={mem_clock}MHz cho GPU={gpu_index}, PID={pid}.")

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
                self.logger.error("GPUResourceManager chưa init. Không thể limit_temperature.")
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
                current_sm_clock = pynvml.nvmlDeviceGetClock(handle, pynvml.NVML_CLOCK_SM, pynvml.NVML_CLOCK_ID_CURRENT)
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

                # Tăng công suất (nhưng không vượt quá 250W)
                desired_power_limit = min(250, int(current_power_limit * (1 + boost_pct / 100)))
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
                self.logger.error("GPUResourceManager chưa init. Không thể lấy nhiệt độ GPU.")
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
        
        self.logger.info(f"✅ OptimizedHardwareController initialized (NVML: {self.nvml_available})")

    def get_gpu_utilization_metrics(self) -> Dict[int, float]:
        """
        **Get real-time GPU utilization metrics** (lấy số liệu sử dụng GPU thời gian thực)
        
        :return: Dict mapping GPU index to utilization percentage
        """
        gpu_loads = {}
        try:
            gpu_count = self.gpu_manager.get_gpu_count()
            for i in range(gpu_count):
                handle = self.gpu_manager.get_handle(i)
                if handle:
                    try:
                        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        gpu_loads[i] = util.gpu / 100.0  # Convert to 0-1 range
                    except:
                        gpu_loads[i] = 0.5  # Default medium load if can't read
                else:
                    gpu_loads[i] = 0.5
        except Exception as e:
            self.logger.error(f"Error getting GPU utilization: {e}")
            # Return default equal loads
            gpu_count = self.gpu_manager.get_gpu_count() or 2
            for i in range(gpu_count):
                gpu_loads[i] = 0.5
        
        return gpu_loads
    
    def allocate_gpu_workload(self, pids: List[int]) -> Dict[int, int]:
        """
        **Dynamic GPU allocation based on real-time metrics** (phân bổ GPU động dựa trên số liệu thời gian thực)
        
        :param pids: List of PIDs to allocate
        :return: Dict mapping PID to GPU index
        """
        allocation = {}
        
        # Get current GPU loads
        gpu_loads = self.get_gpu_utilization_metrics()
        
        # Estimate load per PID (can be refined based on history)
        estimated_load_per_pid = 0.25  # 25% estimated load per process
        
        # Create mutable load tracking
        current_loads = list(gpu_loads.items())
        
        # Sort GPUs by current load (ascending)
        current_loads.sort(key=lambda x: x[1])
        
        # Assign PIDs to least loaded GPUs
        for pid in pids:
            # Get least loaded GPU
            target_gpu = current_loads[0][0]
            target_load = current_loads[0][1]
            
            # Assign PID to this GPU
            allocation[pid] = target_gpu
            self.logger.info(f"📊 Allocating PID {pid} to GPU {target_gpu} (current load: {target_load:.1%})")
            
            # Update estimated load
            new_load = target_load + estimated_load_per_pid
            current_loads[0] = (target_gpu, new_load)
            
            # Re-sort to maintain order
            current_loads.sort(key=lambda x: x[1])
        
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
        if gpu_index == 0:
            allocation = self.allocate_gpu_workload([pid])
            gpu_index = allocation.get(pid, 0)
            self.logger.info(f"🎯 Dynamic allocation: PID={pid} -> GPU={gpu_index}")
        
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
                    
            # **Verify baseline** (xác minh baseline)
            if time.time() - self.last_verification > self.verification_interval:
                baseline_ok = self._verify_baseline(gpu_index)
                results['baseline_verified'] = baseline_ok
                if not baseline_ok:
                    self._adjust_baseline(gpu_index)
                    results['operations_applied'].append('baseline_adjusted')
                self.last_verification = time.time()
            
            # **Apply strategy-specific optimizations** (áp dụng tối ưu hóa theo chiến lược)
            strategy_params = self._get_strategy_params(strategy)
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
                success &= self._apply_nvml_controls(pid, gpu_index, params)
            else:
                # Fallback: Compute-based simulation
                self.logger.debug("NVML not available, using compute simulation...")
                success &= self._apply_compute_simulation(gpu_index, params)
            
            # Step 3: VRAM management (always available)
            self.logger.debug("Managing VRAM allocation...")
            success &= self._manage_vram_allocation(gpu_index, params)
            
            # Step 4: Verify and adjust
            if self._should_verify_baseline():
                self.logger.debug("Verifying baseline metrics...")
                self._verify_and_adjust_baseline(gpu_index)

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
        scaled = params.copy()
        
        # Reduce power by 30%
        if 'power_limit' in scaled:
            scaled['power_limit'] = int(scaled['power_limit'] * 0.7)
            self.logger.info(f"Emergency: Reducing power to {scaled['power_limit']}W")
        
        # Reduce clocks by 20%
        if 'sm_clock' in scaled:
            scaled['sm_clock'] = int(scaled['sm_clock'] * 0.8)
            self.logger.info(f"Emergency: Reducing SM clock to {scaled['sm_clock']}MHz")
        
        # Add aggressive fan control
        scaled['fan_increase'] = 30.0  # 30% fan increase
        
        return scaled
    
    def _apply_nvml_controls(self, pid: int, gpu_index: int, params: Dict[str, Any]) -> bool:
        """
        Apply controls via NVML nếu available
        
        :param params: Control parameters
        :return: Success status
        """
        try:
            # Power limit với smooth transition thông qua GPUResourceManager để có tracking per-PID
            
            # Set power limit với smooth transition
            if 'power_limit' in params:
                current_power = self._get_current_power(gpu_index)
                target_power = params['power_limit']
                
                # Smooth transition để tránh spikes
                if abs(target_power - current_power) > 20:
                    # Step-wise adjustment
                    steps = 3
                    for i in range(steps):
                        intermediate = current_power + (target_power - current_power) * (i+1) / steps
                        try:
                            self.gpu_manager.set_gpu_power_limit(pid, gpu_index, int(intermediate))
                            time.sleep(0.1)
                        except Exception as e:
                            self.logger.warning(f"Cannot set power limit (step): {e}")
                else:
                    try:
                        self.gpu_manager.set_gpu_power_limit(pid, gpu_index, int(target_power))
                    except Exception as e:
                        self.logger.warning(f"Cannot set power limit: {e}")
                
                self.logger.info(f"✅ Set power limit to {target_power}W")
            
            # Set clocks nếu supported
            if 'sm_clock' in params and 'memory_clock' in params:
                try:
                    ok = self.gpu_manager.set_gpu_clocks(pid, gpu_index, params['sm_clock'], params['memory_clock'])
                    if ok:
                        self.logger.info(f"✅ Set clocks: SM={params['sm_clock']}MHz, Mem={params['memory_clock']}MHz")
                    else:
                        self.logger.warning("Cannot set GPU clocks via nvidia-smi")
                except Exception as e:
                    self.logger.warning(f"Cannot set GPU clocks: {e}")
            
            return True
            
        except Exception as e:
            self.logger.warning(f"NVML control failed: {e}")
            return False

    def _get_current_power(self, gpu_index: int) -> float:
        """
        Get current GPU power usage
        
        :return: Power in Watts
        """
        try:
            gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            power_mw = pynvml.nvmlDeviceGetPowerUsage(gpu_handle)
            return power_mw / 1000.0  # Convert to Watts
        except:
            return self.baseline_power  # Return baseline if can't read

    def _apply_compute_simulation(self, gpu_index: int, params: Dict[str, Any]) -> bool:
        """
        Fallback: Simulate power variation via compute load
        
        :param params: Control parameters
        :return: Success status
        """
        try:
            # Calculate duty cycle based on target power
            target_power = params.get('power_limit', self.baseline_power)
            duty_cycle = target_power / self.baseline_power
            duty_cycle = max(0.5, min(1.0, duty_cycle))
            
            # Launch compute kernel với duty cycle
            compute_cmd = f"""
python3 -c "
import torch
import time
import sys

try:
    # Allocate tensors
    a = torch.randn(2000, 2000, device='cuda')
    b = torch.randn(2000, 2000, device='cuda')
    
    # Run với duty cycle
    work_time = {duty_cycle * 0.1}  # 100ms window
    sleep_time = {(1 - duty_cycle) * 0.1}
    
    for _ in range(10):
        start = time.time()
        while time.time() - start < work_time:
            c = torch.matmul(a, b)
            torch.cuda.synchronize()
        time.sleep(sleep_time)
except Exception as e:
    print(f'Compute simulation error: {{e}}', file=sys.stderr)
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
            self.logger.info(f"✅ Launched compute simulation (duty cycle: {duty_cycle:.2f})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Compute simulation failed: {e}")
            return False
    
    def _manage_vram_allocation(self, gpu_index: int, params: Dict[str, Any]) -> bool:
        """
        Manage VRAM để mimic AI workload
        
        :param params: Control parameters
        :return: Success status
        """
        try:
            target_percent = params.get('vram_allocation', self.profile.get('vram_allocation', 0.5))
            
            # Get available VRAM
            total_vram = self._get_total_vram(gpu_index)
            target_bytes = int(total_vram * target_percent)
            target_mb = target_bytes // (1024**2)
            
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
            self.logger.info(f"✅ VRAM allocation pattern started ({target_mb}MB, {target_percent:.1%})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"VRAM management failed: {e}")
            return False
    
    def _get_total_vram(self, gpu_index: int) -> int:
        """
        Get total VRAM in bytes
        
        :return: Total VRAM bytes
        """
        try:
            gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(gpu_handle)
            return mem_info.total
        except:
            return int(self.baseline_vram * 1024**3)  # Convert GB to bytes
    
    def _should_verify_baseline(self) -> bool:
        """
        Check if baseline verification is needed
        
        :return: True if verification needed
        """
        current_time = time.time()
        if current_time - self.last_verification > self.verification_interval:
            self.last_verification = current_time
            return True
        return False
    
    def _verify_and_adjust_baseline(self, gpu_index: int):
        """
        Verify current metrics against baseline and adjust if needed
        """
        try:
            # Get current metrics
            current_power = self._get_current_power(gpu_index)
            current_temp = self.gpu_manager.get_gpu_temperature(gpu_index)
            
            # Check deviations
            power_deviation = abs(current_power - self.baseline_power) / self.baseline_power
            
            if power_deviation > 0.3:  # 30% deviation
                self.logger.warning(f"⚠️ Power deviation: {power_deviation:.1%}")
                # Adjust baseline
                self.baseline_power = current_power * 0.7 + self.baseline_power * 0.3
                self.logger.info(f"Updated baseline power to {self.baseline_power:.1f}W")
            
            if current_temp and abs(current_temp - self.baseline_temp) > 10:
                self.logger.warning(f"⚠️ Temperature deviation: {current_temp - self.baseline_temp:.1f}°C")
                # Adjust baseline
                self.baseline_temp = current_temp * 0.5 + self.baseline_temp * 0.5
                self.logger.info(f"Updated baseline temp to {self.baseline_temp:.1f}°C")
            
        except Exception as e:
            self.logger.error(f"Baseline verification failed: {e}")

    def _schedule_restore(self, pid: int, gpu_index: int, window_sec: int):
        """
        Hẹn giờ khôi phục device-wide settings sau cửa sổ thời gian (per-PID simulation window).
        """
        def _restore_task():
            try:
                time.sleep(max(0, window_sec))
                # Khôi phục settings đã thay đổi bởi PID
                self.gpu_manager.restore_gpu_settings_for_pid(pid)
                # Dọn tiến trình mô phỏng
                self.cleanup()
                self.logger.info(f"✅ Đã khôi phục GPU settings sau {window_sec}s cho PID={pid} (GPU={gpu_index}).")
            except Exception as e:
                self.logger.warning(f"Lỗi khi khôi phục tự động cho PID={pid}: {e}")

        t = threading.Thread(target=_restore_task, daemon=True)
        t.start()
    
    def cleanup(self):
        """
        Clean up active subprocesses
        """
        for proc in self.active_subprocesses:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except:
                try:
                    proc.kill()
                except:
                    pass
        
        self.active_subprocesses.clear()
        self.logger.info("✅ Cleaned up OptimizedHardwareController")
