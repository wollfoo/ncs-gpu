use crate::{StorageError, StorageValue, ValueMetadata};
use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, info, warn};
use uuid::Uuid;

/// Transaction state
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum TransactionState {
    Active,
    Committed,
    Aborted,
    Preparing,
}

/// Transaction operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransactionOp {
    Put { key: String, value: Vec<u8>, metadata: Option<ValueMetadata> },
    Delete { key: String },
}

/// Transaction information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    pub id: Uuid,
    pub state: TransactionState,
    pub operations: Vec<TransactionOp>,
    pub created_at: DateTime<Utc>,
    pub committed_at: Option<DateTime<Utc>>,
    pub isolation_level: IsolationLevel,
}

/// Transaction isolation levels
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum IsolationLevel {
    ReadUncommitted,
    ReadCommitted,
    RepeatableRead,
    Serializable,
}

/// Transaction statistics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct TransactionStats {
    pub active_transactions: u64,
    pub committed_transactions: u64,
    pub aborted_transactions: u64,
    pub avg_transaction_duration_ms: u64,
    pub deadlock_count: u64,
    pub conflict_count: u64,
}

/// Transaction manager
pub struct TransactionManager {
    transactions: Arc<RwLock<HashMap<Uuid, Transaction>>>,
    stats: Arc<RwLock<TransactionStats>>,
}

impl TransactionManager {
    pub fn new() -> Self {
        Self {
            transactions: Arc::new(RwLock::new(HashMap::new())),
            stats: Arc::new(RwLock::new(TransactionStats::default())),
        }
    }

    /// Begin a new transaction
    pub async fn begin(&self, isolation_level: IsolationLevel) -> Result<Uuid> {
        let tx_id = Uuid::new_v4();
        let transaction = Transaction {
            id: tx_id,
            state: TransactionState::Active,
            operations: Vec::new(),
            created_at: Utc::now(),
            committed_at: None,
            isolation_level,
        };

        let mut transactions = self.transactions.write().await;
        transactions.insert(tx_id, transaction);

        let mut stats = self.stats.write().await;
        stats.active_transactions += 1;

        debug!("🔄 Transaction started: {}", tx_id);
        Ok(tx_id)
    }

    /// Add operation to transaction
    pub async fn add_operation(&self, tx_id: Uuid, op: TransactionOp) -> Result<()> {
        let mut transactions = self.transactions.write().await;
        let tx = transactions.get_mut(&tx_id)
            .ok_or_else(|| StorageError::TransactionNotFound(tx_id.to_string()))?;

        if tx.state != TransactionState::Active {
            return Err(StorageError::TransactionConflict("Transaction not active".to_string()).into());
        }

        tx.operations.push(op);
        debug!("➕ Operation added to transaction: {}", tx_id);
        Ok(())
    }

    /// Commit transaction
    pub async fn commit(&self, tx_id: Uuid) -> Result<()> {
        let mut transactions = self.transactions.write().await;
        let tx = transactions.get_mut(&tx_id)
            .ok_or_else(|| StorageError::TransactionNotFound(tx_id.to_string()))?;

        if tx.state != TransactionState::Active {
            return Err(StorageError::TransactionConflict("Transaction not active".to_string()).into());
        }

        tx.state = TransactionState::Committed;
        tx.committed_at = Some(Utc::now());

        let mut stats = self.stats.write().await;
        stats.active_transactions -= 1;
        stats.committed_transactions += 1;

        info!("✅ Transaction committed: {}", tx_id);
        Ok(())
    }

    /// Abort transaction
    pub async fn abort(&self, tx_id: Uuid) -> Result<()> {
        let mut transactions = self.transactions.write().await;
        let tx = transactions.get_mut(&tx_id)
            .ok_or_else(|| StorageError::TransactionNotFound(tx_id.to_string()))?;

        tx.state = TransactionState::Aborted;

        let mut stats = self.stats.write().await;
        stats.active_transactions -= 1;
        stats.aborted_transactions += 1;

        warn!("❌ Transaction aborted: {}", tx_id);
        Ok(())
    }

    /// Get transaction info
    pub async fn get_transaction(&self, tx_id: Uuid) -> Result<Option<Transaction>> {
        let transactions = self.transactions.read().await;
        Ok(transactions.get(&tx_id).cloned())
    }

    /// Get statistics
    pub async fn get_stats(&self) -> TransactionStats {
        self.stats.read().await.clone()
    }
}

impl Default for IsolationLevel {
    fn default() -> Self {
        IsolationLevel::ReadCommitted
    }
}