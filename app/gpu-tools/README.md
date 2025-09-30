# OPUS-GPU Go Tools

**Complete DevOps tooling suite** (Bộ công cụ DevOps hoàn chỉnh) cho OPUS-GPU mining infrastructure. 6 Go-based tools để quản lý, giám sát, và tự động hóa GPU mining operations.

## 📦 Components (Thành phần)

### 1. **gpu-ctl** - CLI Management Tool
Command-line interface để điều khiển GPU miner.

**Features** (Tính năng):
- ✅ Start/stop miner với graceful shutdown
- ✅ Real-time status monitoring (watch mode)
- ✅ GPU-specific statistics và health checks
- ✅ Stealth mode toggle
- ✅ Log streaming với filtering
- ✅ Multiple output formats (table, JSON, YAML)

**Usage**:
```bash
# Start miner
gpu-ctl start --config /etc/miner/config.yaml

# Monitor status
gpu-ctl status --watch

# GPU management
gpu-ctl gpu list
gpu-ctl gpu stats 0

# Stealth mode
gpu-ctl stealth enable

# Logs
gpu-ctl logs --follow --level error
```

---

### 2. **metrics-aggregator** - Metrics Collection Service
Thu thập metrics từ miner và export sang time-series databases.

**Features**:
- ✅ Prometheus metrics scraping (5s interval)
- ✅ InfluxDB/VictoriaMetrics support
- ✅ Alert rules engine
- ✅ Webhook notifications
- ✅ Aggregated metrics HTTP endpoint

**Metrics Tracked**:
- `gpu_hashrate_mhs` - Per-GPU hashrate
- `gpu_temperature_celsius` - GPU temperature
- `gpu_power_draw_watts` - Power consumption
- `gpu_memory_used_mb` - Memory utilization
- `mining_shares_accepted_total` - Total shares
- `process_uptime_seconds` - Miner uptime

**Configuration**:
```yaml
# aggregator.yaml
miner_url: "http://localhost:8080"
collect_interval: 5s
storage_type: "influxdb"
storage_url: "http://influxdb:8086"

alerts:
  - name: "high_temperature"
    condition: "gpu_temperature > 85"
    action: "webhook"
    url: "https://alerts.example.com/gpu-overheat"
```

---

### 3. **gpu-watchdog** - Health Monitoring Daemon
Watchdog service với auto-restart capability.

**Features**:
- ✅ HTTP health checks (10s interval)
- ✅ Auto-restart on failures
- ✅ Graceful shutdown (SIGTERM → 30s → SIGKILL)
- ✅ Restart rate limiting (5 restarts/5min)
- ✅ Process group cleanup
- ✅ Systemd integration

**Configuration**:
```yaml
binary_path: "/usr/local/bin/gpu-miner"
health_check_url: "http://localhost:8080/health"
check_interval: 10s
unhealthy_timeout: 30s
max_restarts: 5
restart_backoff: 5s
shutdown_timeout: 30s
```

---

### 4. **config-manager** - Configuration Manager với Hot-Reload
Theo dõi config file changes và hot-reload miner.

**Features**:
- ✅ File watcher với fsnotify
- ✅ JSON Schema validation
- ✅ Hot-reload via gRPC
- ✅ HashiCorp Vault integration
- ✅ AWS Secrets Manager support

**Usage**:
```go
cfg := &configmgr.Config{
    ConfigPath:  "/etc/miner/config.yaml",
    SchemaPath:  "/etc/miner/schema.json",
    GRPCAddr:    "localhost:9090",
}

mgr := configmgr.NewManager(cfg, logger)
mgr.Run(context.Background())
```

---

### 5. **log-collector** - Centralized Logging Infrastructure
Thu thập logs từ multiple sources và forward đến multiple sinks.

**Features**:
- ✅ Multiple inputs (file, stdout, HTTP)
- ✅ Multiple outputs (file, Loki, stdout)
- ✅ JSON log parsing
- ✅ Structured logging
- ✅ Log rotation support

**Configuration**:
```yaml
inputs:
  - type: "file"
    path: "/var/log/miner/output.log"
  - type: "stdout"

outputs:
  - type: "file"
    path: "/var/log/miner/aggregated.log"
    format: "json"
  - type: "stdout"
    format: "text"
```

---

### 6. **Deployment Automation**
Scripts và Docker infrastructure cho production deployment.

**Files**:
- `deploy/docker/Dockerfile.miner` - Multi-stage Dockerfile
- `deploy/docker/docker-compose.yml` - Complete stack
- `deploy/scripts/build.sh` - Build automation
- `deploy/scripts/deploy.sh` - Deployment automation
- `deploy/k8s/` - Kubernetes manifests

---

## 🚀 Quick Start (Bắt đầu nhanh)

### Build Tools

```bash
# Build tất cả Go tools
cd gpu-tools
./deploy/scripts/build.sh

# Build specific component
./deploy/scripts/build.sh --go-only

# Build Docker image
./deploy/scripts/build.sh --docker
```

### Deploy với Docker Compose

```bash
cd deploy/docker

# Edit .env file
cp .env.example .env
vim .env

# Start stack
docker-compose up -d

# Check status
docker-compose ps
gpu-ctl status
```

### Deploy với Systemd

```bash
# Build binaries
./deploy/scripts/build.sh

# Deploy
sudo ./deploy/scripts/deploy.sh systemd

# Check status
systemctl status gpu-watchdog
gpu-ctl status
```

---

## 📊 Architecture (Kiến trúc)

```
┌─────────────────────────────────────────────────────────────┐
│                     GPU Miner (Rust)                        │
│  ┌─────────┐  ┌─────────┐  ┌────────────┐                 │
│  │ HTTP API│  │  gRPC   │  │ Prometheus │                 │
│  │  :8080  │  │  :9090  │  │  /metrics  │                 │
│  └────┬────┘  └────┬────┘  └─────┬──────┘                 │
└───────┼───────────┼──────────────┼────────────────────────┘
        │           │              │
        │           │              │
┌───────▼───────────▼──────────────▼────────────────────────┐
│                    Go Tools Layer                          │
│                                                            │
│  ┌──────────┐  ┌─────────────┐  ┌──────────────┐        │
│  │ gpu-ctl  │  │  watchdog   │  │   metrics-   │        │
│  │   CLI    │  │   daemon    │  │  aggregator  │        │
│  └──────────┘  └─────────────┘  └──────┬───────┘        │
│                                         │                 │
│  ┌──────────┐  ┌─────────────┐  ┌──────▼───────┐        │
│  │  config  │  │     log     │  │   InfluxDB   │        │
│  │ manager  │  │  collector  │  │  VictoriaM   │        │
│  └──────────┘  └─────────────┘  └──────────────┘        │
└────────────────────────────────────────────────────────────┘
         │                 │                │
         │                 │                │
┌────────▼─────────────────▼────────────────▼───────────────┐
│             External Services (Optional)                   │
│  ┌──────────┐  ┌─────────┐  ┌─────────┐  ┌────────────┐ │
│  │ Grafana  │  │  Loki   │  │  Vault  │  │ Alertmanager│ │
│  │   :3000  │  │  :3100  │  │  :8200  │  │    :9093    │ │
│  └──────────┘  └─────────┘  └─────────┘  └────────────┘ │
└────────────────────────────────────────────────────────────┘
```

---

## 🔧 Configuration (Cấu hình)

### Global Config (`.gpu-ctl.yaml`)

```yaml
miner:
  url: "http://localhost:8080"
  grpc_addr: "localhost:9090"
  timeout: 30

output:
  format: "table"  # table, json, yaml
  color: true

alerts:
  enabled: true
  rules:
    - name: "gpu_temperature"
      metric: "gpu_temperature"
      operator: ">"
      threshold: 85.0
      action: "webhook"
      action_url: "https://alerts.example.com/gpu-overheat"
```

### Environment Variables

```bash
# Miner connection
export GPUCTL_MINER_URL="http://localhost:8080"
export GPUCTL_MINER_GRPC_ADDR="localhost:9090"

# Output format
export GPUCTL_OUTPUT_FORMAT="json"

# Aggregator
export MINER_URL="http://localhost:8080"
export INFLUXDB_URL="http://influxdb:8086"
export INFLUXDB_TOKEN="your-secret-token"
```

---

## 📈 Monitoring Stack (Stack giám sát)

### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'gpu-miner'
    static_configs:
      - targets: ['miner:9091']
    scrape_interval: 5s

  - job_name: 'metrics-aggregator'
    static_configs:
      - targets: ['metrics-aggregator:9091']
    scrape_interval: 10s
```

### Grafana Dashboards

Pre-built dashboards available in `deploy/config/grafana/dashboards/`:
- **GPU Performance**: Hashrate, temperature, power draw
- **System Health**: Uptime, restarts, errors
- **Mining Stats**: Shares accepted/rejected, pool status

---

## 🧪 Testing (Kiểm thử)

```bash
# Unit tests
go test ./...

# Integration tests
go test -tags=integration ./...

# Benchmarks
go test -bench=. ./...

# Coverage
go test -cover ./...
```

---

## 📦 Dependencies (Phụ thuộc)

### Core Libraries
- `github.com/spf13/cobra` - CLI framework
- `github.com/spf13/viper` - Configuration management
- `google.golang.org/grpc` - gRPC client
- `github.com/prometheus/client_golang` - Prometheus metrics
- `github.com/fsnotify/fsnotify` - File watching
- `go.uber.org/zap` - Structured logging

### Optional
- `github.com/influxdata/influxdb-client-go/v2` - InfluxDB
- `github.com/hashicorp/vault/api` - Vault secrets
- `github.com/charmbracelet/bubbletea` - TUI framework

---

## 🔒 Security (Bảo mật)

### Best Practices
- ✅ Non-root container user
- ✅ Secrets management (Vault/AWS Secrets Manager)
- ✅ TLS/mTLS for gRPC connections
- ✅ API authentication tokens
- ✅ Resource limits và isolation

### Secrets Management

```bash
# Load secrets từ Vault
config-manager --vault-addr https://vault:8200 \
              --vault-token $VAULT_TOKEN

# Load từ AWS Secrets Manager
config-manager --aws-secret gpu-miner-config
```

---

## 🚧 Troubleshooting (Xử lý sự cố)

### Watchdog không restart miner
```bash
# Check logs
journalctl -u gpu-watchdog -f

# Verify health endpoint
curl http://localhost:8080/health

# Check restart rate limit
gpu-ctl status
```

### Metrics không thu thập được
```bash
# Test Prometheus endpoint
curl http://localhost:8080/metrics

# Check aggregator logs
docker logs opus-metrics-aggregator

# Verify InfluxDB connection
influx ping --url http://localhost:8086
```

### Config hot-reload không hoạt động
```bash
# Verify file watcher
config-manager --validate

# Test gRPC connection
grpcurl -plaintext localhost:9090 list

# Check schema validation
config-manager --schema-validate
```

---

## 📚 Documentation (Tài liệu)

- **Architecture Design**: `/docs/architecture.md`
- **API Reference**: `/docs/api.md`
- **Deployment Guide**: `/docs/deployment.md`
- **Troubleshooting**: `/docs/troubleshooting.md`

---

## 🤝 Contributing (Đóng góp)

```bash
# Fork và clone repo
git clone https://github.com/your-username/opus-gpu

# Create feature branch
git checkout -b feature/new-tool

# Make changes và test
go test ./...
go build ./...

# Commit và push
git commit -m "feat: Add new monitoring tool"
git push origin feature/new-tool

# Create Pull Request
```

---

## 📄 License (Giấy phép)

MIT License - See LICENSE file for details.

---

## 🎯 Roadmap (Lộ trình)

### v1.1.0 (Q1 2025)
- [ ] Kubernetes operator
- [ ] Advanced alerting with PagerDuty/Slack
- [ ] Multi-miner orchestration
- [ ] Web dashboard (React + Go backend)

### v1.2.0 (Q2 2025)
- [ ] Auto-scaling based on profitability
- [ ] A/B testing for mining strategies
- [ ] Machine learning for GPU optimization
- [ ] Advanced stealth mode features

---

## 📞 Support (Hỗ trợ)

- **Issues**: https://github.com/opus-gpu/gpu-tools/issues
- **Discussions**: https://github.com/opus-gpu/gpu-tools/discussions
- **Email**: support@opus-gpu.io

---

**Built with ❤️ by OPUS-GPU Team**
