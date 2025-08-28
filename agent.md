Mục tiêu: đọc kỹ tài liệu `docs/bao-cao-phan-tich-gpu.md`, rút ra các vấn đề hiện tại và đề xuất phương án tối ưu GPU cuối cùng, bao gồm loại bỏ trùng lặp chức năng.

Kế hoạch:
1) Mở và đọc toàn bộ nội dung tài liệu để nắm các nhận định/khuyến nghị hiện có.
2) Tổng hợp vấn đề theo nhóm: kiến trúc, metrics, tối ưu hiệu năng, cloaking, giám sát, cấu hình.
3) Đề xuất phương án tối ưu “cuối cùng” phù hợp quyết định giữ [OptimizedHardwareController](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1225:0-2452:90) và hợp nhất API GPU.
4) Liệt kê bước triển khai theo pha và rủi ro/biện pháp giảm thiểu.

Tôi sẽ mở file tài liệu để phân tích.

Mục tiêu: rà soát trùng lặp NVML/clock/power theo tài liệu và kiểm tra mức độ hiện thực của [IGpuMetricsProvider.get_metrics_snapshot()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:318:4-394:23) và alias [apply_gpu_controls()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1203:0-1223:20) trong code hiện tại, để đề xuất phương án tối ưu cuối cùng.

Kế hoạch:
1) Tìm [get_metrics_snapshot](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:318:4-394:23)/[apply_gpu_controls](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1203:0-1223:20) trong [resource_control.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:0:0-0:0) để xác nhận hiện trạng.
2) Tìm callsites trùng NVML/clock/power trong [utils.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/utils.py:0:0-0:0), [privileged_operations.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/privileged_operations.py:0:0-0:0), và [gpu_resource_monitor.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/gpu_resource_monitor.py:0:0-0:0) để liệt kê điểm cần gộp về [GPUResourceManager](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:66:4-66:33).
3) Tổng hợp phát hiện và đưa ra phương án tối ưu/cleanup.

Tôi sẽ chạy tìm kiếm song song trên các file liên quan.

Tôi sẽ cập nhật kế hoạch công việc (TODO) để phản ánh đề xuất tối ưu và loại bỏ trùng lặp, giúp bạn theo dõi tiến độ rõ ràng. Tôi sẽ thêm/cập nhật các mục: hợp nhất NVML về [GPUResourceManager](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:66:4-66:33), refactor chiến lược và monitor sang [IGpuMetricsProvider](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:111:0-116:11), chuẩn hóa TTL/sampling, toggle rollback, tests, logging, ENV, và sửa các edge cases.

Tôi sẽ lưu lại “phương án tối ưu GPU cuối cùng” vào bộ nhớ dùng chung để đảm bảo nhất quán trong các bước triển khai tiếp theo và tránh quên các quyết định kiến trúc quan trọng.
Tóm tắt nhanh:
- [docs/bao-cao-phan-tich-gpu.md](cci:7://file:///home/azureuser/opus-gpu/docs/bao-cao-phan-tich-gpu.md:0:0-0:0) chỉ ra trùng lặp NVML/clock/power ở nhiều lớp, TTL/monitor chưa đồng bộ, bug pre‑unlock, thiếu `pynvml` fallback.
- Phương án cuối: lấy [GPUResourceManager](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:66:4-66:33) làm “single source of truth” và triển khai [IGpuMetricsProvider](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:111:0-116:11) + [GpuMetricsSnapshot](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:92:0-108:45); [MetricsCollectionHub](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:83:0-472:38) chỉ làm time‑series aggregator. Xoá mọi NVML trực tiếp khỏi strategy/monitor/utils, ủy quyền về một chỗ. Giữ [OptimizedHardwareController](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1225:0-2452:90), thêm alias tương thích.
- Có toggle rollback, TTL động, fallback `nvidia-smi`, chuẩn hóa ENV/logging/tests.

Tôi bám theo quyết định trong memory “Giữ OptimizedHardwareController… hợp nhất API GPU” (quyết định ưu tiên – định hướng hợp nhất).

# Findings (từ tài liệu)
- __Điểm trùng NVML/điều khiển__  
  - Theo tài liệu: NVML và thao tác clock/power xuất hiện ở nhiều lớp: `utils.GPUManager` (NVML cơ bản), [GPUResourceManager](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:66:4-66:33) (NVML + policy), `PrivilegedOperationManager` (đụng clock).  
  - Đặt clock/power lặp lại ở [utils.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/utils.py:0:0-0:0), [resource_control.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:0:0-0:0), [privileged_operations.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/privileged_operations.py:0:0-0:0).  
  - Khuyến nghị của tài liệu: chọn 1 API trung tâm là [GPUResourceManager](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:66:4-66:33) để thống nhất policy (dwell/clamp/min-util).  
  - Trích dẫn: [docs/bao-cao-phan-tich-gpu.md](cci:7://file:///home/azureuser/opus-gpu/docs/bao-cao-phan-tich-gpu.md:0:0-0:0) mục 3 và 6 (dẫn chứng chi tiết các file).

- __Vấn đề vận hành__  
  - `CUDA_COMMAND` chưa khớp thực tế (env → `/usr/local/bin/inference-cuda` → fallback [/app/inference-cuda](cci:7://file:///home/azureuser/opus-gpu/app/home/azureuser/opus-gpu/app/inference-cuda:0:0-0:0)).  
  - Vòng pre‑unlock chạy khi không có GPU (bug `range(max(1,_cnt))`).  
  - Thiếu `pynvml` trong môi trường Python → cần fallback `nvidia-smi`.  
  - Trích dẫn: mục 5 (edge cases) và mục 6 (đề xuất).

- __Vai trò class hiện có__  
  - [GpuMetricsSnapshot](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:92:0-108:45) (ảnh chụp số liệu – gói số liệu tức thời, đa‑GPU).  
  - [IGpuMetricsProvider](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:111:0-116:11) (giao diện cung cấp số liệu – API đọc snapshot có TTL).  
  - Cả hai đã hiện diện tại [app/mining_environment/scripts/resource_control.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:0:0-0:0) (đoạn 86–120).  
  - [MetricsCollectionHub](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:83:0-472:38) (trung tâm thu thập – time‑series, circular buffer, thống kê) hiện được [GpuCloakStrategy](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:1162:0-1794:114) đẩy số liệu “pre/warmup”, nhưng chưa có “post‑apply” để đóng vòng phản hồi.

# Kết luận về trùng lặp
- __Không trùng nếu phân vai đúng__:  
  - [IGpuMetricsProvider](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:111:0-116:11) (nguồn sự thật phần cứng – đọc NVML/cached, đưa [GpuMetricsSnapshot](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:92:0-108:45)).  
  - [MetricsCollectionHub](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:83:0-472:38) (bus/event time‑series – nhận sự kiện từ snapshot, aggregate, export).  
- __Trùng lặp hiện hữu__ là do: strategy/monitor/utils/privileged ops đều tự đọc NVML hoặc tự đặt clock/power. Cần dồn về [GPUResourceManager](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:66:4-66:33).

# Phương án tối ưu GPU cuối cùng
- __Trục lõi__  
  - [GPUResourceManager](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:66:4-66:33) (quản lý NVML – nguồn sự thật): triển khai đầy đủ [IGpuMetricsProvider.get_metrics_snapshot(ttl_sec)](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:318:4-394:23) trả [GpuMetricsSnapshot](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:92:0-108:45).  
    - TTL động: Idle (util thấp, T ổn) → TTL ~1.5–2.0s; Busy (util cao, T ≥72°C) → TTL ~0.5s.  
    - Cache handle NVML theo GPU, khóa RLock per‑GPU; thống nhất xử lý lỗi NVML.  
    - Fallback `nvidia-smi` (lệnh hệ thống – truy vấn NVML gián tiếp) khi thiếu `pynvml` với tần suất thấp.
  - [OptimizedHardwareController](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1225:0-2452:90) (bộ điều khiển phần cứng tối ưu – áp dụng an toàn clock/power/VRAM/compute): giữ nguyên làm nơi thực thi cuối.  
    - Thêm alias [apply_gpu_controls()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1203:0-1223:20) (bí danh – tương thích ngược) trỏ tới thực thi hiện tại (ví dụ [apply_optimization()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1629:4-1681:24)).
- __Luồng metrics thống nhất__  
  - Strategy/monitor chỉ gọi [IGpuMetricsProvider.get_metrics_snapshot()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:318:4-394:23) → ánh xạ snapshot → [MetricsCollectionHub.add_metric()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:171:4-204:24) theo từng type.  
  - Chuẩn hóa mapping:  
    - utilization (0..1) → `gpu_usage.utilization` (%).  
    - power_watts → `power.power_draw` (W).  
    - temperature_c → `temperature.temperature` (°C).  
    - mem_used/total bytes → `memory_usage.memory_usage_mb/gpu_memory_mb` (MB).  
  - Bổ sung “post‑apply metrics” (sau khi OHC áp dụng) để đánh giá hiệu quả vòng sau.
- __Xoá trùng lặp điều khiển__  
  - Mọi thao tác [set_gpu_power_limit](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:396:4-497:24), [set_gpu_clocks](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:499:4-596:24) chỉ được thực hiện bởi [GPUResourceManager](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:66:4-66:33) theo policy thống nhất (dwell/clamp/safety).  
  - `utils.GPUManager` trở thành thin‑proxy (hoặc deprecate), gọi sang [GPUResourceManager](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:66:4-66:33).  
  - `PrivilegedOperationManager` chỉ làm phần đặc quyền; khi cần clock/power → ủy quyền sang [GPUResourceManager](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py:66:4-66:33).
- __Đồng bộ cấu hình__  
  - Sampling interval/TTL đặt tại cấu hình trung tâm (ENV/const), `monitor` và `strategy` dùng chung.  
  - ENV chuẩn hóa: `CUDA_COMMAND` theo thứ tự: ENV → `/usr/local/bin/inference-cuda` → [/app/inference-cuda](cci:7://file:///home/azureuser/opus-gpu/app/home/azureuser/opus-gpu/app/inference-cuda:0:0-0:0).  
  - Toggle rollback: `USE_UNIFIED_GPU_PROVIDER=0/1`; hỗ trợ log song song để so sánh số liệu (A/B) trước khi bật mặc định.
- __Logging/Hardening__  
  - Chuẩn hóa tên logger/level, áp dụng log deduplication tại vòng lặp nhanh.  
  - Thread‑safety: khóa theo GPU cho cả snapshot cache và điều khiển; thời gian “dwell” giữa hai lần set clock/power.  
  - Thống nhất xử lý lỗi NVML (retry/backoff, degrade sang `nvidia-smi`).

# Lộ trình triển khai (ngắn gọn, ít rủi ro)

- __Pha 1 – Hạ tầng provider__  
  - Hoàn thiện `get_metrics_snapshot()` trong `GPUResourceManager` + TTL động + fallback `nvidia-smi`.  
  - Thêm alias `apply_gpu_controls()` trong OHC.  
  - Bật toggle `USE_UNIFIED_GPU_PROVIDER` (mặc định off), ghi log song song.

- __Pha 2 – Refactor tiêu thụ metrics__  
  - [GpuCloakStrategy] dùng provider thay vì tự đọc NVML; publish snapshot → [MetricsCollectionHub](pre + post‑apply).  
  - [gpu_resource_monitor.py] chuyển sang provider; bỏ NVML trực tiếp.  



- __Pha 3 – Dọn trùng lặp điều khiển__  
  - `utils.GPUManager`: chuyển thành proxy hoặc gắn deprecation + ủy quyền.  
  - `PrivilegedOperationManager`: bỏ trực tiếp clock/power, ủy quyền về [GPUResourceManager].  


- __Pha 4 – Đồng bộ cấu hình & sửa lỗi__  
  - Đồng bộ sampling/TTL, chuẩn hóa `CUDA_COMMAND`.  
  - Sửa vòng pre‑unlock `range(_cnt)`.  
- __Pha 5 – Kiểm thử & rollout__  
  - Unit tests: snapshot/provider; mock NVML.  
  - Integration: đa‑GPU, stress; đo số NVML calls trước/sau TTL động.  
  - Bật dần `USE_UNIFIED_GPU_PROVIDER` sau khi so sánh sai khác trong ngưỡng.

