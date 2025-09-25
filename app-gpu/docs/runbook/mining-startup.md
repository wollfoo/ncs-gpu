# Hướng dẫn khởi chạy mining

## 1. Yêu cầu hệ thống
- Python components cũ cần CUDA loader `libmlls-cuda.so` và binary `inference-cuda` (tham khảo `start_mining.py:529-620` trong repo nguyên gốc).
- Rust toolchain 1.76+, Go 1.22+, Node.js 20 LTS (đã nêu tại `README.md`).
- Docker (tùy chọn) với NVIDIA Container Toolkit khi triển khai trong container.
- NATS server có thể truy cập (`NATS_URL`, mặc định `127.0.0.1:4222`).
- Prometheus (tùy chọn) để thu thập metric tại các cổng `SCHEDULER_METRICS_ADDR` (9100) và `EXECUTOR_METRICS_ADDR` (9200).

## 2. Các bước cài đặt và cấu hình
1. Cài đặt Rust, Go, Node.js theo yêu cầu.
2. Cài đặt NATS server (docker hoặc binary): `docker run --rm -p 4222:4222 -p 8222:8222 nats:2.10`.
3. Thiết lập biến môi trường:
   - `NATS_URL`, `SCHEDULER_SUBJECT`, `EXECUTOR_SUBJECT` nếu cần tùy chỉnh.
   - `SCHEDULER_BEARER_TOKEN` (optional) để bật xác thực HTTP.
   - `NATS_AUTH_TOKEN` (optional) nếu NATS yêu cầu Bearer token.
   - `SCHEDULER_METRICS_ADDR`, `EXECUTOR_METRICS_ADDR` nếu cần thay đổi cổng metrics.
4. (Tạm thời) cấu hình GPU binary cũ nếu còn sử dụng `start_mining.py`: đảm bảo `MINING_SERVER_GPU`, `MINING_WALLET_GPU`, `MLLS_CUDA` được đặt.

## 3. Khởi chạy dịch vụ
1. Chạy scheduler Rust:
   ```bash
   cd /home/azureuser/opus-gpu/app/app-gpu
   cargo run -p scheduler
   ```
2. Chạy executor Rust:
   ```bash
   cargo run -p executor
   ```
3. (Legacy) Nếu cần chạy pipeline Python hiện tại:
   ```bash
   python ../start_mining.py
   ```
   để khởi động binary `inference-cuda`.

## 4. Kiểm tra hoạt động
1. Gửi thử job:
   ```bash
   curl -X POST http://127.0.0.1:8080/jobs \
     -H "Content-Type: application/json" \
     -d '{"payload":{"test":true}}'
   ```
   Khi bật Bearer token: thêm `-H "Authorization: Bearer $SCHEDULER_BEARER_TOKEN"`.
2. Kiểm tra log scheduler/executor để xác nhận job nhận + ACK.
3. Theo dõi metrics:
   ```bash
   curl http://127.0.0.1:9100/metrics   # scheduler
   curl http://127.0.0.1:9200/metrics   # executor
   ```
   Metric như `scheduler_jobs_published_total`, `executor_jobs_completed_total` phải tăng tương ứng.
4. Dùng script benchmark:
   ```bash
   SCHEDULER_URL=http://127.0.0.1:8080/jobs \
   SCHEDULER_BENCH_TOKEN=$SCHEDULER_BEARER_TOKEN \
   tooling/scripts/bench_scheduler.sh 100
   ```
   Sau khi chạy, kiểm tra metrics và log để xác nhận throughput.

---

# Các hạng mục còn thiếu trước sản xuất

1. **Module/Dependencies cần bổ sung**
   - GPU mining thực tế chưa port sang executor Rust: `simulate_gpu_work()` chỉ là giả lập (`data-plane/executor/src/main.rs:69-84`).
   - Chưa có package kiểm soát secrets/mTLS thực tế (mới dừng ở token + HTTP metrics, `control-plane/scheduler/src/main.rs:52-95`).
   - Thiếu test integration tự động hoá NATS queue (chưa có tập tin trong `tests/`).

2. **Chức năng cần phát triển**
   - Triển khai loader CUDA hoặc binding tới binary `inference-cuda` thay cho hàm giả lập (`start_mining.py:501-620`).
   - Thêm health-check trả về trạng thái thực của NATS/queue và GPU executor (hiện `/health` chỉ trả về static ok, `control-plane/scheduler/src/main.rs:45-50`).
   - Hoàn thiện API điều phối (retry, backpressure, ack-check) và job status store (chưa tồn tại module lưu trạng thái).

3. **Vấn đề bảo mật cần xử lý**
   - Chưa triển khai mTLS giữa scheduler và gateway; mới có Bearer token (`control-plane/scheduler/src/main.rs:52-65`).
   - Chưa có quản lý secrets tập trung (Vault/KMS) – token và config vẫn lấy từ env (`control-plane/scheduler/src/main.rs:110-120`).
   - Legacy stealth code vẫn tồn tại trong `start_mining.py` (ẩn tiến trình) cần đánh giá tuân thủ khi đưa vào production.

4. **Yêu cầu tối ưu hóa hiệu năng**
   - Benchmark thực tế chưa chạy do thiếu môi trường GPU/NATS (scripts đã có `tooling/scripts/bench_scheduler.sh`, nhưng chưa thu kết quả). Cần đo P95 latency, throughput.
   - Executor chưa thực hiện batching hoặc parallel kernel execution; hiện xử lý tuần tự (`data-plane/executor/src/main.rs:45-81`).
   - Chưa có autoscaling/queue depth monitoring – cần tích hợp metrics vào HPA/KEDA hoặc tương đương.

Hoàn thiện các mục trên sẽ đưa hệ thống tới trạng thái production-ready: mining chạy bằng executor Rust với GPU thực, bảo mật/mTLS đầy đủ, có tests integration & benchmark, quan sát được và có kế hoạch scale.
