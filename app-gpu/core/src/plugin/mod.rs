//! Plugin Management System
//! 
//! Dynamic plugin loading và lifecycle management

use std::path::{Path, PathBuf};
use std::collections::HashMap;
use std::sync::Arc;
use std::ffi::OsStr;
use async_trait::async_trait;
use anyhow::{Result, Context};
use libloading::{Library, Symbol};
use parking_lot::RwLock;
use serde::{Serialize, Deserialize};
use tracing::{info, debug, warn, error, instrument};
use uuid::Uuid;

use crate::config::PluginConfig;
use crate::error::OpusError;

/// Plugin metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginMetadata {
    pub name: String,
    pub version: String,
    pub author: String,
    pub description: String,
    pub capabilities: Vec<String>,
}

/// Plugin lifecycle events
#[derive(Debug, Clone)]
pub enum PluginEvent {
    /// Plugin đã được load
    Loaded {
        name: String,
        version: String,
    },
    /// Plugin đã được unload
    Unloaded {
        name: String,
    },
    /// Plugin error
    Error {
        plugin: String,
        error: String,
    },
    /// Message received từ plugin
    MessageReceived {
        source: String,
        payload: Vec<u8>,
    },
}

/// Plugin trait mà mọi plugin phải implement
#[async_trait]
pub trait Plugin: Send + Sync {
    /// Get plugin metadata
    fn metadata(&self) -> PluginMetadata;
    
    /// Initialize plugin
    async fn initialize(&mut self) -> Result<()>;
    
    /// Execute task
    async fn execute(&self, task: PluginTask) -> Result<PluginOutput>;
    
    /// Shutdown plugin
    async fn shutdown(&mut self) -> Result<()>;
    
    /// Health check
    fn health_check(&self) -> HealthStatus;
}

/// Plugin task
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginTask {
    pub id: Uuid,
    pub type_: String,
    pub payload: Vec<u8>,
    pub priority: u8,
}

/// Plugin output
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginOutput {
    pub task_id: Uuid,
    pub status: TaskStatus,
    pub result: Vec<u8>,
    pub metrics: HashMap<String, f64>,
}

/// Task status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TaskStatus {
    Success,
    Failed(String),
    Partial(f32), // Percentage complete
}

/// Health status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthStatus {
    pub healthy: bool,
    pub uptime_seconds: u64,
    pub tasks_completed: u64,
    pub tasks_failed: u64,
    pub memory_usage_mb: f32,
}

/// Plugin wrapper với dynamic library
struct LoadedPlugin {
    library: Arc<Library>,
    plugin: Arc<dyn Plugin>,
    metadata: PluginMetadata,
    path: PathBuf,
    health: RwLock<HealthStatus>,
}

/// Plugin Manager
pub struct PluginManager {
    config: PluginConfig,
    plugins: Arc<RwLock<HashMap<String, LoadedPlugin>>>,
}

impl PluginManager {
    /// Create new plugin manager
    #[instrument(skip(config))]
    pub async fn new(config: PluginConfig) -> Result<Self> {
        info!("Initializing plugin manager");
        
        // Ensure plugin directory exists
        if !config.plugin_dir.exists() {
            std::fs::create_dir_all(&config.plugin_dir)?;
        }
        
        Ok(Self {
            config,
            plugins: Arc::new(RwLock::new(HashMap::new())),
        })
    }
    
    /// Discover plugins trong configured directory
    pub async fn discover_plugins(&self) -> Result<Vec<PathBuf>> {
        let mut plugins = Vec::new();
        
        let entries = std::fs::read_dir(&self.config.plugin_dir)?;
        
        for entry in entries {
            let entry = entry?;
            let path = entry.path();
            
            // Check for .so (Linux), .dll (Windows), .dylib (macOS)
            if path.is_file() {
                let ext = path.extension().and_then(OsStr::to_str);
                if matches!(ext, Some("so") | Some("dll") | Some("dylib")) {
                    debug!("Found plugin: {:?}", path);
                    plugins.push(path);
                }
            }
        }
        
        Ok(plugins)
    }
    
    /// Load plugin từ path
    #[instrument(skip(self))]
    pub async fn load_plugin(&self, path: &Path) -> Result<String> {
        info!("Loading plugin from {:?}", path);
        
        // Load dynamic library
        let library = unsafe {
            Library::new(path)
                .with_context(|| format!("Failed to load library from {:?}", path))?
        };
        
        // Get plugin entry point
        let plugin: Arc<dyn Plugin> = unsafe {
            let constructor: Symbol<fn() -> Box<dyn Plugin>> = 
                library.get(b"create_plugin")
                    .with_context(|| "Plugin missing 'create_plugin' export")?;
            
            Arc::from(constructor())
        };
        
        // Get metadata
        let metadata = plugin.metadata();
        let name = metadata.name.clone();
        
        // Initialize plugin
        let mut plugin_mut = plugin.clone();
        Arc::get_mut(&mut plugin_mut)
            .ok_or_else(|| anyhow::anyhow!("Failed to get mutable reference"))?
            .initialize()
            .await?;
        
        // Store plugin
        let loaded = LoadedPlugin {
            library: Arc::new(library),
            plugin,
            metadata: metadata.clone(),
            path: path.to_owned(),
            health: RwLock::new(HealthStatus {
                healthy: true,
                uptime_seconds: 0,
                tasks_completed: 0,
                tasks_failed: 0,
                memory_usage_mb: 0.0,
            }),
        };
        
        self.plugins.write().insert(name.clone(), loaded);
        
        info!("✅ Plugin '{}' v{} loaded", name, metadata.version);
        Ok(name)
    }
    
    /// Unload plugin
    #[instrument(skip(self))]
    pub async fn unload_plugin(&self, name: &str) -> Result<()> {
        info!("Unloading plugin '{}'", name);
        
        let plugin = self.plugins.write().remove(name)
            .ok_or_else(|| anyhow::anyhow!("Plugin '{}' not found", name))?;
        
        // Shutdown plugin
        let mut plugin_mut = plugin.plugin.clone();
        Arc::get_mut(&mut plugin_mut)
            .ok_or_else(|| anyhow::anyhow!("Failed to get mutable reference"))?
            .shutdown()
            .await?;
        
        // Plugin will be dropped here, unloading the library
        info!("✅ Plugin '{}' unloaded", name);
        Ok(())
    }
    
    /// Reload plugin (unload và load lại)
    pub async fn reload_plugin(&self, name: &str) -> Result<()> {
        let path = {
            let plugins = self.plugins.read();
            plugins.get(name)
                .ok_or_else(|| anyhow::anyhow!("Plugin '{}' not found", name))?
                .path
                .clone()
        };
        
        self.unload_plugin(name).await?;
        self.load_plugin(&path).await?;
        
        Ok(())
    }
    
    /// Execute task on plugin
    pub async fn execute_task(&self, plugin_name: &str, task: PluginTask) -> Result<PluginOutput> {
        let plugin = {
            let plugins = self.plugins.read();
            plugins.get(plugin_name)
                .ok_or_else(|| anyhow::anyhow!("Plugin '{}' not found", plugin_name))?
                .plugin
                .clone()
        };
        
        let output = plugin.execute(task).await?;
        
        // Update health stats
        {
            let plugins = self.plugins.read();
            if let Some(loaded) = plugins.get(plugin_name) {
                let mut health = loaded.health.write();
                match output.status {
                    TaskStatus::Success => health.tasks_completed += 1,
                    TaskStatus::Failed(_) => health.tasks_failed += 1,
                    TaskStatus::Partial(_) => {}
                }
            }
        }
        
        Ok(output)
    }
    
    /// Dispatch event to all plugins
    pub async fn dispatch_event(&self, event: &PluginEvent) -> Result<()> {
        // Implementation depends on plugin capabilities
        debug!("Dispatching event to plugins: {:?}", event);
        Ok(())
    }
    
    /// Health check all plugins
    pub async fn health_check(&self) -> HashMap<String, HealthStatus> {
        let mut health_map = HashMap::new();
        
        let plugins = self.plugins.read();
        for (name, loaded) in plugins.iter() {
            let health = loaded.plugin.health_check();
            health_map.insert(name.clone(), health);
        }
        
        health_map
    }
    
    /// Unload all plugins
    pub async fn unload_all(&self) -> Result<()> {
        let names: Vec<String> = self.plugins.read().keys().cloned().collect();
        
        for name in names {
            if let Err(e) = self.unload_plugin(&name).await {
                error!("Failed to unload plugin '{}': {}", name, e);
            }
        }
        
        Ok(())
    }
    
    /// Cleanup resources
    pub async fn cleanup(&self) -> Result<()> {
        self.unload_all().await
    }
}

/// Macro để export plugin từ dynamic library
#[macro_export]
macro_rules! export_plugin {
    ($plugin_type:ty) => {
        #[no_mangle]
        pub extern "C" fn create_plugin() -> Box<dyn Plugin> {
            Box::new(<$plugin_type>::default())
        }
    };
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;
    
    #[tokio::test]
    async fn test_plugin_manager_creation() {
        let temp = tempdir().unwrap();
        let config = PluginConfig {
            plugin_dir: temp.path().to_owned(),
            auto_load: false,
            hot_reload: false,
        };
        
        let manager = PluginManager::new(config).await.unwrap();
        let plugins = manager.discover_plugins().await.unwrap();
        
        assert_eq!(plugins.len(), 0);
    }
}
