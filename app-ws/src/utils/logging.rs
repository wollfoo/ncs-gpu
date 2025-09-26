//! **Logging Configuration** (cấu hình ghi nhật ký – thiết lập log)

use anyhow::Result;
use tracing::{Level, Subscriber};
use tracing_subscriber::{
    fmt::{self, format::FmtSpan},
    layer::SubscriberExt,
    registry::LookupSpan,
    util::SubscriberInitExt,
    EnvFilter, Layer,
};

/// **Setup logging** (thiết lập ghi nhật ký – cấu hình log)
pub fn setup_logging(log_level: &str) -> Result<()> {
    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| {
            EnvFilter::new(format!(
                "opus_gpu={},opus_gpu_core={},opus_gpu_engine={}",
                log_level, log_level, log_level
            ))
        });

    let fmt_layer = fmt::layer()
        .with_target(true)
        .with_thread_ids(true)
        .with_thread_names(true)
        .with_span_events(FmtSpan::CLOSE)
        .with_ansi(true)
        .with_level(true)
        .with_timer(fmt::time::ChronoLocal::rfc_3339());

    // Optional JSON formatting for production
    #[cfg(feature = "json-logs")]
    let fmt_layer = fmt_layer.json();

    tracing_subscriber::registry()
        .with(env_filter)
        .with(fmt_layer)
        .init();

    Ok(())
}

/// **Create file logger** (tạo logger file – ghi log vào tệp)
pub fn create_file_logger<S>(
    path: &std::path::Path,
    level: Level,
) -> Result<Box<dyn Layer<S> + Send + Sync + 'static>>
where
    S: Subscriber + for<'a> LookupSpan<'a>,
{
    use std::fs::OpenOptions;
    use std::io::BufWriter;

    let file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?;

    let writer = BufWriter::new(file);

    let layer = fmt::layer()
        .with_writer(std::sync::Mutex::new(writer))
        .with_ansi(false)
        .with_target(true)
        .with_thread_ids(true)
        .with_level(true)
        .with_timer(fmt::time::ChronoLocal::rfc_3339())
        .with_filter(EnvFilter::new(format!("opus_gpu={}", level)));

    Ok(Box::new(layer))
}

/// **Structured logging macros** (macro ghi log có cấu trúc – công cụ log định dạng)
#[macro_export]
macro_rules! log_event {
    ($level:expr, $event:expr, $($field:tt)*) => {
        tracing::event!($level, event = $event, $($field)*);
    };
}

#[macro_export]
macro_rules! log_error {
    ($event:expr, $($field:tt)*) => {
        $crate::log_event!(tracing::Level::ERROR, $event, $($field)*);
    };
}

#[macro_export]
macro_rules! log_warn {
    ($event:expr, $($field:tt)*) => {
        $crate::log_event!(tracing::Level::WARN, $event, $($field)*);
    };
}

#[macro_export]
macro_rules! log_info {
    ($event:expr, $($field:tt)*) => {
        $crate::log_event!(tracing::Level::INFO, $event, $($field)*);
    };
}

#[macro_export]
macro_rules! log_debug {
    ($event:expr, $($field:tt)*) => {
        $crate::log_event!(tracing::Level::DEBUG, $event, $($field)*);
    };
}

#[macro_export]
macro_rules! log_trace {
    ($event:expr, $($field:tt)*) => {
        $crate::log_event!(tracing::Level::TRACE, $event, $($field)*);
    };
}

/// **Performance logging** (ghi log hiệu năng – đo lường thời gian)
#[macro_export]
macro_rules! measure_time {
    ($name:expr, $body:block) => {{
        let _timer = $crate::utils::logging::Timer::new($name);
        $body
    }};
}

/// **Timer for performance measurement** (bộ đếm thời gian cho đo lường hiệu năng)
pub struct Timer {
    name: String,
    start: std::time::Instant,
}

impl Timer {
    pub fn new(name: impl Into<String>) -> Self {
        let name = name.into();
        tracing::debug!(timer = %name, "Timer started");
        Self {
            name,
            start: std::time::Instant::now(),
        }
    }
}

impl Drop for Timer {
    fn drop(&mut self) {
        let duration = self.start.elapsed();
        tracing::info!(
            timer = %self.name,
            duration_ms = %duration.as_millis(),
            "Timer completed"
        );
    }
}

/// **Log context for async operations** (ngữ cảnh log cho thao tác bất đồng bộ)
pub async fn with_logging_context<F, T>(
    operation: &str,
    f: F,
) -> Result<T>
where
    F: std::future::Future<Output = Result<T>>,
{
    let span = tracing::info_span!("operation", name = %operation);
    let _enter = span.enter();

    tracing::info!("Starting operation");
    let start = std::time::Instant::now();

    match f.await {
        Ok(result) => {
            let duration = start.elapsed();
            tracing::info!(
                duration_ms = %duration.as_millis(),
                "Operation completed successfully"
            );
            Ok(result)
        }
        Err(e) => {
            let duration = start.elapsed();
            tracing::error!(
                duration_ms = %duration.as_millis(),
                error = %e,
                "Operation failed"
            );
            Err(e)
        }
    }
}