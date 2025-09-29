//! API Server Implementation
//!
//! **High-performance HTTP/WebSocket server** (Server HTTP/WebSocket hiệu suất cao)
//! Built with async/await patterns and comprehensive monitoring

use anyhow::{Context, Result};
use std::sync::Arc;
use tokio::{
    net::TcpListener,
    sync::{RwLock, broadcast},
    task::JoinHandle,
};
use tracing::{info, warn, error};

use crate::{
    gpu_mining::{MiningEngine, ThermalManager},
    resource_manager::ResourceManager,
    common::MetricsCollector,
    api::{endpoints::ApiRoutes, websocket::WebSocketHandler},
};

/// **Main API server** (Server API chính)
pub struct ApiServer {
    /// **Bind address** (Địa chỉ bind)
    bind_addr: String,
    /// **Server task handle** (Handle task server)
    server_handle: Option<JoinHandle<()>>,
    /// **Shutdown signal** (Tín hiệu tắt)
    shutdown_tx: Option<broadcast::Sender<()>>,
    /// **Mining engine reference** (Tham chiếu engine đào)
    mining_engine: Arc<RwLock<MiningEngine>>,
    /// **Thermal manager** (Quản lý nhiệt)
    thermal_manager: Arc<ThermalManager>,
    /// **Resource manager** (Quản lý tài nguyên)
    resource_manager: Arc<ResourceManager>,
    /// **Metrics collector** (Thu thập metrics)
    metrics_collector: Arc<MetricsCollector>,
}

impl ApiServer {
    /// **Create new API server** (Tạo server API mới)
    pub async fn new(
        bind_addr: &str,
        mining_engine: Arc<RwLock<MiningEngine>>,
        thermal_manager: Arc<ThermalManager>,
        resource_manager: Arc<ResourceManager>,
        metrics_collector: Arc<MetricsCollector>,
    ) -> Result<Self> {
        let (shutdown_tx, _) = broadcast::channel(1);

        Ok(Self {
            bind_addr: bind_addr.to_string(),
            server_handle: None,
            shutdown_tx: Some(shutdown_tx),
            mining_engine,
            thermal_manager,
            resource_manager,
            metrics_collector,
        })
    }

    /// **Start the API server** (Khởi động server API)
    pub async fn start(&mut self) -> Result<()> {
        if self.server_handle.is_some() {
            return Ok(()); // **Already running** (Đã chạy rồi)
        }

        let bind_addr = self.bind_addr.clone();
        let shutdown_rx = self.shutdown_tx.as_ref().unwrap().subscribe();

        // **Clone references for the server task** (Clone tham chiếu cho task server)
        let mining_engine = Arc::clone(&self.mining_engine);
        let thermal_manager = Arc::clone(&self.thermal_manager);
        let resource_manager = Arc::clone(&self.resource_manager);
        let metrics_collector = Arc::clone(&self.metrics_collector);

        let server_handle = tokio::spawn(async move {
            if let Err(e) = Self::run_server(
                &bind_addr,
                mining_engine,
                thermal_manager,
                resource_manager,
                metrics_collector,
                shutdown_rx,
            ).await {
                error!("API server error: {}", e);
            }
        });

        self.server_handle = Some(server_handle);
        info!("API server starting on {}", self.bind_addr);

        Ok(())
    }

    /// **Stop the API server** (Dừng server API)
    pub async fn stop(&self) -> Result<()> {
        if let Some(shutdown_tx) = &self.shutdown_tx {
            let _ = shutdown_tx.send(());
        }

        if let Some(handle) = &self.server_handle {
            handle.abort();
            info!("API server stopped");
        }

        Ok(())
    }

    /// **Internal server runner** (Bộ chạy server nội bộ)
    async fn run_server(
        bind_addr: &str,
        mining_engine: Arc<RwLock<MiningEngine>>,
        thermal_manager: Arc<ThermalManager>,
        resource_manager: Arc<ResourceManager>,
        metrics_collector: Arc<MetricsCollector>,
        mut shutdown_rx: broadcast::Receiver<()>,
    ) -> Result<()> {
        // **Create TCP listener** (Tạo TCP listener)
        let listener = TcpListener::bind(bind_addr).await
            .with_context(|| format!("Failed to bind to {}", bind_addr))?;

        info!("API server listening on {}", bind_addr);

        // **Initialize API routes** (Khởi tạo routes API)
        let api_routes = ApiRoutes::new(
            Arc::clone(&mining_engine),
            Arc::clone(&thermal_manager),
            Arc::clone(&resource_manager),
            Arc::clone(&metrics_collector),
        );

        // **Initialize WebSocket handler** (Khởi tạo handler WebSocket)
        let ws_handler = WebSocketHandler::new(
            Arc::clone(&mining_engine),
            Arc::clone(&thermal_manager),
            Arc::clone(&resource_manager),
            Arc::clone(&metrics_collector),
        );

        // **Main server loop** (Vòng lặp chính server)
        loop {
            tokio::select! {
                // **Accept new connections** (Chấp nhận kết nối mới)
                result = listener.accept() => {
                    match result {
                        Ok((stream, addr)) => {
                            info!("New connection from {}", addr);

                            let api_routes = api_routes.clone();
                            let ws_handler = ws_handler.clone();

                            tokio::spawn(async move {
                                if let Err(e) = Self::handle_connection(stream, api_routes, ws_handler).await {
                                    error!("Connection handling error: {}", e);
                                }
                            });
                        }
                        Err(e) => {
                            error!("Failed to accept connection: {}", e);
                        }
                    }
                }

                // **Shutdown signal received** (Nhận tín hiệu tắt)
                _ = shutdown_rx.recv() => {
                    info!("Shutdown signal received, stopping server");
                    break;
                }
            }
        }

        Ok(())
    }

    /// **Handle individual connection** (Xử lý kết nối riêng lẻ)
    async fn handle_connection(
        stream: tokio::net::TcpStream,
        api_routes: ApiRoutes,
        ws_handler: WebSocketHandler,
    ) -> Result<()> {
        use tokio_tungstenite::{accept_async, tungstenite::Message};
        use futures::{StreamExt, SinkExt};

        // **Try to upgrade to WebSocket** (Thử nâng cấp lên WebSocket)
        match accept_async(stream).await {
            Ok(ws_stream) => {
                info!("WebSocket connection established");

                let (mut ws_sender, mut ws_receiver) = ws_stream.split();

                // **Handle WebSocket messages** (Xử lý tin nhắn WebSocket)
                while let Some(msg) = ws_receiver.next().await {
                    match msg {
                        Ok(Message::Text(text)) => {
                            match ws_handler.handle_message(&text).await {
                                Ok(response) => {
                                    if let Err(e) = ws_sender.send(Message::Text(response)).await {
                                        error!("Failed to send WebSocket response: {}", e);
                                        break;
                                    }
                                }
                                Err(e) => {
                                    error!("WebSocket message handling error: {}", e);
                                    let error_msg = format!("{{\"error\": \"{}\"}}", e);
                                    let _ = ws_sender.send(Message::Text(error_msg)).await;
                                }
                            }
                        }
                        Ok(Message::Close(_)) => {
                            info!("WebSocket connection closed by client");
                            break;
                        }
                        Ok(Message::Ping(data)) => {
                            let _ = ws_sender.send(Message::Pong(data)).await;
                        }
                        Err(e) => {
                            error!("WebSocket error: {}", e);
                            break;
                        }
                        _ => {}
                    }
                }

                Ok(())
            }
            Err(_) => {
                // **Handle as HTTP request** (Xử lý như HTTP request)
                warn!("HTTP connections not implemented yet");
                Ok(())
            }
        }
    }

    /// **Get server status** (Lấy trạng thái server)
    pub fn is_running(&self) -> bool {
        self.server_handle.is_some()
    }

    /// **Get bind address** (Lấy địa chỉ bind)
    pub fn bind_address(&self) -> &str {
        &self.bind_addr
    }
}

impl Drop for ApiServer {
    fn drop(&mut self) {
        if let Some(handle) = &self.server_handle {
            handle.abort();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::common::Config;

    #[tokio::test]
    async fn test_api_server_creation() {
        // **Create mock dependencies** (Tạo phụ thuộc giả)
        let config = Config::default();

        let metrics = Arc::new(MetricsCollector::new(&config.metrics).unwrap());
        let thermal_manager = Arc::new(ThermalManager::new(&config.thermal).await.unwrap());
        let resource_manager = Arc::new(ResourceManager::new(&config.resources).await.unwrap());
        let mining_engine = Arc::new(RwLock::new(MiningEngine::new(&config.mining, thermal_manager.clone(), resource_manager.clone(), metrics.clone()).await.unwrap()));

        let api_server = ApiServer::new(
            "127.0.0.1:0", // **Use port 0 for testing** (Dùng port 0 để test)
            mining_engine,
            thermal_manager,
            resource_manager,
            metrics,
        ).await;

        assert!(api_server.is_ok());
        let server = api_server.unwrap();
        assert!(!server.is_running());
    }
}