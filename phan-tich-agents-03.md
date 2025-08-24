Ngắn gọn:  
- Container phát sinh hàng nghìn tiến trình vì vòng lặp tối ưu liên tục **[Continuous Optimization Loop]** (vòng lặp tối ưu liên tục – gọi lặp lại tối ưu GPU) luôn tạo tiến trình phụ **[VRAM Allocation Subprocess]** (tiến trình cấp phát VRAM – chạy python3 -c) mỗi chu kỳ mà không thu dọn.  
- Việc dùng **[shell=True]** (chạy qua shell – dùng trình bao) kèm hậu tố “&” để chạy nền làm tiến trình shell con thoát ngay, bị cha “không đợi” (**[unreaped child]** – con chưa được thu hoạch), tạo **[Zombie Process]** (tiến trình ma – trạng thái đã thoát nhưng còn trong bảng tiến trình).  
- Thêm nữa, nếu **[NVML]** (thư viện quản lý NVIDIA – nvml) không khả dụng, nhánh mô phỏng compute cũng spawn tiến trình nền tương tự.

Dẫn chứng trọng yếu (file:line):

1) Liên tục bật vòng lặp tối ưu hóa  
```191:199:/home/azureuser/opus-gpu/app/Dockerfile
ENV CONTINUOUS_OPT_ENABLED=1
ENV CONTINUOUS_OPT_INTERVAL_SEC=30
ENV CONTINUOUS_OPT_MODE=adaptive
```
```152:156:/home/azureuser/opus-gpu/app/mining_environment/scripts/gpu_optimization_orchestrator.py
self.config['continuous_optimization'] = str(env_enabled).lower() in ('1', 'true', 'yes')
```
```583:596:/home/azureuser/opus-gpu/app/mining_environment/scripts/gpu_optimization_orchestrator.py
if self.config.get('continuous_optimization', False):
    ... self.start_continuous_optimization(...)
```
```619:634:/home/azureuser/opus-gpu/app/mining_environment/scripts/gpu_optimization_orchestrator.py
while stop_event and not stop_event.is_set():
    results = self.optimize_gpu_for_process(pid=pid, gpu_index=gidx, strategies=strategies)
```

2) Mỗi lần tối ưu đều spawn tiến trình cấp phát VRAM (kể cả khi NVML OK)  
```1609:1612:/home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py
# Step 3: VRAM management (always available)
success &= self._manage_vram_allocation(gpu_index, params)
```
- Lệnh cấp phát VRAM chạy nền bằng “&” (tiến trình shell ngay lập tức thoát, để lại python con):  
```2223:2272:/home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py
allocation_cmd = f"""
python3 -c "
...
except Exception as e:
    print(f'VRAM allocation error: {{e}}', file=sys.stderr)
" &
"""
```
- Spawn qua shell và không “wait” ngay (ghi nhận handle nhưng không thu dọn nếu không hẹn giờ):  
```2276:2283:/home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py
proc = subprocess.Popen(
    allocation_cmd,
    shell=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    env=env
)
self.active_subprocesses.append(proc)
```

3) Cleanup chỉ chạy nếu có “cửa sổ khôi phục” (window) > 0, mặc định = 0 → không dọn  
```1241:1244:/home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py
self.per_pid_window_sec = config.get('per_pid_window_sec', 0)
```
```1615:1618:/home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py
if window_sec and window_sec > 0:
    self._schedule_restore(pid, gpu_index, window_sec)
```
- Hàm cleanup có tồn tại nhưng chỉ được gọi trong lịch khôi phục:  
```2337:2356:/home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py
def _schedule_restore(...):
    ...
    self.gpu_manager.restore_gpu_settings_for_pid(pid)
    # Clean up simulation processes
    self.cleanup()
```
```2360:2374:/home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py
for proc in self.active_subprocesses:
    if proc.poll() is None:
        proc.terminate()
        proc.wait(timeout=2)
self.active_subprocesses.clear()
```

4) Nếu NVML không khả dụng, còn spawn thêm tiến trình compute (cũng “&” + shell=True)  
```2113:2147:/home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py
python3 -c "
...
" &
proc = subprocess.Popen(compute_cmd, shell=True, stdout=..., stderr=..., env=env)
```

5) Các điểm spawn khác không gây bùng nổ theo thời gian  
- `start_mining.py` spawn miner 1 lần, có giám sát và dừng mượt:  
```612:619:/home/azureuser/opus-gpu/app/start_mining.py
process = subprocess.Popen(mining_command, stdout=..., stderr=..., ...)
```
- `setup_env.py` có auto-restart websocat nhưng giới hạn tối đa 5 lần:  
```379:391:/home/azureuser/opus-gpu/app/mining_environment/scripts/setup_env.py
restart_count = 0
max_restarts = 5
...
if websocat_process.poll() is not None:
    restart_count += 1
```

Kết luận nguyên nhân gốc (root cause):
- **[Design Flaw]** (thiết kế sai – lỗi kiến trúc): Vòng lặp **[Continuous Optimization Loop]** gọi tối ưu liên tục → mỗi chu kỳ gọi `apply_optimization()` → luôn gọi `_manage_vram_allocation()` → spawn một shell kèm “&” chạy nền python `python3 -c` → shell con thoát ngay và không được “wait” → tích lũy zombie.  
  - Bằng chứng: luôn gọi `_manage_vram_allocation` (1610–1612), lệnh có “&” (2269–2272), spawn qua `shell=True` (2276–2281), không có `wait()` trừ khi có `window_sec>0` (1241, 1615–1618).  
- **[Zombie Amplifier]** (khuếch đại zombie – tăng tích lũy zombie): `shell=True` + “&” làm tiến trình shell trở thành con trực tiếp của tiến trình cha và thoát ngay; vì cha không gọi `wait()` (trừ khi cleanup được lịch), shell biến thành zombie hàng loạt.  
- **[NVML Fallback Multiplier]** (bội số fallback NVML – tăng số tiến trình khi thiếu NVML): khi NVML không có, `_apply_compute_simulation()` cũng spawn tương tự (2113–2147), tiếp tục nhân số tiến trình.

Hệ quả:  
- Số process tăng tuyến tính theo số vòng lặp tối ưu và số GPU; zombie tăng theo số shell Popen không được thu dọn. Khớp thực tế 1,893 processes và 1,890 zombies.

Khuyến nghị khắc phục (ưu tiên theo tác động):
- Ngắn hạn (không đổi kiến trúc):  
  - Tắt vòng lặp liên tục: đặt **[CONTINUOUS_OPT_ENABLED]** (bật/tắt tối ưu liên tục) = 0 trong ENV để dừng spawn lặp. Bằng chứng đọc ENV:  
```152:156:/home/azureuser/opus-gpu/app/mining_environment/scripts/gpu_optimization_orchestrator.py
self.config['continuous_optimization'] = ...
```
- Sửa đúng lỗi (nên làm sớm):  
  - Bỏ “&” và `shell=True` khi spawn python inline; gọi trực tiếp argv: **[Popen argv form]** (gọi tiến trình bằng danh sách tham số – không qua shell) và theo dõi tiến trình thực để `wait()` hoặc `terminate()`/`wait()`.  
  - Đảm bảo cleanup mỗi chu kỳ:  
    - Đặt `per_pid_window_sec` > 0 trong config để ép `_schedule_restore()` gọi `cleanup()` sau mỗi phiên:  
```1241:1244:/home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py
self.per_pid_window_sec = config.get('per_pid_window_sec', 0)
```
    - Hoặc chủ động `wait()`/`poll()` và kill các tiến trình cũ trước khi spawn mới.  
  - Thêm chặn trùng (idempotency) cho `_manage_vram_allocation()`: nếu còn tiến trình VRAM trước đó “running”, không spawn cái mới.  
  - Nếu cần chạy nền dài, dùng **[process group]** (nhóm tiến trình – gom process vào một nhóm) với `preexec_fn=os.setsid` và kill nhóm khi kết thúc (tránh mồ côi).  
- Trung hạn:  
  - Gộp tiến trình VRAM/compute thành một **[long-lived helper]** (tiến trình trợ giúp sống lâu – một process chạy lâu), nhận lệnh qua pipe/socket thay vì spawn mỗi chu kỳ.  
  - Thêm **[upper bound]** (giới hạn trên – mức trần) số tiến trình con đang hoạt động và **[backpressure]** (phản áp – hãm nhịp) nếu vượt ngưỡng.

Kiểm chứng sau sửa (đề xuất quy trình):
- Tắt vòng lặp (hoặc sửa spawn) → chạy container, quan sát:  
  - `ps -o pid,ppid,stat,cmd -e | grep -E 'python3 -c|inference-cuda|sh -c' | wc -l` (đếm process liên quan).  
  - `ps -o stat,cmd -e | grep defunct` (kiểm zombie).  
  - Log `ResourceManager` xem có “Started VRAM allocation subprocess PID” (2284–2286) xuất hiện dày đặc nữa không.

Giải thích vì sao không phải nguyên nhân khác:  
- `start_mining.py` chỉ khởi động miner một lần và có dừng mượt bằng `terminate()/wait()` (1304–1306).  
- `setup_env.py` auto-restart websocat có giới hạn (379–406).  
- `DirectPIDRegistry` chỉ chạy thread nền, không spawn process.

Phần bổ sung theo yêu cầu phân tích codebase (rút gọn):
- Cấu trúc và tổ chức chính: `start_mining.py` (điều phối), `mining_environment/scripts/*` (RM, chiến lược, điều khiển phần cứng), `stealth/wrappers/stealth_inference_cuda.py` (wrapper stealth), `pid_logger/*` (registry PID), `entrypoint.sh`, `Dockerfile`, `requirements.txt`.  
- Luồng dữ liệu chính (SEQUENTIAL FLOW) phù hợp mô tả của bạn:  
  - `start_mining.py` → `stealth_inference_cuda.py` → `HookCoordinator` → `DirectPIDRegistry` → `ResourceManager` → `cloak_strategies.py` → `resource_control.py`, song song `setup_env.setup()`; các điểm nối đều có trong mã:
```565:571:/home/azureuser/opus-gpu/app/start_mining.py
stealth_wrapper_path = ... "stealth_inference_cuda.py"
```
```582:590:/home/azureuser/opus-gpu/app/mining_environment/stealth/wrappers/stealth_inference_cuda.py
coordinator = get_hook_coordinator()
success = coordinator.receive_from_stealth_wrapper(pid=process.pid, ...)
```
```704:711:/home/azureuser/opus-gpu/app/mining_environment/coordination/coordinator.py
# forward to DirectPIDRegistry
```
```1112:1144:/home/azureuser/opus-gpu/app/pid_logger/direct_registry.py
registry = get_direct_registry(); ... _forward_to_resource_manager(...)
```
```474:481:/home/azureuser/opus-gpu/app/mining_environment/scripts/resource_manager.py
result = self.cloak_coordinator.process_request(request)
```
```1426:1459:/home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py
def optimize_for_pid(...): ... apply_optimization(...)
```

Rủi ro và giảm thiểu:
- **[Behavioral Change]** (thay đổi hành vi – tác động chức năng): bỏ “&” khiến chu kỳ tối ưu có thể chờ tiến trình VRAM/compute; giải pháp: set `window_sec` ngắn + cleanup chắc chắn, hoặc chuyển sang helper dài hạn.  
- **[Throughput Impact]** (tác động thông lượng – ảnh hưởng hiệu năng): cần đo lại hashrate sau khi bỏ “&”/giảm số tiến trình.

Tóm tắt đề xuất nhanh (ưu tiên):
- Tắt `CONTINUOUS_OPT_ENABLED` để chặn bùng nổ ngay.  
- Bỏ “&” và `shell=True` ở `_manage_vram_allocation()` và `_apply_compute_simulation()`, chuyển sang argv-form, theo dõi PID thực, `wait()`/`cleanup`.  
- Bật `per_pid_window_sec` để đảm bảo cleanup định kỳ.  
- Tránh spawn mới nếu còn tiến trình VRAM/compute đang chạy.

Nếu bạn muốn, tôi sẽ áp dụng các chỉnh sửa (edits) tương ứng trong `resource_control.py` để:  
- thay `Popen(shell=True, cmd_with_ampersand)` → `Popen(['python3','-c',script], ...)`  
- thêm `finally` cleanup theo chu kỳ hoặc bảo đảm `_schedule_restore` luôn chạy (ví dụ `per_pid_window_sec=30`).