# KIẾN TRÚC HỆ THỐNG – GPU MINING SYSTEM V2

## Tổng quan

Hệ thống được thiết kế theo **[Coordinator-Worker Pattern]** (Mẫu điều phối-worker – kiến trúc phân tán) với các thành phần:

- **Coordinator**: Điều phối tác vụ, quản lý workers, health monitoring
- **Workers**: Thực thi GPU workloads, báo cáo metrics
- **CUDA Kernels**: Tính toán GPU thực tế (AI training, image processing, etc.)

## Sơ đồ luồng dữ liệu

```
┌─────────┐
│  Client │
│  (CLI)  │
└────┬────┘
     │ gRPC: SubmitTask
     ▼
┌────────────────┐
│  Coordinator   │
│  - Scheduler   │◄───────┐
│  - Registry    │        │ Heartbeat (10s)
└────┬───────────┘        │
     │ gRPC: AssignTask   │
     ▼                    │
┌────────────────┐        │
│    Worker      │────────┘
│  - Executor    │
│  - Monitor     │
└────┬───────────┘
     │ FFI call
     ▼
┌────────────────┐
│ CUDA Kernels   │
│  libgpu*.so    │
└────────────────┘
```

## Module boundaries

### 1. Common (`crates/common`)

**Trách nhiệm**: Shared types, errors, workload definitions

**Exports**:
- `WorkerId`, `TaskId`, `GpuDevice`: Identity types
- `WorkloadType`, `WorkloadConfig`, `WorkloadResult`: Workload abstractions
- `GpuError`, `Result<T>`: Error handling

**Dependencies**: None (pure types)

---

### 2. Coordinator (`crates/coordinator`)

**Trách nhiệm**: Task orchestration, worker management, gRPC server

**Modules**:
- `scheduler`: Task queue + assignment logic
- `worker_registry`: Worker registration + health tracking
- `server`: gRPC service implementation
- `config`: Configuration loading

**Dependencies**:
- `gpu-common`
- `tokio` (async runtime)
- `tonic` (gRPC)
- `dashmap` (concurrent hashmap)

**Protocols**:
- gRPC API: `SubmitTask`, `GetTaskStatus`, `ListWorkers`
- Internal: `mpsc` channels for dispatch loop

---

### 3. Worker (`crates/worker`)

**Trách nhiệm**: Execute GPU workloads, report metrics, heartbeat

**Modules**:
- `executor`: Workload execution + CUDA FFI calls
- `gpu_monitor`: NVML wrapper for GPU telemetry
- `main`: Worker lifecycle (register, poll, execute, report)

**Dependencies**:
- `gpu-common`
- `nvml-wrapper` (GPU monitoring)
- `tokio` (async runtime)
- CUDA kernels via FFI (`extern "C"`)

**Lifecycle**:
1. **Register**: Gửi GPU device info tới coordinator
2. **Poll**: Lấy task từ coordinator (blocking hoặc long-polling)
3. **Execute**: Gọi CUDA kernel via FFI
4. **Report**: Gửi `WorkloadResult` về coordinator
5. **Heartbeat**: Gửi keep-alive mỗi 10s

---

### 4. CUDA Kernels (`kernels/`)

**Trách nhiệm**: GPU compute primitives

**Kernels**:
- `ai_training.cu`: GEMM, loss, backprop simulation
- `image_processing.cu`: Convolution 2D, resize, batching
- `scientific_computing.cu`: FFT, BLAS operations
- `ai_inference.cu`: Forward pass, activation functions
- `memory_pool.cu`: Custom allocator for GPU memory

**Build**: CMake + nvcc

**Linking**: Rust FFI via `extern "C"` exports

**Optimization**:
- `--use_fast_math`: Fast math operations
- `--maxrregcount=64`: Limit register usage
- Multiple CUDA streams: Overlapping compute + transfer

---

## Luồng thực thi task (Task Flow)

```
1. Client → Coordinator: SubmitTask(WorkloadConfig)
2. Coordinator → Scheduler: Enqueue task
3. Scheduler → Dispatch Loop: Poll for available worker
4. Dispatch Loop → Worker (gRPC): AssignTask(TaskId, WorkloadConfig)
5. Worker → Executor: execute_workload(config)
6. Executor → CUDA Kernel (FFI): cuda_*_kernel(...)
7. CUDA Kernel → GPU: Launch kernel on device
8. GPU → CUDA Kernel: Result
9. Executor → Worker: WorkloadResult
10. Worker → Coordinator (gRPC): ReportResult(TaskId, Result)
11. Coordinator → Scheduler: Mark task completed
12. Client ← Coordinator: GetTaskStatus() → Completed
```

---

## Cơ chế bảo mật

### 1. Isolation (Cô lập)

- **seccomp**: Whitelist syscalls (config/seccomp.json)
- **cgroups v2**: Giới hạn CPU/memory/GPU
- **AppArmor**: MAC policy cho file access
- **User namespaces**: Chạy non-root (UID 1000)

### 2. Supply Chain Security

- **SBOM**: Syft generates SPDX JSON
- **Signing**: cosign signs OCI images
- **Provenance**: SLSA attestation via GitHub Actions
- **Hermetic Builds**: Nix flakes + Cargo.lock

### 3. Obfuscation

- **Rust**: `cargo-strip --strip-all` + LTO
- **C++**: `strip -s` for kernels
- No UPX (trade-off: performance vs obfuscation)

---

## Telemetry & Observability

### Metrics (Prometheus)

- **GPU**: Utilization, memory, temperature, power
- **Tasks**: Throughput, latency (P50/P95/P99), queue depth
- **Workers**: Active count, task count, heartbeat status

**Endpoint**: `:9090/metrics`

### Logs (Structured JSON)

```json
{
  "timestamp": "2025-09-30T12:51:29Z",
  "level": "INFO",
  "target": "coordinator::scheduler",
  "message": "Task submitted",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Traces (OpenTelemetry)

- Distributed tracing qua OTLP protocol
- Span: SubmitTask → Execute → Report

---

## Performance Optimization

### 1. GPU Level

- **CUDA Streams**: 4 concurrent streams per worker
- **Memory Pooling**: Pre-allocate 2GB pool per GPU
- **Kernel Fusion**: Combine small kernels to reduce overhead

### 2. Coordinator Level

- **Lock-free**: `DashMap` for concurrent access
- **Async I/O**: tokio runtime
- **Batch Processing**: Group small tasks

### 3. Network Level

- **gRPC Streaming**: Reduce per-request overhead
- **Compression**: Enable gzip for large payloads

---

## Scalability

### Horizontal Scaling

- **Multi-worker**: 1 coordinator : N workers
- **Multi-GPU**: 1 worker : M GPUs
- **Leader Election**: Raft/etcd for multi-coordinator (future)

### Vertical Scaling

- **Multi-stream**: Increase CUDA streams
- **Larger batches**: Increase batch size (memory permitting)

---

## Testing Strategy

### 1. Unit Tests

- **Rust**: `cargo test`
- **CUDA**: CTest with mock kernels

### 2. Integration Tests

- **End-to-end**: Client → Coordinator → Worker → CUDA
- **Failure scenarios**: Worker crash, GPU OOM, network partition

### 3. Benchmarks

- **GPU**: Throughput (ops/sec), latency (P99)
- **Memory**: Peak usage, allocation count
- **Network**: gRPC latency, bandwidth

**Script**: `scripts/benchmark.sh`

---

## Deployment

### Local (Dev)

```bash
make build
./target/release/coordinator &
./target/release/worker --coordinator-addr localhost:50051
```

### Docker (Production)

```bash
docker build -t gpu-miner:latest .
docker run --gpus all \
  --security-opt seccomp=config/seccomp.json \
  --security-opt apparmor=gpu-miner \
  gpu-miner:latest
```

### Kubernetes (Future)

- **Coordinator**: Deployment (replicas=3, leader election)
- **Workers**: DaemonSet (1 pod per GPU node)
- **GPU**: NVIDIA Device Plugin

---

## Roadmap

- [ ] gRPC service implementation (proto definitions)
- [ ] Prometheus exporter integration
- [ ] OpenTelemetry tracing
- [ ] Kubernetes manifests
- [ ] AMD ROCm support (in addition to CUDA)
- [ ] Web UI dashboard (Grafana)

---

**Last Updated**: 2025-09-30  
**Version**: 2.0.0  
**Maintainer**: NTV Team
