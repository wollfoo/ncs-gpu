# 🏗️ KIẾN TRÚC HỆ THỐNG APP-GPU

## 📋 Tổng quan

**Kiến trúc**: **Modular Monolith** (nguyên khối mô-đun – single binary với plugin architecture)  
**Ngôn ngữ chính**: **Rust** (core system, GPU operations)  
**Ngôn ngữ phụ**: **Go** (monitoring, orchestration), **C++** (CUDA kernels)  
**Pattern**: **Plugin-based** (dựa trên plugin – dynamic loading), **Event Bus** (bus sự kiện – pub/sub nội bộ)

---

## 🎯 Mục tiêu đạt được

| Tiêu chí | Hiện tại (Python) | Mục tiêu (Rust) | Cải thiện |
|----------|-------------------|-----------------|-----------|
| **P95 Latency** | ~50ms | ~2ms | ✅ 96% ↓ |
| **GPU Utilization** | 70-75% | 85-90% | ✅ 20% ↑ |
| **Memory Safety** | Runtime checks | Compile-time | ✅ 100% |
| **Binary Size** | ~500MB (Python+deps) | ~50MB (static) | ✅ 90% ↓ |
| **Startup Time** | ~5-8s | ~500ms | ✅ 90% ↓ |

---

## 📂 Cấu trúc thư mục

```
app-gpu/
├── Cargo.toml                    # Rust workspace root
├── Dockerfile                    # Multi-stage build (Rust + CUDA)
├── README.md                     # Hướng dẫn sử dụng
├── ARCHITECTURE.md               # Tài liệu này
├── LICENSE                       # Giấy phép
│
├── crates/                       # Rust crates (module)
│   ├── core/                     # Core system (singleton orchestrator)
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── main.rs           # Entry point
│   │       ├── config.rs         # Configuration management
│   │       ├── plugin_loader.rs  # Plugin dynamic loading
│   │       ├── event_bus.rs      # Internal event bus (pub/sub)
│   │       └── telemetry.rs      # Metrics & observability
│   │
│   ├── gpu-executor/             # GPU Execution Engine
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs            # Plugin interface
│   │       ├── cuda_wrapper.rs   # CUDA API bindings (cudarc/inline CUDA)
│   │       ├── nvml_control.rs   # NVML control (power, clocks, temp)
│   │       ├── mining_kernel.rs  # Mining workload dispatcher
│   │       └── health_monitor.rs # GPU health tracking
│   │
│   ├── cloaking/                 # GPU Cloaking System
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs            # Plugin interface
│   │       ├── strategy_engine.rs    # Strategy selection & execution
│   │       ├── pattern_generator.rs  # AI-like workload patterns
│   │       ├── vram_balloning.rs     # VRAM allocation rotation
│   │       ├── power_modulation.rs   # Power variance injection
│   │       └── metrics_masking.rs    # Performance counter obfuscation
│   │
│   ├── resource-manager/         # Resource Management
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs            # Plugin interface
│   │       ├── qos_controller.rs # QoS limits (CPU/GPU/Network)
│   │       ├── scheduler.rs      # Task scheduling (priority queue)
│   │       ├── backpressure.rs   # Load shedding & throttling
│   │       └── numa_aware.rs     # NUMA-aware memory allocation
│   │
│   ├── security/                 # Security Hardening
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs            # Plugin interface
│   │       ├── tls_manager.rs    # mTLS certificate management
│   │       ├── secrets_vault.rs  # Encrypted secrets storage
│   │       ├── audit_logger.rs   # Security event logging
│   │       └── integrity_check.rs # Binary/plugin signature verification
│   │
│   ├── ffi-bindings/             # FFI Bindings (Rust ↔ C/C++)
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── cuda_ffi.rs       # CUDA Runtime/Driver API
│   │       └── nvml_ffi.rs       # NVML bindings
│   │
│   └── common/                   # Shared utilities
│       ├── Cargo.toml
│       └── src/
│           ├── lib.rs
│           ├── types.rs          # Common types (GPUMetrics, ProcessInfo)
│           ├── error.rs          # Error handling (thiserror/anyhow)
│           ├── logging.rs        # Structured logging (tracing)
│           └── ipc.rs            # IPC primitives (shared memory, channels)
│
├── go-services/                  # Go microservices (optional)
│   ├── monitoring-agent/         # Prometheus exporter
│   │   ├── go.mod
│   │   └── main.go
│   └── orchestrator/             # External orchestration API
│       ├── go.mod
│       └── main.go
│
├── cuda-kernels/                 # Custom CUDA kernels (C++/CUDA)
│   ├── CMakeLists.txt
│   ├── mining_kernel.cu          # Optimized mining kernel
│   ├── dummy_kernel.cu           # Cloaking dummy workload
│   └── memory_bandwidth_test.cu  # Benchmark kernel
│
├── config/                       # Configuration files
│   ├── app-gpu.toml              # Main config (TOML)
│   ├── gpu-profiles.json         # GPU optimization profiles
│   ├── cloaking-strategies.json  # Cloaking strategy definitions
│   └── security-policy.yaml      # Security policies
│
├── scripts/                      # Deployment & utility scripts
│   ├── build.sh                  # Build script (cross-compilation)
│   ├── deploy.sh                 # Deployment automation
│   ├── benchmark.sh              # Performance benchmarking
│   └── obfuscate.sh              # Binary obfuscation (UPX/strip)
│
├── tests/                        # Integration tests
│   ├── unit/                     # Unit tests (Rust #[cfg(test)])
│   ├── integration/              # Integration tests
│   │   ├── gpu_smoke_test.rs
│   │   └── cloaking_validation.rs
│   └── performance/              # Performance benchmarks
│       ├── latency_test.rs
│       └── throughput_test.rs
│
└── docs/                         # Documentation
    ├── deployment.md             # Deployment guide
    ├── configuration.md          # Configuration reference
    ├── plugin-development.md     # Plugin development guide
    └── api-reference.md          # API documentation (rustdoc)
```

---

## 🔌 Plugin Architecture

### Plugin Interface (Rust trait)

```rust
/// Plugin trait - tất cả plugin phải implement
pub trait Plugin: Send + Sync {
    /// Plugin metadata
    fn metadata(&self) -> PluginMetadata;
    
    /// Initialize plugin with config
    fn init(&mut self, config: &Config) -> Result<()>;
    
    /// Start plugin (non-blocking)
    fn start(&self) -> Result<()>;
    
    /// Stop plugin gracefully
    fn stop(&self) -> Result<()>;
    
    /// Health check
    fn health(&self) -> HealthStatus;
}

/// GPU Executor Plugin Interface
pub trait GPUExecutorPlugin: Plugin {
    fn submit_mining_task(&self, task: MiningTask) -> Result<TaskHandle>;
    fn get_gpu_metrics(&self) -> Result<GPUMetrics>;
    fn set_power_limit(&self, watts: u32) -> Result<()>;
}

/// Cloaking Plugin Interface
pub trait CloakingPlugin: Plugin {
    fn apply_strategy(&self, strategy: CloakStrategy) -> Result<()>;
    fn generate_ai_pattern(&self) -> Result<WorkloadPattern>;
    fn inject_noise(&self, target: NoiseTarget) -> Result<()>;
}
```

### Plugin Lifecycle

```
[Load] → [Init] → [Start] → [Running] → [Stop] → [Unload]
   ↓        ↓         ↓          ↓          ↓         ↓
Static  Config   Spawn    Event Loop   Graceful  Cleanup
Linking  Parsing  Threads  Processing   Shutdown  Resources
```

---

## 🚀 Event Bus Architecture

### Internal Communication

```
┌──────────────────────────────────────────────────────────┐
│                      Event Bus (MPSC)                     │
│  ┌────────────────────────────────────────────────────┐  │
│  │  crossbeam-channel (bounded, backpressure-aware)   │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
         ↑              ↑              ↑              ↑
         │              │              │              │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │  GPU    │   │ Cloaking│   │Resource │   │Security │
    │Executor │   │ System  │   │ Manager │   │ Module  │
    └─────────┘   └─────────┘   └─────────┘   └─────────┘
         │              │              │              │
         └──────────────┴──────────────┴──────────────┘
                       Event Publishers
```

### Event Types

```rust
pub enum SystemEvent {
    // GPU Events
    GPUMetricsUpdated { gpu_id: u32, metrics: GPUMetrics },
    MiningTaskCompleted { task_id: u64, result: MiningResult },
    
    // Cloaking Events
    StrategyApplied { strategy: CloakStrategy },
    PatternGenerated { pattern: WorkloadPattern },
    
    // Resource Events
    BackpressureTriggered { level: PressureLevel },
    QoSViolation { resource: ResourceType, actual: f64, limit: f64 },
    
    // Security Events
    SecurityAlert { severity: AlertSeverity, message: String },
    IntegrityCheckFailed { component: String },
}
```

---

## 🔐 Security Architecture

### Defense-in-Depth Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 7: Binary Obfuscation (UPX packing, symbol stripping) │
├─────────────────────────────────────────────────────────────┤
│ Layer 6: Runtime Integrity (plugin signature verification)  │
├─────────────────────────────────────────────────────────────┤
│ Layer 5: Memory Safety (Rust ownership, bounds checking)    │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: Encrypted Secrets (sled-encrypted, AES-256-GCM)    │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: mTLS Communication (rustls, ed25519 certs)         │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Privilege Separation (CAP_SYS_ADMIN drop after init)│
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Sandboxing (seccomp-bpf, namespace isolation)      │
└─────────────────────────────────────────────────────────────┘
```

### Threat Model

| Threat | Mitigation | Status |
|--------|-----------|--------|
| **Memory corruption** | Rust memory safety | ✅ Built-in |
| **Supply chain attack** | Plugin signing, SBOM | ✅ Implemented |
| **Credential theft** | Encrypted vault, no plaintext | ✅ Implemented |
| **Side-channel timing** | Constant-time crypto (subtle crate) | ✅ Implemented |
| **Reverse engineering** | Obfuscation, anti-debug | ✅ Scripts provided |

---

## 📊 Performance Optimization

### Critical Path Analysis

```
[Submit Mining Task]
         ↓
   [Validate Task]  ← 100µs (in-memory check)
         ↓
 [Acquire GPU Lock]  ← 50µs (RwLock, uncontended)
         ↓
 [Dispatch to CUDA]  ← 500µs (kernel launch)
         ↓
  [CUDA Execution]   ← 10-50ms (actual mining work)
         ↓
 [Collect Metrics]   ← 200µs (NVML queries)
         ↓
   [Emit Event]      ← 50µs (channel send)
```

**Total Overhead**: ~900µs (~0.9ms)  
**Target**: <2ms end-to-end (P95)

### Memory Layout Optimization

- **NUMA-aware allocation**: Bind GPU memory to nearest CPU socket
- **Hugepages**: 2MB pages for large buffers (reduce TLB misses)
- **Zero-copy IPC**: Shared memory regions via `mmap` + `memfd`

---

## 🧪 Testing Strategy

### Test Pyramid

```
         /\
        /  \       E2E Tests (5%)
       /────\      - Full system smoke tests
      /      \     - Deployment validation
     /────────\    
    /  Integration\ Integration Tests (15%)
   /     Tests    \  - Plugin interaction
  /────────────────\ - GPU mock tests
 /   Unit Tests     \ Unit Tests (80%)
/      (80%)        \  - Pure functions
────────────────────── - Error handling
```

### Performance Benchmarks

```bash
# Latency benchmark
cargo bench --bench latency_test

# Throughput benchmark  
cargo bench --bench throughput_test

# GPU utilization stress test
./scripts/benchmark.sh --stress-gpu --duration=300s
```

**Acceptance Criteria**:
- P95 latency < 2ms ✅
- GPU utilization > 85% ✅
- No memory leaks in 24h run ✅
- Race condition detection: 0 (via `cargo miri test`) ✅

---

## 📦 Deployment

### Build Process

```bash
# 1. Build Rust core (release mode, LTO, strip symbols)
cargo build --release --target x86_64-unknown-linux-gnu

# 2. Build CUDA kernels
cd cuda-kernels && cmake -DCMAKE_BUILD_TYPE=Release . && make

# 3. Obfuscate binary (optional)
./scripts/obfuscate.sh target/release/app-gpu

# 4. Build Docker image
docker build -t app-gpu:latest -f Dockerfile .
```

### Docker Multi-Stage Build

```dockerfile
# Stage 1: Rust builder
FROM rust:1.75-slim AS rust-builder
RUN cargo build --release

# Stage 2: CUDA builder  
FROM nvidia/cuda:12.0.0-devel-ubuntu22.04 AS cuda-builder
COPY cuda-kernels/ /build
RUN cmake . && make

# Stage 3: Runtime (slim)
FROM nvidia/cuda:12.0.0-base-ubuntu22.04
COPY --from=rust-builder /app/target/release/app-gpu /usr/local/bin/
COPY --from=cuda-builder /build/*.so /usr/local/lib/
CMD ["/usr/local/bin/app-gpu", "--config", "/etc/app-gpu/config.toml"]
```

**Final Image Size**: ~200MB (vs 2GB Python image)

---

## 🔄 Migration Path (Python → Rust)

### Phase 1: Core Infrastructure (Week 1-2)
- ✅ Project setup (Cargo workspace)
- ✅ Plugin loader & event bus
- ✅ Configuration management
- ✅ Telemetry & logging

**DoD**: Core binary starts, loads config, plugins can register

### Phase 2: GPU Executor (Week 3-4)
- ✅ CUDA bindings (cudarc)
- ✅ NVML control (nvml-wrapper)
- ✅ Mining kernel dispatcher
- ✅ Health monitoring

**DoD**: Can submit mining tasks, GPU metrics collected

### Phase 3: Cloaking System (Week 5-6)
- ✅ Strategy engine port
- ✅ Pattern generator (AI-like)
- ✅ VRAM ballooning
- ✅ Power modulation

**DoD**: Cloaking strategies apply correctly, metrics masked

### Phase 4: Integration & Hardening (Week 7-8)
- ✅ End-to-end tests
- ✅ Performance benchmarks
- ✅ Security audit
- ✅ Documentation

**DoD**: Production-ready, benchmarks passed, docs complete

---

## 📈 Metrics & Observability

### Prometheus Metrics (via Go exporter)

```
# GPU Metrics
app_gpu_utilization_percent{gpu_id="0"} 87.5
app_gpu_temperature_celsius{gpu_id="0"} 72.0
app_gpu_power_watts{gpu_id="0"} 245.0

# Mining Metrics
app_mining_hashrate_mhs{pool="stratum+tcp://..."} 125.3
app_mining_accepted_shares_total 1523
app_mining_rejected_shares_total 2

# System Metrics
app_latency_seconds{operation="submit_task",quantile="0.95"} 0.0018
app_throughput_ops_per_second{resource="gpu_executor"} 14250
```

### Tracing (via tokio-tracing)

```rust
#[instrument(skip(self))]
async fn submit_mining_task(&self, task: MiningTask) -> Result<TaskHandle> {
    let span = info_span!("submit_mining_task", task_id = %task.id);
    let _enter = span.enter();
    
    debug!("Validating task");
    self.validate_task(&task)?;
    
    debug!("Acquiring GPU lock");
    let gpu = self.gpu_pool.acquire().await?;
    
    info!("Dispatching to GPU");
    gpu.dispatch(task).await
}
```

---

## 🔧 Troubleshooting

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| **CUDA not found** | `libcuda.so.1: cannot open` | Install NVIDIA drivers, set `LD_LIBRARY_PATH` |
| **Plugin load fail** | `Plugin signature mismatch` | Regenerate plugin signatures: `./scripts/sign-plugins.sh` |
| **Low GPU util** | <70% utilization | Check QoS limits, increase batch size in config |
| **High latency** | P95 >10ms | Enable hugepages, check CPU frequency governor |

---

## 📚 References

- **Rust CUDA**: https://github.com/Rust-GPU/Rust-CUDA
- **cudarc**: https://github.com/coreylowman/cudarc
- **nvml-wrapper**: https://github.com/Cldfire/nvml-wrapper
- **Cargo Workspace**: https://doc.rust-lang.org/book/ch14-03-cargo-workspaces.html

---

**Version**: 1.0.0  
**Last Updated**: 2025-09-29  
**Maintainer**: GPU Systems Architecture Team
