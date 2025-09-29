//! Configuration file watching and hot reload system

use crate::{
    audit::{AuditLogger, ConfigEvent},
    errors::{ConfigError, ConfigResult},
    AppConfig,
};
use notify::{Event, EventKind, RecommendedWatcher, RecursiveMode, Watcher};
use parking_lot::RwLock;
use std::{
    path::PathBuf,
    sync::Arc,
    time::{Duration, Instant},
};
use tokio::sync::{broadcast, watch};
use tracing::{debug, error, info, warn};

/// Configuration change event types
#[derive(Debug, Clone, PartialEq)]
pub enum WatchEvent {
    /// Configuration file was modified
    Modified {
        path: PathBuf,
        timestamp: Instant,
    },
    /// Configuration file was created
    Created {
        path: PathBuf,
        timestamp: Instant,
    },
    /// Configuration file was deleted
    Deleted {
        path: PathBuf,
        timestamp: Instant,
    },
    /// Configuration reload completed successfully
    ReloadSuccess {
        path: PathBuf,
        timestamp: Instant,
        config: AppConfig,
    },
    /// Configuration reload failed
    ReloadFailed {
        path: PathBuf,
        timestamp: Instant,
        error: String,
    },
    /// File watching error occurred
    WatchError {
        error: String,
        timestamp: Instant,
    },
}

impl WatchEvent {
    /// Get the timestamp of this event
    pub fn timestamp(&self) -> Instant {
        match self {
            WatchEvent::Modified { timestamp, .. }
            | WatchEvent::Created { timestamp, .. }
            | WatchEvent::Deleted { timestamp, .. }
            | WatchEvent::ReloadSuccess { timestamp, .. }
            | WatchEvent::ReloadFailed { timestamp, .. }
            | WatchEvent::WatchError { timestamp, .. } => *timestamp,
        }
    }

    /// Get the file path if available
    pub fn path(&self) -> Option<&PathBuf> {
        match self {
            WatchEvent::Modified { path, .. }
            | WatchEvent::Created { path, .. }
            | WatchEvent::Deleted { path, .. }
            | WatchEvent::ReloadSuccess { path, .. }
            | WatchEvent::ReloadFailed { path, .. } => Some(path),
            WatchEvent::WatchError { .. } => None,
        }
    }

    /// Check if this is an error event
    pub fn is_error(&self) -> bool {
        matches!(self, WatchEvent::ReloadFailed { .. } | WatchEvent::WatchError { .. })
    }
}

/// Configuration watcher settings
#[derive(Debug, Clone)]
pub struct WatcherConfig {
    /// Debounce delay to avoid multiple rapid reloads
    pub debounce_delay: Duration,
    /// Maximum number of reload attempts on failure
    pub max_retry_attempts: u32,
    /// Delay between retry attempts
    pub retry_delay: Duration,
    /// Enable automatic backup before reload
    pub enable_backup: bool,
    /// Enable audit logging for configuration changes
    pub enable_audit_logging: bool,
    /// Watch subdirectories recursively
    pub recursive: bool,
    /// File patterns to ignore
    pub ignore_patterns: Vec<String>,
}

impl Default for WatcherConfig {
    fn default() -> Self {
        Self {
            debounce_delay: Duration::from_millis(500),
            max_retry_attempts: 3,
            retry_delay: Duration::from_secs(1),
            enable_backup: true,
            enable_audit_logging: true,
            recursive: false,
            ignore_patterns: vec![
                "*.tmp".to_string(),
                "*.backup".to_string(),
                "*~".to_string(),
                ".#*".to_string(),
            ],
        }
    }
}

/// Hot reload configuration watcher with advanced features
pub struct ConfigWatcher {
    config_path: PathBuf,
    current_config: Arc<RwLock<AppConfig>>,
    watcher_config: WatcherConfig,
    audit_logger: Option<Arc<AuditLogger>>,
    _watcher: Option<RecommendedWatcher>,
    config_tx: Option<watch::Sender<AppConfig>>,
    event_tx: Option<broadcast::Sender<WatchEvent>>,
    last_reload: Arc<RwLock<Option<Instant>>>,
    reload_count: Arc<RwLock<u64>>,
}

impl ConfigWatcher {
    /// Create new configuration watcher
    pub fn new(
        config_path: PathBuf,
        initial_config: AppConfig,
        watcher_config: WatcherConfig,
    ) -> Self {
        Self {
            config_path,
            current_config: Arc::new(RwLock::new(initial_config)),
            watcher_config,
            audit_logger: None,
            _watcher: None,
            config_tx: None,
            event_tx: None,
            last_reload: Arc::new(RwLock::new(None)),
            reload_count: Arc::new(RwLock::new(0)),
        }
    }

    /// Enable audit logging for configuration changes
    pub fn with_audit_logger(mut self, audit_logger: Arc<AuditLogger>) -> Self {
        self.audit_logger = Some(audit_logger);
        self
    }

    /// Start watching for configuration changes
    pub async fn start_watching(
        &mut self,
    ) -> ConfigResult<(watch::Receiver<AppConfig>, broadcast::Receiver<WatchEvent>)> {
        let (config_tx, config_rx) = watch::channel(self.current_config.read().clone());
        let (event_tx, event_rx) = broadcast::channel(1000);

        self.config_tx = Some(config_tx);
        self.event_tx = Some(event_tx.clone());

        let config_path = self.config_path.clone();
        let current_config = Arc::clone(&self.current_config);
        let watcher_config = self.watcher_config.clone();
        let audit_logger = self.audit_logger.clone();
        let last_reload = Arc::clone(&self.last_reload);
        let reload_count = Arc::clone(&self.reload_count);

        // Create file watcher
        let (tx, mut rx) = tokio::sync::mpsc::channel(1000);
        let mut watcher = notify::recommended_watcher(move |res: Result<Event, notify::Error>| {
            if let Err(e) = tx.blocking_send(res) {
                error!("Failed to send file watch event: {}", e);
            }
        })?;

        // Watch the configuration file directory
        let watch_path = config_path.parent().unwrap_or(&config_path);
        let mode = if watcher_config.recursive {
            RecursiveMode::Recursive
        } else {
            RecursiveMode::NonRecursive
        };

        watcher.watch(watch_path, mode)?;
        self._watcher = Some(watcher);

        // Spawn event processing task
        let config_tx_clone = self.config_tx.as_ref().unwrap().clone();
        tokio::spawn(async move {
            let mut last_event_time: Option<Instant> = None;

            while let Some(res) = rx.recv().await {
                match res {
                    Ok(event) => {
                        if Self::should_process_event(&event, &config_path, &watcher_config) {
                            let now = Instant::now();

                            // Debounce: only process if enough time has passed since last event
                            if let Some(last_time) = last_event_time {
                                if now.duration_since(last_time) < watcher_config.debounce_delay {
                                    debug!("Debouncing config file change event");
                                    continue;
                                }
                            }
                            last_event_time = Some(now);

                            let watch_event = match event.kind {
                                EventKind::Modify(_) => WatchEvent::Modified {
                                    path: config_path.clone(),
                                    timestamp: now,
                                },
                                EventKind::Create(_) => WatchEvent::Created {
                                    path: config_path.clone(),
                                    timestamp: now,
                                },
                                EventKind::Remove(_) => WatchEvent::Deleted {
                                    path: config_path.clone(),
                                    timestamp: now,
                                },
                                _ => continue,
                            };

                            let _ = event_tx.send(watch_event);

                            // Only reload on modify events
                            if matches!(event.kind, EventKind::Modify(_)) {
                                Self::handle_config_reload(
                                    &config_path,
                                    &current_config,
                                    &config_tx_clone,
                                    &event_tx,
                                    &watcher_config,
                                    &audit_logger,
                                    &last_reload,
                                    &reload_count,
                                ).await;
                            }
                        }
                    }
                    Err(error) => {
                        let watch_event = WatchEvent::WatchError {
                            error: error.to_string(),
                            timestamp: Instant::now(),
                        };
                        let _ = event_tx.send(watch_event);
                        error!("File watcher error: {}", error);
                    }
                }
            }
        });

        info!("Started configuration file watcher for: {}", config_path.display());

        Ok((config_rx, event_rx))
    }

    /// Stop watching (watcher will be dropped automatically)
    pub fn stop_watching(&mut self) {
        self._watcher = None;
        self.config_tx = None;
        self.event_tx = None;
        info!("Stopped configuration file watcher");
    }

    /// Get current configuration
    pub fn current_config(&self) -> AppConfig {
        self.current_config.read().clone()
    }

    /// Get reload statistics
    pub fn reload_stats(&self) -> (Option<Instant>, u64) {
        let last_reload = *self.last_reload.read();
        let count = *self.reload_count.read();
        (last_reload, count)
    }

    /// Manual configuration reload
    pub async fn reload_now(&self) -> ConfigResult<AppConfig> {
        let new_config = AppConfig::load(self.config_path.to_str().unwrap()).await?;

        // Update current config
        {
            let mut current = self.current_config.write();
            *current = new_config.clone();
        }

        // Update reload stats
        {
            let mut last_reload = self.last_reload.write();
            *last_reload = Some(Instant::now());
            let mut count = self.reload_count.write();
            *count += 1;
        }

        // Send update notifications
        if let Some(ref tx) = self.config_tx {
            let _ = tx.send(new_config.clone());
        }

        if let Some(ref tx) = self.event_tx {
            let event = WatchEvent::ReloadSuccess {
                path: self.config_path.clone(),
                timestamp: Instant::now(),
                config: new_config.clone(),
            };
            let _ = tx.send(event);
        }

        // Log to audit if enabled
        if let Some(ref audit_logger) = self.audit_logger {
            let event = ConfigEvent::Reloaded {
                path: self.config_path.clone(),
                timestamp: chrono::Utc::now(),
                trigger: "manual".to_string(),
            };
            if let Err(e) = audit_logger.log_event(event).await {
                warn!("Failed to log audit event: {}", e);
            }
        }

        info!("Configuration reloaded successfully");
        Ok(new_config)
    }

    fn should_process_event(
        event: &Event,
        config_path: &PathBuf,
        watcher_config: &WatcherConfig,
    ) -> bool {
        // Check if the event affects our config file
        if !event.paths.iter().any(|p| p == config_path) {
            return false;
        }

        // Check ignore patterns
        if let Some(file_name) = config_path.file_name().and_then(|n| n.to_str()) {
            for pattern in &watcher_config.ignore_patterns {
                if Self::matches_pattern(file_name, pattern) {
                    return false;
                }
            }
        }

        true
    }

    fn matches_pattern(name: &str, pattern: &str) -> bool {
        // Simple glob pattern matching
        if pattern.contains('*') {
            let pattern_parts: Vec<&str> = pattern.split('*').collect();
            if pattern_parts.len() == 2 {
                let prefix = pattern_parts[0];
                let suffix = pattern_parts[1];
                return name.starts_with(prefix) && name.ends_with(suffix);
            }
        }
        name == pattern
    }

    async fn handle_config_reload(
        config_path: &PathBuf,
        current_config: &Arc<RwLock<AppConfig>>,
        config_tx: &watch::Sender<AppConfig>,
        event_tx: &broadcast::Sender<WatchEvent>,
        watcher_config: &WatcherConfig,
        audit_logger: &Option<Arc<AuditLogger>>,
        last_reload: &Arc<RwLock<Option<Instant>>>,
        reload_count: &Arc<RwLock<u64>>,
    ) {
        let mut attempts = 0;
        let timestamp = Instant::now();

        while attempts <= watcher_config.max_retry_attempts {
            attempts += 1;

            match AppConfig::load(config_path.to_str().unwrap()).await {
                Ok(new_config) => {
                    // Backup current config if enabled
                    if watcher_config.enable_backup {
                        if let Err(e) = Self::backup_current_config(config_path).await {
                            warn!("Failed to backup configuration: {}", e);
                        }
                    }

                    // Update current config
                    {
                        let mut current = current_config.write();
                        *current = new_config.clone();
                    }

                    // Update reload stats
                    {
                        let mut last = last_reload.write();
                        *last = Some(timestamp);
                        let mut count = reload_count.write();
                        *count += 1;
                    }

                    // Send notifications
                    let _ = config_tx.send(new_config.clone());

                    let event = WatchEvent::ReloadSuccess {
                        path: config_path.clone(),
                        timestamp,
                        config: new_config,
                    };
                    let _ = event_tx.send(event);

                    // Log to audit if enabled
                    if let Some(audit_logger) = audit_logger {
                        let audit_event = ConfigEvent::Reloaded {
                            path: config_path.clone(),
                            timestamp: chrono::Utc::now(),
                            trigger: "file_change".to_string(),
                        };
                        if let Err(e) = audit_logger.log_event(audit_event).await {
                            warn!("Failed to log audit event: {}", e);
                        }
                    }

                    info!("Configuration reloaded successfully (attempt {})", attempts);
                    return;
                }
                Err(error) => {
                    warn!("Configuration reload failed (attempt {}): {}", attempts, error);

                    if attempts > watcher_config.max_retry_attempts {
                        let event = WatchEvent::ReloadFailed {
                            path: config_path.clone(),
                            timestamp,
                            error: error.to_string(),
                        };
                        let _ = event_tx.send(event);

                        error!(
                            "Configuration reload failed after {} attempts: {}",
                            watcher_config.max_retry_attempts,
                            error
                        );
                    } else {
                        tokio::time::sleep(watcher_config.retry_delay).await;
                    }
                }
            }
        }
    }

    async fn backup_current_config(config_path: &PathBuf) -> ConfigResult<PathBuf> {
        let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
        let backup_path = config_path.with_extension(format!(
            "{}.backup.{}",
            config_path
                .extension()
                .and_then(|ext| ext.to_str())
                .unwrap_or(""),
            timestamp
        ));

        tokio::fs::copy(config_path, &backup_path).await?;
        debug!("Created configuration backup: {}", backup_path.display());

        Ok(backup_path)
    }
}

impl Drop for ConfigWatcher {
    fn drop(&mut self) {
        if self._watcher.is_some() {
            info!("Configuration watcher dropped");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::NamedTempFile;

    #[tokio::test]
    async fn test_watcher_creation() {
        let temp_file = NamedTempFile::new().unwrap();
        let config = AppConfig::default();
        let watcher_config = WatcherConfig::default();

        let watcher = ConfigWatcher::new(
            temp_file.path().to_path_buf(),
            config,
            watcher_config,
        );

        assert_eq!(watcher.config_path, temp_file.path());
    }

    #[test]
    fn test_pattern_matching() {
        assert!(ConfigWatcher::matches_pattern("test.tmp", "*.tmp"));
        assert!(ConfigWatcher::matches_pattern("backup.file", "*.file"));
        assert!(!ConfigWatcher::matches_pattern("test.toml", "*.tmp"));
        assert!(ConfigWatcher::matches_pattern("exact", "exact"));
    }

    #[test]
    fn test_watch_event_properties() {
        let now = Instant::now();
        let path = PathBuf::from("test.toml");

        let event = WatchEvent::Modified {
            path: path.clone(),
            timestamp: now,
        };

        assert_eq!(event.timestamp(), now);
        assert_eq!(event.path(), Some(&path));
        assert!(!event.is_error());

        let error_event = WatchEvent::WatchError {
            error: "test error".to_string(),
            timestamp: now,
        };

        assert!(error_event.is_error());
        assert_eq!(error_event.path(), None);
    }
}