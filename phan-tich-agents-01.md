áp dụng Refactor code theo phương án đề xuất 

### Refactor đề xuất 
- Thêm logic reset tất cả về trạng thái bình thường  của GPU loại bỏ khóa xung/điện, nhiệt vv.. vào module `setup_env.py` trước khi chức năng GPU optimization được kích hoạt 
- [Guard trước khi khóa xung] (bộ bảo vệ – chỉ khóa khi đã có mục tiêu cao):
  - Trong `resource_control.py` → `set_gpu_clocks`:
    - Thêm kiểm tra ENV `ALLOW_CLOCK_LOCK=1` mới cho phép lock; mặc định không lock trong giai đoạn khởi động.
    - Nếu hiện tại SM clock < 800 MHz và `GPU_CLOSED_LOOP_ENABLED=0`, bỏ qua lock và log cảnh báo.
- [Mở khóa an toàn trước optimization] (pre-unlock – bước mở khóa chuẩn):
  - Tại điểm nhận PID thành công (sau `HookCoordinator`), gọi trình tự:
    - `pynvml.nvmlDeviceResetApplicationsClocks(handle)` (nếu hỗ trợ).
    - Bỏ mọi lock qua `nvidia-smi -rgc` và `--reset-memory-clocks` (best-effort).
    - Chỉ sau đó, cho phép closed-loop nâng dần power/xung theo `GPU_TARGET_UTIL`.
- [Clamp power tối thiểu] (kẹp tối thiểu công suất):
  - Trong `set_gpu_power_limit`, đã có kẹp min theo 80% nếu `ALLOW_UTIL_UNDER_80=0`. Đảm bảo biến này mặc định 0 để không hạ quá sâu.
- [Entrypoint an toàn] (khởi tạo an toàn):
  - Giữ `-rac` như hiện tại, nhưng không đặt `-pl` nếu `GPU_POWER_LIMIT_WATTS` rỗng; trường hợp test nên để rỗng để tránh áp limit thấp không phù hợp.

