//! **Health Monitoring** (Giám sát sức khỏe)
//!
//! Component health checks, status tracking, and diagnostic reporting.

use crate::{MonitorError, Result, metrics::{GpuMetrics, SystemMetrics, PoolMetrics}, AlertThresholds};
use async_trait::async_trait;
use chrono::{DateTime, Utc, Duration};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use parking_lot::Mutex;

/// **Health Status** (Trạng thái sức khỏe) - Overall health status enum
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum HealthStatus {
    /// All systems operating normally
    Healthy,
    /// Minor issues detected, system still operational
    Warning,
    /// Critical issues detected, system may be degraded
    Critical,
    /// System is down or unresponsive
    Down,
    /// Health status unknown or not yet determined
    Unknown,
}

impl HealthStatus {
    /// Check if health status indicates a problem
    pub fn is_problematic(&self) -> bool {
        matches!(self, Self::Critical | Self::Down)
    }

    /// Check if health status requires attention
    pub fn needs_attention(&self) -> bool {
        matches!(self, Self::Warning | Self::Critical | Self::Down)
    }

    /// Get numeric severity score (higher = worse)
    pub fn severity_score(&self) -> u8 {
        match self {
            Self::Healthy => 0,
            Self::Unknown => 1,
            Self::Warning => 2,
            Self::Critical => 3,
            Self::Down => 4,
        }
    }

    /// Combine multiple health statuses (worst wins)
    pub fn combine(statuses: &[HealthStatus]) -> HealthStatus {
        statuses.iter()
            .max_by_key(|status| status.severity_score())
            .copied()
            .unwrap_or(Self::Unknown)
    }
}

impl std::fmt::Display for HealthStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Healthy => write!(f, "Healthy"),
            Self::Warning => write!(f, "Warning"),
            Self::Critical => write!(f, "Critical"),
            Self::Down => write!(f, "Down"),
            Self::Unknown => write!(f, "Unknown"),
        }
    }
}

/// **Component Health** (Sức khỏe thành phần) - Individual component health info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComponentHealth {
    pub component_id: String,
    pub component_type: ComponentType,
    pub status: HealthStatus,
    pub last_check: DateTime<Utc>,
    pub uptime: std::time::Duration,
    pub error_count: u64,
    pub warning_count: u64,
    pub last_error: Option<String>,
    pub last_warning: Option<String>,
    pub diagnostics: HashMap<String, String>,
}

impl ComponentHealth {
    /// Create new component health
    pub fn new(component_id: String, component_type: ComponentType) -> Self {
        Self {
            component_id,
            component_type,
            status: HealthStatus::Unknown,
            last_check: Utc::now(),
            uptime: std::time::Duration::from_secs(0),
            error_count: 0,
            warning_count: 0,
            last_error: None,
            last_warning: None,
            diagnostics: HashMap::new(),
        }
    }

    /// Update health status
    pub fn update_status(&mut self, status: HealthStatus) {
        self.status = status;
        self.last_check = Utc::now();
    }

    /// Record error
    pub fn record_error(&mut self, error: String) {
        self.error_count += 1;
        self.last_error = Some(error);
        self.status = HealthStatus::Critical;
        self.last_check = Utc::now();
    }

    /// Record warning
    pub fn record_warning(&mut self, warning: String) {
        self.warning_count += 1;
        self.last_warning = Some(warning);
        if self.status == HealthStatus::Healthy {
            self.status = HealthStatus::Warning;
        }
        self.last_check = Utc::now();
    }

    /// Add diagnostic information
    pub fn add_diagnostic(&mut self, key: String, value: String) {
        self.diagnostics.insert(key, value);
        self.last_check = Utc::now();
    }

    /// Check if component is stale (hasn't been updated recently)
    pub fn is_stale(&self, max_age: std::time::Duration) -> bool {
        let now = Utc::now();
        let age = now.signed_duration_since(self.last_check);
        age.to_std().unwrap_or(std::time::Duration::MAX) > max_age
    }
}

/// **Component Type** (Loại thành phần) - Different types of monitored components
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ComponentType {
    Gpu,
    Pool,
    System,
    Network,
    Storage,
    Mining,
    Wallet,
    Api,
}

impl std::fmt::Display for ComponentType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Gpu => write!(f, "GPU"),
            Self::Pool => write!(f, "Pool"),
            Self::System => write!(f, "System"),
            Self::Network => write!(f, "Network"),
            Self::Storage => write!(f, "Storage"),
            Self::Mining => write!(f, "Mining"),
            Self::Wallet => write!(f, "Wallet"),
            Self::Api => write!(f, "API"),
        }
    }
}

/// **Health Check** (Kiểm tra sức khỏe) - Trait for health check implementations
#[async_trait]
pub trait HealthCheck: Send + Sync {
    /// Perform health check for component
    async fn check_health(&self) -> Result<ComponentHealth>;

    /// Get component identifier
    fn component_id(&self) -> String;

    /// Get component type
    fn component_type(&self) -> ComponentType;

    /// Get check interval
    fn check_interval(&self) -> std::time::Duration {
        std::time::Duration::from_secs(30)
    }
}

/// **GPU Health Check** (Kiểm tra sức khỏe GPU)
pub struct GpuHealthCheck {
    gpu_id: u32,
    thresholds: AlertThresholds,
    last_metrics: Arc<RwLock<Option<GpuMetrics>>>,
}

impl GpuHealthCheck {
    /// Create new GPU health check
    pub fn new(gpu_id: u32, thresholds: AlertThresholds) -> Self {
        Self {
            gpu_id,
            thresholds,
            last_metrics: Arc::new(RwLock::new(None)),
        }
    }

    /// Update with latest GPU metrics
    pub async fn update_metrics(&self, metrics: GpuMetrics) {
        let mut last_metrics = self.last_metrics.write().await;
        *last_metrics = Some(metrics);
    }
}

#[async_trait]
impl HealthCheck for GpuHealthCheck {
    async fn check_health(&self) -> Result<ComponentHealth> {
        let metrics = self.last_metrics.read().await;
        let mut health = ComponentHealth::new(
            format!("gpu_{}", self.gpu_id),
            ComponentType::Gpu,
        );

        match metrics.as_ref() {
            Some(metrics) => {
                // Check temperature
                let mut status = HealthStatus::Healthy;
                let mut issues = Vec::new();

                if metrics.temperature_current >= self.thresholds.gpu_temperature_critical {
                    status = HealthStatus::Critical;
                    issues.push(format!("Critical temperature: {:.1}°C", metrics.temperature_current));
                } else if metrics.temperature_current >= self.thresholds.gpu_temperature_warning {
                    status = HealthStatus::Warning;
                    issues.push(format!("High temperature: {:.1}°C", metrics.temperature_current));
                }

                // Check utilization
                if metrics.gpu_utilization < self.thresholds.gpu_utilization_low {
                    if status == HealthStatus::Healthy {
                        status = HealthStatus::Warning;
                    }
                    issues.push(format!("Low GPU utilization: {:.1}%", metrics.gpu_utilization));
                } else if metrics.gpu_utilization > self.thresholds.gpu_utilization_critical {
                    status = HealthStatus::Critical;
                    issues.push(format!("Critical GPU utilization: {:.1}%", metrics.gpu_utilization));
                }

                // Check hashrate drop
                let hashrate_drop = (metrics.hashrate_average - metrics.hashrate).abs();
                let hashrate_drop_percent = if metrics.hashrate_average > 0.0 {
                    (hashrate_drop / metrics.hashrate_average) * 100.0
                } else {
                    0.0
                };

                if hashrate_drop_percent >= self.thresholds.hashrate_drop_critical {
                    status = HealthStatus::Critical;
                    issues.push(format!("Critical hashrate drop: {:.1}%", hashrate_drop_percent));
                } else if hashrate_drop_percent >= self.thresholds.hashrate_drop_warning {
                    if status == HealthStatus::Healthy {
                        status = HealthStatus::Warning;
                    }
                    issues.push(format!("Hashrate drop: {:.1}%", hashrate_drop_percent));
                }

                // Check power consumption
                if metrics.power_draw >= self.thresholds.power_consumption_critical {
                    status = HealthStatus::Critical;
                    issues.push(format!("Critical power draw: {:.1}W", metrics.power_draw));
                }

                // Check memory usage
                let memory_usage_percent = if metrics.memory_total > 0 {
                    (metrics.memory_used as f32 / metrics.memory_total as f32) * 100.0
                } else {
                    0.0
                };

                if memory_usage_percent >= self.thresholds.memory_usage_critical {
                    status = HealthStatus::Critical;
                    issues.push(format!("Critical memory usage: {:.1}%", memory_usage_percent));
                } else if memory_usage_percent >= self.thresholds.memory_usage_warning {
                    if status == HealthStatus::Healthy {
                        status = HealthStatus::Warning;
                    }
                    issues.push(format!("High memory usage: {:.1}%", memory_usage_percent));
                }

                // Check thermal throttling
                if metrics.temperature_throttling {
                    status = HealthStatus::Critical;
                    issues.push("GPU is thermal throttling".to_string());
                }

                health.update_status(status);

                // Add diagnostics
                health.add_diagnostic("temperature".to_string(), format!("{:.1}°C", metrics.temperature_current));
                health.add_diagnostic("utilization".to_string(), format!("{:.1}%", metrics.gpu_utilization));
                health.add_diagnostic("hashrate".to_string(), format!("{:.2} MH/s", metrics.hashrate));
                health.add_diagnostic("power_draw".to_string(), format!("{:.1}W", metrics.power_draw));
                health.add_diagnostic("memory_usage".to_string(), format!("{:.1}%", memory_usage_percent));
                health.add_diagnostic("rejection_rate".to_string(), format!("{:.2}%", metrics.rejection_rate()));

                // Record issues
                if !issues.is_empty() {
                    let issue_text = issues.join("; ");
                    if status == HealthStatus::Critical {
                        health.record_error(issue_text);
                    } else {
                        health.record_warning(issue_text);
                    }
                }
            }
            None => {
                health.update_status(HealthStatus::Down);
                health.record_error("No GPU metrics available".to_string());
            }
        }

        Ok(health)
    }

    fn component_id(&self) -> String {
        format!("gpu_{}", self.gpu_id)
    }

    fn component_type(&self) -> ComponentType {
        ComponentType::Gpu
    }

    fn check_interval(&self) -> std::time::Duration {
        std::time::Duration::from_secs(15)
    }
}

/// **Pool Health Check** (Kiểm tra sức khỏe pool)
pub struct PoolHealthCheck {
    pool_name: String,
    thresholds: AlertThresholds,
    last_metrics: Arc<RwLock<Option<PoolMetrics>>>,
}

impl PoolHealthCheck {
    pub fn new(pool_name: String, thresholds: AlertThresholds) -> Self {
        Self {
            pool_name,
            thresholds,
            last_metrics: Arc::new(RwLock::new(None)),
        }
    }

    pub async fn update_metrics(&self, metrics: PoolMetrics) {
        let mut last_metrics = self.last_metrics.write().await;
        *last_metrics = Some(metrics);
    }
}

#[async_trait]
impl HealthCheck for PoolHealthCheck {
    async fn check_health(&self) -> Result<ComponentHealth> {
        let metrics = self.last_metrics.read().await;
        let mut health = ComponentHealth::new(
            format!("pool_{}", self.pool_name),
            ComponentType::Pool,
        );

        match metrics.as_ref() {
            Some(metrics) => {
                let mut status = HealthStatus::Healthy;
                let mut issues = Vec::new();

                // Check connection status
                if !metrics.connected {
                    status = HealthStatus::Critical;
                    issues.push("Pool not connected".to_string());
                }

                // Check latency
                let latency_duration = std::time::Duration::from_millis(metrics.latency_ms as u64);
                if latency_duration >= self.thresholds.pool_latency_critical {
                    status = HealthStatus::Critical;
                    issues.push(format!("Critical pool latency: {}ms", metrics.latency_ms));
                } else if latency_duration >= self.thresholds.pool_latency_critical / 2 {
                    if status == HealthStatus::Healthy {
                        status = HealthStatus::Warning;
                    }
                    issues.push(format!("High pool latency: {}ms", metrics.latency_ms));
                }

                // Check rejection rate
                let rejection_rate = metrics.rejection_rate();
                if rejection_rate >= self.thresholds.pool_rejection_rate_critical {
                    status = HealthStatus::Critical;
                    issues.push(format!("Critical rejection rate: {:.2}%", rejection_rate));
                } else if rejection_rate >= self.thresholds.pool_rejection_rate_critical / 2.0 {
                    if status == HealthStatus::Healthy {
                        status = HealthStatus::Warning;
                    }
                    issues.push(format!("High rejection rate: {:.2}%", rejection_rate));
                }

                health.update_status(status);

                // Add diagnostics
                health.add_diagnostic("connected".to_string(), metrics.connected.to_string());
                health.add_diagnostic("latency".to_string(), format!("{}ms", metrics.latency_ms));
                health.add_diagnostic("rejection_rate".to_string(), format!("{:.2}%", rejection_rate));
                health.add_diagnostic("acceptance_rate".to_string(), format!("{:.2}%", metrics.acceptance_rate()));
                health.add_diagnostic("hashrate_reported".to_string(), format!("{:.2} MH/s", metrics.hashrate_reported));
                health.add_diagnostic("efficiency".to_string(), format!("{:.2}%", metrics.efficiency));

                // Record issues
                if !issues.is_empty() {
                    let issue_text = issues.join("; ");
                    if status == HealthStatus::Critical {
                        health.record_error(issue_text);
                    } else {
                        health.record_warning(issue_text);
                    }
                }
            }
            None => {
                health.update_status(HealthStatus::Down);
                health.record_error("No pool metrics available".to_string());
            }
        }

        Ok(health)
    }

    fn component_id(&self) -> String {
        format!("pool_{}", self.pool_name)
    }

    fn component_type(&self) -> ComponentType {
        ComponentType::Pool
    }

    fn check_interval(&self) -> std::time::Duration {
        std::time::Duration::from_secs(20)
    }
}

/// **System Health Check** (Kiểm tra sức khỏe hệ thống)
pub struct SystemHealthCheck {
    thresholds: AlertThresholds,
    last_metrics: Arc<RwLock<Option<SystemMetrics>>>,
}

impl SystemHealthCheck {
    pub fn new(thresholds: AlertThresholds) -> Self {
        Self {
            thresholds,
            last_metrics: Arc::new(RwLock::new(None)),
        }
    }

    pub async fn update_metrics(&self, metrics: SystemMetrics) {
        let mut last_metrics = self.last_metrics.write().await;
        *last_metrics = Some(metrics);
    }
}

#[async_trait]
impl HealthCheck for SystemHealthCheck {
    async fn check_health(&self) -> Result<ComponentHealth> {
        let metrics = self.last_metrics.read().await;
        let mut health = ComponentHealth::new(
            "system".to_string(),
            ComponentType::System,
        );

        match metrics.as_ref() {
            Some(metrics) => {
                let mut status = HealthStatus::Healthy;
                let mut issues = Vec::new();

                // Check CPU usage
                if metrics.cpu_usage_percent >= self.thresholds.cpu_usage_critical {
                    status = HealthStatus::Critical;
                    issues.push(format!("Critical CPU usage: {:.1}%", metrics.cpu_usage_percent));
                } else if metrics.cpu_usage_percent >= 80.0 {
                    if status == HealthStatus::Healthy {
                        status = HealthStatus::Warning;
                    }
                    issues.push(format!("High CPU usage: {:.1}%", metrics.cpu_usage_percent));
                }

                // Check memory usage
                let memory_usage_percent = metrics.memory_usage_percent();
                if memory_usage_percent >= self.thresholds.memory_usage_critical {
                    status = HealthStatus::Critical;
                    issues.push(format!("Critical memory usage: {:.1}%", memory_usage_percent));
                } else if memory_usage_percent >= self.thresholds.memory_usage_warning {
                    if status == HealthStatus::Healthy {
                        status = HealthStatus::Warning;
                    }
                    issues.push(format!("High memory usage: {:.1}%", memory_usage_percent));
                }

                // Check disk usage
                for (device, usage) in &metrics.disk_usage {
                    if usage.usage_percent >= 95.0 {
                        status = HealthStatus::Critical;
                        issues.push(format!("Critical disk usage on {}: {:.1}%", device, usage.usage_percent));
                    } else if usage.usage_percent >= 85.0 {
                        if status == HealthStatus::Healthy {
                            status = HealthStatus::Warning;
                        }
                        issues.push(format!("High disk usage on {}: {:.1}%", device, usage.usage_percent));
                    }
                }

                health.update_status(status);

                // Add diagnostics
                health.add_diagnostic("cpu_usage".to_string(), format!("{:.1}%", metrics.cpu_usage_percent));
                health.add_diagnostic("memory_usage".to_string(), format!("{:.1}%", memory_usage_percent));
                health.add_diagnostic("load_1m".to_string(), format!("{:.2}", metrics.load_average_1m));
                health.add_diagnostic("load_5m".to_string(), format!("{:.2}", metrics.load_average_5m));
                health.add_diagnostic("uptime".to_string(), format!("{}s", metrics.uptime_seconds));

                // Record issues
                if !issues.is_empty() {
                    let issue_text = issues.join("; ");
                    if status == HealthStatus::Critical {
                        health.record_error(issue_text);
                    } else {
                        health.record_warning(issue_text);
                    }
                }
            }
            None => {
                health.update_status(HealthStatus::Down);
                health.record_error("No system metrics available".to_string());
            }
        }

        Ok(health)
    }

    fn component_id(&self) -> String {
        "system".to_string()
    }

    fn component_type(&self) -> ComponentType {
        ComponentType::System
    }

    fn check_interval(&self) -> std::time::Duration {
        std::time::Duration::from_secs(30)
    }
}

/// **Health Checker** (Trình kiểm tra sức khỏe) - Main health monitoring coordinator
pub struct HealthChecker {
    checks: Arc<RwLock<Vec<Arc<dyn HealthCheck>>>>,
    health_states: Arc<RwLock<HashMap<String, ComponentHealth>>>,
    check_interval: std::time::Duration,
    thresholds: AlertThresholds,
    running: Arc<RwLock<bool>>,
}

impl HealthChecker {
    /// Create new health checker
    pub fn new(check_interval: std::time::Duration, thresholds: AlertThresholds) -> Self {
        Self {
            checks: Arc::new(RwLock::new(Vec::new())),
            health_states: Arc::new(RwLock::new(HashMap::new())),
            check_interval,
            thresholds,
            running: Arc::new(RwLock::new(false)),
        }
    }

    /// Register a health check
    pub async fn register_check(&self, check: Arc<dyn HealthCheck>) -> Result<()> {
        let mut checks = self.checks.write().await;
        checks.push(check);
        Ok(())
    }

    /// Start health checking
    pub async fn start(&self) -> Result<()> {
        let mut running = self.running.write().await;
        if *running {
            return Ok(());
        }

        tracing::info!("Starting health checker");

        let checks = self.checks.clone();
        let health_states = self.health_states.clone();
        let running_flag = self.running.clone();
        let check_interval = self.check_interval;

        tokio::spawn(async move {
            while *running_flag.read().await {
                let checks_snapshot = checks.read().await.clone();

                for check in checks_snapshot {
                    match check.check_health().await {
                        Ok(health) => {
                            let component_id = health.component_id.clone();
                            let mut states = health_states.write().await;
                            states.insert(component_id, health);
                        }
                        Err(e) => {
                            tracing::error!("Health check failed for {}: {}", check.component_id(), e);
                        }
                    }
                }

                tokio::time::sleep(check_interval).await;
            }
        });

        *running = true;
        tracing::info!("Health checker started");
        Ok(())
    }

    /// Stop health checking
    pub async fn stop(&self) -> Result<()> {
        let mut running = self.running.write().await;
        *running = false;
        tracing::info!("Health checker stopped");
        Ok(())
    }

    /// Get overall health status
    pub async fn get_overall_health(&self) -> HealthStatus {
        let states = self.health_states.read().await;
        let statuses: Vec<HealthStatus> = states.values().map(|h| h.status).collect();
        HealthStatus::combine(&statuses)
    }

    /// Get health status for specific component
    pub async fn get_component_health(&self, component_id: &str) -> Option<ComponentHealth> {
        let states = self.health_states.read().await;
        states.get(component_id).cloned()
    }

    /// Get all component health states
    pub async fn get_all_health(&self) -> HashMap<String, ComponentHealth> {
        self.health_states.read().await.clone()
    }

    /// Get unhealthy components
    pub async fn get_unhealthy_components(&self) -> Vec<ComponentHealth> {
        let states = self.health_states.read().await;
        states.values()
            .filter(|h| h.status.needs_attention())
            .cloned()
            .collect()
    }
}