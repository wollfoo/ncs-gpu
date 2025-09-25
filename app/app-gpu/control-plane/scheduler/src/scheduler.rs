//! GPU Scheduler - Core scheduling logic với backpressure và QoS

use anyhow::{Context, Result};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::{
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc,
    },
    time::{Duration, Instant},
};
use tokio::sync::{RwLock, Semaphore};
use tracing::{debug, info, warn, error, instrument};
use uuid::Uuid;

use crate::{
    config::Config,
    gpu_monitor::{GpuMonitor, GpuStats},
    backpressure::BackpressureController,
    metrics::SCHEDULER_METRICS,
};

/// Task priority levels cho QoS
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum TaskPriority {
    Low = 1,
    Normal = 5,
    High = 8,
    Critical = 10,
}

/// GPU task request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuTask {
    pub id: String,
    pub priority: TaskPriority,
    pub gpu_requirements: GpuRequirements,
    pub estimated_duration_ms: u64,
    pub deadline: Option<Instant>,
    pub retry_count: u32,
    pub max_retries: u32,
    pub payload: TaskPayload,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuRequirements {
    pub memory_mb: u64,
    pub compute_units: f32,  // 0.0-1.0 utilization
    pub min_gpu_memory_gb: u32,
    pub preferred_gpu_arch: Option<String>, // "Volta", "Turing", "Ampere", etc.
    pub exclusive_access: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskPayload {
    pub operation: String,
    pub params: serde_json::Value,
    pub input_data: Option<Vec<u8>>,
}

/// Task execution status
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum TaskStatus {
    Queued,
    Scheduled { gpu_id: u32, worker_id: String },
    Running { gpu_id: u32, worker_id: String, started_at: Instant },
    Completed { result: TaskResult },
    Failed { error: String, retry_after: Option<Instant> },
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskResult {
    pub output_data: Option<Vec<u8>>,
    pub metrics: ExecutionMetrics,
    pub completed_at: Instant,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionMetrics {
    pub gpu_utilization_avg: f32,
    pub memory_peak_mb: u64,
    pub kernel_time_ms: u64,
    pub memory_copy_time_ms: u64,
    pub total_time_ms: u64,
}

/// GPU worker information
#[derive(Debug, Clone)]
pub struct GpuWorker {
    pub id: String,
    pub gpu_id: u32,
    pub status: WorkerStatus,
    pub current_task: Option<String>, // task_id
    pub last_heartbeat: Instant,
    pub capabilities: WorkerCapabilities,
}

#[derive(Debug, Clone, PartialEq)]
pub enum WorkerStatus {
    Idle,
    Busy,
    Offline,
    Error(String),
}

#[derive(Debug, Clone)]
pub struct WorkerCapabilities {
    pub max_memory_mb: u64,
    pub compute_capability: String,
    pub cuda_cores: u32,
    pub supports_fp16: bool,
    pub supports_int8: bool,
}

/// Main GPU scheduler
pub struct GpuScheduler {
    config: Config,
    
    // Task management
    tasks: Arc<DashMap<String, TaskStatus>>,
    pending_queue: Arc<RwLock<Vec<GpuTask>>>,
    
    // GPU resource tracking
    gpu_monitor: Arc<GpuMonitor>,
    workers: Arc<DashMap<String, GpuWorker>>,
    
    // Concurrency control
    backpressure: Arc<BackpressureController>,
    task_semaphore: Arc<Semaphore>,
    
    // Metrics
    total_tasks: AtomicU64,
    completed_tasks: AtomicU64,
    failed_tasks: AtomicU64,
}

impl GpuScheduler {
    pub async fn new(config: Config, gpu_monitor: Arc<GpuMonitor>) -> Result<Self> {
        let max_concurrent_tasks = config.scheduler.max_concurrent_tasks;
        
        let scheduler = Self {
            config: config.clone(),
            tasks: Arc::new(DashMap::new()),
            pending_queue: Arc::new(RwLock::new(Vec::new())),
            gpu_monitor,
            workers: Arc::new(DashMap::new()),
            backpressure: Arc::new(BackpressureController::new(config.scheduler.backpressure.clone())?),
            task_semaphore: Arc::new(Semaphore::new(max_concurrent_tasks)),
            total_tasks: AtomicU64::new(0),
            completed_tasks: AtomicU64::new(0),
            failed_tasks: AtomicU64::new(0),
        };
        
        info!("🎯 GPU Scheduler initialized with max_concurrent_tasks={}", max_concurrent_tasks);
        Ok(scheduler)
    }
    
    /// Submit a new GPU task
    #[instrument(skip(self, task), fields(task_id = %task.id, priority = ?task.priority))]
    pub async fn submit_task(&self, mut task: GpuTask) -> Result<String> {
        // Check backpressure
        if !self.backpressure.should_accept_task(&task).await {
            SCHEDULER_METRICS.tasks_rejected_backpressure.inc();
            anyhow::bail!("Task rejected due to backpressure");
        }
        
        // Generate task ID if not provided
        if task.id.is_empty() {
            task.id = Uuid::new_v4().to_string();
        }
        
        let task_id = task.id.clone();
        
        // Record task
        self.tasks.insert(task_id.clone(), TaskStatus::Queued);
        self.total_tasks.fetch_add(1, Ordering::Relaxed);
        
        // Add to pending queue (sorted by priority)
        {
            let mut queue = self.pending_queue.write().await;
            queue.push(task);
            queue.sort_by_key(|t| std::cmp::Reverse(t.priority)); // High priority first
        }
        
        SCHEDULER_METRICS.tasks_submitted.inc();
        SCHEDULER_METRICS.queue_size.set(self.get_queue_size().await as f64);
        
        info!(task_id = %task_id, "📝 Task submitted to queue");
        
        // Trigger scheduling
        self.try_schedule_tasks().await?;
        
        Ok(task_id)
    }
    
    /// Try to schedule pending tasks to available workers
    #[instrument(skip(self))]
    pub async fn try_schedule_tasks(&self) -> Result<()> {
        let mut scheduled_count = 0;
        
        // Get current GPU stats
        let gpu_stats = self.gpu_monitor.get_current_stats().await?;
        
        // Process pending queue
        let mut queue = self.pending_queue.write().await;
        let mut remaining_tasks = Vec::new();
        
        for task in queue.drain(..) {
            if let Some(worker) = self.find_suitable_worker(&task, &gpu_stats).await {
                match self.assign_task_to_worker(task, worker).await {
                    Ok(_) => scheduled_count += 1,
                    Err(e) => {
                        warn!("Failed to assign task to worker: {}", e);
                        remaining_tasks.push(task);
                    }
                }
            } else {
                remaining_tasks.push(task);
            }
        }
        
        // Put unscheduled tasks back in queue
        queue.extend(remaining_tasks);
        
        if scheduled_count > 0 {
            info!("📋 Scheduled {} tasks to workers", scheduled_count);
            SCHEDULER_METRICS.tasks_scheduled.inc_by(scheduled_count as u64);
        }
        
        SCHEDULER_METRICS.queue_size.set(queue.len() as f64);
        
        Ok(())
    }
    
    /// Find suitable worker for a task
    async fn find_suitable_worker(&self, task: &GpuTask, gpu_stats: &[GpuStats]) -> Option<GpuWorker> {
        let mut best_worker: Option<GpuWorker> = None;
        let mut best_score = f32::MIN;
        
        for worker_ref in self.workers.iter() {
            let worker = worker_ref.value().clone();
            
            // Check if worker is available
            if worker.status != WorkerStatus::Idle {
                continue;
            }
            
            // Check GPU requirements
            if let Some(gpu_stat) = gpu_stats.iter().find(|g| g.gpu_id == worker.gpu_id) {
                if !self.worker_meets_requirements(&worker, task, gpu_stat) {
                    continue;
                }
                
                // Calculate suitability score
                let score = self.calculate_worker_score(&worker, task, gpu_stat);
                if score > best_score {
                    best_score = score;
                    best_worker = Some(worker);
                }
            }
        }
        
        best_worker
    }
    
    /// Check if worker meets task requirements
    fn worker_meets_requirements(&self, worker: &GpuWorker, task: &GpuTask, gpu_stat: &GpuStats) -> bool {
        // Memory requirement
        if task.gpu_requirements.memory_mb > worker.capabilities.max_memory_mb {
            return false;
        }
        
        // Available memory check
        let available_memory_mb = (gpu_stat.memory_total - gpu_stat.memory_used) / (1024 * 1024);
        if task.gpu_requirements.memory_mb > available_memory_mb {
            return false;
        }
        
        // GPU utilization check (don't overload)
        if gpu_stat.utilization > 0.9 && task.gpu_requirements.compute_units > 0.5 {
            return false;
        }
        
        // Architecture preference
        if let Some(ref preferred_arch) = task.gpu_requirements.preferred_gpu_arch {
            if !worker.capabilities.compute_capability.contains(preferred_arch) {
                return false;
            }
        }
        
        true
    }
    
    /// Calculate worker suitability score
    fn calculate_worker_score(&self, worker: &GpuWorker, task: &GpuTask, gpu_stat: &GpuStats) -> f32 {
        let mut score = 0.0;
        
        // Prefer less utilized GPUs
        score += (1.0 - gpu_stat.utilization) * 50.0;
        
        // Prefer GPUs with more available memory
        let memory_ratio = (gpu_stat.memory_total - gpu_stat.memory_used) as f32 / gpu_stat.memory_total as f32;
        score += memory_ratio * 30.0;
        
        // Prefer newer/more capable GPUs for high-priority tasks
        if task.priority >= TaskPriority::High {
            if worker.capabilities.supports_fp16 {
                score += 10.0;
            }
            if worker.capabilities.cuda_cores > 2048 {
                score += 10.0;
            }
        }
        
        score
    }
    
    /// Assign task to worker
    async fn assign_task_to_worker(&self, task: GpuTask, mut worker: GpuWorker) -> Result<()> {
        // Acquire semaphore permit
        let _permit = self.task_semaphore.acquire().await
            .context("Failed to acquire task semaphore")?;
        
        let task_id = task.id.clone();
        
        // Update worker status
        worker.status = WorkerStatus::Busy;
        worker.current_task = Some(task_id.clone());
        self.workers.insert(worker.id.clone(), worker.clone());
        
        // Update task status
        self.tasks.insert(task_id.clone(), TaskStatus::Scheduled {
            gpu_id: worker.gpu_id,
            worker_id: worker.id.clone(),
        });
        
        // Send task to worker via message queue
        // TODO: Implement NATS message sending
        
        info!(task_id = %task_id, worker_id = %worker.id, gpu_id = worker.gpu_id, 
              "🎯 Task assigned to worker");
        
        Ok(())
    }
    
    /// Register new GPU worker
    pub async fn register_worker(&self, worker: GpuWorker) -> Result<()> {
        let worker_id = worker.id.clone();
        let gpu_id = worker.gpu_id;
        
        self.workers.insert(worker_id.clone(), worker);
        
        info!(worker_id = %worker_id, gpu_id = gpu_id, "🤖 Worker registered");
        SCHEDULER_METRICS.workers_registered.inc();
        
        // Try to schedule pending tasks
        self.try_schedule_tasks().await?;
        
        Ok(())
    }
    
    /// Update task status (called by workers)
    pub async fn update_task_status(&self, task_id: &str, status: TaskStatus) -> Result<()> {
        if let Some(mut task_entry) = self.tasks.get_mut(task_id) {
            let old_status = task_entry.clone();
            *task_entry = status.clone();
            
            // Update metrics based on status change
            match status {
                TaskStatus::Completed { .. } => {
                    self.completed_tasks.fetch_add(1, Ordering::Relaxed);
                    SCHEDULER_METRICS.tasks_completed.inc();
                    
                    // Free up worker
                    if let TaskStatus::Running { worker_id, .. } = old_status {
                        self.mark_worker_idle(&worker_id).await;
                    }
                }
                TaskStatus::Failed { .. } => {
                    self.failed_tasks.fetch_add(1, Ordering::Relaxed);
                    SCHEDULER_METRICS.tasks_failed.inc();
                    
                    // Free up worker  
                    if let TaskStatus::Running { worker_id, .. } = old_status {
                        self.mark_worker_idle(&worker_id).await;
                    }
                }
                TaskStatus::Running { .. } => {
                    SCHEDULER_METRICS.tasks_running.inc();
                }
                _ => {}
            }
            
            debug!(task_id = %task_id, ?status, "📊 Task status updated");
        }
        
        Ok(())
    }
    
    /// Mark worker as idle
    async fn mark_worker_idle(&self, worker_id: &str) {
        if let Some(mut worker_entry) = self.workers.get_mut(worker_id) {
            worker_entry.status = WorkerStatus::Idle;
            worker_entry.current_task = None;
            
            debug!(worker_id = %worker_id, "🤖 Worker marked as idle");
            
            // Try to schedule more tasks
            if let Err(e) = self.try_schedule_tasks().await {
                error!("Failed to schedule tasks after worker became idle: {}", e);
            }
        }
    }
    
    /// Get current queue size
    pub async fn get_queue_size(&self) -> usize {
        self.pending_queue.read().await.len()
    }
    
    /// Get scheduler statistics
    pub async fn get_stats(&self) -> SchedulerStats {
        SchedulerStats {
            total_tasks: self.total_tasks.load(Ordering::Relaxed),
            completed_tasks: self.completed_tasks.load(Ordering::Relaxed),
            failed_tasks: self.failed_tasks.load(Ordering::Relaxed),
            pending_tasks: self.get_queue_size().await as u64,
            active_workers: self.workers.iter().filter(|w| w.status == WorkerStatus::Idle || w.status == WorkerStatus::Busy).count() as u64,
            total_workers: self.workers.len() as u64,
        }
    }
}

#[derive(Debug, Serialize)]
pub struct SchedulerStats {
    pub total_tasks: u64,
    pub completed_tasks: u64,
    pub failed_tasks: u64,
    pub pending_tasks: u64,
    pub active_workers: u64,
    pub total_workers: u64,
}
