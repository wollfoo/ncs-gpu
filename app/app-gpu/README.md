# Opus GPU – Next-Gen Architecture

Repo này chứa kiến trúc microservice thế hệ mới cho runtime GPU với control-plane (Rust/Go) và data-plane (Rust/CUDA).

## Cấu trúc thư mục
- `control-plane/` – Scheduler Rust, API Gateway Go và policy điều phối.
- `data-plane/` – Executor Rust, thư mục `kernels/` cho CUDA, `telemetry-agent/` cho daemon quan trắc.
- `orchestration/` – Helm chart, Terraform IaC.
- `tooling/` – SDK TypeScript và kịch bản tự động.
- `security/` – SBOM, policy Zero Trust, threat modeling.
- `tests/` – bộ kiểm thử unit, integration, performance.
- `docs/` – Kiến trúc, runbook vận hành, tài liệu tuân thủ.

## Yêu cầu build
- Rust 1.76 (được ghim trong `rust-toolchain.toml`), Go 1.22 (được khai báo trong `go.mod`), Node.js 20 LTS (ghim qua `.nvmrc`).
- Docker với NVIDIAContainer Toolkit khi build executor.
- NATS server mặc định `nats://127.0.0.1:4222`; có thể đổi qua biến môi trường `NATS_URL`, `EXECUTOR_SUBJECT`, `EXECUTOR_ACK_SUBJECT`, `EXECUTOR_QUEUE_GROUP`.
- Đặt `NATS_AUTH_TOKEN` nếu NATS yêu cầu Bearer token; scheduler và executor chuyển tiếp token vào frame `CONNECT`.
- HTTP API của scheduler hỗ trợ Bearer token qua `SCHEDULER_BEARER_TOKEN`.
- `JOB_STORE_URL` cấu hình kho trạng thái job (hỗ trợ `redis://` hoặc `memory` cho phát triển). Nếu không đặt sẽ dùng in-memory store (không bền vững).
- `GPU_KERNEL_BASE_PATH` (tùy chọn) đặt thư mục chứa binary GPU; `GPU_KERNEL_DEFAULT` xác định command mặc định (mặc định `inference-cuda`).
- Metrics Prometheus:
  - Scheduler: `SCHEDULER_METRICS_ADDR` (mặc định `0.0.0.0:9100`).
  - Executor: `EXECUTOR_METRICS_ADDR` (mặc định `0.0.0.0:9200`).

## Quy trình build/test chuẩn
1. Cài đặt toolchain theo phiên bản ghim (`rustup`, `go`, `nvm use`).
2. Chạy `make deps` để cài đặt phụ thuộc Node bằng `npm ci`.
3. Thực thi `make fmt lint test` hoặc xem GitHub Actions workflow `.github/workflows/ci.yml` để tham khảo pipeline.

## Lộ trình
Theo dõi chi tiết các phase nâng cấp production-ready tại `docs/production-ready-phases.md` và các runbook trong `docs/runbook/`.

## Quy ước phát triển
- Nhánh chính: `main` (được bảo vệ). Làm việc trên nhánh tính năng `feature/<mota-ngan>`.
- Bắt buộc mở Pull Request, tối thiểu 1 lượt review từ Platform hoặc Security khi thay đổi liên quan.
- Mọi PR phải vượt qua workflow CI, đính kèm liên kết issue và cập nhật tài liệu nếu hành vi thay đổi.
