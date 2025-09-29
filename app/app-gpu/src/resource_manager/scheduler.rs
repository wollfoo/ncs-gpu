//! Advanced task scheduler with work-stealing and priority queuing
//!
//! High-performance task scheduling system optimized for mining workloads
//! with adaptive load balancing and thermal-aware scheduling.

use std::collections::{BinaryHeap, HashMap, VecDeque};
use std::sync::atomic::{AtomicU64, AtomicUsize, AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use crossbeam::deque::{Injector, Stealer, Worker};
use crossbeam::utils::Backoff;
use parking_lot::{RwLock, Mutex};
use tokio::sync::{mpsc, oneshot, Semaphore};

use crate::common::error::{OpusError, OpusResult};
use crate::common::metrics::OpusMetrics;
use crate::common::config::SchedulingAlgorithm;

/// Task scheduler with multiple scheduling strategies
pub struct TaskScheduler {
    /// Work-stealing queues for each worker
    workers: Vec<WorkerQueue>,
    /// Global task injector
    injector: Arc<Injector<Task>>,
    /// Worker stealers for work-stealing
    stealers: Vec<Stealer<Task>>,
    /// Priority queue for high-priority tasks
    priority_queue: Arc<Mutex<BinaryHeap<PriorityTask>>>,
    /// Scheduler configuration
    config: SchedulerConfig,
    /// Worker threads
    worker_threads: Vec<tokio::task::JoinHandle<()>>,
    /// Scheduler state
    state: Arc<RwLock<SchedulerState>>,
    /// Metrics collector
    metrics: Option<Arc<OpusMetrics>>,
    /// Shutdown signal
    shutdown: Arc<AtomicBool>,
}

/// Worker queue for work-stealing
struct WorkerQueue {
    /// Worker deque
    worker: Worker<Task>,
    /// Worker ID
    worker_id: usize,
    /// Local task statistics
    stats: Arc<RwLock<WorkerStats>>,
    /// Thermal throttling state
    thermal_throttle: Arc<AtomicU64>, // Throttle level (0-100)
}

/// Scheduled task
#[derive(Debug)]
pub struct Task {
    /// Task identifier
    pub id: String,
    /// Task function
    pub function: TaskFunction,
    /// Task priority (0-255, higher = more priority)
    pub priority: u8,
    /// Task category
    pub category: TaskCategory,
    /// Preferred worker affinity
    pub worker_affinity: Option<usize>,
    /// GPU device affinity
    pub device_affinity: Option<u32>,
    /// Task constraints
    pub constraints: TaskConstraints,
    /// Task metadata
    pub metadata: TaskMetadata,
    /// Completion callback
    pub completion_tx: Option<oneshot::Sender<TaskResult>>,
}

/// Task function type
pub type TaskFunction = Box<dyn FnOnce() -> TaskResult + Send + 'static>;

/// Task execution result
#[derive(Debug)]
pub struct TaskResult {
    /// Task ID
    pub task_id: String,
    /// Execution status
    pub status: TaskStatus,
    /// Execution time
    pub execution_time: Duration,
    /// Output data
    pub output: Option<Vec<u8>>,
    /// Error message if failed
    pub error: Option<String>,
}

/// Task execution status
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TaskStatus {
    /// Task completed successfully
    Completed,
    /// Task failed with error
    Failed,
    /// Task was cancelled
    Cancelled,
    /// Task timed out
    TimedOut,
}

/// Task categories for scheduling optimization
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum TaskCategory {
    /// GPU mining computation
    Mining,
    /// Memory allocation/deallocation
    Memory,
    /// Network I/O
    Network,
    /// File I/O
    FileIo,
    /// Background maintenance
    Maintenance,
    /// System monitoring
    Monitoring,
    /// User interface
    UserInterface,
}

/// Task constraints
#[derive(Debug, Clone, Default)]
pub struct TaskConstraints {
    /// Maximum execution time
    pub timeout: Option<Duration>,
    /// Minimum CPU cores required
    pub min_cpu_cores: Option<usize>,
    /// Memory requirement (bytes)
    pub memory_requirement: Option<u64>,
    /// GPU memory requirement (bytes)
    pub gpu_memory_requirement: Option<u64>,
    /// Exclusive GPU access required
    pub exclusive_gpu: bool,
    /// Can be preempted by higher priority tasks
    pub preemptible: bool,
}

/// Task metadata
#[derive(Debug, Clone, Default)]
pub struct TaskMetadata {
    /// Task creation timestamp
    pub created_at: Instant,
    /// Task submission timestamp
    pub submitted_at: Option<Instant>,
    /// Task start timestamp
    pub started_at: Option<Instant>,
    /// Task completion timestamp
    pub completed_at: Option<Instant>,
    /// Task source/origin
    pub source: Option<String>,
    /// Additional context data
    pub context: HashMap<String, String>,
}

/// Priority task wrapper for priority queue
#[derive(Debug)]
struct PriorityTask {
    task: Task,
    effective_priority: u64,
    submission_time: Instant,
}

impl PartialEq for PriorityTask {
    fn eq(&self, other: &Self) -> bool {
        self.effective_priority == other.effective_priority
    }
}

impl Eq for PriorityTask {}

impl PartialOrd for PriorityTask {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for PriorityTask {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        // Higher priority first, then older tasks first
        self.effective_priority.cmp(&other.effective_priority)
            .then_with(|| other.submission_time.cmp(&self.submission_time))
    }
}

/// Worker statistics
#[derive(Debug, Clone, Default)]
pub struct WorkerStats {
    /// Total tasks executed
    pub tasks_executed: u64,
    /// Total execution time
    pub total_execution_time: Duration,
    /// Average execution time
    pub average_execution_time: Duration,
    /// Failed tasks
    pub failed_tasks: u64,
    /// Stolen tasks
    pub stolen_tasks: u64,
    /// Tasks given to other workers
    pub given_tasks: u64,
    /// Current load (0.0-1.0)
    pub current_load: f64,
}

/// Scheduler configuration
#[derive(Debug, Clone)]
pub struct SchedulerConfig {
    /// Number of worker threads
    pub worker_count: usize,
    /// Scheduling algorithm
    pub algorithm: SchedulingAlgorithm,
    /// Task queue capacity
    pub queue_capacity: usize,
    /// Enable work stealing
    pub work_stealing: bool,
    /// Work stealing attempt limit
    pub steal_attempts: usize,
    /// Priority boost for aging tasks
    pub priority_boost_interval: Duration,
    /// Maximum task execution time
    pub max_task_duration: Duration,
    /// Enable thermal-aware scheduling
    pub thermal_aware: bool,
    /// Load balancing interval
    pub load_balance_interval: Duration,
}

impl Default for SchedulerConfig {
    fn default() -> Self {
        Self {
            worker_count: num_cpus::get(),
            algorithm: SchedulingAlgorithm::WorkStealing,
            queue_capacity: 10000,
            work_stealing: true,
            steal_attempts: 3,
            priority_boost_interval: Duration::from_secs(60),
            max_task_duration: Duration::from_secs(300),
            thermal_aware: true,
            load_balance_interval: Duration::from_secs(5),
        }
    }
}

/// Scheduler state
#[derive(Debug, Clone)]
pub struct SchedulerState {
    /// Total tasks submitted
    pub total_tasks: u64,
    /// Currently executing tasks
    pub executing_tasks: u64,
    /// Completed tasks
    pub completed_tasks: u64,
    /// Failed tasks
    pub failed_tasks: u64,
    /// Average task latency
    pub average_latency: Duration,
    /// Current throughput (tasks/second)
    pub throughput: f64,
    /// Worker utilization
    pub worker_utilization: Vec<f64>,
}

impl TaskScheduler {
    /// Create new task scheduler
    pub async fn new(
        config: SchedulerConfig,
        metrics: Option<Arc<OpusMetrics>>,
    ) -> OpusResult<Self> {
        let injector = Arc::new(Injector::new());
        let mut workers = Vec::with_capacity(config.worker_count);
        let mut stealers = Vec::with_capacity(config.worker_count);

        // Create worker queues
        for i in 0..config.worker_count {
            let worker = Worker::new_fifo();
            let stealer = worker.stealer();

            let worker_queue = WorkerQueue {
                worker,
                worker_id: i,
                stats: Arc::new(RwLock::new(WorkerStats::default())),
                thermal_throttle: Arc::new(AtomicU64::new(0)),
            };

            workers.push(worker_queue);
            stealers.push(stealer);
        }

        let state = SchedulerState {
            total_tasks: 0,
            executing_tasks: 0,
            completed_tasks: 0,
            failed_tasks: 0,
            average_latency: Duration::from_millis(0),
            throughput: 0.0,
            worker_utilization: vec![0.0; config.worker_count],
        };

        Ok(Self {
            workers,
            injector,
            stealers,
            priority_queue: Arc::new(Mutex::new(BinaryHeap::new())),
            config,
            worker_threads: Vec::new(),
            state: Arc::new(RwLock::new(state)),
            metrics,
            shutdown: Arc::new(AtomicBool::new(false)),
        })
    }

    /// Start the scheduler
    pub async fn start(&mut self) -> OpusResult<()> {
        // Start worker threads
        for (i, worker_queue) in self.workers.iter().enumerate() {
            let injector = self.injector.clone();
            let stealers = self.stealers.clone();
            let priority_queue = self.priority_queue.clone();
            let state = self.state.clone();
            let metrics = self.metrics.clone();
            let shutdown = self.shutdown.clone();
            let config = self.config.clone();

            // Clone worker queue components
            let stealer = worker_queue.worker.stealer();
            let stats = worker_queue.stats.clone();
            let thermal_throttle = worker_queue.thermal_throttle.clone();

            let handle = tokio::spawn(async move {
                Self::worker_loop(
                    i,
                    stealer,
                    injector,
                    stealers,
                    priority_queue,
                    state,
                    metrics,
                    shutdown,
                    config,
                    stats,
                    thermal_throttle,
                ).await;
            });

            self.worker_threads.push(handle);
        }

        // Start load balancer
        let state = self.state.clone();
        let metrics = self.metrics.clone();
        let shutdown = self.shutdown.clone();
        let interval = self.config.load_balance_interval;

        let load_balancer = tokio::spawn(async move {
            Self::load_balancer_loop(state, metrics, shutdown, interval).await;
        });

        self.worker_threads.push(load_balancer);

        Ok(())
    }

    /// Submit task for execution
    pub async fn submit_task(&self, mut task: Task) -> OpusResult<oneshot::Receiver<TaskResult>> {
        let (tx, rx) = oneshot::channel();
        task.completion_tx = Some(tx);
        task.metadata.submitted_at = Some(Instant::now());

        // Update state
        {
            let mut state = self.state.write();
            state.total_tasks += 1;
        }

        // Determine scheduling strategy
        match self.config.algorithm {
            SchedulingAlgorithm::Priority => {
                self.submit_priority_task(task).await?;
            }
            SchedulingAlgorithm::RoundRobin => {
                self.submit_round_robin_task(task).await?;
            }
            SchedulingAlgorithm::WorkStealing => {
                self.submit_work_stealing_task(task).await?;
            }
        }

        Ok(rx)
    }

    /// Submit task with priority scheduling
    async fn submit_priority_task(&self, task: Task) -> OpusResult<()> {
        let priority_task = PriorityTask {
            effective_priority: self.calculate_effective_priority(&task),
            submission_time: Instant::now(),
            task,
        };

        self.priority_queue.lock().push(priority_task);
        Ok(())
    }

    /// Submit task with round-robin scheduling
    async fn submit_round_robin_task(&self, task: Task) -> OpusResult<()> {
        static ROUND_ROBIN_COUNTER: AtomicUsize = AtomicUsize::new(0);

        let worker_id = ROUND_ROBIN_COUNTER.fetch_add(1, Ordering::Relaxed) % self.workers.len();

        if let Some(worker) = self.workers.get(worker_id) {
            worker.worker.push(task);
        } else {
            self.injector.push(task);
        }

        Ok(())
    }

    /// Submit task with work-stealing scheduling
    async fn submit_work_stealing_task(&self, task: Task) -> OpusResult<()> {
        // Try to submit to preferred worker if specified
        if let Some(worker_id) = task.worker_affinity {
            if let Some(worker) = self.workers.get(worker_id) {
                worker.worker.push(task);
                return Ok(());
            }
        }

        // Submit to global injector
        self.injector.push(task);
        Ok(())
    }

    /// Calculate effective priority based on task properties and aging
    fn calculate_effective_priority(&self, task: &Task) -> u64 {
        let base_priority = task.priority as u64;
        let age_factor = task.metadata.created_at.elapsed().as_secs() / 60; // Age in minutes
        let category_boost = match task.category {
            TaskCategory::Mining => 50,
            TaskCategory::Memory => 30,
            TaskCategory::Network => 20,
            TaskCategory::FileIo => 10,
            TaskCategory::Monitoring => 5,
            TaskCategory::Maintenance => 1,
            TaskCategory::UserInterface => 100,
        };

        base_priority + age_factor + category_boost
    }

    /// Update thermal throttling for worker
    pub fn set_thermal_throttle(&self, worker_id: usize, throttle_level: u8) -> OpusResult<()> {
        if let Some(worker) = self.workers.get(worker_id) {
            worker.thermal_throttle.store(throttle_level as u64, Ordering::Relaxed);
        }
        Ok(())
    }

    /// Get scheduler statistics
    pub fn get_statistics(&self) -> SchedulerState {
        self.state.read().clone()
    }

    /// Get worker statistics
    pub fn get_worker_statistics(&self) -> Vec<WorkerStats> {
        self.workers.iter().map(|w| w.stats.read().clone()).collect()
    }

    /// Shutdown scheduler
    pub async fn shutdown(&mut self) -> OpusResult<()> {
        self.shutdown.store(true, Ordering::Relaxed);

        // Wait for all worker threads to complete
        for handle in self.worker_threads.drain(..) {
            let _ = handle.await;
        }

        Ok(())
    }

    /// Worker loop for executing tasks
    async fn worker_loop(
        worker_id: usize,
        stealer: Stealer<Task>,
        injector: Arc<Injector<Task>>,
        stealers: Vec<Stealer<Task>>,
        priority_queue: Arc<Mutex<BinaryHeap<PriorityTask>>>,
        state: Arc<RwLock<SchedulerState>>,
        metrics: Option<Arc<OpusMetrics>>,
        shutdown: Arc<AtomicBool>,
        config: SchedulerConfig,
        stats: Arc<RwLock<WorkerStats>>,
        thermal_throttle: Arc<AtomicU64>,
    ) {
        let backoff = Backoff::new();

        while !shutdown.load(Ordering::Relaxed) {
            // Check thermal throttling
            let throttle_level = thermal_throttle.load(Ordering::Relaxed);
            if throttle_level > 0 {
                let delay_ms = (throttle_level * 10) as u64; // Up to 1 second delay
                tokio::time::sleep(Duration::from_millis(delay_ms)).await;
            }

            // Try to get task from various sources
            let task = Self::find_task(
                &stealer,
                &injector,
                &stealers,
                &priority_queue,
                &config,
                worker_id,
            );

            if let Some(task) = task {
                // Execute task
                let execution_start = Instant::now();

                // Update state
                {
                    let mut state = state.write();
                    state.executing_tasks += 1;
                }

                let result = Self::execute_task(task, &config).await;
                let execution_time = execution_start.elapsed();

                // Update statistics
                {
                    let mut worker_stats = stats.write();
                    worker_stats.tasks_executed += 1;
                    worker_stats.total_execution_time += execution_time;
                    worker_stats.average_execution_time =
                        worker_stats.total_execution_time / worker_stats.tasks_executed as u32;

                    if result.status != TaskStatus::Completed {
                        worker_stats.failed_tasks += 1;
                    }
                }

                // Update global state
                {
                    let mut state = state.write();
                    state.executing_tasks -= 1;
                    if result.status == TaskStatus::Completed {
                        state.completed_tasks += 1;
                    } else {
                        state.failed_tasks += 1;
                    }
                }

                // Record metrics
                if let Some(metrics) = &metrics {
                    metrics.record_operation_duration(
                        "task_execution",
                        &format!("worker_{}", worker_id),
                        execution_time,
                    );
                }

                backoff.reset();
            } else {
                // No work found, back off
                backoff.snooze();
            }
        }
    }

    /// Find task from available sources
    fn find_task(
        local_stealer: &Stealer<Task>,
        injector: &Arc<Injector<Task>>,
        stealers: &[Stealer<Task>],
        priority_queue: &Arc<Mutex<BinaryHeap<PriorityTask>>>,
        config: &SchedulerConfig,
        worker_id: usize,
    ) -> Option<Task> {
        // 1. Try local work-stealing queue
        if let crossbeam::deque::Steal::Success(task) = local_stealer.steal() {
            return Some(task);
        }

        // 2. Try priority queue
        if let Ok(mut pq) = priority_queue.try_lock() {
            if let Some(priority_task) = pq.pop() {
                return Some(priority_task.task);
            }
        }

        // 3. Try global injector
        if let crossbeam::deque::Steal::Success(task) = injector.steal() {
            return Some(task);
        }

        // 4. Try stealing from other workers
        if config.work_stealing {
            for (i, stealer) in stealers.iter().enumerate() {
                if i != worker_id {
                    if let crossbeam::deque::Steal::Success(task) = stealer.steal() {
                        return Some(task);
                    }
                }
            }
        }

        None
    }

    /// Execute a single task
    async fn execute_task(mut task: Task, config: &SchedulerConfig) -> TaskResult {
        let start_time = Instant::now();
        task.metadata.started_at = Some(start_time);

        // Set up timeout
        let timeout = task.constraints.timeout.unwrap_or(config.max_task_duration);

        let result = tokio::time::timeout(timeout, async move {
            // Execute task function
            let function = task.function;
            let result = tokio::task::spawn_blocking(move || function()).await;

            match result {
                Ok(task_result) => task_result,
                Err(e) => TaskResult {
                    task_id: task.id.clone(),
                    status: TaskStatus::Failed,
                    execution_time: start_time.elapsed(),
                    output: None,
                    error: Some(format!("Task execution error: {}", e)),
                },
            }
        }).await;

        let mut final_result = match result {
            Ok(mut task_result) => {
                task_result.execution_time = start_time.elapsed();
                task_result
            }
            Err(_) => TaskResult {
                task_id: task.id.clone(),
                status: TaskStatus::TimedOut,
                execution_time: start_time.elapsed(),
                output: None,
                error: Some("Task timed out".to_string()),
            },
        };

        // Send result through completion channel
        if let Some(tx) = task.completion_tx {
            let _ = tx.send(final_result.clone());
        }

        final_result
    }

    /// Load balancer loop
    async fn load_balancer_loop(
        state: Arc<RwLock<SchedulerState>>,
        metrics: Option<Arc<OpusMetrics>>,
        shutdown: Arc<AtomicBool>,
        interval: Duration,
    ) {
        let mut interval_timer = tokio::time::interval(interval);

        while !shutdown.load(Ordering::Relaxed) {
            interval_timer.tick().await;

            // Update scheduler statistics
            let current_throughput = {
                let state = state.read();
                state.completed_tasks as f64 / interval.as_secs_f64()
            };

            {
                let mut state = state.write();
                state.throughput = current_throughput;
                // Reset counters for next interval
                // (In practice, you'd use a sliding window)
            }

            // Record metrics
            if let Some(metrics) = &metrics {
                // Record scheduler metrics here
            }
        }
    }
}

/// Task builder for easy task creation
pub struct TaskBuilder {
    id: String,
    priority: u8,
    category: TaskCategory,
    worker_affinity: Option<usize>,
    device_affinity: Option<u32>,
    constraints: TaskConstraints,
    metadata: TaskMetadata,
}

impl TaskBuilder {
    /// Create new task builder
    pub fn new(id: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            priority: 128, // Default priority
            category: TaskCategory::Mining,
            worker_affinity: None,
            device_affinity: None,
            constraints: TaskConstraints::default(),
            metadata: TaskMetadata {
                created_at: Instant::now(),
                ..Default::default()
            },
        }
    }

    /// Set task priority
    pub fn priority(mut self, priority: u8) -> Self {
        self.priority = priority;
        self
    }

    /// Set task category
    pub fn category(mut self, category: TaskCategory) -> Self {
        self.category = category;
        self
    }

    /// Set worker affinity
    pub fn worker_affinity(mut self, worker_id: usize) -> Self {
        self.worker_affinity = Some(worker_id);
        self
    }

    /// Set device affinity
    pub fn device_affinity(mut self, device_id: u32) -> Self {
        self.device_affinity = Some(device_id);
        self
    }

    /// Set task timeout
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.constraints.timeout = Some(timeout);
        self
    }

    /// Set memory requirement
    pub fn memory_requirement(mut self, bytes: u64) -> Self {
        self.constraints.memory_requirement = Some(bytes);
        self
    }

    /// Build task with function
    pub fn build<F, R>(self, function: F) -> Task
    where
        F: FnOnce() -> R + Send + 'static,
        R: Into<TaskResult>,
    {
        let task_id = self.id.clone();
        let wrapped_function = Box::new(move || function().into());

        Task {
            id: self.id,
            function: wrapped_function,
            priority: self.priority,
            category: self.category,
            worker_affinity: self.worker_affinity,
            device_affinity: self.device_affinity,
            constraints: self.constraints,
            metadata: self.metadata,
            completion_tx: None,
        }
    }
}

/// Simple task result conversion
impl From<()> for TaskResult {
    fn from(_: ()) -> Self {
        TaskResult {
            task_id: String::new(),
            status: TaskStatus::Completed,
            execution_time: Duration::from_millis(0),
            output: None,
            error: None,
        }
    }
}

impl From<String> for TaskResult {
    fn from(output: String) -> Self {
        TaskResult {
            task_id: String::new(),
            status: TaskStatus::Completed,
            execution_time: Duration::from_millis(0),
            output: Some(output.into_bytes()),
            error: None,
        }
    }
}

impl From<Result<String, String>> for TaskResult {
    fn from(result: Result<String, String>) -> Self {
        match result {
            Ok(output) => TaskResult {
                task_id: String::new(),
                status: TaskStatus::Completed,
                execution_time: Duration::from_millis(0),
                output: Some(output.into_bytes()),
                error: None,
            },
            Err(error) => TaskResult {
                task_id: String::new(),
                status: TaskStatus::Failed,
                execution_time: Duration::from_millis(0),
                output: None,
                error: Some(error),
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_scheduler_creation() {
        let config = SchedulerConfig::default();
        let scheduler = TaskScheduler::new(config, None).await.unwrap();

        let stats = scheduler.get_statistics();
        assert_eq!(stats.total_tasks, 0);
        assert_eq!(stats.executing_tasks, 0);
    }

    #[tokio::test]
    async fn test_task_builder() {
        let task = TaskBuilder::new("test_task")
            .priority(200)
            .category(TaskCategory::Mining)
            .timeout(Duration::from_secs(10))
            .build(|| "Task completed".to_string());

        assert_eq!(task.id, "test_task");
        assert_eq!(task.priority, 200);
        assert_eq!(task.category, TaskCategory::Mining);
        assert_eq!(task.constraints.timeout, Some(Duration::from_secs(10)));
    }

    #[test]
    fn test_priority_task_ordering() {
        let mut heap = BinaryHeap::new();

        let task1 = PriorityTask {
            task: TaskBuilder::new("task1").priority(100).build(|| ()),
            effective_priority: 100,
            submission_time: Instant::now(),
        };

        let task2 = PriorityTask {
            task: TaskBuilder::new("task2").priority(200).build(|| ()),
            effective_priority: 200,
            submission_time: Instant::now(),
        };

        heap.push(task1);
        heap.push(task2);

        let top = heap.pop().unwrap();
        assert_eq!(top.effective_priority, 200);

        let next = heap.pop().unwrap();
        assert_eq!(next.effective_priority, 100);
    }

    #[test]
    fn test_worker_stats() {
        let mut stats = WorkerStats::default();
        assert_eq!(stats.tasks_executed, 0);
        assert_eq!(stats.failed_tasks, 0);
        assert_eq!(stats.current_load, 0.0);

        stats.tasks_executed = 100;
        stats.total_execution_time = Duration::from_secs(50);
        stats.average_execution_time = stats.total_execution_time / stats.tasks_executed as u32;

        assert_eq!(stats.average_execution_time, Duration::from_millis(500));
    }

    #[test]
    fn test_task_constraints() {
        let constraints = TaskConstraints {
            timeout: Some(Duration::from_secs(30)),
            min_cpu_cores: Some(4),
            memory_requirement: Some(1024 * 1024 * 1024), // 1GB
            gpu_memory_requirement: Some(512 * 1024 * 1024), // 512MB
            exclusive_gpu: true,
            preemptible: false,
        };

        assert_eq!(constraints.timeout, Some(Duration::from_secs(30)));
        assert_eq!(constraints.min_cpu_cores, Some(4));
        assert!(constraints.exclusive_gpu);
        assert!(!constraints.preemptible);
    }
}