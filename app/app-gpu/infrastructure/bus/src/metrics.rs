use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

/// Message bus metrics and monitoring
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BusMetrics {
    /// Message processing metrics
    pub message_metrics: MessageMetrics,
    /// Topic-specific metrics
    pub topic_metrics: HashMap<String, TopicMetrics>,
    /// Performance metrics
    pub performance_metrics: PerformanceMetrics,
    /// Error metrics
    pub error_metrics: ErrorMetrics,
    /// System health metrics
    pub health_metrics: HealthMetrics,
    /// Last updated timestamp
    pub last_updated: DateTime<Utc>,
}

/// Message processing metrics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MessageMetrics {
    /// Total messages sent
    pub total_sent: u64,
    /// Total messages received
    pub total_received: u64,
    /// Messages sent per second (current rate)
    pub send_rate: f64,
    /// Messages received per second (current rate)
    pub receive_rate: f64,
    /// Total bytes processed
    pub total_bytes: u64,
    /// Average message size
    pub avg_message_size: f64,
}

/// Topic-specific metrics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct TopicMetrics {
    /// Topic name
    pub topic: String,
    /// Number of subscribers
    pub subscriber_count: usize,
    /// Messages sent to this topic
    pub messages_sent: u64,
    /// Messages received from this topic
    pub messages_received: u64,
    /// Last activity timestamp
    pub last_activity: Option<DateTime<Utc>>,
    /// Average message processing time for this topic
    pub avg_processing_time_ms: f64,
    /// Error count for this topic
    pub error_count: u64,
}

/// Performance metrics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PerformanceMetrics {
    /// Average message processing time (milliseconds)
    pub avg_processing_time_ms: f64,
    /// 95th percentile processing time (milliseconds)
    pub p95_processing_time_ms: f64,
    /// 99th percentile processing time (milliseconds)
    pub p99_processing_time_ms: f64,
    /// Maximum processing time (milliseconds)
    pub max_processing_time_ms: f64,
    /// Current queue depth
    pub queue_depth: usize,
    /// Maximum queue depth reached
    pub max_queue_depth: usize,
    /// Memory usage (bytes)
    pub memory_usage_bytes: u64,
    /// CPU usage percentage
    pub cpu_usage_percent: f64,
}

/// Error metrics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ErrorMetrics {
    /// Total errors
    pub total_errors: u64,
    /// Errors per minute (current rate)
    pub error_rate: f64,
    /// Error breakdown by type
    pub error_types: HashMap<String, u64>,
    /// Recent errors (last 100)
    pub recent_errors: Vec<ErrorEvent>,
    /// Dead letter queue size
    pub dlq_size: usize,
}

/// Health metrics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct HealthMetrics {
    /// Overall health status
    pub status: HealthStatus,
    /// Uptime in seconds
    pub uptime_seconds: u64,
    /// Number of active connections
    pub active_connections: usize,
    /// System load
    pub system_load: f64,
    /// Available memory percentage
    pub available_memory_percent: f64,
    /// Last health check timestamp
    pub last_health_check: Option<DateTime<Utc>>,
}

/// Health status enumeration
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum HealthStatus {
    Healthy,
    Warning,
    Critical,
    Down,
}

impl Default for HealthStatus {
    fn default() -> Self {
        HealthStatus::Healthy
    }
}

/// Error event for tracking
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorEvent {
    /// Error message
    pub message: String,
    /// Error type/category
    pub error_type: String,
    /// Associated topic (if any)
    pub topic: Option<String>,
    /// Timestamp
    pub timestamp: DateTime<Utc>,
    /// Additional context
    pub context: HashMap<String, String>,
}

/// Processing time sample for percentile calculations
#[derive(Debug, Clone)]
struct ProcessingTimeSample {
    duration_ms: f64,
    timestamp: Instant,
}

/// Metrics collector for the message bus
pub struct MetricsCollector {
    metrics: Arc<RwLock<BusMetrics>>,
    processing_times: Arc<RwLock<Vec<ProcessingTimeSample>>>,
    start_time: Instant,
    last_rate_calculation: Arc<RwLock<Instant>>,
    last_message_counts: Arc<RwLock<(u64, u64)>>, // (sent, received)
}

impl MetricsCollector {
    /// Create a new metrics collector
    pub fn new() -> Self {
        let start_time = Instant::now();

        Self {
            metrics: Arc::new(RwLock::new(BusMetrics::default())),
            processing_times: Arc::new(RwLock::new(Vec::new())),
            start_time,
            last_rate_calculation: Arc::new(RwLock::new(start_time)),
            last_message_counts: Arc::new(RwLock::new((0, 0))),
        }
    }

    /// Record a message being sent
    pub async fn record_message_sent(&self, topic: &str, size_bytes: usize) {
        let mut metrics = self.metrics.write().await;

        // Update message metrics
        metrics.message_metrics.total_sent += 1;
        metrics.message_metrics.total_bytes += size_bytes as u64;

        // Update average message size
        if metrics.message_metrics.total_sent > 0 {
            metrics.message_metrics.avg_message_size =
                metrics.message_metrics.total_bytes as f64 /
                (metrics.message_metrics.total_sent + metrics.message_metrics.total_received) as f64;
        }

        // Update topic metrics
        let topic_metrics = metrics.topic_metrics
            .entry(topic.to_string())
            .or_insert_with(|| TopicMetrics {
                topic: topic.to_string(),
                ..Default::default()
            });

        topic_metrics.messages_sent += 1;
        topic_metrics.last_activity = Some(Utc::now());

        metrics.last_updated = Utc::now();
    }

    /// Record a message being received
    pub async fn record_message_received(&self, topic: &str) {
        let mut metrics = self.metrics.write().await;

        metrics.message_metrics.total_received += 1;

        // Update topic metrics
        let topic_metrics = metrics.topic_metrics
            .entry(topic.to_string())
            .or_insert_with(|| TopicMetrics {
                topic: topic.to_string(),
                ..Default::default()
            });

        topic_metrics.messages_received += 1;
        topic_metrics.last_activity = Some(Utc::now());

        metrics.last_updated = Utc::now();
    }

    /// Record message processing time
    pub async fn record_processing_time(&self, topic: &str, duration: Duration) {
        let duration_ms = duration.as_secs_f64() * 1000.0;

        // Add to processing times for percentile calculation
        {
            let mut times = self.processing_times.write().await;
            times.push(ProcessingTimeSample {
                duration_ms,
                timestamp: Instant::now(),
            });

            // Keep only recent samples (last 1000)
            if times.len() > 1000 {
                times.drain(0..times.len() - 1000);
            }
        }

        // Update metrics
        let mut metrics = self.metrics.write().await;

        // Update overall performance metrics
        self.update_performance_metrics(&mut metrics.performance_metrics, duration_ms).await;

        // Update topic-specific metrics
        if let Some(topic_metrics) = metrics.topic_metrics.get_mut(topic) {
            // Simple moving average for topic processing time
            topic_metrics.avg_processing_time_ms =
                (topic_metrics.avg_processing_time_ms + duration_ms) / 2.0;
        }

        metrics.last_updated = Utc::now();
    }

    /// Record an error
    pub async fn record_error(&self, error_type: &str, message: &str, topic: Option<&str>) {
        let mut metrics = self.metrics.write().await;

        metrics.error_metrics.total_errors += 1;

        // Update error type count
        *metrics.error_metrics.error_types
            .entry(error_type.to_string())
            .or_insert(0) += 1;

        // Add to recent errors
        let error_event = ErrorEvent {
            message: message.to_string(),
            error_type: error_type.to_string(),
            topic: topic.map(|t| t.to_string()),
            timestamp: Utc::now(),
            context: HashMap::new(),
        };

        metrics.error_metrics.recent_errors.push(error_event);

        // Keep only last 100 errors
        if metrics.error_metrics.recent_errors.len() > 100 {
            metrics.error_metrics.recent_errors.drain(0..1);
        }

        // Update topic error count if applicable
        if let Some(topic_name) = topic {
            if let Some(topic_metrics) = metrics.topic_metrics.get_mut(topic_name) {
                topic_metrics.error_count += 1;
            }
        }

        metrics.last_updated = Utc::now();
    }

    /// Update subscriber count for a topic
    pub async fn update_subscriber_count(&self, topic: &str, count: usize) {
        let mut metrics = self.metrics.write().await;

        let topic_metrics = metrics.topic_metrics
            .entry(topic.to_string())
            .or_insert_with(|| TopicMetrics {
                topic: topic.to_string(),
                ..Default::default()
            });

        topic_metrics.subscriber_count = count;
        metrics.last_updated = Utc::now();
    }

    /// Update queue depth
    pub async fn update_queue_depth(&self, depth: usize) {
        let mut metrics = self.metrics.write().await;

        metrics.performance_metrics.queue_depth = depth;
        metrics.performance_metrics.max_queue_depth =
            metrics.performance_metrics.max_queue_depth.max(depth);

        metrics.last_updated = Utc::now();
    }

    /// Update DLQ size
    pub async fn update_dlq_size(&self, size: usize) {
        let mut metrics = self.metrics.write().await;
        metrics.error_metrics.dlq_size = size;
        metrics.last_updated = Utc::now();
    }

    /// Calculate and update rates
    pub async fn update_rates(&self) {
        let now = Instant::now();
        let mut last_time = self.last_rate_calculation.write().await;
        let mut last_counts = self.last_message_counts.write().await;

        let time_diff = now.duration_since(*last_time).as_secs_f64();

        if time_diff >= 1.0 { // Update rates every second
            let metrics = self.metrics.read().await;
            let current_sent = metrics.message_metrics.total_sent;
            let current_received = metrics.message_metrics.total_received;

            drop(metrics); // Release read lock

            let sent_diff = current_sent - last_counts.0;
            let received_diff = current_received - last_counts.1;

            let mut metrics = self.metrics.write().await;
            metrics.message_metrics.send_rate = sent_diff as f64 / time_diff;
            metrics.message_metrics.receive_rate = received_diff as f64 / time_diff;

            // Update error rate
            metrics.error_metrics.error_rate =
                metrics.error_metrics.total_errors as f64 / 60.0; // errors per minute

            *last_time = now;
            *last_counts = (current_sent, current_received);

            metrics.last_updated = Utc::now();
        }
    }

    /// Update performance metrics with new processing time
    async fn update_performance_metrics(&self, perf_metrics: &mut PerformanceMetrics, duration_ms: f64) {
        // Update average (simple moving average)
        perf_metrics.avg_processing_time_ms =
            (perf_metrics.avg_processing_time_ms + duration_ms) / 2.0;

        // Update maximum
        perf_metrics.max_processing_time_ms =
            perf_metrics.max_processing_time_ms.max(duration_ms);

        // Calculate percentiles from recent samples
        let times = self.processing_times.read().await;
        if !times.is_empty() {
            let mut durations: Vec<f64> = times.iter().map(|s| s.duration_ms).collect();
            durations.sort_by(|a, b| a.partial_cmp(b).unwrap());

            let len = durations.len();
            if len > 0 {
                perf_metrics.p95_processing_time_ms = durations[(len as f64 * 0.95) as usize];
                perf_metrics.p99_processing_time_ms = durations[(len as f64 * 0.99) as usize];
            }
        }
    }

    /// Update health status
    pub async fn update_health_status(&self, status: HealthStatus) {
        let mut metrics = self.metrics.write().await;
        metrics.health_metrics.status = status;
        metrics.health_metrics.last_health_check = Some(Utc::now());
        metrics.health_metrics.uptime_seconds = self.start_time.elapsed().as_secs();
        metrics.last_updated = Utc::now();
    }

    /// Get current metrics snapshot
    pub async fn get_metrics(&self) -> BusMetrics {
        // Update rates before returning metrics
        self.update_rates().await;

        let metrics = self.metrics.read().await;
        metrics.clone()
    }

    /// Get metrics for a specific topic
    pub async fn get_topic_metrics(&self, topic: &str) -> Option<TopicMetrics> {
        let metrics = self.metrics.read().await;
        metrics.topic_metrics.get(topic).cloned()
    }

    /// Reset all metrics
    pub async fn reset_metrics(&self) {
        info!("🔄 Resetting message bus metrics");

        let mut metrics = self.metrics.write().await;
        *metrics = BusMetrics::default();

        let mut times = self.processing_times.write().await;
        times.clear();

        let mut last_counts = self.last_message_counts.write().await;
        *last_counts = (0, 0);

        let mut last_time = self.last_rate_calculation.write().await;
        *last_time = Instant::now();
    }

    /// Start metrics collection background task
    pub async fn start_collection_task(&self) -> Result<()> {
        let collector = self.clone();

        tokio::spawn(async move {
            collector.collection_worker().await;
        });

        info!("📊 Started metrics collection task");
        Ok(())
    }

    /// Background worker for metrics collection
    async fn collection_worker(&self) {
        let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(1));

        loop {
            interval.tick().await;

            // Update rates
            self.update_rates().await;

            // Perform health checks
            self.perform_health_check().await;
        }
    }

    /// Perform system health check
    async fn perform_health_check(&self) {
        let metrics = self.metrics.read().await;
        let error_rate = metrics.error_metrics.error_rate;
        let queue_depth = metrics.performance_metrics.queue_depth;
        let avg_processing_time = metrics.performance_metrics.avg_processing_time_ms;

        drop(metrics); // Release read lock

        let status = if error_rate > 10.0 || queue_depth > 1000 || avg_processing_time > 5000.0 {
            HealthStatus::Critical
        } else if error_rate > 5.0 || queue_depth > 500 || avg_processing_time > 1000.0 {
            HealthStatus::Warning
        } else {
            HealthStatus::Healthy
        };

        if status != HealthStatus::Healthy {
            warn!("⚠️ Message bus health status: {:?}", status);
        }

        self.update_health_status(status).await;
    }
}

impl Clone for MetricsCollector {
    fn clone(&self) -> Self {
        Self {
            metrics: Arc::clone(&self.metrics),
            processing_times: Arc::clone(&self.processing_times),
            start_time: self.start_time,
            last_rate_calculation: Arc::clone(&self.last_rate_calculation),
            last_message_counts: Arc::clone(&self.last_message_counts),
        }
    }
}

impl Default for BusMetrics {
    fn default() -> Self {
        Self {
            message_metrics: MessageMetrics::default(),
            topic_metrics: HashMap::new(),
            performance_metrics: PerformanceMetrics::default(),
            error_metrics: ErrorMetrics::default(),
            health_metrics: HealthMetrics::default(),
            last_updated: Utc::now(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[tokio::test]
    async fn test_metrics_collection() {
        let collector = MetricsCollector::new();

        // Record some metrics
        collector.record_message_sent("test.topic", 100).await;
        collector.record_message_received("test.topic").await;
        collector.record_processing_time("test.topic", Duration::from_millis(50)).await;

        let metrics = collector.get_metrics().await;

        assert_eq!(metrics.message_metrics.total_sent, 1);
        assert_eq!(metrics.message_metrics.total_received, 1);
        assert_eq!(metrics.message_metrics.total_bytes, 100);

        let topic_metrics = metrics.topic_metrics.get("test.topic").unwrap();
        assert_eq!(topic_metrics.messages_sent, 1);
        assert_eq!(topic_metrics.messages_received, 1);
    }

    #[tokio::test]
    async fn test_error_recording() {
        let collector = MetricsCollector::new();

        collector.record_error("connection_failed", "Failed to connect", Some("test.topic")).await;

        let metrics = collector.get_metrics().await;

        assert_eq!(metrics.error_metrics.total_errors, 1);
        assert_eq!(metrics.error_metrics.error_types.get("connection_failed"), Some(&1));
        assert_eq!(metrics.error_metrics.recent_errors.len(), 1);
    }
}