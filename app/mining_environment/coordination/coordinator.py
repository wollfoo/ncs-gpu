#!/usr/bin/env python3
"""
Simple Hook Coordinator - Production Ready
Điều phối Hook đơn giản - sẵn sàng sản xuất
"""

import os
import time
import threading
import json
from typing import Dict, Optional

class HookCoordinator:
    """Điều phối Hook đơn giản cho PHASE 3+ và cloaking"""
    
    def __init__(self):
        self.lock = threading.Lock()
        self.hooks_ready: Dict[int, bool] = {}
        
    def register_pid(self, pid: int) -> None:
        """Đăng ký PID"""
        with self.lock:
            self.hooks_ready[pid] = False
            
    def notify_hooks_ready(self, pid: int) -> None:
        """Thông báo hooks đã sẵn sàng"""
        with self.lock:
            self.hooks_ready[pid] = True
            # Environment variable để ResourceManager check
            os.environ[f'HOOKS_READY_PID_{pid}'] = '1'
            
    def check_hooks_ready(self, pid: int) -> bool:
        """Kiểm tra hooks có sẵn sàng không"""
        with self.lock:
            return self.hooks_ready.get(pid, False)
            
    def wait_for_hooks_ready(self, pid: int, timeout: int = 70) -> bool:
        """Chờ hooks sẵn sàng với timeout"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.check_hooks_ready(pid):
                return True
            time.sleep(2)
            
        return False
        
    def cleanup_pid(self, pid: int) -> None:
        """Dọn dẹp PID"""
        with self.lock:
            self.hooks_ready.pop(pid, None)
            env_var = f'HOOKS_READY_PID_{pid}'
            if env_var in os.environ:
                del os.environ[env_var]

# Global instance
_coordinator: Optional[HookCoordinator] = None
_lock = threading.Lock()

def get_hook_coordinator() -> HookCoordinator:
    """Lấy coordinator singleton"""
    global _coordinator
    
    with _lock:
        if _coordinator is None:
            _coordinator = HookCoordinator()
        return _coordinator