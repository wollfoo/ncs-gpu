//! # Work Distribution (Phân Phối Công Việc)
//!
//! Phân chia mining work giữa các nodes để tránh duplicate effort.

use anyhow::Result;
use tracing::{debug, info};

/// Work assignment cho một peer
#[derive(Debug, Clone)]
pub struct WorkAssignment {
    pub nonce_start: u64,
    pub nonce_end: u64,
    pub assigned_at: std::time::Instant,
}

pub struct WorkDistributor {
    total_nodes: usize,
    current_nonce: u64,
    batch_size: u64,
}

impl WorkDistributor {
    pub fn new(total_nodes: usize) -> Self {
        info!("📋 Initializing Work Distributor for {} nodes", total_nodes);
        Self {
            total_nodes,
            current_nonce: 0,
            batch_size: 1_000_000, // 1M nonces per batch
        }
    }

    /// Phân chia work cho node_id
    pub fn assign_work(&mut self, node_id: usize) -> Result<WorkAssignment> {
        debug!("Assigning work to node {}", node_id);

        let nonce_start = self.current_nonce + (node_id as u64 * self.batch_size);
        let nonce_end = nonce_start + self.batch_size;

        let assignment = WorkAssignment {
            nonce_start,
            nonce_end,
            assigned_at: std::time::Instant::now(),
        };

        Ok(assignment)
    }

    /// Advance nonce counter sau khi một round hoàn thành
    pub fn advance_round(&mut self) {
        self.current_nonce += self.batch_size * self.total_nodes as u64;
        debug!("Advanced to nonce range starting at {}", self.current_nonce);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_work_distribution() {
        let mut distributor = WorkDistributor::new(3);

        let work0 = distributor.assign_work(0).unwrap();
        let work1 = distributor.assign_work(1).unwrap();

        assert_eq!(work0.nonce_start, 0);
        assert_eq!(work1.nonce_start, 1_000_000);
        assert!(work0.nonce_end > work0.nonce_start);
    }
}
