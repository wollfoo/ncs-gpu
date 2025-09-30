use thiserror::Error;

/// **[GPU Error]** (Lỗi GPU – tất cả error types trong hệ thống)
#[derive(Error, Debug)]
pub enum GpuError {
    /// **[CUDA Error]** (Lỗi CUDA – runtime/driver errors)
    #[error("CUDA error: {0}")]
    Cuda(String),
    
    /// **[Device Not Found]** (Không tìm thấy thiết bị – GPU index invalid)
    #[error("GPU device {0} not found")]
    DeviceNotFound(u32),
    
    /// **[Out of Memory]** (Hết bộ nhớ – CUDA allocation failed)
    #[error("GPU out of memory: {0}")]
    OutOfMemory(String),
    
    /// **[Kernel Launch Failed]** (Kernel thất bại – kernel execution error)
    #[error("Kernel launch failed: {0}")]
    KernelLaunchFailed(String),
    
    /// **[IO Error]** (Lỗi I/O – file/network errors)
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    
    /// **[Config Error]** (Lỗi cấu hình – invalid config)
    #[error("Configuration error: {0}")]
    Config(String),
    
    /// **[Task Failed]** (Tác vụ thất bại – task execution error)
    #[error("Task failed: {0}")]
    TaskFailed(String),
    
    /// **[Worker Unavailable]** (Worker không khả dụng – no workers available)
    #[error("No workers available")]
    WorkerUnavailable,
    
    /// **[Timeout]** (Hết thời gian – operation timeout)
    #[error("Operation timed out")]
    Timeout,
    
    /// **[Internal Error]** (Lỗi nội bộ – unexpected errors)
    #[error("Internal error: {0}")]
    Internal(String),
}

/// **[Result Type]** (Kiểu kết quả – shorthand cho Result với GpuError)
pub type Result<T> = std::result::Result<T, GpuError>;
