use clap::Parser;
use std::path::PathBuf;

/// Command line interface for OPUS-GPU
#[derive(Parser, Debug)]
#[command(
    name = "opus-gpu",
    version = env!("CARGO_PKG_VERSION"),
    about = "High-performance GPU mining platform with modular architecture",
    long_about = None
)]
pub struct Cli {
    /// Configuration file path
    #[arg(
        short,
        long,
        default_value = "config/default.toml",
        help = "Path to configuration file"
    )]
    pub config_path: String,

    /// Log level (trace, debug, info, warn, error)
    #[arg(
        short = 'l',
        long,
        default_value = "info",
        help = "Set logging level"
    )]
    pub log_level: String,

    /// Enable development mode
    #[arg(
        long,
        help = "Run in development mode with additional debugging"
    )]
    pub dev_mode: bool,

    /// GPU devices to use (comma-separated indices)
    #[arg(
        short = 'g',
        long,
        help = "Specify GPU devices to use (e.g., '0,1,2')"
    )]
    pub gpu_devices: Option<String>,

    /// Mining pool URL
    #[arg(
        short = 'p',
        long,
        help = "Mining pool URL to connect to"
    )]
    pub pool_url: Option<String>,

    /// Wallet address
    #[arg(
        short = 'w',
        long,
        help = "Wallet address for mining rewards"
    )]
    pub wallet_address: Option<String>,

    /// API server bind address
    #[arg(
        long,
        default_value = "127.0.0.1:8080",
        help = "API server bind address"
    )]
    pub api_bind: String,

    /// WebSocket server bind address
    #[arg(
        long,
        default_value = "127.0.0.1:8081",
        help = "WebSocket server bind address"
    )]
    pub websocket_bind: String,

    /// gRPC server bind address
    #[arg(
        long,
        default_value = "127.0.0.1:8082",
        help = "gRPC server bind address"
    )]
    pub grpc_bind: String,

    /// Data directory
    #[arg(
        short = 'd',
        long,
        default_value = "./data",
        help = "Data directory for storage"
    )]
    pub data_dir: PathBuf,

    /// Plugin directory
    #[arg(
        long,
        default_value = "./plugins",
        help = "Directory containing plugins"
    )]
    pub plugin_dir: PathBuf,

    /// Disable plugins
    #[arg(
        long,
        help = "Disable plugin system"
    )]
    pub no_plugins: bool,

    /// Benchmark mode
    #[arg(
        long,
        help = "Run in benchmark mode"
    )]
    pub benchmark: bool,
}