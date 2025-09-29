//! Transaction history management

use super::types::{Transaction, TransactionStatus, TransactionType};
use crate::types::{Address, CoinType};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Transaction history filter
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionHistoryFilter {
    /// Filter by transaction type
    pub tx_type: Option<TransactionType>,
    /// Filter by transaction status
    pub status: Option<TransactionStatus>,
    /// Filter by minimum amount
    pub min_amount: Option<u64>,
    /// Filter by maximum amount
    pub max_amount: Option<u64>,
    /// Filter by date range (start)
    pub start_date: Option<DateTime<Utc>>,
    /// Filter by date range (end)
    pub end_date: Option<DateTime<Utc>>,
    /// Filter by coin type
    pub coin_type: Option<CoinType>,
    /// Filter by address involvement
    pub address: Option<Address>,
    /// Limit number of results
    pub limit: Option<usize>,
    /// Offset for pagination
    pub offset: Option<usize>,
    /// Sort order (newest first by default)
    pub sort_desc: bool,
}

impl Default for TransactionHistoryFilter {
    fn default() -> Self {
        Self {
            tx_type: None,
            status: None,
            min_amount: None,
            max_amount: None,
            start_date: None,
            end_date: None,
            coin_type: None,
            address: None,
            limit: Some(100), // Default limit
            offset: None,
            sort_desc: true, // Newest first
        }
    }
}

impl TransactionHistoryFilter {
    /// Create new filter
    pub fn new() -> Self {
        Self::default()
    }

    /// Filter by transaction type
    pub fn with_type(mut self, tx_type: TransactionType) -> Self {
        self.tx_type = Some(tx_type);
        self
    }

    /// Filter by transaction status
    pub fn with_status(mut self, status: TransactionStatus) -> Self {
        self.status = Some(status);
        self
    }

    /// Filter by amount range
    pub fn with_amount_range(mut self, min: Option<u64>, max: Option<u64>) -> Self {
        self.min_amount = min;
        self.max_amount = max;
        self
    }

    /// Filter by date range
    pub fn with_date_range(
        mut self,
        start: Option<DateTime<Utc>>,
        end: Option<DateTime<Utc>>,
    ) -> Self {
        self.start_date = start;
        self.end_date = end;
        self
    }

    /// Filter by coin type
    pub fn with_coin_type(mut self, coin_type: CoinType) -> Self {
        self.coin_type = Some(coin_type);
        self
    }

    /// Filter by address
    pub fn with_address(mut self, address: Address) -> Self {
        self.address = Some(address);
        self
    }

    /// Set pagination
    pub fn with_pagination(mut self, limit: usize, offset: usize) -> Self {
        self.limit = Some(limit);
        self.offset = Some(offset);
        self
    }

    /// Set sort order
    pub fn with_sort_order(mut self, desc: bool) -> Self {
        self.sort_desc = desc;
        self
    }

    /// Apply filter to transaction
    pub fn matches(&self, transaction: &Transaction) -> bool {
        // Check transaction type
        if let Some(tx_type) = &self.tx_type {
            if transaction.tx_type != *tx_type {
                return false;
            }
        }

        // Check transaction status
        if let Some(status) = &self.status {
            if transaction.status != *status {
                return false;
            }
        }

        // Check coin type
        if let Some(coin_type) = &self.coin_type {
            if transaction.coin_type != *coin_type {
                return false;
            }
        }

        // Check amount range
        let tx_amount = transaction.total_output_amount();
        if let Some(min_amount) = self.min_amount {
            if tx_amount < min_amount {
                return false;
            }
        }
        if let Some(max_amount) = self.max_amount {
            if tx_amount > max_amount {
                return false;
            }
        }

        // Check date range
        if let Some(start_date) = &self.start_date {
            if transaction.created_at < *start_date {
                return false;
            }
        }
        if let Some(end_date) = &self.end_date {
            if transaction.created_at > *end_date {
                return false;
            }
        }

        // Check address involvement
        if let Some(address) = &self.address {
            if !transaction.involves_address(address) {
                return false;
            }
        }

        true
    }
}

/// Transaction history manager
#[derive(Debug)]
pub struct TransactionHistory {
    transactions: Vec<Transaction>,
}

impl TransactionHistory {
    /// Create new transaction history
    pub fn new() -> Self {
        Self {
            transactions: Vec::new(),
        }
    }

    /// Add transaction to history
    pub fn add_transaction(&mut self, transaction: Transaction) {
        // Check if transaction already exists
        if !self.transactions.iter().any(|tx| tx.id == transaction.id) {
            self.transactions.push(transaction);
            // Keep transactions sorted by creation time (newest first)
            self.transactions.sort_by(|a, b| b.created_at.cmp(&a.created_at));
        }
    }

    /// Update existing transaction
    pub fn update_transaction(&mut self, transaction: Transaction) -> bool {
        if let Some(existing) = self.transactions.iter_mut().find(|tx| tx.id == transaction.id) {
            *existing = transaction;
            true
        } else {
            false
        }
    }

    /// Remove transaction
    pub fn remove_transaction(&mut self, tx_id: &str) -> bool {
        if let Some(pos) = self.transactions.iter().position(|tx| tx.id == tx_id) {
            self.transactions.remove(pos);
            true
        } else {
            false
        }
    }

    /// Get transaction by ID
    pub fn get_transaction(&self, tx_id: &str) -> Option<&Transaction> {
        self.transactions.iter().find(|tx| tx.id == tx_id)
    }

    /// Get all transactions
    pub fn get_all_transactions(&self) -> &[Transaction] {
        &self.transactions
    }

    /// Get filtered transactions
    pub fn get_filtered_transactions(&self, filter: &TransactionHistoryFilter) -> Vec<Transaction> {
        let mut filtered: Vec<Transaction> = self
            .transactions
            .iter()
            .filter(|tx| filter.matches(tx))
            .cloned()
            .collect();

        // Sort
        if filter.sort_desc {
            filtered.sort_by(|a, b| b.created_at.cmp(&a.created_at));
        } else {
            filtered.sort_by(|a, b| a.created_at.cmp(&b.created_at));
        }

        // Apply pagination
        let start = filter.offset.unwrap_or(0);
        let end = if let Some(limit) = filter.limit {
            start + limit
        } else {
            filtered.len()
        };

        filtered.into_iter().skip(start).take(end - start).collect()
    }

    /// Get transaction count
    pub fn transaction_count(&self) -> usize {
        self.transactions.len()
    }

    /// Get transaction count by filter
    pub fn filtered_transaction_count(&self, filter: &TransactionHistoryFilter) -> usize {
        self.transactions
            .iter()
            .filter(|tx| filter.matches(tx))
            .count()
    }

    /// Get transactions for address
    pub fn get_transactions_for_address(&self, address: &Address) -> Vec<Transaction> {
        self.transactions
            .iter()
            .filter(|tx| tx.involves_address(address))
            .cloned()
            .collect()
    }

    /// Get pending transactions
    pub fn get_pending_transactions(&self) -> Vec<Transaction> {
        self.transactions
            .iter()
            .filter(|tx| tx.is_pending())
            .cloned()
            .collect()
    }

    /// Get confirmed transactions
    pub fn get_confirmed_transactions(&self) -> Vec<Transaction> {
        self.transactions
            .iter()
            .filter(|tx| tx.is_confirmed())
            .cloned()
            .collect()
    }

    /// Get failed transactions
    pub fn get_failed_transactions(&self) -> Vec<Transaction> {
        self.transactions
            .iter()
            .filter(|tx| tx.has_failed())
            .cloned()
            .collect()
    }

    /// Get transaction statistics
    pub fn get_statistics(&self) -> TransactionStatistics {
        let total_count = self.transactions.len();
        let pending_count = self.get_pending_transactions().len();
        let confirmed_count = self.get_confirmed_transactions().len();
        let failed_count = self.get_failed_transactions().len();

        let total_sent = self.transactions
            .iter()
            .filter(|tx| tx.tx_type.is_outgoing())
            .map(|tx| tx.total_output_amount())
            .sum();

        let total_received = self.transactions
            .iter()
            .filter(|tx| tx.tx_type.is_incoming())
            .map(|tx| tx.total_output_amount())
            .sum();

        let total_fees = self.transactions
            .iter()
            .map(|tx| tx.fee)
            .sum();

        TransactionStatistics {
            total_count,
            pending_count,
            confirmed_count,
            failed_count,
            total_sent,
            total_received,
            total_fees,
        }
    }

    /// Clear all transactions
    pub fn clear(&mut self) {
        self.transactions.clear();
    }

    /// Export transactions to JSON
    pub fn export_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(&self.transactions)
    }

    /// Import transactions from JSON
    pub fn import_json(&mut self, json: &str) -> Result<usize, serde_json::Error> {
        let imported_transactions: Vec<Transaction> = serde_json::from_str(json)?;
        let count = imported_transactions.len();

        for transaction in imported_transactions {
            self.add_transaction(transaction);
        }

        Ok(count)
    }
}

impl Default for TransactionHistory {
    fn default() -> Self {
        Self::new()
    }
}

/// Transaction statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionStatistics {
    pub total_count: usize,
    pub pending_count: usize,
    pub confirmed_count: usize,
    pub failed_count: usize,
    pub total_sent: u64,
    pub total_received: u64,
    pub total_fees: u64,
}

impl TransactionStatistics {
    /// Get net amount (received - sent)
    pub fn net_amount(&self) -> i64 {
        self.total_received as i64 - self.total_sent as i64
    }

    /// Get success rate
    pub fn success_rate(&self) -> f64 {
        if self.total_count == 0 {
            0.0
        } else {
            self.confirmed_count as f64 / self.total_count as f64
        }
    }

    /// Get average fee
    pub fn average_fee(&self) -> f64 {
        if self.total_count == 0 {
            0.0
        } else {
            self.total_fees as f64 / self.total_count as f64
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::CoinType;

    fn create_test_transaction(id: &str, tx_type: TransactionType, amount: u64) -> Transaction {
        let address = Address::new("test".to_string(), CoinType::Bitcoin, None, None);
        Transaction::new(
            CoinType::Bitcoin,
            tx_type,
            vec![],
            vec![super::super::types::TransactionOutput::new(amount, address, vec![], 0)],
            1000,
        )
    }

    #[test]
    fn test_transaction_history() {
        let mut history = TransactionHistory::new();

        let tx1 = create_test_transaction("tx1", TransactionType::Send, 50_000);
        let tx2 = create_test_transaction("tx2", TransactionType::Receive, 30_000);

        history.add_transaction(tx1.clone());
        history.add_transaction(tx2.clone());

        assert_eq!(history.transaction_count(), 2);
        assert!(history.get_transaction("tx1").is_some());
        assert!(history.get_transaction("tx2").is_some());
    }

    #[test]
    fn test_transaction_filter() {
        let mut history = TransactionHistory::new();

        let tx1 = create_test_transaction("tx1", TransactionType::Send, 50_000);
        let tx2 = create_test_transaction("tx2", TransactionType::Receive, 30_000);

        history.add_transaction(tx1);
        history.add_transaction(tx2);

        // Filter by type
        let filter = TransactionHistoryFilter::new().with_type(TransactionType::Send);
        let filtered = history.get_filtered_transactions(&filter);
        assert_eq!(filtered.len(), 1);
        assert_eq!(filtered[0].tx_type, TransactionType::Send);

        // Filter by amount range
        let filter = TransactionHistoryFilter::new().with_amount_range(Some(40_000), None);
        let filtered = history.get_filtered_transactions(&filter);
        assert_eq!(filtered.len(), 1);
        assert_eq!(filtered[0].total_output_amount(), 50_000);
    }

    #[test]
    fn test_transaction_statistics() {
        let mut history = TransactionHistory::new();

        let tx1 = create_test_transaction("tx1", TransactionType::Send, 50_000);
        let tx2 = create_test_transaction("tx2", TransactionType::Receive, 30_000);

        history.add_transaction(tx1);
        history.add_transaction(tx2);

        let stats = history.get_statistics();
        assert_eq!(stats.total_count, 2);
        assert_eq!(stats.total_sent, 50_000);
        assert_eq!(stats.total_received, 30_000);
        assert_eq!(stats.net_amount(), -20_000);
    }

    #[test]
    fn test_transaction_update() {
        let mut history = TransactionHistory::new();

        let mut tx = create_test_transaction("tx1", TransactionType::Send, 50_000);
        history.add_transaction(tx.clone());

        // Update transaction status
        tx.update_status(TransactionStatus::Confirmed);
        assert!(history.update_transaction(tx));

        let updated = history.get_transaction("tx1").unwrap();
        assert_eq!(updated.status, TransactionStatus::Confirmed);
    }

    #[test]
    fn test_export_import() {
        let mut history = TransactionHistory::new();

        let tx1 = create_test_transaction("tx1", TransactionType::Send, 50_000);
        let tx2 = create_test_transaction("tx2", TransactionType::Receive, 30_000);

        history.add_transaction(tx1);
        history.add_transaction(tx2);

        // Export
        let json = history.export_json().unwrap();
        assert!(!json.is_empty());

        // Import to new history
        let mut new_history = TransactionHistory::new();
        let count = new_history.import_json(&json).unwrap();
        assert_eq!(count, 2);
        assert_eq!(new_history.transaction_count(), 2);
    }
}