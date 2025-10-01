// Networking Module - Kết nối pool và giao tiếp mạng
// Networking Module - Pool connection and network communication

use anyhow::{Result, Context, bail};
use tokio::net::TcpStream;
use tokio_tungstenite::{connect_async, WebSocketStream, MaybeTlsStream};
use tungstenite::protocol::Message;
use futures_util::{StreamExt, SinkExt};
use serde::{Deserialize, Serialize};
use serde_json;
use tracing::{info, debug, error, warn};
use std::time::Duration;

/// Pool connection state
/// Trạng thái kết nối pool
#[derive(Debug, Clone, PartialEq)]
pub enum ConnectionState {
    /// Chưa kết nối
    Disconnected,
    /// Đang kết nối
    Connecting,
    /// Đã kết nối
    Connected,
    /// Đã xác thực
    Authorized,
    /// Lỗi kết nối
    Error(String),
}

/// Mining pool connection
/// Kết nối đến mining pool
pub struct PoolConnection {
    /// Pool address
    address: String,
    /// Wallet address
    wallet: String,
    /// Worker name
    worker: String,
    /// Use TLS?
    use_tls: bool,
    /// WebSocket connection
    ws: Option<WebSocketStream<MaybeTlsStream<TcpStream>>>,
    /// Connection state
    state: ConnectionState,
    /// Current job
    current_job: Option<StratumJob>,
    /// Submission ID counter
    submission_id: u64,
}

/// Stratum protocol messages
#[derive(Debug, Serialize, Deserialize)]
pub struct StratumRequest {
    pub id: u64,
    pub method: String,
    pub params: Vec<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct StratumResponse {
    pub id: Option<u64>,
    pub result: Option<serde_json::Value>,
    pub error: Option<StratumError>,
    pub method: Option<String>,
    pub params: Option<Vec<serde_json::Value>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct StratumError {
    pub code: i32,
    pub message: String,
}

/// Stratum job từ pool
#[derive(Debug, Clone)]
pub struct StratumJob {
    pub job_id: String,
    pub prev_hash: String,
    pub coinbase1: String,
    pub coinbase2: String,
    pub merkle_branch: Vec<String>,
    pub version: String,
    pub nbits: String,
    pub ntime: String,
    pub clean_jobs: bool,
    pub target: String,
}

impl PoolConnection {
    /// Create new pool connection
    pub async fn new(address: &str, wallet: &str, worker: &str, use_tls: bool) -> Result<Self> {
        Ok(Self {
            address: address.to_string(),
            wallet: wallet.to_string(),
            worker: worker.to_string(),
            use_tls,
            ws: None,
            state: ConnectionState::Disconnected,
            current_job: None,
            submission_id: 1,
        })
    }
    
    /// Connect to mining pool
    pub async fn connect(&mut self) -> Result<()> {
        info!("🔌 Connecting to pool: {}", self.address);
        
        self.state = ConnectionState::Connecting;
        
        // Parse pool address
        let url = if self.address.starts_with("stratum+tcp://") {
            self.address.replace("stratum+tcp://", "ws://")
        } else if self.address.starts_with("stratum+ssl://") || self.use_tls {
            self.address.replace("stratum+ssl://", "wss://")
                       .replace("stratum+tcp://", "wss://")
        } else {
            format!("ws://{}", self.address)
        };
        
        debug!("WebSocket URL: {}", url);
        
        // Connect with timeout
        let connect_future = connect_async(&url);
        let timeout = Duration::from_secs(30);
        
        match tokio::time::timeout(timeout, connect_future).await {
            Ok(Ok((ws_stream, _))) => {
                info!("✅ Connected to pool successfully");
                self.ws = Some(ws_stream);
                self.state = ConnectionState::Connected;
                
                // Authorize worker
                self.authorize().await?;
                
                // Subscribe to notifications
                self.subscribe().await?;
                
                Ok(())
            }
            Ok(Err(e)) => {
                error!("❌ Failed to connect: {}", e);
                self.state = ConnectionState::Error(e.to_string());
                bail!("Connection failed: {}", e)
            }
            Err(_) => {
                error!("❌ Connection timeout");
                self.state = ConnectionState::Error("Timeout".to_string());
                bail!("Connection timeout after 30 seconds")
            }
        }
    }
    
    /// Authorize worker với pool
    async fn authorize(&mut self) -> Result<()> {
        info!("🔐 Authorizing worker: {}", self.worker);
        
        let auth_request = StratumRequest {
            id: self.get_next_id(),
            method: "mining.authorize".to_string(),
            params: vec![
                serde_json::Value::String(format!("{}.{}", self.wallet, self.worker)),
                serde_json::Value::String("x".to_string()), // Password (usually 'x')
            ],
        };
        
        self.send_request(&auth_request).await?;
        
        // Wait for response
        if let Some(response) = self.receive_response().await? {
            if response.result == Some(serde_json::Value::Bool(true)) {
                info!("✅ Worker authorized successfully");
                self.state = ConnectionState::Authorized;
                Ok(())
            } else {
                error!("❌ Authorization failed");
                self.state = ConnectionState::Error("Auth failed".to_string());
                bail!("Worker authorization failed")
            }
        } else {
            bail!("No response to authorization request")
        }
    }
    
    /// Subscribe to pool notifications
    async fn subscribe(&mut self) -> Result<()> {
        debug!("📡 Subscribing to pool notifications");
        
        let subscribe_request = StratumRequest {
            id: self.get_next_id(),
            method: "mining.subscribe".to_string(),
            params: vec![
                serde_json::Value::String("gpu-miner/1.0".to_string()),
            ],
        };
        
        self.send_request(&subscribe_request).await?;
        
        // Handle subscription response
        if let Some(response) = self.receive_response().await? {
            debug!("Subscription response: {:?}", response);
            Ok(())
        } else {
            warn!("No response to subscription request");
            Ok(())
        }
    }
    
    /// Get work from pool
    pub async fn get_work(&mut self) -> Result<crate::mining::MiningWork> {
        // Check for new job from pool
        self.check_for_new_job().await?;
        
        if let Some(ref job) = self.current_job {
            Ok(crate::mining::MiningWork {
                job_id: job.job_id.clone(),
                header: self.build_block_header(job),
                target: hex::decode(&job.target)?,
                nonce_start: 0,
                nonce_end: u32::MAX as u64,
                extra_nonce: None,
            })
        } else {
            bail!("No work available from pool")
        }
    }
    
    /// Check for new job from pool
    async fn check_for_new_job(&mut self) -> Result<()> {
        if let Some(ref mut ws) = self.ws {
            // Non-blocking receive
            match tokio::time::timeout(Duration::from_millis(100), ws.next()).await {
                Ok(Some(Ok(Message::Text(text)))) => {
                    if let Ok(response) = serde_json::from_str::<StratumResponse>(&text) {
                        if response.method == Some("mining.notify".to_string()) {
                            self.handle_new_job(response)?;
                        }
                    }
                }
                _ => {}
            }
        }
        
        Ok(())
    }
    
    /// Handle new job notification
    fn handle_new_job(&mut self, response: StratumResponse) -> Result<()> {
        if let Some(params) = response.params {
            if params.len() >= 9 {
                let job = StratumJob {
                    job_id: params[0].as_str().unwrap_or("").to_string(),
                    prev_hash: params[1].as_str().unwrap_or("").to_string(),
                    coinbase1: params[2].as_str().unwrap_or("").to_string(),
                    coinbase2: params[3].as_str().unwrap_or("").to_string(),
                    merkle_branch: params[4].as_array()
                        .map(|arr| arr.iter()
                            .filter_map(|v| v.as_str().map(|s| s.to_string()))
                            .collect())
                        .unwrap_or_default(),
                    version: params[5].as_str().unwrap_or("").to_string(),
                    nbits: params[6].as_str().unwrap_or("").to_string(),
                    ntime: params[7].as_str().unwrap_or("").to_string(),
                    clean_jobs: params[8].as_bool().unwrap_or(false),
                    target: "00000000ffff0000000000000000000000000000000000000000000000000000".to_string(),
                };
                
                info!("📦 New job received: {}", job.job_id);
                self.current_job = Some(job);
            }
        }
        
        Ok(())
    }
    
    /// Build block header from job
    fn build_block_header(&self, job: &StratumJob) -> Vec<u8> {
        // Simplified block header construction
        // Real implementation would properly construct the header
        let mut header = Vec::new();
        
        // Version
        header.extend_from_slice(&hex::decode(&job.version).unwrap_or_default());
        // Previous hash
        header.extend_from_slice(&hex::decode(&job.prev_hash).unwrap_or_default());
        // Merkle root (simplified)
        header.extend_from_slice(&[0u8; 32]);
        // Timestamp
        header.extend_from_slice(&hex::decode(&job.ntime).unwrap_or_default());
        // Bits
        header.extend_from_slice(&hex::decode(&job.nbits).unwrap_or_default());
        // Nonce placeholder
        header.extend_from_slice(&[0u8; 4]);
        
        header
    }
    
    /// Submit share to pool
    pub async fn submit_share(&mut self, nonce: &u64, hash: &[u8]) -> Result<bool> {
        if self.current_job.is_none() {
            bail!("No active job to submit share for");
        }
        
        let job = self.current_job.as_ref().unwrap();
        
        info!("📤 Submitting share for job {}", job.job_id);
        
        let submit_request = StratumRequest {
            id: self.get_next_id(),
            method: "mining.submit".to_string(),
            params: vec![
                serde_json::Value::String(format!("{}.{}", self.wallet, self.worker)),
                serde_json::Value::String(job.job_id.clone()),
                serde_json::Value::String("00000000".to_string()), // Extra nonce2
                serde_json::Value::String(job.ntime.clone()),
                serde_json::Value::String(format!("{:08x}", nonce)),
            ],
        };
        
        self.send_request(&submit_request).await?;
        
        // Wait for response
        if let Some(response) = self.receive_response().await? {
            if response.error.is_some() {
                warn!("❌ Share rejected: {:?}", response.error);
                Ok(false)
            } else {
                info!("✅ Share accepted!");
                Ok(true)
            }
        } else {
            Ok(false)
        }
    }
    
    /// Send request to pool
    async fn send_request(&mut self, request: &StratumRequest) -> Result<()> {
        if let Some(ref mut ws) = self.ws {
            let json = serde_json::to_string(request)?;
            debug!("→ Sending: {}", json);
            ws.send(Message::Text(json)).await?;
        } else {
            bail!("Not connected to pool");
        }
        
        Ok(())
    }
    
    /// Receive response from pool
    async fn receive_response(&mut self) -> Result<Option<StratumResponse>> {
        if let Some(ref mut ws) = self.ws {
            match tokio::time::timeout(Duration::from_secs(5), ws.next()).await {
                Ok(Some(Ok(Message::Text(text)))) => {
                    debug!("← Received: {}", text);
                    Ok(serde_json::from_str(&text).ok())
                }
                Ok(Some(Ok(_))) => Ok(None),
                Ok(Some(Err(e))) => {
                    error!("WebSocket error: {}", e);
                    Err(e.into())
                }
                Ok(None) => Ok(None),
                Err(_) => Ok(None), // Timeout
            }
        } else {
            bail!("Not connected to pool");
        }
    }
    
    /// Disconnect from pool
    pub async fn disconnect(&mut self) -> Result<()> {
        info!("🔌 Disconnecting from pool");
        
        if let Some(mut ws) = self.ws.take() {
            let _ = ws.close(None).await;
        }
        
        self.state = ConnectionState::Disconnected;
        self.current_job = None;
        
        Ok(())
    }
    
    /// Get next request ID
    fn get_next_id(&mut self) -> u64 {
        let id = self.submission_id;
        self.submission_id += 1;
        id
    }
    
    /// Get connection state
    pub fn state(&self) -> &ConnectionState {
        &self.state
    }
}
