"""
Parallel Execution Package
==========================
Parallel strategy execution framework for GPU optimization.
Framework thực thi chiến lược song song cho tối ưu GPU.

Modules:
    parallel_strategy_executor: Main executor for parallel strategy execution
                               Bộ thực thi chính cho chiến lược song song
"""

from .parallel_strategy_executor import (
    ParallelStrategyExecutor,
    ExecutionPlan,
    ExecutionResult,
    StrategySpec,
    StrategyOutcome,
    ExecutorConfig,
    # Exceptions  
    ParallelExecutionError,
    StrategyTimeoutError,
    GPUAllocationError,
    # Utilities
    dry_run_example,
    get_available_gpus
)

__all__ = [
    # Main classes
    'ParallelStrategyExecutor',
    'ExecutionPlan',
    'ExecutionResult',
    'StrategySpec',
    'StrategyOutcome', 
    'ExecutorConfig',
    # Exceptions
    'ParallelExecutionError',
    'StrategyTimeoutError',
    'GPUAllocationError',
    # Utilities
    'dry_run_example',
    'get_available_gpus'
]

__version__ = '2.0.0'
