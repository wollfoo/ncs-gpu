//! **Metrics Plugin** (plugin metrics – module giám sát)

use anyhow::Result;
use async_trait::async_trait;
use prometheus::{Encoder, TextEncoder, Counter, Gauge, Histogram, HistogramOpts};
use std::any::Any;
use std::sync::Arc;
use tracing::{debug, info};

use crate::core::plugin_api::{Plugin, PluginContext, PluginInfo};

lazy_static::lazy_static! {
    // GPU Metrics
    static ref GPU_UTILIZATION: Gauge = Gauge::new(
        "gpu_utilization_percent", "GPU utilization percentage"
    ).unwrap();
    
    static ref GPU_MEMORY_USED: Gauge = Gauge::new(
        "gpu_memory_used_bytes", "GPU memory used in bytes"
    ).unwrap();
    
    static ref GPU_TEMPERATURE: Gauge = Gauge::new(
        "gpu_temperature_celsius", "GPU temperature in Celsius"
    ).unwrap();
    
    static ref GPU_POWER_USAGE: Gauge = Gauge::new(
        "gpu_power_usage_watts", "GPU power usage in watts"
    ).unwrap();
    
    // Mining Metrics
    static ref HASHRATE: Gauge = Gauge::new(
        "mining_hashrate_hps", "Mining hashrate in hashes per second"
    ).unwrap();
    
    static ref SHARES_ACCEPTED: Counter = Counter::new(
        "mining_shares_accepted_total", "Total accepted shares"
    ).unwrap();
    
    static ref SHARES_REJECTED: Counter = Counter::new(
        "mining_shares_rejected_total", "Total rejected shares"
    ).unwrap();
    
    // Task Metrics
    static ref TASKS_SUBMITTED: Counter = Counter::new(
        "scheduler_tasks_submitted_total", "Total tasks submitted"
    ).unwrap();
    
    static ref TASKS_COMPLETED: Counter = Counter::new(
        "scheduler_tasks_completed_total", "Total tasks completed"
    ).unwrap();
    
    static ref TASK_DURATION: Histogram = Histogram::with_opts(
        HistogramOpts::new("task_duration_seconds", "Task execution duration")
    ).unwrap();
}

/// **Metrics Plugin Implementation** (triển khai plugin metrics – module giám sát)
pub struct MetricsPlugin {
    context: Option<Arc<PluginContext>>,
}

impl MetricsPlugin {
    /// **Create new metrics plugin** (tạo plugin metrics mới – khởi tạo module giám sát)
    pub fn new() -> Result<Self> {
        Ok(Self {
            context: None,
        })
    }

    /// **Collect GPU metrics** (thu thập metrics GPU – lấy chỉ số card đồ họa)
    async fn collect_gpu_metrics(&self) -> Result<()> {
        let context = self.context.as_ref()
            .ok_or_else(|| anyhow::anyhow!("Plugin not initialized"))?;

        // Update GPU metrics
        context.gpu_pool.update_metrics().await?;

        for device in context.gpu_pool.devices() {
            let utilization = *device.utilization.read();
            let memory_used = device.total_memory - *device.available_memory.read();
            let temperature = *device.temperature.read();
            let power_usage = *device.power_usage.read();

            GPU_UTILIZATION.set(utilization as f64);
            GPU_MEMORY_USED.set(memory_used as f64);
            GPU_TEMPERATURE.set(temperature as f64);
            GPU_POWER_USAGE.set(power_usage as f64);
        }

        Ok(())
    }

    /// **Collect scheduler metrics** (thu thập metrics scheduler – lấy chỉ số điều phối)
    async fn collect_scheduler_metrics(&self) -> Result<()> {
        let context = self.context.as_ref()
            .ok_or_else(|| anyhow::anyhow!("Plugin not initialized"))?;

        let stats = context.scheduler.stats();
        
        TASKS_SUBMITTED.inc_by(stats.total_submitted.load(std::sync::atomic::Ordering::Relaxed));
        TASKS_COMPLETED.inc_by(stats.total_completed.load(std::sync::atomic::Ordering::Relaxed));

        Ok(())
    }
}

#[async_trait]
impl Plugin for MetricsPlugin {
    fn info(&self) -> PluginInfo {
        PluginInfo {
            name: "MetricsPlugin".to_string(),
            version: "0.1.0".to_string(),
            description: "System and mining metrics collection".to_string(),
            author: "Opus GPU Team".to_string(),
            capabilities: vec![
                "metrics".to_string(),
                "prometheus".to_string(),
                "monitoring".to_string(),
            ],
        }
    }

    async fn initialize(&self, context: Arc<PluginContext>) -> Result<()> {
        info!("🔧 Initializing metrics plugin");
        
        // Store context
        let self_mut = unsafe { &mut *(self as *const Self as *mut Self) };
        self_mut.context = Some(context);

        // Register metrics
        prometheus::register(Box::new(GPU_UTILIZATION.clone()))?;
        prometheus::register(Box::new(GPU_MEMORY_USED.clone()))?;
        prometheus::register(Box::new(GPU_TEMPERATURE.clone()))?;
        prometheus::register(Box::new(GPU_POWER_USAGE.clone()))?;
        prometheus::register(Box::new(HASHRATE.clone()))?;
        prometheus::register(Box::new(SHARES_ACCEPTED.clone()))?;
        prometheus::register(Box::new(SHARES_REJECTED.clone()))?;
        prometheus::register(Box::new(TASKS_SUBMITTED.clone()))?;
        prometheus::register(Box::new(TASKS_COMPLETED.clone()))?;
        prometheus::register(Box::new(TASK_DURATION.clone()))?;

        info!("✅ Metrics plugin initialized");
        Ok(())
    }

    async fn start(&self) -> Result<()> {
        info!("🚀 Starting metrics plugin");
        
        // Start periodic collection
        let self_clone = self as *const Self;
        tokio::spawn(async move {
            loop {
                let plugin = unsafe { &*self_clone };
                
                if let Err(e) = plugin.collect_gpu_metrics().await {
                    debug!("Failed to collect GPU metrics: {}", e);
                }
                
                if let Err(e) = plugin.collect_scheduler_metrics().await {
                    debug!("Failed to collect scheduler metrics: {}", e);
                }
                
                tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
            }
        });

        Ok(())
    }

    async fn metrics(&self) -> Result<serde_json::Value> {
        // Gather all metrics
        let metric_families = prometheus::gather();
        let encoder = TextEncoder::new();
        let mut buffer = Vec::new();
        encoder.encode(&metric_families, &mut buffer)?;
        
        Ok(serde_json::json!({
            "prometheus": String::from_utf8_lossy(&buffer),
            "gpu_count": self.context.as_ref().map(|c| c.gpu_pool.device_count()).unwrap_or(0),
        }))
    }

    fn as_any(&self) -> &dyn Any {
        self
    }
}

/// **Start metrics HTTP server** (khởi động server HTTP metrics – chạy máy chủ giám sát)
pub async fn start_metrics_server(port: u16) -> Result<()> {
    use warp::Filter;

    info!("📊 Starting metrics server on port {}", port);

    let metrics_route = warp::path!("metrics")
        .map(|| {
            let encoder = TextEncoder::new();
            let metric_families = prometheus::gather();
            let mut buffer = Vec::new();
            encoder.encode(&metric_families, &mut buffer).unwrap();
            buffer
        });

    warp::serve(metrics_route)
        .run(([0, 0, 0, 0], port))
        .await;

    Ok(())
}