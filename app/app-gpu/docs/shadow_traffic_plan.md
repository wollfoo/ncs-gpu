# Shadow Traffic & Tinh Chỉnh Pipeline

## Kiến trúc triển khai

1. **Cụm cũ (Monolith)**: chạy `start_mining.py` trên host hiện tại.
2. **Cụm mới (app-gpu)**: dùng `docker-compose.yml` để dựng các service `control-plane`, `orchestrator`, `rust-inference`, `telemetry`.
3. **Shadow gateway**: NGINX/Envoy hoặc Istio định tuyến `primary` → monolith, đồng thời mirror 5% request đến orchestrator mới.

```
client --> gateway --primary--> monolith
                 \--mirror--> orchestrator (app-gpu)
```

## Quy trình thực hiện

1. **Khởi động cụm mới**
   ```bash
   cd app-gpu
   docker compose up --build -d
   ```

2. **Cấu hình gateway** (ví dụ Envoy):
   - Route chính `production_cluster` → monolith.
   - Route mirror `shadow_cluster` → `orchestrator:9000` với `shadow_policy.default_value=0.05`.

3. **Thu thập metrics**
   - Control-plane: `curl http://<gateway>:8080/metrics`.
   - Telemetry exporter: `scripts/poll_metrics.py --endpoint http://localhost:9464/metrics` (`app-gpu/scripts/poll_metrics.py`).
   - GPU cũ: `nvidia-smi dmon -s pucvmt` hoặc file `docs/baseline_gpu.csv` làm chuẩn so sánh.
   - Prometheus scrape job mẫu:
     ```yaml
     - job_name: shadow-orchestrator
       metrics_path: /metrics
       static_configs:
         - targets: ['telemetry:9464']
     ```
   - Grafana: tạo dashboard nhập liệu từ series `jobs_total`, `job_latency_ms_sum`, `job_latency_ms_count` → chuyển đổi thành p50/p95 bằng biểu thức PromQL.
   - Sidecar polling: chạy `poll_metrics.py` như service hệ thống để gửi log thời gian thực:
     ```bash
     scripts/poll_metrics.py --endpoint http://telemetry:9464/metrics --interval 10 --iterations 0 \
       --metrics jobs_total job_latency_ms_sum job_latency_ms_count >> logs/shadow_metrics.log
     ```

4. **Tinh chỉnh tham số**
   - `APPGPU_BATCH_SIZE` để đổi batch (default 32).
   - `APPGPU_MAX_PIPELINE_CONCURRENCY` để thay đổi số stage song song.
   - Kiểm tra log orchestrator (`uvicorn`) để đảm bảo không timeout.
   - Nếu p95 cao > 70ms → giảm batch size hoặc bật `enable_feature_flags=False` để fallback.
   - Tính toán p95 từ Prometheus: `histogram_quantile(0.95, rate(job_latency_ms_bucket[5m]))`.

5. **Tiêu chí trước cutover**
   - `job_latency_ms` histogram tại telemetry cho thấy p95 ≤ 70ms, p99 ≤ 120ms.
   - `jobs_total` trong shadow ≥ 10k request mà không có lỗi 5xx.
   - GPU SM% trên nền tảng mới ≥ 80% (cần future NVML collector).

6. **Cutover**
   - Tăng shadow ratio lên 50% trong 30 phút, monitor.
   - Nếu ổn định, chuyển routing chính sang orchestrator, giữ monolith ready làm backstop 24h.

## Công cụ hỗ trợ

- `scripts/poll_metrics.py`: poll Prometheus metrics (jobs_total, latency sum/count).
- `docs/baseline_report.md`: ghi nhận base idle + checklist số liệu còn thiếu.
- `docs/hot_path.md`: tham chiếu stage để map metrics ↔ pipeline.

## Quy trình tinh chỉnh chi tiết

1. Lấy snapshot 5 phút một lần:
   ```promql
   rate(job_latency_ms_sum[5m]) / rate(job_latency_ms_count[5m])
   ```
   → latency trung bình.
2. Tính p95/p99 bằng `histogram_quantile` và ghi vào Grafana.
3. Nếu p95 > 70 ms:
   - Giảm `APPGPU_BATCH_SIZE` xuống 24, giữ nguyên concurrency; hoặc
   - Chia pipeline thành nhiều worker bằng cách tăng replicas orchestrator.
4. Nếu throughput chưa đạt 2× baseline:
   - Tăng `APPGPU_MAX_PIPELINE_CONCURRENCY` (tối đa 6) và theo dõi CPU/GPU.
5. Sau mỗi thay đổi, chạy `scripts/poll_metrics.py --interval 15 --iterations 20` để lưu log so sánh trước/sau vào `logs/shadow_metrics.log`.
