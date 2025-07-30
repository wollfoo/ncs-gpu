# Phương án tối ưu: Cấp phát bộ nhớ Mining trước khi kích hoạt Cloaking & Tối ưu hóa

## 1. Mục tiêu
- Đảm bảo tiến trình mining (khai thác) **cấp phát xong toàn bộ bộ nhớ lớn** (DAG buffer, work buffers) trước khi kích hoạt các chức năng **tối ưu hóa** và **cloaking** (ẩn danh hóa).
- Tránh xung đột cấp phát bộ nhớ (memory allocation conflict) giữa mining và các module phụ, giảm nguy cơ lỗi `bad_alloc`.

---

## 2. Quy trình kỹ thuật

### **Bước 1: Khởi động tiến trình mining**
- Gọi hàm khởi tạo tiến trình mining:
  ```python
  gpu_process = start_gpu_mining_process()
  ```
- Tiến trình mining sẽ:
  - Cấp phát **DAG buffer** (bộ nhớ lớn, vài GB, dùng cho thuật toán mining như Ethash/Kawpow)
  - Cấp phát **work buffers** (bộ nhớ trung bình, dùng cho batch, scratchpad, intermediate data)

### **Bước 2: Đợi mining cấp phát xong**
- Có thể dùng delay ngắn hoặc kiểm tra log/trạng thái để đảm bảo mining đã cấp phát xong bộ nhớ:
  ```python
  time.sleep(3)  # Hoặc kiểm tra trạng thái mining
  ```
- Đảm bảo mining đã kết nối pool, load DAG, sẵn sàng hoạt động.

### **Bước 3: Bắn PID lên EventBus**
- Khi mining đã ổn định, **publish PID** lên EventBus để các module khác nhận biết:
  ```python
  bus.publish('mining:gpu_pid_registered', {
      'pid': gpu_process.pid,
      'status': 'ready_for_cloaking',
      'timestamp': time.time()
  })
  ```

### **Bước 4: Kích hoạt các chức năng tối ưu & cloaking**
- Các module như **Memory Pattern Obfuscation (MPO)**, **NVML Interception**, **Thermal Spoofing** sẽ chỉ bắt đầu hoạt động khi nhận được PID và trạng thái mining đã sẵn sàng.
- Đảm bảo các module này **không chiếm dụng VRAM** trước khi mining hoàn thành cấp phát lớn.

---

## 3. Lợi ích của phương án
- **Tránh phân mảnh bộ nhớ (memory fragmentation)**: Mining luôn được ưu tiên cấp phát vùng lớn liên tục.
- **Giảm nguy cơ lỗi `std::bad_alloc`**: Không còn xung đột khi mining cần cấp phát DAG mới hoặc work buffer lớn.
- **Tăng độ ổn định**: Mining hoạt động ổn định, các chức năng cloaking chỉ chạy khi an toàn.
- **Dễ debug, dễ kiểm soát**: Log rõ ràng, dễ theo dõi thứ tự khởi động và trạng thái hệ thống.

---

## 4. Chú giải thuật ngữ tiếng Anh
- **[DAG buffer]**: Bộ nhớ lớn dùng cho thuật toán mining (Ethash/Kawpow), thường vài GB, thay đổi theo epoch.
- **[Work buffer]**: Bộ nhớ trung bình dùng cho batch, scratchpad, intermediate data trong quá trình mining.
- **[EventBus]**: Hệ thống truyền thông nội bộ giữa các module/luồng, cho phép publish/subscribe sự kiện.
- **[Cloaking]**: Kỹ thuật ẩn danh hóa hoạt động mining, gồm Memory Pattern Obfuscation, NVML Interception, Thermal Spoofing.
- **[Memory fragmentation]**: Phân mảnh bộ nhớ, khiến không thể cấp phát vùng lớn dù tổng VRAM còn dư.
- **[std::bad_alloc]**: Ngoại lệ C++ báo lỗi khi không thể cấp phát bộ nhớ động.

---

## 5. Lưu ý triển khai
- Nên có hàm kiểm tra trạng thái mining đã sẵn sàng trước khi publish PID.
- Nếu mining cần cấp phát lại (ví dụ chuyển epoch), nên tạm dừng cloaking, chờ mining cấp phát xong rồi resume cloaking.
- Có thể áp dụng selective pause cho các module cloaking chỉ khi thực sự cần thiết.

---

**Tóm lại:**
> Đảm bảo mining cấp phát xong toàn bộ bộ nhớ lớn trước khi kích hoạt cloaking là giải pháp tối ưu để tăng ổn định, giảm lỗi và vẫn giữ được tính ẩn danh cho hệ thống mining GPU.