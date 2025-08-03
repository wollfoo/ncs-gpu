#!/usr/bin/env python3
"""
Performance Benchmark for Hook Coordinator Fixes
Kiểm tra performance overhead và timing requirements
"""

import os
import time
import threading
import sys
from unittest.mock import MagicMock

# Mock dependencies for testing
sys.modules['psutil'] = MagicMock()
sys.modules['unified_logging'] = MagicMock()

def mock_pid_exists(pid):
    """Mock psutil.pid_exists"""
    return True

def mock_get_unified_logger(name):
    """Mock unified logger"""
    logger = MagicMock()
    return logger

# Patch the imports
import psutil
psutil.pid_exists = mock_pid_exists

try:
    from unified_logging import get_unified_logger
    get_unified_logger = mock_get_unified_logger
except:
    pass

# Now import coordinator
from coordinator import HookCoordinator


class PerformanceBenchmark:
    """Performance testing for coordinator fixes"""
    
    def __init__(self):
        self.coordinator = HookCoordinator()
        self.results = {}
    
    def cleanup_env_vars(self):
        """Clean up test environment variables"""
        env_vars_to_clean = [key for key in os.environ.keys() if key.startswith('HOOKS_READY_PID_')]
        for var in env_vars_to_clean:
            del os.environ[var]
    
    def benchmark_baseline_operations(self, num_operations=1000):
        """Benchmark baseline operations without fixes"""
        print(f"🔍 Benchmarking baseline operations ({num_operations} ops)...")
        
        test_pids = list(range(20000, 20000 + num_operations))
        self.cleanup_env_vars()
        
        start_time = time.time()
        
        for pid in test_pids:
            # Simple registration and notification (original method)
            with self.coordinator.lock:
                self.coordinator.hooks_ready[pid] = False
                self.coordinator.active_processes.add(pid)
            
            # Simple notification
            with self.coordinator.lock:
                self.coordinator.hooks_ready[pid] = True
            os.environ[f'HOOKS_READY_PID_{pid}'] = '1'
        
        baseline_time = time.time() - start_time
        
        # Cleanup
        for pid in test_pids:
            self.coordinator.cleanup_pid(pid)
        
        self.results['baseline'] = {
            'time': baseline_time,
            'ops_per_sec': num_operations / baseline_time,
            'avg_time_per_op': baseline_time / num_operations * 1000  # ms
        }
        
        print(f"✅ Baseline: {baseline_time:.4f}s, {self.results['baseline']['ops_per_sec']:.1f} ops/sec")
        return baseline_time
    
    def benchmark_enhanced_operations(self, num_operations=1000):
        """Benchmark enhanced operations with fixes"""
        print(f"🔧 Benchmarking enhanced operations ({num_operations} ops)...")
        
        test_pids = list(range(21000, 21000 + num_operations))
        self.cleanup_env_vars()
        
        start_time = time.time()
        
        for pid in test_pids:
            # Enhanced registration and notification
            self.coordinator.register_pid(pid)
            self.coordinator._sync_hooks_ready_state(pid, True)
        
        enhanced_time = time.time() - start_time
        
        # Cleanup
        for pid in test_pids:
            self.coordinator.cleanup_pid(pid)
        
        self.results['enhanced'] = {
            'time': enhanced_time,
            'ops_per_sec': num_operations / enhanced_time,
            'avg_time_per_op': enhanced_time / num_operations * 1000  # ms
        }
        
        print(f"✅ Enhanced: {enhanced_time:.4f}s, {self.results['enhanced']['ops_per_sec']:.1f} ops/sec")
        return enhanced_time
    
    def benchmark_verification_with_retry(self, num_verifications=500):
        """Benchmark verification with retry mechanism"""
        print(f"🔍 Benchmarking verification with retry ({num_verifications} verifications)...")
        
        test_pids = list(range(22000, 22000 + num_verifications))
        self.cleanup_env_vars()
        
        # Setup test data
        for pid in test_pids:
            self.coordinator.register_pid(pid)
            self.coordinator._sync_hooks_ready_state(pid, True)
        
        start_time = time.time()
        
        # Run verifications
        successful_verifications = 0
        for pid in test_pids:
            if self.coordinator.verify_hook_status(pid):
                successful_verifications += 1
        
        verification_time = time.time() - start_time
        
        # Cleanup
        for pid in test_pids:
            self.coordinator.cleanup_pid(pid)
        
        self.results['verification'] = {
            'time': verification_time,
            'ops_per_sec': num_verifications / verification_time,
            'avg_time_per_op': verification_time / num_verifications * 1000,  # ms
            'success_rate': successful_verifications / num_verifications * 100
        }
        
        print(f"✅ Verification: {verification_time:.4f}s, {self.results['verification']['ops_per_sec']:.1f} ops/sec, {self.results['verification']['success_rate']:.1f}% success")
        return verification_time
    
    def benchmark_recovery_performance(self, num_recoveries=50):
        """Benchmark recovery performance"""
        print(f"🔧 Benchmarking recovery operations ({num_recoveries} recoveries)...")
        
        test_pids = list(range(23000, 23000 + num_recoveries))
        self.cleanup_env_vars()
        
        # Setup test data with intentional issues
        for pid in test_pids:
            self.coordinator.register_pid(pid)
            # Create inconsistent state to trigger recovery
            with self.coordinator.lock:
                self.coordinator.hooks_ready[pid] = True
            # Don't set environment variable to create inconsistency
        
        start_time = time.time()
        
        successful_recoveries = 0
        for pid in test_pids:
            if self.coordinator.attempt_hook_recovery(pid):
                successful_recoveries += 1
        
        recovery_time = time.time() - start_time
        
        # Cleanup
        for pid in test_pids:
            self.coordinator.cleanup_pid(pid)
        
        self.results['recovery'] = {
            'time': recovery_time,
            'ops_per_sec': num_recoveries / recovery_time,
            'avg_time_per_op': recovery_time / num_recoveries * 1000,  # ms
            'success_rate': successful_recoveries / num_recoveries * 100
        }
        
        print(f"✅ Recovery: {recovery_time:.4f}s, {self.results['recovery']['ops_per_sec']:.1f} ops/sec, {self.results['recovery']['success_rate']:.1f}% success")
        return recovery_time
    
    def test_thread_safety(self, num_threads=10, operations_per_thread=100):
        """Test thread safety under concurrent load"""
        print(f"🧵 Testing thread safety ({num_threads} threads, {operations_per_thread} ops each)...")
        
        self.cleanup_env_vars()
        errors = []
        results = []
        
        def thread_worker(thread_id):
            try:
                pids = list(range(30000 + thread_id * 1000, 30000 + (thread_id + 1) * 1000))[:operations_per_thread]
                
                start_time = time.time()
                
                for pid in pids:
                    # Concurrent operations
                    self.coordinator.register_pid(pid)
                    self.coordinator._sync_hooks_ready_state(pid, True)
                    self.coordinator.verify_hook_status(pid)
                
                thread_time = time.time() - start_time
                results.append((thread_id, thread_time))
                
                # Cleanup
                for pid in pids:
                    self.coordinator.cleanup_pid(pid)
                    
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Start threads
        threads = []
        start_time = time.time()
        
        for i in range(num_threads):
            thread = threading.Thread(target=thread_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Analyze results
        self.results['thread_safety'] = {
            'total_time': total_time,
            'errors': len(errors),
            'threads_completed': len(results),
            'success_rate': len(results) / num_threads * 100,
            'total_operations': num_threads * operations_per_thread,
            'ops_per_sec': (num_threads * operations_per_thread) / total_time
        }
        
        if errors:
            print(f"❌ Thread safety errors: {errors}")
        else:
            print(f"✅ Thread safety: {total_time:.4f}s, {self.results['thread_safety']['ops_per_sec']:.1f} ops/sec, no errors")
        
        return len(errors) == 0
    
    def calculate_performance_overhead(self):
        """Calculate and report performance overhead"""
        if 'baseline' not in self.results or 'enhanced' not in self.results:
            print("❌ Missing baseline or enhanced results")
            return None
        
        baseline_time = self.results['baseline']['time']
        enhanced_time = self.results['enhanced']['time']
        
        overhead_percent = ((enhanced_time - baseline_time) / baseline_time) * 100
        
        self.results['overhead'] = {
            'overhead_percent': overhead_percent,
            'overhead_acceptable': overhead_percent < 5.0
        }
        
        return overhead_percent
    
    def generate_report(self):
        """Generate comprehensive performance report"""
        print("\n" + "="*80)
        print("📊 PERFORMANCE BENCHMARK REPORT")
        print("="*80)
        
        if 'baseline' in self.results and 'enhanced' in self.results:
            overhead = self.calculate_performance_overhead()
            
            print(f"🔍 BASELINE PERFORMANCE:")
            print(f"   Time: {self.results['baseline']['time']:.4f}s")
            print(f"   Ops/sec: {self.results['baseline']['ops_per_sec']:.1f}")
            print(f"   Avg time/op: {self.results['baseline']['avg_time_per_op']:.3f}ms")
            
            print(f"\n🔧 ENHANCED PERFORMANCE:")
            print(f"   Time: {self.results['enhanced']['time']:.4f}s")
            print(f"   Ops/sec: {self.results['enhanced']['ops_per_sec']:.1f}")
            print(f"   Avg time/op: {self.results['enhanced']['avg_time_per_op']:.3f}ms")
            
            print(f"\n📈 PERFORMANCE OVERHEAD:")
            print(f"   Overhead: {overhead:.2f}%")
            print(f"   Acceptable (< 5%): {'✅ YES' if overhead < 5.0 else '❌ NO'}")
        
        if 'verification' in self.results:
            print(f"\n🔍 VERIFICATION PERFORMANCE:")
            print(f"   Time: {self.results['verification']['time']:.4f}s")
            print(f"   Ops/sec: {self.results['verification']['ops_per_sec']:.1f}")
            print(f"   Success rate: {self.results['verification']['success_rate']:.1f}%")
            print(f"   Avg time/op: {self.results['verification']['avg_time_per_op']:.3f}ms")
        
        if 'recovery' in self.results:
            print(f"\n🔧 RECOVERY PERFORMANCE:")
            print(f"   Time: {self.results['recovery']['time']:.4f}s")
            print(f"   Ops/sec: {self.results['recovery']['ops_per_sec']:.1f}")
            print(f"   Success rate: {self.results['recovery']['success_rate']:.1f}%")
            print(f"   Avg time/op: {self.results['recovery']['avg_time_per_op']:.3f}ms")
            print(f"   Recovery time acceptable (< 2s): {'✅ YES' if self.results['recovery']['avg_time_per_op'] < 2000 else '❌ NO'}")
        
        if 'thread_safety' in self.results:
            print(f"\n🧵 THREAD SAFETY:")
            print(f"   Total time: {self.results['thread_safety']['total_time']:.4f}s")
            print(f"   Errors: {self.results['thread_safety']['errors']}")
            print(f"   Success rate: {self.results['thread_safety']['success_rate']:.1f}%")
            print(f"   Ops/sec: {self.results['thread_safety']['ops_per_sec']:.1f}")
            print(f"   Thread safe: {'✅ YES' if self.results['thread_safety']['errors'] == 0 else '❌ NO'}")
        
        print("\n" + "="*80)
        print("📋 REQUIREMENT COMPLIANCE:")
        
        # Check requirements
        requirements_met = []
        
        if 'overhead' in self.results:
            req_overhead = self.results['overhead']['overhead_acceptable']
            requirements_met.append(f"Performance overhead < 5%: {'✅' if req_overhead else '❌'}")
        
        if 'recovery' in self.results:
            req_recovery_time = self.results['recovery']['avg_time_per_op'] < 2000
            requirements_met.append(f"Recovery time < 2s: {'✅' if req_recovery_time else '❌'}")
        
        if 'thread_safety' in self.results:
            req_thread_safety = self.results['thread_safety']['errors'] == 0
            requirements_met.append(f"Thread safety: {'✅' if req_thread_safety else '❌'}")
        
        for requirement in requirements_met:
            print(f"   {requirement}")
        
        print("="*80)
        
        return self.results


def main():
    """Main benchmark execution"""
    print("🚀 Starting Hook Coordinator Fixes Performance Benchmark")
    print("="*80)
    
    benchmark = PerformanceBenchmark()
    
    try:
        # Run benchmarks
        benchmark.benchmark_baseline_operations(500)
        benchmark.benchmark_enhanced_operations(500)
        benchmark.benchmark_verification_with_retry(200)
        benchmark.benchmark_recovery_performance(20)
        benchmark.test_thread_safety(5, 50)
        
        # Generate final report
        results = benchmark.generate_report()
        
        print("\n🎯 BENCHMARK COMPLETED SUCCESSFULLY")
        
        return results
        
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    main()