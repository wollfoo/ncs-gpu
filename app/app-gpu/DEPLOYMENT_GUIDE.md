# Agent-GPU Deployment Guide

🚀 **Production Deployment Guide** cho **Agent-GPU v2.0** - High-performance GPU mining platform với modular monolith architecture

## 📋 Tổng quan

Hướng dẫn này cung cấp quy trình triển khai production đầy đủ cho **Agent-GPU**, bao gồm yêu cầu phần cứng, cài đặt phần mềm, cấu hình bảo mật và monitoring.

## 🔧 Yêu cầu hệ thống

### Hardware Requirements (Yêu cầu phần cứng)

#### **Minimum Requirements** (Yêu cầu tối thiểu)
```yaml
gpu:
  nvidia: "GTX 1060 6GB hoặc tương đương"
  amd: "RX 580 8GB hoặc tương đương"
  cuda_compute: "6.0+"
  opencl: "2.0+"

cpu:
  cores: "4 cores"
  frequency: "2.4 GHz"
  architecture: "x86_64"

memory:
  ram: "8 GB"
  swap: "4 GB"
  gpu_memory: "6 GB+"

storage:
  type: "SSD (khuyến nghị)"
  space: "50 GB khả dụng"
  iops: "1000+ IOPS"

network:
  bandwidth: "10 Mbps"
  latency: "<100ms to mining pools"
```

#### **Recommended Production** (Khuyến nghị production)
```yaml
gpu:
  nvidia: "RTX 4080/4090 hoặc A100"
  amd: "RX 7900 XTX"
  quantity: "2-8 GPUs"
  total_memory: "24-80 GB"

cpu:
  cores: "16+ cores"
  frequency: "3.2+ GHz"
  model: "Intel i7/i9, AMD Ryzen 7/9"

memory:
  ram: "32-64 GB"
  type: "DDR4-3200+ hoặc DDR5"
  ecc: "Khuyến nghị cho production"

storage:
  primary: "1 TB NVMe SSD"
  backup: "2 TB HDD"
  raid: "RAID 1 cho redundancy"

network:
  bandwidth: "100+ Mbps"
  redundancy: "Dual internet connections"
```

#### **Enterprise Scale** (Quy mô doanh nghiệp)
```yaml
infrastructure:
  servers: "Multiple dedicated mining rigs"
  gpus_per_server: "8-12 high-end GPUs"
  power_supply: "2000W+ 80+ Platinum"
  cooling: "Liquid cooling hoặc datacenter AC"
  monitoring: "24/7 infrastructure monitoring"

redundancy:
  power: "UPS backup + generator"
  network: "Multiple ISP connections"
  hardware: "Hot-swap components"
```

### Software Prerequisites (Yêu cầu phần mềm)

#### **Operating System Support**
```bash
# Linux (Khuyến nghị)
Ubuntu 22.04 LTS
Ubuntu 20.04 LTS
CentOS 8/9
RHEL 8/9
Debian 11/12

# Windows (Testing only)
Windows 10 Professional
Windows Server 2019/2022

# macOS (Development only)
macOS 12+ (M1/M2 limited support)
```

#### **GPU Drivers & Runtime**
```bash
# NVIDIA CUDA Setup
CUDA Toolkit: 12.2+
NVIDIA Driver: 525+
cuDNN: 8.8+
NCCL: 2.15+ (cho multi-GPU)

# AMD OpenCL Setup
AMD GPU Driver: 22.40+
ROCm: 5.4+ (cho Linux)
OpenCL SDK: 2.0+

# Vulkan Support
Vulkan SDK: 1.3+
VulkanRT: Latest
```

#### **Container Runtime**
```bash
# Docker Setup (Khuyến nghị)
Docker Engine: 20.10+
NVIDIA Container Toolkit: 1.14+
Docker Compose: 2.20+

# Podman Alternative
Podman: 4.0+
Podman-compose: 1.0+

# Kubernetes (Enterprise)
Kubernetes: 1.28+
NVIDIA GPU Operator: 23.6+
```

## 🚀 Installation Methods

### Method 1: Docker Deployment (Khuyến nghị)

#### **Single GPU Setup**
```bash
# 1. Pull latest image
docker pull agent-gpu:latest

# 2. Create configuration
mkdir -p /opt/agent-gpu/{config,data,logs}

# 3. Deploy with GPU support
docker run -d \
  --name agent-gpu-miner \
  --runtime=nvidia \
  --gpus all \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 8081:8081 \
  -p 8082:8082 \
  -p 9090:9090 \
  -v /opt/agent-gpu/config:/app/config \
  -v /opt/agent-gpu/data:/app/data \
  -v /opt/agent-gpu/logs:/app/logs \
  -e OPUS_GPU_POOL_URL="stratum+tcp://pool.example.com:4444" \
  -e OPUS_GPU_WALLET_ADDRESS="your_wallet_address" \
  -e OPUS_GPU_WORKER_NAME="miner01" \
  agent-gpu:latest
```

#### **Multi-GPU Production Setup**
```bash
# 1. Create production configuration
cat > /opt/agent-gpu/config/production.toml << EOF
[mining]
algorithm = "SHA256"
max_workers = 8
gpu_devices = [0, 1, 2, 3]
worker_threads = 2
batch_size = 2000
memory_size = 1073741824  # 1GB

[pool]
urls = [
  "stratum+tcp://primary-pool.example.com:4444",
  "stratum+tcp://backup-pool.example.com:4444"
]
username = "your_wallet_address"
password = "miner01"
retry_attempts = 5
keepalive_interval_secs = 30

[monitoring]
enabled = true
metrics_port = 9090
temperature_threshold = 75.0
memory_threshold = 85.0
enable_alerts = true

[api.rest]
host = "0.0.0.0"
port = 8080
rate_limit = 200
EOF

# 2. Deploy with production config
docker run -d \
  --name agent-gpu-production \
  --runtime=nvidia \
  --gpus all \
  --restart unless-stopped \
  --memory=16g \
  --cpus=8 \
  -p 8080:8080 \
  -p 8081:8081 \
  -p 8082:8082 \
  -p 9090:9090 \
  -v /opt/agent-gpu/config:/app/config \
  -v /opt/agent-gpu/data:/app/data \
  -v /opt/agent-gpu/logs:/app/logs \
  --log-driver=json-file \
  --log-opt max-size=100m \
  --log-opt max-file=3 \
  agent-gpu:latest \
  --config config/production.toml
```

#### **Docker Compose Deployment**
```yaml
# docker-compose.production.yml
version: '3.8'

services:
  agent-gpu:
    image: agent-gpu:latest
    container_name: agent-gpu-miner
    restart: unless-stopped
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - OPUS_GPU_LOG_LEVEL=info
      - OPUS_GPU_CONFIG_PATH=/app/config/production.toml
    ports:
      - "8080:8080"   # REST API
      - "8081:8081"   # WebSocket
      - "8082:8082"   # gRPC
      - "9090:9090"   # Metrics
    volumes:
      - ./config:/app/config:ro
      - ./data:/app/data
      - ./logs:/app/logs
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9091:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana

volumes:
  grafana-storage:
```

### Method 2: Native Binary Installation

#### **Build from Source**
```bash
# 1. Install Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
rustup toolchain install 1.75.0
rustup default 1.75.0

# 2. Install system dependencies
# Ubuntu/Debian
sudo apt update && sudo apt install -y \
  build-essential pkg-config libssl-dev \
  libsqlite3-dev cmake clang llvm-dev \
  ocl-icd-opencl-dev opencl-headers

# CentOS/RHEL
sudo dnf groupinstall "Development Tools"
sudo dnf install -y openssl-devel sqlite-devel \
  cmake clang llvm-devel opencl-headers

# 3. Clone và build
git clone https://github.com/agent-gpu/agent-gpu.git
cd agent-gpu/app/app-gpu
cargo build --release --features "cuda,opencl,security"

# 4. Install binary
sudo cp target/release/agent-gpu /usr/local/bin/
sudo chmod +x /usr/local/bin/agent-gpu

# 5. Create service user
sudo useradd --system --shell /bin/false agent-gpu
sudo mkdir -p /opt/agent-gpu/{config,data,logs}
sudo chown -R agent-gpu:agent-gpu /opt/agent-gpu
```

#### **Pre-compiled Binary**
```bash
# 1. Download latest release
wget https://github.com/agent-gpu/agent-gpu/releases/download/v2.0.0/agent-gpu-linux-x86_64.tar.gz

# 2. Extract và install
tar -xzf agent-gpu-linux-x86_64.tar.gz
sudo cp agent-gpu /usr/local/bin/
sudo chmod +x /usr/local/bin/agent-gpu

# 3. Verify installation
agent-gpu --version
```

### Method 3: Kubernetes Deployment

#### **Kubernetes Manifest**
```yaml
# agent-gpu-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-gpu-miner
  labels:
    app: agent-gpu
spec:
  replicas: 1
  selector:
    matchLabels:
      app: agent-gpu
  template:
    metadata:
      labels:
        app: agent-gpu
    spec:
      containers:
      - name: agent-gpu
        image: agent-gpu:latest
        resources:
          limits:
            nvidia.com/gpu: 4
            memory: "16Gi"
            cpu: "8"
          requests:
            nvidia.com/gpu: 4
            memory: "8Gi"
            cpu: "4"
        ports:
        - containerPort: 8080
          name: rest-api
        - containerPort: 8081
          name: websocket
        - containerPort: 8082
          name: grpc
        - containerPort: 9090
          name: metrics
        env:
        - name: OPUS_GPU_CONFIG_PATH
          value: "/app/config/production.toml"
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: data
          mountPath: /app/data
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: config
        configMap:
          name: agent-gpu-config
      - name: data
        persistentVolumeClaim:
          claimName: agent-gpu-data

---
apiVersion: v1
kind: Service
metadata:
  name: agent-gpu-service
spec:
  selector:
    app: agent-gpu
  ports:
  - name: rest-api
    port: 8080
    targetPort: 8080
  - name: websocket
    port: 8081
    targetPort: 8081
  - name: grpc
    port: 8082
    targetPort: 8082
  - name: metrics
    port: 9090
    targetPort: 9090
  type: LoadBalancer
```

## ⚙️ Configuration Templates

### Production Configuration
```toml
# /opt/agent-gpu/config/production.toml
[mining]
algorithm = "SHA256"
max_workers = 8
difficulty = 10000000
work_timeout_secs = 45
stats_interval_secs = 5
gpu_devices = [0, 1, 2, 3]
worker_threads = 2
batch_size = 2000
memory_size = 2147483648  # 2GB

[pool]
urls = [
  "stratum+tcp://primary-pool.com:4444",
  "stratum+tcp://backup-pool.com:4444",
  "stratum+tcp://failover-pool.com:4444"
]
username = "your_production_wallet"
password = "production-worker-01"
retry_attempts = 5
retry_delay_secs = 10
connection_timeout_secs = 15
keepalive_interval_secs = 30

[wallet]
keystore_dir = "/opt/agent-gpu/secure/keystore"
backup_dir = "/opt/agent-gpu/backup"
encryption_enabled = true

[monitoring]
enabled = true
metrics_port = 9090
stats_interval_secs = 5
temperature_threshold = 75.0
memory_threshold = 85.0
enable_alerts = true
alert_webhook_url = "https://hooks.slack.com/your-webhook"

[storage]
data_dir = "/opt/agent-gpu/data"
database_url = "postgres://opus:password@localhost:5432/opus_gpu"
max_connections = 20
backup_enabled = true
backup_interval_hours = 6
retention_days = 90

[api.rest]
host = "0.0.0.0"
port = 8080
cors_enabled = true
cors_origins = ["https://your-dashboard.com"]
rate_limit = 200
request_timeout_secs = 30

[api.websocket]
host = "0.0.0.0"
port = 8081
max_connections = 2000
message_buffer_size = 2000
heartbeat_interval_secs = 30

[api.grpc]
host = "0.0.0.0"
port = 8082
max_message_size = 8388608  # 8MB
keepalive_interval_secs = 30
keepalive_timeout_secs = 5

[plugins]
disabled = false
plugin_dir = "/opt/agent-gpu/plugins"
max_plugins = 100
load_timeout_secs = 60
whitelist = ["trusted-plugin", "monitoring-plugin"]
blacklist = []

[bus]
buffer_size = 2000
max_subscribers = 200
message_timeout_secs = 10
enable_persistence = true
persistence_file = "/opt/agent-gpu/data/bus_state.json"
```

## 🔒 Security Configuration

### SSL/TLS Setup
```bash
# 1. Generate SSL certificates
sudo mkdir -p /opt/agent-gpu/ssl
cd /opt/agent-gpu/ssl

# Self-signed certificate (development)
sudo openssl req -x509 -newkey rsa:4096 -keyout private.key -out certificate.crt -days 365 -nodes

# Let's Encrypt (production)
sudo apt install certbot
sudo certbot certonly --standalone -d your-mining-domain.com
sudo cp /etc/letsencrypt/live/your-mining-domain.com/fullchain.pem /opt/agent-gpu/ssl/
sudo cp /etc/letsencrypt/live/your-mining-domain.com/privkey.pem /opt/agent-gpu/ssl/
```

### Authentication Setup
```toml
# Add to production.toml
[security]
enable_auth = true
jwt_secret = "your-super-secret-jwt-key"
token_expiry_hours = 24
max_login_attempts = 5
lockout_duration_minutes = 15

[api.rest]
require_auth = true
tls_enabled = true
tls_cert_file = "/opt/agent-gpu/ssl/certificate.crt"
tls_key_file = "/opt/agent-gpu/ssl/private.key"

[api.websocket]
require_auth = true
tls_enabled = true
tls_cert_file = "/opt/agent-gpu/ssl/certificate.crt"
tls_key_file = "/opt/agent-gpu/ssl/private.key"
```

### Firewall Configuration
```bash
# UFW Setup (Ubuntu)
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH
sudo ufw allow ssh

# Allow Agent-GPU ports
sudo ufw allow 8080/tcp  # REST API
sudo ufw allow 8081/tcp  # WebSocket
sudo ufw allow 8082/tcp  # gRPC
sudo ufw allow 9090/tcp  # Metrics

# Allow mining pool connections
sudo ufw allow out 4444/tcp  # Stratum

# iptables setup (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --permanent --add-port=8081/tcp
sudo firewall-cmd --permanent --add-port=8082/tcp
sudo firewall-cmd --permanent --add-port=9090/tcp
sudo firewall-cmd --reload
```

## 📊 Monitoring & Alerting Setup

### Prometheus Configuration
```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'agent-gpu'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 5s
    metrics_path: '/metrics'

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']
```

### Alert Rules
```yaml
# monitoring/alert_rules.yml
groups:
  - name: agent-gpu-alerts
    rules:
      - alert: HighGPUTemperature
        expr: opus_gpu_temperature > 80
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "GPU temperature is high"
          description: "GPU temperature is {{ $value }}°C"

      - alert: LowHashrate
        expr: opus_gpu_hashrate < 1000000
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Hashrate is low"
          description: "Current hashrate: {{ $value }}"

      - alert: MiningPoolDisconnected
        expr: opus_gpu_pool_connected == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Mining pool disconnected"
```

### Grafana Dashboard
```json
{
  "dashboard": {
    "title": "Agent-GPU Monitoring",
    "panels": [
      {
        "title": "Hashrate",
        "type": "graph",
        "targets": [
          {
            "expr": "opus_gpu_hashrate",
            "legendFormat": "Hashrate"
          }
        ]
      },
      {
        "title": "GPU Temperature",
        "type": "graph",
        "targets": [
          {
            "expr": "opus_gpu_temperature",
            "legendFormat": "GPU {{device}}"
          }
        ]
      },
      {
        "title": "Power Consumption",
        "type": "graph",
        "targets": [
          {
            "expr": "opus_gpu_power_usage",
            "legendFormat": "Power (W)"
          }
        ]
      }
    ]
  }
}
```

## 💾 Backup & Disaster Recovery

### Automated Backup Script
```bash
#!/bin/bash
# /opt/agent-gpu/scripts/backup.sh

BACKUP_DIR="/opt/agent-gpu/backups"
DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="agent-gpu-backup-${DATE}.tar.gz"

# Create backup directory
mkdir -p ${BACKUP_DIR}

# Stop mining temporarily
docker stop agent-gpu-miner

# Backup configuration và data
tar -czf ${BACKUP_DIR}/${BACKUP_FILE} \
  /opt/agent-gpu/config \
  /opt/agent-gpu/data \
  /opt/agent-gpu/ssl

# Backup database
pg_dump opus_gpu > ${BACKUP_DIR}/database-${DATE}.sql

# Restart mining
docker start agent-gpu-miner

# Clean old backups (keep 30 days)
find ${BACKUP_DIR} -name "agent-gpu-backup-*.tar.gz" -mtime +30 -delete
find ${BACKUP_DIR} -name "database-*.sql" -mtime +30 -delete

# Upload to cloud storage (optional)
# aws s3 cp ${BACKUP_DIR}/${BACKUP_FILE} s3://your-backup-bucket/
```

### Disaster Recovery Plan
```bash
# 1. Emergency shutdown procedure
docker stop agent-gpu-miner
systemctl stop agent-gpu

# 2. Restore from backup
cd /opt/agent-gpu
tar -xzf backups/agent-gpu-backup-YYYYMMDD_HHMMSS.tar.gz

# 3. Restore database
psql opus_gpu < backups/database-YYYYMMDD_HHMMSS.sql

# 4. Verify configuration
agent-gpu --config config/production.toml --validate

# 5. Restart services
docker start agent-gpu-miner
systemctl start agent-gpu
```

## ⚡ Performance Tuning

### System Optimization
```bash
# CPU Governor
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Memory optimization
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
echo 'vm.dirty_ratio=15' | sudo tee -a /etc/sysctl.conf
echo 'vm.dirty_background_ratio=5' | sudo tee -a /etc/sysctl.conf

# Network optimization
echo 'net.core.rmem_max = 16777216' | sudo tee -a /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' | sudo tee -a /etc/sysctl.conf
echo 'net.ipv4.tcp_rmem = 4096 65536 16777216' | sudo tee -a /etc/sysctl.conf

# Apply changes
sudo sysctl -p

# Increase file descriptor limits
echo 'agent-gpu soft nofile 65536' | sudo tee -a /etc/security/limits.conf
echo 'agent-gpu hard nofile 65536' | sudo tee -a /etc/security/limits.conf
```

### GPU Optimization
```bash
# NVIDIA settings
sudo nvidia-smi -pm 1  # Enable persistence mode
sudo nvidia-smi -ac 877,1911  # Set memory và core clocks

# Power limit optimization
sudo nvidia-smi -pl 350  # Set power limit to 350W

# Fan speed control
sudo nvidia-settings -a '[gpu:0]/GPUFanControlState=1'
sudo nvidia-settings -a '[fan:0]/GPUTargetFanSpeed=75'
```

### Database Optimization
```sql
-- PostgreSQL performance tuning
-- /etc/postgresql/14/main/postgresql.conf

shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 1GB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
```

## 🐛 Troubleshooting Guide

### Common Issues

#### **GPU Not Detected**
```bash
# Check NVIDIA drivers
nvidia-smi
nvcc --version

# Check CUDA installation
cat /usr/local/cuda/version.txt

# Verify OpenCL
clinfo

# Check permissions
ls -la /dev/nvidia*
```

#### **High Memory Usage**
```toml
# Reduce memory allocation
[mining]
memory_size = 268435456  # 256MB instead of 1GB
batch_size = 500         # Smaller batches
worker_threads = 1       # Reduce threads
```

#### **Connection Issues**
```bash
# Test pool connectivity
telnet pool.example.com 4444

# Check firewall
sudo ufw status
sudo iptables -L

# Verify DNS resolution
nslookup pool.example.com
```

#### **Performance Issues**
```bash
# Check GPU utilization
nvidia-smi -l 1

# Monitor system resources
htop
iotop

# Check thermal throttling
sudo nvidia-smi -q -d TEMPERATURE
```

### Log Analysis
```bash
# Container logs
docker logs agent-gpu-miner --tail 100 -f

# System logs
journalctl -u agent-gpu -f

# Application logs
tail -f /opt/agent-gpu/logs/agent-gpu.log

# GPU logs
sudo dmesg | grep -i nvidia
```

### Health Checks
```bash
# API health check
curl http://localhost:8080/health

# Mining status
curl http://localhost:8080/api/v1/mining/stats

# System metrics
curl http://localhost:9090/metrics
```

## 🔄 Maintenance Procedures

### Regular Maintenance
```bash
# Weekly tasks
- Monitor GPU temperatures và performance
- Check disk space usage
- Review error logs
- Verify backup integrity
- Update mining pool lists

# Monthly tasks
- Update Agent-GPU to latest version
- Clean log files
- Optimize database
- Security audit
- Performance benchmarking

# Quarterly tasks
- Driver updates
- Hardware cleaning
- Capacity planning
- Disaster recovery testing
```

### Update Procedure
```bash
# 1. Backup current installation
/opt/agent-gpu/scripts/backup.sh

# 2. Stop mining
docker stop agent-gpu-miner

# 3. Pull new image
docker pull agent-gpu:latest

# 4. Verify configuration compatibility
agent-gpu --config config/production.toml --validate

# 5. Deploy update
docker-compose up -d

# 6. Verify operation
curl http://localhost:8080/health
```

## 📞 Support & Resources

### **Emergency Contacts**
- **Technical Support**: support@agent-gpu.com
- **Security Issues**: security@agent-gpu.com
- **Business Critical**: +1-XXX-XXX-XXXX

### **Documentation**
- **API Reference**: [API_REFERENCE.md](API_REFERENCE.md)
- **Architecture Guide**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Quick Start**: [QUICKSTART.md](QUICKSTART.md)

### **Community**
- **GitHub Issues**: https://github.com/agent-gpu/agent-gpu/issues
- **Discord Server**: https://discord.gg/agent-gpu
- **Telegram Group**: https://t.me/opus_gpu

---

**Made with ❤️ by Agent-GPU Team** | **Production-Ready Since 2024**