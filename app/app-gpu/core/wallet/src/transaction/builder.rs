//! Transaction builder for constructing transactions

use super::types::{TransactionOutput, TransactionType, UnsignedTransaction, UnsignedTransactionInput};
use crate::{
    types::{Address, CoinType},
    WalletError, WalletResult,
};
use thiserror::Error;

/// Transaction builder errors
#[derive(Error, Debug, Clone)]
pub enum TransactionBuilderError {
    #[error("No inputs provided")]
    NoInputs,

    #[error("No outputs provided")]
    NoOutputs,

    #[error("Invalid amount: {amount}")]
    InvalidAmount { amount: u64 },

    #[error("Output already exists for address: {address}")]
    DuplicateOutput { address: String },
}

/// Transaction builder for step-by-step transaction construction
#[derive(Debug, Default)]
pub struct TransactionBuilder {
    coin_type: Option<CoinType>,
    tx_type: Option<TransactionType>,
    inputs: Vec<UnsignedTransactionInput>,
    outputs: Vec<TransactionOutput>,
    estimated_fee: Option<u64>,
    gas_price: Option<u64>,
    gas_limit: Option<u64>,
    nonce: Option<u64>,
    lock_time: Option<u64>,
}

impl TransactionBuilder {
    /// Create new transaction builder
    pub fn new() -> Self {
        Self::default()
    }

    /// Set coin type
    pub fn coin_type(mut self, coin_type: CoinType) -> Self {
        self.coin_type = Some(coin_type);
        self
    }

    /// Set transaction type
    pub fn transaction_type(mut self, tx_type: TransactionType) -> Self {
        self.tx_type = Some(tx_type);
        self
    }

    /// Add input
    pub fn add_input(
        mut self,
        tx_id: String,
        output_index: u32,
        amount: u64,
        address: Address,
        script_pubkey: Vec<u8>,
    ) -> Self {
        self.inputs.push(UnsignedTransactionInput {
            tx_id,
            output_index,
            amount,
            address,
            script_pubkey,
            sequence: Some(0xffffffff),
            witness: None,
        });
        self
    }

    /// Add output
    pub fn add_output(mut self, amount: u64, address: Address) -> Result<Self, TransactionBuilderError> {
        if amount == 0 {
            return Err(TransactionBuilderError::InvalidAmount { amount });
        }

        // Check for duplicate outputs to same address
        if self.outputs.iter().any(|output| output.address == address) {
            return Err(TransactionBuilderError::DuplicateOutput {
                address: address.value.clone(),
            });
        }

        self.outputs.push(TransactionOutput::new(
            amount,
            address,
            vec![], // Script will be generated based on address
            self.outputs.len() as u32,
        ));

        Ok(self)
    }

    /// Set estimated fee
    pub fn estimated_fee(mut self, fee: u64) -> Self {
        self.estimated_fee = Some(fee);
        self
    }

    /// Set gas price (Ethereum)
    pub fn gas_price(mut self, gas_price: u64) -> Self {
        self.gas_price = Some(gas_price);
        self
    }

    /// Set gas limit (Ethereum)
    pub fn gas_limit(mut self, gas_limit: u64) -> Self {
        self.gas_limit = Some(gas_limit);
        self
    }

    /// Set nonce (Ethereum)
    pub fn nonce(mut self, nonce: u64) -> Self {
        self.nonce = Some(nonce);
        self
    }

    /// Set lock time
    pub fn lock_time(mut self, lock_time: u64) -> Self {
        self.lock_time = Some(lock_time);
        self
    }

    /// Build the unsigned transaction
    pub fn build(self) -> Result<UnsignedTransaction, TransactionBuilderError> {
        let coin_type = self.coin_type.ok_or_else(|| {
            WalletError::InvalidInput {
                message: "Coin type must be specified".to_string(),
            }
        }).map_err(|_| TransactionBuilderError::NoInputs)?;

        let tx_type = self.tx_type.unwrap_or(TransactionType::Send);

        if self.inputs.is_empty() {
            return Err(TransactionBuilderError::NoInputs);
        }

        if self.outputs.is_empty() {
            return Err(TransactionBuilderError::NoOutputs);
        }

        let estimated_fee = self.estimated_fee.unwrap_or(0);

        let mut unsigned_tx = UnsignedTransaction::new(
            coin_type,
            tx_type,
            self.inputs,
            self.outputs,
            estimated_fee,
        );

        // Set Ethereum-specific fields
        unsigned_tx.gas_price = self.gas_price;
        unsigned_tx.gas_limit = self.gas_limit;
        unsigned_tx.nonce = self.nonce;
        unsigned_tx.lock_time = self.lock_time;

        Ok(unsigned_tx)
    }

    /// Get current input count
    pub fn input_count(&self) -> usize {
        self.inputs.len()
    }

    /// Get current output count
    pub fn output_count(&self) -> usize {
        self.outputs.len()
    }

    /// Get total input amount
    pub fn total_input_amount(&self) -> u64 {
        self.inputs.iter().map(|input| input.amount).sum()
    }

    /// Get total output amount
    pub fn total_output_amount(&self) -> u64 {
        self.outputs.iter().map(|output| output.amount).sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::CoinType;

    fn create_test_address(name: &str) -> Address {
        Address::new(name.to_string(), CoinType::Bitcoin, None, None)
    }

    #[test]
    fn test_transaction_builder() {
        let builder = TransactionBuilder::new()
            .coin_type(CoinType::Bitcoin)
            .transaction_type(TransactionType::Send)
            .add_input(
                "input_tx".to_string(),
                0,
                100_000,
                create_test_address("from"),
                vec![],
            )
            .add_output(90_000, create_test_address("to")).unwrap()
            .estimated_fee(10_000);

        assert_eq!(builder.input_count(), 1);
        assert_eq!(builder.output_count(), 1);
        assert_eq!(builder.total_input_amount(), 100_000);
        assert_eq!(builder.total_output_amount(), 90_000);

        let unsigned_tx = builder.build().unwrap();
        assert_eq!(unsigned_tx.coin_type, CoinType::Bitcoin);
        assert_eq!(unsigned_tx.tx_type, TransactionType::Send);
        assert_eq!(unsigned_tx.estimated_fee, 10_000);
    }

    #[test]
    fn test_builder_validation() {
        // Test no inputs
        let result = TransactionBuilder::new()
            .coin_type(CoinType::Bitcoin)
            .add_output(90_000, create_test_address("to")).unwrap()
            .build();
        assert!(matches!(result, Err(TransactionBuilderError::NoInputs)));

        // Test no outputs
        let result = TransactionBuilder::new()
            .coin_type(CoinType::Bitcoin)
            .add_input("tx".to_string(), 0, 100_000, create_test_address("from"), vec![])
            .build();
        assert!(matches!(result, Err(TransactionBuilderError::NoOutputs)));

        // Test invalid amount
        let result = TransactionBuilder::new()
            .add_output(0, create_test_address("to"));
        assert!(matches!(result, Err(TransactionBuilderError::InvalidAmount { amount: 0 })));
    }

    #[test]
    fn test_duplicate_output() {
        let address = create_test_address("duplicate");
        let builder = TransactionBuilder::new()
            .add_output(50_000, address.clone()).unwrap();

        let result = builder.add_output(30_000, address);
        assert!(matches!(result, Err(TransactionBuilderError::DuplicateOutput { .. })));
    }
}