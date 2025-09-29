//! Transaction Management Module
//!
//! Secure transaction creation, signing, and management for multi-coin wallets.
//! Supports various transaction types and fee estimation strategies.

pub mod builder;
pub mod fee_estimator;
pub mod history;
pub mod manager;
pub mod signer;
pub mod types;

pub use builder::{TransactionBuilder, TransactionBuilderError};
pub use fee_estimator::{FeeEstimator, FeeRate, FeeStrategy};
pub use history::{TransactionHistory, TransactionHistoryFilter};
pub use manager::TransactionManager;
pub use signer::{TransactionSigner, SigningContext};
pub use types::{
    Transaction, TransactionInput, TransactionOutput, TransactionStatus, TransactionType,
    UnsignedTransaction,
};

use crate::{
    key_management::ExtendedPrivateKey,
    types::{Address, Balance, CoinType, PrivateKey},
    WalletError, WalletResult,
};
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Transaction ID type
pub type TransactionId = String;

/// Transaction management interface
#[async_trait]
pub trait TransactionManagerTrait: Send + Sync {
    /// Create new unsigned transaction
    async fn create_transaction(
        &self,
        from_address: &Address,
        to_address: &Address,
        amount: u64,
        coin_type: CoinType,
        fee_strategy: FeeStrategy,
    ) -> WalletResult<UnsignedTransaction>;

    /// Sign transaction with private key
    async fn sign_transaction(
        &self,
        unsigned_tx: UnsignedTransaction,
        private_key: &PrivateKey,
    ) -> WalletResult<Transaction>;

    /// Estimate transaction fee
    async fn estimate_fee(
        &self,
        from_address: &Address,
        to_address: &Address,
        amount: u64,
        coin_type: CoinType,
        fee_strategy: FeeStrategy,
    ) -> WalletResult<u64>;

    /// Broadcast transaction to network
    async fn broadcast_transaction(&self, transaction: &Transaction) -> WalletResult<TransactionId>;

    /// Get transaction status
    async fn get_transaction_status(&self, tx_id: &TransactionId) -> WalletResult<TransactionStatus>;

    /// Get transaction by ID
    async fn get_transaction(&self, tx_id: &TransactionId) -> WalletResult<Option<Transaction>>;

    /// Get transaction history for address
    async fn get_transaction_history(
        &self,
        address: &Address,
        filter: Option<TransactionHistoryFilter>,
    ) -> WalletResult<Vec<Transaction>>;

    /// Get pending transactions
    async fn get_pending_transactions(&self, address: &Address) -> WalletResult<Vec<Transaction>>;

    /// Cancel pending transaction (if supported)
    async fn cancel_transaction(&self, tx_id: &TransactionId) -> WalletResult<()>;

    /// Replace transaction with higher fee (RBF)
    async fn replace_transaction(
        &self,
        tx_id: &TransactionId,
        new_fee_rate: FeeRate,
    ) -> WalletResult<Transaction>;

    /// Create multi-send transaction
    async fn create_multi_send_transaction(
        &self,
        from_address: &Address,
        outputs: Vec<(Address, u64)>,
        coin_type: CoinType,
        fee_strategy: FeeStrategy,
    ) -> WalletResult<UnsignedTransaction>;

    /// Validate transaction before signing
    async fn validate_transaction(&self, transaction: &UnsignedTransaction) -> WalletResult<()>;
}

/// Transaction validation context
#[derive(Debug, Clone)]
pub struct ValidationContext {
    pub available_balance: u64,
    pub minimum_fee: u64,
    pub maximum_fee: u64,
    pub network_rules: NetworkRules,
}

/// Network-specific transaction rules
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkRules {
    pub minimum_output_value: u64,
    pub maximum_transaction_size: u64,
    pub supports_rbf: bool,
    pub supports_cpfp: bool,
    pub confirmation_target: u32,
    pub dust_threshold: u64,
}

impl NetworkRules {
    pub fn bitcoin_mainnet() -> Self {
        Self {
            minimum_output_value: 546,     // Bitcoin dust limit
            maximum_transaction_size: 100_000, // 100KB
            supports_rbf: true,
            supports_cpfp: true,
            confirmation_target: 6,
            dust_threshold: 546,
        }
    }

    pub fn ethereum_mainnet() -> Self {
        Self {
            minimum_output_value: 1,       // 1 wei
            maximum_transaction_size: u64::MAX, // No size limit
            supports_rbf: false,
            supports_cpfp: false,
            confirmation_target: 12,
            dust_threshold: 1,
        }
    }

    pub fn litecoin_mainnet() -> Self {
        Self {
            minimum_output_value: 5460,    // Litecoin dust limit
            maximum_transaction_size: 100_000,
            supports_rbf: true,
            supports_cpfp: true,
            confirmation_target: 6,
            dust_threshold: 5460,
        }
    }

    pub fn for_coin_type(coin_type: CoinType) -> Self {
        match coin_type {
            CoinType::Bitcoin => Self::bitcoin_mainnet(),
            CoinType::Ethereum | CoinType::EthereumClassic => Self::ethereum_mainnet(),
            CoinType::Litecoin => Self::litecoin_mainnet(),
            CoinType::BitcoinCash => {
                let mut rules = Self::bitcoin_mainnet();
                rules.dust_threshold = 546;
                rules
            }
            CoinType::Dogecoin => {
                let mut rules = Self::bitcoin_mainnet();
                rules.minimum_output_value = 100_000_000; // 1 DOGE
                rules.dust_threshold = 100_000_000;
                rules
            }
            _ => Self::bitcoin_mainnet(), // Default to Bitcoin rules
        }
    }
}

/// Transaction building error types
#[derive(Debug, Clone, thiserror::Error)]
pub enum TransactionError {
    #[error("Insufficient funds: required {required}, available {available}")]
    InsufficientFunds { required: u64, available: u64 },

    #[error("Invalid recipient address: {address}")]
    InvalidRecipient { address: String },

    #[error("Amount too small: {amount} (minimum: {minimum})")]
    AmountTooSmall { amount: u64, minimum: u64 },

    #[error("Fee too low: {fee} (minimum: {minimum})")]
    FeeTooLow { fee: u64, minimum: u64 },

    #[error("Fee too high: {fee} (maximum: {maximum})")]
    FeeTooHigh { fee: u64, maximum: u64 },

    #[error("Transaction too large: {size} bytes (maximum: {maximum})")]
    TransactionTooLarge { size: u64, maximum: u64 },

    #[error("Dust output detected: {amount} (threshold: {threshold})")]
    DustOutput { amount: u64, threshold: u64 },

    #[error("Network error: {message}")]
    NetworkError { message: String },

    #[error("Signing failed: {reason}")]
    SigningError { reason: String },

    #[error("Invalid transaction format: {reason}")]
    InvalidFormat { reason: String },

    #[error("Transaction not found: {tx_id}")]
    TransactionNotFound { tx_id: String },

    #[error("Operation not supported: {operation}")]
    UnsupportedOperation { operation: String },

    #[error("Validation failed: {reason}")]
    ValidationError { reason: String },
}

impl From<TransactionError> for WalletError {
    fn from(err: TransactionError) -> Self {
        match err {
            TransactionError::InsufficientFunds { required, available } => {
                WalletError::InsufficientFunds { required, available }
            }
            TransactionError::InvalidRecipient { address } => {
                WalletError::InvalidAddress { address }
            }
            TransactionError::SigningError { reason } => {
                WalletError::TransactionSigningError { reason }
            }
            TransactionError::InvalidFormat { reason } => {
                WalletError::InvalidTransaction { reason }
            }
            TransactionError::NetworkError { message } => {
                WalletError::NetworkError { message }
            }
            _ => WalletError::InternalError {
                message: err.to_string(),
            },
        }
    }
}

/// UTXO (Unspent Transaction Output) representation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UTXO {
    pub tx_id: TransactionId,
    pub output_index: u32,
    pub amount: u64,
    pub script_pubkey: Vec<u8>,
    pub address: Address,
    pub confirmations: u32,
    pub is_coinbase: bool,
    pub block_height: Option<u64>,
}

impl UTXO {
    pub fn new(
        tx_id: TransactionId,
        output_index: u32,
        amount: u64,
        script_pubkey: Vec<u8>,
        address: Address,
    ) -> Self {
        Self {
            tx_id,
            output_index,
            amount,
            script_pubkey,
            address,
            confirmations: 0,
            is_coinbase: false,
            block_height: None,
        }
    }

    /// Check if UTXO is spendable (enough confirmations)
    pub fn is_spendable(&self, min_confirmations: u32) -> bool {
        if self.is_coinbase {
            self.confirmations >= 100 // Coinbase maturity
        } else {
            self.confirmations >= min_confirmations
        }
    }

    /// Check if UTXO is dust
    pub fn is_dust(&self, dust_threshold: u64) -> bool {
        self.amount <= dust_threshold
    }
}

/// UTXO selection strategy
#[derive(Debug, Clone, Copy)]
pub enum UTXOSelectionStrategy {
    /// Select largest UTXOs first (minimize change)
    LargestFirst,
    /// Select smallest UTXOs first (consolidate dust)
    SmallestFirst,
    /// Best effort to minimize fee
    MinimizeFee,
    /// Random selection (privacy)
    Random,
    /// Branch and bound (optimal selection)
    BranchAndBound,
}

/// UTXO selector for coin selection
pub struct UTXOSelector {
    strategy: UTXOSelectionStrategy,
    network_rules: NetworkRules,
}

impl UTXOSelector {
    pub fn new(strategy: UTXOSelectionStrategy, network_rules: NetworkRules) -> Self {
        Self {
            strategy,
            network_rules,
        }
    }

    /// Select UTXOs for transaction
    pub fn select_utxos(
        &self,
        available_utxos: &[UTXO],
        target_amount: u64,
        fee_rate: FeeRate,
    ) -> WalletResult<(Vec<UTXO>, u64)> {
        match self.strategy {
            UTXOSelectionStrategy::LargestFirst => {
                self.select_largest_first(available_utxos, target_amount, fee_rate)
            }
            UTXOSelectionStrategy::SmallestFirst => {
                self.select_smallest_first(available_utxos, target_amount, fee_rate)
            }
            UTXOSelectionStrategy::MinimizeFee => {
                self.select_minimize_fee(available_utxos, target_amount, fee_rate)
            }
            UTXOSelectionStrategy::Random => {
                self.select_random(available_utxos, target_amount, fee_rate)
            }
            UTXOSelectionStrategy::BranchAndBound => {
                self.select_branch_and_bound(available_utxos, target_amount, fee_rate)
            }
        }
    }

    fn select_largest_first(
        &self,
        available_utxos: &[UTXO],
        target_amount: u64,
        fee_rate: FeeRate,
    ) -> WalletResult<(Vec<UTXO>, u64)> {
        let mut sorted_utxos = available_utxos.to_vec();
        sorted_utxos.sort_by(|a, b| b.amount.cmp(&a.amount));

        let mut selected = Vec::new();
        let mut total_amount = 0u64;
        let mut estimated_fee = 0u64;

        for utxo in sorted_utxos {
            if !utxo.is_spendable(1) || utxo.is_dust(self.network_rules.dust_threshold) {
                continue;
            }

            selected.push(utxo);
            total_amount += utxo.amount;

            // Estimate fee based on transaction size
            estimated_fee = self.estimate_tx_fee(&selected, 2, fee_rate)?; // Assume 2 outputs

            if total_amount >= target_amount + estimated_fee {
                break;
            }
        }

        if total_amount < target_amount + estimated_fee {
            return Err(TransactionError::InsufficientFunds {
                required: target_amount + estimated_fee,
                available: total_amount,
            }.into());
        }

        Ok((selected, estimated_fee))
    }

    fn select_smallest_first(
        &self,
        available_utxos: &[UTXO],
        target_amount: u64,
        fee_rate: FeeRate,
    ) -> WalletResult<(Vec<UTXO>, u64)> {
        let mut sorted_utxos = available_utxos.to_vec();
        sorted_utxos.sort_by(|a, b| a.amount.cmp(&b.amount));

        let mut selected = Vec::new();
        let mut total_amount = 0u64;
        let mut estimated_fee = 0u64;

        for utxo in sorted_utxos {
            if !utxo.is_spendable(1) || utxo.is_dust(self.network_rules.dust_threshold) {
                continue;
            }

            selected.push(utxo);
            total_amount += utxo.amount;

            estimated_fee = self.estimate_tx_fee(&selected, 2, fee_rate)?;

            if total_amount >= target_amount + estimated_fee {
                break;
            }
        }

        if total_amount < target_amount + estimated_fee {
            return Err(TransactionError::InsufficientFunds {
                required: target_amount + estimated_fee,
                available: total_amount,
            }.into());
        }

        Ok((selected, estimated_fee))
    }

    fn select_minimize_fee(
        &self,
        available_utxos: &[UTXO],
        target_amount: u64,
        fee_rate: FeeRate,
    ) -> WalletResult<(Vec<UTXO>, u64)> {
        // Try to find the exact amount or close to it to minimize change output
        let mut best_selection: Option<(Vec<UTXO>, u64)> = None;
        let mut best_waste = u64::MAX;

        // Try different combinations (simplified approach)
        for combination in self.generate_utxo_combinations(available_utxos, 5) {
            let total_amount: u64 = combination.iter().map(|utxo| utxo.amount).sum();
            let estimated_fee = self.estimate_tx_fee(&combination, 2, fee_rate)?;

            if total_amount >= target_amount + estimated_fee {
                let change = total_amount - target_amount - estimated_fee;
                let waste = change + estimated_fee; // Simplified waste calculation

                if waste < best_waste {
                    best_waste = waste;
                    best_selection = Some((combination, estimated_fee));
                }
            }
        }

        best_selection.ok_or_else(|| {
            TransactionError::InsufficientFunds {
                required: target_amount,
                available: available_utxos.iter().map(|utxo| utxo.amount).sum(),
            }.into()
        })
    }

    fn select_random(
        &self,
        available_utxos: &[UTXO],
        target_amount: u64,
        fee_rate: FeeRate,
    ) -> WalletResult<(Vec<UTXO>, u64)> {
        use rand::seq::SliceRandom;
        use rand::thread_rng;

        let mut shuffled_utxos = available_utxos.to_vec();
        shuffled_utxos.shuffle(&mut thread_rng());

        let mut selected = Vec::new();
        let mut total_amount = 0u64;
        let mut estimated_fee = 0u64;

        for utxo in shuffled_utxos {
            if !utxo.is_spendable(1) || utxo.is_dust(self.network_rules.dust_threshold) {
                continue;
            }

            selected.push(utxo);
            total_amount += utxo.amount;

            estimated_fee = self.estimate_tx_fee(&selected, 2, fee_rate)?;

            if total_amount >= target_amount + estimated_fee {
                break;
            }
        }

        if total_amount < target_amount + estimated_fee {
            return Err(TransactionError::InsufficientFunds {
                required: target_amount + estimated_fee,
                available: total_amount,
            }.into());
        }

        Ok((selected, estimated_fee))
    }

    fn select_branch_and_bound(
        &self,
        available_utxos: &[UTXO],
        target_amount: u64,
        fee_rate: FeeRate,
    ) -> WalletResult<(Vec<UTXO>, u64)> {
        // Simplified branch and bound implementation
        // In a real implementation, this would be more sophisticated
        self.select_minimize_fee(available_utxos, target_amount, fee_rate)
    }

    fn generate_utxo_combinations(&self, utxos: &[UTXO], max_combinations: usize) -> Vec<Vec<UTXO>> {
        let mut combinations = Vec::new();

        // Generate single UTXO combinations
        for utxo in utxos {
            if utxo.is_spendable(1) && !utxo.is_dust(self.network_rules.dust_threshold) {
                combinations.push(vec![utxo.clone()]);
            }
        }

        // Generate pairs (simplified)
        for i in 0..utxos.len() {
            for j in i + 1..utxos.len() {
                if combinations.len() >= max_combinations {
                    break;
                }

                let utxo1 = &utxos[i];
                let utxo2 = &utxos[j];

                if utxo1.is_spendable(1) && utxo2.is_spendable(1) &&
                   !utxo1.is_dust(self.network_rules.dust_threshold) &&
                   !utxo2.is_dust(self.network_rules.dust_threshold) {
                    combinations.push(vec![utxo1.clone(), utxo2.clone()]);
                }
            }
        }

        combinations
    }

    fn estimate_tx_fee(&self, inputs: &[UTXO], outputs: usize, fee_rate: FeeRate) -> WalletResult<u64> {
        // Simplified fee estimation
        let input_size = inputs.len() as u64 * 148; // ~148 bytes per input
        let output_size = outputs as u64 * 34; // ~34 bytes per output
        let base_size = 10; // Base transaction overhead

        let total_size = input_size + output_size + base_size;
        let fee = total_size * fee_rate.satoshis_per_byte();

        Ok(fee)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{Address, CoinType};

    fn create_test_utxo(amount: u64, confirmations: u32) -> UTXO {
        UTXO {
            tx_id: "test_tx".to_string(),
            output_index: 0,
            amount,
            script_pubkey: vec![],
            address: Address::new("test_address".to_string(), CoinType::Bitcoin, None, None),
            confirmations,
            is_coinbase: false,
            block_height: Some(100),
        }
    }

    #[test]
    fn test_utxo_spendability() {
        let utxo = create_test_utxo(100_000, 6);
        assert!(utxo.is_spendable(1));
        assert!(utxo.is_spendable(6));
        assert!(!utxo.is_spendable(10));

        let coinbase_utxo = UTXO {
            is_coinbase: true,
            confirmations: 50,
            ..utxo
        };
        assert!(!coinbase_utxo.is_spendable(1)); // Coinbase needs 100 confirmations
    }

    #[test]
    fn test_utxo_dust_detection() {
        let utxo = create_test_utxo(100, 6);
        assert!(utxo.is_dust(546)); // Bitcoin dust threshold
        assert!(!utxo.is_dust(50));
    }

    #[tokio::test]
    async fn test_utxo_selection_largest_first() {
        let utxos = vec![
            create_test_utxo(50_000, 6),
            create_test_utxo(100_000, 6),
            create_test_utxo(25_000, 6),
        ];

        let network_rules = NetworkRules::bitcoin_mainnet();
        let selector = UTXOSelector::new(UTXOSelectionStrategy::LargestFirst, network_rules);
        let fee_rate = FeeRate::new(1); // 1 sat/byte

        let result = selector.select_utxos(&utxos, 75_000, fee_rate);
        assert!(result.is_ok());

        let (selected, _fee) = result.unwrap();
        assert_eq!(selected.len(), 1); // Should select the 100k UTXO
        assert_eq!(selected[0].amount, 100_000);
    }

    #[tokio::test]
    async fn test_utxo_selection_insufficient_funds() {
        let utxos = vec![
            create_test_utxo(10_000, 6),
            create_test_utxo(20_000, 6),
        ];

        let network_rules = NetworkRules::bitcoin_mainnet();
        let selector = UTXOSelector::new(UTXOSelectionStrategy::LargestFirst, network_rules);
        let fee_rate = FeeRate::new(1);

        let result = selector.select_utxos(&utxos, 100_000, fee_rate);
        assert!(result.is_err());
    }

    #[test]
    fn test_network_rules() {
        let bitcoin_rules = NetworkRules::bitcoin_mainnet();
        assert_eq!(bitcoin_rules.dust_threshold, 546);
        assert!(bitcoin_rules.supports_rbf);

        let ethereum_rules = NetworkRules::ethereum_mainnet();
        assert_eq!(ethereum_rules.dust_threshold, 1);
        assert!(!ethereum_rules.supports_rbf);
    }
}