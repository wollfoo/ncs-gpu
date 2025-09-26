//! **Opus GPU Mining Engine** (công cụ khai thác GPU Opus – hệ thống đào coin card đồ họa)
//!
//! High-performance modular GPU mining system with plugin architecture.

use anyhow::Result;
use clap::Parser;
use std::path::PathBuf;
use tracing::{error, info};

mod core;
mod plugins;
mod utils;

use crate::core::engine::Engine;
use crate::utils::logging::setup_logging;

/// **CLI Arguments** (tham số dòng lệnh – các tùy chọn khởi động)
#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// **Config file path** (đường dẫn file cấu hình – vị trí tệp thiết lập)
    #[arg(short, long, default_value = "config/default.toml")]
    config: PathBuf,

    /// **Plugin directory** (thư mục plugin – nơi chứa các module mở rộng)
    #[arg(short, long, default_value = "plugins")]
    plugin_dir: PathBuf,

    /// **Log level** (mức độ log – chi tiết thông tin ghi nhật ký)
    #[arg(short, long, default_value = "info")]
    log_level: String,

    /// **Number of GPUs to use** (số lượng GPU sử dụng – card đồ họa khai thác)
    #[arg(short = 'g', long)]
    gpu_count: Option<usize>,

    /// **Enable metrics server** (bật server metrics – thu thập chỉ số hiệu năng)
    #[arg(long, default_value = "true")]
    metrics: bool,

    /// **Metrics port** (cổng metrics – port cho prometheus)
    #[arg(long, default_value = "9090")]
    metrics_port: u16,
}

#[tokio::main]
async fn main() -> Result<()> {
    // Parse command line arguments
    let args = Args::parse();

    // Setup logging
    setup_logging(&args.log_level)?;

    info!("🚀 Starting Opus GPU Mining Engine v{}", env!("CARGO_PKG_VERSION"));
    info!("📁 Config: {}", args.config.display());
    info!("🔌 Plugin directory: {}", args.plugin_dir.display());

    // Initialize the engine
    let mut engine = match Engine::new(&args.config, &args.plugin_dir).await {
        Ok(engine) => {
            info!("✅ Engine initialized successfully");
            engine
        }
        Err(e) => {
            error!("❌ Failed to initialize engine: {}", e);
            return Err(e);
        }
    };

    // Configure GPU count if specified
    if let Some(gpu_count) = args.gpu_count {
        engine.set_gpu_count(gpu_count)?;
        info!("🎮 Configured to use {} GPUs", gpu_count);
    }

    // Start metrics server if enabled
    if args.metrics {
        engine.start_metrics_server(args.metrics_port).await?;
        info!("📊 Metrics server started on port {}", args.metrics_port);
    }

    // Setup graceful shutdown
    let shutdown = setup_shutdown_handler();

    // Run the engine
    info!("🏃 Starting engine main loop");
    match engine.run(shutdown).await {
        Ok(()) => {
            info!("✅ Engine stopped gracefully");
            Ok(())
        }
        Err(e) => {
            error!("❌ Engine error: {}", e);
            Err(e)
        }
    }
}

/// **Setup shutdown handler** (thiết lập xử lý tắt máy – cấu hình dừng an toàn)
fn setup_shutdown_handler() -> tokio::sync::broadcast::Receiver<()> {
    let (shutdown_tx, shutdown_rx) = tokio::sync::broadcast::channel(1);

    tokio::spawn(async move {
        use tokio::signal;

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
            _ = ctrl_c => {
                info!("🛑 Received Ctrl+C signal");
            },
            _ = terminate => {
                info!("🛑 Received terminate signal");
            },
        }

        let _ = shutdown_tx.send(());
    });

    shutdown_rx
}