# 🧵 Multi-Threading Architecture (Kiến trúc Đa luồng) - start_mining.py

## 📋 Tổng quan Architecture

**Refactoring thành công** từ **sequential architecture** (kiến trúc tuần tự) sang **multi-threading architecture** (kiến trúc đa luồng) với **4 threads độc lập**:

### 🔧 Core Components

#### **EventBus System** (Hệ thống EventBus)
- **Memory-based EventBus** (EventBus dựa trên bộ nhớ) cho **inter-thread communication** (giao tiếp giữa luồng)
- **Thread-safe singleton** (singleton an toàn luồng) với **locking mechanism** (cơ chế khóa)
- **Event-driven architecture** (kiến trúc hướng sự kiện) để **coordination** (phối hợp)

#### **Thread Synchronization** (Đồng bộ hóa Luồng)  
- **Global stop_event** (sự kiện dừng toàn cục) cho **graceful shutdown** (tắt máy nhẹ nhàng)
- **process_lock** (khóa tiến trình) cho **thread-safe process management** (quản lý tiến trình an toàn luồng)
- **EventBus-based coordination** (phối hợp dựa trên EventBus) giữa các threads

---

## 🎯 Thread Architecture

### **Thread 1: Environment Setup** (Thiết lập Môi trường)
```python
def environment_setup_thread():
```

**Responsibilities** (Trách nhiệm):
- **Thread-safe environment initialization** (khởi tạo môi trường an toàn luồng)
- **Security context validation** (xác thực bối cảnh bảo mật) 
- **GPU access verification** (xác minh truy cập GPU)
- **eBPF filter loading** (tải bộ lọc eBPF)
- **Centralized setup_env.setup()** (thiết lập tập trung)

**EventBus Events** (Sự kiện EventBus):
- `thread:env_setup_complete` - **Environment ready** (môi trường sẵn sàng)
- `thread:env_setup_failed` - **Setup failure** (thất bại thiết lập)

### **Thread 2: CPU Mining** (Khai thác CPU)
```python
def cpu_mining_thread():
```

**Responsibilities** (Trách nhiệm):
- **CPU mining process lifecycle** (vòng đời tiến trình khai thác CPU)
- **PID tracking and registration** (theo dõi và đăng ký PID)
- **Process monitoring and restart** (giám sát và khởi động lại tiến trình)
- **Wait for environment setup** (đợi thiết lập môi trường)

**EventBus Events** (Sự kiện EventBus):
- `mining:cpu_pid_registered` - **CPU process started** (tiến trình CPU bắt đầu) với PID
- `mining:cpu_pid_heartbeat` - **Periodic health check** (kiểm tra sức khỏe định kỳ)

### **Thread 3: GPU Mining** (Khai thác GPU) 
```python
def gpu_mining_thread():
```

**Responsibilities** (Trách nhiệm):
- **GPU mining process lifecycle** (vòng đời tiến trình khai thác GPU)
- **PID tracking and registration** (theo dõi và đăng ký PID)
- **GPU configuration validation** (xác thực cấu hình GPU)
- **Optional execution** (thực thi tùy chọn) based on environment variables

**EventBus Events** (Sự kiện EventBus):
- `mining:gpu_pid_registered` - **GPU process started** (tiến trình GPU bắt đầu) với PID
- `mining:gpu_pid_heartbeat` - **Periodic health check** (kiểm tra sức khỏe định kỳ)

### **Thread 4: Resource Manager** (Trình quản lý Tài nguyên)
```python
def resource_manager_thread():
```

**Responsibilities** (Trách nhiệm):
- **ResourceManager initialization** (khởi tạo ResourceManager)
- **Configuration loading** (tải cấu hình) từ JSON
- **System resource monitoring** (giám sát tài nguyên hệ thống)
- **EventBus integration** (tích hợp EventBus)

**EventBus Events** (Sự kiện EventBus):
- `thread:resource_manager_ready` - **ResourceManager operational** (ResourceManager hoạt động)
- `thread:resource_manager_failed` - **ResourceManager failure** (ResourceManager thất bại)

---

## 🔄 Thread Coordination Flow

### **Sequential Startup** (Khởi động Tuần tự)
```
1. Environment Setup Thread    → Thiết lập môi trường
2. Resource Manager Thread     → Khởi động quản lý tài nguyên  
3. CPU Mining Thread          → Đợi env setup → Bắt đầu CPU mining
4. GPU Mining Thread          → Đợi env setup → Bắt đầu GPU mining (nếu enabled)
```

### **Dependency Management** (Quản lý Phụ thuộc)
- **CPU & GPU threads** **wait** (đợi) for **env setup completion** (hoàn thành thiết lập môi trường)
- **30-second timeout** (thời gian chờ 30 giây) for environment setup
- **EventBus subscription** (đăng ký EventBus) cho dependency coordination

### **Process Supervision** (Giám sát Tiến trình)
- **CPU thread**: 30-second **supervision interval** (khoảng thời gian giám sát)  
- **GPU thread**: 15-second **supervision interval** (khoảng thời gian giám sát)
- **Automatic restart** (khởi động lại tự động) với **retry limits** (giới hạn thử lại)
- **PID registration** (đăng ký PID) through EventBus

---

## 🛡️ Error Handling & Safety

### **Thread-Safe Operations** (Thao tác An toàn Luồng)
- **process_lock** protection cho **global process variables** (biến toàn cục)
- **EventBus thread-safe design** (thiết kế EventBus an toàn luồng)
- **Exception isolation** (cô lập ngoại lệ) per thread

### **Graceful Shutdown** (Tắt máy Nhẹ nhàng)
- **EventBus shutdown notification** (thông báo tắt EventBus)
- **10-second thread termination timeout** (thời gian chờ kết thúc luồng 10 giây)
- **Process cleanup** (dọn dẹp tiến trình) với **5-second graceful termination** (kết thúc nhẹ nhàng 5 giây)
- **Forced kill** (buộc giết) backup nếu graceful fails

### **Error Recovery** (Phục hồi Lỗi)
- **Thread failure detection** (phát hiện lỗi luồng) và logging
- **EventBus error events** (sự kiện lỗi EventBus): `thread:failure_detected`
- **System health monitoring** (giám sát sức khỏe hệ thống): `system:health_check`

---

## 🚀 Performance Benefits

### **Parallel Execution** (Thực thi Song song)
- **Environment setup** chạy **concurrent** (đồng thời) với **resource management** (quản lý tài nguyên)
- **Mining processes** start **immediately** (ngay lập tức) sau environment ready
- **Independent thread lifecycles** (vòng đời luồng độc lập)

### **Resource Optimization** (Tối ưu Tài nguyên)
- **Separate logging** (ghi nhật ký riêng biệt) per thread
- **Dedicated loggers** (logger chuyên dụng) để avoid log contention
- **EventBus memory backend** (backend bộ nhớ EventBus) để **low-overhead** (chi phí thấp)

### **Scalability** (Khả năng Mở rộng)
- **Modular thread design** (thiết kế luồng mô-đun) cho easy extension
- **EventBus pattern** (mẫu EventBus) supports additional threads
- **Configurable supervision intervals** (khoảng thời gian giám sát có thể cấu hình)

---

## 📊 Monitoring & Diagnostics

### **EventBus Events** (Sự kiện EventBus) để Tracking
- `thread:env_setup_complete`
- `thread:resource_manager_ready` 
- `mining:cpu_pid_registered`
- `mining:gpu_pid_registered`
- `mining:cpu_pid_heartbeat`
- `mining:gpu_pid_heartbeat`
- `thread:failure_detected`
- `system:health_check`
- `system:shutdown_initiated`

### **Log Files** (Tệp Nhật ký)
- `env_setup_thread.log` - **Environment setup** (thiết lập môi trường) logs
- `cpu_mining_thread.log` - **CPU mining** (khai thác CPU) lifecycle logs  
- `gpu_mining_thread.log` - **GPU mining** (khai thác GPU) lifecycle logs
- `resource_manager_thread.log` - **Resource management** (quản lý tài nguyên) logs

### **Health Indicators** (Chỉ số Sức khỏe)
- **Thread alive status** (trạng thái sống của luồng)
- **Process PID tracking** (theo dõi PID tiến trình)  
- **EventBus message flow** (luồng tin nhắn EventBus)
- **Supervision cycle timing** (thời gian chu kỳ giám sát)

---

## ⚙️ Configuration

### **Environment Variables** (Biến Môi trường)
- `MINING_SERVER_CPU` - **CPU mining server** (máy chủ khai thác CPU)
- `MINING_SERVER_GPU` - **GPU mining server** (máy chủ khai thác GPU)  
- `MINING_WALLET_CPU` - **CPU wallet address** (địa chỉ ví CPU)
- `MINING_WALLET_GPU` - **GPU wallet address** (địa chỉ ví GPU)
- `LOGS_DIR` - **Log directory path** (đường dẫn thư mục nhật ký)

### **Thread Configuration** (Cấu hình Luồng)
- **CPU supervision**: 30s interval, 5 max retries
- **GPU supervision**: 15s interval, 5 max retries  
- **Thread shutdown timeout**: 10s graceful termination
- **Process termination timeout**: 5s graceful + forced kill backup

---

## 🔧 Migration Notes

### **Deprecated Functions** (Hàm Bị Phản đối)
- `manage_cpu_miner()` → **Replaced by** `cpu_mining_thread()`
- `manage_gpu_miner()` → **Replaced by** `gpu_mining_thread()`  
- `start_resource_manager()` → **Replaced by** `resource_manager_thread()`
- `stop_resource_manager()` → **Replaced by** thread cleanup

### **Backward Compatibility** (Tương thích Ngược)
- **Deprecated functions preserved** (hàm phản đối được bảo tồn) cho compatibility
- **Warning messages** (tin nhắn cảnh báo) when deprecated functions called
- **Existing process variables** (biến tiến trình hiện có) maintained for compatibility

---

## ✅ Implementation Status

- ✅ **Environment Setup Thread** - Implemented with thread-safe operations
- ✅ **CPU Mining Thread** - Implemented with PID tracking and EventBus integration  
- ✅ **GPU Mining Thread** - Implemented with PID tracking and EventBus integration
- ✅ **Resource Manager Thread** - Implemented with EventBus integration
- ✅ **EventBus Communication** - Memory-based EventBus for inter-thread messaging
- ✅ **Thread Synchronization** - Global stop_event and process_lock protection
- ✅ **Error Handling** - Thread-safe error handling and graceful shutdown
- ✅ **Graceful Cleanup** - Thread termination with timeout and process cleanup

**Architecture validated** ✅: **Python syntax check passed** (kiểm tra cú pháp Python đã vượt qua)