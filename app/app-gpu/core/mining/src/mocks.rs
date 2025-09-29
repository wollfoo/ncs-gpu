//! Mock implementations for testing and standalone compilation

use anyhow::Result;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;

// Mock GPU types
#[derive(Debug, Clone)]
pub struct MockGpuDevice {
    pub id: usize,
    pub name: String,
}

#[derive(Debug, Clone)]
pub struct MockGpuMemory {
    pub size: usize,
}

#[derive(Debug, Clone)]
pub struct MockGpuKernel {
    pub name: String,
}

#[derive(Debug, Clone)]
pub struct MockGpuInfo {
    pub name: String,
    pub total_memory: usize,
    pub available_memory: usize,
    pub capabilities: MockGpuCapabilities,
}

#[derive(Debug, Clone)]
pub struct MockGpuCapabilities {
    pub compute_capability_major: u32,
    pub compute_capability_minor: u32,
}

// Mock Message Bus types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub id: Uuid,
    pub topic: String,
    pub payload: Option<serde_json::Value>,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

impl Message {
    pub fn new(topic: String, payload: serde_json::Value, reply_to: Option<Uuid>) -> Self {
        Self {
            id: Uuid::new_v4(),
            topic,
            payload: Some(payload),
            timestamp: chrono::Utc::now(),
        }
    }
}

#[async_trait]
pub trait MessageBus: Send + Sync {
    async fn publish(&self, message: Message) -> Result<()>;
    async fn subscribe(&self, topic: &str) -> Result<()>;
}

#[async_trait]
pub trait MessageHandler: Send + Sync {
    async fn handle_message(&self, message: &Message) -> Result<()>;
}

// Mock GPU Device trait
#[async_trait]
pub trait GpuDevice: Send + Sync {
    fn name(&self) -> String;
    async fn get_info(&self) -> Result<MockGpuInfo>;
    async fn allocate_memory(&self, size: usize) -> Result<Arc<dyn GpuMemory>>;
    async fn create_kernel(&self, source: &str, entry_point: &str) -> Result<Arc<dyn GpuKernel>>;
    async fn get_utilization(&self) -> Result<f64>;
    async fn get_temperature(&self) -> Result<f32>;
    async fn get_power_consumption(&self) -> Result<f32>;
    async fn get_memory_utilization(&self) -> Result<f64>;
    async fn get_fan_speed(&self) -> Result<f64>;
    async fn synchronize(&self) -> Result<()>;
}

#[async_trait]
pub trait GpuMemory: Send + Sync {
    fn size(&self) -> usize;
    fn as_raw_ptr(&self) -> u64;
}

#[async_trait]
pub trait GpuKernel: Send + Sync {
    async fn set_parameter(&self, index: u32, value: u64) -> Result<()>;
    async fn launch(&self, work_groups: usize, work_group_size: usize) -> Result<()>;
}

// Mock Manager trait
#[async_trait]
pub trait GpuManager: Send + Sync {
    async fn get_device(&self, device_id: usize) -> Result<Arc<dyn GpuDevice>>;
    async fn list_devices(&self) -> Result<Vec<Arc<dyn GpuDevice>>>;
}

// Mock implementations
#[async_trait]
impl GpuDevice for MockGpuDevice {
    fn name(&self) -> String {
        self.name.clone()
    }

    async fn get_info(&self) -> Result<MockGpuInfo> {
        Ok(MockGpuInfo {
            name: self.name.clone(),
            total_memory: 8 * 1024 * 1024 * 1024, // 8GB
            available_memory: 6 * 1024 * 1024 * 1024, // 6GB
            capabilities: MockGpuCapabilities {
                compute_capability_major: 8,
                compute_capability_minor: 0,
            },
        })
    }

    async fn allocate_memory(&self, size: usize) -> Result<Arc<dyn GpuMemory>> {
        Ok(Arc::new(MockGpuMemory { size }))
    }

    async fn create_kernel(&self, source: &str, entry_point: &str) -> Result<Arc<dyn GpuKernel>> {
        Ok(Arc::new(MockGpuKernel {
            name: entry_point.to_string()
        }))
    }

    async fn get_utilization(&self) -> Result<f64> {
        Ok(0.85) // 85% utilization
    }

    async fn get_temperature(&self) -> Result<f32> {
        Ok(75.0) // 75°C
    }

    async fn get_power_consumption(&self) -> Result<f32> {
        Ok(250.0) // 250W
    }

    async fn get_memory_utilization(&self) -> Result<f64> {
        Ok(0.75) // 75% memory usage
    }

    async fn get_fan_speed(&self) -> Result<f64> {
        Ok(0.8) // 80% fan speed
    }

    async fn synchronize(&self) -> Result<()> {
        Ok(())
    }
}

#[async_trait]
impl GpuMemory for MockGpuMemory {
    fn size(&self) -> usize {
        self.size
    }

    fn as_raw_ptr(&self) -> u64 {
        0x1000000 // Mock pointer
    }
}

#[async_trait]
impl GpuKernel for MockGpuKernel {
    async fn set_parameter(&self, _index: u32, _value: u64) -> Result<()> {
        Ok(())
    }

    async fn launch(&self, _work_groups: usize, _work_group_size: usize) -> Result<()> {
        Ok(())
    }
}

pub struct MockGpuManager;

#[async_trait]
impl GpuManager for MockGpuManager {
    async fn get_device(&self, device_id: usize) -> Result<Arc<dyn GpuDevice>> {
        Ok(Arc::new(MockGpuDevice {
            id: device_id,
            name: format!("Mock GPU {}", device_id),
        }))
    }

    async fn list_devices(&self) -> Result<Vec<Arc<dyn GpuDevice>>> {
        Ok(vec![
            Arc::new(MockGpuDevice { id: 0, name: "Mock GPU 0".to_string() }),
            Arc::new(MockGpuDevice { id: 1, name: "Mock GPU 1".to_string() }),
        ])
    }
}

pub struct MockMessageBus;

#[async_trait]
impl MessageBus for MockMessageBus {
    async fn publish(&self, _message: Message) -> Result<()> {
        Ok(())
    }

    async fn subscribe(&self, _topic: &str) -> Result<()> {
        Ok(())
    }
}