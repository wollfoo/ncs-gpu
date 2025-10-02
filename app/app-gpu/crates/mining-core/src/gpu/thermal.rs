//! # Thermal Monitoring System (Hệ thống giám sát nhiệt)
//!
//! **Thermal management** (quản lý nhiệt độ) với monitoring, alert thresholds, fan control.

use super::device::GpuDevice;
use super::error::{GpuError, GpuResult};
use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
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
        // Get device ID first
        let device_id = device.lock().device_id();
        // Then move device into map
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
                // Simplified synchronous version
                let device_status = {
                    let lock = device_clone.lock();
                    lock.query_status()
                };

                match device_status {
                    Ok(status) => {
                        let prev_temp = self.previous_temps.get(&device_id).copied().unwrap_or(0.0);
                        let temperature = status.temperature;

                        debug!("GPU {} temperature: {:.1}°C (previous: {:.1}°C)",
                               device_id, temperature, prev_temp);

                        let event = self.determine_thermal_event(device_id, temperature, prev_temp);
                        self.previous_temps.insert(device_id, temperature);

                        if let Some(callback) = &self.event_callback {
                            callback(event);
                        }
                    }
                    Err(e) => {
                        warn!("⚠️  Failed to query device {} status: {}", device_id, e);
                    }
                }
            }
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
            // (chỉ báo cảnh báo nếu chưa ở trạng thái cảnh báo)
            if previous_temp < warn_threshold {
                ThermalEvent::Warning {
                    device_id,
                    temperature,
                    threshold: warn_threshold,
                }
            } else {
                ThermalEvent::Normal { device_id, temperature }
            }
        } else {
            ThermalEvent::Normal { device_id, temperature }
        }
    }

    /// **Get thresholds** (lấy ngưỡng)
    pub fn thresholds(&self) -> &ThermalThresholds {
        &self.thresholds
    }

    /// **Set thresholds** (đặt ngưỡng)
    pub fn set_thresholds(&mut self, thresholds: ThermalThresholds) {
        self.thresholds = thresholds;
    }

    /// **Get device temperatures** (lấy nhiệt độ thiết bị)
    pub fn get_device_temperatures(&self) -> HashMap<usize, f32> {
        self.previous_temps.clone()
    }
}

impl Default for ThermalMonitor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_thermal_thresholds_default() {
        let thresholds = ThermalThresholds::default();
        assert_eq!(thresholds.warning_celsius, 75.0);
        assert_eq!(thresholds.critical_celsius, 85.0);
        assert_eq!(thresholds.max_fan_speed, 80);
    }

    #[test]
    fn test_thermal_event_display() {
        let event = ThermalEvent::Warning {
            device_id: 1,
            temperature: 78.5,
            threshold: 75.0,
        };

        let display = event.to_string();
        assert!(display.contains("GPU 1"));
        assert!(display.contains("78.5"));
        assert!(display.contains("warning"));
    }

    #[test]
    fn test_monitor_creation() {
        let monitor = ThermalMonitor::new();
        assert_eq!(monitor.thresholds().warning_celsius, 75.0);
    }

    #[test]
    fn test_thermal_event_determination() {
        let monitor = ThermalMonitor::new();

        // Test normal temperature
        let event = monitor.determine_thermal_event(0, 65.0, 70.0);
        match event {
            ThermalEvent::Normal { device_id, temperature } => {
                assert_eq!(device_id, 0);
                assert_eq!(temperature, 65.0);
            }
            _ => panic!("Expected normal event"),
        }

        // Test warning temperature
        let event = monitor.determine_thermal_event(0, 78.0, 70.0);
        match event {
            ThermalEvent::Warning { device_id, temperature, threshold } => {
                assert_eq!(device_id, 0);
                assert_eq!(temperature, 78.0);
                assert_eq!(threshold, 75.0);
            }
            _ => panic!("Expected warning event"),
        }

        // Test critical temperature
        let event = monitor.determine_thermal_event(0, 90.0, 80.0);
        match event {
            ThermalEvent::Critical { device_id, temperature, threshold } => {
                assert_eq!(device_id, 0);
                assert_eq!(temperature, 90.0);
                assert_eq!(threshold, 85.0);
            }
            _ => panic!("Expected critical event"),
        }
    }
}