//! # Mining CLI (Giao Diện Dòng Lệnh)
//!
//! Command-line interface để quản lý GPU mining system.

mod commands;
mod config_loader;

use anyhow::Result;
use clap::{Parser, Subcommand};
use colored::*;
use std::path::PathBuf;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[derive(Parser)]
#[command(name = "mining-cli")]
#[command(author = "Opus GPU Team")]
#[command(version = "1.0.0")]
#[command(about = "GPU Mining System với Stealth Capabilities", long_about = None)]
struct Cli {
    /// Configuration file path
    #[arg(short, long, value_name = "FILE", default_value = "config/default.toml")]
    config: PathBuf,

    /// Verbose mode
    #[arg(short, long)]
    verbose: bool,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Start mining operations
    Start {
        /// Run in background (daemon mode)
        #[arg(short, long)]
        daemon: bool,
    },

    /// Stop mining operations
    Stop,

    /// Show current mining status
    Status,

    /// Validate configuration file
    Validate {
        /// Config file to validate
        #[arg(value_name = "FILE")]
        config: PathBuf,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    // Parse CLI arguments
    let cli = Cli::parse();

    // Setup logging
    setup_logging(cli.verbose)?;

    // Print banner
    print_banner();

    // Execute command
    match cli.command {
        Commands::Start { daemon } => {
            commands::start::execute(&cli.config, daemon).await?;
        }
        Commands::Stop => {
            commands::stop::execute().await?;
        }
        Commands::Status => {
            commands::status::execute().await?;
        }
        Commands::Validate { config } => {
            commands::validate::execute(&config).await?;
        }
    }

    Ok(())
}

/// Setup tracing/logging
fn setup_logging(verbose: bool) -> Result<()> {
    let filter = if verbose {
        "debug"
    } else {
        "info"
    };

    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| filter.into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    Ok(())
}

/// Print ASCII banner
fn print_banner() {
    println!("{}", "
╔═══════════════════════════════════════════════════╗
║                                                   ║
║        🎮  OPUS GPU MINING SYSTEM  🚀             ║
║                                                   ║
║        High-Performance Mining với Stealth       ║
║                                                   ║
╚═══════════════════════════════════════════════════╝
    ".bright_cyan());
}
