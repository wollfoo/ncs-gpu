//! Structured logging module for centralized log aggregation
//! 
//! Provides structured logging with JSON format for easy parsing and indexing

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fmt;
use std::sync::Arc;
use tokio::sync::mpsc;
use tokio::io::AsyncWriteExt;
use tokio::fs::OpenOptions;
use chrono::{DateTime, Utc};
use anyhow::{Result, Context};

/// Log level enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum LogLevel {
    Trace = 0,
    Debug = 1,
    Info = 2,
    Warn = 3,
    Error = 4,
    Fatal = 5,
}

impl fmt::Display for LogLevel {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            LogLevel::Trace => write!(f, "TRACE"),
            LogLevel::Debug => write!(f, "DEBUG"),
            LogLevel::Info => write!(f, "INFO"),
            LogLevel::Warn => write!(f, "WARN"),
            LogLevel::Error => write!(f, "ERROR"),
            LogLevel::Fatal => write!(f, "FATAL"),
        }
    }
}

/// Structured log entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    /// Timestamp in ISO 8601 format
    pub timestamp: DateTime<Utc>,
    
    /// Log level
    pub level: LogLevel,
    
    /// Service name
    pub service: String,
    
    /// Component within service
    pub component: String,
    
    /// Log message
    pub message: String,
    
    /// Trace ID for correlation
    pub trace_id: Option<String>,
    
    /// Span ID for distributed tracing
    pub span_id: Option<String>,
    
    /// GPU device ID if applicable
    pub gpu_device_id: Option<usize>,
    
    /// Task ID if applicable
    pub task_id: Option<String>,
    
    /// Error details
    pub error: Option<ErrorInfo>,
    
    /// Additional fields
    pub fields: HashMap<String, serde_json::Value>,
    
    /// Labels for filtering
    pub labels: HashMap<String, String>,
}

/// Error information in logs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorInfo {
    pub code: String,
    pub message: String,
    pub stack_trace: Option<Vec<String>>,
    pub cause: Option<Box<ErrorInfo>>,
}

/// Log aggregator configuration
#[derive(Debug, Clone)]
pub struct LogAggregatorConfig {
    pub batch_size: usize,
    pub flush_interval: std::time::Duration,
    pub max_buffer_size: usize,
    pub output_path: Option<String>,
    pub elasticsearch_url: Option<String>,
    pub loki_url: Option<String>,
}

impl Default for LogAggregatorConfig {
    fn default() -> Self {
        Self {
            batch_size: 100,
            flush_interval: std::time::Duration::from_secs(5),
            max_buffer_size: 10000,
            output_path: Some("/var/log/opus-gpu/aggregated.json".to_string()),
            elasticsearch_url: None,
            loki_url: None,
        }
    }
}

/// Log aggregator service
pub struct LogAggregator {
    config: LogAggregatorConfig,
    sender: mpsc::Sender<LogEntry>,
}

impl LogAggregator {
    /// Create new log aggregator
    pub async fn new(config: LogAggregatorConfig) -> Result<Self> {
        let (sender, receiver) = mpsc::channel(config.max_buffer_size);
        
        // Spawn aggregation task
        let config_clone = config.clone();
        tokio::spawn(async move {
            if let Err(e) = Self::aggregation_loop(config_clone, receiver).await {
                eprintln!("Log aggregation error: {}", e);
            }
        });
        
        Ok(Self { config, sender })
    }
    
    /// Send log entry to aggregator
    pub async fn log(&self, entry: LogEntry) -> Result<()> {
        self.sender
            .send(entry)
            .await
            .context("Failed to send log entry")
    }
    
    /// Aggregation loop
    async fn aggregation_loop(
        config: LogAggregatorConfig,
        mut receiver: mpsc::Receiver<LogEntry>,
    ) -> Result<()> {
        let mut buffer = Vec::with_capacity(config.batch_size);
        let flush_interval = tokio::time::interval(config.flush_interval);
        tokio::pin!(flush_interval);
        
        loop {
            tokio::select! {
                Some(entry) = receiver.recv() => {
                    buffer.push(entry);
                    
                    if buffer.len() >= config.batch_size {
                        Self::flush_logs(&config, &mut buffer).await?;
                    }
                }
                _ = flush_interval.tick() => {
                    if !buffer.is_empty() {
                        Self::flush_logs(&config, &mut buffer).await?;
                    }
                }
                else => break,
            }
        }
        
        // Final flush
        if !buffer.is_empty() {
            Self::flush_logs(&config, &mut buffer).await?;
        }
        
        Ok(())
    }
    
    /// Flush logs to storage
    async fn flush_logs(config: &LogAggregatorConfig, buffer: &mut Vec<LogEntry>) -> Result<()> {
        if buffer.is_empty() {
            return Ok(());
        }
        
        // Write to file if configured
        if let Some(ref path) = config.output_path {
            Self::write_to_file(path, buffer).await?;
        }
        
        // Send to Elasticsearch if configured
        if let Some(ref url) = config.elasticsearch_url {
            Self::send_to_elasticsearch(url, buffer).await?;
        }
        
        // Send to Loki if configured
        if let Some(ref url) = config.loki_url {
            Self::send_to_loki(url, buffer).await?;
        }
        
        buffer.clear();
        Ok(())
    }
    
    /// Write logs to file
    async fn write_to_file(path: &str, entries: &[LogEntry]) -> Result<()> {
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .await
            .context("Failed to open log file")?;
        
        for entry in entries {
            let json = serde_json::to_string(entry)
                .context("Failed to serialize log entry")?;
            file.write_all(json.as_bytes()).await?;
            file.write_all(b"\n").await?;
        }
        
        file.flush().await?;
        Ok(())
    }
    
    /// Send logs to Elasticsearch
    async fn send_to_elasticsearch(url: &str, entries: &[LogEntry]) -> Result<()> {
        // In real implementation, would use elasticsearch client
        // For now, just prepare the bulk request format
        let mut bulk_body = String::new();
        
        for entry in entries {
            // Index metadata
            let index_meta = serde_json::json!({
                "index": {
                    "_index": format!("opus-gpu-{}", entry.timestamp.format("%Y.%m.%d")),
                    "_type": "_doc"
                }
            });
            bulk_body.push_str(&serde_json::to_string(&index_meta)?);
            bulk_body.push('\n');
            
            // Document
            bulk_body.push_str(&serde_json::to_string(entry)?);
            bulk_body.push('\n');
        }
        
        // Would send bulk_body to Elasticsearch _bulk endpoint
        println!("Would send {} logs to Elasticsearch at {}", entries.len(), url);
        
        Ok(())
    }
    
    /// Send logs to Loki
    async fn send_to_loki(url: &str, entries: &[LogEntry]) -> Result<()> {
        // Convert to Loki stream format
        let mut streams = HashMap::new();
        
        for entry in entries {
            // Create stream key based on labels
            let mut labels = entry.labels.clone();
            labels.insert("service".to_string(), entry.service.clone());
            labels.insert("component".to_string(), entry.component.clone());
            labels.insert("level".to_string(), entry.level.to_string());
            
            let stream_key = serde_json::to_string(&labels)?;
            
            let values = streams
                .entry(stream_key.clone())
                .or_insert_with(Vec::new);
            
            // Add log line with timestamp
            values.push(vec![
                entry.timestamp.timestamp_nanos().to_string(),
                serde_json::to_string(&entry)?,
            ]);
        }
        
        // Build Loki push request
        let push_data = serde_json::json!({
            "streams": streams.into_iter().map(|(labels_json, values)| {
                let labels: HashMap<String, String> = serde_json::from_str(&labels_json).unwrap();
                serde_json::json!({
                    "stream": labels,
                    "values": values
                })
            }).collect::<Vec<_>>()
        });
        
        // Would send push_data to Loki /loki/api/v1/push endpoint
        println!("Would send {} logs to Loki at {}", entries.len(), url);
        
        Ok(())
    }
}

/// Logger builder for structured logging
pub struct LoggerBuilder {
    service: String,
    component: String,
    aggregator: Option<Arc<LogAggregator>>,
    default_fields: HashMap<String, serde_json::Value>,
    default_labels: HashMap<String, String>,
}

impl LoggerBuilder {
    pub fn new(service: impl Into<String>) -> Self {
        Self {
            service: service.into(),
            component: "default".to_string(),
            aggregator: None,
            default_fields: HashMap::new(),
            default_labels: HashMap::new(),
        }
    }
    
    pub fn component(mut self, component: impl Into<String>) -> Self {
        self.component = component.into();
        self
    }
    
    pub fn aggregator(mut self, aggregator: Arc<LogAggregator>) -> Self {
        self.aggregator = Some(aggregator);
        self
    }
    
    pub fn field(mut self, key: impl Into<String>, value: impl Serialize) -> Self {
        self.default_fields.insert(
            key.into(),
            serde_json::to_value(value).unwrap_or(serde_json::Value::Null),
        );
        self
    }
    
    pub fn label(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.default_labels.insert(key.into(), value.into());
        self
    }
    
    pub fn build(self) -> Logger {
        Logger {
            service: self.service,
            component: self.component,
            aggregator: self.aggregator,
            default_fields: self.default_fields,
            default_labels: self.default_labels,
        }
    }
}

/// Structured logger
#[derive(Clone)]
pub struct Logger {
    service: String,
    component: String,
    aggregator: Option<Arc<LogAggregator>>,
    default_fields: HashMap<String, serde_json::Value>,
    default_labels: HashMap<String, String>,
}

impl Logger {
    /// Log with specified level
    pub async fn log(&self, level: LogLevel, message: impl Into<String>) -> LogContext {
        LogContext::new(self.clone(), level, message.into())
    }
    
    /// Log trace level
    pub async fn trace(&self, message: impl Into<String>) -> LogContext {
        self.log(LogLevel::Trace, message).await
    }
    
    /// Log debug level
    pub async fn debug(&self, message: impl Into<String>) -> LogContext {
        self.log(LogLevel::Debug, message).await
    }
    
    /// Log info level
    pub async fn info(&self, message: impl Into<String>) -> LogContext {
        self.log(LogLevel::Info, message).await
    }
    
    /// Log warn level
    pub async fn warn(&self, message: impl Into<String>) -> LogContext {
        self.log(LogLevel::Warn, message).await
    }
    
    /// Log error level
    pub async fn error(&self, message: impl Into<String>) -> LogContext {
        self.log(LogLevel::Error, message).await
    }
    
    /// Log fatal level
    pub async fn fatal(&self, message: impl Into<String>) -> LogContext {
        self.log(LogLevel::Fatal, message).await
    }
}

/// Log context for adding fields
pub struct LogContext {
    logger: Logger,
    entry: LogEntry,
}

impl LogContext {
    fn new(logger: Logger, level: LogLevel, message: String) -> Self {
        let mut entry = LogEntry {
            timestamp: Utc::now(),
            level,
            service: logger.service.clone(),
            component: logger.component.clone(),
            message,
            trace_id: None,
            span_id: None,
            gpu_device_id: None,
            task_id: None,
            error: None,
            fields: logger.default_fields.clone(),
            labels: logger.default_labels.clone(),
        };
        
        Self { logger, entry }
    }
    
    pub fn trace_id(mut self, trace_id: impl Into<String>) -> Self {
        self.entry.trace_id = Some(trace_id.into());
        self
    }
    
    pub fn span_id(mut self, span_id: impl Into<String>) -> Self {
        self.entry.span_id = Some(span_id.into());
        self
    }
    
    pub fn gpu(mut self, device_id: usize) -> Self {
        self.entry.gpu_device_id = Some(device_id);
        self
    }
    
    pub fn task(mut self, task_id: impl Into<String>) -> Self {
        self.entry.task_id = Some(task_id.into());
        self
    }
    
    pub fn error_info(mut self, error: ErrorInfo) -> Self {
        self.entry.error = Some(error);
        self
    }
    
    pub fn field(mut self, key: impl Into<String>, value: impl Serialize) -> Self {
        self.entry.fields.insert(
            key.into(),
            serde_json::to_value(value).unwrap_or(serde_json::Value::Null),
        );
        self
    }
    
    pub fn label(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.entry.labels.insert(key.into(), value.into());
        self
    }
    
    /// Send the log entry
    pub async fn send(self) -> Result<()> {
        // Print to stdout as well
        println!("{}", serde_json::to_string(&self.entry)?);
        
        // Send to aggregator if configured
        if let Some(aggregator) = self.logger.aggregator {
            aggregator.log(self.entry).await?;
        }
        
        Ok(())
    }
}

/// Query builder for searching logs
pub struct LogQuery {
    pub start_time: Option<DateTime<Utc>>,
    pub end_time: Option<DateTime<Utc>>,
    pub levels: Vec<LogLevel>,
    pub services: Vec<String>,
    pub components: Vec<String>,
    pub trace_ids: Vec<String>,
    pub task_ids: Vec<String>,
    pub gpu_device_ids: Vec<usize>,
    pub labels: HashMap<String, String>,
    pub full_text_search: Option<String>,
    pub limit: usize,
}

impl Default for LogQuery {
    fn default() -> Self {
        Self {
            start_time: None,
            end_time: None,
            levels: vec![],
            services: vec![],
            components: vec![],
            trace_ids: vec![],
            task_ids: vec![],
            gpu_device_ids: vec![],
            labels: HashMap::new(),
            full_text_search: None,
            limit: 100,
        }
    }
}

impl LogQuery {
    pub fn new() -> Self {
        Self::default()
    }
    
    pub fn time_range(mut self, start: DateTime<Utc>, end: DateTime<Utc>) -> Self {
        self.start_time = Some(start);
        self.end_time = Some(end);
        self
    }
    
    pub fn level(mut self, level: LogLevel) -> Self {
        self.levels.push(level);
        self
    }
    
    pub fn service(mut self, service: impl Into<String>) -> Self {
        self.services.push(service.into());
        self
    }
    
    pub fn trace(mut self, trace_id: impl Into<String>) -> Self {
        self.trace_ids.push(trace_id.into());
        self
    }
    
    pub fn search(mut self, query: impl Into<String>) -> Self {
        self.full_text_search = Some(query.into());
        self
    }
    
    /// Convert to Elasticsearch query DSL
    pub fn to_elasticsearch_query(&self) -> serde_json::Value {
        let mut must_clauses = vec![];
        
        // Time range
        if let (Some(start), Some(end)) = (&self.start_time, &self.end_time) {
            must_clauses.push(serde_json::json!({
                "range": {
                    "timestamp": {
                        "gte": start.to_rfc3339(),
                        "lte": end.to_rfc3339()
                    }
                }
            }));
        }
        
        // Levels
        if !self.levels.is_empty() {
            must_clauses.push(serde_json::json!({
                "terms": {
                    "level": self.levels.iter().map(|l| l.to_string()).collect::<Vec<_>>()
                }
            }));
        }
        
        // Services
        if !self.services.is_empty() {
            must_clauses.push(serde_json::json!({
                "terms": {
                    "service": &self.services
                }
            }));
        }
        
        // Full text search
        if let Some(ref query) = self.full_text_search {
            must_clauses.push(serde_json::json!({
                "multi_match": {
                    "query": query,
                    "fields": ["message", "error.message"]
                }
            }));
        }
        
        serde_json::json!({
            "query": {
                "bool": {
                    "must": must_clauses
                }
            },
            "size": self.limit,
            "sort": [
                { "timestamp": { "order": "desc" } }
            ]
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_structured_logging() {
        let logger = LoggerBuilder::new("test-service")
            .component("test-component")
            .field("version", "1.0.0")
            .label("env", "test")
            .build();
        
        logger
            .info("Test message")
            .await
            .trace_id("trace-123")
            .span_id("span-456")
            .gpu(0)
            .task("task-789")
            .field("custom_field", "value")
            .label("custom_label", "label_value")
            .send()
            .await
            .unwrap();
    }
    
    #[test]
    fn test_log_query_builder() {
        let query = LogQuery::new()
            .level(LogLevel::Error)
            .service("gpu-executor")
            .search("out of memory");
        
        let es_query = query.to_elasticsearch_query();
        assert!(es_query["query"]["bool"]["must"].is_array());
    }
}
