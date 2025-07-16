"""
GPU Optimization Logger - Detailed Logging System for GPU Optimization Functions
Hệ thống ghi log chi tiết cho các chức năng tối ưu GPU
"""
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from functools import wraps

# LOGS_DIR configuration - thư mục lưu trữ logs
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
os.makedirs(LOGS_DIR, exist_ok=True)

class GPUOptimizationLogger:
    """
    GPU Optimization Logger - Ghi log chi tiết cho các chức năng tối ưu GPU
    
    Features:
    - Function activation status tracking (SUCCESS/FAILED/DISABLED)
    - Error details logging (chi tiết lỗi)
    - Performance metrics (thời gian thực thi, memory usage)
    - Timestamp logging (dấu thời gian chính xác)
    - JSON structured logging format
    """
    
    def __init__(self, log_dir: str = LOGS_DIR):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Thread-safe logging
        self._lock = threading.Lock()
        
        # Performance metrics storage
        self.performance_metrics: Dict[str, List[Dict[str, Any]]] = {}
        
        # Setup logger
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Thiết lập logger với format JSON"""
        logger = logging.getLogger('gpu_optimization_logger')
        logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create file handler với timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.log_dir / f'gpu_optimization_{timestamp}.log'
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # JSON formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        
        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def log_function_call(self, 
                         function_name: str, 
                         status: str,
                         execution_time: float = 0.0,
                         memory_usage: Optional[float] = None,
                         parameters: Optional[Dict[str, Any]] = None,
                         error_details: Optional[str] = None,
                         additional_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log GPU optimization function call details
        
        Args:
            function_name: Tên chức năng GPU được gọi
            status: SUCCESS/FAILED/DISABLED
            execution_time: Thời gian thực thi (seconds)
            memory_usage: Memory usage (MB)
            parameters: Các tham số đầu vào
            error_details: Chi tiết lỗi (nếu có)
            additional_data: Dữ liệu bổ sung
        """
        with self._lock:
            timestamp = datetime.now().isoformat()
            
            log_entry = {
                'timestamp': timestamp,
                'function_name': function_name,
                'status': status,
                'execution_time_seconds': execution_time,
                'memory_usage_mb': memory_usage,
                'parameters': parameters or {},
                'error_details': error_details,
                'additional_data': additional_data or {}
            }
            
            # Store performance metrics
            if function_name not in self.performance_metrics:
                self.performance_metrics[function_name] = []
            
            self.performance_metrics[function_name].append({
                'timestamp': timestamp,
                'execution_time': execution_time,
                'memory_usage': memory_usage,
                'status': status
            })
            
            # Log to file với standard format
            self.logger.info(f"GPU_OPTIMIZATION: {function_name} - {status} - {execution_time:.4f}s")
            
    def log_plugin_lifecycle(self, 
                           plugin_name: str,
                           lifecycle_event: str,
                           status: str,
                           details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log GPU plugin lifecycle events
        
        Args:
            plugin_name: Tên plugin GPU
            lifecycle_event: INITIALIZE/START/STOP/DESTROY
            status: SUCCESS/FAILED
            details: Chi tiết bổ sung
        """
        self.log_function_call(
            function_name=f"plugin_{plugin_name}_{lifecycle_event.lower()}",
            status=status,
            additional_data={
                'plugin_name': plugin_name,
                'lifecycle_event': lifecycle_event,
                'details': details or {}
            }
        )
    
    def log_performance_metrics(self, 
                              function_name: str,
                              metrics: Dict[str, Any]) -> None:
        """
        Log performance metrics for GPU optimization functions
        
        Args:
            function_name: Tên chức năng
            metrics: Performance metrics dictionary
        """
        self.log_function_call(
            function_name=f"{function_name}_performance",
            status="SUCCESS",
            additional_data={
                'metrics_type': 'performance',
                'metrics': metrics
            }
        )
    
    def get_performance_summary(self, function_name: str) -> Dict[str, Any]:
        """
        Lấy tổng kết performance cho một function
        
        Args:
            function_name: Tên function
            
        Returns:
            Dict chứa performance summary
        """
        if function_name not in self.performance_metrics:
            return {}
        
        metrics = self.performance_metrics[function_name]
        if not metrics:
            return {}
        
        # Calculate statistics
        execution_times = [m['execution_time'] for m in metrics if m['execution_time'] > 0]
        memory_usages = [m['memory_usage'] for m in metrics if m['memory_usage'] is not None]
        
        success_count = sum(1 for m in metrics if m['status'] == 'SUCCESS')
        failed_count = sum(1 for m in metrics if m['status'] == 'FAILED')
        
        summary = {
            'function_name': function_name,
            'total_calls': len(metrics),
            'success_count': success_count,
            'failed_count': failed_count,
            'success_rate': success_count / len(metrics) if metrics else 0,
            'first_call': metrics[0]['timestamp'],
            'last_call': metrics[-1]['timestamp']
        }
        
        if execution_times:
            summary.update({
                'avg_execution_time': sum(execution_times) / len(execution_times),
                'min_execution_time': min(execution_times),
                'max_execution_time': max(execution_times)
            })
        
        if memory_usages:
            summary.update({
                'avg_memory_usage': sum(memory_usages) / len(memory_usages),
                'min_memory_usage': min(memory_usages),
                'max_memory_usage': max(memory_usages)
            })
            
        return summary
    
    def export_performance_report(self, output_file: Optional[str] = None) -> str:
        """
        Export performance report to standard log format
        
        Args:
            output_file: Output file path (optional)
            
        Returns:
            Path to exported file
        """
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = str(self.log_dir / f'gpu_optimization_report_{timestamp}.log')
        
        # Write report to standard log format
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"GPU Optimization Performance Report - Generated at: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            
            for function_name in self.performance_metrics:
                summary = self.get_performance_summary(function_name)
                f.write(f"Function: {function_name}\n")
                f.write(f"  Total Calls: {summary.get('total_calls', 0)}\n")
                f.write(f"  Success Rate: {summary.get('success_rate', 0):.2%}\n")
                if 'avg_execution_time' in summary:
                    f.write(f"  Avg Execution Time: {summary['avg_execution_time']:.4f}s\n")
                f.write("\n")
        
        self.logger.info(f"Performance report exported to: {output_file}")
        return output_file

# Global logger instance
gpu_opt_logger = GPUOptimizationLogger()

def log_gpu_optimization(status: str = "SUCCESS", 
                        measure_performance: bool = True,
                        capture_memory: bool = True):
    """
    Decorator cho GPU optimization functions logging
    
    Args:
        status: Default status (SUCCESS/FAILED/DISABLED)
        measure_performance: Có đo performance không
        capture_memory: Có capture memory usage không
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            function_name = f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            # Memory tracking (if available)
            memory_before = None
            if capture_memory:
                try:
                    import psutil
                    process = psutil.Process()
                    memory_before = process.memory_info().rss / 1024 / 1024  # MB
                except ImportError:
                    pass
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Calculate execution time
                execution_time = time.time() - start_time
                
                # Memory usage
                memory_usage = None
                if capture_memory and memory_before is not None:
                    try:
                        import psutil
                        process = psutil.Process()
                        memory_after = process.memory_info().rss / 1024 / 1024  # MB
                        memory_usage = memory_after - memory_before
                    except ImportError:
                        pass
                
                # Log successful execution
                gpu_opt_logger.log_function_call(
                    function_name=function_name,
                    status="SUCCESS",
                    execution_time=execution_time,
                    memory_usage=memory_usage,
                    parameters={
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys()) if kwargs else []
                    }
                )
                
                return result
                
            except Exception as e:
                # Calculate execution time even for failures
                execution_time = time.time() - start_time
                
                # Log failed execution
                gpu_opt_logger.log_function_call(
                    function_name=function_name,
                    status="FAILED",
                    execution_time=execution_time,
                    error_details=str(e),
                    parameters={
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys()) if kwargs else []
                    }
                )
                
                # Re-raise exception
                raise
                
        return wrapper
    return decorator

# Utility functions
def log_gpu_event(event_type: str, 
                 event_name: str, 
                 status: str, 
                 details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log GPU-related events
    
    Args:
        event_type: Type of event (OPTIMIZATION/CLOAKING/TELEMETRY)
        event_name: Name of the event
        status: SUCCESS/FAILED/DISABLED
        details: Additional details
    """
    gpu_opt_logger.log_function_call(
        function_name=f"gpu_event_{event_type.lower()}_{event_name}",
        status=status,
        additional_data={
            'event_type': event_type,
            'event_name': event_name,
            'details': details or {}
        }
    )