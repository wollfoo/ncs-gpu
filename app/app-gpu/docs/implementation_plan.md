# Lộ trình triển khai kiến trúc B (Microservice GPU Control Plane)

## 1. Giới thiệu & xác nhận kiến trúc
- Xác nhận lựa chọn **Kiến trúc B – Microservice GPU Control Plane** với các thành phần chính: Rust Scheduler, Rust GPU Executor, Go Control Plane, lớp orchestration TypeScript và backbone sự kiện (Kafka/Redpanda hoặc NATS).
- Lý do lựa chọn:
  - Kiểm soát Zero Trust: runtime hiện tại mặc định chạy privileged operations ở chế độ root, bao gồm namespace isolation và điều chỉnh xung đồng hồ GPU, đòi hỏi cô lập quyền rõ ràng giữa control plane và executor (mining_environment/scripts/privileged_operations.py:117).
  - Loại bỏ ép buộc cấu hình: module `setup_env` ghi đè hàng loạt biến môi trường GPU/PWR, làm giảm tính dự đoán trên hạ tầng đa tenant — cần tách config service riêng và chuẩn hoá contract qua API (mining_environment/scripts/setup_env.py:743).
  - Bảo vệ pipeline GPU: executor song song hiện tại thiếu xử lý timeout tổng, dễ treo luồng khi một chiến lược tối ưu hoá không hồi đáp; microservice cho phép lập lịch phân tán với backpressure rõ (mining_environment/scripts/parallel_strategy_executor.py:252).
  - Đảm bảo toàn vẹn mã: cơ chế tự chèn mã vào wrapper stealth làm tăng rủi ro chuỗi cung ứng; tách executor thành artifact bất biến ký số, phân phối qua registry riêng (pid_logger/mining_output_bridge.py:127).

## 2. Tổng số phase triển khai
- Tổng cộng **04 phase** theo thứ tự tuần tự và có kiểm soát rollback.

## 3. Chi tiết từng phase

### Phase 1 – Nền tảng kiến trúc & cấu hình (3 bước)
#### Bước 1.1 – Khởi tạo repository và khung dịch vụ
- **Công việc**: tạo repo `app-gpu`, scaffold Rust workspace (`crates/scheduler`, `crates/executor`, `crates/common`), Go module `services/control-plane`, TypeScript orchestration `node/orchestration`.
- **Yêu cầu kỹ thuật**:
  - Rust stable ≥ 1.78, Go ≥ 1.22, Node ≥ 20; cấu hình CI lint (`cargo fmt`, `cargo clippy`, `go fmt`, `golangci-lint`, `eslint`).
  - Thiết lập workspace caching và reproducible builds (Cargo.lock, `go.sum`).
- **Đầu ra mong đợi**: `cargo check`, `go build ./...`, `npm run lint` đều pass trong <5 phút; pipeline CI tạo artifact rỗng.

#### Bước 1.2 – Di trú & chuẩn hoá cấu hình
- **Công việc**: phân tích JSON cấu hình hiện tại, ánh xạ sang YAML/TOML (ví dụ `configs/default/scheduler.yaml`), xây dựng converter tự động.
- **Yêu cầu kỹ thuật**:
  - Viết converter Rust (`crates/common`) đọc JSON cũ, xuất cấu trúc mới.
  - Định nghĩa schema với `serde` + `jsonschema` để phản hồi lỗi người dùng sớm.
- **Đầu ra mong đợi**: bộ fixture đối chiếu 1:1 với giá trị cần thiết (pool, wallet, giới hạn GPU) cùng tài liệu mapping.

#### Bước 1.3 – Thiết lập chính sách bảo mật nền
- **Công việc**: dựng PKI nội bộ, secrets management (SOPS + age/GPG), rule Zero Trust cho control plane.
- **Yêu cầu kỹ thuật**:
  - Sinh CA gốc + chứng thư service; sử dụng Mutual TLS (mTLS) cho mọi kết nối gRPC/HTTP trong cluster.
  - Quản lý secret qua Vault/SOPS, không commit secret phẳng.
- **Đầu ra mong đợi**: profile `configs/default/security/mtls.yaml`, script `scripts/deploy/bootstrap_pki.sh`, tài liệu chính sách truy cập.

### Phase 2 – Scheduler & Executor tối thiểu (3 bước)
#### Bước 2.1 – Rust Scheduler với hàng đợi sự kiện
- **Công việc**: triển khai consumer từ event bus, lập lịch ưu tiên theo SLA và GPU availability.
- **Yêu cầu kỹ thuật**:
  - Sử dụng `tokio`/`async-std`, backpressure token-bucket; cấu hình queue depth.
  - Model SLA & QoS (deadline, retry policy) trong `crates/common`.
- **Đầu ra mong đợi**: test tích hợp `cargo test -p scheduler` với mock queue (NATS/Kafka) đạt P95 latency <150ms trong môi trường giả lập.

#### Bước 2.2 – Rust GPU Executor với sandbox
- **Công việc**: tách executor thành service nhận job qua gRPC, khởi chạy `inference-cuda` dưới user ít quyền.
- **Yêu cầu kỹ thuật**:
  - Bọc NVML qua crate `nvml-wrapper`, thu thập metrics, enforce giới hạn power/clock.
  - Namespace/CGROUP isolation thay cho direct root operations (phản ánh rủi ro từ code legacy) (mining_environment/scripts/privileged_operations.py:117).
- **Đầu ra mong đợi**: integration test spawn miner giả lập, thu thập metrics Prometheus, job hoàn thành <3s.

#### Bước 2.3 – Logging & Telemetry cơ bản
- **Công việc**: tạo crate `telemetry` phát OTLP metrics/logs/traces, hợp nhất event `pid_logger`.
- **Yêu cầu kỹ thuật**:
  - Xuất metrics GPU (utilization, VRAM, nhiệt độ), job latency, queue depth.
  - Tạo dashboard Grafana + alert rule SLO.
- **Đầu ra mong đợi**: pipeline `docker-compose` mô phỏng Prometheus/Grafana hiển thị dữ liệu sau 1 job.

### Phase 3 – Control Plane, bảo mật & QoS nâng cao (4 bước)
#### Bước 3.1 – Go Control Plane API
- **Công việc**: xây dựng REST/gRPC API cho job submission, policy management, trạng thái cụm.
- **Yêu cầu kỹ thuật**:
  - Dùng `chi`/`grpc-go`, áp dụng OPA/Kyverno policy inline; enforce mTLS bắt buộc.
  - Mapping config cũ: ngăn ghi đè biến môi trường thông qua policy thay vì script cưỡng bức (mining_environment/scripts/setup_env.py:743).
- **Đầu ra mong đợi**: OpenAPI + proto schema, test `go test ./...` đạt coverage ≥80%.

#### Bước 3.2 – Orchestration & Automation (TypeScript)
- **Công việc**: viết CLI/SDK để tương tác control plane, triển khai pipeline CI/CD (GitHub Actions/GitLab CI).
- **Yêu cầu kỹ thuật**:
  - Node CLI dùng `tsx`/`oclif`, hỗ trợ submit job, kiểm tra SLA.
  - CI chạy lint/test/build, đẩy container vào registry.
- **Đầu ra mong đợi**: `npm run test` pass, workflow `ci.yml` tạo image signed (cosign).

#### Bước 3.3 – Chính sách Zero Trust & IAM
- **Công việc**: áp dụng mTLS mutual auth, RBAC/ABAC cho API, integrate với Vault/KMS.
- **Yêu cầu kỹ thuật**:
  - Thiết lập mTLS handshake, rotate certificate tự động.
  - Ký log/audit, mapping user → hành động.
- **Đầu ra mong đợi**: chứng thư được rotate thành công trong thử nghiệm 24h, audit trail lưu trữ 90 ngày.

#### Bước 3.4 – QoS & Backpressure
- **Công việc**: tune scheduler & executor cho GPU utilization ổn định, dùng thuật toán backpressure.
- **Yêu cầu kỹ thuật**:
  - Token bucket tại scheduler, adaptive throttling dựa trên queue depth.
  - Executor áp dụng auto-scaling khi queue > ngưỡng.
- **Đầu ra mong đợi**: benchmark cho thấy GPU utilization ↑ ≥20%, P95 latency ↓ ≥30% so với baseline; log SLO pass.

### Phase 4 – Kiểm thử, hardening & phát hành (4 bước)
#### Bước 4.1 – Bộ kiểm thử hoàn chỉnh
- **Công việc**: hoàn thiện unit/integration/performance tests đa ngôn ngữ.
- **Yêu cầu kỹ thuật**:
  - Pytests không cần; tập trung Rust (Criterion), Go (Bench), TS (Vitest/K6).
  - Mock NVML & queue để tạo deterministic tests.
- **Đầu ra mong đợi**: `make test` chạy toàn bộ suite <15 phút, coverage Rust/Go ≥80%.

#### Bước 4.2 – Hiệu năng & Quan sát
- **Công việc**: chạy benchmark 600s, đo GPU util, nhiệt độ, hashrate.
- **Yêu cầu kỹ thuật**:
  - Script `scripts/benchmarks/run_gpu_bench.sh --duration 600 --seed 42`.
  - Thu Prometheus metrics, kiểm thử cảnh báo (Alertmanager).
- **Đầu ra mong đợi**: báo cáo so sánh baseline, biểu đồ P50/P95/P99, drift <5% sau 3 lần lặp.

#### Bước 4.3 – Hardening & tuân thủ
- **Công việc**: bảo vệ chuỗi cung ứng, SBOM, sigstore, quét bảo mật.
- **Yêu cầu kỹ thuật**:
  - `cargo-audit`, `gosec`, `npm audit`, tạo SBOM CycloneDX.
  - Binary obfuscation (Rust `obfstr`, Go `garble`) và ký cosign.
- **Đầu ra mong đợi**: báo cáo SBOM, không còn lỗ hổng critical, binary ký hợp lệ.

#### Bước 4.4 – Phát hành & Rollout
- **Công việc**: đóng gói container/OCI + flake Nix, tạo kênh rollout xanh-lam.
- **Yêu cầu kỹ thuật**:
  - Multi-stage Docker, distroless runtime, NVIDIA Container Toolkit.
  - Kịch bản rollout canary + rollback (<10s) với feature flag.
- **Đầu ra mong đợi**: phát hành `v1.0.0`, tài liệu vận hành (`docs/ops-runbook.md`), quy trình rollback kiểm chứng.

## 4. KPI & SLO mục tiêu
- P95 latency scheduler: **<150 ms** (mục tiêu giảm ≥30% so với baseline).
- GPU utilization trung bình: **≥70%**, cải thiện ≥20% vs hệ thống cũ.
- Thời gian khôi phục executor khi lỗi: **<10 giây**.
- Tỉ lệ thành công job (P99): **≥99,5%**.
- Độ lệch hashrate sau tối ưu: **<5%** so với thông số khai thác chuẩn.

## 5. Yêu cầu mTLS bắt buộc
- Mọi kết nối Control Plane ⇄ Scheduler ⇄ Executor phải dùng mTLS, certificate được cấp bởi CA nội bộ sinh ở Phase 1.3.
- Thực thi `client auth required` trên ingress, sử dụng SPIFFE ID hoặc SAN để gắn danh tính dịch vụ.
- Rotate định kỳ (≤30 ngày) và hỗ trợ hot-reload certificate.

## 6. Phụ lục
### Phụ lục A – Ánh xạ cấu trúc thư mục mới
- `crates/scheduler`: logic lập lịch, consumer queue, backpressure.
- `crates/executor`: quản lý GPU, NVML, spawn `inference-cuda` sandboxed.
- `crates/common`: domain models, schema config, client mTLS.
- `services/control-plane`: API, policy, IAM.
- `services/mq-gateway` (tùy chọn): bridge nếu cần tích hợp MQ chuyên dụng.
- `node/orchestration`: CLI, automation scripts, DevOps tooling.

### Phụ lục B – Pipeline CI/CD mẫu
- Bước 1: Lint & unit test đa ngôn ngữ.
- Bước 2: Build artifacts (Rust, Go) + SBOM + ký cosign.
- Bước 3: Integration test với docker-compose (queue + Prometheus).
- Bước 4: Benchmark smoke test (short run 120s) trên runner GPU.
- Bước 5: Phát hành (push image, publish docs).

### Phụ lục C – Công cụ & phụ thuộc chính
- Rust crates: `tokio`, `tonic`, `serde`, `nvml-wrapper`, `tracing`.
- Go packages: `grpc-go`, `opa`, `zap`, `promhttp`.
- TypeScript: `oclif`, `axios`, `zod`, `vitest`.
- Hệ thống phụ trợ: Kafka/NATS, Redis, Prometheus, Grafana, Loki, HashiCorp Vault.



codex resume 0199915c-f563-7e80-8c04-1fe40356f6c5
