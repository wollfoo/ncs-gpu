/*!
 * Common Types and Utilities
 * 
 * Module chung cho các types, errors, và utilities được sử dụng across toàn bộ workspace.
 */

pub mod types;
pub mod error;
pub mod logging;

// Re-export commonly used items
pub use error::{AppError, Result};
pub use types::{GPUMetrics, ProcessInfo, PluginMetadata, HealthStatus};
pub use logging::init_logging;
