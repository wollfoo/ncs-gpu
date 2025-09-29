use crate::{Storage, StorageValue, StorageQuery, StorageEntry, StorageError, ValueMetadata, OperationMetrics, StorageResult, BackupInfo, RestoreOptions};
use anyhow::Result;
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Instant;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};
use uuid::Uuid;

/// Storage backend types
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum StorageBackend {
    RocksDB,
    Sled,
    Memory,
}

/// Storage configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageConfig {
    /// Storage backend type
    pub backend: StorageBackend,
    /// Storage path
    pub path: PathBuf,
    /// Enable compression
    pub enable_compression: bool,
    /// Enable encryption
    pub enable_encryption: bool,
    /// Cache size in bytes
    pub cache_size: usize,
    /// Write buffer size
    pub write_buffer_size: usize,
    /// Maximum number of open files
    pub max_open_files: i32,
    /// Enable WAL (Write-Ahead Log)
    pub enable_wal: bool,
    /// WAL sync mode
    pub wal_sync: bool,
    /// Background compaction
    pub enable_compaction: bool,
    /// Statistics collection
    pub enable_stats: bool,
    /// TTL cleanup interval (seconds)
    pub ttl_cleanup_interval: u64,
}

/// Storage statistics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct StorageStats {
    /// Total number of keys
    pub total_keys: u64,
    /// Total data size in bytes
    pub total_size: u64,
    /// Number of reads
    pub read_count: u64,
    /// Number of writes
    pub write_count: u64,
    /// Number of deletes
    pub delete_count: u64,
    /// Cache hit ratio
    pub cache_hit_ratio: f64,
    /// Average read latency (microseconds)
    pub avg_read_latency_us: u64,
    /// Average write latency (microseconds)
    pub avg_write_latency_us: u64,
    /// Storage engine specific stats
    pub engine_stats: HashMap<String, String>,
    /// Last compaction time
    pub last_compaction: Option<DateTime<Utc>>,
    /// Disk usage
    pub disk_usage: u64,
    /// Memory usage
    pub memory_usage: u64,
}

/// Key-Value store trait
#[async_trait]
pub trait KeyValueStore: Storage + Send + Sync {
    /// Initialize the store
    async fn init(&mut self) -> Result<()>;

    /// Flush pending writes
    async fn flush(&self) -> Result<()>;

    /// Get store-specific statistics
    async fn get_engine_stats(&self) -> Result<HashMap<String, String>>;
}

/// Memory-based storage implementation
pub struct MemoryStore {
    config: StorageConfig,
    data: Arc<DashMap<String, StorageValue>>,
    stats: Arc<RwLock<StorageStats>>,
}

impl MemoryStore {
    pub async fn new(config: StorageConfig) -> Result<Self> {
        info!("💾 Initializing memory storage at: {:?}", config.path);

        Ok(Self {
            config,
            data: Arc::new(DashMap::new()),
            stats: Arc::new(RwLock::new(StorageStats::default())),
        })
    }

    async fn update_read_stats(&self, duration: std::time::Duration, cache_hit: bool) {
        let mut stats = self.stats.write().await;
        stats.read_count += 1;
        stats.avg_read_latency_us =
            (stats.avg_read_latency_us + duration.as_micros() as u64) / 2;

        if cache_hit {
            let total_reads = stats.read_count as f64;
            let hit_count = total_reads * stats.cache_hit_ratio + 1.0;
            stats.cache_hit_ratio = hit_count / total_reads;
        }
    }

    async fn update_write_stats(&self, duration: std::time::Duration, bytes_written: usize) {
        let mut stats = self.stats.write().await;
        stats.write_count += 1;
        stats.total_size += bytes_written as u64;
        stats.avg_write_latency_us =
            (stats.avg_write_latency_us + duration.as_micros() as u64) / 2;
    }

    async fn update_delete_stats(&self, bytes_deleted: usize) {
        let mut stats = self.stats.write().await;
        stats.delete_count += 1;
        stats.total_size = stats.total_size.saturating_sub(bytes_deleted as u64);
    }

    fn matches_query(&self, key: &str, value: &StorageValue, query: &StorageQuery) -> bool {
        // Check prefix
        if let Some(prefix) = &query.prefix {
            if !key.starts_with(prefix) {
                return false;
            }
        }

        // Check pattern (simple glob matching)
        if let Some(pattern) = &query.pattern {
            if !self.matches_pattern(key, pattern) {
                return false;
            }
        }

        // Check tags
        for (tag_key, tag_value) in &query.tags {
            if value.metadata.tags.get(tag_key) != Some(tag_value) {
                return false;
            }
        }

        // Check creation time range
        if let Some(after) = query.created_after {
            if value.metadata.created_at <= after {
                return false;
            }
        }

        if let Some(before) = query.created_before {
            if value.metadata.created_at >= before {
                return false;
            }
        }

        true
    }

    fn matches_pattern(&self, text: &str, pattern: &str) -> bool {
        // Simple glob pattern matching
        if pattern == "*" {
            return true;
        }

        if pattern.contains('*') {
            let parts: Vec<&str> = pattern.split('*').collect();
            if parts.len() == 2 {
                let prefix = parts[0];
                let suffix = parts[1];
                return text.starts_with(prefix) && text.ends_with(suffix) && text.len() >= prefix.len() + suffix.len();
            }
        }

        text == pattern
    }
}

#[async_trait]
impl Storage for MemoryStore {
    async fn get(&self, key: &str) -> Result<Option<StorageValue>> {
        let start = Instant::now();

        let result = if let Some(mut value) = self.data.get_mut(key) {
            // Check expiration
            if value.is_expired() {
                drop(value);
                self.data.remove(key);
                None
            } else {
                value.mark_accessed();
                Some(value.clone())
            }
        } else {
            None
        };

        self.update_read_stats(start.elapsed(), result.is_some()).await;

        debug!("📖 Memory store get: {} -> {}", key, result.is_some());
        Ok(result)
    }

    async fn put(&self, key: &str, value: Vec<u8>) -> Result<()> {
        let start = Instant::now();

        let storage_value = StorageValue::new(value);
        let bytes_written = storage_value.total_size();

        self.data.insert(key.to_string(), storage_value);

        // Update key count
        {
            let mut stats = self.stats.write().await;
            stats.total_keys = self.data.len() as u64;
        }

        self.update_write_stats(start.elapsed(), bytes_written).await;

        debug!("💾 Memory store put: {} ({} bytes)", key, bytes_written);
        Ok(())
    }

    async fn put_with_metadata(&self, key: &str, value: Vec<u8>, metadata: ValueMetadata) -> Result<()> {
        let start = Instant::now();

        let storage_value = StorageValue::with_metadata(value, metadata);
        let bytes_written = storage_value.total_size();

        self.data.insert(key.to_string(), storage_value);

        // Update key count
        {
            let mut stats = self.stats.write().await;
            stats.total_keys = self.data.len() as u64;
        }

        self.update_write_stats(start.elapsed(), bytes_written).await;

        debug!("💾 Memory store put with metadata: {} ({} bytes)", key, bytes_written);
        Ok(())
    }

    async fn delete(&self, key: &str) -> Result<bool> {
        if let Some((_, value)) = self.data.remove(key) {
            let bytes_deleted = value.total_size();

            // Update key count
            {
                let mut stats = self.stats.write().await;
                stats.total_keys = self.data.len() as u64;
            }

            self.update_delete_stats(bytes_deleted).await;

            debug!("🗑️ Memory store delete: {} ({} bytes)", key, bytes_deleted);
            Ok(true)
        } else {
            debug!("🗑️ Memory store delete: {} (not found)", key);
            Ok(false)
        }
    }

    async fn exists(&self, key: &str) -> Result<bool> {
        let exists = if let Some(value) = self.data.get(key) {
            !value.is_expired()
        } else {
            false
        };

        debug!("🔍 Memory store exists: {} -> {}", key, exists);
        Ok(exists)
    }

    async fn list_keys(&self, prefix: Option<&str>) -> Result<Vec<String>> {
        let keys: Vec<String> = self.data
            .iter()
            .filter_map(|entry| {
                let key = entry.key();
                let value = entry.value();

                // Check expiration
                if value.is_expired() {
                    return None;
                }

                // Check prefix
                if let Some(prefix) = prefix {
                    if !key.starts_with(prefix) {
                        return None;
                    }
                }

                Some(key.clone())
            })
            .collect();

        debug!("📋 Memory store list_keys: prefix={:?} -> {} keys", prefix, keys.len());
        Ok(keys)
    }

    async fn query(&self, query: StorageQuery) -> Result<Vec<StorageEntry>> {
        let mut results: Vec<StorageEntry> = self.data
            .iter()
            .filter_map(|entry| {
                let key = entry.key();
                let value = entry.value();

                // Check expiration
                if value.is_expired() {
                    return None;
                }

                // Check query filters
                if !self.matches_query(key, value, &query) {
                    return None;
                }

                Some(StorageEntry {
                    key: key.clone(),
                    value: value.clone(),
                })
            })
            .collect();

        // Apply skip and limit
        if let Some(skip) = query.skip {
            if skip < results.len() {
                results = results.into_iter().skip(skip).collect();
            } else {
                results.clear();
            }
        }

        if let Some(limit) = query.limit {
            results.truncate(limit);
        }

        debug!("🔍 Memory store query: {} results", results.len());
        Ok(results)
    }

    async fn batch_get(&self, keys: &[String]) -> Result<HashMap<String, Option<StorageValue>>> {
        let mut results = HashMap::new();

        for key in keys {
            let value = self.get(key).await?;
            results.insert(key.clone(), value);
        }

        debug!("📖 Memory store batch_get: {} keys", keys.len());
        Ok(results)
    }

    async fn batch_put(&self, entries: HashMap<String, Vec<u8>>) -> Result<()> {
        for (key, value) in entries {
            self.put(&key, value).await?;
        }

        debug!("💾 Memory store batch_put: {} entries", entries.len());
        Ok(())
    }

    async fn batch_delete(&self, keys: &[String]) -> Result<Vec<bool>> {
        let mut results = Vec::new();

        for key in keys {
            let deleted = self.delete(key).await?;
            results.push(deleted);
        }

        debug!("🗑️ Memory store batch_delete: {} keys", keys.len());
        Ok(results)
    }

    async fn get_stats(&self) -> Result<StorageStats> {
        let mut stats = self.stats.read().await.clone();
        stats.total_keys = self.data.len() as u64;
        stats.memory_usage = self.data
            .iter()
            .map(|entry| entry.value().total_size() as u64)
            .sum();

        Ok(stats)
    }

    async fn compact(&self) -> Result<()> {
        // Remove expired entries
        let mut removed_count = 0;
        let keys_to_remove: Vec<String> = self.data
            .iter()
            .filter_map(|entry| {
                if entry.value().is_expired() {
                    Some(entry.key().clone())
                } else {
                    None
                }
            })
            .collect();

        for key in keys_to_remove {
            if self.data.remove(&key).is_some() {
                removed_count += 1;
            }
        }

        // Update stats
        {
            let mut stats = self.stats.write().await;
            stats.last_compaction = Some(Utc::now());
            stats.total_keys = self.data.len() as u64;
        }

        info!("🔧 Memory store compaction: removed {} expired entries", removed_count);
        Ok(())
    }

    async fn backup(&self, path: &str) -> Result<BackupInfo> {
        let backup_path = PathBuf::from(path);
        let backup_id = Uuid::new_v4();
        let created_at = Utc::now();

        // Create backup directory
        tokio::fs::create_dir_all(&backup_path).await?;

        // Serialize all data
        let data: HashMap<String, StorageValue> = self.data
            .iter()
            .map(|entry| (entry.key().clone(), entry.value().clone()))
            .collect();

        let backup_data = serde_json::to_vec_pretty(&data)
            .map_err(|e| StorageError::SerializationError(e.to_string()))?;

        // Write backup file
        let backup_file = backup_path.join("data.json");
        tokio::fs::write(&backup_file, &backup_data).await?;

        let backup_info = BackupInfo {
            id: backup_id,
            path: backup_path,
            created_at,
            size: backup_data.len() as u64,
            key_count: data.len() as u64,
            compression: None,
            encryption: None,
            checksum: blake3::hash(&backup_data).to_hex().to_string(),
        };

        info!("💾 Memory store backup created: {} ({} keys, {} bytes)",
              backup_id, backup_info.key_count, backup_info.size);

        Ok(backup_info)
    }

    async fn restore(&self, backup_path: &str, _options: RestoreOptions) -> Result<()> {
        let backup_file = PathBuf::from(backup_path).join("data.json");

        // Read backup file
        let backup_data = tokio::fs::read(&backup_file).await?;

        // Deserialize data
        let data: HashMap<String, StorageValue> = serde_json::from_slice(&backup_data)
            .map_err(|e| StorageError::SerializationError(e.to_string()))?;

        // Clear current data and restore
        self.data.clear();

        for (key, value) in data {
            self.data.insert(key, value);
        }

        // Update stats
        {
            let mut stats = self.stats.write().await;
            stats.total_keys = self.data.len() as u64;
        }

        info!("🔄 Memory store restored: {} keys", self.data.len());
        Ok(())
    }

    async fn clear(&self) -> Result<()> {
        let count = self.data.len();
        self.data.clear();

        // Reset stats
        {
            let mut stats = self.stats.write().await;
            *stats = StorageStats::default();
        }

        info!("🧹 Memory store cleared: {} keys removed", count);
        Ok(())
    }

    async fn close(&self) -> Result<()> {
        info!("🔒 Memory store closed");
        Ok(())
    }
}

#[async_trait]
impl KeyValueStore for MemoryStore {
    async fn init(&mut self) -> Result<()> {
        info!("🔧 Memory store initialized");
        Ok(())
    }

    async fn flush(&self) -> Result<()> {
        // No-op for memory store
        Ok(())
    }

    async fn get_engine_stats(&self) -> Result<HashMap<String, String>> {
        let mut stats = HashMap::new();
        stats.insert("engine".to_string(), "memory".to_string());
        stats.insert("keys".to_string(), self.data.len().to_string());

        let memory_usage: usize = self.data
            .iter()
            .map(|entry| entry.value().total_size())
            .sum();
        stats.insert("memory_usage".to_string(), memory_usage.to_string());

        Ok(stats)
    }
}

// RocksDB implementation (when feature is enabled)
#[cfg(feature = "rocksdb")]
pub struct RocksDBStore {
    config: StorageConfig,
    db: Arc<rocksdb::DB>,
    stats: Arc<RwLock<StorageStats>>,
}

#[cfg(feature = "rocksdb")]
impl RocksDBStore {
    pub async fn new(config: StorageConfig) -> Result<Self> {
        info!("🗿 Initializing RocksDB storage at: {:?}", config.path);

        // Create directory
        tokio::fs::create_dir_all(&config.path).await?;

        // Configure RocksDB options
        let mut opts = rocksdb::Options::default();
        opts.create_if_missing(true);
        opts.set_write_buffer_size(config.write_buffer_size);
        opts.set_max_open_files(config.max_open_files);
        opts.set_use_fsync(config.wal_sync);

        if config.enable_compaction {
            opts.set_disable_auto_compactions(false);
        }

        // Open database
        let db = rocksdb::DB::open(&opts, &config.path)
            .map_err(|e| StorageError::BackendError(e.to_string()))?;

        Ok(Self {
            config,
            db: Arc::new(db),
            stats: Arc::new(RwLock::new(StorageStats::default())),
        })
    }

    fn serialize_value(&self, value: &StorageValue) -> Result<Vec<u8>> {
        serde_json::to_vec(value)
            .map_err(|e| StorageError::SerializationError(e.to_string()).into())
    }

    fn deserialize_value(&self, data: &[u8]) -> Result<StorageValue> {
        serde_json::from_slice(data)
            .map_err(|e| StorageError::SerializationError(e.to_string()).into())
    }
}

#[cfg(feature = "rocksdb")]
#[async_trait]
impl Storage for RocksDBStore {
    async fn get(&self, key: &str) -> Result<Option<StorageValue>> {
        let start = Instant::now();

        let result = match self.db.get(key.as_bytes()) {
            Ok(Some(data)) => {
                let value = self.deserialize_value(&data)?;
                if value.is_expired() {
                    // Delete expired key
                    let _ = self.db.delete(key.as_bytes());
                    None
                } else {
                    Some(value)
                }
            }
            Ok(None) => None,
            Err(e) => return Err(StorageError::BackendError(e.to_string()).into()),
        };

        // Update stats
        {
            let mut stats = self.stats.write().await;
            stats.read_count += 1;
            stats.avg_read_latency_us =
                (stats.avg_read_latency_us + start.elapsed().as_micros() as u64) / 2;
        }

        debug!("📖 RocksDB get: {} -> {}", key, result.is_some());
        Ok(result)
    }

    async fn put(&self, key: &str, value: Vec<u8>) -> Result<()> {
        let start = Instant::now();

        let storage_value = StorageValue::new(value);
        let serialized = self.serialize_value(&storage_value)?;

        self.db.put(key.as_bytes(), &serialized)
            .map_err(|e| StorageError::BackendError(e.to_string()))?;

        // Update stats
        {
            let mut stats = self.stats.write().await;
            stats.write_count += 1;
            stats.total_size += serialized.len() as u64;
            stats.avg_write_latency_us =
                (stats.avg_write_latency_us + start.elapsed().as_micros() as u64) / 2;
        }

        debug!("💾 RocksDB put: {} ({} bytes)", key, serialized.len());
        Ok(())
    }

    async fn put_with_metadata(&self, key: &str, value: Vec<u8>, metadata: ValueMetadata) -> Result<()> {
        let start = Instant::now();

        let storage_value = StorageValue::with_metadata(value, metadata);
        let serialized = self.serialize_value(&storage_value)?;

        self.db.put(key.as_bytes(), &serialized)
            .map_err(|e| StorageError::BackendError(e.to_string()))?;

        // Update stats
        {
            let mut stats = self.stats.write().await;
            stats.write_count += 1;
            stats.total_size += serialized.len() as u64;
            stats.avg_write_latency_us =
                (stats.avg_write_latency_us + start.elapsed().as_micros() as u64) / 2;
        }

        debug!("💾 RocksDB put with metadata: {} ({} bytes)", key, serialized.len());
        Ok(())
    }

    async fn delete(&self, key: &str) -> Result<bool> {
        // Check if key exists first
        let exists = self.db.get(key.as_bytes())
            .map_err(|e| StorageError::BackendError(e.to_string()))?
            .is_some();

        if exists {
            self.db.delete(key.as_bytes())
                .map_err(|e| StorageError::BackendError(e.to_string()))?;

            // Update stats
            {
                let mut stats = self.stats.write().await;
                stats.delete_count += 1;
            }

            debug!("🗑️ RocksDB delete: {}", key);
            Ok(true)
        } else {
            debug!("🗑️ RocksDB delete: {} (not found)", key);
            Ok(false)
        }
    }

    async fn exists(&self, key: &str) -> Result<bool> {
        match self.db.get(key.as_bytes()) {
            Ok(Some(data)) => {
                let value = self.deserialize_value(&data)?;
                Ok(!value.is_expired())
            }
            Ok(None) => Ok(false),
            Err(e) => Err(StorageError::BackendError(e.to_string()).into()),
        }
    }

    async fn list_keys(&self, prefix: Option<&str>) -> Result<Vec<String>> {
        let mut keys = Vec::new();
        let iter = self.db.iterator(rocksdb::IteratorMode::Start);

        for item in iter {
            let (key_bytes, value_bytes) = item
                .map_err(|e| StorageError::BackendError(e.to_string()))?;

            let key = String::from_utf8_lossy(&key_bytes).to_string();

            // Check prefix
            if let Some(prefix) = prefix {
                if !key.starts_with(prefix) {
                    continue;
                }
            }

            // Check expiration
            if let Ok(value) = self.deserialize_value(&value_bytes) {
                if !value.is_expired() {
                    keys.push(key);
                }
            }
        }

        debug!("📋 RocksDB list_keys: prefix={:?} -> {} keys", prefix, keys.len());
        Ok(keys)
    }

    async fn query(&self, query: StorageQuery) -> Result<Vec<StorageEntry>> {
        // For now, implement query by listing all keys and filtering
        // In a production system, you'd want more efficient indexing
        let all_keys = self.list_keys(query.prefix.as_deref()).await?;
        let mut results = Vec::new();

        for key in all_keys {
            if let Some(value) = self.get(&key).await? {
                // Apply additional filters
                let matches = query.tags.iter().all(|(tag_key, tag_value)| {
                    value.metadata.tags.get(tag_key) == Some(tag_value)
                }) && query.created_after.map_or(true, |after| value.metadata.created_at > after)
                   && query.created_before.map_or(true, |before| value.metadata.created_at < before);

                if matches {
                    results.push(StorageEntry { key, value });
                }
            }
        }

        // Apply skip and limit
        if let Some(skip) = query.skip {
            if skip < results.len() {
                results = results.into_iter().skip(skip).collect();
            } else {
                results.clear();
            }
        }

        if let Some(limit) = query.limit {
            results.truncate(limit);
        }

        debug!("🔍 RocksDB query: {} results", results.len());
        Ok(results)
    }

    async fn batch_get(&self, keys: &[String]) -> Result<HashMap<String, Option<StorageValue>>> {
        let mut results = HashMap::new();

        for key in keys {
            let value = self.get(key).await?;
            results.insert(key.clone(), value);
        }

        debug!("📖 RocksDB batch_get: {} keys", keys.len());
        Ok(results)
    }

    async fn batch_put(&self, entries: HashMap<String, Vec<u8>>) -> Result<()> {
        let mut batch = rocksdb::WriteBatch::default();

        for (key, value) in entries.iter() {
            let storage_value = StorageValue::new(value.clone());
            let serialized = self.serialize_value(&storage_value)?;
            batch.put(key.as_bytes(), &serialized);
        }

        self.db.write(batch)
            .map_err(|e| StorageError::BackendError(e.to_string()))?;

        debug!("💾 RocksDB batch_put: {} entries", entries.len());
        Ok(())
    }

    async fn batch_delete(&self, keys: &[String]) -> Result<Vec<bool>> {
        let mut batch = rocksdb::WriteBatch::default();
        let mut results = Vec::new();

        for key in keys {
            let exists = self.exists(key).await?;
            if exists {
                batch.delete(key.as_bytes());
            }
            results.push(exists);
        }

        if !batch.is_empty() {
            self.db.write(batch)
                .map_err(|e| StorageError::BackendError(e.to_string()))?;
        }

        debug!("🗑️ RocksDB batch_delete: {} keys", keys.len());
        Ok(results)
    }

    async fn get_stats(&self) -> Result<StorageStats> {
        let stats = self.stats.read().await.clone();
        // TODO: Get actual RocksDB statistics
        Ok(stats)
    }

    async fn compact(&self) -> Result<()> {
        self.db.compact_range(None::<&[u8]>, None::<&[u8]>);

        let mut stats = self.stats.write().await;
        stats.last_compaction = Some(Utc::now());

        info!("🔧 RocksDB compaction completed");
        Ok(())
    }

    async fn backup(&self, _path: &str) -> Result<BackupInfo> {
        // TODO: Implement RocksDB backup
        Err(StorageError::BackupError("RocksDB backup not implemented".to_string()).into())
    }

    async fn restore(&self, _backup_path: &str, _options: RestoreOptions) -> Result<()> {
        // TODO: Implement RocksDB restore
        Err(StorageError::BackupError("RocksDB restore not implemented".to_string()).into())
    }

    async fn clear(&self) -> Result<()> {
        // Delete all keys
        let keys = self.list_keys(None).await?;
        let mut batch = rocksdb::WriteBatch::default();

        for key in keys {
            batch.delete(key.as_bytes());
        }

        self.db.write(batch)
            .map_err(|e| StorageError::BackendError(e.to_string()))?;

        // Reset stats
        {
            let mut stats = self.stats.write().await;
            *stats = StorageStats::default();
        }

        info!("🧹 RocksDB cleared");
        Ok(())
    }

    async fn close(&self) -> Result<()> {
        info!("🔒 RocksDB closed");
        Ok(())
    }
}

#[cfg(feature = "rocksdb")]
#[async_trait]
impl KeyValueStore for RocksDBStore {
    async fn init(&mut self) -> Result<()> {
        info!("🔧 RocksDB initialized");
        Ok(())
    }

    async fn flush(&self) -> Result<()> {
        self.db.flush()
            .map_err(|e| StorageError::BackendError(e.to_string()))?;
        Ok(())
    }

    async fn get_engine_stats(&self) -> Result<HashMap<String, String>> {
        let mut stats = HashMap::new();
        stats.insert("engine".to_string(), "rocksdb".to_string());

        // Get RocksDB properties
        if let Ok(Some(value)) = self.db.property_value("rocksdb.stats") {
            stats.insert("rocksdb_stats".to_string(), value);
        }

        Ok(stats)
    }
}

// Sled implementation (when feature is enabled)
#[cfg(feature = "sled")]
pub struct SledStore {
    config: StorageConfig,
    db: Arc<sled::Db>,
    stats: Arc<RwLock<StorageStats>>,
}

#[cfg(feature = "sled")]
impl SledStore {
    pub async fn new(config: StorageConfig) -> Result<Self> {
        info!("🌲 Initializing Sled storage at: {:?}", config.path);

        let db = sled::open(&config.path)
            .map_err(|e| StorageError::BackendError(e.to_string()))?;

        Ok(Self {
            config,
            db: Arc::new(db),
            stats: Arc::new(RwLock::new(StorageStats::default())),
        })
    }

    fn serialize_value(&self, value: &StorageValue) -> Result<Vec<u8>> {
        serde_json::to_vec(value)
            .map_err(|e| StorageError::SerializationError(e.to_string()).into())
    }

    fn deserialize_value(&self, data: &[u8]) -> Result<StorageValue> {
        serde_json::from_slice(data)
            .map_err(|e| StorageError::SerializationError(e.to_string()).into())
    }
}

// TODO: Implement Sled Storage trait methods similar to RocksDB

impl Default for StorageConfig {
    fn default() -> Self {
        Self {
            backend: StorageBackend::Memory,
            path: PathBuf::from("./storage"),
            enable_compression: false,
            enable_encryption: false,
            cache_size: 64 * 1024 * 1024, // 64MB
            write_buffer_size: 16 * 1024 * 1024, // 16MB
            max_open_files: 1000,
            enable_wal: true,
            wal_sync: false,
            enable_compaction: true,
            enable_stats: true,
            ttl_cleanup_interval: 3600, // 1 hour
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_memory_store_basic_operations() {
        let config = StorageConfig::default();
        let store = MemoryStore::new(config).await.unwrap();

        // Test put and get
        let key = "test_key";
        let value = b"test_value".to_vec();

        store.put(key, value.clone()).await.unwrap();

        let retrieved = store.get(key).await.unwrap();
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap().data, value);

        // Test delete
        let deleted = store.delete(key).await.unwrap();
        assert!(deleted);

        let after_delete = store.get(key).await.unwrap();
        assert!(after_delete.is_none());
    }

    #[tokio::test]
    async fn test_memory_store_expiration() {
        let config = StorageConfig::default();
        let store = MemoryStore::new(config).await.unwrap();

        let key = "expiring_key";
        let value = b"expiring_value".to_vec();

        let mut metadata = ValueMetadata::default();
        metadata.expires_at = Some(Utc::now() - chrono::Duration::seconds(1)); // Already expired

        store.put_with_metadata(key, value, metadata).await.unwrap();

        // Should return None for expired value
        let retrieved = store.get(key).await.unwrap();
        assert!(retrieved.is_none());
    }

    #[tokio::test]
    async fn test_memory_store_query() {
        let config = StorageConfig::default();
        let store = MemoryStore::new(config).await.unwrap();

        // Put test data
        for i in 0..5 {
            let key = format!("test_{}", i);
            let value = format!("value_{}", i).into_bytes();
            let mut metadata = ValueMetadata::default();
            metadata.tags.insert("category".to_string(), "test".to_string());

            store.put_with_metadata(&key, value, metadata).await.unwrap();
        }

        // Query with prefix
        let query = StorageQuery {
            prefix: Some("test_".to_string()),
            ..Default::default()
        };

        let results = store.query(query).await.unwrap();
        assert_eq!(results.len(), 5);

        // Query with tag filter
        let query = StorageQuery {
            tags: {
                let mut tags = HashMap::new();
                tags.insert("category".to_string(), "test".to_string());
                tags
            },
            limit: Some(3),
            ..Default::default()
        };

        let results = store.query(query).await.unwrap();
        assert_eq!(results.len(), 3);
    }
}