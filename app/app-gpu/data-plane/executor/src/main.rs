use serde::Deserialize;
use tokio::{
    sync::mpsc,
    time::{sleep, Duration},
};
use tracing::info;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[derive(Debug, Deserialize)]
struct JobRequest {
    id: String,
    payload: serde_json::Value,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let (tx, mut rx) = mpsc::channel::<JobRequest>(32);

    tokio::spawn(async move {
        let mut counter = 0u64;
        loop {
            counter += 1;
            let job = JobRequest {
                id: format!("demo-{}", counter),
                payload: serde_json::json!({"kind": "diagnostic"}),
            };
            if tx.send(job).await.is_err() {
                break;
            }
            sleep(Duration::from_secs(5)).await;
        }
    });

    while let Some(job) = rx.recv().await {
        process_job(job).await;
    }

    Ok(())
}

async fn process_job(job: JobRequest) {
    info!(job_id = %job.id, payload = %job.payload, "job_received");
    sleep(Duration::from_millis(500)).await;
    info!(job_id = %job.id, "job_completed");
}
