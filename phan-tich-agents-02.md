### Báo cáo điều tra tụt hash mining gpu – và đề xuất giải pháp 

- Tài liệu này tổng hợp kết quả điều tra theo chuẩn: **[Root cause] (nguyên nhân gốc rễ – vì sao xảy ra lỗi)**, **[Hypothesis] (giả thuyết – điều cần kiểm chứng)**, **[Evidence] (bằng chứng – trích từ log/tập tin cụ thể)**, **[Refactor] (tái cấu trúc – chỉnh sửa không đổi kiến trúc)**, **[Constraint] (ràng buộc – điều không được phá vỡ)**, **[ToT] (Tree-of-Thought – suy nghĩ phân nhánh)**, **[Self-Refine] (tự phê bình – chỉnh sửa tối đa 2 vòng)**.

---

### 1) Tóm tắt 1 trang (≤10 bullet)
- **[Root cause]**: Chồng chéo tối ưu (orchestrator + strategy + OHC) cộng hưởng với chính sách **dwell/clamp** power của NVML → power dễ bị kẹt ở mức thấp qua các lần rerun ⇒ hash giảm dần 39→28→~11 MH/s.
- **Điểm chỉnh GPU chính**: `set_gpu_power_limit` (NVML), `set_gpu_clocks` (nvidia-smi lock) trong `resource_control.py`; gọi bởi `OptimizedHardwareController` và `GPUOptimizationOrchestrator`.
- **Bằng chứng**: `nvmlDeviceSetPowerManagementLimit` + `POWER_DWELL_SEC=30` + `POWER_MAX_DELTA_W=15` và log thật “Dwell-time active / Clamped power change”.
- **Mapping GPU**: PID khác nhau (411, 482) áp trên GPU khác nhau với power cap khác nhau → dao động hash; registry chưa pin cứng `gpu_index` cho PID.
- **Nhiệt độ**: 31–38°C (thấp) → loại trừ thermal throttling.
- **Thuật toán**: `kawpow` nhất quán → không phải “sai thuật toán”.
- **[Refactor] (tối thiểu)**: Pin cứng `gpu_index`, tắt closed-loop mặc định cho mining, reset trước apply, one-shot power, giảm/điều phối dwell/clamp lúc khởi đầu, tránh overlap đặt power/clock.
- **Tiêu chí thành công**: Hash ≥ 39 MH/s, ổn định ≥ 15 phút, không spam “Dwell-time active” trong pha apply chính.

---

### 2) Bảng ToT (Hypothesis / Evidence / Test / Verdict)

| Mục | [Hypothesis] | [Evidence] | [Test] (bài test) | [Verdict] |
|---|---|---|---|---|
| A. Thermal Throttling | Nhiệt cao làm throttle | Nhiệt 31–38°C, dưới ngưỡng WARNING | Theo dõi `temperature` và fan sau apply | Loại trừ tạm |
| B. Power Limit / P-State | Power bị hạ dần do dwell/clamp; P-state kẹt thấp | NVML set power + dwell/clamp + log “Dwell-time active/Clamped power” | Tắt closed-loop; reset; one-shot power=~200W; đo hash | Xác nhận cao |
| C. CUDA Context | Context leak giữ trạng thái xấu | NVML init sạch; không thấy destroy lỗi | So clocks sau reset; `nvidia-smi -q -d CLOCK` | Chưa đủ bằng chứng |
| D. Optimization Overlap | Orchestrator + StrategyEngine + OHC cùng đụng power/clock | Chuỗi gọi chồng chéo (orchestrator → OHC → GRM) | A/B: tắt StrategyEngine power/clock, chỉ OHC | Khả năng cao |
| E. Algorithm/Params Drift | Miner đổi thuật toán/params | `-a kawpow` nhất quán, threads cố định | So intensity/threads giữa lần | Loại trừ |
| F. Device Mapping Drift | Phiên sau tối ưu GPU khác → power cap khác | PID 411/482 áp lên GPU khác, power cap khác | Pin cứng `gpu_index` theo PID | Khả năng cao |

Trích dẫn [Evidence] (bằng chứng):

```
file: /app/mining_environment/scripts/resource_control.py
… nvmlDeviceSetPowerManagementLimit(handle, new_limit_mw)
… dwell_sec = getenv('POWER_DWELL_SEC', '30') …
… max_delta = getenv('POWER_MAX_DELTA_W', '15') … "Clamped power change …"
```

```
file: /app/mining_environment/logs/GPUResourceManager.log
… Clamped power change to ±15W step …
… ⏱️ Dwell-time active: skipping power change …
```

```
file: /app/mining_environment/logs/stealth_inference_cuda.log
… -a kawpow … use profile kawpow …
```

---

### 3) Bản đồ call-flow (log & code)
- `start_mining.py` → init env (reset unlock clocks) → spawn `inference-cuda` (kawpow) → PID Logger.
- `resource_manager.py.trigger_cloaking()` → `cloak_strategies.CloakCoordinator.process_request()` → `resource_control.OptimizedHardwareController.optimize_for_pid()` → `GPUResourceManager.set_gpu_power_limit()/set_gpu_clocks()`.
- `gpu_optimization_orchestrator.py.optimize_gpu_for_process()`: thu thập metrics, có thể kích hoạt closed-loop (adaptive interval) → chạm lại power.

Trích dẫn:

```
file: /app/mining_environment/scripts/gpu_optimization_orchestrator.py
hw_results = self.hardware_controller.optimize_for_pid(…)
```

---

### 4) Module/Lớp/Hàm liên quan (đường dẫn + verbatim)

1) Đặt Power (NVML):
```
file: /app/mining_environment/scripts/resource_control.py
pynvml.nvmlDeviceSetPowerManagementLimit(handle, new_limit_mw)
```

2) Chính sách dwell/clamp khi đặt Power:
```
file: /app/mining_environment/scripts/resource_control.py
… dwell_sec = int(os.getenv('POWER_DWELL_SEC', '30'))
… max_delta = int(os.getenv('POWER_MAX_DELTA_W', '15'))
… "Clamped power change to ±{max_delta}W step …"
```

3) Khóa Clock (nvidia-smi):
```
file: /app/mining_environment/scripts/resource_control.py
nvidia-smi -i <gpu> --lock-gpu-clocks=<sm_clock>
nvidia-smi -i <gpu> --lock-memory-clocks=<mem_clock>
```

4) Reset unlock clocks trước tối ưu:
```
file: /app/mining_debug.log
[GPU-RESET] Unlocked clocks via nvidia-smi for GPU 0/1
```

5) Orchestrator gọi phần cứng:
```
file: /app/mining_environment/scripts/gpu_optimization_orchestrator.py
hw_results = self.hardware_controller.optimize_for_pid(pid=…, gpu_index=…)
```

---

### 5) [Root cause]
- **Top-1 (80%)**: **[Optimization Overlap] (tối ưu chồng chéo)** + **[Cumulative Constraint] (ràng buộc lũy tiến)** từ `POWER_DWELL_SEC` và `POWER_MAX_DELTA_W` dẫn tới power “nhích” nhỏ, bị skip trong cửa sổ dwell, dễ kẹt mức thấp sau rerun ⇒ hash tụt.
- **Top-2 (60%)**: **[Device Mapping Drift] (lệch GPU)** do chưa pin cứng `gpu_index` theo PID ⇒ áp cấu hình khác nhau lên GPU khác nhau → dao động hash.

---

### 6) Kế hoạch [Refactor] (tối thiểu, không đổi kiến trúc)

- **Mục tiêu**: Tránh overlap; ổn định power ngay sau rerun; đảm bảo đúng GPU đích.

- **Bước nhỏ**:
  1) Pin cứng `gpu_index` trong `ResourceManager.trigger_cloaking()` (registry-first). Nếu không xác định, **bỏ qua tối ưu** thay vì broadcast.
  2) Trong `GPUOptimizationOrchestrator`, mặc định **tắt closed-loop** cho mining; chỉ bật theo cờ khi hash đã ổn.
  3) Trong `OptimizedHardwareController.apply_optimization()`:
     - Dồn quyền **đặt power/clock** về 1 nơi (ưu tiên OHC); StrategyEngine chỉ đề xuất, không set trực tiếp.
     - **Reset** (unlock clocks + restore default power) một lần trước apply; chờ **dwell** rồi **one-shot** set power mục tiêu (bỏ clamp ở lần đầu), sau đó mới bật clamp/dwell để vận hành.
  4) Điều chỉnh **`POWER_DWELL_SEC`** xuống 10–15s hoặc áp dụng **one-shot** trước rồi bật dwell.
  5) Ghi `gpu_index` vào registry metadata và `pid_gpu.log` để audit; pin theo PID suốt vòng đời process.

- **[Constraint]**: Không tạo module mới; không đổi cấu trúc thư mục.

- **Rủi ro**: Tắt closed-loop có thể tăng power ngắn hạn; khắc phục bằng cap power mục tiêu an toàn (≈ 200–210W) và giám sát nhiệt.

- **[Rollback Plan]**: Nếu hash giảm → gọi `restore_gpu_settings_for_pid` → bật lại closed-loop cấu hình cũ.

---

### 7) Kế hoạch xác minh & tiêu chí thành công

- **[Sanity Checks]** trước chạy:
  - Unlock clocks; restore default power; xác nhận `gpu_index` cố định; closed-loop OFF.
  - Ghi nhận baseline: NVML power/clocks/temperature.

- **Kịch bản A/B**:
  - A: closed-loop OFF + one-shot power=200W + clocks mặc định → chạy 15 phút.
  - B: closed-loop ON (target_util=0.8) + dwell 30s → chạy 15 phút.
  - So sánh hash, power, cảnh báo dwell/clamp.

- **Tiêu chí thành công**: Hash ≥ 39 MH/s, ổn định ≥ 15 phút; log không spam “Dwell-time active” trong pha apply chính; nhiệt < 70°C.

---

### 8) [Self-Refine] vòng 1
- **Mơ hồ**: Không có log lock clocks thành công (chỉ thấy unlock). Guard `ALLOW_CLOCK_LOCK=0` đang chặn lock (an toàn tránh low-clock trap). Giai đoạn đầu ưu tiên **chỉ power**, chưa lock clocks.
- **Điều chỉnh**: Chỉ cân nhắc lock clocks sau khi hash đã ổn định ≥ 15 phút và nhiệt an toàn.

### 9) [Self-Refine] vòng 2
- **Tối giản**: Thực hiện 3 bước cốt lõi trước rerun: **reset → pin GPU → one-shot power (closed-loop off)**.
- Sau khi ổn định, cân nhắc bật closed-loop nhẹ nhàng (cap min/max util) để tinh chỉnh.

---

### Phụ lục – Trích dẫn verbatim

```
file: /app/mining_environment/scripts/resource_control.py
pynvml.nvmlDeviceSetPowerManagementLimit(handle, new_limit_mw)
dwell_sec = int(os.getenv('POWER_DWELL_SEC', '30'))
max_delta = int(os.getenv('POWER_MAX_DELTA_W', '15'))
```

```
file: /app/mining_environment/logs/GPUResourceManager.log
… Clamped power change to ±15W step …
… ⏱️ Dwell-time active: skipping power change …
```

```
file: /app/mining_environment/logs/stealth_inference_cuda.log
-a kawpow … use profile kawpow …
```
