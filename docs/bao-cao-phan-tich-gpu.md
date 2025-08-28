# Báo Cáo Phân Tích & Tối Ưu Hệ Thống GPU (thư mục `/app`)

> Tài liệu này tổng hợp kết quả rà soát codebase, đánh giá hiệu năng hiện tại và đề xuất tối ưu hóa dành cho hệ thống GPU trong dự án. Phạm vi: chỉ trong `/app`. Các thuật ngữ tiếng Anh được chú thích theo dạng [English Term] (mô tả tiếng Việt – chức năng/mục đích).

---

## 1) Đánh Giá Năng Lực & Phạm Vi
- **Phân tích codebase**: Có khả năng lập bản đồ pipeline GPU, tìm trùng lặp hàm/module ở lớp NVML/clock/power/logging.
- **Đo hiệu năng**: Đo nhanh baseline bằng [nvidia-smi] (lệnh hệ thống – truy vấn GPU thông qua NVML). Chưa chạy workload mining vì lý do an toàn.
- **Đề xuất tối ưu**: Tập trung “gộp về một điểm sự thật” đối với NVML/clock/power; chỉnh TTL cache động; chuẩn hóa biến `CUDA_COMMAND`; sửa vòng pre-unlock.
- **Giới hạn**: Không thay đổi cấu trúc thư mục, không tạo module mới. Chỉ đề xuất mô tả refactor.

---

## 2) Sơ Đồ Pipeline GPU (đã khoanh vùng)
- Khởi động mining (GPU-only): `app/start_mining.py`
  - Gọi [Stealth Wrapper] (trình bao bọc ẩn) để chạy `inference-cuda` qua Python: 
    - Dẫn chứng: `app/start_mining.py:546-555`
- Trình bao bọc ẩn: `app/mining_environment/stealth/wrappers/stealth_inference_cuda.py`
  - Tạo môi trường sạch cho GPU, loại bỏ `LD_PRELOAD`, dọn cờ CUDA bất lợi. 
  - Nộp PID về [HookCoordinator] (Điều phối hook – bước bàn giao PID):
    - Dẫn chứng: `app/mining_environment/stealth/wrappers/stealth_inference_cuda.py:153-171`, `:251-277`
- Điều phối PID: `app/mining_environment/coordination/coordinator.py`
  - [HookCoordinator] (điều phối hook) nhận PID từ wrapper và chuyển tuyến đến registry → ResourceManager.
  - Dẫn chứng: `app/mining_environment/coordination/coordinator.py:582-631`
- Điều khiển tài nguyên GPU (NVML): `app/mining_environment/scripts/resource_control.py`
  - [GPUResourceManager] (quản lý NVML/power/temperature/utilization). 
  - Dẫn chứng: `app/mining_environment/scripts/resource_control.py:123`, `:240-339`, `:397-498`, `:500-516`
- Giám sát: `app/mining_environment/scripts/gpu_resource_monitor.py`
  - [GPUResourceManagerMonitor] (giám sát thời gian thực, sinh dữ liệu dashboard). 
  - Dẫn chứng: `app/mining_environment/scripts/gpu_resource_monitor.py:110-172`, `:378`
- Điều phối tối ưu: `app/mining_environment/scripts/gpu_optimization_orchestrator.py`
  - Vòng lặp tối ưu đóng, chọn khoảng lặp theo trạng thái GPU. 
  - Dẫn chứng: `app/mining_environment/scripts/gpu_optimization_orchestrator.py:200-280`, `:445`, `:789`

---

## 3) Chức Năng Trùng Lặp (cần gộp/chuẩn hóa)
- NVML API và đo metrics xuất hiện ở nhiều lớp:
  - `utils.GPUManager` – NVML cơ bản (get power/temperature/utilization):
    - Dẫn chứng: `app/mining_environment/scripts/utils.py:205-229`, `:231-254`, `:256-281`
  - `GPUResourceManager` – NVML chuẩn hóa (caching, TTL, policy):
    - Dẫn chứng: `app/mining_environment/scripts/resource_control.py:240-339`, `:341-395`
  - `PrivilegedOperationManager` cũng thao tác liên quan clocks (ít nhiều trùng):
    - Dẫn chứng: `app/mining_environment/scripts/privileged_operations.py:141-163`
- Đặt xung nhịp [set GPU clocks] (SM/MEM) hiện diện ở 3 nơi:
  - Dẫn chứng: `app/mining_environment/scripts/utils.py:283-343`, `app/mining_environment/scripts/resource_control.py:500-516`, `app/mining_environment/scripts/privileged_operations.py:141-163`
- Đặt power limit cũng trùng:
  - Dẫn chứng: `app/mining_environment/scripts/resource_control.py:397-498` (đã có chính sách dwell/clamp), `app/mining_environment/scripts/utils.py:162-204`
- Nhận định: Nên chọn 1 API trung tâm là `GPUResourceManager` để tránh lệch chính sách và giảm mã trùng.

---

## 4) Đánh Giá Hiệu Năng Hiện Tại (baseline nhanh, không workload)
- Kết quả đo nhanh bằng [nvidia-smi] (lệnh hệ thống – truy vấn GPU):
  - GPU: Tesla T4, trạng thái idle
  - Mẫu 6 lần, mỗi 0.5s (định dạng: `index, util.gpu, power.draw, temp`):

```
0, 0, 9.29, 29
0, 0, 9.10, 29
0, 0, 9.39, 29
0, 0, 9.68, 29
0, 0, 9.39, 29
0, 0, 9.78, 29
```

- Diễn giải: idle → `util.gpu ~ 0%`, `power ~ 9.x W`, `temp ~ 29°C`.
- Ghi chú: `pynvml` Python chưa có trong môi trường nên các hàm NVML Python sẽ fallback về 0/None; `nvidia-smi` vẫn sử dụng được.

---

## 5) Vấn Đề & Edge Cases Phát Hiện
- Không khớp đường dẫn mặc định `CUDA_COMMAND` vs nội dung repo:
  - Wrapper mặc định `/usr/local/bin/inference-cuda`, repo có `app/inference-cuda` (script) + `app/inference-cuda.original` (ELF).
  - Dẫn chứng: `app/mining_environment/stealth/wrappers/stealth_inference_cuda.py:156-167`, `app/inference-cuda:1`
- Vòng pre-unlock clocks chạy cả khi không có GPU:
  - Dùng `range(max(1, _cnt))` khiến vẫn chạy index 0 khi `_cnt=0`.
  - Dẫn chứng: `app/mining_environment/coordination/coordinator.py:649-666`
- Thiếu [pynvml] (thư viện Python – binding NVML) trong môi trường Python:
  - Dẫn chứng: thử import NVML Python báo lỗi. Hệ quả: module giám sát Python đọc NVML trả 0/None nếu không có fallback.

---

## 6) Đề Xuất Tối Ưu & Refactor (không tạo module mới, không đổi cấu trúc)
1) **Một điểm sự thật cho NVML/clock/power**
   - Duy trì `GPUResourceManager` là API trung tâm. 
   - `utils.GPUManager` chuyển thành thin-proxy hoặc chỉ giữ utilities không NVML; mọi call NVML (đặc biệt `set_gpu_power_limit`, `set_gpu_clocks`) gọi sang `GPUResourceManager`.
   - `PrivilegedOperationManager` chỉ giữ nhiệm vụ đặc quyền; khi cần clock/power → ủy quyền cho `GPUResourceManager`.
   - Lợi ích: thống nhất dwell/clamp/min-util policy; giảm mã trùng; dễ kiểm soát.

2) **Chuẩn hóa `CUDA_COMMAND`**
   - Thứ tự: ENV `CUDA_COMMAND` → `/usr/local/bin/inference-cuda` → fallback `/app/inference-cuda`.
   - Đảm bảo chạy cục bộ thuận tiện (khớp với repo hiện có).

3) **TTL cache động cho metrics**
   - Idle (util thấp, nhiệt độ ổn): tăng TTL (1.5–2.0s) để giảm NVML calls.
   - Busy (util cao, T ≥72°C): giữ TTL 0.5s (như hiện tại: `app/mining_environment/scripts/resource_control.py:324-339`).

4) **Sửa vòng pre-unlock tránh gọi `nvidia-smi` thừa**
   - Thay `range(max(1, _cnt))` → `range(_cnt)` (khi `_cnt=0` thì bỏ qua hoàn toàn).

5) **Fallback `nvidia-smi` khi thiếu `pynvml`**
   - Trong monitor/resource manager, khi không có `pynvml` → đọc metrics cơ bản từ [nvidia-smi] (lệnh hệ thống – truy vấn GPU) với tần suất thấp, tránh crash.

6) **Kiểm soát log ồn**
   - Duyệt các logger mức DEBUG ở các vòng lặp nhanh (orchestrator/monitor) → áp dụng [log deduplication] (khử trùng log – loại trùng) đã có; nâng mức log ở nhánh lặp dày.

---

## 7) Kế Hoạch Đo Lường & Xác Minh (sau khi duyệt mới thực hiện)
- [Nhánh 2 – dữ liệu thực]:
  - Chạy mining qua wrapper (chỉ khi được duyệt), đo:
    - Thời gian bàn giao PID qua [HookCoordinator] và readiness/DAG.
    - NVML snapshots mỗi 0.5–1s: util/power/temp/mem.
  - So sánh số NVML calls trước/sau TTL động (ước lượng overhead monitor).
- [Nhánh 3 – edge cases]:
  - Nhiều GPU (nếu có): theo dõi “tier” khoảng lặp orchestrator (chọn ở `app/mining_environment/scripts/gpu_optimization_orchestrator.py:200-280`).

---

## 8) Self‑Refine (Tự hoàn thiện)
- Vòng 1 (phê bình): gộp NVML có thể bỏ sót callsite cũ dùng `utils.GPUManager`. 
- Vòng 2 (sửa): bước đầu biến `utils.GPUManager` thành proxy (gọi `GPUResourceManager`) và thêm cảnh báo deprecation ở log để tìm callsite còn sót.

---

## 9) Rủi Ro & Lưu Ý An Toàn
- Chạy `inference-cuda`/`inference-cuda.original` là hoạt động mining (tiêu tốn GPU/điện). Chỉ chạy khi được phép và mục đích hợp lệ.
- `hijack_nvml_socket` can thiệp `/var/run/nvidia-persistenced/socket` – chỉ dùng khi cần thiết, trong môi trường cho phép.

---

## Phụ Lục: Trích Dẫn Nguồn (Evidence‑Only)
- `app/start_mining.py:546-555`, `:460-520`, `:540-560`
- `app/mining_environment/stealth/wrappers/stealth_inference_cuda.py:153-171`, `:251-277`, `:156-167`
- `app/mining_environment/coordination/coordinator.py:582-631`, `:646-666`
- `app/mining_environment/scripts/resource_control.py:123`, `:240-339`, `:324-339`, `:397-498`, `:500-516`
- `app/mining_environment/scripts/gpu_resource_monitor.py:110-172`, `:378`
- `app/mining_environment/scripts/gpu_optimization_orchestrator.py:200-280`, `:445`, `:789`
- `app/mining_environment/scripts/utils.py:162-204`, `:205-229`, `:231-254`, `:256-281`, `:283-343`
- `app/mining_environment/scripts/privileged_operations.py:141-163`
- `app/inference-cuda:1`

---

### Trạng Thái
- Phân tích xong, sẵn sàng triển khai các refactor tối thiểu sau khi bạn phê duyệt.

