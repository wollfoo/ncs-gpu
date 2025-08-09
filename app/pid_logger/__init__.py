"""pid_logger package (gói pid_logger – bộ công cụ ghi PID) (relocated vào app)

Enhanced PID Logger (bộ ghi PID nâng cao – công cụ theo dõi ID tiến trình cải tiến) với Real Process Output Monitor (giám sát đầu ra tiến trình thực – theo dõi kết quả trực tiếp).

API (giao diện lập trình ứng dụng):
    - start_worker() (khởi động worker): khởi động enhanced worker threads (luồng worker nâng cao).
    - log_pid(pid, is_gpu) (ghi PID): ghi một PID (ID tiến trình) (legacy API – giao diện cũ).
    - register_process(pid, process_type, process_obj, process_name) (đăng ký tiến trình): đăng ký process (tiến trình) để monitor runtime output (giám sát đầu ra thời gian chạy).
    
Debug API (giao diện gỡ lỗi):
    - debug_registry_status() (trạng thái registry gỡ lỗi): hiển thị trạng thái process registry (đăng ký tiến trình).
    - force_test_output(test_pid, test_type) (buộc thử đầu ra): thử output format (định dạng đầu ra).
    - manual_register_real_pids() (đăng ký PID thực thủ công): manual registration (đăng ký thủ công) của real mining PIDs (PID khai thác thực).
"""

from .worker import start_worker, log_pid, register_process, debug_registry_status, force_test_output, manual_register_real_pids, _WORKER_STARTED, _PROCESS_REGISTRY, force_restart_worker

# 🚀 DIRECT REGISTRY INTEGRATION (tích hợp registry trực tiếp)
from .direct_registry import (
    get_direct_registry,
    reset_direct_registry,
    ProcessInfo,
    DirectPIDRegistry
)
