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
import hashlib
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
        
        # ✅ IDEMPOTENCY PROTECTION: Handoff deduplication system
        self.handoff_timestamps: Dict[int, float] = {}  # Track last handoff time per PID
        self.handoff_metadata_cache: Dict[int, Dict[str, Any]] = {}  # Cache handoff metadata
        self.duplicate_detection_window: float = 5.0  # 5-second deduplication window
        self.handoff_sequence_numbers: Dict[int, int] = {}  # Track handoff sequence per PID
        
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
    
    def receive_from_stealth_wrapper(self, pid: int, process_metadata: Dict[str, Any]) -> bool:
        """
        **Receive From Stealth Wrapper** (nhận từ stealth wrapper)
        
        NEW METHOD: Primary entry point cho linear flow từ stealth_inference_cuda.py.
        Implements CORRECT flow: stealth → HookCoordinator → DirectPIDRegistry → ResourceManager
        
        Args:
            pid: Process ID từ stealth wrapper
            process_metadata: Metadata từ stealth wrapper
            
        Returns:
            bool: True nếu handoff successful và ready for next step
        """
        try:
            current_time = time.time()
            
            if self.logger:
                self.logger.info(f"🚀 [LINEAR-FLOW] Receiving PID {pid} from stealth wrapper (PRIMARY ENTRY POINT)")
                self.logger.debug(f"🔍 [LINEAR-FLOW] Process metadata: {process_metadata}")
            
            # **STEP 1: Register PID với HookCoordinator** (đăng ký PID với HookCoordinator)
            with self.lock:
                self.hooks_ready[pid] = False  # Initialize as not ready
                self.active_processes.add(pid)
                
                # Initialize tracking data
                if pid not in self.hook_status_history:
                    self.hook_status_history[pid] = []
                if pid not in self.recovery_attempts:
                    self.recovery_attempts[pid] = 0
                
                # Record stealth handoff event
                handoff_record = {
                    'timestamp': current_time,
                    'event_type': 'stealth_handoff_received',
                    'success': True,
                    'source': 'stealth_inference_cuda',
                    'metadata': process_metadata,
                    'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))
                }
                self.hook_status_history[pid].append(handoff_record)
                
                if self.logger:
                    self.logger.info(f"✅ [LINEAR-FLOW] PID {pid} registered with HookCoordinator")
            
            # **STEP 2: Forward to DirectPIDRegistry** (chuyển tiếp đến DirectPIDRegistry)
            registry_success = self._forward_to_direct_registry(pid, process_metadata)
            
            if registry_success:
                if self.logger:
                    self.logger.info(f"✅ [LINEAR-FLOW] PID {pid} successfully forwarded to DirectPIDRegistry")
                return True
            else:
                if self.logger:
                    self.logger.warning(f"⚠️ [LINEAR-FLOW] DirectPIDRegistry forwarding failed for PID {pid}")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [LINEAR-FLOW] Failed to receive from stealth wrapper for PID {pid}: {e}")
            return False
    
    # REMOVED: receive_from_registry method - obsolete with new linear flow
            
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
        """**Enhanced Cleanup PID** (dọn dẹp PID nâng cao - xóa tiến trình khỏi tất cả hệ thống theo dõi)"""
        with self.lock:
            was_tracked = pid in self.hooks_ready
            self.hooks_ready.pop(pid, None)
            self.active_processes.discard(pid)
            self.hook_status_history.pop(pid, None)
            self.recovery_attempts.pop(pid, None)
            
            # ✅ IDEMPOTENCY CLEANUP: Remove handoff tracking data
            self.handoff_timestamps.pop(pid, None)
            self.handoff_metadata_cache.pop(pid, None)
            self.handoff_sequence_numbers.pop(pid, None)
            
            # **Enhanced Environment Cleanup** (dọn dẹp môi trường nâng cao)
            env_vars_cleaned = []
            
            # Core hook coordination variables
            env_var = f'HOOKS_READY_PID_{pid}'
            if env_var in os.environ:
                del os.environ[env_var]
                env_vars_cleaned.append(env_var)
            
            # Linear handoff variables
            handoff_var = f'LINEAR_HANDOFF_RM_PID_{pid}'
            if handoff_var in os.environ:
                del os.environ[handoff_var]
                env_vars_cleaned.append(handoff_var)
            
            # Pickup detection variables
            pickup_var = f'RM_PICKUP_READY_PID_{pid}'
            if pickup_var in os.environ:
                del os.environ[pickup_var]
                env_vars_cleaned.append(pickup_var)
            
            # Deferred handoff variables
            deferred_var = f'DEFERRED_RM_HANDOFF_PID_{pid}'
            if deferred_var in os.environ:
                del os.environ[deferred_var]
                env_vars_cleaned.append(deferred_var)
            
            if self.logger and was_tracked:
                self.logger.info(f"🧹 [CLEANUP] PID {pid} removed from all tracking systems")
                if env_vars_cleaned:
                    self.logger.info(f"📝 [CLEANUP] Environment variables cleaned: {env_vars_cleaned}")
                self.logger.info(f"🏥 [HEALTH] Health monitoring cleanup for PID {pid} completed")
                
            # ✅ HEALTH MONITORING: Stop monitoring if no active processes
            if len(self.active_processes) == 0 and self.health_monitoring_active:
                self._stop_health_monitoring()
    
    # ===== IDEMPOTENCY PROTECTION HELPER METHODS =====
    
    def _generate_handoff_fingerprint(self, handoff_metadata: Dict[str, Any]) -> str:
        """
        **Generate Handoff Fingerprint** (tạo vân tay handoff)
        
        ✅ ENHANCED: Creates consistent fingerprint với metadata normalization để detect duplicate handoffs.
        Fixes metadata structure inconsistency between duplicate handoffs.
        
        Args:
            handoff_metadata: Metadata của handoff
            
        Returns:
            str: Unique fingerprint string
        """
        try:
            # ✅ REDESIGNED: Focus on STABLE PROCESS IDENTITY, not handoff artifacts
            # Extract stable process identification only
            process_info = handoff_metadata.get('original_metadata', handoff_metadata)
            
            # ✅ CORE PROCESS IDENTITY - These fields uniquely identify the process
            registration_source = (process_info.get('registration_source') or 
                                 handoff_metadata.get('registration_source', 'unknown'))
            
            # Use process creation timestamp, not handoff timing
            process_timestamp = (process_info.get('timestamp') or 
                               handoff_metadata.get('timestamp', 0))
            
            # ✅ NORMALIZE: Round to nearest second to eliminate timing variance
            process_timestamp = round(process_timestamp) if process_timestamp else 0
            
            # Extract process identification consistently
            if isinstance(process_info, dict):
                executable = process_info.get('executable', 'inference-cuda')
                role = process_info.get('role', 'unknown')
                stealth_name = process_info.get('stealth_name', 'unknown')
            else:
                executable = 'inference-cuda'  # Default for mining process
                role = 'unknown'
                stealth_name = 'unknown'
            
            # ✅ PROCESS-IDENTITY FINGERPRINT - Stable process characteristics only
            fingerprint_elements = [
                str(registration_source),  # How process was registered (stable)
                str(process_timestamp),    # When process was created (stable, rounded)
                str(executable),           # What executable is running (stable)
                str(role),                # Process role (stable)
                str(stealth_name)         # Process stealth identity (stable)
            ]
            
            # Generate consistent hash
            fingerprint_data = '|'.join(fingerprint_elements)
            fingerprint = hashlib.md5(fingerprint_data.encode('utf-8')).hexdigest()
            
            if self.logger:
                self.logger.debug(f"🔍 [PROCESS-FINGERPRINT] Generated: {fingerprint} from: {fingerprint_data}")
                self.logger.debug(f"🔍 [PROCESS-DEBUG] Registration: {registration_source}, Process time: {process_timestamp}, Role: {role}, Name: {stealth_name}")
            
            return fingerprint
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [ENHANCED-FINGERPRINT] Error generating handoff fingerprint: {e}")
            
            # ✅ ENHANCED FALLBACK - Use more stable fallback
            try:
                fallback_data = f"{handoff_metadata.get('source', 'unknown')}|{handoff_metadata.get('timestamp', 0)}"
                return hashlib.md5(fallback_data.encode('utf-8')).hexdigest()
            except:
                return hashlib.md5(str(handoff_metadata).encode('utf-8')).hexdigest()
    
    def _record_duplicate_handoff(self, pid: int, handoff_metadata: Dict[str, Any], sequence_number: int, detection_method: list = None) -> None:
        """
        **Record Duplicate Handoff** (ghi lại handoff trùng lặp)
        
        ✅ ENHANCED: Records duplicate handoff event với detailed detection information for monitoring.
        
        Args:
            pid: Process ID
            handoff_metadata: Metadata của duplicate handoff
            sequence_number: Sequence number của handoff
            detection_method: List of detection methods used (fingerprint, source, role)
        """
        try:
            timestamp = time.time()
            duplicate_record = {
                'timestamp': timestamp,
                'event_type': 'duplicate_handoff_detected',
                'success': True,  # Successfully detected and handled
                'source': handoff_metadata.get('source', 'unknown'),
                'sequence_number': sequence_number,
                'fingerprint': self._generate_handoff_fingerprint(handoff_metadata),
                'preserved_state': self.hooks_ready.get(pid, False),
                'detection_method': detection_method or ['unknown'],  # ✅ NEW: Detection method tracking
                'detection_method_str': '+'.join(detection_method) if detection_method else 'unknown',  # ✅ NEW: Readable format
                'metadata_has_handoff_timestamp': 'handoff_timestamp' in handoff_metadata,  # ✅ NEW: Timestamp presence tracking
                'metadata_has_original_metadata': 'original_metadata' in handoff_metadata,  # ✅ NEW: Structure tracking
                'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            }
            
            with self.lock:
                if pid in self.hook_status_history:
                    self.hook_status_history[pid].append(duplicate_record)
                    
                    # Keep history manageable
                    if len(self.hook_status_history[pid]) > 25:
                        self.hook_status_history[pid] = self.hook_status_history[pid][-25:]
            
            if self.logger:
                self.logger.debug(f"📝 [DUPLICATE] Recorded duplicate handoff event for PID {pid} (seq: {sequence_number})")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [DUPLICATE] Error recording duplicate handoff for PID {pid}: {e}")
    
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
    
    def _forward_to_direct_registry(self, pid: int, process_metadata: Dict[str, Any]) -> bool:
        """
        **🥈 SOLUTION 2: Enhanced Forward to DirectPIDRegistry** (chuyển tiếp nâng cao đến DirectPIDRegistry)
        
        Forward process từ HookCoordinator đến DirectPIDRegistry với enhanced reliability và acknowledgment system.
        
        Args:
            pid: Process ID
            process_metadata: Metadata từ stealth wrapper
            
        Returns:
            bool: True nếu forwarding successful với acknowledgment
        """
        try:
            if self.logger:
                self.logger.info(f"🔄 [SOLUTION-2] Enhanced forwarding PID {pid} to DirectPIDRegistry")
            
            # **🥈 SOLUTION 2: Enhanced Retry Logic** (logic thử lại nâng cao)
            max_retries = 3
            retry_delay = 0.1  # 100ms
            
            for attempt in range(max_retries):
                try:
                    if self.logger:
                        self.logger.debug(f"🔄 [HANDOFF-RETRY] PID {pid} attempt {attempt + 1}/{max_retries}")
                    
                    # **Import DirectPIDRegistry** (nhập DirectPIDRegistry)
                    from pid_logger.direct_registry import get_direct_registry
                    
                    # **Get DirectPIDRegistry singleton** (lấy singleton DirectPIDRegistry)
                    registry = get_direct_registry()
                    
                    # **🥈 SOLUTION 2: Enhanced Handoff Metadata** (metadata handoff nâng cao)
                    handoff_timestamp = time.time()
                    registry_metadata = {
                        **process_metadata,  # Include original metadata
                        'coordinator_timestamp': handoff_timestamp,
                        'handoff_attempt': attempt + 1,
                        'max_handoff_attempts': max_retries,
                        'source_chain': ['stealth_inference_cuda', 'hook_coordinator'],
                        'coordinator_handoff': True,
                        'handoff_id': f"HC-{pid}-{int(handoff_timestamp * 1000)}",  # Unique handoff ID
                        'acknowledgment_required': True,
                        'bidirectional_communication': True
                    }
                    
                    # **🥈 SOLUTION 2: Call with Acknowledgment** (gọi với acknowledgment)
                    success = registry.receive_from_coordinator(pid, registry_metadata)
                    
                    if success:
                        # **🥈 SOLUTION 2: Wait for Acknowledgment** (chờ acknowledgment)
                        ack_success = self._wait_for_registry_acknowledgment(pid, handoff_timestamp, timeout=2.0)
                        
                        if ack_success:
                            if self.logger:
                                self.logger.info(f"✅ [SOLUTION-2] DirectPIDRegistry handoff successful với acknowledgment for PID {pid}")
                            
                            # **🥈 SOLUTION 2: Record Successful Handoff** (ghi lại handoff thành công)
                            self._record_handoff_success(pid, handoff_timestamp, attempt + 1)
                            return True
                        else:
                            if self.logger:
                                self.logger.warning(f"⚠️ [SOLUTION-2] DirectPIDRegistry handoff without acknowledgment for PID {pid}, attempt {attempt + 1}")
                            
                            # If this is the last attempt, still consider it successful if registry accepted
                            if attempt == max_retries - 1:
                                if self.logger:
                                    self.logger.info(f"✅ [SOLUTION-2] Final attempt success despite missing acknowledgment for PID {pid}")
                                return True
                    else:
                        if self.logger:
                            self.logger.warning(f"⚠️ [SOLUTION-2] DirectPIDRegistry registration failed for PID {pid}, attempt {attempt + 1}")
                    
                    # **🥈 SOLUTION 2: Retry Delay** (độ trễ thử lại)
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                        
                except ImportError as import_err:
                    if self.logger:
                        self.logger.error(f"❌ [SOLUTION-2] Cannot import DirectPIDRegistry: {import_err}")
                        self.logger.error("💡 [FIX-HINT] Check if psutil dependency is installed: pip install psutil")
                    return False
                    
                except Exception as attempt_err:
                    if self.logger:
                        self.logger.error(f"❌ [SOLUTION-2] Handoff attempt {attempt + 1} failed for PID {pid}: {attempt_err}")
                    
                    if attempt == max_retries - 1:
                        raise attempt_err
                    
                    time.sleep(retry_delay)
                    retry_delay *= 1.5
            
            # **All attempts failed** (tất cả lần thử đều thất bại)
            if self.logger:
                self.logger.error(f"❌ [SOLUTION-2] All {max_retries} handoff attempts failed for PID {pid}")
            return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [SOLUTION-2] Enhanced handoff failed for PID {pid}: {e}")
            return False
    
    def _wait_for_registry_acknowledgment(self, pid: int, handoff_timestamp: float, timeout: float = 2.0) -> bool:
        """
        **🥈 SOLUTION 2: Wait for Registry Acknowledgment** (chờ acknowledgment từ registry)
        
        Wait for DirectPIDRegistry để acknowledge successful handoff.
        
        Args:
            pid: Process ID
            handoff_timestamp: Timestamp của handoff
            timeout: Timeout in seconds
            
        Returns:
            bool: True nếu acknowledgment received
        """
        try:
            # **🥈 SOLUTION 2: Environment Variable-based Acknowledgment** (acknowledgment qua biến môi trường)
            ack_env_var = f"REGISTRY_ACK_PID_{pid}"
            start_time = time.time()
            
            if self.logger:
                self.logger.debug(f"⏳ [ACK-WAIT] Waiting for DirectPIDRegistry acknowledgment for PID {pid}")
            
            while time.time() - start_time < timeout:
                # **Check for acknowledgment signal** (kiểm tra tín hiệu acknowledgment)
                ack_value = os.environ.get(ack_env_var)
                
                if ack_value:
                    try:
                        ack_timestamp = float(ack_value)
                        
                        # **Verify acknowledgment is for current handoff** (xác minh acknowledgment cho handoff hiện tại)
                        if ack_timestamp >= handoff_timestamp - 1.0:  # Allow 1 second tolerance
                            if self.logger:
                                elapsed = time.time() - start_time
                                self.logger.debug(f"✅ [ACK-WAIT] Registry acknowledgment received for PID {pid} after {elapsed*1000:.1f}ms")
                            
                            # **Clean up acknowledgment variable** (dọn dẹp biến acknowledgment)
                            os.environ.pop(ack_env_var, None)
                            return True
                    except ValueError:
                        # Invalid acknowledgment format, ignore and continue
                        pass
                
                time.sleep(0.01)  # Check every 10ms
            
            # **Timeout reached** (đã timeout)
            if self.logger:
                self.logger.warning(f"⏰ [ACK-WAIT] Acknowledgment timeout for PID {pid} after {timeout}s")
            
            # **Clean up acknowledgment variable on timeout** (dọn dẹp biến acknowledgment khi timeout)
            os.environ.pop(ack_env_var, None)
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [ACK-WAIT] Error waiting for acknowledgment for PID {pid}: {e}")
            return False
    
    def _record_handoff_success(self, pid: int, handoff_timestamp: float, attempt_number: int) -> None:
        """
        **🥈 SOLUTION 2: Record Handoff Success** (ghi lại thành công handoff)
        
        Record successful handoff với acknowledgment system tracking.
        """
        try:
            handoff_record = {
                'timestamp': handoff_timestamp,
                'event_type': 'coordinator_handoff_success',
                'success': True,
                'target': 'direct_pid_registry',
                'attempt_number': attempt_number,
                'acknowledgment_received': True,
                'handoff_duration_ms': (time.time() - handoff_timestamp) * 1000,
                'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(handoff_timestamp))
            }
            
            with self.lock:
                # **Update handoff tracking** (cập nhật theo dõi handoff)
                self.handoff_timestamps[pid] = handoff_timestamp
                
                # **Record in history** (ghi vào lịch sử)
                if pid in self.hook_status_history:
                    self.hook_status_history[pid].append(handoff_record)
                    
                    # Keep history manageable
                    if len(self.hook_status_history[pid]) > 25:
                        self.hook_status_history[pid] = self.hook_status_history[pid][-25:]
            
            if self.logger:
                duration = handoff_record['handoff_duration_ms']
                self.logger.info(f"📝 [HANDOFF-SUCCESS] Recorded successful handoff for PID {pid} "
                               f"(attempt: {attempt_number}, duration: {duration:.1f}ms)")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [HANDOFF-SUCCESS] Error recording handoff success for PID {pid}: {e}")
    
    def provide_acknowledgment_to_stealth(self, pid: int, success: bool, details: Dict[str, Any] = None) -> None:
        """
        **🥈 SOLUTION 2: Provide Acknowledgment to Stealth** (cung cấp acknowledgment cho stealth)
        
        Send acknowledgment back to stealth_inference_cuda về handoff status.
        
        Args:
            pid: Process ID
            success: Whether handoff was successful
            details: Additional details about handoff result
        """
        try:
            # **🥈 SOLUTION 2: Bidirectional Communication** (giao tiếp hai chiều)
            ack_env_var = f"COORDINATOR_ACK_PID_{pid}"
            ack_timestamp = time.time()
            
            ack_data = {
                'success': success,
                'timestamp': ack_timestamp,
                'details': details or {},
                'source': 'hook_coordinator'
            }
            
            # **Set acknowledgment environment variable** (đặt biến môi trường acknowledgment)
            os.environ[ack_env_var] = json.dumps(ack_data)
            
            if self.logger:
                self.logger.debug(f"📤 [BIDIRECTIONAL] Sent acknowledgment to stealth for PID {pid}: {success}")
            
            # **Schedule cleanup** (lên lịch dọn dẹp)
            # Clean up after 30 seconds to prevent environment variable buildup
            def cleanup_ack():
                time.sleep(30.0)
                os.environ.pop(ack_env_var, None)
            
            cleanup_thread = threading.Thread(target=cleanup_ack, daemon=True)
            cleanup_thread.start()
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [BIDIRECTIONAL] Error providing acknowledgment to stealth for PID {pid}: {e}")

    # REMOVED: _handoff_to_resource_manager method - obsolete with new linear flow
    
    # REMOVED: _defer_resource_manager_handoff method - obsolete with new linear flow
    
    # REMOVED: _notify_resource_manager method - obsolete with new linear flow
    
    def health_check_continuous(self) -> None:
        """**Continuous Health Check** (kiểm tra sức khỏe liên tục - giám sát hook coordination status cho tất cả active processes)"""
        if self.logger:
            self.logger.debug(f"🏥 [HEALTH] Running health check for {len(self.active_processes)} active processes")
        
        with self.lock:
            processes_to_check = list(self.active_processes)
        
        for pid in processes_to_check:
            try:
                # ✅ ENHANCED FIX: Skip health check for recent handoffs to prevent race conditions
                with self.lock:
                    last_handoff_time = self.handoff_timestamps.get(pid, 0)
                
                current_time = time.time()
                time_since_handoff = current_time - last_handoff_time
                # ✅ HEALTH_CHECK_PROTECTION_PERIOD: Enhanced protection for handoff coordination
                handoff_protection_period = 5.0  # 5-second protection period for new handoffs (increased from 3.0s)
                
                if time_since_handoff < handoff_protection_period:
                    if self.logger:
                        self.logger.debug(f"⏳ [HEALTH] Skipping health check for PID {pid} - recent handoff "
                                        f"({time_since_handoff:.2f}s ago, protection: {handoff_protection_period}s)")
                    continue
                
                # Verify hook status for each PID
                if not self.verify_hook_status(pid):
                    # ✅ ENHANCED DIAGNOSIS: Add detailed context logging before error
                    with self.lock:
                        hooks_ready_state = self.hooks_ready.get(pid, False)
                        sequence_number = self.handoff_sequence_numbers.get(pid, 0)
                    
                    env_var = f'HOOKS_READY_PID_{pid}'
                    env_state = os.environ.get(env_var) == '1'
                    
                    if self.logger:
                        # ✅ ENHANCED LOGGING: Detailed state analysis for hook coordination errors
                        with self.lock:
                            recent_history = self.hook_status_history.get(pid, [])
                            last_events = [event.get('event_type', 'unknown') for event in recent_history[-3:]] if recent_history else []
                        
                        process_status = "exists" if psutil.pid_exists(pid) else "missing"
                        recovery_count = self.recovery_attempts.get(pid, 0)
                        
                        self.logger.error(f"🚨 [HEALTH] Hook coordination lost for PID {pid} - "
                                        f"State Analysis: internal={hooks_ready_state}, env={env_state}, "
                                        f"seq={sequence_number}, handoff_age={time_since_handoff:.2f}s, "
                                        f"process={process_status}, recovery_attempts={recovery_count}, "
                                        f"recent_events={last_events}, protection_window={handoff_protection_period}s")
                    
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
        """
        **Sync Hooks Ready State** (đồng bộ trạng thái hooks)
        
        ✅ PRIORITY 2: STATE SYNCHRONIZATION với comprehensive retry mechanism và exponential backoff
        Enhanced thread-safe synchronization với systematic retry, state verification, và graceful error handling.
        """
        # ✅ RETRY CONFIGURATION: Enhanced retry parameters for better reliability
        max_retries = 3
        base_delay = 0.1  # 100ms base delay
        backoff_factor = 2  # Exponential backoff multiplier
        max_delay = 1.0  # Maximum delay cap (1 second)
        
        for attempt in range(max_retries):
            try:
                # ✅ EXPONENTIAL BACKOFF: Calculate delay for current attempt
                if attempt > 0:
                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                    # Add jitter to prevent thundering herd
                    jitter = random.uniform(0, delay * 0.1)
                    total_delay = delay + jitter
                    
                    if self.logger:
                        self.logger.debug(f"🔄 [STATE-SYNC] PID {pid} retry {attempt + 1}/{max_retries} after {total_delay:.3f}s")
                    
                    time.sleep(total_delay)
                
                # ✅ ATOMIC OPERATION: Double-lock pattern for maximum consistency
                with self.environment_sync_lock:
                    with self.lock:
                        # Store previous state for rollback capability
                        previous_internal_state = self.hooks_ready.get(pid, False)
                        env_var = f'HOOKS_READY_PID_{pid}'
                        previous_env_state = os.environ.get(env_var) == '1'
                        
                        # Record synchronization attempt with retry context
                        sync_timestamp = time.time()
                        sync_context = {
                            'attempt': attempt + 1,
                            'max_retries': max_retries,
                            'pid': pid,
                            'target_state': ready_state,
                            'previous_internal': previous_internal_state,
                            'previous_env': previous_env_state
                        }
                        
                        if self.logger:
                            self.logger.debug(f"🔄 [STATE-SYNC] PID {pid} synchronization attempt {attempt + 1}/{max_retries} - "
                                            f"target: {ready_state}, current_internal: {previous_internal_state}, current_env: {previous_env_state}")
                        
                        try:
                            # ✅ Step 1: Update internal state
                            success = self._update_internal_state(pid, ready_state)
                            if not success:
                                raise Exception("Failed to update internal state")
                            
                            # ✅ Step 2: Sync environment variable with verification
                            success = self._sync_environment_variable(pid, ready_state)
                            if not success:
                                raise Exception("Failed to sync environment variable")
                            
                            # ✅ Step 3: Verify state consistency between internal and external state
                            if self._verify_state_consistency(pid):
                                # ✅ SUCCESS: Record successful synchronization
                                self._record_sync_success(pid, ready_state, sync_timestamp, sync_context)
                                
                                if self.logger:
                                    self.logger.info(f"✅ [STATE-SYNC] PID {pid} state synchronized successfully: {ready_state} "
                                                   f"(attempt: {attempt + 1}, duration: {(time.time() - sync_timestamp)*1000:.1f}ms)")
                                return True
                            else:
                                raise Exception("State consistency verification failed")
                                
                        except Exception as sync_error:
                            # ✅ ROLLBACK: Restore previous state on failure
                            rollback_success = self._rollback_state(pid, previous_internal_state, previous_env_state, env_var)
                            
                            if self.logger:
                                self.logger.warning(f"⚠️ [STATE-SYNC] PID {pid} sync failed (attempt {attempt + 1}): {sync_error} "
                                                 f"(rollback: {'success' if rollback_success else 'failed'})")
                            
                            # Record failure attempt
                            self._record_sync_failure(pid, ready_state, sync_timestamp, sync_context, str(sync_error))
                            
                            # If this is the last attempt, fail permanently
                            if attempt == max_retries - 1:
                                if self.logger:
                                    self.logger.error(f"❌ [STATE-SYNC] PID {pid} state sync failed after {max_retries} attempts: {sync_error}")
                                return False
                            
                            # Continue to next retry attempt
                            continue
                            
            except Exception as e:
                # ✅ COMPREHENSIVE ERROR HANDLING: Handle unexpected errors
                if self.logger:
                    self.logger.error(f"❌ [STATE-SYNC] Critical error in state sync for PID {pid} (attempt {attempt + 1}): {e}")
                
                if attempt == max_retries - 1:
                    if self.logger:
                        self.logger.error(f"❌ [STATE-SYNC] State sync failed after {max_retries} attempts: {e}")
                    return False
                
                # Continue to next retry attempt even on critical errors
                continue
        
        # All retry attempts exhausted
        if self.logger:
            self.logger.error(f"❌ [STATE-SYNC] All {max_retries} state sync attempts failed for PID {pid}")
        return False
    
    def _update_internal_state(self, pid: int, ready_state: bool) -> bool:
        """
        **Update Internal State** (cập nhật trạng thái internal)
        
        Safely update internal hooks_ready state with validation.
        """
        try:
            self.hooks_ready[pid] = ready_state
            
            # Verify update was successful
            actual_state = self.hooks_ready.get(pid, False)
            if actual_state == ready_state:
                if self.logger:
                    self.logger.debug(f"🔄 [INTERNAL-UPDATE] PID {pid} internal state updated: {ready_state}")
                return True
            else:
                if self.logger:
                    self.logger.error(f"❌ [INTERNAL-UPDATE] PID {pid} state update failed - expected: {ready_state}, actual: {actual_state}")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [INTERNAL-UPDATE] Error updating internal state for PID {pid}: {e}")
            return False
    
    def _sync_environment_variable(self, pid: int, ready_state: bool) -> bool:
        """
        **Sync Environment Variable** (đồng bộ biến môi trường)
        
        Update environment variable with fallback mechanism và verification.
        """
        try:
            env_var = f'HOOKS_READY_PID_{pid}'
            
            # Update environment variable based on state
            if ready_state:
                os.environ[env_var] = '1'
            else:
                os.environ.pop(env_var, None)
            
            # ✅ VERIFICATION: Verify environment variable was set correctly
            actual_env_state = os.environ.get(env_var) == '1'
            if actual_env_state == ready_state:
                if self.logger:
                    self.logger.debug(f"🔄 [ENV-SYNC] PID {pid} environment variable synced: {ready_state}")
                return True
            else:
                if self.logger:
                    self.logger.error(f"❌ [ENV-SYNC] PID {pid} environment sync failed - expected: {ready_state}, actual: {actual_env_state}")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [ENV-SYNC] Error syncing environment variable for PID {pid}: {e}")
            return False
    
    def _verify_state_consistency(self, pid: int) -> bool:
        """
        **Verify State Consistency** (xác minh tính nhất quán trạng thái)
        
        Compare internal hooks_ready[pid] vs environment variable để ensure consistency.
        """
        try:
            # Get internal state
            internal_state = self.hooks_ready.get(pid, False)
            
            # Get environment variable state
            env_var = f'HOOKS_READY_PID_{pid}'
            env_state = os.environ.get(env_var) == '1'
            
            # Check consistency
            is_consistent = (internal_state == env_state)
            
            if self.logger:
                if is_consistent:
                    self.logger.debug(f"✅ [CONSISTENCY] PID {pid} state consistent - internal: {internal_state}, env: {env_state}")
                else:
                    self.logger.warning(f"⚠️ [CONSISTENCY] PID {pid} state inconsistent - internal: {internal_state}, env: {env_state}")
            
            return is_consistent
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [CONSISTENCY] Error verifying state consistency for PID {pid}: {e}")
            return False
    
    def _rollback_state(self, pid: int, previous_internal_state: bool, previous_env_state: bool, env_var: str) -> bool:
        """
        **Rollback State** (khôi phục trạng thái)
        
        Restore previous state on synchronization failure.
        """
        try:
            rollback_success = True
            
            # Restore internal state
            try:
                self.hooks_ready[pid] = previous_internal_state
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ [ROLLBACK] Failed to restore internal state for PID {pid}: {e}")
                rollback_success = False
            
            # Restore environment variable
            try:
                if previous_env_state:
                    os.environ[env_var] = '1'
                else:
                    os.environ.pop(env_var, None)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ [ROLLBACK] Failed to restore environment variable for PID {pid}: {e}")
                rollback_success = False
            
            if self.logger:
                if rollback_success:
                    self.logger.debug(f"🔄 [ROLLBACK] PID {pid} state rollback successful")
                else:
                    self.logger.warning(f"⚠️ [ROLLBACK] PID {pid} partial rollback failure")
            
            return rollback_success
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [ROLLBACK] Critical error during rollback for PID {pid}: {e}")
            return False
    
    def _record_sync_success(self, pid: int, ready_state: bool, timestamp: float, context: Dict[str, Any]) -> None:
        """
        **Record Sync Success** (ghi lại thành công sync)
        
        Record successful state synchronization event với comprehensive context.
        """
        try:
            sync_duration = time.time() - timestamp
            success_record = {
                'timestamp': timestamp,
                'event_type': 'state_sync_success',
                'success': True,
                'ready_state': ready_state,
                'attempt_number': context.get('attempt', 1),
                'max_retries': context.get('max_retries', 3),
                'sync_duration_ms': round(sync_duration * 1000, 2),
                'previous_states': {
                    'internal': context.get('previous_internal', False),
                    'env': context.get('previous_env', False)
                },
                'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            }
            
            with self.lock:
                if pid in self.hook_status_history:
                    self.hook_status_history[pid].append(success_record)
                    
                    # Keep history manageable
                    if len(self.hook_status_history[pid]) > 25:
                        self.hook_status_history[pid] = self.hook_status_history[pid][-25:]
            
            if self.logger:
                self.logger.debug(f"📝 [SYNC-SUCCESS] Recorded successful sync for PID {pid} (attempt: {context.get('attempt', 1)})")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [SYNC-SUCCESS] Error recording sync success for PID {pid}: {e}")
    
    def _record_sync_failure(self, pid: int, ready_state: bool, timestamp: float, context: Dict[str, Any], error_msg: str) -> None:
        """
        **Record Sync Failure** (ghi lại thất bại sync)
        
        Record failed synchronization attempt với detailed error context.
        """
        try:
            sync_duration = time.time() - timestamp
            failure_record = {
                'timestamp': timestamp,
                'event_type': 'state_sync_failure',
                'success': False,
                'ready_state': ready_state,
                'attempt_number': context.get('attempt', 1),
                'max_retries': context.get('max_retries', 3),
                'sync_duration_ms': round(sync_duration * 1000, 2),
                'error_message': error_msg,
                'previous_states': {
                    'internal': context.get('previous_internal', False),
                    'env': context.get('previous_env', False)
                },
                'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            }
            
            with self.lock:
                if pid in self.hook_status_history:
                    self.hook_status_history[pid].append(failure_record)
                    
                    # Keep history manageable
                    if len(self.hook_status_history[pid]) > 25:
                        self.hook_status_history[pid] = self.hook_status_history[pid][-25:]
            
            if self.logger:
                self.logger.debug(f"📝 [SYNC-FAILURE] Recorded sync failure for PID {pid} (attempt: {context.get('attempt', 1)})")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [SYNC-FAILURE] Error recording sync failure for PID {pid}: {e}")
    
    def _validate_atomic_sync(self, pid: int, expected_state: bool, sync_timestamp: float) -> Dict[str, Any]:
        """
        **Validate Atomic Sync** (xác thực atomic sync)
        
        ✅ LEGACY SUPPORT: Maintained for compatibility with existing verification calls.
        Now serves as a wrapper around the enhanced _verify_state_consistency method.
        
        Returns:
            Dict với success status và validation details
        """
        try:
            # Multi-layer validation using enhanced consistency check
            sync_duration = time.time() - sync_timestamp
            
            # Use enhanced consistency verification
            is_consistent = self._verify_state_consistency(pid)
            
            # Additional validations for backward compatibility
            internal_state = self.hooks_ready.get(pid, False)
            env_var = f'HOOKS_READY_PID_{pid}'
            env_state = os.environ.get(env_var) == '1'
            
            validations = {
                'internal_state': (internal_state == expected_state),
                'env_state': (env_state == expected_state),
                'cross_state_sync': is_consistent,
                'timing': (sync_duration < 0.1),  # Increased to 100ms for retry scenarios
                'pid_tracking': (pid in self.active_processes)
            }
            
            # Overall success
            all_valid = all(validations.values())
            
            return {
                'success': all_valid,
                'details': validations,
                'sync_duration': sync_duration,
                'expected_state': expected_state,
                'actual_internal': internal_state,
                'actual_env': env_state
            }
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [VALIDATE-ATOMIC] Error in atomic sync validation for PID {pid}: {e}")
            return {
                'success': False,
                'error': str(e),
                'details': {'validation_error': True}
            }
    
    def _record_atomic_sync_success(self, pid: int, ready_state: bool, timestamp: float, attempt_number: int) -> None:
        """
        **Record Atomic Sync Success** (ghi lại thành công atomic sync)
        
        ✅ LEGACY SUPPORT: Wrapper around enhanced sync success recording.
        """
        try:
            # Use enhanced sync success recording with legacy compatibility
            context = {
                'attempt': attempt_number,
                'max_retries': 3,  # Default for legacy calls
                'previous_internal': False,  # Unknown for legacy calls
                'previous_env': False  # Unknown for legacy calls
            }
            
            self._record_sync_success(pid, ready_state, timestamp, context)
                    
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [ATOMIC-SYNC] Error recording legacy success for PID {pid}: {e}")
    
    def _record_atomic_sync_failure(self, pid: int, ready_state: bool, timestamp: float, attempt_number: int, validation_results: Dict[str, Any]) -> None:
        """
        **Record Atomic Sync Failure** (ghi lại thất bại atomic sync)
        
        ✅ LEGACY SUPPORT: Wrapper around enhanced sync failure recording.
        """
        try:
            # Use enhanced sync failure recording with legacy compatibility
            context = {
                'attempt': attempt_number,
                'max_retries': 3,  # Default for legacy calls
                'previous_internal': False,  # Unknown for legacy calls
                'previous_env': False  # Unknown for legacy calls
            }
            
            error_msg = f"Validation failed: {validation_results.get('details', 'Unknown error')}"
            self._record_sync_failure(pid, ready_state, timestamp, context, error_msg)
                    
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [ATOMIC-SYNC] Error recording legacy failure for PID {pid}: {e}")
    
    def _verify_with_retry(self, pid: int, attempt: int) -> Dict[str, any]:
        """
        **Verify With Retry** (xác minh với retry)
        
        ✅ SOLUTION 3: HEALTH CHECK REFINEMENT với handoff-aware validation
        Single verification attempt với detailed result và handoff coordination awareness.
        """
        try:
            verification_start_time = time.time()
            
            # ✅ HANDOFF AWARENESS: Check for recent handoffs that might affect verification
            with self.lock:
                hooks_ready = self.hooks_ready.get(pid, False)
                
                # Get handoff timing information for context
                last_handoff_time = self.handoff_timestamps.get(pid, 0)
                time_since_handoff = verification_start_time - last_handoff_time
                current_sequence = self.handoff_sequence_numbers.get(pid, 0)
            
            # Check environment variable consistency
            env_var = f'HOOKS_READY_PID_{pid}'
            env_status = os.environ.get(env_var) == '1'
            
            # ✅ HANDOFF-AWARE TIMING: Allow grace period for recent handoffs
            handoff_grace_period = 3.0  # 3-second grace period after handoff (increased from 2.0s for enhanced stability)
            is_recent_handoff = time_since_handoff < handoff_grace_period
            
            # Enhanced verification với handoff context
            verification_context = {
                'verification_timestamp': verification_start_time,
                'last_handoff_time': last_handoff_time,
                'time_since_handoff': time_since_handoff,
                'is_recent_handoff': is_recent_handoff,
                'handoff_sequence': current_sequence,
                'attempt_number': attempt + 1
            }
            
            if self.logger:
                self.logger.debug(f"🔍 [VERIFY-ENHANCED] PID {pid} verification context: "
                                f"recent_handoff={is_recent_handoff}, time_since={time_since_handoff:.2f}s, "
                                f"seq={current_sequence}, attempt={attempt + 1}")
            
            # Verify consistency between internal state and environment variable
            if hooks_ready != env_status:
                inconsistency_severity = self._assess_inconsistency_severity(
                    pid, hooks_ready, env_status, verification_context
                )
                
                if self.logger:
                    severity_msg = f"severity={inconsistency_severity['level']}"
                    if is_recent_handoff:
                        severity_msg += f" (recent_handoff_tolerance)"
                    
                    self.logger.warning(f"⚠️ [VERIFY-ENHANCED] PID {pid} inconsistency (attempt {attempt + 1}): "
                                      f"internal={hooks_ready}, env={env_status}, {severity_msg}")
                
                # ✅ HANDOFF-AWARE RECOVERY: Different strategies based on handoff timing
                if is_recent_handoff and inconsistency_severity['level'] == 'low':
                    # For recent handoffs with low severity, allow more recovery attempts
                    if attempt < self.verification_retry_config['max_retries'] - 1:
                        # Try enhanced synchronization for recent handoffs
                        sync_success = self._enhanced_sync_for_handoff(pid, verification_context)
                        
                        return {
                            'success': False,
                            'should_retry': True,
                            'hooks_ready': False,
                            'sync_attempted': sync_success,
                            'inconsistency_detected': True,
                            'inconsistency_severity': inconsistency_severity,
                            'verification_context': verification_context,
                            'recovery_strategy': 'handoff_aware_sync'
                        }
                else:
                    # Standard recovery for non-recent handoffs or high severity
                    if attempt < self.verification_retry_config['max_retries'] - 1:
                        sync_success = self.sync_environment_state(pid)
                        return {
                            'success': False,
                            'should_retry': True,
                            'hooks_ready': False,
                            'sync_attempted': sync_success,
                            'inconsistency_detected': True,
                            'inconsistency_severity': inconsistency_severity,
                            'verification_context': verification_context,
                            'recovery_strategy': 'standard_sync'
                        }
                
                # Final attempt or unrecoverable inconsistency
                return {
                    'success': False,
                    'should_retry': False,
                    'hooks_ready': False,
                    'inconsistency_detected': True,
                    'inconsistency_severity': inconsistency_severity,
                    'verification_context': verification_context,
                    'recovery_strategy': 'none_final_attempt'
                }
            
            # ✅ CONSISTENT STATES: Perform additional validation for recent handoffs
            if is_recent_handoff:
                # Additional validation for recent handoffs to ensure stability
                additional_validation = self._validate_handoff_stability(pid, verification_context)
                
                if not additional_validation['stable']:
                    if self.logger:
                        self.logger.debug(f"🔍 [VERIFY-ENHANCED] PID {pid} handoff stability check failed: "
                                        f"{additional_validation['details']}")
                    
                    if attempt < self.verification_retry_config['max_retries'] - 1:
                        return {
                            'success': False,
                            'should_retry': True,
                            'hooks_ready': hooks_ready and env_status,
                            'inconsistency_detected': False,
                            'stability_check': additional_validation,
                            'verification_context': verification_context,
                            'recovery_strategy': 'stability_recheck'
                        }
            
            # ✅ SUCCESS: States are consistent and stable
            verification_duration = time.time() - verification_start_time
            
            return {
                'success': True,
                'should_retry': False,
                'hooks_ready': hooks_ready and env_status,
                'inconsistency_detected': False,
                'verification_context': verification_context,
                'verification_duration': verification_duration,
                'stability_validated': is_recent_handoff
            }
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [VERIFY-ENHANCED] Error in verification attempt {attempt + 1} for PID {pid}: {e}")
            
            return {
                'success': False,
                'should_retry': True,  # Retry on exception unless it's the last attempt
                'hooks_ready': False,
                'error': str(e),
                'verification_context': {
                    'verification_timestamp': time.time(),
                    'error_occurred': True,
                    'attempt_number': attempt + 1
                }
            }
    
    def _assess_inconsistency_severity(self, pid: int, internal_state: bool, env_state: bool, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        **Assess Inconsistency Severity** (đánh giá mức độ nghiêm trọng inconsistency)
        
        Evaluates severity của state inconsistency dựa trên handoff timing và patterns.
        """
        try:
            severity_factors = {
                'time_since_handoff': context.get('time_since_handoff', 999),
                'is_recent_handoff': context.get('is_recent_handoff', False),
                'state_difference': abs(int(internal_state) - int(env_state)),
                'attempt_number': context.get('attempt_number', 1)
            }
            
            # Calculate severity level
            if severity_factors['is_recent_handoff'] and severity_factors['time_since_handoff'] < 0.5:
                level = 'low'  # Very recent handoff, inconsistency might be temporary
            elif severity_factors['time_since_handoff'] < 2.0:
                level = 'medium'  # Recent handoff, worth retrying
            else:
                level = 'high'  # Old handoff, inconsistency is problematic
            
            return {
                'level': level,
                'factors': severity_factors,
                'recommendation': 'retry' if level in ['low', 'medium'] else 'escalate'
            }
            
        except Exception as e:
            return {
                'level': 'unknown',
                'error': str(e),
                'recommendation': 'escalate'
            }
    
    def _enhanced_sync_for_handoff(self, pid: int, context: Dict[str, Any]) -> bool:
        """
        **Enhanced Sync for Handoff** (đồng bộ nâng cao cho handoff)
        
        Special synchronization method cho recent handoffs với additional validation.
        """
        try:
            if self.logger:
                self.logger.debug(f"🔄 [ENHANCED-SYNC] Performing handoff-aware sync for PID {pid}")
            
            # Use the enhanced atomic sync method
            sync_success = self._sync_hooks_ready_state(pid, self.hooks_ready.get(pid, False))
            
            if sync_success:
                # Additional verification after sync
                time.sleep(0.001)  # Brief stabilization delay
                
                # Re-verify consistency
                with self.lock:
                    internal_state = self.hooks_ready.get(pid, False)
                
                env_var = f'HOOKS_READY_PID_{pid}'
                env_state = os.environ.get(env_var) == '1'
                
                final_consistency = (internal_state == env_state)
                
                if self.logger:
                    self.logger.debug(f"🔄 [ENHANCED-SYNC] PID {pid} post-sync verification: "
                                    f"consistent={final_consistency}, state={internal_state}")
                
                return final_consistency
            else:
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [ENHANCED-SYNC] Error in enhanced sync for PID {pid}: {e}")
            return False
    
    def _validate_handoff_stability(self, pid: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        **Validate Handoff Stability** (xác thực tính ổn định handoff)
        
        Additional validation cho recent handoffs để ensure state stability.
        """
        try:
            # Check for rapid state changes that might indicate instability
            with self.lock:
                recent_history = self.hook_status_history.get(pid, [])
                
            # Look for recent state changes
            current_time = time.time()
            recent_changes = [
                event for event in recent_history[-5:]  # Last 5 events
                if current_time - event.get('timestamp', 0) < 2.0  # Within 2 seconds
            ]
            
            # Stability indicators
            stability_checks = {
                'rapid_changes': len(recent_changes) > 3,  # More than 3 changes in 2 seconds
                'state_oscillation': self._detect_state_oscillation(recent_changes),
                'handoff_completion': context.get('time_since_handoff', 0) > 0.1  # ✅ ENHANCED: Increased to 100ms for stability with longer grace periods
            }
            
            # Overall stability
            is_stable = not any([
                stability_checks['rapid_changes'],
                stability_checks['state_oscillation']
            ]) and stability_checks['handoff_completion']
            
            return {
                'stable': is_stable,
                'details': stability_checks,
                'recent_changes_count': len(recent_changes)
            }
            
        except Exception as e:
            return {
                'stable': False,
                'error': str(e),
                'details': {'validation_error': True}
            }
    
    def _detect_state_oscillation(self, recent_events: list) -> bool:
        """**Detect State Oscillation** (phát hiện dao động trạng thái)"""
        try:
            if len(recent_events) < 3:
                return False
            
            # Look for alternating success/failure patterns
            success_pattern = [event.get('success', True) for event in recent_events[-3:]]
            
            # Detect oscillation: True->False->True or False->True->False
            if len(success_pattern) >= 3:
                return (success_pattern[0] != success_pattern[1] and 
                       success_pattern[1] != success_pattern[2])
            
            return False
            
        except Exception:
            return False
    
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
        """**Enhanced Health Report** (báo cáo sức khỏe nâng cao - trả về comprehensive health status với linear flow metrics)"""
        try:
            with self.lock:
                current_time = time.time()
                
                # Basic statistics
                total_processes = len(self.active_processes)
                ready_processes = sum(1 for pid in self.active_processes if self.hooks_ready.get(pid, False))
                
                # Recovery statistics
                total_recovery_attempts = sum(self.recovery_attempts.values())
                processes_with_recoveries = len([pid for pid, attempts in self.recovery_attempts.items() if attempts > 0])
                
                # **Linear Flow Statistics** (thống kê luồng tuyến tính)
                handoff_stats = {
                    'total_handoffs': len(self.handoff_timestamps),
                    'recent_handoffs': len([t for t in self.handoff_timestamps.values() if current_time - t < 300]),  # Last 5 minutes
                    'average_handoff_interval': 0.0
                }
                
                # Calculate average handoff interval
                if len(self.handoff_timestamps) > 1:
                    handoff_times = sorted(self.handoff_timestamps.values())
                    intervals = [handoff_times[i] - handoff_times[i-1] for i in range(1, len(handoff_times))]
                    handoff_stats['average_handoff_interval'] = sum(intervals) / len(intervals)
                
                # **Environment Variable Health** (sức khỏe biến môi trường)
                env_health = {
                    'linear_handoff_vars': len([k for k in os.environ.keys() if k.startswith('LINEAR_HANDOFF_RM_PID_')]),
                    'pickup_ready_vars': len([k for k in os.environ.keys() if k.startswith('RM_PICKUP_READY_PID_')]),
                    'deferred_handoff_vars': len([k for k in os.environ.keys() if k.startswith('DEFERRED_RM_HANDOFF_PID_')]),
                    'hooks_ready_vars': len([k for k in os.environ.keys() if k.startswith('HOOKS_READY_PID_')])
                }
                
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
                    'linear_flow_stats': handoff_stats,
                    'environment_health': env_health,
                    'active_processes': list(self.active_processes),
                    'process_status': {pid: self.hooks_ready.get(pid, False) for pid in self.active_processes},
                    'last_health_check': self.last_health_check,
                    'health_check_interval': self.health_check_interval
                }
                
                return report
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [HEALTH] Error generating enhanced health report: {e}")
            
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
    """**Enhanced Hook Coordinator Singleton** (lấy coordinator singleton nâng cao)
    
    Thread-safe singleton access với enhanced initialization logging.
    
    Returns:
        HookCoordinator: Enhanced singleton instance with linear flow support
    """
    global _coordinator
    
    with _lock:
        if _coordinator is None:
            _coordinator = HookCoordinator()
            # **Enhanced initialization logging** (ghi log khởi tạo nâng cao)
            if hasattr(_coordinator, 'logger') and _coordinator.logger:
                _coordinator.logger.info("✅ [SINGLETON] Enhanced HookCoordinator singleton created with linear flow support")
                _coordinator.logger.info(f"🔗 [SINGLETON] Enhanced features: direct handoff, deferred coordination, comprehensive cleanup")
        return _coordinator

def reset_hook_coordinator() -> None:
    """**Reset Hook Coordinator** (reset hook coordinator)
    
    Testing and development utility to reset singleton state.
    """
    global _coordinator
    with _lock:
        if _coordinator:
            # Cleanup resources before reset
            if hasattr(_coordinator, '_stop_health_monitoring'):
                _coordinator._stop_health_monitoring()
        _coordinator = None