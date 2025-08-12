#!/usr/bin/env python3
"""
**GPU Optimization Orchestrator** (Bộ điều phối tối ưu GPU)

Central orchestration module that integrates:
- Cross-Process Coordination (điều phối liên tiến trình)
- Parallel Strategy Executor (thực thi chiến lược song song)  
- Performance Profiler (phân tích hiệu năng)

This module serves as the main entry point for GPU optimization tasks.
"""

import os
import logging
import time
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

# **Import core modules** (nhập module lõi)
try:
    from .cloak_strategies import StrategyEngine, MetricsCollectionHub
    from .resource_control import OptimizedHardwareController, GPUResourceManager
    from .cross_process_coordination import CrossProcessCoordinator, ResourceType
    from .parallel_strategy_executor import ParallelStrategyExecutor, StrategyTask
    from .performance_profiler import get_profiler, profile_function
    from .module_loggers import get_optimization_logger
    from .error_management import get_error_reporter, ErrorCode, ErrorSeverity
except ImportError:
    # Fallback for standalone testing
    from .cloak_strategies import StrategyEngine, MetricsCollectionHub
    from resource_control import OptimizedHardwareController, GPUResourceManager
    from .cross_process_coordination import CrossProcessCoordinator, ResourceType
    from .parallel_strategy_executor import ParallelStrategyExecutor, StrategyTask
    from .performance_profiler import PerformanceProfiler, profile_function
    from module_loggers import get_optimization_logger
    from error_management import get_error_reporter, ErrorCode, ErrorSeverity

# **Logger setup** (thiết lập logger)
logger = get_optimization_logger()
error_reporter = get_error_reporter()

# **Global instances** (thực thể toàn cục)
_profiler = get_profiler()
_coordinator: Optional[CrossProcessCoordinator] = None
_parallel_executor: Optional[ParallelStrategyExecutor] = None
_metrics_hub: Optional[MetricsCollectionHub] = None


class GPUOptimizationOrchestrator:
    """
    **Main Orchestrator** (bộ điều phối chính) for GPU optimization workflow.
    
    Coordinates all optimization modules:
    - Resource coordination between processes
    - Parallel strategy execution
    - Performance monitoring and profiling
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize orchestrator with configuration.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or self._get_default_config()
        self.logger = logger
        
        # **Initialize components** (khởi tạo thành phần)
        self._init_components()
        
        # **Performance tracking** (theo dõi hiệu năng)
        self.execution_stats = {
            'total_optimizations': 0,
            'successful': 0,
            'failed': 0,
            'avg_duration': 0.0
        }
        
        self.logger.info("🚀 **GPU Optimization Orchestrator initialized** "
                        "(bộ điều phối tối ưu GPU đã khởi tạo)")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'max_parallel_strategies': 4,
            'strategy_timeout': 30.0,
            'enable_profiling': True,
            'enable_coordination': True,
            'metrics_buffer_size': 1000,
            'profile_report_interval': 300  # 5 minutes
        }
    
    def _init_components(self):
        """Initialize all orchestrator components"""
        global _coordinator, _parallel_executor, _metrics_hub
        
        # **Initialize Cross-Process Coordinator** (khởi tạo điều phối liên tiến trình)
        if self.config['enable_coordination']:
            pid = os.getpid()
            _coordinator = CrossProcessCoordinator(pid)
            self.coordinator = _coordinator
            self.logger.info(f"✅ Cross-Process Coordinator initialized for PID {pid}")
        else:
            self.coordinator = None
        
        # **Initialize Parallel Executor** (khởi tạo bộ thực thi song song)
        _parallel_executor = ParallelStrategyExecutor(
            max_workers=self.config['max_parallel_strategies'],
            default_timeout=self.config['strategy_timeout']
        )
        self.parallel_executor = _parallel_executor
        self.logger.info("✅ Parallel Strategy Executor initialized")
        
        # **Initialize Metrics Hub** (khởi tạo trung tâm số liệu)
        _metrics_hub = MetricsCollectionHub(
            buffer_size=self.config['metrics_buffer_size']
        )
        self.metrics_hub = _metrics_hub
        self.metrics_hub.start_background_logging()
        self.logger.info("✅ Metrics Collection Hub initialized")
        
        # **Initialize core engines** (khởi tạo engine lõi)
        self.strategy_engine = StrategyEngine()
        self.logger.info("✅ Strategy Engine initialized")
        
        # **Initialize Hardware Controller** (khởi tạo điều khiển phần cứng)
        gpu_config = self.config.get('gpu_config', {})
        gpu_logger = logger.getChild('gpu')
        gpu_manager = GPUResourceManager(gpu_config, gpu_logger)
        
        self.hardware_controller = OptimizedHardwareController(
            gpu_manager=gpu_manager,
            baseline_power=300,  # Default baseline
            baseline_temp=70     # Default baseline
        )
        self.logger.info("✅ Hardware Controller initialized")
    
    @profile_function(track_memory=True)
    def optimize_gpu_for_process(self, 
                                 pid: int, 
                                 gpu_index: int = 0,
                                 strategies: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        **Main optimization entry point** (điểm vào tối ưu chính).
        
        Applies GPU optimization strategies to a process with:
        - Cross-process coordination
        - Parallel strategy execution
        - Performance profiling
        
        Args:
            pid: Process ID to optimize
            gpu_index: GPU index to use
            strategies: List of strategies to apply (None = all)
            
        Returns:
            Dictionary with optimization results
        """
        start_time = time.time()
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
            self.logger.info(f"🎯 **Starting GPU optimization** "
                           f"(bắt đầu tối ưu GPU) for PID {pid} on GPU {gpu_index}")
            
            # **Step 1: Request resource coordination** (yêu cầu điều phối tài nguyên)
            if self.coordinator:
                if not self._acquire_gpu_resources(pid, gpu_index):
                    results['errors'].append("Failed to acquire GPU resources")
                    return results
            
            # **Step 2: Collect baseline metrics** (thu thập số liệu cơ sở)
            baseline_metrics = self._collect_gpu_metrics(gpu_index)
            results['metrics']['baseline'] = baseline_metrics
            self.metrics_hub.add_metric('baseline', baseline_metrics)
            
            # **Step 3: Prepare strategy tasks** (chuẩn bị tác vụ chiến lược)
            if strategies is None:
                strategies = ['gpu_power', 'gpu_clock', 'temperature', 'memory']
            
            tasks = self._prepare_strategy_tasks(pid, gpu_index, strategies)
            
            # **Step 4: Execute strategies in parallel** (thực thi chiến lược song song)
            self.logger.info(f"🔄 Executing {len(tasks)} strategies in parallel...")
            execution_results = self.parallel_executor.execute_parallel(tasks)
            
            # **Step 5: Apply hardware optimizations** (áp dụng tối ưu phần cứng)
            hw_results = self.hardware_controller.apply_gpu_optimizations(
                pid, 
                gpu_index,
                window_sec=60  # 1 minute window
            )
            
            # **Step 6: Collect post-optimization metrics** (thu thập số liệu sau tối ưu)
            post_metrics = self._collect_gpu_metrics(gpu_index)
            results['metrics']['post'] = post_metrics
            self.metrics_hub.add_metric('post_optimization', post_metrics)
            
            # **Step 7: Aggregate results** (tổng hợp kết quả)
            results['strategies_applied'] = list(execution_results.keys())
            results['execution_details'] = self.parallel_executor.aggregate_results()
            results['hardware_results'] = hw_results
            results['success'] = True
            
            # **Update statistics** (cập nhật thống kê)
            self.execution_stats['total_optimizations'] += 1
            self.execution_stats['successful'] += 1
            
        except Exception as e:
            self.logger.error(f"❌ Optimization failed for PID {pid}: {e}")
            results['errors'].append(str(e))
            self.execution_stats['failed'] += 1
            
            # **Report error** (báo cáo lỗi)
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Orchestrator optimization failed: {e}",
                severity=ErrorSeverity.HIGH,
                context={
                    'pid': pid,
                    'gpu_index': gpu_index,
                    'strategies': strategies
                }
            )
        
        finally:
            # **Release resources** (giải phóng tài nguyên)
            if self.coordinator:
                self._release_gpu_resources(gpu_index)
            
            # **Calculate duration** (tính thời gian)
            duration = time.time() - start_time
            results['duration'] = duration
            
            # **Update average duration** (cập nhật thời gian trung bình)
            total = self.execution_stats['total_optimizations']
            if total > 0:
                avg = self.execution_stats['avg_duration']
                self.execution_stats['avg_duration'] = (avg * (total - 1) + duration) / total
            
            self.logger.info(f"✅ **Optimization completed** "
                           f"(tối ưu hoàn thành) in {duration:.2f}s")
        
        return results
    
    def _acquire_gpu_resources(self, pid: int, gpu_index: int) -> bool:
        """
        **Acquire GPU resources** (lấy tài nguyên GPU) through coordinator.
        
        Returns:
            True if resources acquired successfully
        """
        try:
            # Request compute resources
            compute_acquired = self.coordinator.request_resource(
                gpu_index,
                ResourceType.GPU_COMPUTE,
                amount=50.0,  # Request 50% compute
                priority=7
            )
            
            if not compute_acquired:
                self.logger.warning(f"⚠️ Failed to acquire GPU compute for PID {pid}")
                return False
            
            # Request memory resources
            memory_acquired = self.coordinator.request_resource(
                gpu_index,
                ResourceType.GPU_MEMORY,
                amount=30.0,  # Request 30% memory
                priority=7
            )
            
            if not memory_acquired:
                # Release compute if memory fails
                self.coordinator.release_resource(gpu_index, ResourceType.GPU_COMPUTE)
                self.logger.warning(f"⚠️ Failed to acquire GPU memory for PID {pid}")
                return False
            
            self.logger.info(f"✅ Acquired GPU resources for PID {pid} on GPU {gpu_index}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Resource acquisition error: {e}")
            return False
    
    def _release_gpu_resources(self, gpu_index: int):
        """**Release GPU resources** (giải phóng tài nguyên GPU)"""
        try:
            self.coordinator.release_resource(gpu_index, ResourceType.GPU_COMPUTE)
            self.coordinator.release_resource(gpu_index, ResourceType.GPU_MEMORY)
            self.logger.info(f"✅ Released GPU resources for GPU {gpu_index}")
        except Exception as e:
            self.logger.error(f"❌ Resource release error: {e}")
    
    def _collect_gpu_metrics(self, gpu_index: int) -> Dict[str, Any]:
        """**Collect GPU metrics** (thu thập số liệu GPU)"""
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            
            metrics = {
                'timestamp': time.time(),
                'gpu_index': gpu_index,
                'temperature': pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU),
                'power': pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0,  # Convert to watts
                'utilization': pynvml.nvmlDeviceGetUtilizationRates(handle).gpu,
                'memory_info': {
                    'used': pynvml.nvmlDeviceGetMemoryInfo(handle).used / (1024**3),  # GB
                    'total': pynvml.nvmlDeviceGetMemoryInfo(handle).total / (1024**3)  # GB
                },
                'clocks': {
                    'sm': pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM),
                    'mem': pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
                }
            }
            
            return metrics
            
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to collect GPU metrics: {e}")
            return {
                'timestamp': time.time(),
                'gpu_index': gpu_index,
                'error': str(e)
            }
    
    def _prepare_strategy_tasks(self, 
                                pid: int, 
                                gpu_index: int,
                                strategies: List[str]) -> List[StrategyTask]:
        """
        **Prepare strategy tasks** (chuẩn bị tác vụ chiến lược) for parallel execution.
        
        Returns:
            List of StrategyTask objects
        """
        tasks = []
        
        for strategy in strategies:
            # Create task function
            def execute_strategy(s=strategy, p=pid, g=gpu_index):
                """Execute single strategy"""
                try:
                    # Apply through strategy engine
                    result = self.strategy_engine.apply_strategy(
                        strategy_type=s,
                        pid=p,
                        params={'gpu_index': g}
                    )
                    
                    # Collect metrics after strategy
                    metrics = self._collect_gpu_metrics(g)
                    
                    return {
                        'strategy': s,
                        'result': result,
                        'metrics': metrics
                    }
                except Exception as e:
                    return {
                        'strategy': s,
                        'error': str(e)
                    }
            
            # Create task
            task = StrategyTask(
                name=f"{strategy}_pid{pid}_gpu{gpu_index}",
                function=execute_strategy,
                timeout=self.config['strategy_timeout'],
                priority=self._get_strategy_priority(strategy)
            )
            
            tasks.append(task)
        
        # Add dependencies
        self._add_task_dependencies(tasks)
        
        return tasks
    
    def _get_strategy_priority(self, strategy: str) -> int:
        """Get priority for strategy (higher = more important)"""
        priority_map = {
            'gpu_power': 10,      # Highest priority
            'temperature': 9,
            'gpu_clock': 8,
            'memory': 7,
            'network': 5,
            'cache': 4
        }
        return priority_map.get(strategy, 5)
    
    def _add_task_dependencies(self, tasks: List[StrategyTask]):
        """Add dependencies between tasks"""
        # Example: memory depends on gpu_power
        task_map = {t.name.split('_')[0]: t for t in tasks}
        
        if 'memory' in task_map and 'gpu' in task_map:
            task_map['memory'].dependencies = [task_map['gpu'].name]
        
        if 'temperature' in task_map and 'gpu' in task_map:
            task_map['temperature'].dependencies = [task_map['gpu'].name]
    
    def generate_performance_report(self, 
                                   output_path: Optional[Path] = None) -> Path:
        """
        **Generate performance report** (tạo báo cáo hiệu năng).
        
        Args:
            output_path: Optional output path for report
            
        Returns:
            Path to generated report
        """
        # Generate profiler report
        dashboard = _profiler.generate_dashboard()
        
        # Add orchestrator statistics
        dashboard['orchestrator_stats'] = self.execution_stats
        
        # Add metrics summary
        dashboard['metrics_summary'] = self.metrics_hub.aggregate_all_metrics()
        
        # Export report
        if output_path is None:
            output_path = Path(f"/tmp/gpu_optimization_report_{datetime.now():%Y%m%d_%H%M%S}.json")
        
        with open(output_path, 'w') as f:
            json.dump(dashboard, f, indent=2, default=str)
        
        self.logger.info(f"📊 Performance report generated: {output_path}")
        return output_path
    
    def shutdown(self):
        """**Shutdown orchestrator** (tắt bộ điều phối) and cleanup resources"""
        self.logger.info("🛑 Shutting down GPU Optimization Orchestrator...")
        
        # Stop coordinator
        if self.coordinator:
            self.coordinator.stop()
        
        # Shutdown parallel executor
        self.parallel_executor.shutdown(wait=True)
        
        # Stop metrics hub
        self.metrics_hub.stop_background_logging()
        
        # Generate final report
        self.generate_performance_report()
        
        self.logger.info("✅ Orchestrator shutdown complete")


def optimize_gpu(pid: int, 
                 gpu_index: int = 0,
                 strategies: Optional[List[str]] = None,
                 config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    **Main entry point** (điểm vào chính) for GPU optimization.
    
    Convenience function that creates orchestrator and runs optimization.
    
    Args:
        pid: Process ID to optimize
        gpu_index: GPU index to use
        strategies: List of strategies to apply
        config: Optional configuration
        
    Returns:
        Optimization results dictionary
    """
    orchestrator = GPUOptimizationOrchestrator(config)
    
    try:
        results = orchestrator.optimize_gpu_for_process(pid, gpu_index, strategies)
        return results
    finally:
        orchestrator.shutdown()


# **Test function** (hàm kiểm thử)
def test_orchestrator():
    """Test the GPU Optimization Orchestrator"""
    import multiprocessing
    
    # Get current process PID
    test_pid = os.getpid()
    
    logger.info("="*60)
    logger.info("🧪 **Testing GPU Optimization Orchestrator**")
    logger.info("="*60)
    
    # Test configuration
    config = {
        'max_parallel_strategies': 3,
        'strategy_timeout': 20.0,
        'enable_profiling': True,
        'enable_coordination': True
    }
    
    # Run optimization
    results = optimize_gpu(
        pid=test_pid,
        gpu_index=0,
        strategies=['gpu_power', 'temperature', 'memory'],
        config=config
    )
    
    # Display results
    logger.info("\n📊 **Optimization Results**:")
    logger.info(f"Success: {results['success']}")
    logger.info(f"Strategies applied: {results['strategies_applied']}")
    logger.info(f"Duration: {results.get('duration', 0):.2f}s")
    
    if results.get('metrics'):
        baseline = results['metrics'].get('baseline', {})
        post = results['metrics'].get('post', {})
        
        if baseline and post:
            logger.info("\n📈 **Metrics Comparison**:")
            logger.info(f"Temperature: {baseline.get('temperature', 'N/A')}°C → "
                       f"{post.get('temperature', 'N/A')}°C")
            logger.info(f"Power: {baseline.get('power', 'N/A')}W → "
                       f"{post.get('power', 'N/A')}W")
            logger.info(f"Utilization: {baseline.get('utilization', 'N/A')}% → "
                       f"{post.get('utilization', 'N/A')}%")
    
    logger.info("="*60)
    logger.info("✅ **Test completed successfully**")
    logger.info("="*60)
    
    return results


if __name__ == "__main__":
    # Run test when executed directly
    test_orchestrator()
