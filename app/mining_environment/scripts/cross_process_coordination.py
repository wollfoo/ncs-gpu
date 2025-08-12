#!/usr/bin/env python3
"""
**Cross-Process Coordination Module** (module phối hợp liên tiến trình)

Triển khai **Intelligence Layer - Step 2.3** (tầng trí tuệ - bước 2.3)
để điều phối tài nguyên GPU giữa nhiều tiến trình mining với:
- **Semaphore** (cờ hiệu – kiểm soát truy cập đồng thời)
- **Resource Reservation** (đặt trước tài nguyên – ngăn xung đột)
- **Conflict Resolution** (giải quyết xung đột – khi nhiều process cần GPU)
- **Deadlock Prevention** (ngăn chặn deadlock – tránh phụ thuộc vòng)
- **Inter-Process Messaging** (nhắn tin liên tiến trình – giao tiếp giữa các process)
"""

import os
import time
import json
import threading
import multiprocessing
import queue
import psutil
import signal
import fcntl
import struct
import socket
import pickle
import hashlib
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import logging

# **Import utilities** (nhập tiện ích)
try:
    from .module_loggers import get_coordination_logger
    logger = get_coordination_logger()
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# **Constants** (hằng số)
COORDINATION_DIR = Path("/tmp/gpu_coordination")
LOCK_FILE = COORDINATION_DIR / "coordination.lock"
RESOURCE_DB = COORDINATION_DIR / "resources.json"
MESSAGE_QUEUE = COORDINATION_DIR / "messages"
SEMAPHORE_DIR = COORDINATION_DIR / "semaphores"

# **Ensure directories exist** (đảm bảo thư mục tồn tại)
COORDINATION_DIR.mkdir(exist_ok=True)
MESSAGE_QUEUE.mkdir(exist_ok=True)
SEMAPHORE_DIR.mkdir(exist_ok=True)


class ResourceType(Enum):
    """**Resource Types** (loại tài nguyên)"""
    GPU_COMPUTE = "gpu_compute"  # GPU compute capacity
    GPU_MEMORY = "gpu_memory"    # GPU memory (VRAM)
    GPU_POWER = "gpu_power"      # GPU power budget
    GPU_CLOCKS = "gpu_clocks"    # GPU clock speeds
    NETWORK_BW = "network_bandwidth"  # Network bandwidth


class MessageType(Enum):
    """**Message Types** (loại tin nhắn)"""
    REQUEST_RESOURCE = "request"     # Request resource access
    RELEASE_RESOURCE = "release"     # Release resource
    GRANT_ACCESS = "grant"           # Grant resource access
    DENY_ACCESS = "deny"            # Deny resource access
    HEARTBEAT = "heartbeat"         # Process alive signal
    PRIORITY_UPDATE = "priority"    # Update priority
    CONFLICT_DETECTED = "conflict"  # Conflict detected
    DEADLOCK_WARNING = "deadlock"   # Deadlock warning


@dataclass
class ResourceRequest:
    """**Resource Request** (yêu cầu tài nguyên)"""
    pid: int
    gpu_index: int
    resource_type: ResourceType
    amount: float  # Percentage or absolute value
    priority: int = 5  # 1-10, higher is more important
    timestamp: float = field(default_factory=time.time)
    timeout: float = 30.0  # Seconds to wait
    request_id: str = field(default_factory=lambda: hashlib.md5(
        f"{time.time()}_{os.getpid()}".encode()).hexdigest()[:8])


@dataclass
class ProcessMessage:
    """**Inter-Process Message** (tin nhắn liên tiến trình)"""
    sender_pid: int
    receiver_pid: int  # 0 for broadcast
    message_type: MessageType
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    message_id: str = field(default_factory=lambda: hashlib.md5(
        f"{time.time()}_{os.getpid()}".encode()).hexdigest()[:8])


class GPUSemaphore:
    """
    **GPU Semaphore** (cờ hiệu GPU – điều khiển số lượng process truy cập GPU đồng thời)
    
    Implements counting semaphore for GPU resources using file locks.
    """
    
    def __init__(self, name: str, max_count: int = 1):
        """
        Initialize GPU semaphore.
        
        Args:
            name: Semaphore name
            max_count: Maximum concurrent accessors
        """
        self.name = name
        self.max_count = max_count
        self.lock_file = SEMAPHORE_DIR / f"{name}.sem"
        self.count_file = SEMAPHORE_DIR / f"{name}.count"
        
        # Initialize count file if not exists
        if not self.count_file.exists():
            self._write_count(0)
    
    def _read_count(self) -> int:
        """Read current count from file"""
        try:
            with open(self.count_file, 'r') as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 0
    
    def _write_count(self, count: int):
        """Write count to file"""
        with open(self.count_file, 'w') as f:
            f.write(str(count))
    
    def acquire(self, timeout: float = 30.0) -> bool:
        """
        **Acquire semaphore** (lấy cờ hiệu – xin quyền truy cập)
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            True if acquired, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Use file lock for atomic operations
            with open(self.lock_file, 'a+') as lock_fd:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                try:
                    current = self._read_count()
                    if current < self.max_count:
                        self._write_count(current + 1)
                        logger.info(f"🔒 **Semaphore acquired** (đã lấy cờ hiệu): {self.name} "
                                  f"({current + 1}/{self.max_count})")
                        return True
                finally:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
            
            # Wait before retry
            time.sleep(0.1)
        
        logger.warning(f"⏱️ **Semaphore timeout** (hết thời gian chờ cờ hiệu): {self.name}")
        return False
    
    def release(self):
        """**Release semaphore** (trả cờ hiệu – giải phóng quyền truy cập)"""
        with open(self.lock_file, 'a+') as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                current = self._read_count()
                if current > 0:
                    self._write_count(current - 1)
                    logger.info(f"🔓 **Semaphore released** (đã trả cờ hiệu): {self.name} "
                              f"({current - 1}/{self.max_count})")
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)


class ResourceReservationManager:
    """
    **Resource Reservation Manager** (quản lý đặt trước tài nguyên)
    
    Manages GPU resource reservations to prevent conflicts.
    """
    
    def __init__(self):
        """Initialize reservation manager"""
        self.reservations: Dict[str, List[ResourceRequest]] = {}
        self.lock = threading.RLock()
        self._load_reservations()
    
    def _load_reservations(self):
        """Load existing reservations from disk"""
        try:
            if RESOURCE_DB.exists():
                with open(RESOURCE_DB, 'r') as f:
                    data = json.load(f)
                    # Convert dict back to ResourceRequest objects
                    for key, requests in data.items():
                        self.reservations[key] = [
                            ResourceRequest(**req) for req in requests
                        ]
        except Exception as e:
            logger.error(f"❌ **Failed to load reservations** (không tải được đặt trước): {e}")
    
    def _save_reservations(self):
        """Save reservations to disk"""
        try:
            data = {}
            for key, requests in self.reservations.items():
                data[key] = [
                    {
                        'pid': req.pid,
                        'gpu_index': req.gpu_index,
                        'resource_type': req.resource_type.value,
                        'amount': req.amount,
                        'priority': req.priority,
                        'timestamp': req.timestamp,
                        'timeout': req.timeout,
                        'request_id': req.request_id
                    }
                    for req in requests
                ]
            
            with open(RESOURCE_DB, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ **Failed to save reservations** (không lưu được đặt trước): {e}")
    
    def reserve_resource(self, request: ResourceRequest) -> bool:
        """
        **Reserve resource** (đặt trước tài nguyên)
        
        Args:
            request: Resource request
            
        Returns:
            True if reserved, False if conflict
        """
        with self.lock:
            key = f"{request.gpu_index}_{request.resource_type.value}"
            
            if key not in self.reservations:
                self.reservations[key] = []
            
            # Check for conflicts
            existing = self.reservations[key]
            total_amount = sum(req.amount for req in existing)
            
            # Check if adding this request would exceed 100%
            if total_amount + request.amount > 100:
                logger.warning(f"⚠️ **Resource conflict** (xung đột tài nguyên): "
                             f"GPU {request.gpu_index} {request.resource_type.value} "
                             f"at {total_amount + request.amount}%")
                return False
            
            # Add reservation
            self.reservations[key].append(request)
            self._save_reservations()
            
            logger.info(f"✅ **Resource reserved** (đã đặt trước tài nguyên): "
                       f"PID {request.pid} -> GPU {request.gpu_index} "
                       f"{request.resource_type.value} {request.amount}%")
            return True
    
    def release_resource(self, pid: int, gpu_index: int, 
                        resource_type: ResourceType) -> bool:
        """
        **Release resource** (giải phóng tài nguyên)
        
        Args:
            pid: Process ID
            gpu_index: GPU index
            resource_type: Resource type
            
        Returns:
            True if released, False if not found
        """
        with self.lock:
            key = f"{gpu_index}_{resource_type.value}"
            
            if key not in self.reservations:
                return False
            
            # Remove all reservations for this PID
            original_count = len(self.reservations[key])
            self.reservations[key] = [
                req for req in self.reservations[key]
                if req.pid != pid
            ]
            
            if len(self.reservations[key]) < original_count:
                self._save_reservations()
                logger.info(f"🔓 **Resource released** (đã giải phóng tài nguyên): "
                           f"PID {pid} -> GPU {gpu_index} {resource_type.value}")
                return True
            
            return False
    
    def get_resource_usage(self, gpu_index: int, 
                          resource_type: ResourceType) -> float:
        """
        **Get resource usage** (lấy mức sử dụng tài nguyên)
        
        Returns:
            Total usage percentage
        """
        with self.lock:
            key = f"{gpu_index}_{resource_type.value}"
            if key not in self.reservations:
                return 0.0
            
            return sum(req.amount for req in self.reservations[key])


class ConflictResolver:
    """
    **Conflict Resolver** (bộ giải quyết xung đột)
    
    Resolves resource conflicts between processes.
    """
    
    def __init__(self, reservation_manager: ResourceReservationManager):
        """
        Initialize conflict resolver.
        
        Args:
            reservation_manager: Resource reservation manager
        """
        self.reservation_manager = reservation_manager
        self.conflict_history: List[Dict[str, Any]] = []
    
    def resolve_conflict(self, requests: List[ResourceRequest]) -> List[ResourceRequest]:
        """
        **Resolve conflict** (giải quyết xung đột) between multiple requests.
        
        Uses priority-based resolution with fair sharing.
        
        Args:
            requests: List of conflicting requests
            
        Returns:
            List of approved requests
        """
        if not requests:
            return []
        
        # Sort by priority (higher first) then by timestamp (earlier first)
        sorted_requests = sorted(
            requests,
            key=lambda r: (-r.priority, r.timestamp)
        )
        
        approved = []
        remaining_capacity = 100.0
        
        for request in sorted_requests:
            if request.amount <= remaining_capacity:
                approved.append(request)
                remaining_capacity -= request.amount
                logger.info(f"✅ **Request approved** (yêu cầu được chấp thuận): "
                           f"PID {request.pid} gets {request.amount}% "
                           f"(priority: {request.priority})")
            else:
                # Partial allocation for high priority
                if request.priority >= 8 and remaining_capacity > 10:
                    # Give partial resources to high priority
                    partial_request = ResourceRequest(
                        pid=request.pid,
                        gpu_index=request.gpu_index,
                        resource_type=request.resource_type,
                        amount=remaining_capacity,
                        priority=request.priority,
                        timestamp=request.timestamp,
                        timeout=request.timeout,
                        request_id=request.request_id
                    )
                    approved.append(partial_request)
                    logger.info(f"⚠️ **Partial allocation** (phân bổ một phần): "
                               f"PID {request.pid} gets {remaining_capacity}% "
                               f"(requested {request.amount}%)")
                    remaining_capacity = 0
                else:
                    logger.warning(f"❌ **Request denied** (yêu cầu bị từ chối): "
                                 f"PID {request.pid} (no remaining capacity)")
        
        # Log conflict resolution
        self.conflict_history.append({
            'timestamp': time.time(),
            'requests': len(requests),
            'approved': len(approved),
            'gpu_index': requests[0].gpu_index if requests else -1,
            'resource_type': requests[0].resource_type.value if requests else 'unknown'
        })
        
        return approved


class DeadlockDetector:
    """
    **Deadlock Detector** (bộ phát hiện deadlock – phát hiện tình trạng khóa chết)
    
    Detects and prevents circular dependencies in resource allocation.
    """
    
    def __init__(self):
        """Initialize deadlock detector"""
        self.resource_graph: Dict[int, Set[int]] = {}  # PID -> Set of PIDs it's waiting for
        self.lock = threading.RLock()
    
    def add_dependency(self, waiter_pid: int, holder_pid: int):
        """
        **Add dependency** (thêm phụ thuộc) to resource graph.
        
        Args:
            waiter_pid: PID waiting for resource
            holder_pid: PID holding resource
        """
        with self.lock:
            if waiter_pid not in self.resource_graph:
                self.resource_graph[waiter_pid] = set()
            self.resource_graph[waiter_pid].add(holder_pid)
    
    def remove_dependency(self, waiter_pid: int, holder_pid: int):
        """
        **Remove dependency** (xóa phụ thuộc) from resource graph.
        """
        with self.lock:
            if waiter_pid in self.resource_graph:
                self.resource_graph[waiter_pid].discard(holder_pid)
                if not self.resource_graph[waiter_pid]:
                    del self.resource_graph[waiter_pid]
    
    def detect_cycle(self) -> Optional[List[int]]:
        """
        **Detect cycle** (phát hiện chu kỳ) in resource graph.
        
        Returns:
            List of PIDs in cycle if found, None otherwise
        """
        with self.lock:
            visited = set()
            rec_stack = set()
            
            def dfs(pid: int, path: List[int]) -> Optional[List[int]]:
                visited.add(pid)
                rec_stack.add(pid)
                path.append(pid)
                
                if pid in self.resource_graph:
                    for neighbor in self.resource_graph[pid]:
                        if neighbor not in visited:
                            cycle = dfs(neighbor, path.copy())
                            if cycle:
                                return cycle
                        elif neighbor in rec_stack:
                            # Cycle detected
                            cycle_start = path.index(neighbor)
                            return path[cycle_start:]
                
                rec_stack.remove(pid)
                return None
            
            for pid in list(self.resource_graph.keys()):
                if pid not in visited:
                    cycle = dfs(pid, [])
                    if cycle:
                        logger.warning(f"🔴 **Deadlock detected** (phát hiện deadlock): "
                                     f"PIDs {cycle}")
                        return cycle
            
            return None
    
    def prevent_deadlock(self, waiter_pid: int, holder_pid: int) -> bool:
        """
        **Prevent deadlock** (ngăn chặn deadlock) by checking if adding
        dependency would create cycle.
        
        Args:
            waiter_pid: PID requesting resource
            holder_pid: PID holding resource
            
        Returns:
            True if safe to proceed, False if would cause deadlock
        """
        with self.lock:
            # Temporarily add dependency
            self.add_dependency(waiter_pid, holder_pid)
            
            # Check for cycle
            cycle = self.detect_cycle()
            
            if cycle:
                # Remove dependency to prevent deadlock
                self.remove_dependency(waiter_pid, holder_pid)
                logger.warning(f"⚠️ **Deadlock prevented** (đã ngăn chặn deadlock): "
                             f"PID {waiter_pid} waiting for PID {holder_pid}")
                return False
            
            # Safe to proceed
            return True


class InterProcessMessenger:
    """
    **Inter-Process Messenger** (bộ nhắn tin liên tiến trình)
    
    Handles message passing between processes using Unix domain sockets.
    """
    
    def __init__(self, pid: int):
        """
        Initialize messenger for a process.
        
        Args:
            pid: Process ID
        """
        self.pid = pid
        self.socket_path = MESSAGE_QUEUE / f"ipc_{pid}.sock"
        self.server_socket = None
        self.client_sockets: Dict[int, socket.socket] = {}
        self.message_queue = queue.Queue()
        self.running = False
        self.server_thread = None
    
    def start(self):
        """**Start message server** (khởi động máy chủ nhắn tin)"""
        if self.running:
            return
        
        self.running = True
        
        # Remove old socket if exists
        if self.socket_path.exists():
            self.socket_path.unlink()
        
        # Create server socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(str(self.socket_path))
        self.server_socket.listen(5)
        
        # Start server thread
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()
        
        logger.info(f"📨 **Message server started** (máy chủ nhắn tin đã khởi động – server IPC sẵn sàng): PID {self.pid}")
    
    def _server_loop(self):
        """Server loop to accept connections"""
        while self.running:
            try:
                # Set timeout to allow periodic checks
                self.server_socket.settimeout(1.0)
                conn, _ = self.server_socket.accept()
                
                # Handle connection in separate thread
                threading.Thread(
                    target=self._handle_connection,
                    args=(conn,),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"❌ **Server error** (lỗi máy chủ – sự cố dịch vụ): {e}")
    
    def _handle_connection(self, conn: socket.socket):
        """Handle incoming connection"""
        try:
            # Receive message size
            size_data = conn.recv(4)
            if not size_data:
                return
            
            size = struct.unpack('!I', size_data)[0]
            
            # Receive message data
            data = b''
            while len(data) < size:
                chunk = conn.recv(min(size - len(data), 4096))
                if not chunk:
                    break
                data += chunk
            
            # Deserialize message
            message = pickle.loads(data)
            if isinstance(message, ProcessMessage):
                self.message_queue.put(message)
                logger.debug(f"📥 **Message received** (tin nhắn đã nhận – thông điệp vào): "
                           f"from PID {message.sender_pid} "
                           f"type {message.message_type.value}")
        except Exception as e:
            logger.error(f"❌ **Connection error** (lỗi kết nối – sự cố truyền thông): {e}")
        finally:
            conn.close()
    
    def send_message(self, receiver_pid: int, message_type: MessageType,
                    payload: Dict[str, Any]) -> bool:
        """
        **Send message** (gửi tin nhắn) to another process.
        
        Args:
            receiver_pid: Receiver process ID (0 for broadcast)
            message_type: Message type
            payload: Message payload
            
        Returns:
            True if sent successfully
        """
        message = ProcessMessage(
            sender_pid=self.pid,
            receiver_pid=receiver_pid,
            message_type=message_type,
            payload=payload
        )
        
        # Get target PIDs
        if receiver_pid == 0:
            # Broadcast to all active processes
            target_pids = [p.pid for p in psutil.process_iter(['pid']) 
                          if p.pid != self.pid]
        else:
            target_pids = [receiver_pid]
        
        success_count = 0
        for target_pid in target_pids:
            socket_path = MESSAGE_QUEUE / f"ipc_{target_pid}.sock"
            
            if not socket_path.exists():
                continue
            
            try:
                # Create client socket
                client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                client.settimeout(1.0)
                client.connect(str(socket_path))
                
                # Serialize and send message
                data = pickle.dumps(message)
                size = struct.pack('!I', len(data))
                client.sendall(size + data)
                
                client.close()
                success_count += 1
                
                logger.debug(f"📤 **Message sent** (tin nhắn đã gửi – thông điệp ra): "
                           f"to PID {target_pid} type {message_type.value}")
            except Exception as e:
                logger.error(f"❌ **Failed to send message** (gửi tin nhắn thất bại – lỗi truyền): "
                           f"to PID {target_pid}: {e}")
        
        return success_count > 0
    
    def receive_message(self, timeout: float = 0.1) -> Optional[ProcessMessage]:
        """
        **Receive message** (nhận tin nhắn) from queue.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Message if available, None otherwise
        """
        try:
            return self.message_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def stop(self):
        """**Stop message server** (dừng máy chủ nhắn tin)"""
        self.running = False
        
        if self.server_socket:
            self.server_socket.close()
        
        if self.socket_path.exists():
            self.socket_path.unlink()
        
        logger.info(f"📪 **Message server stopped** (máy chủ nhắn tin đã dừng – server IPC ngừng hoạt động): PID {self.pid}")


class CrossProcessCoordinator:
    """
    **Cross-Process Coordinator** (bộ điều phối liên tiến trình)
    
    Main coordinator combining all cross-process coordination features.
    """
    
    def __init__(self, pid: int):
        """
        Initialize cross-process coordinator.
        
        Args:
            pid: Process ID
        """
        self.pid = pid
        
        # Initialize components
        self.reservation_manager = ResourceReservationManager()
        self.conflict_resolver = ConflictResolver(self.reservation_manager)
        self.deadlock_detector = DeadlockDetector()
        self.messenger = InterProcessMessenger(pid)
        
        # Semaphores for each GPU
        self.gpu_semaphores: Dict[int, GPUSemaphore] = {}
        self._init_semaphores()
        
        # Start messenger
        self.messenger.start()
        
        # Process tracking
        self.active_processes: Set[int] = set()
        self.process_priorities: Dict[int, int] = {}
        
        # Heartbeat tracking
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 10.0  # seconds
        
        # Start background threads
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info(f"🚀 **Cross-Process Coordinator initialized** "
                   f"(bộ điều phối liên tiến trình đã khởi tạo): PID {pid}")
    
    def _init_semaphores(self):
        """Initialize GPU semaphores"""
        try:
            import pynvml
            pynvml.nvmlInit()
            gpu_count = pynvml.nvmlDeviceGetCount()
            
            for i in range(gpu_count):
                # Allow 2 processes per GPU by default
                self.gpu_semaphores[i] = GPUSemaphore(f"gpu_{i}", max_count=2)
            
            logger.info(f"🎮 **Initialized {gpu_count} GPU semaphores** "
                       f"(đã khởi tạo {gpu_count} cờ hiệu GPU)")
        except Exception as e:
            logger.error(f"❌ **Failed to initialize GPU semaphores** "
                        f"(khởi tạo cờ hiệu GPU thất bại): {e}")
            # Default to 1 GPU
            self.gpu_semaphores[0] = GPUSemaphore("gpu_0", max_count=2)
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.running:
            try:
                # Send heartbeat
                if time.time() - self.last_heartbeat > self.heartbeat_interval:
                    self._send_heartbeat()
                    self.last_heartbeat = time.time()
                
                # Process incoming messages
                message = self.messenger.receive_message(timeout=0.1)
                if message:
                    self._handle_message(message)
                
                # Check for deadlocks
                cycle = self.deadlock_detector.detect_cycle()
                if cycle:
                    self._resolve_deadlock(cycle)
                
                # Clean up stale reservations
                self._cleanup_stale_reservations()
                
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"❌ **Monitor loop error** (lỗi vòng lặp giám sát): {e}")
    
    def _send_heartbeat(self):
        """Send heartbeat to all processes"""
        self.messenger.send_message(
            0,  # Broadcast
            MessageType.HEARTBEAT,
            {'pid': self.pid, 'timestamp': time.time()}
        )
    
    def _handle_message(self, message: ProcessMessage):
        """Handle incoming message"""
        try:
            if message.message_type == MessageType.REQUEST_RESOURCE:
                self._handle_resource_request(message)
            elif message.message_type == MessageType.RELEASE_RESOURCE:
                self._handle_resource_release(message)
            elif message.message_type == MessageType.HEARTBEAT:
                self._handle_heartbeat(message)
            elif message.message_type == MessageType.PRIORITY_UPDATE:
                self._handle_priority_update(message)
        except Exception as e:
            logger.error(f"❌ **Message handling error** (lỗi xử lý tin nhắn): {e}")
    
    def _handle_resource_request(self, message: ProcessMessage):
        """Handle resource request message"""
        payload = message.payload
        request = ResourceRequest(
            pid=message.sender_pid,
            gpu_index=payload['gpu_index'],
            resource_type=ResourceType(payload['resource_type']),
            amount=payload['amount'],
            priority=payload.get('priority', 5)
        )
        
        # Check for deadlock
        holders = self._get_resource_holders(request.gpu_index, request.resource_type)
        for holder_pid in holders:
            if not self.deadlock_detector.prevent_deadlock(request.pid, holder_pid):
                # Deadlock would occur, deny request
                self.messenger.send_message(
                    request.pid,
                    MessageType.DENY_ACCESS,
                    {'reason': 'deadlock_prevention', 'request_id': request.request_id}
                )
                return
        
        # Try to reserve resource
        if self.reservation_manager.reserve_resource(request):
            self.messenger.send_message(
                request.pid,
                MessageType.GRANT_ACCESS,
                {'request_id': request.request_id}
            )
        else:
            # Conflict detected, try to resolve
            self._handle_conflict(request)
    
    def _handle_resource_release(self, message: ProcessMessage):
        """Handle resource release message"""
        payload = message.payload
        success = self.reservation_manager.release_resource(
            message.sender_pid,
            payload['gpu_index'],
            ResourceType(payload['resource_type'])
        )
        
        if success:
            # Remove dependencies
            self._remove_all_dependencies(message.sender_pid)
    
    def _handle_heartbeat(self, message: ProcessMessage):
        """Handle heartbeat message"""
        self.active_processes.add(message.sender_pid)
    
    def _handle_priority_update(self, message: ProcessMessage):
        """Handle priority update message"""
        self.process_priorities[message.sender_pid] = message.payload['priority']
    
    def _handle_conflict(self, request: ResourceRequest):
        """Handle resource conflict"""
        # Get all conflicting requests
        key = f"{request.gpu_index}_{request.resource_type.value}"
        existing_requests = self.reservation_manager.reservations.get(key, [])
        all_requests = existing_requests + [request]
        
        # Resolve conflict
        approved = self.conflict_resolver.resolve_conflict(all_requests)
        
        # Apply resolution
        self.reservation_manager.reservations[key] = approved
        self.reservation_manager._save_reservations()
        
        # Notify processes
        for req in approved:
            if req.request_id == request.request_id:
                self.messenger.send_message(
                    req.pid,
                    MessageType.GRANT_ACCESS,
                    {'request_id': req.request_id, 'amount': req.amount}
                )
        
        if request not in approved:
            self.messenger.send_message(
                request.pid,
                MessageType.DENY_ACCESS,
                {'reason': 'conflict_resolution', 'request_id': request.request_id}
            )
    
    def _resolve_deadlock(self, cycle: List[int]):
        """Resolve detected deadlock"""
        # Find lowest priority process in cycle
        priorities = [(pid, self.process_priorities.get(pid, 5)) for pid in cycle]
        priorities.sort(key=lambda x: x[1])
        
        victim_pid = priorities[0][0]
        
        # Release all resources held by victim
        for gpu_idx in range(len(self.gpu_semaphores)):
            for res_type in ResourceType:
                self.reservation_manager.release_resource(victim_pid, gpu_idx, res_type)
        
        # Notify victim
        self.messenger.send_message(
            victim_pid,
            MessageType.DEADLOCK_WARNING,
            {'action': 'resources_released', 'cycle': cycle}
        )
        
        logger.warning(f"🔴 **Deadlock resolved** (đã giải quyết deadlock): "
                      f"Released resources from PID {victim_pid}")
    
    def _cleanup_stale_reservations(self):
        """Clean up reservations from dead processes"""
        try:
            active_pids = {p.pid for p in psutil.process_iter(['pid'])}
            
            for key in list(self.reservation_manager.reservations.keys()):
                requests = self.reservation_manager.reservations[key]
                active_requests = [req for req in requests if req.pid in active_pids]
                
                if len(active_requests) < len(requests):
                    self.reservation_manager.reservations[key] = active_requests
                    self.reservation_manager._save_reservations()
                    logger.info(f"🧹 **Cleaned stale reservations** "
                               f"(đã dọn đặt trước cũ): {key}")
        except Exception as e:
            logger.error(f"❌ **Cleanup error** (lỗi dọn dẹp): {e}")
    
    def _get_resource_holders(self, gpu_index: int, 
                             resource_type: ResourceType) -> List[int]:
        """Get PIDs holding a resource"""
        key = f"{gpu_index}_{resource_type.value}"
        requests = self.reservation_manager.reservations.get(key, [])
        return [req.pid for req in requests]
    
    def _remove_all_dependencies(self, pid: int):
        """Remove all dependencies for a PID"""
        # Remove from deadlock detector
        if pid in self.deadlock_detector.resource_graph:
            del self.deadlock_detector.resource_graph[pid]
        
        # Remove as dependency target
        for waiter_pid in list(self.deadlock_detector.resource_graph.keys()):
            self.deadlock_detector.remove_dependency(waiter_pid, pid)
    
    def request_resource(self, gpu_index: int, resource_type: ResourceType,
                         amount: float, priority: int = 5,
                         timeout: float = 30.0) -> bool:
        """
        **Request resource** (yêu cầu tài nguyên) for current process.
        
        Args:
            gpu_index: GPU index
            resource_type: Type of resource
            amount: Amount requested (percentage)
            priority: Request priority (1-10)
            timeout: Timeout in seconds
            
        Returns:
            True if granted, False otherwise
        """
        # Acquire semaphore first
        if gpu_index in self.gpu_semaphores:
            if not self.gpu_semaphores[gpu_index].acquire(timeout):
                logger.warning(f"⏱️ **Semaphore timeout** (hết thời gian chờ cờ hiệu)")
                return False
        
        # Create request
        request = ResourceRequest(
            pid=self.pid,
            gpu_index=gpu_index,
            resource_type=resource_type,
            amount=amount,
            priority=priority,
            timeout=timeout
        )
        
        # Try local reservation first
        if self.reservation_manager.reserve_resource(request):
            logger.info(f"✅ **Resource granted locally** (tài nguyên được cấp cục bộ)")
            return True
        
        # Send request to other processes
        self.messenger.send_message(
            0,  # Broadcast
            MessageType.REQUEST_RESOURCE,
            {
                'gpu_index': gpu_index,
                'resource_type': resource_type.value,
                'amount': amount,
                'priority': priority,
                'request_id': request.request_id
            }
        )
        
        # Wait for response
        start_time = time.time()
        while time.time() - start_time < timeout:
            message = self.messenger.receive_message(timeout=0.1)
            if message:
                if message.message_type == MessageType.GRANT_ACCESS:
                    if message.payload.get('request_id') == request.request_id:
                        logger.info(f"✅ **Resource granted** (tài nguyên được cấp)")
                        return True
                elif message.message_type == MessageType.DENY_ACCESS:
                    if message.payload.get('request_id') == request.request_id:
                        logger.warning(f"❌ **Resource denied** (tài nguyên bị từ chối): "
                                     f"{message.payload.get('reason')}")
                        # Release semaphore
                        if gpu_index in self.gpu_semaphores:
                            self.gpu_semaphores[gpu_index].release()
                        return False
        
        logger.warning(f"⏱️ **Request timeout** (hết thời gian chờ yêu cầu)")
        # Release semaphore
        if gpu_index in self.gpu_semaphores:
            self.gpu_semaphores[gpu_index].release()
        return False
    
    def release_resource(self, gpu_index: int, resource_type: ResourceType) -> bool:
        """
        **Release resource** (giải phóng tài nguyên) held by current process.
        
        Args:
            gpu_index: GPU index
            resource_type: Type of resource
            
        Returns:
            True if released successfully
        """
        # Release from reservation manager
        success = self.reservation_manager.release_resource(
            self.pid, gpu_index, resource_type
        )
        
        if success:
            # Release semaphore
            if gpu_index in self.gpu_semaphores:
                self.gpu_semaphores[gpu_index].release()
            
            # Notify other processes
            self.messenger.send_message(
                0,  # Broadcast
                MessageType.RELEASE_RESOURCE,
                {
                    'gpu_index': gpu_index,
                    'resource_type': resource_type.value
                }
            )
            
            logger.info(f"🔓 **Resource released** (đã giải phóng tài nguyên)")
        
        return success
    
    def update_priority(self, priority: int):
        """
        **Update process priority** (cập nhật độ ưu tiên tiến trình).
        
        Args:
            priority: New priority (1-10)
        """
        self.process_priorities[self.pid] = priority
        
        # Notify other processes
        self.messenger.send_message(
            0,  # Broadcast
            MessageType.PRIORITY_UPDATE,
            {'priority': priority}
        )
    
    def stop(self):
        """**Stop coordinator** (dừng bộ điều phối)"""
        self.running = False
        
        # Release all resources
        for gpu_idx in range(len(self.gpu_semaphores)):
            for res_type in ResourceType:
                self.release_resource(gpu_idx, res_type)
        
        # Stop messenger
        self.messenger.stop()
        
        # Wait for monitor thread
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        
        logger.info(f"🛑 **Coordinator stopped** (bộ điều phối đã dừng): PID {self.pid}")


# **Helper Functions** (hàm trợ giúp)

def test_coordination():
    """
    **Test cross-process coordination** (kiểm tra phối hợp liên tiến trình).
    
    Creates multiple processes to test coordination features.
    """
    import multiprocessing
    
    def worker_process(worker_id: int):
        """Worker process function"""
        pid = os.getpid()
        coordinator = CrossProcessCoordinator(pid)
        
        try:
            # Request GPU resources
            gpu_index = worker_id % 2  # Use 2 GPUs
            
            # Request compute resources
            if coordinator.request_resource(
                gpu_index, 
                ResourceType.GPU_COMPUTE,
                30.0,  # 30% compute
                priority=5 + worker_id
            ):
                logger.info(f"Worker {worker_id} got GPU {gpu_index} compute")
                
                # Simulate work
                time.sleep(5)
                
                # Release resources
                coordinator.release_resource(gpu_index, ResourceType.GPU_COMPUTE)
            else:
                logger.warning(f"Worker {worker_id} failed to get resources")
        
        finally:
            coordinator.stop()
    
    # Create worker processes
    processes = []
    for i in range(4):
        p = multiprocessing.Process(target=worker_process, args=(i,))
        p.start()
        processes.append(p)
    
    # Wait for completion
    for p in processes:
        p.join()
    
    logger.info("✅ **Test completed** (kiểm tra hoàn tất)")


if __name__ == "__main__":
    # Run test if executed directly
    test_coordination()
