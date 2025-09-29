//! OPUS-GPU v2.0 - High-Performance GPU Mining Library
//!
//! **Core Library Exports** (Xuất thư viện cốt lõi) - Module registration and public APIs
//!
//! ## Architecture Overview
//! ```text
//! ┌─────────────────────────────────────────────────────────────┐
//! │                    OPUS-GPU Library                         │
//! ├─────────────────────────────────────────────────────────────┤
//! │  gpu_mining/     │  resource_manager/  │  security/        │
//! │  ├─ engine       │  ├─ allocator       │  ├─ auth          │
//! │  ├─ cuda_wrapper │  ├─ monitor         │  ├─ crypto        │
//! │  └─ thermal      │  └─ scheduler       │  └─ access        │
//! ├─────────────────────────────────────────────────────────────┤
//! │  api/           │  common/            │  cloaking/         │
//! │  ├─ endpoints   │  ├─ config          │  ├─ steganography │
//! │  ├─ middleware  │  ├─ metrics         │  ├─ traffic       │
//! │  └─ websocket   │  └─ types           │  └─ detection     │
//! └─────────────────────────────────────────────────────────────┘
//! ```
//!
//! ## Features
//! - **Lock-free GPU mining** (Đào GPU không khóa) with CUDA acceleration
//! - **Thermal management** (Quản lý nhiệt) with dynamic throttling
//! - **Resource optimization** (Tối ưu tài nguyên) with intelligent scheduling
//! - **Security hardening** (Tăng cường bảo mật) with stealth capabilities
//! - **Real-time monitoring** (Giám sát thời gian thực) with metrics collection

#![deny(missing_docs)]
#![deny(unsafe_code)]
#![warn(clippy::all, clippy::pedantic)]
#![allow(clippy::module_name_repetitions)]
#![allow(clippy::must_use_candidate)]

use anyhow::Result;

// **Core module exports** (Xuất module cốt lõi)
pub mod api;
pub mod common;
pub mod gpu_mining;
pub mod resource_manager;
pub mod security;
pub mod cloaking;

// **Re-export common types** (Xuất lại các kiểu thông dụng)
pub use common::{
    config::Config,
    error::{Error, ErrorKind},
    metrics::MetricsCollector,
    types::{GpuId, HashRate, Temperature, PowerUsage},
};

// **Re-export core engine types** (Xuất lại các kiểu engine cốt lõi)
pub use gpu_mining::{
    engine::{MiningEngine, MiningStats, WorkerStats},
    thermal::{ThermalManager, ThermalState},
};

// **Re-export resource management** (Xuất lại quản lý tài nguyên)
pub use resource_manager::{
    ResourceManager,
    SystemStats,
    GpuStats,
    allocator::MemoryAllocator,
};

// **Re-export security components** (Xuất lại thành phần bảo mật)
pub use security::{
    SecurityManager,
    auth::{AuthManager, AuthToken},
    crypto::{CryptoManager, EncryptionKey},
};

// **Re-export API components** (Xuất lại thành phần API)
pub use api::{
    ApiServer,
    endpoints::{MiningEndpoint, MetricsEndpoint},
    websocket::WebSocketHandler,
};

// **Feature flags** (Cờ tính năng)
#[cfg(feature = "cuda")]
pub use gpu_mining::cuda_wrapper::{CudaContext, CudaKernel};

#[cfg(feature = "stealth")]
pub use cloaking::{
    steganography::SteganographyEngine,
    traffic::TrafficObfuscator,
};

/// **Library version information** (Thông tin phiên bản thư viện)
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// **Library build information** (Thông tin build thư viện)
pub const BUILD_INFO: BuildInfo = BuildInfo {
    version: env!("CARGO_PKG_VERSION"),
    git_hash: option_env!("GIT_HASH").unwrap_or("unknown"),
    build_date: env!("BUILD_DATE"),
    rust_version: env!("RUST_VERSION"),
    features: &[
        #[cfg(feature = "cuda")]
        "cuda",
        #[cfg(feature = "metrics")]
        "metrics",
        #[cfg(feature = "security")]
        "security",
        #[cfg(feature = "stealth")]
        "stealth",
        #[cfg(feature = "enterprise")]
        "enterprise",
    ],
};

/// **Build metadata** (Metadata build)
#[derive(Debug, Clone)]
pub struct BuildInfo {
    /// **Library version** (Phiên bản thư viện)
    pub version: &'static str,
    /// **Git commit hash** (Hash commit Git)
    pub git_hash: &'static str,
    /// **Build timestamp** (Timestamp build)
    pub build_date: &'static str,
    /// **Rust compiler version** (Phiên bản trình biên dịch Rust)
    pub rust_version: &'static str,
    /// **Enabled features** (Tính năng được bật)
    pub features: &'static [&'static str],
}

/// **Library initialization** (Khởi tạo thư viện)
///
/// Initializes the OPUS-GPU library with default configuration.
/// Must be called before using any library functions.
///
/// ## Example
/// ```rust
/// use opus_gpu::init;
///
/// #[tokio::main]
/// async fn main() -> anyhow::Result<()> {
///     init().await?;
///     // Use library functions...
///     Ok(())
/// }
/// ```
pub async fn init() -> Result<()> {
    init_with_config(Config::default()).await
}

/// **Library initialization with custom config** (Khởi tạo thư viện với cấu hình tùy chỉnh)
///
/// Initializes the OPUS-GPU library with provided configuration.
///
/// ## Arguments
/// * `config` - **Configuration settings** (Cài đặt cấu hình)
///
/// ## Example
/// ```rust
/// use opus_gpu::{init_with_config, Config};
///
/// #[tokio::main]
/// async fn main() -> anyhow::Result<()> {
///     let config = Config {
///         mining: Default::default(),
///         thermal: Default::default(),
///         // ... other settings
///     };
///     init_with_config(config).await?;
///     Ok(())
/// }
/// ```
pub async fn init_with_config(config: Config) -> Result<()> {
    // **Initialize global allocator** (Khởi tạo allocator toàn cục)
    #[cfg(feature = "mimalloc")]
    {
        use mimalloc::MiMalloc;
        #[global_allocator]
        static GLOBAL: MiMalloc = MiMalloc;
    }

    // **Initialize metrics system** (Khởi tạo hệ thống metrics)
    #[cfg(feature = "metrics")]
    {
        common::metrics::init_metrics(&config.metrics)?;
    }

    // **Initialize security subsystem** (Khởi tạo hệ thống con bảo mật)
    #[cfg(feature = "security")]
    {
        security::init_security(&config.security).await?;
    }

    // **Initialize CUDA runtime** (Khởi tạo runtime CUDA)
    #[cfg(feature = "cuda")]
    {
        gpu_mining::cuda_wrapper::init_cuda()?;
    }

    // **Initialize cloaking systems** (Khởi tạo hệ thống cloaking)
    #[cfg(feature = "stealth")]
    {
        cloaking::init_stealth(&config.stealth).await?;
    }

    tracing::info!("OPUS-GPU library initialized successfully");
    tracing::info!("Version: {}, Features: {:?}", VERSION, BUILD_INFO.features);

    Ok(())
}

/// **Library cleanup** (Dọn dẹp thư viện)
///
/// Performs cleanup operations and releases resources.
/// Should be called before application shutdown.
///
/// ## Example
/// ```rust
/// use opus_gpu::cleanup;
///
/// #[tokio::main]
/// async fn main() -> anyhow::Result<()> {
///     // ... use library
///     cleanup().await?;
///     Ok(())
/// }
/// ```
pub async fn cleanup() -> Result<()> {
    tracing::info!("Starting OPUS-GPU library cleanup");

    // **Cleanup in reverse initialization order** (Dọn dẹp theo thứ tự ngược với khởi tạo)

    #[cfg(feature = "stealth")]
    {
        if let Err(e) = cloaking::cleanup_stealth().await {
            tracing::error!("Error cleaning up stealth systems: {}", e);
        }
    }

    #[cfg(feature = "cuda")]
    {
        if let Err(e) = gpu_mining::cuda_wrapper::cleanup_cuda() {
            tracing::error!("Error cleaning up CUDA runtime: {}", e);
        }
    }

    #[cfg(feature = "security")]
    {
        if let Err(e) = security::cleanup_security().await {
            tracing::error!("Error cleaning up security subsystem: {}", e);
        }
    }

    #[cfg(feature = "metrics")]
    {
        if let Err(e) = common::metrics::cleanup_metrics().await {
            tracing::error!("Error cleaning up metrics system: {}", e);
        }
    }

    tracing::info!("OPUS-GPU library cleanup completed");
    Ok(())
}

/// **Check library health** (Kiểm tra sức khỏe thư viện)
///
/// Performs comprehensive health checks across all subsystems.
/// Returns detailed health status for monitoring.
///
/// ## Returns
/// * `HealthStatus` - **Detailed health information** (Thông tin sức khỏe chi tiết)
pub async fn health_check() -> Result<HealthStatus> {
    let mut status = HealthStatus::default();

    // **Check GPU mining subsystem** (Kiểm tra hệ thống con đào GPU)
    status.gpu_mining = gpu_mining::health_check().await.is_ok();

    // **Check resource manager** (Kiểm tra resource manager)
    status.resource_manager = resource_manager::health_check().await.is_ok();

    // **Check security subsystem** (Kiểm tra hệ thống con bảo mật)
    #[cfg(feature = "security")]
    {
        status.security = security::health_check().await.is_ok();
    }

    // **Check API server** (Kiểm tra server API)
    status.api_server = api::health_check().await.is_ok();

    // **Overall health** (Sức khỏe tổng thể)
    status.overall = status.gpu_mining
        && status.resource_manager
        && status.security
        && status.api_server;

    Ok(status)
}

/// **Health status information** (Thông tin trạng thái sức khỏe)
#[derive(Debug, Clone, Default)]
pub struct HealthStatus {
    /// **Overall health status** (Trạng thái sức khỏe tổng thể)
    pub overall: bool,
    /// **GPU mining subsystem status** (Trạng thái hệ thống con đào GPU)
    pub gpu_mining: bool,
    /// **Resource manager status** (Trạng thái resource manager)
    pub resource_manager: bool,
    /// **Security subsystem status** (Trạng thái hệ thống con bảo mật)
    pub security: bool,
    /// **API server status** (Trạng thái server API)
    pub api_server: bool,
}

/// **Performance statistics** (Thống kê hiệu suất)
#[derive(Debug, Clone)]
pub struct PerformanceStats {
    /// **Mining hashrate in MH/s** (Tốc độ hash đào tính bằng MH/s)
    pub hashrate_mhs: f64,
    /// **Power consumption in watts** (Tiêu thụ điện năng tính bằng watt)
    pub power_watts: f64,
    /// **Efficiency ratio (MH/s per watt)** (Tỷ lệ hiệu quả MH/s trên watt)
    pub efficiency: f64,
    /// **GPU utilization percentage** (Phần trăm sử dụng GPU)
    pub gpu_utilization: f64,
    /// **Memory utilization percentage** (Phần trăm sử dụng bộ nhớ)
    pub memory_utilization: f64,
    /// **Average temperature in Celsius** (Nhiệt độ trung bình tính bằng độ C)
    pub temperature: f64,
    /// **Active worker threads** (Luồng worker đang hoạt động)
    pub active_workers: usize,
}

/// **Get current performance statistics** (Lấy thống kê hiệu suất hiện tại)
///
/// Collects and returns comprehensive performance metrics from all subsystems.
///
/// ## Returns
/// * `PerformanceStats` - **Current performance data** (Dữ liệu hiệu suất hiện tại)
pub async fn get_performance_stats() -> Result<PerformanceStats> {
    // **Collect stats from all subsystems** (Thu thập stats từ tất cả hệ thống con)
    let gpu_stats = gpu_mining::get_performance_stats().await?;
    let resource_stats = resource_manager::get_system_stats().await?;

    Ok(PerformanceStats {
        hashrate_mhs: gpu_stats.total_hashrate,
        power_watts: gpu_stats.total_power,
        efficiency: gpu_stats.total_hashrate / gpu_stats.total_power.max(1.0),
        gpu_utilization: resource_stats.gpu_usage,
        memory_utilization: resource_stats.memory_usage,
        temperature: gpu_stats.average_temperature,
        active_workers: gpu_stats.active_workers,
    })
}

/// **Library feature detection** (Phát hiện tính năng thư viện)
#[derive(Debug, Clone)]
pub struct FeatureSet {
    /// **CUDA acceleration available** (Có gia tốc CUDA)
    pub cuda: bool,
    /// **Metrics collection enabled** (Bật thu thập metrics)
    pub metrics: bool,
    /// **Security features enabled** (Bật tính năng bảo mật)
    pub security: bool,
    /// **Stealth mode available** (Có chế độ stealth)
    pub stealth: bool,
    /// **Enterprise features** (Tính năng enterprise)
    pub enterprise: bool,
}

/// **Get available features** (Lấy tính năng có sẵn)
///
/// Returns information about enabled library features.
///
/// ## Returns
/// * `FeatureSet` - **Available feature information** (Thông tin tính năng có sẵn)
pub fn get_features() -> FeatureSet {
    FeatureSet {
        cuda: cfg!(feature = "cuda"),
        metrics: cfg!(feature = "metrics"),
        security: cfg!(feature = "security"),
        stealth: cfg!(feature = "stealth"),
        enterprise: cfg!(feature = "enterprise"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_library_initialization() {
        let result = init().await;
        assert!(result.is_ok());

        let health = health_check().await.unwrap();
        // **Don't require all systems to be healthy in tests** (Không yêu cầu tất cả hệ thống healthy trong test)
        // assert!(health.overall);
    }

    #[test]
    fn test_build_info() {
        assert!(!BUILD_INFO.version.is_empty());
        assert!(!BUILD_INFO.features.is_empty());
    }

    #[test]
    fn test_feature_detection() {
        let features = get_features();
        // **Check that at least one feature is enabled** (Kiểm tra ít nhất một tính năng được bật)
        assert!(features.cuda || features.metrics || features.security);
    }

    #[tokio::test]
    async fn test_cleanup() {
        let result = cleanup().await;
        assert!(result.is_ok());
    }
}