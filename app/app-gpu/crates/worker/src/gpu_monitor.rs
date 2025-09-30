use gpu_common::{GpuDevice, GpuError, Result};
use nvml_wrapper::Nvml;
use tracing::info;

/// **[GPU Stats]** (Thống kê GPU – runtime metrics)
pub struct GpuStats {
    pub utilization: f32,
    pub memory_used_mb: u32,
    pub memory_total_mb: u32,
    pub temperature_c: u32,
    pub power_usage_w: f32,
}

/// **[GPU Monitor]** (Giám sát GPU – NVML wrapper for telemetry)
pub struct GpuMonitor {
    nvml: Nvml,
}

impl GpuMonitor {
    /// **[New]** (Tạo mới – khởi tạo NVML)
    pub fn new() -> Result<Self> {
        let nvml = Nvml::init()
            .map_err(|e| GpuError::Cuda(format!("NVML init failed: {}", e)))?;
        
        info!("✅ NVML initialized");
        Ok(Self { nvml })
    }
    
    /// **[Enumerate Devices]** (Liệt kê thiết bị – discover all GPUs)
    pub fn enumerate_devices(&self) -> Result<Vec<GpuDevice>> {
        let device_count = self.nvml.device_count()
            .map_err(|e| GpuError::Cuda(format!("Failed to get device count: {}", e)))?;
        
        let mut devices = Vec::new();
        
        for i in 0..device_count {
            let device = self.nvml.device_by_index(i)
                .map_err(|e| GpuError::DeviceNotFound(i))?;
            
            let name = device.name()
                .map_err(|e| GpuError::Cuda(format!("Failed to get device name: {}", e)))?;
            
            let memory_info = device.memory_info()
                .map_err(|e| GpuError::Cuda(format!("Failed to get memory info: {}", e)))?;
            
            let uuid = device.uuid()
                .map_err(|e| GpuError::Cuda(format!("Failed to get UUID: {}", e)))?;
            
            let compute_capability = device.cuda_compute_capability()
                .map_err(|e| GpuError::Cuda(format!("Failed to get compute capability: {}", e)))?;
            
            devices.push(GpuDevice {
                index: i,
                name,
                total_memory: memory_info.total,
                compute_capability: (compute_capability.major as u32, compute_capability.minor as u32),
                uuid,
            });
        }
        
        Ok(devices)
    }
    
    /// **[Get GPU Stats]** (Lấy thống kê GPU – runtime metrics)
    pub fn get_gpu_stats(&self, index: u32) -> Result<GpuStats> {
        let device = self.nvml.device_by_index(index)
            .map_err(|_| GpuError::DeviceNotFound(index))?;
        
        let utilization = device.utilization_rates()
            .map(|u| u.gpu as f32)
            .unwrap_or(0.0);
        
        let memory_info = device.memory_info()
            .map_err(|e| GpuError::Cuda(format!("Failed to get memory info: {}", e)))?;
        
        let temperature = device.temperature(nvml_wrapper::enum_wrappers::device::TemperatureSensor::Gpu)
            .unwrap_or(0);
        
        let power_usage = device.power_usage()
            .map(|p| p as f32 / 1000.0) // Convert mW to W
            .unwrap_or(0.0);
        
        Ok(GpuStats {
            utilization,
            memory_used_mb: ((memory_info.total - memory_info.free) / 1024 / 1024) as u32,
            memory_total_mb: (memory_info.total / 1024 / 1024) as u32,
            temperature_c: temperature,
            power_usage_w: power_usage,
        })
    }
}
