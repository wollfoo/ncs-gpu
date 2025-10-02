//! # Test Fixtures Module (Module Fixtures Kiểm Thử)
//!
//! **Test utilities and mock implementations** (tiện ích test và implementation giả lập)
//! cho Phase 4 integration tests.
//!
//! ## Modules (Các module)
//! - `gpu_emulator`: Fake GPU devices cho testing
//! - `mock_pool`: Mock Stratum pool server
//! - `test_configs`: Configuration generators
//! - `common`: Shared utilities và helpers

pub mod common;
pub mod gpu_emulator;
pub mod mock_pool;
pub mod test_configs;

// Re-export commonly used items (xuất lại các item thường dùng)
pub use common::{
    cleanup_test_artifacts, find_free_port, setup_test_logger, wait_for_condition,
};
pub use gpu_emulator::{
    create_default_emulator, create_high_temp_emulator, create_low_hashrate_emulator,
    GpuEmulator,
};
pub use mock_pool::{MockStratumPool, Share};
pub use test_configs::{
    generate_high_performance_config, generate_invalid_config, generate_low_power_config,
    generate_test_config,
};

#[cfg(test)]
mod integration_tests {
    use super::*;
    use std::time::Duration;

    #[tokio::test]
    async fn test_all_fixtures_compile_and_work() {
        // Test GPU emulator
        let mut emulator = GpuEmulator::new(2);
        emulator.initialize().await.expect("Init failed");
        assert!(emulator.is_initialized());

        // Test GPU emulator helpers
        let default_emu = create_default_emulator().await;
        assert_eq!(default_emu.get_device_count(), 2);

        let high_temp_emu = create_high_temp_emulator().await;
        let temp = high_temp_emu.get_temperature(0).await.unwrap();
        assert_eq!(temp, 90);

        let low_hash_emu = create_low_hashrate_emulator().await;
        let hashrate = low_hash_emu.get_hashrate(0).await.unwrap();
        assert_eq!(hashrate, 5.0);

        // Test mock pool
        let port = find_free_port();
        let pool = MockStratumPool::new(port);
        assert_eq!(pool.get_client_count().await, 0);

        // Test config generators
        let test_config = generate_test_config();
        assert!(!test_config.stratum_config.primary_pool.url.is_empty());

        let invalid_config = generate_invalid_config();
        assert!(invalid_config.stratum_config.primary_pool.url.is_empty());

        let high_perf = generate_high_performance_config();
        assert!(high_perf.intensity >= 0.9);

        let low_power = generate_low_power_config();
        assert!(low_power.intensity <= 0.5);

        // Test common utilities
        let mut counter = 0;
        let result = wait_for_condition(
            || {
                counter += 1;
                counter >= 3
            },
            Duration::from_secs(2),
            Duration::from_millis(100),
        )
        .await;
        assert!(result);

        println!("✅ All fixtures validated successfully!");
    }
}
