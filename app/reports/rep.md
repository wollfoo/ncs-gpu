
## 5) Giải pháp đề xuất (theo Pha 0–5)

- __Phase 0 – Rapid Stabilization__ (cứu hỏa & phục hồi tức thì)  
  - Mục tiêu: thoát bẫy low-clock, phục hồi hashrate; loại race/silent exceptions [unified-solution-plan.md:61–68].  
  - Bước chính: NVML-first reset → CLI verify với `-rac`/`-rgc`/`--reset-memory-clocks`; cleanup on exit; Readiness Gate; nới skip-lock SM<800 hoặc dùng Closed-loop Controller (bộ điều khiển vòng kín) ngắn [unified-solution-plan.md:64–69].  
  - Rủi ro/giảm thiểu: nếu `-rac` không hỗ trợ, fallback `-rgc`/reset-mem; thêm timeout, health checks, file/PID locks [unified-solution-plan.md:70].

- __Phase 1 – Deterministic GPU Control__ (SoT NVML-first)  
  - Mục tiêu: gom mọi set/reset về `resource_control.py`, thứ tự tất định; CLI chỉ verify/fallback [unified-solution-plan.md:72–78].  
  - Pipeline: unlock → NVML reset (application clocks) → CLI verify (nếu cần) → apply base (power/clocks an toàn) → confirm [unified-solution-plan.md:75].

- __Phase 2 – Observability & Telemetry__  
  - Mục tiêu: structured logging + state mirror [unified-solution-plan.md:80–86].  
  - Bước: snapshot before/after (clocks, P-state, power, perf-cap reasons, NVML/CLI rc); gắn run_id/timestamp; health checks [unified-solution-plan.md:83–86].

- __Phase 3 – Reliability & Rollback & Concurrency__  
  - Mục tiêu: tăng độ bền, hoàn nguyên an toàn, chống race/cross-PID [unified-solution-plan.md:88–93].  
  - Bước: rollback khi verify fail; thread-safety cho GPU ops; file/PID locks; shutdown có timeout + health checks [unified-solution-plan.md:91–93].

- __Phase 4 – Policy Tuning__  
  - Mục tiêu: tinh chỉnh skip-lock/closed-loop; tối ưu power limit [unified-solution-plan.md:95–100].  
  - Kết quả: dao động hashrate ≤ 3% trong 15′ [unified-solution-plan.md:100].

- __Phase 5 – A/B Validation & Rollout__  
  - Mục tiêu: xác minh định lượng rồi triển khai [unified-solution-plan.md:102–109].  
  - Bước: A/B ≥ 15′ và ≥ 3 restart; so hashrate, thời gian hồi phục, clocks, P-state, perf-cap, power; cân bằng GPU0/GPU1; báo cáo + quyết định rollout + rollback plan [unified-solution-plan.md:105–107].  
  - Pass criteria: ≥ 24 MH/s; ≤ 90s; không stuck 412/75W; logs sạch; P-state đúng [unified-solution-plan.md:108–109].

## 6) Kế hoạch đo lường & Telemetry
- __Chỉ số__: Hashrate (10s/60s/15m), SM/Mem clocks, Power draw/limit, Temperature, P-state, Perf-cap reasons, NVML/CLI return codes [unified-solution-plan.md:112–114].  
- __Quy ước__: gắn timestamp + run_id cho mọi snapshot before/after; log có cấu trúc; lưu baseline A (trước) và bản sửa B (sau) [unified-solution-plan.md:114–115].

## 7) A/B Validation – Bài test đề xuất
- __A1__: Preflight có `-rac` vs không → so `applications.clocks.*`, hashrate phục hồi/ổn định [unified-solution-plan.md:119].  
- __A2__: Persistence Mode ON vs OFF tạm thời → so P-state/perf-cap [unified-solution-plan.md:120].  
- __A3__: Nới Skip-lock SM<800 vs giữ nguyên → so thời gian thoát low-clock [unified-solution-plan.md:121].  
- __A4__: Readiness Gate ON vs OFF → so lỗi cleanup/drift và thời gian phục hồi [unified-solution-plan.md:122].  
- __A5__: A/B tổng thể (Phase 5) ≥ 15′ và ≥ 3 restart; so toàn bộ chỉ số + cân bằng GPU0/GPU1 [unified-solution-plan.md:123].

## 8) Timeline triển khai (mốc tham chiếu)
- __Ngay lập tức (P0)__: Phase 0 – phục hồi nhanh [unified-solution-plan.md:127–129].  
- __Ngắn hạn (P1–P2)__: SoT NVML-first, Deterministic Order, State Mirror, Structured Logging, Health Checks (1–2 ngày) [unified-solution-plan.md:129].  
- __Trung hạn (P3–P5)__: Reliability/Locks/Rollback, Policy Tuning, A/B & Rollout (2–3 ngày) [unified-solution-plan.md:130].

## 9) Rủi ro & Giảm thiểu
- __Thiếu hỗ trợ `-rac`/`--lock-memory-clocks`__: fallback `-rgc`/reset-mem; log cảnh báo; không dừng hệ thống [unified-solution-plan.md:134–135].  
- __Xung đột NVML↔CLI / race__: bắt buộc NVML-first; lock tinh gọn + timeout; health checks [unified-solution-plan.md:136].  
- __Cross-PID conflicts__: file/PID locks; giám sát deadlock [unified-solution-plan.md:137].  
- __Bùng nổ log__: điều khiển mức log qua ENV; sampling; lưu trữ luân phiên [unified-solution-plan.md:138].  
- __Sai lệch sequencing__: verify 2 pha (before/after) + assertion; audit trail trước rollback [unified-solution-plan.md:139].

## 10) Điều kiện hoàn tất (Completion Criteria)
- __Định lượng__: Per-GPU ≥ 24 MH/s ổn định ≥ 15′; phục hồi ≤ 90s; 3/3 restart đạt cùng mức ±2%; không stuck 412/75W [unified-solution-plan.md:187–188].  
- __Chất lượng vận hành__: Không còn `applications.clocks.*` sau reset; P-state/perf-cap phù hợp; 0 NVML exceptions bị nuốt; logs đủ ngữ cảnh để truy vết trong ≤ 10 phút [unified-solution-plan.md:189].  
- __Quy trình__: Báo cáo A/B pass; quyết định rollout; tài liệu hoá đầy đủ baseline A, dữ liệu đo, báo cáo A/B, nhật ký triển khai [unified-solution-plan.md:190].

---

## Ví dụ minh họa (tham khảo triển khai – phù hợp nội dung kế hoạch)

- __Ví dụ 1 – Preflight Reset pipeline__  
  Dựa trên Phase 0/1 (NVML-first + CLI verification) [unified-solution-plan.md:64–66, 75]:
  ```bash
  # NVML-first (khung ý tưởng – không phải code sẵn có trong repo)
  # 1) Unlock/Reset application clocks
  nvidia-smi -rac || true          # Reset application clocks (CLI fallback nếu cần)
  nvidia-smi --reset-memory-clocks || true

  # 2) Apply base safe settings (ví dụ: power limit và clocks an toàn)
  # (giá trị cụ thể điều chỉnh theo telemetry thực tế)
  # 3) Verify (CLI Verification)
  nvidia-smi --query-gpu=clocks.applications.graphics,clocks.current.graphics,pstate,power.draw --format=csv
  ```
  Ghi chú: Nếu `-rac` không hỗ trợ, fallback `-rgc`/reset-mem như rủi ro đã nêu [unified-solution-plan.md:70, 134–135].

- __Ví dụ 2 – Structured Logging snapshot__  
  Theo mục Telemetry [unified-solution-plan.md:83–86, 112–115]:
  ```json
  {
    "run_id": "2025-09-02T08:00Z#1",
    "gpu": 0,
    "phase": "preflight_before",
    "clocks": {"sm_mhz": 405, "mem_mhz": 405},
    "pstate": "P8",
    "power": {"draw_w": 75, "limit_w": 120},
    "perf_cap_reasons": ["Utilization"],
    "nvml_rc": 0,
    "cli_rc": 0,
    "timestamp": "2025-09-02T08:00:15Z"
  }
  ```
  Mục tiêu: so sánh before/after, A vs B, GPU0 vs GPU1.

- __Ví dụ 3 – Ma trận A/B__  
  Theo Phase 5 và mục 8 [unified-solution-plan.md:102–109, 118–124]:
  ```
  Biến thể A (hiện trạng): không -rac; skip-lock SM<800 giữ nguyên; không Readiness Gate
  Biến thể B (đề xuất): có -rac; nới skip-lock SM<800; bật Readiness Gate

  Đo lường: hashrate(10s/60s/15m), t_hồi_phục(s), SM/Mem clocks, P-state, perf-cap, power, cân bằng GPU0/GPU1
  Tiêu chí pass: ≥24 MH/s; ≤90s; không stuck 412/75W; logs sạch; P-state/perf-cap đúng
  ```

---

## Kết luận ngắn gọn
- Kế hoạch đã khóa mục tiêu/KPIs, phạm vi, nguyên nhân gốc, chuỗi call-flow, lộ trình 6 pha, đo lường, A/B, timeline, rủi ro và tiêu chí hoàn tất với trích dẫn rõ ràng.  
- Trọng tâm kỹ thuật: NVML-first, Single Source of Truth tại `resource_control.py`, thứ tự tất định, telemetry đầy đủ, guards/concurrency, rollback, và xác minh A/B.  
- Bước tiếp theo hợp lý: thực thi Phase 0 ngay, sau đó Phase 1–2 trong 1–2 ngày theo timeline (P1–P2), rồi P3–P5 để hoàn thiện độ bền/chính sách và rollout [unified-solution-plan.md:127–131].

Nếu bạn muốn, mình có thể chuyển phần này thành checklist triển khai (per-file, per-function) kèm mẫu log/đo lường để dán thẳng vào codebase.