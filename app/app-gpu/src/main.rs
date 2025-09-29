use anyhow::Result;
use clap::Parser;
use opus_gpu_bus::MessageBus;
use opus_gpu_config::AppConfig;
use std::sync::Arc;
use tokio::signal;
use tracing::{error, info, warn};

// Import security modules
#[cfg(feature = "security")]
use opus_gpu_security::{SecurityManager, SecurityConfig};

#[cfg(feature = "obfuscation")]
use opus_gpu_obfuscation::{ObfuscationManager, ObfuscationConfig, StealthManager, StealthConfig};

mod app;
mod cli;

use app::OpusGpuApp;
use cli::Cli;

/// OPUS-GPU - High-performance GPU mining platform with security hardening
#[tokio::main]
async fn main() -> Result<()> {
    // Initialize security checks before anything else
    #[cfg(feature = "obfuscation")]
    early_security_checks();

    // Initialize tracing/logging
    init_tracing()?;

    info!("🚀 Starting OPUS-GPU v{} with Security Hardening", env!("CARGO_PKG_VERSION"));

    // Parse command line arguments
    let cli = Cli::parse();

    // Initialize security manager
    #[cfg(feature = "security")]
    let mut security_manager = {
        let security_config = SecurityConfig::default();
        let mut mgr = SecurityManager::new(security_config)?;
        mgr.initialize().await?;
        info!("🔒 Security hardening initialized");
        Some(mgr)
    };

    // Initialize obfuscation manager
    #[cfg(feature = "obfuscation")]
    let obfuscation_manager = {
        let obf_config = ObfuscationConfig::default();
        let mgr = ObfuscationManager::new(obf_config)?;
        mgr.initialize_runtime_protection().await?;
        info!("🛡️ Runtime obfuscation protection initialized");
        Some(mgr)
    };

    // Initialize stealth manager
    #[cfg(feature = "stealth")]
    let mut stealth_manager = {
        let stealth_config = StealthConfig::default();
        let mut mgr = StealthManager::new(stealth_config)?;
        mgr.initialize().await?;
        mgr.activate_stealth_mode().await?;
        info!("👻 Stealth operations activated");
        Some(mgr)
    };

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

            // Shutdown security components first
            #[cfg(feature = "stealth")]
            if let Some(mut stealth_mgr) = stealth_manager {
                if let Err(e) = stealth_mgr.deactivate_stealth_mode().await {
                    error!("❌ Error deactivating stealth mode: {}", e);
                }
            }

            #[cfg(feature = "security")]
            if let Some(mut security_mgr) = security_manager {
                if let Err(e) = security_mgr.shutdown().await {
                    error!("❌ Error shutting down security manager: {}", e);
                }
            }

            // Shutdown main application
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