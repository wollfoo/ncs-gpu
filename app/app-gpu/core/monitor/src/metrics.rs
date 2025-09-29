//! **Metrics Module** (Mô-đun đo lường)
//!
//! Core metrics definitions and collection utilities for OPUS-GPU monitoring.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// **Metric Value** (Giá trị đo lường) - Different types of metric values
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MetricValue {
    Counter(u64),
    Gauge(f64),
    Histogram { buckets: Vec<(f64, u64)>, sum: f64, count: u64 },
    Summary { quantiles: Vec<(f64, f64)>, sum: f64, count: u64 },
}

impl MetricValue {
    /// Get numeric value for simple metrics
    pub fn as_f64(&self) -> Option<f64> {
        match self {
            MetricValue::Counter(v) => Some(*v as f64),
            MetricValue::Gauge(v) => Some(*v),
            MetricValue::Histogram { sum, count, .. } => {
                if *count > 0 {
                    Some(sum / (*count as f64))
                } else {
                    Some(0.0)
                }
            }
            MetricValue::Summary { sum, count, .. } => {
                if *count > 0 {
                    Some(sum / (*count as f64))
                } else {
                    Some(0.0)
                }
            }
        }
    }

    /// Increment counter value
    pub fn increment(&mut self, value: u64) {
        if let MetricValue::Counter(ref mut v) = self {
            *v += value;
        }
    }

    /// Set gauge value
    pub fn set(&mut self, value: f64) {
        if let MetricValue::Gauge(ref mut v) = self {
            *v = value;
        }
    }
}

/// **Metric** (Đo lường) - Core metric structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Metric {
    pub name: String,
    pub value: MetricValue,
    pub labels: HashMap<String, String>,
    pub help: String,
    pub timestamp: DateTime<Utc>,
    pub unit: Option<String>,
}

impl Metric {
    /// Create new counter metric
    pub fn counter(name: &str, value: u64, help: &str) -> Self {
        Self {
            name: name.to_string(),
            value: MetricValue::Counter(value),
            labels: HashMap::new(),
            help: help.to_string(),
            timestamp: Utc::now(),
            unit: None,
        }
    }

    /// Create new gauge metric
    pub fn gauge(name: &str, value: f64, help: &str) -> Self {
        Self {
            name: name.to_string(),
            value: MetricValue::Gauge(value),
            labels: HashMap::new(),
            help: help.to_string(),
            timestamp: Utc::now(),
            unit: None,
        }
    }

    /// Add labels to metric
    pub fn with_labels(mut self, labels: HashMap<String, String>) -> Self {
        self.labels = labels;
        self
    }

    /// Add single label to metric
    pub fn with_label(mut self, key: &str, value: &str) -> Self {
        self.labels.insert(key.to_string(), value.to_string());
        self
    }

    /// Set unit for metric
    pub fn with_unit(mut self, unit: &str) -> Self {
        self.unit = Some(unit.to_string());
        self
    }
}

/// **GPU Metrics** (Đo lường GPU) - GPU-specific performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuMetrics {
    pub gpu_id: u32,
    pub gpu_name: String,
    pub gpu_uuid: String,
    pub timestamp: DateTime<Utc>,

    // Temperature metrics
    pub temperature_current: f32,
    pub temperature_max: f32,
    pub temperature_throttling: bool,

    // Power metrics
    pub power_draw: f32,
    pub power_limit: f32,
    pub power_efficiency: f32, // MH/s per Watt

    // Utilization metrics
    pub gpu_utilization: f32,
    pub memory_utilization: f32,
    pub encoder_utilization: Option<f32>,
    pub decoder_utilization: Option<f32>,

    // Memory metrics
    pub memory_total: u64,
    pub memory_used: u64,
    pub memory_free: u64,

    // Clock speeds
    pub clock_graphics: u32,
    pub clock_memory: u32,
    pub clock_sm: u32,

    // Mining-specific metrics
    pub hashrate: f64, // MH/s
    pub hashrate_average: f64, // Average over time window
    pub shares_accepted: u64,
    pub shares_rejected: u64,
    pub shares_stale: u64,

    // Error metrics
    pub error_count: u64,
    pub restart_count: u64,
    pub thermal_throttle_count: u64,

    // Fan metrics
    pub fan_speed: Option<f32>, // RPM
    pub fan_percentage: Option<f32>, // %
}

impl GpuMetrics {
    /// Create new GPU metrics instance
    pub fn new(gpu_id: u32, gpu_name: String, gpu_uuid: String) -> Self {
        Self {
            gpu_id,
            gpu_name,
            gpu_uuid,
            timestamp: Utc::now(),
            temperature_current: 0.0,
            temperature_max: 0.0,
            temperature_throttling: false,
            power_draw: 0.0,
            power_limit: 0.0,
            power_efficiency: 0.0,
            gpu_utilization: 0.0,
            memory_utilization: 0.0,
            encoder_utilization: None,
            decoder_utilization: None,
            memory_total: 0,
            memory_used: 0,
            memory_free: 0,
            clock_graphics: 0,
            clock_memory: 0,
            clock_sm: 0,
            hashrate: 0.0,
            hashrate_average: 0.0,
            shares_accepted: 0,
            shares_rejected: 0,
            shares_stale: 0,
            error_count: 0,
            restart_count: 0,
            thermal_throttle_count: 0,
            fan_speed: None,
            fan_percentage: None,
        }
    }

    /// Convert to Prometheus metrics
    pub fn to_prometheus_metrics(&self) -> Vec<Metric> {
        let gpu_id = self.gpu_id.to_string();
        let gpu_name = self.gpu_name.clone();
        let labels = HashMap::from([
            ("gpu_id".to_string(), gpu_id.clone()),
            ("gpu_name".to_string(), gpu_name.clone()),
            ("gpu_uuid".to_string(), self.gpu_uuid.clone()),
        ]);

        vec![
            // Temperature metrics
            Metric::gauge("opus_gpu_temperature_celsius", self.temperature_current as f64,
                         "Current GPU temperature in Celsius")
                .with_labels(labels.clone())
                .with_unit("celsius"),

            Metric::gauge("opus_gpu_temperature_max_celsius", self.temperature_max as f64,
                         "Maximum GPU temperature in Celsius")
                .with_labels(labels.clone())
                .with_unit("celsius"),

            // Power metrics
            Metric::gauge("opus_gpu_power_draw_watts", self.power_draw as f64,
                         "Current GPU power draw in Watts")
                .with_labels(labels.clone())
                .with_unit("watts"),

            Metric::gauge("opus_gpu_power_limit_watts", self.power_limit as f64,
                         "GPU power limit in Watts")
                .with_labels(labels.clone())
                .with_unit("watts"),

            Metric::gauge("opus_gpu_power_efficiency_mhs_per_watt", self.power_efficiency as f64,
                         "GPU power efficiency in MH/s per Watt")
                .with_labels(labels.clone())
                .with_unit("mhs_per_watt"),

            // Utilization metrics
            Metric::gauge("opus_gpu_utilization_percent", self.gpu_utilization as f64,
                         "GPU utilization percentage")
                .with_labels(labels.clone())
                .with_unit("percent"),

            Metric::gauge("opus_gpu_memory_utilization_percent", self.memory_utilization as f64,
                         "GPU memory utilization percentage")
                .with_labels(labels.clone())
                .with_unit("percent"),

            // Memory metrics
            Metric::gauge("opus_gpu_memory_total_bytes", self.memory_total as f64,
                         "Total GPU memory in bytes")
                .with_labels(labels.clone())
                .with_unit("bytes"),

            Metric::gauge("opus_gpu_memory_used_bytes", self.memory_used as f64,
                         "Used GPU memory in bytes")
                .with_labels(labels.clone())
                .with_unit("bytes"),

            Metric::gauge("opus_gpu_memory_free_bytes", self.memory_free as f64,
                         "Free GPU memory in bytes")
                .with_labels(labels.clone())
                .with_unit("bytes"),

            // Clock speeds
            Metric::gauge("opus_gpu_clock_graphics_mhz", self.clock_graphics as f64,
                         "GPU graphics clock speed in MHz")
                .with_labels(labels.clone())
                .with_unit("mhz"),

            Metric::gauge("opus_gpu_clock_memory_mhz", self.clock_memory as f64,
                         "GPU memory clock speed in MHz")
                .with_labels(labels.clone())
                .with_unit("mhz"),

            // Mining metrics
            Metric::gauge("opus_gpu_hashrate_mhs", self.hashrate,
                         "Current GPU hash rate in MH/s")
                .with_labels(labels.clone())
                .with_unit("mhs"),

            Metric::gauge("opus_gpu_hashrate_average_mhs", self.hashrate_average,
                         "Average GPU hash rate in MH/s")
                .with_labels(labels.clone())
                .with_unit("mhs"),

            Metric::counter("opus_gpu_shares_accepted_total", self.shares_accepted,
                           "Total number of accepted shares")
                .with_labels(labels.clone()),

            Metric::counter("opus_gpu_shares_rejected_total", self.shares_rejected,
                           "Total number of rejected shares")
                .with_labels(labels.clone()),

            Metric::counter("opus_gpu_shares_stale_total", self.shares_stale,
                           "Total number of stale shares")
                .with_labels(labels.clone()),

            // Error metrics
            Metric::counter("opus_gpu_errors_total", self.error_count,
                           "Total number of GPU errors")
                .with_labels(labels.clone()),

            Metric::counter("opus_gpu_restarts_total", self.restart_count,
                           "Total number of GPU restarts")
                .with_labels(labels.clone()),

            Metric::counter("opus_gpu_thermal_throttle_total", self.thermal_throttle_count,
                           "Total number of thermal throttling events")
                .with_labels(labels.clone()),
        ]
    }

    /// Calculate rejection rate percentage
    pub fn rejection_rate(&self) -> f32 {
        let total_shares = self.shares_accepted + self.shares_rejected + self.shares_stale;
        if total_shares == 0 {
            0.0
        } else {
            (self.shares_rejected as f32 / total_shares as f32) * 100.0
        }
    }
}

/// **Pool Metrics** (Đo lường pool) - Mining pool statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoolMetrics {
    pub pool_name: String,
    pub pool_url: String,
    pub timestamp: DateTime<Utc>,

    // Connection metrics
    pub connected: bool,
    pub connection_uptime: Duration,
    pub connection_attempts: u64,
    pub connection_failures: u64,

    // Network metrics
    pub latency_ms: u32,
    pub latency_average_ms: f32,
    pub network_errors: u64,

    // Share metrics
    pub shares_submitted: u64,
    pub shares_accepted: u64,
    pub shares_rejected: u64,
    pub shares_stale: u64,
    pub difficulty_current: f64,
    pub difficulty_average: f64,

    // Performance metrics
    pub hashrate_reported: f64, // MH/s
    pub hashrate_calculated: f64, // MH/s
    pub efficiency: f32, // %

    // Payout metrics
    pub balance: f64,
    pub paid_total: f64,
    pub last_payout: Option<DateTime<Utc>>,

    // Worker metrics
    pub workers_active: u32,
    pub workers_total: u32,
}

use std::time::Duration;

impl PoolMetrics {
    /// Create new pool metrics
    pub fn new(pool_name: String, pool_url: String) -> Self {
        Self {
            pool_name,
            pool_url,
            timestamp: Utc::now(),
            connected: false,
            connection_uptime: Duration::from_secs(0),
            connection_attempts: 0,
            connection_failures: 0,
            latency_ms: 0,
            latency_average_ms: 0.0,
            network_errors: 0,
            shares_submitted: 0,
            shares_accepted: 0,
            shares_rejected: 0,
            shares_stale: 0,
            difficulty_current: 0.0,
            difficulty_average: 0.0,
            hashrate_reported: 0.0,
            hashrate_calculated: 0.0,
            efficiency: 0.0,
            balance: 0.0,
            paid_total: 0.0,
            last_payout: None,
            workers_active: 0,
            workers_total: 0,
        }
    }

    /// Convert to Prometheus metrics
    pub fn to_prometheus_metrics(&self) -> Vec<Metric> {
        let pool_name = self.pool_name.clone();
        let labels = HashMap::from([
            ("pool_name".to_string(), pool_name.clone()),
            ("pool_url".to_string(), self.pool_url.clone()),
        ]);

        vec![
            // Connection metrics
            Metric::gauge("opus_pool_connected", if self.connected { 1.0 } else { 0.0 },
                         "Pool connection status (1=connected, 0=disconnected)")
                .with_labels(labels.clone()),

            Metric::gauge("opus_pool_connection_uptime_seconds", self.connection_uptime.as_secs() as f64,
                         "Pool connection uptime in seconds")
                .with_labels(labels.clone())
                .with_unit("seconds"),

            Metric::counter("opus_pool_connection_attempts_total", self.connection_attempts,
                           "Total number of pool connection attempts")
                .with_labels(labels.clone()),

            Metric::counter("opus_pool_connection_failures_total", self.connection_failures,
                           "Total number of pool connection failures")
                .with_labels(labels.clone()),

            // Network metrics
            Metric::gauge("opus_pool_latency_ms", self.latency_ms as f64,
                         "Current pool latency in milliseconds")
                .with_labels(labels.clone())
                .with_unit("milliseconds"),

            Metric::gauge("opus_pool_latency_average_ms", self.latency_average_ms as f64,
                         "Average pool latency in milliseconds")
                .with_labels(labels.clone())
                .with_unit("milliseconds"),

            // Share metrics
            Metric::counter("opus_pool_shares_submitted_total", self.shares_submitted,
                           "Total number of shares submitted to pool")
                .with_labels(labels.clone()),

            Metric::counter("opus_pool_shares_accepted_total", self.shares_accepted,
                           "Total number of shares accepted by pool")
                .with_labels(labels.clone()),

            Metric::counter("opus_pool_shares_rejected_total", self.shares_rejected,
                           "Total number of shares rejected by pool")
                .with_labels(labels.clone()),

            // Performance metrics
            Metric::gauge("opus_pool_hashrate_reported_mhs", self.hashrate_reported,
                         "Pool-reported hash rate in MH/s")
                .with_labels(labels.clone())
                .with_unit("mhs"),

            Metric::gauge("opus_pool_hashrate_calculated_mhs", self.hashrate_calculated,
                         "Locally calculated hash rate in MH/s")
                .with_labels(labels.clone())
                .with_unit("mhs"),

            Metric::gauge("opus_pool_efficiency_percent", self.efficiency as f64,
                         "Pool efficiency percentage")
                .with_labels(labels.clone())
                .with_unit("percent"),

            // Payout metrics
            Metric::gauge("opus_pool_balance", self.balance,
                         "Current pool balance")
                .with_labels(labels.clone()),

            Metric::gauge("opus_pool_paid_total", self.paid_total,
                         "Total amount paid by pool")
                .with_labels(labels.clone()),

            // Worker metrics
            Metric::gauge("opus_pool_workers_active", self.workers_active as f64,
                         "Number of active workers")
                .with_labels(labels.clone()),

            Metric::gauge("opus_pool_workers_total", self.workers_total as f64,
                         "Total number of workers")
                .with_labels(labels.clone()),
        ]
    }

    /// Calculate rejection rate
    pub fn rejection_rate(&self) -> f32 {
        if self.shares_submitted == 0 {
            0.0
        } else {
            (self.shares_rejected as f32 / self.shares_submitted as f32) * 100.0
        }
    }

    /// Calculate acceptance rate
    pub fn acceptance_rate(&self) -> f32 {
        if self.shares_submitted == 0 {
            0.0
        } else {
            (self.shares_accepted as f32 / self.shares_submitted as f32) * 100.0
        }
    }
}

/// **System Metrics** (Đo lường hệ thống) - System resource metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemMetrics {
    pub timestamp: DateTime<Utc>,
    pub hostname: String,

    // CPU metrics
    pub cpu_usage_percent: f32,
    pub cpu_temperature: Option<f32>,
    pub cpu_frequency: Option<f32>,
    pub load_average_1m: f32,
    pub load_average_5m: f32,
    pub load_average_15m: f32,

    // Memory metrics
    pub memory_total: u64,
    pub memory_used: u64,
    pub memory_available: u64,
    pub memory_cached: u64,
    pub swap_total: u64,
    pub swap_used: u64,

    // Disk metrics
    pub disk_usage: HashMap<String, DiskUsage>,

    // Network metrics
    pub network_interfaces: HashMap<String, NetworkInterface>,

    // Process metrics
    pub process_count: u32,
    pub thread_count: u32,

    // Uptime
    pub uptime_seconds: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiskUsage {
    pub total: u64,
    pub used: u64,
    pub available: u64,
    pub usage_percent: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkInterface {
    pub bytes_sent: u64,
    pub bytes_received: u64,
    pub packets_sent: u64,
    pub packets_received: u64,
    pub errors_sent: u64,
    pub errors_received: u64,
}

impl SystemMetrics {
    /// Convert to Prometheus metrics
    pub fn to_prometheus_metrics(&self) -> Vec<Metric> {
        let hostname = self.hostname.clone();
        let base_labels = HashMap::from([
            ("hostname".to_string(), hostname.clone()),
        ]);

        let mut metrics = vec![
            // CPU metrics
            Metric::gauge("opus_system_cpu_usage_percent", self.cpu_usage_percent as f64,
                         "System CPU usage percentage")
                .with_labels(base_labels.clone())
                .with_unit("percent"),

            Metric::gauge("opus_system_load_average_1m", self.load_average_1m as f64,
                         "System load average over 1 minute")
                .with_labels(base_labels.clone()),

            Metric::gauge("opus_system_load_average_5m", self.load_average_5m as f64,
                         "System load average over 5 minutes")
                .with_labels(base_labels.clone()),

            Metric::gauge("opus_system_load_average_15m", self.load_average_15m as f64,
                         "System load average over 15 minutes")
                .with_labels(base_labels.clone()),

            // Memory metrics
            Metric::gauge("opus_system_memory_total_bytes", self.memory_total as f64,
                         "Total system memory in bytes")
                .with_labels(base_labels.clone())
                .with_unit("bytes"),

            Metric::gauge("opus_system_memory_used_bytes", self.memory_used as f64,
                         "Used system memory in bytes")
                .with_labels(base_labels.clone())
                .with_unit("bytes"),

            Metric::gauge("opus_system_memory_available_bytes", self.memory_available as f64,
                         "Available system memory in bytes")
                .with_labels(base_labels.clone())
                .with_unit("bytes"),

            // Process metrics
            Metric::gauge("opus_system_process_count", self.process_count as f64,
                         "Number of system processes")
                .with_labels(base_labels.clone()),

            Metric::gauge("opus_system_uptime_seconds", self.uptime_seconds as f64,
                         "System uptime in seconds")
                .with_labels(base_labels.clone())
                .with_unit("seconds"),
        ];

        // Add disk metrics
        for (device, usage) in &self.disk_usage {
            let mut disk_labels = base_labels.clone();
            disk_labels.insert("device".to_string(), device.clone());

            metrics.extend(vec![
                Metric::gauge("opus_system_disk_total_bytes", usage.total as f64,
                             "Total disk space in bytes")
                    .with_labels(disk_labels.clone())
                    .with_unit("bytes"),

                Metric::gauge("opus_system_disk_used_bytes", usage.used as f64,
                             "Used disk space in bytes")
                    .with_labels(disk_labels.clone())
                    .with_unit("bytes"),

                Metric::gauge("opus_system_disk_usage_percent", usage.usage_percent as f64,
                             "Disk usage percentage")
                    .with_labels(disk_labels.clone())
                    .with_unit("percent"),
            ]);
        }

        // Add network metrics
        for (interface, stats) in &self.network_interfaces {
            let mut net_labels = base_labels.clone();
            net_labels.insert("interface".to_string(), interface.clone());

            metrics.extend(vec![
                Metric::counter("opus_system_network_bytes_sent_total", stats.bytes_sent,
                               "Total bytes sent on network interface")
                    .with_labels(net_labels.clone())
                    .with_unit("bytes"),

                Metric::counter("opus_system_network_bytes_received_total", stats.bytes_received,
                               "Total bytes received on network interface")
                    .with_labels(net_labels.clone())
                    .with_unit("bytes"),

                Metric::counter("opus_system_network_packets_sent_total", stats.packets_sent,
                               "Total packets sent on network interface")
                    .with_labels(net_labels.clone()),

                Metric::counter("opus_system_network_packets_received_total", stats.packets_received,
                               "Total packets received on network interface")
                    .with_labels(net_labels.clone()),
            ]);
        }

        metrics
    }

    /// Calculate memory usage percentage
    pub fn memory_usage_percent(&self) -> f32 {
        if self.memory_total == 0 {
            0.0
        } else {
            (self.memory_used as f32 / self.memory_total as f32) * 100.0
        }
    }
}