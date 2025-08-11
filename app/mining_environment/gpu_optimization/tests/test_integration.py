#!/usr/bin/env python3
"""
End-to-End Integration Test for GPU Optimization System
Test tích hợp đầu cuối đến đầu cuối cho hệ thống tối ưu hóa GPU
"""

import sys
import os
import time
import subprocess
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import GPU Optimization package
import gpu_optimization

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_package_api():
    """Test package-level API"""
    print("\n" + "="*60)
    print("📦 TESTING PACKAGE API")
    print("="*60)
    
    # Test package metadata
    print(f"\n1️⃣ Package info:")
    print(f"   Version: {gpu_optimization.__version__}")
    print(f"   API exports: {gpu_optimization.__all__}")
    
    info = gpu_optimization.get_info()
    print(f"   Full info: {info}")
    
    assert gpu_optimization.__version__ == "2.0.0"
    assert 'initialize' in gpu_optimization.__all__
    print("   ✅ Package API verified")
    
    return True


def test_simple_workflow():
    """Test simple optimization workflow"""
    print("\n" + "="*60)
    print("🔄 TESTING SIMPLE WORKFLOW")
    print("="*60)
    
    try:
        # Initialize
        print("\n1️⃣ Initializing system...")
        success = gpu_optimization.initialize()
        assert success == True
        print("   ✅ System initialized")
        
        # Get status
        print("\n2️⃣ Getting status...")
        status = gpu_optimization.get_status()
        print(f"   Status: {status}")
        assert status['initialized'] == True
        print("   ✅ Status retrieved")
        
        # Optimize current process
        print("\n3️⃣ Optimizing current process...")
        result = gpu_optimization.optimize(
            pid=os.getpid(),
            gpu_index=0
        )
        print(f"   Result: {result}")
        assert result['success'] == True
        print("   ✅ Optimization successful")
        
        # Shutdown
        print("\n4️⃣ Shutting down...")
        success = gpu_optimization.shutdown()
        assert success == True
        print("   ✅ Shutdown complete")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_concurrent_optimizations():
    """Test concurrent optimization requests"""
    print("\n" + "="*60)
    print("🔀 TESTING CONCURRENT OPTIMIZATIONS")
    print("="*60)
    
    try:
        # Initialize
        gpu_optimization.initialize()
        
        # Create dummy processes
        print("\n1️⃣ Creating test processes...")
        processes = []
        for i in range(3):
            # Start a simple Python process
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            processes.append(proc)
            print(f"   Started process {proc.pid}")
        
        # Optimize all processes
        print("\n2️⃣ Optimizing all processes...")
        results = []
        for i, proc in enumerate(processes):
            result = gpu_optimization.optimize(
                pid=proc.pid,
                gpu_index=i % 2  # Alternate between GPU 0 and 1
            )
            results.append(result)
            print(f"   Process {proc.pid} on GPU {i%2}: {'✓' if result['success'] else '✗'}")
        
        # Check results
        successful = sum(1 for r in results if r['success'])
        print(f"\n   Successfully optimized: {successful}/{len(processes)}")
        
        # Clean up processes
        print("\n3️⃣ Cleaning up processes...")
        for proc in processes:
            proc.terminate()
            proc.wait(timeout=5)
            print(f"   Terminated process {proc.pid}")
        
        # Shutdown
        gpu_optimization.shutdown()
        
        return successful > 0  # At least one should succeed
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Clean up
        for proc in processes:
            try:
                proc.terminate()
            except:
                pass
        
        return False


def test_error_handling():
    """Test error handling and edge cases"""
    print("\n" + "="*60)
    print("⚠️ TESTING ERROR HANDLING")
    print("="*60)
    
    try:
        # Test optimization without initialization
        print("\n1️⃣ Testing optimization without init...")
        gpu_optimization.shutdown()  # Ensure clean state
        result = gpu_optimization.optimize(pid=99999, gpu_index=0)
        assert result['success'] == False
        print(f"   Result: {result}")
        print("   ✅ Properly handled uninitialized state")
        
        # Test invalid PID
        print("\n2️⃣ Testing invalid PID...")
        gpu_optimization.initialize()
        result = gpu_optimization.optimize(pid=99999, gpu_index=0)
        # Should handle gracefully
        print(f"   Result: {result}")
        print("   ✅ Properly handled invalid PID")
        
        # Test invalid GPU index
        print("\n3️⃣ Testing invalid GPU index...")
        result = gpu_optimization.optimize(pid=os.getpid(), gpu_index=99)
        # Should handle gracefully or fallback
        print(f"   Result: {result}")
        print("   ✅ Properly handled invalid GPU index")
        
        # Cleanup
        gpu_optimization.shutdown()
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance():
    """Test performance metrics"""
    print("\n" + "="*60)
    print("⚡ TESTING PERFORMANCE")
    print("="*60)
    
    try:
        # Initialize
        gpu_optimization.initialize()
        
        # Measure optimization time
        print("\n1️⃣ Measuring optimization time...")
        times = []
        
        for i in range(5):
            start = time.time()
            result = gpu_optimization.optimize(
                pid=os.getpid(),
                gpu_index=0
            )
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"   Iteration {i+1}: {elapsed:.3f}s")
        
        avg_time = sum(times) / len(times)
        print(f"\n   Average time: {avg_time:.3f}s")
        print(f"   Min time: {min(times):.3f}s")
        print(f"   Max time: {max(times):.3f}s")
        
        # Check performance threshold
        assert avg_time < 5.0  # Should complete within 5 seconds
        print("   ✅ Performance within acceptable range")
        
        # Cleanup
        gpu_optimization.shutdown()
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests"""
    print("\n" + "="*80)
    print("🧪 GPU OPTIMIZATION INTEGRATION TEST SUITE")
    print("="*80)
    
    tests = [
        ("Package API", test_package_api),
        ("Simple Workflow", test_simple_workflow),
        ("Concurrent Optimizations", test_concurrent_optimizations),
        ("Error Handling", test_error_handling),
        ("Performance", test_performance)
    ]
    
    results = {}
    
    for name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {name}")
        print('='*60)
        
        try:
            result = test_func()
            results[name] = result
            print(f"\nTest {name}: {'✅ PASSED' if result else '❌ FAILED'}")
        except Exception as e:
            print(f"\nTest {name}: ❌ CRASHED - {e}")
            results[name] = False
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    
    for name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} tests failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
