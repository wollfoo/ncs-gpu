// Common types cho GPU Mining System
// Module chứa các struct, enum, error types dùng chung

pub mod types;
pub mod error;
pub mod workload;

pub use error::{GpuError, Result};
pub use types::{WorkerId, TaskId, GpuDevice, TaskStatus};
pub use workload::{WorkloadType, WorkloadConfig, WorkloadResult};
