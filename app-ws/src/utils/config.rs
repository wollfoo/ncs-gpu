//! **Configuration Management** (quản lý cấu hình – điều khiển thiết lập)

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::fs;

/// **Main Configuration** (cấu hình chính – thiết lập tổng thể)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    /// GPU configuration
    pub gpu: GpuConfig,
    /// Mining configuration
    pub mining: MiningConfig,
    /// Scheduler configuration
    pub scheduler: SchedulerConfig,
    /// Metrics configuration
    pub metrics: MetricsConfig,
    /// Security configuration
    pub security: SecurityConfig,
    /// Feature flags
    pub features: Features,
}

/// **GPU Configuration** (cấu hình GPU – thiết lập card đồ họa)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuConfig {
    /// Maximum number of GPUs to use
    pub max_gpus: Option<usize>,
    /// GPU indices to use (empty = all)
    pub gpu_indices: Vec<u32>,
    /// Maximum GPU utilization percentage
    pub max_utilization: u32,
    /// Maximum GPU temperature in Celsius
    pub max_temperature: u32,
    /// Memory allocation percentage
    pub memory_allocation: f32,
    /// Enable GPU metrics collection
    pub enable_metrics: bool,
}

/// **Mining Configuration** (cấu hình khai thác – thiết lập đào coin)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningConfig {
    /// Mining algorithm
    pub algorithm: String,
    /// Mining pool address
    pub pool_address: String,
    /// Wallet address
    pub wallet_address: String,
    /// Worker name
    pub worker_name: String,
    /// Enable TLS
    pub enable_tls: bool,
    /// Mining intensity (0-100)
    pub intensity: u32,
    /// Auto-tune parameters
    pub auto_tune: bool,
    /// Custom parameters
    pub custom_params: Vec<String>,
}

/// **Scheduler Configuration** (cấu hình bộ lập lịch – thiết lập điều phối)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchedulerConfig {
    /// Number of worker threads
    pub worker_threads: Option<usize>,
    /// Task queue size
    pub queue_size: usize,
    /// Enable work stealing
    pub work_stealing: bool,
    /// Task timeout in seconds
    pub task_timeout: u64,
    /// Retry failed tasks
    pub retry_failed: bool,
    /// Maximum retry attempts
    pub max_retries: u32,
}

/// **Metrics Configuration** (cấu hình metrics – thiết lập giám sát)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricsConfig {
    /// Enable metrics collection
    pub enabled: bool,
    /// Metrics server port
    pub port: u16,
    /// Metrics collection interval in seconds
    pub interval: u64,
    /// Enable detailed metrics
    pub detailed: bool,
    /// Export format
    pub export_format: String,
}

/// **Security Configuration** (cấu hình bảo mật – thiết lập an ninh)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityConfig {
    /// Enable encryption
    pub enable_encryption: bool,
    /// Encryption algorithm
    pub encryption_algorithm: String,
    /// Enable authentication
    pub enable_auth: bool,
    /// API key
    pub api_key: Option<String>,
    /// Allowed IPs
    pub allowed_ips: Vec<String>,
    /// Enable audit logging
    pub audit_logging: bool,
}

/// **Feature Flags** (cờ tính năng – bật/tắt chức năng)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Features {
    /// Enable cloaking/stealth mode
    pub cloaking: bool,
    /// Enable auto-optimization
    pub auto_optimize: bool,
    /// Enable debug mode
    pub debug_mode: bool,
    /// Enable experimental features
    pub experimental: bool,
}

impl Config {
    /// **Load configuration from file** (tải cấu hình từ file – đọc thiết lập)
    pub fn load(path: &Path) -> Result<Self> {
        let content = fs::read_to_string(path)
            .with_context(|| format!("Failed to read config file: {}", path.display()))?;

        let config: Config = toml::from_str(&content)
            .with_context(|| format!("Failed to parse config file: {}", path.display()))?;

        config.validate()?;

        Ok(config)
    }

    /// **Save configuration to file** (lưu cấu hình vào file – ghi thiết lập)
    pub fn save(&self, path: &Path) -> Result<()> {
        let content = toml::to_string_pretty(self)
            .context("Failed to serialize config")?;

        fs::write(path, content)
            .with_context(|| format!("Failed to write config file: {}", path.display()))?;

        Ok(())
    }

    /// **Validate configuration** (kiểm tra cấu hình – xác minh thiết lập)
    pub fn validate(&self) -> Result<()> {
        // Validate GPU config
        if self.gpu.max_utilization > 100 {
            return Err(anyhow::anyhow!("GPU max_utilization cannot exceed 100"));
        }

        if self.gpu.max_temperature > 100 {
            return Err(anyhow::anyhow!("GPU max_temperature seems too high"));
        }

        if self.gpu.memory_allocation > 1.0 {
            return Err(anyhow::anyhow!("GPU memory_allocation cannot exceed 1.0"));
        }

        // Validate mining config
        if self.mining.pool_address.is_empty() {
            return Err(anyhow::anyhow!("Mining pool_address cannot be empty"));
        }

        if self.mining.wallet_address.is_empty() {
            return Err(anyhow::anyhow!("Mining wallet_address cannot be empty"));
        }

        if self.mining.intensity > 100 {
            return Err(anyhow::anyhow!("Mining intensity cannot exceed 100"));
        }

        // Validate scheduler config
        if self.scheduler.queue_size == 0 {
            return Err(anyhow::anyhow!("Scheduler queue_size must be greater than 0"));
        }

        Ok(())
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            gpu: GpuConfig {
                max_gpus: None,
                gpu_indices: vec![],
                max_utilization: 90,
                max_temperature: 85,
                memory_allocation: 0.9,
                enable_metrics: true,
            },
            mining: MiningConfig {
                algorithm: "kawpow".to_string(),
                pool_address: String::new(),
                wallet_address: String::new(),
                worker_name: "opus-gpu".to_string(),
                enable_tls: true,
                intensity: 80,
                auto_tune: true,
                custom_params: vec![],
            },
            scheduler: SchedulerConfig {
                worker_threads: None,
                queue_size: 1000,
                work_stealing: true,
                task_timeout: 300,
                retry_failed: true,
                max_retries: 3,
            },
            metrics: MetricsConfig {
                enabled: true,
                port: 9090,
                interval: 10,
                detailed: false,
                export_format: "prometheus".to_string(),
            },
            security: SecurityConfig {
                enable_encryption: true,
                encryption_algorithm: "aes-256-gcm".to_string(),
                enable_auth: false,
                api_key: None,
                allowed_ips: vec![],
                audit_logging: true,
            },
            features: Features {
                cloaking: false,
                auto_optimize: true,
                debug_mode: false,
                experimental: false,
            },
        }
    }
}