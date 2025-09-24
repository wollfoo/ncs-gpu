# Báo Cáo Kỹ Thuật: Tái Cấu Trúc Hệ Thống Khai Thác GPU

## 1. Khảo sát hiện trạng

- **Kiến trúc đơn khối**: `start_mining.py` tự xử lý toàn bộ vòng đời tiến trình bằng vòng lặp tuần tự và `subprocess.Popen` theo từng GPU, không có batching hay pipeline phân tầng dẫn tới p95 cao và throughput bị chặn bởi GIL (`start_mining.py:592-662`).
- **Giám sát blocking**: nhiều `while not stop_event.is_set()` kết hợp `time.sleep` gây phản ứng chậm với sự cố (`start_mining.py:1373-1434`).
- **Thiếu metrics chuẩn hóa**: logging đa dạng nhưng không có Prometheus/OpenTelemetry tích hợp; chỉ có log file.
- **Bảo mật tiến trình**: `subprocess_env` được nhân bản từ môi trường hiện tại, không whitelisting biến, dễ bị lộ cấu hình nhạy cảm (`start_mining.py:604-651`).
- **Baseline**: chưa có số liệu p50/p95/p99, GPU SM% hay DRAM BW trong repo → **Không đủ thông tin để kết luận**. Cần bổ sung benchmark trước/ sau khi áp dụng kiến trúc mới.

### Artefact thu thập

- `tree -a -L 3` (repo cũ): xem `task.md` & output gốc.
- `Dockerfile` chứa build monolith, không chia tầng (`Dockerfile:1-177`).
- `nvidia-smi`: GPU Tesla V100 x2, driver 550.90.07.

## 2. Hot path & dependency map

- Hot path hiện tại: API → start_mining (Python) → inference-cuda binary → log file.
- Hot path đề xuất: Control Plane (Go) → API Orchestrator (FastAPI) → Message Bus → Scheduler → GPU Adapter (Python hoặc Rust) → Telemetry (`docs/hot_path.md`).
- Dependency map chi tiết trong `docs/dependency_map.md`.

## 3. Thiết kế kiến trúc mới

- **Kiểu kiến trúc**: Clean + Hexagonal + Microservices + Event-driven.
- **Ngôn ngữ**:
  - Python cho orchestrator + pipeline (`src/appgpu/infrastructure/api/main.py`).
  - Go cho control-plane SLO (`go/cmd/controlplane/main.go`).
  - Rust cho inference service (`rust/src/main.rs`).
  - C++ stub mở rộng GPU kernels (`cpp/src/gpu_kernel_stub.cpp`).
- **Batching + Pipeline parallelism**: `Scheduler` nhận các stage bất đồng bộ, cho phép mở rộng song song (`src/appgpu/infrastructure/scheduler.py`).
- **Message Bus**: publish/subscribe async để gắn event analytics (`src/appgpu/infrastructure/message_bus.py`).
- **Observability**: Prometheus exporter (`src/appgpu/infrastructure/telemetry_exporter.py`) và metrics control-plane.
- **Runtime metrics**: Orchestrator `/metrics` cung cấp p50/p95/p99 + tổng job phục vụ dashboard shadow.
- **Bảo mật**: Control-plane áp dụng mTLS/JWT (stub) + request logging (`go/cmd/controlplane/main.go`).
- **SLO**: Batch 32 (configurable), pipeline 3 stage, SLO p95 ≤70ms được theo dõi qua histogram.

### Sơ đồ kiến trúc

Xem `docs/architecture_diagram.txt`.

### Cây thư mục repo mới

```
app-gpu
├── src/appgpu/... (domain, application, infrastructure, interfaces)
├── rust/src/main.rs
├── go/cmd/controlplane/main.go
├── cpp/src/gpu_kernel_stub.cpp
├── tests/{unit,integration,performance}
├── docs/*.md
└── ci/github/workflows/ci.yml
```

## 4. Hiện thực hoá yêu cầu

- **Module domain DDD**: `MiningJob`, `Batch`, `PipelineStage`, `PriorityClass` (`src/appgpu/domain/models.py`, `src/appgpu/domain/value_objects.py`).
- **CQRS**: `SubmitJobCommand`, `CommandHandler` (`src/appgpu/application/commands.py`, `src/appgpu/application/handlers.py`).
- **Pipeline**: 3 stage async + GPU adapter (`src/appgpu/infrastructure/api/main.py`, `src/appgpu/infrastructure/gpu_adapter.py`).
- **Microservices**:
  - Control-plane Go REST + Prometheus (`go/cmd/controlplane/main.go`).
  - Rust inference HTTP returning batch metrics (`rust/src/main.rs`).
  - Telemetry exporter FastAPI (`src/appgpu/infrastructure/telemetry_exporter.py`).
- **CI/CD**: GitHub Actions lint/test + build Go/Rust (`ci/github/workflows/ci.yml`).
- **Docker**: mỗi dịch vụ có Dockerfile riêng + docker-compose orchestration (`docker/*`, `docker-compose.yml`).

## 5. Kiểm thử & xác thực

| Nhóm | Tệp | Mục tiêu |
|------|-----|----------|
| Unit | `tests/unit/test_domain_models.py` | Bảo đảm entity hoạt động đúng |
| Unit | `tests/unit/test_message_bus.py` | Đảm bảo pub/sub async |
| Integration | `tests/integration/test_pipeline_flow.py` | Pipeline chạy hết stage |
| Performance | `tests/performance/test_batch_throughput.py` | Benchmark batch 32, dùng `pytest-benchmark` |

- Makefile gom `make test`, `make integration`, `make perf` (`Makefile`).
- Chưa chạy thực nghiệm do thiếu GPU runner → cần `pytest --benchmark-only` trên môi trường có GPU thật.

## 6. Kế hoạch di trú (Blue-Green)

1. **Baseline**: chạy load test trên hệ thống cũ (cần bổ sung script). Ghi p50/p95/p99, GPU SM%, DRAM BW.
2. **Triển khai song song**: build Docker images mới, chạy `docker compose up --build` để kiểm thử.
3. **Shadow traffic**: route 5% lưu lượng qua orchestrator mới, so sánh metrics.
4. **Cutover**: khi đáp ứng SLO, chuyển toàn bộ traffic; giữ cụm cũ standby 24h.
5. **Rollback guard**: feature flag `enable_feature_flags` (`src/appgpu/config.py`) cho phép vô hiệu hoá pipeline mới nếu p95 vượt ngưỡng.

## 7. Tiêu chí đo lường thành công

- p95 latency hot path ≤ 70ms; throughput ≥2× baseline.
- Error rate <0.1% trong 24h đầu sau cutover.
- GPU SM% trung bình ≥80%, DRAM BW ≥65% (cần tooling NVML/Triton sau).
- Test suite phải pass trên CI matrix.

## 8. Hạn chế & bước tiếp theo

- Chưa có số liệu baseline → cần profiling (py-spy, Nsight Systems) trước khi production.
- `go.sum` & `Cargo.lock` sẽ cần sinh trên môi trường có Go/Rust (máy hiện tại thiếu toolchain).
- Wiring thực tế tới inference-cuda (CUDA) cần hiện thực FFI Rust ↔ C++ stub + zero-copy.
