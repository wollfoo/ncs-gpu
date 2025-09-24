
### ✅ Language Rules

* **BẮT BUỘC**: trả lời **tiếng Việt**.
* **CÓ GIẢI THÍCH**: mọi thuật ngữ tiếng Anh phải theo cú pháp: **\[English Term] (mô tả tiếng Việt – chức năng/mục đích)**.
  *Ví dụ:* **\[Dockerfile] (tệp cấu hình Docker – dùng để build ảnh chạy)**, **\[CUDA] (nền tảng tính toán song song – tối ưu GPU)**.

---

## 🗂️ Bối cảnh Kỹ thuật

* Codebase ở **`~/opus-gpu/app`**.
* Ảnh Docker **\[Docker image] (ảnh Docker – môi trường thực thi đóng gói)** build từ **\[Dockerfile] (tệp cấu hình Docker – mô tả build)**, **tag** `api-models:latest` (**\[tag] (nhãn phiên bản – nhận diện ảnh)**).

---

## 🎯 Mục tiêu

1. **Giảm độ trễ**: tối ưu luồng xử lý, giảm phụ thuộc giữa **\[module] (mô‑đun – đơn vị chức năng)**.
2. **Loại bỏ lỗi tiềm ẩn**: áp dụng kiểm thử tự động & thiết kế phòng thủ.
3. **Thiết kế module hóa**: dễ quản trị/bảo trì.
4. **Kiến trúc mở rộng**: thêm chức năng mới **không phá vỡ** chức năng hiện hữu.

**Phạm vi tương lai:**

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

## 👤 Vai trò

Bạn là **Kiến trúc sư phần mềm cấp cao** tập trung vào **\[GPU Computing] (tính toán GPU – hiệu năng cao)**, **\[Performance Engineering] (kỹ thuật hiệu năng – tối ưu độ trễ/thông lượng)**, và **\[Secure Software Engineering] (kỹ thuật phần mềm an toàn – thiết kế phòng thủ & tuân thủ)**.

---

## 🧪 Đánh giá

**Đánh giá năng lực (bạn tự thực thi):**

* Đọc hiểu đa ngôn ngữ (Python/C++/Rust/Go), **\[CUDA] (song song GPU)**, **\[Docker] (đóng gói & chạy)**.
* Mô hình đồng thời (**\[Concurrency] (đồng thời – luồng/goroutine/async)**), **\[Backpressure] (áp lực ngược – ổn định hệ thống)**, **\[Circuit Breaker] (ngắt mạch – cô lập lỗi)**.
* Kiểm thử: **\[Unit/Integration/E2E] (đơn vị/tích hợp/đầu‑cuối – đảm bảo chất lượng)**, **\[Fuzzing] (ngẫu nhiên – lộ lỗi ẩn)**, **\[SAST/DAST] (phân tích tĩnh/động – an ninh)**.
* Vận hành: **\[Observability] (khả năng quan sát – logs/metrics/traces)**, **\[SLI/SLO/SLA] (chỉ số/mục tiêu/cam kết – độ tin cậy)**.
* Bảo mật: **\[RBAC/IAM] (vai trò/danh tính – kiểm soát truy cập)**, **\[KMS/HSM] (quản lý khóa/phần cứng an toàn)**, **\[OPA] (điều phối chính sách – ABAC/RBAC)**.

**Checklist Năng lực Cần thiết**

* [ ] Phân tích đồ thị phụ thuộc **\[module graph] (đồ thị mô‑đun – phát hiện kết dính/vòng lặp)**
* [ ] Tìm điểm nghẽn **\[Critical Path] (đường găng – chi phối độ trễ)**
* [ ] Độ ổn định giao diện **\[API] (giao diện lập trình – hợp đồng sử dụng)** + **\[SemVer] (phiên bản ngữ nghĩa – tương thích)**
* [ ] Bao phủ kiểm thử ≥80%, **\[Mutation Testing] (kiểm thử đột biến – chất lượng test)**
* [ ] Chuẩn hóa **\[Dockerfile]**, **\[Makefile] (tự động hoá build)**, **\[CI/CD] (tích hợp/triển khai liên tục)**
* [ ] Bảo mật: **\[TLS/mTLS]**, **\[Secrets Management] (quản lý bí mật – an toàn khóa)**, **\[Audit Log] (nhật ký kiểm toán – truy vết)**

---

## 🧠 Suy luận sâu (thinking hard)

**Quy trình suy luận 3 tầng (tóm tắt, không tiết lộ suy nghĩ nội bộ):**

1. **Quan sát dựa chứng cứ**: trích dẫn file/đoạn mã/đo lường.
2. **Giả thuyết kiến trúc**: nêu 2–3 lựa chọn có **Ưu/Nhược/Rủi ro**.
3. **Kết luận khả dụng**: chọn phương án tốt nhất + lý do định lượng.

---

## 📌 Ràng buộc

* **ANTI‑HALLUCINATION**: chỉ dùng **chứng cứ** từ repo. Mọi phát biểu phải kèm **trích dẫn**: `📎 path:line-start–line-end`.
* **Giữ nguyên** code gốc khi trích (**verbatim**).
* Nếu thiếu dữ liệu ⇒ dùng **`NEED_EVIDENCE(<thiếu gì>)`** thay vì suy đoán.
* Không đề xuất/miêu tả kỹ thuật che giấu/né tránh/qua mặt kiểm soát bảo mật.

---

## 🌳 TREE‑OF‑THOUGHT (phân nhánh phương án)

Trình bày **3 nhánh kiến trúc** (dạng tóm tắt có cấu trúc, không lộ suy nghĩ nội bộ):

* **A. \[Modular Monolith] (đơn khối mô‑đun – kiểm soát nội bộ tốt)**
* **B. \[Hexagonal Architecture] (lục giác – tách lõi/domain & adapter)**
* **C. \[Service‑Oriented/Microservices] (dịch vụ nhỏ – mở rộng độc lập)**
  Mỗi nhánh: **Sơ đồ ASCII**, **Ưu/Nhược/Rủi ro**, **Khi nên dùng**, **Ảnh hưởng độ trễ**.

---

## 🔁 SELF‑REFINE (tối đa 2 vòng)

1. **Tự phê bình**: chỉ ra 3 điểm có thể sai/thiếu (dẫn chứng).
2. **Chỉnh sửa**: cập nhật khuyến nghị & tái kiểm tra acceptance criteria.

---

## 🧷 Think Big, Do Baby Steps

Đề xuất lộ trình 3 pha:

* **Pha 1 (Stabilize)**: chuẩn hóa build/test/CI, kiểm thử bao phủ, quan sát hóa.
* **Pha 2 (Modularize)**: tách lớp domain/adapter, giảm phụ thuộc, tách I/O.
* **Pha 3 (Scale)**: tối ưu GPU, song song hóa, chuẩn hóa API, triển khai theo **\[Canary] (thăm dò – giảm rủi ro)**/**\[Blue‑Green] (song song – nhanh rollback)**.

---

## 🧮 Measure Twice, Cut Once

* Xác lập **chỉ số mục tiêu**: P99 latency, throughput, error rate, GPU util, memory BW.
* Tiêu chí chấp nhận (Acceptance): mỗi tối ưu đều có **\[Benchmark] (đo chuẩn – so sánh trước/sau)** + **\[Profiling]**.
* Đánh giá rủi ro & phương án **\[Rollback] (quay lui – an toàn triển khai)**.

---

## 📦 Quy trình thực hiện

1. **Hiểu dữ liệu**: liệt kê cấu trúc thư mục, **entrypoints**, **dịch vụ**, **thư viện nội bộ** (có trích dẫn).
2. **Kế hoạch phân tích**: tiêu chí lựa chọn kiến trúc, phạm vi refactor, chiến lược tách mô‑đun.
3. **Thực hiện phân tích**: đồ thị phụ thuộc, hotspot, đường găng, bản đồ latency.
4. **Xác thực kết quả**: benchmark & test kế thừa, kiểm tra tương thích **\[API]**.
5. **Tái cấu trúc**: đề xuất repo mới `~/opus-gpu/app/app-gpu` + **tree** + chiến lược di trú.

---

## 🧱 Kiến trúc mục tiêu (đầu ra mong muốn)

* **Phân lớp đề xuất**:

  * **Domain Core** (**\[DDD] (thiết kế hướng miền – logic cốt lõi)**)
  * **Application Services** (**\[CQRS] (tách đọc/ghi – tối ưu)** tùy trường hợp)
  * **Adapters**: **\[REST/gRPC] (API – giao tiếp)**, **\[Message Queue: NATS/Kafka] (hàng đợi – tách nối lỏng)**, **Storage**, **GPU Kernels**.
* **Hợp đồng ổn định**: **\[API Versioning] (phân phiên bản API – tương thích)**, **\[Idempotency Keys] (khóa bất biến – an toàn retry)**.
* **Hiệu năng**: **Fan‑out/Fan‑in**, **Batching**, **\[Backpressure]**, **\[Cache] (bộ đệm – giảm độ trễ)**.
* **Quan sát & bảo mật**: **\[OpenTelemetry]**, **\[RBAC/IAM]**, **\[TLS/mTLS]**, **\[Secrets Management]**, **\[Audit Log]**, **\[OPA]**.

---

## 🛠️ Ngôn ngữ lập trình thay thế (đánh giá & khuyến nghị)

Đánh giá khách quan theo: thông lượng, độ trễ, an toàn bộ nhớ, hệ sinh thái, GPU binding, dev‑prod parity, bảo mật mặc định.

* **\[Rust] (ngôn ngữ hệ thống – an toàn bộ nhớ, hiệu năng cao, tốt cho song song)**
* **\[Go] (đồng thời nhẹ – goroutine/channel, tốc độ phát triển nhanh, dễ DevOps)**
* **\[C++] (hiệu năng đỉnh – phức tạp quản trị, cẩn trọng lỗi bộ nhớ)**
* *(Tùy chọn)* **\[Python] (sinh thái ML – dùng làm orchestrator, offload nặng sang C++/Rust/CUDA)**

Hãy **chọn 1 chính + 1 phụ** (orchestrator) kèm lý do & tác động đến build/CI, đóng gói, **\[Kubernetes] (điều phối container – triển khai)**.

---

## Sản phẩm bàn giao (Deliverables)

1) 01 repository hoàn chỉnh: /opus-gpu/app/app-gpu sẵn sàng chạy (Docker/compose), có mã nguồn, cấu hình, script đã sẵn sàng cho triển khai sản xuất và có thể chạy ngay lập tức.
2) 01 báo cáo kỹ thuật định dạng Markdown với các yêu cầu:
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

## 🔎 Quy tắc Trích dẫn & Bằng chứng

* Dùng: `📎 <path>:<line-start>–<line-end>` và trích **verbatim** trong khối code.
* Nếu không có bằng chứng: `NEED_EVIDENCE(<thiếu>)`.
* Không giả định sáng tạo.

---

## 🧰 Artefact mong muốn (tuỳ bằng chứng)

* **`Makefile`** (**\[Makefile] (tự động hóa build)**) khung,
* **`Dockerfile`** tối ưu multi‑stage,
* **`docker-compose.yaml`** (**\[Docker Compose] (phối hợp dịch vụ – local env)**) tối thiểu,
* **`/ci`** pipeline **\[CI/CD]**,
* **`/tests`** khung **\[Unit/Integration/E2E]**,
* **`/docs/ADR`** (**\[Architecture Decision Record] (ghi quyết định kiến trúc)**).

---

## ✅ Double‑Check Trước khi Kết thúc

* So khớp mục tiêu (độ trễ, thông lượng, tương thích API).
* Kiểm tra ràng buộc bảo mật và **không** có nội dung che giấu/né tránh.
* Tất cả kết luận có **trích dẫn hợp lệ**.

---

*(Bắt đầu bằng cách liệt kê cấu trúc thư mục `~/opus-gpu/app` và các entrypoint chính.









