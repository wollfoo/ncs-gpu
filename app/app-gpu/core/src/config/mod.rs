//! Configuration Management Module
//! 
//! YAML/TOML configuration với hot-reload support

use std::path::{Path, PathBuf};
use std::sync::Arc;
use anyhow::{Result, Context};
use serde::{Deserialize, Serialize};
use notify::{Watcher, RecursiveMode, Event, Config as NotifyConfig};
use tokio::sync::{RwLock, broadcast};
use tracing::{info, debug, warn, error};

/// Main configuration structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    /// Runtime configuration
    pub runtime: RuntimeConfig,
    
    /// Plugin configuration  
    pub plugin: PluginConfig,
    
    /// IPC configuration
    pub ipc: IpcConfig,
    
    /// GPU configuration
    pub gpu: GpuConfig,
    
    /// Monitoring configuration
    pub monitoring: MonitoringConfig,
}

/// Runtime configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuntimeConfig {
    /// Number of worker threads
    pub workers: usize,
    
    /// Maximum memory usage in MB
    pub max_memory_mb: usize,
    
    /// Event queue size
    pub event_queue_size: usize,
    
    /// Enable debug mode
    pub debug: bool,
}

/// Plugin configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginConfig {
    /// Plugin directory path
    pub plugin_dir: PathBuf,
    
    /// Auto-load plugins on startup
    pub auto_load: bool,
    
    /// Enable hot-reload
    pub hot_reload: bool,
}

/// IPC configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IpcConfig {
    /// Shared memory size in MB
    pub shared_memory_size_mb: usize,
    
    /// Number of shared memory segments
    pub num_segments: usize,
    
    /// Use bounded queue
    pub bounded_queue: bool,
    
    /// Queue size if bounded
    pub queue_size: usize,
}

/// GPU configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuConfig {
    /// GPU device indices to use
    pub devices: Vec<u32>,
    
    /// Memory fraction to allocate (0.0 - 1.0)
    pub memory_fraction: f32,
    
    /// Power limit in watts
    pub power_limit: Option<u32>,
    
    /// Temperature limit in Celsius
    pub temperature_limit: Option<u32>,
}

/// Monitoring configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MonitoringConfig {
    /// Enable Prometheus metrics
    pub prometheus_enabled: bool,
    
    /// Prometheus port
    pub prometheus_port: u16,
    
    /// Log level
    pub log_level: String,
    
    /// Metrics collection interval in seconds
    pub metrics_interval_secs: u64,
    
    /// Enable tracing
    pub tracing_enabled: bool,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            runtime: RuntimeConfig {
                workers: 4,
                max_memory_mb: 500,
                event_queue_size: 10000,
                debug: false,
            },
            plugin: PluginConfig {
                plugin_dir: PathBuf::from("./plugins"),
                auto_load: true,
                hot_reload: true,
            },
            ipc: IpcConfig {
                shared_memory_size_mb: 100,
                num_segments: 4,
                bounded_queue: true,
                queue_size: 1000,
            },
            gpu: GpuConfig {
                devices: vec![0],
                memory_fraction: 0.9,
                power_limit: None,
                temperature_limit: Some(80),
            },
            monitoring: MonitoringConfig {
                prometheus_enabled: true,
                prometheus_port: 9090,
                log_level: "info".to_string(),
                metrics_interval_secs: 30,
                tracing_enabled: true,
            },
        }
    }
}

impl Config {
    /// Load configuration từ file
    pub fn load() -> Result<Self> {
        // Try load từ environment variable
        let config_path = std::env::var("OPUS_CONFIG_PATH")
            .unwrap_or_else(|_| "config.yaml".to_string());
        
        let path = Path::new(&config_path);
        
        if !path.exists() {
            warn!("Config file not found at {:?}, using defaults", path);
            return Ok(Self::default());
        }
        
        info!("Loading configuration from {:?}", path);
        
        // Detect format từ extension
        let config = match path.extension().and_then(|s| s.to_str()) {
            Some("yaml") | Some("yml") => Self::load_yaml(path)?,
            Some("toml") => Self::load_toml(path)?,
            _ => {
                // Try YAML first, then TOML
                Self::load_yaml(path)
                    .or_else(|_| Self::load_toml(path))
                    .context("Failed to parse config as YAML or TOML")?
            }
        };
        
        // Override với environment variables
        let config = Self::apply_env_overrides(config)?;
        
        // Validate configuration
        config.validate()?;
        
        Ok(config)
    }
    
    /// Load YAML configuration
    fn load_yaml(path: &Path) -> Result<Self> {
        let content = std::fs::read_to_string(path)?;
        let config: Self = serde_yaml::from_str(&content)?;
        Ok(config)
    }
    
    /// Load TOML configuration
    fn load_toml(path: &Path) -> Result<Self> {
        let content = std::fs::read_to_string(path)?;
        let config: Self = toml::from_str(&content)?;
        Ok(config)
    }
    
    /// Apply environment variable overrides
    fn apply_env_overrides(mut self) -> Result<Self> {
        // Runtime overrides
        if let Ok(workers) = std::env::var("OPUS_WORKERS") {
            self.runtime.workers = workers.parse()?;
        }
        
        if let Ok(max_memory) = std::env::var("OPUS_MAX_MEMORY_MB") {
            self.runtime.max_memory_mb = max_memory.parse()?;
        }
        
        if let Ok(debug) = std::env::var("OPUS_DEBUG") {
            self.runtime.debug = debug.parse()?;
        }
        
        // Plugin overrides
        if let Ok(plugin_dir) = std::env::var("OPUS_PLUGIN_DIR") {
            self.plugin.plugin_dir = PathBuf::from(plugin_dir);
        }
        
        // GPU overrides
        if let Ok(devices) = std::env::var("CUDA_VISIBLE_DEVICES") {
            self.gpu.devices = devices
                .split(',')
                .filter_map(|s| s.parse().ok())
                .collect();
        }
        
        // Monitoring overrides
        if let Ok(log_level) = std::env::var("RUST_LOG") {
            self.monitoring.log_level = log_level;
        }
        
        Ok(self)
    }
    
    /// Validate configuration
    pub fn validate(&self) -> Result<()> {
        // Validate runtime
        if self.runtime.workers == 0 {
            return Err(anyhow::anyhow!("Workers must be > 0"));
        }
        
        if self.runtime.max_memory_mb < 100 {
            return Err(anyhow::anyhow!("Max memory must be >= 100 MB"));
        }
        
        // Validate GPU
        if self.gpu.devices.is_empty() {
            return Err(anyhow::anyhow!("At least one GPU device required"));
        }
        
        if self.gpu.memory_fraction <= 0.0 || self.gpu.memory_fraction > 1.0 {
            return Err(anyhow::anyhow!("Memory fraction must be between 0.0 and 1.0"));
        }
        
        // Validate IPC
        if self.ipc.shared_memory_size_mb < 10 {
            return Err(anyhow::anyhow!("Shared memory must be >= 10 MB"));
        }
        
        if self.ipc.num_segments == 0 {
            return Err(anyhow::anyhow!("Number of segments must be > 0"));
        }
        
        Ok(())
    }
    
    /// Save configuration to file
    pub fn save(&self, path: &Path) -> Result<()> {
        let content = match path.extension().and_then(|s| s.to_str()) {
            Some("yaml") | Some("yml") => serde_yaml::to_string(self)?,
            Some("toml") => toml::to_string_pretty(self)?,
            _ => serde_yaml::to_string(self)?, // Default to YAML
        };
        
        std::fs::write(path, content)?;
        info!("Configuration saved to {:?}", path);
        
        Ok(())
    }
}

/// Configuration watcher cho hot-reload
pub struct ConfigWatcher {
    config: Arc<RwLock<Config>>,
    update_tx: broadcast::Sender<Config>,
    _watcher: notify::RecommendedWatcher,
}

impl ConfigWatcher {
    /// Create new config watcher
    pub fn new(config_path: PathBuf) -> Result<Self> {
        let config = Arc::new(RwLock::new(Config::load()?));
        let (update_tx, _) = broadcast::channel(10);
        
        let config_clone = config.clone();
        let update_tx_clone = update_tx.clone();
        
        // Setup file watcher
        let mut watcher = notify::recommended_watcher(
            move |res: Result<Event, notify::Error>| {
                match res {
                    Ok(event) => {
                        if event.kind.is_modify() {
                            info!("Config file changed, reloading...");
                            
                            // Reload configuration
                            match Config::load() {
                                Ok(new_config) => {
                                    // Validate new config
                                    if let Err(e) = new_config.validate() {
                                        error!("Invalid configuration: {}", e);
                                        return;
                                    }
                                    
                                    // Update config
                                    let mut config = config_clone.blocking_write();
                                    *config = new_config.clone();
                                    
                                    // Notify watchers
                                    let _ = update_tx_clone.send(new_config);
                                    
                                    info!("✅ Configuration reloaded successfully");
                                }
                                Err(e) => {
                                    error!("Failed to reload configuration: {}", e);
                                }
                            }
                        }
                    }
                    Err(e) => {
                        error!("Watch error: {}", e);
                    }
                }
            }
        )?;
        
        // Start watching config file
        watcher.watch(&config_path, RecursiveMode::NonRecursive)?;
        
        Ok(Self {
            config,
            update_tx,
            _watcher: watcher,
        })
    }
    
    /// Get current configuration
    pub async fn get(&self) -> Config {
        self.config.read().await.clone()
    }
    
    /// Subscribe to configuration updates
    pub fn subscribe(&self) -> broadcast::Receiver<Config> {
        self.update_tx.subscribe()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;
    
    #[test]
    fn test_default_config() {
        let config = Config::default();
        assert_eq!(config.runtime.workers, 4);
        assert_eq!(config.gpu.devices, vec![0]);
    }
    
    #[test]
    fn test_config_validation() {
        let mut config = Config::default();
        
        // Valid config
        assert!(config.validate().is_ok());
        
        // Invalid workers
        config.runtime.workers = 0;
        assert!(config.validate().is_err());
        config.runtime.workers = 4;
        
        // Invalid memory fraction
        config.gpu.memory_fraction = 1.5;
        assert!(config.validate().is_err());
    }
    
    #[test]
    fn test_config_save_load() {
        let temp = tempdir().unwrap();
        let config_path = temp.path().join("config.yaml");
        
        let config = Config::default();
        config.save(&config_path).unwrap();
        
        let loaded = Config::load().unwrap();
        assert_eq!(loaded.runtime.workers, config.runtime.workers);
    }
}
