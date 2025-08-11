"""
Semaphore Pool Module
=====================
Resource semaphore management for GPU optimization.
Module quản lý semaphore tài nguyên cho tối ưu GPU.

Implements:
- **Resource Pooling** (gộp tài nguyên – tái sử dụng hiệu quả)
- **Deadlock Detection** (phát hiện deadlock – ngăn xung đột tài nguyên)
- **Priority Allocation** (phân bổ ưu tiên – tối ưu phân phối)
- **Timeout Management** (quản lý timeout – kiểm soát thời gian)
"""

import logging
import time
import threading
import uuid
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import heapq

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """
    Resource types.
    Các loại tài nguyên.
    """
    GPU_MEMORY = "gpu_memory"      # Bộ nhớ GPU
    GPU_COMPUTE = "gpu_compute"    # Tính toán GPU
    CPU_CORES = "cpu_cores"        # Lõi CPU
    SYSTEM_MEMORY = "system_memory" # Bộ nhớ hệ thống
    NETWORK_IO = "network_io"      # I/O mạng
    DISK_IO = "disk_io"            # I/O đĩa


class LockState(Enum):
    """
    Lock states.
    Trạng thái khóa.
    """
    AVAILABLE = "available"    # Có sẵn
    ACQUIRED = "acquired"      # Đã chiếm
    WAITING = "waiting"        # Đang chờ
    TIMEOUT = "timeout"        # Hết thời gian
    RELEASED = "released"      # Đã giải phóng


@dataclass
class ResourceLock:
    """
    Resource lock information.
    Thông tin khóa tài nguyên.
    
    Attributes:
        lock_id: Unique lock identifier
        resource_type: Type of resource
        resource_id: Resource identifier
        owner_pid: Owner process ID
        priority: Lock priority
        state: Current lock state
        acquired_at: Acquisition timestamp
        timeout: Lock timeout in seconds
        metadata: Additional metadata
    """
    lock_id: str
    resource_type: ResourceType
    resource_id: str
    owner_pid: int
    priority: int = 5
    state: LockState = LockState.WAITING
    acquired_at: Optional[datetime] = None
    timeout: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if lock has expired"""
        if not self.acquired_at:
            return False
        return (datetime.now() - self.acquired_at).total_seconds() > self.timeout
    
    def __lt__(self, other):
        """For priority queue comparison (higher priority = lower value)"""
        return self.priority > other.priority


@dataclass
class SemaphoreResource:
    """
    Semaphore resource definition.
    Định nghĩa tài nguyên semaphore.
    
    Attributes:
        resource_id: Resource identifier
        resource_type: Resource type
        capacity: Total capacity
        available: Available capacity
        locks: Active locks
        wait_queue: Waiting requests queue
    """
    resource_id: str
    resource_type: ResourceType
    capacity: int
    available: int
    locks: Dict[str, ResourceLock] = field(default_factory=dict)
    wait_queue: List[ResourceLock] = field(default_factory=list)
    
    def has_capacity(self, amount: int = 1) -> bool:
        """Check if resource has capacity"""
        return self.available >= amount


class DeadlockDetector:
    """
    **Deadlock Detector** (bộ phát hiện deadlock) - Detects resource deadlocks.
    
    Uses:
    - **Wait-for Graph** (đồ thị chờ đợi – theo dõi phụ thuộc)
    - **Cycle Detection** (phát hiện chu trình – tìm deadlock)
    """
    
    def __init__(self):
        """Initialize deadlock detector"""
        self.wait_graph: Dict[int, Set[int]] = defaultdict(set)
        self.resource_holders: Dict[str, int] = {}
        self.resource_waiters: Dict[str, List[int]] = defaultdict(list)
        self.lock = threading.RLock()
        
        logger.info("✅ Deadlock Detector initialized")
    
    def add_wait(self, waiter_pid: int, resource_id: str, holder_pid: int) -> None:
        """
        Add wait dependency.
        Thêm phụ thuộc chờ.
        
        Args:
            waiter_pid: Waiting process ID
            resource_id: Resource being waited for
            holder_pid: Current holder process ID
        """
        with self.lock:
            self.wait_graph[waiter_pid].add(holder_pid)
            self.resource_waiters[resource_id].append(waiter_pid)
            
            logger.debug(f"Process {waiter_pid} waiting for {resource_id} held by {holder_pid}")
    
    def remove_wait(self, waiter_pid: int, resource_id: str) -> None:
        """
        Remove wait dependency.
        Xóa phụ thuộc chờ.
        
        Args:
            waiter_pid: Waiting process ID
            resource_id: Resource ID
        """
        with self.lock:
            if resource_id in self.resource_waiters:
                self.resource_waiters[resource_id] = [
                    pid for pid in self.resource_waiters[resource_id]
                    if pid != waiter_pid
                ]
            
            # Clear wait edges for this process
            if waiter_pid in self.wait_graph:
                del self.wait_graph[waiter_pid]
    
    def update_holder(self, resource_id: str, holder_pid: Optional[int]) -> None:
        """
        Update resource holder.
        Cập nhật người giữ tài nguyên.
        
        Args:
            resource_id: Resource ID
            holder_pid: New holder PID (None if released)
        """
        with self.lock:
            if holder_pid is None:
                if resource_id in self.resource_holders:
                    del self.resource_holders[resource_id]
            else:
                self.resource_holders[resource_id] = holder_pid
    
    def detect_cycle(self) -> Optional[List[int]]:
        """
        Detect cycle in wait-for graph using DFS.
        Phát hiện chu trình trong đồ thị chờ bằng DFS.
        
        Returns:
            List of PIDs forming a cycle, or None
        """
        with self.lock:
            visited = set()
            rec_stack = set()
            path = []
            
            def dfs(node: int) -> bool:
                visited.add(node)
                rec_stack.add(node)
                path.append(node)
                
                for neighbor in self.wait_graph.get(node, []):
                    if neighbor not in visited:
                        if dfs(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        # Found cycle
                        cycle_start = path.index(neighbor)
                        cycle = path[cycle_start:]
                        cycle.append(neighbor)
                        logger.error(f"❌ Deadlock detected: {' -> '.join(map(str, cycle))}")
                        return True
                
                path.pop()
                rec_stack.remove(node)
                return False
            
            for node in self.wait_graph:
                if node not in visited:
                    if dfs(node):
                        return path
            
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get detector status.
        Lấy trạng thái detector.
        
        Returns:
            Status dictionary
        """
        with self.lock:
            return {
                'wait_graph_size': len(self.wait_graph),
                'resource_holders': len(self.resource_holders),
                'waiting_processes': sum(len(waiters) for waiters in self.resource_waiters.values()),
                'has_cycle': self.detect_cycle() is not None
            }


class SemaphorePool:
    """
    **Semaphore Pool** (nhóm semaphore) - Manages resource semaphores.
    
    Features:
    - **Resource Pooling** (gộp tài nguyên)
    - **Priority Allocation** (phân bổ ưu tiên)
    - **Timeout Management** (quản lý timeout)
    - **Deadlock Prevention** (ngăn deadlock)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize semaphore pool.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.resources: Dict[str, SemaphoreResource] = {}
        self.locks: Dict[str, ResourceLock] = {}
        self.lock = threading.RLock()
        self.deadlock_detector = DeadlockDetector()
        self.cleanup_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Statistics
        self.stats = {
            'locks_acquired': 0,
            'locks_released': 0,
            'locks_timeout': 0,
            'deadlocks_detected': 0,
            'wait_time_total': 0.0,
            'wait_time_max': 0.0
        }
        
        # Initialize default resources
        self._initialize_resources()
        
        # Start cleanup thread
        self._start_cleanup()
        
        logger.info("✅ Semaphore Pool initialized")
    
    def _initialize_resources(self) -> None:
        """
        Initialize default resources.
        Khởi tạo tài nguyên mặc định.
        """
        default_resources = self.config.get('resources', {
            'gpu_memory': {'type': ResourceType.GPU_MEMORY, 'capacity': 100},
            'gpu_compute': {'type': ResourceType.GPU_COMPUTE, 'capacity': 100},
            'cpu_cores': {'type': ResourceType.CPU_CORES, 'capacity': 16},
            'system_memory': {'type': ResourceType.SYSTEM_MEMORY, 'capacity': 100}
        })
        
        for resource_id, resource_config in default_resources.items():
            self.add_resource(
                resource_id=resource_id,
                resource_type=resource_config['type'],
                capacity=resource_config['capacity']
            )
    
    def add_resource(self, resource_id: str, resource_type: ResourceType, 
                    capacity: int) -> bool:
        """
        Add a resource to the pool.
        Thêm tài nguyên vào pool.
        
        Args:
            resource_id: Resource identifier
            resource_type: Resource type
            capacity: Resource capacity
            
        Returns:
            True if successful
        """
        with self.lock:
            if resource_id in self.resources:
                logger.warning(f"⚠️ Resource {resource_id} already exists")
                return False
            
            resource = SemaphoreResource(
                resource_id=resource_id,
                resource_type=resource_type,
                capacity=capacity,
                available=capacity
            )
            
            self.resources[resource_id] = resource
            logger.info(f"✅ Added resource {resource_id} với capacity={capacity}")
            
            return True
    
    def acquire(self, resource_id: str, owner_pid: int, 
               amount: int = 1, priority: int = 5,
               timeout: float = 30.0) -> Optional[str]:
        """
        Acquire resource lock.
        Chiếm khóa tài nguyên.
        
        Args:
            resource_id: Resource to acquire
            owner_pid: Owner process ID
            amount: Amount to acquire
            priority: Request priority
            timeout: Timeout in seconds
            
        Returns:
            Lock ID if successful, None otherwise
        """
        start_time = time.time()
        lock_id = str(uuid.uuid4())
        
        with self.lock:
            if resource_id not in self.resources:
                logger.error(f"❌ Resource {resource_id} not found")
                return None
            
            resource = self.resources[resource_id]
            
            # Create lock request
            lock = ResourceLock(
                lock_id=lock_id,
                resource_type=resource.resource_type,
                resource_id=resource_id,
                owner_pid=owner_pid,
                priority=priority,
                timeout=timeout
            )
            
            # Check for immediate availability
            if resource.has_capacity(amount):
                # Acquire immediately
                resource.available -= amount
                lock.state = LockState.ACQUIRED
                lock.acquired_at = datetime.now()
                
                resource.locks[lock_id] = lock
                self.locks[lock_id] = lock
                
                self.deadlock_detector.update_holder(resource_id, owner_pid)
                
                self.stats['locks_acquired'] += 1
                
                logger.info(f"✅ Lock {lock_id} acquired cho resource {resource_id}")
                return lock_id
            
            # Add to wait queue
            heapq.heappush(resource.wait_queue, lock)
            self.locks[lock_id] = lock
            
            # Check for deadlock
            current_holder = None
            for existing_lock in resource.locks.values():
                if existing_lock.state == LockState.ACQUIRED:
                    current_holder = existing_lock.owner_pid
                    break
            
            if current_holder:
                self.deadlock_detector.add_wait(owner_pid, resource_id, current_holder)
                
                # Check for deadlock
                if self.deadlock_detector.detect_cycle():
                    self.stats['deadlocks_detected'] += 1
                    logger.error(f"❌ Deadlock detected khi acquiring {resource_id}")
                    
                    # Remove from wait queue
                    resource.wait_queue = [l for l in resource.wait_queue if l.lock_id != lock_id]
                    heapq.heapify(resource.wait_queue)
                    
                    self.deadlock_detector.remove_wait(owner_pid, resource_id)
                    
                    del self.locks[lock_id]
                    return None
            
            logger.info(f"⏳ Lock {lock_id} waiting cho resource {resource_id}")
        
        # Wait for lock with timeout
        end_time = start_time + timeout
        
        while time.time() < end_time:
            with self.lock:
                if lock.state == LockState.ACQUIRED:
                    wait_time = time.time() - start_time
                    self.stats['wait_time_total'] += wait_time
                    self.stats['wait_time_max'] = max(self.stats['wait_time_max'], wait_time)
                    return lock_id
                
                if lock.state == LockState.TIMEOUT:
                    self.stats['locks_timeout'] += 1
                    return None
            
            time.sleep(0.1)  # Check every 100ms
        
        # Timeout
        with self.lock:
            lock.state = LockState.TIMEOUT
            resource.wait_queue = [l for l in resource.wait_queue if l.lock_id != lock_id]
            heapq.heapify(resource.wait_queue)
            
            self.deadlock_detector.remove_wait(owner_pid, resource_id)
            
            self.stats['locks_timeout'] += 1
            
            logger.warning(f"⏱️ Lock {lock_id} timeout cho resource {resource_id}")
            
            return None
    
    def release(self, lock_id: str) -> bool:
        """
        Release resource lock.
        Giải phóng khóa tài nguyên.
        
        Args:
            lock_id: Lock ID to release
            
        Returns:
            True if successful
        """
        with self.lock:
            if lock_id not in self.locks:
                logger.warning(f"⚠️ Lock {lock_id} not found")
                return False
            
            lock = self.locks[lock_id]
            resource = self.resources.get(lock.resource_id)
            
            if not resource:
                logger.error(f"❌ Resource {lock.resource_id} not found")
                return False
            
            # Release the lock
            if lock.state == LockState.ACQUIRED:
                resource.available += 1  # Assuming amount=1 for simplicity
                lock.state = LockState.RELEASED
                
                # Remove from resource locks
                if lock_id in resource.locks:
                    del resource.locks[lock_id]
                
                # Update deadlock detector
                self.deadlock_detector.update_holder(lock.resource_id, None)
                
                self.stats['locks_released'] += 1
                
                logger.info(f"✅ Lock {lock_id} released cho resource {lock.resource_id}")
                
                # Process wait queue
                self._process_wait_queue(resource)
                
                # Clean up lock
                del self.locks[lock_id]
                
                return True
            else:
                logger.warning(f"⚠️ Lock {lock_id} not in ACQUIRED state")
                return False
    
    def _process_wait_queue(self, resource: SemaphoreResource) -> None:
        """
        Process resource wait queue.
        Xử lý hàng đợi chờ tài nguyên.
        
        Args:
            resource: Resource to process
        """
        processed = []
        
        while resource.wait_queue and resource.has_capacity():
            # Get highest priority waiter
            waiter = heapq.heappop(resource.wait_queue)
            
            # Acquire for waiter
            resource.available -= 1
            waiter.state = LockState.ACQUIRED
            waiter.acquired_at = datetime.now()
            
            resource.locks[waiter.lock_id] = waiter
            
            # Update deadlock detector
            self.deadlock_detector.remove_wait(waiter.owner_pid, resource.resource_id)
            self.deadlock_detector.update_holder(resource.resource_id, waiter.owner_pid)
            
            self.stats['locks_acquired'] += 1
            
            processed.append(waiter.lock_id)
            
            logger.info(f"✅ Processed waiter {waiter.lock_id} cho resource {resource.resource_id}")
        
        # Re-heapify remaining queue
        heapq.heapify(resource.wait_queue)
    
    def _cleanup_expired_locks(self) -> None:
        """
        Clean up expired locks.
        Dọn dẹp khóa hết hạn.
        """
        with self.lock:
            expired = []
            
            for lock_id, lock in self.locks.items():
                if lock.state == LockState.ACQUIRED and lock.is_expired():
                    expired.append(lock_id)
                    logger.warning(f"⏱️ Lock {lock_id} expired, releasing")
            
            for lock_id in expired:
                self.release(lock_id)
    
    def _start_cleanup(self) -> None:
        """
        Start cleanup thread.
        Bắt đầu luồng dọn dẹp.
        """
        if self.running:
            return
        
        self.running = True
        
        def cleanup_loop():
            while self.running:
                self._cleanup_expired_locks()
                time.sleep(5)  # Check every 5 seconds
        
        self.cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        logger.info("✅ Started cleanup thread")
    
    def stop(self) -> None:
        """
        Stop semaphore pool.
        Dừng semaphore pool.
        """
        self.running = False
        
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
            self.cleanup_thread = None
        
        logger.info("✅ Semaphore Pool stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get pool status.
        Lấy trạng thái pool.
        
        Returns:
            Status dictionary
        """
        with self.lock:
            return {
                'resources': {
                    resource_id: {
                        'type': resource.resource_type.value,
                        'capacity': resource.capacity,
                        'available': resource.available,
                        'locks': len(resource.locks),
                        'waiters': len(resource.wait_queue)
                    }
                    for resource_id, resource in self.resources.items()
                },
                'total_locks': len(self.locks),
                'stats': self.stats.copy(),
                'deadlock_detector': self.deadlock_detector.get_status()
            }
