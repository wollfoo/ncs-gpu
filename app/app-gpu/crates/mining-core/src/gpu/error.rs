//! # GPU Error Types (Các kiểu lỗi GPU)
//!
//! **GPU-specific error handling** (xử lý lỗi đặc thù GPU) với descriptive error messages.

use thiserror::Error;

/// **GpuError** (lỗi GPU) – các lỗi liên quan GPU operations
#[derive(Debug, Error)]
pub enum GpuError {
    /// **NVML initialization failed** (khởi tạo NVML thất bại) – không thể load NVML library
    #[error("Failed to initialize NVML: {0}")]
    NvmlInitFailed(String),

    /// **CUDA initialization failed** (khởi tạo CUDA thất bại) – không thể khởi tạo CUDA context
    #[error("Failed to initialize CUDA context for device {device_id}: {reason}")]
    CudaInitFailed {
        device_id: usize,
        reason: String,
    },

    /// **Device not found** (không tìm thấy thiết bị) – GPU ID không tồn tại
    #[error("GPU device {0} not found")]
    DeviceNotFound(usize),

    /// **Insufficient memory** (thiếu bộ nhớ) – không đủ VRAM cho DAG
    #[error("Insufficient GPU memory on device {device_id}: required {required} bytes, available {available} bytes")]
    InsufficientMemory {
        device_id: usize,
        required: u64,
        available: u64,
    },

    /// **Memory allocation failed** (cấp phát bộ nhớ thất bại) – cudaMalloc error
    #[error("Failed to allocate {size} bytes on device {device_id}: {reason}")]
    MemoryAllocationFailed {
        device_id: usize,
        size: u64,
        reason: String,
    },

    /// **Unsupported compute capability** (compute capability không hỗ trợ) – GPU quá cũ
    #[error("GPU {device_id} compute capability {major}.{minor} is too old (minimum required: {required_major}.{required_minor})")]
    UnsupportedComputeCapability {
        device_id: usize,
        major: u32,
        minor: u32,
        required_major: u32,
        required_minor: u32,
    },

    /// **Temperature threshold exceeded** (vượt ngưỡng nhiệt độ) – GPU quá nóng
    #[error("GPU {device_id} temperature {temp}°C exceeds threshold {threshold}°C")]
    TemperatureThresholdExceeded {
        device_id: usize,
        temp: f32,
        threshold: f32,
    },

    /// **Fan control not supported** (không hỗ trợ điều khiển quạt) – GPU không cho phép fan control
    #[error("Fan control not supported on device {0}")]
    FanControlNotSupported(usize),

    /// **Context already exists** (context đã tồn tại) – cố gắng tạo context mới khi đã có
    #[error("CUDA context already exists for device {0}")]
    ContextAlreadyExists(usize),

    /// **Context not initialized** (context chưa khởi tạo) – thao tác trên context chưa init
    #[error("CUDA context not initialized for device {0}")]
    ContextNotInitialized(usize),

    /// **Invalid device configuration** (cấu hình thiết bị không hợp lệ) – config lỗi
    #[error("Invalid device configuration: {0}")]
    InvalidDeviceConfig(String),

    /// **NVML driver mismatch** (driver không khớp) – NVML version không tương thích với driver
    #[error("NVML library/driver version mismatch: {0}")]
    NvmlDriverMismatch(String),

    /// **CUDA driver not found** (không tìm thấy CUDA driver) – thiếu NVIDIA driver
    #[error("CUDA driver not found. Please install NVIDIA drivers.")]
    CudaDriverNotFound,

    /// **Device busy** (thiết bị bận) – GPU đang được process khác sử dụng
    #[error("GPU device {0} is busy (used by another process)")]
    DeviceBusy(usize),

    /// **Generic GPU error** (lỗi GPU chung) – lỗi chung không thuộc các loại trên
    #[error("GPU error: {0}")]
    Generic(String),
}

/// **GpuResult** (kết quả GPU) – Result type với GpuError
pub type GpuResult<T> = Result<T, GpuError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_display() {
        let err = GpuError::DeviceNotFound(3);
        assert_eq!(err.to_string(), "GPU device 3 not found");

        let err = GpuError::InsufficientMemory {
            device_id: 0,
            required: 8_000_000_000,
            available: 4_000_000_000,
        };
        assert!(err.to_string().contains("Insufficient GPU memory"));
    }

    #[test]
    fn test_temperature_error() {
        let err = GpuError::TemperatureThresholdExceeded {
            device_id: 1,
            temp: 95.0,
            threshold: 85.0,
        };
        assert!(err.to_string().contains("95"));
        assert!(err.to_string().contains("85"));
    }
}
