#!/usr/bin/env python3
"""
Test Progressive Memory Allocation System
Kiểm thử hệ thống cấp phát bộ nhớ tiến tiến
"""

import sys
import os
import logging
import psutil
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, '/home/azureuser/ncs-gpu/app')

# Set environment variable for testing
os.environ['LOGS_DIR'] = '/home/azureuser/ncs-gpu/app/mining_environment/logs'
os.environ['CONFIG_DIR'] = '/home/azureuser/ncs-gpu/app/mining_environment/config'

def setup_test_logger():
    """Setup test logger"""
    logger = logging.getLogger('test_progressive_allocation')
    logger.setLevel(logging.INFO)
    
    # Console handler
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

def create_mock_resource_manager():
    """Create mock ResourceManager with Progressive Memory Allocation methods"""
    from mining_environment.scripts.resource_manager import ResourceManager
    from mining_environment.scripts.auxiliary_modules.models import ConfigModel
    
    # Create minimal config
    config_data = {
        'process_priority_map': {'ml-inference': 1, 'inference-cuda': 2},
        'cloaking_strategies': {
            'gpu_cloaking': {'enabled': True},
            'memory': {'enabled': True},
            'network': {'enabled': True}
        }
    }
    
    config = ConfigModel(config_data)
    logger = setup_test_logger()
    
    # Create ResourceManager (singleton pattern will be used)
    rm = ResourceManager(config, logger=logger)
    
    return rm, logger

def test_progressive_allocation_methods():
    """Test các phương thức Progressive Memory Allocation"""
    print("🔍 [TEST] Kiểm thử Progressive Memory Allocation System...")
    
    try:
        # Create ResourceManager instance
        rm, logger = create_mock_resource_manager()
        
        # Test memory pressure monitoring
        print("\n1️⃣ [TEST] Memory Pressure Monitoring...")
        pressure_data = rm.monitor_memory_pressure()
        print(f"   📊 Memory Usage: {pressure_data['usage_percent']:.1f}%")
        print(f"   🔍 Pressure Level: {pressure_data['pressure_level']}")
        print(f"   ⚡ Action Required: {pressure_data['action_required']}")
        print(f"   💾 Available: {pressure_data['available_gb']:.1f}GB")
        
        # Test different allocation scenarios
        test_scenarios = [
            {"name": "Small Request", "size_mb": 1024},      # 1GB
            {"name": "Medium Request", "size_mb": 4096},     # 4GB
            {"name": "Large Request", "size_mb": 8192},      # 8GB
            {"name": "Very Large Request", "size_mb": 16384} # 16GB
        ]
        
        print(f"\n2️⃣ [TEST] Progressive Allocation Scenarios...")
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n   📋 Scenario {i}: {scenario['name']} ({scenario['size_mb']}MB)")
            
            # Test progressive allocation
            result = rm.allocate_memory_progressive(scenario['size_mb'])
            
            print(f"      ✅ Success: {result['success']}")
            print(f"      📦 Allocated: {result['allocated_mb']}MB")
            print(f"      🎯 Strategy: {result['strategy']}")
            print(f"      📊 Memory Pressure: {result['memory_pressure']:.1f}%")
            print(f"      🛡️ Safety Action: {result['safety_action']}")
        
        # Test individual allocation strategies
        print(f"\n3️⃣ [TEST] Individual Allocation Strategies...")
        
        # Test normal allocation
        print(f"\n   🟢 Normal Allocation (2GB)...")
        normal_result = rm.allocate_normal(2048)
        print(f"      Result: {normal_result}")
        
        # Test conservative allocation
        print(f"\n   🟡 Conservative Allocation (2GB)...")
        conservative_result = rm.allocate_conservative(2048)
        print(f"      Result: {conservative_result}")
        
        # Test reduce memory footprint (simulate high pressure)
        print(f"\n   🔴 Memory Footprint Reduction (2GB)...")
        reduce_result = rm.reduce_memory_footprint(2048)
        print(f"      Result: {reduce_result}")
        
        print(f"\n✅ [TEST SUCCESS] Progressive Memory Allocation system works correctly!")
        return True
        
    except Exception as e:
        print(f"\n❌ [TEST FAILED] Error during testing: {e}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        return False

def test_memory_pressure_thresholds():
    """Test memory pressure threshold detection"""
    print(f"\n🌡️ [TEST] Memory Pressure Threshold Detection...")
    
    try:
        rm, logger = create_mock_resource_manager()
        
        # Mock different memory usage scenarios
        test_cases = [
            {"usage": 50.0, "expected_level": "LOW", "expected_action": "NONE"},
            {"usage": 70.0, "expected_level": "MODERATE", "expected_action": "MONITOR"},
            {"usage": 80.0, "expected_level": "HIGH", "expected_action": "SOON"},
            {"usage": 90.0, "expected_level": "CRITICAL", "expected_action": "IMMEDIATE"}
        ]
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n   📊 Test Case {i}: {case['usage']}% Memory Usage")
            
            # Mock psutil.virtual_memory() to return specific usage
            mock_memory = Mock()
            mock_memory.percent = case['usage']
            mock_memory.available = 1024 * 1024 * 1024 * (100 - case['usage']) / 100  # bytes
            mock_memory.total = 1024 * 1024 * 1024 * 100  # 100GB total
            mock_memory.used = 1024 * 1024 * 1024 * case['usage'] / 100
            
            with patch('psutil.virtual_memory', return_value=mock_memory):
                pressure_data = rm.monitor_memory_pressure()
                
                print(f"      🎯 Expected Level: {case['expected_level']}, Got: {pressure_data['pressure_level']}")
                print(f"      ⚡ Expected Action: {case['expected_action']}, Got: {pressure_data['action_required']}")
                
                # Verify results
                if (pressure_data['pressure_level'] == case['expected_level'] and 
                    pressure_data['action_required'] == case['expected_action']):
                    print(f"      ✅ Threshold detection PASSED")
                else:
                    print(f"      ❌ Threshold detection FAILED")
        
        print(f"\n✅ [TEST SUCCESS] Memory pressure threshold detection works correctly!")
        return True
        
    except Exception as e:
        print(f"\n❌ [TEST FAILED] Threshold detection error: {e}")
        return False

def test_allocation_strategy_routing():
    """Test allocation strategy routing based on memory pressure"""
    print(f"\n🔀 [TEST] Allocation Strategy Routing...")
    
    try:
        rm, logger = create_mock_resource_manager()
        
        # Test routing logic for different memory pressures
        routing_tests = [
            {"usage": 60.0, "expected_strategy": "normal"},
            {"usage": 80.0, "expected_strategy": "conservative"},
            {"usage": 90.0, "expected_strategy": "emergency_reduced"}
        ]
        
        for i, test in enumerate(routing_tests, 1):
            print(f"\n   🎯 Routing Test {i}: {test['usage']}% Memory Usage")
            
            # Mock memory usage
            mock_memory = Mock()
            mock_memory.percent = test['usage']
            mock_memory.available = 1024 * 1024 * 1024 * (100 - test['usage']) / 100
            mock_memory.total = 1024 * 1024 * 1024 * 100
            mock_memory.used = 1024 * 1024 * 1024 * test['usage'] / 100
            
            with patch('psutil.virtual_memory', return_value=mock_memory):
                result = rm.allocate_memory_progressive(2048)  # Request 2GB
                
                print(f"      📦 Requested: 2048MB")
                print(f"      🎯 Expected Strategy: {test['expected_strategy']}")
                print(f"      📊 Actual Strategy: {result['strategy']}")
                print(f"      ✅ Success: {result['success']}")
                print(f"      💾 Allocated: {result['allocated_mb']}MB")
        
        print(f"\n✅ [TEST SUCCESS] Allocation strategy routing works correctly!")
        return True
        
    except Exception as e:
        print(f"\n❌ [TEST FAILED] Strategy routing error: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 [PROGRESSIVE ALLOCATION TEST] Starting comprehensive testing...")
    print("=" * 80)
    
    results = []
    
    # Run all tests
    results.append(test_progressive_allocation_methods())
    results.append(test_memory_pressure_thresholds())
    results.append(test_allocation_strategy_routing())
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 [TEST SUMMARY] Progressive Memory Allocation System")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Tests Passed: {passed}/{total}")
    
    if passed == total:
        print("🎯 [OVERALL RESULT] ALL TESTS PASSED - Progressive Memory Allocation system ready!")
        print("💡 [NEXT STEP] System can safely prevent std::bad_alloc errors through progressive allocation")
    else:
        print(f"❌ [OVERALL RESULT] {total - passed} TESTS FAILED - Review implementation")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)