//! Opus GPU Executor - High-Performance CUDA Execution Engine
//!
//! Features:
//! - CUDA Graphs for minimal launch overhead
//! - Zero-copy memory management với pinned allocators
//! - Multi-stream execution với automatic pipelining
//! - NVTX profiling integration
//! - Advanced memory coalescing

use anyhow::{Context, Result};
use clap::Parser;
use std::sync::Arc;
use tokio::signal;
use tracing::{info, warn, error};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod config;
mod gpu_executor;
mod memory_manager;
mod cuda_graphs;
mod kernel_optimizer;
mod metrics;
mod task_processor;

use crate::{
    config::Config,
    gpu_executor::GpuExecutor,
    memory_manager::ZeroCopyMemoryManager,
};

#[derive(Parser)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Configuration file path
    #[arg(short, long, default_value = "executor_config.toml")]
    config: String,
    
    /// GPU device ID
    #[arg(short, long, default_value = "0")]
    gpu_id: u32,
    
    /// Worker ID (unique identifier)
    #[arg(short, long)]
    worker_id: Option<String>,
    
    /// Log level
    #[arg(short, long, default_value = "info")]
    log_level: String,
    
    /// Enable NVTX profiling
    #[arg(long)]
    nvtx_profiling: bool,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    
    // Initialize tracing với NVTX integration nếu enabled
    init_tracing(&args.log_level, args.nvtx_profiling)?;
    
    info!("🚀 Starting Opus GPU Executor v{}", env!("CARGO_PKG_VERSION"));
    info!("🎮 Target GPU ID: {}", args.gpu_id);
    
    // Load configuration
    let config = Config::load(&args.config)
        .with_context(|| format!("Failed to load config from {}", args.config))?;
    
    // Generate worker ID if not provided
    let worker_id = args.worker_id.unwrap_or_else(|| {
        format!("executor-gpu{}-{}", args.gpu_id, uuid::Uuid::new_v4())
    });
    
    info!("🤖 Worker ID: {}", worker_id);
    
    // Initialize GPU resources
    info!("🔧 Initializing GPU resources...");
    let memory_manager = Arc::new(
        ZeroCopyMemoryManager::new(args.gpu_id, &config.memory)
            .await
            .context("Failed to initialize memory manager")?
    );
    
    let executor = Arc::new(
        GpuExecutor::new(
            args.gpu_id,
            worker_id.clone(),
            config.clone(),
            memory_manager.clone(),
        )
        .await
        .context("Failed to initialize GPU executor")?
    );
    
    // Start task processing loop
    let task_processor_handle = {
        let executor = executor.clone();
        let config = config.clone();
        tokio::spawn(async move {
            executor.start_task_processing_loop(config.nats.url).await
        })
    };
    
    // Start heartbeat to scheduler
    let heartbeat_handle = {
        let executor = executor.clone();
        let config = config.clone();
        tokio::spawn(async move {
            executor.start_heartbeat_loop(config.scheduler.url, Duration::from_secs(30)).await
        })
    };
    
    // Start metrics server
    let metrics_handle = {
        let config = config.clone();
        tokio::spawn(async move {
            crate::metrics::start_metrics_server(config.metrics.bind_address).await
        })
    };
    
    info!("✅ GPU Executor started successfully");
    info!("🔗 Connected to scheduler: {}", config.scheduler.url);
    info!("📊 Metrics server listening on {}", config.metrics.bind_address);
    
    // Wait for shutdown signal
    select_shutdown(vec![
        task_processor_handle,
        heartbeat_handle,
        metrics_handle,
    ]).await?;
    
    info!("🛑 GPU Executor shutdown complete");
    Ok(())
}

fn init_tracing(log_level: &str, nvtx_enabled: bool) -> Result<()> {
    let level = log_level.parse()
        .with_context(|| format!("Invalid log level: {}", log_level))?;
    
    let subscriber = tracing_subscriber::registry()
        .with(tracing_subscriber::fmt::layer()
            .with_target(false)
            .with_thread_ids(true)
            .compact())
        .with(tracing_subscriber::filter::LevelFilter::from_level(level));
    
    // Add NVTX layer if enabled
    if nvtx_enabled {
        info!("🔍 NVTX profiling enabled");
        // TODO: Add NVTX tracing layer when available
    }
    
    subscriber.init();
    Ok(())
}

async fn select_shutdown(handles: Vec<tokio::task::JoinHandle<Result<()>>>) -> Result<()> {
    tokio::select! {
        _ = signal::ctrl_c() => {
            info!("📡 Received Ctrl+C, shutting down GPU executor...");
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

use std::time::Duration;
use uuid;
