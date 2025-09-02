# Kế hoạch giải pháp hợp nhất – Ổn định Hashrate GPU (Phased Plan)

Ngày phát hành: 2025-09-02 (UTC)

Tài liệu này mô tả đầy đủ lộ trình tái cấu trúc nhằm khắc phục hiện tượng tụt hashrate sau restart, bảo đảm ổn định và khả năng phục hồi nhanh. Mỗi giai đoạn (phase) liệt kê rõ mục tiêu, bước triển khai, timeline, yêu cầu đầu vào/đầu ra, vai trò–trách nhiệm (RACI), tiêu chí đánh giá, rủi ro và điều kiện thoát phase.

---

## 1) Executive Summary (Tóm tắt điều hành)
- Mục tiêu: khôi phục và duy trì hashrate mục tiêu ≥ 24 MH/s (mỗi GPU) bền vững ≥ 15 phút, không suy giảm sau ≥ 3 lần restart liên tiếp; clocks/power/P-state đạt vùng hiệu năng, logs sạch lỗi NVML nghiêm trọng.
- Hướng tiếp cận: triển khai theo nhiều phase tăng dần mức đảm bảo, bắt đầu bằng Quick Stabilization rồi hợp nhất điều khiển GPU theo một pipeline tất định (deterministic – thứ tự cố định), quan sát đầy đủ, và xác minh A/B.
- Ràng buộc: không đổi cấu trúc thư mục, không thêm module nếu không cần, chỉ mô tả thiết kế và lộ trình; tuân thủ Scope Lock dựa trên 4 báo cáo tại `app/reports/`.

---

## 2) Scope Lock (Hu hẹp phạm vi)
- Chỉ dựa trên các tài liệu: `app/reports/report-01.md` … `report-04.md`.
- Không suy diễn vượt ngoài dữ liệu; nếu thiếu bằng chứng: ghi rõ “Chưa đủ bằng chứng, cần thu thập …”.
- Thực thi thay đổi trong các module hiện có: ví dụ `app/start_mining.py`, `app/resource_control.py`, `app/resource_manager.py`, `app/gpu_optimization_orchestrator.py`, `app/cloak_strategies.py`, `app/pid_logger/`.

---

## 3) Mục tiêu & KPI (Objectives & KPIs)
- Hashrate ổn định: ≥ 24 MH/s/GPU trong ≥ 15 phút liên tục sau warm-up ≤ 2 phút.
- Sau 3 lần restart liên tiếp: hashrate quay lại mức mục tiêu trong ≤ 90 giây, không còn stuck ~412 MHz/~75W.
- Clocks/P-state/Power: SM ≥ 1245 MHz (mục tiêu), Mem phù hợp; Power draw trong 150–200W (tùy GPU), P-state ở mức hiệu năng.
- Logs sạch lỗi NVML nghiêm trọng; không có ngoại lệ bị nuốt (no “except: pass”).

---

## 4) Tài liệu nguồn & Ghi chú bằng chứng (Evidence Notes)
- Nguồn: `app/reports/report-01.md` … `report-04.md`.
- Kết luận trọng yếu (tóm tắt):
  - Ứng dụng thiếu/không đồng nhất reset Application Clocks (nvidia-smi -rac) và thứ tự reset không tất định → trạng thái xung bị “dính” giữa phiên, đặc biệt khi persistence mode bật.
  - Có rủi ro race condition, cleanup chưa triệt để (signal handler), ngoại lệ NVML bị che giấu, và gating (ví dụ skip-lock) có thể giữ GPU ở low clock.
- Chưa đủ bằng chứng cần bổ sung (verbatim): trích nguyên văn các đoạn then chốt từ 4 báo cáo (perf-cap reasons, P-state, trình tự reset) để đính kèm phụ lục khi thu thập xong.

---

## 5) Thành phần liên quan (Impacted Modules)
- `app/start_mining.py` (entry/exit, handler tín hiệu – signal handler) – xử lý chuẩn bị và dọn dẹp.
- `app/resource_control.py` (điều khiển GPU trung tâm – Single Source of Truth) – áp thứ tự NVML-first + CLI verification.
- `app/resource_manager.py` (readiness gate, phối hợp tài nguyên – synchronization) – tránh race.
- `app/gpu_optimization_orchestrator.py` (trật tự tối ưu hóa/khóa xung – sequencing) – áp sau khi reset.
- `app/cloak_strategies.py` (chiến lược cloaking – có thể ảnh hưởng gating xung).
- `app/pid_logger/` (PID/file lock/cross-PID guards) – chống xung đột tiến trình.

---

## 6) RACI (Roles & Responsibilities)
- Owner (Chịu trách nhiệm chính): Tech Lead/DevOps.
- Approver (Phê duyệt): PM/Kỹ thuật trưởng.
- Consulted (Tham vấn): GPU Ops, SRE, QA/Perf.
- Informed (Nhận thông tin): Security, Data, Stakeholders liên quan.

Ghi chú: dùng vai trò, không gán cá nhân; cập nhật khi phân công cụ thể.

---

## 7) Lộ trình theo Phase (Phased Execution Plan)

Mốc thời gian tham chiếu: bắt đầu 2025-09-02 (UTC). Điều chỉnh theo kế hoạch thực tế nếu cần.

### Phase 0 – Chuẩn bị & Baseline (0.5–1 ngày; 2025-09-02)
- Mục tiêu: tái lập baseline (A) trước can thiệp; kiểm kê điểm reset/clocks; bật telemetry tối thiểu.
- Đầu vào: 4 báo cáo; cấu hình hiện tại; scripts/logs lịch sử (nếu có).
- Tiền điều kiện: môi trường chạy mining sẵn sàng; GPU driver ổn định.
- Bước triển khai:
  1) Thu thập logs hiện tại: clocks (SM/Mem), P-state, power draw/limit, perf-cap reasons, hashrate 10s/60s/15m.
  2) Chạy 1 phiên baseline ≥ 15 phút; thực hiện 3 lần restart để ghi nhận hiện tượng tụt.
  3) Tổng hợp baseline set A (CSV/JSON) + nhật ký thời gian.
- Đầu ra: gói dữ liệu baseline A; báo cáo ngắn hiện trạng.
- RACI: Owner=DevOps; Consulted=GPU Ops, QA/Perf; Approver=PM.
- Tiêu chí đánh giá: baseline đủ trường dữ liệu; tái hiện được tụt hashrate.
- Rủi ro/Mitigation: thiếu trường perf-cap → bổ sung truy vấn CLI/NVML; dữ liệu nhiễu → lặp lại tối thiểu 2 lần.
- Điều kiện thoát: baseline A hoàn chỉnh, lưu trữ có checksum.

### Phase 1 – Rapid Stabilization (1 ngày; 2025-09-02 → 2025-09-03)
- Mục tiêu: khôi phục nhanh khả năng đạt hashrate mục tiêu sau restart.
- Đầu vào: baseline A; danh sách điểm reset/cleanup hiện có.
- Tiền điều kiện: không đổi cấu trúc; có quyền chỉnh sửa logic reset/cleanup ở các điểm vào/ra hợp lệ.
- Bước triển khai:
  1) Preflight Reset (Preflight – reset trước khi chạy): áp thứ tự NVML-first (NVML trước) → CLI verification (xác minh bằng nvidia-smi) để đưa GPU về mặc định an toàn.
  2) Signal Handler Cleanup (dọn dẹp khi thoát): đăng ký restore/reset GPU state có thứ tự; loại bỏ nuốt ngoại lệ.
  3) RM Readiness Gate (cổng sẵn sàng của Resource Manager): chặn khởi chạy miner cho đến khi RM báo ready để tránh race.
  4) Tắt tạm điều kiện “skip-lock if low SM” trong pha khởi động để thoát bẫy low-clock.
- Đầu ra: phiên bản ổn định tạm thời; log trước/sau mỗi bước reset.
- RACI: Owner=DevOps; Consulted=GPU Ops, SRE; Approver=Tech Lead.
- Tiêu chí đánh giá: sau restart ≤ 90 giây đạt ≥ 24 MH/s/GPU; không stuck 412 MHz/75W.
- Rủi ro/Mitigation: một số GPU không hỗ trợ -rac → degrade gracefully (kiểm tra mã trả về, fallback unlock); xung đột tiến trình → PID/file locks.
- Điều kiện thoát: 3 lần restart liên tiếp đạt mục tiêu tạm.

### Phase 2 – Deterministic GPU Control (1–2 ngày; 2025-09-03 → 2025-09-04)
- Mục tiêu: hợp nhất điều khiển GPU về một mối (Single Source of Truth – nguồn sự thật duy nhất) và đảm bảo thứ tự tất định.
- Đầu vào: thay đổi Phase 1; bản đồ điểm set/reset hiện có; danh sách API NVML/CLI dùng.
- Tiền điều kiện: mọi thao tác set/reset phải đi qua `app/resource_control.py`.
- Bước triển khai:
  1) Chuẩn hóa pipeline: NVML-first cho mọi set/reset; CLI chỉ để verify hoặc fallback.
  2) Chuẩn hóa sequencing trong `gpu_optimization_orchestrator.py` sau reset: `reset → power-limit safe → lock clocks (nếu cần) → verify`.
  3) Mirroring state (phản chiếu trạng thái): lưu “state mirror” trước/sau thao tác (clocks/P-state/power/perf-cap) để kiểm soát hồi quy.
  4) Chuẩn hóa error surface: mọi lỗi NVML/CLI phải được log cấp WARNING/ERROR; không nuốt ngoại lệ.
- Đầu ra: pipeline điều khiển GPU tất định; tài liệu sequencing.
- RACI: Owner=Tech Lead; Consulted=DevOps, SRE; Approver=PM.
- Tiêu chí đánh giá: tất cả entry/exit điểm GPU ops đi qua SoT; snapshot trước/sau khớp mong đợi.
- Rủi ro/Mitigation: deadlock luồng → lock tinh gọn + timeout; lệch trạng thái → verify 2 pha (before/after).
- Điều kiện thoát: kiểm thử nội bộ 100% case đã map; không còn thao tác “ngoài luồng”.

### Phase 3 – Reliability & Observability Hardening (1 ngày; 2025-09-04)
- Mục tiêu: tăng độ bền và khả năng chẩn đoán.
- Đầu vào: pipeline SoT; danh sách ngoại lệ NVML/CLI.
- Tiền điều kiện: logging framework sẵn; flags/ENV để bật/tắt mức log.
- Bước triển khai:
  1) Structured Logging (ghi log có cấu trúc): thêm trường P-state, perf-cap reasons, power draw/limit, clocks trước/sau mỗi bước.
  2) Guards & Locks: khóa luồng cho GPU ops; file lock/PID registry để tránh cross-PID conflicts.
  3) Health Checks: kiểm tra chu kỳ sau mỗi thay đổi lớn (post-change) và trước khi khởi mining (preflight health).
- Đầu ra: bộ logs giàu ngữ cảnh; giảm lỗi race/cross-PID.
- RACI: Owner=SRE; Consulted=DevOps, QA/Perf; Approver=Tech Lead.
- Tiêu chí đánh giá: không còn ngoại lệ bị nuốt; logs đủ để truy vết root cause trong ≤ 10 phút.
- Rủi ro/Mitigation: bùng nổ log → mức log điều khiển qua ENV; sampling.
- Điều kiện thoát: bài test stress 30’ không sinh lỗi mới nghiêm trọng.

### Phase 4 – Optimization & Policy Tuning (1 ngày; 2025-09-05)
- Mục tiêu: tinh chỉnh chính sách khóa xung/gating để tối ưu hiệu năng ổn định.
- Đầu vào: dữ liệu Phase 1–3; biểu đồ hashrate/power.
- Tiền điều kiện: đã thoát bẫy low-clock ổn định.
- Bước triển khai:
  1) Rà soát và điều chỉnh điều kiện “skip-lock” theo ngưỡng đo thực tế; nếu cần dùng “closed-loop controller” ngắn (bộ điều khiển vòng kín – tăng dần xung) trước khi khóa cứng.
  2) Tối ưu power limit mục tiêu theo đường cong hiệu năng.
- Đầu ra: cấu hình/logic chính sách chốt.
- RACI: Owner=GPU Ops; Consulted=DevOps, QA/Perf; Approver=Tech Lead.
- Tiêu chí đánh giá: hashrate ổn định, power hiệu quả, không dao động quá 3% trong 15 phút.
- Rủi ro/Mitigation: dao động hashrate → nới/siết ngưỡng hysteresis.
- Điều kiện thoát: metrics đạt mục tiêu ≥ 2 phiên liên tiếp.

### Phase 5 – A/B Validation & Rollout (0.5–1 ngày; 2025-09-05)
- Mục tiêu: xác minh định lượng bằng A/B và ban hành rộng rãi.
- Đầu vào: baseline A (Phase 0) và bản sửa B (Phase 1–4).
- Tiền điều kiện: kịch bản test chuẩn; dữ liệu thu thập tự động.
- Bước triển khai:
  1) A/B Test (thử nghiệm A/B): chạy A (cũ) và B (mới) với cùng workload, ≥ 15’ và ≥ 3 lần restart.
  2) So sánh định lượng các chỉ số: hashrate, thời gian hồi phục sau restart, clocks, P-state, perf-cap reasons, power.
  3) Báo cáo kết quả + quyết định rollout + kế hoạch rollback.
- Đầu ra: báo cáo A/B; quyết định triển khai.
- RACI: Owner=QA/Perf; Consulted=Tech Lead, DevOps; Approver=PM.
- Tiêu chí đánh giá (Pass):
  - Hashrate B ≥ 24 MH/s/GPU và ≥ A; sau restart ≤ 90s đạt mục tiêu; không stuck 412 MHz/75W.
  - Logs sạch ngoại lệ nghiêm trọng; quan sát P-state/perf-cap phù hợp hiệu năng.
- Rủi ro/Mitigation: khác biệt môi trường → pin phiên bản driver, hồ sơ GPU, và tải bài test.
- Điều kiện thoát: đạt toàn bộ tiêu chí Pass; kế hoạch rollback sẵn sàng.

---

## 8) Kế hoạch đo lường & Telemetry (What to Measure)
- Hashrate (10s/60s/15m), Clocks (SM/Mem), Power draw/limit, Temperature, P-state, Perf-cap reasons, NVML/CLI return codes.
- Gắn timestamp và phiên (run_id) cho mọi snapshot trước/sau thao tác.

---

## 9) Rủi ro & Kế hoạch dự phòng (Global)
- Không hỗ trợ một số thao tác (ví dụ -rac) → kiểm tra khả năng, fallback, cảnh báo rõ.
- Race/cross-PID → khóa tinh gọn + timeout; theo dõi deadlock.
- Bùng nổ log → cấu hình mức log, dùng sampling ở mức cao.
- Sai lệch sequencing → kiểm chứng 2 pha (before/after) + assertion.

---

## 10) Thuật ngữ (English → Vietnamese)
- Preflight Reset (reset trước khi chạy – đưa GPU về mặc định an toàn)
- Single Source of Truth (nguồn sự thật duy nhất – nơi tập trung điều khiển/trạng thái)
- Deterministic Order (thứ tự tất định – luôn giống nhau)
- Persistence Mode (chế độ bền bỉ – giữ trạng thái driver giữa phiên)
- NVML-first (ưu tiên API NVML trước)
- CLI Verification (xác minh bằng công cụ dòng lệnh – nvidia-smi)
- Readiness Gate (cổng sẵn sàng – điều kiện cho phép chạy)
- Closed-loop Controller (bộ điều khiển vòng kín – tăng/giảm theo phản hồi)
- Perf-cap Reasons (lý do giới hạn hiệu năng – từ driver/firmware)
- P-state (trạng thái hiệu năng – mức xung/điện năng phần cứng)
- A/B Test (thử nghiệm so sánh – hai biến thể A và B)

---

## 11) Phụ lục
- Checklist triển khai theo phase (tick-list cho mỗi bước).
- Ma trận phụ thuộc giữa module và bước thao tác.
- (Để cập nhật) Trích dẫn verbatim từ `report-01.md` … `report-04.md` cho các kết luận chính; hiện tạm ghi chú tóm tắt và sẽ bổ sung nguyên văn khi hoàn tất rà soát câu chữ.

---

## 12) Điều kiện hoàn tất toàn chương trình
- Đạt tiêu chí Pass của Phase 5 A/B và không phát sinh lỗi nghiêm trọng sau 24 giờ giám sát.
- Lưu trữ đầy đủ tài liệu: baseline A, dữ liệu đo, báo cáo A/B, và nhật ký triển khai.
