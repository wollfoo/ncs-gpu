use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::Path;

/// **[Coordinator Config]** (Cấu hình điều phối viên – system configuration)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoordinatorConfig {
    /// **[Server Config]** (Cấu hình máy chủ)
    pub server: ServerConfig,
    
    /// **[Scheduler Config]** (Cấu hình scheduler)
    pub scheduler: SchedulerConfig,
    
    /// **[Metrics Config]** (Cấu hình metrics)
    pub metrics: MetricsConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    /// **[Bind Address]** (Địa chỉ lắng nghe)
    pub bind_address: String,
    
    /// **[Max Connections]** (Số kết nối tối đa)
    pub max_connections: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchedulerConfig {
    /// **[Queue Capacity]** (Dung lượng hàng đợi – max pending tasks)
    pub queue_capacity: usize,
    
    /// **[Task Timeout]** (Thời gian chờ tác vụ – seconds)
    pub task_timeout_secs: u64,
    
    /// **[Retry Attempts]** (Số lần thử lại – max retries on failure)
    pub retry_attempts: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricsConfig {
    /// **[Enable Prometheus]** (Bật Prometheus)
    pub enable_prometheus: bool,
    
    /// **[Metrics Port]** (Cổng metrics)
    pub metrics_port: u16,
}

impl CoordinatorConfig {
    /// **[From File]** (Từ file – đọc config từ TOML file)
    pub fn from_file(path: &Path) -> Result<Self> {
        let content = std::fs::read_to_string(path)?;
        let config: CoordinatorConfig = toml::from_str(&content)?;
        Ok(config)
    }
}

impl Default for CoordinatorConfig {
    fn default() -> Self {
        Self {
            server: ServerConfig {
                bind_address: "0.0.0.0:50051".to_string(),
                max_connections: 1000,
            },
            scheduler: SchedulerConfig {
                queue_capacity: 10000,
                task_timeout_secs: 3600,
                retry_attempts: 3,
            },
            metrics: MetricsConfig {
                enable_prometheus: true,
                metrics_port: 9090,
            },
        }
    }
}
