# app-gpu

**app-gpu** là kiến trúc tái cấu trúc GPU mining runtime với lõi [Rust] (ngôn ngữ hệ thống – an toàn bộ nhớ, hiệu năng cao, song song tốt) và điều phối [Go] (đồng thời nhẹ – goroutine/channel, dev nhanh, DevOps thuận). Dự án hướng tới giảm độ trễ P99, loại bỏ trạng thái toàn cục và tăng độ an toàn.

## Build nhanh

```bash
make build
```

## Kiểm thử

```bash
make unit-test
make integration-test
make bench
```

## Cấu trúc thư mục

- `cmd/` – entrypoints ứng dụng
- `internal/` – domain core và bộ lập lịch GPU
- `pkg/` – thư viện tái sử dụng (telemetry)
- `gpu/` – kernel CUDA + binding FFI
- `api/` – định nghĩa REST/OpenAPI và gRPC
- `configs/` – cấu hình runtime & chính sách OPA
- `observability/` – [OpenTelemetry] (chuẩn quan sát – trace/metric/log)
- `security/` – cấu hình [SAST/DAST] (phân tích tĩnh/động – an ninh)
- `tests/` – gói kiểm thử đơn vị, tích hợp, hiệu năng
