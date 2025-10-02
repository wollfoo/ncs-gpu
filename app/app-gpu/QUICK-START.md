# 🚀 Quick Start Guide - Opus GPU Mining System

**Production-ready deployment** (triển khai sẵn sàng sản xuất) trong **5 phút**.

## ⚡ Option 1: Docker (Khuyến Nghị)

### Bước 1: Cài đặt Docker + NVIDIA Container Toolkit

```bash
# Cài Docker (nếu chưa có)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Cài NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Verify GPU access (Xác minh truy cập GPU)
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### Bước 2: Cấu hình

```bash
cd ~/opus-gpu/app/app-gpu

# Chỉnh sửa config/default.toml
nano config/default.toml
```

**Cấu hình tối thiểu:**
```toml
[mining]
pool_url = "stratum+tcp://your-pool.com:3333"
wallet_address = "YOUR_WALLET_ADDRESS"
algorithm = "Ethash"
gpu_devices = [0]  # GPU IDs từ nvidia-smi
intensity = 80
```

### Bước 3: Build & Run

```bash
# Build Docker image
docker build -t mining-gpu:latest -f docker/Dockerfile.ubuntu-cuda .

# Run container
docker run -d \
  --name opus-mining \
  --gpus all \
  --restart unless-stopped \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/logs:/var/log/mining-gpu \
  mining-gpu:latest

# Xem logs
docker logs -f opus-mining

# Dừng
docker stop opus-mining
```

### Bước 4 (Tùy chọn): Docker Compose

```bash
# Chạy với docker-compose
cd docker
docker-compose up -d

# Xem logs
docker-compose logs -f

# Dừng
docker-compose down
```

---

## 🛠️ Option 2: Build từ Source

### Bước 1: Cài đặt Rust

```bash
# Cài Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Verify
rustc --version
cargo --version
```

### Bước 2: Cài CUDA (nếu chưa có)

```bash
# Ubuntu 22.04
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
sudo dpkg -i cuda-keyring_1.0-1_all.deb
sudo apt-get update
sudo apt-get install -y cuda-11-8

# Verify
nvcc --version
nvidia-smi
```

### Bước 3: Build

```bash
cd ~/opus-gpu/app/app-gpu

# Build release binary
./scripts/build_release.sh

# Hoặc build thủ công
cargo build --release
```

### Bước 4: Run

```bash
# Chỉnh sửa config
nano config/default.toml

# Chạy
./target/release/mining-cli start --config config/default.toml

# Check status
./target/release/mining-cli status

# Dừng
./target/release/mining-cli stop
```

---

## 🐍 Option 3: Python Wrapper (Tích hợp với code cũ)

### Cài đặt

```bash
cd ~/opus-gpu/app/app-gpu

# Build Rust library
cargo build --release --lib

# Thêm vào PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)/python
```

### Sử dụng

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/azureuser/opus-gpu/app/app-gpu/python')

from mining_core_wrapper import MiningEngine, MiningConfig, MiningAlgorithm

# Tạo config
config = MiningConfig(
    pool_url="stratum+tcp://pool.example.com:3333",
    wallet_address="YOUR_WALLET_ADDRESS",
    algorithm=MiningAlgorithm.ETHASH,
    gpu_devices=[0],
    intensity=80,
)

# Tạo engine
engine = MiningEngine(config)

# Start mining
if engine.start():
    print("✅ Mining started!")

    # Get stats
    import time
    time.sleep(5)
    stats = engine.get_stats()
    print(f"📊 Hashrate: {stats.hashrate} MH/s")

    # Stop
    engine.stop()
```

### Tích hợp với `start_mining.py` hiện tại

```python
# Thêm vào start_mining.py
import sys
sys.path.insert(0, '/home/azureuser/opus-gpu/app/app-gpu/python')
from mining_core_wrapper import MiningEngine, MiningConfig, MiningAlgorithm

# Thay thế mining logic cũ
rust_config = MiningConfig(
    pool_url=os.getenv('POOL_URL'),
    wallet_address=os.getenv('WALLET_ADDRESS'),
    algorithm=MiningAlgorithm.ETHASH,
    gpu_devices=[0, 1],  # Từ config
    intensity=80,
)

rust_engine = MiningEngine(rust_config)
rust_engine.start()
```

---

## 📊 Monitoring & Debugging

### Xem GPU Status

```bash
# Real-time monitoring
watch -n 1 nvidia-smi

# Temperature & utilization
nvidia-smi --query-gpu=temperature.gpu,utilization.gpu --format=csv --loop=1
```

### Xem Logs

```bash
# Docker logs
docker logs -f opus-mining

# File logs (nếu build từ source)
tail -f /var/log/mining-gpu/app.log

# JSON logs (structured)
tail -f /var/log/mining-gpu/app.json | jq .
```

### Check Process

```bash
# Tìm mining process
ps aux | grep mining

# Check stealth process name
ps aux | grep pytorch_train  # Nếu dùng AI Training profile

# Check network connections
netstat -tnp | grep mining
```

### Performance Monitoring

```bash
# CPU usage
top -p $(pgrep mining-cli)

# Memory usage
ps -p $(pgrep mining-cli) -o pid,vsz,rss,comm

# GPU memory
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
```

---

## 🔒 Security Hardening

### Apply Seccomp

```bash
# Tạo seccomp profile
sudo mkdir -p /etc/seccomp
sudo cp security/seccomp-profile.json /etc/seccomp/mining-gpu.json

# Run với seccomp
docker run --security-opt seccomp=/etc/seccomp/mining-gpu.json ...
```

### Apply AppArmor

```bash
# Cài AppArmor profile
sudo cp security/apparmor-profile /etc/apparmor.d/mining-gpu
sudo apparmor_parser -r /etc/apparmor.d/mining-gpu

# Verify
sudo aa-status | grep mining
```

### Apply Cgroups

```bash
# Tạo cgroup
sudo cgcreate -g cpu,memory:/mining-gpu

# Giới hạn CPU 80%
echo 800000 | sudo tee /sys/fs/cgroup/cpu/mining-gpu/cpu.cfs_quota_us
echo 1000000 | sudo tee /sys/fs/cgroup/cpu/mining-gpu/cpu.cfs_period_us

# Giới hạn memory 4GB
echo 4294967296 | sudo tee /sys/fs/cgroup/memory/mining-gpu/memory.limit_in_bytes

# Run với cgroup
sudo cgexec -g cpu,memory:/mining-gpu ./target/release/mining-cli start
```

---

## 🚨 Troubleshooting

### Lỗi: "CUDA not found"

```bash
# Kiểm tra CUDA installation
nvcc --version
ls /usr/local/cuda/lib64/

# Set environment variables
export CUDA_HOME=/usr/local/cuda
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
export PATH=$CUDA_HOME/bin:$PATH
```

### Lỗi: "Permission denied" (GPU)

```bash
# Thêm user vào video group
sudo usermod -a -G video $USER

# Relogin
exit  # Rồi đăng nhập lại
```

### Lỗi: "Cannot connect to pool"

```bash
# Test connectivity
nc -zv pool.example.com 3333

# Check firewall
sudo ufw status
sudo ufw allow out 3333/tcp
```

### Lỗi: "Out of memory"

```bash
# Giảm intensity trong config
intensity = 60  # Thay vì 80

# Hoặc giảm số GPU
gpu_devices = [0]  # Chỉ dùng 1 GPU
```

### Lỗi: Build failed

```bash
# Update Rust
rustup update

# Clean và rebuild
cargo clean
cargo build --release

# Check dependencies
apt-get install -y build-essential cmake libssl-dev
```

---

## ⚡ Performance Tuning

### Tối ưu GPU

```bash
# Set persistence mode (giảm latency)
sudo nvidia-smi -pm 1

# Set power limit (giảm nhiệt)
sudo nvidia-smi -pl 200  # 200W limit

# Set clock speed
sudo nvidia-smi -ac 5001,1455  # Memory,Graphics MHz
```

### Tối ưu CPU

```bash
# Set CPU governor to performance
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### Tối ưu Network

```bash
# Increase network buffer
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.wmem_max=16777216
```

---

## 📈 Expected Results

| Metric | Target | Actual (sẽ khác tùy GPU) |
|--------|--------|---------------------------|
| Hashrate (RTX 3090) | ~120 MH/s | Verify với pool |
| CPU Usage | <5% | Check với `top` |
| Memory | <500MB | Check với `ps` |
| GPU Utilization | >95% | Check với `nvidia-smi` |
| GPU Temperature | <75°C | Check với `nvidia-smi` |

---

## 🎯 Next Steps

1. ✅ **Monitor** (Giám sát) - Xem logs và metrics 24h đầu
2. ✅ **Optimize** (Tối ưu) - Điều chỉnh intensity và power limit
3. ✅ **Secure** (Bảo mật) - Apply seccomp/AppArmor/cgroups
4. ✅ **Scale** (Mở rộng) - Thêm nhiều GPU hoặc nodes
5. ✅ **Automate** (Tự động hóa) - Setup systemd service hoặc cron

---

**⚠️ Disclaimer**: Chỉ sử dụng cho nghiên cứu bảo mật. Tuân thủ ToS của cloud providers và pháp luật địa phương.

**Need help?** Check full documentation:
- [Architecture](docs/ARCHITECTURE.md)
- [Stealth Techniques](docs/STEALTH_TECHNIQUES.md)
- [Deployment](docs/DEPLOYMENT.md)
- [API Reference](docs/API.md)
