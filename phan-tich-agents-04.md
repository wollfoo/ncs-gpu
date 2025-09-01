### Báo cáo điều tra tụt hash mining gpu – và đề xuất giải pháp 


Cập nhật: 2025-09-01T08:45:25Z

---

## 1) Bối cảnh & Mục tiêu

- __[Bối cảnh]__ Sau nhiều lần dừng/chạy lại (restart) mining, hashrate quan sát được giảm so với mức trước đó.
- __[Mục tiêu]__ Xác định __Root cause__ (nguyên nhân gốc rễ – vì sao tụt hash) và đề xuất __Refactor tối thiểu__ (tái cấu trúc tối thiểu – biện pháp khắc phục an toàn) theo ràng buộc: không đổi cấu trúc thư mục, không đưa code, chỉ mô tả giải pháp bằng lời.

---

## 2) Thành phần chính liên quan (Components – các thành phần)

- `app/mining_environment/scripts/resource_control.py`
  - `GPUResourceManager.restore_gpu_settings_for_pid(pid)` (__Restore__ – khôi phục): dùng __NVML__ (thư viện quản lý NVIDIA – NVML) `nvmlDeviceResetApplicationsClocks` để reset __application clocks__ (xung ứng dụng – phạm vi __device-wide__ trên GPU mục tiêu), sau đó khôi phục `power limit`/`clocks` từ trạng thái đã lưu theo __PID__ (mã tiến trình – per-PID orchestration).
  - `OptimizedHardwareController._schedule_restore(pid, gpu_index, window_sec, cancel_event)` (__Schedule Restore__ – lập lịch khôi phục): thiết lập hẹn giờ có thể hủy (__cancelable__) với khóa `(pid, gpu_index)`, chờ `window_sec`, có __final guard__ (bảo vệ cuối) kiểm tra hủy trước khi thực thi.
  - `_cancel_pending_restores_for_gpu(gpu_index, except_key)` (__Cross-PID cancel__ – hủy chéo giữa PID theo GPU): chủ động hủy mọi restore pending khác trên cùng `gpu_index` ngoại trừ khóa hiện tại; điều khiển bởi `CANCEL_CROSS_PID_RESTORE_BY_GPU` (mặc định=1).
  - `GPUResourceManager.verify_clock_lock_conditions()` (__Clock lock verification__ – xác minh trước khi khóa xung): parse `pid_gpu.log` (định dạng JSON + raw), __normalize units__ (chuẩn hóa đơn vị H/s, kH/s, MH/s, …), tính % tăng hashrate trong cửa sổ thời gian, kiểm tra nhiệt độ so với `CLOCK_LOCK_TEMP_MAX`. Được tích hợp vào `set_target_utilization()` để chỉ khóa clocks khi điều kiện đạt.

- __Mặc định môi trường (Env defaults – biến môi trường mặc định)__
  - Theo `setup_env.py`: `LOGS_DIR`, `CLOCK_LOCK_VERIFY_WINDOW_SEC=60`, `CLOCK_LOCK_TEMP_MAX=70`, `CLOCK_LOCK_MIN_INCREASE_PCT=5`, `ALLOW_CLOCK_LOCK=1`.
  - Theo triển khai hủy cross-PID: `CANCEL_CROSS_PID_RESTORE_BY_GPU=1` (bật theo mặc định).

---

## 3) Bằng chứng log & dòng thời gian (Evidence & Timeline – chuỗi sự kiện)

- __Hướng dẫn trích xuất (không bịa đặt)__:
  - Trích dẫn verbatim (nguyên văn) từ log thực tế của môi trường bạn, không suy diễn.
  - Nguồn log cần thiết:
    - `app/mining_environment/logs/optimizedhardwarecontroller.log` (schedule/cancel/restore theo PID×GPU)
    - `app/mining_environment/logs/gpu_optimization.log` và `app/mining_debug.log` (quyết định verify/lock, target utilization)
    - `app/mining_environment/logs/gpu_miner.log` (diễn biến MH/s quanh sự kiện)
  - Khuôn mẫu điền dữ liệu (placeholder) — thay [ts]/[PID]/[GPU]/[...] bằng số liệu thực tế, rồi xóa placeholder:
    > [ts] optimizedhardwarecontroller.log — Restoring GPU settings... (PID=[...], GPU=[...])
    > [ts] optimizedhardwarecontroller.log — Restore canceled (PID=[...], GPU=[...])
    > [ts] gpu_optimization.log — verify_window=[...], min_increase_pct=[...], decision=[lock|skip]
    > [ts] gpu_miner.log — speed 10s/60s/15m [...]/[...]/[...] MH/s (GPU=[...])
  - Ghi chú: Chỉ kết luận sau khi đã điền dữ liệu thực tế và đối chiếu đủ cửa sổ thời gian (ví dụ ±2–3 phút quanh sự kiện restore/lock).

---

## 4) Kết luận kỹ thuật trọng yếu (Key Findings – phát hiện chính)

- __Orchestrate per-PID, effect device-wide__ (điều phối theo PID nhưng hiệu ứng ở cấp thiết bị):
  - Dữ liệu trạng thái lưu theo `pid` nhưng `nvmlDeviceResetApplicationsClocks` và `power limit` là thiết lập __device-wide__ trên GPU; có thể ảnh hưởng tiến trình khác trên cùng GPU.

- __Cross-PID cancellation hoạt động (theo thiết kế và cấu hình mặc định)__:
  - Cần xác thực bằng log thực tế ở môi trường triển khai để đánh giá mức độ tránh "restore muộn".

- __Lock clocks theo verify window__ (khóa xung dựa vào cửa sổ xác minh):
  - Cửa sổ ngắn có thể gây dương giả nếu hashrate dao động mạnh hoặc nhiệt độ/điện chưa ổn định.

- __Power dwell/step__ (trì hoãn/giới hạn bước công suất):
  - Bảo vệ ổn định điện nhưng có thể làm chậm phục hồi hashrate sau các lần reset/restore.

---

## 5) Giả thuyết nguyên nhân tụt hashrate (Root-cause hypotheses)

- __[H1] Restore muộn từ PID cũ__ (late restore – khôi phục muộn):
  - Dù có hủy cross-PID, vẫn có khả năng một đợt restore về sau rơi đúng lúc phiên mới đang tăng hiệu suất → tạm thời reset device-wide.

- __[H2] Clock lock sai ngữ cảnh__ (mis-timed lock – khóa sai thời điểm):
  - Cửa sổ xác minh quá ngắn hoặc ngưỡng tăng thấp → khóa clocks tại mặt bằng chưa bền vững, tạo plateau thấp.

- __[H3] Power dwell/step gây trễ__ (lag due to power control):
  - Thay đổi công suất bị kìm/nhảy bậc khiến hashrate phục hồi chậm sau các sự kiện reset/restore.

---

## 6) Giải pháp đề xuất tối thiểu (Minimal refactors – không đưa code)

- __[R1] Post-restore baseline check__ (kiểm tra đường cơ sở sau khôi phục):
  - Sau mỗi restore, kiểm chứng nhanh rằng clocks/power ≥ baseline kỳ vọng; nếu thấp, ghi cảnh báo và đánh dấu __needs re-tune__ (cần tối ưu lại) thay vì để hệ thống chạy ở plateau thấp.

- __[R2] Tăng cường cross-PID cancellation + logging__:
  - Khi lập lịch restore mới, tiếp tục hủy mọi pending khác cùng GPU (đã làm) và __log tương quan PID↔GPU__ (correlation-id) rõ ràng để dựng lại timeline dễ dàng.

- __[R3] Hardening clock-lock verification__ (làm chặt xác minh khóa clocks):
  - Điều chỉnh `CLOCK_LOCK_VERIFY_WINDOW_SEC` (ví dụ +30s đến +60s tùy GPU) và `CLOCK_LOCK_MIN_INCREASE_PCT` (tăng 2–3 điểm) để giảm dương giả.
  - Thêm điều kiện __temperature ceiling__ (trần nhiệt động): hoãn lock nếu nhiệt gần ngưỡng `CLOCK_LOCK_TEMP_MAX`.

- __[R4] Observability nâng cao__ (nâng khả năng quan sát):
  - Gắn __correlation-id__ (mã tương quan – PID/GPU/timestamp) xuyên suốt: schedule → cancel → restore → lock → sample MH/s.
  - Đảm bảo dòng METRICS trong `gpu_miner.log` luôn có GPU index nhất quán để dựng biểu đồ PID×GPU.

- __[R5] Giữ an toàn theo defaults__:
  - Duy trì `CANCEL_CROSS_PID_RESTORE_BY_GPU=1` (opt-out khi cần test).
  - Tận dụng defaults đã được tập trung ở `setup_env.py` (không rải rác shell).

---

## 7) Kế hoạch kiểm chứng (Verification/A-B plan)

- __Thiết kế A/B__ (controlled experiment – thí nghiệm có kiểm soát):
  - Nhánh A: cấu hình hiện tại.
  - Nhánh B: tăng `CLOCK_LOCK_VERIFY_WINDOW_SEC` (ví dụ 90s), tăng `CLOCK_LOCK_MIN_INCREASE_PCT` (ví dụ +2–3 điểm), giữ `CANCEL_CROSS_PID_RESTORE_BY_GPU=1`.

- __Quan trắc 20–30 phút__ (monitoring):
  - Tỷ lệ sự kiện restore/cancel rơi vào giai đoạn MH/s đang tăng.
  - Plateau MH/s và phương sai trước/sau lock.
  - Số lần power change bị dwell/step và độ trễ phục hồi MH/s.

- __Tiêu chí thành công__:
  - Giảm tụt MH/s sát sự kiện restore/lock.
  - Plateau cao hơn hoặc ổn định hơn (độ lệch chuẩn thấp).
  - Nhiệt/điện giữ trong ngưỡng, không tăng cảnh báo.

---

## 8) Hướng dẫn phân tích log (Operational guidance – thao tác thực địa)

- __Chuỗi cần trích__:
  - `optimizedhardwarecontroller.log`: cụm schedule/cancel/restore theo PID×GPU (ví dụ 07:16–07:20).
  - `gpu_optimization.log` và `app/mining_debug.log`: quyết định lock/verify, target utilization.
  - `gpu_miner.log`: MH/s trong khung ±2–3 phút quanh sự kiện restore/lock.

- __Mẹo thực thi__ (không code):
  - Dùng từ khóa: "Restoring GPU settings", "Restore canceled", "lock", "verify", "MH/s".
  - Lập bảng thời gian: cột [ts | PID | GPU | action | MH/s (t-120s → t+180s)].

---

## 9) Phụ lục (Appendix)

- __Đường dẫn quan trọng__:
  - `app/mining_environment/scripts/resource_control.py`
  - `app/mining_environment/logs/optimizedhardwarecontroller.log`
  - `app/mining_environment/logs/gpu_miner.log`
  - `app/mining_debug.log`

- __Hàm/Lớp liên quan__:
  - `GPUResourceManager.restore_gpu_settings_for_pid()`
  - `OptimizedHardwareController._schedule_restore()`
  - `OptimizedHardwareController._cancel_pending_restores_for_gpu()`
  - `GPUResourceManager.verify_clock_lock_conditions()`
  - `OptimizedHardwareController.set_target_utilization()` (điểm tích hợp verify & lock)

- __Biến môi trường (Env) chủ chốt__:
  - `ALLOW_CLOCK_LOCK=1` (bật khóa clocks khi verify đạt)
  - `CLOCK_LOCK_VERIFY_WINDOW_SEC=60` (cửa sổ xác minh)
  - `CLOCK_LOCK_TEMP_MAX=70` (trần nhiệt độ)
  - `CLOCK_LOCK_MIN_INCREASE_PCT=5` (mức tăng tối thiểu)
  - `CANCEL_CROSS_PID_RESTORE_BY_GPU=1` (hủy cross-PID theo GPU)
  - `LOGS_DIR`

---

## 10) Tóm tắt ngắn (Executive summary – tóm lược)

- Restore được điều phối theo PID; hành động NVML reset application clocks và điều khiển power có hiệu lực device-wide trên GPU mục tiêu.
- Cơ chế cross-PID cancellation đã được triển khai và bật mặc định theo code/config; cần xác nhận hiệu quả bằng log thực tế.
- Cần thu thập và đối chiếu log thực tế để xác nhận mối tương quan giữa restore/lock và biến thiên MH/s trước khi kết luận.
- Khuyến nghị áp dụng post-restore baseline check, làm chặt clock-lock verification và tăng observability như ở mục 6.
