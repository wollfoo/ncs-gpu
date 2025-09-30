// Coordinator - Điều phối viên chính cho GPU Mining System
// Chịu trách nhiệm: task scheduling, worker management, health monitoring

use anyhow::Result;
use clap::Parser;
use std::path::PathBuf;
use tracing::{info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod config;
mod scheduler;
mod worker_registry;
mod server;

use config::CoordinatorConfig;
use scheduler::TaskScheduler;
use worker_registry::WorkerRegistry;
use server::CoordinatorServer;

/// **[CLI Arguments]** (Tham số dòng lệnh – command-line options)
#[derive(Parser, Debug)]
#[command(name = "coordinator")]
#[command(about = "GPU Mining Coordinator - Điều phối viên khai thác GPU", long_about = None)]
struct Args {
    /// **[Config Path]** (Đường dẫn cấu hình – path to TOML config file)
    #[arg(short, long, default_value = "config/default.toml")]
    config: PathBuf,
    
    /// **[Bind Address]** (Địa chỉ lắng nghe – gRPC server bind address)
    #[arg(short, long, default_value = "0.0.0.0:50051")]
    bind: String,
}

#[tokio::main]
async fn main() -> Result<()> {
    // Khởi tạo **[Tracing Subscriber]** (bộ thu thập tracing – structured logging)
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "coordinator=info,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer().json())
        .init();

    let args = Args::parse();
    
    info!("🚀 Khởi động Coordinator...");
    info!("📁 Đọc cấu hình từ: {:?}", args.config);

    // Đọc **[Config]** (cấu hình – system configuration)
    let config = CoordinatorConfig::from_file(&args.config)?;
    info!("✅ Cấu hình đã tải: {:?}", config);

    // Khởi tạo **[Worker Registry]** (sổ đăng ký worker – tracking workers)
    let worker_registry = WorkerRegistry::new();
    info!("📋 Worker Registry đã khởi tạo");

    // Khởi tạo **[Task Scheduler]** (bộ lập lịch tác vụ – task queue management)
    let scheduler = TaskScheduler::new(worker_registry.clone());
    info!("📅 Task Scheduler đã khởi tạo");

    // Khởi động **[Health Check Loop]** (vòng kiểm tra sức khỏe – monitor workers)
    let health_check_handle = tokio::spawn({
        let registry = worker_registry.clone();
        async move {
            health_check_loop(registry).await;
        }
    });

    // Khởi động **[gRPC Server]** (máy chủ gRPC – API endpoint)
    let server = CoordinatorServer::new(scheduler, worker_registry);
    
    info!("🌐 Coordinator đang lắng nghe tại: {}", args.bind);
    
    // Chạy server
    let addr = args.bind.parse()?;
    server.serve(addr).await?;

    // Chờ health check loop kết thúc (không bao giờ trong điều kiện bình thường)
    health_check_handle.await?;

    Ok(())
}

/// **[Health Check Loop]** (Vòng kiểm tra sức khỏe – định kỳ ping workers)
async fn health_check_loop(registry: WorkerRegistry) {
    let mut interval = tokio::time::interval(std::time::Duration::from_secs(30));
    
    loop {
        interval.tick().await;
        
        let worker_count = registry.active_worker_count();
        info!("💓 Health check: {} workers hoạt động", worker_count);
        
        // Loại bỏ **[Dead Workers]** (workers chết – không phản hồi)
        let removed = registry.remove_dead_workers(std::time::Duration::from_secs(120)).await;
        
        if removed > 0 {
            warn!("⚠️  Đã loại bỏ {} workers không phản hồi", removed);
        }
    }
}
