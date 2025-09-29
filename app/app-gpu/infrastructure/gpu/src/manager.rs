use crate::{GpuDevice, GpuDeviceInfo, GpuDeviceType, GenericGpuDevice};
use anyhow::Result;
use std::collections::HashMap;
use std::sync::Arc;
use tracing::{info, warn};
use uuid::Uuid;

/// GPU Manager for discovering and managing GPU devices
pub struct GpuManager {
    devices: HashMap<Uuid, Arc<dyn GpuDevice>>,
}

impl GpuManager {
    pub async fn new() -> Result<Self> {
        let mut manager = Self {
            devices: HashMap::new(),
        };
        
        manager.discover_devices().await?;
        Ok(manager)
    }
    
    async fn discover_devices(&mut self) -> Result<()> {
        info!("🔍 Discovering GPU devices");
        
        // Create mock devices for demonstration
        let mock_device1 = GpuDeviceInfo {
            id: Uuid::new_v4(),
            name: "NVIDIA RTX 4090".to_string(),
            device_type: GpuDeviceType::Cuda,
            memory_total: 24 * 1024 * 1024 * 1024, // 24GB
            memory_available: 20 * 1024 * 1024 * 1024, // 20GB available
            core_count: 16384,
            vendor: "NVIDIA".to_string(),
            ..Default::default()
        };
        
        let device1 = Arc::new(GenericGpuDevice::new(mock_device1));
        self.devices.insert(device1.id(), device1);
        
        info!("✅ Discovered {} GPU devices", self.devices.len());
        Ok(())
    }
    
    pub async fn get_device(&self, id: Uuid) -> Option<Arc<dyn GpuDevice>> {
        self.devices.get(&id).cloned()
    }
    
    pub async fn get_devices(&self, device_indices: &[usize]) -> Result<Vec<Arc<dyn GpuDevice>>> {
        let available_devices: Vec<_> = self.devices.values().cloned().collect();
        
        let mut selected_devices = Vec::new();
        for &index in device_indices {
            if let Some(device) = available_devices.get(index) {
                selected_devices.push(device.clone());
            } else {
                warn!("⚠️ Device index {} not found", index);
            }
        }
        
        Ok(selected_devices)
    }
    
    pub async fn get_all_devices(&self) -> Vec<Arc<dyn GpuDevice>> {
        self.devices.values().cloned().collect()
    }
    
    pub fn device_count(&self) -> usize {
        self.devices.len()
    }
}