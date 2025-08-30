import sys
import os
import time
import logging
import threading
import types
import io
from pathlib import Path

import pytest

# Ensure 'app/' is on sys.path so 'mining_environment' package is importable
APP_DIR = Path(__file__).resolve().parents[1] / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Stub 'pynvml' to avoid NVML dependency during tests
if 'pynvml' not in sys.modules:
    _pynvml = types.ModuleType('pynvml')
    setattr(_pynvml, 'nvmlInit', lambda: None)
    class _NVMLError(Exception):
        pass
    setattr(_pynvml, 'NVMLError', _NVMLError)
    setattr(_pynvml, 'NVML_TEMPERATURE_GPU', 0)
    setattr(_pynvml, 'NVML_CLOCK_SM', 0)
    setattr(_pynvml, 'NVML_CLOCK_MEM', 0)
    sys.modules['pynvml'] = _pynvml

# Stub GPUOptimizationOrchestrator to avoid importing heavy modules with filesystem side-effects
stub_orch_module_name = 'mining_environment.scripts.gpu_optimization_orchestrator'
if stub_orch_module_name not in sys.modules:
    _orch = types.ModuleType(stub_orch_module_name)
    class GPUOptimizationOrchestrator:  # minimal stub
        def __init__(self, *args, **kwargs):
            pass
        def optimize_gpu_for_process(self, *args, **kwargs):
            return True
    setattr(_orch, 'GPUOptimizationOrchestrator', GPUOptimizationOrchestrator)
    sys.modules[stub_orch_module_name] = _orch

from mining_environment.scripts.resource_manager import ResourceManager


class DummyConfig:
    def __init__(self):
        # Minimal field to satisfy _validate_configuration()
        self.cloaking_strategies = {"one_shot_apply": {}}


def test_receive_from_registry_reservation_dedup_entry(caplog):
    """
    Verify early reservation-based de-duplication at entry:
    - First call reserves the PID, begins immediate processing (monkeypatched).
    - Second call arrives during reservation window → should log
      "⏩ [ENTRY] Skip duplicate PID ..." and return early.
    - Only one simulated processing should occur.
    """
    # Capture all logs at DEBUG to ensure skip message is recorded
    caplog.set_level(logging.DEBUG)
    # Attach in-memory log capture handler to 'resource_manager' logger (module logger used by ResourceManager)
    rm_logger = logging.getLogger("resource_manager")
    rm_logger.setLevel(logging.DEBUG)
    log_buffer = io.StringIO()
    buffer_handler = logging.StreamHandler(log_buffer)
    buffer_handler.setLevel(logging.DEBUG)
    rm_logger.addHandler(buffer_handler)

    # Initialize ResourceManager with dummy config to avoid strict checks
    rm = ResourceManager(config=DummyConfig(), logger=logging.getLogger("resource_manager.test"))
    # Start worker threads so queued PID will be consumed by processing loop
    rm.start()

    # Avoid any GPU optimization path in tests
    try:
        rm._gpu_orchestrator = None
    except Exception:
        pass

    # Monkeypatch _process_pid_immediately to control timing and avoid heavy work
    original_process_immediately = getattr(rm, "_process_pid_immediately")

    def stub_process_immediately(self, pid_data):
        pid = pid_data["pid"]
        # Hold reservation for a short window to allow second entry to hit skip path
        time.sleep(0.2)
        # Release reservation as real code would at start
        try:
            self._release_pid_reservation(pid)
        except Exception:
            pass
        # Mark as processed to emulate successful processing
        try:
            self._mark_pid_seen_if_new(pid)
        except Exception:
            pass
        self.logger.info(f"[TEST] Simulated processing PID {pid}")
        return True

    rm._process_pid_immediately = types.MethodType(stub_process_immediately, rm)

    pid = os.getpid()

    md1 = {"pid": pid, "source": "direct_registry_handoff", "process_name": f"test_pid_{pid}"}
    md2 = {"pid": pid, "source": "file_scanner", "process_name": f"test_pid_{pid}"}

    t1 = threading.Thread(target=lambda: rm.receive_from_registry(pid, md1))
    t1.start()
    # Send second entry shortly after first; within the reservation window
    time.sleep(0.01)
    rm.receive_from_registry(pid, md2)
    t1.join(timeout=2.0)
    # Wait until background worker processed queued PID
    try:
        rm._pid_queue.join()
    except Exception:
        pass

    # Read logs from in-memory buffer
    logs = log_buffer.getvalue()
    assert "⏩ [ENTRY] Skip duplicate PID" in logs, "Expected reservation dedup skip log was not found"
    # Ensure exactly one simulated processing occurrence
    assert logs.count("[TEST] Simulated processing PID") == 1

    # Restore original method to avoid side-effects for other tests
    rm._process_pid_immediately = original_process_immediately
    rm_logger.removeHandler(buffer_handler)
    # Shutdown ResourceManager to stop background threads
    try:
        rm.shutdown()
    except Exception:
        pass
