//! Health check module for system monitoring
//! 
//! Provides liveness, readiness probes and dependency health checks

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use anyhow::{Result, Context};

/// Health status enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum HealthStatus {
    /// Service is healthy and ready
    Healthy,
    /// Service is degraded but operational
    Degraded,
    /// Service is unhealthy
    Unhealthy,
    /// Service status is unknown
    Unknown,
}

impl HealthStatus {
    /// Check if status is healthy or degraded (operational)
    pub fn is_operational(&self) -> bool {
        matches!(self, HealthStatus::Healthy | HealthStatus::Degraded)
    }
}

/// Health check result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthCheckResult {
    /// Component name
    pub component: String,
    
    /// Health status
    pub status: HealthStatus,
    
    /// Check timestamp
    pub timestamp: u64,
    
    /// Optional message
    pub message: Option<String>,
    
    /// Additional details
    pub details: HashMap<String, serde_json::Value>,
    
    /// Time taken for check (ms)
    pub duration_ms: u64,
}

/// Overall system health
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemHealth {
    /// Overall system status
    pub status: HealthStatus,
    
    /// System version
    pub version: String,
    
    /// System uptime in seconds
    pub uptime_seconds: u64,
    
    /// Individual component health
    pub components: Vec<HealthCheckResult>,
    
    /// System metrics
    pub metrics: SystemMetrics,
    
    /// Last check timestamp
    pub timestamp: u64,
}

/// System metrics for health monitoring
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemMetrics {
    /// CPU usage percentage
    pub cpu_usage: f32,
    
    /// Memory usage in MB
    pub memory_used_mb: u64,
    
    /// Memory total in MB
    pub memory_total_mb: u64,
    
    /// Disk usage percentage
    pub disk_usage: f32,
    
    /// Active connections
    pub active_connections: u32,
    
    /// Request rate (req/sec)
    pub request_rate: f32,
    
    /// Error rate (errors/sec)
    pub error_rate: f32,
    
    /// GPU count
    pub gpu_count: usize,
    
    /// Available GPUs
    pub gpus_available: usize,
}

/// Health check trait
#[async_trait]
pub trait HealthCheck: Send + Sync {
    /// Perform health check
    async fn check(&self) -> HealthCheckResult;
    
    /// Get component name
    fn component_name(&self) -> &str;
}

/// GPU health checker
pub struct GpuHealthChecker {
    device_id: usize,
    name: String,
}

impl GpuHealthChecker {
    pub fn new(device_id: usize, name: String) -> Self {
        Self { device_id, name }
    }
}

#[async_trait]
impl HealthCheck for GpuHealthChecker {
    async fn check(&self) -> HealthCheckResult {
        let start = SystemTime::now();
        
        // In real implementation, would check actual GPU status
        // For now, simulate health check
        let (status, message, mut details) = match self.device_id {
            0 => {
                let mut details = HashMap::new();
                details.insert("utilization".to_string(), serde_json::json!(85.5));
                details.insert("temperature".to_string(), serde_json::json!(72));
                details.insert("memory_used_mb".to_string(), serde_json::json!(8192));
                details.insert("memory_total_mb".to_string(), serde_json::json!(24576));
                (HealthStatus::Healthy, None, details)
            }
            _ => {
                let details = HashMap::new();
                (HealthStatus::Unknown, Some("GPU not found".to_string()), details)
            }
        };
        
        let duration = start.elapsed().unwrap_or_default();
        
        HealthCheckResult {
            component: format!("gpu_{}", self.device_id),
            status,
            timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            message,
            details,
            duration_ms: duration.as_millis() as u64,
        }
    }
    
    fn component_name(&self) -> &str {
        &self.name
    }
}

/// Database health checker
pub struct DatabaseHealthChecker {
    connection_string: String,
}

impl DatabaseHealthChecker {
    pub fn new(connection_string: String) -> Self {
        Self { connection_string }
    }
}

#[async_trait]
impl HealthCheck for DatabaseHealthChecker {
    async fn check(&self) -> HealthCheckResult {
        let start = SystemTime::now();
        
        // Simulate database connectivity check
        let (status, message) = if self.connection_string.contains("localhost") {
            (HealthStatus::Healthy, None)
        } else {
            (HealthStatus::Degraded, Some("High latency detected".to_string()))
        };
        
        let duration = start.elapsed().unwrap_or_default();
        
        let mut details = HashMap::new();
        details.insert("latency_ms".to_string(), serde_json::json!(duration.as_millis()));
        details.insert("connections".to_string(), serde_json::json!(10));
        
        HealthCheckResult {
            component: "database".to_string(),
            status,
            timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            message,
            details,
            duration_ms: duration.as_millis() as u64,
        }
    }
    
    fn component_name(&self) -> &str {
        "database"
    }
}

/// Redis health checker
pub struct RedisHealthChecker {
    url: String,
}

impl RedisHealthChecker {
    pub fn new(url: String) -> Self {
        Self { url }
    }
}

#[async_trait]
impl HealthCheck for RedisHealthChecker {
    async fn check(&self) -> HealthCheckResult {
        let start = SystemTime::now();
        
        // Simulate Redis connectivity check
        let status = HealthStatus::Healthy;
        
        let duration = start.elapsed().unwrap_or_default();
        
        let mut details = HashMap::new();
        details.insert("memory_used_mb".to_string(), serde_json::json!(256));
        details.insert("keys".to_string(), serde_json::json!(1024));
        details.insert("connected_clients".to_string(), serde_json::json!(5));
        
        HealthCheckResult {
            component: "redis".to_string(),
            status,
            timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            message: None,
            details,
            duration_ms: duration.as_millis() as u64,
        }
    }
    
    fn component_name(&self) -> &str {
        "redis"
    }
}

/// Health monitor service
pub struct HealthMonitor {
    checkers: Arc<RwLock<Vec<Box<dyn HealthCheck>>>>,
    cache: Arc<RwLock<Option<SystemHealth>>>,
    cache_ttl: Duration,
    start_time: SystemTime,
}

impl HealthMonitor {
    /// Create new health monitor
    pub fn new(cache_ttl: Duration) -> Self {
        Self {
            checkers: Arc::new(RwLock::new(Vec::new())),
            cache: Arc::new(RwLock::new(None)),
            cache_ttl,
            start_time: SystemTime::now(),
        }
    }
    
    /// Register a health checker
    pub async fn register_checker(&self, checker: Box<dyn HealthCheck>) {
        let mut checkers = self.checkers.write().await;
        checkers.push(checker);
    }
    
    /// Perform liveness check (is the service alive?)
    pub async fn liveness_check(&self) -> HealthCheckResult {
        // Simple liveness check - just verify the service is running
        HealthCheckResult {
            component: "liveness".to_string(),
            status: HealthStatus::Healthy,
            timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            message: Some("Service is alive".to_string()),
            details: HashMap::new(),
            duration_ms: 0,
        }
    }
    
    /// Perform readiness check (is the service ready to accept traffic?)
    pub async fn readiness_check(&self) -> HealthCheckResult {
        let health = self.check_system_health().await;
        
        let status = if health.status.is_operational() {
            HealthStatus::Healthy
        } else {
            HealthStatus::Unhealthy
        };
        
        let mut details = HashMap::new();
        details.insert("components_healthy".to_string(), 
            serde_json::json!(health.components.iter()
                .filter(|c| c.status == HealthStatus::Healthy)
                .count()));
        details.insert("components_total".to_string(), 
            serde_json::json!(health.components.len()));
        
        HealthCheckResult {
            component: "readiness".to_string(),
            status,
            timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            message: if status == HealthStatus::Healthy {
                Some("Service is ready".to_string())
            } else {
                Some("Service not ready - dependencies unhealthy".to_string())
            },
            details,
            duration_ms: 0,
        }
    }
    
    /// Check overall system health
    pub async fn check_system_health(&self) -> SystemHealth {
        // Check cache first
        if let Some(cached) = self.get_cached_health().await {
            return cached;
        }
        
        // Perform health checks
        let checkers = self.checkers.read().await;
        let mut components = Vec::new();
        
        for checker in checkers.iter() {
            components.push(checker.check().await);
        }
        
        // Determine overall status
        let overall_status = if components.iter().all(|c| c.status == HealthStatus::Healthy) {
            HealthStatus::Healthy
        } else if components.iter().any(|c| c.status == HealthStatus::Unhealthy) {
            HealthStatus::Unhealthy
        } else {
            HealthStatus::Degraded
        };
        
        let uptime = self.start_time.elapsed().unwrap_or_default().as_secs();
        
        let health = SystemHealth {
            status: overall_status,
            version: env!("CARGO_PKG_VERSION").to_string(),
            uptime_seconds: uptime,
            components,
            metrics: self.collect_system_metrics().await,
            timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        };
        
        // Update cache
        self.update_cache(health.clone()).await;
        
        health
    }
    
    /// Collect system metrics
    async fn collect_system_metrics(&self) -> SystemMetrics {
        // In real implementation, would collect actual metrics
        SystemMetrics {
            cpu_usage: 45.2,
            memory_used_mb: 8192,
            memory_total_mb: 32768,
            disk_usage: 65.0,
            active_connections: 42,
            request_rate: 150.5,
            error_rate: 0.5,
            gpu_count: 4,
            gpus_available: 3,
        }
    }
    
    /// Get cached health if still valid
    async fn get_cached_health(&self) -> Option<SystemHealth> {
        let cache = self.cache.read().await;
        
        if let Some(ref health) = *cache {
            let age = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs() - health.timestamp;
            
            if age < self.cache_ttl.as_secs() {
                return Some(health.clone());
            }
        }
        
        None
    }
    
    /// Update health cache
    async fn update_cache(&self, health: SystemHealth) {
        let mut cache = self.cache.write().await;
        *cache = Some(health);
    }
    
    /// Get health for specific component
    pub async fn get_component_health(&self, component: &str) -> Option<HealthCheckResult> {
        let health = self.check_system_health().await;
        health.components
            .into_iter()
            .find(|c| c.component == component)
    }
}

/// HTTP health endpoints handler
pub struct HealthEndpoints {
    monitor: Arc<HealthMonitor>,
}

impl HealthEndpoints {
    pub fn new(monitor: Arc<HealthMonitor>) -> Self {
        Self { monitor }
    }
    
    /// Handle /health/live endpoint
    pub async fn handle_liveness(&self) -> Result<String> {
        let result = self.monitor.liveness_check().await;
        serde_json::to_string(&result)
            .context("Failed to serialize liveness check")
    }
    
    /// Handle /health/ready endpoint
    pub async fn handle_readiness(&self) -> Result<String> {
        let result = self.monitor.readiness_check().await;
        serde_json::to_string(&result)
            .context("Failed to serialize readiness check")
    }
    
    /// Handle /health endpoint (full health status)
    pub async fn handle_health(&self) -> Result<String> {
        let health = self.monitor.check_system_health().await;
        serde_json::to_string(&health)
            .context("Failed to serialize health status")
    }
    
    /// Handle /health/{component} endpoint
    pub async fn handle_component_health(&self, component: &str) -> Result<String> {
        if let Some(health) = self.monitor.get_component_health(component).await {
            serde_json::to_string(&health)
                .context("Failed to serialize component health")
        } else {
            Err(anyhow::anyhow!("Component not found: {}", component))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_health_monitor() {
        let monitor = HealthMonitor::new(Duration::from_secs(60));
        
        // Register checkers
        monitor.register_checker(Box::new(
            GpuHealthChecker::new(0, "GPU-0".to_string())
        )).await;
        
        monitor.register_checker(Box::new(
            DatabaseHealthChecker::new("localhost:5432".to_string())
        )).await;
        
        monitor.register_checker(Box::new(
            RedisHealthChecker::new("redis://localhost:6379".to_string())
        )).await;
        
        // Check system health
        let health = monitor.check_system_health().await;
        assert_eq!(health.components.len(), 3);
        assert!(health.uptime_seconds >= 0);
        
        // Check liveness
        let liveness = monitor.liveness_check().await;
        assert_eq!(liveness.status, HealthStatus::Healthy);
        
        // Check readiness
        let readiness = monitor.readiness_check().await;
        assert!(readiness.status.is_operational());
    }
    
    #[tokio::test]
    async fn test_health_endpoints() {
        let monitor = Arc::new(HealthMonitor::new(Duration::from_secs(60)));
        let endpoints = HealthEndpoints::new(monitor);
        
        // Test liveness endpoint
        let liveness = endpoints.handle_liveness().await.unwrap();
        assert!(liveness.contains("liveness"));
        
        // Test readiness endpoint
        let readiness = endpoints.handle_readiness().await.unwrap();
        assert!(readiness.contains("readiness"));
        
        // Test full health endpoint
        let health = endpoints.handle_health().await.unwrap();
        assert!(health.contains("version"));
    }
}
