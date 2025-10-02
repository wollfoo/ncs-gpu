//! # Distributed Coordination (Điều Phối Phân Tán)
//!
//! Module quản lý peer discovery, work distribution giữa các node.

pub mod peer_discovery;
pub mod work_distribution;

use anyhow::Result;
use std::net::SocketAddr;

/// Thông tin về một peer node
#[derive(Debug, Clone)]
pub struct PeerInfo {
    pub address: SocketAddr,
    pub last_seen: std::time::Instant,
    pub status: PeerStatus,
}

#[derive(Debug, Clone, PartialEq)]
pub enum PeerStatus {
    Active,
    Inactive,
    Failed,
}
