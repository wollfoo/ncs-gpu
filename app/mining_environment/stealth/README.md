# stealth/ – Thành phần ẩn mình (stealth components)

Cấu trúc:

```text
stealth/
├─ core/
│  └─ stealth_activation_manager.py
└─ wrappers/
   └─ stealth_inference_cuda.py
```

- `core/`: lõi quản lý bật/tắt/tình trạng ẩn mình.
- `wrappers/`: lớp bọc (wrappers – tương tác gián tiếp) quanh công cụ/nhị phân bên ngoài để áp chính sách ẩn mình khi cần.

Khuyến nghị:
- Tránh phụ thuộc ngược từ core vào lớp bọc; inject giao diện.
- Nhật ký thay đổi trạng thái (state change – đổi trạng thái) nên có mức INFO kèm lý do.
