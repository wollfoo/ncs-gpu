#!/usr/bin/env python3
"""
Simple Hook Coordinator - Production Ready
Điều phối Hook đơn giản - sẵn sàng sản xuất
"""

import os
import time
import threading
import json
import psutil
from typing import Dict, Optional, Set, Any

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
        
        # ✅ HEALTH CHECK: Hook coordination health monitoring attributes
        self.active_processes: Set[int] = set()
        self.hook_status_history: Dict[int, list] = {}  # Track status changes over time
        self.last_health_check: float = 0
        self.health_check_interval: float = 30  # Check every 30 seconds
        self.recovery_attempts: Dict[int, int] = {}  # Track recovery attempts per PID
        self.max_recovery_attempts: int = 3
        
        # ✅ HEALTH MONITORING: Start health monitoring thread
        self.health_monitoring_active = False
        self.health_monitor_thread: Optional[threading.Thread] = None
        
        # ✅ UNIFIED LOGGING: Initialize coordination logger
        if LOGGING_AVAILABLE:
            self.logger = get_unified_logger('mining_environment.coordination')
            self.logger.info("🔗 HookCoordinator initialized with unified logging")
            self.logger.info("🏥 [HEALTH] Health monitoring system initialized")
        else:
            self.logger = None
        
    def register_pid(self, pid: int) -> None:
        """**Register PID** (đăng ký PID - thêm tiến trình vào hệ thống theo dõi hook coordination)"""
        with self.lock:
            self.hooks_ready[pid] = False
            self.active_processes.add(pid)
            self.hook_status_history[pid] = []
            self.recovery_attempts[pid] = 0
            
            # ✅ HEALTH MONITORING: Auto-start health monitoring on first registration
            if not self.health_monitoring_active:
                self._start_health_monitoring()
            
            if self.logger:
                self.logger.info(f"📝 [REGISTER] PID {pid} registered for hook coordination")
                self.logger.info(f"🏥 [HEALTH] PID {pid} added to health monitoring (total: {len(self.active_processes)})")
            
    def notify_hooks_ready(self, pid: int) -> None:
        """**Notify Hooks Ready** (thông báo hooks sẵn sàng - báo hiệu hoàn thành PHASE 3+ initialization)"""
        with self.lock:
            self.hooks_ready[pid] = True
            # Environment variable để ResourceManager check
            os.environ[f'HOOKS_READY_PID_{pid}'] = '1'
            
            # ✅ HEALTH TRACKING: Record status change in history
            self._record_status_change(pid, 'hooks_ready', True)
            
            if self.logger:
                self.logger.info(f"✅ [NOTIFY] PID {pid} hooks ready - environment variable set")
                self.logger.debug(f"🔍 [DEBUG] Current hooks_ready state: {dict(list(self.hooks_ready.items())[-5:])}")
                self.logger.info(f"🏥 [HEALTH] Status change recorded for PID {pid}")
            
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
        """**Cleanup PID** (dọn dẹp PID - xóa tiến trình khỏi tất cả hệ thống theo dõi)"""
        with self.lock:
            was_tracked = pid in self.hooks_ready
            self.hooks_ready.pop(pid, None)
            self.active_processes.discard(pid)
            self.hook_status_history.pop(pid, None)
            self.recovery_attempts.pop(pid, None)
            
            env_var = f'HOOKS_READY_PID_{pid}'
            env_cleaned = False
            if env_var in os.environ:
                del os.environ[env_var]
                env_cleaned = True
                
            if self.logger and was_tracked:
                self.logger.info(f"🧹 [CLEANUP] PID {pid} removed from all tracking systems (env_var_cleaned: {env_cleaned})")
                self.logger.info(f"🏥 [HEALTH] Health monitoring cleanup for PID {pid} completed")
                
            # ✅ HEALTH MONITORING: Stop monitoring if no active processes
            if len(self.active_processes) == 0 and self.health_monitoring_active:
                self._stop_health_monitoring()
    
    # ===== HEALTH CHECK SYSTEM METHODS =====
    
    def _start_health_monitoring(self) -> None:
        """**Start Health Monitoring** (khởi động giám sát sức khỏe - bắt đầu thread monitoring hook coordination)"""
        if self.health_monitoring_active:
            return
            
        self.health_monitoring_active = True
        self.health_monitor_thread = threading.Thread(
            target=self._health_monitoring_loop,
            daemon=True,
            name="HookCoordinator-HealthMonitor"
        )
        self.health_monitor_thread.start()
        
        if self.logger:
            self.logger.info("🏥 [HEALTH] Health monitoring thread started")
    
    def _stop_health_monitoring(self) -> None:
        """**Stop Health Monitoring** (dừng giám sát sức khỏe - dừng thread monitoring khi không có active processes)"""
        self.health_monitoring_active = False
        
        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            # Wait for thread to finish
            self.health_monitor_thread.join(timeout=5)
            
        if self.logger:
            self.logger.info("🏥 [HEALTH] Health monitoring thread stopped")
    
    def _health_monitoring_loop(self) -> None:
        """**Health Monitoring Loop** (vòng lặp giám sát sức khỏe - continuous monitoring của hook coordination status)"""
        if self.logger:
            self.logger.info("🏥 [HEALTH] Health monitoring loop started")
        
        while self.health_monitoring_active:
            try:
                current_time = time.time()
                
                # Run health check if interval has passed
                if current_time - self.last_health_check >= self.health_check_interval:
                    self.health_check_continuous()
                    self.last_health_check = current_time
                
                # Sleep for a short interval before next check
                time.sleep(5)  # Check every 5 seconds for timing, run full health check based on interval
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ [HEALTH] Error in health monitoring loop: {e}")
                time.sleep(10)  # Wait longer on error
        
        if self.logger:
            self.logger.info("🏥 [HEALTH] Health monitoring loop ended")
    
    def health_check_continuous(self) -> None:
        """**Continuous Health Check** (kiểm tra sức khỏe liên tục - giám sát hook coordination status cho tất cả active processes)"""
        if self.logger:
            self.logger.debug(f"🏥 [HEALTH] Running health check for {len(self.active_processes)} active processes")
        
        with self.lock:
            processes_to_check = list(self.active_processes)
        
        for pid in processes_to_check:
            try:
                # Verify hook status for each PID
                if not self.verify_hook_status(pid):
                    if self.logger:
                        self.logger.error(f"🚨 [HEALTH] Hook coordination lost for PID {pid}")
                    
                    # Attempt recovery
                    self.attempt_hook_recovery(pid)
                else:
                    # Reset recovery attempts on successful verification
                    with self.lock:
                        self.recovery_attempts[pid] = 0
                    
                    if self.logger:
                        self.logger.debug(f"✅ [HEALTH] PID {pid} hook coordination healthy")
                        
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ [HEALTH] Error checking PID {pid}: {e}")
    
    def verify_hook_status(self, pid: int) -> bool:
        """**Verify Hook Status** (xác minh trạng thái hook - kiểm tra chi tiết hook coordination cho PID cụ thể)"""
        try:
            # Check if process still exists
            if not psutil.pid_exists(pid):
                if self.logger:
                    self.logger.warning(f"⚠️ [HEALTH] PID {pid} no longer exists - removing from tracking")
                self.cleanup_pid(pid)
                return False
            
            # Check hooks_ready status
            with self.lock:
                hooks_ready = self.hooks_ready.get(pid, False)
            
            # Check environment variable consistency
            env_var = f'HOOKS_READY_PID_{pid}'
            env_status = os.environ.get(env_var) == '1'
            
            # Verify consistency between internal state and environment variable
            if hooks_ready != env_status:
                if self.logger:
                    self.logger.warning(f"⚠️ [HEALTH] PID {pid} status inconsistency: internal={hooks_ready}, env={env_status}")
                return False
            
            # Record successful verification
            self._record_status_change(pid, 'health_check', True)
            
            return hooks_ready and env_status
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [HEALTH] Error verifying PID {pid} status: {e}")
            return False
    
    def attempt_hook_recovery(self, pid: int) -> bool:
        """**Attempt Hook Recovery** (thử phục hồi hook - khôi phục hook coordination khi phát hiện lỗi)"""
        try:
            with self.lock:
                current_attempts = self.recovery_attempts.get(pid, 0)
                
                if current_attempts >= self.max_recovery_attempts:
                    if self.logger:
                        self.logger.error(f"💀 [RECOVERY] PID {pid} exceeded max recovery attempts ({self.max_recovery_attempts}) - removing from tracking")
                    self.cleanup_pid(pid)
                    return False
                
                # Increment recovery attempts
                self.recovery_attempts[pid] = current_attempts + 1
            
            if self.logger:
                self.logger.info(f"🔧 [RECOVERY] Attempting recovery for PID {pid} (attempt {current_attempts + 1}/{self.max_recovery_attempts})")
            
            # Recovery steps:
            
            # Step 1: Reset internal state and environment variable
            with self.lock:
                self.hooks_ready[pid] = False
            
            env_var = f'HOOKS_READY_PID_{pid}'
            if env_var in os.environ:
                del os.environ[env_var]
            
            # Step 2: Re-register the PID (without incrementing recovery counter again)
            with self.lock:
                self.hooks_ready[pid] = False
                # Don't call register_pid to avoid double-increment of recovery attempts
            
            # Step 3: Simulate hook readiness notification after brief delay
            time.sleep(2)
            
            # Step 4: Check if process is still alive and responsive
            if psutil.pid_exists(pid):
                # Re-establish hook coordination
                self.notify_hooks_ready(pid)
                
                if self.logger:
                    self.logger.info(f"✅ [RECOVERY] PID {pid} hook coordination restored")
                
                # Record successful recovery
                self._record_status_change(pid, 'recovery_success', True)
                
                return True
            else:
                if self.logger:
                    self.logger.warning(f"⚠️ [RECOVERY] PID {pid} no longer exists during recovery")
                self.cleanup_pid(pid)
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [RECOVERY] Recovery failed for PID {pid}: {e}")
            
            # Record failed recovery
            self._record_status_change(pid, 'recovery_failed', False)
            
            return False
    
    def _record_status_change(self, pid: int, event_type: str, success: bool) -> None:
        """**Record Status Change** (ghi lại thay đổi trạng thái - lưu trữ lịch sử changes cho health monitoring)"""
        try:
            timestamp = time.time()
            status_entry = {
                'timestamp': timestamp,
                'event_type': event_type,
                'success': success,
                'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            }
            
            with self.lock:
                if pid not in self.hook_status_history:
                    self.hook_status_history[pid] = []
                
                self.hook_status_history[pid].append(status_entry)
                
                # Keep only last 50 entries per PID to avoid memory bloat
                if len(self.hook_status_history[pid]) > 50:
                    self.hook_status_history[pid] = self.hook_status_history[pid][-50:]
            
            if self.logger:
                self.logger.debug(f"📝 [HEALTH] Recorded {event_type} for PID {pid}: {success}")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [HEALTH] Error recording status change for PID {pid}: {e}")
    
    def get_health_report(self) -> Dict[str, Any]:
        """**Get Health Report** (lấy báo cáo sức khỏe - trả về comprehensive health status của hook coordination system)"""
        try:
            with self.lock:
                current_time = time.time()
                
                # Basic statistics
                total_processes = len(self.active_processes)
                ready_processes = sum(1 for pid in self.active_processes if self.hooks_ready.get(pid, False))
                
                # Recovery statistics
                total_recovery_attempts = sum(self.recovery_attempts.values())
                processes_with_recoveries = len([pid for pid, attempts in self.recovery_attempts.items() if attempts > 0])
                
                # Health status determination
                if total_processes == 0:
                    health_status = 'IDLE'
                elif ready_processes == total_processes:
                    health_status = 'HEALTHY'
                elif ready_processes > total_processes * 0.7:
                    health_status = 'WARNING'
                else:
                    health_status = 'CRITICAL'
                
                report = {
                    'timestamp': current_time,
                    'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time)),
                    'health_status': health_status,
                    'monitoring_active': self.health_monitoring_active,
                    'statistics': {
                        'total_processes': total_processes,
                        'ready_processes': ready_processes,
                        'pending_processes': total_processes - ready_processes,
                        'ready_percentage': (ready_processes / total_processes * 100) if total_processes > 0 else 0
                    },
                    'recovery_stats': {
                        'total_recovery_attempts': total_recovery_attempts,
                        'processes_with_recoveries': processes_with_recoveries,
                        'max_recovery_attempts': self.max_recovery_attempts
                    },
                    'active_processes': list(self.active_processes),
                    'process_status': {pid: self.hooks_ready.get(pid, False) for pid in self.active_processes},
                    'last_health_check': self.last_health_check,
                    'health_check_interval': self.health_check_interval
                }
                
                return report
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [HEALTH] Error generating health report: {e}")
            
            return {
                'timestamp': time.time(),
                'health_status': 'ERROR',
                'error': str(e),
                'monitoring_active': self.health_monitoring_active
            }
    
    def get_process_health_history(self, pid: int) -> Optional[list]:
        """**Get Process Health History** (lấy lịch sử sức khỏe tiến trình - history của status changes cho PID cụ thể)"""
        with self.lock:
            return self.hook_status_history.get(pid, []).copy() if pid in self.hook_status_history else None

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