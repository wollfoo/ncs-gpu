# GPU Mining Core System
# Hệ Thống Khai Thác GPU

## ⚠️ CẢNH BÁO BẢO MẬT / SECURITY WARNING

**Hệ thống này được thiết kế CHỈ cho mục đích NGHIÊN CỨU BẢO MẬT.**

This system is designed ONLY for SECURITY RESEARCH purposes.

Việc sử dụng trong môi trường production có thể vi phạm:
- Cloud Provider Terms of Service (ToS)
- Computer Fraud and Abuse Act (CFAA)
- Cryptocurrency mining regulations
- Local laws and regulations

## 📋 Tổng Quan / Overview

GPU Mining Core là một **research framework** (framework nghiên cứu) được thiết kế để:
- Nghiên cứu **GPU resource management** (quản lý tài nguyên GPU)
- Phát triển **detection mechanisms** (cơ chế phát hiện) cho mining malware
- Kiểm tra **security controls** (kiểm soát bảo mật) trong cloud environments
- Đánh giá **stealth techniques** (kỹ thuật ẩn giấu) được sử dụng bởi malware

## 🏗️ Kiến Trúc / Architecture

```
┌─────────────────────────────────┐
│     Camouflage Layer            │  <- AI/ML workload mimicking
├─────────────────────────────────┤
│     Stealth Layer               │  <- Process hiding, obfuscation
├─────────────────────────────────┤
│     Orchestration Layer         │  <- Task scheduling, monitoring
├─────────────────────────────────┤
│     Mining Core (Rust)          │  <- Core mining implementation
├─────────────────────────────────┤
│     Hardware Abstraction        │  <- CUDA/OpenCL interface
└─────────────────────────────────┘
```

## 🚀 Cài Đặt / Installation

### Yêu Cầu / Requirements

- **Hardware**:
  - NVIDIA GPU với CUDA Compute Capability ≥ 6.0
  - Minimum 4GB VRAM
  - 8GB System RAM

- **Software**:
  - Ubuntu 20.04+ hoặc compatible Linux
  - NVIDIA Driver ≥ 470
  - CUDA Toolkit 11.8+
  - Docker 20.10+ với nvidia-docker2
  - Rust 1.75+ (cho development)

### Build từ Source

```bash
# Clone repository
git clone https://github.com/security-research/gpu-miner-core.git
cd gpu-miner-core

# Build với Cargo
cargo build --release

# Hoặc build Docker image
docker build -t gpu-miner:latest .
```

## 🔧 Cấu Hình / Configuration

### Environment Variables

```bash
# Required - Bắt buộc
export WALLET_ADDRESS="your_wallet_address"
export POOL_ADDRESS="stratum+tcp://pool.example.com:3333"

# Optional - Tùy chọn
export WORKER_NAME="worker-01"
export MINING_ALGO="kawpow"
export INTENSITY=75
export STEALTH_MODE=true
export GPU_INDICES="0,1"  # Multiple GPUs
```

### Configuration File

Copy và edit file cấu hình:
```bash
cp config.toml.example config.toml
nano config.toml
```

## 🏃 Chạy / Running

### Docker (Recommended)

```bash
# Run với GPU support
docker run --rm -it \
  --runtime=nvidia \
  --gpus all \
  -e WALLET_ADDRESS="$WALLET_ADDRESS" \
  -e POOL_ADDRESS="$POOL_ADDRESS" \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  gpu-miner:latest

# Run với docker-compose
docker-compose up -d
```

### Native Binary

```bash
# Run với config file
./target/release/gpu-miner --config config.toml

# Run với environment variables
WALLET_ADDRESS="..." POOL_ADDRESS="..." ./target/release/gpu-miner
```

## 📊 Monitoring

### Metrics Endpoint

Hệ thống expose Prometheus metrics tại port 9090:

```bash
# View metrics
curl http://localhost:9090/metrics

# Metrics available:
# - gpu_hashrate_mhs: Current hashrate
# - gpu_temperature_celsius: GPU temperature
# - gpu_power_watts: Power consumption
# - shares_accepted_total: Accepted shares
# - shares_rejected_total: Rejected shares
```

### Logs

Logs được lưu tại `/app/logs/` với rotation tự động:
- `gpu-miner.log`: Main application log
- `gpu_stats.csv`: GPU statistics
- `stealth.log`: Stealth mode operations

## 🥷 Stealth Mode

Hệ thống hỗ trợ nhiều **wrapper modes** để ngụy trang:

### AI Training Mode
Giả lập PyTorch/TensorFlow training:
```toml
[stealth]
wrapper_mode = "ai_training"
process_name = "python3"
```

### Image Processing Mode
Giả lập OpenCV operations:
```toml
[stealth]
wrapper_mode = "image_processing"
process_name = "opencv_worker"
```

### Scientific Computing Mode
Giả lập HPC workloads:
```toml
[stealth]
wrapper_mode = "scientific_computing"
process_name = "mpirun"
```

## 🔒 Security Considerations

### Isolation
- Run trong **isolated environment** (môi trường cô lập)
- Use **network segmentation** (phân đoạn mạng)
- Enable **AppArmor/SELinux** profiles
- Drop unnecessary **capabilities**

### Detection Avoidance Research
Hệ thống implement các techniques để research:
- Process name spoofing
- Resource usage jittering
- Pattern randomization
- Traffic obfuscation

### Responsible Disclosure
Nếu phát hiện vulnerabilities:
1. Document findings chi tiết
2. Contact affected vendors
3. Follow responsible disclosure timeline
4. Share detection signatures

## 🧪 Testing

### Unit Tests
```bash
cargo test
```

### Integration Tests
```bash
cargo test --test integration
```

### Benchmark
```bash
cargo bench
```

## 📈 Performance Tuning

### GPU Optimization
```toml
[gpu]
mem_clock_offset = 1000   # Memory overclock
core_clock_offset = 100    # Core overclock
power_limit = 85           # Power efficiency
```

### Algorithm Tuning
```toml
[mining]
intensity = 80            # Higher intensity
auto_switch = true        # Auto profit switching
```

## 🐛 Troubleshooting

### Common Issues

**GPU Not Detected:**
```bash
# Check GPU visibility
nvidia-smi
# Check CUDA installation
nvcc --version
```

**Low Hashrate:**
- Check GPU temperature và throttling
- Verify power limits
- Update GPU drivers

**Connection Issues:**
- Verify pool address và port
- Check firewall rules
- Test với different DNS servers

## 📚 API Documentation

### Health Check
```
GET /health
Response: {"status": "healthy", "uptime": 3600}
```

### Stats Endpoint
```
GET /stats
Response: {
  "hashrate": 75.5,
  "temperature": 72,
  "shares": {"accepted": 150, "rejected": 2}
}
```

## 🤝 Contributing

Contributions cho security research được welcome:

1. Fork repository
2. Create feature branch
3. Commit changes với clear messages
4. Push to branch
5. Create Pull Request

## 📜 License

This project is for EDUCATIONAL and RESEARCH purposes only.

Sử dụng có trách nhiệm và tuân thủ mọi luật pháp địa phương.

## ⚠️ Disclaimer

Các tác giả không chịu trách nhiệm cho bất kỳ việc lạm dụng hoặc thiệt hại nào gây ra bởi phần mềm này. Người dùng chịu hoàn toàn trách nhiệm về việc sử dụng và phải tuân thủ mọi quy định pháp luật có liên quan.

The authors are not responsible for any misuse or damage caused by this software. Users are fully responsible for their usage and must comply with all applicable laws and regulations.

## 📞 Contact

For security research collaboration:
- Email: security-research@example.com
- PGP Key: [Public Key ID]

---

**REMEMBER**: This is a RESEARCH TOOL. Use responsibly and ethically.
