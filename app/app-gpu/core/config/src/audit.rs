//! Audit logging system for configuration changes

use crate::errors::{ConfigError, ConfigResult};
use serde::{Deserialize, Serialize};
use std::{
    collections::VecDeque,
    path::{Path, PathBuf},
    sync::Arc,
};
use tokio::{
    fs::OpenOptions,
    io::AsyncWriteExt,
    sync::{Mutex, RwLock},
};
use tracing::{debug, error, info, warn};

/// Configuration audit event types
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum ConfigEvent {
    /// Configuration file was loaded
    Loaded {
        path: PathBuf,
        timestamp: chrono::DateTime<chrono::Utc>,
        source: String,
    },
    /// Configuration file was saved
    Saved {
        path: PathBuf,
        timestamp: chrono::DateTime<chrono::Utc>,
        format: String,
    },
    /// Configuration was reloaded due to file change
    Reloaded {
        path: PathBuf,
        timestamp: chrono::DateTime<chrono::Utc>,
        trigger: String,
    },
    /// Configuration validation failed
    ValidationFailed {
        path: PathBuf,
        timestamp: chrono::DateTime<chrono::Utc>,
        errors: Vec<String>,
    },
    /// Configuration access denied
    AccessDenied {
        path: PathBuf,
        timestamp: chrono::DateTime<chrono::Utc>,
        user: Option<String>,
        permission: String,
        section: String,
    },
    /// Secret was encrypted/stored
    SecretEncrypted {
        name: String,
        timestamp: chrono::DateTime<chrono::Utc>,
        algorithm: String,
    },
    /// Secret was decrypted/accessed
    SecretDecrypted {
        name: String,
        timestamp: chrono::DateTime<chrono::Utc>,
        accessed_by: Option<String>,
    },
    /// Configuration backup created
    BackupCreated {
        original_path: PathBuf,
        backup_path: PathBuf,
        timestamp: chrono::DateTime<chrono::Utc>,
    },
    /// Configuration rollback performed
    RollbackPerformed {
        path: PathBuf,
        backup_path: PathBuf,
        timestamp: chrono::DateTime<chrono::Utc>,
        reason: String,
    },
    /// Key rotation performed
    KeyRotation {
        timestamp: chrono::DateTime<chrono::Utc>,
        key_id: String,
        reason: String,
    },
    /// Schema validation performed
    SchemaValidated {
        path: PathBuf,
        timestamp: chrono::DateTime<chrono::Utc>,
        schema_version: String,
        result: bool,
    },
}

impl ConfigEvent {
    /// Get the timestamp of this event
    pub fn timestamp(&self) -> chrono::DateTime<chrono::Utc> {
        match self {
            ConfigEvent::Loaded { timestamp, .. }
            | ConfigEvent::Saved { timestamp, .. }
            | ConfigEvent::Reloaded { timestamp, .. }
            | ConfigEvent::ValidationFailed { timestamp, .. }
            | ConfigEvent::AccessDenied { timestamp, .. }
            | ConfigEvent::SecretEncrypted { timestamp, .. }
            | ConfigEvent::SecretDecrypted { timestamp, .. }
            | ConfigEvent::BackupCreated { timestamp, .. }
            | ConfigEvent::RollbackPerformed { timestamp, .. }
            | ConfigEvent::KeyRotation { timestamp, .. }
            | ConfigEvent::SchemaValidated { timestamp, .. } => *timestamp,
        }
    }

    /// Get the severity level of this event
    pub fn severity(&self) -> AuditSeverity {
        match self {
            ConfigEvent::AccessDenied { .. } => AuditSeverity::Critical,
            ConfigEvent::ValidationFailed { .. } => AuditSeverity::High,
            ConfigEvent::KeyRotation { .. } => AuditSeverity::High,
            ConfigEvent::RollbackPerformed { .. } => AuditSeverity::Medium,
            ConfigEvent::SecretDecrypted { .. } => AuditSeverity::Medium,
            _ => AuditSeverity::Low,
        }
    }

    /// Get the event category
    pub fn category(&self) -> &'static str {
        match self {
            ConfigEvent::Loaded { .. }
            | ConfigEvent::Saved { .. }
            | ConfigEvent::Reloaded { .. } => "configuration",
            ConfigEvent::ValidationFailed { .. }
            | ConfigEvent::SchemaValidated { .. } => "validation",
            ConfigEvent::AccessDenied { .. } => "security",
            ConfigEvent::SecretEncrypted { .. }
            | ConfigEvent::SecretDecrypted { .. }
            | ConfigEvent::KeyRotation { .. } => "security",
            ConfigEvent::BackupCreated { .. }
            | ConfigEvent::RollbackPerformed { .. } => "backup",
        }
    }

    /// Check if this event should trigger an alert
    pub fn should_alert(&self) -> bool {
        matches!(
            self.severity(),
            AuditSeverity::Critical | AuditSeverity::High
        )
    }
}

/// Audit event severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum AuditSeverity {
    Low,
    Medium,
    High,
    Critical,
}

impl std::fmt::Display for AuditSeverity {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AuditSeverity::Low => write!(f, "LOW"),
            AuditSeverity::Medium => write!(f, "MEDIUM"),
            AuditSeverity::High => write!(f, "HIGH"),
            AuditSeverity::Critical => write!(f, "CRITICAL"),
        }
    }
}

/// Audit logging configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditConfig {
    /// Enable audit logging
    pub enabled: bool,
    /// Maximum number of events to keep in memory
    pub max_memory_events: usize,
    /// Log file path for persistent storage
    pub log_file: Option<PathBuf>,
    /// Log rotation settings
    pub rotation: LogRotationConfig,
    /// Minimum severity level to log
    pub min_severity: AuditSeverity,
    /// Enable structured JSON logging
    pub json_format: bool,
    /// Buffer size for async logging
    pub buffer_size: usize,
    /// Enable real-time event streaming
    pub enable_streaming: bool,
}

impl Default for AuditConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            max_memory_events: 10000,
            log_file: Some(PathBuf::from("./logs/config_audit.log")),
            rotation: LogRotationConfig::default(),
            min_severity: AuditSeverity::Low,
            json_format: true,
            buffer_size: 1000,
            enable_streaming: false,
        }
    }
}

/// Log rotation configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogRotationConfig {
    /// Enable log rotation
    pub enabled: bool,
    /// Maximum log file size in bytes
    pub max_size: u64,
    /// Maximum number of rotated files to keep
    pub max_files: u32,
    /// Compress rotated files
    pub compress: bool,
}

impl Default for LogRotationConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            max_size: 100 * 1024 * 1024, // 100MB
            max_files: 10,
            compress: true,
        }
    }
}

/// Audit event filter for querying
#[derive(Debug, Clone, Default)]
pub struct AuditFilter {
    /// Filter by event category
    pub category: Option<String>,
    /// Filter by minimum severity
    pub min_severity: Option<AuditSeverity>,
    /// Filter by time range
    pub time_range: Option<(chrono::DateTime<chrono::Utc>, chrono::DateTime<chrono::Utc>)>,
    /// Filter by path pattern
    pub path_pattern: Option<String>,
    /// Filter by user
    pub user: Option<String>,
    /// Maximum number of events to return
    pub limit: Option<usize>,
}

/// Audit logger with persistent storage and real-time streaming
pub struct AuditLogger {
    config: AuditConfig,
    memory_events: Arc<RwLock<VecDeque<ConfigEvent>>>,
    event_buffer: Arc<Mutex<VecDeque<ConfigEvent>>>,
    streaming_tx: Option<tokio::sync::broadcast::Sender<ConfigEvent>>,
    _log_writer_task: Option<tokio::task::JoinHandle<()>>,
}

impl AuditLogger {
    /// Create new audit logger
    pub fn new(config: AuditConfig) -> ConfigResult<Self> {
        let memory_events = Arc::new(RwLock::new(VecDeque::with_capacity(
            config.max_memory_events,
        )));
        let event_buffer = Arc::new(Mutex::new(VecDeque::with_capacity(config.buffer_size)));

        let streaming_tx = if config.enable_streaming {
            let (tx, _) = tokio::sync::broadcast::channel(1000);
            Some(tx)
        } else {
            None
        };

        let mut logger = Self {
            config,
            memory_events,
            event_buffer,
            streaming_tx,
            _log_writer_task: None,
        };

        // Start background log writer task if file logging is enabled
        if logger.config.log_file.is_some() {
            logger.start_log_writer_task()?;
        }

        info!("Audit logger initialized");
        Ok(logger)
    }

    /// Log a configuration event
    pub async fn log_event(&self, event: ConfigEvent) -> ConfigResult<()> {
        if !self.config.enabled {
            return Ok(());
        }

        // Check severity filter
        if event.severity() < self.config.min_severity {
            return Ok(());
        }

        debug!("Logging audit event: {:?}", event);

        // Add to memory storage
        {
            let mut events = self.memory_events.write().await;
            if events.len() >= self.config.max_memory_events {
                events.pop_front();
            }
            events.push_back(event.clone());
        }

        // Add to file logging buffer
        if self.config.log_file.is_some() {
            let mut buffer = self.event_buffer.lock().await;
            buffer.push_back(event.clone());
        }

        // Stream event if enabled
        if let Some(ref tx) = self.streaming_tx {
            let _ = tx.send(event);
        }

        Ok(())
    }

    /// Query events with optional filtering
    pub async fn query_events(&self, filter: AuditFilter) -> ConfigResult<Vec<ConfigEvent>> {
        let events = self.memory_events.read().await;
        let mut filtered_events: Vec<ConfigEvent> = events
            .iter()
            .filter(|event| self.matches_filter(event, &filter))
            .cloned()
            .collect();

        // Apply time-based sorting (newest first)
        filtered_events.sort_by(|a, b| b.timestamp().cmp(&a.timestamp()));

        // Apply limit
        if let Some(limit) = filter.limit {
            filtered_events.truncate(limit);
        }

        Ok(filtered_events)
    }

    /// Get event statistics
    pub async fn get_statistics(&self) -> ConfigResult<AuditStatistics> {
        let events = self.memory_events.read().await;
        let total_events = events.len();

        let mut by_category = std::collections::HashMap::new();
        let mut by_severity = std::collections::HashMap::new();

        for event in events.iter() {
            *by_category.entry(event.category().to_string()).or_insert(0) += 1;
            *by_severity.entry(event.severity()).or_insert(0) += 1;
        }

        let oldest_event = events.front().map(|e| e.timestamp());
        let newest_event = events.back().map(|e| e.timestamp());

        Ok(AuditStatistics {
            total_events,
            by_category,
            by_severity,
            oldest_event,
            newest_event,
        })
    }

    /// Subscribe to real-time event stream
    pub fn subscribe_to_events(&self) -> Option<tokio::sync::broadcast::Receiver<ConfigEvent>> {
        self.streaming_tx.as_ref().map(|tx| tx.subscribe())
    }

    /// Clear all events from memory
    pub async fn clear_events(&self) -> ConfigResult<()> {
        let mut events = self.memory_events.write().await;
        events.clear();
        info!("Cleared all audit events from memory");
        Ok(())
    }

    /// Export events to file
    pub async fn export_events(&self, file_path: &Path, filter: AuditFilter) -> ConfigResult<()> {
        let events = self.query_events(filter).await?;

        let content = if self.config.json_format {
            serde_json::to_string_pretty(&events)?
        } else {
            events
                .iter()
                .map(|e| format!("{}: {:?}", e.timestamp().format("%Y-%m-%d %H:%M:%S UTC"), e))
                .collect::<Vec<_>>()
                .join("\n")
        };

        tokio::fs::write(file_path, content).await?;
        info!("Exported {} events to {}", events.len(), file_path.display());

        Ok(())
    }

    /// Rotate log files if needed
    pub async fn rotate_logs_if_needed(&self) -> ConfigResult<()> {
        if let Some(ref log_file) = self.config.log_file {
            if !self.config.rotation.enabled {
                return Ok(());
            }

            if let Ok(metadata) = tokio::fs::metadata(log_file).await {
                if metadata.len() > self.config.rotation.max_size {
                    self.rotate_log_file(log_file).await?;
                }
            }
        }

        Ok(())
    }

    fn start_log_writer_task(&mut self) -> ConfigResult<()> {
        let log_file = self.config.log_file.as_ref().unwrap().clone();
        let event_buffer = Arc::clone(&self.event_buffer);
        let json_format = self.config.json_format;

        let task = tokio::spawn(async move {
            let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(1));

            loop {
                interval.tick().await;

                let events_to_write = {
                    let mut buffer = event_buffer.lock().await;
                    let events: Vec<ConfigEvent> = buffer.drain(..).collect();
                    events
                };

                if events_to_write.is_empty() {
                    continue;
                }

                if let Err(e) = Self::write_events_to_file(&log_file, &events_to_write, json_format).await {
                    error!("Failed to write audit events to file: {}", e);
                }
            }
        });

        self._log_writer_task = Some(task);
        Ok(())
    }

    async fn write_events_to_file(
        log_file: &Path,
        events: &[ConfigEvent],
        json_format: bool,
    ) -> ConfigResult<()> {
        // Ensure directory exists
        if let Some(parent) = log_file.parent() {
            tokio::fs::create_dir_all(parent).await?;
        }

        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(log_file)
            .await?;

        for event in events {
            let line = if json_format {
                serde_json::to_string(event)?
            } else {
                format!("{}: {:?}", event.timestamp().format("%Y-%m-%d %H:%M:%S UTC"), event)
            };

            file.write_all(line.as_bytes()).await?;
            file.write_all(b"\n").await?;
        }

        file.flush().await?;
        Ok(())
    }

    async fn rotate_log_file(&self, log_file: &Path) -> ConfigResult<()> {
        let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
        let rotated_file = log_file.with_extension(format!(
            "{}.{}",
            log_file.extension().and_then(|ext| ext.to_str()).unwrap_or("log"),
            timestamp
        ));

        tokio::fs::rename(log_file, &rotated_file).await?;

        if self.config.rotation.compress {
            // Note: Compression would be implemented here
            warn!("Log compression not yet implemented");
        }

        // Clean up old log files
        self.cleanup_old_log_files(log_file).await?;

        info!("Rotated log file to: {}", rotated_file.display());
        Ok(())
    }

    async fn cleanup_old_log_files(&self, log_file: &Path) -> ConfigResult<()> {
        let parent_dir = log_file.parent().ok_or_else(|| {
            ConfigError::audit_log("Cannot determine log file parent directory")
        })?;

        let file_stem = log_file.file_stem().and_then(|stem| stem.to_str())
            .ok_or_else(|| ConfigError::audit_log("Cannot determine log file stem"))?;

        let mut entries = tokio::fs::read_dir(parent_dir).await?;
        let mut log_files = Vec::new();

        while let Some(entry) = entries.next_entry().await? {
            let path = entry.path();
            if let Some(file_name) = path.file_name().and_then(|name| name.to_str()) {
                if file_name.starts_with(file_stem) && file_name != log_file.file_name().unwrap() {
                    if let Ok(metadata) = entry.metadata().await {
                        log_files.push((path, metadata.modified().unwrap_or(std::time::SystemTime::UNIX_EPOCH)));
                    }
                }
            }
        }

        // Sort by modification time (oldest first)
        log_files.sort_by(|a, b| a.1.cmp(&b.1));

        // Remove excess files
        let files_to_remove = log_files.len().saturating_sub(self.config.rotation.max_files as usize);
        for (path, _) in log_files.iter().take(files_to_remove) {
            if let Err(e) = tokio::fs::remove_file(path).await {
                warn!("Failed to remove old log file {}: {}", path.display(), e);
            } else {
                debug!("Removed old log file: {}", path.display());
            }
        }

        Ok(())
    }

    fn matches_filter(&self, event: &ConfigEvent, filter: &AuditFilter) -> bool {
        if let Some(ref category) = filter.category {
            if event.category() != category {
                return false;
            }
        }

        if let Some(min_severity) = filter.min_severity {
            if event.severity() < min_severity {
                return false;
            }
        }

        if let Some((start, end)) = filter.time_range {
            let timestamp = event.timestamp();
            if timestamp < start || timestamp > end {
                return false;
            }
        }

        if let Some(ref path_pattern) = filter.path_pattern {
            // Simple pattern matching - could be enhanced with regex
            if let Some(path) = event.get_path() {
                if let Some(path_str) = path.to_str() {
                    if !path_str.contains(path_pattern) {
                        return false;
                    }
                }
            } else {
                return false;
            }
        }

        true
    }
}

impl ConfigEvent {
    fn get_path(&self) -> Option<&PathBuf> {
        match self {
            ConfigEvent::Loaded { path, .. }
            | ConfigEvent::Saved { path, .. }
            | ConfigEvent::Reloaded { path, .. }
            | ConfigEvent::ValidationFailed { path, .. }
            | ConfigEvent::AccessDenied { path, .. }
            | ConfigEvent::SchemaValidated { path, .. } => Some(path),
            ConfigEvent::BackupCreated { original_path, .. }
            | ConfigEvent::RollbackPerformed { path: original_path, .. } => Some(original_path),
            _ => None,
        }
    }
}

/// Audit statistics summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditStatistics {
    pub total_events: usize,
    pub by_category: std::collections::HashMap<String, usize>,
    pub by_severity: std::collections::HashMap<AuditSeverity, usize>,
    pub oldest_event: Option<chrono::DateTime<chrono::Utc>>,
    pub newest_event: Option<chrono::DateTime<chrono::Utc>>,
}

impl Drop for AuditLogger {
    fn drop(&mut self) {
        if let Some(task) = self._log_writer_task.take() {
            task.abort();
        }
        info!("Audit logger dropped");
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::NamedTempFile;

    #[tokio::test]
    async fn test_audit_logger_creation() {
        let config = AuditConfig::default();
        let logger = AuditLogger::new(config).unwrap();

        let event = ConfigEvent::Loaded {
            path: PathBuf::from("test.toml"),
            timestamp: chrono::Utc::now(),
            source: "file".to_string(),
        };

        logger.log_event(event).await.unwrap();
        let stats = logger.get_statistics().await.unwrap();
        assert_eq!(stats.total_events, 1);
    }

    #[tokio::test]
    async fn test_event_filtering() {
        let config = AuditConfig::default();
        let logger = AuditLogger::new(config).unwrap();

        // Log events with different severities
        let events = vec![
            ConfigEvent::Loaded {
                path: PathBuf::from("test1.toml"),
                timestamp: chrono::Utc::now(),
                source: "file".to_string(),
            },
            ConfigEvent::AccessDenied {
                path: PathBuf::from("test2.toml"),
                timestamp: chrono::Utc::now(),
                user: Some("testuser".to_string()),
                permission: "read".to_string(),
                section: "mining".to_string(),
            },
        ];

        for event in events {
            logger.log_event(event).await.unwrap();
        }

        // Filter by high severity
        let filter = AuditFilter {
            min_severity: Some(AuditSeverity::High),
            ..Default::default()
        };

        let filtered = logger.query_events(filter).await.unwrap();
        assert_eq!(filtered.len(), 1); // Only AccessDenied should match
    }

    #[tokio::test]
    async fn test_event_export() {
        let config = AuditConfig::default();
        let logger = AuditLogger::new(config).unwrap();

        let event = ConfigEvent::Saved {
            path: PathBuf::from("test.toml"),
            timestamp: chrono::Utc::now(),
            format: "toml".to_string(),
        };

        logger.log_event(event).await.unwrap();

        let temp_file = NamedTempFile::new().unwrap();
        let filter = AuditFilter::default();

        logger.export_events(temp_file.path(), filter).await.unwrap();

        let content = tokio::fs::read_to_string(temp_file.path()).await.unwrap();
        assert!(!content.is_empty());
    }
}