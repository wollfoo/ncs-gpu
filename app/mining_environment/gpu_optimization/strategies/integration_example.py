#!/usr/bin/env python3
"""
Integration Example - GPU Optimization Strategies with Orchestrator
Ví dụ tích hợp các chiến lược tối ưu GPU với hệ thống điều phối

This example demonstrates how to integrate the GPU optimization strategies
with an orchestrator and monitoring system in a production environment.
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json
from pathlib import Path

# Import strategies modules
from base import (
    StrategyContext, 
    StrategyResult, 
    StrategyType,
    Priority
)
from selector import StrategySelector, SelectionMode
from balanced import BalancedStrategy
from aggressive import AggressiveStrategy
from cloak import CloakStrategy
from parallel_executor import (
    ParallelExecutor,
    ExecutionMode,
    ParallelConfig,
    execute_strategies_parallel
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class OrchestrationConfig:
    """Configuration for orchestration (Cấu hình điều phối)"""
    max_concurrent_strategies: int = 3
    monitoring_interval: float = 5.0  # seconds
    auto_adjust: bool = True
    save_metrics: bool = True
    metrics_path: Path = Path("./metrics")


class GPUOptimizationOrchestrator:
    """
    GPU Optimization Orchestrator (Bộ điều phối tối ưu GPU)
    
    Coordinates strategy selection, execution, and monitoring.
    """
    
    def __init__(self, config: OrchestrationConfig):
        self.config = config
        self.selector = StrategySelector(mode=SelectionMode.AUTOMATIC)
        self.executor = ParallelExecutor(
            config=ParallelConfig(
                mode=ExecutionMode.THREAD,
                max_workers=config.max_concurrent_strategies
            )
        )
        
        # Register available strategies
        self._register_strategies()
        
        # Monitoring state
        self.is_running = False
        self.metrics_history: List[Dict[str, Any]] = []
        
        # Ensure metrics directory exists
        if config.save_metrics:
            config.metrics_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized Orchestrator [concurrent={config.max_concurrent_strategies}]")
    
    def _register_strategies(self):
        """Register all available strategies (Đăng ký các chiến lược)"""
        self.selector.register_strategy(StrategyType.BALANCED, BalancedStrategy)
        self.selector.register_strategy(StrategyType.AGGRESSIVE, AggressiveStrategy)
        self.selector.register_strategy(StrategyType.CLOAK, CloakStrategy)
        logger.info(f"Registered {len(self.selector.available_strategies)} strategies")
    
    def _create_mock_context(self, gpu_id: int = 0) -> StrategyContext:
        """Create mock context for demonstration (Tạo context giả để demo)"""
        import random
        
        return StrategyContext(
            pid=12345,
            gpu_id=gpu_id,
            gpu_metrics={
                'utilization': random.uniform(30, 95),
                'memory_used': random.uniform(1000, 8000),
                'memory_total': 8192,
                'temperature': random.uniform(50, 85),
                'power_draw': random.uniform(100, 300),
                'fan_speed': random.uniform(30, 100)
            },
            system_metrics={
                'cpu_percent': random.uniform(20, 80),
                'memory_mb': random.randint(500, 2000),
                'num_threads': random.randint(4, 16),
                'runtime_seconds': random.uniform(100, 10000),
                'total_processes': random.randint(50, 200),
                'gpu_processes': random.randint(1, 10),
                'available_memory': random.uniform(4000, 16000),
                'load_average': random.uniform(0.5, 4.0)
            },
            constraints={
                'max_temperature': 85,
                'max_power': 350,
                'min_utilization': 30
            },
            metadata={
                'node_id': f'node-{gpu_id}',
                'timestamp': time.time()
            }
        )
    
    async def optimize_single_gpu(self, gpu_id: int) -> StrategyResult:
        """
        Optimize single GPU (Tối ưu GPU đơn)
        
        Args:
            gpu_id: GPU identifier
            
        Returns:
            Strategy execution result
        """
        # Create context
        context = self._create_mock_context(gpu_id)
        
        # Select best strategy
        selected_type = self.selector.select_strategy(context)
        if not selected_type:
            logger.warning(f"No strategy selected for GPU {gpu_id}")
            return StrategyResult(
                success=False,
                message=f"No suitable strategy for GPU {gpu_id}"
            )
        
        logger.info(f"Selected {selected_type.name} strategy for GPU {gpu_id}")
        
        # Get strategy class and create instance
        strategy_class = self.selector.available_strategies[selected_type]
        strategy = strategy_class()
        
        # Execute strategy
        result = await self._execute_strategy_async(strategy, context)
        
        # Update selector with performance feedback
        self.selector.update_performance(selected_type, result)
        
        # Record metrics
        self._record_metrics(gpu_id, selected_type, result)
        
        return result
    
    async def _execute_strategy_async(self, 
                                     strategy,
                                     context: StrategyContext) -> StrategyResult:
        """Execute strategy asynchronously (Thực thi chiến lược bất đồng bộ)"""
        loop = asyncio.get_event_loop()
        
        # Run in executor to avoid blocking
        result = await loop.run_in_executor(
            None,
            strategy.apply,
            context
        )
        
        return result
    
    def _record_metrics(self, 
                       gpu_id: int,
                       strategy_type: StrategyType,
                       result: StrategyResult):
        """Record metrics for monitoring (Ghi lại metrics để giám sát)"""
        metric = {
            'timestamp': time.time(),
            'gpu_id': gpu_id,
            'strategy': strategy_type.name,
            'success': result.success,
            'duration': result.duration,
            'metrics_after': result.metrics_after
        }
        
        self.metrics_history.append(metric)
        
        # Save to file if configured
        if self.config.save_metrics:
            self._save_metrics()
    
    def _save_metrics(self):
        """Save metrics to file (Lưu metrics ra file)"""
        filepath = self.config.metrics_path / f"metrics_{int(time.time())}.json"
        
        try:
            with open(filepath, 'w') as f:
                json.dump(self.metrics_history[-100:], f, indent=2)  # Keep last 100
            logger.debug(f"Saved metrics to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    async def optimize_multiple_gpus(self, gpu_ids: List[int]) -> List[StrategyResult]:
        """
        Optimize multiple GPUs concurrently (Tối ưu nhiều GPU đồng thời)
        
        Args:
            gpu_ids: List of GPU identifiers
            
        Returns:
            List of execution results
        """
        logger.info(f"Starting optimization for {len(gpu_ids)} GPUs")
        
        # Create tasks for each GPU
        tasks = [
            self.optimize_single_gpu(gpu_id)
            for gpu_id in gpu_ids
        ]
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful = sum(1 for r in results if isinstance(r, StrategyResult) and r.success)
        logger.info(f"Optimization complete: {successful}/{len(gpu_ids)} successful")
        
        return results
    
    async def monitor_and_optimize(self, gpu_ids: List[int], duration: float = 60.0):
        """
        Monitor and continuously optimize (Giám sát và tối ưu liên tục)
        
        Args:
            gpu_ids: GPUs to monitor
            duration: Total monitoring duration in seconds
        """
        self.is_running = True
        start_time = time.time()
        iteration = 0
        
        logger.info(f"Starting monitoring for {duration} seconds")
        
        try:
            while self.is_running and (time.time() - start_time) < duration:
                iteration += 1
                logger.info(f"\n=== Optimization Iteration {iteration} ===")
                
                # Optimize all GPUs
                results = await self.optimize_multiple_gpus(gpu_ids)
                
                # Print summary
                self._print_summary(results)
                
                # Wait before next iteration
                await asyncio.sleep(self.config.monitoring_interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")
        finally:
            self.is_running = False
            await self.cleanup()
    
    def _print_summary(self, results: List[StrategyResult]):
        """Print optimization summary (In tóm tắt tối ưu)"""
        successful = sum(1 for r in results if isinstance(r, StrategyResult) and r.success)
        
        print("\n📊 Optimization Summary:")
        print(f"  • Total GPUs: {len(results)}")
        print(f"  • Successful: {successful}")
        print(f"  • Failed: {len(results) - successful}")
        
        if self.metrics_history:
            recent = self.metrics_history[-len(results):]
            avg_duration = sum(m['duration'] for m in recent) / len(recent)
            print(f"  • Avg Duration: {avg_duration:.3f}s")
    
    async def cleanup(self):
        """Cleanup resources (Dọn dẹp tài nguyên)"""
        logger.info("Cleaning up orchestrator resources")
        
        # Stop executor
        self.executor.stop()
        
        # Save final metrics
        if self.config.save_metrics and self.metrics_history:
            self._save_metrics()
        
        # Export selector statistics
        stats_file = self.config.metrics_path / "selector_stats.json"
        self.selector.export_statistics(stats_file)
        
        logger.info("Cleanup complete")


async def run_demonstration():
    """Run demonstration of integrated system (Chạy demo hệ thống tích hợp)"""
    print("\n" + "="*60)
    print("GPU Optimization Strategies - Integration Demo")
    print("="*60)
    
    # Create orchestrator
    config = OrchestrationConfig(
        max_concurrent_strategies=3,
        monitoring_interval=3.0,
        auto_adjust=True,
        save_metrics=True
    )
    
    orchestrator = GPUOptimizationOrchestrator(config)
    
    # Demo 1: Single GPU optimization
    print("\n📍 Demo 1: Single GPU Optimization")
    result = await orchestrator.optimize_single_gpu(gpu_id=0)
    print(f"  Result: {'✅ Success' if result.success else '❌ Failed'}")
    print(f"  Message: {result.message}")
    print(f"  Duration: {result.duration:.3f}s")
    
    # Demo 2: Multiple GPU optimization
    print("\n📍 Demo 2: Multiple GPU Optimization (4 GPUs)")
    gpu_ids = [0, 1, 2, 3]
    results = await orchestrator.optimize_multiple_gpus(gpu_ids)
    orchestrator._print_summary(results)
    
    # Demo 3: Continuous monitoring (short duration for demo)
    print("\n📍 Demo 3: Continuous Monitoring (15 seconds)")
    await orchestrator.monitor_and_optimize(gpu_ids, duration=15.0)
    
    # Print final statistics
    print("\n📈 Final Statistics:")
    print(f"  • Total optimizations: {len(orchestrator.metrics_history)}")
    print(f"  • Strategies used: {len(orchestrator.selector.available_strategies)}")
    
    # Get recommendation for current state
    context = orchestrator._create_mock_context(0)
    recommendation = orchestrator.selector.get_recommendation(context)
    print(f"\n💡 Current Recommendation:")
    print(f"  • Strategy: {recommendation['recommended']}")
    print(f"  • Confidence: {recommendation['confidence']:.1f}%")
    print(f"  • Mode: {recommendation['mode']}")


def main():
    """Main entry point"""
    try:
        # Run async demonstration
        asyncio.run(run_demonstration())
        
        print("\n✅ Integration demonstration completed successfully!")
        
    except Exception as e:
        logger.error(f"Demonstration failed: {e}")
        raise


if __name__ == "__main__":
    main()
