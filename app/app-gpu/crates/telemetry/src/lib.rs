use anyhow::{Context, Result};
use metrics_exporter_prometheus::{PrometheusBuilder, PrometheusHandle};
use once_cell::sync::OnceCell;
use opentelemetry::global;
use opentelemetry::KeyValue;
use opentelemetry_otlp::WithExportConfig;
use opentelemetry_sdk::resource::Resource;
use opentelemetry_sdk::{runtime, trace};
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::EnvFilter;

static TELEMETRY_INIT: OnceCell<()> = OnceCell::new();

#[derive(Clone, Debug)]
pub struct TelemetryConfig {
    pub service_name: String,
    pub otlp_endpoint: Option<String>,
    pub enable_prometheus: bool,
}

impl Default for TelemetryConfig {
    fn default() -> Self {
        Self {
            service_name: "app-gpu".into(),
            otlp_endpoint: None,
            enable_prometheus: false,
        }
    }
}

pub struct TelemetryGuard {
    prom_handle: Option<PrometheusHandle>,
}

impl TelemetryGuard {
    pub fn prometheus_snapshot(&self) -> Option<String> {
        self.prom_handle.as_ref().map(|handle| handle.render())
    }
}

impl Drop for TelemetryGuard {
    fn drop(&mut self) {
        global::shutdown_tracer_provider();
    }
}

pub fn init(config: TelemetryConfig) -> Result<TelemetryGuard> {
    let resource = Resource::new(vec![KeyValue::new("service.name", config.service_name.clone())]);

    if let Some(endpoint) = &config.otlp_endpoint {
        let trace_exporter = opentelemetry_otlp::new_exporter().tonic().with_endpoint(endpoint.clone());

        opentelemetry_otlp::new_pipeline()
            .tracing()
            .with_trace_config(trace::Config::default().with_resource(resource.clone()))
            .with_exporter(trace_exporter)
            .install_batch(runtime::Tokio)
            .context("failed to install tracing pipeline")?;

        let metrics_exporter = opentelemetry_otlp::new_exporter().tonic().with_endpoint(endpoint.clone());
        let _ = opentelemetry_otlp::new_pipeline()
            .metrics(runtime::Tokio)
            .with_exporter(metrics_exporter)
            .with_resource(resource.clone())
            .build();
    }

    if TELEMETRY_INIT.get().is_none() {
        let env_filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
        tracing_subscriber::registry()
            .with(env_filter)
            .with(tracing_subscriber::fmt::layer())
            .try_init()
            .ok();
        let _ = TELEMETRY_INIT.set(());
    }

    let prom_handle = if config.enable_prometheus {
        Some(
            PrometheusBuilder::new()
                .install_recorder()
                .context("failed to install prometheus recorder")?,
        )
    } else {
        None
    };

    Ok(TelemetryGuard { prom_handle })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn prometheus_metrics_render() {
        let guard = init(TelemetryConfig {
            service_name: "telemetry-test".into(),
            otlp_endpoint: None,
            enable_prometheus: true,
        })
        .expect("init telemetry");

        metrics::counter!("jobs_submitted").increment(1);

        let output = guard.prometheus_snapshot().expect("prometheus output");
        assert!(output.contains("jobs_submitted"));
    }
}
