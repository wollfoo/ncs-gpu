//! Storage Layer Module
//!
//! Persistent storage implementation for wallet data with encryption support.

pub mod database;
pub mod file_storage;
pub mod memory_storage;

pub use database::{DatabaseStorage, SqliteStorage};
pub use file_storage::FileStorage;
pub use memory_storage::MemoryStorage;

use crate::{
    types::{WalletConfig, WalletInfo, WalletId},
    WalletError, WalletResult,
};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Wallet storage interface
#[async_trait]
pub trait WalletStorage: Send + Sync {
    /// Initialize storage
    async fn initialize(&self) -> WalletResult<()>;

    /// Close storage
    async fn close(&self) -> WalletResult<()>;

    /// Store wallet information
    async fn store_wallet(&self, wallet_info: &WalletInfo) -> WalletResult<()>;

    /// Retrieve wallet information
    async fn get_wallet(&self, wallet_id: &WalletId) -> WalletResult<Option<WalletInfo>>;

    /// Update wallet information
    async fn update_wallet(&self, wallet_info: &WalletInfo) -> WalletResult<()>;

    /// Delete wallet
    async fn delete_wallet(&self, wallet_id: &WalletId) -> WalletResult<()>;

    /// List all wallets
    async fn list_wallets(&self) -> WalletResult<Vec<WalletInfo>>;

    /// Store encrypted data
    async fn store_encrypted_data(&self, key: &str, data: &[u8]) -> WalletResult<()>;

    /// Retrieve encrypted data
    async fn get_encrypted_data(&self, key: &str) -> WalletResult<Option<Vec<u8>>>;

    /// Delete encrypted data
    async fn delete_encrypted_data(&self, key: &str) -> WalletResult<()>;

    /// List all encrypted data keys
    async fn list_encrypted_keys(&self) -> WalletResult<Vec<String>>;

    /// Check if wallet exists
    async fn wallet_exists(&self, wallet_id: &WalletId) -> WalletResult<bool>;

    /// Get storage statistics
    async fn get_statistics(&self) -> WalletResult<StorageStatistics>;

    /// Backup storage
    async fn backup(&self, backup_path: &std::path::Path) -> WalletResult<()>;

    /// Restore from backup
    async fn restore(&self, backup_path: &std::path::Path) -> WalletResult<()>;

    /// Compact/optimize storage
    async fn compact(&self) -> WalletResult<()>;
}

/// Storage statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageStatistics {
    /// Number of wallets stored
    pub wallet_count: usize,
    /// Number of encrypted data entries
    pub encrypted_data_count: usize,
    /// Total storage size in bytes
    pub total_size_bytes: u64,
    /// Available space in bytes
    pub available_space_bytes: Option<u64>,
    /// Last backup timestamp
    pub last_backup: Option<chrono::DateTime<chrono::Utc>>,
    /// Storage health status
    pub health_status: StorageHealth,
}

/// Storage health status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum StorageHealth {
    /// Storage is functioning normally
    Healthy,
    /// Storage has minor issues but is functional
    Warning,
    /// Storage has significant issues
    Error,
    /// Storage is corrupted or inaccessible
    Critical,
}

impl StorageHealth {
    pub fn description(&self) -> &'static str {
        match self {
            StorageHealth::Healthy => "Storage is functioning normally",
            StorageHealth::Warning => "Storage has minor issues but is functional",
            StorageHealth::Error => "Storage has significant issues",
            StorageHealth::Critical => "Storage is corrupted or inaccessible",
        }
    }
}

impl std::fmt::Display for StorageHealth {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            StorageHealth::Healthy => write!(f, "Healthy"),
            StorageHealth::Warning => write!(f, "Warning"),
            StorageHealth::Error => write!(f, "Error"),
            StorageHealth::Critical => write!(f, "Critical"),
        }
    }
}

/// Create storage backend based on configuration
pub async fn create_storage(config: &WalletConfig) -> WalletResult<Box<dyn WalletStorage>> {
    match config.database.max_connections {
        0 => {
            // Use file storage for simple scenarios
            let storage = FileStorage::new(config.storage_path.clone()).await?;
            Ok(Box::new(storage))
        }
        _ => {
            // Use SQLite database storage
            let storage = SqliteStorage::new(config.clone()).await?;
            Ok(Box::new(storage))
        }
    }
}

/// Storage migration utilities
pub struct StorageMigration;

impl StorageMigration {
    /// Migrate data between storage backends
    pub async fn migrate(
        source: &dyn WalletStorage,
        target: &dyn WalletStorage,
    ) -> WalletResult<MigrationResult> {
        let mut result = MigrationResult::new();

        // Migrate wallets
        let wallets = source.list_wallets().await?;
        for wallet in wallets {
            match target.store_wallet(&wallet).await {
                Ok(()) => result.wallets_migrated += 1,
                Err(e) => {
                    result.errors.push(format!("Failed to migrate wallet {}: {}", wallet.id, e));
                    result.wallets_failed += 1;
                }
            }
        }

        // Migrate encrypted data
        let keys = source.list_encrypted_keys().await?;
        for key in keys {
            match source.get_encrypted_data(&key).await {
                Ok(Some(data)) => {
                    match target.store_encrypted_data(&key, &data).await {
                        Ok(()) => result.data_entries_migrated += 1,
                        Err(e) => {
                            result.errors.push(format!("Failed to migrate data {}: {}", key, e));
                            result.data_entries_failed += 1;
                        }
                    }
                }
                Ok(None) => {
                    result.errors.push(format!("Data not found for key: {}", key));
                    result.data_entries_failed += 1;
                }
                Err(e) => {
                    result.errors.push(format!("Failed to read data {}: {}", key, e));
                    result.data_entries_failed += 1;
                }
            }
        }

        Ok(result)
    }

    /// Verify migration integrity
    pub async fn verify_migration(
        source: &dyn WalletStorage,
        target: &dyn WalletStorage,
    ) -> WalletResult<bool> {
        // Compare wallet counts
        let source_wallets = source.list_wallets().await?;
        let target_wallets = target.list_wallets().await?;

        if source_wallets.len() != target_wallets.len() {
            return Ok(false);
        }

        // Verify each wallet exists in target
        for wallet in &source_wallets {
            if !target.wallet_exists(&wallet.id).await? {
                return Ok(false);
            }

            // Verify wallet data integrity
            if let Some(target_wallet) = target.get_wallet(&wallet.id).await? {
                if target_wallet.id != wallet.id ||
                   target_wallet.name != wallet.name ||
                   target_wallet.created_at != wallet.created_at {
                    return Ok(false);
                }
            } else {
                return Ok(false);
            }
        }

        // Compare encrypted data
        let source_keys = source.list_encrypted_keys().await?;
        let target_keys = target.list_encrypted_keys().await?;

        if source_keys.len() != target_keys.len() {
            return Ok(false);
        }

        for key in &source_keys {
            if !target_keys.contains(key) {
                return Ok(false);
            }

            // Verify data integrity
            let source_data = source.get_encrypted_data(key).await?;
            let target_data = target.get_encrypted_data(key).await?;

            if source_data != target_data {
                return Ok(false);
            }
        }

        Ok(true)
    }
}

/// Migration result summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MigrationResult {
    /// Number of wallets successfully migrated
    pub wallets_migrated: usize,
    /// Number of wallets that failed to migrate
    pub wallets_failed: usize,
    /// Number of encrypted data entries migrated
    pub data_entries_migrated: usize,
    /// Number of encrypted data entries that failed
    pub data_entries_failed: usize,
    /// List of errors encountered
    pub errors: Vec<String>,
    /// Migration start time
    pub started_at: chrono::DateTime<chrono::Utc>,
    /// Migration completion time
    pub completed_at: Option<chrono::DateTime<chrono::Utc>>,
}

impl MigrationResult {
    pub fn new() -> Self {
        Self {
            wallets_migrated: 0,
            wallets_failed: 0,
            data_entries_migrated: 0,
            data_entries_failed: 0,
            errors: Vec::new(),
            started_at: chrono::Utc::now(),
            completed_at: None,
        }
    }

    /// Mark migration as completed
    pub fn complete(&mut self) {
        self.completed_at = Some(chrono::Utc::now());
    }

    /// Check if migration was successful
    pub fn is_successful(&self) -> bool {
        self.wallets_failed == 0 && self.data_entries_failed == 0
    }

    /// Get total items migrated
    pub fn total_migrated(&self) -> usize {
        self.wallets_migrated + self.data_entries_migrated
    }

    /// Get total items failed
    pub fn total_failed(&self) -> usize {
        self.wallets_failed + self.data_entries_failed
    }

    /// Get migration duration
    pub fn duration(&self) -> Option<chrono::Duration> {
        self.completed_at.map(|completed| completed - self.started_at)
    }
}

impl Default for MigrationResult {
    fn default() -> Self {
        Self::new()
    }
}

/// Storage configuration options
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageConfig {
    /// Storage backend type
    pub backend: StorageBackend,
    /// Encryption enabled
    pub encryption_enabled: bool,
    /// Automatic backup enabled
    pub auto_backup: bool,
    /// Backup interval in hours
    pub backup_interval_hours: u32,
    /// Maximum number of backups to keep
    pub max_backups: u32,
    /// Compression enabled
    pub compression_enabled: bool,
    /// Vacuum/compact interval in hours
    pub compact_interval_hours: u32,
}

impl Default for StorageConfig {
    fn default() -> Self {
        Self {
            backend: StorageBackend::SQLite,
            encryption_enabled: true,
            auto_backup: true,
            backup_interval_hours: 24,
            max_backups: 7,
            compression_enabled: true,
            compact_interval_hours: 168, // Weekly
        }
    }
}

/// Storage backend types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum StorageBackend {
    /// SQLite database
    SQLite,
    /// File-based storage
    File,
    /// In-memory storage (testing only)
    Memory,
}

impl std::str::FromStr for StorageBackend {
    type Err = WalletError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "sqlite" => Ok(StorageBackend::SQLite),
            "file" => Ok(StorageBackend::File),
            "memory" => Ok(StorageBackend::Memory),
            _ => Err(WalletError::InvalidConfiguration {
                field: "storage_backend".to_string(),
                value: s.to_string(),
            }),
        }
    }
}

impl std::fmt::Display for StorageBackend {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            StorageBackend::SQLite => write!(f, "SQLite"),
            StorageBackend::File => write!(f, "File"),
            StorageBackend::Memory => write!(f, "Memory"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_storage_creation() {
        let temp_dir = TempDir::new().unwrap();
        let config = WalletConfig::default_with_path(temp_dir.path().to_path_buf());

        let storage = create_storage(&config).await.unwrap();
        assert!(storage.initialize().await.is_ok());
        assert!(storage.close().await.is_ok());
    }

    #[test]
    fn test_storage_health() {
        assert_eq!(StorageHealth::Healthy.description(), "Storage is functioning normally");
        assert_eq!(StorageHealth::Critical.to_string(), "Critical");
    }

    #[test]
    fn test_storage_backend_parsing() {
        assert_eq!("sqlite".parse::<StorageBackend>().unwrap(), StorageBackend::SQLite);
        assert_eq!("file".parse::<StorageBackend>().unwrap(), StorageBackend::File);
        assert_eq!("memory".parse::<StorageBackend>().unwrap(), StorageBackend::Memory);
        assert!("invalid".parse::<StorageBackend>().is_err());
    }

    #[test]
    fn test_migration_result() {
        let mut result = MigrationResult::new();
        assert!(!result.is_successful()); // No items migrated yet
        assert_eq!(result.total_migrated(), 0);
        assert_eq!(result.total_failed(), 0);

        result.wallets_migrated = 5;
        result.data_entries_migrated = 10;
        assert_eq!(result.total_migrated(), 15);
        assert!(result.is_successful());

        result.wallets_failed = 1;
        assert!(!result.is_successful());
        assert_eq!(result.total_failed(), 1);

        result.complete();
        assert!(result.completed_at.is_some());
        assert!(result.duration().is_some());
    }

    #[test]
    fn test_storage_config() {
        let config = StorageConfig::default();
        assert_eq!(config.backend, StorageBackend::SQLite);
        assert!(config.encryption_enabled);
        assert!(config.auto_backup);
        assert_eq!(config.backup_interval_hours, 24);
    }
}