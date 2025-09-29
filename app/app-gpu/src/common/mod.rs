//! Common utilities and shared types for OPUS-GPU
//!
//! This module provides foundational types, configuration management,
//! error handling, and metrics collection for the OPUS-GPU system.

pub mod config;
pub mod error;
pub mod metrics;
pub mod types;

pub use config::*;
pub use error::*;
pub use metrics::*;
pub use types::*;

/// Version information for OPUS-GPU
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
pub const NAME: &str = env!("CARGO_PKG_NAME");

/// System constants
pub mod constants {
    /// Default GPU memory allocation chunk size (MB)
    pub const DEFAULT_GPU_CHUNK_SIZE: usize = 256;

    /// Maximum number of concurrent mining threads
    pub const MAX_MINING_THREADS: usize = 64;

    /// Default network timeout (seconds)
    pub const DEFAULT_NETWORK_TIMEOUT: u64 = 30;

    /// Metrics collection interval (seconds)
    pub const METRICS_INTERVAL: u64 = 5;

    /// Thermal monitoring threshold (Celsius)
    pub const THERMAL_WARNING_THRESHOLD: f32 = 75.0;
    pub const THERMAL_CRITICAL_THRESHOLD: f32 = 85.0;

    /// Memory usage thresholds (percentage)
    pub const MEMORY_WARNING_THRESHOLD: f32 = 80.0;
    pub const MEMORY_CRITICAL_THRESHOLD: f32 = 95.0;
}