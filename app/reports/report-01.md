# GPU Performance Investigation — Report 01

Generated: 2025-09-02 06:15 UTC

## 1) Objective, Scope, Constraints
- **Objective**: Điều tra suy giảm hiệu năng GPU; kiểm kê đầy đủ các lệnh `nvidia-smi` liên quan clock/power, xác nhận vắng mặt reset Application Clocks (`-rac`), chẩn đoán nguyên nhân, đề xuất refactor không đổi cấu trúc thư mục hay viết thêm code.
- **Scope**: Mã trong `app/` (đặc biệt: `setup_env.py`, `resource_control.py`, `utils.py`) và log `app/mining_debug.log`.
- **Constraints**: Không thay đổi cấu trúc dự án; ưu tiên tận dụng mã hiện có; báo cáo ngắn gọn, trích dẫn nguồn (file:line) khi khả dụng.

## 2) Environment & Config (from code and logs)
- **GPU**: Tesla V100-PCIE-16GB (log `start_mining`: GPU 0/1).
- **Driver**: 550.90.07 (`mining_debug.log` lines ≈ 61–63).
- **Env Vars (được đọc trong `setup_env.py`)**:
  - `ALLOW_CLOCK_LOCK`, `ENABLE_PERSISTENCE_MODE_ON_SETUP`
  - `MIN_POWER_LIMIT`, `MIN_SM_CLOCK`, `MIN_MEM_CLOCK`
  - `LOCK_TARGET_SM_CLOCK`, `LOCK_TARGET_MEM_CLOCK`

## 3) Inventory nvidia-smi theo file
- `app/mining_environment/scripts/setup_env.py`
  - Reset/unlock trước tối ưu:
    - `nvidia-smi -i <idx> -rgc` (unlock graphics clocks)
    - `nvidia-smi -i <idx> --reset-memory-clocks`
    - Function tham chiếu: `reset_gpu_state(logger)` (đã xem file 1–633 dòng; phiên trước)
  - Thiết lập baseline sau reset:
    - `nvidia-smi -pm 1` (persistence mode)
    - `nvidia-smi -i <idx> -pl <W>` (power limit)
    - `nvidia-smi -i <idx> --lock-gpu-clocks=<MHz>`
    - `nvidia-smi -i <idx> --lock-memory-clocks=<MHz>`
    - Function tham chiếu: `enforce_gpu_baselines(logger)`
  - Ghi nhận: Không thấy `-rac` trong file này.

- `app/mining_environment/scripts/resource_control.py`
  - Fallback metrics: `--query-gpu=... --format=csv,noheader,nounits` [resource_control.py:572–579]
  - Set clocks (đồng bộ):
    - `--lock-gpu-clocks=<MHz>` [resource_control.py:962–965]
    - `--lock-memory-clocks=<MHz>` [resource_control.py:971–975]
  - Temp fallback: `--query-gpu=temperature.gpu` [resource_control.py:1120–1126]
  - PID↔GPU mapping fallback:
    - `--query-gpu=index,uuid` [resource_control.py:1557–1559]
    - `--query-compute-apps=pid,gpu_uuid` [resource_control.py:1566–1568]
  - Restore/unlock trước áp dụng:
    - `-rgc` [resource_control.py:1604–1609]
    - `--reset-memory-clocks` [resource_control.py:1616–1619]
  - Ghi nhận: Không có `-rac` được thực thi trong file này.

- `app/mining_environment/scripts/utils.py`
  - `set_gpu_clocks(...)`: `--lock-gpu-clocks=<MHz>`, `--lock-memory-clocks=<MHz>` (phiên trước)
  - Ghi nhận: Không thấy `-ac`, không thấy `-rac` trong hàm này.

- Ghi chú: `privileged_operations.py` từng được ghi nhận có dùng `-ac` (phiên trước); không tái-đối-soát trong báo cáo rút gọn này.

## 4) Evidence Timeline (log trích dẫn)
Nguồn: `app/mining_debug.log`.
- 17:44:05 — Pre-unlock & Baseline
  - Unlock GPU 0/1: `-rgc`, `--reset-memory-clocks` [lines 144–147]
  - Enable persistence: `-pm 1` [line 149]
  - Baseline per-GPU: `-pl`, `--lock-gpu-clocks`, `--lock-memory-clocks` [lines 150–155]
- 17:44:18–25 — Coordination hooks
  - `[HOOK] Unlocked clocks via nvidia-smi` cho GPU 0/1 [lines 842–853, 1724–1735]
- Ghi chú bổ sung
  - `Setting locked Memory clocks is not supported for GPU 00000002:00:00.0.` [lines 846, 1728]
  - Không tìm thấy “PerfCap” hay “P-state” khi grep trong log (không có chỉ dấu trực tiếp trong log hiện có).

## 5) Key Findings
- **Thiếu reset Application Clocks `-rac` trong mã thực thi** (chỉ thấy `-rgc`/`--reset-memory-clocks`).
- **Chiến lược clocks đang pha trộn**: khóa bằng `--lock-*`; khả năng tồn tại nơi khác từng dùng `-ac` (cần re-verify có kiểm chứng nếu phạm vi mở rộng).
- **Persistence mode** chủ động bật; trạng thái clocks có thể giữ qua vòng đời nếu không `-rac`.
- **Khả năng không hỗ trợ lock memory trên một thiết bị** (log cảnh báo), dẫn tới cấu hình không đồng nhất theo GPU.

## 6) Hypotheses (Impact/Likelihood/Effort)
- H1 — Thiếu `-rac` khiến app clocks còn giữ sau nhiều lần restart → hiệu năng suy giảm dần. (High/High/Low)
- H2 — Pha trộn `--lock-*` và tiềm năng `-ac` làm reset không bao phủ hết trường hợp. (Med/Med/Low)
- H3 — Power limit đặt thấp so với clocks mục tiêu → PerfCap=PWR (không thấy trong log, nhưng khả dĩ). (Med/Low/Low)
- H4 — Persistence mode lưu trạng thái clocks giữa các vòng → reset chưa đủ sâu. (Med/Med/Low)
- H5 — Thiếu hỗ trợ lock memory trên GPU nhất định làm cấu hình lệch → hiệu năng không ổn định. (Med/Med/Low)

## 7) Diagnosis (Root Cause)
- Nguyên nhân chính có khả năng cao: **vắng `nvidia-smi -rac` trong các điểm reset**. `-rgc`/`--reset-memory-clocks` không xóa Application Clocks; qua nhiều vòng khởi động, các lock ẩn có thể tích lũy/gắn cứng, làm giảm hashrate.

## 8) Refactor Plan (không đổi cấu trúc, không viết code mới)
- **Bổ sung `-rac` vào các điểm reset đã có**:
  - `setup_env.py::reset_gpu_state(...)`: chèn `nvidia-smi -i <idx> -rac` cạnh `-rgc` và `--reset-memory-clocks` (idempotent, check rc, log rõ).
  - `resource_control.py` (khối restore ln ~1603+): thêm `-rac` theo mẫu logging đang dùng.
- **Trình tự chuẩn mỗi GPU**:
  1) `-pm 1`
  2) `-rac`, `-rgc`, `--reset-memory-clocks`
  3) `-pl <W>`
  4) `--lock-gpu-clocks=…`, `--lock-memory-clocks=…` (theo `ALLOW_CLOCK_LOCK`)
  5) Verify với `--query-gpu=clocks.sm,clocks.mem,applications.clocks.graphics,applications.clocks.mem,pstate,power.draw,power.limit,utilization.gpu`
- **Gating & fallback**: nếu `-rac` không hỗ trợ (rc≠0) → tiếp tục `-rgc`/reset-mem; cảnh báo log.
- **Thống nhất phương pháp**: nếu có nơi dùng `-ac`, đảm bảo có `-rac` ở entry/exit tương ứng để không để lại app clocks.

## 9) Test & Evaluation Design
- **Tiêu chí thành công**: sau ≥3 chu kỳ restart, hashrate không suy giảm; `applications.clocks.*` ở trạng thái mong muốn (N/A hoặc theo giá trị đặt); `pstate`, `power.draw`, `utilization.gpu` ổn định.
- **Quy trình**: vòng lặp setup→mine 10–15′→stop, lặp 3–5 lần; mỗi vòng dump `nvidia-smi --query-*` nêu trên để đối chiếu.

## 10) Risks & Mitigations
- Không hỗ trợ `-rac`/`--lock-memory-clocks` trên một số GPU/driver → kiểm tra rc, degrade gracefully.
- Power limit không tương thích clocks khóa → nâng `-pl` theo quan sát để tránh PerfCap=PWR.

## 11) Reproducibility Plan
- Ghi nhận driver (550.90.07), GPU (V100 16GB), env vars như mục (2).
- Lưu snapshot `nvidia-smi --query-*` trước/sau mỗi thao tác chính (reset/lock/power/persistence).
- Nhật ký đầy đủ lệnh + rc như hiện có trong `setup_env.py` và `resource_control.py`.

## 12) Summary
- **Core fix (đề xuất)**: thêm `nvidia-smi -rac` vào các điểm reset để xoá triệt để Application Clocks trước khi đặt baseline và (nếu cần) khóa lại; giữ nguyên cấu trúc dự án, tận dụng sẵn logging và luồng hiện có.
