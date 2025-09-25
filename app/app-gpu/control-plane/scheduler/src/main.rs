use std::{
    net::SocketAddr,
    sync::Arc,
    time::{SystemTime, UNIX_EPOCH},
};

use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    routing::{get, post},
    Json, Router,
};
use metrics_exporter_prometheus::PrometheusBuilder;
use nats_lite::NatsConnection;
use once_cell::sync::OnceCell;
use serde::{Deserialize, Serialize};
use tokio::{net::TcpListener, signal};
use tracing::{error, info};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};
use uuid::Uuid;

#[derive(Clone)]
struct AppState {
    nats: NatsConnection,
    subject: String,
    bearer_token: Option<String>,
}

#[derive(Serialize)]
struct HealthResponse {
    status: &'static str,
    service: &'static str,
}

#[derive(Deserialize)]
struct CreateJobRequest {
    payload: serde_json::Value,
}

#[derive(Serialize)]
struct CreateJobResponse {
    id: String,
}

async fn health_handler() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok",
        service: "scheduler",
    })
}

async fn create_job(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(request): Json<CreateJobRequest>,
) -> Result<Json<CreateJobResponse>, StatusCode> {
    if let Some(expected) = &state.bearer_token {
        let provided = headers
            .get(axum::http::header::AUTHORIZATION)
            .and_then(|value| value.to_str().ok());
        let expected_header = format!("Bearer {expected}");
        if provided != Some(expected_header.as_str()) {
            metrics::counter!("scheduler_jobs_unauthorized_total").increment(1);
            return Err(StatusCode::UNAUTHORIZED);
        }
    }

    metrics::counter!("scheduler_jobs_received_total").increment(1);
    let job_id = Uuid::new_v4().to_string();
    let job_id_for_message = job_id.clone();
    let created_at = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .as_secs_f64();
    let message = serde_json::json!({
        "id": job_id_for_message,
        "payload": request.payload,
        "created_at": created_at,
    });

    let job_bytes = serde_json::to_vec(&message).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    state
        .nats
        .publish(&state.subject, &job_bytes)
        .await
        .map_err(|err| {
            metrics::counter!("scheduler_jobs_publish_error_total").increment(1);
            error!(error = %err, "không thể publish job tới NATS");
            StatusCode::BAD_GATEWAY
        })?;

    metrics::counter!("scheduler_jobs_published_total").increment(1);
    metrics::histogram!("scheduler_job_payload_bytes").record(job_bytes.len() as f64);

    Ok(Json(CreateJobResponse { id: job_id }))
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    init_metrics()?;

    let nats_url = std::env::var("NATS_URL").unwrap_or_else(|_| "127.0.0.1:4222".into());
    let subject = std::env::var("SCHEDULER_SUBJECT").unwrap_or_else(|_| "gpu.jobs".into());
    let bearer_token = std::env::var("SCHEDULER_BEARER_TOKEN").ok();
    let auth_token = std::env::var("NATS_AUTH_TOKEN").ok();

    let nats = NatsConnection::connect(&nats_url, "scheduler", auth_token.as_deref()).await?;
    let state = Arc::new(AppState {
        nats,
        subject,
        bearer_token,
    });

    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/jobs", post(create_job))
        .with_state(state);

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

static PROM_HANDLE: OnceCell<metrics_exporter_prometheus::PrometheusHandle> = OnceCell::new();

fn init_metrics() -> anyhow::Result<()> {
    let addr: SocketAddr = std::env::var("SCHEDULER_METRICS_ADDR")
        .unwrap_or_else(|_| "0.0.0.0:9100".into())
        .parse()?;

    let handle = PrometheusBuilder::new()
        .with_http_listener(addr)
        .install_recorder()?;

    let _ = PROM_HANDLE.set(handle);
    Ok(())
}
