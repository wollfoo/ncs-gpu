//! OPUS-GPU Plugin API
//!
//! This crate defines the core API and interfaces that plugins must implement
//! to integrate with the OPUS-GPU system. It provides traits for different
//! types of plugins including mining algorithms, monitoring tools, and APIs.

use anyhow::Result;
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;

// Re-export important types for plugin developers
pub use serde_json::Value as JsonValue;
pub use uuid::Uuid;

/// Plugin metadata information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginMetadata {
    /// Plugin unique identifier
    pub id: Uuid,
    /// Plugin name
    pub name: String,
    /// Plugin version
    pub version: String,
    /// Plugin description
    pub description: String,
    /// Plugin author/organization
    pub author: String,
    /// Plugin website or repository URL
    pub url: Option<String>,
    /// Plugin license
    pub license: String,
    /// Plugin type
    pub plugin_type: PluginType,
    /// Supported OPUS-GPU API version
    pub api_version: String,
    /// Plugin dependencies
    pub dependencies: Vec<PluginDependency>,
    /// Plugin configuration schema
    pub config_schema: Option<JsonValue>,
    /// Plugin capabilities/features
    pub capabilities: Vec<String>,
    /// Minimum OPUS-GPU version required
    pub min_opus_version: String,
    /// Maximum OPUS-GPU version supported
    pub max_opus_version: Option<String>,
    /// Plugin tags/keywords
    pub tags: Vec<String>,
    /// Creation timestamp
    pub created_at: DateTime<Utc>,
    /// Last update timestamp
    pub updated_at: DateTime<Utc>,
}

/// Plugin dependency information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginDependency {
    /// Dependency name
    pub name: String,
    /// Required version range
    pub version_range: String,
    /// Whether dependency is optional
    pub optional: bool,
    /// Dependency type
    pub dependency_type: DependencyType,
}

/// Dependency type enumeration
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum DependencyType {
    /// Another plugin
    Plugin,
    /// System library
    Library,
    /// Hardware requirement
    Hardware,
    /// Service dependency
    Service,
}

/// Plugin type enumeration
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum PluginType {
    /// Mining algorithm plugin
    MiningAlgorithm,
    /// Monitoring and metrics plugin
    Monitor,
    /// API extension plugin
    ApiExtension,
    /// Wallet/payment plugin
    Wallet,
    /// Pool connector plugin
    Pool,
    /// Hardware driver plugin
    Hardware,
    /// Security/authentication plugin
    Security,
    /// UI/dashboard plugin
    UI,
    /// Utility plugin
    Utility,
    /// Custom plugin type
    Custom(String),
}

/// Plugin lifecycle state
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum PluginState {
    /// Plugin is not loaded
    Unloaded,
    /// Plugin is loaded but not initialized
    Loaded,
    /// Plugin is initialized and ready
    Initialized,
    /// Plugin is active and running
    Active,
    /// Plugin is paused
    Paused,
    /// Plugin has stopped
    Stopped,
    /// Plugin has an error
    Error(String),
    /// Plugin is being updated
    Updating,
}

/// Plugin configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginConfig {
    /// Plugin ID
    pub plugin_id: Uuid,
    /// Plugin-specific configuration
    pub config: JsonValue,
    /// Whether plugin is enabled
    pub enabled: bool,
    /// Plugin priority (lower number = higher priority)
    pub priority: i32,
    /// Auto-start on system boot
    pub auto_start: bool,
    /// Configuration version for updates
    pub config_version: String,
    /// Environment variables for plugin
    pub environment: HashMap<String, String>,
    /// Resource limits
    pub resource_limits: ResourceLimits,
}

/// Resource limits for plugins
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceLimits {
    /// Maximum memory usage in bytes
    pub max_memory_bytes: Option<u64>,
    /// Maximum CPU usage percentage (0-100)
    pub max_cpu_percent: Option<f32>,
    /// Maximum disk usage in bytes
    pub max_disk_bytes: Option<u64>,
    /// Maximum network bandwidth in bytes/sec
    pub max_network_bps: Option<u64>,
    /// Maximum number of threads
    pub max_threads: Option<u32>,
    /// Maximum number of file descriptors
    pub max_file_descriptors: Option<u32>,
}

/// Plugin execution context
#[derive(Debug, Clone)]
pub struct PluginContext {
    /// Plugin metadata
    pub metadata: PluginMetadata,
    /// Plugin configuration
    pub config: PluginConfig,
    /// OPUS-GPU API handle
    pub api: Arc<dyn OpusGpuApi>,
    /// Plugin event bus handle
    pub event_bus: Arc<dyn PluginEventBus>,
    /// Plugin storage handle
    pub storage: Arc<dyn PluginStorage>,
    /// Plugin logger
    pub logger: Arc<dyn PluginLogger>,
    /// Shutdown signal
    pub shutdown_signal: Arc<tokio::sync::Notify>,
}

/// Plugin health status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginHealth {
    /// Plugin ID
    pub plugin_id: Uuid,
    /// Current state
    pub state: PluginState,
    /// Health status
    pub healthy: bool,
    /// Last health check timestamp
    pub last_check: DateTime<Utc>,
    /// Health check message
    pub message: Option<String>,
    /// Plugin uptime
    pub uptime: std::time::Duration,
    /// Performance metrics
    pub metrics: PluginMetrics,
    /// Error count since last restart
    pub error_count: u32,
    /// Warning count since last restart
    pub warning_count: u32,
}

/// Plugin performance metrics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PluginMetrics {
    /// CPU usage percentage
    pub cpu_usage: f32,
    /// Memory usage in bytes
    pub memory_usage: u64,
    /// Disk usage in bytes
    pub disk_usage: u64,
    /// Network bytes sent
    pub network_tx_bytes: u64,
    /// Network bytes received
    pub network_rx_bytes: u64,
    /// Number of active threads
    pub active_threads: u32,
    /// Number of open file descriptors
    pub open_file_descriptors: u32,
    /// Plugin-specific metrics
    pub custom_metrics: HashMap<String, f64>,
}

/// Main plugin trait that all plugins must implement
#[async_trait]
pub trait Plugin: Send + Sync {
    /// Get plugin metadata
    fn metadata(&self) -> &PluginMetadata;

    /// Initialize the plugin with given context
    async fn initialize(&mut self, context: PluginContext) -> Result<()>;

    /// Start the plugin
    async fn start(&mut self) -> Result<()>;

    /// Stop the plugin
    async fn stop(&mut self) -> Result<()>;

    /// Pause the plugin (optional)
    async fn pause(&mut self) -> Result<()> {
        // Default implementation
        Ok(())
    }

    /// Resume the plugin (optional)
    async fn resume(&mut self) -> Result<()> {
        // Default implementation
        Ok(())
    }

    /// Get current plugin state
    fn state(&self) -> PluginState;

    /// Perform health check
    async fn health_check(&self) -> Result<PluginHealth>;

    /// Handle configuration update
    async fn update_config(&mut self, config: PluginConfig) -> Result<()>;

    /// Handle plugin event
    async fn handle_event(&mut self, event: PluginEvent) -> Result<()>;

    /// Get plugin metrics
    async fn get_metrics(&self) -> Result<PluginMetrics>;

    /// Clean up resources
    async fn cleanup(&mut self) -> Result<()>;
}

/// Mining algorithm plugin trait
#[async_trait]
pub trait MiningPlugin: Plugin {
    /// Get algorithm name
    fn algorithm_name(&self) -> &str;

    /// Compute hash for given input
    async fn compute_hash(&self, input: &[u8], target: &[u8]) -> Result<Option<Vec<u8>>>;

    /// Get algorithm difficulty
    async fn get_difficulty(&self) -> Result<f64>;

    /// Set algorithm difficulty
    async fn set_difficulty(&mut self, difficulty: f64) -> Result<()>;

    /// Get current hash rate
    async fn get_hash_rate(&self) -> Result<f64>;

    /// Validate solution
    async fn validate_solution(&self, input: &[u8], solution: &[u8], target: &[u8]) -> Result<bool>;
}

/// Monitor plugin trait
#[async_trait]
pub trait MonitorPlugin: Plugin {
    /// Start monitoring
    async fn start_monitoring(&mut self) -> Result<()>;

    /// Stop monitoring
    async fn stop_monitoring(&mut self) -> Result<()>;

    /// Get monitored metrics
    async fn get_monitored_metrics(&self) -> Result<HashMap<String, f64>>;

    /// Set alert thresholds
    async fn set_alert_thresholds(&mut self, thresholds: HashMap<String, f64>) -> Result<()>;

    /// Check for alerts
    async fn check_alerts(&self) -> Result<Vec<Alert>>;
}

/// API extension plugin trait
#[async_trait]
pub trait ApiPlugin: Plugin {
    /// Get API routes/endpoints
    fn get_routes(&self) -> Vec<ApiRoute>;

    /// Handle API request
    async fn handle_request(&self, request: ApiRequest) -> Result<ApiResponse>;

    /// Get API documentation
    fn get_documentation(&self) -> Option<ApiDocumentation>;
}

/// Alert information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Alert {
    /// Alert ID
    pub id: Uuid,
    /// Alert severity level
    pub severity: AlertSeverity,
    /// Alert title
    pub title: String,
    /// Alert description
    pub description: String,
    /// Alert source (metric name)
    pub source: String,
    /// Alert value that triggered the alert
    pub value: f64,
    /// Alert threshold that was exceeded
    pub threshold: f64,
    /// Alert timestamp
    pub timestamp: DateTime<Utc>,
    /// Additional metadata
    pub metadata: HashMap<String, String>,
}

/// Alert severity levels
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum AlertSeverity {
    Info,
    Warning,
    Error,
    Critical,
}

/// API route definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiRoute {
    /// HTTP method
    pub method: String,
    /// Route path
    pub path: String,
    /// Route description
    pub description: String,
    /// Required permissions
    pub permissions: Vec<String>,
    /// Route parameters
    pub parameters: Vec<ApiParameter>,
}

/// API parameter definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiParameter {
    /// Parameter name
    pub name: String,
    /// Parameter type
    pub param_type: String,
    /// Whether parameter is required
    pub required: bool,
    /// Parameter description
    pub description: String,
    /// Default value
    pub default: Option<String>,
}

/// API request structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiRequest {
    /// Request ID
    pub id: Uuid,
    /// Request method
    pub method: String,
    /// Request path
    pub path: String,
    /// Request headers
    pub headers: HashMap<String, String>,
    /// Request parameters
    pub parameters: HashMap<String, String>,
    /// Request body
    pub body: Option<Vec<u8>>,
    /// Request timestamp
    pub timestamp: DateTime<Utc>,
}

/// API response structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiResponse {
    /// Response status code
    pub status: u16,
    /// Response headers
    pub headers: HashMap<String, String>,
    /// Response body
    pub body: Vec<u8>,
    /// Response timestamp
    pub timestamp: DateTime<Utc>,
}

/// API documentation structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiDocumentation {
    /// API title
    pub title: String,
    /// API version
    pub version: String,
    /// API description
    pub description: String,
    /// API base URL
    pub base_url: String,
    /// API routes
    pub routes: Vec<ApiRoute>,
    /// API authentication methods
    pub authentication: Vec<String>,
}

/// Plugin event types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PluginEvent {
    /// System started
    SystemStarted,
    /// System stopping
    SystemStopping,
    /// Configuration changed
    ConfigChanged(JsonValue),
    /// New mining job
    MiningJob(JsonValue),
    /// Mining solution found
    MiningSolution(JsonValue),
    /// Device status changed
    DeviceStatusChanged(Uuid, String),
    /// Alert triggered
    AlertTriggered(Alert),
    /// Custom event
    Custom {
        event_type: String,
        data: JsonValue,
    },
}

/// Plugin event bus trait
#[async_trait]
pub trait PluginEventBus: Send + Sync {
    /// Subscribe to events
    async fn subscribe(&self, event_types: Vec<String>) -> Result<()>;

    /// Unsubscribe from events
    async fn unsubscribe(&self, event_types: Vec<String>) -> Result<()>;

    /// Publish an event
    async fn publish(&self, event: PluginEvent) -> Result<()>;

    /// Get event history
    async fn get_history(&self, limit: Option<usize>) -> Result<Vec<PluginEvent>>;
}

/// Plugin storage trait
#[async_trait]
pub trait PluginStorage: Send + Sync {
    /// Get value by key
    async fn get(&self, key: &str) -> Result<Option<Vec<u8>>>;

    /// Set value by key
    async fn set(&self, key: &str, value: Vec<u8>) -> Result<()>;

    /// Delete value by key
    async fn delete(&self, key: &str) -> Result<bool>;

    /// List all keys with optional prefix
    async fn list_keys(&self, prefix: Option<&str>) -> Result<Vec<String>>;

    /// Check if key exists
    async fn exists(&self, key: &str) -> Result<bool>;

    /// Clear all plugin data
    async fn clear(&self) -> Result<()>;
}

/// Plugin logger trait
#[async_trait]
pub trait PluginLogger: Send + Sync {
    /// Log error message
    async fn error(&self, message: &str);

    /// Log warning message
    async fn warn(&self, message: &str);

    /// Log info message
    async fn info(&self, message: &str);

    /// Log debug message
    async fn debug(&self, message: &str);

    /// Log trace message
    async fn trace(&self, message: &str);
}

/// OPUS-GPU API interface for plugins
#[async_trait]
pub trait OpusGpuApi: Send + Sync {
    /// Get system information
    async fn get_system_info(&self) -> Result<JsonValue>;

    /// Get device information
    async fn get_devices(&self) -> Result<Vec<JsonValue>>;

    /// Get device by ID
    async fn get_device(&self, device_id: Uuid) -> Result<Option<JsonValue>>;

    /// Get mining status
    async fn get_mining_status(&self) -> Result<JsonValue>;

    /// Start mining
    async fn start_mining(&self, config: JsonValue) -> Result<()>;

    /// Stop mining
    async fn stop_mining(&self) -> Result<()>;

    /// Get wallet information
    async fn get_wallet_info(&self) -> Result<JsonValue>;

    /// Get pool information
    async fn get_pool_info(&self) -> Result<JsonValue>;

    /// Send notification
    async fn send_notification(&self, title: &str, message: &str) -> Result<()>;

    /// Get configuration
    async fn get_config(&self, path: &str) -> Result<Option<JsonValue>>;

    /// Set configuration
    async fn set_config(&self, path: &str, value: JsonValue) -> Result<()>;
}

/// Plugin factory trait for creating plugin instances
pub trait PluginFactory: Send + Sync {
    /// Create a new plugin instance
    fn create_plugin(&self) -> Result<Box<dyn Plugin>>;

    /// Get plugin metadata
    fn get_metadata(&self) -> &PluginMetadata;

    /// Validate plugin compatibility
    fn validate_compatibility(&self, opus_version: &str) -> Result<bool>;
}

// Implement default values for various structs

impl Default for PluginState {
    fn default() -> Self {
        Self::Unloaded
    }
}

impl Default for ResourceLimits {
    fn default() -> Self {
        Self {
            max_memory_bytes: Some(1024 * 1024 * 1024), // 1GB default
            max_cpu_percent: Some(50.0), // 50% CPU default
            max_disk_bytes: Some(10 * 1024 * 1024 * 1024), // 10GB default
            max_network_bps: Some(100 * 1024 * 1024), // 100MB/s default
            max_threads: Some(10),
            max_file_descriptors: Some(1000),
        }
    }
}

impl Default for PluginConfig {
    fn default() -> Self {
        Self {
            plugin_id: Uuid::new_v4(),
            config: JsonValue::Object(Default::default()),
            enabled: true,
            priority: 0,
            auto_start: false,
            config_version: "1.0.0".to_string(),
            environment: HashMap::new(),
            resource_limits: ResourceLimits::default(),
        }
    }
}

impl std::fmt::Display for PluginType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PluginType::MiningAlgorithm => write!(f, "mining-algorithm"),
            PluginType::Monitor => write!(f, "monitor"),
            PluginType::ApiExtension => write!(f, "api-extension"),
            PluginType::Wallet => write!(f, "wallet"),
            PluginType::Pool => write!(f, "pool"),
            PluginType::Hardware => write!(f, "hardware"),
            PluginType::Security => write!(f, "security"),
            PluginType::UI => write!(f, "ui"),
            PluginType::Utility => write!(f, "utility"),
            PluginType::Custom(name) => write!(f, "custom-{}", name),
        }
    }
}

impl std::fmt::Display for PluginState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PluginState::Unloaded => write!(f, "unloaded"),
            PluginState::Loaded => write!(f, "loaded"),
            PluginState::Initialized => write!(f, "initialized"),
            PluginState::Active => write!(f, "active"),
            PluginState::Paused => write!(f, "paused"),
            PluginState::Stopped => write!(f, "stopped"),
            PluginState::Error(err) => write!(f, "error: {}", err),
            PluginState::Updating => write!(f, "updating"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_plugin_metadata_creation() {
        let metadata = PluginMetadata {
            id: Uuid::new_v4(),
            name: "Test Plugin".to_string(),
            version: "1.0.0".to_string(),
            description: "A test plugin".to_string(),
            author: "Test Author".to_string(),
            url: Some("https://example.com".to_string()),
            license: "MIT".to_string(),
            plugin_type: PluginType::Utility,
            api_version: "1.0.0".to_string(),
            dependencies: vec![],
            config_schema: None,
            capabilities: vec!["test".to_string()],
            min_opus_version: "1.0.0".to_string(),
            max_opus_version: None,
            tags: vec!["test".to_string()],
            created_at: Utc::now(),
            updated_at: Utc::now(),
        };

        assert_eq!(metadata.name, "Test Plugin");
        assert_eq!(metadata.plugin_type, PluginType::Utility);
    }

    #[test]
    fn test_plugin_state_display() {
        assert_eq!(PluginState::Active.to_string(), "active");
        assert_eq!(PluginState::Error("test error".to_string()).to_string(), "error: test error");
    }

    #[test]
    fn test_plugin_type_display() {
        assert_eq!(PluginType::MiningAlgorithm.to_string(), "mining-algorithm");
        assert_eq!(PluginType::Custom("my-plugin".to_string()).to_string(), "custom-my-plugin");
    }
}