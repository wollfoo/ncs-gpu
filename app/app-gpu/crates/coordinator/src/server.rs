use std::net::SocketAddr;
use tonic::{transport::Server, Request, Response, Status};
use tracing::info;

use crate::scheduler::TaskScheduler;
use crate::worker_registry::WorkerRegistry;

/// **[Coordinator Server]** (Máy chủ điều phối – gRPC API server)
pub struct CoordinatorServer {
    scheduler: TaskScheduler,
    worker_registry: WorkerRegistry,
}

impl CoordinatorServer {
    pub fn new(scheduler: TaskScheduler, worker_registry: WorkerRegistry) -> Self {
        Self {
            scheduler,
            worker_registry,
        }
    }
    
    /// **[Serve]** (Chạy server – khởi động gRPC server)
    pub async fn serve(self, addr: SocketAddr) -> Result<(), Box<dyn std::error::Error>> {
        info!("🌐 Starting gRPC server on {}", addr);
        
        // TODO: Implement actual gRPC service với proto definitions
        // Hiện tại chỉ là placeholder để demo structure
        
        // Ví dụ:
        // Server::builder()
        //     .add_service(CoordinatorServiceServer::new(self))
        //     .serve(addr)
        //     .await?;
        
        // Tạm thời chỉ log và keep-alive
        info!("✅ gRPC server ready (placeholder - cần implement proto service)");
        
        // Keep server alive
        tokio::signal::ctrl_c().await?;
        info!("🛑 Shutting down server...");
        
        Ok(())
    }
}

// TODO: Implement gRPC service traits
// #[tonic::async_trait]
// impl CoordinatorService for CoordinatorServer {
//     async fn submit_task(
//         &self,
//         request: Request<SubmitTaskRequest>,
//     ) -> Result<Response<SubmitTaskResponse>, Status> {
//         // Implementation
//     }
// }
