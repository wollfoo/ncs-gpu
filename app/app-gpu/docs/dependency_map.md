# Dependency Map (Bản đồ phụ thuộc)

## Python Core (`appgpu`)

- `domain` (không phụ thuộc xuống hạ tầng).
- `application` chỉ dùng `domain`.
- `infrastructure`
  - `message_bus` (asyncio chuẩn).
  - `scheduler` phụ thuộc `domain` events + callbacks.
  - `gpu_adapter` phụ thuộc `numpy`, tùy chọn `httpx`.
  - `api.main` phụ thuộc `fastapi`, `application`, `infrastructure`.

## Go Control Plane

- Module `github.com/go-chi/chi/v5`
- `github.com/prometheus/client_golang`

## Rust Inference

- `axum`, `tokio`, `serde`, `rand`.
- Tương lai: bind sang C++ `gpu_kernel_stub` qua FFI.

## C++ Stub

- Không phụ thuộc ngoài chuẩn C++20.

## Observability / Tooling

- Prometheus client (Python + Go).
- OpenTelemetry API hook sẵn trong orchestrator (tích hợp sau).
