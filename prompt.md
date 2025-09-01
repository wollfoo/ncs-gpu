# Hãy chọn sub agent phù hợp để thực hiện task này 

# Chẩn đoán tụt hash mining GPU sau nhiều lần restart

## ✅ Language Rules
- **MANDATORY**: Trả lời bằng **Tiếng Việt**.  
- **WITH EXPLANATION**: Mọi thuật ngữ **[English Term] (mô tả tiếng Việt – chức năng/mục đích)** phải kèm **mô tả tiếng Việt ngắn** ngay sau lần xuất hiện **đầu tiên** trong phần trả lời.
- **Standard Syntax** khi trích dẫn thuật ngữ:  
  **[Application clocks] (xung ứng dụng – cấu hình xung nhịp do ứng dụng đặt)**, **[Power limit] (giới hạn công suất – ràng buộc TDP)**, **[Persistence mode] (chế độ duy trì – giữ ngữ cảnh GPU khi không có tiến trình)**, **[CUDA context] (ngữ cảnh CUDA – phiên làm việc GPU)**, **[NVML] (thư viện quản lý NVIDIA – API đọc/đặt trạng thái GPU)**, **[Thermal throttling] (giảm xung do nhiệt – hạ tần số để hạ nhiệt)**, **[P-state] (trạng thái hiệu năng – cấp xung/điện của GPU)**, **[KawPow] (thuật toán mining – workload dạng memory-hard)**, **[TOT/Tree-of-Thought] (cây suy luận – phân nhánh giả thuyết)**, **[Self-Refine] (tự hiệu chỉnh – vòng rà soát cải tiến)**.

---

## 🗂️ Bối Cảnh Kỹ Thuật
- **Codebase**: toàn bộ trong `/app`.
- **Docker image** (ảnh Docker – gói môi trường chạy): build từ `Dockerfile`, tag `api-models:latest`.

**Luồng logic chính** (kiểm tra theo thứ tự và trích dẫn file/func thực tế):
```

\[app/start\_mining.py] → \[stealth\_inference\_cuda.py] → \[inference-cuda]
→ \[coordinator.py] → \[direct\_registry.py]
→ \[resource\_manager.py] → \[cloak\_strategies.py]
→ (trong resource\_manager.py, sau cloaking) → \[gpu\_optimization\_orchestrator.py] → \[resource\_control.py]
→ \[app/start\_mining.py]

```

---

## 📦 Dữ Liệu Log (Evidence ban đầu – trích dẫn nguyên văn)
> Lần 1 (≈ **29.12 MH/s**)
```

2025-09-01 12:40:33,359 ... task progress: 1 unit (equivalent to 32669992.44 H/s)
2025-09-01 12:40:33,360 ... task progress: 1 unit (equivalent to 29598351.54 H/s)
... 📊 METRICS \[inference-cuda\[gpu0]]: Current=29598351.54 H/s | ...

```

> Lần 2 (≈ **20.59 MH/s**)
```

2025-09-01 12:53:36,327 ... task progress: 1 unit (equivalent to 17065126.22 H/s)
... 📊 METRICS \[inference-cuda\[gpu0]]: Current=17065126.22 H/s | ...
2025-09-01 12:53:36,329 ... task progress: 1 unit (equivalent to 19788845.50 H/s)
... 📊 METRICS \[inference-cuda\[gpu1]]: Current=19788845.50 H/s | ...

```

> Lần 3+ (≈ **10.87 MH/s**)
```

2025-09-01 13:39:28,220 ... task progress: 1 unit (equivalent to 10646703.18 H/s)
... 📊 METRICS \[inference-cuda\[gpu1]]: Current=10646703.18 H/s | ...
2025-09-01 13:39:28,226 ... task progress: 1 unit (equivalent to 10198681.48 H/s)
... 📊 METRICS \[inference-cuda\[gpu0]]: Current=10198681.48 H/s | ...

```

**Log cần đọc từ máy chạy thật**:
- `/app/mining_debug.log`
- `/app/mining_environment/logs` (duyệt tất cả file con theo mốc thời gian)

> **Lưu ý**: Khi trích chứng cứ, luôn ghi **timestamp**, **module**, **dòng** và **đường dẫn file** nếu có.

---

## 👤 Vai Trò & Định Vị
Bạn là **[Senior GPU Performance Engineer] (kỹ sư hiệu năng GPU cao cấp – chịu trách nhiệm chẩn đoán & tối ưu)**.  
Mục tiêu: Tìm **nguyên nhân cốt lõi** tụt hash sau nhiều lần dừng/chạy lại mining **KawPow (thuật toán mining – workload memory-hard)**; xác định **module/lớp** liên quan; đề xuất **refactor** tận dụng mã nguồn sẵn có, **không** thêm module không cần và **không** đổi cấu trúc thư mục.

---

## 🧪 Đánh Giá Năng Lực Trước Khi Làm (Checklist)
Đánh dấu ✅ nếu bạn **đủ**:
1. Hiểu **[CUDA context] (ngữ cảnh CUDA – phiên làm việc GPU)**, **[P-state] (trạng thái hiệu năng)**, **[Application clocks] (xung ứng dụng)**, **[Power limit] (giới hạn công suất)**, **[Persistence mode] (chế độ duy trì)**.
2. Biết đọc/đặt trạng thái GPU qua **[NVML] (thư viện quản lý NVIDIA)** hoặc lệnh hệ thống tương đương.
3. Nắm **khoá cổ chai** mining **KawPow (thuật toán mining – memory/bandwidth-bound)**.
4. Thành thạo **điều tra hồi quy** (so sánh lần 1 vs 2 vs 3).
5. Tuân thủ **Evidence-Only (chỉ theo chứng cứ)**, không giả định.

Nếu có mục ❌, hãy **nêu rõ giới hạn** trước khi kết luận.

---

## 🧠 THINKING HARD — Quy Trình Tư Duy 3 Tầng (tóm tắt cấp cao, **không** lộ “sổ tay suy nghĩ vi mô**)** 
1) **Quan sát**: Tóm tắt số liệu & dấu hiệu bất thường (hash, runtime, event liên quan GPU).  
2) **Giả thuyết có thể kiểm chứng**: Ví dụ:  
   - **[Thermal throttling] (giảm xung do nhiệt)** theo thời gian.  
   - **[Power limit] (giới hạn công suất)** bị hạ dần giữa các lượt.  
   - **[Application clocks] (xung ứng dụng)** bị ghi đè/chồng chéo sau **cloaking**.  
   - **[CUDA context] (ngữ cảnh CUDA)** rò rỉ, giữ **P-state** thấp.  
   - **Tối ưu GPU chồng chéo** giữa `gpu_optimization_orchestrator.py` và `resource_control.py`.  
   - Đường dữ liệu/đồng bộ trong `resource_manager.py` sau bước **cloaking** làm khóa bận.  
3) **Thử nghiệm xác minh**: Tìm **log bằng chứng** trong các module liên quan (liệt kê chính xác file/func/dòng, trích nguyên văn). Kết luận **đúng/sai** cho từng giả thuyết.

> **Tree-of-Thought (TOT)**: Liệt kê **3–5 nhánh giả thuyết** như trên, đánh giá **pro/con** ngắn gọn và **chọn nhánh mạnh nhất** bằng **chứng cứ**.  
> **Self-Refine**: Tối đa **2 vòng**. Mỗi vòng: (i) nêu điểm yếu/còn thiếu **chứng cứ**, (ii) bổ sung kiểm tra/đọc log, (iii) cập nhật kết luận ngắn.

---

## ✅ Nhiệm Vụ Cụ Thể (theo thứ tự)
1. **Rà soát toàn bộ codebase** trong `/app`:  
   - Liệt kê **module/lớp/hàm** liên quan luồng chính (trên).  
   - Tập trung `resource_manager.py`, `cloak_strategies.py`, `gpu_optimization_orchestrator.py`, `resource_control.py`, `stealth_inference_cuda.py`.  
   - **Trích nguyên văn** chữ ký hàm/đoạn code khi nhắc tới (verbatim – không chỉnh sửa).
2. **Phân tích log** tại:  
   - `/app/mining_debug.log`  
   - `/app/mining_environment/logs`  
   Yêu cầu: **Trích dẫn chính xác** các dòng thể hiện **đặt/đọc**: nhiệt độ, xung, **P-state**, **Power limit**, **Application clocks**, lỗi **CUDA**, reset device, thay đổi **Persistence mode**, thông báo “tối ưu”/“cloaking”/“orchestrator”.  
3. **Chuẩn hoá mốc suy giảm hash**:  
   - Lần 1: ~**29.12 MH/s** (dẫn chứng dòng cụ thể).  
   - Lần 2: ~**20.59 MH/s** (dẫn chứng).  
   - Lần 3+: ~**10.87 MH/s** (dẫn chứng).  
   - Vẽ **bảng so sánh** (timestamp → hash → sự kiện liên quan GPU gần đó).  
4. **Xác định nguyên nhân cốt lõi**:  
   Trả lời **rõ ràng**: do **thuật toán tối ưu GPU sai**, hay do **tối ưu chồng chéo**, hay do **mỗi lần tối ưu làm hạ dần trần sử dụng GPU** (ví dụ giữ **P-state** thấp, hạ **Power limit**, khoá **Application clocks**, hoặc tắt **Persistence mode** vô tình).  
   - Mọi kết luận phải có **evidence** (trích dẫn log/code).  
5. **Chỉ rõ module & lớp liên quan**:  
   - Kể tên file/lớp/hàm và **vai trò**: ai **đọc/đặt** xung, công suất, nhiệt; ai **gọi** ai; thứ tự gọi.  
   - Trích nguyên văn khi nêu chữ ký hàm/đoạn config.  
6. **Đề xuất giải pháp refactor** (không viết code):  
   - **Giữ nguyên** cấu trúc thư mục, **tận dụng** mã hiện có, **không** tạo module mới nếu không bắt buộc.  
   - Mô tả **thiết kế** ở mức ý tưởng:  
     - “Chuẩn hoá đầu vào tối ưu” (**[single source of truth] – nguồn cấu hình duy nhất**).  
     - “Hàng rào tuần tự hoá” (**[idempotent] – lặp lại không đổi trạng thái**, **[re-entrant] – vào lại an toàn**) khi set **Application clocks/Power limit**.  
     - “Bộ nhớ đệm trạng thái” (**[state cache] – cache tham số GPU** tránh set lặp).  
     - “Kiểm tra sức khoẻ sau tối ưu” (**[post-optimization health check] – xác nhận P-state/xung/giới hạn**).  
     - “Log có cấu trúc” (**[structured logging] – key-value, timestamp, gpu-id**).  
   - **Get It Working First**: ưu tiên phương án **ít thay đổi**, nhanh áp dụng, có thể bật/tắt.  
7. **Kế hoạch xác minh & đo lường**:  
   - Trước/Sau: mục tiêu khôi phục **~29–30 MH/s**.  
   - Quy trình test **3 lượt khởi động** liên tiếp; log các tham số **nhiệt/xung/P-state/power**.  
   - **Always Double-Check**: lặp lại trên **gpu0/gpu1**; so sánh chéo.

---

## 🧯 ANTI-HALLUCINATION (BẮT BUỘC)
- **Evidence-Only**: Mọi nhận định **phải** kèm **trích dẫn** (log/file/đường dẫn).  
- **Không bịa đặt** tên hàm/biến/module. Nếu không tìm thấy, hãy ghi **“không thấy trong mã nguồn/log”**.  
- Khi nhắc lại mã, dùng **verbatim** (không đổi 1 ký tự).  
- Nếu thiếu dữ liệu, **nêu thiếu gì** + **đề xuất đọc ở đâu**.

---

## 🧱 Ràng Buộc & Thứ Tự Thực Thi
- **Không cung cấp code**; chỉ mô tả thiết kế theo quy tắc ngôn ngữ.  
- **Không** tạo module mới không cần thiết; **không** đổi cấu trúc thư mục.  
- Thực hiện theo **thứ tự nhiệm vụ 1→7**.  
- **Measure Twice, Cut Once**: Kiểm tra log 2 lần trước khi kết luận.  
- **Think Big, Do Baby Steps**: Ý tưởng tổng thể → bước nhỏ khả thi.

---

## 📤 Định Dạng Đầu Ra (Markdown rõ ràng)
1. `# Tóm tắt phát hiện` (3–5 gạch đầu dòng)  
2. `# Bảng dòng thời gian & hash`  
3. `# TOT: Giả thuyết & bằng chứng` (bảng pro/con + trích dẫn)  
4. `# Kết luận nguyên nhân cốt lõi` (1 đoạn ngắn + trích dẫn)  
5. `# Module/Lớp/Hàm liên quan` (danh sách có đường dẫn + trích nguyên văn)  
6. `# Giải pháp refactor (không code)` (ý tưởng theo ràng buộc)  
7. `# Kế hoạch xác minh` (bước test, tiêu chí pass/fail)  
8. `# Self-Refine vòng 1` (thiếu sót + bổ sung)  
9. `# Self-Refine vòng 2` (chốt)  

> **Ghi nhớ**: Tổng hợp ngắn gọn, **không** lộ “sổ tay suy nghĩ vi mô”; chỉ cung cấp **tóm tắt cấp cao** của lập luận.
