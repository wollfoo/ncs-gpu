"""worker.py (đặt trong app/pid_logger)
Ghi PID tiến trình mining vào pid_cpu.log hoặc pid_gpu.log.
Code giống bản gốc nhưng đặt lại đường dẫn.
"""
from __future__ import annotations

import json
import os
import pathlib
import queue
import threading
import time
import logging

# Cấu hình - Tự động phát hiện đường dẫn dựa trên script location
_SCRIPT_DIR = pathlib.Path(__file__).parent.parent
LOG_DIR = os.getenv("LOGS_DIR", str(_SCRIPT_DIR / "mining_environment" / "logs"))
PID_CPU_FILE = pathlib.Path(LOG_DIR) / "pid_cpu.log"
PID_GPU_FILE = pathlib.Path(LOG_DIR) / "pid_gpu.log"
MAX_SIZE_MB = 3

_QUEUE: "queue.Queue[dict]" = queue.Queue()
_STOP_EVENT = threading.Event()
_WORKER_STARTED = threading.Event()

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
    if mtype not in ("cpu", "gpu"):
        raise ValueError("mtype must be 'cpu' or 'gpu'")
    payload = {"pid": pid, "type": mtype, "ts": time.time()}
    _QUEUE.put(payload)
    logger.debug(f"Enqueued PID {payload['pid']} ({payload['type']}). Queue size: {_QUEUE.qsize()}")

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
    if _WORKER_STARTED.is_set():
        return
    logger.info("Starting PIDLoggerWorker thread")
    thread = threading.Thread(target=_writer_loop_wrapper, daemon=True, name="PIDLoggerWorker")
    thread.start()
    _WORKER_STARTED.set()
    logger.info("PIDLoggerWorker thread started successfully")

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
