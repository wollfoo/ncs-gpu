//! HD Wallet implementation following BIP32/BIP39/BIP44 standards

use super::{
    DerivationPath, ExtendedPrivateKey, KeyDerivationContext, KeyManager, MnemonicManager,
};
use crate::{
    types::{Address, CoinType, Mnemonic, PrivateKey, WalletConfig},
    WalletError, WalletResult,
};
use async_trait::async_trait;
use parking_lot::RwLock;
use std::sync::Arc;
use tokio::sync::Mutex;
use zeroize::Zeroize;

/// HD Wallet Key Manager implementation
#[derive(Debug)]
pub struct HDKeyManager {
    config: WalletConfig,
    mnemonic_manager: MnemonicManager,
    derivation_context: Arc<Mutex<KeyDerivationContext>>,
    master_keys: Arc<RwLock<std::collections::HashMap<String, ExtendedPrivateKey>>>,
}

impl HDKeyManager {
    /// Create new HD Key Manager
    pub fn new(config: WalletConfig) -> WalletResult<Self> {
        let mnemonic_manager = MnemonicManager::new();
        let derivation_context = Arc::new(Mutex::new(KeyDerivationContext::new(1000)));
        let master_keys = Arc::new(RwLock::new(std::collections::HashMap::new()));

        Ok(Self {
            config,
            mnemonic_manager,
            derivation_context,
            master_keys,
        })
    }

    /// Derive key using BIP44 path for specific coin and index
    pub async fn derive_bip44_key(
        &self,
        master_key: &ExtendedPrivateKey,
        coin_type: CoinType,
        account: u32,
        change: u32,
        index: u32,
    ) -> WalletResult<ExtendedPrivateKey> {
        let path = DerivationPath::bip44(coin_type, account, change, index);
        self.derive_key(master_key, &path).await
    }

    /// Derive account key for coin type
    pub async fn derive_account_key(
        &self,
        master_key: &ExtendedPrivateKey,
        coin_type: CoinType,
        account: u32,
    ) -> WalletResult<ExtendedPrivateKey> {
        let path = DerivationPath::bip44_account(coin_type, account);
        self.derive_key(master_key, &path).await
    }

    /// Store master key with identifier
    pub fn store_master_key(&self, identifier: String, master_key: ExtendedPrivateKey) {
        self.master_keys.write().insert(identifier, master_key);
    }

    /// Retrieve stored master key
    pub fn get_master_key(&self, identifier: &str) -> Option<ExtendedPrivateKey> {
        self.master_keys.read().get(identifier).cloned()
    }

    /// Remove master key securely
    pub fn remove_master_key(&self, identifier: &str) -> bool {
        if let Some(mut key) = self.master_keys.write().remove(identifier) {
            key.zeroize();
            true
        } else {
            false
        }
    }

    /// Clear all master keys securely
    pub fn clear_master_keys(&self) {
        let mut keys = self.master_keys.write();
        for (_, mut key) in keys.drain() {
            key.zeroize();
        }
    }

    /// Check if wallet supports coin type
    pub fn supports_coin_type(&self, coin_type: CoinType) -> bool {
        self.config.networks.contains_key(&coin_type)
    }

    /// Get supported coin types
    pub fn supported_coin_types(&self) -> Vec<CoinType> {
        self.config.networks.keys().copied().collect()
    }

    /// Validate derivation path for coin type
    pub fn validate_derivation_path(
        &self,
        path: &DerivationPath,
        coin_type: CoinType,
    ) -> WalletResult<()> {
        // Check if path is compatible with coin type
        if let Some(coin_type_from_path) = path.coin_type() {
            if coin_type_from_path != coin_type {
                return Err(WalletError::InvalidDerivationPath {
                    path: path.to_string(),
                });
            }
        }

        // Validate path depth and structure
        path.validate()?;

        Ok(())
    }

    /// Generate receiving address for external chain (change = 0)
    pub async fn generate_receiving_address(
        &self,
        master_key: &ExtendedPrivateKey,
        coin_type: CoinType,
        account: u32,
    ) -> WalletResult<Address> {
        let mut context = self.derivation_context.lock().await;
        let index = context.get_next_index(coin_type);
        drop(context);

        let key = self.derive_bip44_key(master_key, coin_type, account, 0, index).await?;
        self.generate_address(&key, coin_type).await
    }

    /// Generate change address for internal chain (change = 1)
    pub async fn generate_change_address(
        &self,
        master_key: &ExtendedPrivateKey,
        coin_type: CoinType,
        account: u32,
    ) -> WalletResult<Address> {
        let mut context = self.derivation_context.lock().await;
        let index = context.get_next_index(coin_type);
        drop(context);

        let key = self.derive_bip44_key(master_key, coin_type, account, 1, index).await?;
        self.generate_address(&key, coin_type).await
    }

    /// Get wallet statistics
    pub async fn get_wallet_stats(&self, master_key: &ExtendedPrivateKey) -> WalletStats {
        let context = self.derivation_context.lock().await;
        let mut stats = WalletStats {
            supported_coins: self.supported_coin_types(),
            next_indices: context.next_indices.clone(),
            cached_keys: context.key_cache.len(),
            master_keys_count: self.master_keys.read().len(),
        };

        // Calculate total addresses generated
        stats.total_addresses = stats.next_indices.values().sum();

        stats
    }

    /// Reset derivation indices (for testing or wallet recovery)
    pub async fn reset_derivation_indices(&self, coin_type: Option<CoinType>) {
        let mut context = self.derivation_context.lock().await;
        if let Some(coin_type) = coin_type {
            context.reset_index(coin_type);
        } else {
            // Reset all indices
            for coin_type in self.supported_coin_types() {
                context.reset_index(coin_type);
            }
        }
    }
}

#[async_trait]
impl KeyManager for HDKeyManager {
    async fn generate_mnemonic(&self, word_count: usize) -> WalletResult<Mnemonic> {
        self.mnemonic_manager.generate_mnemonic(word_count).await
    }

    async fn validate_mnemonic(&self, mnemonic: &Mnemonic) -> WalletResult<()> {
        self.mnemonic_manager.validate_mnemonic(mnemonic).await
    }

    async fn generate_master_key(
        &self,
        mnemonic: &Mnemonic,
        passphrase: Option<&str>,
    ) -> WalletResult<ExtendedPrivateKey> {
        // Generate seed from mnemonic
        let seed = mnemonic.to_seed(passphrase)?;

        // Generate master private key using HMAC-SHA512
        let hmac_key = b"ed25519 seed";
        let hmac_result = hmac_sha512(hmac_key, seed.as_bytes());

        // Split result into private key and chain code
        let (private_key_data, chain_code_data) = hmac_result.split_at(32);

        let mut chain_code = [0u8; 32];
        chain_code.copy_from_slice(chain_code_data);

        let private_key = PrivateKey::new(
            CoinType::Bitcoin, // Default to Bitcoin for master key
            private_key_data.to_vec(),
            Some("m".to_string()),
        );

        // Check if private key is valid
        if private_key_data.iter().all(|&x| x == 0) {
            return Err(WalletError::KeyDerivationError {
                reason: "Invalid master key generated".to_string(),
            });
        }

        let master_key = ExtendedPrivateKey::new(
            private_key,
            chain_code,
            0, // Master key depth is 0
            [0u8; 4], // Master key has no parent
            0, // Master key child number is 0
            [0x04, 0x88, 0xAD, 0xE4], // Bitcoin mainnet version
        );

        Ok(master_key)
    }

    async fn derive_key(
        &self,
        master_key: &ExtendedPrivateKey,
        path: &DerivationPath,
    ) -> WalletResult<ExtendedPrivateKey> {
        let path_str = path.to_string();

        // Check cache first
        {
            let context = self.derivation_context.lock().await;
            if let Some(cached_key) = context.get_cached_key(&path_str) {
                return Ok(cached_key.clone());
            }
        }

        // Derive key step by step
        let mut current_key = master_key.clone();

        for &index in path.indices() {
            current_key = self.derive_child_key(&current_key, index).await?;
        }

        // Cache the derived key
        {
            let mut context = self.derivation_context.lock().await;
            context.cache_key(&path_str, current_key.clone());
        }

        Ok(current_key)
    }

    async fn generate_address(
        &self,
        key: &ExtendedPrivateKey,
        coin_type: CoinType,
    ) -> WalletResult<Address> {
        if !self.supports_coin_type(coin_type) {
            return Err(WalletError::UnsupportedCoinType {
                coin_type: coin_type.to_string(),
            });
        }

        // Get public key from private key
        let public_key = key.private_key.public_key()?;

        // Generate address from public key
        let mut address = public_key.to_address()?;
        address.coin_type = coin_type;

        Ok(address)
    }

    async fn get_next_index(
        &self,
        _master_key: &ExtendedPrivateKey,
        coin_type: CoinType,
    ) -> WalletResult<u32> {
        let mut context = self.derivation_context.lock().await;
        Ok(context.get_next_index(coin_type))
    }

    async fn generate_addresses_batch(
        &self,
        master_key: &ExtendedPrivateKey,
        coin_type: CoinType,
        count: u32,
        start_index: Option<u32>,
    ) -> WalletResult<Vec<Address>> {
        if !self.supports_coin_type(coin_type) {
            return Err(WalletError::UnsupportedCoinType {
                coin_type: coin_type.to_string(),
            });
        }

        let start_idx = start_index.unwrap_or_else(|| {
            let mut context = futures::executor::block_on(self.derivation_context.lock());
            context.get_next_index(coin_type).saturating_sub(1).max(0)
        });

        let mut addresses = Vec::with_capacity(count as usize);

        for i in 0..count {
            let index = start_idx + i;
            let key = self.derive_bip44_key(master_key, coin_type, 0, 0, index).await?;
            let mut address = self.generate_address(&key, coin_type).await?;
            address.index = Some(index);
            address.derivation_path = Some(format!("m/44'/{}'/{}'/{}/{}",
                coin_type.bip44_coin_type(), 0, 0, index));
            addresses.push(address);
        }

        Ok(addresses)
    }
}

impl HDKeyManager {
    /// Derive child key from parent key and index
    async fn derive_child_key(
        &self,
        parent_key: &ExtendedPrivateKey,
        child_index: u32,
    ) -> WalletResult<ExtendedPrivateKey> {
        let hardened = child_index >= 0x80000000;

        // Prepare data for HMAC
        let mut data = Vec::new();

        if hardened {
            // Hardened derivation: use private key
            data.push(0x00);
            data.extend_from_slice(&parent_key.private_key.key_data);
        } else {
            // Non-hardened derivation: use public key
            let public_key = parent_key.private_key.public_key()?;
            data.extend_from_slice(&public_key.key_data);
        }

        data.extend_from_slice(&child_index.to_be_bytes());

        // Compute HMAC-SHA512
        let hmac_result = hmac_sha512(&parent_key.chain_code, &data);
        let (left, right) = hmac_result.split_at(32);

        // Check if left part is valid private key
        if left.iter().all(|&x| x == 0) {
            return Err(WalletError::KeyDerivationError {
                reason: "Invalid child key derived".to_string(),
            });
        }

        // Add parent private key to left part (modulo curve order)
        let child_private_key_data = add_private_keys(&parent_key.private_key.key_data, left)?;

        let mut child_chain_code = [0u8; 32];
        child_chain_code.copy_from_slice(right);

        let child_private_key = PrivateKey::new(
            parent_key.private_key.coin_type,
            child_private_key_data,
            None,
        );

        let child_key = ExtendedPrivateKey::new(
            child_private_key,
            child_chain_code,
            parent_key.depth + 1,
            parent_key.fingerprint()?,
            child_index,
            parent_key.version,
        );

        Ok(child_key)
    }
}

/// Wallet statistics
#[derive(Debug, Clone)]
pub struct WalletStats {
    pub supported_coins: Vec<CoinType>,
    pub next_indices: std::collections::HashMap<CoinType, u32>,
    pub total_addresses: u32,
    pub cached_keys: usize,
    pub master_keys_count: usize,
}

/// Compute HMAC-SHA512
fn hmac_sha512(key: &[u8], data: &[u8]) -> [u8; 64] {
    use sha2::{Digest, Sha512};

    let mut ipad = [0x36u8; 64];
    let mut opad = [0x5cu8; 64];

    let key = if key.len() > 64 {
        let mut hasher = Sha512::new();
        hasher.update(key);
        let result = hasher.finalize();
        result.as_slice().to_vec()
    } else {
        key.to_vec()
    };

    for i in 0..key.len().min(64) {
        ipad[i] ^= key[i];
        opad[i] ^= key[i];
    }

    let mut hasher = Sha512::new();
    hasher.update(&ipad);
    hasher.update(data);
    let inner_result = hasher.finalize();

    let mut hasher = Sha512::new();
    hasher.update(&opad);
    hasher.update(&inner_result);
    let result = hasher.finalize();

    let mut output = [0u8; 64];
    output.copy_from_slice(&result);
    output
}

/// Add two private keys modulo secp256k1 curve order
fn add_private_keys(a: &[u8], b: &[u8]) -> WalletResult<Vec<u8>> {
    if a.len() != 32 || b.len() != 32 {
        return Err(WalletError::InvalidPrivateKey {
            reason: "Private keys must be 32 bytes".to_string(),
        });
    }

    let secret_a = secp256k1::SecretKey::from_slice(a)?;
    let secret_b = secp256k1::SecretKey::from_slice(b)?;

    let mut result = secret_a;
    result = result.add_tweak(&secp256k1::scalar::Scalar::from(secret_b))?;

    Ok(result.secret_bytes().to_vec())
}

impl Drop for HDKeyManager {
    fn drop(&mut self) {
        // Secure cleanup
        self.clear_master_keys();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::WalletConfig;

    async fn create_test_hd_manager() -> HDKeyManager {
        let config = WalletConfig::default();
        HDKeyManager::new(config).unwrap()
    }

    #[tokio::test]
    async fn test_mnemonic_generation() {
        let manager = create_test_hd_manager().await;

        let mnemonic = manager.generate_mnemonic(12).await;
        assert!(mnemonic.is_ok());

        let mnemonic = mnemonic.unwrap();
        assert!(manager.validate_mnemonic(&mnemonic).await.is_ok());
    }

    #[tokio::test]
    async fn test_master_key_generation() {
        let manager = create_test_hd_manager().await;

        let mnemonic = manager.generate_mnemonic(12).await.unwrap();
        let master_key = manager.generate_master_key(&mnemonic, None).await;

        assert!(master_key.is_ok());
        let master_key = master_key.unwrap();
        assert_eq!(master_key.depth, 0);
        assert_eq!(master_key.child_number, 0);
    }

    #[tokio::test]
    async fn test_address_generation() {
        let manager = create_test_hd_manager().await;

        let mnemonic = manager.generate_mnemonic(12).await.unwrap();
        let master_key = manager.generate_master_key(&mnemonic, None).await.unwrap();

        let address = manager.generate_receiving_address(&master_key, CoinType::Bitcoin, 0).await;
        assert!(address.is_ok());

        let address = address.unwrap();
        assert_eq!(address.coin_type, CoinType::Bitcoin);
        assert!(address.index.is_some());
    }

    #[tokio::test]
    async fn test_batch_address_generation() {
        let manager = create_test_hd_manager().await;

        let mnemonic = manager.generate_mnemonic(12).await.unwrap();
        let master_key = manager.generate_master_key(&mnemonic, None).await.unwrap();

        let addresses = manager.generate_addresses_batch(&master_key, CoinType::Bitcoin, 5, None).await;
        assert!(addresses.is_ok());

        let addresses = addresses.unwrap();
        assert_eq!(addresses.len(), 5);

        for (i, address) in addresses.iter().enumerate() {
            assert_eq!(address.coin_type, CoinType::Bitcoin);
            assert_eq!(address.index, Some(i as u32));
            assert!(address.derivation_path.is_some());
        }
    }

    #[tokio::test]
    async fn test_key_derivation() {
        let manager = create_test_hd_manager().await;

        let mnemonic = manager.generate_mnemonic(12).await.unwrap();
        let master_key = manager.generate_master_key(&mnemonic, None).await.unwrap();

        let path = DerivationPath::bip44(CoinType::Bitcoin, 0, 0, 0);
        let derived_key = manager.derive_key(&master_key, &path).await;

        assert!(derived_key.is_ok());
        let derived_key = derived_key.unwrap();
        assert!(derived_key.depth > master_key.depth);
    }

    #[tokio::test]
    async fn test_wallet_stats() {
        let manager = create_test_hd_manager().await;

        let mnemonic = manager.generate_mnemonic(12).await.unwrap();
        let master_key = manager.generate_master_key(&mnemonic, None).await.unwrap();

        // Generate some addresses
        let _addr1 = manager.generate_receiving_address(&master_key, CoinType::Bitcoin, 0).await.unwrap();
        let _addr2 = manager.generate_receiving_address(&master_key, CoinType::Ethereum, 0).await.unwrap();

        let stats = manager.get_wallet_stats(&master_key).await;
        assert!(!stats.supported_coins.is_empty());
        assert!(stats.total_addresses > 0);
    }
}