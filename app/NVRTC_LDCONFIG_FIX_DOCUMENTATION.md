# 🔧 NVRTC LDCONFIG FIX - DOCUMENTATION & ROLLBACK PLAN

**Date**: 2025-07-28  
**Method**: ldconfig configuration (thay thế symbolic links)  
**Issue**: `libnvrtc-builtins.so.12.0` not found by inference-cuda  
**Solution**: Cấu hình ldconfig để system tự động tìm NVRTC libraries

---

## 📦 THAY ĐỔI ĐÃ THỰC HIỆN

### Files Modified:
1. `/home/azureuser/ncs-gpu/app/Dockerfile` - Lines 179-214
2. `/home/azureuser/ncs-gpu/app/mining_environment/gpu_plugins/fix_nvrtc_symlinks.sh` - Multiple functions updated

### Phương Pháp Mới (ldconfig Method):
- **Dockerfile**: Tạo `/etc/ld.so.conf.d/cuda-nvrtc.conf` với đường dẫn chính xác
- **Runtime Script**: Kiểm tra và cấu hình ldconfig thay vì tạo symbolic links
- **System State**: ldconfig cache chứa NVRTC libraries, không cần symbolic links

### So Sánh Old vs New:

#### ❌ Phương Pháp Cũ (Symbolic Links):
```bash
# Tạo symbolic links
ln -sf /usr/local/cuda-12.0/targets/x86_64-linux/lib/libnvrtc-builtins.so.12.0.140 \
       /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.0

# Rủi ro: Broken links, path resolution issues
```

#### ✅ Phương Pháp Mới (ldconfig):
```bash
# Cấu hình ldconfig
echo "/usr/local/cuda-12.0/targets/x86_64-linux/lib" > /etc/ld.so.conf.d/cuda-nvrtc.conf
ldconfig

# Lợi ích: System-wide, persistent, no broken links
```

---

## 🛡️ LỢI ÍCH CỦA LDCONFIG METHOD

### ✅ Advantages:
1. **No Broken Links Risk** (không rủi ro liên kết hỏng)
2. **System-wide Effect** (ảnh hưởng toàn hệ thống)
3. **Persistent Across Reboots** (bền vững qua reboot)
4. **Standard Linux Method** (phương pháp chuẩn Linux)
5. **Simpler Troubleshooting** (troubleshoot đơn giản hơn)
6. **Better Performance** (hiệu năng tốt hơn - ldconfig cache)

### 📊 Performance Comparison:
- **Symbolic Links**: Path resolution overhead mỗi lần access
- **ldconfig**: Cache-based lookup, faster resolution

---

## 🔄 ROLLBACK PROCEDURES

### Method 1: Container-Level Rollback (Immediate)
```bash
# Remove ldconfig configuration
sudo docker exec opus-container sh -c "
rm -f /etc/ld.so.conf.d/cuda-nvrtc.conf
ldconfig
echo 'ldconfig configuration removed'
"

# Fallback to environment variable
sudo docker exec opus-container sh -c "
export LD_LIBRARY_PATH='/usr/local/cuda-12.0/targets/x86_64-linux/lib:\$LD_LIBRARY_PATH'
echo 'Switched to LD_LIBRARY_PATH method'
"
```

### Method 2: Rollback to Original Symbolic Links Method
```bash
# Restore old symbolic links (if needed)
sudo docker exec opus-container sh -c "
# Remove ldconfig config
rm -f /etc/ld.so.conf.d/cuda-nvrtc.conf
ldconfig

# Create old-style symbolic links
mkdir -p /usr/lib/x86_64-linux-gnu
ln -sf /usr/local/cuda-12.0/targets/x86_64-linux/lib/libnvrtc-builtins.so.12.0.140 \
       /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.0

echo 'Restored to symbolic links method'
"
```

### Method 3: Code-Level Rollback
Restore original Dockerfile section từ file `NVRTC_FIX_BACKUP_AND_ROLLBACK.md`

---

## ✅ VERIFICATION COMMANDS

### Check ldconfig Configuration:
```bash
# Check config file exists
ls -la /etc/ld.so.conf.d/cuda-nvrtc.conf
cat /etc/ld.so.conf.d/cuda-nvrtc.conf

# Check ldconfig cache
ldconfig -p | grep nvrtc-builtins

# Run script verification
/app/mining_environment/gpu_plugins/fix_nvrtc_symlinks.sh --check-only --verbose
```

### Test với Actual Application:
```bash
# Test compilation hoặc inference
# (Tùy thuộc vào application cụ thể sử dụng NVRTC)
```

---

## 🚨 TROUBLESHOOTING

### Common Issues:

#### 1. "Permission denied" khi tạo ldconfig config
```bash
# Solution: Ensure running with sufficient privileges
sudo echo "/path/to/nvrtc/lib" > /etc/ld.so.conf.d/cuda-nvrtc.conf
```

#### 2. Libraries không xuất hiện trong ldconfig cache
```bash
# Debug steps:
ldconfig -v | grep cuda
ls -la /usr/local/cuda-12.0/targets/x86_64-linux/lib/libnvrtc*

# Solution: Verify path and run ldconfig again
```

#### 3. Application vẫn báo lỗi "library not found"
```bash
# Fallback to environment variable
export LD_LIBRARY_PATH="/usr/local/cuda-12.0/targets/x86_64-linux/lib:$LD_LIBRARY_PATH"
```

---

## 📈 SUCCESS METRICS

### Fix Success Indicators:
- ✅ `/etc/ld.so.conf.d/cuda-nvrtc.conf` exists and contains correct path
- ✅ `ldconfig -p | grep nvrtc-builtins` returns results
- ✅ Script `--check-only` passes all tests
- ✅ Application runs without NVRTC errors
- ✅ Performance improved (faster library loading)

**Status**: Fix implemented using ldconfig method ✅  
**Risk Level**: Very Low (safe, standard method) 🟢  
**Maintenance**: Minimal (self-managing) 🟢  
**Impact**: Resolves NVRTC compilation errors with better reliability 🎯

---

## 🔗 RELATED FILES

- Original analysis: `NVRTC_FIX_BACKUP_AND_ROLLBACK.md`
- Updated Dockerfile: `/app/Dockerfile` (lines 179-214)
- Updated script: `/app/mining_environment/gpu_plugins/fix_nvrtc_symlinks.sh`
- This documentation: `NVRTC_LDCONFIG_FIX_DOCUMENTATION.md`
