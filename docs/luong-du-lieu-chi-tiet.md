# Tài liệu Chi Tiết Luồng Dữ liệu Chính - Hệ thống Khai thác GPU

## Tổng quan Kiến trúc Hệ thống

Hệ thống khai thác GPU tại `/home/azureuser/opus-gpu/app` được thiết kế theo mô hình **sequential architecture** (kiến trúc tuần tự) với **DirectPIDRegistry coordination** (phối hợp DirectPIDRegistry). Các thành phần chính tương tác thông qua một luồng dữ liệu được điều phối chặt chẽ để đảm bảo hiệu suất và bảo mật.

### Các Thành phần Cốt lõi:
- **start_mining.py**: Điểm khởi đầu và điều phối chính
- **DirectPIDRegistry**: Hệ thống đăng ký tiến trình tập trung
- **StealthActivationManager**: Quản lý kích hoạt ẩn danh
- **ResourceManager**: Quản lý tài nguyên GPU
- **HookCoordinator**: Điều phối hook và đồng bộ hóa
- **GPUOptimizationOrchestrator**: Điều phối tối ưu hóa GPU
- **GPUMonitoringDashboard**: Giám sát và theo dõi

---

## 1. Luồng Khởi động Khai thác (Mining Startup Flow)

### Mô tả chi tiết các module tham gia và cách chúng tương tác

Luồng khởi động khai thác là quá trình bắt đầu từ file `start_mining.py` và trải qua các bước sau:

1. **Khởi tạo môi trường** (Environment Initialization):
   - Module `initialize_environment()` thiết lập môi trường khai thác
   - Khởi tạo `privileged_manager` để quản lý các hoạt động cần quyền cao
   - Kiểm tra bối cảnh bảo mật và quyền truy cập GPU
   - Gọi `setup_env.setup()` để cấu hình môi trường tập trung

2. **Khởi động PID Logger Worker**:
   - Gọi `start_worker()` từ module `pid_logger` để bắt đầu theo dõi các tiến trình
   - Tạo cơ chế ghi log và theo dõi PID cho các tiến trình khai thác

3. **Khởi động Resource Manager**:
   - Tạo thread `EnhancedResourceManagerThread` để chạy `ResourceManager`
   - Chờ `ResourceManager` khởi tạo và sẵn sàng nhận handoffs
   - Đăng ký `ResourceManager` với `DirectPIDRegistry` để phối hợp quản lý tài nguyên

4. **Khởi động GPU Mining Process**:
   - Gọi `start_gpu_mining_process()` để bắt đầu tiến trình khai thác GPU
   - Sử dụng wrapper `stealth_inference_cuda.py` để kích hoạt chế độ ẩn danh
   - Thiết lập các tham số khai thác như thuật toán, pool, wallet

### Sơ đồ luồng dữ liệu khởi động khai thác

start_mining.py (main) │ ├─> initialize_environment() │ │ │ ├─> get_privileged_manager() ──> validate_security_context() │ │ └─> check_gpu_access() │ │ │ └─> setup_env.setup() │ ├─> start_worker() [pid_logger] │ ├─> start_resource_manager_thread() ──> ResourceManager._instance │ │ │ └─> register_resource_manager() [DirectPIDRegistry] │ └─> start_gpu_mining_process() │ ├─> stealth_inference_cuda.py [wrapper] │ │ │ └─> subprocess.Popen(inference-cuda) [real mining process] │ └─> register_process() [DirectPIDRegistry]


---

## 2. Luồng Đăng ký Tiến trình (Process Registration Flow)

### Các module liên quan và giao diện tương tác

Luồng đăng ký tiến trình là cơ chế để theo dõi và quản lý các tiến trình khai thác:

1. **DirectPIDRegistry**:
   - Trung tâm đăng ký và theo dõi các tiến trình khai thác
   - Cung cấp API để đăng ký, theo dõi và quản lý các tiến trình
   - Lưu trữ thông tin về các tiến trình đang chạy và metadata của chúng

2. **LockFreeProcessManager**:
   - Quản lý tiến trình không sử dụng khóa để tránh xung đột
   - Theo dõi cả wrapper process và real mining process
   - Cung cấp cơ chế graceful shutdown để kết thúc an toàn các tiến trình

3. **HookCoordinator**:
   - Điều phối giữa các thành phần khác nhau trong hệ thống
   - Nhận thông tin từ stealth wrapper và chuyển tiếp đến DirectPIDRegistry

### Luồng dữ liệu từ khi nhận yêu cầu đến khi hoàn tất đăng ký

start_gpu_mining_process() │ ├─> subprocess.Popen(stealth_wrapper) │ │ │ └─> stealth_inference_cuda.py │ │ │ ├─> subprocess.Popen(inference-cuda) │ │ │ └─> get_hook_coordinator().receive_from_stealth_wrapper() │ │ │ └─> DirectPIDRegistry.register_process() │ └─> process_manager.set_gpu_process() │ └─> log_pid() [pid_logger] │ └─> register_process() [DirectPIDRegistry] │ └─> notify_observers() [ResourceManager]


---

## 3. Luồng Kích hoạt Ẩn danh (Stealth Activation Flow)

### Cơ chế hoạt động của các module

Luồng kích hoạt ẩn danh là quá trình che giấu hoạt động khai thác tiền điện tử:

1. **StealthActivationManager**:
   - Quản lý trung tâm cho việc kích hoạt chế độ ẩn danh
   - Đăng ký observer với DirectPIDRegistry để nhận thông báo về tiến trình mới
   - Áp dụng các chiến lược ẩn danh cho các tiến trình khai thác

2. **Stealth Wrapper (stealth_inference_cuda.py)**:
   - Bọc tiến trình khai thác thực (inference-cuda)
   - Thực hiện các biện pháp ẩn danh như đổi tên tiến trình
   - Tạo môi trường sạch cho tiến trình khai thác

3. **HookCoordinator**:
   - Điều phối giữa stealth wrapper và các thành phần khác
   - Nhận thông tin từ stealth wrapper và chuyển tiếp đến DirectPIDRegistry

### Cách thức truyền và xử lý dữ liệu giữa các thành phần

initialize_stealth_activation() │ └─> get_stealth_activation_manager().initialize() │ ├─> _setup_direct_registry_observer() │ │ │ └─> direct_registry.register_observer(_on_process_registered) │ └─> _initialize_stealth_strategies()

stealth_inference_cuda.py [main] │ ├─> subprocess.Popen(inference-cuda) │ └─> get_hook_coordinator().receive_from_stealth_wrapper() │ └─> DirectPIDRegistry.register_process() │ └─> notify_observers() [StealthActivationManager._on_process_registered] │ └─> _activate_process_stealth() │ └─> _handle_gpu_stealth()


---

## 4. Luồng Tối ưu hóa GPU (GPU Optimization Flow)

### Các module quản lý tài nguyên GPU

Luồng tối ưu hóa GPU là quá trình tối ưu hiệu suất khai thác trên GPU:

1. **GPUOptimizationOrchestrator**:
   - Điều phối trung tâm cho tất cả các tác vụ tối ưu hóa GPU
   - Tích hợp các module khác như CrossProcessCoordinator, ParallelStrategyExecutor, và PerformanceProfiler
   - Quản lý chu kỳ tối ưu hóa liên tục

2. **OptimizedHardwareController**:
   - Điều khiển phần cứng GPU để tối ưu hiệu suất
   - Áp dụng các cài đặt như điều chỉnh xung nhịp, quản lý nhiệt độ

3. **StrategyEngine**:
   - Cung cấp các chiến lược tối ưu hóa khác nhau
   - Thực hiện các chiến lược như gpu_power, gpu_clock, temperature, memory

4. **MetricsCollectionHub**:
   - Thu thập và lưu trữ các số liệu hiệu suất
   - Cung cấp dữ liệu cho việc phân tích và tối ưu hóa

### Quy trình phân bổ và điều phối tài nguyên

ResourceManager.register_mining_process() │ └─> GPUOptimizationOrchestrator.optimize_for_pid() │ ├─> _reserve_gpu_resources() [CrossProcessCoordinator] │ ├─> _collect_gpu_metrics() [baseline] │ ├─> _prepare_strategy_tasks() │ │ │ └─> StrategyEngine.create_strategy() │ ├─> parallel_executor.execute_parallel() [ParallelStrategyExecutor] │ ├─> hardware_controller.optimize_for_pid() [OptimizedHardwareController] │ ├─> _collect_gpu_metrics() [post] │ └─> _release_gpu_resources() [CrossProcessCoordinator]



---

## 5. Luồng Giám sát và Điều chỉnh (Monitoring and Adjustment Flow)

### Hệ thống module giám sát

Luồng giám sát và điều chỉnh là quá trình theo dõi và điều chỉnh hiệu suất khai thác:

1. **ResourceManager**:
   - Quản lý tài nguyên hệ thống và giám sát hiệu suất
   - Điều phối việc phân bổ tài nguyên giữa các tiến trình
   - Phát hiện và xử lý các vấn đề hiệu suất

2. **PerformanceProfiler**:
   - Phân tích hiệu suất của các tiến trình khai thác
   - Thu thập và phân tích các số liệu hiệu suất
   - Cung cấp thông tin cho việc tối ưu hóa

3. **ErrorManagement**:
   - Phát hiện và báo cáo các lỗi trong hệ thống
   - Cung cấp cơ chế khôi phục từ lỗi

4. **StealthMonitor**:
   - Giám sát trạng thái ẩn danh của các tiến trình
   - Đảm bảo các biện pháp ẩn danh hoạt động hiệu quả

### Cơ chế phản hồi và điều chỉnh tự động

ResourceManager.monitor_thread() │ ├─> check_process_health() │ │ │ └─> process_manager.get_gpu_process_status() │ ├─> monitor_gpu_resources() │ │ │ └─> GPUResourceManager.get_gpu_metrics() │ └─> adjust_resources_if_needed() │ └─> GPUOptimizationOrchestrator.optimize_for_pid()

GPUOptimizationOrchestrator.start_continuous_optimization() │ └─> _continuous_optimization_loop() │ ├─> _compute_state_from_metrics() │ ├─> _select_interval_tier() │ ├─> optimize_for_pid() │ └─> _apply_jitter() [adaptive interval]


---

## Điểm giao tiếp quan trọng giữa các module

1. **DirectPIDRegistry ↔ ResourceManager**:
   - DirectPIDRegistry đăng ký ResourceManager để nhận thông báo về các tiến trình mới
   - ResourceManager sử dụng thông tin từ DirectPIDRegistry để quản lý tài nguyên

2. **StealthActivationManager ↔ DirectPIDRegistry**:
   - StealthActivationManager đăng ký observer với DirectPIDRegistry
   - DirectPIDRegistry thông báo cho StealthActivationManager khi có tiến trình mới

3. **HookCoordinator ↔ DirectPIDRegistry**:
   - HookCoordinator nhận thông tin từ stealth wrapper
   - HookCoordinator chuyển tiếp thông tin đến DirectPIDRegistry

4. **ResourceManager ↔ GPUOptimizationOrchestrator**:
   - ResourceManager gọi GPUOptimizationOrchestrator để tối ưu hóa tiến trình
   - GPUOptimizationOrchestrator báo cáo kết quả tối ưu hóa cho ResourceManager

5. **GPUOptimizationOrchestrator ↔ CrossProcessCoordinator**:
   - GPUOptimizationOrchestrator sử dụng CrossProcessCoordinator để đặt và giải phóng tài nguyên
   - CrossProcessCoordinator đảm bảo không có xung đột tài nguyên giữa các tiến trình

6. **GPUOptimizationOrchestrator ↔ ParallelStrategyExecutor**:
   - GPUOptimizationOrchestrator chuẩn bị các tác vụ chiến lược
   - ParallelStrategyExecutor thực thi các chiến lược song song

7. **GPUOptimizationOrchestrator ↔ OptimizedHardwareController**:
   - GPUOptimizationOrchestrator gọi OptimizedHardwareController để tối ưu hóa phần cứng
   - OptimizedHardwareController áp dụng các cài đặt phần cứng tối ưu

---

## Kết luận

Hệ thống khai thác GPU opus-gpu được thiết kế với kiến trúc tuần tự và phối hợp DirectPIDRegistry, tạo ra một luồng dữ liệu chặt chẽ và hiệu quả. Các thành phần chính như ResourceManager, StealthActivationManager, và GPUOptimizationOrchestrator tương tác với nhau thông qua các giao diện được định nghĩa rõ ràng, đảm bảo hiệu suất cao và khả năng mở rộng.

Luồng dữ liệu chính bắt đầu từ việc khởi động khai thác, qua đăng ký tiến trình, kích hoạt ẩn danh, tối ưu hóa GPU, và kết thúc với giám sát và điều chỉnh liên tục. Mỗi bước trong luồng này được thiết kế để tối ưu hóa hiệu suất khai thác và đảm bảo tính ổn định của hệ thống.


# Sơ đồ Luồng Chính Tổng thể - Hệ thống Khai thác GPU

## 🎯 LUỒNG CHÍNH TUYẾN TÍNH (MAIN LINEAR FLOW)

[🚀 Khởi động start_mining.py] → 
[⚙️ Khởi tạo Môi trường] → 
[📋 Khởi động PID Logger Worker] → 
[💾 Khởi động Resource Manager] → 
[🔨 Xây dựng Lệnh Khai thác] → 
[🎭 Khởi động Stealth Wrapper] → 
[📦 Tạo Process Khai thác Thực] → 
[📝 Đăng ký Process với DirectPIDRegistry] → 
[🛡️ Kích hoạt Stealth Activation Manager] → 
[🔄 Handoff từ HookCoordinator đến DirectPIDRegistry] → 
[⚡ Tối ưu hóa GPU bởi GPUOptimizationOrchestrator] → 
[📊 Thu thập Metrics Baseline] → 
[🔧 Thực thi Chiến lược Tối ưu Song song] → 
[🔌 Áp dụng Tối ưu Phần cứng] → 
[📈 Thu thập Metrics Sau Tối ưu] → 
[🏥 Giám sát Sức khỏe Hệ thống] → 
[🔄 Vòng lặp Tối ưu Liên tục]

## 📋 CHI TIẾT TỪNG BƯỚC

1. **[🚀 Khởi động start_mining.py]**
   - Điểm khởi đầu của toàn bộ hệ thống
   - Xử lý tham số dòng lệnh và cấu hình
   - Thiết lập logging và báo cáo lỗi

2. **[⚙️ Khởi tạo Môi trường]**
   - Gọi `initialize_environment()`
   - Khởi tạo `privileged_manager` để quản lý các hoạt động cần quyền cao
   - Kiểm tra bối cảnh bảo mật và quyền truy cập GPU
   - Cấu hình biến môi trường và thư mục làm việc

3. **[📋 Khởi động PID Logger Worker]**
   - Gọi `start_worker()` từ module `pid_logger`
   - Khởi tạo hệ thống theo dõi và ghi log PID
   - Chuẩn bị cơ chế theo dõi tiến trình

4. **[💾 Khởi động Resource Manager]**
   - Tạo thread `EnhancedResourceManagerThread`
   - Khởi tạo `ResourceManager` singleton
   - Đăng ký với `DirectPIDRegistry` để nhận thông báo về tiến trình mới
   - Chuẩn bị quản lý tài nguyên GPU

5. **[🔨 Xây dựng Lệnh Khai thác]**
   - Xây dựng lệnh khai thác dựa trên cấu hình
   - Thiết lập các tham số như thuật toán, pool, wallet
   - Chuẩn bị môi trường cho tiến trình khai thác

6. **[🎭 Khởi động Stealth Wrapper]**
   - Gọi `subprocess.Popen()` để khởi động `stealth_inference_cuda.py`
   - Thiết lập môi trường cho wrapper
   - Chuẩn bị cơ chế ẩn danh

7. **[📦 Tạo Process Khai thác Thực]**
   - Stealth wrapper gọi `subprocess.Popen()` để khởi động `inference-cuda`
   - Tạo tiến trình khai thác thực tế
   - Thiết lập môi trường sạch cho tiến trình khai thác

8. **[📝 Đăng ký Process với DirectPIDRegistry]**
   - Wrapper gọi `get_hook_coordinator().receive_from_stealth_wrapper()`
   - Đăng ký PID của tiến trình khai thác thực với `DirectPIDRegistry`
   - Lưu trữ metadata về tiến trình

9. **[🛡️ Kích hoạt Stealth Activation Manager]**
   - `DirectPIDRegistry` thông báo cho `StealthActivationManager`
   - `StealthActivationManager._on_process_registered()` được gọi
   - Kích hoạt chiến lược ẩn danh cho tiến trình khai thác

10. **[🔄 Handoff từ HookCoordinator đến DirectPIDRegistry]**
    - `HookCoordinator` chuyển tiếp thông tin từ stealth wrapper
    - `DirectPIDRegistry` thông báo cho các observer đã đăng ký
    - Hoàn tất quá trình đăng ký và kích hoạt

11. **[⚡ Tối ưu hóa GPU bởi GPUOptimizationOrchestrator]**
    - `ResourceManager` gọi `GPUOptimizationOrchestrator.optimize_for_pid()`
    - Bắt đầu quá trình tối ưu hóa GPU
    - Đặt tài nguyên thông qua `CrossProcessCoordinator`

12. **[📊 Thu thập Metrics Baseline]**
    - Thu thập số liệu cơ sở trước khi tối ưu
    - Ghi lại trạng thái ban đầu của GPU
    - Chuẩn bị cho việc so sánh trước/sau

13. **[🔧 Thực thi Chiến lược Tối ưu Song song]**
    - Chuẩn bị các tác vụ chiến lược (gpu_power, gpu_clock, temperature, memory)
    - Thực thi các chiến lược song song thông qua `ParallelStrategyExecutor`
    - Áp dụng các cài đặt tối ưu

14. **[🔌 Áp dụng Tối ưu Phần cứng]**
    - Gọi `hardware_controller.optimize_for_pid()`
    - Áp dụng các cài đặt phần cứng tối ưu
    - Điều chỉnh các thông số GPU

15. **[📈 Thu thập Metrics Sau Tối ưu]**
    - Thu thập số liệu sau khi tối ưu
    - So sánh với số liệu cơ sở
    - Đánh giá hiệu quả của quá trình tối ưu

16. **[🏥 Giám sát Sức khỏe Hệ thống]**
    - Theo dõi trạng thái của tiến trình khai thác
    - Giám sát tài nguyên GPU
    - Phát hiện và xử lý các vấn đề

17. **[🔄 Vòng lặp Tối ưu Liên tục]**
    - Khởi động `_continuous_optimization_loop()`
    - Tối ưu hóa định kỳ dựa trên khoảng thời gian được cấu hình
    - Điều chỉnh tài nguyên dựa trên điều kiện hiện tại

## 🔄 LUỒNG PHẢN HỒI VÀ PHỤC HỒI

[🏥 Giám sát Sức khỏe] → 
[⚠️ Phát hiện Lỗi] → 
[📝 Báo cáo Lỗi] → 
[🔄 Khôi phục Tự động] → 
[🚀 Khởi động lại Tiến trình] → 
[📋 Đăng ký lại với DirectPIDRegistry]

## 🔀 LUỒNG PHÂN NHÁNH CHÍNH

1. **Nhánh Stealth Mode**:
   [🎭 Stealth Wrapper] → 
   [🛡️ Stealth Activation] → 
   [🔒 Process Name Spoofing]

2. **Nhánh Tối ưu hóa**:
   [⚡ GPU Optimization] → 
   [🔧 Strategy Execution] → 
   [📊 Performance Metrics]

3. **Nhánh Giám sát**:
   [🏥 Health Monitor] → 
   [📈 Metrics Collection] → 
   [📊 Dashboard Update]


Sơ đồ Luồng Chính Tổng thể - Hệ thống Khai thác GPU
🎯 LUỒNG CHÍNH TUYẾN TÍNH (MAIN LINEAR FLOW)

┌─────────────────────────┐
│  🚀 start_mining.py     │
│  (Điểm khởi đầu)        │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  ⚙️ initialize_         │
│  environment()          │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  📋 pid_logger.         │
│  start_worker()         │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  💾 ResourceManager     │
│  Initialization         │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  🔨 Command Builder     │
│  (mining_command)       │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  🎭 stealth_inference_  │
│  cuda.py (Wrapper)      │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  📦 subprocess.Popen    │
│  (inference-cuda)       │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  📝 DirectPIDRegistry   │
│  register_process()     │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  🛡️ StealthActivation   │
│  Manager.initialize()   │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  🔄 HookCoordinator     │
│  receive_from_wrapper() │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  ⚡ GPUOptimization     │
│  Orchestrator           │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  📊 Metrics Collection  │
│  (baseline)             │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  🔧 ParallelStrategy    │
│  Executor               │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  🔌 OptimizedHardware   │
│  Controller             │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  📈 Metrics Collection  │
│  (post-optimization)    │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  🏥 Health Monitor      │
│  System                 │
└───────────┬─────────────┘
            ↓
┌─────────────────────────┐
│  🔄 Continuous          │
│  Optimization Loop      │
└─────────────────────────┘

Dưới đây là MAIN LINEAR FLOW (luồng tuyến tính chính – mô tả dễ hiểu, thuần văn bản, không sơ đồ) và đã bao gồm điểm nối cloaking/tối ưu GPU.

# Luồng tuyến tính chính

1) [start_mining.py](chính – orchestrator/điều phối khởi động)  
   ↓

2) `setup_env.setup()` (khởi tạo môi trường – biến môi trường, log, kiểm tra an ninh)  
   ↓

3) Privileged Manager (quản lý đặc quyền – kiểm tra quyền root/namespace cô lập)  
   ↓

4) `pid_logger.start_worker()` (khởi động worker – giám sát/ghi `PID` (mã tiến trình))  
   ↓

5) [stealth_inference_cuda.py](stealth wrapper – bọc tiến trình GPU, chuẩn hóa môi trường)  
   ↓

6) `inference-cuda` (nhị phân GPU – tiến trình khai thác thực thi)  
   ↓

7) [HookCoordinator](HookCoordinator) (điều phối hook – theo dõi, phục hồi, thực hiện handoff/bàn giao)  
   ↓

8) [DirectPIDRegistry](DirectPIDRegistry) (registry PID trực tiếp – ghi và notify observers/thông báo tới bộ quan sát)  
   ↓

9) [ResourceManager](ResourceManager) (quản lý tài nguyên GPU – nhận handoff, điều phối)  
   • [receive_from_registry()](receive_from_registry) (nhận bàn giao – đưa `PID` vào hàng đợi)  
   • PID Queue (hàng đợi PID – đệm xử lý; nếu đầy → xử lý tức thì)  
   • [_pid_processing_loop()](pid_processing_loop) (vòng lặp xử lý – rút `PID` từ hàng đợi)  
   • [trigger_cloaking()](trigger_cloaking) (kích hoạt cloaking – Stage 1 xây `CloakRequest`)  
   • `CloakCoordinator` (điều phối cloaking – Stage 2 quyết định chiến lược)  
   • Nếu cloaking “success” (thành công) → điểm nối tối ưu GPU:
     - `GPUOptimizationOrchestrator` (điều phối tối ưu GPU – chạy bất đồng bộ/thread nền)  
       · Cooldown bằng `GPU_OPT_COOLDOWN_SEC` (thời gian chờ nguội – tránh xung đột)  
       · Rẽ nhánh theo `OPTIMIZE_ALL_GPUS`:
         - Yes: `optimize_gpu_for_all_available(pid)` (tối ưu mọi GPU khả dụng)  
         - No: `optimize_gpu_for_process(pid, gpu_index=0)` (tối ưu 1 GPU – chọn GPU index 0 hiện tại)  
       · Safety check (kiểm tra an toàn – nhiệt/điều khiển) + Rollback (hoàn trả cấu hình) nếu rủi ro  
   • [_persistent_monitoring_loop()](persistent_monitoring_loop) (giám sát liên tục – thu thập metrics, dọn PID chết)
