# Opus GPU Mining System v2

**[GPU Mining System]** (Hệ thống khai thác GPU – mô phỏng tải tính toán) được thiết kế lại hoàn toàn với kiến trúc mô-đun, hiệu năng cao, và bảo mật.

## Kiến trúc

- **[Rust]** (ngôn ngữ hệ thống – an toàn bộ nhớ): Orchestrator, API, workers
- **[C++/CUDA]** (CUDA gốc – hiệu năng tối đa): GPU kernels cho AI training, image processing, inference
- **[gRPC]** (RPC hiệu quả): Communication protocol
- **[Prometheus]** (thu thập metrics): Telemetry
- **[seccomp/cgroups]** (cô lập – bảo mật): Security isolation

## Tính năng

✅ **[Modular Architecture]** (Kiến trúc mô-đun – tách biệt rõ ràng)  
✅ **[Distributed Support]** (Hỗ trợ phân tán – multi-node coordination)  
✅ **[GPU Optimization]** (Tối ưu GPU – CUDA streams, memory pooling)  
✅ **[Security Hardening]** (Bảo mật cứng – seccomp, cgroups, AppArmor)  
✅ **[Observability]** (Quan sát – Prometheus metrics, structured logs)  
✅ **[Reproducible Builds]** (Build tái lập – Nix flakes, Cargo lock)

## Workloads mô phỏng

- **[AI Training]** (Huấn luyện AI – GEMM, loss, backprop)
- **[Image Processing]** (Xử lý ảnh – convolution, resize, batching)
- **[Scientific Computing]** (Tính toán khoa học – FFT, BLAS)
- **[AI Inference]** (Suy luận AI – activation, latency-optimized)

## Cài đặt

### Prerequisites

```bash
# Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# CUDA Toolkit 12.0+
# https://developer.nvidia.com/cuda-downloads

# CMake, build-essential
sudo apt install cmake build-essential pkg-config
```

### Build

```bash
# Build toàn bộ project
make build

# Hoặc manual:
cargo build --release
cd kernels && cmake -B build && cmake --build build --config Release
```

### Run

```bash
# Chạy coordinator
./target/release/coordinator --config config/default.toml

# Chạy worker
./target/release/worker --coordinator-addr localhost:50051

# CLI tool
./target/release/gpu-miner --help
```

### Docker

```bash
# Build image
docker build -t gpu-miner:latest .

# Run với GPU
docker run --gpus all \
  --security-opt seccomp=config/seccomp.json \
  --security-opt apparmor=gpu-miner \
  -e RUST_LOG=info \
  gpu-miner:latest
```

## Development

```bash
# Run tests
make test

# Run benchmarks
make benchmark

# Lint & format
make lint
make fmt

# Dev container (Nix)
nix develop
```

## Security

- **[Least Privilege]** (Đặc quyền tối thiểu): Chạy non-root (UID 1000)
- **[seccomp]** (lọc syscall): Whitelist system calls
- **[cgroups v2]** (giới hạn tài nguyên): CPU/Memory/GPU isolation
- **[AppArmor]** (MAC policy): Mandatory access control

## Metrics

- **GPU utilization** (sử dụng GPU): NVML-based
- **Throughput** (thông lượng): Tasks/sec
- **Latency** (độ trễ): P50/P95/P99
- **Memory** (bộ nhớ): Heap/GPU allocations

Exposed via Prometheus on `:9090/metrics`

## License

Proprietary - NTV.com.vn

## Contributors

System redesigned theo chuẩn **[SLSA Level 3]** (chuỗi cung ứng an toàn – mức độ 3).
