# Lộ trình Nâng Cấp Production Ready cho Opus GPU

## Phase 0 – Củng cố nền tảng
- **Mục tiêu**: Thiết lập baseline ổn định cho control-plane/data-plane, thống nhất cấu hình build/test và cập nhật tài liệu trước khi mở rộng chức năng.
- **Công việc cụ thể**:
  - Hoàn thiện pipeline build đa ngôn ngữ (Rust/Go/Node) và đảm bảo lệnh `make test` chạy thành công trong CI.
  - Chuẩn hóa cấu trúc repository (Helm, Terraform, security) và cập nhật README, runbook phản ánh trạng thái hiện tại.
  - Ghim phiên bản compiler/runtime và thiết lập quy ước branching, review.
- **Tiêu chí hoàn thành**:
  - Toàn bộ target `fmt`, `lint`, `test` chạy thành công trên môi trường CI.
  - Tài liệu kiến trúc và runbook không còn thông tin “TODO”.
- **Ước lượng thời gian**: 1 tuần.
- **Rủi ro & Giải pháp**:
  - Thiếu tài nguyên CI đa nền tảng → Sử dụng matrix build tự lưu trữ hoặc GitHub Actions với runner GPU giả lập.
- **Bên liên quan**: Nhóm Platform, DevOps.

## Phase 1 – Hoàn thiện lõi xử lý GPU
- **Mục tiêu**: Biến executor từ mô phỏng thành pipeline GPU thực thụ và bổ sung lưu vết trạng thái job.[^1]
- **Công việc cụ thể**:
  - Tích hợp CUDA kernel hoặc binding tới `inference-cuda`/FFI và đảm bảo quản lý tài nguyên GPU an toàn.[^1]
  - Thiết kế kho trạng thái (PostgreSQL/Redis) lưu job lifecycle và expose API truy vấn từ scheduler.[^2]
  - Định nghĩa schema payload, validation và mapping sang kernel.
- **Tiêu chí hoàn thành**:
  - Job end-to-end chạy trên GPU thật, trả ACK kèm trạng thái trong store.
  - Benchmark nhỏ xác nhận độ chính xác kết quả so với kỳ vọng.
- **Ước lượng thời gian**: 3 tuần.
- **Rủi ro & Giải pháp**:
  - Sai lệch hiệu năng kernel mới → Triển khai profiling CUDA và fallback sang binary cũ.
  - Deadlock GPU khi đa tiến trình → Áp dụng worker isolation và health monitor GPU.
- **Bên liên quan**: Platform, GPU Engineering, QA.

## Phase 2 – Gia cố bảo mật & quản lý bí mật
- **Mục tiêu**: Đáp ứng yêu cầu Zero Trust: mTLS, secret management, audit logging cho toàn bộ control-plane.[^3][^4]
- **Công việc cụ thể**:
  - Thiết lập CA nội bộ, cấp chứng chỉ dịch vụ cho API Gateway ↔ Scheduler ↔ Executor; cập nhật client `nats-lite` hỗ trợ TLS.
  - Tích hợp Vault/KMS để phát hành Bearer token, rotating secret và loại bỏ phụ thuộc biến môi trường tĩnh.[^4]
  - Bổ sung audit log job request/response và lưu trữ tối thiểu 30 ngày.
- **Tiêu chí hoàn thành**:
  - Tất cả traffic nội bộ yêu cầu TLS mutual và kiểm thử thành công.
  - Rotation secret tự động với alert khi thất bại.
- **Ước lượng thời gian**: 2 tuần.
- **Rủi ro & Giải pháp**:
  - Phức tạp khi triển khai TLS cho NATS → Dùng staging cluster với cert tạm, thêm test integration TLS.
  - Vault downtime → Thiết kế caching token tại gateway và cơ chế retry exponential backoff.
- **Bên liên quan**: Security, DevOps, Platform.

## Phase 3 – Độ tin cậy & Quan sát
- **Mục tiêu**: Nâng cao health-check, retry/backpressure và mở rộng quan sát hệ thống.[^5][^6][^7]
- **Công việc cụ thể**:
  - Mở rộng `/health` trả về trạng thái NATS, store, metrics exporter; thêm `/jobs/{id}` trả job status.[^5][^7]
  - Bổ sung retry khi publish thất bại, hàng đợi đệm và dead-letter queue cho executor.[^6]
  - Viết test integration scheduler ↔ NATS ↔ executor, kèm test giả lập network partition.[^3]
  - Tích hợp OpenTelemetry trace, correlate với metrics hiện hữu.[^8]
- **Tiêu chí hoàn thành**:
  - Test integration chạy tự động trong CI/CD.
  - SLA health endpoint phản ánh chính xác tình trạng phụ thuộc.
- **Ước lượng thời gian**: 3 tuần.
- **Rủi ro & Giải pháp**:
  - Test end-to-end flakey vì NATS thật → Dùng container nats-server nội bộ và seed deterministic.
  - Thêm retry gây trùng job → Thiết kế idempotent handler, dùng status lock trong store.
- **Bên liên quan**: Platform, QA, SRE.

## Phase 4 – Hiệu năng & khả năng mở rộng
- **Mục tiêu**: Đạt mục tiêu throughput/latency với autoscaling và benchmark đáng tin cậy.[^8][^9]
- **Công việc cụ thể**:
  - Chạy `tooling/scripts/bench_scheduler.sh`, đo P95/P99 latency, CPU/GPU utilization và tối ưu nút cổ chai.[^8]
  - Thêm thực thi song song đa GPU, cân bằng tải và pin bộ nhớ GPU trong executor.[^9]
  - Viết manifest Helm/Kubernetes hoàn chỉnh cho scheduler/executor/observability, cấu hình HPA/KEDA dựa trên metrics hàng đợi.[^8]
  - Thiết lập cảnh báo Prometheus cho backlog, lỗi ACK, độ trễ cao.[^8]
- **Tiêu chí hoàn thành**:
  - Benchmark đạt ngưỡng KPI chấp thuận (định nghĩa bởi Product + SRE).
  - Autoscaling phản ứng trong vùng thời gian mục tiêu và dashboard cung cấp số liệu realtime.
- **Ước lượng thời gian**: 4 tuần.
- **Rủi ro & Giải pháp**:
  - KPI chưa xác định → Tổ chức workshop với Product/SRE đặt ngưỡng cụ thể.
  - Thay đổi kernel ảnh hưởng chất lượng → Thiết lập canary release và theo dõi metric sai số.
- **Bên liên quan**: SRE, Platform, Product.

## Phase 5 – Tuân thủ & triển khai production
- **Mục tiêu**: Đáp ứng checklist production-readiness, hoàn thiện runbook, security review và quy trình vận hành cuối.[^10]
- **Công việc cụ thể**:
  - Hoàn thiện tài liệu runbook (failover, rollback, incident response) và đảm bảo sbom cập nhật mỗi build.
  - Thực hiện STRIDE review, pen-test và khắc phục phát hiện.
  - Chạy rehearsal cutover, DR drill và xác nhận quy trình hỗ trợ 24/7.
  - Chuẩn bị báo cáo tuân thủ, bao gồm retention log ≥30 ngày.[^3]
- **Tiêu chí hoàn thành**:
  - Checklist production-ready được tick đầy đủ và thông qua bởi Steering Committee.[^10]
  - Runbook, dashboard, cảnh báo vận hành sẵn sàng cho on-call.
- **Ước lượng thời gian**: 3 tuần.
- **Rủi ro & Giải pháp**:
  - Pen-test phát hiện lỗ hổng nghiêm trọng → Dự phòng buffer thời gian 1-2 sprint để khắc phục.
  - Thiếu nguồn lực on-call → Training chéo và lập lịch trực trước khi go-live.
- **Bên liên quan**: Security, Compliance, SRE, Support, Product.

---

[^1]: docs/production-readiness.md:8
[^2]: docs/production-readiness.md:9
[^3]: docs/production-readiness.md:10
[^4]: docs/production-readiness.md:20-22
[^5]: docs/production-readiness.md:14
[^6]: docs/production-readiness.md:15
[^7]: docs/production-readiness.md:16
[^8]: docs/production-readiness.md:26-28
[^9]: docs/production-readiness.md:27
[^10]: docs/production-readiness.md:33-49
