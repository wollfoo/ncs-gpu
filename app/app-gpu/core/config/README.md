# Agent-GPU Configuration Management System

**Advanced Configuration Management** (Hệ thống quản lý cấu hình cao cấp) với đầy đủ tính năng **security** (bảo mật), **hot reload** (tải lại nóng), **validation** (xác thực), và **audit logging** (ghi log kiểm toán).

## 🌟 Features (Tính năng)

### 📁 **Multi-Format Support** (Hỗ trợ đa định dạng)
- **TOML**, **YAML**, **JSON** configuration files
- **Automatic format detection** (Phát hiện định dạng tự động)
- **Format conversion utilities** (Tiện ích chuyển đổi định dạng)

### 🔄 **Hot Reload** (Tải lại nóng)
- **File watching** với inotify events
- **Debounced reload** (Tải lại có độ trễ) để tránh spam
- **Atomic updates** (Cập nhật nguyên tử)
- **Rollback on error** (Rollback khi lỗi)
- **Change notifications** (Thông báo thay đổi)

### 🔐 **Security** (Bảo mật)
- **AES-256-GCM encryption** cho sensitive values
- **PBKDF2 key derivation** với salt
- **Secret management** (Quản lý bí mật)
- **Access control** (Kiểm soát truy cập) with RBAC
- **Configuration integrity checking** (Kiểm tra tính toàn vẹn)

### ✅ **Comprehensive Validation** (Xác thực toàn diện)
- **JSON Schema validation** (Xác thực lược đồ JSON)
- **Custom validation rules** (Quy tắc xác thực tùy chỉnh)
- **Business logic validation** (Xác thực logic nghiệp vụ)
- **Built-in security checks** (Kiểm tra bảo mật tích hợp)
- **Performance validation** (Xác thực hiệu năng)

### 📊 **Audit Logging** (Ghi log kiểm toán)
- **Comprehensive event tracking** (Theo dõi sự kiện toàn diện)
- **Structured logging** với JSON format
- **Log rotation** (Xoay log) và compression
- **Real-time event streaming** (Truyền sự kiện thời gian thực)
- **Audit statistics** (Thống kê kiểm toán)

### 🚀 **Advanced Management** (Quản lý nâng cao)
- **Configuration caching** (Cache cấu hình)
- **Automatic backups** (Sao lưu tự động)
- **Multi-source loading** (Tải từ nhiều nguồn)
- **Environment variable override** (Ghi đè biến môi trường)
- **Remote configuration loading** (Tải cấu hình từ xa)

## 📋 Architecture (Kiến trúc)

```
core/config/src/
├── lib.rs              # Main module với AppConfig definition
├── manager.rs          # ConfigManager - Advanced config management
├── watcher.rs          # ConfigWatcher - Hot reload system
├── security.rs         # SecretManager - Encryption & secrets
├── validation.rs       # ConfigValidator - Validation system
├── audit.rs           # AuditLogger - Audit logging system
├── formats.rs         # Format detection & conversion
└── errors.rs          # Error types & handling
```

## 🚀 Quick Start (Bắt đầu nhanh)

### Basic Configuration Loading

```rust
use opus_gpu_config::AppConfig;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Load configuration from file
    let config = AppConfig::load("config.toml").await?;

    println!("Mining algorithm: {}", config.mining.algorithm);
    println!("API port: {}", config.api.rest.port);

    Ok(())
}
```

### Advanced Configuration Manager

```rust
use opus_gpu_config::{
    ConfigManager, ConfigSource, ManagerConfig,
    validation::{ConfigValidator, ValidationConfig},
    security::SecretManager,
    audit::{AuditLogger, AuditConfig},
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create components
    let validator = Arc::new(ConfigValidator::new(ValidationConfig::default()));
    let audit_logger = Arc::new(AuditLogger::new(AuditConfig::default())?);

    // Create full-featured manager
    let mut manager = ConfigManager::new(
        AppConfig::default(),
        ManagerConfig::default()
    )
    .with_validator(validator)
    .with_audit_logger(audit_logger);

    // Load from multiple sources
    let source = ConfigSource::Multiple {
        sources: vec![
            ConfigSource::File {
                path: "base.toml".into(),
                format: None
            },
            ConfigSource::Environment {
                prefix: "OPUS_GPU_".to_string()
            },
        ]
    };

    let config = manager.load_from_source(source).await?;
    println!("Configuration loaded successfully!");

    Ok(())
}
```

### Hot Reload Setup

```rust
use opus_gpu_config::watcher::{ConfigWatcher, WatcherConfig};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let config = AppConfig::load("config.toml").await?;
    let watcher_config = WatcherConfig::default();

    let mut watcher = ConfigWatcher::new(
        "config.toml".into(),
        config,
        watcher_config
    );

    let (config_rx, event_rx) = watcher.start_watching().await?;

    // Handle configuration changes
    tokio::spawn(async move {
        let mut config_rx = config_rx;
        while config_rx.changed().await.is_ok() {
            let new_config = config_rx.borrow().clone();
            println!("Configuration reloaded: {}", new_config.mining.algorithm);
        }
    });

    // Handle watch events
    tokio::spawn(async move {
        let mut event_rx = event_rx;
        while let Ok(event) = event_rx.recv().await {
            println!("Watch event: {:?}", event);
        }
    });

    // Keep running
    tokio::time::sleep(std::time::Duration::from_secs(60)).await;

    Ok(())
}
```

### Security & Encryption

```rust
use opus_gpu_config::security::{SecretManager, EncryptionConfig};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create secret manager
    let config = EncryptionConfig::default();
    let mut secrets = SecretManager::new("my_password", config)?;

    // Store encrypted secrets
    secrets.store_secret(
        "database_password".to_string(),
        secrecy::Secret::new("super_secret_db_password".to_string())
    )?;

    // Retrieve secrets
    if let Some(password) = secrets.get_secret("database_password")? {
        println!("Retrieved password safely");
    }

    // Encrypt entire configuration
    let config = AppConfig::default();
    let key = b"my_32_byte_encryption_key_here!!";
    let encrypted = config.to_encrypted_bytes(key).await?;

    // Decrypt configuration
    let decrypted = AppConfig::from_encrypted_bytes(&encrypted, key).await?;

    Ok(())
}
```

### Custom Validation Rules

```rust
use opus_gpu_config::validation::{ConfigValidator, ValidationRule};

struct CustomRule;

impl ValidationRule for CustomRule {
    fn name(&self) -> &'static str {
        "custom_mining_check"
    }

    fn description(&self) -> &'static str {
        "Validates mining configuration settings"
    }

    fn validate(&self, config: &serde_json::Value) -> opus_gpu_config::ConfigResult<()> {
        if let Some(mining) = config.get("mining") {
            if let Some(algorithm) = mining.get("algorithm") {
                if algorithm.as_str() == Some("FORBIDDEN") {
                    return Err(opus_gpu_config::ConfigError::validation(
                        "Forbidden mining algorithm detected"
                    ));
                }
            }
        }
        Ok(())
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut validator = ConfigValidator::new(ValidationConfig::default());
    validator.add_custom_rule(Box::new(CustomRule));

    let config = AppConfig::default();
    let config_json = serde_json::to_value(&config)?;
    let result = validator.validate_config(&config_json).await?;

    if result.is_valid {
        println!("✅ Configuration validation passed!");
    } else {
        println!("❌ Validation failed with {} errors", result.errors.len());
    }

    Ok(())
}
```

## 🔧 Configuration Structure (Cấu trúc cấu hình)

```toml
[mining]
algorithm = "SHA256"
max_workers = 8
difficulty = 1000000
work_timeout_secs = 30
stats_interval_secs = 5
gpu_devices = [0, 1]
worker_threads = 2
batch_size = 1000
memory_size = 536870912  # 512MB

[pool]
urls = ["stratum+tcp://pool.example.com:4444"]
username = "your_wallet_address"
password = "worker1"
retry_attempts = 3
retry_delay_secs = 5
connection_timeout_secs = 10
keepalive_interval_secs = 30

[wallet]
address = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
keystore_dir = "./keystore"
backup_dir = "./backup"
encryption_enabled = true

[monitoring]
enabled = true
metrics_port = 9090
stats_interval_secs = 10
temperature_threshold = 80.0
memory_threshold = 90.0
enable_alerts = false

[api]
[api.rest]
host = "127.0.0.1"
port = 8080
cors_enabled = true
cors_origins = ["*"]
rate_limit = 100
request_timeout_secs = 30

[api.websocket]
host = "127.0.0.1"
port = 8081
max_connections = 1000
message_buffer_size = 1000
heartbeat_interval_secs = 30

[api.grpc]
host = "127.0.0.1"
port = 8082
max_message_size = 4194304  # 4MB
keepalive_interval_secs = 30
keepalive_timeout_secs = 5
```

## 🔐 Environment Variables (Biến môi trường)

Override configuration using environment variables với prefix `OPUS_GPU_`:

```bash
export OPUS_GPU_MINING__ALGORITHM="SHA3"
export OPUS_GPU_MINING__MAX_WORKERS="16"
export OPUS_GPU_API__REST__PORT="9090"
export OPUS_GPU_POOL__PASSWORD="secure_password"
```

## 📊 Validation Rules (Quy tắc xác thực)

### Built-in Rules (Quy tắc tích hợp)
- **Port conflict detection** (Phát hiện xung đột cổng)
- **Resource usage validation** (Xác thực sử dụng tài nguyên)
- **Security best practices** (Thực hành bảo mật tốt nhất)
- **Performance implications** (Tác động hiệu năng)
- **Common misconfigurations** (Cấu hình sai phổ biến)

### Custom Validation (Xác thực tùy chỉnh)
```rust
// Implement ValidationRule trait for custom logic
impl ValidationRule for MyCustomRule {
    fn validate(&self, config: &Value) -> ConfigResult<()> {
        // Custom validation logic here
        Ok(())
    }
}
```

## 📈 Performance (Hiệu năng)

- **Zero-copy configuration access** (Truy cập cấu hình không copy)
- **Efficient file watching** với inotify
- **Configuration caching** với TTL
- **Lazy validation** (Xác thực lười) cho non-critical paths
- **Async I/O** cho tất cả file operations

## 🔍 Debugging & Monitoring (Gỡ lỗi & Giám sát)

### Structured Logging
```rust
use tracing::{info, warn, error};

// Enable structured logging
tracing_subscriber::init();

// Logs automatically include context
info!("Configuration loaded successfully");
warn!("Using default value for missing setting");
error!("Configuration validation failed");
```

### Audit Events
- Configuration **loaded/saved/reloaded**
- **Validation failures** với detailed errors
- **Access denied** events
- **Secret operations** (encrypted/decrypted)
- **Backup/rollback** operations

### Metrics & Statistics
```rust
let stats = manager.get_statistics().await?;
println!("Cache hit rate: {}%", stats.cache_hit_rate);
println!("Average validation time: {}ms", stats.avg_validation_time);
```

## 🧪 Testing (Kiểm thử)

Run comprehensive tests:
```bash
cd core/config
cargo test
```

Run with logging:
```bash
RUST_LOG=debug cargo test
```

Run specific test module:
```bash
cargo test validation
cargo test security
cargo test watcher
```

## 📚 Examples (Ví dụ)

Xem thêm examples trong `examples/` directory:
- `basic_usage.rs` - Basic configuration operations
- `advanced_features.rs` - Full feature demonstration
- `security_demo.rs` - Security & encryption examples
- `validation_examples.rs` - Custom validation rules

Run examples:
```bash
cargo run --example basic_usage
```

## 🚨 Error Handling (Xử lý lỗi)

Comprehensive error types với context:

```rust
use opus_gpu_config::ConfigError;

match config_result {
    Ok(config) => println!("Success!"),
    Err(ConfigError::ValidationFailed { details }) => {
        eprintln!("Validation failed: {}", details);
    },
    Err(ConfigError::SecurityError { message }) => {
        eprintln!("Security error: {}", message);
    },
    Err(ConfigError::HotReload { message }) => {
        eprintln!("Hot reload failed: {}", message);
    },
    Err(e) => eprintln!("Other error: {}", e),
}
```

## 🔄 Migration (Di chuyển)

### From v1.x to v2.x
1. Update **Cargo.toml** dependencies
2. Replace `ConfigManager::new()` calls
3. Update **validation rules** to new API
4. Migrate **security settings**

### Configuration Format Migration
```rust
// Convert between formats
use opus_gpu_config::formats::FormatSerializer;

let toml_content = "...";
let json_content = FormatSerializer::convert::<AppConfig>(
    toml_content,
    ConfigFormat::Toml,
    ConfigFormat::Json
)?;
```

## 🛡️ Security Considerations (Cân nhắc bảo mật)

### Best Practices
1. **Enable encryption** for sensitive configurations
2. **Use strong passwords** for secret management
3. **Enable audit logging** trong production
4. **Restrict file permissions** (600 hoặc 640)
5. **Regular key rotation** cho encryption keys
6. **Monitor audit logs** for suspicious activity

### Security Features
- **AES-256-GCM encryption** với authenticated encryption
- **PBKDF2 key derivation** with configurable iterations
- **Secure random generation** using system entropy
- **Memory protection** với zeroization
- **Access control** với role-based permissions

## 📄 License (Giấy phép)

MIT License - xem [LICENSE](../../LICENSE) file for details.

## 🤝 Contributing (Đóng góp)

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support (Hỗ trợ)

- **Documentation**: [docs.rs/agent-gpu-config](https://docs.rs/agent-gpu-config)
- **Issues**: [GitHub Issues](https://github.com/agent-gpu/agent-gpu/issues)
- **Discussions**: [GitHub Discussions](https://github.com/agent-gpu/agent-gpu/discussions)

---

**Agent-GPU Configuration Management System** - Building the future of **secure** (bảo mật), **scalable** (có thể mở rộng), và **reliable** (đáng tin cậy) configuration management! 🚀