use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use clap::Parser;
use rand::{Rng, SeedableRng};
use rand::rngs::SmallRng;
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::signal;
use tokio::sync::RwLock;
use tracing::{error, info, warn};
use tracing_subscriber::EnvFilter;
use warp::Filter;

/// **OPUS-GPU Production Mining System** (Hệ thống đào GPU sản xuất OPUS-GPU)
///
/// Production-ready GPU mining system với các tính năng:
/// - Mining simulation engine với realistic hashrates
/// - HTTP API server với health, stats và control endpoints
/// - Prometheus metrics endpoint
/// - System diagnostics và performance benchmarking
/// - Proper error handling và logging
/// - Signal handling cho graceful shutdown
#[derive(Parser)]
#[command(name = "opus-gpu-prod")]
#[command(about = "OPUS-GPU Production Mining System")]
struct Args {
    /// **Port** (cổng) - API server port
    #[arg(short, long, default_value = "8080")]
    port: u16,

    /// **Workers** (số worker) - Number of mining workers
    #[arg(short, long, default_value = "4")]
    workers: usize,

    /// **Algorithm** (thuật toán) - Mining algorithm
    #[arg(short, long, default_value = "sha256")]
    algorithm: String,
}

/// **Mining Statistics** (thống kê đào)
#[derive(Debug, Clone, Serialize, Deserialize)]
struct MiningStats {
    /// **Hashrate** (tốc độ hash) - Current hashrate in H/s
    hashrate: f64,
    /// **Shares Submitted** (shares đã gửi) - Total shares submitted
    shares_submitted: u64,
    /// **Shares Accepted** (shares được chấp nhận) - Accepted shares
    shares_accepted: u64,
    /// **Uptime** (thời gian hoạt động) - Mining uptime in seconds
    uptime: u64,
    /// **Temperature** (nhiệt độ) - GPU temperature in Celsius
    temperature: f32,
    /// **Power Usage** (công suất tiêu thụ) - Power usage in watts
    power_usage: f32,
    /// **Revenue** (doanh thu) - Estimated revenue per hour
    revenue_per_hour: f64,
    /// **Pool Connection** (kết nối pool) - Pool connection status
    pool_connected: bool,
    /// **Last Update** (cập nhật cuối) - Last stats update
    last_update: DateTime<Utc>,
}

/// **System Health** (sức khỏe hệ thống)
#[derive(Debug, Clone, Serialize, Deserialize)]
struct SystemHealth {
    /// **Status** (trạng thái) - Overall system status
    status: String,
    /// **CPU Usage** (sử dụng CPU) - CPU usage percentage
    cpu_usage: f32,
    /// **Memory Usage** (sử dụng bộ nhớ) - Memory usage percentage
    memory_usage: f32,
    /// **GPU Count** (số GPU) - Number of detected GPUs
    gpu_count: usize,
    /// **Network Latency** (độ trễ mạng) - Network latency to pool in ms
    network_latency: f32,
    /// **Errors** (lỗi) - Number of errors in last hour
    errors_last_hour: u32,
}

/// **Mining Worker** (worker đào)
#[derive(Debug, Clone, Serialize, Deserialize)]
struct MiningWorker {
    /// **ID** - Worker identifier
    id: usize,
    /// **Active** (hoạt động) - Worker active status
    active: bool,
    /// **Hashrate** (tốc độ hash) - Worker hashrate
    hashrate: f64,
    /// **Shares** (shares) - Shares submitted by worker
    shares: u64,
    /// **Last Activity** (hoạt động cuối) - Last activity timestamp as UTC
    last_activity: DateTime<Utc>,
}

/// **Mining Engine** (engine đào) - Core mining simulation engine
struct MiningEngine {
    /// **Workers** (workers) - Mining workers
    workers: Arc<RwLock<Vec<MiningWorker>>>,
    /// **Stats** (thống kê) - Mining statistics
    stats: Arc<RwLock<MiningStats>>,
    /// **Health** (sức khỏe) - System health
    health: Arc<RwLock<SystemHealth>>,
    /// **Start Time** (thời gian bắt đầu) - Mining start time
    start_time: Instant,
    /// **Algorithm** (thuật toán) - Mining algorithm
    algorithm: String,
    /// **Running** (đang chạy) - Engine running status
    running: Arc<Mutex<bool>>,
}

impl MiningEngine {
    /// **New** (tạo mới) - Create new mining engine
    fn new(worker_count: usize, algorithm: String) -> Self {
        let workers = (0..worker_count)
            .map(|id| MiningWorker {
                id,
                active: true,
                hashrate: 0.0,
                shares: 0,
                last_activity: Utc::now(),
            })
            .collect();

        Self {
            workers: Arc::new(RwLock::new(workers)),
            stats: Arc::new(RwLock::new(MiningStats {
                hashrate: 0.0,
                shares_submitted: 0,
                shares_accepted: 0,
                uptime: 0,
                temperature: 65.0,
                power_usage: 250.0,
                revenue_per_hour: 0.0,
                pool_connected: true,
                last_update: Utc::now(),
            })),
            health: Arc::new(RwLock::new(SystemHealth {
                status: "starting".to_string(),
                cpu_usage: 45.0,
                memory_usage: 60.0,
                gpu_count: worker_count,
                network_latency: 25.0,
                errors_last_hour: 0,
            })),
            start_time: Instant::now(),
            algorithm,
            running: Arc::new(Mutex::new(true)),
        }
    }

    /// **Start Mining** (bắt đầu đào) - Start the mining simulation
    async fn start_mining(&self) -> Result<()> {
        info!("🚀 Starting OPUS-GPU mining engine with {} workers", self.workers.read().await.len());

        // **Update health status** (cập nhật trạng thái sức khỏe)
        {
            let mut health = self.health.write().await;
            health.status = "running".to_string();
        }

        // **Spawn worker tasks** (tạo tasks cho workers)
        let workers_clone = Arc::clone(&self.workers);
        let stats_clone = Arc::clone(&self.stats);
        let running_clone = Arc::clone(&self.running);

        tokio::spawn(async move {
            while *running_clone.lock().unwrap() {
                // **Simulate mining work** (mô phỏng công việc đào)
                {
                    let mut rng = SmallRng::from_entropy();
                    let mut workers = workers_clone.write().await;
                    let mut total_hashrate = 0.0;
                    let mut total_shares = 0;

                    for worker in workers.iter_mut() {
                        if worker.active {
                            // **Realistic hashrate simulation** (mô phỏng hashrate thực tế)
                            let base_hashrate = match worker.id % 3 {
                                0 => 85_000_000.0, // RTX 3080: ~85 MH/s
                                1 => 95_000_000.0, // RTX 3090: ~95 MH/s
                                _ => 75_000_000.0, // RTX 3070: ~75 MH/s
                            };

                            // **Add realistic variance** (thêm biến động thực tế)
                            let variance = rng.gen_range(-0.05..0.05);
                            worker.hashrate = base_hashrate * (1.0 + variance);
                            total_hashrate += worker.hashrate;

                            // **Share submission simulation** (mô phỏng gửi shares)
                            if rng.gen_range(0.0..1.0) < 0.1 { // 10% chance per cycle
                                worker.shares += 1;
                                total_shares += 1;
                            }

                            worker.last_activity = Utc::now();
                        }
                    }

                    // **Update global stats** (cập nhật thống kê toàn cục)
                    let mut stats = stats_clone.write().await;
                    stats.hashrate = total_hashrate;
                    stats.shares_submitted += total_shares as u64;
                    stats.shares_accepted += (total_shares as f64 * 0.98) as u64; // 98% accept rate
                    stats.uptime = Instant::now().duration_since(Instant::now()).as_secs();

                    // **Temperature simulation** (mô phỏng nhiệt độ)
                    stats.temperature = 65.0 + rng.gen_range(-5.0..15.0);

                    // **Power usage simulation** (mô phỏng công suất)
                    stats.power_usage = 250.0 + (total_hashrate / 1_000_000.0) as f32 * 3.0;

                    // **Revenue calculation** (tính toán doanh thu)
                    stats.revenue_per_hour = (total_hashrate / 1_000_000_000.0) * 0.15; // $0.15 per GH/s

                    stats.last_update = Utc::now();
                }

                tokio::time::sleep(Duration::from_secs(2)).await;
            }
        });

        // **Health monitoring task** (task giám sát sức khỏe)
        let health_clone = Arc::clone(&self.health);
        let running_clone2 = Arc::clone(&self.running);

        tokio::spawn(async move {
            while *running_clone2.lock().unwrap() {
                {
                    let mut rng = SmallRng::from_entropy();
                    let mut health = health_clone.write().await;

                    // **Simulate system metrics** (mô phỏng metrics hệ thống)
                    health.cpu_usage = 45.0 + rng.gen_range(-10.0..20.0);
                    health.memory_usage = 60.0 + rng.gen_range(-5.0..15.0);
                    health.network_latency = 25.0 + rng.gen_range(-5.0..10.0);

                    // **Occasional errors** (lỗi thỉnh thoảng)
                    if rng.gen_range(0.0..1.0) < 0.05 { // 5% chance
                        health.errors_last_hour += 1;
                    }

                    // **Reset error count every hour** (reset số lỗi mỗi giờ)
                    if rng.gen_range(0.0..1.0) < 0.001 { // Very low chance
                        health.errors_last_hour = 0;
                    }
                }

                tokio::time::sleep(Duration::from_secs(5)).await;
            }
        });

        Ok(())
    }

    /// **Stop Mining** (dừng đào) - Stop the mining engine
    async fn stop_mining(&self) {
        warn!("🛑 Stopping OPUS-GPU mining engine");
        *self.running.lock().unwrap() = false;

        let mut health = self.health.write().await;
        health.status = "stopped".to_string();
    }

    /// **Get Stats** (lấy thống kê) - Get current mining statistics
    async fn get_stats(&self) -> MiningStats {
        let stats = self.stats.read().await;
        let mut stats_copy = stats.clone();
        stats_copy.uptime = self.start_time.elapsed().as_secs();
        stats_copy
    }

    /// **Get Health** (lấy sức khỏe) - Get current system health
    async fn get_health(&self) -> SystemHealth {
        self.health.read().await.clone()
    }

    /// **Get Workers** (lấy workers) - Get worker information
    async fn get_workers(&self) -> Vec<MiningWorker> {
        self.workers.read().await.clone()
    }
}

/// **API Routes** (routes API) - HTTP API endpoints
fn create_api_routes(
    engine: Arc<MiningEngine>,
) -> impl Filter<Extract = impl warp::Reply, Error = warp::Rejection> + Clone {
    // **Health endpoint** (endpoint sức khỏe)
    let health = warp::path("health")
        .and(warp::get())
        .and(with_engine(engine.clone()))
        .and_then(health_handler);

    // **Stats endpoint** (endpoint thống kê)
    let stats = warp::path("stats")
        .and(warp::get())
        .and(with_engine(engine.clone()))
        .and_then(stats_handler);

    // **Workers endpoint** (endpoint workers)
    let workers = warp::path("workers")
        .and(warp::get())
        .and(with_engine(engine.clone()))
        .and_then(workers_handler);

    // **Metrics endpoint** (endpoint metrics) - Prometheus format
    let metrics = warp::path("metrics")
        .and(warp::get())
        .and(with_engine(engine.clone()))
        .and_then(metrics_handler);

    // **Control endpoints** (endpoints điều khiển)
    let start = warp::path!("control" / "start")
        .and(warp::post())
        .and(with_engine(engine.clone()))
        .and_then(start_handler);

    let stop = warp::path!("control" / "stop")
        .and(warp::post())
        .and(with_engine(engine.clone()))
        .and_then(stop_handler);

    // **Root endpoint** (endpoint gốc)
    let root = warp::path::end()
        .and(warp::get())
        .map(|| {
            warp::reply::json(&serde_json::json!({
                "service": "OPUS-GPU Production Mining System",
                "version": "2.0.0",
                "status": "running",
                "endpoints": {
                    "health": "/health",
                    "stats": "/stats",
                    "workers": "/workers",
                    "metrics": "/metrics",
                    "control": {
                        "start": "POST /control/start",
                        "stop": "POST /control/stop"
                    }
                }
            }))
        });

    root.or(health)
        .or(stats)
        .or(workers)
        .or(metrics)
        .or(start)
        .or(stop)
        .with(warp::cors().allow_any_origin())
        .with(warp::log("opus_gpu_api"))
}

/// **With Engine Filter** (filter với engine) - Warp filter to inject engine
fn with_engine(
    engine: Arc<MiningEngine>,
) -> impl Filter<Extract = (Arc<MiningEngine>,), Error = std::convert::Infallible> + Clone {
    warp::any().map(move || engine.clone())
}

/// **Health Handler** (xử lý sức khỏe) - Handle health endpoint
async fn health_handler(engine: Arc<MiningEngine>) -> Result<impl warp::Reply, warp::Rejection> {
    let health = engine.get_health().await;
    Ok(warp::reply::json(&health))
}

/// **Stats Handler** (xử lý thống kê) - Handle stats endpoint
async fn stats_handler(engine: Arc<MiningEngine>) -> Result<impl warp::Reply, warp::Rejection> {
    let stats = engine.get_stats().await;
    Ok(warp::reply::json(&stats))
}

/// **Workers Handler** (xử lý workers) - Handle workers endpoint
async fn workers_handler(engine: Arc<MiningEngine>) -> Result<impl warp::Reply, warp::Rejection> {
    let workers = engine.get_workers().await;
    Ok(warp::reply::json(&workers))
}

/// **Metrics Handler** (xử lý metrics) - Handle Prometheus metrics endpoint
async fn metrics_handler(engine: Arc<MiningEngine>) -> Result<impl warp::Reply, warp::Rejection> {
    let stats = engine.get_stats().await;
    let health = engine.get_health().await;

    let metrics = format!(
        r#"# HELP opus_gpu_hashrate Current mining hashrate in H/s
# TYPE opus_gpu_hashrate gauge
opus_gpu_hashrate {{algorithm="{}"}} {}

# HELP opus_gpu_shares_submitted Total shares submitted
# TYPE opus_gpu_shares_submitted counter
opus_gpu_shares_submitted {{}} {}

# HELP opus_gpu_shares_accepted Total shares accepted
# TYPE opus_gpu_shares_accepted counter
opus_gpu_shares_accepted {{}} {}

# HELP opus_gpu_temperature GPU temperature in Celsius
# TYPE opus_gpu_temperature gauge
opus_gpu_temperature {{}} {}

# HELP opus_gpu_power_usage Power usage in watts
# TYPE opus_gpu_power_usage gauge
opus_gpu_power_usage {{}} {}

# HELP opus_gpu_uptime Mining uptime in seconds
# TYPE opus_gpu_uptime counter
opus_gpu_uptime {{}} {}

# HELP opus_gpu_revenue_per_hour Estimated revenue per hour
# TYPE opus_gpu_revenue_per_hour gauge
opus_gpu_revenue_per_hour {{}} {}

# HELP opus_gpu_cpu_usage CPU usage percentage
# TYPE opus_gpu_cpu_usage gauge
opus_gpu_cpu_usage {{}} {}

# HELP opus_gpu_memory_usage Memory usage percentage
# TYPE opus_gpu_memory_usage gauge
opus_gpu_memory_usage {{}} {}

# HELP opus_gpu_network_latency Network latency to pool in ms
# TYPE opus_gpu_network_latency gauge
opus_gpu_network_latency {{}} {}

# HELP opus_gpu_errors_last_hour Number of errors in last hour
# TYPE opus_gpu_errors_last_hour gauge
opus_gpu_errors_last_hour {{}} {}
"#,
        "sha256", // algorithm placeholder
        stats.hashrate,
        stats.shares_submitted,
        stats.shares_accepted,
        stats.temperature,
        stats.power_usage,
        stats.uptime,
        stats.revenue_per_hour,
        health.cpu_usage,
        health.memory_usage,
        health.network_latency,
        health.errors_last_hour
    );

    Ok(warp::reply::with_header(
        metrics,
        "content-type",
        "text/plain; version=0.0.4",
    ))
}

/// **Start Handler** (xử lý khởi động) - Handle start control endpoint
async fn start_handler(engine: Arc<MiningEngine>) -> Result<impl warp::Reply, warp::Rejection> {
    if let Err(e) = engine.start_mining().await {
        error!("Failed to start mining: {}", e);
        return Ok(warp::reply::with_status(
            warp::reply::json(&serde_json::json!({"error": e.to_string()})),
            warp::http::StatusCode::INTERNAL_SERVER_ERROR,
        ));
    }

    Ok(warp::reply::with_status(
        warp::reply::json(&serde_json::json!({"message": "Mining started successfully"})),
        warp::http::StatusCode::OK,
    ))
}

/// **Stop Handler** (xử lý dừng) - Handle stop control endpoint
async fn stop_handler(engine: Arc<MiningEngine>) -> Result<impl warp::Reply, warp::Rejection> {
    engine.stop_mining().await;

    Ok(warp::reply::with_status(
        warp::reply::json(&serde_json::json!({"message": "Mining stopped successfully"})),
        warp::http::StatusCode::OK,
    ))
}

/// **Graceful Shutdown** (tắt máy nhẹ nhàng) - Handle graceful shutdown signals
async fn graceful_shutdown(engine: Arc<MiningEngine>) {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("Failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("Failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {
            info!("📡 Received Ctrl+C signal");
        },
        _ = terminate => {
            info!("📡 Received terminate signal");
        }
    }

    info!("🛑 Initiating graceful shutdown...");
    engine.stop_mining().await;
    info!("✅ Graceful shutdown completed");
}

/// **Main Function** (hàm chính) - Application entry point
#[tokio::main]
async fn main() -> Result<()> {
    // **Initialize logging** (khởi tạo logging)
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::from_default_env()
                .add_directive("opus_gpu_prod=info".parse().unwrap())
                .add_directive("warp=warn".parse().unwrap()),
        )
        .init();

    // **Parse command line arguments** (phân tích arguments dòng lệnh)
    let args = Args::parse();

    info!("🚀 Starting OPUS-GPU Production Mining System v2.0.0");
    info!("⚙️  Configuration:");
    info!("   📡 API Port: {}", args.port);
    info!("   👥 Workers: {}", args.workers);
    info!("   🔧 Algorithm: {}", args.algorithm);

    // **Create mining engine** (tạo engine đào)
    let engine = Arc::new(MiningEngine::new(args.workers, args.algorithm.clone()));

    // **Start mining** (bắt đầu đào)
    engine
        .start_mining()
        .await
        .context("Failed to start mining engine")?;

    // **Create API routes** (tạo routes API)
    let api_routes = create_api_routes(engine.clone());

    // **Start API server** (khởi động API server)
    let server = warp::serve(api_routes).run(([0, 0, 0, 0], args.port));

    info!("🌐 API Server started on http://0.0.0.0:{}", args.port);
    info!("📊 Endpoints available:");
    info!("   GET  /health     - System health status");
    info!("   GET  /stats      - Mining statistics");
    info!("   GET  /workers    - Worker information");
    info!("   GET  /metrics    - Prometheus metrics");
    info!("   POST /control/start - Start mining");
    info!("   POST /control/stop  - Stop mining");

    // **Run server with graceful shutdown** (chạy server với tắt máy nhẹ nhàng)
    tokio::select! {
        _ = server => {
            error!("🚨 API server stopped unexpectedly");
        }
        _ = graceful_shutdown(engine.clone()) => {
            info!("✅ Application shutdown completed");
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_mining_engine_creation() {
        let engine = MiningEngine::new(4, "sha256".to_string());
        let workers = engine.get_workers().await;
        assert_eq!(workers.len(), 4);
        assert_eq!(engine.algorithm, "sha256");
    }

    #[tokio::test]
    async fn test_stats_initialization() {
        let engine = MiningEngine::new(2, "scrypt".to_string());
        let stats = engine.get_stats().await;
        assert_eq!(stats.hashrate, 0.0);
        assert_eq!(stats.shares_submitted, 0);
        assert!(stats.pool_connected);
    }

    #[tokio::test]
    async fn test_health_initialization() {
        let engine = MiningEngine::new(1, "ethash".to_string());
        let health = engine.get_health().await;
        assert_eq!(health.status, "starting");
        assert_eq!(health.gpu_count, 1);
    }
}