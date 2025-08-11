#!/usr/bin/env python3
"""
Process Metrics Collector
=========================
Collects metrics for GPU-utilizing processes
Thu thập số liệu cho các tiến trình sử dụng GPU
"""

import os
import time
import json
import psutil
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict, deque
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ProcessMetrics:
    """Process metrics snapshot"""
    timestamp: float
    pid: int
    name: str
    status: str
    gpu_index: int
    cpu_percent: float
    memory_rss_mb: float  # Resident Set Size
    memory_vms_mb: float  # Virtual Memory Size
    gpu_memory_mb: float
    num_threads: int
    create_time: float
    optimization_applied: bool = False
    optimization_strategy: Optional[str] = None
    
    @property
    def runtime_seconds(self) -> float:
        """Process runtime in seconds"""
        return self.timestamp - self.create_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class ProcessMetricsCollector:
    """
    **Process Metrics Collector** (bộ thu thập số liệu tiến trình)
    
    Responsibilities:
    - Process discovery (khám phá tiến trình)
    - Resource monitoring (giám sát tài nguyên)
    - Optimization tracking (theo dõi tối ưu hóa)
    - Lifecycle monitoring (giám sát vòng đời)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize process metrics collector
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or self._get_default_config()
        
        # **Process tracking** (theo dõi tiến trình)
        self.tracked_processes: Dict[int, ProcessMetrics] = {}
        self.process_history: Dict[int, deque] = {}
        self.buffer_size = self.config.get('buffer_size', 500)
        
        # **GPU process detection** (phát hiện tiến trình GPU)
        self.gpu_processes: Set[int] = set()
        self.scan_interval = self.config.get('scan_interval', 5.0)
        
        # **Collection settings** (cài đặt thu thập)
        self.collection_interval = self.config.get('collection_interval', 2.0)
        
        # **State management** (quản lý trạng thái)
        self.is_collecting = False
        self.collection_thread = None
        self.scan_thread = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        
        # **Statistics** (thống kê)
        self.stats = {
            'total_processes_tracked': 0,
            'current_processes': 0,
            'total_collections': 0,
            'failed_collections': 0
        }
        
        logger.info("📊 Process Metrics Collector initialized")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'buffer_size': 500,
            'collection_interval': 2.0,
            'scan_interval': 5.0,
            'enable_gpu_scan': True,
            'min_gpu_memory_mb': 100,
            'export_path': '/tmp/process_metrics'
        }
    
    # ============ Process Discovery ============
    
    def discover_gpu_processes(self) -> Set[int]:
        """
        Discover processes using GPU
        
        Returns:
            Set of PIDs using GPU
        """
        gpu_pids = set()
        
        # Method 1: Check nvidia-smi
        if self.config.get('enable_gpu_scan', True):
            gpu_pids.update(self._scan_nvidia_smi())
        
        # Method 2: Check known GPU-using process names
        gpu_process_names = ['python', 'python3', 'pytorch', 'tensorflow']
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] in gpu_process_names:
                    # Additional check for GPU usage indicators
                    if self._check_process_gpu_usage(proc.info['pid']):
                        gpu_pids.add(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return gpu_pids
    
    def _scan_nvidia_smi(self) -> Set[int]:
        """Scan nvidia-smi for GPU processes"""
        pids = set()
        
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            pids.add(int(line.strip()))
                        except ValueError:
                            pass
        except Exception as e:
            logger.debug(f"nvidia-smi scan failed: {e}")
        
        return pids
    
    def _check_process_gpu_usage(self, pid: int) -> bool:
        """Check if process is likely using GPU"""
        try:
            proc = psutil.Process(pid)
            
            # Check for CUDA environment variables
            environ = proc.environ()
            if 'CUDA_VISIBLE_DEVICES' in environ:
                return True
            
            # Check for GPU-related file descriptors
            for conn in proc.connections(kind='all'):
                if 'nvidia' in str(conn.laddr):
                    return True
            
            # Check memory maps for GPU libraries
            for mmap in proc.memory_maps():
                if any(lib in mmap.path for lib in ['libcuda', 'libnvidia', 'libcudnn']):
                    return True
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        return False
    
    # ============ Metrics Collection ============
    
    def collect_process_metrics(self, pid: int) -> Optional[ProcessMetrics]:
        """
        Collect metrics for a specific process
        
        Args:
            pid: Process ID
            
        Returns:
            ProcessMetrics object or None if failed
        """
        try:
            proc = psutil.Process(pid)
            
            # Get process info
            with proc.oneshot():
                proc_info = proc.as_dict(attrs=[
                    'name', 'status', 'cpu_percent', 'memory_info',
                    'num_threads', 'create_time'
                ])
            
            # Determine GPU index (simplified - would need actual mapping)
            gpu_index = self._get_process_gpu_index(pid)
            
            # Get GPU memory usage
            gpu_memory = self._get_process_gpu_memory(pid, gpu_index)
            
            # Create metrics object
            metrics = ProcessMetrics(
                timestamp=time.time(),
                pid=pid,
                name=proc_info['name'],
                status=proc_info['status'],
                gpu_index=gpu_index,
                cpu_percent=proc_info['cpu_percent'],
                memory_rss_mb=proc_info['memory_info'].rss / (1024 * 1024),
                memory_vms_mb=proc_info['memory_info'].vms / (1024 * 1024),
                gpu_memory_mb=gpu_memory,
                num_threads=proc_info['num_threads'],
                create_time=proc_info['create_time']
            )
            
            # Check if optimization is applied
            metrics.optimization_applied = self._check_optimization_status(pid)
            if metrics.optimization_applied:
                metrics.optimization_strategy = self._get_optimization_strategy(pid)
            
            return metrics
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug(f"Failed to collect metrics for PID {pid}: {e}")
            return None
    
    def _get_process_gpu_index(self, pid: int) -> int:
        """Get GPU index for process (simplified)"""
        # In real implementation, would check CUDA_VISIBLE_DEVICES
        # or query nvidia-smi for actual GPU assignment
        try:
            proc = psutil.Process(pid)
            environ = proc.environ()
            if 'CUDA_VISIBLE_DEVICES' in environ:
                devices = environ['CUDA_VISIBLE_DEVICES'].split(',')
                if devices:
                    return int(devices[0])
        except:
            pass
        return 0  # Default to GPU 0
    
    def _get_process_gpu_memory(self, pid: int, gpu_index: int) -> float:
        """Get GPU memory usage for process"""
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', f'--id={gpu_index}', 
                 '--query-compute-apps=pid,used_memory',
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split(', ')
                        if len(parts) >= 2 and int(parts[0]) == pid:
                            return float(parts[1])
        except:
            pass
        
        return 0.0
    
    def _check_optimization_status(self, pid: int) -> bool:
        """Check if process has optimization applied"""
        # Check if process is in optimization tracking
        # This would integrate with the orchestrator
        return pid in self.tracked_processes
    
    def _get_optimization_strategy(self, pid: int) -> Optional[str]:
        """Get optimization strategy for process"""
        # Would retrieve from orchestrator/lifecycle manager
        return "balanced"  # Placeholder
    
    # ============ Collection Control ============
    
    def start_collection(self) -> bool:
        """Start metrics collection"""
        if self.is_collecting:
            logger.warning("Collection already running")
            return False
        
        self.is_collecting = True
        self.stop_event.clear()
        
        # Start GPU process scanner
        self.scan_thread = threading.Thread(
            target=self._scan_loop,
            daemon=True
        )
        self.scan_thread.start()
        
        # Start metrics collector
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True
        )
        self.collection_thread.start()
        
        logger.info("▶️ Process metrics collection started")
        return True
    
    def stop_collection(self):
        """Stop metrics collection"""
        if not self.is_collecting:
            return
        
        self.is_collecting = False
        self.stop_event.set()
        
        if self.scan_thread:
            self.scan_thread.join(timeout=5)
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        
        logger.info("⏹️ Process metrics collection stopped")
    
    def _scan_loop(self):
        """Process discovery loop"""
        while not self.stop_event.is_set():
            try:
                # Discover GPU processes
                gpu_pids = self.discover_gpu_processes()
                
                with self.lock:
                    # Add new processes
                    for pid in gpu_pids:
                        if pid not in self.process_history:
                            self.process_history[pid] = deque(maxlen=self.buffer_size)
                            self.stats['total_processes_tracked'] += 1
                    
                    # Update current GPU processes
                    self.gpu_processes = gpu_pids
                    self.stats['current_processes'] = len(gpu_pids)
                
            except Exception as e:
                logger.error(f"Scan loop error: {e}")
            
            self.stop_event.wait(self.scan_interval)
    
    def _collection_loop(self):
        """Main collection loop"""
        while not self.stop_event.is_set():
            try:
                with self.lock:
                    pids_to_collect = list(self.gpu_processes)
                
                # Collect metrics for each process
                for pid in pids_to_collect:
                    metrics = self.collect_process_metrics(pid)
                    
                    if metrics:
                        with self.lock:
                            self.tracked_processes[pid] = metrics
                            self.process_history[pid].append(metrics)
                            self.stats['total_collections'] += 1
                    else:
                        # Process might have terminated
                        with self.lock:
                            if pid in self.gpu_processes:
                                self.gpu_processes.remove(pid)
                            if pid in self.tracked_processes:
                                del self.tracked_processes[pid]
                        self.stats['failed_collections'] += 1
                
            except Exception as e:
                logger.error(f"Collection loop error: {e}")
                self.stats['failed_collections'] += 1
            
            self.stop_event.wait(self.collection_interval)
    
    # ============ Data Access ============
    
    def get_current_processes(self) -> Dict[int, ProcessMetrics]:
        """Get current tracked processes"""
        with self.lock:
            return dict(self.tracked_processes)
    
    def get_process_history(self, pid: int) -> List[ProcessMetrics]:
        """Get historical metrics for a process"""
        with self.lock:
            if pid in self.process_history:
                return list(self.process_history[pid])
            return []
    
    def get_process_summary(self, pid: int) -> Dict[str, Any]:
        """Get summary statistics for a process"""
        history = self.get_process_history(pid)
        
        if not history:
            return {}
        
        current = history[-1] if history else None
        cpu_values = [m.cpu_percent for m in history]
        memory_values = [m.memory_rss_mb for m in history]
        gpu_memory_values = [m.gpu_memory_mb for m in history]
        
        return {
            'pid': pid,
            'name': current.name if current else 'unknown',
            'runtime_seconds': current.runtime_seconds if current else 0,
            'cpu_avg': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
            'cpu_max': max(cpu_values) if cpu_values else 0,
            'memory_avg_mb': sum(memory_values) / len(memory_values) if memory_values else 0,
            'memory_max_mb': max(memory_values) if memory_values else 0,
            'gpu_memory_avg_mb': sum(gpu_memory_values) / len(gpu_memory_values) if gpu_memory_values else 0,
            'gpu_memory_max_mb': max(gpu_memory_values) if gpu_memory_values else 0,
            'optimization_applied': current.optimization_applied if current else False,
            'samples': len(history)
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get collector statistics"""
        return {
            **self.stats,
            'buffer_size': self.buffer_size,
            'is_collecting': self.is_collecting
        }
    
    def export_metrics(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        """Export current metrics to JSON"""
        with self.lock:
            export_data = {
                'timestamp': datetime.now().isoformat(),
                'processes': {},
                'statistics': self.get_statistics()
            }
            
            # Add current process metrics
            for pid, metrics in self.tracked_processes.items():
                export_data['processes'][str(pid)] = metrics.to_dict()
            
            # Save to file if requested
            if filepath:
                Path(filepath).parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, 'w') as f:
                    json.dump(export_data, f, indent=2)
                logger.info(f"📁 Process metrics exported to {filepath}")
            
            return export_data


# ============ Module Testing ============

def test_process_metrics_collector():
    """Test process metrics collector"""
    logger.info("🧪 Testing Process Metrics Collector...")
    
    # Create collector
    collector = ProcessMetricsCollector()
    
    # Discover GPU processes
    gpu_pids = collector.discover_gpu_processes()
    logger.info(f"Discovered {len(gpu_pids)} GPU processes")
    
    # Start collection
    assert collector.start_collection(), "Failed to start collection"
    
    # Wait for some data
    time.sleep(5)
    
    # Get current processes
    processes = collector.get_current_processes()
    logger.info(f"Tracking {len(processes)} processes")
    
    # Get process summaries
    for pid in list(processes.keys())[:3]:  # First 3 processes
        summary = collector.get_process_summary(pid)
        logger.info(f"Process {pid} summary: {summary}")
    
    # Export metrics
    export_data = collector.export_metrics()
    logger.info(f"Exported metrics for {len(export_data['processes'])} processes")
    
    # Stop collection
    collector.stop_collection()
    
    # Check stats
    stats = collector.get_statistics()
    logger.info(f"Collection stats: {stats}")
    
    logger.info("✅ Process Metrics Collector test passed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_process_metrics_collector()
