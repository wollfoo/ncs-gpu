//! # Validate Command (Lệnh Xác Thực)
//!
//! Xác thực configuration file.

use anyhow::Result;
use colored::*;
use std::path::Path;
use tracing::info;

use crate::config_loader;

/// Execute validate command
pub async fn execute(config_path: &Path) -> Result<()> {
    println!("{}", "🔍 Validating Configuration...".cyan().bold());
    println!("   File: {}\n", config_path.display());

    info!("Loading config file: {:?}", config_path);

    // Load and validate config
    match config_loader::load_config(config_path) {
        Ok(config) => {
            println!("{}", "✅ Configuration is valid!".green().bold());
            println!("\n{}", "Configuration Summary:".bright_cyan());
            println!("  Pool URL:         {}", config.mining.pool_url);
            println!("  Wallet:           {}", mask_wallet(&config.mining.wallet_address));
            println!("  GPUs:             {:?}", config.mining.gpu_devices);
            println!("  Algorithm:        {:?}", config.mining.algorithm);
            println!("  Stealth Profile:  {:?}", config.stealth.profile);
            println!("  Security Level:   {:?}", config.security.profile);
        }
        Err(e) => {
            println!("{}", "❌ Configuration validation failed!".red().bold());
            println!("\n{}", format!("Error: {}", e).red());
            return Err(e);
        }
    }

    Ok(())
}

/// Mask wallet address (hiển thị 6 ký tự đầu/cuối)
fn mask_wallet(wallet: &str) -> String {
    if wallet.len() > 12 {
        format!("{}...{}", &wallet[..6], &wallet[wallet.len() - 6..])
    } else {
        wallet.to_string()
    }
}
