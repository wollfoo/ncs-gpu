# MODULE_INDEX – Chỉ mục chi tiết mã nguồn `app/`

Tài liệu này cung cấp cái nhìn toàn cảnh và mô tả ngắn cho từng module (module – đơn vị mã) và component (thành phần – khối chức năng) trong thư mục `app/`, giúp điều hướng nhanh, dễ bảo trì.

Xem thêm: `app/README.md` (overview – tổng quan), README ở từng thư mục con:
- `mining_environment/README.md`
- `mining_environment/scripts/README.md`
- `mining_environment/scripts/auxiliary_modules/README.md`
- `mining_environment/coordination/README.md`
- `mining_environment/stealth/README.md`
- `mining_environment/stealth/core/README.md`
- `mining_environment/stealth/wrappers/README.md`
- `pid_logger/README.md`

---

## Cấp cao nhất (top-level – cấp gốc)

- `start_mining.py`: Entry point (điểm vào – tập tin khởi chạy) quản lý khởi động, giám sát tiến trình, logging, kết nối `pid_logger` và `ResourceManager`. Có import `initialize_stealth_activation()` nhưng theo phân tích hiện tại hàm này chưa được gọi; `cleanup_stealth_activation()` được gọi khi shutdown (shutdown – tắt hệ thống).
- `requirements.txt`: Danh sách phụ thuộc Python.
- `Dockerfile`: Định nghĩa build container (container build – dựng môi trường).
- `entrypoint.sh`: Script (kịch bản – tập lệnh) khởi chạy container.
- `inference-cuda`, `inference-cuda.original`: Binary wrapper (trình bọc nhị phân – lớp bọc) cho suy luận CUDA; file `.original` là bản gốc tham chiếu.
- `libmlls-cuda.so`: Thư viện động (shared library – thư viện dùng chung) đi kèm.

---

## `mining_environment/` – Lõi điều phối & tối ưu

- `__init__.py`: Khai báo package (gói – đơn vị phát hành).
- `config/` (cấu hình – tham số runtime):
  - `coordination.json`: Tham số điều phối liên tiến trình.
  - `environmental_limits.json`: Ngưỡng/giới hạn môi trường (nhiệt, công suất, v.v.).
  - `gpu_optimization_config.json`: Tham số tối ưu GPU.
  - `hardware_optimization.json`: Tùy chọn tối ưu phần cứng.
  - `resource_config.json`: Cấu hình tài nguyên tổng thể.
  - `system_params.json`: Tham số chung hệ thống.
  - `threading_config.json`: Số luồng, timeout, chính sách.
- `coordination/` (điều phối – sắp xếp thực thi):
  - `coordinator.py`: Coordinator (bộ điều phối – nhạc trưởng) cho tác vụ/DAG.
- `scripts/` (tác nghiệp – chiến lược/giám sát/tối ưu):
  - `auxiliary_modules/` (phụ trợ – mô hình & giao diện):
    - `interfaces.py`: Interfaces/contracts (giao diện/khế ước – ràng buộc giữa thành phần).
    - `models.py`: Data models/dataclasses (mô hình dữ liệu – lớp dữ liệu).  
  - `cloak_strategies.py`: Chiến lược ẩn mình/che giấu (cloaking – giảm lộ dấu).
  - `cross_process_coordination.py`: Phối hợp đa tiến trình (cross-process – liên tiến trình).
  - `dag_synchronization.py`: Đồng bộ DAG (đồ thị công việc – phụ thuộc).
  - `error_management.py`: Chuẩn hóa và xử lý lỗi (error handling – bắt/ghi lỗi).
  - `error_recovery_coordinator.py`: Điều phối khôi phục khi lỗi (recovery – phục hồi).
  - `gpu_monitoring_dashboard.py`: Dashboard/TUI/CLI (bảng điều khiển – hiển thị chỉ số GPU).
  - `gpu_optimization_orchestrator.py`: Orchestrator (dàn nhạc – điều phối tối ưu GPU).
  - `gpu_resource_monitor.py`: Monitor (giám sát – đọc/util hóa GPU: util/mem/temp/power nếu có).
  - `log_deduplication.py`: Khử trùng lặp log (dedup – giảm lặp lại).
  - `log_rotation_guard.py`: Bảo vệ xoay vòng log (rotation guard – chống quá tải). 
  - `logging_compat.py`: Tương thích/tiện ích logging.
  - `logging_config.py`: Cấu hình logging trung tâm (logger levels/handlers – mức/đầu ra).
  - `module_loggers.py`: Logger theo module (module-scoped – phạm vi theo mô-đun).
  - `parallel_strategy_executor.py`: Thực thi chiến lược song song (parallel executor – bộ thực thi song song).
  - `performance_profiler.py`: Profiling (phân tích hiệu năng – đo thời gian/tải).
  - `privileged_operations.py`: Thao tác đặc quyền (privileged ops – yêu cầu quyền cao).
  - `resource_control.py`: Áp chính sách kiểm soát tài nguyên (controls – hạn mức/quy tắc).
  - `resource_manager.py`: Resource manager (quản lý tài nguyên – lớp trung tâm).
  - `setup_env.py`: Chuẩn bị môi trường chạy (env setup – thiết lập biến/đường dẫn).
  - `strategy_cache.py`: Cache kết quả/chiến lược (cache – bộ nhớ đệm).
  - `utils.py`: Tiện ích chung; enum `StrategyType` (kiểu chiến lược – phân loại) và hằng số/phụ trợ.
- `stealth/` (ẩn mình – core + wrappers):
  - `core/stealth_activation_manager.py`: Quản lý bật/tắt ẩn mình; đảm bảo idempotent (lặp lại an toàn).
  - `wrappers/stealth_inference_cuda.py`: Wrapper (lớp bọc – chuyển tiếp) cho `inference-cuda` để cấy hook/điều phối khi cần.

---

## `pid_logger/` – PID registry & log bridge

- `direct_registry.py`: In-process PID registry (đăng ký PID trong tiến trình – tra cứu nhanh).
- `mining_output_bridge.py`: Log bridge (cầu nối log – chuyển tiếp dòng ra đến đích khác).
- `worker.py`: Worker (tiến trình/luồng – thực thi thu thập/đẩy log).

---

## Hướng điều hướng (navigation – cách tìm nhanh)

- Bắt đầu từ `app/README.md` để nắm kiến trúc và quy ước.
- Đi vào `mining_environment/scripts/README.md` để chọn đúng module tác nghiệp.
- Xem README tương ứng trong `stealth/` và `pid_logger/` trước khi mở rộng/chỉnh sửa.

---

## Ghi chú triển khai (implementation notes – lưu ý)

- Metrics provider (nhà cung cấp chỉ số – đọc NVML/đo lường) nên hợp nhất, có TTL, và fallback an toàn; tránh đọc trực tiếp từ nhiều nơi.
- Logging (ghi nhật ký) tiêu chuẩn hóa qua `logging_config.py`; dùng logger theo module.
- Config (cấu hình) lấy từ `mining_environment/config/`; không hardcode.
- Concurrency (đồng thời) nên thông qua executor/coordinator; tránh thread/process “mồ côi”.

---

## Quy trình đóng góp (contributing – cách bổ sung)

1. Thêm docstring (chuỗi tài liệu – mô tả) cho module/hàm/method public.
2. Cập nhật README tại thư mục liên quan và bổ sung mục trong `MODULE_INDEX.md` này.
3. Khi thêm chỉ số/giám sát mới, bám chuẩn provider hợp nhất, cập nhật cấu hình nếu cần.
4. Ghi log có ngữ cảnh (context – ngữ cảnh hoạt động) và dùng `log_deduplication.py` khi phù hợp.
