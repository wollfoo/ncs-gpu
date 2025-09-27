//! Metrics collection module for Prometheus integration
//! 
//! Provides comprehensive metrics for GPU operations, system health, and performance

use prometheus::{
    Counter, CounterVec, Gauge, GaugeVec, Histogram, HistogramVec,
    IntCounter, IntCounterVec, IntGauge, IntGaugeVec,
    register_counter, register_counter_vec, register_gauge, register_gauge_vec,
    register_histogram, register_histogram_vec, register_int_counter, register_int_counter_vec,
    register_int_gauge, register_int_gauge_vec, Encoder, TextEncoder,
};
use lazy_static::lazy_static;
use std::collections::HashMap;
use std::sync::RwLock;
use anyhow::{Result, Context};

lazy_static! {
    // ========== Task Metrics ==========
    
    /// Total number of tasks submitted
    pub static ref TASKS_SUBMITTED_TOTAL: IntCounter = register_int_counter!(
        "opus_tasks_submitted_total",
        "Total number of tasks submitted to the system"
    ).unwrap();
    
    /// Tasks by status
    pub static ref TASKS_BY_STATUS: IntGaugeVec = register_int_gauge_vec!(
        "opus_tasks_status",
        "Current number of tasks by status",
        &["status"]
    ).unwrap();
    
    /// Task execution duration histogram
    pub static ref TASK_DURATION_HISTOGRAM: HistogramVec = register_histogram_vec!(
        "opus_task_duration_seconds",
        "Task execution duration in seconds",
        &["task_type", "status"],
        vec![0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0]
    ).unwrap();
    
    /// Task queue length
    pub static ref TASK_QUEUE_LENGTH: IntGaugeVec = register_int_gauge_vec!(
        "opus_task_queue_length",
        "Current length of task queues",
        &["queue_name", "priority"]
    ).unwrap();
    
    // ========== GPU Metrics ==========
    
    /// GPU utilization percentage
    pub static ref GPU_UTILIZATION: GaugeVec = register_gauge_vec!(
        "opus_gpu_utilization_percent",
        "GPU utilization percentage",
        &["device_id", "device_name"]
    ).unwrap();
    
    /// GPU memory usage
    pub static ref GPU_MEMORY_USED_BYTES: GaugeVec = register_gauge_vec!(
        "opus_gpu_memory_used_bytes",
        "GPU memory usage in bytes",
        &["device_id", "device_name"]
    ).unwrap();
    
    /// GPU memory total
    pub static ref GPU_MEMORY_TOTAL_BYTES: GaugeVec = register_gauge_vec!(
        "opus_gpu_memory_total_bytes",
        "Total GPU memory in bytes",
        &["device_id", "device_name"]
    ).unwrap();
    
    /// GPU temperature
    pub static ref GPU_TEMPERATURE_CELSIUS: GaugeVec = register_gauge_vec!(
        "opus_gpu_temperature_celsius",
        "GPU temperature in Celsius",
        &["device_id", "device_name"]
    ).unwrap();
    
    /// GPU power usage
    pub static ref GPU_POWER_USAGE_WATTS: GaugeVec = register_gauge_vec!(
        "opus_gpu_power_usage_watts",
        "GPU power usage in watts",
        &["device_id", "device_name"]
    ).unwrap();
    
    /// GPU clock speeds
    pub static ref GPU_CLOCK_SPEED_MHZ: GaugeVec = register_gauge_vec!(
        "opus_gpu_clock_speed_mhz",
        "GPU clock speed in MHz",
        &["device_id", "device_name", "clock_type"]
    ).unwrap();
    
    /// CUDA kernel execution count
    pub static ref CUDA_KERNELS_EXECUTED: CounterVec = register_counter_vec!(
        "opus_cuda_kernels_executed_total",
        "Total number of CUDA kernels executed",
        &["kernel_name", "device_id"]
    ).unwrap();
    
    /// CUDA kernel execution time
    pub static ref CUDA_KERNEL_TIME_SECONDS: HistogramVec = register_histogram_vec!(
        "opus_cuda_kernel_time_seconds",
        "CUDA kernel execution time in seconds",
        &["kernel_name", "device_id"],
        vec![0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
    ).unwrap();
    
    // ========== Memory Pool Metrics ==========
    
    /// Memory pool allocations
    pub static ref MEMORY_POOL_ALLOCATIONS: CounterVec = register_counter_vec!(
        "opus_memory_pool_allocations_total",
        "Total memory pool allocations",
        &["pool_size", "device_id"]
    ).unwrap();
    
    /// Memory pool deallocations
    pub static ref MEMORY_POOL_DEALLOCATIONS: CounterVec = register_counter_vec!(
        "opus_memory_pool_deallocations_total",
        "Total memory pool deallocations",
        &["pool_size", "device_id"]
    ).unwrap();
    
    /// Memory pool fragmentation
    pub static ref MEMORY_POOL_FRAGMENTATION: GaugeVec = register_gauge_vec!(
        "opus_memory_pool_fragmentation_ratio",
        "Memory pool fragmentation ratio",
        &["device_id"]
    ).unwrap();
    
    // ========== Plugin Metrics ==========
    
    /// Plugin load time
    pub static ref PLUGIN_LOAD_TIME_SECONDS: HistogramVec = register_histogram_vec!(
        "opus_plugin_load_time_seconds",
        "Plugin loading time in seconds",
        &["plugin_name", "plugin_version"]
    ).unwrap();
    
    /// Plugin execution count
    pub static ref PLUGIN_EXECUTIONS: CounterVec = register_counter_vec!(
        "opus_plugin_executions_total",
        "Total plugin executions",
        &["plugin_name", "method"]
    ).unwrap();
    
    /// Plugin errors
    pub static ref PLUGIN_ERRORS: CounterVec = register_counter_vec!(
        "opus_plugin_errors_total",
        "Total plugin errors",
        &["plugin_name", "error_type"]
    ).unwrap();
    
    // ========== System Metrics ==========
    
    /// Runtime uptime
    pub static ref RUNTIME_UPTIME_SECONDS: Gauge = register_gauge!(
        "opus_runtime_uptime_seconds",
        "Runtime uptime in seconds"
    ).unwrap();
    
    /// Active connections
    pub static ref ACTIVE_CONNECTIONS: IntGauge = register_int_gauge!(
        "opus_active_connections",
        "Number of active connections"
    ).unwrap();
    
    /// Request rate
    pub static ref REQUEST_RATE: Counter = register_counter!(
        "opus_requests_total",
        "Total number of requests"
    ).unwrap();
    
    /// Request latency
    pub static ref REQUEST_LATENCY: HistogramVec = register_histogram_vec!(
        "opus_request_latency_seconds",
        "Request latency in seconds",
        &["endpoint", "method", "status"],
        vec![0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
    ).unwrap();
    
    /// Error rate
    pub static ref ERROR_RATE: CounterVec = register_counter_vec!(
        "opus_errors_total",
        "Total number of errors",
        &["error_type", "severity"]
    ).unwrap();
}

/// Custom metrics registry for dynamic metrics
pub struct CustomMetrics {
    counters: RwLock<HashMap<String, Counter>>,
    gauges: RwLock<HashMap<String, Gauge>>,
    histograms: RwLock<HashMap<String, Histogram>>,
}

impl CustomMetrics {
    pub fn new() -> Self {
        Self {
            counters: RwLock::new(HashMap::new()),
            gauges: RwLock::new(HashMap::new()),
            histograms: RwLock::new(HashMap::new()),
        }
    }
    
    /// Register a custom counter
    pub fn register_counter(&self, name: &str, help: &str) -> Result<()> {
        let counter = register_counter!(name, help)
            .context("Failed to register counter")?;
        
        let mut counters = self.counters.write().unwrap();
        counters.insert(name.to_string(), counter);
        Ok(())
    }
    
    /// Register a custom gauge
    pub fn register_gauge(&self, name: &str, help: &str) -> Result<()> {
        let gauge = register_gauge!(name, help)
            .context("Failed to register gauge")?;
        
        let mut gauges = self.gauges.write().unwrap();
        gauges.insert(name.to_string(), gauge);
        Ok(())
    }
    
    /// Register a custom histogram
    pub fn register_histogram(&self, name: &str, help: &str, buckets: Vec<f64>) -> Result<()> {
        use prometheus::HistogramOpts;
        
        let opts = HistogramOpts::new(name, help).buckets(buckets);
        let histogram = Histogram::with_opts(opts)
            .context("Failed to create histogram")?;
        
        prometheus::register(Box::new(histogram.clone()))
            .context("Failed to register histogram")?;
        
        let mut histograms = self.histograms.write().unwrap();
        histograms.insert(name.to_string(), histogram);
        Ok(())
    }
    
    /// Increment a counter
    pub fn inc_counter(&self, name: &str, value: f64) {
        let counters = self.counters.read().unwrap();
        if let Some(counter) = counters.get(name) {
            counter.inc_by(value);
        }
    }
    
    /// Set a gauge value
    pub fn set_gauge(&self, name: &str, value: f64) {
        let gauges = self.gauges.read().unwrap();
        if let Some(gauge) = gauges.get(name) {
            gauge.set(value);
        }
    }
    
    /// Observe a histogram value
    pub fn observe_histogram(&self, name: &str, value: f64) {
        let histograms = self.histograms.read().unwrap();
        if let Some(histogram) = histograms.get(name) {
            histogram.observe(value);
        }
    }
}

/// GPU-specific metrics collector
pub struct GPUMetricsCollector {
    device_id: usize,
    device_name: String,
}

impl GPUMetricsCollector {
    pub fn new(device_id: usize, device_name: String) -> Self {
        Self {
            device_id,
            device_name,
        }
    }
    
    /// Update GPU metrics
    pub fn update_metrics(&self, metrics: &GPUMetrics) {
        let device_id_str = self.device_id.to_string();
        
        GPU_UTILIZATION
            .with_label_values(&[&device_id_str, &self.device_name])
            .set(metrics.utilization as f64);
        
        GPU_MEMORY_USED_BYTES
            .with_label_values(&[&device_id_str, &self.device_name])
            .set(metrics.memory_used as f64);
        
        GPU_MEMORY_TOTAL_BYTES
            .with_label_values(&[&device_id_str, &self.device_name])
            .set(metrics.memory_total as f64);
        
        GPU_TEMPERATURE_CELSIUS
            .with_label_values(&[&device_id_str, &self.device_name])
            .set(metrics.temperature as f64);
        
        GPU_POWER_USAGE_WATTS
            .with_label_values(&[&device_id_str, &self.device_name])
            .set(metrics.power_usage as f64);
        
        GPU_CLOCK_SPEED_MHZ
            .with_label_values(&[&device_id_str, &self.device_name, "graphics"])
            .set(metrics.graphics_clock as f64);
        
        GPU_CLOCK_SPEED_MHZ
            .with_label_values(&[&device_id_str, &self.device_name, "memory"])
            .set(metrics.memory_clock as f64);
    }
    
    /// Record kernel execution
    pub fn record_kernel_execution(&self, kernel_name: &str, duration_secs: f64) {
        let device_id_str = self.device_id.to_string();
        
        CUDA_KERNELS_EXECUTED
            .with_label_values(&[kernel_name, &device_id_str])
            .inc();
        
        CUDA_KERNEL_TIME_SECONDS
            .with_label_values(&[kernel_name, &device_id_str])
            .observe(duration_secs);
    }
}

/// GPU metrics structure
pub struct GPUMetrics {
    pub utilization: f32,
    pub memory_used: u64,
    pub memory_total: u64,
    pub temperature: f32,
    pub power_usage: f32,
    pub graphics_clock: f32,
    pub memory_clock: f32,
}

/// Export metrics in Prometheus format
pub fn export_metrics() -> Result<String> {
    let encoder = TextEncoder::new();
    let metric_families = prometheus::gather();
    let mut buffer = Vec::new();
    encoder.encode(&metric_families, &mut buffer)?;
    
    String::from_utf8(buffer).context("Failed to convert metrics to string")
}

/// Initialize metrics subsystem
pub fn init_metrics() -> Result<()> {
    // Set initial values for gauges
    RUNTIME_UPTIME_SECONDS.set(0.0);
    ACTIVE_CONNECTIONS.set(0);
    
    // Initialize task status gauges
    for status in &["pending", "running", "completed", "failed"] {
        TASKS_BY_STATUS.with_label_values(&[status]).set(0);
    }
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_metrics_registration() {
        // Test that metrics are properly registered
        assert!(export_metrics().is_ok());
    }
    
    #[test]
    fn test_custom_metrics() {
        let custom = CustomMetrics::new();
        
        // Register custom metrics
        custom.register_counter("test_counter", "Test counter").unwrap();
        custom.register_gauge("test_gauge", "Test gauge").unwrap();
        custom.register_histogram(
            "test_histogram",
            "Test histogram",
            vec![0.1, 0.5, 1.0]
        ).unwrap();
        
        // Use custom metrics
        custom.inc_counter("test_counter", 1.0);
        custom.set_gauge("test_gauge", 42.0);
        custom.observe_histogram("test_histogram", 0.75);
    }
    
    #[test]
    fn test_gpu_metrics_collector() {
        let collector = GPUMetricsCollector::new(0, "RTX 4090".to_string());
        
        let metrics = GPUMetrics {
            utilization: 85.0,
            memory_used: 10737418240, // 10GB
            memory_total: 25769803776, // 24GB
            temperature: 65.0,
            power_usage: 250.0,
            graphics_clock: 2520.0,
            memory_clock: 10500.0,
        };
        
        collector.update_metrics(&metrics);
        collector.record_kernel_execution("matmul", 0.025);
        
        // Verify metrics are exported
        let exported = export_metrics().unwrap();
        assert!(exported.contains("opus_gpu_utilization_percent"));
        assert!(exported.contains("opus_cuda_kernels_executed_total"));
    }
}
