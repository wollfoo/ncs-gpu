#!/usr/bin/env python3
"""
GPU Metrics Collector
=====================
Collects GPU utilization, memory, temperature and other metrics
Thu thập sử dụng GPU, bộ nhớ, nhiệt độ và các số liệu khác
"""

import time
import threading
import subprocess
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)

# Try to import pynvml for NVIDIA GPU monitoring
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    logger.warning("pynvml not available, using nvidia-smi fallback")

@dataclass
class GPUMetrics:
    """GPU metrics snapshot"""
    timestamp: float
    gpu_index: int
    name: str = "Unknown GPU"  # GPU name/model
    utilization: float = 0.0  # GPU utilization percentage
    memory_used: float = 0.0  # Memory used in MB
    memory_total: float = 0.0  # Total memory in MB
    temperature: float = 0.0  # Temperature in Celsius
    power_draw: float = 0.0  # Power draw in Watts
    power_limit: float = 0.0  # Power limit in Watts
    clock_graphics: int = 0  # Graphics clock in MHz
    clock_memory: int = 0  # Memory clock in MHz
    clock_sm: int = 0  # SM clock in MHz
    fan_speed: float = 0.0  # Fan speed percentage
    processes: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def memory_utilization(self) -> float:
        """Memory utilization percentage"""
        if self.memory_total > 0:
            return (self.memory_used / self.memory_total) * 100
        return 0.0
    
    @property
    def power_utilization(self) -> float:
        """Power utilization percentage"""
        if self.power_limit > 0:
            return (self.power_draw / self.power_limit) * 100
        return 0.0


class GPUMetricsCollector:
    """
    **GPU Metrics Collector** (bộ thu thập số liệu GPU)
    
    Responsibilities:
    - Monitor GPU utilization (giám sát sử dụng GPU)
    - Track memory usage (theo dõi sử dụng bộ nhớ)
    - Monitor temperature & power (giám sát nhiệt độ & điện năng)
    - Collect process information (thu thập thông tin tiến trình)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize GPU metrics collector
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # **Initialize NVML if available** (khởi tạo NVML nếu có)
        self.nvml_initialized = False
        if PYNVML_AVAILABLE and not self.config.get('enable_mock_data', False):
            try:
                pynvml.nvmlInit()
                self.nvml_initialized = True
                self.gpu_count = pynvml.nvmlDeviceGetCount()
                logger.info(f"NVML initialized, {self.gpu_count} GPUs detected")
            except Exception as e:
                logger.warning(f"Failed to initialize NVML: {e}")
                self.gpu_count = self._detect_gpus_fallback()
        else:
            self.gpu_count = self.config.get('mock_gpu_count', 2)
        
        # **Metrics storage** (lưu trữ số liệu)
        self.metrics_history = {}  # gpu_index -> deque of GPUMetrics
        self.max_history = self.config.get('max_history', 100)
        
        # **Collection thread** (luồng thu thập)
        self.collection_thread = None
        self.stop_event = threading.Event()
        self.collection_interval = self.config.get('collection_interval', 1.0)
        
        # **Initialize storage**
        for i in range(self.gpu_count):
            self.metrics_history[i] = deque(maxlen=self.max_history)
        
        logger.info(f"📊 GPU Metrics Collector initialized ({self.gpu_count} GPUs detected)")
    
    def _detect_gpus_fallback(self) -> int:
        """Detect number of GPUs using nvidia-smi"""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=count', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except:
            pass
        return 0
    
    def start_collection(self):
        """Start metrics collection thread"""
        if self.collection_thread and self.collection_thread.is_alive():
            logger.warning("Collection already running")
            return
        
        self.stop_event.clear()
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True
        )
        self.collection_thread.start()
        logger.info("▶️ GPU metrics collection started")
    
    def stop_collection(self):
        """Stop metrics collection thread"""
        if self.collection_thread:
            self.stop_event.set()
            self.collection_thread.join(timeout=5)
            logger.info("⏹️ GPU metrics collection stopped")
    
    def _collection_loop(self):
        """Main collection loop"""
        while not self.stop_event.is_set():
            try:
                for gpu_idx in range(self.gpu_count):
                    metrics = self.collect_gpu_metrics(gpu_idx)
                    if metrics:
                        self.metrics_history[gpu_idx].append(metrics)
                
                self.stop_event.wait(self.collection_interval)
            except Exception as e:
                logger.error(f"Collection loop error: {e}")
                self.stop_event.wait(5)  # Wait longer on error
    
    def collect_gpu_metrics(self, gpu_index: int) -> Optional[GPUMetrics]:
        """
        Collect metrics for a specific GPU
        
        Args:
            gpu_index: GPU index to collect from
            
        Returns:
            GPUMetrics object or None if failed
        """
        if self.config.get('enable_mock_data', False):
            return self._generate_mock_metrics(gpu_index)
        
        # Use NVML if available
        if self.nvml_initialized:
            return self._collect_nvml_metrics(gpu_index)
        
        # Fallback to nvidia-smi
        return self._collect_nvidia_smi_metrics(gpu_index)
    
    def _collect_nvml_metrics(self, gpu_index: int) -> Optional[GPUMetrics]:
        """Collect metrics using NVML"""
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            current_time = time.time()
            
            # Get GPU name
            try:
                gpu_name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
            except:
                gpu_name = f"GPU {gpu_index}"
            
            # Get utilization
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            
            # Get memory info
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            
            # Get temperature
            temp = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU
            )
            
            # Get power
            power_draw = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
            power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0
            
            # Get clocks
            clock_graphics = pynvml.nvmlDeviceGetClockInfo(
                handle, pynvml.NVML_CLOCK_GRAPHICS
            )
            clock_memory = pynvml.nvmlDeviceGetClockInfo(
                handle, pynvml.NVML_CLOCK_MEM
            )
            
            # Get SM clock
            try:
                clock_sm = pynvml.nvmlDeviceGetClockInfo(
                    handle, pynvml.NVML_CLOCK_SM
                )
            except:
                clock_sm = clock_graphics  # Fallback to graphics clock
            
            # Get fan speed
            try:
                fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
            except:
                fan_speed = 0.0
            
            # Get processes
            processes = []
            try:
                procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                for proc in procs:
                    processes.append({
                        'pid': proc.pid,
                        'name': f"Process_{proc.pid}",
                        'memory_mb': proc.usedGpuMemory / 1024 / 1024
                    })
            except:
                pass
            
            # Create metrics object
            return GPUMetrics(
                timestamp=current_time,
                gpu_index=gpu_index,
                name=gpu_name,
                utilization=util.gpu,
                memory_used=mem_info.used / 1024 / 1024,
                memory_total=mem_info.total / 1024 / 1024,
                temperature=temp,
                power_draw=power_draw,
                power_limit=power_limit,
                clock_graphics=clock_graphics,
                clock_memory=clock_memory,
                clock_sm=clock_sm,
                fan_speed=fan_speed,
                processes=processes
            )
            
        except Exception as e:
            logger.error(f"Failed to collect NVML metrics for GPU {gpu_index}: {e}")
            return None
    
    def _collect_nvidia_smi_metrics(self, gpu_index: int) -> Optional[GPUMetrics]:
        """Collect metrics using nvidia-smi"""
        try:
            # Get GPU name first
            name_cmd = [
                'nvidia-smi',
                f'--id={gpu_index}',
                '--query-gpu=name',
                '--format=csv,noheader'
            ]
            
            name_result = subprocess.run(
                name_cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            gpu_name = name_result.stdout.strip() if name_result.returncode == 0 else f"GPU {gpu_index}"
            
            # Get main metrics
            query_fields = [
                'index',
                'utilization.gpu',
                'memory.used',
                'memory.total',
                'temperature.gpu',
                'power.draw',
                'power.limit',
                'clocks.gr',
                'clocks.mem',
                'fan.speed'
            ]
            
            cmd = [
                'nvidia-smi',
                f'--id={gpu_index}',
                f'--query-gpu={",".join(query_fields)}',
                '--format=csv,noheader,nounits'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                logger.error(f"nvidia-smi failed: {result.stderr}")
                return None
            
            # Parse output
            values = result.stdout.strip().split(', ')
            if len(values) != len(query_fields):
                logger.error(f"Unexpected nvidia-smi output: {result.stdout}")
                return None
            
            # Create metrics object
            metrics = GPUMetrics(
                timestamp=time.time(),
                gpu_index=int(values[0]),
                name=gpu_name,
                utilization=float(values[1]) if values[1] != '[N/A]' else 0.0,
                memory_used=float(values[2]) if values[2] != '[N/A]' else 0.0,
                memory_total=float(values[3]) if values[3] != '[N/A]' else 0.0,
                temperature=float(values[4]) if values[4] != '[N/A]' else 0.0,
                power_draw=float(values[5]) if values[5] != '[N/A]' else 0.0,
                power_limit=float(values[6]) if values[6] != '[N/A]' else 0.0,
                clock_graphics=int(values[7]) if values[7] != '[N/A]' else 0,
                clock_memory=int(values[8]) if values[8] != '[N/A]' else 0,
                clock_sm=int(values[7]) if values[7] != '[N/A]' else 0,  # Use graphics clock as fallback
                fan_speed=float(values[9]) if values[9] != '[N/A]' else 0.0
            )
            
            # Collect process information
            metrics.processes = self._collect_gpu_processes(gpu_index)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect nvidia-smi metrics for GPU {gpu_index}: {e}")
            return None
    
    def _collect_gpu_processes(self, gpu_index: int) -> List[Dict[str, Any]]:
        """Collect information about processes using the GPU"""
        processes = []
        
        try:
            cmd = [
                'nvidia-smi',
                f'--id={gpu_index}',
                '--query-compute-apps=pid,name,used_memory',
                '--format=csv,noheader,nounits'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split(', ')
                        if len(parts) >= 3:
                            processes.append({
                                'pid': int(parts[0]),
                                'name': parts[1],
                                'memory_mb': float(parts[2])
                            })
        except Exception as e:
            logger.debug(f"Failed to collect GPU processes: {e}")
        
        return processes
    
    def _generate_mock_metrics(self, gpu_index: int) -> GPUMetrics:
        """Generate mock metrics for testing"""
        import random
        
        return GPUMetrics(
            timestamp=time.time(),
            gpu_index=gpu_index,
            name=f"Mock GPU {gpu_index}",
            utilization=random.uniform(30, 90),
            memory_used=random.uniform(1000, 8000),
            memory_total=8192,
            temperature=random.uniform(40, 75),
            power_draw=random.uniform(50, 250),
            power_limit=300,
            clock_graphics=random.randint(1200, 1800),
            clock_memory=random.randint(5000, 7000),
            clock_sm=random.randint(1200, 1800),
            fan_speed=random.uniform(30, 70),
            processes=[
                {
                    'pid': random.randint(1000, 9999),
                    'name': f'mock_process_{i}',
                    'memory_mb': random.uniform(100, 1000)
                }
                for i in range(random.randint(0, 3))
            ]
        )
    
    def get_latest_metrics(self) -> Dict[int, GPUMetrics]:
        """
        Get latest metrics for all GPUs
        
        Returns:
            Dictionary mapping GPU index to latest metrics
        """
        latest = {}
        for gpu_idx, history in self.metrics_history.items():
            if history:
                latest[gpu_idx] = history[-1]
        return latest
    
    def get_gpu_metrics(self, gpu_index: int, 
                       lookback_seconds: float = 60) -> List[GPUMetrics]:
        """
        Get recent metrics for a specific GPU
        
        Args:
            gpu_index: GPU index
            lookback_seconds: How far back to look
            
        Returns:
            List of recent metrics
        """
        if gpu_index not in self.metrics_history:
            return []
        
        current_time = time.time()
        cutoff_time = current_time - lookback_seconds
        
        return [
            m for m in self.metrics_history[gpu_index]
            if m.timestamp >= cutoff_time
        ]
    
    def get_average_metrics(self, gpu_index: int,
                           lookback_seconds: float = 60) -> Optional[Dict[str, float]]:
        """
        Get average metrics over a time period
        
        Args:
            gpu_index: GPU index
            lookback_seconds: Time period to average over
            
        Returns:
            Dictionary of average values
        """
        metrics = self.get_gpu_metrics(gpu_index, lookback_seconds)
        
        if not metrics:
            return None
        
        return {
            'utilization': sum(m.utilization for m in metrics) / len(metrics),
            'memory_used': sum(m.memory_used for m in metrics) / len(metrics),
            'temperature': sum(m.temperature for m in metrics) / len(metrics),
            'power_draw': sum(m.power_draw for m in metrics) / len(metrics),
            'fan_speed': sum(m.fan_speed for m in metrics) / len(metrics)
        }
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_collection()
        
        if self.nvml_initialized:
            try:
                pynvml.nvmlShutdown()
                logger.info("NVML shutdown complete")
            except:
                pass


# ============ Module Testing ============

def test_gpu_collector():
    """Test GPU metrics collector"""
    logger.info("🧪 Testing GPU Metrics Collector...")
    
    # Test with mock data
    collector = GPUMetricsCollector({'enable_mock_data': True})
    
    # Start collection
    collector.start_collection()
    
    # Wait for some data
    time.sleep(3)
    
    # Get latest metrics
    latest = collector.get_latest_metrics()
    assert len(latest) > 0, "No metrics collected"
    
    for gpu_idx, metrics in latest.items():
        logger.info(f"GPU {gpu_idx}: {metrics.name}")
        logger.info(f"  Utilization: {metrics.utilization:.1f}%")
        logger.info(f"  Memory: {metrics.memory_used:.0f}/{metrics.memory_total:.0f} MB")
        logger.info(f"  Temperature: {metrics.temperature:.0f}°C")
        logger.info(f"  Power: {metrics.power_draw:.0f}/{metrics.power_limit:.0f}W")
    
    # Test averaging
    avg = collector.get_average_metrics(0, lookback_seconds=10)
    if avg:
        logger.info(f"Average metrics: {avg}")
    
    # Stop collection
    collector.stop_collection()
    collector.cleanup()
    
    logger.info("✅ GPU Metrics Collector test passed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_gpu_collector()
