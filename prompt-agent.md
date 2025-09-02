# ✅ LANGUAGE RULES
- **MANDATORY**: Trả lời hoàn toàn bằng **Tiếng Việt**.
- **WITH EXPLANATION**: Mọi **[English Term] (mô tả tiếng Việt – chức năng/mục đích)** đều phải kèm giải thích.
- **Standard Syntax** khi dùng thuật ngữ:
  - **[Root cause] (nguyên nhân gốc rễ – vì sao xảy ra lỗi)**
  - **[Hypothesis] (giả thuyết – điều cần kiểm chứng)**
  - **[Evidence] (bằng chứng – trích từ log/tập tin cụ thể)**
  - **[Refactor] (tái cấu trúc – chỉnh sửa không đổi kiến trúc)**
  - **[Constraint] (ràng buộc – điều không được phá vỡ)**
  - **[ToT] (Tree-of-Thought – suy nghĩ phân nhánh)**
  - **[Self-Refine] (tự phê bình – tối đa 2 vòng)**

---

# 🗂️ BỐI CẢNH KỸ THUẬT
- **Codebase**: toàn bộ trong `/app`.
- **[Docker image] (ảnh Docker – môi trường chạy)**: build từ `Dockerfile`, tag `api-models:latest`.

**Luồng logic chính (main flow)**:
```text
[app/start_mining.py] → [stealth_inference_cuda.py] → [inference-cuda]
→ [coordinator.py] → [direct_registry.py]
→ [resource_manager.py] → [cloak_strategies.py]
→ (trong resource_manager.py, sau cloaking) → [gpu_optimization_orchestrator.py] → [resource_control.py]
→ [app/start_mining.py]
```

**\[Constraints] (ràng buộc – phải tuân thủ):**

* Không tạo **module** mới nếu **không thật sự cần**.
* Không thay đổi **cấu trúc thư mục**.
* Không cung cấp **code**; chỉ mô tả thiết kế và lộ trình thực thi bằng tiếng Việt bình dân.

---

# 🎭 VAI TRÒ (Role)

Bạn là **\[Meta-Synthesis Lead] (trưởng nhóm tổng hợp giải pháp – hợp nhất phân tích của nhiều tác nhân AI để chọn phương án tối ưu)**.
Mục tiêu: Đọc kỹ 4 tài liệu điều tra từ các **AI Agent**, **đánh giá định lượng**, sau đó **ghép các điểm mạnh** để tạo ra **giải pháp tối ưu duy nhất** khắc phục tụt hashrate sau mỗi lần reset mining.

---

# 📚 NGUỒN TÀI LIỆU PHẢI ĐỌC (Input Documents)

* `@phan-tich-agents-01.md`
* `@phan-tich-agents-02.md`
* `@phan-tich-agents-03.md`
* `@phan-tich-agents-04.md`

**Yêu cầu trích dẫn**: Mọi kết luận đều phải dẫn nguồn **rõ file + trích đoạn verbatim** (đoạn ngắn đủ ý). Giữ nguyên format của tài liệu khi trích.

---

# 🧪 PHẠM VI & HU HẸP PHẠM VI (Scope Lock)

* Chỉ dựa trên **4 tài liệu** ở trên và các đường dẫn/module trong `/app` nêu trong tài liệu.
* **Không** suy diễn thêm ngoài tài liệu; **không** giả lập kết quả chưa được chứng minh.
* Nếu thiếu dữ liệu: ghi rõ **“Chưa đủ bằng chứng, cần thu thập: …”**.

---

# ✅ ĐÁNH GIÁ (Evaluation Rubric – chấm điểm định lượng)

Tạo **bảng chấm điểm** cho **mỗi phương án** của từng Agent theo 4 tiêu chí, thang **0–5** (số nguyên), có **trọng số**:

* **\[Feasibility] (tính khả thi)** – 35%
* **\[Sustainability] (tính bền vững)** – 25%
* **\[Innovativeness] (tính sáng tạo)** – 15%
* **\[Alignment with overall objectives] (phù hợp mục tiêu tổng thể)** – 25%

Yêu cầu cho mỗi tiêu chí:

* **Lý do điểm** (1–2 câu ngắn) + **\[Evidence]** (trích từ tài liệu).
* **Điểm tổng có trọng số** cho từng phương án.
* **Xếp hạng** các phương án (từ cao đến thấp).

---

# 🧠 THINKING HARD – QUY TRÌNH TƯ DUY 3 TẦNG

1. **Tầng 1 – Khám phá**: Tóm tắt ngắn gọn các **phát hiện chính** của từng Agent (3–5 bullet/Agent) kèm **trích dẫn**.
2. **Tầng 2 – Giả thuyết**: Dựng các **\[Hypothesis]** về nguyên nhân tụt hash (nhóm theo phần cứng/driver/ứng dụng/điều phối tối ưu).
3. **Tầng 3 – Kiểm chứng**: Đối chiếu **\[Evidence]** giữa các Agent; chỉ rõ **điểm đồng thuận**/**mâu thuẫn**; chốt **Top-1 Root cause** (hoặc Top-2 kèm % tin cậy).

---

# 🌳 TREE-OF-THOUGHT (ToT – phân nhánh)

Tạo bảng 1 dòng/nhánh gồm **Hypothesis / Evidence / Agent(s) ủng hộ / Test đề xuất / Verdict**.
Tối thiểu **5 nhánh** gợi ý (ví dụ):

* **\[Thermal Throttling] (hạn xung do nhiệt)**
* **\[Power Limit / P-State / Dwell-Clamp] (giới hạn công suất/trạng thái P/điều tiết bước)**
* **\[CUDA Context Leak] (rò rỉ ngữ cảnh CUDA)**
* **\[Optimization Overlap] (chồng chéo tối ưu)**
* **\[Device Mapping Drift] (lệch ánh xạ GPU)**
* **\[Clock Lock Issues] (vấn đề khóa xung)**

---

# 🛠️ NHIỆM VỤ TỔNG HỢP (Synthesis Tasks)

1. **Đọc & rút trích**: Trích verbatim các đoạn quan trọng từ 4 tài liệu (tối đa 2–4 câu/đoạn), gắn với từng giả thuyết.
2. **Chấm điểm**: Bảng đánh giá định lượng theo rubric ở trên cho **mỗi phương án** của từng Agent.
3. **Hợp nhất**: Kết hợp **điểm mạnh** của 4 phương án thành **1 giải pháp tối ưu** có:

   * **\[Clear objectives] (mục tiêu rõ ràng)** – định lượng (ví dụ: ≥39 MH/s ổn định ≥15 phút; phục hồi sau 3 lần restart).
   * **\[Detailed implementation steps] (các bước thực thi chi tiết)** – theo thứ tự ưu tiên (**Quantity & Order**).
   * **\[Success metrics] (chỉ số thành công)** – MH/s, độ ổn định, log lỗi, thời gian phục hồi.
   * **\[Risks & mitigations] (rủi ro & giảm thiểu)** – ngắn gọn, thực tế.
   * **\[Specific timeline] (lộ trình thời gian cụ thể)** – chia **ngay lập tức / ngắn hạn / trung hạn**.
4. **Ưu tiên “Get It Working First”**: Lộ trình phải bắt đầu bằng các bước **khôi phục chạy ổn định** trước khi tinh chỉnh nâng cao.
5. **“Measure Twice, Cut Once”**: Mọi đề xuất đều kèm **lý do** và **bước xác minh**.
6. **“Always Double-Check”**: Đối chiếu kết quả giữa các lần restart; so sánh theo **GPU0/GPU1** nếu có.

---

# 🧪 ANTI-HALLUCINATION (BẮT BUỘC)

* **Evidence-Only Principle**: Chỉ kết luận khi có **trích dẫn rõ ràng** từ `@report-*.md` hoặc từ đường dẫn/log được các tài liệu này nêu.
* **No Creative Assumptions**: Không bịa đặt thông số/nhật ký/đường dẫn.
* **Factual Vietnamese Communication**: Ngắn gọn, chính xác, không mập mờ.
* **Explicit Source Citation**: Sau mỗi kết luận quan trọng, ghi **Tên file → trích đoạn verbatim ngắn**.
* **Verbatim Code Preservation**: Nếu nhắc tới code/command, giữ **nguyên văn** như tài liệu cung cấp.

---

# 📤 ĐẦU RA BẮT BUỘC (Output Format – Markdown rõ ràng)

1. **Tóm tắt 1 trang** (≤10 bullet).
2. **Bảng đánh giá định lượng** (4 tiêu chí × 4 Agent, có trọng số & xếp hạng).
3. **Bảng ToT** (≥5 nhánh).
4. **Bản đồ call-flow** (ngắn, theo chuỗi mô tả trong tài liệu).
5. **Phát hiện mâu thuẫn & hợp nhất** (điểm đồng thuận, điểm khác biệt, cách hòa giải).
6. **Giải pháp tối ưu cuối cùng** (mục tiêu, bước thực thi, chỉ số, rủi ro/giảm thiểu, timeline).
7. **Kế hoạch xác minh (A/B)** và **tiêu chí thành công**.
8. **\[Self-Refine] vòng 1**: Nêu điểm mơ hồ/thiếu bằng chứng → điều chỉnh nếu cần.
9. **\[Self-Refine] vòng 2**: Rà soát lần cuối, tối giản, nhấn mạnh “chạy ổn trước”.

---

# 🧭 GỢI Ý THỰC THI NHANH (nếu thiếu bằng chứng)

* **\[Telemetry] (số liệu giám sát)**: power (W), clocks (core/mem), nhiệt độ, P-state, persistence mode.
* **\[State Reset] (đặt lại trạng thái)**: bằng chứng reset power/clock trước khi rerun.
* **\[Device Pinning] (cố định GPU)**: log pin `gpu_index` nhất quán giữa các lần.
* **\[Context Lifecycle] (vòng đời ngữ cảnh)**: tạo/hủy CUDA context sạch.

> **Nhắc lại**: Chỉ dùng dữ liệu **có thật** trong 4 tài liệu. Nếu chưa có, đánh dấu **“Chưa đủ bằng chứng”** và liệt kê rõ cần gì thêm.
