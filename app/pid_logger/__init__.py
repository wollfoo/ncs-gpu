"""pid_logger package (relocated vào app)

Enhanced PID Logger với Real Process Output Monitor.

API:
    - start_worker(): khởi động enhanced worker threads.
    - log_pid(pid, is_gpu): ghi một PID (legacy API).
    - register_process(pid, process_type, process_obj, process_name): đăng ký process để monitor runtime output.
    
Debug API:
    - debug_registry_status(): hiển thị trạng thái process registry.
    - force_test_output(test_pid, test_type): test output format.
    - manual_register_real_pids(): manual registration của real mining PIDs.
"""

from .worker import start_worker, log_pid, register_process, debug_registry_status, force_test_output, manual_register_real_pids, _WORKER_STARTED, _PROCESS_REGISTRY, force_restart_worker

# 🚀 **DIRECT REGISTRY INTEGRATION** (tích hợp registry trực tiếp)
from .direct_registry import (
    get_direct_registry,
    reset_direct_registry,
    ProcessInfo,
    DirectPIDRegistry
)
