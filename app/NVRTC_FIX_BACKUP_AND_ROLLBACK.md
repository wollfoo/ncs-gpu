# 🔧 NVRTC SYMBOLIC LINK FIX - BACKUP & ROLLBACK PLAN

**Date**: 2025-07-28  
**Issue**: `libnvrtc-builtins.so.12.0` not found by inference-cuda  
**Root Cause**: Symbolic link pointing to wrong path

---

## 📦 BACKUP INFORMATION

### Files Modified:
1. `/home/azureuser/ncs-gpu/app/Dockerfile` - Lines 179-213
2. `/home/azureuser/ncs-gpu/app/mining_environment/gpu_plugins/fix_nvrtc_symlinks.sh` - Functions updated

### Original State (Before Fix):
- **Dockerfile**: NVRTC fix looked for file at `/usr/local/cuda/lib64/libnvrtc-builtins.so.12.0.140`
- **Runtime Script**: Same incorrect path assumption
- **Container State**: Symbolic link pointed to non-existent `/usr/local/cuda/lib64/libnvrtc-builtins.so.12.0.140`

### Corrected State (After Fix):
- **Dockerfile**: Dynamic path detection with fallback to `/usr/local/cuda-12.0/targets/x86_64-linux/lib/`
- **Runtime Script**: Uses same dynamic path detection logic
- **Container State**: Symbolic link correctly points to actual file location

---

## 🔄 ROLLBACK PROCEDURE

If the fix causes issues, follow these steps:

### Step 1: Container-Level Rollback (Immediate)
```bash
# Reset symbolic links to original state
sudo docker exec opus-container sh -c "
# Remove corrected links
rm -f /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.0
rm -f /usr/local/cuda/lib64/libnvrtc-builtins.so.12.0

# Recreate original (broken) symbolic link
mkdir -p /usr/lib/x86_64-linux-gnu
ln -sf /usr/local/cuda/lib64/libnvrtc-builtins.so.12.0.140 /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.0

echo 'Rollback to original broken state completed'
"
```

### Step 2: Code-Level Rollback (If Rebuild Needed)

#### Dockerfile Rollback:
Replace lines 179-213 in Dockerfile with:
```dockerfile
# ------------------  NVRTC Symbolic Link Fix (Original) ---------------------
RUN set -eux; \
    echo "🔧 [NVRTC-BUILD-FIX] Checking and creating NVRTC symbolic links..."; \
    if [ -f "/usr/local/cuda/lib64/libnvrtc-builtins.so.12.0.140" ] && [ ! -f "/usr/local/cuda/lib64/libnvrtc-builtins.so.12.0" ]; then \
        echo "[NVRTC-BUILD-FIX] Creating symbolic link: libnvrtc-builtins.so.12.0 -> libnvrtc-builtins.so.12.0.140"; \
        cd /usr/local/cuda/lib64 && \
        ln -sf libnvrtc-builtins.so.12.0.140 libnvrtc-builtins.so.12.0; \
    fi; \
    if [ -f "/usr/local/cuda/lib64/libnvrtc-builtins.so.12.0.140" ]; then \
        echo "[NVRTC-BUILD-FIX] Creating system-wide symbolic link"; \
        mkdir -p /usr/lib/x86_64-linux-gnu && \
        ln -sf /usr/local/cuda/lib64/libnvrtc-builtins.so.12.0.140 /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.0; \
    fi; \
    ldconfig 2>/dev/null || echo "[NVRTC-BUILD-FIX] ldconfig update skipped"; \
    echo "✅ [NVRTC-BUILD-FIX] Build-time fix completed"
```

#### Script Rollback:
Reset `fix_nvrtc_symlinks.sh` to use hardcoded paths:
```bash
# In check_nvrtc_libraries() function
local base_path="/usr/local/cuda/lib64"
local target_lib="$base_path/libnvrtc-builtins.so.12.0.140"

# In create_nvrtc_symlinks() function  
local base_path="/usr/local/cuda/lib64"
local target_lib="$base_path/libnvrtc-builtins.so.12.0.140"
```

---

## ✅ VERIFICATION OF FIX

### Current Working State:
```bash
# Check symbolic links
sudo docker exec opus-container ls -la /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.0
# Output: -> /usr/local/cuda-12.0/targets/x86_64-linux/lib/libnvrtc-builtins.so.12.0.140

# Check ldconfig cache
sudo docker exec opus-container ldconfig -p | grep nvrtc-builtins
# Output: Multiple entries including correct path

# Test script
sudo docker exec opus-container /app/mining_environment/gpu_plugins/fix_nvrtc_symlinks.sh --check-only
# Output: "All NVRTC symbolic links are correct!"
```

### Fix Success Indicators:
- ✅ No more "nvrtc: error: failed to open libnvrtc-builtins.so.12.0" in logs
- ✅ ldconfig shows correct library paths
- ✅ Symbolic links point to actual file locations
- ✅ Build process creates correct links automatically

---

## 🛡️ PREVENTION MEASURES

### Future-Proofing:
1. **Dynamic Path Detection**: Fix now automatically finds NVRTC library regardless of CUDA installation path
2. **Fallback Mechanism**: Multiple search paths ensure compatibility across CUDA versions
3. **Runtime Validation**: Entrypoint script verifies and fixes links on container startup
4. **Build-Time Integration**: Dockerfile includes comprehensive fix during image build

### Monitoring:
- Monitor inference-cuda logs for NVRTC errors
- Check symbolic link integrity during container health checks
- Validate NVRTC library availability in CI/CD pipeline

---

## 📞 EMERGENCY CONTACTS

If rollback doesn't work:
1. Check container logs: `sudo docker logs opus-container`
2. Inspect CUDA installation: `sudo docker exec opus-container find /usr/local -name "*nvrtc*"`
3. Validate library search paths: `sudo docker exec opus-container echo $LD_LIBRARY_PATH`

**Status**: Fix tested and verified working ✅  
**Risk Level**: Low (rollback available) 🟢  
**Impact**: Resolves critical NVRTC compilation errors 🎯