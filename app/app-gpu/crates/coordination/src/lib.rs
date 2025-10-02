//! # Coordination Layer (Lớp Điều Phối)
//!
//! Module điều phối công việc phân tán giữa các node mining,
//! giám sát health và thu thập metrics.

pub mod distributed;
pub mod monitoring;

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use tracing::{debug, info, warn};

/// Configuration cho coordination layer
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoordinationConfig {
    /// Chế độ standalone hoặc distributed
    pub mode: CoordinationMode,
    /// Danh sách peer addresses (nếu distributed mode)
    pub peers: Vec<SocketAddr>,
    /// Health check interval (giây)
    pub health_check_interval: u64,
    /// Metrics collection interval (giây)
    pub metrics_interval: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CoordinationMode {
    Standalone,
    Distributed,
}

impl Default for CoordinationConfig {
    fn default() -> Self {
        Self {
            mode: CoordinationMode::Standalone,
            peers: Vec::new(),
            health_check_interval: 30,
            metrics_interval: 60,
        }
    }
}

/// Coordination Manager - quản lý điều phối
pub struct CoordinationManager {
    config: CoordinationConfig,
    running: std::sync::Arc<tokio::sync::RwLock<bool>>,
}

impl CoordinationManager {
    /// Tạo coordination manager mới
    pub fn new(config: CoordinationConfig) -> Self {
        info!("🔗 Initializing Coordination Manager");
        Self {
            config,
            running: std::sync::Arc::new(tokio::sync::RwLock::new(false)),
        }
    }

    /// Khởi động coordination layer
    pub async fn start(&self) -> Result<()> {
        info!("▶️  Starting Coordination Layer (mode: {:?})", self.config.mode);

        let mut running = self.running.write().await;
        *running = true;

        match self.config.mode {
            CoordinationMode::Standalone => {
                debug!("Running in standalone mode - no peer coordination");
            }
            CoordinationMode::Distributed => {
                info!("🌐 Starting distributed coordination with {} peers",
                      self.config.peers.len());
                // TODO: Start peer discovery and work distribution
            }
        }

        Ok(())
    }

    /// Dừng coordination layer
    pub async fn stop(&self) -> Result<()> {
        info!("⏹️  Stopping Coordination Layer");

        let mut running = self.running.write().await;
        *running = false;

        Ok(())
    }

    /// Kiểm tra trạng thái
    pub async fn is_running(&self) -> bool {
        *self.running.read().await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_coordination_lifecycle() {
        let config = CoordinationConfig::default();
        let manager = CoordinationManager::new(config);

        assert!(!manager.is_running().await);

        manager.start().await.unwrap();
        assert!(manager.is_running().await);

        manager.stop().await.unwrap();
        assert!(!manager.is_running().await);
    }
}
