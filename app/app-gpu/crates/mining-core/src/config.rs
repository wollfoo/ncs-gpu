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

/// Use the MiningEngine validation (Sử dụng validation của MiningEngine)
pub fn validate_config(config: &crate::MiningConfig) -> Result<()> {
    // Delegate to MiningEngine's validation method (Ủy quyền cho phương thức validation của MiningEngine)
    crate::MiningEngine::validate_config(config)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{MiningConfig, MiningAlgorithm};

    #[test]
    fn test_validate_config() {
        let config = MiningConfig {
            stratum_config: crate::stratum::StratumConfig {
                primary_pool: crate::stratum::PoolConfig {
                    url: "stratum+tcp://pool.example.com:3333".to_string(),
                    worker_name: "test-worker".to_string(),
                    password: None,
                    user_agent: Some("Test/1.0".to_string()),
                    ssl: false,
                    backup_pools: vec![],
                },
                connect_timeout_secs: 30,
                reconnect_delay_secs: 10,
                max_reconnect_attempts: 5,
                share_batch_size: 10,
                max_job_age_secs: 60,
                rate_limit: 100.0,
                ssl_verify_hostname: true,
            },
            gpu_devices: vec![0, 1],
            algorithm: MiningAlgorithm::Ethash,
            intensity: 0.8,
        };

        assert!(validate_config(&config).is_ok());
    }

    #[test]
    fn test_validate_empty_pool() {
        let config = MiningConfig {
            stratum_config: crate::stratum::StratumConfig {
                primary_pool: crate::stratum::PoolConfig {
                    url: "".to_string(),
                    worker_name: "test-worker".to_string(),
                    password: None,
                    user_agent: Some("Test/1.0".to_string()),
                    ssl: false,
                    backup_pools: vec![],
                },
                connect_timeout_secs: 30,
                reconnect_delay_secs: 10,
                max_reconnect_attempts: 5,
                share_batch_size: 10,
                max_job_age_secs: 60,
                rate_limit: 100.0,
                ssl_verify_hostname: true,
            },
            gpu_devices: vec![0],
            algorithm: MiningAlgorithm::Ethash,
            intensity: 0.8,
        };

        assert!(validate_config(&config).is_err());
    }
}
