use std::net::SocketAddr;

use axum::{routing::get, Router};
use serde::Serialize;
use tokio::{net::TcpListener, signal};
use tracing::{error, info};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[derive(Serialize)]
struct HealthResponse {
    status: &'static str,
    service: &'static str,
}

async fn health_handler() -> axum::Json<HealthResponse> {
    axum::Json(HealthResponse {
        status: "ok",
        service: "scheduler",
    })
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let app = Router::new().route("/health", get(health_handler));

    let addr: SocketAddr = std::env::var("SCHEDULER_HTTP_ADDR")
        .unwrap_or_else(|_| "0.0.0.0:8080".to_string())
        .parse()?;

    info!(address = %addr, "starting scheduler");

    let listener = TcpListener::bind(addr).await?;
    let server = axum::serve(listener, app);

    tokio::select! {
        res = server => {
            if let Err(err) = res {
                error!("scheduler server error: {err}");
            }
        }
        _ = shutdown_signal() => {
            info!("shutdown signal received");
        }
    }

    info!("scheduler stopped");
    Ok(())
}

async fn shutdown_signal() {
    if let Err(err) = signal::ctrl_c().await {
        error!("failed to listen for shutdown signal: {err}");
    }
}
