//! Configuration management for OPUS-GPU
//!
//! Hierarchical configuration system supporting environment variables,
//! config files, and runtime overrides with validation.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::time::Duration;

use crate::common::error::{OpusError, OpusResult};

/// Main configuration structure for OPUS-GPU
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpusConfig {
    /// GPU mining configuration
    pub gpu: GpuConfig,
    /// Resource management configuration
    pub resources: ResourceConfig,
    /// Security configuration
    pub security: SecurityConfig,
    /// Cloaking/stealth configuration
    pub cloaking: CloakingConfig,
    /// Network configuration
    pub network: NetworkConfig,
    /// Monitoring and metrics configuration
    pub monitoring: MonitoringConfig,
    /// Logging configuration
    pub logging: LoggingConfig,
}

/// GPU mining configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuConfig {
    /// List of GPU device IDs to use (empty = auto-detect)
    pub device_ids: Vec<u32>,
    /// Memory allocation strategy
    pub memory_strategy: MemoryStrategy,
    /// Maximum memory usage per GPU (MB, 0 = unlimited)
    pub max_memory_mb: usize,
    /// Mining algorithm parameters
    pub algorithm: AlgorithmConfig,
    /// Thermal protection settings
    pub thermal: ThermalConfig,
    /// Performance tuning
    pub performance: PerformanceConfig,
}

/// Memory allocation strategy
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemoryStrategy {
    /// Conservative allocation - safe for shared systems
    Conservative,
    /// Balanced allocation - good performance/stability balance
    Balanced,
    /// Aggressive allocation - maximum performance
    Aggressive,
    /// Custom allocation with specific parameters
    Custom {
        chunk_size_mb: usize,
        pool_size_mb: usize,
        fragmentation_threshold: f32,
    },
}

/// Mining algorithm configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlgorithmConfig {
    /// Algorithm name (e.g., "ethash", "kawpow", "autolykos2")
    pub name: String,
    /// Algorithm-specific parameters
    pub parameters: std::collections::HashMap<String, serde_json::Value>,
    /// Intensity level (1-10)
    pub intensity: u8,
    /// Number of concurrent streams
    pub streams: u32,
}

/// Thermal protection configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalConfig {
    /// Enable thermal monitoring
    pub enabled: bool,
    /// Warning temperature threshold (°C)
    pub warning_temp: f32,
    /// Critical temperature threshold (°C)
    pub critical_temp: f32,
    /// Action to take when critical temperature is reached
    pub critical_action: ThermalAction,
    /// Thermal monitoring interval (seconds)
    pub monitor_interval: u64,
}

/// Actions to take on thermal events
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ThermalAction {
    /// Log warning only
    LogOnly,
    /// Reduce mining intensity
    ReduceIntensity,
    /// Pause mining temporarily
    PauseMining,
    /// Shutdown system
    Shutdown,
}

/// Performance tuning configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceConfig {
    /// Enable zero-copy memory transfers
    pub zero_copy: bool,
    /// Use memory pools for allocations
    pub memory_pools: bool,
    /// Enable CUDA graphs for optimization
    pub cuda_graphs: bool,
    /// Number of worker threads per GPU
    pub threads_per_gpu: u32,
    /// Enable SIMD optimizations
    pub simd_enabled: bool,
}

/// Resource management configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceConfig {
    /// CPU resource limits
    pub cpu: CpuConfig,
    /// Memory resource limits
    pub memory: MemoryConfig,
    /// Scheduling configuration
    pub scheduler: SchedulerConfig,
}

/// CPU resource configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CpuConfig {
    /// Maximum CPU usage percentage (0-100)
    pub max_usage_percent: f32,
    /// CPU affinity mask (empty = no affinity)
    pub affinity_mask: Vec<u32>,
    /// Enable CPU optimizations
    pub optimizations: bool,
}

/// Memory resource configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryConfig {
    /// Maximum system memory usage (MB, 0 = unlimited)
    pub max_system_mb: usize,
    /// Enable memory compression
    pub compression: bool,
    /// Memory allocator type
    pub allocator: MemoryAllocator,
}

/// Memory allocator types
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemoryAllocator {
    /// System default allocator
    System,
    /// High-performance mimalloc
    Mimalloc,
    /// Custom pool allocator
    Pool,
}

/// Task scheduler configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchedulerConfig {
    /// Scheduling algorithm
    pub algorithm: SchedulingAlgorithm,
    /// Task queue size
    pub queue_size: usize,
    /// Enable work stealing
    pub work_stealing: bool,
}

/// Scheduling algorithms
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SchedulingAlgorithm {
    /// Round-robin scheduling
    RoundRobin,
    /// Work-stealing scheduler
    WorkStealing,
    /// Priority-based scheduling
    Priority,
}

/// Security configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityConfig {
    /// Enable TLS for all communications
    pub tls_enabled: bool,
    /// TLS certificate configuration
    pub tls: TlsConfig,
    /// Authentication configuration
    pub auth: AuthConfig,
    /// Encryption settings
    pub encryption: EncryptionConfig,
}

/// TLS configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TlsConfig {
    /// Certificate file path
    pub cert_file: Option<PathBuf>,
    /// Private key file path
    pub key_file: Option<PathBuf>,
    /// CA certificate file path
    pub ca_file: Option<PathBuf>,
    /// Verify peer certificates
    pub verify_peer: bool,
}

/// Authentication configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthConfig {
    /// Authentication method
    pub method: AuthMethod,
    /// API key for authentication
    pub api_key: Option<String>,
    /// Token refresh interval (seconds)
    pub token_refresh_interval: u64,
}

/// Authentication methods
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthMethod {
    /// No authentication
    None,
    /// API key authentication
    ApiKey,
    /// JWT token authentication
    Jwt,
    /// Mutual TLS authentication
    MutualTls,
}

/// Encryption configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptionConfig {
    /// Encryption algorithm
    pub algorithm: EncryptionAlgorithm,
    /// Key size in bits
    pub key_size: u32,
    /// Enable encryption for data at rest
    pub encrypt_at_rest: bool,
}

/// Encryption algorithms
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EncryptionAlgorithm {
    /// AES-256-GCM
    Aes256Gcm,
    /// ChaCha20-Poly1305
    ChaCha20Poly1305,
    /// XChaCha20-Poly1305
    XChaCha20Poly1305,
}

/// Cloaking/stealth configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CloakingConfig {
    /// Enable stealth mode
    pub enabled: bool,
    /// Process cloaking settings
    pub process: ProcessCloakingConfig,
    /// Network cloaking settings
    pub network: NetworkCloakingConfig,
    /// Power consumption cloaking
    pub power: PowerCloakingConfig,
}

/// Process cloaking configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessCloakingConfig {
    /// Hide process from task managers
    pub hide_process: bool,
    /// Fake process name
    pub fake_name: Option<String>,
    /// CPU usage masking
    pub mask_cpu_usage: bool,
    /// Memory usage masking
    pub mask_memory_usage: bool,
}

/// Network cloaking configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkCloakingConfig {
    /// Use proxy for connections
    pub use_proxy: bool,
    /// Proxy configuration
    pub proxy_config: Option<ProxyConfig>,
    /// Traffic pattern obfuscation
    pub obfuscate_traffic: bool,
    /// Rate limiting to avoid detection
    pub rate_limiting: RateLimitConfig,
}

/// Proxy configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProxyConfig {
    /// Proxy type
    pub proxy_type: ProxyType,
    /// Proxy address
    pub address: String,
    /// Proxy port
    pub port: u16,
    /// Proxy authentication
    pub auth: Option<ProxyAuth>,
}

/// Proxy types
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ProxyType {
    Http,
    Https,
    Socks4,
    Socks5,
}

/// Proxy authentication
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProxyAuth {
    pub username: String,
    pub password: String,
}

/// Rate limiting configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimitConfig {
    /// Requests per second
    pub requests_per_second: f64,
    /// Burst size
    pub burst_size: u32,
}

/// Power consumption cloaking
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PowerCloakingConfig {
    /// Enable power consumption masking
    pub enabled: bool,
    /// Target power consumption (watts)
    pub target_power: f32,
    /// Power fluctuation range (±watts)
    pub fluctuation_range: f32,
}

/// Network configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkConfig {
    /// Mining pool configuration
    pub pools: Vec<PoolConfig>,
    /// Connection timeout
    #[serde(with = "humantime_serde")]
    pub connection_timeout: Duration,
    /// Keep-alive interval
    #[serde(with = "humantime_serde")]
    pub keepalive_interval: Duration,
    /// Retry configuration
    pub retry: RetryConfig,
}

/// Mining pool configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoolConfig {
    /// Pool name/identifier
    pub name: String,
    /// Pool URL
    pub url: String,
    /// Pool port
    pub port: u16,
    /// Worker name
    pub worker: String,
    /// Pool password
    pub password: Option<String>,
    /// Pool priority (lower = higher priority)
    pub priority: u32,
    /// Enable this pool
    pub enabled: bool,
}

/// Retry configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetryConfig {
    /// Maximum number of retries
    pub max_retries: u32,
    /// Base delay between retries
    #[serde(with = "humantime_serde")]
    pub base_delay: Duration,
    /// Maximum delay between retries
    #[serde(with = "humantime_serde")]
    pub max_delay: Duration,
    /// Exponential backoff multiplier
    pub backoff_multiplier: f64,
}

/// Monitoring and metrics configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MonitoringConfig {
    /// Enable metrics collection
    pub enabled: bool,
    /// Metrics collection interval
    #[serde(with = "humantime_serde")]
    pub interval: Duration,
    /// Prometheus metrics endpoint
    pub prometheus: PrometheusConfig,
    /// Health check configuration
    pub health_check: HealthCheckConfig,
}

/// Prometheus configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrometheusConfig {
    /// Enable Prometheus metrics
    pub enabled: bool,
    /// Metrics endpoint address
    pub address: String,
    /// Metrics endpoint port
    pub port: u16,
    /// Metrics endpoint path
    pub path: String,
}

/// Health check configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthCheckConfig {
    /// Enable health checks
    pub enabled: bool,
    /// Health check interval
    #[serde(with = "humantime_serde")]
    pub interval: Duration,
    /// Health check timeout
    #[serde(with = "humantime_serde")]
    pub timeout: Duration,
}

/// Logging configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoggingConfig {
    /// Log level
    pub level: LogLevel,
    /// Log format
    pub format: LogFormat,
    /// Log output configuration
    pub output: LogOutput,
    /// Enable log rotation
    pub rotation: LogRotation,
}

/// Log levels
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum LogLevel {
    Trace,
    Debug,
    Info,
    Warn,
    Error,
}

/// Log formats
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LogFormat {
    Plain,
    Json,
    Pretty,
}

/// Log output configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogOutput {
    /// Log to console
    pub console: bool,
    /// Log to file
    pub file: Option<LogFile>,
}

/// Log file configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogFile {
    /// Log file path
    pub path: PathBuf,
    /// Maximum file size (MB)
    pub max_size_mb: usize,
}

/// Log rotation configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogRotation {
    /// Enable rotation
    pub enabled: bool,
    /// Maximum number of log files to keep
    pub max_files: u32,
    /// Rotation interval
    #[serde(with = "humantime_serde")]
    pub interval: Duration,
}

impl Default for OpusConfig {
    fn default() -> Self {
        Self {
            gpu: GpuConfig::default(),
            resources: ResourceConfig::default(),
            security: SecurityConfig::default(),
            cloaking: CloakingConfig::default(),
            network: NetworkConfig::default(),
            monitoring: MonitoringConfig::default(),
            logging: LoggingConfig::default(),
        }
    }
}

impl Default for GpuConfig {
    fn default() -> Self {
        Self {
            device_ids: vec![], // Auto-detect all devices
            memory_strategy: MemoryStrategy::Balanced,
            max_memory_mb: 0, // Unlimited
            algorithm: AlgorithmConfig::default(),
            thermal: ThermalConfig::default(),
            performance: PerformanceConfig::default(),
        }
    }
}

impl Default for AlgorithmConfig {
    fn default() -> Self {
        Self {
            name: "ethash".to_string(),
            parameters: std::collections::HashMap::new(),
            intensity: 7,
            streams: 2,
        }
    }
}

impl Default for ThermalConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            warning_temp: 75.0,
            critical_temp: 85.0,
            critical_action: ThermalAction::ReduceIntensity,
            monitor_interval: 5,
        }
    }
}

impl Default for PerformanceConfig {
    fn default() -> Self {
        Self {
            zero_copy: true,
            memory_pools: true,
            cuda_graphs: true,
            threads_per_gpu: 2,
            simd_enabled: true,
        }
    }
}

impl Default for ResourceConfig {
    fn default() -> Self {
        Self {
            cpu: CpuConfig::default(),
            memory: MemoryConfig::default(),
            scheduler: SchedulerConfig::default(),
        }
    }
}

impl Default for CpuConfig {
    fn default() -> Self {
        Self {
            max_usage_percent: 80.0,
            affinity_mask: vec![],
            optimizations: true,
        }
    }
}

impl Default for MemoryConfig {
    fn default() -> Self {
        Self {
            max_system_mb: 0, // Unlimited
            compression: false,
            allocator: MemoryAllocator::Mimalloc,
        }
    }
}

impl Default for SchedulerConfig {
    fn default() -> Self {
        Self {
            algorithm: SchedulingAlgorithm::WorkStealing,
            queue_size: 1024,
            work_stealing: true,
        }
    }
}

impl Default for SecurityConfig {
    fn default() -> Self {
        Self {
            tls_enabled: true,
            tls: TlsConfig::default(),
            auth: AuthConfig::default(),
            encryption: EncryptionConfig::default(),
        }
    }
}

impl Default for TlsConfig {
    fn default() -> Self {
        Self {
            cert_file: None,
            key_file: None,
            ca_file: None,
            verify_peer: true,
        }
    }
}

impl Default for AuthConfig {
    fn default() -> Self {
        Self {
            method: AuthMethod::ApiKey,
            api_key: None,
            token_refresh_interval: 3600, // 1 hour
        }
    }
}

impl Default for EncryptionConfig {
    fn default() -> Self {
        Self {
            algorithm: EncryptionAlgorithm::Aes256Gcm,
            key_size: 256,
            encrypt_at_rest: false,
        }
    }
}

impl Default for CloakingConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            process: ProcessCloakingConfig::default(),
            network: NetworkCloakingConfig::default(),
            power: PowerCloakingConfig::default(),
        }
    }
}

impl Default for ProcessCloakingConfig {
    fn default() -> Self {
        Self {
            hide_process: false,
            fake_name: None,
            mask_cpu_usage: false,
            mask_memory_usage: false,
        }
    }
}

impl Default for NetworkCloakingConfig {
    fn default() -> Self {
        Self {
            use_proxy: false,
            proxy_config: None,
            obfuscate_traffic: false,
            rate_limiting: RateLimitConfig::default(),
        }
    }
}

impl Default for RateLimitConfig {
    fn default() -> Self {
        Self {
            requests_per_second: 10.0,
            burst_size: 50,
        }
    }
}

impl Default for PowerCloakingConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            target_power: 150.0,
            fluctuation_range: 10.0,
        }
    }
}

impl Default for NetworkConfig {
    fn default() -> Self {
        Self {
            pools: vec![],
            connection_timeout: Duration::from_secs(30),
            keepalive_interval: Duration::from_secs(60),
            retry: RetryConfig::default(),
        }
    }
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_retries: 5,
            base_delay: Duration::from_millis(500),
            max_delay: Duration::from_secs(60),
            backoff_multiplier: 2.0,
        }
    }
}

impl Default for MonitoringConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            interval: Duration::from_secs(5),
            prometheus: PrometheusConfig::default(),
            health_check: HealthCheckConfig::default(),
        }
    }
}

impl Default for PrometheusConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            address: "127.0.0.1".to_string(),
            port: 9090,
            path: "/metrics".to_string(),
        }
    }
}

impl Default for HealthCheckConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            interval: Duration::from_secs(30),
            timeout: Duration::from_secs(5),
        }
    }
}

impl Default for LoggingConfig {
    fn default() -> Self {
        Self {
            level: LogLevel::Info,
            format: LogFormat::Json,
            output: LogOutput {
                console: true,
                file: None,
            },
            rotation: LogRotation {
                enabled: false,
                max_files: 10,
                interval: Duration::from_secs(86400), // 24 hours
            },
        }
    }
}

/// Configuration loader and validator
pub struct ConfigLoader;

impl ConfigLoader {
    /// Load configuration from multiple sources with precedence:
    /// 1. Command line arguments
    /// 2. Environment variables
    /// 3. Configuration file
    /// 4. Default values
    pub fn load() -> OpusResult<OpusConfig> {
        let mut config = OpusConfig::default();

        // Try to load from config file
        if let Ok(file_config) = Self::load_from_file("opus-gpu.toml") {
            config = file_config;
        }

        // Override with environment variables
        Self::load_from_env(&mut config)?;

        // Validate configuration
        Self::validate(&config)?;

        Ok(config)
    }

    /// Load configuration from file
    pub fn load_from_file(path: impl AsRef<std::path::Path>) -> OpusResult<OpusConfig> {
        let content = std::fs::read_to_string(path).map_err(|e| OpusError::Io(e))?;
        let config: OpusConfig = toml::from_str(&content).map_err(|e| {
            OpusError::Config {
                message: format!("Failed to parse config file: {}", e),
            }
        })?;
        Ok(config)
    }

    /// Load configuration overrides from environment variables
    pub fn load_from_env(config: &mut OpusConfig) -> OpusResult<()> {
        // GPU configuration
        if let Ok(devices) = std::env::var("OPUS_GPU_DEVICES") {
            config.gpu.device_ids = devices
                .split(',')
                .filter_map(|s| s.trim().parse().ok())
                .collect();
        }

        if let Ok(memory_str) = std::env::var("OPUS_GPU_MAX_MEMORY") {
            if let Ok(memory) = memory_str.parse() {
                config.gpu.max_memory_mb = memory;
            }
        }

        // Security configuration
        if let Ok(api_key) = std::env::var("OPUS_API_KEY") {
            config.security.auth.api_key = Some(api_key);
        }

        // Monitoring configuration
        if let Ok(metrics_port) = std::env::var("OPUS_METRICS_PORT") {
            if let Ok(port) = metrics_port.parse() {
                config.monitoring.prometheus.port = port;
            }
        }

        Ok(())
    }

    /// Validate configuration
    pub fn validate(config: &OpusConfig) -> OpusResult<()> {
        // Validate GPU configuration
        if config.gpu.algorithm.intensity == 0 || config.gpu.algorithm.intensity > 10 {
            return Err(OpusError::Config {
                message: "GPU intensity must be between 1 and 10".to_string(),
            });
        }

        if config.gpu.thermal.warning_temp >= config.gpu.thermal.critical_temp {
            return Err(OpusError::Config {
                message: "Warning temperature must be less than critical temperature".to_string(),
            });
        }

        // Validate resource limits
        if config.resources.cpu.max_usage_percent > 100.0 {
            return Err(OpusError::Config {
                message: "CPU usage percentage cannot exceed 100%".to_string(),
            });
        }

        // Validate network configuration
        for pool in &config.network.pools {
            if pool.enabled && pool.url.is_empty() {
                return Err(OpusError::Config {
                    message: format!("Pool '{}' is enabled but has no URL", pool.name),
                });
            }
        }

        Ok(())
    }

    /// Save configuration to file
    pub fn save_to_file(config: &OpusConfig, path: impl AsRef<std::path::Path>) -> OpusResult<()> {
        let content = toml::to_string_pretty(config).map_err(|e| OpusError::Config {
            message: format!("Failed to serialize config: {}", e),
        })?;
        std::fs::write(path, content).map_err(OpusError::Io)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::NamedTempFile;

    #[test]
    fn test_default_config() {
        let config = OpusConfig::default();
        assert!(ConfigLoader::validate(&config).is_ok());
    }

    #[test]
    fn test_config_validation() {
        let mut config = OpusConfig::default();

        // Test invalid intensity
        config.gpu.algorithm.intensity = 11;
        assert!(ConfigLoader::validate(&config).is_err());

        // Reset and test thermal validation
        config.gpu.algorithm.intensity = 7;
        config.gpu.thermal.warning_temp = 90.0;
        config.gpu.thermal.critical_temp = 85.0;
        assert!(ConfigLoader::validate(&config).is_err());
    }

    #[test]
    fn test_config_file_operations() {
        let config = OpusConfig::default();
        let temp_file = NamedTempFile::new().unwrap();

        // Test save
        assert!(ConfigLoader::save_to_file(&config, temp_file.path()).is_ok());

        // Test load
        let loaded_config = ConfigLoader::load_from_file(temp_file.path()).unwrap();
        assert_eq!(config.gpu.algorithm.intensity, loaded_config.gpu.algorithm.intensity);
    }
}