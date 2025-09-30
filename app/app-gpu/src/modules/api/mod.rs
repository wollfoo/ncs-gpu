//! HTTP API server for monitoring and control
//!
//! Provides REST endpoints for:
//! - Health checks
//! - Metrics exposition (Prometheus format)
//! - Runtime configuration
//! - GPU status queries

use crate::error::MinerError;
use crate::messaging::bus::MiningTask;
use crate::messaging::{Message, MessageBus};
use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::net::TcpListener;
use tokio_util::sync::CancellationToken;
use tower_http::trace::TraceLayer;
use tracing::{info, warn};

/// API server configuration
#[derive(Debug, Clone, Deserialize)]
pub struct ApiConfig {
    /// Bind address (e.g., "127.0.0.1:8080")
    pub bind_addr: String,
    /// Enable CORS for web dashboards
    pub enable_cors: bool,
}

impl Default for ApiConfig {
    fn default() -> Self {
        Self {
            bind_addr: "127.0.0.1:8080".to_string(),
            enable_cors: false,
        }
    }
}

/// Shared application state
#[derive(Clone)]
struct AppState {
    message_bus: Arc<MessageBus>,
}

/// Health check response
#[derive(Serialize)]
struct HealthResponse {
    status: String,
    version: String,
}

/// Start the API server
///
/// # Arguments
/// * `config` - API server configuration
/// * `message_bus` - Shared message bus for inter-module communication
/// * `cancel_token` - Cancellation token for graceful shutdown
pub async fn start_api_server(
    config: ApiConfig,
    message_bus: Arc<MessageBus>,
    cancel_token: CancellationToken,
) -> crate::error::Result<()> {
    info!(bind_addr = %config.bind_addr, "Starting API server");

    let state = AppState { message_bus };

    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/metrics", get(metrics_handler))
        .route("/api/v1/status", get(status_handler))
        .route("/api/v1/submit_task", post(submit_task_handler))
        .layer(TraceLayer::new_for_http())
        .with_state(state);

    let listener = TcpListener::bind(&config.bind_addr)
        .await
        .map_err(|e| MinerError::Api(format!("Failed to bind to {}: {}", config.bind_addr, e)))?;

    info!(bind_addr = %config.bind_addr, "API server listening");

    axum::serve(listener, app)
        .with_graceful_shutdown(async move {
            cancel_token.cancelled().await;
            info!("API server shutting down gracefully");
        })
        .await
        .map_err(|e| MinerError::Api(format!("Server error: {}", e)))?;

    Ok(())
}

/// Health check endpoint: GET /health
async fn health_handler() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "healthy".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
    })
}

/// Prometheus metrics endpoint: GET /metrics
async fn metrics_handler() -> Response {
    // TODO: Integrate with prometheus registry from metrics module
    let metrics = prometheus::default_registry().gather();
    let encoder = prometheus::TextEncoder::new();
    match encoder.encode_to_string(&metrics) {
        Ok(text) => (StatusCode::OK, text).into_response(),
        Err(e) => {
            warn!(error = %e, "Failed to encode metrics");
            (StatusCode::INTERNAL_SERVER_ERROR, "Encoding error").into_response()
        }
    }
}

/// GPU status endpoint: GET /api/v1/status
async fn status_handler(State(_state): State<AppState>) -> Json<serde_json::Value> {
    // TODO: Query GPU status from message bus
    Json(serde_json::json!({
        "gpus": [],
        "total_hashrate": 0,
        "uptime_seconds": 0
    }))
}

/// Task submission request
#[derive(Debug, Deserialize)]
struct SubmitTaskRequest {
    gpu_id: usize,
    job_id: u64,
    difficulty: u64,
    input_data: String, // Hex-encoded data
    timeout_ms: Option<u64>,
}

/// Task submission response
#[derive(Debug, Serialize)]
struct SubmitTaskResponse {
    success: bool,
    message: String,
    job_id: u64,
}

/// Submit mining task endpoint: POST /api/v1/submit_task
///
/// Accepts JSON payload với mining task parameters và routes to appropriate GPU.
///
/// # Request Body
/// ```json
/// {
///   "gpu_id": 0,
///   "job_id": 12345,
///   "difficulty": 1000000,
///   "input_data": "deadbeef...",
///   "timeout_ms": 30000
/// }
/// ```
///
/// # Response
/// ```json
/// {
///   "success": true,
///   "message": "Task submitted to GPU 0",
///   "job_id": 12345
/// }
/// ```
async fn submit_task_handler(
    State(state): State<AppState>,
    Json(req): Json<SubmitTaskRequest>,
) -> std::result::Result<Json<SubmitTaskResponse>, (StatusCode, String)> {
    info!(
        gpu_id = req.gpu_id,
        job_id = req.job_id,
        "Received task submission request"
    );

    // Decode hex input data
    let input_data = hex::decode(&req.input_data).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("Invalid hex data: {}", e),
        )
    })?;

    // Create mining task
    let task = Arc::new(MiningTask {
        job_id: req.job_id,
        difficulty: req.difficulty,
        input_data,
        timeout_ms: req.timeout_ms.unwrap_or(30000),
    });

    // Send to GPU via message bus
    state
        .message_bus
        .send_to_gpu(req.gpu_id, Message::GpuTask(task))
        .map_err(|e| {
            warn!(gpu_id = req.gpu_id, error = %e, "Failed to send task to GPU");
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("Failed to submit task: {}", e),
            )
        })?;

    Ok(Json(SubmitTaskResponse {
        success: true,
        message: format!("Task submitted to GPU {}", req.gpu_id),
        job_id: req.job_id,
    }))
}

// Re-export for convenience
pub use start_api_server as start;

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_health_endpoint() {
        let response = health_handler().await;
        assert_eq!(response.0.status, "healthy");
    }
}
