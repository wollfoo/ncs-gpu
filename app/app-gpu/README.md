# 🚀 Opus GPU - High-Performance GPU Mining Architecture

**Event-Driven GPU Processing System** với **Zero-Copy**, **CUDA Graphs**, và **Advanced Security**

## 🏛️ Kiến Trúc Tổng Quan

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTROL PLANE (Go)                          │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Scheduler     │  Resource Mgr   │       API Gateway          │
│   (Go/gRPC)    │   (Go/Etcd)     │      (Go/mTLS)             │
└─────────────────┴─────────────────┴─────────────────────────────┘
                              │
                    ┌─────────────────┐
                    │   MESSAGE BUS   │  
                    │  (NATS/Redis)   │
                    └─────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     DATA PLANE (C++/CUDA)                      │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  GPU Executor   │  CUDA Kernels   │    Memory Manager           │
│  (C++/Streams)  │ (CUDA Graphs)   │   (Zero-Copy/Pinned)        │
└─────────────────┴─────────────────┴─────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│              ORCHESTRATION SDK (TypeScript)                    │
├─────────────────┬─────────────────┬─────────────────────────────┤
│    CLI Tools    │   Monitoring    │       Config Mgmt           │
│  (Node.js/TS)   │ (Prometheus)    │      (YAML/JSON)            │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## 🎯 Mục Tiêu Hiệu Năng

- **Latency**: P95 ↓ ≥ 30% (target: <50ms)
- **GPU Utilization**: ↑ ≥ 20% (target: >90%)
- **Throughput**: Scale tuyến tính theo GPU count
- **Reliability**: 99.9% uptime, zero race conditions

## 🔧 Công Nghệ Stack

### Control Plane (Go)
- **Scheduler**: gRPC + Backpressure + QoS
- **Resource Manager**: Etcd + TTL leases + SSOT
- **API Gateway**: mTLS + JWT + rate limiting

### Data Plane (C++/CUDA)
- **GPU Executor**: CUDA Streams + Graphs + Zero-Copy
- **Memory Manager**: Pinned memory pools + coalesced access
- **Kernel Optimization**: Double buffering + occupancy tuning

### Message Bus (NATS/Redis)
- **Event Streaming**: NATS JetStream với persistence
- **Schema**: Protobuf + versioning + validation
- **Backpressure**: Consumer groups + flow control

### Orchestration (TypeScript)
- **CLI**: Configuration management + deployment
- **Monitoring**: OpenTelemetry + Prometheus + Grafana
- **Testing**: Unit + integration + performance benchmarks

## 📊 Observability

### Metrics (Prometheus)
- `gpu_utilization_percent{gpu_id}`
- `kernel_launch_latency_ms{operation}`  
- `memory_copy_bandwidth_gbps{direction}`
- `queue_depth{queue_name}`

### Tracing (OpenTelemetry)
- End-to-end request tracing
- NVTX markers in CUDA kernels
- GPU timeline correlation

### Logging (Structured)
- JSON format với correlation IDs
- Error budgets + SLI/SLO tracking
- Security audit trail

## 🔒 Security

- **Zero Trust**: mTLS for all inter-service communication
- **RBAC**: OPA policies + JWT claims
- **SBOM**: Syft + Grype vulnerability scanning
- **SAST/DAST**: Integrated in CI pipeline

## 🚀 Quick Start

```bash
# Build all components
make build-all

# Start infrastructure
docker-compose up -d

# Deploy GPU workers
./deploy.sh --gpu-count 2

# Run benchmark
make benchmark
```

## 📁 Repository Structure

```
app-gpu/
├── control-plane/          # Go services
│   ├── scheduler/           # GPU task scheduling
│   ├── api-gateway/         # HTTP/gRPC API
│   └── resource-manager/    # Resource state management
├── data-plane/             # C++/CUDA executors
│   └── executor/           # GPU kernel execution
├── common/                 # Shared libraries
│   ├── nats-lite/         # Lightweight NATS client
│   └── job-core/          # Job abstractions
├── tooling/               # TypeScript SDK
│   └── ts-sdk/            # CLI tools & monitoring
└── docs/                  # Documentation
```

## 🧪 Testing Strategy

- **Unit Tests**: 90%+ coverage per module
- **Integration Tests**: End-to-end workflows
- **Performance Tests**: Micro-benchmarks + soak tests
- **Chaos Engineering**: GPU failure simulation

---

**Status**: 🚧 In Development  
**License**: Proprietary  
**Maintainer**: Opus GPU Team
