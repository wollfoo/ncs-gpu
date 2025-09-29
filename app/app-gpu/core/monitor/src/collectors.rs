//! **Metrics Collectors** (Trình thu thập đo lường)
//!
//! Specialized collectors for GPU, system, and pool metrics.

use crate::{MonitorError, Result, metrics::{GpuMetrics, SystemMetrics, PoolMetrics, Metric}};
use crate::{GpuMonitoringConfig, SystemMonitoringConfig};
use async_trait::async_trait;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use parking_lot::Mutex;

/// **Metrics Collector** (Trình thu thập đo lường) - Base trait for all collectors
#[async_trait]
pub trait MetricsCollector: Send + Sync {
    /// Collect metrics from the source
    async fn collect(&self) -> Result<()>;

    /// Get collector name
    fn name(&self) -> &str;

    /// Get collection interval
    fn interval(&self) -> std::time::Duration {
        std::time::Duration::from_secs(5)
    }

    /// Check if collector is enabled
    fn is_enabled(&self) -> bool {
        true
    }
}

/// **GPU Collector** (Trình thu thập GPU) - Collects GPU performance metrics
pub struct GpuCollector {
    config: GpuMonitoringConfig,
    gpu_metrics: Arc<RwLock<HashMap<u32, GpuMetrics>>>,
    discovered_gpus: Arc<RwLock<Vec<GpuInfo>>>,
    #[cfg(feature = "nvidia")]
    nvml: Arc<Mutex<Option<nvml_wrapper::Nvml>>>,
}

/// **GPU Information** (Thông tin GPU) - Basic GPU device information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuInfo {
    pub id: u32,
    pub name: String,
    pub uuid: String,
    pub pci_bus: String,
    pub driver_version: String,
    pub cuda_compute_capability: Option<(u32, u32)>,
    pub memory_total: u64,
    pub power_limit_max: f32,
    pub temperature_limit: f32,
}

impl GpuCollector {
    /// Create new GPU collector
    pub fn new(config: GpuMonitoringConfig) -> Result<Self> {
        #[cfg(feature = "nvidia")]
        let nvml = if config.nvidia_ml_enabled {
            match nvml_wrapper::Nvml::init() {
                Ok(nvml) => {
                    tracing::info!("NVML initialized successfully");
                    Some(nvml)
                }
                Err(e) => {
                    tracing::warn!("Failed to initialize NVML: {}", e);
                    None
                }
            }
        } else {
            None
        };

        Ok(Self {
            config,
            gpu_metrics: Arc::new(RwLock::new(HashMap::new())),
            discovered_gpus: Arc::new(RwLock::new(Vec::new())),
            #[cfg(feature = "nvidia")]
            nvml: Arc::new(Mutex::new(nvml)),
        })
    }

    /// Discover available GPUs
    pub async fn discover_gpus(&self) -> Result<Vec<GpuInfo>> {
        let mut gpus = Vec::new();

        #[cfg(feature = "nvidia")]
        {
            let nvml = self.nvml.lock();
            if let Some(ref nvml) = *nvml {
                match nvml.device_count() {
                    Ok(count) => {
                        tracing::debug!("Found {} NVIDIA GPU(s)", count);

                        for i in 0..count {
                            match nvml.device_by_index(i) {
                                Ok(device) => {
                                    if let Ok(gpu_info) = self.get_gpu_info(&device, i).await {
                                        gpus.push(gpu_info);
                                    }
                                }
                                Err(e) => {
                                    tracing::warn!("Failed to get GPU {}: {}", i, e);
                                }
                            }
                        }
                    }
                    Err(e) => {
                        tracing::error!("Failed to get GPU device count: {}", e);
                    }
                }
            }
        }

        // Update discovered GPUs
        let mut discovered = self.discovered_gpus.write().await;
        *discovered = gpus.clone();

        Ok(gpus)
    }

    #[cfg(feature = "nvidia")]
    async fn get_gpu_info(&self, device: &nvml_wrapper::Device, id: u32) -> Result<GpuInfo> {
        let name = device.name()
            .map_err(|e| MonitorError::Gpu { gpu_id: id, error: format!("Failed to get name: {}", e) })?;

        let uuid = device.uuid()
            .map_err(|e| MonitorError::Gpu { gpu_id: id, error: format!("Failed to get UUID: {}", e) })?;

        let pci_info = device.pci_info()
            .map_err(|e| MonitorError::Gpu { gpu_id: id, error: format!("Failed to get PCI info: {}", e) })?;

        let driver_version = device.driver_version()
            .unwrap_or_else(|_| "Unknown".to_string());

        let memory_info = device.memory_info()
            .map_err(|e| MonitorError::Gpu { gpu_id: id, error: format!("Failed to get memory info: {}", e) })?;

        let power_limit = device.max_power_limit()
            .unwrap_or(0) as f32 / 1000.0; // Convert mW to W

        let temperature_limit = device.temperature_threshold(nvml_wrapper::enum_wrappers::device::TemperatureThreshold::Shutdown)
            .unwrap_or(95) as f32;

        let cuda_compute = device.cuda_compute_capability()
            .map(|(major, minor)| (major as u32, minor as u32))
            .ok();

        Ok(GpuInfo {
            id,
            name,
            uuid,
            pci_bus: format!("{:04x}:{:02x}:{:02x}.0", pci_info.domain, pci_info.bus, pci_info.device),
            driver_version,
            cuda_compute_capability: cuda_compute,
            memory_total: memory_info.total,
            power_limit_max: power_limit,
            temperature_limit,
        })
    }

    /// Collect metrics from specific GPU
    #[cfg(feature = "nvidia")]
    async fn collect_gpu_metrics(&self, gpu_info: &GpuInfo) -> Result<GpuMetrics> {
        let nvml = self.nvml.lock();
        if let Some(ref nvml) = *nvml {
            let device = nvml.device_by_index(gpu_info.id)
                .map_err(|e| MonitorError::Gpu {
                    gpu_id: gpu_info.id,
                    error: format!("Failed to get device: {}", e)
                })?;

            let mut metrics = GpuMetrics::new(
                gpu_info.id,
                gpu_info.name.clone(),
                gpu_info.uuid.clone(),
            );

            // Temperature
            if let Ok(temp) = device.temperature(nvml_wrapper::enum_wrappers::device::TemperatureSensor::Gpu) {
                metrics.temperature_current = temp as f32;
                metrics.temperature_max = gpu_info.temperature_limit;

                // Check for thermal throttling
                if let Ok(throttle_reasons) = device.current_throttle_reasons() {
                    metrics.temperature_throttling = throttle_reasons.contains(
                        nvml_wrapper::bitmasks::device::ThrottleReasons::GPU_IDLE |
                        nvml_wrapper::bitmasks::device::ThrottleReasons::APPLICATIONS_CLOCKS_SETTING |
                        nvml_wrapper::bitmasks::device::ThrottleReasons::SW_POWER_CAP |
                        nvml_wrapper::bitmasks::device::ThrottleReasons::HW_SLOWDOWN |
                        nvml_wrapper::bitmasks::device::ThrottleReasons::HW_THERMAL_SLOWDOWN |
                        nvml_wrapper::bitmasks::device::ThrottleReasons::HW_POWER_BRAKE_SLOWDOWN
                    );
                }
            }

            // Power
            if let Ok(power) = device.power_usage() {
                metrics.power_draw = power as f32 / 1000.0; // Convert mW to W
            }

            if let Ok(power_limit) = device.power_management_limit() {
                metrics.power_limit = power_limit as f32 / 1000.0; // Convert mW to W
            }

            // Utilization
            if let Ok(utilization) = device.utilization_rates() {
                metrics.gpu_utilization = utilization.gpu as f32;
                metrics.memory_utilization = utilization.memory as f32;
            }

            // Memory
            if let Ok(memory_info) = device.memory_info() {
                metrics.memory_total = memory_info.total;
                metrics.memory_used = memory_info.used;
                metrics.memory_free = memory_info.free;
            }

            // Clock speeds
            if let Ok(graphics_clock) = device.clock_info(nvml_wrapper::enum_wrappers::device::Clock::Graphics) {
                metrics.clock_graphics = graphics_clock;
            }

            if let Ok(memory_clock) = device.clock_info(nvml_wrapper::enum_wrappers::device::Clock::Memory) {
                metrics.clock_memory = memory_clock;
            }

            if let Ok(sm_clock) = device.clock_info(nvml_wrapper::enum_wrappers::device::Clock::SM) {
                metrics.clock_sm = sm_clock;
            }

            // Fan speed
            if let Ok(fan_speed) = device.fan_speed(0) {
                metrics.fan_percentage = Some(fan_speed as f32);
            }

            // Calculate power efficiency
            if metrics.power_draw > 0.0 && metrics.hashrate > 0.0 {
                metrics.power_efficiency = metrics.hashrate / (metrics.power_draw as f64);
            }

            Ok(metrics)
        } else {
            Err(MonitorError::Gpu {
                gpu_id: gpu_info.id,
                error: "NVML not initialized".to_string(),
            })
        }
    }

    #[cfg(not(feature = "nvidia"))]
    async fn collect_gpu_metrics(&self, gpu_info: &GpuInfo) -> Result<GpuMetrics> {
        // Mock implementation for non-NVIDIA builds
        let mut metrics = GpuMetrics::new(
            gpu_info.id,
            gpu_info.name.clone(),
            gpu_info.uuid.clone(),
        );

        // Set some dummy values for testing
        metrics.temperature_current = 65.0;
        metrics.gpu_utilization = 95.0;
        metrics.memory_utilization = 80.0;
        metrics.power_draw = 250.0;
        metrics.hashrate = 100.0;

        Ok(metrics)
    }

    /// Get latest GPU metrics
    pub async fn get_gpu_metrics(&self, gpu_id: u32) -> Option<GpuMetrics> {
        let metrics = self.gpu_metrics.read().await;
        metrics.get(&gpu_id).cloned()
    }

    /// Get all GPU metrics
    pub async fn get_all_gpu_metrics(&self) -> HashMap<u32, GpuMetrics> {
        self.gpu_metrics.read().await.clone()
    }

    /// Update mining statistics for GPU
    pub async fn update_mining_stats(&self, gpu_id: u32, hashrate: f64, shares_accepted: u64, shares_rejected: u64, shares_stale: u64) -> Result<()> {
        let mut metrics = self.gpu_metrics.write().await;

        if let Some(gpu_metrics) = metrics.get_mut(&gpu_id) {
            gpu_metrics.hashrate = hashrate;
            gpu_metrics.shares_accepted = shares_accepted;
            gpu_metrics.shares_rejected = shares_rejected;
            gpu_metrics.shares_stale = shares_stale;
            gpu_metrics.timestamp = Utc::now();

            // Update hashrate average (simple moving average)
            if gpu_metrics.hashrate_average == 0.0 {
                gpu_metrics.hashrate_average = hashrate;
            } else {
                gpu_metrics.hashrate_average = (gpu_metrics.hashrate_average * 0.9) + (hashrate * 0.1);
            }

            // Calculate power efficiency
            if gpu_metrics.power_draw > 0.0 {
                gpu_metrics.power_efficiency = hashrate / (gpu_metrics.power_draw as f64);
            }
        }

        Ok(())
    }
}

#[async_trait]
impl MetricsCollector for GpuCollector {
    async fn collect(&self) -> Result<()> {
        if !self.config.enabled {
            return Ok(());
        }

        // Discover GPUs periodically
        let should_discover = {
            let discovered = self.discovered_gpus.read().await;
            discovered.is_empty()
        };

        if should_discover {
            self.discover_gpus().await?;
        }

        // Collect metrics from all discovered GPUs
        let discovered_gpus = self.discovered_gpus.read().await.clone();
        let mut new_metrics = HashMap::new();

        for gpu_info in discovered_gpus {
            match self.collect_gpu_metrics(&gpu_info).await {
                Ok(metrics) => {
                    new_metrics.insert(gpu_info.id, metrics);
                }
                Err(e) => {
                    tracing::warn!("Failed to collect metrics for GPU {}: {}", gpu_info.id, e);
                }
            }
        }

        // Update stored metrics
        let mut metrics_store = self.gpu_metrics.write().await;
        *metrics_store = new_metrics;

        Ok(())
    }

    fn name(&self) -> &str {
        "gpu"
    }

    fn interval(&self) -> std::time::Duration {
        std::time::Duration::from_secs(5)
    }

    fn is_enabled(&self) -> bool {
        self.config.enabled
    }
}

/// **System Collector** (Trình thu thập hệ thống) - Collects system resource metrics
pub struct SystemCollector {
    config: SystemMonitoringConfig,
    system_info: Arc<RwLock<sysinfo::System>>,
    last_metrics: Arc<RwLock<Option<SystemMetrics>>>,
}

impl SystemCollector {
    /// Create new system collector
    pub fn new(config: SystemMonitoringConfig) -> Result<Self> {
        let mut system = sysinfo::System::new_all();
        system.refresh_all();

        Ok(Self {
            config,
            system_info: Arc::new(RwLock::new(system)),
            last_metrics: Arc::new(RwLock::new(None)),
        })
    }

    /// Get latest system metrics
    pub async fn get_metrics(&self) -> Option<SystemMetrics> {
        self.last_metrics.read().await.clone()
    }

    async fn collect_system_metrics(&self) -> Result<SystemMetrics> {
        let mut system = self.system_info.write().await;
        system.refresh_all();

        let hostname = system.host_name().unwrap_or_else(|| "unknown".to_string());

        // CPU metrics
        let cpu_usage = system.global_cpu_info().cpu_usage();
        let load_avg = system.load_average();

        // Memory metrics
        let memory_total = system.total_memory();
        let memory_used = system.used_memory();
        let memory_available = system.available_memory();
        let swap_total = system.total_swap();
        let swap_used = system.used_swap();

        // Disk metrics
        let mut disk_usage = HashMap::new();
        for disk in system.disks() {
            let device_name = disk.name().to_string_lossy().to_string();
            let total = disk.total_space();
            let available = disk.available_space();
            let used = total - available;
            let usage_percent = if total > 0 {
                (used as f32 / total as f32) * 100.0
            } else {
                0.0
            };

            disk_usage.insert(device_name, crate::metrics::DiskUsage {
                total,
                used,
                available,
                usage_percent,
            });
        }

        // Network metrics
        let mut network_interfaces = HashMap::new();
        for (interface_name, network_data) in system.networks() {
            network_interfaces.insert(interface_name.clone(), crate::metrics::NetworkInterface {
                bytes_sent: network_data.total_transmitted(),
                bytes_received: network_data.total_received(),
                packets_sent: network_data.total_packets_transmitted(),
                packets_received: network_data.total_packets_received(),
                errors_sent: network_data.total_errors_on_transmitted(),
                errors_received: network_data.total_errors_on_received(),
            });
        }

        let metrics = SystemMetrics {
            timestamp: Utc::now(),
            hostname,
            cpu_usage_percent: cpu_usage,
            cpu_temperature: None, // System doesn't provide CPU temp easily
            cpu_frequency: None,   // System doesn't provide CPU freq easily
            load_average_1m: load_avg.one as f32,
            load_average_5m: load_avg.five as f32,
            load_average_15m: load_avg.fifteen as f32,
            memory_total,
            memory_used,
            memory_available,
            memory_cached: 0, // sysinfo doesn't provide cached memory directly
            swap_total,
            swap_used,
            disk_usage,
            network_interfaces,
            process_count: system.processes().len() as u32,
            thread_count: 0, // TODO: Calculate total thread count
            uptime_seconds: system.uptime(),
        };

        Ok(metrics)
    }
}

#[async_trait]
impl MetricsCollector for SystemCollector {
    async fn collect(&self) -> Result<()> {
        if !self.config.enabled {
            return Ok(());
        }

        match self.collect_system_metrics().await {
            Ok(metrics) => {
                let mut last_metrics = self.last_metrics.write().await;
                *last_metrics = Some(metrics);
                Ok(())
            }
            Err(e) => {
                tracing::error!("Failed to collect system metrics: {}", e);
                Err(e)
            }
        }
    }

    fn name(&self) -> &str {
        "system"
    }

    fn interval(&self) -> std::time::Duration {
        std::time::Duration::from_secs(10)
    }

    fn is_enabled(&self) -> bool {
        self.config.enabled
    }
}

/// **Pool Collector** (Trình thu thập pool) - Collects mining pool statistics
pub struct PoolCollector {
    pool_metrics: Arc<RwLock<HashMap<String, PoolMetrics>>>,
}

impl PoolCollector {
    /// Create new pool collector
    pub fn new() -> Self {
        Self {
            pool_metrics: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Update pool metrics
    pub async fn update_pool_metrics(&self, pool_name: String, metrics: PoolMetrics) {
        let mut pool_metrics = self.pool_metrics.write().await;
        pool_metrics.insert(pool_name, metrics);
    }

    /// Get pool metrics
    pub async fn get_pool_metrics(&self, pool_name: &str) -> Option<PoolMetrics> {
        let pool_metrics = self.pool_metrics.read().await;
        pool_metrics.get(pool_name).cloned()
    }

    /// Get all pool metrics
    pub async fn get_all_pool_metrics(&self) -> HashMap<String, PoolMetrics> {
        self.pool_metrics.read().await.clone()
    }
}

#[async_trait]
impl MetricsCollector for PoolCollector {
    async fn collect(&self) -> Result<()> {
        // Pool metrics are updated externally by the mining engine
        // This collector just maintains the storage
        Ok(())
    }

    fn name(&self) -> &str {
        "pool"
    }

    fn interval(&self) -> std::time::Duration {
        std::time::Duration::from_secs(30)
    }
}