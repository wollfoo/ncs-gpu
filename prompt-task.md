## ✅ Language Rules
- **MANDATORY**: Trả lời **tiếng Việt**.
- **WITH EXPLANATION**: Mọi thuật ngữ tiếng Anh phải kèm mô tả theo cú pháp **[English Term] (mô tả tiếng Việt – chức năng/mục đích)**.
- **Standard Syntax**: **[English Term] (mô tả – chức năng/mục đích)**.
---
## 🗂️ Bối Cảnh Kỹ Thuật
- Toàn bộ codebase nằm trong `directory: ~/opus-gpu/app`.
- Docker image: build từ **[Dockerfile] (tệp mô tả build – tạo ảnh)**, 
---
## 🎯 Nhiệm vụ
- Phân tích, rà soát kỹ codebase trong `~/opus-gpu/app`.
- Đề xuất & thiết kế tái cấu trúc thành repo mới hoàn toàn ( không tương thích ngược API ) `~/opus-gpu/app/app-gpu` đáp ứng:
  1) **Giảm độ trễ**: tối ưu luồng xử lý, giảm phụ thuộc giữa **[module] (mô-đun – đơn vị chức năng)**.
  2) **Loại bỏ lỗi tiềm ẩn**: kiểm thử tự động + **[Defensive Design]**.
  3) **Module hóa**: dễ quản lý, bảo trì và mở rộng an toàn.
  4) **Mở rộng an toàn**: thêm tính năng mới **không phá vỡ** chức năng cốt lõi hoặc ảnh hưởng đến chức năng cốt lõi.

## Phạm vi chức năng chính Tương lai tích hợp các chức năng sau:

**Nhóm bảo vệ/hardening (blue team)**

* Bảo vệ & “ngụy trang” tiến trình quan trọng của hệ thống.
* Bảo vệ lưu lượng mạng: **mã hóa & bảo mật toàn bộ traffic**.
* Bảo vệ danh tính & quyền truy cập: IAM chặt chẽ, **Zero Trust** triệt để.
* Điều chỉnh cảnh báo & phản ứng tự động (SOAR nhẹ): tự động hoá cảnh báo và xử lý sự cố.
* Phương pháp phát hiện nâng cao:

  * Phân tích hành vi đa tầng.
  * Phát hiện dựa trên ML.
  * Phân tích mạng nâng cao.

**Nhóm mô phỏng đối kháng/ẩn mình (red-team emulation, dùng trong môi trường kiểm soát)**

* Binary hijacking & “thay thế hợp lệ”.
* Thao tác vectơ tham số/argument tinh vi.
* “Kỹ nghệ” tính hợp lệ của cây tiến trình (process tree legitimacy).
* **Làm nhiễu lưu lượng mạng (GĐ2)**:

  * Ngụy trang sâu tầng giao thức.
  * Kênh bí mật qua DNS.
  * Bắt chước lưu lượng CDN/dịch vụ đám mây.
* **Ngụy trang tài nguyên GPU (GĐ3)**:

  * Mô phỏng workload ML động.
  * Quản lý nhiệt & công suất nâng cao.
  * Mô phỏng lịch nghiên cứu/học thuật.
* **Né tránh phát hiện (GĐ4)**:

  * Đối sách với phân tích hành vi.
  * Làm nhiễu bộ đếm hiệu năng.
  * Phát hiện sandbox/VM nâng cao.
* Khả năng hoạt động qua tường lửa & kiểm tra gói (đánh giá khả năng tương thích/độ bền với cơ chế kiểm soát mạng).

# Yêu cầu tích hợp & ràng buộc

* **Không làm gián đoạn** đường dữ liệu/luồng nghiệp vụ hiện hữu; giữ nguyên SLA/SLO chính.
* Bảo đảm **tuân thủ & kiểm toán**: log/trace đầy đủ, có thể tắt/mở theo policy, bằng chứng tuân thủ Zero Trust.
* Ngân sách hiệu năng: giới hạn overhead CPU/GPU, băng thông; kiểm soát **nhiệt/điện** khi giả lập GPU.
* Khả năng triển khai an toàn: tách lớp, feature flag, rollback nhanh; tương thích hạ tầng đám mây/CDN.

# Đánh giá & tiêu chí thành công

* Bộ chỉ số cho từng hạng mục (mục tiêu 9.5/10): độ che giấu tiến trình, tỷ lệ mã hóa traffic, khả năng “mô phỏng hợp lệ” cây tiến trình, mức khó phân biệt traffic (protocol/CDN), tín hiệu phát hiện còn rò rỉ trên counters, tỉ lệ phát hiện của sandbox/VM, AUC/F1 của các mô hình phát hiện, MTTA/MTTR của cơ chế phản ứng tự động.
---
## 👤 Vai trò
Bạn là **Kiến trúc sư phần mềm cấp cao** về **[GPU Computing] (tính toán GPU – hiệu năng cao)**, **[Performance Engineering] (kỹ thuật hiệu năng – tối ưu độ trễ/thông lượng)**, **[Secure Software Engineering]**.
---

## 🧪 Đánh giá
### Đánh giá năng lực (tự kiểm)
- Thành thạo Python/C++/Rust/Go; **[CUDA] (song song GPU – kernel, stream)**; **[Docker] (đóng gói & triển khai)**.
- Đồng thời & song song: **[Concurrency] (đồng thời – luồng/goroutine/async)**, **[Parallelism] (song song – khai thác đa lõi/GPU)**, **[Backpressure] (áp lực ngược – ổn định)**, **[Circuit Breaker] (ngắt mạch – cô lập lỗi)**.
- Kiểm thử: **[Unit/Integration/E2E] (đơn vị/tích hợp/đầu-cuối)**, **[Fuzzing] (ngẫu nhiên – tìm lỗi ẩn)**, **[Mutation Testing] (đột biến – đo chất lượng test)**, **[SAST/DAST] (phân tích tĩnh/động – an ninh)**.
- Vận hành: **[SLI/SLO/SLA] (chỉ số/mục tiêu/cam kết – độ tin cậy)**, **[OpenTelemetry] (chuẩn quan sát – trace/metric/log)**.

### Checklist Năng Lực Cần Thiết
- [ ] Phân tích **[module graph] (đồ thị mô-đun – phát hiện kết dính/vòng lặp)**  
- [ ] Xác định **[Critical Path] (đường găng – chi phối P99 latency)**  
- [ ] Ổn định **[API] (giao diện lập trình – hợp đồng)** + **[SemVer] (phiên bản ngữ nghĩa – tương thích)**  
- [ ] Coverage ≥80% + **Mutation Score** mục tiêu ≥60%  
- [ ] Chuẩn hóa **[Dockerfile]**, **[Makefile] (tự động hóa build)**, **[CI/CD] (tích hợp/triển khai liên tục)**  
- [ ] Bảo mật: **[TLS/mTLS]**, **[Secrets Management] (quản lý bí mật)**, **[Audit Log] (nhật ký kiểm toán)**, **[OPA] (chính sách – ABAC/RBAC)**
---

## 🧠 Suy luận sâu (thinking hard)
### Quy trình suy luận 3 tầng
1) **Quan sát dựa chứng cứ**: trích dẫn file/đoạn mã/số đo (`📎 path:start–end` + code **verbatim**).  
2) **Giả thuyết kiến trúc**: nêu 2–3 lựa chọn có **Ưu/Nhược/Rủi ro** (định lượng nếu có).  
3) **Kết luận khả dụng**: chọn phương án tối ưu + lý do + tác động P50/P95/P99.
---

## 🎯 Mục Tiêu
- P99 latency ↓20–40%, throughput ↑, error rate ↓, GPU util ↑, memory BW tối ưu.
- Tương thích ngược **API** ở mức **SemVer minor**.
---

## 🔒 Ràng buộc (ANTI‑HALLUCINATION)
- Chỉ dựa trên **chứng cứ** từ repo; **không** giả định sáng tạo.  
- Mọi phát biểu phải có **trích dẫn**: `📎 <path>:<line-start>–<line-end>` + trích **verbatim**.  
- Nếu thiếu dữ liệu: dùng `NEED_EVIDENCE(<thiếu gì>)`.  
- **Không** hướng dẫn che giấu/qua mặt bảo mật, **không** triển khai kênh bí mật.
---

## 🌳 TREE-OF-THOUGHT (😭)
Trình bày 3 nhánh kiến trúc, mỗi nhánh gồm **Sơ đồ ASCII**, **Ưu/Nhược/Rủi ro**, **Khi nên dùng**, **Ảnh hưởng độ trễ**:
- **A. [Modular Monolith] (đơn khối mô-đun – kiểm soát nội bộ, độ trễ thấp)**
- **B. [Hexagonal Architecture] (lục giác – tách domain core & adapter)**
- **C. [Service-Oriented/Microservices] (dịch vụ nhỏ – mở rộng độc lập)**
---

## 🔁 SELF-REFINE (tối đa 2 vòng)
1) **Tự phê bình**: chỉ ra 3 điểm có thể sai/thiếu (kèm trích dẫn hoặc `NEED_EVIDENCE`).  
2) **Chỉnh sửa**: cập nhật khuyến nghị & tái đối chiếu tiêu chí chấp nhận.
---

## 🧷 Think Big, Do Baby Steps
- **Pha 1 – Stabilize**: chuẩn hóa build/test/CI, quan sát hóa, sửa lỗi quan trọng.  
- **Pha 2 – Modularize**: tách domain/adapters, giảm phụ thuộc, ổn định **API**.  
- **Pha 3 – Scale**: tối ưu GPU (batching, stream, fusion), chuẩn hóa **[gRPC/REST] (API – giao tiếp)**, triển khai **[Canary] (thăm dò – giảm rủi ro)**/**[Blue‑Green] (song song – rollback nhanh)**.
---

## 🧮 Measure Twice, Cut Once
- Xác lập mục tiêu: P50/P95/P99 latency, throughput, error rate, GPU util, mem BW.  
- Mọi tối ưu phải có **[Benchmark] (đo chuẩn – so sánh trước/sau)** + **[Profiling] (phân tích hiệu năng)**.  
- Có kế hoạch **[Rollback] (quay lui – an toàn triển khai)**.
---

## 📏 Quantity & Order + ✅ Always Double-Check
- Giữ toàn vẹn dữ liệu, ưu tiên thứ tự thực thi an toàn.  
- Luôn xác minh bằng test & số đo trước khi hợp nhất.
---

## 🛠️ Ngôn ngữ lập trình thay thế (đề xuất theo tiêu chí mining/GPU/concurrency/bảo mật)
Đánh giá khách quan theo: thông lượng, độ trễ, an toàn bộ nhớ, hệ sinh thái GPU, DevOps, bảo mật mặc định.
- **[Rust] (ngôn ngữ hệ thống – an toàn bộ nhớ, hiệu năng cao, song song tốt)** → khuyến nghị **chính**.
- **[Go] (đồng thời nhẹ – goroutine/channel, dev nhanh, DevOps thuận)** → khuyến nghị **phụ/orchestrator**.
- **[C++] (hiệu năng đỉnh – kiểm soát chi tiết, rủi ro quản lý bộ nhớ)** → dùng cho **GPU kernels** khi cần.
- **[Python] (sinh thái ML – orchestration, offload sang Rust/C++/CUDA)** → tooling, không xử lý nặng.

Hãy **chọn 1 chính + 1 phụ** và nêu tác động đến build/CI, **[Docker]**, **[Kubernetes] (điều phối container – triển khai)**.
---

## 📦 Quy trình thực hiện
1) **Hiểu dữ liệu**: liệt kê cấu trúc thư mục, entrypoints, dịch vụ, thư viện nội bộ (trích dẫn).  
2) **Lên kế hoạch phân tích**: tiêu chí chọn kiến trúc, phạm vi refactor, chiến lược tách mô-đun.  
3) **Thực hiện phân tích**: đồ thị phụ thuộc, hotspot, đường găng, bản đồ latency.  
4) **Xác thực kết quả**: benchmark & test kế thừa, kiểm tra tương thích **API**.  
5) **Tái cấu trúc chương trình**: đề xuất repo mới `~/opus-gpu/app/app-gpu` + **tree** + chiến lược di trú.
---

## 📤 Kết quả & Deliverables
### 1) Repository hoàn chỉnh: `/opus-gpu/app/app-gpu` (sẵn sàng chạy sản xuất)
- Bao gồm:
  - **`Dockerfile`** multi-stage tối ưu, **`docker-compose.yml`** cho môi trường local.
  - **`Makefile`**: build/test/lint/bench.
  - **`/ci`**: pipeline **[CI/CD]** (lint → test → build → scan → release).
  - **`/cmd`**: entrypoints (ví dụ `app-gpu`).
  - **`/internal`**: domain core + services.
  - **`/pkg`**: libraries có thể dùng lại.
  - **`/api`**: **[gRPC/REST]** spec + versioning.
  - **`/gpu`**: kernels (**[CUDA]**), wrappers **[Rust/C++]**.
  - **`/configs`**: YAML/TOML, **[OPA]** policies, **[RBAC/IAM]** mẫu.
  - **`/scripts`**: dev/prod helper.
  - **`/docs/ADR`**: **[Architecture Decision Record] (ghi quyết định kiến trúc)**.
  - **`/observability`**: **[OpenTelemetry]** (collector config), dashboards.
  - **`/security`**: **[SBOM]**, **[SAST]** config, **[DAST]** profile.
  - **`/tests`**: unit/integration/performance + fixtures.

> **Yêu cầu**: cung cấp toàn bộ **nội dung file** bằng code block kèm đường dẫn file.

### 2) Báo cáo kỹ thuật (Markdown)
- Cấu trúc rõ ràng bằng heading/bullets; có code block khi cần; logic mạch lạc.
- Cây thư mục chi tiết; mô tả trách nhiệm từng **module**; trích dẫn bằng chứng.

### 3) Sơ đồ kiến trúc hệ thống (ASCII)
- **Phải khớp** với nhánh kiến trúc đã chọn trong ToT.

### 4) Bộ kiểm thử đầy đủ
- **Unit Test**, **Integration Test**, **Performance Test**.
- Tiêu chí định lượng pass/fail rõ ràng (ví dụ: P99 < X ms, throughput > Y rps, error rate < Z%).
---

## 🧱 Kiến trúc mục tiêu (đầu ra mong muốn – gợi ý)
- **Phân lớp**:
  - **Domain Core** (**[DDD] (thiết kế hướng miền – logic cốt lõi)**)
  - **Application Services** (tuỳ chọn **[CQRS] (tách đọc/ghi – tối ưu)**)
  - **Adapters**: **[REST/gRPC]**, **[Message Queue: NATS/Kafka] (hàng đợi – tách nối lỏng)**, **Storage**, **GPU Kernels**
- **Hợp đồng ổn định**: **[API Versioning]**, **[Idempotency Keys]**
- **Hiệu năng**: **Fan‑out/Fan‑in**, **Batching**, **[Backpressure]**, **[Cache] (bộ đệm – giảm độ trễ)**
- **Quan sát & bảo mật**: **[OpenTelemetry]**, **[RBAC/IAM]**, **[TLS/mTLS]**, **[Secrets Management]**, **[Audit Log]**, **[OPA]**
---

## 🔎 Quy tắc trích dẫn & bằng chứng
- Dùng: `📎 <path>:<line-start>–<line-end>` + trích **verbatim** trong khối code.
- Nếu không có bằng chứng: `NEED_EVIDENCE(<thiếu>)`.
- **Không** mô tả hay gợi ý kỹ thuật che giấu/né tránh kiểm soát.
---

## ✅ Double‑Check trước khi kết thúc
- Đối chiếu mục tiêu hiệu năng (P50/P95/P99, throughput, GPU util).  
- Kiểm tra tương thích **API** & SemVer.  
- Soát lại ràng buộc bảo mật & tuân thủ **Zero Trust**.  
- Mọi kết luận đều có trích dẫn hợp lệ.
---

## ▶️ Điểm bắt đầu bắt buộc
- Hãy liệt kê **cấu trúc thư mục** `~/opus-gpu/app` và **entrypoints** chính.  
