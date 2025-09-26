//! **Core Engine Implementation** (triển khai động cơ lõi – module chính hệ thống)

use anyhow::{Context, Result};
use dashmap::DashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tokio::sync::{broadcast, RwLock};
use tracing::{debug, error, info, warn};

use crate::core::{
    gpu_pool::GpuPool,
    plugin_api::{Plugin, PluginContext, PluginInfo},
    scheduler::Scheduler,
};
use crate::utils::config::Config;

/// **Engine State** (trạng thái động cơ – tình trạng hệ thống)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EngineState {
    /// **Initializing** (đang khởi tạo – chuẩn bị hệ thống)
    Initializing,
    /// **Running** (đang chạy – hoạt động bình thường)
    Running,
    /// **Stopping** (đang dừng – kết thúc hoạt động)
    Stopping,
    /// **Stopped** (đã dừng – ngừng hoạt động)
    Stopped,
}

/// **Main Engine** (động cơ chính – module điều khiển trung tâm)
pub struct Engine {
    /// Configuration
    config: Arc<Config>,
    /// GPU resource pool
    gpu_pool: Arc<GpuPool>,
    /// Task scheduler
    scheduler: Arc<Scheduler>,
    /// Loaded plugins
    plugins: Arc<DashMap<String, Box<dyn Plugin>>>,
    /// Engine state
    state: Arc<RwLock<EngineState>>,
    /// Plugin directory
    plugin_dir: PathBuf,
    /// Metrics server handle
    metrics_handle: Option<tokio::task::JoinHandle<()>>,
}

impl Engine {
    /// **Create new engine instance** (tạo thể hiện động cơ mới – khởi tạo hệ thống)
    pub async fn new(config_path: &Path, plugin_dir: &Path) -> Result<Self> {
        info!("🔧 Initializing engine with config: {}", config_path.display());

        // Load configuration
        let config = Config::load(config_path)
            .with_context(|| format!("Failed to load config from {}", config_path.display()))?;
        let config = Arc::new(config);

        // Initialize GPU pool
        let gpu_pool = GpuPool::new(config.gpu.clone())
            .await
            .context("Failed to initialize GPU pool")?;
        let gpu_pool = Arc::new(gpu_pool);

        info!("🎮 Detected {} GPUs", gpu_pool.device_count());

        // Initialize scheduler
        let scheduler = Scheduler::new(config.scheduler.clone());
        let scheduler = Arc::new(scheduler);

        // Create engine instance
        let engine = Self {
            config,
            gpu_pool,
            scheduler,
            plugins: Arc::new(DashMap::new()),
            state: Arc::new(RwLock::new(EngineState::Initializing)),
            plugin_dir: plugin_dir.to_path_buf(),
            metrics_handle: None,
        };

        // Load plugins
        engine.load_plugins().await?;

        Ok(engine)
    }

    /// **Load plugins from directory** (tải plugin từ thư mục – nạp module mở rộng)
    async fn load_plugins(&self) -> Result<()> {
        info!("🔌 Loading plugins from: {}", self.plugin_dir.display());

        // Read plugin manifest
        let manifest_path = self.plugin_dir.join("manifest.toml");
        if !manifest_path.exists() {
            warn!("⚠️ No plugin manifest found at {}", manifest_path.display());
            return Ok(());
        }

        // TODO: Implement plugin loading
        // For now, we'll load built-in plugins

        // Load mining plugin
        self.load_builtin_mining_plugin().await?;

        // Load metrics plugin
        self.load_builtin_metrics_plugin().await?;

        // Load cloaking plugin if enabled
        if self.config.features.cloaking {
            self.load_builtin_cloaking_plugin().await?;
        }

        info!("✅ Loaded {} plugins", self.plugins.len());
        Ok(())
    }

    /// **Load built-in mining plugin** (tải plugin khai thác tích hợp – nạp module đào coin)
    async fn load_builtin_mining_plugin(&self) -> Result<()> {
        use crate::plugins::mining::MiningPlugin;

        let plugin = MiningPlugin::new(self.config.mining.clone())?;
        let info = plugin.info();
        
        info!("📦 Loading plugin: {} v{}", info.name, info.version);
        self.plugins.insert(info.name.clone(), Box::new(plugin));
        
        Ok(())
    }

    /// **Load built-in metrics plugin** (tải plugin metrics tích hợp – nạp module giám sát)
    async fn load_builtin_metrics_plugin(&self) -> Result<()> {
        use crate::plugins::metrics::MetricsPlugin;

        let plugin = MetricsPlugin::new()?;
        let info = plugin.info();
        
        info!("📦 Loading plugin: {} v{}", info.name, info.version);
        self.plugins.insert(info.name.clone(), Box::new(plugin));
        
        Ok(())
    }

    /// **Load built-in cloaking plugin** (tải plugin cloaking tích hợp – nạp module ngụy trang)
    async fn load_builtin_cloaking_plugin(&self) -> Result<()> {
        use crate::plugins::cloaking::CloakingPlugin;

        let plugin = CloakingPlugin::new()?;
        let info = plugin.info();
        
        info!("📦 Loading plugin: {} v{}", info.name, info.version);
        self.plugins.insert(info.name.clone(), Box::new(plugin));
        
        Ok(())
    }

    /// **Set GPU count** (đặt số lượng GPU – cấu hình card đồ họa)
    pub fn set_gpu_count(&mut self, count: usize) -> Result<()> {
        // This would be implemented properly
        info!("🎮 Setting GPU count to: {}", count);
        Ok(())
    }

    /// **Start metrics server** (khởi động server metrics – chạy máy chủ giám sát)
    pub async fn start_metrics_server(&mut self, port: u16) -> Result<()> {
        use crate::plugins::metrics::start_metrics_server;

        let handle = tokio::spawn(async move {
            if let Err(e) = start_metrics_server(port).await {
                error!("❌ Metrics server error: {}", e);
            }
        });

        self.metrics_handle = Some(handle);
        Ok(())
    }

    /// **Run the engine** (chạy động cơ – vận hành hệ thống)
    pub async fn run(&mut self, mut shutdown: broadcast::Receiver<()>) -> Result<()> {
        // Update state
        {
            let mut state = self.state.write().await;
            *state = EngineState::Running;
        }

        info!("🚀 Engine running");

        // Create plugin context
        let context = Arc::new(PluginContext {
            gpu_pool: self.gpu_pool.clone(),
            scheduler: self.scheduler.clone(),
            config: self.config.clone(),
        });

        // Initialize all plugins
        for plugin in self.plugins.iter() {
            let (name, plugin) = plugin.pair();
            info!("🔧 Initializing plugin: {}", name);
            
            if let Err(e) = plugin.initialize(context.clone()).await {
                error!("❌ Failed to initialize plugin {}: {}", name, e);
                return Err(e);
            }
        }

        // Start scheduler
        self.scheduler.start().await?;

        // Main engine loop
        loop {
            tokio::select! {
                _ = shutdown.recv() => {
                    info!("🛑 Shutdown signal received");
                    break;
                }
                _ = tokio::time::sleep(tokio::time::Duration::from_secs(1)) => {
                    // Periodic maintenance tasks
                    self.maintenance_tick().await?;
                }
            }
        }

        // Shutdown sequence
        self.shutdown().await?;

        Ok(())
    }

    /// **Periodic maintenance** (bảo trì định kỳ – kiểm tra hệ thống)
    async fn maintenance_tick(&self) -> Result<()> {
        // Check GPU health
        if let Err(e) = self.gpu_pool.health_check().await {
            warn!("⚠️ GPU health check failed: {}", e);
        }

        // Update metrics
        // TODO: Implement metrics update

        Ok(())
    }

    /// **Shutdown engine** (tắt động cơ – dừng hệ thống)
    async fn shutdown(&mut self) -> Result<()> {
        info!("🔄 Starting engine shutdown");

        // Update state
        {
            let mut state = self.state.write().await;
            *state = EngineState::Stopping;
        }

        // Stop scheduler
        self.scheduler.stop().await?;

        // Shutdown all plugins
        for plugin in self.plugins.iter() {
            let (name, plugin) = plugin.pair();
            info!("🔌 Shutting down plugin: {}", name);
            
            if let Err(e) = plugin.shutdown().await {
                error!("❌ Error shutting down plugin {}: {}", name, e);
            }
        }

        // Stop metrics server
        if let Some(handle) = self.metrics_handle.take() {
            handle.abort();
        }

        // Update state
        {
            let mut state = self.state.write().await;
            *state = EngineState::Stopped;
        }

        info!("✅ Engine shutdown complete");
        Ok(())
    }
}