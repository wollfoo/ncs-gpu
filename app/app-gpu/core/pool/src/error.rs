//! Error types for the pool communication module

use thiserror::Error;

/// Pool operation result type
pub type PoolResult<T> = Result<T, PoolError>;

/// Pool communication errors
#[derive(Error, Debug)]
pub enum PoolError {
    /// Connection errors
    #[error("Connection error: {0}")]
    Connection(String),

    /// Authentication errors
    #[error("Authentication failed: {0}")]
    Authentication(String),

    /// Protocol errors
    #[error("Protocol error: {0}")]
    Protocol(String),

    /// Stratum-specific errors
    #[error("Stratum error: {0}")]
    Stratum(String),

    /// Serialization/Deserialization errors
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// Network I/O errors
    #[error("Network I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// TLS/SSL errors
    #[error("TLS error: {0}")]
    Tls(String),

    /// WebSocket errors
    #[error("WebSocket error: {0}")]
    WebSocket(String),

    /// Timeout errors
    #[error("Operation timeout: {0}")]
    Timeout(String),

    /// Pool not found
    #[error("Pool not found: {pool_id}")]
    PoolNotFound { pool_id: uuid::Uuid },

    /// Invalid configuration
    #[error("Invalid configuration: {0}")]
    InvalidConfig(String),

    /// Work validation errors
    #[error("Work validation error: {0}")]
    WorkValidation(String),

    /// Share submission errors
    #[error("Share submission error: {0}")]
    ShareSubmission(String),

    /// Difficulty adjustment errors
    #[error("Difficulty adjustment error: {0}")]
    DifficultyAdjustment(String),

    /// Pool manager errors
    #[error("Pool manager error: {0}")]
    PoolManager(String),

    /// Connection pool exhausted
    #[error("Connection pool exhausted")]
    PoolExhausted,

    /// Invalid response format
    #[error("Invalid response format: expected {expected}, got {actual}")]
    InvalidResponse { expected: String, actual: String },

    /// Rate limiting error
    #[error("Rate limited: {0}")]
    RateLimit(String),

    /// Unsupported feature
    #[error("Unsupported feature: {0}")]
    Unsupported(String),
}

impl PoolError {
    /// Create a connection error
    pub fn connection<S: Into<String>>(msg: S) -> Self {
        Self::Connection(msg.into())
    }

    /// Create an authentication error
    pub fn authentication<S: Into<String>>(msg: S) -> Self {
        Self::Authentication(msg.into())
    }

    /// Create a protocol error
    pub fn protocol<S: Into<String>>(msg: S) -> Self {
        Self::Protocol(msg.into())
    }

    /// Create a Stratum error
    pub fn stratum<S: Into<String>>(msg: S) -> Self {
        Self::Stratum(msg.into())
    }

    /// Create a TLS error
    pub fn tls<S: Into<String>>(msg: S) -> Self {
        Self::Tls(msg.into())
    }

    /// Create a WebSocket error
    pub fn websocket<S: Into<String>>(msg: S) -> Self {
        Self::WebSocket(msg.into())
    }

    /// Create a timeout error
    pub fn timeout<S: Into<String>>(msg: S) -> Self {
        Self::Timeout(msg.into())
    }

    /// Create an invalid configuration error
    pub fn invalid_config<S: Into<String>>(msg: S) -> Self {
        Self::InvalidConfig(msg.into())
    }

    /// Check if error is recoverable
    pub fn is_recoverable(&self) -> bool {
        matches!(
            self,
            PoolError::Connection(_)
                | PoolError::Timeout(_)
                | PoolError::WebSocket(_)
                | PoolError::Io(_)
                | PoolError::RateLimit(_)
        )
    }

    /// Check if error requires reconnection
    pub fn requires_reconnection(&self) -> bool {
        matches!(
            self,
            PoolError::Connection(_)
                | PoolError::Authentication(_)
                | PoolError::WebSocket(_)
                | PoolError::Tls(_)
        )
    }

    /// Get error severity level
    pub fn severity(&self) -> ErrorSeverity {
        match self {
            PoolError::Authentication(_) | PoolError::InvalidConfig(_) => ErrorSeverity::Critical,
            PoolError::Protocol(_) | PoolError::Stratum(_) => ErrorSeverity::High,
            PoolError::Connection(_) | PoolError::WebSocket(_) | PoolError::Timeout(_) => {
                ErrorSeverity::Medium
            }
            PoolError::RateLimit(_) | PoolError::Io(_) => ErrorSeverity::Low,
            _ => ErrorSeverity::Medium,
        }
    }
}

/// Error severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorSeverity {
    Low,
    Medium,
    High,
    Critical,
}

impl std::fmt::Display for ErrorSeverity {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ErrorSeverity::Low => write!(f, "LOW"),
            ErrorSeverity::Medium => write!(f, "MEDIUM"),
            ErrorSeverity::High => write!(f, "HIGH"),
            ErrorSeverity::Critical => write!(f, "CRITICAL"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_creation() {
        let err = PoolError::connection("test connection error");
        assert!(matches!(err, PoolError::Connection(_)));
        assert!(err.is_recoverable());
        assert!(err.requires_reconnection());
    }

    #[test]
    fn test_error_severity() {
        let auth_err = PoolError::authentication("invalid credentials");
        assert_eq!(auth_err.severity(), ErrorSeverity::Critical);

        let conn_err = PoolError::connection("connection lost");
        assert_eq!(conn_err.severity(), ErrorSeverity::Medium);
    }

    #[test]
    fn test_error_classification() {
        let timeout_err = PoolError::timeout("operation timed out");
        assert!(timeout_err.is_recoverable());
        assert!(!timeout_err.requires_reconnection());

        let tls_err = PoolError::tls("certificate validation failed");
        assert!(!tls_err.is_recoverable());
        assert!(tls_err.requires_reconnection());
    }
}