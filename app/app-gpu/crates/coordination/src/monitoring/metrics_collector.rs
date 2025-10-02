//! # Metrics Collector (Thu Thập Metrics)
//!
//! Thu thập và lưu trữ performance metrics.

use super::SystemMetrics;
use anyhow::Result;
use std::time::SystemTime;
use tracing::{debug, info};

pub struct MetricsCollector {
    metrics_history: Vec<SystemMetrics>,
    max_history: usize,
}

impl MetricsCollector {
    pub fn new() -> Self {
        info!("📊 Initializing Metrics Collector");
        Self {
            metrics_history: Vec::new(),
            max_history: 1000, // Keep last 1000 metrics
        }
    }

    /// Thu thập metrics hiện tại
    pub async fn collect(&mut self) -> Result<SystemMetrics> {
        debug!("Collecting system metrics...");

        let metrics = SystemMetrics {
            timestamp: SystemTime::now()
                .duration_since(SystemTime::UNIX_EPOCH)?
                .as_secs(),
            hashrate: self.get_current_hashrate().await?,
            gpu_usage: self.get_gpu_usage()?,
            memory_usage: self.get_memory_usage()?,
            uptime_seconds: self.get_uptime(),
        };

        self.metrics_history.push(metrics.clone());

        // Giới hạn history size
        if self.metrics_history.len() > self.max_history {
            self.metrics_history.remove(0);
        }

        Ok(metrics)
    }

    /// Lấy hashrate hiện tại (stub)
    async fn get_current_hashrate(&self) -> Result<f64> {
        // TODO: Query từ MiningEngine
        Ok(0.0)
    }

    /// Lấy GPU usage (stub)
    fn get_gpu_usage(&self) -> Result<Vec<f32>> {
        // TODO: Query nvidia-smi hoặc NVML
        Ok(vec![0.0])
    }

    /// Lấy memory usage (stub)
    fn get_memory_usage(&self) -> Result<u64> {
        // TODO: Query system memory
        Ok(0)
    }

    /// Lấy uptime
    fn get_uptime(&self) -> u64 {
        // TODO: Track từ lúc start
        0
    }

    /// Lấy metrics history
    pub fn get_history(&self) -> &[SystemMetrics] {
        &self.metrics_history
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_metrics_collection() {
        let mut collector = MetricsCollector::new();
        let metrics = collector.collect().await.unwrap();
        assert_eq!(collector.get_history().len(), 1);
    }
}
