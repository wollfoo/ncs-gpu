use std::{net::SocketAddr, sync::Arc};

use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    routing::{get, post},
    Json, Router,
};
use job_core::{
    DynJobStore, JobError, JobPayload, JobRecord, JobStatus, JobStoreBuilder, JobUpdate,
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
    store: DynJobStore,
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
    status: JobStatus,
}

#[derive(Serialize)]
struct JobDetailsResponse {
    job: JobRecord,
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
    let payload = JobPayload::try_from(request.payload).map_err(|err| {
        metrics::counter!("scheduler_jobs_invalid_payload_total").increment(1);
        error!(error = ?err, "payload không hợp lệ");
        StatusCode::UNPROCESSABLE_ENTITY
    })?;

    let job_record = JobRecord::new(job_id.clone(), payload.clone());
    if let Err(err) = state.store.create_job(job_record.clone()).await {
        metrics::counter!("scheduler_jobs_store_error_total").increment(1);
        error!(error = ?err, job_id = %job_id, "không thể lưu job vào store");
        return Err(status_from_store_error(&err));
    }

    let message = serde_json::json!({
        "id": job_record.id.clone(),
        "payload": payload,
        "created_at": job_record.created_at,
    });

    let job_bytes = serde_json::to_vec(&message).map_err(|err| {
        error!(error = %err, "không serialize được job message");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    if let Err(err) = state.nats.publish(&state.subject, &job_bytes).await {
        metrics::counter!("scheduler_jobs_publish_error_total").increment(1);
        error!(error = %err, "không thể publish job tới NATS");
        let update = JobUpdate::failed(format!("publish NATS error: {err}"));
        if let Err(store_err) = state.store.update_job(&job_id, update).await {
            error!(error = ?store_err, job_id = %job_id, "không thể cập nhật trạng thái thất bại");
        }
        return Err(StatusCode::BAD_GATEWAY);
    }

    metrics::counter!("scheduler_jobs_published_total").increment(1);
    metrics::histogram!("scheduler_job_payload_bytes").record(job_bytes.len() as f64);

    Ok(Json(CreateJobResponse {
        id: job_id,
        status: JobStatus::Queued,
    }))
}

async fn get_job(
    Path(job_id): Path<String>,
    State(state): State<Arc<AppState>>,
) -> Result<Json<JobDetailsResponse>, StatusCode> {
    match state.store.get_job(&job_id).await {
        Ok(Some(record)) => Ok(Json(JobDetailsResponse { job: record })),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(err) => {
            error!(error = ?err, job_id = %job_id, "không thể truy vấn job");
            Err(status_from_store_error(&err))
        }
    }
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
    let store = JobStoreBuilder::from_env().build().await?;
    let state = Arc::new(AppState {
        nats,
        subject,
        bearer_token,
        store,
    });

    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/jobs", post(create_job))
        .route("/jobs/:id", get(get_job))
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

fn status_from_store_error(err: &JobError) -> StatusCode {
    match err {
        JobError::InvalidPayload(_) => StatusCode::UNPROCESSABLE_ENTITY,
        JobError::NotFound => StatusCode::NOT_FOUND,
        JobError::Redis(_) => StatusCode::BAD_GATEWAY,
        JobError::Serialization(_) | JobError::StoreFailure(_) => StatusCode::INTERNAL_SERVER_ERROR,
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
