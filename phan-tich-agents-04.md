# 🔍 **BÁO CÁO ĐIỀU TRA TỤT HASH RATE GPU** — **VÀ ĐỀ XUẤT PHƯƠNG ÁN KHẮC PHỤC**

### 1) Tóm tắt hiện trạng

Dựa trên phân tích log từ `/home/azureuser/opus-gpu/app/mining_debug.log` và các trích dẫn được cung cấp trong truy vấn, dòng thời gian và con số **[hash rate] (tốc độ băm – chỉ số hiệu năng đào)** như sau:

- **Lần 1**: ~29.12 MH/s, với các giá trị như "equivalent to 32669992.44 H/s" (tương đương 32.67 MH/s) và "29598351.54 H/s" (29.60 MH/s) tại timestamp "2025-09-01 12:40:33" (nguồn: `/home/azureuser/opus-gpu/app/mining_debug.log`, dòng liên quan đến [inference-cuda-stdout]).
- **Lần 2**: ~20.59 MH/s, với "equivalent to 17065126.22 H/s" (17.07 MH/s) và "19788845.50 H/s" (19.79 MH/s) tại timestamp "2025-09-01 12:53:36" (nguồn: `/home/azureuser/opus-gpu/app/mining_debug.log`).
- **Lần 3+**: ~12.87 MH/s, với "speed 10s/60s/15m 11.87 n/a n/a MH/s" và "equivalent to 8989106.73 H/s" (8.99 MH/s) tại timestamp "2025-09-01 17:45:30" và "2025-09-01 17:46:54" (nguồn: `/home/azureuser/opus-gpu/app/mining_debug.log`).
- **Trường hợp không chạy tối ưu**: ~20.31 MH/s, với "speed 10s/60s/15m 20.31 n/a n/a MH/s" tại timestamp "2025-09-01 17:37:01" (nguồn: log cung cấp trong truy vấn).

Các dấu hiệu chung: **[clock speed] (tốc độ xung – tần số hoạt động GPU)** giảm dần như "405/877 MHz" và "412/877 MHz", chỉ ra trạng thái idle hoặc low-power.

### 2) Cây nguyên nhân (Tree-of-Thought tóm tắt)

Dựa trên **[Tree-of-Thought] (cây tư duy – phương pháp phân nhánh giả thuyết)**, tôi tạo 3 nhánh theo yêu cầu, mỗi nhánh với triệu chứng → giả thuyết → bằng chứng → test. Chọn nhánh tốt nhất dựa trên bằng chứng từ log (clock thấp persistent) và code (có set nhưng thiếu reset rõ ràng).

- **Nhánh A — Driver/OS**: Triệu chứng: Clock kẹt ở mức thấp (405/877 MHz) sau stop/start. Giả thuyết: **[Persistence Mode] (chế độ duy trì – giữ cấu hình GPU sau khi ứng dụng dừng)** hoặc **[Application Clocks] (khóa xung ứng dụng – cố định tần số)** sticky không được reset, dẫn đến **[P8] (trạng thái hiệu năng chậm – chế độ tiết kiệm năng lượng)**. Bằng chứng: Log "405/877 MHz" tại "2025-09-01 17:45:30" (nguồn: `/home/azureuser/opus-gpu/app/mining_debug.log`); code trong `app/mining_environment/scripts/setup_env.py` (dòng 366: _run_smi(['nvidia-smi','-pm','1']) enable persistence nhưng thiếu disable). Test: Chạy nvidia-smi -q -d POWER,CLOCK trước/sau stop để kiểm tra nếu clock/power khôi phục.
- **Nhánh B — Ứng dụng/Orchestrator**: Triệu chứng: Hash rate giảm dần dù không tối ưu. Giả thuyết: **[gpu_optimization_orchestrator.py] (điều phối tối ưu – quản lý tài nguyên GPU)** và **[resource_control.py] (điều khiển tài nguyên – set giới hạn)** áp dụng power/clock nhưng thiếu teardown. Bằng chứng: Code trong `app/mining_environment/scripts/resource_control.py` (dòng 3045: target_power = int(max(20, min(self.power_max, self.baseline_power * (1.0 + power_var * 0.2)))) set power_limit nhưng không thấy reset; log power "75W" persistent tại "2025-09-01 17:45:30". Test: Thêm log trước/sau stop trong resource_control.py để xác nhận nếu reset được gọi.
- **Nhánh C — Miner/Workload**: Triệu chứng: Hash rate thấp ngay cả không tối ưu. Giả thuyết: Thay đổi **[intensity] (mức tải – độ mạnh workload)** hoặc affinity dẫn đến underutilization. Bằng chứng: Log "task progress: 1 unit (equivalent to 8989106.73 H/s)" tại "2025-09-01 17:46:54" cho thấy workload không đầy tải; nhưng thiếu code cụ thể về DAG/intensity trong kết quả search. Test: So sánh utilization % qua nvidia-smi trước/sau start miner.

**Nhánh chọn**: Nhánh A (tốt nhất vì log clock thấp sticky khớp trực tiếp với persistence mode được enable trong code mà thiếu disable, và hash rate giảm dần chỉ ra vấn đề driver-level persistent; các nhánh khác ít bằng chứng trực tiếp hơn).

### 3) Nguyên nhân cốt lõi (Root Cause)

Dựa trên **[evidence-only] (chỉ dựa chứng cứ – không suy đoán)** từ log và code:

- Clock speed kẹt ở mức thấp (ví dụ: "405/877 MHz" tại timestamp "2025-09-01 17:45:30", nguồn: `/home/azureuser/opus-gpu/app/mining_debug.log`), chỉ ra **[P-state] (trạng thái hiệu năng – mức power management)** bị kẹt ở idle (P8), dẫn đến hash rate giảm từ 29 MH/s xuống 12 MH/s.
- Persistence mode được enable (bằng chứng: `app/mining_environment/scripts/setup_env.py` dòng 366: _run_smi(['nvidia-smi','-pm','1'])), nhưng thiếu code reset (không thấy --pm 0 hoặc tương đương trong kết quả search).
- Power limit set (bằng chứng: `app/mining_environment/scripts/resource_control.py` dòng 3045: target_power set, và Dockerfile ENV GPU_POWER_LIMIT_WATTS), nhưng không reset, dẫn đến sticky sau stop/start (log "75W" persistent).
- Không đủ chứng cứ cho thermal throttle (nhiệt "38C" thấp, nguồn: log "2025-09-01 17:45:30"), nhưng clock thấp sticky là root chính.

### 4) Module/Lớp/Hàm bị ảnh hưởng

Danh sách từ rà soát codebase qua search, tập trung vào thao tác **[power_limit] (giới hạn công suất – set max watt)**, **[sm_clock] (xung nhân CUDA – tần số core)**, **[mem_clock] (xung bộ nhớ – tần số VRAM)**, **[persistence mode] (chế độ duy trì – giữ cấu hình)**, v.v. (điểm vào: nơi áp dụng; điểm thoát: nơi reset, nhưng thiếu reset là vấn đề).

- `app/mining_environment/scripts/setup_env.py: enforce_gpu_baselines` → Vai trò: Set power limit (_run_smi(['nvidia-smi','-pl',str(int(float(min_pl)))]), lock sm/mem clocks (--lock-gpu-clocks, --lock-memory-clocks), enable persistence (-pm 1); bằng chứng: dòng 374, 386, 393 (nguồn: search result). Điểm vào: Gọi tại setup; điểm thoát: Thiếu reset rõ ràng.
- `app/mining_environment/scripts/resource_control.py: OptimizedHardwareController` → Vai trò: Set power_limit, sm_clock, mem_clock trong _get_strategy_params và _apply_compute_simulation; bằng chứng: dòng 3045 (target_power), 3054 (params['sm_clock']), 3058 (params['mem_clock']) (nguồn: search result). Điểm vào: Khi apply strategy; điểm thoát: Không thấy teardown/reset.
- `app/mining_environment/scripts/resource_control.py: _get_strategy_params` → Vai trò: Tính toán params cho power_limit, clocks dựa baseline; bằng chứng: dòng 3045 (nguồn: search result). Điểm vào: Per strategy; điểm thoát: Thiếu.
- `app/Dockerfile` (không phải hàm, nhưng liên quan) → Vai trò: Định nghĩa ENV như GPU_POWER_LIMIT_WATTS, ALLOW_CLOCK_LOCK; bằng chứng: dòng 152, 153 (nguồn: search result). Điểm vào: Build time; điểm thoát: N/A.

Không đủ chứng cứ cho **[temperature] (nhiệt độ – ngưỡng cảnh báo)** hoặc **[compute mode] (chế độ tính toán – exclusive/process)** trong code tìm thấy (chỉ thấy temp trong config, không set/reset).

### 5) Thiết kế refactor (không code)

Theo **[Get It Working First] (làm chạy ổn định trước – ưu tiên chức năng cơ bản)**, đề xuất refactor tận dụng mã hiện có, nhúng vào file/module sẵn, không tạo mới, không đổi cấu trúc.

- **[Idempotent reset] (reset lặp lại an toàn – khôi phục trạng thái mà không phụ thuộc lần chạy trước)** trong `resource_control.py`: Thêm logic nhúng vào OptimizedHardwareController (sử dụng existing _apply_compute_simulation làm base), gọi nvidia-smi --reset-gpu-clocks và -pm 0 để nhả clock/persistence; gọi bắt buộc từ `start_mining.py` trong khối **[finally] (luôn chạy kể cả lỗi – đảm bảo teardown)** để reset sau stop, sử dụng existing pynvml handle để xác nhận.
- **[Single Source of Truth] (nguồn trạng thái duy nhất – lưu baseline một nơi)** trong `gpu_optimization_orchestrator.py`: Nhúng vào existing class (nếu có) hoặc function, lưu baseline clock/power từ pynvml.nvmlDeviceGetClockInfo/GetPowerManagementLimit khi start, áp dụng delta (tận dụng existing params dict), và nhả về baseline tại end (gọi từ finally ở start_mining.py).
- **[Cloak release path] (đường nhả cloaking – giải phóng che giấu tài nguyên)** trong `cloak_strategies.py`: Nhúng vào existing strategy functions, thêm path thoát gọi reset từ resource_control.py (tận dụng existing params), đảm bảo nhả power/clock sau cloaking; chứng minh bằng log assert sau stop (tận dụng existing logger).
- **[Double-check logging] (log xác minh kép – kiểm tra trước/sau thao tác)**: Nhúng vào resource_control.py sau mỗi set/reset, đọc lại clock/power via pynvml và log "restored >= baseline" (tận dụng existing get_handle và logger), fail nếu không khớp.

### 6) Kế hoạch kiểm chứng & tiêu chí “Get It Working First”

Theo **[Think Big, Do Baby Steps] (nghĩ lớn, làm nhỏ – phân tích toàn bộ nhưng test từng bước)** và **[Quantity & Order] (số lượng & thứ tự – đếm GPU, ưu tiên baseline trước)**, kế hoạch tuần tự:

- B1: **Chụp baseline**: Tại start đầu, ghi clock/power/temp mỗi GPU via nvidia-smi -q -d CLOCK,POWER (log số lượng GPU từ detect_gpu_count trong setup_env.py); tiêu chí pass: Log đầy đủ baseline mà không lỗi.
- B2: **Áp dụng → Xác minh**: Sau apply strategy trong resource_control.py, đọc lại giá trị thực via pynvml; tiêu chí pass: Giá trị khớp params ±5%.
- B3: **Dừng → Reset → Xác minh**: Tại stop, chạy idempotent reset (từ finally), đọc lại clock/power; tiêu chí pass: Khớp baseline ±5%, không sticky low clock.
- B4: **Start lại miner**: Chạy miner 2–5 phút, đối chiếu hash rate; tiêu chí pass: ±5% so với baseline lượt 1 (ví dụ: >=27.66 MH/s từ 29.12), fail nếu giảm >10%.

Tiêu chí tổng: Working first nếu hash ổn định sau 3 stop/start, ưu tiên stability trước optimize.

### 7) Rủi ro & phương án rollback

- Rủi ro: Reset thất bại dẫn đến clock không nhả, ảnh hưởng workload khác (bằng chứng: log clock sticky); rollback: Chạy manual nvidia-smi -pm 0 và --reset-gpu-clocks từ privileged_operations.py (nếu có), sau đó restart container.
- Rủi ro: Log assert fail do NVML error (bằng chứng: potential exception trong resource_control.py dòng 3052); rollback: Bỏ qua assert và fallback về baseline ENV từ Dockerfile, log warning.
- Rủi ro: Không đủ quyền trong Docker (bằng chứng: ENV ENABLE_NVML_CONTROL=1 nhưng có thể fail); rollback: Escalate privilege via existing PrivilegedOperationManager trong privileged_operations.py, hoặc restart với --privileged.

**Always Double-Check**: Mọi kết luận dựa trên search result từ codebase (ví dụ: setup_env.py dòng 366 cho persistence) và log từ grep (ví dụ: "11.87 MH/s" tại /home/azureuser/opus-gpu/app/mining_debug.log). Không đủ chứng cứ cho MIG/MPS (không tìm thấy trong search).