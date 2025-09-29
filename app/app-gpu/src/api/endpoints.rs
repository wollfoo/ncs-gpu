//! API Endpoints Implementation
//!
//! **RESTful API endpoints** (Endpoint API RESTful) for mining control and monitoring

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, error};

use crate::{
    gpu_mining::{MiningEngine, ThermalManager},
    resource_manager::ResourceManager,
    common::{MetricsCollector, types::*},
};

/// **API Routes handler** (Bộ xử lý routes API)
#[derive(Clone)]
pub struct ApiRoutes {
    /// **Mining engine reference** (Tham chiếu engine đào)
    mining_engine: Arc<RwLock<MiningEngine>>,
    /// **Thermal manager** (Quản lý nhiệt)
    thermal_manager: Arc<ThermalManager>,
    /// **Resource manager** (Quản lý tài nguyên)
    resource_manager: Arc<ResourceManager>,
    /// **Metrics collector** (Thu thập metrics)
    metrics_collector: Arc<MetricsCollector>,
}

impl ApiRoutes {
    /// **Create new API routes handler** (Tạo handler routes API mới)
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
}

/// **Mining endpoint handler** (Bộ xử lý endpoint đào)
pub struct MiningEndpoint {
    mining_engine: Arc<RwLock<MiningEngine>>,
}

impl MiningEndpoint {
    /// **Create new mining endpoint** (Tạo endpoint đào mới)
    pub fn new(mining_engine: Arc<RwLock<MiningEngine>>) -> Self {
        Self { mining_engine }
    }

    /// **Start mining operation** (Khởi động hoạt động đào)
    pub async fn start_mining(&self, request: StartMiningRequest) -> Result<StartMiningResponse> {
        let mut engine = self.mining_engine.write().await;

        // **Configure mining parameters** (Cấu hình tham số đào)
        if let Some(pool_url) = request.pool_url {
            engine.set_pool_url(&pool_url).await?;
        }

        if let Some(gpu_ids) = request.gpu_ids {
            engine.set_target_gpus(gpu_ids).await?;
        }

        if let Some(threads) = request.worker_threads {
            engine.set_worker_threads(threads).await?;
        }

        // **Start mining** (Bắt đầu đào)
        engine.start().await?;

        info!("Mining started via API");

        Ok(StartMiningResponse {
            success: true,
            message: "Mining started successfully".to_string(),
            active_devices: engine.get_active_device_count().await,
        })
    }

    /// **Stop mining operation** (Dừng hoạt động đào)
    pub async fn stop_mining(&self) -> Result<StopMiningResponse> {
        let mut engine = self.mining_engine.write().await;
        engine.stop().await?;

        info!("Mining stopped via API");

        Ok(StopMiningResponse {
            success: true,
            message: "Mining stopped successfully".to_string(),
        })
    }

    /// **Get mining status** (Lấy trạng thái đào)
    pub async fn get_status(&self) -> Result<MiningStatusResponse> {
        let engine = self.mining_engine.read().await;
        let stats = engine.get_stats().await?;

        Ok(MiningStatusResponse {
            status: engine.get_status().await,
            total_hashrate: stats.total_hashrate,
            active_devices: engine.get_active_device_count().await,
            uptime_seconds: stats.uptime_seconds,
            total_shares: stats.accepted_shares + stats.rejected_shares,
            accepted_shares: stats.accepted_shares,
            rejected_shares: stats.rejected_shares,
        })
    }

    /// **Get device statistics** (Lấy thống kê thiết bị)
    pub async fn get_device_stats(&self) -> Result<Vec<DeviceStatsResponse>> {
        let engine = self.mining_engine.read().await;
        let device_stats = engine.get_device_stats().await?;

        let mut response = Vec::new();
        for (device_id, stats) in device_stats {
            response.push(DeviceStatsResponse {
                device_id,
                hashrate: stats.current_hash_rate,
                temperature: stats.temperature,
                power_usage: stats.power_usage,
                memory_usage: stats.memory_utilization,
                gpu_usage: stats.gpu_utilization,
                fan_speed: stats.fan_speed,
                errors: stats.errors,
            });
        }

        Ok(response)
    }
}

/// **Metrics endpoint handler** (Bộ xử lý endpoint metrics)
pub struct MetricsEndpoint {
    metrics_collector: Arc<MetricsCollector>,
    resource_manager: Arc<ResourceManager>,
}

impl MetricsEndpoint {
    /// **Create new metrics endpoint** (Tạo endpoint metrics mới)
    pub fn new(
        metrics_collector: Arc<MetricsCollector>,
        resource_manager: Arc<ResourceManager>,
    ) -> Self {
        Self {
            metrics_collector,
            resource_manager,
        }
    }

    /// **Get system metrics** (Lấy metrics hệ thống)
    pub async fn get_system_metrics(&self) -> Result<SystemMetricsResponse> {
        let system_stats = self.resource_manager.get_system_stats().await?;
        let performance_metrics = self.metrics_collector.get_performance_metrics().await;

        Ok(SystemMetricsResponse {
            cpu_usage: system_stats.cpu_usage,
            memory_usage: system_stats.memory_usage,
            gpu_usage: system_stats.gpu_usage,
            total_hashrate: system_stats.total_hashrate,
            total_power: system_stats.total_power,
            average_temperature: system_stats.average_temperature,
            active_workers: system_stats.active_workers,
            uptime_seconds: system_stats.uptime_seconds,
            network_stats: performance_metrics.network_stats,
            timestamp: chrono::Utc::now(),
        })
    }

    /// **Get performance history** (Lấy lịch sử hiệu suất)
    pub async fn get_performance_history(&self, duration_hours: u32) -> Result<PerformanceHistoryResponse> {
        let history = self.metrics_collector
            .get_performance_history(duration_hours)
            .await?;

        Ok(PerformanceHistoryResponse {
            duration_hours,
            data_points: history.len(),
            history,
        })
    }
}

/// **Thermal endpoint handler** (Bộ xử lý endpoint nhiệt)
pub struct ThermalEndpoint {
    thermal_manager: Arc<ThermalManager>,
}

impl ThermalEndpoint {
    /// **Create new thermal endpoint** (Tạo endpoint nhiệt mới)
    pub fn new(thermal_manager: Arc<ThermalManager>) -> Self {
        Self { thermal_manager }
    }

    /// **Get thermal status** (Lấy trạng thái nhiệt)
    pub async fn get_thermal_status(&self) -> Result<ThermalStatusResponse> {
        let thermal_status = self.thermal_manager.get_thermal_status().await?;

        Ok(ThermalStatusResponse {
            overall_status: thermal_status.overall_status,
            devices: thermal_status.device_temperatures
                .into_iter()
                .map(|(device_id, temp)| DeviceThermalStatus {
                    device_id,
                    temperature: temp,
                    status: if temp > 85.0 { ThermalLevel::Critical }
                           else if temp > 75.0 { ThermalLevel::Warning }
                           else { ThermalLevel::Normal },
                    fan_speed: thermal_status.fan_speeds.get(&device_id).copied().unwrap_or(0.0),
                })
                .collect(),
        })
    }

    /// **Get thermal alerts** (Lấy cảnh báo nhiệt)
    pub async fn get_thermal_alerts(&self) -> Result<Vec<ThermalAlert>> {
        self.thermal_manager.get_recent_alerts(100).await
    }
}

// **Request/Response Types** (Kiểu Request/Response)

/// **Start mining request** (Yêu cầu bắt đầu đào)
#[derive(Debug, Deserialize)]
pub struct StartMiningRequest {
    /// **Mining pool URL** (URL pool đào)
    pub pool_url: Option<String>,
    /// **Target GPU device IDs** (ID thiết bị GPU mục tiêu)
    pub gpu_ids: Option<Vec<GpuId>>,
    /// **Number of worker threads** (Số luồng worker)
    pub worker_threads: Option<usize>,
    /// **Mining intensity** (Cường độ đào)
    pub intensity: Option<u8>,
}

/// **Start mining response** (Phản hồi bắt đầu đào)
#[derive(Debug, Serialize)]
pub struct StartMiningResponse {
    /// **Success status** (Trạng thái thành công)
    pub success: bool,
    /// **Response message** (Thông báo phản hồi)
    pub message: String,
    /// **Number of active devices** (Số thiết bị đang hoạt động)
    pub active_devices: u32,
}

/// **Stop mining response** (Phản hồi dừng đào)
#[derive(Debug, Serialize)]
pub struct StopMiningResponse {
    /// **Success status** (Trạng thái thành công)
    pub success: bool,
    /// **Response message** (Thông báo phản hồi)
    pub message: String,
}

/// **Mining status response** (Phản hồi trạng thái đào)
#[derive(Debug, Serialize)]
pub struct MiningStatusResponse {
    /// **Current mining status** (Trạng thái đào hiện tại)
    pub status: String,
    /// **Total hashrate** (Tổng tốc độ hash)
    pub total_hashrate: HashRate,
    /// **Active devices count** (Số thiết bị đang hoạt động)
    pub active_devices: u32,
    /// **Uptime in seconds** (Thời gian hoạt động bằng giây)
    pub uptime_seconds: u64,
    /// **Total shares** (Tổng share)
    pub total_shares: u64,
    /// **Accepted shares** (Share được chấp nhận)
    pub accepted_shares: u64,
    /// **Rejected shares** (Share bị từ chối)
    pub rejected_shares: u64,
}

/// **Device statistics response** (Phản hồi thống kê thiết bị)
#[derive(Debug, Serialize)]
pub struct DeviceStatsResponse {
    /// **Device ID** (ID thiết bị)
    pub device_id: GpuId,
    /// **Current hashrate** (Tốc độ hash hiện tại)
    pub hashrate: HashRate,
    /// **Temperature** (Nhiệt độ)
    pub temperature: Temperature,
    /// **Power usage** (Tiêu thụ điện)
    pub power_usage: PowerUsage,
    /// **Memory usage** (Sử dụng bộ nhớ)
    pub memory_usage: f32,
    /// **GPU usage** (Sử dụng GPU)
    pub gpu_usage: f32,
    /// **Fan speed** (Tốc độ quạt)
    pub fan_speed: f32,
    /// **Error count** (Số lỗi)
    pub errors: u64,
}

/// **System metrics response** (Phản hồi metrics hệ thống)
#[derive(Debug, Serialize)]
pub struct SystemMetricsResponse {
    /// **CPU usage** (Sử dụng CPU)
    pub cpu_usage: f32,
    /// **Memory usage** (Sử dụng bộ nhớ)
    pub memory_usage: f32,
    /// **GPU usage** (Sử dụng GPU)
    pub gpu_usage: f32,
    /// **Total hashrate** (Tổng tốc độ hash)
    pub total_hashrate: HashRate,
    /// **Total power** (Tổng điện năng)
    pub total_power: PowerUsage,
    /// **Average temperature** (Nhiệt độ trung bình)
    pub average_temperature: Temperature,
    /// **Active workers** (Worker đang hoạt động)
    pub active_workers: usize,
    /// **Uptime** (Thời gian hoạt động)
    pub uptime_seconds: u64,
    /// **Network statistics** (Thống kê mạng)
    pub network_stats: NetworkStats,
    /// **Timestamp** (Dấu thời gian)
    pub timestamp: Timestamp,
}

/// **Performance history response** (Phản hồi lịch sử hiệu suất)
#[derive(Debug, Serialize)]
pub struct PerformanceHistoryResponse {
    /// **Duration in hours** (Thời lượng bằng giờ)
    pub duration_hours: u32,
    /// **Number of data points** (Số điểm dữ liệu)
    pub data_points: usize,
    /// **Historical data** (Dữ liệu lịch sử)
    pub history: Vec<SystemStats>,
}

/// **Thermal status response** (Phản hồi trạng thái nhiệt)
#[derive(Debug, Serialize)]
pub struct ThermalStatusResponse {
    /// **Overall thermal status** (Trạng thái nhiệt tổng thể)
    pub overall_status: ThermalLevel,
    /// **Device thermal status** (Trạng thái nhiệt thiết bị)
    pub devices: Vec<DeviceThermalStatus>,
}

/// **Device thermal status** (Trạng thái nhiệt thiết bị)
#[derive(Debug, Serialize)]
pub struct DeviceThermalStatus {
    /// **Device ID** (ID thiết bị)
    pub device_id: GpuId,
    /// **Current temperature** (Nhiệt độ hiện tại)
    pub temperature: Temperature,
    /// **Thermal status** (Trạng thái nhiệt)
    pub status: ThermalLevel,
    /// **Fan speed** (Tốc độ quạt)
    pub fan_speed: f32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_start_mining_request_deserialization() {
        let json = r#"{
            "pool_url": "stratum+tcp://test.pool.com:4444",
            "gpu_ids": [0, 1],
            "worker_threads": 4
        }"#;

        let request: StartMiningRequest = serde_json::from_str(json).unwrap();
        assert_eq!(request.pool_url, Some("stratum+tcp://test.pool.com:4444".to_string()));
        assert_eq!(request.gpu_ids, Some(vec![0, 1]));
        assert_eq!(request.worker_threads, Some(4));
    }

    #[test]
    fn test_mining_status_response_serialization() {
        let response = MiningStatusResponse {
            status: "Running".to_string(),
            total_hashrate: 1500.0,
            active_devices: 2,
            uptime_seconds: 3600,
            total_shares: 100,
            accepted_shares: 95,
            rejected_shares: 5,
        };

        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("Running"));
        assert!(json.contains("1500"));
    }
}