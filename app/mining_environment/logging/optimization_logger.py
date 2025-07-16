"""
optimization_logger.py

Enhanced Logging Framework cho CPU Optimization và Cloaking Functions.
Cung cấp detailed logging với timestamps, thread IDs, performance metrics.

Author: Claude AI Audit Framework
Purpose: Comprehensive logging cho optimization và cloaking operations
"""

import os
import time
import threading
import logging
import traceback
import psutil
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
import json
import sys


class OptimizationLogger:
    """
    Enhanced Logger cho CPU Optimization và Cloaking Operations.
    Cung cấp detailed logging với performance metrics và debug support.
    """
    
    def __init__(self, name: str, log_dir: str = "/tmp/optimization_logs"):
        """
        Khởi tạo OptimizationLogger.
        
        Args:
            name: Logger name
            log_dir: Directory để lưu log files
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Lưu trữ **performance metrics** (chỉ số hiệu suất)
        self.performance_metrics: Dict[str, List[Dict[str, Any]]] = {}
        self.metrics_lock = threading.Lock()
        
        # Thiết lập **loggers** (trình ghi nhật ký)
        self._setup_loggers()
        
        # **Performance monitoring** (giám sát hiệu suất)
        self.start_time = time.time()
        self.call_count = 0
        
    def _setup_loggers(self):
        """
        Thiết lập các **logger levels** (mức độ ghi nhật ký) với **appropriate handlers** (trình xử lý phù hợp).
        """
        
        # **Main logger** (trình ghi nhật ký chính)
        self.logger = logging.getLogger(f"optimization.{self.name}")
        self.logger.setLevel(logging.DEBUG)
        
        # Xóa **existing handlers** (trình xử lý hiện có)
        self.logger.handlers.clear()
        
        # **Debug handler** (trình xử lý debug) - **detailed logs** (nhật ký chi tiết)
        debug_handler = logging.FileHandler(
            self.log_dir / f"{self.name}_debug.log",
            mode='a',
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d [%(levelname)s] [%(threadName)s:%(thread)d] '
            '[%(funcName)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        debug_handler.setFormatter(debug_formatter)
        self.logger.addHandler(debug_handler)
        
        # **Info handler** (trình xử lý info) - **operation logs** (nhật ký hoạt động)
        info_handler = logging.FileHandler(
            self.log_dir / f"{self.name}_operations.log",
            mode='a',
            encoding='utf-8'
        )
        info_handler.setLevel(logging.INFO)
        info_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        info_handler.setFormatter(info_formatter)
        self.logger.addHandler(info_handler)
        
        # **Error handler** (trình xử lý lỗi) - **error logs** (nhật ký lỗi)
        error_handler = logging.FileHandler(
            self.log_dir / f"{self.name}_errors.log",
            mode='a',
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(threadName)s:%(thread)d] '
            '[%(funcName)s:%(lineno)d] %(message)s\\n'
            'Stack Trace:\\n%(stack_trace)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        self.logger.addHandler(error_handler)
        
        # **Console handler** (trình xử lý console) cho **immediate feedback** (phản hồi ngay lập tức)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
    
    def log_function_entry(self, func_name: str, args: tuple = None, kwargs: dict = None):
        """
        **Log function entry** (ghi nhật ký vào hàm) với **parameters** (tham số).
        """
        thread_id = threading.current_thread().ident
        thread_name = threading.current_thread().name
        
        entry_msg = f"🔵 ENTRY: {func_name}"
        if args:
            entry_msg += f" | Args: {args}"
        if kwargs:
            entry_msg += f" | Kwargs: {kwargs}"
        
        self.logger.info(f"{entry_msg} | Thread: {thread_name}({thread_id})")
        
        # Lưu trữ **entry time** (thời gian vào) cho **performance calculation** (tính toán hiệu suất)
        entry_time = time.time()
        setattr(threading.current_thread(), f"{func_name}_entry_time", entry_time)
    
    def log_function_exit(self, func_name: str, result: Any = None, success: bool = True):
        """
        **Log function exit** (ghi nhật ký thoát hàm) với **result** (kết quả) và **execution time** (thời gian thực thi).
        """
        thread_id = threading.current_thread().ident
        thread_name = threading.current_thread().name
        
        # Calculate execution time
        entry_time = getattr(threading.current_thread(), f"{func_name}_entry_time", time.time())
        execution_time = time.time() - entry_time
        
        status = "✅ SUCCESS" if success else "❌ FAILED"
        exit_msg = f"🔴 EXIT: {func_name} | Status: {status} | Time: {execution_time:.3f}s"
        
        if result is not None:
            exit_msg += f" | Result: {result}"
        
        self.logger.info(f"{exit_msg} | Thread: {thread_name}({thread_id})")
        
        # Store performance metrics
        self._store_performance_metric(func_name, execution_time, success)
    
    def log_activation_status(self, component: str, status: str, details: Dict[str, Any] = None):
        """Log activation status của components."""
        status_indicator = {
            "ENABLED": "🟢 ENABLED",
            "DISABLED": "🔴 DISABLED", 
            "PARTIAL": "🟡 PARTIAL",
            "ERROR": "❌ ERROR"
        }.get(status, status)
        
        msg = f"🎯 ACTIVATION: {component} | Status: {status_indicator}"
        
        if details:
            msg += f" | Details: {json.dumps(details, indent=2)}"
        
        self.logger.info(msg)
        
        # Store activation metrics
        self._store_activation_metric(component, status, details)
    
    def log_performance_metrics(self, operation: str, metrics: Dict[str, Any]):
        """Log performance metrics cho operations."""
        metrics_msg = f"📊 PERFORMANCE: {operation}"
        
        formatted_metrics = []
        for key, value in metrics.items():
            if isinstance(value, float):
                formatted_metrics.append(f"{key}: {value:.3f}")
            else:
                formatted_metrics.append(f"{key}: {value}")
        
        metrics_msg += f" | {' | '.join(formatted_metrics)}"
        
        self.logger.info(metrics_msg)
        
        # Store detailed metrics
        self._store_performance_metric(operation, metrics.get('execution_time', 0), True, metrics)
    
    def log_error_with_context(self, func_name: str, error: Exception, context: Dict[str, Any] = None):
        """Log error với full context và stack trace."""
        thread_id = threading.current_thread().ident
        thread_name = threading.current_thread().name
        
        error_msg = f"❌ ERROR: {func_name} | Exception: {type(error).__name__}: {str(error)}"
        
        if context:
            error_msg += f" | Context: {json.dumps(context, indent=2)}"
        
        # Get stack trace
        stack_trace = traceback.format_exc()
        
        # Log with stack trace
        self.logger.error(error_msg, extra={'stack_trace': stack_trace})
        
        # Store error metrics
        self._store_error_metric(func_name, error, context)
    
    def log_cpu_metrics(self, pid: int, operation: str):
        """Log CPU metrics cho specific process."""
        try:
            process = psutil.Process(pid)
            cpu_percent = process.cpu_percent(interval=0.1)
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            cpu_affinity = process.cpu_affinity()
            
            cpu_metrics = {
                'pid': pid,
                'cpu_percent': cpu_percent,
                'memory_mb': memory_info.rss // 1024 // 1024,
                'memory_percent': memory_percent,
                'cpu_affinity': cpu_affinity,
                'threads': process.num_threads() if hasattr(process, 'num_threads') else 0
            }
            
            self.log_performance_metrics(f"CPU_METRICS_{operation}", cpu_metrics)
            
        except Exception as e:
            self.log_error_with_context("log_cpu_metrics", e, {"pid": pid, "operation": operation})
    
    def log_stealth_status(self, component: str, stealth_data: Dict[str, Any]):
        """Log stealth status và metrics."""
        stealth_msg = f"🛡️ STEALTH: {component}"
        
        # Format stealth data
        formatted_data = []
        for key, value in stealth_data.items():
            if key == 'cloaked_processes':
                formatted_data.append(f"processes: {len(value)}")
            elif key == 'threat_level':
                formatted_data.append(f"threat: {value}")
            elif isinstance(value, bool):
                formatted_data.append(f"{key}: {'✅' if value else '❌'}")
            else:
                formatted_data.append(f"{key}: {value}")
        
        stealth_msg += f" | {' | '.join(formatted_data)}"
        
        self.logger.info(stealth_msg)
        
        # Store stealth metrics
        self._store_stealth_metric(component, stealth_data)
    
    def _store_performance_metric(self, operation: str, execution_time: float, success: bool, extra_metrics: Dict[str, Any] = None):
        """Store performance metric trong internal storage."""
        with self.metrics_lock:
            if operation not in self.performance_metrics:
                self.performance_metrics[operation] = []
            
            metric = {
                'timestamp': datetime.now().isoformat(),
                'execution_time': execution_time,
                'success': success,
                'thread_id': threading.current_thread().ident,
                'thread_name': threading.current_thread().name
            }
            
            if extra_metrics:
                metric.update(extra_metrics)
            
            self.performance_metrics[operation].append(metric)
            
            # Keep only last 100 entries per operation
            if len(self.performance_metrics[operation]) > 100:
                self.performance_metrics[operation] = self.performance_metrics[operation][-100:]
    
    def _store_activation_metric(self, component: str, status: str, details: Dict[str, Any] = None):
        """Store activation metric."""
        metric_key = f"activation_{component}"
        metric_data = {
            'component': component,
            'status': status,
            'details': details or {}
        }
        self._store_performance_metric(metric_key, 0, status in ['ENABLED', 'PARTIAL'], metric_data)
    
    def _store_error_metric(self, func_name: str, error: Exception, context: Dict[str, Any] = None):
        """Store error metric."""
        metric_key = f"error_{func_name}"
        metric_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {}
        }
        self._store_performance_metric(metric_key, 0, False, metric_data)
    
    def _store_stealth_metric(self, component: str, stealth_data: Dict[str, Any]):
        """Store stealth metric."""
        metric_key = f"stealth_{component}"
        self._store_performance_metric(metric_key, 0, True, stealth_data)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary của all operations."""
        with self.metrics_lock:
            summary = {
                'total_operations': len(self.performance_metrics),
                'uptime_seconds': time.time() - self.start_time,
                'operations_summary': {}
            }
            
            for operation, metrics in self.performance_metrics.items():
                if metrics:
                    execution_times = [m['execution_time'] for m in metrics if 'execution_time' in m]
                    success_count = sum(1 for m in metrics if m.get('success', False))
                    
                    summary['operations_summary'][operation] = {
                        'total_calls': len(metrics),
                        'success_rate': success_count / len(metrics) if metrics else 0,
                        'avg_execution_time': sum(execution_times) / len(execution_times) if execution_times else 0,
                        'min_execution_time': min(execution_times) if execution_times else 0,
                        'max_execution_time': max(execution_times) if execution_times else 0
                    }
            
            return summary
    
    def export_metrics(self, output_path: Optional[str] = None):
        """Export metrics ra JSON file."""
        if output_path is None:
            output_path = self.log_dir / f"{self.name}_metrics.json"
        
        with self.metrics_lock:
            export_data = {
                'logger_name': self.name,
                'export_timestamp': datetime.now().isoformat(),
                'performance_summary': self.get_performance_summary(),
                'detailed_metrics': self.performance_metrics
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"📁 Metrics exported to: {output_path}")
    
    def setup_log_rotation(self, max_size_mb: int = 10, backup_count: int = 5):
        """Setup log rotation để tránh đầy disk."""
        from logging.handlers import RotatingFileHandler
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                self.logger.removeHandler(handler)
        
        # Add rotating handlers
        debug_handler = RotatingFileHandler(
            self.log_dir / f"{self.name}_debug.log",
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d [%(levelname)s] [%(threadName)s:%(thread)d] '
            '[%(funcName)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        debug_handler.setFormatter(debug_formatter)
        self.logger.addHandler(debug_handler)
        
        self.logger.info(f"🔄 Log rotation setup: max_size={max_size_mb}MB, backup_count={backup_count}")


def optimization_logger(logger_name: str = "default"):
    """
    Decorator để automatically log function entry/exit với performance metrics.
    
    Args:
        logger_name: Name của logger instance
    
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get or create logger
            if not hasattr(wrapper, '_logger'):
                wrapper._logger = OptimizationLogger(logger_name)
            
            logger = wrapper._logger
            func_name = func.__name__
            
            # Log function entry
            logger.log_function_entry(func_name, args, kwargs)
            
            start_time = time.time()
            result = None
            success = True
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Log CPU metrics if PID is available
                if 'pid' in kwargs:
                    logger.log_cpu_metrics(kwargs['pid'], func_name)
                elif args and isinstance(args[0], int):
                    logger.log_cpu_metrics(args[0], func_name)
                
                return result
                
            except Exception as e:
                success = False
                logger.log_error_with_context(func_name, e, {'args': args, 'kwargs': kwargs})
                raise
                
            finally:
                # Log function exit
                logger.log_function_exit(func_name, result, success)
                
                # Log performance metrics
                execution_time = time.time() - start_time
                logger.log_performance_metrics(func_name, {
                    'execution_time': execution_time,
                    'success': success
                })
        
        return wrapper
    return decorator


# Global logger instances
_logger_instances: Dict[str, OptimizationLogger] = {}
_logger_lock = threading.Lock()


def get_optimization_logger(name: str) -> OptimizationLogger:
    """
    Get or create OptimizationLogger instance.
    
    Args:
        name: Logger name
        
    Returns:
        OptimizationLogger instance
    """
    with _logger_lock:
        if name not in _logger_instances:
            _logger_instances[name] = OptimizationLogger(name)
        return _logger_instances[name]


def setup_global_logging(log_dir: str = "/tmp/optimization_logs"):
    """
    Setup global logging configuration cho all optimization components.
    
    Args:
        log_dir: Directory để lưu log files
    """
    # Create log directory
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Setup loggers cho major components
    components = [
        'cloaking_lib',
        'cpu_optimization', 
        'stealth_execution',
        'randomx_optimizer',
        'system_integration',
        'cloak_strategies'
    ]
    
    for component in components:
        logger = get_optimization_logger(component)
        logger.setup_log_rotation(max_size_mb=10, backup_count=5)
        logger.log_activation_status(component, "ENABLED", {"log_dir": log_dir})
    
    print(f"🔧 Global optimization logging setup complete: {log_dir}")


if __name__ == "__main__":
    # Test logging functionality
    setup_global_logging()
    
    # Test logger
    test_logger = get_optimization_logger("test")
    
    @optimization_logger("test")
    def test_function(x: int, y: int = 10) -> int:
        """Test function với logging."""
        if x < 0:
            raise ValueError("x must be positive")
        return x * y
    
    # Test normal execution
    result = test_function(5, y=20)
    print(f"Result: {result}")
    
    # Test error handling
    try:
        test_function(-1)
    except ValueError as e:
        print(f"Caught expected error: {e}")
    
    # Export metrics
    test_logger.export_metrics()
    
    # Show performance summary
    summary = test_logger.get_performance_summary()
    print(f"Performance summary: {json.dumps(summary, indent=2)}")