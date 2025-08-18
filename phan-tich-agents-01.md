

# Findings

- __Giá trị 50% bị cố định ở Orchestrator__  
  - [GPUOptimizationOrchestrator._acquire_gpu_resources()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/gpu_optimization_orchestrator.py:782:4-834:24) gọi [request_resource(... amount=50.0)](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:942:4-1014:20) cho `GPU_COMPUTE` (request tài nguyên tính toán GPU)  
    - Trích dẫn: `app/mining_environment/scripts/gpu_optimization_orchestrator.py:799-804`  
    - Hệ quả: mỗi tiến trình chỉ xin 50% “compute quota” (hạn mức compute – giới hạn DAL), khiến tổng cộng 2 tiến trình là 100%, dễ “khóa” cấu hình ở mức ~50% sử dụng thực tế nếu không đủ song song.
- __Semaphore per-request gây “double-acquire” cho cùng PID/GPU__  
  - [CrossProcessCoordinator.request_resource()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:942:4-1014:20) luôn [acquire()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:138:4-168:20) semaphore cho MỖI lần xin tài nguyên (một lần cho compute, một lần cho memory).  
    - Trích dẫn: `app/mining_environment/scripts/cross_process_coordination.py:959-973`  
    - [GPUSemaphore.acquire()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:138:4-168:20) ghi log “Semaphore acquired … (x/y)”  
      - Trích dẫn: `app/mining_environment/scripts/cross_process_coordination.py:139-161`
  - Vì `max_count=2`/GPU, một tiến trình khi xin compute + memory sẽ chiếm 2 “slot” cùng lúc → chặn tiến trình khác, tạo timeout.  
    - Cấu hình semaphore mặc định: `max_count=2`  
      - Trích dẫn: `app/mining_environment/scripts/cross_process_coordination.py:741-744` (khởi tạo theo số GPU NVML) và fallback `:748-752`
- __Log khẳng định mô hình trên và chu kỳ timeout__  
  - Ví dụ:  
    - “acquired (1/2)” → “Resource reserved … gpu_compute 50.0%” → ngay sau đó “acquired (2/2)” → lại “Resource reserved … gpu_compute 50.0%”  
      - Trích dẫn log: `app/mining_environment/logs/coordination.log:56-61` và `:69-71`  
    - Liên tục “⏱️ Semaphore timeout” sau khi đủ 2/2 slot bị chiếm  
      - Trích dẫn log: `app/mining_environment/logs/coordination.log:62-68, 72-73, 82-83`  
  - Ghi log “Resource reserved” do [ResourceReservationManager.reserve_resource()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:235:4-269:23) (in ra amount%)  
    - Trích dẫn: `app/mining_environment/scripts/cross_process_coordination.py:267-270`

## Nguyên nhân cốt lõi

- __Quota compute cố định 50%__ ở orchestrator: `amount=50.0` (`gpu_optimization_orchestrator.py:799-804`).  
- __Thiết kế semaphore “per-request”__ (mỗi request tài nguyên đều acquire) → cùng một PID xin `GPU_COMPUTE` và `GPU_MEMORY` sẽ chiếm 2 slot trên cùng GPU, trong khi `max_count=2` (`cross_process_coordination.py:741-744` và `:959-973`).  
- Kết quả: dễ xảy ra serialize/throttle và timeout, làm GPU không đạt >90% như mong đợi, quan sát trung bình ~50%.

# Recommended Actions

- __Ngắn hạn (không đổi code hoặc đổi tối thiểu)__  
  - __Tham số hóa phần trăm compute qua ENV__ tương tự `COORD_GPU_MEMORY_PCT`:  
    - Thêm `COORD_GPU_COMPUTE_PCT` và thay `amount=50.0` bằng đọc ENV (chấp nhận 0..1 hoặc 0..100 như memory).  
    - Vị trí sửa: `gpu_optimization_orchestrator.py:799-804`.  
    - Đề xuất giá trị thử: `COORD_GPU_COMPUTE_PCT=100` khi chạy đơn tiến trình để đạt util ~90-100%.
  - __Expose max_count và timeout qua ENV__:  
    - `COORD_GPU_SEM_MAX_COUNT` → truyền vào [GPUSemaphore(..., max_count=ENV)](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:101:0-181:51) thay vì cố định 2.  
    - `COORD_SEM_TIMEOUT_SEC` → thay tham số `timeout` mặc định khi [request_resource()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:942:4-1014:20) gọi [acquire()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:138:4-168:20).  
    - Vị trí: `cross_process_coordination.py:741-744` (khởi tạo), `:959-973` (timeout).
- __Trung hạn (sửa logic để giảm timeout)__  
  - __Re-entrant semaphore per PID/GPU (tránh double-acquire)__:  
    - Duy trì `self._sem_hold_counts[gpu_index]` trong [CrossProcessCoordinator](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:688:0-1083:102).  
    - Trong [request_resource()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:942:4-1014:20) (`cross_process_coordination.py:959-973`):  
      - Nếu `hold_count[gpu_index] == 0` mới [acquire()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:138:4-168:20).  
      - Tăng `hold_count` mỗi request (compute/memory).  
      - Nếu request bị DENY/timeout, giảm `hold_count` và chỉ [release()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:170:4-181:51) khi về 0.  
    - Trong [release_resource()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:1016:4-1049:22) (`cross_process_coordination.py:1017-1050`):  
      - Giảm `hold_count` và chỉ [release()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:170:4-181:51) semaphore khi về 0.  
    - Mục tiêu: 1 tiến trình giữ tối đa 1 slot/ GPU, dù xin nhiều loại tài nguyên.
  - __Tùy chọn__: cho phép tiếp tục “compute-only” nếu `GPU_MEMORY` xin thất bại thay vì hủy compute ngay (giảm chu kỳ reacquire). Vị trí: orchestrator khi `memory_acquired=False` (`gpu_optimization_orchestrator.py:820-826`).
- __Chẩn đoán & logging__  
  - Ghi rõ `pid` khi acquire/release semaphore để đối chiếu dễ hơn (hiện [GPUSemaphore.acquire()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:138:4-168:20) không log PID).  
  - Ghi tổng “compute usage” theo [get_resource_usage()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/cross_process_coordination.py:305:4-318:68) để theo dõi phân bổ:  
    - Vị trí: `cross_process_coordination.py:306-319` (đã có hàm), log tại monitor loop (`:753-778`).

# Kế hoạch kiểm thử (đo util >90%)

- __Case A: đơn tiến trình__  
  - Set `COORD_GPU_COMPUTE_PCT=100`, `COORD_GPU_SEM_MAX_COUNT=1`.  
  - Chạy một job → xác nhận không còn timeout trong log và util ~95-100%.
- __Case B: 2 tiến trình song song__  
  - Bật sửa “re-entrant semaphore”; set `COORD_GPU_COMPUTE_PCT=50`, `COORD_GPU_SEM_MAX_COUNT=2`.  
  - Chạy 2 job song song → kỳ vọng không còn chiếm 2/2 slot bởi 1 PID khi xin thêm memory; giảm timeout đáng kể; tổng util tiệm cận ~90-100% khi workload đủ.
- __Giám sát__  
  - Theo dõi [coordination.log](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/logs/coordination.log:0:0-0:0) và [mining_debug.log](cci:7://file:///home/azureuser/opus-gpu/app/mining_debug.log:0:0-0:0) (đã thấy mẫu ở: `app/mining_debug.log:1023-1031, 1226-1232, 1728-1743`) để xác thực giảm timeout.

# Trích dẫn chính

- Orchestrator cố định 50%: `app/mining_environment/scripts/gpu_optimization_orchestrator.py:799-804`  
- Acquire per-request (gây double-acquire): `app/mining_environment/scripts/cross_process_coordination.py:959-973`  
- Semaphore logs: acquire `:139-161`, release `:171-181`  
- Khởi tạo `max_count=2`: `:741-744` (và fallback `:748-752`)  
- Log “Resource reserved … 50.0%”: `:267-270`  
- Timeout log (thực tế): `app/mining_environment/logs/coordination.log:62-68, 72-73, 82-83`

# Recommended Next Actions

- __[nt4]__ Tham số hóa `COORD_GPU_COMPUTE_PCT` ở orchestrator (giống memory).  
- __[nt5]__ Thêm cơ chế re-entrant semaphore per PID/GPU để tránh double-acquire compute+memory.  
- __[nt6]__ Expose `COORD_GPU_SEM_MAX_COUNT` và `COORD_SEM_TIMEOUT_SEC`; bổ sung logging tổng usage.  
- __[nt7]__ Chạy bộ test A/B như trên để xác nhận util >90%.

Tôi sẵn sàng tạo patch cho 3 hạng mục [nt4][nt5][nt6] ở các vị trí đã chỉ rõ, khi bạn bật đèn xanh.

Tóm tắt trạng thái
- Đã xác định nguyên nhân 50% và timeout bằng trích dẫn file:line.  
- Đã cập nhật TODO: nt1, nt2, nt3 hoàn tất; nt4–nt7 đang pending.  
- Sẵn sàng triển khai sửa nhanh (param compute pct, re-entrant semaphore, cấu hình semaphore qua ENV) để tăng util.