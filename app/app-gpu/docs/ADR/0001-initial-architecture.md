# ADR 0001: Rust Core With Go Control Plane

## Bối cảnh

Repo gốc `start_mining.py` tạo kết dính mạnh giữa quản lý tài nguyên, log và khởi động tiến trình (`start_mining.py` ~1300 dòng) → khó bảo trì và khó giảm độ trễ (`📎 start_mining.py:1120–1458`). Hệ thống điều phối hiện dựa vào semaphore tệp nhưng bị bypass theo mặc định (`📎 mining_environment/scripts/cross_process_coordination.py:158–198`).

## Quyết định

- Lõi domain được viết bằng [Rust] (ngôn ngữ hệ thống – an toàn bộ nhớ, hiệu năng cao, song song tốt) để tận dụng async non-blocking và kiểm soát bộ nhớ.
- Lớp điều phối/health-check viết bằng [Go] (đồng thời nhẹ – goroutine/channel, dev nhanh, DevOps thuận) nhằm tích hợp dễ dàng với tooling vận hành.
- Tách scheduler, telemetry, GPU binding thành crate độc lập, loại bỏ `_instance` toàn cục (`📎 start_mining.py:1161–1288`).

## Hệ quả

- Kiến trúc mới giảm coupling, cho phép benchmark rõ ràng giữa luồng REST/gRPC và pipeline GPU.
- Yêu cầu quy trình build đa ngôn ngữ (Rust + Go) -> đã chuẩn hóa trong `Dockerfile` và `Makefile`.
- Thêm chi phí FFI khi gọi kernel, nhưng bù lại có thể quản lý an toàn lỗi nhị phân.

## Tình trạng

Chấp nhận.
