//! Mining Metrics Collection and Reporting
//!
//! This module provides comprehensive metrics collection for mining operations including:
//! - Real-time performance metrics (hashrate, efficiency, temperatures)
//! - Historical data aggregation and analysis
//! - Resource utilization tracking
//! - Alert and threshold monitoring
//! - Export capabilities for external monitoring systems

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use histogram::Histogram;
use metrics::{counter, gauge, histogram as metrics_histogram, Key, Label};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Mutex;
use tokio::time::interval;
use tracing::{debug, info, warn, error};
use uuid::Uuid;

/// Metrics collection configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricsConfig {
    /// Collection interval for real-time metrics
    pub collection_interval: Duration,
    /// Historical data retention period
    pub retention_period: Duration,
    /// Number of data points to keep in memory
    pub max_data_points: usize,
    /// Enable detailed GPU metrics collection
    pub detailed_gpu_metrics: bool,
    /// Enable process metrics collection
    pub process_metrics: bool,
    /// Enable network metrics collection
    pub network_metrics: bool,
    /// Metrics export format
    pub export_format: MetricsExportFormat,
    /// Alert thresholds
    pub alert_thresholds: AlertThresholds,
}

/// Metrics export formats
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MetricsExportFormat {
    /// Prometheus format
    Prometheus,
    /// JSON format
    Json,
    /// CSV format
    Csv,
    /// InfluxDB line protocol
    InfluxDB,
}

/// Alert threshold configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertThresholds {
    /// Low hashrate threshold (percentage of expected)
    pub low_hashrate_threshold: f64,
    /// High temperature threshold (Celsius)
    pub high_temperature_threshold: f32,
    /// High power consumption threshold (watts)
    pub high_power_threshold: f32,
    /// Low efficiency threshold (hashes per watt)
    pub low_efficiency_threshold: f64,
    /// High error rate threshold (percentage)
    pub high_error_rate_threshold: f64,
    /// Memory usage threshold (percentage)
    pub memory_usage_threshold: f64,
}

/// Real-time mining metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningMetrics {
    /// Timestamp of measurement
    pub timestamp: DateTime<Utc>,
    /// Total system hashrate (hashes/second)
    pub total_hashrate: f64,
    /// Average hashrate over last minute
    pub avg_hashrate_1m: f64,
    /// Average hashrate over last hour
    pub avg_hashrate_1h: f64,
    /// Average hashrate over last 24 hours
    pub avg_hashrate_24h: f64,
    /// Total power consumption (watts)
    pub total_power: f64,
    /// System efficiency (hashes per watt)
    pub efficiency: f64,
    /// Number of shares found
    pub shares_found: u64,
    /// Number of shares accepted
    pub shares_accepted: u64,
    /// Number of shares rejected
    pub shares_rejected: u64,
    /// Share acceptance rate (0.0-1.0)
    pub acceptance_rate: f64,
    /// Average share time
    pub avg_share_time: Duration,
    /// Total mining uptime
    pub uptime: Duration,
    /// Per-GPU metrics
    pub gpu_metrics: HashMap<usize, GpuMetrics>,
}

/// Individual GPU metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuMetrics {
    /// GPU device ID
    pub device_id: usize,
    /// GPU hashrate (hashes/second)
    pub hashrate: f64,
    /// GPU temperature (Celsius)
    pub temperature: f32,
    /// GPU power consumption (watts)
    pub power: f32,
    /// GPU utilization (0.0-1.0)
    pub utilization: f64,
    /// Memory utilization (0.0-1.0)
    pub memory_utilization: f64,
    /// Fan speed (0.0-1.0)
    pub fan_speed: f64,
    /// Mining intensity
    pub intensity: u8,
    /// Number of errors
    pub error_count: u64,
    /// Thermal throttling status
    pub thermal_throttled: bool,
}

/// Historical metrics data point
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricsDataPoint {
    /// Timestamp
    pub timestamp: DateTime<Utc>,
    /// Metric name
    pub metric: String,
    /// Metric value
    pub value: f64,
    /// Optional labels/tags
    pub labels: HashMap<String, String>,
}

/// Performance statistics and analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceStats {
    /// Current metrics snapshot
    pub current: MiningMetrics,
    /// Performance trends
    pub trends: PerformanceTrends,
    /// Performance distribution histograms
    pub distributions: PerformanceDistributions,
    /// Alert status
    pub alerts: Vec<MetricsAlert>,
    /// Efficiency analysis
    pub efficiency_analysis: EfficiencyAnalysis,
}

/// Performance trends over time
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceTrends {
    /// Hashrate trend (positive = increasing)
    pub hashrate_trend: f64,
    /// Power consumption trend
    pub power_trend: f64,
    /// Temperature trend
    pub temperature_trend: f64,
    /// Efficiency trend
    pub efficiency_trend: f64,
    /// Error rate trend
    pub error_rate_trend: f64,
}

/// Performance distribution histograms
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceDistributions {
    /// Hashrate distribution percentiles
    pub hashrate_percentiles: HashMap<String, f64>,
    /// Temperature distribution percentiles
    pub temperature_percentiles: HashMap<String, f32>,
    /// Power distribution percentiles
    pub power_percentiles: HashMap<String, f64>,
    /// Efficiency distribution percentiles
    pub efficiency_percentiles: HashMap<String, f64>,
}

/// Metrics alert
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricsAlert {
    /// Alert ID
    pub id: Uuid,
    /// Alert severity level
    pub severity: AlertSeverity,
    /// Alert message
    pub message: String,
    /// Metric that triggered the alert
    pub metric: String,
    /// Current value
    pub current_value: f64,
    /// Threshold value
    pub threshold_value: f64,
    /// Alert timestamp
    pub timestamp: DateTime<Utc>,
    /// Whether alert is acknowledged
    pub acknowledged: bool,
}

/// Alert severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AlertSeverity {
    Info,
    Warning,
    Error,
    Critical,
}

/// Efficiency analysis results
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EfficiencyAnalysis {
    /// Current overall efficiency (hashes/watt)
    pub current_efficiency: f64,
    /// Best recorded efficiency
    pub best_efficiency: f64,
    /// Efficiency improvement potential
    pub improvement_potential: f64,
    /// Recommended optimizations
    pub recommendations: Vec<String>,
    /// Power consumption breakdown
    pub power_breakdown: PowerBreakdown,
}

/// Power consumption breakdown
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PowerBreakdown {
    /// GPU power consumption
    pub gpu_power: f64,
    /// CPU power consumption
    pub cpu_power: f64,
    /// System power consumption
    pub system_power: f64,
    /// Cooling power consumption
    pub cooling_power: f64,
}

/// Main metrics collector
pub struct MetricsCollector {
    /// Configuration
    config: RwLock<MetricsConfig>,
    /// Current metrics snapshot
    current_metrics: RwLock<Option<MiningMetrics>>,
    /// Historical data storage
    historical_data: RwLock<VecDeque<MetricsDataPoint>>,
    /// Performance histograms
    histograms: RwLock<HashMap<String, Histogram>>,
    /// Active alerts
    active_alerts: RwLock<HashMap<Uuid, MetricsAlert>>,
    /// Collection task handle
    collection_task: Mutex<Option<tokio::task::JoinHandle<()>>>,
    /// Data sources
    data_sources: RwLock<Vec<Arc<dyn MetricsSource>>>,
}

/// Trait for metrics data sources
#[async_trait::async_trait]
pub trait MetricsSource: Send + Sync {
    /// Get source identifier
    fn source_id(&self) -> &str;

    /// Collect metrics from this source
    async fn collect_metrics(&self) -> Result<Vec<MetricsDataPoint>>;

    /// Get source health status
    async fn health_status(&self) -> Result<bool>;
}

/// GPU metrics source
pub struct GpuMetricsSource {
    /// GPU device ID
    device_id: usize,
    /// GPU context reference
    gpu_context: Arc<crate::gpu_manager::GpuMiningContext>,
}

/// Process metrics source
pub struct ProcessMetricsSource {
    /// Process ID
    process_id: Uuid,
    /// Process manager reference
    process_manager: Arc<crate::process::ProcessManager>,
}

impl Default for MetricsConfig {
    fn default() -> Self {
        Self {
            collection_interval: Duration::from_secs(5),
            retention_period: Duration::from_secs(24 * 3600), // 24 hours
            max_data_points: 17280, // 24 hours at 5-second intervals
            detailed_gpu_metrics: true,
            process_metrics: true,
            network_metrics: false,
            export_format: MetricsExportFormat::Prometheus,
            alert_thresholds: AlertThresholds::default(),
        }
    }
}

impl Default for AlertThresholds {
    fn default() -> Self {
        Self {
            low_hashrate_threshold: 0.8, // 80% of expected
            high_temperature_threshold: 85.0,
            high_power_threshold: 350.0,
            low_efficiency_threshold: 100000.0, // 100K hashes/watt
            high_error_rate_threshold: 0.05, // 5%
            memory_usage_threshold: 0.9, // 90%
        }
    }
}

impl MetricsCollector {
    /// Create new metrics collector
    pub fn new(config: MetricsConfig) -> Self {
        Self {
            config: RwLock::new(config),
            current_metrics: RwLock::new(None),
            historical_data: RwLock::new(VecDeque::new()),
            histograms: RwLock::new(HashMap::new()),
            active_alerts: RwLock::new(HashMap::new()),
            collection_task: Mutex::new(None),
            data_sources: RwLock::new(Vec::new()),
        }
    }

    /// Add a metrics data source
    pub fn add_source(&self, source: Arc<dyn MetricsSource>) {
        self.data_sources.write().push(source);
    }

    /// Start metrics collection
    pub async fn start_collection(&self) -> Result<()> {
        let config = self.config.read().clone();
        let data_sources = self.data_sources.read().clone();
        let current_metrics = Arc::clone(&self.current_metrics);
        let historical_data = Arc::clone(&self.historical_data);
        let histograms = Arc::clone(&self.histograms);
        let active_alerts = Arc::clone(&self.active_alerts);

        let collection_task = tokio::spawn(async move {
            let mut interval = interval(config.collection_interval);

            loop {
                interval.tick().await;

                // Collect data from all sources
                let mut all_data_points = Vec::new();

                for source in &data_sources {
                    match source.collect_metrics().await {
                        Ok(mut data_points) => {
                            all_data_points.append(&mut data_points);
                        }
                        Err(e) => {
                            warn!("Failed to collect metrics from source {}: {}",
                                  source.source_id(), e);
                        }
                    }
                }

                // Process collected data
                if !all_data_points.is_empty() {
                    Self::process_data_points(
                        &all_data_points,
                        &current_metrics,
                        &historical_data,
                        &histograms,
                        &active_alerts,
                        &config,
                    ).await;
                }
            }
        });

        *self.collection_task.lock().await = Some(collection_task);
        info!("Started metrics collection");

        Ok(())
    }

    /// Process collected data points
    async fn process_data_points(
        data_points: &[MetricsDataPoint],
        current_metrics: &RwLock<Option<MiningMetrics>>,
        historical_data: &RwLock<VecDeque<MetricsDataPoint>>,
        histograms: &RwLock<HashMap<String, Histogram>>,
        active_alerts: &RwLock<HashMap<Uuid, MetricsAlert>>,
        config: &MetricsConfig,
    ) {
        // Update Prometheus metrics
        for data_point in data_points {
            let labels = data_point.labels.iter()
                .map(|(k, v)| Label::new(k.clone(), v.clone()))
                .collect::<Vec<_>>();

            let key = Key::from_parts(&data_point.metric, labels);
            gauge!(key.clone(), data_point.value);

            // Update histograms
            let mut histograms_guard = histograms.write();
            let histogram = histograms_guard.entry(data_point.metric.clone())
                .or_insert_with(|| Histogram::new());

            let _ = histogram.increment(data_point.value as u64);
        }

        // Update historical data
        {
            let mut historical = historical_data.write();
            for data_point in data_points {
                historical.push_back(data_point.clone());
            }

            // Trim old data
            while historical.len() > config.max_data_points {
                historical.pop_front();
            }
        }

        // Aggregate current metrics
        let aggregated = Self::aggregate_current_metrics(data_points);
        *current_metrics.write() = Some(aggregated.clone());

        // Check for alerts
        Self::check_alert_thresholds(&aggregated, active_alerts, &config.alert_thresholds);
    }

    /// Aggregate data points into current metrics
    fn aggregate_current_metrics(data_points: &[MetricsDataPoint]) -> MiningMetrics {
        let mut gpu_metrics = HashMap::new();
        let mut total_hashrate = 0.0;
        let mut total_power = 0.0;
        let mut shares_found = 0u64;
        let mut shares_accepted = 0u64;
        let mut shares_rejected = 0u64;

        // Group data points by GPU
        let mut gpu_data: HashMap<usize, HashMap<String, f64>> = HashMap::new();

        for data_point in data_points {
            if let Some(gpu_id_str) = data_point.labels.get("gpu_id") {
                if let Ok(gpu_id) = gpu_id_str.parse::<usize>() {
                    let gpu_entry = gpu_data.entry(gpu_id).or_insert_with(HashMap::new);
                    gpu_entry.insert(data_point.metric.clone(), data_point.value);
                }
            }

            // Aggregate system-wide metrics
            match data_point.metric.as_str() {
                "hashrate" => total_hashrate += data_point.value,
                "power" => total_power += data_point.value,
                "shares_found" => shares_found += data_point.value as u64,
                "shares_accepted" => shares_accepted += data_point.value as u64,
                "shares_rejected" => shares_rejected += data_point.value as u64,
                _ => {}
            }
        }

        // Build GPU metrics
        for (gpu_id, data) in gpu_data {
            let gpu_metric = GpuMetrics {
                device_id: gpu_id,
                hashrate: data.get("hashrate").copied().unwrap_or(0.0),
                temperature: data.get("temperature").copied().unwrap_or(0.0) as f32,
                power: data.get("power").copied().unwrap_or(0.0) as f32,
                utilization: data.get("utilization").copied().unwrap_or(0.0),
                memory_utilization: data.get("memory_utilization").copied().unwrap_or(0.0),
                fan_speed: data.get("fan_speed").copied().unwrap_or(0.0),
                intensity: data.get("intensity").copied().unwrap_or(20.0) as u8,
                error_count: data.get("error_count").copied().unwrap_or(0.0) as u64,
                thermal_throttled: data.get("thermal_throttled").copied().unwrap_or(0.0) > 0.0,
            };
            gpu_metrics.insert(gpu_id, gpu_metric);
        }

        // Calculate derived metrics
        let acceptance_rate = if shares_found > 0 {
            shares_accepted as f64 / shares_found as f64
        } else {
            0.0
        };

        let efficiency = if total_power > 0.0 {
            total_hashrate / total_power
        } else {
            0.0
        };

        MiningMetrics {
            timestamp: Utc::now(),
            total_hashrate,
            avg_hashrate_1m: total_hashrate, // TODO: Calculate actual averages
            avg_hashrate_1h: total_hashrate,
            avg_hashrate_24h: total_hashrate,
            total_power,
            efficiency,
            shares_found,
            shares_accepted,
            shares_rejected,
            acceptance_rate,
            avg_share_time: Duration::from_secs(30), // TODO: Calculate from data
            uptime: Duration::from_secs(3600), // TODO: Track actual uptime
            gpu_metrics,
        }
    }

    /// Check alert thresholds
    fn check_alert_thresholds(
        metrics: &MiningMetrics,
        active_alerts: &RwLock<HashMap<Uuid, MetricsAlert>>,
        thresholds: &AlertThresholds,
    ) {
        let mut alerts_guard = active_alerts.write();

        // Check hashrate threshold
        if metrics.avg_hashrate_1h > 0.0 {
            let hashrate_ratio = metrics.total_hashrate / metrics.avg_hashrate_1h;
            if hashrate_ratio < thresholds.low_hashrate_threshold {
                let alert = MetricsAlert {
                    id: Uuid::new_v4(),
                    severity: AlertSeverity::Warning,
                    message: format!("Low hashrate detected: {:.2} MH/s ({:.1}% of average)",
                                   metrics.total_hashrate / 1_000_000.0,
                                   hashrate_ratio * 100.0),
                    metric: "hashrate".to_string(),
                    current_value: hashrate_ratio,
                    threshold_value: thresholds.low_hashrate_threshold,
                    timestamp: Utc::now(),
                    acknowledged: false,
                };
                alerts_guard.insert(alert.id, alert);
            }
        }

        // Check GPU temperature thresholds
        for (gpu_id, gpu_metric) in &metrics.gpu_metrics {
            if gpu_metric.temperature > thresholds.high_temperature_threshold {
                let alert = MetricsAlert {
                    id: Uuid::new_v4(),
                    severity: if gpu_metric.temperature > 90.0 {
                        AlertSeverity::Critical
                    } else {
                        AlertSeverity::Warning
                    },
                    message: format!("High temperature on GPU {}: {:.1}°C",
                                   gpu_id, gpu_metric.temperature),
                    metric: "temperature".to_string(),
                    current_value: gpu_metric.temperature as f64,
                    threshold_value: thresholds.high_temperature_threshold as f64,
                    timestamp: Utc::now(),
                    acknowledged: false,
                };
                alerts_guard.insert(alert.id, alert);
            }
        }

        // Check efficiency threshold
        if metrics.efficiency < thresholds.low_efficiency_threshold {
            let alert = MetricsAlert {
                id: Uuid::new_v4(),
                severity: AlertSeverity::Warning,
                message: format!("Low efficiency: {:.0} H/W", metrics.efficiency),
                metric: "efficiency".to_string(),
                current_value: metrics.efficiency,
                threshold_value: thresholds.low_efficiency_threshold,
                timestamp: Utc::now(),
                acknowledged: false,
            };
            alerts_guard.insert(alert.id, alert);
        }
    }

    /// Get current metrics snapshot
    pub fn get_current_metrics(&self) -> Option<MiningMetrics> {
        self.current_metrics.read().clone()
    }

    /// Get performance statistics
    pub fn get_performance_stats(&self) -> PerformanceStats {
        let current = self.current_metrics.read().clone().unwrap_or_else(|| {
            MiningMetrics {
                timestamp: Utc::now(),
                total_hashrate: 0.0,
                avg_hashrate_1m: 0.0,
                avg_hashrate_1h: 0.0,
                avg_hashrate_24h: 0.0,
                total_power: 0.0,
                efficiency: 0.0,
                shares_found: 0,
                shares_accepted: 0,
                shares_rejected: 0,
                acceptance_rate: 0.0,
                avg_share_time: Duration::ZERO,
                uptime: Duration::ZERO,
                gpu_metrics: HashMap::new(),
            }
        });

        let alerts = self.active_alerts.read().values().cloned().collect();

        // TODO: Calculate actual trends and distributions from historical data
        PerformanceStats {
            current,
            trends: PerformanceTrends {
                hashrate_trend: 0.0,
                power_trend: 0.0,
                temperature_trend: 0.0,
                efficiency_trend: 0.0,
                error_rate_trend: 0.0,
            },
            distributions: PerformanceDistributions {
                hashrate_percentiles: HashMap::new(),
                temperature_percentiles: HashMap::new(),
                power_percentiles: HashMap::new(),
                efficiency_percentiles: HashMap::new(),
            },
            alerts,
            efficiency_analysis: EfficiencyAnalysis {
                current_efficiency: 0.0,
                best_efficiency: 0.0,
                improvement_potential: 0.0,
                recommendations: Vec::new(),
                power_breakdown: PowerBreakdown {
                    gpu_power: 0.0,
                    cpu_power: 0.0,
                    system_power: 0.0,
                    cooling_power: 0.0,
                },
            },
        }
    }

    /// Export metrics in specified format
    pub fn export_metrics(&self, format: &MetricsExportFormat) -> Result<String> {
        let metrics = self.get_current_metrics()
            .context("No current metrics available")?;

        match format {
            MetricsExportFormat::Prometheus => self.export_prometheus(&metrics),
            MetricsExportFormat::Json => {
                serde_json::to_string_pretty(&metrics)
                    .context("Failed to serialize metrics to JSON")
            }
            MetricsExportFormat::Csv => self.export_csv(&metrics),
            MetricsExportFormat::InfluxDB => self.export_influxdb(&metrics),
        }
    }

    /// Export metrics in Prometheus format
    fn export_prometheus(&self, metrics: &MiningMetrics) -> Result<String> {
        let mut output = String::new();

        // System-wide metrics
        output.push_str(&format!("# HELP mining_hashrate_total Total system hashrate in hashes per second\n"));
        output.push_str(&format!("# TYPE mining_hashrate_total gauge\n"));
        output.push_str(&format!("mining_hashrate_total {}\n", metrics.total_hashrate));

        output.push_str(&format!("# HELP mining_power_total Total system power consumption in watts\n"));
        output.push_str(&format!("# TYPE mining_power_total gauge\n"));
        output.push_str(&format!("mining_power_total {}\n", metrics.total_power));

        output.push_str(&format!("# HELP mining_efficiency System efficiency in hashes per watt\n"));
        output.push_str(&format!("# TYPE mining_efficiency gauge\n"));
        output.push_str(&format!("mining_efficiency {}\n", metrics.efficiency));

        // Per-GPU metrics
        for (gpu_id, gpu_metric) in &metrics.gpu_metrics {
            let labels = format!("gpu_id=\"{}\"", gpu_id);

            output.push_str(&format!("mining_gpu_hashrate{{{}}} {}\n", labels, gpu_metric.hashrate));
            output.push_str(&format!("mining_gpu_temperature{{{}}} {}\n", labels, gpu_metric.temperature));
            output.push_str(&format!("mining_gpu_power{{{}}} {}\n", labels, gpu_metric.power));
            output.push_str(&format!("mining_gpu_utilization{{{}}} {}\n", labels, gpu_metric.utilization));
            output.push_str(&format!("mining_gpu_intensity{{{}}} {}\n", labels, gpu_metric.intensity));
        }

        Ok(output)
    }

    /// Export metrics in CSV format
    fn export_csv(&self, _metrics: &MiningMetrics) -> Result<String> {
        // TODO: Implement CSV export
        Ok("CSV export not implemented yet".to_string())
    }

    /// Export metrics in InfluxDB line protocol format
    fn export_influxdb(&self, _metrics: &MiningMetrics) -> Result<String> {
        // TODO: Implement InfluxDB export
        Ok("InfluxDB export not implemented yet".to_string())
    }

    /// Acknowledge an alert
    pub fn acknowledge_alert(&self, alert_id: Uuid) -> Result<()> {
        let mut alerts = self.active_alerts.write();
        if let Some(alert) = alerts.get_mut(&alert_id) {
            alert.acknowledged = true;
            info!("Acknowledged alert: {}", alert_id);
        }
        Ok(())
    }

    /// Clear acknowledged alerts
    pub fn clear_acknowledged_alerts(&self) {
        let mut alerts = self.active_alerts.write();
        alerts.retain(|_, alert| !alert.acknowledged);
    }

    /// Stop metrics collection
    pub async fn stop_collection(&self) -> Result<()> {
        if let Some(task) = self.collection_task.lock().await.take() {
            task.abort();
            info!("Stopped metrics collection");
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metrics_config_default() {
        let config = MetricsConfig::default();
        assert_eq!(config.collection_interval, Duration::from_secs(5));
        assert!(config.detailed_gpu_metrics);
    }

    #[test]
    fn test_alert_thresholds_default() {
        let thresholds = AlertThresholds::default();
        assert_eq!(thresholds.low_hashrate_threshold, 0.8);
        assert_eq!(thresholds.high_temperature_threshold, 85.0);
    }

    #[test]
    fn test_alert_severity_ordering() {
        assert!(AlertSeverity::Critical > AlertSeverity::Error);
        assert!(AlertSeverity::Error > AlertSeverity::Warning);
        assert!(AlertSeverity::Warning > AlertSeverity::Info);
    }
}