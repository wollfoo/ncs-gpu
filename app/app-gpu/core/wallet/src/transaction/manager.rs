//! Transaction Manager implementation

use super::{
    fee_estimator::{FeeEstimator, FeeStrategy, SmartFeeEstimator},
    signer::{TransactionSigner, SigningContext},
    types::{Transaction, TransactionStatus, TransactionType, UnsignedTransaction},
    TransactionError, TransactionManagerTrait, TransactionHistoryFilter, UTXO,
};
use crate::{
    types::{Address, CoinType, PrivateKey, WalletConfig},
    WalletError, WalletResult,
};
use async_trait::async_trait;
use std::collections::HashMap;
use std::time::Duration;
use tokio::sync::RwLock;

/// Core transaction manager implementation
#[derive(Debug)]
pub struct TransactionManager {
    config: WalletConfig,
    fee_estimator: SmartFeeEstimator,
    signer: TransactionSigner,
    transaction_cache: RwLock<HashMap<String, Transaction>>,
    utxo_cache: RwLock<HashMap<Address, Vec<UTXO>>>,
}

impl TransactionManager {
    /// Create new transaction manager
    pub async fn new(config: WalletConfig) -> WalletResult<Self> {
        let fee_estimator = SmartFeeEstimator::new(Duration::from_secs(300));
        let signer = TransactionSigner::new(config.clone());

        Ok(Self {
            config,
            fee_estimator,
            signer,
            transaction_cache: RwLock::new(HashMap::new()),
            utxo_cache: RwLock::new(HashMap::new()),
        })
    }

    /// Initialize transaction manager
    pub async fn initialize(&self) -> WalletResult<()> {
        tracing::info!("Initializing transaction manager");
        // Initialize fee estimator with data sources
        // In a real implementation, you would add actual fee data sources here
        Ok(())
    }

    /// Get available UTXOs for address
    async fn get_available_utxos(&self, address: &Address) -> WalletResult<Vec<UTXO>> {
        let utxo_cache = self.utxo_cache.read().await;
        Ok(utxo_cache.get(address).cloned().unwrap_or_default())
    }

    /// Update UTXO cache
    pub async fn update_utxos(&self, address: Address, utxos: Vec<UTXO>) {
        let mut utxo_cache = self.utxo_cache.write().await;
        utxo_cache.insert(address, utxos);
    }

    /// Cache transaction
    async fn cache_transaction(&self, transaction: Transaction) {
        let mut cache = self.transaction_cache.write().await;
        cache.insert(transaction.id.clone(), transaction);
    }

    /// Get cached transaction
    async fn get_cached_transaction(&self, tx_id: &str) -> Option<Transaction> {
        let cache = self.transaction_cache.read().await;
        cache.get(tx_id).cloned()
    }

    /// Estimate transaction size
    fn estimate_transaction_size(
        &self,
        inputs: usize,
        outputs: usize,
        coin_type: CoinType,
    ) -> u64 {
        match coin_type {
            CoinType::Bitcoin | CoinType::Litecoin | CoinType::BitcoinCash => {
                // Approximate sizes for Bitcoin-like transactions
                let base_size = 10u64; // Version (4) + locktime (4) + input count (1) + output count (1)
                let input_size = inputs as u64 * 148; // ~148 bytes per input (varies by script type)
                let output_size = outputs as u64 * 34; // ~34 bytes per output

                base_size + input_size + output_size
            }
            CoinType::Ethereum | CoinType::EthereumClassic => {
                // Ethereum transaction size is more predictable
                21000 // Base gas cost for simple transfer
            }
            _ => {
                // Default to Bitcoin-like estimation
                let base_size = 10u64;
                let input_size = inputs as u64 * 148;
                let output_size = outputs as u64 * 34;

                base_size + input_size + output_size
            }
        }
    }
}

#[async_trait]
impl TransactionManagerTrait for TransactionManager {
    async fn create_transaction(
        &self,
        from_address: &Address,
        to_address: &Address,
        amount: u64,
        coin_type: CoinType,
        fee_strategy: FeeStrategy,
    ) -> WalletResult<UnsignedTransaction> {
        // Validate inputs
        if amount == 0 {
            return Err(TransactionError::AmountTooSmall {
                amount,
                minimum: 1,
            }.into());
        }

        to_address.validate()?;

        if to_address.coin_type != coin_type {
            return Err(TransactionError::InvalidRecipient {
                address: format!("Address {} is for {} but transaction is for {}",
                    to_address.value, to_address.coin_type, coin_type),
            }.into());
        }

        // Get available UTXOs
        let available_utxos = self.get_available_utxos(from_address).await?;
        if available_utxos.is_empty() {
            return Err(TransactionError::InsufficientFunds {
                required: amount,
                available: 0,
            }.into());
        }

        // Estimate transaction size and fee
        let tx_size = self.estimate_transaction_size(available_utxos.len(), 2, coin_type);
        let fee_estimate = self.fee_estimator
            .estimate_fee(coin_type, tx_size, fee_strategy)
            .await?;

        let total_required = amount + fee_estimate.total_fee;
        let total_available: u64 = available_utxos.iter()
            .filter(|utxo| utxo.is_spendable(1))
            .map(|utxo| utxo.amount)
            .sum();

        if total_available < total_required {
            return Err(TransactionError::InsufficientFunds {
                required: total_required,
                available: total_available,
            }.into());
        }

        // Select UTXOs (simplified selection - largest first)
        let mut selected_utxos = Vec::new();
        let mut selected_amount = 0u64;
        let mut sorted_utxos = available_utxos;
        sorted_utxos.sort_by(|a, b| b.amount.cmp(&a.amount));

        for utxo in sorted_utxos {
            if !utxo.is_spendable(1) {
                continue;
            }

            selected_utxos.push(utxo.clone());
            selected_amount += utxo.amount;

            if selected_amount >= total_required {
                break;
            }
        }

        // Create inputs
        let inputs = selected_utxos
            .into_iter()
            .map(|utxo| super::types::UnsignedTransactionInput {
                tx_id: utxo.tx_id,
                output_index: utxo.output_index,
                amount: utxo.amount,
                address: utxo.address,
                script_pubkey: utxo.script_pubkey,
                sequence: Some(0xffffffff),
                witness: None,
            })
            .collect();

        // Create outputs
        let mut outputs = vec![
            super::types::TransactionOutput::new(
                amount,
                to_address.clone(),
                vec![], // Script will be generated based on address type
                0,
            )
        ];

        // Add change output if necessary
        let change_amount = selected_amount - amount - fee_estimate.total_fee;
        if change_amount > 0 {
            outputs.push(super::types::TransactionOutput::new(
                change_amount,
                from_address.clone(),
                vec![],
                1,
            ));
        }

        let unsigned_tx = UnsignedTransaction::new(
            coin_type,
            TransactionType::Send,
            inputs,
            outputs,
            fee_estimate.total_fee,
        );

        // Validate transaction
        self.validate_transaction(&unsigned_tx).await?;

        Ok(unsigned_tx)
    }

    async fn sign_transaction(
        &self,
        unsigned_tx: UnsignedTransaction,
        private_key: &PrivateKey,
    ) -> WalletResult<Transaction> {
        let signing_context = SigningContext::new(
            private_key.clone(),
            unsigned_tx.coin_type,
        );

        let signed_tx = self.signer
            .sign_transaction(unsigned_tx, &signing_context)
            .await?;

        // Cache the signed transaction
        self.cache_transaction(signed_tx.clone()).await;

        Ok(signed_tx)
    }

    async fn estimate_fee(
        &self,
        from_address: &Address,
        _to_address: &Address,
        amount: u64,
        coin_type: CoinType,
        fee_strategy: FeeStrategy,
    ) -> WalletResult<u64> {
        let available_utxos = self.get_available_utxos(from_address).await?;

        // Estimate how many inputs we'll need
        let mut selected_amount = 0u64;
        let mut input_count = 0;
        let mut sorted_utxos = available_utxos;
        sorted_utxos.sort_by(|a, b| b.amount.cmp(&a.amount));

        for utxo in sorted_utxos {
            if !utxo.is_spendable(1) {
                continue;
            }

            input_count += 1;
            selected_amount += utxo.amount;

            // Rough estimate - we need enough for amount plus some fee buffer
            if selected_amount >= amount * 2 {
                break;
            }
        }

        let tx_size = self.estimate_transaction_size(input_count, 2, coin_type);
        let fee_estimate = self.fee_estimator
            .estimate_fee(coin_type, tx_size, fee_strategy)
            .await?;

        Ok(fee_estimate.total_fee)
    }

    async fn broadcast_transaction(&self, transaction: &Transaction) -> WalletResult<String> {
        // In a real implementation, this would broadcast to the network
        tracing::info!("Broadcasting transaction {}", transaction.id);

        // Update transaction status
        let mut tx = transaction.clone();
        tx.update_status(TransactionStatus::Broadcasting);
        self.cache_transaction(tx).await;

        // Simulate successful broadcast
        tokio::time::sleep(Duration::from_millis(100)).await;

        let mut tx = transaction.clone();
        tx.update_status(TransactionStatus::Broadcasted);
        tx.hash = Some(format!("hash_{}", transaction.id));
        self.cache_transaction(tx).await;

        Ok(transaction.id.clone())
    }

    async fn get_transaction_status(&self, tx_id: &str) -> WalletResult<TransactionStatus> {
        if let Some(tx) = self.get_cached_transaction(tx_id).await {
            Ok(tx.status)
        } else {
            Err(TransactionError::TransactionNotFound {
                tx_id: tx_id.to_string(),
            }.into())
        }
    }

    async fn get_transaction(&self, tx_id: &str) -> WalletResult<Option<Transaction>> {
        Ok(self.get_cached_transaction(tx_id).await)
    }

    async fn get_transaction_history(
        &self,
        address: &Address,
        _filter: Option<TransactionHistoryFilter>,
    ) -> WalletResult<Vec<Transaction>> {
        let cache = self.transaction_cache.read().await;
        let mut transactions: Vec<Transaction> = cache
            .values()
            .filter(|tx| tx.involves_address(address))
            .cloned()
            .collect();

        // Sort by creation time, newest first
        transactions.sort_by(|a, b| b.created_at.cmp(&a.created_at));

        Ok(transactions)
    }

    async fn get_pending_transactions(&self, address: &Address) -> WalletResult<Vec<Transaction>> {
        let cache = self.transaction_cache.read().await;
        let transactions: Vec<Transaction> = cache
            .values()
            .filter(|tx| tx.involves_address(address) && tx.is_pending())
            .cloned()
            .collect();

        Ok(transactions)
    }

    async fn cancel_transaction(&self, tx_id: &str) -> WalletResult<()> {
        let mut cache = self.transaction_cache.write().await;

        if let Some(tx) = cache.get_mut(tx_id) {
            if tx.is_pending() {
                tx.update_status(TransactionStatus::Canceled);
                tracing::info!("Transaction {} canceled", tx_id);
                Ok(())
            } else {
                Err(TransactionError::UnsupportedOperation {
                    operation: format!("Cannot cancel transaction in status: {}", tx.status),
                }.into())
            }
        } else {
            Err(TransactionError::TransactionNotFound {
                tx_id: tx_id.to_string(),
            }.into())
        }
    }

    async fn replace_transaction(
        &self,
        tx_id: &str,
        _new_fee_rate: super::fee_estimator::FeeRate,
    ) -> WalletResult<Transaction> {
        // RBF (Replace-By-Fee) implementation would go here
        // This is a placeholder implementation

        if let Some(_tx) = self.get_cached_transaction(tx_id).await {
            Err(TransactionError::UnsupportedOperation {
                operation: "RBF not implemented yet".to_string(),
            }.into())
        } else {
            Err(TransactionError::TransactionNotFound {
                tx_id: tx_id.to_string(),
            }.into())
        }
    }

    async fn create_multi_send_transaction(
        &self,
        from_address: &Address,
        outputs: Vec<(Address, u64)>,
        coin_type: CoinType,
        fee_strategy: FeeStrategy,
    ) -> WalletResult<UnsignedTransaction> {
        if outputs.is_empty() {
            return Err(TransactionError::ValidationError {
                reason: "Multi-send transaction must have at least one output".to_string(),
            }.into());
        }

        let total_amount: u64 = outputs.iter().map(|(_, amount)| *amount).sum();

        // Validate all recipient addresses
        for (address, amount) in &outputs {
            address.validate()?;
            if address.coin_type != coin_type {
                return Err(TransactionError::InvalidRecipient {
                    address: format!("Address {} is for {} but transaction is for {}",
                        address.value, address.coin_type, coin_type),
                }.into());
            }
            if *amount == 0 {
                return Err(TransactionError::AmountTooSmall {
                    amount: *amount,
                    minimum: 1,
                }.into());
            }
        }

        // Get available UTXOs
        let available_utxos = self.get_available_utxos(from_address).await?;
        if available_utxos.is_empty() {
            return Err(TransactionError::InsufficientFunds {
                required: total_amount,
                available: 0,
            }.into());
        }

        // Estimate transaction size and fee
        let tx_size = self.estimate_transaction_size(available_utxos.len(), outputs.len() + 1, coin_type);
        let fee_estimate = self.fee_estimator
            .estimate_fee(coin_type, tx_size, fee_strategy)
            .await?;

        let total_required = total_amount + fee_estimate.total_fee;
        let total_available: u64 = available_utxos.iter()
            .filter(|utxo| utxo.is_spendable(1))
            .map(|utxo| utxo.amount)
            .sum();

        if total_available < total_required {
            return Err(TransactionError::InsufficientFunds {
                required: total_required,
                available: total_available,
            }.into());
        }

        // Select UTXOs
        let mut selected_utxos = Vec::new();
        let mut selected_amount = 0u64;
        let mut sorted_utxos = available_utxos;
        sorted_utxos.sort_by(|a, b| b.amount.cmp(&a.amount));

        for utxo in sorted_utxos {
            if !utxo.is_spendable(1) {
                continue;
            }

            selected_utxos.push(utxo.clone());
            selected_amount += utxo.amount;

            if selected_amount >= total_required {
                break;
            }
        }

        // Create inputs
        let inputs = selected_utxos
            .into_iter()
            .map(|utxo| super::types::UnsignedTransactionInput {
                tx_id: utxo.tx_id,
                output_index: utxo.output_index,
                amount: utxo.amount,
                address: utxo.address,
                script_pubkey: utxo.script_pubkey,
                sequence: Some(0xffffffff),
                witness: None,
            })
            .collect();

        // Create outputs
        let mut tx_outputs = Vec::new();
        for (i, (address, amount)) in outputs.into_iter().enumerate() {
            tx_outputs.push(super::types::TransactionOutput::new(
                amount,
                address,
                vec![],
                i as u32,
            ));
        }

        // Add change output if necessary
        let change_amount = selected_amount - total_amount - fee_estimate.total_fee;
        if change_amount > 0 {
            tx_outputs.push(super::types::TransactionOutput::new(
                change_amount,
                from_address.clone(),
                vec![],
                tx_outputs.len() as u32,
            ));
        }

        let unsigned_tx = UnsignedTransaction::new(
            coin_type,
            TransactionType::MultiSend,
            inputs,
            tx_outputs,
            fee_estimate.total_fee,
        );

        // Validate transaction
        self.validate_transaction(&unsigned_tx).await?;

        Ok(unsigned_tx)
    }

    async fn validate_transaction(&self, transaction: &UnsignedTransaction) -> WalletResult<()> {
        // Basic structure validation
        transaction.validate()
            .map_err(|e| TransactionError::ValidationError { reason: e })?;

        // Network rules validation
        let network_rules = super::NetworkRules::for_coin_type(transaction.coin_type);

        // Check transaction size
        let estimated_size = self.estimate_transaction_size(
            transaction.inputs.len(),
            transaction.outputs.len(),
            transaction.coin_type,
        );

        if estimated_size > network_rules.maximum_transaction_size {
            return Err(TransactionError::TransactionTooLarge {
                size: estimated_size,
                maximum: network_rules.maximum_transaction_size,
            }.into());
        }

        // Check for dust outputs
        for output in &transaction.outputs {
            if output.amount < network_rules.minimum_output_value {
                return Err(TransactionError::DustOutput {
                    amount: output.amount,
                    threshold: network_rules.minimum_output_value,
                }.into());
            }
        }

        // Check fee reasonableness
        let fee_rate = transaction.estimated_fee as f64 / estimated_size as f64;
        if fee_rate < 1.0 {
            return Err(TransactionError::FeeTooLow {
                fee: transaction.estimated_fee,
                minimum: estimated_size, // 1 sat/byte minimum
            }.into());
        }

        if fee_rate > 1000.0 {
            return Err(TransactionError::FeeTooHigh {
                fee: transaction.estimated_fee,
                maximum: estimated_size * 1000, // 1000 sat/byte maximum
            }.into());
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{Address, CoinType, WalletConfig};
    use tempfile::TempDir;

    async fn create_test_manager() -> (TransactionManager, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let config = WalletConfig::default_with_path(temp_dir.path().to_path_buf());
        let manager = TransactionManager::new(config).await.unwrap();
        (manager, temp_dir)
    }

    fn create_test_address(name: &str) -> Address {
        Address::new(name.to_string(), CoinType::Bitcoin, None, None)
    }

    #[tokio::test]
    async fn test_transaction_manager_creation() {
        let (_manager, _temp_dir) = create_test_manager().await;
        // Success if no panic
    }

    #[tokio::test]
    async fn test_estimate_fee() {
        let (manager, _temp_dir) = create_test_manager().await;

        let from_address = create_test_address("from");
        let to_address = create_test_address("to");

        // Add some mock UTXOs
        let utxos = vec![
            UTXO::new(
                "tx1".to_string(),
                0,
                100_000,
                vec![],
                from_address.clone(),
            )
        ];
        manager.update_utxos(from_address.clone(), utxos).await;

        let fee = manager.estimate_fee(
            &from_address,
            &to_address,
            50_000,
            CoinType::Bitcoin,
            FeeStrategy::Standard,
        ).await;

        assert!(fee.is_ok());
        assert!(fee.unwrap() > 0);
    }

    #[tokio::test]
    async fn test_insufficient_funds() {
        let (manager, _temp_dir) = create_test_manager().await;

        let from_address = create_test_address("from");
        let to_address = create_test_address("to");

        // No UTXOs added, should fail
        let result = manager.create_transaction(
            &from_address,
            &to_address,
            50_000,
            CoinType::Bitcoin,
            FeeStrategy::Standard,
        ).await;

        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_transaction_creation() {
        let (manager, _temp_dir) = create_test_manager().await;

        let from_address = create_test_address("from");
        let to_address = create_test_address("to");

        // Add sufficient UTXOs
        let utxos = vec![
            UTXO::new(
                "tx1".to_string(),
                0,
                100_000,
                vec![],
                from_address.clone(),
            )
        ];
        manager.update_utxos(from_address.clone(), utxos).await;

        let unsigned_tx = manager.create_transaction(
            &from_address,
            &to_address,
            50_000,
            CoinType::Bitcoin,
            FeeStrategy::Standard,
        ).await;

        assert!(unsigned_tx.is_ok());
        let tx = unsigned_tx.unwrap();
        assert_eq!(tx.coin_type, CoinType::Bitcoin);
        assert!(!tx.inputs.is_empty());
        assert!(!tx.outputs.is_empty());
        assert!(tx.estimated_fee > 0);
    }

    #[tokio::test]
    async fn test_multi_send_transaction() {
        let (manager, _temp_dir) = create_test_manager().await;

        let from_address = create_test_address("from");
        let to_address1 = create_test_address("to1");
        let to_address2 = create_test_address("to2");

        // Add sufficient UTXOs
        let utxos = vec![
            UTXO::new(
                "tx1".to_string(),
                0,
                200_000,
                vec![],
                from_address.clone(),
            )
        ];
        manager.update_utxos(from_address.clone(), utxos).await;

        let outputs = vec![
            (to_address1, 30_000),
            (to_address2, 40_000),
        ];

        let unsigned_tx = manager.create_multi_send_transaction(
            &from_address,
            outputs,
            CoinType::Bitcoin,
            FeeStrategy::Standard,
        ).await;

        assert!(unsigned_tx.is_ok());
        let tx = unsigned_tx.unwrap();
        assert_eq!(tx.tx_type, TransactionType::MultiSend);
        assert_eq!(tx.outputs.len(), 3); // 2 outputs + 1 change
    }
}