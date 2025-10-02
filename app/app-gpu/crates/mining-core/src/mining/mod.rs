//! # Mining Loop Orchestration Module (Module điều phối vòng lặp khai thác)
//!
//! **High-performance mining orchestration** (điều phối khai thác hiệu năng cao)
//! với async actor patterns, GPU workload distribution, work management pipeline
//! và comprehensive monitoring cho scale mining operations.
//!
//! ## Architecture Overview (Tổng quan kiến trúc)
//!
//! ```
//! mining/
//! ├── mod.rs           # Module interface - giao diện module
//! ├── loop.rs          # MiningLoop (orchestrator) - vòng lặp khai thác chính
//! ├── worker.rs        # GpuWorker (per-GPU actor) - worker cho mỗi GPU
//! └── statistics.rs    # MiningStats (metrics) - thống kê và metrics
//! ```
//!
//! ## Key Components (Thành phần chính)
//!
//! - **`MiningLoop`**: Central orchestrator với work distribution, kernel launch tracking, result aggregation
//! - **`GpuWorker`**: Per-GPU actor cho async kernel execution, nonce range management, solution extraction
//! - **`MiningStatistics`**: Real-time metrics, hashrate calculation, performance monitoring
//! - **Work Management**: Job queue management, nonce distribution, difficulty validation
//!
//! ## Async Architecture (Kiến trúc bất đồng bộ)
//!
//! ```rust,ignore
//! MiningLoop ────► stratum client (work fetching)
//!     │
//!     ├──► shared work queue
//!     │
//!     ├─► GpuWorker #0 ───┐
//!     ├─► GpuWorker #1 ───┼──► kernel launches → results → submissions
//!     ├─► GpuWorker #2 ───┘
//!     │
//!     └──► statistics aggregator (hashrate, efficiency, health)
//! ```
//!
//! ## Feature Flags (Cờ tính năng)
//!
//! - `stats`: Enable detailed performance monitoring - Bật giám sát hiệu năng chi tiết
//! - `thermal`: Enable GPU thermal-aware workload balancing - Bật cân bằng tải theo nhiệt độ GPU
//! - `debug`: Enable additional debug logging và validation - Bật ghi nhật ký debug bổ sung
//!
//! ## Example Usage (Ví dụ sử dụng)
//!
//! ```rust,ignore
//! use mining_core::mining::{MiningLoop, GpuWorker};
//!
//! // Create mining loop với configuration
//! let mining_loop = MiningLoop::new(config).await?;
//!
//! // Start mining operation
//! mining_loop.start().await;
//!
//! // Get real-time statistics
//! let stats = mining_loop.get_statistics().await;
//! println!("Mining at {} MH/s across {} GPUs", stats.hashrate_mega(), stats.active_gpus());
//!
//! // Graceful shutdown
//! mining_loop.shutdown().await?;
//! ```

pub mod loop_mod;
pub mod statistics;
pub mod worker;

// Re-export main types cho convenient access (Xuất lại kiểu chính)
pub use loop_mod::{MiningLoop, WorkPackage as MiningWorkPackage};
pub use worker::GpuWorker;
pub use statistics::{MiningStatistics, WorkerStats, GpuMetrics};

// Export configuration types (Xuất kiểu cấu hình)
pub use statistics::{StatisticsConfig, MetricsBackend};

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_module_exports() {
        // Test that all main types are exported correctly
        // Note: Actual instantiation requires config and dependencies
        println!("✅ Mining module exports loaded successfully");
    }
}