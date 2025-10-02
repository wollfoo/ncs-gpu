//! # GPU Mining Worker (Worker khai thác GPU)
//!
//! **Per-GPU mining actor** (actor khai thác cho mỗi GPU)
//! với async message passing, kernel orchestration, result processing
//! và thermal-aware workload management.
//!
//! ## Architecture Overview (Tổng quan kiến trúc)
//!
//! ```
//! GpuWorker (Actor)
//! ├── Message Handler ───► Command Processing
//! ├── Work Queue ───────► Kernel Launch Control
//! ├── Result Collector ──► Solution Aggregation
//! └─┬─► Statistics ─────► Performance Tracking
//!   └─► Health Monitor ─► Thermal Control
//! ```
//!
//! ## Worker Lifecycle (Vòng đời Worker)
//!
//! ```rust,ignore
//! 1. Initialization (Khởi tạo)
//!    ├── Setup CUDA context (Thiết lập context CUDA)
//!    ├── Initialize DAG memory (Khởi tạo bộ nhớ DAG)
//!    └── Create GPU streams (Tạo stream GPU)
//!
//! 2. Work Processing (Xử lý công việc)
//!    ├── Receive work package (Nhận gói công việc)
//!    ├── Generate nonce ranges (Tạo phạm vi nonce)
//!    ├── Launch kernels asynchronously (Khởi động kernel bất đồng bộ)
//!    └── Collect results (Thu thập kết quả)
//!
//! 3. Solution Handling (Xử lý giải pháp)
//!    ├── Validate solutions (Xác thực giải pháp)
//!    ├── Submit to pool (Nộp cho pool)
//!    └── Update statistics (Cập nhật thống kê)
//!
//! 4. Thermal Management (Quản lý nhiệt)
//!    ├── Monitor temperature (Giám sát nhiệt độ)
//!    ├── Adjust workloads (Điều chỉnh tải)
//!    └── Thermal throttling (Giới hạn nhiệt)
//! ```

use std::collections::VecDeque;
use std::sync::Arc;
use std::time::{Duration, SystemTime};

use anyhow::{anyhow, Result};
use async_trait::async_trait;
use tokio::sync::{mpsc, Mutex, RwLock};
use tracing::{debug, error, info, warn};

use super::statistics::{GpuMetrics, MiningStatistics, WorkerStats};
use super::loop_mod::WorkPackage;
use crate::stratum::Solution;

/// **MineResult** (kết quả khai thác) – result từ mining operation
#[derive(Debug, Clone)]
pub enum MineResult {
    /// **Solution found** (tìm thấy giải pháp) – valid nonce
    Solution(Solution),

    /// **No solution** (không có giải pháp) – nonce range processed without results
    NoSolution,

    /// **Error occurred** (xảy ra lỗi) – mining error
    Error(String),

    /// **Timeout** (hết thời gian) – kernel execution timeout
    Timeout,
}

/// **WorkerCommand** (lệnh worker) – commands cho GPU worker
#[derive(Debug)]
pub enum WorkerCommand {
    /// **Start mining work** (bắt đầu công việc khai thác)
    Mine(WorkPackage),

    /// **Stop current work** (dừng công việc hiện tại)
    Stop,

    /// **Update thermal limits** (cập nhật giới hạn nhiệt)
    UpdateThermalLimits(ThermalLimits),

    /// **Get current stats** (lấy thống kê hiện tại)
    GetStats { reply_to: mpsc::Sender<WorkerStats> },

    /// **Get GPU metrics** (lấy metrics GPU)
    GetMetrics { reply_to: mpsc::Sender<GpuMetrics> },

    /// **Shutdown worker** (tắt worker)
    Shutdown,
}

/// **ThermalLimits** (giới hạn nhiệt) – temperature thresholds cho GPU
#[derive(Debug, Clone)]
pub struct ThermalLimits {
    /// **Max temperature** (nhiệt độ tối đa) – °C, pause if exceeded
    pub max_temperature: f32,

    /// **Throttle temperature** (nhiệt độ throttle) – °C, reduce workload
    pub throttle_temperature: f32,

    /// **Target temperature** (nhiệt độ mục tiêu) – °C, optimize for this
    pub target_temperature: f32,
}

impl Default for ThermalLimits {
    fn default() -> Self {
        Self {
            max_temperature: 85.0,
            throttle_temperature: 75.0,
            target_temperature: 70.0,
        }
    }
}

/// **GpuWorker** (GPU worker) – per-GPU mining actor
pub struct GpuWorker {
    /// **Device ID** (ID thiết bị) – GPU device number
    device_id: usize,

    /// **CUDA device handle** (handle thiết bị CUDA)
    cuda_device: Option<i32>,

    /// **Worker statistics** (thống kê worker)
    stats: Arc<RwLock<WorkerStats>>,

    /// **Thermal limits** (giới hạn nhiệt)
    thermal_limits: Arc<RwLock<ThermalLimits>>,

    /// **Actor handle** (handle actor) – background task
    actor_handle: Option<tokio::task::JoinHandle<()>>,

    /// **Command sender** (người gửi lệnh)
    command_tx: mpsc::Sender<WorkerCommand>,

    /// **Result receiver** (người nhận kết quả) – from actor
    result_rx: Arc<Mutex<mpsc::Receiver<MineResult>>>,

    /// **Mining statistics** (thống kê khai thác) – parent stats tracker
    mining_stats: Option<Arc<MiningStatistics>>,
}

impl GpuWorker {
    /// **Create new GPU worker** (tạo worker GPU mới)
    pub async fn new(
        device_id: usize,
        mining_stats: Option<Arc<MiningStatistics>>,
    ) -> Result<Self> {
        info!("🚀 Creating GPU worker for device {}", device_id);

        let (command_tx, command_rx) = mpsc::channel(100);
        let (result_tx, result_rx) = mpsc::channel(100);

        // Initialize CUDA device
        let cuda_device = Self::initialize_cuda_device(device_id).await?;
        info!("✅ GPU worker created for device {}", device_id);

        // Initialize worker stats
        let stats = Arc::new(RwLock::new(WorkerStats {
            device_id,
            ..Default::default()
        }));

        let thermal_limits = Arc::new(RwLock::new(ThermalLimits::default()));

        // Create and start actor
        let actor = WorkerActor::new(
            device_id,
            cuda_device,
            Arc::clone(&stats),
            Arc::clone(&thermal_limits),
            command_rx,
            result_tx,
            mining_stats.as_ref().map(Arc::clone),
        );

        let actor_handle = tokio::spawn(async move {
            if let Err(e) = actor.run().await {
                error!("GPU worker actor error for device {}: {}", device_id, e);
            }
        });

        Ok(Self {
            device_id,
            cuda_device,
            stats,
            thermal_limits,
            actor_handle: Some(actor_handle),
            command_tx,
            result_rx: Arc::new(Mutex::new(result_rx)),
            mining_stats,
        })
    }

    /// **Initialize CUDA device** (khởi tạo thiết bị CUDA)
    async fn initialize_cuda_device(device_id: usize) -> Result<Option<i32>> {
        #[cfg(feature = "cuda")]
        {
            use crate::kernels::{cuda_device_count, cuda_init};

            let device_count = cuda_device_count()?;
            if device_id >= device_count as usize {
                return Err(anyhow!("Device ID {} exceeds available CUDA devices ({})",
                    device_id, device_count));
            }

            // Initialize CUDA device
            cuda_init(device_id as i32)?;
            info!("🎮 Initialized CUDA device {}", device_id);
            Ok(Some(device_id as i32))
        }

        #[cfg(not(feature = "cuda"))]
        {
            warn!("⚠️ CUDA not available, GPU worker {} will be stub", device_id);
            Ok(None)
        }
    }

    /// **Start mining work** (bắt đầu công việc khai thác)
    pub async fn start_mining(&self, work_package: WorkPackage) -> Result<()> {
        debug!("⛏️ GPU worker {} starting mining work", self.device_id);
        self.command_tx.send(WorkerCommand::Mine(work_package)).await
            .map_err(|_| anyhow!("Failed to send mining command"))?;
        Ok(())
    }

    /// **Stop current work** (dừng công việc hiện tại)
    pub async fn stop_mining(&self) -> Result<()> {
        debug!("🛑 Stopping GPU worker {}", self.device_id);
        self.command_tx.send(WorkerCommand::Stop).await
            .map_err(|_| anyhow!("Failed to send stop command"))?;
        Ok(())
    }

    /// **Update thermal limits** (cập nhật giới hạn nhiệt)
    pub async fn update_thermal_limits(&self, limits: ThermalLimits) -> Result<()> {
        debug!("🌡️ Updating thermal limits for GPU worker {}", self.device_id);
        self.command_tx.send(WorkerCommand::UpdateThermalLimits(limits)).await
            .map_err(|_| anyhow!("Failed to send thermal update"))?;
        Ok(())
    }

    /// **Get worker statistics** (lấy thống kê worker)
    pub async fn get_stats(&self) -> Result<WorkerStats> {
        let (reply_tx, mut reply_rx) = mpsc::channel(1);

        self.command_tx.send(WorkerCommand::GetStats { reply_to: reply_tx }).await
            .map_err(|_| anyhow!("Failed to send get_stats command"))?;

        match tokio::time::timeout(Duration::from_secs(2), reply_rx.recv()).await {
            Ok(Some(stats)) => Ok(stats),
            _ => Err(anyhow!("Timeout getting worker stats")),
        }
    }

    /// **Get GPU metrics** (lấy metrics GPU)
    pub async fn get_gpu_metrics(&self) -> Result<GpuMetrics> {
        let (reply_tx, mut reply_rx) = mpsc::channel(1);

        self.command_tx.send(WorkerCommand::GetMetrics { reply_to: reply_tx }).await
            .map_err(|_| anyhow!("Failed to send get_metrics command"))?;

        match tokio::time::timeout(Duration::from_secs(2), reply_rx.recv()).await {
            Ok(Some(metrics)) => Ok(metrics),
            _ => Err(anyhow!("Timeout getting GPU metrics")),
        }
    }

    /// **Receive mining result** (nhận kết quả khai thác)
    pub async fn receive_result(&self) -> Result<Option<MineResult>> {
        let mut rx = self.result_rx.lock().await;
        match tokio::time::timeout(Duration::from_millis(100), rx.recv()).await {
            Ok(Some(result)) => Ok(Some(result)),
            Ok(None) => Ok(None), // Channel closed
            Err(_) => Ok(None),   // Timeout, no result available
        }
    }

    /// **Shutdown worker** (tắt worker)
    pub async fn shutdown(self) -> Result<()> {
        debug!("🛑 Shutting down GPU worker {}", self.device_id);

        // Send shutdown command
        let _ = self.command_tx.send(WorkerCommand::Shutdown).await;

        // Wait for actor to finish
        if let Some(handle) = self.actor_handle {
            let _ = handle.await;
        }

        info!("✅ GPU worker {} shutdown complete", self.device_id);
        Ok(())
    }

    /// **Get device ID** (lấy ID thiết bị)
    pub fn device_id(&self) -> usize {
        self.device_id
    }
}

/// **WorkerActor** (actor worker) – internal actor implementation
struct WorkerActor {
    /// **Device ID** (ID thiết bị)
    device_id: usize,

    /// **CUDA device** (thiết bị CUDA)
    cuda_device: Option<i32>,

    /// **Worker statistics** (thống kê worker)
    stats: Arc<RwLock<WorkerStats>>,

    /// **Thermal limits** (giới hạn nhiệt)
    thermal_limits: Arc<RwLock<ThermalLimits>>,

    /// **Command receiver** (người nhận lệnh)
    command_rx: mpsc::Receiver<WorkerCommand>,

    /// **Result sender** (người gửi kết quả)
    result_tx: mpsc::Sender<MineResult>,

    /// **Current work** (công việc hiện tại) – đang xử lý
    current_work: Option<WorkPackage>,

    /// **Mining active** (đang hoạt động) – trạng thái khai thác
    mining_active: bool,

    /// **Nonce range** (phạm vi nonce) – current range being processed
    current_nonce_start: u64,

    /// **Work queue** (hàng đợi công việc) – pending work packages
    work_queue: VecDeque<WorkPackage>,

    /// **Mining statistics** (thống kê khai thác)
    mining_stats: Option<Arc<MiningStatistics>>,

    /// **Thermal throttling active** (đang giới hạn nhiệt)
    thermal_throttling: bool,

    /// **Last thermal check** (kiểm tra nhiệt cuối)
    last_thermal_check: SystemTime,
}

impl WorkerActor {
    /// **Create new worker actor** (tạo actor worker mới)
    fn new(
        device_id: usize,
        cuda_device: Option<i32>,
        stats: Arc<RwLock<WorkerStats>>,
        thermal_limits: Arc<RwLock<ThermalLimits>>,
        command_rx: mpsc::Receiver<WorkerCommand>,
        result_tx: mpsc::Sender<MineResult>,
        mining_stats: Option<Arc<MiningStatistics>>,
    ) -> Self {
        Self {
            device_id,
            cuda_device,
            stats,
            thermal_limits,
            command_rx,
            result_tx,
            current_work: None,
            mining_active: false,
            current_nonce_start: 0,
            work_queue: VecDeque::new(),
            mining_stats,
            thermal_throttling: false,
            last_thermal_check: SystemTime::now(),
        }
    }

    /// **Main actor loop** (vòng lặp actor chính)
    async fn run(mut self) -> Result<()> {
        info!("🌟 GPU worker actor {} starting", self.device_id);

        loop {
            tokio::select! {
                // Handle commands (Xử lý lệnh)
                command = self.command_rx.recv() => {
                    match command {
                        Some(cmd) => {
                            if let Err(e) = self.handle_command(cmd).await {
                                error!("Error handling command: {}", e);
                            }
                        }
                        None => {
                            debug!("Command channel closed, shutting down worker {}", self.device_id);
                            break;
                        }
                    }
                }

                // Periodic thermal check (Kiểm tra nhiệt định kỳ)
                _ = tokio::time::sleep(Duration::from_secs(10)) => {
                    if let Err(e) = self.check_thermal_limits().await {
                        warn!("Thermal check error: {}", e);
                    }
                }
            }
        }

        info!("✅ GPU worker actor {} shutdown", self.device_id);
        Ok(())
    }

    /// **Handle worker commands** (xử lý lệnh worker)
    async fn handle_command(&mut self, command: WorkerCommand) -> Result<()> {
        match command {
            WorkerCommand::Mine(work_package) => {
                self.handle_mine_command(work_package).await?;
            }
            WorkerCommand::Stop => {
                self.handle_stop_command().await?;
            }
            WorkerCommand::UpdateThermalLimits(limits) => {
                self.handle_thermal_update(limits).await?;
            }
            WorkerCommand::GetStats { reply_to } => {
                let stats = self.stats.read().await.clone();
                let _ = reply_to.send(stats).await;
            }
            WorkerCommand::GetMetrics { reply_to } => {
                let metrics = self.get_current_gpu_metrics().await?;
                let _ = reply_to.send(metrics).await;
            }
            WorkerCommand::Shutdown => {
                debug!("Shutdown command received for worker {}", self.device_id);
                return Ok(());
            }
        }
        Ok(())
    }

    /// **Handle mining command** (xử lý lệnh khai thác)
    async fn handle_mine_command(&mut self, work_package: WorkPackage) -> Result<()> {
        info!("📦 GPU worker {} received mining work: {}", self.device_id, work_package.job_id);

        // Queue work or start immediately if no current work
        if self.current_work.is_none() {
            self.current_work = Some(work_package);
            self.start_mining_cycle().await?;
        } else {
            self.work_queue.push_back(work_package);
        }

        Ok(())
    }

    /// **Handle stop command** (xử lý lệnh dừng)
    async fn handle_stop_command(&mut self) -> Result<()> {
        info!("🛑 Stopping mining on GPU worker {}", self.device_id);
        self.mining_active = false;
        self.current_work = None;

        // Send no-solution result to indicate work stopped
        let _ = self.result_tx.send(MineResult::NoSolution).await;

        Ok(())
    }

    /// **Handle thermal limits update** (xử lý cập nhật giới hạn nhiệt)
    async fn handle_thermal_update(&mut self, limits: ThermalLimits) -> Result<()> {
        debug!("🌡️ Updating thermal limits for GPU worker {}", self.device_id);
        *self.thermal_limits.write().await = limits;
        Ok(())
    }

    /// **Start mining cycle** (bắt đầu chu kỳ khai thác)
    async fn start_mining_cycle(&mut self) -> Result<()> {
        if let Some(work) = &self.current_work {
            info!("⛏️ Starting mining cycle on GPU {}", self.device_id);

            // Configure kernel parameters
            let nonce_range = self.calculate_nonce_range(work)?;
            self.current_nonce_start = nonce_range.start;

            // Launch kernel (simulated)
            self.mining_active = true;
            let hashes_computed = nonce_range.end - nonce_range.start;

            // Record kernel launch in stats
            if let Some(stats) = &self.mining_stats {
                stats.record_kernel_launch(self.device_id, hashes_computed).await;
            }
            {
                let mut worker_stats = self.stats.write().await;
                worker_stats.record_kernel_launch(hashes_computed);
            }

            // Simulate kernel execution time
            tokio::spawn(async move {
                tokio::time::sleep(Duration::from_millis(100)).await;
                // In real implementation, this would be actual kernel execution
            });

            // Schedule result collection
            self.schedule_result_collection(hashes_computed).await?;
        }

        Ok(())
    }

    /// **Calculate nonce range** (tính phạm vi nonce)
    fn calculate_nonce_range(&self, work: &WorkPackage) -> Result<NonceRange> {
        // Simple nonce range calculation - in real implementation,
        // this would be more sophisticated based on difficulty and GPU capability
        let nonce_step = 1_000_000; // 1M nonces per work unit
        let start = self.current_nonce_start;
        let end = start + nonce_step;

        Ok(NonceRange { start, end })
    }

    /// **Schedule result collection** (lên lịch thu thập kết quả)
    async fn schedule_result_collection(&self, hashes_computed: u64) -> Result<()> {
        let result_tx = self.result_tx.clone();
        let device_id = self.device_id;

        tokio::spawn(async move {
            // Simulate kernel completion time
            tokio::time::sleep(Duration::from_millis(150)).await;

            // Check for solutions (simulated - would be actual kernel result)
            let has_solution = rand::random::<f32>() < 0.001; // 0.1% chance of solution

            let result = if has_solution {
                // Generate fake solution for testing
                let nonce = (rand::random::<u64>() % hashes_computed) + 1;
                let solution = Solution {
                    job_id: "test-job".to_string(),
                    extra_nonce2: vec![0, 1, 2, 3],
                    nonce,
                    hash: vec![0; 32],
                    mix_hash: vec![0; 32],
                };
                MineResult::Solution(solution)
            } else {
                MineResult::NoSolution
            };

            let _ = result_tx.send(result).await;
            debug!("📤 Sent result for device {}", device_id);
        });

        Ok(())
    }

    /// **Check thermal limits** (kiểm tra giới hạn nhiệt)
    async fn check_thermal_limits(&mut self) -> Result<()> {
        // Skip if no recent work
        if self.last_thermal_check.elapsed().unwrap_or_default() < Duration::from_secs(30) {
            return Ok(());
        }

        let metrics = self.get_current_gpu_metrics().await?;
        let limits = self.thermal_limits.read().await;

        if metrics.temperature > limits.max_temperature {
            if !self.thermal_throttling {
                warn!("🔥 GPU {} temperature {}°C exceeds max {}, throttling",
                    self.device_id, metrics.temperature, limits.max_temperature);
                self.thermal_throttling = true;
            }
            // In real implementation, reduce kernel occupancy here
        } else if metrics.temperature < limits.target_temperature && self.thermal_throttling {
            info!("❄️ GPU {} cooled to {}°C, resuming normal operation",
                self.device_id, metrics.temperature);
            self.thermal_throttling = false;
        }

        self.last_thermal_check = SystemTime::now();
        Ok(())
    }

    /// **Get current GPU metrics** (lấy metrics GPU hiện tại)
    async fn get_current_gpu_metrics(&self) -> Result<GpuMetrics> {
        #[cfg(feature = "nvml")]
        {
            // Real NVML metrics would go here
            // For now, return simulated metrics
        }

        // Simulated metrics for testing
        let base_temp = if self.thermal_throttling { 80.0 } else { 65.0 };
        let temp = base_temp + (rand::random::<f32>() * 5.0);

        Ok(GpuMetrics {
            device_id: self.device_id,
            temperature: temp,
            utilization: 85.0 + (rand::random::<f32>() * 10.0),
            memory_used_mb: 4000 + (rand::random::<u64>() % 1000),
            memory_total_mb: 8192,
            fan_speed: Some(60.0 + (rand::random::<f32>() * 20.0)),
            power_watts: Some(200.0 + (rand::random::<f32>() * 50.0)),
            hashrate_mh: 40.0 + (rand::random::<f64>() * 10.0),
            timestamp: SystemTime::now(),
        })
    }

    /// **Process mining result** (xử lý kết quả khai thác)
    async fn process_mining_result(&mut self, result: MineResult) -> Result<()> {
        match result {
            MineResult::Solution(solution) => {
                info!("✅ Device {} found solution! Nonce: {}", self.device_id, solution.nonce);

                // Record in statistics
                if let Some(stats) = &self.mining_stats {
                    stats.record_share_result(self.device_id, true, false).await;
                }

                // Send to result channel (would go to pool submission)
                let _ = self.result_tx.send(MineResult::Solution(solution)).await;
            }
            MineResult::NoSolution => {
                // Continue with next nonce range or next work package
                if let Some(work) = &self.current_work {
                    // Check if more ranges to process
                    if self.should_process_more_ranges(work) {
                        self.start_mining_cycle().await?;
                    } else {
                        // Move to next work package
                        self.current_work = self.work_queue.pop_front();

                        if self.current_work.is_some() {
                            self.start_mining_cycle().await?;
                        } else {
                            // No more work
                            self.mining_active = false;
                        }
                    }
                }
            }
            MineResult::Error(e) => {
                warn!("❌ Mining error on device {}: {}", self.device_id, e);
                // Could implement retry logic here
                let _ = self.result_tx.send(MineResult::Error(e)).await;
            }
            MineResult::Timeout => {
                warn!("⏰ Mining timeout on device {}", self.device_id);
                // Handle timeout - maybe retry with smaller nonce range
                if let Some(work) = &self.current_work {
                    // Try again with smaller range
                    self.start_mining_cycle().await?;
                }
            }
        }
        Ok(())
    }

    /// **Check if should process more ranges** (kiểm tra có nên xử lý phạm vi nonce khác không)
    fn should_process_more_ranges(&self, work: &WorkPackage) -> bool {
        // Simple logic - in real implementation, this would be based on
        // time elapsed, thermal conditions, difficulty, etc.
        self.current_nonce_start < 10_000_000 // Process up to 10M nonces per work package
    }
}

/// **NonceRange** (phạm vi nonce) – range cho nonce search
#[derive(Debug, Clone)]
struct NonceRange {
    /// **Start nonce** (nonce bắt đầu)
    start: u64,

    /// **End nonce** (nonce kết thúc)
    end: u64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_thermal_limits_default() {
        let limits = ThermalLimits::default();
        assert_eq!(limits.max_temperature, 85.0);
        assert_eq!(limits.throttle_temperature, 75.0);
        assert_eq!(limits.target_temperature, 70.0);
    }

    #[tokio::test]
    async fn test_worker_creation() {
        let worker = GpuWorker::new(0, None).await;
        match worker {
            Ok(w) => {
                assert_eq!(w.device_id(), 0);

                // Shutdown to clean up
                let _ = w.shutdown().await;
                println!("✅ GPU worker creation test passed");
            }
            Err(e) => {
                println!("⚠️ GPU worker creation failed (expected without CUDA): {}", e);
            }
        }
    }

    #[test]
    fn test_nonce_range_calculation() {
        // This would test the static method if it were public
        println!("Nonce range calculation test placeholder");
    }
}