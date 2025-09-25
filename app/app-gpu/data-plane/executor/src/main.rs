use std::{
    collections::HashMap,
    net::SocketAddr,
    path::{Path, PathBuf},
    process::Stdio,
};

use anyhow::{anyhow, Context, Result};
use base64::engine::general_purpose::STANDARD as BASE64_STANDARD;
use base64::Engine;
use job_core::{DynJobStore, JobPayload, JobResult, JobStatus, JobStoreBuilder, JobUpdate};
use metrics_exporter_prometheus::PrometheusBuilder;
use nats_lite::{NatsConnection, NatsSubscription};
use once_cell::sync::OnceCell;
use serde::Deserialize;
use tokio::{io::AsyncWriteExt, process::Command, time::Instant};
use tracing::{error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[derive(Debug, Deserialize)]
struct JobRequest {
    id: String,
    payload: serde_json::Value,
}

struct ExecutionPlan {
    command: PathBuf,
    args: Vec<String>,
    env: HashMap<String, String>,
    stdin: Option<Vec<u8>>,
}

struct ExecutionOutput {
    result: JobResult,
    duration_secs: f64,
    success: bool,
    error: Option<String>,
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
    let store = JobStoreBuilder::from_env().build().await?;

    info!(url = %nats_url, %subject, %queue_group, "executor subscribed");

    process_loop(connection, &ack_subject, &mut subscription, store).await
}

async fn process_loop(
    connection: NatsConnection,
    ack_subject: &str,
    subscription: &mut NatsSubscription,
    store: DynJobStore,
) -> Result<()> {
    while let Some(payload) = subscription.next().await {
        metrics::counter!("executor_jobs_received_total").increment(1);
        match serde_json::from_slice::<JobRequest>(&payload) {
            Ok(job) => {
                if let Err(err) = handle_job(&connection, ack_subject, store.clone(), job).await {
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

async fn handle_job(
    connection: &NatsConnection,
    ack_subject: &str,
    store: DynJobStore,
    job: JobRequest,
) -> Result<()> {
    info!(job_id = %job.id, "job_received");

    let payload = match JobPayload::try_from(job.payload) {
        Ok(payload) => payload,
        Err(err) => {
            metrics::counter!("executor_jobs_invalid_payload_total").increment(1);
            error!(job_id = %job.id, error = ?err, "payload không hợp lệ tại executor");
            let update = JobUpdate {
                status: JobStatus::Failed,
                result: None,
                error: Some(format!("payload invalid: {err}")),
                duration_secs: None,
            };
            if let Err(store_err) = store.update_job(&job.id, update).await {
                warn!(job_id = %job.id, error = ?store_err, "không thể cập nhật job failed sau khi payload invalid");
            }
            return Ok(());
        }
    };

    if let Err(err) = store.update_job(&job.id, JobUpdate::running()).await {
        metrics::counter!("executor_jobs_store_error_total").increment(1);
        warn!(job_id = %job.id, error = ?err, "không thể đánh dấu job đang chạy");
    }

    let plan = match resolve_plan(&payload) {
        Ok(plan) => plan,
        Err(err) => {
            metrics::counter!("executor_jobs_invalid_payload_total").increment(1);
            error!(job_id = %job.id, error = %err, "không tạo được execution plan");
            let update = JobUpdate {
                status: JobStatus::Failed,
                result: None,
                error: Some(err.to_string()),
                duration_secs: None,
            };
            if let Err(store_err) = store.update_job(&job.id, update).await {
                warn!(job_id = %job.id, error = ?store_err, "không thể cập nhật job failed sau khi tạo plan thất bại");
            }
            publish_ack(
                connection,
                ack_subject,
                &job.id,
                JobStatus::Failed,
                None,
                Some(&err.to_string()),
            )
            .await?;
            return Ok(());
        }
    };

    info!(job_id = %job.id, command = %plan.command.display(), args = ?plan.args, "gpu_job_start");

    let execution = match execute_plan(&plan).await {
        Ok(output) => output,
        Err(err) => {
            metrics::counter!("executor_jobs_gpu_error_total").increment(1);
            error!(job_id = %job.id, error = %err, "GPU job không thể chạy");
            let update = JobUpdate {
                status: JobStatus::Failed,
                result: None,
                error: Some(err.to_string()),
                duration_secs: None,
            };
            if let Err(store_err) = store.update_job(&job.id, update).await {
                warn!(job_id = %job.id, error = ?store_err, "không thể cập nhật store sau GPU error");
            }
            publish_ack(
                connection,
                ack_subject,
                &job.id,
                JobStatus::Failed,
                None,
                Some(&err.to_string()),
            )
            .await?;
            return Ok(());
        }
    };

    if execution.success {
        metrics::counter!("executor_jobs_completed_total").increment(1);
        metrics::histogram!("executor_job_duration_seconds").record(execution.duration_secs);
        let update = JobUpdate::succeeded(execution.result.clone(), execution.duration_secs);
        if let Err(err) = store.update_job(&job.id, update).await {
            metrics::counter!("executor_jobs_store_error_total").increment(1);
            warn!(job_id = %job.id, error = ?err, "không thể cập nhật trạng thái thành công");
        }
        info!(
            job_id = %job.id,
            duration_secs = execution.duration_secs,
            exit_code = ?execution.result.exit_code,
            "job_completed"
        );
        publish_ack(
            connection,
            ack_subject,
            &job.id,
            JobStatus::Succeeded,
            Some(execution.duration_secs),
            None,
        )
        .await?;
    } else {
        metrics::counter!("executor_jobs_failed_total").increment(1);
        let update = JobUpdate {
            status: JobStatus::Failed,
            result: Some(execution.result.clone()),
            error: execution.error.clone(),
            duration_secs: Some(execution.duration_secs),
        };
        if let Err(err) = store.update_job(&job.id, update).await {
            metrics::counter!("executor_jobs_store_error_total").increment(1);
            warn!(job_id = %job.id, error = ?err, "không thể cập nhật trạng thái failed");
        }
        error!(
            job_id = %job.id,
            duration_secs = execution.duration_secs,
            error = ?execution.error,
            exit_code = ?execution.result.exit_code,
            "gpu job trả về thất bại"
        );
        publish_ack(
            connection,
            ack_subject,
            &job.id,
            JobStatus::Failed,
            Some(execution.duration_secs),
            execution.error.as_deref(),
        )
        .await?;
    }

    Ok(())
}

fn resolve_plan(payload: &JobPayload) -> Result<ExecutionPlan> {
    let base_path = std::env::var("GPU_KERNEL_BASE_PATH").ok();
    let mut command = PathBuf::from(&payload.kernel);
    if command.as_os_str().is_empty() {
        return Err(anyhow!("kernel không hợp lệ (rỗng)"));
    }
    if command.is_relative() {
        if let Some(base) = base_path {
            command = Path::new(&base).join(&command);
        }
    }

    let stdin = if let Some(text) = &payload.stdin {
        Some(text.as_bytes().to_vec())
    } else if let Some(value) = payload.extra.get("stdin_base64") {
        let encoded = value
            .as_str()
            .ok_or_else(|| anyhow!("stdin_base64 phải là string"))?;
        Some(
            BASE64_STANDARD
                .decode(encoded)
                .map_err(|err| anyhow!("stdin_base64 decode thất bại: {err}"))?,
        )
    } else {
        None
    };

    Ok(ExecutionPlan {
        command,
        args: payload.args.clone(),
        env: payload.env.clone(),
        stdin,
    })
}

async fn execute_plan(plan: &ExecutionPlan) -> Result<ExecutionOutput> {
    let mut command = Command::new(&plan.command);
    command.args(&plan.args);
    command.kill_on_drop(true);
    if plan.stdin.is_some() {
        command.stdin(Stdio::piped());
    } else {
        command.stdin(Stdio::null());
    }
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    command.envs(plan.env.iter());

    let mut child = command
        .spawn()
        .with_context(|| format!("không thể spawn GPU command {}", plan.command.display()))?;

    if let Some(stdin_bytes) = &plan.stdin {
        if let Some(mut stdin) = child.stdin.take() {
            stdin
                .write_all(stdin_bytes)
                .await
                .context("ghi stdin cho GPU job thất bại")?;
        } else {
            warn!(command = %plan.command.display(), "stdin không khả dụng dù dữ liệu đã cung cấp");
        }
    }

    let start = Instant::now();
    let output = child
        .wait_with_output()
        .await
        .context("không chờ được GPU job hoàn thành")?;
    let duration_secs = start.elapsed().as_secs_f64();

    let stdout = normalize_output(&output.stdout);
    let stderr = normalize_output(&output.stderr);
    let result = JobResult {
        stdout,
        stderr,
        exit_code: output.status.code(),
    };
    let success = output.status.success();
    let error = if success {
        None
    } else if let Some(code) = output.status.code() {
        Some(format!("process exited with status {code}"))
    } else {
        Some("process terminated by signal".to_string())
    };

    Ok(ExecutionOutput {
        result,
        duration_secs,
        success,
        error,
    })
}

fn normalize_output(bytes: &[u8]) -> Option<String> {
    if bytes.is_empty() {
        None
    } else {
        Some(String::from_utf8_lossy(bytes).to_string())
    }
}

async fn publish_ack(
    connection: &NatsConnection,
    ack_subject: &str,
    job_id: &str,
    status: JobStatus,
    duration_secs: Option<f64>,
    error: Option<&str>,
) -> Result<()> {
    let payload = serde_json::json!({
        "id": job_id,
        "status": status_label(&status),
        "duration_secs": duration_secs,
        "error": error,
    });
    let bytes = serde_json::to_vec(&payload)?;
    if let Err(err) = connection.publish(ack_subject, &bytes).await {
        metrics::counter!("executor_jobs_ack_error_total").increment(1);
        return Err(err);
    }
    Ok(())
}

fn status_label(status: &JobStatus) -> &'static str {
    match status {
        JobStatus::Queued => "queued",
        JobStatus::Running => "running",
        JobStatus::Succeeded => "succeeded",
        JobStatus::Failed => "failed",
    }
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
