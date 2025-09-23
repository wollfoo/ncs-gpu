# Opus GPU Mining Runtime

Opus GPU là tập hợp script và nhị phân tối ưu hóa cho môi trường khai thác GPU thuần (không dùng CPU). Mã nguồn bao gồm bộ điều phối `start_mining.py`, các module trong `mining_environment/` và tiện ích logging PID cho các tiến trình con.

## Bắt đầu nhanh
- Cài phụ thuộc: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
- Chạy trực tiếp: `python start_mining.py` và xem log trong `mining_environment/logs`.
- Dựng container: `docker build -t gpu-miner .` rồi `docker run --gpus all --env-file <env> gpu-miner`.

## Tài liệu dành cho contributor
- Đọc `AGENTS.md` để nắm cấu trúc kho, quy chuẩn coding, kiểm thử và quy trình PR.
- Khi thay đổi cấu hình runtime hoặc pipeline build, luôn cập nhật `AGENTS.md` và mô tả lý do trong PR.

## Giấy phép & bảo mật
- Không commit khóa ví hay cấu hình nhạy cảm; lưu trong `.env` cục bộ và truyền qua `--env-file` khi chạy container.
- Các nhị phân CUDA trong repo cần được xác minh nguồn gốc trước khi phát hành.
