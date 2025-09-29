//! OPUS-GPU Monitoring Module
//!
//! Comprehensive monitoring and observability system for GPU mining operations.
//!
//! # Features
//! - **Performance Monitoring**: GPU metrics, hash rates, pool statistics
//! - **Health Monitoring**: Component health checks, alerts, auto-recovery
//! - **Observability**: Prometheus metrics, OpenTelemetry tracing, structured logging
//! - **Dashboard Support**: Real-time metrics export and visualization

pub mod metrics;
pub mod health;
pub mod alerts;
pub mod collectors;
pub mod exporters;
pub mod dashboards;
pub mod recovery;

use anyhow::Result;
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::time::Duration;
use uuid::Uuid;

/// **Monitor Service** (Dịch vụ giám sát) - Main monitoring service coordinator
pub use crate::service::MonitorService;

/// **Monitoring Error** (Lỗi giám sát) - Monitoring-specific error types
#[derive(Debug, thiserror::Error)]
pub enum MonitorError {
    #[error("Metric collection failed: {reason}")]
    MetricCollection { reason: String },

    #[error("Health check failed for component {component}: {error}")]
    HealthCheck { component: String, error: String },

    #[error("Alert system error: {message}")]
    Alert { message: String },

    #[error("Export failed: {exporter} - {reason}")]
    Export { exporter: String, reason: String },

    #[error("Configuration error: {config}")]
    Configuration { config: String },

    #[error("GPU monitoring error: {gpu_id} - {error}")]
    Gpu { gpu_id: u32, error: String },

    #[error("System resource error: {resource}")]
    System { resource: String },
}

/// **Monitoring Configuration** (Cấu hình giám sát)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MonitorConfig {
    /// Collection interval for metrics
    pub collection_interval: Duration,

    /// Health check intervals
    pub health_check_interval: Duration,

    /// Alert configuration
    pub alerts: AlertConfig,

    /// Prometheus exporter settings
    pub prometheus: PrometheusConfig,

    /// OpenTelemetry settings
    pub opentelemetry: OpenTelemetryConfig,

    /// Dashboard configuration
    pub dashboard: DashboardConfig,

    /// Auto-recovery settings
    pub recovery: RecoveryConfig,

    /// GPU monitoring settings
    pub gpu_monitoring: GpuMonitoringConfig,

    /// System monitoring settings
    pub system_monitoring: SystemMonitoringConfig,
}

impl Default for MonitorConfig {
    fn default() -> Self {
        Self {
            collection_interval: Duration::from_secs(5),
            health_check_interval: Duration::from_secs(10),
            alerts: AlertConfig::default(),
            prometheus: PrometheusConfig::default(),
            opentelemetry: OpenTelemetryConfig::default(),
            dashboard: DashboardConfig::default(),
            recovery: RecoveryConfig::default(),
            gpu_monitoring: GpuMonitoringConfig::default(),
            system_monitoring: SystemMonitoringConfig::default(),
        }
    }
}

/// **Alert Configuration** (Cấu hình cảnh báo)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertConfig {
    pub enabled: bool,
    pub channels: Vec<AlertChannel>,
    pub thresholds: AlertThresholds,
    pub cooldown: Duration,
}

impl Default for AlertConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            channels: vec![AlertChannel::Log],
            thresholds: AlertThresholds::default(),
            cooldown: Duration::from_secs(300), // 5 minutes
        }
    }
}

/// **Alert Channel** (Kênh cảnh báo) - Different ways to send alerts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AlertChannel {
    Log,
    Email { recipients: Vec<String> },
    Slack { webhook_url: String },
    Webhook { url: String, headers: std::collections::HashMap<String, String> },
    Discord { webhook_url: String },
}

/// **Alert Thresholds** (Ngưỡng cảnh báo) - Configurable alert thresholds
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertThresholds {
    /// GPU temperature threshold (Celsius)
    pub gpu_temperature_critical: f32,
    pub gpu_temperature_warning: f32,

    /// GPU utilization thresholds (%)
    pub gpu_utilization_low: f32,
    pub gpu_utilization_critical: f32,

    /// Hash rate thresholds (MH/s)
    pub hashrate_drop_critical: f32,
    pub hashrate_drop_warning: f32,

    /// Power consumption thresholds (Watts)
    pub power_consumption_critical: f32,

    /// Memory usage thresholds (%)
    pub memory_usage_critical: f32,
    pub memory_usage_warning: f32,

    /// System CPU usage (%)
    pub cpu_usage_critical: f32,

    /// Pool connection thresholds
    pub pool_latency_critical: Duration,
    pub pool_rejection_rate_critical: f32,
}

impl Default for AlertThresholds {
    fn default() -> Self {
        Self {
            gpu_temperature_critical: 85.0,
            gpu_temperature_warning: 80.0,
            gpu_utilization_low: 70.0,
            gpu_utilization_critical: 98.0,
            hashrate_drop_critical: 20.0,
            hashrate_drop_warning: 10.0,
            power_consumption_critical: 400.0,
            memory_usage_critical: 95.0,
            memory_usage_warning: 85.0,
            cpu_usage_critical: 95.0,
            pool_latency_critical: Duration::from_millis(5000),
            pool_rejection_rate_critical: 5.0,
        }
    }
}

/// **Prometheus Configuration** (Cấu hình Prometheus)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PrometheusConfig {
    pub enabled: bool,
    pub bind_address: String,
    pub port: u16,
    pub metrics_path: String,
    pub scrape_interval: Duration,
}

impl Default for PrometheusConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            bind_address: "0.0.0.0".to_string(),
            port: 9090,
            metrics_path: "/metrics".to_string(),
            scrape_interval: Duration::from_secs(15),
        }
    }
}

/// **OpenTelemetry Configuration** (Cấu hình OpenTelemetry)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenTelemetryConfig {
    pub enabled: bool,
    pub endpoint: Option<String>,
    pub service_name: String,
    pub service_version: String,
    pub environment: String,
}

impl Default for OpenTelemetryConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            endpoint: None,
            service_name: "opus-gpu".to_string(),
            service_version: env!("CARGO_PKG_VERSION").to_string(),
            environment: "development".to_string(),
        }
    }
}

/// **Dashboard Configuration** (Cấu hình dashboard)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DashboardConfig {
    pub enabled: bool,
    pub grafana_url: Option<String>,
    pub auto_import_dashboards: bool,
    pub refresh_interval: Duration,
}

impl Default for DashboardConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            grafana_url: None,
            auto_import_dashboards: true,
            refresh_interval: Duration::from_secs(30),
        }
    }
}

/// **Recovery Configuration** (Cấu hình phục hồi)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecoveryConfig {
    pub enabled: bool,
    pub max_recovery_attempts: u32,
    pub recovery_cooldown: Duration,
    pub actions: Vec<RecoveryAction>,
}

impl Default for RecoveryConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            max_recovery_attempts: 3,
            recovery_cooldown: Duration::from_secs(60),
            actions: vec![
                RecoveryAction::RestartMining,
                RecoveryAction::SwitchPool,
                RecoveryAction::ReducePowerLimit,
                RecoveryAction::RestartSystem,
            ],
        }
    }
}

/// **Recovery Action** (Hành động phục hồi)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RecoveryAction {
    RestartMining,
    SwitchPool,
    ReducePowerLimit,
    RestartGpu { gpu_id: u32 },
    RestartSystem,
    NotifyAdmin,
    Custom { command: String, args: Vec<String> },
}

/// **GPU Monitoring Configuration** (Cấu hình giám sát GPU)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuMonitoringConfig {
    pub enabled: bool,
    pub nvidia_ml_enabled: bool,
    pub collect_detailed_metrics: bool,
    pub gpu_discovery_interval: Duration,
}

impl Default for GpuMonitoringConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            nvidia_ml_enabled: true,
            collect_detailed_metrics: true,
            gpu_discovery_interval: Duration::from_secs(30),
        }
    }
}

/// **System Monitoring Configuration** (Cấu hình giám sát hệ thống)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemMonitoringConfig {
    pub enabled: bool,
    pub collect_process_metrics: bool,
    pub collect_network_metrics: bool,
    pub collect_disk_metrics: bool,
}

impl Default for SystemMonitoringConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            collect_process_metrics: true,
            collect_network_metrics: true,
            collect_disk_metrics: true,
        }
    }
}

/// **Monitor Service** (Dịch vụ giám sát) - Main monitoring service
pub mod service {
    use super::*;
    use crate::{
        collectors::{MetricsCollector, GpuCollector, SystemCollector},
        health::HealthChecker,
        alerts::AlertManager,
        exporters::{PrometheusExporter, OpenTelemetryExporter},
        recovery::RecoveryManager,
    };
    use std::sync::Arc;
    use tokio::sync::RwLock;
    use parking_lot::Mutex;

    /// **Monitor Service** (Dịch vụ giám sát chính)
    pub struct MonitorService {
        config: MonitorConfig,
        collectors: Vec<Arc<dyn MetricsCollector>>,
        health_checker: Arc<HealthChecker>,
        alert_manager: Arc<AlertManager>,
        prometheus_exporter: Option<Arc<PrometheusExporter>>,
        opentelemetry_exporter: Option<Arc<OpenTelemetryExporter>>,
        recovery_manager: Arc<RecoveryManager>,
        running: Arc<RwLock<bool>>,
    }

    impl MonitorService {
        /// Create new monitoring service with configuration
        pub fn new(config: MonitorConfig) -> Result<Self> {
            let collectors: Vec<Arc<dyn MetricsCollector>> = vec![
                Arc::new(GpuCollector::new(config.gpu_monitoring.clone())?),
                Arc::new(SystemCollector::new(config.system_monitoring.clone())?),
            ];

            let health_checker = Arc::new(HealthChecker::new(
                config.health_check_interval,
                config.alerts.thresholds.clone(),
            ));

            let alert_manager = Arc::new(AlertManager::new(config.alerts.clone())?);

            let prometheus_exporter = if config.prometheus.enabled {
                Some(Arc::new(PrometheusExporter::new(config.prometheus.clone())?))
            } else {
                None
            };

            let opentelemetry_exporter = if config.opentelemetry.enabled {
                Some(Arc::new(OpenTelemetryExporter::new(config.opentelemetry.clone())?))
            } else {
                None
            };

            let recovery_manager = Arc::new(RecoveryManager::new(
                config.recovery.clone(),
                alert_manager.clone(),
            )?);

            Ok(Self {
                config,
                collectors,
                health_checker,
                alert_manager,
                prometheus_exporter,
                opentelemetry_exporter,
                recovery_manager,
                running: Arc::new(RwLock::new(false)),
            })
        }

        /// Start monitoring services
        pub async fn start(&self) -> Result<()> {
            let mut running = self.running.write().await;
            if *running {
                return Err(anyhow::anyhow!("Monitor service already running"));
            }

            tracing::info!("Starting OPUS-GPU monitoring service");

            // Start Prometheus exporter
            if let Some(prometheus) = &self.prometheus_exporter {
                prometheus.start().await?;
                tracing::info!("Prometheus exporter started on {}:{}",
                    self.config.prometheus.bind_address,
                    self.config.prometheus.port
                );
            }

            // Start OpenTelemetry exporter
            if let Some(otel) = &self.opentelemetry_exporter {
                otel.start().await?;
                tracing::info!("OpenTelemetry exporter started");
            }

            // Start health checker
            self.health_checker.start().await?;
            tracing::info!("Health checker started");

            // Start alert manager
            self.alert_manager.start().await?;
            tracing::info!("Alert manager started");

            // Start recovery manager
            self.recovery_manager.start().await?;
            tracing::info!("Recovery manager started");

            // Start metrics collection loop
            let collectors = self.collectors.clone();
            let collection_interval = self.config.collection_interval;
            let running_flag = self.running.clone();

            tokio::spawn(async move {
                let mut interval = tokio::time::interval(collection_interval);

                while *running_flag.read().await {
                    interval.tick().await;

                    // Collect metrics from all collectors
                    for collector in &collectors {
                        if let Err(e) = collector.collect().await {
                            tracing::warn!("Metrics collection failed: {}", e);
                        }
                    }
                }
            });

            *running = true;
            tracing::info!("OPUS-GPU monitoring service started successfully");
            Ok(())
        }

        /// Stop monitoring services
        pub async fn stop(&self) -> Result<()> {
            let mut running = self.running.write().await;
            if !*running {
                return Ok(());
            }

            tracing::info!("Stopping OPUS-GPU monitoring service");

            // Stop all services
            self.recovery_manager.stop().await?;
            self.alert_manager.stop().await?;
            self.health_checker.stop().await?;

            if let Some(otel) = &self.opentelemetry_exporter {
                otel.stop().await?;
            }

            if let Some(prometheus) = &self.prometheus_exporter {
                prometheus.stop().await?;
            }

            *running = false;
            tracing::info!("OPUS-GPU monitoring service stopped");
            Ok(())
        }

        /// Get current monitoring status
        pub async fn status(&self) -> MonitorStatus {
            let running = *self.running.read().await;
            let health_status = self.health_checker.get_overall_health().await;
            let active_alerts = self.alert_manager.get_active_alerts().await.len();

            MonitorStatus {
                running,
                health_status,
                active_alerts,
                uptime: chrono::Utc::now(), // Simplified for now
                collectors_count: self.collectors.len(),
                exporters_active: [
                    self.prometheus_exporter.as_ref().map(|_| "prometheus"),
                    self.opentelemetry_exporter.as_ref().map(|_| "opentelemetry"),
                ].iter().filter_map(|&x| x).count(),
            }
        }
    }
}

/// **Monitor Status** (Trạng thái giám sát) - Current monitoring service status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MonitorStatus {
    pub running: bool,
    pub health_status: crate::health::HealthStatus,
    pub active_alerts: usize,
    pub uptime: DateTime<Utc>,
    pub collectors_count: usize,
    pub exporters_active: usize,
}

pub type Result<T> = std::result::Result<T, MonitorError>;