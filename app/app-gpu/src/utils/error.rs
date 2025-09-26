/*!
# Error Handling

**Structured error types** và **error handling utilities** cho App-GPU.

## Features

- **Type-safe error handling** với **thiserror**
- **Error context** với **anyhow** integration
- **GPU-specific errors** với detailed information
- **Structured error logging**

## Example

```rust
use app_gpu::utils::error::{AppError, Result};

fn gpu_operation() -> Result<()> {
    Err(AppError::GpuError {
        gpu_index: 0,
        message: "GPU memory allocation failed".to_string(),
        cuda_error_code: Some(2),
    })?
}
```
*/

use thiserror::Error;
use std::collections::HashMap;

/// **Application Result Type** (kiểu kết quả ứng dụng)
pub type Result<T> = std::result::Result<T, AppError>;

/// **Main Application Error Type** (kiểu lỗi ứng dụng chính)
#[derive(Error, Debug)]
pub enum AppError {
    /// **GPU-related errors** (lỗi liên quan GPU)
    #[error("GPU {gpu_index} error: {message}")]
    GpuError {
        gpu_index: usize,
        message: String,
        cuda_error_code: Option<u32>,
    },
    
    /// **Resource allocation errors** (lỗi cấp phát tài nguyên)
    #[error("Resource allocation error: {resource_type} - {message}")]
    ResourceError {
        resource_type: String,
        message: String,
        current_usage: Option<u64>,
        limit: Option<u64>,
    },
    
    /// **Event bus errors** (lỗi event bus)
    #[error("Event bus error: {operation} - {message}")]
    EventBusError {
        operation: String,
        message: String,
        subject: Option<String>,
    },
    
    /// **Stealth operation errors** (lỗi thao tác stealth)
    #[error("Stealth error: {operation} - {message}")]
    StealtHError {
        operation: String,
        message: String,
        pid: Option<u32>,
    },
    
    /// **Configuration errors** (lỗi cấu hình)
    #[error("Configuration error: {field} - {message}")]
    ConfigError {
        field: String,
        message: String,
        valid_values: Option<Vec<String>>,
    },
    
    /// **Network/NATS errors** (lỗi mạng/NATS)
    #[error("Network error: {operation} - {message}")]
    NetworkError {
        operation: String,
        message: String,
        endpoint: Option<String>,
    },
    
    /// **Security errors** (lỗi bảo mật)
    #[error("Security error: {context} - {message}")]
    SecurityError {
        context: String,
        message: String,
        severity: SecuritySeverity,
    },
    
    /// **Performance/timeout errors** (lỗi hiệu suất/timeout)
    #[error("Performance error: {operation} took {duration_ms}ms (limit: {limit_ms}ms)")]
    PerformanceError {
        operation: String,
        duration_ms: u64,
        limit_ms: u64,
    },
    
    /// **Worker pool errors** (lỗi worker pool)
    #[error("Worker error: {worker_type} - {message}")]
    WorkerError {
        worker_type: String,
        message: String,
        worker_id: Option<String>,
    },
    
    /// **Memory errors** (lỗi bộ nhớ)
    #[error("Memory error: {message}")]
    MemoryError {
        message: String,
        requested_bytes: Option<usize>,
        available_bytes: Option<usize>,
    },
    
    /// **I/O errors** (lỗi I/O)
    #[error("I/O error: {operation} - {message}")]
    IoError {
        operation: String,
        message: String,
        path: Option<String>,
    },
    
    /// **Generic errors** (lỗi tổng quát)
    #[error("Application error: {message}")]
    Generic {
        message: String,
        context: HashMap<String, String>,
    },
    
    /// **External errors** (lỗi từ bên ngoài)
    #[error("External error: {source}")]
    External {
        #[from]
        source: anyhow::Error,
    },
}

/// **Security Error Severity** (mức độ nghiêm trọng lỗi bảo mật)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum SecuritySeverity {
    Low,
    Medium,
    High,
    Critical,
}

impl AppError {
    /// **Create GPU error** (tạo lỗi GPU)
    pub fn gpu_error(gpu_index: usize, message: impl Into<String>) -> Self {
        Self::GpuError {
            gpu_index,
            message: message.into(),
            cuda_error_code: None,
        }
    }
    
    /// **Create GPU error with CUDA code** (tạo lỗi GPU với mã CUDA)
    pub fn gpu_error_with_code(
        gpu_index: usize,
        message: impl Into<String>,
        cuda_error_code: u32,
    ) -> Self {
        Self::GpuError {
            gpu_index,
            message: message.into(),
            cuda_error_code: Some(cuda_error_code),
        }
    }
    
    /// **Create resource error** (tạo lỗi tài nguyên)
    pub fn resource_error(
        resource_type: impl Into<String>,
        message: impl Into<String>,
    ) -> Self {
        Self::ResourceError {
            resource_type: resource_type.into(),
            message: message.into(),
            current_usage: None,
            limit: None,
        }
    }
    
    /// **Create resource limit error** (tạo lỗi giới hạn tài nguyên)
    pub fn resource_limit_error(
        resource_type: impl Into<String>,
        current_usage: u64,
        limit: u64,
    ) -> Self {
        Self::ResourceError {
            resource_type: resource_type.into(),
            message: format!("Resource limit exceeded: {} > {}", current_usage, limit),
            current_usage: Some(current_usage),
            limit: Some(limit),
        }
    }
    
    /// **Create event bus error** (tạo lỗi event bus)
    pub fn event_bus_error(
        operation: impl Into<String>,
        message: impl Into<String>,
    ) -> Self {
        Self::EventBusError {
            operation: operation.into(),
            message: message.into(),
            subject: None,
        }
    }
    
    /// **Create stealth error** (tạo lỗi stealth)
    pub fn stealth_error(
        operation: impl Into<String>,
        message: impl Into<String>,
    ) -> Self {
        Self::StealtHError {
            operation: operation.into(),
            message: message.into(),
            pid: None,
        }
    }
    
    /// **Create stealth error with PID** (tạo lỗi stealth với PID)
    pub fn stealth_error_with_pid(
        operation: impl Into<String>,
        message: impl Into<String>,
        pid: u32,
    ) -> Self {
        Self::StealtHError {
            operation: operation.into(),
            message: message.into(),
            pid: Some(pid),
        }
    }
    
    /// **Create configuration error** (tạo lỗi cấu hình)
    pub fn config_error(
        field: impl Into<String>,
        message: impl Into<String>,
    ) -> Self {
        Self::ConfigError {
            field: field.into(),
            message: message.into(),
            valid_values: None,
        }
    }
    
    /// **Create security error** (tạo lỗi bảo mật)
    pub fn security_error(
        context: impl Into<String>,
        message: impl Into<String>,
        severity: SecuritySeverity,
    ) -> Self {
        Self::SecurityError {
            context: context.into(),
            message: message.into(),
            severity,
        }
    }
    
    /// **Create performance error** (tạo lỗi hiệu suất)
    pub fn performance_error(
        operation: impl Into<String>,
        duration_ms: u64,
        limit_ms: u64,
    ) -> Self {
        Self::PerformanceError {
            operation: operation.into(),
            duration_ms,
            limit_ms,
        }
    }
    
    /// **Create worker error** (tạo lỗi worker)
    pub fn worker_error(
        worker_type: impl Into<String>,
        message: impl Into<String>,
    ) -> Self {
        Self::WorkerError {
            worker_type: worker_type.into(),
            message: message.into(),
            worker_id: None,
        }
    }
    
    /// **Create memory error** (tạo lỗi bộ nhớ)
    pub fn memory_error(message: impl Into<String>) -> Self {
        Self::MemoryError {
            message: message.into(),
            requested_bytes: None,
            available_bytes: None,
        }
    }
    
    /// **Create I/O error** (tạo lỗi I/O)
    pub fn io_error(
        operation: impl Into<String>,
        message: impl Into<String>,
    ) -> Self {
        Self::IoError {
            operation: operation.into(),
            message: message.into(),
            path: None,
        }
    }
    
    /// **Create generic error** (tạo lỗi tổng quát)
    pub fn generic(message: impl Into<String>) -> Self {
        Self::Generic {
            message: message.into(),
            context: HashMap::new(),
        }
    }
    
    /// **Add context to error** (thêm ngữ cảnh vào lỗi)
    pub fn with_context(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        match &mut self {
            Self::Generic { context, .. } => {
                context.insert(key.into(), value.into());
            }
            _ => {
                // Convert to generic error with context
                let message = self.to_string();
                let mut context = HashMap::new();
                context.insert(key.into(), value.into());
                return Self::Generic { message, context };
            }
        }
        self
    }
    
    /// **Get error category** (lấy danh mục lỗi)
    pub fn category(&self) -> &'static str {
        match self {
            Self::GpuError { .. } => "gpu",
            Self::ResourceError { .. } => "resource",
            Self::EventBusError { .. } => "event_bus",
            Self::StealtHError { .. } => "stealth",
            Self::ConfigError { .. } => "config",
            Self::NetworkError { .. } => "network",
            Self::SecurityError { .. } => "security",
            Self::PerformanceError { .. } => "performance",
            Self::WorkerError { .. } => "worker",
            Self::MemoryError { .. } => "memory",
            Self::IoError { .. } => "io",
            Self::Generic { .. } => "generic",
            Self::External { .. } => "external",
        }
    }
    
    /// **Check if error is recoverable** (kiểm tra lỗi có thể khôi phục)
    pub fn is_recoverable(&self) -> bool {
        match self {
            Self::GpuError { .. } => false, // GPU errors usually require restart
            Self::ResourceError { .. } => true, // Resource errors can be recovered
            Self::EventBusError { .. } => true, // Network issues can recover
            Self::StealtHError { .. } => true, // Stealth operations can be retried
            Self::ConfigError { .. } => false, // Config errors need fix
            Self::NetworkError { .. } => true, // Network can recover
            Self::SecurityError { severity, .. } => {
                !matches!(severity, SecuritySeverity::Critical)
            }
            Self::PerformanceError { .. } => true, // Performance can improve
            Self::WorkerError { .. } => true, // Workers can be restarted
            Self::MemoryError { .. } => false, // Memory errors are serious
            Self::IoError { .. } => true, // I/O can be retried
            Self::Generic { .. } => true, // Assume recoverable
            Self::External { .. } => true, // Depends on external error
        }
    }
    
    /// **Get retry delay suggestion** (lấy gợi ý độ trễ retry)
    pub fn retry_delay(&self) -> Option<std::time::Duration> {
        if !self.is_recoverable() {
            return None;
        }
        
        Some(match self {
            Self::ResourceError { .. } => std::time::Duration::from_millis(500),
            Self::EventBusError { .. } => std::time::Duration::from_millis(1000),
            Self::NetworkError { .. } => std::time::Duration::from_millis(2000),
            Self::PerformanceError { .. } => std::time::Duration::from_millis(100),
            Self::WorkerError { .. } => std::time::Duration::from_millis(1000),
            _ => std::time::Duration::from_millis(500),
        })
    }
}

/// **Error logging helper** (helper ghi log lỗi)
pub fn log_error(error: &AppError) {
    use tracing::{error, warn, info};
    
    let severity = match error.category() {
        "security" => if let AppError::SecurityError { severity, .. } = error {
            match severity {
                SecuritySeverity::Critical => "critical",
                SecuritySeverity::High => "high", 
                SecuritySeverity::Medium => "medium",
                SecuritySeverity::Low => "low",
            }
        } else {
            "unknown"
        },
        _ => "normal",
    };
    
    match error {
        AppError::SecurityError { severity: SecuritySeverity::Critical, .. } |
        AppError::GpuError { .. } |
        AppError::MemoryError { .. } => {
            error!(
                error_category = error.category(),
                error_message = %error,
                severity = severity,
                recoverable = error.is_recoverable(),
                "Critical error occurred"
            );
        }
        
        AppError::PerformanceError { .. } => {
            warn!(
                error_category = error.category(),
                error_message = %error,
                severity = severity,
                recoverable = error.is_recoverable(),
                "Performance issue detected"
            );
        }
        
        _ => {
            info!(
                error_category = error.category(),
                error_message = %error,
                severity = severity,
                recoverable = error.is_recoverable(),
                "Application error"
            );
        }
    }
}

// Implement conversions for common error types

impl From<std::io::Error> for AppError {
    fn from(err: std::io::Error) -> Self {
        Self::IoError {
            operation: "io_operation".to_string(),
            message: err.to_string(),
            path: None,
        }
    }
}

impl From<serde_json::Error> for AppError {
    fn from(err: serde_json::Error) -> Self {
        Self::Generic {
            message: format!("JSON error: {}", err),
            context: HashMap::new(),
        }
    }
}

impl From<bincode::Error> for AppError {
    fn from(err: bincode::Error) -> Self {
        Self::Generic {
            message: format!("Bincode error: {}", err),
            context: HashMap::new(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gpu_error_creation() {
        let error = AppError::gpu_error(0, "Memory allocation failed");
        
        assert_eq!(error.category(), "gpu");
        assert!(!error.is_recoverable());
        assert!(error.retry_delay().is_none());
        assert!(error.to_string().contains("GPU 0 error"));
    }
    
    #[test]
    fn test_resource_error_with_limits() {
        let error = AppError::resource_limit_error("memory", 1000, 800);
        
        assert_eq!(error.category(), "resource");
        assert!(error.is_recoverable());
        assert!(error.retry_delay().is_some());
    }
    
    #[test]
    fn test_security_error_severity() {
        let critical_error = AppError::security_error(
            "authentication",
            "Invalid credentials",
            SecuritySeverity::Critical,
        );
        
        assert_eq!(critical_error.category(), "security");
        assert!(!critical_error.is_recoverable());
        
        let low_error = AppError::security_error(
            "rate_limit",
            "Rate limit exceeded",
            SecuritySeverity::Low,
        );
        
        assert!(low_error.is_recoverable());
    }
    
    #[test]
    fn test_error_context() {
        let error = AppError::generic("Something went wrong")
            .with_context("component", "gpu_engine")
            .with_context("gpu_index", "0");
        
        if let AppError::Generic { context, .. } = error {
            assert_eq!(context.get("component").unwrap(), "gpu_engine");
            assert_eq!(context.get("gpu_index").unwrap(), "0");
        } else {
            panic!("Expected Generic error");
        }
    }
}
