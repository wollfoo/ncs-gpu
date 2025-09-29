//! Transaction types and data structures

use crate::types::{Address, CoinType};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Transaction identifier
pub type TransactionId = String;

/// Transaction hash type
pub type TxHash = String;

/// Complete transaction representation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    /// Unique transaction ID
    pub id: TransactionId,
    /// Transaction hash (blockchain-specific)
    pub hash: Option<TxHash>,
    /// Coin type
    pub coin_type: CoinType,
    /// Transaction type
    pub tx_type: TransactionType,
    /// Transaction status
    pub status: TransactionStatus,
    /// Transaction inputs
    pub inputs: Vec<TransactionInput>,
    /// Transaction outputs
    pub outputs: Vec<TransactionOutput>,
    /// Transaction fee in smallest unit
    pub fee: u64,
    /// Gas price for Ethereum-like chains (in wei)
    pub gas_price: Option<u64>,
    /// Gas limit for Ethereum-like chains
    pub gas_limit: Option<u64>,
    /// Block height where transaction was confirmed
    pub block_height: Option<u64>,
    /// Block hash where transaction was confirmed
    pub block_hash: Option<String>,
    /// Number of confirmations
    pub confirmations: u32,
    /// Transaction creation timestamp
    pub created_at: DateTime<Utc>,
    /// Transaction confirmation timestamp
    pub confirmed_at: Option<DateTime<Utc>>,
    /// Raw transaction data (hex encoded)
    pub raw_data: Option<String>,
    /// Transaction size in bytes
    pub size: Option<u64>,
    /// Virtual size (for segwit transactions)
    pub vsize: Option<u64>,
    /// Transaction metadata
    pub metadata: TransactionMetadata,
}

impl Transaction {
    /// Create new transaction
    pub fn new(
        coin_type: CoinType,
        tx_type: TransactionType,
        inputs: Vec<TransactionInput>,
        outputs: Vec<TransactionOutput>,
        fee: u64,
    ) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            hash: None,
            coin_type,
            tx_type,
            status: TransactionStatus::Pending,
            inputs,
            outputs,
            fee,
            gas_price: None,
            gas_limit: None,
            block_height: None,
            block_hash: None,
            confirmations: 0,
            created_at: Utc::now(),
            confirmed_at: None,
            raw_data: None,
            size: None,
            vsize: None,
            metadata: TransactionMetadata::default(),
        }
    }

    /// Get total input amount
    pub fn total_input_amount(&self) -> u64 {
        self.inputs.iter().map(|input| input.amount).sum()
    }

    /// Get total output amount
    pub fn total_output_amount(&self) -> u64 {
        self.outputs.iter().map(|output| output.amount).sum()
    }

    /// Check if transaction is confirmed
    pub fn is_confirmed(&self) -> bool {
        matches!(self.status, TransactionStatus::Confirmed | TransactionStatus::Final)
    }

    /// Check if transaction is pending
    pub fn is_pending(&self) -> bool {
        matches!(self.status, TransactionStatus::Pending | TransactionStatus::Broadcasting)
    }

    /// Check if transaction has failed
    pub fn has_failed(&self) -> bool {
        matches!(self.status, TransactionStatus::Failed | TransactionStatus::Rejected)
    }

    /// Get effective fee rate (satoshis per byte)
    pub fn fee_rate(&self) -> Option<f64> {
        match (self.size, self.vsize) {
            (_, Some(vsize)) if vsize > 0 => Some(self.fee as f64 / vsize as f64),
            (Some(size), _) if size > 0 => Some(self.fee as f64 / size as f64),
            _ => None,
        }
    }

    /// Get confirmation score (0.0 to 1.0)
    pub fn confirmation_score(&self) -> f64 {
        let required_confirmations = self.coin_type.min_confirmations();
        if self.confirmations >= required_confirmations {
            1.0
        } else {
            self.confirmations as f64 / required_confirmations as f64
        }
    }

    /// Get transaction age in hours
    pub fn age_hours(&self) -> i64 {
        let now = Utc::now();
        now.signed_duration_since(self.created_at).num_hours()
    }

    /// Check if transaction involves given address
    pub fn involves_address(&self, address: &Address) -> bool {
        self.inputs.iter().any(|input| &input.address == address) ||
        self.outputs.iter().any(|output| &output.address == address)
    }

    /// Get net amount for given address (positive for receiving, negative for sending)
    pub fn net_amount_for_address(&self, address: &Address) -> i64 {
        let received: u64 = self.outputs.iter()
            .filter(|output| &output.address == address)
            .map(|output| output.amount)
            .sum();

        let sent: u64 = self.inputs.iter()
            .filter(|input| &input.address == address)
            .map(|input| input.amount)
            .sum();

        received as i64 - sent as i64
    }

    /// Update transaction status
    pub fn update_status(&mut self, status: TransactionStatus) {
        self.status = status;
        if matches!(status, TransactionStatus::Confirmed | TransactionStatus::Final) && self.confirmed_at.is_none() {
            self.confirmed_at = Some(Utc::now());
        }
    }

    /// Add confirmation
    pub fn add_confirmation(&mut self, block_height: u64, block_hash: String) {
        self.confirmations += 1;
        self.block_height = Some(block_height);
        self.block_hash = Some(block_hash);

        if self.confirmations >= self.coin_type.min_confirmations() {
            self.update_status(TransactionStatus::Final);
        } else if self.confirmations > 0 && self.status == TransactionStatus::Pending {
            self.update_status(TransactionStatus::Confirmed);
        }
    }
}

/// Unsigned transaction (before signing)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UnsignedTransaction {
    /// Transaction ID
    pub id: TransactionId,
    /// Coin type
    pub coin_type: CoinType,
    /// Transaction type
    pub tx_type: TransactionType,
    /// Transaction inputs (without signatures)
    pub inputs: Vec<UnsignedTransactionInput>,
    /// Transaction outputs
    pub outputs: Vec<TransactionOutput>,
    /// Estimated fee
    pub estimated_fee: u64,
    /// Lock time (for time-locked transactions)
    pub lock_time: Option<u64>,
    /// Sequence numbers for inputs
    pub sequence: Option<u32>,
    /// Gas price for Ethereum-like chains
    pub gas_price: Option<u64>,
    /// Gas limit for Ethereum-like chains
    pub gas_limit: Option<u64>,
    /// Nonce for Ethereum-like chains
    pub nonce: Option<u64>,
    /// Creation timestamp
    pub created_at: DateTime<Utc>,
}

impl UnsignedTransaction {
    /// Create new unsigned transaction
    pub fn new(
        coin_type: CoinType,
        tx_type: TransactionType,
        inputs: Vec<UnsignedTransactionInput>,
        outputs: Vec<TransactionOutput>,
        estimated_fee: u64,
    ) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            coin_type,
            tx_type,
            inputs,
            outputs,
            estimated_fee,
            lock_time: None,
            sequence: None,
            gas_price: None,
            gas_limit: None,
            nonce: None,
            created_at: Utc::now(),
        }
    }

    /// Get total input amount
    pub fn total_input_amount(&self) -> u64 {
        self.inputs.iter().map(|input| input.amount).sum()
    }

    /// Get total output amount
    pub fn total_output_amount(&self) -> u64 {
        self.outputs.iter().map(|output| output.amount).sum()
    }

    /// Validate transaction structure
    pub fn validate(&self) -> Result<(), String> {
        if self.inputs.is_empty() {
            return Err("Transaction must have at least one input".to_string());
        }

        if self.outputs.is_empty() {
            return Err("Transaction must have at least one output".to_string());
        }

        let input_total = self.total_input_amount();
        let output_total = self.total_output_amount();

        if input_total < output_total + self.estimated_fee {
            return Err("Insufficient input amount to cover outputs and fee".to_string());
        }

        // Validate outputs
        for output in &self.outputs {
            if output.amount == 0 {
                return Err("Output amount cannot be zero".to_string());
            }
        }

        Ok(())
    }

    /// Convert to signed transaction (requires signatures)
    pub fn to_signed_transaction(self, signatures: Vec<Vec<u8>>) -> Result<Transaction, String> {
        if signatures.len() != self.inputs.len() {
            return Err("Number of signatures must match number of inputs".to_string());
        }

        let mut signed_inputs = Vec::new();
        for (unsigned_input, signature) in self.inputs.into_iter().zip(signatures.into_iter()) {
            signed_inputs.push(TransactionInput {
                tx_id: unsigned_input.tx_id,
                output_index: unsigned_input.output_index,
                amount: unsigned_input.amount,
                address: unsigned_input.address,
                script_sig: signature,
                sequence: unsigned_input.sequence,
                witness: unsigned_input.witness,
            });
        }

        Ok(Transaction::new(
            self.coin_type,
            self.tx_type,
            signed_inputs,
            self.outputs,
            self.estimated_fee,
        ))
    }
}

/// Transaction input (UTXO reference)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionInput {
    /// Referenced transaction ID
    pub tx_id: TransactionId,
    /// Output index in referenced transaction
    pub output_index: u32,
    /// Amount being spent
    pub amount: u64,
    /// Address that owns the UTXO
    pub address: Address,
    /// Signature script (scriptSig)
    pub script_sig: Vec<u8>,
    /// Sequence number (for RBF and time locks)
    pub sequence: Option<u32>,
    /// Witness data (for SegWit)
    pub witness: Option<Vec<Vec<u8>>>,
}

/// Unsigned transaction input (before signing)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UnsignedTransactionInput {
    /// Referenced transaction ID
    pub tx_id: TransactionId,
    /// Output index in referenced transaction
    pub output_index: u32,
    /// Amount being spent
    pub amount: u64,
    /// Address that owns the UTXO
    pub address: Address,
    /// Script public key of the UTXO
    pub script_pubkey: Vec<u8>,
    /// Sequence number
    pub sequence: Option<u32>,
    /// Witness data template
    pub witness: Option<Vec<Vec<u8>>>,
}

/// Transaction output
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionOutput {
    /// Output amount
    pub amount: u64,
    /// Recipient address
    pub address: Address,
    /// Script public key (scriptPubKey)
    pub script_pubkey: Vec<u8>,
    /// Output index in transaction
    pub index: u32,
}

impl TransactionOutput {
    /// Create new transaction output
    pub fn new(amount: u64, address: Address, script_pubkey: Vec<u8>, index: u32) -> Self {
        Self {
            amount,
            address,
            script_pubkey,
            index,
        }
    }

    /// Check if output is dust
    pub fn is_dust(&self, dust_threshold: u64) -> bool {
        self.amount <= dust_threshold
    }
}

/// Transaction status enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TransactionStatus {
    /// Transaction created but not yet broadcasted
    Pending,
    /// Transaction is being broadcasted to network
    Broadcasting,
    /// Transaction broadcasted but not yet confirmed
    Broadcasted,
    /// Transaction has been confirmed (included in block)
    Confirmed,
    /// Transaction is final (enough confirmations)
    Final,
    /// Transaction failed or was rejected
    Failed,
    /// Transaction was rejected by network
    Rejected,
    /// Transaction was replaced (RBF)
    Replaced,
    /// Transaction was canceled
    Canceled,
}

impl TransactionStatus {
    /// Check if status indicates transaction is in mempool or confirmed
    pub fn is_active(&self) -> bool {
        matches!(
            self,
            TransactionStatus::Broadcasting |
            TransactionStatus::Broadcasted |
            TransactionStatus::Confirmed |
            TransactionStatus::Final
        )
    }

    /// Check if status indicates failure
    pub fn is_failed(&self) -> bool {
        matches!(
            self,
            TransactionStatus::Failed |
            TransactionStatus::Rejected |
            TransactionStatus::Canceled
        )
    }

    /// Get human-readable description
    pub fn description(&self) -> &'static str {
        match self {
            TransactionStatus::Pending => "Pending",
            TransactionStatus::Broadcasting => "Broadcasting",
            TransactionStatus::Broadcasted => "Broadcasted",
            TransactionStatus::Confirmed => "Confirmed",
            TransactionStatus::Final => "Final",
            TransactionStatus::Failed => "Failed",
            TransactionStatus::Rejected => "Rejected",
            TransactionStatus::Replaced => "Replaced",
            TransactionStatus::Canceled => "Canceled",
        }
    }
}

impl std::fmt::Display for TransactionStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.description())
    }
}

/// Transaction type enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TransactionType {
    /// Standard send transaction
    Send,
    /// Receive transaction
    Receive,
    /// Self-send (change)
    SelfSend,
    /// Multi-send transaction
    MultiSend,
    /// Contract interaction (Ethereum)
    ContractInteraction,
    /// Token transfer (ERC-20, etc.)
    TokenTransfer,
    /// Staking transaction
    Stake,
    /// Unstaking transaction
    Unstake,
    /// Mining reward
    MiningReward,
    /// Fee payment
    Fee,
    /// Other/Unknown
    Other,
}

impl TransactionType {
    /// Get human-readable description
    pub fn description(&self) -> &'static str {
        match self {
            TransactionType::Send => "Send",
            TransactionType::Receive => "Receive",
            TransactionType::SelfSend => "Self Send",
            TransactionType::MultiSend => "Multi Send",
            TransactionType::ContractInteraction => "Contract Interaction",
            TransactionType::TokenTransfer => "Token Transfer",
            TransactionType::Stake => "Stake",
            TransactionType::Unstake => "Unstake",
            TransactionType::MiningReward => "Mining Reward",
            TransactionType::Fee => "Fee",
            TransactionType::Other => "Other",
        }
    }

    /// Check if transaction type is outgoing
    pub fn is_outgoing(&self) -> bool {
        matches!(
            self,
            TransactionType::Send |
            TransactionType::MultiSend |
            TransactionType::ContractInteraction |
            TransactionType::TokenTransfer |
            TransactionType::Stake |
            TransactionType::Fee
        )
    }

    /// Check if transaction type is incoming
    pub fn is_incoming(&self) -> bool {
        matches!(
            self,
            TransactionType::Receive |
            TransactionType::MiningReward |
            TransactionType::Unstake
        )
    }
}

impl std::fmt::Display for TransactionType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.description())
    }
}

/// Transaction metadata for additional information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionMetadata {
    /// User-defined label
    pub label: Option<String>,
    /// Transaction notes
    pub notes: Option<String>,
    /// Tags for categorization
    pub tags: Vec<String>,
    /// Exchange rate at time of transaction
    pub exchange_rate: Option<f64>,
    /// Fiat currency used
    pub fiat_currency: Option<String>,
    /// Fiat amount at time of transaction
    pub fiat_amount: Option<f64>,
    /// Whether transaction was created by this wallet
    pub is_internal: bool,
    /// Privacy level
    pub privacy_level: PrivacyLevel,
    /// Additional custom fields
    pub custom_fields: HashMap<String, String>,
}

impl Default for TransactionMetadata {
    fn default() -> Self {
        Self {
            label: None,
            notes: None,
            tags: Vec::new(),
            exchange_rate: None,
            fiat_currency: None,
            fiat_amount: None,
            is_internal: true,
            privacy_level: PrivacyLevel::Normal,
            custom_fields: HashMap::new(),
        }
    }
}

/// Privacy level for transactions
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PrivacyLevel {
    /// Normal privacy (default)
    Normal,
    /// Enhanced privacy (coin mixing, etc.)
    Enhanced,
    /// Maximum privacy
    Maximum,
}

impl PrivacyLevel {
    pub fn description(&self) -> &'static str {
        match self {
            PrivacyLevel::Normal => "Normal",
            PrivacyLevel::Enhanced => "Enhanced",
            PrivacyLevel::Maximum => "Maximum",
        }
    }
}

impl std::fmt::Display for PrivacyLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.description())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::CoinType;

    fn create_test_address() -> Address {
        Address::new("test_address".to_string(), CoinType::Bitcoin, None, None)
    }

    #[test]
    fn test_transaction_creation() {
        let inputs = vec![TransactionInput {
            tx_id: "input_tx".to_string(),
            output_index: 0,
            amount: 100_000,
            address: create_test_address(),
            script_sig: vec![],
            sequence: Some(0xffffffff),
            witness: None,
        }];

        let outputs = vec![TransactionOutput::new(
            90_000,
            create_test_address(),
            vec![],
            0,
        )];

        let tx = Transaction::new(
            CoinType::Bitcoin,
            TransactionType::Send,
            inputs,
            outputs,
            10_000,
        );

        assert_eq!(tx.coin_type, CoinType::Bitcoin);
        assert_eq!(tx.tx_type, TransactionType::Send);
        assert_eq!(tx.total_input_amount(), 100_000);
        assert_eq!(tx.total_output_amount(), 90_000);
        assert_eq!(tx.fee, 10_000);
        assert!(tx.is_pending());
    }

    #[test]
    fn test_unsigned_transaction_validation() {
        let inputs = vec![UnsignedTransactionInput {
            tx_id: "input_tx".to_string(),
            output_index: 0,
            amount: 100_000,
            address: create_test_address(),
            script_pubkey: vec![],
            sequence: Some(0xffffffff),
            witness: None,
        }];

        let outputs = vec![TransactionOutput::new(
            90_000,
            create_test_address(),
            vec![],
            0,
        )];

        let unsigned_tx = UnsignedTransaction::new(
            CoinType::Bitcoin,
            TransactionType::Send,
            inputs,
            outputs,
            10_000,
        );

        assert!(unsigned_tx.validate().is_ok());

        // Test insufficient funds
        let mut invalid_tx = unsigned_tx.clone();
        invalid_tx.estimated_fee = 20_000; // More than available
        assert!(invalid_tx.validate().is_err());
    }

    #[test]
    fn test_transaction_status() {
        assert!(TransactionStatus::Confirmed.is_active());
        assert!(!TransactionStatus::Failed.is_active());
        assert!(TransactionStatus::Failed.is_failed());
        assert!(!TransactionStatus::Confirmed.is_failed());
    }

    #[test]
    fn test_transaction_type() {
        assert!(TransactionType::Send.is_outgoing());
        assert!(!TransactionType::Send.is_incoming());
        assert!(TransactionType::Receive.is_incoming());
        assert!(!TransactionType::Receive.is_outgoing());
    }

    #[test]
    fn test_transaction_net_amount() {
        let address = create_test_address();
        let other_address = Address::new("other".to_string(), CoinType::Bitcoin, None, None);

        let inputs = vec![TransactionInput {
            tx_id: "input_tx".to_string(),
            output_index: 0,
            amount: 100_000,
            address: address.clone(),
            script_sig: vec![],
            sequence: Some(0xffffffff),
            witness: None,
        }];

        let outputs = vec![
            TransactionOutput::new(50_000, address.clone(), vec![], 0),
            TransactionOutput::new(40_000, other_address, vec![], 1),
        ];

        let tx = Transaction::new(
            CoinType::Bitcoin,
            TransactionType::Send,
            inputs,
            outputs,
            10_000,
        );

        // Net amount for address: received 50k - sent 100k = -50k
        assert_eq!(tx.net_amount_for_address(&address), -50_000);
    }

    #[test]
    fn test_confirmation_score() {
        let mut tx = Transaction::new(
            CoinType::Bitcoin,
            TransactionType::Send,
            vec![],
            vec![],
            0,
        );

        tx.confirmations = 0;
        assert_eq!(tx.confirmation_score(), 0.0);

        tx.confirmations = 3; // Bitcoin needs 6 confirmations
        assert_eq!(tx.confirmation_score(), 0.5);

        tx.confirmations = 6;
        assert_eq!(tx.confirmation_score(), 1.0);

        tx.confirmations = 10;
        assert_eq!(tx.confirmation_score(), 1.0); // Capped at 1.0
    }

    #[test]
    fn test_dust_detection() {
        let output = TransactionOutput::new(100, create_test_address(), vec![], 0);
        assert!(output.is_dust(546)); // Bitcoin dust threshold
        assert!(!output.is_dust(50));
    }
}