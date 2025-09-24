# Integration Test Playbook

1. Chạy `make integration-test`.
2. Pipeline sử dụng `docker-compose.yml` + `tests/integration/docker-compose.override.yml` để dựng core + controller + otel giả lập.
3. Kỳ vọng:
   - REST `/healthz` trả về 200 trong 5 giây.
   - gRPC `SubmitJob` trả về job_id không rỗng.
4. Thu thập metric bằng `curl localhost:9100/metrics` để xác nhận `app_gpu_scheduler_queue_depth` < 200.
