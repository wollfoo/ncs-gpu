//! # GPU Device Abstraction (Trừu tượng hóa thiết bị GPU)
//!
//! **Individual GPU device management** (quản lý từng thiết bị GPU) với device info, monitoring.

use super::error::{GpuError, GpuResult};
use serde::{Deserialize, Serialize};
use std::fmt;
use tracing::{debug, info, warn};

#[cfg(feature = "nvml")]
use nvml_wrapper::{Device as NvmlDevice, Nvml};

/// **GpuDeviceInfo** (thông tin thiết bị GPU) – static device information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuDeviceInfo {
    /// **Device ID** (ID thiết bị) – GPU index (0, 1, 2,...)
    pub device_id: usize,

    /// **Device name** (tên thiết bị) – GPU model name
    pub name: String,

    /// **Total memory** (tổng bộ nhớ) – VRAM total bytes
    pub memory_total: u64,

    /// **Compute capability** (khả năng tính toán) – (major, minor) version
    pub compute_capability: (u32, u32),

    /// **PCI bus ID** (ID bus PCI) – PCI location
    pub pci_bus_id: String,

    /// **UUID** – GPU unique identifier
    pub uuid: String,

    /// **Driver version** (phiên bản driver) – NVIDIA driver version
    pub driver_version: String,

    /// **CUDA version** – CUDA driver version
    pub cuda_version: String,
}

impl fmt::Display for GpuDeviceInfo {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "GPU {}: {} [CC {}.{}, {}MB VRAM]",
            self.device_id,
            self.name,
            self.compute_capability.0,
            self.compute_capability.1,
            self.memory_total / (1024 * 1024)
        )
    }
}

/// **GpuDeviceStatus** (trạng thái thiết bị GPU) – runtime monitoring data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuDeviceStatus {
    /// **Temperature** (nhiệt độ) – degrees Celsius
    pub temperature: f32,

    /// **Fan speed** (tốc độ quạt) – percentage 0-100
    pub fan_speed: Option<f32>,

    /// **GPU utilization** (sử dụng GPU) – percentage 0-100
    pub utilization: f32,

    /// **Memory utilization** (sử dụng bộ nhớ) – percentage 0-100
    pub memory_utilization: f32,

    /// **Memory used** (bộ nhớ đã dùng) – bytes
    pub memory_used: u64,

    /// **Memory free** (bộ nhớ trống) – bytes
    pub memory_free: u64,

    /// **Power usage** (tiêu thụ điện) – watts
    pub power_usage: Option<f32>,

    /// **Clock speed** (tốc độ xung) – MHz (graphics, memory)
    pub clock_speeds: Option<(u32, u32)>,
}

impl Default for GpuDeviceStatus {
    fn default() -> Self {
        Self {
            temperature: 0.0,
            fan_speed: None,
            utilization: 0.0,
            memory_utilization: 0.0,
            memory_used: 0,
            memory_free: 0,
            power_usage: None,
            clock_speeds: None,
        }
    }
}

/// **GpuDevice** (thiết bị GPU) – wrapper cho NVML device
pub struct GpuDevice {
    /// **Device info** (thông tin thiết bị) – static information
    info: GpuDeviceInfo,

    /// **NVML device handle** – optional NVML device (None nếu NVML disabled)
    #[cfg(feature = "nvml")]
    nvml_device: Option<NvmlDevice<'static>>,
}

impl GpuDevice {
    /// **Create GPU device** (tạo thiết bị GPU) – từ device ID và NVML
    #[cfg(feature = "nvml")]
    pub fn new(device_id: usize, nvml: &'static Nvml) -> GpuResult<Self> {
        debug!("Creating GPU device {}", device_id);

        // Get NVML device handle (lấy handle thiết bị NVML)
        let nvml_device = nvml
            .device_by_index(device_id as u32)
            .map_err(|e| {
                GpuError::DeviceNotFound(device_id)
                    .with_context(format!("NVML error: {}", e))
            })?;

        // Query device info (truy vấn thông tin thiết bị)
        let name = nvml_device
            .name()
            .map_err(|e| GpuError::Generic(format!("Failed to get device name: {}", e)))?;

        let memory_info = nvml_device
            .memory_info()
            .map_err(|e| GpuError::Generic(format!("Failed to get memory info: {}", e)))?;

        let pci_info = nvml_device
            .pci_info()
            .map_err(|e| GpuError::Generic(format!("Failed to get PCI info: {}", e)))?;

        let uuid = nvml_device
            .uuid()
            .map_err(|e| GpuError::Generic(format!("Failed to get UUID: {}", e)))?;

        let cc = nvml_device
            .cuda_compute_capability()
            .map_err(|e| {
                GpuError::Generic(format!("Failed to get compute capability: {}", e))
            })?;

        // Get driver version (lấy phiên bản driver)
        let driver_version = nvml
            .sys_driver_version()
            .map_err(|e| GpuError::Generic(format!("Failed to get driver version: {}", e)))?;

        // Get CUDA version (lấy phiên bản CUDA) - not available in current API
        let cuda_version = "N/A".to_string(); // API changed

        let info = GpuDeviceInfo {
            device_id,
            name,
            memory_total: memory_info.total,
            compute_capability: (cc.major as u32, cc.minor as u32),
            pci_bus_id: pci_info.bus_id.to_string(), // Already formatted
            uuid,
            driver_version: driver_version.to_string(),
            cuda_version,
        };

        info!("✅ Initialized GPU device: {}", info);

        Ok(Self {
            info,
            nvml_device: Some(nvml_device),
        })
    }

    /// **Create stub device** (tạo thiết bị giả) – without NVML (testing)
    pub fn new_stub(device_id: usize) -> Self {
        warn!("⚠️  Creating stub GPU device {} (NVML disabled)", device_id);

        let info = GpuDeviceInfo {
            device_id,
            name: format!("NVIDIA GPU {} (stub)", device_id),
            memory_total: 10_737_418_240, // 10GB
            compute_capability: (8, 6),
            pci_bus_id: format!("0000:0{}:00.0", device_id + 1),
            uuid: format!("GPU-{:08x}", device_id),
            driver_version: "stub".to_string(),
            cuda_version: "stub".to_string(),
        };

        Self {
            info,
            #[cfg(feature = "nvml")]
            nvml_device: None,
        }
    }

    /// **Get device info** (lấy thông tin thiết bị) – static information
    pub fn info(&self) -> &GpuDeviceInfo {
        &self.info
    }

    /// **Get device ID** (lấy ID thiết bị)
    pub fn device_id(&self) -> usize {
        self.info.device_id
    }

    /// **Query device status** (truy vấn trạng thái thiết bị) – runtime monitoring
    #[cfg(feature = "nvml")]
    pub fn query_status(&self) -> GpuResult<GpuDeviceStatus> {
        let nvml_device = self
            .nvml_device
            .as_ref()
            .ok_or_else(|| GpuError::ContextNotInitialized(self.info.device_id))?;

        // Temperature (nhiệt độ)
        let temperature = nvml_device
            .temperature(nvml_wrapper::enum_wrappers::device::TemperatureSensor::Gpu)
            .map(|t| t as f32)
            .unwrap_or(0.0);

        // Fan speed (tốc độ quạt) – có thể không có
        let fan_speed = nvml_device
            .fan_speed(0)
            .ok()
            .map(|s| s as f32);

        // GPU utilization (sử dụng GPU)
        let utilization = nvml_device
            .utilization_rates()
            .map(|u| u.gpu as f32)
            .unwrap_or(0.0);

        // Memory info (thông tin bộ nhớ)
        let memory_info = nvml_device
            .memory_info()
            .map_err(|e| GpuError::Generic(format!("Failed to get memory info: {}", e)))?;

        let memory_used = memory_info.used;
        let memory_free = memory_info.free;
        let memory_utilization = if memory_info.total > 0 {
            (memory_used as f32 / memory_info.total as f32) * 100.0
        } else {
            0.0
        };

        // Power usage (tiêu thụ điện) – có thể không có
        let power_usage = nvml_device
            .power_usage()
            .ok()
            .map(|p| p as f32 / 1000.0); // mW → W

        // Clock speeds (tốc độ xung) – có thể không có
        let clock_speeds = nvml_device
            .clock_info(nvml_wrapper::enum_wrappers::device::Clock::Graphics)
            .ok()
            .and_then(|graphics| {
                nvml_device
                    .clock_info(nvml_wrapper::enum_wrappers::device::Clock::Memory)
                    .ok()
                    .map(|memory| (graphics, memory))
            });

        Ok(GpuDeviceStatus {
            temperature,
            fan_speed,
            utilization,
            memory_utilization,
            memory_used,
            memory_free,
            power_usage,
            clock_speeds,
        })
    }

    /// **Query status stub** (truy vấn trạng thái giả) – without NVML
    #[cfg(not(feature = "nvml"))]
    pub fn query_status(&self) -> GpuResult<GpuDeviceStatus> {
        Ok(GpuDeviceStatus {
            temperature: 65.0,
            fan_speed: Some(75.0),
            utilization: 85.0,
            memory_utilization: 80.0,
            memory_used: 8_000_000_000,
            memory_free: 2_000_000_000,
            power_usage: Some(250.0),
            clock_speeds: Some((1800, 7000)),
        })
    }

    /// **Set fan speed** (đặt tốc độ quạt) – percentage 0-100
    #[cfg(feature = "nvml")]
    pub fn set_fan_speed(&mut self, speed: u32) -> GpuResult<()> {
        if speed > 100 {
            return Err(GpuError::InvalidDeviceConfig(format!(
                "Fan speed {} exceeds 100%",
                speed
            )));
        }

        let nvml_device = self
            .nvml_device
            .as_ref()
            .ok_or_else(|| GpuError::ContextNotInitialized(self.info.device_id))?;

        // Note: NVML wrapper doesn't have set_fan_speed method in v0.10
        // Fan control is not supported in this version
        Err(GpuError::FanControlNotSupported(self.info.device_id))
    }

    /// **Set fan speed stub** (đặt tốc độ quạt giả) – without NVML
    #[cfg(not(feature = "nvml"))]
    pub fn set_fan_speed(&mut self, speed: u32) -> GpuResult<()> {
        warn!(
            "⚠️  Fan speed control not available (NVML disabled), requested {}%",
            speed
        );
        Ok(())
    }

    /// **Check temperature threshold** (kiểm tra ngưỡng nhiệt độ) – returns error if exceeded
    pub fn check_temperature_threshold(&self, threshold: f32) -> GpuResult<()> {
        let status = self.query_status()?;

        if status.temperature > threshold {
            return Err(GpuError::TemperatureThresholdExceeded {
                device_id: self.info.device_id,
                temp: status.temperature,
                threshold,
            });
        }

        Ok(())
    }

    /// **Validate compute capability** (xác thực compute capability) – check minimum version
    pub fn validate_compute_capability(
        &self,
        required_major: u32,
        required_minor: u32,
    ) -> GpuResult<()> {
        let (major, minor) = self.info.compute_capability;

        if major < required_major || (major == required_major && minor < required_minor) {
            return Err(GpuError::UnsupportedComputeCapability {
                device_id: self.info.device_id,
                major,
                minor,
                required_major,
                required_minor,
            });
        }

        Ok(())
    }
}

impl fmt::Display for GpuDevice {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.info.fmt(f)
    }
}

// Extension trait for GpuError to add context (trait mở rộng GpuError để thêm context)
trait GpuErrorExt {
    fn with_context(self, context: String) -> Self;
}

impl GpuErrorExt for GpuError {
    fn with_context(self, _context: String) -> Self {
        // Simple implementation - could be enhanced with backtrace
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_device_info_display() {
        let info = GpuDeviceInfo {
            device_id: 0,
            name: "NVIDIA GeForce RTX 3080".to_string(),
            memory_total: 10_737_418_240,
            compute_capability: (8, 6),
            pci_bus_id: "00000000".to_string(),
            uuid: "GPU-00000000".to_string(),
            driver_version: "525.0".to_string(),
            cuda_version: "12.0".to_string(),
        };

        let display = info.to_string();
        assert!(display.contains("RTX 3080"));
        assert!(display.contains("10240MB")); // 10GB
    }

    #[cfg(not(feature = "nvml"))]
    #[test]
    fn test_stub_device_creation() {
        let device = GpuDevice::new_stub(0);
        assert_eq!(device.device_id(), 0);
        assert!(device.info().name.contains("stub"));
    }

    #[cfg(not(feature = "nvml"))]
    #[test]
    fn test_stub_status_query() {
        let device = GpuDevice::new_stub(0);
        let status = device.query_status().unwrap();
        assert!(status.temperature > 0.0);
        assert!(status.utilization > 0.0);
    }

    #[test]
    fn test_compute_capability_validation() {
        let info = GpuDeviceInfo {
            device_id: 0,
            name: "Test GPU".to_string(),
            memory_total: 8_000_000_000,
            compute_capability: (8, 6),
            pci_bus_id: "00000000".to_string(),
            uuid: "GPU-test".to_string(),
            driver_version: "test".to_string(),
            cuda_version: "test".to_string(),
        };

        #[cfg(not(feature = "nvml"))]
        let device = GpuDevice { info };

        #[cfg(feature = "nvml")]
        let device = GpuDevice {
            info,
            nvml_device: None,
        };

        // Should pass: 7.5 <= 8.6
        assert!(device.validate_compute_capability(7, 5).is_ok());

        // Should fail: 9.0 > 8.6
        assert!(device.validate_compute_capability(9, 0).is_err());
    }
}
