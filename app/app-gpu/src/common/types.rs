//! Core types and type aliases for OPUS-GPU
//!
//! **Shared Type Definitions** (Định nghĩa kiểu dùng chung) used across the OPUS-GPU system

use std::fmt;
use serde::{Deserialize, Serialize};

/// **GPU device identifier** (Định danh thiết bị GPU)
pub type GpuId = u32;

/// **Hash rate measurement** (Đo lường tốc độ hash) in hashes per second
pub type HashRate = f64;

/// **Temperature measurement** (Đo lường nhiệt độ) in Celsius
pub type Temperature = f32;

/// **Power usage measurement** (Đo lường tiêu thụ điện) in watts
pub type PowerUsage = f32;

/// **Memory size** (Kích thước bộ nhớ) in bytes
pub type MemorySize = u64;

/// **Timestamp** (Dấu thời gian) using UTC
pub type Timestamp = chrono::DateTime<chrono::Utc>;

/// **Worker thread identifier** (Định danh luồng worker)
pub type WorkerId = u32;

/// **Mining pool job ID** (ID công việc từ mining pool)
pub type JobId = String;

/// **Mining difficulty target** (Mục tiêu độ khó đào)
pub type DifficultyTarget = Vec<u8>;

/// **Nonce value** (Giá trị nonce) for mining
pub type Nonce = u64;

/// **Device performance metrics** (Chỉ số hiệu suất thiết bị)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceMetrics {
    /// **Device ID** (ID thiết bị)
    pub device_id: GpuId,
    /// **Current hash rate** (Tốc độ hash hiện tại)
    pub hash_rate: HashRate,
    /// **Device temperature** (Nhiệt độ thiết bị)
    pub temperature: Temperature,
    /// **Power consumption** (Tiêu thụ điện)
    pub power_usage: PowerUsage,
    /// **Memory utilization** (Sử dụng bộ nhớ) as percentage (0.0-1.0)
    pub memory_utilization: f32,
    /// **GPU utilization** (Sử dụng GPU) as percentage (0.0-1.0)
    pub gpu_utilization: f32,
    /// **Fan speed** (Tốc độ quạt) as percentage (0.0-1.0)
    pub fan_speed: f32,
    /// **Measurement timestamp** (Thời điểm đo)
    pub timestamp: Timestamp,
}

/// **System-wide performance statistics** (Thống kê hiệu suất toàn hệ thống)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemStats {
    /// **Total hash rate** (Tổng tốc độ hash) across all devices
    pub total_hashrate: HashRate,
    /// **Total power consumption** (Tổng tiêu thụ điện)
    pub total_power: PowerUsage,
    /// **Average temperature** (Nhiệt độ trung bình) across all devices
    pub average_temperature: Temperature,
    /// **System CPU usage** (Sử dụng CPU hệ thống) as percentage (0.0-1.0)
    pub cpu_usage: f32,
    /// **System memory usage** (Sử dụng bộ nhớ hệ thống) as percentage (0.0-1.0)
    pub memory_usage: f32,
    /// **GPU memory usage** (Sử dụng bộ nhớ GPU) as percentage (0.0-1.0)
    pub gpu_usage: f32,
    /// **Number of active workers** (Số worker đang hoạt động)
    pub active_workers: usize,
    /// **Uptime** (Thời gian hoạt động) in seconds
    pub uptime_seconds: u64,
    /// **Statistics timestamp** (Thời điểm thống kê)
    pub timestamp: Timestamp,
}

/// **GPU device information** (Thông tin thiết bị GPU)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuInfo {
    /// **Device ID** (ID thiết bị)
    pub device_id: GpuId,
    /// **Device name** (Tên thiết bị)
    pub name: String,
    /// **Total memory** (Tổng bộ nhớ) in bytes
    pub total_memory: MemorySize,
    /// **Free memory** (Bộ nhớ trống) in bytes
    pub free_memory: MemorySize,
    /// **Compute capability** (Khả năng tính toán) (major, minor)
    pub compute_capability: (i32, i32),
    /// **Number of SMs** (Số lượng SM)
    pub multiprocessor_count: i32,
    /// **Max threads per block** (Tối đa luồng trên block)
    pub max_threads_per_block: i32,
    /// **CUDA driver version** (Phiên bản driver CUDA)
    pub driver_version: String,
    /// **Current status** (Trạng thái hiện tại)
    pub status: GpuStatus,
}

/// **GPU device status** (Trạng thái thiết bị GPU)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum GpuStatus {
    /// **Available for mining** (Có sẵn để đào)
    Available,
    /// **Currently mining** (Đang đào)
    Mining,
    /// **Thermal throttling** (Điều chỉnh nhiệt)
    ThermalThrottling,
    /// **Error state** (Trạng thái lỗi)
    Error(String),
    /// **Disabled** (Bị tắt)
    Disabled,
}

impl fmt::Display for GpuStatus {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            GpuStatus::Available => write!(f, "Available"),
            GpuStatus::Mining => write!(f, "Mining"),
            GpuStatus::ThermalThrottling => write!(f, "Thermal Throttling"),
            GpuStatus::Error(msg) => write!(f, "Error: {}", msg),
            GpuStatus::Disabled => write!(f, "Disabled"),
        }
    }
}

/// **Mining work unit** (Đơn vị công việc đào)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkUnit {
    /// **Job identifier** (Định danh công việc)
    pub job_id: JobId,
    /// **Block header** (Header block)
    pub header: Vec<u8>,
    /// **Difficulty target** (Mục tiêu độ khó)
    pub target: DifficultyTarget,
    /// **Starting nonce** (Nonce bắt đầu)
    pub nonce_start: Nonce,
    /// **Nonce range** (Phạm vi nonce)
    pub nonce_range: u32,
    /// **Creation timestamp** (Thời điểm tạo)
    pub timestamp: Timestamp,
    /// **Expiration time** (Thời gian hết hạn)
    pub expires_at: Timestamp,
    /// **Priority level** (Mức độ ưu tiên)
    pub priority: WorkPriority,
}

/// **Work priority levels** (Mức độ ưu tiên công việc)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum WorkPriority {
    /// **Low priority** (Ưu tiên thấp)
    Low = 1,
    /// **Normal priority** (Ưu tiên bình thường)
    Normal = 2,
    /// **High priority** (Ưu tiên cao)
    High = 3,
    /// **Critical priority** (Ưu tiên khẩn cấp)
    Critical = 4,
}

/// **Mining result** (Kết quả đào)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningResult {
    /// **Job ID** (ID công việc)
    pub job_id: JobId,
    /// **Device ID** (ID thiết bị)
    pub device_id: GpuId,
    /// **Worker ID** (ID worker)
    pub worker_id: WorkerId,
    /// **Found nonces** (Nonce tìm được)
    pub nonces: Vec<Nonce>,
    /// **Hash count** (Số lượng hash)
    pub hash_count: u64,
    /// **Execution time** (Thời gian thực thi) in microseconds
    pub execution_time_us: u64,
    /// **Completion timestamp** (Thời điểm hoàn thành)
    pub timestamp: Timestamp,
    /// **Success status** (Trạng thái thành công)
    pub success: bool,
    /// **Error message** (Thông báo lỗi) if any
    pub error: Option<String>,
}

/// **Performance benchmark result** (Kết quả benchmark hiệu suất)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BenchmarkResult {
    /// **Device ID** (ID thiết bị)
    pub device_id: GpuId,
    /// **Algorithm name** (Tên thuật toán)
    pub algorithm: String,
    /// **Hash rate** (Tốc độ hash) achieved
    pub hashrate_mhs: f64,
    /// **Temperature** (Nhiệt độ) during benchmark
    pub temperature: Temperature,
    /// **Power consumption** (Tiêu thụ điện) during benchmark
    pub power_watts: PowerUsage,
    /// **Memory usage** (Sử dụng bộ nhớ) peak
    pub memory_usage_mb: u64,
    /// **Test duration** (Thời lượng test) in seconds
    pub duration_seconds: u64,
    /// **Benchmark timestamp** (Thời điểm benchmark)
    pub timestamp: Timestamp,
}

/// **Thermal alert information** (Thông tin cảnh báo nhiệt)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalAlert {
    /// **Device ID** (ID thiết bị)
    pub device_id: GpuId,
    /// **Alert level** (Mức độ cảnh báo)
    pub level: ThermalLevel,
    /// **Current temperature** (Nhiệt độ hiện tại)
    pub temperature: Temperature,
    /// **Threshold temperature** (Nhiệt độ ngưỡng)
    pub threshold: Temperature,
    /// **Alert message** (Thông báo cảnh báo)
    pub message: String,
    /// **Alert timestamp** (Thời điểm cảnh báo)
    pub timestamp: Timestamp,
}

/// **Thermal alert levels** (Mức độ cảnh báo nhiệt)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum ThermalLevel {
    /// **Normal temperature** (Nhiệt độ bình thường)
    Normal,
    /// **Warning level** (Mức cảnh báo)
    Warning,
    /// **Critical level** (Mức nguy hiểm)
    Critical,
    /// **Emergency shutdown** (Tắt khẩn cấp)
    Emergency,
}

impl fmt::Display for ThermalLevel {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ThermalLevel::Normal => write!(f, "Normal"),
            ThermalLevel::Warning => write!(f, "Warning"),
            ThermalLevel::Critical => write!(f, "Critical"),
            ThermalLevel::Emergency => write!(f, "Emergency"),
        }
    }
}

/// **Resource allocation info** (Thông tin phân bổ tài nguyên)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceAllocation {
    /// **Device ID** (ID thiết bị)
    pub device_id: GpuId,
    /// **Allocated memory** (Bộ nhớ đã phân bổ) in bytes
    pub allocated_memory: MemorySize,
    /// **Thread count** (Số lượng luồng)
    pub thread_count: u32,
    /// **Stream count** (Số lượng stream)
    pub stream_count: u32,
    /// **Priority level** (Mức ưu tiên)
    pub priority: i32,
    /// **Allocation timestamp** (Thời điểm phân bổ)
    pub timestamp: Timestamp,
}

/// **Network statistics** (Thống kê mạng)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkStats {
    /// **Bytes sent** (Byte đã gửi)
    pub bytes_sent: u64,
    /// **Bytes received** (Byte đã nhận)
    pub bytes_received: u64,
    /// **Packets sent** (Gói tin đã gửi)
    pub packets_sent: u64,
    /// **Packets received** (Gói tin đã nhận)
    pub packets_received: u64,
    /// **Connection errors** (Lỗi kết nối)
    pub connection_errors: u64,
    /// **Average latency** (Độ trễ trung bình) in milliseconds
    pub average_latency_ms: f64,
    /// **Statistics timestamp** (Thời điểm thống kê)
    pub timestamp: Timestamp,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gpu_status_display() {
        assert_eq!(GpuStatus::Available.to_string(), "Available");
        assert_eq!(GpuStatus::Mining.to_string(), "Mining");
        assert_eq!(GpuStatus::Error("Test error".to_string()).to_string(), "Error: Test error");
    }

    #[test]
    fn test_thermal_level_ordering() {
        assert!(ThermalLevel::Normal < ThermalLevel::Warning);
        assert!(ThermalLevel::Warning < ThermalLevel::Critical);
        assert!(ThermalLevel::Critical < ThermalLevel::Emergency);
    }

    #[test]
    fn test_work_priority_ordering() {
        assert!(WorkPriority::Low < WorkPriority::Normal);
        assert!(WorkPriority::Normal < WorkPriority::High);
        assert!(WorkPriority::High < WorkPriority::Critical);
    }

    #[test]
    fn test_device_metrics_serialization() {
        let metrics = DeviceMetrics {
            device_id: 0,
            hash_rate: 100.0,
            temperature: 65.0,
            power_usage: 200.0,
            memory_utilization: 0.8,
            gpu_utilization: 0.95,
            fan_speed: 0.75,
            timestamp: chrono::Utc::now(),
        };

        let serialized = serde_json::to_string(&metrics).unwrap();
        let deserialized: DeviceMetrics = serde_json::from_str(&serialized).unwrap();

        assert_eq!(metrics.device_id, deserialized.device_id);
        assert_eq!(metrics.hash_rate, deserialized.hash_rate);
    }
}