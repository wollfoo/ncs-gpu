"""
GPU Orchestrator Module
=======================
Core orchestration logic for GPU optimization
Điều phối lõi cho tối ưu hóa GPU
"""

import os
import time
import json
import logging
import psutil
from typing import Dict, Any, Optional, List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

# Internal imports
# Fix circular import - sửa import vòng tròn
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gpu_optimization.core.base import BaseOptimizer
from gpu_optimization.config.loader import ConfigLoader
from .lifecycle_manager import LifecycleManager, LifecycleState

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Strategy types (các loại chiến lược)"""
    POWER = "power"
    CLOCK = "clock"
    MEMORY = "memory"
    TEMPERATURE = "temperature"
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"
    STEALTH = "stealth"


@dataclass
class OptimizationTask:
    """
    Optimization task definition.
    Định nghĩa tác vụ tối ưu.
    """
    pid: int
    gpu_index: int
    strategy: str
    params: Dict[str, Any]
    timeout: float = 30.0


class GPUOrchestrator:
    """
    **GPU Orchestrator** (bộ điều phối GPU) - Core orchestration engine.
    
    Coordinates:
    - Strategy selection (lựa chọn chiến lược)
    - Resource allocation (phân bổ tài nguyên)
    - Parallel execution (thực thi song song)
    - Metrics collection (thu thập số liệu)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize orchestrator.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logger
        
        # **Lifecycle Manager** (quản lý vòng đời)
        self.lifecycle = LifecycleManager(config.get('lifecycle', {}))
        
        # **Core components** (thành phần lõi)
        self.executor = None
        self.strategy_engine = None
        self.hardware_controller = None
        self.metrics_collector = None
        
        # **State tracking** (theo dõi trạng thái)
        self.active_processes = {}
        self.optimization_history = []
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'avg_duration': 0.0
        }
        
        # Initialize components
        self._initialize_components()
        
        logger.info("✅ GPU Orchestrator initialized")
    
    def _initialize_components(self):
        """Initialize all orchestrator components"""
        
        # **Thread pool executor** (bộ thực thi luồng)
        max_workers = self.config.get('max_workers', 4)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(f"Thread pool created with {max_workers} workers")
        
        # **Strategy engine** (engine chiến lược)
        self.strategy_engine = StrategyEngine()
        
        # **Hardware controller** (điều khiển phần cứng)  
        self.hardware_controller = HardwareController()
        
        # **Metrics collector** (thu thập số liệu)
        self.metrics_collector = MetricsCollector()
    
    def optimize(self, 
                 process_info: Dict[str, Any],
                 strategies: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        **Main optimization method** (phương thức tối ưu chính).
        
        Args:
            process_info: Process information
            strategies: Optional list of strategies
            
        Returns:
            Optimization results
        """
        start_time = time.time()
        pid = process_info['pid']
        gpu_index = process_info.get('gpu_index', 0)
        
        results = {
            'pid': pid,
            'gpu_index': gpu_index,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'strategies_applied': [],
            'metrics': {},
            'errors': []
        }
        
        try:
            logger.info(f"🎯 Starting optimization for PID {pid} on GPU {gpu_index}")
            
            # **Step 1: Validate process** (xác thực tiến trình)
            if not self._validate_process(pid):
                results['errors'].append(f"Process {pid} not found or not accessible")
                return results
            
            # **Step 2: Collect baseline metrics** (thu thập số liệu cơ sở)
            baseline = self.metrics_collector.collect_gpu_metrics(gpu_index)
            results['metrics']['baseline'] = baseline
            
            # **Step 3: Select strategies** (lựa chọn chiến lược)
            if not strategies:
                strategies = self.strategy_engine.select_strategies(baseline)
            
            # **Step 4: Prepare tasks** (chuẩn bị tác vụ)
            tasks = self._prepare_tasks(pid, gpu_index, strategies)
            
            # **Step 5: Execute strategies** (thực thi chiến lược)
            execution_results = self._execute_strategies(tasks)
            
            # **Step 6: Apply optimizations** (áp dụng tối ưu)
            hw_results = self.hardware_controller.apply_optimizations(
                pid, gpu_index, execution_results
            )
            
            # **Step 7: Collect post metrics** (thu thập số liệu sau)
            post_metrics = self.metrics_collector.collect_gpu_metrics(gpu_index)
            results['metrics']['post'] = post_metrics
            
            # **Step 8: Calculate improvements** (tính toán cải thiện)
            improvements = self._calculate_improvements(baseline, post_metrics)
            results['improvements'] = improvements
            
            # Update results
            results['strategies_applied'] = strategies
            results['execution_results'] = execution_results
            results['hardware_results'] = hw_results
            results['success'] = True
            
            # Update stats
            self.stats['total'] += 1
            self.stats['success'] += 1
            
            logger.info(f"✅ Optimization completed for PID {pid}")
            
        except Exception as e:
            logger.error(f"❌ Optimization failed: {e}")
            results['errors'].append(str(e))
            self.stats['failed'] += 1
        
        finally:
            # Calculate duration
            duration = time.time() - start_time
            results['duration'] = duration
            
            # Update average
            self._update_avg_duration(duration)
            
            # Save to history
            self.optimization_history.append(results)
            
        return results
    
    def _validate_process(self, pid: int) -> bool:
        """
        Validate if process exists and is accessible.
        Xác thực tiến trình tồn tại và có thể truy cập.
        """
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def _prepare_tasks(self, 
                      pid: int, 
                      gpu_index: int,
                      strategies: List[str]) -> List[OptimizationTask]:
        """
        Prepare optimization tasks.
        Chuẩn bị các tác vụ tối ưu.
        """
        tasks = []
        for strategy in strategies:
            task = OptimizationTask(
                pid=pid,
                gpu_index=gpu_index,
                strategy=strategy,
                params=self.config.get(f'{strategy}_params', {}),
                timeout=self.config.get('strategy_timeout', 30.0)
            )
            tasks.append(task)
        
        return tasks
    
    def _execute_strategies(self, tasks: List[OptimizationTask]) -> Dict[str, Any]:
        """
        Execute strategies in parallel.
        Thực thi chiến lược song song.
        """
        results = {}
        futures = []
        
        for task in tasks:
            future = self.executor.submit(self._execute_single_strategy, task)
            futures.append((task.strategy, future))
        
        # Collect results
        for strategy, future in futures:
            try:
                result = future.result(timeout=30.0)
                results[strategy] = result
            except TimeoutError:
                logger.warning(f"Strategy {strategy} timed out")
                results[strategy] = {'status': 'timeout'}
            except Exception as e:
                logger.error(f"Strategy {strategy} failed: {e}")
                results[strategy] = {'status': 'error', 'error': str(e)}
        
        return results
    
    def _execute_single_strategy(self, task: OptimizationTask) -> Dict[str, Any]:
        """
        Execute a single strategy.
        Thực thi một chiến lược đơn.
        """
        return self.strategy_engine.execute(
            task.strategy,
            task.pid,
            task.gpu_index,
            task.params
        )
    
    def _calculate_improvements(self, 
                               baseline: Dict[str, Any],
                               post: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate performance improvements.
        Tính toán cải thiện hiệu năng.
        """
        improvements = {}
        
        # Power reduction
        if 'power' in baseline and 'power' in post:
            power_reduction = baseline['power'] - post['power']
            improvements['power_reduction'] = power_reduction
            improvements['power_reduction_pct'] = (power_reduction / baseline['power']) * 100
        
        # Temperature reduction
        if 'temperature' in baseline and 'temperature' in post:
            temp_reduction = baseline['temperature'] - post['temperature']
            improvements['temp_reduction'] = temp_reduction
        
        # Memory optimization
        if 'memory_used' in baseline and 'memory_used' in post:
            mem_reduction = baseline['memory_used'] - post['memory_used']
            improvements['memory_saved'] = mem_reduction
        
        return improvements
    
    def _update_avg_duration(self, duration: float):
        """Update average optimization duration"""
        total = self.stats['total']
        if total > 0:
            avg = self.stats['avg_duration']
            self.stats['avg_duration'] = (avg * (total - 1) + duration) / total
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get orchestrator status.
        Lấy trạng thái bộ điều phối.
        """
        return {
            'active_processes': len(self.active_processes),
            'stats': self.stats,
            'executor_active': self.executor._threads if self.executor else 0
        }
    
    def shutdown(self):
        """
        Graceful shutdown.
        Tắt ổn định.
        """
        logger.info("Shutting down orchestrator...")
        
        if self.executor:
            self.executor.shutdown(wait=True)
        
        if self.hardware_controller:
            self.hardware_controller.cleanup()
        
        logger.info("✅ Orchestrator shut down")


class StrategyEngine:
    """
    **Strategy Engine** (engine chiến lược) - Strategy selection and execution.
    """
    
    def __init__(self):
        """Initialize strategy engine"""
        self.strategies = {
            'power': self._optimize_power,
            'clock': self._optimize_clock,
            'memory': self._optimize_memory,
            'temperature': self._optimize_temperature,
            'aggressive': self._apply_aggressive,
            'balanced': self._apply_balanced,
            'stealth': self._apply_stealth
        }
    
    def select_strategies(self, metrics: Dict[str, Any]) -> List[str]:
        """
        Select optimal strategies based on metrics.
        Lựa chọn chiến lược tối ưu dựa trên số liệu.
        """
        strategies = []
        
        # High power usage
        if metrics.get('power', 0) > 250:
            strategies.append('power')
        
        # High temperature
        if metrics.get('temperature', 0) > 75:
            strategies.append('temperature')
        
        # High memory usage
        if metrics.get('memory_used', 0) > 8000:
            strategies.append('memory')
        
        # Default to balanced if no specific issues
        if not strategies:
            strategies.append('balanced')
        
        return strategies
    
    def execute(self, 
                strategy: str,
                pid: int,
                gpu_index: int,
                params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a strategy.
        Thực thi một chiến lược.
        """
        if strategy not in self.strategies:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        return self.strategies[strategy](pid, gpu_index, params)
    
    def _optimize_power(self, pid: int, gpu_index: int, params: Dict) -> Dict:
        """Power optimization (tối ưu công suất)"""
        target_power = params.get('target_power', 200)
        return {
            'status': 'success',
            'action': 'power_cap',
            'target': target_power,
            'applied': True
        }
    
    def _optimize_clock(self, pid: int, gpu_index: int, params: Dict) -> Dict:
        """Clock optimization (tối ưu xung nhịp)"""
        target_clock = params.get('target_clock', 1500)
        return {
            'status': 'success',
            'action': 'clock_limit',
            'target': target_clock,
            'applied': True
        }
    
    def _optimize_memory(self, pid: int, gpu_index: int, params: Dict) -> Dict:
        """Memory optimization (tối ưu bộ nhớ)"""
        return {
            'status': 'success',
            'action': 'memory_cleanup',
            'freed': 1024,  # MB
            'applied': True
        }
    
    def _optimize_temperature(self, pid: int, gpu_index: int, params: Dict) -> Dict:
        """Temperature optimization (tối ưu nhiệt độ)"""
        return {
            'status': 'success',
            'action': 'thermal_throttle',
            'target_temp': 70,
            'applied': True
        }
    
    def _apply_aggressive(self, pid: int, gpu_index: int, params: Dict) -> Dict:
        """Aggressive strategy (chiến lược mạnh)"""
        return {
            'status': 'success',
            'mode': 'aggressive',
            'power_reduction': 30,  # %
            'performance_impact': 15  # %
        }
    
    def _apply_balanced(self, pid: int, gpu_index: int, params: Dict) -> Dict:
        """Balanced strategy (chiến lược cân bằng)"""
        return {
            'status': 'success',
            'mode': 'balanced',
            'power_reduction': 15,  # %
            'performance_impact': 5  # %
        }
    
    def _apply_stealth(self, pid: int, gpu_index: int, params: Dict) -> Dict:
        """Stealth strategy (chiến lược ẩn)"""
        return {
            'status': 'success',
            'mode': 'stealth',
            'power_variation': True,
            'noise_added': True
        }


class HardwareController:
    """
    **Hardware Controller** (điều khiển phần cứng) - GPU hardware control.
    """
    
    def __init__(self):
        """Initialize hardware controller"""
        self.logger = logger.getChild('hardware')
        self.applied_settings = {}
    
    def apply_optimizations(self,
                           pid: int,
                           gpu_index: int,
                           strategy_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply hardware optimizations based on strategy results.
        Áp dụng tối ưu phần cứng dựa trên kết quả chiến lược.
        """
        results = {
            'applied': [],
            'failed': [],
            'status': 'success'
        }
        
        for strategy, result in strategy_results.items():
            if result.get('status') != 'success':
                continue
            
            try:
                if strategy == 'power' and 'target' in result:
                    self._set_power_limit(gpu_index, result['target'])
                    results['applied'].append(f"power_limit={result['target']}W")
                
                elif strategy == 'clock' and 'target' in result:
                    self._set_clock_limit(gpu_index, result['target'])
                    results['applied'].append(f"clock_limit={result['target']}MHz")
                
                elif strategy == 'temperature' and 'target_temp' in result:
                    self._set_temp_limit(gpu_index, result['target_temp'])
                    results['applied'].append(f"temp_limit={result['target_temp']}C")
                
            except Exception as e:
                self.logger.error(f"Failed to apply {strategy}: {e}")
                results['failed'].append(strategy)
        
        # Store applied settings
        key = f"{pid}_{gpu_index}"
        self.applied_settings[key] = {
            'timestamp': datetime.now(),
            'settings': results['applied']
        }
        
        return results
    
    def _set_power_limit(self, gpu_index: int, limit: int):
        """Set GPU power limit (đặt giới hạn công suất GPU)"""
        # Placeholder - would use nvidia-smi or NVML
        self.logger.info(f"Set GPU {gpu_index} power limit to {limit}W")
    
    def _set_clock_limit(self, gpu_index: int, limit: int):
        """Set GPU clock limit (đặt giới hạn xung nhịp GPU)"""
        # Placeholder - would use nvidia-smi or NVML
        self.logger.info(f"Set GPU {gpu_index} clock limit to {limit}MHz")
    
    def _set_temp_limit(self, gpu_index: int, limit: int):
        """Set GPU temperature limit (đặt giới hạn nhiệt độ GPU)"""
        # Placeholder - would use nvidia-smi or NVML
        self.logger.info(f"Set GPU {gpu_index} temp limit to {limit}C")
    
    def cleanup(self):
        """Cleanup and restore original settings"""
        self.logger.info("Cleaning up hardware settings...")
        # Would restore original GPU settings here


class MetricsCollector:
    """
    **Metrics Collector** (thu thập số liệu) - Collect GPU and system metrics.
    """
    
    def __init__(self):
        """Initialize metrics collector"""
        self.logger = logger.getChild('metrics')
    
    def collect_gpu_metrics(self, gpu_index: int) -> Dict[str, Any]:
        """
        Collect GPU metrics.
        Thu thập số liệu GPU.
        """
        try:
            # Placeholder - would use nvidia-ml-py or nvidia-smi
            metrics = {
                'gpu_index': gpu_index,
                'timestamp': datetime.now().isoformat(),
                'power': 150 + (gpu_index * 10),  # Mock data
                'temperature': 65 + (gpu_index * 2),  # Mock data
                'memory_used': 4096 + (gpu_index * 512),  # Mock data MB
                'memory_total': 16384,  # Mock data MB
                'utilization': 75 + (gpu_index * 5),  # Mock data %
                'clock_sm': 1500,  # MHz
                'clock_mem': 7000  # MHz
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect GPU metrics: {e}")
            return {}
