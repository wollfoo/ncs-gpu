use app_gpu_domain::{config::AppConfig, JobSpec, ScheduleResult};
use app_gpu_scheduler::SchedulerHandle;
use axum::{extract::State, http::StatusCode, routing::{get, post}, Json, Router};
use chrono::Utc;
use serde::Serialize;
use std::net::SocketAddr;
use tokio::task::JoinHandle;
use tracing::info;

pub struct RestServer {
    join: JoinHandle<()>,
}

impl RestServer {
    pub async fn graceful_shutdown(self) {
        if let Err(err) = self.join.await {
            tracing::warn!(target = "rest", ?err, "REST server join failed");
        }
    }
}

#[derive(Debug, Serialize)]
struct ApiError {
    error: String,
}

pub fn serve(config: AppConfig, handle: SchedulerHandle) -> RestServer {
    let addr: SocketAddr = config.api.rest_bind.parse().expect("invalid REST bind address");
    let state = handle.clone();
    let shutdown_handle = handle.clone();

    let router = Router::new()
        .route("/healthz", get(healthz))
        .route("/schedule", post(schedule))
        .with_state(state);

    let join = tokio::spawn(async move {
        info!(target: "rest", "listening", %addr);
        axum::Server::bind(&addr)
            .serve(router.into_make_service())
            .with_graceful_shutdown(async move {
                shutdown_handle.shutdown_notifier().await;
            })
            .await
            .expect("REST server failed");
    });

    RestServer { join }
}

async fn healthz() -> &'static str {
    "ok"
}

async fn schedule(
    State(handle): State<SchedulerHandle>,
    Json(payload): Json<JobSpec>,
) -> Result<Json<ScheduleResult>, (StatusCode, Json<ApiError>)> {
    let job_id = handle
        .schedule(payload)
        .await
        .map_err(|err| {
            let message = format!("failed to enqueue job: {err}");
            (StatusCode::INTERNAL_SERVER_ERROR, Json(ApiError { error: message }))
        })?;

    Ok(Json(ScheduleResult { job_id, queued_at: Utc::now() }))
}
