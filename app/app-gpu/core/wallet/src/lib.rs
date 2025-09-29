//! # OPUS-GPU Wallet Management Module
//!
//! Secure multi-coin wallet management system with HD wallet support, hardware wallet integration,
//! and multi-signature capabilities for cryptocurrency mining rewards and transactions.
//!
//! ## Features
//! - HD Wallet support (BIP32/39/44)
//! - Multi-coin support (Bitcoin, Ethereum, etc.)
//! - Hardware wallet integration
//! - Multi-signature support
//! - Secure key storage with encryption
//! - Transaction management and signing
//! - Balance tracking and history

pub mod error;
pub mod types;
pub mod key_management;
pub mod transaction;
pub mod security;
pub mod storage;
pub mod multi_signature;

#[cfg(feature = "hardware-wallet")]
pub mod hardware;

// Re-exports for convenience
pub use error::{WalletError, WalletResult};
pub use types::{
    Address, Balance, CoinType, KeyPair, Mnemonic, PrivateKey, PublicKey, Seed, WalletConfig,
    WalletId, WalletInfo, WalletType,
};

// Re-export main interfaces
pub use key_management::{HDKeyManager, KeyManager};
pub use transaction::{TransactionManager, TransactionManagerTrait};
pub use security::{SecurityManager, SecurityManagerTrait};
pub use storage::{WalletStorage, create_storage};
pub use multi_signature::{MultiSigWallet, MultiSigWalletTrait};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tokio::sync::RwLock;
use uuid::Uuid;

/// Main wallet management interface providing secure multi-coin wallet operations
#[async_trait]
pub trait WalletManager: Send + Sync {
    /// Create a new HD wallet with mnemonic phrase generation
    async fn create_wallet(
        &self,
        name: String,
        password: String,
        coin_types: Vec<CoinType>,
    ) -> WalletResult<WalletInfo>;

    /// Import existing wallet from mnemonic phrase
    async fn import_wallet(
        &self,
        name: String,
        mnemonic: Mnemonic,
        password: String,
        coin_types: Vec<CoinType>,
    ) -> WalletResult<WalletInfo>;

    /// Load existing wallet by ID
    async fn load_wallet(&self, wallet_id: &WalletId, password: String) -> WalletResult<WalletInfo>;

    /// Generate new receiving address for specified coin type
    async fn generate_address(
        &self,
        wallet_id: &WalletId,
        coin_type: CoinType,
    ) -> WalletResult<Address>;

    /// Get wallet balance for all supported coins
    async fn get_balance(&self, wallet_id: &WalletId) -> WalletResult<HashMap<CoinType, Balance>>;

    /// Sign transaction with wallet private key
    async fn sign_transaction(
        &self,
        wallet_id: &WalletId,
        transaction_data: &[u8],
        coin_type: CoinType,
    ) -> WalletResult<Vec<u8>>;

    /// List all available wallets
    async fn list_wallets(&self) -> WalletResult<Vec<WalletInfo>>;

    /// Delete wallet (secure deletion)
    async fn delete_wallet(&self, wallet_id: &WalletId, password: String) -> WalletResult<()>;

    /// Backup wallet to encrypted format
    async fn backup_wallet(
        &self,
        wallet_id: &WalletId,
        password: String,
    ) -> WalletResult<Vec<u8>>;

    /// Restore wallet from backup
    async fn restore_wallet(&self, backup_data: &[u8], password: String) -> WalletResult<WalletInfo>;

    /// Update wallet password
    async fn change_password(
        &self,
        wallet_id: &WalletId,
        old_password: String,
        new_password: String,
    ) -> WalletResult<()>;
}

/// Core wallet manager implementation
#[derive(Debug)]
pub struct CoreWalletManager {
    storage: Box<dyn storage::WalletStorage>,
    key_manager: key_management::HDKeyManager,
    transaction_manager: transaction::TransactionManager,
    security_manager: security::SecurityManager,
    config: WalletConfig,
    wallets: RwLock<HashMap<WalletId, wallet_cache::WalletCache>>,
}

impl CoreWalletManager {
    /// Create new wallet manager instance
    pub async fn new(
        storage: Box<dyn storage::WalletStorage>,
        config: WalletConfig,
    ) -> WalletResult<Self> {
        let key_manager = key_management::HDKeyManager::new(config.clone())?;
        let transaction_manager = transaction::TransactionManager::new(config.clone()).await?;
        let security_manager = security::SecurityManager::new(config.clone()).await?;

        Ok(Self {
            storage,
            key_manager,
            transaction_manager,
            security_manager,
            config,
            wallets: RwLock::new(HashMap::new()),
        })
    }

    /// Initialize wallet manager and load existing wallets
    pub async fn initialize(&self) -> WalletResult<()> {
        tracing::info!("Initializing wallet manager");

        // Load existing wallets metadata
        let wallet_infos = self.storage.list_wallets().await?;

        for wallet_info in wallet_infos {
            let cache = wallet_cache::WalletCache::new(wallet_info.clone());
            self.wallets
                .write()
                .await
                .insert(wallet_info.id, cache);
        }

        tracing::info!("Wallet manager initialized with {} wallets", self.wallets.read().await.len());
        Ok(())
    }

    /// Shutdown wallet manager and secure cleanup
    pub async fn shutdown(&self) -> WalletResult<()> {
        tracing::info!("Shutting down wallet manager");

        // Clear wallet cache securely
        let mut wallets = self.wallets.write().await;
        for (_, cache) in wallets.drain() {
            cache.secure_drop();
        }

        self.security_manager.shutdown().await?;
        self.storage.close().await?;

        tracing::info!("Wallet manager shutdown complete");
        Ok(())
    }
}

/// Internal wallet cache for performance optimization
mod wallet_cache {
    use super::*;
    use chrono::{DateTime, Utc};
    use parking_lot::RwLock;
    use zeroize::Zeroize;

    #[derive(Debug)]
    pub struct WalletCache {
        pub info: WalletInfo,
        pub last_accessed: RwLock<DateTime<Utc>>,
        pub address_cache: RwLock<HashMap<CoinType, Vec<Address>>>,
        pub balance_cache: RwLock<HashMap<CoinType, (Balance, DateTime<Utc>)>>,
    }

    impl WalletCache {
        pub fn new(info: WalletInfo) -> Self {
            Self {
                info,
                last_accessed: RwLock::new(Utc::now()),
                address_cache: RwLock::new(HashMap::new()),
                balance_cache: RwLock::new(HashMap::new()),
            }
        }

        pub fn update_access(&self) {
            *self.last_accessed.write() = Utc::now();
        }

        pub fn secure_drop(self) {
            // Secure cleanup of sensitive data
            let mut info = self.info;
            info.zeroize();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    async fn create_test_wallet_manager() -> (CoreWalletManager, TempDir) {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let config = WalletConfig::default_with_path(temp_dir.path().to_path_buf());
        let storage = storage::create_storage(&config).await.expect("Failed to create storage");
        let manager = CoreWalletManager::new(storage, config)
            .await
            .expect("Failed to create wallet manager");

        (manager, temp_dir)
    }

    #[tokio::test]
    async fn test_wallet_manager_creation() {
        let (_manager, _temp_dir) = create_test_wallet_manager().await;
        // Manager creation successful
    }

    #[tokio::test]
    async fn test_wallet_manager_initialization() {
        let (manager, _temp_dir) = create_test_wallet_manager().await;
        assert!(manager.initialize().await.is_ok());
    }

    #[tokio::test]
    async fn test_wallet_manager_shutdown() {
        let (manager, _temp_dir) = create_test_wallet_manager().await;
        manager.initialize().await.expect("Failed to initialize");
        assert!(manager.shutdown().await.is_ok());
    }
}