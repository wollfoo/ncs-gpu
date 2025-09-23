# Repository Guidelines

## Project Structure & Module Organization
- `start_mining.py` điều phối khai thác, khởi tạo logging và quản lý tiến trình GPU.
- `mining_environment/` gom logic cốt lõi: `scripts/` (thiết lập + resource manager), `coordination/`, `stealth/`, `config/`.
- `pid_logger/` chứa tiện ích giám sát PID; log mặc định nằm trong `mining_environment/logs`.
- Nhị phân CUDA (`inference-cuda`, `libmlls-cuda.so`) ở gốc và được Dockerfile cài vào `/usr/local/bin`; `entrypoint.sh` thiết lập biến GPU.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` rồi `pip install -r requirements.txt` để đồng bộ phụ thuộc.
- `python start_mining.py` khởi chạy hệ thống, ghi log về `mining_environment/logs`.
- `docker build -t gpu-miner .` và `docker run --gpus all --env-file <env> gpu-miner` để chạy container; đảm bảo cung cấp `MINING_SERVER_GPU`, `MINING_WALLET_GPU`.

## Coding Style & Naming Conventions
- Tuân thủ PEP 8: thụt 4 khoảng, `snake_case` cho hàm/biến, `PascalCase` cho lớp (ví dụ `LockFreeProcessManager`).
- Ghi log thông qua helper trong `mining_environment/scripts/logging_config.py`; thông điệp nên chỉ rõ GPU/thiết bị.
- Khi thêm module, giữ cấu trúc gói hiện hữu và cập nhật `__init__.py` cùng tham chiếu trong `start_mining.py`.

## Testing Guidelines
- Chưa có thư mục kiểm thử (`find . -maxdepth 3 -type d -name 'tests'` không trả kết quả); tạo `mining_environment/tests/` cho bài kiểm thử mới.
- Dùng fixture/mocking để mô phỏng GPU khi viết unit test cho `scripts/` hoặc `pid_logger`.
- Mục tiêu >=80% coverage; chạy `pytest --maxfail=1 --disable-warnings` trước khi gửi PR và đính kèm kết quả.

## Commit & Pull Request Guidelines
- Dùng định dạng commit kiểu Conventional như `remove(env): delete obsolete .env file...`.
- PR cần tóm tắt thay đổi, ảnh hưởng tới GPU runtime, kiểm thử đã chạy và liên kết issue; thêm log/ảnh minh họa khi chính sách vận hành thay đổi.
- Đồng bộ cập nhật cấu hình trong `Dockerfile`, `entrypoint.sh` và tài liệu khi động chạm tới biến môi trường.

## Security & Configuration Tips
- Không commit giá trị thực cho `MINING_SERVER_GPU`, `MINING_WALLET_GPU` hay khóa TLS; lưu trong `.env` và nạp bằng `--env-file`.
- Sau khi chỉnh đường dẫn, kiểm tra `entrypoint.sh` để bảo đảm `PYTHONPATH` và `LD_LIBRARY_PATH` chính xác; khóa phiên bản quan trọng trong `requirements.txt`.
