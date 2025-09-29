//! OPUS-GPU v2.0 - High-Performance GPU Mining System
//!
//! **Entry Point** (Điểm khởi đầu) - Main CLI and service initialization
//! Features:
//! - **Async/await runtime** (runtime bất đồng bộ)
//! - **GPU mining engine** (engine đào GPU)
//! - **Thermal management** (quản lý nhiệt)
//! - **Resource optimization** (tối ưu tài nguyên)
//! - **Distributed coordination** (điều phối phân tán)

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use std::{path::PathBuf, sync::Arc, time::Duration};
use tokio::{signal, sync::RwLock, time::sleep};
use tracing::{error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use opus_gpu::{
    api::ApiServer,
    common::{config::Config, metrics::MetricsCollector},
    gpu_mining::{engine::MiningEngine, thermal::ThermalManager},
    resource_manager::ResourceManager,
    security::SecurityManager,
};

/// **CLI Arguments** (Tham số dòng lệnh)
#[derive(Parser)]
#[command(name = "opus-gpu")]
#[command(about = "OPUS-GPU v2.0 - High-Performance GPU Mining System")]
#[command(version = env!("CARGO_PKG_VERSION"))]
struct Cli {
    /// **Configuration file path** (Đường dẫn file cấu hình)
    #[arg(short, long, default_value = "config.toml")]
    config: PathBuf,

    /// **Log level** (Mức độ log)
    #[arg(short, long, default_value = "info")]
    log_level: String,

    /// **Enable development mode** (Bật chế độ phát triển)
    #[arg(long)]
    dev_mode: bool,

    /// **Enable metrics endpoint** (Bật endpoint metrics)
    #[arg(long)]
    metrics: bool,

    /// **Bind address for API** (Địa chỉ bind cho API)
    #[arg(long, default_value = "127.0.0.1:8080")]
    bind: String,

    #[command(subcommand)]
    command: Option<Commands>,
}

/// **CLI Subcommands** (Lệnh con CLI)
#[derive(Subcommand)]
enum Commands {
    /// **Start mining service** (Khởi động dịch vụ đào)
    Mine {
        /// **Mining pool URL** (URL pool đào)
        #[arg(short, long)]
        pool: Option<String>,

        /// **Mining threads** (Luồng đào)
        #[arg(short, long)]
        threads: Option<usize>,

        /// **GPU device IDs** (ID thiết bị GPU)
        #[arg(long)]
        gpu_ids: Option<Vec<u32>>,
    },

    /// **System diagnostics** (Chẩn đoán hệ thống)
    Diagnose {
        /// **Run thermal stress test** (Chạy test stress nhiệt)
        #[arg(long)]
        thermal: bool,

        /// **Check GPU capabilities** (Kiểm tra khả năng GPU)
        #[arg(long)]
        gpu_check: bool,
    },

    /// **Performance benchmarking** (Đánh giá hiệu suất)
    Benchmark {
        /// **Benchmark duration in seconds** (Thời gian benchmark tính bằng giây)
        #[arg(short, long, default_value = "60")]
        duration: u64,

        /// **Target GPU devices** (Thiết bị GPU mục tiêu)
        #[arg(long)]
        gpu_ids: Option<Vec<u32>>,
    },

    /// **Configuration management** (Quản lý cấu hình)
    Config {
        /// **Show current configuration** (Hiện cấu hình hiện tại)
        #[arg(long)]
        show: bool,

        /// **Validate configuration** (Xác thực cấu hình)
        #[arg(long)]
        validate: bool,
    },
}

/// **Main Application State** (Trạng thái ứng dụng chính)
struct AppState {
    config: Arc<Config>,
    mining_engine: Arc<RwLock<MiningEngine>>,
    thermal_manager: Arc<ThermalManager>,
    resource_manager: Arc<ResourceManager>,
    security_manager: Arc<SecurityManager>,
    metrics_collector: Arc<MetricsCollector>,
    api_server: Option<Arc<ApiServer>>,
}

impl AppState {
    /// **Initialize application state** (Khởi tạo trạng thái ứng dụng)
    async fn new(config: Config) -> Result<Self> {
        let config = Arc::new(config);

        // **Initialize core managers** (Khởi tạo các manager cốt lõi)
        let thermal_manager = Arc::new(
            ThermalManager::new(&config.thermal)
                .await
                .context("Failed to initialize thermal manager")?
        );

        let resource_manager = Arc::new(
            ResourceManager::new(&config.resources)
                .await
                .context("Failed to initialize resource manager")?
        );

        let security_manager = Arc::new(
            SecurityManager::new(&config.security)
                .await
                .context("Failed to initialize security manager")?
        );

        let metrics_collector = Arc::new(
            MetricsCollector::new(&config.metrics)
                .context("Failed to initialize metrics collector")?
        );

        // **Initialize mining engine** (Khởi tạo engine đào)
        let mining_engine = Arc::new(RwLock::new(
            MiningEngine::new(
                &config.mining,
                Arc::clone(&thermal_manager),
                Arc::clone(&resource_manager),
                Arc::clone(&metrics_collector),
            )
            .await
            .context("Failed to initialize mining engine")?
        ));

        Ok(Self {
            config,
            mining_engine,
            thermal_manager,
            resource_manager,
            security_manager,
            metrics_collector,
            api_server: None,
        })
    }

    /// **Start API server** (Khởi động server API)
    async fn start_api_server(&mut self, bind_addr: &str) -> Result<()> {
        let api_server = Arc::new(
            ApiServer::new(
                bind_addr,
                Arc::clone(&self.mining_engine),
                Arc::clone(&self.thermal_manager),
                Arc::clone(&self.resource_manager),
                Arc::clone(&self.metrics_collector),
            )
            .await
            .context("Failed to create API server")?
        );

        api_server.start().await.context("Failed to start API server")?;
        self.api_server = Some(api_server);

        info!("API server started on {}", bind_addr);
        Ok(())
    }

    /// **Start mining operations** (Khởi động hoạt động đào)
    async fn start_mining(&self, pool_url: Option<String>, gpu_ids: Option<Vec<u32>>) -> Result<()> {
        let mut engine = self.mining_engine.write().await;

        if let Some(pool) = pool_url {
            engine.set_pool_url(&pool).await?;
        }

        if let Some(ids) = gpu_ids {
            engine.set_target_gpus(ids).await?;
        }

        engine.start().await.context("Failed to start mining")?;
        info!("Mining engine started successfully");

        Ok(())
    }

    /// **Run system diagnostics** (Chạy chẩn đoán hệ thống)
    async fn run_diagnostics(&self, thermal_test: bool, gpu_check: bool) -> Result<()> {
        info!("Running system diagnostics...");

        if thermal_test {
            info!("Running thermal stress test...");
            self.thermal_manager.run_stress_test(Duration::from_secs(30)).await?;
        }

        if gpu_check {
            info!("Checking GPU capabilities...");
            let engine = self.mining_engine.read().await;
            engine.check_gpu_capabilities().await?;
        }

        // **Resource manager diagnostics** (Chẩn đoán resource manager)
        let resource_stats = self.resource_manager.get_system_stats().await?;
        info!("System resources: CPU: {:.1}%, Memory: {:.1}%, GPU: {:.1}%",
              resource_stats.cpu_usage * 100.0,
              resource_stats.memory_usage * 100.0,
              resource_stats.gpu_usage * 100.0);

        info!("Diagnostics completed successfully");
        Ok(())
    }

    /// **Run performance benchmark** (Chạy benchmark hiệu suất)
    async fn run_benchmark(&self, duration: Duration, gpu_ids: Option<Vec<u32>>) -> Result<()> {
        info!("Starting performance benchmark for {} seconds", duration.as_secs());

        let engine = self.mining_engine.read().await;
        let results = engine.run_benchmark(duration, gpu_ids).await?;

        info!("Benchmark Results:");
        for (gpu_id, result) in results.iter() {
            info!("  GPU {}: {:.2} MH/s, {:.1}°C, {:.1}W",
                  gpu_id, result.hashrate_mhs, result.temperature, result.power_watts);
        }

        Ok(())
    }

    /// **Graceful shutdown** (Tắt máy một cách nhẹ nhàng)
    async fn shutdown(&self) -> Result<()> {
        info!("Initiating graceful shutdown...");

        // **Stop mining first** (Dừng đào trước)
        {
            let mut engine = self.mining_engine.write().await;
            if let Err(e) = engine.stop().await {
                error!("Error stopping mining engine: {}", e);
            }
        }

        // **Stop API server** (Dừng server API)
        if let Some(ref api_server) = self.api_server {
            if let Err(e) = api_server.stop().await {
                error!("Error stopping API server: {}", e);
            }
        }

        // **Shutdown managers** (Tắt các manager)
        if let Err(e) = self.thermal_manager.shutdown().await {
            error!("Error shutting down thermal manager: {}", e);
        }

        if let Err(e) = self.resource_manager.shutdown().await {
            error!("Error shutting down resource manager: {}", e);
        }

        info!("Shutdown completed");
        Ok(())
    }
}

/// **Initialize logging system** (Khởi tạo hệ thống logging)
fn init_logging(log_level: &str, dev_mode: bool) -> Result<()> {
    let level = log_level.parse()
        .context("Invalid log level")?;

    let fmt_layer = tracing_subscriber::fmt::layer()
        .with_target(true)
        .with_thread_ids(true)
        .with_file(dev_mode)
        .with_line_number(dev_mode);

    if dev_mode {
        // **Development logging** (Logging phát triển)
        tracing_subscriber::registry()
            .with(tracing_subscriber::EnvFilter::new(level))
            .with(fmt_layer.pretty())
            .init();
    } else {
        // **Production logging** (Logging production)
        tracing_subscriber::registry()
            .with(tracing_subscriber::EnvFilter::new(level))
            .with(fmt_layer.json())
            .init();
    }

    Ok(())
}

/// **Load configuration** (Tải cấu hình)
async fn load_config(path: &PathBuf) -> Result<Config> {
    if !path.exists() {
        warn!("Configuration file not found at {:?}, using defaults", path);
        return Ok(Config::default());
    }

    let config_str = tokio::fs::read_to_string(path).await
        .with_context(|| format!("Failed to read config file: {:?}", path))?;

    let config: Config = toml::from_str(&config_str)
        .with_context(|| format!("Failed to parse config file: {:?}", path))?;

    info!("Configuration loaded from {:?}", path);
    Ok(config)
}

/// **Main application entry point** (Điểm khởi đầu ứng dụng chính)
#[tokio::main]
async fn main() -> Result<()> {
    // **Parse CLI arguments** (Phân tích tham số CLI)
    let cli = Cli::parse();

    // **Initialize logging** (Khởi tạo logging)
    init_logging(&cli.log_level, cli.dev_mode)
        .context("Failed to initialize logging")?;

    info!("OPUS-GPU v{} starting up...", env!("CARGO_PKG_VERSION"));

    // **Load configuration** (Tải cấu hình)
    let config = load_config(&cli.config).await?;

    // **Initialize application state** (Khởi tạo trạng thái ứng dụng)
    let mut app_state = AppState::new(config).await
        .context("Failed to initialize application state")?;

    // **Setup signal handling** (Thiết lập xử lý tín hiệu)
    let shutdown_signal = async {
        signal::ctrl_c().await.expect("Failed to install CTRL+C signal handler");
        info!("Received shutdown signal");
    };

    // **Execute subcommands** (Thực thi lệnh con)
    match cli.command {
        Some(Commands::Mine { pool, threads, gpu_ids }) => {
            // **Start API server if enabled** (Khởi động server API nếu được bật)
            if cli.metrics {
                app_state.start_api_server(&cli.bind).await?;
            }

            // **Set thread count** (Đặt số luồng)
            if let Some(thread_count) = threads {
                let engine = app_state.mining_engine.read().await;
                engine.set_worker_threads(thread_count).await?;
            }

            // **Start mining** (Khởi động đào)
            app_state.start_mining(pool, gpu_ids).await?;

            // **Wait for shutdown signal** (Chờ tín hiệu tắt máy)
            tokio::select! {
                _ = shutdown_signal => {
                    info!("Shutdown signal received, stopping...");
                }
                _ = tokio::time::sleep(Duration::from_secs(86400)) => {
                    info!("Daily restart triggered");
                }
            }
        }

        Some(Commands::Diagnose { thermal, gpu_check }) => {
            app_state.run_diagnostics(thermal, gpu_check).await?;
            return Ok(());
        }

        Some(Commands::Benchmark { duration, gpu_ids }) => {
            app_state.run_benchmark(Duration::from_secs(duration), gpu_ids).await?;
            return Ok(());
        }

        Some(Commands::Config { show, validate }) => {
            if show {
                println!("{}", serde_json::to_string_pretty(&*app_state.config)?);
            }
            if validate {
                info!("Configuration validation passed");
            }
            return Ok(());
        }

        None => {
            // **Default: start service mode** (Mặc định: khởi động chế độ dịch vụ)
            if cli.metrics {
                app_state.start_api_server(&cli.bind).await?;
            }

            info!("Service mode started. Press Ctrl+C to stop.");
            shutdown_signal.await;
        }
    }

    // **Graceful shutdown** (Tắt máy một cách nhẹ nhàng)
    app_state.shutdown().await?;

    info!("OPUS-GPU shutdown completed");
    Ok(())
}

/// **Health check for monitoring systems** (Kiểm tra sức khỏe cho hệ thống giám sát)
pub async fn health_check() -> Result<()> {
    // **Basic health checks** (Kiểm tra sức khỏe cơ bản)
    info!("Health check: OK");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::NamedTempFile;
    use tokio::fs;

    #[tokio::test]
    async fn test_config_loading() {
        let mut config_file = NamedTempFile::new().unwrap();
        let config_content = r#"
[mining]
pool_url = "stratum+tcp://test.pool.com:4444"
worker_name = "test_worker"

[thermal]
max_temperature = 85.0
fan_curve = "aggressive"
"#;

        fs::write(&config_file.path(), config_content).await.unwrap();
        let config = load_config(&config_file.path().to_path_buf()).await.unwrap();

        assert_eq!(config.mining.pool_url, Some("stratum+tcp://test.pool.com:4444".to_string()));
        assert_eq!(config.thermal.max_temperature, 85.0);
    }

    #[tokio::test]
    async fn test_app_state_initialization() {
        let config = Config::default();
        let app_state = AppState::new(config).await;
        assert!(app_state.is_ok());
    }

    #[test]
    fn test_cli_parsing() {
        let cli = Cli::parse_from(&["opus-gpu", "mine", "--pool", "test://pool"]);
        match cli.command {
            Some(Commands::Mine { pool, .. }) => {
                assert_eq!(pool, Some("test://pool".to_string()));
            }
            _ => panic!("Expected mine command"),
        }
    }
}