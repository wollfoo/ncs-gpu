# 📚 HƯỚNG DẪN SỬ DỤNG HỆ THỐNG OPUS-GPU v2.0

## 📋 MỤC LỤC

1. [Giới thiệu tổng quan](#giới-thiệu-tổng-quan)
2. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
3. [Hướng dẫn cài đặt](#hướng-dẫn-cài-đặt)
4. [Cấu hình hệ thống](#cấu-hình-hệ-thống)
5. [Mô tả chức năng chính](#mô-tả-chức-năng-chính)
6. [Hướng dẫn sử dụng thực tế](#hướng-dẫn-sử-dụng-thực-tế)
7. [Giám sát và quản lý](#giám-sát-và-quản-lý)
8. [Xử lý sự cố thường gặp](#xử-lý-sự-cố-thường-gặp)
9. [Tối ưu hiệu suất](#tối-ưu-hiệu-suất)
10. [Phụ lục](#phụ-lục)

---

## 🎯 GIỚI THIỆU TỔNG QUAN

### Mục đích sử dụng

OPUS-GPU v2.0 là hệ thống khai thác GPU hiệu năng cao được phát triển bằng Rust, được thiết kế để:

- **Khai thác cryptocurrency** với hiệu suất tối ưu trên GPU NVIDIA
- **Quản lý tài nguyên** thông minh với khả năng tự động điều chỉnh nhiệt độ và công suất
- **Giám sát thời gian thực** qua REST API và Prometheus metrics
- **Tự động hóa** quá trình khai thác với khả năng phục hồi lỗi tự động
- **Bảo mật doanh nghiệp** với mã hóa TLS và xác thực JWT

### Phạm vi ứng dụng

Hệ thống phù hợp cho:
- ✅ **Các farm khai thác** quy mô vừa và lớn
- ✅ **Nhà phát triển** cần tích hợp API khai thác
- ✅ **Doanh nghiệp** yêu cầu giải pháp khai thác ổn định
- ✅ **Nghiên cứu** tối ưu hóa thuật toán khai thác

### Kiến trúc tổng quan

```
┌─────────────────────────────────────────────┐
│           OPUS-GPU v2.0 System              │
├─────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ REST API │  │  Mining  │  │ Resource │ │
│  │  Server  │◄─┤  Engine  ├─►│ Manager  │ │
│  └──────────┘  └──────────┘  └──────────┘ │
│        ▲              ▲             ▲       │
│        │              │             │       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │Prometheus│  │  Thermal │  │ Security │ │
│  │ Metrics  │  │  Control │  │  Layer   │ │
│  └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────┘
```

---

## 💻 YÊU CẦU HỆ THỐNG

### Phần cứng tối thiểu

| Thành phần | Yêu cầu tối thiểu | Khuyến nghị |
|------------|-------------------|-------------|
| **CPU** | 4 cores, 2.0 GHz | 8+ cores, 3.0+ GHz |
| **RAM** | 8 GB | 16+ GB |
| **GPU** | NVIDIA GTX 1060 | RTX 3070 trở lên |
| **Storage** | 50 GB SSD | 100+ GB NVMe SSD |
| **Network** | 10 Mbps | 100+ Mbps |

### Phần mềm yêu cầu

```bash
# Hệ điều hành
- Ubuntu 20.04/22.04 LTS (khuyến nghị)
- CentOS 8+/RHEL 8+
- Debian 11+

# NVIDIA Driver và CUDA
- NVIDIA Driver: 470.xx trở lên
- CUDA Toolkit: 11.8 hoặc 12.0+
- NVIDIA Container Toolkit (cho Docker)

# Runtime và công cụ
- Docker: 24.0+
- Docker Compose: 2.20+
- Git: 2.x
- Rust: 1.75+ (nếu build từ source)
```

### Kiểm tra môi trường

```bash
# Kiểm tra GPU NVIDIA
nvidia-smi

# Kiểm tra CUDA
nvcc --version

# Kiểm tra Docker
docker --version
docker-compose --version

# Kiểm tra GPU trong Docker
docker run --rm --gpus all nvidia/cuda:12.2.0-base nvidia-smi
```

---

## 🚀 HƯỚNG DẪN CÀI ĐẶT

### Phương pháp 1: Cài đặt nhanh (Khuyến nghị)

```bash
# 1. Clone repository
git clone https://github.com/opus-gpu/opus-gpu.git
cd opus-gpu/app/app-gpu

# 2. Chạy script cài đặt tự động
chmod +x scripts/deploy.sh
./scripts/deploy.sh production

# 3. Kiểm tra trạng thái
docker-compose ps
curl http://localhost:8080/health
```

### Phương pháp 2: Cài đặt thủ công

#### Bước 1: Chuẩn bị môi trường

```bash
# Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# Cài đặt các gói cần thiết
sudo apt install -y build-essential git curl

# Cài đặt NVIDIA Driver (nếu chưa có)
sudo apt install -y nvidia-driver-470

# Cài đặt Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Cài đặt NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```

#### Bước 2: Clone và build

```bash
# Clone repository
git clone https://github.com/opus-gpu/opus-gpu.git
cd opus-gpu/app/app-gpu

# Build từ source (tùy chọn)
cargo build --release --features "cuda,metrics,security"

# Hoặc sử dụng binary có sẵn
chmod +x target/release/opus-production
```

#### Bước 3: Cấu hình

```bash
# Sao chép file cấu hình mẫu
cp configs/config.toml.template configs/config.toml

# Chỉnh sửa cấu hình
vim configs/config.toml
```

#### Bước 4: Khởi động hệ thống

```bash
# Khởi động với Docker
docker-compose up -d

# Hoặc khởi động trực tiếp
./target/release/opus-production --port 8080
```

### Phương pháp 3: Triển khai Kubernetes

```bash
# Áp dụng các manifest Kubernetes
kubectl apply -f deployments/kubernetes/

# Kiểm tra pods
kubectl get pods -n opus-gpu

# Expose service
kubectl port-forward -n opus-gpu svc/opus-gpu 8080:8080
```

---

## ⚙️ CẤU HÌNH HỆ THỐNG

### File cấu hình chính (config.toml)

```toml
# Cấu hình khai thác
[mining]
pool_url = "stratum+tcp://your.pool.com:4444"
wallet_address = "YOUR_WALLET_ADDRESS"
worker_name = "opus-gpu-01"
algorithm = "ethash"  # ethash, kawpow, autolykos2
intensity = 8  # 1-10, càng cao càng tốn tài nguyên

# Quản lý nhiệt độ
[thermal]
max_temperature = 85.0  # Ngưỡng tối đa (°C)
target_temperature = 75.0  # Nhiệt độ mục tiêu
throttle_temperature = 80.0  # Bắt đầu giảm hiệu suất
check_interval_secs = 5  # Kiểm tra mỗi 5 giây

# Cấu hình GPU
[gpu]
devices = "all"  # "all" hoặc "0,1,2" cho GPU cụ thể
memory_percent = 85  # Phần trăm VRAM sử dụng
power_limit = 250  # Giới hạn công suất (Watts)
core_clock_offset = 100  # MHz
memory_clock_offset = 500  # MHz

# API Server
[api]
host = "0.0.0.0"
port = 8080
cors_enabled = true
auth_enabled = false  # Bật JWT authentication
jwt_secret = "your-secret-key"

# Prometheus Metrics
[metrics]
enabled = true
port = 9090
update_interval_secs = 10

# Logging
[logging]
level = "info"  # trace, debug, info, warn, error
file = "/var/log/opus-gpu/app.log"
max_size_mb = 100
max_backups = 5

# Bảo mật
[security]
tls_enabled = false
cert_file = "/path/to/cert.pem"
key_file = "/path/to/key.pem"
ip_whitelist = []  # ["192.168.1.0/24"]
rate_limit_per_minute = 60
```

### Biến môi trường

```bash
# File .env
RUST_LOG=info
RUST_BACKTRACE=1
CUDA_VISIBLE_DEVICES=0,1,2
POOL_URL=stratum+tcp://eth-us-east1.nanopool.org:9999
WALLET_ADDRESS=0xYourWalletAddress
WORKER_NAME=rig01
API_PORT=8080
METRICS_PORT=9090
```

---

## 🎮 MÔ TẢ CHỨC NĂNG CHÍNH

### 1. Mining Engine (Động cơ khai thác)

**Chức năng:** Thực hiện các thuật toán khai thác cryptocurrency trên GPU

**Các thành phần:**
- **Worker Pool**: Quản lý các luồng khai thác song song
- **Hash Calculator**: Tính toán hash với CUDA
- **Share Submitter**: Gửi kết quả về pool
- **Algorithm Manager**: Hỗ trợ nhiều thuật toán

**Tham số quan trọng:**
```rust
// Cấu hình trong code
MiningConfig {
    algorithm: "ethash",
    intensity: 8,
    worker_threads: 4,
    cuda_streams: 2,
}
```

### 2. Resource Manager (Quản lý tài nguyên)

**Chức năng:** Tối ưu hóa việc sử dụng GPU và hệ thống

**Tính năng:**
- Phân bổ VRAM động
- Cân bằng tải giữa các GPU
- Giám sát CPU và RAM
- Tự động điều chỉnh intensity

**Giám sát thời gian thực:**
```bash
# Xem thông tin tài nguyên
curl http://localhost:8080/stats | jq '.'
```

### 3. Thermal Control (Kiểm soát nhiệt độ)

**Chức năng:** Duy trì nhiệt độ GPU trong ngưỡng an toàn

**Chiến lược:**
1. **Monitoring**: Kiểm tra nhiệt độ mỗi 5 giây
2. **Throttling**: Giảm intensity khi quá nhiệt
3. **Emergency Stop**: Dừng khai thác nếu vượt ngưỡng
4. **Recovery**: Tự động khởi động lại khi nhiệt độ ổn định

**Ngưỡng nhiệt độ:**
```
< 70°C: Hoạt động bình thường
70-75°C: Cảnh báo
75-80°C: Giảm hiệu suất
80-85°C: Giảm mạnh
> 85°C: Dừng khẩn cấp
```

### 4. API Server

**Endpoints chính:**

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/` | GET | Thông tin service |
| `/health` | GET | Kiểm tra sức khỏe hệ thống |
| `/stats` | GET | Thống kê khai thác chi tiết |
| `/workers` | GET | Thông tin các worker |
| `/metrics` | GET | Prometheus metrics |
| `/control/start` | POST | Bắt đầu khai thác |
| `/control/stop` | POST | Dừng khai thác |
| `/control/restart` | POST | Khởi động lại |
| `/config` | GET/POST | Xem/cập nhật cấu hình |

### 5. Monitoring System (Hệ thống giám sát)

**Metrics được theo dõi:**
- Hashrate (MH/s)
- Shares (submitted/accepted/rejected)
- Temperature (°C)
- Power usage (Watts)
- Memory usage (MB)
- Fan speed (%)
- Revenue estimation

---

## 📖 HƯỚNG DẪN SỬ DỤNG THỰC TẾ

### Tình huống 1: Khởi động khai thác cơ bản

```bash
# 1. Kiểm tra GPU
nvidia-smi

# 2. Cấu hình pool và wallet
export POOL_URL="stratum+tcp://eth-us-east1.nanopool.org:9999"
export WALLET_ADDRESS="0xYourWalletAddress"

# 3. Khởi động
./scripts/start.sh

# 4. Kiểm tra trạng thái
curl http://localhost:8080/health
curl http://localhost:8080/stats
```

### Tình huống 2: Khai thác multi-GPU

```bash
# Cấu hình cho 3 GPU
cat > configs/multi-gpu.toml << EOF
[gpu]
devices = "0,1,2"
memory_percent = 90

[mining]
intensity = 9
worker_threads = 12  # 4 threads per GPU
EOF

# Khởi động với cấu hình custom
./target/release/opus-production --config configs/multi-gpu.toml
```

### Tình huống 3: Tối ưu cho hashrate cao

```bash
# 1. Overclock GPU
nvidia-smi -i 0 -pl 300  # Power limit 300W
nvidia-settings -a "[gpu:0]/GPUGraphicsClockOffset[3]=150"
nvidia-settings -a "[gpu:0]/GPUMemoryTransferRateOffset[3]=1000"

# 2. Cấu hình aggressive
cat > configs/aggressive.toml << EOF
[mining]
intensity = 10
algorithm = "ethash"

[gpu]
memory_percent = 95
power_limit = 300

[thermal]
max_temperature = 90.0
target_temperature = 80.0
EOF

# 3. Khởi động và monitor
./target/release/opus-production --config configs/aggressive.toml
watch -n 1 'curl -s http://localhost:8080/stats | jq .hashrate'
```

### Tình huống 4: Khai thác an toàn 24/7

```bash
# Script tự động khởi động lại
cat > auto-restart.sh << 'EOF'
#!/bin/bash
while true; do
    echo "Starting OPUS-GPU..."
    ./target/release/opus-production \
        --port 8080 \
        --config configs/safe-24-7.toml

    echo "Process exited. Restarting in 10 seconds..."
    sleep 10
done
EOF

chmod +x auto-restart.sh
nohup ./auto-restart.sh > mining.log 2>&1 &
```

### Tình huống 5: Tích hợp với monitoring

```yaml
# docker-compose với Grafana
version: '3.8'
services:
  opus-gpu:
    image: opus-gpu:2.0
    ports:
      - "8080:8080"
      - "9090:9090"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  prometheus:
    image: prom/prometheus
    ports:
      - "9091:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## 📊 GIÁM SÁT VÀ QUẢN LÝ

### Dashboard Grafana

1. **Cài đặt Grafana Dashboard:**
```bash
# Import dashboard
curl -X POST http://admin:admin@localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @monitoring/grafana-dashboard.json
```

2. **Metrics quan trọng cần theo dõi:**
- **Hashrate Trend**: Xu hướng hashrate theo thời gian
- **Temperature Heatmap**: Bản đồ nhiệt GPU
- **Share Success Rate**: Tỷ lệ share thành công
- **Revenue Projection**: Dự báo doanh thu

### Alerts và thông báo

```yaml
# Prometheus alert rules
groups:
  - name: opus-gpu
    rules:
      - alert: HighTemperature
        expr: gpu_temperature_celsius > 85
        for: 1m
        annotations:
          summary: "GPU temperature too high: {{ $value }}°C"

      - alert: LowHashrate
        expr: gpu_hashrate_mhs < 100
        for: 5m
        annotations:
          summary: "Hashrate dropped below 100 MH/s"

      - alert: HighRejectionRate
        expr: rate(mining_shares_rejected[5m]) > 0.05
        annotations:
          summary: "Share rejection rate > 5%"
```

### Log management

```bash
# Xem logs real-time
tail -f /var/log/opus-gpu/app.log

# Filter errors
grep ERROR /var/log/opus-gpu/app.log

# Rotate logs
logrotate -f /etc/logrotate.d/opus-gpu
```

---

## 🔧 XỬ LÝ SỰ CỐ THƯỜNG GẶP

### Sự cố 1: GPU không được nhận diện

**Triệu chứng:**
```
Error: No CUDA devices found
```

**Giải pháp:**
```bash
# 1. Kiểm tra driver
nvidia-smi
# Nếu lỗi, cài lại driver:
sudo apt purge nvidia-*
sudo apt install nvidia-driver-470

# 2. Kiểm tra CUDA
nvcc --version
# Nếu không có, cài CUDA Toolkit

# 3. Reset GPU
sudo nvidia-smi -r

# 4. Kiểm tra trong Docker
docker run --rm --gpus all nvidia/cuda:12.2.0-base nvidia-smi
```

### Sự cố 2: Hashrate thấp

**Triệu chứng:** Hashrate < 50% mức kỳ vọng

**Giải pháp:**
```bash
# 1. Kiểm tra thermal throttling
nvidia-smi -q -d PERFORMANCE

# 2. Tăng power limit
sudo nvidia-smi -pl 300

# 3. Điều chỉnh intensity
curl -X POST http://localhost:8080/config \
  -H "Content-Type: application/json" \
  -d '{"mining": {"intensity": 9}}'

# 4. Kiểm tra memory errors
nvidia-smi --query-gpu=memory.free,memory.used --format=csv
```

### Sự cố 3: Nhiệt độ cao

**Triệu chứng:** Temperature > 85°C

**Giải pháp:**
```bash
# 1. Giảm power limit
sudo nvidia-smi -pl 200

# 2. Tăng tốc độ quạt
nvidia-settings -a "[gpu:0]/GPUFanControlState=1"
nvidia-settings -a "[fan:0]/GPUTargetFanSpeed=80"

# 3. Giảm intensity
echo '[mining]
intensity = 6' > configs/cool.toml
./target/release/opus-production --config configs/cool.toml

# 4. Kiểm tra thông gió
# Đảm bảo khoảng cách giữa các GPU >= 2cm
# Nhiệt độ phòng < 25°C
```

### Sự cố 4: Connection pool bị mất

**Triệu chứng:**
```
Error: Pool connection timeout
```

**Giải pháp:**
```bash
# 1. Kiểm tra network
ping pool.server.com
traceroute pool.server.com

# 2. Thử pool backup
export POOL_URL="stratum+tcp://backup.pool.com:4444"

# 3. Restart với retry logic
./target/release/opus-production \
  --pool-retry-count 10 \
  --pool-retry-delay 30
```

### Sự cố 5: High share rejection

**Triệu chứng:** Rejection rate > 2%

**Giải pháp:**
```bash
# 1. Kiểm tra latency đến pool
ping -c 100 pool.server.com | grep avg

# 2. Giảm intensity
curl -X POST http://localhost:8080/config \
  -d '{"mining": {"intensity": 7}}'

# 3. Kiểm tra overclock settings
# Giảm memory clock nếu cần
nvidia-settings -a "[gpu:0]/GPUMemoryTransferRateOffset[3]=0"

# 4. Chuyển sang pool gần hơn
# Chọn pool có latency < 50ms
```

---

## ⚡ TỐI ƯU HIỆU SUẤT

### Tối ưu GPU

```bash
# 1. Profile hiệu suất hiện tại
nvidia-smi dmon -s pucvmet -c 10

# 2. Tìm điểm tối ưu
for INTENSITY in {6..10}; do
    echo "Testing intensity $INTENSITY"
    ./target/release/opus-production \
        --intensity $INTENSITY \
        --benchmark 60
done

# 3. Áp dụng overclock tối ưu
cat > overclock.sh << 'EOF'
#!/bin/bash
# RTX 3070 settings
nvidia-smi -pl 220  # Power limit
nvidia-settings -a "[gpu:0]/GPUGraphicsClockOffset[3]=-200"
nvidia-settings -a "[gpu:0]/GPUMemoryTransferRateOffset[3]=1200"
EOF
```

### Tối ưu hệ thống

```bash
# 1. Tắt GUI để tiết kiệm tài nguyên
sudo systemctl set-default multi-user.target

# 2. Tối ưu kernel parameters
cat >> /etc/sysctl.conf << EOF
vm.swappiness = 10
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
EOF

# 3. CPU Governor
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# 4. Huge pages
echo 128 | sudo tee /proc/sys/vm/nr_hugepages
```

### Tối ưu network

```bash
# 1. Sử dụng pool với stratum proxy
./target/release/opus-production \
  --stratum-proxy localhost:8888 \
  --pool-backup "stratum+tcp://backup.pool:4444"

# 2. Tối ưu MTU
sudo ip link set dev eth0 mtu 9000

# 3. TCP tuning
echo 'net.ipv4.tcp_congestion_control = bbr' | sudo tee -a /etc/sysctl.conf
```

---

## 📚 PHỤ LỤC

### A. Danh sách lệnh CLI

```bash
# Lệnh cơ bản
opus-production --help
opus-production --version
opus-production mine --pool <URL> --wallet <ADDRESS>

# Diagnostic
opus-production diagnose --thermal
opus-production diagnose --gpu-check
opus-production diagnose --network

# Benchmark
opus-production benchmark --duration 300
opus-production benchmark --algorithm ethash

# Configuration
opus-production config --show
opus-production config --validate
opus-production config --set mining.intensity=8
```

### B. Mã lỗi thông dụng

| Mã lỗi | Ý nghĩa | Giải pháp |
|--------|---------|-----------|
| E001 | GPU not found | Kiểm tra driver NVIDIA |
| E002 | CUDA initialization failed | Cài đặt CUDA Toolkit |
| E003 | Pool connection failed | Kiểm tra network/firewall |
| E004 | Temperature critical | Kiểm tra cooling system |
| E005 | Out of memory | Giảm intensity hoặc memory_percent |
| E006 | Invalid configuration | Kiểm tra file config.toml |
| E007 | Permission denied | Chạy với sudo hoặc fix permissions |

### C. Performance Benchmarks

| GPU Model | Algorithm | Hashrate | Power | Efficiency |
|-----------|-----------|----------|-------|------------|
| RTX 3090 | Ethash | 120 MH/s | 350W | 0.34 MH/W |
| RTX 3080 | Ethash | 100 MH/s | 320W | 0.31 MH/W |
| RTX 3070 | Ethash | 62 MH/s | 220W | 0.28 MH/W |
| RTX 3060 Ti | Ethash | 61 MH/s | 200W | 0.30 MH/W |

### D. Script templates

**Auto-switch algorithm:**
```bash
#!/bin/bash
# Auto-switch based on profitability

ALGOS=("ethash" "kawpow" "autolykos2")
BEST_ALGO=""
BEST_PROFIT=0

for ALGO in "${ALGOS[@]}"; do
    PROFIT=$(curl -s "https://whattomine.com/api/$ALGO" | jq .profit)
    if (( $(echo "$PROFIT > $BEST_PROFIT" | bc -l) )); then
        BEST_PROFIT=$PROFIT
        BEST_ALGO=$ALGO
    fi
done

echo "Switching to $BEST_ALGO (profit: $BEST_PROFIT)"
./target/release/opus-production --algorithm $BEST_ALGO
```

**Health check monitoring:**
```bash
#!/bin/bash
# Monitor and alert on issues

while true; do
    HEALTH=$(curl -s http://localhost:8080/health)
    if [[ $HEALTH != *"ok"* ]]; then
        echo "ALERT: System unhealthy!"
        # Send notification (email, telegram, etc)
        curl -X POST https://api.telegram.org/bot$TOKEN/sendMessage \
            -d "chat_id=$CHAT_ID&text=OPUS-GPU Alert: System unhealthy"
    fi
    sleep 60
done
```

### E. Troubleshooting Flowchart

```
Start
  │
  ├─> GPU Detected? ──No──> Check NVIDIA Driver
  │                          │
  │                          └─> Install/Update Driver
  │
  ├─> CUDA Working? ──No──> Install CUDA Toolkit
  │                          │
  │                          └─> Set CUDA_PATH
  │
  ├─> Config Valid? ──No──> Fix config.toml
  │                         │
  │                         └─> Validate syntax
  │
  ├─> Pool Connected? ──No──> Check firewall
  │                           │
  │                           ├─> Test network
  │                           └─> Try backup pool
  │
  ├─> Hashrate OK? ──No──> Check temperature
  │                        │
  │                        ├─> Adjust intensity
  │                        └─> Check overclock
  │
  └─> Mining Successfully
```

---

## 📞 HỖ TRỢ

### Kênh hỗ trợ chính thức

- **Documentation**: https://docs.opus-gpu.io
- **GitHub Issues**: https://github.com/opus-gpu/opus-gpu/issues
- **Discord**: https://discord.gg/opus-gpu
- **Email**: support@opus-gpu.io
- **Telegram**: @opusgpu_support

### FAQ (Câu hỏi thường gặp)

**Q: Có thể chạy trên Windows không?**
A: Hiện tại chỉ hỗ trợ Linux. Windows qua WSL2 có thể hoạt động nhưng hiệu suất thấp hơn.

**Q: Hỗ trợ AMD GPU không?**
A: Phiên bản hiện tại chỉ hỗ trợ NVIDIA. AMD support đang trong kế hoạch phát triển.

**Q: Làm sao để dual mine?**
A: Cấu hình `algorithm = "ethash+ton"` trong config.toml để khai thác 2 đồng cùng lúc.

**Q: Dev fee là bao nhiêu?**
A: 1% dev fee, có thể tắt bằng flag `--no-fee` nhưng sẽ mất support.

---

## 📝 GHI CHÚ PHIÊN BẢN

### v2.0.0 (Current)
- ✅ Complete Rust rewrite
- ✅ Microservices architecture
- ✅ Advanced thermal management
- ✅ Enterprise security features
- ✅ Distributed mining support

### Roadmap v2.1.0
- 🔄 AMD GPU support
- 🔄 Machine learning optimization
- 🔄 Mobile app monitoring
- 🔄 Cloud mining integration

---

**© 2024 OPUS-GPU Team. MIT License.**

*Tài liệu được cập nhật lần cuối: September 29, 2024*