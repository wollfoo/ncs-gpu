"""
Direct PID Registry Access System
=================================

Direct registry access pattern replacing EventBus with direct function calls
for improved performance and simplicity.

Key features:
- Thread-safe operations with RLock protection
- Observer pattern with plugin auto-discovery
- Centralized registry as single source of truth
- Immediate notifications via direct callbacks

Usage:
    registry = get_direct_registry()
    registry.register_process(pid, "gpu", process_obj, "inference-cuda")
"""

import threading
import time
import logging
import psutil
import os
import json
import uuid
import fcntl
from pathlib import Path
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field

# Setup logger
logger = logging.getLogger("direct_pid_registry")

# Configuration management
class RegistryConfig:
    """Registry configuration class with centralized settings for all operations"""
    # File-based registry settings
    FILE_REGISTRY_DIR = Path("/tmp/ncs_pid_registry")
    REGISTRY_FILE_PREFIX = "pid_"
    REGISTRY_FILE_SUFFIX = ".json"
    REGISTRY_CLEANUP_AGE = 3600  # 1 hour in seconds
    
    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 0.5  # 500ms
    BACKOFF_MULTIPLIER = 1.5
    
    # Priority configuration
    HIGH_PRIORITY_KEYWORDS = {'inference', 'cuda', 'ml'}
    DEFAULT_PRIORITY = 2
    PRIORITY_RANGE = (1, 10)
    
    # Performance settings
    CLEANUP_INTERVAL = 60  # seconds
    DEFAULT_WAIT_TIMEOUT = 5.0  # seconds

def _ensure_file_registry_dir() -> bool:
    """Ensure file registry directory exists with proper permissions"""
    try:
        RegistryConfig.FILE_REGISTRY_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
        
        # Verify directory permissions
        if not RegistryConfig.FILE_REGISTRY_DIR.is_dir():
            logger.error(f"❌ [FILE-REGISTRY] Directory creation failed: {RegistryConfig.FILE_REGISTRY_DIR}")
            return False
        
        # Test write permissions
        test_file = RegistryConfig.FILE_REGISTRY_DIR / f".test_{uuid.uuid4().hex[:8]}"
        try:
            test_file.write_text("test")
            test_file.unlink()
            logger.debug(f"✅ [FILE-REGISTRY] Directory ready: {RegistryConfig.FILE_REGISTRY_DIR}")
            return True
        except Exception as perm_err:
            logger.error(f"❌ [FILE-REGISTRY] Directory not writable: {perm_err}")
            return False
            
    except Exception as e:
        logger.error(f"❌ [FILE-REGISTRY] Failed to ensure directory: {e}")
        return False

def _write_pid_file_atomic(pid: int, metadata: Dict[str, Any]) -> bool:
    """Atomic PID file write with race condition prevention"""
    try:
        if not _ensure_file_registry_dir():
            return False
        
        # Create unique temporary filename
        temp_file = RegistryConfig.FILE_REGISTRY_DIR / f".tmp_{pid}_{uuid.uuid4().hex[:8]}"
        final_file = RegistryConfig.FILE_REGISTRY_DIR / f"{RegistryConfig.REGISTRY_FILE_PREFIX}{pid}{RegistryConfig.REGISTRY_FILE_SUFFIX}"
        
        # Prepare file data
        file_data = {
            'pid': pid,
            'timestamp': time.time(),
            'metadata': metadata,
            'registry_id': uuid.uuid4().hex,
            'created_by': 'DirectPIDRegistry',
            'version': '1.0'
        }
        
        # Atomic write operation
        with open(temp_file, 'w') as f:
            # File locking to ensure atomicity
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(file_data, f, indent=2)
            f.flush()  # Force write to disk
            os.fsync(f.fileno())  # Force OS buffer flush
        
        # Atomic move to final location
        temp_file.rename(final_file)
        
        logger.info(f"FILE-REGISTRY: Atomic write successful: PID={pid}, File={final_file.name}")
        return True
        
    except Exception as e:
        logger.error(f"FILE-REGISTRY: Atomic write failed for PID {pid}: {e}")
        # Cleanup temp file if exists
        try:
            if 'temp_file' in locals() and temp_file.exists():
                temp_file.unlink()
        except Exception as cleanup_err:
            logger.debug(f"Could not cleanup temp file: {cleanup_err}")
        return False

def _cleanup_old_pid_files() -> int:
    """
    **Cleanup Old PID Files** (dọn dẹp file PID cũ)
    
    Remove files older than REGISTRY_CLEANUP_AGE seconds.
    
    Returns:
        int: Number of files cleaned up
    """
    try:
        if not RegistryConfig.FILE_REGISTRY_DIR.exists():
            return 0
        
        current_time = time.time()
        cleanup_count = 0
        
        for file_path in RegistryConfig.FILE_REGISTRY_DIR.glob(f"{RegistryConfig.REGISTRY_FILE_PREFIX}*{RegistryConfig.REGISTRY_FILE_SUFFIX}"):
            try:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > RegistryConfig.REGISTRY_CLEANUP_AGE:
                    file_path.unlink()
                    cleanup_count += 1
                    logger.debug(f"🧹 [FILE-CLEANUP] Removed old file: {file_path.name} (age: {file_age:.1f}s)")
            except Exception as file_err:
                logger.debug(f"⚠️ [FILE-CLEANUP] Could not process file {file_path.name}: {file_err}")
        
        if cleanup_count > 0:
            logger.info(f"🧹 [FILE-CLEANUP] Cleaned up {cleanup_count} old PID files")
        
        return cleanup_count
        
    except Exception as e:
        logger.error(f"❌ [FILE-CLEANUP] Cleanup failed: {e}")
        return 0

# **Common Helper Methods** (các phương thức trợ giúp chung)
def _setup_module_path(module_path: str, module_name: str) -> bool:
    """
    **Setup Module Import Path** (thiết lập đường dẫn nhập module)
    
    Helper method để setup import path cho dynamic module imports.
    
    Args:
        module_path: Đường dẫn tới module directory
        module_name: Tên module để import
        
    Returns:
        bool: True nếu setup thành công
    """
    try:
        import sys
        from pathlib import Path
        
        # **Calculate full module path** (tính toán đường dẫn module đầy đủ)
        full_path = Path(__file__).parent.parent / module_path
        
        # **Add to sys.path if not already present** (thêm vào sys.path nếu chưa có)
        path_str = str(full_path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            logger.debug(f"✅ [MODULE-SETUP] Added path: {path_str} for {module_name}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ [MODULE-SETUP] Failed to setup path for {module_name}: {e}")
        return False

def _build_enhanced_metadata(base: Dict[str, Any], additional: Dict[str, Any]) -> Dict[str, Any]:
    """
    **Build Enhanced Metadata** (xây dựng metadata nâng cao)
    
    Helper method để combine và enhance metadata objects.
    
    Args:
        base: Base metadata dictionary
        additional: Additional metadata to merge
        
    Returns:
        Dict[str, Any]: Enhanced metadata dictionary
    """
    try:
        # **Create enhanced metadata** (tạo metadata nâng cao)
        enhanced = {
            **base,  # Include all base metadata
            **additional,  # Overlay additional metadata
            'enhanced_timestamp': time.time(),
            'metadata_version': '2.0',
            'source_chain': base.get('source_chain', []) + additional.get('source_chain', [])
        }
        
        # **Deduplicate source chain** (loại bỏ trùng lặp trong source chain)
        if 'source_chain' in enhanced:
            enhanced['source_chain'] = list(dict.fromkeys(enhanced['source_chain']))  # Preserve order, remove duplicates
        
        logger.debug(f"✅ [METADATA] Enhanced metadata created with {len(enhanced)} fields")
        return enhanced
        
    except Exception as e:
        logger.error(f"❌ [METADATA] Failed to build enhanced metadata: {e}")
        return {**base, **additional}  # Fallback to simple merge

def _log_operation_result(operation: str, success: bool, details: Dict[str, Any]) -> None:
    """
    **Log Operation Result** (ghi log kết quả thao tác)
    
    Standardized logging cho operation results với consistent format.
    
    Args:
        operation: Tên operation
        success: Kết quả thành công/thất bại
        details: Chi tiết thêm về operation
    """
    try:
        # **Extract common details** (trích xuất chi tiết chung)
        pid = details.get('pid', 'unknown')
        duration = details.get('duration')
        attempt = details.get('attempt', 1)
        
        # **Format status symbol** (định dạng biểu tượng trạng thái)
        status_symbol = "✅" if success else "❌"
        status_text = "successful" if success else "failed"
        
        # **Build log message** (xây dựng thông điệp log)
        message_parts = [f"{status_symbol} [{operation.upper()}] {operation} {status_text}"]
        
        if pid != 'unknown':
            message_parts.append(f"PID={pid}")
        
        if attempt > 1:
            message_parts.append(f"attempt {attempt}")
            
        if duration is not None:
            message_parts.append(f"duration: {duration:.3f}s")
        
        # **Additional context** (ngữ cảnh thêm)
        context_items = []
        for key, value in details.items():
            if key not in ['pid', 'duration', 'attempt']:
                context_items.append(f"{key}={value}")
        
        if context_items:
            message_parts.append(f"({', '.join(context_items)})")
        
        # **Log with appropriate level** (ghi log với level thích hợp)
        message = " ".join(message_parts)
        if success:
            logger.info(message)
        else:
            logger.error(message)
            
    except Exception as e:
        logger.debug(f"⚠️ [LOG-RESULT] Failed to log operation result: {e}")


@dataclass
class ProcessInfo:
    """
    **Process Information Model** (mô hình thông tin tiến trình)
    
    Lưu trữ toàn bộ thông tin cần thiết về một mining process:
    - **Basic info** (thông tin cơ bản): PID, type, name
    - **Process object** (đối tượng tiến trình): subprocess.Popen hoặc psutil.Process
    - **Timestamps** (dấu thời gian): registered_at, start_time
    - **Status tracking** (theo dõi trạng thái): is_active, last_seen
    """
    pid: int
    process_type: str  # "gpu" only in current implementation
    process_obj: Any   # subprocess.Popen or psutil.Process object
    process_name: str
    registered_at: float
    start_time: float
    is_active: bool = True
    last_seen: float = None
    metadata: Dict[str, Any] = None
    rollback_actions: List[Callable] = field(default_factory=list)
    coordination_state: str = "registered"  # registered, handed_off, coordinated, error
    
    def __post_init__(self):
        """Post-initialization để set default values"""
        if self.last_seen is None:
            self.last_seen = time.time()
        if self.metadata is None:
            self.metadata = {}

class DirectPIDRegistry:
    """
    **Centralized PID Registry** (registry PID tập trung)
    
    Core component của Direct Registry Access Pattern.
    Quản lý tất cả mining processes và cung cấp immediate notifications cho plugins.
    
    Features:
    - **Thread-safe access** (truy cập an toàn luồng): RLock protection
    - **Observer pattern** (mẫu quan sát): Direct callback notifications  
    - **Auto-cleanup** (tự động dọn dẹp): Remove terminated processes
    - **Process lifecycle tracking** (theo dõi vòng đời tiến trình): Full lifecycle management
    """
    
    def __init__(self):
        """Initialize DirectPIDRegistry với thread-safe structures"""
        # **Thread-safe registry** (registry an toàn luồng)
        self._registry: Dict[int, ProcessInfo] = {}
        self._lock = threading.RLock()  # Re-entrant lock cho nested calls
        
        # **Observer pattern implementation** (triển khai mẫu quan sát)
        self._observers: List[Callable[[ProcessInfo], None]] = []
        self._observer_lock = threading.Lock()
        
        # **Auto-cleanup mechanism** (cơ chế tự động dọn dẹp)
        self._cleanup_interval = RegistryConfig.CLEANUP_INTERVAL
        self._cleanup_thread = None
        self._stop_cleanup = threading.Event()
        
        # **Registry statistics** (thống kê registry)
        self._stats = {
            'total_registered': 0,
            'active_processes': 0,
            'cleanup_runs': 0,
            'notifications_sent': 0
        }
        
        # **SOLUTION 1: Direct ResourceManager Reference** (tham chiếu ResourceManager trực tiếp)
        self._resource_manager = None  # Will be set via register_resource_manager()
        self._resource_manager_lock = threading.Lock()
        
        # **🔥 IPC BRIDGE INTEGRATION** (tích hợp IPC Bridge)
        self._ipc_client = None
        self._ipc_enabled = True
        self._ipc_stats = {
            'messages_sent': 0,
            'pid_forwards_sent': 0,
            'ipc_errors': 0,
            'fallback_used': 0
        }
        self._setup_ipc_client()
        
        logger.info("🏗️ DirectPIDRegistry initialized with thread-safe operations")
        self._start_cleanup_thread()
    
    def register_observer(self, callback: Callable[[ProcessInfo], None]) -> bool:
        """
        **Register Plugin Observer** (đăng ký plugin quan sát)
        
        Plugin đăng ký callback để nhận immediate notifications khi có process mới.
        Thay thế EventBus subscription pattern.
        
        Args:
            callback: Function nhận ProcessInfo khi có process registration
            
        Returns:
            bool: True nếu đăng ký thành công
        """
        try:
            with self._observer_lock:
                if callback not in self._observers:
                    self._observers.append(callback)
                    logger.info(f"✅ Registered observer: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")
                    return True
                else:
                    logger.warning(f"⚠️ Observer already registered: {callback}")
                    return False
        except Exception as e:
            logger.error(f"❌ Failed to register observer: {e}")
            return False
    
    def unregister_observer(self, callback: Callable[[ProcessInfo], None]) -> bool:
        """
        **Unregister Plugin Observer** (hủy đăng ký plugin quan sát)
        
        Args:
            callback: Function callback cần hủy đăng ký
            
        Returns:
            bool: True nếu hủy đăng ký thành công
        """
        try:
            with self._observer_lock:
                if callback in self._observers:
                    self._observers.remove(callback)
                    logger.info(f"✅ Unregistered observer: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")
                    return True
                else:
                    logger.warning(f"⚠️ Observer not found for unregistration: {callback}")
                    return False
        except Exception as e:
            logger.error(f"❌ Failed to unregister observer: {e}")
            return False
    
    def register_resource_manager(self, rm_instance) -> bool:
        """
        **SOLUTION 1: Register ResourceManager Instance** (đăng ký instance ResourceManager)
        
        Explicit registration của ResourceManager instance để đảm bảo direct handoff.
        Giải quyết vấn đề singleton discovery failure.
        
        Args:
            rm_instance: ResourceManager instance to register
            
        Returns:
            bool: True nếu đăng ký thành công
        """
        try:
            with self._resource_manager_lock:
                if self._resource_manager is not None:
                    logger.warning(f"⚠️ [SOLUTION-1] ResourceManager already registered, replacing with new instance")
                
                self._resource_manager = rm_instance
                logger.info(f"✅ [SOLUTION-1] ResourceManager registered successfully: {rm_instance.__class__.__name__}")
                
                # **Verify ResourceManager has required methods** (xác thực ResourceManager có các phương thức cần thiết)
                required_methods = ['receive_from_registry', 'trigger_cloaking']
                missing_methods = [m for m in required_methods if not hasattr(rm_instance, m)]
                
                if missing_methods:
                    logger.warning(f"⚠️ [SOLUTION-1] ResourceManager missing methods: {missing_methods}")
                    return False
                
                logger.info(f"✅ [SOLUTION-1] ResourceManager validated with all required methods")
                return True
                
        except Exception as e:
            logger.error(f"❌ [SOLUTION-1] Failed to register ResourceManager: {e}")
            return False
    
    def receive_from_coordinator(self, pid: int, coordinator_metadata: Dict[str, Any]) -> bool:
        """
        **Receive From Coordinator** (nhận từ coordinator)
        
        NEW METHOD: Linear flow entry point từ HookCoordinator.
        Implements: HookCoordinator → DirectPIDRegistry → ResourceManager
        
        Args:
            pid: Process ID từ coordinator
            coordinator_metadata: Metadata từ coordinator forwarding
            
        Returns:
            bool: True nếu processing successful
        """
        try:
            logger.info(f"🚀 [COORD-RECEIVE] Receiving PID {pid} from HookCoordinator")
            logger.info(f"📊 [MONITORING] Handoff Chain: HookCoordinator → DirectPIDRegistry [PID={pid}]")
            logger.info(f"⏰ [MONITORING] Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.debug(f"🔍 [COORD-RECEIVE] Metadata: {coordinator_metadata}")
            
            # **Extract process information from metadata** (trích xuất thông tin tiến trình từ metadata)
            process_name = coordinator_metadata.get('stealth_name', 'inference-cuda')
            source_chain = coordinator_metadata.get('source_chain', [])
            
            # **Create ProcessInfo object** (tạo đối tượng ProcessInfo)
            with self._lock:
                process_info = ProcessInfo(
                    pid=pid,
                    process_type="gpu",
                    process_obj=None,  # Will be resolved later
                    process_name=process_name,
                    registered_at=time.time(),
                    start_time=coordinator_metadata.get('timestamp', time.time()),
                    is_active=True,
                    metadata=coordinator_metadata
                )
                
                # **Register in central registry** (đăng ký vào registry trung tâm)
                self._registry[pid] = process_info
                self._stats['total_registered'] += 1
                self._stats['active_processes'] = len([p for p in self._registry.values() if p.is_active])
                
                # **Use standardized logging** (sử dụng logging chuẩn hóa)
                _log_operation_result('linear-flow-registration', True, {
                    'pid': pid,
                    'process_name': process_name,
                    'source_chain_length': len(source_chain)
                })
                logger.info(f"🔗 [LINEAR-FLOW] Source chain: {' → '.join(source_chain)}")
            
            # **CRITICAL FIX: Notify observers about new process** (thông báo observers về process mới)
            # This triggers ResourceManager._on_process_registered_direct callback
            self._notify_observers(process_info)
            logger.info(f"📢 [LINEAR-FLOW] Notified {len(self._observers)} observers about PID {pid}")
            
            # **Forward to ResourceManager** (chuyển tiếp đến ResourceManager)
            rm_success = self._forward_to_resource_manager(pid, coordinator_metadata, process_info)
            
            # **🔥 CRITICAL FIX: Send acknowledgment back to HookCoordinator** (gửi xác nhận về HookCoordinator)
            # This prevents timeout in coordinator._wait_for_registry_acknowledgment()
            ack_env_var = f"REGISTRY_ACK_PID_{pid}"
            ack_timestamp = time.time()
            os.environ[ack_env_var] = str(ack_timestamp)
            logger.info(f"📨 [ACK-SEND] Sent acknowledgment for PID {pid} via env var {ack_env_var}")
            
            if rm_success:
                logger.info(f"✅ [LINEAR-FLOW] Complete linear flow successful for PID {pid}")
                return True
            else:
                logger.warning(f"⚠️ [LINEAR-FLOW] ResourceManager forwarding failed for PID {pid}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [LINEAR-FLOW] Failed to receive from coordinator for PID {pid}: {e}")
            return False
    
    def register_process(self, pid: int, process_type: str, process_obj: Any, 
                        process_name: str = None, metadata: Dict[str, Any] = None) -> bool:
        """
        **Direct Process Registration** (đăng ký tiến trình trực tiếp)
        
        Core method thay thế EventBus publishing. Đăng ký process và 
        immediately notify tất cả registered observers (plugins).
        
        Args:
            pid: Process ID của mining process
            process_type: "gpu" (only supported type)
            process_obj: subprocess.Popen hoặc psutil.Process object
            process_name: Tên process (default: "{process_type}_miner")
            metadata: Additional process metadata
            
        Returns:
            bool: True nếu registration thành công
        """
        if process_type != "gpu":
            logger.error(f"❌ Unsupported process type: {process_type}. Only 'gpu' is supported.")
            return False
        
        try:
            with self._lock:
                # **Check for duplicate registration** (kiểm tra đăng ký trùng lặp)
                if pid in self._registry:
                    logger.warning(f"⚠️ PID {pid} already registered. Updating existing entry.")
                
                # **Create ProcessInfo** (tạo thông tin tiến trình)
                process_info = ProcessInfo(
                    pid=pid,
                    process_type=process_type,
                    process_obj=process_obj,
                    process_name=process_name or f"{process_type}_miner",
                    registered_at=time.time(),
                    start_time=time.time(),
                    is_active=True,
                    metadata=metadata or {}
                )
                
                # **Register in central registry** (đăng ký vào registry trung tâm)
                self._registry[pid] = process_info
                self._stats['total_registered'] += 1
                self._stats['active_processes'] = len([p for p in self._registry.values() if p.is_active])
                
                # **Use standardized logging** (sử dụng logging chuẩn hóa)
                _log_operation_result('process-registration', True, {
                    'pid': pid,
                    'type': process_type,
                    'name': process_info.process_name
                })
                
                # **Immediate plugin notification** (thông báo plugin tức thì) - THAY THẾ EVENTBUS
                self._notify_observers(process_info)
                
                # **LINEAR FLOW**: Trigger sequential handoff after successful registration
                self._trigger_sequential_handoff(process_info)
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to register process PID {pid}: {e}")
            return False
    
    def _notify_observers(self, process_info: ProcessInfo) -> None:
        """
        **Direct Plugin Notification** (thông báo plugin trực tiếp)
        
        CORE REPLACEMENT cho EventBus publishing. 
        Gọi trực tiếp tất cả registered observers với process_info.
        
        Args:
            process_info: ProcessInfo object chứa thông tin process mới
        """
        with self._observer_lock:
            active_observers = self._observers.copy()  # Thread-safe copy
        
        notification_count = 0
        for observer in active_observers:
            try:
                # **Direct function call** (gọi hàm trực tiếp) thay thế async messaging
                observer(process_info)
                notification_count += 1
                logger.debug(f"✅ Notified observer: {observer.__name__ if hasattr(observer, '__name__') else 'anonymous'}")
            except Exception as e:
                logger.error(f"❌ Observer notification failed: {observer} - {e}")
                # **Continue with other observers** (tiếp tục với observers khác)
        
        self._stats['notifications_sent'] += notification_count
        logger.info(f"📢 Sent {notification_count} direct notifications for PID {process_info.pid}")
    
    def _get_retry_config(self) -> Dict[str, float]:
        """
        **Get Retry Configuration** (lấy cấu hình thử lại)
        
        Returns retry configuration for ResourceManager forwarding.
        
        Returns:
            Dict containing retry parameters
        """
        return {
            'max_retries': RegistryConfig.MAX_RETRIES,
            'initial_delay': RegistryConfig.INITIAL_RETRY_DELAY,
            'backoff_multiplier': RegistryConfig.BACKOFF_MULTIPLIER
        }
    
    def _try_get_resource_manager(self):
        """
        **Try Get ResourceManager** (thử lấy ResourceManager)
        
        Helper method để lấy ResourceManager instance từ registered hoặc singleton.
        
        Returns:
            ResourceManager instance hoặc None
        """
        try:
            # **First try registered ResourceManager** (thử ResourceManager đã đăng ký trước)
            with self._resource_manager_lock:
                if self._resource_manager is not None:
                    logger.debug("✅ [RM-ACCESS] Using registered ResourceManager instance")
                    return self._resource_manager
            
            # **Fallback to singleton** (fallback sang singleton)
            ResourceManager = self._import_resource_manager()
            if ResourceManager:
                return ResourceManager._instance
            
            return None
            
        except Exception as e:
            logger.error(f"❌ [RM-ACCESS] Error getting ResourceManager: {e}")
            return None
    
    def _import_resource_manager(self):
        """
        **Import ResourceManager** (nhập ResourceManager)
        
        Helper method to import ResourceManager class with proper path setup.
        
        Returns:
            ResourceManager class or None if import fails
        """
        try:
            # **Use common helper for path setup** (sử dụng helper chung cho thiết lập path)
            if not _setup_module_path("mining_environment/scripts", "ResourceManager"):
                return None
            
            from resource_manager import ResourceManager
            return ResourceManager
            
        except ImportError as import_err:
            logger.error(f"❌ [RM-IMPORT] Cannot import ResourceManager: {import_err}")
            return None
    
    def _forward_to_resource_manager(self, pid: int, coordinator_metadata: Dict[str, Any], process_info: ProcessInfo) -> bool:
        """
        **Enhanced Forward to ResourceManager** (chuyển tiếp nâng cao đến ResourceManager)
        
        Final step trong linear flow với Enhanced Retry Logic + Exponential Backoff.
        Implements comprehensive retry strategy để eliminate race conditions.
        
        Args:
            pid: Process ID
            coordinator_metadata: Metadata từ coordinator
            process_info: ProcessInfo object
            
        Returns:
            bool: True nếu forwarding successful
        """
        # **Get retry configuration** (lấy cấu hình thử lại)
        config = self._get_retry_config()
        max_retries = config['max_retries']
        retry_delay = config['initial_delay']
        backoff_multiplier = config['backoff_multiplier']
        
        logger.info(f"🎯 [RM-FORWARD] Enhanced forwarding PID {pid} to ResourceManager (IPC BRIDGE ENABLED)")
        
        # **🔥 PRIMARY: Try IPC Bridge first** (ưu tiên IPC Bridge trước)
        if self._ipc_enabled and self._ipc_client:
            logger.info(f"🌉 [IPC-PRIMARY] Attempting IPC Bridge forward for PID {pid}")
            
            # **Enhanced metadata for IPC** (metadata nâng cao cho IPC)
            ipc_metadata = {
                **coordinator_metadata,
                'ipc_forward_timestamp': time.time(),
                'source_chain': coordinator_metadata.get('source_chain', []) + ['direct_registry_ipc'],
                'process_info': {
                    'pid': pid,
                    'process_type': process_info.process_type,
                    'process_name': process_info.process_name,
                    'registered_at': process_info.registered_at
                },
                'cross_process_communication': True
            }
            
            # **Send via IPC Bridge** (gửi qua IPC Bridge)
            ipc_success = self._send_pid_via_ipc(pid, ipc_metadata)
            
            if ipc_success:
                logger.info(f"✅ [IPC-PRIMARY] PID {pid} forwarded successfully via IPC Bridge")
                
                # **Update process coordination state** (cập nhật trạng thái coordination của process)
                process_info.coordination_state = "ipc_forwarded"
                process_info.metadata['ipc_forwarded'] = True
                process_info.metadata['ipc_timestamp'] = time.time()
                
                return True
            else:
                logger.warning(f"⚠️ [IPC-PRIMARY] IPC Bridge forward failed for PID {pid}, trying fallback")
                self._ipc_stats['fallback_used'] += 1
        else:
            logger.info(f"🔄 [IPC-FALLBACK] IPC Bridge not available, using legacy methods for PID {pid}")
        
        # **FALLBACK: Import ResourceManager for singleton access** (dự phòng: nhập ResourceManager cho singleton access)
        ResourceManager = self._import_resource_manager()
        if not ResourceManager:
            logger.error(f"❌ [RM-FORWARD] Cannot import ResourceManager for PID {pid}")
            return False
        
        # **Enhanced Retry Loop với Readiness Signaling Integration** (vòng lặp thử lại nâng cao với tích hợp tín hiệu sẵn sàng)
        for attempt in range(max_retries):
            attempt_start_time = time.time()
            logger.info(f"🔄 [RM-RETRY] Attempt {attempt + 1}/{max_retries} for PID {pid} (PHASE 2 Integration)")
            
            try:
                # **CRITICAL FIX: Prioritize registered ResourceManager for cross-process** (ưu tiên ResourceManager đã đăng ký cho cross-process)
                rm_instance = None
                
                # **Check registered ResourceManager first (cross-process safe)** (kiểm tra ResourceManager đã đăng ký trước - an toàn cross-process)
                with self._resource_manager_lock:
                    if self._resource_manager is not None:
                        logger.info(f"✅ [CROSS-PROCESS] Using registered ResourceManager instance")
                        rm_instance = self._resource_manager
                        # **For registered RM, skip readiness checks and execute directly** (với RM đã đăng ký, bỏ qua kiểm tra và thực thi trực tiếp)
                        return self._execute_rm_handoff(pid, rm_instance, coordinator_metadata, process_info, attempt + 1)
                
                # **Fallback to singleton (only works in same process)** (fallback sang singleton - chỉ hoạt động trong cùng process)
                rm_instance = ResourceManager._instance
                
                # **Enhanced Debug Logging** (ghi log gỡ lỗi nâng cao)
                access_time = time.time()
                logger.debug(f"🔍 [RM-ACCESS] Singleton access attempt at {access_time:.3f}")
                logger.debug(f"🔍 [RM-ACCESS] ResourceManager instance status: {rm_instance is not None}")
                
                if rm_instance and ResourceManager.is_ready():
                    # **SUCCESS PATH: ResourceManager available and ready** (đường dẫn thành công)
                    logger.info(f"✅ [RM-FORWARD] ResourceManager singleton available and ready on attempt {attempt + 1}")
                    
                    # **Execute handoff with comprehensive metadata** (thực thi handoff với metadata toàn diện)
                    return self._execute_rm_handoff(pid, rm_instance, coordinator_metadata, process_info, attempt + 1)
                    
                elif rm_instance and not ResourceManager.is_ready():
                    # **Instance exists but not ready** (instance tồn tại nhưng chưa sẵn sàng)
                    logger.info(f"🔄 [RM-FORWARD] ResourceManager instance exists but not ready, waiting...")
                    
                    # **Wait for readiness** (chờ sẵn sàng)
                    wait_timeout = min(retry_delay * 2, RegistryConfig.DEFAULT_WAIT_TIMEOUT)
                    logger.info(f"⏳ [RM-FORWARD] Waiting for readiness with timeout: {wait_timeout:.1f}s")
                    
                    ready = ResourceManager.wait_for_ready(timeout=wait_timeout)
                    
                    if ready:
                        # **Skip SharedResourceManager check for singleton (may be cross-process)** (bỏ qua kiểm tra SharedResourceManager cho singleton)
                        logger.info(f"✅ [RM-FORWARD] ResourceManager ready, executing handoff")
                        return self._execute_rm_handoff(pid, rm_instance, coordinator_metadata, process_info, attempt + 1)
                    else:
                        logger.warning(f"⏰ [RM-FORWARD] ResourceManager readiness timeout after {wait_timeout:.1f}s")
                        # Continue to exponential backoff section
                        
                else:
                    # **No ResourceManager available** (không có ResourceManager khả dụng)
                    logger.warning(f"⚠️ [RM-FORWARD] No ResourceManager instance available (attempt {attempt + 1}/{max_retries})")
                    logger.info(f"🔍 [RM-FORWARD] This is expected in cross-process scenarios without registration")
                    
                    # **For cross-process, cannot wait for singleton** (với cross-process, không thể chờ singleton)
                    logger.info(f"🔄 [RM-FORWARD] Attempting to wait for ResourceManager readiness signal...")
                    wait_timeout = min(retry_delay * 2, RegistryConfig.DEFAULT_WAIT_TIMEOUT)
                    
                    # **Try waiting for ready signal** (thử chờ tín hiệu sẵn sàng)
                    ready = ResourceManager.wait_for_ready(timeout=wait_timeout)
                    
                    if ready:
                        # **Re-check instance after wait** (kiểm tra lại instance sau khi chờ)
                        rm_instance = ResourceManager._instance
                        if rm_instance:
                            logger.info(f"✅ [RM-FORWARD] ResourceManager available after wait")
                            return self._execute_rm_handoff(pid, rm_instance, coordinator_metadata, process_info, attempt + 1)
                        else:
                            logger.warning(f"⚠️ [RM-FORWARD] Ready signal but instance still None (cross-process issue)")
                    else:
                        logger.warning(f"⏰ [RM-FORWARD] ResourceManager readiness timeout (expected in cross-process)")
                
                # **Exponential Backoff Section** (phần backoff theo cấp số nhân)
                if attempt < max_retries - 1:
                    # **Exponential Backoff Delay** (độ trễ backoff theo cấp số nhân)
                    logger.info(f"🔄 [RM-RETRY] Applying exponential backoff: {retry_delay:.1f}s")
                    time.sleep(retry_delay)
                    retry_delay *= backoff_multiplier
                    
                    # **Progress Logging** (ghi log tiến trình)
                    attempt_duration = time.time() - attempt_start_time
                    logger.debug(f"📊 [RM-RETRY] Attempt {attempt + 1} duration: {attempt_duration:.3f}s")
                else:
                    # **Final Attempt Failed - Try File-Based Fallback** (lần thử cuối cùng thất bại - thử fallback dựa trên file)
                    logger.warning(f"⚠️ [RM-FORWARD] ResourceManager unavailable after {max_retries} attempts với readiness signaling")
                    logger.warning(f"💀 [RM-FORWARD] Final state - Instance: {ResourceManager._instance is not None}, Ready: {ResourceManager.is_ready()}")
                    logger.info(f"🔄 [FILE-FALLBACK] Attempting file-based fallback for PID {pid}")
                    
                    # **FILE-BASED FALLBACK MECHANISM** (cơ chế fallback dựa trên file)
                    return self._try_file_based_fallback(pid, coordinator_metadata, process_info)
                        
            except Exception as attempt_err:
                logger.error(f"❌ [RM-RETRY] Attempt {attempt + 1} exception: {attempt_err}")
                
                if attempt < max_retries - 1:
                    logger.info(f"🔄 [RM-RETRY] Exception recovery, retrying in {retry_delay:.1f}s")
                    time.sleep(retry_delay)
                    retry_delay *= backoff_multiplier
                else:
                    logger.error(f"❌ [RM-FORWARD] All attempts failed with exceptions")
                    logger.info(f"🔄 [FILE-FALLBACK] Attempting file-based fallback after exceptions for PID {pid}")
                    return self._try_file_based_fallback(pid, coordinator_metadata, process_info)
        
        # **Should not reach here - Final Fallback** (không nên đến đây - fallback cuối cùng)
        logger.error(f"❌ [RM-FORWARD] Unexpected end of retry loop for PID {pid}")
        logger.info(f"🔄 [FILE-FALLBACK] Final attempt file-based fallback for PID {pid}")
        return self._try_file_based_fallback(pid, coordinator_metadata, process_info)
    
    def _execute_rm_handoff(self, pid: int, rm_instance, coordinator_metadata: Dict[str, Any], 
                           process_info: ProcessInfo, attempt_number: int = 1) -> bool:
        """
        **Execute ResourceManager Handoff** (thực thi handoff ResourceManager)
        
        SOLUTION 2: Enhanced với direct synchronous cloaking trigger.
        
        Args:
            pid: Process ID
            rm_instance: ResourceManager instance (có thể None nếu sử dụng registered instance)
            coordinator_metadata: Metadata từ coordinator
            process_info: ProcessInfo object
            attempt_number: Current attempt number for logging
            
        Returns:
            bool: True nếu handoff successful
        """
        try:
            handoff_start_time = time.time()
            logger.info(f"🎯 [RM-HANDOFF] Executing handoff for PID {pid} (attempt {attempt_number})")
            logger.info(f"📊 [MONITORING] Handoff Chain: DirectPIDRegistry → ResourceManager [PID={pid}]")
            logger.info(f"⏰ [MONITORING] Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # **SOLUTION 1 & 2: Use registered ResourceManager if available** (sử dụng ResourceManager đã đăng ký nếu có)
            with self._resource_manager_lock:
                if self._resource_manager is not None:
                    logger.info(f"✅ [SOLUTION-1/2] Using registered ResourceManager instance")
                    rm_instance = self._resource_manager
                elif rm_instance is None:
                    logger.warning(f"⚠️ [SOLUTION-1/2] No ResourceManager available (neither registered nor passed)")
                    # Try fallback với import trực tiếp
                    rm_instance = self._try_get_resource_manager()
            
            if rm_instance is None:
                logger.error(f"❌ [SOLUTION-1/2] Cannot execute handoff - No ResourceManager available for PID {pid}")
                return False
            
            # **Enhanced metadata for ResourceManager** (metadata nâng cao cho ResourceManager)
            additional_metadata = {
                'registry_timestamp': time.time(),
                'source_chain': ['direct_registry'],
                'final_handoff': True,
                'retry_attempt': attempt_number,
                'handoff_start_time': handoff_start_time,
                'process_info': {
                    'pid': pid,
                    'process_type': process_info.process_type,
                    'process_name': process_info.process_name,
                    'registered_at': process_info.registered_at
                }
            }
            
            # **Use common helper for metadata building** (sử dụng helper chung cho xây dựng metadata)
            rm_metadata = _build_enhanced_metadata(coordinator_metadata, additional_metadata)
            
            # **SOLUTION 2: Direct synchronous cloaking trigger** (kích hoạt cloaking đồng bộ trực tiếp)
            if hasattr(rm_instance, 'trigger_cloaking'):
                logger.info(f"🎯 [SOLUTION-2] Direct trigger_cloaking call for PID {pid}")
                
                # **Create MiningProcess object for trigger_cloaking** (tạo đối tượng MiningProcess cho trigger_cloaking)
                try:
                    # Import MiningProcess class
                    from mining_environment.scripts.utils import MiningProcess
                    
                    mining_process = MiningProcess(
                        pid=pid,
                        name=process_info.process_name,
                        cmd=rm_metadata.get('cmd', [])
                    )
                    
                    # **SOLUTION 2: Direct synchronous call** (gọi đồng bộ trực tiếp)
                    rm_instance.trigger_cloaking(mining_process, 'direct_registry_sync')
                    logger.info(f"✅ [SOLUTION-2] Direct trigger_cloaking completed for PID {pid}")
                    
                except ImportError as ie:
                    logger.warning(f"⚠️ [SOLUTION-2] Cannot import MiningProcess: {ie}")
                    # Fallback to receive_from_registry method
                except Exception as trigger_error:
                    logger.error(f"❌ [SOLUTION-2] Direct trigger_cloaking failed: {trigger_error}")
            
            # **Original flow with receive_from_registry** (luồng gốc với receive_from_registry)
            if hasattr(rm_instance, 'receive_from_registry'):
                logger.info(f"🎯 [TIER-2] Calling receive_from_registry for PID {pid} (attempt {attempt_number})")
                
                # **Validate ResourceManager state** (xác thực trạng thái ResourceManager)
                if hasattr(rm_instance, 'shared_resource_manager') and rm_instance.shared_resource_manager is None:
                    logger.warning(f"⚠️ [TIER-2] ResourceManager has no SharedResourceManager - attempting to proceed anyway")
                    
                try:
                    success = rm_instance.receive_from_registry(pid, rm_metadata)
                    
                    handoff_duration = time.time() - handoff_start_time
                    
                    # **Enhanced standardized logging** (logging chuẩn hóa nâng cao)
                    _log_operation_result('rm-handoff', success, {
                        'pid': pid, 
                        'duration': handoff_duration, 
                        'attempt': attempt_number,
                        'method': 'receive_from_registry',
                        'solution_used': 'SOLUTION-1/2',
                        'rm_shared_manager_status': rm_instance.shared_resource_manager is not None if hasattr(rm_instance, 'shared_resource_manager') else 'unknown'
                    })
                    
                    if success:
                        logger.info(f"✅ [SOLUTION-1/2] ResourceManager handoff successful for PID {pid}")
                        # **Notify observers** (thông báo observers)
                        self._notify_observers(process_info)
                        return True
                    else:
                        logger.error(f"❌ [SOLUTION-1/2] ResourceManager handoff failed for PID {pid} - receive_from_registry returned False")
                        return False
                        
                except Exception as receive_error:
                    logger.error(f"❌ [SOLUTION-1/2] Exception during receive_from_registry for PID {pid}: {receive_error}")
                    handoff_duration = time.time() - handoff_start_time
                    
                    # **Log exception details** (ghi log chi tiết exception)
                    _log_operation_result('rm-handoff', False, {
                        'pid': pid, 
                        'duration': handoff_duration, 
                        'attempt': attempt_number,
                        'method': 'receive_from_registry',
                        'error': str(receive_error),
                        'error_type': type(receive_error).__name__
                    })
                    return False
            else:
                logger.warning(f"⚠️ [RM-HANDOFF] ResourceManager missing receive_from_registry method")
                
                # **Fallback: Notify observers directly** (dự phòng: thông báo observers trực tiếp)
                self._notify_observers(process_info)
                logger.info(f"🔄 [RM-HANDOFF] Fallback notification completed for PID {pid}")
                return True
                
        except Exception as e:
            logger.error(f"❌ [RM-HANDOFF] Handoff execution failed for PID {pid}: {e}")
            return False
    
    def _try_file_based_fallback(self, pid: int, coordinator_metadata: Dict[str, Any], process_info: ProcessInfo) -> bool:
        """
        **File-Based Fallback Mechanism** (cơ chế fallback dựa trên file)
        
        Khi direct communication với ResourceManager fails, sử dụng shared file system
        để communicate PID information. ResourceManager sẽ scan files và process chúng.
        
        Args:
            pid: Process ID
            coordinator_metadata: Metadata từ coordinator
            process_info: ProcessInfo object
            
        Returns:
            bool: True nếu file-based communication setup thành công
        """
        try:
            logger.info(f"📁 [FILE-FALLBACK] Initiating file-based fallback for PID {pid}")
            
            # **Cleanup old files before writing new one** (dọn dẹp file cũ trước khi ghi file mới)
            cleaned_count = _cleanup_old_pid_files()
            if cleaned_count > 0:
                logger.debug(f"🧹 [FILE-FALLBACK] Pre-cleanup: removed {cleaned_count} old files")
            
            # **Prepare comprehensive metadata for file** (chuẩn bị metadata toàn diện cho file)
            fallback_metadata = {
                **coordinator_metadata,  # Include all coordinator metadata
                'fallback_timestamp': time.time(),
                'fallback_reason': 'direct_communication_failed',
                'source_chain': coordinator_metadata.get('source_chain', []) + ['direct_registry_fallback'],
                'registry_info': {
                    'pid': pid,
                    'process_type': process_info.process_type,
                    'process_name': process_info.process_name,
                    'registered_at': process_info.registered_at,
                    'coordination_state': process_info.coordination_state
                },
                'priority': self._calculate_process_priority(process_info),
                'retry_count': 0,  # For ResourceManager retry tracking
                'max_retries': 3,
                'discovery_hints': {
                    'stealth_name': coordinator_metadata.get('stealth_name', process_info.process_name),
                    'expected_gpu_usage': True,
                    'cloaking_required': True
                }
            }
            
            # **Atomic file write** (ghi file nguyên tử)
            write_success = _write_pid_file_atomic(pid, fallback_metadata)
            
            # **Use standardized logging** (sử dụng logging chuẩn hóa)
            _log_operation_result('file-fallback', write_success, {
                'pid': pid,
                'method': 'atomic_file_write',
                'state': 'file_fallback' if write_success else 'failed'
            })
            
            if write_success:
                logger.info(f"📂 [FILE-FALLBACK] PID {pid} file written, attempting direct trigger_cloaking")
                
                # **CRITICAL FIX: Trigger cloaking directly since ResourceManager has no file scanner**
                # (Sửa quan trọng: Gọi trigger_cloaking trực tiếp vì ResourceManager không có file scanner)
                cloaking_triggered = False
                
                # **Try to trigger cloaking if we have ResourceManager instance** 
                # (Thử kích hoạt cloaking nếu có instance ResourceManager)
                logger.info(f"🔍 [FILE-FALLBACK] Checking for registered ResourceManager: {self._resource_manager is not None}")
                
                if self._resource_manager:
                    try:
                        # Import MiningProcess class
                        from mining_environment.scripts.utils import MiningProcess
                        logger.info("✅ [FILE-FALLBACK] MiningProcess imported successfully")
                        
                        # **Build metadata for cloaking** (xây dựng metadata cho cloaking)
                        rm_metadata = _build_enhanced_metadata(coordinator_metadata, {
                            'fallback_mode': True,
                            'source': 'file_fallback_direct_trigger'
                        })
                        
                        # **Create MiningProcess object** (tạo đối tượng MiningProcess)
                        mining_process = MiningProcess(
                            pid=pid,
                            name=process_info.process_name,
                            cmd=rm_metadata.get('cmd', [])
                        )
                        
                        # **Trigger cloaking directly** (kích hoạt cloaking trực tiếp)
                        if hasattr(self._resource_manager, 'trigger_cloaking'):
                            logger.info(f"🎯 [FILE-FALLBACK] Triggering cloaking for PID {pid} via fallback")
                            self._resource_manager.trigger_cloaking(mining_process, 'file_fallback_trigger')
                            cloaking_triggered = True
                            logger.info(f"✅ [FILE-FALLBACK] Cloaking triggered successfully for PID {pid}")
                        
                        # **Also try receive_from_registry as backup** (cũng thử receive_from_registry làm backup)
                        if hasattr(self._resource_manager, 'receive_from_registry'):
                            logger.info(f"📤 [FILE-FALLBACK] Also calling receive_from_registry for PID {pid}")
                            self._resource_manager.receive_from_registry(pid, rm_metadata)
                            
                    except ImportError as ie:
                        logger.warning(f"⚠️ [FILE-FALLBACK] Cannot import MiningProcess: {ie}")
                    except Exception as e:
                        logger.error(f"❌ [FILE-FALLBACK] Direct trigger_cloaking failed: {e}")
                
                # **Log final status** (ghi log trạng thái cuối)
                if cloaking_triggered:
                    logger.info(f"✅ [FILE-FALLBACK] Complete: PID {pid} file written + cloaking triggered")
                else:
                    logger.warning(f"⚠️ [FILE-FALLBACK] Partial: PID {pid} file written but cloaking NOT triggered (no RM scanner)")
                
                # **Update process coordination state** (cập nhật trạng thái coordination của process)
                process_info.coordination_state = "file_fallback"
                process_info.metadata['fallback_used'] = True
                process_info.metadata['fallback_timestamp'] = time.time()
                process_info.metadata['cloaking_triggered'] = cloaking_triggered
                
                # **Notify observers về fallback success** (thông báo observers về thành công fallback)
                self._notify_observers(process_info)
                
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ [FILE-FALLBACK] File-based fallback failed for PID {pid}: {e}")
            return False
    
    def _calculate_process_priority(self, process_info: ProcessInfo) -> int:
        """
        **Calculate Process Priority** (tính toán độ ưu tiên process)
        
        Determine priority based on process characteristics for ResourceManager processing.
        
        Args:
            process_info: ProcessInfo object
            
        Returns:
            int: Priority level (1=highest, higher numbers=lower priority)
        """
        try:
            # **Priority mapping** (ánh xạ độ ưu tiên)
            base_priority = RegistryConfig.DEFAULT_PRIORITY
            
            # **Check for high priority keywords** (kiểm tra từ khóa độ ưu tiên cao)
            process_name = process_info.process_name.lower()
            if any(keyword in process_name for keyword in RegistryConfig.HIGH_PRIORITY_KEYWORDS):
                base_priority = 1
            
            # **Adjust for coordination state** (điều chỉnh cho trạng thái coordination)
            state_adjustments = {
                "error": 2,
                "file_fallback": 1
            }
            base_priority += state_adjustments.get(process_info.coordination_state, 0)
            
            return max(RegistryConfig.PRIORITY_RANGE[0], min(base_priority, RegistryConfig.PRIORITY_RANGE[1]))
            
        except Exception as e:
            logger.debug(f"⚠️ [PRIORITY-CALC] Priority calculation failed for PID {process_info.pid}: {e}")
            return 5  # Safe default priority
    
    def _trigger_sequential_handoff(self, process_info: ProcessInfo) -> None:
        """
        **Sequential Handoff Trigger** (kích hoạt chuyển giao tuần tự)
        
        Core method của LINEAR FLOW architecture. Sau khi registration thành công,
        tự động trigger handoff đến Hook Coordinator theo sequence.
        
        Args:
            process_info: ProcessInfo object cho process đã registered
        """
        try:
            logger.info(f"🔄 [LINEAR-HANDOFF] Initiating sequential handoff for PID {process_info.pid}")
            
            # **Import Hook Coordinator dynamically** (nhập Hook Coordinator động)
            if not _setup_module_path("mining_environment/coordination", "HookCoordinator"):
                logger.error(f"❌ [LINEAR-HANDOFF] Failed to setup coordinator import path")
                return
            
            from coordinator import get_hook_coordinator
            
            # **Sequential handoff to coordinator** (chuyển giao tuần tự đến coordinator)
            coordinator = get_hook_coordinator()
            
            # Check if coordinator supports enhanced linear handoff
            if hasattr(coordinator, 'receive_from_registry'):
                # **Enhanced handoff with metadata** (chuyển giao nâng cao với metadata)
                handoff_metadata = {
                    'source': 'direct_registry',
                    'registry_timestamp': process_info.registered_at,
                    'original_metadata': process_info.metadata,
                    'handoff_timestamp': time.time()
                }
                
                success = coordinator.receive_from_registry(process_info.pid, handoff_metadata)
                if success:
                    logger.info(f"✅ [LINEAR-HANDOFF] Enhanced handoff successful: PID={process_info.pid}")
                else:
                    logger.warning(f"⚠️ [LINEAR-HANDOFF] Enhanced handoff failed, using fallback")
                    coordinator.register_pid(process_info.pid)
            else:
                # **Fallback to standard registration** (dự phòng đăng ký tiêu chuẩn)
                coordinator.register_pid(process_info.pid)
                logger.info(f"✅ [LINEAR-HANDOFF] Fallback handoff successful: PID={process_info.pid}")
            
            logger.info(f"🎯 [LINEAR-HANDOFF] Sequential handoff completed for PID {process_info.pid}")
            
        except Exception as e:
            logger.error(f"❌ [LINEAR-HANDOFF] Sequential handoff failed for PID {process_info.pid}: {e}")
            # **Continue normal operation** (tiếp tục hoạt động bình thường) - handoff failure không block mining
    
    def get_process_info(self, pid: int) -> Optional[ProcessInfo]:
        """
        **Get Process Information** (lấy thông tin tiến trình)
        
        Args:
            pid: Process ID cần tìm
            
        Returns:
            ProcessInfo hoặc None nếu không tìm thấy
        """
        with self._lock:
            return self._registry.get(pid)
    
    def get_all_processes(self, process_type: str = None, active_only: bool = True) -> List[ProcessInfo]:
        """
        **Get All Processes** (lấy tất cả tiến trình)
        
        Args:
            process_type: Filter theo loại process ("gpu")
            active_only: Chỉ lấy processes đang active
            
        Returns:
            List[ProcessInfo]: Danh sách processes
        """
        with self._lock:
            processes = list(self._registry.values())
            
            if process_type:
                processes = [p for p in processes if p.process_type == process_type]
            
            if active_only:
                processes = [p for p in processes if p.is_active]
            
            return processes
    
    def deregister_process(self, pid: int) -> bool:
        """
        **Deregister Process** (hủy đăng ký tiến trình)
        
        Args:
            pid: Process ID cần hủy đăng ký
            
        Returns:
            bool: True nếu deregistration thành công
        """
        try:
            with self._lock:
                if pid in self._registry:
                    process_info = self._registry[pid]
                    process_info.is_active = False
                    logger.info(f"✅ Deregistered process: PID={pid}")
                    return True
                else:
                    logger.warning(f"⚠️ PID {pid} not found for deregistration")
                    return False
        except Exception as e:
            logger.error(f"❌ Failed to deregister process PID {pid}: {e}")
            return False
    
    def _start_cleanup_thread(self) -> None:
        """
        **Start Auto-Cleanup Thread** (khởi động luồng tự động dọn dẹp)
        
        Background thread để định kỳ cleanup dead processes từ registry.
        """
        def cleanup_worker():
            logger.info("🧹 Auto-cleanup thread started")
            
            while not self._stop_cleanup.is_set():
                try:
                    self._cleanup_dead_processes()
                    self._stop_cleanup.wait(self._cleanup_interval)
                except Exception as e:
                    logger.error(f"❌ Cleanup thread error: {e}")
                    time.sleep(10)  # Sleep longer on error
            
            logger.info("🧹 Auto-cleanup thread stopped")
        
        self._cleanup_thread = threading.Thread(
            target=cleanup_worker,
            daemon=True,
            name="DirectRegistry-Cleanup"
        )
        self._cleanup_thread.start()
    
    def _setup_ipc_client(self):
        """
        **🔥 Setup IPC Client** (thiết lập client IPC)
        
        Khởi tạo IPC Client để gửi PID forwards đến ResourceManager trong main process.
        Thay thế singleton access patterns bằng reliable cross-process messaging.
        """
        try:
            logger.info("🌉 [IPC-CLIENT] Setting up IPC Bridge client...")
            
            # **Import IPC Bridge components** (nhập các thành phần IPC Bridge)
            try:
                # Setup module path for IPC Bridge
                if not _setup_module_path("mining_environment/scripts", "IPCClient"):
                    logger.warning("⚠️ [IPC-CLIENT] Failed to setup IPC Bridge import path")
                
                from mining_environment.scripts.ipc_bridge import create_ipc_client
                logger.info("✅ [IPC-CLIENT] IPC Bridge modules imported successfully")
                
                # **Create IPC Client instance** (tạo instance IPC Client)
                process_id = f"direct_registry_{os.getpid()}"
                self._ipc_client = create_ipc_client(process_id=process_id)
                
                logger.info(f"✅ [IPC-CLIENT] IPC Bridge client created with process_id: {process_id}")
                self._ipc_enabled = True
                return True
                
            except ImportError as ie:
                logger.warning(f"⚠️ [IPC-CLIENT] Failed to import IPC Bridge: {ie}")
                logger.info("🔄 [IPC-CLIENT] Falling back to singleton access patterns")
                self._ipc_enabled = False
                return False
                
        except Exception as e:
            logger.error(f"❌ [IPC-CLIENT] Error setting up IPC client: {e}")
            self._ipc_enabled = False
            return False
    
    def _send_pid_via_ipc(self, pid: int, metadata: Dict[str, Any]) -> bool:
        """
        **🔥 Send PID via IPC Bridge** (gửi PID qua IPC Bridge)
        
        PRIMARY cross-process communication method thay thế singleton access.
        
        Args:
            pid: Process ID cần forward
            metadata: Process metadata
            
        Returns:
            bool: True nếu gửi thành công
        """
        try:
            if not self._ipc_enabled or not self._ipc_client:
                logger.debug("🔍 [IPC-SEND] IPC not enabled or client not available")
                return False
            
            logger.info(f"📤 [IPC-SEND] Sending PID {pid} to ResourceManager via IPC")
            
            # **Send PID forward message** (gửi tin nhắn chuyển tiếp PID)
            success = self._ipc_client.send_pid_forward(pid, metadata)
            
            if success:
                self._ipc_stats['messages_sent'] += 1
                self._ipc_stats['pid_forwards_sent'] += 1
                logger.info(f"✅ [IPC-SEND] PID {pid} sent successfully via IPC")
                return True
            else:
                self._ipc_stats['ipc_errors'] += 1
                logger.error(f"❌ [IPC-SEND] Failed to send PID {pid} via IPC")
                return False
                
        except Exception as e:
            logger.error(f"❌ [IPC-SEND] Error sending PID {pid} via IPC: {e}")
            self._ipc_stats['ipc_errors'] += 1
            return False
    
    def _cleanup_dead_processes(self) -> None:
        """
        **Cleanup Dead Processes** (dọn dẹp tiến trình đã chết)
        
        Kiểm tra và remove các processes không còn running từ registry.
        """
        try:
            with self._lock:
                dead_pids = []
                
                for pid, process_info in self._registry.items():
                    if not process_info.is_active:
                        continue
                    
                    # **Check if process is still running** (kiểm tra process còn chạy)
                    is_running = False
                    try:
                        # **Support both subprocess.Popen and psutil.Process** (hỗ trợ cả hai loại)
                        if hasattr(process_info.process_obj, 'poll'):
                            # subprocess.Popen object
                            is_running = process_info.process_obj.poll() is None
                        elif hasattr(process_info.process_obj, 'is_running'):
                            # psutil.Process object
                            is_running = process_info.process_obj.is_running()
                        else:
                            # **Fallback: check /proc filesystem** (dự phòng: kiểm tra hệ thống tệp /proc)
                            is_running = os.path.exists(f"/proc/{pid}")
                    except Exception as e:
                        logger.debug(f"⚠️ Error checking process {pid} status: {e}")
                        is_running = False
                    
                    if not is_running:
                        dead_pids.append(pid)
                        process_info.is_active = False
                        logger.info(f"🪦 Detected dead process: PID={pid}, Name={process_info.process_name}")
                
                # **Remove dead processes from registry** (xóa processes đã chết khỏi registry)
                for pid in dead_pids:
                    del self._registry[pid]
                
                if dead_pids:
                    self._stats['cleanup_runs'] += 1
                    self._stats['active_processes'] = len([p for p in self._registry.values() if p.is_active])
                    logger.info(f"🧹 Cleanup completed: Removed {len(dead_pids)} dead processes")
                
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        **Get Registry Statistics** (lấy thống kê registry)
        
        Returns:
            Dict chứa các thống kê về registry usage
        """
        with self._lock:
            return {
                **self._stats,
                'current_registry_size': len(self._registry),
                'active_observers': len(self._observers),
                'cleanup_interval': self._cleanup_interval
            }
    
    def shutdown(self) -> None:
        """
        **Shutdown Registry** (tắt registry)
        
        Cleanup resources và stop background threads.
        """
        logger.info("🔚 Shutting down DirectPIDRegistry...")
        
        # **Stop cleanup thread** (dừng luồng dọn dẹp)
        self._stop_cleanup.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        
        # **Clear observers** (xóa observers)
        with self._observer_lock:
            self._observers.clear()
        
        # **🔥 Cleanup IPC Client** (dọn dẹp IPC Client)
        if self._ipc_enabled and self._ipc_client:
            try:
                logger.info("🌉 [IPC-CLIENT] Shutting down IPC Bridge client...")
                # Note: IPCClient doesn't need explicit shutdown in current implementation
                self._ipc_client = None
                self._ipc_enabled = False
                logger.info("✅ [IPC-CLIENT] IPC Bridge client shutdown complete")
            except Exception as e:
                logger.error(f"❌ [IPC-CLIENT] Error shutting down IPC client: {e}")
        
        # **Clear registry** (xóa registry)
        with self._lock:
            self._registry.clear()
        
        logger.info("✅ DirectPIDRegistry shutdown completed")
    
    def execute_rollback(self, pid: int) -> bool:
        """
        **Execute Rollback** (thực thi rollback)
        
        Execute rollback actions for failed linear flow operations.
        
        Args:
            pid: Process ID to rollback
            
        Returns:
            bool: True if rollback successful
        """
        try:
            with self._lock:
                process_info = self._registry.get(pid)
                if not process_info:
                    logger.warning(f"⚠️ [ROLLBACK] No process info found for PID {pid}")
                    return False
                
                # Execute rollback actions in reverse order
                rollback_success = True
                for action in reversed(process_info.rollback_actions):
                    try:
                        action()
                        logger.debug(f"✅ [ROLLBACK] Rollback action executed for PID {pid}")
                    except Exception as e:
                        logger.error(f"❌ [ROLLBACK] Rollback action failed for PID {pid}: {e}")
                        rollback_success = False
                
                # Update coordination state
                process_info.coordination_state = "error" if not rollback_success else "registered"
                
                logger.info(f"🔄 [ROLLBACK] Rollback {'successful' if rollback_success else 'failed'} for PID {pid}")
                return rollback_success
                
        except Exception as e:
            logger.error(f"❌ [ROLLBACK] Rollback execution failed for PID {pid}: {e}")
            return False

# **🥈 SOLUTION 2: Acknowledgment Support Methods** (phương thức hỗ trợ acknowledgment)

def _send_acknowledgment_to_coordinator(registry_self, pid: int, timestamp: float, success: bool, error: str = None) -> None:
    """
    **🥈 SOLUTION 2: Send Acknowledgment to Coordinator** (gửi acknowledgment cho coordinator)
    
    Send acknowledgment back to HookCoordinator về handoff status.
    
    Args:
        registry_self: DirectPIDRegistry instance
        pid: Process ID
        timestamp: Timestamp của registry processing
        success: Whether processing was successful
        error: Error message if applicable
    """
    try:
        # **🥈 SOLUTION 2: Environment Variable-based Acknowledgment** (acknowledgment qua biến môi trường)
        ack_env_var = f"REGISTRY_ACK_PID_{pid}"
        
        if success:
            # **Success acknowledgment** (acknowledgment thành công)
            os.environ[ack_env_var] = str(timestamp)
            logger.debug(f"📤 [REGISTRY-ACK] Success acknowledgment sent to coordinator for PID {pid}")
        else:
            # **Failure acknowledgment with error** (acknowledgment thất bại với lỗi)
            import json
            ack_data = {
                'success': False,
                'timestamp': timestamp,
                'error': error or 'Unknown error',
                'source': 'direct_pid_registry'
            }
            os.environ[ack_env_var] = json.dumps(ack_data)
            logger.debug(f"📤 [REGISTRY-ACK] Failure acknowledgment sent to coordinator for PID {pid}: {error}")
        
        # **Schedule cleanup** (lên lịch dọn dẹp)
        # Clean up after 10 seconds to prevent environment variable buildup
        def cleanup_ack():
            time.sleep(10.0)
            os.environ.pop(ack_env_var, None)
        
        cleanup_thread = threading.Thread(target=cleanup_ack, daemon=True)
        cleanup_thread.start()
        
    except Exception as e:
        logger.error(f"❌ [REGISTRY-ACK] Error sending acknowledgment for PID {pid}: {e}")

def _send_chain_completion_acknowledgment(registry_self, pid: int, handoff_id: str) -> None:
    """
    **🥈 SOLUTION 2: Send Chain Completion Acknowledgment** (gửi acknowledgment hoàn thành chuỗi)
    
    Send acknowledgment về complete handoff chain success.
    
    Args:
        registry_self: DirectPIDRegistry instance
        pid: Process ID
        handoff_id: Unique handoff identifier
    """
    try:
        # **🥈 SOLUTION 2: Chain Completion Signal** (tín hiệu hoàn thành chuỗi)
        chain_ack_env_var = f"CHAIN_COMPLETE_PID_{pid}"
        import json
        completion_data = {
            'handoff_id': handoff_id,
            'timestamp': time.time(),
            'complete_chain': ['stealth_inference_cuda', 'hook_coordinator', 'direct_pid_registry', 'resource_manager'],
            'source': 'direct_pid_registry'
        }
        
        os.environ[chain_ack_env_var] = json.dumps(completion_data)
        logger.debug(f"📤 [CHAIN-ACK] Complete chain acknowledgment sent for PID {pid} (handoff_id: {handoff_id})")
        
        # **Schedule cleanup** (lên lịch dọn dẹp)
        # Clean up after 60 seconds to allow monitoring systems to read
        def cleanup_chain_ack():
            time.sleep(60.0)
            os.environ.pop(chain_ack_env_var, None)
        
        cleanup_thread = threading.Thread(target=cleanup_chain_ack, daemon=True)
        cleanup_thread.start()
        
    except Exception as e:
        logger.error(f"❌ [CHAIN-ACK] Error sending chain completion acknowledgment for PID {pid}: {e}")

# **Bind acknowledgment methods to DirectPIDRegistry class** (liên kết phương thức acknowledgment với lớp DirectPIDRegistry)
DirectPIDRegistry._send_acknowledgment_to_coordinator = lambda self, pid, timestamp, success, error=None: _send_acknowledgment_to_coordinator(self, pid, timestamp, success, error)
DirectPIDRegistry._send_chain_completion_acknowledgment = lambda self, pid, handoff_id: _send_chain_completion_acknowledgment(self, pid, handoff_id)

_registry_instance: Optional[DirectPIDRegistry] = None
_registry_lock = threading.Lock()

def get_direct_registry() -> DirectPIDRegistry:
    """
    **Get Direct Registry Singleton** (lấy singleton registry trực tiếp)
    
    Thread-safe singleton accessor cho DirectPIDRegistry.
    
    Returns:
        DirectPIDRegistry: Singleton instance
    """
    global _registry_instance
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = DirectPIDRegistry()
                logger.info("🏗️ Created DirectPIDRegistry singleton instance")
    
    return _registry_instance

def reset_direct_registry() -> None:
    """
    **Reset Direct Registry** (reset registry trực tiếp)
    
    Chỉ dùng cho testing. Reset singleton instance.
    """
    global _registry_instance
    with _registry_lock:
        if _registry_instance:
            _registry_instance.shutdown()
        _registry_instance = None
        logger.warning("🔄 DirectPIDRegistry singleton reset")