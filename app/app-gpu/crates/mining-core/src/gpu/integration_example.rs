//! # GPU Manager Integration Example (Ví dụ tích hợp GPU Manager)
//!
//! **Complete example** showing how to use GpuManager in a mining application.
//!
//! This example demonstrates:
//! - Device enumeration and selection
//! - Algorithm initialization with thermal monitoring
//! - Background monitoring and stats collection
//! - Proper cleanup and resource management

use crate::gpu::{GpuManager, GpuAlgorithm, ThermalThresholds, GpuManagerStats};
use crate::MiningAlgorithm;
use std::time::Duration;
use tokio::time::sleep;

/// **Example: Basic GPU Mining Setup** (Thiết lập khai thác cơ bản)
// Trong production app, có thể gọi hàm này từ main
pub async fn example_gpu_mining_basic() -> Result<(), Box<dyn std::error::Error>> {
    println!("🚀 GPU Mining Manager - Basic Example");
    println!("=====================================");

    // 1. Create GPU Manager (Tạo GPU Manager)
    let manager = GpuManager::builder()
        .with_thermal_thresholds(ThermalThresholds {
            warning_celsius: 75.0,
            critical_celsius: 85.0,
            max_fan_speed: 80,
        })
        .enable_auto_fan_control()
        .build();

    println!("✅ GPU Manager created");

    // 2. Enumerate available GPUs (Liệt kê GPU có sẵn)
    println!("🔍 Enumerating GPU devices...");
    let devices = manager.enumerate_devices().await?;

    if devices.is_empty() {
        println!("⚠️  No GPU devices found");
        return Ok(());
    }

    println!("✅ Found {} GPU device(s):", devices.len());
    for device in &devices {
        println!("  • {}", device);
    }

    // 3. Select devices for mining (chọn thiết bị khai thác)
    let active_devices: Vec<usize> = devices.iter().map(|d| d.device_id).collect();
    println!("🎯 Using devices: {:?}", active_devices);

    // 4. Initialize for mining algorithm (khởi tạo thuật toán khai thác)
    println!("⚡ Initializing for Ethash mining...");
    manager.initialize_for_algorithm(GpuAlgorithm::Ethash, &active_devices).await?;
    println!("✅ GPU initialization complete");

    // 5. Start monitoring (bắt đầu giám sát)
    println!("📊 Starting monitoring loop...");
    manager.start_monitoring_loop().await?;
    println!("✅ Monitoring started");

    // 6. Run mining simulation (chạy mô phỏng khai thác)
    println!("⛏️  Running mining simulation...");
    for i in 0..12 { // Run for ~1 minute
        sleep(Duration::from_secs(5)).await;

        let stats: GpuManagerStats = manager.get_mining_stats().await?;
        print_stats_summary(&stats, i + 1);
    }

    // 7. Cleanup (dọn dẹp)
    println!("\n🧹 Cleaning up...");
    manager.cleanup().await?;
    println!("✅ Cleanup complete");

    Ok(())
}

/// **Example: Advanced Multi-Algorithm Support** (Hỗ trợ đa thuật toán nâng cao)
pub async fn example_multi_algorithm_support() -> Result<(), Box<dyn std::error::Error>> {
    println!("🔄 GPU Mining Manager - Multi-Algorithm Example");
    println!("==============================================");

    let manager = GpuManager::new_with_monitoring(ThermalThresholds::default());

    // Enumerate devices
    let devices = manager.enumerate_devices().await?;
    let device_ids: Vec<usize> = devices.iter().map(|d| d.device_id).collect();

    // Test different algorithms
    let algorithms = vec![
        (GpuAlgorithm::Ethash, "Ethereum mining"),
        (GpuAlgorithm::KawPow, "Ravencoin mining"),
        (GpuAlgorithm::RandomX, "Monero mining"),
    ];

    for (algorithm, description) in algorithms {
        println!("\n🎯 Testing {} algorithm...", description);

        // Check if algorithm is supported
        let supported = devices.iter().all(|device| {
            let (major, minor) = device.compute_capability;
            let (req_major, req_minor) = algorithm.min_compute_capability();
            major > req_major || (major == req_major && minor >= req_minor)
        });

        if !supported {
            println!("⚠️  Skipping {} - insufficient compute capability", description);
            continue;
        }

        // Initialize
        manager.initialize_for_algorithm(algorithm, &device_ids).await?;
        manager.start_monitoring_loop().await?;

        // Run for 10 seconds
        sleep(Duration::from_secs(10)).await;

        let stats: GpuManagerStats = manager.get_mining_stats().await?;
        println!("📊 Result: {} active devices, ~{}°C average temperature",
                stats.active_devices,
                calculate_average_temp(&stats));

        manager.stop_monitoring_loop().await?;
        manager.cleanup().await?;
    }

    Ok(())
}

/// **Helper: Print stats summary** (Trợ giúp: in tóm tắt thống kê)
fn print_stats_summary(stats: &GpuManagerStats, iteration: u32) {
    let avg_temp = calculate_average_temp(stats);

    print!("📊 [{:<2}] ", iteration);

    if let Some(alg) = stats.algorithm {
        print!("{:?} ", alg);
    }

    print!("{}devs {:.1}°C", stats.active_devices, avg_temp);

    if !stats.device_stats.is_empty() {
        let total_util: f32 = stats.device_stats.values()
            .map(|s| s.utilization)
            .sum();
        let avg_util = total_util / stats.device_stats.len() as f32;
        print!(" {:.1}% util", avg_util);
    }

    println!();
}

/// **Helper: Calculate average temperature** (Trợ giúp: tính nhiệt độ trung bình)
fn calculate_average_temp(stats: &GpuManagerStats) -> f32 {
    if stats.device_stats.is_empty() {
        return 0.0;
    }

    let total: f32 = stats.device_stats.values()
        .map(|s| s.temperature)
        .sum();

    total / stats.device_stats.len() as f32
}

/// **Error Handling Example** (Ví dụ xử lý lỗi)
pub async fn example_error_handling() -> Result<(), Box<dyn std::error::Error>> {
    println!("🚨 GPU Mining Manager - Error Handling Example");
    println!("=============================================");

    let manager = GpuManager::new();

    // Try operations that might fail
    match manager.enumerate_devices().await {
        Ok(devices) => {
            println!("✅ Device enumeration succeeded: {} devices", devices.len());

            if devices.is_empty() {
                println!("⚠️  No devices found - running in CPU-only mode");
                return Ok(());
            }

            // Try initialization with invalid device
            match manager.initialize_for_algorithm(GpuAlgorithm::Ethash, &[999]).await {
                Ok(_) => println!("✅ Initialization succeeded"),
                Err(e) => println!("⚠️  Initialization failed as expected: {}", e),
            }

            // Try initialization with valid device
            let device_ids = vec![0]; // Assume device 0 exists
            match manager.initialize_for_algorithm(GpuAlgorithm::Ethash, &device_ids).await {
                Ok(_) => {
                    println!("✅ Initialization succeeded with device 0");

                    // Cleanup
                    match manager.cleanup().await {
                        Ok(_) => println!("✅ Cleanup succeeded"),
                        Err(e) => println!("⚠️  Cleanup failed: {}", e),
                    }
                }
                Err(e) => println!("⚠️  Initialization failed: {}", e),
            }
        }
        Err(e) => {
            println!("⚠️  Device enumeration failed: {}", e);
            println!("💡 Check if NVIDIA drivers are installed and GPUs are available");
        }
    }

    Ok(())
}