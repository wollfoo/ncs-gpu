#!/usr/bin/env python3
"""
Integration Test for Hook Coordinator Fixes
Kiểm tra tính năng và integration với existing system
"""

import os
import time
import threading
import sys
from unittest.mock import MagicMock

# Mock dependencies
sys.modules['psutil'] = MagicMock()
sys.modules['unified_logging'] = MagicMock()

def mock_pid_exists(pid):
    return True

def mock_get_unified_logger(name):
    logger = MagicMock()
    return logger

import psutil
psutil.pid_exists = mock_pid_exists

# Import coordinator
from coordinator import HookCoordinator


class IntegrationTest:
    """Integration test suite để verify coordinator fixes"""
    
    def __init__(self):
        self.coordinator = HookCoordinator()
        self.test_results = {}
    
    def cleanup_env_vars(self):
        """Clean environment variables"""
        env_vars_to_clean = [key for key in os.environ.keys() if key.startswith('HOOKS_READY_PID_')]
        for var in env_vars_to_clean:
            del os.environ[var]
    
    def test_hook_coordination_scenario(self):
        """Test typical mining scenario with multiple processes"""
        print("🔍 Testing hook coordination scenario...")
        
        mining_pids = [1001, 1002, 1003, 1004]
        self.cleanup_env_vars()
        
        try:
            # Step 1: Register mining processes
            for pid in mining_pids:
                self.coordinator.register_pid(pid)
            
            print(f"✅ Registered {len(mining_pids)} mining processes")
            
            # Step 2: Simulate hook ready notifications
            for i, pid in enumerate(mining_pids):
                if i < 3:  # First 3 processes become ready
                    self.coordinator.notify_hooks_ready(pid)
            
            # Step 3: Check status
            ready_count = 0
            for pid in mining_pids:
                if self.coordinator.check_hooks_ready(pid):
                    ready_count += 1
            
            print(f"✅ {ready_count}/{len(mining_pids)} processes ready")
            
            # Step 4: Test verification
            verification_results = {}
            for pid in mining_pids:
                verification_results[pid] = self.coordinator.verify_hook_status(pid)
            
            successful_verifications = sum(verification_results.values())
            print(f"✅ {successful_verifications}/{len(mining_pids)} verifications successful")
            
            # Step 5: Test consistency
            consistency_check = True
            for pid in mining_pids:
                internal_state = self.coordinator.hooks_ready.get(pid, False)
                env_var = f'HOOKS_READY_PID_{pid}'
                env_state = os.environ.get(env_var) == '1'
                
                if internal_state != env_state:
                    consistency_check = False
                    print(f"❌ Inconsistency detected for PID {pid}: internal={internal_state}, env={env_state}")
            
            if consistency_check:
                print("✅ All states consistent")
            
            # Cleanup
            for pid in mining_pids:
                self.coordinator.cleanup_pid(pid)
            
            self.test_results['hook_coordination'] = {
                'processes_registered': len(mining_pids),
                'processes_ready': ready_count,
                'verifications_successful': successful_verifications,
                'state_consistent': consistency_check,
                'success': ready_count >= 3 and successful_verifications >= 3 and consistency_check
            }
            
            return self.test_results['hook_coordination']['success']
            
        except Exception as e:
            print(f"❌ Hook coordination test failed: {e}")
            self.test_results['hook_coordination'] = {'success': False, 'error': str(e)}
            return False
    
    def test_race_condition_fix(self):
        """Test race condition fix with concurrent operations"""
        print("🧵 Testing race condition fix...")
        
        test_pid = 2001
        self.cleanup_env_vars()
        errors = []
        
        try:
            self.coordinator.register_pid(test_pid)
            
            def concurrent_operation(operation_id):
                try:
                    for i in range(10):
                        # Alternate between ready and not ready
                        if i % 2 == 0:
                            self.coordinator._sync_hooks_ready_state(test_pid, True)
                        else:
                            self.coordinator._sync_hooks_ready_state(test_pid, False)
                        
                        # Verify state
                        self.coordinator.verify_hook_status(test_pid)
                        
                        time.sleep(0.001)  # Small delay
                        
                except Exception as e:
                    errors.append(f"Thread {operation_id}: {e}")
            
            # Run concurrent operations
            threads = []
            for i in range(5):
                thread = threading.Thread(target=concurrent_operation, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join()
            
            # Final state check
            internal_state = self.coordinator.hooks_ready.get(test_pid, False)
            env_var = f'HOOKS_READY_PID_{test_pid}'
            env_state = os.environ.get(env_var) == '1'
            final_consistency = (internal_state == env_state)
            
            print(f"✅ Concurrent operations completed with {len(errors)} errors")
            print(f"✅ Final state consistency: {final_consistency}")
            
            # Cleanup
            self.coordinator.cleanup_pid(test_pid)
            
            self.test_results['race_condition'] = {
                'errors': len(errors),
                'final_consistency': final_consistency,
                'success': len(errors) == 0 and final_consistency
            }
            
            return self.test_results['race_condition']['success']
            
        except Exception as e:
            print(f"❌ Race condition test failed: {e}")
            self.test_results['race_condition'] = {'success': False, 'error': str(e)}
            return False
    
    def test_recovery_mechanism(self):
        """Test recovery mechanism effectiveness"""
        print("🔧 Testing recovery mechanism...")
        
        test_pid = 3001
        self.cleanup_env_vars()
        
        try:
            # Setup process with inconsistent state
            self.coordinator.register_pid(test_pid)
            
            # Create inconsistency manually
            with self.coordinator.lock:
                self.coordinator.hooks_ready[test_pid] = True
            # Don't set environment variable to create inconsistency
            
            print("✅ Created intentional state inconsistency")
            
            # Verify inconsistency is detected
            verification_before = self.coordinator.verify_hook_status(test_pid)
            print(f"✅ Inconsistency detected: {not verification_before}")
            
            # Attempt recovery
            recovery_start = time.time()
            recovery_success = self.coordinator.attempt_hook_recovery(test_pid)
            recovery_time = time.time() - recovery_start
            
            print(f"✅ Recovery attempt: {'SUCCESS' if recovery_success else 'FAILED'}")
            print(f"✅ Recovery time: {recovery_time*1000:.1f}ms")
            
            # Verify recovery
            if recovery_success:
                verification_after = self.coordinator.verify_hook_status(test_pid)
                print(f"✅ Post-recovery verification: {'SUCCESS' if verification_after else 'FAILED'}")
                
                # Check final consistency
                internal_state = self.coordinator.hooks_ready.get(test_pid, False)
                env_var = f'HOOKS_READY_PID_{test_pid}'
                env_state = os.environ.get(env_var) == '1'
                final_consistency = (internal_state == env_state)
                
                print(f"✅ Final state consistency: {final_consistency}")
            else:
                verification_after = False
                final_consistency = False
            
            # Cleanup
            self.coordinator.cleanup_pid(test_pid)
            
            self.test_results['recovery'] = {
                'inconsistency_detected': not verification_before,
                'recovery_successful': recovery_success,
                'recovery_time_ms': recovery_time * 1000,
                'post_recovery_verification': verification_after,
                'final_consistency': final_consistency,
                'success': recovery_success and verification_after and final_consistency and recovery_time < 2.0
            }
            
            return self.test_results['recovery']['success']
            
        except Exception as e:
            print(f"❌ Recovery test failed: {e}")
            self.test_results['recovery'] = {'success': False, 'error': str(e)}
            return False
    
    def test_backward_compatibility(self):
        """Test backward compatibility with existing functionality"""
        print("🔄 Testing backward compatibility...")
        
        test_pid = 4001
        self.cleanup_env_vars()
        
        try:
            # Test original interface methods still work
            
            # Original registration
            self.coordinator.register_pid(test_pid)
            print("✅ register_pid() works")
            
            # Original notification
            self.coordinator.notify_hooks_ready(test_pid)
            print("✅ notify_hooks_ready() works")
            
            # Original check
            is_ready = self.coordinator.check_hooks_ready(test_pid)
            print(f"✅ check_hooks_ready() returns: {is_ready}")
            
            # Original wait (with short timeout)
            wait_result = self.coordinator.wait_for_hooks_ready(test_pid, timeout=1)
            print(f"✅ wait_for_hooks_ready() returns: {wait_result}")
            
            # Original cleanup
            self.coordinator.cleanup_pid(test_pid)
            print("✅ cleanup_pid() works")
            
            # Verify cleanup was complete
            is_ready_after_cleanup = self.coordinator.check_hooks_ready(test_pid)
            env_var_exists = f'HOOKS_READY_PID_{test_pid}' in os.environ
            
            print(f"✅ Post-cleanup state: ready={is_ready_after_cleanup}, env_var={env_var_exists}")
            
            self.test_results['backward_compatibility'] = {
                'all_methods_work': True,
                'cleanup_complete': not is_ready_after_cleanup and not env_var_exists,
                'success': True
            }
            
            return True
            
        except Exception as e:
            print(f"❌ Backward compatibility test failed: {e}")
            self.test_results['backward_compatibility'] = {'success': False, 'error': str(e)}
            return False
    
    def test_performance_acceptable(self):
        """Test performance is acceptable for production"""
        print("⚡ Testing performance acceptability...")
        
        num_operations = 100
        test_pids = list(range(5000, 5000 + num_operations))
        self.cleanup_env_vars()
        
        try:
            # Test notification performance
            start_time = time.time()
            for pid in test_pids:
                self.coordinator.register_pid(pid)
                self.coordinator.notify_hooks_ready(pid)
            notification_time = time.time() - start_time
            
            # Test verification performance  
            start_time = time.time()
            for pid in test_pids:
                self.coordinator.verify_hook_status(pid)
            verification_time = time.time() - start_time
            
            # Cleanup
            for pid in test_pids:
                self.coordinator.cleanup_pid(pid)
            
            # Performance metrics
            avg_notification_time = (notification_time / num_operations) * 1000  # ms
            avg_verification_time = (verification_time / num_operations) * 1000  # ms
            
            print(f"✅ Avg notification time: {avg_notification_time:.3f}ms")
            print(f"✅ Avg verification time: {avg_verification_time:.3f}ms")
            
            # Performance acceptable if under reasonable thresholds
            notification_acceptable = avg_notification_time < 5.0  # 5ms per operation
            verification_acceptable = avg_verification_time < 2.0  # 2ms per operation
            
            print(f"✅ Notification performance acceptable: {notification_acceptable}")
            print(f"✅ Verification performance acceptable: {verification_acceptable}")
            
            self.test_results['performance'] = {
                'avg_notification_time_ms': avg_notification_time,
                'avg_verification_time_ms': avg_verification_time,
                'notification_acceptable': notification_acceptable,
                'verification_acceptable': verification_acceptable,
                'success': notification_acceptable and verification_acceptable
            }
            
            return self.test_results['performance']['success']
            
        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            self.test_results['performance'] = {'success': False, 'error': str(e)}
            return False
    
    def generate_integration_report(self):
        """Generate comprehensive integration test report"""
        print("\n" + "="*80)
        print("📋 INTEGRATION TEST REPORT")
        print("="*80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get('success', False))
        
        print(f"📊 OVERALL RESULTS: {passed_tests}/{total_tests} tests passed")
        print()
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result.get('success', False) else "❌ FAIL"
            print(f"{status} {test_name.upper().replace('_', ' ')}")
            
            if 'error' in result:
                print(f"   Error: {result['error']}")
            else:
                # Print key metrics
                for key, value in result.items():
                    if key != 'success' and not key.endswith('_ms'):
                        print(f"   {key}: {value}")
        
        print("\n" + "="*80)
        print("🎯 CRITICAL REQUIREMENTS CHECK:")
        
        # Check critical requirements
        requirements = [
            ("Functionality", self.test_results.get('hook_coordination', {}).get('success', False)),
            ("Race Condition Fix", self.test_results.get('race_condition', {}).get('success', False)),
            ("Recovery Mechanism", self.test_results.get('recovery', {}).get('success', False)),
            ("Backward Compatibility", self.test_results.get('backward_compatibility', {}).get('success', False)),
            ("Performance Acceptable", self.test_results.get('performance', {}).get('success', False))
        ]
        
        all_critical_passed = True
        for req_name, req_passed in requirements:
            status = "✅" if req_passed else "❌"
            print(f"   {status} {req_name}")
            if not req_passed:
                all_critical_passed = False
        
        print("="*80)
        
        if all_critical_passed:
            print("🎉 ALL CRITICAL REQUIREMENTS MET - READY FOR PRODUCTION")
        else:
            print("⚠️  SOME REQUIREMENTS NOT MET - NEEDS ATTENTION")
        
        print("="*80)
        
        return all_critical_passed


def main():
    """Main integration test execution"""
    print("🚀 Starting Hook Coordinator Integration Tests")
    print("="*80)
    
    test_suite = IntegrationTest()
    
    # Run all tests
    tests = [
        test_suite.test_hook_coordination_scenario,
        test_suite.test_race_condition_fix,
        test_suite.test_recovery_mechanism,
        test_suite.test_backward_compatibility,
        test_suite.test_performance_acceptable
    ]
    
    for test in tests:
        try:
            print()
            test()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    # Generate report
    success = test_suite.generate_integration_report()
    
    return success


if __name__ == '__main__':
    success = main()
    if success:
        print("\n🎯 INTEGRATION TESTS COMPLETED SUCCESSFULLY")
        exit(0)
    else:
        print("\n❌ INTEGRATION TESTS FAILED")
        exit(1)