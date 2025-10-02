//! # Mining Core Library (Thư viện khai thác cốt lõi)
//!
//! **Core mining engine** (động cơ khai thác cốt lõi) với **GPU management** (quản lý GPU),
//! **pool connection** (kết nối pool), và **hashrate monitoring** (giám sát tốc độ băm).

pub mod config;
pub mod crypto;
pub mod gpu;
pub mod mining;
pub mod stratum;

// Export CUDA kernels khi CUDA available
#[cfg(feature = "cuda")]
pub mod kernels;

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, warn};

// Import stratum client (Nhập client stratum)
use crate::stratum::{StratumClient, StratumConfig, PoolConfig};
use crate::mining::{MiningLoop, MiningStatistics};

/// **MiningAlgorithm** (thuật toán khai thác) – các thuật toán hỗ trợ
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum MiningAlgorithm {
    /// **Ethash** (Ethereum mining algorithm – thuật toán khai thác Ethereum)
    Ethash,
    /// **KawPow** (Ravencoin mining algorithm – thuật toán khai thác Ravencoin)
    KawPow,
    /// **RandomX** (Monero mining algorithm – thuật toán khai thác Monero)
    RandomX,
}

/// **MiningConfig** (cấu hình khai thác) – thiết lập tham số mining
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningConfig {
    /// **Stratum configuration** (cấu hình stratum) – pool và kết nối settings
    pub stratum_config: StratumConfig,

    /// **Algorithm** (thuật toán) – Ethash/KawPow/RandomX
    pub algorithm: MiningAlgorithm,

    /// **GPU devices** (thiết bị GPU) – danh sách GPU IDs (0,1,2,...)
    pub gpu_devices: Vec<usize>,

    /// **Intensity** (cường độ) – mức sử dụng GPU 0.0-1.0
    #[serde(default = "default_intensity")]
    pub intensity: f32,
}

fn default_intensity() -> f32 {
    0.8
}

impl Default for MiningConfig {
    fn default() -> Self {
        Self {
            stratum_config: StratumConfig {
                primary_pool: PoolConfig {
                    url: "stratum+tcp://pool.example.com:3333".to_string(),
                    worker_name: format!("worker-{}", uuid::Uuid::new_v4()),
                    password: None,
                    user_agent: Some("MiningCore/1.0.0".to_string()),
                    ssl: false,
                    backup_pools: vec![],
                },
                connect_timeout_secs: 30,
                reconnect_delay_secs: 10,
                max_reconnect_attempts: 5,
                share_batch_size: 10,
                max_job_age_secs: 60,
                rate_limit: 100.0,
                ssl_verify_hostname: true,
            },
            algorithm: MiningAlgorithm::Ethash,
            gpu_devices: vec![0],
            intensity: 0.8,
        }
    }
}

/// **MiningStats** (thống kê khai thác) – metrics runtime
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningStats {
    /// **Hashrate** (tốc độ băm) – hash/giây
    pub hashrate: f64,

    /// **Accepted shares** (share chấp nhận) – số share hợp lệ
    pub accepted_shares: u64,

    /// **Rejected shares** (share từ chối) – số share không hợp lệ
    pub rejected_shares: u64,

    /// **Uptime** (thời gian chạy) – giây
    pub uptime_seconds: u64,

    /// **GPU temperature** (nhiệt độ GPU) – độ C
    pub gpu_temperatures: Vec<f32>,

    /// **GPU utilization** (sử dụng GPU) – phần trăm
    pub gpu_utilizations: Vec<f32>,
}

impl Default for MiningStats {
    fn default() -> Self {
        Self {
            hashrate: 0.0,
            accepted_shares: 0,
            rejected_shares: 0,
            uptime_seconds: 0,
            gpu_temperatures: Vec::new(),
            gpu_utilizations: Vec::new(),
        }
    }
}

/// **MiningEngine** (động cơ khai thác) – core mining logic
pub struct MiningEngine {
    /// **Configuration** (cấu hình) – mining settings
    config: MiningConfig,

    /// **Mining loop** (vòng lặp khai thác) – main mining orchestrator
    mining_loop: Option<MiningLoop>,

    /// **Statistics tracker** (tracker thống kê) – comprehensive metrics
    statistics: Arc<tokio::sync::RwLock<MiningStatistics>>,

    /// **Running** (đang chạy) – trạng thái hoạt động
    running: Arc<RwLock<bool>>,

    /// **Start time** (thời điểm bắt đầu) – timestamp khởi động
    start_time: Option<std::time::Instant>,
}

impl MiningEngine {
    /// **Create new mining engine** (tạo động cơ mới) – khởi tạo instance
    pub fn new(config: MiningConfig) -> Result<Self> {
        info!("🚀 Initializing mining engine with config: {:?}", config);

        // Validate configuration (xác thực cấu hình)
        Self::validate_config(&config)?;

        // Initialize statistics tracker (khởi tạo tracker thống kê)
        let stats_config = crate::mining::StatisticsConfig {
            update_interval_secs: 5,
            history_retention_minutes: 60,
            enable_gpu_monitoring: true,
            alert_thresholds: Default::default(),
        };
        let statistics = Arc::new(tokio::sync::RwLock::new(MiningStatistics::new(stats_config)));

        Ok(Self {
            config,
            mining_loop: None,
            statistics,
            running: Arc::new(RwLock::new(false)),
            start_time: None,
        })
    }

    /// **Validate configuration** (xác thực cấu hình) – kiểm tra config hợp lệ
    fn validate_config(config: &MiningConfig) -> Result<()> {
        // Check pool URL (kiểm tra URL pool)
        if !config.stratum_config.primary_pool.url.starts_with("stratum+tcp://") &&
           !config.stratum_config.primary_pool.url.starts_with("stratum+ssl://") {
            anyhow::bail!("Invalid pool URL: must start with stratum+tcp:// or stratum+ssl://");
        }

        // Check worker name (kiểm tra tên worker)
        if config.stratum_config.primary_pool.worker_name.is_empty() {
            anyhow::bail!("Worker name cannot be empty");
        }

        // Check GPU devices (kiểm tra thiết bị GPU)
        if config.gpu_devices.is_empty() {
            anyhow::bail!("No GPU devices specified");
        }

        // Check intensity (kiểm tra cường độ)
        if config.intensity > 1.0 {
            anyhow::bail!("Intensity must be between 0 and 1.0");
        }

        Ok(())
    }

    /// **Start mining** (bắt đầu khai thác) – chạy mining loop
    pub async fn start(&mut self) -> Result<()> {
        let mut running = self.running.write().await;
        if *running {
            warn!("⚠️ Mining engine is already running");
            return Ok(());
        }

        info!("🎯 Starting mining engine...");
        *running = true;
        drop(running);

        self.start_time = Some(std::time::Instant::now());

        // Initialize GPU manager (khởi tạo trình quản lý GPU)
        info!("🔧 Initializing GPU manager...");
        self.initialize_gpus().await?;

        // Create and start mining loop (tạo và khởi động vòng lặp khai thác)
        info!("🔄 Creating mining loop orchestrator...");
        let mining_loop = MiningLoop::new(self.config.clone()).await?;
        mining_loop.start_mining().await?;
        self.mining_loop = Some(mining_loop);

        // Start statistics tracking (bắt đầu theo dõi thống kê)
        let mut statistics = self.statistics.write().await;
        statistics.start();

        info!("✅ Mining engine started successfully");

        Ok(())
    }

    /// **Stop mining** (dừng khai thác) – tắt gracefully
    pub async fn stop(&mut self) -> Result<()> {
        let mut running = self.running.write().await;
        if !*running {
            warn!("⚠️ Mining engine is not running");
            return Ok(());
        }

        info!("🛑 Stopping mining engine...");
        *running = false;
        drop(running);

        // Stop mining loop (dừng vòng lặp khai thác)
        if let Some(mining_loop) = self.mining_loop.take() {
            mining_loop.stop_mining().await?;
        }

        // Cleanup (dọn dẹp tài nguyên)
        self.cleanup().await?;

        info!("✅ Mining engine stopped successfully");
        Ok(())
    }

    /// **Get current stats** (lấy thống kê hiện tại) – đọc metrics
    pub async fn get_stats(&self) -> MiningStats {
        // Get aggregated stats from mining loop (lấy thống kê tổng hợp từ mining loop)
        if let Some(mining_loop) = &self.mining_loop {
            let agg_stats = mining_loop.get_statistics().await;

            MiningStats {
                hashrate: agg_stats.hashrate_mh * 1_000_000.0, // Convert MH/s to H/s
                accepted_shares: agg_stats.total_shares_accepted,
                rejected_shares: agg_stats.total_shares_rejected,
                uptime_seconds: agg_stats.uptime_seconds,
                gpu_temperatures: vec![agg_stats.avg_temperature as f32; agg_stats.active_gpus],
                gpu_utilizations: vec![agg_stats.avg_utilization as f32; agg_stats.active_gpus],
            }
        } else {
            MiningStats::default()
        }
    }

    /// **Get hashrate** (lấy tốc độ băm) – MH/s hiện tại
    pub async fn get_hashrate(&self) -> f64 {
        if let Some(mining_loop) = &self.mining_loop {
            mining_loop.get_statistics().await.hashrate_mh
        } else {
            0.0
        }
    }

    /// **Initialize GPUs** (khởi tạo GPUs) – setup GPU devices
    async fn initialize_gpus(&self) -> Result<()> {
        info!("🎮 Initializing {} GPU device(s)", self.config.gpu_devices.len());

        #[cfg(feature = "cuda")]
        {
            // Check CUDA availability
            if !kernels::is_cuda_available() {
                anyhow::bail!("CUDA is not available on this system");
            }
            
            let device_count = kernels::get_device_count()?;
            info!("✅ Found {} CUDA device(s)", device_count);
        }

        for &gpu_id in &self.config.gpu_devices {
            info!("  • GPU {}: Initializing...", gpu_id);

            #[cfg(feature = "cuda")]
            {
                // Initialize CUDA device
                kernels::cuda_init(gpu_id as i32)?;
                info!("  • GPU {}: ✅ CUDA initialized", gpu_id);
            }

            info!("  • GPU {}: ✅ Ready", gpu_id);
        }

        Ok(())
    }

    /// **Connect to pool** (kết nối pool) – establish stratum connection
    async fn connect_to_pool(&self) -> Result<()> {
        // This method is no longer used - stratum client handles connection
        info!("🔌 Stratum client handles pool connections");
        Ok(())
    }

    /// **Wait for mining completion** (chờ hoàn thành khai thác) – hold until stopped
    async fn wait_for_completion(&self) -> Result<()> {
        info!("⏳ Mining engine active, waiting for shutdown signal...");

        // Keep the engine alive while mining loop runs in background
        // The mining loop handles its own lifecycle through tokio::select!
        loop {
            let running = self.running.read().await;
            if !*running {
                info!("🛑 Mining engine shutdown requested");
                break;
            }
            drop(running);

            tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
        }

        Ok(())
    }

    /// **Cleanup** (dọn dẹp) – giải phóng tài nguyên
    async fn cleanup(&mut self) -> Result<()> {
        info!("🧹 Cleaning up resources...");

        // MiningLoop handles its own cleanup when shutdown
        // No additional stratum client to clean up

        // TODO: Free GPU resources (giải phóng tài nguyên GPU)

        info!("✅ Cleanup complete");
        Ok(())
    }
}

/// **Python FFI exports** (xuất FFI Python) – cho phép gọi từ Python
#[cfg(feature = "python")]
pub mod python_ffi {
    use super::*;

    /// **Create mining engine** (tạo động cơ khai thác) – từ Python
    #[no_mangle]
    pub extern "C" fn mining_core_create(
        pool_url: *const std::os::raw::c_char,
        wallet: *const std::os::raw::c_char,
        algorithm: u8,
    ) -> *mut MiningEngine {
        // TODO: Implement FFI wrapper
        std::ptr::null_mut()
    }

    /// **Start mining** (bắt đầu khai thác) – từ Python
    #[no_mangle]
    pub extern "C" fn mining_core_start(engine: *mut MiningEngine) -> i32 {
        // TODO: Implement FFI wrapper
        0
    }

    /// **Stop mining** (dừng khai thác) – từ Python
    #[no_mangle]
    pub extern "C" fn mining_core_stop(engine: *mut MiningEngine) -> i32 {
        // TODO: Implement FFI wrapper
        0
    }

    /// **Get hashrate** (lấy tốc độ băm) – từ Python
    #[no_mangle]
    pub extern "C" fn mining_core_get_hashrate(engine: *const MiningEngine) -> f64 {
        // TODO: Implement FFI wrapper
        0.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mining_config_default() {
        let config = MiningConfig::default();
        assert_eq!(config.algorithm, MiningAlgorithm::Ethash);
        assert_eq!(config.intensity, 0.8);
        assert!(!config.gpu_devices.is_empty());
    }

    #[test]
    fn test_mining_config_validation() {
        let mut config = MiningConfig::default();
        assert!(MiningEngine::validate_config(&config).is_ok());

        // Invalid pool URL (URL pool không hợp lệ)
        config.stratum_config.primary_pool.url = "http://invalid".to_string();
        assert!(MiningEngine::validate_config(&config).is_err());

        // Empty worker name (tên worker trống)
        config.stratum_config.primary_pool.url = "stratum+tcp://pool.example.com:3333".to_string();
        config.stratum_config.primary_pool.worker_name = String::new();
        assert!(MiningEngine::validate_config(&config).is_err());

        // No GPUs (không có GPU)
        config.stratum_config.primary_pool.worker_name = "test-worker".to_string();
        config.gpu_devices = Vec::new();
        assert!(MiningEngine::validate_config(&config).is_err());

        // Invalid intensity (cường độ không hợp lệ)
        config.gpu_devices = vec![0];
        config.intensity = 1.5;
        assert!(MiningEngine::validate_config(&config).is_err());
    }

    #[tokio::test]
    async fn test_mining_engine_lifecycle() {
        let config = MiningConfig::default();
        let engine = MiningEngine::new(config).unwrap();

        // Initial state (trạng thái ban đầu)
        let running = engine.running.read().await;
        assert!(!*running);
        drop(running);

        // Start should succeed (khởi động phải thành công)
        // Note: This will fail without actual GPU, but tests structure
        // (Lưu ý: Sẽ fail nếu không có GPU thật, nhưng test cấu trúc)
        // assert!(engine.start().await.is_ok());

        // Stop should succeed (dừng phải thành công)
        // assert!(engine.stop().await.is_ok());
    }
    
    #[test]
    #[cfg(feature = "cuda")]
    fn test_cuda_availability() {
        // Test if CUDA detection works
        let available = kernels::is_cuda_available();
        println!("CUDA available: {}", available);
        
        if available {
            match kernels::get_device_count() {
                Ok(count) => println!("Found {} CUDA devices", count),
                Err(e) => println!("Error getting device count: {}", e),
            }
        }
    }
}
