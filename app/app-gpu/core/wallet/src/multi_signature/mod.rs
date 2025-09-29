//! Multi-signature Wallet Support
//!
//! Implementation of multi-signature wallets for enhanced security requiring multiple
//! private keys to authorize transactions.

pub mod multisig_wallet;
pub mod script;
pub mod threshold;

pub use multisig_wallet::{MultiSigWallet, MultiSigWalletManager};
pub use script::{MultiSigScript, ScriptBuilder};
pub use threshold::{SignatureThreshold, ThresholdPolicy};

use crate::{
    key_management::ExtendedPrivateKey,
    types::{Address, CoinType, PublicKey},
    WalletError, WalletResult,
};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Multi-signature wallet identifier
pub type MultiSigWalletId = Uuid;

/// Multi-signature wallet interface
#[async_trait]
pub trait MultiSigWalletTrait: Send + Sync {
    /// Create new multi-signature wallet
    async fn create_multisig_wallet(
        &self,
        name: String,
        public_keys: Vec<PublicKey>,
        threshold: u32,
        coin_type: CoinType,
    ) -> WalletResult<MultiSigWallet>;

    /// Add signer to existing wallet
    async fn add_signer(
        &self,
        wallet_id: &MultiSigWalletId,
        public_key: PublicKey,
    ) -> WalletResult<()>;

    /// Remove signer from wallet (if threshold allows)
    async fn remove_signer(
        &self,
        wallet_id: &MultiSigWalletId,
        public_key: &PublicKey,
    ) -> WalletResult<()>;

    /// Generate multi-signature address
    async fn generate_address(
        &self,
        wallet_id: &MultiSigWalletId,
    ) -> WalletResult<Address>;

    /// Create partial signature for transaction
    async fn create_partial_signature(
        &self,
        wallet_id: &MultiSigWalletId,
        transaction_data: &[u8],
        private_key: &ExtendedPrivateKey,
    ) -> WalletResult<PartialSignature>;

    /// Combine partial signatures to create complete signature
    async fn combine_signatures(
        &self,
        wallet_id: &MultiSigWalletId,
        partial_signatures: Vec<PartialSignature>,
    ) -> WalletResult<CompleteSignature>;

    /// Verify multi-signature
    async fn verify_multisig(
        &self,
        wallet_id: &MultiSigWalletId,
        message: &[u8],
        signature: &CompleteSignature,
    ) -> WalletResult<bool>;

    /// Get wallet information
    async fn get_wallet(&self, wallet_id: &MultiSigWalletId) -> WalletResult<Option<MultiSigWallet>>;

    /// List all multi-signature wallets
    async fn list_wallets(&self) -> WalletResult<Vec<MultiSigWallet>>;

    /// Update signature threshold
    async fn update_threshold(
        &self,
        wallet_id: &MultiSigWalletId,
        new_threshold: u32,
        authorizations: Vec<PartialSignature>,
    ) -> WalletResult<()>;
}

/// Multi-signature wallet information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MultiSigWallet {
    /// Unique wallet identifier
    pub id: MultiSigWalletId,
    /// Wallet name
    pub name: String,
    /// Required signature threshold
    pub threshold: u32,
    /// Total number of signers
    pub total_signers: u32,
    /// Public keys of all signers
    pub public_keys: Vec<PublicKey>,
    /// Coin type supported
    pub coin_type: CoinType,
    /// Multi-signature script
    pub script: MultiSigScript,
    /// Wallet addresses generated
    pub addresses: Vec<Address>,
    /// Creation timestamp
    pub created_at: chrono::DateTime<chrono::Utc>,
    /// Last modified timestamp
    pub last_modified: chrono::DateTime<chrono::Utc>,
    /// Wallet metadata
    pub metadata: MultiSigMetadata,
}

impl MultiSigWallet {
    /// Create new multi-signature wallet
    pub fn new(
        name: String,
        public_keys: Vec<PublicKey>,
        threshold: u32,
        coin_type: CoinType,
    ) -> WalletResult<Self> {
        if threshold == 0 {
            return Err(WalletError::InvalidSignatureThreshold { threshold });
        }

        if threshold > public_keys.len() as u32 {
            return Err(WalletError::InvalidSignatureThreshold { threshold });
        }

        if public_keys.is_empty() {
            return Err(WalletError::InvalidInput {
                message: "At least one public key is required".to_string(),
            });
        }

        // Create multi-signature script
        let script = MultiSigScript::new(threshold, public_keys.clone())?;

        let now = chrono::Utc::now();

        Ok(Self {
            id: Uuid::new_v4(),
            name,
            threshold,
            total_signers: public_keys.len() as u32,
            public_keys,
            coin_type,
            script,
            addresses: Vec::new(),
            created_at: now,
            last_modified: now,
            metadata: MultiSigMetadata::default(),
        })
    }

    /// Check if threshold is met by signatures
    pub fn is_threshold_met(&self, signature_count: u32) -> bool {
        signature_count >= self.threshold
    }

    /// Validate public key is part of this wallet
    pub fn contains_public_key(&self, public_key: &PublicKey) -> bool {
        self.public_keys.iter().any(|pk| pk == public_key)
    }

    /// Get signing policy
    pub fn signing_policy(&self) -> SigningPolicy {
        SigningPolicy {
            threshold: self.threshold,
            total_signers: self.total_signers,
            require_all_signers: self.threshold == self.total_signers,
            timeout_hours: self.metadata.signing_timeout_hours,
        }
    }

    /// Update last modified timestamp
    pub fn touch(&mut self) {
        self.last_modified = chrono::Utc::now();
    }

    /// Add new address
    pub fn add_address(&mut self, address: Address) {
        if !self.addresses.contains(&address) {
            self.addresses.push(address);
            self.touch();
        }
    }

    /// Get security level based on configuration
    pub fn security_level(&self) -> SecurityLevel {
        let threshold_ratio = self.threshold as f32 / self.total_signers as f32;

        match (self.total_signers, threshold_ratio) {
            (1, _) => SecurityLevel::Low,
            (2, ratio) if ratio >= 1.0 => SecurityLevel::High, // 2-of-2
            (2, _) => SecurityLevel::Medium, // 2-of-1
            (3.., ratio) if ratio >= 0.67 => SecurityLevel::High, // 2-of-3 or higher
            (3.., ratio) if ratio >= 0.5 => SecurityLevel::Medium,
            _ => SecurityLevel::Low,
        }
    }
}

/// Multi-signature wallet metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MultiSigMetadata {
    /// Description of the wallet
    pub description: Option<String>,
    /// Organizations or parties involved
    pub parties: Vec<String>,
    /// Signing timeout in hours
    pub signing_timeout_hours: u32,
    /// Require sequential signing order
    pub sequential_signing: bool,
    /// Custom metadata fields
    pub custom_fields: HashMap<String, String>,
}

impl Default for MultiSigMetadata {
    fn default() -> Self {
        Self {
            description: None,
            parties: Vec::new(),
            signing_timeout_hours: 24, // 24 hours default
            sequential_signing: false,
            custom_fields: HashMap::new(),
        }
    }
}

/// Partial signature from one signer
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PartialSignature {
    /// Signer's public key
    pub public_key: PublicKey,
    /// Signature data
    pub signature: Vec<u8>,
    /// Signature timestamp
    pub created_at: chrono::DateTime<chrono::Utc>,
    /// Optional signer identifier/name
    pub signer_id: Option<String>,
}

impl PartialSignature {
    /// Create new partial signature
    pub fn new(public_key: PublicKey, signature: Vec<u8>, signer_id: Option<String>) -> Self {
        Self {
            public_key,
            signature,
            created_at: chrono::Utc::now(),
            signer_id,
        }
    }

    /// Check if signature is expired
    pub fn is_expired(&self, timeout_hours: u32) -> bool {
        let now = chrono::Utc::now();
        let elapsed = now.signed_duration_since(self.created_at);
        elapsed.num_hours() > timeout_hours as i64
    }
}

/// Complete multi-signature
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompleteSignature {
    /// All partial signatures
    pub partial_signatures: Vec<PartialSignature>,
    /// Combined signature script
    pub script_sig: Vec<u8>,
    /// Signature completion timestamp
    pub completed_at: chrono::DateTime<chrono::Utc>,
    /// Threshold that was met
    pub threshold_met: u32,
}

impl CompleteSignature {
    /// Create new complete signature
    pub fn new(
        partial_signatures: Vec<PartialSignature>,
        script_sig: Vec<u8>,
        threshold_met: u32,
    ) -> Self {
        Self {
            partial_signatures,
            script_sig,
            completed_at: chrono::Utc::now(),
            threshold_met,
        }
    }

    /// Get signers count
    pub fn signer_count(&self) -> u32 {
        self.partial_signatures.len() as u32
    }

    /// Check if signature is valid (threshold met)
    pub fn is_valid(&self, required_threshold: u32) -> bool {
        self.threshold_met >= required_threshold && self.signer_count() >= required_threshold
    }
}

/// Signing policy for multi-signature operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SigningPolicy {
    /// Required threshold
    pub threshold: u32,
    /// Total number of signers
    pub total_signers: u32,
    /// Whether all signers must sign (for unanimous decisions)
    pub require_all_signers: bool,
    /// Signing timeout in hours
    pub timeout_hours: u32,
}

impl SigningPolicy {
    /// Check if signing requirements are met
    pub fn requirements_met(&self, signature_count: u32) -> bool {
        if self.require_all_signers {
            signature_count == self.total_signers
        } else {
            signature_count >= self.threshold
        }
    }

    /// Get minimum required signatures
    pub fn min_required_signatures(&self) -> u32 {
        if self.require_all_signers {
            self.total_signers
        } else {
            self.threshold
        }
    }
}

/// Security level for multi-signature wallets
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SecurityLevel {
    Low,
    Medium,
    High,
    Maximum,
}

impl SecurityLevel {
    pub fn description(&self) -> &'static str {
        match self {
            SecurityLevel::Low => "Low security (single signature or low threshold)",
            SecurityLevel::Medium => "Medium security (moderate threshold)",
            SecurityLevel::High => "High security (high threshold)",
            SecurityLevel::Maximum => "Maximum security (unanimous required)",
        }
    }
}

impl std::fmt::Display for SecurityLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SecurityLevel::Low => write!(f, "Low"),
            SecurityLevel::Medium => write!(f, "Medium"),
            SecurityLevel::High => write!(f, "High"),
            SecurityLevel::Maximum => write!(f, "Maximum"),
        }
    }
}

/// Multi-signature transaction builder
pub struct MultiSigTransactionBuilder {
    wallet: MultiSigWallet,
    transaction_data: Option<Vec<u8>>,
    partial_signatures: Vec<PartialSignature>,
    signing_deadline: Option<chrono::DateTime<chrono::Utc>>,
}

impl MultiSigTransactionBuilder {
    /// Create new transaction builder
    pub fn new(wallet: MultiSigWallet) -> Self {
        let signing_deadline = Some(
            chrono::Utc::now() + chrono::Duration::hours(wallet.metadata.signing_timeout_hours as i64)
        );

        Self {
            wallet,
            transaction_data: None,
            partial_signatures: Vec::new(),
            signing_deadline,
        }
    }

    /// Set transaction data to be signed
    pub fn with_transaction_data(mut self, data: Vec<u8>) -> Self {
        self.transaction_data = Some(data);
        self
    }

    /// Add partial signature
    pub fn add_partial_signature(mut self, signature: PartialSignature) -> WalletResult<Self> {
        // Verify signer is authorized
        if !self.wallet.contains_public_key(&signature.public_key) {
            return Err(WalletError::AuthenticationError {
                reason: "Signer not authorized for this wallet".to_string(),
            });
        }

        // Check for duplicate signatures
        if self.partial_signatures.iter().any(|s| s.public_key == signature.public_key) {
            return Err(WalletError::MultiSignatureError {
                message: "Duplicate signature from same signer".to_string(),
            });
        }

        // Check if signature is expired
        if signature.is_expired(self.wallet.metadata.signing_timeout_hours) {
            return Err(WalletError::MultiSignatureError {
                message: "Signature has expired".to_string(),
            });
        }

        self.partial_signatures.push(signature);
        Ok(self)
    }

    /// Check if threshold is met
    pub fn is_threshold_met(&self) -> bool {
        self.partial_signatures.len() as u32 >= self.wallet.threshold
    }

    /// Check if signing deadline has passed
    pub fn is_expired(&self) -> bool {
        if let Some(deadline) = self.signing_deadline {
            chrono::Utc::now() > deadline
        } else {
            false
        }
    }

    /// Build complete signature if threshold is met
    pub fn build(self) -> WalletResult<CompleteSignature> {
        if !self.is_threshold_met() {
            return Err(WalletError::InsufficientSignatures {
                required: self.wallet.threshold as usize,
                provided: self.partial_signatures.len(),
            });
        }

        if self.is_expired() {
            return Err(WalletError::MultiSignatureError {
                message: "Signing deadline has passed".to_string(),
            });
        }

        // Create script signature combining all partial signatures
        let script_sig = self.create_script_signature()?;

        Ok(CompleteSignature::new(
            self.partial_signatures,
            script_sig,
            self.wallet.threshold,
        ))
    }

    /// Create script signature from partial signatures
    fn create_script_signature(&self) -> WalletResult<Vec<u8>> {
        let mut script_sig = Vec::new();

        // Add OP_0 (due to Bitcoin off-by-one bug in CHECKMULTISIG)
        script_sig.push(0x00);

        // Add signatures in order
        for signature in &self.partial_signatures {
            // Add signature length
            script_sig.push(signature.signature.len() as u8);
            // Add signature data
            script_sig.extend_from_slice(&signature.signature);
        }

        // Add redeem script
        let redeem_script = self.wallet.script.to_bytes()?;
        script_sig.push(redeem_script.len() as u8);
        script_sig.extend_from_slice(&redeem_script);

        Ok(script_sig)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::CoinType;

    fn create_test_public_keys(count: usize) -> Vec<PublicKey> {
        (0..count)
            .map(|i| PublicKey::new(
                CoinType::Bitcoin,
                vec![i as u8; 33], // Compressed public key length
                None,
            ))
            .collect()
    }

    #[test]
    fn test_multisig_wallet_creation() {
        let public_keys = create_test_public_keys(3);

        let wallet = MultiSigWallet::new(
            "Test Multisig".to_string(),
            public_keys.clone(),
            2,
            CoinType::Bitcoin,
        ).unwrap();

        assert_eq!(wallet.threshold, 2);
        assert_eq!(wallet.total_signers, 3);
        assert_eq!(wallet.public_keys.len(), 3);
        assert_eq!(wallet.security_level(), SecurityLevel::Medium);
    }

    #[test]
    fn test_invalid_threshold() {
        let public_keys = create_test_public_keys(2);

        // Threshold too high
        let result = MultiSigWallet::new(
            "Test".to_string(),
            public_keys.clone(),
            3, // More than number of keys
            CoinType::Bitcoin,
        );
        assert!(result.is_err());

        // Zero threshold
        let result = MultiSigWallet::new(
            "Test".to_string(),
            public_keys,
            0,
            CoinType::Bitcoin,
        );
        assert!(result.is_err());
    }

    #[test]
    fn test_partial_signature() {
        let public_key = create_test_public_keys(1)[0].clone();
        let signature_data = vec![1, 2, 3, 4];

        let partial_sig = PartialSignature::new(
            public_key.clone(),
            signature_data.clone(),
            Some("Alice".to_string()),
        );

        assert_eq!(partial_sig.public_key, public_key);
        assert_eq!(partial_sig.signature, signature_data);
        assert_eq!(partial_sig.signer_id, Some("Alice".to_string()));
        assert!(!partial_sig.is_expired(24)); // Should not be expired immediately
    }

    #[test]
    fn test_transaction_builder() {
        let public_keys = create_test_public_keys(3);
        let wallet = MultiSigWallet::new(
            "Test Multisig".to_string(),
            public_keys.clone(),
            2,
            CoinType::Bitcoin,
        ).unwrap();

        let mut builder = MultiSigTransactionBuilder::new(wallet)
            .with_transaction_data(vec![1, 2, 3, 4]);

        assert!(!builder.is_threshold_met());

        // Add first signature
        let sig1 = PartialSignature::new(
            public_keys[0].clone(),
            vec![1, 2, 3],
            Some("Alice".to_string()),
        );
        builder = builder.add_partial_signature(sig1).unwrap();
        assert!(!builder.is_threshold_met());

        // Add second signature
        let sig2 = PartialSignature::new(
            public_keys[1].clone(),
            vec![4, 5, 6],
            Some("Bob".to_string()),
        );
        builder = builder.add_partial_signature(sig2).unwrap();
        assert!(builder.is_threshold_met());

        // Should be able to build complete signature
        let complete_sig = builder.build().unwrap();
        assert_eq!(complete_sig.signer_count(), 2);
        assert!(complete_sig.is_valid(2));
    }

    #[test]
    fn test_security_levels() {
        // 1-of-1 (low security)
        let keys1 = create_test_public_keys(1);
        let wallet1 = MultiSigWallet::new("Test".to_string(), keys1, 1, CoinType::Bitcoin).unwrap();
        assert_eq!(wallet1.security_level(), SecurityLevel::Low);

        // 2-of-2 (high security)
        let keys2 = create_test_public_keys(2);
        let wallet2 = MultiSigWallet::new("Test".to_string(), keys2, 2, CoinType::Bitcoin).unwrap();
        assert_eq!(wallet2.security_level(), SecurityLevel::High);

        // 2-of-3 (high security)
        let keys3 = create_test_public_keys(3);
        let wallet3 = MultiSigWallet::new("Test".to_string(), keys3, 2, CoinType::Bitcoin).unwrap();
        assert_eq!(wallet3.security_level(), SecurityLevel::High);
    }

    #[test]
    fn test_signing_policy() {
        let public_keys = create_test_public_keys(5);
        let wallet = MultiSigWallet::new(
            "Test".to_string(),
            public_keys,
            3,
            CoinType::Bitcoin,
        ).unwrap();

        let policy = wallet.signing_policy();
        assert_eq!(policy.threshold, 3);
        assert_eq!(policy.total_signers, 5);
        assert!(!policy.require_all_signers);

        assert!(policy.requirements_met(3));
        assert!(policy.requirements_met(4));
        assert!(!policy.requirements_met(2));
    }
}