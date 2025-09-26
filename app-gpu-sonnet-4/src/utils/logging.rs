/*!
# Structured Logging

**High-performance structured logging** với **tracing** crate.
Supports **JSON output**, **filtering**, và **distributed tracing**.

## Features

- **Structured logging** với **key-value pairs**
- **JSON output** cho **log aggregation**
- **Environment-based filtering** (LOG_LEVEL)
- **OpenTelemetry integration** (optional)
- **High-performance** với **minimal allocations**

## Example

```rust
use tracing::{info, error, instrument};
use app_gpu::utils::logging::init_logging;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_logging("info")?;
    
    info!("Application started");
    
    // Structured logging
    info!(
        gpu_count = 2,
        memory_mb = 8192,
        "GPU initialization complete"
    );
    
    Ok(())
}

#[instrument(skip(data))]
async fn process_data(id: u32, data: &[u8]) {
    info!(data_len = data.len(), "Processing data");
}
```
*/

use anyhow::{Context, Result};
use tracing::{info, Level};
use tracing_subscriber::{
    fmt,
    layer::SubscriberExt,
    util::SubscriberInitExt,
    EnvFilter,
};

/// **Initialize structured logging** (khởi tạo structured logging)
/// 
/// Sets up **tracing-subscriber** với:
/// - **Environment filter** từ LOG_LEVEL hoặc tham số
/// - **JSON formatting** cho production
/// - **Human-readable** formatting cho development
/// 
/// # Arguments
/// 
/// * `log_level` - Log level string ("trace", "debug", "info", "warn", "error")
pub fn init_logging(log_level: &str) -> Result<()> {
    // Parse log level
    let level = parse_log_level(log_level)
        .with_context(|| format!("Invalid log level: {}", log_level))?;
    
    // Create environment filter
    let env_filter = EnvFilter::from_default_env()
        .add_directive(level.into())
        .add_directive("async_nats=warn".parse()?) // Reduce NATS noise
        .add_directive("cudarc=info".parse()?)     // Reduce CUDA noise
        .add_directive("hyper=warn".parse()?)     // Reduce HTTP noise
        .add_directive("h2=warn".parse()?)        // Reduce HTTP/2 noise
        .add_directive("tower=warn".parse()?)     // Reduce tower noise
        .add_directive("tokio=warn".parse()?);    // Reduce tokio noise
    
    // Determine output format based on environment
    let use_json = std::env::var("LOG_FORMAT").unwrap_or_default() == "json"
        || std::env::var("ENVIRONMENT").unwrap_or_default() == "production";
    
    if use_json {
        // JSON output for production/log aggregation
        tracing_subscriber::registry()
            .with(env_filter)
            .with(
                fmt::layer()
                    .json()
                    .with_current_span(true)
                    .with_span_list(true)
                    .with_target(true)
                    .with_thread_ids(true)
                    .with_thread_names(true)
                    .with_file(true)
                    .with_line_number(true)
            )
            .init();
    } else {
        // Human-readable output for development
        tracing_subscriber::registry()
            .with(env_filter)
            .with(
                fmt::layer()
                    .pretty()
                    .with_target(true)
                    .with_thread_ids(false)
                    .with_thread_names(true)
                    .with_file(true)
                    .with_line_number(true)
                    .with_ansi(true)
            )
            .init();
    }
    
    info!(
        log_level = log_level,
        format = if use_json { "json" } else { "pretty" },
        "Logging initialized"
    );
    
    Ok(())
}

/// **Parse log level string** (phân tích chuỗi log level)
fn parse_log_level(level_str: &str) -> Result<Level> {
    match level_str.to_lowercase().as_str() {
        "trace" => Ok(Level::TRACE),
        "debug" => Ok(Level::DEBUG),
        "info" => Ok(Level::INFO),
        "warn" | "warning" => Ok(Level::WARN),
        "error" => Ok(Level::ERROR),
        _ => anyhow::bail!("Invalid log level: {}. Valid levels: trace, debug, info, warn, error", level_str),
    }
}

/// **Performance-optimized logging macros** (macro logging tối ưu hiệu suất)
/// 
/// These macros provide **zero-cost** logging when the level is disabled.
#[macro_export]
macro_rules! log_performance {
    ($level:expr, $($arg:tt)*) => {
        if tracing::enabled!($level) {
            tracing::event!($level, $($arg)*);
        }
    };
}

/// **GPU-specific logging helper** (helper logging riêng cho GPU)
#[macro_export]
macro_rules! log_gpu {
    ($level:expr, $gpu_index:expr, $($arg:tt)*) => {
        tracing::event!(
            $level,
            gpu_index = $gpu_index,
            component = "gpu",
            $($arg)*
        );
    };
}

/// **Resource-specific logging helper** (helper logging riêng cho tài nguyên)
#[macro_export]
macro_rules! log_resource {
    ($level:expr, $resource_type:expr, $($arg:tt)*) => {
        tracing::event!(
            $level,
            resource_type = $resource_type,
            component = "resource",
            $($arg)*
        );
    };
}

/// **Stealth-specific logging helper** (helper logging riêng cho stealth)
#[macro_export]
macro_rules! log_stealth {
    ($level:expr, $operation:expr, $($arg:tt)*) => {
        tracing::event!(
            $level,
            operation = $operation,
            component = "stealth",
            $($arg)*
        );
    };
}

/// **Event-specific logging helper** (helper logging riêng cho event)
#[macro_export]
macro_rules! log_event {
    ($level:expr, $event_type:expr, $subject:expr, $($arg:tt)*) => {
        tracing::event!(
            $level,
            event_type = $event_type,
            subject = $subject,
            component = "event_bus",
            $($arg)*
        );
    };
}

/// **Timing helper for performance measurement** (helper đo thời gian cho đo hiệu suất)
pub struct Timer {
    start: std::time::Instant,
    name: String,
}

impl Timer {
    /// **Start new timer** (bắt đầu timer mới)
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            start: std::time::Instant::now(),
            name: name.into(),
        }
    }
    
    /// **Get elapsed time** (lấy thời gian đã trôi qua)
    pub fn elapsed(&self) -> std::time::Duration {
        self.start.elapsed()
    }
    
    /// **Finish timer and log result** (kết thúc timer và log kết quả)
    pub fn finish(self) {
        let duration = self.elapsed();
        tracing::info!(
            timer = self.name,
            duration_ms = duration.as_millis(),
            duration_us = duration.as_micros(),
            "Timer finished"
        );
    }
    
    /// **Finish timer with custom level** (kết thúc timer với level tùy chỉnh)
    pub fn finish_with_level(self, level: Level) {
        let duration = self.elapsed();
        tracing::event!(
            level,
            timer = self.name,
            duration_ms = duration.as_millis(),
            duration_us = duration.as_micros(),
            "Timer finished"
        );
    }
}

/// **Memory usage helper** (helper sử dụng bộ nhớ)
pub fn log_memory_usage(component: &str) {
    #[cfg(target_os = "linux")]
    {
        if let Ok(status) = std::fs::read_to_string("/proc/self/status") {
            for line in status.lines() {
                if line.starts_with("VmRSS:") || line.starts_with("VmSize:") {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.len() >= 3 {
                        let metric_name = match parts[0] {
                            "VmRSS:" => "memory_rss_kb",
                            "VmSize:" => "memory_vsize_kb",
                            _ => continue,
                        };
                        
                        if let Ok(value) = parts[1].parse::<u64>() {
                            tracing::info!(
                                component = component,
                                "{}" = value,
                                "Memory usage"
                            );
                        }
                    }
                }
            }
        }
    }
    
    #[cfg(not(target_os = "linux"))]
    {
        tracing::debug!(
            component = component,
            "Memory usage logging not implemented for this platform"
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tracing::Level;

    #[test]
    fn test_parse_log_level() {
        assert_eq!(parse_log_level("trace").unwrap(), Level::TRACE);
        assert_eq!(parse_log_level("DEBUG").unwrap(), Level::DEBUG);
        assert_eq!(parse_log_level("Info").unwrap(), Level::INFO);
        assert_eq!(parse_log_level("warn").unwrap(), Level::WARN);
        assert_eq!(parse_log_level("ERROR").unwrap(), Level::ERROR);
        
        assert!(parse_log_level("invalid").is_err());
    }
    
    #[test]
    fn test_timer() {
        let timer = Timer::new("test_operation");
        std::thread::sleep(std::time::Duration::from_millis(10));
        let elapsed = timer.elapsed();
        
        assert!(elapsed.as_millis() >= 10);
        assert!(elapsed.as_millis() < 100); // Should be reasonable
    }
    
    #[test]
    fn test_memory_usage() {
        // This test just ensures the function doesn't panic
        log_memory_usage("test_component");
    }
}
