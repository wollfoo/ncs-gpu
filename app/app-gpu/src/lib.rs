//! Thư viện chung cho orchestrator/worker (Việt/Anh)
//! Common library for orchestrator/worker.

use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// **[TaskKind]** (loại tác vụ – kiểu tải GPU)
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskKind {
    Gemm { n: usize, iters: u32 },
    Conv2d { width: usize, height: usize, kernel: usize, iters: u32 },
    Fft1d { n: usize, iters: u32 },
    Inference { size: usize, iters: u32 },
}

/// **[Task]** (tác vụ – đơn vị công việc)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Task {
    pub id: Uuid,
    pub kind: TaskKind,
    pub submitted_at_ms: i64,
}

/// **[TaskStatus]** (trạng thái tác vụ)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum TaskStatus {
    Queued,
    Running,
    Completed,
    Failed { message: String },
}

/// **[EnqueueRequest]** (yêu cầu thêm tác vụ vào hàng đợi)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EnqueueRequest {
    pub kind: TaskKind,
}

/// **[EnqueueResponse]** (phản hồi thêm tác vụ)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EnqueueResponse {
    pub id: Uuid,
    pub status: TaskStatus,
}

impl Task {
    pub fn new(kind: TaskKind) -> Self {
        Self {
            id: Uuid::new_v4(),
            kind,
            submitted_at_ms: chrono::Utc::now().timestamp_millis(),
        }
    }
}

pub mod gpu {
    /// Module GPU (để worker import). Hiện chưa chứa triển khai; sẽ bổ sung `opencl`.
    pub mod opencl;
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn serde_roundtrip() {
        let t = Task::new(TaskKind::Gemm { n: 512, iters: 5 });
        let s = serde_json::to_string(&t).unwrap();
        let _back: Task = serde_json::from_str(&s).unwrap();
    }
}
