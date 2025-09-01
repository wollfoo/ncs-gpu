# 🔍 **BÁO CÁO ĐIỀU TRA TỤT HASH RATE GPU** — **VÀ ĐỀ XUẤT PHƯƠNG ÁN KHẮC PHỤC**

### 1) Tóm tắt hiện trạng

- Lần 1 (~29.12 MH/s):
  - "2025-09-01 12:40:33,360 - gpu_miner - INFO - ... (equivalent to 29598351.54 H/s)" (nguồn: `/app/mining_debug.log`).
- Lần 2 (~20.59 MH/s):
  - "2025-09-01 12:53:36,327 - gpu_miner - INFO - ... (equivalent to 17065126.22 H/s)" (nguồn: `/app/mining_debug.log`).
  - "2025-09-01 12:53:36,330 - gpu_miner - INFO - ... (equivalent to 19788845.50 H/s)" (nguồn: `/app/mining_debug.log`).
- Lần 3+ (~12.87 MH/s):
  - "2025-09-01 17:45:30,787 - stealth_inference - INFO - ... 405/877 MHz ... speed ... 11.87 MH/s" (nguồn: `/app/mining_environment/logs/stealth_inference_cuda.log`).

Đặc biệt: khi KHÔNG chạy hệ thống tối ưu vẫn chỉ ~20.31 MH/s:
- "[2025-09-01 17:37:01.544]  miner    speed ... 20.31 ... MH/s max 24.96 MH/s" (nguồn: dữ liệu người dùng).

### 2) Cây nguyên nhân (Tree-of-Thought tóm tắt)

- Nhánh A — Driver/OS (Evidence-backed):
  - Triệu chứng: clock tụt về "405/877 MHz", hash ~11–12 MH/s.
  - Bằng chứng: `"[2025-09-01 17:45:30.787] ... 75W 38C 405/877 MHz"` (nguồn: `/app/mining_environment/logs/stealth_inference_cuda.log`).
  - Giả thuyết: PowerMizer kẹt P8; application clocks/persistence mode/limit sticky giữa các lần restart.
  - Test đề xuất: sau mỗi stop/start, đọc `nvidia-smi --query-gpu=clocks.gr,clocks.mem,power.limit --format=csv` và so baseline; nếu < baseline hoặc 405 MHz → P8/lock chưa được reset.

- Nhánh B — Ứng dụng/Orchestrator (Evidence-backed):
  - Triệu chứng: có luồng đặt lock/power nhưng không teardown đầy đủ khi dừng, và/hoặc cloaking hạ xung không nhả.
  - Bằng chứng:
    - Đặt lock: `resource_control.py:set_gpu_clocks()` gọi `--lock-gpu-clocks=...` và `--lock-memory-clocks=...` (file: `/app/mining_environment/scripts/resource_control.py`, dòng 961–976).  
    - Khôi phục: `resource_control.py:restore_gpu_settings_for_pid()` reset application clocks bằng NVML (dòng 1604–1606), rồi set lại power limit nếu có (1618–1623).  
    - Pre-unlock nhiều nơi chạy trước tối ưu hóa: 
      - `setup_env.reset_gpu_state()` gọi `-rgc` và `--reset-memory-clocks` (dòng 309–311) và sau đó `enforce_gpu_baselines()` có thể lock lại (dòng 383–394) (file: `/app/mining_environment/scripts/setup_env.py`).
      - `coordination/coordinator.py` cũng `-rgc`/`--reset-memory-clocks` theo `GPU_PRE_UNLOCK` (dòng 659–661).
    - Không thấy teardown GPU ở `start_mining.py` (khối finally) để buộc restore/baseline khi stop.
  - Giả thuyết: khâu stop/terminate không gọi restore idempotent → clock/power dính trạng thái giữa lần chạy; hoặc `enforce_gpu_baselines()` khóa xung cố định gây lệch khi restart theo thời điểm.
  - Test: ép gọi restore idempotent khi stop và log post-restore; so clock/power trước-sau.

- Nhánh C — Miner/Workload (Speculative):
  - Triệu chứng: thay đổi intensity/DAG/affinity làm underutilization.
  - Bằng chứng: chưa có log trực tiếp về pinning/affinity thay đổi gây dưới tải.
  - Test: giữ nguyên môi trường GPU, chỉ thay đổi workload params để xem hash biến thiên độc lập clocks; hiện thiếu chứng cứ trong log/code.

→ Chọn Nhánh B là hướng chính (ứng dụng/orchestrator) do có bằng chứng thao tác lock/reset rải rác nhưng thiếu teardown đồng bộ khi stop.

### 3) Nguyên nhân cốt lõi (Root Cause)

- Thiếu đường thoát reset idempotent khi dừng: `start_mining.py` không thực hiện khôi phục GPU về baseline trong khối `finally` (không tìm thấy any restore/reset call) (nguồn: `/app/start_mining.py`).  
- Nhiều nơi can thiệp clocks (lock) và reset rời rạc:
  - Lock: `/app/mining_environment/scripts/resource_control.py` `set_gpu_clocks()` dùng `nvidia-smi --lock-gpu-clocks=...` và `--lock-memory-clocks=...` (961–976).  
  - Reset: `/app/mining_environment/scripts/resource_control.py` `restore_gpu_settings_for_pid()` dùng `pynvml.nvmlDeviceResetApplicationsClocks(...)` (1604–1606).  
  - Reset trước tối ưu: `/app/mining_environment/scripts/setup_env.py:reset_gpu_state()` dùng `-rgc` + `--reset-memory-clocks` (309–311).  
  - Ngay sau reset lại có `enforce_gpu_baselines()` khóa lại clocks và đặt power min (149–155, 383–394).  
  - `coordination/coordinator.py` cũng pre-unlock (659–661) nhưng chỉ khi entry flow; không đảm bảo teardown khi stop.
- Kết quả: Sau nhiều stop/start, có thể kịch bản xảy ra: reset/lock tương tác không đồng bộ + thiếu teardown → GPU rơi vào `405/877 MHz` (dấu P8/idle) kèm hash tụt ~11–12 MH/s (nguồn: `/app/mining_environment/logs/stealth_inference_cuda.log` dòng 279–301), và trường hợp không chạy tối ưu vẫn ~20.31 MH/s cho thấy trạng thái sticky còn tồn tại.

### 4) Module/Lớp/Hàm bị ảnh hưởng

- `/app/mining_environment/scripts/resource_control.py: set_gpu_clocks(pid, gpu_index, sm_clock, mem_clock)` → đặt lock SM/MEM clocks bằng nvidia-smi.
- `/app/mining_environment/scripts/resource_control.py: set_gpu_power_limit(pid, gpu_index, power_limit_w)` → đặt power limit NVML.
- `/app/mining_environment/scripts/resource_control.py: restore_gpu_settings_for_pid(pid, correlation_id)` → reset application clocks NVML, phục hồi power limit; chỉ chạy khi được gọi, chưa thấy được gắn lifecycle stop rõ ràng.
- `/app/mining_environment/scripts/setup_env.py: reset_gpu_state(logger)` → `-rgc` và `--reset-memory-clocks` (pre-unlock).  
- `/app/mining_environment/scripts/setup_env.py: enforce_gpu_baselines(logger)` → bật persistence, đặt power limit tối thiểu, và khóa clock baseline (có thể tạo trạng thái sticky).  
- `/app/mining_environment/coordination/coordinator.py` (640–666): pre-unlock clocks khi handoff, nhưng không đảm bảo teardown khi stop.
- `/app/start_mining.py` → không có khối `finally` buộc gọi restore/reset GPU khi stop.

### 5) Thiết kế refactor (không code)

- [Idempotent reset] (reset an toàn) trong `resource_control.py` + gọi từ `start_mining.py`:
  - Thêm hàm `restore_all_gpus_idempotent()` trong `resource_control.py` tái sử dụng `pynvml`/`nvidia-smi` để: `nvmlDeviceResetApplicationsClocks` cho từng GPU, bỏ lock `-rgc`/`--reset-memory-clocks`, và nếu đã lưu baseline qua `process_gpu_settings` thì khôi phục power limit về baseline; đọc lại để xác nhận.
  - Trong `start_mining.py`, đăng ký callback với `process_manager.register_cleanup_callback(...)` và trong `signal_handler`/shutdown path gọi cứng `restore_all_gpus_idempotent()` trong khối `finally` để luôn chạy khi stop.

- [Single Source of Truth] (nguồn trạng thái duy nhất) trong `gpu_optimization_orchestrator.py`:
  - Lưu snapshot baseline lần start đầu: power limit hiện tại, SM/MEM clocks đọc từ NVML, persistence mode; lưu vào `self._baseline[gpu_index]` (SSOT).  
  - Mọi tối ưu chỉ áp dụng delta so với baseline; cuối vòng đời bắt buộc gọi nhả về baseline qua `GPUResourceManager.restore_gpu_settings_for_pid`/hàm mới GPU-wide restore; tránh multiply-lock từ `setup_env.enforce_gpu_baselines` bằng cờ tránh double-apply khi orchestrator quản lý.

- [Cloak release path] (đường nhả cloaking) trong `cloak_strategies.py`:
  - Bổ sung đường thoát đảm bảo khi cloaking kết thúc, mọi hạ xung/power đều được hoàn nguyên thông qua orchestrator/GRM; ghi log xác nhận cuối phiên: “Cloak released: clocks unlocked, power restored”.

- [Double-check logging] (log xác minh kép):
  - Sau mỗi set/reset/restore: đọc lại NVML (`clock SM/MEM`, `power limit`) và ghi log assert theo mẫu: `restored >= baseline`, hoặc `== baseline` nếu có thể; log sai khác để điều tra.
  - Chuẩn hóa chỉ một nơi được phép khóa clock (orchestrator) và một nơi reset (teardown) để tránh xung đột với `setup_env`.

- Ràng buộc: không tạo module mới/không đổi cấu trúc; nhúng các hàm vào `resource_control.py` và wiring từ `start_mining.py`/`gpu_optimization_orchestrator.py`.

### 6) Kế hoạch kiểm chứng & tiêu chí “Get It Working First”

- B1: Chụp baseline khi start đầu (mỗi GPU): log `SM/MEM clocks`, `power limit`, `persistence mode` (nguồn: NVML/nvidia-smi) → ghi vào `GPUResourceManager.log`.
- B2: Áp dụng tối ưu/throttle → đọc lại `clock/power` xác nhận giá trị thực và hash trong 2 phút đầu.
- B3: Dừng → chạy `restore_all_gpus_idempotent()` → đọc lại `clock/power` so với baseline; log “restored == baseline”.
- B4: Start lại miner → trong 2–5 phút đầu, so sánh hash với baseline lượt 1; tiêu chí pass: ±5% (ví dụ 29.12 ± 5%).

### 7) Rủi ro & rollback

- Rủi ro: Reset device-wide có thể ảnh hưởng process khác; mitigate bằng idle-gate đã có (`_schedule_restore`), và teardown chỉ chạy khi stop toàn hệ thống.  
- Rollback: Nếu hash không phục hồi, tắt `enforce_gpu_baselines()` tạm (ENV `ENFORCE_BASELINES_ON_RESET=0`) để loại bỏ can thiệp setup, chỉ cho orchestrator quản lý; có thể revert bằng bật lại ENV.

---

Tham chiếu (verbatim):
- `/app/mining_environment/logs/stealth_inference_cuda.log`: "[2025-09-01 17:45:30.787] ... 75W 38C 405/877 MHz", "... speed ... 11.87 MH/s".
- `/app/mining_environment/scripts/resource_control.py`: `set_gpu_clocks()` (961–976); `restore_gpu_settings_for_pid()` (1604–1623).
- `/app/mining_environment/scripts/setup_env.py`: `reset_gpu_state()` (309–311); `enforce_gpu_baselines()` (365–396, 383–394).
- `/app/mining_environment/coordination/coordinator.py`: pre-unlock `-rgc` & `--reset-memory-clocks` (659–661).
- `/app/start_mining.py`: không có teardown restore trong `finally`.
