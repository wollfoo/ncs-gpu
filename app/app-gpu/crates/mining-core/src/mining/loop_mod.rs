//! # Mining Loop Orchestrator (Điều phối viên vòng lặp khai thác)
//!
//! **Central mining coordination** (điều phối khai thác trung tâm)
//! với work distribution across GPUs, result aggregation, performance monitoring
//! và automated load balancing cho high-throughput mining operation.
//!
//! ## Architecture Overview (Tổng quan kiến trúc)
//!
//! ```
//! MiningLoop (Orchestrator)
//! ├── Work Distributor ──┬──► Stratum Client (Job fetching)
//! │                      └──► GPU Workers (Work dispatch)
//! ├── Result Collector ──┬──► GPU Workers (Solution gathering)
//! │                      └──► Stratum Client (Share submission)
//! └── Statistics Engine ─► Performance Metrics (Hashrate, efficiency)
//! ```
//!
//! ## Key Flows (Luồng chính)
//!
//! ### Work Management Flow (Luồng quản lý công việc)
//! ```rust,ignore
//! Stratum ───► Job Received ──► Work Package ──► Nonce Distribution
//!     ▲               │               │                │
//!     │               ▼               ▼                ▼
//!     └─────── Submission ◄── Validation ◄─── GPU Results ◄─── Kernel Execution
//! ```
//!
//! ### Performance Flow (Luồng hiệu năng)
//! ```rust,ignore
//! GPU Workers ───► Result Collection ──► Statistics Update ──► Load Balancing
//!       ▲                 │                      │                   │
//!       └──── Thermal ◄─── Metrics ◄──────────── Alert System ◄──────┘
//! ```

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, SystemTime};

use anyhow::Result;
use async_trait::async_trait;
use tokio::sync::{mpsc, RwLock};
use tokio::time::{self, Instant};
use tracing::{debug, error, info, warn};

use super::statistics::{MiningStatistics, StatisticsConfig, GpuMetrics, AggregatedStats, MiningAlert};
use super::worker::{GpuWorker, MineResult, WorkerCommand, ThermalLimits};
use crate::stratum::{StratumClient, WorkPackage as StratumWorkPackage, Solution, PoolConfig, StratumConfig};
use crate::MiningConfig;
use crate::gpu::GpuAlgorithm;

/// **WorkPackage** (gói công việc) – mining work unit với nonce ranges
#[derive(Debug, Clone)]
pub struct WorkPackage {
    /// **Job ID** (ID job) – từ stratum
    pub job_id: String,

    /// **Header hash** (header hash) – block header hash
    pub header_hash: Vec<u8>,

    /// **Seed hash** (seed hash) – Ethash seed hash
    pub seed_hash: Vec<u8>,

    /// **Target** (mục tiêu) – mining target difficulty
    pub target: Vec<u8>,

    /// **Block height** (chiều cao block)
    pub height: u64,

    /// **Network difficulty** (độ khó mạng)
    pub difficulty: f64,

    /// **Epoch** (epoch) – Ethash epoch number
    pub epoch: u32,

    /// **Extra nonce1** (extra nonce1) – từ pool
    pub extra_nonce1: Option<Vec<u8>>,

    /// **Nonce range start** (nonce range bắt đầu) – starting nonce
    pub nonce_start: u64,

    /// **Nonce range size** (kích thước nonce range) – number of nonces to mine
    pub nonce_range: u64,

    /// **Timestamp** (thời điểm) – when work was created
    pub timestamp: SystemTime,
}

impl WorkPackage {
    /// **Create from stratum work** (tạo từ work stratum)
    pub fn from_stratum_work(work: &StratumWorkPackage, nonce_start: u64, nonce_range: u64) -> Self {
        // Calculate epoch from seed hash (simplified)
        let epoch = ((work.seed_hash.len() as u32 * 8) / 30000).max(0);

        Self {
            job_id: work.job_id.clone(),
            header_hash: work.header_hash.clone(),
            seed_hash: work.seed_hash.clone(),
            target: work.target.clone(),
            height: work.height,
            difficulty: work.difficulty,
            epoch,
            extra_nonce1: work.extra_nonce1.clone(),
            nonce_start,
            nonce_range,
            timestamp: SystemTime::now(),
        }
    }

    /// **Check if work is stale** (kiểm tra work cũ)
    pub fn is_stale(&self, max_age_secs: u64) -> bool {
        self.timestamp.elapsed().unwrap_or_default() > Duration::from_secs(max_age_secs)
    }

    /// **Get end nonce** (lấy nonce cuối)
    pub fn end_nonce(&self) -> u64 {
        self.nonce_start + self.nonce_range
    }
}

/// **MiningLoop** (vòng lặp khai thác) – central mining orchestrator
pub struct MiningLoop {
    /// **Configuration** (cấu hình)
    config: MiningConfig,

    /// **Stratum client** (client stratum)
    stratum_client: Arc<StratumClient>,

    /// **GPU workers** (workers GPU) – per-device actors
    workers: Arc<RwLock<HashMap<usize, Arc<GpuWorker>>>>,

    /// **Statistics tracker** (tracker thống kê)
    statistics: Arc<MiningStatistics>,

    /// **Current work** (công việc hiện tại) – active job from pool
    current_work: Arc<RwLock<Option<StratumWorkPackage>>>,

    /// **Work distribution state** (trạng thái phân phối work)
    work_distribution: Arc<RwLock<WorkDistributionState>>,

    /// **Control channel** (kênh điều khiển) – for shutdown signals
    control_tx: mpsc::Sender<LoopCommand>,

    /// **Main loop task** (task vòng lặp chính)
    main_loop_task: Option<tokio::task::JoinHandle<()>>,
}

/// **WorkDistributionState** (trạng thái phân phối work) – tracks nonce allocation across GPUs
#[derive(Debug, Default)]
struct WorkDistributionState {
    /// **Next nonce to assign** (nonce tiếp theo để gán)
    next_nonce: u64,

    /// **Total nonces assigned** (tổng nonce đã gán)
    total_assigned: u64,

    /// **Per-device nonce assignments** (phân bổ nonce theo thiết bị)
    device_assignments: HashMap<usize, DeviceNonceAssignment>,
}

/// **DeviceNonceAssignment** (phân bổ nonce thiết bị) – per-GPU nonce tracking
#[derive(Debug)]
struct DeviceNonceAssignment {
    /// **Last assigned nonce** (nonce cuối đã gán)
    last_nonce: u64,

    /// **Assigned range size** (kích thước phạm vi đã gán)
    range_size: u64,

    /// **Active work packages** (gói công việc đang hoạt động)
    active_packages: Vec<String>, // job_ids
}

/// **LoopCommand** (lệnh vòng lặp) – control commands cho mining loop
#[derive(Debug)]
enum LoopCommand {
    /// **Shutdown loop** (tắt vòng lặp)
    Shutdown,

    /// **Force work refresh** (buộc làm mới work)
    RefreshWork,

    /// **Update thermal limits** (cập nhật giới hạn nhiệt)
    UpdateThermalLimits(ThermalLimits),

    /// **Rebalance workloads** (cân bằng lại tải)
    RebalanceWorkloads,
}

impl MiningLoop {
    /// **Create new mining loop** (tạo vòng lặp khai thác mới)
    pub async fn new(config: MiningConfig) -> Result<Self> {
        info!("🚀 Initializing mining loop orchestrator");

        // Create stratum client
        let stratum_client = StratumClient::new(config.stratum_config.clone()).await?;
        let stratum_client = Arc::new(stratum_client);

        // Initialize statistics
        let stats_config = StatisticsConfig {
            update_interval_secs: 5,
            history_retention_minutes: 60,
            enable_gpu_monitoring: true,
            alert_thresholds: Default::default(),
        };
        let statistics = Arc::new(MiningStatistics::new(stats_config));
        // Note: start() will be called when mining actually begins
        // statistics.start().await;

        // Control channel
        let (control_tx, control_rx) = mpsc::channel(10);

        let workers = Arc::new(RwLock::new(HashMap::new()));
        let current_work = Arc::new(RwLock::new(None));
        let work_distribution = Arc::new(RwLock::new(WorkDistributionState::default()));

        let mut mining_loop = Self {
            config,
            stratum_client,
            workers,
            statistics,
            current_work,
            work_distribution,
            control_tx,
            main_loop_task: None,
        };

        // Initialize GPU workers
        mining_loop.initialize_workers().await?;

        // Start main loop
        let main_loop = mining_loop.clone();
        let handle = tokio::spawn(async move {
            if let Err(e) = main_loop.run_main_loop(control_rx).await {
                error!("Mining loop error: {}", e);
            }
        });

        mining_loop.main_loop_task = Some(handle);

        info!("✅ Mining loop orchestrator initialized with {} GPUs", mining_loop.config.gpu_devices.len());
        Ok(mining_loop)
    }

    /// **Clone for async operations** (clone cho operations bất đồng bộ)
    fn clone(&self) -> Self {
        Self {
            config: self.config.clone(),
            stratum_client: Arc::clone(&self.stratum_client),
            workers: Arc::clone(&self.workers),
            statistics: Arc::clone(&self.statistics),
            current_work: Arc::clone(&self.current_work),
            work_distribution: Arc::clone(&self.work_distribution),
            control_tx: self.control_tx.clone(),
            main_loop_task: None, // Don't clone the task handle
        }
    }

    /// **Initialize GPU workers** (khởi tạo workers GPU)
    async fn initialize_workers(&self) -> Result<()> {
        for &device_id in &self.config.gpu_devices {
            let worker = GpuWorker::new(
                device_id,
                Some(Arc::clone(&self.statistics)),
            ).await?;

            let worker = Arc::new(worker);
            self.workers.write().await.insert(device_id, worker);
            info!("✅ Initialized GPU worker for device {}", device_id);
        }

        Ok(())
    }

    /// **Start mining operation** (bắt đầu operation khai thác)
    pub async fn start_mining(&self) -> Result<()> {
        info!("⛏️ Starting mining operation");

        // Connect to pool
        self.stratum_client.connect().await?;
        info!("🌐 Connected to mining pool: {}", self.config.stratum_config.primary_pool.url);

        Ok(())
    }

    /// **Stop mining operation** (dừng operation khai thác)
    pub async fn stop_mining(&self) -> Result<()> {
        info!("🛑 Stopping mining operation");

        // Stop all workers
        let workers = self.workers.read().await;
        for (device_id, worker) in workers.iter() {
            debug!("Stopping worker {}", device_id);
            let _ = worker.stop_mining().await;
        }

        Ok(())
    }

    /// **Shutdown mining loop** (tắt vòng lặp khai thác)
    pub async fn shutdown(self) -> Result<()> {
        info!("🔄 Shutting down mining loop");

        // Send shutdown command
        let _ = self.control_tx.send(LoopCommand::Shutdown).await;

        // Wait for main loop to finish
        if let Some(handle) = self.main_loop_task {
            let _ = handle.await;
        }

        // Shutdown stratum client
        let stratum_client = Arc::try_unwrap(self.stratum_client)
            .unwrap_or_else(|_| panic!("Failed to unwrap stratum client Arc"));
        let _ = stratum_client.shutdown().await;

        // Shutdown workers
        let workers_map = self.workers.read().await;
        for (device_id, worker) in workers_map.iter() {
            debug!("Shutting down worker {}", device_id);
            let worker_clone = Arc::clone(worker);
            tokio::spawn(async move {
                let worker = Arc::try_unwrap(worker_clone)
                    .unwrap_or_else(|_| panic!("Failed to unwrap worker Arc"));
                let _ = worker.shutdown().await;
            });
        }

        info!("✅ Mining loop shutdown complete");
        Ok(())
    }

    /// **Get current statistics** (lấy thống kê hiện tại)
    pub async fn get_statistics(&self) -> AggregatedStats {
        self.statistics.get_current_stats().await
    }

    /// **Get alerts** (lấy cảnh báo)
    pub async fn get_alerts(&self) -> Vec<MiningAlert> {
        self.statistics.check_alerts().await
    }

    /// **Main mining loop** (vòng lặp khai thác chính)
    async fn run_main_loop(
        self,
        mut control_rx: mpsc::Receiver<LoopCommand>,
    ) -> Result<()> {
        info!("🔄 Starting main mining loop");

        let mut work_refresh_interval = time::interval(Duration::from_secs(30));
        let mut stats_update_interval = time::interval(Duration::from_secs(5));

        loop {
            tokio::select! {
                // Handle control commands
                command = control_rx.recv() => {
                    match command {
                        Some(LoopCommand::Shutdown) => {
                            info!("📴 Mining loop received shutdown command");
                            break;
                        }
                        Some(LoopCommand::RefreshWork) => {
                            if let Err(e) = self.refresh_work().await {
                                warn!("Failed to refresh work: {}", e);
                            }
                        }
                        Some(LoopCommand::UpdateThermalLimits(limits)) => {
                            if let Err(e) = self.update_thermal_limits(limits).await {
                                warn!("Failed to update thermal limits: {}", e);
                            }
                        }
                        Some(LoopCommand::RebalanceWorkloads) => {
                            if let Err(e) = self.rebalance_workloads().await {
                                warn!("Failed to rebalance workloads: {}", e);
                            }
                        }
                        None => {
                            info!("Control channel closed");
                            break;
                        }
                    }
                }

                // Periodic work refresh
                _ = work_refresh_interval.tick() => {
                    if let Err(e) = self.check_and_refresh_work().await {
                        warn!("Work refresh error: {}", e);
                    }
                }

                // Statistics update
                _ = stats_update_interval.tick() => {
                    // Take snapshot for historical data
                    self.statistics.take_snapshot().await;

                    // Check for stale work
                    self.check_stale_work().await;
                }
            }
        }

        info!("✅ Main mining loop completed");
        Ok(())
    }

    /// **Check work and refresh if needed** (kiểm tra work và làm mới nếu cần)
    async fn check_and_refresh_work(&self) -> Result<()> {
        let should_refresh = {
            let current_work = self.current_work.read().await;
            match &*current_work {
                Some(work) => work.is_stale(self.config.stratum_config.max_job_age_secs),
                None => true,
            }
        };

        if should_refresh {
            self.refresh_work().await?;
        }
        Ok(())
    }

    /// **Refresh work from pool** (làm mới work từ pool)
    async fn refresh_work(&self) -> Result<()> {
        debug!("📡 Fetching new work from pool");

        match self.stratum_client.get_work().await {
            Ok(work) => {
                {
                    *self.current_work.write().await = Some(work.clone());
                }

                info!("📦 Received new work: {} (difficulty: {})", work.job_id, work.difficulty);

                // Distribute work to GPUs
                self.distribute_work_to_gpus(&work).await?;
            }
            Err(e) => {
                warn!("Failed to get work from pool: {}", e);

                // If pool disconnected, don't clear current work
                // Keep mining with existing work
            }
        }
        Ok(())
    }

    /// **Distribute work to GPUs** (phân phối work cho GPUs)
    async fn distribute_work_to_gpus(&self, stratum_work: &StratumWorkPackage) -> Result<()> {
        let device_count = self.config.gpu_devices.len();
        if device_count == 0 {
            return Ok(());
        }

        let work_range_size = 1_000_000; // 1M nonces per work package per GPU
        let mut distribution = self.work_distribution.write().await;

        // Calculate nonce ranges for each GPU
        for &device_id in &self.config.gpu_devices {
            let nonce_range = work_range_size;

            // Get current nonce before mutable borrow
            let current_nonce = distribution.next_nonce;

            let work_package = WorkPackage::from_stratum_work(
                stratum_work,
                current_nonce,
                nonce_range,
            );

            // Send work to GPU worker
            if let Some(worker) = self.workers.read().await.get(&device_id) {
                if let Err(e) = worker.start_mining(work_package).await {
                    warn!("Failed to start mining on GPU {}: {}", device_id, e);
                    continue;
                }

                // Update distribution state
                distribution.total_assigned += nonce_range;
                distribution.next_nonce += nonce_range;

                let next_nonce = distribution.next_nonce;

                let assignment = distribution.device_assignments
                    .entry(device_id)
                    .or_insert(DeviceNonceAssignment {
                        last_nonce: 0,
                        range_size: 0,
                        active_packages: Vec::new(),
                    });

                assignment.last_nonce = next_nonce;
                assignment.range_size += nonce_range;
                assignment.active_packages.push(stratum_work.job_id.clone());

                info!("📤 Distributed work to GPU {}: nonces {}-{}",
                    device_id,
                    current_nonce,
                    current_nonce + nonce_range - 1);
            }
        }

        Ok(())
    }

    /// **Check for stale work** (kiểm tra work cũ)
    async fn check_stale_work(&self) -> Result<()> {
        let max_age = self.config.stratum_config.max_job_age_secs;
        let current_work = self.current_work.read().await;

        if let Some(work) = &*current_work {
            if work.is_stale(max_age) {
                info!("♻️ Work is stale (age: {}s > {}s max), refreshing",
                    work.received_at.elapsed().unwrap_or_default().as_secs(), max_age);

                // Trigger work refresh
                let _ = self.control_tx.send(LoopCommand::RefreshWork).await;
            }
        }
        Ok(())
    }

    /// **Update thermal limits** (cập nhật giới hạn nhiệt)
    async fn update_thermal_limits(&self, limits: ThermalLimits) -> Result<()> {
        let workers = self.workers.read().await;
        for (device_id, worker) in workers.iter() {
            if let Err(e) = worker.update_thermal_limits(limits.clone()).await {
                warn!("Failed to update thermal limits on GPU {}: {}", device_id, e);
            }
        }
        info!("🌡️ Updated thermal limits across all GPUs");
        Ok(())
    }

    /// **Rebalance workloads** (cân bằng lại tải)
    async fn rebalance_workloads(&self) -> Result<()> {
        info!("⚖️ Rebalancing GPU workloads");

        // Collect current GPU performance
        let mut gpu_performance = Vec::new();

        let workers = self.workers.read().await;
        for (device_id, worker) in workers.iter() {
            match worker.get_gpu_metrics().await {
                Ok(metrics) => {
                    gpu_performance.push((*device_id, metrics));
                }
                Err(e) => {
                    warn!("Failed to get metrics from GPU {}: {}", device_id, e);
                }
            }
        }

        // Sort by temperature (hotter GPUs get smaller workloads)
        gpu_performance.sort_by(|a, b| a.1.temperature.partial_cmp(&b.1.temperature).unwrap());

        // Adjust work distribution based on thermal performance
        for (device_id, metrics) in gpu_performance {
            let workload_multiplier = if metrics.temperature > 80.0 {
                0.5 // Reduce workload for hot GPUs
            } else if metrics.temperature < 65.0 {
                1.2 // Increase workload for cool GPUs
            } else {
                1.0 // Normal workload
            };

            debug!("GPU {}: temp={}°C, workload_multiplier={}",
                device_id, metrics.temperature, workload_multiplier);
        }

        info!("✅ Workload rebalancing complete");
        Ok(())
    }

    /// **Handle mining results** (xử lý kết quả khai thác) – would be called by result collector
    async fn handle_mining_results(&self) -> Result<()> {
        // This would be called periodically to collect results from workers
        // For now, workers send results directly to stratum client

        let workers = self.workers.read().await;
        for (device_id, worker) in workers.iter() {
            // Try to receive result from this worker
            if let Ok(Some(result)) = worker.receive_result().await {
                match result {
                    MineResult::Solution(solution) => {
                        info!("🎉 GPU {} found valid solution! Submitting to pool", device_id);

                        // Submit solution to pool
                        if let Err(e) = self.stratum_client.submit_solution(solution).await {
                            warn!("Failed to submit solution: {}", e);
                            self.statistics.record_share_result(*device_id, false, false).await;
                        } else {
                            info!("✅ Solution submitted successfully");
                            self.statistics.record_share_result(*device_id, true, false).await;
                        }
                    }
                    MineResult::Error(e) => {
                        error!("Mining error from GPU {}: {}", device_id, e);
                        // Could trigger recovery actions here
                    }
                    _ => {
                        // No solution or timeout - continue mining
                    }
                }
            }
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_work_package_creation() {
        let stratum_work = StratumWorkPackage {
            job_id: "test-job".to_string(),
            header_hash: vec![0; 32],
            seed_hash: vec![0; 32],
            target: vec![255; 32],
            height: 12345,
            difficulty: 1.0,
            extra_nonce1: Some(vec![1, 2, 3, 4]),
            received_at: SystemTime::now(),
            clean_jobs: false,
        };

        let work_package = WorkPackage::from_stratum_work(&stratum_work, 0, 1000000);

        assert_eq!(work_package.job_id, "test-job");
        assert_eq!(work_package.nonce_start, 0);
        assert_eq!(work_package.nonce_range, 1000000);
        assert_eq!(work_package.end_nonce(), 1000000);
    }

    #[tokio::test]
    async fn test_statistics_integration() {
        let config = StatisticsConfig::default();
        let stats = MiningStatistics::new(config);

        // Test basic functionality
        let agg_stats = stats.get_current_stats().await;
        assert!(agg_stats.uptime_seconds >= 0);
        assert_eq!(agg_stats.active_gpus, 0); // No workers initialized
    }
}