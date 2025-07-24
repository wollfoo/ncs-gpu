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

# Cấu hình
LOG_DIR = os.getenv("LOGS_DIR", "/app/mining_environment/logs")
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

def _writer_loop():
    logger.info("PID logger worker thread started")
    _ensure_log_dir()
    logger.debug(f"Log directory verified: {LOG_DIR}")
    files = {
        "cpu": PID_CPU_FILE.open("a", buffering=1, encoding="utf-8"),
        "gpu": PID_GPU_FILE.open("a", buffering=1, encoding="utf-8"),
    }
    while not _STOP_EVENT.is_set():
        try:
            item = _QUEUE.get(timeout=1)
        except queue.Empty:
            continue
        logger.debug(f"Dequeued item: {item}")
        f = files[item["type"]]
        _rotate_if_needed(f.name if isinstance(f,str) else pathlib.Path(f.name))
        try:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        except Exception:
            try:
                f.close()
            except Exception:
                pass
            files[item["type"]] = (PID_CPU_FILE if item["type"]=="cpu" else PID_GPU_FILE).open("a", buffering=1, encoding="utf-8")
    for f in files.values():
        try:
            f.close()
        except Exception:
            pass

def start_worker():
    if _WORKER_STARTED.is_set():
        return
    _WORKER_STARTED.set()
        logger.debug("Starting PIDLoggerWorker thread")
    threading.Thread(target=_writer_loop, daemon=True, name="PIDLoggerWorker").start()

def log_pid(pid: int, is_cpu: bool):
        logger.debug(f"Logging PID {pid} (is_cpu={is_cpu})")
    enqueue_pid(pid, "cpu" if is_cpu else "gpu")
