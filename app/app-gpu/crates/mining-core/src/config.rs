//! # Configuration Module (Module Cấu Hình)
//!
//! Configuration structures và utilities cho mining system.

use serde::Serialize;
use std::path::Path;
use anyhow::{Context, Result};

/// Load configuration từ file
pub fn load_config<P: AsRef<Path>>(path: P) -> Result<crate::MiningConfig> {
    let contents = std::fs::read_to_string(path.as_ref())
        .with_context(|| format!("Failed to read config file: {:?}", path.as_ref()))?;

    let config: crate::MiningConfig = toml::from_str(&contents)
        .with_context(|| "Failed to parse TOML configuration")?;

    Ok(config)
}

/// Validate configuration
pub fn validate_config(config: &crate::MiningConfig) -> Result<()> {
    if config.pool_url.is_empty() {
        anyhow::bail!("Pool URL cannot be empty");
    }

    if config.wallet_address.is_empty() {
        anyhow::bail!("Wallet address cannot be empty");
    }

    if config.gpu_devices.is_empty() {
        anyhow::bail!("No GPU devices specified");
    }

    if config.intensity < 0.0 || config.intensity > 1.0 {
        anyhow::bail!("Intensity must be between 0.0 and 1.0");
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{MiningConfig, MiningAlgorithm};

    #[test]
    fn test_validate_config() {
        let config = MiningConfig {
            pool_url: "stratum+tcp://pool.example.com:3333".to_string(),
            wallet_address: "0x1234567890abcdef".to_string(),
            gpu_devices: vec![0, 1],
            algorithm: MiningAlgorithm::Ethash,
            intensity: 0.8,
        };

        assert!(validate_config(&config).is_ok());
    }

    #[test]
    fn test_validate_empty_pool() {
        let config = MiningConfig {
            pool_url: "".to_string(),
            wallet_address: "0x1234".to_string(),
            gpu_devices: vec![0],
            algorithm: MiningAlgorithm::Ethash,
            intensity: 0.8,
        };

        assert!(validate_config(&config).is_err());
    }
}
