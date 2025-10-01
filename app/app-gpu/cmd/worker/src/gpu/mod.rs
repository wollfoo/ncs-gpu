// GPU management module - Quản lý và điều khiển GPU

use anyhow::{Context, Result};
use nvml_wrapper::{Nvml, Device};
use std::sync::Arc;
use tracing::{debug, info, warn};

pub mod cuda;
pub mod opencl;

pub struct Manager {
    nvml: Arc<Nvml>,
    devices: Vec<GpuDevice>,
}

#[derive(Debug, Clone)]
pub struct GpuDevice {
    pub index: u32,
    pub name: String,
    pub uuid: String,
    pub memory_mb: u64,
    pub compute_capability: String,
    pub max_threads_per_block: u32,
    pub multiprocessor_count: u32,
}

#[derive(Debug, Clone)]
pub struct GpuMetrics {
    pub temperature: u32,
    pub power_watts: u32,
    pub gpu_utilization: u32,
    pub memory_utilization: u32,
    pub memory_used_mb: u64,
    pub memory_total_mb: u64,
    pub fan_speed: u32,
}

impl Manager {
    pub fn new() -> Result<Self> {
        let nvml = Nvml::init()
            .context("Failed to initialize NVML")?;
        
        Ok(Self {
            nvml: Arc::new(nvml),
            devices: Vec::new(),
        })
    }
    
    pub fn enumerate_devices(&mut self) -> Result<&Vec<GpuDevice>> {
        let device_count = self.nvml.device_count()
            .context("Failed to get GPU device count")?;
        
        self.devices.clear();
        
        for i in 0..device_count {
            let device = self.nvml.device_by_index(i)
                .context(format!("Failed to get GPU device {}", i))?;
            
            let gpu_device = self.get_device_info(&device, i)?;
            self.devices.push(gpu_device);
        }
        
        Ok(&self.devices)
    }
    
    fn get_device_info(&self, device: &Device, index: u32) -> Result<GpuDevice> {
        let name = device.name()
            .unwrap_or_else(|_| format!("GPU {}", index));
        
        let uuid = device.uuid()
            .unwrap_or_else(|_| format!("GPU-{}", index));
        
        let memory_info = device.memory_info()
            .context("Failed to get memory info")?;
        
        let compute_cap = device.cuda_compute_capability()
            .map(|cc| format!("{}.{}", cc.major, cc.minor))
            .unwrap_or_else(|_| "Unknown".to_string());
        
        let max_threads = device.max_threads_per_multiprocessor()
            .unwrap_or(1024);
        
        let mp_count = device.num_cores()
            .unwrap_or(1);
        
        Ok(GpuDevice {
            index,
            name,
            uuid,
            memory_mb: memory_info.total / (1024 * 1024),
            compute_capability: compute_cap,
            max_threads_per_block: max_threads,
            multiprocessor_count: mp_count,
        })
    }
    
    pub fn get_metrics(&self, gpu_index: u32) -> Result<GpuMetrics> {
        let device = self.nvml.device_by_index(gpu_index)
            .context(format!("Failed to get GPU device {}", gpu_index))?;
        
        let temperature = device.temperature(nvml_wrapper::enum_wrappers::device::TemperatureSensor::Gpu)
            .unwrap_or(0);
        
        let power = device.power_usage()
            .map(|p| p / 1000) // mW to W
            .unwrap_or(0);
        
        let utilization = device.utilization_rates()
            .context("Failed to get utilization")?;
        
        let memory_info = device.memory_info()
            .context("Failed to get memory info")?;
        
        let fan_speed = device.fan_speed(0)
            .unwrap_or(0);
        
        Ok(GpuMetrics {
            temperature,
            power_watts: power,
            gpu_utilization: utilization.gpu,
            memory_utilization: utilization.memory,
            memory_used_mb: memory_info.used / (1024 * 1024),
            memory_total_mb: memory_info.total / (1024 * 1024),
            fan_speed,
        })
    }
    
    pub fn set_power_limit(&self, gpu_index: u32, watts: u32) -> Result<()> {
        let device = self.nvml.device_by_index(gpu_index)?;
        let milliwatts = watts * 1000;
        
        device.set_power_management_limit(milliwatts)
            .context(format!("Failed to set power limit for GPU {}", gpu_index))?;
        
        info!("Set power limit for GPU {} to {} W", gpu_index, watts);
        Ok(())
    }
    
    pub fn set_gpu_clocks(&self, gpu_index: u32, memory_mhz: Option<u32>, core_mhz: Option<u32>) -> Result<()> {
        let device = self.nvml.device_by_index(gpu_index)?;
        
        if let Some(mem) = memory_mhz {
            device.set_mem_clocked_frequency(mem, mem)
                .context("Failed to set memory clock")?;
            debug!("Set GPU {} memory clock to {} MHz", gpu_index, mem);
        }
        
        if let Some(core) = core_mhz {
            device.set_gpu_clocked_frequency(core, core)
                .context("Failed to set core clock")?;
            debug!("Set GPU {} core clock to {} MHz", gpu_index, core);
        }
        
        Ok(())
    }
    
    pub fn reset_clocks(&self, gpu_index: u32) -> Result<()> {
        let device = self.nvml.device_by_index(gpu_index)?;
        device.reset_gpu_clocked_frequency()
            .context("Failed to reset GPU clocks")?;
        device.reset_mem_clocked_frequency()
            .context("Failed to reset memory clocks")?;
        
        info!("Reset clocks for GPU {}", gpu_index);
        Ok(())
    }
}

impl Drop for Manager {
    fn drop(&mut self) {
        // Reset all GPUs to default state
        for device in &self.devices {
            if let Err(e) = self.reset_clocks(device.index) {
                warn!("Failed to reset GPU {} on shutdown: {}", device.index, e);
            }
        }
    }
}
