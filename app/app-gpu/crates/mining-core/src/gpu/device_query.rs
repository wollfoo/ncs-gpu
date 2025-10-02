//! # Device Query (Truy Vấn Thiết Bị)
//!
//! Query GPU device information (temperature, utilization, etc.).

use anyhow::Result;
use tracing::warn;

/// GPU temperature (°C)
pub fn get_temperature(device_id: usize) -> Result<f32> {
    // TODO: Query via nvidia-ml-sys
    warn!("⚠️  GPU temperature query not implemented for device {}", device_id);
    Ok(65.0) // Stub
}

/// GPU utilization (%)
pub fn get_utilization(device_id: usize) -> Result<f32> {
    // TODO: Query via nvidia-ml-sys
    warn!("⚠️  GPU utilization query not implemented for device {}", device_id);
    Ok(85.0) // Stub
}

/// GPU memory usage (bytes used, total bytes)
pub fn get_memory_usage(device_id: usize) -> Result<(u64, u64)> {
    // TODO: Query via nvidia-ml-sys
    warn!("⚠️  GPU memory query not implemented for device {}", device_id);
    Ok((8_000_000_000, 10_000_000_000)) // Stub: 8GB used / 10GB total
}

/// GPU fan speed (%)
pub fn get_fan_speed(device_id: usize) -> Result<f32> {
    // TODO: Query via nvidia-ml-sys
    warn!("⚠️  GPU fan speed query not implemented for device {}", device_id);
    Ok(75.0) // Stub
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_temperature_query() {
        let temp = get_temperature(0).unwrap();
        assert!(temp > 0.0);
        assert!(temp < 120.0); // Reasonable range
    }

    #[test]
    fn test_utilization_query() {
        let util = get_utilization(0).unwrap();
        assert!(util >= 0.0);
        assert!(util <= 100.0);
    }
}
