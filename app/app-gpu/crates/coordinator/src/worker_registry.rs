use gpu_common::{WorkerId, GpuDevice};
use dashmap::DashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tracing::{info, warn};

/// **[Worker Info]** (Thông tin worker – metadata về worker node)
#[derive(Debug, Clone)]
pub struct WorkerInfo {
    pub worker_id: WorkerId,
    pub gpu_devices: Vec<GpuDevice>,
    pub last_heartbeat: Instant,
    pub is_busy: bool,
}

/// **[Worker Registry]** (Sổ đăng ký worker – tracking tất cả workers)
#[derive(Clone)]
pub struct WorkerRegistry {
    workers: Arc<DashMap<WorkerId, WorkerInfo>>,
}

impl WorkerRegistry {
    /// **[New]** (Tạo mới – khởi tạo registry rỗng)
    pub fn new() -> Self {
        Self {
            workers: Arc::new(DashMap::new()),
        }
    }
    
    /// **[Register Worker]** (Đăng ký worker – thêm worker mới vào registry)
    pub async fn register_worker(&self, worker_id: WorkerId, gpu_devices: Vec<GpuDevice>) {
        let info = WorkerInfo {
            worker_id,
            gpu_devices: gpu_devices.clone(),
            last_heartbeat: Instant::now(),
            is_busy: false,
        };
        
        self.workers.insert(worker_id, info);
        info!("🔌 Worker registered: {:?} with {} GPUs", worker_id, gpu_devices.len());
    }
    
    /// **[Unregister Worker]** (Hủy đăng ký worker)
    pub async fn unregister_worker(&self, worker_id: WorkerId) {
        self.workers.remove(&worker_id);
        info!("🔌 Worker unregistered: {:?}", worker_id);
    }
    
    /// **[Update Heartbeat]** (Cập nhật heartbeat – worker còn sống)
    pub async fn update_heartbeat(&self, worker_id: WorkerId) {
        if let Some(mut worker) = self.workers.get_mut(&worker_id) {
            worker.last_heartbeat = Instant::now();
        }
    }
    
    /// **[Get Available Worker]** (Lấy worker khả dụng – tìm worker không bận)
    pub async fn get_available_worker(&self) -> Option<WorkerId> {
        for entry in self.workers.iter() {
            if !entry.value().is_busy {
                return Some(entry.key().clone());
            }
        }
        None
    }
    
    /// **[Mark Busy]** (Đánh dấu bận)
    pub async fn mark_worker_busy(&self, worker_id: WorkerId, busy: bool) {
        if let Some(mut worker) = self.workers.get_mut(&worker_id) {
            worker.is_busy = busy;
        }
    }
    
    /// **[Active Worker Count]** (Số lượng worker hoạt động)
    pub fn active_worker_count(&self) -> usize {
        self.workers.len()
    }
    
    /// **[Remove Dead Workers]** (Loại bỏ workers chết – không heartbeat)
    pub async fn remove_dead_workers(&self, timeout: Duration) -> usize {
        let now = Instant::now();
        let mut removed = 0;
        
        self.workers.retain(|worker_id, info| {
            let elapsed = now.duration_since(info.last_heartbeat);
            if elapsed > timeout {
                warn!("💀 Removing dead worker: {:?} (no heartbeat for {:?})", worker_id, elapsed);
                removed += 1;
                false
            } else {
                true
            }
        });
        
        removed
    }
    
    /// **[Get Worker Info]** (Lấy thông tin worker)
    pub async fn get_worker_info(&self, worker_id: WorkerId) -> Option<WorkerInfo> {
        self.workers.get(&worker_id).map(|entry| entry.value().clone())
    }
    
    /// **[List All Workers]** (Liệt kê tất cả workers)
    pub async fn list_all_workers(&self) -> Vec<WorkerInfo> {
        self.workers.iter().map(|entry| entry.value().clone()).collect()
    }
}
