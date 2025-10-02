//! # Thermal Monitoring System (Hệ thống giám sát nhiệt)
//!
//! **Thermal management** (quản lý nhiệt độ) với monitoring, alert thresholds, fan control.

use super::device::{GpuDevice, GpuDeviceStatus};
use super::error::{GpuError, GpuResult};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{debug, info, warn};

/// **ThermalThresholds** (ngưỡng nhiệt) – temperature limits and actions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalThresholds {
    /// **Warning temperature** (nhiệt độ cảnh báo) – °C
    pub warning_celsius: f32,

    /// **Critical temperature** (nhiệt độ nguy hiểm) – °C
    pub critical_celsius: f32,

    /// **Max fan speed** (tốc độ quạt tối đa) – percentage 0-100
    pub max_fan_speed: u32,
}

impl Default for ThermalThresholds {
    fn default() -> Self {
        Self {
            warning_celsius: 75.0,     // Warning at 75°C
            critical_celsius: 85.0,     // Critical at 85°C
            max_fan_speed: 80,          // Max 80% fan speed
        }
    }
}

/// **ThermalEvent** (sự kiện nhiệt) – thermal occurrence
#[derive(Debug, Clone)]
pub enum ThermalEvent {
    /// **Normal** (bình thường) – temperature OK
    Normal {
        device_id: usize,
        temperature: f32,
    },

    /// **Warning** (cảnh báo) – temperature high
    Warning {
        device_id: usize,
        temperature: f32,
        threshold: f32,
    },

    /// **Critical** (nguy hiểm) – temperature too high
    Critical {
        device_id: usize,
        temperature: f32,
        threshold: f32,
    },
}

impl std::fmt::Display for ThermalEvent {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ThermalEvent::Normal { device_id, temperature } =>
                write!(f, "GPU {} thermal normal: {:.1}°C", device_id, temperature),
            ThermalEvent::Warning { device_id, temperature, threshold } =>
                write!(f, "GPU {} thermal warning: {:.1}°C (threshold: {:.1}°C)", device_id, temperature, threshold),
            ThermalEvent::Critical { device_id, temperature, threshold } =>
                write!(f, "GPU {} thermal critical: {:.1}°C (threshold: {:.1}°C)", device_id, temperature, threshold),
        }
    }
}

/// **ThermalMonitor** (trình giám sát nhiệt) – monitors device temperatures
pub struct ThermalMonitor {
    /// **Thresholds** (ngưỡng)
    thresholds: ThermalThresholds,

    /// **Previous states** (trạng thái trước) – device_id → temperature
    previous_temps: HashMap<usize, f32>,

    /// **Event callback** (callback sự kiện)
    event_callback: Option<Box<dyn Fn(ThermalEvent) + Send + Sync>>,

    /// **Devices** (thiết bị) – reference to GPU devices
    devices: HashMap<usize, Arc<Mutex<GpuDevice>>>,
}

impl ThermalMonitor {
    /// **Create new monitor** (tạo trình giám sát mới)
    pub fn new() -> Self {
        Self {
            thresholds: ThermalThresholds::default(),
            previous_temps: HashMap::new(),
            event_callback: None,
            devices: HashMap::new(),
        }
    }

    /// **With thresholds** (với ngưỡng tùy chỉnh)
    pub fn with_thresholds(mut self, thresholds: ThermalThresholds) -> Self {
        self.thresholds = thresholds;
        self
    }

    /// **Set event callback** (đặt callback sự kiện)
    pub fn with_event_callback<F>(mut self, callback: F) -> Self
    where
        F: Fn(ThermalEvent) + Send + Sync + 'static,
    {
        self.event_callback = Some(Box::new(callback));
        self
    }

    /// **Add device** (thêm thiết bị)
    pub fn add_device(&mut self, device: Arc<Mutex<GpuDevice>>) -> GpuResult<()> {
        let device_lock = device.lock();
        let device_id = device_lock.device_id();
        self.devices.insert(device_id, device);
        Ok(())
    }

    /// **Remove device** (xóa thiết bị)
    pub fn remove_device(&mut self, device_id: usize) {
        self.devices.remove(&device_id);
        self.previous_temps.remove(&device_id);
    }

    /// **Monitor once** (giám sát một lần) – poll all devices
    pub fn monitor_once(&mut self) -> GpuResult<()> {
        let device_ids: Vec<usize> = self.devices.keys().copied().collect();

        for device_id in device_ids {
            if let Some(device) = self.devices.get(&device_id) {
                let device_clone = Arc::clone(device);
                // Spawn on tokio runtime but keep overall function sync
                let result = tokio::spawn(async move {
                    let gpu_device = device_clone.lock();
                    gpu_device.query_status()
                });

                // This is a simplified version - in practice you'd want to handle this better
                match futures::executor::block_on(result) {
                    Ok(Ok(status)) => {
                        // Note: process_device_status was async but doesn't need to be
                        let prev_temp = self.previous_temps.get(&device_id).copied().unwrap_or(0.0);
                        let event = self.determine_thermal_event(device_id, status.temperature, prev_temp);
                        self.previous_temps.insert(device_id, status.temperature);

                        if let Some(callback) = &self.event_callback {
                            callback(event.clone());
                        }
                    }
                    Ok(Err(e)) => {
                        warn!("⚠️  Failed to query device {} status: {}", device_id, e);
                    }
                    Err(e) => {
                        warn!("⚠️  Task panicked for device {}: {}", device_id, e);
                    }
                }
            }
        }

        Ok(())
    }

    /// **Process device status** (xử lý trạng thái thiết bị)
    fn determine_thermal_event(&self, device_id: usize, temperature: f32, previous_temp: f32) -> ThermalEvent {
        let temperature = status.temperature;
        let previous_temp = self.previous_temps.get(&device_id).copied().unwrap_or(0.0);

        debug!("GPU {} temperature: {:.1}°C (previous: {:.1}°C)",
               device_id, temperature, previous_temp);

        // Determine current thermal state (xác định trạng thái nhiệt hiện tại)
        let event = self.determine_thermal_event(device_id, status.temperature, prev_temp);

        // Store current temperature (lưu nhiệt độ hiện tại)
        self.previous_temps.insert(device_id, status.temperature);

        // Trigger callback if needed (kích hoạt callback nếu cần)
        if let Some(callback) = &self.event_callback {
            callback(event);
        }

        Ok(())
    }

    /// **Determine thermal event** (xác định sự kiện nhiệt)
    fn determine_thermal_event(&self, device_id: usize, temperature: f32, previous_temp: f32) -> ThermalEvent {
        let warn_threshold = self.thresholds.warning_celsius;
        let crit_threshold = self.thresholds.critical_celsius;

        if temperature >= crit_threshold {
            ThermalEvent::Critical {
                device_id,
                temperature,
                threshold: crit_threshold,
            }
        } else if temperature >= warn_threshold {
            // Only report warning if it wasn't already in warning state
