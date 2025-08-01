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

# ✅ UNIFIED LOGGING: Import unified logging system
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    from unified_logging import get_unified_logger
    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False

class HookCoordinator:
    """Điều phối Hook đơn giản cho PHASE 3+ và cloaking"""
    
    def __init__(self):
        self.lock = threading.Lock()
        self.hooks_ready: Dict[int, bool] = {}
        
        # ✅ UNIFIED LOGGING: Initialize coordination logger
        if LOGGING_AVAILABLE:
            self.logger = get_unified_logger('mining_environment.coordination')
            self.logger.info("🔗 HookCoordinator initialized with unified logging")
        else:
            self.logger = None
        
    def register_pid(self, pid: int) -> None:
        """Đăng ký PID"""
        with self.lock:
            self.hooks_ready[pid] = False
            if self.logger:
                self.logger.info(f"📝 [REGISTER] PID {pid} registered for hook coordination")
            
    def notify_hooks_ready(self, pid: int) -> None:
        """Thông báo hooks đã sẵn sàng"""
        with self.lock:
            self.hooks_ready[pid] = True
            # Environment variable để ResourceManager check
            os.environ[f'HOOKS_READY_PID_{pid}'] = '1'
            if self.logger:
                self.logger.info(f"✅ [NOTIFY] PID {pid} hooks ready - environment variable set")
                self.logger.debug(f"🔍 [DEBUG] Current hooks_ready state: {dict(list(self.hooks_ready.items())[-5:])}")
            
    def check_hooks_ready(self, pid: int) -> bool:
        """Kiểm tra hooks có sẵn sàng không"""
        with self.lock:
            is_ready = self.hooks_ready.get(pid, False)
            if self.logger:
                self.logger.debug(f"🔍 [CHECK] PID {pid} hooks ready status: {is_ready}")
            return is_ready
            
    def wait_for_hooks_ready(self, pid: int, timeout: int = 70) -> bool:
        """Chờ hooks sẵn sàng với timeout"""
        start_time = time.time()
        
        if self.logger:
            self.logger.info(f"⏳ [WAIT] Waiting for PID {pid} hooks ready (timeout: {timeout}s)")
        
        while time.time() - start_time < timeout:
            if self.check_hooks_ready(pid):
                elapsed = time.time() - start_time
                if self.logger:
                    self.logger.info(f"✅ [WAIT] PID {pid} hooks ready after {elapsed:.1f}s")
                return True
            time.sleep(2)
        
        elapsed = time.time() - start_time    
        if self.logger:
            self.logger.warning(f"⏰ [TIMEOUT] PID {pid} hooks not ready after {elapsed:.1f}s timeout")
        return False
        
    def cleanup_pid(self, pid: int) -> None:
        """Dọn dẹp PID"""
        with self.lock:
            was_tracked = pid in self.hooks_ready
            self.hooks_ready.pop(pid, None)
            env_var = f'HOOKS_READY_PID_{pid}'
            env_cleaned = False
            if env_var in os.environ:
                del os.environ[env_var]
                env_cleaned = True
                
            if self.logger and was_tracked:
                self.logger.info(f"🧹 [CLEANUP] PID {pid} removed from tracking (env_var_cleaned: {env_cleaned})")

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