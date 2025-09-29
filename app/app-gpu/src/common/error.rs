//! Error types and handling for OPUS-GPU
//!
//! Comprehensive error management with structured error types
//! for different subsystems and failure modes.

use std::fmt;
use thiserror::Error;

/// Main error type for OPUS-GPU operations
#[derive(Error, Debug)]
pub enum OpusError {
    /// GPU-related errors
    #[error("GPU error: {message}")]
    Gpu { message: String, device_id: Option<u32> },

    /// CUDA runtime errors
    #[error("CUDA error: {message} (code: {code})")]
    Cuda { message: String, code: i32 },

    /// Memory allocation errors
    #[error("Memory allocation failed: {message}")]
    Memory { message: String, requested: usize },

    /// Resource management errors
    #[error("Resource error: {message}")]
    Resource { message: String, resource_type: String },

    /// Security and authentication errors
    #[error("Security error: {message}")]
    Security { message: String },

    /// Network communication errors
    #[error("Network error: {message}")]
    Network { message: String },

    /// Configuration errors
    #[error("Configuration error: {message}")]
    Config { message: String },

    /// Thermal management errors
    #[error("Thermal error: temperature {temp}°C exceeds limit {limit}°C")]
    Thermal { temp: f32, limit: f32 },

    /// Cloaking/stealth errors
    #[error("Cloaking error: {message}")]
    Cloaking { message: String },

    /// I/O errors
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// Serialization errors
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// General system errors
    #[error("System error: {message}")]
    System { message: String },
}

/// Result type alias for OPUS-GPU operations
pub type OpusResult<T> = Result<T, OpusError>;

/// Error severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorSeverity {
    /// Low severity - informational
    Low,
    /// Medium severity - warning
    Medium,
    /// High severity - error that affects operation
    High,
    /// Critical severity - system failure
    Critical,
}

impl OpusError {
    /// Get the severity level of this error
    pub fn severity(&self) -> ErrorSeverity {
        match self {
            OpusError::Gpu { .. } => ErrorSeverity::High,
            OpusError::Cuda { .. } => ErrorSeverity::High,
            OpusError::Memory { .. } => ErrorSeverity::Critical,
            OpusError::Resource { .. } => ErrorSeverity::Medium,
            OpusError::Security { .. } => ErrorSeverity::Critical,
            OpusError::Network { .. } => ErrorSeverity::Medium,
            OpusError::Config { .. } => ErrorSeverity::High,
            OpusError::Thermal { temp, limit } => {
                if temp - limit > 10.0 {
                    ErrorSeverity::Critical
                } else {
                    ErrorSeverity::High
                }
            }
            OpusError::Cloaking { .. } => ErrorSeverity::Medium,
            OpusError::Io(_) => ErrorSeverity::Medium,
            OpusError::Serialization(_) => ErrorSeverity::Low,
            OpusError::System { .. } => ErrorSeverity::High,
        }
    }

    /// Check if this error is recoverable
    pub fn is_recoverable(&self) -> bool {
        match self {
            OpusError::Memory { .. } => false,
            OpusError::Security { .. } => false,
            OpusError::Thermal { temp, limit } => temp - limit < 15.0,
            OpusError::Cuda { code, .. } => *code != -1, // Generic CUDA errors might be recoverable
            _ => true,
        }
    }

    /// Get error code for programmatic handling
    pub fn error_code(&self) -> u32 {
        match self {
            OpusError::Gpu { .. } => 1001,
            OpusError::Cuda { .. } => 1002,
            OpusError::Memory { .. } => 1003,
            OpusError::Resource { .. } => 1004,
            OpusError::Security { .. } => 1005,
            OpusError::Network { .. } => 1006,
            OpusError::Config { .. } => 1007,
            OpusError::Thermal { .. } => 1008,
            OpusError::Cloaking { .. } => 1009,
            OpusError::Io(_) => 2001,
            OpusError::Serialization(_) => 2002,
            OpusError::System { .. } => 9999,
        }
    }
}

/// GPU-specific error constructors
impl OpusError {
    /// Create a GPU error with device ID
    pub fn gpu_error(message: impl Into<String>, device_id: Option<u32>) -> Self {
        Self::Gpu {
            message: message.into(),
            device_id,
        }
    }

    /// Create a CUDA error with error code
    pub fn cuda_error(message: impl Into<String>, code: i32) -> Self {
        Self::Cuda {
            message: message.into(),
            code,
        }
    }

    /// Create a memory allocation error
    pub fn memory_error(message: impl Into<String>, requested: usize) -> Self {
        Self::Memory {
            message: message.into(),
            requested,
        }
    }

    /// Create a resource management error
    pub fn resource_error(message: impl Into<String>, resource_type: impl Into<String>) -> Self {
        Self::Resource {
            message: message.into(),
            resource_type: resource_type.into(),
        }
    }

    /// Create a security error
    pub fn security_error(message: impl Into<String>) -> Self {
        Self::Security {
            message: message.into(),
        }
    }

    /// Create a thermal error
    pub fn thermal_error(temp: f32, limit: f32) -> Self {
        Self::Thermal { temp, limit }
    }
}

/// Error context for better debugging
#[derive(Debug, Clone)]
pub struct ErrorContext {
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub thread_id: String,
    pub component: String,
    pub operation: String,
    pub additional_info: Option<String>,
}

impl ErrorContext {
    /// Create new error context
    pub fn new(component: impl Into<String>, operation: impl Into<String>) -> Self {
        Self {
            timestamp: chrono::Utc::now(),
            thread_id: format!("{:?}", std::thread::current().id()),
            component: component.into(),
            operation: operation.into(),
            additional_info: None,
        }
    }

    /// Add additional information to context
    pub fn with_info(mut self, info: impl Into<String>) -> Self {
        self.additional_info = Some(info.into());
        self
    }
}

/// Trait for adding context to errors
pub trait ErrorExt<T> {
    /// Add context to error
    fn with_context(self, context: ErrorContext) -> Result<T, (OpusError, ErrorContext)>;
}

impl<T> ErrorExt<T> for OpusResult<T> {
    fn with_context(self, context: ErrorContext) -> Result<T, (OpusError, ErrorContext)> {
        self.map_err(|e| (e, context))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_severity() {
        let gpu_error = OpusError::gpu_error("Test GPU error", Some(0));
        assert_eq!(gpu_error.severity(), ErrorSeverity::High);

        let memory_error = OpusError::memory_error("Out of memory", 1024);
        assert_eq!(memory_error.severity(), ErrorSeverity::Critical);

        let thermal_error = OpusError::thermal_error(90.0, 85.0);
        assert_eq!(thermal_error.severity(), ErrorSeverity::High);

        let critical_thermal = OpusError::thermal_error(100.0, 85.0);
        assert_eq!(critical_thermal.severity(), ErrorSeverity::Critical);
    }

    #[test]
    fn test_error_recoverability() {
        let network_error = OpusError::Network {
            message: "Connection failed".into(),
        };
        assert!(network_error.is_recoverable());

        let memory_error = OpusError::memory_error("Out of memory", 1024);
        assert!(!memory_error.is_recoverable());

        let security_error = OpusError::security_error("Authentication failed");
        assert!(!security_error.is_recoverable());
    }

    #[test]
    fn test_error_codes() {
        let gpu_error = OpusError::gpu_error("Test", None);
        assert_eq!(gpu_error.error_code(), 1001);

        let cuda_error = OpusError::cuda_error("Test", 100);
        assert_eq!(cuda_error.error_code(), 1002);
    }

    #[test]
    fn test_error_context() {
        let context = ErrorContext::new("gpu_mining", "initialize")
            .with_info("Device 0 initialization");

        assert_eq!(context.component, "gpu_mining");
        assert_eq!(context.operation, "initialize");
        assert!(context.additional_info.is_some());
    }
}