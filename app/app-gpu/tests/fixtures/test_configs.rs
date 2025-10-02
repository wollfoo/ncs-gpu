//! # Test Config Generators (Bộ Tạo Cấu Hình Kiểm Thử)
//!
//! **Config factory functions** (hàm factory cấu hình) cho various test scenarios.

use mining_core::stratum::{PoolConfig, StratumConfig};
use mining_core::{MiningAlgorithm, MiningConfig};

/// **Generate default test config** (tạo cấu hình test mặc định)
///
/// Valid config với reasonable defaults:
/// - Pool: localhost:3333 (mock pool)
/// - Algorithm: Ethash
/// - GPUs: [0, 1]
/// - Intensity: 0.8 (80%)
pub fn generate_test_config() -> MiningConfig {
    MiningConfig {
        stratum_config: StratumConfig {
            primary_pool: PoolConfig {
                url: "stratum+tcp://127.0.0.1:3333".to_string(),
                worker_name: "test-worker-001".to_string(),
                password: Some("x".to_string()),
                user_agent: Some("TestMiner/1.0.0".to_string()),
                ssl: false,
                backup_pools: vec![],
            },
            connect_timeout_secs: 10,
            reconnect_delay_secs: 5,
            max_reconnect_attempts: 3,
            share_batch_size: 10,
            max_job_age_secs: 60,
            rate_limit: 100.0,
            ssl_verify_hostname: false,
        },
        algorithm: MiningAlgorithm::Ethash,
        gpu_devices: vec![0, 1],
        intensity: 0.8,
    }
}

/// **Generate invalid config** (tạo cấu hình không hợp lệ)
///
/// Missing required fields hoặc invalid values:
/// - Empty pool URL
/// - No GPU devices
/// - Invalid intensity
///
/// Dùng để test validation logic.
pub fn generate_invalid_config() -> MiningConfig {
    MiningConfig {
        stratum_config: StratumConfig {
            primary_pool: PoolConfig {
                url: "".to_string(), // ❌ Empty URL
                worker_name: "".to_string(), // ❌ Empty worker name
                password: None,
                user_agent: None,
                ssl: false,
                backup_pools: vec![],
            },
            connect_timeout_secs: 0, // ❌ Zero timeout
            reconnect_delay_secs: 0,
            max_reconnect_attempts: 0,
            share_batch_size: 0, // ❌ Zero batch size
            max_job_age_secs: 0,
            rate_limit: 0.0, // ❌ Zero rate limit
            ssl_verify_hostname: false,
        },
        algorithm: MiningAlgorithm::Ethash,
        gpu_devices: vec![], // ❌ No GPUs
        intensity: 1.5, // ❌ Out of range (>1.0)
    }
}

/// **Generate high performance config** (tạo cấu hình hiệu năng cao)
///
/// Aggressive settings cho maximum throughput:
/// - High intensity (0.95)
/// - Multiple GPUs (4 devices)
/// - Large batch size (50)
/// - Short timeouts (fast failover)
///
/// Dùng để test performance limits.
pub fn generate_high_performance_config() -> MiningConfig {
    MiningConfig {
        stratum_config: StratumConfig {
            primary_pool: PoolConfig {
                url: "stratum+tcp://127.0.0.1:3333".to_string(),
                worker_name: "high-perf-worker".to_string(),
                password: Some("x".to_string()),
                user_agent: Some("HighPerfMiner/1.0.0".to_string()),
                ssl: false,
                backup_pools: vec![
                    PoolConfig {
                        url: "stratum+tcp://backup1.pool.com:3333".to_string(),
                        worker_name: "high-perf-worker".to_string(),
                        password: Some("x".to_string()),
                        user_agent: Some("HighPerfMiner/1.0.0".to_string()),
                        ssl: false,
                        backup_pools: vec![],
                    },
                    PoolConfig {
                        url: "stratum+tcp://backup2.pool.com:3333".to_string(),
                        worker_name: "high-perf-worker".to_string(),
                        password: Some("x".to_string()),
                        user_agent: Some("HighPerfMiner/1.0.0".to_string()),
                        ssl: false,
                        backup_pools: vec![],
                    },
                ],
            },
            connect_timeout_secs: 5, // Fast timeout
            reconnect_delay_secs: 2, // Quick reconnect
            max_reconnect_attempts: 10, // Nhiều retries
            share_batch_size: 50, // Large batches
            max_job_age_secs: 30, // Short job lifetime
            rate_limit: 500.0, // High rate
            ssl_verify_hostname: false,
        },
        algorithm: MiningAlgorithm::Ethash,
        gpu_devices: vec![0, 1, 2, 3], // 4 GPUs
        intensity: 0.95, // 95% intensity
    }
}

/// **Generate low power config** (tạo cấu hình tiêu thụ thấp)
///
/// Conservative settings cho power efficiency:
/// - Low intensity (0.5)
/// - Single GPU
/// - Small batch size (5)
/// - Long timeouts (stable operation)
///
/// Dùng để test stealth mode hoặc power-constrained scenarios.
pub fn generate_low_power_config() -> MiningConfig {
    MiningConfig {
        stratum_config: StratumConfig {
            primary_pool: PoolConfig {
                url: "stratum+tcp://127.0.0.1:3333".to_string(),
                worker_name: "low-power-worker".to_string(),
                password: Some("x".to_string()),
                user_agent: Some("StealthMiner/1.0.0".to_string()),
                ssl: false,
                backup_pools: vec![],
            },
            connect_timeout_secs: 30, // Slow timeout
            reconnect_delay_secs: 15, // Slower reconnect
            max_reconnect_attempts: 3,
            share_batch_size: 5, // Small batches
            max_job_age_secs: 120, // Long job lifetime
            rate_limit: 50.0, // Low rate
            ssl_verify_hostname: false,
        },
        algorithm: MiningAlgorithm::Ethash,
        gpu_devices: vec![0], // Single GPU
        intensity: 0.5, // 50% intensity (low power)
    }
}

/// **Generate SSL config** (tạo cấu hình SSL)
///
/// Secure connection settings:
/// - SSL enabled
/// - Hostname verification
/// - stratum+ssl:// URL
///
/// Dùng để test secure pool connections.
pub fn generate_ssl_config() -> MiningConfig {
    let mut config = generate_test_config();

    config.stratum_config.primary_pool.url = "stratum+ssl://ssl.pool.com:3443".to_string();
    config.stratum_config.primary_pool.ssl = true;
    config.stratum_config.ssl_verify_hostname = true;

    config
}

/// **Generate multi-algorithm config** (tạo config đa thuật toán)
///
/// Return configs cho các algorithm khác nhau để test switching.
pub fn generate_algorithm_configs() -> Vec<MiningConfig> {
    vec![
        // Ethash
        {
            let mut config = generate_test_config();
            config.algorithm = MiningAlgorithm::Ethash;
            config
        },
        // KawPow
        {
            let mut config = generate_test_config();
            config.algorithm = MiningAlgorithm::KawPow;
            config
        },
        // RandomX
        {
            let mut config = generate_test_config();
            config.algorithm = MiningAlgorithm::RandomX;
            config
        },
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config_valid() {
        let config = generate_test_config();

        assert_eq!(config.algorithm, MiningAlgorithm::Ethash);
        assert_eq!(config.gpu_devices.len(), 2);
        assert!(config.intensity > 0.0 && config.intensity <= 1.0);
        assert!(!config.stratum_config.primary_pool.url.is_empty());
    }

    #[test]
    fn test_invalid_config_has_errors() {
        let config = generate_invalid_config();

        // Empty URL
        assert!(config.stratum_config.primary_pool.url.is_empty());

        // No GPUs
        assert!(config.gpu_devices.is_empty());

        // Invalid intensity
        assert!(config.intensity > 1.0);
    }

    #[test]
    fn test_high_performance_config() {
        let config = generate_high_performance_config();

        assert!(config.intensity >= 0.9);
        assert!(config.gpu_devices.len() >= 4);
        assert_eq!(config.stratum_config.share_batch_size, 50);
        assert!(!config.stratum_config.primary_pool.backup_pools.is_empty());
    }

    #[test]
    fn test_low_power_config() {
        let config = generate_low_power_config();

        assert!(config.intensity <= 0.5);
        assert_eq!(config.gpu_devices.len(), 1);
        assert_eq!(config.stratum_config.share_batch_size, 5);
    }

    #[test]
    fn test_ssl_config() {
        let config = generate_ssl_config();

        assert!(config.stratum_config.primary_pool.ssl);
        assert!(config.stratum_config.ssl_verify_hostname);
        assert!(config.stratum_config.primary_pool.url.contains("ssl"));
    }

    #[test]
    fn test_algorithm_configs() {
        let configs = generate_algorithm_configs();

        assert_eq!(configs.len(), 3);
        assert_eq!(configs[0].algorithm, MiningAlgorithm::Ethash);
        assert_eq!(configs[1].algorithm, MiningAlgorithm::KawPow);
        assert_eq!(configs[2].algorithm, MiningAlgorithm::RandomX);
    }
}
