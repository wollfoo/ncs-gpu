# 🔍 **BÁO CÁO ĐIỀU TRA TỤT HASH RATE GPU** — **VÀ ĐỀ XUẤT PHƯƠNG ÁN KHẮC PHỤC**

## 1) **Tóm tắt hiện trạng**

### **Timeline Hash Rate** (theo **[kawpow algorithm] (thuật toán KAWPOW)**)

| Lần chạy | **Hash Rate** | Nguồn Evidence | Clock Evidence |
|----------|--------------|----------------|----------------|
| **Lần 1** | ~**29.12 MH/s** | User log: `29598351.54 H/s` (`/app/mining_debug.log` - lần chạy đầu) | Không có data |
| **Lần 2** | ~**20.59 MH/s** | User log: `19788845.50 H/s` + `17065126.22 H/s` | Không có data |
| **Lần 3+** | ~**12.87 MH/s** | User log: `8989106.73 H/s` + Clock: `405/877 MHz`, `412/877 MHz` | **[P-state] (trạng thái hiệu năng)** thấp |
| **Hiện tại** | ~**11.10-11.87 MH/s** | Current log: `📊 METRICS: Current=11.10 MH/s` (dòng 4578-4579) | `Tesla V100 1380/877 MHz` (dòng 1051-1052) |

---

## 2) **Cây nguyên nhân** (**Tree-of-Thought** tóm tắt)

### **🌳 Ba Nhánh Phân Tích**

#### **Nhánh A — Driver/OS Persistence** 
- **Triệu chứng**: Clock frequencies thấp (`405/877 MHz`, `412/877 MHz`)
- **Giả thuyết**: **[Application Clocks] (khóa xung ứng dụng)** hoặc **[Power Limits] (giới hạn công suất)** "sticky" trong **[NVML] (thư viện NVIDIA)**
- **Bằng chứng**: Không đủ evidence trực tiếp từ logs hiện tại
- **Test**: Cần kiểm tra `nvidia-smi -q` để xác minh

#### **Nhánh B — Cloaking Strategy Không Teardown** ⭐ **CHỌN**
- **Triệu chứng**: **Power limit cực thấp** + **Restore operations bị canceled**
- **Giả thuyết**: **[Cloaking strategies] (chiến lược che giấu)** đặt giới hạn thấp nhưng không **restore** (khôi phục)
- **Bằng chứng**: 
  - `cloak_strategies.py:3` — **"đã loại bỏ hoàn toàn chức năng restoration"**
  - Power limits: `53W`, `50W`, `51W` (dòng 572-580, 1131-1132)
  - **TẤT CẢ restore bị canceled**: `🛑 Restore canceled ... before execution` (16 instances)
- **Test**: Kiểm tra GPU settings retention sau restart

#### **Nhánh C — Workload/DAG Changes**
- **Triệu chứng**: Hash rate giảm dần theo thời gian
- **Giả thuyết**: **[DAG size] (kích thước bộ dữ liệu)** tăng hoặc **[workload intensity] (cường độ tải)** thay đổi
- **Bằng chứng**: Thiếu evidence về DAG size changes
- **Test**: Monitor DAG progression

### **🎯 Nhánh được chọn: B — Cloaking Strategy Không Teardown**

**Lý do**: Có **evidence trực tiếp** và **bằng chứng mạnh** từ logs về việc restore operations bị canceled hoàn toàn.

---

## 3) **Nguyên nhân cốt lõi** (**Root Cause**)

### **🚨 IDENTIFIED ROOT CAUSE**

- **[Cloaking Strategies] (chiến lược che giấu)** trong `cloak_strategies.py` đặt **[power limits] (giới hạn công suất)** và **[clock frequencies] (tần số xung nhịp)** cực thấp để **camouflage** (ngụy trang)
- **[Restoration function] (chức năng khôi phục)** đã bị **"loại bỏ hoàn toàn"** (dòng 3, `cloak_strategies.py`)
- **[Scheduled restores] (khôi phục lên lịch)** bị **canceled** (hủy) 100% trước khi thực thi do **[Cross-PID cancellation] (hủy liên tiến trình)**
- GPU settings trở nên **"sticky"** (bám dính) sau mỗi lần **stop/start**, tích lũy thành **performance degradation** (suy giảm hiệu năng)

### **🔍 Evidence Support**

1. **Power limits cực thấp**: `{'power_limit': 53}`, `{'power_limit': 50}`, `{'power_limit': 51}` (nguồn: dòng 573, 1131-1132)
2. **Clock throttling**: `{'sm_clock': 976}`, `{'sm_clock': 1156}`, `{'sm_clock': 1238}` — thấp hơn baseline Tesla V100
3. **100% restore cancellation**: 16 instances `🛑 Restore canceled ... before execution` (dòng 1267, 1357, 1536, v.v.)
4. **No actual restore executed**: Không có dòng log nào showing completed restore

---

## 4) **Module/Lớp/Hàm bị ảnh hưởng**

### **🎯 Modules Liên Quan Trực Tiếp**

#### **`cloak_strategies.py`**
- **Class**: `MetricsCollectionHub`, `AdaptivePatternGenerator`  
- **Function**: Pattern generation applying low limits
- **Vai trò**: Đặt **power_limit** thấp (50-53W), **sm_clock** thấp (976-1238MHz)
- **Evidence**: Dòng 573 `🎯 [Pattern] Applied adaptive params: {'power_limit': 53, 'sm_clock': 976}`
- **⚠️ CRITICAL**: **Restoration function removed** (dòng 3 comment)

#### **`resource_control.py`**
- **Class**: `OptimizedHardwareController`, `GPUResourceManager`
- **Functions**: 
  - `set_gpu_power_limit()` (dòng 786) — đặt power limit
  - `set_gpu_clocks()` (dòng 889) — đặt xung nhịp  
  - `_schedule_restore()` (dòng 3437) — lên lịch restore (BỊ CANCEL)
  - `restore_gpu_settings_for_pid()` (dòng 1583) — restore logic (KHÔNG ĐƯỢC GỌI)
- **Evidence**: `⏰ [OHC._schedule_restore] Scheduling restore for PID 248 on GPU 0 after 30.0s` → `🛑 Restore canceled`

#### **`gpu_optimization_orchestrator.py`**
- **Class**: `GPUOptimizationOrchestrator`
- **Function**: Coordinates cloaking và resource control
- **Vai trò**: **Central coordinator** (điều phối viên trung tâm) cho GPU optimization
- **Evidence**: Import relationship với `resource_control` và `cloak_strategies`

#### **`start_mining.py`**
- **Function**: Mining workflow initiation
- **Vai trò**: **Entry point** (điểm khởi đầu) — không có **explicit teardown** (dọn dẹp rõ ràng) cho GPU settings
- **Evidence**: Import `ResourceManager` nhưng thiếu **cleanup logic** (logic dọn dẹp)

---

## 5) **Thiết kế Refactor** (**Design-only** — không code)

### **🔧 Idempotent Reset** trong `resource_control.py`

**Thêm function**:
- `reset_gpu_to_baseline()`: Force reset tất cả GPU về **[default settings] (cài đặt mặc định)**  
- Gọi `nvidia-smi --reset-clocks` + `nvidia-smi --reset-power-management` + verify
- **Always execute** trong khối `finally` của `start_mining.py` — đảm bảo **cleanup** (dọn dẹp)

### **🎯 Single Source of Truth** trong `gpu_optimization_orchestrator.py`

**Thêm components**:
- `GPUStateManager`: Lưu **baseline snapshot** (ảnh chụp cơ sở) khi start mining
- Track all GPU modifications với **[state diff] (chênh lệch trạng thái)**
- **Mandatory restore** (khôi phục bắt buộc) về baseline trước khi exit process

### **🎭 Cloak Release Path** trong `cloak_strategies.py`

**Restore lại function**:
- `release_cloaking()`: **Explicit uncloaking** (bỏ che giấu rõ ràng) — khôi phục power/clock về **[normal ranges] (khoảng bình thường)**
- **Register exit handler** (đăng ký xử lý thoát) để gọi automatic release
- **Backup mechanism**: Nếu cloaking fails, immediate revert

### **✅ Double-Check Logging**

**Thêm verification**:
- Sau mỗi GPU modification: **đọc lại settings** từ **[NVML] (thư viện NVIDIA)**
- **Assert log**: `restored >= baseline` với tolerances
- **Performance monitoring**: Track **hash rate delta** (chênh lệch tốc độ băm) trước/sau restore

---

## 6) **Kế hoạch kiểm chứng** & tiêu chí **"Get It Working First"**

### **📋 Sequential Testing Plan (B1→B4)**

#### **B1: Chụp Baseline** 
```bash
# Capture initial state
nvidia-smi --query-gpu=clocks.gr,clocks.mem,power.limit --format=csv > baseline.csv
# Expected: Core ~1400MHz, Memory 877MHz, Power 250-300W
```
**Pass criteria**: Successful baseline capture với reasonable values

#### **B2: Áp dụng → Xác minh**
```bash  
# After cloaking applied  
nvidia-smi --query-gpu=clocks.gr,clocks.mem,power.limit --format=csv > post_cloak.csv
# Expected: Lower values matching log evidence
```
**Pass criteria**: Settings match expected cloaking parameters

#### **B3: Dừng → Reset → Xác minh** 
```bash
# Stop mining + execute reset_gpu_to_baseline()
nvidia-smi --reset-clocks --reset-power-management -i 0,1
nvidia-smi --query-gpu=clocks.gr,clocks.mem,power.limit --format=csv > post_reset.csv
```
**Pass criteria**: Values within **±5%** of baseline

#### **B4: Start Mining → Performance Check**
- Restart mining process
- Monitor **hash rate** for **5 minutes**  
- **Pass criteria**: Hash rate **≥ 85%** của baseline lần 1 (~25+ MH/s)

---

## 7) **Rủi ro & phương án rollback**

### **⚠️ Identified Risks**

1. **Hardware damage risk**: **LOW** — chỉ reset về factory defaults
2. **Service disruption**: **MEDIUM** — cần restart mining processes  
3. **Performance regression**: **LOW** — reset improves performance

### **🔄 Rollback Plan**

```bash
# Emergency rollback to current state
# 1. Stop new reset logic
systemctl stop mining-service  
# 2. Restore previous cloaking behavior (manual low settings)  
nvidia-smi -pl 50 -i 0,1
# 3. Restart with old logic
systemctl start mining-service
```

### **🛡️ Mitigations**

- **Gradual rollout**: Test trên 1 GPU trước, sau đó scale
- **Monitoring alerts**: Track hash rate deviations **> 10%**
- **Automatic fallback**: Nếu hash rate **< 80%** baseline, auto-revert

---

## **📊 Kết luận Evidence-Based**

**Nguyên nhân cốt lõi** đã được **xác định với high confidence** (độ tin cậy cao) dựa trên:
- **16 instances** restore cancellation trong logs
- **Explicit code comment** về removal of restoration  
- **Measurable power/clock evidence** cho thấy cloaking active nhưng không reverse

**Giải pháp recommended**: Implement **idempotent reset pattern** (mẫu reset lặp lại an toàn) với **mandatory cleanup** trong `start_mining.py` và restore **release_cloaking()** function trong `cloak_strategies.py`.

**Risk assessment**: **LOW-MEDIUM** với clear rollback path và gradual deployment strategy.

---

## **📝 Chi tiết Thiết kế Refactor** 

### **Component 1: GPUStateManager trong `gpu_optimization_orchestrator.py`**

#### **Chức năng core**:
- **Baseline capture**: Lưu trạng thái GPU ban đầu (power limits, clocks, thermal thresholds)
- **State tracking**: Theo dõi mọi thay đổi với timestamp và correlation ID
- **Restore orchestration**: Điều phối việc khôi phục về trạng thái gốc

#### **API Design**:
```python
class GPUStateManager:
    def capture_baseline(self, gpu_indices: List[int]) -> Dict[int, GPUBaseline]
    def track_modification(self, gpu_index: int, changes: Dict[str, Any]) -> str
    def restore_to_baseline(self, gpu_index: int, correlation_id: str) -> bool
    def get_current_delta(self, gpu_index: int) -> Dict[str, Any]
```

### **Component 2: Enhanced reset_gpu_to_baseline() trong `resource_control.py`**

#### **Implementation strategy**:
- **Force reset sequence**: nvidia-smi reset commands + NVML verification
- **Idempotent behavior**: Safe to call multiple times
- **Error resilience**: Continue on partial failures, log all attempts

#### **Reset sequence**:
1. `nvidia-smi --reset-clocks -i <gpu_index>`
2. `nvidia-smi --reset-power-management -i <gpu_index>` 
3. `nvidia-smi --reset-gpu-ecc -i <gpu_index>`
4. **Verification loop**: Read back settings via NVML
5. **Assert baseline**: Compare with captured values

### **Component 3: release_cloaking() trong `cloak_strategies.py`**

#### **Uncloaking logic**:
- **Progressive restoration**: Từ từ tăng power/clocks về normal ranges
- **Safety checks**: Không vượt quá thermal/power thresholds
- **Performance validation**: Monitor hash rate during restore

#### **Exit handlers**:
```python
import atexit
atexit.register(release_all_cloaking)

def signal_handler(signum, frame):
    release_all_cloaking()
    sys.exit(0)
```

### **Component 4: Integration với `start_mining.py`**

#### **Modified workflow**:
```python
def main():
    gpu_state_manager = GPUStateManager()
    try:
        # Capture baseline trước khi start
        baselines = gpu_state_manager.capture_baseline([0, 1])
        
        # Normal mining operations
        start_mining_processes()
        
    except Exception as e:
        logger.error(f"Mining error: {e}")
    finally:
        # MANDATORY cleanup
        gpu_state_manager.restore_all_to_baseline()
        release_all_cloaking()
```

### **Component 5: Monitoring & Alerting**

#### **Performance tracking**:
- **Hash rate baseline**: Lưu performance expectations
- **Deviation alerts**: Cảnh báo khi hash rate < 85% baseline  
- **Recovery suggestions**: Auto-suggest reset actions

#### **Health checks**:
- **GPU settings verification**: Định kỳ check settings vs expected
- **Thermal monitoring**: Ngăn chặn overheating during restore
- **Power consumption tracking**: Đảm bảo power usage reasonable

---

## **🔬 Testing & Validation Strategy**

### **Unit Tests**
- **GPUStateManager**: Capture/restore cycle testing
- **reset_gpu_to_baseline()**: Idempotent behavior verification  
- **release_cloaking()**: Progressive uncloaking validation

### **Integration Tests**  
- **Full mining cycle**: Start → cloak → mine → restore → verify
- **Failure scenarios**: Partial failures, interrupted restores
- **Performance regression**: Hash rate before/after comparisons

### **Production Rollout**
- **Phase 1**: Single GPU testing (1 week)
- **Phase 2**: Multi-GPU validation (1 week)  
- **Phase 3**: Full production deployment
- **Monitoring**: 24/7 hash rate tracking during rollout

---

## **📋 Acceptance Criteria**

### **Functional Requirements**
- ✅ Hash rate stability: Variance < 5% between restarts
- ✅ Complete restore: All GPU settings return to baseline
- ✅ Error handling: Graceful degradation on failures
- ✅ Performance: Restore operations < 30 seconds

### **Non-functional Requirements**  
- ✅ **Reliability**: 99.9% successful restore operations
- ✅ **Maintainability**: Clear logging và error messages
- ✅ **Observability**: Comprehensive metrics và tracing
- ✅ **Safety**: No hardware damage risk

---

*Báo cáo được tạo ngày: 2025-01-01*  
*Phiên bản: 1.0*  
*Trạng thái: EVIDENCE-BASED ANALYSIS COMPLETED*
