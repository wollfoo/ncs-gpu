//! Configuration manager with advanced features

use crate::{
    audit::{AuditLogger, ConfigEvent},
    errors::{ConfigError, ConfigResult},
    formats::{ConfigFormat, FormatDetector, FormatSerializer},
    security::{AccessControl, SecretManager},
    validation::{ConfigValidator, ValidationResult},
    watcher::{ConfigWatcher, WatchEvent, WatcherConfig},
    AppConfig,
};
use figment::{
    providers::{Env, Format, Json, Toml, Yaml},
    Figment,
};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    path::{Path, PathBuf},
    sync::Arc,
    time::Duration,
};
use tokio::sync::{broadcast, watch};
use tracing::{debug, error, info, warn};

/// Configuration source types
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum ConfigSource {
    /// Load from file path
    File { path: PathBuf, format: Option<ConfigFormat> },
    /// Load from environment variables
    Environment { prefix: String },
    /// Load from raw string content
    String { content: String, format: ConfigFormat },
    /// Load from JSON value
    Json { value: serde_json::Value },
    /// Load from remote URL
    Remote { url: String, format: Option<ConfigFormat> },
    /// Load from multiple sources (merged)
    Multiple { sources: Vec<ConfigSource> },
}

/// Configuration change notification
#[derive(Debug, Clone)]
pub struct ConfigChange {
    /// Type of change
    pub change_type: ChangeType,
    /// Configuration section affected
    pub section: Option<String>,
    /// Old configuration value
    pub old_config: Option<AppConfig>,
    /// New configuration value
    pub new_config: AppConfig,
    /// Timestamp of change
    pub timestamp: chrono::DateTime<chrono::Utc>,
    /// Source of change
    pub source: String,
}

/// Configuration change types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChangeType {
    /// Configuration loaded for first time
    Loaded,
    /// Configuration reloaded from file
    Reloaded,
    /// Configuration updated programmatically
    Updated,
    /// Configuration validated
    Validated,
    /// Configuration saved to file
    Saved,
}

/// Configuration manager settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManagerConfig {
    /// Enable configuration caching
    pub enable_caching: bool,
    /// Cache TTL in seconds
    pub cache_ttl_seconds: u64,
    /// Enable change notifications
    pub enable_notifications: bool,
    /// Enable automatic backups
    pub enable_auto_backup: bool,
    /// Backup directory
    pub backup_dir: PathBuf,
    /// Maximum number of backup files to keep
    pub max_backups: u32,
    /// Enable hot reload
    pub enable_hot_reload: bool,
    /// Hot reload debounce delay
    pub reload_debounce_ms: u64,
    /// Enable validation on load
    pub validate_on_load: bool,
    /// Enable audit logging
    pub enable_audit_logging: bool,
    /// Enable access control
    pub enable_access_control: bool,
}

impl Default for ManagerConfig {
    fn default() -> Self {
        Self {
            enable_caching: true,
            cache_ttl_seconds: 300, // 5 minutes
            enable_notifications: true,
            enable_auto_backup: true,
            backup_dir: PathBuf::from("./config/backups"),
            max_backups: 10,
            enable_hot_reload: true,
            reload_debounce_ms: 500,
            validate_on_load: true,
            enable_audit_logging: true,
            enable_access_control: false,
        }
    }
}

/// Advanced configuration manager
pub struct ConfigManager {
    /// Current configuration
    current_config: Arc<RwLock<AppConfig>>,
    /// Manager configuration
    config: ManagerConfig,
    /// Configuration validator
    validator: Option<Arc<ConfigValidator>>,
    /// Secret manager
    secret_manager: Option<Arc<RwLock<SecretManager>>>,
    /// Access control
    access_control: Option<Arc<AccessControl>>,
    /// Audit logger
    audit_logger: Option<Arc<AuditLogger>>,
    /// File watcher for hot reload
    file_watcher: Option<Arc<RwLock<ConfigWatcher>>>,
    /// Configuration change broadcaster
    change_tx: Option<broadcast::Sender<ConfigChange>>,
    /// Configuration watch channel
    config_tx: Option<watch::Sender<AppConfig>>,
    /// Configuration cache
    cache: Arc<RwLock<HashMap<String, (AppConfig, chrono::DateTime<chrono::Utc>)>>>,
    /// Current configuration source
    current_source: Option<ConfigSource>,
}

impl ConfigManager {
    /// Create new configuration manager
    pub fn new(initial_config: AppConfig, config: ManagerConfig) -> Self {
        let (change_tx, _) = if config.enable_notifications {
            let (tx, rx) = broadcast::channel(1000);
            (Some(tx), Some(rx))
        } else {
            (None, None)
        };

        let (config_tx, _) = if config.enable_hot_reload {
            let (tx, rx) = watch::channel(initial_config.clone());
            (Some(tx), Some(rx))
        } else {
            (None, None)
        };

        Self {
            current_config: Arc::new(RwLock::new(initial_config)),
            config,
            validator: None,
            secret_manager: None,
            access_control: None,
            audit_logger: None,
            file_watcher: None,
            change_tx,
            config_tx,
            cache: Arc::new(RwLock::new(HashMap::new())),
            current_source: None,
        }
    }

    /// Set configuration validator
    pub fn with_validator(mut self, validator: Arc<ConfigValidator>) -> Self {
        self.validator = Some(validator);
        self
    }

    /// Set secret manager
    pub fn with_secret_manager(mut self, secret_manager: Arc<RwLock<SecretManager>>) -> Self {
        self.secret_manager = Some(secret_manager);
        self
    }

    /// Set access control
    pub fn with_access_control(mut self, access_control: Arc<AccessControl>) -> Self {
        self.access_control = Some(access_control);
        self
    }

    /// Set audit logger
    pub fn with_audit_logger(mut self, audit_logger: Arc<AuditLogger>) -> Self {
        self.audit_logger = Some(audit_logger);
        self
    }

    /// Load configuration from source
    pub async fn load_from_source(&mut self, source: ConfigSource) -> ConfigResult<AppConfig> {
        let start_time = std::time::Instant::now();
        info!("Loading configuration from source: {:?}", source);

        // Check cache first
        if self.config.enable_caching {
            if let Some(cached) = self.get_from_cache(&source).await? {
                debug!("Configuration loaded from cache");
                return Ok(cached);
            }
        }

        let config = match &source {
            ConfigSource::File { path, format } => {
                self.load_from_file(path, format.as_ref()).await?
            }
            ConfigSource::Environment { prefix } => {
                self.load_from_environment(prefix).await?
            }
            ConfigSource::String { content, format } => {
                self.load_from_string(content, *format).await?
            }
            ConfigSource::Json { value } => {
                self.load_from_json(value).await?
            }
            ConfigSource::Remote { url, format } => {
                self.load_from_remote(url, format.as_ref()).await?
            }
            ConfigSource::Multiple { sources } => {
                self.load_from_multiple_sources(sources).await?
            }
        };

        // Validate configuration if enabled
        if self.config.validate_on_load {
            if let Some(ref validator) = self.validator {
                let config_json = serde_json::to_value(&config)?;
                let validation_result = validator.validate_config(&config_json).await?;

                if !validation_result.is_valid {
                    // Log validation errors
                    if let Some(ref audit_logger) = self.audit_logger {
                        let event = ConfigEvent::ValidationFailed {
                            path: self.get_source_path(&source).unwrap_or_else(|| PathBuf::from("unknown")),
                            timestamp: chrono::Utc::now(),
                            errors: validation_result.errors.iter().map(|e| e.message.clone()).collect(),
                        };
                        if let Err(e) = audit_logger.log_event(event).await {
                            warn!("Failed to log validation failure: {}", e);
                        }
                    }

                    return Err(ConfigError::schema_validation(format!(
                        "Configuration validation failed with {} errors",
                        validation_result.errors.len()
                    )));
                }

                info!("Configuration validation passed with {} warnings", validation_result.warnings.len());
            }
        }

        // Update current configuration
        {
            let mut current = self.current_config.write();
            *current = config.clone();
        }

        // Cache configuration if enabled
        if self.config.enable_caching {
            self.store_in_cache(source.clone(), config.clone()).await?;
        }

        // Create backup if enabled
        if self.config.enable_auto_backup {
            if let Err(e) = self.create_backup(&config, &source).await {
                warn!("Failed to create configuration backup: {}", e);
            }
        }

        // Send notifications
        if let Some(ref tx) = self.config_tx {
            let _ = tx.send(config.clone());
        }

        if let Some(ref tx) = self.change_tx {
            let change = ConfigChange {
                change_type: if self.current_source.is_some() { ChangeType::Reloaded } else { ChangeType::Loaded },
                section: None,
                old_config: None,
                new_config: config.clone(),
                timestamp: chrono::Utc::now(),
                source: format!("{:?}", source),
            };
            let _ = tx.send(change);
        }

        // Log audit event
        if let Some(ref audit_logger) = self.audit_logger {
            let event = ConfigEvent::Loaded {
                path: self.get_source_path(&source).unwrap_or_else(|| PathBuf::from("unknown")),
                timestamp: chrono::Utc::now(),
                source: format!("{:?}", source),
            };
            if let Err(e) = audit_logger.log_event(event).await {
                warn!("Failed to log load event: {}", e);
            }
        }

        self.current_source = Some(source);

        let duration = start_time.elapsed();
        info!("Configuration loaded successfully in {:?}", duration);

        Ok(config)
    }

    /// Get current configuration
    pub fn current_config(&self) -> AppConfig {
        self.current_config.read().clone()
    }

    /// Update configuration programmatically
    pub async fn update_config(&self, new_config: AppConfig) -> ConfigResult<()> {
        let old_config = {
            let mut current = self.current_config.write();
            let old = current.clone();
            *current = new_config.clone();
            old
        };

        // Send notifications
        if let Some(ref tx) = self.config_tx {
            let _ = tx.send(new_config.clone());
        }

        if let Some(ref tx) = self.change_tx {
            let change = ConfigChange {
                change_type: ChangeType::Updated,
                section: None,
                old_config: Some(old_config),
                new_config: new_config.clone(),
                timestamp: chrono::Utc::now(),
                source: "programmatic".to_string(),
            };
            let _ = tx.send(change);
        }

        info!("Configuration updated programmatically");
        Ok(())
    }

    /// Save current configuration to file
    pub async fn save_to_file(&self, path: &Path, format: Option<ConfigFormat>) -> ConfigResult<()> {
        let config = self.current_config.read().clone();
        let detected_format = format.unwrap_or_else(|| {
            FormatDetector::detect_from_path(path).unwrap_or(ConfigFormat::Toml)
        });

        let content = FormatSerializer::serialize(&config, detected_format)?;

        // Create backup of existing file
        if path.exists() && self.config.enable_auto_backup {
            let backup_path = self.generate_backup_path(path)?;
            if let Err(e) = tokio::fs::copy(path, &backup_path).await {
                warn!("Failed to backup existing file: {}", e);
            }
        }

        tokio::fs::write(path, content).await?;

        // Log audit event
        if let Some(ref audit_logger) = self.audit_logger {
            let event = ConfigEvent::Saved {
                path: path.to_path_buf(),
                timestamp: chrono::Utc::now(),
                format: detected_format.to_string(),
            };
            if let Err(e) = audit_logger.log_event(event).await {
                warn!("Failed to log save event: {}", e);
            }
        }

        info!("Configuration saved to: {}", path.display());
        Ok(())
    }

    /// Start hot reload watching
    pub async fn start_hot_reload(&mut self, config_path: PathBuf) -> ConfigResult<broadcast::Receiver<WatchEvent>> {
        if !self.config.enable_hot_reload {
            return Err(ConfigError::hot_reload("Hot reload is disabled"));
        }

        let watcher_config = WatcherConfig {
            debounce_delay: Duration::from_millis(self.config.reload_debounce_ms),
            enable_audit_logging: self.config.enable_audit_logging,
            ..Default::default()
        };

        let current_config = self.current_config.read().clone();
        let mut watcher = ConfigWatcher::new(config_path.clone(), current_config, watcher_config);

        if let Some(ref audit_logger) = self.audit_logger {
            watcher = watcher.with_audit_logger(Arc::clone(audit_logger));
        }

        let (config_rx, watch_events_rx) = watcher.start_watching().await?;

        // Spawn task to handle configuration updates
        let current_config = Arc::clone(&self.current_config);
        let config_tx = self.config_tx.clone();
        let change_tx = self.change_tx.clone();

        tokio::spawn(async move {
            let mut config_rx = config_rx;
            while config_rx.changed().await.is_ok() {
                let new_config = config_rx.borrow().clone();

                // Update current configuration
                {
                    let mut current = current_config.write();
                    *current = new_config.clone();
                }

                // Send notifications
                if let Some(ref tx) = config_tx {
                    let _ = tx.send(new_config.clone());
                }

                if let Some(ref tx) = change_tx {
                    let change = ConfigChange {
                        change_type: ChangeType::Reloaded,
                        section: None,
                        old_config: None,
                        new_config: new_config.clone(),
                        timestamp: chrono::Utc::now(),
                        source: "file_watcher".to_string(),
                    };
                    let _ = tx.send(change);
                }
            }
        });

        self.file_watcher = Some(Arc::new(RwLock::new(watcher)));

        info!("Hot reload started for: {}", config_path.display());
        Ok(watch_events_rx)
    }

    /// Subscribe to configuration changes
    pub fn subscribe_to_changes(&self) -> Option<broadcast::Receiver<ConfigChange>> {
        self.change_tx.as_ref().map(|tx| tx.subscribe())
    }

    /// Subscribe to configuration updates
    pub fn subscribe_to_config(&self) -> Option<watch::Receiver<AppConfig>> {
        self.config_tx.as_ref().map(|tx| tx.subscribe())
    }

    /// Get configuration statistics
    pub async fn get_statistics(&self) -> ConfigResult<ManagerStatistics> {
        let cache_size = self.cache.read().len();
        let current_config = self.current_config.read().clone();

        let stats = ManagerStatistics {
            cache_size,
            current_source: self.current_source.clone(),
            hot_reload_enabled: self.file_watcher.is_some(),
            validation_enabled: self.validator.is_some(),
            audit_enabled: self.audit_logger.is_some(),
            access_control_enabled: self.access_control.is_some(),
            config_size: serde_json::to_vec(&current_config)?.len(),
        };

        Ok(stats)
    }

    /// Clear configuration cache
    pub async fn clear_cache(&self) -> ConfigResult<()> {
        let mut cache = self.cache.write();
        let cleared_count = cache.len();
        cache.clear();

        info!("Cleared {} entries from configuration cache", cleared_count);
        Ok(())
    }

    async fn load_from_file(&self, path: &Path, format: Option<&ConfigFormat>) -> ConfigResult<AppConfig> {
        if !path.exists() {
            return Err(ConfigError::not_found(path.display().to_string()));
        }

        let content = tokio::fs::read_to_string(path).await?;
        let detected_format = format.copied().unwrap_or_else(|| {
            FormatDetector::detect_from_path(path).unwrap_or(ConfigFormat::Toml)
        });

        FormatSerializer::deserialize(&content, detected_format)
    }

    async fn load_from_environment(&self, prefix: &str) -> ConfigResult<AppConfig> {
        let config: AppConfig = Figment::new()
            .merge(Env::prefixed(prefix))
            .extract()?;
        Ok(config)
    }

    async fn load_from_string(&self, content: &str, format: ConfigFormat) -> ConfigResult<AppConfig> {
        FormatSerializer::deserialize(content, format)
    }

    async fn load_from_json(&self, value: &serde_json::Value) -> ConfigResult<AppConfig> {
        serde_json::from_value(value.clone()).map_err(ConfigError::Serialization)
    }

    async fn load_from_remote(&self, url: &str, format: Option<&ConfigFormat>) -> ConfigResult<AppConfig> {
        let response = reqwest::get(url).await
            .map_err(|e| ConfigError::Io(std::io::Error::new(std::io::ErrorKind::Other, e)))?;

        let content = response.text().await
            .map_err(|e| ConfigError::Io(std::io::Error::new(std::io::ErrorKind::Other, e)))?;

        let detected_format = format.copied().unwrap_or_else(|| {
            FormatDetector::detect_from_content(&content).unwrap_or(ConfigFormat::Json)
        });

        FormatSerializer::deserialize(&content, detected_format)
    }

    async fn load_from_multiple_sources(&self, sources: &[ConfigSource]) -> ConfigResult<AppConfig> {
        if sources.is_empty() {
            return Err(ConfigError::validation("No sources provided"));
        }

        let mut figment = Figment::new();

        for source in sources {
            match source {
                ConfigSource::File { path, format } => {
                    if path.exists() {
                        let detected_format = format.unwrap_or_else(|| {
                            FormatDetector::detect_from_path(path).unwrap_or(ConfigFormat::Toml)
                        });

                        figment = match detected_format {
                            ConfigFormat::Toml => figment.merge(Toml::file(path)),
                            ConfigFormat::Yaml => figment.merge(Yaml::file(path)),
                            ConfigFormat::Json => figment.merge(Json::file(path)),
                        };
                    }
                }
                ConfigSource::Environment { prefix } => {
                    figment = figment.merge(Env::prefixed(prefix));
                }
                _ => {
                    // For complex sources, load individually and merge
                    let mut temp_manager = ConfigManager::new(AppConfig::default(), ManagerConfig::default());
                    let config = temp_manager.load_from_source(source.clone()).await?;
                    let config_value = serde_json::to_value(config)?;
                    figment = figment.merge(figment::providers::Serialized::defaults(config_value));
                }
            }
        }

        figment.extract().map_err(ConfigError::Figment)
    }

    async fn get_from_cache(&self, source: &ConfigSource) -> ConfigResult<Option<AppConfig>> {
        let cache_key = format!("{:?}", source);
        let cache = self.cache.read();

        if let Some((config, timestamp)) = cache.get(&cache_key) {
            let age = chrono::Utc::now().signed_duration_since(*timestamp);
            if age.num_seconds() < self.config.cache_ttl_seconds as i64 {
                return Ok(Some(config.clone()));
            }
        }

        Ok(None)
    }

    async fn store_in_cache(&self, source: ConfigSource, config: AppConfig) -> ConfigResult<()> {
        let cache_key = format!("{:?}", source);
        let mut cache = self.cache.write();
        cache.insert(cache_key, (config, chrono::Utc::now()));
        Ok(())
    }

    async fn create_backup(&self, config: &AppConfig, source: &ConfigSource) -> ConfigResult<()> {
        if !self.config.enable_auto_backup {
            return Ok(());
        }

        tokio::fs::create_dir_all(&self.config.backup_dir).await?;

        let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
        let backup_name = match source {
            ConfigSource::File { path, .. } => {
                format!("{}_{}.backup.toml",
                    path.file_stem().unwrap_or_default().to_string_lossy(),
                    timestamp)
            }
            _ => format!("config_{}.backup.toml", timestamp),
        };

        let backup_path = self.config.backup_dir.join(backup_name);
        let content = FormatSerializer::serialize(config, ConfigFormat::Toml)?;

        tokio::fs::write(&backup_path, content).await?;

        // Cleanup old backups
        self.cleanup_old_backups().await?;

        debug!("Created configuration backup: {}", backup_path.display());
        Ok(())
    }

    async fn cleanup_old_backups(&self) -> ConfigResult<()> {
        let mut entries = tokio::fs::read_dir(&self.config.backup_dir).await?;
        let mut backup_files = Vec::new();

        while let Some(entry) = entries.next_entry().await? {
            let path = entry.path();
            if let Some(file_name) = path.file_name().and_then(|name| name.to_str()) {
                if file_name.ends_with(".backup.toml") {
                    if let Ok(metadata) = entry.metadata().await {
                        backup_files.push((path, metadata.modified().unwrap_or(std::time::SystemTime::UNIX_EPOCH)));
                    }
                }
            }
        }

        // Sort by modification time (newest first)
        backup_files.sort_by(|a, b| b.1.cmp(&a.1));

        // Remove excess backups
        let files_to_remove = backup_files.len().saturating_sub(self.config.max_backups as usize);
        for (path, _) in backup_files.iter().skip(self.config.max_backups as usize) {
            if let Err(e) = tokio::fs::remove_file(path).await {
                warn!("Failed to remove old backup {}: {}", path.display(), e);
            }
        }

        if files_to_remove > 0 {
            debug!("Cleaned up {} old backup files", files_to_remove);
        }

        Ok(())
    }

    fn get_source_path(&self, source: &ConfigSource) -> Option<PathBuf> {
        match source {
            ConfigSource::File { path, .. } => Some(path.clone()),
            _ => None,
        }
    }

    fn generate_backup_path(&self, original_path: &Path) -> ConfigResult<PathBuf> {
        let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
        let file_name = original_path.file_name()
            .ok_or_else(|| ConfigError::validation("Invalid file path"))?;

        Ok(original_path.with_file_name(format!("{}.backup.{}",
            file_name.to_string_lossy(), timestamp)))
    }
}

/// Configuration manager statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManagerStatistics {
    pub cache_size: usize,
    pub current_source: Option<ConfigSource>,
    pub hot_reload_enabled: bool,
    pub validation_enabled: bool,
    pub audit_enabled: bool,
    pub access_control_enabled: bool,
    pub config_size: usize,
}

/// Static method to load configuration from source without manager instance
impl ConfigManager {
    pub async fn load_from_source(source: ConfigSource) -> ConfigResult<AppConfig> {
        let mut manager = ConfigManager::new(AppConfig::default(), ManagerConfig::default());
        manager.load_from_source(source).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::{NamedTempFile, TempDir};

    #[tokio::test]
    async fn test_manager_creation() {
        let config = AppConfig::default();
        let manager_config = ManagerConfig::default();
        let manager = ConfigManager::new(config.clone(), manager_config);

        assert_eq!(manager.current_config(), config);
    }

    #[tokio::test]
    async fn test_file_loading() {
        let temp_file = NamedTempFile::new().unwrap();
        let config = AppConfig::default();
        let content = toml::to_string_pretty(&config).unwrap();

        tokio::fs::write(temp_file.path(), content).await.unwrap();

        let source = ConfigSource::File {
            path: temp_file.path().to_path_buf(),
            format: Some(ConfigFormat::Toml),
        };

        let mut manager = ConfigManager::new(AppConfig::default(), ManagerConfig::default());
        let loaded_config = manager.load_from_source(source).await.unwrap();

        // Basic comparison (some fields might differ due to defaults)
        assert_eq!(loaded_config.mining.algorithm, config.mining.algorithm);
    }

    #[tokio::test]
    async fn test_change_notifications() {
        let config = AppConfig::default();
        let manager_config = ManagerConfig::default();
        let manager = ConfigManager::new(config.clone(), manager_config);

        let mut change_rx = manager.subscribe_to_changes().unwrap();

        let new_config = AppConfig::default();
        manager.update_config(new_config).await.unwrap();

        let change = change_rx.recv().await.unwrap();
        assert_eq!(change.change_type, ChangeType::Updated);
    }

    #[tokio::test]
    async fn test_backup_functionality() {
        let temp_dir = TempDir::new().unwrap();
        let config = AppConfig::default();

        let manager_config = ManagerConfig {
            enable_auto_backup: true,
            backup_dir: temp_dir.path().to_path_buf(),
            ..Default::default()
        };

        let mut manager = ConfigManager::new(config.clone(), manager_config);

        let source = ConfigSource::Json {
            value: serde_json::to_value(config).unwrap(),
        };

        manager.load_from_source(source).await.unwrap();

        // Check if backup was created
        let mut entries = tokio::fs::read_dir(temp_dir.path()).await.unwrap();
        let mut backup_found = false;

        while let Some(entry) = entries.next_entry().await.unwrap() {
            let path = entry.path();
            if let Some(file_name) = path.file_name().and_then(|name| name.to_str()) {
                if file_name.contains("backup") {
                    backup_found = true;
                    break;
                }
            }
        }

        assert!(backup_found, "Backup file should have been created");
    }

    #[tokio::test]
    async fn test_cache_functionality() {
        let config = AppConfig::default();
        let manager_config = ManagerConfig {
            enable_caching: true,
            cache_ttl_seconds: 60,
            ..Default::default()
        };

        let mut manager = ConfigManager::new(config.clone(), manager_config);

        let source = ConfigSource::Json {
            value: serde_json::to_value(config).unwrap(),
        };

        // First load (should cache)
        let config1 = manager.load_from_source(source.clone()).await.unwrap();

        // Second load (should use cache)
        let config2 = manager.load_from_source(source).await.unwrap();

        assert_eq!(config1.mining.algorithm, config2.mining.algorithm);
    }
}