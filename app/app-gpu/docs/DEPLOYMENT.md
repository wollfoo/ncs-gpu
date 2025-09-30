# 🚀 OPUS-GPU Deployment Guide

**Version**: 0.1.0-alpha
**Last Updated**: 2025-09-30

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Build Instructions](#build-instructions)
- [Configuration Guide](#configuration-guide)
- [Local Deployment](#local-deployment)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Systemd Deployment](#systemd-deployment)
- [Monitoring Setup](#monitoring-setup)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Hardware Minimum**:
- **CPU**: 4 cores (8+ recommended)
- **RAM**: 8GB (16GB+ recommended)
- **GPU**: NVIDIA GPU với CUDA capability ≥7.0
  - RTX 20xx, 30xx, 40xx series
  - Tesla T4, V100, A100
- **Storage**: 10GB free space
- **Network**: 10 Mbps upload (for pool connection)

**Operating System**:
- **Linux**: Ubuntu 20.04+, Debian 11+, RHEL 8+ (recommended)
- **Windows**: Windows 10/11 với WSL2
- **macOS**: macOS 12+ (limited GPU support)

### Software Dependencies

**Required**:

```bash
# 1. Rust Toolchain (1.70+)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# 2. NVIDIA CUDA Toolkit 12.x
# Download from: https://developer.nvidia.com/cuda-downloads

# Ubuntu/Debian
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt install -y cuda-toolkit-12-0

# 3. NVIDIA Driver (compatible version)
sudo apt install -y nvidia-driver-535

# Verify installation
nvidia-smi  # Should show GPU info
nvcc --version  # Should show CUDA 12.x
```

**Optional** (for DevOps tools):

```bash
# Go Toolchain (1.21+)
wget https://go.dev/dl/go1.23.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.23.0.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin
go version  # Should show go1.23.0

# Docker (for containerized deployment)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Kubernetes (for orchestration)
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

---

## Build Instructions

### Build Rust Core

```bash
cd /path/to/opus-gpu/app/app-gpu

# Development build (debug symbols, slower)
cargo build

# Production build (optimized, fast)
cargo build --release

# Output binary location
ls -lh target/release/gpu-miner
# -rwxr-xr-x 1 user user 2.8M Sep 30 10:00 gpu-miner
```

**Build Flags**:
```bash
# Enable CUDA support (requires CUDA toolkit)
cargo build --release --features cuda

# Enable all features
cargo build --release --all-features

# Custom optimization level
RUSTFLAGS="-C target-cpu=native" cargo build --release
```

### Build Go DevOps Tools

```bash
cd /path/to/opus-gpu/app/app-gpu/gpu-tools

# Build all tools
make build

# Or build individually
go build -o bin/gpu-ctl cmd/gpu-ctl/main.go
go build -o bin/gpu-watchdog cmd/gpu-watchdog/main.go
go build -o bin/metrics-aggregator cmd/metrics-aggregator/main.go

# Cross-compile for different platforms
GOOS=linux GOARCH=amd64 go build -o bin/gpu-ctl-linux cmd/gpu-ctl/main.go
GOOS=windows GOARCH=amd64 go build -o bin/gpu-ctl.exe cmd/gpu-ctl/main.go
```

### Build Verification

```bash
# Run tests
cargo test
cargo test --release

# Run linter
cargo clippy -- -D warnings

# Run benchmarks
cargo bench

# Check binary size
ls -lh target/release/gpu-miner

# Check dependencies
cargo tree
```

---

## Configuration Guide

### Configuration File Format

**Location**: `config/app.toml`

**Full Example**:
```toml
# GPU Configuration
[gpu]
devices = [0, 1]              # GPU IDs to use (0-indexed)
memory_limit_mb = 8192        # Optional VRAM limit per GPU
threads_per_block = 256       # CUDA kernel configuration
blocks_per_grid = 1024        # CUDA kernel configuration

# API Configuration
[api]
host = "0.0.0.0"              # Bind address (0.0.0.0 = all interfaces)
port = 8080                   # HTTP port
enable_cors = false           # CORS support (security risk)

# Mining Configuration
[mining]
pool_url = "stratum+tcp://pool.example.com:3333"
wallet_address = "0x1234567890abcdef1234567890abcdef12345678"
worker_name = "opus-gpu-worker-01"
algorithm = "ethash"          # ethash, kawpow, etc.

# Stealth Configuration
[stealth]
enabled = false               # Enable stealth features
plugins_dir = "/opt/opus-gpu/plugins"
obfuscate_process_name = false
throttle_cpu_percent = 80     # Max CPU usage (0-100)

# Metrics Configuration
[metrics]
enabled = true                # Enable Prometheus metrics
port = 9090                   # Metrics endpoint port
collect_interval_ms = 1000    # Metrics collection interval

# Logging Configuration
[logging]
level = "info"                # trace, debug, info, warn, error
format = "json"               # json, pretty
file = "/var/log/opus-gpu/gpu-miner.log"
max_size_mb = 100             # Log rotation size
max_backups = 5               # Number of old logs to keep
```

### Environment Variables

**Override Configuration**:
```bash
# Config file location
export CONFIG_PATH=/etc/opus-gpu/app.toml

# Logging level
export RUST_LOG=debug,opus_gpu=trace

# CUDA device selection
export CUDA_VISIBLE_DEVICES=0,1

# API settings
export API_HOST=127.0.0.1
export API_PORT=8080

# Mining settings
export POOL_URL=stratum+tcp://pool.example.com:3333
export WALLET_ADDRESS=0x1234567890abcdef
```

### Secrets Management

**⚠️ Security Warning**: Never commit secrets to version control!

**Recommended Approach** (Age encryption):

```bash
# 1. Install age encryption tool
cargo install age

# 2. Generate key pair
age-keygen -o /etc/opus-gpu/age-key.txt

# 3. Encrypt config file
age -e -i /etc/opus-gpu/age-key.txt -o config/app.toml.age config/app.toml

# 4. Decrypt at runtime
age -d -i /etc/opus-gpu/age-key.txt config/app.toml.age > /tmp/app.toml
CONFIG_PATH=/tmp/app.toml ./gpu-miner
rm /tmp/app.toml
```

**Alternative** (OS Keyring):
```bash
# Store wallet in system keyring
secret-tool store --label="OPUS-GPU Wallet" service opus-gpu username wallet
# Enter password when prompted

# Retrieve at runtime
WALLET=$(secret-tool lookup service opus-gpu username wallet)
```

---

## Local Deployment

### Quick Start

```bash
# 1. Build binary
cargo build --release

# 2. Create config
cat > config/app.toml <<EOF
[gpu]
devices = [0]

[api]
host = "127.0.0.1"
port = 8080

[mining]
pool_url = "stratum+tcp://pool.example.com:3333"
wallet_address = "YOUR_WALLET_ADDRESS"

[metrics]
enabled = true
port = 9090
EOF

# 3. Run miner
CONFIG_PATH=config/app.toml ./target/release/gpu-miner

# 4. Verify health (in another terminal)
curl http://localhost:8080/health
```

### Background Execution

```bash
# Using nohup
nohup ./target/release/gpu-miner > /var/log/opus-gpu/output.log 2>&1 &

# Using screen
screen -S opus-gpu
./target/release/gpu-miner
# Press Ctrl+A, D to detach

# Using tmux
tmux new -s opus-gpu
./target/release/gpu-miner
# Press Ctrl+B, D to detach
```

### Process Management

```bash
# Check if running
ps aux | grep gpu-miner

# Send graceful shutdown signal
pkill -SIGTERM gpu-miner

# Force kill (not recommended)
pkill -SIGKILL gpu-miner

# Monitor logs
tail -f /var/log/opus-gpu/gpu-miner.log
```

---

## Docker Deployment

### Dockerfile

**Production Dockerfile**:
```dockerfile
# Multi-stage build
FROM nvidia/cuda:12.0.0-devel-ubuntu22.04 AS builder

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy source
WORKDIR /build
COPY . .

# Build release binary
RUN cargo build --release --features cuda

# Runtime stage
FROM nvidia/cuda:12.0.0-runtime-ubuntu22.04

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 opus && \
    mkdir -p /var/log/opus-gpu && \
    chown -R opus:opus /var/log/opus-gpu

# Copy binary from builder
COPY --from=builder /build/target/release/gpu-miner /usr/local/bin/
COPY --from=builder /build/config/app.toml /etc/opus-gpu/

USER opus
WORKDIR /home/opus

# Expose ports
EXPOSE 8080 9090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run miner
CMD ["gpu-miner"]
```

### Docker Build & Run

```bash
# Build image
docker build -t opus-gpu:latest .

# Run container
docker run -d \
  --name opus-gpu-miner \
  --gpus all \
  -p 8080:8080 \
  -p 9090:9090 \
  -v /path/to/config:/etc/opus-gpu:ro \
  -v /var/log/opus-gpu:/var/log/opus-gpu \
  --restart unless-stopped \
  opus-gpu:latest

# View logs
docker logs -f opus-gpu-miner

# Execute commands inside container
docker exec -it opus-gpu-miner /bin/bash

# Stop container
docker stop opus-gpu-miner

# Remove container
docker rm opus-gpu-miner
```

### Docker Compose

**`docker-compose.yml`**:
```yaml
version: '3.8'

services:
  gpu-miner:
    image: opus-gpu:latest
    container_name: opus-gpu-miner
    restart: unless-stopped
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=0,1
      - CONFIG_PATH=/etc/opus-gpu/app.toml
      - RUST_LOG=info
    ports:
      - "8080:8080"
      - "9090:9090"
    volumes:
      - ./config:/etc/opus-gpu:ro
      - /var/log/opus-gpu:/var/log/opus-gpu
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  prometheus:
    image: prom/prometheus:latest
    container_name: opus-gpu-prometheus
    restart: unless-stopped
    ports:
      - "9091:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    container_name: opus-gpu-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  prometheus-data:
  grafana-data:
```

**Usage**:
```bash
docker-compose up -d
docker-compose logs -f gpu-miner
docker-compose down
```

---

## Kubernetes Deployment

### Kubernetes Manifests

**Namespace**:
```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: opus-gpu
```

**ConfigMap**:
```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: opus-gpu-config
  namespace: opus-gpu
data:
  app.toml: |
    [gpu]
    devices = [0]

    [api]
    host = "0.0.0.0"
    port = 8080

    [mining]
    pool_url = "stratum+tcp://pool.example.com:3333"
    wallet_address = "0x1234567890abcdef"

    [metrics]
    enabled = true
    port = 9090
```

**Secret** (wallet address):
```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: opus-gpu-secret
  namespace: opus-gpu
type: Opaque
stringData:
  wallet-address: "0x1234567890abcdef1234567890abcdef12345678"
```

**Deployment**:
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opus-gpu-miner
  namespace: opus-gpu
  labels:
    app: opus-gpu-miner
spec:
  replicas: 1  # One pod per GPU node
  selector:
    matchLabels:
      app: opus-gpu-miner
  template:
    metadata:
      labels:
        app: opus-gpu-miner
    spec:
      nodeSelector:
        gpu-type: nvidia
      containers:
      - name: gpu-miner
        image: opus-gpu:latest
        imagePullPolicy: IfNotPresent
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "2Gi"
            cpu: "2"
          limits:
            nvidia.com/gpu: 1
            memory: "4Gi"
            cpu: "4"
        ports:
        - containerPort: 8080
          name: api
          protocol: TCP
        - containerPort: 9090
          name: metrics
          protocol: TCP
        env:
        - name: CONFIG_PATH
          value: "/etc/opus-gpu/app.toml"
        - name: RUST_LOG
          value: "info"
        - name: WALLET_ADDRESS
          valueFrom:
            secretKeyRef:
              name: opus-gpu-secret
              key: wallet-address
        volumeMounts:
        - name: config
          mountPath: /etc/opus-gpu
          readOnly: true
        - name: logs
          mountPath: /var/log/opus-gpu
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: config
        configMap:
          name: opus-gpu-config
      - name: logs
        emptyDir: {}
```

**Service**:
```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: opus-gpu-miner
  namespace: opus-gpu
  labels:
    app: opus-gpu-miner
spec:
  type: ClusterIP
  ports:
  - port: 8080
    targetPort: 8080
    protocol: TCP
    name: api
  - port: 9090
    targetPort: 9090
    protocol: TCP
    name: metrics
  selector:
    app: opus-gpu-miner
```

**ServiceMonitor** (for Prometheus Operator):
```yaml
# servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: opus-gpu-miner
  namespace: opus-gpu
spec:
  selector:
    matchLabels:
      app: opus-gpu-miner
  endpoints:
  - port: metrics
    interval: 30s
```

### Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f namespace.yaml

# Create secrets (replace with actual values)
kubectl create secret generic opus-gpu-secret \
  --from-literal=wallet-address=YOUR_WALLET_ADDRESS \
  -n opus-gpu

# Deploy resources
kubectl apply -f configmap.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f servicemonitor.yaml  # If using Prometheus Operator

# Verify deployment
kubectl get pods -n opus-gpu
kubectl logs -f deployment/opus-gpu-miner -n opus-gpu

# Port-forward for local access
kubectl port-forward -n opus-gpu svc/opus-gpu-miner 8080:8080

# Scale deployment
kubectl scale deployment opus-gpu-miner --replicas=3 -n opus-gpu

# Delete resources
kubectl delete namespace opus-gpu
```

---

## Systemd Deployment

### Systemd Service Unit

**`/etc/systemd/system/opus-gpu.service`**:
```ini
[Unit]
Description=OPUS-GPU Cryptocurrency Miner
Documentation=https://github.com/your-org/opus-gpu
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=opus
Group=opus
WorkingDirectory=/opt/opus-gpu
Environment="CONFIG_PATH=/etc/opus-gpu/app.toml"
Environment="RUST_LOG=info"
ExecStart=/opt/opus-gpu/bin/gpu-miner
ExecReload=/bin/kill -SIGHUP $MAINPID
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=opus-gpu

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/opus-gpu
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
```

### Systemd Setup

```bash
# 1. Create user
sudo useradd -r -s /bin/false -d /opt/opus-gpu opus

# 2. Install binary
sudo mkdir -p /opt/opus-gpu/bin
sudo cp target/release/gpu-miner /opt/opus-gpu/bin/
sudo chown -R opus:opus /opt/opus-gpu

# 3. Install config
sudo mkdir -p /etc/opus-gpu
sudo cp config/app.toml /etc/opus-gpu/
sudo chmod 600 /etc/opus-gpu/app.toml
sudo chown opus:opus /etc/opus-gpu/app.toml

# 4. Create log directory
sudo mkdir -p /var/log/opus-gpu
sudo chown opus:opus /var/log/opus-gpu

# 5. Install service file
sudo cp opus-gpu.service /etc/systemd/system/
sudo systemctl daemon-reload

# 6. Enable and start service
sudo systemctl enable opus-gpu
sudo systemctl start opus-gpu

# 7. Check status
sudo systemctl status opus-gpu

# 8. View logs
sudo journalctl -u opus-gpu -f
```

### Systemd Management

```bash
# Start service
sudo systemctl start opus-gpu

# Stop service
sudo systemctl stop opus-gpu

# Restart service
sudo systemctl restart opus-gpu

# Reload config (SIGHUP)
sudo systemctl reload opus-gpu

# Enable autostart
sudo systemctl enable opus-gpu

# Disable autostart
sudo systemctl disable opus-gpu

# View logs
sudo journalctl -u opus-gpu --since today
sudo journalctl -u opus-gpu -n 100 -f

# Check resource usage
systemctl show opus-gpu --property=MemoryCurrent
systemctl show opus-gpu --property=CPUUsageNSec
```

---

## Monitoring Setup

### Prometheus Configuration

**`prometheus.yml`**:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'opus-gpu-miner'
    static_configs:
      - targets: ['localhost:9090']
        labels:
          instance: 'miner-01'
          environment: 'production'

    # If using service discovery
    # kubernetes_sd_configs:
    #   - role: service
    #     namespaces:
    #       names: ['opus-gpu']
    # relabel_configs:
    #   - source_labels: [__meta_kubernetes_service_name]
    #     regex: opus-gpu-miner
    #     action: keep

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
```

### Grafana Dashboard

**Import Dashboard**:
```json
{
  "dashboard": {
    "title": "OPUS-GPU Mining Dashboard",
    "panels": [
      {
        "title": "Total Hashrate",
        "targets": [
          {
            "expr": "sum(opus_miner_hashrate_mhs)"
          }
        ],
        "type": "graph"
      },
      {
        "title": "GPU Temperatures",
        "targets": [
          {
            "expr": "opus_miner_gpu_temperature_celsius",
            "legendFormat": "GPU {{gpu_id}}"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Accepted Shares",
        "targets": [
          {
            "expr": "rate(opus_miner_shares_accepted_total[5m])"
          }
        ],
        "type": "stat"
      }
    ]
  }
}
```

**Access Grafana**:
```bash
# Default credentials
URL: http://localhost:3000
Username: admin
Password: admin

# Add Prometheus datasource
# Configuration > Data Sources > Add data source > Prometheus
# URL: http://prometheus:9090 (or http://localhost:9091 if local)
```

---

## Troubleshooting

### Common Issues

**1. Binary won't start**:
```bash
# Check dependencies
ldd target/release/gpu-miner

# Check CUDA driver
nvidia-smi

# Check config file
cat config/app.toml

# Run with debug logging
RUST_LOG=debug ./target/release/gpu-miner
```

**2. GPU not detected**:
```bash
# Verify CUDA installation
nvcc --version
nvidia-smi

# Check CUDA_VISIBLE_DEVICES
echo $CUDA_VISIBLE_DEVICES

# Test CUDA runtime
cargo run --example cuda_test  # If example exists
```

**3. High CPU usage**:
```bash
# Check for logging overhead
RUST_LOG=warn ./target/release/gpu-miner

# Profile CPU usage
perf record -F 99 -p $(pgrep gpu-miner) -- sleep 30
perf report
```

**4. Memory leak**:
```bash
# Monitor memory usage
watch -n 1 'ps aux | grep gpu-miner'

# Use valgrind (debug build only)
cargo build
valgrind --leak-check=full target/debug/gpu-miner
```

**5. Permission denied**:
```bash
# Check binary permissions
chmod +x target/release/gpu-miner

# Check config file permissions
chmod 600 config/app.toml

# Check NVIDIA device permissions
ls -l /dev/nvidia*
sudo usermod -aG video $USER
```

### Logging & Debugging

**Enable Debug Logging**:
```bash
# Set environment variable
export RUST_LOG=trace,opus_gpu=debug

# Run with verbose output
./target/release/gpu-miner 2>&1 | tee debug.log
```

**Analyze Crash Dumps**:
```bash
# Enable core dumps
ulimit -c unlimited

# If crashed, analyze core dump
gdb target/release/gpu-miner core
# Inside gdb:
(gdb) backtrace
(gdb) info threads
```

**Network Debugging**:
```bash
# Monitor network connections
ss -tunap | grep gpu-miner

# Trace system calls
strace -p $(pgrep gpu-miner)

# Capture network traffic
sudo tcpdump -i any -w capture.pcap port 8080 or port 3333
```

---

**Document Version**: 1.0
**Authors**: OPUS-GPU Team
**License**: MIT
