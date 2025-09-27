//! Logging Infrastructure Module
//! 
//! Structured logging với tracing, rotation và compression

use std::path::PathBuf;
use anyhow::Result;
use tracing::{Level, Subscriber};
use tracing_subscriber::{
    fmt::{self, format::FmtSpan},
    layer::SubscriberExt,
    registry::LookupSpan,
    util::SubscriberInitExt,
    EnvFilter, Layer,
};
use tracing_appender::{non_blocking, rolling};

/// Logging configuration
#[derive(Debug, Clone)]
pub struct LogConfig {
    /// Log level (trace, debug, info, warn, error)
    pub level: String,
    
    /// Log to console
    pub console: bool,
    
    /// Log to file
    pub file: bool,
    
    /// Log directory
    pub log_dir: PathBuf,
    
    /// Log file prefix
    pub file_prefix: String,
    
    /// Enable JSON format
    pub json: bool,
    
    /// Include file/line info
    pub with_file: bool,
    
    /// Include thread info
    pub with_thread: bool,
    
    /// Include target info
    pub with_target: bool,
    
    /// Include span events
    pub with_spans: bool,
}

impl Default for LogConfig {
    fn default() -> Self {
        Self {
            level: "info".to_string(),
            console: true,
            file: true,
            log_dir: PathBuf::from("./logs"),
            file_prefix: "opus-gpu".to_string(),
            json: false,
            with_file: true,
            with_thread: true,
            with_target: true,
            with_spans: true,
        }
    }
}

/// Initialize logging system
pub fn init_logging(config: &LogConfig) -> Result<()> {
    // Ensure log directory exists
    if config.file {
        std::fs::create_dir_all(&config.log_dir)?;
    }
    
    // Create environment filter
    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(&config.level));
    
    // Create registry
    let subscriber = tracing_subscriber::registry().with(env_filter);
    
    // Add console layer if enabled
    let subscriber = if config.console {
        let console_layer = create_console_layer(config);
        subscriber.with(console_layer)
    } else {
        subscriber
    };
    
    // Add file layer if enabled
    if config.file {
        let (file_layer, _guard) = create_file_layer(config)?;
        
        // Store guard to keep file writer alive
        // In production, store this guard somewhere to prevent dropping
        Box::leak(Box::new(_guard));
        
        subscriber.with(file_layer).init();
    } else {
        subscriber.init();
    }
    
    // Setup panic handler
    crate::error::setup_panic_handler();
    
    tracing::info!("🚀 Logging initialized with level: {}", config.level);
    
    Ok(())
}

/// Create console logging layer
fn create_console_layer<S>(config: &LogConfig) -> impl Layer<S>
where
    S: Subscriber + for<'a> LookupSpan<'a>,
{
    let format = fmt::format()
        .with_level(true)
        .with_target(config.with_target)
        .with_thread_ids(config.with_thread)
        .with_thread_names(config.with_thread)
        .with_file(config.with_file)
        .with_line_number(config.with_file)
        .with_ansi(true)
        .pretty();
    
    let span_events = if config.with_spans {
        FmtSpan::ENTER | FmtSpan::EXIT | FmtSpan::CLOSE
    } else {
        FmtSpan::NONE
    };
    
    fmt::layer()
        .event_format(format)
        .with_span_events(span_events)
        .with_writer(std::io::stdout)
}

/// Create file logging layer với rotation
fn create_file_layer<S>(
    config: &LogConfig,
) -> Result<(impl Layer<S>, non_blocking::WorkerGuard)>
where
    S: Subscriber + for<'a> LookupSpan<'a>,
{
    // Setup rolling file appender (daily rotation)
    let file_appender = rolling::daily(&config.log_dir, &config.file_prefix);
    let (non_blocking, guard) = non_blocking(file_appender);
    
    let layer = if config.json {
        // JSON format for structured logging
        fmt::layer()
            .json()
            .with_file(config.with_file)
            .with_line_number(config.with_file)
            .with_thread_ids(config.with_thread)
            .with_thread_names(config.with_thread)
            .with_target(config.with_target)
            .with_current_span(true)
            .with_span_list(config.with_spans)
            .with_writer(non_blocking)
    } else {
        // Human-readable format
        fmt::layer()
            .with_file(config.with_file)
            .with_line_number(config.with_file)
            .with_thread_ids(config.with_thread)
            .with_thread_names(config.with_thread)
            .with_target(config.with_target)
            .with_ansi(false)
            .with_writer(non_blocking)
    };
    
    Ok((layer, guard))
}

/// Performance profiling macros
#[macro_export]
macro_rules! profile {
    ($name:expr) => {
        let _guard = $crate::logging::ProfileGuard::new($name);
    };
}

#[macro_export]
macro_rules! profile_fn {
    () => {
        let _guard = $crate::logging::ProfileGuard::new(
            &format!("{}::{}", module_path!(), std::any::type_name_of_val(&()))
        );
    };
}

/// Profile guard for automatic timing
pub struct ProfileGuard {
    name: String,
    start: std::time::Instant,
}

impl ProfileGuard {
    pub fn new(name: impl Into<String>) -> Self {
        let name = name.into();
        tracing::debug!(target: "profile", ">> Entering {}", name);
        Self {
            name,
            start: std::time::Instant::now(),
        }
    }
}

impl Drop for ProfileGuard {
    fn drop(&mut self) {
        let elapsed = self.start.elapsed();
        tracing::debug!(
            target: "profile",
            "<< Exiting {} (took {:?})",
            self.name,
            elapsed
        );
        
        // Report to metrics if > threshold
        if elapsed.as_millis() > 100 {
            tracing::warn!(
                target: "performance",
                function = %self.name,
                duration_ms = elapsed.as_millis(),
                "Slow function detected"
            );
        }
    }
}

/// Log rotation manager
pub struct LogRotationManager {
    config: LogConfig,
    max_size_mb: usize,
    max_files: usize,
    compress: bool,
}

impl LogRotationManager {
    pub fn new(config: LogConfig) -> Self {
        Self {
            config,
            max_size_mb: 100,
            max_files: 10,
            compress: true,
        }
    }
    
    /// Check và rotate logs if needed
    pub async fn check_rotation(&self) -> Result<()> {
        let log_files = self.list_log_files()?;
        
        for file in log_files {
            let metadata = std::fs::metadata(&file)?;
            let size_mb = metadata.len() / 1024 / 1024;
            
            if size_mb > self.max_size_mb as u64 {
                self.rotate_file(&file)?;
            }
        }
        
        self.cleanup_old_files()?;
        
        Ok(())
    }
    
    /// List all log files
    fn list_log_files(&self) -> Result<Vec<PathBuf>> {
        let mut files = Vec::new();
        
        for entry in std::fs::read_dir(&self.config.log_dir)? {
            let entry = entry?;
            let path = entry.path();
            
            if path.is_file() {
                if let Some(name) = path.file_name() {
                    if name.to_string_lossy().starts_with(&self.config.file_prefix) {
                        files.push(path);
                    }
                }
            }
        }
        
        Ok(files)
    }
    
    /// Rotate log file
    fn rotate_file(&self, file: &PathBuf) -> Result<()> {
        let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
        let rotated_name = format!(
            "{}.{}.log",
            self.config.file_prefix,
            timestamp
        );
        let rotated_path = self.config.log_dir.join(&rotated_name);
        
        std::fs::rename(file, &rotated_path)?;
        
        if self.compress {
            self.compress_file(&rotated_path)?;
        }
        
        tracing::info!("Rotated log file to {:?}", rotated_path);
        
        Ok(())
    }
    
    /// Compress log file using gzip
    fn compress_file(&self, file: &PathBuf) -> Result<()> {
        use flate2::write::GzEncoder;
        use flate2::Compression;
        use std::fs::File;
        use std::io::{BufReader, BufWriter, copy};
        
        let input = File::open(file)?;
        let mut reader = BufReader::new(input);
        
        let output_path = file.with_extension("log.gz");
        let output = File::create(&output_path)?;
        let writer = BufWriter::new(output);
        let mut encoder = GzEncoder::new(writer, Compression::default());
        
        copy(&mut reader, &mut encoder)?;
        encoder.finish()?;
        
        // Remove original file
        std::fs::remove_file(file)?;
        
        tracing::debug!("Compressed log file to {:?}", output_path);
        
        Ok(())
    }
    
    /// Cleanup old log files
    fn cleanup_old_files(&self) -> Result<()> {
        let mut files = self.list_log_files()?;
        
        if files.len() <= self.max_files {
            return Ok(());
        }
        
        // Sort by modified time
        files.sort_by_key(|f| {
            std::fs::metadata(f)
                .and_then(|m| m.modified())
                .unwrap_or(std::time::SystemTime::UNIX_EPOCH)
        });
        
        // Remove oldest files
        let to_remove = files.len() - self.max_files;
        for file in files.iter().take(to_remove) {
            std::fs::remove_file(file)?;
            tracing::info!("Removed old log file: {:?}", file);
        }
        
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;
    
    #[test]
    fn test_log_config_default() {
        let config = LogConfig::default();
        assert_eq!(config.level, "info");
        assert!(config.console);
        assert!(config.file);
    }
    
    #[test]
    fn test_init_logging() {
        let temp = tempdir().unwrap();
        let mut config = LogConfig::default();
        config.log_dir = temp.path().to_owned();
        config.file = false; // Disable file logging for test
        
        init_logging(&config).unwrap();
        
        // Test logging works
        tracing::info!("Test log message");
        tracing::debug!("Debug message");
    }
    
    #[test]
    fn test_profile_guard() {
        let _guard = ProfileGuard::new("test_function");
        std::thread::sleep(std::time::Duration::from_millis(10));
        // Guard will log on drop
    }
}
