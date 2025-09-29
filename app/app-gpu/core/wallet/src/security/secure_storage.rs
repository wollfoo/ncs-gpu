//! Secure storage backend implementations

use crate::{types::WalletConfig, WalletError, WalletResult};
use async_trait::async_trait;
use std::collections::HashMap;
use tokio::sync::RwLock;

/// Secure storage backend interface
#[async_trait]
pub trait SecureStorageBackend: Send + Sync {
    /// Initialize storage
    async fn initialize(&self) -> WalletResult<()>;

    /// Store data
    async fn store(&self, key: &str, data: &[u8]) -> WalletResult<()>;

    /// Retrieve data
    async fn retrieve(&self, key: &str) -> WalletResult<Option<Vec<u8>>>;

    /// Delete data
    async fn delete(&self, key: &str) -> WalletResult<()>;

    /// List all keys
    async fn list_keys(&self) -> WalletResult<Vec<String>>;

    /// Shutdown storage
    async fn shutdown(&self) -> WalletResult<()>;
}

/// Memory-based secure storage (for testing)
#[derive(Debug, Default)]
pub struct MemorySecureStorage {
    data: RwLock<HashMap<String, Vec<u8>>>,
}

#[async_trait]
impl SecureStorageBackend for MemorySecureStorage {
    async fn initialize(&self) -> WalletResult<()> {
        Ok(())
    }

    async fn store(&self, key: &str, data: &[u8]) -> WalletResult<()> {
        let mut storage = self.data.write().await;
        storage.insert(key.to_string(), data.to_vec());
        Ok(())
    }

    async fn retrieve(&self, key: &str) -> WalletResult<Option<Vec<u8>>> {
        let storage = self.data.read().await;
        Ok(storage.get(key).cloned())
    }

    async fn delete(&self, key: &str) -> WalletResult<()> {
        let mut storage = self.data.write().await;
        storage.remove(key);
        Ok(())
    }

    async fn list_keys(&self) -> WalletResult<Vec<String>> {
        let storage = self.data.read().await;
        Ok(storage.keys().cloned().collect())
    }

    async fn shutdown(&self) -> WalletResult<()> {
        let mut storage = self.data.write().await;
        storage.clear();
        Ok(())
    }
}

/// Create secure storage backend
pub async fn create_backend(config: &WalletConfig) -> WalletResult<Box<dyn SecureStorageBackend>> {
    Ok(Box::new(MemorySecureStorage::default()))
}

/// Secure storage wrapper
pub struct SecureStorage {
    backend: Box<dyn SecureStorageBackend>,
}

impl SecureStorage {
    pub fn new(backend: Box<dyn SecureStorageBackend>) -> Self {
        Self { backend }
    }
}

#[async_trait]
impl SecureStorageBackend for SecureStorage {
    async fn initialize(&self) -> WalletResult<()> {
        self.backend.initialize().await
    }

    async fn store(&self, key: &str, data: &[u8]) -> WalletResult<()> {
        self.backend.store(key, data).await
    }

    async fn retrieve(&self, key: &str) -> WalletResult<Option<Vec<u8>>> {
        self.backend.retrieve(key).await
    }

    async fn delete(&self, key: &str) -> WalletResult<()> {
        self.backend.delete(key).await
    }

    async fn list_keys(&self) -> WalletResult<Vec<String>> {
        self.backend.list_keys().await
    }

    async fn shutdown(&self) -> WalletResult<()> {
        self.backend.shutdown().await
    }
}