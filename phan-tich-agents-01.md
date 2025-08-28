### Nhận diện trùng lặp và module tương đồng
- **NVML lifecycle** (vòng đời NVML – khởi tạo/tắt): trùng giữa `GPUResourceManager` và `SharedResourceManager`. Khuyến nghị 1 đầu mối.
- **GPU metrics** (chỉ số GPU – nhiệt/điện/utilization): trùng giữa `GPUResourceManager` và `GPUResourceManagerMonitor`. Khuyến nghị chuẩn hoá một nơi đọc, nơi khác chỉ gọi.
- **GPU reset/clocks** (đặt lại xung): lặp giữa `setup_env.reset_gpu_state` và thao tác trong `resource_control.py` (NVML reset apps clocks). Khuyến nghị gom về một chỗ gọi duy nhất.
- **VRAM allocation jitter** (dao động cấp phát VRAM – thử nghiệm bộ nhớ): cấp phát tensor CUDA lớn trong `resource_control.py` không kiểm tra dung lượng trước → rủi ro OOM.

### Đánh giá hiệu năng hiện tại
- **Thời gian xử lý GPU** (GPU-time – thời gian thao tác GPU): Có đoạn `torch.matmul` + `torch.cuda.synchronize()` để “burn GPU”, nhưng chưa có đo có hệ thống/kết hợp dashboard. Xem trích dẫn trên.
- **Sử dụng tài nguyên** (telemetry NVML – nhiệt/điện/utilization): Có, nhưng phân tán nhiều nơi, sampling chưa nhất quán (không có smoothing/moving-average/cửa sổ thời gian chung).

### Đề xuất tối ưu (chỉ mô tả, không đổi cấu trúc thư mục)
1) Hợp nhất API NVML/metrics
- **Unify NVML** (nhất quán NVML – một đầu mối): Dùng `SharedResourceManager.initialize_nvml()` làm nguồn NVML duy nhất; bỏ khởi tạo NVML ở `GPUResourceManager`.
- **Single metrics surface** (bề mặt đọc chỉ số duy nhất): Tạo nhóm hàm đọc `temperature/power/utilization` tại `SharedResourceManager` hoặc (nếu ưu tiên) tại `GPUResourceManager`, sau đó:
  - `GPUResourceManagerMonitor` chỉ gọi sang manager, không tự truy cập NVML.
  - Các nơi khác (orchestrator/controller) tái dùng hàm này thay vì gọi NVML thẳng.
- **Reset clocks single point** (điểm reset xung duy nhất): Định nghĩa một “reset” tại `setup_env.reset_gpu_state` và các nơi khác gọi về đây; tránh thao tác NVML reset rải rác.

2) Chuẩn hóa đo GPU-time và sampling
- **Use PerformanceProfiler** (dùng bộ đo hiệu năng – decorator đo thời gian) để wrap các “điểm nóng” GPU (ví dụ các vòng `torch`/NVML điều chỉnh) thay vì đo ad-hoc, ghi log ra `mining_performance.log`.
- **Sampling policy** (chính sách lấy mẫu – tần suất đo): đặt 1 tần suất cố định (ví dụ 1–2s) cho NVML sampling ở manager; dashboard/monitor đọc lại từ cache để tránh nhân đôi đọc NVML.
- **Smoothing** (làm mượt – trung bình trượt): dùng moving-average 5–10 mẫu cho utilization/temperature/power để giảm nhiễu, tránh flip-flop khi điều chỉnh power/clock.

3) Cải thiện thuật toán điều khiển GPU (giữ hiện trạng, tăng ổn định)
- **Closed-loop tuning** (điều chỉnh vòng kín – dùng mục tiêu utilization): sử dụng ngưỡng có sẵn `GPU_UTIL_MIN/MAX/TARGET` và ràng buộc `POWER_DWELL_SEC`/`POWER_MAX_DELTA_W` (đã có trong ENV) làm “guardrail”; điều chỉnh step nhỏ, chỉ đổi sau dwell time.
- **Safety checks** (kiểm soát an toàn – nhiệt/điện): luôn kiểm soát nhiệt trước khi tăng clock/power; rollback nếu vượt safe band.
- **VRAM guarding** (bảo vệ bộ nhớ VRAM): trước khi cấp phát tensor CUDA lớn, đọc `nvmlDeviceGetMemoryInfo` để so sánh còn trống/giới hạn config, tránh OOM rồi mới cấp phát.

4) Hạn chế overhead benchmark
- **Gate benchmark torch** (đặt sau cờ – tránh overhead runtime): chỉ chạy benchmark `torch` khi `RC_TORCH_BENCH=1`, mặc định tắt.

### Đề xuất refactor cụ thể (không tạo module mới)
- **Xoá song song khởi tạo NVML**: Giữ tại `SharedResourceManager.initialize_nvml()`; chuyển `GPUResourceManager` sang kiểm tra trạng thái NVML qua `SharedResourceManager` thay vì tự `pynvml.nvmlInit`.
  - Bằng chứng NVML ở 2 nơi: xem trích dẫn `resource_manager.py:100–125` và `resource_control.py:153–160`.
- **Hợp nhất đọc nhiệt/điện/utilization**:
  - Tạo/giữ bộ API đọc trong 1 nơi (ưu tiên `SharedResourceManager` hoặc `GPUResourceManager`), rồi đổi `GPUResourceManagerMonitor` gọi sang đó, bỏ đọc NVML trực tiếp.
  - Bằng chứng trùng lặp: `resource_control.py:577–594` vs `gpu_resource_monitor.py:261–279`; `resource_control.py:239–257`; `resource_control.py:1239–1274` vs `gpu_resource_monitor.py:301–319`.
- **Reset clocks một chỗ**:
  - Giữ `setup_env.reset_gpu_state` làm entrypoint reset; nơi khác gọi hàm này thay vì NVML reset riêng lẻ.
  - Bằng chứng: `setup_env.py:344–356` (NVML+nvidia-smi).
- **Chuẩn hoá đo GPU-time**:
  - Dùng `PerformanceProfiler.timing_decorator` bọc các điểm nóng I/O NVML hoặc xử lý CUDA “burner”; xuất metric vào `mining_performance.log` thay vì in rải rác.
  - Bằng chứng decorator: `performance_profiler.py:143–156`.
- **VRAM allocation guard**:
  - Trước các cấp phát CUDA lớn ở `resource_control.py:2016–2026` và khối VRAM jitter ở `resource_control.py:2151–2174`, thêm guard kiểm tra `mem.free` (NVML) và tôn trọng `resource_config` (`max_usage_percent` GPU, `VRAM_ALLOC_*` ENV).

### Kế hoạch đo lường (không chạy code lúc này; mô tả thao tác)
- **Đo GPU-time** (thời gian thực thi GPU – độ trễ thao tác): bọc vòng `torch.matmul` ở `resource_control.py:2016–2026` bằng `time.perf_counter()` và decorator profiler để ghi `wall_time`, `cpu_time` (đối chiếu `torch.cuda.synchronize()` để đo thật GPU).
- **Đo tài nguyên** (NVML): lấy snapshot trước-sau (nhiệt/điện/utilization) cùng timestamp; tính delta/mean qua moving-average.
- **Tiêu chí chấp nhận**:
  - Không crash khi `NVML` vắng hoặc `nvidia-smi` vắng (fallback đã có).
  - Telemetry sampling hợp nhất: mỗi 1–2s, không đọc NVML từ nhiều nơi trùng lặp.
  - Benchmark tắt mặc định; bật có chủ đích qua ENV.

### Rủi ro/Edge cases và cách xử lý
- **0 GPU** (không có GPU): luôn return số liệu 0/safe và skip điều khiển.
- **NVML lỗi**: giữ fallback `nvidia-smi` chỉ khi cần, có timeout ngắn.
- **VRAM OOM**: guard trước cấp phát; ưu tiên partial allocation + backoff.

### Self-Refine
- Vòng 1 (phê bình): Đề xuất hợp nhất NVML có thể ảnh hưởng đường gọi cũ; cần đảm bảo các chỗ gọi cũ được chuyển hướng an toàn, đặc biệt đối với rollback và reset clocks.
- Vòng 2 (sửa/chuẩn hoá): Chọn “giữ API ở `SharedResourceManager`”, còn `GPUResourceManager`/monitor chỉ là “khách hàng” của API này; thêm lớp chuyển tiếp mỏng (adapter) để không đổi chữ ký hàm public hiện có.

### Lộ trình triển khai (chỉ sau khi bạn duyệt)
- Bước 1: Chuẩn hóa NVML lifecycle – bỏ `pynvml.nvmlInit()` trong `GPUResourceManager`, dùng `SharedResourceManager` (giữ chữ ký public).
- Bước 2: Hợp nhất đọc `temperature/power/utilization` – di chuyển call NVML vào một cụm API duy nhất; `Monitor` gọi qua manager.
- Bước 3: Đặt `setup_env.reset_gpu_state` làm entrypoint reset; thay thế các reset NVML rải rác bằng gọi hàm này.
- Bước 4: Tích hợp `PerformanceProfiler` tại điểm nóng GPU; bật/tắt benchmark theo ENV.
- Bước 5: Thêm VRAM guards tại các cấp phát CUDA lớn.
- Bước 6: Kiểm thử khô (không GPU) và tích hợp (có GPU) với logging xác nhận sampling hợp nhất.

Bạn xác nhận để tôi bắt đầu thực hiện các “edits” theo thứ tự trên chứ?

- Nếu đồng ý, tôi sẽ:
  - Không tạo module mới, chỉ đổi gọi hàm và gom API vào nơi hiện có.
  - Giữ nguyên cấu trúc thư mục `app`.
  - Thêm cờ ENV cho benchmark để tránh overhead mặc định.

Tóm tắt
- Phát hiện trùng lặp NVML/metrics/reset giữa `resource_control.py`, `resource_manager.py`, `gpu_resource_monitor.py`, `setup_env.py`.
- Đề xuất hợp nhất NVML/metrics vào 1 đầu mối, chuẩn hoá đo GPU-time bằng `PerformanceProfiler`, đặt benchmark `torch` sau cờ ENV, thêm VRAM guard.
- Chờ duyệt để triển khai tuần tự, thay đổi tối thiểu, không tạo module mới.
