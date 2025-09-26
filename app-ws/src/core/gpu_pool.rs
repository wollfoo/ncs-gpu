//! **GPU Resource Pool** (nhóm tài nguyên GPU – quản lý card đồ họa)

use anyhow::{Context, Result};
use nvml_wrapper::{Nvml, Device as NvmlDevice};
use parking_lot::RwLock;
use std::sync::Arc;
use tracing::{debug, error, info, warn};

use crate::utils::config::GpuConfig;

/// **GPU Device Information** (thông tin thiết bị GPU – chi tiết card đồ họa)
#[derive(Debug, Clone)]
pub struct GpuDevice {
    /// Device index
    pub index: u32,
    /// Device name
    pub name: String,
    /// Device UUID
    pub uuid: String,
    /// Total memory in bytes
    pub total_memory: u64,
    /// Available memory in bytes
    pub available_memory: Arc<RwLock<u64>>,
    /// Current utilization percentage
    pub utilization: Arc<RwLock<u32>>,
    /// Temperature in Celsius
    pub temperature: Arc<RwLock<u32>>,
    /// Power usage in watts
    pub power_usage: Arc<RwLock<u32>>,
}

/// **GPU Pool** (nhóm GPU – quản lý tập hợp card đồ họa)
pub struct GpuPool {
    /// NVML handle
    nvml: Arc<Nvml>,
    /// Available GPU devices
    devices: Vec<Arc<GpuDevice>>,
    /// Configuration
    config: GpuConfig,
    /// Pool statistics
    stats: Arc<RwLock<PoolStats>>,
}

/// **Pool Statistics** (thống kê nhóm – chỉ số tập hợp)
#[derive(Debug, Default)]
struct PoolStats {
    /// Total allocations
    total_allocations: u64,
    /// Failed allocations
    failed_allocations: u64,
    /// Current active allocations
    active_allocations: u32,
}

impl GpuPool {
    /// **Create new GPU pool** (tạo nhóm GPU mới – khởi tạo quản lý card đồ họa)
    pub async fn new(config: GpuConfig) -> Result<Self> {
        info!("🎮 Initializing GPU pool");

        // Initialize NVML
        let nvml = Nvml::init().context("Failed to initialize NVML")?;
        let nvml = Arc::new(nvml);

        // Detect available GPUs
        let device_count = nvml.device_count().context("Failed to get device count")?;
        info!("🔍 Found {} GPU devices", device_count);

        let mut devices = Vec::new();

        for i in 0..device_count {
            match Self::create_device(&nvml, i) {
                Ok(device) => {
                    info!(
                        "✅ GPU {}: {} ({})",
                        i, device.name, device.uuid
                    );
                    devices.push(Arc::new(device));
                }
                Err(e) => {
                    error!("❌ Failed to initialize GPU {}: {}", i, e);
                }
            }
        }

        if devices.is_empty() {
            return Err(anyhow::anyhow!("No usable GPU devices found"));
        }

        Ok(Self {
            nvml,
            devices,
            config,
            stats: Arc::new(RwLock::new(PoolStats::default())),
        })
    }

    /// **Create device info** (tạo thông tin thiết bị – khởi tạo chi tiết GPU)
    fn create_device(nvml: &Nvml, index: u32) -> Result<GpuDevice> {
        let device = nvml.device_by_index(index)
            .with_context(|| format!("Failed to get device {}", index))?;

        let name = device.name()
            .unwrap_or_else(|_| format!("GPU {}", index));
        
        let uuid = device.uuid()
            .unwrap_or_else(|_| format!("GPU-{}", index));

        let memory_info = device.memory_info()
            .context("Failed to get memory info")?;

        let utilization = device.utilization_rates()
            .map(|u| u.gpu)
            .unwrap_or(0);

        let temperature = device.temperature(nvml_wrapper::enum_wrappers::device::TemperatureSensor::Gpu)
            .unwrap_or(0);

        let power_usage = device.power_usage()
            .map(|p| p / 1000) // Convert mW to W
            .unwrap_or(0);

        Ok(GpuDevice {
            index,
            name,
            uuid,
            total_memory: memory_info.total,
            available_memory: Arc::new(RwLock::new(memory_info.free)),
            utilization: Arc::new(RwLock::new(utilization)),
            temperature: Arc::new(RwLock::new(temperature)),
            power_usage: Arc::new(RwLock::new(power_usage)),
        })
    }

    /// **Get device count** (lấy số lượng thiết bị – đếm card đồ họa)
    pub fn device_count(&self) -> usize {
        self.devices.len()
    }

    /// **Get device by index** (lấy thiết bị theo chỉ số – tìm GPU theo vị trí)
    pub fn get_device(&self, index: usize) -> Option<Arc<GpuDevice>> {
        self.devices.get(index).cloned()
    }

    /// **Get all devices** (lấy tất cả thiết bị – danh sách GPU)
    pub fn devices(&self) -> &[Arc<GpuDevice>] {
        &self.devices
    }

    /// **Allocate GPU for task** (cấp phát GPU cho tác vụ – phân bổ card đồ họa)
    pub async fn allocate(&self) -> Result<Arc<GpuDevice>> {
        // Update stats
        {
            let mut stats = self.stats.write();
            stats.total_allocations += 1;
        }

        // Find least loaded GPU
        let device = self.find_best_device()
            .ok_or_else(|| {
                let mut stats = self.stats.write();
                stats.failed_allocations += 1;
                anyhow::anyhow!("No available GPU for allocation")
            })?;

        // Update active allocations
        {
            let mut stats = self.stats.write();
            stats.active_allocations += 1;
        }

        debug!(
            "📌 Allocated GPU {}: {} (util: {}%)",
            device.index,
            device.name,
            *device.utilization.read()
        );

        Ok(device)
    }

    /// **Find best available device** (tìm thiết bị tốt nhất – chọn GPU phù hợp)
    fn find_best_device(&self) -> Option<Arc<GpuDevice>> {
        self.devices
            .iter()
            .filter(|d| {
                let util = *d.utilization.read();
                let temp = *d.temperature.read();
                
                // Check thresholds
                util < self.config.max_utilization &&
                temp < self.config.max_temperature
            })
            .min_by_key(|d| *d.utilization.read())
            .cloned()
    }

    /// **Release GPU allocation** (giải phóng cấp phát GPU – trả lại card đồ họa)
    pub async fn release(&self, device: Arc<GpuDevice>) -> Result<()> {
        {
            let mut stats = self.stats.write();
            stats.active_allocations = stats.active_allocations.saturating_sub(1);
        }

        debug!("📌 Released GPU {}: {}", device.index, device.name);
        Ok(())
    }

    /// **Update device metrics** (cập nhật chỉ số thiết bị – làm mới thông số GPU)
    pub async fn update_metrics(&self) -> Result<()> {
        for (i, device) in self.devices.iter().enumerate() {
            if let Ok(nvml_device) = self.nvml.device_by_index(i as u32) {
                // Update memory
                if let Ok(mem_info) = nvml_device.memory_info() {
                    *device.available_memory.write() = mem_info.free;
                }

                // Update utilization
                if let Ok(util) = nvml_device.utilization_rates() {
                    *device.utilization.write() = util.gpu;
                }

                // Update temperature
                if let Ok(temp) = nvml_device.temperature(
                    nvml_wrapper::enum_wrappers::device::TemperatureSensor::Gpu
                ) {
                    *device.temperature.write() = temp;
                }

                // Update power
                if let Ok(power) = nvml_device.power_usage() {
                    *device.power_usage.write() = power / 1000; // mW to W
                }
            }
        }

        Ok(())
    }

    /// **Health check** (kiểm tra sức khỏe – xác minh tình trạng)
    pub async fn health_check(&self) -> Result<()> {
        let mut unhealthy = 0;

        for device in &self.devices {
            let temp = *device.temperature.read();
            let util = *device.utilization.read();

            if temp > self.config.max_temperature {
                warn!("⚠️ GPU {} temperature too high: {}°C", device.index, temp);
                unhealthy += 1;
            }

            if util > 95 {
                warn!("⚠️ GPU {} utilization very high: {}%", device.index, util);
            }
        }

        if unhealthy > 0 {
            return Err(anyhow::anyhow!("{} GPUs are unhealthy", unhealthy));
        }

        Ok(())
    }

    /// **Get pool statistics** (lấy thống kê nhóm – xem chỉ số tập hợp)
    pub fn stats(&self) -> PoolStats {
        self.stats.read().clone()
    }
}

impl Drop for GpuPool {
    fn drop(&mut self) {
        info!("🔌 Shutting down GPU pool");
        // NVML cleanup is handled automatically
    }
}