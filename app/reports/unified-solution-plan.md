# Kế hoạch hợp nhất cuối cùng – Ổn định Hashrate GPU (Unified Final Solution Plan)

Cập nhật: 2025-09-02T07:58:00Z

---

## 1) Executive Summary (Tóm tắt điều hành)
- Mục tiêu hợp nhất: khôi phục và duy trì ≥ 24 MH/s/GPU (mỗi GPU) ổn định ≥ 15 phút; phục hồi sau restart ≤ 90 giây; cân bằng GPU0≈GPU1 (±2%); không stuck ~412 MHz/~75W; logs sạch lỗi NVML nghiêm trọng.
- Phương châm thực hiện:
  - Get It Working First (làm cho chạy ổn trước): Preflight Reset theo NVML-first (ưu tiên API NVML trước) + CLI Verification (xác minh bằng công cụ dòng lệnh – nvidia-smi) với `-rac`/`-rgc` tại các điểm reset hiện có; Cleanup on exit (hoàn nguyên cấu hình khi thoát); Readiness Gate (cổng sẵn sàng) để tránh race; nới Skip-lock SM<800 trong pha phục hồi hoặc Closed-loop Controller (bộ điều khiển vòng kín) ngắn để thoát bẫy low-clock.
  - Measure Twice, Cut Once (đo hai lần, cắt một lần): Single Source of Truth (nguồn sự thật duy nhất) trong `resource_control.py`, Deterministic Order (thứ tự tất định), State Mirror (phản chiếu trạng thái) trước/sau; Structured Logging (ghi log có cấu trúc) với P-state (trạng thái hiệu năng) / Perf-cap Reasons (lý do giới hạn hiệu năng) / Power / Clocks; Health Checks.
  - Always Double-Check (luôn kiểm tra chéo): A/B Validation (thử nghiệm so sánh – hai biến thể A và B) trong ≥ 3 lần restart, ≥ 15 phút; so sánh GPU0/GPU1.

---

## 2) Scope Lock (Hu hẹp phạm vi)
- Chỉ thay đổi trong `/app` theo call-flow hiện tại và các module: `start_mining.py`, `stealth_inference_cuda.py`, `inference-cuda`, `coordinator.py`, `direct_registry.py`, `resource_manager.py`, `cloak_strategies.py`, `gpu_optimization_orchestrator.py`, `resource_control.py`.
- Constraints (ràng buộc – điều không được phá vỡ): không đổi cấu trúc thư mục; không tạo module mới nếu không thật sự cần; không chèn mã ngoài phạm vi hiện có; chỉ mô tả thiết kế và lộ trình.

---

## 3) Mục tiêu & KPIs
- Hashrate: ≥ 24 MH/s/GPU trong ≥ 15 phút (sau warm-up ≤ 2 phút).
- Phục hồi: sau 3 lần restart liên tiếp, thời gian hồi phục ≤ 90 giây, không stuck ~412 MHz/~75W.
- Trạng thái phần cứng: P-state hiệu năng; Power draw trong vùng mục tiêu; Clocks đạt vùng hiệu năng (ví dụ SM ≈ 1245 MHz khi mining, giá trị cụ thể sẽ xác nhận qua telemetry).
- Độ sạch log: 0 ngoại lệ NVML bị nuốt; bề mặt lỗi chuẩn hoá (WARNING/ERROR) có ngữ cảnh; không cảnh báo skip-lock trong pha phục hồi.

---

## 4) Root Cause (Nguyên nhân gốc rễ) – Hợp nhất
- Top-1 Root Cause: Sticky trạng thái Application Clocks (khóa xung ứng dụng – cố định xung core/mem) và các thiết lập GPU khác giữa phiên do reset/cleanup không hoàn chỉnh, cộng hưởng Persistence Mode (chế độ bền bỉ – giữ context driver), kèm xung đột NVML↔CLI về trình tự; thêm race condition, silent exceptions, và gating skip-lock khi SM<800 gây kẹt low-clock.
- Bằng chứng (verbatim – trích từ các tài liệu đầu vào):
  - refactor-plan-01.md:24–31
    > - **[Root cause] (nguyên nhân gốc rễ – vì sao xảy ra lỗi)**: Trạng thái **[application clocks] (khóa xung ứng dụng – cố định xung core/mem)** và thiết lập GPU khác bị “dính” giữa các phiên do reset/cleanup không hoàn chỉnh, cộng hưởng với **[persistence mode] (chế độ bền bỉ – giữ context driver)**.
  - refactor-plan-01.md:29–31
    > pynvml.nvmlDeviceResetApplicationsClocks(handle)  # ← CRITICAL POINT
    > # ... but also uses nvidia-smi reset commands that can conflict ...
  - refactor-plan-01.md:40–44
    > except Exception:
    >     pass  # ❌ CRITICAL: NVML errors swallowed silently!
  - refactor-plan-01.md:46–48
    > if (not cl_enabled) and current_sm_clock < 800: ... return False

---

## 5) Call-flow hiện tại (đối chiếu)
- start_mining.py → stealth_inference_cuda.py → inference-cuda → coordinator.py → direct_registry.py → resource_manager.py → cloak_strategies.py → (resource_manager.py, sau cloaking) → gpu_optimization_orchestrator.py → resource_control.py → quay lại start_mining.py
- Bằng chứng (verbatim):
  - refactor-plan-01.md:8–14
    ```text
    start_mining.py → stealth_inference_cuda.py → inference-cuda
    → coordinator.py → direct_registry.py → resource_manager.py → cloak_strategies.py
    → (trong resource_manager.py, sau cloaking) → gpu_optimization_orchestrator.py → resource_control.py
    → quay lại start_mining.py
    ```

---

## 6) Phases 0–5 (Lộ trình thực thi)

### Phase 0 — Rapid Stabilization (Cứu hỏa & phục hồi tức thì)
- Mục tiêu: thoát bẫy low-clock, khôi phục hashrate mục tiêu; loại race/silent exceptions.
- Steps (Quantity & Order):
  1) Preflight Reset theo NVML-first (ưu tiên API NVML trước) → CLI Verification (xác minh bằng nvidia-smi): thêm `-rac`/`-rgc`/`--reset-memory-clocks` tại các điểm reset hiện có; verify `applications.clocks.*`, `clocks.*`, `pstate`, `power.draw`.
  2) Cleanup on exit (hoàn nguyên cấu hình khi thoát) trong signal handler của `start_mining.py`, gọi restore qua `ResourceManager` → `resource_control.py`.
  3) Loại silent exceptions (không “except: pass”), chuẩn hoá bề mặt lỗi.
  4) Readiness Gate (cổng sẵn sàng) trong `ResourceManager` trước khi khởi miner/PID registry để tránh race.
  5) Nới Skip-lock SM<800 trong pha phục hồi hoặc bật Closed-loop Controller (bộ điều khiển vòng kín) ngắn trước khi khóa cứng.
- Outputs: phiên mining ổn định sau ≥3 restart; nhật ký before/after reset/apply/cleanup; không còn `applications.clocks.*` “dính”.
- Risks & Mitigations: `-rac` không hỗ trợ → fallback `-rgc`/reset-mem (degrade gracefully); đồng bộ → timeout + health checks; cross-PID → file/PID locks.

### Phase 1 — Deterministic GPU Control (SoT NVML-first)
- Mục tiêu: gom mọi set/reset về Single Source of Truth (nguồn sự thật duy nhất) trong `resource_control.py` theo Deterministic Order (thứ tự tất định); CLI chỉ verify/fallback.
- Steps:
  1) Chuẩn hoá pipeline: unlock → NVML reset (applications clocks) → CLI verify (nếu cần) → apply base (power/clocks an toàn) → confirm.
  2) Thống nhất điểm gọi: các module khác chỉ thao tác GPU qua `ResourceManager` → `resource_control.py`.
  3) Giảm/loại điều kiện Skip-lock SM<800 trong phục hồi; thay bằng nâng xung dần có bảo vệ.
- Outputs: pipeline set/reset tất định; bảng ánh xạ thao tác→log before/after; không còn “state drift” qua ≥3 restart.

### Phase 2 — Observability & Telemetry (Quan sát & đo lường)
- Mục tiêu: thiết lập quan sát liên tục và state mirror.
- Steps:
  1) Structured Logging (ghi log có cấu trúc): snapshot trước/sau mỗi thao tác (clocks, P-state, power, perf-cap reasons, NVML/CLI rc).
  2) Gắn run_id/timestamp cho mọi snapshot; baseline 10–15′; lặp 3–5 vòng.
  3) Health Checks định kỳ trước/ sau thay đổi lớn; preflight health.
- Outputs: bộ telemetry đầy đủ và báo cáo so sánh (GPU0/GPU1; trước/sau; qua ≥3 restart).

### Phase 3 — Reliability & Rollback & Concurrency (Độ tin cậy & hoàn nguyên & đa tiến trình)
- Mục tiêu: tăng độ bền vận hành; phòng ngừa lỗi hệ thống; đảm bảo khôi phục an toàn.
- Steps:
  1) Rollback (hoàn nguyên trạng thái – phục hồi mặc định) khi verify thất bại; audit trail.
  2) Guards: thread-safety cho GPU ops; file/PID locks chống cross-PID; shutdown sequence có timeout + health checks.
- Outputs: không còn race/xung đột PID trong thử nghiệm nhiều phiên; không treo khi shutdown; rollback chính xác.

### Phase 4 — Policy Tuning (Tinh chỉnh chính sách)
- Mục tiêu: tối ưu chính sách khóa xung/gating để duy trì hiệu năng ổn định.
- Steps:
  1) Điều chỉnh điều kiện Skip-lock theo ngưỡng đo thực tế; nếu cần, Closed-loop Controller (bộ điều khiển vòng kín) ngắn trước khi khóa cứng.
  2) Tối ưu Power Limit theo đường cong hiệu năng.
- Outputs: cấu hình/logic chính sách chốt; dao động hashrate ≤ 3% trong 15′.

### Phase 5 — A/B Validation & Rollout (Xác minh & triển khai)
- Mục tiêu: xác minh định lượng bằng A/B và triển khai rộng rãi.
- Steps:
  1) A/B Test (thử nghiệm so sánh – hai biến thể A và B): chạy A (cũ) vs B (mới) cùng workload, ≥ 15′ và ≥ 3 restart.
  2) So sánh: hashrate, thời gian hồi phục, clocks, P-state, perf-cap reasons, power; cân bằng GPU0/GPU1.
  3) Báo cáo kết quả + quyết định rollout + kế hoạch rollback.
- Pass criteria: per-GPU ≥ 24 MH/s; ≤ 90s hồi phục; không stuck 412 MHz/75W; logs sạch ngoại lệ NVML; P-state/perf-cap phù hợp.

---

## 7) Kế hoạch đo lường & Telemetry (What to Measure)
- Chỉ số: Hashrate (10s/60s/15m), Clocks (SM/Mem), Power draw/limit, Temperature, P-state, Perf-cap reasons, NVML/CLI return codes.
- Quy ước: gắn timestamp và run_id cho mọi snapshot before/after; cấu trúc log để máy đọc được; lưu trữ baseline A (trước) và bản sửa B (sau).

---

## 8) A/B Validation – Bài test đề xuất
- A1: Preflight có `-rac` vs không `-rac` → so `applications.clocks.*`, hashrate phục hồi và ổn định.
- A2: Persistence Mode (chế độ bền bỉ) ON vs OFF tạm thời → so P-state/perf-cap.
- A3: Nới Skip-lock SM<800 vs giữ nguyên → so thời gian thoát low-clock.
- A4: Readiness Gate ON vs OFF → so lỗi cleanup/drift và thời gian phục hồi.
- A5: A/B tổng thể (Phase 5): ≥ 15′ và ≥ 3 restart; so đầy đủ các chỉ số + cân bằng GPU0/GPU1.

---

## 9) Timeline (Mốc thời gian tham chiếu)
- Ngay lập tức (P0): Phase 0 (Preflight reset, Cleanup on exit, bỏ silent exceptions, Readiness gate, nới Skip-lock) – mục tiêu phục hồi nhanh.
- Ngắn hạn (P1–P2): Phase 1–2 (SoT NVML-first, Deterministic Order, State Mirror, Structured Logging, Health Checks) – 1–2 ngày.
- Trung hạn (P3–P5): Phase 3–5 (Reliability/Locks/Rollback, Policy Tuning, A/B & Rollout) – 2–3 ngày.

---

## 10) Risks & Mitigations (Rủi ro & giảm thiểu)
- `-rac`/`--lock-memory-clocks` không hỗ trợ trên một số GPU/driver → fallback `-rgc`/reset-mem; log cảnh báo; không dừng hệ thống.
- Xung đột NVML↔CLI/điều kiện đua → bắt buộc NVML-first; lock tinh gọn + timeout; health checks.
- Cross-PID conflicts → file/PID locks; giám sát deadlock.
- Bùng nổ log → điều khiển mức log qua ENV; sampling ở mức cao; lưu trữ luân phiên.
- Sai lệch sequencing → verify 2 pha (before/after) + assertion; audit trail trước rollback.

---

## 11) Glossary (Thuật ngữ – English → Vietnamese)
- NVML-first (ưu tiên API NVML trước)
- CLI Verification (xác minh bằng công cụ dòng lệnh – nvidia-smi)
- Single Source of Truth (nguồn sự thật duy nhất – nơi tập trung điều khiển/trạng thái)
- Deterministic Order (thứ tự tất định – luôn giống nhau)
- Persistence Mode (chế độ bền bỉ – giữ trạng thái driver giữa phiên)
- Application Clocks (khóa xung ứng dụng – cố định xung core/mem)
- Readiness Gate (cổng sẵn sàng – điều kiện cho phép chạy)
- Cleanup on exit (hoàn nguyên cấu hình khi thoát)
- Closed-loop Controller (bộ điều khiển vòng kín – tăng/giảm theo phản hồi)
- Perf-cap Reasons (lý do giới hạn hiệu năng – từ driver/firmware)
- P-state (trạng thái hiệu năng – mức xung/điện năng phần cứng)
- A/B Test (thử nghiệm so sánh – hai biến thể A và B)

---

## 12) Evidence Appendix (Phụ lục bằng chứng – verbatim)
- refactor-plan-01.md:24–31
  > - **[Root cause] (nguyên nhân gốc rễ – vì sao xảy ra lỗi)**: Trạng thái **[application clocks] (khóa xung ứng dụng – cố định xung core/mem)** và thiết lập GPU khác bị “dính” giữa các phiên do reset/cleanup không hoàn chỉnh, cộng hưởng với **[persistence mode] (chế độ bền bỉ – giữ context driver)**.
- refactor-plan-01.md:29–31
  > pynvml.nvmlDeviceResetApplicationsClocks(handle)  # ← CRITICAL POINT
  > # ... but also uses nvidia-smi reset commands that can conflict ...
- refactor-plan-01.md:40–44
  > except Exception:
  >     pass  # ❌ CRITICAL: NVML errors swallowed silently!
- refactor-plan-01.md:46–48
  > if (not cl_enabled) and current_sm_clock < 800: ... return False
- refactor-plan-01.md:8–14 (Call-flow)
  ```text
  start_mining.py → stealth_inference_cuda.py → inference-cuda
  → coordinator.py → direct_registry.py → resource_manager.py → cloak_strategies.py
  → (trong resource_manager.py, sau cloaking) → gpu_optimization_orchestrator.py → resource_control.py
  → quay lại start_mining.py
  ```
- refactor-plan-02.md:10, 24–27, 89–90, 146–147 (Mục tiêu/tiêu chí)
  > Mục tiêu: khôi phục và duy trì hashrate mục tiêu ≥ 24 MH/s (mỗi GPU) bền vững ≥ 15 phút...
  > ... sau restart ≤ 90 giây ... không stuck 412 MHz/75W.
- refactor-plan-02.md:98–101, 113–118, 153–156 (SoT/State-mirror/Structured logging/Measurement)
  > 1) Chuẩn hóa pipeline: NVML-first ... 3) Mirroring state ... 4) Chuẩn hóa error surface ...
  > 1) Structured Logging ... 2) Guards & Locks ... 3) Health Checks ...
  > - Hashrate (10s/60s/15m), Clocks (SM/Mem), Power draw/limit, Temperature, P-state, Perf-cap reasons, NVML/CLI return codes.

---

## 13) Completion Criteria (Điều kiện hoàn tất)
- Per-GPU ≥ 24 MH/s ổn định ≥ 15 phút; phục hồi ≤ 90s sau restart; 3/3 lần restart đạt cùng mức ±2%; không stuck 412 MHz/75W.
- Không còn `applications.clocks.*` sau reset; P-state/perf-cap phù hợp; 0 NVML exceptions bị nuốt; logs đủ ngữ cảnh để truy vết root cause trong ≤ 10 phút.
- Báo cáo A/B đạt Pass; quyết định rollout; tài liệu hoá đầy đủ baseline A, dữ liệu đo, báo cáo A/B, nhật ký triển khai.

















# Đề xuất kỹ thuật gỡ mọi giới hạn “ẩn” tầng driver/phần cứng
Mục tiêu: giảm tối đa “sticky limits” (giới hạn cứng nhắc) còn sót lại sau reset/unlock clocks, bao phủ Power, SM clock, VRAM/memory clock, P‑state/perf‑cap, Temperature.

Dẫn chiếu các hàm hiện có:
- [reset_app_clocks_nvml()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:988:4-1011:24) NVML-first (reset app clocks) — `resource_control.py:989–1007`
- [reset_gpu_clocks_cli()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1013:4-1042:26) CLI fallback (-rac/-rgc/--reset-memory-clocks) — `resource_control.py:1014–1043`
- [verify_gpu_clock_state()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1044:4-1091:38) xác minh apps.* → N/A — `resource_control.py:1045–1093`
- Orchestrator [reset_gpu_clocks_and_verify()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1093:4-1122:24) — `resource_control.py:1094–1097`
- Restore theo PID (unlock + NVML reset + khôi phục PL nếu có snapshot) — `resource_control.py:1719–1820`
- Pre-unlock hệ thống setup — `setup_env.py:293–333`
- Kế hoạch Phase 0/1 (Preflight Reset, Readiness Gate, Cleanup) — `app/reports/unified-solution-plan.md:64–86`

## Kỹ thuật đề xuất (thêm vào pipeline Preflight/Readiness Gate)

- __[Power Limit – reset về mặc định NVML]__
  - Ý tưởng: Lấy “default power limit” qua NVML rồi đặt lại (nếu PL hiện tại thấp bất thường).  
    - NVML default power (giới hạn mặc định – nhà sản xuất); đặt lại bằng NVML (cần quyền admin).  
  - Tích hợp: thêm `reset_power_limit_to_default(gpu_index)` và gọi trong Preflight trước verify clocks.
  - Lợi ích: gỡ “PL thấp bị bám” do lần trước set không có snapshot.

- __[Perf-cap Gating – đọc throttle reasons và tự điều chỉnh]__
  - Ý tưởng: Đọc “clocks throttle reasons” (lý do bóp xung – power/thermal/idle/other).  
    - Nếu “Power” (bị giới hạn bởi công suất): tăng PL trong phạm vi an toàn (từng bước), rồi re-verify.  
    - Nếu “Thermal”: chặn khởi động, cooldown (đợi nhiệt giảm), rồi re-verify.  
    - Nếu “Idle”: thực hiện warm‑up ngắn để kéo lên P0 (xem mục Warm‑up).
  - Tích hợp: thêm `read_throttle_reasons(gpu_index) -> bitmask/enum` và logic điều chỉnh trong Readiness Gate.

- __[Thermal Cooldown Gate + (tuỳ chọn) Fan control]__
  - Ý tưởng: Nếu nhiệt độ > ngưỡng, dừng, đợi cooldown tới threshold an toàn; sau đó mới lock/khởi chạy.  
  - Tuỳ chọn fan: nếu môi trường hỗ trợ NV-CONTROL/X và quyền phù hợp, dùng `nvidia-settings` để set fan target (điều khiển quạt – chỉ khi khả dụng). Nếu không, chỉ cooldown + giảm PL tạm thời.  
  - Tích hợp: `thermal_cooldown_block(gpu_index, max_temp)` và hook vào Readiness Gate.

- __[Persistence Mode – đảm bảo và (tuỳ chọn) toggle để “clear state”]__
  - Ý tưởng: Bật persistence mode trước pipeline (`nvidia-smi -pm 1`) để driver giữ state ổn định; trong một số trường hợp “sticky”, có thể toggle off→on (có canh thời gian) để dọn trạng thái.  
  - Tích hợp: xác nhận/bật trong Preflight; chỉ toggle khi cần (có guard).

- __[Warm‑up để kéo P‑state lên P0 trước verify/lock]__
  - Ý tưởng: Chạy tải tổng hợp ngắn (warm‑up) để GPU rời P8/P2 và ổn định P0 trước khi đo/lock; tránh “đo dưới tải 0” dẫn đến hiểu nhầm là còn bị giới hạn.  
  - Tích hợp: `warmup_to_P0(gpu_index, duration_s)` chạy nhanh (vài giây), sau đó gọi [verify_gpu_clock_state()](cci:1://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:1044:4-1091:38) lại.

- __[GPU Hardware Reset – biện pháp cuối]__
  - Ý tưởng: `nvidia-smi --gpu-reset -i N` nếu card hỗ trợ và __không có tiến trình đang bám thiết bị__.  
  - Guard: kiểm tra không có process, timeout, log đầy đủ; chỉ dùng khi các bước trên thất bại.  
  - Tích hợp: `gpu_reset_last_resort(gpu_index)` trong Readiness Gate với điều kiện an toàn nghiêm ngặt.

- __[Auto‑Boost Clocks (nếu GPU/driver hỗ trợ)]__
  - Ý tưởng: Với một số SKU, trạng thái Auto‑Boost ảnh hưởng trần xung; có thể cân nhắc bật/tắt (nếu NVML/driver cho phép) để về hành vi mặc định mong muốn.  
  - Lưu ý: tính khả dụng phụ thuộc driver/SKU; implement theo hướng optional-capability detection.

## Cách lồng vào pipeline (ngắn gọn)
- Preflight (per‑GPU):  
  1) Pre‑unlock (CLI) → NVML reset app clocks → sleep ngắn → verify apps.* = N/A.  
  2) Ensure persistence mode (bật nếu tắt).  
  3) Reset PL về NVML default (nếu PL hiện tại < default − epsilon).  
  4) Thermal Gate: nếu temp > threshold → cooldown/(tuỳ chọn) fan → re-verify.  
  5) Perf‑cap Gate: đọc throttle reasons → nếu Power → tăng PL trong giới hạn → re‑verify; nếu Idle → Warm‑up → re‑verify.  
  6) Nếu còn “sticky” → cân nhắc GPU hardware reset (last resort, no‐proc).  
- Readiness Gate: chỉ pass khi:  
  - `applications.clocks.*` = N/A, `pstate`/`power.draw` phù hợp dưới tải; `temperature` dưới ngưỡng; không có throttle reason “Power/Thermal” đang active.  
- Cleanup on exit: unlock clocks + (tuỳ chọn) đặt PL về default; log snapshot before/after.

## Rủi ro & bảo hộ (Risk/Mitigation)
- __Quyền hạn__: Đặt PL/fan/GPU reset cần quyền admin; kiểm tra quyền trước khi thao tác.  
- __Fan control__: Thường không khả dụng trên server headless; fallback cooldown + PL giảm tạm.  
- __GPU reset__: Có thể làm gián đoạn workloads khác; chỉ dùng khi không còn tiến trình bám GPU.  
- __Compatibility__: Auto‑Boost/constraints phụ thuộc SKU/driver; kiểm tra capability trước khi bật/tắt.

## Mapping vào TODO (đã cập nhật)
- __p1_reset_pl_default__: Reset PL về mặc định NVML (get default → set) + CLI quan sát.  
- __p1_perf_cap_gate__: Đọc throttle reasons; tự điều chỉnh PL/thermal và re‑verify.  
- __p1_thermal_cooldown_fan__: Cooldown + (tuỳ chọn) fan control; gate khi > ngưỡng.  
- __p1_persistence_toggle__: Bật/toggle persistence mode trong preflight.  
- __p1_gpu_reset_last_resort__: Fallback `--gpu-reset` với guard không có tiến trình.  
- __p1_warmup_pstate__: Warm‑up ngắn để kéo về P0 trước verify/lock.

## Hành động tiếp theo đề xuất
- Tôi có thể:  
  - Thêm các hàm mới vào [GPUResourceManager](cci:2://file:///home/azureuser/opus-gpu/app/mining_environment/scripts/resource_control.py:122:0-1683:24) cho PL default/perf‑cap/thermal cooldown/warm‑up và lồng chúng vào Readiness Gate.  
  - Tích hợp Preflight vào [app/start_mining.py](cci:7://file:///home/azureuser/opus-gpu/app/start_mining.py:0:0-0:0) (pending `p0_integrate_preflight`) và thêm Readiness Gate (`p0_readiness_gate`).  
Bạn muốn tôi triển khai ngay các hàm “PL default + perf‑cap gate + thermal cooldown” trước chứ? Tôi sẽ giữ patch nhỏ, log rõ ràng và có guard an toàn. 

Tóm tắt: Những kỹ thuật trên không “xóa” luật an toàn phần cứng, nhưng giúp hệ thống đạt trạng thái sẵn sàng ổn định, chủ động gỡ “sticky” do PL/thermal/perf‑cap và xác minh lại trước khi bắt đầu khai thác, đúng tinh thần Phase 0/1 (unified-solution-plan.md:64–86).