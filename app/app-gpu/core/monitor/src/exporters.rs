//! **Metrics Exporters** (Trình xuất đo lường)
//!
//! Export monitoring metrics to external systems like Prometheus and OpenTelemetry.

use crate::{MonitorError, Result, PrometheusConfig, OpenTelemetryConfig};
use crate::metrics::{Metric, GpuMetrics, SystemMetrics, PoolMetrics};
use async_trait::async_trait;
use prometheus::{Registry, Counter, Gauge, Histogram, Opts, HistogramOpts};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use parking_lot::Mutex;

/// **Metrics Exporter** (Trình xuất đo lường) - Base trait for metrics exporters
#[async_trait]
pub trait MetricsExporter: Send + Sync {
    /// Start the exporter
    async fn start(&self) -> Result<()>;

    /// Stop the exporter
    async fn stop(&self) -> Result<()>;

    /// Export metrics
    async fn export_metrics(&self, metrics: Vec<Metric>) -> Result<()>;

    /// Get exporter name
    fn name(&self) -> &str;

    /// Check if exporter is enabled
    fn is_enabled(&self) -> bool {
        true
    }
}

/// **Prometheus Exporter** (Trình xuất Prometheus) - Exports metrics in Prometheus format
pub struct PrometheusExporter {
    config: PrometheusConfig,
    registry: Arc<Registry>,
    metrics_cache: Arc<RwLock<HashMap<String, PrometheusMetricWrapper>>>,
    server_handle: Arc<RwLock<Option<tokio::task::JoinHandle<()>>>>,
    running: Arc<RwLock<bool>>,
}

/// **Prometheus Metric Wrapper** (Gói đo lường Prometheus)
#[derive(Clone)]
enum PrometheusMetricWrapper {
    Counter(Counter),
    Gauge(Gauge),
    Histogram(Histogram),
}

impl PrometheusExporter {
    /// Create new Prometheus exporter
    pub fn new(config: PrometheusConfig) -> Result<Self> {
        let registry = Registry::new();

        Ok(Self {
            config,
            registry: Arc::new(registry),
            metrics_cache: Arc::new(RwLock::new(HashMap::new())),
            server_handle: Arc::new(RwLock::new(None)),
            running: Arc::new(RwLock::new(false)),
        })
    }

    /// Create or get Prometheus metric
    async fn get_or_create_metric(&self, metric: &Metric) -> Result<PrometheusMetricWrapper> {
        let metric_key = format!("{}_{}", metric.name,
            metric.labels.iter()
                .map(|(k, v)| format!("{}={}", k, v))
                .collect::<Vec<_>>()
                .join(","));

        let mut cache = self.metrics_cache.write().await;

        if let Some(cached_metric) = cache.get(&metric_key) {
            return Ok(cached_metric.clone());
        }

        // Create new Prometheus metric
        let prometheus_metric = match &metric.value {
            crate::metrics::MetricValue::Counter(_) => {
                let counter = Counter::with_opts(
                    Opts::new(&metric.name, &metric.help)
                        .const_labels(metric.labels.clone())
                )?;

                self.registry.register(Box::new(counter.clone()))?;
                PrometheusMetricWrapper::Counter(counter)
            }
            crate::metrics::MetricValue::Gauge(_) => {
                let gauge = Gauge::with_opts(
                    Opts::new(&metric.name, &metric.help)
                        .const_labels(metric.labels.clone())
                )?;

                self.registry.register(Box::new(gauge.clone()))?;
                PrometheusMetricWrapper::Gauge(gauge)
            }
            crate::metrics::MetricValue::Histogram { buckets, .. } => {
                let bucket_boundaries: Vec<f64> = buckets.iter().map(|(bucket, _)| *bucket).collect();

                let histogram = Histogram::with_opts(
                    HistogramOpts::new(&metric.name, &metric.help)
                        .const_labels(metric.labels.clone())
                        .buckets(bucket_boundaries)
                )?;

                self.registry.register(Box::new(histogram.clone()))?;
                PrometheusMetricWrapper::Histogram(histogram)
            }
            crate::metrics::MetricValue::Summary { .. } => {
                // For simplicity, treat summaries as gauges for now
                let gauge = Gauge::with_opts(
                    Opts::new(&metric.name, &metric.help)
                        .const_labels(metric.labels.clone())
                )?;

                self.registry.register(Box::new(gauge.clone()))?;
                PrometheusMetricWrapper::Gauge(gauge)
            }
        };

        cache.insert(metric_key, prometheus_metric.clone());
        Ok(prometheus_metric)
    }

    /// Update Prometheus metric with new value
    fn update_prometheus_metric(wrapper: &PrometheusMetricWrapper, metric: &Metric) -> Result<()> {
        match (wrapper, &metric.value) {
            (PrometheusMetricWrapper::Counter(counter), crate::metrics::MetricValue::Counter(value)) => {
                counter.reset();
                counter.inc_by(*value as f64);
            }
            (PrometheusMetricWrapper::Gauge(gauge), crate::metrics::MetricValue::Gauge(value)) => {
                gauge.set(*value);
            }
            (PrometheusMetricWrapper::Gauge(gauge), crate::metrics::MetricValue::Counter(value)) => {
                gauge.set(*value as f64);
            }
            (PrometheusMetricWrapper::Histogram(histogram), crate::metrics::MetricValue::Histogram { buckets, .. }) => {
                for (bucket, count) in buckets {
                    for _ in 0..*count {
                        histogram.observe(*bucket);
                    }
                }
            }
            (PrometheusMetricWrapper::Gauge(gauge), crate::metrics::MetricValue::Summary { sum, count, .. }) => {
                if *count > 0 {
                    gauge.set(sum / (*count as f64));
                }
            }
            _ => {
                return Err(MonitorError::Export {
                    exporter: "prometheus".to_string(),
                    reason: "Metric type mismatch".to_string(),
                });
            }
        }

        Ok(())
    }

    /// Start HTTP server for metrics endpoint
    async fn start_server(&self) -> Result<tokio::task::JoinHandle<()>> {
        use std::convert::Infallible;
        use std::sync::Arc;
        use hyper::service::{make_service_fn, service_fn};
        use hyper::{Body, Request, Response, Server, Method, StatusCode};

        let registry = self.registry.clone();
        let bind_addr = format!("{}:{}", self.config.bind_address, self.config.port);

        let make_svc = make_service_fn(move |_conn| {
            let registry = registry.clone();
            async move {
                Ok::<_, Infallible>(service_fn(move |req: Request<Body>| {
                    let registry = registry.clone();
                    async move {
                        match (req.method(), req.uri().path()) {
                            (&Method::GET, "/metrics") => {
                                let metric_families = registry.gather();
                                let encoder = prometheus::TextEncoder::new();

                                match encoder.encode_to_string(&metric_families) {
                                    Ok(metrics_text) => {
                                        Response::builder()
                                            .status(StatusCode::OK)
                                            .header("Content-Type", encoder.format_type())
                                            .body(Body::from(metrics_text))
                                    }
                                    Err(e) => {
                                        Response::builder()
                                            .status(StatusCode::INTERNAL_SERVER_ERROR)
                                            .body(Body::from(format!("Error encoding metrics: {}", e)))
                                    }
                                }
                            }
                            (&Method::GET, "/health") => {
                                Response::builder()
                                    .status(StatusCode::OK)
                                    .body(Body::from("OK"))
                            }
                            _ => {
                                Response::builder()
                                    .status(StatusCode::NOT_FOUND)
                                    .body(Body::from("Not Found"))
                            }
                        }
                    }
                }))
            }
        });

        let addr = bind_addr.parse()
            .map_err(|e| MonitorError::Configuration {
                config: format!("Invalid bind address {}: {}", bind_addr, e)
            })?;

        let server = Server::bind(&addr).serve(make_svc);

        tracing::info!("Prometheus metrics server starting on http://{}{}",
                      bind_addr, self.config.metrics_path);

        let handle = tokio::spawn(async move {
            if let Err(e) = server.await {
                tracing::error!("Prometheus server error: {}", e);
            }
        });

        Ok(handle)
    }
}

#[async_trait]
impl MetricsExporter for PrometheusExporter {
    async fn start(&self) -> Result<()> {
        let mut running = self.running.write().await;
        if *running {
            return Ok(());
        }

        tracing::info!("Starting Prometheus exporter on {}:{}",
                      self.config.bind_address, self.config.port);

        let handle = self.start_server().await?;
        let mut server_handle = self.server_handle.write().await;
        *server_handle = Some(handle);

        *running = true;
        tracing::info!("Prometheus exporter started");
        Ok(())
    }

    async fn stop(&self) -> Result<()> {
        let mut running = self.running.write().await;
        if !*running {
            return Ok(());
        }

        tracing::info!("Stopping Prometheus exporter");

        let mut server_handle = self.server_handle.write().await;
        if let Some(handle) = server_handle.take() {
            handle.abort();
        }

        *running = false;
        tracing::info!("Prometheus exporter stopped");
        Ok(())
    }

    async fn export_metrics(&self, metrics: Vec<Metric>) -> Result<()> {
        for metric in metrics {
            let prometheus_metric = self.get_or_create_metric(&metric).await?;
            Self::update_prometheus_metric(&prometheus_metric, &metric)?;
        }

        Ok(())
    }

    fn name(&self) -> &str {
        "prometheus"
    }

    fn is_enabled(&self) -> bool {
        self.config.enabled
    }
}

/// **OpenTelemetry Exporter** (Trình xuất OpenTelemetry) - Exports metrics using OpenTelemetry
pub struct OpenTelemetryExporter {
    config: OpenTelemetryConfig,
    running: Arc<RwLock<bool>>,
}

impl OpenTelemetryExporter {
    /// Create new OpenTelemetry exporter
    pub fn new(config: OpenTelemetryConfig) -> Result<Self> {
        Ok(Self {
            config,
            running: Arc::new(RwLock::new(false)),
        })
    }

    /// Initialize OpenTelemetry SDK
    async fn initialize_otel(&self) -> Result<()> {
        use opentelemetry::KeyValue;

        // Set up resource
        let resource = opentelemetry::sdk::Resource::new(vec![
            KeyValue::new("service.name", self.config.service_name.clone()),
            KeyValue::new("service.version", self.config.service_version.clone()),
            KeyValue::new("deployment.environment", self.config.environment.clone()),
        ]);

        // TODO: Set up OpenTelemetry metrics pipeline
        // This is a placeholder implementation
        tracing::info!("OpenTelemetry metrics initialized (placeholder)");

        Ok(())
    }
}

#[async_trait]
impl MetricsExporter for OpenTelemetryExporter {
    async fn start(&self) -> Result<()> {
        let mut running = self.running.write().await;
        if *running {
            return Ok(());
        }

        tracing::info!("Starting OpenTelemetry exporter");

        self.initialize_otel().await?;

        *running = true;
        tracing::info!("OpenTelemetry exporter started");
        Ok(())
    }

    async fn stop(&self) -> Result<()> {
        let mut running = self.running.write().await;
        if !*running {
            return Ok(());
        }

        tracing::info!("Stopping OpenTelemetry exporter");

        // TODO: Shutdown OpenTelemetry pipeline

        *running = false;
        tracing::info!("OpenTelemetry exporter stopped");
        Ok(())
    }

    async fn export_metrics(&self, metrics: Vec<Metric>) -> Result<()> {
        // TODO: Export metrics to OpenTelemetry collector
        tracing::debug!("Exporting {} metrics to OpenTelemetry (placeholder)", metrics.len());
        Ok(())
    }

    fn name(&self) -> &str {
        "opentelemetry"
    }

    fn is_enabled(&self) -> bool {
        self.config.enabled
    }
}

/// **Multi Exporter** (Trình xuất đa kênh) - Exports to multiple backends simultaneously
pub struct MultiExporter {
    exporters: Vec<Arc<dyn MetricsExporter>>,
    running: Arc<RwLock<bool>>,
}

impl MultiExporter {
    /// Create new multi-exporter
    pub fn new(exporters: Vec<Arc<dyn MetricsExporter>>) -> Self {
        Self {
            exporters,
            running: Arc::new(RwLock::new(false)),
        }
    }

    /// Add exporter
    pub async fn add_exporter(&mut self, exporter: Arc<dyn MetricsExporter>) {
        self.exporters.push(exporter);
    }
}

#[async_trait]
impl MetricsExporter for MultiExporter {
    async fn start(&self) -> Result<()> {
        let mut running = self.running.write().await;
        if *running {
            return Ok(());
        }

        tracing::info!("Starting multi-exporter with {} backends", self.exporters.len());

        for exporter in &self.exporters {
            if exporter.is_enabled() {
                if let Err(e) = exporter.start().await {
                    tracing::error!("Failed to start exporter {}: {}", exporter.name(), e);
                }
            }
        }

        *running = true;
        tracing::info!("Multi-exporter started");
        Ok(())
    }

    async fn stop(&self) -> Result<()> {
        let mut running = self.running.write().await;
        if !*running {
            return Ok(());
        }

        tracing::info!("Stopping multi-exporter");

        for exporter in &self.exporters {
            if let Err(e) = exporter.stop().await {
                tracing::error!("Failed to stop exporter {}: {}", exporter.name(), e);
            }
        }

        *running = false;
        tracing::info!("Multi-exporter stopped");
        Ok(())
    }

    async fn export_metrics(&self, metrics: Vec<Metric>) -> Result<()> {
        let mut errors = Vec::new();

        for exporter in &self.exporters {
            if exporter.is_enabled() {
                if let Err(e) = exporter.export_metrics(metrics.clone()).await {
                    errors.push(format!("{}: {}", exporter.name(), e));
                }
            }
        }

        if !errors.is_empty() {
            return Err(MonitorError::Export {
                exporter: "multi".to_string(),
                reason: errors.join("; "),
            });
        }

        Ok(())
    }

    fn name(&self) -> &str {
        "multi"
    }

    fn is_enabled(&self) -> bool {
        self.exporters.iter().any(|e| e.is_enabled())
    }
}

/// **Metrics Export Manager** (Trình quản lý xuất đo lường) - Coordinates metric exports
pub struct MetricsExportManager {
    exporters: Vec<Arc<dyn MetricsExporter>>,
    export_interval: std::time::Duration,
    running: Arc<RwLock<bool>>,
}

impl MetricsExportManager {
    /// Create new export manager
    pub fn new(exporters: Vec<Arc<dyn MetricsExporter>>, export_interval: std::time::Duration) -> Self {
        Self {
            exporters,
            export_interval,
            running: Arc::new(RwLock::new(false)),
        }
    }

    /// Start export manager
    pub async fn start(&self) -> Result<()> {
        let mut running = self.running.write().await;
        if *running {
            return Ok(());
        }

        tracing::info!("Starting metrics export manager");

        // Start all exporters
        for exporter in &self.exporters {
            if exporter.is_enabled() {
                exporter.start().await?;
            }
        }

        *running = true;
        tracing::info!("Metrics export manager started");
        Ok(())
    }

    /// Stop export manager
    pub async fn stop(&self) -> Result<()> {
        let mut running = self.running.write().await;
        if !*running {
            return Ok(());
        }

        tracing::info!("Stopping metrics export manager");

        // Stop all exporters
        for exporter in &self.exporters {
            exporter.stop().await?;
        }

        *running = false;
        tracing::info!("Metrics export manager stopped");
        Ok(())
    }

    /// Export metrics to all enabled exporters
    pub async fn export_all(&self, gpu_metrics: &HashMap<u32, GpuMetrics>,
                            system_metrics: Option<&SystemMetrics>,
                            pool_metrics: &HashMap<String, PoolMetrics>) -> Result<()> {
        let mut all_metrics = Vec::new();

        // Convert GPU metrics
        for (_, gpu_metric) in gpu_metrics {
            all_metrics.extend(gpu_metric.to_prometheus_metrics());
        }

        // Convert system metrics
        if let Some(sys_metrics) = system_metrics {
            all_metrics.extend(sys_metrics.to_prometheus_metrics());
        }

        // Convert pool metrics
        for (_, pool_metric) in pool_metrics {
            all_metrics.extend(pool_metric.to_prometheus_metrics());
        }

        // Export to all enabled exporters
        for exporter in &self.exporters {
            if exporter.is_enabled() {
                if let Err(e) = exporter.export_metrics(all_metrics.clone()).await {
                    tracing::error!("Export failed for {}: {}", exporter.name(), e);
                }
            }
        }

        Ok(())
    }
}