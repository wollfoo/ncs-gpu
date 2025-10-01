// GPU Worker - High-performance mining worker written in Rust

use anyhow::Result;
use clap::Parser;
use once_cell::sync::Lazy;
use std::sync::Arc;
use tokio::signal;
use tracing::{error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod config;
mod gpu;
mod mining;
mod metrics;
mod pool;
mod worker;

use crate::config::Config;
use crate::metrics::MetricsServer;
use crate::worker::WorkerManager;

/// GPU Mining Worker - Công nhân khai thác GPU hiệu năng cao
#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Configuration file path
    #[arg(short, long, default_value = "worker.toml")]
    config: String,
    
    /// GPU index to use (-1 for all GPUs)
    #[arg(short, long, default_value = "-1")]
    gpu_index: i32,
    
    /// Enable debug logging
    #[arg(short, long)]
    debug: bool,
    
    /// Metrics server port
    #[arg(short, long, default_value = "9090")]
    metrics_port: u16,
}

static CONFIG: Lazy<Arc<Config>> = Lazy::new(|| {
    Arc::new(Config::default())
});

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    
    // Initialize tracing
    init_tracing(args.debug);
    
    info!("🚀 Starting GPU Mining Worker v2.0...");
    
    // Load configuration
    let config = match Config::load(&args.config) {
        Ok(cfg) => Arc::new(cfg),
        Err(e) => {
            warn!("Failed to load config file: {}, using defaults", e);
            CONFIG.clone()
        }
    };
    
    // Initialize GPU subsystem
    info!("🎮 Initializing GPU subsystem...");
    let gpu_manager = gpu::Manager::new()?;
    let available_gpus = gpu_manager.enumerate_devices()?;
    
    info!("✅ Found {} GPU(s):", available_gpus.len());
    for (idx, gpu) in available_gpus.iter().enumerate() {
        info!("  GPU {}: {} | {} MB | Compute: {}", 
            idx, gpu.name, gpu.memory_mb, gpu.compute_capability);
    }
    
    // Select GPU(s) to use
    let selected_gpus = if args.gpu_index >= 0 {
        vec![args.gpu_index as usize]
    } else {
        (0..available_gpus.len()).collect()
    };
    
    info!("📊 Using GPU(s): {:?}", selected_gpus);
    
    // Start metrics server
    let metrics_server = MetricsServer::new(args.metrics_port);
    let metrics_handle = tokio::spawn(async move {
        if let Err(e) = metrics_server.run().await {
            error!("Metrics server error: {}", e);
        }
    });
    
    // Initialize worker manager
    let worker_manager = WorkerManager::new(
        config.clone(),
        gpu_manager,
        selected_gpus,
    )?;
    
    // Start mining workers
    info!("⛏️ Starting mining workers...");
    let worker_handle = tokio::spawn(async move {
        if let Err(e) = worker_manager.run().await {
            error!("Worker manager error: {}", e);
        }
    });
    
    info!("✅ GPU Worker started successfully!");
    info!("📈 Metrics available at http://localhost:{}/metrics", args.metrics_port);
    
    // Wait for shutdown signal
    shutdown_signal().await;
    
    info!("🛑 Shutting down GPU Worker...");
    
    // Graceful shutdown
    worker_handle.abort();
    metrics_handle.abort();
    
    // Wait a bit for cleanup
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
    
    info!("✅ GPU Worker shutdown complete");
    
    Ok(())
}

fn init_tracing(debug: bool) {
    let env_filter = if debug {
        "debug"
    } else {
        "info"
    };
    
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| env_filter.into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();
}

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
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
