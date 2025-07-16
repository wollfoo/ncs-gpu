#!/usr/bin/env python3
"""
GPU Optimization và Cloaking Logger
Hệ thống ghi log chi tiết cho các chức năng GPU optimization và cloaking
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
import traceback
from pathlib import Path
import threading
import functools
from enum import Enum

class GPULogLevel(Enum):
    """
    GPU Log Levels (Mức độ log GPU)
    """
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class GPUFunctionStatus(Enum):
    """
    GPU Function Status (Trạng thái chức năng GPU)
    """
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    DISABLED = "DISABLED"
    STARTING = "STARTING"
    STOPPING = "STOPPING"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class GPULogger:
    """
    GPU Logger System (Hệ thống ghi log GPU)
    Ghi log chi tiết cho GPU optimization và cloaking functions
    """
    
    def __init__(self, logs_dir: str = "/app/mining_environment/logs"):
        """
        Khởi tạo GPU Logger
        
        Args:
            logs_dir: Thư mục lưu trữ logs
        """
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Tạo tên file log theo convention
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.optimization_log_file = self.logs_dir / f"gpu_optimization_{timestamp}.log"
        self.cloaking_log_file = self.logs_dir / f"gpu_cloaking_{timestamp}.log"
        
        # Setup loggers
        self._setup_loggers()
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Performance metrics storage
        self._performance_metrics: Dict[str, List[Dict]] = {}
        
        # Function call counter
        self._function_calls: Dict[str, int] = {}
        
        print(f"✅ GPU Logger initialized - Logs: {self.logs_dir}")

    def _setup_loggers(self):
        """
        Cấu hình logging system
        """
        # Optimization logger
        self.optimization_logger = logging.getLogger("gpu_optimization")
        self.optimization_logger.setLevel(logging.DEBUG)
        
        opt_handler = logging.FileHandler(self.optimization_log_file)
        opt_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        opt_handler.setFormatter(opt_formatter)
        self.optimization_logger.addHandler(opt_handler)
        
        # Cloaking logger
        self.cloaking_logger = logging.getLogger("gpu_cloaking")
        self.cloaking_logger.setLevel(logging.DEBUG)
        
        cloak_handler = logging.FileHandler(self.cloaking_log_file)
        cloak_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        cloak_handler.setFormatter(cloak_formatter)
        self.cloaking_logger.addHandler(cloak_handler)

    def log_gpu_optimization(self, 
                           function_name: str,
                           status: GPUFunctionStatus,
                           details: Optional[Dict[str, Any]] = None,
                           performance_metrics: Optional[Dict[str, Any]] = None,
                           error_details: Optional[str] = None,
                           gpu_index: Optional[int] = None):
        """
        Ghi log cho GPU optimization functions
        
        Args:
            function_name: Tên function (VD: "set_gpu_power_limit")
            status: Trạng thái thực thi (SUCCESS/FAILED/DISABLED)
            details: Chi tiết bổ sung
            performance_metrics: Thông số hiệu suất
            error_details: Chi tiết lỗi (nếu có)
            gpu_index: Index của GPU (nếu có)
        """
        with self._lock:
            timestamp = datetime.now().isoformat()
            
            # Tăng counter
            self._function_calls[function_name] = self._function_calls.get(function_name, 0) + 1
            
            log_entry = {
                "timestamp": timestamp,
                "function_name": function_name,
                "function_type": "optimization",
                "status": status.value,
                "gpu_index": gpu_index,
                "call_count": self._function_calls[function_name],
                "details": details or {},
                "performance_metrics": performance_metrics or {},
                "error_details": error_details,
                "thread_id": threading.current_thread().ident
            }
            
            # Lưu performance metrics
            if performance_metrics:
                if function_name not in self._performance_metrics:
                    self._performance_metrics[function_name] = []
                self._performance_metrics[function_name].append({
                    "timestamp": timestamp,
                    "metrics": performance_metrics
                })
            
            # Ghi log text với standard format
            log_level = logging.ERROR if status == GPUFunctionStatus.FAILED else logging.INFO
            log_message = f"GPU_OPTIMIZATION: {function_name} - {status.value} - {execution_time:.4f}s"
            if error_details:
                log_message += f" - Error: {error_details}"
            self.optimization_logger.log(log_level, log_message)
            
            # Console output
            status_emoji = "✅" if status == GPUFunctionStatus.SUCCESS else "❌" if status == GPUFunctionStatus.FAILED else "⚠️"
            print(f"{status_emoji} GPU_OPT: {function_name} - {status.value} (GPU {gpu_index})")

    def log_gpu_cloaking(self, 
                        function_name: str,
                        status: GPUFunctionStatus,
                        strategies: Optional[List[str]] = None,
                        fake_metrics: Optional[Dict[str, Any]] = None,
                        detection_status: Optional[str] = None,
                        error_details: Optional[str] = None,
                        target_pid: Optional[int] = None):
        """
        Ghi log cho GPU cloaking functions
        
        Args:
            function_name: Tên function (VD: "enable_nvml_cloaking")
            status: Trạng thái thực thi
            strategies: Danh sách strategies đang active
            fake_metrics: Fake metrics đang sử dụng
            detection_status: Trạng thái detection
            error_details: Chi tiết lỗi
            target_pid: PID của process target
        """
        with self._lock:
            timestamp = datetime.now().isoformat()
            
            # Tăng counter
            self._function_calls[function_name] = self._function_calls.get(function_name, 0) + 1
            
            log_entry = {
                "timestamp": timestamp,
                "function_name": function_name,
                "function_type": "cloaking",
                "status": status.value,
                "target_pid": target_pid,
                "call_count": self._function_calls[function_name],
                "active_strategies": strategies or [],
                "fake_metrics": fake_metrics or {},
                "detection_status": detection_status,
                "error_details": error_details,
                "thread_id": threading.current_thread().ident
            }
            
            # Ghi log text với standard format
            log_level = logging.ERROR if status == GPUFunctionStatus.FAILED else logging.INFO
            log_message = f"GPU_CLOAKING: {strategy_name} - {action} - {status.value} - {execution_time:.4f}s"
            if error_details:
                log_message += f" - Error: {error_details}"
            self.cloaking_logger.log(log_level, log_message)
            
            # Console output
            status_emoji = "🎭" if status == GPUFunctionStatus.SUCCESS else "❌" if status == GPUFunctionStatus.FAILED else "⚠️"
            print(f"{status_emoji} GPU_CLOAK: {function_name} - {status.value} (PID {target_pid})")

    def log_function_decorator(self, function_type: str = "optimization"):
        """
        Decorator để tự động log function calls
        
        Args:
            function_type: Loại function ("optimization" hoặc "cloaking")
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                function_name = f"{func.__module__}.{func.__name__}"
                start_time = time.time()
                
                try:
                    # Log function start
                    if function_type == "optimization":
                        self.log_gpu_optimization(
                            function_name=function_name,
                            status=GPUFunctionStatus.STARTING,
                            details={"args": str(args), "kwargs": str(kwargs)}
                        )
                    else:
                        self.log_gpu_cloaking(
                            function_name=function_name,
                            status=GPUFunctionStatus.STARTING
                        )
                    
                    # Execute function
                    result = func(*args, **kwargs)
                    
                    # Calculate performance metrics
                    execution_time = time.time() - start_time
                    performance_metrics = {
                        "execution_time_seconds": execution_time,
                        "execution_time_ms": execution_time * 1000,
                        "memory_usage_mb": self._get_memory_usage()
                    }
                    
                    # Log function success
                    if function_type == "optimization":
                        self.log_gpu_optimization(
                            function_name=function_name,
                            status=GPUFunctionStatus.SUCCESS,
                            details={"result": str(result)},
                            performance_metrics=performance_metrics
                        )
                    else:
                        self.log_gpu_cloaking(
                            function_name=function_name,
                            status=GPUFunctionStatus.SUCCESS,
                            detection_status="ACTIVE"
                        )
                    
                    return result
                    
                except Exception as e:
                    # Log function failure
                    error_details = f"{str(e)}\n{traceback.format_exc()}"
                    
                    if function_type == "optimization":
                        self.log_gpu_optimization(
                            function_name=function_name,
                            status=GPUFunctionStatus.FAILED,
                            error_details=error_details
                        )
                    else:
                        self.log_gpu_cloaking(
                            function_name=function_name,
                            status=GPUFunctionStatus.FAILED,
                            error_details=error_details
                        )
                    
                    raise
                    
            return wrapper
        return decorator

    def _get_memory_usage(self) -> float:
        """
        Lấy memory usage hiện tại (MB)
        """
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0

    def generate_summary_report(self) -> Dict[str, Any]:
        """
        Tạo báo cáo tổng kết
        """
        with self._lock:
            timestamp = datetime.now().isoformat()
            
            summary = {
                "report_timestamp": timestamp,
                "total_function_calls": sum(self._function_calls.values()),
                "function_call_breakdown": self._function_calls.copy(),
                "performance_summary": {},
                "log_files": {
                    "optimization_log": str(self.optimization_log_file),
                    "cloaking_log": str(self.cloaking_log_file)
                }
            }
            
            # Performance summary
            for func_name, metrics_list in self._performance_metrics.items():
                if metrics_list:
                    execution_times = [m["metrics"].get("execution_time_ms", 0) for m in metrics_list]
                    summary["performance_summary"][func_name] = {
                        "total_calls": len(metrics_list),
                        "avg_execution_time_ms": sum(execution_times) / len(execution_times) if execution_times else 0,
                        "min_execution_time_ms": min(execution_times) if execution_times else 0,
                        "max_execution_time_ms": max(execution_times) if execution_times else 0
                    }
            
            return summary

    def save_summary_report(self) -> str:
        """
        Lưu báo cáo tổng kết
        """
        summary = self.generate_summary_report()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.logs_dir / f"gpu_logging_summary_{timestamp}.log"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"GPU Logging Summary Report - Generated at: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Total Optimization Calls: {summary.get('total_optimization_calls', 0)}\n")
            f.write(f"Total Cloaking Calls: {summary.get('total_cloaking_calls', 0)}\n")
            f.write(f"Success Rate: {summary.get('success_rate', 0):.2%}\n")
            f.write(f"Average Execution Time: {summary.get('avg_execution_time', 0):.4f}s\n")
        
        print(f"📊 Summary report saved: {report_file}")
        return str(report_file)

# Global logger instance
_gpu_logger_instance = None

def get_gpu_logger(logs_dir: str = "/app/mining_environment/logs") -> GPULogger:
    """
    Lấy GPU Logger instance (Singleton pattern)
    """
    global _gpu_logger_instance
    if _gpu_logger_instance is None:
        _gpu_logger_instance = GPULogger(logs_dir)
    return _gpu_logger_instance

# Convenience functions
def log_optimization(function_name: str, status: GPUFunctionStatus, **kwargs):
    """
    Convenience function để log GPU optimization
    """
    logger = get_gpu_logger()
    logger.log_gpu_optimization(function_name, status, **kwargs)

def log_cloaking(function_name: str, status: GPUFunctionStatus, **kwargs):
    """
    Convenience function để log GPU cloaking
    """
    logger = get_gpu_logger()
    logger.log_gpu_cloaking(function_name, status, **kwargs)

def optimization_logger_decorator(func):
    """
    Decorator cho GPU optimization functions
    """
    logger = get_gpu_logger()
    return logger.log_function_decorator("optimization")(func)

def cloaking_logger_decorator(func):
    """
    Decorator cho GPU cloaking functions
    """
    logger = get_gpu_logger()
    return logger.log_function_decorator("cloaking")(func)

if __name__ == "__main__":
    # Test logging system
    print("🧪 Testing GPU Logger System...")
    
    logger = get_gpu_logger()
    
    # Test optimization logging
    logger.log_gpu_optimization(
        function_name="set_gpu_power_limit",
        status=GPUFunctionStatus.SUCCESS,
        details={"power_limit": 250, "unit": "watts"},
        performance_metrics={"execution_time_ms": 15.5, "memory_usage_mb": 45.2},
        gpu_index=0
    )
    
    # Test cloaking logging
    logger.log_gpu_cloaking(
        function_name="enable_nvml_cloaking",
        status=GPUFunctionStatus.SUCCESS,
        strategies=["fake_utilization", "fake_memory"],
        fake_metrics={"fake_utilization": 25, "fake_memory": 2048},
        detection_status="ACTIVE",
        target_pid=1234
    )
    
    # Test failed operation
    logger.log_gpu_optimization(
        function_name="set_gpu_clocks",
        status=GPUFunctionStatus.FAILED,
        error_details="NVML error: Insufficient permissions",
        gpu_index=1
    )
    
    # Generate summary report
    report_file = logger.save_summary_report()
    print(f"✅ Test completed - Report: {report_file}")