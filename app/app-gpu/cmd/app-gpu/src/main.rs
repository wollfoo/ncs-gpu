use anyhow::{Context, Result};
use app_gpu_domain::{config::AppConfig, telemetry::init_tracing, ApiMode};
use app_gpu_domain::telemetry::metrics::Exporter;
use app_gpu_scheduler::{Scheduler, SchedulerHandle};
use tokio::select;
use tokio::signal;
use tracing::{error, info};

mod rest;
mod grpc;

#[tokio::main(flavor = "multi_thread", worker_threads = 4)]
async fn main() -> Result<()> {
    let config = AppConfig::load().context("load configuration")?;
    init_tracing(&config.observability)?;
    let metrics_exporter = Exporter::new(&config.metrics).context("init metrics exporter")?.spawn()?;

    info!(target: "bootstrap", "configuration loaded");

    let scheduler = Scheduler::new(config.clone()).context("create scheduler")?;
    let handle = scheduler.spawn().await.context("spawn scheduler")?;

    let rest_server = if config.api.modes.contains(&ApiMode::Rest) {
        Some(rest::serve(config.clone(), handle.clone()))
    } else {
        None
    };

    let grpc_server = if config.api.modes.contains(&ApiMode::Grpc) {
        Some(grpc::serve(config.clone(), handle.clone()))
    } else {
        None
    };

    info!(target: "bootstrap", rest = %rest_server.is_some(), grpc = %grpc_server.is_some(), "services ready");

    select! {
        _ = signal::ctrl_c() => {
            info!(target: "shutdown", "ctrl+c received");
        }
        _ = SchedulerHandle::wait_for_shutdown(handle.clone()) => {
            error!(target: "shutdown", "scheduler requested shutdown");
        }
    }

    info!(target: "shutdown", "draining services");
    if let Some(server) = rest_server { server.graceful_shutdown().await; }
    if let Some(server) = grpc_server { server.graceful_shutdown().await; }
    SchedulerHandle::stop(handle).await;
    metrics_exporter.stop().await;

    Ok(())
}
