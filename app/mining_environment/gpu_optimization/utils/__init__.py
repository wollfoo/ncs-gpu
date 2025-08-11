"""
GPU Optimization Utilities Package.
Package tiện ích tối ưu hóa GPU.

Provides common utilities for logging, validation, and error handling.
Cung cấp các tiện ích chung cho logging, validation, và xử lý lỗi.
"""

# Logger exports
from .logger import (
    GPULogger,
    get_logger,
    debug,
    info,
    warning,
    error,
    critical,
    exception,
    log_execution_time,
    log_errors
)

# Validator exports
from .validators import (
    ValidationError,
    Validator,
    GPUValidator,
    validate_decorator,
    validate_config,
    validate_batch_operation
)

# Exception exports
from .exceptions import (
    # Base exception
    GPUOptimizationError,
    
    # Hardware exceptions
    GPUHardwareError,
    GPUNotFoundError,
    GPUMemoryError,
    GPUTemperatureError,
    GPUPowerError,
    
    # Configuration exceptions
    ConfigurationError,
    InvalidConfigError,
    MissingConfigError,
    
    # Orchestration exceptions
    OrchestrationError,
    WorkerPoolError,
    TaskSchedulingError,
    
    # Strategy exceptions
    StrategyError,
    StrategyNotFoundError,
    StrategyExecutionError,
    
    # Monitoring exceptions
    MonitoringError,
    MetricsCollectionError,
    
    # Coordination exceptions
    CoordinationError,
    DeadlockError,
    SynchronizationError,
    
    # Resource exceptions
    ResourceError,
    ResourceExhaustedError,
    
    # Other exceptions
    TimeoutError,
    
    # Exception handler
    handle_exception
)

__all__ = [
    # Logger
    'GPULogger',
    'get_logger',
    'debug',
    'info',
    'warning',
    'error',
    'critical',
    'exception',
    'log_execution_time',
    'log_errors',
    
    # Validators
    'ValidationError',
    'Validator',
    'GPUValidator',
    'validate_decorator',
    'validate_config',
    'validate_batch_operation',
    
    # Exceptions
    'GPUOptimizationError',
    'GPUHardwareError',
    'GPUNotFoundError',
    'GPUMemoryError',
    'GPUTemperatureError',
    'GPUPowerError',
    'ConfigurationError',
    'InvalidConfigError',
    'MissingConfigError',
    'OrchestrationError',
    'WorkerPoolError',
    'TaskSchedulingError',
    'StrategyError',
    'StrategyNotFoundError',
    'StrategyExecutionError',
    'MonitoringError',
    'MetricsCollectionError',
    'CoordinationError',
    'DeadlockError',
    'SynchronizationError',
    'ResourceError',
    'ResourceExhaustedError',
    'TimeoutError',
    'handle_exception'
]
