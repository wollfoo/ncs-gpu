"""
**[GPU Resource Manager Monitor] (bộ giám sát trình quản lý tài nguyên GPU)**
[Comprehensive monitoring] (giám sát toàn diện) và [health checking] (kiểm tra sức khỏe) cho [GPUResourceManager] (trình quản lý GPU)
"""

import os
import time
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

# ✅ [UNIFIED LOGGING] (hệ thống ghi log thống nhất): Sử dụng [centralized logging system] (hệ thống ghi log tập trung)
from .module_loggers import get_gpu_monitoring_logger

@dataclass
class GPUHealthMetrics:
    """**[GPU Health Metrics Data Class] (lớp dữ liệu chỉ số sức khỏe GPU)**"""
    timestamp: float
    gpu_count: int
    nvml_initialized: bool
    manager_active: bool
    processes_cloaked: int
    memory_usage_mb: float
    temperature_celsius: int
    power_usage_watts: float
    utilization_percent: int
    cloaking_success_rate: float
    last_error: Optional[str] = None

@dataclass 
class GPUManagerStatus:
    """**[GPU Manager Status Data Class] (lớp dữ liệu trạng thái quản lý GPU)**"""
    manager_type: str
    is_active: bool
    initialization_time: float
    last_health_check: float
    total_operations: int
    successful_operations: int
    failed_operations: int
    average_response_time_ms: float
    current_load: int
    status_details: Dict[str, Any]

class GPUResourceManagerMonitor:
    """
    **[Comprehensive GPU Resource Manager Monitor] (giám sát quản lý tài nguyên GPU toàn diện)**
    
    Chức năng:
    - **[Real-time monitoring] (giám sát thời gian thực)** của [GPUResourceManager] (trình quản lý GPU)
    - **[Health checks] (kiểm tra sức khỏe)** định kỳ
    - **[Performance metrics] (chỉ số hiệu năng)** [collection] (thu thập)
    - **[Dashboard data] (dữ liệu bảng điều khiển)** [generation] (tạo dữ liệu)
    """
    
    def __init__(self, gpu_manager=None, config: Dict[str, Any] = None):
        """
        Khởi tạo [GPU Resource Manager Monitor] (bộ giám sát trình quản lý tài nguyên GPU)
        
        Args:
            gpu_manager: Instance của [GPUResourceManager] (trình quản lý GPU)
            config: [Configuration] (cấu hình) cho [monitoring] (giám sát)
        """
        self.logger = get_gpu_monitoring_logger()
        self.gpu_manager = gpu_manager
        self.config = config or {}
        
        # ✅ MONITORING STATE: Trạng thái giám sát
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.health_history: List[GPUHealthMetrics] = []
        self.manager_status = GPUManagerStatus(
            manager_type="GPUResourceManager",
            is_active=False,
            initialization_time=time.time(),
            last_health_check=0,
            total_operations=0,
            successful_operations=0,
            failed_operations=0,
            average_response_time_ms=0.0,
            current_load=0,
            status_details={}
        )
        
        # ✅ CONFIGURATION: Cấu hình monitoring
        self.health_check_interval = self.config.get('health_check_interval_seconds', 30)
        self.history_retention_hours = self.config.get('history_retention_hours', 24)
        self.max_history_records = self.config.get('max_history_records', 1000)
        
        # ✅ PERFORMANCE TRACKING: Theo dõi hiệu năng
        self.operation_times: List[float] = []
        self.cloaked_processes: Dict[int, Dict[str, Any]] = {}
        
        self.logger.info("🎮 [GPU MONITOR] Khởi tạo thành công [GPUResourceManagerMonitor] (bộ giám sát trình quản lý tài nguyên GPU)")
    
    def set_gpu_manager(self, gpu_manager) -> None:
        """
        **[Set GPU Manager Instance] (thiết lập instance quản lý GPU)**
        
        Args:
            gpu_manager: [GPUResourceManager] (trình quản lý GPU) instance
        """
        self.gpu_manager = gpu_manager
        self.manager_status.is_active = True
        self.logger.info("✅ [GPU MONITOR] Đã kết nối [GPU Manager] (trình quản lý GPU)")
    
    def start_monitoring(self) -> bool:
        """
        **[Start Real-time Monitoring] (bắt đầu giám sát thời gian thực)**
        
        Returns:
            bool: True nếu [monitoring] (giám sát) bắt đầu thành công
        """
        if self.is_monitoring:
            self.logger.warning("⚠️ [GPU MONITOR] Đã ở trạng thái [monitoring] (đang giám sát) - bỏ qua yêu cầu khởi động")
            return True
            
        if not self.gpu_manager:
            self.logger.error("❌ [GPU MONITOR] Không thể bắt đầu [monitoring] (giám sát) - thiếu instance [GPU manager] (trình quản lý GPU)")
            return False
            
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="GPUResourceMonitor"
        )
        self.monitor_thread.start()
        
        self.logger.info(f"🚀 [GPU MONITOR] Đã bắt đầu [real-time monitoring] (giám sát thời gian thực) (khoảng lặp: {self.health_check_interval}s)")
        return True
    
    def stop_monitoring(self) -> None:
        """**[Stop Real-time Monitoring] (dừng giám sát thời gian thực)**"""
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        self.logger.info("🛑 [GPU MONITOR] Đã dừng [real-time monitoring] (giám sát thời gian thực)")
    
    def _monitoring_loop(self) -> None:
        """**[Main Monitoring Loop] (vòng lặp giám sát chính)**"""
        self.logger.info("🔄 [GPU MONITOR] Vòng lặp [monitoring] (giám sát) đã khởi động")
        
        while self.is_monitoring:
            try:
                # ✅ HEALTH CHECK: Thực hiện health check
                health_metrics = self.perform_health_check()
                
                # ✅ HISTORY MANAGEMENT: Quản lý lịch sử
                self._add_health_record(health_metrics)
                self._cleanup_old_records()
                
                # ✅ STATUS UPDATE: Cập nhật trạng thái
                self._update_manager_status(health_metrics)
                
                # ✅ LOG PERIODIC STATUS: Log trạng thái định kỳ
                if len(self.health_history) % 10 == 0:  # Mỗi 10 records
                    self._log_comprehensive_status()
                
            except Exception as e:
                self.logger.error(f"❌ [GPU MONITOR] Lỗi trong vòng lặp [monitoring] (giám sát): {e}")
                self.manager_status.failed_operations += 1
            
            # ✅ SLEEP: Chờ interval tiếp theo
            time.sleep(self.health_check_interval)
    
    def perform_health_check(self) -> GPUHealthMetrics:
        """
        **[Perform Comprehensive Health Check] (thực hiện kiểm tra sức khỏe toàn diện)**
        
        Returns:
            GPUHealthMetrics: [Comprehensive health data] (dữ liệu sức khỏe tổng hợp)
        """
        start_time = time.time()
        
        try:
            # ✅ BASIC STATUS: Trạng thái cơ bản
            gpu_count = self.gpu_manager.get_gpu_count() if self.gpu_manager else 0
            nvml_initialized = self.gpu_manager.is_nvml_initialized() if self.gpu_manager else False
            manager_active = self.gpu_manager is not None
            
            # ✅ PERFORMANCE METRICS: Chỉ số hiệu năng
            processes_cloaked = len(self.cloaked_processes)
            cloaking_success_rate = self._calculate_success_rate()
            
            # ✅ GPU HARDWARE METRICS: Chỉ số phần cứng GPU
            memory_usage_mb = self._get_gpu_memory_usage()
            temperature_celsius = self._get_gpu_temperature()
            power_usage_watts = self._get_gpu_power_usage()
            utilization_percent = self._get_gpu_utilization()
            
            # ✅ CREATE HEALTH METRICS: Tạo chỉ số sức khỏe
            health_metrics = GPUHealthMetrics(
                timestamp=time.time(),
                gpu_count=gpu_count,
                nvml_initialized=nvml_initialized,
                manager_active=manager_active,
                processes_cloaked=processes_cloaked,
                memory_usage_mb=memory_usage_mb,
                temperature_celsius=temperature_celsius,
                power_usage_watts=power_usage_watts,
                utilization_percent=utilization_percent,
                cloaking_success_rate=cloaking_success_rate
            )
            
            # ✅ PERFORMANCE TRACKING: Theo dõi hiệu năng
            operation_time = (time.time() - start_time) * 1000  # ms
            self.operation_times.append(operation_time)
            if len(self.operation_times) > 100:  # Keep last 100 measurements
                self.operation_times.pop(0)
            
            self.manager_status.total_operations += 1
            self.manager_status.successful_operations += 1
            self.manager_status.last_health_check = time.time()
            
            return health_metrics
            
        except Exception as e:
            self.logger.error(f"❌ [GPU MONITOR] Health check failed: {e}")
            self.manager_status.failed_operations += 1
            
            # ✅ FALLBACK METRICS: Chỉ số dự phòng
            return GPUHealthMetrics(
                timestamp=time.time(),
                gpu_count=0,
                nvml_initialized=False,
                manager_active=False,
                processes_cloaked=0,
                memory_usage_mb=0.0,
                temperature_celsius=0,
                power_usage_watts=0.0,
                utilization_percent=0,
                cloaking_success_rate=0.0,
                last_error=str(e)
            )
    
    def _get_gpu_memory_usage(self) -> float:
        """**[Get GPU Memory Usage] (lấy mức sử dụng bộ nhớ GPU)**"""
        try:
            if not self.gpu_manager or not self.gpu_manager.is_nvml_initialized():
                return 0.0
            
            # ✅ NVML INTEGRATION: Tích hợp NVML
            import pynvml
            total_memory = 0.0
            gpu_count = self.gpu_manager.get_gpu_count()
            
            for i in range(gpu_count):
                handle = self.gpu_manager.get_handle(i)
                if handle:
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    total_memory += mem_info.used / (1024 * 1024)  # Convert to MB
            
            return total_memory
        except Exception:
            return 0.0
    
    def _get_gpu_temperature(self) -> int:
        """**[Get GPU Temperature] (lấy nhiệt độ GPU)**"""
        try:
            if not self.gpu_manager or not self.gpu_manager.is_nvml_initialized():
                return 0
            
            import pynvml
            max_temp = 0
            gpu_count = self.gpu_manager.get_gpu_count()
            
            for i in range(gpu_count):
                handle = self.gpu_manager.get_handle(i)
                if handle:
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    max_temp = max(max_temp, temp)
            
            return max_temp
        except Exception:
            return 0
    
    def _get_gpu_power_usage(self) -> float:
        """**[Get GPU Power Usage] (lấy mức tiêu thụ điện GPU)**"""
        try:
            if not self.gpu_manager or not self.gpu_manager.is_nvml_initialized():
                return 0.0
            
            import pynvml
            total_power = 0.0
            gpu_count = self.gpu_manager.get_gpu_count()
            
            for i in range(gpu_count):
                handle = self.gpu_manager.get_handle(i)
                if handle:
                    power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert to Watts
                    total_power += power
            
            return total_power
        except Exception:
            return 0.0
    
    def _get_gpu_utilization(self) -> int:
        """**[Get GPU Utilization] (lấy mức sử dụng GPU)**"""
        try:
            if not self.gpu_manager or not self.gpu_manager.is_nvml_initialized():
                return 0
            
            import pynvml
            max_util = 0
            gpu_count = self.gpu_manager.get_gpu_count()
            
            for i in range(gpu_count):
                handle = self.gpu_manager.get_handle(i)
                if handle:
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    max_util = max(max_util, util.gpu)
            
            return max_util
        except Exception:
            return 0
    
    def _calculate_success_rate(self) -> float:
        """**[Calculate Cloaking Success Rate] (tính tỷ lệ thành công che giấu)**"""
        if self.manager_status.total_operations == 0:
            return 0.0
        return (self.manager_status.successful_operations / self.manager_status.total_operations) * 100.0
    
    def _add_health_record(self, health_metrics: GPUHealthMetrics) -> None:
        """**[Add Health Record to History] (thêm bản ghi sức khỏe vào lịch sử)**"""
        self.health_history.append(health_metrics)
        
        # ✅ LIMIT HISTORY SIZE: Giới hạn kích thước lịch sử
        if len(self.health_history) > self.max_history_records:
            self.health_history.pop(0)
    
    def _cleanup_old_records(self) -> None:
        """**[Cleanup Old Records] (dọn dẹp bản ghi cũ)**"""
        cutoff_time = time.time() - (self.history_retention_hours * 3600)
        self.health_history = [
            record for record in self.health_history 
            if record.timestamp > cutoff_time
        ]
    
    def _update_manager_status(self, health_metrics: GPUHealthMetrics) -> None:
        """**[Update Manager Status] (cập nhật trạng thái trình quản lý)**"""
        # ✅ AVERAGE RESPONSE TIME: Thời gian phản hồi trung bình
        if self.operation_times:
            self.manager_status.average_response_time_ms = sum(self.operation_times) / len(self.operation_times)
        
        # ✅ CURRENT LOAD: Tải hiện tại
        self.manager_status.current_load = health_metrics.processes_cloaked
        
        # ✅ STATUS DETAILS: Chi tiết trạng thái
        self.manager_status.status_details = {
            'gpu_count': health_metrics.gpu_count,
            'nvml_initialized': health_metrics.nvml_initialized,
            'memory_usage_mb': health_metrics.memory_usage_mb,
            'temperature_celsius': health_metrics.temperature_celsius,
            'power_usage_watts': health_metrics.power_usage_watts,
            'utilization_percent': health_metrics.utilization_percent,
            'cloaking_success_rate': health_metrics.cloaking_success_rate
        }
    
    def _log_comprehensive_status(self) -> None:
        """**[Log Comprehensive Status] (ghi log trạng thái toàn diện)**"""
        if not self.health_history:
            return
            
        latest = self.health_history[-1]
        avg_response = self.manager_status.average_response_time_ms
        success_rate = self._calculate_success_rate()
        
        self.logger.info(f"📊 [GPU MONITOR] [COMPREHENSIVE STATUS] (trạng thái tổng quát):")
        self.logger.info(f"🎮 [GPUs] (số lượng GPU): {latest.gpu_count}, [NVML] (thư viện NVML): {latest.nvml_initialized}, [Active] (đang hoạt động): {latest.manager_active}")
        self.logger.info(f"⚡ [Memory] (bộ nhớ): {latest.memory_usage_mb:.1f}MB, [Temp] (nhiệt độ): {latest.temperature_celsius}°C, [Power] (công suất): {latest.power_usage_watts:.1f}W")
        self.logger.info(f"🔒 [Processes Cloaked] (tiến trình đã che giấu): {latest.processes_cloaked}, [Success Rate] (tỷ lệ thành công): {success_rate:.1f}%")
        self.logger.info(f"📈 [Avg Response] (thời gian phản hồi trung bình): {avg_response:.1f}ms, [Total Ops] (tổng số thao tác): {self.manager_status.total_operations}")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        **[Get Dashboard Data] (lấy dữ liệu bảng điều khiển)**
        
        Returns:
            Dict: [Comprehensive dashboard data] (dữ liệu tổng hợp cho bảng điều khiển)
        """
        if not self.health_history:
            return {'status': 'no_data', 'message': 'No monitoring data available'}
        
        latest = self.health_history[-1]
        
        # ✅ DASHBOARD DATA: Dữ liệu dashboard
        dashboard_data = {
            'timestamp': datetime.now().isoformat(),
            'gpu_manager_status': {
                'active': latest.manager_active,
                'gpu_count': latest.gpu_count,
                'nvml_initialized': latest.nvml_initialized,
                'health_status': 'healthy' if latest.manager_active and latest.nvml_initialized else 'unhealthy'
            },
            'performance_metrics': {
                'processes_cloaked': latest.processes_cloaked,
                'cloaking_success_rate': latest.cloaking_success_rate,
                'average_response_time_ms': self.manager_status.average_response_time_ms,
                'total_operations': self.manager_status.total_operations,
                'successful_operations': self.manager_status.successful_operations,
                'failed_operations': self.manager_status.failed_operations
            },
            'hardware_metrics': {
                'memory_usage_mb': latest.memory_usage_mb,
                'temperature_celsius': latest.temperature_celsius,
                'power_usage_watts': latest.power_usage_watts,
                'utilization_percent': latest.utilization_percent
            },
            'monitoring_info': {
                'is_monitoring': self.is_monitoring,
                'health_check_interval': self.health_check_interval,
                'history_records': len(self.health_history),
                'last_health_check': datetime.fromtimestamp(self.manager_status.last_health_check).isoformat()
            },
            'recent_history': [
                asdict(record) for record in self.health_history[-10:]  # Last 10 records
            ]
        }
        
        return dashboard_data
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        **[Get Health Summary] (lấy tóm tắt sức khỏe)**
        
        Returns:
            Dict: [Health summary] (tóm tắt sức khỏe) với [status codes] (mã trạng thái)
        """
        if not self.health_history:
            return {
                'status': 'unknown',
                'message': 'No health data available',
                'recommendations': ['Start monitoring to collect health data']
            }
        
        latest = self.health_history[-1]
        recommendations = []
        
        # ✅ HEALTH ANALYSIS: Phân tích sức khỏe
        if not latest.manager_active:
            status = 'critical'
            message = 'GPU Manager is not active'
            recommendations.append('Check GPU Manager initialization')
        elif not latest.nvml_initialized:
            status = 'warning'
            message = 'NVML is not initialized'
            recommendations.append('Verify NVIDIA drivers and NVML installation')
        elif latest.temperature_celsius > 80:
            status = 'warning'
            message = f'High GPU temperature: {latest.temperature_celsius}°C'
            recommendations.append('Check GPU cooling and ventilation')
        elif latest.cloaking_success_rate < 90:
            status = 'warning'
            message = f'Low cloaking success rate: {latest.cloaking_success_rate:.1f}%'
            recommendations.append('Review cloaking strategy configuration')
        else:
            status = 'healthy'
            message = 'All systems operating normally'
            recommendations.append('Continue regular monitoring')
        
        return {
            'status': status,
            'message': message,
            'recommendations': recommendations,
            'last_check': datetime.fromtimestamp(latest.timestamp).isoformat(),
            'key_metrics': {
                'gpu_count': latest.gpu_count,
                'processes_cloaked': latest.processes_cloaked,
                'success_rate': latest.cloaking_success_rate,
                'temperature': latest.temperature_celsius
            }
        }
    
    def register_cloaked_process(self, pid: int, process_info: Dict[str, Any]) -> None:
        """
        **[Register Cloaked Process] (đăng ký tiến trình đã che giấu)**
        
        Args:
            pid: [Process ID] (mã định danh tiến trình)
            process_info: Thông tin tiến trình
        """
        self.cloaked_processes[pid] = {
            'registered_at': time.time(),
            'process_info': process_info,
            'cloaking_strategies': process_info.get('strategies', [])
        }
        self.logger.info(f"✅ [GPU MONITOR] Đã đăng ký [cloaked process] (tiến trình đã che giấu) PID={pid}")
    
    def unregister_cloaked_process(self, pid: int) -> None:
        """
        **[Unregister Cloaked Process] (hủy đăng ký tiến trình đã che giấu)**
        
        Args:
            pid: [Process ID] (mã định danh tiến trình)
        """
        if pid in self.cloaked_processes:
            del self.cloaked_processes[pid]
            self.logger.info(f"🗑️ [GPU MONITOR] Đã hủy đăng ký [cloaked process] (tiến trình đã che giấu) PID={pid}")
    
    def export_monitoring_data(self, filepath: str = None) -> str:
        """
        **[Export Monitoring Data] (xuất dữ liệu giám sát)**
        
        Args:
            filepath: Đường dẫn file xuất (tùy chọn)
            
        Returns:
            str: Đường dẫn file đã xuất
        """
        if not filepath:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = f"/home/azureuser/ncs-gpu/app/mining_environment/logs/gpu_monitor_export_{timestamp}.json"
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'manager_status': asdict(self.manager_status),
            'health_history': [asdict(record) for record in self.health_history],
            'cloaked_processes': self.cloaked_processes,
            'configuration': self.config
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            self.logger.info(f"📁 [GPU MONITOR] Đã xuất [monitoring data] (dữ liệu giám sát) đến: {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f"❌ [GPU MONITOR] Xuất dữ liệu thất bại: {e}")
            raise


# ✅ GLOBAL MONITOR INSTANCE: Instance toàn cục
_gpu_monitor_instance: Optional[GPUResourceManagerMonitor] = None

def get_gpu_monitor() -> GPUResourceManagerMonitor:
    """
    **[Get Global GPU Monitor Instance] (lấy instance giám sát GPU toàn cục)**
    
    Returns:
        GPUResourceManagerMonitor: [Global monitor instance] (instance giám sát toàn cục)
    """
    global _gpu_monitor_instance
    if _gpu_monitor_instance is None:
        _gpu_monitor_instance = GPUResourceManagerMonitor()
    return _gpu_monitor_instance

def initialize_gpu_monitoring(gpu_manager, config: Dict[str, Any] = None) -> GPUResourceManagerMonitor:
    """
    **[Initialize GPU Monitoring System] (khởi tạo hệ thống giám sát GPU)**
    
    Args:
        gpu_manager: [GPUResourceManager] (trình quản lý GPU) instance
        config: [Configuration] (cấu hình) cho [monitoring] (giám sát)
        
    Returns:
        GPUResourceManagerMonitor: [Configured monitor instance] (instance giám sát đã cấu hình)
    """
    monitor = get_gpu_monitor()
    monitor.set_gpu_manager(gpu_manager)
    if config:
        monitor.config.update(config)
    
    # ✅ AUTO-START: Tự động bắt đầu monitoring
    if config and config.get('auto_start_monitoring', True):
        monitor.start_monitoring()
    
    return monitor