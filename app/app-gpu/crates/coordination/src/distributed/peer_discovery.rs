//! # Peer Discovery (Tìm Kiếm Peer)
//!
//! Tự động tìm kiếm các mining node khác trong mạng local thông qua mDNS.

use super::{PeerInfo, PeerStatus};
use anyhow::Result;
use std::net::SocketAddr;
use tracing::{debug, info, warn};

pub struct PeerDiscovery {
    peers: Vec<PeerInfo>,
}

impl PeerDiscovery {
    pub fn new() -> Self {
        info!("🔍 Initializing Peer Discovery");
        Self { peers: Vec::new() }
    }

    /// Tìm kiếm peers trong local network thông qua mDNS
    pub async fn discover_local_peers(&mut self) -> Result<()> {
        info!("🌐 Starting mDNS peer discovery...");

        // TODO: Implement mDNS discovery
        // - Broadcast service on _opus-mining._tcp.local
        // - Listen for other instances
        // - Update self.peers với discovered peers

        debug!("Discovered {} peers", self.peers.len());
        Ok(())
    }

    /// Thêm peer thủ công
    pub fn add_peer(&mut self, addr: SocketAddr) -> Result<()> {
        info!("➕ Adding manual peer: {}", addr);

        self.peers.push(PeerInfo {
            address: addr,
            last_seen: std::time::Instant::now(),
            status: PeerStatus::Active,
        });

        Ok(())
    }

    /// Kiểm tra health của tất cả peers
    pub async fn check_peer_health(&mut self) -> Result<()> {
        debug!("💓 Checking health of {} peers", self.peers.len());

        for peer in &mut self.peers {
            // TODO: Ping peer, update status
            let elapsed = peer.last_seen.elapsed();
            if elapsed.as_secs() > 60 {
                warn!("Peer {} inactive for {:?}", peer.address, elapsed);
                peer.status = PeerStatus::Inactive;
            }
        }

        Ok(())
    }

    /// Lấy danh sách active peers
    pub fn get_active_peers(&self) -> Vec<&PeerInfo> {
        self.peers
            .iter()
            .filter(|p| p.status == PeerStatus::Active)
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_peer_discovery() {
        let mut discovery = PeerDiscovery::new();
        assert_eq!(discovery.get_active_peers().len(), 0);

        let addr: SocketAddr = "192.168.1.100:8545".parse().unwrap();
        discovery.add_peer(addr).unwrap();
        assert_eq!(discovery.get_active_peers().len(), 1);
    }
}
