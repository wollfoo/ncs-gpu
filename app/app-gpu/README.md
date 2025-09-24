# app-gpu

Hệ thống khai thác GPU được tái cấu trúc theo hướng Microservices + Clean/Hexagonal Architecture, đáp ứng yêu cầu batching, pipeline song song và vận hành SRE.

## Thành phần chính

- `src/appgpu`: Core domain theo DDD/CQRS, message bus hướng sự kiện và các adapter.
- `services` tách biệt bằng ngôn ngữ:
  - Python orchestration (FastAPI + asyncio pipeline).
  - Go control-plane API (quản lý SLO, health) — xem `go/cmd/controlplane`.
  - Rust inference engine (`rust/src/lib.rs`) dùng rayon + CUDA FFI stub.
  - C++ CUDA stub (`cpp/src/gpu_kernel_stub.cpp`) làm mẫu mở rộng zero-copy.
- `docs/`: báo cáo kỹ thuật, sơ đồ ASCII, dependency map, hot path.
- `tests/`: Unit + Integration + Performance với tiêu chí định lượng rõ ràng.
- `ci/github/workflows/ci.yml`: Pipeline CI/CD ma trận CPU/GPU.

## Quy trình nhanh

```bash
# Thiết lập môi trường Python
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# Chạy unit + integration
make test

# Benchmark hiệu năng batch/pipeline
make perf

# Build Go control-plane
make go-build

# Build Rust inference (ffi .so)
make rust-build

# Build stub C++ CUDA (yêu cầu nvcc hoặc clang++)
make cpp-build

# Khởi chạy toàn bộ stack bằng Docker Compose
docker compose up --build
```

## Chuẩn SLO

- p95 latency ≤ 70ms cho Hot Path.
- Throughput tối thiểu gấp 2 so với baseline, nhờ batching 32 & pipeline 3 stage.
- Availability ≥ 99.9% (SLO) với healthcheck và autoscaling guard.

## Giám sát & Bảo mật

- Orchestrator phơi bày `/metrics` với percentile (p50/p95/p99) và tổng số job xử lý, sẵn sàng cho Prometheus/Grafana.
- mTLS + JWT (OPA policy stub) tại Go control-plane.
- Feature flag + rollback guard trong orchestrator.

## Hướng dẫn di trú

1. Phân tích hiện trạng bằng báo cáo trong `docs/technical_report.md`.
2. Triển khai song song (`blue-green`) bằng Docker Compose.
3. Dùng tests + benchmark để xác nhận SLO trước khi switch traffic.
