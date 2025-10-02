# GPU Mining Manager (Trình Quản Lý Khai Thác GPU)

**Complete GPU mining management system** (hệ thống quản lý khai thác GPU hoàn chỉnh)
cho **GPU Mining System Phase 2.2.3**.

## 🚀 Features (Tính Năng)

### ✅ **NVML GPU Monitoring** (Giám sát GPU qua NVML)
- **Real NVIDIA GPU enumeration** (liệt kê GPU NVIDIA thật)
- **Live thermal tracking** (theo dõi nhiệt độ thời gian thực)
- **Power and utilization metrics** (thông số điện năng và sử dụng)
- **Fan speed monitoring and control** (giám sát và điều khiển tốc độ quạt)

### 🌡️ **Smart Thermal Management** (Quản Lý Nhiệt Thông Minh)
- **Configurable temperature thresholds** (ngưỡng nhiệt có thể cấu hình)
- **Automatic fan control** (điều khiển quạt tự động)
- **Thermal event callbacks** (callback sự kiện nhiệt)
- **Overheat protection** (bảo vệ quá nhiệt)

### ⚡ **CUDA Context & Memory Management** (Quản Lý CUDA Context & Bộ Nhớ)
- **Lifecycle-managed CUDA contexts** (CUDA contexts có vòng đời được quản lý)
- **Thread-safe context switching** (chuyển đổi context an toàn thread)
- **DAG memory allocation strategies** (chiến lược cấp phát bộ nhớ DAG)
- **OOM error handling** (xử lý lỗi thiếu bộ nhớ)

### 🎯 **Multi-Algorithm Support** (Hỗ trợ Đa Thuật Toán)
- **Ethash** (Ethereum) - với epoch 30000
- **KawPow** (Ravencoin) - Ravencoin GPU mining
- **RandomX** (Monero) - CPU mining với GPU acceleration

### 📊 **Comprehensive Telemetry** (Telemetry Toàn Diện)
- **Real-time hashrate tracking** (theo dõi hashrate thời gian thực)
- **Device health monitoring** (giám sát sức khỏe thiết bị)
- **Performance metrics collection** (thu thập số liệu hiệu năng)
- **Background stats collection** (thu thập thống kê nền)

## 🏗️ **Architecture** (Kiến Trúc)

```
gpu/
├── manager.rs       # GpuManager (orchestrator) - điều phối viên chính
├── device.rs        # GpuDevice (NVIDIA GPU abstraction) - trừu tượng hóa GPU
├── context.rs       # CudaContextManager - quản lý CUDA contexts
├── memory.rs        # DagMemoryManager - quản lý bộ nhớ DAG
├── thermal.rs       # ThermalMonitor - giám sát nhiệt độ
├── error.rs         # GpuError types - định nghĩa lỗi GPU
├── integration_example.rs # Usage examples - ví dụ sử dụng
└── manager_tests.rs # Unit tests - unit tests
```

## 📝 **Quick Start** (Bắt Đầu Nhanh)

### **Basic Setup** (Thiết Lập Cơ Bản)

```rust
use mining_core::gpu::{GpuManager, GpuAlgorithm, ThermalThresholds};

// Tạo GPU Manager với thermal monitoring
let manager = GpuManager::builder()
    .with_thermal_thresholds(ThermalThresholds::default())
    .enable_auto_fan_control()
    .build();

// Liệt kê GPU có sẵn
let devices = manager.enumerate_devices().await?;
println!("Found {} GPUs", devices.len());

// Khởi tạo cho Ethash mining
manager.initialize_for_algorithm(GpuAlgorithm::Ethash, &[0, 1]).await?;

// Bắt đầu giám sát nền
manager.start_monitoring_loop().await;

// Lấy thống kê mining
let stats = manager.get_mining_stats().await?;
println!("Hashrate: {:.2} MH/s", stats.total_hashrate());

// Cleanup
manager.cleanup().await?;
```

### **Advanced Configuration** (Cấu Hình Nâng Cao)

```rust
use mining_core::gpu::{GpuManager, GpuAlgorithm, ThermalThresholds};

// Cấu hình thermal tùy chỉnh
let thresholds = ThermalThresholds {
    warning_celsius: 75.0,
    critical_celsius: 85.0,
    max_fan_speed: 80,
};

// Tạo manager với đầy đủ tính năng
let manager = GpuManager::builder()
    .with_thermal_thresholds(thresholds)
    .enable_auto_fan_control()
    .build();

// Multi-algorithm support
for algorithm in &[GpuAlgorithm::Ethash, GpuAlgorithm::KawPow] {
    manager.initialize_for_algorithm(*algorithm, &[0]).await?;
    // Run mining...
    manager.cleanup().await?;
}
```

## 🛠️ **Dependencies** (Phụ Thuộc)

### **NVML Support** (Hỗ Trợ NVML)
```toml
[features]
default = ["nvml"]
nvml = ["nvml-wrapper"]
```

### **CUDA Support** (Hỗ Trợ CUDA)
```toml
[dependencies]
cuda-runtime-sys = { workspace = true }
parking_lot = "0.12"
serde = { workspace = true }
tokio = { workspace = true }
tracing = { workspace = true }
```

## 🔧 **Error Handling** (Xử Lý Lỗi)

### **Common Errors** (Lỗi Thường Gặp)

```rust
use mining_core::gpu::GpuError;

// Device not found
match manager.initialize_for_algorithm(GpuAlgorithm::Ethash, &[999]).await {
    Ok(_) => println!("Success"),
    Err(GpuError::DeviceNotFound(id)) => println!("GPU {} not found", id),
    Err(GpuError::NvmlInitFailed(msg)) => println!("NVML error: {}", msg),
    Err(GpuError::CudaDriverNotFound) => println!("CUDA driver not installed"),
    Err(GpuError::InsufficientMemory { device_id, required, available }) =>
        println!("GPU {} needs {}MB, only {}MB available",
                device_id, required/1024/1024, available/1024/1024),
    _ => println!("Other error"),
}
```

### **Graceful Degradation** (Degradation Thân Thiện)
- **No NVML**: Falls back to CPU-only mode
- **Insufficient memory**: Logs warning, reduces intensity
- **Thermal issues**: Auto-adjusts fan speed, shuts down if critical

## 📊 **Performance Characteristics** (Đặc Điểm Hiệu Năng)

| Metric | Target | Requirement |
|--------|--------|-------------|
| **Monitoring overhead** | <1% CPU | Low-latency operation |
| **ENUM enumeration** | <100ms | Fast device discovery |
| **Context switching** | <500μs | Minimal overhead |
| **Memory allocation** | <50ms | One-time setup cost |
| **Telemetry latency** | <5ms | Real-time monitoring |

## 🧪 **Testing** (Kiểm Tra)

### **Unit Tests** (Unit Tests)
```bash
cargo test gpu::manager_tests
cargo test gpu::device::tests
cargo test gpu::memory::tests
```

### **Integration Tests** (Integration Tests)
```bash
# Với GPU thật (có NVML)
cargo test --features nvml gpu::integration_tests

# Chỉ CPU (stub mode)
cargo test gpu::manager_tests::tests::test_enumerate_devices_fallback
```

### **Hardware Requirements** (Yêu Cầu Phần Cứng)
- **Supported GPUs**: NVIDIA RTX 20xx/30xx series +
- **Compute Capability**: 7.0+ (minimum)
- **VRAM**: 8GB+ recommended for mining
- **CUDA Driver**: 11.0+ (automatic fallback)

## 📚 **API Reference** (Tham Chiếu API)

### **GpuManager** (Main Interface)
- `new()` / `builder()`: Constructor methods
- `enumerate_devices()`: Discover available GPUs
- `initialize_for_algorithm()`: Setup for mining
- `start_monitoring_loop()`: Background monitoring
- `get_mining_stats()`: Current performance stats
- `cleanup()`: Resource cleanup

### **GpuAlgorithm** (Mining Algorithms)
- `Ethash(min_cc: 7.0)`: Ethereum Proof-of-Work
- `KawPow(min_cc: 7.0)`: Ravencoin GPU mining
- `RandomX(min_cc: 7.5)`: Monero with GPU acceleration

### **ThermalThresholds** (Thermal Configuration)
- `warning_celsius`: Warning temperature (°C)
- `critical_celsius`: Critical temperature (°C)
- `max_fan_speed`: Maximum fan speed (%)

See: `src/gpu/integration_example.rs` for complete usage patterns.

## 🔍 **Troubleshooting** (Khắc Phục Sự Cố)

### **"NVML not available"**
```bash
# Install NVIDIA drivers
sudo apt install nvidia-driver-525

# Enable NVML feature
cargo build --features nvml
```

### **"CUDA driver not found"**
```bash
# Install CUDA toolkit
# https://developer.nvidia.com/cuda-downloads

# Verify installation
nvidia-smi
```

### **"Insufficient memory"**
- Reduce mining intensity in config
- Use fewer GPUs simultaneously
- Switch to lower-memory algorithm (KawPow > Ethash > RandomX)

### **Performance Issues**
- Enable `--release` builds
- Check GPU utilization with `nvidia-smi`
- Monitor temperatures and fan speeds

## 🏆 **Success Criteria** (Tiêu Chí Thành Công)

✅ **Enumerates GPUs Successfully** - Real NVIDIA GPU discovery via NVML
✅ **Monitors Temperature** - Live thermal tracking with <1% CPU overhead
✅ **Creates CUDA Contexts** - Memory-safe context management without leaks
✅ **Allocates DAG Memory** - Proper memory pooling for typical mining scenarios
✅ **Clean Shutdown** - Releases all resources safely

## 📄 **License**

MIT License - See [LICENSE](../../../LICENSE)