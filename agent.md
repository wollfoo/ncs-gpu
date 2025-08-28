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

