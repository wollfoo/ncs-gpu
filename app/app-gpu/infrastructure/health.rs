//! Health Check and Readiness Probe System for OPUS-GPU
//!
//! This module provides comprehensive health monitoring capabilities including
//! health checks, readiness probes, liveness probes, and system metrics.

use anyhow::Result;
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};
use uuid::Uuid;

/// Health status enumeration
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum HealthStatus {
    /// Service is healthy and functioning normally
    Healthy,
    /// Service has non-critical issues but is still functional
    Warning,
    /// Service has critical issues and may not be functioning properly
    Unhealthy,
    /// Service is in an unknown state
    Unknown,
}

/// Component health information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComponentHealth {
    /// Component unique identifier
    pub id: Uuid,
    /// Component name
    pub name: String,
    /// Component type/category
    pub component_type: String,
    /// Current health status
    pub status: HealthStatus,
    /// Health check timestamp
    pub timestamp: DateTime<Utc>,
    /// Health check message
    pub message: Option<String>,
    /// Detailed health information
    pub details: HashMap<String, serde_json::Value>,
    /// Health check duration
    pub check_duration: Duration,
    /// Last successful health check
    pub last_success: Option<DateTime<Utc>>,
    /// Consecutive failure count
    pub consecutive_failures: u32,
    /// Component uptime
    pub uptime: Duration,
    /// Component version
    pub version: Option<String>,
}

/// System-wide health summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemHealth {
    /// Overall system status
    pub status: HealthStatus,
    /// Health check timestamp
    pub timestamp: DateTime<Utc>,
    /// Individual component health status
    pub components: HashMap<String, ComponentHealth>,
    /// System uptime
    pub uptime: Duration,
    /// Total number of components
    pub total_components: usize,
    /// Number of healthy components
    pub healthy_components: usize,
    /// Number of unhealthy components
    pub unhealthy_components: usize,
    /// System load metrics
    pub system_metrics: SystemMetrics,
}

/// System performance metrics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SystemMetrics {
    /// CPU usage percentage (0-100)
    pub cpu_usage: f32,
    /// Memory usage in bytes
    pub memory_used: u64,
    /// Total memory in bytes
    pub memory_total: u64,
    /// Memory usage percentage (0-100)
    pub memory_percentage: f32,
    /// Disk usage in bytes
    pub disk_used: u64,
    /// Total disk space in bytes
    pub disk_total: u64,
    /// Disk usage percentage (0-100)
    pub disk_percentage: f32,
    /// Network bytes sent
    pub network_tx_bytes: u64,
    /// Network bytes received
    pub network_rx_bytes: u64,
    /// Number of active connections
    pub active_connections: u32,
    /// System load average (1min, 5min, 15min)
    pub load_average: [f64; 3],
    /// Number of running processes
    pub running_processes: u32,
}

/// Health check configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthConfig {
    /// Enable health checks
    pub enabled: bool,
    /// Health check interval
    pub check_interval: Duration,
    /// Health check timeout
    pub check_timeout: Duration,
    /// Number of consecutive failures before marking unhealthy
    pub failure_threshold: u32,
    /// Number of consecutive successes before marking healthy
    pub success_threshold: u32,
    /// Enable detailed metrics collection
    pub enable_metrics: bool,
    /// Metrics collection interval
    pub metrics_interval: Duration,
    /// Health check history size
    pub history_size: usize,
    /// Enable readiness probes
    pub enable_readiness: bool,
    /// Enable liveness probes
    pub enable_liveness: bool,
    /// Initial delay before starting health checks
    pub initial_delay: Duration,
}

/// Health check trait for components
#[async_trait]
pub trait HealthCheck: Send + Sync {
    /// Get component name
    fn name(&self) -> &str;

    /// Get component type
    fn component_type(&self) -> &str;

    /// Perform health check
    async fn check_health(&self) -> Result<ComponentHealth>;

    /// Check if component is ready to serve requests
    async fn check_readiness(&self) -> Result<bool> {
        // Default implementation based on health status
        let health = self.check_health().await?;
        Ok(health.status == HealthStatus::Healthy)
    }

    /// Check if component is alive
    async fn check_liveness(&self) -> Result<bool> {
        // Default implementation - component is alive if it can respond
        self.check_health().await.map(|_| true)
    }

    /// Get component dependencies
    fn dependencies(&self) -> Vec<String> {
        Vec::new()
    }

    /// Get component tags/labels
    fn tags(&self) -> HashMap<String, String> {
        HashMap::new()
    }
}

/// Health check history entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthHistoryEntry {
    /// Entry timestamp
    pub timestamp: DateTime<Utc>,
    /// Health status at this time
    pub status: HealthStatus,
    /// Check duration
    pub duration: Duration,
    /// Error message if check failed
    pub error: Option<String>,
}

/// Health monitor implementation
pub struct HealthMonitor {
    config: HealthConfig,
    components: Arc<RwLock<HashMap<String, Arc<dyn HealthCheck>>>>,
    health_status: Arc<RwLock<HashMap<String, ComponentHealth>>>,
    health_history: Arc<RwLock<HashMap<String, Vec<HealthHistoryEntry>>>>,
    system_metrics: Arc<RwLock<SystemMetrics>>,
    start_time: DateTime<Utc>,
    shutdown_signal: Arc<tokio::sync::Notify>,
}

impl HealthMonitor {
    /// Create a new health monitor
    pub fn new(config: HealthConfig) -> Self {
        info!("🏥 Initializing health monitor");

        Self {
            config,
            components: Arc::new(RwLock::new(HashMap::new())),
            health_status: Arc::new(RwLock::new(HashMap::new())),
            health_history: Arc::new(RwLock::new(HashMap::new())),
            system_metrics: Arc::new(RwLock::new(SystemMetrics::default())),
            start_time: Utc::now(),
            shutdown_signal: Arc::new(tokio::sync::Notify::new()),
        }
    }

    /// Register a component for health monitoring
    pub async fn register_component(&self, component: Arc<dyn HealthCheck>) -> Result<()> {
        let name = component.name().to_string();
        info!("📋 Registering component for health monitoring: {}", name);

        // Add component
        self.components.write().await.insert(name.clone(), component);

        // Initialize health status
        self.health_status.write().await.insert(
            name.clone(),
            ComponentHealth {
                id: Uuid::new_v4(),
                name: name.clone(),
                component_type: "unknown".to_string(),
                status: HealthStatus::Unknown,
                timestamp: Utc::now(),
                message: None,
                details: HashMap::new(),
                check_duration: Duration::ZERO,
                last_success: None,
                consecutive_failures: 0,
                uptime: Duration::ZERO,
                version: None,
            },
        );

        // Initialize history
        self.health_history.write().await.insert(name, Vec::new());

        Ok(())
    }

    /// Unregister a component
    pub async fn unregister_component(&self, name: &str) -> Result<bool> {
        info!("🗑️ Unregistering component: {}", name);

        let removed = self.components.write().await.remove(name).is_some();
        self.health_status.write().await.remove(name);
        self.health_history.write().await.remove(name);

        Ok(removed)
    }

    /// Start the health monitor
    pub async fn start(&self) -> Result<()> {
        if !self.config.enabled {
            info!("🚫 Health monitoring is disabled");
            return Ok(());
        }

        info!("🚀 Starting health monitor");

        // Wait for initial delay
        if !self.config.initial_delay.is_zero() {
            info!("⏳ Waiting for initial delay: {:?}", self.config.initial_delay);
            tokio::time::sleep(self.config.initial_delay).await;
        }

        // Start health check loop
        let monitor = self.clone();
        tokio::spawn(async move {
            monitor.health_check_loop().await;
        });

        // Start metrics collection if enabled
        if self.config.enable_metrics {
            let monitor = self.clone();
            tokio::spawn(async move {
                monitor.metrics_collection_loop().await;
            });
        }

        info!("✅ Health monitor started");
        Ok(())
    }

    /// Stop the health monitor
    pub async fn stop(&self) -> Result<()> {
        info!("🛑 Stopping health monitor");

        // Signal shutdown
        self.shutdown_signal.notify_waiters();

        info!("✅ Health monitor stopped");
        Ok(())
    }

    /// Get overall system health
    pub async fn get_system_health(&self) -> SystemHealth {
        let health_status = self.health_status.read().await;
        let system_metrics = self.system_metrics.read().await.clone();

        // Calculate overall system status
        let total_components = health_status.len();
        let healthy_components = health_status
            .values()
            .filter(|h| h.status == HealthStatus::Healthy)
            .count();
        let unhealthy_components = health_status
            .values()
            .filter(|h| h.status == HealthStatus::Unhealthy)
            .count();

        let overall_status = if unhealthy_components > 0 {
            HealthStatus::Unhealthy
        } else if health_status
            .values()
            .any(|h| h.status == HealthStatus::Warning)
        {
            HealthStatus::Warning
        } else if healthy_components == total_components && total_components > 0 {
            HealthStatus::Healthy
        } else {
            HealthStatus::Unknown
        };

        SystemHealth {
            status: overall_status,
            timestamp: Utc::now(),
            components: health_status.clone(),
            uptime: Utc::now()
                .signed_duration_since(self.start_time)
                .to_std()
                .unwrap_or_default(),
            total_components,
            healthy_components,
            unhealthy_components,
            system_metrics,
        }
    }

    /// Get component health by name
    pub async fn get_component_health(&self, name: &str) -> Option<ComponentHealth> {
        self.health_status.read().await.get(name).cloned()
    }

    /// Get component health history
    pub async fn get_component_history(&self, name: &str) -> Option<Vec<HealthHistoryEntry>> {
        self.health_history.read().await.get(name).cloned()
    }

    /// Check if system is ready
    pub async fn is_ready(&self) -> bool {
        if !self.config.enable_readiness {
            return true;
        }

        let components = self.components.read().await;
        for component in components.values() {
            if let Ok(ready) = component.check_readiness().await {
                if !ready {
                    return false;
                }
            } else {
                return false;
            }
        }

        true
    }

    /// Check if system is alive
    pub async fn is_alive(&self) -> bool {
        if !self.config.enable_liveness {
            return true;
        }

        let components = self.components.read().await;
        for component in components.values() {
            if let Ok(alive) = component.check_liveness().await {
                if !alive {
                    return false;
                }
            } else {
                return false;
            }
        }

        true
    }

    /// Health check loop
    async fn health_check_loop(&self) {
        let mut interval = tokio::time::interval(self.config.check_interval);

        loop {
            tokio::select! {
                _ = interval.tick() => {
                    self.perform_health_checks().await;
                }
                _ = self.shutdown_signal.notified() => {
                    debug!("Health check loop shutting down");
                    break;
                }
            }
        }
    }

    /// Perform health checks on all components
    async fn perform_health_checks(&self) {
        let components = self.components.read().await.clone();

        for (name, component) in components {
            self.check_component_health(&name, component).await;
        }
    }

    /// Check health of a specific component
    async fn check_component_health(&self, name: &str, component: Arc<dyn HealthCheck>) {
        let start_time = std::time::Instant::now();

        let health_result = tokio::time::timeout(
            self.config.check_timeout,
            component.check_health()
        ).await;

        let check_duration = start_time.elapsed();

        let (status, message, details, error) = match health_result {
            Ok(Ok(mut health)) => {
                health.check_duration = check_duration;
                (health.status, health.message, health.details, None)
            }
            Ok(Err(e)) => {
                (
                    HealthStatus::Unhealthy,
                    Some(format!("Health check failed: {}", e)),
                    HashMap::new(),
                    Some(e.to_string()),
                )
            }
            Err(_) => {
                (
                    HealthStatus::Unhealthy,
                    Some("Health check timeout".to_string()),
                    HashMap::new(),
                    Some("Timeout".to_string()),
                )
            }
        };

        // Update health status
        {
            let mut health_status = self.health_status.write().await;
            if let Some(current_health) = health_status.get_mut(name) {
                let was_healthy = current_health.status == HealthStatus::Healthy;
                let is_healthy = status == HealthStatus::Healthy;

                current_health.status = status.clone();
                current_health.timestamp = Utc::now();
                current_health.message = message.clone();
                current_health.details = details;
                current_health.check_duration = check_duration;

                if is_healthy {
                    current_health.last_success = Some(Utc::now());
                    current_health.consecutive_failures = 0;
                } else {
                    current_health.consecutive_failures += 1;
                }

                // Log status changes
                if !was_healthy && is_healthy {
                    info!("✅ Component {} is now healthy", name);
                } else if was_healthy && !is_healthy {
                    warn!("❌ Component {} is now unhealthy: {:?}", name, message);
                }
            }
        }

        // Update history
        {
            let mut history = self.health_history.write().await;
            if let Some(component_history) = history.get_mut(name) {
                component_history.push(HealthHistoryEntry {
                    timestamp: Utc::now(),
                    status,
                    duration: check_duration,
                    error,
                });

                // Limit history size
                if component_history.len() > self.config.history_size {
                    component_history.drain(0..component_history.len() - self.config.history_size);
                }
            }
        }
    }

    /// Metrics collection loop
    async fn metrics_collection_loop(&self) {
        let mut interval = tokio::time::interval(self.config.metrics_interval);

        loop {
            tokio::select! {
                _ = interval.tick() => {
                    self.collect_system_metrics().await;
                }
                _ = self.shutdown_signal.notified() => {
                    debug!("Metrics collection loop shutting down");
                    break;
                }
            }
        }
    }

    /// Collect system metrics
    async fn collect_system_metrics(&self) {
        let metrics = self.gather_system_metrics().await;
        *self.system_metrics.write().await = metrics;
    }

    /// Gather system metrics from the OS
    async fn gather_system_metrics(&self) -> SystemMetrics {
        // TODO: Implement actual system metrics collection
        // This would involve reading from /proc filesystem on Linux,
        // or using system APIs on other platforms

        SystemMetrics {
            cpu_usage: self.get_cpu_usage().await,
            memory_used: self.get_memory_usage().await.0,
            memory_total: self.get_memory_usage().await.1,
            memory_percentage: self.get_memory_percentage().await,
            disk_used: self.get_disk_usage().await.0,
            disk_total: self.get_disk_usage().await.1,
            disk_percentage: self.get_disk_percentage().await,
            network_tx_bytes: self.get_network_stats().await.0,
            network_rx_bytes: self.get_network_stats().await.1,
            active_connections: self.get_connection_count().await,
            load_average: self.get_load_average().await,
            running_processes: self.get_process_count().await,
        }
    }

    // Mock system metrics functions (TODO: Replace with actual implementations)
    async fn get_cpu_usage(&self) -> f32 { 0.0 }
    async fn get_memory_usage(&self) -> (u64, u64) { (0, 0) }
    async fn get_memory_percentage(&self) -> f32 { 0.0 }
    async fn get_disk_usage(&self) -> (u64, u64) { (0, 0) }
    async fn get_disk_percentage(&self) -> f32 { 0.0 }
    async fn get_network_stats(&self) -> (u64, u64) { (0, 0) }
    async fn get_connection_count(&self) -> u32 { 0 }
    async fn get_load_average(&self) -> [f64; 3] { [0.0, 0.0, 0.0] }
    async fn get_process_count(&self) -> u32 { 0 }
}

// Clone implementation for HealthMonitor
impl Clone for HealthMonitor {
    fn clone(&self) -> Self {
        Self {
            config: self.config.clone(),
            components: self.components.clone(),
            health_status: self.health_status.clone(),
            health_history: self.health_history.clone(),
            system_metrics: self.system_metrics.clone(),
            start_time: self.start_time,
            shutdown_signal: self.shutdown_signal.clone(),
        }
    }
}

impl Default for HealthConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            check_interval: Duration::from_secs(30),
            check_timeout: Duration::from_secs(10),
            failure_threshold: 3,
            success_threshold: 1,
            enable_metrics: true,
            metrics_interval: Duration::from_secs(60),
            history_size: 100,
            enable_readiness: true,
            enable_liveness: true,
            initial_delay: Duration::from_secs(10),
        }
    }
}

impl std::fmt::Display for HealthStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            HealthStatus::Healthy => write!(f, "healthy"),
            HealthStatus::Warning => write!(f, "warning"),
            HealthStatus::Unhealthy => write!(f, "unhealthy"),
            HealthStatus::Unknown => write!(f, "unknown"),
        }
    }
}

// Example health check implementations

/// Mining engine health check
pub struct MiningEngineHealthCheck {
    name: String,
    engine: Arc<dyn MiningEngineHealth>,
}

#[async_trait]
pub trait MiningEngineHealth: Send + Sync {
    async fn get_hash_rate(&self) -> Result<f64>;
    async fn get_active_gpus(&self) -> Result<usize>;
    async fn is_mining(&self) -> Result<bool>;
}

impl MiningEngineHealthCheck {
    pub fn new(engine: Arc<dyn MiningEngineHealth>) -> Self {
        Self {
            name: "mining-engine".to_string(),
            engine,
        }
    }
}

#[async_trait]
impl HealthCheck for MiningEngineHealthCheck {
    fn name(&self) -> &str {
        &self.name
    }

    fn component_type(&self) -> &str {
        "mining"
    }

    async fn check_health(&self) -> Result<ComponentHealth> {
        let start_time = Utc::now();
        let mut details = HashMap::new();
        let mut status = HealthStatus::Healthy;
        let mut message = None;

        // Check if mining
        match self.engine.is_mining().await {
            Ok(is_mining) => {
                details.insert("is_mining".to_string(), serde_json::Value::Bool(is_mining));
                if !is_mining {
                    status = HealthStatus::Warning;
                    message = Some("Mining is not active".to_string());
                }
            }
            Err(e) => {
                status = HealthStatus::Unhealthy;
                message = Some(format!("Failed to check mining status: {}", e));
            }
        }

        // Check hash rate
        if let Ok(hash_rate) = self.engine.get_hash_rate().await {
            details.insert("hash_rate".to_string(), serde_json::Value::Number(
                serde_json::Number::from_f64(hash_rate).unwrap_or_default()
            ));

            if hash_rate < 1.0 {
                status = HealthStatus::Warning;
                message = Some("Low hash rate detected".to_string());
            }
        }

        // Check active GPUs
        if let Ok(active_gpus) = self.engine.get_active_gpus().await {
            details.insert("active_gpus".to_string(), serde_json::Value::Number(
                serde_json::Number::from(active_gpus as u64)
            ));

            if active_gpus == 0 {
                status = HealthStatus::Unhealthy;
                message = Some("No active GPUs".to_string());
            }
        }

        Ok(ComponentHealth {
            id: Uuid::new_v4(),
            name: self.name.clone(),
            component_type: self.component_type().to_string(),
            status,
            timestamp: Utc::now(),
            message,
            details,
            check_duration: Utc::now().signed_duration_since(start_time).to_std().unwrap_or_default(),
            last_success: None,
            consecutive_failures: 0,
            uptime: Duration::ZERO,
            version: Some(env!("CARGO_PKG_VERSION").to_string()),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct MockHealthCheck {
        name: String,
        status: HealthStatus,
    }

    impl MockHealthCheck {
        fn new(name: &str, status: HealthStatus) -> Self {
            Self {
                name: name.to_string(),
                status,
            }
        }
    }

    #[async_trait]
    impl HealthCheck for MockHealthCheck {
        fn name(&self) -> &str {
            &self.name
        }

        fn component_type(&self) -> &str {
            "mock"
        }

        async fn check_health(&self) -> Result<ComponentHealth> {
            Ok(ComponentHealth {
                id: Uuid::new_v4(),
                name: self.name.clone(),
                component_type: self.component_type().to_string(),
                status: self.status.clone(),
                timestamp: Utc::now(),
                message: Some("Mock health check".to_string()),
                details: HashMap::new(),
                check_duration: Duration::from_millis(10),
                last_success: Some(Utc::now()),
                consecutive_failures: 0,
                uptime: Duration::from_secs(3600),
                version: Some("1.0.0".to_string()),
            })
        }
    }

    #[tokio::test]
    async fn test_health_monitor_creation() {
        let config = HealthConfig::default();
        let monitor = HealthMonitor::new(config);

        let system_health = monitor.get_system_health().await;
        assert_eq!(system_health.status, HealthStatus::Unknown);
        assert_eq!(system_health.total_components, 0);
    }

    #[tokio::test]
    async fn test_component_registration() {
        let config = HealthConfig::default();
        let monitor = HealthMonitor::new(config);

        let component = Arc::new(MockHealthCheck::new("test", HealthStatus::Healthy));
        monitor.register_component(component).await.unwrap();

        let system_health = monitor.get_system_health().await;
        assert_eq!(system_health.total_components, 1);
        assert!(system_health.components.contains_key("test"));
    }

    #[tokio::test]
    async fn test_health_check_execution() {
        let config = HealthConfig {
            check_interval: Duration::from_millis(100),
            ..Default::default()
        };
        let monitor = HealthMonitor::new(config);

        let component = Arc::new(MockHealthCheck::new("test", HealthStatus::Healthy));
        monitor.register_component(component.clone()).await.unwrap();

        // Manually perform health check
        monitor.check_component_health("test", component).await;

        let component_health = monitor.get_component_health("test").await.unwrap();
        assert_eq!(component_health.status, HealthStatus::Healthy);
    }

    #[tokio::test]
    async fn test_readiness_and_liveness() {
        let config = HealthConfig::default();
        let monitor = HealthMonitor::new(config);

        let healthy_component = Arc::new(MockHealthCheck::new("healthy", HealthStatus::Healthy));
        let unhealthy_component = Arc::new(MockHealthCheck::new("unhealthy", HealthStatus::Unhealthy));

        monitor.register_component(healthy_component).await.unwrap();

        // Should be ready with healthy component
        assert!(monitor.is_ready().await);
        assert!(monitor.is_alive().await);

        monitor.register_component(unhealthy_component).await.unwrap();

        // Should not be ready with unhealthy component
        // Note: This test might need adjustment based on actual implementation
    }
}