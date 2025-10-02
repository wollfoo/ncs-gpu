//! # Stratum Mining Protocol Client (Khách hàng giao thức khai thác Stratum)
//!
//! High-performance Stratum client với actor architecture, pooled connections,
//! automatic failover và comprehensive error handling.

use std::collections::VecDeque;
use std::net::ToSocketAddrs;
use std::sync::Arc;
use std::time::{Duration, SystemTime};

use anyhow::Result;
use async_trait::async_trait;
use tokio::sync::mpsc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::TcpStream;
use tokio::sync::{Mutex, RwLock};
use tokio::time::{self, Instant};
use tracing::{debug, error, info, warn};

use serde::{Deserialize, Serialize};
use serde_json::Value;
use super::error::{ShareError, StratumError, Result as StratumResult};
use super::protocol::{
    ConnectionState, Message, MessageId, Notification, PoolCapabilities, Request, Response,
    SessionStats, Solution, StratumError as ProtocolError, WorkPackage,
    METHOD_MINING_AUTHORIZE, METHOD_MINING_NOTIFY, METHOD_MINING_SET_DIFFICULTY,
    METHOD_MINING_SET_EXTRANONCE, METHOD_MINING_SUBSCRIBE, METHOD_MINING_SUBMIT,
};

/// Actor messages for Stratum client (Thông điệp actor cho client Stratum)
#[derive(Debug)]
enum ActorMessage {
    /// Start connection to pool (Bắt đầu kết nối với pool)
    Connect { pool_url: String, pool_password: Option<String> },
    /// Disconnect from current pool (Ngắt kết nối khỏi pool hiện tại)
    Disconnect,
    /// Submit a solution (Nộp một giải pháp)
    SubmitSolution(Solution),
    /// Get current work package (Lấy gói công việc hiện tại)
    GetWork { reply_to: mpsc::Sender<WorkPackage> },
    /// Get connection stats (Lấy thống kê kết nối)
    GetStats { reply_to: mpsc::Sender<SessionStats> },
    /// Stop the actor (Dừng actor)
    Stop,
}

/// Pool configuration (Cấu hình pool)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoolConfig {
    /// Pool URL in stratum+tcp://host:port format (URL pool theo định dạng stratum+tcp://host:port)
    pub url: String,
    /// Worker name (Tên worker)
    pub worker_name: String,
    /// Pool password (if required) (Mật khẩu pool nếu cần)
    pub password: Option<String>,
    /// User agent string (Chuỗi user agent)
    pub user_agent: Option<String>,
    /// SSL/TLS flag (Cờ SSL/TLS)
    pub ssl: bool,
    /// Backup pools for failover (Pool backup cho failover)
    pub backup_pools: Vec<PoolConfig>,
}

/// Main Stratum client configuration (Cấu hình client Stratum chính)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StratumConfig {
    /// Primary pool config (Cấu hình pool chính)
    pub primary_pool: PoolConfig,
    /// Connection timeout in seconds (Timeout kết nối tính bằng giây)
    pub connect_timeout_secs: u64,
    /// Reconnection delay settings (Thiết lập độ trễ kết nối lại)
    pub reconnect_delay_secs: u64,
    /// Maximum reconnection attempts (Số lần kết nối lại tối đa)
    pub max_reconnect_attempts: u32,
    /// Share submission batch size (Kích thước batch nộp share)
    pub share_batch_size: usize,
    /// Maximum job age in seconds (Tuổi job tối đa tính bằng giây)
    pub max_job_age_secs: u64,
    /// Submission rate limit (shares per second) (Giới hạn tỷ lệ nộp share/giây)
    pub rate_limit: f64,
    /// Enable SSL hostname verification (Bật xác minh tên host SSL)
    pub ssl_verify_hostname: bool,
}

/// External control interface (Giao diện điều khiển bên ngoài)
#[derive(Clone)]
pub struct StratumClient {
    /// Actor message sender (Người gửi thông điệp actor)
    tx: mpsc::Sender<ActorMessage>,
    /// Current session stats (Thống kê phiên hiện tại)
    stats: Arc<RwLock<SessionStats>>,
    /// Actor handle (Quản lý actor)
    _handle: Arc<tokio::task::JoinHandle<()>>,
}

impl StratumClient {
    /// Create new Stratum client instance (Tạo instance client Stratum mới)
    pub async fn new(config: StratumConfig) -> Result<Self> {
        let (tx, rx) = mpsc::channel(100); // Backpressure buffer size
        let stats = Arc::new(RwLock::new(SessionStats::default()));

        // Inject start time (Tiêm thời gian bắt đầu)
        {
            let mut session_stats = stats.write().await;
            session_stats.session_start = Some(SystemTime::now());
        }

        // Create and start actor (Tạo và khởi động actor)
        let actor = Actor::new(rx, config, Arc::clone(&stats));
        let handle = tokio::spawn(async move {
            if let Err(e) = actor.run().await {
                error!("Stratum actor error: {}", e);
            }
        });

        Ok(Self {
            tx,
            stats,
            _handle: Arc::new(handle),
        })
    }

    /// Connect to mining pool (Kết nối với mining pool)
    pub async fn connect(&self) -> Result<()> {
        // Note: Config is stored in the actor, so we send a message to get it
        // For now, we'll reconstruct it or modify the design
        // This is a known limitation in the current design
        let pool_url = "stratum+tcp://127.0.0.1:3333".to_string(); // Default for testing
        let pool_password = None;

        self.tx
            .send(ActorMessage::Connect {
                pool_url,
                pool_password,
            })
            .await
            .map_err(|_| StratumError::Internal {
                message: "Failed to send connect message".to_string(),
            })?;

        Ok(())
    }

    /// Disconnect from mining pool (Ngắt kết nối khỏi mining pool)
    pub async fn disconnect(&self) -> Result<()> {
        self.tx
            .send(ActorMessage::Disconnect)
            .await
            .map_err(|_| StratumError::Internal {
                message: "Failed to send disconnect message".to_string(),
            })?;

        Ok(())
    }

    /// Submit mining solution (Nộp giải pháp khai thác)
    pub async fn submit_solution(&self, solution: Solution) -> Result<()> {
        self.tx
            .send(ActorMessage::SubmitSolution(solution))
            .await
            .map_err(|_| StratumError::Internal {
                message: "Failed to send solution".to_string(),
            })?;

        Ok(())
    }

    /// Get current work package (Lấy gói công việc hiện tại)
    pub async fn get_work(&self) -> Result<WorkPackage> {
        let (reply_tx, mut reply_rx) = mpsc::channel(1);

        self.tx
            .send(ActorMessage::GetWork { reply_to: reply_tx })
            .await
            .map_err(|_| StratumError::Internal {
                message: "Failed to send get_work message".to_string(),
            })?;

        match tokio::time::timeout(Duration::from_secs(5), reply_rx.recv()).await {
            Ok(Some(work)) => Ok(work),
            Ok(None) => Err(StratumError::Internal {
                message: "No work package received".to_string(),
            }.into()),
            Err(_) => Err(StratumError::Internal {
                message: "Timeout waiting for work package".to_string(),
            }.into()),
        }
    }

    /// Get current session statistics (Lấy thống kê phiên hiện tại)
    pub async fn get_stats(&self) -> SessionStats {
        let (reply_tx, mut reply_rx) = mpsc::channel(1);

        let _ = self.tx
            .send(ActorMessage::GetStats { reply_to: reply_tx })
            .await;

        match tokio::time::timeout(Duration::from_secs(2), reply_rx.recv()).await {
            Ok(Some(stats)) => stats,
            _ => self.stats.read().await.clone(), // Fallback to cached stats
        }
    }

    /// Shutdown client (Tắt client)
    pub async fn shutdown(self) -> Result<()> {
        let _ = self.tx.send(ActorMessage::Stop).await;
        // Handle will be dropped automatically
        Ok(())
    }
}

/// Internal actor implementation (Triển khai actor nội bộ)
struct Actor {
    /// Message receiver (Người nhận thông điệp)
    rx: mpsc::Receiver<ActorMessage>,
    /// Configuration (Cấu hình)
    config: StratumConfig,
    /// Session statistics (Thống kê phiên)
    stats: Arc<RwLock<SessionStats>>,
    /// Current connection state (Trạng thái kết nối hiện tại)
    state: ConnectionState,
    /// Current work package (Gói công việc hiện tại)
    current_work: Option<WorkPackage>,
    /// Work queue for GPU distribution (Hàng đợi công việc cho phân phối GPU)
    work_queue: VecDeque<WorkPackage>,
    /// Connection stream (Luồng kết nối)
    stream: Option<tokio::io::Lines<BufReader<TcpStream>>>,
    /// Pool capabilities (Khả năng của pool)
    capabilities: PoolCapabilities,
    /// Last read timestamp for connection health (Timestamp đọc cuối cùng cho sức khỏe kết nối)
    last_read: Option<Instant>,
    /// Share submission rate tracker (Theo dõi tỷ lệ nộp share)
    share_rate: ShareRateTracker,
    /// Share batch accumulator (Tích lũy batch share)
    share_batch: Vec<Solution>,
}

impl Actor {
    /// Create new actor instance (Tạo instance actor mới)
    fn new(
        rx: mpsc::Receiver<ActorMessage>,
        config: StratumConfig,
        stats: Arc<RwLock<SessionStats>>
    ) -> Self {
        Self {
            rx,
            config,
            stats,
            state: ConnectionState::Disconnected,
            current_work: None,
            work_queue: VecDeque::new(),
            stream: None,
            capabilities: PoolCapabilities::default(),
            last_read: None,
            share_rate: ShareRateTracker::new(),
            share_batch: Vec::new(),
        }
    }

    /// Main actor loop (Vòng lặp actor chính)
    async fn run(mut self) -> StratumResult<()> {
        info!("🌐 Stratum actor started");

        loop {
            tokio::select! {
                // Handle incoming messages (Xử lý thông điệp đến)
                message = self.rx.recv() => {
                    match message {
                        Some(msg) => {
                            if let Err(e) = self.handle_message(msg).await {
                                error!("Failed to handle message: {}", e);
                            }
                        }
                        None => {
                            // Channel closed, exit (Kênh đóng, thoát)
                            break;
                        }
                    }
                }

                // Handle incoming pool messages (Xử lý thông điệp từ pool)
                line_result = async {
                    if let Some(lines) = &mut self.stream {
                        lines.next_line().await
                    } else {
                        std::future::pending().await
                    }
                } => {
                    match line_result {
                        Ok(Some(line)) => {
                            self.handle_incoming_line(line.trim()).await;
                        }
                        Ok(None) => {
                            // Stream ended (Dòng chảy kết thúc)
                            warn!("Pool connection stream ended");
                            self.handle_connection_loss().await;
                        }
                        Err(e) => {
                            error!("Error reading from pool: {}", e);
                            self.handle_connection_loss().await;
                        }
                    }
                }

                // Handle connection health (Xử lý sức khỏe kết nối)
                _ = tokio::time::sleep(Duration::from_secs(30)) => {
                    self.check_connection_health().await;
                }
            }
        }

        self.cleanup().await?;
        info!("🛑 Stratum actor stopped");
        Ok(())
    }

    /// Handle incoming actor messages (Xử lý thông điệp actor đến)
    async fn handle_message(&mut self, msg: ActorMessage) -> StratumResult<()> {
        match msg {
            ActorMessage::Connect { pool_url, pool_password } => {
                self.connect_to_pool(pool_url, pool_password).await?;
            }
            ActorMessage::Disconnect => {
                self.disconnect().await?;
            }
            ActorMessage::SubmitSolution(solution) => {
                self.submit_solution(solution).await?;
            }
            ActorMessage::GetWork { reply_to } => {
                if let Some(work) = &self.current_work {
                    let _ = reply_to.send(work.clone()).await;
                }
            }
            ActorMessage::GetStats { reply_to } => {
                let stats = self.stats.read().await.clone();
                let _ = reply_to.send(stats).await;
            }
            ActorMessage::Stop => {
                return self.cleanup().await.map_err(Into::into);
            }
        }
        Ok(())
    }

    /// Connect to mining pool (Kết nối với mining pool)
    async fn connect_to_pool(&mut self, pool_url: String, pool_password: Option<String>) -> StratumResult<()> {
        info!("🔌 Connecting to pool: {}", pool_url);

        // Update stats (Cập nhật thống kê)
        {
            let mut stats = self.stats.write().await;
            stats.connections_attempted += 1;
        }

        self.state = ConnectionState::Connecting;

        // Parse pool URL (Phân tích URL pool)
        let (host, port) = self.parse_pool_url(&pool_url)?;

        // Resolve hostname (Giải quyết tên host)
        let socket_addr = (host.as_str(), port)
            .to_socket_addrs()?
            .next()
            .ok_or_else(|| StratumError::Config {
                source: crate::stratum::error::ConfigError::InvalidPoolUrl { url: pool_url.clone() }
            })?;

        // Connect with timeout (Kết nối với timeout)
        let timeout = Duration::from_secs(self.config.connect_timeout_secs);
        let stream = tokio::time::timeout(timeout, TcpStream::connect(&socket_addr)).await??;

        info!("✅ Connected to {}:{}", host, port);

        // Update stats (Cập nhật thống kê)
        {
            let mut stats = self.stats.write().await;
            stats.connections_successful += 1;
        }

        // Create line-based reader for JSON-RPC messages (Tạo reader dựa trên dòng cho thông điệp JSON-RPC)
        let reader = BufReader::new(stream);
        let lines = reader.lines();
        self.stream = Some(lines);

        self.state = ConnectionState::Connected;
        self.last_read = Some(Instant::now());

        // Start message handling (Bắt đầu xử lý thông điệp)
        self.subscribe_from_config(pool_password).await?;

        Ok(())
    }

    /// Parse pool URL to extract host and port (Phân tích URL pool để trích xuất host và port)
    fn parse_pool_url(&self, url: &str) -> StratumResult<(String, u16)> {
        let url = url
            .strip_prefix("stratum+tcp://")
            .or_else(|| url.strip_prefix("stratum://"))
            .or_else(|| url.strip_prefix("tcp://"))
            .ok_or_else(|| StratumError::Config {
                source: crate::stratum::error::ConfigError::InvalidPoolUrl { url: url.to_string() }
            })?;

        if let Some((host, port_str)) = url.rsplit_once(':') {
            let port = port_str.parse().map_err(|_| StratumError::Config {
                source: crate::stratum::error::ConfigError::InvalidPort { port: port_str.parse().unwrap_or(0) }
            })?;
            Ok((host.to_string(), port))
        } else {
            Ok((url.to_string(), 3333)) // Default port
        }
    }

    /// Subscribe with pool using config (Subscribe với pool sử dụng config)
    async fn subscribe_from_config(&mut self, pool_password: Option<String>) -> StratumResult<()> {
        // Send mining.subscribe (Gửi mining.subscribe)
        let subscribe_msg = Request {
            id: MessageId::new(),
            method: METHOD_MINING_SUBSCRIBE.to_string(),
            params: vec![
                serde_json::json!("Miner"),
                serde_json::json!(self.config.primary_pool.worker_name),
                serde_json::json!(pool_password.unwrap_or_default()),
            ],
        };

        self.send_message(&Message::Request(subscribe_msg)).await?;
        self.state = ConnectionState::Subscribed;

        // Wait for subscribe response and then authorize (Chờ phản hồi subscribe và sau đó authorize)
        self.authorize().await?;

        Ok(())
    }

    /// Authorize with pool (Xác thực với pool)
    async fn authorize(&mut self) -> StratumResult<()> {
        let authorize_msg = Request {
            id: MessageId::new(),
            method: METHOD_MINING_AUTHORIZE.to_string(),
            params: vec![
                serde_json::json!(self.config.primary_pool.worker_name),
                serde_json::json!(""),
            ],
        };

        self.send_message(&Message::Request(authorize_msg)).await?;
        self.state = ConnectionState::Authorized;

        info!("🔑 Authorized with pool");
        Ok(())
    }

    /// Submit mining solution (Nộp giải pháp khai thác)
    async fn submit_solution(&mut self, solution: Solution) -> Result<()> {
        // Check rate limits (Kiểm tra giới hạn tỷ lệ)
        if !self.share_rate.check_limit(self.config.rate_limit) {
            return Err(ShareError::RateExceeded {
                current_rate: self.share_rate.current_rate(),
                limit_rate: self.config.rate_limit,
            }.into());
        }

        // Add to batch or send immediately (Thêm vào batch hoặc gửi ngay lập tức)
        self.share_batch.push(solution);

        if self.share_batch.len() >= self.config.share_batch_size {
            self.flush_share_batch().await?;
        }

        Ok(())
    }

    /// Flush accumulated share batch (Xóa batch share tích lũy)
    async fn flush_share_batch(&mut self) -> Result<()> {
        let batch = std::mem::take(&mut self.share_batch);

        for solution in batch {
            let submit_msg = Request {
                id: MessageId::new(),
                method: METHOD_MINING_SUBMIT.to_string(),
                params: vec![
                    serde_json::json!(self.config.primary_pool.worker_name),
                    serde_json::json!(solution.job_id),
                    serde_json::json!(solution.extra_nonce2),
                    serde_json::json!(solution.nonce),
                    serde_json::json!(solution.hash),
                    serde_json::json!(solution.mix_hash),
                ],
            };

            self.send_message(&Message::Request(submit_msg)).await?;

            // Update stats (Cập nhật thống kê)
            let mut stats = self.stats.write().await;
            stats.shares_submitted += 1;
            stats.last_share_time = Some(SystemTime::now());
        }

        self.share_rate.record_batch(self.share_batch.len());
        Ok(())
    }

    /// Send message to pool (Gửi thông điệp đến pool)
    async fn send_message(&mut self, message: &Message) -> StratumResult<()> {
        if let Some(lines) = &mut self.stream {
            let json = serde_json::to_string(message)?;
            let stream = lines.get_mut().get_mut();

            // Send JSON-RPC message followed by newline (Gửi thông điệp JSON-RPC theo sau bởi newline)
            stream.write_all(json.as_bytes()).await?;
            stream.write_all(b"\n").await?;
            stream.flush().await?;

            debug!("📤 Sent: {}", json);
            Ok(())
        } else {
            Err(StratumError::Connection {
                source: crate::stratum::error::ConnectionError::UnexpectedDisconnect,
            })
        }
    }

    /// Check connection health and attempt recovery (Kiểm tra sức khỏe kết nối và thử khôi phục)
    async fn check_connection_health(&mut self) {
        if let Some(last_read) = self.last_read {
            if last_read.elapsed() > Duration::from_secs(60) {
                warn!("Connection appears stale, attempting recovery");
                // TODO: Trigger reconnection logic
            }
        }
    }

    /// Disconnect and cleanup (Ngắt kết nối và dọn dẹp)
    async fn disconnect(&mut self) -> Result<()> {
        info!("🔌 Disconnecting from pool");

        if let Some(lines) = self.stream.take() {
            drop(lines); // Simply drop to close the connection
        }

        self.state = ConnectionState::Disconnected;
        self.current_work = None;
        self.work_queue.clear();
        self.share_batch.clear();

        Ok(())
    }

    /// Handle incoming line from pool (Xử lý dòng đến từ pool)
    async fn handle_incoming_line(&mut self, line: &str) {
        self.last_read = Some(Instant::now());

        if line.trim().is_empty() {
            return; // Skip empty lines
        }

        debug!("📨 Received: {}", line);

        match serde_json::from_str::<Message>(line) {
            Ok(message) => {
                if let Err(e) = self.handle_pool_message(message).await {
                    error!("Error handling pool message: {}", e);
                }
            }
            Err(e) => {
                warn!("Failed to parse JSON message '{}': {}", line, e);
            }
        }
    }

    /// Handle parsed pool message (Xử lý thông điệp pool đã phân tích)
    async fn handle_pool_message(&mut self, message: Message) -> Result<()> {
        match message {
            Message::Response(response) => {
                self.handle_pool_response(response).await?;
            }
            Message::Notification(notification) => {
                self.handle_pool_notification(notification).await?;
            }
            Message::Request(request) => {
                // Pool shouldn't send requests to miner
                warn!("Unexpected request from pool: {:?}", request);
            }
        }
        Ok(())
    }

    /// Handle pool response messages (Xử lý thông điệp phản hồi từ pool)
    async fn handle_pool_response(&mut self, response: Response) -> Result<()> {
        if let Some(ProtocolError(code, message, _)) = &response.error {
            return Err(StratumError::Protocol {
                source: crate::stratum::error::ProtocolError::InvalidJsonFormat {
                    details: format!("Pool error {}: {}", code, message),
                },
            }.into());
        }

        debug!("Pool response ID {}: {:?}", response.id.raw(), response.result);
        Ok(())
    }

    /// Handle pool notification messages (Xử lý thông điệp thông báo từ pool)
    async fn handle_pool_notification(&mut self, notification: Notification) -> Result<()> {
        match notification.method.as_str() {
            METHOD_MINING_NOTIFY => {
                self.handle_mining_notify(notification.params).await?;
            }
            METHOD_MINING_SET_DIFFICULTY => {
                self.handle_set_difficulty(notification.params)?;
            }
            METHOD_MINING_SET_EXTRANONCE => {
                self.handle_set_extranonce(notification.params)?;
            }
            other => {
                debug!("Unhandled notification method: {}", other);
            }
        }
        Ok(())
    }

    /// Handle mining.notify notification (Xử lý thông báo mining.notify)
    async fn handle_mining_notify(&mut self, params: Vec<Value>) -> StratumResult<()> {
        if params.len() < 9 {
            return Err(StratumError::Protocol {
                source: crate::stratum::error::ProtocolError::MissingField {
                    field: "mining.notify parameters".to_string(),
                },
            });
        }

        let job_id = params[0].as_str().ok_or_else(|| {
            StratumError::Protocol {
                source: crate::stratum::error::ProtocolError::InvalidParameter {
                    parameter: "job_id".to_string(),
                    value: params[0].to_string(),
                },
            }
        })?;

        let previous_hash = params[1].as_str().unwrap_or("");
        let coinbase1 = params[2].as_str().unwrap_or("");
        let coinbase2 = params[3].as_str().unwrap_or("");
        let merkle_branches: Vec<&str> = params[4]
            .as_array()
            .unwrap_or(&vec![])
            .iter()
            .filter_map(|v| v.as_str())
            .collect();

        let version = params[5].as_str().unwrap_or("");
        let nbits = params[6].as_str().unwrap_or("");
        let ntime = params[7].as_str().unwrap_or("");
        let clean_jobs = params[8].as_bool().unwrap_or(false);

        // Convert strings to bytes (Chuyển đổi chuỗi thành byte)
        let header_hash = hex::decode(previous_hash.trim_start_matches("0x")).map_err(|_| {
            StratumError::Protocol {
                source: crate::stratum::error::ProtocolError::InvalidHexEncoding {
                    hex: previous_hash.to_string(),
                },
            }
        })?;

        let seed_hash = header_hash.clone(); // For Ethereum, seed hash is same as header hash
        let target = if let Some(diff_target) = params.get(9) {
            if let Some(hex_str) = diff_target.as_str() {
                hex::decode(hex_str.trim_start_matches("0x"))?
            } else if let Some(num) = diff_target.as_f64() {
                // Convert difficulty to target
                let diff = num;
                // Ethereum uses 32-byte BE target
                let mut target_bytes = vec![0u8; 32];
                // Simple difficulty to target conversion (placeholder)
                let target_value = (0xFFFFFFFFFFFFFFFFu64 as f64 / diff) as u64;
                target_bytes[24..].copy_from_slice(&target_value.to_be_bytes());
                target_bytes
            } else {
                vec![0u8; 32] // Default target
            }
        } else {
            vec![0u8; 32] // Default target
        };

        let work_package = WorkPackage {
            job_id: job_id.to_string(),
            header_hash,
            seed_hash,
            target,
            height: 1000000, // Placeholder, need to parse from params
            difficulty: params.get(9).and_then(|v| v.as_f64()).unwrap_or(1.0),
            extra_nonce1: self.capabilities.subscribe_extranonce.then_some(vec![0u8; 8]),
            received_at: SystemTime::now(),
            clean_jobs,
        };

        if clean_jobs {
            self.work_queue.clear();
        }

        // Add to work queue and update current work (Thêm vào hàng đợi công việc và cập nhật công việc hiện tại)
        self.work_queue.push_back(work_package.clone());
        self.current_work = Some(work_package);

        // Update stats (Cập nhật thống kê)
        {
            let mut stats = self.stats.write().await;
            stats.jobs_received += 1;
        }

        info!("📦 Received new job: {} (clean: {})", job_id, clean_jobs);
        Ok(())
    }

    /// Handle mining.set_difficulty notification (Xử lý thông báo mining.set_difficulty)
    fn handle_set_difficulty(&mut self, params: Vec<Value>) -> Result<()> {
        if let Some(diff_value) = params.get(0) {
            if let Some(difficulty) = diff_value.as_f64() {
                info!("🎯 Difficulty set to: {}", difficulty);

                // Update current work difficulty if exists (Cập nhật độ khó công việc hiện tại nếu có)
                if let Some(work) = &mut self.current_work {
                    work.difficulty = difficulty;
                }
            }
        }
        Ok(())
    }

    /// Handle mining.set_extranonce notification (Xử lý thông báo mining.set_extranonce)
    fn handle_set_extranonce(&mut self, params: Vec<Value>) -> Result<()> {
        if params.len() >= 2 {
            if let (Some(extra_nonce1), Some(extra_nonce2_size)) =
                (params[0].as_str(), params[1].as_u64()) {

                info!("🔢 Extra nonce updated: {} (size: {})",
                      extra_nonce1, extra_nonce2_size);

                if let Some(work) = &mut self.current_work {
                    work.extra_nonce1 = Some(hex::decode(extra_nonce1.trim_start_matches("0x"))?);
                }
            }
        }
        Ok(())
    }

    /// Handle connection loss and attempt recovery (Xử lý mất kết nối và thử khôi phục)
    async fn handle_connection_loss(&mut self) {
        error!("💔 Connection to pool lost");

        // Update state and stats (Cập nhật trạng thái và thống kê)
        self.state = ConnectionState::Failover;

        {
            let mut stats = self.stats.write().await;
            stats.connections_failed += 1;
        }

        // Close current connection (Đóng kết nối hiện tại)
        self.disconnect().await.ok();

        // Attempt to failover to backup pools (Thử failover sang pool backup)
        if let Err(e) = self.attempt_failover().await {
            error!("Failover failed: {}", e);
            // Schedule reconnection attempt (Lên lịch thử kết nối lại)
            self.schedule_reconnection().await;
        }
    }

    /// Attempt failover to backup pools (Thử failover sang pool backup)
    async fn attempt_failover(&mut self) -> Result<()> {
        let backup_pools = self.config.primary_pool.backup_pools.clone(); // Clone to avoid borrowing issues
        for backup_pool in &backup_pools {
            info!("🔄 Trying failover to backup pool: {}", backup_pool.url);

            let pool_url = backup_pool.url.clone();
            let pool_password = backup_pool.password.clone();

            match tokio::time::timeout(
                Duration::from_secs(10),
                self.connect_to_pool(pool_url, pool_password)
            ).await {
                Ok(Ok(())) => {
                    info!("✅ Successfully failed over to backup pool");
                    return Ok(());
                }
                Ok(Err(e)) => {
                    warn!("Failed to connect to backup pool: {}", e);
                }
                Err(_) => {
                    warn!("Timeout connecting to backup pool");
                }
            }
        }

        Err(StratumError::Failover {
            source: crate::stratum::error::FailoverError::AllPoolsFailed,
        }.into())
    }

    /// Schedule reconnection attempt (Lên lịch thử kết nối lại)
    async fn schedule_reconnection(&mut self) {
        info!("⏰ Scheduling reconnection in {} seconds", self.config.reconnect_delay_secs);
        tokio::time::sleep(Duration::from_secs(self.config.reconnect_delay_secs)).await;

        if let Err(e) = self.connect_to_pool(
            self.config.primary_pool.url.clone(),
            self.config.primary_pool.password.clone()
        ).await {
            error!("Reconnection failed: {}", e);
            // If primary fails, try backup pools again
            self.attempt_failover().await.ok();
        }
    }

    /// Cleanup resources (Dọn dẹp tài nguyên)
    async fn cleanup(&mut self) -> Result<()> {
        let _ = self.disconnect().await;
        Ok(())
    }
}

/// Share rate tracking for rate limiting (Theo dõi tỷ lệ share cho giới hạn tỷ lệ)
struct ShareRateTracker {
    /// Share timestamps (Timestamp share)
    share_times: VecDeque<Instant>,
    /// Max entries to track (Số entry tối đa để theo dõi)
    max_entries: usize,
}

impl ShareRateTracker {
    /// Create new rate tracker (Tạo tracker tỷ lệ mới)
    fn new() -> Self {
        Self {
            share_times: VecDeque::with_capacity(100),
            max_entries: 100,
        }
    }

    /// Check if submission rate is within limit (Kiểm tra nếu tỷ lệ nộp nằm trong giới hạn)
    fn check_limit(&mut self, limit_per_second: f64) -> bool {
        // Clean old entries (Dọn dẹp entry cũ)
        let cutoff = Instant::now() - Duration::from_secs(60);
        while let Some(&oldest) = self.share_times.front() {
            if oldest < cutoff {
                self.share_times.pop_front();
            } else {
                break;
            }
        }

        let current_rate = self.current_rate();
        current_rate < limit_per_second * 0.95 // 5% buffer
    }

    /// Get current submission rate (Lấy tỷ lệ nộp hiện tại)
    fn current_rate(&self) -> f64 {
        if self.share_times.len() < 2 {
            return 0.0;
        }

        let duration = self.share_times.back().unwrap().duration_since(*self.share_times.front().unwrap()).as_secs_f64();
        if duration > 0.0 {
            self.share_times.len() as f64 / duration
        } else {
            0.0
        }
    }

    /// Record share submissions (Ghi lại việc nộp share)
    fn record_batch(&mut self, count: usize) {
        let now = Instant::now();
        for _ in 0..count {
            if self.share_times.len() >= self.max_entries {
                self.share_times.pop_front();
            }
            self.share_times.push_back(now);
        }
    }
}

impl Default for ShareRateTracker {
    fn default() -> Self {
        Self::new()
    }
}