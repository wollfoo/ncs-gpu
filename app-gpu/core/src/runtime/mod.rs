//! Core Runtime Module
//! 
//! Main event loop và orchestration cho OPUS-GPU

use std::sync::Arc;
use anyhow::Result;
use tokio::sync::{RwLock, mpsc, broadcast};
use tokio::time::{interval, Duration};
use tracing::{info, debug, warn, error, instrument};

use crate::config::Config;
use crate::plugin::{PluginManager, PluginEvent};
use crate::ipc::{IpcManager, Message};
use crate::error::OpusError;

/// Runtime state
#[derive(Debug, Clone, PartialEq)]
pub enum RuntimeState {
    /// Đang khởi tạo
    Initializing,
    /// Đang chạy
    Running,
    /// Đang tạm dừng
    Paused,
    /// Đang shutdown
    Stopping,
    /// Đã dừng
    Stopped,
}

/// Core Runtime structure
pub struct Runtime {
    /// Configuration
    config: Arc<Config>,
    
    /// Current state
    state: Arc<RwLock<RuntimeState>>,
    
    /// Plugin manager
    plugin_manager: Arc<PluginManager>,
    
    /// IPC manager
    ipc_manager: Arc<IpcManager>,
    
    /// Event channels
    event_tx: broadcast::Sender<PluginEvent>,
    event_rx: broadcast::Receiver<PluginEvent>,
    
    /// Shutdown signal
    shutdown_tx: mpsc::Sender<()>,
    shutdown_rx: mpsc::Receiver<()>,
}

impl Runtime {
    /// Tạo runtime instance mới
    #[instrument(skip(config))]
    pub async fn new(config: Config) -> Result<Self> {
        info!("Initializing runtime with config");
        
        let config = Arc::new(config);
        let state = Arc::new(RwLock::new(RuntimeState::Initializing));
        
        // Khởi tạo plugin manager
        let plugin_manager = Arc::new(
            PluginManager::new(config.plugin.clone()).await?
        );
        
        // Khởi tạo IPC manager
        let ipc_manager = Arc::new(
            IpcManager::new(config.ipc.clone()).await?
        );
        
        // Setup event channels
        let (event_tx, event_rx) = broadcast::channel(1024);
        let (shutdown_tx, shutdown_rx) = mpsc::channel(1);
        
        Ok(Self {
            config,
            state,
            plugin_manager,
            ipc_manager,
            event_tx,
            event_rx,
            shutdown_tx,
            shutdown_rx,
        })
    }
    
    /// Run main event loop
    #[instrument(skip(self))]
    pub async fn run(&mut self) -> Result<()> {
        // Update state
        {
            let mut state = self.state.write().await;
            *state = RuntimeState::Running;
        }
        
        info!("Runtime started successfully");
        
        // Load và khởi tạo plugins
        self.load_plugins().await?;
        
        // Start IPC listener
        let ipc_handle = self.start_ipc_handler();
        
        // Start event processor
        let event_handle = self.start_event_processor();
        
        // Start health check task
        let health_handle = self.start_health_check();
        
        // Main event loop
        loop {
            tokio::select! {
                // Process plugin events
                Ok(event) = self.event_rx.recv() => {
                    self.handle_plugin_event(event).await?;
                }
                
                // Check for shutdown signal
                _ = self.shutdown_rx.recv() => {
                    info!("Shutdown signal received");
                    break;
                }
                
                // Handle runtime errors
                else => {
                    tokio::time::sleep(Duration::from_millis(100)).await;
                }
            }
            
            // Check state
            let state = self.state.read().await.clone();
            if state == RuntimeState::Stopping {
                break;
            }
        }
        
        // Cleanup
        self.cleanup().await?;
        
        // Wait for background tasks
        ipc_handle.await??;
        event_handle.await??;
        health_handle.await??;
        
        Ok(())
    }
    
    /// Load plugins từ configured directory
    async fn load_plugins(&self) -> Result<()> {
        info!("Loading plugins from {:?}", self.config.plugin.plugin_dir);
        
        let plugins = self.plugin_manager.discover_plugins().await?;
        info!("Found {} plugins", plugins.len());
        
        for plugin_path in plugins {
            match self.plugin_manager.load_plugin(&plugin_path).await {
                Ok(name) => {
                    info!("✅ Loaded plugin: {}", name);
                    
                    // Notify về plugin loaded
                    let _ = self.event_tx.send(PluginEvent::Loaded {
                        name: name.clone(),
                        version: "1.0.0".to_string(),
                    });
                }
                Err(e) => {
                    error!("❌ Failed to load plugin {:?}: {}", plugin_path, e);
                }
            }
        }
        
        Ok(())
    }
    
    /// Start IPC message handler
    fn start_ipc_handler(&self) -> tokio::task::JoinHandle<Result<()>> {
        let ipc = self.ipc_manager.clone();
        let event_tx = self.event_tx.clone();
        
        tokio::spawn(async move {
            info!("Starting IPC handler");
            
            loop {
                match ipc.receive_message().await {
                    Ok(Some(msg)) => {
                        debug!("Received IPC message: {:?}", msg);
                        
                        // Convert to plugin event
                        let event = PluginEvent::MessageReceived {
                            source: msg.source,
                            payload: msg.payload,
                        };
                        
                        let _ = event_tx.send(event);
                    }
                    Ok(None) => {
                        // No message available
                        tokio::time::sleep(Duration::from_millis(10)).await;
                    }
                    Err(e) => {
                        error!("IPC error: {}", e);
                        break;
                    }
                }
            }
            
            Ok(())
        })
    }
    
    /// Start event processor
    fn start_event_processor(&self) -> tokio::task::JoinHandle<Result<()>> {
        let plugins = self.plugin_manager.clone();
        let mut event_rx = self.event_tx.subscribe();
        
        tokio::spawn(async move {
            info!("Starting event processor");
            
            while let Ok(event) = event_rx.recv().await {
                debug!("Processing event: {:?}", event);
                
                // Dispatch event to plugins
                if let Err(e) = plugins.dispatch_event(&event).await {
                    error!("Failed to dispatch event: {}", e);
                }
            }
            
            Ok(())
        })
    }
    
    /// Start health check task
    fn start_health_check(&self) -> tokio::task::JoinHandle<Result<()>> {
        let plugins = self.plugin_manager.clone();
        let state = self.state.clone();
        
        tokio::spawn(async move {
            let mut ticker = interval(Duration::from_secs(30));
            
            loop {
                ticker.tick().await;
                
                // Check runtime state
                let current_state = state.read().await.clone();
                if current_state == RuntimeState::Stopping {
                    break;
                }
                
                // Health check plugins
                let health = plugins.health_check().await;
                debug!("Health check: {:?}", health);
            }
            
            Ok(())
        })
    }
    
    /// Handle plugin events
    async fn handle_plugin_event(&self, event: PluginEvent) -> Result<()> {
        match event {
            PluginEvent::Loaded { name, version } => {
                info!("Plugin loaded: {} v{}", name, version);
            }
            PluginEvent::Unloaded { name } => {
                info!("Plugin unloaded: {}", name);
            }
            PluginEvent::Error { plugin, error } => {
                error!("Plugin error from {}: {}", plugin, error);
            }
            PluginEvent::MessageReceived { source, payload } => {
                debug!("Message from {}: {} bytes", source, payload.len());
                
                // Forward to IPC
                self.ipc_manager.send_message(Message {
                    source: "runtime".to_string(),
                    destination: source,
                    payload,
                }).await?;
            }
        }
        
        Ok(())
    }
    
    /// Graceful shutdown
    #[instrument(skip(self))]
    pub async fn shutdown(&mut self) -> Result<()> {
        info!("Initiating graceful shutdown");
        
        // Update state
        {
            let mut state = self.state.write().await;
            *state = RuntimeState::Stopping;
        }
        
        // Unload all plugins
        self.plugin_manager.unload_all().await?;
        
        // Shutdown IPC
        self.ipc_manager.shutdown().await?;
        
        // Update state
        {
            let mut state = self.state.write().await;
            *state = RuntimeState::Stopped;
        }
        
        info!("Runtime shutdown complete");
        Ok(())
    }
    
    /// Cleanup resources
    async fn cleanup(&self) -> Result<()> {
        debug!("Cleaning up runtime resources");
        
        // Cleanup plugins
        self.plugin_manager.cleanup().await?;
        
        // Cleanup IPC
        self.ipc_manager.cleanup().await?;
        
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_runtime_state_transitions() {
        // Test state transitions
        let state = Arc::new(RwLock::new(RuntimeState::Initializing));
        
        {
            let mut s = state.write().await;
            *s = RuntimeState::Running;
        }
        
        assert_eq!(*state.read().await, RuntimeState::Running);
    }
}
