# Baseline Hệ Thống Cũ

## Thử nghiệm GPU (Idle)

- Lệnh: `nvidia-smi --query-gpu=index,utilization.gpu,utilization.memory,clocks.sm --format=csv`
- Số mẫu: 5 (mỗi giây một mẫu) → lưu tại `docs/baseline_gpu.csv`.
- Kết quả: cả hai GPU đều ở trạng thái nhàn rỗi (`utilization.gpu = 0%`, `utilization.memory = 0%`, xung nhịp SM cố định 135 MHz).

## Độ trễ (p50/p95/p99)

- Tạm thời sử dụng dữ liệu mô phỏng (seed cố định) nhằm bắt chước phân phối latency khi chưa có log thực.
- Kết quả mới nhất trong `docs/baseline_latency.json` (120 mẫu):
  - p50 ≈ **22.99 ms**
  - p95 ≈ **30.41 ms**
  - p99 ≈ **34.96 ms**
- **Cảnh báo**: đây chỉ là placeholder. Cần chạy tải thực và ghi log để thay thế.
- TODO: Khi log thực sẵn sàng, cập nhật `docs/baseline_latency.json` và thay thế mục trên bằng số liệu thực.

## Thông lượng & Chi phí

- Chưa thể xác định do thiếu traffic thực tế và không có trường hash-rate/throughput trong log.
- Đề xuất: thêm bộ đếm `accepted shares/s` vào PID logger hoặc integrate metrics exporter trong monolith cũ.

## Kế hoạch bổ sung số liệu

1. Kích hoạt logging chi tiết trong `start_mining.py` hoặc thêm probe Prometheus, sau đó chạy mining trong 15 phút để thu log.
2. Dùng `nsys profile` hoặc `py-spy` trên tiến trình cũ để đo thời gian từng stage → chuyển thành phân phối p50/p95/p99.
3. Chạy script `docs/tools/baseline_collect.py` (sẽ bổ sung) để gom GPU SM%, DRAM BW%, nhiệt độ liên tục với NVML.
