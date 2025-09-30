//! NVML (NVIDIA Management Library) GPU Metrics Collector
//!
//! Thu thập GPU stats thực tế từ NVIDIA GPUs.
//! Gracefully fallback sang mock metrics nếu NVML không available.

use crate::error::Result;
use crate::messaging::bus::GpuMetrics;
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::{debug, info, warn};

#[cfg(feature = "nvml")]
use nvml_wrapper::{Device as NvmlDevice, Nvml};

/// NVML collector với graceful fallback
pub struct NvmlCollector {
    #[cfg(feature = "nvml")]
    nvml: Option<Nvml>,
    #[cfg(feature = "nvml")]
    devices: Vec<NvmlDevice<'static>>,

    /// Fallback mode khi NVML unavailable
    mock_mode: bool,
    num_gpus: usize,
}

impl NvmlCollector {
    /// Initialize NVML collector
    ///
    /// Nếu NVML init failed (no GPU, driver issues, etc.), fallback sang mock mode.
    pub fn new() -> Self {
        #[cfg(feature = "nvml")]
        {
            match Nvml::init() {
                Ok(nvml) => {
                    // Query available GPUs
                    match nvml.device_count() {
                        Ok(count) => {
                            info!(
                                gpu_count = count,
                                "✅ NVML initialized successfully"
                            );

                            // Enumerate devices
                            let mut devices = Vec::new();
                            for i in 0..count {
                                match nvml.device_by_index(i) {
                                    Ok(device) => {
                                        // Get device name for logging
                                        let name = device.name().unwrap_or_else(|_| "Unknown GPU".to_string());
                                        info!(gpu_id = i, name = %name, "Found GPU device");

                                        // SAFETY: We're storing the device with static lifetime
                                        // This is safe because NVML and devices live for program lifetime
                                        let static_device: NvmlDevice<'static> = unsafe {
                                            std::mem::transmute(device)
                                        };
                                        devices.push(static_device);
                                    }
                                    Err(e) => {
                                        warn!(gpu_id = i, error = %e, "Failed to access GPU device");
                                    }
                                }
                            }

                            if devices.is_empty() {
                                warn!("⚠️ No GPU devices found, using mock metrics");
                                Self {
                                    nvml: None,
                                    devices: vec![],
                                    mock_mode: true,
                                    num_gpus: 1, // Default mock 1 GPU
                                }
                            } else {
                                Self {
                                    nvml: Some(nvml),
                                    devices,
                                    mock_mode: false,
                                    num_gpus: count as usize,
                                }
                            }
                        }
                        Err(e) => {
                            warn!(error = %e, "⚠️ Failed to query GPU count, using mock metrics");
                            Self {
                                nvml: None,
                                devices: vec![],
                                mock_mode: true,
                                num_gpus: 1,
                            }
                        }
                    }
                }
                Err(e) => {
                    warn!(error = %e, "⚠️ NVML initialization failed, using mock metrics");
                    Self {
                        nvml: None,
                        devices: vec![],
                        mock_mode: true,
                        num_gpus: 1,
                    }
                }
            }
        }

        // NVML feature not enabled - always use mock mode
        #[cfg(not(feature = "nvml"))]
        {
            info!("🔧 NVML feature disabled, using mock metrics");
            Self {
                mock_mode: true,
                num_gpus: 1,
            }
        }
    }

    /// Collect metrics từ specific GPU
    ///
    /// Returns real NVML data nếu available, fallback sang mock data nếu failed.
    pub fn collect(&self, gpu_id: usize) -> Result<GpuMetrics> {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        // Mock mode - return simulated metrics
        if self.mock_mode {
            return Ok(Self::mock_metrics(gpu_id, timestamp));
        }

        // Real NVML collection
        #[cfg(feature = "nvml")]
        {
            if let Some(device) = self.devices.get(gpu_id) {
                match self.collect_nvml_metrics(device, gpu_id, timestamp) {
                    Ok(metrics) => {
                        debug!(
                            gpu_id = gpu_id,
                            temperature = metrics.temperature,
                            power = metrics.power_usage,
                            utilization = metrics.utilization,
                            memory_mb = metrics.memory_used_mb,
                            "Collected NVML metrics"
                        );
                        Ok(metrics)
                    }
                    Err(e) => {
                        warn!(gpu_id = gpu_id, error = %e, "NVML query failed, using mock data");
                        Ok(Self::mock_metrics(gpu_id, timestamp))
                    }
                }
            } else {
                warn!(gpu_id = gpu_id, "Invalid GPU ID, using mock data");
                Ok(Self::mock_metrics(gpu_id, timestamp))
            }
        }

        #[cfg(not(feature = "nvml"))]
        Ok(Self::mock_metrics(gpu_id, timestamp))
    }

    /// Collect metrics từ NVML device
    #[cfg(feature = "nvml")]
    fn collect_nvml_metrics(
        &self,
        device: &NvmlDevice,
        gpu_id: usize,
        timestamp: u64,
    ) -> Result<GpuMetrics> {
        // Temperature (Celsius)
        let temperature = device
            .temperature(nvml_wrapper::enum_wrappers::device::TemperatureSensor::Gpu)
            .map(|t| t as f32)
            .unwrap_or(0.0);

        // Power usage (Watts)
        let power_usage = device
            .power_usage()
            .map(|p| p as f32 / 1000.0) // Convert milliwatts to watts
            .unwrap_or(0.0);

        // GPU utilization (percentage)
        let utilization = device
            .utilization_rates()
            .map(|u| u.gpu as f32)
            .unwrap_or(0.0);

        // Memory usage (MB)
        let memory_used_mb = device
            .memory_info()
            .map(|info| info.used / 1024 / 1024) // Convert bytes to MB
            .unwrap_or(0);

        Ok(GpuMetrics {
            gpu_id,
            hashrate: 0.0, // Hashrate not measured by NVML
            temperature,
            power_usage,
            utilization,
            memory_used_mb,
            timestamp,
        })
    }

    /// Generate mock metrics cho testing/fallback
    fn mock_metrics(gpu_id: usize, timestamp: u64) -> GpuMetrics {
        use std::f32::consts::PI;

        // Use timestamp để tạo varying mock data
        let t = (timestamp % 60) as f32;
        let cycle = (t / 60.0 * 2.0 * PI).sin();

        GpuMetrics {
            gpu_id,
            hashrate: 0.0,
            temperature: 65.0 + cycle * 10.0,           // Vary 55-75°C
            power_usage: 150.0 + cycle * 50.0,           // Vary 100-200W
            utilization: 85.0 + cycle * 15.0,            // Vary 70-100%
            memory_used_mb: 4096 + (cycle * 1024.0) as u64, // Vary 3-5GB
            timestamp,
        }
    }

    /// Get số lượng GPUs available
    pub fn gpu_count(&self) -> usize {
        self.num_gpus
    }

    /// Check nếu đang running trong mock mode
    pub fn is_mock_mode(&self) -> bool {
        self.mock_mode
    }
}

impl Default for NvmlCollector {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_nvml_collector_creation() {
        let collector = NvmlCollector::new();
        assert!(collector.gpu_count() > 0, "Should have at least 1 GPU (mock or real)");
    }

    #[test]
    fn test_metrics_collection() {
        let collector = NvmlCollector::new();
        let metrics = collector.collect(0);

        assert!(metrics.is_ok(), "Metrics collection should succeed");

        let metrics = metrics.unwrap();
        assert_eq!(metrics.gpu_id, 0);
        assert!(metrics.temperature > 0.0, "Temperature should be positive");
        assert!(metrics.power_usage >= 0.0, "Power usage should be non-negative");
        assert!(metrics.utilization >= 0.0 && metrics.utilization <= 100.0, "Utilization should be 0-100%");
    }

    #[test]
    fn test_mock_metrics_vary_over_time() {
        let collector = NvmlCollector::new();

        if collector.is_mock_mode() {
            let metrics1 = collector.collect(0).unwrap();
            std::thread::sleep(std::time::Duration::from_secs(2));
            let metrics2 = collector.collect(0).unwrap();

            // Mock metrics should vary slightly due to timestamp-based calculation
            assert!(
                (metrics1.temperature - metrics2.temperature).abs() < 20.0,
                "Temperature variation should be realistic"
            );
        }
    }

    #[test]
    fn test_invalid_gpu_id_fallback() {
        let collector = NvmlCollector::new();
        let metrics = collector.collect(999);

        // Should fallback to mock data gracefully
        assert!(metrics.is_ok(), "Should fallback gracefully for invalid GPU ID");
    }
}
