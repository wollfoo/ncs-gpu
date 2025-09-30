use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

/// **[Worker ID]** (ID worker – định danh worker node duy nhất)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct WorkerId(pub Uuid);

impl WorkerId {
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for WorkerId {
    fn default() -> Self {
        Self::new()
    }
}

/// **[Task ID]** (ID tác vụ – định danh task duy nhất)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TaskId(pub Uuid);

impl TaskId {
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for TaskId {
    fn default() -> Self {
        Self::new()
    }
}

/// **[GPU Device Info]** (Thông tin thiết bị GPU – metadata card đồ họa)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuDevice {
    /// **[Device Index]** (chỉ số thiết bị – GPU number)
    pub index: u32,
    
    /// **[Device Name]** (tên thiết bị – ví dụ: "NVIDIA RTX 4090")
    pub name: String,
    
    /// **[Total Memory]** (bộ nhớ tổng – VRAM size in bytes)
    pub total_memory: u64,
    
    /// **[Compute Capability]** (khả năng tính toán – CUDA compute version)
    pub compute_capability: (u32, u32),
    
    /// **[UUID]** (định danh duy nhất – hardware UUID)
    pub uuid: String,
}

/// **[Task Status]** (Trạng thái tác vụ – lifecycle state của task)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskStatus {
    /// **[Pending]** (Chờ xử lý – task đang trong queue)
    Pending,
    
    /// **[Running]** (Đang chạy – task đang execute trên GPU)
    Running,
    
    /// **[Completed]** (Hoàn thành – task finished successfully)
    Completed,
    
    /// **[Failed]** (Thất bại – task encountered error)
    Failed,
    
    /// **[Cancelled]** (Đã hủy – task cancelled by user/system)
    Cancelled,
}

/// **[Task Metadata]** (Metadata tác vụ – thông tin tracking)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskMetadata {
    pub task_id: TaskId,
    pub worker_id: Option<WorkerId>,
    pub status: TaskStatus,
    pub created_at: DateTime<Utc>,
    pub started_at: Option<DateTime<Utc>>,
    pub completed_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
}

impl TaskMetadata {
    pub fn new(task_id: TaskId) -> Self {
        Self {
            task_id,
            worker_id: None,
            status: TaskStatus::Pending,
            created_at: Utc::now(),
            started_at: None,
            completed_at: None,
            error_message: None,
        }
    }
    
    /// **[Mark Running]** (Đánh dấu đang chạy – chuyển sang Running state)
    pub fn mark_running(&mut self, worker_id: WorkerId) {
        self.status = TaskStatus::Running;
        self.worker_id = Some(worker_id);
        self.started_at = Some(Utc::now());
    }
    
    /// **[Mark Completed]** (Đánh dấu hoàn thành – chuyển sang Completed state)
    pub fn mark_completed(&mut self) {
        self.status = TaskStatus::Completed;
        self.completed_at = Some(Utc::now());
    }
    
    /// **[Mark Failed]** (Đánh dấu thất bại – chuyển sang Failed state với error)
    pub fn mark_failed(&mut self, error: String) {
        self.status = TaskStatus::Failed;
        self.completed_at = Some(Utc::now());
        self.error_message = Some(error);
    }
}
