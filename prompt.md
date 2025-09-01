# 🧠 PROMPT ĐIỀU TRA TỤT HASH GPU — EVIDENCE-ONLY

## ✅ Language Rules
- **MANDATORY**: Trả lời bằng **tiếng Việt**.
- **WITH EXPLANATION**: Mọi thuật ngữ **[English Term] (mô tả tiếng Việt – chức năng/mục đích)**.
- **Standard Syntax**: **[English Term]** (mô tả tiếng Việt – function/purpose).

---

## 🗂️ Bối Cảnh Kỹ Thuật
- **[codebase] (toàn bộ mã nguồn – phạm vi phân tích)**: `/app`
- **[Docker image] (ảnh Docker – môi trường chạy)**: build từ `Dockerfile`, tag `api-models:latest`.

**Luồng logic chính** (điểm “hook” để lần dấu cài đặt/tháo cài đặt GPU):
```

\[app/start\_mining.py] → \[stealth\_inference\_cuda.py] → \[inference-cuda]
→ \[coordinator.py] → \[direct\_registry.py]
→ \[resource\_manager.py] → \[cloak\_strategies.py]
→ (trong resource\_manager.py, sau cloaking) → \[gpu\_optimization\_orchestrator.py] → \[resource\_control.py]
→ \[app/start\_mining.py]

```

**Thuật toán đào**: **[kawpow] (thuật toán KAWPOW – đặc trưng nhạy cảm xung nhịp/độ trễ bộ nhớ)**  
**Đơn vị hiệu năng**: **[hash rate] (tốc độ băm – chỉ số hiệu năng đào)**

---

## 🎯 VAI TRÒ & ĐỊNH VỊ
Bạn là **[Senior GPU Performance Engineer] (kỹ sư hiệu năng GPU cao cấp – chịu trách nhiệm tìm nguyên nhân & ổn định hiệu năng)**, kiêm **[SRE] (kỹ sư độ tin cậy – chuẩn hóa quy trình, rollback)**, làm việc **evidence-only** trong phạm vi code & log nêu trên.  
Mục tiêu: Xác định **nguyên nhân cốt lõi** tụt **[hash rate] (tốc độ băm)** do **giới hạn tài nguyên GPU** sau nhiều lần **stop/start**; chỉ ra **module/lớp/hàm** liên quan; đề xuất **refactor** **không tạo module mới**, **không đổi cấu trúc thư mục**, **tận dụng mã hiện có**, và **chỉ mô tả thiết kế** (không cung cấp code).

---

## 🧩 DỮ LIỆU CHỨNG CỨ
**Log & đường dẫn phải trích dẫn nguyên văn (verbatim) khi lập luận**:

1) **Lần 1** — ~**29.12 MH/s**:
```log
2025-09-01 12:40:33,359 - gpu_miner - INFO - unknown - [2025-09-01 12:40:33][inference-cuda[gpu1]][R:115s] 2025-09-01 12:40:33,359 - stealth_inference - INFO - unknown - [inference-cuda-stdout] [2025-09-01 12:40:33[1;30m.359[0m] [44;1m[1;37m net     [0m [1;35mnew AI computation task[0m from [1;37mAI Server 127.0.0.1:4444[0m difficulty level [1;37m4295M[0m algorithm [1;37mkawpow[0m height [1;37m4001420[0m, task progress: 1 unit (equivalent to 32669992.44 H/s)[0m
2025-09-01 12:40:33,360 - gpu_miner - INFO - unknown - [2025-09-01 12:40:33][inference-cuda[gpu0]][R:121s] 2025-09-01 12:40:33,359 - stealth_inference - INFO - unknown - [inference-cuda-stdout] [2025-09-01 12:40:33[1;30m.359[0m] [44;1m[1;37m net     [0m [1;35mnew AI computation task[0m from [1;37mAI Server 127.0.0.1:4444[0m difficulty level [1;37m4295M[0m algorithm [1;37mkawpow[0m height [1;37m4001420[0m, task progress: 1 unit (equivalent to 29598351.54 H/s)[0m
2025-09-01 12:40:33,361 - gpu_miner - INFO - unknown - [96m📊 METRICS [inference-cuda[gpu0]]: Current=29598351.54 H/s | Avg5=21137320.27 H/s | TotalAvg=21137320.27 H/s | Samples=5 | Runtime=121s[0m
````

2. **Lần 2** — \~**20.59 MH/s**:

```log
2025-09-01 12:53:35,738 - gpu_miner - INFO - unknown - [2025-09-01 12:53:35][inference-cuda[gpu1]][R:274s] 2025-09-01 12:53:35,737 - stealth_inference - INFO - unknown - [inference-cuda-stdout] PCA computation complete. Top eigenvalue: 0.968844
2025-09-01 12:53:36,327 - gpu_miner - INFO - unknown - [2025-09-01 12:53:36][inference-cuda[gpu0]][R:281s] ... algorithm [1;37mkawpow[0m ... (equivalent to 17065126.22 H/s)
2025-09-01 12:53:36,330 - gpu_miner - INFO - unknown - ... (equivalent to 19788845.50 H/s)
```

3. **Lần 3+** — \~**12.87 MH/s**:

```log
2025-09-01 17:45:30,787 - gpu_miner - INFO - unknown - [2025-09-01 17:45:30][inference-cuda[gpu1]][R:63s] ... [42;1m[1;37m nvidia  [0m[1;36m #0[0m[0;33m 00:00.0[0m[1;35m  75W[0m[1;32m 38C[0m[1;37m 405/877 MHz[0m[0m
2025-09-01 17:45:30,788 - gpu_miner - INFO - unknown - ... [1;37mspeed[0m 10s/60s/15m [1;36m11.87[0m ... [1;36mMH/s[0m max [1;36m11.91 MH/s[0m
PCA computation complete. Top eigenvalue: 0.9682
2025-09-01 17:46:54,836 - stealth_inference - INFO - ... task progress: 1 unit (equivalent to 8989106.73 H/s)
```

4. **Trường hợp đặc biệt** — **không chạy hệ thống tối ưu GPU** vẫn chỉ \~**20.31 MH/s**:

```log
[2025-09-01 17:37:01.524]  nvidia   #0 00:00.0  75W 38C 412/877 MHz
[2025-09-01 17:37:01.544]  nvidia   #1 00:00.0  75W 38C 412/877 MHz
[2025-09-01 17:37:01.544]  miner    speed 10s/60s/15m 20.31 n/a n/a MH/s max 24.96 MH/s
```

**Đường dẫn log bắt buộc đọc:**

* `/app/mining_debug.log`
* `/app/mining_environment/logs`

---

## 📝 ĐÁNH GIÁ NĂNG LỰC (tự kiểm trước khi làm)

### Checklist Năng Lực Cần Thiết

* Hiểu **\[NVML] (thư viện quản trị NVIDIA – đọc/đặt trạng thái GPU)**; **\[nvidia-smi] (công cụ dòng lệnh – quan sát/reset giới hạn)**; **\[P-state] (trạng thái hiệu năng – P0 nhanh/P8 chậm)**; **\[Application Clocks] (khóa xung ứng dụng – cố định core/mem)**; **\[Power Limit] (giới hạn công suất – giới hạn boost)**; **\[Thermal Throttle] (giới hạn nhiệt – hạ xung khi nóng)**.
* Kiến thức **\[CUDA] (nền tảng tính toán NVIDIA – ngữ cảnh/khởi tạo/teardown)**, **\[MPS] (dịch vụ đa tiến trình – ảnh hưởng chia tài nguyên)**, **\[MIG] (chia tách GPU – giới hạn phần cứng)**.
* Am hiểu **\[kawpow] (thuật toán – phụ thuộc băng thông VRAM & xung core/mem)**.
* Nắm kiến trúc **Docker** (ràng buộc quyền với **\[NVML] (thư viện NVIDIA)** trong container), xử lý **restart idempotent** (khởi chạy lặp không để lại “dư âm” cấu hình).

Nếu thiếu, ghi rõ: “**Không đủ chứng cứ**: \<nêu mục thiếu>”.

---

## 🧠 THINKING HARD — Quy Trình Tư Duy 3 Tầng

* **Tầng 1 — Sự kiện/Chứng cứ**: Trích nguyên văn dòng log + file/đường dẫn + thời điểm; ví dụ: “`… 405/877 MHz …` (nguồn: `<file>`, `<timestamp>`).”
* **Tầng 2 — Giả thuyết (đánh nhãn)**:

  * **\[Evidence-backed] (dựa chứng cứ)**: liên kết trực tiếp tới log/code.
  * **\[Speculative] (cần kiểm chứng)**: nêu **cách kiểm chứng cụ thể** bằng log/code hiện có.
* **Tầng 3 — Kế hoạch kiểm tra**: Các bước nhỏ, **\[idempotent] (lặp lại cho kết quả ổn định)**, không tạo module mới.

---

## 🌳 TREE-OF-THOUGHT (😭) — Phân Nhánh & Chọn Hướng

Tạo ít nhất 3 nhánh, mỗi nhánh nêu **triệu chứng → giả thuyết → bằng chứng → test**:

1. **Nhánh A — Driver/OS**: **\[Persistence Mode] (chế độ duy trì)**, **\[Application Clocks] (khóa xung)** còn **sticky** (bám dính) sau stop/start; **\[PowerMizer] (quản lý năng lượng)** kẹt ở **\[P8] (trạng thái chậm)** ⇒ log “`405/877 MHz`” là dấu hiệu.
2. **Nhánh B — Ứng dụng/Orchestrator**: **\[gpu\_optimization\_orchestrator.py] (điều phối tối ưu)** & **\[resource\_control.py] (điều khiển tài nguyên)** đặt **power/xung/temperature** nhưng **không reset** (thiếu teardown), hoặc **cloaking** trong **\[cloak\_strategies.py] (chiến lược che giấu)** cố ý hạ xung và **không nhả** khi dừng.
3. **Nhánh C — Miner/Workload**: thay đổi **\[dataset DAG] (bộ dữ liệu đồ thị)**/**\[intensity] (mức tải)**/**\[affinity] (ghim CPU/GPU)** dẫn tới **underutilization** (không tận dụng hết).

Chọn **1 hướng tốt nhất** dựa **log** (giải thích vì sao) + **bước xác minh** tương ứng.

---

## 🛡️ ANTI-HALLUCINATION — Evidence-Only

* **Không suy đoán** nếu **không có log/code**. Viết: “**Không đủ chứng cứ**: \<mục>”.
* Khi nhắc **code**: trích **verbatim** đúng file/hàm (ví dụ: `/app/resource_control.py: set_power_limit(...)`).
* Khi nhắc **log**: trích **verbatim** đúng dòng/timestamp/thiết bị.
* Không sáng tạo tình tiết. Không suy rộng ngoài **/app** & log đã nêu.

---

## 📦 PHẠM VI & RÀNG BUỘC

* **Không** tạo module mới. **Không** đổi cấu trúc thư mục. **Chỉ** tận dụng mã có sẵn.
* **Chỉ mô tả thiết kế** (no code).
* Ưu tiên **Get It Working First** (làm chạy ổn định trước), tối ưu sau.

---

## ✅ NHIỆM VỤ CỤ THỂ (thực hiện theo thứ tự — Quantity & Order)

1. **Rà soát toàn bộ \[codebase] (mã trong `/app`)**: liệt kê **module/lớp/hàm** có thao tác:

   * **\[power\_limit] (giới hạn công suất)**, **\[sm\_clock] (xung nhân CUDA)**, **\[vram\_target/mem\_clock] (xung bộ nhớ)**, **\[temperature] (nhiệt độ/điểm ngưỡng)**, **\[application clocks] (khóa xung)**, **\[persistence mode] (duy trì)**, **\[compute mode] (chế độ tính toán)**.
   * Ghi **điểm vào/điểm thoát**: ai **áp dụng**, ai **reset/teardown**.
   * Tập trung: `resource_control.py`, `gpu_optimization_orchestrator.py`, `resource_manager.py`, `cloak_strategies.py`, `start_mining.py`.
2. **Phân tích log** tại:

   * `/app/mining_debug.log`
   * `/app/mining_environment/logs`
   * So sánh **clock (MHz)**, **công suất (W)**, **nhiệt độ (°C)**, **hash (MH/s)** giữa lần 1/2/3.
   * Đánh dấu dấu hiệu **P8/idle** qua chuỗi “`405/877 MHz`”, “`412/877 MHz`”.
3. **Xác định nguyên nhân cốt lõi tụt \[hash rate] (tốc độ băm)** sau stop/start:

   * Ràng buộc: lần 1 \~29.12 MH/s → lần 2 \~20.59 MH/s → lần 3+ \~12.87 MH/s.
   * Lưu ý “**không chạy hệ thống tối ưu** mà vẫn \~20.31 MH/s” ⇒ có thể còn **giới hạn “sticky”**.
4. **Chỉ ra module/lớp/hàm liên quan trực tiếp** (trích dẫn file + tên hàm **verbatim**) tới **đặt giới hạn** và **không reset**.
5. **Đề xuất refactor (Design-only – mô tả, không code)**

   * **\[Idempotent reset] (reset lặp lại an toàn)**: thêm luồng **khôi phục trạng thái GPU** ban đầu (xung, power, nhiệt) trong **`resource_control.py`** và **gọi bắt buộc** từ **`start_mining.py`** (khối **\[finally] (luôn chạy kể cả khi lỗi)**).
   * **\[Single Source of Truth] (nguồn trạng thái duy nhất)**: trong **`gpu_optimization_orchestrator.py`** lưu **ảnh trạng thái gốc** khi start, và **chỉ áp dụng delta**; cuối vòng đời **nhả về gốc**.
   * **\[Cloak release] (nhả che giấu)**: đảm bảo **`cloak_strategies.py`** có **đường thoát** nhả mọi hạ xung; chứng minh bằng log cuối phiên.
   * **\[Double-check] (xác minh kép)**: sau reset, **đọc lại** clock/power từ **NVML** và ghi **log assert** (ví dụ: “`restored >= baseline`”).
   * Không thêm module; **nhúng** chức năng trong file hiện có.
6. **Kế hoạch kiểm chứng tuần tự (Think Big, Do Baby Steps)**:

   * B1: **Chụp baseline**: lần start đầu ghi clock/power/temp **mỗi GPU** (log).
   * B2: **Áp dụng → Xác minh**: sau khi áp dụng bất kỳ throttle, **đọc lại** để xác nhận giá trị thật.
   * B3: **Dừng → Reset → Xác minh**: tại stop, chạy **reset idempotent**, rồi **đọc lại** clock/power; so sánh với baseline.
   * B4: **Start lại miner**: đối chiếu **hash** với baseline trong 2–5 phút đầu; ghi chênh lệch %.
7. **Báo cáo kết quả** theo format dưới.

---

## 🔁 SELF-REFINE (tối đa 2 vòng)

* **Vòng 1 — Tự phê bình**: Liệt kê 3 chỗ còn mơ hồ/thiếu chứng cứ; yêu cầu log/điểm code cần bổ sung (nếu có).
* **Vòng 2 — Chỉnh sửa**: Cập nhật kết luận/giải pháp dựa trên bổ sung hoặc ghi “Không đủ chứng cứ”.

---

## 🧪 OUTPUT FORMAT (Markdown rõ ràng, dễ đọc)

**lưu kết quả thành một file `report.md` trong thư mục `/app/reports`**

### 1) Tóm tắt hiện trạng

* Dòng thời gian & con số **MH/s** theo từng lần, trích log nguồn.

### 2) Cây nguyên nhân (Tree-of-Thought tóm tắt)

* Nhánh A/B/C: (triệu chứng → giả thuyết → bằng chứng → test). Đánh dấu nhánh chọn.

### 3) Nguyên nhân cốt lõi (Root Cause)

* Gạch đầu dòng, **evidence-only** (trích dẫn log/file).

### 4) Module/Lớp/Hàm bị ảnh hưởng

* Danh sách: `file.py: Class/Func` → vai trò → bằng chứng (log/code trích dẫn).

### 5) Thiết kế refactor (không code)

* **\[Idempotent reset] (reset an toàn)** trong `resource_control.py` + gọi từ `start_mining.py`.
* **\[Single Source of Truth] (nguồn trạng thái duy nhất)** trong `gpu_optimization_orchestrator.py`.
* **\[Cloak release path] (đường nhả cloaking)** trong `cloak_strategies.py`.
* **\[Double-check logging] (log xác minh kép)** sau mỗi thao tác.

### 6) Kế hoạch kiểm chứng & tiêu chí “Get It Working First”

* Các bước B1→B4; tiêu chí pass/fail (ví dụ: ±5% so với baseline lượt 1).

### 7) Rủi ro & phương án rollback

* Tác động phụ khả dĩ + cách hoàn nguyên ngay (bằng quy trình reset đã mô tả).

> **Luôn “Always Double-Check”**: mọi kết luận phải đi kèm **trích dẫn log/file**. Nếu thiếu: “Không đủ chứng cứ”.
