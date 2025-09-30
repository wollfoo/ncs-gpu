//! Prometheus metrics collection
//!
//! Collects and exposes metrics in Prometheus format:
//! - GPU utilization and temperature
//! - Mining hashrate and shares
//! - System resource usage
//! - Error rates and uptime

use crate::error::{MinerError, Result};
use crate::messaging::{Message, MessageBus, MessageBusHandles};
use prometheus::{
    register_gauge, register_int_counter, register_int_gauge, Gauge, IntCounter,
    IntGauge, TextEncoder,
};
use serde::Deserialize;
use std::sync::Arc;
use tokio::select;
use tokio_util::sync::CancellationToken;
use tracing::{debug, info, warn};

/// Metrics collection configuration
#[derive(Debug, Clone, Deserialize)]
pub struct MetricsConfig {
    /// Collection interval in seconds
    pub interval_secs: u64,
    /// Enable GPU metrics
    pub enable_gpu_metrics: bool,
    /// Enable system metrics
    pub enable_system_metrics: bool,
}

impl Default for MetricsConfig {
    fn default() -> Self {
        Self {
            interval_secs: 5,
            enable_gpu_metrics: true,
            enable_system_metrics: true,
        }
    }
}

/// Prometheus metric collectors
pub struct MetricsCollector {
    // Mining metrics
    pub hashrate: Gauge,
    pub shares_accepted: IntCounter,
    pub shares_rejected: IntCounter,

    // GPU metrics
    pub gpu_utilization: IntGauge,
    pub gpu_temperature: IntGauge,
    pub gpu_power_watts: IntGauge,

    // System metrics
    pub cpu_usage_percent: IntGauge,
    pub memory_used_mb: IntGauge,
}

impl MetricsCollector {
    /// Create and register all metrics with Prometheus registry
    pub fn new() -> Result<Self> {
        Ok(Self {
            // Mining metrics
            hashrate: register_gauge!(
                "opus_miner_hashrate_mhs",
                "Current mining hashrate in MH/s"
            )
            .map_err(|e| MinerError::Metrics(format!("Failed to register hashrate: {}", e)))?,

            shares_accepted: register_int_counter!(
                "opus_miner_shares_accepted_total",
                "Total number of accepted shares"
            )
            .map_err(|e| {
                MinerError::Metrics(format!("Failed to register shares_accepted: {}", e))
            })?,

            shares_rejected: register_int_counter!(
                "opus_miner_shares_rejected_total",
                "Total number of rejected shares"
            )
            .map_err(|e| {
                MinerError::Metrics(format!("Failed to register shares_rejected: {}", e))
            })?,

            // GPU metrics
            gpu_utilization: register_int_gauge!(
                "opus_miner_gpu_utilization_percent",
                "GPU utilization percentage"
            )
            .map_err(|e| {
                MinerError::Metrics(format!("Failed to register gpu_utilization: {}", e))
            })?,

            gpu_temperature: register_int_gauge!(
                "opus_miner_gpu_temperature_celsius",
                "GPU temperature in Celsius"
            )
            .map_err(|e| {
                MinerError::Metrics(format!("Failed to register gpu_temperature: {}", e))
            })?,

            gpu_power_watts: register_int_gauge!(
                "opus_miner_gpu_power_watts",
                "GPU power consumption in watts"
            )
            .map_err(|e| {
                MinerError::Metrics(format!("Failed to register gpu_power_watts: {}", e))
            })?,

            // System metrics
            cpu_usage_percent: register_int_gauge!(
                "opus_miner_cpu_usage_percent",
                "CPU usage percentage"
            )
            .map_err(|e| {
                MinerError::Metrics(format!("Failed to register cpu_usage_percent: {}", e))
            })?,

            memory_used_mb: register_int_gauge!(
                "opus_miner_memory_used_mb",
                "Memory usage in megabytes"
            )
            .map_err(|e| {
                MinerError::Metrics(format!("Failed to register memory_used_mb: {}", e))
            })?,
        })
    }

    /// Export all metrics in Prometheus text format
    pub fn export(&self) -> Result<String> {
        let encoder = TextEncoder::new();
        let metric_families = prometheus::gather();

        encoder
            .encode_to_string(&metric_families)
            .map_err(|e| MinerError::Metrics(format!("Failed to encode metrics: {}", e)))
    }
}

/// Start metrics collector
///
/// # Arguments
/// * `config` - Metrics collection configuration
/// * `bus_handles` - Message bus handles for receiving metrics updates
/// * `cancel_token` - Cancellation token for graceful shutdown
pub async fn start_metrics_collector(
    config: MetricsConfig,
    bus_handles: MessageBusHandles,
    cancel_token: CancellationToken,
) -> Result<()> {
    info!(interval_secs = config.interval_secs, "Starting metrics collector");

    let collector = MetricsCollector::new()?;

    // Main collection loop
    tokio::select! {
        result = metrics_collection_loop(config, collector, bus_handles) => {
            match result {
                Ok(_) => info!("Metrics collector completed normally"),
                Err(e) => warn!(error = %e, "Metrics collector error"),
            }
        }
        _ = cancel_token.cancelled() => {
            info!("Metrics collector shutting down gracefully");
        }
    }

    Ok(())
}

/// Main metrics collection loop
async fn metrics_collection_loop(
    config: MetricsConfig,
    collector: MetricsCollector,
    _message_bus: Arc<MessageBus>,
) -> Result<()> {
    let interval = tokio::time::Duration::from_secs(config.interval_secs);

    loop {
        // TODO: Collect actual metrics from GPU and system
        if config.enable_gpu_metrics {
            collect_gpu_metrics(&collector)?;
        }

        if config.enable_system_metrics {
            collect_system_metrics(&collector)?;
        }

        debug!("Metrics collected successfully");
        tokio::time::sleep(interval).await;
    }
}

/// Collect GPU metrics (stub)
fn collect_gpu_metrics(collector: &MetricsCollector) -> Result<()> {
    // TODO: Use nvml-wrapper to query GPU stats
    // let nvml = nvml_wrapper::Nvml::init()?;
    // let device = nvml.device_by_index(0)?;
    // collector.gpu_utilization.set(device.utilization_rates()?.gpu as i64);
    // collector.gpu_temperature.set(device.temperature(TemperatureSensor::Gpu)? as i64);

    collector.gpu_utilization.set(75);
    collector.gpu_temperature.set(65);
    collector.gpu_power_watts.set(250);

    Ok(())
}

/// Collect system metrics (stub)
fn collect_system_metrics(collector: &MetricsCollector) -> Result<()> {
    // TODO: Use sysinfo or similar crate for system metrics
    collector.cpu_usage_percent.set(30);
    collector.memory_used_mb.set(4096);

    Ok(())
}

// Re-export for convenience
pub use start_metrics_collector as start;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metrics_collector_creation() {
        let collector = MetricsCollector::new();
        assert!(collector.is_ok(), "Collector should be created successfully");
    }

    #[test]
    fn test_metrics_export() {
        let collector = MetricsCollector::new().unwrap();
        let exported = collector.export();
        assert!(exported.is_ok(), "Metrics export should succeed");
    }
}
