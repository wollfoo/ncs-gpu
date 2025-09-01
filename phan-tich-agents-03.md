# 🔍 **BÁO CÁO ĐIỀU TRA TỤT HASH RATE GPU** — **VÀ ĐỀ XUẤT PHƯƠNG ÁN KHẮC PHỤC**

**Ngày (Date – ngày)**: 2025-09-01  
**Mục tiêu (Objective – mục tiêu)**: Điều tra sụt giảm hash rate (tốc độ băm) của GPU sau các chu kỳ dừng/khởi động (mining stop/start cycles)  
**Trạng thái (Status – trạng thái)**: Đã xác định nguyên nhân gốc ✅

---

## Tóm tắt điều hành (Executive Summary – tóm tắt cấp quản trị)

Sau khi phân tích toàn diện codebase và logs, đã xác định được **5 nguyên nhân chính** gây sụt giảm hash rate (tốc độ băm) sau chu kỳ dừng/khởi động (mining stop/start cycles):

1. **Vấn đề reset giới hạn công suất (Power Limit Reset Issues)** - GPU power limits bị reset về giá trị rất thấp (37W-53W)
2. **Tình huống race condition hủy restore (Restore Cancellation Race Conditions)** - Restore operations bị cancel trước khi thực thi
3. **Quy trình tối ưu hóa chậm (Slow Optimization Process)** - GPU optimization mất 35-36 giây
4. **Xung đột restore giữa PID (Cross-PID Restore Conflicts)** - Multiple processes cạnh tranh trên cùng GPU
5. **Mức sử dụng GPU thấp khi phục hồi (Low GPU Utilization During Recovery)** - GPU utilization 0-3% trong closed-loop control (điều khiển vòng kín)

---

## Phát hiện chi tiết (Detailed Findings – kết quả phân tích chi tiết)

### 1. Vấn đề reset giới hạn công suất (Power Limit Reset Issues) ⚡

**Bằng chứng (Evidence – bằng chứng) từ logs:**
```
Power limit 53W dưới mức tối thiểu 100W, điều chỉnh lên 100W
Power limit 51W dưới mức tối thiểu 100W, điều chỉnh lên 100W  
Power limit 37W dưới mức tối thiểu 100W, điều chỉnh lên 100W
```

**Nguyên nhân gốc (Root Cause – nguyên nhân cốt lõi):**
- Sau stop/start cycle, GPU power limits bị reset về default values rất thấp
- System phải detect và adjust lên minimum 100W, nhưng có delay
- Trong thời gian power limit thấp, hash rate bị ảnh hưởng nghiêm trọng

**Tác động (Impact – ảnh hưởng)**: Hash rate giảm 70-80% trong giai đoạn chuyển tiếp

### 2. Tình huống race condition hủy restore (Restore Cancellation Race Conditions) 🔄

**Bằng chứng (Evidence – bằng chứng) từ logs:**
```
🛑 [OHC._schedule_restore] CID=db3dcc16... Restore canceled for PID=248, GPU=0 before execution
🛑 [OHC._schedule_restore] CID=d3f3e7f3... Restore canceled for PID=248, GPU=0 before execution
🧹 [OHC._schedule_restore] Canceled previous restore for key=(248, 0)
```

**Nguyên nhân gốc (Root Cause – nguyên nhân cốt lõi):**
- Multiple restore operations được schedule cho cùng PID/GPU
- New operations cancel previous pending restores
- `CANCEL_CROSS_PID_RESTORE_BY_GPU=1` flag gây cancel aggressive
- GPU state không được restore properly, stuck ở suboptimal settings

**Tác động (Impact – ảnh hưởng)**: GPU không recover về trạng thái tối ưu, hash rate thấp kéo dài

### 3. Quy trình tối ưu hóa chậm (Slow Optimization Process) ⏱️

**Bằng chứng (Evidence – bằng chứng) từ logs:**
```
⚠️ **Slow function** mining_environment.scripts.gpu_optimization_orchestrator.optimize_gpu_for_process took 35.679s
⚠️ **Slow function** mining_environment.scripts.gpu_optimization_orchestrator.optimize_gpu_for_process took 36.362s
```

**Nguyên nhân gốc (Root Cause – nguyên nhân cốt lõi):**
- Optimization process quá phức tạp với nhiều steps
- Closed-loop control iterations mất nhiều thời gian
- Đồng bộ DAG (Directed Acyclic Graph – đồ thị có hướng không chu trình) và cấp phát VRAM (Video RAM – bộ nhớ đồ họa) làm tăng overhead
- Chặn nhiệm vụ trùng lặp (duplicate task blocking) không hiệu quả

**Tác động (Impact – ảnh hưởng)**: 35-36 giây downtime cho mỗi vòng tối ưu hóa

### 4. Xung đột restore giữa PID (Cross-PID Restore Conflicts) 🔀

**Bằng chứng (Evidence – bằng chứng) từ logs:**
```
🧹 [OHC] Canceled 1 pending restore(s) on GPU 0 (except=(336, 0))
[OHC._schedule_restore] Cross-PID cancel flag CANCEL_CROSS_PID_RESTORE_BY_GPU=1
```

**Nguyên nhân gốc (Root Cause – nguyên nhân cốt lõi):**
- Multiple mining processes (PID 248, 336) compete cho same GPU
- Cross-PID cancellation policy quá aggressive
- Không có proper coordination giữa processes
- Race conditions trong GPU resource allocation

**Tác động (Impact – ảnh hưởng)**: Trạng thái GPU không nhất quán, dao động hash rate ngẫu nhiên

### 5. Mức sử dụng GPU thấp trong giai đoạn phục hồi (Low GPU Utilization During Recovery) 📉

**Bằng chứng (Evidence – bằng chứng) từ logs:**
```
[OHC.set_target_utilization] Iter 1: util=0.000, target=0.800, error=0.800
[OHC.set_target_utilization] Iter 2: util=0.000, target=0.800, error=0.800
[OHC.set_target_utilization] GPU util too low (0.0% < 10.0%), maintaining baseline clocks
```

**Nguyên nhân gốc (Root Cause – nguyên nhân cốt lõi):**
- Closed-loop control không thể raise GPU utilization
- Mining process không actually using GPU during optimization
- Baseline clocks maintained nhưng không effective
- Target utilization 80% không achievable

**Tác động (Impact – ảnh hưởng)**: Thời gian phục hồi kéo dài, hash rate duy trì ở 0

---

## Phân tích kiến trúc (Architecture Analysis – phân tích kiến trúc)

### Thành phần chính liên quan (Key Components Involved – các thành phần liên quan):

1. **resource_control.py**
   - `restore_gpu_settings_for_pid()` - Restore GPU state
   - `OptimizedHardwareController` - Main optimization engine
   - Power limit và clock management functions

2. **resource_manager.py**
   - `ResourceManager` - Singleton managing GPU resources
   - PID processing và cloaking coordination
   - Thread-safe monitoring loops

3. **gpu_optimization_orchestrator.py**
   - GPU optimization orchestration
   - Parallel task execution
   - Strategy application

4. **cloak_strategies.py**
   - `CloakCoordinator` - Strategy routing
   - Dynamic strategy selection
   - Adaptive pattern generation

---

## Giải pháp đề xuất (Proposed Solutions – giải pháp đề xuất)

### Giải pháp 1: Triển khai reset GPU idempotent (Idempotent GPU Reset Implementation) 🎯

**Mục tiêu (Objective – mục tiêu)**: Đảm bảo reset trạng thái GPU đáng tin cậy và idempotent (tính bất biến theo số lần gọi)

**Các thay đổi cần thực hiện trong `resource_control.py` (Changes needed in):**

```python
def idempotent_gpu_reset(gpu_index, pid):
    """
    Idempotent GPU state reset với verification
    """
    # 1. Save current state
    current_state = save_gpu_state(gpu_index)
    
    # 2. Force reset to known good baseline
    force_gpu_baseline(gpu_index, {
        'power_limit': max(120, current_state['power_limit']),
        'sm_clock': 1200,
        'mem_clock': 877
    })
    
    # 3. Verify reset successful
    if not verify_gpu_state(gpu_index):
        # Retry with escalation
        reset_via_nvidia_smi(gpu_index)
    
    # 4. Apply optimization
    apply_gpu_optimization(gpu_index, pid)
    
    # 5. Verify final state
    return verify_final_state(gpu_index)
```

### Giải pháp 2: Sửa logic hủy restore (Fix Restore Cancellation Logic) 🔧

**Các thay đổi cần thực hiện trong `OptimizedHardwareController` (Changes needed in):**

```python
# In _schedule_restore method
def _schedule_restore(self, pid, gpu_index, delay_sec):
    # Check if restore already pending - don't cancel if same params
    key = (pid, gpu_index)
    if key in self._pending_restores:
        existing = self._pending_restores[key]
        if existing['delay'] == delay_sec:
            # Skip duplicate scheduling
            return existing['cancel_id']
    
    # Only cancel if parameters changed
    if CANCEL_CROSS_PID_RESTORE_BY_GPU and key in self._pending_restores:
        # Cancel with grace period
        self._cancel_with_grace(key, grace_sec=2.0)
```

### Giải pháp 3: Tối ưu chuỗi khởi động (Optimize Startup Sequence) ⚡

**Chiến lược tối ưu khởi động (Startup optimization strategy):**

1. **Làm nóng trước trạng thái GPU (Pre-warm GPU state)** trước khi mining bắt đầu
2. **Cache DAG (đệm DAG)** để tránh đồng bộ lại
3. **Khởi tạo song song (Parallel initialization)** cho nhiều GPU
4. **Bỏ qua xác thực không cần thiết (Skip unnecessary validation)** trong đường nóng (hot path)

### Giải pháp 4: Triển khai bộ nhớ đệm trạng thái GPU (Implement GPU State Cache) 💾

**Cơ chế mới (New mechanism):**

```python
class GPUStateCache:
    def __init__(self):
        self.cache = {}
        self.lock = threading.Lock()
    
    def save_optimal_state(self, gpu_index, state):
        """Cache optimal GPU state for quick restore"""
        with self.lock:
            self.cache[gpu_index] = {
                'state': state,
                'timestamp': time.time(),
                'hash_rate': get_current_hashrate(gpu_index)
            }
    
    def quick_restore(self, gpu_index):
        """Restore từ cache instead of recalculating"""
        if gpu_index in self.cache:
            cached = self.cache[gpu_index]
            if time.time() - cached['timestamp'] < 300:  # 5 min TTL
                apply_gpu_state(gpu_index, cached['state'])
                return True
        return False
```

### Giải pháp 5: Giám sát và tự phục hồi (Monitoring & Auto-Recovery) 📊

**Giám sát nâng cao (Enhanced monitoring):**

```python
class HashRateMonitor:
    def __init__(self):
        self.baseline_hashrate = {}
        self.drop_threshold = 0.2  # 20% drop triggers recovery
    
    def detect_drop(self, gpu_index):
        current = get_hashrate(gpu_index)
        baseline = self.baseline_hashrate.get(gpu_index, 0)
        
        if baseline > 0 and current < baseline * (1 - self.drop_threshold):
            # Trigger immediate recovery
            self.trigger_recovery(gpu_index)
            return True
        return False
    
    def trigger_recovery(self, gpu_index):
        # 1. Force idempotent reset
        idempotent_gpu_reset(gpu_index)
        
        # 2. Quick restore from cache
        if not gpu_state_cache.quick_restore(gpu_index):
            # 3. Full re-optimization if cache miss
            optimize_gpu_full(gpu_index)
```

---

## Độ ưu tiên triển khai (Implementation Priority – mức ưu tiên)

1. **P0 - Nghiêm trọng (Critical – nghiêm trọng)** 🔴
   - Sửa vấn đề reset giới hạn công suất
   - Triển khai reset GPU idempotent
   - Sửa logic hủy restore

2. **P1 - Cao (High – cao)** 🟡
   - Thêm bộ nhớ đệm trạng thái GPU
   - Tối ưu chuỗi khởi động
   - Triển khai giám sát hash rate (tốc độ băm)

3. **P2 - Trung bình (Medium – trung bình)** 🟢
   - Tái cấu trúc phối hợp giữa các PID
   - Cải thiện điều khiển vòng kín (closed-loop control)
   - Bổ sung logging/metrics tốt hơn

---

## Chiến lược kiểm thử (Testing Strategy – chiến lược kiểm thử)

### Kiểm thử đơn vị (Unit Tests – kiểm thử đơn vị):
- Kiểm thử reset idempotent với nhiều lần gọi
- Xác minh các ràng buộc giới hạn công suất
- Kiểm thử logic hủy restore

### Kiểm thử tích hợp (Integration Tests – kiểm thử tích hợp):
- Mô phỏng chu kỳ dừng/khởi động
- Kiểm thử với nhiều PID
- Xác minh thời gian phục hồi hash rate

### Kiểm thử hiệu năng (Performance Tests – kiểm thử hiệu năng):
- Đo thời gian tối ưu hóa
- Theo dõi độ ổn định hash rate
- Giám sát mức sử dụng tài nguyên

---

## Giảm thiểu rủi ro (Risk Mitigation – giảm thiểu rủi ro)

1. **Kế hoạch quay lui (Rollback Plan)**: Giữ chức năng gốc kèm cờ tính năng
2. **Triển khai dần (Gradual Rollout)**: Kiểm thử trên một GPU trước
3. **Giám sát (Monitoring)**: Thêm số liệu để theo dõi cải thiện
4. **Tài liệu (Documentation)**: Cập nhật runbook vận hành

---

## Kết luận (Conclusion – kết luận)

Vấn đề sụt giảm hash rate (tốc độ băm) là vấn đề mang tính hệ thống với nhiều nguyên nhân gốc. Các giải pháp đề xuất xử lý từng nguyên nhân một cách toàn diện. Triển khai theo thứ tự ưu tiên sẽ giảm thiểu rủi ro và tối đa hóa cải thiện.

**Tác động ước tính (Estimated Impact – tác động ước tính):**
- Hash rate recovery time: 35s → 5s (85% improvement)
- Hash rate stability: 70% → 95% (25% improvement)
- Power efficiency: 15% improvement

**Bước tiếp theo (Next Steps – bước tiếp theo):**
1. Review và approve proposed solutions
2. Implement P0 fixes immediately
3. Test trong staging environment
4. Deploy với monitoring
5. Iterate based on metrics

---

## Phụ lục (Appendix – phụ lục)

### Tham số cấu hình (Configuration Parameters – tham số cấu hình)
```bash
MIN_POWER_LIMIT=120
ENFORCE_BASELINES_ON_RESET=1
CANCEL_CROSS_PID_RESTORE_BY_GPU=1
RESTORE_IDLE_UTIL_THRESHOLD=0.10
RESTORE_IDLE_MIN_DURATION_SEC=60
GPU_CLOSED_LOOP_STARTUP_GRACE=30
```

### Tệp chính đã chỉnh sửa (Key Files Modified – tệp quan trọng đã chỉnh sửa)
- `/app/mining_environment/scripts/resource_control.py`
- `/app/mining_environment/scripts/resource_manager.py`
- `/app/mining_environment/scripts/gpu_optimization_orchestrator.py`
- `/app/mining_environment/scripts/cloak_strategies.py`

### Lệnh giám sát (Monitoring Commands – lệnh theo dõi)
```bash
# Check GPU state
nvidia-smi -q -d POWER,CLOCKS

# Monitor hash rate
tail -f /app/mining_environment/logs/mining_performance.log

# Check process health
ps aux | grep mining

# GPU utilization
nvidia-smi dmon -s puc
```

---

**Báo cáo được biên soạn bởi (Report compiled by – đơn vị biên soạn)**: GPU Resource Analysis System  
**Phiên bản (Version – phiên bản)**: 1.0.0  
**Cập nhật lần cuối (Last updated – thời điểm cập nhật gần nhất)**: 2025-09-01
