//! Prometheus metrics collection
//!
//! Collects and exposes metrics in Prometheus format:
//! - GPU utilization and temperature
//! - Mining hashrate and shares
//! - System resource usage
//! - Error rates and uptime

mod nvml;

use crate::error::{MinerError, Result};
use crate::messaging::{Message, MessageBusHandles};
use nvml::NvmlCollector;
use prometheus::{
    register_gauge, register_int_counter, register_int_gauge, Gauge, IntCounter,
    IntGauge, TextEncoder,
};
use serde::Deserialize;
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
    pub gpu_memory_used_mb: IntGauge,

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

            gpu_memory_used_mb: register_int_gauge!(
                "opus_miner_gpu_memory_used_mb",
                "GPU memory usage in megabytes"
            )
            .map_err(|e| {
                MinerError::Metrics(format!("Failed to register gpu_memory_used_mb: {}", e))
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
///
/// Listens for MetricsUpdate messages từ GPU modules và updates Prometheus metrics.
async fn metrics_collection_loop(
    config: MetricsConfig,
    collector: MetricsCollector,
    bus_handles: MessageBusHandles,
) -> Result<()> {
    let interval = tokio::time::Duration::from_secs(config.interval_secs);
    let mut last_collection = tokio::time::Instant::now();

    // Initialize NVML collector (graceful fallback if no GPU)
    let nvml_collector = if config.enable_gpu_metrics {
        Some(NvmlCollector::new())
    } else {
        None
    };

    if let Some(ref nvml) = nvml_collector {
        if nvml.is_mock_mode() {
            info!("🔧 NVML metrics running in mock mode (no GPU hardware detected)");
        } else {
            info!(gpu_count = nvml.gpu_count(), "✅ NVML metrics enabled");
        }
    }

    info!("Metrics collection loop started, listening for GPU metrics");

    loop {
        select! {
            // Listen for metrics updates từ message bus
            _ = tokio::time::sleep(tokio::time::Duration::from_millis(100)) => {
                // Non-blocking check for metrics messages
                match bus_handles.metrics_rx.try_recv() {
                    Ok(Message::MetricsUpdate(metrics)) => {
                        debug!(
                            gpu_id = metrics.gpu_id,
                            hashrate = metrics.hashrate,
                            temperature = metrics.temperature,
                            power = metrics.power_usage,
                            utilization = metrics.utilization,
                            memory_mb = metrics.memory_used_mb,
                            "Received GPU metrics update"
                        );

                        // Update Prometheus metrics
                        if config.enable_gpu_metrics {
                            collector.hashrate.set(metrics.hashrate);
                            collector.gpu_temperature.set(metrics.temperature as i64);
                            collector.gpu_power_watts.set(metrics.power_usage as i64);
                            collector.gpu_utilization.set(metrics.utilization as i64);
                            collector.gpu_memory_used_mb.set(metrics.memory_used_mb as i64);
                        }
                    }
                    Ok(Message::Shutdown) => {
                        info!("Received shutdown message");
                        break;
                    }
                    Ok(_) => {
                        // Ignore other message types
                    }
                    Err(crossbeam::channel::TryRecvError::Empty) => {
                        // No messages, continue
                    }
                    Err(crossbeam::channel::TryRecvError::Disconnected) => {
                        warn!("Metrics channel disconnected");
                        break;
                    }
                }
            }

            // Periodic system metrics collection
            _ = tokio::time::sleep_until(last_collection + interval) => {
                last_collection = tokio::time::Instant::now();

                // Collect NVML GPU metrics
                if let Some(ref nvml) = nvml_collector {
                    if let Err(e) = collect_nvml_metrics(nvml, &collector) {
                        warn!(error = %e, "Failed to collect NVML metrics");
                    }
                }

                // Collect system metrics
                if config.enable_system_metrics {
                    collect_system_metrics(&collector)?;
                }

                debug!("Periodic metrics collected");
            }
        }
    }

    Ok(())
}

/// Collect NVML GPU metrics
fn collect_nvml_metrics(nvml: &NvmlCollector, collector: &MetricsCollector) -> Result<()> {
    // Poll all GPUs (typically just GPU 0)
    for gpu_id in 0..nvml.gpu_count() {
        match nvml.collect(gpu_id) {
            Ok(metrics) => {
                collector.gpu_utilization.set(metrics.utilization as i64);
                collector.gpu_temperature.set(metrics.temperature as i64);
                collector.gpu_power_watts.set(metrics.power_usage as i64);
                collector.gpu_memory_used_mb.set(metrics.memory_used_mb as i64);

                debug!(
                    gpu_id = gpu_id,
                    temp = metrics.temperature,
                    power = metrics.power_usage,
                    util = metrics.utilization,
                    mem_mb = metrics.memory_used_mb,
                    "Updated NVML metrics"
                );
            }
            Err(e) => {
                warn!(gpu_id = gpu_id, error = %e, "Failed to collect GPU metrics");
            }
        }
    }

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
        // Note: This test may fail if run in parallel with other tests
        // due to Prometheus registry being a global singleton
        match MetricsCollector::new() {
            Ok(collector) => {
                let exported = collector.export();
                assert!(exported.is_ok(), "Metrics export should succeed");
            }
            Err(_) => {
                // Registry already initialized from another test - skip
                eprintln!("Skipping test_metrics_export: registry already initialized");
            }
        }
    }
}
