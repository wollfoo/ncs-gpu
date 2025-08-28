# stealth/core/ – Quản lý kích hoạt ẩn mình

- `stealth_activation_manager.py`: quản lý vòng đời bật/tắt cơ chế ẩn mình; cung cấp điểm mở rộng để quan sát (observer – quan sát) hoặc hook.

Gợi ý:
- Bảo đảm hàm khởi tạo (initialize – khởi tạo) và dọn dẹp (cleanup – thu dọn) là idempotent (lặp lại an toàn).
- Khi chưa dùng, các hàm nên là no-op an toàn.
