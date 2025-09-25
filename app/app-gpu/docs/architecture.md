# Kiến trúc Tổng Quát

- Control-plane gồm `scheduler` (Rust, Axum) và `api-gateway` (Go, Gin) nói chuyện qua NATS và gRPC.
- Data-plane `executor` (Rust, async-nats) nhận job, chạy GPU kernel trong `kernels/`.
- Observability tích hợp Prometheus/OpenTelemetry được cấu hình trong `orchestration/charts`.
- Bảo mật: mọi dịch vụ yêu cầu mTLS, policy đặt trong `control-plane/policy` và `security/policies`.

## Roadmap Sprint 1 (Baseline Cutover)
1. Hoàn thiện skeleton build/test.
2. Cài CICD kiểm thử Rust/Go/Node.
3. Nhập cấu hình mẫu Terraform + Helm.
