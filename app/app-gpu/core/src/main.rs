//! OPUS-GPU Core Runtime
//! 
//! High-performance GPU computing framework với plugin architecture

use anyhow::Result;
use color_eyre::eyre::WrapErr;
use tracing::{info, warn, error};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod runtime;
mod plugin;
mod ipc;
mod config;
mod error;

use runtime::Runtime;
use config::Config;

#[tokio::main]
async fn main() -> Result<()> {
    // Khởi tạo error reporting
    color_eyre::install()?;
    
    // Setup logging với tracing
    setup_logging()?;
    
    info!("🚀 Starting OPUS-GPU v2.0 Core Runtime");
    info!("📝 Loading configuration...");
    
    // Load configuration
    let config = Config::load().wrap_err("Failed to load configuration")?;
    info!("✅ Configuration loaded successfully");
    
    // Khởi tạo runtime
    info!("🔧 Initializing runtime...");
    let mut runtime = Runtime::new(config).await?;
    
    // Setup signal handlers cho graceful shutdown
    let shutdown = setup_signal_handlers();
    
    // Run main event loop
    info!("🏃 Starting main event loop");
    tokio::select! {
        result = runtime.run() => {
            match result {
                Ok(_) => info!("✅ Runtime completed successfully"),
                Err(e) => error!("❌ Runtime error: {:?}", e),
            }
        }
        _ = shutdown => {
            warn!("⚠️ Shutdown signal received");
            runtime.shutdown().await?;
        }
    }
    
    info!("👋 OPUS-GPU shutdown complete");
    Ok(())
}

/// Setup structured logging với tracing
fn setup_logging() -> Result<()> {
    let fmt_layer = tracing_subscriber::fmt::layer()
        .with_target(true)
        .with_thread_ids(true)
        .with_thread_names(true)
        .with_file(true)
        .with_line_number(true);
    
    let filter_layer = tracing_subscriber::EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info"));
    
    tracing_subscriber::registry()
        .with(filter_layer)
        .with(fmt_layer)
        .init();
    
    Ok(())
}

/// Setup signal handlers cho graceful shutdown
async fn setup_signal_handlers() {
    tokio::signal::ctrl_c()
        .await
        .expect("Failed to setup signal handler");
}
