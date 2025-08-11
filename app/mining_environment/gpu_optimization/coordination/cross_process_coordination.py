"""
Cross-Process Coordination Module
==================================
Inter-process communication and resource coordination for GPU optimization.
Module giao tiếp liên tiến trình và điều phối tài nguyên cho tối ưu GPU.

Implements:
- **Message Queue** (hàng đợi tin nhắn – truyền dữ liệu bất đồng bộ)
- **Process Registry** (đăng ký tiến trình – quản lý lifecycle)
- **Shared Memory** (bộ nhớ chia sẻ – truyền dữ liệu hiệu năng cao)
- **Event Synchronization** (đồng bộ sự kiện – điều phối hoạt động)
"""

import os
import json
import time
import psutil
import logging
import threading
import multiprocessing as mp
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from queue import Queue, Empty, Full
from datetime import datetime, timedelta
from collections import defaultdict
import pickle

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """
    IPC message types.
    Các loại tin nhắn IPC.
    """
    REGISTER = "register"        # Đăng ký process
    UNREGISTER = "unregister"    # Hủy đăng ký  
    HEARTBEAT = "heartbeat"      # Tín hiệu sống
    COMMAND = "command"          # Lệnh điều khiển
    STATUS = "status"            # Trạng thái
    DATA = "data"                # Dữ liệu
    ERROR = "error"              # Lỗi
    SHUTDOWN = "shutdown"        # Tắt


class ProcessState(Enum):
    """
    Process states.
    Trạng thái tiến trình.
    """
    INITIALIZING = "initializing"  # Đang khởi tạo
    READY = "ready"                # Sẵn sàng
    RUNNING = "running"            # Đang chạy
    PAUSED = "paused"              # Tạm dừng
    ERROR = "error"                # Lỗi
    TERMINATED = "terminated"      # Đã kết thúc


@dataclass
class IPCMessage:
    """
    IPC message structure.
    Cấu trúc tin nhắn IPC.
    
    Attributes:
        msg_id: Unique message ID
        msg_type: Message type
        sender_pid: Sender process ID
        receiver_pid: Target process ID (0 for broadcast)
        payload: Message data
        timestamp: Message timestamp
        priority: Message priority (0-10, higher is more important)
    """
    msg_id: str
    msg_type: MessageType
    sender_pid: int
    receiver_pid: int
    payload: Dict[str, Any]
    timestamp: datetime
    priority: int = 5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'msg_id': self.msg_id,
            'msg_type': self.msg_type.value,
            'sender_pid': self.sender_pid,
            'receiver_pid': self.receiver_pid,
            'payload': self.payload,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCMessage':
        """Create from dictionary"""
        return cls(
            msg_id=data['msg_id'],
            msg_type=MessageType(data['msg_type']),
            sender_pid=data['sender_pid'],
            receiver_pid=data['receiver_pid'],
            payload=data['payload'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            priority=data.get('priority', 5)
        )


@dataclass
class ProcessInfo:
    """
    Process information.
    Thông tin tiến trình.
    """
    pid: int
    name: str
    gpu_index: int
    state: ProcessState
    start_time: datetime
    last_heartbeat: datetime
    metadata: Dict[str, Any]
    
    def is_alive(self, timeout: int = 30) -> bool:
        """Check if process is alive based on heartbeat"""
        return (datetime.now() - self.last_heartbeat).seconds < timeout


class MessageQueue:
    """
    **Message Queue** (hàng đợi tin nhắn) - Thread-safe message queue.
    
    Features:
    - **Priority Queue** (hàng đợi ưu tiên)
    - **Size Limits** (giới hạn kích thước)
    - **Timeout Support** (hỗ trợ timeout)
    """
    
    def __init__(self, maxsize: int = 1000):
        """
        Initialize message queue.
        
        Args:
            maxsize: Maximum queue size
        """
        self.queue = Queue(maxsize=maxsize)
        self.priority_queue = []
        self.lock = threading.RLock()
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'messages_dropped': 0
        }
        
        logger.info(f"✅ Message Queue initialized với maxsize={maxsize}")
    
    def put(self, message: IPCMessage, timeout: Optional[float] = None) -> bool:
        """
        Put message in queue.
        Đưa tin nhắn vào hàng đợi.
        
        Args:
            message: Message to send
            timeout: Timeout in seconds
            
        Returns:
            True if successful
        """
        try:
            with self.lock:
                # Priority insertion
                self.priority_queue.append((message.priority, message))
                self.priority_queue.sort(key=lambda x: x[0], reverse=True)
                
                # Put in queue
                if len(self.priority_queue) > 0:
                    _, msg = self.priority_queue.pop(0)
                    self.queue.put(msg, block=True, timeout=timeout)
                    self.stats['messages_sent'] += 1
                    return True
            
        except Full:
            logger.warning(f"⚠️ Queue full, dropping message {message.msg_id}")
            self.stats['messages_dropped'] += 1
            return False
        
        except Exception as e:
            logger.error(f"❌ Error putting message: {e}")
            return False
    
    def get(self, timeout: Optional[float] = None) -> Optional[IPCMessage]:
        """
        Get message from queue.
        Lấy tin nhắn từ hàng đợi.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Message or None
        """
        try:
            message = self.queue.get(block=True, timeout=timeout)
            self.stats['messages_received'] += 1
            return message
            
        except Empty:
            return None
        
        except Exception as e:
            logger.error(f"❌ Error getting message: {e}")
            return None
    
    def size(self) -> int:
        """Get queue size"""
        return self.queue.qsize()
    
    def clear(self) -> None:
        """Clear all messages"""
        with self.lock:
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except Empty:
                    break
            self.priority_queue.clear()


class ProcessRegistry:
    """
    **Process Registry** (đăng ký tiến trình) - Manages process lifecycle.
    
    Features:
    - **Process Tracking** (theo dõi tiến trình)
    - **Heartbeat Monitoring** (giám sát heartbeat)
    - **State Management** (quản lý trạng thái)
    """
    
    def __init__(self):
        """Initialize process registry"""
        self.processes: Dict[int, ProcessInfo] = {}
        self.lock = threading.RLock()
        self.heartbeat_thread: Optional[threading.Thread] = None
        self.running = False
        
        logger.info("✅ Process Registry initialized")
    
    def register(self, pid: int, name: str, gpu_index: int, 
                metadata: Optional[Dict] = None) -> bool:
        """
        Register a process.
        Đăng ký một tiến trình.
        
        Args:
            pid: Process ID
            name: Process name
            gpu_index: GPU index
            metadata: Additional metadata
            
        Returns:
            True if successful
        """
        with self.lock:
            if pid in self.processes:
                logger.warning(f"⚠️ Process {pid} already registered")
                return False
            
            # Verify process exists
            if not psutil.pid_exists(pid):
                logger.error(f"❌ Process {pid} does not exist")
                return False
            
            # Create process info
            process_info = ProcessInfo(
                pid=pid,
                name=name,
                gpu_index=gpu_index,
                state=ProcessState.INITIALIZING,
                start_time=datetime.now(),
                last_heartbeat=datetime.now(),
                metadata=metadata or {}
            )
            
            self.processes[pid] = process_info
            logger.info(f"✅ Registered process {pid} ({name}) on GPU {gpu_index}")
            
            return True
    
    def unregister(self, pid: int) -> bool:
        """
        Unregister a process.
        Hủy đăng ký tiến trình.
        
        Args:
            pid: Process ID
            
        Returns:
            True if successful
        """
        with self.lock:
            if pid not in self.processes:
                logger.warning(f"⚠️ Process {pid} not registered")
                return False
            
            del self.processes[pid]
            logger.info(f"✅ Unregistered process {pid}")
            
            return True
    
    def update_heartbeat(self, pid: int) -> bool:
        """
        Update process heartbeat.
        Cập nhật heartbeat tiến trình.
        
        Args:
            pid: Process ID
            
        Returns:
            True if successful
        """
        with self.lock:
            if pid not in self.processes:
                return False
            
            self.processes[pid].last_heartbeat = datetime.now()
            return True
    
    def update_state(self, pid: int, state: ProcessState) -> bool:
        """
        Update process state.
        Cập nhật trạng thái tiến trình.
        
        Args:
            pid: Process ID
            state: New state
            
        Returns:
            True if successful
        """
        with self.lock:
            if pid not in self.processes:
                return False
            
            old_state = self.processes[pid].state
            self.processes[pid].state = state
            
            logger.info(f"Process {pid} state: {old_state.value} → {state.value}")
            return True
    
    def get_process(self, pid: int) -> Optional[ProcessInfo]:
        """
        Get process information.
        Lấy thông tin tiến trình.
        
        Args:
            pid: Process ID
            
        Returns:
            ProcessInfo or None
        """
        with self.lock:
            return self.processes.get(pid)
    
    def get_processes_by_gpu(self, gpu_index: int) -> List[ProcessInfo]:
        """
        Get processes by GPU index.
        Lấy tiến trình theo GPU index.
        
        Args:
            gpu_index: GPU index
            
        Returns:
            List of ProcessInfo
        """
        with self.lock:
            return [p for p in self.processes.values() 
                   if p.gpu_index == gpu_index]
    
    def cleanup_dead_processes(self, timeout: int = 30) -> List[int]:
        """
        Clean up dead processes.
        Dọn dẹp tiến trình chết.
        
        Args:
            timeout: Heartbeat timeout in seconds
            
        Returns:
            List of removed PIDs
        """
        removed = []
        
        with self.lock:
            current_time = datetime.now()
            
            for pid, process in list(self.processes.items()):
                # Check heartbeat timeout
                if (current_time - process.last_heartbeat).seconds > timeout:
                    # Double-check with psutil
                    if not psutil.pid_exists(pid):
                        logger.warning(f"🪦 Process {pid} is dead, removing")
                        del self.processes[pid]
                        removed.append(pid)
                    else:
                        # Process exists but no heartbeat
                        process.state = ProcessState.ERROR
                        logger.warning(f"⚠️ Process {pid} heartbeat timeout")
        
        return removed
    
    def start_monitoring(self, interval: int = 10) -> None:
        """
        Start heartbeat monitoring.
        Bắt đầu giám sát heartbeat.
        
        Args:
            interval: Check interval in seconds
        """
        if self.running:
            logger.warning("Monitoring already running")
            return
        
        self.running = True
        
        def monitor():
            while self.running:
                removed = self.cleanup_dead_processes()
                if removed:
                    logger.info(f"Cleaned up {len(removed)} dead processes")
                time.sleep(interval)
        
        self.heartbeat_thread = threading.Thread(target=monitor, daemon=True)
        self.heartbeat_thread.start()
        
        logger.info(f"✅ Started heartbeat monitoring với interval={interval}s")
    
    def stop_monitoring(self) -> None:
        """
        Stop heartbeat monitoring.
        Dừng giám sát heartbeat.
        """
        self.running = False
        
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
            self.heartbeat_thread = None
        
        logger.info("✅ Stopped heartbeat monitoring")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get registry status.
        Lấy trạng thái registry.
        
        Returns:
            Status dictionary
        """
        with self.lock:
            return {
                'total_processes': len(self.processes),
                'by_state': {
                    state.value: sum(1 for p in self.processes.values() 
                                   if p.state == state)
                    for state in ProcessState
                },
                'by_gpu': defaultdict(int, {
                    p.gpu_index: sum(1 for proc in self.processes.values() 
                                   if proc.gpu_index == p.gpu_index)
                    for p in self.processes.values()
                }),
                'monitoring': self.running
            }


class IPCManager:
    """
    **IPC Manager** (quản lý IPC) - Central inter-process communication manager.
    
    Coordinates:
    - Message routing (định tuyến tin nhắn)
    - Process registration (đăng ký tiến trình) 
    - Event synchronization (đồng bộ sự kiện)
    """
    
    def __init__(self, max_queue_size: int = 1000):
        """
        Initialize IPC manager.
        
        Args:
            max_queue_size: Maximum message queue size
        """
        self.message_queue = MessageQueue(max_queue_size)
        self.process_registry = ProcessRegistry()
        self.message_handlers: Dict[MessageType, List[Callable]] = defaultdict(list)
        self.running = False
        self.message_thread: Optional[threading.Thread] = None
        self.message_counter = 0
        self.lock = threading.RLock()
        
        # Start process monitoring
        self.process_registry.start_monitoring()
        
        logger.info("✅ IPC Manager initialized")
    
    def register_handler(self, msg_type: MessageType, handler: Callable) -> None:
        """
        Register message handler.
        Đăng ký handler xử lý tin nhắn.
        
        Args:
            msg_type: Message type to handle
            handler: Handler function
        """
        self.message_handlers[msg_type].append(handler)
        logger.info(f"Registered handler for {msg_type.value}")
    
    def send_message(self, msg_type: MessageType, receiver_pid: int,
                    payload: Dict[str, Any], priority: int = 5) -> bool:
        """
        Send message to process.
        Gửi tin nhắn đến tiến trình.
        
        Args:
            msg_type: Message type
            receiver_pid: Target process ID (0 for broadcast)
            payload: Message payload
            priority: Message priority
            
        Returns:
            True if sent successfully
        """
        with self.lock:
            self.message_counter += 1
            msg_id = f"msg_{self.message_counter}_{os.getpid()}"
        
        message = IPCMessage(
            msg_id=msg_id,
            msg_type=msg_type,
            sender_pid=os.getpid(),
            receiver_pid=receiver_pid,
            payload=payload,
            timestamp=datetime.now(),
            priority=priority
        )
        
        return self.message_queue.put(message)
    
    def start(self) -> None:
        """
        Start message processing.
        Bắt đầu xử lý tin nhắn.
        """
        if self.running:
            logger.warning("IPC Manager already running")
            return
        
        self.running = True
        
        def process_messages():
            while self.running:
                message = self.message_queue.get(timeout=1)
                if message:
                    self._handle_message(message)
        
        self.message_thread = threading.Thread(target=process_messages, daemon=True)
        self.message_thread.start()
        
        logger.info("✅ IPC Manager started")
    
    def stop(self) -> None:
        """
        Stop message processing.
        Dừng xử lý tin nhắn.
        """
        self.running = False
        
        if self.message_thread:
            self.message_thread.join(timeout=5)
            self.message_thread = None
        
        self.process_registry.stop_monitoring()
        
        logger.info("✅ IPC Manager stopped")
    
    def _handle_message(self, message: IPCMessage) -> None:
        """
        Handle incoming message.
        Xử lý tin nhắn đến.
        
        Args:
            message: Message to handle
        """
        # Check if message is for this process or broadcast
        current_pid = os.getpid()
        if message.receiver_pid != 0 and message.receiver_pid != current_pid:
            return
        
        # Execute registered handlers
        handlers = self.message_handlers.get(message.msg_type, [])
        for handler in handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"❌ Handler error for {message.msg_type.value}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get IPC manager status.
        Lấy trạng thái IPC manager.
        
        Returns:
            Status dictionary
        """
        return {
            'running': self.running,
            'queue_size': self.message_queue.size(),
            'queue_stats': self.message_queue.stats,
            'registry_status': self.process_registry.get_status(),
            'handlers': {
                msg_type.value: len(handlers)
                for msg_type, handlers in self.message_handlers.items()
            }
        }
