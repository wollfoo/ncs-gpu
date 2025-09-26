//! **Opus GPU Core Library** (thư viện lõi Opus GPU – module chính hệ thống)
//!
//! Core components for the GPU mining engine.

#![warn(missing_docs)]
#![warn(clippy::all)]
#![warn(clippy::pedantic)]
#![allow(clippy::module_name_repetitions)]

pub mod core;
pub mod plugins;
pub mod utils;

// Re-export important types
pub use crate::core::{
    engine::Engine,
    gpu_pool::{GpuPool, GpuDevice},
    plugin_api::{Plugin, PluginInfo, PluginContext},
    scheduler::{Scheduler, Task, TaskPriority},
};

pub use crate::utils::{
    config::Config,
    crypto::{encrypt, decrypt, hash},
    logging::setup_logging,
};

/// **Library version** (phiên bản thư viện – số hiệu module)
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// **Library name** (tên thư viện – định danh module)
pub const NAME: &str = env!("CARGO_PKG_NAME");