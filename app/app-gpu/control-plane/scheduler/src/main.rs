//! Opus GPU Scheduler - High-Performance GPU Task Scheduler
//! 
//! Features:
//! - gRPC API với mTLS
//! - Backpressure control và QoS
//! - GPU resource aware scheduling
//! - OpenTelemetry tracing
//! - Prometheus metrics

use anyhow::{Context, Result};
use clap::Parser;
use std::sync::Arc;
use tokio::signal;
use tracing::{info, warn, error};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod config;
mod scheduler;
mod gpu_monitor;
mod backpressure;
mod metrics;
mod grpc_server;

use crate::{
    config::Config,
    scheduler::GpuScheduler,
    gpu_monitor::GpuMonitor,
    grpc_server::SchedulerServer,
};

#[derive(Parser)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Configuration file path
    #[arg(short, long, default_value = "config.toml")]
    config: String,
    
    /// Log level
    #[arg(short, long, default_value = "info")]
    log_level: String,
    
    /// Enable development mode (disable mTLS)
    #[arg(short, long)]
    dev_mode: bool,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    
    // Initialize tracing
    init_tracing(&args.log_level)?;
    
    info!("🚀 Starting Opus GPU Scheduler v{}", env!("CARGO_PKG_VERSION"));
    
    // Load configuration
    let config = Config::load(&args.config)
        .with_context(|| format!("Failed to load config from {}", args.config))?;
    
    info!("📋 Configuration loaded: {:?}", config);
    
    // Initialize components
    let gpu_monitor = Arc::new(GpuMonitor::new(&config.gpu).await?);
    let scheduler = Arc::new(GpuScheduler::new(config.clone(), gpu_monitor.clone()).await?);
    
    // Start GPU monitoring background task
    let monitor_handle = {
        let gpu_monitor = gpu_monitor.clone();
        let config = config.clone();
        tokio::spawn(async move {
            if let Err(e) = gpu_monitor.start_monitoring_loop(config.gpu.monitor_interval).await {
                error!("GPU monitoring loop failed: {}", e);
            }
        })
    };
    
    // Start gRPC server
    let server_handle = {
        let scheduler = scheduler.clone();
        let config = config.clone();
        tokio::spawn(async move {
            let server = SchedulerServer::new(scheduler, !args.dev_mode).await?;
            server.serve(config.server.bind_address).await
        })
    };
    
    // Start metrics server
    let metrics_handle = {
        let config = config.clone();
        tokio::spawn(async move {
            crate::metrics::start_metrics_server(config.metrics.bind_address).await
        })
    };
    
    info!("✅ Scheduler started successfully");
    info!("🌐 gRPC server listening on {}", config.server.bind_address);
    info!("📊 Metrics server listening on {}", config.metrics.bind_address);
    
    // Wait for shutdown signal
    select_shutdown(vec![
        monitor_handle,
        server_handle, 
        metrics_handle,
    ]).await?;
    
    info!("🛑 Scheduler shutdown complete");
    Ok(())
}

fn init_tracing(log_level: &str) -> Result<()> {
    let level = log_level.parse()
        .with_context(|| format!("Invalid log level: {}", log_level))?;
    
    tracing_subscriber::registry()
        .with(tracing_subscriber::fmt::layer()
            .with_target(false)
            .with_thread_ids(true)
            .compact())
        .with(tracing_subscriber::filter::LevelFilter::from_level(level))
        .init();
    
    Ok(())
}

async fn select_shutdown(handles: Vec<tokio::task::JoinHandle<Result<()>>>) -> Result<()> {
    tokio::select! {
        _ = signal::ctrl_c() => {
            info!("📡 Received Ctrl+C, shutting down...");
        }
        result = futures::future::try_join_all(handles) => {
            match result {
                Ok(_) => info!("✅ All services completed successfully"),
                Err(e) => error!("❌ Service error: {}", e),
            }
        }
    }
    Ok(())
}
