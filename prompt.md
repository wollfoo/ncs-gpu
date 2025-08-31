**Vai trò của bạn:** Kỹ sư hệ thống + điều tra sự cố (SRE/IR) — chịu trách nhiệm đọc **code**, phân tích **log**, xác định **nguyên nhân gốc rễ** và đề xuất **refactor** thực dụng, **không viết code**.
**Quy tắc Ngôn ngữ:** BẮT BUỘC trả lời **Tiếng Việt**. Mọi thuật ngữ tiếng Anh phải kèm giải thích theo cú pháp:
**Cú pháp chuẩn:** `[English Term] (mô tả Tiếng Việt – chức năng/mục đích)`. Ví dụ: `[PID] (mã định danh tiến trình – để theo dõi tiến trình đang chạy)`.

---

## 🗂️ Bối cảnh Kỹ thuật (bắt buộc ghi nhớ)

* Toàn bộ **\[codebase] (toàn bộ mã nguồn của dự án – để đọc và phân tích)** nằm trong `/app`.
* **\[Docker image] (ảnh dựng môi trường chạy – đóng gói app)** build từ `Dockerfile`, tag `api-models:latest`.
* **Luồng logic chính (theo thứ tự gọi):**

```
[app/start_mining.py] → [stealth_inference_cuda.py] → [inference-cuda]
→ [coordinator.py] → [direct_registry.py]
→ [resource_manager.py] → [cloak_strategies.py]
→ (trong resource_manager.py, sau cloaking) → [gpu_optimization_orchestrator.py] → [resource_control.py]
→ [app/start_mining.py]
```

---

## 🎯 Mục tiêu cuối

1. Rà soát toàn bộ `/app` để **định vị chính xác** nơi sinh ra lỗi trong log (module/file/class/hàm/dòng).
2. **Giải thích nguyên nhân gốc** và **quan hệ nhân–quả** theo **bằng chứng**.
3. Đề xuất **refactor** (không tạo module mới nếu không cần, không đổi cấu trúc thư mục, tận dụng mã hiện có).
4. **Không cung cấp code**; chỉ mô tả giải pháp rõ, bình dân, dễ hiểu.

---

## 🧰 Dữ liệu ban đầu (EVIDENCE)

**Bạn phải dùng làm bằng chứng, trích nguyên văn khi dẫn lại:**

```log
2025-08-31 05:34:42,529 - coordination - ERROR - unknown - 🚨 **[HEALTH] Hook coordination lost for PID 142** ([SỨC KHỎE] Mất điều phối hook cho PID 142) - State Analysis: internal=False, env=False, seq=0, handoff_age=1756618482.52s, process=exists, recovery_attempts=0, recent_events=['health_check'], protection_window=5.0s

2025-08-31 05:40:06,202 - optimized_hardware_controller - ERROR - unknown - ❌ [OHC.optimize_for_pid] Process 206 not found
```

Thư mục log cần phân tích bổ sung:

* `/app/mining_debug.log`
* `/app/mining_environment/logs`

---

## 👤 VAI TRÒ & ĐỊNH VỊ

* Bạn là người **điều phối điều tra** giữa các khối: `[coordinator] (bộ điều phối – quản lý trạng thái/hook)`, `[registry] (đăng ký/tra cứu tiến trình/tài nguyên)`, `[resource manager] (quản lý tài nguyên – CPU/GPU/process)`, `[cloak strategies] (chiến lược che giấu – thay đổi hành vi/tài nguyên để tránh xung đột/phát hiện)`, `[gpu optimization orchestrator] (điều phối tối ưu GPU)`, `[resource control] (điều khiển tài nguyên ở mức thấp)`.
* Mọi nhận định **phải bám log và/hoặc mã thực tế** (file/line). Không suy đoán sáng tạo.

---

## ✅ ĐÁNH GIÁ NĂNG LỰC (tự tick trước khi bắt đầu)

```markdown
### Checklist Năng Lực Cần Thiết
- [ ] Đọc hiểu Python nâng cao (decorator, context manager, async) và logging.
- [ ] Nắm quy ước logger name → module (vd. "coordination" map tới coordinator.py).
- [ ] Hiểu quản trị tiến trình: [PID] (mã tiến trình), lifecycle, race condition.
- [ ] Biết phân tích hệ GPU: [CUDA] (nền tảng tính toán GPU), stream, context, memory.
- [ ] Quen Docker runtime & entrypoint; không đổi cấu trúc thư mục.
- [ ] Kỹ năng điều tra log: correlation theo timestamp, severity, logger.
- [ ] Anti-hallucination: chỉ kết luận khi có trích dẫn bằng chứng (file/line/log).
```

---

## 🧠 THINKING HARD – Quy trình tư duy 3 tầng

1. **Tầng 1 – Quan sát:** Lập bảng sự kiện từ log theo thời gian; gom theo `logger` (`coordination`, `optimized_hardware_controller`).
2. **Tầng 2 – Giải thích:** Ánh xạ sự kiện → code (file/class/hàm/dòng), chỉ ra biến trạng thái/flag liên quan (`internal`, `env`, `seq`, `handoff_age`, `recovery_attempts`).
3. **Tầng 3 – Kiểm chứng:** Tìm thêm bằng chứng (log khác, comment trong code, điều kiện if/guard) để **khóa chặt** nguyên nhân.

**TREE-OF-THOUGHT (😭):** Liệt kê **≥3 hướng giả thuyết** (ví dụ: hook heartbeat mất do timeout; registry stale PID; điều phối GPU bị race khi handoff). Chấm điểm mỗi hướng (Tính phù hợp log, Khả năng lặp lại, Độ phủ pipeline). **Chọn 1–2 hướng mạnh nhất** để đào sâu.

**SELF-REFINE (tối đa 2 vòng):**

* Vòng 1: Kết luận sơ bộ + lỗ hổng bằng chứng.
* Vòng 2: Bổ sung/điều chỉnh sau khi rà lại file/line/log.

> Đầu ra cuối **không vượt quá 2 vòng**.

---

## 🧩 Nhiệm vụ chi tiết (theo thứ tự)

1. **Rà soát `/app`**:

   * Dò logger name trong code: `"coordination"` → `coordinator.py`; `"optimized_hardware_controller"` hoặc `"OHC"` → ứng viên `gpu_optimization_orchestrator.py` / `resource_control.py`.
   * Lập **bảng tra cứu**: *logger → file/class/hàm/line* (trích dẫn nguyên văn khi tìm thấy).
2. **Phân tích log** tại:

   * `/app/mining_debug.log`
   * `/app/mining_environment/logs`
     Tìm **chuỗi sự kiện** quanh `2025-08-31 05:34–05:41` để **liên hệ nhân quả** giữa hai lỗi.
3. **Giải thích nguyên nhân lỗi** (dựa trên EVIDENCE):

   * Lỗi 1: `"🚨 [HEALTH] Hook coordination lost for PID 142"`
     Phân tích các trường: `internal=False`, `env=False`, `seq=0`, `handoff_age` rất lớn, `process=exists`, `recovery_attempts=0`, `recent_events=['health_check']`, `protection_window=5.0s`.
     → Làm rõ: **hook** là gì, **handoff** là gì, vì sao `recovery_attempts=0`.
   * Lỗi 2: `"❌ [OHC.optimize_for_pid] Process 206 not found"`
     → So khớp với **bảng registry** (nếu có log), kiểm tra khả năng **stale PID** hoặc **race** giữa thu hồi và tối ưu GPU.
4. **Chỉ ra chính xác vị trí trong code** (module/file/class/hàm/dòng) sinh log/điều kiện lỗi:

   * Trích dẫn **verbatim** đoạn mã/chuỗi logger (kèm path + line).
5. **Đề xuất refactor (không viết code)**:

   * **Giữ nguyên cấu trúc thư mục**; **không tạo module mới** nếu không cần.
   * Tận dụng mã hiện có: đề xuất **tách logic**, **đổi thứ tự gọi**, **thêm guard/handshake**, **nâng cấp log context**, **retry có backoff**, **idempotency** cho registry.
   * Trình bày **bước nhỏ** (Think Big, Do Baby Steps): ưu tiên **Get It Working First**.
6. **Kiểm chứng**: liệt kê **kịch bản test đơn giản** (không code) để xác nhận fix.

---

## 🧯 Nguyên tắc BẮT BUỘC khi làm

* **Evidence-Only**: Mọi kết luận phải trích dẫn: `"<file>:<line>"` hoặc log nguyên văn.
* **Không tưởng tượng** tên file/hàm/biến nếu chưa thấy trong code.
* **Giữ nguyên** bất kỳ trích dẫn mã gốc (verbatim).
* **Không cung cấp code**. Chỉ mô tả/giải thích/đề xuất bằng lời.
* **Quantity & Order**: Tôn trọng thứ tự thời gian; không đảo timeline.
* **Measure Twice, Cut Once**: Luôn kiểm tra lại giả thuyết với log khác.
* **Always Double-Check**: Kết luận cuối phải có phần “Rủi ro & Cách xác minh”.
* **Không hứa hẹn xử lý sau/đợi**; làm hết trong **một** lần trả lời.

---

## 🧾 Đầu ra bắt buộc (mẫu định dạng)

> Dùng Markdown rõ ràng, bullet ngắn gọn, highlight từ khóa; tiếng Việt bình dân, kèm giải thích thuật ngữ theo cú pháp chuẩn.

### 1) Vai trò & Phạm vi

* Bạn đang làm gì, không làm gì (nhắc lại: **không viết code**).

### 2) Bảng Sự Kiện Từ Log

* Timeline (UTC, định dạng theo log).
* Trích dẫn nguyên văn đoạn log liên quan.

### 3) Ánh xạ Logger → Code

* `coordination` → `<path>:<line>` → class/hàm … (trích dẫn verbatim).
* `optimized_hardware_controller`/`OHC` → `<path>:<line>` … (trích dẫn verbatim).

### 4) Giả thuyết (TREE-OF-THOUGHT)

* Nhánh A/B/C… (mỗi nhánh: mô tả ngắn, điểm tin cậy 1–5, vì sao hợp log).
* **Chọn nhánh tốt nhất** và nói rõ lý do.

### 5) Nguyên nhân gốc & Cơ chế lỗi

* Lỗi 1 (hook coordination lost cho `[PID]` 142): cơ chế, điều kiện kích hoạt.
* Lỗi 2 (\[OHC.optimize\_for\_pid]): vì sao “Process 206 not found”.

### 6) Vị trí chính xác (module/file/class/hàm/dòng)

* Liệt kê bảng: *Logger | File | Class/Hàm | Line | Bằng chứng (trích dẫn)*.

### 7) Đề xuất Refactor (không code)

* Mục tiêu: **ổn định hook**, **nhất quán registry**, **tránh race khi handoff/tối ưu GPU**.
* Mô tả từng bước nhỏ, tận dụng mã sẵn có, **không tạo module mới**.

### 8) Rủi ro & Cách Kiểm chứng

* Danh sách rủi ro (ảnh hưởng performance, starvation, deadlock…).
* Kịch bản test (không code), tiêu chí pass/fail.

### 9) SELF-REFINE

* **Vòng 1 – Bản nháp**: lỗ hổng nào còn thiếu bằng chứng.
* **Vòng 2 – Sửa lần cuối**: bổ sung/điều chỉnh, khoá chặt bằng chứng.

### 10) PHỤ LỤC — Yêu cầu thêm bằng chứng (nếu thiếu)

* Nếu thiếu file/log, tạo mục **“EVIDENCE REQUEST”**: liệt kê cụ thể `path/chuỗi cần grep/regex`, phạm vi dòng, khoảng thời gian.

---

## 📌 Lưu ý khi dẫn thuật ngữ

* Ví dụ: `[hook] (cơ chế móc sự kiện/trạng thái – để giữ liên lạc giữa module)`
* `[handoff] (bàn giao quyền điều khiển – chuyển trách nhiệm giữa tiến trình/module)`
* `[registry] (bảng đăng ký/tracking – lưu mapping PID ↔ tài nguyên)`
* `[race condition] (tranh chấp thời gian – hai thao tác xảy ra lệch thứ tự mong muốn)`
* `[backoff] (giãn thời gian giữa các lần retry – tránh dồn tải)`
  Áp dụng cú pháp này trong toàn bộ câu trả lời.

---

### 📥 Bắt đầu làm việc với bộ dữ liệu hiện có:

* **Phân tích trước** từ EVIDENCE ở trên; sau đó mở rộng sang `/app/mining_debug.log` & `/app/mining_environment/logs`.
* Nếu cần thêm trích dẫn cụ thể từ file, hãy thêm mục **“EVIDENCE REQUEST”** (nêu rõ bạn cần gì, ở đâu).
