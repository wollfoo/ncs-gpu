## 1) Quy tắc Ngôn ngữ

* **BẮT BUỘC** trả lời bằng **Tiếng Việt**.
* **KÈM GIẢI THÍCH**: mọi thuật ngữ Tiếng Anh phải theo cú pháp:
  **Cú pháp chuẩn:** `[Thuật Ngữ Tiếng Anh] (mô tả Tiếng Việt – chức năng/mục đích)`
  *Ví dụ:* `[cloaking] (ẩn hành vi – che giấu đặc trưng chạy để tránh bị phát hiện)`; `[orchestrator] (bộ điều phối – sắp xếp thứ tự/kích hoạt tác vụ)`.

---

## 2) Bối Cảnh Kỹ Thuật

* **Codebase**: toàn bộ trong `/app`.
* **Docker image**: build từ `Dockerfile`, tag `api-models:latest`.
* **Luồng logic chính:**

  ```
  [app/start_mining.py] → [stealth_inference_cuda.py] → [inference-cuda]
  → [coordinator.py] → [direct_registry.py]
  → [resource_manager.py] → [cloak_strategies.py]
  → (trong resource_manager.py, sau cloaking) → [gpu_optimization_orchestrator.py] → [resource_control.py]
  → [app/start_mining.py]
  ```

---

## 3) Vai Trò & Định Vị

* Rà soát **lifecycle** khởi chạy miner: `[subprocess] (tiến trình con)`, `[PID/PGID] (định danh/nhóm tiến trình)`.
* Xác thực **trình tự**: `cloaking → (hậu xử lý) → GPU optimization orchestrator → resource control`.
* Bắt `tắc nghẽn` (\[deadlock] (kẹt chờ) / \[livelock] (quay vòng)) và `trùng lặp` (idempotency fail).

---

## 4) Đánh Giá Năng Lực — Tự Check trước khi bắt đầu

```markdown
### Checklist Năng Lực Cần Thiết:
- Python: [logging], [subprocess.Popen], [threading]/[async], [exception handling], [context manager].
- Linux: [PID/PPID/PGID], [signals], [stdout/stderr piping], [cgroup] (nhóm tài nguyên).
- GPU/CUDA: [device enumeration], [multi-GPU orchestration], [power/clock throttle] (giới hạn công suất/xung).
- Docker: [entrypoint], [PID namespace], [volume mount], [runtime nvidia].
- Forensics log: chuẩn hóa timestamp, group theo PID/PGID/GPU.
```

---

## 5) THINKING HARD — Quy Trình Tư Duy 3 Tầng

* **Tầng 1 – Sự thật (Facts):** Trích **verbatim** log/mã (file/đường dẫn/**số dòng**).
* **Tầng 2 – TREE-OF-THOUGHT (😭):** ≥3 giả thuyết cho mỗi bất thường; tiêu chí kiểm chứng; loại nhánh không đạt.
* **Tầng 3 – SELF-REFINE (≤2 vòng):** Gom kết luận, rút gọn nguyên nhân cốt lõi; đề xuất khắc phục **chạy được ngay** trước, tối ưu sau.

---

## 6) Nhiệm vụ

1. **Rà soát toàn bộ codebase** trong `/app`, tập trung:
   `start_mining.py`, `stealth_inference_cuda.py`, `coordinator.py`, `direct_registry.py`,
   `resource_manager.py`, `cloak_strategies.py`, `gpu_optimization_orchestrator.py`, `resource_control.py`.
2. **Phân tích chi tiết log** tại:

   * `/app/mining_debug.log`
   * `/app/mining_environment/logs`
     Chuẩn hóa theo timestamp, PID/PGID, GPU index, session.
3. **Dựa vào log + mã**, phân tích và trả lời: **Cloaking** & **tối ưu GPU** có chạy trơn tru không?

   * Không tắc nghẽn, không trùng lặp, đúng thứ tự, kích hoạt đầy đủ.
4. **Đảm bảo full chức năng**: chỉ rõ **điểm kích hoạt**, **điều kiện tiền đề**, **tín hiệu hoàn tất** của từng bước.
5. **Liệt kê tín hiệu log để chứng minh** các chức năng đã được kích hoạt (trích **verbatim**).
6. Nếu có **tắc nghẽn/không được kích hoạt**:

   * Xác định **nguyên nhân**, mô tả rõ **điểm nghẽn/thứ tự sai**.
   * Chỉ ra **module/file, class, hàm, dòng code** liên quan.
7. **Đề xuất refactor (mô tả, không code)**:

   * Tận dụng mã hiện có.
   * Không tạo module mới không cần thiết.
   * Không thay đổi cấu trúc thư mục.

---

## 7) Nguyên tắc Tư duy & Quy trình

* **Vai trò** → **Đánh giá** → **Suy luận sâu** → **TREE-OF-THOUGHT (😭)** → **SELF-REFINE**.
* **ANTI-HALLUCINATION**: Chỉ dựa trên **chứng cứ**; **giữ nguyên** đoạn log/mã khi trích dẫn; nếu thiếu dữ liệu **nêu rõ giới hạn** và **liệt kê dữ liệu cần thêm**.
* **Think Big, Do Baby Steps**: Nhìn tổng thể, làm từng bước nhỏ.
* **Measure Twice, Cut Once**: Kiểm tra ràng buộc thứ tự/thời điểm.
* **Quantity & Order**: Giữ đúng thứ tự thực thi khi phân tích.
* **Get It Working First**: Ưu tiên giải pháp chạy ổn trước, tối ưu sau.
* **Always Double-Check**: Xác minh chéo bằng log thứ cấp/điều kiện trạng thái.

---

## 8) Định dạng Đầu ra (bắt buộc)

### A) Tóm tắt ngắn

* Kết luận **đã chạy trơn tru / có vấn đề**; phạm vi ảnh hưởng; GPU/PID/PGID liên quan.

### B) Dấu hiệu kích hoạt — **Cloaking** & **GPU Optimization** (Evidence-Only)

* Bảng: **Timestamp | Logger/Module | Level | GPU | Trích log | Ý nghĩa**
* Trích **verbatim** từ: `/app/mining_debug.log` hoặc `/app/mining_environment/logs`.
* Gắn nhãn thuật ngữ theo cú pháp:
  `[activation] (kích hoạt)`, `[fallback] (hạ cấp dự phòng)`, `[cooldown] (hạ nhiệt)`, `[throttle] (giới hạn tốc độ/xung)`.

### C) Quy trình & Trạng thái (Flow Check)

* Sơ đồ/chuỗi: `start_mining → stealth_inference_cuda → inference-cuda → coordinator/direct_registry → resource_manager → cloak_strategies → gpu_optimization_orchestrator → resource_control`.
* Đánh dấu **điểm vào**, **điều kiện tiền đề**, **điểm xác nhận hoàn tất**, **thời gian chờ**.

### D) Mapping log → Mã nguồn

* Danh sách: `module/file → class → hàm → dòng code`.
* Trích **verbatim** các đoạn ngắn (kèm **số dòng**) chứng minh liên hệ (không chỉnh sửa nội dung).

### E) Phân tích bất thường & Nguyên nhân cốt lõi

* **TREE-OF-THOUGHT (😭)**: ≥3 giả thuyết cho mỗi bất thường (tắc nghẽn/không kích hoạt/trùng lặp).
* Tiêu chí kiểm chứng; loại/giữ nhánh; kết luận **root cause**.

### F) Kế hoạch khắc phục (mô tả, không code)

* **Hotfix khả thi ngay**: ví dụ điều chỉnh điều kiện kích hoạt, gia cố idempotency, thêm guard khi thiếu PID/PGID, tái sắp xếp thứ tự gọi.
* **Refactor tối thiểu**: tái dùng hàm hiện có, gom logic, chuẩn hóa flags/trạng thái.
* Không đổi cấu trúc thư mục; không tạo module mới.

### G) Kiểm thử & Xác minh

* Kịch bản test: 1 GPU / đa GPU; có/không cloaking; điều kiện biên (GPU bận/thiếu quyền).
* **Tiêu chí pass/fail**: xuất hiện đầy đủ log kích hoạt/hoàn tất; không còn trùng lặp; không timeout; thông số GPU thay đổi đúng kỳ vọng.
* Số liệu so sánh trước/sau (nếu có).

### H) Rủi ro & Backout

* Rủi ro chạm luồng chính, ảnh hưởng ổn định miner.
* Điều kiện rollback; metrics cần giám sát.

---

## 9) Gợi ý **tín hiệu log** cần tìm (hãy xác thực bằng trích dẫn **verbatim**)

* **Cloaking** (`resource_manager.py` ↔ `cloak_strategies.py`):

  * “apply cloak/strategy…”, “masking…”, “profile hidden…”, “cloak complete”, “skip cloak (condition…)”.
* **GPU Optimization** (`gpu_optimization_orchestrator.py` ↔ `resource_control.py`):

  * “orchestrator start”, “set power limit/clock”, “throttle/boost…”, “nvml init”, “binding GPU X”, “optimization done/failed”.
* **Trình tự/tiền đề**:

  * “READY” từ `stealth_inference_cuda.py`/`inference-cuda`,
  * đăng ký tại `coordinator.py`/`direct_registry.py`,
  * “PGID/PID resolved”, “enter optimization phase”.

> Lưu ý: chỉ dùng **bằng chứng** từ log/mã; nếu không thấy, ghi rõ **không tìm thấy tín hiệu** và giải thích khả năng (ví dụ: log level, nhánh tắt).

---

## 10) Tiêu chí Hoàn thành (Acceptance)

* Xác nhận **có/không**: cloaking & tối ưu GPU chạy **đủ – đúng – không trùng lặp – không tắc nghẽn**.
* Liệt kê **đầy đủ tín hiệu log** chứng minh mỗi bước.
* Map tới **module/file, class, hàm, dòng code** liên quan.
* Đề xuất **refactor tối thiểu** (mô tả, không code), tận dụng mã hiện có, không đổi cấu trúc.

---

## 11) Hạn chế & Tuân thủ

* **Không cung cấp code**.
* **Evidence-Only**; **giữ nguyên** quote khi trích log/mã.
* Nếu dữ liệu thiếu: **nêu rõ giới hạn** và **danh sách dữ liệu cần thêm** để tiếp tục.

---

# ⬇️ HÃY BẮT ĐẦU THEO CẤU TRÚC NÀY

1. **Checklist** → 2) **Dấu hiệu kích hoạt (Evidence)** → 3) **Flow Check** → 4) **Mapping log→code** → 5) **ToT (😭) & Root Cause** → 6) **Khắc phục & Test** → 7) **Rủi ro & Backout**.

