//! Secure keystore implementation

use super::encryption::EncryptionManager;
use crate::{types::WalletConfig, WalletError, WalletResult};
use std::collections::HashMap;
use tokio::sync::RwLock;

/// Secure key store interface
pub trait KeyStore: Send + Sync {
    /// Store encrypted key
    async fn store_key(&self, key_id: &str, encrypted_key: &[u8]) -> WalletResult<()>;

    /// Retrieve encrypted key
    async fn get_key(&self, key_id: &str) -> WalletResult<Option<Vec<u8>>>;

    /// Delete key
    async fn delete_key(&self, key_id: &str) -> WalletResult<()>;

    /// List all key IDs
    async fn list_keys(&self) -> WalletResult<Vec<String>>;
}

/// Secure keystore implementation
#[derive(Debug)]
pub struct SecureKeyStore {
    encryption_manager: EncryptionManager,
    keys: RwLock<HashMap<String, Vec<u8>>>,
    salt: [u8; 32],
    password_hash: RwLock<Option<String>>,
}

impl SecureKeyStore {
    /// Create new secure keystore
    pub async fn new(config: WalletConfig) -> WalletResult<Self> {
        let encryption_manager = EncryptionManager::new(config.security.encryption_algorithm)?;
        let salt = encryption_manager.generate_salt();

        Ok(Self {
            encryption_manager,
            keys: RwLock::new(HashMap::new()),
            salt,
            password_hash: RwLock::new(None),
        })
    }

    /// Initialize keystore
    pub async fn initialize(&self) -> WalletResult<()> {
        self.encryption_manager.initialize().await
    }

    /// Setup master password
    pub async fn setup_password(&self, password: &str) -> WalletResult<()> {
        let hash = self.encryption_manager.hash_password(password)?;
        *self.password_hash.write().await = Some(hash);
        Ok(())
    }

    /// Verify password
    pub async fn verify_password(&self, password: &str) -> WalletResult<bool> {
        if let Some(ref hash) = *self.password_hash.read().await {
            self.encryption_manager.verify_password(password, hash)
        } else {
            Ok(false)
        }
    }

    /// Update password
    pub async fn update_password(&self, new_password: &str) -> WalletResult<()> {
        let hash = self.encryption_manager.hash_password(new_password)?;
        *self.password_hash.write().await = Some(hash);
        Ok(())
    }

    /// Check if password is set
    pub async fn has_password(&self) -> WalletResult<bool> {
        Ok(self.password_hash.read().await.is_some())
    }

    /// Get salt for key derivation
    pub async fn get_salt(&self) -> WalletResult<[u8; 32]> {
        Ok(self.salt)
    }

    /// Shutdown keystore
    pub async fn shutdown(&self) -> WalletResult<()> {
        let mut keys = self.keys.write().await;
        keys.clear();
        Ok(())
    }
}

impl KeyStore for SecureKeyStore {
    async fn store_key(&self, key_id: &str, encrypted_key: &[u8]) -> WalletResult<()> {
        let mut keys = self.keys.write().await;
        keys.insert(key_id.to_string(), encrypted_key.to_vec());
        Ok(())
    }

    async fn get_key(&self, key_id: &str) -> WalletResult<Option<Vec<u8>>> {
        let keys = self.keys.read().await;
        Ok(keys.get(key_id).cloned())
    }

    async fn delete_key(&self, key_id: &str) -> WalletResult<()> {
        let mut keys = self.keys.write().await;
        keys.remove(key_id);
        Ok(())
    }

    async fn list_keys(&self) -> WalletResult<Vec<String>> {
        let keys = self.keys.read().await;
        Ok(keys.keys().cloned().collect())
    }
}