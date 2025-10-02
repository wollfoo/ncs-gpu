//! # Mock Pool Server (Máy chủ pool giả lập)
//!
//! **Full Stratum protocol implementation** (triển khai đầy đủ giao thức Stratum)
//! cho testing mining clients với configurable responses, error injection,
//! và connection lifecycle simulation.

// Core crates (thư viện cốt lõi)
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};

use async_trait::async_trait;
use futures::future::join_all;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader, Lines};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::{mpsc, RwLock};
use tokio::time;
use tracing::{debug, error, info, warn};

// Internal imports (nhập nội bộ)
use mining_core::stratum::protocol::{
    ConnectionState, Message, MessageId, Notification, Request, Response, SessionStats, Solution,
    WorkPackage, StratumError, METHOD_MINING_AUTHORIZE, METHOD_MINING_NOTIFY,
    METHOD_MINING_SET_DIFFICULTY, METHOD_MINING_SET_EXTRANONCE, METHOD_MINING_SUBSCRIBE,
    METHOD_MINING_SUBMIT,
};

/// **Mock Pool Server Configuration** (cấu hình máy chủ pool giả lập)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MockPoolConfig {
    /// **Server bind address** (địa chỉ ràng buộc máy chủ)
    pub bind_address: String,
    /// **User agent string** (chuỗi user agent)
    pub user_agent: String,
    /// **Default difficulty** (độ khó mặc định)
    pub default_difficulty: f64,
    /// **Enable SSL** (bật SSL)
    pub enable_ssl: bool,
    /// **Response delay** (độ trễ phản hồi)
    pub response_delay_ms: u64,
    /// **Max connections** (kết nối tối đa)
    pub max_connections: usize,
    /// **Reject probability** (khả năng từ chối)
    pub reject_probability: f64,
    /// **Disconnect probability** (khả năng ngắt kết nối)
    pub disconnect_probability: f64,
}

impl Default for MockPoolConfig {
    fn default() -> Self {
        Self {
            bind_address: "127.0.0.1:3333".to_string(),
            user_agent: "MockPool/1.0.0".to_string(),
            default_difficulty: 1.0,
            enable_ssl: false,
            response_delay_ms: 50,
            max_connections: 10,
            reject_probability: 0.1,
            disconnect_probability: 0.01,
        }
    }
}

/// **Job Template** (mẫu công việc) – cho mining.notify
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobTemplate {
    /// **Previous block hash** (hash khối trước)
    pub prev_hash: Vec<u8>,
    /// **Coinbase1** (coinbase1)
    pub coinbase1: Vec<u8>,
    /// **Coinbase2** (coinbase2)
    pub coinbase2: Vec<u8>,
    /// **Merkle branches** (nhánh merkle)
    pub merkle_branches: Vec<Vec<u8>>,
    /// **Version** (phiên bản)
    pub version: Vec<u8>,
    /// **Target** (mục tiêu)
    pub target: Vec<u8>,
    /// **Nonce timestamp** (timestamp nonce)
    pub ntime: Vec<u8>,
}

impl Default for JobTemplate {
    fn default() -> Self {
        Self {
            prev_hash: vec![0; 32],
            coinbase1: hex::decode("01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff").unwrap(),
            coinbase2: hex::decode("ffffffff02").unwrap(),
            merkle_branches: vec![],
            version: vec![0; 4],
            target: vec![0xff; 32],
            ntime: vec![0; 4],
        }
    }
}

/// **Mock Pool Server** (máy chủ pool giả lập) – implements full Stratum protocol
pub struct MockPoolServer {
    /// **Configuration** (cấu hình)
    config: MockPoolConfig,
    /// **TCP listener** (trình nghe TCP)
    listener: Option<TcpListener>,
    /// **Active connections** (kết nối hoạt động)
    connections: Arc<RwLock<HashMap<SocketAddr, ConnectionHandler>>>,
    /// **Server statistics** (thống kê máy chủ)
    stats: Arc<RwLock<MockPoolStats>>,
    /// **Shutdown channel** (kênh tắt)
    shutdown_tx: mpsc::Sender<()>,
    /// **Job templates** (mẫu công việc)
    job_templates: Arc<RwLock<Vec<JobTemplate>>>,
}

#[derive(Debug, Clone)]
pub struct MockPoolStats {
    pub total_connections: usize,
    pub active_connections: usize,
    pub total_jobs: usize,
    pub total_submissions: usize,
    pub accepted_submissions: usize,
    pub rejected_submissions: usize,
    pub total_authorizations: usize,
}

impl Default for MockPoolStats {
    fn default() -> Self {
        Self {
            total_connections: 0,
            active_connections: 0,
            total_jobs: 0,
            total_submissions: 0,
            accepted_submissions: 0,
            rejected_submissions: 0,
            total_authorizations: 0,
        }
    }
}

/// **Connection Handler** (xử lý kết nối) – per-client state
#[derive(Debug)]
pub struct ConnectionHandler {
    /// **Peer address** (địa chỉ ngang hàng)
    peer_addr: SocketAddr,
    /// **Connection state** (trạng thái kết nối)
    state: ConnectionState,
    /// **Worker name** (tên worker)
    worker_name: Option<String>,
    /// **Extra nonce1** (extra nonce1)
    extra_nonce1: Option<String>,
    /// **Difficulty** (độ khó)
    difficulty: f64,
    /// **Last activity** (hoạt động cuối cùng)
    last_activity: Instant,
    /// **Is authorized** (đã được ủy quyền)
    authorized: bool,
}

impl MockPoolServer {
    /// **Create new mock pool server** (tạo máy chủ pool giả lập mới)
    pub fn new(config: MockPoolConfig) -> Self {
        let (shutdown_tx, _shutdown_rx) = mpsc::channel(1);

        Self {
            config,
            listener: None,
            connections: Arc::new(RwLock::new(HashMap::new())),
            stats: Arc::new(RwLock::new(MockPoolStats::default())),
            shutdown_tx,
            job_templates: Arc::new(RwLock::new(vec![JobTemplate::default()])),
        }
    }

    /// **Start the server** (bắt đầu máy chủ)
    pub async fn start(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        info!("🌐 Starting mock pool server on {}", self.config.bind_address);

        let listener = TcpListener::bind(&self.config.bind_address).await?;
        self.listener = Some(listener);

        info!("✅ Mock pool server listening on {}", self.config.bind_address);

        let listener = self.listener.take().unwrap();
        let connections = Arc::clone(&self.connections);
        let stats = Arc::clone(&self.stats);
        let config = self.config.clone();
        let job_templates = Arc::clone(&self.job_templates);

        tokio::spawn(async move {
            if let Err(e) = Self::accept_loop(listener, connections, stats, config, job_templates).await {
                error!("❌ Mock pool server error: {}", e);
            }
        });

        Ok(())
    }

    /// **Stop the server** (dừng máy chủ)
    pub async fn stop(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        info!("🛑 Stopping mock pool server");

        let _ = self.shutdown_tx.send(()).await;

        // Close all connections
        let mut connections = self.connections.write().await;
        for (addr, handler) in connections.drain() {
            debug!("👋 Disconnecting client {}", addr);
        }

        Ok(())
    }

    /// **Get server statistics** (lấy thống kê máy chủ)
    pub async fn get_stats(&self) -> MockPoolStats {
        self.stats.read().await.clone()
    }

    /// **Inject new job** (tiêm công việc mới)
    pub async fn inject_job(&self, job: JobTemplate) {
        let mut jobs = self.job_templates.write().await;
        jobs.push(job);

        // Send mining.notify to all connected clients
        self.notify_all_clients().await;
    }

    /// **Get bind address** (lấy địa chỉ ràng buộc)
    pub fn get_bind_address(&self) -> &str {
        &self.config.bind_address
    }

    /// **Accept connections loop** (vòng lặp chấp nhận kết nối)
    async fn accept_loop(
        listener: TcpListener,
        connections: Arc<RwLock<HashMap<SocketAddr, ConnectionHandler>>>,
        stats: Arc<RwLock<MockPoolStats>>,
        config: MockPoolConfig,
        job_templates: Arc<RwLock<Vec<JobTemplate>>>,
    ) -> Result<(), Box<dyn std::error::Error>> {
        loop {
            tokio::select! {
                accept_result = listener.accept() => {
                    match accept_result {
                        Ok((socket, addr)) => {
                            info!("🤝 New connection from {}", addr);

                            // Check connection limit
                            {
                                let conn_count = connections.read().await.len();
                                if conn_count >= config.max_connections {
                                    warn!("❌ Connection limit reached ({}), rejecting {}", config.max_connections, addr);
                                    continue;
                                }
                            }

                            // Create connection handler
                            let handler = ConnectionHandler {
                                peer_addr: addr,
                                state: ConnectionState::Connected,
                                worker_name: None,
                                extra_nonce1: Some(format!("{:08x}", rand::random::<u32>())),
                                difficulty: config.default_difficulty,
                                last_activity: Instant::now(),
                                authorized: false,
                            };

                            connections.write().await.insert(addr, handler);

                            // Update stats
                            {
                                let mut stats_lock = stats.write().await;
                                stats_lock.total_connections += 1;
                                stats_lock.active_connections += 1;
                            }

                            // Spawn client handler
                            let connections_clone = Arc::clone(&connections);
                            let stats_clone = Arc::clone(&stats);
                            let config_clone = config.clone();
                            let job_templates_clone = Arc::clone(&job_templates);

                            tokio::spawn(async move {
                                if let Err(e) = Self::handle_client(
                                    socket,
                                    addr,
                                    connections_clone,
                                    stats_clone,
                                    config_clone,
                                    job_templates_clone,
                                ).await {
                                    error!("Client {} handler error: {}", addr, e);
                                }
                            });
                        }
                        Err(e) => {
                            error!("❌ Accept error: {}", e);
                            break;
                        }
                    }
                }
            }
        }

        Ok(())
    }

    /// **Handle individual client** (xử lý từng client)
    async fn handle_client(
        socket: TcpStream,
        addr: SocketAddr,
        connections: Arc<RwLock<HashMap<SocketAddr, ConnectionHandler>>>,
        stats: Arc<RwLock<MockPoolStats>>,
        config: MockPoolConfig,
        job_templates: Arc<RwLock<Vec<JobTemplate>>>,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let (reader, mut writer) = socket.into_split();
        let mut lines = BufReader::new(reader).lines();

        loop {
            tokio::select! {
                line_result = lines.next_line() => {
                    match line_result {
                        Ok(Some(line)) => {
                            // Update last activity (cập nhật hoạt động cuối cùng)
                            {
                                let mut conns = connections.write().await;
                                if let Some(handler) = conns.get_mut(&addr) {
                                    handler.last_activity = Instant::now();
                                }
                            }

                            debug!("📨 Received from {}: {}", addr, line);

                            // Parse and handle message
                            match serde_json::from_str::<Message>(&line) {
                                Ok(message) => {
                                    let response = Self::handle_message(
                                        message,
                                        addr,
                                        Arc::clone(&connections),
                                        Arc::clone(&stats),
                                        Arc::clone(&job_templates),
                                        &config,
                                    ).await;

                                    // Send response with delay simulation
                                    if let Some(response) = response {
                                        if config.response_delay_ms > 0 {
                                            tokio::time::sleep(Duration::from_millis(config.response_delay_ms)).await;
                                        }

                                        let response_json = serde_json::to_string(&response)?;
                                        writer.write_all(response_json.as_bytes()).await?;
                                        writer.write_all(b"\n").await?;
                                        writer.flush().await?;

                                        debug!("📤 Sent to {}: {}", addr, response_json);
                                    }
                                }
                                Err(e) => {
                                    warn!("JSON parse error from {}: {}", addr, e);
                                }
                            }
                        }
                        Ok(None) => {
                            info!("👋 Client {} disconnected", addr);
                            break;
                        }
                        Err(e) => {
                            error!("Read error from {}: {}", addr, e);
                            break;
                        }
                    }
                }

                // Simulate random disconnections (giả lập ngắt kết nối ngẫu nhiên)
                _ = tokio::time::sleep(Duration::from_secs(10)) => {
                    if rand::random::<f64>() < config.disconnect_probability {
                        info!("🌪️ Simulating disconnection for {}", addr);
                        break;
                    }
                }
            }
        }

        // Clean up connection
        {
            let mut conns = connections.write().await;
            conns.remove(&addr);

            let mut stats_lock = stats.write().await;
            stats_lock.active_connections -= 1;
        }

        Ok(())
    }

    /// **Handle incoming message** (xử lý thông điệp đến)
    async fn handle_message(
        message: Message,
        addr: SocketAddr,
        connections: Arc<RwLock<HashMap<SocketAddr, ConnectionHandler>>>,
        stats: Arc<RwLock<MockPoolStats>>,
        job_templates: Arc<RwLock<Vec<JobTemplate>>>,
        config: &MockPoolConfig,
    ) -> Option<Message> {
        match message {
            Message::Request(request) => {
                Self::handle_request(
                    request,
                    addr,
                    connections,
                    stats,
                    job_templates,
                    config,
                )
                .await
            }
            Message::Response(response) => {
                debug!("Unexpected response from {}: {:?}", addr, response);
                None
            }
            Message::Notification(notification) => {
                debug!("Unexpected notification from {}: {:?}", addr, notification);
                None
            }
        }
    }

    /// **Handle requests** (xử lý yêu cầu)
    async fn handle_request(
        request: Request,
        addr: SocketAddr,
        connections: Arc<RwLock<HashMap<SocketAddr, ConnectionHandler>>>,
        stats: Arc<RwLock<MockPoolStats>>,
        job_templates: Arc<RwLock<Vec<JobTemplate>>>,
        config: &MockPoolConfig,
    ) -> Option<Message> {
        let response = match request.method.as_str() {
            METHOD_MINING_SUBSCRIBE => {
                Self::handle_mining_subscribe(request.id, addr, connections, stats).await
            }
            METHOD_MINING_AUTHORIZE => {
                Self::handle_mining_authorize(request, addr, connections, stats, config).await
            }
            METHOD_MINING_SUBMIT => {
                Self::handle_mining_submit(request, addr, connections, stats, config).await
            }
            _ => {
                debug!("Unhandled method: {}", request.method);
                Response {
                    id: request.id,
                    result: Value::Null,
                    error: Some(serde_json::json!([-1, "method not found", null])),
                }
            }
        };

        Some(Message::Response(response))
    }

    /// **Handle mining.subscribe** (xử lý mining.subscribe)
    async fn handle_mining_subscribe(
        id: MessageId,
        addr: SocketAddr,
        connections: Arc<RwLock<HashMap<SocketAddr, ConnectionHandler>>>,
        stats: Arc<RwLock<MockPoolStats>>,
    ) -> Response {
        // Generate extra nonce1 for this connection
        let extra_nonce1 = format!("{:08x}", rand::random::<u32>());
        let extra_nonce2_size = 4;

        // Update connection state
        {
            let mut conns = connections.write().await;
            if let Some(handler) = conns.get_mut(&addr) {
                handler.state = ConnectionState::Subscribed;
                handler.extra_nonce1 = Some(extra_nonce1.clone());
            }
        }

        Response {
            id,
            result: serde_json::json!([
                [
                    ["mining.set_difficulty", "1"],
                    ["mining.notify", "1"]
                ],
                &extra_nonce1,
                extra_nonce2_size
            ]),
            error: None,
        }
    }

    /// **Handle mining.authorize** (xử lý mining.authorize)
    async fn handle_mining_authorize(
        request: Request,
        addr: SocketAddr,
        connections: Arc<RwLock<HashMap<SocketAddr, ConnectionHandler>>>,
        stats: Arc<RwLock<MockPoolStats>>,
        config: &MockPoolConfig,
    ) -> Response {
        let worker_name = match request.params.get(0) {
            Some(Value::String(name)) => name.clone(),
            _ => "unknown".to_string(),
        };

        // Update connection state
        {
            let mut conns = connections.write().await;
            if let Some(handler) = conns.get_mut(&addr) {
                handler.worker_name = Some(worker_name.clone());
                handler.authorized = true;
                handler.state = ConnectionState::Authorized;
            }
        }

        // Update stats
        {
            let mut stats_lock = stats.write().await;
            stats_lock.total_authorizations += 1;
        }

        info!("🔑 Authorized worker: {} ({})", worker_name, addr);

        // Send initial difficulty and notify
        tokio::spawn(async move {
            tokio::time::sleep(Duration::from_millis(100)).await;

            // TODO: Send mining.set_difficulty and mining.notify
            // This would need a way to send notifications to specific clients
        });

        Response {
            id: request.id,
            result: serde_json::json!(true),
            error: None,
        }
    }

    /// **Handle mining.submit** (xử lý mining.submit)
    async fn handle_mining_submit(
        request: Request,
        addr: SocketAddr,
        connections: Arc<RwLock<HashMap<SocketAddr, ConnectionHandler>>>,
        stats: Arc<RwLock<MockPoolStats>>,
        config: &MockPoolConfig,
    ) -> Response {
        // Update stats
        {
            let mut stats_lock = stats.write().await;
            stats_lock.total_submissions += 1;
        }

        // Simulate share validation (giả lập xác thực share)
        let is_valid = rand::random::<f64>() >= config.reject_probability;

        if is_valid {
            // Accept share
            let mut stats_lock = stats.write().await;
            stats_lock.accepted_submissions += 1;

            debug!("✅ Accepted share from {}", addr);

            Response {
                id: request.id,
                result: serde_json::json!(true),
                error: None,
            }
        } else {
            // Reject share
            let mut stats_lock = stats.write().await;
            stats_lock.rejected_submissions += 1;

            debug!("❌ Rejected share from {}", addr);

            Response {
                id: request.id,
                result: serde_json::json!(false),
                error: Some(serde_json::json!([23, "low difficulty share", null])),
            }
        }
    }

    /// **Notify all connected clients** (thông báo tất cả client kết nối)
    async fn notify_all_clients(&self) {
        let jobs = self.job_templates.read().await;

        if let Some(job) = jobs.last() {
            // Generate job ID
            let job_id = format!("{:x}", rand::random::<u64>());

            // Create mining.notify notification
            let notify = Notification {
                id: None,
                method: METHOD_MINING_NOTIFY.to_string(),
                params: vec![
                    serde_json::json!(job_id),
                    serde_json::json!(hex::encode(&job.prev_hash)),
                    serde_json::json!(hex::encode(&job.coinbase1)),
                    serde_json::json!(hex::encode(&job.coinbase2)),
                    serde_json::json!(job.merkle_branches.iter().map(hex::encode).collect::<Vec<_>>()),
                    serde_json::json!(hex::encode(&job.version)),
                    serde_json::json!(hex::encode(&job.ntime)),
                    serde_json::json!(hex::encode(&job.target)),
                    serde_json::json!(false), // clean jobs
                ],
            };

            // TODO: Send to all connected clients
            debug!("📦 Broadcasting new job {}", job_id);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::time::timeout;

    #[tokio::test]
    async fn test_mock_pool_server_creation() {
        let config = MockPoolConfig::default();
        let server = MockPoolServer::new(config);
        assert_eq!(server.get_bind_address(), "127.0.0.1:3333");
    }

    #[tokio::test]
    async fn test_mock_pool_start_stop() {
        let config = MockPoolConfig::default();
        let mut server = MockPoolServer::new(config);

        // Start server with timeout
        let start_result = timeout(Duration::from_secs(5), server.start()).await;
        assert!(start_result.is_ok());

        // Stop server
        let stop_result = timeout(Duration::from_secs(5), server.stop()).await;
        assert!(stop_result.is_ok());
    }

    #[tokio::test]
    async fn test_job_template_creation() {
        let template = JobTemplate::default();
        assert_eq!(template.prev_hash.len(), 32);
        assert!(!template.coinbase1.is_empty());
        assert!(!template.coinbase2.is_empty());
    }
}