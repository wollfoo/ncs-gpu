//! Configuration error types and handling

use thiserror::Error;

/// Configuration management result type
pub type ConfigResult<T> = Result<T, ConfigError>;

/// Configuration management errors
#[derive(Error, Debug)]
pub enum ConfigError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    #[error("TOML parsing error: {0}")]
    TomlParsing(#[from] toml::de::Error),

    #[error("YAML parsing error: {0}")]
    YamlParsing(#[from] serde_yaml::Error),

    #[error("Configuration validation error: {0}")]
    Validation(String),

    #[error("Figment error: {0}")]
    Figment(#[from] figment::Error),

    #[error("File watcher error: {0}")]
    Watcher(#[from] notify::Error),

    #[error("Security error: {0}")]
    Security(String),

    #[error("Encryption error: {0}")]
    Encryption(String),

    #[error("Access denied: {permission} permission required")]
    AccessDenied { permission: String },

    #[error("Configuration not found at path: {path}")]
    NotFound { path: String },

    #[error("Invalid configuration format: {format}")]
    InvalidFormat { format: String },

    #[error("Configuration schema validation failed: {details}")]
    SchemaValidation { details: String },

    #[error("Hot reload error: {message}")]
    HotReload { message: String },

    #[error("Audit logging error: {0}")]
    AuditLog(String),

    #[error("Secret management error: {0}")]
    SecretManagement(String),
}

impl ConfigError {
    /// Create a new validation error
    pub fn validation<S: Into<String>>(message: S) -> Self {
        Self::Validation(message.into())
    }

    /// Create a new security error
    pub fn security<S: Into<String>>(message: S) -> Self {
        Self::Security(message.into())
    }

    /// Create a new encryption error
    pub fn encryption<S: Into<String>>(message: S) -> Self {
        Self::Encryption(message.into())
    }

    /// Create a new access denied error
    pub fn access_denied<S: Into<String>>(permission: S) -> Self {
        Self::AccessDenied {
            permission: permission.into(),
        }
    }

    /// Create a new not found error
    pub fn not_found<S: Into<String>>(path: S) -> Self {
        Self::NotFound {
            path: path.into(),
        }
    }

    /// Create a new invalid format error
    pub fn invalid_format<S: Into<String>>(format: S) -> Self {
        Self::InvalidFormat {
            format: format.into(),
        }
    }

    /// Create a new schema validation error
    pub fn schema_validation<S: Into<String>>(details: S) -> Self {
        Self::SchemaValidation {
            details: details.into(),
        }
    }

    /// Create a new hot reload error
    pub fn hot_reload<S: Into<String>>(message: S) -> Self {
        Self::HotReload {
            message: message.into(),
        }
    }

    /// Create a new audit log error
    pub fn audit_log<S: Into<String>>(message: S) -> Self {
        Self::AuditLog(message.into())
    }

    /// Create a new secret management error
    pub fn secret_management<S: Into<String>>(message: S) -> Self {
        Self::SecretManagement(message.into())
    }

    /// Check if error is retryable
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            ConfigError::Io(_) | ConfigError::Watcher(_) | ConfigError::HotReload { .. }
        )
    }

    /// Get error severity level
    pub fn severity(&self) -> ErrorSeverity {
        match self {
            ConfigError::Security(_) | ConfigError::AccessDenied { .. } => ErrorSeverity::Critical,
            ConfigError::Validation(_) | ConfigError::SchemaValidation { .. } => ErrorSeverity::High,
            ConfigError::NotFound { .. } | ConfigError::InvalidFormat { .. } => ErrorSeverity::Medium,
            _ => ErrorSeverity::Low,
        }
    }
}

/// Error severity levels for monitoring and alerting
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