"""worker.py (đặt trong app/pid_logger)
Enhanced PID Logger với Real Process Output Monitor.
Ghi PID và runtime output cho CPU/GPU mining processes.
"""
from __future__ import annotations

import json
import os
import pathlib
import queue
import threading
import time
import logging
import select
import subprocess
import fcntl
from datetime import datetime
from typing import Dict, Optional, Any

# Cấu hình - Tự động phát hiện đường dẫn dựa trên script location
_SCRIPT_DIR = pathlib.Path(__file__).parent.parent
LOG_DIR = os.getenv("LOGS_DIR", str(_SCRIPT_DIR / "mining_environment" / "logs"))
PID_CPU_FILE = pathlib.Path(LOG_DIR) / "pid_cpu.log"
PID_GPU_FILE = pathlib.Path(LOG_DIR) / "pid_gpu.log"
MAX_SIZE_MB = 3

# Output format configuration
# "raw" = raw text format với timestamp prefix
# "json" = JSON structured format  
OUTPUT_FORMAT = os.getenv("PID_LOG_FORMAT", "raw")

# Queues và Events
_QUEUE: "queue.Queue[dict]" = queue.Queue()
_OUTPUT_QUEUE: "queue.Queue[dict]" = queue.Queue()
_STOP_EVENT = threading.Event()
_WORKER_STARTED = threading.Event()
_OUTPUT_MONITOR_STARTED = threading.Event()

# Process Registry để theo dõi processes đã đăng ký
_PROCESS_REGISTRY: Dict[int, Dict[str, Any]] = {}

# Thiết lập logger cho PID Logger
logger = logging.getLogger("pid_logger")
# Nếu chưa có handler, tạo cấu hình cơ bản
if not logger.handlers:
    logging.basicConfig(
        level=os.getenv("PID_LOGGER_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] pid_logger - %(message)s",
    )

def _ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)

def _rotate_if_needed(path: pathlib.Path) -> None:
    if path.exists() and path.stat().st_size / (1024*1024) > MAX_SIZE_MB:
        try:
            logger.info(f"Rotating PID log file {path} (> {MAX_SIZE_MB}MB)")
            path.unlink()
        except Exception as exc:
            logger.error(f"Failed to rotate PID log file {path}: {exc}")

def enqueue_pid(pid: int, mtype: str):
    """Ghi PID vào queue cho PID logging"""
    if mtype not in ("cpu", "gpu"):
        raise ValueError("mtype must be 'cpu' or 'gpu'")
    payload = {"pid": pid, "type": mtype, "ts": time.time()}
    _QUEUE.put(payload)
    logger.debug(f"Enqueued PID {payload['pid']} ({payload['type']}). Queue size: {_QUEUE.qsize()}")

def register_process(pid: int, process_type: str, process_obj, process_name: str = None):
    """
    Đăng ký process để monitor output runtime.
    
    Args:
        pid: Process ID
        process_type: 'cpu' hoặc 'gpu'
        process_obj: subprocess.Popen object hoặc psutil.Process object
        process_name: Tên process (optional)
    """
    if process_type not in ("cpu", "gpu"):
        raise ValueError("process_type must be 'cpu' or 'gpu'")
    
    # Handle both subprocess.Popen and psutil.Process objects
    if hasattr(process_obj, 'poll'):
        # subprocess.Popen object
        obj_type = "subprocess"
    elif hasattr(process_obj, 'is_running'):
        # psutil.Process object  
        obj_type = "psutil"
    else:
        obj_type = "unknown"
        logger.warning(f"Unknown process object type for PID {pid}: {type(process_obj)}")
    
    _PROCESS_REGISTRY[pid] = {
        "type": process_type,
        "process_obj": process_obj,
        "process_name": process_name or f"{process_type}_miner",
        "start_time": time.time(),
        "registered_at": time.time(),
        "obj_type": obj_type
    }
    logger.info(f"Registered process PID {pid} ({process_type}, {obj_type}) for output monitoring")
    
    # Tự động enqueue PID để log
    enqueue_pid(pid, process_type)

def _read_process_output_via_proc(pid: int) -> Optional[str]:
    """
    Enhanced Real Process Output Monitor - đọc output qua subprocess pipes + /proc fallback
    
    Args:
        pid: Process ID để monitor
        
    Returns:
        str: Output line nếu có, None nếu không có hoặc lỗi
    """
    try:
        # Priority 1: Sử dụng subprocess PIPE từ process_obj (efficient)
        if pid in _PROCESS_REGISTRY:
            process_obj = _PROCESS_REGISTRY[pid]["process_obj"]
            if process_obj and process_obj.stdout:
                try:
                    # Non-blocking read từ subprocess pipe
                    fd = process_obj.stdout.fileno()
                    fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
                    line = process_obj.stdout.readline()
                    if line and line.strip():
                        return line.strip()
                except (BlockingIOError, OSError):
                    pass  # No data available, try /proc fallback
        
        # Priority 2: Fallback to /proc/<pid>/fd/ (less efficient but reliable)
        stdout_path = f"/proc/{pid}/fd/1"
        stderr_path = f"/proc/{pid}/fd/2"
        
        # Check process still exists
        if not os.path.exists(f"/proc/{pid}"):
            logger.debug(f"Process {pid} no longer exists")
            return None
        
        if os.path.exists(stdout_path):
            with open(stdout_path, 'r', errors='ignore') as f:
                # Non-blocking read
                line = f.readline()
                if line.strip():
                    return line.strip()
        
        # Fallback: đọc stderr nếu stdout trống
        if os.path.exists(stderr_path):
            with open(stderr_path, 'r', errors='ignore') as f:
                line = f.readline()
                if line.strip():
                    return line.strip()
                    
    except (OSError, IOError, PermissionError) as e:
        logger.debug(f"Cannot read process {pid} output: {e}")
        # Process might have died, remove from registry
        if pid in _PROCESS_REGISTRY:
            del _PROCESS_REGISTRY[pid]
    except Exception as e:
        logger.warning(f"Unexpected error reading process {pid} output: {e}")
    
    return None

def _output_monitor_loop():
    """
    Real Process Output Monitor Loop - giám sát và ghi log runtime output
    """
    logger.info("Process Output Monitor started")
    
    while not _STOP_EVENT.is_set():
        try:
            # Check các process đã registered
            active_pids = list(_PROCESS_REGISTRY.keys())
            
            for pid in active_pids:
                if pid not in _PROCESS_REGISTRY:
                    continue
                    
                process_info = _PROCESS_REGISTRY[pid]
                process_obj = process_info["process_obj"]
                obj_type = process_info.get("obj_type", "subprocess")
                
                # Kiểm tra process còn sống không (support both subprocess và psutil)
                is_alive = False
                try:
                    if obj_type == "subprocess":
                        is_alive = process_obj.poll() is None
                    elif obj_type == "psutil":
                        is_alive = process_obj.is_running()
                    else:
                        # Fallback: check /proc/{pid} exists
                        is_alive = os.path.exists(f"/proc/{pid}")
                except Exception as e:
                    logger.debug(f"Error checking process {pid} status: {e}")
                    is_alive = False
                
                if not is_alive:
                    logger.info(f"Process {pid} ({process_info['type']}) has terminated, removing from registry")
                    del _PROCESS_REGISTRY[pid]
                    continue
                
                # Đọc output via /proc/<pid>/fd/
                output_line = _read_process_output_via_proc(pid)
                
                if output_line:
                    runtime_seconds = time.time() - process_info["start_time"]
                    
                    # Tạo output entry để log
                    output_entry = {
                        "timestamp": time.time(),
                        "pid": pid,
                        "type": process_info["type"],
                        "process_name": process_info["process_name"],
                        "runtime_seconds": round(runtime_seconds, 1),
                        "output": output_line,
                        "level": "INFO"
                    }
                    
                    # Enqueue để _output_writer_loop xử lý
                    _OUTPUT_QUEUE.put(output_entry)
                    logger.debug(f"Captured output from PID {pid}: {output_line[:50]}...")
            
            # Sleep ngắn để không tốn quá nhiều CPU
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error in output monitor loop: {e}")
            time.sleep(2)
    
    logger.info("Process Output Monitor stopped")

def _output_writer_loop():
    """
    Output Writer Loop - ghi runtime output vào file riêng biệt
    """
    logger.info("Output Writer Loop started")
    _ensure_log_dir()
    
    # Mở file để ghi runtime output (tách biệt với PID log)
    cpu_output_file = (pathlib.Path(LOG_DIR) / "pid_cpu.log").open("a", buffering=1, encoding="utf-8")
    gpu_output_file = (pathlib.Path(LOG_DIR) / "pid_gpu.log").open("a", buffering=1, encoding="utf-8")
    
    files = {
        "cpu": cpu_output_file,
        "gpu": gpu_output_file
    }
    
    while not _STOP_EVENT.is_set():
        try:
            output_entry = _OUTPUT_QUEUE.get(timeout=1)
        except queue.Empty:
            continue
            
        try:
            process_type = output_entry["type"]
            f = files[process_type]
            
            # Kiểm tra rotation
            file_path = pathlib.Path(f.name)
            _rotate_if_needed(file_path)
            
            # Format output theo cấu hình: raw hoặc json
            if OUTPUT_FORMAT.lower() == "json":
                # JSON structured format (legacy)
                runtime_log_entry = {
                    "timestamp": output_entry["timestamp"],
                    "pid": output_entry["pid"], 
                    "runtime_seconds": output_entry["runtime_seconds"],
                    "output": output_entry["output"],
                    "level": output_entry["level"]
                }
                log_line = json.dumps(runtime_log_entry, ensure_ascii=False) + "\n"
            else:
                # Raw text format (default) - mining output như thật
                timestamp_str = datetime.fromtimestamp(output_entry["timestamp"]).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                runtime_str = f"[Runtime: {output_entry['runtime_seconds']}s]"
                pid_str = f"[PID: {output_entry['pid']}]"
                
                # Ghi raw format: [timestamp] [runtime] [pid] actual_output
                log_line = f"[{timestamp_str}] {runtime_str} {pid_str} {output_entry['output']}\n"
            
            f.write(log_line)
            f.flush()
            logger.debug(f"Wrote {OUTPUT_FORMAT} runtime output for PID {output_entry['pid']} to {process_type} log")
            
        except Exception as write_err:
            logger.error(f"Failed to write output log: {write_err}")
    
    # Cleanup
    for f in files.values():
        try:
            f.close()
        except:
            pass
    
    logger.info("Output Writer Loop stopped")

def _writer_loop_wrapper():
    """Wrapper với exception handling cho writer thread"""
    try:
        _writer_loop()
    except Exception as exc:
        logger.error(f"PID logger worker thread crashed: {exc}")
        # Reset worker started flag để có thể restart
        _WORKER_STARTED.clear()

def _writer_loop():
    logger.info("PID logger worker thread started")
    _ensure_log_dir()
    logger.info(f"Log directory verified: {LOG_DIR}")
    files = {
        "cpu": PID_CPU_FILE.open("a", buffering=1, encoding="utf-8"),
        "gpu": PID_GPU_FILE.open("a", buffering=1, encoding="utf-8"),
    }
    logger.info(f"Log files opened - CPU: {PID_CPU_FILE}, GPU: {PID_GPU_FILE}")
    
    while not _STOP_EVENT.is_set():
        try:
            item = _QUEUE.get(timeout=1)
        except queue.Empty:
            continue
        logger.info(f"Processing PID log entry: {item}")
        f = files[item["type"]]
        _rotate_if_needed(f.name if isinstance(f,str) else pathlib.Path(f.name))
        try:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            f.flush()  # Đảm bảo ghi ngay lập tức
            logger.info(f"Successfully wrote PID {item['pid']} to {item['type']} log")
        except Exception as write_exc:
            logger.error(f"Failed to write PID log: {write_exc}")
            try:
                f.close()
            except Exception:
                pass
            files[item["type"]] = (PID_CPU_FILE if item["type"]=="cpu" else PID_GPU_FILE).open("a", buffering=1, encoding="utf-8")
    
    logger.info("PID logger worker thread shutting down")
    for f in files.values():
        try:
            f.close()
        except Exception:
            pass

def start_worker():
    """Khởi động cả PID Logger và Real Process Output Monitor"""
    if _WORKER_STARTED.is_set():
        return
    
    logger.info("Starting Enhanced PID Logger with Real Process Output Monitor")
    
    # Start PID Logger thread
    pid_thread = threading.Thread(target=_writer_loop_wrapper, daemon=True, name="PIDLoggerWorker")
    pid_thread.start()
    
    # Start Output Monitor threads
    monitor_thread = threading.Thread(target=_output_monitor_loop, daemon=True, name="ProcessOutputMonitor")
    monitor_thread.start()
    
    output_writer_thread = threading.Thread(target=_output_writer_loop, daemon=True, name="OutputWriter")  
    output_writer_thread.start()
    
    _WORKER_STARTED.set()
    _OUTPUT_MONITOR_STARTED.set()
    
    logger.info("Enhanced PID Logger started successfully:")
    logger.info("  - PID Logger Worker: ACTIVE")
    logger.info("  - Process Output Monitor: ACTIVE") 
    logger.info("  - Output Writer: ACTIVE")

def force_restart_worker():
    """Buộc khởi động lại worker (chỉ dùng khi debug)"""
    global _WORKER_STARTED
    _WORKER_STARTED.clear()
    logger.info("Force restarting PID Logger worker")
    start_worker()

def log_pid(pid: int, is_cpu: bool):
    logger.info(f"Logging PID {pid} (is_cpu={is_cpu})")
    # Đảm bảo worker đang chạy trước khi enqueue
    if not _WORKER_STARTED.is_set():
        logger.warning("Worker not started, attempting to start now")
        start_worker()
    enqueue_pid(pid, "cpu" if is_cpu else "gpu")

def debug_registry_status():
    """Debug function để kiểm tra trạng thái process registry"""
    logger.info(f"=== PROCESS REGISTRY DEBUG ===")
    logger.info(f"Total registered processes: {len(_PROCESS_REGISTRY)}")
    logger.info(f"Output format: {OUTPUT_FORMAT}")
    
    for pid, info in _PROCESS_REGISTRY.items():
        logger.info(f"PID {pid}: type={info['type']}, name={info['process_name']}, obj_type={info.get('obj_type', 'unknown')}")
        
        # Kiểm tra process có còn sống không
        try:
            if info.get('obj_type') == 'psutil':
                is_alive = info['process_obj'].is_running()
            else:
                is_alive = os.path.exists(f"/proc/{pid}")
            logger.info(f"  └─ Process alive: {is_alive}")
        except Exception as e:
            logger.info(f"  └─ Status check failed: {e}")
    
    logger.info(f"Queue sizes: PID={_QUEUE.qsize()}, OUTPUT={_OUTPUT_QUEUE.qsize()}")
    logger.info(f"Worker status: STARTED={_WORKER_STARTED.is_set()}, OUTPUT_MONITOR={_OUTPUT_MONITOR_STARTED.is_set()}")
    logger.info(f"===============================")

def force_test_output(test_pid: int = None, test_type: str = "cpu"):
    """Force test một output entry để verify format"""
    if test_pid is None:
        test_pid = 99999  # fake PID for testing
    
    test_entry = {
        "timestamp": time.time(),
        "pid": test_pid,
        "type": test_type,
        "process_name": f"{test_type}_test_miner",
        "runtime_seconds": 123.5,
        "output": "* ABOUT        AI Compute Engine/1.0.0 gcc/11.4.0 (built for Linux x86-64, 64 bit)",
        "level": "INFO"
    }
    
    _OUTPUT_QUEUE.put(test_entry)
    logger.info(f"Added test output entry for PID {test_pid} ({test_type}) to queue")
