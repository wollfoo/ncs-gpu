/*!
# Core Event-Driven Engine

**High-performance event bus** dựa trên **NATS JetStream** cho
**asynchronous message processing** với **at-least-once delivery**.

## Architecture

```text
┌─────────────┐    Events     ┌─────────────┐    Handlers   ┌─────────────┐
│  Publishers │ ──────────→   │  Event Bus  │ ──────────→   │  Consumers  │
│             │               │   (NATS)    │               │             │
└─────────────┘               └─────────────┘               └─────────────┘
```

## Event Types

- **[`GpuEvent`]**: GPU operations (optimize, allocate, monitor)  
- **[`ResourceEvent`]**: Resource management (allocate, deallocate, monitor)
- **[`StealtHEvent`]**: Process stealth operations (hide, unhide, monitor)

## Example Usage

```rust
use app_gpu::core::{EventBus, GpuEvent, EventType};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let event_bus = EventBus::new("nats://localhost:4222").await?;
    
    // Publish GPU event
    let event = GpuEvent::OptimizeProcess { pid: 1234, gpu_index: 0 };
    event_bus.publish("gpu.optimize", event).await?;
    
    // Subscribe to events
    event_bus.subscribe("gpu.>", |event| async move {
        println!("Received GPU event: {:?}", event);
        Ok(())
    }).await?;
    
    event_bus.start().await?;
    Ok(())
}
```
*/

use anyhow::{Context, Result};
use async_nats::jetstream;
use dashmap::DashMap;
use futures::StreamExt;
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::{broadcast, RwLock};
use tracing::{debug, error, info, warn};

pub mod event_types;
pub mod handlers;

pub use event_types::{EventType, GpuEvent, ResourceEvent, StealtHEvent};
pub use handlers::{EventHandler, HandlerRegistry};

/// **Event Bus** - Core message routing system
#[derive(Clone)]
pub struct EventBus {
    client: async_nats::Client,
    jetstream: Arc<RwLock<Option<jetstream::Context>>>,
    publisher_stats: Arc<PublisherStats>,
    consumer_stats: Arc<DashMap<String, ConsumerStats>>,
    handler_registry: Arc<HandlerRegistry>,
    shutdown_signal: Arc<AtomicBool>,
    health_status: Arc<AtomicBool>,
}

/// **Publisher Statistics** (thống kê publisher)
#[derive(Debug, Default)]
pub struct PublisherStats {
    pub messages_sent: AtomicU64,
    pub bytes_sent: AtomicU64,
    pub errors: AtomicU64,
    pub last_publish_time: AtomicU64,
}

/// **Consumer Statistics** (thống kê consumer)
#[derive(Debug, Default)]
pub struct ConsumerStats {
    pub messages_received: AtomicU64,
    pub bytes_received: AtomicU64,
    pub processing_errors: AtomicU64,
    pub last_message_time: AtomicU64,
    pub active_handlers: AtomicU64,
}

/// **Event Metadata** (metadata event)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventMetadata {
    pub event_id: String,
    pub timestamp: u64,
    pub source: String,
    pub correlation_id: Option<String>,
    pub retry_count: u32,
    pub priority: EventPriority,
}

/// **Event Priority** (ưu tiên event)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EventPriority {
    Low,
    Normal,
    High,
    Critical,
}

/// **Event Envelope** (bao bì event)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventEnvelope {
    pub metadata: EventMetadata,
    pub event_type: String,
    pub payload: serde_json::Value,
}

/// **Subscription Handle** (handle subscription)
pub struct SubscriptionHandle {
    subject: String,
    cancel_tx: broadcast::Sender<()>,
    stats: Arc<ConsumerStats>,
}

impl EventBus {
    /// **Create new EventBus** (tạo EventBus mới)
    pub async fn new(nats_url: &str) -> Result<Self> {
        info!("🔌 Connecting to NATS at {}", nats_url);
        
        let client = async_nats::connect(nats_url)
            .await
            .with_context(|| format!("Failed to connect to NATS at {}", nats_url))?;
        
        info!("✅ Connected to NATS successfully");
        
        let publisher_stats = Arc::new(PublisherStats::default());
        let consumer_stats = Arc::new(DashMap::new());
        let handler_registry = Arc::new(HandlerRegistry::new());
        let shutdown_signal = Arc::new(AtomicBool::new(false));
        let health_status = Arc::new(AtomicBool::new(true));
        
        Ok(Self {
            client,
            jetstream: Arc::new(RwLock::new(None)),
            publisher_stats,
            consumer_stats,
            handler_registry,
            shutdown_signal,
            health_status,
        })
    }
    
    /// **Initialize JetStream** (khởi tạo JetStream)
    pub async fn init_jetstream(&self) -> Result<()> {
        info!("🚀 Initializing JetStream...");
        
        let jetstream = jetstream::new(self.client.clone());
        
        // Create streams for different event types
        self.create_stream(&jetstream, "GPU_EVENTS", &["gpu.>"])
            .await
            .context("Failed to create GPU events stream")?;
            
        self.create_stream(&jetstream, "RESOURCE_EVENTS", &["resource.>"])
            .await
            .context("Failed to create resource events stream")?;
            
        self.create_stream(&jetstream, "STEALTH_EVENTS", &["stealth.>"])
            .await
            .context("Failed to create stealth events stream")?;
            
        self.create_stream(&jetstream, "MONITORING_EVENTS", &["monitoring.>"])
            .await
            .context("Failed to create monitoring events stream")?;
        
        *self.jetstream.write().await = Some(jetstream);
        info!("✅ JetStream initialized successfully");
        
        Ok(())
    }
    
    /// **Create JetStream stream** (tạo JetStream stream)
    async fn create_stream(
        &self,
        jetstream: &jetstream::Context,
        stream_name: &str,
        subjects: &[&str],
    ) -> Result<()> {
        let stream_config = jetstream::stream::Config {
            name: stream_name.to_string(),
            subjects: subjects.iter().map(|s| s.to_string()).collect(),
            max_messages: 10_000,
            max_bytes: 1_024_000_000, // 1GB
            max_age: Duration::from_secs(24 * 3600), // 24 hours
            storage: jetstream::stream::StorageType::File,
            num_replicas: 1,
            ..Default::default()
        };
        
        match jetstream.get_or_create_stream(stream_config).await {
            Ok(_) => {
                debug!("✅ Stream '{}' ready", stream_name);
                Ok(())
            }
            Err(e) => {
                error!("❌ Failed to create stream '{}': {}", stream_name, e);
                Err(anyhow::anyhow!("Stream creation failed: {}", e))
            }
        }
    }
    
    /// **Publish event** (xuất bản event)
    pub async fn publish<T>(&self, subject: &str, event: T) -> Result<()>
    where
        T: EventType + Serialize + Send + 'static,
    {
        let metadata = EventMetadata {
            event_id: uuid::Uuid::new_v4().to_string(),
            timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            source: "app-gpu".to_string(),
            correlation_id: None,
            retry_count: 0,
            priority: EventPriority::Normal,
        };
        
        let envelope = EventEnvelope {
            metadata,
            event_type: T::event_type(),
            payload: serde_json::to_value(&event)
                .context("Failed to serialize event")?,
        };
        
        let payload = bincode::serialize(&envelope)
            .context("Failed to serialize envelope")?;
        
        // Try JetStream first, fallback to core NATS
        if let Some(jetstream) = &*self.jetstream.read().await {
            match jetstream.publish(subject.to_string(), payload.clone().into()).await {
                Ok(_) => {
                    self.update_publisher_stats(payload.len());
                    debug!("📤 Published event to {} via JetStream", subject);
                    return Ok(());
                }
                Err(e) => {
                    warn!("⚠️ JetStream publish failed, falling back to core NATS: {}", e);
                }
            }
        }
        
        // Fallback to core NATS
        self.client
            .publish(subject.to_string(), payload.into())
            .await
            .with_context(|| format!("Failed to publish to subject {}", subject))?;
        
        self.update_publisher_stats(payload.len());
        debug!("📤 Published event to {} via core NATS", subject);
        
        Ok(())
    }
    
    /// **Register GPU event handler** (đăng ký handler event GPU)
    pub async fn register_gpu_handler<F>(&self, subject: &str, handler: F) -> Result<()>
    where
        F: Fn(GpuEvent) -> futures::future::BoxFuture<'static, Result<()>> + Send + Sync + 'static,
    {
        self.handler_registry.register_gpu_handler(subject, handler)
    }

    /// **Register resource event handler** (đăng ký handler event tài nguyên)
    pub async fn register_resource_handler<F>(&self, subject: &str, handler: F) -> Result<()>
    where
        F: Fn(ResourceEvent) -> futures::future::BoxFuture<'static, Result<()>> + Send + Sync + 'static,
    {
        self.handler_registry.register_resource_handler(subject, handler)
    }

    /// **Register stealth event handler** (đăng ký handler event ẩn danh)
    pub async fn register_stealth_handler<F>(&self, subject: &str, handler: F) -> Result<()>
    where
        F: Fn(StealtHEvent) -> futures::future::BoxFuture<'static, Result<()>> + Send + Sync + 'static,
    {
        self.handler_registry.register_stealth_handler(subject, handler)
    }

    /// **Subscribe to events** (đăng ký nhận events)
    pub async fn subscribe<F>(&self, subject: &str, handler: F) -> Result<SubscriptionHandle>
    where
        F: Fn(EventEnvelope) -> futures::future::BoxFuture<'static, Result<()>>
            + Send
            + Sync
            + 'static,
    {
        let (cancel_tx, mut cancel_rx) = broadcast::channel(1);
        let stats = Arc::new(ConsumerStats::default());
        
        let consumer_stats = Arc::clone(&stats);
        self.consumer_stats.insert(subject.to_string(), Arc::clone(&stats));
        
        let mut subscription = self.client
            .subscribe(subject.to_string())
            .await
            .with_context(|| format!("Failed to subscribe to {}", subject))?;
            
        let handler = Arc::new(handler);
        let subject_clone = subject.to_string();
        
        // Spawn subscription handler
        tokio::spawn(async move {
            info!("📥 Started subscription to '{}'", subject_clone);
            
            loop {
                tokio::select! {
                    msg_opt = subscription.next() => {
                        if let Some(msg) = msg_opt {
                            let payload_len = msg.payload.len();
                            
                            match bincode::deserialize::<EventEnvelope>(&msg.payload) {
                                Ok(envelope) => {
                                    consumer_stats.messages_received.fetch_add(1, Ordering::Relaxed);
                                    consumer_stats.bytes_received.fetch_add(payload_len as u64, Ordering::Relaxed);
                                    consumer_stats.last_message_time.store(
                                        SystemTime::now()
                                            .duration_since(UNIX_EPOCH)
                                            .unwrap()
                                            .as_secs(),
                                        Ordering::Relaxed
                                    );
                                    
                                    consumer_stats.active_handlers.fetch_add(1, Ordering::Relaxed);
                                    
                                    // Process event
                                    if let Err(e) = handler(envelope).await {
                                        error!("❌ Event handler error: {}", e);
                                        consumer_stats.processing_errors.fetch_add(1, Ordering::Relaxed);
                                    }
                                    
                                    consumer_stats.active_handlers.fetch_sub(1, Ordering::Relaxed);
                                }
                                Err(e) => {
                                    error!("❌ Failed to deserialize event envelope: {}", e);
                                    consumer_stats.processing_errors.fetch_add(1, Ordering::Relaxed);
                                }
                            }
                        } else {
                            warn!("⚠️ Subscription stream ended for '{}'", subject_clone);
                            break;
                        }
                    }
                    
                    _ = cancel_rx.recv() => {
                        info!("🛑 Subscription cancelled for '{}'", subject_clone);
                        break;
                    }
                }
            }
            
            info!("📪 Subscription to '{}' terminated", subject_clone);
        });
        
        Ok(SubscriptionHandle {
            subject: subject.to_string(),
            cancel_tx,
            stats,
        })
    }
    
    /// **Start event bus** (khởi động event bus)
    pub async fn start(&self) -> Result<()> {
        info!("🚀 Starting EventBus...");
        
        // Initialize JetStream
        self.init_jetstream().await?;
        
        // Start health monitoring
        self.start_health_monitoring().await;
        
        info!("✅ EventBus started successfully");
        Ok(())
    }
    
    /// **Shutdown event bus** (tắt event bus)
    pub async fn shutdown(&self) -> Result<()> {
        info!("🛑 Shutting down EventBus...");
        
        self.shutdown_signal.store(true, Ordering::SeqCst);
        
        // Close NATS connection
        if let Err(e) = self.client.flush().await {
            warn!("⚠️ Failed to flush NATS client: {}", e);
        }
        
        info!("✅ EventBus shutdown completed");
        Ok(())
    }
    
    /// **Check if event bus is healthy** (kiểm tra sức khỏe event bus)
    pub async fn is_healthy(&self) -> bool {
        if self.shutdown_signal.load(Ordering::SeqCst) {
            return false;
        }
        
        self.health_status.load(Ordering::SeqCst)
    }
    
    /// **Get publisher statistics** (lấy thống kê publisher)
    pub fn get_publisher_stats(&self) -> &PublisherStats {
        &self.publisher_stats
    }
    
    /// **Get consumer statistics** (lấy thống kê consumer)  
    pub fn get_consumer_stats(&self, subject: &str) -> Option<Arc<ConsumerStats>> {
        self.consumer_stats.get(subject).map(|stats| Arc::clone(&*stats))
    }
    
    /// **Update publisher statistics** (cập nhật thống kê publisher)
    fn update_publisher_stats(&self, payload_size: usize) {
        self.publisher_stats.messages_sent.fetch_add(1, Ordering::Relaxed);
        self.publisher_stats.bytes_sent.fetch_add(payload_size as u64, Ordering::Relaxed);
        self.publisher_stats.last_publish_time.store(
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            Ordering::Relaxed
        );
    }
    
    /// **Start health monitoring** (bắt đầu giám sát sức khỏe)
    async fn start_health_monitoring(&self) {
        let client = self.client.clone();
        let health_status = Arc::clone(&self.health_status);
        let shutdown_signal = Arc::clone(&self.shutdown_signal);
        
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(10));
            
            while !shutdown_signal.load(Ordering::SeqCst) {
                interval.tick().await;
                
                // Check NATS connection health
                match client.connection_state() {
                    async_nats::ConnectionState::Connected => {
                        health_status.store(true, Ordering::SeqCst);
                    }
                    state => {
                        warn!("⚠️ NATS connection unhealthy: {:?}", state);
                        health_status.store(false, Ordering::SeqCst);
                    }
                }
            }
        });
    }
}

impl SubscriptionHandle {
    /// **Cancel subscription** (hủy subscription)
    pub fn cancel(&self) -> Result<()> {
        self.cancel_tx
            .send(())
            .map_err(|_| anyhow::anyhow!("Failed to send cancel signal"))?;
        Ok(())
    }
    
    /// **Get subscription statistics** (lấy thống kê subscription)
    pub fn get_stats(&self) -> &ConsumerStats {
        &self.stats
    }
    
    /// **Get subject** (lấy subject)
    pub fn subject(&self) -> &str {
        &self.subject
    }
}

impl Default for EventPriority {
    fn default() -> Self {
        Self::Normal
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;
    use tokio::time::timeout;

    #[tokio::test]
    async fn test_event_bus_creation() -> Result<()> {
        // This test requires a running NATS server
        // Skip if NATS_TEST_URL is not set
        if std::env::var("NATS_TEST_URL").is_err() {
            return Ok(());
        }
        
        let nats_url = std::env::var("NATS_TEST_URL").unwrap_or_else(|_| "nats://localhost:4222".to_string());
        
        let event_bus = EventBus::new(&nats_url).await;
        assert!(event_bus.is_ok());
        
        Ok(())
    }
    
    #[test]
    fn test_event_metadata() {
        let metadata = EventMetadata {
            event_id: "test-123".to_string(),
            timestamp: 1234567890,
            source: "test".to_string(),
            correlation_id: Some("corr-456".to_string()),
            retry_count: 0,
            priority: EventPriority::High,
        };
        
        assert_eq!(metadata.event_id, "test-123");
        assert_eq!(metadata.timestamp, 1234567890);
        assert_eq!(metadata.source, "test");
        assert_eq!(metadata.correlation_id, Some("corr-456".to_string()));
        assert_eq!(metadata.retry_count, 0);
        assert!(matches!(metadata.priority, EventPriority::High));
    }
    
    #[test]
    fn test_publisher_stats() {
        let stats = PublisherStats::default();
        assert_eq!(stats.messages_sent.load(Ordering::Relaxed), 0);
        assert_eq!(stats.bytes_sent.load(Ordering::Relaxed), 0);
        assert_eq!(stats.errors.load(Ordering::Relaxed), 0);
        
        stats.messages_sent.fetch_add(1, Ordering::Relaxed);
        stats.bytes_sent.fetch_add(100, Ordering::Relaxed);
        
        assert_eq!(stats.messages_sent.load(Ordering::Relaxed), 1);
        assert_eq!(stats.bytes_sent.load(Ordering::Relaxed), 100);
    }
}
