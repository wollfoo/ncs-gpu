"""
IPC Bridge Infrastructure for Cross-Process Communication
=======================================================

Queue-based cross-process communication solution để khắc phục Cross-Process Singleton Access Failure
trong GPU mining system. Cung cấp reliable message passing giữa subprocess và main process.

Key Features:
- Queue-based reliable message passing
- Thread-safe operations với timeout support
- Error recovery mechanisms và graceful degradation
- High-performance design (target: 1-5ms latency)
- Comprehensive logging và monitoring

Architecture:
- IPC Server (chạy trong main process) 
- IPC Client (chạy trong subprocess)
- Message queue với priority support
- Callback-based message handling
- Automatic retry logic với exponential backoff

Usage:
    # Server side (main process)
    server = IPCServer()
    server.register_callback('pid_forward', handle_pid_callback)
    server.start()
    
    # Client side (subprocess) 
    client = IPCClient()
    client.send_message('pid_forward', {'pid': 704, 'metadata': {...}})
"""

import threading
import queue
import time
import json
import logging
import traceback
import uuid
import os
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Setup logger
logger = logging.getLogger("ipc_bridge")
# Ensure logging configured even when main app chưa gọi setup_logging()
try:
    from mining_environment.scripts.logging_config import setup_logging as _internal_setup_logging  # type: ignore
    _internal_setup_logging()
except Exception:
    # Fallback basicConfig nếu không import được logging_config
    logging.basicConfig(level=logging.INFO)

# Global reference tới IPCServer đang chạy trong process (nếu có)
_GLOBAL_ACTIVE_SERVER = None  # type: Optional["IPCServer"]

class IPCMessageType(Enum):
    """**IPC Message Types** (các loại tin nhắn IPC)"""
    PID_FORWARD = "pid_forward"
    STATUS_CHECK = "status_check" 
    SHUTDOWN = "shutdown"
    HEARTBEAT = "heartbeat"
    ACKNOWLEDGMENT = "acknowledgment"

class IPCPriority(Enum):
    """**IPC Message Priority** (độ ưu tiên tin nhắn IPC)"""
    LOW = 3
    NORMAL = 2 
    HIGH = 1
    CRITICAL = 0

@dataclass
class IPCMessage:
    """
    **IPC Message Model** (mô hình tin nhắn IPC)
    
    Cấu trúc tin nhắn chuẩn cho cross-process communication.
    """
    message_id: str
    message_type: IPCMessageType
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    priority: IPCPriority = IPCPriority.NORMAL
    source_process: str = "unknown"
    target_process: str = "main"
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: float = 5.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'message_id': self.message_id,
            'message_type': self.message_type.value,
            'payload': self.payload,
            'timestamp': self.timestamp,
            'priority': self.priority.value,
            'source_process': self.source_process,
            'target_process': self.target_process,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'timeout_seconds': self.timeout_seconds
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCMessage':
        """Create from dictionary"""
        return cls(
            message_id=data['message_id'],
            message_type=IPCMessageType(data['message_type']),
            payload=data['payload'],
            timestamp=data.get('timestamp', time.time()),
            priority=IPCPriority(data.get('priority', IPCPriority.NORMAL.value)),
            source_process=data.get('source_process', 'unknown'),
            target_process=data.get('target_process', 'main'),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3),
            timeout_seconds=data.get('timeout_seconds', 5.0)
        )

class IPCBridgeConfig:
    """**IPC Bridge Configuration** (cấu hình IPC Bridge)"""
    
    # **Queue Configuration** (cấu hình queue)
    MAX_QUEUE_SIZE = 1000
    MESSAGE_TIMEOUT = 5.0  # seconds
    HEARTBEAT_INTERVAL = 10.0  # seconds
    
    # **Retry Configuration** (cấu hình thử lại)
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 0.1  # 100ms
    BACKOFF_MULTIPLIER = 2.0
    MAX_RETRY_DELAY = 2.0  # 2 seconds
    
    # **Performance Targets** (mục tiêu hiệu suất)
    TARGET_LATENCY_MS = 5.0  # 5ms target
    WARNING_LATENCY_MS = 10.0  # 10ms warning
    CRITICAL_LATENCY_MS = 50.0  # 50ms critical
    
    # **File-based IPC Configuration** (cấu hình IPC dựa trên file)
    IPC_DIRECTORY = Path("/tmp/ncs_ipc_bridge")
    MESSAGE_FILE_PREFIX = "ipc_msg_"
    MESSAGE_FILE_SUFFIX = ".json"
    FILE_CLEANUP_AGE = 120  # giảm tuổi file xuống 2 phút để tránh rác khi TPS cao  # 5 minutes
    
    # **Process Identification** (nhận dạng process)
    MAIN_PROCESS_ID = "main_resource_manager"
    SUBPROCESS_PREFIX = "subprocess_"

class IPCBridgeError(Exception):
    """**Base IPC Bridge Exception** (exception cơ bản IPC Bridge)"""
    pass

class IPCTimeoutError(IPCBridgeError):
    """**IPC Timeout Exception** (exception timeout IPC)"""
    pass

class IPCConnectionError(IPCBridgeError):
    """**IPC Connection Exception** (exception kết nối IPC)"""
    pass

def _ensure_ipc_directory() -> bool:
    """**Ensure IPC Directory Exists** (đảm bảo thư mục IPC tồn tại)"""
    try:
        IPCBridgeConfig.IPC_DIRECTORY.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Force directory permissions to 0700 (owner rwx only) for security
        try:
            os.chmod(IPCBridgeConfig.IPC_DIRECTORY, 0o700)
        except Exception as chmod_err:
            logger.warning(f"⚠️ [IPC-SETUP] Could not set directory permissions (không thể đặt quyền thư mục – lỗi phân quyền): {chmod_err}")
        
        # Test write permissions
        test_file = IPCBridgeConfig.IPC_DIRECTORY / f".test_{uuid.uuid4().hex[:8]}"
        try:
            test_file.write_text("test")
            test_file.unlink()
            logger.debug(f"✅ [IPC-SETUP] Directory ready (thư mục sẵn sàng – đường dẫn IPC): {IPCBridgeConfig.IPC_DIRECTORY}")
            return True
        except Exception as perm_err:
            logger.error(f"❌ [IPC-SETUP] Directory not writable (thư mục không ghi được – thiếu quyền ghi): {perm_err}")
            return False
            
    except Exception as e:
        logger.error(f"❌ [IPC-SETUP] Failed to ensure IPC directory (không đảm bảo được thư mục IPC – lỗi khởi tạo): {e}")
        return False

class IPCServer:
    """
    **IPC Server** (máy chủ IPC)
    
    Chạy trong main process để nhận messages từ subprocesses.
    Sử dụng priority queue và callback-based message handling.
    """
    
    def __init__(self, process_id: str = IPCBridgeConfig.MAIN_PROCESS_ID):
        """Initialize IPC Server"""
        self.process_id = process_id
        self.logger = logging.getLogger("ipc_bridge.server")
        
        # **🔥 PRODUCTION FIX: Ensure IPC directory exists** (đảm bảo thư mục IPC tồn tại - khắc phục production)
        if not _ensure_ipc_directory():
            self.logger.error("❌ [IPC-SERVER] Failed to create IPC directory (không tạo được thư mục IPC - lỗi khởi tạo)")
            # **Fallback to /var/tmp if /tmp fails** (chuyển sang /var/tmp nếu /tmp thất bại)
            IPCBridgeConfig.IPC_DIRECTORY = Path("/var/tmp/ncs_ipc_bridge")
            if not _ensure_ipc_directory():
                raise RuntimeError("Cannot create IPC directory in any location (không thể tạo thư mục IPC ở bất kỳ đâu)")
            self.logger.warning(f"⚠️ [IPC-SERVER] Using fallback directory: {IPCBridgeConfig.IPC_DIRECTORY}")
        else:
            self.logger.info(f"✅ [IPC-SERVER] IPC directory ready: {IPCBridgeConfig.IPC_DIRECTORY}")
        
        # **Message queue với priority support** (hàng đợi tin nhắn có hỗ trợ ưu tiên)
        self._message_queue = queue.PriorityQueue(maxsize=IPCBridgeConfig.MAX_QUEUE_SIZE)
        
        # **Message callbacks** (callbacks xử lý tin nhắn)
        self._callbacks = {}  # type: Dict[IPCMessageType, Callable[[IPCMessage], bool]]
        
        # **Thread management** (quản lý luồng)
        self._worker_thread = None  # type: Optional[threading.Thread]
        self._file_monitor_thread = None  # type: Optional[threading.Thread]
        self._shutdown_event = threading.Event()
        self._ready_event = threading.Event()
        
        # **Statistics tracking** (theo dõi thống kê)
        self._statistics = {
            'messages_received': 0,
            'messages_processed': 0,
            'messages_failed': 0,
            'total_latency_ms': 0.0,
            'max_latency_ms': 0.0
        }
        
        self.logger.info(f"🚀 [IPC-SERVER] Initialized for process: {self.process_id}")

    def register_callback(self, message_type: IPCMessageType, callback: Callable[[IPCMessage], bool]) -> bool:
        """
        **Register Message Callback** (đăng ký callback tin nhắn)
        
        Args:
            message_type: Loại tin nhắn cần xử lý
            callback: Function callback nhận IPCMessage và trả về bool (success)
            
        Returns:
            bool: True nếu đăng ký thành công
        """
        try:
            with threading.Lock():
                if message_type not in self._callbacks:
                    self._callbacks[message_type] = []
                
                if callback not in self._callbacks[message_type]:
                    self._callbacks[message_type].append(callback)
                    self.logger.info(f"✅ [IPC-SERVER] Callback registered (đã đăng ký callback – hàm xử lý) for {message_type.value}")
                    return True
                else:
                    self.logger.warning(f"⚠️ [IPC-SERVER] Callback already registered (callback đã tồn tại – trùng đăng ký) for {message_type.value}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"❌ [IPC-SERVER] Failed to register callback (đăng ký callback thất bại – lỗi cấu hình): {e}")
            return False
    
    def start(self) -> bool:
        """
        **Start IPC Server** (khởi động máy chủ IPC)
        
        Returns:
            bool: True nếu khởi động thành công
        """
        try:
            if self._worker_thread and self._worker_thread.is_alive():
                self.logger.warning("⚠️ [IPC-SERVER] Server already started (máy chủ đã khởi động – trạng thái đang chạy)")
                return True
            
            self.logger.info("🚀 [IPC-SERVER] Starting IPC Server (đang khởi động máy chủ IPC – bắt đầu phục vụ)...")
            
            # **Start Worker Thread** (khởi động worker thread)
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="IPCServer-Worker",
                daemon=True
            )
            self._worker_thread.start()
            
            # **Start File Monitor Thread** (khởi động file monitor thread)
            self._file_monitor_thread = threading.Thread(
                target=self._file_monitor_loop,
                name="IPCServer-FileMonitor",
                daemon=True
            )
            self._file_monitor_thread.start()
            
            # **Update Statistics** (cập nhật thống kê)
            self._statistics['server_start_time'] = time.time()
            
            self.logger.info(f"✅ [IPC-SERVER] Server started successfully (máy chủ đã khởi động thành công – dịch vụ sẵn sàng)")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [IPC-SERVER] Failed to start server (khởi động máy chủ thất bại – lỗi runtime): {e}")
            return False
    
    def stop(self) -> None:
        """**Stop IPC Server** (dừng máy chủ IPC)"""
        self.logger.info("🔚 [IPC-SERVER] Stopping IPC Server (đang dừng máy chủ IPC – kết thúc phục vụ)...")
        
        self._shutdown_event.set()
        
        # **Wait for Worker** (chờ worker)
        if self._worker_thread and self._worker_thread.is_alive():
            try:
                self._worker_thread.join(timeout=2.0)
                if self._worker_thread.is_alive():
                    self.logger.warning(f"⚠️ [IPC-SERVER] Worker still alive (luồng xử lý vẫn còn chạy – chưa dừng)")
            except Exception as e:
                self.logger.error(f"❌ [IPC-SERVER] Error joining worker: {e}")
        
        # **Wait for File Monitor** (chờ file monitor)
        if self._file_monitor_thread and self._file_monitor_thread.is_alive():
            try:
                self._file_monitor_thread.join(timeout=2.0)
            except Exception as e:
                self.logger.error(f"❌ [IPC-SERVER] Error joining file monitor (lỗi chờ luồng giám sát file – join thất bại): {e}")
        
        self.logger.info("✅ [IPC-SERVER] Server stopped (máy chủ đã dừng – dịch vụ kết thúc)")
    
    def send_message_to_queue(self, message: IPCMessage) -> bool:
        """
        **Send Message to Processing Queue** (gửi tin nhắn vào queue xử lý)
        
        Args:
            message: IPCMessage cần xử lý
            
        Returns:
            bool: True nếu queued thành công
        """
        try:
            if not self._worker_thread or not self._worker_thread.is_alive():
                self.logger.warning("⚠️ [IPC-SERVER] Server not running, cannot queue message")
                return False
            
            # **Priority-based queuing** (queuing theo độ ưu tiên)
            priority_tuple = (message.priority.value, time.time(), message)
            
            try:
                self._message_queue.put(priority_tuple, block=False)
                
                self._statistics['messages_received'] += 1
                
                self.logger.debug(f"📥 [IPC-SERVER] Message queued: {message.message_type.value} (id: {message.message_id[:8]})")
                return True
                
            except queue.Full:
                # Retry logic when queue is full
                retry_delay = 0.05  # 50 ms
                max_retries = 3
                for attempt in range(max_retries):
                    time.sleep(retry_delay * (attempt + 1))
                    try:
                        self._message_queue.put(priority_tuple, block=False)
                        self._statistics['messages_received'] += 1
                        self.logger.warning(f"⚠️ [IPC-SERVER] Queue was full (hàng đợi đầy – quá tải), succeeded on retry {attempt+1} (thành công ở lần thử {attempt+1})")
                        return True
                    except queue.Full:
                        continue
                self.logger.error(f"❌ [IPC-SERVER] Message queue full after {max_retries} retries (hàng đợi đầy sau {max_retries} lần thử – bỏ thông điệp): {message.message_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ [IPC-SERVER] Failed to queue message (xếp hàng thông điệp thất bại – lỗi đẩy vào queue): {e}")
            return False
    
    def _worker_loop(self) -> None:
        """**Worker Loop** (vòng lặp worker)"""
        self.logger.info("🔄 [IPC-WORKER] Started (worker đã khởi động – luồng xử lý sẵn sàng)")
        
        while not self._shutdown_event.is_set():
            try:
                # **Get Message with Timeout** (lấy tin nhắn với timeout)
                try:
                    priority, queued_time, message = self._message_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # **Calculate Queue Latency** (tính latency queue)
                queue_latency_ms = (time.time() - queued_time) * 1000
                
                # **Process Message** (xử lý tin nhắn)
                start_time = time.time()
                success = self._process_message(message)
                processing_time_ms = (time.time() - start_time) * 1000
                
                total_latency_ms = queue_latency_ms + processing_time_ms
                
                # **Update Statistics** (cập nhật thống kê)
                self._statistics['messages_processed'] += 1
                self._statistics['total_latency_ms'] += total_latency_ms
                self._statistics['max_latency_ms'] = max(self._statistics['max_latency_ms'], total_latency_ms)
                
                # **Performance Monitoring** (giám sát hiệu suất)
                if total_latency_ms > IPCBridgeConfig.CRITICAL_LATENCY_MS:
                    self.logger.warning(f"🐌 [IPC-PERF] Critical latency (độ trễ nghiêm trọng – vượt ngưỡng): {total_latency_ms:.1f}ms for message {message.message_id[:8]}")
                elif total_latency_ms > IPCBridgeConfig.WARNING_LATENCY_MS:
                    self.logger.debug(f"⚡ [IPC-PERF] Warning latency (độ trễ cảnh báo – gần ngưỡng): {total_latency_ms:.1f}ms for message {message.message_id[:8]}")
                
                self._message_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"❌ [IPC-WORKER] Processing error (lỗi xử lý – sự cố worker): {e}")
                self.logger.debug(f"🔍 [IPC-WORKER] Traceback: {traceback.format_exc()}")
                time.sleep(0.1)  # Brief pause on error
        
        self.logger.info("🔚 [IPC-WORKER] Stopped (worker đã dừng – luồng xử lý kết thúc)")
    
    def _process_message(self, message: IPCMessage) -> bool:
        """
        **Process Single Message** (xử lý tin nhắn đơn)
        
        Args:
            message: IPCMessage cần xử lý
            
        Returns:
            bool: True nếu xử lý thành công
        """
        try:
            self.logger.debug(f"🎯 [IPC-PROCESS] Processing message (đang xử lý thông điệp – thực thi callback): {message.message_type.value} (id: {message.message_id[:8]})")
            
            # **Find Callbacks** (tìm callbacks)
            callbacks = self._callbacks.get(message.message_type, [])
            
            if not callbacks:
                self.logger.warning(f"⚠️ [IPC-PROCESS] No callbacks registered (chưa đăng ký callback – thiếu hàm xử lý) for {message.message_type.value}")
                return False
            
            # **Execute Callbacks** (thực thi callbacks)
            success_count = 0
            for callback in callbacks:
                try:
                    callback_start = time.time()
                    result = callback(message)
                    callback_duration_ms = (time.time() - callback_start) * 1000
                    
                    if result:
                        success_count += 1
                        self.logger.debug(f"✅ [IPC-CALLBACK] Callback successful (callback thành công – thời gian {callback_duration_ms:.1f}ms)")
                    else:
                        self.logger.warning(f"❌ [IPC-CALLBACK] Callback returned False (callback trả về False – xử lý không thành công)")
                        
                    self._statistics['callbacks_executed'] += 1
                        
                except Exception as callback_error:
                    self.logger.error(f"❌ [IPC-CALLBACK] Callback exception (ngoại lệ trong callback – lỗi hàm xử lý): {callback_error}")
                    self.logger.debug(f"🔍 [IPC-CALLBACK] Callback traceback: {traceback.format_exc()}")
            
            # **Success if any callback succeeded** (thành công nếu bất kỳ callback nào thành công)
            overall_success = success_count > 0
            
            self.logger.debug(f"📊 [IPC-PROCESS] Message processed (đã xử lý thông điệp – kết quả): {success_count}/{len(callbacks)} callbacks successful (số callback thành công)")
            return overall_success
            
        except Exception as e:
            self.logger.error(f"❌ [IPC-PROCESS] Message processing failed (xử lý thông điệp thất bại – lỗi chạy): {e}")
            return False
    
    def _file_monitor_loop(self) -> None:
        """
        **File Monitor Loop** (vòng lặp giám sát file)
        
        Monitor file-based messages from subprocesses as fallback communication method.
        """
        self.logger.info("🔍 [IPC-MONITOR] File monitor started (trình giám sát file đã khởi động – theo dõi thông điệp qua tệp)")
        
        while not self._shutdown_event.is_set():
            try:
                if not IPCBridgeConfig.IPC_DIRECTORY.exists():
                    time.sleep(1.0)
                    continue
                
                # **Scan for Message Files** (quét các file tin nhắn)
                message_files = list(IPCBridgeConfig.IPC_DIRECTORY.glob(
                    f"{IPCBridgeConfig.MESSAGE_FILE_PREFIX}*{IPCBridgeConfig.MESSAGE_FILE_SUFFIX}"
                ))
                
                for message_file in message_files:
                    try:
                        self._process_message_file(message_file)
                    except Exception as file_error:
                        self.logger.error(f"❌ [IPC-MONITOR] Error processing file (lỗi xử lý tệp tin – không đọc được) {message_file.name}: {file_error}")
                
                # **Cleanup Old Files** (dọn dẹp file cũ)
                self._cleanup_old_message_files()
                
                time.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                self.logger.error(f"❌ [IPC-MONITOR] File monitor error (lỗi trình giám sát file – sự cố nền): {e}")
                time.sleep(2.0)
        
        self.logger.info("🔚 [IPC-MONITOR] File monitor stopped (trình giám sát file đã dừng – ngừng theo dõi)")
    
    def _process_message_file(self, message_file: Path) -> None:
        """
        **Process Message File** (xử lý file tin nhắn)
        
        Args:
            message_file: Path to message file
        """
        try:
            # **Read and Parse Message** (đọc và phân tích tin nhắn)
            with open(message_file, 'r') as f:
                file_data = json.load(f)
            
            # **Create IPCMessage** (tạo IPCMessage)
            message = IPCMessage.from_dict(file_data)
            
            # **Queue Message for Processing** (queue tin nhắn để xử lý)
            queued = self.send_message_to_queue(message)
            
            if queued:
                self.logger.debug(f"📁 [IPC-MONITOR] File message queued (đã xếp hàng thông điệp từ tệp): {message_file.name}")
                
                # **Remove Processed File** (xóa file đã xử lý)
                try:
                    message_file.unlink()
                    self.logger.debug(f"🗑️ [IPC-MONITOR] Cleaned up file (đã dọn tệp): {message_file.name}")
                except Exception as cleanup_error:
                    self.logger.warning(f"⚠️ [IPC-MONITOR] Failed to cleanup file {message_file.name}: {cleanup_error}")
            else:
                self.logger.warning(f"❌ [IPC-MONITOR] Failed to queue file message (không thể xếp hàng thông điệp từ tệp): {message_file.name}")
                
        except Exception as e:
            self.logger.error(f"❌ [IPC-MONITOR] Failed to process message file (xử lý tệp thông điệp thất bại – lỗi đọc/ghi) {message_file.name}: {e}")
    
    def _cleanup_old_message_files(self) -> None:
        """**Cleanup Old Message Files** (dọn dẹp file tin nhắn cũ)"""
        try:
            current_time = time.time()
            cleanup_count = 0
            
            for file_path in IPCBridgeConfig.IPC_DIRECTORY.glob(f"{IPCBridgeConfig.MESSAGE_FILE_PREFIX}*{IPCBridgeConfig.MESSAGE_FILE_SUFFIX}"):
                try:
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > IPCBridgeConfig.FILE_CLEANUP_AGE:
                        file_path.unlink()
                        cleanup_count += 1
                        self.logger.debug(f"🧹 [IPC-CLEANUP] Removed old file (đã xóa tệp cũ – dọn dẹp): {file_path.name} (age: {file_age:.1f}s)")
                except Exception as file_err:
                    self.logger.debug(f"⚠️ [IPC-CLEANUP] Could not process file (không thể xử lý tệp – lỗi quyền/định dạng) {file_path.name}: {file_err}")
            
            if cleanup_count > 0:
                self.logger.debug(f"🧹 [IPC-CLEANUP] Cleaned up (đã dọn dẹp – xóa tệp cũ) {cleanup_count} old message files")
                
        except Exception as e:
            self.logger.error(f"❌ [IPC-CLEANUP] Cleanup failed (dọn dẹp thất bại – lỗi xóa tệp): {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """**Get Server Statistics** (lấy thống kê máy chủ)"""
        statistics = self._statistics.copy()
        
        statistics.update({
            'is_running': self._worker_thread and self._worker_thread.is_alive(),
            'is_started': True,
            'queue_size': self._message_queue.qsize(),
            'worker_count': 1,
            'callback_count': sum(len(callbacks) for callbacks in self._callbacks.values()),
            'uptime_seconds': time.time() - statistics['server_start_time'] if statistics['server_start_time'] else 0
        })
        
        return statistics

class IPCClient:
    """
    **IPC Client** (client IPC)
    
    Chạy trong subprocess để gửi messages tới main process.
    Supports both direct queue messaging và file-based fallback.
    """
    
    def __init__(self, process_id: str = None):
        """Initialize IPC Client"""
        self.process_id = process_id or f"{IPCBridgeConfig.SUBPROCESS_PREFIX}{os.getpid()}"
        self.logger = logging.getLogger("ipc_bridge.client")
        
        # **🔥 PRODUCTION FIX: Ensure IPC directory exists for client** (đảm bảo thư mục IPC cho client)
        if not _ensure_ipc_directory():
            self.logger.warning("⚠️ [IPC-CLIENT] IPC directory not available, using fallback (thư mục IPC không khả dụng - dùng dự phòng)")
            # Client vẫn có thể hoạt động qua file-based fallback
        
        # **Try to connect to server queue** (cố gắng kết nối tới server queue)
        self._server_queue = None  # type: Optional[queue.Queue]
        self._try_connect_to_server()
        
        # **Message retry tracking** (theo dõi retry tin nhắn)
        self._retry_tracker = {}  # type: Dict[str, int]
        
        self.logger.info(f"🚀 [IPC-CLIENT] Initialized for process: {self.process_id}")

    def send_message(self, message_type: IPCMessageType, payload: Dict[str, Any], 
                    priority: IPCPriority = IPCPriority.NORMAL, 
                    timeout: float = IPCBridgeConfig.MESSAGE_TIMEOUT) -> bool:
        """
        **Send Message** (gửi tin nhắn)
        
        Args:
            message_type: Loại tin nhắn
            payload: Nội dung tin nhắn
            priority: Độ ưu tiên tin nhắn
            timeout: Timeout cho tin nhắn
            
        Returns:
            bool: True nếu gửi thành công
        """
        try:
            # **Create Message** (tạo tin nhắn)
            message = IPCMessage(
                message_id=str(uuid.uuid4()),
                message_type=message_type,
                payload=payload,
                priority=priority,
                source_process=self.process_id,
                timeout_seconds=timeout
            )
            
            logger.debug(f"📤 [IPC-CLIENT] Sending message: {message_type.value} (id: {message.message_id[:8]})")
            
            # **Try In-Process Queue First** (nếu server sống trong cùng process)
            if _GLOBAL_ACTIVE_SERVER and _GLOBAL_ACTIVE_SERVER.is_running:
                if self._send_via_queue(_GLOBAL_ACTIVE_SERVER, message):
                    logger.debug(f"✅ [IPC-CLIENT] Message queued in-process: {message.message_id[:8]}")
                    return True
                logger.debug("⚠️ [IPC-CLIENT] Queue path failed or full – fallback file")
            # **Try File-Based Communication** (fallback cross-process)
            # Trong cross-process scenario, file-based là most reliable
            success = self._send_via_file(message)
            
            if success:
                logger.debug(f"✅ [IPC-CLIENT] Message sent successfully via file: {message.message_id[:8]}")
                return True
            else:
                logger.warning(f"❌ [IPC-CLIENT] Failed to send message: {message.message_id[:8]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [IPC-CLIENT] Error sending message: {e}")
            return False
    
    def _send_via_queue(self, server_ref, message: "IPCMessage") -> bool:
        """Attempt to queue message directly if server in same process"""
        try:
            max_retries = 3
            retry_delay = 0.05
            for attempt in range(max_retries):
                queued = server_ref.send_message_to_queue(message)
                if queued:
                    return True
                time.sleep(retry_delay * (attempt + 1))
            return False
        except Exception as err:
            logger.debug(f"Queue send failed: {err} (gửi qua queue thất bại – lỗi: {err})")
            return False

    def _send_via_file(self, message: IPCMessage) -> bool:
        """
        **Send Message via File** (gửi tin nhắn qua file)
        
        File-based message passing for cross-process communication.
        
        Args:
            message: IPCMessage cần gửi
            
        Returns:
            bool: True nếu gửi thành công
        """
        try:
            # **Ensure IPC Directory** (đảm bảo thư mục IPC)
            if not _ensure_ipc_directory():
                return False
            
            # **Create Message File** (tạo file tin nhắn)
            message_filename = f"{IPCBridgeConfig.MESSAGE_FILE_PREFIX}{message.message_id}{IPCBridgeConfig.MESSAGE_FILE_SUFFIX}"
            message_file = IPCBridgeConfig.IPC_DIRECTORY / message_filename
            
            # **Atomic Write** (ghi nguyên tử)
            temp_file = IPCBridgeConfig.IPC_DIRECTORY / f".tmp_{message.message_id}"
            
            try:
                with open(temp_file, 'w') as f:
                    json.dump(message.to_dict(), f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                
                # **Atomic Move** (di chuyển nguyên tử)
                temp_file.rename(message_file)
                
                logger.debug(f"📁 [IPC-CLIENT] Message file written: {message_filename}")
                return True
                
            except Exception as write_error:
                # **Cleanup on Error** (dọn dẹp khi lỗi)
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except Exception:
                    pass
                raise write_error
                
        except Exception as e:
            logger.error(f"❌ [IPC-CLIENT] File-based send failed: {e} (gửi qua file thất bại – lỗi: {e})")
            return False
    
    def send_pid_forward(self, pid: int, metadata: Dict[str, Any]) -> bool:
        """
        **Send PID Forward Message** (gửi tin nhắn chuyển tiếp PID)
        
        Convenience method để gửi PID forward message với metadata.
        
        Args:
            pid: Process ID cần forward
            metadata: Process metadata
            
        Returns:
            bool: True nếu gửi thành công
        """
        try:
            payload = {
                'pid': pid,
                'metadata': metadata,
                'timestamp': time.time(),
                'source': 'direct_registry_ipc'
            }
            
            return self.send_message(
                message_type=IPCMessageType.PID_FORWARD,
                payload=payload,
                priority=IPCPriority.HIGH  # PID forwards có priority cao
            )
            
        except Exception as e:
            logger.error(f"❌ [IPC-CLIENT] Error sending PID forward: {e}")
            return False

# **Utility Functions** (các hàm tiện ích)

def create_ipc_server() -> "IPCServer":
    """Create IPC Server Instance và lưu global reference"""
    global _GLOBAL_ACTIVE_SERVER
    server = IPCServer()
    _GLOBAL_ACTIVE_SERVER = server
    return server
    """**Create IPC Server Instance** (tạo instance máy chủ IPC)"""
    return IPCServer()

def create_ipc_client(process_id: str = None) -> IPCClient:
    """**Create IPC Client Instance** (tạo instance client IPC)"""
    return IPCClient(process_id=process_id)

def test_ipc_bridge() -> bool:
    """
    **Test IPC Bridge Functionality** (kiểm tra chức năng IPC Bridge)
    
    Basic functionality test cho IPC Bridge system.
    
    Returns:
        bool: True nếu test thành công
    """
    try:
        logger.info("🧪 [IPC-TEST] Starting IPC Bridge test... (bắt đầu kiểm thử IPC Bridge)")
        
        # **Test Message Creation** (kiểm tra tạo tin nhắn)
        test_message = IPCMessage(
            message_id="test_001",
            message_type=IPCMessageType.PID_FORWARD,
            payload={'pid': 12345, 'test': True}
        )
        
        # **Test Serialization** (kiểm tra tuần tự hóa)
        message_dict = test_message.to_dict()
        restored_message = IPCMessage.from_dict(message_dict)
        
        if restored_message.message_id != test_message.message_id:
            logger.error("❌ [IPC-TEST] Message serialization failed")
            return False
        
        # **Test Directory Creation** (kiểm tra tạo thư mục)
        if not _ensure_ipc_directory():
            logger.error("❌ [IPC-TEST] Directory creation failed")
            return False
        
        logger.info("✅ [IPC-TEST] IPC Bridge basic test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ [IPC-TEST] Test failed: {e}")
        return False

if __name__ == "__main__":
    # **Basic Test** (kiểm tra cơ bản)
    logging.basicConfig(level=logging.DEBUG)
    test_result = test_ipc_bridge()
    print(f"IPC Bridge Test Result: {'PASS' if test_result else 'FAIL'}")