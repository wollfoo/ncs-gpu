/*!
# App-GPU Library

**High-performance GPU mining** với **event-driven architecture**.

## Modules

- [`config`]: Configuration management
- [`core`]: Core event-driven engine
- [`gpu`]: GPU compute engine
- [`workers`]: Async worker pools  
- [`resource`]: Resource management
- [`stealth`]: Process anonymization
- [`monitoring`]: Performance monitoring
- [`utils`]: Shared utilities

## Example Usage

```rust
use app_gpu::{AppConfig, EventBus, GpuEngine};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let config = AppConfig::load("config.toml")?;
    let event_bus = EventBus::new("nats://localhost:4222").await?;
    let gpu_engine = GpuEngine::new(vec![0, 1]).await?;
    
    // Start event-driven processing
    event_bus.start().await?;
    gpu_engine.start().await?;
    
    Ok(())
}
```
*/

#![forbid(unsafe_code)]
#![warn(
    clippy::all,
    clippy::pedantic,
    clippy::nursery,
    clippy::cargo,
    missing_docs,
    rust_2018_idioms
)]
#![allow(
    clippy::module_name_repetitions,
    clippy::missing_errors_doc,
    clippy::missing_panics_doc
)]

pub mod config;
pub mod core;
pub mod gpu;
pub mod monitoring;
pub mod resource;
pub mod stealth;
pub mod utils;
pub mod workers;

// Re-export public API
pub use crate::config::AppConfig;
pub use crate::core::{EventBus, EventType, GpuEvent, ResourceEvent, StealtHEvent};
pub use crate::gpu::{GpuEngine, GpuWorker};
pub use crate::monitoring::MetricsCollector;
pub use crate::resource::ResourceManager;
pub use crate::stealth::StealtHCoordinator;
pub use crate::workers::WorkerPool;

/// **Application Result Type** (kiểu kết quả ứng dụng)
pub type Result<T> = anyhow::Result<T>;

/// **Application Error Type** (kiểu lỗi ứng dụng)
pub use anyhow::Error;

/// **Version Information** (thông tin phiên bản)
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// **Build Information** (thông tin build)
pub const BUILD_DATE: &str = env!("VERGEN_BUILD_DATE");

/// **Git Information** (thông tin git)
pub const GIT_SHA: &str = env!("VERGEN_GIT_SHA");

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_version_info() {
        assert!(!VERSION.is_empty());
        println!("App-GPU version: {}", VERSION);
    }
}
