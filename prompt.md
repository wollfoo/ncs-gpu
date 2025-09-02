**HÃY LỰA CHỌN CÁC SUB AGENTS PHÙ HỢP NHẤT VỚI YÊU CẦU CÔNG VIỆC VÀ TIẾN HÀNH TRIỂN KHAI TASK MỘT CÁCH HIỆU QUẢ**

# ✅ LANGUAGE RULES
- **MANDATORY**: Trả lời **bằng tiếng Việt**.
- **WITH EXPLANATION**: Mỗi thuật ngữ **English** đều phải kèm mô tả tiếng Việt theo cú pháp:
  - **[English Term]** *(mô tả tiếng Việt – chức năng/mục đích)*  
  - Ví dụ: **[throttle]** *(giới hạn tài nguyên có chủ đích để kiểm soát điện/nhệt/độ ổn định)*

---

# 🗂️ BỐI CẢNH KỸ THUẬT (Technical Context)
- **Codebase**: toàn bộ trong **`/app`**.
- **Docker image**: build từ **`Dockerfile`**, tag **`api-models:latest`**.
- **Luồng logic chính** *(main execution flow)*:
```

\[app/start\_mining.py] → \[stealth\_inference\_cuda.py] → \[inference-cuda]
→ \[coordinator.py] → \[direct\_registry.py]
→ \[resource\_manager.py] → \[cloak\_strategies.py]
→ (trong resource\_manager.py, sau cloaking) → \[gpu\_optimization\_orchestrator.py] → \[resource\_control.py]
→ \[app/start\_mining.py]

```

- **Log liên quan**:
  - `/app/mining_debug.log`
  - `/app/mining_environment/logs`

- **Triệu chứng từ người dùng (user-provided evidence)**:
  - Hashrate 2 GPU chỉ **`20.31 MH/s`**, từng đạt **`24.96 MH/s`**.
  - Khi **chỉ chạy app mining** (hệ thống tối ưu GPU **không chạy**), hashrate **vẫn tụt**.
  - Trích log:
    ```
    [2025-09-01 17:37:01.524]  nvidia   #0 00:00.0  75W 38C 412/877 MHz
    [2025-09-01 17:37:01.544]  nvidia   #1 00:00.0  75W 38C 412/877 MHz
    [2025-09-01 17:37:01.544]  miner    speed 10s/60s/15m 20.31 n/a n/a MH/s max 24.96 MH/s
    ```
  - Nghi ngờ: sau khi bật **throttle** *([power_limit], [sm_clock], [vram_target], [clock], [temperature])* xuất hiện **limit ẩn** *([hidden limit] – giới hạn không hiển thị trực tiếp]* hoặc **reset chưa hoàn toàn** *([incomplete reset] – trạng thái GPU chưa trở về mặc định]*, khiến GPU bị bó cứng.

---

# 🎯 VAI TRÒ & ĐỊNH VỊ (Role & Positioning)
Bạn là **Chuyên viên Điều tra Hiệu năng GPU** **[GPU Performance Investigator]** *(phân tích nguyên nhân gốc rễ – [root cause], xác thực bằng chứng – [evidence], đưa ra khuyến nghị khả thi – [actionable recommendations])* trong bối cảnh mining.  
Mục tiêu: **xác định nguyên nhân cốt lõi** gây **giới hạn tài nguyên GPU nghiêm trọng** *([severe resource capping])* và **tụt hashrate** sau nhiều vòng start/stop; đề xuất **refactor** **không** phá vỡ cấu trúc thư mục, **không** tạo module mới không cần thiết, **tận dụng tối đa mã nguồn hiện có**.

---

# 🧪 ĐÁNH GIÁ NĂNG LỰC (Self-Assessment Before Start)
Hãy tự chấm theo checklist (tick ✅ nếu tự tin, ❌ nếu không):
- Hiểu [NVIDIA NVML] *(thư viện quản lý GPU ở mức driver)*, [nvidia-smi] *(CLI điều khiển/truy vấn GPU)*, [application clocks] *(khóa xung nhịp core/mem theo giá trị xác định)*, [persistence mode] *(giữ context driver sống để tránh reset)*, [perf cap reasons] *(lý do giới hạn hiệu năng: Pwr, Thrm, VRel, VOp, Util…)*.
- Hiểu [idempotent reset] *(reset lặp lại cho kết quả như nhau, không để sót trạng thái)* và [cleanup on exit] *(hoàn nguyên cấu hình khi thoát)*.
- Đọc/định vị log, tái lập timeline sự kiện.
- Theo dấu [side effects] *(tác dụng phụ)* trong call graph Python.
- Ghi nhận/soi trạng thái GPU trước–trong–sau tối ưu (power, clocks, temp, P-state).

Nếu có mục ❌, nêu rõ rủi ro và cách bù đắp (ví dụ: cần thêm bằng chứng từ log).

---

# 🧠 THINKING HARD — QUY TRÌNH TƯ DUY 3 TẦNG
1) **Observation** *(quan sát)*: Thu thập **bằng chứng** từ code + log, không suy diễn.  
2) **Hypotheses** *(giả thuyết)*: Nêu nhiều giả thuyết độc lập, liên kết trực tiếp tới bằng chứng.  
3) **Validation** *(thẩm định)*: Đề xuất kiểm chứng tối thiểu, **không** chạy lệnh; chỉ mô tả cách xác minh, tiêu chí pass/fail.

---

# 🌳 TREE-OF-THOUGHT (😭)
Liệt kê **≥5 nhánh giả thuyết** có thể gây tụt hash sau nhiều vòng start/stop, ví dụ:
- **[Application clocks persistence]** *(khóa xung vẫn còn hiệu lực sau khi tắt optimizer)*.
- **[Power limit stickiness]** *(giới hạn công suất không được hoàn nguyên)*.
- **[Thermal hysteresis]** *(quán tính nhiệt khiến GPU giữ P-state thấp)*.
- **[Driver persistence mode interaction]** *(ngữ cảnh driver giữ lại cấu hình)*.
- **[Race condition]** *(điều kiện tranh chấp giữa mining và optimizer dẫn tới trạng thái trung gian)*.
- **[Cloaking side-effects]** *(chiến lược “ẩn mình” để lại hạn chế)*.
- **[Faulty reset order]** *(thứ tự reset sai khiến NVML bỏ qua một số thay đổi)*.
- **[Silent error handling]** *(bắt lỗi im lặng — swallow exceptions)*.
Chấm điểm từng nhánh theo **Impact / Likelihood / Effort** và **chọn 1–2 nhánh ưu tiên** để đào sâu.

---

# 🔒 ANTI-HALLUCINATION — EVIDENCE-ONLY
- **Không** suy đoán. **Chỉ** kết luận khi có **bằng chứng** từ:
  - Trích **log** (nguyên văn, kèm **timestamp**).
  - Trích **đoạn code** ngắn (nguyên văn, kèm **file path** + **số dòng** nếu có).  
  - Chỉ ra **luồng gọi** (call chain) tới các API NVML/**nvidia-smi wrapper** trong:
    - `resource_manager.py`, `gpu_optimization_orchestrator.py`, `resource_control.py`, `cloak_strategies.py`, `coordinator.py`, `direct_registry.py`, `start_mining.py`.
- **Cách trích dẫn chuẩn**:
```

\[EVIDENCE] /app/resource\_control.py:123–141
"set\_power\_limit(...)" ... "nvmlDeviceSetPowerManagementLimit(...)"  # nguyên văn

```
- Nếu thiếu bằng chứng, ghi rõ: **"Không đủ chứng cứ – cần bổ sung X"**.

---

# 🧩 3️⃣ NHIỆM VỤ BẮT BUỘC
1) **Rà soát toàn bộ codebase** trong `/app` (mô tả cấu trúc, entrypoints, call graph tới GPU control).
2) **Phân tích chi tiết log** tại:
 - `/app/mining_debug.log`
 - `/app/mining_environment/logs`
 Tạo **timeline** thay đổi trạng thái GPU (power/clocks/temp/P-state/perf caps) so với hoạt động mining.
3) **Chẩn đoán triệu chứng**: Nhiều lần khởi chạy mining, **hash không tăng**; khi **optimizer không chạy**, hashrate **vẫn thấp**.
4) **Đặt trọng tâm nghi vấn**: **limit ẩn/reset chưa hoàn toàn** sau khi dùng các throttle *([power_limit], [sm_clock], [vram_target], [clock], [temperature])*.
5) **Xác định nguyên nhân cốt lõi** *(root cause)* dẫn đến **giới hạn tài nguyên GPU nghiêm trọng**.
6) **Chỉ ra module/lớp/hàm** chịu trách nhiệm lớn nhất cho tình trạng trên (nêu rõ file, hàm, cơ chế state).
7) **Đề xuất refactor**:
 - **Tận dụng mã nguồn hiện có**.
 - **Không** tạo module mới **không cần thiết**.
 - **Không** thay đổi cấu trúc thư mục.
 - Chỉ mô tả **thiết kế/luồng/điều kiện**; **không cung cấp code**.
8) **Định dạng đầu ra**: Lưu thành **`/app/reports/report-04.md`** (Markdown rõ ràng, có heading/bullets/code block, highlight từ khóa; luồng logic dễ đọc).

---

# 🔬 KHUNG PHÂN TÍCH CHUẨN (Think Big, Do Baby Steps)
- **P0 — Inventory** *(kiểm kê)*: Map entrypoints, nơi chạm NVML/**nvidia-smi** (set/reset **[power limit]**, **[application clocks]**, **[persistence mode]**, **[fan/temperature targets]**).
- **P1 — State Model** *(mô hình trạng thái)*: Định nghĩa trạng thái **Trước / Trong / Sau** optimizer; nêu **biến toàn cục**/**singleton**/**cache** ảnh hưởng setpoint.
- **P2 — Failure Modes** *(cách thức hỏng)*: Mỗi giả thuyết phải có **dấu hiệu quan sát được** trong log hoặc code.
- **P3 — Validation Plan** *(kế hoạch thẩm định)*: Mô tả cách xác minh **không chạy lệnh**; tiêu chí pass/fail, nguồn dữ liệu cần.
- **P4 — Quick Wins** *(Get It Working First)*: Đề xuất **biện pháp an toàn tạm thời** (preflight reset, guardrail, single source of truth).
- **P5 — Hardening** *(Measure Twice, Cut Once)*: Chốt thiết kế giúp hệ thống **idempotent** và **có rollback**.

---

# 🧱 CHECKLIST TRIỆU CHỨNG & NGUYÊN NHÂN KHẢ DĨ
Đối chiếu từng mục với **bằng chứng**:
- **[Application clocks persistence]**: có **khóa xung** còn hiệu lực sau khi tắt? Truy vết hàm *apply/reset* trong `gpu_optimization_orchestrator.py` / `resource_control.py`.
- **[Power limit stickiness]**: có set **power_limit** nhưng **không reset**? Kiểm tra **try/except** nuốt lỗi.
- **[Perf cap reasons]** *(Pwr/Thrm/VRel/VOp/Util)*: log có ghi? Nếu không, đánh dấu **thiếu quan sát**.
- **[P-state lock]**: xung 412/877 MHz (thấp) cho thấy P-state xuống thấp? Có *idle heuristic* từ *cloaking*?
- **[Race/Order issues]**: thứ tự *set clocks → start miner → set power* có bị đảo? Có *cleanup on exit*?
- **[Persistence mode]**: bật **persistence** khiến state không reset giữa lần chạy?
- **[Thermal targets]**: throttle vì *temperature target*? Log nhiệt/điện tương quan?

---

# 🏗️ ĐỀ XUẤT REFACTOR (No New Modules, No Folder Changes)
> **Chỉ mô tả ý tưởng thiết kế** — **không cung cấp code**.

Ưu tiên **đang chạy được trước**:
1) **[Preflight Reset]** *(reset trước khi mining)*:  
 - Một điểm vào duy nhất (ví dụ trong `start_mining.py`) thực hiện **reset idempotent** cho **power limit / application clocks / persistence mode / temperature targets** trước khi khởi động mining.  
 - Ghi log **before/after** theo định dạng nhất quán để so sánh.

2) **[Single Source of Truth]** *(nguồn sự thật duy nhất về setpoint)*:  
 - Tập trung mọi **set/get** GPU state vào **một lớp hiện có** (ví dụ `resource_control.py`) — các nơi khác **chỉ gọi thông qua lớp này**.  
 - Cơ chế **state mirror** *(bản sao trạng thái)* trong bộ nhớ để tránh đặt lặp.

3) **[Deterministic Order]** *(thứ tự tất định)*:  
 - Chuẩn hóa trình tự: **reset → apply base → start miner → (tùy chọn) incremental tuning**.  
 - Cấm thao tác song song lên cùng tham số (lock ở `resource_manager.py`).

4) **[Guardrails & Rollback]** *(lan can & hoàn nguyên)*:  
 - Nếu **apply** thất bại ở bất kỳ bước nào, **rollback** về default; **không** để hệ thống ở trạng thái nửa vời.  
 - Log **nguyên văn exception** và **trạng thái GPU** ngay trước/ sau lỗi.

5) **[Exit Cleanup]** *(dọn dẹp khi thoát)*:  
 - Hook thoát có bảo đảm **reset** về default ngay cả khi có lỗi; ghi log chứng cứ.

6) **[Cloak Isolation]** *(cô lập tác dụng phụ của cloaking)*:  
 - `cloak_strategies.py` **không** được chạm trực tiếp NVML; chỉ thông qua `resource_control.py`.  
 - Mọi thay đổi bởi cloaking phải có **tag** trong log để truy ngược.

7) **[Observability Baseline]** *(nâng nền quan sát)*:  
 - Chuẩn hóa log định kỳ: **power (W)**, **clocks core/mem (MHz)**, **temp (°C)**, **P-state**, **perf cap reasons**; kèm **phase** (preflight/apply/mining/exit).  
 - Trích dẫn log theo mẫu **EVIDENCE** như trên.

---

# 🔁 SELF-REFINE (tối đa 2 vòng)
- **Vòng 1 — Bản nháp báo cáo**: trình bày phát hiện, giả thuyết, bằng chứng, khuyến nghị.
- **Vòng 2 — Tự phê bình**: chỉ ra lỗ hổng chứng cứ, thuật ngữ chưa giải thích, đề xuất chỉnh sửa; cập nhật báo cáo.
> Nếu vẫn thiếu chứng cứ quan trọng (ví dụ: không thấy **perf cap reasons**), **đánh dấu rõ** và **đề xuất đúng nguồn cần bổ sung** (log/file/vị trí trong code).

---

# 🗃️ OUTPUT — REPORT.MD
- **Đường dẫn**: `/app/reports/report-04.md`
- **Bố cục khuyến nghị**:
1. **Executive Summary** *(tóm tắt quản trị)*  
2. **Environment & Context** *(môi trường & bối cảnh)*  
3. **Evidence Timeline** *(dòng thời gian bằng chứng)*  
4. **Root Cause Analysis** *(phân tích nguyên nhân gốc rễ)*  
5. **Tree-of-Thought** *(giả thuyết → chọn hướng)*  
6. **Recommendations (Quick Wins → Hardening)**  
7. **Refactor Plan** *(không tạo module mới, không đổi cấu trúc)*  
8. **Risks & Rollback**  
9. **Open Questions (Thiếu chứng cứ cần bổ sung)**  
10. **Appendix: Trích dẫn log & code (verbatim)**

- **Phong cách trình bày**:
- Markdown rõ ràng; heading/bullets/code block.
- Mỗi **English term** phải kèm mô tả tiếng Việt.
- Nhấn mạnh từ khóa: **bold** các trạng thái, tham số GPU, file, hàm.

---

# 📏 QUALITY GATES (Always Double-Check)
- Không kết luận nếu thiếu bằng chứng trực tiếp.
- Mọi nhận định đều có **trích dẫn** (log/code/path).
- Thứ tự thực thi/thiết kế **rõ ràng**, nhất quán.
- Ưu tiên giải pháp **chạy được trước**, tối ưu sau.
- Kiểm tra chéo: triệu chứng **412/877 MHz & 75W & 38°C** có phù hợp **P-state/perf cap** đã nêu?

> **Bắt đầu ngay**: Thực hiện theo các bước trên và xuất **toàn bộ kết quả** vào **`/app/reports/report-04.md`**.
```
