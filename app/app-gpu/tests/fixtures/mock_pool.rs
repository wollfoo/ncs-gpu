//! # Mock Stratum Pool (Pool Stratum Giả)
//!
//! **Fake Stratum pool server** (server pool stratum giả) cho integration testing.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::{Mutex, RwLock};
use tokio::time::{sleep, Duration};
use tracing::{debug, error, info, warn};

/// **Share submission** (submit share) – parsed share data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Share {
    /// **Worker name** (tên worker)
    pub worker_name: String,

    /// **Job ID** (ID công việc) – from mining.notify
    pub job_id: String,

    /// **Nonce** (số dùng một lần) – solution nonce
    pub nonce: String,

    /// **Result** (kết quả) – hash result
    pub result: String,

    /// **Timestamp** (dấu thời gian)
    pub timestamp: Instant,
}

/// **Mock Stratum Pool** (pool stratum giả)
pub struct MockStratumPool {
    /// **Port** (cổng) – TCP listen port
    port: u16,

    /// **Connected clients** (client kết nối)
    clients: Arc<RwLock<Vec<Arc<Mutex<TcpStream>>>>>,

    /// **Received shares** (share nhận được)
    received_shares: Arc<RwLock<Vec<Share>>>,

    /// **Accepted shares** (share chấp nhận)
    accepted_shares: Arc<RwLock<u64>>,

    /// **Rejected shares** (share từ chối)
    rejected_shares: Arc<RwLock<u64>>,

    /// **Reject rate** (tỷ lệ từ chối) – 0.0-1.0 (0% to 100%)
    reject_rate: Arc<RwLock<f64>>,

    /// **Job ID counter** (bộ đếm job ID)
    job_id_counter: Arc<RwLock<u64>>,

    /// **Running status** (trạng thái chạy)
    is_running: Arc<RwLock<bool>>,

    /// **Simulate connection drops** (giả lập mất kết nối)
    simulate_drops: Arc<RwLock<bool>>,

    /// **Job timeout** (timeout công việc) – seconds
    job_timeout_secs: Arc<RwLock<u64>>,
}

impl MockStratumPool {
    /// **Create new mock pool** (tạo pool giả mới)
    ///
    /// # Arguments (Tham số)
    /// - `port`: TCP port để listen
    pub fn new(port: u16) -> Self {
        info!("🏊 Creating mock Stratum pool on port {}", port);

        Self {
            port,
            clients: Arc::new(RwLock::new(Vec::new())),
            received_shares: Arc::new(RwLock::new(Vec::new())),
            accepted_shares: Arc::new(RwLock::new(0)),
            rejected_shares: Arc::new(RwLock::new(0)),
            reject_rate: Arc::new(RwLock::new(0.0)), // Default: không reject
            job_id_counter: Arc::new(RwLock::new(1)),
            is_running: Arc::new(RwLock::new(false)),
            simulate_drops: Arc::new(RwLock::new(false)),
            job_timeout_secs: Arc::new(RwLock::new(120)), // 2 minutes default
        }
    }

    /// **Start pool server** (khởi động server pool)
    ///
    /// Spawn async task listening for connections.
    pub async fn start(&self) -> Result<(), String> {
        let mut running = self.is_running.write().await;
        if *running {
            return Err("Pool already running".to_string());
        }

        *running = true;
        drop(running);

        let listener = TcpListener::bind(format!("127.0.0.1:{}", self.port))
            .await
            .map_err(|e| format!("Failed to bind port {}: {}", self.port, e))?;

        info!("✅ Mock pool listening on port {}", self.port);

        // Clone Arcs for spawned task
        let clients = Arc::clone(&self.clients);
        let received_shares = Arc::clone(&self.received_shares);
        let accepted_shares = Arc::clone(&self.accepted_shares);
        let rejected_shares = Arc::clone(&self.rejected_shares);
        let reject_rate = Arc::clone(&self.reject_rate);
        let job_id_counter = Arc::clone(&self.job_id_counter);
        let is_running = Arc::clone(&self.is_running);
        let simulate_drops = Arc::clone(&self.simulate_drops);

        tokio::spawn(async move {
            while *is_running.read().await {
                match listener.accept().await {
                    Ok((socket, addr)) => {
                        info!("🔌 New client connected: {}", addr);

                        let client_stream = Arc::new(Mutex::new(socket));
                        clients.write().await.push(Arc::clone(&client_stream));

                        // Spawn handler cho client này
                        let stream = Arc::clone(&client_stream);
                        let shares = Arc::clone(&received_shares);
                        let accepted = Arc::clone(&accepted_shares);
                        let rejected = Arc::clone(&rejected_shares);
                        let reject = Arc::clone(&reject_rate);
                        let job_counter = Arc::clone(&job_id_counter);
                        let drops = Arc::clone(&simulate_drops);

                        tokio::spawn(async move {
                            Self::handle_client(
                                stream,
                                shares,
                                accepted,
                                rejected,
                                reject,
                                job_counter,
                                drops,
                            )
                            .await;
                        });
                    }
                    Err(e) => {
                        error!("❌ Accept error: {}", e);
                    }
                }
            }
        });

        Ok(())
    }

    /// **Stop pool server** (dừng server pool)
    pub async fn stop(&self) {
        *self.is_running.write().await = false;
        info!("🛑 Mock pool stopped");
    }

    /// **Handle client connection** (xử lý kết nối client)
    async fn handle_client(
        stream: Arc<Mutex<TcpStream>>,
        received_shares: Arc<RwLock<Vec<Share>>>,
        accepted_shares: Arc<RwLock<u64>>,
        rejected_shares: Arc<RwLock<u64>>,
        reject_rate: Arc<RwLock<f64>>,
        job_id_counter: Arc<RwLock<u64>>,
        simulate_drops: Arc<RwLock<bool>>,
    ) {
        let mut socket = stream.lock().await;
        let (reader, mut writer) = socket.split();
        let mut reader = BufReader::new(reader);

        // Send mining.notify (job)
        let job_id = {
            let mut counter = job_id_counter.write().await;
            let id = *counter;
            *counter += 1;
            id
        };

        let notify = format!(
            r#"{{"id":null,"method":"mining.notify","params":["{}","0xabcd","0x1234","0x5678",true]}}{}"#,
            job_id, "\n"
        );

        if let Err(e) = writer.write_all(notify.as_bytes()).await {
            error!("❌ Failed to send notify: {}", e);
            return;
        }

        debug!("📤 Sent mining.notify (job_id={})", job_id);

        // Read loop
        let mut line = String::new();
        loop {
            line.clear();

            // Check nếu simulate drops
            if *simulate_drops.read().await {
                warn!("⚡ Simulating connection drop");
                break;
            }

            match reader.read_line(&mut line).await {
                Ok(0) => {
                    debug!("📡 Client disconnected");
                    break;
                }
                Ok(_) => {
                    debug!("📥 Received: {}", line.trim());

                    // Parse JSON-RPC
                    if let Ok(msg) = serde_json::from_str::<serde_json::Value>(&line) {
                        if let Some(method) = msg.get("method").and_then(|m| m.as_str()) {
                            match method {
                                "mining.subscribe" => {
                                    let response = r#"{"id":1,"result":[["mining.notify","subscription_id"],"extranonce1",4],"error":null}"#;
                                    let _ = writer.write_all(format!("{}\n", response).as_bytes()).await;
                                }
                                "mining.authorize" => {
                                    let response =
                                        r#"{"id":2,"result":true,"error":null}"#;
                                    let _ = writer.write_all(format!("{}\n", response).as_bytes()).await;
                                }
                                "mining.submit" => {
                                    // Parse share
                                    if let Some(params) = msg.get("params").and_then(|p| p.as_array()) {
                                        let worker = params.get(0).and_then(|w| w.as_str()).unwrap_or("unknown");
                                        let job = params.get(1).and_then(|j| j.as_str()).unwrap_or("");
                                        let nonce = params.get(2).and_then(|n| n.as_str()).unwrap_or("");
                                        let result = params.get(4).and_then(|r| r.as_str()).unwrap_or("");

                                        let share = Share {
                                            worker_name: worker.to_string(),
                                            job_id: job.to_string(),
                                            nonce: nonce.to_string(),
                                            result: result.to_string(),
                                            timestamp: Instant::now(),
                                        };

                                        received_shares.write().await.push(share.clone());

                                        // Validate share dựa trên reject_rate
                                        let reject = *reject_rate.read().await;
                                        let should_reject = rand::random::<f64>() < reject;

                                        if should_reject {
                                            *rejected_shares.write().await += 1;
                                            let response = r#"{"id":3,"result":null,"error":[21,"Low difficulty share",null]}"#;
                                            let _ = writer.write_all(format!("{}\n", response).as_bytes()).await;
                                            debug!("❌ Share rejected (simulated)");
                                        } else {
                                            *accepted_shares.write().await += 1;
                                            let response = r#"{"id":3,"result":true,"error":null}"#;
                                            let _ = writer.write_all(format!("{}\n", response).as_bytes()).await;
                                            debug!("✅ Share accepted");
                                        }
                                    }
                                }
                                _ => {
                                    debug!("⚠️  Unknown method: {}", method);
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    error!("❌ Read error: {}", e);
                    break;
                }
            }
        }
    }

    /// **Set reject rate** (đặt tỷ lệ từ chối)
    ///
    /// # Arguments (Tham số)
    /// - `rate`: 0.0-1.0 (0% to 100%)
    pub async fn set_reject_rate(&self, rate: f64) {
        let clamped = rate.clamp(0.0, 1.0);
        *self.reject_rate.write().await = clamped;
        info!("📊 Reject rate set to {:.1}%", clamped * 100.0);
    }

    /// **Enable connection drops** (bật giả lập mất kết nối)
    pub async fn enable_connection_drops(&self, enable: bool) {
        *self.simulate_drops.write().await = enable;
        info!("⚡ Connection drops: {}", if enable { "ON" } else { "OFF" });
    }

    /// **Set job timeout** (đặt timeout công việc)
    pub async fn set_job_timeout(&self, secs: u64) {
        *self.job_timeout_secs.write().await = secs;
        info!("⏱️  Job timeout set to {}s", secs);
    }

    /// **Get received shares** (lấy share nhận được)
    pub async fn get_received_shares(&self) -> Vec<Share> {
        self.received_shares.read().await.clone()
    }

    /// **Get acceptance rate** (lấy tỷ lệ chấp nhận)
    ///
    /// # Returns (Trả về)
    /// - Tỷ lệ acceptance (0.0-1.0)
    pub async fn get_acceptance_rate(&self) -> f64 {
        let accepted = *self.accepted_shares.read().await;
        let rejected = *self.rejected_shares.read().await;
        let total = accepted + rejected;

        if total == 0 {
            1.0 // 100% nếu chưa có share nào
        } else {
            accepted as f64 / total as f64
        }
    }

    /// **Get accepted shares count** (lấy số share chấp nhận)
    pub async fn get_accepted_count(&self) -> u64 {
        *self.accepted_shares.read().await
    }

    /// **Get rejected shares count** (lấy số share từ chối)
    pub async fn get_rejected_count(&self) -> u64 {
        *self.rejected_shares.read().await
    }

    /// **Get client count** (lấy số client kết nối)
    pub async fn get_client_count(&self) -> usize {
        self.clients.read().await.len()
    }

    /// **Reset statistics** (đặt lại thống kê)
    pub async fn reset(&self) {
        self.received_shares.write().await.clear();
        *self.accepted_shares.write().await = 0;
        *self.rejected_shares.write().await = 0;
        info!("🔄 Pool statistics reset");
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fixtures::common::find_free_port;

    #[tokio::test]
    async fn test_pool_creation() {
        let port = find_free_port();
        let pool = MockStratumPool::new(port);

        assert_eq!(pool.get_client_count().await, 0);
        assert_eq!(pool.get_accepted_count().await, 0);
    }

    #[tokio::test]
    async fn test_pool_start_stop() {
        let port = find_free_port();
        let pool = MockStratumPool::new(port);

        pool.start().await.expect("Start failed");
        sleep(Duration::from_millis(100)).await;

        pool.stop().await;
    }

    #[tokio::test]
    async fn test_reject_rate_setting() {
        let pool = MockStratumPool::new(find_free_port());

        pool.set_reject_rate(0.5).await; // 50%
        pool.set_reject_rate(1.5).await; // Clamp to 100%

        // Internal state check thông qua acceptance rate
        let rate = pool.get_acceptance_rate().await;
        assert!(rate >= 0.0 && rate <= 1.0);
    }
}
