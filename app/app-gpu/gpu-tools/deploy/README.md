# OPUS-GPU Deployment Guide

Complete deployment package for OPUS-GPU with support for Docker, Kubernetes, and Systemd.

## 📁 Directory Structure

```
deploy/
├── docker/              # Docker Compose deployment
│   ├── docker-compose.yml
│   ├── prometheus.yml
│   └── config/         # Configuration files
├── k8s/                # Kubernetes manifests
│   ├── namespace.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── secret.yaml
├── systemd/            # Systemd service files
│   ├── opus-gpu.service
│   └── opus-gpu-watchdog.service
├── scripts/            # Automation scripts
│   ├── build.sh
│   └── deploy.sh
└── grafana/            # Monitoring dashboards
    └── dashboard.json
```

## 🚀 Quick Start

### Prerequisites

- **Docker**: Docker Engine 20.10+ with nvidia-docker2 runtime
- **Kubernetes**: kubectl 1.24+ with GPU operator installed
- **Systemd**: systemd-based Linux distribution
- **NVIDIA GPU**: CUDA 12.0+ compatible GPU with latest drivers

### Build

Build all components (Rust binary, Go tools, Docker image):

```bash
cd gpu-tools/deploy/scripts
./build.sh
```

**Build Options**:
```bash
# Release build (default)
BUILD_TYPE=release ./build.sh

# Debug build
BUILD_TYPE=debug ./build.sh

# Skip tests
SKIP_TESTS=true ./build.sh

# Custom Docker tag
DOCKER_TAG=opus-gpu:v0.1.0 ./build.sh

# Verbose output
VERBOSE=true ./build.sh
```

## 🐳 Docker Deployment

### Quick Deploy

```bash
cd gpu-tools/deploy/scripts
./deploy.sh docker
```

### Manual Deployment

```bash
cd gpu-tools/deploy/docker

# Create config directory
mkdir -p config
cp ../../config/app.toml config/

# Start services
docker-compose up -d

# View logs
docker-compose logs -f miner

# Stop services
docker-compose down
```

### Access Services

- **Miner API**: http://localhost:8080
- **Metrics**: http://localhost:9090
- **Prometheus**: http://localhost:9091
- **Grafana**: http://localhost:3000 (admin/admin)

### Docker Compose Services

| Service | Description | Port |
|---------|-------------|------|
| miner | Main GPU miner | 8080, 9090 |
| prometheus | Metrics collection | 9091 |
| grafana | Monitoring dashboard | 3000 |
| influxdb | Time-series storage (optional) | 8086 |
| gpu-watchdog | GPU health monitoring | - |

## ☸️ Kubernetes Deployment

### Prerequisites

1. **GPU Operator**: Install NVIDIA GPU Operator
```bash
helm repo add nvidia https://nvidia.github.io/gpu-operator
helm install --wait --generate-name \
  nvidia/gpu-operator
```

2. **Verify GPU Nodes**:
```bash
kubectl get nodes -l nvidia.com/gpu=true
```

### Quick Deploy

```bash
cd gpu-tools/deploy/scripts
./deploy.sh k8s
```

### Manual Deployment

```bash
cd gpu-tools/deploy/k8s

# Create namespace
kubectl apply -f namespace.yaml

# Apply configurations
kubectl apply -f configmap.yaml -n opus-gpu
kubectl apply -f secret.yaml -n opus-gpu

# Deploy application
kubectl apply -f deployment.yaml -n opus-gpu
kubectl apply -f service.yaml -n opus-gpu

# Wait for deployment
kubectl rollout status deployment/opus-gpu-miner -n opus-gpu
```

### Access Services

```bash
# Port forwarding
kubectl port-forward svc/opus-gpu-miner 8080:8080 -n opus-gpu

# NodePort access (if using NodePort service)
# http://<node-ip>:30080
```

### Useful Commands

```bash
# View pods
kubectl get pods -n opus-gpu

# View logs
kubectl logs -f deployment/opus-gpu-miner -n opus-gpu

# Exec into pod
kubectl exec -it deployment/opus-gpu-miner -n opus-gpu -- /bin/bash

# Scale deployment
kubectl scale deployment/opus-gpu-miner --replicas=3 -n opus-gpu

# Delete deployment
kubectl delete namespace opus-gpu
```

## 🔧 Systemd Deployment

### Prerequisites

- Root/sudo access
- NVIDIA drivers installed
- Binaries built (run `build.sh` first)

### Quick Deploy

```bash
cd gpu-tools/deploy/scripts
sudo ./deploy.sh systemd
```

### Manual Deployment

```bash
# Create user
sudo useradd -m -s /bin/bash miner

# Create directories
sudo mkdir -p /opt/opus-gpu/{bin,config,data}
sudo mkdir -p /var/log/opus-gpu
sudo mkdir -p /etc/opus-gpu

# Copy binaries
sudo cp target/release/gpu-miner /usr/local/bin/
sudo cp gpu-tools/bin/* /usr/local/bin/

# Copy configuration
sudo cp config/* /etc/opus-gpu/

# Set permissions
sudo chown -R miner:miner /opt/opus-gpu /var/log/opus-gpu /etc/opus-gpu

# Install service
sudo cp gpu-tools/deploy/systemd/opus-gpu.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable opus-gpu
sudo systemctl start opus-gpu
```

### Service Management

```bash
# Status
systemctl status opus-gpu

# Start
sudo systemctl start opus-gpu

# Stop
sudo systemctl stop opus-gpu

# Restart
sudo systemctl restart opus-gpu

# View logs
journalctl -u opus-gpu -f

# View last 100 lines
journalctl -u opus-gpu -n 100
```

## 📊 Monitoring

### Prometheus Metrics

Metrics exposed on port 9090 (or 8080/metrics):

- `mining_hashrate_mhs` - GPU hashrate in MH/s
- `gpu_temperature_celsius` - GPU temperature
- `gpu_power_watts` - GPU power consumption
- `gpu_utilization_percent` - GPU utilization
- `gpu_memory_used_bytes` - GPU memory usage
- `mining_shares_accepted_total` - Accepted shares counter
- `mining_shares_rejected_total` - Rejected shares counter

### Grafana Dashboard

Import the dashboard:

```bash
# Copy dashboard to Grafana
cp gpu-tools/deploy/grafana/dashboard.json /path/to/grafana/dashboards/
```

Or import via Grafana UI:
1. Login to Grafana (http://localhost:3000)
2. Go to Dashboards → Import
3. Upload `dashboard.json`

## 🔐 Security

### Production Checklist

- [ ] Change default passwords in `secret.yaml`
- [ ] Update JWT secret in configuration
- [ ] Enable API authentication
- [ ] Use TLS/SSL certificates
- [ ] Configure firewall rules
- [ ] Enable resource limits
- [ ] Regular security updates
- [ ] Monitor access logs

### Secrets Management

**Kubernetes**:
```bash
# Create secret from literals
kubectl create secret generic opus-gpu-secrets \
  --from-literal=jwt-secret=<your-secret> \
  --from-literal=wallet-address=<your-wallet> \
  -n opus-gpu

# Use external secret manager (recommended)
# - HashiCorp Vault
# - AWS Secrets Manager
# - Azure Key Vault
# - Google Secret Manager
```

**Docker**:
```bash
# Use Docker secrets
echo "my-secret" | docker secret create jwt_secret -

# Update docker-compose.yml to use secrets
```

## 🧪 Testing

### Health Checks

```bash
# Docker
curl http://localhost:8080/health

# Kubernetes
kubectl exec -n opus-gpu deployment/opus-gpu-miner -- \
  curl -f http://localhost:8080/health

# Systemd
curl http://localhost:8080/health
```

### Performance Testing

```bash
# Run benchmark
./gpu-tools/bin/gpu-ctl benchmark --duration 60s

# Check metrics
curl http://localhost:8080/metrics | grep mining_hashrate
```

## 🐛 Troubleshooting

### Docker Issues

**GPU not detected**:
```bash
# Verify nvidia-docker2 runtime
docker run --rm --gpus all nvidia/cuda:12.0-runtime nvidia-smi

# Check docker daemon configuration
cat /etc/docker/daemon.json
```

**Container crashes**:
```bash
# View logs
docker-compose logs miner

# Check resource usage
docker stats
```

### Kubernetes Issues

**Pods pending**:
```bash
# Check pod events
kubectl describe pod -n opus-gpu

# Verify GPU resources
kubectl describe nodes | grep -A 5 nvidia.com/gpu
```

**OOMKilled**:
```bash
# Increase memory limits in deployment.yaml
resources:
  limits:
    memory: 8Gi
```

### Systemd Issues

**Service fails to start**:
```bash
# Check status
systemctl status opus-gpu

# View full logs
journalctl -u opus-gpu --no-pager

# Check binary
/usr/local/bin/gpu-miner --version
```

**Permission denied**:
```bash
# Check file ownership
ls -la /etc/opus-gpu/
ls -la /var/log/opus-gpu/

# Fix permissions
sudo chown -R miner:miner /opt/opus-gpu /var/log/opus-gpu
```

## 📝 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CUDA_VISIBLE_DEVICES` | GPU devices to use | `0,1` |
| `CONFIG_PATH` | Configuration file path | `/etc/opus-gpu/app.toml` |
| `RUST_LOG` | Log level | `info` |
| `LOG_PATH` | Log directory | `/var/log/opus-gpu` |

### Resource Limits

**Docker**:
```yaml
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '4'
```

**Kubernetes**:
```yaml
resources:
  limits:
    memory: 4Gi
    cpu: "4"
    nvidia.com/gpu: 2
```

**Systemd**:
```ini
MemoryMax=4G
CPUQuota=400%
```

## 🔄 Updates

### Rolling Updates (Kubernetes)

```bash
# Update image
kubectl set image deployment/opus-gpu-miner \
  miner=opus-gpu:v0.2.0 -n opus-gpu

# Monitor rollout
kubectl rollout status deployment/opus-gpu-miner -n opus-gpu

# Rollback if needed
kubectl rollout undo deployment/opus-gpu-miner -n opus-gpu
```

### Zero-Downtime Updates (Docker)

```bash
# Build new image
docker build -t opus-gpu:new .

# Update service
docker-compose up -d --no-deps --build miner
```

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Kubernetes GPU Documentation](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [Systemd Service Documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

## 🆘 Support

For issues and questions:
- GitHub Issues: https://github.com/opus-gpu/app-gpu/issues
- Documentation: https://opus-gpu.readthedocs.io
