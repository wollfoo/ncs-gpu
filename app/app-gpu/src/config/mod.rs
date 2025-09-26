/*!
# Configuration Management

**Centralized configuration** cho App-GPU với **type-safe** loading
từ multiple sources: files, environment variables, command line.

## Features

- **TOML/JSON/YAML** file support
- **Environment variable** override
- **Validation** với **serde** và **config crate**
- **Hot reload** capability (optional)
- **Secure defaults** cho production

## Example

```rust
use app_gpu::config::AppConfig;

let config = AppConfig::load("config.toml")?;
println!("NATS URL: {}", config.nats.url);
println!("GPU count: {}", config.gpu.device_count);
```
*/

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::time::Duration;

/// **Main Application Configuration** (cấu hình ứng dụng chính)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    /// **NATS configuration** (cấu hình NATS)
    pub nats: NatsConfig,
    
    /// **GPU configuration** (cấu hình GPU)
    pub gpu: GpuConfig,
    
    /// **Resource management configuration** (cấu hình quản lý tài nguyên)
    pub resource: ResourceConfig,
    
    /// **Security configuration** (cấu hình bảo mật)
    pub security: SecurityConfig,
    
    /// **Monitoring configuration** (cấu hình giám sát)
    pub monitoring: MonitoringConfig,
    
    /// **Worker configuration** (cấu hình worker)
    pub workers: WorkerConfig,
}

/// **NATS Event Bus Configuration** (cấu hình NATS Event Bus)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NatsConfig {
    /// **NATS server URL** (URL máy chủ NATS)
    #[serde(default = "default_nats_url")]
    pub url: String,
    
    /// **Connection timeout** (timeout kết nối)
    #[serde(default = "default_nats_timeout")]
    pub connect_timeout: Duration,
    
    /// **JetStream enabled** (bật JetStream)
    #[serde(default = "default_true")]
    pub jetstream: bool,
    
    /// **Max reconnect attempts** (số lần kết nối lại tối đa)
    #[serde(default = "default_nats_reconnect")]
    pub max_reconnects: usize,
    
    /// **Event retention** (thời gian giữ event)
    #[serde(default = "default_event_retention")]
    pub event_retention: Duration,
    
    /// **Subjects** (các chủ đề)
    #[serde(default)]
    pub subjects: NatsSubjects,
}

/// **NATS Subjects Configuration** (cấu hình chủ đề NATS)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NatsSubjects {
    /// **GPU events subject** (chủ đề sự kiện GPU)
    #[serde(default = "default_gpu_subject")]
    pub gpu: String,
    
    /// **Resource events subject** (chủ đề sự kiện tài nguyên)
    #[serde(default = "default_resource_subject")]
    pub resource: String,
    
    /// **Stealth events subject** (chủ đề sự kiện ẩn danh)
    #[serde(default = "default_stealth_subject")]
    pub stealth: String,
    
    /// **Monitoring events subject** (chủ đề sự kiện giám sát)
    #[serde(default = "default_monitoring_subject")]
    pub monitoring: String,
}

/// **GPU Configuration** (cấu hình GPU)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuConfig {
    /// **Device indices to use** (chỉ số thiết bị sử dụng)
    pub device_indices: Vec<usize>,
    
    /// **Auto-detect devices** (tự động phát hiện thiết bị)
    #[serde(default = "default_true")]
    pub auto_detect: bool,
    
    /// **Memory pool size per GPU (MB)** (kích thước pool bộ nhớ mỗi GPU)
    #[serde(default = "default_gpu_memory_pool")]
    pub memory_pool_mb: usize,
    
    /// **Temperature threshold (°C)** (ngưỡng nhiệt độ)
    #[serde(default = "default_temperature_threshold")]
    pub temperature_threshold: u32,
    
    /// **Power limit (watts)** (giới hạn công suất)
    pub power_limit_watts: Option<u32>,
    
    /// **Compute mode** (chế độ tính toán)
    #[serde(default)]
    pub compute_mode: GpuComputeMode,
    
    /// **Optimization settings** (cài đặt tối ưu)
    #[serde(default)]
    pub optimization: GpuOptimization,
}

/// **GPU Compute Mode** (chế độ tính toán GPU)
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum GpuComputeMode {
    /// **Default compute mode** (chế độ tính toán mặc định)
    #[default]
    Default,
    /// **Exclusive process** (tiến trình độc quyền)
    ExclusiveProcess,
    /// **Exclusive thread** (luồng độc quyền)  
    ExclusiveThread,
    /// **Prohibited** (bị cấm)
    Prohibited,
}

/// **GPU Optimization Settings** (cài đặt tối ưu GPU)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuOptimization {
    /// **Enable GPU boost** (bật tăng tốc GPU)
    #[serde(default = "default_true")]
    pub enable_boost: bool,
    
    /// **Memory coalescing** (gộp bộ nhớ)
    #[serde(default = "default_true")]
    pub memory_coalescing: bool,
    
    /// **Async kernel execution** (thực thi kernel bất đồng bộ)
    #[serde(default = "default_true")]
    pub async_kernels: bool,
    
    /// **Stream priority** (ưu tiên stream)
    #[serde(default)]
    pub stream_priority: i32,
}

/// **Resource Management Configuration** (cấu hình quản lý tài nguyên)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceConfig {
    /// **CPU core limit** (giới hạn lõi CPU)
    pub cpu_cores: Option<usize>,
    
    /// **Memory limit (MB)** (giới hạn bộ nhớ)
    pub memory_limit_mb: Option<usize>,
    
    /// **QoS enforcement** (thực thi QoS)
    #[serde(default = "default_true")]
    pub qos_enabled: bool,
    
    /// **Resource monitoring interval** (khoảng giám sát tài nguyên)
    #[serde(default = "default_monitoring_interval")]
    pub monitoring_interval: Duration,
    
    /// **Auto-scaling** (tự động mở rộng)
    #[serde(default)]
    pub auto_scaling: AutoScalingConfig,
}

/// **Auto-scaling Configuration** (cấu hình tự động mở rộng)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AutoScalingConfig {
    /// **Enable auto-scaling** (bật tự động mở rộng)
    #[serde(default)]
    pub enabled: bool,
    
    /// **Scale up threshold** (ngưỡng mở rộng)
    #[serde(default = "default_scale_up_threshold")]
    pub scale_up_threshold: f32,
    
    /// **Scale down threshold** (ngưỡng thu hẹp)
    #[serde(default = "default_scale_down_threshold")]
    pub scale_down_threshold: f32,
    
    /// **Scale up cooldown** (thời gian chờ mở rộng)
    #[serde(default = "default_scale_cooldown")]
    pub scale_up_cooldown: Duration,
    
    /// **Scale down cooldown** (thời gian chờ thu hẹp)
    #[serde(default = "default_scale_cooldown")]
    pub scale_down_cooldown: Duration,
}

/// **Security Configuration** (cấu hình bảo mật)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityConfig {
    /// **Enable TLS** (bật TLS)
    #[serde(default = "default_true")]
    pub tls_enabled: bool,
    
    /// **CA certificate path** (đường dẫn chứng chỉ CA)
    pub ca_cert_path: Option<String>,
    
    /// **Client certificate path** (đường dẫn chứng chỉ client)
    pub client_cert_path: Option<String>,
    
    /// **Client key path** (đường dẫn key client)
    pub client_key_path: Option<String>,
    
    /// **Process isolation** (cô lập tiến trình)
    #[serde(default)]
    pub process_isolation: ProcessIsolation,
    
    /// **Memory encryption** (mã hóa bộ nhớ)
    #[serde(default)]
    pub memory_encryption: bool,
}

/// **Process Isolation Configuration** (cấu hình cô lập tiến trình)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessIsolation {
    /// **Enable isolation** (bật cô lập)
    #[serde(default)]
    pub enabled: bool,
    
    /// **Use namespaces** (sử dụng namespace)
    #[serde(default = "default_true")]
    pub namespaces: bool,
    
    /// **Use seccomp** (sử dụng seccomp)
    #[serde(default)]
    pub seccomp: bool,
    
    /// **Use capabilities** (sử dụng capability)
    #[serde(default)]
    pub capabilities: bool,
}

/// **Monitoring Configuration** (cấu hình giám sát)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MonitoringConfig {
    /// **Metrics port** (cổng metrics)
    #[serde(default = "default_metrics_port")]
    pub metrics_port: u16,
    
    /// **Enable Prometheus** (bật Prometheus)
    #[serde(default = "default_true")]
    pub prometheus_enabled: bool,
    
    /// **Health check interval** (khoảng kiểm tra sức khỏe)
    #[serde(default = "default_health_check_interval")]
    pub health_check_interval: Duration,
    
    /// **Tracing enabled** (bật tracing)
    #[serde(default = "default_true")]
    pub tracing_enabled: bool,
    
    /// **Log level** (mức độ log)
    #[serde(default = "default_log_level")]
    pub log_level: String,
}

/// **Worker Configuration** (cấu hình worker)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerConfig {
    /// **GPU worker count** (số lượng GPU worker)
    #[serde(default = "default_gpu_worker_count")]
    pub gpu_workers: usize,
    
    /// **Resource worker count** (số lượng resource worker)
    #[serde(default = "default_resource_worker_count")]
    pub resource_workers: usize,
    
    /// **Stealth worker count** (số lượng stealth worker)
    #[serde(default = "default_stealth_worker_count")]
    pub stealth_workers: usize,
    
    /// **Worker queue size** (kích thước queue worker)
    #[serde(default = "default_worker_queue_size")]
    pub queue_size: usize,
    
    /// **Worker timeout** (timeout worker)
    #[serde(default = "default_worker_timeout")]
    pub timeout: Duration,
}

// Default value functions
fn default_nats_url() -> String { "nats://localhost:4222".to_string() }
fn default_nats_timeout() -> Duration { Duration::from_secs(5) }
fn default_nats_reconnect() -> usize { 10 }
fn default_event_retention() -> Duration { Duration::from_secs(3600) }
fn default_true() -> bool { true }
fn default_gpu_subject() -> String { "gpu.>".to_string() }
fn default_resource_subject() -> String { "resource.>".to_string() }
fn default_stealth_subject() -> String { "stealth.>".to_string() }
fn default_monitoring_subject() -> String { "monitoring.>".to_string() }
fn default_gpu_memory_pool() -> usize { 1024 }
fn default_temperature_threshold() -> u32 { 80 }
fn default_monitoring_interval() -> Duration { Duration::from_secs(30) }
fn default_scale_up_threshold() -> f32 { 0.8 }
fn default_scale_down_threshold() -> f32 { 0.3 }
fn default_scale_cooldown() -> Duration { Duration::from_secs(60) }
fn default_metrics_port() -> u16 { 9090 }
fn default_health_check_interval() -> Duration { Duration::from_secs(30) }
fn default_log_level() -> String { "info".to_string() }
fn default_gpu_worker_count() -> usize { num_cpus::get() }
fn default_resource_worker_count() -> usize { 2 }
fn default_stealth_worker_count() -> usize { 1 }
fn default_worker_queue_size() -> usize { 1000 }
fn default_worker_timeout() -> Duration { Duration::from_secs(30) }

impl Default for NatsSubjects {
    fn default() -> Self {
        Self {
            gpu: default_gpu_subject(),
            resource: default_resource_subject(),
            stealth: default_stealth_subject(),
            monitoring: default_monitoring_subject(),
        }
    }
}

impl Default for GpuOptimization {
    fn default() -> Self {
        Self {
            enable_boost: true,
            memory_coalescing: true,
            async_kernels: true,
            stream_priority: 0,
        }
    }
}

impl Default for AutoScalingConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            scale_up_threshold: default_scale_up_threshold(),
            scale_down_threshold: default_scale_down_threshold(),
            scale_up_cooldown: default_scale_cooldown(),
            scale_down_cooldown: default_scale_cooldown(),
        }
    }
}

impl Default for ProcessIsolation {
    fn default() -> Self {
        Self {
            enabled: false,
            namespaces: true,
            seccomp: false,
            capabilities: false,
        }
    }
}

impl AppConfig {
    /// **Load configuration from file** (tải cấu hình từ file)
    pub fn load<P: AsRef<Path>>(path: P) -> Result<Self> {
        let path = path.as_ref();
        
        let mut builder = config::Config::builder();
        
        // Load from file if it exists
        if path.exists() {
            builder = builder
                .add_source(config::File::from(path))
                .add_source(config::Environment::with_prefix("APP_GPU"));
        } else {
            // Use defaults and environment only
            builder = builder
                .add_source(config::Environment::with_prefix("APP_GPU"));
        }
        
        let config = builder
            .build()
            .with_context(|| format!("Failed to build configuration from {}", path.display()))?;
            
        config
            .try_deserialize()
            .context("Failed to deserialize configuration")
    }
    
    /// **Load with defaults** (tải với giá trị mặc định)
    pub fn default() -> Self {
        Self {
            nats: NatsConfig {
                url: default_nats_url(),
                connect_timeout: default_nats_timeout(),
                jetstream: true,
                max_reconnects: default_nats_reconnect(),
                event_retention: default_event_retention(),
                subjects: NatsSubjects::default(),
            },
            gpu: GpuConfig {
                device_indices: vec![],
                auto_detect: true,
                memory_pool_mb: default_gpu_memory_pool(),
                temperature_threshold: default_temperature_threshold(),
                power_limit_watts: None,
                compute_mode: GpuComputeMode::Default,
                optimization: GpuOptimization::default(),
            },
            resource: ResourceConfig {
                cpu_cores: None,
                memory_limit_mb: None,
                qos_enabled: true,
                monitoring_interval: default_monitoring_interval(),
                auto_scaling: AutoScalingConfig::default(),
            },
            security: SecurityConfig {
                tls_enabled: true,
                ca_cert_path: None,
                client_cert_path: None,
                client_key_path: None,
                process_isolation: ProcessIsolation::default(),
                memory_encryption: false,
            },
            monitoring: MonitoringConfig {
                metrics_port: default_metrics_port(),
                prometheus_enabled: true,
                health_check_interval: default_health_check_interval(),
                tracing_enabled: true,
                log_level: default_log_level(),
            },
            workers: WorkerConfig {
                gpu_workers: default_gpu_worker_count(),
                resource_workers: default_resource_worker_count(),
                stealth_workers: default_stealth_worker_count(),
                queue_size: default_worker_queue_size(),
                timeout: default_worker_timeout(),
            },
        }
    }
    
    /// **Validate configuration** (xác thực cấu hình)
    pub fn validate(&self) -> Result<()> {
        // Validate NATS URL
        if self.nats.url.is_empty() {
            anyhow::bail!("NATS URL cannot be empty");
        }
        
        // Validate GPU configuration
        if self.gpu.device_indices.is_empty() && !self.gpu.auto_detect {
            anyhow::bail!("GPU device indices cannot be empty when auto-detect is disabled");
        }
        
        // Validate temperature threshold
        if self.gpu.temperature_threshold < 50 || self.gpu.temperature_threshold > 100 {
            anyhow::bail!("GPU temperature threshold must be between 50-100°C");
        }
        
        // Validate worker counts
        if self.workers.gpu_workers == 0 {
            anyhow::bail!("GPU worker count must be greater than 0");
        }
        
        // Validate queue size
        if self.workers.queue_size == 0 {
            anyhow::bail!("Worker queue size must be greater than 0");
        }
        
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::NamedTempFile;
    use std::io::Write;

    #[test]
    fn test_default_config() {
        let config = AppConfig::default();
        assert_eq!(config.nats.url, "nats://localhost:4222");
        assert!(config.gpu.auto_detect);
        assert!(config.security.tls_enabled);
        assert!(config.monitoring.prometheus_enabled);
    }

    #[test]
    fn test_config_validation() {
        let mut config = AppConfig::default();
        assert!(config.validate().is_ok());
        
        // Test invalid temperature
        config.gpu.temperature_threshold = 200;
        assert!(config.validate().is_err());
        
        // Test invalid worker count
        config.gpu.temperature_threshold = 80;
        config.workers.gpu_workers = 0;
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_config_loading() -> Result<()> {
        let toml_content = r#"
            [nats]
            url = "nats://test:4222"
            jetstream = true
            
            [gpu]
            device_indices = [0, 1]
            auto_detect = false
            memory_pool_mb = 2048
            temperature_threshold = 75
            
            [monitoring]
            metrics_port = 9091
            log_level = "debug"
        "#;
        
        let mut temp_file = NamedTempFile::new()?;
        temp_file.write_all(toml_content.as_bytes())?;
        
        let config = AppConfig::load(temp_file.path())?;
        
        assert_eq!(config.nats.url, "nats://test:4222");
        assert_eq!(config.gpu.device_indices, vec![0, 1]);
        assert!(!config.gpu.auto_detect);
        assert_eq!(config.gpu.memory_pool_mb, 2048);
        assert_eq!(config.gpu.temperature_threshold, 75);
        assert_eq!(config.monitoring.metrics_port, 9091);
        assert_eq!(config.monitoring.log_level, "debug");
        
        Ok(())
    }
}
