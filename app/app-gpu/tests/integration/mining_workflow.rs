//! # Mining Workflow Integration Tests (Kiểm Thử Tích Hợp Quy Trình Khai Thác)
//!
//! **Scenario 1**: Miner Startup → GPU Init → Ready
//!
//! Tests trong file này:
//! 1. `test_successful_miner_startup()` - Khởi động miner thành công với 2 GPUs
//! 2. `test_gpu_initialization_timeout()` - Xử lý timeout khi GPU init chậm
//! 3. `test_multiple_gpu_detection()` - Phát hiện 4 GPUs chính xác

use std::time::Duration;
use tokio::time::{sleep, timeout};

// Import fixtures từ module cha
mod fixtures {
    pub use crate::fixtures::*;
}

/// **Test 1**: Successful miner startup với 2 GPUs
///
/// **Setup**: GpuEmulator với 2 GPUs
/// **Action**: Initialize miner, wait for ready state
/// **Assert**:
/// - GPU count = 2
/// - All initialized
/// - Hashrate > 0
#[tokio::test]
async fn test_successful_miner_startup() {
    fixtures::setup_test_logger();
    tracing::info!("🚀 Starting test: test_successful_miner_startup");

    // Setup: Create emulator với 2 GPUs
    let mut emulator = fixtures::GpuEmulator::new(2);

    // Action: Initialize trong 5s timeout
    let result = timeout(Duration::from_secs(5), emulator.initialize()).await;

    // Assert: Initialization thành công
    assert!(result.is_ok(), "GPU initialization timed out");
    assert!(
        result.unwrap().is_ok(),
        "GPU initialization returned error"
    );

    // Assert: GPU count chính xác
    let device_count = emulator.get_device_count();
    assert_eq!(device_count, 2, "Expected 2 GPUs, found {}", device_count);

    // Assert: Emulator initialized
    assert!(
        emulator.is_initialized(),
        "Emulator should be initialized after successful init"
    );

    // Assert: Hashrate > 0 cho tất cả devices
    for device_id in 0..device_count {
        let hashrate = emulator
            .get_hashrate(device_id)
            .await
            .expect("Failed to get hashrate");
        assert!(
            hashrate > 0.0,
            "GPU {} should have hashrate > 0, got {}",
            device_id,
            hashrate
        );
    }

    tracing::info!("✅ Test passed: Miner startup successful with {} GPUs", device_count);
}

/// **Test 2**: GPU initialization timeout handling
///
/// **Setup**: Emulator với slow init (delay >5s simulated via small timeout)
/// **Action**: Try initialize với 3s timeout
/// **Assert**:
/// - Error returned (timeout)
/// - Not initialized
#[tokio::test]
async fn test_gpu_initialization_timeout() {
    fixtures::setup_test_logger();
    tracing::info!("🚀 Starting test: test_gpu_initialization_timeout");

    // Setup: Create emulator với 2 GPUs (init takes 500ms normally)
    let mut emulator = fixtures::GpuEmulator::new(2);

    // Action: Try initialize với very short timeout (100ms < 500ms required)
    let result = timeout(Duration::from_millis(100), emulator.initialize()).await;

    // Assert: Timeout error occurred
    assert!(
        result.is_err(),
        "Should timeout, but initialization completed"
    );

    // Assert: Emulator NOT initialized
    assert!(
        !emulator.is_initialized(),
        "Emulator should NOT be initialized after timeout"
    );

    tracing::info!("✅ Test passed: Timeout handled correctly");
}

/// **Test 3**: Multiple GPU detection (4 GPUs)
///
/// **Setup**: Emulator với 4 GPUs
/// **Action**: Enumerate devices
/// **Assert**:
/// - Detected count = 4
/// - All devices listed và accessible
#[tokio::test]
async fn test_multiple_gpu_detection() {
    fixtures::setup_test_logger();
    tracing::info!("🚀 Starting test: test_multiple_gpu_detection");

    // Setup: Create emulator với 4 GPUs
    let mut emulator = fixtures::GpuEmulator::new(4);

    // Action: Initialize
    emulator
        .initialize()
        .await
        .expect("Failed to initialize emulator");

    // Assert: Device count chính xác
    let device_count = emulator.get_device_count();
    assert_eq!(
        device_count, 4,
        "Expected 4 GPUs, detected {}",
        device_count
    );

    // Assert: All devices accessible và có valid metrics
    for device_id in 0..device_count {
        // Check hashrate accessible
        let hashrate = emulator
            .get_hashrate(device_id)
            .await
            .expect(&format!("Failed to get hashrate for GPU {}", device_id));

        assert!(
            hashrate > 0.0,
            "GPU {} should have valid hashrate, got {}",
            device_id,
            hashrate
        );

        // Check temperature accessible
        let temp = emulator
            .get_temperature(device_id)
            .await
            .expect(&format!("Failed to get temperature for GPU {}", device_id));

        assert!(
            temp > 0,
            "GPU {} should have valid temperature, got {}",
            device_id,
            temp
        );

        // Check utilization accessible
        let util = emulator
            .get_utilization(device_id)
            .await
            .expect(&format!("Failed to get utilization for GPU {}", device_id));

        assert!(
            util > 0,
            "GPU {} should have valid utilization, got {}",
            device_id,
            util
        );

        tracing::debug!(
            "GPU {}: hashrate={} MH/s, temp={}°C, util={}%",
            device_id,
            hashrate,
            temp,
            util
        );
    }

    tracing::info!("✅ Test passed: All 4 GPUs detected and accessible");
}
