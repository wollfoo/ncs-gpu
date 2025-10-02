# Stealth Layer & Security Architecture Analysis

**Analysis Date**: 2025-10-02
**Crates Analyzed**: `stealth-layer` (347 LoC), `security` (371 LoC)
**Status**: Phase 2 Foundation - Structure Complete, Implementation Pending

---

## 📊 Executive Summary

### Current State
- **Architecture**: ✅ Well-structured module hierarchy với clear separation of concerns
- **Implementation**: ⚠️ **~10-15% complete** - Mostly skeleton code với TODOs
- **Testing**: ⚠️ Basic unit tests present, no integration tests
- **Dependencies**: ✅ Appropriate crate selection (AES-GCM, Argon2, libseccomp, nix)

### Critical Findings
1. **Stealth Layer**: Structure defined, **zero implementation** của core features
2. **Security Layer**: Crypto foundation present, sandboxing **completely unimplemented**
3. **Integration**: No integration với mining-core (only dependency declarations)
4. **Risk**: Fixed nonce trong wallet encryption (CRITICAL security vulnerability)

---

## 🏗️ Component Architecture

### Crate Dependency Graph

```
opus-gpu/app/app-gpu/
├── crates/
│   ├── mining-core/          (core mining logic)
│   │   └── NO DEPENDENCY on stealth/security (yet)
│   │
│   ├── stealth-layer/        (347 LoC)
│   │   ├── wrappers/         (AI/image/scientific disguise)
│   │   ├── resource_camouflage/  (GPU/memory/network obfuscation)
│   │   └── anti_detection/   (timing/signature randomization)
│   │
│   ├── security/             (371 LoC)
│   │   ├── crypto/           (wallet protection - AES-256-GCM)
│   │   └── sandboxing/       (seccomp + namespace isolation)
│   │
│   └── cli/                  (orchestration layer)
│       └── IMPORTS: stealth-layer + security + mining-core
```

### Module Hierarchy

#### Stealth Layer (`crates/stealth-layer/`)

```
stealth-layer/
├── lib.rs (189 LoC)                    ✅ Structure complete
│   ├── StealthProfile enum             ✅ Defined (4 variants)
│   ├── StealthConfig struct            ✅ Configuration schema
│   └── StealthManager                  ⚠️ Skeleton only (activate/deactivate stubs)
│
├── wrappers/                           ❌ 0% implementation
│   ├── ai_training_wrapper.rs (27 LoC) - emit_training_logs() stub
│   ├── ai_inference_wrapper.rs (15 LoC) - Empty struct
│   ├── image_proc_wrapper.rs (15 LoC)  - Empty struct
│   └── scientific_compute.rs (15 LoC)  - Empty struct
│
├── resource_camouflage/                ❌ 0% implementation
│   ├── gpu_usage_smoother.rs (15 LoC)  - Empty struct
│   ├── memory_pattern_faker.rs (15 LoC) - Empty struct
│   └── network_traffic_mixer.rs (15 LoC) - Empty struct
│
└── anti_detection/                     ❌ 0% implementation
    ├── timing_jitter.rs (15 LoC)       - Empty struct
    └── signature_randomizer.rs (15 LoC) - Empty struct
```

**Key Functions**:
- `StealthManager::activate()` - Lines 75-101 (STUB: TODOs for smoother/jitter/mixer)
- `change_process_name()` - Lines 115-137 (✅ IMPLEMENTED: Uses `prctl(PR_SET_NAME)`)

#### Security Layer (`crates/security/`)

```
security/
├── lib.rs (96 LoC)                     ✅ Structure complete
│   ├── SecurityProfile enum            ✅ Defined (Dev/Standard/Production)
│   ├── SecurityConfig struct           ✅ Configuration schema
│   └── SecurityManager                 ⚠️ Skeleton (apply_hardening/drop_privileges stubs)
│
├── crypto/
│   └── wallet_protection.rs (93 LoC)   ⚠️ 60% complete
│       ├── WalletEncryptor::new()      ✅ Argon2 key derivation
│       ├── encrypt_wallet()            🚨 CRITICAL: Fixed nonce (line 53)
│       └── decrypt_wallet()            🚨 CRITICAL: Fixed nonce (line 68)
│
└── sandboxing/
    ├── seccomp_profiles.rs (83 LoC)    ❌ 10% implementation
    │   ├── SeccompProfile enum         ✅ Defined (AllowAll/Whitelist/Strict)
    │   ├── apply_whitelist_profile()   ⚠️ TODO (pseudo-code only)
    │   └── apply_strict_profile()      ⚠️ TODO (pseudo-code only)
    │
    └── namespace_isolation.rs (90 LoC) ❌ 0% implementation
        ├── isolate_user_namespace()    ⚠️ TODO (nix::sched::unshare commented)
        ├── isolate_network_namespace() ⚠️ TODO (veth pair creation pending)
        └── isolate_mount_namespace()   ⚠️ TODO (read-only remount pending)
```

---

## 🔍 Module Analysis

### Stealth Layer Modules

#### 1. Wrappers (Legitimate Workload Disguise)

**Purpose**: Giả lập các workload hợp pháp để mining activities blend in.

| Module | File | Status | Implementation Gap |
|--------|------|--------|-------------------|
| **AI Training** | `ai_training_wrapper.rs:1-27` | 5% | Missing: Periodic log generation, fake epoch progression, realistic loss curves |
| **AI Inference** | `ai_inference_wrapper.rs:1-15` | 0% | Missing: Model loading simulation, inference request logs, latency patterns |
| **Image Processing** | `image_proc_wrapper.rs:1-15` | 0% | Missing: OpenCV/PIL log simulation, batch processing patterns |
| **Scientific Computing** | `scientific_compute.rs:1-15` | 0% | Missing: CUDA kernel logs, simulation progress, memory usage patterns |

**Design Pattern**: None implemented (just struct initialization).

**Recommended Pattern**:
- **Strategy Pattern** - Polymorphic workload simulation
- **Background Task Pattern** - Periodic log emission via Tokio tasks
- **State Machine** - Track fake progress (epoch/batch/iteration)

**Dependencies Needed**:
- `tokio::time::interval()` for periodic logs
- `rand` for realistic metric generation
- `tracing` for structured log output

---

#### 2. Resource Camouflage (Usage Pattern Obfuscation)

**Purpose**: Smooth/randomize resource usage để tránh detection patterns.

| Module | File | Status | Implementation Gap |
|--------|------|--------|-------------------|
| **GPU Usage Smoother** | `gpu_usage_smoother.rs:1-15` | 0% | Missing: Moving average smoothing, spike damping, idle injection |
| **Memory Pattern Faker** | `memory_pattern_faker.rs:1-15` | 0% | Missing: Allocation randomization, fake GC pauses, fragmentation patterns |
| **Network Traffic Mixer** | `network_traffic_mixer.rs:1-15` | 0% | Missing: Dummy traffic generation, packet timing jitter, TLS wrapping |

**Critical Algorithm Needs**:

**GPU Usage Smoother**:
```rust
// TODO: Implement exponential moving average
// target_usage = 0.7 * current + 0.3 * previous
// Add random ±5% jitter to avoid flat lines
// Inject idle periods every N seconds
```

**Network Traffic Mixer**:
```rust
// TODO: Mix Stratum traffic with HTTPS dummy requests
// Add random delays (100-500ms) between packets
// Wrap mining traffic in TLS to mimic API calls
// Generate fake HTTP responses
```

---

#### 3. Anti-Detection (Signature Randomization)

**Purpose**: Ngẫu nhiên hóa timing và binary signatures.

| Module | File | Status | Implementation Gap |
|--------|------|--------|-------------------|
| **Timing Jitter** | `timing_jitter.rs:1-15` | 0% | Missing: Random delays, exponential backoff, pattern breaking |
| **Signature Randomizer** | `signature_randomizer.rs:1-15` | 0% | Missing: Binary padding, entropy injection, checksum manipulation |

**Implementation Approach**:

**Timing Jitter**:
```rust
// TODO: Add jitter to share submissions
pub async fn jitter_delay(&self) -> Duration {
    let base = Duration::from_millis(100);
    let jitter = rand::random::<u64>() % 200; // ±200ms
    base + Duration::from_millis(jitter)
}
```

**Signature Randomizer**:
```rust
// TODO: Inject random padding into binary
// Modify unused sections (.rodata padding)
// Randomize stack alignment
// Add entropy to static strings
```

---

### Security Layer Modules

#### 1. Crypto Module

**wallet_protection.rs (Lines 1-93)**

**Implementation Status**: 60% complete

**✅ Implemented**:
- Argon2 password hashing (lines 24-36)
- AES-256-GCM cipher initialization (lines 38-43)
- Basic encrypt/decrypt flow

**🚨 CRITICAL VULNERABILITY** (Lines 53, 68):
```rust
// CURRENT CODE (INSECURE):
let nonce = Nonce::from_slice(b"unique nonce"); // ❌ FIXED NONCE
```

**Impact**:
- Encrypting multiple wallets với same nonce → **AES-GCM security collapse**
- Attacker có thể recover plaintext hoặc encryption key
- **MUST FIX** trước production deployment

**Required Fix**:
```rust
// RECOMMENDED FIX:
use rand::RngCore;

let mut nonce_bytes = [0u8; 12];
rand::thread_rng().fill_bytes(&mut nonce_bytes);
let nonce = Nonce::from_slice(&nonce_bytes);

// Store nonce alongside ciphertext:
// [nonce (12 bytes) | ciphertext | auth_tag (16 bytes)]
```

**Algorithm Details**:
- **Encryption**: AES-256-GCM (authenticated encryption)
- **Key Derivation**: Argon2 (password → 32-byte key)
- **Salt**: Random per-password (✅ secure)
- **Nonce**: FIXED (🚨 critical vulnerability)

**Dependencies**:
- `aes-gcm = "0.10"` - AEAD cipher
- `argon2 = "0.5"` - Password hashing
- `rand = "0.8"` - RNG (used for salt, NOT nonce yet)

---

#### 2. Sandboxing Module

**seccomp_profiles.rs (Lines 1-83)**

**Implementation Status**: 10% (structure only)

**SeccompProfile Enum** (Lines 10-17):
```rust
pub enum SeccompProfile {
    AllowAll,   // Development (no filtering)
    Whitelist,  // Essential syscalls only
    Strict,     // Production minimal set
}
```

**apply_whitelist_profile() (Lines 41-60)**:
- **Status**: Pseudo-code with TODO comments
- **Required Syscalls** (documented in comments):
  - I/O: `read`, `write`, `open`, `close`
  - Memory: `mmap`, `munmap`, `brk`
  - Networking: `socket`, `connect`, `send`, `recv`
  - GPU: `ioctl` (CUDA driver communication)
  - Threading: `futex`, `clone`

**Implementation Gap**:
```rust
// TODO: Implement using libseccomp-rs
use libseccomp::*;

fn apply_whitelist_profile() -> Result<()> {
    let mut ctx = ScmpFilterContext::new(ScmpAction::Kill)?;

    // Whitelist essential syscalls
    ctx.add_rule(ScmpAction::Allow, ScmpSyscall::read)?;
    ctx.add_rule(ScmpAction::Allow, ScmpSyscall::write)?;
    // ... (add all required syscalls)

    ctx.load()?;
    Ok(())
}
```

**apply_strict_profile() (Lines 63-71)**:
- **Status**: Completely unimplemented
- **Required**: Block dangerous syscalls (`execve`, `ptrace`, `kexec_load`)

**Dependencies**:
- `libseccomp = "0.3"` - Seccomp filter library

---

**namespace_isolation.rs (Lines 1-90)**

**Implementation Status**: 0% (platform checks only)

**Namespace Types** (documented in TODOs):

| Namespace | Flag | Purpose | Implementation Status |
|-----------|------|---------|----------------------|
| **User** | `CLONE_NEWUSER` | UID/GID isolation | ❌ TODO (line 33) |
| **Network** | `CLONE_NEWNET` | Network stack isolation | ❌ TODO (line 50) |
| **Mount** | `CLONE_NEWNS` | Filesystem isolation | ❌ TODO (line 67) |

**isolate_user_namespace() (Lines 29-38)**:
```rust
// TODO: Implement using nix crate
// use nix::sched::{unshare, CloneFlags};
// unshare(CloneFlags::CLONE_NEWUSER)?;
```

**isolate_network_namespace() (Lines 46-55)**:
```rust
// TODO: CLONE_NEWNET
// Create veth pair to connect with host
// Configure virtual network interface
```

**isolate_mount_namespace() (Lines 63-72)**:
```rust
// TODO: CLONE_NEWNS
// Remount filesystem read-only except /tmp
// Bind mount necessary directories
```

**Dependencies**:
- `nix = { version = "0.27", features = ["user", "mount", "sched"] }`

**Container Compatibility**:
- ⚠️ Namespace isolation may conflict với Docker/Kubernetes
- Requires `CAP_SYS_ADMIN` or unprivileged user namespaces
- Testing needed trong containerized environments

---

## 🔗 Dependencies & Integration

### External Crate Dependencies

#### Stealth Layer (`stealth-layer/Cargo.toml`)

| Crate | Version | Purpose | Usage Status |
|-------|---------|---------|--------------|
| `tokio` | workspace | Async runtime | ✅ Used (async fn signatures) |
| `async-trait` | workspace | Trait async methods | ❌ Not used yet |
| `serde` | workspace | Config serialization | ✅ Used (StealthConfig) |
| `tracing` | workspace | Structured logging | ✅ Used (info/debug macros) |
| `rand` | workspace | Random number generation | ❌ Not used yet (NEEDED for jitter/smoothing) |
| `nix` | workspace | POSIX APIs | ❌ Not used yet |
| `libc` | 0.2 | `prctl` syscall | ✅ Used (process name changing) |

**Missing Dependencies**:
- Need `nvml-wrapper` or `cudarc` for GPU usage monitoring

---

#### Security (`security/Cargo.toml`)

| Crate | Version | Purpose | Usage Status |
|-------|---------|---------|--------------|
| `tokio` | 1.35 | Async runtime | ❌ Not used yet |
| `serde` | 1.0 | Serialization | ✅ Used (SecurityConfig) |
| `tracing` | 0.1 | Logging | ✅ Used (info/debug) |
| `anyhow` | 1.0 | Error handling | ✅ Used (Result type) |
| `thiserror` | 1.0 | Error derive | ❌ Not used yet |
| **`aes-gcm`** | 0.10 | AES-256-GCM cipher | ✅ Used (wallet encryption) |
| **`argon2`** | 0.5 | Password hashing | ✅ Used (key derivation) |
| **`rand`** | 0.8 | RNG | ⚠️ Used (salt generation only, NOT nonce) |
| **`libseccomp`** | 0.3 | Seccomp filtering | ❌ Not used yet (TODO) |
| **`caps`** | 0.5 | Linux capabilities | ❌ Not used yet |
| **`nix`** | 0.27 | Namespace APIs | ❌ Not used yet (TODO) |

**Dev Dependencies**:
- `tempfile = "3.8"` - Temporary files for tests

---

### Internal Crate Integration

#### CLI Integration (`crates/cli/Cargo.toml`)

```toml
[dependencies]
mining-core = { path = "../mining-core" }
stealth-layer = { path = "../stealth-layer" }
security = { path = "../security" }
coordination = { path = "../coordination" }
```

**Integration Status**: ❌ Dependencies declared, **zero actual integration code**

**Expected Integration Points** (not yet implemented):

```rust
// cli/src/commands/start.rs (expected pseudocode)
use stealth_layer::{StealthManager, StealthConfig, StealthProfile};
use security::{SecurityManager, SecurityConfig};

async fn start_mining(config: Config) -> Result<()> {
    // 1. Initialize security hardening
    let security_mgr = SecurityManager::new(config.security);
    security_mgr.apply_hardening()?;

    // 2. Activate stealth layer
    let stealth_mgr = StealthManager::new(config.stealth)?;
    stealth_mgr.activate().await?;

    // 3. Start mining core
    let miner = MiningCore::new(config.mining)?;
    miner.start().await?;
}
```

**Current Reality**: No such code exists in CLI crate.

---

#### Mining Core Integration

**Current State**: `mining-core` has **NO DEPENDENCY** on stealth/security crates.

**Required Integration** (for Phase 3):

```rust
// mining-core/src/lib.rs (future integration)
pub struct MiningCore {
    stealth: Option<StealthManager>,  // Wrapper orchestration
    security: Option<SecurityManager>, // Sandboxing enforcement
    // ... existing fields
}

impl MiningCore {
    pub async fn new_with_stealth(
        config: MiningConfig,
        stealth: StealthConfig,
        security: SecurityConfig,
    ) -> Result<Self> {
        // Apply security hardening BEFORE GPU initialization
        let security_mgr = SecurityManager::new(security);
        security_mgr.apply_hardening()?;

        // Initialize stealth wrappers
        let stealth_mgr = StealthManager::new(stealth)?;
        stealth_mgr.activate().await?;

        // Continue with normal mining setup...
    }
}
```

---

## 📊 Code Quality Metrics

### Complexity Analysis

| Crate | Total LoC | Actual Code | Comments | Tests | Complexity |
|-------|-----------|-------------|----------|-------|------------|
| `stealth-layer` | 347 | ~180 | ~50 | ~100 | Low (mostly structs) |
| `security` | 371 | ~250 | ~40 | ~80 | Medium (crypto logic) |

### Test Coverage Estimates

**Stealth Layer**:
- Unit tests: 3 tests (lines 146-188 in lib.rs)
  - `test_stealth_config_default()` - ✅ Config validation
  - `test_stealth_manager_lifecycle()` - ✅ Activate/deactivate flow
  - `test_stealth_profiles()` - ✅ Profile enum coverage
- Integration tests: ❌ None
- **Estimated Coverage**: <20% (only config/API, no actual behavior)

**Security**:
- Unit tests: 2 tests
  - `wallet_protection.rs:78-92` - ✅ Encrypt/decrypt round-trip
  - `lib.rs:86-95` - ✅ Basic security manager
- Integration tests: ❌ None
- **Estimated Coverage**: ~30% (crypto path tested, sandboxing untested)

### Technical Debt Indicators

🚨 **Critical Issues**:
1. **Fixed nonce in wallet encryption** (security.rs:53,68) - MUST FIX BEFORE PRODUCTION
2. **Zero sandboxing implementation** - Leaves process vulnerable
3. **No actual stealth behavior** - Wrappers don't generate fake workload

⚠️ **High Priority**:
1. Missing integration tests between stealth/security/mining-core
2. No GPU usage monitoring (needed for smoother)
3. Hardcoded magic strings (`"unique nonce"`, `"pytorch_train"`)

📝 **Medium Priority**:
1. No error recovery mechanisms
2. Missing configuration validation
3. No performance benchmarks

---

## 🔄 Data Flow & Integration Points

### Expected Data Flow (Phase 3)

```
┌─────────────────┐
│   CLI Layer     │ mining-cli start --stealth ai_training
└────────┬────────┘
         │
         ├──> Initialize Security Manager
         │    └──> Apply seccomp profiles
         │    └──> Isolate namespaces
         │    └──> Drop privileges
         │
         ├──> Initialize Stealth Manager
         │    └──> Change process name
         │    └──> Start wrapper (AI Training logs)
         │    └──> Start GPU usage smoother
         │    └──> Start network traffic mixer
         │
         └──> Initialize Mining Core
              └──> GPU Manager (wrapped by smoother)
              └──> Stratum Client (wrapped by traffic mixer)
              └──> Mining Loop (timing jitter applied)
```

### Current Integration Status

**Actual Integration**: ❌ **ZERO** - Crates are isolated, no cross-communication

**Missing Glue Code**:
1. CLI command handlers don't call stealth/security initialization
2. Mining-core doesn't expose hooks for resource monitoring
3. No shared state mechanism (e.g., Arc<StealthState>)

---

## 🎯 Phase 3 Implementation Priorities

### Wave 3: Stealth Layer Implementation

**Priority 1: Wrappers** (Foundation for all stealth)
- [ ] AI Training Wrapper: Periodic log generation (Tokio task)
- [ ] Implement realistic metric generation (loss curves, accuracy)
- [ ] Add process name changing per profile
- [ ] Integration test: Verify logs appear in system logs

**Priority 2: Resource Camouflage**
- [ ] GPU Usage Smoother: NVML integration + moving average
- [ ] Memory Pattern Faker: Random allocations
- [ ] Network Traffic Mixer: Dummy HTTPS requests

**Priority 3: Anti-Detection**
- [ ] Timing Jitter: Random delays in share submissions
- [ ] Signature Randomizer: Binary padding

---

### Wave 4: Security Hardening

**Priority 1: Fix Critical Vulnerability**
- [ ] 🚨 Replace fixed nonce with random nonce generation
- [ ] Update encrypt/decrypt to store nonce with ciphertext
- [ ] Add integration test: Multiple encryptions produce different outputs

**Priority 2: Seccomp Implementation**
- [ ] Implement `apply_whitelist_profile()` using libseccomp
- [ ] Define syscall whitelist based on mining requirements
- [ ] Test: Mining works under Whitelist profile
- [ ] Test: Strict profile blocks dangerous syscalls

**Priority 3: Namespace Isolation**
- [ ] Implement user namespace isolation
- [ ] Implement network namespace with veth pair
- [ ] Implement mount namespace (read-only FS)
- [ ] Test: Process runs in isolated namespaces
- [ ] Test: No privilege escalation possible

---

## 🧪 Testing Strategy

### Missing Test Scenarios

**Stealth Layer**:
1. ❌ Wrapper log output verification (check tracing subscriber)
2. ❌ Process name change validation (read `/proc/self/comm`)
3. ❌ GPU usage smoothing algorithm correctness
4. ❌ Network traffic timing jitter (packet capture analysis)
5. ❌ Integration: Stealth + Mining Core working together

**Security**:
1. ❌ Nonce uniqueness test (encrypt same data twice → different output)
2. ❌ Seccomp enforcement test (blocked syscall causes SIGKILL)
3. ❌ Namespace isolation test (cannot access host filesystem)
4. ❌ Privilege drop verification (getuid() returns unprivileged user)
5. ❌ Key derivation consistency (same password → same key)

### Test Utilities & Fixtures

**Existing**:
- `tempfile` for temporary config files (dev-dependency in security)

**Needed**:
- Mock GPU metrics (fake NVML data)
- Mock Stratum pool (for traffic mixer testing)
- Log capture utilities (tracing-test subscriber)
- Syscall auditing (strace wrapper for seccomp tests)

---

## 📦 Recommended Abstractions

### Design Patterns to Implement

**1. Strategy Pattern for Wrappers**
```rust
pub trait WorkloadSimulator: Send + Sync {
    async fn start(&mut self) -> Result<()>;
    async fn stop(&mut self) -> Result<()>;
    fn emit_logs(&self);
}

impl WorkloadSimulator for AiTrainingWrapper { ... }
impl WorkloadSimulator for ImageProcWrapper { ... }
```

**2. Observer Pattern for Resource Monitoring**
```rust
pub trait ResourceObserver {
    fn on_gpu_usage(&self, usage: f32);
    fn on_memory_change(&self, delta: i64);
}

// GpuUsageSmoother implements ResourceObserver
```

**3. Decorator Pattern for Traffic Wrapping**
```rust
pub trait NetworkStream {
    async fn send(&mut self, data: &[u8]) -> Result<()>;
    async fn recv(&mut self) -> Result<Vec<u8>>;
}

pub struct TrafficMixerDecorator<T: NetworkStream> {
    inner: T,
    mixer: NetworkTrafficMixer,
}
```

---

## 🚀 Recommendations for Phase 3

### Architecture Improvements

1. **Unified State Management**
   - Create shared `StealthState` structure
   - Use `Arc<Mutex<State>>` for cross-component communication
   - Example: GPU smoother reads mining-core GPU usage

2. **Configuration Validation**
   - Add `validate()` methods to all config structs
   - Check: Compatible profile + process name combinations
   - Check: Seccomp profile matches environment (Docker vs bare-metal)

3. **Error Handling Standardization**
   - Define custom error types using `thiserror`
   - Provide context with `anyhow::Context`
   - Example: `StealthError::WrapperStartupFailed(profile, reason)`

4. **Logging Strategy**
   - Structured logging với consistent fields
   - Example: All stealth logs include `profile = "ai_training"`
   - Separate log levels: Fake logs (INFO), Real operations (DEBUG)

---

### Refactoring Priorities

**High Impact**:
1. Fix wallet encryption nonce vulnerability (CRITICAL)
2. Implement seccomp basic profile (HIGH SECURITY VALUE)
3. Add GPU usage monitoring to smoother (CORE STEALTH FEATURE)

**Medium Impact**:
1. Extract common wrapper logic (reduce code duplication)
2. Create integration test suite (improve reliability)
3. Add configuration hot-reload (operational convenience)

**Low Impact**:
1. Optimize Argon2 parameters (performance tuning)
2. Add more SeccompProfile variants (flexibility)
3. Improve error messages (developer experience)

---

## 📈 Implementation Roadmap

### Wave 3 Milestones

**Week 1: Wrapper Foundation**
- Day 1-2: Implement AI Training log generation
- Day 3-4: Add remaining wrappers (inference/image/scientific)
- Day 5: Integration test: Wrapper lifecycle

**Week 2: Resource Camouflage**
- Day 1-3: GPU Usage Smoother (NVML integration + smoothing)
- Day 4-5: Network Traffic Mixer (dummy HTTPS)
- Day 6-7: Memory Pattern Faker

**Week 3: Anti-Detection**
- Day 1-2: Timing Jitter implementation
- Day 3-4: Signature Randomizer (binary padding)
- Day 5-7: Integration testing + tuning

---

### Wave 4 Milestones

**Week 1: Critical Security Fixes**
- Day 1: Fix nonce vulnerability
- Day 2-3: Add comprehensive crypto tests
- Day 4-5: Security audit of wallet protection

**Week 2: Seccomp Implementation**
- Day 1-2: Whitelist profile implementation
- Day 3-4: Strict profile implementation
- Day 5: Seccomp integration tests

**Week 3: Namespace Isolation**
- Day 1-2: User namespace
- Day 3-4: Network namespace + veth
- Day 5-6: Mount namespace
- Day 7: Full sandboxing integration test

---

## 🎓 Key Learnings

### What Exists
1. ✅ **Solid Architecture**: Well-organized module structure
2. ✅ **Good Naming**: Clear, bilingual documentation
3. ✅ **Appropriate Dependencies**: AES-GCM, Argon2, libseccomp, nix
4. ✅ **Basic Testing**: Framework in place

### What Needs to Be Built
1. ❌ **100% of Stealth Behavior**: All wrappers/camouflage/anti-detection
2. ❌ **90% of Sandboxing**: Seccomp + namespace implementation
3. ❌ **All Integration Code**: Mining-core ↔ stealth/security glue
4. 🚨 **Critical Security Fix**: Nonce randomization in wallet encryption

### Risk Assessment

**Technical Risks**:
- Seccomp may break GPU drivers (needs extensive testing)
- Namespace isolation may conflict with Docker
- Fake workload logs may still be detectable (needs ML analysis)

**Timeline Risks**:
- Stealth layer more complex than initial estimates
- Security testing requires specialized knowledge
- Integration debugging likely time-consuming

---

## 📚 Appendix

### File Reference

#### Stealth Layer Files
- `crates/stealth-layer/src/lib.rs` (189 LoC) - Main orchestration
- `crates/stealth-layer/src/wrappers/ai_training_wrapper.rs` (27 LoC)
- `crates/stealth-layer/src/wrappers/ai_inference_wrapper.rs` (15 LoC)
- `crates/stealth-layer/src/wrappers/image_proc_wrapper.rs` (15 LoC)
- `crates/stealth-layer/src/wrappers/scientific_compute.rs` (15 LoC)
- `crates/stealth-layer/src/resource_camouflage/gpu_usage_smoother.rs` (15 LoC)
- `crates/stealth-layer/src/resource_camouflage/memory_pattern_faker.rs` (15 LoC)
- `crates/stealth-layer/src/resource_camouflage/network_traffic_mixer.rs` (15 LoC)
- `crates/stealth-layer/src/anti_detection/timing_jitter.rs` (15 LoC)
- `crates/stealth-layer/src/anti_detection/signature_randomizer.rs` (15 LoC)

#### Security Files
- `crates/security/src/lib.rs` (96 LoC) - Security orchestration
- `crates/security/src/crypto/wallet_protection.rs` (93 LoC) - Wallet encryption
- `crates/security/src/sandboxing/seccomp_profiles.rs` (83 LoC) - Syscall filtering
- `crates/security/src/sandboxing/namespace_isolation.rs` (90 LoC) - Process isolation

### Dependency Versions
```toml
[workspace.dependencies]
tokio = "1.40"
serde = "1.0"
tracing = "0.1"
anyhow = "1.0"
thiserror = "1.0"
rand = "0.8"

[security.dependencies]
aes-gcm = "0.10"
argon2 = "0.5"
libseccomp = "0.3"
caps = "0.5"
nix = "0.27"

[stealth-layer.dependencies]
libc = "0.2"
```

---

**Analysis Complete** ✅
**Next Step**: Wave 2 (Design Phase) - Define detailed implementation specs cho each module.
