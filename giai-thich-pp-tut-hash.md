

# Phương pháp ngăn tụt hashrate sau restart (giải thích ngắn gọn + từng bước)

## Nguyên lý hoạt động
- __[Tránh downclock]__  
  - Khi `ALLOW_CLOCK_LOCK=0`, GPU dễ bị hạ xung SM xuống ~420–480 MHz → hashrate tụt mạnh (~11–12 MH/s).  
  - Giải pháp: bật khóa xung có điều kiện và/hoặc cưỡng bức “baseline” tối thiểu để duy trì xung/power an toàn ngay sau restart.
- __[Điều khiển phản hồi]__  
  - Dùng vòng lặp “closed-loop” (điều khiển phản hồi – đo util và điều chỉnh dần) để đưa GPU về mức tải mục tiêu ổn định, thay đổi power/clock theo bước nhỏ có “dwell” (thời gian chờ).
- __[Khôi phục đúng ngữ cảnh]__  
  - Restore là “device-wide” (toàn GPU), nên nếu còn restore từ PID cũ sẽ phá trạng thái PID mới. Hủy “cross-PID restore” (hủy khôi phục chéo PID) là bắt buộc.
- __[Quan sát và truy vết]__  
  - Dùng **Correlation ID** (mã tương quan – liên kết log cùng một phiên) để theo dõi toàn bộ chuỗi restore và xác minh sau restore.
- __[Xác minh sau restore]__  
  - Sau khi restore, kiểm tra hashrate tăng hợp lệ và nhiệt độ an toàn trước khi khóa xung. Điều này ngăn việc khóa vào trạng thái xấu.

## Các bước cụ thể (triển khai trong code hiện tại)
- __[1) Cưỡng bức baseline ngay khi bắt đầu tối ưu]__  
  - Trong [OptimizedHardwareController.set_target_utilization()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:2377:4-2696:9) ở [app/mining_environment/scripts/resource_control.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:0:0-0:0):  
    - Cưỡng bức power ≥ `MIN_POWER_LIMIT` (mặc định 120W).  
    - Cưỡng bức xung SM ≥ `MIN_SM_CLOCK` (mặc định 1200 MHz); MEM clock tối thiểu có thể lấy hiện tại hoặc `MIN_MEM_CLOCK` (nếu có).  
    - Mục tiêu: đảm bảo GPU không bị kẹt ở xung thấp sau restart.
- __[2) Hủy restore chéo PID trước khi tuning]__  
  - Gọi [_cancel_pending_restores_for_gpu(gpu_index, except_key=(pid,gpu))](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:3315:4-3369:23) sớm để hủy mọi restore pending từ PID khác.  
  - Bật `CANCEL_CROSS_PID_RESTORE_BY_GPU=1` (mặc định bật) để tránh reset thiết bị muộn gây tụt hiệu suất.
- __[3) Vòng “closed-loop” điều chỉnh nhẹ]__  
  - Vẫn trong [set_target_utilization()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:2377:4-2696:9): điều chỉnh `power_limit` và/hoặc `sm_clock` theo bước nhỏ (`GPU_CLOSED_LOOP_STEP_POWER`, `GPU_CLOSED_LOOP_STEP_SM`) với khoảng chờ (`GPU_CLOSED_LOOP_MIN_INTERVAL_SEC`), có kiểm tra nhiệt độ mỗi vòng.  
  - Nguyên tắc: phản hồi theo “utilization target” để đạt plateau ổn định.
- __[4) Khóa xung có điều kiện]__  
  - Khi đã đạt mục tiêu và nếu `ALLOW_CLOCK_LOCK=1` (bật khóa xung), gọi [GPUResourceManager.verify_clock_lock_conditions()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:243:4-423:24) (xác minh khóa xung – hashrate tăng đủ phần trăm, nhiệt độ < ngưỡng) trong cửa sổ `CLOCK_LOCK_VERIFY_WINDOW_SEC` (mặc định 60s).  
  - Nếu đạt, khóa bằng [set_gpu_clocks()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:888:4-985:24) để ngăn downclock.
- __[5) Lên lịch restore có theo dõi ID]__  
  - Trong [OptimizedHardwareController._schedule_restore()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:3371:4-3447:116): tạo **Correlation ID** (mã tương quan) cho mỗi job, log đầy đủ, hủy cross-PID pending, chờ “window” rồi:  
  - Gọi [GPUResourceManager.restore_gpu_settings_for_pid(pid, correlation_id=cid)](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1581:4-1663:24):
    - Reset application clocks bằng **NVML** (thư viện quản lý NVIDIA – điều khiển thiết bị), phục hồi power/clocks theo trạng thái đã lưu.
    - Ghi “post-restore status” (trạng thái sau restore) và chạy xác minh hậu kiểm ([verify_clock_lock_conditions()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:243:4-423:24)) chỉ để quan sát, không tự khóa trong restore.  
  - Mọi log đều gắn CID để truy vết chuỗi sự kiện.

## Thành phần/biến quan trọng
- __[Hàm/đường dẫn]__  
  - [resource_control.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:0:0-0:0)  
  - [GPUResourceManager.restore_gpu_settings_for_pid()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1581:4-1663:24) (khôi phục + hậu kiểm + CID)  
  - [OptimizedHardwareController._schedule_restore()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:3371:4-3447:116) (lập lịch + CID + hủy cross-PID)  
  - [OptimizedHardwareController.set_target_utilization()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:2377:4-2696:9) (cưỡng bức baseline + closed-loop + điều kiện khóa xung)  
  - [GPUResourceManager.verify_clock_lock_conditions()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:243:4-423:24) (xác minh hashrate tăng và nhiệt độ an toàn).
- __[Biến môi trường]__  
  - `ALLOW_CLOCK_LOCK=1` (bật khóa xung – ngăn downclock)  
  - `MIN_SM_CLOCK=1200`, `MIN_POWER_LIMIT=120` (baseline – ngưỡng tối thiểu)  
  - `CLOCK_LOCK_VERIFY_WINDOW_SEC=60`, `CLOCK_LOCK_TEMP_MAX=70`, `CLOCK_LOCK_MIN_INCREASE_PCT=5` (cửa sổ/xác minh)  
  - `CANCEL_CROSS_PID_RESTORE_BY_GPU=1` (hủy restore chéo PID).

## Cách đọc log để xác nhận
- __[theo dõi CID]__  
  - Tìm `[OHC._schedule_restore] CID=…` và `[RC.restore] CID=…` để thấy “Waiting…”, “Restoring…”, “Post-restore status… power_limit=XW, SM=Y, MEM=Z”, và `Verification after restore | result=True/False`.
- __[tín hiệu xấu cần hết]__  
  - Không còn spam “Dwell-time active / Clamped power change”.  
  - Không còn “[RC] ⛔ Skipping clock lock (ALLOW_CLOCK_LOCK=0)”.

## Tại sao cách này hiệu quả?
- __[Ổn định xung/power]__  
  - Cưỡng bức baseline + (nếu an toàn) khóa xung đảm bảo SM clock không tụt sau restart → hashrate không rơi về 11–12 MH/s.
- __[Tránh restore muộn phá trạng thái]__  
  - Hủy cross-PID restore ngăn reset thiết bị sau khi đã tuning, tránh mất cấu hình tốt.  
- __[Điều khiển phản hồi]__  
  - Closed-loop giúp đạt mức tải mục tiêu một cách mượt với kiểm soát nhiệt/chờ, giảm “oscillation” (dao động – lên xuống thất thường).
- __[Quan sát tốt]__  
  - Correlation ID giúp gắn kết log, nhanh chóng khoanh vùng giai đoạn gây tụt nếu có.

## Kết luận
- Thực thi đầy đủ 5 bước trên giúp duy trì hashrate ổn định (≥39 MH/s/GPU) sau restart: baseline trước, hủy cross-PID đúng lúc, điều khiển closed-loop, khóa xung có điều kiện, và restore có hậu kiểm + quan sát theo CID.

Tôi đã hoàn thành phần giải thích và hướng dẫn. Nếu bạn muốn, tôi có thể trích một checklist kiểm thử và mẫu truy vấn log theo CID để bạn so sánh A/B sau lần restart kế tiếp.