//! # GPU Management Module (Module Quản Lý GPU)
//!
//! GPU device enumeration, initialization và resource management.

pub mod cuda_wrapper;
pub mod device_query;

use anyhow::Result;
use tracing::{debug, info, warn};

/// GPU device information
#[derive(Debug, Clone)]
pub struct GpuInfo {
    pub id: usize,
    pub name: String,
    pub memory_total: u64,      // Bytes
    pub memory_free: u64,       // Bytes
    pub compute_capability: (u32, u32),
    pub pci_bus_id: String,
}

/// GPU Manager - quản lý GPU devices
pub struct GpuManager {
    devices: Vec<GpuInfo>,
    initialized: bool,
}

impl GpuManager {
    /// Tạo GPU manager mới
    pub fn new() -> Self {
        info!("🎮 Initializing GPU Manager");
        Self {
            devices: Vec::new(),
            initialized: false,
        }
    }

    /// Enumerate tất cả GPU devices
    pub fn enumerate_devices(&mut self) -> Result<()> {
        info!("🔍 Enumerating GPU devices...");

        // TODO: Implement actual GPU enumeration using nvidia-ml-sys
        // For now, return stub data

        warn!("⚠️  GPU enumeration not yet implemented - using stub data");

        // Stub: Add fake GPU for testing
        self.devices.push(GpuInfo {
            id: 0,
            name: "NVIDIA GeForce RTX 3080 (stub)".to_string(),
            memory_total: 10_737_418_240, // 10GB
            memory_free: 9_663_676_416,   // 9GB
            compute_capability: (8, 6),
            pci_bus_id: "0000:01:00.0".to_string(),
        });

        info!("✅ Found {} GPU device(s)", self.devices.len());
        for gpu in &self.devices {
            debug!("  GPU {}: {}", gpu.id, gpu.name);
        }

        Ok(())
    }

    /// Initialize GPU contexts cho selected devices
    pub fn initialize(&mut self, device_ids: &[usize]) -> Result<()> {
        info!("🚀 Initializing GPU contexts for devices: {:?}", device_ids);

        if self.devices.is_empty() {
            self.enumerate_devices()?;
        }

        for &id in device_ids {
            if id >= self.devices.len() {
                anyhow::bail!("Invalid GPU ID: {} (only {} devices available)",
                             id, self.devices.len());
            }

            // TODO: Initialize CUDA context for this device
            // cuda_wrapper::initialize_context(id)?;

            debug!("  Initialized GPU {}", id);
        }

        self.initialized = true;
        info!("✅ GPU initialization complete");

        Ok(())
    }

    /// Get GPU information
    pub fn get_device_info(&self, id: usize) -> Option<&GpuInfo> {
        self.devices.get(id)
    }

    /// Get all devices
    pub fn get_all_devices(&self) -> &[GpuInfo] {
        &self.devices
    }

    /// Check if initialized
    pub fn is_initialized(&self) -> bool {
        self.initialized
    }

    /// Cleanup GPU resources
    pub fn cleanup(&mut self) -> Result<()> {
        info!("🧹 Cleaning up GPU resources...");

        // TODO: Free CUDA contexts

        self.initialized = false;
        info!("✅ GPU cleanup complete");

        Ok(())
    }
}

impl Drop for GpuManager {
    fn drop(&mut self) {
        if self.initialized {
            let _ = self.cleanup();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gpu_manager_creation() {
        let manager = GpuManager::new();
        assert!(!manager.is_initialized());
        assert_eq!(manager.get_all_devices().len(), 0);
    }

    #[test]
    fn test_gpu_enumeration() {
        let mut manager = GpuManager::new();
        manager.enumerate_devices().unwrap();
        assert!(manager.get_all_devices().len() > 0);
    }

    #[test]
    fn test_gpu_initialization() {
        let mut manager = GpuManager::new();
        manager.enumerate_devices().unwrap();
        manager.initialize(&[0]).unwrap();
        assert!(manager.is_initialized());
    }
}
