use anyhow::Result;
use opus_gpu_api_grpc::GrpcServer;
use opus_gpu_api_rest::RestServer;
use opus_gpu_api_websocket::WebSocketServer;
use opus_gpu_bus::{Message, MessageBus, MessageHandler};
use opus_gpu_config::AppConfig;
use opus_gpu_gpu::GpuContext;
use opus_gpu_mining::MiningEngine;
use opus_gpu_monitor::MonitoringService;
use opus_gpu_plugin_loader::PluginLoader;
use opus_gpu_plugin_registry::PluginRegistry;
use opus_gpu_pool::PoolManager;
use opus_gpu_storage::{Storage, StorageFactory};
use opus_gpu_wallet::WalletManager;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{error, info, warn};
use uuid::Uuid;

// Import health monitoring
mod health;
use health::{HealthMonitor, HealthConfig, HealthCheck, ComponentHealth, SystemHealth};

/// Main application container that manages all components
pub struct OpusGpuApp {
    id: Uuid,
    config: AppConfig,
    message_bus: Arc<MessageBus>,

    // Infrastructure layer
    gpu_context: Arc<RwLock<GpuContext>>,
    storage: Arc<dyn Storage>,
    health_monitor: Arc<HealthMonitor>,

    // Core services
    mining_engine: Arc<MiningEngine>,
    pool_manager: Arc<PoolManager>,
    wallet_manager: Arc<WalletManager>,
    monitoring_service: Arc<MonitoringService>,

    // Plugin system
    plugin_loader: Arc<PluginLoader>,
    plugin_registry: Arc<RwLock<PluginRegistry>>,

    // API servers
    rest_server: RestServer,
    websocket_server: WebSocketServer,
    grpc_server: GrpcServer,

    // Application state
    is_running: Arc<RwLock<bool>>,
    shutdown_signal: Arc<tokio::sync::Notify>,
}

impl OpusGpuApp {
    /// Create a new OPUS-GPU application instance
    pub async fn new(
        config: AppConfig,
        message_bus: Arc<MessageBus>,
    ) -> Result<Self> {
        let app_id = Uuid::new_v4();
        info!("🏗️ Initializing OPUS-GPU application (ID: {})", app_id);

        // Initialize storage manager
        let storage_manager = Arc::new(
            StorageManager::new(&config.storage).await?
        );
        info!("💾 Storage manager initialized");

        // Initialize wallet manager
        let wallet_manager = Arc::new(
            WalletManager::new(&config.wallet, storage_manager.clone()).await?
        );
        info!("💰 Wallet manager initialized");

        // Initialize pool manager
        let pool_manager = Arc::new(
            PoolManager::new(&config.pool, message_bus.clone()).await?
        );
        info!("🏊 Pool manager initialized");

        // Initialize mining engine
        let mining_engine = Arc::new(
            MiningEngine::new(
                &config.mining,
                message_bus.clone(),
                pool_manager.clone(),
            ).await?
        );
        info!("⛏️ Mining engine initialized");

        // Initialize monitoring service
        let monitoring_service = Arc::new(
            MonitoringService::new(&config.monitoring, message_bus.clone()).await?
        );
        info!("📊 Monitoring service initialized");

        // Initialize plugin system
        let plugin_registry = Arc::new(RwLock::new(PluginRegistry::new()));
        let plugin_loader = Arc::new(
            PluginLoader::new(&config.plugins, plugin_registry.clone()).await?
        );
        info!("🔌 Plugin system initialized");

        // Initialize API servers
        let rest_server = RestServer::new(
            config.api.rest.clone(),
            message_bus.clone(),
            mining_engine.clone(),
        ).await?;

        let websocket_server = WebSocketServer::new(
            config.api.websocket.clone(),
            message_bus.clone(),
        ).await?;

        let grpc_server = GrpcServer::new(
            config.api.grpc.clone(),
            message_bus.clone(),
            mining_engine.clone(),
            pool_manager.clone(),
            wallet_manager.clone(),
        ).await?;

        info!("🌐 API servers initialized");

        Ok(Self {
            id: app_id,
            config,
            message_bus,
            mining_engine,
            pool_manager,
            wallet_manager,
            monitoring_service,
            storage_manager,
            plugin_loader,
            plugin_registry,
            rest_server,
            websocket_server,
            grpc_server,
            is_running: Arc::new(RwLock::new(false)),
        })
    }

    /// Start the application and all its components
    pub async fn run(&self) -> Result<()> {
        info!("🚀 Starting OPUS-GPU application");

        // Mark as running
        *self.is_running.write().await = true;

        // Setup message bus handlers
        self.setup_message_handlers().await?;

        // Load and initialize plugins
        if !self.config.plugins.disabled {
            self.plugin_loader.load_plugins().await?;
            info!("🔌 Plugins loaded");
        }

        // Start core services
        tokio::try_join!(
            self.mining_engine.start(),
            self.pool_manager.start(),
            self.monitoring_service.start(),
        )?;

        // Start API servers
        tokio::try_join!(
            self.rest_server.start(),
            self.websocket_server.start(),
            self.grpc_server.start(),
        )?;

        info!("✅ All services started successfully");

        // Keep running until shutdown
        while *self.is_running.read().await {
            tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
        }

        Ok(())
    }

    /// Shutdown the application gracefully
    pub async fn shutdown(&self) -> Result<()> {
        info!("🛑 Shutting down OPUS-GPU application");

        // Mark as not running
        *self.is_running.write().await = false;

        // Stop API servers
        tokio::try_join!(
            self.rest_server.shutdown(),
            self.websocket_server.shutdown(),
            self.grpc_server.shutdown(),
        )?;

        // Stop core services
        tokio::try_join!(
            self.mining_engine.stop(),
            self.pool_manager.stop(),
            self.monitoring_service.stop(),
        )?;

        // Unload plugins
        if !self.config.plugins.disabled {
            let mut registry = self.plugin_registry.write().await;
            registry.unload_all_plugins().await?;
        }

        info!("✅ Application shutdown complete");
        Ok(())
    }

    /// Setup message bus event handlers
    async fn setup_message_handlers(&self) -> Result<()> {
        let bus = &self.message_bus;

        // Mining events
        let mining_engine = self.mining_engine.clone();
        bus.subscribe("mining.*", Box::new(move |msg: &Message| {
            let engine = mining_engine.clone();
            Box::pin(async move {
                if let Err(e) = engine.handle_message(msg).await {
                    error!("Error handling mining message: {}", e);
                }
            })
        })).await?;

        // Pool events
        let pool_manager = self.pool_manager.clone();
        bus.subscribe("pool.*", Box::new(move |msg: &Message| {
            let manager = pool_manager.clone();
            Box::pin(async move {
                if let Err(e) = manager.handle_message(msg).await {
                    error!("Error handling pool message: {}", e);
                }
            })
        })).await?;

        // Monitoring events
        let monitoring_service = self.monitoring_service.clone();
        bus.subscribe("monitor.*", Box::new(move |msg: &Message| {
            let service = monitoring_service.clone();
            Box::pin(async move {
                if let Err(e) = service.handle_message(msg).await {
                    error!("Error handling monitor message: {}", e);
                }
            })
        })).await?;

        info!("📡 Message bus handlers configured");
        Ok(())
    }

    /// Get application ID
    pub fn id(&self) -> Uuid {
        self.id
    }

    /// Get application configuration
    pub fn config(&self) -> &AppConfig {
        &self.config
    }

    /// Get message bus reference
    pub fn message_bus(&self) -> Arc<MessageBus> {
        self.message_bus.clone()
    }
}