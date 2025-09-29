//! Database storage implementation using SQLite

use super::{StorageHealth, StorageStatistics, WalletStorage};
use crate::{
    types::{WalletConfig, WalletInfo, WalletId},
    WalletError, WalletResult,
};
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde_json;
use sqlx::{sqlite::SqlitePool, Pool, Row, Sqlite};
use std::path::Path;
use tokio::fs;
use uuid::Uuid;

/// SQLite database storage implementation
#[derive(Debug)]
pub struct SqliteStorage {
    pool: Pool<Sqlite>,
    config: WalletConfig,
}

impl SqliteStorage {
    /// Create new SQLite storage
    pub async fn new(config: WalletConfig) -> WalletResult<Self> {
        let db_path = config.storage_path.join("wallets.db");

        // Ensure directory exists
        if let Some(parent) = db_path.parent() {
            fs::create_dir_all(parent).await.map_err(|e| WalletError::StorageError {
                message: format!("Failed to create storage directory: {}", e),
            })?;
        }

        // Create database URL
        let database_url = format!("sqlite:{}", db_path.display());

        // Create connection pool
        let pool = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(config.database.max_connections)
            .connect_timeout(std::time::Duration::from_millis(config.database.connection_timeout_ms))
            .connect(&database_url)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to connect to database: {}", e),
            })?;

        Ok(Self { pool, config })
    }

    /// Get database file path
    pub fn database_path(&self) -> std::path::PathBuf {
        self.config.storage_path.join("wallets.db")
    }

    /// Get database size in bytes
    async fn get_database_size(&self) -> WalletResult<u64> {
        let db_path = self.database_path();
        match fs::metadata(&db_path).await {
            Ok(metadata) => Ok(metadata.len()),
            Err(_) => Ok(0),
        }
    }

    /// Check database health
    async fn check_health(&self) -> StorageHealth {
        // Try a simple query
        match sqlx::query("SELECT 1").fetch_optional(&self.pool).await {
            Ok(_) => StorageHealth::Healthy,
            Err(_) => StorageHealth::Error,
        }
    }

    /// Run database maintenance
    async fn vacuum(&self) -> WalletResult<()> {
        sqlx::query("VACUUM")
            .execute(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to vacuum database: {}", e),
            })?;

        Ok(())
    }

    /// Analyze database for optimization
    async fn analyze(&self) -> WalletResult<()> {
        sqlx::query("ANALYZE")
            .execute(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to analyze database: {}", e),
            })?;

        Ok(())
    }
}

#[async_trait]
impl WalletStorage for SqliteStorage {
    async fn initialize(&self) -> WalletResult<()> {
        tracing::info!("Initializing SQLite storage");

        // Create tables
        let create_wallets_table = r#"
            CREATE TABLE IF NOT EXISTS wallets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                wallet_type INTEGER NOT NULL,
                supported_coins TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                last_accessed DATETIME,
                encrypted INTEGER NOT NULL DEFAULT 1,
                backup_created INTEGER NOT NULL DEFAULT 0,
                address_count TEXT NOT NULL DEFAULT '{}',
                cached_balances TEXT NOT NULL DEFAULT '{}',
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        "#;

        let create_encrypted_data_table = r#"
            CREATE TABLE IF NOT EXISTS encrypted_data (
                key TEXT PRIMARY KEY,
                data BLOB NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        "#;

        let create_indexes = vec![
            "CREATE INDEX IF NOT EXISTS idx_wallets_name ON wallets(name)",
            "CREATE INDEX IF NOT EXISTS idx_wallets_created_at ON wallets(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_encrypted_data_created_at ON encrypted_data(created_at)",
        ];

        // Execute table creation
        sqlx::query(create_wallets_table)
            .execute(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to create wallets table: {}", e),
            })?;

        sqlx::query(create_encrypted_data_table)
            .execute(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to create encrypted_data table: {}", e),
            })?;

        // Create indexes
        for index_sql in create_indexes {
            sqlx::query(index_sql)
                .execute(&self.pool)
                .await
                .map_err(|e| WalletError::DatabaseError {
                    message: format!("Failed to create index: {}", e),
                })?;
        }

        // Set pragmas for performance and security
        let pragmas = vec![
            "PRAGMA journal_mode = WAL",
            "PRAGMA synchronous = NORMAL",
            "PRAGMA cache_size = -64000", // 64MB cache
            "PRAGMA temp_store = memory",
            "PRAGMA mmap_size = 268435456", // 256MB mmap
        ];

        for pragma in pragmas {
            sqlx::query(pragma)
                .execute(&self.pool)
                .await
                .map_err(|e| WalletError::DatabaseError {
                    message: format!("Failed to set pragma: {}", e),
                })?;
        }

        tracing::info!("SQLite storage initialized successfully");
        Ok(())
    }

    async fn close(&self) -> WalletResult<()> {
        tracing::info!("Closing SQLite storage");
        self.pool.close().await;
        Ok(())
    }

    async fn store_wallet(&self, wallet_info: &WalletInfo) -> WalletResult<()> {
        let supported_coins = serde_json::to_string(&wallet_info.supported_coins)
            .map_err(|e| WalletError::SerializationError {
                message: format!("Failed to serialize supported coins: {}", e),
            })?;

        let address_count = serde_json::to_string(&wallet_info.address_count)
            .map_err(|e| WalletError::SerializationError {
                message: format!("Failed to serialize address count: {}", e),
            })?;

        let cached_balances = serde_json::to_string(&wallet_info.cached_balances)
            .map_err(|e| WalletError::SerializationError {
                message: format!("Failed to serialize cached balances: {}", e),
            })?;

        let metadata = serde_json::to_string(&wallet_info.metadata)
            .map_err(|e| WalletError::SerializationError {
                message: format!("Failed to serialize metadata: {}", e),
            })?;

        sqlx::query(
            r#"
            INSERT INTO wallets (
                id, name, wallet_type, supported_coins, created_at, last_accessed,
                encrypted, backup_created, address_count, cached_balances, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            "#,
        )
        .bind(wallet_info.id.to_string())
        .bind(&wallet_info.name)
        .bind(wallet_info.wallet_type as i32)
        .bind(&supported_coins)
        .bind(wallet_info.created_at)
        .bind(wallet_info.last_accessed)
        .bind(wallet_info.encrypted as i32)
        .bind(wallet_info.backup_created as i32)
        .bind(&address_count)
        .bind(&cached_balances)
        .bind(&metadata)
        .execute(&self.pool)
        .await
        .map_err(|e| WalletError::DatabaseError {
            message: format!("Failed to store wallet: {}", e),
        })?;

        Ok(())
    }

    async fn get_wallet(&self, wallet_id: &WalletId) -> WalletResult<Option<WalletInfo>> {
        let row = sqlx::query(
            "SELECT id, name, wallet_type, supported_coins, created_at, last_accessed, encrypted, backup_created, address_count, cached_balances, metadata FROM wallets WHERE id = ?"
        )
        .bind(wallet_id.to_string())
        .fetch_optional(&self.pool)
        .await
        .map_err(|e| WalletError::DatabaseError {
            message: format!("Failed to get wallet: {}", e),
        })?;

        if let Some(row) = row {
            let wallet_info = self.row_to_wallet_info(row)?;
            Ok(Some(wallet_info))
        } else {
            Ok(None)
        }
    }

    async fn update_wallet(&self, wallet_info: &WalletInfo) -> WalletResult<()> {
        let supported_coins = serde_json::to_string(&wallet_info.supported_coins)
            .map_err(|e| WalletError::SerializationError {
                message: format!("Failed to serialize supported coins: {}", e),
            })?;

        let address_count = serde_json::to_string(&wallet_info.address_count)
            .map_err(|e| WalletError::SerializationError {
                message: format!("Failed to serialize address count: {}", e),
            })?;

        let cached_balances = serde_json::to_string(&wallet_info.cached_balances)
            .map_err(|e| WalletError::SerializationError {
                message: format!("Failed to serialize cached balances: {}", e),
            })?;

        let metadata = serde_json::to_string(&wallet_info.metadata)
            .map_err(|e| WalletError::SerializationError {
                message: format!("Failed to serialize metadata: {}", e),
            })?;

        sqlx::query(
            r#"
            UPDATE wallets SET
                name = ?, wallet_type = ?, supported_coins = ?, last_accessed = ?,
                encrypted = ?, backup_created = ?, address_count = ?, cached_balances = ?, metadata = ?
            WHERE id = ?
            "#,
        )
        .bind(&wallet_info.name)
        .bind(wallet_info.wallet_type as i32)
        .bind(&supported_coins)
        .bind(wallet_info.last_accessed)
        .bind(wallet_info.encrypted as i32)
        .bind(wallet_info.backup_created as i32)
        .bind(&address_count)
        .bind(&cached_balances)
        .bind(&metadata)
        .bind(wallet_info.id.to_string())
        .execute(&self.pool)
        .await
        .map_err(|e| WalletError::DatabaseError {
            message: format!("Failed to update wallet: {}", e),
        })?;

        Ok(())
    }

    async fn delete_wallet(&self, wallet_id: &WalletId) -> WalletResult<()> {
        sqlx::query("DELETE FROM wallets WHERE id = ?")
            .bind(wallet_id.to_string())
            .execute(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to delete wallet: {}", e),
            })?;

        Ok(())
    }

    async fn list_wallets(&self) -> WalletResult<Vec<WalletInfo>> {
        let rows = sqlx::query(
            "SELECT id, name, wallet_type, supported_coins, created_at, last_accessed, encrypted, backup_created, address_count, cached_balances, metadata FROM wallets ORDER BY created_at DESC"
        )
        .fetch_all(&self.pool)
        .await
        .map_err(|e| WalletError::DatabaseError {
            message: format!("Failed to list wallets: {}", e),
        })?;

        let mut wallets = Vec::new();
        for row in rows {
            wallets.push(self.row_to_wallet_info(row)?);
        }

        Ok(wallets)
    }

    async fn store_encrypted_data(&self, key: &str, data: &[u8]) -> WalletResult<()> {
        sqlx::query(
            r#"
            INSERT OR REPLACE INTO encrypted_data (key, data, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            "#,
        )
        .bind(key)
        .bind(data)
        .execute(&self.pool)
        .await
        .map_err(|e| WalletError::DatabaseError {
            message: format!("Failed to store encrypted data: {}", e),
        })?;

        Ok(())
    }

    async fn get_encrypted_data(&self, key: &str) -> WalletResult<Option<Vec<u8>>> {
        let row = sqlx::query("SELECT data FROM encrypted_data WHERE key = ?")
            .bind(key)
            .fetch_optional(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to get encrypted data: {}", e),
            })?;

        if let Some(row) = row {
            let data: Vec<u8> = row.get("data");
            Ok(Some(data))
        } else {
            Ok(None)
        }
    }

    async fn delete_encrypted_data(&self, key: &str) -> WalletResult<()> {
        sqlx::query("DELETE FROM encrypted_data WHERE key = ?")
            .bind(key)
            .execute(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to delete encrypted data: {}", e),
            })?;

        Ok(())
    }

    async fn list_encrypted_keys(&self) -> WalletResult<Vec<String>> {
        let rows = sqlx::query("SELECT key FROM encrypted_data ORDER BY created_at")
            .fetch_all(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to list encrypted keys: {}", e),
            })?;

        let keys = rows.iter().map(|row| row.get::<String, _>("key")).collect();
        Ok(keys)
    }

    async fn wallet_exists(&self, wallet_id: &WalletId) -> WalletResult<bool> {
        let row = sqlx::query("SELECT 1 FROM wallets WHERE id = ? LIMIT 1")
            .bind(wallet_id.to_string())
            .fetch_optional(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to check wallet existence: {}", e),
            })?;

        Ok(row.is_some())
    }

    async fn get_statistics(&self) -> WalletResult<StorageStatistics> {
        // Get wallet count
        let wallet_count_row = sqlx::query("SELECT COUNT(*) as count FROM wallets")
            .fetch_one(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to get wallet count: {}", e),
            })?;
        let wallet_count: i64 = wallet_count_row.get("count");

        // Get encrypted data count
        let data_count_row = sqlx::query("SELECT COUNT(*) as count FROM encrypted_data")
            .fetch_one(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to get encrypted data count: {}", e),
            })?;
        let encrypted_data_count: i64 = data_count_row.get("count");

        // Get database size
        let total_size_bytes = self.get_database_size().await?;

        // Check health
        let health_status = self.check_health().await;

        Ok(StorageStatistics {
            wallet_count: wallet_count as usize,
            encrypted_data_count: encrypted_data_count as usize,
            total_size_bytes,
            available_space_bytes: None, // Would need filesystem info
            last_backup: None, // Would track in metadata
            health_status,
        })
    }

    async fn backup(&self, backup_path: &Path) -> WalletResult<()> {
        // Copy database file
        let db_path = self.database_path();

        if let Some(parent) = backup_path.parent() {
            fs::create_dir_all(parent).await.map_err(|e| WalletError::StorageError {
                message: format!("Failed to create backup directory: {}", e),
            })?;
        }

        fs::copy(&db_path, backup_path).await.map_err(|e| WalletError::StorageError {
            message: format!("Failed to backup database: {}", e),
        })?;

        tracing::info!("Database backed up to: {}", backup_path.display());
        Ok(())
    }

    async fn restore(&self, backup_path: &Path) -> WalletResult<()> {
        let db_path = self.database_path();

        // Close existing connections
        self.pool.close().await;

        // Copy backup file
        fs::copy(backup_path, &db_path).await.map_err(|e| WalletError::StorageError {
            message: format!("Failed to restore database: {}", e),
        })?;

        tracing::info!("Database restored from: {}", backup_path.display());
        Ok(())
    }

    async fn compact(&self) -> WalletResult<()> {
        tracing::info!("Compacting database");

        self.vacuum().await?;
        self.analyze().await?;

        tracing::info!("Database compaction completed");
        Ok(())
    }
}

impl SqliteStorage {
    /// Convert database row to WalletInfo
    fn row_to_wallet_info(&self, row: sqlx::sqlite::SqliteRow) -> WalletResult<WalletInfo> {
        let id_str: String = row.get("id");
        let id = Uuid::parse_str(&id_str).map_err(|e| WalletError::DeserializationError {
            message: format!("Invalid wallet ID: {}", e),
        })?;

        let wallet_type_int: i32 = row.get("wallet_type");
        let wallet_type = match wallet_type_int {
            0 => crate::types::WalletType::HD,
            1 => crate::types::WalletType::MultiSignature,
            #[cfg(feature = "hardware-wallet")]
            2 => crate::types::WalletType::Hardware,
            3 => crate::types::WalletType::WatchOnly,
            _ => return Err(WalletError::DeserializationError {
                message: format!("Unknown wallet type: {}", wallet_type_int),
            }),
        };

        let supported_coins_str: String = row.get("supported_coins");
        let supported_coins = serde_json::from_str(&supported_coins_str)
            .map_err(|e| WalletError::DeserializationError {
                message: format!("Failed to deserialize supported coins: {}", e),
            })?;

        let address_count_str: String = row.get("address_count");
        let address_count = serde_json::from_str(&address_count_str)
            .map_err(|e| WalletError::DeserializationError {
                message: format!("Failed to deserialize address count: {}", e),
            })?;

        let cached_balances_str: String = row.get("cached_balances");
        let cached_balances = serde_json::from_str(&cached_balances_str)
            .map_err(|e| WalletError::DeserializationError {
                message: format!("Failed to deserialize cached balances: {}", e),
            })?;

        let metadata_str: String = row.get("metadata");
        let metadata = serde_json::from_str(&metadata_str)
            .map_err(|e| WalletError::DeserializationError {
                message: format!("Failed to deserialize metadata: {}", e),
            })?;

        let created_at: DateTime<Utc> = row.get("created_at");
        let last_accessed: Option<DateTime<Utc>> = row.get("last_accessed");
        let encrypted: i32 = row.get("encrypted");
        let backup_created: i32 = row.get("backup_created");

        Ok(WalletInfo {
            id,
            name: row.get("name"),
            wallet_type,
            supported_coins,
            created_at,
            last_accessed,
            encrypted: encrypted != 0,
            backup_created: backup_created != 0,
            address_count,
            cached_balances,
            metadata,
        })
    }
}

/// Database storage interface
pub trait DatabaseStorage: WalletStorage {
    /// Get database pool for direct access
    fn pool(&self) -> &Pool<Sqlite>;

    /// Execute raw SQL query
    async fn execute_raw(&self, sql: &str) -> WalletResult<u64>;

    /// Run database maintenance tasks
    async fn maintenance(&self) -> WalletResult<()>;
}

impl DatabaseStorage for SqliteStorage {
    fn pool(&self) -> &Pool<Sqlite> {
        &self.pool
    }

    async fn execute_raw(&self, sql: &str) -> WalletResult<u64> {
        let result = sqlx::query(sql)
            .execute(&self.pool)
            .await
            .map_err(|e| WalletError::DatabaseError {
                message: format!("Failed to execute raw SQL: {}", e),
            })?;

        Ok(result.rows_affected())
    }

    async fn maintenance(&self) -> WalletResult<()> {
        self.compact().await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{CoinType, WalletMetadata, WalletType};
    use tempfile::TempDir;

    async fn create_test_storage() -> (SqliteStorage, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let config = WalletConfig::default_with_path(temp_dir.path().to_path_buf());
        let storage = SqliteStorage::new(config).await.unwrap();
        (storage, temp_dir)
    }

    fn create_test_wallet() -> WalletInfo {
        use std::collections::HashMap;

        WalletInfo {
            id: Uuid::new_v4(),
            name: "Test Wallet".to_string(),
            wallet_type: WalletType::HD,
            supported_coins: vec![CoinType::Bitcoin, CoinType::Ethereum],
            created_at: Utc::now(),
            last_accessed: None,
            encrypted: true,
            backup_created: false,
            address_count: HashMap::new(),
            cached_balances: HashMap::new(),
            metadata: WalletMetadata::default(),
        }
    }

    #[tokio::test]
    async fn test_storage_initialization() {
        let (storage, _temp_dir) = create_test_storage().await;
        assert!(storage.initialize().await.is_ok());
        assert!(storage.close().await.is_ok());
    }

    #[tokio::test]
    async fn test_wallet_operations() {
        let (storage, _temp_dir) = create_test_storage().await;
        storage.initialize().await.unwrap();

        let wallet = create_test_wallet();

        // Store wallet
        assert!(storage.store_wallet(&wallet).await.is_ok());

        // Check existence
        assert!(storage.wallet_exists(&wallet.id).await.unwrap());

        // Retrieve wallet
        let retrieved = storage.get_wallet(&wallet.id).await.unwrap();
        assert!(retrieved.is_some());
        let retrieved = retrieved.unwrap();
        assert_eq!(retrieved.id, wallet.id);
        assert_eq!(retrieved.name, wallet.name);

        // Update wallet
        let mut updated_wallet = wallet.clone();
        updated_wallet.name = "Updated Wallet".to_string();
        assert!(storage.update_wallet(&updated_wallet).await.is_ok());

        let retrieved = storage.get_wallet(&wallet.id).await.unwrap().unwrap();
        assert_eq!(retrieved.name, "Updated Wallet");

        // List wallets
        let wallets = storage.list_wallets().await.unwrap();
        assert_eq!(wallets.len(), 1);

        // Delete wallet
        assert!(storage.delete_wallet(&wallet.id).await.is_ok());
        assert!(!storage.wallet_exists(&wallet.id).await.unwrap());
    }

    #[tokio::test]
    async fn test_encrypted_data_operations() {
        let (storage, _temp_dir) = create_test_storage().await;
        storage.initialize().await.unwrap();

        let key = "test_key";
        let data = b"test_encrypted_data";

        // Store encrypted data
        assert!(storage.store_encrypted_data(key, data).await.is_ok());

        // Retrieve encrypted data
        let retrieved = storage.get_encrypted_data(key).await.unwrap();
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap(), data);

        // List keys
        let keys = storage.list_encrypted_keys().await.unwrap();
        assert_eq!(keys.len(), 1);
        assert_eq!(keys[0], key);

        // Delete encrypted data
        assert!(storage.delete_encrypted_data(key).await.is_ok());
        let retrieved = storage.get_encrypted_data(key).await.unwrap();
        assert!(retrieved.is_none());
    }

    #[tokio::test]
    async fn test_statistics() {
        let (storage, _temp_dir) = create_test_storage().await;
        storage.initialize().await.unwrap();

        let wallet = create_test_wallet();
        storage.store_wallet(&wallet).await.unwrap();
        storage.store_encrypted_data("test_key", b"test_data").await.unwrap();

        let stats = storage.get_statistics().await.unwrap();
        assert_eq!(stats.wallet_count, 1);
        assert_eq!(stats.encrypted_data_count, 1);
        assert!(stats.total_size_bytes > 0);
    }

    #[tokio::test]
    async fn test_backup_restore() {
        let (storage, temp_dir) = create_test_storage().await;
        storage.initialize().await.unwrap();

        let wallet = create_test_wallet();
        storage.store_wallet(&wallet).await.unwrap();

        let backup_path = temp_dir.path().join("backup.db");
        assert!(storage.backup(&backup_path).await.is_ok());
        assert!(backup_path.exists());

        // Create new storage and restore
        let (new_storage, _temp_dir2) = create_test_storage().await;
        new_storage.initialize().await.unwrap();
        assert!(new_storage.restore(&backup_path).await.is_ok());
    }
}