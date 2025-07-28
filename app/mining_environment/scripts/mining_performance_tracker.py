# mining_performance_tracker.py

"""
**Mining Performance Tracker** (Trình theo dõi hiệu suất khai thác)

Cung cấp **performance tracking** (theo dõi hiệu suất), **metrics collection** (thu thập chỉ số), 
và **reporting capabilities** (khả năng báo cáo) cho **mining operations** (hoạt động khai thác).
"""

import os
import time
import threading
import json
import psutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from mining_environment.scripts.logging_config import setup_logging

# **Performance tracking storage** (lưu trữ theo dõi hiệu suất)
_mining_processes = {}
_hash_rate_data = {}
_resource_usage_data = {}
_mining_operations = {}
_metrics_lock = threading.Lock()

# **Logger setup** (thiết lập logger)
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
performance_logger = setup_logging('mining_performance_tracker', str(Path(LOGS_DIR) / 'mining_performance_tracker.log'), 'INFO')

def register_mining_process(process_name: str, pid: int, process_obj: Any) -> None:
    """
    **Register mining process** (đăng ký tiến trình khai thác) cho **performance tracking** (theo dõi hiệu suất).
    
    Args:
        process_name (str): **Process name** (tên tiến trình)
        pid (int): **Process ID** (ID tiến trình) 
        process_obj (Any): **Process object** (đối tượng tiến trình)
    """
    with _metrics_lock:
        _mining_processes[process_name] = {
            'pid': pid,
            'process_obj': process_obj,
            'start_time': time.time(),
            'status': 'running'
        }
        performance_logger.info(f"📊 Registered mining process: {process_name} (PID: {pid})")

def log_hash_rate(process_name: str, hash_rate: float) -> None:
    """
    **Log hash rate** (ghi nhật ký tốc độ băm) cho **process** (tiến trình).
    
    Args:
        process_name (str): **Process name** (tên tiến trình)
        hash_rate (float): **Hash rate in H/s** (tốc độ băm tính bằng hash/giây)
    """
    with _metrics_lock:
        if process_name not in _hash_rate_data:
            _hash_rate_data[process_name] = []
        
        _hash_rate_data[process_name].append({
            'timestamp': time.time(),
            'hash_rate': hash_rate
        })
        
        # **Keep only last 100 entries** (chỉ giữ 100 mục cuối cùng) để tránh **memory overflow** (tràn bộ nhớ)
        if len(_hash_rate_data[process_name]) > 100:
            _hash_rate_data[process_name] = _hash_rate_data[process_name][-100:]
        
        performance_logger.debug(f"📈 Hash rate logged: {process_name} = {hash_rate:.2f} H/s")

def log_resource_usage(process_name: str, force_gpu_check: bool = False) -> None:
    """
    **Log resource usage** (ghi nhật ký sử dụng tài nguyên) cho **process** (tiến trình).
    
    Args:
        process_name (str): **Process name** (tên tiến trình)
        force_gpu_check (bool): **Force GPU usage check** (buộc kiểm tra sử dụng GPU)
    """
    try:
        with _metrics_lock:
            if process_name not in _mining_processes:
                performance_logger.warning(f"⚠️ Process {process_name} not registered for resource tracking")
                return
            
            process_info = _mining_processes[process_name]
            pid = process_info['pid']
            
            try:
                # **System resource usage** (sử dụng tài nguyên hệ thống)
                proc = psutil.Process(pid)
                cpu_percent = proc.cpu_percent()
                memory_info = proc.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                
                resource_data = {
                    'timestamp': time.time(),
                    'cpu_percent': cpu_percent,
                    'memory_mb': memory_mb,
                    'process_status': proc.status()
                }
                
                if process_name not in _resource_usage_data:
                    _resource_usage_data[process_name] = []
                
                _resource_usage_data[process_name].append(resource_data)
                
                # **Keep only last 50 entries** (chỉ giữ 50 mục cuối cùng)
                if len(_resource_usage_data[process_name]) > 50:
                    _resource_usage_data[process_name] = _resource_usage_data[process_name][-50:]
                
                performance_logger.debug(f"📊 Resource usage logged: {process_name} - CPU: {cpu_percent:.1f}%, Memory: {memory_mb:.1f}MB")
                
            except psutil.NoSuchProcess:
                performance_logger.warning(f"⚠️ Process {process_name} (PID: {pid}) no longer exists")
                process_info['status'] = 'terminated'
            except psutil.AccessDenied:
                performance_logger.warning(f"⚠️ Access denied for process {process_name} (PID: {pid})")
            except Exception as e:
                performance_logger.error(f"❌ Error logging resource usage for {process_name}: {e}")
    
    except Exception as e:
        performance_logger.error(f"❌ Unexpected error in log_resource_usage: {e}")

def log_mining_operation(process_name: str, operation: str, pid: int, details: Dict[str, Any], duration: float, status: str) -> None:
    """
    **Log mining operation** (ghi nhật ký hoạt động khai thác).
    
    Args:
        process_name (str): **Process name** (tên tiến trình)
        operation (str): **Operation type** (loại hoạt động)
        pid (int): **Process ID** (ID tiến trình)
        details (Dict[str, Any]): **Operation details** (chi tiết hoạt động)
        duration (float): **Operation duration** (thời gian hoạt động)
        status (str): **Operation status** (trạng thái hoạt động)
    """
    with _metrics_lock:
        if process_name not in _mining_operations:
            _mining_operations[process_name] = []
        
        operation_data = {
            'timestamp': time.time(),
            'operation': operation,
            'pid': pid,
            'details': details,
            'duration': duration,
            'status': status
        }
        
        _mining_operations[process_name].append(operation_data)
        
        # **Keep only last 50 operations** (chỉ giữ 50 hoạt động cuối cùng)
        if len(_mining_operations[process_name]) > 50:
            _mining_operations[process_name] = _mining_operations[process_name][-50:]
        
        performance_logger.info(f"🎯 Mining operation logged: {process_name} - {operation} ({status}) - Duration: {duration:.2f}s")

def get_real_time_metrics() -> Dict[str, Dict[str, Any]]:
    """
    **Get real-time metrics** (lấy chỉ số thời gian thực) cho tất cả **mining processes** (tiến trình khai thác).
    
    Returns:
        Dict[str, Dict[str, Any]]: **Real-time metrics data** (dữ liệu chỉ số thời gian thực)
    """
    with _metrics_lock:
        metrics = {}
        
        for process_name in _mining_processes:
            process_metrics = {}
            
            # **Current hash rate** (tốc độ băm hiện tại)
            if process_name in _hash_rate_data and _hash_rate_data[process_name]:
                latest_hash = _hash_rate_data[process_name][-1]
                process_metrics['current_hash_rate'] = latest_hash['hash_rate']
                process_metrics['hash_rate_timestamp'] = latest_hash['timestamp']
                
                # **Average hash rate** (tốc độ băm trung bình) (last 10 samples)
                recent_samples = _hash_rate_data[process_name][-10:]
                avg_hash_rate = sum(sample['hash_rate'] for sample in recent_samples) / len(recent_samples)
                process_metrics['average_hash_rate'] = avg_hash_rate
            else:
                process_metrics['current_hash_rate'] = 0
                process_metrics['average_hash_rate'] = 0
            
            # **Current resource usage** (sử dụng tài nguyên hiện tại)
            if process_name in _resource_usage_data and _resource_usage_data[process_name]:
                latest_resource = _resource_usage_data[process_name][-1]
                process_metrics['cpu_percent'] = latest_resource['cpu_percent']
                process_metrics['memory_mb'] = latest_resource['memory_mb']
                process_metrics['process_status'] = latest_resource['process_status']
            else:
                process_metrics['cpu_percent'] = 0
                process_metrics['memory_mb'] = 0
                process_metrics['process_status'] = 'unknown'
            
            # **Process info** (thông tin tiến trình)
            if process_name in _mining_processes:
                process_info = _mining_processes[process_name]
                process_metrics['pid'] = process_info['pid']
                process_metrics['uptime'] = time.time() - process_info['start_time']
                process_metrics['status'] = process_info['status']
            
            metrics[process_name] = process_metrics
        
        return metrics

def generate_performance_comparison() -> str:
    """
    **Generate performance comparison report** (tạo báo cáo so sánh hiệu suất).
    
    Returns:
        str: **Performance comparison report** (báo cáo so sánh hiệu suất)
    """
    with _metrics_lock:
        report_lines = []
        report_lines.append("=== MINING PERFORMANCE COMPARISON REPORT ===")
        report_lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        for process_name in _mining_processes:
            report_lines.append(f"Process: {process_name}")
            report_lines.append("-" * 40)
            
            # **Process info** (thông tin tiến trình)
            process_info = _mining_processes[process_name]
            uptime = time.time() - process_info['start_time']
            report_lines.append(f"  PID: {process_info['pid']}")
            report_lines.append(f"  Status: {process_info['status']}")
            report_lines.append(f"  Uptime: {uptime:.0f} seconds ({uptime/3600:.1f} hours)")
            
            # **Hash rate statistics** (thống kê tốc độ băm)
            if process_name in _hash_rate_data and _hash_rate_data[process_name]:
                hash_rates = [sample['hash_rate'] for sample in _hash_rate_data[process_name]]
                report_lines.append(f"  Hash Rate Samples: {len(hash_rates)}")
                report_lines.append(f"  Current Hash Rate: {hash_rates[-1]:.2f} H/s")
                report_lines.append(f"  Average Hash Rate: {sum(hash_rates)/len(hash_rates):.2f} H/s")
                report_lines.append(f"  Max Hash Rate: {max(hash_rates):.2f} H/s")
                report_lines.append(f"  Min Hash Rate: {min(hash_rates):.2f} H/s")
            else:
                report_lines.append("  Hash Rate: No data available")
            
            # **Resource usage statistics** (thống kê sử dụng tài nguyên)
            if process_name in _resource_usage_data and _resource_usage_data[process_name]:
                cpu_usage = [sample['cpu_percent'] for sample in _resource_usage_data[process_name]]
                memory_usage = [sample['memory_mb'] for sample in _resource_usage_data[process_name]]
                report_lines.append(f"  Average CPU Usage: {sum(cpu_usage)/len(cpu_usage):.1f}%")
                report_lines.append(f"  Average Memory Usage: {sum(memory_usage)/len(memory_usage):.1f} MB")
                report_lines.append(f"  Max Memory Usage: {max(memory_usage):.1f} MB")
            else:
                report_lines.append("  Resource Usage: No data available")
            
            # **Operations count** (số lượng hoạt động)
            if process_name in _mining_operations:
                operations = _mining_operations[process_name]
                successful_ops = sum(1 for op in operations if op['status'] == 'SUCCESS')
                failed_ops = len(operations) - successful_ops
                report_lines.append(f"  Total Operations: {len(operations)}")
                report_lines.append(f"  Successful Operations: {successful_ops}")
                report_lines.append(f"  Failed Operations: {failed_ops}")
            
            report_lines.append("")
        
        report_lines.append("=== END PERFORMANCE REPORT ===")
        
        return "\n".join(report_lines)

class MiningPerformanceLogger:
    """
    **Mining Performance Logger Class** (lớp logger hiệu suất khai thác) với **additional functionality** (chức năng bổ sung).
    """
    
    def __init__(self):
        self.logger = performance_logger
        self.start_time = time.time()
    
    def monitor_process_logs(self, process_name: str, log_file_path: str) -> None:
        """
        **Monitor process logs** (giám sát log tiến trình) cho **performance tracking** (theo dõi hiệu suất).
        
        Args:
            process_name (str): **Process name** (tên tiến trình)
            log_file_path (str): **Log file path** (đường dẫn tệp log)
        """
        self.logger.info(f"🔍 Started monitoring logs for {process_name}: {log_file_path}")
    
    def export_performance_report(self) -> str:
        """
        **Export performance report** (xuất báo cáo hiệu suất) to file.
        
        Returns:
            str: **Report file path** (đường dẫn tệp báo cáo)
        """
        try:
            report_content = generate_performance_comparison()
            report_file = Path(LOGS_DIR) / f"mining_performance_report_{int(time.time())}.txt"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            self.logger.info(f"📄 Performance report exported to: {report_file}")
            return str(report_file)
            
        except Exception as e:
            self.logger.error(f"❌ Error exporting performance report: {e}")
            return ""

# **Global instance** (thể hiện toàn cầu)
mining_perf_logger = MiningPerformanceLogger()

# **Export functions for compatibility** (xuất hàm để tương thích)
__all__ = [
    'register_mining_process',
    'log_hash_rate', 
    'log_resource_usage',
    'log_mining_operation',
    'get_real_time_metrics',
    'generate_performance_comparison',
    'mining_perf_logger'
]