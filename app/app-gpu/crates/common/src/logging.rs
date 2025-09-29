/*!
 * Logging Setup
 * 
 * Cấu hình structured logging với tracing.
 */

use tracing_subscriber::{fmt, layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

/// Initialize logging with tracing
/// Khởi tạo logging với tracing
pub fn init_logging(log_level: &str, json_logs: bool) -> anyhow::Result<()> {
    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(log_level));

    let fmt_layer = if json_logs {
        // JSON format for production (machine-readable)
        fmt::layer()
            .json()
            .with_target(true)
            .with_thread_ids(true)
            .with_thread_names(true)
            .boxed()
    } else {
        // Human-readable format for development
        fmt::layer()
            .with_target(true)
            .with_thread_ids(true)
            .with_thread_names(true)
            .boxed()
    };

    tracing_subscriber::registry()
        .with(env_filter)
        .with(fmt_layer)
        .init();

    Ok(())
}
