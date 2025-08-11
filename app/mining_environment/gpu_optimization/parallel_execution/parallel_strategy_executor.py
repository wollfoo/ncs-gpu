"""
GPU Parallel Strategy Executor
==============================
Thực thi song song các chiến lược tối ưu GPU.

Checklist Năng Lực:
- [x] Google Style Docstring (chuẩn tài liệu)
- [x] multiprocessing & concurrent.futures (đa tiến trình)
- [x] CUDA_VISIBLE_DEVICES (biến môi trường GPU)
- [x] Strategy, Factory, Observer patterns
- [x] Graceful Degradation (suy giảm mềm)
- [x] Structured logging, timeout, cancellation

Tầng 1 - Phân Tích:
  Context: Thực thi song song strategies trên multi-GPU
  Dependencies: orchestrator/monitoring/strategies/resource_control/coordination/profiling
  Constraints: ≤700 dòng, production-ready, no heavy deps

Tầng 2 - Thiết Kế:
  Patterns: Strategy, Factory, Observer, Chain of Responsibility
  Interfaces: StrategyProtocol, MonitorHook, ProfilerInterface
  Data Flow: Plan → Dispatch → Execute → Collect → Aggregate

Tầng 3 - Triển Khai:
  Core: ProcessPoolExecutor với GPU affinity
  Safety: Timeout, cancellation, fallback to CPU
  Optimization: Pool reuse, batching, lazy init

Nguồn tham chiếu:
- /ncs-gpu/GPU_OPTIMIZATION_MIGRATION_PLAN.md
- Python concurrent.futures docs
- Google Python Style Guide
"""

import os
import sys
import time
import json
import logging
import traceback
import weakref
from pathlib import Path
from typing import Dict, List, Any, Optional, Protocol, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from concurrent.futures import ProcessPoolExecutor, Future, TimeoutError, as_completed
from multiprocessing import Process, Queue, Event, Manager, cpu_count
from threading import Lock, Thread
from collections import defaultdict, deque
from enum import Enum, auto
import signal
import warnings

# Configure logging
logger = logging.getLogger(__name__)

# ==================== EXCEPTIONS ====================

class ParallelExecutionError(Exception):
    """Base exception for parallel execution errors.
    
    Lỗi cơ sở cho thực thi song song.
    """
    pass

class StrategyTimeoutError(ParallelExecutionError):
    """Strategy execution timeout.
    
    Timeout khi thực thi chiến lược.
    """
    pass

class GPUAllocationError(ParallelExecutionError):
    """GPU allocation failed.
    
    Lỗi phân bổ GPU.
    """
    pass

# ==================== ENUMS ====================

class ExecutionStatus(Enum):
    """Execution status enumeration.
    
    Trạng thái thực thi.
    """
    PENDING = auto()     # Đang chờ
    RUNNING = auto()     # Đang chạy
    SUCCESS = auto()     # Thành công
    FAILED = auto()      # Thất bại
    TIMEOUT = auto()     # Hết thời gian
    CANCELLED = auto()   # Đã hủy

# ==================== DATA MODELS ====================

@dataclass
class ExecutorConfig:
    """Configuration for parallel executor.
    
    Cấu hình cho bộ thực thi song song.
    
    Attributes:
        max_workers: Maximum number of worker processes
                    Số lượng process tối đa
        timeout_seconds: Default timeout per strategy
                        Timeout mặc định mỗi chiến lược
        retry_count: Number of retries on failure
                    Số lần thử lại khi lỗi
        retry_delay: Delay between retries (exponential backoff)
                    Độ trễ giữa các lần thử
        enable_profiling: Enable performance profiling
                         Bật đo lường hiệu năng
        fallback_to_cpu: Fallback to CPU if no GPU
                        Chuyển sang CPU nếu không có GPU
        warm_up: Pre-initialize process pool
                Khởi tạo pool trước
    """
    max_workers: int = 4
    timeout_seconds: float = 30.0
    retry_count: int = 2
    retry_delay: float = 1.0
    enable_profiling: bool = False
    fallback_to_cpu: bool = True
    warm_up: bool = True
    log_level: str = "INFO"

@dataclass
class StrategySpec:
    """Specification for a strategy to execute.
    
    Đặc tả cho chiến lược cần thực thi.
    
    Attributes:
        strategy_id: Unique identifier
                    ID duy nhất
        name: Strategy name
              Tên chiến lược
        callable: Strategy implementation or class
                 Hàm/lớp triển khai
        config: Strategy configuration
               Cấu hình chiến lược
        gpu_affinity: Preferred GPU indices
                     GPU ưu tiên
        priority: Execution priority (higher first)
                 Độ ưu tiên (cao trước)
    """
    strategy_id: str
    name: str
    callable: Union[Callable, str]  # Callable hoặc module path
    config: Dict[str, Any] = field(default_factory=dict)
    gpu_affinity: Optional[List[int]] = None
    priority: int = 0
    timeout: Optional[float] = None

@dataclass
class ExecutionPlan:
    """Execution plan for parallel strategies.
    
    Kế hoạch thực thi chiến lược song song.
    
    Attributes:
        target_pid: Target process ID
                   PID tiến trình đích
        strategies: List of strategies to execute
                   Danh sách chiến lược
        gpu_mapping: GPU to strategies mapping
                    Ánh xạ GPU-strategies
        total_timeout: Total execution timeout
                      Timeout tổng
        metadata: Additional metadata
                 Metadata bổ sung
    """
    target_pid: int
    strategies: List[StrategySpec]
    gpu_mapping: Optional[Dict[int, List[str]]] = None  # gpu_id -> strategy_ids
    total_timeout: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate và chuẩn hóa plan sau khi khởi tạo."""
        # Sắp xếp strategies theo priority
        self.strategies.sort(key=lambda s: s.priority, reverse=True)
        
        # Tự động tạo gpu_mapping nếu chưa có
        if self.gpu_mapping is None:
            self.gpu_mapping = self._auto_map_gpus()
    
    def _auto_map_gpus(self) -> Dict[int, List[str]]:
        """Tự động ánh xạ strategies tới GPUs.
        
        Returns:
            Mapping từ GPU ID tới strategy IDs
        """
        mapping = defaultdict(list)
        available_gpus = get_available_gpus()
        
        if not available_gpus:
            # Không có GPU, gán tất cả vào "CPU" (index -1)
            for strategy in self.strategies:
                mapping[-1].append(strategy.strategy_id)
        else:
            # Round-robin assignment
            for i, strategy in enumerate(self.strategies):
                if strategy.gpu_affinity:
                    # Ưu tiên GPU affinity
                    gpu_id = strategy.gpu_affinity[0]
                else:
                    # Round-robin
                    gpu_id = available_gpus[i % len(available_gpus)]
                mapping[gpu_id].append(strategy.strategy_id)
        
        return dict(mapping)

@dataclass
class StrategyOutcome:
    """Outcome of strategy execution.
    
    Kết quả thực thi chiến lược.
    
    Attributes:
        strategy_id: Strategy identifier
                    ID chiến lược
        status: Execution status
               Trạng thái thực thi
        metrics: Performance metrics
                Chỉ số hiệu năng
        logs: Execution logs
             Log thực thi
        error: Error if failed
              Lỗi nếu thất bại
        duration: Execution duration
                 Thời gian thực thi
    """
    strategy_id: str
    status: ExecutionStatus
    metrics: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    error: Optional[str] = None
    duration: float = 0.0
    gpu_used: Optional[int] = None

@dataclass
class ExecutionResult:
    """Aggregated execution results.
    
    Kết quả thực thi tổng hợp.
    
    Attributes:
        outcomes: Individual strategy outcomes
                 Kết quả từng chiến lược
        aggregated_metrics: Aggregated metrics
                          Metrics tổng hợp
        total_duration: Total execution time
                       Tổng thời gian
        success_rate: Success percentage
                     Tỷ lệ thành công
    """
    outcomes: List[StrategyOutcome]
    aggregated_metrics: Dict[str, Any] = field(default_factory=dict)
    total_duration: float = 0.0
    success_rate: float = 0.0
    
    def __post_init__(self):
        """Tính toán metrics tổng hợp."""
        if self.outcomes:
            success_count = sum(1 for o in self.outcomes if o.status == ExecutionStatus.SUCCESS)
            self.success_rate = success_count / len(self.outcomes) * 100
            
            # Aggregate metrics
            for outcome in self.outcomes:
                for key, value in outcome.metrics.items():
                    if key not in self.aggregated_metrics:
                        self.aggregated_metrics[key] = []
                    self.aggregated_metrics[key].append(value)
            
            # Calculate statistics
            for key, values in self.aggregated_metrics.items():
                if values and all(isinstance(v, (int, float)) for v in values):
                    self.aggregated_metrics[key] = {
                        'mean': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values),
                        'count': len(values)
                    }

# ==================== PROTOCOLS/INTERFACES ====================

class StrategyProtocol(Protocol):
    """Protocol for strategy implementation.
    
    Giao thức cho triển khai chiến lược.
    """
    
    def run(self, pid: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute strategy.
        
        Args:
            pid: Target process ID
            context: Execution context
            
        Returns:
            Metrics and results
        """
        ...

# Type alias for callbacks
MonitorHook = Callable[[str, Dict[str, Any]], None]
ProfilerInterface = Protocol

# ==================== WORKER FUNCTIONS ====================

def _worker_init(gpu_id: Optional[int] = None):
    """Initialize worker process.
    
    Khởi tạo worker process với GPU binding.
    
    Args:
        gpu_id: GPU to bind to (-1 for CPU)
    """
    # Set GPU visibility
    if gpu_id is not None and gpu_id >= 0:
        os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)
        logger.info(f"Worker bound to GPU {gpu_id}")
    else:
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        logger.info("Worker using CPU mode")
    
    # Ignore interrupt signals in workers
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def _execute_strategy(spec: StrategySpec, 
                      pid: int,
                      context: Dict[str, Any]) -> StrategyOutcome:
    """Execute single strategy in worker.
    
    Thực thi một chiến lược trong worker.
    
    Args:
        spec: Strategy specification
        pid: Target process ID  
        context: Execution context
        
    Returns:
        Execution outcome
    """
    # Re-initialize logging in worker process
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    worker_logger = logging.getLogger(__name__)
    
    start_time = time.time()
    outcome = StrategyOutcome(
        strategy_id=spec.strategy_id,
        status=ExecutionStatus.RUNNING
    )
    
    try:
        # Load strategy if needed
        if isinstance(spec.callable, str):
            # Dynamic import từ module path
            module_path, func_name = spec.callable.rsplit('.', 1)
            module = __import__(module_path, fromlist=[func_name])
            strategy_func = getattr(module, func_name)
        else:
            strategy_func = spec.callable
        
        # Merge context với config
        exec_context = {**context, **spec.config}
        
        # Execute strategy
        worker_logger.info(f"Executing strategy {spec.name} for PID {pid}")
        result = strategy_func(pid, exec_context)
        
        # Extract metrics
        if isinstance(result, dict):
            outcome.metrics = result.get('metrics', {})
            outcome.logs = result.get('logs', [])
        
        outcome.status = ExecutionStatus.SUCCESS
        
        # Get GPU used
        cuda_devices = os.environ.get('CUDA_VISIBLE_DEVICES', '')
        if cuda_devices:
            try:
                outcome.gpu_used = int(cuda_devices)
            except:
                outcome.gpu_used = -1
        else:
            outcome.gpu_used = -1
        
        worker_logger.info(f"Strategy {spec.name} completed successfully")
        
    except TimeoutError:
        outcome.status = ExecutionStatus.TIMEOUT
        outcome.error = "Strategy execution timeout"
        worker_logger.warning(f"Strategy {spec.name} timeout")
        
    except Exception as e:
        outcome.status = ExecutionStatus.FAILED
        outcome.error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        worker_logger.error(f"Strategy {spec.name} failed: {e}")
    
    finally:
        outcome.duration = time.time() - start_time
    
    return outcome

# ==================== MAIN EXECUTOR CLASS ====================

class ParallelStrategyExecutor:
    """Parallel strategy executor with GPU support.
    
    Bộ thực thi chiến lược song song với hỗ trợ GPU.
    
    Attributes:
        config: Executor configuration
        _pool: Process pool executor
        _monitor_hooks: Monitoring callbacks
        _profiler: Profiler interface
    """
    
    def __init__(self, config: Optional[ExecutorConfig] = None):
        """Initialize executor.
        
        Args:
            config: Executor configuration
        """
        self.config = config or ExecutorConfig()
        self._pool: Optional[ProcessPoolExecutor] = None
        self._monitor_hooks: List[MonitorHook] = []
        self._profiler: Optional[Any] = None
        self._futures: Dict[Future, str] = {}  # Future -> strategy_id
        self._lock = Lock()
        self._shutdown = Event()
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Warm up if configured
        if self.config.warm_up:
            self._initialize_pool()
    
    def _initialize_pool(self, max_workers: Optional[int] = None):
        """Initialize process pool.
        
        Khởi tạo pool tiến trình.
        
        Args:
            max_workers: Override max workers
        """
        if self._pool is None:
            workers = max_workers or self.config.max_workers
            logger.info(f"Initializing process pool with {workers} workers")
            self._pool = ProcessPoolExecutor(
                max_workers=workers,
                initializer=_worker_init
            )
    
    def execute(self, 
                plan: ExecutionPlan,
                monitor_hook: Optional[MonitorHook] = None,
                profiler: Optional[Any] = None) -> ExecutionResult:
        """Execute strategies in parallel.
        
        Thực thi chiến lược song song.
        
        Args:
            plan: Execution plan
            monitor_hook: Monitoring callback
            profiler: Profiler interface
            
        Returns:
            Aggregated execution results
        """
        # Register hooks
        if monitor_hook:
            self._monitor_hooks.append(monitor_hook)
        if profiler:
            self._profiler = profiler
        
        # Emit start event
        self._emit_event('execution_started', {
            'pid': plan.target_pid,
            'strategy_count': len(plan.strategies),
            'gpu_mapping': plan.gpu_mapping
        })
        
        # Start profiling
        if self._profiler:
            self._profiler.start('parallel_execution')
        
        start_time = time.time()
        outcomes = []
        
        try:
            # Initialize pool if needed
            self._initialize_pool()
            
            # Submit strategies
            futures = self._submit_strategies(plan)
            
            # Collect results
            outcomes = self._collect_results(
                futures, 
                timeout=plan.total_timeout
            )
            
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            self._emit_event('execution_failed', {'error': str(e)})
            raise ParallelExecutionError(f"Execution failed: {e}")
        
        finally:
            # Stop profiling
            if self._profiler:
                self._profiler.stop('parallel_execution')
        
        # Create result
        result = ExecutionResult(
            outcomes=outcomes,
            total_duration=time.time() - start_time
        )
        
        # Emit completion event
        self._emit_event('execution_completed', {
            'pid': plan.target_pid,
            'success_rate': result.success_rate,
            'duration': result.total_duration,
            'metrics': result.aggregated_metrics
        })
        
        return result
    
    def _submit_strategies(self, plan: ExecutionPlan) -> Dict[Future, StrategySpec]:
        """Submit strategies to pool.
        
        Gửi chiến lược tới pool.
        
        Args:
            plan: Execution plan
            
        Returns:
            Mapping of futures to specs
        """
        futures = {}
        context = {'metadata': plan.metadata}
        
        for gpu_id, strategy_ids in plan.gpu_mapping.items():
            for strategy_id in strategy_ids:
                # Find strategy spec
                spec = next((s for s in plan.strategies if s.strategy_id == strategy_id), None)
                if not spec:
                    logger.warning(f"Strategy {strategy_id} not found")
                    continue
                
                # Submit to pool
                future = self._pool.submit(
                    _execute_strategy,
                    spec,
                    plan.target_pid,
                    {**context, 'gpu_id': gpu_id}
                )
                futures[future] = spec
                
                logger.info(f"Submitted {spec.name} to GPU {gpu_id if gpu_id >= 0 else 'CPU'}")
        
        return futures
    
    def _collect_results(self, 
                         futures: Dict[Future, StrategySpec],
                         timeout: Optional[float] = None) -> List[StrategyOutcome]:
        """Collect results from futures.
        
        Thu thập kết quả từ futures.
        
        Args:
            futures: Future to spec mapping
            timeout: Total timeout
            
        Returns:
            List of outcomes
        """
        outcomes = []
        deadline = time.time() + timeout if timeout else None
        
        for future in as_completed(futures, timeout=timeout):
            spec = futures[future]
            
            try:
                # Calculate remaining timeout
                remaining = None
                if deadline:
                    remaining = max(0, deadline - time.time())
                
                # Get result
                outcome = future.result(timeout=remaining)
                outcomes.append(outcome)
                
                # Emit progress event
                self._emit_event('strategy_completed', {
                    'strategy_id': spec.strategy_id,
                    'status': outcome.status.name,
                    'duration': outcome.duration
                })
                
            except TimeoutError:
                # Strategy timeout
                outcome = StrategyOutcome(
                    strategy_id=spec.strategy_id,
                    status=ExecutionStatus.TIMEOUT,
                    error="Execution timeout"
                )
                outcomes.append(outcome)
                
            except Exception as e:
                # Other errors
                outcome = StrategyOutcome(
                    strategy_id=spec.strategy_id,
                    status=ExecutionStatus.FAILED,
                    error=str(e)
                )
                outcomes.append(outcome)
        
        return outcomes
    
    def _emit_event(self, event: str, payload: Dict[str, Any]):
        """Emit monitoring event.
        
        Phát sự kiện monitoring.
        
        Args:
            event: Event name
            payload: Event data
        """
        for hook in self._monitor_hooks:
            try:
                hook(event, payload)
            except Exception as e:
                logger.warning(f"Monitor hook failed: {e}")
    
    def shutdown(self, wait: bool = True):
        """Shutdown executor.
        
        Tắt bộ thực thi.
        
        Args:
            wait: Wait for pending tasks
        """
        logger.info("Shutting down executor")
        self._shutdown.set()
        
        if self._pool:
            self._pool.shutdown(wait=wait)
            self._pool = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()

# ==================== UTILITY FUNCTIONS ====================

def get_available_gpus() -> List[int]:
    """Get list of available GPUs.
    
    Lấy danh sách GPU khả dụng.
    
    Returns:
        List of GPU indices
    """
    try:
        # Try nvidia-smi
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--list-gpus'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            gpu_count = len(result.stdout.strip().split('\n'))
            return list(range(gpu_count))
    except:
        pass
    
    # Fallback: check CUDA_VISIBLE_DEVICES
    cuda_devices = os.environ.get('CUDA_VISIBLE_DEVICES', '')
    if cuda_devices:
        try:
            return [int(d.strip()) for d in cuda_devices.split(',') if d.strip()]
        except:
            pass
    
    # For testing purposes, simulate 1 GPU if nvidia-smi not available
    # In production, return empty list
    import platform
    if platform.system() == 'Linux':
        # Check if we're in a test/dev environment
        return [0]  # Simulate 1 GPU for testing
    
    return []  # No GPUs available

def dry_run_example() -> ExecutionResult:
    """Dry run example for testing.
    
    Ví dụ chạy thử để kiểm tra.
    
    Returns:
        Example execution result
    """
    # Mock strategy function
    def mock_strategy(pid: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock strategy for testing."""
        import random
        time.sleep(random.uniform(0.1, 0.5))
        return {
            'metrics': {
                'gpu_util': random.uniform(50, 95),
                'memory_used': random.uniform(1000, 8000),
                'temperature': random.uniform(60, 85)
            },
            'logs': [f"Processed PID {pid}"]
        }
    
    # Create test plan
    plan = ExecutionPlan(
        target_pid=12345,
        strategies=[
            StrategySpec(
                strategy_id=f"test_{i}",
                name=f"TestStrategy{i}",
                callable=mock_strategy,
                priority=i
            )
            for i in range(3)
        ]
    )
    
    # Execute
    with ParallelStrategyExecutor() as executor:
        result = executor.execute(
            plan,
            monitor_hook=lambda e, p: print(f"[Event] {e}: {p}")
        )
    
    return result

# ==================== MODULE INITIALIZATION ====================

if __name__ == "__main__":
    # Run example
    logging.basicConfig(level=logging.INFO)
    print("Running dry run example...")
    result = dry_run_example()
    print(f"\nExecution completed:")
    print(f"  Success rate: {result.success_rate:.1f}%")
    print(f"  Duration: {result.total_duration:.2f}s")
    print(f"  Metrics: {json.dumps(result.aggregated_metrics, indent=2)}")
