# OPUS-GPU Quick Start Guide

🚀 **5-Minute Quick Start** cho **OPUS-GPU v2.0** - Bắt đầu mining trong 5 phút!

## 📋 Tổng quan

Hướng dẫn này giúp bạn bắt đầu với **OPUS-GPU** trong thời gian ngắn nhất với **minimal setup** (cấu hình tối thiểu).

## ⚡ Yêu cầu tối thiểu

```yaml
hardware:
  gpu: "NVIDIA GTX 1060+ hoặc AMD RX 580+"
  ram: "8 GB"
  storage: "10 GB khả dụng"

software:
  os: "Ubuntu 20.04+ / Windows 10+ / macOS 12+"
  drivers: "NVIDIA 525+ hoặc AMD 22.40+"
  docker: "20.10+ (khuyến nghị)"
```

## 🐳 Method 1: Docker Quick Start (Khuyến nghị)

### Step 1: Cài đặt Docker + NVIDIA Runtime
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Verify GPU access
docker run --rm --gpus all nvidia/cuda:12.2-base-ubuntu22.04 nvidia-smi
```

### Step 2: Chạy OPUS-GPU
```bash
# Quick start với default settings
docker run -d \
  --name opus-gpu-quickstart \
  --runtime=nvidia \
  --gpus all \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 9090:9090 \
  -e OPUS_GPU_POOL_URL="stratum+tcp://pool.example.com:4444" \
  -e OPUS_GPU_WALLET_ADDRESS="your_wallet_address_here" \
  -e OPUS_GPU_WORKER_NAME="worker01" \
  opus-gpu:latest

# Check status
docker logs opus-gpu-quickstart -f
```

### Step 3: Verify Operation
```bash
# Check mining status
curl http://localhost:8080/api/v1/status

# View real-time stats
curl http://localhost:8080/api/v1/mining/stats

# Check GPU metrics
curl http://localhost:9090/metrics | grep gpu
```

## 💻 Method 2: Pre-built Binary

### Step 1: Download Binary
```bash
# Linux x64
wget https://github.com/opus-gpu/opus-gpu/releases/latest/download/opus-gpu-linux-x64.tar.gz
tar -xzf opus-gpu-linux-x64.tar.gz
chmod +x opus-gpu

# Windows x64
# Download opus-gpu-windows-x64.zip from GitHub releases
# Extract and run opus-gpu.exe
```

### Step 2: Basic Configuration
```bash
# Create minimal config
cat > config.toml << EOF
[mining]
algorithm = "SHA256"
gpu_devices = [0]
max_workers = 2

[pool]
urls = ["stratum+tcp://pool.example.com:4444"]
username = "your_wallet_address_here"
password = "worker01"

[api.rest]
host = "127.0.0.1"
port = 8080
EOF
```

### Step 3: Start Mining
```bash
# Linux/macOS
./opus-gpu --config config.toml

# Windows
opus-gpu.exe --config config.toml
```

## 🔧 Quick Configuration Examples

### Single GPU Setup
```toml
# quickstart-single.toml
[mining]
algorithm = "SHA256"
max_workers = 2
gpu_devices = [0]
batch_size = 1000

[pool]
urls = ["stratum+tcp://your-pool.com:4444"]
username = "your_wallet_address"
password = "quickstart-worker"

[monitoring]
enabled = true
metrics_port = 9090

[api.rest]
host = "127.0.0.1"
port = 8080
```

### Multi-GPU Setup
```toml
# quickstart-multi.toml
[mining]
algorithm = "SHA256"
max_workers = 4
gpu_devices = [0, 1, 2, 3]
worker_threads = 2
batch_size = 2000

[pool]
urls = [
  "stratum+tcp://primary-pool.com:4444",
  "stratum+tcp://backup-pool.com:4444"
]
username = "your_wallet_address"
password = "multi-gpu-worker"

[monitoring]
enabled = true
metrics_port = 9090
temperature_threshold = 75.0

[api.rest]
host = "0.0.0.0"
port = 8080
```

## 🎯 Command Line Quick Start

### Essential Commands
```bash
# Start với default config
opus-gpu

# Specify config file
opus-gpu --config my-config.toml

# Quick mining với command line
opus-gpu \
  --pool-url "stratum+tcp://pool.example.com:4444" \
  --wallet-address "your_wallet_here" \
  --gpu-devices "0,1" \
  --worker-name "quickstart"

# Development mode
opus-gpu --dev-mode --log-level debug

# Benchmark mode
opus-gpu --benchmark --gpu-devices "0"
```

### Environment Variables
```bash
# Quick setup via environment
export OPUS_GPU_POOL_URL="stratum+tcp://pool.example.com:4444"
export OPUS_GPU_WALLET_ADDRESS="your_wallet_address"
export OPUS_GPU_WORKER_NAME="quickstart-worker"
export OPUS_GPU_GPU_DEVICES="0,1"
export OPUS_GPU_LOG_LEVEL="info"

# Start mining
opus-gpu
```

## 📊 Quick Monitoring

### Web Dashboard
```bash
# Open web dashboard
xdg-open http://localhost:8080
# hoặc truy cập: http://localhost:8080
```

### Real-time Stats
```bash
# Mining statistics
curl -s http://localhost:8080/api/v1/mining/stats | jq

# GPU status
curl -s http://localhost:8080/api/v1/devices | jq

# System health
curl -s http://localhost:8080/health
```

### WebSocket Monitoring
```javascript
// Quick WebSocket connection
const ws = new WebSocket('ws://localhost:8081/ws');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Mining update:', data);
};

ws.onopen = function() {
    // Subscribe to mining stats
    ws.send(JSON.stringify({
        type: 'subscribe',
        topics: ['mining.stats', 'device.status']
    }));
};
```

## 🔍 Quick Verification

### Check GPU Detection
```bash
# Verify GPUs are detected
opus-gpu --list-devices

# Test GPU functionality
opus-gpu --benchmark --duration 30
```

### Network Connectivity
```bash
# Test pool connection
telnet pool.example.com 4444

# Check firewall
sudo ufw status
```

### Performance Check
```bash
# Monitor GPU usage
nvidia-smi -l 1

# Check system resources
htop

# View mining logs
tail -f /var/log/opus-gpu.log
```

## 🚀 Quick Optimization

### Performance Boost
```toml
# Add to config for better performance
[mining]
batch_size = 2000        # Larger batches
worker_threads = 2       # More threads per GPU
memory_size = 1073741824 # 1GB memory allocation

[monitoring]
stats_interval_secs = 5  # Faster updates
```

### Power Optimization
```bash
# NVIDIA power management
sudo nvidia-smi -pm 1
sudo nvidia-smi -pl 250  # Set 250W power limit

# CPU performance mode
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

## 🐛 Quick Troubleshooting

### Common Issues

#### GPU Not Found
```bash
# Check drivers
nvidia-smi
# hoặc
clinfo

# Verify permissions
ls -la /dev/nvidia*
```

#### Connection Failed
```bash
# Test network
ping pool.example.com
telnet pool.example.com 4444

# Check logs
docker logs opus-gpu-quickstart
```

#### Low Performance
```bash
# Check GPU utilization
nvidia-smi

# Monitor temperatures
nvidia-smi -q -d TEMPERATURE

# Verify configuration
opus-gpu --config config.toml --validate
```

### Quick Fixes
```bash
# Restart mining
docker restart opus-gpu-quickstart

# Reset configuration
cp config/default.toml config/current.toml

# Check system resources
free -h
df -h
```

## 📱 Quick Mobile Monitoring

### Setup Ngrok (External Access)
```bash
# Install ngrok
wget https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-amd64.zip
unzip ngrok-stable-linux-amd64.zip

# Expose API
./ngrok http 8080

# Access từ mobile: https://xxxxx.ngrok.io
```

### Mobile-Friendly API
```bash
# Compact stats for mobile
curl http://localhost:8080/api/v1/mining/stats?format=compact

# Key metrics only
curl http://localhost:8080/api/v1/metrics/summary
```

## 🎓 Next Steps

### **Upgrade to Production**
- Đọc [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) cho production setup
- Cấu hình monitoring với Prometheus/Grafana
- Setup backup và disaster recovery

### **Advanced Features**
- Tìm hiểu [API_REFERENCE.md](API_REFERENCE.md) cho automation
- Khám phá plugin system
- Optimize performance cho hardware cụ thể

### **Community**
- Join Discord: https://discord.gg/opus-gpu
- GitHub Issues: https://github.com/opus-gpu/opus-gpu/issues
- Documentation: https://docs.opus-gpu.com

## 💡 Pro Tips

```bash
# Quick alias for easier management
echo 'alias opus="docker logs opus-gpu-quickstart -f"' >> ~/.bashrc
echo 'alias opus-stats="curl -s http://localhost:8080/api/v1/mining/stats | jq"' >> ~/.bashrc
echo 'alias opus-restart="docker restart opus-gpu-quickstart"' >> ~/.bashrc

# Reload bash
source ~/.bashrc

# Now use shortcuts
opus-stats
opus-restart
```

## 📞 Quick Support

### **Self-Help**
```bash
# Built-in help
opus-gpu --help

# Configuration validation
opus-gpu --config config.toml --validate

# System diagnostics
opus-gpu --diagnose
```

### **Get Help**
- **Discord**: https://discord.gg/opus-gpu (fastest response)
- **GitHub**: https://github.com/opus-gpu/opus-gpu/issues
- **Email**: support@opus-gpu.com

---

**🎉 Happy Mining with OPUS-GPU!** | **Optimized for Performance & Simplicity**