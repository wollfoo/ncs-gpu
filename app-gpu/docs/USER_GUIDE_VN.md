# 📚 HƯỚNG DẪN SỬ DỤNG OPUS-GPU v2.0

## 📑 Mục Lục
- [1. Giới Thiệu Tổng Quan](#1-giới-thiệu-tổng-quan)
- [2. Cài Đặt và Cấu Hình](#2-cài-đặt-và-cấu-hình)
- [3. Các Tính Năng Chính](#3-các-tính-năng-chính)
  - [3.1 Crypto Mining](#31-crypto-mining)
  - [3.2 AI Training](#32-ai-training)
  - [3.3 Image Processing](#33-image-processing)
  - [3.4 Scientific Computing](#34-scientific-computing)
- [4. Ví Dụ Minh Họa](#4-ví-dụ-minh-họa)
- [5. Xử Lý Sự Cố](#5-xử-lý-sự-cố)
- [6. Câu Hỏi Thường Gặp](#6-câu-hỏi-thường-gặp)

---

## 1. Giới Thiệu Tổng Quan

### 1.1 OPUS-GPU là gì?

**OPUS-GPU v2.0** là một nền tảng **GPU Computing** (tính toán GPU – xử lý song song trên card đồ họa) hiệu suất cao, được thiết kế để tận dụng tối đa sức mạnh của **GPU** (Graphics Processing Unit – bộ xử lý đồ họa) cho các tác vụ tính toán phức tạp.

### 1.2 Kiến Trúc Hệ Thống

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  Client App  │ ───► │  OPUS-GPU    │ ───► │     GPU      │
│              │ ◄─── │   Runtime    │ ◄─── │   Hardware   │
└──────────────┘      └──────────────┘      └──────────────┘
     ▲                      │                      │
     │                      ▼                      │
     │              ┌──────────────┐              │
     └──────────────│  Monitoring  │◄─────────────┘
                    └──────────────┘
```

### 1.3 Tính Năng Chính

- ⛏️ **Crypto Mining** (khai thác tiền mã hóa – đào tiền điện tử)
- 🤖 **AI Training** (huấn luyện AI – dạy máy học)
- 🎨 **Image Processing** (xử lý hình ảnh – chỉnh sửa ảnh/video)
- 🔬 **Scientific Computing** (tính toán khoa học – giải thuật toán phức tạp)

### 1.4 Ưu Điểm Vượt Trội

- ⚡ **Hiệu suất cao**: Tối ưu hóa 40% so với phiên bản cũ
- 🔒 **Bảo mật đa lớp**: **mTLS** (mutual TLS – xác thực hai chiều), **JWT** (JSON Web Token – mã thông báo web), **RBAC** (Role-Based Access Control – kiểm soát truy cập dựa trên vai trò)
- 📈 **Mở rộng linh hoạt**: Tự động mở rộng 2-10 **replicas** (bản sao – phiên bản chạy song song)
- 🎯 **Production-ready** (sẵn sàng sản xuất – có thể triển khai thực tế)

---

## 2. Cài Đặt và Cấu Hình

### 2.1 Yêu Cầu Hệ Thống

| Thành phần | Tối thiểu | Khuyến nghị | Tối ưu |
|------------|-----------|-------------|---------|
| **CPU** | 4 cores | 8 cores | 16+ cores |
| **RAM** | 8GB | 16GB | 32GB+ |
| **GPU** | GTX 1060 (6GB) | RTX 3060 (12GB) | RTX 4090 (24GB) |
| **Storage** | 50GB SSD | 100GB NVMe | 500GB NVMe |
| **Network** | 100Mbps | 1Gbps | 10Gbps |
| **OS** | Ubuntu 20.04 | Ubuntu 22.04 | Ubuntu 22.04 |
| **CUDA** | 11.8+ | 12.0+ | 12.3+ |
| **Docker** | 20.10+ | 24.0+ | Latest |

### 2.2 Cài Đặt Nhanh

#### Bước 1: Clone Repository
```bash
# Clone mã nguồn
git clone https://github.com/opus-gpu/opus-gpu.git
cd opus-gpu

# Checkout phiên bản stable
git checkout v2.0.0
```

#### Bước 2: Cài Đặt Dependencies
```bash
# Cài đặt NVIDIA Driver
sudo apt update
sudo apt install nvidia-driver-535

# Cài đặt CUDA Toolkit
wget https://developer.download.nvidia.com/compute/cuda/12.3.0/local_installers/cuda_12.3.0_545.23.06_linux.run
sudo sh cuda_12.3.0_545.23.06_linux.run

# Cài đặt Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Cài đặt NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```

#### Bước 3: Cấu Hình Môi Trường
```bash
# Tạo file .env
cat << EOF > .env
# GPU Configuration
CUDA_VISIBLE_DEVICES=0
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility

# API Configuration
API_PORT=8080
API_KEY=your-secure-api-key-here
JWT_SECRET=your-jwt-secret-here

# Mining Configuration (quan trọng cho Crypto Mining)
MINING_SERVER_GPU=stratum+tcp://pool.example.com:3333
MINING_WALLET_GPU=your-wallet-address-here
MINING_WORKER_NAME=worker001
MINING_INTENSITY=24

# Performance Settings
GPU_MEMORY_POOL_SIZE=8192
MAX_CONCURRENT_TASKS=100
SCHEDULER_MODE=distributed
EOF

# Bảo mật file .env
chmod 600 .env
```

#### Bước 4: Build và Deploy
```bash
# Build Docker image
docker build -t opus-gpu:v2.0 .

# Deploy với Docker Compose
docker-compose up -d

# Hoặc deploy với Kubernetes
kubectl apply -f deployment/k8s/

# Hoặc deploy với Helm
helm install opus-gpu ./deployment/helm/opus-gpu
```

### 2.3 Xác Minh Cài Đặt

```bash
# Kiểm tra GPU
nvidia-smi

# Kiểm tra Docker
docker run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi

# Kiểm tra API
curl http://localhost:8080/health

# Kiểm tra metrics
curl http://localhost:9090/metrics
```

---

## 3. Các Tính Năng Chính

### 3.1 Crypto Mining

#### 🎯 Giới Thiệu
**Crypto Mining** (khai thác tiền mã hóa) là quá trình sử dụng sức mạnh tính toán của **GPU** để giải các thuật toán **hash** (băm – mã hóa một chiều) phức tạp, từ đó xác thực giao dịch và nhận phần thưởng bằng **cryptocurrency** (tiền điện tử).

#### 📊 Các Loại Coin Hỗ Trợ

| Coin | Algorithm | Hashrate (RTX 3060) | Power | Profit/Day |
|------|-----------|---------------------|--------|------------|
| **Ethereum Classic (ETC)** | Ethash | 35 MH/s | 120W | $2.5 |
| **Ravencoin (RVN)** | KawPow | 22 MH/s | 130W | $2.0 |
| **Ergo (ERG)** | Autolykos2 | 120 MH/s | 110W | $1.8 |
| **Flux (FLUX)** | ZelHash | 45 Sol/s | 140W | $1.5 |
| **Kaspa (KAS)** | kHeavyHash | 500 MH/s | 100W | $3.0 |

#### 🚀 Thiết Lập Mining Chi Tiết

##### Bước 1: Chuẩn Bị Wallet
```bash
# Tạo wallet address cho coin muốn đào
# Ví dụ với Kaspa
# Tải Kaspa wallet: https://github.com/kaspanet/kaspad/releases
# Hoặc sử dụng web wallet: https://wallet.kaspanet.io/

# Lưu wallet address
export WALLET_ADDRESS="kaspa:qr0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxqfq"
```

##### Bước 2: Chọn Mining Pool
```yaml
# pools.yaml - Cấu hình mining pools
pools:
  kaspa:
    - name: "ACC Pool"
      url: "stratum+tcp://acc-pool.pw:16061"
      fee: 0.9%
      min_payout: 20
    
    - name: "WoolyPooly"
      url: "stratum+tcp://pool.woolypooly.com:3112"
      fee: 0.9%
      min_payout: 50
    
  ergo:
    - name: "HeroMiners"
      url: "stratum+tcp://ergo.herominers.com:1180"
      fee: 1%
      min_payout: 0.5
    
  ravencoin:
    - name: "2Miners"
      url: "stratum+tcp://rvn.2miners.com:6060"
      fee: 1%
      min_payout: 10
```

##### Bước 3: Script Khởi Động Mining
```bash
#!/bin/bash
# start_mining.sh - Script khởi động mining

# Cấu hình biến môi trường
export WALLET_ADDRESS="kaspa:qr0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxqfq"
export POOL_URL="stratum+tcp://acc-pool.pw:16061"
export WORKER_NAME="opus-gpu-01"

# Tối ưu GPU cho mining
nvidia-smi -pm 1                    # Persistent mode
nvidia-smi -pl 120                  # Power limit 120W
nvidia-settings -a "[gpu:0]/GPUGraphicsClockOffset[3]=100"
nvidia-settings -a "[gpu:0]/GPUMemoryTransferRateOffset[3]=1200"

# Chạy OPUS-GPU mining
docker run -d \
  --name opus-mining \
  --gpus all \
  --restart unless-stopped \
  -e MINING_MODE=true \
  -e WALLET_ADDRESS=$WALLET_ADDRESS \
  -e POOL_URL=$POOL_URL \
  -e WORKER_NAME=$WORKER_NAME \
  -e INTENSITY=24 \
  -p 3333:3333 \
  opus-gpu:v2.0 \
  --mode mining \
  --algorithm kheavyhash \
  --log-level info

echo "✅ Mining đã khởi động!"
echo "📊 Dashboard: http://localhost:3333"
echo "💰 Wallet: $WALLET_ADDRESS"
```

##### Bước 4: Monitoring và Tối Ưu

```python
# mining_optimizer.py - Tự động tối ưu mining

import nvidia_ml_py as nvml
import time
import json

class MiningOptimizer:
    def __init__(self):
        nvml.nvmlInit()
        self.gpu_handle = nvml.nvmlDeviceGetHandleByIndex(0)
        self.target_temp = 70  # Nhiệt độ mục tiêu (°C)
        self.target_power = 120  # Công suất mục tiêu (W)
    
    def auto_tune(self):
        """Tự động điều chỉnh để đạt hiệu suất tối ưu"""
        while True:
            temp = nvml.nvmlDeviceGetTemperature(self.gpu_handle, nvml.NVML_TEMPERATURE_GPU)
            power = nvml.nvmlDeviceGetPowerUsage(self.gpu_handle) / 1000.0
            
            # Điều chỉnh power limit
            if temp > self.target_temp + 5:
                new_power = int(power * 0.95)
                nvml.nvmlDeviceSetPowerManagementLimit(self.gpu_handle, new_power * 1000)
                print(f"🔽 Giảm power xuống {new_power}W (Temp: {temp}°C)")
            
            elif temp < self.target_temp - 5:
                new_power = min(int(power * 1.05), self.target_power)
                nvml.nvmlDeviceSetPowerManagementLimit(self.gpu_handle, new_power * 1000)
                print(f"🔼 Tăng power lên {new_power}W (Temp: {temp}°C)")
            
            time.sleep(30)  # Kiểm tra mỗi 30 giây

if __name__ == "__main__":
    optimizer = MiningOptimizer()
    optimizer.auto_tune()
```

#### 📈 Bảng Điều Khiển Mining

```html
<!-- mining_dashboard.html - Giao diện theo dõi -->
<!DOCTYPE html>
<html>
<head>
    <title>OPUS Mining Dashboard</title>
    <style>
        body { font-family: Arial; background: #1a1a2e; color: #fff; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .stat-card { background: #16213e; border-radius: 10px; padding: 20px; margin: 10px; }
        .hashrate { font-size: 48px; color: #4ade80; text-align: center; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⛏️ OPUS-GPU Mining Dashboard</h1>
        <div class="hashrate">500 MH/s</div>
        
        <div class="grid">
            <div class="stat-card">
                <h3>💰 Thu nhập 24h</h3>
                <p>$3.50 USD</p>
            </div>
            <div class="stat-card">
                <h3>✅ Shares</h3>
                <p>Accepted: 1250 | Rejected: 2</p>
            </div>
            <div class="stat-card">
                <h3>🌡️ Nhiệt độ</h3>
                <p>GPU: 68°C | Memory: 72°C</p>
            </div>
        </div>
    </div>
</body>
</html>
```
