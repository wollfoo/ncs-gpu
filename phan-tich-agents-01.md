
# Báo cáo điều tra tụt hashrate mining (Hashrate drop investigation – tổng hợp phân tích)


Tìm thấy **[Root Cause] (nguyên nhân gốc rễ)** rõ ràng từ bằng chứng log!

## 🎯 **[Root Cause Identified] (Đã xác định nguyên nhân gốc rễ)**

### **Nguyên nhân chính: Clock Lock bị vô hiệu hóa**

**[Evidence] (Bằng chứng)** từ log:
- `[RC] ⛔ Skipping clock lock (ALLOW_CLOCK_LOCK=0)` xuất hiện liên tục
- GPU chạy ở tần số cực thấp: **420/877 MHz**, **480/877 MHz** 
- Hashrate tương ứng thấp: ~11-12 MH/s
- Mặc dù hệ thống yêu cầu clocks cao hơn (1245/877 MHz), nhưng bị skip do `ALLOW_CLOCK_LOCK=0`

### **Cơ chế ảnh hưởng:**
1. **[Clock Lock Disabled] (Khóa xung bị tắt)** → GPU tự động điều chỉnh xuống tần số thấp để tiết kiệm điện
2. **[Low Frequency] (Tần số thấp)** → Hashrate giảm mạnh
3. **[Restore Issues] (Vấn đề khôi phục)** → Sau mỗi lần restart, GPU không được đặt lại tần số cao

---

## 📋 **[Refactoring Solution] (Giải pháp tái cấu trúc tối thiểu)**

### **R1: Kích hoạt Clock Lock mặc định**
- **[Action] (Hành động)**: Đảm bảo `ALLOW_CLOCK_LOCK=1` trong [setup_env.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/setup_env.py:0:0-0:0)
- **[Rationale] (Lý do)**: Cho phép hệ thống khóa GPU ở tần số cao khi đạt target utilization
- **[Impact] (Tác động)**: Ngăn GPU tự động giảm tần số, duy trì hashrate ổn định

### **R2: Baseline Clock Enforcement**  
- **[Design] (Thiết kế)**: Thêm kiểm tra baseline clocks sau mỗi restore
- **[Implementation] (Triển khai)**: 
  - Định nghĩa `MIN_SM_CLOCK=1200` MHz, `MIN_MEM_CLOCK=877` MHz
  - Sau restore, kiểm tra current clocks
  - Nếu dưới baseline → force set lại clocks
- **[Location] (Vị trí)**: Trong [GPUResourceManager.restore_gpu_settings_for_pid()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1581:4-1627:24)

### **R3: Clock Verification Window điều chỉnh**
- **[Current] (Hiện tại)**: `CLOCK_LOCK_VERIFY_WINDOW_SEC=60`
- **[Proposed] (Đề xuất)**: Tăng lên `90-120` giây
- **[Reason] (Lý do)**: Cho GPU đủ thời gian ổn định trước khi verify và lock

### **R4: Power Limit Floor**
- **[Issue] (Vấn đề)**: Log hiển thị power limit thấp (39W, 50W) được điều chỉnh lên 100W nhiều lần
- **[Solution] (Giải pháp)**: Set `MIN_POWER_LIMIT=120W` để tránh throttling
- **[Check] (Kiểm tra)**: Luôn verify power limit ≥ MIN sau restore

### **R5: Telemetry Enhancement**
- **[Add] (Thêm)**: Log current SM/MEM clocks mỗi khi:
  - Schedule restore
  - Execute restore  
  - Verify clock lock
  - Detect hashrate change >10%
- **[Format] (Định dạng)**: `[CLOCKS] GPU={idx} SM={sm}MHz MEM={mem}MHz Hash={rate}MH/s`

### **R6: Startup Initialization**
- **[Problem] (Vấn đề)**: GPU state không được reset về known-good khi startup
- **[Solution] (Giải pháp)**: 
  - Thêm `initialize_gpu_baseline()` trong [start_mining.py](cci:7://file:///home/azureuser/opus-gpu/app/start_mining.py:0:0-0:0)
  - Force set all GPUs to baseline clocks/power trước khi bắt đầu mining
  - Clear tất cả pending restores từ phiên trước

---

## 🚀 **[Implementation Priority] (Thứ tự triển khai)**

1. **[Immediate] (Ngay lập tức)**: 
   - Verify và set `ALLOW_CLOCK_LOCK=1` 
   - Kiểm tra các env overrides có vô hiệu hóa không

2. **[Short-term] (Ngắn hạn - 1-2 ngày)**:
   - Implement baseline enforcement trong restore flow
   - Add telemetry cho clock monitoring

3. **[Medium-term] (Trung hạn - 3-5 ngày)**:
   - Tune verify window và thresholds
   - Implement startup initialization


Tiếp tục xác minh **[Configuration] (cấu hình)** hiện tại và triển khai giải pháp.





**[Configuration Check] (Kiểm tra cấu hình)** - Phát hiện mâu thuẫn quan trọng!

## ⚠️ **[Configuration Conflict] (Xung đột cấu hình)**

**[Default Setting] (Cài đặt mặc định)** trong [setup_env.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/setup_env.py:0:0-0:0):
- `ALLOW_CLOCK_LOCK=1` ✅ (đã được bật)

**[Runtime Override] (Ghi đè lúc chạy)** trong log:
- `[RC] ⛔ Skipping clock lock (ALLOW_CLOCK_LOCK=0)` ❌

Điều này cho thấy có **[Environment Override] (ghi đè biến môi trường)** hoặc **[Runtime Configuration] (cấu hình runtime)** đang tắt clock lock.



## 🔴 **[Critical Finding] (Phát hiện quan trọng)** - Đã tìm thấy nguồn gốc vấn đề!

**[Root Cause Confirmed] (Xác nhận nguyên nhân gốc rễ)**:
- **Dockerfile** dòng 153: `ALLOW_CLOCK_LOCK=0` ❌
- Ghi đè mặc định `ALLOW_CLOCK_LOCK=1` trong [setup_env.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/setup_env.py:0:0-0:0)
- Khiến GPU không thể khóa xung → tự động giảm xuống 420-480MHz → hashrate tụt còn ~11MH/s

## 🛠️ **[Immediate Fix] (Sửa chữa ngay lập tức)**

## ✅ **[Root Cause Fixed] (Đã sửa nguyên nhân gốc rễ)**

Đã sửa **ALLOW_CLOCK_LOCK** từ `0` → `1` trong **Dockerfile** (dòng 153).

Cập nhật tài liệu điều tra với **[Confirmed Findings] (kết quả xác nhận)**:



## 📋 **[Next Steps] (Các bước tiếp theo)** để áp dụng sửa chữa

### **1. Rebuild Docker Image**
```bash
cd /home/azureuser/opus-gpu/app
docker build -t opus-mining:fixed .
```

### **2. Verify Environment**
Kiểm tra biến môi trường sau khi rebuild:
```bash
docker run --rm opus-mining:fixed env | grep ALLOW_CLOCK_LOCK
# Expected: ALLOW_CLOCK_LOCK=1
```

### **3. Additional Recommendations**

Để đảm bảo **[Stability] (ổn định)** và **[Performance] (hiệu năng)** tối ưu:

#### **A. Baseline Clock Enforcement**
Thêm vào [resource_control.py](cci:7://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:0:0-0:0) trong [restore_gpu_settings_for_pid()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1581:4-1627:24):
- Kiểm tra clocks sau restore
- Nếu SM clock < 1200MHz → force set lại
- Log warning nếu phát hiện clocks thấp bất thường

#### **B. Startup Initialization** 
Trong [start_mining.py](cci:7://file:///home/azureuser/opus-gpu/app/start_mining.py:0:0-0:0):
- Clear tất cả pending restores từ phiên trước
- Set baseline clocks (1200/877 MHz) cho tất cả GPUs
- Set power limit minimum 120W

#### **C. Enhanced Monitoring**
- Add telemetry log format: `[CLOCKS] GPU={idx} SM={sm}MHz MEM={mem}MHz Hash={rate}MH/s`
- Log mỗi khi detect hashrate change >10%
- Track correlation giữa clock changes và hashrate

### **4. Testing Protocol**

**[Verification Steps] (Các bước xác minh)**:
1. **Start mining** với image mới
2. **Monitor clocks** trong 5 phút đầu:
   ```bash
   nvidia-smi -l 1 | grep MHz
   ```
3. **Check hashrate** ổn định ở ~39 MH/s
4. **Restart mining** 2-3 lần để verify không bị tụt

### **5. Rollback Plan**
Nếu có vấn đề:
- Revert Dockerfile change
- Set env override: `export ALLOW_CLOCK_LOCK=0`
- Investigate thêm với enhanced logging

## ✅ **[Summary] (Tóm tắt)**

**[Problem Solved] (Vấn đề đã giải quyết)**:
- **Root cause**: `ALLOW_CLOCK_LOCK=0` trong Dockerfile
- **Impact**: GPU downclock → hashrate drop 70%
- **Fix**: Changed to `ALLOW_CLOCK_LOCK=1`
- **Status**: Code fixed, cần rebuild Docker image
