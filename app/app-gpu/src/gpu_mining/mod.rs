//! GPU Mining Engine for OPUS-GPU
//!
//! High-performance GPU mining implementation with CUDA support,
//! thermal monitoring, and adaptive performance optimization.

pub mod cuda_wrapper;
pub mod engine;
pub mod thermal;

pub use cuda_wrapper::*;
pub use engine::*;
pub use thermal::*;

/// Mining algorithm trait for extensible algorithm support
pub trait MiningAlgorithm: Send + Sync {
    /// Algorithm name identifier
    fn name(&self) -> &str;

    /// Initialize algorithm on GPU device
    fn initialize(&mut self, device_id: u32) -> crate::common::OpusResult<()>;

    /// Execute mining iteration
    fn mine_iteration(
        &mut self,
        work_data: &[u8],
        target: &[u8],
        nonce_start: u64,
        nonce_count: u32,
    ) -> crate::common::OpusResult<MiningResult>;

    /// Get current hash rate estimate
    fn hash_rate(&self) -> f64;

    /// Clean up algorithm resources
    fn cleanup(&mut self) -> crate::common::OpusResult<()>;
}

/// Mining operation result
#[derive(Debug, Clone)]
pub struct MiningResult {
    /// Found nonces that meet target difficulty
    pub nonces: Vec<u64>,
    /// Number of hashes computed
    pub hashes_computed: u64,
    /// Execution time in microseconds
    pub execution_time_us: u64,
    /// Device temperature during mining
    pub device_temperature: f32,
}

/// Mining work specification
#[derive(Debug, Clone)]
pub struct WorkData {
    /// Block header data
    pub header: Vec<u8>,
    /// Target difficulty
    pub target: Vec<u8>,
    /// Starting nonce value
    pub nonce_start: u64,
    /// Number of nonces to test
    pub nonce_range: u32,
    /// Work identifier
    pub work_id: String,
    /// Timestamp when work was received
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

/// Mining device information
#[derive(Debug, Clone)]
pub struct MiningDevice {
    /// CUDA device ID
    pub device_id: u32,
    /// Device name
    pub name: String,
    /// Total memory in bytes
    pub total_memory: u64,
    /// Free memory in bytes
    pub free_memory: u64,
    /// Compute capability (major, minor)
    pub compute_capability: (i32, i32),
    /// Number of SMs
    pub multiprocessor_count: i32,
    /// Maximum threads per block
    pub max_threads_per_block: i32,
    /// Current temperature
    pub temperature: f32,
    /// Power usage in watts
    pub power_usage: f32,
}

/// Mining statistics
#[derive(Debug, Clone, Default)]
pub struct MiningStats {
    /// Total hashes computed
    pub total_hashes: u64,
    /// Accepted shares
    pub accepted_shares: u64,
    /// Rejected shares
    pub rejected_shares: u64,
    /// Average hash rate (hashes/second)
    pub average_hash_rate: f64,
    /// Current hash rate (hashes/second)
    pub current_hash_rate: f64,
    /// Mining errors
    pub errors: u64,
    /// Uptime in seconds
    pub uptime_seconds: u64,
    /// Last share timestamp
    pub last_share_time: Option<chrono::DateTime<chrono::Utc>>,
}

/// Mining configuration per device
#[derive(Debug, Clone)]
pub struct DeviceMiningConfig {
    /// Device ID
    pub device_id: u32,
    /// Mining intensity (1-10)
    pub intensity: u8,
    /// Number of concurrent streams
    pub streams: u32,
    /// Work size (threads per block)
    pub work_size: u32,
    /// Memory usage limit in MB
    pub memory_limit_mb: Option<usize>,
    /// Enable thermal throttling
    pub thermal_throttling: bool,
    /// Target temperature for throttling
    pub target_temperature: f32,
}

impl Default for DeviceMiningConfig {
    fn default() -> Self {
        Self {
            device_id: 0,
            intensity: 7,
            streams: 2,
            work_size: 256,
            memory_limit_mb: None,
            thermal_throttling: true,
            target_temperature: 80.0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mining_result() {
        let result = MiningResult {
            nonces: vec![123456789],
            hashes_computed: 1000000,
            execution_time_us: 1000,
            device_temperature: 65.0,
        };

        assert_eq!(result.nonces.len(), 1);
        assert_eq!(result.hashes_computed, 1000000);
        assert!(result.device_temperature > 0.0);
    }

    #[test]
    fn test_work_data() {
        let work = WorkData {
            header: vec![0u8; 76],
            target: vec![0u8; 32],
            nonce_start: 0,
            nonce_range: 1000000,
            work_id: "test_work_001".to_string(),
            timestamp: chrono::Utc::now(),
        };

        assert_eq!(work.header.len(), 76);
        assert_eq!(work.target.len(), 32);
        assert!(!work.work_id.is_empty());
    }

    #[test]
    fn test_device_mining_config() {
        let config = DeviceMiningConfig::default();
        assert_eq!(config.intensity, 7);
        assert_eq!(config.streams, 2);
        assert!(config.thermal_throttling);
    }
}