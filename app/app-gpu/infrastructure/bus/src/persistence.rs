use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tokio::fs::{File, OpenOptions};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader, BufWriter};
use tokio::sync::{mpsc, RwLock};
use tracing::{debug, error, info, warn};
use uuid::Uuid;

use crate::Message;

/// Configuration for message persistence
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PersistenceConfig {
    /// Directory for storing message logs
    pub log_directory: PathBuf,
    /// Maximum size of a single log file (bytes)
    pub max_file_size: u64,
    /// Maximum number of log files to keep
    pub max_files: u32,
    /// Batch size for writing messages
    pub batch_size: usize,
    /// Flush interval in milliseconds
    pub flush_interval_ms: u64,
    /// Enable compression for log files
    pub enable_compression: bool,
    /// Index file for fast message lookup
    pub index_file: String,
}

/// Message log entry for persistence
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageLogEntry {
    /// Message
    pub message: Message,
    /// Log sequence number
    pub sequence: u64,
    /// File offset for the message
    pub offset: u64,
    /// Size of the serialized message
    pub size: u32,
    /// CRC32 checksum for data integrity
    pub checksum: u32,
}

/// Message index entry for fast lookups
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageIndex {
    /// Message ID
    pub message_id: Uuid,
    /// Topic
    pub topic: String,
    /// Timestamp
    pub timestamp: DateTime<Utc>,
    /// File number
    pub file_number: u32,
    /// Offset in file
    pub offset: u64,
    /// Message size
    pub size: u32,
}

/// Persistence statistics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PersistenceStats {
    /// Total messages persisted
    pub messages_persisted: u64,
    /// Total bytes written
    pub bytes_written: u64,
    /// Current file number
    pub current_file: u32,
    /// Messages in current batch
    pub batch_size: usize,
    /// Last flush time
    pub last_flush: Option<DateTime<Utc>>,
    /// Total files created
    pub total_files: u32,
}

/// Message persistence layer for reliable storage and replay
pub struct MessagePersistence {
    config: PersistenceConfig,
    current_file: Arc<RwLock<Option<BufWriter<File>>>>,
    current_file_number: Arc<RwLock<u32>>,
    current_sequence: Arc<RwLock<u64>>,
    message_index: Arc<RwLock<Vec<MessageIndex>>>,
    stats: Arc<RwLock<PersistenceStats>>,
    write_buffer: Arc<RwLock<VecDeque<MessageLogEntry>>>,
}

impl MessagePersistence {
    /// Create a new message persistence layer
    pub async fn new(config: PersistenceConfig) -> Result<Self> {
        info!(
            "💾 Initializing message persistence at: {}",
            config.log_directory.display()
        );

        // Create log directory if it doesn't exist
        tokio::fs::create_dir_all(&config.log_directory)
            .await
            .context("Failed to create log directory")?;

        let current_file_number = Self::get_latest_file_number(&config.log_directory).await?;

        let persistence = Self {
            config,
            current_file: Arc::new(RwLock::new(None)),
            current_file_number: Arc::new(RwLock::new(current_file_number)),
            current_sequence: Arc::new(RwLock::new(0)),
            message_index: Arc::new(RwLock::new(Vec::new())),
            stats: Arc::new(RwLock::new(PersistenceStats::default())),
            write_buffer: Arc::new(RwLock::new(VecDeque::new())),
        };

        // Load existing index
        persistence.load_index().await?;

        // Initialize current file
        persistence.ensure_current_file().await?;

        info!("✅ Message persistence initialized");
        Ok(persistence)
    }

    /// Start the persistence worker
    pub async fn start_worker(&self, mut rx: mpsc::Receiver<Message>) -> Result<()> {
        let persistence = self.clone();

        tokio::spawn(async move {
            persistence.persistence_worker(rx).await;
        });

        // Start flush worker
        let persistence_for_flush = self.clone();
        tokio::spawn(async move {
            persistence_for_flush.flush_worker().await;
        });

        info!("🔄 Started persistence workers");
        Ok(())
    }

    /// Background worker for persisting messages
    async fn persistence_worker(&self, mut rx: mpsc::Receiver<Message>) {
        while let Some(message) = rx.recv().await {
            if let Err(e) = self.persist_message(message).await {
                error!("❌ Error persisting message: {}", e);
            }
        }
        info!("🛑 Persistence worker stopped");
    }

    /// Background worker for periodic flushing
    async fn flush_worker(&self) {
        let mut interval = tokio::time::interval(tokio::time::Duration::from_millis(
            self.config.flush_interval_ms,
        ));

        loop {
            interval.tick().await;
            if let Err(e) = self.flush_batch().await {
                error!("❌ Error flushing batch: {}", e);
            }
        }
    }

    /// Persist a single message
    pub async fn persist_message(&self, message: Message) -> Result<()> {
        let sequence = {
            let mut seq = self.current_sequence.write().await;
            *seq += 1;
            *seq
        };

        let serialized = serde_json::to_vec(&message)
            .context("Failed to serialize message")?;

        let checksum = crc32fast::hash(&serialized);

        let log_entry = MessageLogEntry {
            message: message.clone(),
            sequence,
            offset: 0, // Will be set when writing
            size: serialized.len() as u32,
            checksum,
        };

        // Add to write buffer
        {
            let mut buffer = self.write_buffer.write().await;
            buffer.push_back(log_entry);

            // Update stats
            let mut stats = self.stats.write().await;
            stats.batch_size = buffer.len();
        }

        // Check if we need to flush
        let should_flush = {
            let buffer = self.write_buffer.read().await;
            buffer.len() >= self.config.batch_size
        };

        if should_flush {
            self.flush_batch().await?;
        }

        Ok(())
    }

    /// Flush the current batch to disk
    pub async fn flush_batch(&self) -> Result<()> {
        let entries_to_write = {
            let mut buffer = self.write_buffer.write().await;
            if buffer.is_empty() {
                return Ok(());
            }
            buffer.drain(..).collect::<Vec<_>>()
        };

        if entries_to_write.is_empty() {
            return Ok(());
        }

        debug!("💾 Flushing {} messages to disk", entries_to_write.len());

        self.ensure_current_file().await?;

        let mut total_bytes = 0u64;
        let mut new_indices = Vec::new();

        {
            let mut file_guard = self.current_file.write().await;
            let file_number = *self.current_file_number.read().await;

            if let Some(ref mut file) = *file_guard {
                for mut entry in entries_to_write {
                    let serialized = serde_json::to_vec(&entry)
                        .context("Failed to serialize log entry")?;

                    // Record the offset before writing
                    let current_offset = file.stream_position().await
                        .context("Failed to get file position")?;
                    entry.offset = current_offset;

                    // Write the entry
                    file.write_all(&serialized).await
                        .context("Failed to write message to file")?;
                    file.write_all(b"\n").await
                        .context("Failed to write newline")?;

                    total_bytes += serialized.len() as u64 + 1; // +1 for newline

                    // Add to index
                    let index_entry = MessageIndex {
                        message_id: entry.message.id,
                        topic: entry.message.topic.clone(),
                        timestamp: entry.message.timestamp,
                        file_number,
                        offset: current_offset,
                        size: entry.size,
                    };
                    new_indices.push(index_entry);
                }

                file.flush().await.context("Failed to flush file")?;
            }
        }

        // Update index
        {
            let mut index = self.message_index.write().await;
            index.extend(new_indices);
        }

        // Update statistics
        {
            let mut stats = self.stats.write().await;
            stats.messages_persisted += entries_to_write.len() as u64;
            stats.bytes_written += total_bytes;
            stats.last_flush = Some(Utc::now());
            stats.batch_size = 0;
        }

        // Check if we need to rotate files
        self.check_file_rotation().await?;

        debug!("✅ Flushed {} messages ({} bytes)", entries_to_write.len(), total_bytes);
        Ok(())
    }

    /// Ensure current file is open and ready
    async fn ensure_current_file(&self) -> Result<()> {
        let mut file_guard = self.current_file.write().await;

        if file_guard.is_none() {
            let file_number = *self.current_file_number.read().await;
            let file_path = self.get_log_file_path(file_number);

            let file = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&file_path)
                .await
                .context("Failed to open log file")?;

            *file_guard = Some(BufWriter::new(file));

            debug!("📁 Opened log file: {}", file_path.display());
        }

        Ok(())
    }

    /// Check if file rotation is needed
    async fn check_file_rotation(&self) -> Result<()> {
        let file_number = *self.current_file_number.read().await;
        let file_path = self.get_log_file_path(file_number);

        if let Ok(metadata) = tokio::fs::metadata(&file_path).await {
            if metadata.len() >= self.config.max_file_size {
                debug!("🔄 Rotating log file (size: {} bytes)", metadata.len());

                // Close current file
                {
                    let mut file_guard = self.current_file.write().await;
                    if let Some(mut file) = file_guard.take() {
                        file.flush().await.context("Failed to flush before rotation")?;
                    }
                }

                // Increment file number
                {
                    let mut file_num = self.current_file_number.write().await;
                    *file_num += 1;
                }

                // Update stats
                {
                    let mut stats = self.stats.write().await;
                    stats.current_file = *self.current_file_number.read().await;
                    stats.total_files += 1;
                }

                // Clean up old files if necessary
                self.cleanup_old_files().await?;

                info!("✅ Log file rotated to: {}", self.get_log_file_path(*self.current_file_number.read().await).display());
            }
        }

        Ok(())
    }

    /// Clean up old log files
    async fn cleanup_old_files(&self) -> Result<()> {
        let current_file = *self.current_file_number.read().await;

        if current_file > self.config.max_files {
            let old_file_number = current_file - self.config.max_files;
            let old_file_path = self.get_log_file_path(old_file_number);

            if old_file_path.exists() {
                tokio::fs::remove_file(&old_file_path)
                    .await
                    .context("Failed to remove old log file")?;

                debug!("🗑️ Removed old log file: {}", old_file_path.display());
            }
        }

        Ok(())
    }

    /// Get the path for a log file
    fn get_log_file_path(&self, file_number: u32) -> PathBuf {
        self.config
            .log_directory
            .join(format!("messages_{:06}.log", file_number))
    }

    /// Get the latest file number from the log directory
    async fn get_latest_file_number(log_dir: &Path) -> Result<u32> {
        let mut max_number = 0u32;

        if log_dir.exists() {
            let mut entries = tokio::fs::read_dir(log_dir).await
                .context("Failed to read log directory")?;

            while let Some(entry) = entries.next_entry().await? {
                if let Some(file_name) = entry.file_name().to_str() {
                    if file_name.starts_with("messages_") && file_name.ends_with(".log") {
                        if let Some(number_str) = file_name
                            .strip_prefix("messages_")
                            .and_then(|s| s.strip_suffix(".log"))
                        {
                            if let Ok(number) = number_str.parse::<u32>() {
                                max_number = max_number.max(number);
                            }
                        }
                    }
                }
            }
        }

        Ok(max_number)
    }

    /// Load the message index from disk
    async fn load_index(&self) -> Result<()> {
        let index_path = self.config.log_directory.join(&self.config.index_file);

        if index_path.exists() {
            let index_data = tokio::fs::read_to_string(&index_path)
                .await
                .context("Failed to read index file")?;

            let index: Vec<MessageIndex> = serde_json::from_str(&index_data)
                .context("Failed to parse index file")?;

            let mut index_guard = self.message_index.write().await;
            *index_guard = index;

            info!("📋 Loaded {} index entries", index_guard.len());
        }

        Ok(())
    }

    /// Save the message index to disk
    pub async fn save_index(&self) -> Result<()> {
        let index_path = self.config.log_directory.join(&self.config.index_file);
        let index = self.message_index.read().await.clone();

        let index_data = serde_json::to_string_pretty(&index)
            .context("Failed to serialize index")?;

        tokio::fs::write(&index_path, index_data)
            .await
            .context("Failed to write index file")?;

        debug!("💾 Saved {} index entries", index.len());
        Ok(())
    }

    /// Replay messages from a specific timestamp
    pub async fn replay_from_timestamp(&self, since: DateTime<Utc>) -> Result<Vec<Message>> {
        let index = self.message_index.read().await;
        let matching_entries: Vec<_> = index
            .iter()
            .filter(|entry| entry.timestamp >= since)
            .collect();

        let mut messages = Vec::new();

        for entry in matching_entries {
            if let Ok(message) = self.load_message_by_index(entry).await {
                messages.push(message);
            }
        }

        info!("🔄 Replayed {} messages from {}", messages.len(), since);
        Ok(messages)
    }

    /// Replay messages for a specific topic
    pub async fn replay_for_topic(&self, topic: &str) -> Result<Vec<Message>> {
        let index = self.message_index.read().await;
        let matching_entries: Vec<_> = index
            .iter()
            .filter(|entry| entry.topic == topic)
            .collect();

        let mut messages = Vec::new();

        for entry in matching_entries {
            if let Ok(message) = self.load_message_by_index(entry).await {
                messages.push(message);
            }
        }

        info!("🔄 Replayed {} messages for topic: {}", messages.len(), topic);
        Ok(messages)
    }

    /// Load a specific message by its index entry
    async fn load_message_by_index(&self, index_entry: &MessageIndex) -> Result<Message> {
        let file_path = self.get_log_file_path(index_entry.file_number);

        let file = File::open(&file_path)
            .await
            .context("Failed to open log file for reading")?;

        let mut reader = BufReader::new(file);

        // Seek to the message offset
        use tokio::io::AsyncSeekExt;
        reader.seek(std::io::SeekFrom::Start(index_entry.offset)).await
            .context("Failed to seek to message offset")?;

        let mut line = String::new();
        reader.read_line(&mut line).await
            .context("Failed to read message line")?;

        let log_entry: MessageLogEntry = serde_json::from_str(&line)
            .context("Failed to parse message log entry")?;

        Ok(log_entry.message)
    }

    /// Get persistence statistics
    pub async fn get_stats(&self) -> Result<PersistenceStats> {
        let mut stats = self.stats.read().await.clone();
        stats.current_file = *self.current_file_number.read().await;
        stats.batch_size = self.write_buffer.read().await.len();
        Ok(stats)
    }

    /// Shutdown persistence
    pub async fn shutdown(&self) -> Result<()> {
        info!("🛑 Shutting down message persistence");

        // Flush any remaining messages
        self.flush_batch().await?;

        // Close current file
        {
            let mut file_guard = self.current_file.write().await;
            if let Some(mut file) = file_guard.take() {
                file.flush().await.context("Failed to flush during shutdown")?;
            }
        }

        // Save index
        self.save_index().await?;

        info!("✅ Message persistence shutdown complete");
        Ok(())
    }
}

impl Clone for MessagePersistence {
    fn clone(&self) -> Self {
        Self {
            config: self.config.clone(),
            current_file: Arc::clone(&self.current_file),
            current_file_number: Arc::clone(&self.current_file_number),
            current_sequence: Arc::clone(&self.current_sequence),
            message_index: Arc::clone(&self.message_index),
            stats: Arc::clone(&self.stats),
            write_buffer: Arc::clone(&self.write_buffer),
        }
    }
}

impl Default for PersistenceConfig {
    fn default() -> Self {
        Self {
            log_directory: PathBuf::from("./logs/messages"),
            max_file_size: 100 * 1024 * 1024, // 100MB
            max_files: 10,
            batch_size: 100,
            flush_interval_ms: 1000,
            enable_compression: false,
            index_file: "message_index.json".to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_message_persistence() {
        let temp_dir = TempDir::new().unwrap();
        let config = PersistenceConfig {
            log_directory: temp_dir.path().to_path_buf(),
            batch_size: 2,
            ..Default::default()
        };

        let persistence = MessagePersistence::new(config).await.unwrap();

        let message1 = Message::new(
            "test.topic".to_string(),
            json!({"test": "data1"}),
            None,
        );

        let message2 = Message::new(
            "test.topic".to_string(),
            json!({"test": "data2"}),
            None,
        );

        // Persist messages
        persistence.persist_message(message1.clone()).await.unwrap();
        persistence.persist_message(message2.clone()).await.unwrap();

        // Wait for batch to flush
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

        let stats = persistence.get_stats().await.unwrap();
        assert_eq!(stats.messages_persisted, 2);

        // Test replay
        let replayed = persistence.replay_for_topic("test.topic").await.unwrap();
        assert_eq!(replayed.len(), 2);
    }
}