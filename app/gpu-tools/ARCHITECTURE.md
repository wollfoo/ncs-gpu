# OPUS-GPU Tools Architecture

**Complete DevOps Tooling Suite** (Bộ công cụ DevOps hoàn chỉnh) cho GPU mining infrastructure.

## 📐 System Overview (Tổng quan hệ thống)

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    OPUS-GPU Ecosystem                            │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         GPU Miner (Rust Core Binary)                   │    │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │    │
│  │  │ Mining   │  │   GPU     │  │   Monitoring       │  │    │
│  │  │ Engine   │  │ Executor  │  │   & Health         │  │    │
│  │  └────┬─────┘  └────┬─────┘  └──────┬─────────────┘  │    │
│  │       │             │                │                 │    │
│  │  ┌────▼─────────────▼────────────────▼─────────────┐  │    │
│  │  │       HTTP API (8080) & gRPC (9090)             │  │    │
│  │  └────┬──────────────────────────────────────┬─────┘  │    │
│  └───────┼──────────────────────────────────────┼────────┘    │
│          │                                      │              │
│  ┌───────▼──────────────────────────────────────▼────────┐    │
│  │              Go DevOps Tools Layer                     │    │
│  │                                                        │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │    │
│  │  │  gpu-ctl    │  │  watchdog   │  │   metrics-   │ │    │
│  │  │   (CLI)     │  │  (daemon)   │  │  aggregator  │ │    │
│  │  │             │  │             │  │  (service)   │ │    │
│  │  │ • Start/Stop│  │ • Health    │  │ • Prometheus │ │    │
│  │  │ • Status    │  │   checks    │  │   scraping   │ │    │
│  │  │ • GPU mgmt  │  │ • Auto-     │  │ • InfluxDB   │ │    │
│  │  │ • Stealth   │  │   restart   │  │   export     │ │    │
│  │  │ • Logs      │  │ • Rate      │  │ • Alerting   │ │    │
│  │  └─────────────┘  │   limiting  │  └──────┬───────┘ │    │
│  │                   └─────────────┘         │         │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────▼────────┐ │    │
│  │  │   config    │  │     log     │  │  Time-Series │ │    │
│  │  │  manager    │  │  collector  │  │   Storage    │ │    │
│  │  │             │  │             │  │  (InfluxDB)  │ │    │
│  │  │ • Hot-reload│  │ • Multi-    │  │             │ │    │
│  │  │ • Schema    │  │   input     │  │             │ │    │
│  │  │   validation│  │ • Multi-    │  │             │ │    │
│  │  │ • Vault     │  │   output    │  │             │ │    │
│  │  └─────────────┘  └─────────────┘  └──────────────┘ │    │
│  └────────────────────────────────────────────────────────┘    │
│          │                      │                │              │
│  ┌───────▼──────────────────────▼────────────────▼────────┐    │
│  │              External Services (Optional)              │    │
│  │  ┌──────────┐  ┌────────┐  ┌────────┐  ┌──────────┐  │    │
│  │  │ Grafana  │  │  Loki  │  │ Vault  │  │  Alert   │  │    │
│  │  │Dashboard │  │  Logs  │  │Secrets │  │ Manager  │  │    │
│  │  └──────────┘  └────────┘  └────────┘  └──────────┘  │    │
│  └───────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧩 Component Details (Chi tiết thành phần)

### 1. **gpu-ctl CLI Tool**

**Purpose** (Mục đích): Command-line interface cho user interaction.

**Architecture**:
```
gpu-ctl (main)
├── cmd/
│   ├── root.go       # Cobra root command
│   ├── start.go      # Start miner
│   ├── stop.go       # Stop miner
│   ├── status.go     # Status display
│   ├── metrics.go    # Metrics query
│   ├── logs.go       # Log streaming
│   ├── stealth.go    # Stealth toggle
│   └── gpu.go        # GPU commands
├── internal/
│   ├── client/
│   │   ├── grpc_client.go   # gRPC client implementation
│   │   └── http_client.go   # HTTP REST client
│   └── config/
│       └── config.go         # Config loading (Viper)
└── main.go
```

**Key Features**:
- **Cobra Framework**: Professional CLI với subcommands
- **Dual Protocol**: HTTP REST + gRPC support
- **Multiple Output Formats**: Table, JSON, YAML
- **Interactive Mode**: Bubbletea TUI (future)

**Communication Flow**:
```
User Command → Cobra Parser → Config Load → Client Creation
                                                ↓
                                          gRPC/HTTP Request
                                                ↓
                                          Response Parse
                                                ↓
                                          Format Output
```

---

### 2. **Metrics Aggregator Service**

**Purpose**: Thu thập metrics từ miner và export sang TSDB.

**Architecture**:
```
metrics-aggregator
├── cmd/
│   └── main.go
├── internal/
│   ├── aggregator/
│   │   ├── aggregator.go     # Core aggregator
│   │   └── alertmanager.go   # Alert processing
│   └── storage/
│       ├── storage.go         # Storage interface
│       ├── memory.go          # In-memory storage
│       ├── influxdb.go        # InfluxDB backend
│       └── victoria.go        # VictoriaMetrics backend
└── main.go
```

**Data Flow**:
```
Miner /metrics → Scraper → Parser → Prometheus Metrics
   (5s)                                    ↓
                                    Alert Rules Check
                                           ↓
                                    ┌──────┴──────┐
                                    ↓             ↓
                              Time-Series DB  Webhook
                              (InfluxDB)     (Alerts)
```

**Metrics Pipeline**:
1. **Scrape**: HTTP GET `/metrics` mỗi 5s
2. **Parse**: Prometheus text format parser
3. **Transform**: Convert to internal format
4. **Check**: Evaluate alert rules
5. **Store**: Write to InfluxDB/Victoria
6. **Export**: Expose aggregated metrics

---

### 3. **Watchdog Daemon**

**Purpose**: Health monitoring với auto-restart capability.

**Architecture**:
```
gpu-watchdog
├── cmd/
│   └── main.go
├── internal/
│   └── watchdog/
│       └── watchdog.go       # Core watchdog logic
└── main.go
```

**State Machine**:
```
       ┌─────────────┐
       │   START     │
       └──────┬──────┘
              │
      ┌───────▼────────┐
      │  Start Miner   │
      └───────┬────────┘
              │
      ┌───────▼────────────┐
      │  Health Check Loop │◄────────┐
      └───────┬────────────┘         │
              │                       │
       ┌──────▼──────┐                │
       │  Healthy?   │────Yes─────────┘
       └──────┬──────┘
              │ No
       ┌──────▼───────────┐
       │ Exceeded Timeout?│
       └──────┬───────────┘
              │ Yes
       ┌──────▼──────┐
       │  Restart    │
       └──────┬──────┘
              │
       ┌──────▼──────────┐
       │ Rate Limit OK?  │
       └──────┬──────────┘
          Yes │ │ No
       ┌──────▼──┐  ┌──────▼─────┐
       │ Restart │  │  Log Error │
       └──────┬──┘  └────────────┘
              │
       ┌──────▼─────────┐
       │  Backoff Delay │
       └───────┬────────┘
               │
       Back to Health Check
```

**Key Features**:
- Health check polling (10s interval)
- Graceful shutdown (SIGTERM → 30s → SIGKILL)
- Rate limiting (5 restarts per 5min window)
- Process group cleanup
- Systemd integration

---

### 4. **Config Manager**

**Purpose**: Hot-reload configuration với validation.

**Architecture**:
```
config-manager
├── internal/
│   └── configmgr/
│       └── manager.go        # File watcher + validation
└── api/proto/
    └── miner.proto           # ReloadConfig gRPC method
```

**Hot-Reload Flow**:
```
File Change Event → fsnotify Watcher
                         ↓
                   Debounce (100ms)
                         ↓
                   Read File Content
                         ↓
                   Parse YAML
                         ↓
                   JSON Schema Validation
                         ↓
                   ┌────┴────┐
                   │ Valid?  │
                   └────┬────┘
                   Yes  │  No
              ┌─────────┴────────┐
              ↓                  ↓
    gRPC ReloadConfig()    Log Error
              ↓
        Miner Reloads
              ↓
        Success Response
```

**Secrets Management**:
- HashiCorp Vault integration
- AWS Secrets Manager support
- Environment variable injection

---

### 5. **Log Collector**

**Purpose**: Centralized log aggregation.

**Architecture**:
```
log-collector
├── internal/
│   └── logcollector/
│       ├── collector.go      # Main collector
│       ├── input.go          # Input interfaces
│       └── sink.go           # Output interfaces
└── main.go
```

**Pipeline**:
```
Input Sources:
- File (/var/log/miner/*.log)
- Stdout (Docker containers)
- HTTP API (/logs endpoint)
      ↓
┌─────▼─────────┐
│  Log Parser   │  (JSON/Text)
└─────┬─────────┘
      ↓
┌─────▼─────────┐
│ Buffer Queue  │  (1000 entries)
└─────┬─────────┘
      ↓
Output Sinks:
- File (rotation)
- Loki (aggregation)
- Stdout (console)
- Elasticsearch (search)
```

---

### 6. **Deployment Automation**

**Purpose**: Production deployment infrastructure.

**Components**:
```
deploy/
├── docker/
│   ├── Dockerfile.miner          # Multi-stage build
│   └── docker-compose.yml        # Complete stack
├── scripts/
│   ├── build.sh                  # Build automation
│   └── deploy.sh                 # Deployment automation
├── k8s/
│   ├── deployment.yaml           # K8s deployment
│   ├── service.yaml              # ClusterIP service
│   ├── configmap.yaml            # Config
│   └── secret.yaml               # Secrets template
└── config/
    ├── miner.yaml                # Miner config
    ├── aggregator.yaml           # Aggregator config
    └── grafana/                  # Grafana dashboards
```

**Multi-Stage Dockerfile**:
```dockerfile
Stage 1: Rust Builder
- FROM rust:1.80-slim
- Build Rust binary (cargo build --release)
- Strip binary (reduce size)

Stage 2: Go Builder
- FROM golang:1.23-alpine
- Build Go tools (gpu-ctl, watchdog, aggregator)

Stage 3: Runtime
- FROM nvidia/cuda:12.0-runtime-ubuntu22.04
- Copy binaries from stages 1 & 2
- Non-root user (security)
- Health checks
```

---

## 🔄 Data Flow Diagrams (Sơ đồ luồng dữ liệu)

### Metrics Collection Flow

```
┌─────────────┐
│ GPU Miner   │
│  (Rust)     │
└──────┬──────┘
       │ HTTP /metrics
       │ (Prometheus format)
       │
┌──────▼─────────────────┐
│ Metrics Aggregator     │
│  (Go)                  │
│  ┌──────────────────┐  │
│  │ Scraper (5s)     │  │
│  │ Parser           │  │
│  │ Alert Engine     │  │
│  └────┬─────────────┘  │
└───────┼────────────────┘
        │
    ┌───▼───┐
    │       │
┌───▼──┐ ┌──▼────┐
│ TSDB │ │Webhook│
│InfluxDB Alerts │
└──┬───┘ └───────┘
   │
┌──▼──────┐
│ Grafana │
│Dashboard│
└─────────┘
```

### Configuration Management Flow

```
┌────────────────┐
│ config.yaml    │
│  (on disk)     │
└───────┬────────┘
        │ File change event
        │
┌───────▼──────────────┐
│ Config Manager (Go)  │
│  ┌────────────────┐  │
│  │ fsnotify       │  │
│  │ Watcher        │  │
│  └────┬───────────┘  │
│       │              │
│  ┌────▼───────────┐  │
│  │ JSON Schema    │  │
│  │ Validator      │  │
│  └────┬───────────┘  │
└───────┼──────────────┘
        │ gRPC ReloadConfig()
        │
┌───────▼──────────┐
│ GPU Miner (Rust) │
│  ┌─────────────┐ │
│  │ Config Hot- │ │
│  │ Reload Logic│ │
│  └─────────────┘ │
└──────────────────┘
```

### Health Monitoring Flow

```
┌───────────────────┐
│ Watchdog Daemon   │
│  (Go)             │
│  ┌─────────────┐  │
│  │ Ticker 10s  │  │
│  └──────┬──────┘  │
└─────────┼─────────┘
          │ HTTP GET /health
          │
┌─────────▼─────────┐
│ GPU Miner (Rust)  │
│  ┌─────────────┐  │
│  │ Health      │  │
│  │ Endpoint    │  │
│  └──────┬──────┘  │
└─────────┼─────────┘
          │ Status: OK / Unhealthy
          │
┌─────────▼──────────────┐
│ Watchdog Decision      │
│  ┌──────────────────┐  │
│  │ Healthy? → OK    │  │
│  │ Unhealthy? →     │  │
│  │   Restart?       │  │
│  └──────────────────┘  │
└────────────────────────┘
```

---

## 🔒 Security Architecture (Kiến trúc bảo mật)

### Authentication & Authorization

```
┌──────────────┐
│ API Request  │
└──────┬───────┘
       │ API Token Header
       │
┌──────▼───────────────┐
│ Token Validation     │
│  ┌────────────────┐  │
│  │ JWT Verify     │  │
│  │ Scope Check    │  │
│  └────┬───────────┘  │
└───────┼──────────────┘
        │
    ┌───▼───┐
    │       │
  Valid   Invalid
    │       │
┌───▼───┐ ┌─▼────┐
│Process│ │ 401  │
│Request│ │Reject│
└───────┘ └──────┘
```

### Secrets Management

```
┌────────────────┐
│ Vault/AWS SM   │
└───────┬────────┘
        │ API Call
        │
┌───────▼──────────────┐
│ Config Manager       │
│  ┌────────────────┐  │
│  │ Fetch Secret   │  │
│  │ Inject Config  │  │
│  └────┬───────────┘  │
└───────┼──────────────┘
        │ Hot-reload
        │
┌───────▼────────┐
│ GPU Miner      │
│  (with secrets)│
└────────────────┘
```

---

## 📊 Performance Considerations (Cân nhắc hiệu năng)

### Metrics Aggregator
- **Collection Interval**: 5s (configurable)
- **Buffer Size**: 1000 metric points
- **Storage Batching**: 100 points per write
- **Memory Usage**: ~50MB base + ~1KB per metric

### Watchdog
- **Health Check Interval**: 10s
- **Unhealthy Timeout**: 30s
- **Memory Usage**: ~10MB
- **CPU Usage**: <1%

### Config Manager
- **File Watch**: fsnotify (event-driven, zero polling)
- **Validation**: <100ms for typical configs
- **Hot-Reload**: <1s end-to-end

---

## 🚀 Deployment Patterns (Mẫu triển khai)

### 1. Docker Compose (Development)
- All services in one stack
- Shared network
- Volume mounts for config

### 2. Systemd (Production Servers)
- Independent service units
- Automatic restart
- Log integration với journald

### 3. Kubernetes (Cloud)
- DaemonSet for miner (1 per GPU node)
- Deployment for aggregator (replicated)
- ConfigMap + Secret for config
- PersistentVolume for logs

---

## 🎯 Design Decisions (Quyết định thiết kế)

### Why Go for Tools?
- **Simplicity**: Clear, readable code
- **Concurrency**: Goroutines cho parallel ops
- **Cross-compile**: Single binary, no dependencies
- **Stdlib**: Rich standard library
- **DevOps**: Perfect for tooling & automation

### Why Separate Binaries?
- **Modularity**: Each tool has single responsibility
- **Deployment**: Deploy only what you need
- **Testing**: Easier to test in isolation
- **Debugging**: Simpler debugging

### Why gRPC + HTTP?
- **gRPC**: Efficient binary protocol, streaming
- **HTTP**: Human-readable, curl-friendly
- **Dual Support**: Best of both worlds

---

**Built with ❤️ by OPUS-GPU Team**
