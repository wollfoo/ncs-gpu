/*!
# Shared Utilities

**Common utilities** và **helper functions** được sử dụng across all modules.

## Modules

- [`error`]: Error types và error handling
- [`logging`]: Structured logging setup
- [`crypto`]: Cryptographic utilities

## Features

- **Structured error handling** với **anyhow** integration
- **High-performance logging** với **tracing**
- **Memory-safe cryptographic** operations
*/

pub mod error;
pub mod logging;
pub mod crypto;

// Re-export common utilities
pub use crate::utils::error::{AppError, Result};
pub use crate::utils::logging::init_logging;
