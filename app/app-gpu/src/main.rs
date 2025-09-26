/*!
# App-GPU: High-Performance GPU Mining with Event-Driven Architecture

**Kiến trúc Event-Driven** (hướng sự kiện) với **Rust + NATS + CUDA** stack
cho **GPU mining operations** (hoạt động khai thác GPU).

## Core Architecture

- **Event Bus**: NATS streaming cho **high-throughput messaging**
- **GPU Engine**: CUDA integration với **async processing**
- **Worker Pools**: Tokio async workers cho **parallel execution**
- **Security**: Process isolation và **memory encryption**

## Performance Targets

- **Startup**: 100-200ms (vs 15-30s hiện tại)
- **GPU Utilization**: >80% (vs 60-70% hiện tại)
- **Event Throughput**: >10K events/sec
- **Latency**: <10ms p95 processing time
*/

use anyhow::{Context, Result};
use clap::Parser;
use color_eyre::eyre::Report;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::signal;
use tracing::{error, info, warn};

mod config;
mod core;
mod gpu;
mod monitoring;
mod resource;
mod stealth;
mod utils;
mod workers;

use crate::config::AppConfig;
use crate::core::EventBus;
use crate::gpu::GpuEngine;
use crate::monitoring::MetricsCollector;
use crate::resource::ResourceManager;
use crate::utils::logging::init_logging;
use crate::workers::WorkerPool;

/// **App-GPU Command Line Interface**
#[derive(Parser, Debug)]
#[command(name = "app-gpu")]
#[command(about = "High-performance GPU mining với event-driven architecture")]
#[command(version = env!("CARGO_PKG_VERSION"))]
struct Cli {
    /// **Configuration file path** (đường dẫn file cấu hình)
    #[arg(short, long, default_value = "config.toml")]
    config: String,

    /// **NATS server URL** (URL máy chủ NATS)
    #[arg(long, env = "NATS_URL", default_value = "nats://localhost:4222")]
    nats_url: String,

    /// **GPU indices to use** (chỉ số GPU sử dụng)
    #[arg(long, env = "GPU_INDICES", value_delimiter = ',')]
    gpu_indices: Option<Vec<usize>>,

    /// **Enable stealth mode** (bật chế độ ẩn danh)
    #[arg(long, env = "ENABLE_STEALTH_MODE")]
    stealth: bool,

    /// **Metrics port** (cổng metrics)
    #[arg(long, env = "METRICS_PORT", default_value = "9090")]
    metrics_port: u16,

    /// **Log level** (mức độ log)
    #[arg(long, env = "LOG_LEVEL", default_value = "info")]
    log_level: String,
}

/// **Application State** (trạng thái ứng dụng)
struct AppState {
    config: AppConfig,
    event_bus: EventBus,
    gpu_engine: GpuEngine,
    resource_manager: ResourceManager,
    worker_pool: WorkerPool,
    metrics_collector: MetricsCollector,
    shutdown_signal: Arc<AtomicBool>,
}

impl AppState {
    /// **Initialize Application State** (khởi tạo trạng thái ứng dụng)
    async fn new(cli: Cli) -> Result<Self> {
        info!("🚀 Initializing App-GPU với event-driven architecture...");

        // Load configuration
        let config = AppConfig::load(&cli.config)
            .with_context(|| format!("Failed to load config from {}", cli.config))?;

        // Initialize event bus with NATS
        info!("📡 Connecting to NATS at {}", cli.nats_url);
        let event_bus = EventBus::new(&cli.nats_url)
            .await
            .context("Failed to initialize NATS event bus")?;

        // Initialize GPU engine
        info!("🎮 Initializing GPU engine...");
        let gpu_indices = cli.gpu_indices.unwrap_or_else(|| {
            // Auto-detect available GPUs
            (0..detect_gpu_count()).collect()
        });
        let gpu_engine = GpuEngine::new(gpu_indices)
            .await
            .context("Failed to initialize GPU engine")?;

        // Initialize resource manager
        info!("📊 Initializing resource manager...");
        let resource_manager = ResourceManager::new(&config.resource)
            .context("Failed to initialize resource manager")?;

        // Initialize worker pool
        info!("👷 Initializing worker pool...");
        let worker_pool = WorkerPool::new(
            event_bus.clone(),
            gpu_engine.clone(),
            resource_manager.clone(),
        )
        .await
        .context("Failed to initialize worker pool")?;

        // Initialize metrics collector
        info!("📈 Initializing metrics collector on port {}...", cli.metrics_port);
        let metrics_collector = MetricsCollector::new(cli.metrics_port)
            .context("Failed to initialize metrics collector")?;

        let shutdown_signal = Arc::new(AtomicBool::new(false));

        Ok(AppState {
            config,
            event_bus,
            gpu_engine,
            resource_manager,
            worker_pool,
            metrics_collector,
            shutdown_signal,
        })
    }

    /// **Start Application Services** (khởi động các dịch vụ ứng dụng)
    async fn start(&mut self) -> Result<()> {
        info!("🎯 Starting App-GPU services...");

        // Start metrics collection
        self.metrics_collector.start().await
            .context("Failed to start metrics collector")?;

        // Start resource manager
        self.resource_manager.start().await
            .context("Failed to start resource manager")?;

        // Start GPU engine
        self.gpu_engine.start().await
            .context("Failed to start GPU engine")?;

        // Start worker pool
        self.worker_pool.start().await
            .context("Failed to start worker pool")?;

        // Start event bus processing
        self.event_bus.start().await
            .context("Failed to start event bus")?;

        info!("✅ All services started successfully!");
        Ok(())
    }

    /// **Shutdown Application Services** (tắt các dịch vụ ứng dụng)
    async fn shutdown(&mut self) -> Result<()> {
        info!("🛑 Shutting down App-GPU services...");

        // Set shutdown signal
        self.shutdown_signal.store(true, Ordering::SeqCst);

        // Graceful shutdown in reverse order
        if let Err(e) = self.worker_pool.shutdown().await {
            error!("Failed to shutdown worker pool: {}", e);
        }

        if let Err(e) = self.gpu_engine.shutdown().await {
            error!("Failed to shutdown GPU engine: {}", e);
        }

        if let Err(e) = self.resource_manager.shutdown().await {
            error!("Failed to shutdown resource manager: {}", e);
        }

        if let Err(e) = self.event_bus.shutdown().await {
            error!("Failed to shutdown event bus: {}", e);
        }

        if let Err(e) = self.metrics_collector.shutdown().await {
            error!("Failed to shutdown metrics collector: {}", e);
        }

        info!("✅ Graceful shutdown completed");
        Ok(())
    }

    /// **Health Check** (kiểm tra sức khỏe)
    async fn health_check(&self) -> bool {
        let event_bus_healthy = self.event_bus.is_healthy().await;
        let gpu_healthy = self.gpu_engine.is_healthy().await;
        let resource_healthy = self.resource_manager.is_healthy().await;
        let worker_healthy = self.worker_pool.is_healthy().await;

        event_bus_healthy && gpu_healthy && resource_healthy && worker_healthy
    }
}

/// **Main Application Entry Point** (điểm vào chính của ứng dụng)
#[tokio::main]
async fn main() -> Result<(), Report> {
    color_eyre::install()?;

    let cli = Cli::parse();

    // Initialize logging
    init_logging(&cli.log_level)?;

    info!("🚀 Starting App-GPU v{}", env!("CARGO_PKG_VERSION"));
    info!("📝 Configuration: {}", cli.config);
    info!("📡 NATS URL: {}", cli.nats_url);
    info!("🎮 GPU Indices: {:?}", cli.gpu_indices);
    info!("🔒 Stealth Mode: {}", cli.stealth);

    // Initialize application state
    let mut app_state = AppState::new(cli).await
        .context("Failed to initialize application")?;

    // Start all services
    app_state.start().await
        .context("Failed to start application services")?;

    // Setup signal handlers
    let shutdown_signal = app_state.shutdown_signal.clone();
    tokio::spawn(async move {
        signal::ctrl_c().await.expect("Failed to listen for Ctrl+C");
        warn!("📟 Received Ctrl+C signal, initiating graceful shutdown...");
        shutdown_signal.store(true, Ordering::SeqCst);
    });

    // Main event loop
    info!("🔄 Entering main event loop...");
    let mut health_check_interval = tokio::time::interval(
        std::time::Duration::from_secs(30)
    );

    loop {
        tokio::select! {
            _ = health_check_interval.tick() => {
                if !app_state.health_check().await {
                    error!("❌ Health check failed, initiating shutdown");
                    break;
                }
                info!("💚 Health check passed");
            }
            
            _ = tokio::time::sleep(std::time::Duration::from_secs(1)) => {
                if app_state.shutdown_signal.load(Ordering::SeqCst) {
                    break;
                }
            }
        }
    }

    // Graceful shutdown
    app_state.shutdown().await
        .context("Failed to shutdown application")?;

    info!("👋 App-GPU shutdown complete");
    Ok(())
}

/// **Detect GPU Count** (phát hiện số lượng GPU)
fn detect_gpu_count() -> usize {
    match nvidia_ml_rs::Nvml::init() {
        Ok(nvml) => {
            match nvml.device_count() {
                Ok(count) => {
                    info!("🎮 Detected {} GPU(s)", count);
                    count as usize
                }
                Err(e) => {
                    warn!("⚠️ Failed to get GPU count: {}", e);
                    0
                }
            }
        }
        Err(e) => {
            warn!("⚠️ Failed to initialize NVML: {}", e);
            0
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cli_parsing() {
        let cli = Cli::parse_from(&[
            "app-gpu",
            "--config", "test.toml",
            "--nats-url", "nats://test:4222",
            "--gpu-indices", "0,1,2",
            "--stealth",
            "--metrics-port", "9091",
            "--log-level", "debug",
        ]);

        assert_eq!(cli.config, "test.toml");
        assert_eq!(cli.nats_url, "nats://test:4222");
        assert_eq!(cli.gpu_indices, Some(vec![0, 1, 2]));
        assert!(cli.stealth);
        assert_eq!(cli.metrics_port, 9091);
        assert_eq!(cli.log_level, "debug");
    }

    #[tokio::test]
    async fn test_gpu_detection() {
        let count = detect_gpu_count();
        // Should not panic and return a reasonable value
        assert!(count <= 16); // Reasonable upper bound
    }
}
