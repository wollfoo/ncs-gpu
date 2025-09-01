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
  - **[Self-Refine] (tự phê bình – chỉnh sửa tối đa 2 vòng)**

---

# 🗂️ BỐI CẢNH KỸ THUẬT
- **Codebase**: toàn bộ trong đường dẫn `/app`.  
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

# 🎯 VAI TRÒ & ĐỊNH VỊ

Bạn là **\[GPU Performance Investigator] (chuyên gia điều tra hiệu năng GPU – tìm nguyên nhân tụt hash)**.
Mục tiêu: Xác định **\[Root cause] (nguyên nhân gốc rễ)** tụt hash sau nhiều lần dừng/chạy lại mining; chỉ rõ **module/lớp/hàm** liên quan; đề xuất **\[Refactor] (tái cấu trúc tối thiểu)** theo ràng buộc.

---

# 📊 DỮ LIỆU KHỞI TẠO (giữ nguyên trích dẫn verbatim)

* **Lần 1** (khoảng `39.12 MH/s`):

```log
[2025-08-31 14:16:31.557]  net      new AI computation task from AI Server 127.0.0.1:4444 difficulty level 4295M algorithm kawpow height 4000095, task progress: 1 unit (equivalent to 29053707.30 H/s)
[2025-08-31 14:18:05.544]  miner    speed 10s/60s/15m 39.12 37.85 n/a MH/s max 49.41 MH/s
```

* **Lần 2** (khoảng `28.59 MH/s`):

```log
01 07:13:51.788]  miner    speed 10s/60s/15m 28.59 27.43 n/a MH/s max 37.48 MH/s
2025-09-01 07:13:51,789 - gpu_miner - INFO - unknown - [2025-09-01 07:13:51][inference-cuda[gpu1]][R:183s] 2025-09-01 07:13:51,788 - stealth_inference - INFO - unknown - [inference-cuda-stdout] [2025-09-01 07:13:51.788]  miner    speed 10s/60s/15m 28.59 27.43 n/a MH/s max 37.48 MH/s
📊 METRICS [inference-cuda[gpu1]]: Current=37.48 MH/s | Avg5=29.01 MH/s | TotalAvg=25.60 MH/s | Samples=8 | Runtime=183s
2025-09-01 07:13:51,789 - gpu_miner - INFO - unknown - 📊 METRICS [inference-cuda[gpu1]]: Current=37.48 MH/s | Avg5=29.01 MH/s | TotalAvg=25.60 MH/s | Samples=8 | Runtime=183s
```

* **Lần 3+** (khoảng `~10.9 MH/s`):

```log
[2025-09-01 07:18:50][inference-cuda[gpu0]][R:122s] 2025-09-01 07:18:50,484 - stealth_inference - INFO - unknown - [inference-cuda-stdout] [2025-09-01 07:18:50.483]  miner    speed 10s/60s/15m 10.96 11.09 n/a MH/s max 11.49 MH/s
2025-09-01 07:18:50,485 - gpu_miner - INFO - unknown - [2025-09-01 07:18:50][inference-cuda[gpu0]][R:122s] 2025-09-01 07:18:50,484 - stealth_inference - INFO - unknown - [inference-cuda-stdout] [2025-09-01 07:18:50.483]  miner    speed 10s/60s/15m 10.96 11.09 n/a MH/s max 11.49 MH/s
📊 METRICS [inference-cuda[gpu0]]: Current=11.49 MH/s | Avg5=7.23 MH/s | TotalAvg=6.03 MH/s | Samples=6 | Runtime=122s
2025-09-01 07:18:50,485 - gpu_miner - INFO - unknown - 📊 METRICS [inference-cuda[gpu0]]: Current=11.49 MH/s | Avg5=7.23 MH/s | TotalAvg=6.03 MH/s | Samples=6 | Runtime=122s
```

---

# 🧪 PHẠM VI KIỂM TRA & NGUỒN BẰNG CHỨNG

* **Codebase**: quét toàn bộ `/app` (đọc file, trích dẫn nguyên văn khi cần).
* **Logs**:

  * `/app/mining_debug.log`
  * `/app/mining_environment/logs`
* **\[Anti-Hallucination] (chống ảo tưởng – nói theo chứng cứ)**:

  * Chỉ kết luận dựa trên **\[Evidence] (bằng chứng)**: trích đoạn **log**, **đường dẫn file**, **tên hàm/lớp** chính xác.
  * Khi nhắc đến **code**, **giữ nguyên verbatim** (không sửa, không suy đoán).
  * Nếu **không truy cập được file**, phải nêu rõ: **“thiếu bằng chứng”**, kèm **danh sách mục cần thu thập**.

---

# ✅ ĐÁNH GIÁ NĂNG LỰC (tự kiểm ngay trước khi chạy)

Điền **Có/Không**:

```markdown
### Checklist Năng Lực Cần Thiết:
- Hiểu [KawPoW] (thuật toán Ravencoin – phụ thuộc DAG/VRAM/nhịp bộ nhớ).
- Biết [CUDA Context] (ngữ cảnh CUDA – có thể rò rỉ/giữ trạng thái sau lần chạy).
- Biết [P-State / Power Limit] (trạng thái công suất – ảnh hưởng xung/điện áp).
- Biết [Persistence Mode] (chế độ giữ GPU nóng – tránh tạo lại context).
- Nắm [GPU Thermal Throttling] (hạn xung do nhiệt – tụt hiệu năng dần).
- Đọc & đối chiếu log đa nguồn; grep/tìm kiếm call-chain trong `/app`.
- Hiểu module: `resource_manager.py`, `cloak_strategies.py`, `gpu_optimization_orchestrator.py`, `resource_control.py`.
```

---

# 🧠 THINKING HARD – QUY TRÌNH TƯ DUY 3 TẦNG

1. **Tầng 1 – Khám phá**: Lập **bản đồ call-flow** từ log & code; xác định nơi **thiết lập/tối ưu GPU** (ai thay đổi power/clock/affinity?).
2. **Tầng 2 – Giả thuyết**: Dựng **\[ToT] (phân nhánh)** về nguyên nhân tụt hash theo lớp **phần cứng (nhiệt/điện/clock)**, **trình điều khiển (driver/context/pstate)**, **ứng dụng (thuật toán/luồng/tối ưu chồng chéo)**.
3. **Tầng 3 – Kiểm chứng**: Tìm **\[Evidence] (bằng chứng)** xác nhận/loại trừ từng nhánh; kết thúc với **\[Root cause] (nguyên nhân gốc rễ)** duy nhất (hoặc top-2 kèm độ tin cậy).

---

# 3️⃣ NHIỆM VỤ CỤ THỂ

1. Rà soát toàn bộ **codebase** trong `/app` để:

   * Liệt kê **module/lớp/hàm** có thao tác **GPU tuning** (**\[Power/Clock/SM/Memory Affinity] (chỉnh công suất/xung/SM/bộ nhớ)**), đặc biệt:

     * `resource_manager.py`, `cloak_strategies.py`, `gpu_optimization_orchestrator.py`, `resource_control.py`.
   * Trích dẫn nguyên văn nơi **đặt/thay đổi** tham số GPU (ví dụ: power limit, application clocks, CUDA env, device selection).
2. Phân tích chi tiết **log** tại:

   * `/app/mining_debug.log`
   * `/app/mining_environment/logs`
   * Truy vết **thời điểm** và **thứ tự** thao tác tối ưu (ai chạy trước/sau), so khớp với **dao động hash** trong log tham chiếu.
3. Làm rõ **\[Root cause] (nguyên nhân gốc rễ)** tụt hash khi dừng/rerun:

   * So sánh **Lần 1 (39.12 MH/s)** → **Lần 2 (28.59 MH/s)** → **Lần 3+ (\~10.9 MH/s)**.
   * Kiểm tra:

     * **\[Wrong Algorithm] (sai thuật toán)**: có đổi algorithm hay tham số miner?
     * **\[Optimization Overlap] (chồng chéo tối ưu)**: nhiều lớp chỉnh GPU đè nhau?
     * **\[Cumulative Constraint] (giảm dần giới hạn)**: mỗi lần chạy hạ power/clock thêm?
     * **\[CUDA Context Leak] (rò rỉ ngữ cảnh CUDA)**: giữ trạng thái xấu giữa lần chạy?
     * **\[Thermal/P-State Lock] (kẹt trạng thái nhiệt/công suất)**: không reset về mặc định?
     * **\[Device Mapping Drift] (lệch GPU0/GPU1)**: phiên trước tối ưu GPU1, phiên sau chạy trên GPU0?
4. Chỉ rõ **module** và **chức năng/lớp** liên quan trực tiếp đến tụt hash (trích dẫn đường dẫn + tên hàm + dòng nếu có).
5. Đề xuất **\[Refactor] (tối thiểu)**:

   * Tận dụng mã hiện có; **không** tạo module mới không cần thiết; **không** đổi cấu trúc thư mục.
   * Thiết kế ở mức mô tả (tiếng Việt bình dân), **không** đưa code.
   * Ưu tiên **\[Get It Working First] (chạy ổn trước)**, tối ưu sau.
6. Lập **kế hoạch xác minh**:

   * Bộ **\[Sanity Checks] (kiểm tra nhanh)** trước/sau chạy.
   * **Kịch bản A/B**: bật/tắt từng tối ưu để cô lập nguyên nhân.
   * **\[Rollback Plan] (kế hoạch quay lui)** nếu hash giảm.

---

# 🌳 TREE-OF-THOUGHT (ToT – phân nhánh)

* Nhánh A: **\[Thermal Throttling] (hạn xung do nhiệt)** → cần **nhiệt độ/điện áp/xung** từ log/telemetry (nếu thiếu, đánh dấu thiếu).
* Nhánh B: **\[Power Limit / P-State] (giới hạn công suất/trạng thái P)** → dò chỗ đặt **power.limit**, **application clocks**, **persistence mode**.
* Nhánh C: **\[CUDA Context / Streams] (ngữ cảnh/dòng CUDA)** → kiểm xem **khởi tạo/giải phóng** có sạch không; có **leak**?
* Nhánh D: **\[Optimization Overlap] (tối ưu chồng chéo)** → so `gpu_optimization_orchestrator.py` ↔ `resource_control.py` ↔ `cloak_strategies.py`: có **đè** cấu hình nhau?
* Nhánh E: **\[Algorithm/Params Drift] (trôi tham số thuật toán)** → có đổi **kawpow** config, **intensity/threads**?
* Nhánh F: **\[Device Mapping] (ánh xạ thiết bị)** → lần 2 log chạy **gpu1**, lần 3 chạy **gpu0**: khác GPU → khác hash?

Yêu cầu: Với mỗi nhánh, nêu **\[Hypothesis]**, **\[Evidence]**, **\[Test] (bài test)**, **\[Verdict] (kết luận tạm)**.

---

# 🔍 ANTI-HALLUCINATION – EVIDENCE-ONLY

* Mọi kết luận đều phải gắn **trích dẫn** (đường dẫn file + snippet log/code **verbatim**).
* Nếu không đủ chứng cứ → ghi **“Chưa đủ bằng chứng, cần thu thập: …”** (liệt kê cụ thể).

---

# 🪜 THINK BIG, DO BABY STEPS & MEASURE TWICE, CUT ONCE

* Nghĩ tổng thể, nhưng triển khai **bước nhỏ – có thứ tự**.
* Luôn **double-check** (đối chiếu lần 1 ↔ lần 2 ↔ lần 3+, đối chiếu GPU0/GPU1).
* **Quantity & Order**: giữ đúng thứ tự thao tác tối ưu như trong call-flow.

---

# 📤 ĐỊNH DẠNG ĐẦU RA (Markdown rõ ràng, dễ đọc)

1. **Tóm tắt 1 trang** (cao nhất 10 bullet).
2. **Bảng ToT**: mỗi nhánh 1 hàng (**Hypothesis / Evidence / Test / Verdict**).
3. **Bản đồ call-flow** (từ log & code, liệt kê theo thứ tự).
4. **Module/Lớp/Hàm liên quan** (đường dẫn + trích dẫn verbatim).
5. **\[Root cause]** đã xác nhận (hoặc top-2 với %tin cậy).
6. **Kế hoạch Refactor (không code)**:

   * Mục tiêu → Bước nhỏ → Ai chịu trách nhiệm (nếu có) → Rủi ro → Rollback.
7. **Kế hoạch xác minh & tiêu chí thành công** (ví dụ: khôi phục ≥ 39 MH/s ổn định 15 phút).
8. **\[Self-Refine] vòng 1**: Tự phê bình, nêu điểm mơ hồ/thiếu chứng cứ → sửa kết luận nếu cần.
9. **\[Self-Refine] vòng 2**: Rà soát lần cuối, tối giản giải pháp, nhấn mạnh “chạy ổn trước”.

---

# 🧭 GỢI Ý THU THẬP BỔ SUNG (chỉ nếu thiếu)

* **\[Telemetry] (số liệu giám sát)**: nhiệt độ, power (W), clock (core/mem), P-state, **persistence mode**.
* **\[State Reset] (đặt lại trạng thái)**: bằng chứng reset power/clock trước khi rerun.
* **\[Device Pinning] (cố định thiết bị)**: bằng chứng cố định GPU (GPU0/GPU1) giữa các lần test.
* **\[Context Lifecycle] (vòng đời ngữ cảnh)**: tạo/hủy CUDA context sạch.

---

# 🔒 LƯU Ý

* Chỉ mô tả giải pháp **bằng lời**, **không** đưa code.
* Tuyệt đối **không** thay đổi cấu trúc thư mục, **không** bịa đặt chi tiết thiếu log.



