#!/usr/bin/env python3
"""
Test script for GPU Optimization Central Manager
Kiểm thử cho trình quản lý trung tâm GPU Optimization
"""

import sys
import os
import time
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.manager import (
    GPUOptimizationManager,
    get_manager,
    initialize,
    optimize,
    get_status,
    shutdown
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_manager():
    """Test Central Manager functionality"""
    
    print("\n" + "="*60)
    print("🧪 CENTRAL MANAGER TEST")
    print("="*60)
    
    try:
        # 1. Test singleton pattern
        print("\n1️⃣ Testing singleton pattern...")
        manager1 = get_manager()
        manager2 = get_manager()
        manager3 = GPUOptimizationManager()
        
        assert manager1 is manager2 is manager3
        print("   ✅ Singleton pattern working correctly")
        
        # 2. Test initialization
        print("\n2️⃣ Testing initialization...")
        success = initialize()
        assert success == True
        print("   ✅ Manager initialized successfully")
        
        # 3. Test status retrieval
        print("\n3️⃣ Testing status retrieval...")
        status = get_status()
        
        print(f"   Manager status:")
        print(f"   - Initialized: {status['initialized']}")
        print(f"   - State: {status['state']['status']}")
        print(f"   - Optimizations count: {status['state']['optimizations_count']}")
        print(f"   - Config loaded: {status['config']['loaded']}")
        
        assert status['initialized'] == True
        assert status['state']['status'] == 'ready'
        print("   ✅ Status retrieval working")
        
        # 4. Test optimization API
        print("\n4️⃣ Testing optimization API...")
        
        # Test with current process
        current_pid = os.getpid()
        
        # Test default optimization
        result1 = optimize(pid=current_pid, gpu_index=0)
        print(f"   Default optimization:")
        print(f"   - Success: {result1['success']}")
        print(f"   - GPU: {result1.get('gpu_index', 0)}")
        print(f"   - Strategies: {result1.get('strategies_applied', [])}")
        assert result1['success'] == True
        
        # Test with specific strategy
        result2 = optimize(pid=current_pid, gpu_index=0, strategy='power')
        print(f"   Power strategy optimization:")
        print(f"   - Success: {result2['success']}")
        print(f"   - Strategies: {result2.get('strategies_applied', [])}")
        assert result2['success'] == True
        assert 'power' in result2.get('strategies_applied', [])
        
        print("   ✅ Optimization API working")
        
        # 5. Test multiple optimizations
        print("\n5️⃣ Testing multiple optimizations...")
        
        for i in range(3):
            result = optimize(pid=current_pid + i, gpu_index=i % 2)
            print(f"   Optimization {i+1}: PID {current_pid + i}, GPU {i % 2} - {'✓' if result['success'] else '✗'}")
        
        # Check updated status
        status = get_status()
        total_optimizations = status['state']['optimizations_count']
        print(f"   Total optimizations: {total_optimizations}")
        assert total_optimizations >= 5
        print("   ✅ Multiple optimizations handled")
        
        # 6. Test re-initialization (should warn)
        print("\n6️⃣ Testing re-initialization...")
        success = initialize()
        assert success == True  # Should still return True but log warning
        print("   ✅ Re-initialization handled correctly")
        
        # 7. Test shutdown
        print("\n7️⃣ Testing shutdown...")
        success = shutdown()
        assert success == True
        
        # Check status after shutdown
        status = get_status()
        assert status['state']['status'] == 'shutdown'
        print("   ✅ Shutdown successful")
        
        # 8. Test optimization after shutdown (should fail)
        print("\n8️⃣ Testing post-shutdown behavior...")
        result = optimize(pid=current_pid, gpu_index=0)
        assert result['success'] == False
        assert 'not initialized' in result.get('error', '').lower()
        print("   ✅ Post-shutdown protection working")
        
        # 9. Test re-initialization after shutdown
        print("\n9️⃣ Testing re-initialization after shutdown...")
        success = initialize()
        assert success == True
        
        # Test optimization works again
        result = optimize(pid=current_pid, gpu_index=0)
        assert result['success'] == True
        print("   ✅ Re-initialization after shutdown working")
        
        # Final shutdown
        shutdown()
        
        print("\n" + "="*60)
        print("✅ ALL MANAGER TESTS PASSED")
        print("="*60)
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_manager()
    sys.exit(0 if success else 1)
