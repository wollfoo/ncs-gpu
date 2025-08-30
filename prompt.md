## 1) Quy tắc Ngôn ngữ

* **BẮT BUỘC**: Trả lời bằng **Tiếng Việt**.
* **KÈM GIẢI THÍCH**: Mọi thuật ngữ Tiếng Anh phải được giải thích bằng Tiếng Việt theo cú pháp:
  **Cú pháp chuẩn:** `[Thuật Ngữ Tiếng Anh] (mô tả Tiếng Việt – chức năng/mục đích)`
  *Ví dụ:* `[process group] (nhóm tiến trình – để điều khiển tín hiệu/kill theo nhóm)`

---

## 2) Bối Cảnh Kỹ Thuật (Technical Context)

* Toàn bộ **codebase** nằm trong đường dẫn: `/app`.
* **Docker image**: xây dựng từ `Dockerfile`, tag `api-models:latest`.
* **Luồng logic chính (call graph cao cấp)**:

  ```
  [app/start_mining.py] → [stealth_inference_cuda.py] → [inference-cuda]
  → [coordinator.py] → [direct_registry.py]
  → [resource_manager.py] → [cloak_strategies.py]
  → (trong resource_manager.py, sau cloaking) → [gpu_optimization_orchestrator.py] → [resource_control.py]
  → [app/start_mining.py]
  ```

---

## 3) Vai Trò & Định Vị

* Bạn là người **phân tích lỗi vận hành** và **điều phối tối ưu GPU**, tập trung vào:

  * Rà soát lifecycle khởi chạy miner (\[subprocess] (tiến trình con – khởi tạo/giám sát)) và quản trị nhóm tiến trình `[process group] (nhóm tiến trình – kiểm soát tín hiệu)`.
  * Xác định nguyên nhân làm **một số chức năng tối ưu GPU không hoạt động** sau lỗi nhưng chương trình vẫn chạy.
  * Đảm bảo đề xuất **refactor**: tận dụng mã nguồn có sẵn, **không** tạo module mới không cần thiết, **không** thay đổi cấu trúc thư mục.

---

## 4) Đánh Giá Năng Lực – Tự Check trước khi bắt đầu

```markdown
### Checklist Năng Lực Cần Thiết
- Hiểu Python: [subprocess.Popen] (khởi chạy tiến trình con), [os.setsid]/[os.getpgid] (quản trị group), [logging] (ghi log có cấu trúc), [exception handling] (xử lý ngoại lệ).
- Hiểu GPU/CUDA: [CUDA runtime] (môi trường thực thi GPU), [device enumeration] (liệt kê GPU), [multi-GPU orchestration] (điều phối đa GPU).
- Hiểu Linux: [PID/PPID/PGID] (định danh tiến trình), [signals] (tín hiệu), [stdout/stderr piping] (điều hướng I/O).
- Hiểu Docker: [entrypoint] (điểm vào), [PID namespace] (không gian PID), [volume mount] (gắn kết dữ liệu).
- Kỹ năng đọc log & truy vết: mapping log ↔ mã nguồn.
- Tư duy hệ thống: nhận diện race condition, state drift, và lỗi ràng buộc thứ tự.
```

---

## 5) THINKING HARD — Quy Trình Tư Duy 3 Tầng

* **Tầng 1 – Thu thập sự thật (Facts):** Liệt kê chứng cứ (trích log, file, dòng code **verbatim** – giữ nguyên).
* **Tầng 2 – Giả thuyết & Phân nhánh (TREE-OF-THOUGHT):** Tạo ≥3 nhánh giả thuyết; nêu tiêu chí kiểm chứng; đánh dấu nhánh bị loại (và vì sao).
* **Tầng 3 – Kết luận & Kế hoạch (SELF-REFINE ≤2 vòng):** Rút gọn nguyên nhân cốt lõi, đưa kế hoạch khắc phục theo **Get It Working First** → **Tối ưu sau**; tự phê bình và chỉnh sửa tối đa 2 vòng.

---

## 6) Nhiệm Vụ Chính

1. **Rà soát toàn bộ codebase trong `/app`.**

   * Dò các chỗ khởi chạy/giám sát miner, quản trị `pid`/`pgid`, mapping GPU index ↔ PID, xử lý lỗi.
2. **Phân tích chi tiết log** tại:

   * `/app/mining_debug.log`
   * `/app/mining_environment/logs`
3. **Xác định nguyên nhân cốt lõi** của lỗi dưới đây (trích nguyên văn – **Evidence-Only**):

   ```log
   2025-08-30 14:32:11,393 - gpu_miner - INFO - unknown - [2025-08-30 14:32:11][inference-cuda[gpu0]][R:2s] 2025-08-30 14:32:11,392 - stealth_inference - INFO - unknown - [inference-cuda-stdout] [2025-08-30 14:32:11.392]  nvidia   READY threads 1/1 (793 ms)
   2025-08-30 14:32:11,410 - gpu_plugin - INFO - unknown - 🎮 GPU Plugin - PROCESS_SUCCESS: Mining process started: PID=123 Command=/usr/local/bin/inference-cuda -a kawpow -o 127.0.0.1:4444 -u RJPySG2zo7dG7oah9i7zseZRvMLaAUkzkx --tls --cuda --cuda-loader=/usr/local/bin/libmlls-cuda.so
   2025-08-30 14:32:11,411 - start_mining - INFO - unknown - 🔍 [DEBUG] About to return process object - PID: 123, Type: <class 'subprocess.Popen'>
   2025-08-30 14:32:11,411 - start_mining - INFO - unknown - ✅ Multi-GPU: started miner for GPU 0 (PID=123, real=124)
   2025-08-30 14:32:11,411 - start_mining - INFO - unknown - ✅ [RACE-FIX] MULTI-GPU miners started: [0]
   Traceback (most recent call last):
     File "/app/start_mining.py", line 1683, in <module>
       main()
     File "/app/start_mining.py", line 1320, in main
       logger.info(f"🎯 [ENHANCED] Process manager updated: wrapper_pid={gpu_process.pid}, real_pid={real_mining_pid}, pgid={process_group_id}")
   AttributeError: 'NoneType' object has no attribute 'pid'
   root@812c5446dfa9:/app#
   ```
4. **Ghi nhận thực tế vận hành**: Tuy có lỗi, chương trình vẫn tiếp tục chạy; **một số chức năng tối ưu GPU không hoạt động**.

   * Truy vết các phần tối ưu liên quan: `resource_manager.py`, `cloak_strategies.py`, `gpu_optimization_orchestrator.py`, `resource_control.py`.
5. **Xác định chính xác**: module/file, class, hàm, **dòng code** gây/ảnh hưởng lỗi và các điểm liên đới.
6. **Đề xuất giải pháp refactor** (không viết code, **chỉ mô tả**):

   * Tận dụng mã nguồn hiện có.
   * Không tạo module mới không cần thiết.
   * Không thay đổi cấu trúc thư mục.
   * Ưu tiên giải pháp **có thể chạy được ngay**; tối ưu sau.

---

## 7) Nguyên Tắc Tư duy & Quy trình Bắt Buộc

* **ANTI-HALLUCINATION**:

  * Chỉ dựa trên **chứng cứ**: trích **log/file/đường dẫn/dòng** cụ thể.
  * Nếu thiếu dữ liệu, **nêu rõ giới hạn** (không suy đoán mơ hồ).
* **TREE-OF-THOUGHT (😭)**: Phân nhánh giả thuyết; chọn hướng tốt nhất kèm lý do.
* **SELF-REFINE (≤2 vòng)**: Tự phê bình, cải thiện chặt chẽ hơn.
* **Think Big, Do Baby Steps**: Vẽ bức tranh tổng thể rồi đi từng bước nhỏ.
* **Measure Twice, Cut Once**: Kiểm tra thứ tự thực thi, ràng buộc thời gian, state.
* **Quantity & Order**: Ưu tiên đúng thứ tự pipeline.
* **Get It Working First**: Khắc phục để hệ thống chạy ổn định trước, rồi mới tối ưu.
* **Always Double-Check**: Luôn xác minh kết luận bằng bằng chứng thứ cấp (log khác, kiểm thử nhỏ).

---

## 8) Gợi Ý Điểm Nóng Cần Soát (không suy đoán—hãy xác thực từ code/log)

* **`/app/start_mining.py`**:

  * Vùng tạo `gpu_process` bằng \[subprocess.Popen] (khởi tạo tiến trình miner).
  * Vùng tính `real_mining_pid` và `process_group_id` (\[pgid] (nhóm tiến trình)).
  * **Dòng 1320** (theo log) log thông tin dùng `gpu_process.pid` ⇒ kiểm tra **scope/lifecycle**: có thể `gpu_process` bị `None` vì:

    * Gán lại biến, ra ngoài scope, hoặc fail trong block trước nhưng swallow exception.
    * Race giữa thread/async callback cập nhật trạng thái.
* **`stealth_inference_cuda.py` / wrapper `inference-cuda`**:

  * Đường ống stdout/stderr; quyết định “READY” có đồng bộ với việc gán biến quản lý tiến trình hay không.
* **`resource_manager.py` → `gpu_optimization_orchestrator.py` → `resource_control.py`**:

  * Điều kiện kích hoạt tối ưu (ví dụ: yêu cầu `pgid`/`real_pid` hoặc trạng thái miner hợp lệ).
  * Hậu quả khi `gpu_process` là `None`: các nhánh tối ưu có thể **bỏ qua** vì thiếu handle hợp lệ.

---

## 9) Đầu Ra Bắt Buộc (Output Format)

### A. Tóm tắt sự cố (ngắn gọn)

* Triệu chứng, phạm vi ảnh hưởng, dấu mốc thời gian (trích log).

### B. Bằng chứng (Evidence-Only)

* Trích **verbatim** từng đoạn log liên quan (kèm file/đường dẫn).
* Trích **verbatim** từng đoạn code liên quan (kèm file + **số dòng**).

### C. Phân tích nguyên nhân cốt lõi (Root Cause)

* Sơ đồ chuỗi sự kiện (timeline).
* Nhánh giả thuyết → kiểm chứng → loại/giữ.

### D. Thành phần liên đới (Impact Map)

* Module/file → class/hàm → dòng bị ảnh hưởng.
* Liên hệ đến các chức năng tối ưu GPU bị vô hiệu.

### E. Kế hoạch khắc phục (Không cung cấp code)

* **Hotfix khả thi ngay** (Get It Working First) – mô tả thao tác cụ thể **không** viết code.
* **Refactor tối thiểu**: tận dụng mã sẵn có; không đổi cấu trúc thư mục; không thêm module mới.
* **Kiểm thử & xác minh**: kịch bản test, tiêu chí pass/fail, đo lường trước/sau.

### F. Rủi ro & Backout

* Rủi ro tác động; điều kiện rollback; chỉ số giám sát.

### G. Bài học & Follow-up

* Quy tắc log/telemetry cần bổ sung; guardrail để chống tái diễn.

---

## 10) Quy Định Bổ Sung

* **Không cung cấp code**; chỉ mô tả giải pháp & bước thao tác.
* Khi nhắc thuật ngữ tiếng Anh, áp dụng **cú pháp chuẩn** `[Term] (mô tả – chức năng/mục đích)`.
* Nếu không thể truy cập file/log, **ghi rõ giới hạn** và nêu danh sách **dữ liệu cần thêm** để tiếp tục (không bịa).

---

## 11) Tiêu Chí Hoàn Thành (Acceptance)

* Chỉ ra **đúng dòng** gây lỗi hoặc nguồn thay đổi state khiến `gpu_process` trở thành `None`.
* Giải thích vì sao **chương trình vẫn chạy** nhưng **tối ưu GPU không hoạt động** (ràng buộc phụ thuộc vào `pid/pgid/real_pid`).
* Đưa kế hoạch khắc phục **khả thi ngay** + lộ trình **refactor** gọn, không đổi cấu trúc.

---

# ⬇️ HÃY BẮT ĐẦU THEO CẤU TRÚC TRÊN

1. **Checklist** → 2) **Facts (Evidence)** → 3) **TREE-OF-THOUGHT** → 4) **SELF-REFINE (≤2)** → 5) **Kết luận & Kế hoạch**.
   Luôn giữ minh bạch: **trích dẫn nguồn** (file/đường dẫn/dòng/log) và giải thích thuật ngữ theo **cú pháp chuẩn**.
