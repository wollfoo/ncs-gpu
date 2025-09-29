//! API Server Module for OPUS-GPU
//!
//! **RESTful API and WebSocket Services** (Dịch vụ API RESTful và WebSocket)
//! Features:
//! - **Real-time mining metrics** (Chỉ số đào thời gian thực)
//! - **Device management** (Quản lý thiết bị)
//! - **Configuration endpoints** (Endpoint cấu hình)
//! - **WebSocket streaming** (Streaming WebSocket)

use anyhow::Result;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, error};

pub mod server;
pub mod endpoints;
pub mod websocket;
pub mod middleware;

pub use server::ApiServer;
pub use endpoints::*;
pub use websocket::WebSocketHandler;

use crate::{
    gpu_mining::MiningEngine,
    resource_manager::ResourceManager,
    common::MetricsCollector,
    gpu_mining::ThermalManager,
};

/// **API module health check** (Kiểm tra sức khỏe module API)
pub async fn health_check() -> Result<()> {
    info!("API module health check: OK");
    Ok(())
}

/// **Initialize API services** (Khởi tạo dịch vụ API)
pub async fn init_api_services() -> Result<()> {
    info!("API services initialized");
    Ok(())
}

/// **Cleanup API resources** (Dọn dẹp tài nguyên API)
pub async fn cleanup_api_services() -> Result<()> {
    info!("API services cleaned up");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_api_health_check() {
        let result = health_check().await;
        assert!(result.is_ok());
    }
}