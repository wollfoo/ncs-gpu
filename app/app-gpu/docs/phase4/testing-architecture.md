# Phase 4 Testing Architecture Design
## Comprehensive Testing Infrastructure for GPU Mining System

**Document Version**: 1.0
**Created**: 2025-10-02
**Project**: Opus GPU Mining Infrastructure
**Phase**: 4 - Testing & Quality Assurance
**Status**: Architecture Design - Ready for Implementation

---

## Executive Summary

Đây là **Testing Architecture Specification** (đặc tả kiến trúc testing – thiết kế hệ thống test) cho Phase 4 của GPU Mining System. Document này thiết kế 3 tầng testing infrastructure:

1. **Integration Tests** - End-to-end workflow validation
2. **GPU Test Harness** - GPU code testing without physical GPUs
3. **Property-based Testing** - Fuzzing critical components

### Current State Analysis

**✅ Existing Test Infrastructure**:
- **Phase 3 Validation Tests**: 8 validation tests trong `tests/phase3-validation/`
  - E2E: Complete system validation (`complete_system_validation.rs`)
  - Integration: Stealth integration tests (`stealth_integration.rs`)
  - Security: Wallet encryption, Seccomp, Namespace validation
  - Stealth: Profile validation tests
  - Resources: Camouflage validation tests
  - Coverage: Benchmarking infrastructure (`coverage_benchmarks.rs`)

- **Unit Tests**: Scattered trong modules
  - `crates/mining-core/src/gpu/manager_tests.rs` (230 lines)
  - `crates/security/tests.rs` (81 lines - wallet encryption)

- **Mock Infrastructure**:
  - `MockStratumPool` - Full Stratum protocol simulation
  - `DockerGPUTester` - GPU container validation

**❌ Missing Test Infrastructure**:
- ❌ **No Integration Tests Directory** - Tests hiện tại trong `phase3-validation/`
- ❌ **No Property-based Testing** - Không có `proptest` dependency
- ❌ **No GPU Test Harness** - Tests chỉ chạy với GPU thật hoặc skip
- ❌ **No Coverage Tracking** - `cargo-tarpaulin` chưa được cài đặt
- ❌ **Limited Test Organization** - Tests không được tổ chức theo layers

**🔶 Test Dependencies Review** (từ `Cargo.toml`):
- ✅ `tokio-test = "0.4"` - Async test utilities
- ✅ `mockall = "0.11"` - Mock generation (chỉ trong mining-core)
- ✅ `assert_matches = "1.5"` - Pattern matching assertions
- ✅ `criterion = "0.5"` - Benchmarking framework
- ❌ **Missing**: `proptest`, `test-case`, `rstest`, `cargo-tarpaulin`

---

## Table of Contents

1. [Integration Tests Architecture](#1-integration-tests-architecture)
2. [GPU Test Harness Strategy](#2-gpu-test-harness-strategy)
3. [Property-based Testing Plan](#3-property-based-testing-plan)
4. [Test Infrastructure Requirements](#4-test-infrastructure-requirements)
5. [Implementation Roadmap](#5-implementation-roadmap)
6. [Success Criteria](#6-success-criteria)

---

## 1. Integration Tests Architecture

**Objective**: Validate end-to-end workflows without requiring full system deployment.

### 1.1 Test Organization Structure

```
tests/
├── integration/                    # NEW: Integration tests directory
│   ├── mod.rs                     # Module definition
│   ├── mining_workflow.rs         # Complete mining workflow tests
│   ├── pool_connection.rs         # Stratum pool connection tests
│   ├── gpu_initialization.rs      # GPU initialization workflow
│   ├── stealth_integration.rs     # Stealth + Mining integration (MOVE from phase3-validation/)
│   └── security_integration.rs    # Security features integration
│
├── phase3-validation/              # KEEP: Phase 3 validation tests
│   ├── e2e/                       # End-to-end system tests
│   ├── security/                  # Security validation
│   ├── stealth/                   # Stealth validation
│   └── resources/                 # Resource validation
│
├── unit/                          # NEW: Centralized unit tests
│   ├── mod.rs
│   ├── config_parsing.rs          # Config parsing tests
│   ├── stratum_protocol.rs        # Protocol parsing tests
│   └── crypto_tests.rs            # Cryptography tests
│
└── fixtures/                      # NEW: Shared test fixtures
    ├── mod.rs
    ├── mock_pool.rs               # Mock Stratum pool
    ├── test_configs.rs            # Test configuration files
    └── gpu_emulator.rs            # GPU emulation for tests
```

### 1.2 Integration Test Scenarios

#### **Scenario 1: Miner Startup Workflow**

**Test**: `tests/integration/mining_workflow.rs::test_miner_startup_to_ready_state`

**Steps**:
1. ✅ Parse configuration file
2. ✅ Initialize GPU Manager (with mock GPU)
3. ✅ Apply security policies (seccomp, namespaces)
4. ✅ Start stealth profiles
5. ✅ Verify system ready state
6. ✅ Cleanup resources

**Test Fixtures Required**:
- Valid test configuration (`test_config.toml`)
- Mock GPU device (via test harness)
- Mock security policies (skip privileged operations in test mode)

**Assertions**:
```rust
#[tokio::test]
async fn test_miner_startup_to_ready_state() {
    let config = load_test_config("valid_mining_config.toml");
    let mut miner = MiningSystem::new_with_mock_gpu(config).await.unwrap();

    // Initialize all components
    let result = miner.initialize().await;
    assert!(result.is_ok(), "Miner initialization failed: {:?}", result.err());

    // Verify ready state
    assert!(miner.is_initialized(), "Miner not initialized");
    assert_eq!(miner.gpu_count(), 1, "Expected 1 GPU");
    assert!(miner.stealth_layer_active(), "Stealth layer not active");
    assert!(miner.security_enabled(), "Security policies not applied");

    // Cleanup
    miner.shutdown().await.unwrap();
}
```

**Expected Duration**: <5 seconds

---

#### **Scenario 2: Pool Connection & Authentication**

**Test**: `tests/integration/pool_connection.rs::test_pool_connection_authentication_job_reception`

**Steps**:
1. ✅ Start mock Stratum pool server (`MockStratumPool`)
2. ✅ Connect miner to pool
3. ✅ Send `mining.subscribe` message
4. ✅ Send `mining.authorize` message
5. ✅ Receive `mining.notify` (job assignment)
6. ✅ Validate job parameters
7. ✅ Verify connection state

**Test Fixtures Required**:
- `MockStratumPool` (already exists in `complete_system_validation.rs`)
- Test wallet address
- Test worker credentials

**Assertions**:
```rust
#[tokio::test]
async fn test_pool_connection_authentication_job_reception() {
    // Start mock pool
    let mock_pool = MockStratumPool::start(3334).await.unwrap();

    // Create Stratum client
    let mut client = StratumClient::new("stratum+tcp://127.0.0.1:3334");

    // Connect and authenticate
    client.connect().await.unwrap();
    let subscribe_result = client.subscribe("TestMiner/1.0").await;
    assert!(subscribe_result.is_ok(), "Subscribe failed");

    let auth_result = client.authorize("test.worker", "password").await;
    assert!(auth_result.is_ok(), "Authorization failed");

    // Wait for job
    let job = client.wait_for_job(Duration::from_secs(5)).await;
    assert!(job.is_some(), "No job received from pool");

    let job = job.unwrap();
    assert!(!job.job_id.is_empty(), "Job ID is empty");
    assert_eq!(job.target_difficulty, 1.0, "Unexpected difficulty");

    // Cleanup
    client.disconnect().await.unwrap();
    mock_pool.stop().await;
}
```

**Expected Duration**: <3 seconds

---

#### **Scenario 3: Share Submission & Validation**

**Test**: `tests/integration/mining_workflow.rs::test_share_submission_validation_acceptance`

**Steps**:
1. ✅ Connect to mock pool
2. ✅ Receive mining job
3. ✅ Generate valid share (mock GPU mining)
4. ✅ Submit share via `mining.submit`
5. ✅ Wait for acceptance/rejection response
6. ✅ Validate share count metrics

**Test Fixtures Required**:
- `MockStratumPool` with share validation
- Mock share generator (GPU emulation)

**Assertions**:
```rust
#[tokio::test]
async fn test_share_submission_validation_acceptance() {
    let mock_pool = MockStratumPool::start(3335).await.unwrap();
    let mut client = StratumClient::new("stratum+tcp://127.0.0.1:3335");

    // Setup connection
    client.connect().await.unwrap();
    client.subscribe("TestMiner").await.unwrap();
    client.authorize("worker", "pass").await.unwrap();

    // Get job
    let job = client.wait_for_job(Duration::from_secs(5)).await.unwrap();

    // Generate valid share (mock)
    let share = MockGpuEmulator::generate_valid_share(&job);

    // Submit share
    let submit_result = client.submit_share(&share).await;
    assert!(submit_result.is_ok(), "Share submission failed: {:?}", submit_result.err());

    // Verify pool received share
    tokio::time::sleep(Duration::from_millis(100)).await;
    let shares_received = mock_pool.get_submitted_shares().await;
    assert_eq!(shares_received, 1, "Pool did not receive share");

    // Cleanup
    client.disconnect().await.unwrap();
    mock_pool.stop().await;
}
```

**Expected Duration**: <5 seconds

---

### 1.3 Integration Test Utilities

#### **Shared Mock Infrastructure**

**File**: `tests/fixtures/mock_pool.rs`

```rust
/// Mock Stratum pool for integration testing
///
/// Features:
/// - Full Stratum protocol support (subscribe, authorize, notify, submit)
/// - Share validation (check nonce, extranonce, job_id)
/// - Difficulty adjustment simulation
/// - Latency simulation (network delay)
pub struct MockStratumPool {
    port: u16,
    listener: Option<TcpListener>,
    server_task: Option<JoinHandle<()>>,
    received_shares: Arc<RwLock<Vec<StratumShare>>>,
    config: MockPoolConfig,
}

pub struct MockPoolConfig {
    /// Simulate network latency (milliseconds)
    pub latency_ms: u64,

    /// Accept/reject rate (0.0-1.0)
    pub acceptance_rate: f32,

    /// Initial difficulty
    pub initial_difficulty: f32,

    /// Job generation interval (seconds)
    pub job_interval_secs: u64,
}

impl MockStratumPool {
    pub async fn start(port: u16) -> Result<Self> { /* ... */ }
    pub async fn stop(&mut self) { /* ... */ }
    pub async fn get_submitted_shares(&self) -> Vec<StratumShare> { /* ... */ }
    pub async fn get_acceptance_rate(&self) -> f32 { /* ... */ }
}
```

**File**: `tests/fixtures/test_configs.rs`

```rust
/// Generate test configuration files
pub fn generate_test_config(scenario: &str) -> String {
    match scenario {
        "minimal" => r#"
[mining]
algorithm = "ethash"
pool_url = "stratum+tcp://127.0.0.1:3334"

[mining.gpu]
devices = [0]
threads_per_gpu = 512
"#.to_string(),

        "full_stealth" => r#"
[mining]
algorithm = "ethash"
pool_url = "stratum+tcp://127.0.0.1:3334"

[stealth]
enabled = true

[stealth.profiles]
enabled = ["ai_training", "ai_inference"]

[security]
enable_seccomp = true
enable_namespaces = true

[camouflage]
gpu_smoother_enabled = true
memory_faker_enabled = true
network_mixer_enabled = true
"#.to_string(),

        _ => panic!("Unknown test config scenario: {}", scenario)
    }
}

/// Load test configuration file
pub fn load_test_config(filename: &str) -> MiningConfig {
    let config_path = format!("tests/fixtures/configs/{}", filename);
    let config_str = std::fs::read_to_string(&config_path)
        .unwrap_or_else(|_| panic!("Failed to load test config: {}", filename));

    toml::from_str(&config_str)
        .unwrap_or_else(|e| panic!("Failed to parse test config {}: {}", filename, e))
}
```

---

## 2. GPU Test Harness Strategy

**Challenge**: Testing GPU code requires physical NVIDIA GPUs, which are not available in CI/CD environments.

**Solution**: 3-tier testing strategy.

### 2.1 GPU Testing Tiers

#### **Tier 1: Mock GPU for Unit Tests** (No GPU Required)

**Implementation**: Mock `GpuManager` using `mockall` crate.

**File**: `tests/fixtures/gpu_emulator.rs`

```rust
use mockall::predicate::*;
use mockall::mock;

mock! {
    pub GpuManager {
        pub async fn enumerate_devices(&self) -> Result<Vec<GpuDevice>>;
        pub async fn initialize_for_algorithm(&self, algo: GpuAlgorithm, device_ids: &[usize]) -> Result<()>;
        pub async fn is_initialized(&self) -> bool;
        pub async fn cleanup(&self) -> Result<()>;
        pub async fn get_mining_stats(&self) -> Result<GpuManagerStats>;
        pub async fn start_monitoring_loop(&self) -> Result<()>;
        pub async fn stop_monitoring_loop(&self) -> Result<()>;
    }
}

/// GPU emulator for integration tests
///
/// Simulates GPU behavior without requiring physical hardware:
/// - Fake device enumeration (returns configurable device count)
/// - Simulated mining (generates fake shares at target hashrate)
/// - Thermal simulation (returns fake temperature values)
/// - Memory management simulation
pub struct GpuEmulator {
    device_count: usize,
    simulated_hashrate: f64, // MH/s
    simulated_temperature: f32, // Celsius
    config: GpuEmulatorConfig,
}

pub struct GpuEmulatorConfig {
    /// Number of virtual GPUs to emulate
    pub device_count: usize,

    /// Target hashrate per GPU (MH/s)
    pub hashrate_per_gpu: f64,

    /// Simulated temperature range (min, max) Celsius
    pub temperature_range: (f32, f32),

    /// Simulated memory per GPU (GB)
    pub memory_per_gpu: usize,

    /// Share generation interval (milliseconds)
    pub share_interval_ms: u64,
}

impl GpuEmulator {
    pub fn new(config: GpuEmulatorConfig) -> Self { /* ... */ }

    /// Enumerate fake GPU devices
    pub async fn enumerate_devices(&self) -> Result<Vec<GpuDevice>> {
        let mut devices = Vec::new();
        for i in 0..self.device_count {
            devices.push(GpuDevice {
                device_id: i,
                name: format!("Emulated RTX 3080 #{}", i),
                compute_capability: (8, 6),
                memory_total: self.config.memory_per_gpu * 1024 * 1024 * 1024, // GB to bytes
                temperature: self.simulated_temperature,
                utilization: 0.0,
            });
        }
        Ok(devices)
    }

    /// Generate fake valid share
    pub fn generate_valid_share(&self, job: &StratumJob) -> StratumShare {
        StratumShare {
            job_id: job.job_id.clone(),
            worker_name: "test.worker".to_string(),
            extranonce2: "11223344".to_string(),
            ntime: "aabbccdd".to_string(),
            nonce: format!("{:08x}", rand::random::<u32>()),
            // Generate fake but valid-looking hash
            hash: blake3::hash(format!("{}{}", job.job_id, rand::random::<u64>()).as_bytes())
                .to_hex()
                .to_string(),
        }
    }

    /// Simulate mining for duration and return share count
    pub async fn simulate_mining(&self, duration: Duration) -> usize {
        let target_shares = (duration.as_secs() * 1000 / self.config.share_interval_ms) as usize;
        tokio::time::sleep(duration).await;
        target_shares
    }
}
```

**Usage Example**:
```rust
#[tokio::test]
async fn test_gpu_initialization_with_emulator() {
    let emulator = GpuEmulator::new(GpuEmulatorConfig {
        device_count: 2,
        hashrate_per_gpu: 100.0,
        temperature_range: (60.0, 75.0),
        memory_per_gpu: 10,
        share_interval_ms: 1000,
    });

    // Test device enumeration
    let devices = emulator.enumerate_devices().await.unwrap();
    assert_eq!(devices.len(), 2);
    assert_eq!(devices[0].name, "Emulated RTX 3080 #0");
}
```

---

#### **Tier 2: Nightly GPU Integration Tests** (Requires GPU)

**Strategy**: Run full GPU tests on nightly schedule with actual NVIDIA GPUs.

**Infrastructure**: Azure VM with NVIDIA GPU (NC-series).

**Test Configuration**:
- **VM Size**: Standard_NC6s_v3 (1x Tesla V100)
- **OS**: Ubuntu 22.04 with CUDA 12.0
- **Schedule**: Nightly at 02:00 UTC
- **Duration**: 30 minutes maximum

**GitHub Actions Workflow**: `.github/workflows/nightly-gpu-tests.yml`

```yaml
name: Nightly GPU Integration Tests

on:
  schedule:
    - cron: '0 2 * * *'  # 02:00 UTC daily
  workflow_dispatch:      # Manual trigger

jobs:
  gpu-tests:
    runs-on: [self-hosted, gpu, linux]

    steps:
      - uses: actions/checkout@v3

      - name: Check NVIDIA GPU availability
        run: nvidia-smi

      - name: Install Rust toolchain
        uses: actions-rs/toolchain@v1
        with:
          profile: minimal
          toolchain: stable

      - name: Run GPU integration tests
        run: |
          cargo test --features cuda --test gpu_integration -- --nocapture
        env:
          RUST_LOG: debug
          GPU_TEST_MODE: full

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: gpu-test-results
          path: target/test-results/
```

**Dedicated GPU Test Suite**: `tests/integration/gpu_integration.rs`

```rust
/// GPU integration tests that require physical NVIDIA GPUs
///
/// These tests only run when:
/// - CUDA feature is enabled
/// - GPU_TEST_MODE=full environment variable is set
/// - nvidia-smi is available

#[cfg(all(feature = "cuda", test))]
mod gpu_integration {
    use super::*;

    fn is_gpu_test_enabled() -> bool {
        std::env::var("GPU_TEST_MODE").unwrap_or_default() == "full"
    }

    #[tokio::test]
    async fn test_real_gpu_enumeration() {
        if !is_gpu_test_enabled() {
            eprintln!("Skipping GPU test: GPU_TEST_MODE != full");
            return;
        }

        let manager = GpuManager::new();
        let devices = manager.enumerate_devices().await;

        assert!(devices.is_ok(), "GPU enumeration failed: {:?}", devices.err());
        let devices = devices.unwrap();
        assert!(devices.len() > 0, "No GPUs detected");

        // Validate device properties
        for device in &devices {
            assert!(device.compute_capability.0 >= 7, "GPU too old: compute {}.{}",
                device.compute_capability.0, device.compute_capability.1);
            assert!(device.memory_total > 0, "GPU has no memory");
        }
    }

    #[tokio::test]
    async fn test_real_gpu_mining_workflow() {
        if !is_gpu_test_enabled() {
            return;
        }

        let manager = GpuManager::new();
        let devices = manager.enumerate_devices().await.unwrap();
        let device_ids: Vec<usize> = devices.iter().map(|d| d.device_id).collect();

        // Initialize for Ethash
        let result = manager.initialize_for_algorithm(GpuAlgorithm::Ethash, &device_ids).await;
        assert!(result.is_ok(), "GPU initialization failed: {:?}", result.err());

        // Start monitoring
        manager.start_monitoring_loop().await.unwrap();

        // Let it run for 10 seconds
        tokio::time::sleep(Duration::from_secs(10)).await;

        // Check stats
        let stats = manager.get_mining_stats().await.unwrap();
        assert_eq!(stats.total_devices, devices.len());
        assert!(stats.active_devices > 0);

        // Stop monitoring
        manager.stop_monitoring_loop().await.unwrap();

        // Cleanup
        manager.cleanup().await.unwrap();
    }
}
```

---

#### **Tier 3: Docker GPU Container Tests** (Already Implemented)

**Status**: ✅ Already implemented in `complete_system_validation.rs::phase33_docker_gpu_container_validation`.

**Infrastructure**: Docker with NVIDIA Container Toolkit.

**Test Script** (already exists):
```bash
# Test GPU access
nvidia-smi --query-gpu=name --format=csv,noheader,nounits

# Test namespace support
[ -f /proc/self/ns/user ] && [ -f /proc/self/ns/mnt ]

# Test seccomp capability
# (requires loading custom profiles)

# Test memory management
dd if=/dev/zero of=/tmp/test_mem bs=1M count=10

# Test network capabilities
curl -s --max-time 5 http://httpbin.org/status/200
```

**Integration**: Keep existing `DockerGPUTester` trong `complete_system_validation.rs`.

---

### 2.2 GPU Test Harness Implementation Plan

**Dependencies** (add to workspace `Cargo.toml`):
```toml
[workspace.dependencies]
mockall = "0.11"  # Already exists in mining-core
```

**Test Organization**:
```
tests/
├── fixtures/
│   └── gpu_emulator.rs          # NEW: GPU emulation for tests
│
└── integration/
    ├── gpu_initialization.rs     # NEW: GPU init tests (with emulator)
    └── gpu_integration.rs        # NEW: Real GPU tests (nightly only)
```

**Estimated Effort**:
- GPU Emulator implementation: **3-4 hours**
- Mock GPU integration: **2-3 hours**
- Nightly test workflow setup: **2 hours**
- Total: **7-9 hours**

---

## 3. Property-based Testing Plan

**Objective**: Fuzz critical components to find edge cases and invalid inputs.

**Tool**: `proptest` crate for property-based testing.

### 3.1 Property Testing Candidates

#### **Candidate 1: Configuration Parsing**

**Component**: `crates/mining-core/src/config.rs`

**Property**: "Any valid TOML input should parse successfully or return meaningful error"

**Test File**: `tests/unit/config_parsing.rs`

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_config_parsing_never_panics(
        pool_url in "[a-z]+://[a-z0-9.-]+:[0-9]{1,5}",
        wallet_addr in "0x[0-9a-fA-F]{40}",
        gpu_count in 1..8usize,
        threads in 256..2048u32,
    ) {
        let config_str = format!(r#"
[mining]
algorithm = "ethash"
pool_url = "{}"
wallet = "{}"

[mining.gpu]
devices = [0]
threads_per_gpu = {}
"#, pool_url, wallet_addr, threads);

        // Should never panic
        let result = toml::from_str::<MiningConfig>(&config_str);

        // Either parse successfully or return error
        match result {
            Ok(config) => {
                assert_eq!(config.mining.pool_url, pool_url);
                assert_eq!(config.mining.wallet, wallet_addr);
            }
            Err(e) => {
                // Error should be meaningful
                assert!(!e.to_string().is_empty());
            }
        }
    }
}

proptest! {
    #[test]
    fn test_invalid_config_rejects_gracefully(
        invalid_url in "[^a-zA-Z0-9:/.]+",
        invalid_wallet in "[^0-9a-fA-Fx]+",
    ) {
        let config_str = format!(r#"
[mining]
algorithm = "ethash"
pool_url = "{}"
wallet = "{}"
"#, invalid_url, invalid_wallet);

        let result = toml::from_str::<MiningConfig>(&config_str);

        // Should reject invalid inputs
        assert!(result.is_err(), "Invalid config should not parse");
    }
}
```

**Properties to Test**:
- ✅ Valid configurations parse successfully
- ✅ Invalid configurations return clear errors
- ✅ Parsing never panics
- ✅ Default values are applied correctly
- ✅ URL validation works for all valid schemes

---

#### **Candidate 2: Stratum Protocol Parsing**

**Component**: `crates/mining-core/src/crypto/stratum.rs`

**Property**: "Malformed JSON messages should be rejected without panic"

**Test File**: `tests/unit/stratum_protocol.rs`

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_stratum_message_parsing_never_panics(
        id in any::<u32>(),
        method in "[a-z._]+",
        random_json in any::<String>(),
    ) {
        // Generate potentially malformed Stratum messages
        let message = format!(r#"{{"id": {}, "method": "{}", "params": {}}}"#,
            id, method, random_json);

        // Parse should never panic
        let result = StratumMessage::from_json(&message);

        // Either parse or return error
        match result {
            Ok(msg) => {
                assert_eq!(msg.id, id);
                assert_eq!(msg.method, method);
            }
            Err(e) => {
                // Error should be descriptive
                assert!(e.to_string().contains("parse") || e.to_string().contains("invalid"));
            }
        }
    }
}

proptest! {
    #[test]
    fn test_stratum_subscribe_response_parsing(
        session_id in "[0-9a-f]{16}",
        extranonce1 in "[0-9a-f]{8}",
        extranonce2_size in 2..8usize,
    ) {
        let response = format!(r#"{{
            "id": 1,
            "result": [
                ["mining.set_difficulty", "{}"],
                ["mining.notify", "{}"],
                "{}",
                {}
            ],
            "error": null
        }}"#, session_id, session_id, extranonce1, extranonce2_size);

        let result = StratumMessage::from_json(&response);
        assert!(result.is_ok(), "Valid subscribe response should parse");

        let msg = result.unwrap();
        // Validate parsed fields
        assert_eq!(msg.id, 1);
    }
}

proptest! {
    #[test]
    fn test_malformed_json_rejected(
        malformed in prop_oneof![
            Just(r#"{"id": 1, "method": "mining.subscribe""#),  // Missing closing brace
            Just(r#"{"id": "not_a_number", "method": "test"}"#), // Invalid ID type
            Just(r#"{id: 1, method: "test"}"#),                 // Unquoted keys
            Just(r#"{"id": 1, "method": null}"#),              // Null method
        ]
    ) {
        let result = StratumMessage::from_json(malformed);
        assert!(result.is_err(), "Malformed JSON should be rejected");
    }
}
```

**Properties to Test**:
- ✅ Valid Stratum messages parse correctly
- ✅ Malformed JSON is rejected
- ✅ Missing required fields return errors
- ✅ Type mismatches are caught
- ✅ Parsing never panics

---

#### **Candidate 3: Cryptographic Operations**

**Component**: `crates/security/src/crypto/wallet_protection.rs`

**Property**: "Encryption/decryption with same password always succeeds"

**Test File**: `tests/unit/crypto_tests.rs`

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_encrypt_decrypt_round_trip(
        password in "[a-zA-Z0-9!@#$%^&*()]{8,64}",
        plaintext in prop::collection::vec(any::<u8>(), 1..1024),
    ) {
        let protector = WalletProtector::with_password(&password).unwrap();

        // Encrypt
        let encrypted = protector.encrypt_wallet(&plaintext).unwrap();

        // Decrypt
        let decrypted = protector.decrypt_wallet(&encrypted).unwrap();

        // Should match original
        assert_eq!(plaintext, decrypted, "Round-trip encryption/decryption failed");
    }
}

proptest! {
    #[test]
    fn test_nonces_always_unique(
        password in "[a-zA-Z0-9]{16}",
        data in prop::collection::vec(any::<u8>(), 100),
        iterations in 10..100usize,
    ) {
        let protector = WalletProtector::with_password(&password).unwrap();

        let mut nonces = std::collections::HashSet::new();

        for _ in 0..iterations {
            let encrypted = protector.encrypt_wallet(&data).unwrap();
            let nonce_hex = hex::encode(&encrypted.nonce);

            // Nonce must be unique
            assert!(nonces.insert(nonce_hex.clone()),
                "Duplicate nonce detected: {}", nonce_hex);
        }
    }
}

proptest! {
    #[test]
    fn test_wrong_password_always_fails(
        correct_password in "[a-zA-Z0-9]{16}",
        wrong_password in "[a-zA-Z0-9]{16}",
        data in prop::collection::vec(any::<u8>(), 100),
    ) {
        prop_assume!(correct_password != wrong_password);

        let protector1 = WalletProtector::with_password(&correct_password).unwrap();
        let protector2 = WalletProtector::with_password(&wrong_password).unwrap();

        let encrypted = protector1.encrypt_wallet(&data).unwrap();

        // Wrong password should always fail
        let result = protector2.decrypt_wallet(&encrypted);
        assert!(result.is_err(), "Wrong password should fail decryption");
    }
}
```

**Properties to Test**:
- ✅ Round-trip encryption always succeeds
- ✅ Nonces are always unique
- ✅ Wrong password always fails
- ✅ Encryption is deterministic given same nonce
- ✅ Ciphertext length is predictable

---

### 3.2 Property Testing Implementation Plan

**Dependencies** (add to workspace `Cargo.toml`):
```toml
[workspace.dependencies]
proptest = "1.4"  # Property-based testing framework
```

**Update crate dev-dependencies**:
```toml
# In crates/mining-core/Cargo.toml
[dev-dependencies]
proptest = { workspace = true }

# In crates/security/Cargo.toml
[dev-dependencies]
proptest = { workspace = true }
```

**Test Organization**:
```
tests/
└── unit/
    ├── config_parsing.rs         # NEW: Config property tests
    ├── stratum_protocol.rs       # NEW: Stratum property tests
    └── crypto_tests.rs           # NEW: Crypto property tests
```

**Estimated Effort**:
- Setup proptest infrastructure: **1-2 hours**
- Config parsing properties: **2-3 hours**
- Stratum protocol properties: **3-4 hours**
- Crypto operation properties: **2-3 hours**
- Total: **8-12 hours**

---

## 4. Test Infrastructure Requirements

### 4.1 Additional Dependencies

**Add to workspace `Cargo.toml`**:
```toml
[workspace.dependencies]
# Property-based testing
proptest = "1.4"

# Test utilities
test-case = "3.3"      # Parameterized test cases
rstest = "0.18"        # Fixture-based testing
```

**Install coverage tool**:
```bash
cargo install cargo-tarpaulin
```

### 4.2 GitHub Actions CI/CD Workflow

**File**: `.github/workflows/test-suite.yml`

```yaml
name: Test Suite

on:
  push:
    branches: [main, gpu-opus-clean]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Install Rust
        uses: actions-rs/toolchain@v1
        with:
          profile: minimal
          toolchain: stable
          override: true

      - name: Cache cargo registry
        uses: actions/cache@v3
        with:
          path: ~/.cargo/registry
          key: ${{ runner.os }}-cargo-registry-${{ hashFiles('**/Cargo.lock') }}

      - name: Run unit tests
        run: cargo test --lib --bins
        env:
          RUST_BACKTRACE: 1

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Install Rust
        uses: actions-rs/toolchain@v1
        with:
          profile: minimal
          toolchain: stable

      - name: Run integration tests
        run: cargo test --test '*' -- --test-threads=1
        env:
          RUST_LOG: debug

  property-tests:
    name: Property-based Tests
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Install Rust
        uses: actions-rs/toolchain@v1
        with:
          profile: minimal
          toolchain: stable

      - name: Run property tests
        run: cargo test --tests -- --nocapture proptest
        env:
          PROPTEST_CASES: 1000  # Run 1000 test cases

  coverage:
    name: Code Coverage
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Install Rust
        uses: actions-rs/toolchain@v1
        with:
          profile: minimal
          toolchain: stable

      - name: Install tarpaulin
        run: cargo install cargo-tarpaulin

      - name: Generate coverage report
        run: |
          cargo tarpaulin \
            --out Xml \
            --output-dir coverage \
            --exclude-files 'tests/*' 'target/*' \
            --timeout 300

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/cobertura.xml
          fail_ci_if_error: false
```

### 4.3 Terraform Infrastructure for Nightly GPU Tests

**File**: `terraform/nightly-gpu-tests/main.tf`

```hcl
# Azure VM with NVIDIA GPU for nightly testing
resource "azurerm_linux_virtual_machine" "gpu_test_vm" {
  name                = "gpu-test-runner"
  resource_group_name = azurerm_resource_group.test_rg.name
  location            = azurerm_resource_group.test_rg.location
  size                = "Standard_NC6s_v3"  # 1x Tesla V100

  admin_username      = "testrunner"

  network_interface_ids = [
    azurerm_network_interface.gpu_test_nic.id,
  ]

  admin_ssh_key {
    username   = "testrunner"
    public_key = file("~/.ssh/id_rsa.pub")
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "microsoft-dsvm"
    offer     = "ubuntu-hpc"
    sku       = "2004-cuda11"
    version   = "latest"
  }

  tags = {
    environment = "testing"
    purpose     = "gpu-nightly-tests"
  }
}

# Shutdown schedule to save costs
resource "azurerm_dev_test_global_vm_shutdown_schedule" "shutdown" {
  virtual_machine_id = azurerm_linux_virtual_machine.gpu_test_vm.id
  location           = azurerm_resource_group.test_rg.location
  enabled            = true

  daily_recurrence_time = "0300"  # Shutdown after nightly tests
  timezone              = "UTC"

  notification_settings {
    enabled = false
  }
}
```

**Estimated Monthly Cost**: ~$150 USD (1x NC6s_v3 for 1 hour/day)

---

## 5. Implementation Roadmap

### Wave 1: Integration Tests Foundation (Week 1)

**Duration**: 5-7 days
**Effort**: 16-20 hours

**Tasks**:
1. ✅ Create `tests/integration/` directory structure
2. ✅ Implement `tests/fixtures/mock_pool.rs` (enhanced version)
3. ✅ Implement `tests/fixtures/test_configs.rs`
4. ✅ Implement `tests/fixtures/gpu_emulator.rs`
5. ✅ Create integration test scenarios:
   - `mining_workflow.rs` (Scenario 1 & 3)
   - `pool_connection.rs` (Scenario 2)
   - `gpu_initialization.rs` (GPU init tests)
6. ✅ Update CI/CD workflow for integration tests

**Deliverables**:
- ✅ 8-10 integration tests covering critical paths
- ✅ Reusable test fixtures
- ✅ CI/CD integration

---

### Wave 2: Property-based Testing (Week 2)

**Duration**: 3-4 days
**Effort**: 12-16 hours

**Tasks**:
1. ✅ Add `proptest` dependency to workspace
2. ✅ Create `tests/unit/` directory
3. ✅ Implement property tests:
   - `config_parsing.rs` (5-7 properties)
   - `stratum_protocol.rs` (6-8 properties)
   - `crypto_tests.rs` (4-6 properties)
4. ✅ Configure proptest for CI/CD (1000 cases)

**Deliverables**:
- ✅ 15-21 property tests
- ✅ Fuzzing coverage for critical parsing
- ✅ CI/CD integration

---

### Wave 3: GPU Test Harness (Week 3)

**Duration**: 4-5 days
**Effort**: 16-20 hours

**Tasks**:
1. ✅ Implement GPU emulator (`tests/fixtures/gpu_emulator.rs`)
2. ✅ Create nightly GPU test suite (`tests/integration/gpu_integration.rs`)
3. ✅ Setup Terraform infrastructure for Azure GPU VM
4. ✅ Configure GitHub Actions for nightly tests
5. ✅ Document GPU testing tiers and strategy

**Deliverables**:
- ✅ GPU emulator for unit tests
- ✅ 3-5 real GPU integration tests
- ✅ Nightly test infrastructure
- ✅ Documentation

---

### Wave 4: Coverage & Quality Gates (Week 4)

**Duration**: 2-3 days
**Effort**: 8-12 hours

**Tasks**:
1. ✅ Install and configure `cargo-tarpaulin`
2. ✅ Setup Codecov integration
3. ✅ Add coverage badge to README
4. ✅ Define coverage targets:
   - Unit tests: ≥80%
   - Integration tests: ≥70%
   - Overall: ≥75%
5. ✅ Create coverage reports in CI/CD

**Deliverables**:
- ✅ Automated coverage tracking
- ✅ Coverage reports in pull requests
- ✅ Quality gates in CI/CD

---

## 6. Success Criteria

### Test Coverage Targets

**Unit Tests**:
- ✅ **Target**: ≥80% line coverage
- ✅ All public APIs have unit tests
- ✅ Error paths are tested
- ✅ Edge cases are covered

**Integration Tests**:
- ✅ **Target**: ≥70% workflow coverage
- ✅ All critical paths have integration tests:
  - Miner startup → ready state
  - Pool connection → authentication → job reception
  - Share generation → submission → acceptance
  - Stealth + mining integration
  - Security features integration
- ✅ Mock infrastructure is reusable
- ✅ Tests run in <30 seconds

**Property-based Tests**:
- ✅ **Target**: 15-21 properties defined
- ✅ Each property runs 1000+ test cases in CI/CD
- ✅ Critical parsing never panics:
  - Config parsing
  - Stratum protocol parsing
  - Cryptographic operations
- ✅ Invalid inputs are rejected gracefully

**GPU Tests**:
- ✅ **Target**: 100% of GPU code tested via emulation or nightly tests
- ✅ GPU emulator covers standard workflows
- ✅ Nightly tests run on real hardware
- ✅ Docker GPU tests validate containerization

### Quality Gates

**CI/CD Requirements**:
- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ Property tests complete without failures
- ✅ Coverage ≥75% overall
- ✅ No compiler warnings
- ✅ `cargo clippy` passes with no warnings
- ✅ `cargo fmt --check` passes

**Pull Request Requirements**:
- ✅ New code has tests (unit or integration)
- ✅ Coverage does not decrease
- ✅ All tests pass
- ✅ No new warnings introduced

---

## Appendix A: Test Execution Matrix

| Test Type | Location | Run Frequency | GPU Required | Duration |
|-----------|----------|---------------|--------------|----------|
| Unit Tests | `crates/*/src/*_tests.rs` | On every commit | No | <10s |
| Integration Tests (Mock GPU) | `tests/integration/` | On every commit | No | <30s |
| Property Tests | `tests/unit/` | On every commit | No | <60s |
| Phase 3 Validation | `tests/phase3-validation/` | On every commit | No | <30s |
| GPU Integration (Real) | `tests/integration/gpu_integration.rs` | Nightly | Yes | <10min |
| Docker GPU Tests | `tests/phase3-validation/e2e/` | On demand | Yes | <5min |
| Benchmarks | `crates/*/benches/` | Weekly | Optional | <30min |

---

## Appendix B: File Structure Summary

```
tests/
├── fixtures/                      # NEW: Shared test utilities
│   ├── mod.rs
│   ├── mock_pool.rs              # Enhanced MockStratumPool
│   ├── test_configs.rs           # Test configuration generator
│   └── gpu_emulator.rs           # GPU emulation for tests
│
├── unit/                         # NEW: Property-based tests
│   ├── mod.rs
│   ├── config_parsing.rs         # Config property tests
│   ├── stratum_protocol.rs       # Stratum property tests
│   └── crypto_tests.rs           # Crypto property tests
│
├── integration/                  # NEW: Integration tests
│   ├── mod.rs
│   ├── mining_workflow.rs        # Scenarios 1 & 3
│   ├── pool_connection.rs        # Scenario 2
│   ├── gpu_initialization.rs     # GPU init tests
│   ├── gpu_integration.rs        # Real GPU tests (nightly)
│   ├── stealth_integration.rs    # MOVED from phase3-validation/
│   └── security_integration.rs   # Security integration
│
└── phase3-validation/            # KEEP: Phase 3 validation tests
    ├── e2e/
    ├── security/
    ├── stealth/
    └── resources/
```

---

## Appendix C: Dependencies Summary

**To Add to Workspace `Cargo.toml`**:
```toml
[workspace.dependencies]
# Property-based testing
proptest = "1.4"

# Test utilities
test-case = "3.3"
rstest = "0.18"
```

**To Install**:
```bash
# Coverage tool
cargo install cargo-tarpaulin
```

**Already Available**:
- ✅ `tokio-test = "0.4"`
- ✅ `mockall = "0.11"` (in mining-core)
- ✅ `assert_matches = "1.5"`
- ✅ `criterion = "0.5"`

---

## Conclusion

Đây là **comprehensive testing architecture** (kiến trúc testing toàn diện – hệ thống test 3 tầng) cho Phase 4. Architecture này cung cấp:

1. ✅ **Integration Tests**: 8-10 tests covering critical workflows
2. ✅ **GPU Test Harness**: 3-tier strategy (emulation, nightly, Docker)
3. ✅ **Property-based Testing**: 15-21 properties fuzzing critical components
4. ✅ **CI/CD Integration**: Automated testing on every commit
5. ✅ **Coverage Tracking**: 75%+ target with Codecov

**Total Estimated Effort**: 52-68 hours (2-3 weeks for 1 developer)

**Next Steps**:
1. Review và approve architecture
2. Implement Wave 1 (Integration Tests Foundation)
3. Implement Wave 2 (Property-based Testing)
4. Implement Wave 3 (GPU Test Harness)
5. Implement Wave 4 (Coverage & Quality Gates)

---

**Document Control**:
- **Created**: 2025-10-02
- **Author**: Odyssey AI Research System
- **Version**: 1.0
- **Status**: Ready for Implementation
