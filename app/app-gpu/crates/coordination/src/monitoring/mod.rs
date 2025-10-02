//! # Monitoring (Giám Sát)
//!
//! Thu thập metrics và health checks.

pub mod health_check;
pub mod metrics_collector;

use serde::{Deserialize, Serialize};

/// System metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemMetrics {
    pub timestamp: u64,
    pub hashrate: f64,
    pub gpu_usage: Vec<f32>,
    pub memory_usage: u64,
    pub uptime_seconds: u64,
}
