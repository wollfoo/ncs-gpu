use gpu_common::{TaskId, WorkerId, TaskMetadata, TaskStatus, WorkloadConfig, GpuError, Result};
use std::sync::Arc;
use tokio::sync::{RwLock, mpsc};
use dashmap::DashMap;
use tracing::{info, warn, error};

use crate::worker_registry::WorkerRegistry;

/// **[Task Scheduler]** (Bộ lập lịch tác vụ – quản lý task queue và assignment)
#[derive(Clone)]
pub struct TaskScheduler {
    /// **[Pending Tasks]** (Tác vụ chờ – FIFO queue)
    pending_tasks: Arc<DashMap<TaskId, (TaskMetadata, WorkloadConfig)>>,
    
    /// **[Active Tasks]** (Tác vụ đang chạy – tracking running tasks)
    active_tasks: Arc<DashMap<TaskId, TaskMetadata>>,
    
    /// **[Worker Registry]** (Sổ đăng ký worker)
    worker_registry: WorkerRegistry,
    
    /// **[Task Sender]** (Kênh gửi tác vụ – channel to dispatch tasks)
    task_tx: mpsc::UnboundedSender<(TaskId, WorkloadConfig)>,
}

impl TaskScheduler {
    /// **[New]** (Tạo mới – khởi tạo scheduler)
    pub fn new(worker_registry: WorkerRegistry) -> Self {
        let (task_tx, mut task_rx) = mpsc::unbounded_channel();
        
        let pending_tasks = Arc::new(DashMap::new());
        let active_tasks = Arc::new(DashMap::new());
        
        let scheduler = Self {
            pending_tasks: pending_tasks.clone(),
            active_tasks: active_tasks.clone(),
            worker_registry: worker_registry.clone(),
            task_tx,
        };
        
        // Khởi động **[Dispatch Loop]** (vòng điều phối – assign tasks to workers)
        tokio::spawn(async move {
            while let Some((task_id, config)) = task_rx.recv().await {
                info!("📤 Dispatching task: {:?}", task_id);
                
                // Tìm **[Available Worker]** (worker khả dụng)
                if let Some(worker_id) = worker_registry.get_available_worker().await {
                    // Chuyển từ pending -> active
                    if let Some((_, (mut metadata, _))) = pending_tasks.remove(&task_id) {
                        metadata.mark_running(worker_id);
                        active_tasks.insert(task_id, metadata.clone());
                        
                        info!("✅ Task {:?} assigned to worker {:?}", task_id, worker_id);
                        
                        // TODO: Gửi task tới worker qua gRPC
                        // worker_registry.send_task(worker_id, task_id, config).await;
                    }
                } else {
                    warn!("⚠️  Không có worker khả dụng, task {:?} vẫn pending", task_id);
                }
            }
        });
        
        scheduler
    }
    
    /// **[Submit Task]** (Gửi tác vụ – thêm task vào queue)
    pub async fn submit_task(&self, config: WorkloadConfig) -> Result<TaskId> {
        let task_id = TaskId::new();
        let metadata = TaskMetadata::new(task_id);
        
        self.pending_tasks.insert(task_id, (metadata, config.clone()));
        
        // Kích hoạt **[Dispatch]** (điều phối)
        self.task_tx.send((task_id, config))
            .map_err(|_| GpuError::Internal("Failed to queue task".to_string()))?;
        
        info!("📥 Task submitted: {:?}", task_id);
        Ok(task_id)
    }
    
    /// **[Get Task Status]** (Lấy trạng thái tác vụ)
    pub async fn get_task_status(&self, task_id: TaskId) -> Option<TaskStatus> {
        // Check active tasks first
        if let Some(metadata) = self.active_tasks.get(&task_id) {
            return Some(metadata.status);
        }
        
        // Check pending tasks
        if let Some(entry) = self.pending_tasks.get(&task_id) {
            return Some(entry.value().0.status);
        }
        
        None
    }
    
    /// **[Mark Completed]** (Đánh dấu hoàn thành)
    pub async fn mark_task_completed(&self, task_id: TaskId) -> Result<()> {
        if let Some((_, mut metadata)) = self.active_tasks.remove(&task_id) {
            metadata.mark_completed();
            info!("✅ Task {:?} completed", task_id);
            Ok(())
        } else {
            Err(GpuError::TaskFailed("Task not found in active tasks".to_string()))
        }
    }
    
    /// **[Mark Failed]** (Đánh dấu thất bại)
    pub async fn mark_task_failed(&self, task_id: TaskId, error: String) -> Result<()> {
        if let Some((_, mut metadata)) = self.active_tasks.remove(&task_id) {
            metadata.mark_failed(error.clone());
            error!("❌ Task {:?} failed: {}", task_id, error);
            Ok(())
        } else {
            Err(GpuError::TaskFailed("Task not found in active tasks".to_string()))
        }
    }
    
    /// **[Pending Count]** (Số lượng pending)
    pub fn pending_count(&self) -> usize {
        self.pending_tasks.len()
    }
    
    /// **[Active Count]** (Số lượng active)
    pub fn active_count(&self) -> usize {
        self.active_tasks.len()
    }
}
