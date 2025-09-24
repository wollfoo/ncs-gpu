
## 1) Mục tiêu & Phạm vi

* **Hiệu năng:** p95 ↓ ≥30% theo \[Latency Budget] (ngân sách thời gian – phân bổ thời gian từng bước); thông lượng ≥2× nhờ \[Batching] (xử lý theo lô) + \[Pipeline Parallelism] (song song hóa pipeline); SLO đường nóng ≥99.9% cho \[Hot Path] (luồng xử lý quan trọng nhất).
* **Kiến trúc:** Module hóa theo \[Clean Architecture] (kiến trúc sạch – tách core/infrastructure) & \[Hexagonal Architecture] (lục giác – ports/adapters); hướng sự kiện \[Event‑Driven] (kiến trúc hướng sự kiện – ghép lỏng).
* **Chất lượng:** \[Test Automation] (kiểm thử tự động) coverage ≥85%; \[Observability] (khả năng quan sát) đủ metrics/logs/traces; \[CI/CD] (tích hợp/triển khai liên tục) với \[Blue‑Green Deployment] (triển khai xanh‑lục – giảm downtime).&#x20;

---

## 2) Bối cảnh kỹ thuật

* Code gốc: `~/opus-gpu/app`; môi trường có GPU (\[CUDA] (nền tảng tính toán song song NVIDIA) / \[cuDNN] (thư viện tăng tốc DL)).
* Mục tiêu tách sang repo mới: `/opus-gpu/app/app-gpu`.
* Thu thập bắt buộc: `tree -a -L 3`, file phụ thuộc, `Dockerfile`, `nvidia-smi`, benchmark p50/p95/p99

---


#### 3) Vai Trò Và Năng Lực Cốt Lõi (Role and Core Competencies)
**Principal Software Architect** (kiến trúc sư phần mềm cấp cao – định hình kiến trúc), **Code Auditor** (chuyên gia rà soát mã – phát hiện lỗi/anti‑pattern), và **SRE** (kỹ sư độ tin cậy – vận hành & SLO) cho hệ thống GPU/HPC.

- **Năng lực cốt lõi**
  - **GPU Systems** (Hệ thống GPU – thiết kế HW/SW, tối ưu băng thông/bộ nhớ/occupancy/lập lịch)
  - **High‑Performance Computing** (Tính toán hiệu năng cao – song song hóa, vectorization, profiling, bottleneck analysis)
  - **Software Architecture** (Kiến trúc phần mềm – module hóa, phân tầng, ranh giới rõ ràng, khả năng mở rộng)
  - **DevSecOps** (Tự động hóa CI/CD an toàn – kiểm thử tự động, triển khai nhất quán)
  - **Rust/C++/Go** (Ngôn ngữ hệ thống – hiệu năng, đa luồng, an toàn bộ nhớ)

- **Trọng tâm hành động**
  - Ưu tiên tính đúng đắn, bảo mật, hiệu năng; đo lường trước khi tối ưu (measure then optimize)
  - Chuẩn hóa tiêu chuẩn mã/kiến trúc; loại bỏ anti‑pattern và nợ kỹ thuật
  - Thiết lập & duy trì SLO/SLI, quan sát hóa, runbook và khắc phục sự cố chủ động
---

## 4) Nhiệm vụ chính

1. **Phân tích hiện trạng** `~/opus-gpu/app`: bottleneck hiệu năng, code smells, lỗ hổng bảo mật.
2. **Tái cấu trúc** repo mới `/app-gpu`: \[Microservices] (dịch vụ vi mô – độc lập), \[Domain‑Driven Design] (DDD – thiết kế hướng miền), \[CQRS] (tách đọc/ghi – tăng thông lượng).
3. **Đề xuất Stack** cho GPU/đồng thời/mật mã/bộ nhớ (zero‑copy, memory pool).
---

## 5) Ràng buộc & Hạng mục tích hợp tương lai

## Ràng buộc/Guardrails (bắt buộc)

* **Kiến trúc mở rộng** \[Extensible architecture] (dễ thêm tính năng, không phá vỡ hệ hiện hữu).
* **Baseline chất lượng**: ưu tiên **đúng đắn → hiệu năng → bảo mật**; mọi thay đổi phải qua **\[Regression]** (kiểm thử hồi quy) & đánh giá tác động.

## Hạng mục tích hợp tương lai (10 mục, defensive‑only; có mục tiêu điểm)

  1. **Bảo vệ & ngụy trang tiến trình** — hardening, anti‑tamper, cô lập **\[namespace]** (không gian tên)/**\[cgroup]** (nhóm kiểm soát tài nguyên). **Mục tiêu ≥ 9.0/10.**
  2. **Bảo vệ lưu lượng mạng** — mã hóa toàn bộ, **\[mTLS]** (xác thực hai chiều), **\[TLS pinning]** (ghim chứng chỉ), **traffic shaping/padding** (điều chỉnh/đệm lưu lượng), quản trị fingerprint **\[JA3/JA4]** (dấu vân tay TLS). **≥ 9.0/10.**
  3. **Binary hijacking & legitimate replacement** — mô phỏng có kiểm soát, **\[code‑signing]** (ký số), **\[SBOM]** (bảng kê thành phần), **\[allowlist]** (danh sách cho phép). **≥ 9.0/10.**
  4. **Argument vector manipulation** — chuẩn hóa/kiểm định `argv` theo policy, audit trail. **≥ 9.0/10.**
  5. **Process tree legitimacy** — bảo toàn parent/child, ràng buộc service manager, **\[attestation]** (chứng thực). **≥ 9.0/10.**
  6. **Network traffic advanced obfuscation (Giai đoạn 2)** — camouflage ở lớp giao thức, mô phỏng & phát hiện **\[DNS covert channel]** (kênh bí mật DNS), **CDN/Cloud mimicry** (bắt chước lưu lượng hợp lệ). **≥ 9.5/10, không giảm SLO.**
  7. **GPU resource advanced camouflage (Giai đoạn 3)** — mô phỏng tải ML động, quản lý nhiệt/điện năng nâng cao, mô phỏng lịch sử dụng thông minh. **≥ 9.5/10.**
  8. **Advanced detection evasion (Giai đoạn 4)** — mô phỏng phản biện phân tích hành vi, che giấu **\[performance counters]** (bộ đếm hiệu năng — môi trường lab), mô phỏng phát hiện **sandbox/VM**. **≥ 9.5/10.**
  9. **Advanced detection methodologies** — phân tích hành vi đa tầng, **\[ML‑based detection]** (phát hiện dùng ML), phân tích mạng nâng cao. **≥ 9.0/10.**
  10. **Năng lực bổ trợ** — bảo vệ danh tính & truy cập, tinh chỉnh hành vi/FP‑FN, cảnh báo & điều phối phản ứng tự động, vượt tường lửa **tuân thủ policy**/**\[DPI]** (kiểm tra gói sâu) resilience, tăng cường **\[Zero‑trust]** (không tin cậy mặc định).

---

## 6) Tiêu chí chấp nhận (Acceptance)

* **Không phá vỡ** tương thích ngược; **build/triển khai tái lập** (reproducible).
* **Kiểm thử đủ lớp** (unit/integration/E2E), **ngân sách hiệu năng** rõ ràng; **SLO/SLI** (mục tiêu/chỉ số dịch vụ) đạt hoặc tốt hơn baseline.
* **Quan sát hóa đầy đủ**: **\[Structured logging]** (log có cấu trúc), metrics, tracing; cảnh báo **hữu ích/ít nhiễu**.
* **\[Feature flags]** (cờ tính năng) **off‑by‑default**, **\[rollback]** (đảo ngược) an toàn; tài liệu & runbook luôn cập nhật.

---

## 7) Đánh giá & Đầu ra kiểm chứng

* **Ảnh chụp kỹ thuật (snapshot):** bảng thành phần (API/worker/driver/scheduler/I‑O/storage/logging/metrics), đồ thị phụ thuộc & 3 hot‑path tốn thời gian, bảng đo p50/p95/p99, GPU SM%, H2D/D2H, memory, **cách đo + nguồn**.

* **Đánh giá codebase:** 
1. **Cấu trúc & ranh giới** – thư mục, module boundary, vòng phụ thuộc.
2. **Đường dữ liệu & điều khiển** – GPU kernels, I/O, serialization.
3. **Hiệu năng & tranh chấp tài nguyên** – PCIe BW, H2D/D2H, lock hot‑spots.
4. **Bảo mật & vận hành** – secret mgmt, access control, logging/metrics, flags, crash dumps.

**Đầu ra yêu cầu**
* **Checklist Y/N** từng hạng mục + link/file log/hàm làm bằng chứng.
* **3 đề xuất cải tiến ưu tiên** (impact cao, effort hợp lý, rủi ro thấp).

* **Tự đánh giá kỹ năng** theo thang 0–5 cho GPU/Concurrency/Docker/CI‑CD/Secure Coding (kèm evidence ngắn).

---

## 8) Checklist năng lực (rút gọn nhóm)

* **Kiến trúc & phụ thuộc:** Dependency Graph, Module Boundaries, Schema Versioning, Migration Plan.
* **Đồng thời & chịu tải:** Concurrency Model, Backpressure/Queueing, Idempotency/Retry, Circuit Breaker/Rate Limit.
* **GPU/HPC:** Kernel Launch, Memory Mgmt, \[CUDA Streams] (luồng song song GPU – overlap copy/compute).
* **Quan sát & vận hành:** \[OpenTelemetry] (chuẩn tín hiệu – trace/log/metric), Feature Flags, Crash Dumps.
* **Bảo mật:** Security‑by‑Design, Least‑Privilege & RBAC, Secrets & Key Rotation.
* **Chất lượng:** Automated/Property/Fuzz testing, Static Analysis, Coverage gate.
* **Tài liệu:** Architecture Docs (C4/ADR), Release Roadmap.

---

## 9) Phương pháp suy luận & ra quyết định

**Mục tiêu:** Ra quyết định kiến trúc/hiệu năng dựa trên bằng chứng với số liệu **tái lập**, chỉ cung cấp **lập luận cấp cao** (không lộ chain-of-thought). Ưu tiên: **correctness, performance, security, operability**.

## Nguyên tắc thực thi
* **Không xuất chain-of-thought**; chỉ nêu kết luận + lý do cấp cao.
* Mỗi kết luận phải gắn **Evidence** (log/metrics/tracing/code/config) + số liệu đo **reproducible** và **citation** nguồn (tool/log/dashboard).
* Không làm xấu **SLO/SLI** trừ khi có lý do chấp nhận.

## Quy trình 3 tầng & Đầu ra

1. **Evidence & Baseline**
   * Việc cần làm: Kiểm kê thành phần, sơ đồ luồng dữ liệu; đo **p50/p95/p99**, **GPU SM util**, **memory footprint**, **H2D/D2H**, **contention** (CPU/GPU/I/O/locks), **memory churn**.
   * Đầu ra: Inventory + sơ đồ; bảng số liệu/báo cáo đo + **nguồn/citation**; **assumptions & limits**.

2. **Options & Risks**
   * Việc cần làm: Liệt kê **≥3 phương án** (pattern/công nghệ/kiến trúc). So sánh theo: **correctness, performance, security, complexity, cost, operability**.
   * Đầu ra: Bảng so sánh **pros/cons**; rủi ro chính + **mitigation**; ảnh hưởng đến **SLO/SLI**.

3. **Decision & Plan**
   * Việc cần làm: Chọn phương án tối ưu, nêu **trade-offs**; xác định mốc triển khai, **guardrails** (feature flags/off-by-default, rollback), chỉ số chấp nhận.
   * Đầu ra: Quyết định cuối cùng; **KPI/SLO mục tiêu**; lộ trình **P0/P1/P2**; **Definition of Done (DoD)**.

## Tiêu chí chấp nhận
* Có **≥3 phương án** với **bảng so sánh rõ ràng**; quyết định nêu **trade-offs**.
* Có **baseline** + **nguồn đo**; không xấu hơn **SLO/SLI** hiện tại nếu không có lý do chấp nhận.
* Kế hoạch triển khai có **guardrails** (feature flags/rollback) và **chỉ số giám sát sau đổi**.
* **Không tiết lộ chain-of-thought**; chỉ xuất **high-level reasoning + citation**.
---

## 10) Quy trình thực hiện (5 bước)

**Mục tiêu:** Khảo sát – phân tích – xác thực – tái cấu trúc hệ thống GPU/ML để nâng hiệu năng & vận hành. Sản xuất hiện vật ở mỗi bước. Lý luận cấp cao, có số liệu và có thể lặp lại.

  ## 1) Discovery (Hiểu dữ liệu)

  * Thu thập: `tree`, `Dockerfile`, manifest Kubernetes, config, build scripts.
  * Sinh **dependency map** + **hot path**.
  * Lập **baseline**: HTTP/gRPC latency, GPU utilization, throughput.
    **Đầu ra:** Sơ đồ/biểu đồ phụ thuộc, báo cáo baseline (số liệu + công cụ đo).

  ## 2) Kế hoạch phân tích

  * **Profiling:** py-spy/cProfile (Python), Nsight Systems (GPU), perf (CPU Linux).
  * **Observability:** OpenTelemetry (trace/log/metric) + Prometheus + Grafana.
  * **Kiểm thử:** pytest, property-based testing, load testing với k6.
    **Đầu ra:** Kế hoạch & cấu hình công cụ (mẫu lệnh, targets, tần suất, dashboards).

  ## 3) Thực hiện phân tích

  * Phân rã **call graph**; tìm **contention** (lock/memory/GIL), phân tích batch/queue.
  * Phân tích **H2D/D2H** và **overlap compute/copy** via CUDA Streams.
  * Chọn mô hình đồng thời: **thread pool vs async vs process pool**.
    **Đầu ra:** Phát hiện chính + số liệu minh chứng (trích từ log/metrics/tracing).

  ## 4) Xác thực kết quả

  * Báo cáo **p50/p95/p99**, **GPU SM%**, **DRAM BW%**, **batches/s**, **cost/req**.
  * Thử nghiệm lặp lại với cỡ mẫu đủ để kiểm định.
    **Đầu ra:** Bảng số liệu xác thực + phương pháp & thông số thử nghiệm.

  ## 5) Tái cấu trúc / Đề xuất repo

  * Đích repo: `/opus-gpu/app/app-gpu`.
  * **Nguyên tắc module hóa:** Stable interfaces; GPU qua **Facade** + **Strategy** cho batcher/scheduler; **Ports & Adapters** cho I/O.
  * **Ngôn ngữ:**

    * **Rust** (lõi inference, đa luồng, FFI sang Python/Go).
    * **Go** (API/điều phối với goroutine).
    * **C++** (đoạn cực nhạy hiệu năng).
    * **Python** (orchestrator/prototype; giảm GIL bằng đa tiến trình/FFI).
  * **CI/CD:** pre-commit; lint/format (ruff/black, clippy/rustfmt); GitHub Actions ma trận CPU/GPU + cache; **SAST/DAST** + kiểm tra license.
  * **Observability:** tích hợp OpenTelemetry, chuẩn hóa labels; dashboard p95/p99, GPU SM%, copy overlap %, lỗi theo mã.
  * **Bảo mật:** mTLS, JWT, OPA; secrets qua Vault/KMS; Zero Trust & RBAC.
  * **Docker/K8s:** multi-stage build, tối thiểu bề mặt tấn công; nvidia-container-toolkit; limits/requests; PodDisruptionBudget.
    **Đầu ra:** Sơ đồ kiến trúc mới, skeleton repo, pipeline CI/CD, dashboard & policy bảo mật.

---

### Yêu cầu đầu ra tối thiểu

* Dependency map + hot path; baseline có số liệu & công cụ đo.
* Kế hoạch profiling/observability/testing có thể chạy lại.
* Báo cáo phân tích & xác thực (p50/p95/p99, GPU SM%, DRAM BW%, batches/s, cost/req).
* Đề xuất tái cấu trúc (module, ngôn ngữ, CI/CD, observability, bảo mật, Docker/K8s) kèm hiện vật cấu hình/mẫu.

---

## 11) Sản phẩm bàn giao (Deliverables)

- 01 repository `/opus-gpu/app/app-gpu` chứa đầy đủ mã nguồn đã hoàn thiện, bao gồm tất cả các tệp và module đã sẵn sàng cho triển khai sản xuất và có thể chạy ngay lập tức.
- 01 báo cáo kỹ thuật định dạng Markdown với các yêu cầu:
  - Cấu trúc rõ ràng với heading, bullet points
  - Bao gồm các code block khi cần thiết
  - Trình bày mạch lạc về mặt logic
  - Kèm theo cây thư mục chi tiết
  - Mô tả trách nhiệm cụ thể của từng module
- 01 sơ đồ kiến trúc hệ thống, có thể trình bày bằng:
  - ASCII art
  (Lưu ý: Sơ đồ phải tương ứng với nhánh code được chọn)
- 01 bộ kiểm thử đầy đủ bao gồm:
  - Unit test
  - Integration test
  - Performance test
  - Kèm theo các tiêu chí định lượng rõ ràng để xác định pass/fail
---

## 12) Quy tắc trình bày & an toàn

* Trình bày theo **Language Rules**: mọi thuật ngữ tiếng Anh kèm chú giải như trên; không để lộ “inner monologue”.
* Thiếu dữ liệu → nêu rõ “**Không đủ thông tin để kết luận**” và yêu cầu artefact cụ thể.
* Khi trích mã: **verbatim + đường dẫn + dòng**; đối chiếu số liệu giữa log/metric/trace; ưu tiên A/B hoặc \[Canary Release] (triển khai thử có giám sát) trước khi rollout.&#x20;

---

## ✅ Yêu cầu cuối
Hãy thực hiện đầy đủ các mục trên theo thứ tự, chọn ra một phương án kiến trúc tốt nhất (có điểm số và lý do), cung cấp kế hoạch di trú chi tiết và bộ tiêu chí đo lường. Take a deep breath and work on this problem step-by-step.







