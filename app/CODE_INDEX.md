## Mục lục codebase (Codebase Index – chỉ mục mã nguồn) cho `@app`

Tài liệu này lập chỉ mục toàn bộ nội dung trong thư mục `app` (Python package – gói Python) để cải thiện điều hướng và bảo trì, giữ nguyên cấu trúc hiện tại.

### Phạm vi
- **Files** (tệp – đơn vị mã/ cấu hình)
- **Modules/Packages** (mô-đun/gói – đơn vị import Python)
- **Dependencies** (phụ thuộc – thư viện bên ngoài) từ `requirements.txt`

### Cấu trúc thư mục (Directory Structure – cây tệp tổng quan)

```text
app/
  __init__.py
  start_mining.py
  requirements.txt
  build.log
  Dockerfile
  entrypoint.sh
  stunnel.conf
  inference-cuda
  inference-cuda.original
  libmlls-cuda.so

  mining_environment/
    __init__.py
    config/
      __init__.py
      coordination.json
      environmental_limits.json
      gpu_optimization_config.json
      hardware_optimization.json
      resource_config.json
      system_params.json
      threading_config.json

    coordination/
      __init__.py
      coordinator.py

    scripts/
      __init__.py
      cloak_strategies.py
      cross_process_coordination.py
      dag_synchronization.py
      error_management.py
      error_recovery_coordinator.py
      gpu_monitoring_dashboard.py
      gpu_optimization_orchestrator.py
      gpu_resource_monitor.py
      log_deduplication.py
      log_rotation_guard.py
      logging_compat.py
      logging_config.py
      module_loggers.py
      parallel_strategy_executor.py
      performance_profiler.py
      privileged_operations.py
      resource_control.py
      resource_manager.py
      setup_env.py
      stealth_monitor.py
      strategy_cache.py
      utils.py
      auxiliary_modules/
        __init__.py
        interfaces.py
        models.py

    stealth/
      __init__.py
      core/
        __init__.py
        stealth_activation_manager.py
      plugins/
        __init__.py
      wrappers/
        __init__.py
        stealth_inference_cuda.py

  pid_logger/
    __init__.py
    direct_registry.py
    mining_output_bridge.py
    worker.py
```

### Điểm vào chính (Main entry point – tệp chạy chính)
- `app/start_mining.py`: Khởi động môi trường, ResourceManager, và tiến trình khai thác GPU; tích hợp ghi log PID nâng cao và cơ chế dọn dẹp an toàn.

### Packages và mô-đun chính

- **`mining_environment`** (môi trường khai thác – cấu phần cốt lõi)
  - `config/` (cấu hình JSON – thông số hệ thống, tài nguyên, GPU)
  - `coordination/` (điều phối – điều phối hoạt động)
  - `scripts/` (logic chính – triển khai giám sát, tối ưu, ghi log, tài nguyên)
    - `resource_manager.py` (quản lý tài nguyên – vòng đời và readiness)
    - `privileged_operations.py` (thao tác đặc quyền – kiểm tra GPU/quyền)
    - `logging_config.py`, `module_loggers.py` (thiết lập và cung cấp logger)
    - `gpu_resource_monitor.py`, `performance_profiler.py` (giám sát hiệu năng)
    - `setup_env.py` (khởi tạo môi trường tập trung)
    - `auxiliary_modules/` (định nghĩa `interfaces.py`, `models.py`)
  - `stealth/` (ẩn danh – kích hoạt, wrapper GPU, plugin mở rộng)
    - `core/stealth_activation_manager.py` (kích hoạt/dọn dẹp chế độ ẩn)
    - `wrappers/stealth_inference_cuda.py` (wrapper GPU tự ẩn danh)

- **`pid_logger`** (ghi nhận và chuyển giao PID – theo dõi tiến trình)
  - `worker.py` (tiến trình nền ghi PID)
  - `direct_registry.py` (đăng ký trực tiếp PID và handoff)
  - `mining_output_bridge.py` (cầu nối đầu ra khai thác)

### Binaries/Artifacts (nhị phân/hiện vật – phục vụ runtime)
- `inference-cuda`, `inference-cuda.original` (trình thực thi GPU)
- `libmlls-cuda.so` (CUDA loader bắt buộc)
- `entrypoint.sh`, `Dockerfile`, `stunnel.conf` (khởi chạy/triển khai/bảo mật)

### Dependencies (Phụ thuộc – lấy từ `requirements.txt`)
Những thư viện cốt lõi được khai báo để vận hành GPU mining và tiện ích hệ thống:
- GPU/Monitoring: `pynvml`, `GPUtil`, `numpy`
- Hệ thống/IO: `psutil`, `aiofiles`, `aiorwlock`, `readerwriterlock`, `pyyaml`, `pyroute2`
- Bảo mật/Mã hóa: `cryptography`, `pycryptodome`
- Kiến trúc/Typing/Models: `pydantic`, `typing-extensions`, `importlib-metadata`, `types-*`
- Gỡ lỗi/Log: `loguru`, `ratelimiter`, `retrying`, `pyelftools`, `types-regex`

Chi tiết đầy đủ xem tệp `app/requirements.txt`.

#### Snapshot phụ thuộc (trích từ `requirements.txt`)
```text
# ✅ CORE GPU MINING DEPENDENCIES (Dependencies cốt lõi khai thác GPU)
pynvml==11.4.1
psutil
cryptography

# ✅ SYSTEM UTILITIES (Tiện ích hệ thống)
pyyaml>=6.0,<7.0
pycryptodome

# ✅ UTILITY LIBRARIES (Thư viện tiện ích) - Need verification
retrying
GPUtil
pyelftools
loguru
aiofiles
aiorwlock
readerwriterlock
ratelimiter
pydantic
numpy

# Thư viện Python cho xử lý hệ thống
importlib-metadata>=4.12.0
types-dataclasses>=0.6.6
types-requests>=2.28.11.17
typing-extensions>=4.5.0

# Thư viện cho compile và xử lý code
types-regex>=2022.10.31.3

# libbpf-python sẽ được cài qua apt
pyroute2
```

### Cách import (Import Paths – ví dụ nhanh)
```python
# Logging và cấu hình
from mining_environment.scripts.logging_config import setup_logging
from mining_environment.scripts.module_loggers import get_start_mining_logger

# Resource Manager, mô hình cấu hình, đặc quyền
from mining_environment.scripts.resource_manager import ResourceManager
from mining_environment.scripts.auxiliary_modules.models import ConfigModel
from mining_environment.scripts.privileged_operations import get_privileged_manager

# Stealth subsystem
from mining_environment.stealth.core.stealth_activation_manager import (
    initialize_stealth_activation, cleanup_stealth_activation
)

# PID Logger (đăng ký/truy vết PID)
from pid_logger import start_worker, log_pid, register_process
```

### Hướng dẫn điều hướng (Navigation – gợi ý nhanh)
- **Theo use-case** (trường hợp sử dụng):
  - Khởi động hệ thống: `start_mining.py`
  - Cấu hình/logging: `mining_environment/scripts/logging_config.py`, `module_loggers.py`
  - Tài nguyên GPU/Readiness: `mining_environment/scripts/resource_manager.py`
  - Ẩn danh GPU: `mining_environment/stealth/core/*`, `.../wrappers/*`
  - Cấu hình hệ thống: `mining_environment/config/*.json`
- **Theo vùng chức năng** (functional area): `scripts/` (logic), `stealth/` (ẩn danh), `pid_logger/` (theo dõi PID), `config/` (thiết lập)

### Quy ước bảo trì (Maintainability – khuyến nghị nhẹ)
- Giữ nguyên cấu trúc; thêm mô tả ngắn đầu file khi bổ sung mô-đun mới.
- Cập nhật danh sách tại đây khi thêm tệp mới hoặc đổi tên.
- Khi thêm phụ thuộc, khai báo trong `requirements.txt` và ghi chú mục đích.

---
Tài liệu này chỉ lập chỉ mục và mô tả; không thay đổi import path hay hành vi runtime.


