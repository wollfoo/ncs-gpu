#!/usr/bin/env python3
"""
Test DAG Synchronization Integration
Script kiểm thử tích hợp DAG Synchronization với OptimizedHardwareController

This script tests the integration of DAG synchronization module with the 
OptimizedHardwareController to ensure proper workflow coordination.
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))  # Add app directory

# Setup minimal logging if module_loggers not available
def get_test_logger():
    """Create a test logger if module_loggers not available"""
    logger = logging.getLogger('test_dag_integration')
    logger.setLevel(logging.DEBUG)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger

# Try importing with fallback
try:
    # First try importing as a package (when run from parent)
    from mining_environment.scripts.resource_control import OptimizedHardwareController
    from mining_environment.scripts.dag_synchronization import get_dag_synchronizer, DAGState
    from mining_environment.scripts.module_loggers import get_resource_control_logger
    print("✅ Imported as package")
except ImportError:
    try:
        # Try direct import (when run from same directory)
        from resource_control import OptimizedHardwareController
        from dag_synchronization import get_dag_synchronizer, DAGState
        try:
            from module_loggers import get_resource_control_logger
        except ImportError:
            # Use fallback logger
            get_resource_control_logger = get_test_logger
        print("✅ Imported directly")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all required modules are in the same directory")
        sys.exit(1)

def setup_test_environment():
    """Setup test environment and logging"""
    # Create logs directory if not exists
    log_dir = Path("/app/mining_environment/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure console logging for test visibility
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # Get logger and add console handler
    logger = get_resource_control_logger()
    logger.addHandler(console_handler)
    logger.setLevel(logging.DEBUG)
    
    return logger

def test_dag_synchronization_basic(logger):
    """Test basic DAG synchronization functionality"""
    print("\n" + "="*60)
    print("📊 TEST 1: Basic DAG Synchronization")
    print("="*60)
    
    # Get DAG synchronizer directly
    dag_sync = get_dag_synchronizer()
    
    # Test parameters
    epoch = 451
    algorithm = "ethash"
    gpu_id = 0
    
    print(f"\n🔍 Testing DAG for {algorithm} epoch {epoch} on GPU {gpu_id}")
    
    # Check initial state
    info = dag_sync.get_dag_info(epoch, algorithm)
    if info:
        print(f"✅ Initial DAG state: {info.state.value}")
    else:
        print("ℹ️ No existing DAG found (expected for first run)")
    
    # Register calculation
    should_calc = dag_sync.register_dag_calculation(epoch, algorithm, gpu_id)
    print(f"📝 Should calculate: {should_calc}")
    
    if should_calc:
        # Simulate progress updates
        for progress in [0.25, 0.5, 0.75]:
            dag_sync.update_progress(epoch, algorithm, gpu_id, progress)
            print(f"   Progress: {progress*100:.0f}%")
            time.sleep(0.5)
        
        # Complete calculation
        dag_sync.complete_calculation(
            epoch, algorithm, gpu_id,
            f"/tmp/dag_cache/{algorithm}_{epoch}.dag",
            5 * 1024**3,  # 5GB
            "test_hash_12345"
        )
        print("✅ DAG calculation completed!")
    
    # Verify final state
    final_info = dag_sync.get_dag_info(epoch, algorithm)
    if final_info:
        print(f"📊 Final DAG state: {final_info.state.value}")
        print(f"   File: {final_info.file_path}")
        print(f"   Size: {final_info.size_bytes / (1024**3):.2f} GB")
        return True
    else:
        print("❌ Failed to get final DAG info")
        return False

def test_hardware_controller_integration(logger):
    """Test OptimizedHardwareController with DAG integration"""
    print("\n" + "="*60)
    print("🔧 TEST 2: Hardware Controller Integration")
    print("="*60)
    
    # Configuration for controller
    config = {
        'baseline_power': 150,
        'baseline_temp': 65,
        'temp_critical': 78,
        'mining_config': {
            'algorithm': 'ethash',
            'epoch': 452,
            'dag_size': 4.8
        }
    }
    
    # Initialize controller
    print("\n🔧 Initializing OptimizedHardwareController...")
    controller = OptimizedHardwareController(config, logger)
    
    # Check DAG synchronizer availability
    if controller.dag_synchronizer:
        print("✅ DAG Synchronizer is available in controller")
    else:
        print("❌ DAG Synchronizer not available in controller")
        return False
    
    # Test ensure_dag_ready method
    print("\n🔄 Testing ensure_dag_ready() method...")
    gpu_index = 0
    dag_ready = controller.ensure_dag_ready(gpu_index)
    
    if dag_ready:
        print(f"✅ DAG is ready for mining on GPU {gpu_index}")
    else:
        print(f"❌ DAG preparation failed for GPU {gpu_index}")
    
    return dag_ready

def test_optimize_for_pid_with_dag(logger):
    """Test optimize_for_pid with DAG synchronization"""
    print("\n" + "="*60)
    print("⚡ TEST 3: Optimize for PID with DAG Check")
    print("="*60)
    
    # Configuration with mining strategy
    config = {
        'baseline_power': 150,
        'baseline_temp': 65,
        'temp_critical': 78,
        'mining_config': {
            'algorithm': 'kawpow',
            'epoch': 300,
            'dag_size': 3.2
        }
    }
    
    # Initialize controller
    controller = OptimizedHardwareController(config, logger)
    
    # Get current process PID for testing
    test_pid = os.getpid()
    print(f"\n🔧 Testing optimization for PID: {test_pid}")
    
    # Test with mining strategy (should trigger DAG check)
    print("\n📊 Testing with 'mining' strategy (should check DAG)...")
    result = controller.optimize_for_pid(
        pid=test_pid,
        strategy='mining',
        gpu_index=0
    )
    
    print(f"\n📋 Optimization Results:")
    print(f"   Success: {result.get('success', False)}")
    print(f"   Strategy: {result.get('strategy', 'N/A')}")
    print(f"   GPU Index: {result.get('gpu_index', 'N/A')}")
    print(f"   Operations: {result.get('operations_applied', [])}")
    
    # Check if DAG was checked
    if 'dag_ready' in result.get('operations_applied', []):
        print("✅ DAG synchronization was activated!")
        return True
    elif 'dag_check_failed' in result.get('operations_applied', []):
        print("⚠️ DAG check was attempted but failed")
        return False
    else:
        print("❌ DAG synchronization was not activated")
        return False

def test_multi_gpu_dag_coordination(logger):
    """Test multi-GPU DAG coordination"""
    print("\n" + "="*60)
    print("🖥️ TEST 4: Multi-GPU DAG Coordination")
    print("="*60)
    
    dag_sync = get_dag_synchronizer()
    
    # Test parameters
    epoch = 453
    algorithm = "etchash"
    
    print(f"\n🔍 Testing multi-GPU coordination for {algorithm} epoch {epoch}")
    
    # Simulate multiple GPUs trying to calculate
    gpu_results = {}
    for gpu_id in range(2):
        should_calc = dag_sync.register_dag_calculation(epoch, algorithm, gpu_id)
        gpu_results[gpu_id] = should_calc
        print(f"   GPU {gpu_id}: Should calculate = {should_calc}")
    
    # Only one GPU should calculate
    calculating_gpus = sum(1 for calc in gpu_results.values() if calc)
    print(f"\n📊 GPUs assigned to calculate: {calculating_gpus}")
    
    if calculating_gpus == 1:
        print("✅ Correct: Only one GPU assigned for DAG calculation")
        
        # Find which GPU is calculating
        calc_gpu = next(gpu for gpu, calc in gpu_results.items() if calc)
        print(f"   GPU {calc_gpu} is calculating the DAG")
        
        # Complete calculation
        dag_sync.complete_calculation(
            epoch, algorithm, calc_gpu,
            f"/tmp/dag_cache/{algorithm}_{epoch}.dag",
            4 * 1024**3,  # 4GB
            "test_hash_multi"
        )
        
        # Verify all GPUs can now access the DAG
        for gpu_id in range(2):
            info = dag_sync.get_dag_info(epoch, algorithm)
            if info and info.state == DAGState.COMPLETED:
                print(f"   GPU {gpu_id}: Can access completed DAG ✅")
            else:
                print(f"   GPU {gpu_id}: Cannot access DAG ❌")
                return False
        
        return True
    else:
        print(f"❌ Error: {calculating_gpus} GPUs assigned (expected 1)")
        return False

def main():
    """Main test runner"""
    print("\n" + "#"*60)
    print("# DAG SYNCHRONIZATION INTEGRATION TEST")
    print("# Testing DAG module activation in GPU workflow")
    print("#"*60)
    
    # Setup environment
    logger = setup_test_environment()
    
    # Track test results
    test_results = {}
    
    # Run tests
    tests = [
        ("Basic DAG Sync", test_dag_synchronization_basic),
        ("Controller Integration", test_hardware_controller_integration),
        ("Optimize PID with DAG", test_optimize_for_pid_with_dag),
        ("Multi-GPU Coordination", test_multi_gpu_dag_coordination)
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func(logger)
            test_results[test_name] = result
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with error: {e}")
            test_results[test_name] = False
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    # Overall result
    all_passed = all(test_results.values())
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ DAG Synchronization is successfully integrated")
    else:
        print("⚠️ SOME TESTS FAILED")
        print("Please check the failures above")
    print("="*60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
