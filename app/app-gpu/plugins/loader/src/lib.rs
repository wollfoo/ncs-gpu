//! OPUS-GPU Plugin Loader
//!
//! This crate provides dynamic loading capabilities for OPUS-GPU plugins,
//! including security sandboxing, hot-reload support, and lifecycle management.

use anyhow::Result;
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use opus_gpu_plugin_api::*;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;
use tracing::{debug, error, info, warn};
use uuid::Uuid;

pub mod security;
pub mod hot_reload;
pub mod isolation;

// Re-export public types
pub use security::{SecurityPolicy, PluginSandbox, SecurityViolation};
pub use hot_reload::{HotReloadManager, FileWatcher, ReloadEvent};
pub use isolation::{PluginIsolation, IsolationLevel, ResourceMonitor};

/// Plugin loader configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoaderConfig {
    /// Plugin directories to scan
    pub plugin_dirs: Vec<PathBuf>,
    /// Enable hot-reload functionality
    pub enable_hot_reload: bool,
    /// Hot-reload check interval
    pub hot_reload_interval: Duration,
    /// Enable security sandboxing
    pub enable_security: bool,
    /// Default security policy
    pub default_security_policy: SecurityPolicy,
    /// Plugin load timeout
    pub load_timeout: Duration,
    /// Plugin initialization timeout
    pub init_timeout: Duration,
    /// Maximum concurrent plugin loads
    pub max_concurrent_loads: usize,
    /// Plugin file extensions to scan
    pub plugin_extensions: Vec<String>,
    /// Blacklisted plugins (by name or ID)
    pub blacklist: Vec<String>,
    /// Whitelist mode (only load whitelisted plugins)
    pub whitelist_mode: bool,
    /// Whitelisted plugins (by name or ID)
    pub whitelist: Vec<String>,
    /// Enable plugin metrics collection
    pub enable_metrics: bool,
    /// Metrics collection interval
    pub metrics_interval: Duration,
}

/// Plugin load result
#[derive(Debug, Clone)]
pub struct LoadResult {
    /// Whether load was successful
    pub success: bool,
    /// Plugin metadata if successful
    pub metadata: Option<PluginMetadata>,
    /// Error message if failed
    pub error: Option<String>,
    /// Load duration
    pub load_time: Duration,
    /// Plugin file path
    pub file_path: PathBuf,
}

/// Loaded plugin information
#[derive(Debug)]
pub struct LoadedPlugin {
    /// Plugin metadata
    pub metadata: PluginMetadata,
    /// Plugin instance
    pub plugin: Box<dyn Plugin>,
    /// Plugin context
    pub context: PluginContext,
    /// Load timestamp
    pub loaded_at: DateTime<Utc>,
    /// Plugin file path
    pub file_path: PathBuf,
    /// Plugin library handle
    pub library: Option<libloading::Library>,
    /// Security sandbox
    pub sandbox: Option<PluginSandbox>,
    /// Resource monitor
    pub resource_monitor: Option<ResourceMonitor>,
    /// Last health check
    pub last_health_check: Option<DateTime<Utc>>,
    /// Health check result
    pub health_status: Option<PluginHealth>,
}

/// Plugin loader statistics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct LoaderStats {
    /// Total plugins loaded
    pub total_loaded: usize,
    /// Currently active plugins
    pub active_plugins: usize,
    /// Failed load attempts
    pub failed_loads: usize,
    /// Hot-reload events
    pub hot_reload_events: usize,
    /// Security violations detected
    pub security_violations: usize,
    /// Average load time (microseconds)
    pub avg_load_time_us: u64,
    /// Total memory usage by plugins
    pub total_memory_usage: u64,
    /// Total CPU usage by plugins
    pub total_cpu_usage: f32,
}

/// Plugin loader events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum LoaderEvent {
    /// Plugin loaded successfully
    PluginLoaded {
        plugin_id: Uuid,
        plugin_name: String,
        load_time: Duration,
    },
    /// Plugin failed to load
    PluginLoadFailed {
        file_path: PathBuf,
        error: String,
    },
    /// Plugin unloaded
    PluginUnloaded {
        plugin_id: Uuid,
        plugin_name: String,
    },
    /// Plugin reloaded (hot-reload)
    PluginReloaded {
        plugin_id: Uuid,
        plugin_name: String,
    },
    /// Security violation detected
    SecurityViolation {
        plugin_id: Uuid,
        violation: SecurityViolation,
    },
    /// Resource limit exceeded
    ResourceLimitExceeded {
        plugin_id: Uuid,
        resource: String,
        limit: u64,
        actual: u64,
    },
}

/// Plugin lifecycle management interface
#[async_trait]
pub trait PluginLifecycle: Send + Sync {
    /// Called before plugin is loaded
    async fn before_load(&self, file_path: &Path) -> Result<()>;

    /// Called after plugin is loaded successfully
    async fn after_load(&self, plugin: &LoadedPlugin) -> Result<()>;

    /// Called before plugin is unloaded
    async fn before_unload(&self, plugin_id: Uuid) -> Result<()>;

    /// Called after plugin is unloaded
    async fn after_unload(&self, plugin_id: Uuid) -> Result<()>;

    /// Called when plugin error occurs
    async fn on_error(&self, plugin_id: Uuid, error: &str) -> Result<()>;
}

/// Main plugin loader implementation
pub struct PluginLoader {
    config: LoaderConfig,
    loaded_plugins: Arc<DashMap<Uuid, LoadedPlugin>>,
    stats: Arc<RwLock<LoaderStats>>,
    event_handlers: Vec<Box<dyn PluginLifecycle>>,
    hot_reload_manager: Option<HotReloadManager>,
    security_policies: Arc<DashMap<Uuid, SecurityPolicy>>,
    shutdown_signal: Arc<tokio::sync::Notify>,
}

impl PluginLoader {
    /// Create a new plugin loader
    pub fn new(config: LoaderConfig) -> Self {
        info!(\"🔌 Initializing plugin loader with {} plugin directories\", config.plugin_dirs.len());

        Self {
            config: config.clone(),
            loaded_plugins: Arc::new(DashMap::new()),
            stats: Arc::new(RwLock::new(LoaderStats::default())),
            event_handlers: Vec::new(),
            hot_reload_manager: if config.enable_hot_reload {
                Some(HotReloadManager::new(config.hot_reload_interval))
            } else {
                None
            },
            security_policies: Arc::new(DashMap::new()),
            shutdown_signal: Arc::new(tokio::sync::Notify::new()),
        }
    }

    /// Add a lifecycle event handler
    pub fn add_lifecycle_handler(&mut self, handler: Box<dyn PluginLifecycle>) {
        self.event_handlers.push(handler);
    }

    /// Scan and load all plugins from configured directories
    pub async fn scan_and_load_plugins(&self) -> Result<Vec<LoadResult>> {
        info!(\"🔍 Scanning for plugins in {} directories\", self.config.plugin_dirs.len());

        let mut results = Vec::new();
        let mut plugin_files = Vec::new();

        // Scan all plugin directories
        for plugin_dir in &self.config.plugin_dirs {
            if plugin_dir.exists() && plugin_dir.is_dir() {
                debug!(\"📂 Scanning directory: {:?}\", plugin_dir);

                let files = self.scan_directory(plugin_dir).await?;
                plugin_files.extend(files);
            } else {
                warn!(\"⚠️ Plugin directory does not exist: {:?}\", plugin_dir);
            }
        }

        info!(\"📋 Found {} plugin files to load\", plugin_files.len());

        // Load plugins with concurrency control
        let semaphore = Arc::new(tokio::sync::Semaphore::new(self.config.max_concurrent_loads));
        let mut tasks = Vec::new();

        for file_path in plugin_files {
            let semaphore = semaphore.clone();
            let loader = self.clone();

            let task = tokio::spawn(async move {
                let _permit = semaphore.acquire().await.unwrap();
                loader.load_plugin(&file_path).await
            });

            tasks.push(task);
        }

        // Wait for all loads to complete
        for task in tasks {
            match task.await {
                Ok(result) => results.push(result),
                Err(e) => {
                    error!(\"❌ Plugin load task failed: {}\", e);
                    results.push(LoadResult {
                        success: false,
                        metadata: None,
                        error: Some(e.to_string()),
                        load_time: Duration::ZERO,
                        file_path: PathBuf::new(),
                    });
                }
            }
        }

        // Update statistics
        {
            let mut stats = self.stats.write();
            stats.total_loaded = results.iter().filter(|r| r.success).count();
            stats.failed_loads = results.iter().filter(|r| !r.success).count();
            stats.active_plugins = self.loaded_plugins.len();

            if !results.is_empty() {
                let total_time: Duration = results.iter().map(|r| r.load_time).sum();
                stats.avg_load_time_us = (total_time.as_micros() / results.len() as u128) as u64;
            }
        }

        info!(\"✅ Plugin loading complete: {} successful, {} failed\",
              results.iter().filter(|r| r.success).count(),
              results.iter().filter(|r| !r.success).count());

        Ok(results)
    }

    /// Load a single plugin from file
    pub async fn load_plugin(&self, file_path: &Path) -> LoadResult {
        let start_time = std::time::Instant::now();

        debug!(\"📦 Loading plugin from: {:?}\", file_path);

        // Check blacklist/whitelist
        if let Some(filename) = file_path.file_name().and_then(|n| n.to_str()) {
            if self.is_blacklisted(filename) {
                warn!(\"🚫 Plugin {} is blacklisted, skipping\", filename);
                return LoadResult {
                    success: false,
                    metadata: None,
                    error: Some(\"Plugin is blacklisted\".to_string()),
                    load_time: start_time.elapsed(),
                    file_path: file_path.to_path_buf(),
                };
            }

            if self.config.whitelist_mode && !self.is_whitelisted(filename) {
                warn!(\"🚫 Plugin {} is not whitelisted, skipping\", filename);
                return LoadResult {
                    success: false,
                    metadata: None,
                    error: Some(\"Plugin is not whitelisted\".to_string()),
                    load_time: start_time.elapsed(),
                    file_path: file_path.to_path_buf(),
                };
            }
        }

        // Call before_load handlers
        for handler in &self.event_handlers {
            if let Err(e) = handler.before_load(file_path).await {
                error!(\"❌ Before load handler failed: {}\", e);
                return LoadResult {
                    success: false,
                    metadata: None,
                    error: Some(format!(\"Before load handler failed: {}\", e)),
                    load_time: start_time.elapsed(),
                    file_path: file_path.to_path_buf(),
                };
            }
        }

        // Load plugin with timeout
        let load_result = tokio::time::timeout(
            self.config.load_timeout,
            self.load_plugin_internal(file_path)
        ).await;

        match load_result {
            Ok(Ok(loaded_plugin)) => {
                let metadata = loaded_plugin.metadata.clone();
                let plugin_id = metadata.id;

                // Store loaded plugin
                self.loaded_plugins.insert(plugin_id, loaded_plugin);

                // Call after_load handlers
                if let Some(plugin) = self.loaded_plugins.get(&plugin_id) {
                    for handler in &self.event_handlers {
                        if let Err(e) = handler.after_load(&plugin).await {
                            error!(\"❌ After load handler failed: {}\", e);
                        }
                    }
                }

                info!(\"✅ Plugin loaded successfully: {} ({})\", metadata.name, plugin_id);

                LoadResult {
                    success: true,
                    metadata: Some(metadata),
                    error: None,
                    load_time: start_time.elapsed(),
                    file_path: file_path.to_path_buf(),
                }
            }
            Ok(Err(e)) => {
                error!(\"❌ Failed to load plugin {:?}: {}\", file_path, e);
                LoadResult {
                    success: false,
                    metadata: None,
                    error: Some(e.to_string()),
                    load_time: start_time.elapsed(),
                    file_path: file_path.to_path_buf(),
                }
            }
            Err(_) => {
                error!(\"⏰ Plugin load timeout: {:?}\", file_path);
                LoadResult {
                    success: false,
                    metadata: None,
                    error: Some(\"Load timeout\".to_string()),
                    load_time: start_time.elapsed(),
                    file_path: file_path.to_path_buf(),
                }
            }
        }
    }

    /// Internal plugin loading implementation
    async fn load_plugin_internal(&self, file_path: &Path) -> Result<LoadedPlugin> {
        // Load the dynamic library
        let library = unsafe { libloading::Library::new(file_path)? };

        // Get the plugin factory function
        let factory_fn: libloading::Symbol<fn() -> Result<Box<dyn PluginFactory>>> = unsafe {
            library.get(b\"create_plugin_factory\")?
        };

        // Create plugin factory
        let factory = factory_fn()?;

        // Get plugin metadata
        let metadata = factory.get_metadata().clone();

        // Validate compatibility
        if !factory.validate_compatibility(env!(\"CARGO_PKG_VERSION\"))? {
            return Err(anyhow::anyhow!(\"Plugin is not compatible with current OPUS-GPU version\"));
        }

        // Create plugin instance
        let mut plugin = factory.create_plugin()?;

        // Create plugin context
        let context = self.create_plugin_context(metadata.clone()).await?;

        // Setup security sandbox if enabled
        let sandbox = if self.config.enable_security {
            let policy = self.security_policies
                .get(&metadata.id)
                .map(|p| p.clone())
                .unwrap_or_else(|| self.config.default_security_policy.clone());

            Some(PluginSandbox::new(metadata.id, policy)?)
        } else {
            None
        };

        // Setup resource monitoring
        let resource_monitor = if self.config.enable_metrics {
            Some(ResourceMonitor::new(
                metadata.id,
                context.config.resource_limits.clone()
            )?)
        } else {
            None
        };

        // Initialize plugin with timeout
        tokio::time::timeout(
            self.config.init_timeout,
            plugin.initialize(context.clone())
        ).await??;

        let loaded_plugin = LoadedPlugin {
            metadata,
            plugin,
            context,
            loaded_at: Utc::now(),
            file_path: file_path.to_path_buf(),
            library: Some(library),
            sandbox,
            resource_monitor,
            last_health_check: None,
            health_status: None,
        };

        Ok(loaded_plugin)
    }

    /// Create plugin context
    async fn create_plugin_context(&self, metadata: PluginMetadata) -> Result<PluginContext> {
        // TODO: Create actual implementations of these traits
        let api = Arc::new(MockOpusGpuApi::new());
        let event_bus = Arc::new(MockPluginEventBus::new());
        let storage = Arc::new(MockPluginStorage::new());
        let logger = Arc::new(MockPluginLogger::new());

        let config = PluginConfig {
            plugin_id: metadata.id,
            ..Default::default()
        };

        Ok(PluginContext {
            metadata,
            config,
            api,
            event_bus,
            storage,
            logger,
            shutdown_signal: self.shutdown_signal.clone(),
        })
    }

    /// Unload a plugin by ID
    pub async fn unload_plugin(&self, plugin_id: Uuid) -> Result<bool> {
        info!(\"🔌 Unloading plugin: {}\", plugin_id);

        // Call before_unload handlers
        for handler in &self.event_handlers {
            if let Err(e) = handler.before_unload(plugin_id).await {
                error!(\"❌ Before unload handler failed: {}\", e);
            }
        }

        let removed = if let Some((_, mut loaded_plugin)) = self.loaded_plugins.remove(&plugin_id) {
            // Stop the plugin
            if let Err(e) = loaded_plugin.plugin.stop().await {
                error!(\"❌ Error stopping plugin {}: {}\", plugin_id, e);
            }

            // Cleanup plugin resources
            if let Err(e) = loaded_plugin.plugin.cleanup().await {
                error!(\"❌ Error cleaning up plugin {}: {}\", plugin_id, e);
            }

            // Stop resource monitoring
            if let Some(monitor) = loaded_plugin.resource_monitor.take() {
                if let Err(e) = monitor.stop().await {
                    error!(\"❌ Error stopping resource monitor for plugin {}: {}\", plugin_id, e);
                }
            }

            // Cleanup security sandbox
            if let Some(sandbox) = loaded_plugin.sandbox.take() {
                if let Err(e) = sandbox.cleanup().await {
                    error!(\"❌ Error cleaning up sandbox for plugin {}: {}\", plugin_id, e);
                }
            }

            true
        } else {
            false
        };

        if removed {
            // Call after_unload handlers
            for handler in &self.event_handlers {
                if let Err(e) = handler.after_unload(plugin_id).await {
                    error!(\"❌ After unload handler failed: {}\", e);
                }
            }

            // Update statistics
            {
                let mut stats = self.stats.write();
                stats.active_plugins = self.loaded_plugins.len();
            }

            info!(\"✅ Plugin {} unloaded successfully\", plugin_id);
        } else {
            warn!(\"⚠️ Plugin {} not found for unloading\", plugin_id);
        }

        Ok(removed)
    }

    /// Get all loaded plugins
    pub fn get_loaded_plugins(&self) -> Vec<PluginMetadata> {
        self.loaded_plugins
            .iter()
            .map(|entry| entry.metadata.clone())
            .collect()
    }

    /// Get plugin by ID
    pub fn get_plugin(&self, plugin_id: Uuid) -> Option<PluginMetadata> {
        self.loaded_plugins
            .get(&plugin_id)
            .map(|plugin| plugin.metadata.clone())
    }

    /// Get loader statistics
    pub fn get_stats(&self) -> LoaderStats {
        let mut stats = self.stats.read().clone();
        stats.active_plugins = self.loaded_plugins.len();

        // Calculate resource usage
        let (total_memory, total_cpu) = self.loaded_plugins
            .iter()
            .filter_map(|entry| entry.resource_monitor.as_ref())
            .fold((0u64, 0f32), |(mem, cpu), monitor| {
                let usage = monitor.get_current_usage();
                (mem + usage.memory_usage, cpu + usage.cpu_usage)
            });

        stats.total_memory_usage = total_memory;
        stats.total_cpu_usage = total_cpu;

        stats
    }

    /// Scan directory for plugin files
    async fn scan_directory(&self, dir: &Path) -> Result<Vec<PathBuf>> {
        let mut plugin_files = Vec::new();
        let mut entries = tokio::fs::read_dir(dir).await?;

        while let Some(entry) = entries.next_entry().await? {
            let path = entry.path();

            if path.is_file() {
                if let Some(extension) = path.extension().and_then(|ext| ext.to_str()) {
                    if self.config.plugin_extensions.contains(&extension.to_string()) {
                        plugin_files.push(path);
                    }
                }
            } else if path.is_dir() {
                // Recursively scan subdirectories
                let sub_files = self.scan_directory(&path).await?;
                plugin_files.extend(sub_files);
            }
        }

        Ok(plugin_files)
    }

    /// Check if plugin is blacklisted
    fn is_blacklisted(&self, name: &str) -> bool {
        self.config.blacklist.iter().any(|item| {
            name.contains(item) || item.contains(name)
        })
    }

    /// Check if plugin is whitelisted
    fn is_whitelisted(&self, name: &str) -> bool {
        self.config.whitelist.iter().any(|item| {
            name.contains(item) || item.contains(name)
        })
    }

    /// Start the plugin loader
    pub async fn start(&self) -> Result<()> {
        info!(\"🚀 Starting plugin loader\");

        // Start hot-reload manager if enabled
        if let Some(hot_reload) = &self.hot_reload_manager {
            hot_reload.start(&self.config.plugin_dirs).await?;
        }

        // Load all plugins
        self.scan_and_load_plugins().await?;

        // Start resource monitoring if enabled
        if self.config.enable_metrics {
            self.start_resource_monitoring().await?;
        }

        info!(\"✅ Plugin loader started successfully\");
        Ok(())
    }

    /// Start resource monitoring
    async fn start_resource_monitoring(&self) -> Result<()> {
        let loaded_plugins = self.loaded_plugins.clone();
        let interval = self.config.metrics_interval;

        tokio::spawn(async move {
            let mut interval_timer = tokio::time::interval(interval);

            loop {
                interval_timer.tick().await;

                for entry in loaded_plugins.iter() {
                    if let Some(monitor) = &entry.resource_monitor {
                        if let Err(e) = monitor.collect_metrics().await {
                            error!(\"❌ Error collecting metrics for plugin {}: {}\",
                                   entry.metadata.id, e);
                        }
                    }
                }
            }
        });

        Ok(())
    }

    /// Stop the plugin loader
    pub async fn stop(&self) -> Result<()> {
        info!(\"🛑 Stopping plugin loader\");

        // Signal shutdown
        self.shutdown_signal.notify_waiters();

        // Stop hot-reload manager
        if let Some(hot_reload) = &self.hot_reload_manager {
            hot_reload.stop().await?;
        }

        // Unload all plugins
        let plugin_ids: Vec<Uuid> = self.loaded_plugins
            .iter()
            .map(|entry| entry.metadata.id)
            .collect();

        for plugin_id in plugin_ids {
            if let Err(e) = self.unload_plugin(plugin_id).await {
                error!(\"❌ Error unloading plugin {}: {}\", plugin_id, e);
            }
        }

        info!(\"✅ Plugin loader stopped\");
        Ok(())
    }
}

// Clone implementation for PluginLoader
impl Clone for PluginLoader {
    fn clone(&self) -> Self {
        Self {
            config: self.config.clone(),
            loaded_plugins: self.loaded_plugins.clone(),
            stats: self.stats.clone(),
            event_handlers: Vec::new(), // Event handlers are not cloned
            hot_reload_manager: None,   // Hot reload manager is not cloned
            security_policies: self.security_policies.clone(),
            shutdown_signal: self.shutdown_signal.clone(),
        }
    }
}

// Default configuration
impl Default for LoaderConfig {
    fn default() -> Self {
        Self {
            plugin_dirs: vec![PathBuf::from(\"./plugins\")],
            enable_hot_reload: false,
            hot_reload_interval: Duration::from_secs(5),
            enable_security: true,
            default_security_policy: SecurityPolicy::default(),
            load_timeout: Duration::from_secs(30),
            init_timeout: Duration::from_secs(10),
            max_concurrent_loads: 4,
            plugin_extensions: vec![
                \"so\".to_string(),    // Linux
                \"dll\".to_string(),   // Windows
                \"dylib\".to_string(), // macOS
            ],
            blacklist: Vec::new(),
            whitelist_mode: false,
            whitelist: Vec::new(),
            enable_metrics: true,
            metrics_interval: Duration::from_secs(30),
        }
    }
}

// Mock implementations for testing
// TODO: Replace with actual implementations

struct MockOpusGpuApi;

impl MockOpusGpuApi {
    fn new() -> Self { Self }
}

#[async_trait]
impl OpusGpuApi for MockOpusGpuApi {
    async fn get_system_info(&self) -> Result<serde_json::Value> {
        Ok(serde_json::json!({\"system\": \"mock\"}))
    }

    async fn get_devices(&self) -> Result<Vec<serde_json::Value>> {
        Ok(vec![])
    }

    async fn get_device(&self, _device_id: Uuid) -> Result<Option<serde_json::Value>> {
        Ok(None)
    }

    async fn get_mining_status(&self) -> Result<serde_json::Value> {
        Ok(serde_json::json!({\"status\": \"idle\"}))
    }

    async fn start_mining(&self, _config: serde_json::Value) -> Result<()> {
        Ok(())
    }

    async fn stop_mining(&self) -> Result<()> {
        Ok(())
    }

    async fn get_wallet_info(&self) -> Result<serde_json::Value> {
        Ok(serde_json::json!({\"balance\": 0}))
    }

    async fn get_pool_info(&self) -> Result<serde_json::Value> {
        Ok(serde_json::json!({\"connected\": false}))
    }

    async fn send_notification(&self, _title: &str, _message: &str) -> Result<()> {
        Ok(())
    }

    async fn get_config(&self, _path: &str) -> Result<Option<serde_json::Value>> {
        Ok(None)
    }

    async fn set_config(&self, _path: &str, _value: serde_json::Value) -> Result<()> {
        Ok(())
    }
}

struct MockPluginEventBus;

impl MockPluginEventBus {
    fn new() -> Self { Self }
}

#[async_trait]
impl PluginEventBus for MockPluginEventBus {
    async fn subscribe(&self, _event_types: Vec<String>) -> Result<()> {
        Ok(())
    }

    async fn unsubscribe(&self, _event_types: Vec<String>) -> Result<()> {
        Ok(())
    }

    async fn publish(&self, _event: PluginEvent) -> Result<()> {
        Ok(())
    }

    async fn get_history(&self, _limit: Option<usize>) -> Result<Vec<PluginEvent>> {
        Ok(vec![])
    }
}

struct MockPluginStorage;

impl MockPluginStorage {
    fn new() -> Self { Self }
}

#[async_trait]
impl PluginStorage for MockPluginStorage {
    async fn get(&self, _key: &str) -> Result<Option<Vec<u8>>> {
        Ok(None)
    }

    async fn set(&self, _key: &str, _value: Vec<u8>) -> Result<()> {
        Ok(())
    }

    async fn delete(&self, _key: &str) -> Result<bool> {
        Ok(false)
    }

    async fn list_keys(&self, _prefix: Option<&str>) -> Result<Vec<String>> {
        Ok(vec![])
    }

    async fn exists(&self, _key: &str) -> Result<bool> {
        Ok(false)
    }

    async fn clear(&self) -> Result<()> {
        Ok(())
    }
}

struct MockPluginLogger;

impl MockPluginLogger {
    fn new() -> Self { Self }
}

#[async_trait]
impl PluginLogger for MockPluginLogger {
    async fn error(&self, message: &str) {
        tracing::error!(\"[Plugin] {}\", message);
    }

    async fn warn(&self, message: &str) {
        tracing::warn!(\"[Plugin] {}\", message);
    }

    async fn info(&self, message: &str) {
        tracing::info!(\"[Plugin] {}\", message);
    }

    async fn debug(&self, message: &str) {
        tracing::debug!(\"[Plugin] {}\", message);
    }

    async fn trace(&self, message: &str) {
        tracing::trace!(\"[Plugin] {}\", message);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_plugin_loader_creation() {
        let config = LoaderConfig::default();
        let loader = PluginLoader::new(config);

        assert_eq!(loader.get_loaded_plugins().len(), 0);

        let stats = loader.get_stats();
        assert_eq!(stats.active_plugins, 0);
        assert_eq!(stats.total_loaded, 0);
    }

    #[tokio::test]
    async fn test_directory_scanning() {
        let temp_dir = TempDir::new().unwrap();
        let config = LoaderConfig {
            plugin_dirs: vec![temp_dir.path().to_path_buf()],
            ..Default::default()
        };

        let loader = PluginLoader::new(config);

        // Create a mock plugin file
        let plugin_file = temp_dir.path().join(\"test_plugin.so\");
        tokio::fs::write(&plugin_file, b\"mock plugin\").await.unwrap();

        let files = loader.scan_directory(temp_dir.path()).await.unwrap();
        assert_eq!(files.len(), 1);
        assert_eq!(files[0], plugin_file);
    }

    #[test]
    fn test_blacklist_whitelist() {
        let config = LoaderConfig {
            blacklist: vec![\"malicious\".to_string()],
            whitelist: vec![\"trusted\".to_string()],
            whitelist_mode: true,
            ..Default::default()
        };

        let loader = PluginLoader::new(config);

        assert!(loader.is_blacklisted(\"malicious_plugin.so\"));
        assert!(!loader.is_blacklisted(\"safe_plugin.so\"));

        assert!(loader.is_whitelisted(\"trusted_plugin.so\"));
        assert!(!loader.is_whitelisted(\"unknown_plugin.so\"));
    }
}