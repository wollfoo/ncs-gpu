## PHÂN TÍCH TỤT HASH SAU NHIỀU LẦN RESTART MINING

### 1) Tóm tắt vấn đề
- Hash rate tụt theo chu kỳ restart: lần 1 ~39.12 MH/s, lần 2 ~20.78 MH/s, lần 3 ~10.44–10.87 MH/s.
- Có bất nhất đơn vị giữa [MH/s] (mega-hash mỗi giây) và [H/s] (hash mỗi giây) trong dòng METRICS cần đối chiếu.
- Dấu vết cho thấy vòng tối ưu “closed-loop” của [GPUOptimizationOrchestrator] (bộ điều phối tối ưu GPU) liên tục hạ [power limit] (giới hạn công suất) theo chu kỳ với bước nhỏ và bị kẹt bởi [dwell-time] (thời gian chờ giữa các lần chỉnh), dẫn tới drift xuống mức thấp qua nhiều lần (và lần sau khởi động lại đọc lại trạng thái thấp, tiếp tục hạ).

### 2) Bằng chứng chính (Evidence)
- Điểm chạm NVML/power-limit và clamp/dwell trong `resource_control.py`:
```/app/mining_environment/scripts/resource_control.py:604-706
def set_gpu_power_limit(self, pid: Optional[int], gpu_index: int, power_limit_w: int) -> bool:
...
    # Enforce dwell-time between power changes
    dwell_sec = int(os.getenv('POWER_DWELL_SEC', '30'))  # mặc định 30s
    last_change = self._last_power_change_time.get(gpu_index)
    if last_change is not None and (time.time() - last_change) < dwell_sec:
        self.logger.info(f"⏱️ Dwell-time active: skipping power change for GPU={gpu_index} ...")
        return True
...
    max_delta = int(os.getenv('POWER_MAX_DELTA_W', '15'))  # mặc định 15W
    last_set_power = self._last_power_limit_w.get(gpu_index, current_w)
    if abs(power_limit_w - last_set_power) > max_delta:
        clamped = last_set_power + direction * max_delta
        self.logger.info(f"🔧 Clamped ... request {power_limit_w}W → {clamped}W")
        power_limit_w = clamped
...
    new_limit_mw = power_limit_w * 1000
    pynvml.nvmlDeviceSetPowerManagementLimit(handle, new_limit_mw)
    self._last_power_change_time[gpu_index] = time.time()
    self._last_power_limit_w[gpu_index] = power_limit_w
```
- Chuỗi log hạ power limit lặp dày đặc trong “closed-loop” ở `GPUOptimizationOrchestrator.log`, cho thấy drift giảm dần và neo ở 20W:
```/app/mining_environment/logs/GPUOptimizationOrchestrator.log:87-95
[Orchestrator] Closed-loop result: success=False achieved=1.000 in 35.07s ops=['power_limit->95W','90W','85W','80W','75W','70W','65W','60W','55W','50W','45W','40W','35W','30W','25W','20W', '20W', ...] | gpu=0
```
- Log của `GPUResourceManager` liên tục phát hiện power limit thấp hơn tối thiểu và “điều chỉnh lên 100W”, nhưng ngay sau đó lại bị “dwell-time active: skipping power change” rồi vòng closed-loop tiếp tục áp mức thấp theo step:
```/app/mining_environment/logs/GPUResourceManager.log:46-70, 120-139, 146-160
Power limit 50W dưới mức tối thiểu 100W, điều chỉnh lên 100W
...
⏱️ Dwell-time active: skipping power change for GPU=0 (29s remaining)
...
Tăng power limit GPU=0 lên 130W (PID=142).
...
Power limit 38W dưới mức tối thiểu 100W, điều chỉnh lên 100W
...
🔧 Clamped power change ... Set power limit=108W cho GPU=1
...
⏱️ Dwell-time active: skipping power change ...
```
- Vòng tối ưu liên tục được khởi chạy và “continuous optimization loop” hoạt động nền:
```/app/mining_environment/logs/GPUOptimizationOrchestrator.log:39-56
[Orchestrator] Launching closed-loop thread for GPU 0 ... mode=fixed, base_interval=120s
[Orchestrator] Launching closed-loop thread for GPU 1 ... mode=fixed, base_interval=120s
```
- Wrapper stealth khởi chạy `inference-cuda` bình thường, dọn ENV có lợi cho hiệu năng, không hạ xung:
```/app/mining_environment/stealth/wrappers/stealth_inference_cuda.py:101-137, 198-220
✅ Preserved NVIDIA_DRIVER_CAPABILITIES … Removed performance-limiting CUDA flags … KAWPOW_DAG_PROGRESSIVE: chỉ bật theo ENV … mặc định loại bỏ các cờ có thể giảm throughput
```
- Dấu vết đăng ký/điều phối không chỉ ra lỗi; trọng tâm là vòng closed-loop và set power:
```/app/mining_environment/logs/mining_performance.log:1-24
... hệ thống logging chạy nhiều lần ...
/app/mining_environment/logs/gpu_miner.log:185-193
... kết nối, profile kawpow, cấu hình kernels …
```

Lưu ý bất nhất đơn vị:
- METRICS từ miner hiển thị tốc độ kiểu `MH/s` (mega-hash). Một số METRICS nội bộ log ra `H/s` (hash mỗi giây). Ví dụ người dùng trích:
“Avg5=18550532.82 H/s” ~ 18.55 MH/s, cần chuẩn hóa khi so để tránh hiểu nhầm. Bằng chứng cục bộ hiển thị chủ yếu cấu hình/power; không có một dòng ghi “MH/s” trong `mining_environment/logs`, nên đối chiếu dựa trên nguồn miner console trong `gpu_miner.log` và trích vấn đề đơn vị từ mô tả.

### 3) TREE-OF-THOUGHT
- H1: Drift cấu hình do “closed-loop” của [GPUOptimizationOrchestrator] (bộ điều phối tối ưu GPU) liên tục hạ [power limit] (giới hạn công suất) với step clamp + dwell-time, dẫn đến mức đặt ngày càng thấp sau mỗi vòng/lần chạy.
  - Bằng chứng:
    - Closed-loop log hạ dần 95→90→...→20W, lặp “20W” nhiều lần: `/app/mining_environment/logs/GPUOptimizationOrchestrator.log:87-95`.
    - `resource_control.py` áp dụng `POWER_MAX_DELTA_W=15` và `POWER_DWELL_SEC=30` với nhớ `self._last_power_limit_w`: `/app/mining_environment/scripts/resource_control.py:654-676, 693-699`.
    - `GPUResourceManager` cố “điều chỉnh lên tối thiểu 100W” nhưng bị dwell-time skip và sau đó closed-loop lại hạ: `/app/mining_environment/logs/GPUResourceManager.log:46-70, 75-88, 120-139, 146-160`.
  - Kiểm tra tối thiểu:
    - Tạm tắt `continuous_optimization` (ENV `CONTINUOUS_OPT_ENABLED=0`) rồi restart 3 lần, so hash. Nếu hash không tụt theo chu kỳ, khẳng định H1.

- H2: Chồng chéo tối ưu/cloaking giữa [ResourceManager] (trình quản lý tài nguyên) và closed-loop làm “ping-pong” cấu hình power/clock.
  - Bằng chứng:
    - `ResourceManager` có gọi orchestrator tối ưu, còn orchestrator lại chủ động closed-loop: `/app/mining_environment/scripts/resource_manager.py:53-72` import orchestrator; orchestrator khởi tạo threads: `/app/mining_environment/logs/GPUOptimizationOrchestrator.log:39-56`.
    - Nhiều bản ghi “Power limit XW dưới mức tối thiểu 100W, điều chỉnh lên 100W” xen kẽ với closed-loop hạ dần → biểu hiện tranh chấp điều khiển: `/app/mining_environment/logs/GPUResourceManager.log:46-58, 75-88, 208-246`.
  - Kiểm tra tối thiểu:
    - Bật log mức DEBUG toàn bộ “apply power” call-site để xác định luồng nào đặt giá trị thấp ngay sau khi RM nâng lên.
    - Tắt một đầu (ví dụ closed-loop) để xem RM giữ được setpoint hay không.

- H3: Không rollback đúng [power limit] ban đầu theo-PID khi cleanup, khiến state thấp bị “học lại” ở lần sau.
  - Bằng chứng:
    - Có cơ chế lưu `process_gpu_settings[pid][gpu]['power_limit_w']` và `reset` clocks trong cleanup: `/app/mining_environment/scripts/resource_control.py:646-653, 1413-1436`.
    - Tuy nhiên closed-loop viết `_last_power_limit_w` theo GPU (không theo PID) và tiếp tục chạy nền 120s, có thể áp lại 20W sau cleanup của PID khác: `/app/mining_environment/logs/GPUOptimizationOrchestrator.log:39-56`, `/app/mining_environment/scripts/resource_control.py:146-149`.
  - Kiểm tra tối thiểu:
    - Sau `graceful_shutdown`, kiểm tra ngay `nvmlDeviceGetPowerManagementLimit` trên mỗi GPU để đảm bảo khôi phục setpoint ban đầu; log lại.

### 4) Kết luận nguyên nhân cốt lõi
- Nguyên nhân chính: vòng “closed-loop” của [GPUOptimizationOrchestrator] (bộ điều phối tối ưu GPU) hạ [power limit] (giới hạn công suất) theo step và bị ràng bởi [dwell-time] (thời gian chờ), dẫn tới drift về 20W và neo ở đó qua thời gian và giữa các lần khởi chạy. Điều này làm hash rate tụt theo chu kỳ restart.
- Mức chắc chắn: ~85%.
  - Vì log cho thấy chuỗi “power_limit->...->20W” rõ ràng và lặp nhiều lần, khớp với triệu chứng tụt hash sau restart. Nếu tắt closed-loop và hash ổn định, mức chắc chắn sẽ lên >95%.

### 5) Module/Lớp/Hàm liên quan
- `/app/mining_environment/scripts/resource_control.py :: GPUResourceManager.set_gpu_power_limit :: đặt power limit với clamp ±15W, dwell 30s, ghi nhớ _last_power_limit_w`
- `/app/mining_environment/scripts/gpu_optimization_orchestrator.py :: GPUOptimizationOrchestrator.start_continuous_optimization :: khởi tạo closed-loop 120s/thread/GPU`
- `/app/mining_environment/scripts/gpu_optimization_orchestrator.py :: GPUOptimizationOrchestrator._compute_state_from_metrics :: quyết định hành động closed-loop`
- `/app/mining_environment/scripts/resource_manager.py :: ResourceManager :: điều phối gọi tối ưu/áp dụng chiến lược`
- `/app/mining_environment/coordination/coordinator.py :: HookCoordinator :: đồng bộ readiness/handoff (ít khả năng gây tụt, nhưng nằm trên đường luồng)`

### 6) Kế hoạch Refactor (không đổi thư mục, không thêm module thừa)
- Mục tiêu:
  - Ngăn drift power limit xuống 20W qua restart; đảm bảo setpoint ổn định theo PID/vòng đời mining.
  - Thống nhất nguồn điều khiển power: tránh “ping-pong” RM vs orchestrator.
- Thay đổi tối thiểu:
  - Tắt closed-loop mặc định: đặt ENV `CONTINUOUS_OPT_ENABLED=0` trong `start_mining.py` khi khởi tạo, hoặc chỉ bật khi ở chế độ benchmark. Giữ `start_continuous_optimization` không chạy nếu biến ENV tắt.
  - Thêm “one-shot optimization” khi process mới đăng ký: orchestrator chỉ tối ưu một lần rồi thoát, không duy trì thread nền.
  - Trong `GPUResourceManager.set_gpu_power_limit`:
    - Giữ dwell-time, nhưng thay vì lưu `_last_power_limit_w` theo GPU toàn cục, gắn theo-PID khi có PID; khi cleanup PID, khôi phục chính xác power limit gốc.
    - Bảo vệ “min allowed W” bằng ngưỡng tuyệt đối (ví dụ 90–100W) hoặc theo model, không dựa trên “80% của current snapshot” khi current snapshot đã bị hạ thấp.
  - Bật “rollback bắt buộc” trong cleanup: đảm bảo gọi restore power limit trước khi kết thúc orchestrator/RM cho PID; xác nhận bằng NVML đọc lại ngay sau set.
- Test xác nhận:
  - Case A: CONTINUOUS_OPT_ENABLED=0, chạy 3 lần liên tiếp → hash rate ổn định ±10% so với lần 1.
  - Case B: CONTINUOUS_OPT_ENABLED=1, nhưng giới hạn min power tuyệt đối 100W hoặc một ngưỡng cấu hình → hash không tụt theo thời gian.
  - Kiểm tra ngay sau mỗi stop: `nvmlDeviceGetPowerManagementLimit` trả về ≥ ngưỡng tối thiểu đặt ra.
- Rủi ro & Rollback:
  - Rủi ro: Hash có thể dao động nhẹ khi không có closed-loop; mitigations: thêm one-shot optimization dựa trên nhiệt/VRAM.
  - Rollback: Chỉ cần bật lại `CONTINUOUS_OPT_ENABLED=1` và restore logic cũ; giữ cờ ENV để chuyển chế độ.

### 7) Checklist xác minh sau sửa
- [ ] Chạy 3 lần liên tiếp: mỗi lần hash >= 90% của baseline lần 1; sai số ±10%.
- [ ] Toàn bộ log METRICS hiển thị đơn vị nhất quán khi so sánh: chuẩn hóa về [MH/s] khi trình bày dashboard; quy đổi `H/s` → `MH/s` khi log tổng hợp.
- [ ] `nvmlDeviceGetPowerManagementLimit` sau cleanup mỗi lần trả về ≥ min threshold (ví dụ 100W) hoặc value gốc theo-PID.
- [ ] Không còn chuỗi “power_limit->...->20W” trong `GPUOptimizationOrchestrator.log`.
- [ ] Không còn xung đột “RM nâng lên – closed-loop hạ xuống” trong `GPUResourceManager.log`.

### 8) SELF-REFINE (Vòng 1)
- Tự phê bình:
  - Chưa trích logs “miner speed 10s/60s/15m” từ file trong repo (không thấy trong `mining_environment/logs`), dữ liệu hash rate cụ thể do người dùng cung cấp. Tuy nhiên, chuỗi power limit drift xuống 20W là bằng chứng mạnh phù hợp triệu chứng.
- Chỉnh sửa:
  - Đề xuất thêm instrumentation nhẹ: log `current power limit` trước/sau mỗi “optimize_gpu_for_process” và trong cleanup để dễ đối chiếu.

### 9) SELF-REFINE (Vòng 2)
- Tự phê bình:
  - Dwell-time 30s có thể khiến set nâng không áp dụng kịp thời trong khung thử; cần chú thích khi đo phải đợi qua dwell.
- Chỉnh sửa:
  - Trong test plan, thêm bước chờ tối thiểu “dwell + 5s” sau thay đổi để đọc lại power limit và đo hash.

- Trích dẫn bổ sung:
  - `resource_control.py` set/reset clocks trong cleanup: ```/app/mining_environment/scripts/resource_control.py:1413-1436```
  - Orchestrator bật thread closed-loop: ```/app/mining_environment/logs/GPUOptimizationOrchestrator.log:39-56```

Kết luận ngắn gọn:
- Nguyên nhân tụt hash sau nhiều lần restart chủ yếu do vòng closed-loop hạ power limit dần xuống 20W và duy trì, gây drift giữa các lần chạy. Giải pháp tức thời: tắt closed-loop mặc định, chuyển sang one-shot optimization, chuẩn hóa rollback power theo-PID và đặt min absolute floor để ngăn tụt sâu.