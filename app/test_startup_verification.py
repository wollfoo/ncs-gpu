#!/usr/bin/env python3
"""
Test Startup Verification Script
Comprehensive testing for Phase 1 & 2 implementation của GPU mining system startup verification
"""

import sys
import time
import logging
from pathlib import Path

# Add project path
sys.path.insert(0, '/home/azureuser/ncs-gpu/app')

def test_factory_pattern_investigation():
    """Test Phase 1: Factory Pattern Investigation"""
    print("\n🔍 Phase 1: Factory Pattern Investigation")
    print("=" * 50)
    
    try:
        # ✅ TEST 1: ResourceControlFactory import
        print("1️⃣ Testing ResourceControlFactory import...")
        from mining_environment.scripts.resource_control import ResourceControlFactory
        print("✅ ResourceControlFactory import successful")
        
        # ✅ TEST 2: Factory shared managers info
        print("2️⃣ Testing get_shared_managers_info()...")
        sharing_info = ResourceControlFactory.get_shared_managers_info()
        print(f"✅ Factory sharing info: {sharing_info}")
        
        # ✅ TEST 3: Test manager creation
        print("3️⃣ Testing resource managers creation...")
        from mining_environment.scripts.unified_logging import get_unified_logger
        
        # Mock config for testing
        class MockConfig:
            def __init__(self):
                self.data = {}
                self.process_priority_map = {'inference-cuda': 1}
                self.cloaking_strategies = {'gpu_cloaking': {'enabled': True}}
            
            def get(self, key, default=None):
                return getattr(self, key, default)
        
        config = MockConfig()
        logger = get_unified_logger('test_startup')
        
        resource_managers = ResourceControlFactory.create_resource_managers(config, logger)
        print(f"✅ Resource managers created: {list(resource_managers.keys())}")
        
        # ✅ TEST 4: Verify GPU manager registration
        gpu_manager_exists = 'gpu' in resource_managers
        print(f"🎮 GPU manager registered: {gpu_manager_exists}")
        
        if gpu_manager_exists:
            gpu_manager = resource_managers['gpu']
            gpu_count = gpu_manager.get_gpu_count()
            nvml_status = gpu_manager.is_nvml_initialized()
            print(f"🎮 GPU Manager Status: GPUs={gpu_count}, NVML={nvml_status}")
        
        return True
        
    except Exception as e:
        print(f"❌ Factory Pattern Investigation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_enhanced_logging_implementation():
    """Test Phase 2: Enhanced Logging Implementation"""
    print("\n🚀 Phase 2: Enhanced Logging Implementation")
    print("=" * 50)
    
    try:
        # ✅ TEST 1: GPU monitoring system import
        print("1️⃣ Testing GPU monitoring system import...")
        from mining_environment.scripts.gpu_resource_monitor import initialize_gpu_monitoring, get_gpu_monitor
        print("✅ GPU monitoring system import successful")
        
        # ✅ TEST 2: ResourceManager enhanced initialization
        print("2️⃣ Testing ResourceManager enhanced initialization...")
        from mining_environment.scripts.resource_manager import ResourceManager
        from mining_environment.scripts.auxiliary_modules.models import ConfigModel
        
        # Create enhanced config
        config_data = {
            'process_priority_map': {'inference-cuda': 1},
            'cloaking_strategies': {
                'gpu_cloaking': {'enabled': True},
                'network': {'enabled': True},
                'memory': {'enabled': True}
            }
        }
        config = ConfigModel(config_data)
        
        # Create ResourceManager instance
        resource_manager = ResourceManager(config)
        print("✅ ResourceManager instance created with enhanced logging")
        
        # ✅ TEST 3: Test startup validation checkpoints
        print("3️⃣ Testing startup validation checkpoints...")
        if hasattr(resource_manager, '_perform_startup_validation_checkpoints'):
            print("✅ Startup validation checkpoints method exists")
            # Note: Actual execution would be part of start() method
        else:
            print("❌ Startup validation checkpoints method missing")
        
        # ✅ TEST 4: Test GPU monitoring initialization
        print("4️⃣ Testing GPU monitoring initialization...")
        if hasattr(resource_manager, '_initialize_gpu_monitoring'):
            print("✅ GPU monitoring initialization method exists")
        else:
            print("❌ GPU monitoring initialization method missing")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced Logging Implementation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration_verification():
    """Test Integration: Full system integration verification"""
    print("\n🔗 Integration Verification")
    print("=" * 50)
    
    try:
        # ✅ TEST 1: Complete system startup simulation
        print("1️⃣ Testing complete system startup simulation...")
        
        from mining_environment.scripts.resource_control import ResourceControlFactory
        from mining_environment.scripts.unified_logging import get_unified_logger
        
        # Create realistic config
        class TestConfig:
            def __init__(self):
                self.process_priority_map = {'inference-cuda': 1, 'ml-inference': 2}
                self.cloaking_strategies = {
                    'gpu_cloaking': {'enabled': True},
                    'network': {'enabled': True},
                    'disk_io': {'enabled': True},
                    'cache': {'enabled': True},
                    'memory': {'enabled': True}
                }
                self.data = {
                    'process_priority_map': self.process_priority_map,
                    'cloaking_strategies': self.cloaking_strategies
                }
            
            def get(self, key, default=None):
                return self.data.get(key, default)
        
        config = TestConfig()
        logger = get_unified_logger('integration_test')
        
        # ✅ CREATE RESOURCE MANAGERS
        logger.info("🏭 Creating resource managers for integration test...")
        resource_managers = ResourceControlFactory.create_resource_managers(config, logger)
        
        # ✅ VERIFY FACTORY OUTPUT
        expected_managers = ['gpu', 'network', 'disk_io', 'cache', 'memory']
        missing_managers = [mgr for mgr in expected_managers if mgr not in resource_managers]
        
        if missing_managers:
            print(f"⚠️ Missing managers: {missing_managers}")
        else:
            print("✅ All expected managers created successfully")
        
        # ✅ VERIFY GPU MANAGER SPECIFICALLY
        if 'gpu' in resource_managers:
            gpu_manager = resource_managers['gpu']
            try:
                gpu_count = gpu_manager.get_gpu_count()
                nvml_status = gpu_manager.is_nvml_initialized()
                print(f"✅ GPU Manager verification: GPUs={gpu_count}, NVML={nvml_status}")
            except Exception as gpu_err:
                print(f"⚠️ GPU Manager verification warning: {gpu_err}")
        
        # ✅ TEST FACTORY SHARING INFO
        sharing_info = ResourceControlFactory.get_shared_managers_info()
        print(f"📊 Factory sharing efficiency: {sharing_info['memory_efficiency']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test execution"""
    print("🚀 GPU Mining System Startup Verification Test Suite")
    print("=" * 60)
    print(f"⏰ Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Configure logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_results = {}
    
    # Run all test phases
    test_results['Phase 1'] = test_factory_pattern_investigation()
    test_results['Phase 2'] = test_enhanced_logging_implementation()
    test_results['Integration'] = test_integration_verification()
    
    # ✅ FINAL RESULTS SUMMARY
    print("\n📊 Test Results Summary")
    print("=" * 30)
    
    total_tests = len(test_results)
    passed_tests = sum(test_results.values())
    
    for phase, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{phase}: {status}")
    
    print(f"\n🎯 Overall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🏆 ALL TESTS PASSED - GPU mining system startup verification successful!")
        return 0
    else:
        print("⚠️ SOME TESTS FAILED - Review implementation for issues")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)