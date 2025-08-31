# RÀ SOÁT & TÁI CẤU TRÚC ORCHESTRATION MULTI-GPU (ổn định ánh xạ PID↔GPU, tránh tối ưu nhầm GPU)

## ✅ Language Rules
- **MANDATORY**: Trả lời **tiếng Việt**.
- **WITH EXPLANATION**: Mọi thuật ngữ **tiếng Anh** phải kèm mô tả tiếng Việt.
- **Standard Syntax**: **[English Term]** (mô tả tiếng Việt – chức năng/mục đích)

---

## 🗂️ Bối Cảnh Kỹ Thuật
- Toàn bộ **[codebase]** (mã nguồn) trong: `/app`
- **[Docker image]** (ảnh Docker – gói chạy): build từ `Dockerfile`, tag `api-models:latest`
- **Luồng logic chính**:
```text
  [app/start_mining.py] → [stealth_inference_cuda.py] → [inference-cuda]
  → [coordinator.py] → [direct_registry.py]
  → [resource_manager.py] → [cloak_strategies.py]
  → (trong resource_manager.py, sau cloaking) → [gpu_optimization_orchestrator.py] → [resource_control.py]
  → [app/start_mining.py]
```

* **Nguồn log để đối chiếu** (evidence):

  * `/app/mining_debug.log`
  * `/app/mining_environment/logs` (thư mục chứa log con, ví dụ **\[GPUOptimizationOrchestrator.log]** (nhật ký bộ điều phối tối ưu GPU – hoạt động/target GPU))
  * Ghi chú: Khi trích dẫn, nêu **đường dẫn + timestamp + dòng log**. Nếu thiếu, ghi **“Không có chứng cứ — cần xác minh”**.

---

## VAI TRÒ VÀ ĐỊNH VỊ

Bạn là **Kiến trúc sư hệ thống & Điều phối Multi-GPU** (chịu trách nhiệm tính đúng đắn ánh xạ **PID↔GPU** và điều phối tối ưu hóa):

* Thiết kế/chuẩn hóa **\[orchestration]** (điều phối – luồng gọi, thứ tự, ràng buộc) giữa `resource_manager.py`, `gpu_optimization_orchestrator.py`, `resource_control.py`.
* Đảm bảo một **\[binding]** (ràng buộc – ánh xạ duy nhất) giữa **\[process PID]** (mã tiến trình) và **\[GPU device]** (thiết bị GPU).
* Giữ ổn định, không thay đổi cấu trúc thư mục, **tận dụng mã hiện có**, chỉ **refactor** (tái cấu trúc – làm rõ trách nhiệm, tránh trùng lặp) ở mức cần thiết.

---

## ĐÁNH GIÁ NĂNG LỰC

Trước khi bắt đầu, tự đánh giá ngắn (Có/Không, mức tự tin):

```markdown
### Checklist Năng Lực Cần Thiết:
- Hiểu [CUDA multi-GPU] (CUDA đa GPU – enumerate thiết bị, chọn device theo index)
- Biết [NVML] (thư viện quản trị NVIDIA – đọc PID đang gắn với GPU) hoặc tương đương
- Nắm [Linux process namespace] (không gian tên tiến trình – PID trong container vs host)
- Hiểu [Docker] (môi trường container – cgroups, hạn quyền) & [logging] (ghi log – mức, format)
- Kinh nghiệm [concurrency control] (điều khiển đồng thời – lock, debounce, idempotency)
- Kiến thức [orchestration pipeline] (chuỗi điều phối – event → handler → trạng thái)
- Biết phân biệt [logical pid] (PID logic trong hệ) vs [real pid] (PID thực tế OS) & [ppid] (PID cha)
```

---

## THINKING HARD — 🧠 Quy Trình Tư Duy 3 Tầng

* **Tầng 1 — Macro**: Mục tiêu, ràng buộc (không đổi cấu trúc, không tạo module mới), tiêu chí thành công (không còn tối ưu sai GPU).
* **Tầng 2 — Meso**: Ai sinh PID? ai gắn PID với GPU? ai phát lệnh tối ưu? trạng thái được lưu ở đâu? cơ chế **\[idempotent]** (không gây tác dụng phụ khi lặp lại) thế nào?
* **Tầng 3 — Micro**: Bước đọc log, bước dựng bảng **PID↔GPU**, bước so khớp, bước ngăn broadcast, bước xác minh.

---

## 3️⃣ Nhiệm vụ

1. **Rà soát toàn bộ codebase** trong `/app` (chỉ ra file chịu trách nhiệm ánh xạ PID↔GPU, nơi phát lệnh tối ưu).
2. **Phân tích log** tại:

   * `/app/mining_debug.log`
   * `/app/mining_environment/logs` (liệt kê file con liên quan, đặc biệt `start_mining.log` và `GPUOptimizationOrchestrator.log`)
3. **Sự cố hiện tại** (theo log):

   * Multi-GPU: `started miner for GPU 0 (PID=249, real=250)` ⇒ tiến trình **PID thực = 250** chạy trên **GPU 0**
     Nhưng `GPUOptimizationOrchestrator.log` lại báo:

     * **Starting GPU optimization** (bắt đầu tối ưu GPU – khởi động quá trình tối ưu) **for PID 250 on GPU 0** **và** **for PID 250 on GPU 1**
       → Gọi tối ưu sai lên GPU 1, dẫn đến lỗi:

     ```log
     2025-08-31 11:17:37,543 - optimized_hardware_controller - ERROR - unknown - ❌ [OHC.optimize_for_pid] Process 250 not found (backoff=5.00s, misses=1)
     ```
   * Ngược lại: khi `started miner for GPU 1 (PID=313, real=316)` ⇒ **PID thực = 316** trên **GPU 1**, vẫn bị gọi tối ưu trên **GPU 0** và **GPU 1**.
4. **Tìm nguyên nhân cốt lõi**: xác định **vì sao một PID bị tối ưu trên nhiều GPU** (nhầm **broadcast**, sai **map PID↔GPU**, lệch **namespace PID**, hay **mặc định “all GPUs”**).
5. **Đề xuất giải pháp refactor**:

   * Tận dụng mã nguồn hiện có.
   * **Không** tạo module mới không cần thiết.
   * **Không** thay đổi cấu trúc thư mục.
   * Chỉ mô tả **concept** theo quy tắc ngôn ngữ; **không** cung cấp code.

---

## TREE-OF-THOUGHT (😭) — Phân nhánh & Chọn hướng

Đề xuất **≥3 nhánh** giải pháp, mỗi nhánh nêu rõ:

* **Ý tưởng chính**; **Ưu/nhược**; **Rủi ro**; **Khi nào dùng**.
* Ví dụ hướng gợi ý:

  1. **\[Registry-first]** (ưu tiên sổ cái PID↔GPU – một nguồn sự thật)
  2. **\[Orchestrator-filter-first]** (lọc chặt trong `gpu_optimization_orchestrator.py` theo **target\_gpu**)
  3. **\[Event-bus-scoping]** (phạm vi kênh sự kiện – topic theo GPU, cấm broadcast toàn cục)
* **Chọn 1 nhánh** phù hợp nhất bối cảnh, nêu **lý do** & **tiêu chí quyết định** (đơn giản, ít đụng chạm, hiệu quả).

---

## SELF-REFINE — Tự phê bình (tối đa 2 vòng)

* **Vòng 1 (Critique)**: Chỉ ra điểm mơ hồ, chỗ phụ thuộc mong manh (ví dụ: lấy **\[device index]** (chỉ số thiết bị) từ nguồn không ổn định), nơi có nguy cơ **race condition** (điều kiện tranh chấp).
* **Vòng 2 (Refine)**: Siết lại đề xuất: thêm **guard idempotent**, **lock theo PID** (khóa theo tiến trình), **debounce** (chống dồn lệnh), tiêu chí xác minh.

---

## ANTI-HALLUCINATION — Evidence-Only

* **Chỉ dựa trên chứng cứ** từ file/thư mục **thật có**:
* Đường dẫn: `/app/...`, tên file, **timestamp**, trích **verbatim** dòng log/code gốc khi cần (bọc trong block trích dẫn).
* Khi chưa thấy chứng cứ: ghi **“Không có chứng cứ — cần xác minh”** (không suy đoán).
* Nếu so chiếu PID trong container vs host: nêu rõ nguồn xác thực (log nào chỉ PID “real”, log nào chỉ PID “logic”).

---

## Think Big, Do Baby Steps

* Vẽ **bức tranh tổng thể** rồi triển khai **bước nhỏ** (MVP trước, tối ưu sau).
* **Get It Working First**: Ưu tiên thay đổi **nhỏ, ít rủi ro**, dễ rollback.

---

## Measure Twice, Cut Once

* Liệt kê **giả định** (assumptions), **ràng buộc**, **rủi ro**:

  * \[botched mapping] (ánh xạ lỗi – PID lặp), \[broadcast] (phát lệnh toàn cục), \[namespace mismatch] (lệch không gian tên PID), \[race condition] (tranh chấp), \[rate limit] (giới hạn tần suất tối ưu).
* Đề xuất **KPIs**:

  * Tỷ lệ gọi tối ưu **đúng GPU** (%), số **lần lỗi “Process not found”**, thời gian **time-to-optimize** trung bình, số **retry/backoff**.
* **Acceptance Criteria** (tiêu chí chấp nhận):

  * Mỗi **PID** chỉ có **1 GPU đích** trong toàn bộ log.
  * **0** lần lỗi “Process X not found” sau N phiên chạy liên tiếp.
  * Nhật ký **traceable** (truy vết được): mỗi lệnh tối ưu ghi **PID, GPU, nguồn phát, reason**.

---

## Quantity & Order — Thứ tự thực thi (kế hoạch có điều kiện vào/ra)

1. **Thu thập log** → Liệt kê mọi dòng “started miner … (PID=…, real=…)” và “Starting GPU optimization …” (Input: file log; Output: bảng **PID↔GPU dự kiến** vs **GPU bị gọi**).
2. **Đối chiếu code**: tìm nơi tạo **binding PID↔GPU** (dự kiến: `direct_registry.py` hoặc `resource_manager.py`) và nơi phát lệnh tối ưu (`gpu_optimization_orchestrator.py`).
3. **Phát hiện điểm rò**: kiểm tra xem **orchestrator** có **broadcast** lệnh lên **tất cả GPU** hay có **for-loop qua mọi GPU** khi nhận một **PID** duy nhất.
4. **Đề xuất thay đổi nhỏ nhất**:

   * Thêm/chuẩn hóa **filter theo target\_gpu** trước khi gọi tối ưu.
   * Củng cố một **\[PID→GPU registry]** (bảng ánh xạ) dùng chung (single source of truth).
   * Áp dụng **lock theo (PID, GPU)** + **idempotent guard** trong `gpu_optimization_orchestrator.py` hoặc `resource_control.py`.
5. **Xác minh**: chạy lại và kiểm tra log (Output: không còn “Process not found”).
6. **Fallback**: nếu thiếu target\_gpu trong sự kiện → tra registry; nếu registry thiếu → **skip** an toàn + ghi cảnh báo.
7. **Retry/Backoff**: chỉ retry khi **PID còn sống** và **binding hợp lệ**.

---

## Phân tích nguyên nhân cốt lõi — Hướng dẫn tìm cho ra gốc lỗi

* Kiểm tra **đường đi tham số**: từ `resource_manager.py` (sau cloaking) truyền gì qua `gpu_optimization_orchestrator.py`? Có **field target\_gpu** không? Nếu **None** ⇒ có bị hiểu là **“all”**?
* Xem **for-loop** trong `gpu_optimization_orchestrator.py`: có duyệt **tất cả GPU** cho **một PID**? (Trích **verbatim** nếu có bằng chứng.)
* Rà **direct\_registry.py**: có lưu **map PID→GPU** không? Cơ chế **update/evict** (cập nhật/thu hồi) thế nào? Có thể bị **race** khi PID mới sinh?
* Đối chiếu **PID trong container** vs **host**: log ghi `PID=249, real=250` ⇒ dùng **PID nào** khi tối ưu? Nếu dùng **PID logic** nhưng kiểm tra bằng **PID thực** (hoặc ngược lại) ⇒ sẽ báo **“Process not found”** trên GPU không khớp.
* Tìm bằng chứng trong log **“Starting GPU optimization for PID X on GPU Y”** xuất hiện **nhân đôi** cho **Y=0** và **Y=1** với cùng **PID** ⇒ củng cố giả thuyết **broadcast**.

---

## Gợi ý giải pháp refactor (Concept-only, không code)

* **\[Registry-first]**:

  * Chuẩn hoá **bảng PID→GPU** tại `direct_registry.py` (nguồn sự thật).
  * Mọi lệnh tối ưu trong `gpu_optimization_orchestrator.py` phải **resolve** (tra) **target\_gpu** từ bảng này nếu thiếu/không tin cậy tham số.
  * Thêm **idempotent guard**: nếu `(PID, GPU)` đã tối ưu trong T giây gần nhất ⇒ **bỏ qua**.
* **\[Orchestrator-filter-first]**:

  * Ở `gpu_optimization_orchestrator.py`, **bắt buộc** có **target\_gpu** hợp lệ trước khi gọi `resource_control.py`.
  * Nếu nhận **PID** nhưng không xác định **GPU** ⇒ **skip + warn** (cảnh báo có dẫn chứng log).
* **\[Event-bus-scoping]**:

  * Nếu đang dùng **\[pub/sub]** (xuất/nhận sự kiện), chia **topic theo GPU**; handler chỉ nhận **topic GPU** của mình.
  * Tránh **broadcast** tới tất cả GPU khi payload chỉ chứa **PID**.

**Không tạo module mới**, không đổi cấu trúc; chỉ **thêm logic lọc/tra cứu** ngay trong file hiện hữu và **chuẩn hoá registry**.

---

## ALWAYS DOUBLE-CHECK

* Đối chiếu **3 nguồn** cho mỗi phiên:

  1. Dòng log **spawn miner** (PID, real PID, GPU)
  2. Dòng log **starting optimization** (PID, GPU)
  3. Xác thực **PID còn sống** trên **GPU tương ứng** (theo log/trace hiện có)
* Nếu không đủ chứng cứ: đánh dấu **“Không có chứng cứ — cần xác minh”** thay vì suy đoán.

---

## ĐẦU RA BẮT BUỘC (Output Format)

* **Markdown rõ ràng**, có heading, bullet, bảng khi cần.
* Văn phong **dễ đọc**, highlight từ khoá.
* Trình bày theo luồng **Macro → Meso → Micro**.
* **Có TREE-OF-THOUGHT**, **2 vòng SELF-REFINE**.
* **Evidence-Only**: mọi kết luận đều kèm **trích dẫn** (đường dẫn + timestamp + dòng log).
* **Không cung cấp code**. Nếu cần trích code gốc để chứng minh, **giữ nguyên verbatim** + nêu đường dẫn file & dòng.
