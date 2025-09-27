//! Distributed tracing module with OpenTelemetry
//! 
//! Provides distributed tracing capabilities for tracking requests across the system

use opentelemetry::{
    global,
    propagation::Injector,
    sdk::{
        propagation::TraceContextPropagator,
        trace::{self, RandomIdGenerator, Sampler},
        Resource,
    },
    trace::{
        Span, SpanBuilder, SpanContext, SpanId, SpanKind, Status,
        TraceContextExt, TraceError, TraceId, Tracer, TracerProvider,
    },
    Context, KeyValue,
};
use opentelemetry_otlp::{ExportConfig, WithExportConfig};
use opentelemetry_semantic_conventions as semcov;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, SystemTime};
use anyhow::{Result, Context as AnyhowContext};
use tracing::{debug, error, info, warn};
use tracing_opentelemetry::OpenTelemetryLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

/// Tracing configuration
#[derive(Clone, Debug)]
pub struct TracingConfig {
    pub service_name: String,
    pub service_version: String,
    pub otlp_endpoint: String,
    pub sampling_ratio: f64,
    pub export_timeout: Duration,
    pub batch_timeout: Duration,
    pub max_export_batch_size: usize,
    pub max_queue_size: usize,
}

impl Default for TracingConfig {
    fn default() -> Self {
        Self {
            service_name: "opus-gpu".to_string(),
            service_version: env!("CARGO_PKG_VERSION").to_string(),
            otlp_endpoint: "http://localhost:4317".to_string(),
            sampling_ratio: 1.0,
            export_timeout: Duration::from_secs(10),
            batch_timeout: Duration::from_millis(500),
            max_export_batch_size: 512,
            max_queue_size: 2048,
        }
    }
}

/// Initialize tracing subsystem
pub fn init_tracing(config: TracingConfig) -> Result<()> {
    global::set_text_map_propagator(TraceContextPropagator::new());
    
    let tracer = init_tracer(&config)?;
    
    // Create OpenTelemetry layer
    let otel_layer = OpenTelemetryLayer::new(tracer);
    
    // Initialize tracing subscriber với layers
    tracing_subscriber::registry()
        .with(EnvFilter::from_default_env())
        .with(tracing_subscriber::fmt::layer())
        .with(otel_layer)
        .try_init()
        .context("Failed to initialize tracing subscriber")?;
    
    info!("Tracing initialized with OTLP endpoint: {}", config.otlp_endpoint);
    Ok(())
}

/// Initialize OpenTelemetry tracer
fn init_tracer(config: &TracingConfig) -> Result<impl Tracer> {
    let export_config = ExportConfig {
        endpoint: config.otlp_endpoint.clone(),
        timeout: config.export_timeout,
        protocol: opentelemetry_otlp::Protocol::Grpc,
    };
    
    let resource = Resource::new(vec![
        KeyValue::new(
            semcov::resource::SERVICE_NAME.as_str(),
            config.service_name.clone(),
        ),
        KeyValue::new(
            semcov::resource::SERVICE_VERSION.as_str(),
            config.service_version.clone(),
        ),
        KeyValue::new("service.language", "rust"),
        KeyValue::new("service.runtime", "opus-gpu"),
    ]);
    
    opentelemetry_otlp::new_pipeline()
        .tracing()
        .with_exporter(
            opentelemetry_otlp::new_exporter()
                .tonic()
                .with_export_config(export_config)
        )
        .with_trace_config(
            trace::config()
                .with_sampler(Sampler::TraceIdRatioBased(config.sampling_ratio))
                .with_id_generator(RandomIdGenerator::default())
                .with_max_events_per_span(64)
                .with_max_attributes_per_span(32)
                .with_max_links_per_span(32)
                .with_resource(resource),
        )
        .install_batch(opentelemetry::runtime::Tokio)
        .context("Failed to install OpenTelemetry tracer")
}

/// GPU operation span builder
pub struct GPUSpan {
    span: Box<dyn Span>,
    start_time: SystemTime,
}

impl GPUSpan {
    /// Create a new GPU operation span
    pub fn new(operation: &str, device_id: usize) -> Self {
        let tracer = global::tracer("gpu-operations");
        let mut span = tracer
            .span_builder(operation)
            .with_kind(SpanKind::Internal)
            .with_attributes(vec![
                KeyValue::new("gpu.device_id", device_id as i64),
                KeyValue::new("gpu.operation", operation.to_string()),
            ])
            .start(&tracer);
        
        let start_time = SystemTime::now();
        
        Self {
            span: Box::new(span),
            start_time,
        }
    }
    
    /// Add GPU metrics to span
    pub fn set_gpu_metrics(&mut self, metrics: GPUSpanMetrics) {
        self.span.set_attributes(vec![
            KeyValue::new("gpu.utilization", metrics.utilization),
            KeyValue::new("gpu.memory_used_mb", metrics.memory_used_mb as i64),
            KeyValue::new("gpu.memory_total_mb", metrics.memory_total_mb as i64),
            KeyValue::new("gpu.temperature", metrics.temperature),
            KeyValue::new("gpu.power_watts", metrics.power_watts),
        ]);
    }
    
    /// Add kernel execution info
    pub fn add_kernel_info(&mut self, kernel_name: &str, grid_size: (u32, u32, u32), block_size: (u32, u32, u32)) {
        self.span.set_attributes(vec![
            KeyValue::new("cuda.kernel_name", kernel_name.to_string()),
            KeyValue::new("cuda.grid_x", grid_size.0 as i64),
            KeyValue::new("cuda.grid_y", grid_size.1 as i64),
            KeyValue::new("cuda.grid_z", grid_size.2 as i64),
            KeyValue::new("cuda.block_x", block_size.0 as i64),
            KeyValue::new("cuda.block_y", block_size.1 as i64),
            KeyValue::new("cuda.block_z", block_size.2 as i64),
        ]);
    }
    
    /// Record memory transfer
    pub fn record_memory_transfer(&mut self, bytes: u64, direction: &str, duration_ms: f64) {
        self.span.add_event(
            format!("Memory transfer: {}", direction),
            vec![
                KeyValue::new("transfer.bytes", bytes as i64),
                KeyValue::new("transfer.direction", direction.to_string()),
                KeyValue::new("transfer.duration_ms", duration_ms),
                KeyValue::new("transfer.bandwidth_gb_s", 
                    (bytes as f64 / 1_073_741_824.0) / (duration_ms / 1000.0)),
            ],
        );
    }
    
    /// Mark span as failed
    pub fn set_error(&mut self, error: &str) {
        self.span.set_status(Status::error(error));
        self.span.record_error(&anyhow::anyhow!(error));
    }
    
    /// Complete the span
    pub fn end(mut self) {
        let duration = SystemTime::now()
            .duration_since(self.start_time)
            .unwrap_or_default();
        
        self.span.set_attribute(KeyValue::new(
            "duration_ms",
            duration.as_millis() as i64,
        ));
        
        self.span.end();
    }
}

/// GPU span metrics
#[derive(Debug, Clone)]
pub struct GPUSpanMetrics {
    pub utilization: f64,
    pub memory_used_mb: u64,
    pub memory_total_mb: u64,
    pub temperature: f64,
    pub power_watts: f64,
}

/// Task execution tracer
pub struct TaskTracer {
    tracer: Box<dyn Tracer>,
}

impl TaskTracer {
    pub fn new() -> Self {
        Self {
            tracer: Box::new(global::tracer("task-execution")),
        }
    }
    
    /// Start task execution span
    pub fn start_task(&self, task_id: &str, task_type: &str) -> TaskSpan {
        let mut span = self
            .tracer
            .span_builder(format!("task.{}", task_type))
            .with_kind(SpanKind::Internal)
            .with_attributes(vec![
                KeyValue::new("task.id", task_id.to_string()),
                KeyValue::new("task.type", task_type.to_string()),
            ])
            .start(&self.tracer);
        
        TaskSpan {
            span: Box::new(span),
            task_id: task_id.to_string(),
            start_time: SystemTime::now(),
        }
    }
}

/// Task execution span
pub struct TaskSpan {
    span: Box<dyn Span>,
    task_id: String,
    start_time: SystemTime,
}

impl TaskSpan {
    /// Add task metadata
    pub fn set_metadata(&mut self, metadata: HashMap<String, String>) {
        let attrs: Vec<KeyValue> = metadata
            .into_iter()
            .map(|(k, v)| KeyValue::new(format!("task.meta.{}", k), v))
            .collect();
        
        self.span.set_attributes(attrs);
    }
    
    /// Record scheduling event
    pub fn record_scheduled(&mut self, worker_id: &str, gpu_ids: Vec<usize>) {
        self.span.add_event(
            "Task scheduled",
            vec![
                KeyValue::new("worker.id", worker_id.to_string()),
                KeyValue::new("gpu.ids", format!("{:?}", gpu_ids)),
            ],
        );
    }
    
    /// Record checkpoint
    pub fn record_checkpoint(&mut self, checkpoint_id: &str, progress: f64) {
        self.span.add_event(
            "Checkpoint saved",
            vec![
                KeyValue::new("checkpoint.id", checkpoint_id.to_string()),
                KeyValue::new("checkpoint.progress", progress),
            ],
        );
    }
    
    /// Record retry
    pub fn record_retry(&mut self, attempt: u32, reason: &str) {
        self.span.add_event(
            "Task retry",
            vec![
                KeyValue::new("retry.attempt", attempt as i64),
                KeyValue::new("retry.reason", reason.to_string()),
            ],
        );
    }
    
    /// Mark task as completed
    pub fn complete(mut self, status: TaskStatus) {
        let duration = SystemTime::now()
            .duration_since(self.start_time)
            .unwrap_or_default();
        
        self.span.set_attributes(vec![
            KeyValue::new("task.status", status.to_string()),
            KeyValue::new("task.duration_ms", duration.as_millis() as i64),
        ]);
        
        match status {
            TaskStatus::Completed => {
                self.span.set_status(Status::ok("Task completed successfully"));
            }
            TaskStatus::Failed(ref err) => {
                self.span.set_status(Status::error(err));
            }
            TaskStatus::Cancelled => {
                self.span.set_status(Status::error("Task cancelled"));
            }
        }
        
        self.span.end();
    }
}

/// Task completion status
#[derive(Debug, Clone)]
pub enum TaskStatus {
    Completed,
    Failed(String),
    Cancelled,
}

impl ToString for TaskStatus {
    fn to_string(&self) -> String {
        match self {
            TaskStatus::Completed => "completed".to_string(),
            TaskStatus::Failed(_) => "failed".to_string(),
            TaskStatus::Cancelled => "cancelled".to_string(),
        }
    }
}

/// HTTP request tracer for API endpoints
pub struct HttpTracer {
    tracer: Box<dyn Tracer>,
}

impl HttpTracer {
    pub fn new() -> Self {
        Self {
            tracer: Box::new(global::tracer("http")),
        }
    }
    
    /// Start HTTP request span
    pub fn start_request(&self, method: &str, path: &str) -> HttpSpan {
        let mut span = self
            .tracer
            .span_builder(format!("{} {}", method, path))
            .with_kind(SpanKind::Server)
            .with_attributes(vec![
                KeyValue::new("http.method", method.to_string()),
                KeyValue::new("http.target", path.to_string()),
                KeyValue::new("http.scheme", "http"),
            ])
            .start(&self.tracer);
        
        HttpSpan {
            span: Box::new(span),
            start_time: SystemTime::now(),
        }
    }
}

/// HTTP request span
pub struct HttpSpan {
    span: Box<dyn Span>,
    start_time: SystemTime,
}

impl HttpSpan {
    /// Set request headers
    pub fn set_headers(&mut self, headers: HashMap<String, String>) {
        for (key, value) in headers {
            self.span.set_attribute(KeyValue::new(
                format!("http.request.header.{}", key.to_lowercase()),
                value,
            ));
        }
    }
    
    /// Set response status
    pub fn set_response(&mut self, status_code: u16, body_size: usize) {
        self.span.set_attributes(vec![
            KeyValue::new("http.status_code", status_code as i64),
            KeyValue::new("http.response.body.size", body_size as i64),
        ]);
        
        if status_code >= 400 {
            self.span.set_status(Status::error(format!("HTTP {}", status_code)));
        } else {
            self.span.set_status(Status::ok(""));
        }
    }
    
    /// Complete the request span
    pub fn end(mut self) {
        let duration = SystemTime::now()
            .duration_since(self.start_time)
            .unwrap_or_default();
        
        self.span.set_attribute(KeyValue::new(
            "http.duration_ms",
            duration.as_millis() as i64,
        ));
        
        self.span.end();
    }
}

/// Sampling strategies
pub enum SamplingStrategy {
    /// Sample all traces
    AlwaysOn,
    /// Never sample
    AlwaysOff,
    /// Sample based on trace ID ratio
    TraceIdRatio(f64),
    /// Sample based on parent decision
    ParentBased(Box<SamplingStrategy>),
    /// Custom sampling logic
    Custom(Box<dyn Fn(&SpanContext) -> bool + Send + Sync>),
}

impl SamplingStrategy {
    /// Convert to OpenTelemetry sampler
    pub fn to_sampler(&self) -> Sampler {
        match self {
            SamplingStrategy::AlwaysOn => Sampler::AlwaysOn,
            SamplingStrategy::AlwaysOff => Sampler::AlwaysOff,
            SamplingStrategy::TraceIdRatio(ratio) => Sampler::TraceIdRatioBased(*ratio),
            SamplingStrategy::ParentBased(strategy) => {
                Sampler::ParentBased(Box::new(strategy.to_sampler()))
            }
            SamplingStrategy::Custom(_) => {
                // For custom sampling, default to trace ID ratio
                Sampler::TraceIdRatioBased(0.1)
            }
        }
    }
}

/// Shutdown tracing subsystem
pub fn shutdown_tracing() {
    global::shutdown_tracer_provider();
    info!("Tracing subsystem shut down");
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_tracing_config() {
        let config = TracingConfig::default();
        assert_eq!(config.service_name, "opus-gpu");
        assert_eq!(config.sampling_ratio, 1.0);
    }
    
    #[test]
    fn test_gpu_span() {
        let mut span = GPUSpan::new("matmul", 0);
        
        span.set_gpu_metrics(GPUSpanMetrics {
            utilization: 85.0,
            memory_used_mb: 10240,
            memory_total_mb: 24576,
            temperature: 65.0,
            power_watts: 250.0,
        });
        
        span.add_kernel_info("matmul_kernel", (128, 1, 1), (256, 1, 1));
        span.record_memory_transfer(1073741824, "host_to_device", 25.0);
        
        span.end();
    }
    
    #[test]
    fn test_task_tracer() {
        let tracer = TaskTracer::new();
        let mut span = tracer.start_task("task-123", "compute");
        
        let mut metadata = HashMap::new();
        metadata.insert("priority".to_string(), "high".to_string());
        span.set_metadata(metadata);
        
        span.record_scheduled("worker-1", vec![0, 1]);
        span.record_checkpoint("checkpoint-1", 0.5);
        span.record_retry(1, "GPU OOM");
        
        span.complete(TaskStatus::Completed);
    }
    
    #[test]
    fn test_sampling_strategies() {
        let always_on = SamplingStrategy::AlwaysOn;
        let always_off = SamplingStrategy::AlwaysOff;
        let ratio = SamplingStrategy::TraceIdRatio(0.5);
        let parent_based = SamplingStrategy::ParentBased(Box::new(SamplingStrategy::AlwaysOn));
        
        // Test conversion to sampler
        let _ = always_on.to_sampler();
        let _ = always_off.to_sampler();
        let _ = ratio.to_sampler();
        let _ = parent_based.to_sampler();
    }
}
