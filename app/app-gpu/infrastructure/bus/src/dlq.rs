use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};
use uuid::Uuid;

use crate::Message;

/// Configuration for Dead Letter Queue
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DlqConfig {
    /// Maximum number of messages in DLQ
    pub max_messages: usize,
    /// Maximum retry attempts before sending to DLQ
    pub max_retries: u32,
    /// Retry delay multiplier for exponential backoff
    pub retry_delay_multiplier: f64,
    /// Initial retry delay in milliseconds
    pub initial_retry_delay_ms: u64,
    /// Maximum retry delay in milliseconds
    pub max_retry_delay_ms: u64,
    /// Enable automatic retry
    pub enable_auto_retry: bool,
}

/// Failed message entry for Dead Letter Queue
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FailedMessage {
    /// Original message
    pub message: Message,
    /// Number of retry attempts
    pub retry_count: u32,
    /// Error that caused the failure
    pub error: String,
    /// When the message first failed
    pub first_failed_at: DateTime<Utc>,
    /// When the message was last retried
    pub last_retry_at: Option<DateTime<Utc>>,
    /// Next retry time
    pub next_retry_at: Option<DateTime<Utc>>,
    /// DLQ entry ID
    pub dlq_id: Uuid,
}

/// Dead Letter Queue statistics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DlqStats {
    /// Total failed messages
    pub total_failed: u64,
    /// Messages currently in DLQ
    pub messages_in_dlq: usize,
    /// Total retry attempts
    pub total_retries: u64,
    /// Messages successfully recovered
    pub recovered_messages: u64,
    /// Messages permanently failed
    pub permanently_failed: u64,
}

/// Dead Letter Queue implementation for handling failed messages
pub struct DeadLetterQueue {
    config: DlqConfig,
    failed_messages: Arc<RwLock<VecDeque<FailedMessage>>>,
    stats: Arc<RwLock<DlqStats>>,
}

impl DeadLetterQueue {
    /// Create a new Dead Letter Queue
    pub fn new(config: DlqConfig) -> Self {
        info!(
            "📪 Initializing Dead Letter Queue with max messages: {}, max retries: {}",
            config.max_messages, config.max_retries
        );

        Self {
            config,
            failed_messages: Arc::new(RwLock::new(VecDeque::new())),
            stats: Arc::new(RwLock::new(DlqStats::default())),
        }
    }

    /// Add a failed message to the DLQ
    pub async fn add_failed_message(&self, message: Message, error: String) -> Result<()> {
        let dlq_id = Uuid::new_v4();
        let now = Utc::now();

        let failed_message = FailedMessage {
            message,
            retry_count: 0,
            error,
            first_failed_at: now,
            last_retry_at: None,
            next_retry_at: if self.config.enable_auto_retry {
                Some(now + chrono::Duration::milliseconds(self.config.initial_retry_delay_ms as i64))
            } else {
                None
            },
            dlq_id,
        };

        let mut queue = self.failed_messages.write().await;

        // Check if we're at capacity
        if queue.len() >= self.config.max_messages {
            // Remove oldest message
            if let Some(removed) = queue.pop_front() {
                warn!(
                    "🗑️ DLQ at capacity, removing oldest message: {}",
                    removed.dlq_id
                );
            }
        }

        queue.push_back(failed_message.clone());

        // Update statistics
        {
            let mut stats = self.stats.write().await;
            stats.total_failed += 1;
            stats.messages_in_dlq = queue.len();
        }

        error!(
            "☠️ Message {} added to DLQ with ID: {}, error: {}",
            failed_message.message.id, dlq_id, failed_message.error
        );

        Ok(())
    }

    /// Get messages ready for retry
    pub async fn get_retry_candidates(&self) -> Result<Vec<FailedMessage>> {
        let now = Utc::now();
        let queue = self.failed_messages.read().await;

        let candidates: Vec<FailedMessage> = queue
            .iter()
            .filter(|msg| {
                msg.retry_count < self.config.max_retries
                    && msg.next_retry_at
                        .map(|retry_time| retry_time <= now)
                        .unwrap_or(false)
            })
            .cloned()
            .collect();

        debug!("🔄 Found {} retry candidates", candidates.len());
        Ok(candidates)
    }

    /// Mark a message retry attempt
    pub async fn mark_retry_attempt(&self, dlq_id: Uuid, success: bool) -> Result<()> {
        let mut queue = self.failed_messages.write().await;
        let now = Utc::now();

        if let Some(pos) = queue.iter().position(|msg| msg.dlq_id == dlq_id) {
            let mut failed_message = queue[pos].clone();

            if success {
                // Remove from DLQ on successful retry
                queue.remove(pos);

                let mut stats = self.stats.write().await;
                stats.recovered_messages += 1;
                stats.messages_in_dlq = queue.len();

                info!(
                    "✅ Message {} successfully recovered from DLQ",
                    failed_message.message.id
                );
            } else {
                // Update retry information
                failed_message.retry_count += 1;
                failed_message.last_retry_at = Some(now);

                if failed_message.retry_count >= self.config.max_retries {
                    // Mark as permanently failed
                    failed_message.next_retry_at = None;

                    let mut stats = self.stats.write().await;
                    stats.permanently_failed += 1;

                    error!(
                        "💀 Message {} permanently failed after {} retries",
                        failed_message.message.id, failed_message.retry_count
                    );
                } else {
                    // Calculate next retry time with exponential backoff
                    let delay_ms = (self.config.initial_retry_delay_ms as f64
                        * self.config.retry_delay_multiplier.powi(failed_message.retry_count as i32))
                        .min(self.config.max_retry_delay_ms as f64) as u64;

                    failed_message.next_retry_at = Some(now + chrono::Duration::milliseconds(delay_ms as i64));

                    debug!(
                        "⏰ Scheduled retry for message {} in {}ms (attempt {})",
                        failed_message.message.id, delay_ms, failed_message.retry_count + 1
                    );
                }

                queue[pos] = failed_message;

                let mut stats = self.stats.write().await;
                stats.total_retries += 1;
            }
        } else {
            warn!("⚠️ Failed message with DLQ ID {} not found", dlq_id);
        }

        Ok(())
    }

    /// Get all failed messages (for inspection)
    pub async fn get_all_failed_messages(&self) -> Result<Vec<FailedMessage>> {
        let queue = self.failed_messages.read().await;
        Ok(queue.iter().cloned().collect())
    }

    /// Remove a specific message from DLQ
    pub async fn remove_message(&self, dlq_id: Uuid) -> Result<bool> {
        let mut queue = self.failed_messages.write().await;

        if let Some(pos) = queue.iter().position(|msg| msg.dlq_id == dlq_id) {
            let removed = queue.remove(pos).unwrap();

            let mut stats = self.stats.write().await;
            stats.messages_in_dlq = queue.len();

            info!(
                "🗑️ Manually removed message {} from DLQ",
                removed.message.id
            );
            Ok(true)
        } else {
            warn!("⚠️ Message with DLQ ID {} not found for removal", dlq_id);
            Ok(false)
        }
    }

    /// Clear all messages from DLQ
    pub async fn clear(&self) -> Result<usize> {
        let mut queue = self.failed_messages.write().await;
        let count = queue.len();
        queue.clear();

        let mut stats = self.stats.write().await;
        stats.messages_in_dlq = 0;

        info!("🧹 Cleared {} messages from DLQ", count);
        Ok(count)
    }

    /// Get DLQ statistics
    pub async fn get_stats(&self) -> Result<DlqStats> {
        let queue = self.failed_messages.read().await;
        let mut stats = self.stats.read().await.clone();
        stats.messages_in_dlq = queue.len();
        Ok(stats)
    }

    /// Start automatic retry worker
    pub async fn start_retry_worker(&self) -> Result<()> {
        if !self.config.enable_auto_retry {
            debug!("🚫 Auto-retry disabled, not starting retry worker");
            return Ok(());
        }

        let dlq = self.clone();
        tokio::spawn(async move {
            dlq.retry_worker().await;
        });

        info!("🔄 Started DLQ retry worker");
        Ok(())
    }

    /// Background worker for automatic retries
    async fn retry_worker(&self) {
        let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(1));

        loop {
            interval.tick().await;

            if let Ok(candidates) = self.get_retry_candidates().await {
                for candidate in candidates {
                    debug!(
                        "🔄 Auto-retrying message {} (attempt {})",
                        candidate.message.id,
                        candidate.retry_count + 1
                    );

                    // In a real implementation, this would republish the message
                    // For now, we just mark it as failed to simulate retry failure
                    if let Err(e) = self.mark_retry_attempt(candidate.dlq_id, false).await {
                        error!("❌ Error during retry attempt: {}", e);
                    }
                }
            }
        }
    }
}

impl Clone for DeadLetterQueue {
    fn clone(&self) -> Self {
        Self {
            config: self.config.clone(),
            failed_messages: Arc::clone(&self.failed_messages),
            stats: Arc::clone(&self.stats),
        }
    }
}

impl Default for DlqConfig {
    fn default() -> Self {
        Self {
            max_messages: 1000,
            max_retries: 3,
            retry_delay_multiplier: 2.0,
            initial_retry_delay_ms: 1000,
            max_retry_delay_ms: 30000,
            enable_auto_retry: true,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[tokio::test]
    async fn test_dlq_basic_functionality() {
        let config = DlqConfig::default();
        let dlq = DeadLetterQueue::new(config);

        let message = Message::new(
            "test.topic".to_string(),
            json!({"test": "data"}),
            None,
        );

        // Add failed message
        dlq.add_failed_message(message.clone(), "Test error".to_string())
            .await
            .unwrap();

        let stats = dlq.get_stats().await.unwrap();
        assert_eq!(stats.total_failed, 1);
        assert_eq!(stats.messages_in_dlq, 1);

        // Get all failed messages
        let failed_messages = dlq.get_all_failed_messages().await.unwrap();
        assert_eq!(failed_messages.len(), 1);
        assert_eq!(failed_messages[0].message.id, message.id);
    }

    #[tokio::test]
    async fn test_dlq_retry_mechanism() {
        let config = DlqConfig {
            max_retries: 2,
            enable_auto_retry: true,
            ..Default::default()
        };
        let dlq = DeadLetterQueue::new(config);

        let message = Message::new(
            "test.topic".to_string(),
            json!({"test": "data"}),
            None,
        );

        dlq.add_failed_message(message, "Test error".to_string())
            .await
            .unwrap();

        let failed_messages = dlq.get_all_failed_messages().await.unwrap();
        let dlq_id = failed_messages[0].dlq_id;

        // Mark first retry as failed
        dlq.mark_retry_attempt(dlq_id, false).await.unwrap();

        let stats = dlq.get_stats().await.unwrap();
        assert_eq!(stats.total_retries, 1);

        // Mark second retry as successful
        dlq.mark_retry_attempt(dlq_id, true).await.unwrap();

        let stats = dlq.get_stats().await.unwrap();
        assert_eq!(stats.recovered_messages, 1);
        assert_eq!(stats.messages_in_dlq, 0);
    }
}