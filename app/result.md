### 0. Tóm tắt
- Root-Cause Confidence: Cao
- Fix Feasibility: Cao

### 1. TREE-OF-THOUGHT
- Nhánh A: [Missing CUDA Runtime] (thiếu CUDA Runtime) - Có thư viện nhưng sai version (12.0.140 vs 12.0)
- Nhánh B: [GPU Cloaking Plugin Interference] (xung đột GPU Cloaking Plugin) - Plugin hooks có thể chặn access
- Nhánh C: [LD_LIBRARY_PATH Mismatch] (sai LD_LIBRARY_PATH) - Linker không tìm thấy đúng symbolic link
→ Nhánh được chọn: Nhánh A + C (Version mismatch + Library path issue)

### 2. Phân tích & đề xuất khắc phục
1. Nguyên nhân gốc: [NVRTC Version Mismatch] (không khớp version NVRTC) - Ứng dụng tìm `libnvrtc-builtins.so.12.0` nhưng hệ thống có version `12.0.140`, symbolic link bị thiếu.

2. Hướng khắc phục chi tiết:
   ```bash
   # Giải pháp 1: Tạo symbolic link thiếu
   sudo docker exec opus-container bash -c "cd /usr/local/cuda/lib64 && ln -sf libnvrtc-builtins.so.12.0.140 libnvrtc-builtins.so.12.0"
   
   # Giải pháp 2: Cập nhật ldconfig cache
   sudo docker exec opus-container bash -c "ldconfig"
   
   # Giải pháp 3: Kiểm tra và sửa LD_LIBRARY_PATH
   sudo docker exec opus-container bash -c "export LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/lib/python3.10/dist-packages/nvidia/cuda_nvrtc/lib:\$LD_LIBRARY_PATH"
   
   # Giải pháp 4: Tạo system-wide symlink
   sudo docker exec opus-container bash -c "ln -sf /usr/local/cuda/lib64/libnvrtc-builtins.so.12.0.140 /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.0"
   ```

3. Bước kiểm chứng:
   ```bash
   # Kiểm tra symbolic link được tạo
   sudo docker exec opus-container ls -la /usr/local/cuda/lib64/libnvrtc-builtins.so.12.0
   
   # Test linking với ldd
   sudo docker exec opus-container bash -c "ldd /usr/local/bin/inference-cuda | grep nvrtc"
   
   # Kiểm tra ldconfig cache
   sudo docker exec opus-container ldconfig -p | grep nvrtc
   ```

4. Kế hoạch rollback:
   ```bash
   # Xóa symbolic link nếu gây conflict
   sudo docker exec opus-container rm -f /usr/local/cuda/lib64/libnvrtc-builtins.so.12.0
   sudo docker exec opus-container rm -f /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.0
   
   # Khôi phục LD_LIBRARY_PATH gốc
   sudo docker exec opus-container bash -c "export LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/local/nvidia/lib:/usr/local/nvidia/lib64"
   ```

### 3. SELF-REFINE – Nhận xét & cập nhật
- Thiếu/Trùng lặp đã sửa: Bổ sung kiểm tra binary tồn tại, tối ưu rollback plan, xác nhận GPU Cloaking hooks không gây xung đột trực tiếp với NVRTC library loading.