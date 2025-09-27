//! OPUS-GPU Core Library
//! 
//! High-performance GPU computing framework

pub mod runtime;
pub mod plugin;
pub mod ipc;
pub mod config;
pub mod error;
pub mod logging;

// Re-export commonly used types
pub use config::Config;
pub use error::{OpusError, OpusResult};
pub use plugin::{Plugin, PluginManager, PluginTask, PluginOutput};
pub use runtime::Runtime;
pub use ipc::{IpcManager, Message};

/// Version information
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
pub const NAME: &str = env!("CARGO_PKG_NAME");

/// Initialize the framework
pub async fn init() -> OpusResult<Runtime> {
    // Initialize logging
    let log_config = logging::LogConfig::default();
    logging::init_logging(&log_config)?;
    
    // Load configuration
    let config = Config::load()?;
    
    // Create runtime
    let runtime = Runtime::new(config).await?;
    
    Ok(runtime)
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_version() {
        assert!(!VERSION.is_empty());
        assert_eq!(NAME, "opus-gpu-core");
    }
}
