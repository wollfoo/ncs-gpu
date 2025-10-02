//! # Stratum Protocol Messages (Thông điệp giao thức Stratum)
//!
//! JSON-RPC message definitions và parsing logic cho Stratum protocol v1
//! với Ethereum extensions.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::time::{SystemTime, UNIX_EPOCH};

/// Stratum JSON-RPC message ID (ID thông điệp JSON-RPC)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct MessageId(u64);

impl MessageId {
    /// Create new message ID (Tạo ID thông điệp mới)
    pub fn new() -> Self {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_micros() as u64;

        // Use last 32 bits for uniqueness in practical sessions
        Self(timestamp & 0xFFFFFFFF)
    }

    /// Create message ID from raw value (Tạo ID từ giá trị thô)
    pub fn from_raw(id: u64) -> Self {
        Self(id)
    }

    /// Get raw value (Lấy giá trị thô)
    pub fn raw(&self) -> u64 {
        self.0
    }
}

impl Default for MessageId {
    fn default() -> Self {
        Self::new()
    }
}

impl Serialize for MessageId {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        self.0.serialize(serializer)
    }
}

impl<'de> Deserialize<'de> for MessageId {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let value = u64::deserialize(deserializer)?;
        Ok(Self(value))
    }
}

/// Base Stratum JSON-RPC message (Thông điệp JSON-RPC cơ bản)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Message {
    /// Request message (Thông điệp yêu cầu)
    Request(Request),
    /// Response message (Thông điệp phản hồi)
    Response(Response),
    /// Notification message (Thông điệp thông báo)
    Notification(Notification),
}

/// Stratum request message (Thông điệp yêu cầu Stratum)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Request {
    /// Message ID (ID thông điệp)
    pub id: MessageId,
    /// RPC method (Phương thức RPC)
    pub method: String,
    /// Method parameters (Tham số phương thức)
    pub params: Vec<Value>,
}

/// Stratum response message (Thông điệp phản hồi Stratum)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Response {
    /// Message ID from request (ID thông điệp từ request)
    pub id: MessageId,
    /// Result value (Giá trị kết quả)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    /// Error information (Thông tin lỗi)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<StratumError>,
}

/// Stratum error structure (Cấu trúc lỗi Stratum)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StratumError(pub i32, pub String, pub Option<Value>);

/// Stratum notification message (Thông điệp thông báo Stratum)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Notification {
    /// Notification method (Phương thức thông báo)
    pub method: String,
    /// Notification parameters (Tham số thông báo)
    pub params: Vec<Value>,
}

/// Mining work package từ pool (Gói công việc khai thác từ pool)
#[derive(Debug, Clone)]
pub struct WorkPackage {
    /// Job ID từ pool (ID job từ pool)
    pub job_id: String,
    /// Header hash (thô) (Header hash thô)
    pub header_hash: Vec<u8>,
    /// Seed hash (thô) (Seed hash thô)
    pub seed_hash: Vec<u8>,
    /// Target difficulty (Mục tiêu độ khó)
    pub target: Vec<u8>,
    /// Block height (Chiều cao block)
    pub height: u64,
    /// Network difficulty (Độ khó mạng)
    pub difficulty: f64,
    /// Extra nonce 1 từ pool (Extra nonce 1 từ pool)
    pub extra_nonce1: Option<Vec<u8>>,
    /// Timestamp khi nhận job (Thời điểm nhận job)
    pub received_at: SystemTime,
    /// Clean jobs flag (Cờ clean jobs)
    pub clean_jobs: bool,
}

/// Mining solution để submit (Giải pháp khai thác để nộp)
#[derive(Debug, Clone)]
pub struct Solution {
    /// Job ID (ID job)
    pub job_id: String,
    /// Extra nonce 2 (Extra nonce 2)
    pub extra_nonce2: Vec<u8>,
    /// Nonce value (Giá trị nonce)
    pub nonce: u64,
    /// Final hash (Hash cuối cùng)
    pub hash: Vec<u8>,
    /// Mix hash (Mix hash for Ethash)
    pub mix_hash: Vec<u8>,
}

/// Stratum connection state (Trạng thái kết nối Stratum)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConnectionState {
    /// Disconnected from pool (Ngắt kết nối khỏi pool)
    Disconnected,
    /// Connecting to pool (Đang kết nối với pool)
    Connecting,
    /// Connected, waiting for subscribe (Đã kết nối, chờ subscribe)
    Connected,
    /// Subscribed, waiting for authorize (Đã subscribe, chờ authorize)
    Subscribed,
    /// Authorized, ready for work (Đã authorize, sẵn sàng làm việc)
    Authorized,
    /// Temporarily disconnected, attempting reconnection (Tạm thời ngắt kết nối, đang thử kết nối lại)
    Reconnecting,
    /// Connection failed, switched to different pool (Kết nối thất bại, chuyển sang pool khác)
    Failover,
}

/// Pool capabilities (Khả năng của pool)
#[derive(Debug, Clone, Default)]
pub struct PoolCapabilities {
    /// Mining extensions supported (Các扩展 khai thác được hỗ trợ)
    pub extensions: Vec<String>,
    /// Subscribe extranonce flag (Cờ extranonce subscribe)
    pub subscribe_extranonce: bool,
    /// Extra nonce size (Kích thước extra nonce)
    pub extra_nonce_size: Option<usize>,
    /// Mining set difficulty supported (Hỗ trợ set difficulty)
    pub set_difficulty: bool,
    /// Mining notify version (Phiên bản mining notify)
    pub notify_version: Option<String>,
}

/// Stratum session statistics (Thống kê phiên Stratum)
#[derive(Debug, Clone, Default)]
pub struct SessionStats {
    /// Total connections attempted (Tổng số kết nối đã thử)
    pub connections_attempted: u64,
    /// Successful connections (Kết nối thành công)
    pub connections_successful: u64,
    /// Failed connections (Kết nối thất bại)
    pub connections_failed: u64,
    /// Total jobs received (Tổng số jobs nhận được)
    pub jobs_received: u64,
    /// Total shares submitted (Tổng số shares đã nộp)
    pub shares_submitted: u64,
    /// Accepted shares (Shares được chấp nhận)
    pub shares_accepted: u64,
    /// Rejected shares (Shares bị từ chối)
    pub shares_rejected: u64,
    /// Stale shares (Shares cũ)
    pub shares_stale: u64,
    /// Session start time (Thời gian bắt đầu phiên)
    pub session_start: Option<SystemTime>,
    /// Last share submission time (Thời gian nộp share cuối cùng)
    pub last_share_time: Option<SystemTime>,
    /// Current hashrate (Hashrate hiện tại)
    pub current_hashrate: f64,
}

impl SessionStats {
    /// Calculate acceptance rate (Tính tỷ lệ chấp nhận)
    pub fn acceptance_rate(&self) -> f64 {
        if self.shares_submitted == 0 {
            return 0.0;
        }
        (self.shares_accepted as f64) / (self.shares_submitted as f64)
    }

    /// Calculate rejection rate (Tính tỷ lệ từ chối)
    pub fn rejection_rate(&self) -> f64 {
        if self.shares_submitted == 0 {
            return 0.0;
        }
        (self.shares_rejected as f64) / (self.shares_submitted as f64)
    }

    /// Get session duration in seconds (Lấy thời gian phiên tính bằng giây)
    pub fn session_duration_secs(&self) -> u64 {
        if let Some(start) = self.session_start {
            SystemTime::now()
                .duration_since(start)
                .unwrap_or_default()
                .as_secs()
        } else {
            0
        }
    }
}

// Utility functions (Hàm tiện ích)
impl WorkPackage {
    /// Check if job is stale (Kiểm tra xem job có cũ không)
    pub fn is_stale(&self, max_age_secs: u64) -> bool {
        let now = SystemTime::now();
        if let Ok(duration) = now.duration_since(self.received_at) {
            duration.as_secs() > max_age_secs
        } else {
            true // If time went backwards, consider stale
        }
    }

    /// Get job age in seconds (Lấy tuổi job tính bằng giây)
    pub fn age_seconds(&self) -> u64 {
        let now = SystemTime::now();
        now.duration_since(self.received_at)
            .unwrap_or_default()
            .as_secs()
    }
}

impl Default for ConnectionState {
    fn default() -> Self {
        ConnectionState::Disconnected
    }
}

// Stratum method constants (Hằng số phương thức Stratum)
pub const METHOD_MINING_SUBSCRIBE: &str = "mining.subscribe";
pub const METHOD_MINING_AUTHORIZE: &str = "mining.authorize";
pub const METHOD_MINING_SUBMIT: &str = "mining.submit";
pub const METHOD_MINING_NOTIFY: &str = "mining.notify";
pub const METHOD_MINING_SET_DIFFICULTY: &str = "mining.set_difficulty";
pub const METHOD_MINING_SET_EXTRANONCE: &str = "mining.set_extranonce";

// Ethereum-specific extensions (Các extension dành riêng cho Ethereum)
pub const METHOD_ETH_GET_WORK: &str = "eth_getWork";
pub const METHOD_ETH_SUBMIT_WORK: &str = "eth_submitWork";
pub const METHOD_ETH_SUBMIT_HASHRATE: &str = "eth_submitHashrate";