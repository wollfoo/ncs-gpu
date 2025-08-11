#!/usr/bin/env python3
"""
**Parallel Strategy Executor** (Bộ thực thi chiến lược song song)

Module for executing multiple GPU optimization strategies in parallel with:
- ThreadPoolExecutor for concurrent execution
- Timeout handling for each strategy
- Result aggregation across strategies  
- Failure isolation to prevent cascade failures
"""

import os
import time
import threading
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError, as_completed
import traceback
import psutil
from datetime import datetime

# Import từ các modules hiện có
try:
    from module_loggers import get_optimization_logger
    logger = get_optimization_logger()
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """**Execution Status** (trạng thái thực thi)"""
    PENDING = "pending"      # Đang chờ
    RUNNING = "running"      # Đang chạy
    SUCCESS = "success"      # Thành công
    FAILED = "failed"        # Thất bại
    TIMEOUT = "timeout"      # Hết thời gian
    SKIPPED = "skipped"      # Bỏ qua


@dataclass
class StrategyTask:
    """
    **Strategy Task** (tác vụ chiến lược - đơn vị công việc)
    
    Represents a single strategy execution task.
    """
    name: str
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    timeout: float = 30.0  # seconds
    priority: int = 5  # 1-10, higher is more important
    dependencies: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class ExecutionResult:
    """
    **Execution Result** (kết quả thực thi)
    
    Result from executing a strategy task.
    """
    task_name: str
    status: ExecutionStatus
    result: Any = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    retry_attempts: int = 0
    
    def __post_init__(self):
        if self.end_time and self.start_time:
            self.duration = self.end_time - self.start_time


class ParallelStrategyExecutor:
    """
    **Parallel Strategy Executor** (bộ thực thi chiến lược song song)
    
    Executes multiple strategies concurrently with proper isolation.
    """
    
    def __init__(self, max_workers: int = 4, default_timeout: float = 30.0):
        """
        Initialize parallel executor.
        
        Args:
            max_workers: Maximum number of parallel threads
            default_timeout: Default timeout for tasks (seconds)
        """
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="StrategyExec"
        )
        
        # Task tracking
        self.pending_tasks: Dict[str, StrategyTask] = {}
        self.running_tasks: Dict[str, Future] = {}
        self.completed_results: Dict[str, ExecutionResult] = {}
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Statistics
        self.stats = {
            'total_executed': 0,
            'successful': 0,
            'failed': 0,
            'timeouts': 0,
            'total_duration': 0.0
        }
        
        logger.info(f"🚀 **Parallel Executor initialized** "
                   f"(bộ thực thi song song đã khởi tạo): "
                   f"max_workers={max_workers}")
    
    def add_task(self, task: StrategyTask) -> bool:
        """
        **Add task** (thêm tác vụ) to execution queue.
        
        Args:
            task: Strategy task to add
            
        Returns:
            True if added successfully
        """
        with self.lock:
            if task.name in self.pending_tasks:
                logger.warning(f"⚠️ Task '{task.name}' already exists")
                return False
            
            self.pending_tasks[task.name] = task
            logger.debug(f"📝 Task added: {task.name} (priority: {task.priority})")
            return True
    
    def _execute_single_task(self, task: StrategyTask) -> ExecutionResult:
        """
        **Execute single task** (thực thi một tác vụ) with error handling.
        
        Args:
            task: Task to execute
            
        Returns:
            Execution result
        """
        result = ExecutionResult(
            task_name=task.name,
            status=ExecutionStatus.RUNNING,
            start_time=time.time()
        )
        
        try:
            logger.info(f"🔄 **Executing task** (đang thực thi tác vụ): {task.name}")
            
            # Execute the strategy function
            task_result = task.function(*task.args, **task.kwargs)
            
            result.status = ExecutionStatus.SUCCESS
            result.result = task_result
            result.end_time = time.time()
            
            logger.info(f"✅ **Task completed** (tác vụ hoàn thành): {task.name} "
                       f"in {result.duration:.2f}s")
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            result.end_time = time.time()
            
            logger.error(f"❌ **Task failed** (tác vụ thất bại): {task.name} - {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
        
        return result
    
    def _check_dependencies(self, task: StrategyTask) -> bool:
        """
        **Check dependencies** (kiểm tra phụ thuộc) for a task.
        
        Args:
            task: Task to check
            
        Returns:
            True if all dependencies are met
        """
        if not task.dependencies:
            return True
        
        for dep_name in task.dependencies:
            if dep_name not in self.completed_results:
                return False
            
            dep_result = self.completed_results[dep_name]
            if dep_result.status != ExecutionStatus.SUCCESS:
                logger.warning(f"⚠️ Dependency '{dep_name}' failed for task '{task.name}'")
                return False
        
        return True
    
    def execute_parallel(self, tasks: Optional[List[StrategyTask]] = None) -> Dict[str, ExecutionResult]:
        """
        **Execute tasks in parallel** (thực thi tác vụ song song).
        
        Args:
            tasks: List of tasks to execute (uses pending_tasks if None)
            
        Returns:
            Dictionary of task results
        """
        if tasks:
            for task in tasks:
                self.add_task(task)
        
        with self.lock:
            # Sort tasks by priority (higher first)
            sorted_tasks = sorted(
                self.pending_tasks.values(),
                key=lambda t: (-t.priority, t.name)
            )
        
        logger.info(f"🎯 **Starting parallel execution** "
                   f"(bắt đầu thực thi song song): {len(sorted_tasks)} tasks")
        
        futures: Dict[Future, StrategyTask] = {}
        
        for task in sorted_tasks:
            # Check dependencies
            if not self._check_dependencies(task):
                result = ExecutionResult(
                    task_name=task.name,
                    status=ExecutionStatus.SKIPPED,
                    error="Dependencies not met"
                )
                self.completed_results[task.name] = result
                logger.warning(f"⏭️ **Task skipped** (bỏ qua tác vụ): {task.name} "
                              f"(dependencies not met)")
                continue
            
            # Submit task for execution
            future = self.executor.submit(self._execute_single_task, task)
            futures[future] = task
            self.running_tasks[task.name] = future
        
        # Process results as they complete
        for future in as_completed(futures, timeout=self.default_timeout * 2):
            task = futures[future]
            
            try:
                # Get result with individual timeout
                result = future.result(timeout=task.timeout)
                
                with self.lock:
                    self.completed_results[task.name] = result
                    if task.name in self.running_tasks:
                        del self.running_tasks[task.name]
                    
                    # Update statistics
                    self.stats['total_executed'] += 1
                    if result.status == ExecutionStatus.SUCCESS:
                        self.stats['successful'] += 1
                    elif result.status == ExecutionStatus.FAILED:
                        self.stats['failed'] += 1
                    self.stats['total_duration'] += result.duration
                    
            except TimeoutError:
                # Handle timeout
                logger.error(f"⏱️ **Task timeout** (hết thời gian): {task.name} "
                           f"after {task.timeout}s")
                
                result = ExecutionResult(
                    task_name=task.name,
                    status=ExecutionStatus.TIMEOUT,
                    error=f"Timeout after {task.timeout}s"
                )
                
                with self.lock:
                    self.completed_results[task.name] = result
                    if task.name in self.running_tasks:
                        del self.running_tasks[task.name]
                    self.stats['timeouts'] += 1
                    
                # Cancel the future
                future.cancel()
                
            except Exception as e:
                logger.error(f"❌ **Unexpected error** (lỗi không mong đợi) "
                           f"for task {task.name}: {e}")
                
                result = ExecutionResult(
                    task_name=task.name,
                    status=ExecutionStatus.FAILED,
                    error=str(e)
                )
                
                with self.lock:
                    self.completed_results[task.name] = result
                    if task.name in self.running_tasks:
                        del self.running_tasks[task.name]
                    self.stats['failed'] += 1
        
        # Clear pending tasks
        with self.lock:
            self.pending_tasks.clear()
        
        self._log_execution_summary()
        
        return self.completed_results.copy()
    
    def aggregate_results(self) -> Dict[str, Any]:
        """
        **Aggregate results** (tổng hợp kết quả) from all executed tasks.
        
        Returns:
            Aggregated results dictionary
        """
        aggregated = {
            'summary': {
                'total_tasks': len(self.completed_results),
                'successful': sum(1 for r in self.completed_results.values() 
                                if r.status == ExecutionStatus.SUCCESS),
                'failed': sum(1 for r in self.completed_results.values() 
                            if r.status == ExecutionStatus.FAILED),
                'timeouts': sum(1 for r in self.completed_results.values() 
                              if r.status == ExecutionStatus.TIMEOUT),
                'skipped': sum(1 for r in self.completed_results.values() 
                             if r.status == ExecutionStatus.SKIPPED),
                'total_duration': sum(r.duration for r in self.completed_results.values()),
                'average_duration': 0.0
            },
            'tasks': {},
            'successful_results': [],
            'errors': []
        }
        
        # Calculate average duration
        if self.completed_results:
            successful_tasks = [r for r in self.completed_results.values() 
                              if r.status == ExecutionStatus.SUCCESS]
            if successful_tasks:
                aggregated['summary']['average_duration'] = (
                    sum(r.duration for r in successful_tasks) / len(successful_tasks)
                )
        
        # Collect individual task results
        for task_name, result in self.completed_results.items():
            task_info = {
                'status': result.status.value,
                'duration': result.duration,
                'retry_attempts': result.retry_attempts
            }
            
            if result.status == ExecutionStatus.SUCCESS:
                task_info['result'] = result.result
                aggregated['successful_results'].append({
                    'task': task_name,
                    'result': result.result,
                    'duration': result.duration
                })
            elif result.error:
                task_info['error'] = result.error
                aggregated['errors'].append({
                    'task': task_name,
                    'error': result.error,
                    'status': result.status.value
                })
            
            aggregated['tasks'][task_name] = task_info
        
        logger.info(f"📊 **Results aggregated** (kết quả đã tổng hợp): "
                   f"{aggregated['summary']['successful']}/{aggregated['summary']['total_tasks']} "
                   f"successful")
        
        return aggregated
    
    def _log_execution_summary(self):
        """Log execution summary"""
        logger.info("=" * 60)
        logger.info("📈 **Execution Summary** (tóm tắt thực thi):")
        logger.info(f"  Total executed: {self.stats['total_executed']}")
        logger.info(f"  Successful: {self.stats['successful']}")
        logger.info(f"  Failed: {self.stats['failed']}")
        logger.info(f"  Timeouts: {self.stats['timeouts']}")
        logger.info(f"  Total duration: {self.stats['total_duration']:.2f}s")
        
        if self.stats['successful'] > 0:
            avg_duration = self.stats['total_duration'] / self.stats['successful']
            logger.info(f"  Average duration: {avg_duration:.2f}s")
        logger.info("=" * 60)
    
    def shutdown(self, wait: bool = True):
        """
        **Shutdown executor** (tắt bộ thực thi).
        
        Args:
            wait: Whether to wait for running tasks to complete
        """
        logger.info(f"🛑 **Shutting down executor** (đang tắt bộ thực thi): "
                   f"wait={wait}")
        
        # Cancel running tasks if not waiting
        if not wait:
            with self.lock:
                for future in self.running_tasks.values():
                    future.cancel()
        
        self.executor.shutdown(wait=wait)
        
        logger.info("✅ **Executor shut down** (bộ thực thi đã tắt)")


def apply_parallel_strategies(pid: int, 
                             strategies: Optional[List[str]] = None,
                             max_workers: int = 4,
                             timeout: float = 30.0) -> Dict[str, Any]:
    """
    **Apply strategies in parallel** (áp dụng chiến lược song song).
    
    Main entry point for parallel strategy execution.
    
    Args:
        pid: Process ID to apply strategies to
        strategies: List of strategy names (None = all available)
        max_workers: Maximum parallel workers
        timeout: Timeout per strategy (seconds)
        
    Returns:
        Aggregated results from all strategies
    """
    logger.info(f"🎯 **Starting parallel strategy application** "
               f"(bắt đầu áp dụng chiến lược song song) for PID {pid}")
    
    # Import strategy modules
    try:
        from cloak_strategies import StrategyEngine, CloakRequest
        from resource_control import ResourceManager
    except ImportError as e:
        logger.error(f"❌ Failed to import required modules: {e}")
        return {'error': str(e)}
    
    # Default strategies if none specified
    if strategies is None:
        strategies = ['gpu', 'network', 'memory', 'cache']
    
    # Create executor
    executor = ParallelStrategyExecutor(max_workers=max_workers, 
                                       default_timeout=timeout)
    
    # Initialize strategy engine
    strategy_engine = StrategyEngine()
    resource_manager = ResourceManager()
    
    # Create tasks for each strategy
    tasks = []
    
    for strategy_name in strategies:
        # Create closure for strategy execution
        def execute_strategy(name=strategy_name, engine=strategy_engine, rm=resource_manager):
            """Execute a single strategy"""
            request = CloakRequest(
                pid=pid,
                strategy=name,
                params={}
            )
            
            # Process through strategy engine
            result = engine.process_request(request)
            
            # Apply through resource manager if GPU strategy
            if name == 'gpu' and result.success:
                rm_result = rm.manage_resources(pid, {'strategy': name})
                result.metadata['resource_manager'] = rm_result
            
            return result
        
        # Create task
        task = StrategyTask(
            name=strategy_name,
            function=execute_strategy,
            timeout=timeout,
            priority=10 if strategy_name == 'gpu' else 5  # GPU higher priority
        )
        
        tasks.append(task)
    
    # Add dependency example: memory depends on gpu
    for task in tasks:
        if task.name == 'memory':
            task.dependencies = ['gpu']
    
    try:
        # Execute all tasks in parallel
        results = executor.execute_parallel(tasks)
        
        # Aggregate results
        aggregated = executor.aggregate_results()
        
        # Add PID and timestamp
        aggregated['pid'] = pid
        aggregated['timestamp'] = datetime.now().isoformat()
        
        logger.info(f"✅ **Parallel execution completed** "
                   f"(thực thi song song hoàn thành) for PID {pid}")
        
        return aggregated
        
    finally:
        # Clean shutdown
        executor.shutdown(wait=True)


# Test function
def test_parallel_execution():
    """
    **Test parallel execution** (kiểm tra thực thi song song).
    """
    import random
    
    def dummy_task(name: str, duration: float) -> Dict[str, Any]:
        """Dummy task that simulates work"""
        logger.info(f"🔧 Task {name} starting (duration: {duration}s)")
        time.sleep(duration)
        
        # Randomly fail some tasks for testing
        if random.random() < 0.2:  # 20% failure rate
            raise Exception(f"Task {name} randomly failed")
        
        return {
            'name': name,
            'result': f"Completed {name}",
            'duration': duration
        }
    
    # Create executor
    executor = ParallelStrategyExecutor(max_workers=3, default_timeout=5.0)
    
    # Create test tasks
    tasks = [
        StrategyTask(
            name=f"task_{i}",
            function=dummy_task,
            args=(f"task_{i}", random.uniform(0.5, 3.0)),
            timeout=4.0,
            priority=random.randint(1, 10)
        )
        for i in range(6)
    ]
    
    # Execute tasks
    results = executor.execute_parallel(tasks)
    
    # Show results
    logger.info("\n📊 **Test Results** (kết quả kiểm tra):")
    for task_name, result in results.items():
        logger.info(f"  {task_name}: {result.status.value} "
                   f"(duration: {result.duration:.2f}s)")
    
    # Aggregate results
    aggregated = executor.aggregate_results()
    logger.info(f"\n📈 **Aggregated Summary** (tóm tắt tổng hợp): "
               f"{aggregated['summary']}")
    
    # Shutdown
    executor.shutdown()
    
    return aggregated


if __name__ == "__main__":
    # Run test if executed directly
    test_parallel_execution()
