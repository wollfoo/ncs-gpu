use axum::{routing::post, Json, Router};
use rand::Rng;
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use tokio::signal;

#[derive(Deserialize)]
struct InferenceRequest {
    batch: Vec<std::collections::HashMap<String, f32>>,
}

#[derive(Serialize)]
struct InferenceResponse {
    metrics: Vec<f32>,
    processed: usize,
}

#[tokio::main]
async fn main() {
    let app = Router::new().route("/infer", post(handle_infer));
    let addr: SocketAddr = "0.0.0.0:7070".parse().unwrap();
    axum::serve(tokio::net::TcpListener::bind(addr).await.unwrap(), app)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .unwrap();
}

async fn handle_infer(Json(payload): Json<InferenceRequest>) -> Json<InferenceResponse> {
    let mut metrics = Vec::with_capacity(payload.batch.len());
    for item in payload.batch.iter() {
        let sum: f32 = item.values().copied().sum();
        let jitter: f32 = rand::thread_rng().gen_range(0.8..1.2);
        metrics.push(sum * jitter);
    }
    Json(InferenceResponse {
        metrics,
        processed: payload.batch.len(),
    })
}

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {}
        _ = terminate => {}
    }
}

