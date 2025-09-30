//! Core modules for OPUS-GPU miner
//!
//! This module contains the main functional components:
//! - `api`: HTTP API server for monitoring and control
//! - `gpu`: GPU executor for mining operations
//! - `stealth`: Stealth and obfuscation capabilities
//! - `metrics`: Prometheus metrics collection

pub mod api;
pub mod gpu;
pub mod metrics;
pub mod stealth;

// Re-exports are available but not used in main.rs currently
// pub use api::start_api_server;
// pub use gpu::start_gpu_executor;
// pub use metrics::start_metrics_collector;
// pub use stealth::start_stealth_module;
