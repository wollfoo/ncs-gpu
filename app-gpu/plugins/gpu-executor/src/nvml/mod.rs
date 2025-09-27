//! NVIDIA Management Library (NVML) Integration
//! 
//! GPU monitoring, temperature, power management, and metrics collection

use anyhow::{Result, Context};
use nvml_wrapper::{Nvml, Device};
use nvml_wrapper::enum_wrappers::device::{Clock, TemperatureSensor};
use parking_lot::RwLock;
use std::sync::Arc;
use std::collections::HashMap;
use tracing::{info, debug, warn, error};

/// GPU metrics from NVML
#[derive(Debug, Clone, Default)]
pub struct GpuMetrics {
    /// Temperature in Celsius
    pub temperature: u32,
    
    /// Power usage in Watts
    pub power_usage: u32,
    
    /// Power limit in Watts
    pub power_limit: u32,
    
    /// GPU utilization percentage
    pub gpu_utilization: u32,
    
    /// Memory utilization percentage  
    pub memory_utilization: u32,
    
    /// Memory used in MB
    pub memory_used_mb: u64,
    
    /// Memory total in MB
    pub memory_total_mb: u64,
    
    /// Fan speed percentage
    pub fan_speed: u32,
    
    /// Clock speeds
    pub clocks: ClockSpeeds,
    
    /// PCIe throughput
    pub pcie_throughput: PcieThroughput,
    
    /// Process count
    pub process_count: u32,
}

#[derive(Debug, Clone, Default)]
pub struct ClockSpeeds {
    pub graphics_mhz: u32,
    pub sm_mhz: u32,
    pub memory_mhz: u32,
    pub video_mhz: u32,
}

#[derive(Debug, Clone, Default)]
pub struct PcieThroughput {
    pub rx_mbps: f32,
    pub tx_mbps: f32,
}

/// NVML Monitor for GPU metrics
pub struct NvmlMonitor {
    nvml: Arc<RwLock<Option<Nvml>>>,
    devices: Arc<RwLock<HashMap<u32, Device<'static>>>>,
    metrics_cache: Arc<RwLock<HashMap<u32, GpuMetrics>>>,
    monitoring_enabled: Arc<RwLock<bool>>,
}

impl NvmlMonitor {
    /// Create new NVML monitor
    pub fn new() -> Self {
        Self {
            nvml: Arc::new(RwLock::new(None)),
            devices: Arc::new(RwLock::new(HashMap::new())),
            metrics_cache: Arc::new(RwLock::new(HashMap::new())),
            monitoring_enabled: Arc::new(RwLock::new(false)),
        }
    }
    
    /// Initialize NVML
    pub fn init(&self) -> Result<()> {
        info!("Initializing NVML monitoring");
        
        let nvml = Nvml::init()
            .context("Failed to initialize NVML")?;
        
        let device_count = nvml.device_count()?;
        info!("Found {} GPU devices", device_count);
        
        let mut devices = HashMap::new();
        
        for i in 0..device_count {
            let device = nvml.device_by_index(i)?;
            
            // Get device info
            let name = device.name()?;
            let uuid = device.uuid()?;
            let pci_info = device.pci_info()?;
            
            info!(
                "Device {}: {} (UUID: {}, PCI: {:04x}:{:02x}:{:02x}.{:x})",
                i, name, uuid,
                pci_info.domain,
                pci_info.bus,
                pci_info.device,
                pci_info.pci_device_id
            );
            
            // Store device - need to use unsafe to extend lifetime
            let device_static = unsafe {
                std::mem::transmute::<Device<'_>, Device<'static>>(device)
            };
            devices.insert(i, device_static);
        }
        
        *self.devices.write() = devices;
        *self.nvml.write() = Some(nvml);
        *self.monitoring_enabled.write() = true;
        
        info!("✅ NVML monitoring initialized");
        Ok(())
    }
    
    /// Get temperature for device
    pub fn get_temperature(&self, device_id: u32) -> Result<u32> {
        let devices = self.devices.read();
        let device = devices.get(&device_id)
            .ok_or_else(|| anyhow::anyhow!("Device {} not found", device_id))?;
        
        let temp = device.temperature(TemperatureSensor::Gpu)?;
        Ok(temp)
    }
    
    /// Get power usage for device
    pub fn get_power(&self, device_id: u32) -> Result<(u32, u32)> {
        let devices = self.devices.read();
        let device = devices.get(&device_id)
            .ok_or_else(|| anyhow::anyhow!("Device {} not found", device_id))?;
        
        let power_usage = device.power_usage()? / 1000; // Convert mW to W
        let power_limit = device.power_management_limit()? / 1000;
        
        Ok((power_usage, power_limit))
    }
    
    /// Get utilization for device
    pub fn get_utilization(&self, device_id: u32) -> Result<nvml_wrapper::structs::device::Utilization> {
        let devices = self.devices.read();
        let device = devices.get(&device_id)
            .ok_or_else(|| anyhow::anyhow!("Device {} not found", device_id))?;
        
        let utilization = device.utilization_rates()?;
        Ok(utilization)
    }
    
    /// Get memory info for device
    pub fn get_memory_info(&self, device_id: u32) -> Result<nvml_wrapper::structs::device::MemoryInfo> {
        let devices = self.devices.read();
        let device = devices.get(&device_id)
            .ok_or_else(|| anyhow::anyhow!("Device {} not found", device_id))?;
        
        let memory_info = device.memory_info()?;
        Ok(memory_info)
    }
    
    /// Get clock speeds for device
    pub fn get_clocks(&self, device_id: u32) -> Result<ClockSpeeds> {
        let devices = self.devices.read();
        let device = devices.get(&device_id)
            .ok_or_else(|| anyhow::anyhow!("Device {} not found", device_id))?;
        
        let clocks = ClockSpeeds {
            graphics_mhz: device.clock_info(Clock::Graphics)?,
            sm_mhz: device.clock_info(Clock::SM)?,
            memory_mhz: device.clock_info(Clock::Memory)?,
            video_mhz: device.clock_info(Clock::Video).unwrap_or(0),
        };
        
        Ok(clocks)
    }
    
    /// Collect all metrics for device
    pub fn collect_metrics(&self, device_id: u32) -> Result<GpuMetrics> {
        debug!("Collecting metrics for device {}", device_id);
        
        let devices = self.devices.read();
        let device = devices.get(&device_id)
            .ok_or_else(|| anyhow::anyhow!("Device {} not found", device_id))?;
        
        // Temperature
        let temperature = device.temperature(TemperatureSensor::Gpu)
            .unwrap_or(0);
        
        // Power
        let (power_usage, power_limit) = self.get_power(device_id)
            .unwrap_or((0, 0));
        
        // Utilization
        let utilization = device.utilization_rates()
            .unwrap_or(nvml_wrapper::structs::device::Utilization {
                gpu: 0,
                memory: 0,
            });
        
        // Memory
        let memory_info = device.memory_info()
            .unwrap_or(nvml_wrapper::structs::device::MemoryInfo {
                free: 0,
                total: 0,
                used: 0,
            });
        
        // Fan speed
        let fan_speed = device.fan_speed(0)
            .unwrap_or(0);
        
        // Clocks
        let clocks = self.get_clocks(device_id)
            .unwrap_or_default();
        
        // PCIe throughput
        let pcie_rx = device.pcie_throughput(nvml_wrapper::enum_wrappers::device::PcieUtilCounter::RxBytes)
            .unwrap_or(0) as f32 / 1024.0 / 1024.0; // Convert to MB/s
        
        let pcie_tx = device.pcie_throughput(nvml_wrapper::enum_wrappers::device::PcieUtilCounter::TxBytes)
            .unwrap_or(0) as f32 / 1024.0 / 1024.0;
        
        // Process count
        let process_count = device.running_compute_processes()
            .map(|procs| procs.len() as u32)
            .unwrap_or(0);
        
        let metrics = GpuMetrics {
            temperature,
            power_usage,
            power_limit,
            gpu_utilization: utilization.gpu,
            memory_utilization: utilization.memory,
            memory_used_mb: memory_info.used / 1024 / 1024,
            memory_total_mb: memory_info.total / 1024 / 1024,
            fan_speed,
            clocks,
            pcie_throughput: PcieThroughput {
                rx_mbps: pcie_rx,
                tx_mbps: pcie_tx,
            },
            process_count,
        };
        
        // Cache metrics
        self.metrics_cache.write().insert(device_id, metrics.clone());
        
        Ok(metrics)
    }
    
    /// Set power limit for device
    pub fn set_power_limit(&self, device_id: u32, limit_watts: u32) -> Result<()> {
        let devices = self.devices.read();
        let device = devices.get(&device_id)
            .ok_or_else(|| anyhow::anyhow!("Device {} not found", device_id))?;
        
        let limit_mw = limit_watts * 1000;
        device.set_power_management_limit(limit_mw)?;
        
        info!("Set power limit for device {} to {} W", device_id, limit_watts);
        Ok(())
    }
    
    /// Set GPU clocks
    pub fn set_gpu_clocks(&self, device_id: u32, min_mhz: u32, max_mhz: u32) -> Result<()> {
        let devices = self.devices.read();
        let device = devices.get(&device_id)
            .ok_or_else(|| anyhow::anyhow!("Device {} not found", device_id))?;
        
        device.set_gpu_locked_clocks(min_mhz, max_mhz)?;
        
        info!("Set GPU clocks for device {} to {}-{} MHz", device_id, min_mhz, max_mhz);
        Ok(())
    }
    
    /// Reset GPU clocks to default
    pub fn reset_gpu_clocks(&self, device_id: u32) -> Result<()> {
        let devices = self.devices.read();
        let device = devices.get(&device_id)
            .ok_or_else(|| anyhow::anyhow!("Device {} not found", device_id))?;
        
        device.reset_gpu_locked_clocks()?;
        
        info!("Reset GPU clocks for device {} to default", device_id);
        Ok(())
    }
    
    /// Enable persistence mode
    pub fn set_persistence_mode(&self, device_id: u32, enabled: bool) -> Result<()> {
        let devices = self.devices.read();
        let device = devices.get(&device_id)
            .ok_or_else(|| anyhow::anyhow!("Device {} not found", device_id))?;
        
        device.set_persistent(enabled)?;
        
        info!("Set persistence mode for device {} to {}", device_id, enabled);
        Ok(())
    }
    
    /// Get cached metrics
    pub fn get_cached_metrics(&self, device_id: u32) -> Option<GpuMetrics> {
        self.metrics_cache.read().get(&device_id).cloned()
    }
    
    /// Start monitoring loop
    pub async fn start_monitoring(&self, interval_secs: u64) {
        let enabled = self.monitoring_enabled.clone();
        let devices = self.devices.clone();
        let metrics_cache = self.metrics_cache.clone();
        
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(
                tokio::time::Duration::from_secs(interval_secs)
            );
            
            loop {
                interval.tick().await;
                
                if !*enabled.read() {
                    break;
                }
                
                let device_ids: Vec<u32> = devices.read().keys().cloned().collect();
                
                for device_id in device_ids {
                    // Collect metrics for each device
                    // In real implementation, would call collect_metrics
                    debug!("Monitoring device {}", device_id);
                }
            }
        });
    }
    
    /// Shutdown NVML monitoring
    pub fn shutdown(&self) -> Result<()> {
        info!("Shutting down NVML monitoring");
        
        *self.monitoring_enabled.write() = false;
        self.devices.write().clear();
        self.metrics_cache.write().clear();
        *self.nvml.write() = None;
        
        Ok(())
    }
}

/// Thermal management
pub struct ThermalManager {
    temperature_limit: u32,
    throttle_threshold: u32,
    emergency_threshold: u32,
}

impl ThermalManager {
    pub fn new(temperature_limit: u32) -> Self {
        Self {
            temperature_limit,
            throttle_threshold: temperature_limit - 5,
            emergency_threshold: temperature_limit + 5,
        }
    }
    
    pub fn check_temperature(&self, current_temp: u32) -> ThermalAction {
        if current_temp >= self.emergency_threshold {
            ThermalAction::EmergencyShutdown
        } else if current_temp >= self.temperature_limit {
            ThermalAction::StopWork
        } else if current_temp >= self.throttle_threshold {
            ThermalAction::Throttle
        } else {
            ThermalAction::Normal
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ThermalAction {
    Normal,
    Throttle,
    StopWork,
    EmergencyShutdown,
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_thermal_manager() {
        let manager = ThermalManager::new(80);
        
        assert_eq!(manager.check_temperature(70), ThermalAction::Normal);
        assert_eq!(manager.check_temperature(76), ThermalAction::Throttle);
        assert_eq!(manager.check_temperature(81), ThermalAction::StopWork);
        assert_eq!(manager.check_temperature(86), ThermalAction::EmergencyShutdown);
    }
}
