# scripts/ – Chỉ mục module và hướng dẫn

Thư mục `scripts/` chứa các module chiến lược, giám sát, tối ưu hoá, tiện ích và logging. Dưới đây là chỉ mục nhanh (one-liner per module – mô tả ngắn mỗi tệp):

## Chỉ mục module

- `auxiliary_modules/`: mô hình & giao diện phụ trợ (models, interfaces).
- `cloak_strategies.py`: định nghĩa chiến lược ẩn mình/che giấu.
- `cross_process_coordination.py`: tiện ích phối hợp đa tiến trình.
- `dag_synchronization.py`: đồng bộ DAG/nhiệm vụ có phụ thuộc.
- `error_management.py`: xử lý/chuẩn hoá lỗi.
- `error_recovery_coordinator.py`: điều phối khôi phục khi lỗi.
- `gpu_optimization_orchestrator.py`: dàn nhạc (orchestrator – điều phối) tối ưu GPU.
- `log_deduplication.py`: khử trùng lặp log.
- `log_rotation_guard.py`: bảo vệ xoay vòng log.
- `logging_compat.py`: tương thích/tiện ích logging.
- `logging_config.py`: cấu hình logging trung tâm.
- `module_loggers.py`: logger theo module.
- `parallel_strategy_executor.py`: thực thi chiến lược song song.
- `performance_profiler.py`: đo hiệu năng (profiling – phân tích hiệu năng).
- `privileged_operations.py`: thao tác yêu cầu đặc quyền (privileged operations).
- `resource_control.py`: áp chính sách kiểm soát tài nguyên.
- `resource_manager.py`: quản lý tài nguyên cấp cao.
- `setup_env.py`: chuẩn bị môi trường chạy.
- `stealth_monitor.py`: quan sát trạng thái ẩn mình.
- `strategy_cache.py`: bộ nhớ đệm (cache) cho chiến lược/kết quả.
- `utils.py`: tiện ích dùng chung (bao gồm enum `StrategyType`, hằng số, helper).

## Lưu ý triển khai

- Metrics (chỉ số): ưu tiên provider hợp nhất, có TTL và xử lý lỗi an toàn.
- Logging: dùng cấu hình từ `logging_config.py`, tránh spam; cân nhắc `log_deduplication.py`.
- Concurrency: sử dụng executor/điều phối sẵn có; tránh tạo thread/process trôi nổi.
- Config: mọi tham số phải đi qua `mining_environment/config/`.

## Thêm một chiến lược mới (strategy – chiến lược)

1. Khai báo kiểu/enum cần thiết trong `utils.py` (nếu có).
2. Cài đặt logic trong file mới hoặc thêm vào `cloak_strategies.py`/`gpu_optimization_orchestrator.py`.
3. Đăng ký với executor/orchestrator và bổ sung test cơ bản.
