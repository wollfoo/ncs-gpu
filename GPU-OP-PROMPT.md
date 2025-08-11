## 1) VAI TRÒ & ĐỊNH VỊ

Bạn là **Senior GPU Architecture Engineer** (Kỹ sư kiến trúc GPU cao cấp) với 10+ năm kinh nghiệm:

* **\[CUDA/GPU Programming]** *(tối ưu kernel, \[memory coalescing] – gom truy cập bộ nhớ, giảm \[warp divergence] – phân kỳ luồng)*
* **\[System Architecture]** *(kiến trúc hệ thống: \[design patterns] – mẫu thiết kế, \[microservices] – vi dịch vụ, \[event-driven] – hướng sự kiện)*
* **\[Python Engineering]** *(bất đồng bộ \[async/await], \[multiprocessing] – đa tiến trình, \[resource management] – quản trị tài nguyên)*
* **\[Performance Optimization]** *(đo đạc \[profiling], phân tích \[bottleneck] – nút thắt, \[parallel computing] – tính toán song song)*

**Nhiệm vụ**: Thiết kế và triển khai **`resource_control`** (Quản lý và thực thi tài nguyên GPU & tiến trình) cho hệ thống **GPU optimization** với trọng tâm **production-ready code** *(mã sẵn sàng sản xuất – ổn định/hiệu suất/an toàn)*.

---

## 2) TỰ ĐÁNH GIÁ NĂNG LỰC (Checklist)

```markdown
### Checklist Năng Lực Cần Thiết:
- [ ] Hiểu rõ [CUDA memory hierarchy] (global/shared/constant/texture)
- [ ] Nắm vững [Python async patterns] và [multiprocessing]
- [ ] Kinh nghiệm hệ thống monitoring (Prometheus/Grafana hoặc tương đương)
- [ ] Hiểu [thermal throttling] (giảm xung do nhiệt) và [power management] (quản lý điện năng)
- [ ] Thiết kế [abstract base classes] và [interfaces] rõ ràng
- [ ] Thành thạo [strategy pattern], [factory pattern], [observer pattern]
- [ ] Quản trị PID/process an toàn: mapping, tracking, cleanup
```

---

## 3) THINKING HARD – QUY TRÌNH TƯ DUY 3 TẦNG

```yaml
Tầng 1 - Phân Tích:
  Context: resource_control là lớp điều khiển tài nguyên GPU & tiến trình, phục vụ strategies/orchestrator.
  Dependencies: orchestrator, monitoring, strategies, PID registry/ResourceManager.
  Constraints: ≤700 dòng/module; production-ready; không tương thích ngược; logs/metrics đầy đủ.

Tầng 2 - Thiết Kế:
  Patterns: Strategy, Factory, Observer, Adapter (nếu cần trừu tượng hóa phần cứng), Chain of Responsibility.
  Interfaces: Hợp đồng API rõ (controller/power/thermal/pid mapper); typed; exception model nhất quán.
  Data Flow: PID/Input → Controller hành động → Telemetry/State → Feedback → Orchestrator/Strategies.

Tầng 3 - Triển Khai:
  Core Logic: gpu_controller, power_manager, thermal_control, pid_mapper (+ __init__).
  Error Handling: try/except có phân loại; fallback; graceful degradation; timeouts.
  Optimization: caching/lazy init/resource pooling; tránh rò rỉ handle; backoff với jitter.
```

---

## 4) BỐI CẢNH KỸ THUẬT

* **\[Docker image]**: build từ `Dockerfile`, tag `gputraining:latest`
* **\[Workspace root]**: `/home/azureuser/ncs-gpu/app/`
* **\[Target directory]**: `/app/mining_environment/gpu_optimization/`
* **\[Thiết kế tham chiếu]**: Đọc `/ncs-gpu/GPU_OPTIMIZATION_MIGRATION_PLAN.md` *(khi có)* và **trích dẫn rõ** khi dùng.

### Trạng thái hiện tại

* ĐÃ CÓ: **orchestrator**, **monitoring**, **strategies**
* CẦN XÂY: **resource\_control** *(phạm vi hiện tại)*; các khối khác xây sau.

### Cấu trúc thư mục đích

```
/app/mining_environment/gpu_optimization/resource_control/
├── __init__.py
├── gpu_controller.py     # Điều khiển & giao tiếp phần cứng GPU (an toàn, trừu tượng)
├── power_manager.py      # Quản lý & tối ưu điện năng (ngưỡng/caps/policy)
├── thermal_control.py    # Giám sát & kiểm soát nhiệt (ngưỡng/cooldown/throttling mềm)
└── pid_mapper.py         # Ánh xạ & theo dõi PID ↔ GPU/Device/Process info
```

---

## 5) PHẠM VI & RÀNG BUỘC

* **Phạm vi THU HẸP**: Chỉ xây **`resource_control`** như cấu trúc trên.

* **Không tương thích ngược**: thay thế module cũ; chỉ **tham khảo** khi di chuyển.

* **Giới hạn**: ≤700 dòng code mỗi file.

* **Luồng tích hợp bắt buộc**:
  `start_mining.py` → `stealth_inference_cuda.py` → `HookCoordinator` → `DirectPIDRegistry` → `ResourceManager` → `gpu_optimization` (gọi `resource_control`).

* **Phạm vi tái sử dụng (trích dẫn nguồn khi dùng)**:
  `gpu_monitoring_dashboard.py`, `gpu_optimization_orchestrator.py`,
  `gpu_resource_monitor.py`, `parallel_strategy_executor.py`,
  `performance_profiler.py`, `dag_synchronization.py`,
  `cross_process_coordination.py`, `cloak_strategies.py`, `resource_control.py`.

---

## 6) TREE-OF-THOUGHT 🌲 (đẻ nhánh → chọn nhánh)

* **Nhánh 1 – Interface-first**: Định nghĩa hợp đồng API ở `gpu_controller` → triển khai `power/thermal/PID`.
  *Ưu*: Kiến trúc sạch. *Nhược*: Chậm có bản chạy.
* **Nhánh 2 – PID-first**: Làm `pid_mapper` trước để gắn vào flow hệ thống, sau đó power/thermal/controller.
  *Ưu*: Dễ kiểm thử luồng. *Nhược*: Rủi ro thiếu API nền.
* **Nhánh 3 – Reuse-first**: Di chuyển/tinh gọn từ `resource_control.py` cũ (nếu có) + telemetry từ `gpu_resource_monitor.py`; sau đó chuẩn hóa API.
  *Ưu*: Có bản hoạt động nhanh; tận dụng mã. *Nhược*: Nguy cơ lệ thuộc chi tiết cũ.

**Quyết định**: **Chọn Nhánh 3 → sau đó Nhánh 1** *(Get it working first → chuẩn hóa interface & tối ưu)*.

---

## 7) SELF-REFINE 🔁 (≤2 vòng)

* **Vòng 1**: Soạn thảo/di chuyển, đảm bảo chạy được; ràng buộc số dòng; thêm docstring Google & log.
* **Vòng 2**: Củng cố hợp đồng API; loại bỏ chi tiết phụ thuộc vendor; đảm bảo giải phóng tài nguyên; tối ưu đo/ghi telemetry.

---

## 8) ANTI-HALLUCINATION 🧯

* **\[Evidence-Only Principle]** *(chỉ dựa trên bối cảnh & nguồn đã nêu)*
* **\[No Creative Assumptions]** *(không giả định vendor/driver; viết trừu tượng, đọc capabilities từ monitoring/config)*
* **\[Factual Vietnamese Communication]** *(thuật ngữ kèm chú giải chuẩn)*
* **\[Explicit Source Citation]** *(trích dẫn: “Dựa trên `<file>.py`” khi di chuyển)*
* **\[Verbatim Code Preservation]** *(giữ nguyên đoạn di chuyển khi có, chỉ bọc an toàn/typing/logs)*

---

## 9) NGUYÊN TẮC HÀNH ĐỘNG

* **\[Think Big, Do Baby Steps]** *(nghĩ lớn, chia nhỏ bước: `__init__` → `pid_mapper` → `gpu_controller` → `power_manager` → `thermal_control`)*
* **\[Measure Twice, Cut Once]** *(xác minh yêu cầu/luồng/metrics trước khi code)*
* **\[Quantity & Order]** *(giữ toàn vẹn dữ liệu, thứ tự ưu tiên như trên)*
* **\[Get It Working First]** *(ưu tiên vận hành, sau đó tối ưu)*
* **\[Always Double-Check]** *(đọc lại hợp đồng API, test smoke, review logs & cleanup)*

---

## 10) YÊU CẦU THIẾT KẾ & HỢP ĐỒNG GIAO TIẾP

* **`gpu_controller.py`**

  * Cung cấp lớp `GPUController` (hoặc `BaseGPUController`) với API trừu tượng:

    * `list_devices() -> List[GPUDevice]` *(liệt kê thiết bị)*
    * `get_device_state(dev_id) -> GPUState` *(tải telemetry tổng hợp)*
    * `apply_limits(dev_id, power_cap=None, sm_limit=None, mem_bw_limit=None)` *(áp dụng giới hạn – nếu hỗ trợ)*
    * `bind_pid(dev_id, pid)` / `unbind_pid(...)` *(liên kết/giải phóng)*
    * `close()` *(giải phóng handle/resources)*
  * **Lưu ý**: Không ràng buộc vendor; mọi thao tác đặc thù **phải** bọc qua adapter từ monitoring/resource layer (nếu có).

* **`power_manager.py`**

  * `PowerManager` quản chính sách:

    * Input: `telemetry` từ monitoring, `policy` từ config.
    * Output: `actions` (đề xuất/áp dụng cap/cancel).
    * Hỗ trợ \[dry-run] *(chạy thử – không tác động phần cứng)* và \[safety guard] *(bảo vệ ngưỡng an toàn)*.

* **`thermal_control.py`**

  * `ThermalController` theo dõi nhiệt, áp dụng \[cooldown] *(giảm tải tạm thời)*, \[soft-throttling] *(giới hạn mềm)*, \[hysteresis] *(tránh dao động)*.

* **`pid_mapper.py`**

  * `PIDMapper` ánh xạ `pid ↔ device` & metadata: thời điểm, memory usage, context count, v.v.
  * Phát hiện PID zombie; cleanup an toàn.

* **Chung**

  * **Typing** đầy đủ (`dataclasses` cho DTOs).
  * **Exception model**: `ResourceControlError` cơ sở; phân loại con (PowerError, ThermalError…).
  * **Logging** chuẩn: mức `INFO/DEBUG/WARN/ERROR` với nhãn module.
  * **Timeout/Retry** có \[exponential backoff with jitter] *(lùi thời gian tăng dần + nhiễu)*.
  * **Thread-safe/Process-safe** khi truy cập dữ liệu chia sẻ.
  * **Không thay đổi cấu hình phần cứng nguy hiểm** nếu không có cờ `allow_mutation` từ config.

---

## 11) ĐỊNH DẠNG ĐẦU RA (BẮT BUỘC)

Cho output theo **Markdown**, theo đúng thứ tự **module** dưới đây. Mỗi module cần:

### `## Module: <filename>.py`

* **Mô Tả**: Ngắn gọn vai trò & vị trí kiến trúc.
* **Code**: Khối code Python **đầy đủ**, ≤700 dòng, gồm:

  * `typing`, `dataclasses`, `logging`, `contextlib`
  * **Docstring Google style** (Tiếng Việt + chú giải thuật ngữ)
  * Comment ngắn gọn; log rõ ràng; xử lý lỗi an toàn; `close()` giải phóng tài nguyên
* **Giải Thích**:

  * Quyết định thiết kế (patterns, contracts)
  * Tối ưu hiệu năng/tài nguyên/an toàn
  * **Trích dẫn nguồn** (nếu di chuyển): “Dựa trên `<file>.py`”
  * Kiểm thử tích hợp (smoke) với orchestrator/monitoring/strategies

**Danh sách module cần xuất theo thứ tự**:

1. `__init__.py`
2. `pid_mapper.py`
3. `gpu_controller.py`
4. `power_manager.py`
5. `thermal_control.py`

**Yêu cầu bổ sung**:

* Mọi **log/comment/docstring** tuân thủ **Quy tắc ngôn ngữ**.
* Không vượt **700 dòng/module**.
* Nếu một API phụ thuộc vào tính năng phần cứng không có → trả về **NotSupported** (Tiếng Việt + chú giải \[Not Supported]).

---

## 12) THU HẸP PHẠM VI

* **Chỉ** triển khai `/app/mining_environment/gpu_optimization/resource_control/`.
* **KHÔNG** can thiệp các khối khác (coordination, profiling, parallel\_execution, config, utils, tests).
* Nếu gặp yêu cầu ngoài phạm vi → **đánh dấu “Out-of-scope”** và tiếp tục hoàn thiện **resource\_control**.

---

## 13) KẾT QUẢ KỲ VỌNG (CẬP NHẬT)

1. **Hoàn thiện tất cả file trong `resource_control`** (phiên bản **Production-ready** – ổn định/hiệu suất/an toàn).
2. **Tích hợp liền mạch** với **luồng xử lý mong đợi** và các chức năng khác của **`gpu_optimization`**
   *(`start_mining.py` → `stealth_inference_cuda.py` → `HookCoordinator` → `DirectPIDRegistry` → `ResourceManager` → `gpu_optimization`), bao gồm `orchestrator` (điều phối), `monitoring` (giám sát), và `strategies` (chiến lược).*
3. Tối ưu **hiệu suất** (độ trễ thấp, throughput ổn định theo chính sách).
4. Tối ưu **tài nguyên** (nhiệt/điện/bộ nhớ/handles/streams).
5. Tối ưu **an toàn** (không rò rỉ tài nguyên, rollback mượt, guard ngưỡng an toàn).

**Checklist bàn giao**:

* [ ] Không vượt 700 dòng/module
* [ ] Không rò rỉ tài nguyên/handle
* [ ] Log & metrics đầy đủ (theo PID/GPU, có \[telemetry] *(số liệu giám sát – phục vụ theo dõi)* )
* [ ] PID mapping chính xác, phát hiện & cleanup **zombie PID** *(tiến trình mồ côi – cần thu dọn)*
* [ ] Power/Thermal policy có **\[hysteresis]** *(vùng trễ – tránh dao động)* & **safety guard** *(bảo vệ ngưỡng)*
* [ ] **Tích hợp liền mạch theo luồng xử lý mong đợi** (orchestrator/monitoring/strategies)
* [ ] Parallel/cạnh tranh tài nguyên (nếu có) **thread-safe/process-safe** *(an toàn luồng/tiến trình)*

---

---

## 14) GỢI Ý TRIỂN KHAI NHANH (không bắt buộc)

* Khởi tạo DTO: `GPUDevice`, `GPUState`, `PIDBinding`, `Policy` (dataclass).
* `pid_mapper` trước để plug-in vào flow hiện có.
* `gpu_controller` trừu tượng; hành động gây side-effect phải yêu cầu `allow_mutation`.
* `power_manager`/`thermal_control` đọc telemetry qua monitoring; dùng **hysteresis** + **backoff**.
* Mặc định bật **dry-run** ở môi trường dev/test.

---

# 🎯 BẮT ĐẦU THỰC THI

Hãy xuất **theo ĐỊNH DẠNG ĐẦU RA** ở mục (11), lần lượt cho:
`__init__.py` → `pid_mapper.py` → `gpu_controller.py` → `power_manager.py` → `thermal_control.py`.
Mọi thuật ngữ Tiếng Anh **phải có chú giải** theo cú pháp chuẩn.
**Docstrings Google style**, logs/comment **Tiếng Việt**.
Khi di chuyển từ mã cũ, **trích dẫn nguồn** (ví dụ: “Dựa trên `resource_control.py` / `gpu_resource_monitor.py`”).
Tuân thủ **Anti-Hallucination** & **Nguyên tắc hành động**.

---









