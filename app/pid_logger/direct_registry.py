"""
Direct PID Registry Access System
=================================

🎯 **Direct Registry Access Pattern** (mẫu truy cập registry trực tiếp)
Thay thế EventBus bằng direct function calls để cải thiện performance và simplicity.

Các tính năng chính:
- **Thread-safe operations** (thao tác an toàn luồng): RLock protection
- **Observer pattern** (mẫu quan sát): Plugin auto-discovery mechanism  
- **Centralized registry** (registry tập trung): Single source of truth cho process info
- **Immediate notifications** (thông báo tức thì): Direct callbacks thay thế async messaging

Usage:
    registry = get_direct_registry()
    registry.register_process(pid, "gpu", process_obj, "inference-cuda")
"""

import threading
import time
import logging
import psutil
import os
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# Setup logger
logger = logging.getLogger("direct_pid_registry")


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
        self._cleanup_interval = 60  # seconds
        self._cleanup_thread = None
        self._stop_cleanup = threading.Event()
        
        # **Registry statistics** (thống kê registry)
        self._stats = {
            'total_registered': 0,
            'active_processes': 0,
            'cleanup_runs': 0,
            'notifications_sent': 0
        }
        
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
            logger.info(f"🔄 [COORDINATOR-RECEIVE] Receiving PID {pid} from HookCoordinator")
            logger.debug(f"🔍 [COORDINATOR-RECEIVE] Coordinator metadata: {coordinator_metadata}")
            
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
                
                logger.info(f"✅ [COORDINATOR-RECEIVE] Registered process: PID={pid}, Name={process_name}")
                logger.info(f"🔗 [COORDINATOR-RECEIVE] Source chain: {' → '.join(source_chain)}")
            
            # **Forward to ResourceManager** (chuyển tiếp đến ResourceManager)
            rm_success = self._forward_to_resource_manager(pid, coordinator_metadata, process_info)
            
            if rm_success:
                logger.info(f"✅ [COORDINATOR-RECEIVE] Complete linear flow successful for PID {pid}")
                return True
            else:
                logger.warning(f"⚠️ [COORDINATOR-RECEIVE] ResourceManager forwarding failed for PID {pid}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [COORDINATOR-RECEIVE] Failed to receive from coordinator for PID {pid}: {e}")
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
                
                logger.info(f"✅ Registered process: PID={pid}, Type={process_type}, Name={process_info.process_name}")
                
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
    
    def _forward_to_resource_manager(self, pid: int, coordinator_metadata: Dict[str, Any], process_info: ProcessInfo) -> bool:
        """
        **Forward to ResourceManager** (chuyển tiếp đến ResourceManager)
        
        Final step trong linear flow: DirectPIDRegistry → ResourceManager
        
        Args:
            pid: Process ID
            coordinator_metadata: Metadata từ coordinator
            process_info: ProcessInfo object
            
        Returns:
            bool: True nếu forwarding successful
        """
        try:
            logger.info(f"🎯 [RM-FORWARD] Forwarding PID {pid} to ResourceManager (FINAL STEP)")
            
            # **Import ResourceManager** (nhập ResourceManager)
            import sys
            import os
            from pathlib import Path
            
            # Add scripts module to path
            scripts_path = Path(__file__).parent.parent / "mining_environment" / "scripts"
            if str(scripts_path) not in sys.path:
                sys.path.insert(0, str(scripts_path))
            
            try:
                from resource_manager import ResourceManager
                
                # **Get ResourceManager singleton** (lấy singleton ResourceManager)
                rm_instance = ResourceManager._instance
                if not rm_instance:
                    logger.warning(f"⚠️ [RM-FORWARD] ResourceManager instance not yet created")
                    return False
                
                # **Enhanced metadata for ResourceManager** (metadata nâng cao cho ResourceManager)
                rm_metadata = {
                    **coordinator_metadata,  # Include all previous metadata
                    'registry_timestamp': time.time(),
                    'source_chain': coordinator_metadata.get('source_chain', []) + ['direct_registry'],
                    'final_handoff': True,
                    'process_info': {
                        'pid': pid,
                        'process_type': process_info.process_type,
                        'process_name': process_info.process_name,
                        'registered_at': process_info.registered_at
                    }
                }
                
                # **Call ResourceManager receive method** (gọi phương thức receive của ResourceManager)
                if hasattr(rm_instance, 'receive_from_registry'):
                    success = rm_instance.receive_from_registry(pid, rm_metadata)
                    
                    if success:
                        logger.info(f"✅ [RM-FORWARD] ResourceManager receive successful for PID {pid}")
                        
                        # **Notify observers** (thông báo observers)
                        self._notify_observers(process_info)
                        
                        return True
                    else:
                        logger.error(f"❌ [RM-FORWARD] ResourceManager receive failed for PID {pid}")
                        return False
                else:
                    logger.warning(f"⚠️ [RM-FORWARD] ResourceManager missing receive_from_registry method")
                    
                    # **Fallback: Notify observers directly** (dự phòng: thông báo observers trực tiếp)
                    self._notify_observers(process_info)
                    logger.info(f"🔄 [RM-FORWARD] Fallback notification completed for PID {pid}")
                    return True
                    
            except ImportError as import_err:
                logger.error(f"❌ [RM-FORWARD] Cannot import ResourceManager: {import_err}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [RM-FORWARD] Failed to forward to ResourceManager for PID {pid}: {e}")
            return False
    
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
            import sys
            import os
            from pathlib import Path
            
            # Add coordination module to path
            coordination_path = Path(__file__).parent.parent / "mining_environment" / "coordination"
            if str(coordination_path) not in sys.path:
                sys.path.insert(0, str(coordination_path))
            
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

# **Singleton pattern implementation** (triển khai mẫu singleton)
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