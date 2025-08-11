"""
GPU Optimization Exceptions Module.
Module exceptions cho tối ưu hóa GPU.

Provides comprehensive exception hierarchy for GPU operations.
Cung cấp hệ thống phân cấp exception toàn diện cho hoạt động GPU.
"""

import sys
import traceback
from typing import Optional, Dict, Any, List
from datetime import datetime


class GPUOptimizationError(Exception):
    """
    Base exception for all GPU optimization errors.
    Exception gốc cho mọi lỗi tối ưu hóa GPU.
    """
    
    def __init__(self, message: str, 
                 error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None,
                 suggestions: Optional[List[str]] = None):
        """
        Initialize GPU optimization error.
        Khởi tạo lỗi tối ưu hóa GPU.
        
        Args:
            message: Error message (thông báo lỗi)
            error_code: Optional error code (mã lỗi tùy chọn)
            details: Additional error details (chi tiết bổ sung)
            suggestions: Recovery suggestions (gợi ý khắc phục)
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "GPU_ERROR"
        self.details = details or {}
        self.suggestions = suggestions or []
        self.timestamp = datetime.utcnow().isoformat()
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary.
        Chuyển exception thành dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details,
            'suggestions': self.suggestions,
            'timestamp': self.timestamp,
            'traceback': traceback.format_exc()
        }
    
    def __str__(self) -> str:
        """
        String representation of error.
        Biểu diễn chuỗi của lỗi.
        """
        parts = [f"[{self.error_code}] {self.message}"]
        
        if self.details:
            parts.append(f"Details: {self.details}")
            
        if self.suggestions:
            parts.append("Suggestions:")
            for suggestion in self.suggestions:
                parts.append(f"  - {suggestion}")
                
        return "\n".join(parts)


# GPU Hardware Exceptions
class GPUHardwareError(GPUOptimizationError):
    """
    GPU hardware-related errors.
    Lỗi liên quan đến phần cứng GPU.
    """
    
    def __init__(self, message: str, gpu_id: Optional[int] = None, **kwargs):
        """
        Initialize GPU hardware error.
        Khởi tạo lỗi phần cứng GPU.
        """
        if gpu_id is not None:
            kwargs.setdefault('details', {})['gpu_id'] = gpu_id
        super().__init__(message, error_code="GPU_HW_ERROR", **kwargs)


class GPUNotFoundError(GPUHardwareError):
    """
    GPU not found or not accessible.
    Không tìm thấy hoặc không thể truy cập GPU.
    """
    
    def __init__(self, gpu_id: Optional[int] = None):
        """
        Initialize GPU not found error.
        Khởi tạo lỗi không tìm thấy GPU.
        """
        message = f"GPU {gpu_id} not found" if gpu_id is not None else "No GPU found"
        suggestions = [
            "Check if GPU is properly installed",
            "Verify CUDA/driver installation",
            "Run 'nvidia-smi' to list available GPUs",
            "Check GPU ID is valid (0-based index)"
        ]
        super().__init__(message, gpu_id=gpu_id, suggestions=suggestions)


class GPUMemoryError(GPUHardwareError):
    """
    GPU memory allocation or overflow error.
    Lỗi cấp phát hoặc tràn bộ nhớ GPU.
    """
    
    def __init__(self, required: int, available: int, gpu_id: Optional[int] = None):
        """
        Initialize GPU memory error.
        Khởi tạo lỗi bộ nhớ GPU.
        """
        message = f"Insufficient GPU memory: required {required}MB, available {available}MB"
        suggestions = [
            "Reduce batch size",
            "Clear GPU memory cache",
            "Use gradient checkpointing",
            "Enable mixed precision training",
            "Use model parallelism"
        ]
        details = {'required_mb': required, 'available_mb': available}
        super().__init__(message, gpu_id=gpu_id, details=details, suggestions=suggestions)


class GPUTemperatureError(GPUHardwareError):
    """
    GPU temperature threshold exceeded.
    Vượt ngưỡng nhiệt độ GPU.
    """
    
    def __init__(self, temperature: float, threshold: float, gpu_id: Optional[int] = None):
        """
        Initialize GPU temperature error.
        Khởi tạo lỗi nhiệt độ GPU.
        """
        message = f"GPU temperature {temperature}°C exceeds threshold {threshold}°C"
        suggestions = [
            "Improve cooling/ventilation",
            "Reduce GPU power limit",
            "Lower clock speeds",
            "Clean GPU fans and heatsink",
            "Check thermal paste condition"
        ]
        details = {'temperature': temperature, 'threshold': threshold}
        super().__init__(message, gpu_id=gpu_id, details=details, suggestions=suggestions)


class GPUPowerError(GPUHardwareError):
    """
    GPU power limit or consumption error.
    Lỗi giới hạn hoặc tiêu thụ điện GPU.
    """
    
    def __init__(self, power: float, limit: float, gpu_id: Optional[int] = None):
        """
        Initialize GPU power error.
        Khởi tạo lỗi điện năng GPU.
        """
        message = f"GPU power {power}W exceeds limit {limit}W"
        suggestions = [
            "Check PSU capacity",
            "Reduce power limit via nvidia-smi",
            "Lower GPU clock speeds",
            "Optimize workload distribution"
        ]
        details = {'power_watts': power, 'limit_watts': limit}
        super().__init__(message, gpu_id=gpu_id, details=details, suggestions=suggestions)


# Configuration Exceptions
class ConfigurationError(GPUOptimizationError):
    """
    Configuration-related errors.
    Lỗi liên quan đến cấu hình.
    """
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        """
        Initialize configuration error.
        Khởi tạo lỗi cấu hình.
        """
        if config_key:
            kwargs.setdefault('details', {})['config_key'] = config_key
        super().__init__(message, error_code="CONFIG_ERROR", **kwargs)


class InvalidConfigError(ConfigurationError):
    """
    Invalid configuration value or format.
    Giá trị hoặc định dạng cấu hình không hợp lệ.
    """
    
    def __init__(self, config_key: str, value: Any, expected: str):
        """
        Initialize invalid config error.
        Khởi tạo lỗi cấu hình không hợp lệ.
        """
        message = f"Invalid config '{config_key}': got {value}, expected {expected}"
        suggestions = [
            f"Check config file for '{config_key}'",
            f"Ensure value matches expected format: {expected}",
            "Review configuration documentation",
            "Use default configuration as template"
        ]
        details = {'value': value, 'expected': expected}
        super().__init__(message, config_key=config_key, 
                        details=details, suggestions=suggestions)


class MissingConfigError(ConfigurationError):
    """
    Required configuration is missing.
    Thiếu cấu hình bắt buộc.
    """
    
    def __init__(self, config_key: str, config_file: Optional[str] = None):
        """
        Initialize missing config error.
        Khởi tạo lỗi thiếu cấu hình.
        """
        message = f"Missing required configuration: '{config_key}'"
        suggestions = [
            f"Add '{config_key}' to configuration",
            "Check environment variables",
            "Use default configuration template",
            "Verify config file path"
        ]
        details = {'missing_key': config_key}
        if config_file:
            details['config_file'] = config_file
        super().__init__(message, config_key=config_key,
                        details=details, suggestions=suggestions)


# Orchestration Exceptions
class OrchestrationError(GPUOptimizationError):
    """
    Orchestration and scheduling errors.
    Lỗi điều phối và lập lịch.
    """
    
    def __init__(self, message: str, **kwargs):
        """
        Initialize orchestration error.
        Khởi tạo lỗi điều phối.
        """
        super().__init__(message, error_code="ORCH_ERROR", **kwargs)


class WorkerPoolError(OrchestrationError):
    """
    Worker pool management error.
    Lỗi quản lý worker pool.
    """
    
    def __init__(self, message: str, num_workers: Optional[int] = None):
        """
        Initialize worker pool error.
        Khởi tạo lỗi worker pool.
        """
        details = {}
        if num_workers is not None:
            details['num_workers'] = num_workers
        suggestions = [
            "Check worker pool configuration",
            "Verify resource availability",
            "Review worker lifecycle logs",
            "Restart worker pool"
        ]
        super().__init__(message, details=details, suggestions=suggestions)


class TaskSchedulingError(OrchestrationError):
    """
    Task scheduling or execution error.
    Lỗi lập lịch hoặc thực thi tác vụ.
    """
    
    def __init__(self, task_id: str, reason: str):
        """
        Initialize task scheduling error.
        Khởi tạo lỗi lập lịch tác vụ.
        """
        message = f"Failed to schedule task {task_id}: {reason}"
        details = {'task_id': task_id, 'reason': reason}
        suggestions = [
            "Check task dependencies",
            "Verify resource requirements",
            "Review scheduling constraints",
            "Check for deadlocks"
        ]
        super().__init__(message, details=details, suggestions=suggestions)


# Strategy Exceptions
class StrategyError(GPUOptimizationError):
    """
    Strategy selection or execution error.
    Lỗi chọn hoặc thực thi chiến lược.
    """
    
    def __init__(self, message: str, strategy_name: Optional[str] = None, **kwargs):
        """
        Initialize strategy error.
        Khởi tạo lỗi chiến lược.
        """
        if strategy_name:
            kwargs.setdefault('details', {})['strategy'] = strategy_name
        super().__init__(message, error_code="STRATEGY_ERROR", **kwargs)


class StrategyNotFoundError(StrategyError):
    """
    Requested strategy not found.
    Không tìm thấy chiến lược yêu cầu.
    """
    
    def __init__(self, strategy_name: str, available_strategies: List[str]):
        """
        Initialize strategy not found error.
        Khởi tạo lỗi không tìm thấy chiến lược.
        """
        message = f"Strategy '{strategy_name}' not found"
        details = {'available_strategies': available_strategies}
        suggestions = [
            f"Use one of: {', '.join(available_strategies)}",
            "Check strategy name spelling",
            "Review strategy documentation",
            "Use default strategy"
        ]
        super().__init__(message, strategy_name=strategy_name,
                        details=details, suggestions=suggestions)


class StrategyExecutionError(StrategyError):
    """
    Strategy execution failed.
    Thực thi chiến lược thất bại.
    """
    
    def __init__(self, strategy_name: str, reason: str, **kwargs):
        """
        Initialize strategy execution error.
        Khởi tạo lỗi thực thi chiến lược.
        """
        message = f"Strategy '{strategy_name}' execution failed: {reason}"
        suggestions = [
            "Check strategy parameters",
            "Verify GPU state",
            "Review strategy logs",
            "Try fallback strategy"
        ]
        super().__init__(message, strategy_name=strategy_name,
                        suggestions=suggestions, **kwargs)


# Monitoring Exceptions
class MonitoringError(GPUOptimizationError):
    """
    Monitoring and metrics collection error.
    Lỗi giám sát và thu thập metrics.
    """
    
    def __init__(self, message: str, **kwargs):
        """
        Initialize monitoring error.
        Khởi tạo lỗi giám sát.
        """
        super().__init__(message, error_code="MON_ERROR", **kwargs)


class MetricsCollectionError(MonitoringError):
    """
    Failed to collect metrics.
    Thất bại khi thu thập metrics.
    """
    
    def __init__(self, metric_name: str, reason: str):
        """
        Initialize metrics collection error.
        Khởi tạo lỗi thu thập metrics.
        """
        message = f"Failed to collect metric '{metric_name}': {reason}"
        details = {'metric': metric_name, 'reason': reason}
        suggestions = [
            "Check monitoring service status",
            "Verify metric configuration",
            "Check GPU accessibility",
            "Review collector logs"
        ]
        super().__init__(message, details=details, suggestions=suggestions)


# Coordination Exceptions
class CoordinationError(GPUOptimizationError):
    """
    Multi-process coordination error.
    Lỗi phối hợp đa tiến trình.
    """
    
    def __init__(self, message: str, **kwargs):
        """
        Initialize coordination error.
        Khởi tạo lỗi phối hợp.
        """
        super().__init__(message, error_code="COORD_ERROR", **kwargs)


class DeadlockError(CoordinationError):
    """
    Deadlock detected in coordination.
    Phát hiện deadlock trong phối hợp.
    """
    
    def __init__(self, resources: List[str], processes: List[int]):
        """
        Initialize deadlock error.
        Khởi tạo lỗi deadlock.
        """
        message = f"Deadlock detected involving {len(processes)} processes"
        details = {'resources': resources, 'processes': processes}
        suggestions = [
            "Release locked resources",
            "Restart affected processes",
            "Review locking order",
            "Implement timeout mechanisms"
        ]
        super().__init__(message, details=details, suggestions=suggestions)


class SynchronizationError(CoordinationError):
    """
    Process synchronization error.
    Lỗi đồng bộ tiến trình.
    """
    
    def __init__(self, process_id: int, operation: str):
        """
        Initialize synchronization error.
        Khởi tạo lỗi đồng bộ.
        """
        message = f"Synchronization failed for process {process_id} during {operation}"
        details = {'process_id': process_id, 'operation': operation}
        suggestions = [
            "Check process status",
            "Verify IPC mechanisms",
            "Review synchronization barriers",
            "Check for race conditions"
        ]
        super().__init__(message, details=details, suggestions=suggestions)


# Validation Exceptions (re-export from validators)
from .validators import ValidationError


# Timeout Exception
class TimeoutError(GPUOptimizationError):
    """
    Operation timeout error.
    Lỗi timeout thao tác.
    """
    
    def __init__(self, operation: str, timeout_seconds: float):
        """
        Initialize timeout error.
        Khởi tạo lỗi timeout.
        """
        message = f"Operation '{operation}' timed out after {timeout_seconds}s"
        details = {'operation': operation, 'timeout': timeout_seconds}
        suggestions = [
            "Increase timeout value",
            "Check for blocking operations",
            "Verify resource availability",
            "Review operation complexity"
        ]
        super().__init__(message, error_code="TIMEOUT_ERROR",
                        details=details, suggestions=suggestions)


# Resource Exceptions
class ResourceError(GPUOptimizationError):
    """
    Resource allocation or management error.
    Lỗi cấp phát hoặc quản lý tài nguyên.
    """
    
    def __init__(self, message: str, resource_type: Optional[str] = None, **kwargs):
        """
        Initialize resource error.
        Khởi tạo lỗi tài nguyên.
        """
        if resource_type:
            kwargs.setdefault('details', {})['resource_type'] = resource_type
        super().__init__(message, error_code="RESOURCE_ERROR", **kwargs)


class ResourceExhaustedError(ResourceError):
    """
    Resource exhausted or unavailable.
    Tài nguyên cạn kiệt hoặc không khả dụng.
    """
    
    def __init__(self, resource_type: str, requested: Any, available: Any):
        """
        Initialize resource exhausted error.
        Khởi tạo lỗi cạn kiệt tài nguyên.
        """
        message = f"Resource '{resource_type}' exhausted: requested {requested}, available {available}"
        details = {'requested': requested, 'available': available}
        suggestions = [
            "Wait for resources to be released",
            "Reduce resource requirements",
            "Scale up available resources",
            "Implement resource pooling"
        ]
        super().__init__(message, resource_type=resource_type,
                        details=details, suggestions=suggestions)


def handle_exception(exc: Exception, logger=None, reraise: bool = True) -> Optional[Dict[str, Any]]:
    """
    Central exception handler.
    Xử lý exception tập trung.
    
    Args:
        exc: Exception to handle
        logger: Optional logger instance
        reraise: Whether to reraise exception
        
    Returns:
        Exception details as dictionary
    """
    # Convert to dict if it's a GPU optimization error
    if isinstance(exc, GPUOptimizationError):
        error_dict = exc.to_dict()
    else:
        error_dict = {
            'error_type': type(exc).__name__,
            'message': str(exc),
            'traceback': traceback.format_exc()
        }
    
    # Log if logger provided
    if logger:
        logger.error(f"Exception handled: {error_dict}")
    
    # Reraise if requested
    if reraise:
        raise exc
    
    return error_dict
