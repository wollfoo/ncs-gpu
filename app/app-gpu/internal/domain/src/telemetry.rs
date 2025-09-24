use anyhow::Result;
use crate::config::{MetricsConfig, ObservabilityConfig};
use serde::Deserialize;
use tracing::Level;
use tracing_subscriber::{fmt, EnvFilter, Registry};

#[derive(Debug, Clone, Deserialize)]
pub struct TelemetrySettings {
    #[serde(default = "default_service_name")] pub service_name: String,
}

pub fn init_tracing(cfg: &ObservabilityConfig) -> Result<()> {
    let env_filter = EnvFilter::builder()
        .with_default_directive(cfg.log_level.parse().unwrap_or(Level::INFO.into()))
        .from_env_lossy();

    Registry::default()
        .with(env_filter)
        .with(fmt::layer().compact())
        .try_init()
        .or_else(|_| Ok(()))?;
    Ok(())
}

fn default_service_name() -> String { "app-gpu".into() }

pub struct HttpServerTelemetry;

impl HttpServerTelemetry {
    pub async fn prometheus() -> &'static str {
        "metrics"
    }
}

pub mod metrics {
    use super::*;
    use metrics_exporter_prometheus::{PrometheusBuilder, PrometheusHandle};
    use std::net::SocketAddr;
    use tokio::{net::TcpListener, task::JoinHandle};

    #[derive(Clone, Debug)]
    pub struct ExporterConfig {
        pub port: u16,
    }

    pub struct Exporter {
        handle: PrometheusHandle,
        join: Option<JoinHandle<()>>,
        cfg: ExporterConfig,
    }

    impl Exporter {
        pub fn new(cfg: &MetricsConfig) -> Result<Self> {
            let builder = PrometheusBuilder::new();
            let (recorder, handle) = builder.build()?;
            metrics::set_boxed_recorder(Box::new(recorder))?;
            Ok(Self {
                handle,
                join: None,
                cfg: ExporterConfig { port: cfg.port },
            })
        }

        pub fn spawn(mut self) -> Result<Self> {
            let addr: SocketAddr = format!("0.0.0.0:{}", self.cfg.port).parse().unwrap();
            let handle = self.handle.clone();
            self.join = Some(tokio::spawn(async move {
                let listener = TcpListener::bind(addr).await.expect("bind metrics");
                loop {
                    if let Ok((mut socket, _)) = listener.accept().await {
                        let body = handle.render();
                        let response = format!(
                            "HTTP/1.1 200 OK\r\ncontent-type: text/plain\r\ncontent-length: {}\r\n\r\n{}",
                            body.len(), body
                        );
                        if let Err(err) = socket.try_write(response.as_bytes()) {
                            tracing::warn!(target = "metrics", ?err, "failed to write metrics response");
                        }
                    }
                }
            }));
            Ok(self)
        }

        pub async fn stop(mut self) {
            if let Some(join) = self.join.take() {
                join.abort();
            }
        }
    }
}

