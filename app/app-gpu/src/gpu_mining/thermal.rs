//! Thermal management and monitoring for GPU mining
//!
//! Advanced thermal protection system with predictive throttling,
//! adaptive cooling strategies, and hardware safety mechanisms.

use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant};
use tokio::sync::mpsc;

use crate::common::error::{OpusError, OpusResult};
use crate::common::metrics::OpusMetrics;
use crate::common::{constants, config::ThermalAction};

/// Thermal monitoring and management system
pub struct ThermalManager {
    /// Device thermal states
    device_states: Arc<RwLock<HashMap<u32, ThermalState>>>,
    /// Thermal configuration
    config: ThermalConfig,
    /// Metrics collector
    metrics: Option<Arc<OpusMetrics>>,
    /// Event channel for thermal alerts
    alert_sender: mpsc::Sender<ThermalAlert>,
    /// Monitoring task handle
    monitor_handle: Option<tokio::task::JoinHandle<()>>,
}

/// Thermal state for a specific GPU device
#[derive(Debug, Clone)]
pub struct ThermalState {
    /// Device ID
    pub device_id: u32,
    /// Current temperature (°C)
    pub current_temp: f32,
    /// Temperature history for trend analysis
    pub temp_history: Vec<TemperatureReading>,
    /// Current throttle level (0.0 = none, 1.0 = maximum)
    pub throttle_level: f32,
    /// Thermal status
    pub status: ThermalStatus,
    /// Last update timestamp
    pub last_update: Instant,
    /// Thermal trend (°C/minute)
    pub trend: f32,
    /// Power usage (watts)
    pub power_usage: f32,
    /// Fan speed (0-100%)
    pub fan_speed: f32,
}

/// Temperature reading with timestamp
#[derive(Debug, Clone)]
pub struct TemperatureReading {
    pub temperature: f32,
    pub timestamp: Instant,
    pub power_usage: f32,
    pub fan_speed: f32,
}

/// Thermal status levels
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ThermalStatus {
    /// Normal operating temperature
    Normal,
    /// Approaching warning threshold
    Warm,
    /// Warning threshold exceeded
    Warning,
    /// Critical threshold exceeded
    Critical,
    /// Emergency shutdown required
    Emergency,
}

/// Thermal alert event
#[derive(Debug, Clone)]
pub struct ThermalAlert {
    pub device_id: u32,
    pub alert_type: ThermalAlertType,
    pub temperature: f32,
    pub threshold: f32,
    pub timestamp: Instant,
}

/// Types of thermal alerts
#[derive(Debug, Clone)]
pub enum ThermalAlertType {
    /// Temperature rising rapidly
    RapidRise,
    /// Warning threshold exceeded
    WarningThreshold,
    /// Critical threshold exceeded
    CriticalThreshold,
    /// Emergency shutdown triggered
    EmergencyShutdown,
    /// Throttling activated
    ThrottleActivated,
    /// Throttling deactivated
    ThrottleDeactivated,
}

/// Thermal management configuration
#[derive(Debug, Clone)]
pub struct ThermalConfig {
    /// Warning temperature threshold (°C)
    pub warning_temp: f32,
    /// Critical temperature threshold (°C)
    pub critical_temp: f32,
    /// Emergency shutdown temperature (°C)
    pub emergency_temp: f32,
    /// Temperature monitoring interval
    pub monitor_interval: Duration,
    /// Temperature history window
    pub history_window: Duration,
    /// Throttling sensitivity (how aggressively to throttle)
    pub throttle_sensitivity: f32,
    /// Action to take at critical temperature
    pub critical_action: ThermalAction,
    /// Enable predictive throttling
    pub predictive_throttling: bool,
    /// Thermal trend warning threshold (°C/minute)
    pub trend_warning_threshold: f32,
}

impl Default for ThermalConfig {
    fn default() -> Self {
        Self {
            warning_temp: constants::THERMAL_WARNING_THRESHOLD,
            critical_temp: constants::THERMAL_CRITICAL_THRESHOLD,
            emergency_temp: 95.0,
            monitor_interval: Duration::from_secs(5),
            history_window: Duration::from_secs(300), // 5 minutes
            throttle_sensitivity: 0.8,
            critical_action: ThermalAction::ReduceIntensity,
            predictive_throttling: true,
            trend_warning_threshold: 2.0, // 2°C/minute
        }
    }
}

impl ThermalManager {
    /// Create new thermal manager
    pub fn new(
        config: ThermalConfig,
        metrics: Option<Arc<OpusMetrics>>,
    ) -> OpusResult<(Self, mpsc::Receiver<ThermalAlert>)> {
        let (alert_sender, alert_receiver) = mpsc::channel(100);

        let manager = Self {
            device_states: Arc::new(RwLock::new(HashMap::new())),
            config,
            metrics,
            alert_sender,
            monitor_handle: None,
        };

        Ok((manager, alert_receiver))
    }

    /// Add device for thermal monitoring
    pub fn add_device(&self, device_id: u32) -> OpusResult<()> {
        let mut states = self.device_states.write().map_err(|_| {
            OpusError::System {
                message: "Failed to acquire write lock for device states".to_string(),
            }
        })?;

        let state = ThermalState {
            device_id,
            current_temp: 25.0, // Room temperature start
            temp_history: Vec::new(),
            throttle_level: 0.0,
            status: ThermalStatus::Normal,
            last_update: Instant::now(),
            trend: 0.0,
            power_usage: 0.0,
            fan_speed: 0.0,
        };

        states.insert(device_id, state);
        Ok(())
    }

    /// Start thermal monitoring
    pub async fn start_monitoring(&mut self) -> OpusResult<()> {
        let device_states = self.device_states.clone();
        let config = self.config.clone();
        let metrics = self.metrics.clone();
        let alert_sender = self.alert_sender.clone();

        let handle = tokio::spawn(async move {
            let mut interval = tokio::time::interval(config.monitor_interval);

            loop {
                interval.tick().await;

                if let Err(e) = Self::monitoring_iteration(
                    &device_states,
                    &config,
                    &metrics,
                    &alert_sender,
                ).await {
                    tracing::error!("Thermal monitoring error: {}", e);
                }
            }
        });

        self.monitor_handle = Some(handle);
        Ok(())
    }

    /// Stop thermal monitoring
    pub fn stop_monitoring(&mut self) {
        if let Some(handle) = self.monitor_handle.take() {
            handle.abort();
        }
    }

    /// Update temperature reading for device
    pub fn update_temperature(&self, device_id: u32, temp: f32, power: f32, fan_speed: f32) -> OpusResult<()> {
        let mut states = self.device_states.write().map_err(|_| {
            OpusError::System {
                message: "Failed to acquire write lock for device states".to_string(),
            }
        })?;

        let state = states.get_mut(&device_id).ok_or_else(|| {
            OpusError::gpu_error(format!("Device {} not registered for thermal monitoring", device_id), Some(device_id))
        })?;

        let now = Instant::now();
        let reading = TemperatureReading {
            temperature: temp,
            timestamp: now,
            power_usage: power,
            fan_speed,
        };

        // Update current state
        state.current_temp = temp;
        state.power_usage = power;
        state.fan_speed = fan_speed;
        state.last_update = now;

        // Add to history
        state.temp_history.push(reading);

        // Trim history to window
        let cutoff_time = now - self.config.history_window;
        state.temp_history.retain(|r| r.timestamp > cutoff_time);

        // Calculate temperature trend
        state.trend = self.calculate_temperature_trend(&state.temp_history);

        // Update thermal status
        let old_status = state.status.clone();
        state.status = self.determine_thermal_status(temp, state.trend);

        // Update throttle level if needed
        if state.status != ThermalStatus::Normal {
            state.throttle_level = self.calculate_throttle_level(temp, state.trend);
        } else {
            state.throttle_level = 0.0;
        }

        // Send alerts if status changed
        if state.status != old_status {
            self.send_status_change_alert(device_id, &state.status, temp)?;
        }

        // Record metrics
        if let Some(metrics) = &self.metrics {
            metrics.gpu_temperature
                .with_label_values(&[&device_id.to_string(), "unknown"])
                .set(temp as f64);
        }

        Ok(())
    }

    /// Get current thermal state for device
    pub fn get_thermal_state(&self, device_id: u32) -> OpusResult<ThermalState> {
        let states = self.device_states.read().map_err(|_| {
            OpusError::System {
                message: "Failed to acquire read lock for device states".to_string(),
            }
        })?;

        states.get(&device_id)
            .cloned()
            .ok_or_else(|| {
                OpusError::gpu_error(format!("Device {} not registered", device_id), Some(device_id))
            })
    }

    /// Get throttle level for device (0.0 = no throttle, 1.0 = full throttle)
    pub fn get_throttle_level(&self, device_id: u32) -> OpusResult<f32> {
        let state = self.get_thermal_state(device_id)?;
        Ok(state.throttle_level)
    }

    /// Check if device should be shut down due to thermal issues
    pub fn should_shutdown(&self, device_id: u32) -> OpusResult<bool> {
        let state = self.get_thermal_state(device_id)?;
        Ok(matches!(state.status, ThermalStatus::Emergency))
    }

    /// Monitoring iteration
    async fn monitoring_iteration(
        device_states: &Arc<RwLock<HashMap<u32, ThermalState>>>,
        config: &ThermalConfig,
        metrics: &Option<Arc<OpusMetrics>>,
        alert_sender: &mpsc::Sender<ThermalAlert>,
    ) -> OpusResult<()> {
        let states = device_states.read().map_err(|_| {
            OpusError::System {
                message: "Failed to acquire read lock for monitoring".to_string(),
            }
        })?;

        for (device_id, state) in states.iter() {
            // Check for rapid temperature rise
            if config.predictive_throttling && state.trend > config.trend_warning_threshold {
                let alert = ThermalAlert {
                    device_id: *device_id,
                    alert_type: ThermalAlertType::RapidRise,
                    temperature: state.current_temp,
                    threshold: config.trend_warning_threshold,
                    timestamp: Instant::now(),
                };

                let _ = alert_sender.send(alert).await;
            }

            // Update metrics
            if let Some(metrics) = metrics {
                let device_id_str = device_id.to_string();
                metrics.gpu_temperature
                    .with_label_values(&[&device_id_str, "unknown"])
                    .set(state.current_temp as f64);

                metrics.gpu_power_usage
                    .with_label_values(&[&device_id_str, "unknown"])
                    .set(state.power_usage as f64);
            }
        }

        Ok(())
    }

    /// Calculate temperature trend in °C/minute
    fn calculate_temperature_trend(&self, history: &[TemperatureReading]) -> f32 {
        if history.len() < 2 {
            return 0.0;
        }

        // Use linear regression for trend calculation
        let n = history.len() as f32;
        let mut sum_x = 0.0;
        let mut sum_y = 0.0;
        let mut sum_xy = 0.0;
        let mut sum_x2 = 0.0;

        let start_time = history[0].timestamp;

        for (i, reading) in history.iter().enumerate() {
            let x = reading.timestamp.duration_since(start_time).as_secs_f32() / 60.0; // minutes
            let y = reading.temperature;

            sum_x += x;
            sum_y += y;
            sum_xy += x * y;
            sum_x2 += x * x;
        }

        // Calculate slope (trend in °C/minute)
        let slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x);
        slope
    }

    /// Determine thermal status based on temperature and trend
    fn determine_thermal_status(&self, temp: f32, trend: f32) -> ThermalStatus {
        if temp >= self.config.emergency_temp {
            ThermalStatus::Emergency
        } else if temp >= self.config.critical_temp {
            ThermalStatus::Critical
        } else if temp >= self.config.warning_temp {
            ThermalStatus::Warning
        } else if temp >= self.config.warning_temp - 5.0 || trend > 1.0 {
            ThermalStatus::Warm
        } else {
            ThermalStatus::Normal
        }
    }

    /// Calculate throttle level based on temperature and trend
    fn calculate_throttle_level(&self, temp: f32, trend: f32) -> f32 {
        let temp_factor = if temp > self.config.warning_temp {
            (temp - self.config.warning_temp) / (self.config.critical_temp - self.config.warning_temp)
        } else {
            0.0
        };

        let trend_factor = if trend > 0.5 {
            (trend - 0.5) / 2.0 // Normalize trend contribution
        } else {
            0.0
        };

        let throttle = (temp_factor + trend_factor * 0.3) * self.config.throttle_sensitivity;
        throttle.clamp(0.0, 1.0)
    }

    /// Send thermal status change alert
    fn send_status_change_alert(
        &self,
        device_id: u32,
        status: &ThermalStatus,
        temperature: f32,
    ) -> OpusResult<()> {
        let (alert_type, threshold) = match status {
            ThermalStatus::Warning => (ThermalAlertType::WarningThreshold, self.config.warning_temp),
            ThermalStatus::Critical => (ThermalAlertType::CriticalThreshold, self.config.critical_temp),
            ThermalStatus::Emergency => (ThermalAlertType::EmergencyShutdown, self.config.emergency_temp),
            _ => return Ok(()), // No alert for normal/warm states
        };

        let alert = ThermalAlert {
            device_id,
            alert_type,
            temperature,
            threshold,
            timestamp: Instant::now(),
        };

        // Try to send alert (non-blocking)
        if let Err(_) = self.alert_sender.try_send(alert) {
            tracing::warn!("Failed to send thermal alert for device {}", device_id);
        }

        Ok(())
    }
}

/// Thermal protection wrapper for mining operations
pub struct ThermalProtectedMiner {
    thermal_manager: Arc<ThermalManager>,
    base_intensity: f32,
}

impl ThermalProtectedMiner {
    /// Create new thermal-protected miner
    pub fn new(thermal_manager: Arc<ThermalManager>, base_intensity: f32) -> Self {
        Self {
            thermal_manager,
            base_intensity,
        }
    }

    /// Get adjusted mining intensity based on thermal state
    pub fn get_adjusted_intensity(&self, device_id: u32) -> OpusResult<f32> {
        let throttle_level = self.thermal_manager.get_throttle_level(device_id)?;
        let adjusted = self.base_intensity * (1.0 - throttle_level);
        Ok(adjusted.max(0.1)) // Minimum 10% intensity
    }

    /// Check if mining should be paused due to thermal issues
    pub fn should_pause_mining(&self, device_id: u32) -> OpusResult<bool> {
        let state = self.thermal_manager.get_thermal_state(device_id)?;
        Ok(matches!(state.status, ThermalStatus::Critical | ThermalStatus::Emergency))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_thermal_config_default() {
        let config = ThermalConfig::default();
        assert!(config.warning_temp < config.critical_temp);
        assert!(config.critical_temp < config.emergency_temp);
        assert!(config.throttle_sensitivity > 0.0);
    }

    #[test]
    fn test_thermal_state_creation() {
        let state = ThermalState {
            device_id: 0,
            current_temp: 65.0,
            temp_history: Vec::new(),
            throttle_level: 0.0,
            status: ThermalStatus::Normal,
            last_update: Instant::now(),
            trend: 0.0,
            power_usage: 150.0,
            fan_speed: 50.0,
        };

        assert_eq!(state.device_id, 0);
        assert_eq!(state.current_temp, 65.0);
        assert_eq!(state.status, ThermalStatus::Normal);
    }

    #[tokio::test]
    async fn test_thermal_manager_creation() {
        let config = ThermalConfig::default();
        let (manager, _receiver) = ThermalManager::new(config, None).unwrap();

        manager.add_device(0).unwrap();
        manager.update_temperature(0, 70.0, 160.0, 60.0).unwrap();

        let state = manager.get_thermal_state(0).unwrap();
        assert_eq!(state.current_temp, 70.0);
        assert_eq!(state.power_usage, 160.0);
    }

    #[test]
    fn test_thermal_status_determination() {
        let config = ThermalConfig::default();
        let (manager, _) = ThermalManager::new(config, None).unwrap();

        // Test normal temperature
        let status = manager.determine_thermal_status(60.0, 0.0);
        assert_eq!(status, ThermalStatus::Normal);

        // Test warning temperature
        let status = manager.determine_thermal_status(80.0, 0.0);
        assert_eq!(status, ThermalStatus::Warning);

        // Test critical temperature
        let status = manager.determine_thermal_status(90.0, 0.0);
        assert_eq!(status, ThermalStatus::Critical);
    }

    #[test]
    fn test_temperature_trend_calculation() {
        let config = ThermalConfig::default();
        let (manager, _) = ThermalManager::new(config, None).unwrap();

        let now = Instant::now();
        let history = vec![
            TemperatureReading {
                temperature: 60.0,
                timestamp: now,
                power_usage: 150.0,
                fan_speed: 50.0,
            },
            TemperatureReading {
                temperature: 65.0,
                timestamp: now + Duration::from_secs(60),
                power_usage: 160.0,
                fan_speed: 60.0,
            },
            TemperatureReading {
                temperature: 70.0,
                timestamp: now + Duration::from_secs(120),
                power_usage: 170.0,
                fan_speed: 70.0,
            },
        ];

        let trend = manager.calculate_temperature_trend(&history);
        assert!(trend > 0.0); // Should be positive (temperature rising)
    }

    #[test]
    fn test_thermal_protected_miner() {
        let config = ThermalConfig::default();
        let (thermal_manager, _) = ThermalManager::new(config, None).unwrap();
        let thermal_manager = Arc::new(thermal_manager);

        thermal_manager.add_device(0).unwrap();

        let miner = ThermalProtectedMiner::new(thermal_manager.clone(), 1.0);

        // Test with normal temperature
        thermal_manager.update_temperature(0, 60.0, 150.0, 50.0).unwrap();
        let intensity = miner.get_adjusted_intensity(0).unwrap();
        assert!((intensity - 1.0).abs() < 0.1); // Should be close to base intensity

        // Test with high temperature (should throttle)
        thermal_manager.update_temperature(0, 85.0, 200.0, 80.0).unwrap();
        let intensity = miner.get_adjusted_intensity(0).unwrap();
        assert!(intensity < 1.0); // Should be throttled
    }
}