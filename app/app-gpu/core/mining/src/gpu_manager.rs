//! GPU Resource Manager for Mining Operations
//!
//! This module manages GPU devices, memory allocation, and workload distribution
//! across multiple GPUs. It provides optimal resource utilization and thermal
//! management for sustained mining operations.

use anyhow::{Context, Result};
use async_trait::async_trait;
#[cfg(feature = "workspace")]
use opus_gpu_gpu::{GpuDevice, GpuManager as BaseGpuManager, GpuMemory, GpuInfo, GpuCapabilities};

#[cfg(not(feature = "workspace"))]
use crate::mocks::{
    GpuDevice, GpuManager as BaseGpuManager, GpuMemory,
    MockGpuInfo as GpuInfo, MockGpuCapabilities as GpuCapabilities
};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Mutex;
use tracing::{debug, info, warn, error};

/// GPU mining configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuMiningConfig {
    /// Target GPU utilization percentage (0.0-1.0)
    pub target_utilization: f64,
    /// Maximum GPU temperature in Celsius
    pub max_temperature: f32,
    /// Maximum GPU power consumption in watts
    pub max_power_watts: f32,
    /// Memory allocation strategy
    pub memory_strategy: MemoryStrategy,
    /// Load balancing strategy
    pub load_balancing: LoadBalancingStrategy,
    /// Thermal throttling settings
    pub thermal_settings: ThermalSettings,
    /// Performance monitoring interval
    pub monitor_interval: Duration,
    /// Enable automatic intensity adjustment
    pub auto_intensity: bool,
}

/// Memory allocation strategies
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MemoryStrategy {
    /// Allocate maximum available memory
    MaxAllocate,
    /// Allocate percentage of available memory
    Percentage(f64),
    /// Allocate fixed amount in bytes
    Fixed(usize),
    /// Dynamic allocation based on workload
    Dynamic { min: usize, max: usize },
}

/// Load balancing strategies for multi-GPU setups
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum LoadBalancingStrategy {
    /// Equal distribution across all GPUs
    Equal,
    /// Proportional to GPU compute capability
    Proportional,
    /// Based on current GPU performance
    Performance,
    /// Weighted distribution with custom weights
    Weighted(HashMap<usize, f64>),
}

/// Thermal management settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalSettings {
    /// Temperature at which to start reducing intensity
    pub throttle_temp: f32,
    /// Temperature at which to shutdown mining
    pub shutdown_temp: f32,
    /// Fan curve settings
    pub fan_curve: Vec<(f32, f32)>, // (temp, fan_speed_percentage)
    /// Temperature monitoring interval
    pub monitor_interval: Duration,
}

/// GPU performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuPerformanceMetrics {
    /// Current GPU utilization (0.0-1.0)
    pub utilization: f64,
    /// Current temperature in Celsius
    pub temperature: f32,
    /// Current power consumption in watts
    pub power_watts: f32,
    /// Memory utilization (0.0-1.0)
    pub memory_utilization: f64,
    /// Current fan speed percentage (0.0-1.0)
    pub fan_speed: f64,
    /// Hash rate in hashes per second
    pub hashrate: f64,
    /// Efficiency (hashes per watt)
    pub efficiency: f64,
    /// Last update timestamp
    pub last_update: Instant,
}

/// GPU mining context
#[derive(Debug)]
pub struct GpuMiningContext {
    /// GPU device reference
    pub device: Arc<dyn GpuDevice>,
    /// Current mining intensity (1-31)
    pub intensity: u8,
    /// Allocated memory pools
    pub memory_pools: HashMap<String, Arc<dyn GpuMemory>>,
    /// Performance metrics
    pub metrics: RwLock<GpuPerformanceMetrics>,
    /// Current workload weight
    pub workload_weight: RwLock<f64>,
    /// Thermal throttle status
    pub thermal_throttled: RwLock<bool>,
}

/// Main GPU Manager for mining operations
pub struct MiningGpuManager {
    /// Base GPU manager
    base_manager: Arc<dyn BaseGpuManager>,
    /// Mining configuration
    config: RwLock<GpuMiningConfig>,
    /// Active mining contexts per GPU
    contexts: RwLock<HashMap<usize, Arc<GpuMiningContext>>>,
    /// Performance monitoring task handle
    monitor_handle: Mutex<Option<tokio::task::JoinHandle<()>>>,
    /// Total system hashrate
    total_hashrate: RwLock<f64>,
    /// Load balancer
    load_balancer: Arc<LoadBalancer>,
}

/// Load balancer for distributing work across GPUs
pub struct LoadBalancer {
    /// Current load distribution weights
    weights: RwLock<HashMap<usize, f64>>,
    /// Performance history for adaptive balancing
    performance_history: RwLock<HashMap<usize, Vec<f64>>>,
    /// Last rebalance timestamp
    last_rebalance: RwLock<Instant>,
    /// Rebalance interval
    rebalance_interval: Duration,
}

impl Default for GpuMiningConfig {
    fn default() -> Self {
        Self {
            target_utilization: 0.95,
            max_temperature: 85.0,
            max_power_watts: 300.0,
            memory_strategy: MemoryStrategy::Percentage(0.85),
            load_balancing: LoadBalancingStrategy::Proportional,
            thermal_settings: ThermalSettings::default(),
            monitor_interval: Duration::from_secs(5),
            auto_intensity: true,
        }
    }
}

impl Default for ThermalSettings {
    fn default() -> Self {
        Self {
            throttle_temp: 78.0,
            shutdown_temp: 90.0,
            fan_curve: vec![
                (30.0, 0.3),
                (50.0, 0.5),
                (70.0, 0.7),
                (80.0, 0.9),
                (90.0, 1.0),
            ],
            monitor_interval: Duration::from_secs(2),
        }
    }
}

impl MiningGpuManager {
    /// Create new mining GPU manager
    pub async fn new(
        base_manager: Arc<dyn BaseGpuManager>,
        config: GpuMiningConfig,
    ) -> Result<Self> {
        let load_balancer = Arc::new(LoadBalancer::new(Duration::from_secs(30)));

        let manager = Self {
            base_manager,
            config: RwLock::new(config),
            contexts: RwLock::new(HashMap::new()),
            monitor_handle: Mutex::new(None),
            total_hashrate: RwLock::new(0.0),
            load_balancer,
        };

        Ok(manager)
    }

    /// Initialize mining on specific GPU devices
    pub async fn initialize_devices(&self, device_ids: &[usize]) -> Result<()> {
        let mut contexts = self.contexts.write();

        for &device_id in device_ids {
            let device = self.base_manager.get_device(device_id)
                .await
                .with_context(|| format!("Failed to get GPU device {}", device_id))?;

            let context = self.create_mining_context(device).await?;
            contexts.insert(device_id, Arc::new(context));

            info!("Initialized mining context for GPU {}", device_id);
        }

        // Start performance monitoring
        self.start_monitoring().await?;

        // Initialize load balancer
        let device_ids: Vec<usize> = contexts.keys().cloned().collect();
        self.load_balancer.initialize(&device_ids).await?;

        Ok(())
    }

    /// Create mining context for a GPU device
    async fn create_mining_context(&self, device: Arc<dyn GpuDevice>) -> Result<GpuMiningContext> {
        let config = self.config.read();
        let info = device.get_info().await?;

        // Calculate initial intensity based on GPU capabilities
        let initial_intensity = self.calculate_initial_intensity(&info);

        // Allocate memory pools based on strategy
        let memory_pools = self.allocate_memory_pools(&device, &config.memory_strategy).await?;

        // Initialize performance metrics
        let metrics = GpuPerformanceMetrics {
            utilization: 0.0,
            temperature: 0.0,
            power_watts: 0.0,
            memory_utilization: 0.0,
            fan_speed: 0.0,
            hashrate: 0.0,
            efficiency: 0.0,
            last_update: Instant::now(),
        };

        Ok(GpuMiningContext {
            device,
            intensity: initial_intensity,
            memory_pools,
            metrics: RwLock::new(metrics),
            workload_weight: RwLock::new(1.0),
            thermal_throttled: RwLock::new(false),
        })
    }

    /// Calculate initial mining intensity based on GPU capabilities
    fn calculate_initial_intensity(&self, info: &GpuInfo) -> u8 {
        let base_intensity = match info.total_memory {
            // High-end cards (>8GB): Higher intensity
            mem if mem > 8 * 1024 * 1024 * 1024 => 24,
            // Mid-range cards (4-8GB): Medium intensity
            mem if mem > 4 * 1024 * 1024 * 1024 => 20,
            // Entry-level cards (<4GB): Lower intensity
            _ => 16,
        };

        // Adjust based on compute capability
        let capability_bonus = match info.capabilities.compute_capability_major {
            8.. => 4,  // RTX 30xx/40xx series
            7 => 2,    // RTX 20xx series
            6 => 0,    // GTX 10xx series
            _ => -2,   // Older cards
        };

        ((base_intensity as i8 + capability_bonus).clamp(8, 31)) as u8
    }

    /// Allocate memory pools based on strategy
    async fn allocate_memory_pools(
        &self,
        device: &Arc<dyn GpuDevice>,
        strategy: &MemoryStrategy,
    ) -> Result<HashMap<String, Arc<dyn GpuMemory>>> {
        let info = device.get_info().await?;
        let available_memory = info.available_memory;

        let allocation_size = match strategy {
            MemoryStrategy::MaxAllocate => (available_memory as f64 * 0.9) as usize,
            MemoryStrategy::Percentage(pct) => (available_memory as f64 * pct) as usize,
            MemoryStrategy::Fixed(size) => (*size).min(available_memory),
            MemoryStrategy::Dynamic { max, .. } => (*max).min(available_memory),
        };

        let mut pools = HashMap::new();

        // DAG memory pool (largest allocation)
        let dag_size = (allocation_size as f64 * 0.7) as usize;
        let dag_memory = device.allocate_memory(dag_size).await
            .context("Failed to allocate DAG memory pool")?;
        pools.insert("dag".to_string(), dag_memory);

        // Work buffer pool
        let work_size = (allocation_size as f64 * 0.2) as usize;
        let work_memory = device.allocate_memory(work_size).await
            .context("Failed to allocate work buffer pool")?;
        pools.insert("work".to_string(), work_memory);

        // Result buffer pool
        let result_size = (allocation_size as f64 * 0.1) as usize;
        let result_memory = device.allocate_memory(result_size).await
            .context("Failed to allocate result buffer pool")?;
        pools.insert("result".to_string(), result_memory);

        info!("Allocated GPU memory pools: DAG={}, Work={}, Result={}",
              dag_size / 1024 / 1024, work_size / 1024 / 1024, result_size / 1024 / 1024);

        Ok(pools)
    }

    /// Start performance monitoring
    async fn start_monitoring(&self) -> Result<()> {
        let mut handle_guard = self.monitor_handle.lock().await;
        if handle_guard.is_some() {
            return Ok(()); // Already monitoring
        }

        let contexts = self.contexts.read().clone();
        let config = self.config.read().clone();
        let total_hashrate = Arc::clone(&self.total_hashrate);

        let monitor_task = tokio::spawn(async move {
            let mut interval = tokio::time::interval(config.monitor_interval);

            loop {
                interval.tick().await;

                let mut system_hashrate = 0.0;

                for (device_id, context) in &contexts {
                    match Self::update_gpu_metrics(&context).await {
                        Ok(metrics) => {
                            system_hashrate += metrics.hashrate;

                            // Check thermal throttling
                            if metrics.temperature > config.thermal_settings.throttle_temp {
                                Self::apply_thermal_throttling(&context, &metrics).await;
                            }
                        }
                        Err(e) => {
                            warn!("Failed to update metrics for GPU {}: {}", device_id, e);
                        }
                    }
                }

                *total_hashrate.write() = system_hashrate;
                debug!("Updated system hashrate: {:.2} MH/s", system_hashrate / 1_000_000.0);
            }
        });

        *handle_guard = Some(monitor_task);
        Ok(())
    }

    /// Update GPU performance metrics
    async fn update_gpu_metrics(context: &GpuMiningContext) -> Result<GpuPerformanceMetrics> {
        let device = &context.device;
        let mut metrics = context.metrics.write();

        // Get current GPU stats
        metrics.utilization = device.get_utilization().await?;
        metrics.temperature = device.get_temperature().await?;
        metrics.power_watts = device.get_power_consumption().await?;
        metrics.memory_utilization = device.get_memory_utilization().await?;
        metrics.fan_speed = device.get_fan_speed().await?;

        // Calculate efficiency
        metrics.efficiency = if metrics.power_watts > 0.0 {
            metrics.hashrate / metrics.power_watts as f64
        } else {
            0.0
        };

        metrics.last_update = Instant::now();

        Ok(metrics.clone())
    }

    /// Apply thermal throttling to GPU
    async fn apply_thermal_throttling(
        context: &GpuMiningContext,
        metrics: &GpuPerformanceMetrics,
    ) {
        if metrics.temperature > 85.0 && context.intensity > 10 {
            // Reduce intensity by 2
            context.intensity = (context.intensity - 2).max(10);
            *context.thermal_throttled.write() = true;

            warn!("Applied thermal throttling to GPU - reduced intensity to {}",
                  context.intensity);
        } else if metrics.temperature < 75.0 && *context.thermal_throttled.read() {
            // Gradually increase intensity back
            context.intensity = (context.intensity + 1).min(31);

            if context.intensity >= 20 {
                *context.thermal_throttled.write() = false;
                info!("Removed thermal throttling - restored intensity to {}",
                      context.intensity);
            }
        }
    }

    /// Get GPU context by device ID
    pub fn get_gpu_context(&self, device_id: usize) -> Option<Arc<GpuMiningContext>> {
        self.contexts.read().get(&device_id).cloned()
    }

    /// Get all active GPU contexts
    pub fn get_all_contexts(&self) -> HashMap<usize, Arc<GpuMiningContext>> {
        self.contexts.read().clone()
    }

    /// Update mining intensity for specific GPU
    pub async fn set_intensity(&self, device_id: usize, intensity: u8) -> Result<()> {
        let contexts = self.contexts.read();
        let context = contexts.get(&device_id)
            .context("GPU context not found")?;

        context.intensity = intensity.clamp(8, 31);
        info!("Set mining intensity for GPU {} to {}", device_id, context.intensity);

        Ok(())
    }

    /// Get system-wide mining statistics
    pub async fn get_mining_stats(&self) -> Result<MiningStats> {
        let contexts = self.contexts.read();
        let total_hashrate = *self.total_hashrate.read();

        let mut gpu_stats = HashMap::new();
        let mut total_power = 0.0;
        let mut avg_temp = 0.0;
        let mut active_gpus = 0;

        for (&device_id, context) in contexts.iter() {
            let metrics = context.metrics.read();
            gpu_stats.insert(device_id, GpuStats {
                hashrate: metrics.hashrate,
                temperature: metrics.temperature,
                power_watts: metrics.power_watts,
                utilization: metrics.utilization,
                intensity: context.intensity,
                thermal_throttled: *context.thermal_throttled.read(),
            });

            total_power += metrics.power_watts as f64;
            avg_temp += metrics.temperature as f64;
            active_gpus += 1;
        }

        avg_temp /= active_gpus.max(1) as f64;

        Ok(MiningStats {
            total_hashrate,
            total_power,
            average_temperature: avg_temp as f32,
            active_gpus,
            gpu_stats,
            system_efficiency: if total_power > 0.0 { total_hashrate / total_power } else { 0.0 },
        })
    }

    /// Shutdown all mining operations
    pub async fn shutdown(&self) -> Result<()> {
        info!("Shutting down mining GPU manager");

        // Stop monitoring
        if let Some(handle) = self.monitor_handle.lock().await.take() {
            handle.abort();
        }

        // Clear all contexts
        self.contexts.write().clear();

        info!("Mining GPU manager shutdown complete");
        Ok(())
    }
}

/// Load balancer implementation
impl LoadBalancer {
    pub fn new(rebalance_interval: Duration) -> Self {
        Self {
            weights: RwLock::new(HashMap::new()),
            performance_history: RwLock::new(HashMap::new()),
            last_rebalance: RwLock::new(Instant::now()),
            rebalance_interval,
        }
    }

    pub async fn initialize(&self, device_ids: &[usize]) -> Result<()> {
        let mut weights = self.weights.write();
        let mut history = self.performance_history.write();

        for &device_id in device_ids {
            weights.insert(device_id, 1.0);
            history.insert(device_id, Vec::new());
        }

        Ok(())
    }

    pub async fn get_workload_distribution(&self, total_work: usize) -> HashMap<usize, usize> {
        let weights = self.weights.read();
        let total_weight: f64 = weights.values().sum();

        weights.iter().map(|(&device_id, &weight)| {
            let work_amount = ((weight / total_weight) * total_work as f64) as usize;
            (device_id, work_amount)
        }).collect()
    }
}

/// GPU statistics for a single device
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuStats {
    pub hashrate: f64,
    pub temperature: f32,
    pub power_watts: f32,
    pub utilization: f64,
    pub intensity: u8,
    pub thermal_throttled: bool,
}

/// System-wide mining statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningStats {
    pub total_hashrate: f64,
    pub total_power: f64,
    pub average_temperature: f32,
    pub active_gpus: usize,
    pub gpu_stats: HashMap<usize, GpuStats>,
    pub system_efficiency: f64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gpu_mining_config_default() {
        let config = GpuMiningConfig::default();
        assert_eq!(config.target_utilization, 0.95);
        assert_eq!(config.max_temperature, 85.0);
        assert!(config.auto_intensity);
    }

    #[test]
    fn test_memory_strategy() {
        match MemoryStrategy::Percentage(0.8) {
            MemoryStrategy::Percentage(pct) => assert_eq!(pct, 0.8),
            _ => panic!("Unexpected memory strategy variant"),
        }
    }

    #[test]
    fn test_thermal_settings_default() {
        let settings = ThermalSettings::default();
        assert_eq!(settings.throttle_temp, 78.0);
        assert_eq!(settings.shutdown_temp, 90.0);
        assert!(!settings.fan_curve.is_empty());
    }
}