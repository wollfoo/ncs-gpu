use anyhow::Result;
use clap::Parser;
use opus_gpu_bus::MessageBus;
use opus_gpu_config::AppConfig;
use std::sync::Arc;
use tokio::signal;
use tracing::{error, info, warn};

mod app;
mod cli;

use app::OpusGpuApp;
use cli::Cli;

/// OPUS-GPU - High-performance GPU mining platform
#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing/logging
    init_tracing()?;

    info!("🚀 Starting OPUS-GPU v{}", env!("CARGO_PKG_VERSION"));

    // Parse command line arguments
    let cli = Cli::parse();

    // Load configuration
    let config = AppConfig::load(&cli.config_path).await?;
    info!("📋 Configuration loaded from: {}", cli.config_path);

    // Initialize message bus
    let message_bus = Arc::new(MessageBus::new(config.bus.clone()).await?);
    info!("🚌 Message bus initialized");

    // Create and start the application
    let app = OpusGpuApp::new(config, message_bus.clone()).await?;

    // Setup graceful shutdown
    let shutdown = setup_shutdown_handler();

    // Run the application
    tokio::select! {
        result = app.run() => {
            match result {
                Ok(_) => info!("✅ Application completed successfully"),
                Err(e) => error!("❌ Application error: {}", e),
            }
        }
        _ = shutdown => {
            warn!("⚠️ Shutdown signal received, stopping application...");
            if let Err(e) = app.shutdown().await {
                error!("❌ Error during shutdown: {}", e);
            } else {
                info!("✅ Application shutdown completed");
            }
        }
    }

    Ok(())
}

/// Initialize tracing/logging system
fn init_tracing() -> Result<()> {
    use tracing_subscriber::{fmt, layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("opus_gpu=info,warn"));

    tracing_subscriber::registry()
        .with(fmt::layer().with_target(false).with_thread_ids(true))
        .with(env_filter)
        .init();

    Ok(())
}

/// Setup graceful shutdown handler
async fn setup_shutdown_handler() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("Failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("Failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
}