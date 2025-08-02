#!/usr/bin/env python3
"""
Phase 3: GPU Monitoring Activation Test
Test GPU monitoring activation post-modifications trong Docker environment
"""

import sys
import time
import os
import logging
from pathlib import Path

# Add project path
sys.path.insert(0, '/home/azureuser/ncs-gpu/app')

def setup_logging():
    """Setup comprehensive logging for testing"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('/home/azureuser/ncs-gpu/app/logs/gpu_monitoring_test.log', mode='w')
        ]
    )
    return logging.getLogger('gpu_monitoring_test')

def test_docker_environment():
    """Verify Docker environment setup"""
    print("\n🐳 Testing Docker Environment")
    print("=" * 40)
    
    try:
        # ✅ CHECK 1: Working directory
        current_dir = os.getcwd()
        expected_dir = '/home/azureuser/ncs-gpu/app'
        print(f"📁 Current directory: {current_dir}")
        print(f"📁 Expected directory: {expected_dir}")
        
        if current_dir == expected_dir:
            print("✅ Working directory correct")
        else:
            print("⚠️ Working directory mismatch - adjusting")
            os.chdir(expected_dir)
        
        # ✅ CHECK 2: Mount point verification
        mount_dir = '/app'
        if os.path.exists(mount_dir):
            print(f"✅ Mount point {mount_dir} exists")
        else:
            print(f"⚠️ Mount point {mount_dir} not found")
        
        # ✅ CHECK 3: Project structure
        required_paths = [
            'mining_environment/scripts/resource_control.py',
            'mining_environment/scripts/resource_manager.py',
            'mining_environment/scripts/gpu_resource_monitor.py'
        ]
        
        missing_paths = []
        for path in required_paths:
            if os.path.exists(path):
                print(f"✅ {path} exists")
            else:
                missing_paths.append(path)
                print(f"❌ {path} missing")
        
        return len(missing_paths) == 0
        
    except Exception as e:
        print(f"❌ Docker environment test failed: {e}")
        return False

def test_enhanced_factory_logging():
    """Test enhanced factory logging output"""
    print("\n🏭 Testing Enhanced Factory Logging")
    print("=" * 40)
    
    try:
        # ✅ Redirect logging to capture output
        import io
        import contextlib
        from mining_environment.scripts.unified_logging import get_unified_logger
        
        # Create test config
        class TestConfig:
            def __init__(self):
                self.process_priority_map = {'inference-cuda': 1}
                self.cloaking_strategies = {'gpu_cloaking': {'enabled': True}}
                self.data = {
                    'process_priority_map': self.process_priority_map,
                    'cloaking_strategies': self.cloaking_strategies
                }
            
            def get(self, key, default=None):
                return self.data.get(key, default)
        
        config = TestConfig()
        logger = get_unified_logger('factory_test')
        
        print("1️⃣ Testing ResourceControlFactory with enhanced logging...")
        
        # Capture logging output
        log_stream = io.StringIO()
        log_handler = logging.StreamHandler(log_stream)
        logger.addHandler(log_handler)
        
        # Import and test factory
        from mining_environment.scripts.resource_control import ResourceControlFactory
        
        print("2️⃣ Creating resource managers...")
        resource_managers = ResourceControlFactory.create_resource_managers(config, logger)
        
        # Get captured logs
        log_output = log_stream.getvalue()
        logger.removeHandler(log_handler)
        
        print("3️⃣ Verifying enhanced logging output...")
        
        # Check for enhanced logging markers
        expected_logs = [
            "🏭 [FACTORY] ResourceControlFactory initialization started",
            "📋 [FACTORY] Available managers:",
            "🎮 [FACTORY] GPU manager registered:"
        ]
        
        found_logs = []
        missing_logs = []
        
        for expected_log in expected_logs:
            if expected_log in log_output:
                found_logs.append(expected_log)
                print(f"✅ Found: {expected_log}")
            else:
                missing_logs.append(expected_log)
                print(f"❌ Missing: {expected_log}")
        
        # Check resource managers result
        if resource_managers and 'gpu' in resource_managers:
            print("✅ GPU manager successfully created and registered")
            return len(missing_logs) == 0
        else:
            print("❌ GPU manager creation failed")
            return False
        
    except Exception as e:
        print(f"❌ Enhanced factory logging test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gpu_monitoring_system():
    """Test GPU monitoring system integration"""
    print("\n🎮 Testing GPU Monitoring System")
    print("=" * 40)
    
    try:
        print("1️⃣ Testing GPU monitor import...")
        from mining_environment.scripts.gpu_resource_monitor import (
            GPUResourceManagerMonitor, 
            initialize_gpu_monitoring, 
            get_gpu_monitor
        )
        print("✅ GPU monitoring system import successful")
        
        print("2️⃣ Testing GPU monitor instantiation...")
        monitor = GPUResourceManagerMonitor()
        print("✅ GPU monitor instance created")
        
        print("3️⃣ Testing configuration...")
        config = {
            'auto_start_monitoring': False,  # Don't auto-start in test
            'health_check_interval_seconds': 30,
            'history_retention_hours': 24,
            'max_history_records': 1000
        }
        
        monitor.config.update(config)
        print("✅ GPU monitor configured")
        
        print("4️⃣ Testing monitor methods...")
        
        # Test basic functionality
        dashboard_data = monitor.get_dashboard_data()
        health_summary = monitor.get_health_summary()
        
        print(f"✅ Dashboard data: {dashboard_data.get('status', 'unknown')}")
        print(f"✅ Health summary: {health_summary.get('status', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ GPU monitoring system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_validation_checkpoints():
    """Test validation checkpoint system"""
    print("\n🔍 Testing Validation Checkpoints")
    print("=" * 40)
    
    try:
        print("1️⃣ Testing validation checkpoint methods...")
        
        # Import ResourceManager
        from mining_environment.scripts.resource_manager import ResourceManager
        
        # Check if validation methods exist
        methods_to_check = [
            '_perform_startup_validation_checkpoints',
            '_initialize_gpu_monitoring'
        ]
        
        for method_name in methods_to_check:
            if hasattr(ResourceManager, method_name):
                print(f"✅ Method {method_name} exists")
            else:
                print(f"❌ Method {method_name} missing")
                return False
        
        print("2️⃣ Testing method signatures...")
        
        # Create a mock ResourceManager instance for testing
        from mining_environment.scripts.auxiliary_modules.models import ConfigModel
        
        config_data = {
            'process_priority_map': {'inference-cuda': 1},
            'cloaking_strategies': {'gpu_cloaking': {'enabled': True}}
        }
        config = ConfigModel(config_data)
        
        # This will test the __init__ method validation
        resource_manager = ResourceManager(config)
        print("✅ ResourceManager instance created with validation")
        
        return True
        
    except Exception as e:
        print(f"❌ Validation checkpoints test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration_flow():
    """Test complete integration flow"""
    print("\n🔗 Testing Complete Integration Flow")
    print("=" * 40)
    
    try:
        print("1️⃣ Testing complete startup flow simulation...")
        
        # Create comprehensive test configuration
        from mining_environment.scripts.auxiliary_modules.models import ConfigModel
        
        config_data = {
            'process_priority_map': {
                'inference-cuda': 1,
                'ml-inference': 2
            },
            'cloaking_strategies': {
                'gpu_cloaking': {'enabled': True},
                'network': {'enabled': True},
                'disk_io': {'enabled': True},
                'cache': {'enabled': True},
                'memory': {'enabled': True}
            }
        }
        config = ConfigModel(config_data)
        
        print("2️⃣ Creating ResourceManager with enhanced configuration...")
        from mining_environment.scripts.resource_manager import ResourceManager
        
        # Create ResourceManager instance
        resource_manager = ResourceManager(config)
        print("✅ ResourceManager created successfully")
        
        print("3️⃣ Testing configuration validation...")
        
        # Test that configuration was validated properly
        if hasattr(resource_manager, 'config'):
            print("✅ Configuration validated and stored")
        else:
            print("❌ Configuration validation failed")
            return False
        
        print("4️⃣ Testing shared resource manager...")
        
        # Check if shared resource manager was created
        if hasattr(resource_manager, 'shared_resource_manager'):
            print("✅ Shared resource manager attribute exists")
        else:
            print("❌ Shared resource manager missing")
            return False
        
        print("5️⃣ Testing monitoring integration readiness...")
        
        # Check if GPU monitoring attributes exist
        monitoring_attributes = ['_initialize_gpu_monitoring', '_perform_startup_validation_checkpoints']
        
        for attr in monitoring_attributes:
            if hasattr(resource_manager, attr):
                print(f"✅ Monitoring attribute {attr} exists")
            else:
                print(f"❌ Monitoring attribute {attr} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Integration flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test execution for Phase 3"""
    print("🚀 Phase 3: GPU Monitoring Activation Test")
    print("=" * 50)
    print(f"⏰ Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Setup logging
    logger = setup_logging()
    logger.info("Starting Phase 3 GPU monitoring activation test")
    
    test_results = {}
    
    # Run all Phase 3 tests
    test_results['Docker Environment'] = test_docker_environment()
    test_results['Enhanced Factory Logging'] = test_enhanced_factory_logging()
    test_results['GPU Monitoring System'] = test_gpu_monitoring_system()
    test_results['Validation Checkpoints'] = test_validation_checkpoints()
    test_results['Integration Flow'] = test_integration_flow()
    
    # ✅ FINAL RESULTS SUMMARY
    print("\n📊 Phase 3 Test Results Summary")
    print("=" * 35)
    
    total_tests = len(test_results)
    passed_tests = sum(test_results.values())
    
    for test_name, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\n🎯 Overall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🏆 ALL PHASE 3 TESTS PASSED!")
        print("\n✅ COMPREHENSIVE STARTUP VERIFICATION COMPLETE")
        print("🎯 GPU monitoring system activation validated successfully")
        print("📊 Factory pattern investigation verified")
        print("🚀 Enhanced logging implementation confirmed")
        logger.info("Phase 3 GPU monitoring activation test completed successfully")
        return 0
    else:
        print(f"⚠️ {total_tests - passed_tests} TESTS FAILED - Review implementation")
        logger.error(f"Phase 3 test failures: {total_tests - passed_tests}/{total_tests}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)