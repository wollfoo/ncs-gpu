# ⚡ QUICKSTART GUIDE

## 🎯 Mục tiêu

Hướng dẫn nhanh để build và chạy **App-GPU** trong **5 phút**.

---

## 📋 Yêu cầu (Prerequisites)

### Bắt buộc

- ✅ **Linux** (Ubuntu 22.04+ hoặc CentOS 8+)
- ✅ **NVIDIA GPU** (Compute Capability ≥ 7.0)
- ✅ **NVIDIA Drivers** (550+)
- ✅ **CUDA** 12.0+
- ✅ **Rust** 1.75+

### Kiểm tra

```bash
# Check NVIDIA driver
nvidia-smi

# Check CUDA
nvcc --version

# Check Rust
rustc --version
```

---

## 🚀 Quick Start (5 phút)

### Step 1: Clone & Setup (30s)

```bash
# Navigate to project
cd /home/azureuser/opus-gpu/app/app-gpu

# Copy environment variables
cp .env.example .env

# Edit .env with your wallet address
nano .env
# Change: MINING_WALLET=YOUR_WALLET_ADDRESS_HERE
```

### Step 2: Build (2 phút)

```bash
# Build in release mode
./scripts/build.sh --release

# Or manually
cargo build --release
```

**Expected output**:
```
✅ Build successful!
📍 Binary location: target/release/app-gpu
📏 Binary size: ~45M
```

### Step 3: Configure (1 phút)

```bash
# Edit config
nano config/config.toml

# Minimum required changes:
# [gpu_executor.pool]
# wallet = "YOUR_WALLET_ADDRESS"
# url = "stratum+tcp://YOUR_POOL:PORT"
```

### Step 4: Run (30s)

```bash
# Run directly
./target/release/app-gpu --config config/config.toml

# Or with Docker
docker-compose up -d
```

**Expected output**:
```
🚀 Starting App-GPU v1.0.0
📁 Config file: config/config.toml
✅ Configuration loaded successfully
✅ Security plugin loaded
✅ Resource manager plugin loaded
✅ GPU executor plugin loaded
✅ Cloaking plugin loaded
✅ All plugins started successfully
🎯 App-GPU is running. Press Ctrl+C to stop.
```

### Step 5: Verify (30s)

```bash
# Check metrics
curl http://localhost:9090/metrics

# Check health
curl http://localhost:9090/health

# View logs
tail -f /var/log/app-gpu/app-gpu.log
```

---

## 🐳 Docker Quick Start (3 phút)

```bash
# Step 1: Build image (2 min)
docker build -t app-gpu:latest .

# Step 2: Run
docker run --gpus all \
  -e MINING_WALLET="YOUR_WALLET" \
  -e MINING_POOL_URL="stratum+tcp://pool.example.com:3333" \
  -v $(pwd)/config:/etc/app-gpu:ro \
  -p 9090:9090 \
  app-gpu:latest

# Or use docker-compose
docker-compose up -d
```

---

## 🔍 Troubleshooting

### CUDA not found

```bash
# Error: libcuda.so.1: cannot open shared object file
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
```

### Permission denied

```bash
# Add user to video group
sudo usermod -a -G video $USER
newgrp video
```

### Low GPU utilization

```bash
# Check QoS limits
grep "gpu_limit" config/config.toml

# Increase if needed
# gpu_limit = 0.95
```

---

## 📊 Monitor

### Grafana Dashboard

1. Open http://localhost:3000
2. Login: admin / admin
3. View GPU metrics dashboard

### Prometheus

1. Open http://localhost:9091
2. Query: `app_gpu_utilization_percent`

---

## 🛑 Stop

```bash
# Direct run
Ctrl+C

# Docker
docker-compose down

# Systemd
sudo systemctl stop app-gpu
```

---

## 📚 Next Steps

- Read [README.md](README.md) for full documentation
- Read [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for technical details

---

## ✅ Success Criteria

Sau 5 phút, bạn nên thấy:

- [x] App-GPU running without errors
- [x] GPU utilization >80%
- [x] Metrics available at http://localhost:9090/metrics
- [x] Hashrate reporting to pool

**Congratulations! 🎉 App-GPU is now running!**
