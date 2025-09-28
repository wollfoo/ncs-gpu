use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Định danh công việc GPU.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq, Hash)]
pub struct JobId(pub String);

/// Độ ưu tiên QoS (cao hơn = xử lý trước).
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum PriorityClass {
    Critical = 3,
    High = 2,
    Normal = 1,
}

/// Chính sách QoS cho một job.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct QosPolicy {
    pub priority: PriorityClass,
    /// Deadline mềm cho job (millisecond kể từ enqueue).
    pub soft_deadline_ms: u64,
    /// Số lần retry tối đa khi fail.
    pub max_retries: u8,
}

impl Default for QosPolicy {
    fn default() -> Self {
        Self {
            priority: PriorityClass::Normal,
            soft_deadline_ms: 500,
            max_retries: 3,
        }
    }
}

/// Mô tả công việc gửi tới scheduler.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct JobSpec {
    pub id: JobId,
    pub qos: QosPolicy,
    /// Kích thước batch (ví dụ shares cần xử lý) để scheduler cân bằng.
    pub batch_size: u32,
}

impl JobSpec {
    pub fn new(id: impl Into<String>, qos: QosPolicy, batch_size: u32) -> Self {
        Self {
            id: JobId(id.into()),
            qos,
            batch_size,
        }
    }

    /// Chuyển deadline mềm sang Duration.
    pub fn soft_deadline(&self) -> Duration {
        Duration::from_millis(self.qos.soft_deadline_ms)
    }
}
