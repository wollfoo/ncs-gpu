use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Profile configuration cho stealth profile (cấu hình cho hồ sơ ngụy trang)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProfileConfig {
    /// Profile enabled/disabled
    pub enabled: bool,
    /// Log emission frequency (tần suất phát log)
    #[serde(with = "humantime_serde")]
    pub log_frequency: Duration,
    /// Target GPU utilization (mức sử dụng GPU mục tiêu)
    pub gpu_target: f32,
    /// Total training epochs (for AI training)
    pub total_epochs: u32,
}

/// Resource camouflage configuration (cấu hình ngụy trang tài nguyên)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CamouflageConfig {
    /// GPU smoother enabled
    pub gpu_smoother_enabled: bool,
    /// EMA alpha factor (hệ số alpha EMA)
    pub gpu_smoother_alpha: f32,
    /// GPU smoother jitter range (phạm vi dao động)
    pub gpu_smoother_jitter: f32,
    /// Target GPU utilization (mức sử dụng GPU mục tiêu)
    pub gpu_target: f32,

    /// Memory faker enabled
    pub memory_faker_enabled: bool,
    /// Memory allocation strategy
    pub memory_strategy: AllocationStrategy,

    /// Network mixer enabled
    pub network_mixer_enabled: bool,
    /// Request interval for dummy traffic (khoảng thời gian yêu cầu cho lưu lượng giả)
    #[serde(with = "humantime_serde")]
    pub network_request_interval: Duration,
}

/// Memory allocation strategies for memory faker (chiến lược cấp phát bộ nhớ cho memory faker)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AllocationStrategy {
    /// Constant allocation size (kích thước cấp phát không đổi)
    Constant {
        /// Size in bytes (kích thước theo byte)
        size_bytes: usize,
    },
    /// Random allocation within range (cấp phát ngẫu nhiên trong phạm vi)
    Random {
        /// Minimum size (kích thước tối thiểu)
        min_bytes: usize,
        /// Maximum size (kích thước tối đa)
        max_bytes: usize,
    },
    /// Bursty allocation pattern (mô hình cấp phát theo đợt)
    Bursty {
        /// Interval between bursts (khoảng thời gian giữa các đợt)
        burst_interval: Duration,
        /// Number of allocations per burst (số lượng cấp phát mỗi đợt)
        allocations_per_burst: u32,
        /// Size range for allocations (phạm vi kích thước cho cấp phát)
        size_range: std::ops::Range<usize>,
    },
}

/// Main stealth configuration (cấu hình ngụy trang chính)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StealthConfig {
    /// AI training simulation
    pub ai_training: ProfileConfig,
    /// AI inference simulation
    pub ai_inference: ProfileConfig,
    /// Image processing simulation
    pub image_processing: ProfileConfig,
    /// Scientific computing simulation
    pub scientific: ProfileConfig,
    /// Resource camouflage
    pub camouflage: CamouflageConfig,
}

impl Default for StealthConfig {
    fn default() -> Self {
        Self {
            ai_training: ProfileConfig {
                enabled: true,
                log_frequency: Duration::from_secs(30),
                gpu_target: 0.8,
                total_epochs: 100,
            },
            ai_inference: ProfileConfig {
                enabled: false,
                log_frequency: Duration::from_secs(5),
                gpu_target: 0.6,
                total_epochs: 0, // Not applicable
            },
            image_processing: ProfileConfig {
                enabled: false,
                log_frequency: Duration::from_secs(10),
                gpu_target: 0.7,
                total_epochs: 0, // Not applicable
            },
            scientific: ProfileConfig {
                enabled: false,
                log_frequency: Duration::from_secs(60),
                gpu_target: 0.75,
                total_epochs: 0, // Not applicable
            },
            camouflage: CamouflageConfig {
                gpu_smoother_enabled: true,
                gpu_smoother_alpha: 0.2,
                gpu_smoother_jitter: 0.05,
                gpu_target: 0.75,
                memory_faker_enabled: true,
                memory_strategy: AllocationStrategy::Bursty {
                    burst_interval: Duration::from_secs(15),
                    allocations_per_burst: 3,
                    size_range: 1024 * 1024..10 * 1024 * 1024, // 1MB-10MB
                },
                network_mixer_enabled: true,
                network_request_interval: Duration::from_secs(60),
            },
        }
    }
}

/// Load configuration từ TOML file hoặc environment variables
pub fn load_config() -> anyhow::Result<StealthConfig> {
    // Priority: environment variables > config file > defaults
    // For now, just return defaults - can be extended with file/env loading
    Ok(StealthConfig::default())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_stealth_config() {
        let config = StealthConfig::default();

        // Test default values
        assert!(config.ai_training.enabled);
        assert_eq!(config.ai_training.gpu_target, 0.8);
        assert_eq!(config.ai_training.total_epochs, 100);

        assert!(!config.ai_inference.enabled);
        assert_eq!(config.ai_inference.gpu_target, 0.6);

        assert!(config.camouflage.gpu_smoother_enabled);
        assert_eq!(config.camouflage.gpu_target, 0.75);
        assert!(config.camouflage.memory_faker_enabled);

        if let AllocationStrategy::Bursty { burst_interval, allocations_per_burst, size_range } = &config.camouflage.memory_strategy {
            assert_eq!(*burst_interval, Duration::from_secs(15));
            assert_eq!(*allocations_per_burst, 3);
            assert_eq!(size_range.start, 1024 * 1024);
            assert_eq!(size_range.end, 10 * 1024 * 1024);
        } else {
            panic!("Expected Bursty allocation strategy");
        }
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
    }
}