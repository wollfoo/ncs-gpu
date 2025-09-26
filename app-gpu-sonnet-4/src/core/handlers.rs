/*!
# Event Handlers

**Event handler registry** và **routing system** cho **type-safe event processing**.

## Features

- **Dynamic handler registration** (đăng ký handler động)
- **Type-safe event routing** (định tuyến event type-safe)  
- **Error handling and recovery** (xử lý lỗi và phục hồi)
- **Handler lifecycle management** (quản lý vòng đời handler)

## Example

```rust
use app_gpu::core::{EventHandler, HandlerRegistry, GpuEvent};

let registry = HandlerRegistry::new();

registry.register_handler("gpu.optimize", |event: GpuEvent| async move {
    match event {
        GpuEvent::OptimizeProcess { pid, gpu_index, .. } => {
            println!("Optimizing PID {} on GPU {}", pid, gpu_index);
            Ok(())
        }
        _ => Ok(()),
    }
}).await?;
```
*/

use crate::core::event_types::{EventType, GpuEvent, ResourceEvent, StealtHEvent, MonitoringEvent, EventPriority};
use anyhow::{Context, Result};
use dashmap::DashMap;
use futures::future::BoxFuture;
use serde_json::Value;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use tracing::{debug, error, info, warn};

/// **Event Handler Trait** - Interface cho event processing
pub trait EventHandler: Send + Sync + 'static {
    /// **Handle event** (xử lý event)
    fn handle(&self, event_data: Value) -> BoxFuture<'static, Result<()>>;
    
    /// **Handler name** (tên handler)
    fn name(&self) -> &str;
    
    /// **Supported event types** (loại event được hỗ trợ)
    fn supported_events(&self) -> Vec<String>;
}

/// **Generic Event Handler** (handler event tổng quát)
pub struct GenericEventHandler<F>
where
    F: Fn(Value) -> BoxFuture<'static, Result<()>> + Send + Sync + 'static,
{
    name: String,
    handler_fn: F,
    supported_events: Vec<String>,
    call_count: AtomicU64,
    error_count: AtomicU64,
}

/// **Handler Registry** (sổ đăng ký handler)
pub struct HandlerRegistry {
    handlers: DashMap<String, Arc<dyn EventHandler>>,
    subject_handlers: DashMap<String, Vec<String>>,
    stats: Arc<HandlerStats>,
}

/// **Handler Statistics** (thống kê handler)
#[derive(Debug, Default)]
pub struct HandlerStats {
    pub total_handlers: AtomicU64,
    pub total_calls: AtomicU64,
    pub total_errors: AtomicU64,
    pub active_handlers: AtomicU64,
}

/// **Typed Event Handler** - Type-safe handlers cho specific events
pub trait TypedEventHandler<T>: Send + Sync + 'static
where
    T: EventType + for<'de> serde::Deserialize<'de> + Send + 'static,
{
    /// **Handle typed event** (xử lý event có kiểu)
    fn handle_typed(&self, event: T) -> BoxFuture<'static, Result<()>>;
}

impl<F> GenericEventHandler<F>
where
    F: Fn(Value) -> BoxFuture<'static, Result<()>> + Send + Sync + 'static,
{
    /// **Create new generic handler** (tạo handler tổng quát mới)
    pub fn new(
        name: String,
        handler_fn: F,
        supported_events: Vec<String>,
    ) -> Self {
        Self {
            name,
            handler_fn,
            supported_events,
            call_count: AtomicU64::new(0),
            error_count: AtomicU64::new(0),
        }
    }
    
    /// **Get call count** (lấy số lần gọi)
    pub fn call_count(&self) -> u64 {
        self.call_count.load(Ordering::Relaxed)
    }
    
    /// **Get error count** (lấy số lần lỗi)
    pub fn error_count(&self) -> u64 {
        self.error_count.load(Ordering::Relaxed)
    }
    
    /// **Get success rate** (lấy tỷ lệ thành công)
    pub fn success_rate(&self) -> f64 {
        let total = self.call_count();
        if total == 0 {
            return 1.0;
        }
        
        let errors = self.error_count();
        1.0 - (errors as f64 / total as f64)
    }
}

impl<F> EventHandler for GenericEventHandler<F>
where
    F: Fn(Value) -> BoxFuture<'static, Result<()>> + Send + Sync + 'static,
{
    fn handle(&self, event_data: Value) -> BoxFuture<'static, Result<()>> {
        self.call_count.fetch_add(1, Ordering::Relaxed);
        
        let handler_fn = &self.handler_fn;
        let error_count = &self.error_count;
        
        Box::pin(async move {
            match handler_fn(event_data).await {
                Ok(result) => Ok(result),
                Err(e) => {
                    error_count.fetch_add(1, Ordering::Relaxed);
                    Err(e)
                }
            }
        })
    }
    
    fn name(&self) -> &str {
        &self.name
    }
    
    fn supported_events(&self) -> Vec<String> {
        self.supported_events.clone()
    }
}

impl HandlerRegistry {
    /// **Create new handler registry** (tạo sổ đăng ký handler mới)
    pub fn new() -> Self {
        Self {
            handlers: DashMap::new(),
            subject_handlers: DashMap::new(),
            stats: Arc::new(HandlerStats::default()),
        }
    }
    
    /// **Register generic event handler** (đăng ký handler event tổng quát)
    pub fn register_handler<F>(
        &self,
        subject: &str,
        handler_fn: F,
    ) -> Result<()>
    where
        F: Fn(Value) -> BoxFuture<'static, Result<()>> + Send + Sync + 'static,
    {
        let handler_name = format!("handler_{}", self.handlers.len());
        let handler = GenericEventHandler::new(
            handler_name.clone(),
            handler_fn,
            vec![subject.to_string()],
        );
        
        self.handlers.insert(handler_name.clone(), Arc::new(handler));
        
        // Add to subject mapping
        let mut subject_handlers = self.subject_handlers.entry(subject.to_string())
            .or_insert_with(Vec::new);
        subject_handlers.push(handler_name);
        
        self.stats.total_handlers.fetch_add(1, Ordering::Relaxed);
        
        info!("📝 Registered event handler for subject '{}'", subject);
        Ok(())
    }
    
    /// **Register typed GPU event handler** (đăng ký handler event GPU có kiểu)
    pub fn register_gpu_handler<F>(
        &self,
        subject: &str,
        handler_fn: F,
    ) -> Result<()>
    where
        F: Fn(GpuEvent) -> BoxFuture<'static, Result<()>> + Send + Sync + 'static,
    {
        let typed_handler = move |event_data: Value| -> BoxFuture<'static, Result<()>> {
            Box::pin(async move {
                let gpu_event: GpuEvent = serde_json::from_value(event_data)
                    .context("Failed to deserialize GPU event")?;
                handler_fn(gpu_event).await
            })
        };
        
        self.register_handler(subject, typed_handler)
    }
    
    /// **Register typed resource event handler** (đăng ký handler event tài nguyên có kiểu)
    pub fn register_resource_handler<F>(
        &self,
        subject: &str,
        handler_fn: F,
    ) -> Result<()>
    where
        F: Fn(ResourceEvent) -> BoxFuture<'static, Result<()>> + Send + Sync + 'static,
    {
        let typed_handler = move |event_data: Value| -> BoxFuture<'static, Result<()>> {
            Box::pin(async move {
                let resource_event: ResourceEvent = serde_json::from_value(event_data)
                    .context("Failed to deserialize resource event")?;
                handler_fn(resource_event).await
            })
        };
        
        self.register_handler(subject, typed_handler)
    }
    
    /// **Register typed stealth event handler** (đăng ký handler event ẩn danh có kiểu)
    pub fn register_stealth_handler<F>(
        &self,
        subject: &str,
        handler_fn: F,
    ) -> Result<()>
    where
        F: Fn(StealtHEvent) -> BoxFuture<'static, Result<()>> + Send + Sync + 'static,
    {
        let typed_handler = move |event_data: Value| -> BoxFuture<'static, Result<()>> {
            Box::pin(async move {
                let stealth_event: StealtHEvent = serde_json::from_value(event_data)
                    .context("Failed to deserialize stealth event")?;
                handler_fn(stealth_event).await
            })
        };
        
        self.register_handler(subject, typed_handler)
    }
    
    /// **Register typed monitoring event handler** (đăng ký handler event giám sát có kiểu)
    pub fn register_monitoring_handler<F>(
        &self,
        subject: &str,
        handler_fn: F,
    ) -> Result<()>
    where
        F: Fn(MonitoringEvent) -> BoxFuture<'static, Result<()>> + Send + Sync + 'static,
    {
        let typed_handler = move |event_data: Value| -> BoxFuture<'static, Result<()>> {
            Box::pin(async move {
                let monitoring_event: MonitoringEvent = serde_json::from_value(event_data)
                    .context("Failed to deserialize monitoring event")?;
                handler_fn(monitoring_event).await
            })
        };
        
        self.register_handler(subject, typed_handler)
    }
    
    /// **Get handlers for subject** (lấy handlers cho subject)
    pub fn get_handlers(&self, subject: &str) -> Vec<Arc<dyn EventHandler>> {
        let mut handlers = Vec::new();
        
        // Exact match
        if let Some(handler_names) = self.subject_handlers.get(subject) {
            for handler_name in handler_names.iter() {
                if let Some(handler) = self.handlers.get(handler_name) {
                    handlers.push(Arc::clone(&handler));
                }
            }
        }
        
        // Wildcard matching (simple implementation)
        for subject_entry in self.subject_handlers.iter() {
            if subject_matches_pattern(subject, subject_entry.key()) {
                for handler_name in subject_entry.value().iter() {
                    if let Some(handler) = self.handlers.get(handler_name) {
                        handlers.push(Arc::clone(&handler));
                    }
                }
            }
        }
        
        handlers
    }
    
    /// **Handle event** (xử lý event)
    pub async fn handle_event(&self, subject: &str, event_data: Value) -> Result<()> {
        let handlers = self.get_handlers(subject);
        
        if handlers.is_empty() {
            debug!("No handlers found for subject '{}'", subject);
            return Ok(());
        }
        
        debug!("Processing {} handlers for subject '{}'", handlers.len(), subject);
        
        let mut errors = Vec::new();
        
        for handler in handlers {
            self.stats.active_handlers.fetch_add(1, Ordering::Relaxed);
            
            match handler.handle(event_data.clone()).await {
                Ok(()) => {
                    debug!("Handler '{}' processed event successfully", handler.name());
                }
                Err(e) => {
                    error!("Handler '{}' failed: {}", handler.name(), e);
                    errors.push((handler.name().to_string(), e));
                }
            }
            
            self.stats.active_handlers.fetch_sub(1, Ordering::Relaxed);
        }
        
        self.stats.total_calls.fetch_add(1, Ordering::Relaxed);
        
        if !errors.is_empty() {
            self.stats.total_errors.fetch_add(1, Ordering::Relaxed);
            warn!("Event processing had {} errors out of {} handlers", errors.len(), handlers.len());
            
            // Return first error (could be improved to aggregate errors)
            if let Some((handler_name, error)) = errors.into_iter().next() {
                return Err(anyhow::anyhow!("Handler '{}' failed: {}", handler_name, error));
            }
        }
        
        Ok(())
    }
    
    /// **Get handler statistics** (lấy thống kê handler)
    pub fn get_stats(&self) -> &HandlerStats {
        &self.stats
    }
    
    /// **List all registered handlers** (liệt kê tất cả handlers đã đăng ký)
    pub fn list_handlers(&self) -> Vec<(String, Vec<String>)> {
        let mut result = Vec::new();
        
        for handler_entry in self.handlers.iter() {
            let handler_name = handler_entry.key().clone();
            let supported_events = handler_entry.value().supported_events();
            result.push((handler_name, supported_events));
        }
        
        result
    }
    
    /// **Unregister handler** (hủy đăng ký handler)
    pub fn unregister_handler(&self, handler_name: &str) -> Result<()> {
        if let Some((_, handler)) = self.handlers.remove(handler_name) {
            // Remove from subject mappings
            for mut subject_entry in self.subject_handlers.iter_mut() {
                subject_entry.value_mut().retain(|name| name != handler_name);
            }
            
            self.stats.total_handlers.fetch_sub(1, Ordering::Relaxed);
            info!("📝 Unregistered event handler '{}'", handler_name);
            Ok(())
        } else {
            Err(anyhow::anyhow!("Handler '{}' not found", handler_name))
        }
    }
    
    /// **Clear all handlers** (xóa tất cả handlers)
    pub fn clear(&self) {
        let count = self.handlers.len();
        self.handlers.clear();
        self.subject_handlers.clear();
        self.stats.total_handlers.store(0, Ordering::Relaxed);
        info!("📝 Cleared {} event handlers", count);
    }
}

/// **Subject pattern matching** (khớp mẫu subject)
fn subject_matches_pattern(subject: &str, pattern: &str) -> bool {
    if pattern == subject {
        return true;
    }
    
    // Simple wildcard matching
    if pattern.ends_with(".>") {
        let prefix = &pattern[..pattern.len() - 2];
        return subject.starts_with(prefix);
    }
    
    if pattern.ends_with(".*") {
        let prefix = &pattern[..pattern.len() - 2];
        return subject.starts_with(prefix);
    }
    
    false
}

impl Default for HandlerRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::event_types::GpuEvent;

    #[tokio::test]
    async fn test_handler_registration() {
        let registry = HandlerRegistry::new();
        
        let result = registry.register_handler("test.subject", |_event| {
            Box::pin(async move { Ok(()) })
        });
        
        assert!(result.is_ok());
        assert_eq!(registry.handlers.len(), 1);
        assert!(registry.subject_handlers.contains_key("test.subject"));
    }
    
    #[tokio::test]
    async fn test_gpu_event_handler() {
        let registry = HandlerRegistry::new();
        
        let result = registry.register_gpu_handler("gpu.optimize", |event| {
            Box::pin(async move {
                match event {
                    GpuEvent::OptimizeProcess { pid, .. } => {
                        println!("Processing optimization for PID {}", pid);
                        Ok(())
                    }
                    _ => Ok(()),
                }
            })
        });
        
        assert!(result.is_ok());
        
        // Test event handling
        let gpu_event = GpuEvent::OptimizeProcess {
            pid: 1234,
            gpu_index: 0,
            strategies: None,
        };
        
        let event_data = serde_json::to_value(&gpu_event).unwrap();
        let handle_result = registry.handle_event("gpu.optimize", event_data).await;
        
        assert!(handle_result.is_ok());
    }
    
    #[test]
    fn test_subject_pattern_matching() {
        assert!(subject_matches_pattern("gpu.optimize", "gpu.optimize"));
        assert!(subject_matches_pattern("gpu.optimize", "gpu.>"));
        assert!(subject_matches_pattern("gpu.memory.allocate", "gpu.>"));
        assert!(!subject_matches_pattern("resource.allocate", "gpu.>"));
    }
    
    #[test]
    fn test_handler_stats() {
        let registry = HandlerRegistry::new();
        let stats = registry.get_stats();
        
        assert_eq!(stats.total_handlers.load(Ordering::Relaxed), 0);
        assert_eq!(stats.total_calls.load(Ordering::Relaxed), 0);
        assert_eq!(stats.total_errors.load(Ordering::Relaxed), 0);
    }
}
