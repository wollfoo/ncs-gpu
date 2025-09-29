//! Advanced Configuration Management System for OPUS-GPU
//!
//! This module provides comprehensive configuration management with:
//! - Multi-format support (TOML, YAML, JSON)
//! - Hot reload with file watching
//! - Security features (encryption, secret management)
//! - Comprehensive validation
//! - Audit logging
//! - Environment variable override
//! - Configuration access control

use anyhow::{Context, Result};
use figment::{
    providers::{Env, Format, Json, Toml, Yaml},
    Figment,
};
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tokio::fs;
use validator::Validate;

// Re-export public modules
pub mod manager;
pub mod watcher;
pub mod security;
pub mod validation;
pub mod audit;
pub mod formats;
pub mod errors;

pub use manager::{ConfigManager, ConfigSource};
pub use watcher::{ConfigWatcher, WatchEvent};
pub use security::{SecretManager, EncryptionConfig};
pub use validation::{ConfigValidator, ValidationRule};
pub use audit::{AuditLogger, ConfigEvent};
pub use formats::{ConfigFormat, FormatDetector};
pub use errors::{ConfigError, ConfigResult};

/// Main application configuration with comprehensive validation
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct AppConfig {
    pub mining: MiningConfig,
    pub pool: PoolConfig,
    pub wallet: WalletConfig,
    pub monitoring: MonitoringConfig,
    pub storage: StorageConfig,
    pub api: ApiConfig,
    pub plugins: PluginConfig,
    pub bus: BusConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct MiningConfig {
    #[validate(length(min = 1, message = "Algorithm cannot be empty"))]
    pub algorithm: String,
    #[validate(range(min = 1, max = 1024, message = "max_workers must be between 1 and 1024"))]
    pub max_workers: usize,
    #[validate(range(min = 1, message = "difficulty must be greater than 0"))]
    pub difficulty: u64,
    #[validate(range(min = 1, max = 3600, message = "work_timeout_secs must be between 1 and 3600"))]
    pub work_timeout_secs: u64,
    #[validate(range(min = 1, max = 300, message = "stats_interval_secs must be between 1 and 300"))]
    pub stats_interval_secs: u64,
    #[validate(length(min = 1, message = "At least one GPU device must be specified"))]
    pub gpu_devices: Vec<usize>,
    #[validate(range(min = 1, max = 64, message = "worker_threads must be between 1 and 64"))]
    pub worker_threads: usize,
    #[validate(range(min = 1, message = "batch_size must be greater than 0"))]
    pub batch_size: usize,
    #[validate(range(min = 1048576, message = "memory_size must be at least 1MB"))]
    pub memory_size: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct PoolConfig {
    #[validate(length(min = 1, message = "At least one pool URL must be specified"))]
    #[validate(custom = "validate_pool_urls")]
    pub urls: Vec<String>,
    #[validate(length(min = 1, message = "Username cannot be empty"))]
    pub username: String,
    #[validate(length(min = 1, message = "Password cannot be empty"))]
    pub password: String,
    #[validate(range(min = 1, max = 10, message = "retry_attempts must be between 1 and 10"))]
    pub retry_attempts: u32,
    #[validate(range(min = 1, max = 300, message = "retry_delay_secs must be between 1 and 300"))]
    pub retry_delay_secs: u64,
    #[validate(range(min = 1, max = 120, message = "connection_timeout_secs must be between 1 and 120"))]
    pub connection_timeout_secs: u64,
    #[validate(range(min = 1, max = 300, message = "keepalive_interval_secs must be between 1 and 300"))]
    pub keepalive_interval_secs: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct WalletConfig {
    #[validate(custom = "validate_wallet_address")]
    pub address: Option<String>,
    #[validate(custom = "validate_file_path")]
    pub private_key_file: Option<String>,
    #[validate(length(min = 1, message = "keystore_dir cannot be empty"))]
    pub keystore_dir: String,
    #[validate(length(min = 1, message = "backup_dir cannot be empty"))]
    pub backup_dir: String,
    pub encryption_enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct MonitoringConfig {
    pub enabled: bool,
    #[validate(range(min = 1024, max = 65535, message = "metrics_port must be between 1024 and 65535"))]
    pub metrics_port: u16,
    #[validate(range(min = 1, max = 300, message = "stats_interval_secs must be between 1 and 300"))]
    pub stats_interval_secs: u64,
    #[validate(range(min = 0.0, max = 100.0, message = "temperature_threshold must be between 0 and 100"))]
    pub temperature_threshold: f32,
    #[validate(range(min = 0.0, max = 100.0, message = "memory_threshold must be between 0 and 100"))]
    pub memory_threshold: f32,
    pub enable_alerts: bool,
    #[validate(url(message = "Invalid webhook URL"))]
    pub alert_webhook_url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct StorageConfig {
    #[validate(length(min = 1, message = "data_dir cannot be empty"))]
    pub data_dir: String,
    #[validate(length(min = 1, message = "database_url cannot be empty"))]
    pub database_url: String,
    #[validate(range(min = 1, max = 1000, message = "max_connections must be between 1 and 1000"))]
    pub max_connections: u32,
    pub backup_enabled: bool,
    #[validate(range(min = 1, message = "backup_interval_hours must be at least 1"))]
    pub backup_interval_hours: u64,
    #[validate(range(min = 1, message = "retention_days must be at least 1"))]
    pub retention_days: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiConfig {
    pub rest: RestApiConfig,
    pub websocket: WebSocketConfig,
    pub grpc: GrpcConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct RestApiConfig {
    #[validate(length(min = 1, message = "host cannot be empty"))]
    pub host: String,
    #[validate(range(min = 1024, max = 65535, message = "port must be between 1024 and 65535"))]
    pub port: u16,
    pub cors_enabled: bool,
    pub cors_origins: Vec<String>,
    #[validate(range(min = 1, message = "rate_limit must be at least 1"))]
    pub rate_limit: u32,
    #[validate(range(min = 1, max = 300, message = "request_timeout_secs must be between 1 and 300"))]
    pub request_timeout_secs: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct WebSocketConfig {
    #[validate(length(min = 1, message = "host cannot be empty"))]
    pub host: String,
    #[validate(range(min = 1024, max = 65535, message = "port must be between 1024 and 65535"))]
    pub port: u16,
    #[validate(range(min = 1, message = "max_connections must be at least 1"))]
    pub max_connections: usize,
    #[validate(range(min = 1, message = "message_buffer_size must be at least 1"))]
    pub message_buffer_size: usize,
    #[validate(range(min = 1, max = 300, message = "heartbeat_interval_secs must be between 1 and 300"))]
    pub heartbeat_interval_secs: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct GrpcConfig {
    #[validate(length(min = 1, message = "host cannot be empty"))]
    pub host: String,
    #[validate(range(min = 1024, max = 65535, message = "port must be between 1024 and 65535"))]
    pub port: u16,
    #[validate(range(min = 1024, message = "max_message_size must be at least 1024"))]
    pub max_message_size: usize,
    #[validate(range(min = 1, max = 300, message = "keepalive_interval_secs must be between 1 and 300"))]
    pub keepalive_interval_secs: u64,
    #[validate(range(min = 1, max = 60, message = "keepalive_timeout_secs must be between 1 and 60"))]
    pub keepalive_timeout_secs: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct PluginConfig {
    pub disabled: bool,
    #[validate(length(min = 1, message = "plugin_dir cannot be empty"))]
    pub plugin_dir: String,
    #[validate(range(min = 1, max = 1000, message = "max_plugins must be between 1 and 1000"))]
    pub max_plugins: usize,
    #[validate(range(min = 1, max = 300, message = "load_timeout_secs must be between 1 and 300"))]
    pub load_timeout_secs: u64,
    pub whitelist: Vec<String>,
    pub blacklist: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct BusConfig {
    #[validate(range(min = 1, message = "buffer_size must be at least 1"))]
    pub buffer_size: usize,
    #[validate(range(min = 1, message = "max_subscribers must be at least 1"))]
    pub max_subscribers: usize,
    #[validate(range(min = 1, max = 60, message = "message_timeout_secs must be between 1 and 60"))]
    pub message_timeout_secs: u64,
    pub enable_persistence: bool,
    #[validate(length(min = 1, message = "persistence_file cannot be empty"))]
    pub persistence_file: String,
}

impl AppConfig {
    /// Load configuration from file with format detection and environment variables
    pub async fn load(config_path: &str) -> Result<Self> {
        let format = FormatDetector::detect_from_path(config_path)
            .context("Failed to detect configuration format")?;

        let figment = match format {
            ConfigFormat::Toml => Figment::new().merge(Toml::file(config_path)),
            ConfigFormat::Yaml => Figment::new().merge(Yaml::file(config_path)),
            ConfigFormat::Json => Figment::new().merge(Json::file(config_path)),
        };

        let config: AppConfig = figment
            .merge(Env::prefixed("OPUS_GPU_"))
            .extract()
            .context("Failed to extract configuration")?;

        // Comprehensive validation
        config.validate().context("Configuration validation failed")?;
        config.validate_business_rules().context("Business rule validation failed")?;

        Ok(config)
    }

    /// Load configuration with custom source
    pub async fn load_from_source(source: ConfigSource) -> Result<Self> {
        let config = ConfigManager::load_from_source(source).await?;
        config.validate().context("Configuration validation failed")?;
        config.validate_business_rules().context("Business rule validation failed")?;
        Ok(config)
    }

    /// Validate business rules and constraints
    pub fn validate_business_rules(&self) -> Result<()> {
        // Check for port conflicts
        let ports = vec![
            self.api.rest.port,
            self.api.websocket.port,
            self.api.grpc.port,
            self.monitoring.metrics_port,
        ];

        for (i, &port1) in ports.iter().enumerate() {
            for &port2 in &ports[i + 1..] {
                if port1 == port2 {
                    return Err(anyhow::anyhow!(
                        "Port conflict detected: port {} is used multiple times", port1
                    ));
                }
            }
        }

        // Validate GPU device indices
        for &device_id in &self.mining.gpu_devices {
            if device_id >= 32 {
                return Err(anyhow::anyhow!(
                    "GPU device ID {} is out of reasonable range (0-31)", device_id
                ));
            }
        }

        // Check memory requirements
        let total_memory = self.mining.memory_size * self.mining.gpu_devices.len();
        if total_memory > 32 * 1024 * 1024 * 1024 { // 32GB
            return Err(anyhow::anyhow!(
                "Total memory requirement ({} GB) exceeds reasonable limit (32 GB)",
                total_memory / (1024 * 1024 * 1024)
            ));
        }

        // Validate directories exist or can be created
        self.validate_directories()?;

        Ok(())
    }

    /// Validate directory paths
    fn validate_directories(&self) -> Result<()> {
        let dirs = vec![
            &self.wallet.keystore_dir,
            &self.wallet.backup_dir,
            &self.storage.data_dir,
            &self.plugins.plugin_dir,
        ];

        for dir in dirs {
            if dir.is_empty() {
                return Err(anyhow::anyhow!("Directory path cannot be empty"));
            }

            // Check if path is absolute or relative
            let path = std::path::Path::new(dir);
            if path.is_absolute() && !path.exists() {
                // Try to create the directory
                if let Err(e) = std::fs::create_dir_all(path) {
                    return Err(anyhow::anyhow!(
                        "Cannot create directory {}: {}", dir, e
                    ));
                }
            }
        }

        Ok(())
    }

    /// Save configuration to file with format detection
    pub async fn save(&self, config_path: &str) -> Result<()> {
        let format = FormatDetector::detect_from_path(config_path)
            .context("Failed to detect configuration format")?;

        let config_str = match format {
            ConfigFormat::Toml => toml::to_string_pretty(self)?,
            ConfigFormat::Yaml => serde_yaml::to_string(self)?,
            ConfigFormat::Json => serde_json::to_string_pretty(self)?,
        };

        // Backup existing config before overwriting
        if std::path::Path::new(config_path).exists() {
            let backup_path = format!("{}.backup.{}", config_path, chrono::Utc::now().format("%Y%m%d_%H%M%S"));
            if let Err(e) = tokio::fs::copy(config_path, &backup_path).await {
                tracing::warn!("Failed to create backup at {}: {}", backup_path, e);
            }
        }

        fs::write(config_path, config_str).await?;
        Ok(())
    }

    /// Get configuration as encrypted bytes for secure storage
    pub async fn to_encrypted_bytes(&self, encryption_key: &[u8]) -> Result<Vec<u8>> {
        let json_data = serde_json::to_vec(self)?;
        security::encrypt_data(&json_data, encryption_key).await
    }

    /// Load configuration from encrypted bytes
    pub async fn from_encrypted_bytes(encrypted_data: &[u8], encryption_key: &[u8]) -> Result<Self> {
        let decrypted_data = security::decrypt_data(encrypted_data, encryption_key).await?;
        let config: AppConfig = serde_json::from_slice(&decrypted_data)?;

        config.validate().context("Configuration validation failed")?;
        config.validate_business_rules().context("Business rule validation failed")?;

        Ok(config)
    }

    /// Create default configuration with secure defaults
    pub fn default() -> Self {
        Self {
            mining: MiningConfig {
                algorithm: "SHA256".to_string(),
                max_workers: std::cmp::min(num_cpus::get(), 16),
                difficulty: 1000000,
                work_timeout_secs: 30,
                stats_interval_secs: 5,
                gpu_devices: vec![0],
                worker_threads: 1,
                batch_size: 1000,
                memory_size: 1024 * 1024 * 512, // 512MB
            },
            pool: PoolConfig {
                urls: vec!["stratum+tcp://pool.example.com:4444".to_string()],
                username: "your_wallet_address".to_string(),
                password: "worker1".to_string(),
                retry_attempts: 3,
                retry_delay_secs: 5,
                connection_timeout_secs: 10,
                keepalive_interval_secs: 30,
            },
            wallet: WalletConfig {
                address: None,
                private_key_file: None,
                keystore_dir: "./keystore".to_string(),
                backup_dir: "./backup".to_string(),
                encryption_enabled: true,
            },
            monitoring: MonitoringConfig {
                enabled: true,
                metrics_port: 9090,
                stats_interval_secs: 10,
                temperature_threshold: 80.0,
                memory_threshold: 90.0,
                enable_alerts: false,
                alert_webhook_url: None,
            },
            storage: StorageConfig {
                data_dir: "./data".to_string(),
                database_url: "sqlite://opus-gpu.db".to_string(),
                max_connections: 10,
                backup_enabled: true,
                backup_interval_hours: 24,
                retention_days: 30,
            },
            api: ApiConfig {
                rest: RestApiConfig {
                    host: "127.0.0.1".to_string(),
                    port: 8080,
                    cors_enabled: true,
                    cors_origins: vec!["*".to_string()],
                    rate_limit: 100,
                    request_timeout_secs: 30,
                },
                websocket: WebSocketConfig {
                    host: "127.0.0.1".to_string(),
                    port: 8081,
                    max_connections: 1000,
                    message_buffer_size: 1000,
                    heartbeat_interval_secs: 30,
                },
                grpc: GrpcConfig {
                    host: "127.0.0.1".to_string(),
                    port: 8082,
                    max_message_size: 1024 * 1024 * 4, // 4MB
                    keepalive_interval_secs: 30,
                    keepalive_timeout_secs: 5,
                },
            },
            plugins: PluginConfig {
                disabled: false,
                plugin_dir: "./plugins".to_string(),
                max_plugins: 50,
                load_timeout_secs: 30,
                whitelist: vec![],
                blacklist: vec![],
            },
            bus: BusConfig {
                buffer_size: 1000,
                max_subscribers: 100,
                message_timeout_secs: 5,
                enable_persistence: false,
                persistence_file: "./bus_state.json".to_string(),
            },
        }
    }
}

}

// Custom validation functions
fn validate_pool_urls(urls: &[String]) -> Result<(), validator::ValidationError> {
    for url in urls {
        if !url.starts_with("stratum+tcp://") && !url.starts_with("stratum+ssl://") {
            return Err(validator::ValidationError::new("invalid_pool_url"));
        }
    }
    Ok(())
}

fn validate_wallet_address(address: &Option<String>) -> Result<(), validator::ValidationError> {
    if let Some(addr) = address {
        if addr.len() < 26 || addr.len() > 62 {
            return Err(validator::ValidationError::new("invalid_wallet_address"));
        }
        // Basic format validation - should start with common prefixes
        if !addr.starts_with('1') && !addr.starts_with('3') && !addr.starts_with("bc1") {
            return Err(validator::ValidationError::new("invalid_wallet_address_format"));
        }
    }
    Ok(())
}

fn validate_file_path(path: &Option<String>) -> Result<(), validator::ValidationError> {
    if let Some(p) = path {
        if p.is_empty() {
            return Err(validator::ValidationError::new("empty_file_path"));
        }
        // Prevent directory traversal attempts
        if p.contains("..") {
            return Err(validator::ValidationError::new("invalid_file_path"));
        }
    }
    Ok(())
}