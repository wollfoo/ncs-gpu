# Kiến trúc Tổng Quát

- Control-plane gồm `scheduler` (Rust, Axum) và `api-gateway` (Go, Gin) nói chuyện qua NATS và gRPC.
- Scheduler cung cấp `POST /jobs`, bọc payload JSON, phát tới NATS bằng client TCP nội bộ và yêu cầu Bearer token nếu đặt `SCHEDULER_BEARER_TOKEN`.
- Data-plane `executor` (Rust) kết nối tới **[NATS]** (message queue – phân phối sự kiện) bằng lightweight client tự viết (TCP + protocol text) để nhận job, mô phỏng GPU work và gửi ACK.
- Observability tích hợp Prometheus/OpenTelemetry được cấu hình trong `orchestration/charts`.
- Bảo mật: mọi dịch vụ yêu cầu mTLS, policy đặt trong `control-plane/policy` và `security/policies`.
- Prometheus metrics:
  - Scheduler đếm job nhận/đăng, payload bytes, trạng thái unauthorized trên cổng `SCHEDULER_METRICS_ADDR` (mặc định `9100`).
  - Executor theo dõi job nhận/hoàn tất, lỗi deserialize/ack và latency xử lý trên `EXECUTOR_METRICS_ADDR` (mặc định `9200`).

## Roadmap Sprint 1 (Baseline Cutover)
1. Hoàn thiện skeleton build/test.
2. Cài CICD kiểm thử Rust/Go/Node.
3. Nhập cấu hình mẫu Terraform + Helm.

## Phase 2 – Queue & Security Hardening
- Refactor scheduler → NATS publish flow, shared `nats-lite` crate, optional `NATS_AUTH_TOKEN` cho Bearer auth.
- HTTP Bearer token (`SCHEDULER_BEARER_TOKEN`) bảo vệ `/jobs`.
- `tooling/scripts/bench_scheduler.sh` gửi tải song song để kiểm tra throughput.

## Phase 3 – Observability & Performance
- Tích hợp `metrics-exporter-prometheus` cho scheduler/executor, expose metrics HTTP listener.
- Đo lường job latency (executor) và kích thước payload (scheduler) phục vụ benchmark.
