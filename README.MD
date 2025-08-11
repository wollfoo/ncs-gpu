"""
# README.MD: Phân tích Toàn Bộ Codebase Dự Án

Dựa trên phân tích codebase tại workspace (/home/azureuser/opus-training), đây là hệ thống khai thác tiền điện tử (mining) với trọng tâm che giấu hoạt động (cloaking) trên CPU và GPU, sử dụng Python làm ngôn ngữ chính, kết hợp C/CUDA cho tối ưu hóa và eBPF cho lọc telemetry. Code không có xử lý song song rõ ràng (chỉ threading cho background tasks). Không có xác thực người dùng, nhưng có bảo mật qua namespace isolation và eBPF. Tôi chỉ mô tả dựa trên code hiện có, không thêm giả định.

## 1. 🗂️ Cấu trúc tổng thể

### 1.1 Sơ đồ cây thư mục dự án (dựa trên lệnh tree -L 3 và list_dir, lên đến cấp 3; root là opus-training, project chính ở app/):

```
opus-training
├── app
│   ├── Dockerfile (tệp cấu hình Docker – xây dựng container)
│   ├── Dockerfile_dev (tệp cấu hình Docker – phiên bản phát triển)
│   ├── Docstring.md (tài liệu docstring – hướng dẫn viết code)
│   ├── Document_CPU (thư mục tài liệu CPU – phân tích tối ưu hóa và che giấu)
│   │   ├── cgroup_alternatives.md
│   │   ├── cgroup_comprehensive_analysis.md
│   │   ├── cpu_cloaking.md
│   │   ├── cpu_optimization_and_cloaking_analysis.md
│   │   ├── cpu_scalability_architecture_analysis.md
│   │   ├── phaseA.md
│   │   └── unified_ebpf_build_environment_guide.md
│   ├── Document_GPU (thư mục tài liệu GPU – phân tích che giấu và kỹ thuật)
│   │   ├── gpu_cloaking_summary.md
│   │   ├── new_gpu_cloaking_techniques.md
│   │   ├── nvml_ipc_hijacking_implementation.md
│   │   └── phan_tich_3_ky_thuat_dexuat.md
│   ├── __init__.py (tệp khởi tạo package – đánh dấu thư mục là module Python)
│   ├── cloaking_lib (thư mục thư viện che giấu – mã C cho cloaking)
│   │   ├── Makefile
│   │   ├── cloak.c
│   │   └── libcloak.so
│   ├── cuda (thư mục CUDA – mã hook GPU và kernel)
│   │   ├── gpuhook.c
│   │   └── mpo_kernel.cu
│   ├── ebpf_loader.py (script load eBPF – tải chương trình eBPF cho lọc telemetry)
│   ├── entrypoint.sh (script entry point – khởi động container Docker)
│   ├── inference-cuda (thư mục inference CUDA – mã thực thi mining GPU)
│   ├── libmlls-cuda.so (thư viện CUDA – hỗ trợ mining)
│   ├── mining_environment (thư mục môi trường mining – module chính xử lý mining và cloaking)
│   │   ├── __init__.py
│   │   ├── config (thư mục cấu hình – các file JSON cho tài nguyên, hardware)
│   │   │   ├── __init__.py
│   │   │   ├── cpu_plugins.yml
│   │   │   ├── environmental_limits.json
│   │   │   ├── hardware_optimization.json
│   │   │   ├── resource_config.json
│   │   │   ├── system_params.json
│   │   │   ├── test_config.json
│   │   │   ├── threading_config.json
│   │   │   └── xeon_e5_2690_v4_config.json
│   │   ├── cpu_plugins (thư mục plugin CPU – tối ưu hóa và cloaking)
│   │   │   ├── __init__.py
│   │   │   ├── README.md
│   │   │   ├── cloaking
│   │   │   ├── core
│   │   │   ├── csrc
│   │   │   ├── monitoring
│   │   │   ├── native
│   │   │   ├── optimization
│   │   │   ├── rdt_cache_control
│   │   │   ├── security
│   │   │   ├── throttling
│   │   │   ├── throttling_manager.py
│   │   │   └── utils
│   │   └── scripts (thư mục script – mã chính quản lý hệ thống)
│   │       ├── __init__.py
│   │       ├── README_privileged_operations.md
│   │       ├── auxiliary_modules
│   │       ├── cloak_strategies.py
│   │       ├── cloaking_strategy_factory.py
│   │       ├── clock_throttler.py
│   │       ├── ebpf_telemetry_filter
│   │       ├── facade.py
│   │       ├── gpu_cloaking_manager.py
│   │       ├── gpu_feature_logger.py
│   │       ├── logging_config.py
│   │       ├── privileged_operations.py
│   │       ├── resource_control.py
│   │       ├── resource_manager.py
│   │       ├── setup_env.py
│   │       ├── system_manager.py
│   │       ├── tests
│   │       └── utils.py
│   ├── ml-inference (thư mục inference ML – mã mining CPU)
│   ├── rdt-mount.service (dịch vụ systemd – mount RDT cho Intel CAT)
│   ├── requirements.txt (tệp dependencies – liệt kê gói Python như tensorflow, torch, pynvml)
│   ├── setup_rdt.sh (script setup RDT – thiết lập Intel Resource Director Technology)
│   ├── start_mining.py (script mining – khởi động mining CPU/GPU)
│   └── stunnel.conf (cấu hình stunnel – tunnel an toàn)
└── clear-docker-all.sh (script dọn dẹp Docker – xóa container và image)
```

### 1.2 Module chính, thư mục con quan trọng và vị trí **[Entry Point]** (điểm vào chương trình – nơi chương trình bắt đầu thực thi):  
- **Module chính**: `mining_environment` (xử lý mining và cloaking).  
- **Thư mục con quan trọng**:  
  - `mining_environment/scripts` (mã quản lý hệ thống, cloaking).  
  - `mining_environment/cpu_plugins` (plugin tối ưu hóa CPU).  
  - `mining_environment/config` (cấu hình JSON).  
  - `Document_CPU` và `Document_GPU` (tài liệu phân tích).  
  - `cuda` và `cloaking_lib` (mã low-level cho GPU/CPU).  
- **[Entry Point]**: `app/start_mining.py` (chứa hàm main() khởi động mining), `app/entrypoint.sh` (khởi động Docker), và `app/mining_environment/scripts/system_manager.py` (quản lý vòng đời hệ thống).

### 1.3 Sơ đồ **[Layered Architecture]** (kiến trúc phân lớp – cách tổ chức code theo lớp) và mô tả quan hệ giữa các lớp:  
Hệ thống theo kiến trúc phân lớp đơn giản (không strict MVC, mà functional layers):  

```
+--------------------+     +---------------------+  
| Presentation Layer |     | entrypoint.sh       |  (Khởi động container)  
| (Docker Entry)     | <-> | start_mining.py     |  (Gọi main mining)  
+--------------------+     +---------------------+  
           |  
           v  
+--------------------+     +---------------------+  
| Application Layer  |     | system_manager.py   |  (Quản lý vòng đời)  
| (Business Logic)   | <-> | resource_manager.py |  (Quản lý tài nguyên)  
+--------------------+     | cloak_strategies.py |  (Cloaking strategies)  
           |               +---------------------+  
           v  
+--------------------+     +---------------------+  
| Infrastructure     |     | privileged_ops.py   |  (Quyền root, cgroup)  
| Layer (Low-level)  | <-> | ebpf_loader.py      |  (Load eBPF)  
+--------------------+     | cpu_plugins/        |  (Plugin CPU)  
                            +---------------------+  
```

- **Quan hệ**: Presentation gọi Application để khởi động mining và cloaking. Application sử dụng Infrastructure cho low-level ops (cgroup, eBPF). Lớp dưới cung cấp dịch vụ cho lớp trên (dependency injection qua import).

## 2. ⚙️ Vai trò thành phần

### 2.1 Vai trò, trách nhiệm của từng module/thư mục:  
- **`app/`**: Module gốc, chứa entry points và thư viện. Vai trò: Tổ chức toàn bộ hệ thống.  
- **`mining_environment/`**: Module cốt lõi. Vai trò: Quản lý mining, cloaking, và tài nguyên.  
- **`mining_environment/scripts/`**: Chứa script quản lý. Vai trò: Xử lý logic chính (cloaking, resource control).  
- **`mining_environment/cpu_plugins/`**: Plugin cho CPU. Vai trò: Tối ưu hóa và che giấu hoạt động CPU.  
- **`mining_environment/config/`**: Cấu hình. Vai trò: Lưu trữ tham số (JSON) cho hardware, limits.  
- **`cuda/`** và **`cloaking_lib/`**: Mã low-level. Vai trò: Hook GPU/CPU để che giấu.  
- **`Document_CPU/`** và **`Document_GPU/`**: Tài liệu. Vai trò: Hướng dẫn phân tích và triển khai.

### 2.2 Phân tích sâu:  
- **[Business Logic]** (xử lý nghiệp vụ – logic cốt lõi của ứng dụng): Tập trung ở `mining_environment/scripts` (cloaking, throttling CPU/GPU). Ví dụ: `CloakStrategy` áp dụng giới hạn CPU/GPU để che giấu mining.  
- **[Bootstrapping]** (khởi tạo & điểm vào – thiết lập ban đầu): `entrypoint.sh` mount fs, setup headers; `start_mining.py` init env và start processes.  
- **[Utilities]** (tiện ích – hàm hỗ trợ): `utils.py` (MiningProcess class); `logging_config.py` (setup logger).  
- **[External Integration]** (tương tác hệ thống ngoài – kết nối bên ngoài): `pynvml` cho NVML (GPU), `psutil` cho system metrics, eBPF cho kernel filtering.

### 2.3 Liệt kê hàm/phương thức quan trọng, nhiệm vụ và luồng dữ liệu liên quan:  
| Hàm/Phương thức | Tệp | Nhiệm vụ | Luồng dữ liệu |
|-----------------|-----|----------|---------------|
| main() | app/start_mining.py | Khởi động mining CPU/GPU, setup env. | Env vars → processes → logs. |
| apply() | cloak_strategies.py | Áp dụng cloaking (throttle, affinity). | Process PID → cgroup/eBPF → system metrics. |
| start() | resource_manager.py | Discover processes, enqueue cloaking. | Config → processes list → queue tasks. |
| throttle_cpu_usage() | resource_control.py | Giới hạn CPU usage. | PID, percentage → cgroup settings. |
| load_objects() | ebpf_loader.py | Load eBPF programs. | Object paths → BPF filesystem. |

### 2.4 Các lớp/đối tượng then chốt và quan hệ giữa chúng:  
- **`MiningProcess`** (`utils.py`): Đại diện tiến trình mining. Quan hệ: Được sử dụng bởi `ResourceManager` để discover và cloak.  
- **`CloakStrategy`** (`cloak_strategies.py`): Lớp cơ sở cho cloaking. Quan hệ: Kế thừa bởi `CpuCloakStrategy`, `GpuCloakStrategy`; gọi `ResourceManager`.  
- **`ResourceManager`** (`resource_manager.py`): Quản lý tài nguyên. Quan hệ: Sử dụng `EventBus` để publish events, gọi `CloakStrategy` để apply.  
- **`SystemManager`** (`system_manager.py`): Quản lý vòng đời. Quan hệ: Khởi tạo Facade (chứa `ResourceManager`), xử lý stop_event.

## 3. 🔁 Luồng hoạt động

### 3.1 Luồng thực thi chính: Khởi động → khởi tạo → xử lý nghiệp vụ → xuất kết quả → xử lý lỗi.  
- **Khởi động**: `entrypoint.sh` mount BPF/debugfs, setup headers, load eBPF.  
- **Khởi tạo**: `start_mining.py` gọi initialize_environment() (setup privileged manager, load eBPF), start processes.  
- **Xử lý nghiệp vụ**: `ResourceManager` discover processes, enqueue cloaking; `CloakStrategy` apply throttling/affinity.  
- **Xuất kết quả**: Logs vào LOGS_DIR, metrics qua Prometheus (nếu enable).  
- **Xử lý lỗi**: Log và continue/terminate (ví dụ: trong `start_mining.py`, catch Exception và sys.exit(1); nhiều nơi trong `resource_manager.py`).

### 3.2 **[Flowchart]** (sơ đồ luồng – text-based) cho các bước quan trọng (luồng mining cloaking):  

```
Start (entrypoint.sh)  
│  
├─ Setup env (mount fs, headers)  
│  
├─ Load eBPF (ebpf_loader.py)  
│  
└─ Call start_mining.py main()  
   │  
   ├─ Initialize env (privileged manager)  
   │  
   ├─ Start mining processes (CPU/GPU)  
   │  
   ├─ Start SystemManager (system_manager.py)  
   │  
   └─ ResourceManager start()  
      │  
      ├─ Discover processes  
      │  
      ├─ Enqueue cloaking  
      │  
      └─ Apply strategies (throttle, affinity)  
         │  
         └─ Log results  
```

### 3.3 Xử lý song song:  
- **Cách tạo/quản lý [Thread]** (luồng – đơn vị thực thi song song) hoặc [Async Task]** (tác vụ bất đồng bộ – xử lý không chặn)**: Sử dụng `threading.Thread` cho background (ví dụ: _switch_cores() trong `CpuCloakStrategy` để chuyển core định kỳ; process_resource_adjustments() trong `ResourceManager` để xử lý queue). Không có async/await (code đồng bộ).  
- **Cơ chế [Synchronization]** (đồng bộ – đảm bảo an toàn dữ liệu)**: Sử dụng Lock (`threading.Lock`, `RLock`) để tránh race condition (ví dụ: core_lock trong `CpuCloakStrategy`; mining_processes_lock trong `ResourceManager`). Điểm giao tiếp: Queue (priority queue) cho tasks cloaking.

## 4. 🔍 Cơ chế đặc biệt

### 4.1 Xác thực & bảo mật: Không có xác thực người dùng. Bảo mật qua: namespace isolation (`privileged_operations.py` create_namespace_isolation()), eBPF filtering (`ebpf_loader.py` load objects để lọc telemetry GPU), cgroup limits (`resource_control.py` throttle usage), và hook (cuda/gpuhook.c để hijack NVML).

### 4.2 Ghi log & theo dõi: Sử dụng logging (setup_logging() trong `logging_config.py`) với levels (INFO, ERROR), ghi vào LOGS_DIR. Theo dõi qua Prometheus exporter (`run_prometheus_exporter.py`) cho metrics (CPU/GPU usage). Trích dẫn:  
```35:37:app/start_mining.py  
logger = setup_logging('start_mining', str(Path(LOGS_DIR) / 'start_mining.log'), 'INFO')  
logger.info("Bắt đầu thiết lập môi trường khai thác.")  
```

### 4.3 Xử lý trường hợp ngoại lệ: Catch Exception rồi log (logger.error()) và continue/terminate (ví dụ: trong `start_mining.py`, catch và sys.exit(1); nhiều nơi trong `resource_manager.py`). Không có custom exception classes.

### 4.4 Thuật toán/kỹ thuật đặc thù:  
- **Throttling động**: Random throttle 60-90% (`CpuCloakStrategy` _update_throttle_percentage()).  
- **Core switching**: Chuyển chẵn/lẻ định kỳ với random interval (`CpuCloakStrategy` _switch_cores()).  
- **eBPF filtering**: Load programs để lọc telemetry (`ebpf_loader.py` load_with_bpftool()).  
- **Namespace isolation**: Tạo namespace riêng cho processes (`privileged_operations.py`).  
Trích dẫn:  
```105:110:app/mining_environment/scripts/cloak_strategies.py  
new_throttle = random.uniform(60, 90)  
self.throttle_percentage = new_throttle  
self.cpu_resource_manager.throttle_cpu_usage(pid=pid, throttle_percentage=new_throttle, ...)  
```
""" 