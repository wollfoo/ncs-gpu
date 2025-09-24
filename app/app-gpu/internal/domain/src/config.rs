use anyhow::{Context, Result};
use serde::Deserialize;
use std::{collections::BTreeSet, path::PathBuf};

use super::ApiMode;

#[derive(Debug, Clone, Deserialize)]
pub struct AppConfig {
    #[serde(default = "default_config_path")]
    pub config_path: PathBuf,
    #[serde(default)]
    pub api: ApiConfig,
    #[serde(default)]
    pub scheduler: SchedulerConfig,
    #[serde(default)]
    pub observability: ObservabilityConfig,
    #[serde(default)]
    pub metrics: MetricsConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ApiConfig {
    #[serde(default = "default_rest_bind")]
    pub rest_bind: String,
    #[serde(default = "default_grpc_bind")]
    pub grpc_bind: String,
    #[serde(default = "default_api_modes")]
    pub modes: BTreeSet<ApiMode>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SchedulerConfig {
    #[serde(default = "default_backlog")] pub backlog: usize,
    #[serde(default = "default_batch_size")] pub batch_size: usize,
    #[serde(default = "default_tick_ms")] pub tick_ms: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ObservabilityConfig {
    #[serde(default = "default_log_level")] pub log_level: String,
    #[serde(default = "default_tracer_endpoint")] pub tracer_endpoint: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MetricsConfig {
    #[serde(default = "default_metrics_port")] pub port: u16,
}

impl Default for ApiConfig {
    fn default() -> Self {
        Self {
            rest_bind: default_rest_bind(),
            grpc_bind: default_grpc_bind(),
            modes: default_api_modes(),
        }
    }
}

impl Default for SchedulerConfig {
    fn default() -> Self {
        Self {
            backlog: default_backlog(),
            batch_size: default_batch_size(),
            tick_ms: default_tick_ms(),
        }
    }
}

impl Default for ObservabilityConfig {
    fn default() -> Self {
        Self {
            log_level: default_log_level(),
            tracer_endpoint: default_tracer_endpoint(),
        }
    }
}

impl Default for MetricsConfig {
    fn default() -> Self {
        Self { port: default_metrics_port() }
    }
}

impl AppConfig {
    pub fn load() -> Result<Self> {
        let config_path = std::env::var("APP_CONFIG_PATH").map(PathBuf::from).unwrap_or_else(|_| default_config_path());
        let mut settings = config::Config::builder();
        settings = settings.add_source(config::File::from(config_path.clone()).required(false));
        settings = settings.add_source(config::Environment::with_prefix("APP_GPU").separator("__"));

        let mut cfg: AppConfig = settings
            .build()
            .context("read configuration")?
            .try_deserialize()
            .context("deserialize configuration")?;
        cfg.config_path = config_path;
        Ok(cfg)
    }
}

fn default_config_path() -> PathBuf {
    PathBuf::from("./configs/default.yaml")
}
fn default_rest_bind() -> String { "0.0.0.0:8080".into() }
fn default_grpc_bind() -> String { "0.0.0.0:50051".into() }
fn default_api_modes() -> BTreeSet<ApiMode> {
    [ApiMode::Rest, ApiMode::Grpc].into_iter().collect()
}
fn default_backlog() -> usize { 1024 }
fn default_batch_size() -> usize { 64 }
fn default_tick_ms() -> u64 { 500 }
fn default_log_level() -> String { "info".into() }
fn default_tracer_endpoint() -> String { "http://otel-collector:4317".into() }
fn default_metrics_port() -> u16 { 9100 }
