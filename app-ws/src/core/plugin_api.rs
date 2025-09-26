//! **Plugin API** (API plugin – giao diện module mở rộng)

use anyhow::Result;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::any::Any;
use std::sync::Arc;

use crate::core::{gpu_pool::GpuPool, scheduler::Scheduler};
use crate::utils::config::Config;

/// **Plugin Information** (thông tin plugin – chi tiết module mở rộng)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginInfo {
    /// Plugin name
    pub name: String,
    /// Plugin version
    pub version: String,
    /// Plugin description
    pub description: String,
    /// Plugin author
    pub author: String,
    /// Plugin capabilities
    pub capabilities: Vec<String>,
}

/// **Plugin Context** (ngữ cảnh plugin – môi trường hoạt động module)
pub struct PluginContext {
    /// GPU pool access
    pub gpu_pool: Arc<GpuPool>,
    /// Scheduler access
    pub scheduler: Arc<Scheduler>,
    /// Configuration
    pub config: Arc<Config>,
}

/// **Plugin Trait** (đặc điểm plugin – giao diện module mở rộng)
#[async_trait]
pub trait Plugin: Send + Sync {
    /// **Get plugin information** (lấy thông tin plugin – xem chi tiết module)
    fn info(&self) -> PluginInfo;

    /// **Initialize plugin** (khởi tạo plugin – chuẩn bị module)
    async fn initialize(&self, context: Arc<PluginContext>) -> Result<()>;

    /// **Start plugin** (khởi động plugin – chạy module)
    async fn start(&self) -> Result<()> {
        Ok(())
    }

    /// **Stop plugin** (dừng plugin – tắt module)
    async fn stop(&self) -> Result<()> {
        Ok(())
    }

    /// **Shutdown plugin** (tắt plugin – kết thúc module)
    async fn shutdown(&self) -> Result<()> {
        Ok(())
    }

    /// **Handle custom command** (xử lý lệnh tùy chỉnh – thực thi yêu cầu riêng)
    async fn handle_command(&self, command: &str, args: &[u8]) -> Result<Vec<u8>> {
        Err(anyhow::anyhow!("Command not supported: {}", command))
    }

    /// **Get plugin metrics** (lấy chỉ số plugin – xem thông số module)
    async fn metrics(&self) -> Result<serde_json::Value> {
        Ok(serde_json::json!({}))
    }

    /// **As any for downcasting** (chuyển đổi kiểu – ép kiểu động)
    fn as_any(&self) -> &dyn Any;
}

/// **Plugin Loader Trait** (đặc điểm tải plugin – giao diện nạp module)
#[async_trait]
pub trait PluginLoader: Send + Sync {
    /// **Load plugin from path** (tải plugin từ đường dẫn – nạp module từ file)
    async fn load(&self, path: &std::path::Path) -> Result<Box<dyn Plugin>>;

    /// **Unload plugin** (gỡ plugin – hủy nạp module)
    async fn unload(&self, plugin: Box<dyn Plugin>) -> Result<()>;
}

/// **Plugin Event** (sự kiện plugin – thông báo từ module)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PluginEvent {
    /// Plugin started
    Started { plugin: String },
    /// Plugin stopped
    Stopped { plugin: String },
    /// Plugin error
    Error { plugin: String, error: String },
    /// Plugin metric update
    MetricUpdate { plugin: String, metrics: serde_json::Value },
    /// Custom event
    Custom { plugin: String, event: String, data: serde_json::Value },
}

/// **Plugin Manager Trait** (đặc điểm quản lý plugin – giao diện điều khiển module)
#[async_trait]
pub trait PluginManager: Send + Sync {
    /// **Register plugin** (đăng ký plugin – thêm module mới)
    async fn register(&self, plugin: Box<dyn Plugin>) -> Result<()>;

    /// **Unregister plugin** (hủy đăng ký plugin – gỡ module)
    async fn unregister(&self, name: &str) -> Result<()>;

    /// **Get plugin by name** (lấy plugin theo tên – tìm module)
    async fn get(&self, name: &str) -> Option<Arc<dyn Plugin>>;

    /// **List all plugins** (liệt kê tất cả plugin – danh sách module)
    async fn list(&self) -> Vec<PluginInfo>;

    /// **Send command to plugin** (gửi lệnh tới plugin – điều khiển module)
    async fn send_command(&self, plugin: &str, command: &str, args: &[u8]) -> Result<Vec<u8>>;
}

/// **Plugin Priority** (độ ưu tiên plugin – thứ tự module)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum PluginPriority {
    /// Critical priority
    Critical = 0,
    /// High priority
    High = 1,
    /// Normal priority
    Normal = 2,
    /// Low priority
    Low = 3,
}

/// **Plugin State** (trạng thái plugin – tình trạng module)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PluginState {
    /// Not initialized
    Uninitialized,
    /// Initializing
    Initializing,
    /// Initialized
    Initialized,
    /// Starting
    Starting,
    /// Running
    Running,
    /// Stopping
    Stopping,
    /// Stopped
    Stopped,
    /// Error state
    Error,
}