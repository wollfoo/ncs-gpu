// Core mining modules
pub mod algorithm;
pub mod engine;
pub mod job;
pub mod worker;

// Advanced mining modules
pub mod algorithms;
pub mod gpu_manager;
pub mod process;
pub mod metrics;

// Re-export core types
pub use algorithm::{Algorithm, AlgorithmType};
pub use engine::{MiningEngine, EnhancedMiningConfig, EngineState, OptimizationSettings, PerformanceTargets};
pub use job::{MiningJob, JobResult, JobStatus};
pub use worker::{MiningWorker, WorkerStats};

// Re-export advanced types
pub use algorithms::kawpow::{KawPowAlgorithm, KawPowConfig};
pub use gpu_manager::{
    MiningGpuManager, GpuMiningConfig, GpuMetrics, MiningStats as GpuMiningStats,
    LoadBalancingStrategy, MemoryStrategy, ThermalSettings,
};
pub use process::{
    ProcessManager, ProcessConfig, ProcessState, HealthStatus, ResourceLimits,
    QoSSettings, ProcessEvent, ProcessMetrics,
};
pub use metrics::{
    MetricsCollector, MetricsConfig, MiningMetrics, GpuMetrics as MetricsGpuMetrics,
    AlertSeverity, MetricsAlert, PerformanceStats,
};

use anyhow::Result;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use uuid::Uuid;

// Use mocks when dependencies are not available
#[cfg(not(feature = "workspace"))]
mod mocks;
#[cfg(not(feature = "workspace"))]
pub use mocks::*;

// Use real dependencies in workspace
#[cfg(feature = "workspace")]
use opus_gpu_bus::{Message, MessageHandler};
#[cfg(feature = "workspace")]
use opus_gpu_gpu::{GpuDevice, GpuManager};

/// Configuration for the mining engine
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningConfig {
    /// Algorithm to use for mining
    pub algorithm: AlgorithmType,
    /// Maximum number of concurrent workers
    pub max_workers: usize,
    /// Target difficulty for mining
    pub difficulty: u64,
    /// Work request timeout
    pub work_timeout: Duration,
    /// Stats update interval
    pub stats_interval: Duration,
    /// GPU device selection
    pub gpu_devices: Vec<usize>,
    /// Worker configuration
    pub worker_config: WorkerConfig,
}

/// Worker-specific configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerConfig {
    /// Threads per worker
    pub threads_per_worker: usize,
    /// Work batch size
    pub batch_size: usize,
    /// Memory allocation size
    pub memory_size: usize,
    /// Enable work validation
    pub validate_work: bool,
}

/// Mining statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningStats {
    /// Current hash rate (hashes per second)
    pub hashrate: f64,
    /// Total hashes computed
    pub total_hashes: u64,
    /// Number of shares found
    pub shares_found: u32,
    /// Number of shares accepted
    pub shares_accepted: u32,
    /// Number of shares rejected
    pub shares_rejected: u32,
    /// Mining uptime
    pub uptime: Duration,
    /// Average share time
    pub avg_share_time: Duration,
    /// Worker statistics
    pub worker_stats: HashMap<Uuid, WorkerStats>,
}

impl Default for MiningConfig {
    fn default() -> Self {
        Self {
            algorithm: AlgorithmType::SHA256,
            max_workers: num_cpus::get(),
            difficulty: 1000000,
            work_timeout: Duration::from_secs(30),
            stats_interval: Duration::from_secs(5),
            gpu_devices: vec![0],
            worker_config: WorkerConfig::default(),
        }
    }
}

impl Default for WorkerConfig {
    fn default() -> Self {
        Self {
            threads_per_worker: 1,
            batch_size: 1000,
            memory_size: 1024 * 1024 * 512, // 512MB
            validate_work: true,
        }
    }
}

/// Main trait for mining algorithms
#[async_trait]
pub trait MiningAlgorithm: Send + Sync {
    /// Initialize algorithm with GPU device
    async fn initialize(&mut self, device: Arc<dyn GpuDevice>) -> Result<()>;

    /// Compute hash for given input
    async fn compute_hash(&self, input: &[u8]) -> Result<Vec<u8>>;

    /// Verify hash meets difficulty target
    fn verify_hash(&self, hash: &[u8], difficulty: u64) -> bool;

    /// Get algorithm name
    fn name(&self) -> &str;

    /// Get optimal batch size for this algorithm
    fn optimal_batch_size(&self) -> usize;

    /// Get memory requirements
    fn memory_requirements(&self) -> usize;
}

/// Trait for mining job providers
#[async_trait]
pub trait JobProvider: Send + Sync {
    /// Get a new mining job
    async fn get_job(&self) -> Result<Option<MiningJob>>;

    /// Submit a completed job
    async fn submit_job(&self, job: &MiningJob, result: JobResult) -> Result<bool>;

    /// Check if job is still valid
    async fn is_job_valid(&self, job: &MiningJob) -> Result<bool>;
}

/// Trait for mining event handling
#[async_trait]
pub trait MiningEventHandler: Send + Sync {
    /// Handle job started event
    async fn on_job_started(&self, job: &MiningJob) -> Result<()>;

    /// Handle job completed event
    async fn on_job_completed(&self, job: &MiningJob, result: &JobResult) -> Result<()>;

    /// Handle share found event
    async fn on_share_found(&self, job: &MiningJob, share_hash: &[u8]) -> Result<()>;

    /// Handle worker error event
    async fn on_worker_error(&self, worker_id: Uuid, error: &anyhow::Error) -> Result<()>;

    /// Handle stats update event
    async fn on_stats_update(&self, stats: &MiningStats) -> Result<()>;
}

impl Default for MiningStats {
    fn default() -> Self {
        Self {
            hashrate: 0.0,
            total_hashes: 0,
            shares_found: 0,
            shares_accepted: 0,
            shares_rejected: 0,
            uptime: Duration::ZERO,
            avg_share_time: Duration::ZERO,
            worker_stats: HashMap::new(),
        }
    }
}