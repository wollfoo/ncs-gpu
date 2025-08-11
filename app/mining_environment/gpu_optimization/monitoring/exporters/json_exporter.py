#!/usr/bin/env python3
"""
JSON Exporter
=============
Export metrics in JSON format
Xuất số liệu theo định dạng JSON
"""

import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from pathlib import Path

# Import collectors
from ..collectors.gpu_metrics import GPUMetricsCollector
from ..collectors.process_metrics import ProcessMetricsCollector
from ..collectors.system_metrics import SystemMetricsCollector

logger = logging.getLogger(__name__)


class JSONExporter:
    """
    **JSON Exporter** (bộ xuất JSON)
    
    Responsibilities:
    - Format metrics as JSON (định dạng số liệu dạng JSON)
    - Support nested structures (hỗ trợ cấu trúc lồng nhau)
    - Handle timestamps (xử lý dấu thời gian)
    - Provide streaming export (cung cấp xuất streaming)
    """
    
    def __init__(self, collectors: Optional[Dict[str, Any]] = None):
        """
        Initialize JSON exporter
        
        Args:
            collectors: Dictionary of collectors to export from
        """
        self.collectors = collectors or {}
        
        # **Export settings** (cài đặt xuất)
        self.include_metadata = True
        self.pretty_print = False
        self.compress = False
        
        # **Export statistics** (thống kê xuất)
        self.export_count = 0
        self.last_export = None
        
        logger.info("📋 JSON Exporter initialized")
    
    def format_gpu_metrics(self, gpu_collector: GPUMetricsCollector) -> Dict[str, Any]:
        """
        Format GPU metrics as JSON
        
        Args:
            gpu_collector: GPU metrics collector
            
        Returns:
            Dictionary of GPU metrics
        """
        gpu_data = {
            'gpus': {},
            'summary': {
                'total_gpus': 0,
                'avg_utilization': 0.0,
                'total_memory_used_mb': 0.0,
                'total_power_draw_watts': 0.0,
                'max_temperature': 0.0
            }
        }
        
        # Get latest metrics
        latest = gpu_collector.get_latest_metrics()
        
        total_util = 0.0
        total_memory = 0.0
        total_power = 0.0
        max_temp = 0.0
        
        for gpu_idx, metrics in latest.items():
            gpu_data['gpus'][f'gpu_{gpu_idx}'] = {
                'index': gpu_idx,
                'name': metrics.name,
                'utilization': {
                    'gpu': metrics.utilization,
                    'memory': round(metrics.memory_used / metrics.memory_total * 100, 1) if metrics.memory_total > 0 else 0
                },
                'memory': {
                    'used_mb': metrics.memory_used,
                    'total_mb': metrics.memory_total,
                    'free_mb': metrics.memory_total - metrics.memory_used
                },
                'temperature': {
                    'current': metrics.temperature,
                    'threshold': 80,  # Default threshold
                    'status': 'normal' if metrics.temperature < 75 else 'warning' if metrics.temperature < 85 else 'critical'
                },
                'power': {
                    'draw_watts': metrics.power_draw,
                    'limit_watts': metrics.power_limit,
                    'usage_percent': round(metrics.power_draw / metrics.power_limit * 100, 1) if metrics.power_limit > 0 else 0
                },
                'clocks': {
                    'graphics_mhz': metrics.clock_graphics,
                    'memory_mhz': metrics.clock_memory,
                    'sm_mhz': metrics.clock_sm
                },
                'fan_speed': metrics.fan_speed,
                'processes': [
                    {
                        'pid': p['pid'],
                        'name': p['name'],
                        'memory_mb': p['memory_mb']
                    } for p in metrics.processes
                ],
                'timestamp': metrics.timestamp
            }
            
            # Update summary
            total_util += metrics.utilization
            total_memory += metrics.memory_used
            total_power += metrics.power_draw
            max_temp = max(max_temp, metrics.temperature)
        
        # Calculate summary
        gpu_count = len(latest)
        if gpu_count > 0:
            gpu_data['summary'] = {
                'total_gpus': gpu_count,
                'avg_utilization': round(total_util / gpu_count, 1),
                'total_memory_used_mb': round(total_memory, 1),
                'total_power_draw_watts': round(total_power, 1),
                'max_temperature': round(max_temp, 1)
            }
        
        return gpu_data
    
    def format_process_metrics(self, process_collector: ProcessMetricsCollector) -> Dict[str, Any]:
        """
        Format process metrics as JSON
        
        Args:
            process_collector: Process metrics collector
            
        Returns:
            Dictionary of process metrics
        """
        process_data = {
            'processes': {},
            'summary': {
                'total_processes': 0,
                'optimized_processes': 0,
                'total_gpu_memory_mb': 0.0,
                'total_cpu_percent': 0.0,
                'by_gpu': {}
            }
        }
        
        # Get current processes
        processes = process_collector.get_current_processes()
        
        optimized_count = 0
        total_gpu_memory = 0.0
        total_cpu = 0.0
        by_gpu = {}
        
        for pid, metrics in processes.items():
            process_data['processes'][str(pid)] = {
                'pid': pid,
                'name': metrics.name,
                'gpu_index': metrics.gpu_index,
                'cpu': {
                    'percent': metrics.cpu_percent,
                    'threads': metrics.num_threads
                },
                'memory': {
                    'rss_mb': metrics.memory_rss_mb,
                    'vms_mb': metrics.memory_vms_mb,
                    'gpu_mb': metrics.gpu_memory_mb
                },
                'io': {
                    'read_mb': metrics.io_read_mb,
                    'write_mb': metrics.io_write_mb
                },
                'optimization': {
                    'applied': metrics.optimization_applied,
                    'strategy': metrics.optimization_strategy,
                    'timestamp': metrics.optimization_timestamp
                },
                'status': metrics.status,
                'create_time': metrics.create_time,
                'runtime_seconds': time.time() - metrics.create_time
            }
            
            # Update summary
            if metrics.optimization_applied:
                optimized_count += 1
            total_gpu_memory += metrics.gpu_memory_mb
            total_cpu += metrics.cpu_percent
            
            # Group by GPU
            gpu_key = f'gpu_{metrics.gpu_index}'
            if gpu_key not in by_gpu:
                by_gpu[gpu_key] = {
                    'count': 0,
                    'memory_mb': 0.0,
                    'cpu_percent': 0.0
                }
            by_gpu[gpu_key]['count'] += 1
            by_gpu[gpu_key]['memory_mb'] += metrics.gpu_memory_mb
            by_gpu[gpu_key]['cpu_percent'] += metrics.cpu_percent
        
        # Update summary
        process_data['summary'] = {
            'total_processes': len(processes),
            'optimized_processes': optimized_count,
            'total_gpu_memory_mb': round(total_gpu_memory, 1),
            'total_cpu_percent': round(total_cpu, 1),
            'by_gpu': by_gpu
        }
        
        return process_data
    
    def format_system_metrics(self, system_collector: SystemMetricsCollector) -> Dict[str, Any]:
        """
        Format system metrics as JSON
        
        Args:
            system_collector: System metrics collector
            
        Returns:
            Dictionary of system metrics
        """
        system_data = {
            'system': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Get latest metrics
        metrics = system_collector.get_latest_metrics()
        
        if metrics:
            system_data['system'] = {
                'cpu': {
                    'percent': metrics.cpu_percent,
                    'count': metrics.cpu_count,
                    'frequency_mhz': metrics.cpu_freq_mhz,
                    'load_average': {
                        '1min': metrics.load_avg_1min,
                        '5min': metrics.load_avg_5min,
                        '15min': metrics.load_avg_15min
                    }
                },
                'memory': {
                    'percent': metrics.memory_percent,
                    'used_gb': metrics.memory_used_gb,
                    'available_gb': metrics.memory_available_gb,
                    'total_gb': metrics.memory_total_gb,
                    'swap_percent': metrics.swap_percent
                },
                'disk': {
                    'percent': metrics.disk_percent,
                    'used_gb': metrics.disk_used_gb,
                    'free_gb': metrics.disk_total_gb - metrics.disk_used_gb,
                    'total_gb': metrics.disk_total_gb,
                    'io': {
                        'read_mb_s': metrics.disk_read_mb_s,
                        'write_mb_s': metrics.disk_write_mb_s
                    }
                },
                'network': {
                    'sent_mb_s': metrics.network_sent_mb_s,
                    'recv_mb_s': metrics.network_recv_mb_s
                },
                'processes': {
                    'total': metrics.process_count,
                    'threads': metrics.thread_count
                },
                'timestamp': metrics.timestamp
            }
        
        return system_data
    
    def export_all(self, include_history: bool = False) -> Dict[str, Any]:
        """
        Export all metrics as JSON
        
        Args:
            include_history: Include historical data if available
            
        Returns:
            Complete metrics dictionary
        """
        export_data = {
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat(),
            'export_id': f"export_{self.export_count}_{int(time.time())}",
            'metrics': {}
        }
        
        # Add metadata if enabled
        if self.include_metadata:
            export_data['metadata'] = {
                'exporter': 'JSONExporter',
                'export_count': self.export_count,
                'collectors': list(self.collectors.keys()),
                'settings': {
                    'include_metadata': self.include_metadata,
                    'pretty_print': self.pretty_print,
                    'compress': self.compress
                }
            }
        
        # Export from each collector
        if 'gpu' in self.collectors:
            export_data['metrics']['gpu'] = self.format_gpu_metrics(
                self.collectors['gpu']
            )
        
        if 'process' in self.collectors:
            export_data['metrics']['process'] = self.format_process_metrics(
                self.collectors['process']
            )
        
        if 'system' in self.collectors:
            export_data['metrics']['system'] = self.format_system_metrics(
                self.collectors['system']
            )
        
        # Add history if requested
        if include_history:
            export_data['history'] = self._get_history_data()
        
        # Update statistics
        self.export_count += 1
        self.last_export = time.time()
        
        return export_data
    
    def _get_history_data(self) -> Dict[str, Any]:
        """Get historical data from collectors"""
        history = {}
        
        if 'gpu' in self.collectors:
            gpu_collector = self.collectors['gpu']
            if hasattr(gpu_collector, 'metrics_history'):
                history['gpu'] = {
                    'buffer_size': len(gpu_collector.metrics_history),
                    'oldest_timestamp': min(gpu_collector.metrics_history.keys()) if gpu_collector.metrics_history else None,
                    'newest_timestamp': max(gpu_collector.metrics_history.keys()) if gpu_collector.metrics_history else None
                }
        
        return history
    
    def export_to_file(self, filepath: str, 
                      include_history: bool = False) -> bool:
        """
        Export metrics to JSON file
        
        Args:
            filepath: Path to export file
            include_history: Include historical data
            
        Returns:
            True if successful
        """
        try:
            export_data = self.export_all(include_history)
            
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w') as f:
                if self.pretty_print:
                    json.dump(export_data, f, indent=2, default=str)
                else:
                    json.dump(export_data, f, default=str)
            
            logger.info(f"📁 JSON metrics exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export JSON: {e}")
            return False
    
    def export_to_string(self, include_history: bool = False) -> str:
        """
        Export metrics as JSON string
        
        Args:
            include_history: Include historical data
            
        Returns:
            JSON string
        """
        try:
            export_data = self.export_all(include_history)
            
            if self.pretty_print:
                return json.dumps(export_data, indent=2, default=str)
            else:
                return json.dumps(export_data, default=str)
                
        except Exception as e:
            logger.error(f"Failed to serialize JSON: {e}")
            return "{}"


# ============ Module Testing ============

def test_json_exporter():
    """Test JSON exporter"""
    logger.info("🧪 Testing JSON Exporter...")
    
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
    exporter = JSONExporter({
        'gpu': gpu_collector,
        'process': process_collector,
        'system': system_collector
    })
    
    # Test basic export
    exporter.pretty_print = True
    json_data = exporter.export_all()
    assert 'metrics' in json_data
    assert 'timestamp' in json_data
    logger.info(f"Exported JSON with {len(json_data['metrics'])} metric groups")
    
    # Test string export
    json_str = exporter.export_to_string()
    assert len(json_str) > 0
    parsed = json.loads(json_str)
    assert parsed['version'] == '1.0.0'
    
    # Test file export
    success = exporter.export_to_file('/tmp/test_metrics.json')
    assert success, "Failed to export to file"
    
    # Verify file
    with open('/tmp/test_metrics.json', 'r') as f:
        loaded = json.load(f)
        assert loaded['version'] == '1.0.0'
    
    # Stop collectors
    gpu_collector.stop_collection()
    process_collector.stop_collection()
    system_collector.stop_collection()
    
    logger.info("✅ JSON Exporter test passed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_json_exporter()
