//! HD Wallet Key Management Module
//!
//! Implementation of BIP32/BIP39/BIP44 standards for hierarchical deterministic wallets,
//! providing secure key generation, derivation, and management capabilities.

pub mod hd_wallet;
pub mod key_derivation;
pub mod mnemonic_manager;

pub use hd_wallet::HDKeyManager;
pub use key_derivation::{DerivationPath, KeyDerivation};
pub use mnemonic_manager::MnemonicManager;

use crate::{
    types::{Address, CoinType, KeyPair, Mnemonic, PrivateKey, PublicKey, Seed, WalletConfig},
    WalletError, WalletResult,
};
use async_trait::async_trait;
use std::collections::HashMap;
use zeroize::{Zeroize, ZeroizeOnDrop};

/// HD Wallet key management interface for secure key operations
#[async_trait]
pub trait KeyManager: Send + Sync {
    /// Generate new mnemonic phrase
    async fn generate_mnemonic(&self, word_count: usize) -> WalletResult<Mnemonic>;

    /// Validate mnemonic phrase
    async fn validate_mnemonic(&self, mnemonic: &Mnemonic) -> WalletResult<()>;

    /// Generate master key from mnemonic and passphrase
    async fn generate_master_key(
        &self,
        mnemonic: &Mnemonic,
        passphrase: Option<&str>,
    ) -> WalletResult<ExtendedPrivateKey>;

    /// Derive child key from path
    async fn derive_key(
        &self,
        master_key: &ExtendedPrivateKey,
        path: &DerivationPath,
    ) -> WalletResult<ExtendedPrivateKey>;

    /// Generate address from derived key
    async fn generate_address(
        &self,
        key: &ExtendedPrivateKey,
        coin_type: CoinType,
    ) -> WalletResult<Address>;

    /// Get next available derivation index for coin type
    async fn get_next_index(
        &self,
        master_key: &ExtendedPrivateKey,
        coin_type: CoinType,
    ) -> WalletResult<u32>;

    /// Generate multiple addresses in batch
    async fn generate_addresses_batch(
        &self,
        master_key: &ExtendedPrivateKey,
        coin_type: CoinType,
        count: u32,
        start_index: Option<u32>,
    ) -> WalletResult<Vec<Address>>;
}

/// Extended private key structure following BIP32 standard
#[derive(Debug, Clone, Zeroize, ZeroizeOnDrop)]
pub struct ExtendedPrivateKey {
    /// Private key data
    pub private_key: PrivateKey,
    /// Chain code for key derivation
    pub chain_code: [u8; 32],
    /// Key depth in derivation tree
    pub depth: u8,
    /// Parent key fingerprint
    pub parent_fingerprint: [u8; 4],
    /// Child number in derivation
    pub child_number: u32,
    /// Network version bytes
    pub version: [u8; 4],
}

impl ExtendedPrivateKey {
    /// Create new extended private key
    pub fn new(
        private_key: PrivateKey,
        chain_code: [u8; 32],
        depth: u8,
        parent_fingerprint: [u8; 4],
        child_number: u32,
        version: [u8; 4],
    ) -> Self {
        Self {
            private_key,
            chain_code,
            depth,
            parent_fingerprint,
            child_number,
            version,
        }
    }

    /// Get corresponding extended public key
    pub fn extended_public_key(&self) -> WalletResult<ExtendedPublicKey> {
        let public_key = self.private_key.public_key()?;
        Ok(ExtendedPublicKey {
            public_key,
            chain_code: self.chain_code,
            depth: self.depth,
            parent_fingerprint: self.parent_fingerprint,
            child_number: self.child_number,
            version: self.version,
        })
    }

    /// Get key fingerprint (first 4 bytes of public key hash)
    pub fn fingerprint(&self) -> WalletResult<[u8; 4]> {
        let public_key = self.private_key.public_key()?;
        let hash = sha2::Sha256::digest(&public_key.key_data);
        let hash = ripemd::Ripemd160::digest(&hash);
        let mut fingerprint = [0u8; 4];
        fingerprint.copy_from_slice(&hash[..4]);
        Ok(fingerprint)
    }

    /// Serialize to bytes for storage
    pub fn serialize(&self) -> Vec<u8> {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(&self.version);
        bytes.push(self.depth);
        bytes.extend_from_slice(&self.parent_fingerprint);
        bytes.extend_from_slice(&self.child_number.to_be_bytes());
        bytes.extend_from_slice(&self.chain_code);
        bytes.push(0x00); // Private key prefix
        bytes.extend_from_slice(&self.private_key.key_data);
        bytes
    }

    /// Deserialize from bytes
    pub fn deserialize(bytes: &[u8], coin_type: CoinType) -> WalletResult<Self> {
        if bytes.len() != 78 {
            return Err(WalletError::InvalidPrivateKey {
                reason: "Invalid extended private key length".to_string(),
            });
        }

        let version = [bytes[0], bytes[1], bytes[2], bytes[3]];
        let depth = bytes[4];
        let parent_fingerprint = [bytes[5], bytes[6], bytes[7], bytes[8]];
        let child_number = u32::from_be_bytes([bytes[9], bytes[10], bytes[11], bytes[12]]);
        let mut chain_code = [0u8; 32];
        chain_code.copy_from_slice(&bytes[13..45]);

        if bytes[45] != 0x00 {
            return Err(WalletError::InvalidPrivateKey {
                reason: "Invalid private key prefix".to_string(),
            });
        }

        let private_key = PrivateKey::new(coin_type, bytes[46..78].to_vec(), None);

        Ok(Self::new(
            private_key,
            chain_code,
            depth,
            parent_fingerprint,
            child_number,
            version,
        ))
    }
}

/// Extended public key structure following BIP32 standard
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExtendedPublicKey {
    /// Public key data
    pub public_key: PublicKey,
    /// Chain code for key derivation
    pub chain_code: [u8; 32],
    /// Key depth in derivation tree
    pub depth: u8,
    /// Parent key fingerprint
    pub parent_fingerprint: [u8; 4],
    /// Child number in derivation
    pub child_number: u32,
    /// Network version bytes
    pub version: [u8; 4],
}

impl ExtendedPublicKey {
    /// Serialize to bytes
    pub fn serialize(&self) -> Vec<u8> {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(&self.version);
        bytes.push(self.depth);
        bytes.extend_from_slice(&self.parent_fingerprint);
        bytes.extend_from_slice(&self.child_number.to_be_bytes());
        bytes.extend_from_slice(&self.chain_code);
        bytes.extend_from_slice(&self.public_key.key_data);
        bytes
    }

    /// Get key fingerprint
    pub fn fingerprint(&self) -> [u8; 4] {
        let hash = sha2::Sha256::digest(&self.public_key.key_data);
        let hash = ripemd::Ripemd160::digest(&hash);
        let mut fingerprint = [0u8; 4];
        fingerprint.copy_from_slice(&hash[..4]);
        fingerprint
    }
}

/// Key derivation context for managing state
#[derive(Debug, Clone)]
pub struct KeyDerivationContext {
    /// Map of coin types to next available index
    next_indices: HashMap<CoinType, u32>,
    /// Cache of derived keys for performance
    key_cache: HashMap<String, ExtendedPrivateKey>,
    /// Maximum cache size
    max_cache_size: usize,
}

impl KeyDerivationContext {
    pub fn new(max_cache_size: usize) -> Self {
        Self {
            next_indices: HashMap::new(),
            key_cache: HashMap::new(),
            max_cache_size,
        }
    }

    /// Get next index for coin type
    pub fn get_next_index(&mut self, coin_type: CoinType) -> u32 {
        let index = self.next_indices.get(&coin_type).copied().unwrap_or(0);
        self.next_indices.insert(coin_type, index + 1);
        index
    }

    /// Cache derived key
    pub fn cache_key(&mut self, path: &str, key: ExtendedPrivateKey) {
        if self.key_cache.len() >= self.max_cache_size {
            // Remove oldest entry (simple FIFO)
            if let Some((oldest_key, _)) = self.key_cache.iter().next() {
                let oldest_key = oldest_key.clone();
                self.key_cache.remove(&oldest_key);
            }
        }
        self.key_cache.insert(path.to_string(), key);
    }

    /// Get cached key
    pub fn get_cached_key(&self, path: &str) -> Option<&ExtendedPrivateKey> {
        self.key_cache.get(path)
    }

    /// Clear cache securely
    pub fn clear_cache(&mut self) {
        for (_, mut key) in self.key_cache.drain() {
            key.zeroize();
        }
    }

    /// Reset indices for coin type
    pub fn reset_index(&mut self, coin_type: CoinType) {
        self.next_indices.insert(coin_type, 0);
    }
}

impl Drop for KeyDerivationContext {
    fn drop(&mut self) {
        self.clear_cache();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::WalletConfig;

    #[tokio::test]
    async fn test_extended_key_serialization() {
        let coin_type = CoinType::Bitcoin;
        let private_key = PrivateKey::new(coin_type, vec![1u8; 32], None);
        let chain_code = [2u8; 32];
        let extended_key = ExtendedPrivateKey::new(
            private_key,
            chain_code,
            0,
            [0u8; 4],
            0,
            [0x04, 0x88, 0xAD, 0xE4], // Bitcoin mainnet private key version
        );

        let serialized = extended_key.serialize();
        let deserialized = ExtendedPrivateKey::deserialize(&serialized, coin_type);
        assert!(deserialized.is_ok());

        let deserialized = deserialized.unwrap();
        assert_eq!(deserialized.depth, extended_key.depth);
        assert_eq!(deserialized.chain_code, extended_key.chain_code);
        assert_eq!(deserialized.child_number, extended_key.child_number);
    }

    #[tokio::test]
    async fn test_key_derivation_context() {
        let mut context = KeyDerivationContext::new(10);

        let index1 = context.get_next_index(CoinType::Bitcoin);
        let index2 = context.get_next_index(CoinType::Bitcoin);
        let index3 = context.get_next_index(CoinType::Ethereum);

        assert_eq!(index1, 0);
        assert_eq!(index2, 1);
        assert_eq!(index3, 0);
    }

    #[test]
    fn test_extended_public_key() {
        let coin_type = CoinType::Bitcoin;
        let private_key = PrivateKey::new(coin_type, vec![1u8; 32], None);
        let extended_private = ExtendedPrivateKey::new(
            private_key,
            [2u8; 32],
            0,
            [0u8; 4],
            0,
            [0x04, 0x88, 0xAD, 0xE4],
        );

        let extended_public = extended_private.extended_public_key();
        assert!(extended_public.is_ok());

        let extended_public = extended_public.unwrap();
        assert_eq!(extended_public.depth, extended_private.depth);
        assert_eq!(extended_public.chain_code, extended_private.chain_code);
    }
}