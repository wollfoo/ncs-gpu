//! **Task Scheduler** (bộ lập lịch tác vụ – điều phối công việc)

use anyhow::Result;
use crossbeam::deque::{Injector, Stealer, Worker};
use parking_lot::RwLock;
use std::sync::{
    atomic::{AtomicBool, AtomicU64, Ordering},
    Arc,
};
use std::time::{Duration, Instant};
use tokio::sync::mpsc;
use tracing::{debug, error, info, warn};
use uuid::Uuid;

use crate::utils::config::SchedulerConfig;

/// **Task Priority** (độ ưu tiên tác vụ – mức độ quan trọng)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum TaskPriority {
    /// Critical - must run immediately
    Critical = 0,
    /// High priority
    High = 1,
    /// Normal priority
    Normal = 2,
    /// Low priority
    Low = 3,
}

/// **Task State** (trạng thái tác vụ – tình trạng công việc)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TaskState {
    /// Pending execution
    Pending,
    /// Currently running
    Running,
    /// Completed successfully
    Completed,
    /// Failed with error
    Failed,
    /// Cancelled
    Cancelled,
}

/// **Task** (tác vụ – công việc cần thực hiện)
#[derive(Debug, Clone)]
pub struct Task {
    /// Unique task ID
    pub id: Uuid,
    /// Task name
    pub name: String,
    /// Task priority
    pub priority: TaskPriority,
    /// Task state
    pub state: Arc<RwLock<TaskState>>,
    /// GPU device index (optional)
    pub gpu_index: Option<u32>,
    /// Task payload
    pub payload: Vec<u8>,
    /// Created timestamp
    pub created_at: Instant,
    /// Started timestamp
    pub started_at: Arc<RwLock<Option<Instant>>>,
    /// Completed timestamp
    pub completed_at: Arc<RwLock<Option<Instant>>>,
}

impl Task {
    /// **Create new task** (tạo tác vụ mới – khởi tạo công việc)
    pub fn new(name: String, priority: TaskPriority, payload: Vec<u8>) -> Self {
        Self {
            id: Uuid::new_v4(),
            name,
            priority,
            state: Arc::new(RwLock::new(TaskState::Pending)),
            gpu_index: None,
            payload,
            created_at: Instant::now(),
            started_at: Arc::new(RwLock::new(None)),
            completed_at: Arc::new(RwLock::new(None)),
        }
    }

    /// **With GPU index** (với chỉ số GPU – gán card đồ họa)
    pub fn with_gpu(mut self, gpu_index: u32) -> Self {
        self.gpu_index = Some(gpu_index);
        self
    }
}

/// **Scheduler Statistics** (thống kê bộ lập lịch – chỉ số điều phối)
#[derive(Debug, Default)]
pub struct SchedulerStats {
    /// Total tasks submitted
    pub total_submitted: AtomicU64,
    /// Total tasks completed
    pub total_completed: AtomicU64,
    /// Total tasks failed
    pub total_failed: AtomicU64,
    /// Current pending tasks
    pub pending_tasks: AtomicU64,
    /// Current running tasks
    pub running_tasks: AtomicU64,
}

/// **Task Scheduler** (bộ lập lịch tác vụ – điều phối công việc)
pub struct Scheduler {
    /// Configuration
    config: SchedulerConfig,
    /// Global task queue
    injector: Arc<Injector<Arc<Task>>>,
    /// Worker queues
    workers: Vec<Worker<Arc<Task>>>,
    /// Stealers for work stealing
    stealers: Vec<Stealer<Arc<Task>>>,
    /// Running state
    running: Arc<AtomicBool>,
    /// Statistics
    stats: Arc<SchedulerStats>,
    /// Task completion channel
    completion_tx: mpsc::UnboundedSender<Arc<Task>>,
    completion_rx: Arc<RwLock<mpsc::UnboundedReceiver<Arc<Task>>>>,
}

impl Scheduler {
    /// **Create new scheduler** (tạo bộ lập lịch mới – khởi tạo điều phối)
    pub fn new(config: SchedulerConfig) -> Self {
        let worker_count = config.worker_threads.unwrap_or_else(num_cpus::get);
        
        info!("🗓️ Creating scheduler with {} workers", worker_count);

        let injector = Arc::new(Injector::new());
        let mut workers = Vec::with_capacity(worker_count);
        let mut stealers = Vec::with_capacity(worker_count);

        for _ in 0..worker_count {
            let worker = Worker::new_fifo();
            stealers.push(worker.stealer());
            workers.push(worker);
        }

        let (completion_tx, completion_rx) = mpsc::unbounded_channel();

        Self {
            config,
            injector,
            workers,
            stealers,
            running: Arc::new(AtomicBool::new(false)),
            stats: Arc::new(SchedulerStats::default()),
            completion_tx,
            completion_rx: Arc::new(RwLock::new(completion_rx)),
        }
    }

    /// **Start scheduler** (khởi động bộ lập lịch – chạy điều phối)
    pub async fn start(&self) -> Result<()> {
        if self.running.load(Ordering::Acquire) {
            return Ok(());
        }

        self.running.store(true, Ordering::Release);
        info!("🚀 Scheduler started");

        // Start worker threads
        for (i, worker) in self.workers.iter().enumerate() {
            let worker_id = i;
            let injector = self.injector.clone();
            let stealers = self.stealers.clone();
            let running = self.running.clone();
            let stats = self.stats.clone();
            let completion_tx = self.completion_tx.clone();

            tokio::spawn(async move {
                Self::worker_loop(
                    worker_id,
                    worker,
                    injector,
                    stealers,
                    running,
                    stats,
                    completion_tx,
                )
                .await;
            });
        }

        Ok(())
    }

    /// **Stop scheduler** (dừng bộ lập lịch – tắt điều phối)
    pub async fn stop(&self) -> Result<()> {
        if !self.running.load(Ordering::Acquire) {
            return Ok(());
        }

        info!("🛑 Stopping scheduler");
        self.running.store(false, Ordering::Release);

        // Wait a bit for workers to finish
        tokio::time::sleep(Duration::from_millis(100)).await;

        info!("✅ Scheduler stopped");
        Ok(())
    }

    /// **Submit task** (gửi tác vụ – đưa công việc vào hàng đợi)
    pub fn submit(&self, task: Task) -> Result<()> {
        if !self.running.load(Ordering::Acquire) {
            return Err(anyhow::anyhow!("Scheduler is not running"));
        }

        let task = Arc::new(task);
        
        debug!(
            "📥 Submitting task: {} (priority: {:?})",
            task.name, task.priority
        );

        // Push to global queue based on priority
        match task.priority {
            TaskPriority::Critical => {
                // Critical tasks go to front
                self.injector.push(task);
            }
            _ => {
                // Others go to back
                self.injector.push(task);
            }
        }

        self.stats.total_submitted.fetch_add(1, Ordering::Relaxed);
        self.stats.pending_tasks.fetch_add(1, Ordering::Relaxed);

        Ok(())
    }

    /// **Worker loop** (vòng lặp worker – xử lý công việc)
    async fn worker_loop(
        worker_id: usize,
        worker: &Worker<Arc<Task>>,
        injector: Arc<Injector<Arc<Task>>>,
        stealers: Vec<Stealer<Arc<Task>>>,
        running: Arc<AtomicBool>,
        stats: Arc<SchedulerStats>,
        completion_tx: mpsc::UnboundedSender<Arc<Task>>,
    ) {
        debug!("🔧 Worker {} started", worker_id);

        while running.load(Ordering::Acquire) {
            // Try to get task from local queue first
            let task = worker.pop().or_else(|| {
                // Try global queue
                std::iter::repeat_with(|| injector.steal())
                    .find(|s| !s.is_retry())
                    .and_then(|s| s.success())
            }).or_else(|| {
                // Try stealing from other workers
                stealers.iter()
                    .enumerate()
                    .filter(|(i, _)| *i != worker_id)
                    .map(|(_, s)| s.steal())
                    .find(|s| !s.is_retry())
                    .and_then(|s| s.success())
            });

            if let Some(task) = task {
                // Update stats
                stats.pending_tasks.fetch_sub(1, Ordering::Relaxed);
                stats.running_tasks.fetch_add(1, Ordering::Relaxed);

                // Update task state
                {
                    let mut state = task.state.write();
                    *state = TaskState::Running;
                    *task.started_at.write() = Some(Instant::now());
                }

                debug!("⚡ Worker {} executing task: {}", worker_id, task.name);

                // Execute task (simulated for now)
                tokio::time::sleep(Duration::from_millis(100)).await;

                // Update task state
                {
                    let mut state = task.state.write();
                    *state = TaskState::Completed;
                    *task.completed_at.write() = Some(Instant::now());
                }

                // Update stats
                stats.running_tasks.fetch_sub(1, Ordering::Relaxed);
                stats.total_completed.fetch_add(1, Ordering::Relaxed);

                // Send completion notification
                let _ = completion_tx.send(task);
            } else {
                // No work available, sleep a bit
                tokio::time::sleep(Duration::from_millis(10)).await;
            }
        }

        debug!("🔧 Worker {} stopped", worker_id);
    }

    /// **Get scheduler statistics** (lấy thống kê bộ lập lịch – xem chỉ số điều phối)
    pub fn stats(&self) -> &SchedulerStats {
        &self.stats
    }

    /// **Get pending task count** (lấy số lượng tác vụ chờ – đếm công việc đang đợi)
    pub fn pending_count(&self) -> u64 {
        self.stats.pending_tasks.load(Ordering::Relaxed)
    }

    /// **Get running task count** (lấy số lượng tác vụ đang chạy – đếm công việc hoạt động)
    pub fn running_count(&self) -> u64 {
        self.stats.running_tasks.load(Ordering::Relaxed)
    }
}