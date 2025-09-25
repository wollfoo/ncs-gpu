# Opus GPU – Next-Gen Architecture

Repo này chứa kiến trúc microservice thế hệ mới cho runtime GPU với control-plane (Rust/Go) và data-plane (Rust/CUDA).

## Cấu trúc thư mục
- `control-plane/` – Scheduler Rust + API Gateway Go + policy.
- `data-plane/` – Executor Rust, thư mục `kernels/` cho CUDA, `telemetry-agent/` cho daemon quan trắc.
- `orchestration/` – Helm chart và Terraform IaC.
- `tooling/` – SDK TypeScript và script tự động.
- `security/` – SBOM, policy Zero Trust, threat modeling.
- `tests/` – bộ kiểm thử unit, integration, performance.
- `docs/` – Kiến trúc, runbook vận hành, tài liệu tuân thủ.

## Yêu cầu build
- Rust 1.76+, Go 1.22+, Node.js 20 LTS.
- Docker với NVIDIA Container Toolkit khi build executor.

## Lộ trình
Xem `docs/architecture.md` và `docs/runbook/` để theo dõi lộ trình triển khai.
