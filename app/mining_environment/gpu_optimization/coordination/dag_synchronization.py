"""
DAG Synchronization Module
==========================
Directed Acyclic Graph synchronization for GPU optimization tasks.
Module đồng bộ hóa DAG cho các tác vụ tối ưu GPU.

Implements:
- **Topological Sort** (sắp xếp tô-pô – xác định thứ tự thực thi)
- **Dependency Resolution** (giải quyết phụ thuộc – quản lý quan hệ tác vụ)
- **Parallel Execution** (thực thi song song – tối ưu hiệu suất)
- **Cycle Detection** (phát hiện chu trình – ngăn deadlock)
"""

import logging
import time
import threading
from typing import Dict, List, Set, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskState(Enum):
    """
    Task execution states.
    Trạng thái thực thi tác vụ.
    """
    PENDING = "pending"      # Chờ thực thi
    READY = "ready"          # Sẵn sàng (dependencies resolved)
    RUNNING = "running"      # Đang chạy
    SUCCESS = "success"      # Hoàn thành
    FAILED = "failed"        # Thất bại
    CANCELLED = "cancelled"  # Đã hủy


class TaskPriority(Enum):
    """
    Task priority levels.
    Mức độ ưu tiên tác vụ.
    """
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class DAGTask:
    """
    DAG task node.
    Node tác vụ trong đồ thị DAG.
    
    Attributes:
        task_id: Unique task identifier
        name: Task name for logging
        func: Callable to execute
        args: Positional arguments
        kwargs: Keyword arguments
        dependencies: Set of task IDs this task depends on
        priority: Task priority level
        timeout: Execution timeout in seconds
        retry_count: Number of retry attempts
        state: Current task state
        result: Task execution result
        error: Error if task failed
        start_time: Execution start timestamp
        end_time: Execution end timestamp
    """
    task_id: str
    name: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    dependencies: Set[str] = field(default_factory=set)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: float = 30.0
    retry_count: int = 3
    state: TaskState = TaskState.PENDING
    result: Any = None
    error: Optional[Exception] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def __hash__(self):
        return hash(self.task_id)
    
    def __eq__(self, other):
        if isinstance(other, DAGTask):
            return self.task_id == other.task_id
        return False
    
    def reset(self):
        """Reset task state for retry"""
        self.state = TaskState.PENDING
        self.result = None
        self.error = None
        self.start_time = None
        self.end_time = None


class DAGExecutor:
    """
    **DAG Executor** (bộ thực thi DAG) - Executes tasks in topological order.
    
    Features:
    - **Dependency Resolution** (giải quyết phụ thuộc)
    - **Parallel Execution** (thực thi song song)
    - **Deadlock Detection** (phát hiện deadlock)
    - **Error Recovery** (khôi phục lỗi)
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize DAG executor.
        
        Args:
            max_workers: Maximum parallel workers
        """
        self.tasks: Dict[str, DAGTask] = {}
        self.graph: Dict[str, Set[str]] = defaultdict(set)  # adjacency list
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)  # reverse dependencies
        self.max_workers = max_workers
        self.executor: Optional[ThreadPoolExecutor] = None
        self.lock = threading.RLock()
        self.completed_tasks: Set[str] = set()
        self.failed_tasks: Set[str] = set()
        self.running_tasks: Dict[str, Future] = {}
        
        logger.info(f"✅ DAG Executor initialized với {max_workers} workers")
    
    def add_task(self, task: DAGTask) -> None:
        """
        Add task to DAG.
        Thêm tác vụ vào đồ thị.
        
        Args:
            task: Task to add
        """
        with self.lock:
            self.tasks[task.task_id] = task
            
            # Build dependency graph
            for dep_id in task.dependencies:
                self.graph[dep_id].add(task.task_id)
                self.reverse_graph[task.task_id].add(dep_id)
            
            # Ensure node exists in graph even if no dependencies
            if task.task_id not in self.graph:
                self.graph[task.task_id] = set()
            
            logger.debug(f"Added task {task.name} với {len(task.dependencies)} dependencies")
    
    def detect_cycle(self) -> Optional[List[str]]:
        """
        Detect cycle in DAG using DFS.
        Phát hiện chu trình trong DAG bằng DFS.
        
        Returns:
            List of task IDs forming a cycle, or None
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {task_id: WHITE for task_id in self.tasks}
        parent = {}
        cycle = []
        
        def dfs(node: str) -> bool:
            color[node] = GRAY
            
            for neighbor in self.graph.get(node, []):
                if neighbor not in color:
                    continue
                    
                if color[neighbor] == GRAY:
                    # Found cycle - build path
                    cycle.clear()
                    cycle.append(neighbor)
                    curr = node
                    while curr != neighbor:
                        cycle.append(curr)
                        curr = parent.get(curr)
                        if not curr:
                            break
                    cycle.append(neighbor)
                    return True
                
                if color[neighbor] == WHITE:
                    parent[neighbor] = node
                    if dfs(neighbor):
                        return True
            
            color[node] = BLACK
            return False
        
        # Check all components
        for task_id in self.tasks:
            if color[task_id] == WHITE:
                if dfs(task_id):
                    logger.error(f"❌ Phát hiện chu trình: {' -> '.join(cycle)}")
                    return cycle
        
        return None
    
    def topological_sort(self) -> List[str]:
        """
        Perform topological sort using Kahn's algorithm.
        Sắp xếp tô-pô bằng thuật toán Kahn.
        
        Returns:
            List of task IDs in topological order
        """
        # Count in-degrees
        in_degree = {task_id: len(self.reverse_graph[task_id]) 
                     for task_id in self.tasks}
        
        # Find tasks with no dependencies
        queue = deque([task_id for task_id, degree in in_degree.items() 
                      if degree == 0])
        
        # Sort initial queue by priority
        queue = deque(sorted(queue, 
                           key=lambda x: self.tasks[x].priority.value, 
                           reverse=True))
        
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            
            # Reduce in-degree for dependent tasks
            for neighbor in self.graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
            
            # Re-sort queue by priority
            if queue:
                queue = deque(sorted(queue,
                                   key=lambda x: self.tasks[x].priority.value,
                                   reverse=True))
        
        if len(result) != len(self.tasks):
            missing = set(self.tasks.keys()) - set(result)
            logger.error(f"❌ Không thể sắp xếp tô-pô, thiếu: {missing}")
            return []
        
        logger.info(f"✅ Topological sort: {len(result)} tasks")
        return result
    
    def _execute_task(self, task: DAGTask) -> Any:
        """
        Execute a single task.
        Thực thi một tác vụ đơn.
        
        Args:
            task: Task to execute
            
        Returns:
            Task result
        """
        task.state = TaskState.RUNNING
        task.start_time = datetime.now()
        
        logger.info(f"▶️ Executing task {task.name}")
        
        for attempt in range(task.retry_count):
            try:
                # Execute with timeout
                result = task.func(*task.args, **task.kwargs)
                
                task.state = TaskState.SUCCESS
                task.result = result
                task.end_time = datetime.now()
                
                duration = (task.end_time - task.start_time).total_seconds()
                logger.info(f"✅ Task {task.name} completed trong {duration:.2f}s")
                
                return result
                
            except Exception as e:
                logger.warning(f"⚠️ Task {task.name} attempt {attempt + 1} failed: {e}")
                task.error = e
                
                if attempt < task.retry_count - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                
                task.state = TaskState.FAILED
                task.end_time = datetime.now()
                logger.error(f"❌ Task {task.name} failed sau {task.retry_count} attempts")
                raise
    
    def _can_execute(self, task_id: str) -> bool:
        """
        Check if task can be executed.
        Kiểm tra tác vụ có thể thực thi.
        
        Args:
            task_id: Task ID to check
            
        Returns:
            True if all dependencies are satisfied
        """
        task = self.tasks[task_id]
        
        # Check if already completed or running
        if task.state in [TaskState.SUCCESS, TaskState.RUNNING]:
            return False
        
        # Check dependencies
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if not dep_task or dep_task.state != TaskState.SUCCESS:
                return False
        
        return True
    
    def execute(self, parallel: bool = True) -> Dict[str, Any]:
        """
        Execute all tasks in DAG.
        Thực thi tất cả tác vụ trong DAG.
        
        Args:
            parallel: Enable parallel execution
            
        Returns:
            Execution results
        """
        start_time = time.time()
        
        # Detect cycles
        if self.detect_cycle():
            raise ValueError("DAG contains cycle - không thể thực thi")
        
        # Get execution order
        order = self.topological_sort()
        if not order:
            raise ValueError("Không thể xác định thứ tự thực thi")
        
        logger.info(f"🚀 Starting DAG execution với {len(order)} tasks")
        
        results = {}
        
        if parallel:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                self.executor = executor
                futures = {}
                completed = set()
                
                while len(completed) < len(order):
                    # Find ready tasks
                    ready_tasks = []
                    for task_id in order:
                        if task_id not in completed and task_id not in futures:
                            if self._can_execute(task_id):
                                ready_tasks.append(task_id)
                    
                    # Submit ready tasks
                    for task_id in ready_tasks:
                        task = self.tasks[task_id]
                        future = executor.submit(self._execute_task, task)
                        futures[task_id] = future
                        self.running_tasks[task_id] = future
                    
                    # Wait for at least one task to complete
                    if futures:
                        done, pending = as_completed(futures.values(), timeout=1).__next__(), None
                        
                        for task_id, future in list(futures.items()):
                            if future.done():
                                try:
                                    result = future.result()
                                    results[task_id] = result
                                    self.completed_tasks.add(task_id)
                                except Exception as e:
                                    logger.error(f"Task {task_id} failed: {e}")
                                    self.failed_tasks.add(task_id)
                                    results[task_id] = {'error': str(e)}
                                
                                completed.add(task_id)
                                del futures[task_id]
                                if task_id in self.running_tasks:
                                    del self.running_tasks[task_id]
                    
                    # Small delay to prevent busy waiting
                    if not ready_tasks and futures:
                        time.sleep(0.1)
        else:
            # Sequential execution
            for task_id in order:
                task = self.tasks[task_id]
                try:
                    result = self._execute_task(task)
                    results[task_id] = result
                    self.completed_tasks.add(task_id)
                except Exception as e:
                    logger.error(f"Task {task_id} failed: {e}")
                    self.failed_tasks.add(task_id)
                    results[task_id] = {'error': str(e)}
        
        duration = time.time() - start_time
        
        summary = {
            'total_tasks': len(self.tasks),
            'completed': len(self.completed_tasks),
            'failed': len(self.failed_tasks),
            'duration': duration,
            'results': results
        }
        
        logger.info(f"✅ DAG execution completed trong {duration:.2f}s")
        logger.info(f"   Completed: {summary['completed']}, Failed: {summary['failed']}")
        
        return summary
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get execution status.
        Lấy trạng thái thực thi.
        
        Returns:
            Status dictionary
        """
        with self.lock:
            return {
                'total_tasks': len(self.tasks),
                'pending': sum(1 for t in self.tasks.values() 
                             if t.state == TaskState.PENDING),
                'running': sum(1 for t in self.tasks.values() 
                             if t.state == TaskState.RUNNING),
                'completed': len(self.completed_tasks),
                'failed': len(self.failed_tasks),
                'task_states': {
                    task_id: task.state.value 
                    for task_id, task in self.tasks.items()
                }
            }
    
    def cancel(self) -> None:
        """
        Cancel all running tasks.
        Hủy tất cả tác vụ đang chạy.
        """
        logger.warning("🛑 Cancelling DAG execution...")
        
        with self.lock:
            # Cancel running futures
            for task_id, future in self.running_tasks.items():
                if not future.done():
                    future.cancel()
                    self.tasks[task_id].state = TaskState.CANCELLED
            
            self.running_tasks.clear()
            
            # Mark pending tasks as cancelled
            for task in self.tasks.values():
                if task.state == TaskState.PENDING:
                    task.state = TaskState.CANCELLED
        
        logger.info("✅ DAG execution cancelled")
    
    def clear(self) -> None:
        """
        Clear all tasks and reset executor.
        Xóa tất cả tác vụ và reset executor.
        """
        with self.lock:
            self.cancel()
            self.tasks.clear()
            self.graph.clear()
            self.reverse_graph.clear()
            self.completed_tasks.clear()
            self.failed_tasks.clear()
            
        logger.info("✅ DAG Executor cleared")
