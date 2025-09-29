//! # OPUS-GPU Pool Communication Module
//!
//! Advanced pool communication module supporting Stratum protocols v1 and v2,
//! multi-pool management, connection pooling, and intelligent failover.
//!
//! ## Features
//!
//! - **Stratum Protocol Support**: Full Stratum v1 and v2 implementation
//! - **Multi-Pool Management**: Automatic switching based on profitability
//! - **Connection Pooling**: Efficient connection reuse and failover
//! - **Security**: TLS/SSL encryption and secure communication
//! - **Performance**: Connection optimization and latency reduction
//!
//! ## Architecture
//!
//! ```text
//! ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
//! │   Pool Client   │───▶│  Stratum Layer  │───▶│   Connection    │
//! │                 │    │                 │    │      Pool       │
//! └─────────────────┘    └─────────────────┘    └─────────────────┘
//!          │                       │                       │
//!          ▼                       ▼                       ▼
//! ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
//! │  Pool Manager   │    │  Protocol       │    │   Failover      │
//! │                 │    │   Handler       │    │    Manager      │
//! └─────────────────┘    └─────────────────┘    └─────────────────┘
//! ```

pub mod client;
pub mod config;
pub mod connection;
pub mod error;
pub mod manager;
pub mod protocol;
pub mod stratum;

pub use client::PoolClient;
pub use config::{PoolConfig, StratumConfig};
pub use connection::{Connection, ConnectionPool};
pub use error::{PoolError, PoolResult};
pub use manager::{MultiPoolManager, PoolManager};
pub use protocol::{ProtocolHandler, StratumMessage};
pub use stratum::{StratumV1, StratumV2};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tokio::sync::mpsc;
use uuid::Uuid;

/// Pool connection statistics for monitoring and optimization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoolStats {
    /// Unique pool identifier
    pub pool_id: Uuid,
    /// Pool server URL
    pub url: String,
    /// Current connection status
    pub status: ConnectionStatus,
    /// Average latency in milliseconds
    pub latency_ms: f64,
    /// Total shares submitted
    pub shares_submitted: u64,
    /// Total shares accepted
    pub shares_accepted: u64,
    /// Current difficulty
    pub difficulty: f64,
    /// Connected since timestamp
    pub connected_since: chrono::DateTime<chrono::Utc>,
    /// Last work received timestamp
    pub last_work: Option<chrono::DateTime<chrono::Utc>>,
    /// Connection errors count
    pub error_count: u64,
}

/// Connection status enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConnectionStatus {
    Disconnected,
    Connecting,
    Connected,
    Authenticated,
    Error,
}

/// Mining work data structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningWork {
    /// Work identifier
    pub id: String,
    /// Work data for mining
    pub data: Vec<u8>,
    /// Target difficulty
    pub target: Vec<u8>,
    /// Job ID for Stratum
    pub job_id: Option<String>,
    /// Extra nonce for Stratum v2
    pub extra_nonce: Option<Vec<u8>>,
    /// Clean jobs flag
    pub clean_jobs: bool,
    /// Work timestamp
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

/// Mining share submission
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningShare {
    /// Share identifier
    pub id: String,
    /// Job ID
    pub job_id: String,
    /// Extra nonce 2
    pub extra_nonce2: Vec<u8>,
    /// Nonce value
    pub nonce: u32,
    /// Timestamp
    pub timestamp: u32,
    /// Worker name
    pub worker: String,
}

/// Pool notification events
#[derive(Debug, Clone)]
pub enum PoolEvent {
    /// New work received
    NewWork(MiningWork),
    /// Share accepted/rejected
    ShareResult { id: String, accepted: bool, reason: Option<String> },
    /// Difficulty change
    DifficultyChanged(f64),
    /// Connection status change
    StatusChanged { pool_id: Uuid, status: ConnectionStatus },
    /// Pool switched
    PoolSwitched { from: Uuid, to: Uuid },
    /// Error occurred
    Error { pool_id: Uuid, error: String },
}

/// Trait for pool communication implementations
#[async_trait]
pub trait PoolCommunication: Send + Sync {
    /// Connect to the mining pool
    async fn connect(&mut self) -> PoolResult<()>;

    /// Disconnect from the mining pool
    async fn disconnect(&mut self) -> PoolResult<()>;

    /// Subscribe to mining work
    async fn subscribe(&mut self, user_agent: &str, extra_nonce1_size: usize) -> PoolResult<()>;

    /// Authorize worker
    async fn authorize(&mut self, worker: &str, password: &str) -> PoolResult<()>;

    /// Submit mining share
    async fn submit_share(&mut self, share: MiningShare) -> PoolResult<bool>;

    /// Get current pool statistics
    async fn get_stats(&self) -> PoolResult<PoolStats>;

    /// Set difficulty
    async fn set_difficulty(&mut self, difficulty: f64) -> PoolResult<()>;

    /// Get event receiver
    fn get_event_receiver(&self) -> mpsc::Receiver<PoolEvent>;
}

/// Pool profitability information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoolProfitability {
    /// Pool identifier
    pub pool_id: Uuid,
    /// Pool name
    pub name: String,
    /// Estimated hashrate reward (per MH/s per day)
    pub reward_per_mhs: f64,
    /// Pool fee percentage
    pub fee_percent: f64,
    /// Network difficulty
    pub difficulty: f64,
    /// Block reward
    pub block_reward: f64,
    /// Profitability score (0.0 - 1.0)
    pub score: f64,
    /// Last updated timestamp
    pub updated_at: chrono::DateTime<chrono::Utc>,
}

/// Pool selection strategy
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PoolSelectionStrategy {
    /// Always use the first available pool
    FixedPrimary,
    /// Switch based on profitability
    Profitability,
    /// Round-robin switching
    RoundRobin,
    /// Lowest latency first
    LowestLatency,
    /// Custom strategy with weights
    Weighted(HashMap<Uuid, f64>),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_connection_status() {
        assert_eq!(ConnectionStatus::Disconnected, ConnectionStatus::Disconnected);
        assert_ne!(ConnectionStatus::Connected, ConnectionStatus::Disconnected);
    }

    #[test]
    fn test_mining_work_creation() {
        let work = MiningWork {
            id: "work-1".to_string(),
            data: vec![1, 2, 3, 4],
            target: vec![0, 0, 0, 255],
            job_id: Some("job-1".to_string()),
            extra_nonce: None,
            clean_jobs: true,
            timestamp: chrono::Utc::now(),
        };

        assert_eq!(work.id, "work-1");
        assert!(work.clean_jobs);
    }
}