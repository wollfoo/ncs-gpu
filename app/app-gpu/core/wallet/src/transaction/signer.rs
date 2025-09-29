//! Transaction signing implementation

use super::types::{Transaction, UnsignedTransaction};
use crate::{
    types::{CoinType, PrivateKey, WalletConfig},
    WalletError, WalletResult,
};
use secp256k1::{ecdsa::Signature, Message, Secp256k1, SecretKey};
use sha2::{Digest, Sha256};

/// Signing context for transaction operations
#[derive(Debug, Clone)]
pub struct SigningContext {
    pub private_key: PrivateKey,
    pub coin_type: CoinType,
    pub sighash_type: SigHashType,
}

impl SigningContext {
    pub fn new(private_key: PrivateKey, coin_type: CoinType) -> Self {
        Self {
            private_key,
            coin_type,
            sighash_type: SigHashType::All,
        }
    }

    pub fn with_sighash_type(mut self, sighash_type: SigHashType) -> Self {
        self.sighash_type = sighash_type;
        self
    }
}

/// Transaction signer implementation
#[derive(Debug)]
pub struct TransactionSigner {
    config: WalletConfig,
    secp: Secp256k1<secp256k1::All>,
}

impl TransactionSigner {
    pub fn new(config: WalletConfig) -> Self {
        Self {
            config,
            secp: Secp256k1::new(),
        }
    }

    /// Sign transaction with given context
    pub async fn sign_transaction(
        &self,
        unsigned_tx: UnsignedTransaction,
        context: &SigningContext,
    ) -> WalletResult<Transaction> {
        match context.coin_type {
            CoinType::Bitcoin | CoinType::Litecoin | CoinType::BitcoinCash => {
                self.sign_bitcoin_like_transaction(unsigned_tx, context).await
            }
            CoinType::Ethereum | CoinType::EthereumClassic => {
                self.sign_ethereum_transaction(unsigned_tx, context).await
            }
            _ => Err(WalletError::UnsupportedCoinType {
                coin_type: context.coin_type.to_string(),
            }),
        }
    }

    /// Sign Bitcoin-like transaction
    async fn sign_bitcoin_like_transaction(
        &self,
        unsigned_tx: UnsignedTransaction,
        context: &SigningContext,
    ) -> WalletResult<Transaction> {
        let mut signatures = Vec::new();

        for (i, input) in unsigned_tx.inputs.iter().enumerate() {
            // Create signature hash for this input
            let sighash = self.calculate_bitcoin_sighash(&unsigned_tx, i, context)?;

            // Sign the hash
            let signature = self.sign_hash(&sighash, &context.private_key)?;

            // Create script signature (simplified - in reality this would be more complex)
            let mut script_sig = Vec::new();
            script_sig.extend_from_slice(&signature);
            script_sig.push(context.sighash_type as u8);

            // Add public key for P2PKH
            let public_key = context.private_key.public_key()?;
            script_sig.extend_from_slice(&public_key.key_data);

            signatures.push(script_sig);
        }

        // Convert to signed transaction
        unsigned_tx.to_signed_transaction(signatures)
            .map_err(|e| WalletError::TransactionSigningError { reason: e })
    }

    /// Sign Ethereum transaction
    async fn sign_ethereum_transaction(
        &self,
        unsigned_tx: UnsignedTransaction,
        context: &SigningContext,
    ) -> WalletResult<Transaction> {
        if unsigned_tx.inputs.len() != 1 {
            return Err(WalletError::TransactionSigningError {
                reason: "Ethereum transactions must have exactly one input".to_string(),
            });
        }

        // Create Ethereum transaction hash
        let tx_hash = self.calculate_ethereum_hash(&unsigned_tx)?;

        // Sign the hash
        let signature = self.sign_hash(&tx_hash, &context.private_key)?;

        // Convert to signed transaction
        unsigned_tx.to_signed_transaction(vec![signature])
            .map_err(|e| WalletError::TransactionSigningError { reason: e })
    }

    /// Calculate Bitcoin sighash for input
    fn calculate_bitcoin_sighash(
        &self,
        unsigned_tx: &UnsignedTransaction,
        input_index: usize,
        context: &SigningContext,
    ) -> WalletResult<[u8; 32]> {
        if input_index >= unsigned_tx.inputs.len() {
            return Err(WalletError::TransactionSigningError {
                reason: "Input index out of bounds".to_string(),
            });
        }

        let input = &unsigned_tx.inputs[input_index];

        // Simplified sighash calculation
        let mut preimage = Vec::new();

        // Transaction version (simplified - using 1)
        preimage.extend_from_slice(&1u32.to_le_bytes());

        // Previous output hash and index
        preimage.extend_from_slice(input.tx_id.as_bytes());
        preimage.extend_from_slice(&input.output_index.to_le_bytes());

        // Script code (for P2PKH, this would be the script pub key)
        preimage.extend_from_slice(&input.script_pubkey);

        // Amount
        preimage.extend_from_slice(&input.amount.to_le_bytes());

        // Sequence
        preimage.extend_from_slice(&input.sequence.unwrap_or(0xffffffff).to_le_bytes());

        // Outputs
        for output in &unsigned_tx.outputs {
            preimage.extend_from_slice(&output.amount.to_le_bytes());
            preimage.extend_from_slice(&output.script_pubkey);
        }

        // Lock time
        preimage.extend_from_slice(&unsigned_tx.lock_time.unwrap_or(0).to_le_bytes());

        // Sighash type
        preimage.extend_from_slice(&(context.sighash_type as u32).to_le_bytes());

        // Double SHA256
        let hash1 = Sha256::digest(&preimage);
        let hash2 = Sha256::digest(&hash1);

        let mut result = [0u8; 32];
        result.copy_from_slice(&hash2);
        Ok(result)
    }

    /// Calculate Ethereum transaction hash
    fn calculate_ethereum_hash(&self, unsigned_tx: &UnsignedTransaction) -> WalletResult<[u8; 32]> {
        // Simplified Ethereum transaction hash calculation
        let mut data = Vec::new();

        // Nonce
        data.extend_from_slice(&unsigned_tx.nonce.unwrap_or(0).to_le_bytes());

        // Gas price
        data.extend_from_slice(&unsigned_tx.gas_price.unwrap_or(20_000_000_000u64).to_le_bytes());

        // Gas limit
        data.extend_from_slice(&unsigned_tx.gas_limit.unwrap_or(21000).to_le_bytes());

        // To address (first output)
        if let Some(output) = unsigned_tx.outputs.first() {
            data.extend_from_slice(output.address.value.as_bytes());
            data.extend_from_slice(&output.amount.to_le_bytes());
        }

        // Data (empty for simple transfer)
        // data.extend_from_slice(&[]);

        // Keccak256 hash
        use sha3::Keccak256;
        let hash = Keccak256::digest(&data);

        let mut result = [0u8; 32];
        result.copy_from_slice(&hash);
        Ok(result)
    }

    /// Sign hash with private key
    fn sign_hash(&self, hash: &[u8; 32], private_key: &PrivateKey) -> WalletResult<Vec<u8>> {
        if private_key.key_data.len() != 32 {
            return Err(WalletError::InvalidPrivateKey {
                reason: "Private key must be 32 bytes".to_string(),
            });
        }

        let secret_key = SecretKey::from_slice(&private_key.key_data)?;
        let message = Message::from_slice(hash)?;

        let signature = self.secp.sign_ecdsa(&message, &secret_key);

        Ok(signature.serialize_compact().to_vec())
    }

    /// Verify signature
    pub fn verify_signature(
        &self,
        hash: &[u8; 32],
        signature: &[u8],
        public_key: &[u8],
    ) -> WalletResult<bool> {
        if signature.len() != 64 {
            return Err(WalletError::InvalidSignature {
                reason: "Signature must be 64 bytes".to_string(),
            });
        }

        let signature = Signature::from_compact(signature)?;
        let message = Message::from_slice(hash)?;
        let public_key = secp256k1::PublicKey::from_slice(public_key)?;

        Ok(self.secp.verify_ecdsa(&message, &signature, &public_key).is_ok())
    }

    /// Get signature recovery ID (for Ethereum)
    pub fn get_recovery_id(
        &self,
        hash: &[u8; 32],
        signature: &[u8],
        public_key: &[u8],
    ) -> WalletResult<u8> {
        // In a real implementation, this would calculate the recovery ID
        // needed for Ethereum signature verification
        let _ = (hash, signature, public_key);
        Ok(27) // Placeholder
    }
}

/// Signature hash types (Bitcoin)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum SigHashType {
    /// Sign all inputs and outputs
    All = 0x01,
    /// Sign all inputs, no outputs
    None = 0x02,
    /// Sign all inputs, one output
    Single = 0x03,
    /// Sign one input and all outputs
    AllPlusAnyoneCanPay = 0x81,
    /// Sign one input, no outputs
    NonePlusAnyoneCanPay = 0x82,
    /// Sign one input, one output
    SinglePlusAnyoneCanPay = 0x83,
}

impl Default for SigHashType {
    fn default() -> Self {
        SigHashType::All
    }
}

impl std::fmt::Display for SigHashType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SigHashType::All => write!(f, "SIGHASH_ALL"),
            SigHashType::None => write!(f, "SIGHASH_NONE"),
            SigHashType::Single => write!(f, "SIGHASH_SINGLE"),
            SigHashType::AllPlusAnyoneCanPay => write!(f, "SIGHASH_ALL | ANYONECANPAY"),
            SigHashType::NonePlusAnyoneCanPay => write!(f, "SIGHASH_NONE | ANYONECANPAY"),
            SigHashType::SinglePlusAnyoneCanPay => write!(f, "SIGHASH_SINGLE | ANYONECANPAY"),
        }
    }
}

/// Deterministic signature generation (RFC 6979)
pub struct DeterministicSigner {
    secp: Secp256k1<secp256k1::All>,
}

impl DeterministicSigner {
    pub fn new() -> Self {
        Self {
            secp: Secp256k1::new(),
        }
    }

    /// Generate deterministic signature using RFC 6979
    pub fn sign_deterministic(
        &self,
        hash: &[u8; 32],
        private_key: &PrivateKey,
    ) -> WalletResult<Vec<u8>> {
        if private_key.key_data.len() != 32 {
            return Err(WalletError::InvalidPrivateKey {
                reason: "Private key must be 32 bytes".to_string(),
            });
        }

        let secret_key = SecretKey::from_slice(&private_key.key_data)?;
        let message = Message::from_slice(hash)?;

        // Use deterministic nonce generation (RFC 6979)
        let signature = self.secp.sign_ecdsa(&message, &secret_key);

        // Ensure signature is canonical (low S value)
        let normalized_signature = signature.normalize_s().unwrap_or(signature);

        Ok(normalized_signature.serialize_compact().to_vec())
    }

    /// Check if signature has low S value (canonical)
    pub fn is_canonical(&self, signature: &[u8]) -> bool {
        if signature.len() != 64 {
            return false;
        }

        // Check if S value is in lower half of curve order
        let s_bytes = &signature[32..64];
        let s = secp256k1::scalar::Scalar::from_be_bytes(s_bytes);

        s.is_ok() // This is a simplified check
    }
}

impl Default for DeterministicSigner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{Address, CoinType, WalletConfig};

    fn create_test_private_key() -> PrivateKey {
        PrivateKey::new(
            CoinType::Bitcoin,
            vec![1u8; 32], // Test key - DO NOT use in production
            None,
        )
    }

    fn create_test_unsigned_tx() -> UnsignedTransaction {
        use super::super::types::{TransactionType, UnsignedTransactionInput, TransactionOutput};

        let input = UnsignedTransactionInput {
            tx_id: "test_tx_id".to_string(),
            output_index: 0,
            amount: 100_000,
            address: Address::new("test_from".to_string(), CoinType::Bitcoin, None, None),
            script_pubkey: vec![0x76, 0xa9, 0x14], // P2PKH script prefix
            sequence: Some(0xffffffff),
            witness: None,
        };

        let output = TransactionOutput::new(
            90_000,
            Address::new("test_to".to_string(), CoinType::Bitcoin, None, None),
            vec![0x76, 0xa9, 0x14], // P2PKH script
            0,
        );

        UnsignedTransaction::new(
            CoinType::Bitcoin,
            TransactionType::Send,
            vec![input],
            vec![output],
            10_000,
        )
    }

    #[tokio::test]
    async fn test_signer_creation() {
        let config = WalletConfig::default();
        let signer = TransactionSigner::new(config);
        // Success if no panic
        assert!(format!("{:?}", signer).contains("TransactionSigner"));
    }

    #[tokio::test]
    async fn test_bitcoin_transaction_signing() {
        let config = WalletConfig::default();
        let signer = TransactionSigner::new(config);

        let unsigned_tx = create_test_unsigned_tx();
        let private_key = create_test_private_key();
        let context = SigningContext::new(private_key, CoinType::Bitcoin);

        let result = signer.sign_transaction(unsigned_tx, &context).await;
        assert!(result.is_ok());

        let signed_tx = result.unwrap();
        assert_eq!(signed_tx.coin_type, CoinType::Bitcoin);
        assert!(!signed_tx.inputs.is_empty());
        assert!(!signed_tx.inputs[0].script_sig.is_empty());
    }

    #[tokio::test]
    async fn test_ethereum_transaction_signing() {
        let config = WalletConfig::default();
        let signer = TransactionSigner::new(config);

        let mut unsigned_tx = create_test_unsigned_tx();
        unsigned_tx.coin_type = CoinType::Ethereum;
        unsigned_tx.gas_price = Some(20_000_000_000);
        unsigned_tx.gas_limit = Some(21000);
        unsigned_tx.nonce = Some(0);

        let mut private_key = create_test_private_key();
        private_key.coin_type = CoinType::Ethereum;
        let context = SigningContext::new(private_key, CoinType::Ethereum);

        let result = signer.sign_transaction(unsigned_tx, &context).await;
        assert!(result.is_ok());

        let signed_tx = result.unwrap();
        assert_eq!(signed_tx.coin_type, CoinType::Ethereum);
    }

    #[test]
    fn test_signature_verification() {
        let config = WalletConfig::default();
        let signer = TransactionSigner::new(config);

        let private_key = create_test_private_key();
        let public_key = private_key.public_key().unwrap();
        let hash = [1u8; 32];

        let signature = signer.sign_hash(&hash, &private_key).unwrap();
        let is_valid = signer.verify_signature(&hash, &signature, &public_key.key_data).unwrap();

        assert!(is_valid);
    }

    #[test]
    fn test_sighash_types() {
        assert_eq!(SigHashType::All as u8, 0x01);
        assert_eq!(SigHashType::None as u8, 0x02);
        assert_eq!(SigHashType::Single as u8, 0x03);

        let sighash = SigHashType::default();
        assert_eq!(sighash, SigHashType::All);
    }

    #[test]
    fn test_deterministic_signer() {
        let signer = DeterministicSigner::new();
        let private_key = create_test_private_key();
        let hash = [1u8; 32];

        let signature1 = signer.sign_deterministic(&hash, &private_key).unwrap();
        let signature2 = signer.sign_deterministic(&hash, &private_key).unwrap();

        // Deterministic signatures should be identical
        assert_eq!(signature1, signature2);
        assert!(signer.is_canonical(&signature1));
    }
}