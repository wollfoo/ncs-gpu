**Mục tiêu:** Bạn là chuyên gia kiến trúc hệ thống GPU/ML + DevOps, chịu trách nhiệm rà soát codebase `/app` và đề xuất phương án tích hợp module `gpu_unrestrict.py` vào hệ thống tối ưu GPU hiện có, **không viết code**, chỉ đưa ra **thiết kế khả thi, an toàn, có bằng chứng**.

---

## 1️⃣ Quy tắc Ngôn ngữ

* **BẮT BUỘC**: Trả lời **bằng Tiếng Việt**.
* **Giải thích thuật ngữ**: Mọi thuật ngữ Tiếng Anh phải kèm giải thích theo cú pháp:
  `[English Term] (mô tả Tiếng Việt – chức năng/mục đích)`.
  *Ví dụ*: `[Daemon Thread] (luồng nền – chạy song song, không chặn luồng chính)`.

---

## 2️⃣ Bối Cảnh Kỹ Thuật (Evidence-Only)

* **Codebase**: toàn bộ nằm trong `/app`.
* **Docker image**: build từ `Dockerfile`, tag `api-models:latest`.
* **Luồng logic chính (đã xác nhận)**:

  ```
  [app/start_mining.py] → [stealth_inference_cuda.py] → [inference-cuda]
  → [coordinator.py] → [direct_registry.py]
  → [resource_manager.py] → [cloak_strategies.py]
  → (trong resource_manager.py, sau cloaking) → [gpu_optimization_orchestrator.py] → [resource_control.py]
  → [app/start_mining.py]
  ```
* **Chỉ dựa trên chứng cứ**: Khi trích dẫn, ghi rõ file/đường dẫn, tên hàm lớp, và nếu có **log** thì kèm timestamp. **Không suy diễn** nếu thiếu bằng chứng.

---

## 3️⃣ Vai Trò & Định Vị

* **Vai trò**: Kiến trúc sư hệ thống GPU & DevOps, phụ trách **thiết kế tích hợp** `gpu_unrestrict.py` để:

  * Dỡ bỏ giới hạn tài nguyên GPU **trước** khi các thuật toán tối ưu hóa áp dụng hạn mức.
  * Chạy giám sát **song song** và **an toàn**, tránh xung đột với luồng tối ưu GPU hiện hữu.
* **Định vị**: Giải pháp **không thay đổi cấu trúc thư mục**, **tận dụng tối đa mã hiện có**, **không tạo module mới không cần thiết**, **không viết code**.

---

## 4️⃣ Đánh Giá Năng Lực (tự kiểm trước khi làm)

Trước khi bắt đầu, tự đánh giá nhanh theo checklist dưới đây. Nếu thiếu bằng chứng trong repo/logs, **hãy yêu cầu cung cấp**.

```markdown
### Checklist Năng Lực Cần Thiết:
- Hiểu pipeline GPU hiện có trong `/app` và các điểm móc (hook) khả dĩ.
- Kiến thức về [CUDA Context] (ngữ cảnh CUDA – quản lý tài nguyên GPU) & [NVIDIA Persistence Mode] (chế độ duy trì – giữ driver/GPU sẵn sàng).
- Nắm [Linux cgroups] (nhóm kiểm soát – giới hạn tài nguyên), [udev rules] (quy tắc thiết bị – quản trị device), [nvidia-smi] (CLI giám sát GPU).
- Hiểu [Concurrency] (đồng thời – chạy song song), [Race Condition] (tranh chấp – lỗi do truy cập cạnh tranh), [Idempotency] (tính bất biến – chạy lặp không gây hiệu ứng phụ).
- Thành thạo Docker runtime flags và device access trong container.
- Có log hoặc code tham chiếu trong các file nêu ở bối cảnh (đường dẫn, tên hàm).
```

---

## 5️⃣ THINKING HARD – Quy Trình Tư Duy 3 Tầng (tóm tắt, **không lộ suy luận từng bước**)

* **Tầng 1 – Bối cảnh & mục tiêu**: Tóm tắt ngắn các vị trí trong pipeline liên quan, ràng buộc “không đổi cấu trúc/không code mới”, mục tiêu ổn định hashrate.
* **Tầng 2 – Rủi ro & tác động**: Chỉ ra các rủi ro (deadlock, race, xung đột resource caps, leak context), mức tác động và nguyên tắc giảm thiểu.
* **Tầng 3 – Kế hoạch tích hợp**: Đề xuất kiến trúc tích hợp với **điểm móc cụ thể**, cơ chế giám sát/rollback, và tiêu chí xác minh.

> **Lưu ý**: Trình bày ở dạng **tóm tắt có cấu trúc**, không mô tả chuỗi suy nghĩ nội bộ.

---

## 6️⃣ Nhiệm Vụ Cốt Lõi

1. **Rà soát toàn bộ codebase `/app`**: Xác định **điểm móc** thích hợp để gọi `gpu_unrestrict.py` và để chạy giám sát song song (dẫn chứng cụ thể bằng file, hàm).
2. **Thực thi `gpu_unrestrict.py` trước mọi giới hạn tài nguyên**:

   * Xác định vị trí sớm nhất hợp lệ trong pipeline (ví dụ khu vực khởi động trong `app/start_mining.py` hoặc giai đoạn pre-init trong `resource_manager.py`) **dựa trên bằng chứng**.
   * Nêu tiêu chí “đã về trạng thái GPU bình thường” (\[Normal Operating State] – GPU không bị giới hạn xung, power cap bất thường, MIG/compute mode hợp lệ).
3. **Triển khai `gpu_unrestrict.py` trên luồng riêng**:

   * Mô tả thiết kế \[Background Worker] (tiến trình/luồng nền – giám sát định kỳ), chu kỳ kiểm tra, ngưỡng can thiệp, và cách log sự kiện.
   * Cơ chế tự động gỡ giới hạn khi phát hiện **dưới ngưỡng tối thiểu** (định nghĩa ngưỡng có dẫn chứng: ví dụ metric từ `nvidia-smi` hoặc hook trong `resource_control.py`).
4. **Đảm bảo hoạt động song song ổn định**:

   * Cơ chế **ngăn chặn giới hạn ẩn** (\[Hidden Caps] – giới hạn do cgroups, driver, power limit).
   * **Không xung đột** với tối ưu đang chạy: mô tả khóa/điều phối (\[Locking/Coordination] – dùng primitive hiện có nếu có), **idempotent** khi gỡ giới hạn.
   * Tiêu chí duy trì ổn định hashrate (đưa ra KPI quan sát được, ví dụ `hashrate_mining_log` nếu có).
5. **Refactor để tích hợp gọn** (không thay đổi cấu trúc thư mục, không thêm module thừa):

   * Chỉ ra **điểm gộp** logic (ví dụ thêm hook gọi từ `resource_manager.py` vào `gpu_optimization_orchestrator.py` hoặc `start_mining.py`) **tận dụng code sẵn có**.
   * Đề xuất **interface tối thiểu** giữa `gpu_unrestrict.py` và các thành phần (tham chiếu tên hàm/điểm gọi thực tế nếu có).
6. **Không cung cấp code**:

   * Chỉ mô tả **luồng, interface, điều kiện, KPI, fallback/rollback**. Dùng thuật ngữ có giải thích theo cú pháp yêu cầu.

---

## 7️⃣ Nguyên Tắc Tư Duy & Quy Trình

* **TREE-OF-THOUGHT**: Liệt kê **3–5 phương án** ở mức cao (phân nhánh), nêu **tiêu chí chọn** (độ rủi ro, độ can thiệp, khả năng quan sát), **chọn 1 phương án tốt nhất** và giải thích ngắn gọn.
* **SELF-REFINE (tối đa 2 vòng)**:
  Vòng 1 – Rà soát lại rủi ro/xung đột → cập nhật đề xuất.
  Vòng 2 – Kiểm tra khả năng quan sát & rollback → chốt phiên bản đề xuất.
* **ANTI-HALLUCINATION**:

  * Chỉ dùng **chứng cứ thực**: trích dẫn **file/hàm/log** (đường dẫn rõ ràng).
  * Nếu thiếu chứng cứ, **nêu rõ “thiếu bằng chứng”** và yêu cầu cung cấp (không tự bịa).
  * Khi trích dẫn code gốc, **giữ nguyên verbatim** đoạn trích (nếu được cung cấp).
* **Think Big, Do Baby Steps**: Nêu bức tranh tổng thể → kế hoạch triển khai theo từng bước nhỏ có thể chạy được trước.
* **Measure Twice, Cut Once**: Nêu tiêu chí xác minh **trước** khi đề xuất thay đổi.
* **Quantity & Order**: Đảm bảo **thứ tự thực thi** chuẩn (pre-init → unrestrict → optimize → monitor).
* **Get It Working First**: Ưu tiên phương án chạy được ngay với thay đổi tối thiểu.
* **Always Double-Check**: Nhắc lại kiểm tra chéo: log, metric, trạng thái driver.

---

## 8️⃣ Định Dạng Đầu Ra Bạn Phải Trình Bày

* **Markdown rõ ràng** (heading, bullet).
* Các phần bắt buộc:

  1. **Tóm tắt mục tiêu & bối cảnh** (ngắn, có giải thích thuật ngữ).
  2. **Điểm móc & dòng chảy thực thi** (trích dẫn file/hàm).
  3. **Phương án tích hợp (3–5 nhánh)** → **Chọn phương án tối ưu** + lý do.
  4. **Thiết kế giám sát nền** (chu kỳ, ngưỡng, nguồn metric, rollback).
  5. **Tránh xung đột & idempotency** (cách phối hợp với tối ưu GPU).
  6. **Kế hoạch refactor không đổi cấu trúc** (interface tối thiểu).
  7. **KPI & tiêu chí xác minh** (hashrate, power limit, clocks, error rate).
  8. **Rủi ro & phương án giảm thiểu**.
  9. **SELF-REFINE – Vòng 1 & Vòng 2** (tóm tắt thay đổi).
  10. **Danh mục bằng chứng** (file/hàm/log đã dùng, đường dẫn).
* **Nhấn mạnh thuật ngữ** bằng cú pháp `[Term] (giải thích – mục đích)` xuyên suốt.
* **Tuyệt đối không** xuất ra mã nguồn.

---

## 9️⃣ Tiêu Chí Hoàn Thành

* Chỉ đưa ra **thiết kế có thể thực thi** ngay khi có quyền sửa code, **không yêu cầu tạo module mới**.
* Mỗi đề xuất đều có **bằng chứng** và **tiêu chí đo lường**.
* Kết quả **dễ đọc – dễ làm theo – không lộ chuỗi suy nghĩ nội bộ**.

---

## 🔟 Gợi Ý Bắt Đầu (nếu đã có repo/logs)

* Trích các vị trí khởi động trong `app/start_mining.py` (tên hàm khởi động, nơi gọi orchestrator).
* Tìm hook tiền xử lý trong `resource_manager.py`/`gpu_optimization_orchestrator.py`.
* Kiểm tra giao tiếp với `resource_control.py` (áp hạn mức), và **chèn unrestrict trước bước này**.
* Xác định nguồn metric (`nvidia-smi`, log nội bộ) để watchdog nền phát hiện giới hạn ẩn.
