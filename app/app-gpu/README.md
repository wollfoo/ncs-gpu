# Agent-GPU v2.0

🚀 **High-Performance GPU Mining Platform** với **Modular Monolith Architecture** (kiến trúc monolith mô-đun)

[![Rust](https://img.shields.io/badge/rust-1.75+-orange.svg)](https://www.rust-lang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://www.docker.com/)
[![CUDA](https://img.shields.io/badge/CUDA-12.2+-green.svg)](https://developer.nvidia.com/cuda-zone)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-black)](https://github.com/wollfoo/agent-gpu)

## 📋 Tổng quan

**Agent-GPU** (formerly OPUS-GPU) là một nền tảng mining GPU hiệu suất cao được xây dựng bằng **Rust** với kiến trúc **modular monolith**. Hệ thống hỗ trợ nhiều **GPU APIs** (CUDA, OpenCL, Vulkan, WebGPU) và cung cấp **plugin system** (hệ thống plugin) linh hoạt cho việc mở rộng tính năng.

### ✨ Tính năng chính

- 🏗️ **Modular Architecture** - Kiến trúc mô-đun với message bus nội bộ
- ⚡ **Multi-GPU Support** - Hỗ trợ CUDA, OpenCL, Vulkan, WebGPU
- 🔌 **Plugin System** - Hệ thống plugin có thể mở rộng
- 🌐 **Multiple APIs** - REST, WebSocket, gRPC interfaces
- 📊 **Real-time Monitoring** - Theo dõi performance và metrics
- 🔒 **Wallet Management** - Quản lý wallet và key an toàn
- ⚙️ **Hot Configuration** - Cấu hình động không cần restart
- 🐳 **Docker Support** - Container deployment với multi-stage builds

## 📁 Cấu trúc dự án

```
app-gpu/
├── Cargo.toml              # Workspace configuration
├── Dockerfile             # Multi-stage build for production
├── README.md              # Project documentation
├── config/                # Configuration files
│   └── default.toml       # Default configuration
├── src/                   # Main application
│   ├── main.rs           # Application entry point
│   ├── app.rs            # Main application logic
│   └── cli.rs            # Command line interface
├── core/                  # Core business modules
│   ├── mining/           # Mining algorithms and engine
│   ├── pool/             # Mining pool communication
│   ├── wallet/           # Wallet and key management
│   ├── monitor/          # Performance monitoring
│   └── config/           # Configuration management
├── infrastructure/        # Infrastructure layer
│   ├── bus/              # Internal message bus
│   ├── storage/          # Data persistence
│   └── gpu/              # GPU abstraction layer
├── plugins/               # Plugin system
│   ├── api/              # Plugin API definitions
│   ├── loader/           # Dynamic plugin loader
│   └── registry/         # Plugin registry
├── api/                   # External APIs
│   ├── rest/             # REST API server
│   ├── websocket/        # WebSocket server
│   └── grpc/             # gRPC server
└── tests/                 # Integration tests
```

## 🛠️ Yêu cầu hệ thống

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+), Windows 10+, macOS 10.15+
- **Memory**: Minimum 8GB RAM, Recommended 16GB+
- **Storage**: 10GB free space
- **GPU**: NVIDIA GPU with CUDA 12.0+ hoặc AMD GPU with OpenCL 2.0+

### Development Requirements
- **Rust**: 1.75.0 hoặc mới hơn
- **CUDA Toolkit**: 12.2+ (cho CUDA support)
- **OpenCL**: 2.0+ SDK (cho OpenCL support)
- **Docker**: 20.10+ (optional, for containerization)

## 🚀 Installation & Setup

### 1. Clone Repository
```bash
git clone https://github.com/wollfoo/agent-gpu.git
cd agent-gpu
```

### 2. Install Rust Dependencies
```bash
# Install Rust if not already installed
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Build the project
cargo build --release --features "cuda,opencl"
```

### 3. Configuration
```bash
# Copy and edit configuration
cp config/default.toml config/production.toml
nano config/production.toml

# Update your mining pool and wallet settings
```

### 4. Run Application
```bash
# Development mode
cargo run -- --config config/default.toml

# Production mode
./target/release/agent-gpu --config config/production.toml
```

## 🐳 Docker Deployment

### Production Deployment
```bash
# Build production image
docker build --target production -t agent-gpu:latest .

# Run with GPU support
docker run --runtime=nvidia --gpus all \
  -p 8080:8080 -p 8081:8081 -p 8082:8082 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  agent-gpu:latest
```

### Development Environment
```bash
# Build development image
docker build --target development -t agent-gpu:dev .

# Run development container
docker run --runtime=nvidia --gpus all \
  -v $(pwd):/usr/src/agent-gpu \
  -p 8080:8080 -p 8081:8081 -p 8082:8082 \
  agent-gpu:dev
```

## ⚙️ Configuration

### Environment Variables
```bash
# Core configuration
export AGENT_GPU_CONFIG_PATH=/path/to/config.toml
export AGENT_GPU_LOG_LEVEL=info
export AGENT_GPU_DATA_DIR=/path/to/data

# Mining configuration
export AGENT_GPU_MINING_ALGORITHM=SHA256
export AGENT_GPU_GPU_DEVICES=0,1,2
export AGENT_GPU_POOL_URL=stratum+tcp://pool.example.com:4444
export AGENT_GPU_WALLET_ADDRESS=your_wallet_address

# API configuration
export AGENT_GPU_API_REST_HOST=0.0.0.0
export AGENT_GPU_API_REST_PORT=8080
```

### Configuration File Structure
```toml
[mining]
algorithm = "SHA256"
max_workers = 4
gpu_devices = [0, 1]

[pool]
urls = ["stratum+tcp://pool.example.com:4444"]
username = "your_wallet_address"
password = "worker1"

[api.rest]
host = "127.0.0.1"
port = 8080

[monitoring]
enabled = true
metrics_port = 9090
```

## 🔧 Command Line Interface

```bash
agent-gpu [OPTIONS]

OPTIONS:
    -c, --config <PATH>         Configuration file path
    -g, --gpu-devices <LIST>    GPU devices to use (e.g., '0,1,2')
    -p, --pool-url <URL>        Mining pool URL
    -w, --wallet-address <ADDR> Wallet address
    --api-bind <ADDR>           API server bind address
    --dev-mode                  Enable development mode
    --benchmark                 Run benchmark mode
    --no-plugins               Disable plugin system
```

### Usage Examples
```bash
# Basic mining with default configuration
agent-gpu --config config/default.toml

# Mining with specific GPUs and pool
agent-gpu -g "0,1" -p "stratum+tcp://pool.example.com:4444" -w "your_wallet"

# Development mode with debug logging
agent-gpu --dev-mode --log-level debug

# Benchmark mode
agent-gpu --benchmark --gpu-devices "0"
```

## 📊 API Documentation

### REST API Endpoints
```
GET  /api/v1/status          # System status and health
GET  /api/v1/mining/stats    # Mining statistics
POST /api/v1/mining/start    # Start mining
POST /api/v1/mining/stop     # Stop mining
GET  /api/v1/devices         # List GPU devices
GET  /api/v1/metrics         # Prometheus metrics
```

### WebSocket Events
```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8081/ws');

// Listen for mining updates
ws.on('mining.stats', (data) => {
    console.log('Mining stats:', data);
});

// Listen for device events
ws.on('device.status', (data) => {
    console.log('Device status:', data);
});
```

### gRPC Services
```protobuf
service MiningService {
  rpc GetStatus(Empty) returns (StatusResponse);
  rpc StartMining(StartMiningRequest) returns (Empty);
  rpc StopMining(Empty) returns (Empty);
  rpc GetStats(Empty) returns (StatsResponse);
}
```

## 🔌 Plugin System

### Creating a Plugin
```rust
// Plugin trait implementation
use agent_gpu_plugin_api::{Plugin, PluginResult};

#[derive(Default)]
pub struct MyPlugin;

impl Plugin for MyPlugin {
    fn name(&self) -> &str {
        "my-plugin"
    }

    async fn initialize(&mut self) -> PluginResult<()> {
        // Plugin initialization logic
        Ok(())
    }

    async fn execute(&self, input: &[u8]) -> PluginResult<Vec<u8>> {
        // Plugin execution logic
        Ok(input.to_vec())
    }
}
```

### Plugin Configuration
```toml
[plugins]
disabled = false
plugin_dir = "./plugins"
max_plugins = 50
whitelist = ["trusted-plugin"]
blacklist = ["unsafe-plugin"]
```

## 📈 Monitoring & Metrics

### Prometheus Metrics
- Mining hashrate và performance
- GPU temperature và power usage
- Memory utilization và errors
- Pool connection status
- API request metrics

### Health Checks
```bash
# Health check endpoint
curl http://localhost:8080/health

# Metrics endpoint
curl http://localhost:9090/metrics
```

## 🧪 Testing

### Unit Tests
```bash
# Run all tests
cargo test

# Run specific module tests
cargo test core::mining

# Run with coverage
cargo tarpaulin --all-features
```

### Integration Tests
```bash
# Run integration tests
cargo test --test integration_tests

# Run benchmark tests
cargo test --bench mining_benchmarks
```

### Docker Testing
```bash
# Build and test in Docker
docker build --target testing -t agent-gpu:test .
```

## 🏗️ Development

### Building from Source
```bash
# Debug build
cargo build

# Release build with optimizations
cargo build --release

# Build with specific features
cargo build --features "cuda,opencl,vulkan"
```

### Development Tools
```bash
# Format code
cargo fmt

# Lint code
cargo clippy

# Security audit
cargo audit

# Update dependencies
cargo update
```

### Contributing Guidelines
1. Fork repository và tạo feature branch
2. Implement changes with tests
3. Run linting và tests
4. Submit pull request với detailed description

## 🔒 Security

### Best Practices
- Wallet keys được encrypt và stored securely
- API endpoints có rate limiting và authentication
- Plugin system có sandbox và permission controls
- Network communications sử dụng TLS/SSL

### Security Configuration
```toml
[wallet]
encryption_enabled = true
keystore_dir = "./secure/keystore"

[api]
rate_limit = 100
require_auth = true
tls_enabled = true
```

## 📋 Performance Tuning

### GPU Optimization
```toml
[mining]
batch_size = 2000        # Increase for better throughput
memory_size = 1073741824 # 1GB memory allocation
worker_threads = 2       # Threads per GPU
```

### System Optimization
```bash
# Set CPU governor to performance
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Increase file descriptor limits
ulimit -n 65536

# Optimize memory allocation
export MALLOC_ARENA_MAX=4
```

## 🐛 Troubleshooting

### Common Issues

**GPU not detected**
```bash
# Check CUDA installation
nvidia-smi
nvcc --version

# Check OpenCL installation
clinfo
```

**High memory usage**
```toml
# Reduce memory allocation in config
[mining]
memory_size = 536870912  # 512MB instead of 1GB
batch_size = 500         # Smaller batches
```

**Connection issues**
```bash
# Check firewall settings
sudo ufw allow 8080
sudo ufw allow 8081
sudo ufw allow 8082

# Verify network connectivity
telnet pool.example.com 4444
```

## 📝 Changelog

### v2.0.0 (2024-12-29)
- ✨ Initial release với modular monolith architecture
- 🚀 Multi-GPU support (CUDA, OpenCL, Vulkan, WebGPU)
- 🔌 Plugin system implementation
- 🌐 Multiple API interfaces (REST, WebSocket, gRPC)
- 📊 Real-time monitoring và metrics
- 🐳 Docker containerization với multi-stage builds
- ⚙️ Hot configuration reloading
- 🔒 Secure wallet management

## 📄 License

Dự án này được license dưới **MIT License** - xem file [LICENSE](LICENSE) để biết chi tiết.

## 🤝 Contributing

Contributions được hoan nghênh! Vui lòng đọc [CONTRIBUTING.md](CONTRIBUTING.md) để biết guidelines.

## 📞 Support

- **GitHub Issues**: [https://github.com/wollfoo/agent-gpu/issues](https://github.com/wollfoo/agent-gpu/issues)
- **Documentation**: [https://github.com/wollfoo/agent-gpu/wiki](https://github.com/wollfoo/agent-gpu/wiki)
- **Community**: [GitHub Discussions](https://github.com/wollfoo/agent-gpu/discussions)

## 🙏 Acknowledgments

- **Rust Community** cho ecosystem và tools tuyệt vời
- **NVIDIA** và **Khronos Group** cho GPU computing standards
- **Contributors** đã đóng góp cho dự án

---

**Made with ❤️ by Agent-GPU Team**