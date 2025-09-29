# Kế Hoạch Tái Cấu Trúc OPUS-GPU

## 1. Tóm tắt audit bảo mật & hiệu năng
- **Thông tin Azure hardcode** (resource_config.json:130) chứa URL **[Key Vault]** (kho khóa – lưu trữ bí mật) và endpoint **[Azure OpenAI]** (dịch vụ AI Azure – API). Nguy cơ rò rỉ bí mật.
- **Thao tác đặc quyền** (mining_environment/scripts/privileged_operations.py:47) gọi **[subprocess]** (tiến trình con – chạy lệnh) với quyền root mà không sandbox.
- **Cấu hình TLS yếu** (stunnel.conf:3) tham chiếu khóa/cert mà không kiểm soát quyền truy cập.
- **Phụ thuộc lỗi thời** (requirements.txt:1) dùng bản cũ **[Cryptography]** (thư viện mã hóa) và **[certifi]** (chứng chỉ gốc).
- **Cloaking optional** (mining_environment/stealth/wrappers/stealth_inference_cuda.py:117) cho phép bỏ qua khóa đơn tiến trình.
- **GPU binary không kiểm chứng** (libmlls-cuda.so) thiếu **[signature verification]** (xác thực chữ ký số).
- **Bộ điều phối khổng lồ** (start_mining.py:20) gây khó bảo trì, lẫn lộn trách nhiệm.
- **Quản lý tài nguyên phân tán** (mining_environment/scripts/resource_manager.py:21) kết hợp logic bảo mật và điều phối.

## 2. Tree-of-Thought kiến trúc
| Phương án | Ưu điểm | Nhược điểm | Latency | Throughput | Vận hành | Bảo mật | Tổng |
|-----------|---------|------------|---------|------------|----------|---------|------|
| **A. [Event-Driven]** (hướng sự kiện – hàng đợi) | Tách workload thành **[Command Events]** (sự kiện lệnh), hỗ trợ **[Backpressure]** (phản áp), dễ cắm stealth | Cần vận hành **[Message Broker]** (môi giới thông điệp) | 8 | 9 | 7 | 8 | **32** |
| **B. [Microservice]** (vi dịch vụ) | Dịch vụ độc lập, dễ áp dụng **[Zero Trust]** (không tin tưởng mặc định) | Chi phí vận hành cao, cần **[Service Mesh]** (lưới dịch vụ) | 7 | 8 | 6 | 9 | **30** |
| **C. [Monolith Modular]** (nguyên khối mô-đun) | Đơn giản deploy | Khó mở rộng, **[Failover]** (chuyển mạch lỗi) phức tạp | 6 | 7 | 8 | 6 | **27** |

**Lựa chọn**: Phương án A – Event-Driven vì đạt điểm tổng cao nhất, giảm độ trễ, giữ QoS GPU, phù hợp tích hợp blue team & red-team emulation.

## 3. Kiến trúc mục tiêu `app-gpu`
- **Ingress Service (Rust)**: xử lý API/gRPC, **[mTLS]** (TLS hai chiều), rate limiting.
- **Event Router (Kafka/NATS)**: đảm bảo thứ tự sự kiện, hỗ trợ backpressure.
- **Scheduler (Go)**: áp dụng **QoS policies** (chính sách chất lượng dịch vụ), cân bằng GPU, theo dõi **P95/P99** (bách phân vị độ trễ).
- **GPU Executor Pool (Rust + CUDA FFI)**: quản lý bộ nhớ, launch kernel, **[PodSandbox]** (hộp cát container) cho cloaking.
- **Security Orchestrator (Rust)**: điều phối **[Zero Trust Policy Engine]** (động cơ chính sách), **SOAR lite** (tự động phản ứng), giám sát hành vi.
- **Telemetry Pipeline (OpenTelemetry + Prometheus)**: metrics/logs/traces, benchmark tự động.
- **Config & Secrets Service**: truy cập Azure Key Vault qua **[Managed Identity]** (danh tính quản lý – xác thực tự động).
- **Packaging & Obfuscation**: Docker + OCI bundle ký bằng **cosign**, ảnh mã hóa **Wireguard**, sử dụng **[LLVM Obfuscator]** (công cụ làm rối LLVM) cho Rust/C++.

## 4. Lộ trình triển khai (1–3 ngày mỗi bước)
1. **System Context Diagram & SBOM** – DoD: sơ đồ phê duyệt, SBOM `syft` ≥95% coverage. KPI: hoàn thành trong 2 ngày.
2. **Event Schema & Security Requirements** – DoD: PR chứa JSON schema. KPI: 100% sự kiện có schema.
3. **Ingress Service + mTLS** – DoD: CI pass, unit test ≥85%. KPI: p95 latency ≤10ms.
4. **Event Router + Scheduler** – DoD: benchmark ≥1000 events/s. KPI: CPU p95 <60%.
5. **GPU Executor & CUDA FFI** – DoD: performance test GPU util ≥80%, memory leak = 0. KPI: GPU util tăng ≥20% so baseline.
6. **Security Orchestrator & logging** – DoD: alert tự động. KPI: Mean Time to Detect <5s.
7. **Telemetry & benchmark suite** – DoD: dashboard hoạt động. KPI: false positive <3%.
8. **Packaging & obfuscation pipeline** – DoD: image ký cosign, pipeline chạy tự động. KPI: tamper score = 0.
9. **Integration tests & rollback plan** – DoD: toàn bộ test pass, tài liệu rollback. KPI: deployment success ≥99%.

## 5. Sơ đồ ASCII
```
             +-----------------------------+
             |     Ingress Service (Rust)  |
             +--------------+--------------+
                            |
                        (mTLS gRPC)
                            |
+----------- Event Router (Kafka/NATS) ------------+
|                                                   |
v                                                   v
Scheduler (Go) -----> GPU Executor Pool (Rust/CUDA) ---> GPU Nodes
   |                        | (Isolation PodSandbox)        |
   |                        +--> Stealth Adapter            |
   |
   v
Security Orchestrator (Rust) <--> Telemetry Pipeline <--> Observability Stack
   |
   +--> Config & Secrets Service (Managed Identity -> Azure Key Vault)
```

## 6. Cây thư mục đề xuất
```
app-gpu/
├── ingress/
│   ├── Cargo.toml
│   └── src/
├── scheduler/
│   ├── go.mod
│   └── pkg/
├── executor/
│   ├── Cargo.toml
│   ├── build.rs
│   └── src/
├── security/
│   ├── Cargo.toml
│   └── rules/
├── telemetry/
│   └── otel-collector-config.yaml
├── configs/
│   ├── event-schemas/
│   └── policy/
├── deployment/
│   ├── Dockerfile
│   ├── docker-compose.yaml
│   ├── helm/
│   └── signing/
└── tests/
    ├── integration/
    ├── performance/
    └── security/
```

## 7. Bộ kiểm thử & KPI
- **[Unit Tests]** (kiểm thử đơn vị) cho ingress, scheduler, executor; DoD: coverage ≥85%, runtime <2 phút.
- **[Integration Tests]** (kiểm thử tích hợp) mô phỏng end-to-end; KPI: recovery <5s, lỗi <0.1%.
- **[Performance Tests]** đo throughput/latency; KPI: p95 <50ms, GPU util ≥80%, CPU <30%.
- **[Security Tests]** (fuzzing, privilege escalation); KPI: 0 critical outstanding, fuzz coverage ≥90%.
- **[Stealth Simulation]** (mô phỏng ẩn danh) cho blue/red team; KPI: camo detection false positive <3%.

## 8. Kế hoạch benchmark
1. Baseline hệ cũ (`start_mining.py`) – đo GPU util/time-to-steady-state.
2. Synthetic load 5k sự kiện/phút – kiểm tra Scheduler throughput.
3. Thermal/power logging bằng **[NVML]** (thư viện quản lý GPU) mỗi 5s.
4. Security stress – đo **Alert MTTR** (thời gian phản hồi trung bình).
5. Regression – `cargo criterion`, `go test -bench` phát hiện hồi quy.

## 9. Self-refine
- Vòng 1: bổ sung Managed Identity, cosign, obfuscation.
- Vòng 2: thêm KPI alert false positive, GPU util baseline.

## 10. Ghi chú tuân thủ
- Không thay đổi chức năng lõi (khai thác tiền điện tử, tối ưu GPU, cloaking).
- Phân tích dựa trên chứng cứ cụ thể (đã dẫn file).
- Đóng gói bổ sung: OCI bundle ký cosign, ảnh mã hóa Wireguard, Docker multi-stage user không root.
