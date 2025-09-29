//! Basic usage examples for OPUS-GPU Configuration Management System

use opus_gpu_config::{
    AppConfig, ConfigManager, ConfigSource, ManagerConfig,
    security::{EncryptionConfig, SecretManager},
    audit::{AuditConfig, AuditLogger},
    validation::{ConfigValidator, ValidationConfig, builtin_rules::*},
    watcher::WatcherConfig,
    formats::ConfigFormat,
};
use std::path::PathBuf;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing for logging
    tracing_subscriber::init();

    println!("🔧 OPUS-GPU Configuration Management System Examples");

    // Example 1: Basic Configuration Loading
    basic_configuration_loading().await?;

    // Example 2: Configuration with Validation
    configuration_with_validation().await?;

    // Example 3: Secure Configuration with Encryption
    secure_configuration().await?;

    // Example 4: Hot Reload Configuration
    hot_reload_configuration().await?;

    // Example 5: Configuration Manager with Full Features
    full_featured_manager().await?;

    println!("✅ All examples completed successfully!");
    Ok(())
}

/// Example 1: Basic Configuration Loading
async fn basic_configuration_loading() -> Result<(), Box<dyn std::error::Error>> {
    println!("\n📝 Example 1: Basic Configuration Loading");

    // Create default configuration
    let config = AppConfig::default();
    println!("Default mining algorithm: {}", config.mining.algorithm);
    println!("Default worker count: {}", config.mining.max_workers);
    println!("Default API port: {}", config.api.rest.port);

    // Save configuration to different formats
    config.save("./examples/config.toml").await?;
    println!("Configuration saved to TOML format");

    // Load configuration back
    let loaded_config = AppConfig::load("./examples/config.toml").await?;
    println!("Configuration loaded successfully");

    // Verify loaded config matches
    assert_eq!(config.mining.algorithm, loaded_config.mining.algorithm);
    println!("✅ Configuration integrity verified");

    Ok(())
}

/// Example 2: Configuration with Validation
async fn configuration_with_validation() -> Result<(), Box<dyn std::error::Error>> {
    println!("\n🔍 Example 2: Configuration with Validation");

    // Create validator with custom rules
    let validation_config = ValidationConfig::default();
    let mut validator = ConfigValidator::new(validation_config);

    // Add built-in validation rules
    validator.add_custom_rule(Box::new(PortConflictRule));
    validator.add_custom_rule(Box::new(ResourceUsageRule));

    // Create configuration with potential issues
    let mut config = AppConfig::default();
    config.api.rest.port = 8080;
    config.api.websocket.port = 8080; // Port conflict!
    config.mining.memory_size = 64 * 1024 * 1024 * 1024; // 64GB - too much!

    // Validate configuration
    let config_json = serde_json::to_value(&config)?;
    let validation_result = validator.validate_config(&config_json).await?;

    println!("Validation result: {}", if validation_result.is_valid { "PASSED" } else { "FAILED" });
    println!("Errors found: {}", validation_result.errors.len());
    println!("Warnings found: {}", validation_result.warnings.len());

    for error in &validation_result.errors {
        println!("  ❌ Error: {} at {}", error.message, error.path);
        if let Some(ref suggestion) = error.suggestion {
            println!("     💡 Suggestion: {}", suggestion);
        }
    }

    for warning in &validation_result.warnings {
        println!("  ⚠️  Warning: {} at {}", warning.message, warning.path);
        if let Some(ref suggestion) = warning.suggestion {
            println!("     💡 Suggestion: {}", suggestion);
        }
    }

    println!("✅ Validation completed");
    Ok(())
}

/// Example 3: Secure Configuration with Encryption
async fn secure_configuration() -> Result<(), Box<dyn std::error::Error>> {
    println!("\n🔐 Example 3: Secure Configuration with Encryption");

    // Create secret manager
    let encryption_config = EncryptionConfig::default();
    let mut secret_manager = SecretManager::new("my_secure_password", encryption_config)?;

    // Store some secrets
    secret_manager.store_secret(
        "pool_password".to_string(),
        secrecy::Secret::new("super_secure_pool_password".to_string())
    )?;

    secret_manager.store_secret(
        "wallet_private_key".to_string(),
        secrecy::Secret::new("private_key_data_here".to_string())
    )?;

    println!("Stored secrets: {:?}", secret_manager.list_secrets());

    // Retrieve and verify secrets
    if let Some(password) = secret_manager.get_secret("pool_password")? {
        println!("Retrieved pool password (hidden): [PROTECTED]");
    }

    // Demonstrate encryption of configuration
    let config = AppConfig::default();
    let encryption_key = b"my_32_byte_key_for_encryption!!!";
    let encrypted_data = config.to_encrypted_bytes(encryption_key).await?;
    println!("Configuration encrypted: {} bytes", encrypted_data.len());

    // Decrypt and verify
    let decrypted_config = AppConfig::from_encrypted_bytes(&encrypted_data, encryption_key).await?;
    assert_eq!(config.mining.algorithm, decrypted_config.mining.algorithm);
    println!("✅ Encryption/decryption verified");

    Ok(())
}

/// Example 4: Hot Reload Configuration
async fn hot_reload_configuration() -> Result<(), Box<dyn std::error::Error>> {
    println!("\n🔥 Example 4: Hot Reload Configuration");

    // Create configuration file
    let config_path = PathBuf::from("./examples/hot_reload_config.toml");
    let config = AppConfig::default();
    config.save(&config_path).await?;

    // Create watcher configuration
    let watcher_config = WatcherConfig {
        debounce_delay: std::time::Duration::from_millis(100),
        enable_audit_logging: true,
        ..Default::default()
    };

    // Create watcher
    let mut watcher = opus_gpu_config::watcher::ConfigWatcher::new(
        config_path.clone(),
        config,
        watcher_config
    );

    // Start watching (in a real application, you would handle these events)
    let (config_rx, _event_rx) = watcher.start_watching().await?;
    println!("Started watching configuration file: {}", config_path.display());

    // Simulate configuration change
    tokio::time::sleep(std::time::Duration::from_millis(200)).await;

    let mut new_config = AppConfig::default();
    new_config.mining.algorithm = "SHA3".to_string();
    new_config.save(&config_path).await?;
    println!("Configuration file updated");

    // Wait for reload
    tokio::time::sleep(std::time::Duration::from_millis(1000)).await;

    // Check if configuration was reloaded
    let current = config_rx.borrow().clone();
    if current.mining.algorithm == "SHA3" {
        println!("✅ Hot reload successful - algorithm changed to: {}", current.mining.algorithm);
    } else {
        println!("⚠️  Hot reload might still be processing...");
    }

    // Clean up
    let _ = tokio::fs::remove_file(&config_path).await;

    Ok(())
}

/// Example 5: Configuration Manager with Full Features
async fn full_featured_manager() -> Result<(), Box<dyn std::error::Error>> {
    println!("\n🚀 Example 5: Configuration Manager with Full Features");

    // Create audit logger
    let audit_config = AuditConfig {
        enabled: true,
        max_memory_events: 1000,
        log_file: Some(PathBuf::from("./examples/audit.log")),
        ..Default::default()
    };
    let audit_logger = std::sync::Arc::new(AuditLogger::new(audit_config)?);

    // Create validator
    let validation_config = ValidationConfig::default();
    let mut validator = ConfigValidator::new(validation_config);
    validator.add_custom_rule(Box::new(PortConflictRule));
    let validator = std::sync::Arc::new(validator);

    // Create secret manager
    let encryption_config = EncryptionConfig::default();
    let secret_manager = std::sync::Arc::new(parking_lot::RwLock::new(
        SecretManager::new("manager_password", encryption_config)?
    ));

    // Create manager with all features
    let manager_config = ManagerConfig {
        enable_caching: true,
        enable_notifications: true,
        enable_auto_backup: true,
        backup_dir: PathBuf::from("./examples/backups"),
        enable_hot_reload: true,
        validate_on_load: true,
        enable_audit_logging: true,
        ..Default::default()
    };

    let initial_config = AppConfig::default();
    let mut manager = ConfigManager::new(initial_config, manager_config)
        .with_validator(validator)
        .with_secret_manager(secret_manager)
        .with_audit_logger(audit_logger.clone());

    // Subscribe to changes
    let mut change_rx = manager.subscribe_to_changes().unwrap();
    let config_rx = manager.subscribe_to_config().unwrap();

    println!("Created configuration manager with full features enabled");

    // Load configuration from multiple sources
    let sources = vec![
        ConfigSource::File {
            path: PathBuf::from("./examples/base_config.toml"),
            format: Some(ConfigFormat::Toml),
        },
        ConfigSource::Environment {
            prefix: "OPUS_GPU_".to_string(),
        },
    ];

    // Create base configuration file
    let base_config = AppConfig::default();
    base_config.save("./examples/base_config.toml").await?;

    let multiple_source = ConfigSource::Multiple { sources };
    let loaded_config = manager.load_from_source(multiple_source).await?;
    println!("Loaded configuration from multiple sources");

    // Listen for one change notification
    tokio::spawn(async move {
        if let Ok(change) = change_rx.recv().await {
            println!("Received configuration change: {:?}", change.change_type);
        }
    });

    // Update configuration
    let mut updated_config = loaded_config.clone();
    updated_config.mining.algorithm = "BLAKE3".to_string();
    manager.update_config(updated_config).await?;

    // Get statistics
    let stats = manager.get_statistics().await?;
    println!("Manager statistics:");
    println!("  Cache size: {}", stats.cache_size);
    println!("  Hot reload enabled: {}", stats.hot_reload_enabled);
    println!("  Validation enabled: {}", stats.validation_enabled);
    println!("  Audit enabled: {}", stats.audit_enabled);
    println!("  Config size: {} bytes", stats.config_size);

    // Get audit statistics
    let audit_stats = audit_logger.get_statistics().await?;
    println!("Audit statistics:");
    println!("  Total events: {}", audit_stats.total_events);
    println!("  Events by category: {:?}", audit_stats.by_category);

    // Clean up example files
    let _ = tokio::fs::remove_file("./examples/config.toml").await;
    let _ = tokio::fs::remove_file("./examples/base_config.toml").await;
    let _ = tokio::fs::remove_dir_all("./examples/backups").await;

    println!("✅ Full-featured configuration manager example completed");

    Ok(())
}