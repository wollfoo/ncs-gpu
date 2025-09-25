# Runbook: Baseline Cutover Sprint

## Mục tiêu
- Thiết lập repo, CI cơ bản, build skeleton cho scheduler/executor/API gateway.

## Quy trình
1. Cài toolchain (Rust, Go, Node.js, Docker GPU toolkit).
2. Chạy `cargo check` trong `control-plane/scheduler` và `data-plane/executor`.
3. Chạy `go test ./...` trong `control-plane/api-gateway`.
4. Sinh SBOM bằng `make sbom` (sẽ định nghĩa trong CI).

## Định nghĩa hoàn tất
- Build/test pass trên CI.
- Artefact SBOM được upload.
- README cập nhật trạng thái.
