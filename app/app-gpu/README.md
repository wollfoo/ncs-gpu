# OPUS-GPU Miner

**High-performance GPU cryptocurrency miner** với modular monolith architecture.

## 🏗️ Architecture Overview

### Modular Monolith Design
- **Single binary** với independent modules
- **Message bus** cho inter-module communication
- **Graceful shutdown** với CancellationToken
- **Production-ready** error handling và logging

### Modules

#### 1. **API Module** (`src/modules/api/`)
- HTTP server sử dụng **Axum** web framework
- REST endpoints cho monitoring và control
- Prometheus metrics exposition endpoint
- Health checks và status queries

**Endpoints:**
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics (text format)
- `GET /api/v1/status` - GPU status và hashrate

#### 2. **GPU Module** (`src/modules/gpu/`)
- CUDA device management (stub - requires CUDA implementation)
- Mining kernel execution
- Work distribution và result reporting
- Multi-GPU support

**TODO:** Integrate cudarc hoặc nvml-wrapper cho actual GPU operations

#### 3. **Stealth Module** (`src/modules/stealth/`)
- Process obfuscation (platform-specific)
- Network traffic masking
- Resource usage throttling
- Plugin-based extensibility

#### 4. **Metrics Module** (`src/modules/metrics/`)
- Prometheus registry integration
- GPU metrics collection (utilization, temperature, power)
- System metrics (CPU, memory)
- Real-time performance monitoring

#### 5. **Message Bus** (`src/messaging/`)
- Zero-copy messaging với Arc-wrapped data
- Crossbeam channels cho high-performance IPC
- Broadcast và targeted messaging
- Type-safe message passing

#### 6. **Plugin System** (`src/plugins/`)
- Dynamic library loading với libloading
- Versioned plugin API
- Safe plugin initialization/shutdown
- Extensible architecture

## 🚀 Getting Started

### Prerequisites
- **Rust 1.70+** (edition 2021)
- **CUDA Toolkit 12.x** (optional, for GPU support)
- **Linux/Windows/macOS** (Linux recommended for production)

### Build

```bash
# Development build
cargo build

# Production build với optimizations
cargo build --release
```

### Configuration

Tạo config file tại `config/app.toml`:

```toml
[gpu]
devices = [0]  # GPU IDs to use
memory_limit_mb = 8192

[api]
host = "127.0.0.1"
port = 8080

[stealth]
enabled = false
plugins_dir = "/opt/opus-gpu/plugins"

[metrics]
enabled = true
port = 9090
```

### Run

```bash
# Với default config
CONFIG_PATH=config/app.toml cargo run --release

# Hoặc set environment variable
export CONFIG_PATH=/path/to/config.toml
./target/release/gpu-miner
```

## 📊 Monitoring

### Prometheus Integration

Metrics exposed tại `http://localhost:9090/metrics`:

```
# GPU metrics
opus_miner_hashrate_mhs
opus_miner_gpu_utilization_percent
opus_miner_gpu_temperature_celsius
opus_miner_gpu_power_watts

# Mining metrics
opus_miner_shares_accepted_total
opus_miner_shares_rejected_total

# System metrics
opus_miner_cpu_usage_percent
opus_miner_memory_used_mb
```

### Grafana Dashboard

Import Prometheus metrics vào Grafana để visualization real-time.

## 🧪 Testing

```bash
# Run all tests
cargo test

# Run với output
cargo test -- --nocapture

# Run specific test
cargo test test_health_endpoint
```

## 🔧 Development

### Adding New Modules

1. Tạo module directory trong `src/modules/`
2. Implement `start()` function với signature:
   ```rust
   pub async fn start(
       config: YourConfig,
       message_bus: Arc<MessageBus>,
       cancel_token: CancellationToken,
   ) -> Result<()>
   ```
3. Register module trong `src/modules/mod.rs`
4. Spawn module task trong `src/main.rs`

### Error Handling

Sử dụng custom error types trong `src/error.rs`:

```rust
use crate::error::{MinerError, Result};

fn your_function() -> Result<()> {
    Err(MinerError::Gpu("CUDA error".to_string()))
}
```

## 🔐 Security Considerations

⚠️ **Warning:** Code này chứa patterns có thể được sử dụng cho malicious purposes:
- Process obfuscation
- Network traffic masking
- Stealth capabilities

**Chỉ sử dụng cho legitimate mining operations** với permission của system owner.

## 📝 TODO List

### High Priority
- [ ] Implement actual CUDA integration (cudarc)
- [ ] Add NVML metrics collection (nvml-wrapper)
- [ ] Implement message bus handlers trong modules
- [ ] Add authentication cho API endpoints
- [ ] Config validation và hot-reload

### Medium Priority
- [ ] Performance profiling và optimization
- [ ] Integration tests với Docker
- [ ] Grafana dashboard templates
- [ ] Documentation generation (cargo doc)
- [ ] CI/CD pipeline (GitHub Actions)

### Low Priority
- [ ] Legacy binary bridge implementation
- [ ] Plugin SDK documentation
- [ ] Windows service wrapper
- [ ] macOS daemon support

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

Contributions welcome! Please:
1. Fork repository
2. Create feature branch
3. Add tests
4. Submit pull request

## 📚 References

- [Tokio Async Runtime](https://tokio.rs/)
- [Axum Web Framework](https://github.com/tokio-rs/axum)
- [Prometheus Rust Client](https://github.com/tikv/rust-prometheus)
- [Cudarc CUDA Bindings](https://github.com/coreylowman/cudarc)
- [NVML Wrapper](https://github.com/Cldfire/nvml-wrapper)
