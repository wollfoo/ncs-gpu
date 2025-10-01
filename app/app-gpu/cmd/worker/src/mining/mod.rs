// Mining module - Core mining algorithms and pool communication

use anyhow::{Context, Result};
use async_trait::async_trait;
use std::sync::Arc;
use tokio::sync::{mpsc, RwLock};
use tracing::{debug, error, info, warn};

pub mod kawpow;
pub mod stratum;

/// Mining algorithm trait
#[async_trait]
pub trait MiningAlgorithm: Send + Sync {
    /// Initialize the algorithm with GPU
    async fn initialize(&mut self, gpu_index: usize) -> Result<()>;
    
    /// Mine a single block/job
    async fn mine(&self, job: &MiningJob) -> Result<MiningResult>;
    
    /// Get current hashrate
    fn get_hashrate(&self) -> f64;
    
    /// Cleanup resources
    async fn cleanup(&mut self) -> Result<()>;
}

/// Mining job from pool
#[derive(Debug, Clone)]
pub struct MiningJob {
    pub job_id: String,
    pub header_hash: Vec<u8>,
    pub seed_hash: Vec<u8>,
    pub target: Vec<u8>,
    pub height: u64,
    pub difficulty: f64,
}

/// Mining result to submit
#[derive(Debug, Clone)]
pub struct MiningResult {
    pub job_id: String,
    pub nonce: u64,
    pub hash: Vec<u8>,
    pub mix_hash: Vec<u8>,
}

/// Mining engine that coordinates algorithm and pool
pub struct MiningEngine {
    algorithm: Box<dyn MiningAlgorithm>,
    pool_client: Arc<stratum::StratumClient>,
    gpu_index: usize,
    hashrate: Arc<RwLock<f64>>,
    shares_accepted: Arc<RwLock<u64>>,
    shares_rejected: Arc<RwLock<u64>>,
}

impl MiningEngine {
    pub fn new(
        algorithm: Box<dyn MiningAlgorithm>,
        pool_url: String,
        wallet: String,
        worker_name: String,
        gpu_index: usize,
    ) -> Result<Self> {
        let pool_client = Arc::new(stratum::StratumClient::new(
            pool_url,
            wallet,
            worker_name,
        )?);
        
        Ok(Self {
            algorithm,
            pool_client,
            gpu_index,
            hashrate: Arc::new(RwLock::new(0.0)),
            shares_accepted: Arc::new(RwLock::new(0)),
            shares_rejected: Arc::new(RwLock::new(0)),
        })
    }
    
    pub async fn start(&mut self) -> Result<()> {
        info!("Starting mining engine for GPU {}", self.gpu_index);
        
        // Initialize algorithm
        self.algorithm.initialize(self.gpu_index).await
            .context("Failed to initialize mining algorithm")?;
        
        // Connect to pool
        self.pool_client.connect().await
            .context("Failed to connect to pool")?;
        
        // Start mining loop
        self.run_mining_loop().await?;
        
        Ok(())
    }
    
    async fn run_mining_loop(&mut self) -> Result<()> {
        let (job_tx, mut job_rx) = mpsc::channel::<MiningJob>(10);
        let (result_tx, mut result_rx) = mpsc::channel::<MiningResult>(100);
        
        // Start job receiver from pool
        let pool_client = self.pool_client.clone();
        let job_sender = job_tx.clone();
        tokio::spawn(async move {
            loop {
                match pool_client.get_job().await {
                    Ok(job) => {
                        if let Err(e) = job_sender.send(job).await {
                            error!("Failed to send job: {}", e);
                            break;
                        }
                    }
                    Err(e) => {
                        error!("Failed to get job from pool: {}", e);
                        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
                    }
                }
            }
        });
        
        // Start result submitter
        let pool_client = self.pool_client.clone();
        let shares_accepted = self.shares_accepted.clone();
        let shares_rejected = self.shares_rejected.clone();
        tokio::spawn(async move {
            while let Some(result) = result_rx.recv().await {
                match pool_client.submit_result(result).await {
                    Ok(accepted) => {
                        if accepted {
                            let mut count = shares_accepted.write().await;
                            *count += 1;
                            info!("Share accepted! Total: {}", *count);
                        } else {
                            let mut count = shares_rejected.write().await;
                            *count += 1;
                            warn!("Share rejected! Total: {}", *count);
                        }
                    }
                    Err(e) => {
                        error!("Failed to submit result: {}", e);
                    }
                }
            }
        });
        
        // Main mining loop
        info!("Mining loop started for GPU {}", self.gpu_index);
        
        while let Some(job) = job_rx.recv().await {
            debug!("Received new job: {}", job.job_id);
            
            // Update hashrate tracking
            let current_hashrate = self.algorithm.get_hashrate();
            *self.hashrate.write().await = current_hashrate;
            
            // Mine the job
            match self.algorithm.mine(&job).await {
                Ok(result) => {
                    debug!("Found potential solution for job {}", job.job_id);
                    if let Err(e) = result_tx.send(result).await {
                        error!("Failed to send result: {}", e);
                    }
                }
                Err(e) => {
                    warn!("Mining error: {}", e);
                }
            }
        }
        
        Ok(())
    }
    
    pub async fn stop(&mut self) -> Result<()> {
        info!("Stopping mining engine for GPU {}", self.gpu_index);
        
        // Disconnect from pool
        self.pool_client.disconnect().await?;
        
        // Cleanup algorithm resources
        self.algorithm.cleanup().await?;
        
        Ok(())
    }
    
    pub async fn get_stats(&self) -> MiningStats {
        MiningStats {
            hashrate: *self.hashrate.read().await,
            shares_accepted: *self.shares_accepted.read().await,
            shares_rejected: *self.shares_rejected.read().await,
        }
    }
}

#[derive(Debug, Clone)]
pub struct MiningStats {
    pub hashrate: f64,
    pub shares_accepted: u64,
    pub shares_rejected: u64,
}
