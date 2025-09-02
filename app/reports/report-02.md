# 🔬 Báo Cáo Phân Tích Hiệu Năng GPU - Vấn Đề Tụt Hashrate

**Date**: $(date '+%Y-%m-%d--%H-%M-%p')  
**Analyst**: GPU Performance Investigator  
**System**: `/app` Mining Environment  

---

## 1. 📋 Executive Summary *(Tóm tắt quản trị)*

### ❌ **Vấn đề hiện tại**
Hệ thống mining gặp tình trạng **hashrate degradation** *(sụt giảm tốc độ băm)* nghiêm trọng sau nhiều vòng start/stop:
- **Hashrate hiện tại**: 20.31 MH/s (2 GPU)  
- **Hashrate mục tiêu**: 24.96 MH/s (đã từng đạt được)
- **GPU clocks bị giới hạn**: 412/877 MHz (mức thấp)
- **Power/Temp ổn định**: 75W, 38°C (không phải nguyên nhân)

### 🎯 **Root Cause** *(Nguyên nhân gốc rễ)*
**PERSISTENT APPLICATION CLOCKS STATE** *(trạng thái khóa xung nhịp liên tục)* - Hệ thống **cloaking** *(ngụy trang)* và **optimization** *(tối ưu hóa)* để lại **"hidden limits"** *(giới hạn ẩn)* trên GPU sau khi tắt optimizer, dẫn đến **incomplete reset** *(reset không hoàn toàn)*.

---

## 2. 🌍 Environment & Context *(Môi trường & Bối cảnh)*

### **Cấu trúc hệ thống được phân tích**:
```
[app/start_mining.py] → [stealth_inference_cuda.py] → [coordinator.py]
→ [resource_manager.py] → [cloak_strategies.py] 
→ [gpu_optimization_orchestrator.py] → [resource_control.py]
```

### **Các module điều khiển GPU**:
- `resource_control.py`: **GPUResourceManager**, **OptimizedHardwareController**
- `gpu_optimization_orchestrator.py`: **Cross-process coordination** *(phối hợp liên tiến trình)*
- `cloak_strategies.py`: **GpuCloakStrategy**, **AdaptivePatternGenerator**
- `resource_manager.py`: **SharedResourceManager** với **NVML lifecycle** *(vòng đời NVML)*

### **Evidence từ Code Analysis**:

#### 🔍 **EVIDENCE** `/app/mining_environment/scripts/resource_control.py:786-876`
```python
def set_gpu_power_limit(self, pid: Optional[int], gpu_index: int, power_limit_w: int) -> bool:
    # ... validation logic ...
    pynvml.nvmlDeviceSetPowerManagementLimit(handle, new_limit_mw)
    # Record last power change
    self._last_power_change_time[gpu_index] = time.time()
    self._last_power_limit_w[gpu_index] = power_limit_w
```

#### 🔍 **EVIDENCE** `/app/mining_environment/scripts/resource_control.py:1583-1684`
```python
def restore_gpu_settings_for_pid(self, pid: int, correlation_id: Optional[str] = None) -> bool:
    # ... restore logic with multiple fallbacks ...
    pynvml.nvmlDeviceResetApplicationsClocks(handle)  # ← CRITICAL POINT
    # ... but also uses nvidia-smi reset commands that can conflict ...
```

---

## 3. 🔬 Root Cause Analysis *(Phân tích nguyên nhân gốc rễ)*

### **Tree-of-Thought** *(Cây tư duy giả thuyết)*:

| Nhánh | Giả thuyết | Impact | Likelihood | Evidence |
|-------|------------|--------|------------|----------|
| **A** | **Application clocks persistence** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **STRONG** |
| B | Power limit stickiness | ⭐⭐⭐ | ⭐⭐⭐ | Moderate |
| C | Driver persistence mode | ⭐⭐⭐⭐ | ⭐⭐⭐ | Moderate |
| D | Thermal hysteresis | ⭐⭐ | ⭐⭐ | **CONTRADICTED** |
| E | Race condition cleanup | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **STRONG** |
| F | Cloaking side-effects | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **STRONG** |

### **Nhánh ưu tiên: A + E + F** *(Combination hypothesis)*

---

## 4. 🕵️ Detailed Analysis *(Phân tích chi tiết)*

### **4.1 Application Clocks Persistence** *(Nhánh A)*

#### **Mechanism** *(Cơ chế)*:
1. **Cloaking system** gọi `pynvml.nvmlDeviceSetApplicationsClocks()` để lock GPU clocks
2. **Optimization system** điều chỉnh power limits và additional clocks  
3. Khi **mining process** kết thúc, `restore_gpu_settings_for_pid()` được gọi
4. **RACE CONDITION**: Multiple reset commands conflict:
   - `nvidia-smi -rgc` (unlock graphics clocks)
   - `nvidia-smi --reset-memory-clocks`  
   - `pynvml.nvmlDeviceResetApplicationsClocks()`

#### **🔍 EVIDENCE** - Conflicting reset sequence:
```python
# resource_control.py:1606-1624 - NỔNG CƠM RESET SEQUENCE
try:
    cmd = ['nvidia-smi', '-i', str(gpu_index), '-rgc']  # ← Method 1
    r = subprocess.run(cmd, check=False, capture_output=True, text=True)
    # ... then ...
    cmd = ['nvidia-smi', '-i', str(gpu_index), '--reset-memory-clocks']  # ← Method 2
    # ... then ...
    pynvml.nvmlDeviceResetApplicationsClocks(handle)  # ← Method 3 (NVML API)
```

### **4.2 Race Condition in Cleanup** *(Nhánh E)*

#### **Critical Timing Issue**:
- **ResourceManager** khởi động async trong `start_resource_manager_thread()`  
- **Mining processes** start BEFORE ResourceManager fully ready
- **PID handoff** qua **DirectPIDRegistry** có thể miss nếu RM chưa sẵn sàng
- **Cleanup on exit** không đảm bảo thứ tự NVML → nvidia-smi → persistence

#### **🔍 EVIDENCE** `/app/start_mining.py:1219-1230`:  
```python
try:
    from mining_environment.scripts.resource_manager import ResourceManager
    if ResourceManager._instance and ResourceManager.is_ready():  # ← CHECK CAN FAIL
        # GPU processes started regardless of RM readiness
```

### **4.3 Cloaking Side-Effects** *(Nhánh F)*

#### **Stealth Strategy Accumulation**:
- **GpuCloakStrategy** áp dụng multiple parameters: power_limit, sm_clock, memory_clock
- **AdaptivePatternGenerator** tạo dynamic variations với jitter
- **Strategy stacking**: nhiều strategies có thể chồng lêp effects  
- **No centralized state tracking** cho all applied changes

#### **🔍 EVIDENCE** `/app/mining_environment/scripts/cloak_strategies.py:1585-1633`:
```python
enhanced_params = {
    'power_limit': params.get('power_limit', 150),        # ← Multiple params 
    'sm_clock': params.get('sm_clock', self.target_sm_clock),
    'memory_clock': params.get('memory_clock', self.target_mem_clock),
    # ... thermal throttling can modify these further
}
```

---

## 5. 🏗️ Recommendations *(Khuyến nghị)*

### **5.1 Quick Wins** *(Giải pháp tạm thời)*

#### **A. Preflight GPU Reset** *(Reset trước khi mining)*
- **File**: `start_mining.py` 
- **Location**: Trong `start_gpu_mining_process()` trước khi khởi chạy miners
- **Implementation**: 
```python
def preflight_gpu_reset():
    """Reset all GPU states before mining starts"""
    # 1. Reset application clocks (NVML)
    # 2. Reset power limits to default  
    # 3. Clear persistence mode if enabled
    # 4. Log before/after states for comparison
```

#### **B. Single Source of Truth** *(Nguồn sự thật duy nhất)*  
- **File**: `resource_control.py`
- **Enhancement**: Centralize tất cả GPU state changes trong `GPUResourceManager`
- **Pattern**: Mọi module khác chỉ gọi thông qua `GPUResourceManager.apply_changes()`

### **5.2 Hardening** *(Củng cố dài hạn)*

#### **A. Deterministic Reset Order** *(Thứ tự reset tất định)*
```
1. Cancel pending async operations  
2. pynvml.nvmlDeviceResetApplicationsClocks()  [NVML API first]
3. nvidia-smi power/clock resets              [CLI tools second] 
4. Verify final state                         [Confirmation]
5. Log complete state transition              [Audit trail]
```

#### **B. State Mirror & Validation** *(Bản sao trạng thái & xác thực)*
- **Persistent tracking**: In-memory dict của tất cả GPU modifications
- **Exit validation**: So sánh current state vs expected default state  
- **Retry mechanism**: Nếu validation fails, retry reset with exponential backoff

#### **C. ResourceManager-DirectPIDRegistry Synchronization** *(Đồng bộ RM-Registry)*  
- **Wait for ResourceManager readiness** trước khi start GPU processes
- **Explicit registration pattern** trong `start_mining.py`
- **Graceful degradation** nếu RM không available

### **5.3 Exit Cleanup Overhaul** *(Đại tu cleanup exit)*

#### **Enhanced Shutdown Sequence**:
```python  
def enhanced_gpu_cleanup():
    """Guaranteed GPU state restoration"""
    # 1. Stop all optimization/cloaking async tasks
    # 2. Collect all PIDs with GPU modifications  
    # 3. For each GPU: restore to documented default state
    # 4. Verification loop với retry up to 3 attempts
    # 5. Final audit log với before/after comparison
```

---

## 6. 🔄 Refactor Plan *(Kế hoạch tái cấu trúc)*

### **Phase 1: Immediate Fixes** *(Sửa lỗi tức thì)*
- ✅ **Preflight reset** trong `start_mining.py`
- ✅ **Enhanced logging** để debug GPU state changes  
- ✅ **ResourceManager readiness gate** trước GPU process start

### **Phase 2: Architecture Improvements** *(Cải thiện kiến trúc)*  
- ✅ **Centralized GPU state management** trong `resource_control.py`
- ✅ **Deterministic cleanup sequence** với verification
- ✅ **Enhanced DirectPIDRegistry integration**

### **Phase 3: Monitoring & Prevention** *(Giám sát & ngăn ngừa)*
- ✅ **GPU state monitoring** với periodic verification  
- ✅ **Automated recovery** khi detect state drift
- ✅ **Performance baseline tracking** để detect degradation sớm

---

## 7. ⚠️ Risks & Mitigations *(Rủi ro & Giảm thiểu)*

### **High Priority Risks**:

#### **A. NVML Thread Safety Issues** 
- **Risk**: Multiple threads gọi NVML APIs simultaneously
- **Mitigation**: RLock cho tất cả NVML operations trong `GPUResourceManager`

#### **B. Driver State Corruption**
- **Risk**: Nvidia driver enters inconsistent state  
- **Mitigation**: Driver restart detection + automatic system restart on corruption

#### **C. Performance Regression During Fixes**
- **Risk**: Enhanced verification làm chậm mining startup
- **Mitigation**: Async verification + timeout-based fallbacks

### **Medium Priority Risks**:

#### **D. Log Volume Explosion**  
- **Risk**: Enhanced debugging tạo quá nhiều logs
- **Mitigation**: Conditional debug logging với ENV flags

---

## 8. ❓ Open Questions *(Câu hỏi mở)*

### **Missing Evidence** *(Thiếu chứng cứ)*:
1. **GPU P-State transitions**: Log không chứa P-state data để confirm performance states
2. **Actual nvidia-smi output**: Cần capture live nvidia-smi để verify clocks/power states  
3. **NVML error codes**: Chi tiết về NVML API failures during reset operations
4. **Driver persistence mode**: Status của persistence mode không được log

### **Additional Investigation Needed**:
1. **Multi-GPU interaction**: GPU cross-contamination trong multi-GPU setup  
2. **Driver version correlation**: Nvidia driver version vs behavior consistency
3. **Thermal cycling impact**: Ảnh hưởng của temperature cycling lên clock stability

---

## 9. 📊 Implementation Priority *(Ưu tiên triển khai)*

| Priority | Task | Effort | Impact | 
|----------|------|--------|--------|
| **P0** | Preflight GPU reset | 2h | ⭐⭐⭐⭐⭐ |
| **P0** | Enhanced exit cleanup | 4h | ⭐⭐⭐⭐⭐ |
| **P1** | ResourceManager readiness gate | 3h | ⭐⭐⭐⭐ |
| **P1** | Centralized state management | 8h | ⭐⭐⭐⭐ |
| **P2** | State verification system | 6h | ⭐⭐⭐ |
| **P2** | Enhanced monitoring | 12h | ⭐⭐⭐ |

---

## 10. 📝 Appendix: Technical Deep Dive

### **Call Graph Analysis**:
```
start_mining.py::main()
├── initialize_environment()  
├── start_resource_manager_thread()         # ← Async startup
├── start_gpu_mining_process()
│   ├── stealth_inference_cuda.py           # ← Wrapper process  
│   └── DirectPIDRegistry registration      # ← May miss ResourceManager
└── monitoring loop
    └── process_manager.graceful_shutdown()  # ← Cleanup trigger
        └── resource_manager::restore_gpu_settings_for_pid()  # ← Reset attempt
```

### **NVML API Usage Pattern**:
```python
# Current problematic pattern:
1. pynvml.nvmlDeviceSetApplicationsClocks()     # Lock clocks  
2. pynvml.nvmlDeviceSetPowerManagementLimit()   # Set power
3. subprocess.run(['nvidia-smi', '-rgc'])       # CLI unlock attempt  ← CONFLICT
4. pynvml.nvmlDeviceResetApplicationsClocks()   # NVML reset      ← MAY FAIL
```

### **Recommended Pattern**:
```python  
# Proposed idempotent pattern:
1. Read current state (baseline)
2. Apply changes via NVML only  
3. Track all changes in state mirror
4. On restore: NVML reset → CLI verification → state audit
```

---

**🔚 End of Report**

**Next Steps**: Implement P0 fixes trong 1 working day, validate với test mining session để confirm hashrate recovery lên target 24.96 MH/s.
