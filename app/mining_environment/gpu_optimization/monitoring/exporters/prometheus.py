#!/usr/bin/env python3
"""
Prometheus Exporter
===================
Export metrics in Prometheus format
Xuất số liệu theo định dạng Prometheus
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from pathlib import Path

# Import collectors
from ..collectors.gpu_metrics import GPUMetricsCollector, GPUMetrics
from ..collectors.process_metrics import ProcessMetricsCollector, ProcessMetrics
from ..collectors.system_metrics import SystemMetricsCollector, SystemMetrics

logger = logging.getLogger(__name__)


class PrometheusExporter:
    """
    **Prometheus Exporter** (bộ xuất Prometheus)
    
    Responsibilities:
    - Format metrics for Prometheus (định dạng số liệu cho Prometheus)
    - Expose metrics endpoint (cung cấp endpoint số liệu)
    - Handle metric labels (xử lý nhãn số liệu)
    - Support metric types (hỗ trợ các loại số liệu)
    """
    
    def __init__(self, collectors: Optional[Dict[str, Any]] = None):
        """
        Initialize Prometheus exporter
        
        Args:
            collectors: Dictionary of collectors to export from
        """
        self.collectors = collectors or {}
        
        # **Metric prefix** (tiền tố số liệu)
        self.metric_prefix = "gpu_optimization"
        
        # **Export statistics** (thống kê xuất)
        self.export_count = 0
        self.last_export = None
        
        logger.info("📊 Prometheus Exporter initialized")
    
    def format_metric(self, name: str, value: float, 
                     metric_type: str = "gauge",
                     labels: Optional[Dict[str, str]] = None,
                     help_text: Optional[str] = None) -> str:
        """
        Format a single metric in Prometheus format
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Type (gauge, counter, histogram)
            labels: Metric labels
            help_text: Metric description
            
        Returns:
            Formatted metric string
        """
        lines = []
        
        # Add HELP if provided
        if help_text:
            lines.append(f"# HELP {name} {help_text}")
        
        # Add TYPE
        lines.append(f"# TYPE {name} {metric_type}")
        
        # Format labels
        label_str = ""
        if labels:
            label_parts = [f'{k}="{v}"' for k, v in labels.items()]
            label_str = "{" + ",".join(label_parts) + "}"
        
        # Add metric value
        lines.append(f"{name}{label_str} {value}")
        
        return "\n".join(lines)
    
    def export_gpu_metrics(self, gpu_collector: GPUMetricsCollector) -> List[str]:
        """
        Export GPU metrics
        
        Args:
            gpu_collector: GPU metrics collector
            
        Returns:
            List of formatted metric strings
        """
        metrics = []
        
        # Get latest metrics for all GPUs
        latest = gpu_collector.get_latest_metrics()
        
        for gpu_idx, gpu_metrics in latest.items():
            labels = {"gpu": str(gpu_idx)}
            
            # GPU utilization
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_gpu_utilization_percent",
                gpu_metrics.utilization,
                "gauge",
                labels,
                "GPU utilization percentage"
            ))
            
            # Memory usage
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_gpu_memory_used_mb",
                gpu_metrics.memory_used,
                "gauge",
                labels,
                "GPU memory used in MB"
            ))
            
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_gpu_memory_total_mb",
                gpu_metrics.memory_total,
                "gauge",
                labels,
                "GPU total memory in MB"
            ))
            
            # Temperature
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_gpu_temperature_celsius",
                gpu_metrics.temperature,
                "gauge",
                labels,
                "GPU temperature in Celsius"
            ))
            
            # Power
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_gpu_power_draw_watts",
                gpu_metrics.power_draw,
                "gauge",
                labels,
                "GPU power draw in watts"
            ))
            
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_gpu_power_limit_watts",
                gpu_metrics.power_limit,
                "gauge",
                labels,
                "GPU power limit in watts"
            ))
            
            # Clocks
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_gpu_clock_graphics_mhz",
                gpu_metrics.clock_graphics,
                "gauge",
                labels,
                "GPU graphics clock in MHz"
            ))
            
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_gpu_clock_memory_mhz",
                gpu_metrics.clock_memory,
                "gauge",
                labels,
                "GPU memory clock in MHz"
            ))
            
            # Fan speed
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_gpu_fan_speed_percent",
                gpu_metrics.fan_speed,
                "gauge",
                labels,
                "GPU fan speed percentage"
            ))
            
            # Process count
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_gpu_process_count",
                len(gpu_metrics.processes),
                "gauge",
                labels,
                "Number of processes using GPU"
            ))
        
        return metrics
    
    def export_process_metrics(self, process_collector: ProcessMetricsCollector) -> List[str]:
        """
        Export process metrics
        
        Args:
            process_collector: Process metrics collector
            
        Returns:
            List of formatted metric strings
        """
        metrics = []
        
        # Get current processes
        processes = process_collector.get_current_processes()
        
        # Aggregate metrics
        total_gpu_memory = 0.0
        total_cpu_percent = 0.0
        optimized_count = 0
        
        for pid, proc_metrics in processes.items():
            labels = {
                "pid": str(pid),
                "name": proc_metrics.name,
                "gpu": str(proc_metrics.gpu_index)
            }
            
            # CPU usage
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_process_cpu_percent",
                proc_metrics.cpu_percent,
                "gauge",
                labels,
                "Process CPU usage percentage"
            ))
            
            # Memory usage
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_process_memory_rss_mb",
                proc_metrics.memory_rss_mb,
                "gauge",
                labels,
                "Process RSS memory in MB"
            ))
            
            # GPU memory
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_process_gpu_memory_mb",
                proc_metrics.gpu_memory_mb,
                "gauge",
                labels,
                "Process GPU memory in MB"
            ))
            
            # Thread count
            metrics.append(self.format_metric(
                f"{self.metric_prefix}_process_thread_count",
                proc_metrics.num_threads,
                "gauge",
                labels,
                "Process thread count"
            ))
            
            # Aggregates
            total_gpu_memory += proc_metrics.gpu_memory_mb
            total_cpu_percent += proc_metrics.cpu_percent
            if proc_metrics.optimization_applied:
                optimized_count += 1
        
        # Add aggregate metrics
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_processes_total",
            len(processes),
            "gauge",
            None,
            "Total number of GPU processes"
        ))
        
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_processes_optimized",
            optimized_count,
            "gauge",
            None,
            "Number of optimized processes"
        ))
        
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_processes_gpu_memory_total_mb",
            total_gpu_memory,
            "gauge",
            None,
            "Total GPU memory used by all processes"
        ))
        
        return metrics
    
    def export_system_metrics(self, system_collector: SystemMetricsCollector) -> List[str]:
        """
        Export system metrics
        
        Args:
            system_collector: System metrics collector
            
        Returns:
            List of formatted metric strings
        """
        metrics = []
        
        # Get latest system metrics
        sys_metrics = system_collector.get_latest_metrics()
        
        if not sys_metrics:
            return metrics
        
        # CPU metrics
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_system_cpu_percent",
            sys_metrics.cpu_percent,
            "gauge",
            None,
            "System CPU usage percentage"
        ))
        
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_system_load_avg_1min",
            sys_metrics.load_avg_1min,
            "gauge",
            None,
            "System 1-minute load average"
        ))
        
        # Memory metrics
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_system_memory_percent",
            sys_metrics.memory_percent,
            "gauge",
            None,
            "System memory usage percentage"
        ))
        
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_system_memory_available_gb",
            sys_metrics.memory_available_gb,
            "gauge",
            None,
            "System available memory in GB"
        ))
        
        # Disk metrics
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_system_disk_percent",
            sys_metrics.disk_percent,
            "gauge",
            None,
            "System disk usage percentage"
        ))
        
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_system_disk_read_mb_per_sec",
            sys_metrics.disk_read_mb_s,
            "gauge",
            None,
            "System disk read rate in MB/s"
        ))
        
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_system_disk_write_mb_per_sec",
            sys_metrics.disk_write_mb_s,
            "gauge",
            None,
            "System disk write rate in MB/s"
        ))
        
        # Network metrics
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_system_network_sent_mb_per_sec",
            sys_metrics.network_sent_mb_s,
            "gauge",
            None,
            "System network send rate in MB/s"
        ))
        
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_system_network_recv_mb_per_sec",
            sys_metrics.network_recv_mb_s,
            "gauge",
            None,
            "System network receive rate in MB/s"
        ))
        
        # Process counts
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_system_process_count",
            sys_metrics.process_count,
            "gauge",
            None,
            "Total system process count"
        ))
        
        metrics.append(self.format_metric(
            f"{self.metric_prefix}_system_thread_count",
            sys_metrics.thread_count,
            "gauge",
            None,
            "Total system thread count"
        ))
        
        return metrics
    
    def export_all(self) -> str:
        """
        Export all metrics from registered collectors
        
        Returns:
            Complete Prometheus format metrics string
        """
        all_metrics = []
        
        # Add metadata
        all_metrics.append(f"# GPU Optimization Metrics Export")
        all_metrics.append(f"# Timestamp: {datetime.now().isoformat()}")
        all_metrics.append("")
        
        # Export from each collector
        if 'gpu' in self.collectors:
            gpu_metrics = self.export_gpu_metrics(self.collectors['gpu'])
            all_metrics.extend(gpu_metrics)
            all_metrics.append("")
        
        if 'process' in self.collectors:
            proc_metrics = self.export_process_metrics(self.collectors['process'])
            all_metrics.extend(proc_metrics)
            all_metrics.append("")
        
        if 'system' in self.collectors:
            sys_metrics = self.export_system_metrics(self.collectors['system'])
            all_metrics.extend(sys_metrics)
            all_metrics.append("")
        
        # Update statistics
        self.export_count += 1
        self.last_export = time.time()
        
        # Add export stats
        all_metrics.append(self.format_metric(
            f"{self.metric_prefix}_exporter_export_count",
            self.export_count,
            "counter",
            None,
            "Total number of exports"
        ))
        
        return "\n".join(all_metrics)
    
    def export_to_file(self, filepath: str) -> bool:
        """
        Export metrics to a file
        
        Args:
            filepath: Path to export file
            
        Returns:
            True if successful
        """
        try:
            metrics_text = self.export_all()
            
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                f.write(metrics_text)
            
            logger.info(f"📁 Prometheus metrics exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return False


# ============ Module Testing ============

def test_prometheus_exporter():
    """Test Prometheus exporter"""
    logger.info("🧪 Testing Prometheus Exporter...")
    
    # Create mock collectors
    from ..collectors.gpu_metrics import GPUMetricsCollector
    from ..collectors.process_metrics import ProcessMetricsCollector
    from ..collectors.system_metrics import SystemMetricsCollector
    
    gpu_collector = GPUMetricsCollector({'enable_mock_data': True})
    process_collector = ProcessMetricsCollector()
    system_collector = SystemMetricsCollector()
    
    # Start collections
    gpu_collector.start_collection()
    process_collector.start_collection()
    system_collector.start_collection()
    
    # Wait for data
    time.sleep(2)
    
    # Create exporter
    exporter = PrometheusExporter({
        'gpu': gpu_collector,
        'process': process_collector,
        'system': system_collector
    })
    
    # Export metrics
    metrics_text = exporter.export_all()
    logger.info(f"Exported {len(metrics_text.split(chr(10)))} lines of metrics")
    
    # Export to file
    success = exporter.export_to_file('/tmp/test_metrics.prom')
    assert success, "Failed to export to file"
    
    # Stop collectors
    gpu_collector.stop_collection()
    process_collector.stop_collection()
    system_collector.stop_collection()
    
    logger.info("✅ Prometheus Exporter test passed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_prometheus_exporter()
