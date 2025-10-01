// Core Mining Engine Module
// Module engine khai thác chính

use anyhow::{Result, Context};
use std::sync::Arc;
use tokio::sync::{Mutex, RwLock};
use tracing::{info, warn, error, debug};
use std::collections::HashMap;

use crate::config::Config;
use crate::mining::{GpuMiner, MiningAlgorithm, HashRate};
use crate::networking::PoolConnection;

/// Trạng thái của mining engine
/// Mining engine state
#[derive(Debug, Clone, PartialEq)]
pub enum EngineState {
    /// Chưa khởi tạo (not initialized)
    Idle,
    /// Đang khởi động (starting up)
    Starting,
    /// Đang chạy (running)
    Running,
    /// Đang dừng (stopping)
    Stopping,
    /// Đã dừng (stopped)
    Stopped,
    /// Lỗi (error state)
    Error(String),
}

/// Mining Engine chính
/// Main mining engine
pub struct MiningEngine {
    /// Cấu hình hệ thống (system configuration)
    config: Arc<Config>,
    
    /// Trạng thái hiện tại (current state)
    state: Arc<RwLock<EngineState>>,
    
    /// Danh sách GPU miners
    miners: Arc<Mutex<Vec<GpuMiner>>>,
    
    /// Pool connection manager
    pool: Arc<Mutex<PoolConnection>>,
    
    /// Hash rates theo GPU
    hashrates: Arc<RwLock<HashMap<u32, HashRate>>>,
    
    /// Total shares (accepted/rejected)
    shares: Arc<RwLock<(u64, u64)>>,
    
    /// Shutdown signal
    shutdown: Arc<Mutex<bool>>,
}

impl MiningEngine {
    /// Tạo mining engine mới
    /// Create new mining engine
    pub async fn new(config: Arc<Config>) -> Result<Self> {
        info!("🔧 Khởi tạo Mining Engine...");
        
        // Validate config trước
        config.validate().context("Invalid configuration")?;
        
        // Khởi tạo pool connection
        let pool = PoolConnection::new(
            &config.mining.pool_address,
            &config.mining.wallet_address,
            &config.mining.worker_name,
            config.mining.use_tls,
        ).await?;
        
        // Khởi tạo GPU miners
        let mut miners = Vec::new();
        for gpu_idx in &config.gpu.gpu_indices {
            match GpuMiner::new(*gpu_idx, config.clone()).await {
                Ok(miner) => {
                    info!("✅ GPU {} initialized successfully", gpu_idx);
                    miners.push(miner);
                }
                Err(e) => {
                    error!("❌ Failed to initialize GPU {}: {}", gpu_idx, e);
                }
            }
        }
        
        if miners.is_empty() {
            anyhow::bail!("No GPUs could be initialized");
        }
        
        Ok(Self {
            config,
            state: Arc::new(RwLock::new(EngineState::Idle)),
            miners: Arc::new(Mutex::new(miners)),
            pool: Arc::new(Mutex::new(pool)),
            hashrates: Arc::new(RwLock::new(HashMap::new())),
            shares: Arc::new(RwLock::new((0, 0))),
            shutdown: Arc::new(Mutex::new(false)),
        })
    }
    
    /// Bắt đầu mining
    /// Start mining
    pub async fn start(&mut self) -> Result<()> {
        info!("⛏️ Starting mining engine...");
        
        // Update state
        {
            let mut state = self.state.write().await;
            *state = EngineState::Starting;
        }
        
        // Connect to pool
        {
            let mut pool = self.pool.lock().await;
            pool.connect().await
                .context("Failed to connect to mining pool")?;
        }
        
        // Start all GPU miners
        let miners = self.miners.lock().await;
        for miner in miners.iter() {
            self.start_miner_thread(miner.clone()).await?;
        }
        
        // Update state to running
        {
            let mut state = self.state.write().await;
            *state = EngineState::Running;
        }
        
        // Start monitoring thread
        self.start_monitoring().await;
        
        info!("✅ Mining engine started successfully");
        Ok(())
    }
    
    /// Start individual miner thread
    async fn start_miner_thread(&self, miner: GpuMiner) -> Result<()> {
        let pool = self.pool.clone();
        let hashrates = self.hashrates.clone();
        let shares = self.shares.clone();
        let shutdown = self.shutdown.clone();
        let config = self.config.clone();
        
        tokio::spawn(async move {
            let gpu_id = miner.gpu_id();
            info!("🎮 Starting miner thread for GPU {}", gpu_id);
            
            loop {
                // Check shutdown signal
                if *shutdown.lock().await {
                    info!("🛑 Stopping miner thread for GPU {}", gpu_id);
                    break;
                }
                
                // Get work from pool
                let work = {
                    let mut pool = pool.lock().await;
                    match pool.get_work().await {
                        Ok(w) => w,
                        Err(e) => {
                            error!("Failed to get work from pool: {}", e);
                            tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
                            continue;
                        }
                    }
                };
                
                // Mine the work
                match miner.mine(&work).await {
                    Ok(result) => {
                        // Update hashrate
                        {
                            let mut rates = hashrates.write().await;
                            rates.insert(gpu_id, result.hashrate);
                        }
                        
                        // Submit if found valid share
                        if result.found_share {
                            let mut pool = pool.lock().await;
                            match pool.submit_share(&result.nonce, &result.hash).await {
                                Ok(accepted) => {
                                    let mut shares = shares.write().await;
                                    if accepted {
                                        shares.0 += 1;
                                        info!("✅ Share accepted from GPU {}", gpu_id);
                                    } else {
                                        shares.1 += 1;
                                        warn!("❌ Share rejected from GPU {}", gpu_id);
                                    }
                                }
                                Err(e) => {
                                    error!("Failed to submit share: {}", e);
                                }
                            }
                        }
                    }
                    Err(e) => {
                        error!("Mining error on GPU {}: {}", gpu_id, e);
                    }
                }
                
                // Small delay to prevent busy loop
                tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
            }
        });
        
        Ok(())
    }
    
    /// Start monitoring thread
    async fn start_monitoring(&self) {
        let hashrates = self.hashrates.clone();
        let shares = self.shares.clone();
        let shutdown = self.shutdown.clone();
        let state = self.state.clone();
        
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(30));
            
            loop {
                interval.tick().await;
                
                // Check shutdown
                if *shutdown.lock().await {
                    break;
                }
                
                // Log current stats
                let rates = hashrates.read().await;
                let total_hashrate: f64 = rates.values()
                    .map(|h| h.rate_mhs)
                    .sum();
                
                let (accepted, rejected) = *shares.read().await;
                let accept_rate = if accepted + rejected > 0 {
                    (accepted as f64 / (accepted + rejected) as f64) * 100.0
                } else {
                    0.0
                };
                
                info!(
                    "📊 Stats: {:.2} MH/s | Shares: {}/{} ({:.1}% accepted)",
                    total_hashrate, accepted, rejected, accept_rate
                );
                
                // Check for issues
                if total_hashrate < 1.0 {
                    warn!("⚠️ Low hashrate detected");
                }
                
                if accept_rate < 90.0 && accepted + rejected > 10 {
                    warn!("⚠️ High rejection rate: {:.1}%", 100.0 - accept_rate);
                }
            }
        });
    }
    
    /// Dừng mining engine
    /// Stop mining engine
    pub async fn stop(&mut self) -> Result<()> {
        info!("🛑 Stopping mining engine...");
        
        // Update state
        {
            let mut state = self.state.write().await;
            *state = EngineState::Stopping;
        }
        
        // Set shutdown signal
        {
            let mut shutdown = self.shutdown.lock().await;
            *shutdown = true;
        }
        
        // Stop all miners
        let miners = self.miners.lock().await;
        for miner in miners.iter() {
            miner.stop().await?;
        }
        
        // Disconnect from pool
        {
            let mut pool = self.pool.lock().await;
            pool.disconnect().await?;
        }
        
        // Update state
        {
            let mut state = self.state.write().await;
            *state = EngineState::Stopped;
        }
        
        // Log final stats
        let (accepted, rejected) = *self.shares.read().await;
        info!(
            "📈 Final stats: {} accepted, {} rejected shares",
            accepted, rejected
        );
        
        info!("✅ Mining engine stopped");
        Ok(())
    }
    
    /// Get current engine state
    pub async fn get_state(&self) -> EngineState {
        self.state.read().await.clone()
    }
    
    /// Get current hashrates
    pub async fn get_hashrates(&self) -> HashMap<u32, HashRate> {
        self.hashrates.read().await.clone()
    }
    
    /// Get share statistics
    pub async fn get_shares(&self) -> (u64, u64) {
        *self.shares.read().await
    }
}
