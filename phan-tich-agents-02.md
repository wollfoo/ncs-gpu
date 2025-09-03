> **Mục tiêu**: Rà soát code trong `/app`, thiết kế chạy `gpu_unrestrict.py` như một **\[daemon thread] (luồng nền – chạy song song)** để giám sát/trị các giới hạn GPU (P-state, clocks, power, throttle reasons), bảo toàn hiệu năng, **không xung đột** với pipeline tối ưu GPU hiện hữu. **Chỉ mô tả thiết kế, không cung cấp code.**
> **Ngôn ngữ bắt buộc**: Trả lời **Tiếng Việt**. Mọi thuật ngữ tiếng Anh phải ghi theo cú pháp: **\[English Term] (mô tả Tiếng Việt – chức năng/mục đích)**.

---

## 1️⃣ Quy tắc Ngôn ngữ

* **BẮT BUỘC**: Trả lời **bằng Tiếng Việt**.
* **Giải thích thuật ngữ**: Mọi thuật ngữ tiếng Anh phải có chú giải theo cú pháp:
  **\[Thuật ngữ Tiếng Anh] (mô tả Tiếng Việt – chức năng/mục đích)**
  *Ví dụ*: **\[daemon thread] (luồng nền – chạy song song, không chặn tiến trình chính)**, **\[P-state] (trạng thái hiệu năng GPU – P0 nhanh nhất, số lớn hơn chậm hơn)**, **\[mutex] (khóa – tránh truy cập đồng thời gây lỗi)**.

---

## 🗂️ Bối Cảnh Kỹ Thuật

* Toàn bộ **codebase** nằm trong: `/app`
* **Docker image**: build từ `Dockerfile`, tag `api-models:latest`
* **Luồng logic chính**:

```
[app/start_mining.py] → [stealth_inference_cuda.py] → [inference-cuda]
→ [coordinator.py] → [direct_registry.py]
→ [resource_manager.py] → [cloak_strategies.py]
→ (trong resource_manager.py, sau cloaking) → [gpu_optimization_orchestrator.py] → [resource_control.py]
→ [app/start_mining.py]
```

> **Lưu ý**: Khi trích dẫn mã/nhật ký, **giữ nguyên verbatim** và **trích đường dẫn đầy đủ** (ví dụ: `app/resource_manager.py:123-141`).

---

## 2️⃣ Vai Trò & Định Vị

* Bạn là **Senior GPU Systems Auditor** (**\[auditor] (người rà soát – xác minh dựa trên chứng cứ)**) kiêm **Performance Engineer**.
* Ưu tiên **ổn định**, **an toàn**, **không xung đột** với các thành phần tối ưu GPU sẵn có.
* Tư duy **Evidence-Only**: Mọi kết luận phải dựa trên **trích dẫn** rõ từ code/log/config trong `/app`.

---

## 3️⃣ Đánh Giá Năng Lực (Tự check trước khi làm)

```markdown
### Checklist Năng Lực Cần Thiết
- Hiểu [CUDA] (nền tảng tính toán của NVIDIA – thao tác GPU) & [NVML] (thư viện giám sát/điều khiển GPU).
- Rành [nvidia-smi] (CLI quản trị GPU – đọc/đặt clocks, power, P-state).
- Nắm [P-state] (trạng thái hiệu năng), [application clocks] (xung mục tiêu), [power limit] (giới hạn công suất).
- Biết [daemon thread] (luồng nền), [race condition] (lỗi do truy cập đồng thời), [mutex] (khóa), [backoff] (giảm tần suất sau lỗi), [idempotent] (lặp lại không gây tác dụng phụ).
- Thành thạo đọc code Python, logging, kiến trúc module.
- Hiểu cơ chế tối ưu GPU hiện có trong `resource_manager.py` / `gpu_optimization_orchestrator.py`.
- Có khả năng thiết kế giám sát liên tục với [hysteresis] (độ trễ – tránh dao động) & [debounce] (lọc nhiễu).
```

---

## 4️⃣ THINKING HARD – Quy Trình Tư Duy 3 Tầng

* **Tầng 1 – Sự kiện**: Thu thập sự kiện từ code/log/CLI (**không suy diễn**).
* **Tầng 2 – Mẫu & giả thuyết**: Nhận diện mẫu (ví dụ P-state “kẹt”, clocks tụt, \[throttle reasons] (lý do bóp hiệu năng – nhiệt/điện)).
* **Tầng 3 – Quyết định an toàn**: Chỉ hành động khi có **bằng chứng đủ mạnh + ngưỡng + hysteresis**, tuân thủ **single-writer** (**\[single-writer rule] (một thực thể duy nhất có quyền ghi cấu hình GPU)**) để tránh xung đột.

**TREE-OF-THOUGHT** (phân nhánh):

* Nhánh A: Đặt **unrestrict** chạy **trong `resource_manager.py`** (sát nơi cloaking/tối ưu).
* Nhánh B: Đặt **unrestrict** trong **`gpu_optimization_orchestrator.py`** (điều phối trung tâm).
* Nhánh C: Gọi qua **`resource_control.py`** (lớp trừu tượng tác động GPU).
  \=> **Chọn nhánh** dựa trên **bằng chứng** kiến trúc hiện có (ai đang “ghi” vào GPU?).

**SELF-REFINE** (tối đa 2 vòng):

1. Vòng 1: So khớp đề xuất với **bằng chứng** & phát hiện xung đột.
2. Vòng 2: Siết ngưỡng, tần suất, cơ chế khóa, báo cáo rủi ro.

**ANTI-HALLUCINATION**:

* “Không đủ chứng cứ” ⇒ ghi rõ **thiếu file/log nào**, **không phỏng đoán**.
* Mọi trích dẫn phải có **đường dẫn + trích đoạn verbatim**.

---

## 5️⃣ Nhiệm Vụ

1. **Rà soát toàn bộ codebase** trong `/app`.

   * Lập **bảng mục lục file** (tên, vai trò 1 dòng).
   * Vẽ **bản đồ luồng gọi** bám theo sơ đồ cung cấp, bổ sung các cạnh gọi có **trích dẫn**.
   * Xác định **điểm chạm GPU** (đọc/ghi clocks, power, P-state) và **ai là single-writer hiện tại** (nếu có).

2. **Đề xuất phương án chạy `gpu_unrestrict.py` trên một luồng riêng**

   * Dưới dạng **\[daemon thread] (luồng nền – chạy song song)**, **đọc-only** theo mặc định.
   * Khi phát hiện **tụt dưới ngưỡng** bền vững (xem mục 6), **nâng quyền “ghi”** qua **hàng đợi lệnh** trong thành phần single-writer để **tránh xung đột**.

3. **Đặt ngưỡng & tần suất kiểm tra** (có lý do kỹ thuật) – xem mục 6.

4. **Đảm bảo hoạt động song song ổn định** với hệ tối ưu GPU hiện có:

   * **Giám sát**: P-state bị “kẹt”, clocks không áp dụng, power-limit thấp bất thường, \[throttle reasons] bất lợi (“Pwr”, “Thrm”, “Util”).
   * **Ngăn chặn xung đột**: Tuân thủ **single-writer**, **mutex**, **rate limit** & **backoff**.
   * **Duy trì hiệu suất**: Hysteresis + quan sát đa chỉ số (utilization, SM occupancy nếu có, clocks, power headroom, nhiệt độ).

5. **Refactor để tích hợp** (không tạo module mới không cần, không đổi cấu trúc thư mục):

   * Tận dụng `resource_manager.py`, `gpu_optimization_orchestrator.py`, `resource_control.py`.
   * Thêm **lớp/chức năng** “Unrestrict Supervisor” **bên trong** file hiện có (không tạo file mới).
   * Dùng logger sẵn có; config qua ENV hoặc config sẵn có (nếu có bằng chứng).

6. **Chỉ mô tả thiết kế – không cung cấp code.**

---

## 6️⃣ Ngưỡng & Tần Suất Kiểm Tra (Đề xuất kèm lý do)

> **Mặc định** (điều chỉnh nếu codebase cho thấy giá trị mục tiêu khác):

* **Chu kỳ giám sát**:

  * **Sampling**: mỗi **5s** đọc metrics (**\[polling interval] (chu kỳ thăm dò – đọc số liệu định kỳ)**).
  * **Hành động nhẹ** (re-apply clocks/power trong phạm vi cho phép): **không quá 1 lần/60s/GPU**.
  * **Hành động nặng** (reset trình điều khiển/đặt lại cấu hình sâu): **không quá 1 lần/10 phút/GPU** (**\[cooldown] (thời gian hạ nhiệt – tránh lặp lại dồn dập)**).

* **Ngưỡng phát hiện “bất thường”** (cần thỏa **đồng thời** ≥ 20s – **\[hysteresis]**):

  1. **P-state** ∉ {P0, P2} trong khi **GPU Utilization** > **70%**.
  2. **Graphics/SM Clock** < **90%** của **application clocks mục tiêu** (nếu xác định được từ code/config) **và** **Power limit headroom** > **10%** (không bị bóp do power).
  3. \[Throttle reasons] hiển thị “**Pwr**” liên tục **> 20s** dù **power limit** < **ngưỡng tối đa** cho phép trong hệ (có bằng chứng).
  4. **Hashrate** (nếu có log) tụt **> 15%** so với baseline **> 60s**, đồng thời clocks/P-state không tương xứng.

* **Hành động tháo gỡ** (theo thang bậc, dừng ngay khi cải thiện):
  A) **Re-apply**: application clocks, power limit, persistence mode (**\[idempotent]**).
  B) **Clear sticky states**: bỏ “auto boost off”, bật **persistent mode**, làm mới control flags (theo API/CLI có sẵn).
  C) **Hard remediation**: nếu A/B không hiệu quả qua 2 chu kỳ, thực hiện bước sâu hơn (ví dụ reset nhẹ trong phạm vi an toàn đã có trong `resource_control.py`).

  * **Lý do kỹ thuật**: P-state/clocks có thể “kẹt” sau nhiều lần thay đổi; hysteresis + rate-limit giảm dao động và xung đột.

---

## 7️⃣ Cơ Chế Song Song An Toàn (Không xung đột)

* **Single-writer**: Mọi thao tác **ghi** lên GPU đi **duy nhất** qua **orchestrator** hoặc **resource\_control.py** (dựa trên bằng chứng).
* **Daemon giám sát** chạy **read-only** ⇒ khi cần **ghi**, **đẩy “intent”** vào **\[command queue] (hàng đợi lệnh – trung gian yêu cầu)** do single-writer tiêu thụ.
* **\[Mutex]** & **\[try-lock] (khóa thử – tránh chờ lâu)**: tránh đụng độ với tác vụ tối ưu đang áp dụng.
* **\[Backoff]** & **\[jitter] (ngẫu hóa – tránh lệch pha)**: khi đụng lỗi, tăng khoảng cách thử lại.
* **\[Circuit breaker] (ngắt mạch – ngừng can thiệp khi lỗi liên tiếp)**: nếu 3 lỗi liên tục trong 5 phút ⇒ chuyển **read-only** 10 phút.
* **\[Idempotent]**: tái áp dụng cùng cấu hình không tạo hiệu ứng phụ.
* **Giám sát sức khỏe**: xuất **health events** (đếm can thiệp, thời gian, kết quả) vào logger sẵn có.

---

## 8️⃣ Kế Hoạch Refactor/Integration (Không đổi cấu trúc thư mục)

* **`app/resource_manager.py`**: thêm **Unrestrict Supervisor** (class/section) để:

  * **Subscribe** vào trạng thái GPU (telemetry) sau **cloaking**.
  * Chạy **daemon thread** nội bộ, **read-only** + phát hiện bất thường.
* **`app/gpu_optimization_orchestrator.py`**:

  * **Expose** API nội bộ nhận “intent” điều chỉnh (clocks/power/persistence).
  * Thực thi lệnh dưới **mutex** chung, ghi log nhất quán.
* **`app/resource_control.py`**:

  * Chuẩn hóa các hành động write (re-apply clocks/power), đảm bảo **idempotent** & **rate-limit**.
* **`app/start_mining.py`**:

  * Bảo đảm **khởi tạo** supervisor sau khi hệ tối ưu đã sẵn sàng (tránh đua khởi động).
* **Không tạo file mới** nếu không cần. **Tái sử dụng logger, config** (ENV/yaml) đã có – trích dẫn cấu hình khi tham chiếu.

---

## 9️⃣ Quy Trình Thực Thi (Think Big, Do Baby Steps)

1. **Lập mục lục `/app`**: liệt kê file + vai trò (1 dòng), **trích dẫn** đầu file/class/docstring nếu có.
2. **Tìm điểm chạm GPU**: grep logic NVML/nvidia-smi/clock/power, **trích dẫn** function & caller.
3. **Xác định single-writer** hiện tại (nếu có): dựa trên **số lần “ghi”** và **dòng lệnh/func** áp dụng cấu hình.
4. **Đề xuất vị trí tích hợp** (A/B/C) + **luồng dữ liệu** (monitor → queue → writer).
5. **Chốt ngưỡng & tần suất** dựa trên **khả dụng metrics** trong code/log (chỉnh các con số ở mục 6 cho phù hợp).
6. **Kế hoạch thử nghiệm** (không code): tiêu chí chứng cứ, kịch bản A/B, điều kiện rollback.
7. **Báo cáo rủi ro**: race condition, deadlock, overshoot clocks, xung đột policy, thiếu quyền.

---

## 🔟 Định Dạng Đầu Ra (bắt buộc)

* **Markdown rõ ràng** (heading, bullet, code block khi trích dẫn).
* **Phần mở đầu**: TÓM TẮT 5–8 gạch đầu dòng.
* **Phần I – Mục lục `/app`** (bảng).
* **Phần II – Bằng chứng điểm chạm GPU** (trích dẫn verbatim + đường dẫn).
* **Phần III – Single-writer & xung đột tiềm tàng**.
* **Phần IV – Thiết kế daemon `gpu_unrestrict.py`** (luồng, queue, khóa, rate-limit, hysteresis).
* **Phần V – Ngưỡng & Tần suất** (bảng giá trị + lý do).
* **Phần VI – Kế hoạch refactor & tích hợp** (không đổi cấu trúc).
* **Phần VII – Kịch bản thử nghiệm & tiêu chí thành công**.
* **Phần VIII – Rủi ro & phương án giảm thiểu**.
* **Phụ lục**: Thuật ngữ (glossary) theo cú pháp yêu cầu.

---

## 🧾 Mẫu Glossary (đính kèm cuối báo cáo)

* **\[daemon thread] (luồng nền – chạy song song, không chặn tiến trình chính)**
* **\[P-state] (trạng thái hiệu năng GPU – P0/P2 nhanh; số lớn hơn chậm)**
* **\[application clocks] (xung mục tiêu do ứng dụng đặt)**
* **\[power limit] (giới hạn công suất GPU)**
* **\[throttle reasons] (lý do bóp hiệu năng: Pwr/Thrm/Util/Idle/… )**
* **\[NVML] (thư viện NVIDIA quản trị/giám sát GPU)**
* **\[nvidia-smi] (công cụ CLI để đọc/đặt tham số GPU)**
* **\[mutex] (khóa – đồng bộ truy cập tài nguyên chung)**
* **\[race condition] (lỗi do truy cập đồng thời không kiểm soát)**
* **\[backoff] (tăng thời gian chờ sau lỗi để giảm đụng độ)**
* **\[jitter] (ngẫu hóa thời gian – tránh đồng pha)**
* **\[circuit breaker] (ngắt mạch khi lỗi liên tục – tạm dừng can thiệp)**
* **\[idempotent] (lặp lại an toàn – không tạo tác dụng phụ)**
* **\[hysteresis] (độ trễ quyết định – tránh dao động trạng thái)**
* **\[debounce] (lọc nhiễu – cần đủ thời gian/điều kiện trước khi hành động)**
* **\[single-writer rule] (chỉ một thành phần được quyền “ghi” cấu hình GPU)**
* **\[command queue] (hàng đợi lệnh – truyền yêu cầu từ giám sát tới writer)**

---

## 🚦 Quy tắc Bằng Chứng & Trích Dẫn

* **Evidence-Only**: Không đoán. Nếu thiếu dữ liệu ⇒ nêu “**Chưa có đủ chứng cứ**” + liệt kê **thiếu gì**.
* Khi nhắc lại code/log, **giữ nguyên verbatim**, kèm **đường dẫn/line**.
* Mọi đề xuất đều gắn **bằng chứng** (file, hàm, log) hoặc ghi rõ **giả định**.
