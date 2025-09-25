//! NATS Lite - Lightweight async NATS client for GPU job scheduling
//!
//! Features:
//! - Type-safe message serialization
//! - Automatic reconnection với exponential backoff
//! - Message acknowledgment và retry
//! - Flow control và backpressure
//! - Request-reply patterns

use anyhow::{Context, Result};
use bytes::Bytes;
use futures::StreamExt;
use nats::{jetstream::JetStream, Connection, Message};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    sync::Arc,
    time::Duration,
};
use tokio::sync::{mpsc, RwLock};
use tracing::{debug, info, warn, error, instrument};

pub mod client;
pub mod job_message;
pub mod subscription;

pub use client::NatsLiteClient;
pub use job_message::{JobMessage, JobType, MessageMetadata};
pub use subscription::TypedSubscription;

/// NATS connection configuration
#[derive(Debug, Clone)]
pub struct NatsConfig {
    pub servers: Vec<String>,
    pub connection_timeout: Duration,
    pub reconnect_delay_max: Duration,
    pub max_reconnect_attempts: u32,
    pub enable_jetstream: bool,
    pub stream_config: Option<StreamConfig>,
}

/// JetStream configuration
#[derive(Debug, Clone)]
pub struct StreamConfig {
    pub name: String,
    pub subjects: Vec<String>,
    pub max_messages: u64,
    pub max_age: Duration,
    pub retention_policy: RetentionPolicy,
}

#[derive(Debug, Clone)]
pub enum RetentionPolicy {
    Limits,
    Interest,
    WorkQueue,
}

/// Message envelope for type-safe messaging
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageEnvelope<T> {
    pub id: String,
    pub timestamp: u64,
    pub sender: String,
    pub message_type: String,
    pub payload: T,
    pub metadata: HashMap<String, String>,
}

/// Subscription callback type
pub type MessageHandler<T> = Box<dyn Fn(MessageEnvelope<T>) -> Result<()> + Send + Sync>;

/// Error types
#[derive(Debug, thiserror::Error)]
pub enum NatsError {
    #[error("Connection failed: {0}")]
    ConnectionFailed(String),
    
    #[error("Subscription failed: {0}")]
    SubscriptionFailed(String),
    
    #[error("Publish failed: {0}")]
    PublishFailed(String),
    
    #[error("Serialization failed: {0}")]
    SerializationFailed(String),
    
    #[error("Timeout: {0}")]
    Timeout(String),
}

/// Result type alias
pub type NatsResult<T> = std::result::Result<T, NatsError>;

#[cfg(test)]
mod tests {
    use super::*;
    use tokio_test;
    
    #[derive(Debug, Serialize, Deserialize, PartialEq)]
    struct TestMessage {
        content: String,
        value: u32,
    }
    
    #[tokio::test]
    async fn test_message_envelope_serialization() {
        let test_msg = TestMessage {
            content: "Hello NATS".to_string(),
            value: 42,
        };
        
        let envelope = MessageEnvelope {
            id: "test-1".to_string(),
            timestamp: 1234567890,
            sender: "test-sender".to_string(),
            message_type: "test".to_string(),
            payload: test_msg.clone(),
            metadata: HashMap::new(),
        };
        
        // Test serialization roundtrip
        let json = serde_json::to_string(&envelope).unwrap();
        let deserialized: MessageEnvelope<TestMessage> = serde_json::from_str(&json).unwrap();
        
        assert_eq!(envelope.id, deserialized.id);
        assert_eq!(envelope.payload.content, deserialized.payload.content);
        assert_eq!(envelope.payload.value, deserialized.payload.value);
    }
}
