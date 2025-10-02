//! # Mining Statistics Module (Module thống kê khai thác)
//!
//! **Comprehensive performance tracking** (theo dõi hiệu năng toàn diện)
//! với real-time metrics, hashrate calculation, efficiency monitoring
//! và historical data analysis cho mining operations.
//!
//! ## Key Features (Tính năng chính)
//!
//! - **Real-time Hashrate**: Per-GPU và aggregate hashrate calculation - Tính toán hashrate theo thời gian thực
//! - **Work Efficiency**: Share acceptance rates và mining efficiency - Tỷ lệ chấp nhận share và hiệu quả
//! - **GPU Health**: Temperature, utilization, memory usage monitoring - Giám sát sức khỏe GPU
//! - **Pool Performance**: Network latency, submission latency tracking - Theo dõi hiệu năng pool
//! - **Historical Analysis**: Trend analysis và performance forecasting - Phân tích xu hướng lịch sử
//!
//! ## Metrics Overview (Tổng quan metrics)
//!
//! ```
//! MiningStatistics
//! ├── Global Metrics: hashrate, efficiency, uptime
//! ├── Worker Metrics: per-GPU stats, thermal data
//! ├── Pool Metrics: submission rates, latency
//! └── System Health: resource usage, error rates
//! ```
//!
//! ## Architecture (Kiến trúc)
//!
//! ```rust,ignore
//! StatisticsAggregator ──┬──► Time-Series Database (optional)
//!                        │
//!                        ├──► Real-time Monitoring UI
//!                        │
//!                        └──► Alert System (threshold breaches)
//! ```

use std::collections::VecDeque;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime};

use serde::{Deserialize, Serialize};
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

/// **StatisticsConfig** (cấu hình thống kê) – configuration cho statistics collection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StatisticsConfig {
    /// **Update interval** (khoảng cập nhật) – seconds giữa updates
    pub update_interval_secs: u64,

    /// **History retention** (giữ lịch sử) – minutes giữ historical data
    pub history_retention_minutes: u64,

    /// **Enable GPU monitoring** (bật giám sát GPU)
    pub enable_gpu_monitoring: bool,

    /// **Alert thresholds** (ngưỡng cảnh báo)
    pub alert_thresholds: AlertThresholds,
}

impl Default for StatisticsConfig {
    fn default() -> Self {
        Self {
            update_interval_secs: 5,
            history_retention_minutes: 60,
            enable_gpu_monitoring: true,
            alert_thresholds: AlertThresholds::default(),
        }
    }
}

/// **AlertThresholds** (ngưỡng cảnh báo) – thresholds for alerts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertThresholds {
    /// **GPU temperature threshold** (ngưỡng nhiệt độ GPU) – °C
    pub gpu_temp_threshold: f32,

    /// **GPU utilization threshold** (ngưỡng sử dụng GPU) – percentage
    pub gpu_util_threshold: f32,

    /// **Share rejection threshold** (ngưỡng từ chối share) – percentage
    pub share_reject_threshold: f32,

    /// **Hashrate drop threshold** (ngưỡng giảm hashrate) – percentage
    pub hashrate_drop_threshold: f32,
}

impl Default for AlertThresholds {
    fn default() -> Self {
        Self {
            gpu_temp_threshold: 85.0,
            gpu_util_threshold: 95.0,
            share_reject_threshold: 10.0,
            hashrate_drop_threshold: 20.0,
        }
    }
}

/// **MetricsBackend** (backend metrics) – storage backend cho metrics
#[derive(Debug, Clone)]
pub enum MetricsBackend {
    /// **In-memory** (trong bộ nhớ) – basic storage
    Memory,
    /// **Time-series database** (cơ sở dữ liệu chuỗi thời gian)
    TimeSeries,
}

/// **GpuMetrics** (metrics GPU) – comprehensive GPU performance data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuMetrics {
    /// **Device ID** (ID thiết bị)
    pub device_id: usize,

    /// **Temperature** (nhiệt độ) – current °C
    pub temperature: f32,

    /// **Utilization** (sử dụng) – GPU utilization percentage (0-100)
    pub utilization: f32,

    /// **Memory usage** (sử dụng bộ nhớ) – MB used
    pub memory_used_mb: u64,

    /// **Memory total** (tổng bộ nhớ) – MB total
    pub memory_total_mb: u64,

    /// **Fan speed** (tốc độ quạt) – percentage (0-100)
    pub fan_speed: Option<f32>,

    /// **Power usage** (sử dụng điện) – watts
    pub power_watts: Option<f32>,

    /// **Hashrate** (hashrate) – MH/s
    pub hashrate_mh: f64,

    /// **Timestamp** (thời điểm) – when metrics captured
    pub timestamp: SystemTime,
}

impl Default for GpuMetrics {
    fn default() -> Self {
        Self {
            device_id: 0,
            temperature: 0.0,
            utilization: 0.0,
            memory_used_mb: 0,
            memory_total_mb: 0,
            fan_speed: None,
            power_watts: None,
            hashrate_mh: 0.0,
            timestamp: SystemTime::now(),
        }
    }
}

impl GpuMetrics {
    /// **Calculate memory utilization** (tính sử dụng bộ nhớ) – percentage
    pub fn memory_utilization(&self) -> f32 {
        if self.memory_total_mb > 0 {
            (self.memory_used_mb as f32 / self.memory_total_mb as f32) * 100.0
        } else {
            0.0
        }
    }

    /// **Check if overheating** (kiểm tra quá nhiệt)
    pub fn is_overheating(&self, threshold: f32) -> bool {
        self.temperature > threshold
    }

    /// **Check if over-utilized** (kiểm tra quá tải)
    pub fn is_over_utilized(&self, threshold: f32) -> bool {
        self.utilization > threshold
    }
}

/// **WorkerStats** (thống kê worker) – per-worker performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerStats {
    /// **Device ID** (ID thiết bị)
    pub device_id: usize,

    /// **Hashes computed** (hash tính toán được) – total hashes in current window
    pub hashes_computed: u64,

    /// **Shares submitted** (share nộp) – total shares submitted
    pub shares_submitted: u64,

    /// **Shares accepted** (share chấp nhận) – accepted shares
    pub shares_accepted: u64,

    /// **Shares rejected** (share từ chối) – rejected shares
    pub shares_stale: u64,

    /// **Kernel launches** (kernel khởi động) – number of kernel launches
    pub kernel_launches: u64,

    /// **Average nonce range** (phạm vi nonce trung bình) – nonces per work unit
    pub avg_nonce_range: u64,

    /// **Last work timestamp** (thời điểm công việc cuối) – last work processed
    pub last_work_time: Option<SystemTime>,
}

impl Default for WorkerStats {
    fn default() -> Self {
        Self {
            device_id: 0,
            hashes_computed: 0,
            shares_submitted: 0,
            shares_accepted: 0,
            shares_stale: 0,
            kernel_launches: 0,
            avg_nonce_range: 0,
            last_work_time: None,
        }
    }
}

impl WorkerStats {
    /// **Calculate acceptance rate** (tính tỷ lệ chấp nhận) – percentage
    pub fn acceptance_rate(&self) -> f32 {
        if self.shares_submitted > 0 {
            (self.shares_accepted as f32 / self.shares_submitted as f32) * 100.0
        } else {
            0.0
        }
    }

    /// **Calculate current hashrate** (tính hashrate hiện tại) – MH/s
    pub fn current_hashrate_mh(&self, window_duration_secs: u64) -> f64 {
        if window_duration_secs == 0 || self.hashes_computed == 0 {
            return 0.0;
        }

        let hash_per_second = self.hashes_computed as f64 / window_duration_secs as f64;
        hash_per_second / 1_000_000.0 // Convert to MH/s
    }

    /// **Update stats with new share result** (cập nhật với kết quả share mới)
    pub fn record_share_result(&mut self, accepted: bool, stale: bool) {
        self.shares_submitted += 1;
        if accepted && !stale {
            self.shares_accepted += 1;
        } else if stale {
            self.shares_stale += 1;
        } else {
            // Rejected - could add to a separate counter later if needed
            // For now, just track submitted vs accepted+stale
        }
    }

    /// **Record kernel launch** (ghi lại kernel launch)
    pub fn record_kernel_launch(&mut self, hashes_computed: u64) {
        self.kernel_launches += 1;
        self.hashes_computed += hashes_computed;
        self.last_work_time = Some(SystemTime::now());

        // Update average nonce range
        let total_hashes = self.shares_submitted as u64 * self.avg_nonce_range;
        if total_hashes > 0 {
            self.avg_nonce_range = (total_hashes + hashes_computed) / (self.shares_submitted + 1);
        } else if self.avg_nonce_range == 0 {
            self.avg_nonce_range = hashes_computed;
        }
    }
}

/// **MiningStatistics** (thống kê khai thác) – comprehensive mining performance data
pub struct MiningStatistics {
    /// **Configuration** (cấu hình)
    config: StatisticsConfig,

    /// **Start time** (thời điểm bắt đầu)
    start_time: Option<Instant>,

    /// **Worker statistics** (thống kê worker) – per-GPU stats
    worker_stats: Arc<RwLock<std::collections::HashMap<usize, WorkerStats>>>,

    /// **GPU metrics** (metrics GPU) – current GPU state
    gpu_metrics: Arc<RwLock<std::collections::HashMap<usize, GpuMetrics>>>,

    /// **Global counters** (đếm global)
    global_counters: Arc<RwLock<GlobalCounters>>,

    /// **Historical data** (dữ liệu lịch sử) – time series for trend analysis
    historical_data: Arc<RwLock<VecDeque<HistoricalSnapshot>>>,

    /// **Metrics backend** (backend metrics)
    backend: MetricsBackend,
}

/// **GlobalCounters** (đếm global) – aggregate mining counters
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct GlobalCounters {
    /// **Total shares submitted** (tổng share nộp)
    total_shares_submitted: u64,

    /// **Total shares accepted** (tổng share chấp nhận)
    total_shares_accepted: u64,

    /// **Total shares rejected** (tổng share từ chối)
    total_shares_rejected: u64,

    /// **Total kernel launches** (tổng kernel launch)
    total_kernel_launches: u64,

    /// **Total hashes computed** (tổng hash tính toán)
    total_hashes_computed: u64,

    /// **Current hashrate** (hashrate hiện tại) – MH/s
    current_hashrate_mh: f64,

    /// **Peak hashrate** (hashrate đỉnh) – MH/s
    peak_hashrate_mh: f64,

    /// **Uptime** (thời gian chạy) – seconds
    uptime_seconds: u64,
}

/// **HistoricalSnapshot** (snapshot lịch sử) – point-in-time mining stats
#[derive(Debug, Clone, Serialize, Deserialize)]
struct HistoricalSnapshot {
    /// **Timestamp** (thời điểm)
    timestamp: SystemTime,

    /// **Hashrate** (hashrate) – MH/s
    hashrate_mh: f64,

    /// **Acceptance rate** (tỷ lệ chấp nhận) – percentage
    acceptance_rate: f32,

    /// **Active GPUs** (GPU hoạt động) – count
    active_gpus: usize,

    /// **Temperature average** (nhiệt độ trung bình) – °C
    avg_temperature: f32,

    /// **Utilization average** (sử dụng trung bình) – percentage
    avg_utilization: f32,
}

impl MiningStatistics {
    /// **Create new statistics tracker** (tạo tracker thống kê mới)
    pub fn new(config: StatisticsConfig) -> Self {
        Self {
            config,
            start_time: None,
            worker_stats: Arc::new(RwLock::new(std::collections::HashMap::new())),
            gpu_metrics: Arc::new(RwLock::new(std::collections::HashMap::new())),
            global_counters: Arc::new(RwLock::new(GlobalCounters::default())),
            historical_data: Arc::new(RwLock::new(VecDeque::with_capacity(360))), // 1 hour at 10s intervals
            backend: MetricsBackend::Memory,
        }
    }

    /// **Start statistics collection** (bắt đầu thu thập thống kê)
    pub async fn start(&mut self) {
        self.start_time = Some(Instant::now());
        let mut counters = self.global_counters.write().await;
        counters.uptime_seconds = 0;
        info!("📊 Started mining statistics collection");
    }

    /// **Update worker statistics** (cập nhật thống kê worker)
    pub async fn update_worker_stats(&self, device_id: usize, stats: WorkerStats) {
        let mut worker_stats = self.worker_stats.write().await;
        worker_stats.insert(device_id, stats);
        debug!("📈 Updated worker stats for device {}", device_id);
    }

    /// **Update GPU metrics** (cập nhật metrics GPU)
    pub async fn update_gpu_metrics(&self, device_id: usize, metrics: GpuMetrics) {
        let mut gpu_metrics = self.gpu_metrics.write().await;
        gpu_metrics.insert(device_id, metrics);
        debug!("🌡 Updated GPU metrics for device {}", device_id);
    }

    /// **Record share submission** (ghi lại nộp share)
    pub async fn record_share_result(&self, device_id: usize, accepted: bool, stale: bool) {
        // Update worker stats
        {
            let mut worker_stats = self.worker_stats.write().await;
            if let Some(worker) = worker_stats.get_mut(&device_id) {
                worker.record_share_result(accepted, stale);
            }
        }

        // Update global counters
        {
            let mut counters = self.global_counters.write().await;
            counters.total_shares_submitted += 1;
            if accepted {
                counters.total_shares_accepted += 1;
                if stale {
                    counters.total_shares_rejected += 1; // Stale counts as rejected for overall stats
                }
            } else {
                counters.total_shares_rejected += 1;
            }
        }
    }

    /// **Record kernel launch** (ghi lại kernel launch)
    pub async fn record_kernel_launch(&self, device_id: usize, hashes_computed: u64) {
        // Update worker stats
        {
            let mut worker_stats = self.worker_stats.write().await;
            if let Some(worker) = worker_stats.get_mut(&device_id) {
                worker.record_kernel_launch(hashes_computed);
            }
        }

        // Update global counters
        {
            let mut counters = self.global_counters.write().await;
            counters.total_kernel_launches += 1;
            counters.total_hashes_computed += hashes_computed;
        }
    }

    /// **Get current aggregated statistics** (lấy thống kê tổng hợp hiện tại)
    pub async fn get_current_stats(&self) -> AggregatedStats {
        let worker_stats = self.worker_stats.read().await;
        let gpu_metrics = self.gpu_metrics.read().await;
        let counters = self.global_counters.read().await;

        // Calculate uptime
        let uptime_seconds = self.start_time
            .map(|start| start.elapsed().as_secs())
            .unwrap_or(0);

        // Calculate current hashrate (simple moving average)
        let window_duration = self.config.update_interval_secs * 6; // Last 30 seconds
        let mut total_hashrate_mh = 0.0;
        let mut active_gpus = 0;
        let mut total_temp = 0.0;
        let mut total_util = 0.0;

        for (device_id, worker) in worker_stats.iter() {
            let hashrate = worker.current_hashrate_mh(window_duration);
            total_hashrate_mh += hashrate;

            if let Some(gpu) = gpu_metrics.get(device_id) {
                active_gpus += 1;
                total_temp += gpu.temperature;
                total_util += gpu.utilization;

                // Update peak hashrate
                if hashrate > counters.peak_hashrate_mh {
                    let mut counters_mut = self.global_counters.write().await;
                    counters_mut.peak_hashrate_mh = hashrate;
                }
            }
        }

        let avg_temperature = if active_gpus > 0 { total_temp / active_gpus as f32 } else { 0.0 };
        let avg_utilization = if active_gpus > 0 { total_util / active_gpus as f32 } else { 0.0 };

        // Update global counters
        {
            let mut counters_mut = self.global_counters.write().await;
            counters_mut.current_hashrate_mh = total_hashrate_mh;
            counters_mut.uptime_seconds = uptime_seconds;
        }

        AggregatedStats {
            hashrate_mh: total_hashrate_mh,
            acceptance_rate: if counters.total_shares_submitted > 0 {
                (counters.total_shares_accepted as f32 / counters.total_shares_submitted as f32) * 100.0
            } else { 0.0 },
            active_gpus,
            total_shares_submitted: counters.total_shares_submitted,
            total_shares_accepted: counters.total_shares_accepted,
            total_shares_rejected: counters.total_shares_rejected,
            total_kernel_launches: counters.total_kernel_launches,
            uptime_seconds,
            avg_temperature,
            avg_utilization,
            peak_hashrate_mh: counters.peak_hashrate_mh,
        }
    }

    /// **Take historical snapshot** (lấy snapshot lịch sử)
    pub async fn take_snapshot(&self) {
        let stats = self.get_current_stats().await;
        let snapshot = HistoricalSnapshot {
            timestamp: SystemTime::now(),
            hashrate_mh: stats.hashrate_mh,
            acceptance_rate: stats.acceptance_rate,
            active_gpus: stats.active_gpus,
            avg_temperature: stats.avg_temperature,
            avg_utilization: stats.avg_utilization,
        };

        let mut historical = self.historical_data.write().await;
        historical.push_back(snapshot);

        // Remove old data beyond retention period
        let retention_cutoff = SystemTime::now() - Duration::from_secs(self.config.history_retention_minutes * 60);
        while let Some(snap) = historical.front() {
            if snap.timestamp < retention_cutoff {
                historical.pop_front();
            } else {
                break;
            }
        }
    }

    /// **Get worker statistics** (lấy thống kê worker)
    pub async fn get_worker_stats(&self, device_id: usize) -> Option<WorkerStats> {
        let worker_stats = self.worker_stats.read().await;
        worker_stats.get(&device_id).cloned()
    }

    /// **Get GPU metrics** (lấy metrics GPU)
    pub async fn get_gpu_metrics(&self, device_id: usize) -> Option<GpuMetrics> {
        let gpu_metrics = self.gpu_metrics.read().await;
        gpu_metrics.get(&device_id).cloned()
    }

    /// **Check alert conditions** (kiểm tra điều kiện cảnh báo)
    pub async fn check_alerts(&self) -> Vec<MiningAlert> {
        let mut alerts = Vec::new();
        let gpu_metrics = self.gpu_metrics.read().await;
        let worker_stats = self.worker_stats.read().await;

        for (device_id, gpu) in gpu_metrics.iter() {
            // Check temperature
            if gpu.is_overheating(self.config.alert_thresholds.gpu_temp_threshold) {
                alerts.push(MiningAlert {
                    alert_type: AlertType::GpuOverheat,
                    device_id: *device_id,
                    message: format!("GPU {} temperature {}°C exceeds threshold {}°C",
                        device_id, gpu.temperature, self.config.alert_thresholds.gpu_temp_threshold),
                    severity: AlertSeverity::High,
                    timestamp: SystemTime::now(),
                });
            }

            // Check utilization
            if gpu.is_over_utilized(self.config.alert_thresholds.gpu_util_threshold) {
                alerts.push(MiningAlert {
                    alert_type: AlertType::GpuOverUtilized,
                    device_id: *device_id,
                    message: format!("GPU {} utilization {}% exceeds threshold {}%",
                        device_id, gpu.utilization, self.config.alert_thresholds.gpu_util_threshold),
                    severity: AlertSeverity::Medium,
                    timestamp: SystemTime::now(),
                });
            }

            // Check share rejection rate
            if let Some(worker) = worker_stats.get(device_id) {
                let reject_rate = 100.0 - worker.acceptance_rate();
                if reject_rate > self.config.alert_thresholds.share_reject_threshold {
                    alerts.push(MiningAlert {
                        alert_type: AlertType::HighRejectRate,
                        device_id: *device_id,
                        message: format!("GPU {} share rejection rate {}% exceeds threshold {}%",
                            device_id, reject_rate, self.config.alert_thresholds.share_reject_threshold),
                        severity: AlertSeverity::High,
                        timestamp: SystemTime::now(),
                    });
                }
            }
        }

        alerts
    }

    /// **Reset statistics** (đặt lại thống kê)
    pub async fn reset(&mut self) {
        let mut worker_stats = self.worker_stats.write().await;
        worker_stats.clear();

        let mut gpu_metrics = self.gpu_metrics.write().await;
        gpu_metrics.clear();

        let mut counters = self.global_counters.write().await;
        *counters = GlobalCounters::default();

        let mut historical = self.historical_data.write().await;
        historical.clear();

        self.start_time = Some(Instant::now());
        info!("🔄 Reset mining statistics");
    }
}

/// **AggregatedStats** (thống kê tổng hợp) – condensed mining statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AggregatedStats {
    /// **Hashrate** (hashrate) – MH/s
    pub hashrate_mh: f64,

    /// **Acceptance rate** (tỷ lệ chấp nhận) – percentage
    pub acceptance_rate: f32,

    /// **Active GPUs** (GPU hoạt động) – count
    pub active_gpus: usize,

    /// **Total shares submitted** (tổng share nộp)
    pub total_shares_submitted: u64,

    /// **Total shares accepted** (tổng share chấp nhận)
    pub total_shares_accepted: u64,

    /// **Total shares rejected** (tổng share từ chối)
    pub total_shares_rejected: u64,

    /// **Total kernel launches** (tổng kernel launch)
    pub total_kernel_launches: u64,

    /// **Uptime** (thời gian chạy) – seconds
    pub uptime_seconds: u64,

    /// **Average temperature** (nhiệt độ trung bình) – °C
    pub avg_temperature: f32,

    /// **Average utilization** (sử dụng trung bình) – percentage
    pub avg_utilization: f32,

    /// **Peak hashrate** (hashrate đỉnh) – MH/s
    pub peak_hashrate_mh: f64,
}

/// **MiningAlert** (cảnh báo khai thác) – alerts for issues
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningAlert {
    /// **Alert type** (loại cảnh báo)
    pub alert_type: AlertType,

    /// **Device ID** (ID thiết bị) – affected device (if any)
    pub device_id: usize,

    /// **Message** (thông điệp)
    pub message: String,

    /// **Severity** (mức độ nghiêm trọng)
    pub severity: AlertSeverity,

    /// **Timestamp** (thời điểm)
    pub timestamp: SystemTime,
}

/// **AlertType** (loại cảnh báo) – categories of mining alerts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AlertType {
    /// **GPU overheating** (GPU quá nhiệt)
    GpuOverheat,

    /// **GPU over-utilized** (GPU quá tải)
    GpuOverUtilized,

    /// **High share rejection rate** (tỷ lệ từ chối share cao)
    HighRejectRate,

    /// **Hashrate drop** (hashrate giảm)
    HashrateDrop,

    /// **Connection lost** (mất kết nối)
    ConnectionLost,

    /// **Device failure** (thiết bị lỗi)
    DeviceFailure,
}

/// **AlertSeverity** (mức độ nghiêm trọng cảnh báo)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AlertSeverity {
    /// **Low** (thấp)
    Low,

    /// **Medium** (trung bình)
    Medium,

    /// **High** (cao)
    High,

    /// **Critical** (nghiêm trọng)
    Critical,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_statistics_config_default() {
        let config = StatisticsConfig::default();
        assert_eq!(config.update_interval_secs, 5);
        assert_eq!(config.history_retention_minutes, 60);
        assert!(config.enable_gpu_monitoring);
    }

    #[tokio::test]
    async fn test_worker_stats() {
        let mut stats = WorkerStats::default();
        stats.device_id = 0;

        // Test share recording
        stats.record_share_result(true, false); // Accepted
        stats.record_share_result(false, false); // Rejected
        stats.record_share_result(true, true); // Accepted but stale

        assert_eq!(stats.shares_submitted, 3);
        assert_eq!(stats.shares_accepted, 2);
        assert_eq!(stats.shares_rejected, 1);
        assert_eq!(stats.shares_stale, 1);
        assert_eq!(stats.acceptance_rate(), 66.666666); // ~67%
    }

    #[tokio::test]
    async fn test_gpu_metrics() {
        let metrics = GpuMetrics {
            device_id: 0,
            temperature: 75.0,
            utilization: 90.0,
            memory_used_mb: 8000,
            memory_total_mb: 8192,
            fan_speed: Some(70.0),
            power_watts: Some(250.0),
            hashrate_mh: 45.5,
            timestamp: SystemTime::now(),
        };

        assert_eq!(metrics.memory_utilization(), 97.65625); // ~98%
        assert!(!metrics.is_overheating(80.0));
        assert!(metrics.is_overheating(70.0));
    }

    #[tokio::test]
    async fn test_mining_statistics() {
        let config = StatisticsConfig::default();
        let mut stats = MiningStatistics::new(config);

        // Start statistics
        stats.start().await;

        // Add worker stats
        let worker_stats = WorkerStats {
            device_id: 0,
            hashes_computed: 1000000,
            shares_submitted: 10,
            shares_accepted: 8,
            shares_rejected: 2,
            ..Default::default()
        };
        stats.update_worker_stats(0, worker_stats).await;

        // Add GPU metrics
        let gpu_metrics = GpuMetrics {
            device_id: 0,
            temperature: 70.0,
            utilization: 85.0,
            hashrate_mh: 45.0,
            ..Default::default()
        };
        stats.update_gpu_metrics(0, gpu_metrics).await;

        // Get aggregated stats
        let agg_stats = stats.get_current_stats().await;
        assert_eq!(agg_stats.active_gpus, 1);
        assert!(agg_stats.hashrate_mh >= 0.0);
    }
}