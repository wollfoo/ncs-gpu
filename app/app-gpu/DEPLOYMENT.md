# OPUS-GPU Production Deployment Package

**Complete deployment solution** cho OPUS-GPU high-performance cryptocurrency miner với Docker, Kubernetes, và Systemd support.

## 📦 Package Contents

### Core Files

#### 1. **Multi-Stage Dockerfile** (`Dockerfile`)
- **Builder Stage 1**: Rust compiler (gpu-miner binary)
- **Builder Stage 2**: Go compiler (gpu-ctl, gpu-watchdog, gpu-monitor tools)
- **Runtime Stage**: NVIDIA CUDA 12.0 runtime with non-root user
- **Image Size**: Optimized multi-stage build (~500MB final image)
- **Security**: Non-root execution, minimal attack surface

#### 2. **Docker Compose Stack** (`gpu-tools/deploy/docker/`)
```
docker/
├── docker-compose.yml    # Complete stack definition
└── prometheus.yml        # Metrics scraping configuration
```

**Services**:
- `miner` - Main GPU miner with NVIDIA runtime
- `prometheus` - Metrics collection server
- `grafana` - Monitoring dashboard (port 3000)
- `influxdb` - Optional time-series storage
- `gpu-watchdog` - GPU health monitoring service

#### 3. **Kubernetes Manifests** (`gpu-tools/deploy/k8s/`)
```
k8s/
├── namespace.yaml        # opus-gpu namespace
├── deployment.yaml       # GPU-enabled deployment with 2 GPUs
├── service.yaml          # ClusterIP, Headless, NodePort services
├── configmap.yaml        # Application configuration
└── secret.yaml           # Sensitive data template
```

**Features**:
- GPU resource requests: `nvidia.com/gpu: 2`
- Node selectors for GPU nodes
- Liveness/Readiness/Startup probes
- Prometheus annotations for auto-discovery
- SecurityContext with non-root user
- PersistentVolumeClaim for data storage

#### 4. **Systemd Services** (`gpu-tools/deploy/systemd/`)
```
systemd/
├── opus-gpu.service          # Main miner service
└── opus-gpu-watchdog.service # Watchdog service
```

**Security Features**:
- NoNewPrivileges, ProtectSystem, ProtectHome
- Restricted syscalls and capabilities
- GPU device access controls
- Resource limits (Memory, CPU)

#### 5. **Automation Scripts** (`gpu-tools/deploy/scripts/`)
```bash
scripts/
├── build.sh    # Build Rust binary + Go tools + Docker image
└── deploy.sh   # Deploy to docker/k8s/systemd
```

**Build Script Features**:
- Dependency checking
- Multi-language builds (Rust + Go)
- Automated testing (optional)
- Docker image building
- Build summary report

**Deploy Script Features**:
- Target selection (docker/k8s/systemd)
- Pre-flight validation
- Automated deployment
- Post-deployment verification
- Helpful command suggestions

#### 6. **Monitoring** (`gpu-tools/deploy/grafana/`)
```
grafana/
└── dashboard.json    # Pre-configured dashboard
```

**Dashboard Panels**:
- GPU Hashrate (MH/s) - Real-time performance
- GPU Temperature - Thermal monitoring with thresholds
- GPU Power Usage - Power consumption tracking
- GPU Utilization - Resource usage percentage
- GPU Memory - Memory allocation and usage
- Service Status - Uptime and health
- Mining Shares - Accepted/Rejected counters

### Supporting Files

- **`.dockerignore`** - Optimized Docker build context
- **`README.md`** - Comprehensive deployment guide
- **`DEPLOYMENT_CHECKLIST.md`** - Production checklist

## 🚀 Quick Start

### Option 1: Docker Compose (Fastest)

```bash
# 1. Build
cd /home/azureuser/opus-gpu/app/app-gpu
./gpu-tools/deploy/scripts/build.sh

# 2. Deploy
./gpu-tools/deploy/scripts/deploy.sh docker

# 3. Access
# - Miner API: http://localhost:8080
# - Prometheus: http://localhost:9091
# - Grafana: http://localhost:3000 (admin/admin)
```

### Option 2: Kubernetes

```bash
# Prerequisites: kubectl configured, GPU operator installed

# 1. Build
./gpu-tools/deploy/scripts/build.sh

# 2. Deploy
./gpu-tools/deploy/scripts/deploy.sh k8s

# 3. Access (port-forward)
kubectl port-forward svc/opus-gpu-miner 8080:8080 -n opus-gpu
```

### Option 3: Systemd

```bash
# Prerequisites: Root access, NVIDIA drivers installed

# 1. Build
./gpu-tools/deploy/scripts/build.sh

# 2. Deploy
sudo ./gpu-tools/deploy/scripts/deploy.sh systemd

# 3. Manage
systemctl status opus-gpu
journalctl -u opus-gpu -f
```

## 📊 Architecture

### Docker Compose Stack
```
┌─────────────────────────────────────────────┐
│              Docker Host                     │
│                                              │
│  ┌──────────┐  ┌────────────┐  ┌─────────┐ │
│  │  Miner   │→ │ Prometheus │→ │ Grafana │ │
│  │ (GPU x2) │  │  (Metrics) │  │(Dashbrd)│ │
│  └──────────┘  └────────────┘  └─────────┘ │
│       ↓               ↓                      │
│  ┌──────────┐   ┌──────────┐                │
│  │ Watchdog │   │ InfluxDB │                │
│  │  (Mon)   │   │ (TSDB)   │                │
│  └──────────┘   └──────────┘                │
│                                              │
│  Network: opus-network (172.28.0.0/16)      │
└─────────────────────────────────────────────┘
```

### Kubernetes Deployment
```
┌─────────────────────────────────────────────┐
│         Kubernetes Cluster                   │
│                                              │
│  Namespace: opus-gpu                         │
│  ┌────────────────────────────────────────┐ │
│  │  Deployment: opus-gpu-miner            │ │
│  │  ┌──────────────────────────────────┐  │ │
│  │  │  Pod (GPU Node)                  │  │ │
│  │  │  ┌─────────────┐                 │  │ │
│  │  │  │ Container   │                 │  │ │
│  │  │  │ gpu-miner   │                 │  │ │
│  │  │  │ (GPU: 2)    │                 │  │ │
│  │  │  └─────────────┘                 │  │ │
│  │  │  ConfigMap │ Secret │ PVC        │  │ │
│  │  └──────────────────────────────────┘  │ │
│  └────────────────────────────────────────┘ │
│           ↓                                  │
│  ┌────────────────────────────────────────┐ │
│  │  Service: opus-gpu-miner               │ │
│  │  - ClusterIP: Internal access          │ │
│  │  - NodePort: External access (30080)   │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### Systemd Service
```
┌─────────────────────────────────────────────┐
│              Linux Host                      │
│                                              │
│  systemd                                     │
│  ├── opus-gpu.service                       │
│  │   ├── User: miner                        │
│  │   ├── WorkDir: /opt/opus-gpu            │
│  │   ├── Exec: /usr/local/bin/gpu-miner    │
│  │   └── GPU: nvidia0, nvidia1             │
│  │                                          │
│  └── opus-gpu-watchdog.service             │
│      └── Monitors main service              │
│                                              │
│  Files:                                      │
│  ├── /etc/opus-gpu/app.toml (config)       │
│  ├── /var/log/opus-gpu/ (logs)             │
│  └── /opt/opus-gpu/data/ (state)           │
└─────────────────────────────────────────────┘
```

## 🔒 Security Features

### Container Security
- **Non-root User**: UID 1000 (miner)
- **Read-only Root FS**: Where possible
- **Security Options**: no-new-privileges, seccomp
- **Resource Limits**: Memory, CPU constraints
- **Network Isolation**: Bridge network with minimal exposure

### Kubernetes Security
- **Pod Security**: SecurityContext with strict settings
- **RBAC**: Minimal permissions for service accounts
- **Secrets**: Encrypted at rest (KMS recommended)
- **Network Policies**: Traffic restriction (optional)
- **Resource Quotas**: Namespace-level limits

### Systemd Hardening
- **NoNewPrivileges**: Prevent privilege escalation
- **ProtectSystem**: Read-only /usr and /boot
- **RestrictAddressFamilies**: Limited network access
- **SystemCallFilter**: Restricted syscalls
- **Capabilities**: Minimal capability set

## 📈 Monitoring & Metrics

### Prometheus Metrics

**GPU Metrics**:
- `gpu_temperature_celsius` - Temperature per GPU
- `gpu_power_watts` - Power consumption
- `gpu_utilization_percent` - GPU usage
- `gpu_memory_used_bytes` - Memory allocation
- `gpu_memory_total_bytes` - Total memory

**Mining Metrics**:
- `mining_hashrate_mhs` - Hashrate per GPU
- `mining_shares_accepted_total` - Accepted shares counter
- `mining_shares_rejected_total` - Rejected shares counter
- `mining_pool_latency_ms` - Pool connection latency

**System Metrics**:
- `process_cpu_seconds_total` - CPU usage
- `process_resident_memory_bytes` - Memory usage
- `up` - Service health status

### Grafana Dashboard

**Panels**:
1. **Hashrate Timeline** - Real-time GPU performance
2. **Temperature Gauges** - Per-GPU thermal monitoring
3. **Power Gauges** - Power consumption tracking
4. **Utilization Graph** - GPU usage over time
5. **Memory Graph** - Memory allocation trends
6. **Service Status** - Uptime indicator
7. **Share Counters** - Accepted/Rejected statistics

**Alerts** (Prometheus Rules):
- High GPU temperature (>85°C for 2m)
- High memory usage (>95% for 5m)
- Low hashrate (<50 MH/s for 10m)
- Service down (for 2m)

## 🧪 Testing & Validation

### Build Validation
```bash
# Test build
./gpu-tools/deploy/scripts/build.sh

# Expected outputs:
# ✓ target/release/gpu-miner
# ✓ gpu-tools/bin/gpu-ctl
# ✓ gpu-tools/bin/gpu-watchdog
# ✓ gpu-tools/bin/gpu-monitor
# ✓ Docker image: opus-gpu:latest
```

### Docker Validation
```bash
# Health check
curl http://localhost:8080/health

# Expected: {"status":"healthy","uptime":123,"gpus":2}

# Metrics check
curl http://localhost:9090/metrics | grep mining_hashrate

# Expected: mining_hashrate_mhs{gpu_id="0"} 125.5
```

### Kubernetes Validation
```bash
# Pod status
kubectl get pods -n opus-gpu
# Expected: opus-gpu-miner-xxx  1/1  Running

# GPU allocation
kubectl describe pod -n opus-gpu | grep nvidia.com/gpu
# Expected: nvidia.com/gpu: 2

# Logs
kubectl logs -f deployment/opus-gpu-miner -n opus-gpu
# Expected: [INFO] GPU 0 initialized, [INFO] GPU 1 initialized
```

### Systemd Validation
```bash
# Service status
systemctl status opus-gpu
# Expected: active (running)

# GPU access
journalctl -u opus-gpu | grep -i "gpu.*initialized"
# Expected: GPU 0 initialized successfully

# Health endpoint
curl http://localhost:8080/health
# Expected: {"status":"healthy"}
```

## 🛠️ Troubleshooting

### Common Issues

**Problem**: GPU not detected
```bash
# Docker
docker run --rm --gpus all nvidia/cuda:12.0-runtime nvidia-smi

# Kubernetes
kubectl describe nodes | grep -A 5 nvidia.com/gpu

# Systemd
nvidia-smi
```

**Problem**: Permission denied
```bash
# Docker - check nvidia-docker2 runtime
cat /etc/docker/daemon.json

# Kubernetes - check GPU operator
kubectl get pods -n gpu-operator-resources

# Systemd - check user permissions
sudo chown -R miner:miner /opt/opus-gpu /var/log/opus-gpu
```

**Problem**: Service won't start
```bash
# Docker
docker-compose logs miner

# Kubernetes
kubectl describe pod -n opus-gpu
kubectl logs deployment/opus-gpu-miner -n opus-gpu

# Systemd
journalctl -u opus-gpu --no-pager
systemctl status opus-gpu
```

## 📝 Production Checklist

Before deploying to production:

- [ ] **Security**: Change all default passwords and secrets
- [ ] **Configuration**: Review and update `config/app.toml`
- [ ] **Resources**: Set appropriate CPU/Memory/GPU limits
- [ ] **Monitoring**: Configure alerting (email, Slack, PagerDuty)
- [ ] **Backups**: Set up configuration and data backups
- [ ] **Logging**: Configure log aggregation and retention
- [ ] **Access**: Document and secure access credentials
- [ ] **Testing**: Run load tests and validate performance
- [ ] **Documentation**: Complete deployment documentation
- [ ] **Runbook**: Create operational runbooks

See `gpu-tools/deploy/DEPLOYMENT_CHECKLIST.md` for detailed checklist.

## 🔄 Updates & Maintenance

### Rolling Updates (Kubernetes)
```bash
# Update image
kubectl set image deployment/opus-gpu-miner miner=opus-gpu:v0.2.0 -n opus-gpu

# Rollback if needed
kubectl rollout undo deployment/opus-gpu-miner -n opus-gpu
```

### Zero-Downtime Updates (Docker)
```bash
# Rebuild and update
docker-compose up -d --no-deps --build miner
```

### Service Updates (Systemd)
```bash
# Update binary
sudo cp target/release/gpu-miner /usr/local/bin/

# Restart service
sudo systemctl restart opus-gpu
```

## 📚 Additional Resources

- **Deployment Guide**: `gpu-tools/deploy/README.md`
- **Checklist**: `gpu-tools/deploy/DEPLOYMENT_CHECKLIST.md`
- **Docker Compose**: `gpu-tools/deploy/docker/docker-compose.yml`
- **Kubernetes**: `gpu-tools/deploy/k8s/`
- **Systemd**: `gpu-tools/deploy/systemd/`

## 🆘 Support

For deployment issues:
1. Check logs (docker-compose logs / kubectl logs / journalctl)
2. Review troubleshooting section in README
3. Consult DEPLOYMENT_CHECKLIST.md
4. Contact DevOps team

---

**Deployment Package Version**: 1.0.0
**Last Updated**: 2025-09-30
**Maintained By**: OPUS-GPU DevOps Team
