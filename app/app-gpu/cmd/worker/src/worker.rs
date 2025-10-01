// Worker manager module

use anyhow::{Context, Result};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{error, info, warn};

use crate::config::Config;
use crate::gpu;
use crate::mining::{self, MiningEngine};

pub struct WorkerManager {
    config: Arc<Config>,
    gpu_manager: gpu::Manager,
    selected_gpus: Vec<usize>,
    workers: Arc<RwLock<HashMap<usize, Worker>>>,
}

struct Worker {
    gpu_index: usize,
    engine: MiningEngine,
    handle: Option<tokio::task::JoinHandle<()>>,
}

impl WorkerManager {
    pub fn new(
        config: Arc<Config>,
        gpu_manager: gpu::Manager,
        selected_gpus: Vec<usize>,
    ) -> Result<Self> {
        Ok(Self {
            config,
            gpu_manager,
            selected_gpus,
            workers: Arc::new(RwLock::new(HashMap::new())),
        })
    }
    
    pub async fn run(&self) -> Result<()> {
        info!("Starting {} workers...", self.selected_gpus.len());
        
        // Start a worker for each selected GPU
        for &gpu_index in &self.selected_gpus {
            if let Err(e) = self.start_worker(gpu_index).await {
                error!("Failed to start worker for GPU {}: {}", gpu_index, e);
            }
        }
        
        // Monitor workers and restart if needed
        self.monitor_workers().await?;
        
        Ok(())
    }
    
    async fn start_worker(&self, gpu_index: usize) -> Result<()> {
        info!("Starting worker for GPU {}", gpu_index);
        
        // Apply GPU configuration
        self.configure_gpu(gpu_index)?;
        
        // Create mining algorithm based on config
        let algorithm: Box<dyn mining::MiningAlgorithm> = match self.config.mining.algorithm.as_str() {
            "kawpow" => Box::new(mining::kawpow::KawPowAlgorithm::new(
                self.config.mining.intensity,
                self.config.mining.worksize,
            )?),
            _ => {
                return Err(anyhow::anyhow!(
                    "Unsupported algorithm: {}",
                    self.config.mining.algorithm
                ))
            }
        };
        
        // Create mining engine
        let mut engine = MiningEngine::new(
            algorithm,
            self.config.pool.url.clone(),
            self.config.pool.wallet.clone(),
            format!("{}.gpu{}", self.config.pool.worker_name, gpu_index),
            gpu_index,
        )?;
        
        // Start mining in background task
        let handle = tokio::spawn(async move {
            if let Err(e) = engine.start().await {
                error!("Mining engine error: {}", e);
            }
        });
        
        // Store worker
        let mut workers = self.workers.write().await;
        workers.insert(
            gpu_index,
            Worker {
                gpu_index,
                engine,
                handle: Some(handle),
            },
        );
        
        info!("Worker started for GPU {}", gpu_index);
        Ok(())
    }
    
    fn configure_gpu(&self, gpu_index: usize) -> Result<()> {
        let gpu_config = &self.config.gpu;
        
        // Set power limit if specified
        if let Some(power_limit) = gpu_config.power_limit_watts {
            self.gpu_manager.set_power_limit(gpu_index as u32, power_limit)
                .context("Failed to set power limit")?;
        }
        
        // Set clocks if specified
        let memory_clock = gpu_config.memory_clock_offset.map(|offset| {
            // Get base clock and add offset
            // This is simplified - real implementation would query base clock
            (9500 + offset) as u32
        });
        
        let core_clock = gpu_config.core_clock_offset.map(|offset| {
            // Get base clock and add offset
            (1800 + offset) as u32
        });
        
        if memory_clock.is_some() || core_clock.is_some() {
            self.gpu_manager.set_gpu_clocks(gpu_index as u32, memory_clock, core_clock)
                .context("Failed to set GPU clocks")?;
        }
        
        Ok(())
    }
    
    async fn monitor_workers(&self) -> Result<()> {
        let monitor_interval = tokio::time::Duration::from_secs(30);
        let mut interval = tokio::time::interval(monitor_interval);
        
        loop {
            interval.tick().await;
            
            // Check each worker
            let workers = self.workers.read().await;
            for (&gpu_index, worker) in workers.iter() {
                // Get GPU metrics
                match self.gpu_manager.get_metrics(gpu_index as u32) {
                    Ok(metrics) => {
                        // Log metrics
                        info!(
                            "GPU {} - Temp: {}°C, Power: {}W, Util: {}%, Memory: {}/{}MB",
                            gpu_index,
                            metrics.temperature,
                            metrics.power_watts,
                            metrics.gpu_utilization,
                            metrics.memory_used_mb,
                            metrics.memory_total_mb
                        );
                        
                        // Check for thermal throttling
                        if metrics.temperature > self.config.gpu.target_temperature {
                            warn!(
                                "GPU {} temperature high: {}°C (target: {}°C)",
                                gpu_index,
                                metrics.temperature,
                                self.config.gpu.target_temperature
                            );
                            
                            // Could implement power reduction here
                        }
                    }
                    Err(e) => {
                        error!("Failed to get metrics for GPU {}: {}", gpu_index, e);
                    }
                }
                
                // Check if worker is still running
                if let Some(handle) = &worker.handle {
                    if handle.is_finished() {
                        error!("Worker for GPU {} has stopped, restarting...", gpu_index);
                        
                        // Restart worker after delay
                        let restart_delay = self.config.worker.restart_delay_secs;
                        let gpu_idx = gpu_index;
                        let manager = self.clone();
                        
                        tokio::spawn(async move {
                            tokio::time::sleep(tokio::time::Duration::from_secs(restart_delay)).await;
                            if let Err(e) = manager.start_worker(gpu_idx).await {
                                error!("Failed to restart worker for GPU {}: {}", gpu_idx, e);
                            }
                        });
                    }
                }
            }
        }
    }
}

impl Clone for WorkerManager {
    fn clone(&self) -> Self {
        Self {
            config: self.config.clone(),
            gpu_manager: self.gpu_manager.clone(),
            selected_gpus: self.selected_gpus.clone(),
            workers: self.workers.clone(),
        }
    }
}
