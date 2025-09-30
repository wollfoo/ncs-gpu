/*!
 * OPUS-GPU Miner - High-Performance GPU Cryptocurrency Mining
 *
 * Main entry point cho modular monolith architecture.
 * Khởi động tokio runtime, message bus, và tất cả modules.
 */

use anyhow::Result;
use tracing::info;
use tokio_util::sync::CancellationToken;

mod runtime;
mod messaging;
mod modules;
mod error;
mod legacy;
mod performance;
mod plugins;

use messaging::MessageBus;
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing subscriber
    tracing_subscriber::fmt()
        .with_target(false)
        .with_thread_ids(true)
        .with_level(true)
        .with_ansi(true)
        .init();

    info!("🚀 Starting OPUS-GPU Miner v{}", env!("CARGO_PKG_VERSION"));

    // Phase 1: Load configuration
    info!("📝 Loading configuration...");
    let config = load_config()?;

    // Phase 2: Initialize message bus
    info!("🔌 Initializing message bus...");
    let num_gpus = config.gpu.devices.len();
    let (bus, _handles) = MessageBus::new(num_gpus, 1000);
    let bus = Arc::new(bus);

    // Phase 3: Initialize cancellation token for graceful shutdown
    let cancel_token = CancellationToken::new();

    // Phase 4: Start modules in parallel
    info!("⚙️  Starting modules...");

    let api_handle = tokio::spawn({
        let api_config = modules::api::ApiConfig {
            bind_addr: format!("{}:{}", config.api.host, config.api.port),
            enable_cors: false,
        };
        let bus = bus.clone();
        let cancel = cancel_token.clone();
        async move {
            modules::api::start(api_config, bus, cancel).await
        }
    });

    let gpu_handles: Vec<_> = (0..num_gpus).map(|gpu_id| {
        tokio::spawn({
            let gpu_config = modules::gpu::GpuConfig {
                device_id: gpu_id as u32,
                threads_per_block: 256,
                num_blocks: 128,
                intensity: 80,
            };
            let bus = bus.clone();
            let cancel = cancel_token.clone();
            async move {
                modules::gpu::start(gpu_id as u32, gpu_config, bus, cancel).await
            }
        })
    }).collect();

    let stealth_handle = tokio::spawn({
        let stealth_config = modules::stealth::StealthConfig {
            obfuscate_process: config.stealth.enabled,
            mask_network: false,
            cpu_limit: 100,
            gpu_limit: 100,
            plugin_dir: Some(config.stealth.plugins_dir.clone()),
        };
        let bus = bus.clone();
        let cancel = cancel_token.clone();
        async move {
            modules::stealth::start(stealth_config, bus, cancel).await
        }
    });

    let metrics_handle = tokio::spawn({
        let metrics_config = modules::metrics::MetricsConfig {
            interval_secs: 5,
            enable_gpu_metrics: config.metrics.enabled,
            enable_system_metrics: config.metrics.enabled,
        };
        let bus = bus.clone();
        let cancel = cancel_token.clone();
        async move {
            modules::metrics::start(metrics_config, bus, cancel).await
        }
    });

    // Phase 5: Wait for startup completion
    tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
    info!("✅ All modules started successfully");

    // Phase 6: Setup signal handling
    setup_signal_handlers(cancel_token.clone());

    // Phase 7: Wait for shutdown signal
    cancel_token.cancelled().await;

    info!("🛑 Shutting down gracefully...");

    // Phase 8: Wait for all modules to finish
    let _ = tokio::join!(
        api_handle,
        stealth_handle,
        metrics_handle
    );

    for handle in gpu_handles {
        let _ = handle.await;
    }

    info!("✅ Shutdown complete");
    Ok(())
}

/// Load configuration từ file
fn load_config() -> Result<Config> {
    let config_path = std::env::var("CONFIG_PATH")
        .unwrap_or_else(|_| "config/app.toml".to_string());

    let content = std::fs::read_to_string(&config_path)?;
    let config: Config = toml::from_str(&content)?;

    Ok(config)
}

/// Setup signal handlers cho graceful shutdown
fn setup_signal_handlers(cancel_token: CancellationToken) {
    tokio::spawn(async move {
        use tokio::signal::unix::{signal, SignalKind};

        let mut sigterm = signal(SignalKind::terminate())
            .expect("Failed to setup SIGTERM handler");

        let mut sigint = signal(SignalKind::interrupt())
            .expect("Failed to setup SIGINT handler");

        tokio::select! {
            _ = sigterm.recv() => {
                info!("📨 Received SIGTERM");
            }
            _ = sigint.recv() => {
                info!("📨 Received SIGINT");
            }
        }

        cancel_token.cancel();
    });
}

/// Main configuration structure
#[derive(Debug, Clone, serde::Deserialize)]
pub struct Config {
    pub gpu: GpuConfig,
    pub api: ApiConfig,
    pub stealth: StealthConfig,
    pub metrics: MetricsConfig,
}

#[derive(Debug, Clone, serde::Deserialize)]
pub struct GpuConfig {
    pub devices: Vec<usize>,
    pub memory_limit_mb: Option<u64>,
}

#[derive(Debug, Clone, serde::Deserialize)]
pub struct ApiConfig {
    pub host: String,
    pub port: u16,
}

#[derive(Debug, Clone, serde::Deserialize)]
pub struct StealthConfig {
    pub enabled: bool,
    pub plugins_dir: String,
}

#[derive(Debug, Clone, serde::Deserialize)]
pub struct MetricsConfig {
    pub enabled: bool,
    pub port: u16,
}
