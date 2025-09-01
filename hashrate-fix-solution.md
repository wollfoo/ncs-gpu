# Giải Pháp Khắc Phục Tụt Hashrate GPU Mining

## 1. Nguyên Nhân Cốt Lõi

### Vấn đề Closed-Loop Control
- **Bug logic**: Khi `error = target - util > 0` (utilization thấp), code tăng xung thay vì giữ/giảm
- **Thiếu baseline guard**: Xung có thể giảm xuống dưới MIN_SM_CLOCK trong vòng lặp
- **GPU startup delay**: Mining process chưa tạo utilization ngay → closed-loop giảm xung sai

### Evidence
```
[OHC.set_target_utilization] Iter 1-30: util=0.000, target=0.800, error=0.800
GPU clocks set to "(gpuClkMin 435, gpuClkMax 435)"  # Xuống mức tối thiểu!
Hashrate: 10.87 MH/s  # Thấp bất thường (baseline ~39 MH/s)
```

## 2. Giải Pháp Refactor

### A. Fix Closed-Loop Logic (resource_control.py)

```python
# Dòng 2591-2610 trong set_target_utilization()
# HIỆN TẠI (SAI):
increased = error > 0.0  # error dương = cần tăng util

# SỬA THÀNH:
# Option 1: Disable clock adjustment khi util quá thấp
if util < 0.1:  # Skip adjustment if GPU not yet active
    self.logger.info(f"[OHC] GPU util too low ({util:.1%}), maintaining baseline clocks")
    time.sleep(min_interval_sec)
    continue

# Option 2: Reverse logic cho clock adjustment
increased = util > target  # util cao → giảm xung, util thấp → tăng/giữ xung
```

### B. Thêm Baseline Protection

```python
# Dòng 2610 - Thêm guard cho MIN_SM_CLOCK
baseline_min_sm = int(os.getenv('MIN_SM_CLOCK', '1200'))
desired_sm = int(max(baseline_min_sm, min(2100, current_sm_clock + step_clk)))
# Không cho phép xung xuống dưới baseline
```

### C. Skip Closed-Loop cho Mining Startup

```python
# Thêm early return nếu mining mới khởi động
def set_target_utilization(...):
    # Check if mining just started (< 30s)
    mining_startup_grace = 30  # seconds
    if time.time() - process_start_time < mining_startup_grace:
        self.logger.info("[OHC] Mining startup grace period, maintaining baseline")
        # Apply baseline và return
        self._apply_nvml_controls(pid, gpu_index, {
            'power_limit': baseline_power,
            'sm_clock': baseline_min_sm,
            'mem_clock': baseline_min_mem
        })
        return {'success': True, 'reason': 'startup_grace'}
```

## 3. Cấu Hình Environment

### setup_env.py - Đảm bảo defaults đúng
```python
# Baseline minimums
os.environ.setdefault('MIN_SM_CLOCK', '1200')      # MHz
os.environ.setdefault('MIN_POWER_LIMIT', '120')    # Watts
os.environ.setdefault('MIN_MEM_CLOCK', '877')      # MHz

# Closed-loop tuning
os.environ.setdefault('GPU_CLOSED_LOOP_STEP_SM', '30')     # Larger steps
os.environ.setdefault('GPU_CLOSED_LOOP_MIN_UTIL', '0.1')  # Skip if < 10%
os.environ.setdefault('GPU_CLOSED_LOOP_STARTUP_GRACE', '30')  # seconds
```

## 4. Kế Hoạch Triển Khai

### Phase 1: Quick Fix (Ngay lập tức)
1. **Disable closed-loop tuning** cho mining:
   - Set `GPU_CLOSED_LOOP_MAX_SEC=0` hoặc skip set_target_utilization
   - Chỉ apply baseline clocks cố định

### Phase 2: Proper Fix (1-2 ngày)
1. Sửa logic closed-loop control
2. Thêm baseline protection guards
3. Implement startup grace period
4. Test với các scenarios:
   - Cold start
   - Restart sau crash
   - Multiple GPU setup

### Phase 3: Monitoring (Ongoing)
1. Log SM/MEM clocks mỗi 30s
2. Alert nếu xung < MIN_SM_CLOCK
3. Track hashrate vs clock correlation

## 5. Verification Script

```bash
#!/bin/bash
# verify-gpu-clocks.sh

# Check current clocks
nvidia-smi -q -d CLOCK | grep -E "Graphics|SM|Memory"

# Monitor hashrate
tail -f mining_debug.log | grep -E "MH/s|MHz"

# Verify env vars
env | grep -E "MIN_SM_CLOCK|MIN_POWER|CLOSED_LOOP"

# Force baseline
export MIN_SM_CLOCK=1200
export MIN_POWER_LIMIT=120
export GPU_CLOSED_LOOP_MAX_SEC=0  # Disable tuning
```

## 6. Expected Results

### Before Fix
- SM Clock: 435-480 MHz
- Hashrate: 10-12 MH/s
- Power: 36-72W

### After Fix
- SM Clock: 1200+ MHz (stable)
- Hashrate: 35-40 MH/s
- Power: 120-150W

## 7. Rollback Plan

Nếu fix gây vấn đề:
1. Revert resource_control.py changes
2. Set `ALLOW_CLOCK_LOCK=0` temporarily
3. Manual set clocks: `nvidia-smi -lgc 1200,1200`
4. Monitor và điều chỉnh

## 8. Long-term Improvements

1. **Decouple mining từ closed-loop**:
   - Mining dùng fixed clocks
   - Closed-loop chỉ cho inference/compute

2. **Implement proper PID controller**:
   - Proportional-Integral-Derivative thay vì simple stepping
   - Hysteresis và deadband

3. **Profile-based optimization**:
   - Lưu optimal settings per algorithm
   - Auto-apply khi detect workload type
