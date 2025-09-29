use anyhow::Result;
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use uuid::Uuid;

// Public modules
pub mod kv;
pub mod transactions;
pub mod backup;
pub mod migration;
pub mod encryption;
pub mod compression;

// Re-export public types
pub use kv::{KeyValueStore, StorageBackend, StorageConfig, StorageStats};
pub use transactions::{Transaction, TransactionManager, TransactionState, TransactionStats};
pub use backup::{BackupManager, BackupConfig, BackupInfo, RestoreOptions};
pub use migration::{MigrationManager, Migration, MigrationState, MigrationHistory};
pub use encryption::{EncryptionEngine, EncryptionConfig, EncryptionError};
pub use compression::{CompressionEngine, CompressionType, CompressionConfig};

/// Storage value with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageValue {
    /// Actual value data
    pub data: Vec<u8>,
    /// Value metadata
    pub metadata: ValueMetadata,
    /// Value version for optimistic concurrency
    pub version: u64,
    /// Checksum for data integrity
    pub checksum: String,
}

/// Value metadata
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ValueMetadata {
    /// Content type
    pub content_type: Option<String>,
    /// Creation timestamp
    pub created_at: DateTime<Utc>,
    /// Last modification timestamp
    pub modified_at: DateTime<Utc>,
    /// Expiration time (TTL)
    pub expires_at: Option<DateTime<Utc>>,
    /// Custom tags
    pub tags: HashMap<String, String>,
    /// Access count
    pub access_count: u64,
    /// Last access time
    pub last_access: DateTime<Utc>,
    /// Data compression info
    pub compression: Option<CompressionInfo>,
    /// Encryption info
    pub encryption: Option<EncryptionInfo>,
}

/// Compression information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompressionInfo {
    /// Compression algorithm used
    pub algorithm: CompressionType,
    /// Original size before compression
    pub original_size: u64,
    /// Compressed size
    pub compressed_size: u64,
    /// Compression ratio
    pub ratio: f32,
}

/// Encryption information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptionInfo {
    /// Encryption algorithm used
    pub algorithm: String,
    /// Key ID (not the actual key)
    pub key_id: String,
    /// Initialization vector
    pub iv: Vec<u8>,
    /// Authentication tag
    pub tag: Vec<u8>,
}

/// Storage operation result
#[derive(Debug, Clone)]
pub struct StorageResult<T> {
    /// Operation result
    pub data: T,
    /// Operation metrics
    pub metrics: OperationMetrics,
}

/// Operation metrics
#[derive(Debug, Clone, Default)]
pub struct OperationMetrics {
    /// Duration in microseconds
    pub duration_us: u64,
    /// Bytes read
    pub bytes_read: u64,
    /// Bytes written
    pub bytes_written: u64,
    /// Cache hit/miss
    pub cache_hit: bool,
}

/// Storage query for advanced operations
#[derive(Debug, Clone)]
pub struct StorageQuery {
    /// Key prefix filter
    pub prefix: Option<String>,
    /// Key pattern (glob-style)
    pub pattern: Option<String>,
    /// Tag filters
    pub tags: HashMap<String, String>,
    /// Minimum creation time
    pub created_after: Option<DateTime<Utc>>,
    /// Maximum creation time
    pub created_before: Option<DateTime<Utc>>,
    /// Limit number of results
    pub limit: Option<usize>,
    /// Skip first N results
    pub skip: Option<usize>,
}

/// Storage iterator result
#[derive(Debug, Clone)]
pub struct StorageEntry {
    /// Entry key
    pub key: String,
    /// Entry value
    pub value: StorageValue,
}

/// Error types for storage operations
#[derive(thiserror::Error, Debug)]
pub enum StorageError {
    #[error("Key not found: {0}")]
    KeyNotFound(String),

    #[error("Transaction conflict: {0}")]
    TransactionConflict(String),

    #[error("Transaction not found: {0}")]
    TransactionNotFound(String),

    #[error("Serialization error: {0}")]
    SerializationError(String),

    #[error("Backend error: {0}")]
    BackendError(String),

    #[error("Encryption error: {0}")]
    EncryptionError(String),

    #[error("Compression error: {0}")]
    CompressionError(String),

    #[error("Backup error: {0}")]
    BackupError(String),

    #[error("Migration error: {0}")]
    MigrationError(String),

    #[error("Configuration error: {0}")]
    ConfigError(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

/// Main storage interface
#[async_trait]
pub trait Storage: Send + Sync {
    /// Get a value by key
    async fn get(&self, key: &str) -> Result<Option<StorageValue>>;

    /// Put a value with key
    async fn put(&self, key: &str, value: Vec<u8>) -> Result<()>;

    /// Put a value with metadata
    async fn put_with_metadata(&self, key: &str, value: Vec<u8>, metadata: ValueMetadata) -> Result<()>;

    /// Delete a value by key
    async fn delete(&self, key: &str) -> Result<bool>;

    /// Check if key exists
    async fn exists(&self, key: &str) -> Result<bool>;

    /// List keys with optional prefix
    async fn list_keys(&self, prefix: Option<&str>) -> Result<Vec<String>>;

    /// Query storage with filters
    async fn query(&self, query: StorageQuery) -> Result<Vec<StorageEntry>>;

    /// Get multiple values at once
    async fn batch_get(&self, keys: &[String]) -> Result<HashMap<String, Option<StorageValue>>>;

    /// Put multiple values at once
    async fn batch_put(&self, entries: HashMap<String, Vec<u8>>) -> Result<()>;

    /// Delete multiple keys at once
    async fn batch_delete(&self, keys: &[String]) -> Result<Vec<bool>>;

    /// Get storage statistics
    async fn get_stats(&self) -> Result<StorageStats>;

    /// Compact storage (if supported)
    async fn compact(&self) -> Result<()>;

    /// Create a backup
    async fn backup(&self, path: &str) -> Result<BackupInfo>;

    /// Restore from backup
    async fn restore(&self, backup_path: &str, options: RestoreOptions) -> Result<()>;

    /// Clear all data
    async fn clear(&self) -> Result<()>;

    /// Close the storage
    async fn close(&self) -> Result<()>;
}

/// Storage factory for creating storage instances
pub struct StorageFactory;

impl StorageFactory {
    /// Create a new storage instance
    pub async fn create(config: StorageConfig) -> Result<Box<dyn Storage>> {
        match config.backend {
            StorageBackend::RocksDB => {
                #[cfg(feature = "rocksdb")]
                {
                    let store = kv::RocksDBStore::new(config).await?;
                    Ok(Box::new(store))
                }
                #[cfg(not(feature = "rocksdb"))]
                {
                    Err(StorageError::ConfigError("RocksDB feature not enabled".to_string()).into())
                }
            }
            StorageBackend::Sled => {
                #[cfg(feature = "sled")]
                {
                    let store = kv::SledStore::new(config).await?;
                    Ok(Box::new(store))
                }
                #[cfg(not(feature = "sled"))]
                {
                    Err(StorageError::ConfigError("Sled feature not enabled".to_string()).into())
                }
            }
            StorageBackend::Memory => {
                let store = kv::MemoryStore::new(config).await?;
                Ok(Box::new(store))
            }
        }
    }
}

impl Default for StorageQuery {
    fn default() -> Self {
        Self {
            prefix: None,
            pattern: None,
            tags: HashMap::new(),
            created_after: None,
            created_before: None,
            limit: None,
            skip: None,
        }
    }
}

impl StorageValue {
    /// Create a new storage value
    pub fn new(data: Vec<u8>) -> Self {
        let checksum = blake3::hash(&data).to_hex().to_string();

        Self {
            data,
            metadata: ValueMetadata {
                created_at: Utc::now(),
                modified_at: Utc::now(),
                last_access: Utc::now(),
                ..Default::default()
            },
            version: 1,
            checksum,
        }
    }

    /// Create a new storage value with metadata
    pub fn with_metadata(data: Vec<u8>, metadata: ValueMetadata) -> Self {
        let checksum = blake3::hash(&data).to_hex().to_string();

        Self {
            data,
            metadata,
            version: 1,
            checksum,
        }
    }

    /// Verify data integrity
    pub fn verify_checksum(&self) -> bool {
        let expected = blake3::hash(&self.data).to_hex().to_string();
        self.checksum == expected
    }

    /// Check if value has expired
    pub fn is_expired(&self) -> bool {
        if let Some(expires_at) = self.metadata.expires_at {
            Utc::now() > expires_at
        } else {
            false
        }
    }

    /// Update access time and count
    pub fn mark_accessed(&mut self) {
        self.metadata.last_access = Utc::now();
        self.metadata.access_count += 1;
    }

    /// Get data size
    pub fn size(&self) -> usize {
        self.data.len()
    }

    /// Get metadata size
    pub fn metadata_size(&self) -> usize {
        serde_json::to_vec(&self.metadata).map(|v| v.len()).unwrap_or(0)
    }

    /// Get total size (data + metadata)
    pub fn total_size(&self) -> usize {
        self.size() + self.metadata_size()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_storage_value_creation() {
        let data = b"test data".to_vec();
        let value = StorageValue::new(data.clone());

        assert_eq!(value.data, data);
        assert_eq!(value.version, 1);
        assert!(value.verify_checksum());
        assert!(!value.is_expired());
    }

    #[test]
    fn test_storage_value_expiration() {
        let data = b"test data".to_vec();
        let mut metadata = ValueMetadata::default();
        metadata.expires_at = Some(Utc::now() - chrono::Duration::hours(1)); // Expired 1 hour ago

        let value = StorageValue::with_metadata(data, metadata);
        assert!(value.is_expired());
    }

    #[test]
    fn test_storage_value_access_tracking() {
        let data = b"test data".to_vec();
        let mut value = StorageValue::new(data);

        assert_eq!(value.metadata.access_count, 0);

        value.mark_accessed();
        assert_eq!(value.metadata.access_count, 1);

        value.mark_accessed();
        assert_eq!(value.metadata.access_count, 2);
    }
}