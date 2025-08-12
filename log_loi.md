
## xây dựng prompt với nội dung như bên dưới

## nội dung:

---



### 1️⃣ Quy tắc Ngôn ngữ
- **BẮT BUỘC**: Trả lời bằng **Tiếng Việt**.  
- **KÈM GIẢI THÍCH**: Mọi thuật ngữ Tiếng Anh phải được giải thích bằng Tiếng Việt.

**Cú pháp chuẩn**:[Thuật Ngữ Tiếng Anh] (mô tả Tiếng Việt – chức năng/mục đích)

### 🗂️ Bối Cảnh Kỹ Thuật
- **Docker image**: xây dựng từ `Dockerfile`, tag `gputraining:latest`.  
- **Container**: tên `opus-container`, truy cập bằng : `sudo docker exec -it opus-container bash`
- **Mount** thư mục mã nguồn: `-v "$(pwd)":/app:rw`
- **Lưu trữ log**:
* `/app/mining_debug.log`
* `/app/mining_environment/logs`

**Luồng logic chính**:

```text
start_mining.py (khởi tạo ResourceManager)
      ↓
 stealth_inference_cuda.py (khởi tạo GPU process)
      ↓ 
  HookCoordinator (nhận PID, xác minh GPU process cấp phát đầy đủ bộ nhớ rồi mới chuyển PID đến DirectPIDRegistry)
      ↓ 
  DirectPIDRegistry (chuyển PID đến ResourceManager)
      ↓ 
  ResourceManager (nhận PID, kích hoạt CloakRequest)
      ↓
cloak_strategies.py ( Nhận CloakRequest theo PID từ ResourceManager)
      ↓
resource_control.py (Nhận tham số từ CloakStrategies và áp dụng hardware control theo PID )

*(Song song: `setup_env.py` chuẩn bị môi trường)*  

```
## VAI TRÒ VÀ ĐỊNH VỊ
.
.
.

## ĐÁNH GIÁ NĂNG LỰC
.
.
.
Trước khi bắt đầu, hãy tự đánh giá:
```markdown
### Checklist Năng Lực Cần Thiết:
.
.
.
```

## THINKING HARD - SUY LUẬN SÂU
### 🧠 Quy Trình Tư Duy 3 Tầng:
.
.
.

### 3️⃣ Nhiệm vụ
1. Tôi đã khởi chạy start_mining.py trong container : `sudo docker exec -it opus-container bash`
2. Rà soát toàn bộ **codebase** trong `/app`.
3. Phân tích chi tiết **log lỗi** tại:
   * `/app/mining_debug.log`
   * `/app/mining_environment/logs`
   * `/app/mining_environment/logs/start_mining.log`
   * `/app/mining_environment/logs/resource_control.log`

4. Xác minh nguyên nhân cốt lõi gây ra lỗi log dưới đây :

```log
2025-08-12 06:04:22,819 - start_mining - INFO - unknown - [inference-cuda][R:0s] 2025-08-12 06:04:21,912 [ERROR] pid_logger - [SHM] Failed to setup shared memory: [Errno 2] No such file or directory: '/dev/shm/ncs_gpu_registry/registry.shm'
2025-08-12 06:04:22,318 - resource_control - ERROR - unknown - Lỗi NVML set power limit GPU=0: Invalid Argument
2025-08-12 06:04:22,318 - resource_control - ERROR - unknown - [RC] ❌ Failed to set power limit
2025-08-12 06:04:22,378 - resource_control - ERROR - unknown - Lỗi NVML set power limit GPU=0: Invalid Argument
```

8. Tìm **module/file , class, hàm , dòng code** liên quan đến các vấn đề trên
9. Đề xuất **giải pháp refactor**:
   * Tận dụng mã nguồn hiện có.
   * Không tạo module mới không cần thiết.
   * Không thay đổi cấu trúc thư mục.
10. Mọi **ý tưởng thiết kế** chỉ dừng ở mức mô tả theo quy tắc ngôn ngữ trên, ưu tiên nói tiếng việt bình dân; **không** cung cấp code.

### 4️⃣ Nguyên tắc Tư duy & Quy trình:
* **Vai trò**
* **Đánh giá**
* **Suy luận sâu (thinking hard)**
* **TREE-OF-THOUGHT** (😭): Phân nhánh nhiều hướng, tự chọn hướng tốt nhất.
* **SELF-REFINE**: Tự phê bình & chỉnh sửa tối đa 2 vòng.
* **ANTI-HALLUCINATION**:
  * Chỉ dựa trên **chứng cứ** (Evidence-Only).
  * Không giả định sáng tạo.
  * Giao tiếp bằng Tiếng Việt chuẩn xác.
  * **Trích dẫn** rõ nguồn log, file, đường dẫn.
  * **Giữ nguyên** verbatim code gốc khi nhắc lại.
* **Think Big, Do Baby Steps**: Nghĩ tổng thể, triển khai từng bước nhỏ.
* **Measure Twice, Cut Once**: Suy nghĩ kỹ trước khi đề xuất.
* **Quantity & Order**: Bảo đảm toàn vẹn dữ liệu, ưu tiên thứ tự thực thi.
* **Get It Working First**: Ưu tiên giải pháp có thể chạy trước, tối ưu sau.
* **Always Double-Check**: Luôn xác minh; không bao giờ chủ quan.

### 5️⃣ Định dạng Đầu ra
* **Markdown rõ ràng**: sử dụng heading, bullet, code block.
* **Dễ đọc**: khoảng cách hợp lý, highlight các từ khóa.
* **Dễ hiểu**: trình bày theo luồng logic.

### 🔟 Phạm vi:
* **Chỉ** thao tác trong `/app`.
* **Không** can thiệp thư mục hệ thống.
* **Không** đổi tên file/folder.
* Mọi đề xuất **giữ nguyên** cấu trúc thư mục & logic hiện tại.
* **Không** thực hiện hành động code, chỉ đưa ra ý tưởng thiết kế refactor.




