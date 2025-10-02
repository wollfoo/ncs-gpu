//! # GPU Management Module (Module Quản Lý GPU)
//!
//! **Complete GPU mining management system** (hệ thống quản lý khai thác GPU hoàn chỉnh)
//! với device discovery, thermal monitoring, CUDA context lifecycle,
//! DAG memory allocation, fan control và comprehensive error handling.
//!
//! ## Architecture Overview (Tổng quan kiến trúc)
//!
//! ```
//! gpu/
//! ├── manager.rs       # GpuManager (orchestrator) - điều phối viên chính
//! ├── device.rs        # GpuDevice (abstraction) - trừu tượng hóa thiết bị
//! ├── context.rs       # CudaContextManager - quản lý CUDA contexts
//! ├── memory.rs        # DagMemoryManager - quản lý bộ nhớ DAG
//! ├── thermal.rs       # ThermalMonitor - giám sát nhiệt độ
//! └── error.rs         # GpuError types - định nghĩa lỗi GPU
//! ```
//!
//! ## Feature Flags (Cờ tính năng)
//!
//! - `nvml`: Enable NVML GPU monitoring (default) - Bật giám sát GPU qua NVML
//! - `cuda`: Enable CUDA kernel compilation - Bật biên dịch kernel CUDA
//!
//! ## Example Usage (Ví dụ sử dụng)
//!
//! ```rust,ignore
//! use mining_core::gpu::{GpuManager, ThermalThresholds};
//!
//! // Create GPU manager with thermal monitoring
//! let manager = GpuManager::new_with_monitoring(ThermalThresholds::default());
//!
//! // Initialize for Ethash mining
//! manager.initialize_for_algorithm(MiningAlgorithm::Ethash, &[0, 1]).await?;
//!
//! // Start monitoring loop
//! manager.start_monitoring_loop().await;
//!
//! // Get mining stats
//! let stats = manager.get_mining_stats().await?;
//! ```

pub mod context;
pub mod device;
pub mod error;
pub mod manager;
pub mod memory;
pub mod thermal;

// Re-export main types for convenient access (Xuất lại các kiểu chính)
pub use context::{CudaContext, CudaContextManager};
pub use device::{GpuDevice, GpuDeviceInfo, GpuDeviceStatus};
pub use error::{GpuError, GpuResult};
pub use manager::{GpuAlgorithm, GpuManager, GpuManagerBuilder, GpuManagerStats};
pub use memory::{DagAllocationInfo, DagMemoryManager, DagMemoryPool, DeviceMemory};
pub use thermal::{ThermalMonitor, ThermalEvent, ThermalThresholds};

// Export CUDA device count query (Xuất hàm query số lượng thiết bị CUDA)
pub use context::query_cuda_device_count;

// Placeholder for future GpuManager integration
// TODO: Implement GpuManager as main orchestrator
// pub struct GpuManager { ... }

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_module_exports() {
        // Test that key types are exported
        let _error: GpuError = GpuError::DeviceNotFound(0);
        let _thresholds = ThermalThresholds::default();

        // This should compile without issues
        assert!(true);
    }
}
