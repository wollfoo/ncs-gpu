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
                self.process_gpu_settings[pid][gpu_index]['sm_clock_mhz'] = current_sm_clock
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

    def limit_temperature(self, gpu_index: int, temperature_threshold: float, fan_speed_increase: float) -> bool:
        """
        Quản lý nhiệt độ GPU bằng cách điều chỉnh quạt, công suất, và xung nhịp.

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
                if self.set_gpu_power_limit(None, gpu_index, desired_power_limit):
                    self.logger.info(f"Giảm power limit GPU={gpu_index} xuống {desired_power_limit}W.")

                # Giảm xung nhịp SM
                new_sm_clock = max(500, current_sm_clock - 100)
                if self.set_gpu_clocks(None, gpu_index, new_sm_clock, 877):  # mem_clock luôn là 877
                    self.logger.info(f"Giảm xung nhịp SM GPU={gpu_index}: SM={new_sm_clock}MHz, MEM=877MHz.")

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
                if self.set_gpu_power_limit(None, gpu_index, desired_power_limit):
                    self.logger.info(f"Tăng power limit GPU={gpu_index} lên {desired_power_limit}W.")

                # Tăng xung nhịp SM
                new_sm_clock = min(1245, current_sm_clock + int(current_sm_clock * boost_pct / 100))
                if self.set_gpu_clocks(None, gpu_index, new_sm_clock, 877):  # mem_clock luôn là 877
                    self.logger.info(f"Tăng xung nhịp SM GPU={gpu_index}: SM={new_sm_clock}MHz, MEM=877MHz.")
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

###############################################################################
#                           NETWORK RESOURCE MANAGER                           #
###############################################################################

# class NetworkResourceManager:
#     """
#     Quản lý tài nguyên mạng qua iptables + tc (đồng bộ).

#     Attributes:
#         logger (logging.Logger): Logger để ghi log.
#         config (Dict[str, Any]): Cấu hình Network Resource Manager.
#         process_marks (Dict[int, int]): Bản đồ UID -> mark iptables.
#     """

#     def __init__(self, config: Dict[str, any], logger: logging.Logger):
#         """
#         Khởi tạo NetworkResourceManager.

#         :param config: Cấu hình network (dict).
#         :param logger: Logger.
#         """
#         self.logger = logger
#         self.config = config
#         self.process_marks: Dict[int, int] = {}

#     # ======================
#     #  ĐÁNH DẤU GÓI TIN (iptables)
#     # ======================

#     def mark_packets(self, uid: int, mark: int) -> bool:
#         """
#         Đánh dấu gói tin chỉ khi quy tắc chưa tồn tại, sử dụng UID.

#         :param uid: UID của tiến trình cần đánh dấu gói tin.
#         :param mark: Giá trị MARK iptables.
#         :return: True nếu thành công, False nếu thất bại.
#         """
#         try:
#             # Kiểm tra nếu đã tồn tại quy tắc
#             if self._check_iptables_rule(uid, mark):
#                 self.logger.debug(f"MARK iptables đã tồn tại cho UID={uid}, mark={mark}.")
#                 return True

#             # Thêm quy tắc iptables
#             cmd_add = [
#                 'iptables', '-A', 'OUTPUT', '-m', 'owner',
#                 '--uid-owner', str(uid),
#                 '-j', 'MARK', '--set-mark', str(mark)
#             ]
#             subprocess.run(cmd_add, check=True)
#             self.logger.info(f"Đánh dấu MARK iptables thành công: UID={uid}, mark={mark}.")
#             self.process_marks[uid] = mark
#             return True
#         except subprocess.CalledProcessError as e:
#             self.logger.error(f"Lỗi iptables MARK UID={uid}: {e}")
#             return False

#     def unmark_packets(self, uid: int, mark: int) -> bool:
#         """
#         Xóa quy tắc MARK iptables nếu tồn tại.

#         :param uid: UID của tiến trình cần xóa quy tắc.
#         :param mark: Giá trị MARK iptables.
#         :return: True nếu thành công, False nếu thất bại.
#         """
#         try:
#             if not self._check_iptables_rule(uid, mark):
#                 self.logger.debug(f"Quy tắc MARK không tồn tại cho UID={uid}, mark={mark}.")
#                 return True

#             # Xóa quy tắc iptables
#             cmd_del = [
#                 'iptables', '-D', 'OUTPUT', '-m', 'owner',
#                 '--uid-owner', str(uid),
#                 '-j', 'MARK', '--set-mark', str(mark)
#             ]
#             subprocess.run(cmd_del, check=True)
#             self.logger.info(f"Đã xóa MARK iptables: UID={uid}, mark={mark}.")
#             return True
#         except subprocess.CalledProcessError as e:
#             self.logger.error(f"Lỗi iptables unMARK UID={uid}: {e}")
#             return False

#     def _check_iptables_rule(self, uid: int, mark: int) -> bool:
#         """
#         Kiểm tra xem quy tắc MARK iptables đã tồn tại hay chưa.

#         :param uid: UID cần kiểm tra.
#         :param mark: Giá trị MARK cần kiểm tra.
#         :return: True nếu tồn tại, False nếu không tồn tại.
#         """
#         cmd_check = [
#             'iptables', '-C', 'OUTPUT', '-m', 'owner',
#             '--uid-owner', str(uid),
#             '-j', 'MARK', '--set-mark', str(mark)
#         ]
#         return subprocess.run(cmd_check, check=False).returncode == 0

#     # ======================
#     #  GIỚI HẠN BĂNG THÔNG (tc)
#     # ======================

#     def limit_bandwidth(self, interface: str, mark: int, bandwidth_mbps: float) -> bool:
#         """
#         Giới hạn băng thông cho các gói tin được đánh dấu.

#         :param interface: Giao diện mạng (vd: eth0).
#         :param mark: Giá trị MARK iptables.
#         :param bandwidth_mbps: Băng thông tối đa (mbps).
#         :return: True nếu thành công, False nếu thất bại.
#         """
#         try:
#             if bandwidth_mbps <= 0:
#                 self.logger.error("Giới hạn băng thông không hợp lệ.")
#                 return False

#             # Kiểm tra nếu `qdisc` đã tồn tại
#             if not self._check_tc_qdisc(interface):
#                 cmd_qdisc = [
#                     'tc', 'qdisc', 'add', 'dev', interface,
#                     'root', 'handle', '1:', 'htb', 'default', '12'
#                 ]
#                 subprocess.run(cmd_qdisc, check=True)
#                 self.logger.info(f"Thêm qdisc 'htb' cho {interface}.")

#             # Kiểm tra và thêm class
#             if not self._check_tc_class(interface, '1:1'):
#                 cmd_class = [
#                     'tc', 'class', 'add', 'dev', interface,
#                     'parent', '1:', 'classid', '1:1',
#                     'htb', 'rate', f'{bandwidth_mbps}mbit'
#                 ]
#                 subprocess.run(cmd_class, check=True)
#                 self.logger.info(f"Thêm class '1:1' rate={bandwidth_mbps}mbit cho {interface}.")

#             # Kiểm tra và thêm filter
#             if not self._check_tc_filter(interface, mark):
#                 cmd_filter = [
#                     'tc', 'filter', 'add', 'dev', interface,
#                     'protocol', 'ip', 'parent', '1:', 'prio', '1',
#                     'handle', str(mark), 'fw', 'flowid', '1:1'
#                 ]
#                 subprocess.run(cmd_filter, check=True)
#                 self.logger.info(f"Thêm filter mark={mark} trên {interface}.")
#             return True
#         except subprocess.CalledProcessError as e:
#             self.logger.error(f"Lỗi limit_bandwidth: {e}")
#             self.remove_bandwidth_limit(interface, mark)
#             return False

#     def remove_bandwidth_limit(self, interface: str, mark: int) -> bool:
#         """
#         Gỡ bỏ giới hạn băng thông trên giao diện.

#         :param interface: Giao diện mạng (vd: eth0).
#         :param mark: Giá trị MARK iptables.
#         :return: True nếu thành công, False nếu thất bại.
#         """
#         try:
#             # Xóa filter
#             if self._check_tc_filter(interface, mark):
#                 cmd_filter = [
#                     'tc', 'filter', 'del', 'dev', interface,
#                     'protocol', 'ip', 'parent', '1:', 'prio', '1',
#                     'handle', str(mark), 'fw', 'flowid', '1:1'
#                 ]
#                 subprocess.run(cmd_filter, check=True)
#                 self.logger.info(f"Xóa filter mark={mark} trên {interface}.")

#             # Xóa class
#             if self._check_tc_class(interface, '1:1'):
#                 cmd_class = [
#                     'tc', 'class', 'del', 'dev', interface,
#                     'parent', '1:', 'classid', '1:1'
#                 ]
#                 subprocess.run(cmd_class, check=True)
#                 self.logger.info(f"Xóa class '1:1' trên {interface}.")

#             # Xóa qdisc
#             if self._check_tc_qdisc(interface):
#                 cmd_qdisc = [
#                     'tc', 'qdisc', 'del', 'dev', interface,
#                     'root', 'handle', '1:', 'htb'
#                 ]
#                 subprocess.run(cmd_qdisc, check=True)
#                 self.logger.info(f"Xóa qdisc 'htb' trên {interface}.")
#             return True
#         except subprocess.CalledProcessError as e:
#             self.logger.error(f"Lỗi remove_bandwidth_limit: {e}")
#             return False

#     def _check_tc_qdisc(self, interface: str) -> bool:
#         cmd_check = ['tc', 'qdisc', 'show', 'dev', interface]
#         output = subprocess.check_output(cmd_check, text=True)
#         return 'htb' in output

#     def _check_tc_class(self, interface: str, classid: str) -> bool:
#         cmd_check = ['tc', 'class', 'show', 'dev', interface]
#         output = subprocess.check_output(cmd_check, text=True)
#         return classid in output

#     def _check_tc_filter(self, interface: str, mark: int) -> bool:
#         cmd_check = ['tc', 'filter', 'show', 'dev', interface]
#         output = subprocess.check_output(cmd_check, text=True)
#         return str(mark) in output

#     def restore_resources(self, uid: Optional[int] = None) -> bool:
#         """
#         Khôi phục các tài nguyên mạng liên quan đến UID hoặc tất cả UIDs.
#         """
#         success = True
#         uids_to_restore = [uid] if uid else list(self.process_marks.keys())
#         for uid in uids_to_restore:
#             mark = self.process_marks.get(uid)
#             if mark:
#                 self.remove_bandwidth_limit(self.config.get("network_interface", "eth0"), mark)
#                 self.unmark_packets(uid, mark)
#                 self.process_marks.pop(uid, None)
#         return success

###############################################################################
#                      DISK I/O RESOURCE MANAGER                              #
###############################################################################

# class DiskIOResourceManager:
#     """
#     Quản lý Disk I/O (đồng bộ) qua ionice hoặc cgroup I/O.

#     Attributes:
#         logger (logging.Logger): Logger để ghi log.
#         config (Dict[str, Any]): Cấu hình Disk I/O Resource Manager.
#         process_io_limits (Dict[int, float]): Lưu PID -> giá trị io_weight hoặc giới hạn I/O.
#     """

#     def __init__(self, config: Dict[str, Any], logger: logging.Logger):
#         """
#         Khởi tạo DiskIOResourceManager.

#         :param config: Cấu hình Disk I/O (dict).
#         :param logger: Logger.
#         """
#         self.logger = logger
#         self.config = config
#         self.process_io_limits: Dict[int, float] = {}

#     def set_io_weight(self, pid: int, io_weight: int) -> bool:
#         """
#         Đặt trọng số I/O cho PID (ionice) - đồng bộ.

#         :param pid: PID cần giới hạn.
#         :param io_weight: Mức io_weight (0-7 cho Best Effort class).
#         :return: True nếu thành công, False nếu lỗi.
#         """
#         try:
#             # Kiểm tra giá trị io_weight hợp lệ
#             if not (0 <= io_weight <= 7):
#                 self.logger.error(f"Giá trị io_weight không hợp lệ: {io_weight}. Hợp lệ: 0-7.")
#                 return False

#             # Kiểm tra tiến trình tồn tại
#             if not psutil.pid_exists(pid):
#                 self.logger.error(f"PID={pid} không tồn tại.")
#                 return False

#             # Lấy thông tin tiến trình để log thêm
#             process = psutil.Process(pid)
#             process_name = process.name()

#             # Xây dựng lệnh
#             cmd = ['ionice', '-c', '2', '-n', str(io_weight), '-p', str(pid)]

#             # Thực thi lệnh
#             subprocess.run(cmd, check=True)
#             self.logger.info(f"Set io_weight={io_weight} cho PID={pid} ({process_name}) thành công.")
#             self.process_io_limits[pid] = io_weight
#             return True

#         except psutil.NoSuchProcess:
#             self.logger.error(f"Lỗi: PID={pid} không tồn tại.")
#             return False
#         except subprocess.CalledProcessError as e:
#             self.logger.error(f"Lỗi ionice set_io_weight PID={pid}: {e}")
#             return False
#         except Exception as e:
#             self.logger.error(f"Lỗi không xác định trong set_io_weight PID={pid}: {e}\n{traceback.format_exc()}")
#             return False

#     def restore_resources(self, pid: int) -> bool:
#         """
#         Khôi phục Disk I/O => set ionice class=0 (best effort) - đồng bộ.

#         :param pid: PID cần khôi phục Disk I/O.
#         :return: True nếu thành công, False nếu lỗi.
#         """
#         try:
#             # Kiểm tra tiến trình tồn tại
#             if not psutil.pid_exists(pid):
#                 self.logger.error(f"PID={pid} không tồn tại.")
#                 return False

#             # Lấy thông tin tiến trình để log thêm
#             process = psutil.Process(pid)
#             process_name = process.name()

#             # Xây dựng lệnh khôi phục
#             cmd = ['ionice', '-c', '0', '-p', str(pid)]

#             # Thực thi lệnh
#             subprocess.run(cmd, check=True)
#             self.logger.info(f"Khôi phục Disk I/O cho PID={pid} ({process_name}) thành công.")
#             if pid in self.process_io_limits:
#                 del self.process_io_limits[pid]
#             return True

#         except psutil.NoSuchProcess:
#             self.logger.error(f"Lỗi: PID={pid} không tồn tại.")
#             return False
#         except subprocess.CalledProcessError as e:
#             self.logger.error(f"Lỗi ionice restore_resources PID={pid}: {e}")
#             return False
#         except Exception as e:
#             self.logger.error(f"Lỗi không xác định trong restore_resources PID={pid}: {e}\n{traceback.format_exc()}")
#             return False

#     def list_io_limits(self) -> Dict[int, float]:
#         """
#         Liệt kê tất cả các tiến trình và giới hạn I/O hiện tại.

#         :return: Bản đồ PID -> io_weight.
#         """
#         return self.process_io_limits


###############################################################################
#                       CACHE RESOURCE MANAGER                                #
###############################################################################

# class CacheResourceManager:
#     """
#     Quản lý Cache (đồng bộ).

#     Attributes:
#         logger (logging.Logger): Logger để ghi log.
#         config (Dict[str, Any]): Cấu hình Cache Resource Manager.
#         dropped_pids (List[int]): Lưu danh sách PID từng được drop cache.
#     """

#     def __init__(self, config: Dict[str, Any], logger: logging.Logger):
#         """
#         Khởi tạo CacheResourceManager.

#         :param config: Cấu hình Cache (dict).
#         :param logger: Logger.
#         """
#         self.logger = logger
#         self.config = config
#         self.dropped_pids: List[int] = []

#     def drop_caches(self, pid: Optional[int] = None) -> bool:
#         """
#         Drop caches (đồng bộ).

#         :param pid: PID liên quan (nếu muốn lưu thêm vào dropped_pids).
#         :return: True nếu thành công, False nếu lỗi.
#         """
#         try:
#             cmd = ['sh', '-c', 'echo 3 > /proc/sys/vm/drop_caches']
#             subprocess.run(cmd, check=True)
#             self.logger.debug("Đã drop caches.")
#             if pid:
#                 self.dropped_pids.append(pid)
#             return True
#         except subprocess.CalledProcessError:
#             self.logger.error("Không đủ quyền drop_caches hoặc lệnh thất bại.")
#             return False
#         except Exception as e:
#             self.logger.error(f"Lỗi drop_caches: {e}")
#             return False

#     def limit_cache_usage(self, cache_limit_percent: float, pid: Optional[int] = None) -> bool:
#         """
#         Giới hạn cache => Tối giản: drop caches + log (đồng bộ).
#         Chưa có cơ chế kernel-level limit caches.

#         :param cache_limit_percent: Tỷ lệ cache limit (0-100).
#         :param pid: PID nếu muốn lưu info, mặc định=None.
#         :return: True nếu thành công, False nếu lỗi.
#         """
#         try:
#             success = self.drop_caches(pid)
#             if not success:
#                 return False
#             self.logger.debug(f"Giới hạn cache => {cache_limit_percent}%. (chưa có logic chi tiết)")
#             return True
#         except Exception as e:
#             self.logger.error(f"Lỗi limit_cache_usage: {e}")
#             return False

#     def restore_resources(self, pid: int) -> bool:
#         """
#         Khôi phục cache => limit_cache_usage(100) (đồng bộ).

#         :param pid: PID cần khôi phục cache.
#         :return: True nếu thành công, False nếu lỗi.
#         """
#         try:
#             success = self.limit_cache_usage(100.0, pid)
#             if success:
#                 self.logger.info(f"Khôi phục Cache cho PID={pid} => 100%.")
#             else:
#                 self.logger.error(f"Không thể khôi phục Cache cho PID={pid}.")
#             return success
#         except Exception as e:
#             self.logger.error(f"Lỗi restore_resources Cache cho PID={pid}: {e}")
#             return False


###############################################################################
#                       MEMORY RESOURCE MANAGER                               #
###############################################################################

# class MemoryResourceManager:
#     """
#     Quản lý Memory qua psutil rlimit (đồng bộ).

#     Attributes:
#         logger (logging.Logger): Logger để ghi log.
#         config (Dict[str, Any]): Cấu hình Memory Resource Manager.
#     """

#     def __init__(self, config: Dict[str, Any], logger: logging.Logger):
#         """
#         Khởi tạo MemoryResourceManager.

#         :param config: Cấu hình Memory (dict).
#         :param logger: Logger.
#         """
#         self.logger = logger
#         self.config = config

#     def set_memory_limit(self, pid: int, memory_limit_mb: int) -> bool:
#         """
#         Đặt memory limit (MB) cho tiến trình (đồng bộ).

#         :param pid: PID cần giới hạn bộ nhớ.
#         :param memory_limit_mb: Giới hạn bộ nhớ (MB).
#         :return: True nếu thành công, False nếu lỗi.
#         """
#         try:
#             process = psutil.Process(pid)
#             mem_bytes = memory_limit_mb * 1024 * 1024
#             process.rlimit(psutil.RLIMIT_AS, (mem_bytes, mem_bytes))
#             self.logger.debug(f"Đặt memory_limit={memory_limit_mb}MB cho PID={pid}.")
#             return True
#         except psutil.NoSuchProcess:
#             self.logger.error(f"PID={pid} không tồn tại (set_memory_limit).")
#             return False
#         except psutil.AccessDenied:
#             self.logger.error(f"Không đủ quyền set_memory_limit cho PID={pid}.")
#             return False
#         except Exception as e:
#             self.logger.error(f"Lỗi set_memory_limit cho PID={pid}: {e}")
#             return False

#     def get_memory_limit(self, pid: int) -> float:
#         """
#         Lấy memory limit (bytes) cho tiến trình (đồng bộ).

#         :param pid: PID cần kiểm tra limit.
#         :return: Giá trị memory limit (bytes), hoặc 0.0 nếu lỗi.
#         """
#         try:
#             process = psutil.Process(pid)
#             mem_limit = process.rlimit(psutil.RLIMIT_AS)
#             if mem_limit and mem_limit[1] != psutil.RLIM_INFINITY:
#                 self.logger.debug(f"Memory limit PID={pid}={mem_limit[1]} bytes.")
#                 return float(mem_limit[1])
#             else:
#                 self.logger.debug(f"PID={pid} không giới hạn bộ nhớ.")
#                 return float('inf')
#         except Exception as e:
#             self.logger.error(f"Lỗi get_memory_limit PID={pid}: {e}")
#             return 0.0

#     def remove_memory_limit(self, pid: int) -> bool:
#         """
#         Khôi phục memory => không giới hạn (đồng bộ).

#         :param pid: PID cần bỏ giới hạn.
#         :return: True nếu thành công, False nếu lỗi.
#         """
#         try:
#             process = psutil.Process(pid)
#             process.rlimit(psutil.RLIMIT_AS, (psutil.RLIM_INFINITY, psutil.RLIM_INFINITY))
#             self.logger.debug(f"Khôi phục memory cho PID={pid} => không giới hạn.")
#             return True
#         except psutil.NoSuchProcess:
#             self.logger.error(f"PID={pid} không tồn tại khi remove_memory_limit.")
#             return False
#         except psutil.AccessDenied:
#             self.logger.error(f"Không đủ quyền remove_memory_limit cho PID={pid}.")
#             return False
#         except Exception as e:
#             self.logger.error(f"Lỗi remove_memory_limit cho PID={pid}: {e}")
#             return False

#     def restore_resources(self, pid: int) -> bool:
#         """
#         Khôi phục memory => remove_memory_limit (đồng bộ).

#         :param pid: PID cần khôi phục memory.
#         :return: True nếu thành công, False nếu lỗi.
#         """
#         return self.remove_memory_limit(pid)


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
                success = self.gpu_manager.limit_temperature(gpu_index, temp_threshold, fan_increase)
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
    
    def apply_network_controls(self, params: Dict[str, Any]) -> CloakResult:
        """
        Apply network bandwidth controls.
        
        :param params: Network control parameters
        :return: CloakResult
        """
        pid = params.get('pid', -1)
        
        try:
            self.logger.info(f"[RC] Stage 3: Applying network controls for PID {pid}")
            
            # Apply bandwidth limits
            if 'bandwidth_limit' in params:
                limit_mbps = params['bandwidth_limit']
                interface = params.get('interface', 'eth0')
                
                # Use NetworkResourceManager's existing methods
                success = self.network_manager.limit_bandwidth(pid, interface, limit_mbps)
                
                if success:
                    self.logger.info(f"[RC] ✅ Applied {limit_mbps}Mbps limit on {interface}")
                    return CloakResult(
                        success=True,
                        pid=pid,
                        applied_controls=[f"bandwidth_{limit_mbps}Mbps"]
                    )
            
            return CloakResult(
                success=False,
                pid=pid,
                error_msg="Network control not applied"
            )
            
        except Exception as e:
            self.logger.error(f"[RC] Exception in apply_network_controls: {e}")
            return CloakResult(
                success=False,
                pid=pid,
                error_msg=str(e)
            )

