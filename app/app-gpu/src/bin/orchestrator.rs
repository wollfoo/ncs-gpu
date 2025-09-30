use std::{collections::VecDeque, net::SocketAddr, sync::Arc};
use axum::{
    extract::State,
    routing::{get, post},
    Json, Router,
};
use tokio::sync::Mutex;
use tracing::{info, Level};
use tracing_subscriber::EnvFilter;

use app_gpu::{EnqueueRequest, EnqueueResponse, Task, TaskStatus};

#[derive(Clone, Default)]
struct AppState {
    queue: Arc<Mutex<VecDeque<Task>>>,
}

#[tokio::main]
async fn main() {
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::from_default_env().add_directive(Level::INFO.into()));
    tracing_subscriber::fmt().with_env_filter(filter).init();

    let state = AppState::default();
    let app = Router::new()
        .route("/healthz", get(healthz))
        .route("/metrics", get(metrics))
        .route("/enqueue", post(enqueue))
        .route("/dequeue", get(dequeue))
        .with_state(state);

    let addr: SocketAddr = std::env::var("ORCH_ADDR").unwrap_or_else(|_| "0.0.0.0:8080".to_string()).parse().unwrap();
    info!("orchestrator listening on http://{addr}");
    axum::Server::bind(&addr).serve(app.into_make_service()).await.unwrap();
}

async fn healthz() -> &'static str {
    "ok"
}

async fn metrics(State(state): State<AppState>) -> String {
    let q = state.queue.lock().await;
    format!("queue_len {}\n", q.len())
}

async fn enqueue(State(state): State<AppState>, Json(req): Json<EnqueueRequest>) -> Json<EnqueueResponse> {
    let task = Task::new(req.kind);
    let id = task.id;
    {
        let mut q = state.queue.lock().await;
        q.push_back(task);
    }
    Json(EnqueueResponse { id, status: TaskStatus::Queued })
}

async fn dequeue(State(state): State<AppState>) -> Json<Option<Task>> {
    let mut q = state.queue.lock().await;
    Json(q.pop_front())
}
