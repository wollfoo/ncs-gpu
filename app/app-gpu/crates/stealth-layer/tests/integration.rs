use std::time::Duration;
use tokio::time::sleep;
use stealth_layer::{create_stealth_manager_mut, StealthConfig};
use stealth_layer::config::ProfileConfig;

#[tokio::test]
async fn test_full_stealth_integration() {
    // Create manager với default config
    let mut manager = create_stealth_manager_mut();

    // Start stealth layer
    manager.start().await.unwrap();
    assert!(manager.is_active());

    // Wait for some activity
    sleep(Duration::from_secs(2)).await;

    // Check status
    let status = manager.get_status().await;
    assert!(status.contains_key("ai_training"));

    // Stop
    manager.stop().await.unwrap();
    assert!(!manager.is_active());
}

#[test]
fn test_config_serialization() {
    let config = StealthConfig::default();

    // Serialize to TOML
    let toml = toml::to_string(&config).unwrap();

    // Should contain expected keys
    assert!(toml.contains("enabled = true"));
    assert!(toml.contains("log_frequency = \"30s\""));
    assert!(toml.contains("gpu_target = 0.8"));

    // Test round-trip
    let parsed: StealthConfig = toml::from_str(&toml).unwrap();
    assert_eq!(config.ai_training.enabled, parsed.ai_training.enabled);
    assert_eq!(config.ai_training.log_frequency, parsed.ai_training.log_frequency);
    assert_eq!(config.ai_training.gpu_target, parsed.ai_training.gpu_target);
    assert_eq!(config.camouflage.gpu_target, parsed.camouflage.gpu_target);
}

#[tokio::test]
async fn test_multiple_profiles_configuration() {
    // Create custom config with multiple profiles enabled
    let config = StealthConfig {
        ai_training: ProfileConfig {
            enabled: true,
            log_frequency: Duration::from_secs(10),
            gpu_target: 0.9,
            total_epochs: 50,
        },
        ai_inference: ProfileConfig {
            enabled: true,
            log_frequency: Duration::from_secs(2),
            gpu_target: 0.7,
            total_epochs: 0,
        },
        image_processing: ProfileConfig {
            enabled: true,
            log_frequency: Duration::from_secs(5),
            gpu_target: 0.6,
            total_epochs: 0,
        },
        scientific: ProfileConfig {
            enabled: false,
            log_frequency: Duration::from_secs(30),
            gpu_target: 0.8,
            total_epochs: 0,
        },
        ..Default::default()
    };

    let mut manager = stealth_layer::ProfileManager::new(config).unwrap();

    // Get initial status (all inactive)
    let initial_status = manager.get_status().await;
    assert_eq!(initial_status.len(), 3);
    assert!(initial_status.contains_key("ai_training"));
    assert!(initial_status.contains_key("ai_inference"));
    assert!(initial_status.contains_key("image_processing"));
    assert!(!initial_status.contains_key("scientific"));

    // Should count 3 registered profiles
    assert_eq!(manager.profile_count(), 3);
}

#[tokio::test]
async fn test_gpu_target_calculation() {
    // Test with single profile
    let config = StealthConfig {
        ai_training: ProfileConfig {
            enabled: true,
            log_frequency: Duration::from_secs(30),
            gpu_target: 0.8,
            total_epochs: 100,
        },
        ..Default::default()
    };

    let manager = stealth_layer::ProfileManager::new(config).unwrap();

    // With one profile, should return that profile's target
    let target = manager.get_stealth_gpu_target().await;
    assert_eq!(target, 0.8);

    // Test with multiple profiles
    let config_multi = StealthConfig {
        ai_training: ProfileConfig {
            enabled: true,
            log_frequency: Duration::from_secs(30),
            gpu_target: 0.8,
            total_epochs: 100,
        },
        ai_inference: ProfileConfig {
            enabled: true,
            log_frequency: Duration::from_secs(5),
            gpu_target: 0.6,
            total_epochs: 0,
        },
        ..Default::default()
    };

    let manager_multi = stealth_layer::ProfileManager::new(config_multi).unwrap();

    // Should average the targets: (0.8 + 0.6) / 2 = 0.7
    let target_multi = manager_multi.get_stealth_gpu_target().await;
    assert!((target_multi - 0.7).abs() < 1e-6); // Account for floating point precision
}

#[tokio::test]
async fn test_profile_lifecycle() {
    let config = StealthConfig::default();
    let mut manager = stealth_layer::ProfileManager::new(config).unwrap();

    // Test lifecycle
    assert!(!manager.is_active());

    manager.start().await.unwrap();
    assert!(manager.is_active());

    let status = manager.get_status().await;
    assert_eq!(*status.get("ai_training").unwrap_or(&false), true);

    manager.stop().await.unwrap();
    assert!(!manager.is_active());
}