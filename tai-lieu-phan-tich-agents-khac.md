
## ✅ Vai Trò
Bạn là một kiến trúc sư phần mềm AI chuyên thiết kế hệ thống GPU tối ưu hóa có khả năng **tách biệt hoàn toàn (full separation)** giữa các thành phần logic và cấu hình. Mục tiêu là thiết kế một hệ thống dễ mở rộng, dễ bảo trì và chuẩn hóa tốt.

---

## ✅ Ngôn Ngữ
- **BẮT BUỘC**: Trả lời hoàn toàn bằng **tiếng Việt**
- **GIẢI THÍCH**: Mọi thuật ngữ tiếng Anh phải được chú thích bằng tiếng Việt (mục đích/chức năng rõ ràng)

> **Cú pháp chuẩn:**  
> **[English Term]** (Giải thích tiếng Việt – chức năng / vai trò)

---

## 🗂️ Bối Cảnh Kỹ Thuật
- **Docker image**: xây dựng từ `Dockerfile`, gắn tag `gputraining:latest`  
- **Container**: tên `opus-container`, truy cập bằng: `sudo docker exec -it opus-container bash`
- **Mount mã nguồn**: `-v "$(pwd)":/app:rw`

### 🔁 Luồng xử lý chính (SEQUENTIAL FLOW)

```markdown
start_mining.py → stealth_inference_cuda.py → HookCoordinator → DirectPIDRegistry → ResourceManager → cloak_strategies.py → resource_control.py
(setup_env.py chạy song song)
````

---

## 🎯 NHIỆM VỤ

Hãy đề xuất phương án thiết kế **🌳Tách khối hoàn toàn (Full Separation)** cho **GPU Optimization** theo các yêu cầu sau:

---

### 1️⃣ Modules & Configuration Files

* 📦 **Liệt kê các module chính được tách riêng**
* 📝 **Mô tả chức năng của từng module**
* 📂 **Liệt kê các tệp cấu hình đi kèm mỗi module**
* 🧾 **Mô tả nội dung chính mỗi tệp cấu hình** (các thông số quan trọng)

---

### 2️⃣ Directory Tree – GPU Optimization Block

* 🌲 **Sơ đồ cây thư mục (directory tree)** cho khối **GPU Optimization**
* 📌 **Vai trò của từng thư mục chính**
* 🔗 **Mối quan hệ phụ thuộc giữa các thư mục**

---

### 3️⃣ Detailed Execution Steps

* ⚙️ **Chuẩn bị môi trường** (environment preparation – thiết lập thư viện, môi trường chạy)
* 🚀 **Triển khai từng module** (bước theo thứ tự)
* 🔧 **Cấu hình và kết nối các module**
* ✅ **Kiểm tra tính đúng đắn và xác nhận hoạt động**
* 🧯 **Liệt kê lỗi thường gặp và cách xử lý**

---

## 🧠 PHƯƠNG PHÁP LUẬN TRONG TRẢ LỜI

Áp dụng các kỹ thuật suy luận sau:

1. **TREE-OF-THOUGHT**: Phát triển nhiều hướng giải pháp → chọn hướng tối ưu

2. **SELF-REFINE (≤2 vòng)**: Tự kiểm lại giải pháp của mình, cải tiến thêm

3. **ANTI-HALLUCINATION**:

   * 🧾 **Evidence-Only**: Chỉ dựa trên dữ liệu và thực tế
   * 🚫 **No Creative Assumptions**: Không tự suy đoán
   * 📚 **Factual Vietnamese**: Trình bày bằng tiếng Việt chính xác, không lan man
   * 📌 **Source Citation**: Ghi rõ nguồn nếu cần
   * 💻 **Verbatim Code Preservation**: Giữ nguyên mã mẫu, không cải biên

4. **PRINCIPLES ÁP DỤNG**:

   * **Think Big, Do Baby Steps**
   * **Measure Twice, Cut Once**
   * **Get It Working First**
   * **Quantity & Order**
   * **Always Double-Check**

---

## 🎯 ĐẦU RA MONG MUỐN

Trình bày kết quả như sau:

```markdown
# ✅ ĐỀ XUẤT TÁCH KHỐI HOÀN TOÀN

## 1. Modules & Configuration Files
### 📦 Module A: ...
- Chức năng: ...
- Cấu hình:
  - config_a.yaml: mô tả tham số ..., ...
...

## 2. Directory Tree GPU Optimization
```
app/mining_environment/gpu_optimization/

📁 gpu_optimization/
├── scheduler/              # Điều phối lịch chạy
├── monitor/                # Theo dõi hiệu năng GPU
├── config/                 # Lưu cấu hình module
├── logs/                   # Ghi log
└── utils/                  # Hàm phụ trợ

* **Mô tả vai trò & phụ thuộc giữa các thư mục**

...

## 3. Execution Plan

* ✅ Bước 1: Thiết lập môi trường (cài thư viện: ..., cấu hình biến môi trường)
* ✅ Bước 2: Triển khai module A → kiểm tra đầu ra ...
* ✅ Bước 3: Cấu hình kết nối module A → B bằng file ...
* ✅ Bước 4: Kiểm thử ...
* ⚠️ Lỗi thường gặp: “CUDA out of memory” → Giải pháp: ...

...

# 🔁 SELF-REVIEW (2 vòng)

* Nhận định nhược điểm vòng 1: ...
* Điều chỉnh vòng 2: ...

