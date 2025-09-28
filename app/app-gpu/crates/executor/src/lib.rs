pub mod proto {
    tonic::include_proto!("executor.v1");
}

use anyhow::Result;
use proto::executor_server::{Executor, ExecutorServer};
use proto::{ExecuteJobRequest, ExecuteJobResponse};
use std::net::SocketAddr;
use std::process::Stdio;
use std::sync::Arc;
use std::time::Instant;
use thiserror::Error;
use tokio::process::Command;
use tokio::sync::oneshot;
use tokio::task::JoinHandle;
use tonic::{transport::Server, Request, Response, Status};

#[derive(Clone, Debug)]
pub struct SandboxConfig {
    pub allowed_env: Vec<(String, String)>,
    pub working_dir: Option<String>,
}

impl Default for SandboxConfig {
    fn default() -> Self {
        Self {
            allowed_env: vec![
                ("PATH".to_string(), std::env::var("PATH").unwrap_or_default()),
            ],
            working_dir: None,
        }
    }
}

#[derive(Clone)]
pub struct ExecutorService {
    sandbox: Arc<SandboxConfig>,
}

#[derive(Debug, Error)]
pub enum ExecutorError {
    #[error("command missing in ExecuteJobRequest")]
    MissingCommand,
}

impl ExecutorService {
    pub fn new(config: SandboxConfig) -> Self {
        Self {
            sandbox: Arc::new(config),
        }
    }

    fn prepare_command(&self, request: &ExecuteJobRequest) -> Result<Command, ExecutorError> {
        let mut iter = request.command.iter();
        let binary = iter.next().ok_or(ExecutorError::MissingCommand)?;
        let mut command = Command::new(binary);
        command.args(iter);
        command.stdin(Stdio::null());
        command.stdout(Stdio::piped());
        command.stderr(Stdio::piped());
        command.env_clear();

        for (key, value) in &self.sandbox.allowed_env {
            command.env(key, value);
        }

        if let Some(dir) = &self.sandbox.working_dir {
            command.current_dir(dir);
        }

        Ok(command)
    }
}

#[tonic::async_trait]
impl Executor for ExecutorService {
    async fn execute_job(
        &self,
        request: Request<ExecuteJobRequest>,
    ) -> Result<Response<ExecuteJobResponse>, Status> {
        let inner = request.into_inner();
        let mut command = self
            .prepare_command(&inner)
            .map_err(|err| Status::invalid_argument(err.to_string()))?;

        // Bảo vệ: loại bỏ LD_PRELOAD nếu người gọi truyền vào.
        command.env_remove("LD_PRELOAD");

        let start = Instant::now();
        let output = command
            .output()
            .await
            .map_err(|err| Status::internal(format!("spawn error: {err}")))?;
        let duration = start.elapsed();

        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let exit_code = output.status.code().unwrap_or_default();

        let response = ExecuteJobResponse {
            job_id: inner.job_id,
            exit_code,
            stdout,
            stderr,
            duration_ms: duration.as_secs_f64() * 1000.0,
        };

        Ok(Response::new(response))
    }
}

pub struct ExecutorHandle {
    shutdown: Option<oneshot::Sender<()>>,
    join: JoinHandle<Result<(), tonic::transport::Error>>,
}

impl ExecutorHandle {
    pub async fn shutdown(mut self) {
        if let Some(tx) = self.shutdown.take() {
            let _ = tx.send(());
        }
        let _ = self.join.await;
    }
}

/// Khởi động gRPC executor server.
pub async fn serve(addr: SocketAddr, service: ExecutorService) -> Result<ExecutorHandle> {
    let (shutdown_tx, shutdown_rx) = oneshot::channel::<()>();

    let join = tokio::spawn(async move {
        Server::builder()
            .add_service(ExecutorServer::new(service))
            .serve_with_shutdown(addr, async move {
                let _ = shutdown_rx.await;
            })
            .await
    });

    Ok(ExecutorHandle {
        shutdown: Some(shutdown_tx),
        join,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use proto::executor_client::ExecutorClient;
    use tokio::time::timeout;
    use std::time::Duration;

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn execute_job_runs_command_without_ld_preload() {
        let std_listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = std_listener.local_addr().unwrap();
        drop(std_listener);

        let handle = serve(addr, ExecutorService::new(SandboxConfig::default()))
            .await
            .unwrap();

        // Client
        let mut client = ExecutorClient::connect(format!("http://{}", addr))
            .await
            .unwrap();

        // Command in sandbox prints LD_PRELOAD (should be empty)
        let request = ExecuteJobRequest {
            job_id: "test-job".into(),
            command: vec!["/bin/sh".into(), "-c".into(), "printf '%s' \"$LD_PRELOAD\"".into()],
            batch_size: 1,
        };

        let response = timeout(Duration::from_secs(2), client.execute_job(request))
            .await
            .unwrap()
            .unwrap()
            .into_inner();

        assert_eq!(response.exit_code, 0);
        assert!(response.stdout.is_empty(), "LD_PRELOAD leaked: {}", response.stdout);
        assert!(response.duration_ms >= 0.0);

        handle.shutdown().await;
    }
}
