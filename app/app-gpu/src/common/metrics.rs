//! Metrics collection and monitoring for OPUS-GPU
//!
//! Comprehensive metrics system with Prometheus integration,
//! custom metric types, and real-time monitoring capabilities.

use prometheus::{
    Counter, CounterVec, Gauge, GaugeVec, Histogram, HistogramOpts, HistogramVec, IntCounter,
    IntCounterVec, IntGauge, IntGaugeVec, Opts, Registry,
};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};

use crate::common::error::{OpusError, OpusResult};

/// Central metrics registry for OPUS-GPU
pub struct OpusMetrics {
    registry: Arc<Registry>,

    // GPU metrics
    pub gpu_temperature: GaugeVec,
    pub gpu_memory_used: GaugeVec,
    pub gpu_memory_total: GaugeVec,
    pub gpu_power_usage: GaugeVec,
    pub gpu_utilization: GaugeVec,
    pub gpu_fan_speed: GaugeVec,

    // Mining metrics
    pub hash_rate: GaugeVec,
    pub shares_accepted: CounterVec,
    pub shares_rejected: CounterVec,
    pub mining_errors: CounterVec,
    pub mining_restarts: Counter,

    // Resource metrics
    pub cpu_usage: Gauge,
    pub memory_usage: Gauge,
    pub disk_usage: GaugeVec,
    pub network_bytes_sent: Counter,
    pub network_bytes_received: Counter,

    // Performance metrics
    pub operation_duration: HistogramVec,
    pub allocation_time: Histogram,
    pub kernel_execution_time: HistogramVec,

    // Security metrics
    pub auth_attempts: CounterVec,
    pub tls_connections: IntGauge,
    pub encryption_operations: Counter,

    // Cloaking metrics
    pub stealth_events: CounterVec,
    pub process_mask_events: Counter,
    pub network_obfuscation_events: Counter,

    // System health metrics
    pub uptime: Gauge,
    pub health_checks: CounterVec,
    pub error_rate: GaugeVec,
}

impl OpusMetrics {
    /// Create new metrics registry with all OPUS-GPU metrics
    pub fn new() -> OpusResult<Self> {
        let registry = Arc::new(Registry::new());

        // GPU metrics
        let gpu_temperature = GaugeVec::new(
            Opts::new("opus_gpu_temperature_celsius", "GPU temperature in Celsius"),
            &["device_id", "device_name"],
        )?;

        let gpu_memory_used = GaugeVec::new(
            Opts::new("opus_gpu_memory_used_bytes", "GPU memory used in bytes"),
            &["device_id", "device_name"],
        )?;

        let gpu_memory_total = GaugeVec::new(
            Opts::new("opus_gpu_memory_total_bytes", "GPU total memory in bytes"),
            &["device_id", "device_name"],
        )?;

        let gpu_power_usage = GaugeVec::new(
            Opts::new("opus_gpu_power_usage_watts", "GPU power usage in watts"),
            &["device_id", "device_name"],
        )?;

        let gpu_utilization = GaugeVec::new(
            Opts::new("opus_gpu_utilization_percent", "GPU utilization percentage"),
            &["device_id", "device_name"],
        )?;

        let gpu_fan_speed = GaugeVec::new(
            Opts::new("opus_gpu_fan_speed_percent", "GPU fan speed percentage"),
            &["device_id", "device_name"],
        )?;

        // Mining metrics
        let hash_rate = GaugeVec::new(
            Opts::new("opus_mining_hash_rate", "Mining hash rate"),
            &["device_id", "algorithm"],
        )?;

        let shares_accepted = CounterVec::new(
            Opts::new("opus_mining_shares_accepted_total", "Total accepted shares"),
            &["pool", "algorithm"],
        )?;

        let shares_rejected = CounterVec::new(
            Opts::new("opus_mining_shares_rejected_total", "Total rejected shares"),
            &["pool", "algorithm", "reason"],
        )?;

        let mining_errors = CounterVec::new(
            Opts::new("opus_mining_errors_total", "Total mining errors"),
            &["device_id", "error_type"],
        )?;

        let mining_restarts = Counter::new(
            "opus_mining_restarts_total",
            "Total mining restarts",
        )?;

        // Resource metrics
        let cpu_usage = Gauge::new("opus_cpu_usage_percent", "CPU usage percentage")?;

        let memory_usage = Gauge::new("opus_memory_usage_percent", "Memory usage percentage")?;

        let disk_usage = GaugeVec::new(
            Opts::new("opus_disk_usage_percent", "Disk usage percentage"),
            &["mount_point"],
        )?;

        let network_bytes_sent = Counter::new(
            "opus_network_bytes_sent_total",
            "Total network bytes sent",
        )?;

        let network_bytes_received = Counter::new(
            "opus_network_bytes_received_total",
            "Total network bytes received",
        )?;

        // Performance metrics
        let operation_duration = HistogramVec::new(
            HistogramOpts::new(
                "opus_operation_duration_seconds",
                "Duration of various operations",
            )
            .buckets(vec![0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]),
            &["operation", "component"],
        )?;

        let allocation_time = Histogram::with_opts(
            HistogramOpts::new("opus_allocation_duration_seconds", "Memory allocation time")
                .buckets(vec![0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]),
        )?;

        let kernel_execution_time = HistogramVec::new(
            HistogramOpts::new(
                "opus_kernel_execution_duration_seconds",
                "CUDA kernel execution time",
            )
            .buckets(vec![0.0001, 0.001, 0.01, 0.1, 1.0]),
            &["kernel_name", "device_id"],
        )?;

        // Security metrics
        let auth_attempts = CounterVec::new(
            Opts::new("opus_auth_attempts_total", "Authentication attempts"),
            &["method", "status"],
        )?;

        let tls_connections = IntGauge::new(
            "opus_tls_connections_active",
            "Active TLS connections",
        )?;

        let encryption_operations = Counter::new(
            "opus_encryption_operations_total",
            "Total encryption operations",
        )?;

        // Cloaking metrics
        let stealth_events = CounterVec::new(
            Opts::new("opus_stealth_events_total", "Stealth mode events"),
            &["event_type", "status"],
        )?;

        let process_mask_events = Counter::new(
            "opus_process_mask_events_total",
            "Process masking events",
        )?;

        let network_obfuscation_events = Counter::new(
            "opus_network_obfuscation_events_total",
            "Network obfuscation events",
        )?;

        // System health metrics
        let uptime = Gauge::new("opus_uptime_seconds", "System uptime in seconds")?;

        let health_checks = CounterVec::new(
            Opts::new("opus_health_checks_total", "Health check results"),
            &["check_type", "status"],
        )?;

        let error_rate = GaugeVec::new(
            Opts::new("opus_error_rate", "Error rate by component"),
            &["component", "error_type"],
        )?;

        // Register all metrics
        registry.register(Box::new(gpu_temperature.clone()))?;
        registry.register(Box::new(gpu_memory_used.clone()))?;
        registry.register(Box::new(gpu_memory_total.clone()))?;
        registry.register(Box::new(gpu_power_usage.clone()))?;
        registry.register(Box::new(gpu_utilization.clone()))?;
        registry.register(Box::new(gpu_fan_speed.clone()))?;
        registry.register(Box::new(hash_rate.clone()))?;
        registry.register(Box::new(shares_accepted.clone()))?;
        registry.register(Box::new(shares_rejected.clone()))?;
        registry.register(Box::new(mining_errors.clone()))?;
        registry.register(Box::new(mining_restarts.clone()))?;
        registry.register(Box::new(cpu_usage.clone()))?;
        registry.register(Box::new(memory_usage.clone()))?;
        registry.register(Box::new(disk_usage.clone()))?;
        registry.register(Box::new(network_bytes_sent.clone()))?;
        registry.register(Box::new(network_bytes_received.clone()))?;
        registry.register(Box::new(operation_duration.clone()))?;
        registry.register(Box::new(allocation_time.clone()))?;
        registry.register(Box::new(kernel_execution_time.clone()))?;
        registry.register(Box::new(auth_attempts.clone()))?;
        registry.register(Box::new(tls_connections.clone()))?;
        registry.register(Box::new(encryption_operations.clone()))?;
        registry.register(Box::new(stealth_events.clone()))?;
        registry.register(Box::new(process_mask_events.clone()))?;
        registry.register(Box::new(network_obfuscation_events.clone()))?;
        registry.register(Box::new(uptime.clone()))?;
        registry.register(Box::new(health_checks.clone()))?;
        registry.register(Box::new(error_rate.clone()))?;

        Ok(Self {
            registry,
            gpu_temperature,
            gpu_memory_used,
            gpu_memory_total,
            gpu_power_usage,
            gpu_utilization,
            gpu_fan_speed,
            hash_rate,
            shares_accepted,
            shares_rejected,
            mining_errors,
            mining_restarts,
            cpu_usage,
            memory_usage,
            disk_usage,
            network_bytes_sent,
            network_bytes_received,
            operation_duration,
            allocation_time,
            kernel_execution_time,
            auth_attempts,
            tls_connections,
            encryption_operations,
            stealth_events,
            process_mask_events,
            network_obfuscation_events,
            uptime,
            health_checks,
            error_rate,
        })
    }

    /// Get the metrics registry for Prometheus export
    pub fn registry(&self) -> Arc<Registry> {
        self.registry.clone()
    }

    /// Record GPU metrics for a specific device
    pub fn record_gpu_metrics(&self, device_id: u32, device_name: &str, metrics: &GpuMetrics) {
        let device_id_str = device_id.to_string();

        self.gpu_temperature
            .with_label_values(&[&device_id_str, device_name])
            .set(metrics.temperature as f64);

        self.gpu_memory_used
            .with_label_values(&[&device_id_str, device_name])
            .set(metrics.memory_used as f64);

        self.gpu_memory_total
            .with_label_values(&[&device_id_str, device_name])
            .set(metrics.memory_total as f64);

        self.gpu_power_usage
            .with_label_values(&[&device_id_str, device_name])
            .set(metrics.power_usage as f64);

        self.gpu_utilization
            .with_label_values(&[&device_id_str, device_name])
            .set(metrics.utilization as f64);

        self.gpu_fan_speed
            .with_label_values(&[&device_id_str, device_name])
            .set(metrics.fan_speed as f64);
    }

    /// Record mining performance metrics
    pub fn record_mining_metrics(&self, device_id: u32, algorithm: &str, hash_rate: f64) {
        let device_id_str = device_id.to_string();
        self.hash_rate
            .with_label_values(&[&device_id_str, algorithm])
            .set(hash_rate);
    }

    /// Record accepted share
    pub fn record_accepted_share(&self, pool: &str, algorithm: &str) {
        self.shares_accepted
            .with_label_values(&[pool, algorithm])
            .inc();
    }

    /// Record rejected share
    pub fn record_rejected_share(&self, pool: &str, algorithm: &str, reason: &str) {
        self.shares_rejected
            .with_label_values(&[pool, algorithm, reason])
            .inc();
    }

    /// Record mining error
    pub fn record_mining_error(&self, device_id: u32, error_type: &str) {
        let device_id_str = device_id.to_string();
        self.mining_errors
            .with_label_values(&[&device_id_str, error_type])
            .inc();
    }

    /// Record operation timing
    pub fn record_operation_duration(&self, operation: &str, component: &str, duration: Duration) {
        self.operation_duration
            .with_label_values(&[operation, component])
            .observe(duration.as_secs_f64());
    }

    /// Record kernel execution time
    pub fn record_kernel_execution(&self, kernel_name: &str, device_id: u32, duration: Duration) {
        let device_id_str = device_id.to_string();
        self.kernel_execution_time
            .with_label_values(&[kernel_name, &device_id_str])
            .observe(duration.as_secs_f64());
    }

    /// Record authentication attempt
    pub fn record_auth_attempt(&self, method: &str, success: bool) {
        let status = if success { "success" } else { "failure" };
        self.auth_attempts
            .with_label_values(&[method, status])
            .inc();
    }

    /// Update system resource metrics
    pub fn update_system_metrics(&self, system_metrics: &SystemMetrics) {
        self.cpu_usage.set(system_metrics.cpu_usage);
        self.memory_usage.set(system_metrics.memory_usage);

        for (mount_point, usage) in &system_metrics.disk_usage {
            self.disk_usage
                .with_label_values(&[mount_point])
                .set(*usage);
        }
    }

    /// Export metrics as Prometheus format
    pub fn export_prometheus(&self) -> OpusResult<String> {
        use prometheus::Encoder;
        let encoder = prometheus::TextEncoder::new();
        let metric_families = self.registry.gather();

        encoder.encode_to_string(&metric_families)
            .map_err(|e| OpusError::System {
                message: format!("Failed to encode metrics: {}", e),
            })
    }
}

/// GPU metrics snapshot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuMetrics {
    pub temperature: f32,
    pub memory_used: u64,
    pub memory_total: u64,
    pub power_usage: f32,
    pub utilization: f32,
    pub fan_speed: f32,
}

/// System resource metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemMetrics {
    pub cpu_usage: f64,
    pub memory_usage: f64,
    pub disk_usage: HashMap<String, f64>,
    pub network_bytes_sent: u64,
    pub network_bytes_received: u64,
}

/// Mining performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningMetrics {
    pub device_id: u32,
    pub algorithm: String,
    pub hash_rate: f64,
    pub accepted_shares: u64,
    pub rejected_shares: u64,
    pub errors: u64,
}

/// Performance timer for measuring operation duration
pub struct Timer {
    start: Instant,
    operation: String,
    component: String,
}

impl Timer {
    /// Start a new timer
    pub fn new(operation: impl Into<String>, component: impl Into<String>) -> Self {
        Self {
            start: Instant::now(),
            operation: operation.into(),
            component: component.into(),
        }
    }

    /// Stop the timer and record the duration
    pub fn stop(self, metrics: &OpusMetrics) {
        let duration = self.start.elapsed();
        metrics.record_operation_duration(&self.operation, &self.component, duration);
    }
}

/// Macro for timing operations
#[macro_export]
macro_rules! time_operation {
    ($metrics:expr, $operation:expr, $component:expr, $block:block) => {{
        let timer = $crate::common::metrics::Timer::new($operation, $component);
        let result = $block;
        timer.stop($metrics);
        result
    }};
}

/// Metrics collector for automatic system monitoring
pub struct MetricsCollector {
    metrics: Arc<OpusMetrics>,
    collection_interval: Duration,
    running: Arc<std::sync::atomic::AtomicBool>,
}

impl MetricsCollector {
    /// Create new metrics collector
    pub fn new(metrics: Arc<OpusMetrics>, collection_interval: Duration) -> Self {
        Self {
            metrics,
            collection_interval,
            running: Arc::new(std::sync::atomic::AtomicBool::new(false)),
        }
    }

    /// Start metrics collection in background
    pub async fn start(&self) -> OpusResult<()> {
        self.running.store(true, std::sync::atomic::Ordering::SeqCst);

        let metrics = self.metrics.clone();
        let interval = self.collection_interval;
        let running = self.running.clone();

        tokio::spawn(async move {
            let mut interval_timer = tokio::time::interval(interval);

            while running.load(std::sync::atomic::Ordering::SeqCst) {
                interval_timer.tick().await;

                // Collect system metrics
                if let Ok(system_metrics) = Self::collect_system_metrics().await {
                    metrics.update_system_metrics(&system_metrics);
                }

                // Update uptime
                if let Ok(uptime) = Self::get_system_uptime() {
                    metrics.uptime.set(uptime.as_secs_f64());
                }
            }
        });

        Ok(())
    }

    /// Stop metrics collection
    pub fn stop(&self) {
        self.running.store(false, std::sync::atomic::Ordering::SeqCst);
    }

    /// Collect system metrics
    async fn collect_system_metrics() -> OpusResult<SystemMetrics> {
        use sysinfo::{System, SystemExt, DiskExt};

        let mut system = System::new_all();
        system.refresh_all();

        let cpu_usage = system.global_cpu_info().cpu_usage() as f64;
        let memory_usage = (system.used_memory() as f64 / system.total_memory() as f64) * 100.0;

        let mut disk_usage = HashMap::new();
        for disk in system.disks() {
            let mount_point = disk.mount_point().to_string_lossy().to_string();
            let total = disk.total_space();
            let available = disk.available_space();
            let usage = if total > 0 {
                ((total - available) as f64 / total as f64) * 100.0
            } else {
                0.0
            };
            disk_usage.insert(mount_point, usage);
        }

        Ok(SystemMetrics {
            cpu_usage,
            memory_usage,
            disk_usage,
            network_bytes_sent: 0, // Would need additional implementation
            network_bytes_received: 0, // Would need additional implementation
        })
    }

    /// Get system uptime
    fn get_system_uptime() -> OpusResult<Duration> {
        use sysinfo::{System, SystemExt};
        let system = System::new();
        Ok(Duration::from_secs(system.uptime()))
    }
}

impl From<prometheus::Error> for OpusError {
    fn from(err: prometheus::Error) -> Self {
        OpusError::System {
            message: format!("Prometheus error: {}", err),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metrics_creation() {
        let metrics = OpusMetrics::new().unwrap();
        assert!(!metrics.registry().gather().is_empty());
    }

    #[test]
    fn test_gpu_metrics_recording() {
        let metrics = OpusMetrics::new().unwrap();
        let gpu_metrics = GpuMetrics {
            temperature: 65.0,
            memory_used: 1024 * 1024 * 1024, // 1GB
            memory_total: 8 * 1024 * 1024 * 1024, // 8GB
            power_usage: 150.0,
            utilization: 95.0,
            fan_speed: 80.0,
        };

        metrics.record_gpu_metrics(0, "GeForce RTX 3080", &gpu_metrics);

        // Verify metrics were recorded (would need more complex verification in real tests)
        let gathered = metrics.registry().gather();
        assert!(!gathered.is_empty());
    }

    #[test]
    fn test_mining_metrics() {
        let metrics = OpusMetrics::new().unwrap();

        metrics.record_mining_metrics(0, "ethash", 100.5);
        metrics.record_accepted_share("pool1", "ethash");
        metrics.record_rejected_share("pool1", "ethash", "stale");
        metrics.record_mining_error(0, "cuda_error");

        let gathered = metrics.registry().gather();
        assert!(!gathered.is_empty());
    }

    #[test]
    fn test_timer() {
        let metrics = Arc::new(OpusMetrics::new().unwrap());

        {
            let timer = Timer::new("test_operation", "test_component");
            std::thread::sleep(Duration::from_millis(10));
            timer.stop(&metrics);
        }

        let gathered = metrics.registry().gather();
        assert!(!gathered.is_empty());
    }

    #[tokio::test]
    async fn test_metrics_collector() {
        let metrics = Arc::new(OpusMetrics::new().unwrap());
        let collector = MetricsCollector::new(metrics.clone(), Duration::from_millis(100));

        collector.start().await.unwrap();
        tokio::time::sleep(Duration::from_millis(200)).await;
        collector.stop();

        // Verify that system metrics were collected
        let gathered = metrics.registry().gather();
        assert!(!gathered.is_empty());
    }
}