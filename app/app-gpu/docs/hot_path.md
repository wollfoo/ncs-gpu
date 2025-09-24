# Hot Path (Luồng nóng)

1. **Control Plane** nhận cấu hình SLO/SLA và đẩy xuống Orchestrator qua REST.
2. **API Gateway** nhận job (`/jobs`), chuẩn hóa payload → tạo `SubmitJobCommand`.
3. **Application Layer** sinh `MiningJob` + tính `PriorityClass`, lập `Batch` kích thước 32.
4. **Scheduler** chạy pipeline ba stage:
   - `preprocess`: chuẩn hóa feature, xác minh deadline.
   - `inference`: gọi Rust service (hoặc fallback numpy) với song song hóa pipeline.
   - `postprocess`: tổng hợp metrics, route sang Telemetry.
5. **Message Bus** publish `BatchDispatched` + `StageCompleted` để cập nhật SLO + Prometheus.
6. **Telemetry Exporter** từ Prometheus phục vụ scrape, SRE theo dõi p50/p95/p99, SM%, DRAM BW.

Các điểm đo latency:
- API ingress (FastAPI middleware).
- Batch dispatch -> inference start.
- Inference completion -> publish StageCompleted.
