use std::net::SocketAddr;

use anyhow::Result;
use metrics_exporter_prometheus::PrometheusBuilder;
use nats_lite::{NatsConnection, NatsSubscription};
use once_cell::sync::OnceCell;
use serde::Deserialize;
use tokio::time::{sleep, Duration, Instant};
use tracing::{error, info};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[derive(Debug, Deserialize)]
struct JobRequest {
    id: String,
    payload: serde_json::Value,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let nats_url = std::env::var("NATS_URL").unwrap_or_else(|_| "127.0.0.1:4222".into());
    let subject = std::env::var("EXECUTOR_SUBJECT").unwrap_or_else(|_| "gpu.jobs".into());
    let ack_subject =
        std::env::var("EXECUTOR_ACK_SUBJECT").unwrap_or_else(|_| format!("{subject}.ack"));
    let queue_group =
        std::env::var("EXECUTOR_QUEUE_GROUP").unwrap_or_else(|_| "gpu-executors".into());
    let auth_token = std::env::var("NATS_AUTH_TOKEN").ok();

    init_metrics()?;

    let connection = NatsConnection::connect(&nats_url, "executor", auth_token.as_deref()).await?;
    let mut subscription = connection.queue_subscribe(&subject, &queue_group).await?;

    info!(url = %nats_url, %subject, %queue_group, "executor subscribed");

    process_loop(connection, &ack_subject, &mut subscription).await
}

async fn process_loop(
    connection: NatsConnection,
    ack_subject: &str,
    subscription: &mut NatsSubscription,
) -> Result<()> {
    while let Some(payload) = subscription.next().await {
        metrics::counter!("executor_jobs_received_total").increment(1);
        match serde_json::from_slice::<JobRequest>(&payload) {
            Ok(job) => {
                if let Err(err) = handle_job(&connection, ack_subject, job).await {
                    error!(error = %err, "xử lý job thất bại");
                    metrics::counter!("executor_jobs_failed_total").increment(1);
                }
            }
            Err(err) => {
                error!(error = %err, "deserialize job thất bại");
                metrics::counter!("executor_jobs_deserialize_error_total").increment(1);
            }
        }
    }

    Ok(())
}

async fn handle_job(connection: &NatsConnection, ack_subject: &str, job: JobRequest) -> Result<()> {
    info!(job_id = %job.id, payload = %job.payload, "job_received");
    let start = Instant::now();
    simulate_gpu_work().await;
    if let Err(err) = connection.publish(ack_subject, job.id.as_bytes()).await {
        metrics::counter!("executor_jobs_ack_error_total").increment(1);
        return Err(err);
    }
    info!(job_id = %job.id, ack_subject, "job_completed");
    metrics::counter!("executor_jobs_completed_total").increment(1);
    metrics::histogram!("executor_job_duration_seconds").record(start.elapsed().as_secs_f64());
    Ok(())
}

async fn simulate_gpu_work() {
    sleep(Duration::from_millis(500)).await;
}

static PROM_HANDLE: OnceCell<metrics_exporter_prometheus::PrometheusHandle> = OnceCell::new();

fn init_metrics() -> Result<()> {
    let addr: SocketAddr = std::env::var("EXECUTOR_METRICS_ADDR")
        .unwrap_or_else(|_| "0.0.0.0:9200".into())
        .parse()?;

    let handle = PrometheusBuilder::new()
        .with_http_listener(addr)
        .install_recorder()?;

    let _ = PROM_HANDLE.set(handle);
    Ok(())
}
