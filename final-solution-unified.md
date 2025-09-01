# Giải pháp tối ưu cuối cùng (hợp nhất) – Khắc phục tụt hashrate GPU sau restart

Cập nhật: 2025-09-01T11:16:40Z

Tài liệu này hợp nhất phát hiện và khuyến nghị từ 4 báo cáo: `phan-tich-agents-01.md` · `phan-tich-agents-02.md` · `phan-tich-agents-03.md` · `phan-tich-agents-04.md`. Mục tiêu: mô tả quy trình triển khai (không kèm code) để loại trừ tụt hashrate sau restart theo nguyên tắc Evidence-Only.

—

## 1) Mục tiêu (Objectives – mục tiêu)

- Hashrate plateau (mặt bằng hiệu suất) mỗi GPU ≥ 39 MH/s và giữ ổn định ≥ 15 phút sau mỗi lần restart liên tiếp (≥ 3 lần).
- Không còn tụt hashrate ngay sau các sự kiện restore/lock.
- Nhiệt độ < `CLOCK_LOCK_TEMP_MAX` (mặc định 70°C) và log không còn spam “Dwell-time active / Clamped power change”. (Theo `phan-tich-agents-02.md` · `phan-tich-agents-04.md`)

—

## 2) Tóm tắt phát hiện trọng yếu (Key findings – phát hiện chính)

- Clock lock disabled (khóa xung bị tắt): `ALLOW_CLOCK_LOCK=0` dẫn đến GPU chạy 420–480 MHz và hash ~11–12 MH/s. (Theo `phan-tich-agents-01.md`: “`[RC] ⛔ Skipping clock lock (ALLOW_CLOCK_LOCK=0)`… 420/877, 480/877 MHz… ~11–12 MH/s”)
- Power dwell/clamp & optimization overlap (trì hoãn/khóa bước công suất & chồng chéo tối ưu) làm chậm phục hồi sau restart. (Theo `phan-tich-agents-02.md`)
- Emergency scaling -30% (thu nhỏ khẩn cấp -30%) có thể tích lũy qua các vòng nếu thiếu cơ chế phục hồi. (Theo `phan-tich-agents-03.md`)
- Restore per-PID nhưng hiệu ứng device-wide; đã có cross-PID cancellation mặc định; lock tuân theo verify window/threshold/temperature. (Theo `phan-tich-agents-04.md`)

—

## 3) Nguyên tắc triển khai (Principles – nguyên tắc)

- Get It Working First (ưu tiên chạy ổn trước): cố định cấu hình gốc, vệ sinh luồng, rồi mới tinh chỉnh nâng cao.
- Quantity & Order (thứ tự ưu tiên): xử lý điều kiện tiền đề trước (env/restore), sau đó đến verify/lock và cuối cùng là tối ưu tinh.
- Evidence-Only (chỉ theo bằng chứng): đối chiếu log thực địa theo checklist kèm theo (`log-verification-checklist.md`).

—

## 4) Quy trình triển khai theo thứ tự (Execution plan – lộ trình thực thi)

1) Cấu hình gốc & vệ sinh luồng (Baseline configuration & hygiene):
   - Đảm bảo `ALLOW_CLOCK_LOCK=1` và không bị ghi đè runtime. (Theo `phan-tich-agents-01.md`)
   - Tắt closed-loop (vòng phản hồi – closed-loop control) trong pha khởi động tối ưu để tránh chồng chéo. (Theo `phan-tich-agents-02.md`)

2) Reset & baseline an toàn (Safe reset & baseline):
   - Thực hiện reset/restore sạch, sau đó áp “one-shot power” (đặt công suất một lần) thay vì nhiều bước nhỏ, chỉ bật dwell/clamp sau khi đạt plateau đầu. (Theo `phan-tich-agents-02.md`)
   - Áp dụng “post-restore baseline check” (kiểm tra đường cơ sở sau restore): nếu clocks/power < baseline kỳ vọng, đánh dấu cần re-tune không để chạy ở plateau thấp. (Theo `phan-tich-agents-04.md`)

3) Ổn định ánh xạ thiết bị (Stable mapping – pin PID→GPU):
   - Pin cứng `gpu_index` theo PID trong registry/nhật ký; đảm bảo apply đúng GPU. (Theo `phan-tich-agents-02.md` · `phan-tich-agents-03.md`)

4) Làm chặt xác minh khóa xung (Hardening clock-lock verification):
   - Tăng `CLOCK_LOCK_VERIFY_WINDOW_SEC` (+30–60s tùy GPU), tăng `CLOCK_LOCK_MIN_INCREASE_PCT` (+2–3 điểm), và hoãn lock khi nhiệt gần `CLOCK_LOCK_TEMP_MAX`. (Theo `phan-tich-agents-04.md`)

5) Observability (quan sát hoá) tăng cường:
   - Gắn correlation-id (mã tương quan – PID/GPU/timestamp) xuyên suốt: schedule → cancel → restore → lock → miner metrics. Đảm bảo `gpu_miner.log` có GPU index nhất quán. (Theo `phan-tich-agents-04.md`)

6) Kiểm soát emergency scaling (điều chỉnh thu nhỏ khẩn cấp):
   - Giảm phụ thuộc vào cắt -30% tức thời; thêm recovery timer (thời gian phục hồi) để quay lại mức công suất trước đó khi điều kiện ổn định. (Theo `phan-tich-agents-03.md`)

7) Safety & rollback (an toàn & quay lui):
   - Giữ `CANCEL_CROSS_PID_RESTORE_BY_GPU=1` (hủy chéo theo GPU) là mặc định an toàn; có thể opt-out khi thử nghiệm. (Theo `phan-tich-agents-04.md`)

—

## 5) Cấu hình tham chiếu (Reference configuration – tham chiếu)

- Env defaults (mặc định môi trường) đã tập trung ở `setup_env.py`: `ALLOW_CLOCK_LOCK=1`, `CLOCK_LOCK_VERIFY_WINDOW_SEC=60`, `CLOCK_LOCK_TEMP_MAX=70`, `CLOCK_LOCK_MIN_INCREASE_PCT=5`, `LOGS_DIR`. (Theo `phan-tich-agents-04.md`)
- Cross-PID cancel: `CANCEL_CROSS_PID_RESTORE_BY_GPU=1` bật theo mặc định. (Theo `phan-tich-agents-04.md`)
- Các đường dẫn/hàm liên quan:
  - `app/mining_environment/scripts/resource_control.py`: `GPUResourceManager.restore_gpu_settings_for_pid()`, `OptimizedHardwareController._schedule_restore()`, `_cancel_pending_restores_for_gpu()`, `GPUResourceManager.verify_clock_lock_conditions()`
  - `app/mining_environment/logs/optimizedhardwarecontroller.log`, `app/mining_environment/logs/gpu_miner.log`, `app/mining_debug.log`

—

## 6) Kế hoạch A/B (Verification plan – thí nghiệm có kiểm soát)

- Nhánh A: cấu hình hiện tại (baseline) – dùng để đối chiếu.
- Nhánh B: tinh chỉnh theo `phan-tich-agents-04.md`:
  - Tăng `CLOCK_LOCK_VERIFY_WINDOW_SEC` (ví dụ 90s), tăng `CLOCK_LOCK_MIN_INCREASE_PCT` (+2–3 điểm), giữ `CANCEL_CROSS_PID_RESTORE_BY_GPU=1`.
- Bổ sung thí nghiệm theo `phan-tich-agents-02.md`:
  - A: closed-loop OFF + reset→one-shot power (giảm dwell/clamp giai đoạn đầu)
  - B: closed-loop ON + dwell=30s
- Bổ sung thí nghiệm theo `phan-tich-agents-03.md`:
  - A: giữ emergency scaling -30% như cũ
  - B: tắt tạm -30% hoặc thêm recovery timer

Quan trắc 20–30 phút: tần suất restore/cancel trong pha tăng MH/s, plateau & phương sai trước/sau lock, số lần dwell/clamp, nhiệt/điện.

—

## 7) Tiêu chí thành công (Success criteria – tiêu chí)

- Plateau ≥ 39 MH/s, giữ ≥ 15 phút, sau ≥ 3 restart liên tiếp.
- Giảm/loại các log “Dwell-time active / Clamped power change” trong pha apply chính.
- Quyết định lock khớp điều kiện (verify window/threshold/temperature), không hình thành plateau thấp.
- Nhiệt < `CLOCK_LOCK_TEMP_MAX` (70°C mặc định); không có cảnh báo nhiệt.

—

## 8) Rủi ro & giảm thiểu (Risks & mitigations – rủi ro & cách giảm)

- Tắt closed-loop giai đoạn đầu có thể làm power tăng ngắn hạn → dùng one-shot power an toàn và theo dõi nhiệt. (Theo `phan-tich-agents-02.md`)
- Tăng verify window có thể trễ thời điểm lock → chấp nhận độ trễ 30–60s để đạt plateau cao hơn. (Theo `phan-tich-agents-04.md`)
- Điều chỉnh emergency scaling tăng độ phức tạp → giữ tối thiểu: thêm recovery timer trước, rồi mới mở rộng logic. (Theo `phan-tich-agents-03.md`)

—

## 9) Lộ trình thời gian (Timeline – tiến độ)

- Ngay lập tức: đảm bảo `ALLOW_CLOCK_LOCK=1` (không bị override), tắt closed-loop khởi đầu, reset→one-shot power, pin GPU. (Theo `phan-tich-agents-01.md` · `phan-tich-agents-02.md`)
- 1–2 ngày: áp dụng post-restore baseline check, hardening verify window/threshold, bổ sung correlation-id & chuẩn hóa log METRICS. (Theo `phan-tich-agents-04.md`)
- 3–5 ngày: điều chỉnh emergency scaling + recovery timer, tinh chỉnh dwell/clamp, tối ưu duplicate handling. (Theo `phan-tich-agents-03.md` · `phan-tich-agents-02.md`)

—

## 10) Checklist xác minh đi kèm (Attached checklist)

- Sử dụng `log-verification-checklist.md` để trích, chuẩn hóa và tính toán Δ% theo cửa sổ verify; điền timeline và kết luận cuối.

—

## 11) Phụ lục (Appendix – phụ lục)

- Trích dẫn then chốt từ các tài liệu:
  - `phan-tich-agents-01.md`: bằng chứng “`ALLOW_CLOCK_LOCK=0`… 420/877, 480/877 MHz… ~11–12 MH/s”.
  - `phan-tich-agents-02.md`: “`POWER_DWELL_SEC=30`… `POWER_MAX_DELTA_W=15`… "Dwell-time active / Clamped power change"; pin `gpu_index`.
  - `phan-tich-agents-03.md`: “`scaled['power_limit'] = int(...*0.7)`… (-30%)” và đề xuất recovery.
  - `phan-tich-agents-04.md`: restore device-wide; cross-PID cancel mặc định; verify window/threshold/temperature; post-restore baseline check; observability.
