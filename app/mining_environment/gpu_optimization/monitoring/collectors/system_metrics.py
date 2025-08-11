#!/usr/bin/env python3
"""
System Metrics Collector
========================
Collects system-wide metrics and resource utilization
Thu thập số liệu toàn hệ thống và mức sử dụng tài nguyên
"""

import os
import time
import json
import psutil
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import deque
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System metrics snapshot"""
    timestamp: float
    # CPU metrics
    cpu_percent: float
    cpu_count: int
    cpu_freq_mhz: float
    load_avg_1min: float
    load_avg_5min: float
    load_avg_15min: float
    # Memory metrics
    memory_total_gb: float
    memory_used_gb: float
    memory_available_gb: float
    memory_percent: float
    swap_total_gb: float
    swap_used_gb: float
    swap_percent: float
    # Disk metrics
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float
    disk_read_mb_s: float
    disk_write_mb_s: float
    # Network metrics
    network_sent_mb_s: float
    network_recv_mb_s: float
    # Process metrics
    process_count: int
    thread_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class SystemMetricsCollector:
    """
    **System Metrics Collector** (bộ thu thập số liệu hệ thống)
    
    Responsibilities:
    - System resource monitoring (giám sát tài nguyên hệ thống)
    - Performance tracking (theo dõi hiệu năng)
    - Bottleneck detection (phát hiện nút thắt)
    - Resource utilization analysis (phân tích sử dụng tài nguyên)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize system metrics collector
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or self._get_default_config()
        
        # **Metrics storage** (lưu trữ số liệu)
        self.buffer_size = self.config.get('buffer_size', 1000)
        self.metrics_history = deque(maxlen=self.buffer_size)
        
        # **Collection settings** (cài đặt thu thập)
        self.collection_interval = self.config.get('collection_interval', 1.0)
        
        # **State management** (quản lý trạng thái)
        self.is_collecting = False
        self.collection_thread = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        
        # **Baseline metrics** (số liệu cơ sở)
        self.baseline_metrics = None
        self.previous_disk_io = None
        self.previous_net_io = None
        self.previous_timestamp = None
        
        # **Statistics** (thống kê)
        self.stats = {
            'total_collections': 0,
            'failed_collections': 0,
            'last_collection': None,
            'avg_collection_time': 0.0
        }
        
        # **Alert thresholds** (ngưỡng cảnh báo)
        self.thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 90.0,
            'disk_percent': 95.0,
            'load_avg_threshold': psutil.cpu_count()
        }
        
        logger.info("📊 System Metrics Collector initialized")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'buffer_size': 1000,
            'collection_interval': 1.0,
            'disk_path': '/',
            'network_interface': None,  # None = all interfaces
            'export_path': '/tmp/system_metrics'
        }
    
    # ============ Metrics Collection ============
    
    def collect_system_metrics(self) -> Optional[SystemMetrics]:
        """
        Collect current system metrics
        
        Returns:
            SystemMetrics object or None if failed
        """
        try:
            timestamp = time.time()
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            load_avg = os.getloadavg()
            
            # Memory metrics
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk = psutil.disk_usage(self.config.get('disk_path', '/'))
            disk_io = psutil.disk_io_counters()
            
            # Calculate disk I/O rates
            disk_read_mb_s = 0.0
            disk_write_mb_s = 0.0
            if self.previous_disk_io and self.previous_timestamp:
                time_delta = timestamp - self.previous_timestamp
                if time_delta > 0:
                    read_delta = disk_io.read_bytes - self.previous_disk_io.read_bytes
                    write_delta = disk_io.write_bytes - self.previous_disk_io.write_bytes
                    disk_read_mb_s = (read_delta / (1024 * 1024)) / time_delta
                    disk_write_mb_s = (write_delta / (1024 * 1024)) / time_delta
            
            # Network metrics
            net_io = psutil.net_io_counters()
            
            # Calculate network I/O rates
            network_sent_mb_s = 0.0
            network_recv_mb_s = 0.0
            if self.previous_net_io and self.previous_timestamp:
                time_delta = timestamp - self.previous_timestamp
                if time_delta > 0:
                    sent_delta = net_io.bytes_sent - self.previous_net_io.bytes_sent
                    recv_delta = net_io.bytes_recv - self.previous_net_io.bytes_recv
                    network_sent_mb_s = (sent_delta / (1024 * 1024)) / time_delta
                    network_recv_mb_s = (recv_delta / (1024 * 1024)) / time_delta
            
            # Process metrics
            process_count = len(psutil.pids())
            thread_count = sum(p.num_threads() for p in psutil.process_iter(['num_threads']) 
                             if p.info['num_threads'])
            
            # Create metrics object
            metrics = SystemMetrics(
                timestamp=timestamp,
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                cpu_freq_mhz=cpu_freq.current if cpu_freq else 0.0,
                load_avg_1min=load_avg[0],
                load_avg_5min=load_avg[1],
                load_avg_15min=load_avg[2],
                memory_total_gb=mem.total / (1024**3),
                memory_used_gb=mem.used / (1024**3),
                memory_available_gb=mem.available / (1024**3),
                memory_percent=mem.percent,
                swap_total_gb=swap.total / (1024**3),
                swap_used_gb=swap.used / (1024**3),
                swap_percent=swap.percent,
                disk_total_gb=disk.total / (1024**3),
                disk_used_gb=disk.used / (1024**3),
                disk_percent=disk.percent,
                disk_read_mb_s=disk_read_mb_s,
                disk_write_mb_s=disk_write_mb_s,
                network_sent_mb_s=network_sent_mb_s,
                network_recv_mb_s=network_recv_mb_s,
                process_count=process_count,
                thread_count=thread_count
            )
            
            # Update previous values for rate calculations
            self.previous_disk_io = disk_io
            self.previous_net_io = net_io
            self.previous_timestamp = timestamp
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return None
    
    # ============ Collection Control ============
    
    def start_collection(self) -> bool:
        """Start metrics collection"""
        if self.is_collecting:
            logger.warning("Collection already running")
            return False
        
        self.is_collecting = True
        self.stop_event.clear()
        
        # Collect baseline metrics
        self.baseline_metrics = self.collect_system_metrics()
        
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True
        )
        self.collection_thread.start()
        
        logger.info("▶️ System metrics collection started")
        return True
    
    def stop_collection(self):
        """Stop metrics collection"""
        if not self.is_collecting:
            return
        
        self.is_collecting = False
        self.stop_event.set()
        
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        
        logger.info("⏹️ System metrics collection stopped")
    
    def _collection_loop(self):
        """Main collection loop"""
        while not self.stop_event.is_set():
            start_time = time.time()
            
            try:
                # Collect metrics
                metrics = self.collect_system_metrics()
                
                if metrics:
                    with self.lock:
                        self.metrics_history.append(metrics)
                        self.stats['total_collections'] += 1
                    
                    # Check for alerts
                    self._check_alerts(metrics)
                else:
                    self.stats['failed_collections'] += 1
                
                # Update statistics
                collection_time = time.time() - start_time
                self.stats['last_collection'] = time.time()
                
                # Update rolling average
                current_avg = self.stats['avg_collection_time']
                self.stats['avg_collection_time'] = (
                    current_avg * 0.9 + collection_time * 0.1
                )
                
            except Exception as e:
                logger.error(f"Collection loop error: {e}")
                self.stats['failed_collections'] += 1
            
            # Wait for next collection interval
            self.stop_event.wait(self.collection_interval)
    
    def _check_alerts(self, metrics: SystemMetrics):
        """Check metrics against alert thresholds"""
        alerts = []
        
        if metrics.cpu_percent > self.thresholds['cpu_percent']:
            alerts.append(f"High CPU usage: {metrics.cpu_percent:.1f}%")
        
        if metrics.memory_percent > self.thresholds['memory_percent']:
            alerts.append(f"High memory usage: {metrics.memory_percent:.1f}%")
        
        if metrics.disk_percent > self.thresholds['disk_percent']:
            alerts.append(f"High disk usage: {metrics.disk_percent:.1f}%")
        
        if metrics.load_avg_1min > self.thresholds['load_avg_threshold']:
            alerts.append(f"High load average: {metrics.load_avg_1min:.2f}")
        
        if alerts:
            logger.warning(f"⚠️ System alerts: {', '.join(alerts)}")
    
    # ============ Data Access ============
    
    def get_latest_metrics(self) -> Optional[SystemMetrics]:
        """Get the latest system metrics"""
        with self.lock:
            if self.metrics_history:
                return self.metrics_history[-1]
            return None
    
    def get_metrics_history(self, duration_seconds: Optional[int] = None) -> List[SystemMetrics]:
        """
        Get historical metrics
        
        Args:
            duration_seconds: How far back to look (None for all)
            
        Returns:
            List of metrics ordered by time
        """
        with self.lock:
            history = list(self.metrics_history)
            
            if duration_seconds:
                cutoff = time.time() - duration_seconds
                history = [m for m in history if m.timestamp >= cutoff]
            
            return history
    
    def get_aggregated_metrics(self, duration_seconds: int = 60) -> Dict[str, float]:
        """
        Get aggregated metrics over a time period
        
        Args:
            duration_seconds: Aggregation period
            
        Returns:
            Dictionary of aggregated metrics
        """
        history = self.get_metrics_history(duration_seconds)
        
        if not history:
            return {}
        
        # Calculate aggregates
        cpu_values = [m.cpu_percent for m in history]
        memory_values = [m.memory_percent for m in history]
        disk_read_values = [m.disk_read_mb_s for m in history]
        disk_write_values = [m.disk_write_mb_s for m in history]
        net_sent_values = [m.network_sent_mb_s for m in history]
        net_recv_values = [m.network_recv_mb_s for m in history]
        
        return {
            'avg_cpu_percent': sum(cpu_values) / len(cpu_values),
            'max_cpu_percent': max(cpu_values),
            'avg_memory_percent': sum(memory_values) / len(memory_values),
            'max_memory_percent': max(memory_values),
            'avg_disk_read_mb_s': sum(disk_read_values) / len(disk_read_values),
            'max_disk_read_mb_s': max(disk_read_values),
            'avg_disk_write_mb_s': sum(disk_write_values) / len(disk_write_values),
            'max_disk_write_mb_s': max(disk_write_values),
            'avg_network_sent_mb_s': sum(net_sent_values) / len(net_sent_values),
            'avg_network_recv_mb_s': sum(net_recv_values) / len(net_recv_values),
            'samples': len(history)
        }
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get system summary including current state and trends"""
        latest = self.get_latest_metrics()
        if not latest:
            return {}
        
        # Get 5-minute aggregates
        aggregates = self.get_aggregated_metrics(300)
        
        return {
            'current': {
                'cpu_percent': latest.cpu_percent,
                'memory_percent': latest.memory_percent,
                'disk_percent': latest.disk_percent,
                'load_avg': latest.load_avg_1min,
                'process_count': latest.process_count
            },
            'aggregates_5min': aggregates,
            'baseline': {
                'cpu_percent': self.baseline_metrics.cpu_percent if self.baseline_metrics else 0,
                'memory_percent': self.baseline_metrics.memory_percent if self.baseline_metrics else 0
            },
            'system_info': {
                'cpu_count': latest.cpu_count,
                'memory_total_gb': latest.memory_total_gb,
                'disk_total_gb': latest.disk_total_gb
            }
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get collector statistics"""
        return {
            **self.stats,
            'buffer_size': self.buffer_size,
            'is_collecting': self.is_collecting,
            'metrics_count': len(self.metrics_history)
        }
    
    def export_metrics(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        """Export current metrics to JSON"""
        with self.lock:
            latest = self.get_latest_metrics()
            
            export_data = {
                'timestamp': datetime.now().isoformat(),
                'current_metrics': latest.to_dict() if latest else None,
                'summary': self.get_system_summary(),
                'statistics': self.get_statistics()
            }
            
            # Save to file if requested
            if filepath:
                Path(filepath).parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, 'w') as f:
                    json.dump(export_data, f, indent=2)
                logger.info(f"📁 System metrics exported to {filepath}")
            
            return export_data


# ============ Module Testing ============

def test_system_metrics_collector():
    """Test system metrics collector"""
    logger.info("🧪 Testing System Metrics Collector...")
    
    # Create collector
    collector = SystemMetricsCollector()
    
    # Collect single metrics
    metrics = collector.collect_system_metrics()
    if metrics:
        logger.info(f"Collected metrics: CPU={metrics.cpu_percent}%, Memory={metrics.memory_percent}%")
    
    # Start continuous collection
    assert collector.start_collection(), "Failed to start collection"
    
    # Wait for some data
    time.sleep(5)
    
    # Get latest metrics
    latest = collector.get_latest_metrics()
    if latest:
        logger.info(f"Latest: CPU={latest.cpu_percent}%, Memory={latest.memory_percent}%")
    
    # Get history
    history = collector.get_metrics_history(10)
    logger.info(f"History: {len(history)} samples")
    
    # Get aggregated metrics
    aggregated = collector.get_aggregated_metrics(60)
    logger.info(f"Aggregated metrics: {aggregated}")
    
    # Get system summary
    summary = collector.get_system_summary()
    logger.info(f"System summary: {summary}")
    
    # Export metrics
    export_data = collector.export_metrics()
    logger.info(f"Exported system metrics")
    
    # Stop collection
    collector.stop_collection()
    
    # Check stats
    stats = collector.get_statistics()
    logger.info(f"Collection stats: {stats}")
    
    logger.info("✅ System Metrics Collector test passed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_system_metrics_collector()
