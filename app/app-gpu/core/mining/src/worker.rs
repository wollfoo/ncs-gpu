use crate::{
    algorithm::Algorithm,
    job::{MiningJob, JobResult, JobStatus},
    WorkerConfig,
};
use anyhow::Result;
use opus_gpu_bus::{Message, MessageBus};
use opus_gpu_gpu::GpuDevice;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime};
use tokio::sync::{mpsc, oneshot};
use tokio::time::interval;
use tracing::{debug, error, info, warn};
use uuid::Uuid;

/// Individual mining worker statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerStats {
    /// Worker ID
    pub worker_id: Uuid,
    /// Current hash rate (hashes per second)
    pub hashrate: f64,
    /// Total hashes computed by this worker
    pub total_hashes: u64,
    /// Number of jobs completed
    pub jobs_completed: u32,
    /// Number of shares found
    pub shares_found: u32,
    /// Worker uptime
    pub uptime: Duration,
    /// Current temperature (if available)
    pub temperature: Option<f32>,
    /// Memory usage
    pub memory_usage: u64,
    /// Worker status
    pub status: WorkerStatus,
    /// Last activity timestamp
    pub last_activity: SystemTime,
}

/// Worker status
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum WorkerStatus {
    Idle,
    Mining,
    Paused,
    Error,
    Stopped,
}

/// Worker command types
#[derive(Debug)]
pub enum WorkerCommand {
    StartMining(MiningJob),
    StopMining,
    Pause,
    Resume,
    UpdateConfig(WorkerConfig),
    Shutdown,
}

/// Mining worker that runs on a single GPU device
pub struct MiningWorker {
    id: Uuid,
    device: Arc<dyn GpuDevice>,
    algorithm: Algorithm,
    config: WorkerConfig,
    message_bus: Arc<MessageBus>,

    // Worker state
    stats: Arc<RwLock<WorkerStats>>,
    current_job: Arc<RwLock<Option<MiningJob>>>,
    start_time: Instant,

    // Control channels
    command_tx: Option<mpsc::Sender<WorkerCommand>>,
    shutdown_tx: Option<oneshot::Sender<()>>,
    is_running: Arc<RwLock<bool>>,
}

impl MiningWorker {
    /// Create a new mining worker
    pub async fn new(
        id: Uuid,
        device: Arc<dyn GpuDevice>,
        mut algorithm: Algorithm,
        config: WorkerConfig,
        message_bus: Arc<MessageBus>,
    ) -> Result<Self> {
        info!("🔧 Initializing mining worker {}", id);

        // Initialize algorithm with GPU device
        algorithm.initialize(device.clone()).await?;

        let stats = WorkerStats {
            worker_id: id,
            hashrate: 0.0,
            total_hashes: 0,
            jobs_completed: 0,
            shares_found: 0,
            uptime: Duration::ZERO,
            temperature: None,
            memory_usage: 0,
            status: WorkerStatus::Idle,
            last_activity: SystemTime::now(),
        };

        Ok(Self {
            id,
            device,
            algorithm,
            config,
            message_bus,
            stats: Arc::new(RwLock::new(stats)),
            current_job: Arc::new(RwLock::new(None)),
            start_time: Instant::now(),
            command_tx: None,
            shutdown_tx: None,
            is_running: Arc::new(RwLock::new(false)),
        })
    }

    /// Start the mining worker
    pub async fn start(&self) -> Result<()> {
        info!("🚀 Starting mining worker {}", self.id);

        *self.is_running.write() = true;
        self.stats.write().status = WorkerStatus::Idle;

        let (command_tx, mut command_rx) = mpsc::channel::<WorkerCommand>(100);
        let (shutdown_tx, shutdown_rx) = oneshot::channel();

        // Start worker main loop
        let worker_id = self.id;
        let algorithm = self.algorithm.clone();
        let config = self.config.clone();
        let stats = self.stats.clone();
        let current_job = self.current_job.clone();
        let message_bus = self.message_bus.clone();
        let is_running = self.is_running.clone();

        tokio::spawn(async move {
            let mut shutdown_rx = shutdown_rx;
            let mut stats_interval = interval(Duration::from_secs(5));

            loop {
                tokio::select! {
                    command = command_rx.recv() => {
                        if let Some(cmd) = command {
                            if let Err(e) = Self::handle_command(
                                cmd,
                                &algorithm,
                                &config,
                                &stats,
                                &current_job,
                                &message_bus,
                                worker_id,
                            ).await {
                                error!("Worker {} command error: {}", worker_id, e);
                            }
                        } else {
                            break; // Channel closed
                        }
                    }
                    _ = stats_interval.tick() => {
                        Self::update_worker_stats(&stats, worker_id).await;
                    }
                    _ = &mut shutdown_rx => {
                        info!("Worker {} received shutdown signal", worker_id);
                        break;
                    }
                }
            }

            *is_running.write() = false;
            stats.write().status = WorkerStatus::Stopped;
            info!("✅ Worker {} stopped", worker_id);
        });

        info!("✅ Mining worker {} started", self.id);
        Ok(())
    }

    /// Stop the mining worker
    pub async fn stop(&self) -> Result<()> {
        info!("🛑 Stopping mining worker {}", self.id);

        *self.is_running.write() = false;

        if let Some(shutdown_tx) = &self.shutdown_tx {
            let _ = shutdown_tx.send(());
        }

        self.stats.write().status = WorkerStatus::Stopped;
        info!("✅ Worker {} stopped", self.id);
        Ok(())
    }

    /// Assign a new mining job to this worker
    pub async fn assign_job(&self, job: MiningJob) -> Result<()> {
        debug!("📋 Assigning job {} to worker {}", job.id, self.id);

        if let Some(command_tx) = &self.command_tx {
            command_tx.send(WorkerCommand::StartMining(job)).await?;
        }

        Ok(())
    }

    /// Get current worker statistics
    pub async fn get_stats(&self) -> WorkerStats {
        let mut stats = self.stats.read().clone();
        stats.uptime = self.start_time.elapsed();
        stats
    }

    /// Handle worker commands
    async fn handle_command(
        command: WorkerCommand,
        algorithm: &Algorithm,
        config: &WorkerConfig,
        stats: &Arc<RwLock<WorkerStats>>,
        current_job: &Arc<RwLock<Option<MiningJob>>>,
        message_bus: &Arc<MessageBus>,
        worker_id: Uuid,
    ) -> Result<()> {
        match command {
            WorkerCommand::StartMining(job) => {
                info!("⛏️ Worker {} starting job {}", worker_id, job.id);
                stats.write().status = WorkerStatus::Mining;
                *current_job.write() = Some(job.clone());

                // Execute mining job
                let result = Self::execute_mining_job(
                    &job,
                    algorithm,
                    config,
                    stats,
                    worker_id,
                ).await?;

                // Send result via message bus
                let message = Message::new(
                    "mining.job_completed".to_string(),
                    serde_json::to_value(&result)?,
                    None,
                );
                message_bus.publish(message).await?;

                stats.write().jobs_completed += 1;
                if result.meets_target {
                    stats.write().shares_found += 1;
                }

                stats.write().status = WorkerStatus::Idle;
                *current_job.write() = None;
            }
            WorkerCommand::StopMining => {
                info!("⏹️ Worker {} stopping mining", worker_id);
                stats.write().status = WorkerStatus::Idle;
                *current_job.write() = None;
            }
            WorkerCommand::Pause => {
                info!("⏸️ Worker {} paused", worker_id);
                stats.write().status = WorkerStatus::Paused;
            }
            WorkerCommand::Resume => {
                info!("▶️ Worker {} resumed", worker_id);
                stats.write().status = WorkerStatus::Idle;
            }
            WorkerCommand::UpdateConfig(_new_config) => {
                info!("⚙️ Worker {} config updated", worker_id);
                // Config update logic would go here
            }
            WorkerCommand::Shutdown => {
                info!("🛑 Worker {} shutting down", worker_id);
                return Ok(());
            }
        }

        Ok(())
    }

    /// Execute a mining job
    async fn execute_mining_job(
        job: &MiningJob,
        algorithm: &Algorithm,
        config: &WorkerConfig,
        stats: &Arc<RwLock<WorkerStats>>,
        worker_id: Uuid,
    ) -> Result<JobResult> {
        let start_time = Instant::now();
        let mut hashes_computed = 0u64;
        let mut found_nonce = None;
        let mut meets_target = false;

        // Mining loop
        let batch_size = config.batch_size.min(algorithm.optimal_batch_size());
        let mut current_nonce = job.nonce_start;

        while current_nonce < job.nonce_end && !job.is_expired() {
            // Process batch of nonces
            for nonce in current_nonce..=(current_nonce + batch_size as u64).min(job.nonce_end) {
                // Prepare mining input with nonce
                let mut mining_input = job.data.clone();
                mining_input.extend_from_slice(&nonce.to_le_bytes());

                // Compute hash
                let hash = algorithm.compute_hash(&mining_input).await?;
                hashes_computed += 1;

                // Check if hash meets difficulty target
                if algorithm.verify_hash(&hash, job.difficulty) {
                    found_nonce = Some(nonce);
                    meets_target = true;
                    break;
                }

                // Update stats periodically
                if hashes_computed % 1000 == 0 {
                    let elapsed = start_time.elapsed();
                    let hashrate = if elapsed.as_secs_f64() > 0.0 {
                        hashes_computed as f64 / elapsed.as_secs_f64()
                    } else {
                        0.0
                    };

                    let mut worker_stats = stats.write();
                    worker_stats.hashrate = hashrate;
                    worker_stats.total_hashes += 1000;
                    worker_stats.last_activity = SystemTime::now();
                }
            }

            if meets_target {
                break;
            }

            current_nonce += batch_size as u64 + 1;

            // Yield to allow other tasks to run
            tokio::task::yield_now().await;
        }

        let duration = start_time.elapsed();
        let final_hash = if let Some(nonce) = found_nonce {
            let mut mining_input = job.data.clone();
            mining_input.extend_from_slice(&nonce.to_le_bytes());
            algorithm.compute_hash(&mining_input).await?
        } else {
            Vec::new()
        };

        Ok(JobResult::new(
            job.id,
            found_nonce,
            final_hash,
            hashes_computed,
            duration,
            meets_target,
            worker_id,
        ))
    }

    /// Update worker statistics
    async fn update_worker_stats(stats: &Arc<RwLock<WorkerStats>>, worker_id: Uuid) {
        let mut worker_stats = stats.write();
        worker_stats.last_activity = SystemTime::now();

        debug!("📊 Worker {} stats - Hashrate: {:.2} H/s",
               worker_id, worker_stats.hashrate);
    }

    /// Check if worker is running
    pub fn is_running(&self) -> bool {
        *self.is_running.read()
    }

    /// Get worker ID
    pub fn id(&self) -> Uuid {
        self.id
    }

    /// Get current job
    pub async fn get_current_job(&self) -> Option<MiningJob> {
        self.current_job.read().clone()
    }
}

impl Default for WorkerStats {
    fn default() -> Self {
        Self {
            worker_id: Uuid::new_v4(),
            hashrate: 0.0,
            total_hashes: 0,
            jobs_completed: 0,
            shares_found: 0,
            uptime: Duration::ZERO,
            temperature: None,
            memory_usage: 0,
            status: WorkerStatus::Idle,
            last_activity: SystemTime::now(),
        }
    }
}