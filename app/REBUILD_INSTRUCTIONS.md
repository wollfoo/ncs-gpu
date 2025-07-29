# 🔧 Container Rebuild Instructions - CUDA Version Fix

## 📋 **Prerequisites** (Yêu cầu tiên quyết)
- Stop existing container: `sudo docker stop opus-container`
- Remove existing container: `sudo docker rm opus-container`
- Backup existing data if needed

## 🚀 **Rebuild Steps** (Các bước rebuild)

### **Step 1: Backup Current Dockerfile**
```bash
cd /home/azureuser/ncs-gpu/app
cp Dockerfile Dockerfile.backup
cp requirements.txt requirements.txt.backup
```

### **Step 2: Apply Fixed Files**
```bash
# Replace with CUDA-synchronized versions
cp Dockerfile.fixed Dockerfile
cp requirements_fixed.txt requirements.txt
```

### **Step 3: Rebuild Docker Image**
```bash
# Build new image with CUDA 12.0 synchronization
sudo docker build -t gputraining:cuda-sync .

# Alternative: Force rebuild without cache
sudo docker build --no-cache -t gputraining:cuda-sync .
```

### **Step 4: Run New Container**
```bash
# Start container with same configuration
sudo docker run -d \
    --name opus-container \
    --gpus all \
    --privileged \
    --network host \
    -v "$(pwd)":/app:rw \
    gputraining:cuda-sync
```

### **Step 5: Verify Fix**
```bash
# Check container is running
sudo docker ps | grep opus-container

# Verify CUDA 12.0 libraries are used
sudo docker exec opus-container ldconfig -p | grep nvrtc

# Check Python packages (should show minimal CUDA packages)
sudo docker exec opus-container pip3 list | grep nvidia

# Monitor mining logs
sudo docker logs -f opus-container
```

## 🧪 **Verification Commands** (Lệnh xác minh)

### **Check NVRTC Version Alignment**
```bash
# Should show CUDA 12.0 libraries taking precedence
sudo docker exec opus-container bash -c "
echo 'LD_LIBRARY_PATH:' 
echo \$LD_LIBRARY_PATH
echo
echo 'NVRTC Libraries in ldconfig:'
ldconfig -p | grep nvrtc
echo
echo 'CUDA 12.0 NVRTC Files:'
ls -la /usr/local/cuda-12.0/targets/x86_64-linux/lib/libnvrtc*
"
```

### **Test Mining Application**
```bash
# Check if inference-cuda starts without NVRTC errors
sudo docker exec opus-container /usr/local/bin/inference-cuda --help

# Monitor for successful DAG initialization
sudo docker logs opus-container 2>&1 | grep -i "dag\|nvrtc\|kawpow"
```

## 🔍 **Expected Results** (Kết quả mong đợi)

### **Success Indicators:**
- ✅ No "libnvrtc-builtins.so.12.0" not found errors
- ✅ KawPow DAG initializes successfully  
- ✅ Hash rate > 0.00
- ✅ Mining process runs without NVRTC_ERROR_BUILTIN_OPERATION_FAILURE

### **Logs Should Show:**
```
[INFO] NVRTC Enhanced Wrapper - Verification complete
[INFO] KawPow DAG initialization: SUCCESS  
[INFO] Hash rate: [non-zero value]
```

### **Logs Should NOT Show:**  
```
nvrtc: error: failed to open libnvrtc-builtins.so.12.0
NVRTC_ERROR_BUILTIN_OPERATION_FAILURE
KawPow failed to initialize DAG
```

## 🚨 **Troubleshooting** (Khắc phục sự cố)

### **If Build Fails:**
```bash
# Clear Docker cache and retry
sudo docker system prune -f
sudo docker build --no-cache -t gputraining:cuda-sync .
```

### **If NVRTC Still Conflicts:**
```bash
# Check for remaining Python CUDA packages
sudo docker exec opus-container pip3 list | grep -i cuda

# Manual cleanup if needed
sudo docker exec opus-container pip3 uninstall -y [package-name]
```

### **Rollback Instructions:**
```bash
# If new version has issues, rollback to original
cp Dockerfile.backup Dockerfile
cp requirements.txt.backup requirements.txt
sudo docker build -t gputraining:rollback .
sudo docker run -d --name opus-container-rollback --gpus all --privileged --network host -v "$(pwd)":/app:rw gputraining:rollback
```

## 📊 **Key Changes Summary** (Tóm tắt thay đổi chính)

1. **PyTorch**: `latest` → `2.0.1+cu118` (CUDA 12.0 compatible)
2. **Python CUDA Packages**: Removed conflicting nvidia-cuda-* packages  
3. **LD_LIBRARY_PATH**: System CUDA 12.0 libraries prioritized
4. **NVRTC Symlinks**: Exact version matching (12.0.140 → 12.0)
5. **Build Process**: Enforced CUDA 12.0 throughout entire stack

## ⏱️ **Estimated Time**
- Build: 15-25 minutes (depending on internet speed)
- Verification: 2-5 minutes
- Total: ~30 minutes

## 📝 **Notes**
- This fix addresses the root cause at the Docker build level
- Changes are persistent across container restarts
- No manual symlink fixes needed after rebuild
- PyTorch functionality preserved with CUDA 12.0 compatibility