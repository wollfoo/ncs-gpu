# Opus GPU – Next-Gen Architecture

Repo này chứa kiến trúc microservice thế hệ mới cho runtime GPU với control-plane (Rust/Go) và data-plane (Rust/CUDA).

## Cấu trúc thư mục
- `control-plane/` – Scheduler Rust + API Gateway Go + policy.
- `data-plane/` – Executor Rust, thư mục `kernels/` cho CUDA, `telemetry-agent/` cho daemon quan trắc.
- `data-plane/` – Executor Rust kết nối NATS (qua TCP thủ công, không phụ thuộc crate) để lấy job và ACK.
- `orchestration/` – Helm chart và Terraform IaC.
- `tooling/` – SDK TypeScript và script tự động.
- `security/` – SBOM, policy Zero Trust, threat modeling.
- `tests/` – bộ kiểm thử unit, integration, performance.
- `docs/` – Kiến trúc, runbook vận hành, tài liệu tuân thủ.

## Yêu cầu build
- Rust 1.76+, Go 1.22+, Node.js 20 LTS.
- Docker với NVIDIA Container Toolkit khi build executor.
- NATS server mặc định `nats://127.0.0.1:4222`; có thể đổi qua biến môi trường `NATS_URL`, `EXECUTOR_SUBJECT`, `EXECUTOR_ACK_SUBJECT`, `EXECUTOR_QUEUE_GROUP`.
- Đặt `NATS_AUTH_TOKEN` nếu NATS yêu cầu Bearer token; scheduler và executor sẽ chuyển tiếp token vào frame `CONNECT`.
- HTTP API của scheduler hỗ trợ Bearer token qua `SCHEDULER_BEARER_TOKEN`.
- Metrics Prometheus:
  - Scheduler: `SCHEDULER_METRICS_ADDR` (mặc định `0.0.0.0:9100`).
  - Executor: `EXECUTOR_METRICS_ADDR` (mặc định `0.0.0.0:9200`).

## Lộ trình
Xem `docs/architecture.md` và `docs/runbook/` để theo dõi lộ trình triển khai.
