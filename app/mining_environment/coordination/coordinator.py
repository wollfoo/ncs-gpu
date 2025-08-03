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
import random
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
        
        # ✅ SYNCHRONIZATION: Race condition prevention attributes
        self.environment_sync_lock = threading.Lock()
        self.verification_retry_config = {
            'max_retries': 2,     # Reduced from 3 for linear flow efficiency
            'base_delay': 0.0005, # Reduced to 0.5ms for linear flow speed
            'max_delay': 0.02,    # Reduced to 20ms for linear flow speed
            'backoff_factor': 1.5 # Reduced backoff for faster recovery
        }
        
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
    
    def receive_from_registry(self, pid: int, handoff_metadata: Dict[str, Any]) -> bool:
        """
        **Receive From Registry** (nhận từ registry)
        
        Enhanced linear flow method cho sequential handoff từ DirectPIDRegistry.
        Replaces parallel registration với structured sequential flow.
        
        Args:
            pid: Process ID từ registry
            handoff_metadata: Metadata từ registry handoff
            
        Returns:
            bool: True nếu handoff successful và coordinator sẵn sàng for next step
        """
        try:
            if self.logger:
                self.logger.info(f"🔄 [LINEAR-RECEIVE] Receiving PID {pid} from registry via sequential handoff")
                self.logger.debug(f"🔍 [LINEAR-RECEIVE] Handoff metadata: {handoff_metadata}")
            
            # **Enhanced registration with handoff context** (đăng ký nâng cao với ngữ cảnh handoff)
            with self.lock:
                self.hooks_ready[pid] = False
                self.active_processes.add(pid)
                self.hook_status_history[pid] = []
                self.recovery_attempts[pid] = 0
                
                # **Store handoff metadata** (lưu trữ metadata handoff) for tracking
                if pid not in self.hook_status_history:
                    self.hook_status_history[pid] = []
                
                # **Record linear handoff event** (ghi lại sự kiện handoff tuyến tính)
                handoff_record = {
                    'timestamp': handoff_metadata.get('handoff_timestamp', time.time()),
                    'event_type': 'linear_handoff_received',
                    'success': True,
                    'source': handoff_metadata.get('source', 'unknown'),
                    'time_str': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                self.hook_status_history[pid].append(handoff_record)
                
                # **Auto-start health monitoring** (tự động khởi động giám sát sức khỏe)
                if not self.health_monitoring_active:
                    self._start_health_monitoring()
            
            # **Trigger next step in linear flow** (kích hoạt bước tiếp theo trong luồng tuyến tính)
            next_step_success = self._handoff_to_resource_manager(pid, handoff_metadata)
            
            if next_step_success:
                if self.logger:
                    self.logger.info(f"✅ [LINEAR-RECEIVE] PID {pid} successfully received và handed off to resource manager")
                return True
            else:
                if self.logger:
                    self.logger.warning(f"⚠️ [LINEAR-RECEIVE] PID {pid} received but handoff to resource manager failed")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [LINEAR-RECEIVE] Failed to receive PID {pid} from registry: {e}")
            
            # **Fallback to standard registration** (dự phòng đăng ký tiêu chuẩn)
            try:
                self.register_pid(pid)
                if self.logger:
                    self.logger.info(f"✅ [LINEAR-RECEIVE] Fallback registration successful for PID {pid}")
                return True
            except Exception as fallback_err:
                if self.logger:
                    self.logger.error(f"❌ [LINEAR-RECEIVE] Fallback registration failed for PID {pid}: {fallback_err}")
                return False
            
    def notify_hooks_ready(self, pid: int) -> None:
        """**Notify Hooks Ready** (thông báo hooks sẵn sàng - báo hiệu hoàn thành PHASE 3+ initialization)"""
        # ✅ SYNCHRONIZATION: Thread-safe notification with environment sync
        success = self._sync_hooks_ready_state(pid, True)
        
        if success:
            # ✅ HEALTH TRACKING: Record status change in history
            self._record_status_change(pid, 'hooks_ready', True)
            
            if self.logger:
                self.logger.info(f"✅ [NOTIFY] PID {pid} hooks ready - synchronized state set")
                self.logger.debug(f"🔍 [DEBUG] Current hooks_ready state: {dict(list(self.hooks_ready.items())[-5:])}")
                self.logger.info(f"🏥 [HEALTH] Status change recorded for PID {pid}")
        else:
            if self.logger:
                self.logger.error(f"❌ [NOTIFY] Failed to synchronize hooks ready state for PID {pid}")
            
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
    
    def _handoff_to_resource_manager(self, pid: int, coordinator_metadata: Dict[str, Any]) -> bool:
        """
        **Handoff to Resource Manager** (chuyển giao đến resource manager)
        
        Sequential handoff từ Hook Coordinator đến Resource Manager trong linear flow.
        
        Args:
            pid: Process ID để handoff
            coordinator_metadata: Metadata từ coordinator
            
        Returns:
            bool: True nếu handoff successful
        """
        try:
            if self.logger:
                self.logger.info(f"🔄 [COORDINATOR-HANDOFF] Initiating handoff to resource manager for PID {pid}")
            
            # **Dynamic import Resource Manager** (nhập động Resource Manager)
            import sys
            import os
            from pathlib import Path
            
            # Add scripts module to path
            scripts_path = Path(__file__).parent.parent / "scripts"
            if str(scripts_path) not in sys.path:
                sys.path.insert(0, str(scripts_path))
            
            try:
                from resource_manager import ResourceManager
                
                # **Check for global resource manager instance** (kiểm tra instance resource manager toàn cục)
                # Note: In linear flow, resource manager is typically started by main thread
                # We attempt to notify existing instance rather than creating new one
                
                # **Enhanced handoff metadata** (metadata chuyển giao nâng cao)
                enhanced_metadata = {
                    'source': 'hook_coordinator',
                    'coordinator_timestamp': time.time(),
                    'original_metadata': coordinator_metadata,
                    'hooks_ready': self.hooks_ready.get(pid, False),
                    'handoff_chain': ['stealth_inference_cuda', 'direct_registry', 'hook_coordinator']
                }
                
                # **Attempt to find and notify existing resource manager** (thử tìm và thông báo resource manager hiện có)
                # This simulates the linear handoff to resource manager
                success = self._notify_resource_manager(pid, enhanced_metadata)
                
                if success:
                    if self.logger:
                        self.logger.info(f"✅ [COORDINATOR-HANDOFF] Resource manager handoff successful for PID {pid}")
                    return True
                else:
                    if self.logger:
                        self.logger.warning(f"⚠️ [COORDINATOR-HANDOFF] Resource manager handoff failed for PID {pid}")
                    return False
                    
            except ImportError as import_err:
                if self.logger:
                    self.logger.error(f"❌ [COORDINATOR-HANDOFF] Cannot import ResourceManager: {import_err}")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [COORDINATOR-HANDOFF] Handoff to resource manager failed for PID {pid}: {e}")
            return False
    
    def _notify_resource_manager(self, pid: int, handoff_metadata: Dict[str, Any]) -> bool:
        """
        **Notify Resource Manager** (thông báo resource manager)
        
        Simulate linear handoff notification to resource manager.
        In actual implementation, this would trigger resource manager's receive_from_coordinator method.
        
        Args:
            pid: Process ID
            handoff_metadata: Handoff metadata
            
        Returns:
            bool: True nếu notification successful
        """
        try:
            # **Store notification for resource manager pickup** (lưu trữ thông báo cho resource manager nhận)
            # This simulates the handoff - in real implementation, resource manager would have
            # a receive_from_coordinator method that gets called directly
            
            import os
            notification_key = f"LINEAR_HANDOFF_RM_PID_{pid}"
            notification_data = f"{handoff_metadata.get('coordinator_timestamp', time.time())}"
            
            # **Environment variable as handoff signal** (biến môi trường như tín hiệu handoff)
            os.environ[notification_key] = notification_data
            
            if self.logger:
                self.logger.debug(f"🔔 [COORDINATOR-HANDOFF] Notification stored for resource manager: {notification_key}")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [COORDINATOR-HANDOFF] Failed to notify resource manager for PID {pid}: {e}")
            return False
    
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
        """**Verify Hook Status** (xác minh trạng thái hook - kiểm tra chi tiết hook coordination với retry mechanism)"""
        retry_config = self.verification_retry_config
        
        for attempt in range(retry_config['max_retries']):
            try:
                # Check if process still exists
                if not psutil.pid_exists(pid):
                    if self.logger:
                        self.logger.warning(f"⚠️ [HEALTH] PID {pid} no longer exists - removing from tracking")
                    self.cleanup_pid(pid)
                    return False
                
                # ✅ SYNCHRONIZATION: Verify with retry and exponential backoff
                verification_result = self._verify_with_retry(pid, attempt)
                
                if verification_result['success']:
                    # Record successful verification
                    self._record_status_change(pid, 'health_check', True)
                    return verification_result['hooks_ready']
                elif verification_result['should_retry'] and attempt < retry_config['max_retries'] - 1:
                    # Calculate exponential backoff delay
                    delay = min(
                        retry_config['base_delay'] * (retry_config['backoff_factor'] ** attempt),
                        retry_config['max_delay']
                    )
                    # Add jitter to prevent thundering herd
                    jitter = random.uniform(0, 0.1)
                    total_delay = delay + jitter
                    
                    if self.logger:
                        self.logger.debug(f"🔄 [VERIFY] PID {pid} retry {attempt + 1}/{retry_config['max_retries']} after {total_delay:.3f}s")
                    
                    time.sleep(total_delay)
                    continue
                else:
                    # Final failure or non-retryable error
                    if self.logger:
                        self.logger.warning(f"⚠️ [HEALTH] PID {pid} verification failed after {attempt + 1} attempts")
                    return False
                    
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ [HEALTH] Error verifying PID {pid} status (attempt {attempt + 1}): {e}")
                
                if attempt < retry_config['max_retries'] - 1:
                    time.sleep(retry_config['base_delay'])
                    continue
                else:
                    return False
        
        return False
    
    def _sync_hooks_ready_state(self, pid: int, ready_state: bool) -> bool:
        """**Sync Hooks Ready State** (đồng bộ trạng thái hooks - thread-safe synchronization của internal và environment state)"""
        try:
            with self.environment_sync_lock:
                with self.lock:
                    # Update internal state
                    self.hooks_ready[pid] = ready_state
                    
                    # Synchronize environment variable
                    env_var = f'HOOKS_READY_PID_{pid}'
                    if ready_state:
                        os.environ[env_var] = '1'
                    else:
                        os.environ.pop(env_var, None)
                    
                    # Minimal delay to ensure synchronization without performance impact
                    time.sleep(0.0001)  # 0.1ms synchronization delay
                    
                    # Verify synchronization
                    internal_state = self.hooks_ready.get(pid, False)
                    env_state = os.environ.get(env_var) == '1'
                    
                    if internal_state == ready_state and env_state == ready_state:
                        if self.logger:
                            self.logger.debug(f"🔄 [SYNC] PID {pid} state synchronized: {ready_state}")
                        return True
                    else:
                        if self.logger:
                            self.logger.error(f"❌ [SYNC] PID {pid} synchronization failed: internal={internal_state}, env={env_state}, expected={ready_state}")
                        return False
                        
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [SYNC] Error synchronizing PID {pid} state: {e}")
            return False
    
    def _verify_with_retry(self, pid: int, attempt: int) -> Dict[str, any]:
        """**Verify With Retry** (xác minh với retry - single verification attempt với detailed result)"""
        try:
            # Check hooks_ready status with lock
            with self.lock:
                hooks_ready = self.hooks_ready.get(pid, False)
            
            # Check environment variable consistency
            env_var = f'HOOKS_READY_PID_{pid}'
            env_status = os.environ.get(env_var) == '1'
            
            # Verify consistency between internal state and environment variable
            if hooks_ready != env_status:
                if self.logger:
                    self.logger.warning(f"⚠️ [VERIFY] PID {pid} inconsistency (attempt {attempt + 1}): internal={hooks_ready}, env={env_status}")
                
                # Try to sync environment state if this is not the last attempt
                if attempt < self.verification_retry_config['max_retries'] - 1:
                    sync_success = self.sync_environment_state(pid)
                    return {
                        'success': False,
                        'should_retry': True,
                        'hooks_ready': False,
                        'sync_attempted': sync_success,
                        'inconsistency_detected': True
                    }
                else:
                    return {
                        'success': False,
                        'should_retry': False,
                        'hooks_ready': False,
                        'inconsistency_detected': True
                    }
            
            # States are consistent
            return {
                'success': True,
                'should_retry': False,
                'hooks_ready': hooks_ready and env_status,
                'inconsistency_detected': False
            }
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [VERIFY] Error in verification attempt {attempt + 1} for PID {pid}: {e}")
            
            return {
                'success': False,
                'should_retry': True,  # Retry on exception unless it's the last attempt
                'hooks_ready': False,
                'error': str(e)
            }
    
    def sync_environment_state(self, pid: int) -> bool:
        """**Sync Environment State** (đồng bộ trạng thái environment - force sync environment variable với internal state)"""
        try:
            with self.environment_sync_lock:
                with self.lock:
                    internal_state = self.hooks_ready.get(pid, False)
                
                env_var = f'HOOKS_READY_PID_{pid}'
                
                # Sync environment to match internal state
                if internal_state:
                    os.environ[env_var] = '1'
                else:
                    os.environ.pop(env_var, None)
                
                # Verify sync success
                env_state = os.environ.get(env_var) == '1'
                sync_success = (internal_state == env_state)
                
                if self.logger:
                    if sync_success:
                        self.logger.debug(f"🔄 [ENV_SYNC] PID {pid} environment synced to: {internal_state}")
                    else:
                        self.logger.error(f"❌ [ENV_SYNC] PID {pid} sync failed: internal={internal_state}, env={env_state}")
                
                return sync_success
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [ENV_SYNC] Error syncing environment for PID {pid}: {e}")
            return False
    
    def attempt_hook_recovery(self, pid: int) -> bool:
        """**Attempt Hook Recovery** (thử phục hồi hook - comprehensive recovery với enhanced synchronization và state validation)"""
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
                self.logger.info(f"🔧 [RECOVERY] Enhanced recovery for PID {pid} (attempt {current_attempts + 1}/{self.max_recovery_attempts})")
            
            # Enhanced Recovery Strategy:
            
            # Step 1: Comprehensive state validation
            process_exists = psutil.pid_exists(pid)
            if not process_exists:
                if self.logger:
                    self.logger.warning(f"⚠️ [RECOVERY] PID {pid} no longer exists during recovery initiation")
                self.cleanup_pid(pid)
                return False
            
            # Step 2: Reset states with synchronized clearing
            reset_success = self._sync_hooks_ready_state(pid, False)
            if not reset_success:
                if self.logger:
                    self.logger.error(f"❌ [RECOVERY] Failed to reset state for PID {pid}")
                return False
            
            # Step 3: Optimized recovery delay for performance
            recovery_delay = min(0.01 + (current_attempts * 0.005), 0.05)  # Progressive delay: 10ms, 15ms, 20ms, max 50ms
            
            if self.logger:
                self.logger.debug(f"⏳ [RECOVERY] PID {pid} waiting {recovery_delay*1000:.1f}ms for state stabilization")
            
            time.sleep(recovery_delay)
            
            # Step 4: Verify process is still responsive
            if not psutil.pid_exists(pid):
                if self.logger:
                    self.logger.warning(f"⚠️ [RECOVERY] PID {pid} disappeared during recovery")
                self.cleanup_pid(pid)
                return False
            
            # Step 5: Re-establish hook coordination with enhanced sync
            restore_success = self._sync_hooks_ready_state(pid, True)
            
            if restore_success:
                # Step 6: Validate recovery success
                validation_success = self._validate_recovery(pid)
                
                if validation_success:
                    if self.logger:
                        self.logger.info(f"✅ [RECOVERY] PID {pid} hook coordination fully restored and validated")
                    
                    # Record successful recovery
                    self._record_status_change(pid, 'recovery_success', True)
                    
                    # Reset recovery attempts on success
                    with self.lock:
                        self.recovery_attempts[pid] = 0
                    
                    return True
                else:
                    if self.logger:
                        self.logger.error(f"❌ [RECOVERY] PID {pid} restoration failed validation")
                    return False
            else:
                if self.logger:
                    self.logger.error(f"❌ [RECOVERY] Failed to restore hook state for PID {pid}")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [RECOVERY] Enhanced recovery failed for PID {pid}: {e}")
            
            # Record failed recovery
            self._record_status_change(pid, 'recovery_failed', False)
            
            return False
    
    def _validate_recovery(self, pid: int) -> bool:
        """**Validate Recovery** (xác thực phục hồi - comprehensive validation của recovery success)"""
        try:
            # Minimal wait for state stabilization
            time.sleep(0.001)
            
            # Multi-layer validation
            validations = []
            
            # Validation 1: Process existence
            process_exists = psutil.pid_exists(pid)
            validations.append(('process_exists', process_exists))
            
            # Validation 2: Internal state consistency
            with self.lock:
                internal_ready = self.hooks_ready.get(pid, False)
            validations.append(('internal_state', internal_ready))
            
            # Validation 3: Environment variable consistency  
            env_var = f'HOOKS_READY_PID_{pid}'
            env_ready = os.environ.get(env_var) == '1'
            validations.append(('env_state', env_ready))
            
            # Validation 4: State synchronization
            state_sync = (internal_ready == env_ready == True)
            validations.append(('state_sync', state_sync))
            
            # Validation 5: PID tracking consistency
            with self.lock:
                is_tracked = pid in self.active_processes
            validations.append(('tracking_consistency', is_tracked))
            
            # Evaluate overall validation
            all_valid = all(result for _, result in validations)
            
            if self.logger:
                validation_status = ", ".join([f"{name}={result}" for name, result in validations])
                self.logger.debug(f"🔍 [VALIDATION] PID {pid} recovery validation: {validation_status}")
            
            return all_valid
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [VALIDATION] Error validating recovery for PID {pid}: {e}")
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
                
                # Keep only last 25 entries per PID for memory optimization in linear flow
                if len(self.hook_status_history[pid]) > 25:
                    self.hook_status_history[pid] = self.hook_status_history[pid][-25:]
            
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