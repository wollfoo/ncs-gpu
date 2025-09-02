## 1. Executive Summary (Tóm tắt quản trị)

- Quan sát từ log cho thấy GPU thường rơi vào mức xung thấp (SM ≈ 405–450 MHz, MEM = 877 MHz) cùng công suất thấp (≈ 71–75W) và nhiệt độ mát (≈ 37–38°C), dẫn đến hashrate mỗi GPU chỉ ≈ 10–12 MH/s (tổng 2 GPU ≈ 20–24 MH/s).
- Cấu hình hệ thống hiện bật mặc định [persistence mode] (chế độ bền bỉ – giữ context driver) và có các thao tác khóa/mở khóa xung kết hợp giữa [NVIDIA NVML] (thư viện quản lý GPU ở mức driver) và [nvidia-smi] (CLI điều khiển/truy vấn GPU – công cụ dòng lệnh NVIDIA).
- Giả thuyết cốt lõi: sự kết hợp giữa [application clocks persistence] (khóa xung ứng dụng còn hiệu lực) và trình tự reset/restore chưa tất định (có điều kiện chờ idle hoặc có thể bị bỏ qua) trong bối cảnh [persistence mode] bật đã khiến GPU giữ nguyên trạng thái xung thấp qua các vòng start/stop, ngay cả khi chạy chỉ miner (không bật optimizer).
- Khuyến nghị: bổ sung [preflight reset] (reset trước khi chạy) tất định và [cleanup on exit] (hoàn nguyên khi thoát) có kiểm chứng; gom tất cả thao tác NVML/CLI vào một luồng duy nhất trong `resource_control.py` làm [Single Source of Truth] (nguồn sự thật duy nhất), ghi nhận state trước-trong-sau; nâng nền quan sát (thêm P-state, [perf cap reasons] – lý do giới hạn hiệu năng nếu sẵn có; power limit vs usage; logs before/after) để tránh “reset chưa hoàn toàn”.


## 2. Environment & Context (Môi trường & bối cảnh)

- Luồng chính: `app/start_mining.py` → `stealth_inference_cuda.py` → `inference-cuda` → `coordinator.py` → `direct_registry.py` → `resource_manager.py` → `cloak_strategies.py` → (trong `resource_manager.py`, sau cloaking) → `gpu_optimization_orchestrator.py` → `resource_control.py` → trở về `app/start_mining.py`.
- [NVIDIA NVML] (thư viện quản lý GPU ở mức driver) được dùng qua `pynvml` trong `resource_control.py`; [nvidia-smi] (CLI điều khiển/truy vấn GPU) cũng được gọi để [lock/unlock clocks] (khóa/mở khóa xung) và thu thập fallback metrics.
- Mặc định bật [persistence mode] (chế độ bền bỉ – giữ context driver) từ bước setup môi trường.


## 3. Evidence Timeline (Dòng thời gian bằng chứng)

- Khởi đầu có xung cao (ví dụ 1380/877 MHz) sau đó các snapshot ghi nhận xung thấp 405/412/442/450 MHz cùng công suất ≈ 71–75W, nhiệt ≈ 37–38°C và hashrate ~10–12 MH/s.

```45:46:/app/mining_environment/logs/stealth_inference_cuda.log
2025-09-01 17:44:22,598 - ... NVML 12.550.90.07/550.90.07
2025-09-01 17:44:22,598 - ... CUDA GPU #0 ... Tesla V100-PCIE-16GB 1380/877 MHz ...
```

```279:281:/app/mining_environment/logs/stealth_inference_cuda.log
2025-09-01 17:45:24,224 - ... [nvidia  #0 00:00.0  75W 38C 405/877 MHz]
2025-09-01 17:45:24,225 - ... [miner   speed 10s/60s/15m 11.10 n/a n/a MH/s max 11.10 MH/s]
```

```452:453:/app/mining_environment/logs/stealth_inference_cuda.log
2025-09-01 17:46:24,274 - ... [nvidia  #0 00:00.0  75W 38C 412/877 MHz]
2025-09-01 17:46:24,275 - ... [miner   speed 10s/60s/15m 11.26 11.27 n/a MH/s max 11.35 MH/s]
```

```476:478:/app/mining_environment/logs/stealth_inference_cuda.log
2025-09-01 17:46:30,837 - ... [nvidia  #0 00:00.0  75W 37C 412/877 MHz]
```

```634:635:/app/mining_environment/logs/stealth_inference_cuda.log
2025-09-01 17:47:24,316 - ... [nvidia  #0 00:00.0  75W 38C 405/877 MHz]
2025-09-01 17:47:24,317 - ... [miner   speed 10s/60s/15m 11.27 11.27 n/a MH/s max 11.35 MH/s]
```

```994:995:/app/mining_environment/logs/stealth_inference_cuda.log
2025-09-01 17:49:24,433 - ... [nvidia  #0 00:00.0  71W 38C 442/877 MHz]
2025-09-01 17:49:24,433 - ... [miner   speed 10s/60s/15m 11.17 11.17 n/a MH/s max 11.35 MH/s]
```

```1174:1175:/app/mining_environment/logs/stealth_inference_cuda.log
2025-09-01 17:50:24,487 - ... [nvidia  #0 00:00.0  71W 37C 450/877 MHz]
2025-09-01 17:50:24,488 - ... [miner   speed 10s/60s/15m 9.85 9.99 n/a MH/s max 11.35 MH/s]
```

- Bật [persistence mode] (chế độ bền bỉ) lúc setup:

```363:367:/app/mining_environment/scripts/setup_env.py
if str(os.getenv('ENABLE_PERSISTENCE_MODE_ON_SETUP', '1')).lower() in ('1','true','yes'):
    _run_smi(['nvidia-smi','-pm','1'], logger, "Enable persistence mode")
```

- Đặt [power limit] (giới hạn công suất) bằng NVML:

```875:882:/app/mining_environment/scripts/resource_control.py
new_limit_mw = power_limit_w * 1000
pynvml.nvmlDeviceSetPowerManagementLimit(handle, new_limit_mw)
...
self._last_power_limit_w[gpu_index] = power_limit_w
```

- Khóa xung bằng [nvidia-smi] (CLI), và restore theo chuỗi `-rgc`/`--reset-memory-clocks` → [nvmlDeviceResetApplicationsClocks]:

```961:977:/app/mining_environment/scripts/resource_control.py
cmd_sm = ['nvidia-smi','-i', str(gpu_index),'--lock-gpu-clocks=' + str(sm_clock)]
subprocess.run(cmd_sm, check=True)
...
cmd_mem = ['nvidia-smi','-i', str(gpu_index),'--lock-memory-clocks=' + str(mem_clock)]
subprocess.run(cmd_mem, check=True)
```

```1606:1634:/app/mining_environment/scripts/resource_control.py
['nvidia-smi', '-i', str(gpu_index), '-rgc']
['nvidia-smi', '-i', str(gpu_index), '--reset-memory-clocks']
pynvml.nvmlDeviceResetApplicationsClocks(handle)
```


## 4. Root Cause Analysis (Phân tích nguyên nhân gốc rễ)

- Dấu hiệu từ log: xung SM thường xuyên xoay quanh 405/412/442/450 MHz (thấp), công suất 71–75W, nhiệt 37–38°C, tương ứng mức tải nhẹ và P-state thấp. Hashrate duy trì ~10–12 MH/s/GPU.
- Cơ chế có khả năng tác động trạng thái:
  - Bật [persistence mode] (giữ context driver) có thể duy trì state khóa xung giữa các lần chạy nếu [reset chưa hoàn toàn] (trình tự restore không chạy/không đủ/quá muộn).
  - `resource_control.py` vừa dùng NVML vừa dùng [nvidia-smi] để khóa/mở khóa xung; trình tự restore dựa vào unlock bằng [nvidia-smi] rồi gọi [nvmlDeviceResetApplicationsClocks]. Việc phối hợp này có thể bỏ sót/reset không đồng bộ nếu bị gate bởi điều kiện (ví dụ “idle-gate” trong `_schedule_restore`).
  - Điều kiện chặn lock xung khi closed-loop tắt và xung hiện tại < 800 MHz:

```930:937:/app/mining_environment/scripts/resource_control.py
if (not cl_enabled) and current_sm_clock < 800:
    self.logger.warning("... skip locking to avoid low-clock trap ...")
    return False
```

  Điều này có thể khiến hệ thống không bao giờ nâng xung khi đã rơi vào trạng thái thấp, đặc biệt nếu trước đó đã từng có một lần lock/restore không hoàn toàn.

- Tổng hợp: Với [persistence mode] bật, một lần khóa xung (hoặc hạ power/clock) không được hoàn nguyên triệt để sẽ “dính” qua phiên sau. Khi khởi chạy chỉ miner, nếu không có [preflight reset] (reset trước khi chạy), GPU có thể bắt đầu ở xung thấp và không được nâng do điều kiện gating nói trên, dẫn đến hashrate thấp kéo dài.

- Lưu ý bằng chứng còn thiếu: Chưa có log [perf cap reasons] (Pwr/Thrm/VRel/VOp/Util) và P-state trực tiếp; cần bổ sung để khẳng định lý do cap.


## 5. Tree-of-Thought (Giả thuyết → chọn hướng)

- Giả thuyết và chấm điểm (Impact / Likelihood / Effort):
  - [Application clocks persistence] (khóa xung vẫn hiệu lực): 5 / 4 / 2 → Ưu tiên P1
  - [Power limit stickiness] (giới hạn công suất dính): 4 / 3 / 2
  - [Faulty reset order] (thứ tự reset sai/không tất định): 5 / 4 / 3 → Ưu tiên P1
  - [Driver persistence mode interaction] (context driver giữ cấu hình): 4 / 4 / 1
  - [Thermal hysteresis] (quán tính nhiệt, P-state thấp): 2 / 2 / 1 (ít phù hợp vì nhiệt độ thấp ổn định)
  - [Race condition] (điều kiện đua giữa miner/optimizer): 4 / 3 / 3
  - [Cloaking side-effects] (tác dụng phụ cloaking): 3 / 3 / 3
  - [Silent error handling] (bắt lỗi im lặng): 3 / 3 / 2

- Nhánh ưu tiên đào sâu: 
  - P1: [Application clocks persistence] + [Faulty reset order] dưới ảnh hưởng [persistence mode].


## 6. Recommendations (Quick Wins → Hardening)

- Quick Wins (Get It Working First):
  - [Preflight Reset] (reset trước khi mining) trong `start_mining.py`: gọi chuỗi reset tất định (unlock clocks → reset application clocks → set power limit default) cho tất cả GPU trước khi khởi chạy miner, có log before/after.
  - Vô hiệu hóa điều kiện “skip locking if SM<800 MHz khi closed-loop tắt” trong giai đoạn phục hồi ban đầu, hoặc bật closed-loop ngắn hạn để nâng xung về ngưỡng hoạt động trước khi áp điều kiện bảo vệ.
  - Thêm log P-state ([nvmlDeviceGetPerformanceState]) và (nếu có) [perf cap reasons] qua [nvidia-smi -q] để quan sát nguyên nhân cap.

- Hardening (Measure Twice, Cut Once):
  - [Single Source of Truth] trong `resource_control.py`: mọi set/reset qua một lớp duy nhất (NVML-đầu tiên, `nvidia-smi` chỉ fallback), tránh tuần tự lẫn lộn.
  - Thứ tự tất định: reset → apply base (power/clocks an toàn) → start miner → closed-loop nâng xung dần nếu cần → lock xác nhận (tuỳ chọn) → hẹn [cleanup on exit].
  - [Guardrails & Rollback]: nếu bất kỳ bước apply thất bại, rollback ngay (không để trạng thái trung gian); log nguyên văn ngoại lệ + snapshot GPU.
  - [Exit Cleanup] bảo đảm restore state khi thoát (kể cả có lỗi, SIGTERM/SIGINT).
  - [Cloak Isolation]: `cloak_strategies.py` không chạm NVML trực tiếp; chỉ thông qua `resource_control.py`.


## 7. Refactor Plan (không tạo module mới, không đổi cấu trúc)

- `app/start_mining.py`:
  - Bổ sung pha [Preflight Reset] đồng bộ cho toàn bộ GPU trước khi gọi miner/ResourceManager: unlock clocks (`-rgc`/`--reset-memory-clocks`) → [nvmlDeviceResetApplicationsClocks] → đặt power limit default → xác thực before/after.
  - Hook [cleanup on exit] (signal handler) đảm bảo gọi restore cuối cùng (không phụ thuộc idle-gate).

- `mining_environment/scripts/resource_control.py`:
  - Gom mọi set/reset vào một pipeline NVML-first; chỉ dùng [nvidia-smi] khi NVML không đủ; chuẩn hóa “unlock→NVML reset→power default→verify”.
  - Loại bỏ/giảm điều kiện skip-lock khi `current_sm_clock < 800` trong giai đoạn phục hồi; thay bằng “nâng xung dần” có giới hạn an toàn.
  - Ghi log P-state và (nếu có) “cap reason” mỗi lần apply/reset.

- `mining_environment/scripts/gpu_optimization_orchestrator.py`:
  - Khi `optimize_gpu_for_process`, nếu chưa xác định GPU mapping, tránh broadcast; chỉ tối ưu khi có `gpu_index` chắc chắn hoặc sau preflight.
  - Bật closed-loop ngắn (ví dụ ≤ 25s) để thoát bẫy xung thấp trước khi vào steady-state.

- `mining_environment/scripts/setup_env.py`:
  - Cho phép tắt [persistence mode] bằng ENV (mặc định bật) và log trạng thái; nếu bật, buộc [cleanup on exit] chạy để đảm bảo không “dính” state.


## 8. Risks & Rollback (Rủi ro & hoàn nguyên)

- Rủi ro: reset/lock sai thứ tự có thể gây xung đột; nếu đang bật [persistence mode], state có thể tồn tại qua nhiều vòng.
- Giảm thiểu: xác lập thứ tự tất định, log before/after và trạng thái xác minh; nếu bước bất kỳ thất bại, rollback ngay về default (power limit default, reset application clocks).


## 9. Open Questions (Thiếu chứng cứ cần bổ sung)

- Chưa có log [perf cap reasons] (Pwr/Thrm/VRel/VOp/Util) – đề nghị thêm: `nvidia-smi -q -d PERFORMANCE` định kỳ hoặc NVML tương đương; log P-state qua [nvmlDeviceGetPerformanceState].
- Xác thực quyền root (đã có cảnh báo không chạy root); một số thao tác NVML/CLI có thể yêu cầu quyền cao → cần log pass/fail chi tiết khi set/reset.
- So khớp power limit (limit đặt) vs power usage (công suất đo) để phân biệt “không thể boost” do xung/p-state hay do giới hạn điện.


## 10. Appendix: Trích dẫn log & code (verbatim)

- Log clocks/power/temp và hashrate:

```279:281:/app/mining_environment/logs/stealth_inference_cuda.log
2025-09-01 17:45:24,224 - ... [nvidia  #0 00:00.0  75W 38C 405/877 MHz]
2025-09-01 17:45:24,225 - ... [miner   speed 10s/60s/15m 11.10 n/a n/a MH/s max 11.10 MH/s]
```

```452:453:/app/mining_environment/logs/stealth_inference_cuda.log
2025-09-01 17:46:24,274 - ... [nvidia  #0 00:00.0  75W 38C 412/877 MHz]
2025-09-01 17:46:24,275 - ... [miner   speed 10s/60s/15m 11.26 11.27 n/a MH/s max 11.35 MH/s]
```

```994:995:/app/mining_environment/logs/stealth_inference_cuda.log
2025-09-01 17:49:24,433 - ... [nvidia  #0 00:00.0  71W 38C 442/877 MHz]
2025-09-01 17:49:24,433 - ... [miner   speed 10s/60s/15m 11.17 11.17 n/a MH/s max 11.35 MH/s]
```

- Bật [persistence mode] trong setup:

```363:367:/app/mining_environment/scripts/setup_env.py
if str(os.getenv('ENABLE_PERSISTENCE_MODE_ON_SETUP', '1')).lower() in ('1','true','yes'):
    _run_smi(['nvidia-smi','-pm','1'], logger, "Enable persistence mode")
```

- Đặt [power limit] bằng NVML:

```875:882:/app/mining_environment/scripts/resource_control.py
new_limit_mw = power_limit_w * 1000
pynvml.nvmlDeviceSetPowerManagementLimit(handle, new_limit_mw)
...
self._last_power_limit_w[gpu_index] = power_limit_w
```

- Khóa xung bằng [nvidia-smi] và restore tuần tự:

```961:977:/app/mining_environment/scripts/resource_control.py
cmd_sm = ['nvidia-smi','-i', str(gpu_index),'--lock-gpu-clocks=' + str(sm_clock)]
subprocess.run(cmd_sm, check=True)
...
cmd_mem = ['nvidia-smi','-i', str(gpu_index),'--lock-memory-clocks=' + str(mem_clock)]
subprocess.run(cmd_mem, check=True)
```

```1606:1634:/app/mining_environment/scripts/resource_control.py
['nvidia-smi', '-i', str(gpu_index), '-rgc']
['nvidia-smi', '-i', str(gpu_index), '--reset-memory-clocks']
pynvml.nvmlDeviceResetApplicationsClocks(handle)
```

- Điều kiện chặn lock khi SM<800 MHz & closed-loop tắt (cần xem xét nới lỏng trong pha phục hồi):

```930:937:/app/mining_environment/scripts/resource_control.py
if (not cl_enabled) and current_sm_clock < 800:
    self.logger.warning("... skip locking to avoid low-clock trap ...")
    return False
```


---

Ghi chú thuật ngữ (định dạng chuẩn):
- [NVIDIA NVML] (thư viện quản lý GPU ở mức driver)
- [nvidia-smi] (CLI điều khiển/truy vấn GPU – công cụ dòng lệnh NVIDIA)
- [application clocks] (khóa xung ứng dụng – khóa xung core/mem theo giá trị xác định)
- [persistence mode] (chế độ bền bỉ – giữ context driver sống để tránh reset)
- [perf cap reasons] (lý do giới hạn hiệu năng: Pwr, Thrm, VRel, VOp, Util)
- [preflight reset] (reset trước khi chạy – hoàn nguyên trạng thái GPU về mặc định)
- [cleanup on exit] (hoàn nguyên cấu hình khi thoát)
- [Single Source of Truth] (nguồn sự thật duy nhất – điểm tập trung thao tác/state)
- [root cause] (nguyên nhân gốc rễ)
- [evidence] (bằng chứng)
- [actionable recommendations] (khuyến nghị khả thi)
- [race condition] (điều kiện đua)
- [cloaking] (ngụy trang)
- [DirectPIDRegistry] (sổ đăng ký PID trực tiếp)
- [ResourceManager] (trình quản lý tài nguyên)
- [GPUOptimizationOrchestrator] (bộ điều phối tối ưu GPU)
- [OptimizedHardwareController] (bộ điều khiển phần cứng tối ưu)
- [GPUResourceManager] (trình quản lý tài nguyên GPU)
- [stealth wrapper] (trình bao bọc ẩn danh)
- [idempotent reset] (reset lặp lại cho kết quả như nhau)
```
