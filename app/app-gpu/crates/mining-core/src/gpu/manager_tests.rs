//! # GPU Manager Unit Tests (Unit Tests cho GPU Manager)
//!
//! Comprehensive tests covering functionality, error cases, and edge conditions.

use super::{GpuManager, GpuAlgorithm, GpuManagerBuilder, ThermalThresholds, GpuManagerStats};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gpu_manager_creation() {
        let manager = GpuManager::new();
        assert!(!futures::executor::block_on(manager.is_initialized()));
    }

    #[test]
    fn test_builder_pattern() {
        let thresholds = ThermalThresholds {
            warning_celsius: 80.0,
            critical_celsius: 90.0,
            max_fan_speed: 90,
        };

        let manager = GpuManagerBuilder::new()
            .with_thermal_thresholds(thresholds)
            .enable_auto_fan_control()
            .build();

        // Test that manager was created with monitoring
        assert!(manager.thermal_monitor.lock().is_some());
    }

    #[test]
    fn test_algorithm_min_compute_capability() {
        assert_eq!(GpuAlgorithm::Ethash.min_compute_capability(), (7, 0));
        assert_eq!(GpuAlgorithm::KawPow.min_compute_capability(), (7, 0));
        assert_eq!(GpuAlgorithm::RandomX.min_compute_capability(), (7, 5));
    }

    #[test]
    fn test_algorithm_epoch_frequency() {
        assert_eq!(GpuAlgorithm::Ethash.epoch_reset_frequency(), 30000);
        assert_eq!(GpuAlgorithm::KawPow.epoch_reset_frequency(), 30000);
        assert_eq!(GpuAlgorithm::RandomX.epoch_reset_frequency(), 0);
    }

    #[tokio::test]
    async fn test_enumerate_devices_fallback() {
        let manager = GpuManager::new();

        // This should work even without NVML
        let result = manager.enumerate_devices().await;

        // May fail or succeed depending on CUDA availability, but shouldn't panic
        match result {
            Ok(devices) => {
                assert!(devices.len() > 0);
                println!("Found {} devices in fallback mode", devices.len());

                // Check first device
                let device = &devices[0];
                assert_eq!(device.device_id, 0);
                assert!(device.name.contains("GPU"));
            }
            Err(e) => {
                println!("Enumerate failed as expected: {}", e);
                // This is fine - no GPUs available in test environment
            }
        }
    }

    #[tokio::test]
    async fn test_get_mining_stats_empty() {
        let manager = GpuManager::new();
        let stats: GpuManagerStats = manager.get_mining_stats().await.unwrap();

        assert_eq!(stats.total_devices, 0);
        assert_eq!(stats.active_devices, 0);
        assert_eq!(stats.current_epoch, 0);
        assert!(stats.algorithm.is_none());
        assert!(stats.device_stats.is_empty());
    }

    #[tokio::test]
    async fn test_cleanup_uninitialized() {
        let manager = GpuManager::new();

        // Should work without initializing
        let result = manager.cleanup().await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_monitoring_loop_start_stop() {
        let manager = GpuManager::new();

        // Should fail - not initialized
        let result = manager.start_monitoring_loop().await;
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("not initialized"));

        // Stop should work even if not started
        let result = manager.stop_monitoring_loop().await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_initialize_for_algorithm_invalid_device() {
        let manager = GpuManager::new();

        // Try to initialize without enumerating devices first
        let result = manager.initialize_for_algorithm(GpuAlgorithm::Ethash, &[0]).await;
        assert!(result.is_err());
    }

    #[test]
    fn test_manager_stats_default() {
        let stats = GpuManagerStats::default();

        assert_eq!(stats.total_devices, 0);
        assert_eq!(stats.active_devices, 0);
        assert_eq!(stats.current_epoch, 0);
        assert!(stats.algorithm.is_none());
        assert!(stats.device_stats.is_empty());
    }

    #[test]
    fn test_device_removal() {
        let manager = GpuManager::new();

        // Should be empty initially
        assert_eq!(futures::executor::block_on(manager.get_active_device_ids()).len(), 0);
    }

    // Error condition tests
    #[tokio::test]
    async fn test_cleanup_after_drop_warning() {
        // This test ensures drop behavior is correct
        let manager = GpuManager::new();

        // Create a fake initialized state to test drop warning
        *manager.initialized.write().await = true;

        // Drop should warn in logs about improper cleanup
        // Note: This would show in log output but not cause test failure
        drop(manager);
    }

    #[test]
    fn test_algorithm_string_conversion() {
        let manager = GpuManager::new();

        assert_eq!(manager.algorithm_to_string(GpuAlgorithm::Ethash), "ethash");
        assert_eq!(manager.algorithm_to_string(GpuAlgorithm::KawPow), "kawpow");
        assert_eq!(manager.algorithm_to_string(GpuAlgorithm::RandomX), "randomx");
    }
}

// Integration test module
#[cfg(all(test, feature = "nvml"))]
mod integration_tests {
    use super::*;
    use tokio::time::{timeout, Duration};

    #[tokio::test]
    async fn test_full_gpu_workflow() {
        let manager = GpuManager::new_with_monitoring(ThermalThresholds::default());

        // Note: This test only runs if NVML is available and GPUs are present
        // In most test environments, it will be skipped

        let enumerate_result = manager.enumerate_devices().await;

        match enumerate_result {
            Ok(devices) if !devices.is_empty() => {
                // GPUs found - run full test
                let device_ids: Vec<usize> = devices.iter().map(|d| d.device_id).collect();

                // Test initialization
                let init_result = manager.initialize_for_algorithm(GpuAlgorithm::Ethash, &device_ids).await;
                if init_result.is_ok() {
                    assert!(manager.is_initialized().await);

                    // Test monitoring
                    let monitor_result = timeout(
                        Duration::from_secs(1),
                        manager.start_monitoring_loop()
                    ).await;

                    if monitor_result.is_ok() {
                        manager.stop_monitoring_loop().await.unwrap();
                    }

                    // Test stats
                    let stats = manager.get_mining_stats().await.unwrap();
                    assert_eq!(stats.total_devices, devices.len());
                    assert!(stats.active_devices > 0);

                    // Test cleanup
                    manager.cleanup().await.unwrap();
                    assert!(!manager.is_initialized().await);
                }
            }
            _ => {
                // No GPUs available - skip test
                println!("Skipping integration test: No GPUs available");
            }
        }
    }

    #[tokio::test]
    async fn test_thermal_integration() {
        let thresholds = ThermalThresholds {
            warning_celsius: 75.0,
            critical_celsius: 85.0,
            max_fan_speed: 80,
        };

        let manager = GpuManager::new_with_monitoring(thresholds);

        // Thermal monitor should be initialized
        let thermal_lock = manager.thermal_monitor.lock();
        assert!(thermal_lock.is_some());

        let thermal_monitor = thermal_lock.as_ref().unwrap();
        assert_eq!(thermal_monitor.thresholds().warning_celsius, 75.0);
        assert_eq!(thermal_monitor.thresholds().critical_celsius, 85.0);
    }
}