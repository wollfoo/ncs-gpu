# 🚀 Opus GPU Mining System - Production Ready

**Production-ready GPU mining system** (hệ thống khai thác GPU sẵn sàng sản xuất) với **stealth capabilities** (khả năng ẩn danh), được viết bằng **Rust** (an toàn bộ nhớ, hiệu năng cao) và **CUDA** (tối ưu GPU).

## ✨ Tính Năng

### Core Features (Tính năng cốt lõi)
- ⚡ **High-performance mining** (khai thác hiệu năng cao) - Rust + CUDA
- 🥷 **Stealth layer** (lớp ẩn danh) - ngụy trang dưới AI Training/Image Processing/Scientific Computing/AI Inference
- 🔒 **Security hardening** (tăng cường bảo mật) - seccomp, AppArmor, namespace isolation
- 🌐 **Distributed coordination** (điều phối phân tán) - multi-node support
- 📊 **Real-time monitoring** (giám sát thời gian thực) - hashrate, temperature, utilization

### Supported Algorithms (Thuật toán hỗ trợ)
- ✅ **Ethash** (Ethereum)
- ✅ **KawPow** (Ravencoin)
- ✅ **RandomX** (Monero)

### Stealth Profiles (Hồ sơ ẩn danh)
- 🤖 **AI Training** - giả lập huấn luyện mô hình PyTorch/TensorFlow
- 🖼️ **Image Processing** - giả lập xử lý hình ảnh với OpenCV
- 🔬 **Scientific Computing** - giả lập mô phỏng CUDA
- 🧠 **AI Inference** - giả lập dự đoán mô hình

## 🏗️ Kiến Trúc

```
┌─────────────────────────────────────────────┐
│           CLI Interface (Rust)              │
└───────────────────┬─────────────────────────┘
                    │
    ┌───────────────┴──────────────┐
    │                               │
┌───▼────────┐            ┌────────▼────────┐
│  Stealth   │◄──────────►│  Mining Core    │
│  Layer     │            │  (Rust + CUDA)  │
└────────────┘            └─────────────────┘
```

## 📦 Cài Đặt

### Yêu Cầu Hệ Thống
- **OS**: Linux (Ubuntu 22.04+ recommended)
- **GPU**: NVIDIA with CUDA support (compute capability 3.5+)
- **CUDA**: 11.8 or higher
- **Rust**: 1.70+ (stable)
- **Python**: 3.10+ (for legacy compatibility)

### Build từ Source

```bash
# Clone repository
cd ~/opus-gpu/app/app-gpu

# Install Rust (nếu chưa có)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Build release binary
cargo build --release

# Binary sẽ ở target/release/mining-cli
```

### Build với Docker

```bash
# Build Docker image
docker build -t mining-gpu:v1.0.0 -f docker/Dockerfile.ubuntu-cuda .

# Run container với GPU support
docker run --gpus all \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/logs:/var/log/mining-gpu \
  mining-gpu:v1.0.0 start --config /app/config/default.toml
```

## 🚀 Sử Dụng

### Cấu Hình

Chỉnh sửa `config/default.toml`:

```toml
[mining]
pool_url = "stratum+tcp://your-pool.com:3333"
wallet_address = "your_wallet_address"
algorithm = "Ethash"
gpu_devices = [0, 1]  # GPU IDs to use
intensity = 80         # 0-100%

[stealth]
profile = "AiTraining"
process_name = "pytorch_train"
enable_resource_smoothing = true
```

### Chạy Mining

```bash
# Start mining (bắt đầu khai thác)
./target/release/mining-cli start --config config/default.toml

# Check status (kiểm tra trạng thái)
./target/release/mining-cli status

# Stop mining (dừng khai thác)
./target/release/mining-cli stop
```

### Python Wrapper (tương thích với code cũ)

```python
# Sử dụng từ Python (tích hợp với start_mining.py hiện tại)
import mining_core

# Create engine
engine = mining_core.MiningEngine(
    pool_url="stratum+tcp://pool.com:3333",
    wallet="0x...",
    algorithm="Ethash"
)

# Start mining
engine.start()

# Get stats
print(f"Hashrate: {engine.get_hashrate()} MH/s")

# Stop mining
engine.stop()
```

## 🔒 Bảo Mật

### Seccomp Profile

Hệ thống sử dụng **seccomp** để giới hạn syscalls:

```bash
# Apply seccomp profile
./scripts/apply_seccomp.sh
```

### AppArmor Policy

```bash
# Install AppArmor profile
sudo cp security/apparmor-profile /etc/apparmor.d/mining-gpu
sudo apparmor_parser -r /etc/apparmor.d/mining-gpu
```

### Namespace Isolation

Chạy với namespace isolation:

```bash
# Run with user namespace isolation
./target/release/mining-cli start --enable-namespace-isolation
```

### Cgroups Limits

```bash
# Limit CPU to 80%, Memory to 4GB
./scripts/apply_cgroups.sh
```

## 📊 Performance

| Metric | Python (legacy) | Rust + CUDA (new) | Improvement |
|--------|-----------------|-------------------|-------------|
| Hashrate (MH/s) | 45 | 58 | +29% |
| Memory (MB) | 850 | 320 | -62% |
| CPU Usage (%) | 15 | 4 | -73% |
| Startup (s) | 8.5 | 2.1 | -75% |

## 🧪 Testing

```bash
# Run unit tests
cargo test --all

# Run integration tests
cargo test --test integration_tests

# Run benchmarks
cargo bench
```

## 📝 Logging

Logs được lưu tại `/var/log/mining-gpu/`:

```bash
# View logs
tail -f /var/log/mining-gpu/app.log

# JSON logs (for structured parsing)
tail -f /var/log/mining-gpu/app.json
```

## 🔧 Troubleshooting

### GPU Not Detected

```bash
# Check NVIDIA driver
nvidia-smi

# Check CUDA installation
nvcc --version
```

### Permission Denied

```bash
# Add user to video group
sudo usermod -a -G video $USER

# Relogin for changes to take effect
```

### Connection Failed

```bash
# Test pool connectivity
nc -zv pool.example.com 3333

# Check firewall
sudo ufw status
```

## ⚠️ Disclaimer (Tuyên bố từ chối trách nhiệm)

Hệ thống này được thiết kế cho **nghiên cứu bảo mật** (academic/defensive research) và **kiểm thử hệ thống bảo mật Cloud**.

**QUAN TRỌNG**:
- ⚠️ Chỉ sử dụng trên infrastructure riêng hoặc cloud providers cho phép mining
- ⚠️ Vi phạm Terms of Service có thể dẫn đến khóa tài khoản
- ⚠️ Sử dụng stealth features có thể vi phạm pháp luật ở một số quốc gia

## 📚 Tài Liệu

- [Architecture](docs/ARCHITECTURE.md) - Thiết kế kiến trúc hệ thống
- [Stealth Techniques](docs/STEALTH_TECHNIQUES.md) - Chi tiết kỹ thuật ẩn danh
- [Deployment](docs/DEPLOYMENT.md) - Hướng dẫn triển khai production
- [API Documentation](docs/API.md) - API reference

## 🤝 Contributing

Pull requests are welcome! Xem [CONTRIBUTING.md](CONTRIBUTING.md) để biết thêm chi tiết.

## 📄 License

MIT License - xem [LICENSE](LICENSE) file.

## 🙏 Acknowledgments

- Rust community for amazing ecosystem
- NVIDIA for CUDA toolkit
- Mining pool operators
- Security researchers

---

**Built with ❤️ using Rust + CUDA**

**Odyssey AI System** | Version 1.0.0 | 2025-10-02
