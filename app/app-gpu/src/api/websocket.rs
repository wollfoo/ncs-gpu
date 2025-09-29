//! WebSocket Handler for Real-time Communication
//!
//! **Real-time streaming** (Streaming thời gian thực) of mining metrics and alerts

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, error, debug};

use crate::{
    gpu_mining::{MiningEngine, ThermalManager},
    resource_manager::ResourceManager,
    common::{MetricsCollector, types::*},
};

/// **WebSocket message handler** (Bộ xử lý tin nhắn WebSocket)
#[derive(Clone)]
pub struct WebSocketHandler {
    /// **Mining engine reference** (Tham chiếu engine đào)
    mining_engine: Arc<RwLock<MiningEngine>>,
    /// **Thermal manager** (Quản lý nhiệt)
    thermal_manager: Arc<ThermalManager>,
    /// **Resource manager** (Quản lý tài nguyên)
    resource_manager: Arc<ResourceManager>,
    /// **Metrics collector** (Thu thập metrics)
    metrics_collector: Arc<MetricsCollector>,
}

impl WebSocketHandler {
    /// **Create new WebSocket handler** (Tạo handler WebSocket mới)
    pub fn new(
        mining_engine: Arc<RwLock<MiningEngine>>,
        thermal_manager: Arc<ThermalManager>,
        resource_manager: Arc<ResourceManager>,
        metrics_collector: Arc<MetricsCollector>,
    ) -> Self {
        Self {
            mining_engine,
            thermal_manager,
            resource_manager,
            metrics_collector,
        }
    }

    /// **Handle incoming WebSocket message** (Xử lý tin nhắn WebSocket đến)
    pub async fn handle_message(&self, message: &str) -> Result<String> {
        debug!("Received WebSocket message: {}", message);

        // **Parse incoming message** (Phân tích tin nhắn đến)
        let request: WebSocketMessage = serde_json::from_str(message)
            .context("Failed to parse WebSocket message")?;

        // **Process message based on type** (Xử lý tin nhắn dựa trên loại)
        let response = match request.message_type.as_str() {
            "subscribe" => self.handle_subscribe(request.data).await?,
            "unsubscribe" => self.handle_unsubscribe(request.data).await?,
            "get_status" => self.handle_get_status().await?,
            "get_metrics" => self.handle_get_metrics().await?,
            "get_devices" => self.handle_get_devices().await?,
            "get_thermal" => self.handle_get_thermal().await?,
            "start_mining" => self.handle_start_mining(request.data).await?,
            "stop_mining" => self.handle_stop_mining().await?,
            "ping" => self.handle_ping().await?,
            _ => {
                return Err(anyhow::anyhow!(
                    "Unknown message type: {}",
                    request.message_type
                ));
            }
        };

        // **Serialize response** (Tuần tự hóa phản hồi)
        serde_json::to_string(&response)
            .context("Failed to serialize WebSocket response")
    }

    /// **Handle subscription request** (Xử lý yêu cầu đăng ký)
    async fn handle_subscribe(&self, data: Option<serde_json::Value>) -> Result<WebSocketResponse> {
        let subscription_type = data
            .and_then(|d| d.get("type"))
            .and_then(|t| t.as_str())
            .unwrap_or("metrics");

        info!("Client subscribed to: {}", subscription_type);

        Ok(WebSocketResponse {
            message_type: "subscription_confirmed".to_string(),
            success: true,
            data: Some(serde_json::json!({
                "subscription_type": subscription_type,
                "message": "Subscription confirmed"
            })),
            error: None,
            timestamp: chrono::Utc::now(),
        })
    }

    /// **Handle unsubscription request** (Xử lý yêu cầu hủy đăng ký)
    async fn handle_unsubscribe(&self, data: Option<serde_json::Value>) -> Result<WebSocketResponse> {
        let subscription_type = data
            .and_then(|d| d.get("type"))
            .and_then(|t| t.as_str())
            .unwrap_or("metrics");

        info!("Client unsubscribed from: {}", subscription_type);

        Ok(WebSocketResponse {
            message_type: "unsubscription_confirmed".to_string(),
            success: true,
            data: Some(serde_json::json!({
                "subscription_type": subscription_type,
                "message": "Unsubscription confirmed"
            })),
            error: None,
            timestamp: chrono::Utc::now(),
        })
    }

    /// **Handle status request** (Xử lý yêu cầu trạng thái)
    async fn handle_get_status(&self) -> Result<WebSocketResponse> {
        let engine = self.mining_engine.read().await;
        let stats = engine.get_stats().await?;

        let status_data = serde_json::json!({
            "status": engine.get_status().await,
            "total_hashrate": stats.total_hashrate,
            "active_devices": engine.get_active_device_count().await,
            "uptime_seconds": stats.uptime_seconds,
            "accepted_shares": stats.accepted_shares,
            "rejected_shares": stats.rejected_shares,
        });

        Ok(WebSocketResponse {
            message_type: "status".to_string(),
            success: true,
            data: Some(status_data),
            error: None,
            timestamp: chrono::Utc::now(),
        })
    }

    /// **Handle metrics request** (Xử lý yêu cầu metrics)
    async fn handle_get_metrics(&self) -> Result<WebSocketResponse> {
        let system_stats = self.resource_manager.get_system_stats().await?;
        let performance_metrics = self.metrics_collector.get_performance_metrics().await;

        let metrics_data = serde_json::json!({
            "cpu_usage": system_stats.cpu_usage,
            "memory_usage": system_stats.memory_usage,
            "gpu_usage": system_stats.gpu_usage,
            "total_hashrate": system_stats.total_hashrate,
            "total_power": system_stats.total_power,
            "average_temperature": system_stats.average_temperature,
            "active_workers": system_stats.active_workers,
            "network_stats": performance_metrics.network_stats,
        });

        Ok(WebSocketResponse {
            message_type: "metrics".to_string(),
            success: true,
            data: Some(metrics_data),
            error: None,
            timestamp: chrono::Utc::now(),
        })
    }

    /// **Handle devices request** (Xử lý yêu cầu thiết bị)
    async fn handle_get_devices(&self) -> Result<WebSocketResponse> {
        let engine = self.mining_engine.read().await;
        let device_stats = engine.get_device_stats().await?;

        let devices_data: Vec<_> = device_stats
            .into_iter()
            .map(|(device_id, stats)| {
                serde_json::json!({
                    "device_id": device_id,
                    "hashrate": stats.current_hash_rate,
                    "temperature": stats.temperature,
                    "power_usage": stats.power_usage,
                    "memory_usage": stats.memory_utilization,
                    "gpu_usage": stats.gpu_utilization,
                    "fan_speed": stats.fan_speed,
                    "errors": stats.errors,
                })
            })
            .collect();

        Ok(WebSocketResponse {
            message_type: "devices".to_string(),
            success: true,
            data: Some(serde_json::json!({ "devices": devices_data })),
            error: None,
            timestamp: chrono::Utc::now(),
        })
    }

    /// **Handle thermal request** (Xử lý yêu cầu nhiệt)
    async fn handle_get_thermal(&self) -> Result<WebSocketResponse> {
        let thermal_status = self.thermal_manager.get_thermal_status().await?;

        let thermal_data = serde_json::json!({
            "overall_status": thermal_status.overall_status,
            "devices": thermal_status.device_temperatures
                .into_iter()
                .map(|(device_id, temp)| {
                    serde_json::json!({
                        "device_id": device_id,
                        "temperature": temp,
                        "status": if temp > 85.0 { "Critical" }
                                 else if temp > 75.0 { "Warning" }
                                 else { "Normal" },
                        "fan_speed": thermal_status.fan_speeds.get(&device_id).copied().unwrap_or(0.0),
                    })
                })
                .collect::<Vec<_>>(),
        });

        Ok(WebSocketResponse {
            message_type: "thermal".to_string(),
            success: true,
            data: Some(thermal_data),
            error: None,
            timestamp: chrono::Utc::now(),
        })
    }

    /// **Handle start mining request** (Xử lý yêu cầu bắt đầu đào)
    async fn handle_start_mining(&self, data: Option<serde_json::Value>) -> Result<WebSocketResponse> {
        let mut engine = self.mining_engine.write().await;

        // **Extract parameters from data** (Trích xuất tham số từ dữ liệu)
        if let Some(data) = data {
            if let Some(pool_url) = data.get("pool_url").and_then(|v| v.as_str()) {
                engine.set_pool_url(pool_url).await?;
            }

            if let Some(gpu_ids_array) = data.get("gpu_ids").and_then(|v| v.as_array()) {
                let gpu_ids: Result<Vec<u32>, _> = gpu_ids_array
                    .iter()
                    .map(|v| v.as_u64().map(|n| n as u32).ok_or("Invalid GPU ID"))
                    .collect();

                if let Ok(ids) = gpu_ids {
                    engine.set_target_gpus(ids).await?;
                }
            }

            if let Some(threads) = data.get("worker_threads").and_then(|v| v.as_u64()) {
                engine.set_worker_threads(threads as usize).await?;
            }
        }

        // **Start mining** (Bắt đầu đào)
        engine.start().await?;

        info!("Mining started via WebSocket");

        Ok(WebSocketResponse {
            message_type: "mining_started".to_string(),
            success: true,
            data: Some(serde_json::json!({
                "message": "Mining started successfully",
                "active_devices": engine.get_active_device_count().await,
            })),
            error: None,
            timestamp: chrono::Utc::now(),
        })
    }

    /// **Handle stop mining request** (Xử lý yêu cầu dừng đào)
    async fn handle_stop_mining(&self) -> Result<WebSocketResponse> {
        let mut engine = self.mining_engine.write().await;
        engine.stop().await?;

        info!("Mining stopped via WebSocket");

        Ok(WebSocketResponse {
            message_type: "mining_stopped".to_string(),
            success: true,
            data: Some(serde_json::json!({
                "message": "Mining stopped successfully"
            })),
            error: None,
            timestamp: chrono::Utc::now(),
        })
    }

    /// **Handle ping request** (Xử lý yêu cầu ping)
    async fn handle_ping(&self) -> Result<WebSocketResponse> {
        Ok(WebSocketResponse {
            message_type: "pong".to_string(),
            success: true,
            data: Some(serde_json::json!({
                "message": "pong",
                "server_time": chrono::Utc::now(),
            })),
            error: None,
            timestamp: chrono::Utc::now(),
        })
    }

    /// **Send real-time update** (Gửi cập nhật thời gian thực)
    pub async fn send_realtime_update(&self, update_type: &str) -> Result<String> {
        let response = match update_type {
            "metrics" => self.handle_get_metrics().await?,
            "status" => self.handle_get_status().await?,
            "devices" => self.handle_get_devices().await?,
            "thermal" => self.handle_get_thermal().await?,
            _ => {
                return Err(anyhow::anyhow!("Unknown update type: {}", update_type));
            }
        };

        // **Add update type to response** (Thêm loại cập nhật vào phản hồi)
        let mut response_json = serde_json::to_value(&response)?;
        response_json["update_type"] = serde_json::Value::String(update_type.to_string());

        serde_json::to_string(&response_json)
            .context("Failed to serialize real-time update")
    }
}

/// **WebSocket message structure** (Cấu trúc tin nhắn WebSocket)
#[derive(Debug, Deserialize)]
pub struct WebSocketMessage {
    /// **Message type** (Loại tin nhắn)
    pub message_type: String,
    /// **Optional data payload** (Dữ liệu tùy chọn)
    pub data: Option<serde_json::Value>,
    /// **Client timestamp** (Thời điểm từ client)
    pub timestamp: Option<Timestamp>,
}

/// **WebSocket response structure** (Cấu trúc phản hồi WebSocket)
#[derive(Debug, Serialize)]
pub struct WebSocketResponse {
    /// **Response message type** (Loại tin nhắn phản hồi)
    pub message_type: String,
    /// **Success status** (Trạng thái thành công)
    pub success: bool,
    /// **Response data** (Dữ liệu phản hồi)
    pub data: Option<serde_json::Value>,
    /// **Error message** (Thông báo lỗi) if any
    pub error: Option<String>,
    /// **Server timestamp** (Thời điểm từ server)
    pub timestamp: Timestamp,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_websocket_message_parsing() {
        let json = r#"{
            "message_type": "get_status",
            "data": null,
            "timestamp": "2024-01-01T00:00:00Z"
        }"#;

        let message: WebSocketMessage = serde_json::from_str(json).unwrap();
        assert_eq!(message.message_type, "get_status");
        assert!(message.data.is_none());
    }

    #[test]
    fn test_websocket_response_serialization() {
        let response = WebSocketResponse {
            message_type: "status".to_string(),
            success: true,
            data: Some(serde_json::json!({
                "status": "Running",
                "hashrate": 1500.0
            })),
            error: None,
            timestamp: chrono::Utc::now(),
        };

        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("status"));
        assert!(json.contains("Running"));
    }

    #[test]
    fn test_subscription_message_parsing() {
        let json = r#"{
            "message_type": "subscribe",
            "data": {
                "type": "metrics",
                "interval": 5
            }
        }"#;

        let message: WebSocketMessage = serde_json::from_str(json).unwrap();
        assert_eq!(message.message_type, "subscribe");

        let data = message.data.unwrap();
        assert_eq!(data["type"], "metrics");
        assert_eq!(data["interval"], 5);
    }
}