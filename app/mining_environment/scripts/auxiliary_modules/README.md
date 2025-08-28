# auxiliary_modules/ – Models & Interfaces

- `interfaces.py`: giao diện/khế ước (interfaces/contracts – định nghĩa ràng buộc) giữa chiến lược, provider và điều phối.
- `models.py`: kiểu dữ liệu (dataclasses/models – mô hình dữ liệu) lưu trạng thái và cấu hình.

Quy ước:
- Dùng `typing.Protocol` hoặc ABC khi thích hợp.
- Dùng `dataclasses`/`pydantic` (nếu có) kèm type hints đầy đủ.
- Docstring ngắn cho từng lớp/phương thức public.
