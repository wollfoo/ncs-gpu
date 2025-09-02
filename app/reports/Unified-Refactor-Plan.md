## Kế hoạch Giải pháp Hợp nhất – Tái cấu trúc GPU Mining (Unified Refactor Implementation Plan)

### 1) Mục tiêu, Phạm vi, Ràng buộc
- **Mục tiêu**: Khôi phục và giữ vững hashrate mục tiêu (≥24.96 MH/s tổng cho 2 GPU) ổn định ≥15 phút; phục hồi đồng nhất (GPU0≈GPU1) sau ≥3 lần restart liên tiếp, không suy giảm theo thời gian.
- **Phạm vi**: Chỉ các tệp trong `app/` theo luồng hiện tại: `start_mining.py` → `stealth_inference_cuda.py` → `inference-cuda` → `coordinator.py` → `direct_registry.py` → `resource_manager.py` → `cloak_strategies.py` → (trong `resource_manager.py`, sau cloaking) → `gpu_optimization_orchestrator.py` → `resource_control.py` → quay lại `app/start_mining.py`.
- **[Constraints] (ràng buộc – điều không được phá vỡ)**: Không tạo module mới nếu không thật sự cần; không thay đổi cấu trúc thư mục; không chèn mã ngoài phạm vi hiện có; ưu tiên tận dụng hạ tầng logging/khóa/khởi tạo sẵn có.

### 2) Call-flow hiện tại (đối chiếu bằng chứng)
```text
start_mining.py → stealth_inference_cuda.py → inference-cuda
→ coordinator.py → direct_registry.py → resource_manager.py → cloak_strategies.py
→ (trong resource_manager.py, sau cloaking) → gpu_optimization_orchestrator.py → resource_control.py
→ quay lại start_mining.py
```
Nguồn trích dẫn:
```69:76:app/reports/report-03.md
[app/start_mining.py] → ... → [gpu_optimization_orchestrator.py] → [resource_control.py] → [app/start_mining.py]
```
```11:12:app/reports/report-04.md
Luồng chính: ... → `resource_control.py` → trở về `app/start_mining.py`.
```

### 3) Cơ sở bằng chứng (Evidence) để thiết kế giải pháp
- **[Root cause] (nguyên nhân gốc rễ – vì sao xảy ra lỗi)**: Trạng thái **[application clocks] (khóa xung ứng dụng – cố định xung core/mem)** và thiết lập GPU khác bị “dính” giữa các phiên do reset/cleanup không hoàn chỉnh, cộng hưởng với **[persistence mode] (chế độ bền bỉ – giữ context driver)**.
```65:79:app/reports/report-01.md
Thiếu reset Application Clocks `-rac` ... vắng `nvidia-smi -rac` ... `-rgc`/`--reset-memory-clocks` không xoá Application Clocks.
```
```50:56:app/reports/report-02.md
pynvml.nvmlDeviceResetApplicationsClocks(handle)  # ← CRITICAL POINT
# ... but also uses nvidia-smi reset commands that can conflict ...
```
- **Không phải thermal throttling**: Nhiệt độ ~38°C, công suất ~75W, clocks ~412/877 MHz; hashrate ~20.31 MH/s (2 GPU) – mâu thuẫn với giả thuyết do nhiệt.
```11:17:app/reports/report-02.md
Hashrate 20.31 MH/s; GPU clocks 412/877 MHz; Power/Temp 75W, 38°C.
```
- **[Race condition] (điều kiện đua – cạnh tranh thời điểm/luồng)** và thiếu **readiness gate** cho `ResourceManager`.
```110:116:app/reports/report-02.md
if ResourceManager._instance and ResourceManager.is_ready():  # ← CHECK CAN FAIL
```
- **[Silent exception] (bắt lỗi im lặng – nuốt lỗi)** che khuất lỗi NVML → khó chẩn đoán.
```153:160:app/reports/report-03.md
except Exception:
    pass  # ❌ CRITICAL: NVML errors swallowed silently!
```
- **Gate “skip-lock khi SM<800 MHz”** có thể giữ GPU ở bẫy xung thấp nếu không có **[preflight reset] (reset trước khi chạy – hoàn nguyên an toàn)**.
```930:937:app/reports/report-04.md
if (not cl_enabled) and current_sm_clock < 800: ... return False
```
- **[persistence mode]** bật từ setup → trạng thái dễ “dính” nếu reset không triệt để.
```363:367:app/reports/report-04.md
_run_smi(['nvidia-smi','-pm','1'], logger, "Enable persistence mode")
```

### 4) Chiến lược tổng thể
- Ưu tiên “**Get It Working First**” (làm cho chạy ổn trước): bổ sung **preflight deterministic reset** (NVML-first, thêm `-rac` tại điểm reset hiện có), đăng ký **cleanup on exit** (hoàn nguyên khi thoát), loại **silent exceptions**, và **readiness gate** trước khi khởi chạy miner.
- Sau đó “**Measure Twice, Cut Once**” (đo hai lần, cắt một lần): chuẩn hoá **[Single Source of Truth] (nguồn sự thật duy nhất – tập trung thao tác/state)** trong `resource_control.py`, thứ tự tất định NVML-first → CLI fallback → verify, tăng quan sát (P-state, **[perf cap reasons] (lý do giới hạn hiệu năng)**), kèm rollback.
- Luôn “**Always Double-Check**”: so sánh trước/sau reset, qua ≥3 lần restart, theo cặp GPU0/GPU1.

---

## 5) Lộ trình các Giai đoạn (Phases)

### Phase 0 — Cứu hoả & Phục hồi tức thì (0–1 ngày)
- **Mục tiêu**: Xoá trạng thái GPU “dính”, đưa clocks về mức khai thác (≈1245/877 MHz) dưới tải, khôi phục hashrate tổng ≥24.96 MH/s ổn định ≥15′, nhất quán giữa GPU0/GPU1.
- **Đầu vào (Inputs)**:
  - Bằng chứng báo cáo: thiếu `-rac`, conflict NVML↔`nvidia-smi`, silent exceptions, readiness gate thiếu, gate SM<800.
  - Hệ thống đang bật **[persistence mode]**.
- **Đầu ra (Outputs/Deliverables)**:
  - Phiên mining ổn định sau 3 lần restart liên tiếp, không suy giảm.
  - Nhật ký xác nhận không còn `applications.clocks.*` “dính” sau reset.
  - Bản ghi telemetry “before/after” (clocks, P-state, power, perf cap nếu có).
- **Bước triển khai (Quantity & Order)**:
  1) Thiết lập quy trình **preflight deterministic reset** (không chèn code ở đây, mô tả tác vụ): NVML-first (**[NVML] – thư viện quản lý GPU ở mức driver**), sau đó **[nvidia-smi] (CLI điều khiển/truy vấn GPU)** `-rac`/`-rgc`/`--reset-memory-clocks` tại các điểm reset hiện có; xác minh bằng truy vấn `applications.clocks.*`, `clocks.*`, `pstate`, `power.draw`. (Tham chiếu: report-01, report-02, report-04)
  2) Đăng ký **cleanup on exit** cho GPU trong signal handler của `start_mining.py` (gọi khối restore của `ResourceManager` trước khi thoát). (report-03)
  3) Loại **silent exception**: thay “nuốt lỗi” bằng logging chuẩn (có ngữ cảnh). (report-03)
  4) Thiết lập **readiness gate**: đợi `ResourceManager` sẵn sàng trước khi khởi động GPU processes và/hoặc đăng ký PID. (report-02)
  5) Tạm **nới gate “skip-lock khi SM<800”** trong pha phục hồi, hoặc bật closed-loop ngắn để thoát bẫy xung thấp. (report-04)
- **Các bên liên quan (Stakeholders)**: Chủ sở hữu `resource_control.py`, `start_mining.py`, `resource_manager.py`, `gpu_optimization_orchestrator.py`; vận hành (Ops) giám sát log; QA xác nhận tiêu chí.
- **Tiêu chí đánh giá (Success & Acceptance)**:
  - Hashrate tổng ≥24.96 MH/s trong ≥15′; mỗi GPU ≥12.4 MH/s; đồng đều GPU0≈GPU1 (±2%).
  - `applications.clocks.*` ở trạng thái mặc định (không còn khoá ẩn) sau restart.
  - Không còn lỗi NVML ẩn; không xuất hiện cảnh báo “skip-lock” trong pha phục hồi.
- **Rủi ro & Giảm thiểu**:
  - `-rac`/`--lock-memory-clocks` có thể không hỗ trợ trên một số GPU/driver → fallback `-rgc`/reset-mem, log cảnh báo; không dừng hệ thống. (report-01)
  - Deadlock/timeout do đồng bộ → thời gian chờ có kiểm soát; health checks. (report-03)

### Phase 1 — Chuẩn hoá NVML-first & Nguồn chân lý duy nhất (1–3 ngày)
- **Mục tiêu**: Chuẩn hoá đường dẫn thao tác GPU về **NVML-first** với **[Single Source of Truth]**, chỉ dùng `nvidia-smi` làm **fallback**; loại bỏ chồng chéo thao tác.
- **Inputs**: Code hiện có `resource_control.py`; các điểm set/reset; danh sách thao tác nêu trong report-02/04.
- **Outputs**:
  - Pipeline set/reset tất định: unlock → NVML reset → power default → verify.
  - Bảng ánh xạ thao tác→log (before/after) chuẩn hoá.
- **Bước triển khai**:
  1) Gom mọi set/reset về một pipeline trong `resource_control.py` (NVML-first, `nvidia-smi` chỉ fallback khi NVML thiếu API hoặc trả lỗi xác định).
  2) Chuẩn hoá thứ tự: cancel async → NVML reset (applications clocks) → CLI verify (nếu cần) → apply base (power/clocks an toàn) → confirm.
  3) Thống nhất nơi gọi: các module khác chỉ gọi qua lớp trung tâm (`ResourceManager`→`resource_control.py`).
  4) Giảm/loại điều kiện “skip-lock SM<800” trong pha phục hồi; thay bằng nâng xung dần có bảo vệ.
- **Stakeholders**: Chủ sở hữu `resource_control.py`, `resource_manager.py`; kiến trúc sư hiệu năng.
- **Success & Acceptance**:
  - Không còn “state drift” giữa các lần restart (3/3 vòng đạt cùng chỉ số ±2%).
  - Log cho mỗi thao tác gồm: mục tiêu, trạng thái trước/sau, rc.
- **Rủi ro & Giảm thiểu**: Xung đột NVML↔CLI → quy định NVML-first bắt buộc; thêm kiểm tra rc và degrade gracefully.

### Phase 2 — Quan sát, Telemetry & Xác minh (1–2 ngày)
- **Mục tiêu**: Thiết lập quan sát liên tục để xác minh giả thuyết và phát hiện sớm drift.
- **Inputs**: Hạ tầng logging hiện có; đề xuất câu lệnh truy vấn từ báo cáo.
- **Outputs**: Bộ telemetry định kỳ (P-state, clocks, power, perf cap reasons) và dashboard so sánh trước/sau, theo GPU0/GPU1.
- **Bước triển khai**:
  1) Thu thập `pstate` qua NVML; **[perf cap reasons]** qua `nvidia-smi -q` (nếu sẵn có), theo đề xuất trong báo cáo.
  2) Ghi snapshot trước/ sau mỗi reset/apply/cleanup; cấu trúc log để máy đọc được.
  3) Thiết lập baseline so sánh 10–15′ chạy mining; lặp 3–5 vòng.
- **Stakeholders**: Dev hạ tầng logging; Ops; QA hiệu năng.
- **Success & Acceptance**:
  - Đủ dữ liệu để chứng minh không còn persistent `applications.clocks.*` hoặc để khoanh vùng nếu tái diễn.
  - A/B minh bạch (Phase 3) có dữ liệu đầu vào đầy đủ.

### Phase 3 — Độ tin cậy, Rollback & Điều phối đa tiến trình (2–3 ngày)
- **Mục tiêu**: Tăng độ bền vận hành, phòng ngừa lỗi hệ thống, đảm bảo khôi phục an toàn.
- **Inputs**: Kết quả Phase 1–2; danh sách điểm lỗi tiềm năng.
- **Outputs**: Cơ chế rollback, file-based lock cross-PID, thread-safety; shutdown sequence nâng cao.
- **Bước triển khai**:
  1) **[Rollback] (hoàn nguyên trạng thái – phục hồi về mặc định)** khi xác thực thất bại.
  2) **Cross-PID locking** (khoá ở `/tmp/...`) để tránh xung đột nhiều tiến trình.
  3) **Thread-safety** (lock phạm vi thao tác GPU) và **shutdown sequence** có timeout + health checks.
- **Stakeholders**: Chủ sở hữu `resource_manager.py`, `gpu_optimization_orchestrator.py`, Ops.
- **Success & Acceptance**:
  - Không còn race hoặc xung đột PID trong thử nghiệm nhiều phiên; không treo khi shutdown.
  - Rollback hoạt động chính xác, có audit trail.

---

## 6) Mốc thời gian (Timeline tổng)
- Phase 0: 0–1 ngày (ưu tiên P0, khôi phục tức thì).
- Phase 1: 1–3 ngày (chuẩn hoá pipeline NVML-first, nguồn chân lý duy nhất).
- Phase 2: 1–2 ngày (telemetry & xác minh).
- Phase 3: 2–3 ngày (độ tin cậy & rollback & đa tiến trình).

Tổng: 4–9 ngày làm việc, tuỳ theo mức độ tự động hoá logging và độ phức tạp môi trường.

---

## 7) Kế hoạch A/B Validation & Tiêu chí thành công
- **A1**: Preflight có `-rac` vs **B1**: không `-rac` → so `applications.clocks.*`, hashrate sau 3 restart (nguồn: report-01, report-02).
- **A2**: **[persistence mode]** ON vs OFF (tạm thời) → so P-state/khởi động (nguồn: report-04).
- **A3**: Nới “skip-lock SM<800” vs giữ nguyên → so thời gian phục hồi clocks (nguồn: report-04).
- **A4**: **readiness gate** ON vs OFF → tỷ lệ lỗi cleanup và drift (nguồn: report-02).

**Tiêu chí thành công (global)**:
- Hashrate tổng ≥24.96 MH/s bền ≥15′; mỗi restart (×3) phục hồi về cùng mức ±2%.
- Không còn `applications.clocks.*` sau restore; **[P-State] (trạng thái hiệu năng)** P0–P2 khi mining; **[power draw] (công suất)** 150–200W.
- 0 lỗi NVML “nuốt” trong log; không cảnh báo skip-lock trong pha phục hồi; không drift GPU0/GPU1.

---

## 8) Vai trò/Bên liên quan (Stakeholders)
- **Chủ trì**: **[Meta-Synthesis Lead] (trưởng nhóm tổng hợp giải pháp – điều phối và ra quyết định)**.
- **Chủ sở hữu module**: `resource_control.py`, `resource_manager.py`, `start_mining.py`, `gpu_optimization_orchestrator.py`.
- **Vận hành (Ops)**: Giám sát logs, chạy A/B, thu thập telemetry.
- **QA hiệu năng**: Thiết kế kịch bản xác minh và đo lường kết quả.

---

## 9) Rủi ro & Giảm thiểu (theo Phase)
- Phase 0: Không hỗ trợ `-rac`/`--lock-memory-clocks` → fallback `-rgc`/reset-mem + cảnh báo; deadlock → timeout + health checks.
- Phase 1: Xung đột NVML↔CLI → bắt buộc NVML-first, chỉ CLI làm fallback có log.
- Phase 2: Khối lượng log lớn → điều khiển mức log qua ENV; lưu trữ luân phiên.
- Phase 3: Deadlock đa tiến trình → file lock + watchdog; rollback sai mục tiêu → audit trail + xác thực trước khi áp dụng.

---

## 10) Yêu cầu đầu vào/đầu ra chi tiết theo Phase

### Phase 0 – Inputs
- Bản build `api-models:latest` (Docker) và môi trường `/app` hiện tại.
- Nhật ký vận hành gần nhất (stealth_inference_cuda.log, mining_debug.log) để đối chiếu.
### Phase 0 – Outputs
- Phiên mining ổn định; tập nhật ký “before/after” mỗi reset/apply/cleanup; biên bản A/B A1–A4.

### Phase 1 – Inputs
- Danh sách tất cả điểm set/reset trong `resource_control.py` và lời gọi từ module khác.
### Phase 1 – Outputs
- Pipeline NVML-first, bảng ánh xạ thao tác→log, tài liệu hướng dẫn gọi một lối.

### Phase 2 – Inputs
- Hạ tầng logging, danh mục trường telemetry (pstate, clocks.*, power, perf caps).
### Phase 2 – Outputs
- Bộ telemetry định kỳ và báo cáo so sánh (GPU0/GPU1; trước/sau; 3 lần restart).

### Phase 3 – Inputs
- Danh mục rủi ro còn mở; nhu cầu độ tin cậy vận hành.
### Phase 3 – Outputs
- Cơ chế rollback; cross-PID lock; thread-safety; shutdown sequence nâng cao.

---

## 11) Quy trình kiểm chứng lặp (per Phase)
- Trước khi bắt đầu: snapshot trạng thái GPU (NVML + `nvidia-smi` theo mẫu báo cáo).
- Sau mỗi bước chính: ghi lại before/after; so sánh với baseline.
- Kết thúc Phase: chạy bài test mining 10–15′; lặp 3–5 vòng restart; so sánh GPU0/GPU1.

---

## 12) Phụ lục – Trích dẫn bằng chứng (verbatim)
```65:79:app/reports/report-01.md
Thiếu reset Application Clocks `-rac` ... vắng `nvidia-smi -rac` ...
```
```90:100:app/reports/report-02.md
-rgc → --reset-memory-clocks → nvmlDeviceResetApplicationsClocks(handle)
```
```119:126:app/reports/report-03.md
# ❌ MISSING: GPU state restoration!
```
```56:59:app/reports/report-04.md
-pm 1 bật persistence mode trong setup
```

---

### 13) Ghi chú thuật ngữ
- **[NVML] (thư viện quản lý GPU ở mức driver)**
- **[nvidia-smi] (CLI điều khiển/truy vấn GPU – công cụ dòng lệnh NVIDIA)**
- **[application clocks] (khóa xung ứng dụng – cố định xung core/mem)**
- **[persistence mode] (chế độ bền bỉ – giữ context driver sống để tránh reset)**
- **[perf cap reasons] (lý do giới hạn hiệu năng: Pwr, Thrm, VRel, VOp, Util)**
- **[preflight reset] (reset trước khi chạy – hoàn nguyên trạng thái GPU về mặc định)**
- **[cleanup on exit] (hoàn nguyên cấu hình khi thoát)**
- **[Single Source of Truth] (nguồn sự thật duy nhất – điểm tập trung thao tác/state)**
- **[race condition] (điều kiện đua – cạnh tranh thời điểm/luồng)**
- **[rollback] (hoàn nguyên trạng thái – phục hồi về mặc định)**


