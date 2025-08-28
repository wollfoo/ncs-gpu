# stealth/wrappers/ – Lớp bọc suy luận CUDA

- `stealth_inference_cuda.py`: lớp bọc cho `inference-cuda` nhằm cấy hook/điều phối trước khi chuyển quyền điều khiển cho nhị phân nền.

Lưu ý:
- Không thay đổi tham số/luồng chuẩn của công cụ trừ khi có cờ cấu hình rõ ràng.
- Nhật ký đầu/cuối (pre/post) để dễ truy vết lỗi.
