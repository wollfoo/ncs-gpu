/*!
 * App-GPU Core - Entry Point
 * 
 * Điểm khởi đầu chính của hệ thống khai thác GPU với kiến trúc modular monolith.
 * Main entry point cho cryptocurrency mining application với GPU optimization và cloaking.
 */

use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use std::sync::Arc;
use tracing::{error, info, warn};

mod config;
mod event_bus;
mod plugin_loader;
mod telemetry;

use config::AppConfig;
use event_bus::EventBus;
use plugin_loader::PluginManager;

/// App-GPU - High-Performance GPU Mining System
/// Hệ thống khai thác GPU hiệu năng cao với cloaking và optimization
#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Configuration file path (đường dẫn file cấu hình)
    #[arg(short, long, value_name = "FILE", default_value = "/etc/app-gpu/config.toml")]
    config: PathBuf,

    /// Log level (mức độ log): trace, debug, info, warn, error
    #[arg(short, long, default_value = "info")]
    log_level: String,

    /// Enable JSON logging (bật ghi log định dạng JSON)
    #[arg(long)]
    json_logs: bool,

    /// Enable debug mode (chế độ debug - verbose logging)
    #[arg(long)]
    debug: bool,

    /// Dry run - validate config without starting (kiểm tra cấu hình mà không khởi động)
    #[arg(long)]
    dry_run: bool,
}

#[tokio::main]
async fn main() -> Result<()> {
    // Parse command-line arguments (phân tích đối số dòng lệnh)
    let args = Args::parse();

    // Initialize telemetry (tracing + metrics)
    // Khởi tạo telemetry - hệ thống theo dõi và đo lường
    telemetry::init(&args.log_level, args.json_logs)
        .context("Failed to initialize telemetry")?;

    info!("🚀 Starting App-GPU v{}", env!("CARGO_PKG_VERSION"));
    info!("📁 Config file: {}", args.config.display());

    // Load configuration (tải cấu hình)
    let config = AppConfig::load(&args.config)
        .context("Failed to load configuration")?;

    info!("✅ Configuration loaded successfully");
    if args.debug {
        info!("🔍 Debug mode enabled");
        info!("📋 Config: {:#?}", config);
    }

    // Dry run mode - exit after validation
    // Chế độ dry run - thoát sau khi kiểm tra
    if args.dry_run {
        info!("✅ Configuration valid. Exiting (dry-run mode)");
        return Ok(());
    }

    // Initialize event bus (khởi tạo bus sự kiện - pub/sub nội bộ)
    let event_bus = Arc::new(EventBus::new(config.event_bus_capacity));
    info!("✅ Event bus initialized (capacity: {})", config.event_bus_capacity);

    // Initialize plugin manager (khởi tạo trình quản lý plugin)
    let mut plugin_manager = PluginManager::new(config.clone(), event_bus.clone());
    info!("✅ Plugin manager initialized");

    // Load and initialize plugins (tải và khởi tạo các plugin)
    // Thứ tự: Security → Resource Manager → GPU Executor → Cloaking
    plugin_manager.load_plugin("security")
        .await
        .context("Failed to load security plugin")?;
    info!("✅ Security plugin loaded");

    plugin_manager.load_plugin("resource-manager")
        .await
        .context("Failed to load resource manager plugin")?;
    info!("✅ Resource manager plugin loaded");

    plugin_manager.load_plugin("gpu-executor")
        .await
        .context("Failed to load GPU executor plugin")?;
    info!("✅ GPU executor plugin loaded");

    plugin_manager.load_plugin("cloaking")
        .await
        .context("Failed to load cloaking plugin")?;
    info!("✅ Cloaking plugin loaded");

    // Start all plugins (khởi động tất cả plugin)
    plugin_manager.start_all()
        .await
        .context("Failed to start plugins")?;
    info!("✅ All plugins started successfully");

    // Setup signal handlers (thiết lập xử lý tín hiệu - graceful shutdown)
    setup_signal_handlers(plugin_manager.clone()).await?;
    info!("✅ Signal handlers registered (SIGINT, SIGTERM)");

    info!("🎯 App-GPU is running. Press Ctrl+C to stop.");

    // Main event loop (vòng lặp sự kiện chính)
    // Chạy cho đến khi nhận tín hiệu shutdown
    tokio::select! {
        _ = tokio::signal::ctrl_c() => {
            info!("📡 Received Ctrl+C signal");
        }
    }

    // Graceful shutdown (tắt mượt mà)
    info!("🔄 Initiating graceful shutdown...");
    plugin_manager.stop_all()
        .await
        .context("Failed to stop plugins")?;
    info!("✅ All plugins stopped");

    event_bus.shutdown().await;
    info!("✅ Event bus shutdown");

    info!("👋 App-GPU shutdown complete");
    Ok(())
}

/// Setup signal handlers for graceful shutdown
/// Thiết lập xử lý tín hiệu cho shutdown mượt mà
async fn setup_signal_handlers(plugin_manager: PluginManager) -> Result<()> {
    use signal_hook::consts::signal::*;
    use signal_hook_tokio::Signals;
    use futures::StreamExt;

    let signals = Signals::new(&[SIGINT, SIGTERM])
        .context("Failed to register signal handlers")?;
    let handle = signals.handle();

    let signal_task = tokio::spawn(async move {
        let mut signals = signals.fuse();
        while let Some(signal) = signals.next().await {
            match signal {
                SIGINT | SIGTERM => {
                    warn!("⚠️ Received shutdown signal: {}", signal);
                    // Trigger graceful shutdown
                    // Note: Actual shutdown is handled in main loop
                    break;
                }
                _ => unreachable!(),
            }
        }
        handle.close();
    });

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_args_parsing() {
        // Test default arguments
        let args = Args::try_parse_from(&["app-gpu"]).unwrap();
        assert_eq!(args.config, PathBuf::from("/etc/app-gpu/config.toml"));
        assert_eq!(args.log_level, "info");
        assert!(!args.json_logs);
        assert!(!args.debug);
    }

    #[test]
    fn test_custom_config_path() {
        let args = Args::try_parse_from(&["app-gpu", "--config", "/custom/path.toml"]).unwrap();
        assert_eq!(args.config, PathBuf::from("/custom/path.toml"));
    }
}
