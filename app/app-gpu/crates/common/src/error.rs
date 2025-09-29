/*!
 * Error Handling
 * 
 * Định nghĩa error types chung và Result type alias.
 */

use thiserror::Error;

/// Application Error Types
#[derive(Error, Debug)]
pub enum AppError {
    /// Configuration error (lỗi cấu hình)
    #[error("Configuration error: {0}")]
    Config(String),
    
    /// Plugin error (lỗi plugin)
    #[error("Plugin error: {0}")]
    Plugin(String),
    
    /// GPU error (lỗi GPU)
    #[error("GPU error: {0}")]
    Gpu(String),
    
    /// CUDA error (lỗi CUDA)
    #[error("CUDA error: {0}")]
    Cuda(String),
    
    /// NVML error (lỗi NVML)
    #[error("NVML error: {0}")]
    Nvml(String),
    
    /// I/O error (lỗi I/O)
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    
    /// Serialization error (lỗi serialization)
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
    
    /// Event bus error (lỗi event bus)
    #[error("Event bus error: {0}")]
    EventBus(String),
    
    /// Timeout error (lỗi timeout)
    #[error("Timeout error: {0}")]
    Timeout(String),
    
    /// Invalid state error (lỗi trạng thái không hợp lệ)
    #[error("Invalid state: {0}")]
    InvalidState(String),
    
    /// Other error (lỗi khác)
    #[error("Other error: {0}")]
    Other(String),
}

/// Result type alias
pub type Result<T> = std::result::Result<T, AppError>;
