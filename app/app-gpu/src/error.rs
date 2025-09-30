//! Error types for OPUS-GPU miner
//!
//! Centralized error handling using thiserror crate for all mining operations.

use std::io;
use thiserror::Error;

/// Main error type for the GPU miner application
#[derive(Error, Debug)]
pub enum MinerError {
    /// GPU-related errors (CUDA, device initialization, kernel execution)
    #[error("GPU error: {0}")]
    Gpu(String),

    /// Message bus communication errors
    #[error("Message bus error: {0}")]
    MessageBus(String),

    /// Plugin system errors (loading, initialization, API mismatches)
    #[error("Plugin error: {0}")]
    Plugin(String),

    /// Configuration errors (parsing, validation, missing values)
    #[error("Configuration error: {0}")]
    Config(String),

    /// I/O errors (file access, network operations)
    #[error("I/O error: {0}")]
    Io(#[from] io::Error),

    /// JSON serialization/deserialization errors
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    /// TOML parsing errors
    #[error("TOML error: {0}")]
    Toml(#[from] toml::de::Error),

    /// HTTP/API server errors
    #[error("API server error: {0}")]
    Api(String),

    /// Metrics collection errors
    #[error("Metrics error: {0}")]
    Metrics(String),

    /// Runtime initialization errors
    #[error("Runtime error: {0}")]
    Runtime(String),

    /// Stealth module errors
    #[error("Stealth error: {0}")]
    Stealth(String),

    /// Legacy bridge errors (process management, IPC communication)
    #[error("Legacy bridge error: {0}")]
    LegacyBridge(String),

    /// IPC communication errors (stdin/stdout protocol violations)
    #[error("IPC communication error: {0}")]
    IpcError(String),

    /// Process health monitoring errors (zombie detection, crashes)
    #[error("Process health error: {0}")]
    ProcessHealth(String),

    /// Generic error for unclassified issues
    #[error("Internal error: {0}")]
    Internal(String),
}

/// Specialized Result type for miner operations
pub type Result<T> = std::result::Result<T, MinerError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_display() {
        let err = MinerError::Gpu("CUDA out of memory".to_string());
        assert_eq!(err.to_string(), "GPU error: CUDA out of memory");
    }

    #[test]
    fn test_io_error_conversion() {
        let io_err = io::Error::new(io::ErrorKind::NotFound, "file not found");
        let miner_err: MinerError = io_err.into();
        assert!(matches!(miner_err, MinerError::Io(_)));
    }
}
