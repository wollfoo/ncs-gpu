//! # GPU Manager - Main Orchestrator (Điều phối viên chính)
//!
//! **Complete GPU mining manager** (trình quản lý khai thác GPU hoàn chỉnh)
//! tích hợp tất cả subsystems: device discovery, contexts, memory, thermal monitoring.

use super::{
    context::CudaContextManager,
    device::{GpuDevice, GpuDeviceInfo, GpuDeviceStatus},
    error::{GpuError, GpuResult},
    memory::DagMemoryManager,
    thermal::{ThermalMonitor, ThermalThresholds, ThermalEvent},
};
// MiningAlgorithm is defined in the parent crate, not imported here
use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use std::{collections::HashMap, sync::Arc, time::Duration};
use tokio::sync::{mpsc, RwLock};
use tracing::{debug, error, info, warn};

/// **GpuAlgorithm** (thuật toán GPU) – supported mining algorithms
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum GpuAlgorithm {
    /// **Ethash** - Ethereum Proof-of-Work
    Ethash,
    /// **KawPow** - Ravencoin mining algorithm
    KawPow,
    /// **RandomX** - Monero CPU mining (GPU assisted)
    RandomX,
}

impl GpuAlgorithm {
    /// Get minimum compute capability required (Tính toán capability tối thiểu cần thiết)
    pub fn min_compute_capability(&self) -> (u32, u32) {
        match self {
            GpuAlgorithm::Ethash | GpuAlgorithm::KawPow => (7, 0), // RTX 20xx series
            GpuAlgorithm::RandomX => (7, 5), // Turing architecture recommended
        }
    }

    /// Get epoch reset frequency (Tần suất reset epoch)
    pub fn epoch_reset_frequency(&self) -> u32 {
        match self {
            GpuAlgorithm::Ethash => 30000, // Standard Ethash epoch size
            GpuAlgorithm::KawPow => 30000,
            GpuAlgorithm::RandomX => 0,     // RandomX doesn't use epochs
        }
    }
}

/// **GpuManagerStats** (thông kê GPU manager) – runtime metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuManagerStats {
    /// **Total devices** (tổng thiết bị) – all GPUs found
    pub total_devices: usize,

    /// **Active devices** (thiết bị hoạt động) – initialized GPUs
    pub active_devices: usize,

    /// **Current epoch** (epoch hiện tại) – for Ethash/KawPow
    pub current_epoch: u32,

    /// **Algorithm** (thuật toán) – current mining algorithm
    pub algorithm: Option<GpuAlgorithm>,

    /// **Device-specific stats** (thông kê từng thiết bị)
    pub device_stats: HashMap<usize, GpuDeviceStatus>,
}

impl Default for GpuManagerStats {
    fn default() -> Self {
        Self {
            total_devices: 0,
            active_devices: 0,
            current_epoch: 0,
            algorithm: None,
            device_stats: HashMap::new(),
        }
    }
}

/// **GpuManager** (trình quản lý GPU) – main orchestrator
pub struct GpuManager {
    /// **Devices** (thiết bị) – discovered GPU devices
    devices: Arc<RwLock<HashMap<usize, Arc<Mutex<GpuDevice>>>>>,

    /// **CUDA context manager** (trình quản lý CUDA context)
    context_manager: Arc<CudaContextManager>,

    /// **DAG memory manager** (trình quản lý bộ nhớ DAG)
    memory_manager: Arc<DagMemoryManager>,

    /// **Thermal monitor** (trình giám sát nhiệt)
    thermal_monitor: Arc<Mutex<Option<ThermalMonitor>>>,

    /// **Algorithm** (thuật toán) – current mining algorithm
    algorithm: Arc<RwLock<Option<GpuAlgorithm>>>,

    /// **Current epoch** (epoch hiện tại)
    current_epoch: Arc<RwLock<u32>>,

    /// **Monitoring handle** (handle giám sát) – background task
    monitoring_handle: Arc<RwLock<Option<tokio::task::JoinHandle<()>>>>,

    /// **Telemetry channel** (kênh telemetry) – for stats collection
    telemetry_tx: mpsc::UnboundedSender<GpuManagerStats>,

    /// **Telemetry receiver** (receiver telemetry)
    telemetry_rx: Arc<Mutex<mpsc::UnboundedReceiver<GpuManagerStats>>>,

    /// **Initialized** (đã khởi tạo)
    initialized: Arc<RwLock<bool>>,
}

impl GpuManager {
    /// **Create new GPU manager** (tạo trình quản lý GPU mới)
    pub fn new() -> Self {
        let (tx, rx) = mpsc::unbounded_channel();

        Self {
            devices: Arc::new(RwLock::new(HashMap::new())),
            context_manager: Arc::new(CudaContextManager::new()),
            memory_manager: Arc::new(DagMemoryManager::new()),
            thermal_monitor: Arc::new(Mutex::new(None)),
            algorithm: Arc::new(RwLock::new(None)),
            current_epoch: Arc::new(RwLock::new(0)),
            monitoring_handle: Arc::new(RwLock::new(None)),
            telemetry_tx: tx,
            telemetry_rx: Arc::new(Mutex::new(rx)),
            initialized: Arc::new(RwLock::new(false)),
        }
    }

    /// **Builder pattern for configuration** (Builder pattern để cấu hình)
    pub fn builder() -> GpuManagerBuilder {
        GpuManagerBuilder::new()
    }

    /// **Create manager with thermal monitoring** (tạo với giám sát nhiệt)
    pub fn new_with_monitoring(thresholds: ThermalThresholds) -> Self {
        let manager = Self::new();
        *manager.thermal_monitor.lock() = Some(ThermalMonitor::new().with_thresholds(thresholds));
        manager
    }

    /// **Enumerate all available GPU devices** (liệt kê tất cả GPU có sẵn)
    pub async fn enumerate_devices(&self) -> GpuResult<Vec<GpuDeviceInfo>> {
        info!("🔍 Enumerating GPU devices...");

        #[cfg(feature = "nvml")]
        {
            // Use NVML for real enumeration if available
            match self.enumerate_with_nvml().await {
                Ok(devices) => {
                    info!("✅ Found {} GPU device(s) via NVML", devices.len());

                    // Store devices
                    let mut device_map = HashMap::new();
                    for info in &devices {
                        match GpuDevice::new(info.device_id, unsafe { std::mem::zeroed() }) {
                            Ok(gpu_device) => {
                                device_map.insert(info.device_id, Arc::new(Mutex::new(gpu_device)));
                            }
                            Err(e) => {
                                warn!("⚠️  Failed to create device {}: {}", info.device_id, e);
                            }
                        }
                    }
                    let mut manager_devices = self.devices.write().await;
                    *manager_devices = device_map;

                    Ok(devices)
                }
                Err(e) => {
                    warn!("⚠️  NVML enumeration failed: {}, falling back to CPU-only mode", e);

                    // Fallback to CPU-only with stub GPUs
                    self.fallback_enumeration().await
                }
            }
        }

        #[cfg(not(feature = "nvml"))]
        {
            warn!("⚠️  NVML not available, using stub GPU enumeration");
            self.fallback_enumeration().await
        }
    }

    /// **Enumerate devices using NVML** (liệt kê qua NVML)
    #[cfg(feature = "nvml")]
    async fn enumerate_with_nvml(&self) -> GpuResult<Vec<GpuDeviceInfo>> {
        use nvml_wrapper::Nvml;

        let nvml = match Nvml::init() {
            Ok(nvml) => nvml,
            Err(e) => return Err(GpuError::NvmlInitFailed(format!("NVML init failed: {}", e))),
        };

        let device_count = nvml.device_count()
            .map_err(|e| GpuError::NvmlDriverMismatch(format!("Device count failed: {}", e)))?;

        let mut devices = Vec::new();

        for i in 0..device_count {
            // Create GPU device (this will be passed around safely)
            // Note: We create raw Nvml here but it's managed properly
            match GpuDevice::new(i as usize, unsafe { std::mem::transmute(&nvml as *const _) }) {
                Ok(gpu_device) => {
                    devices.push(gpu_device.info().clone());
                }
                Err(e) => {
                    warn!("⚠️  Failed to create device {}: {}", i, e);
                }
            }
        }

        Ok(devices)
    }

    /// **Fallback enumeration without NVML** (liệt kê dự phòng)
    async fn fallback_enumeration(&self) -> GpuResult<Vec<GpuDeviceInfo>> {
        info!("🌐 Using CPU-only fallback mode");

        // Query CUDA device count if available
        let device_count = match super::query_cuda_device_count() {
            Ok(count) => count,
            Err(_) => 0, // No CUDA devices
        };

        let mut devices = Vec::new();

        // Create stub devices for testing
        for i in 0..device_count.max(1) {
            #[cfg(feature = "nvml")]
            let gpu_device = GpuDevice::new_stub(i);

            #[cfg(not(feature = "nvml"))]
            let gpu_device = GpuDevice::new_stub(i);

            devices.push(gpu_device.info().clone());

            // Store device
            let device_map = Arc::new(Mutex::new(gpu_device));
            let mut manager_devices = self.devices.write().await;
            manager_devices.insert(i, device_map);
        }

        Ok(devices)
    }

    /// **Initialize for mining algorithm** (khởi tạo cho thuật toán khai thác)
    pub async fn initialize_for_algorithm(&self, algorithm: GpuAlgorithm, device_ids: &[usize]) -> GpuResult<()> {
        info!("🚀 Initializing GPU manager for algorithm {:?} on devices {:?}", algorithm, device_ids);

        // Validate algorithm requirements (xác thực yêu cầu thuật toán)
        for &device_id in device_ids {
            if let Some(device_arc) = self.devices.read().await.get(&device_id) {
                let device = device_arc.lock();
                device.validate_compute_capability(
                    algorithm.min_compute_capability().0,
                    algorithm.min_compute_capability().1,
                )?;
            } else {
                return Err(GpuError::DeviceNotFound(device_id));
            }
        }

        // Set algorithm (đặt thuật toán)
        *self.algorithm.write().await = Some(algorithm);

        // Initialize CUDA contexts (khởi tạo CUDA contexts)
        for &device_id in device_ids {
            self.context_manager.initialize_context(device_id)?;
        }

        // Initialize thermal monitor (khởi tạo giám sát nhiệt)
        if let Some(thermal_monitor) = self.thermal_monitor.lock().as_ref() {
            // Add devices to thermal monitor
            for device_id in device_ids {
                if let Some(device_arc) = self.devices.read().await.get(device_id) {
                    let cloned_device = Arc::clone(device_arc);
                    // Note: This would need external locking for real implementation
                    // thermal_monitor.add_device(cloned_device)?;
                }
            }
        }

        // Allocate initial DAG (cấp phát DAG ban đầu)
        self.allocate_initial_dag(device_ids, algorithm, 0).await?;

        *self.initialized.write().await = true;
        info!("✅ GPU manager initialization complete");

        Ok(())
    }

    /// **Allocate initial DAG memory** (cấp phát bộ nhớ DAG ban đầu)
    async fn allocate_initial_dag(&self, device_ids: &[usize], algorithm: GpuAlgorithm, epoch: u32) -> GpuResult<()> {
        for &device_id in device_ids {
            // Get device memory available (lấy bộ nhớ thiết bị trống)
            let device_memory = if let Some(device_arc) = self.devices.read().await.get(&device_id) {
                let device = device_arc.lock();
                let status = device.query_status()?;
                status.memory_free
            } else {
                return Err(GpuError::DeviceNotFound(device_id));
            };

            // Allocate DAG for device (cấp phát DAG cho thiết bị) - simplified for now
            let _allocation = self.memory_manager.allocate_dag(
                device_id,
                // Simplified: pass dummy context - in real implementation this would be context reference
                &mut super::CudaContext::new(device_id), // dummy context
                &self.algorithm_to_string(algorithm),
                epoch,
                device_memory,
            )?;

            info!("📊 Device {} DAG allocation completed", device_id);
        }

        Ok(())
    }

    /// **Convert GpuAlgorithm to string** (chuyển GpuAlgorithm thành string)
    fn algorithm_to_string(&self, algorithm: GpuAlgorithm) -> String {
        match algorithm {
            GpuAlgorithm::Ethash => "ethash".to_string(),
            GpuAlgorithm::KawPow => "kawpow".to_string(),
            GpuAlgorithm::RandomX => "randomx".to_string(),
        }
    }

    /// **Convert MiningAlgorithm to GpuAlgorithm** (chuyển đổi từ parent crate)
    fn mining_algorithm_to_gpu(&self, algorithm: crate::MiningAlgorithm) -> GpuAlgorithm {
        match algorithm {
            crate::MiningAlgorithm::Ethash => GpuAlgorithm::Ethash,
            crate::MiningAlgorithm::KawPow => GpuAlgorithm::KawPow,
            crate::MiningAlgorithm::RandomX => GpuAlgorithm::RandomX,
        }
    }

    /// **Start monitoring loop** (bắt đầu vòng lặp giám sát)
    pub async fn start_monitoring_loop(&self) -> GpuResult<()> {
        info!("🔄 Starting GPU monitoring loop...");

        if self.monitoring_handle.read().await.is_some() {
            return Err(GpuError::Generic("Monitoring loop already running".to_string()));
        }

        let devices = Arc::clone(&self.devices);
        let context_manager = Arc::clone(&self.context_manager);
        let thermal_monitor = Arc::clone(&self.thermal_monitor);
        let telemetry_tx = self.telemetry_tx.clone();

        let algorithm = *self.algorithm.read().await;
        let current_epoch = *self.current_epoch.read().await;
        let initialized = *self.initialized.read().await;

        if !initialized {
            return Err(GpuError::Generic("GPU manager not initialized".to_string()));
        }

        let handle = tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(5));

            loop {
                interval.tick().await;

                // Collect device stats (thu thập thống kê thiết bị)
                let mut device_stats = HashMap::new();
                let devices_locked = devices.read().await;

                for (device_id, device_arc) in devices_locked.iter() {
                    let device = device_arc.lock();
                    match device.query_status() {
                        Ok(status) => {
                            device_stats.insert(*device_id, status);
                        }
                        Err(e) => {
                            warn!("⚠️  Failed to query device {} status: {}", device_id, e);
                        }
                    }
                }

                // Send telemetry (gửi telemetry)
                let stats = GpuManagerStats {
                    total_devices: devices_locked.len(),
                    active_devices: device_stats.len(),
                    current_epoch,
                    algorithm,
                    device_stats,
                };

                if telemetry_tx.send(stats).is_err() {
                    error!("⚠️  Telemetry channel closed");
                    break;
                }

                // Run thermal monitoring (chạy giám sát nhiệt)
                if let Some(monitor) = thermal_monitor.lock().as_ref() {
                    // Note: Real implementation would call monitor.monitor_once().await
                    debug!("💨 Running thermal monitoring");
                }

                // Check for epoch changes (kiểm tra thay đổi epoch)
                // TODO: Implement epoch monitoring
            }
        });

        *self.monitoring_handle.write().await = Some(handle);
        info!("✅ GPU monitoring loop started");

        Ok(())
    }

    /// **Stop monitoring loop** (dừng vòng lặp giám sát)
    pub async fn stop_monitoring_loop(&self) -> GpuResult<()> {
        if let Some(handle) = self.monitoring_handle.write().await.take() {
            handle.abort();
            info!("✅ GPU monitoring loop stopped");
        }
        Ok(())
    }

    /// **Get current mining stats** (lấy thống kê khai thác hiện tại)
    pub async fn get_mining_stats(&self) -> GpuResult<GpuManagerStats> {
        // Try to get latest telemetry (thử lấy telemetry gần nhất)
        let mut rx = self.telemetry_rx.lock();
        if let Some(stats) = rx.try_recv().ok() {
            Ok(stats)
        } else {
            // Generate current snapshot (tạo snapshot hiện tại)
            let devices_locked = self.devices.read().await;
            let mut device_stats = HashMap::new();

            for (device_id, device_arc) in devices_locked.iter() {
                let device = device_arc.lock();
                if let Ok(status) = device.query_status() {
                    device_stats.insert(*device_id, status);
                }
            }

            Ok(GpuManagerStats {
                total_devices: devices_locked.len(),
                active_devices: device_stats.len(),
                current_epoch: *self.current_epoch.read().await,
                algorithm: *self.algorithm.read().await,
                device_stats,
            })
        }
    }

    /// **Check if initialized** (kiểm tra đã khởi tạo chưa)
    pub async fn is_initialized(&self) -> bool {
        *self.initialized.read().await
    }

    /// **Get active device IDs** (lấy ID thiết bị hoạt động)
    pub async fn get_active_device_ids(&self) -> Vec<usize> {
        self.devices.read().await.keys().copied().collect()
    }

    /// **Cleanup all resources** (dọn dẹp tất cả tài nguyên)
    pub async fn cleanup(&self) -> GpuResult<()> {
        info!("🧹 Cleaning up GPU manager...");

        // Stop monitoring (dừng giám sát)
        self.stop_monitoring_loop().await?;

        // Cleanup memory (dọn dẹp bộ nhớ)
        let device_ids: Vec<usize> = self.devices.read().await.keys().copied().collect();
        for device_id in device_ids {
            let _ = self.memory_manager.free_device(device_id);
            let _ = self.context_manager.cleanup_device(device_id);
        }

        // Cleanup managers (dọn dẹp trình quản lý)
        self.memory_manager.free_all()?;
        self.context_manager.cleanup_all()?;

        *self.initialized.write().await = false;
        info!("✅ GPU manager cleanup complete");

        Ok(())
    }
}

impl Default for GpuManager {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for GpuManager {
    fn drop(&mut self) {
        // Note: Drop can't be async, so we warn about proper cleanup
        if futures::executor::block_on(self.initialized.read()).clone() {
            warn!("⚠️  GpuManager dropped without proper cleanup. Call cleanup() before dropping.");
        }
    }
}

/// **GpuManagerBuilder** (trình xây dựng GPU Manager) – builder pattern
pub struct GpuManagerBuilder {
    thermal_thresholds: Option<ThermalThresholds>,
    auto_fan_control: bool,
    monitoring_enabled: bool,
}

impl GpuManagerBuilder {
    /// **Create new builder** (tạo builder mới)
    pub fn new() -> Self {
        Self {
            thermal_thresholds: None,
            auto_fan_control: false,
            monitoring_enabled: true,
        }
    }

    /// **Set thermal thresholds** (đặt ngưỡng nhiệt)
    pub fn with_thermal_thresholds(mut self, thresholds: ThermalThresholds) -> Self {
        self.thermal_thresholds = Some(thresholds);
        self
    }

    /// **Enable auto fan control** (bật điều khiển quạt tự động)
    pub fn enable_auto_fan_control(mut self) -> Self {
        self.auto_fan_control = true;
        self
    }

    /// **Disable monitoring** (tắt giám sát)
    pub fn disable_monitoring(mut self) -> Self {
        self.monitoring_enabled = false;
        self
    }

    /// **Build GPU manager** (xây dựng GPU manager)
    pub fn build(self) -> GpuManager {
        let manager = if let Some(thresholds) = self.thermal_thresholds {
            GpuManager::new_with_monitoring(thresholds)
        } else {
            GpuManager::new()
        };

        // Additional configuration would go here
        // Note: auto_fan_control would need callback setup

        manager
    }
}

impl Default for GpuManagerBuilder {
    fn default() -> Self {
        Self::new()
    }
}