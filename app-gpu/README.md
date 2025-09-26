# 🚀 OPUS-GPU v2.0 - High-Performance GPU Computing Framework

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/opus-gpu/v2)
[![Rust](https://img.shields.io/badge/rust-%3E%3D1.75-orange)](https://www.rust-lang.org/)
[![CUDA](https://img.shields.io/badge/CUDA-12.0%2B-green)](https://developer.nvidia.com/cuda-toolkit)
[![License](https://img.shields.io/badge/license-Proprietary-red)](LICENSE)

## 📖 Giới Thiệu

**OPUS-GPU v2.0** là framework **GPU Computing** (tính toán GPU – xử lý song song trên card đồ họa) thế hệ mới, được xây dựng lại hoàn toàn với kiến trúc **Modular Monolith** (nguyên khối mô-đun – kiến trúc plugin linh hoạt) sử dụng **Rust** (ngôn ngữ hệ thống – an toàn bộ nhớ và hiệu năng cao).

### 🎯 Điểm Nổi Bật

- **🚄 Ultra-Low Latency**: P95 < 10ms với zero-copy IPC
- **⚡ High Throughput**: > 2000 requests/second  
- **🔥 GPU Optimization**: > 90% GPU utilization
- **🔌 Plugin Architecture**: Hot-reload modules không downtime
- **🛡️ Memory Safety**: Rust ownership prevents data races
- **📊 Real-time Monitoring**: Prometheus metrics và Grafana dashboards

## 🏗️ Kiến Trúc

```
┌──────────────────────────────────┐
│      Core Runtime (Rust)         │
├──────────────────────────────────┤
│   Plugin Manager │ IPC Layer     │
├─────────┬────────┴──────┬────────┤
│   GPU   │   Scheduler   │Monitor │
│ Executor│     (Go)      │ (Rust) │
└─────────┴───────────────┴────────┘
```

## 🚀 Quick Start

### Prerequisites

```bash
# System Requirements
- Ubuntu 22.04 LTS hoặc mới hơn
- NVIDIA GPU với CUDA Compute Capability >= 6.0
- NVIDIA Driver >= 525.60.13
- 8GB RAM minimum

# Development Tools
- Rust >= 1.75.0
- Go >= 1.21
- CUDA Toolkit >= 12.0
- Docker >= 24.0 (optional)
```

### Installation

#### 1. Clone Repository
```bash
git clone https://github.com/opus-gpu/v2.git opus-gpu
cd opus-gpu/app/app-gpu
```

#### 2. Build từ Source
```bash
# Install Rust nếu chưa có
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Build project
cargo build --release --features cuda

# Run tests
cargo test --all
```

#### 3. Docker Deployment
```bash
# Build Docker image
docker build -t opus-gpu:v2 .

# Run container
docker run --gpus all \
  -p 9090:9090 \
  -v /path/to/config:/config \
  opus-gpu:v2
```

## 📁 Project Structure

```
opus-gpu/app/app-gpu/
├── core/                 # Core runtime (Rust)
│   ├── src/
│   │   ├── main.rs      # Entry point
│   │   ├── runtime.rs   # Event loop
│   │   └── plugin_manager.rs
│   └── Cargo.toml
│
├── plugins/             # Plugin modules
│   ├── gpu-executor/    # GPU execution (Rust+CUDA)
│   ├── scheduler/       # Task scheduler (Go)
│   └── monitor/         # Monitoring (Rust)
│
├── shared/              # Shared libraries
│   ├── proto/          # Protocol definitions
│   └── crypto/         # Encryption utilities
│
├── scripts/            # Build & deployment
├── tests/              # Test suites
└── docs/               # Documentation
```

## ⚙️ Configuration

### Basic Configuration (config.yaml)
```yaml
# Core Runtime Settings
runtime:
  workers: 4
  max_memory: "500MB"
  plugin_dir: "./plugins"

# GPU Configuration  
gpu:
  devices: ["0", "1"]        # GPU indices
  memory_fraction: 0.9        # VRAM allocation
  power_limit: 300            # Watts
  
# Scheduler Settings
scheduler:
  algorithm: "priority"       # priority | fifo | fair
  max_queue_size: 10000
  batch_size: 32

# Monitoring
monitoring:
  prometheus_port: 9090
  log_level: "info"          # trace | debug | info | warn | error
  metrics_interval: 30       # seconds
```

### Environment Variables
```bash
# Required
export OPUS_CONFIG_PATH=/path/to/config.yaml
export OPUS_PLUGIN_PATH=/path/to/plugins

# Optional
export RUST_LOG=info
export OPUS_MAX_THREADS=4
export CUDA_VISIBLE_DEVICES=0,1
```

## 🔧 Development

### Building Plugins

#### Rust Plugin Template
```rust
use opus_gpu::{Plugin, Task, Result};

pub struct MyPlugin {
    // Plugin state
}

impl Plugin for MyPlugin {
    fn name(&self) -> &str { 
        "my-plugin" 
    }
    
    fn initialize(&mut self) -> Result<()> {
        // Setup code
        Ok(())
    }
    
    fn execute(&self, task: Task) -> Result<Output> {
        // Process task
        Ok(output)
    }
}

// Export plugin
opus_gpu::export_plugin!(MyPlugin);
```

#### Go Scheduler Plugin
```go
package main

import "C"
import "github.com/opus-gpu/go-plugin"

type Scheduler struct {
    // State
}

func (s *Scheduler) Schedule(task Task) error {
    // Scheduling logic
    return nil
}

//export PluginInit
func PluginInit() *Scheduler {
    return &Scheduler{}
}

func main() {} // Required for plugin
```

### Running Tests

```bash
# Unit tests
cargo test --lib

# Integration tests  
cargo test --test '*'

# Benchmarks
cargo bench

# GPU tests (requires NVIDIA GPU)
cargo test --features gpu-tests

# Coverage report
cargo tarpaulin --out Html
```

## 📊 Performance Metrics

| Metric | Baseline (v1) | Current (v2) | Improvement |
|--------|---------------|--------------|-------------|
| **P50 Latency** | 30ms | < 5ms | 6x |
| **P95 Latency** | 50ms | < 10ms | 5x |
| **Throughput** | 500/s | > 2000/s | 4x |
| **GPU Util** | 70% | > 90% | 1.3x |
| **Memory** | 2GB | < 500MB | 4x |

## 🔍 Monitoring

### Prometheus Metrics
```bash
# Available at http://localhost:9090/metrics
opus_gpu_tasks_total
opus_gpu_task_duration_seconds
opus_gpu_gpu_utilization_percent
opus_gpu_memory_usage_bytes
opus_gpu_plugin_load_time_seconds
```

### Grafana Dashboard
```bash
# Import dashboard
docker run -d \
  -p 3000:3000 \
  --name grafana \
  grafana/grafana

# Import dashboard từ docs/grafana-dashboard.json
```

## 🛡️ Security

### Binary Protection
- **Code Obfuscation**: Sử dụng cargo-obfuscate
- **Symbol Stripping**: Loại bỏ debug symbols
- **Binary Packing**: UPX compression

### Runtime Security  
- **Hardware Binding**: Kiểm tra GPU UUID
- **Encrypted IPC**: ChaCha20-Poly1305
- **Secure Plugins**: Sandboxed execution
- **Audit Logging**: Comprehensive activity logs

## 📚 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP.md)
- [API Reference](docs/API.md)
- [Plugin Development Guide](docs/PLUGIN_GUIDE.md)
- [Operations Runbook](docs/RUNBOOK.md)

## 🤝 Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

### Development Workflow
1. Fork repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📄 License

This project is proprietary software. See [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- NVIDIA for CUDA toolkit và GPU libraries
- Rust community for excellent tooling
- Contributors và maintainers

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/opus-gpu/v2/issues)
- **Email**: support@opus-gpu.dev
- **Discord**: [Join our server](https://discord.gg/opus-gpu)

---

**Version**: 2.0.0  
**Status**: In Development  
**Last Updated**: 2025-01-26

Made with ❤️ by OPUS-GPU Team
