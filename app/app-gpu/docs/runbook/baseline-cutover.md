# Runbook: Baseline Cutover Sprint

## Mục tiêu
- Thiết lập repo, CI cơ bản, build skeleton cho scheduler/executor/API gateway.

## Quy trình
1. Cài toolchain (Rust, Go, Node.js, Docker GPU toolkit).
2. Chạy `cargo check` trong `control-plane/scheduler` và `data-plane/executor`.
3. Chạy `go test ./...` trong `control-plane/api-gateway`.
4. Sinh SBOM bằng workflow CI (`app-gpu-ci`) và lưu trữ dưới thư mục `security/sbom/` khi phát hành.
5. Khởi chạy Prometheus exporter: đảm bảo `SCHEDULER_METRICS_ADDR` và `EXECUTOR_METRICS_ADDR` hiển thị `/metrics`.
6. Thử tải nhanh: `tooling/scripts/bench_scheduler.sh 50` để xác nhận pipeline NATS.

## Định nghĩa hoàn tất
- Build/test pass trên CI.
- Artefact SBOM được upload.
- README cập nhật trạng thái.
