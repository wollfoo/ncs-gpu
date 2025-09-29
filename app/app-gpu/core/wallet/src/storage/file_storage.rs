//! File-based storage implementation

use super::{StorageHealth, StorageStatistics, WalletStorage};
use crate::{
    types::{WalletInfo, WalletId},
    WalletError, WalletResult,
};
use async_trait::async_trait;
use std::path::PathBuf;
use tokio::fs;

/// File-based storage implementation
#[derive(Debug)]
pub struct FileStorage {
    storage_path: PathBuf,
}

impl FileStorage {
    /// Create new file storage
    pub async fn new(storage_path: PathBuf) -> WalletResult<Self> {
        // Ensure directory exists
        fs::create_dir_all(&storage_path).await.map_err(|e| WalletError::StorageError {
            message: format!("Failed to create storage directory: {}", e),
        })?;

        Ok(Self { storage_path })
    }

    /// Get wallet file path
    fn wallet_file_path(&self, wallet_id: &WalletId) -> PathBuf {
        self.storage_path.join(format!("{}.json", wallet_id))
    }

    /// Get encrypted data file path
    fn encrypted_data_file_path(&self, key: &str) -> PathBuf {
        self.storage_path.join("encrypted").join(format!("{}.bin", key))
    }
}

#[async_trait]
impl WalletStorage for FileStorage {
    async fn initialize(&self) -> WalletResult<()> {
        let encrypted_dir = self.storage_path.join("encrypted");
        fs::create_dir_all(&encrypted_dir).await.map_err(|e| WalletError::StorageError {
            message: format!("Failed to create encrypted data directory: {}", e),
        })?;
        Ok(())
    }

    async fn close(&self) -> WalletResult<()> {
        Ok(())
    }

    async fn store_wallet(&self, wallet_info: &WalletInfo) -> WalletResult<()> {
        let file_path = self.wallet_file_path(&wallet_info.id);
        let json = serde_json::to_string_pretty(wallet_info)?;

        fs::write(&file_path, json).await.map_err(|e| WalletError::StorageError {
            message: format!("Failed to write wallet file: {}", e),
        })?;

        Ok(())
    }

    async fn get_wallet(&self, wallet_id: &WalletId) -> WalletResult<Option<WalletInfo>> {
        let file_path = self.wallet_file_path(wallet_id);

        match fs::read_to_string(&file_path).await {
            Ok(json) => {
                let wallet_info: WalletInfo = serde_json::from_str(&json)?;
                Ok(Some(wallet_info))
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(e) => Err(WalletError::StorageError {
                message: format!("Failed to read wallet file: {}", e),
            }),
        }
    }

    async fn update_wallet(&self, wallet_info: &WalletInfo) -> WalletResult<()> {
        self.store_wallet(wallet_info).await
    }

    async fn delete_wallet(&self, wallet_id: &WalletId) -> WalletResult<()> {
        let file_path = self.wallet_file_path(wallet_id);

        if file_path.exists() {
            fs::remove_file(&file_path).await.map_err(|e| WalletError::StorageError {
                message: format!("Failed to delete wallet file: {}", e),
            })?;
        }

        Ok(())
    }

    async fn list_wallets(&self) -> WalletResult<Vec<WalletInfo>> {
        let mut wallets = Vec::new();
        let mut dir = fs::read_dir(&self.storage_path).await.map_err(|e| WalletError::StorageError {
            message: format!("Failed to read storage directory: {}", e),
        })?;

        while let Some(entry) = dir.next_entry().await.map_err(|e| WalletError::StorageError {
            message: format!("Failed to read directory entry: {}", e),
        })? {
            let path = entry.path();

            if path.extension().and_then(|s| s.to_str()) == Some("json") {
                if let Ok(json) = fs::read_to_string(&path).await {
                    if let Ok(wallet_info) = serde_json::from_str::<WalletInfo>(&json) {
                        wallets.push(wallet_info);
                    }
                }
            }
        }

        Ok(wallets)
    }

    async fn store_encrypted_data(&self, key: &str, data: &[u8]) -> WalletResult<()> {
        let file_path = self.encrypted_data_file_path(key);

        if let Some(parent) = file_path.parent() {
            fs::create_dir_all(parent).await.map_err(|e| WalletError::StorageError {
                message: format!("Failed to create encrypted data directory: {}", e),
            })?;
        }

        fs::write(&file_path, data).await.map_err(|e| WalletError::StorageError {
            message: format!("Failed to write encrypted data: {}", e),
        })?;

        Ok(())
    }

    async fn get_encrypted_data(&self, key: &str) -> WalletResult<Option<Vec<u8>>> {
        let file_path = self.encrypted_data_file_path(key);

        match fs::read(&file_path).await {
            Ok(data) => Ok(Some(data)),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(e) => Err(WalletError::StorageError {
                message: format!("Failed to read encrypted data: {}", e),
            }),
        }
    }

    async fn delete_encrypted_data(&self, key: &str) -> WalletResult<()> {
        let file_path = self.encrypted_data_file_path(key);

        if file_path.exists() {
            fs::remove_file(&file_path).await.map_err(|e| WalletError::StorageError {
                message: format!("Failed to delete encrypted data: {}", e),
            })?;
        }

        Ok(())
    }

    async fn list_encrypted_keys(&self) -> WalletResult<Vec<String>> {
        let encrypted_dir = self.storage_path.join("encrypted");
        let mut keys = Vec::new();

        if !encrypted_dir.exists() {
            return Ok(keys);
        }

        let mut dir = fs::read_dir(&encrypted_dir).await.map_err(|e| WalletError::StorageError {
            message: format!("Failed to read encrypted data directory: {}", e),
        })?;

        while let Some(entry) = dir.next_entry().await.map_err(|e| WalletError::StorageError {
            message: format!("Failed to read directory entry: {}", e),
        })? {
            let path = entry.path();

            if path.extension().and_then(|s| s.to_str()) == Some("bin") {
                if let Some(file_stem) = path.file_stem().and_then(|s| s.to_str()) {
                    keys.push(file_stem.to_string());
                }
            }
        }

        Ok(keys)
    }

    async fn wallet_exists(&self, wallet_id: &WalletId) -> WalletResult<bool> {
        let file_path = self.wallet_file_path(wallet_id);
        Ok(file_path.exists())
    }

    async fn get_statistics(&self) -> WalletResult<StorageStatistics> {
        let wallets = self.list_wallets().await?;
        let encrypted_keys = self.list_encrypted_keys().await?;

        // Calculate total size (simplified)
        let mut total_size = 0u64;

        // Add wallet files size
        for wallet in &wallets {
            let file_path = self.wallet_file_path(&wallet.id);
            if let Ok(metadata) = fs::metadata(&file_path).await {
                total_size += metadata.len();
            }
        }

        // Add encrypted data size
        for key in &encrypted_keys {
            let file_path = self.encrypted_data_file_path(key);
            if let Ok(metadata) = fs::metadata(&file_path).await {
                total_size += metadata.len();
            }
        }

        Ok(StorageStatistics {
            wallet_count: wallets.len(),
            encrypted_data_count: encrypted_keys.len(),
            total_size_bytes: total_size,
            available_space_bytes: None,
            last_backup: None,
            health_status: StorageHealth::Healthy,
        })
    }

    async fn backup(&self, backup_path: &std::path::Path) -> WalletResult<()> {
        // Simple backup: copy entire storage directory
        if let Some(parent) = backup_path.parent() {
            fs::create_dir_all(parent).await.map_err(|e| WalletError::StorageError {
                message: format!("Failed to create backup directory: {}", e),
            })?;
        }

        copy_dir(&self.storage_path, backup_path).await?;
        Ok(())
    }

    async fn restore(&self, backup_path: &std::path::Path) -> WalletResult<()> {
        // Simple restore: copy backup to storage directory
        copy_dir(backup_path, &self.storage_path).await?;
        Ok(())
    }

    async fn compact(&self) -> WalletResult<()> {
        // File storage doesn't need compaction
        Ok(())
    }
}

/// Recursively copy directory
async fn copy_dir(src: &std::path::Path, dst: &std::path::Path) -> WalletResult<()> {
    fs::create_dir_all(dst).await.map_err(|e| WalletError::StorageError {
        message: format!("Failed to create destination directory: {}", e),
    })?;

    let mut dir = fs::read_dir(src).await.map_err(|e| WalletError::StorageError {
        message: format!("Failed to read source directory: {}", e),
    })?;

    while let Some(entry) = dir.next_entry().await.map_err(|e| WalletError::StorageError {
        message: format!("Failed to read directory entry: {}", e),
    })? {
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());

        if src_path.is_dir() {
            copy_dir(&src_path, &dst_path).await?;
        } else {
            fs::copy(&src_path, &dst_path).await.map_err(|e| WalletError::StorageError {
                message: format!("Failed to copy file: {}", e),
            })?;
        }
    }

    Ok(())
}