//! Error Handling Module
//! 
//! Custom error types và error recovery mechanisms

use std::fmt;
use thiserror::Error;

/// Main error type cho OPUS-GPU
#[derive(Error, Debug)]
pub enum OpusError {
    /// Configuration errors
    #[error("Configuration error: {0}")]
    Config(String),
    
    /// Plugin-related errors
    #[error("Plugin error: {0}")]
    Plugin(String),
    
    /// IPC errors
    #[error("IPC error: {0}")]
    Ipc(String),
    
    /// GPU-related errors
    #[error("GPU error: {0}")]
    Gpu(String),
    
    /// Runtime errors
    #[error("Runtime error: {0}")]
    Runtime(String),
    
    /// IO errors
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    
    /// Serialization errors
    #[error("Serialization error: {0}")]
    Serialization(String),
    
    /// Resource exhaustion
    #[error("Resource exhausted: {0}")]
    ResourceExhausted(String),
    
    /// Permission denied
    #[error("Permission denied: {0}")]
    PermissionDenied(String),
    
    /// Timeout
    #[error("Operation timed out: {0}")]
    Timeout(String),
    
    /// Not found
    #[error("Not found: {0}")]
    NotFound(String),
    
    /// Already exists
    #[error("Already exists: {0}")]
    AlreadyExists(String),
    
    /// Invalid input
    #[error("Invalid input: {0}")]
    InvalidInput(String),
    
    /// Internal error
    #[error("Internal error: {0}")]
    Internal(String),
    
    /// Unknown error
    #[error("Unknown error: {0}")]
    Unknown(String),
}

/// Error severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ErrorSeverity {
    /// Thông tin - không phải lỗi thực sự
    Info,
    /// Cảnh báo - có thể tiếp tục
    Warning,
    /// Lỗi - cần xử lý
    Error,
    /// Critical - cần dừng ngay
    Critical,
    /// Fatal - không thể phục hồi
    Fatal,
}

/// Error context với additional metadata
#[derive(Debug)]
pub struct ErrorContext {
    pub error: OpusError,
    pub severity: ErrorSeverity,
    pub component: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub backtrace: Option<std::backtrace::Backtrace>,
    pub metadata: std::collections::HashMap<String, String>,
}

impl ErrorContext {
    /// Create new error context
    pub fn new(error: OpusError, severity: ErrorSeverity, component: impl Into<String>) -> Self {
        Self {
            error,
            severity,
            component: component.into(),
            timestamp: chrono::Utc::now(),
            backtrace: Some(std::backtrace::Backtrace::capture()),
            metadata: std::collections::HashMap::new(),
        }
    }
    
    /// Add metadata
    pub fn with_metadata(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.metadata.insert(key.into(), value.into());
        self
    }
    
    /// Check if error is recoverable
    pub fn is_recoverable(&self) -> bool {
        matches!(self.severity, ErrorSeverity::Info | ErrorSeverity::Warning | ErrorSeverity::Error)
    }
    
    /// Check if error is critical
    pub fn is_critical(&self) -> bool {
        matches!(self.severity, ErrorSeverity::Critical | ErrorSeverity::Fatal)
    }
}

/// Error recovery strategy
#[derive(Debug, Clone)]
pub enum RecoveryStrategy {
    /// Retry với backoff
    Retry {
        max_attempts: u32,
        backoff_ms: u64,
    },
    /// Skip và tiếp tục
    Skip,
    /// Fallback to alternative
    Fallback(String),
    /// Restart component
    Restart,
    /// Shutdown gracefully
    Shutdown,
    /// Escalate to higher level
    Escalate,
    /// No recovery possible
    None,
}

/// Error handler trait
pub trait ErrorHandler: Send + Sync {
    /// Handle error và return recovery strategy
    fn handle(&self, context: &ErrorContext) -> RecoveryStrategy;
    
    /// Log error
    fn log(&self, context: &ErrorContext);
    
    /// Report error to monitoring
    fn report(&self, context: &ErrorContext);
}

/// Default error handler
pub struct DefaultErrorHandler;

impl ErrorHandler for DefaultErrorHandler {
    fn handle(&self, context: &ErrorContext) -> RecoveryStrategy {
        match context.severity {
            ErrorSeverity::Info | ErrorSeverity::Warning => RecoveryStrategy::Skip,
            ErrorSeverity::Error => RecoveryStrategy::Retry {
                max_attempts: 3,
                backoff_ms: 1000,
            },
            ErrorSeverity::Critical => RecoveryStrategy::Restart,
            ErrorSeverity::Fatal => RecoveryStrategy::Shutdown,
        }
    }
    
    fn log(&self, context: &ErrorContext) {
        use tracing::{info, warn, error};
        
        let msg = format!(
            "[{}] {}: {}",
            context.component,
            context.severity,
            context.error
        );
        
        match context.severity {
            ErrorSeverity::Info => info!("{}", msg),
            ErrorSeverity::Warning => warn!("{}", msg),
            ErrorSeverity::Error => error!("{}", msg),
            ErrorSeverity::Critical => error!("CRITICAL: {}", msg),
            ErrorSeverity::Fatal => error!("FATAL: {}", msg),
        }
        
        // Log backtrace if available và severity >= Error
        if context.severity >= ErrorSeverity::Error {
            if let Some(bt) = &context.backtrace {
                error!("Backtrace:\n{}", bt);
            }
        }
    }
    
    fn report(&self, context: &ErrorContext) {
        // Report to monitoring system
        // This would integrate with Prometheus/OpenTelemetry
        
        if context.is_critical() {
            // Send alert
            tracing::error!(
                target: "alerts",
                component = %context.component,
                severity = ?context.severity,
                error = %context.error,
                "Critical error detected"
            );
        }
    }
}

impl fmt::Display for ErrorSeverity {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ErrorSeverity::Info => write!(f, "INFO"),
            ErrorSeverity::Warning => write!(f, "WARN"),
            ErrorSeverity::Error => write!(f, "ERROR"),
            ErrorSeverity::Critical => write!(f, "CRITICAL"),
            ErrorSeverity::Fatal => write!(f, "FATAL"),
        }
    }
}

/// Result type alias
pub type OpusResult<T> = Result<T, OpusError>;

/// Panic handler setup
pub fn setup_panic_handler() {
    use std::panic;
    use tracing::error;
    
    panic::set_hook(Box::new(|panic_info| {
        let location = panic_info.location()
            .map(|l| format!("{}:{}:{}", l.file(), l.line(), l.column()))
            .unwrap_or_else(|| "unknown".to_string());
        
        let msg = if let Some(s) = panic_info.payload().downcast_ref::<&str>() {
            s.to_string()
        } else if let Some(s) = panic_info.payload().downcast_ref::<String>() {
            s.clone()
        } else {
            "Unknown panic payload".to_string()
        };
        
        error!(
            target: "panic",
            location = %location,
            message = %msg,
            "PANIC DETECTED"
        );
        
        // Print backtrace
        let bt = std::backtrace::Backtrace::force_capture();
        error!("Panic backtrace:\n{}", bt);
        
        // In production, could send alert hoặc trigger recovery
    }));
}

/// Macro để wrap function với error context
#[macro_export]
macro_rules! with_error_context {
    ($component:expr, $expr:expr) => {{
        match $expr {
            Ok(val) => Ok(val),
            Err(e) => {
                let context = $crate::error::ErrorContext::new(
                    e.into(),
                    $crate::error::ErrorSeverity::Error,
                    $component,
                );
                
                let handler = $crate::error::DefaultErrorHandler;
                handler.log(&context);
                handler.report(&context);
                
                Err(context.error)
            }
        }
    }};
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_error_context() {
        let error = OpusError::Config("Invalid value".to_string());
        let context = ErrorContext::new(error, ErrorSeverity::Warning, "test");
        
        assert!(context.is_recoverable());
        assert!(!context.is_critical());
    }
    
    #[test]
    fn test_recovery_strategy() {
        let handler = DefaultErrorHandler;
        
        let error = OpusError::Runtime("Test error".to_string());
        let context = ErrorContext::new(error, ErrorSeverity::Error, "test");
        
        match handler.handle(&context) {
            RecoveryStrategy::Retry { max_attempts, .. } => {
                assert_eq!(max_attempts, 3);
            }
            _ => panic!("Expected Retry strategy"),
        }
    }
}
