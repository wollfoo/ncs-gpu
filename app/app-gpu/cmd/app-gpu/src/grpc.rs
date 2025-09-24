use app_gpu_domain::config::AppConfig;
use app_gpu_domain::proto::{scheduler_server::Scheduler as SchedulerRpc, scheduler_server::SchedulerServer, ScheduleRequest, ScheduleResponse};
use app_gpu_scheduler::SchedulerHandle;
use std::net::SocketAddr;
use tokio::task::JoinHandle;
use tonic::{transport::Server, Request, Response, Status};
use tracing::info;

pub struct GrpcServer {
    join: JoinHandle<()>,
}

impl GrpcServer {
    pub async fn graceful_shutdown(self) {
        if let Err(err) = self.join.await {
            tracing::warn!(target = "grpc", ?err, "gRPC server join failed");
        }
    }
}

pub fn serve(config: AppConfig, handle: SchedulerHandle) -> GrpcServer {
    let addr: SocketAddr = config.api.grpc_bind.parse().expect("invalid gRPC bind address");
    let shutdown_handle = handle.clone();
    let service = SchedulerService { handle };

    let join = tokio::spawn(async move {
        info!(target: "grpc", "listening", %addr);
        Server::builder()
            .add_service(SchedulerServer::new(service))
            .serve_with_shutdown(addr, async move {
                shutdown_handle.shutdown_notifier().await;
            })
            .await
            .expect("gRPC server failed");
    });

    GrpcServer { join }
}

struct SchedulerService {
    handle: SchedulerHandle,
}

#[tonic::async_trait]
impl SchedulerRpc for SchedulerService {
    async fn submit_job(&self, request: Request<ScheduleRequest>) -> Result<Response<ScheduleResponse>, Status> {
        let payload = request.into_inner();
        let spec = app_gpu_domain::JobSpec {
            wallet: payload.wallet,
            pool_endpoint: payload.pool_endpoint,
            gpu_index: payload.gpu_index as u8,
            dag_location: payload.dag_location,
        };
        let job_id = self
            .handle
            .schedule(spec)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(ScheduleResponse { job_id }))
    }
}
