//! In-memory storage implementation for testing

use super::{StorageHealth, StorageStatistics, WalletStorage};
use crate::{
    types::{WalletInfo, WalletId},
    WalletResult,
};
use async_trait::async_trait;
use std::collections::HashMap;
use tokio::sync::RwLock;

/// In-memory storage implementation (for testing)
#[derive(Debug, Default)]
pub struct MemoryStorage {
    wallets: RwLock<HashMap<WalletId, WalletInfo>>,
    encrypted_data: RwLock<HashMap<String, Vec<u8>>>,
}

impl MemoryStorage {
    /// Create new memory storage
    pub fn new() -> Self {
        Self::default()
    }
}

#[async_trait]
impl WalletStorage for MemoryStorage {
    async fn initialize(&self) -> WalletResult<()> {
        Ok(())
    }

    async fn close(&self) -> WalletResult<()> {
        let mut wallets = self.wallets.write().await;
        let mut encrypted_data = self.encrypted_data.write().await;
        wallets.clear();
        encrypted_data.clear();
        Ok(())
    }

    async fn store_wallet(&self, wallet_info: &WalletInfo) -> WalletResult<()> {
        let mut wallets = self.wallets.write().await;
        wallets.insert(wallet_info.id, wallet_info.clone());
        Ok(())
    }

    async fn get_wallet(&self, wallet_id: &WalletId) -> WalletResult<Option<WalletInfo>> {
        let wallets = self.wallets.read().await;
        Ok(wallets.get(wallet_id).cloned())
    }

    async fn update_wallet(&self, wallet_info: &WalletInfo) -> WalletResult<()> {
        let mut wallets = self.wallets.write().await;
        wallets.insert(wallet_info.id, wallet_info.clone());
        Ok(())
    }

    async fn delete_wallet(&self, wallet_id: &WalletId) -> WalletResult<()> {
        let mut wallets = self.wallets.write().await;
        wallets.remove(wallet_id);
        Ok(())
    }

    async fn list_wallets(&self) -> WalletResult<Vec<WalletInfo>> {
        let wallets = self.wallets.read().await;
        Ok(wallets.values().cloned().collect())
    }

    async fn store_encrypted_data(&self, key: &str, data: &[u8]) -> WalletResult<()> {
        let mut encrypted_data = self.encrypted_data.write().await;
        encrypted_data.insert(key.to_string(), data.to_vec());
        Ok(())
    }

    async fn get_encrypted_data(&self, key: &str) -> WalletResult<Option<Vec<u8>>> {
        let encrypted_data = self.encrypted_data.read().await;
        Ok(encrypted_data.get(key).cloned())
    }

    async fn delete_encrypted_data(&self, key: &str) -> WalletResult<()> {
        let mut encrypted_data = self.encrypted_data.write().await;
        encrypted_data.remove(key);
        Ok(())
    }

    async fn list_encrypted_keys(&self) -> WalletResult<Vec<String>> {
        let encrypted_data = self.encrypted_data.read().await;
        Ok(encrypted_data.keys().cloned().collect())
    }

    async fn wallet_exists(&self, wallet_id: &WalletId) -> WalletResult<bool> {
        let wallets = self.wallets.read().await;
        Ok(wallets.contains_key(wallet_id))
    }

    async fn get_statistics(&self) -> WalletResult<StorageStatistics> {
        let wallets = self.wallets.read().await;
        let encrypted_data = self.encrypted_data.read().await;

        let total_size_bytes = encrypted_data.values().map(|v| v.len() as u64).sum();

        Ok(StorageStatistics {
            wallet_count: wallets.len(),
            encrypted_data_count: encrypted_data.len(),
            total_size_bytes,
            available_space_bytes: None,
            last_backup: None,
            health_status: StorageHealth::Healthy,
        })
    }

    async fn backup(&self, _backup_path: &std::path::Path) -> WalletResult<()> {
        // Memory storage doesn't support backup
        Ok(())
    }

    async fn restore(&self, _backup_path: &std::path::Path) -> WalletResult<()> {
        // Memory storage doesn't support restore
        Ok(())
    }

    async fn compact(&self) -> WalletResult<()> {
        // Memory storage doesn't need compaction
        Ok(())
    }
}