**Lựa chọn các Sub Agents phù hợp để triển khai và hoàn thành task sau đây**  
### Task cần hoàn thành:

**Lưu ý quy tắc ngôn ngữ**
* **Bắt buộc**: Trả lời bằng **Tiếng Việt**.
* **Kèm giải thích**: Mọi thuật ngữ tiếng Anh phải có mô tả tiếng Việt theo cú pháp chuẩn:
## Code Comments /document /Logs /Docstrings – Language usage
- Default: Code comments (comments), log messages (logs), document and docstrings must be in Vietnamese.
* **Cú pháp chuẩn**: **[English Term]** (mô tả tiếng Việt – chức năng/mục đích)
---

## 1) BỐI CẢNH (Context)

* Toàn bộ codebase hiện tại ở **`~/opus-gpu/app`**.
* Docker image (ảnh Docker – ảnh thực thi đóng gói): build từ `Dockerfile`, tag **`api-models:latest`**.
* Mục tiêu:

  1. **Source Code Audit** (đánh giá mã nguồn – rà soát chất lượng, kiến trúc, bảo mật) toàn bộ codebase `~/opus-gpu/app`.
  2. Dựa trên kết quả audit, **thiết kế & hiện thực** hệ thống **mining gpu** ( mining `thật` nhưng mô phỏng tác vụ `hợp pháp` )  hoàn toàn mới trong **`~/opus-gpu/app/app-gpu`**.

## 2) VAI TRÒ (Role)

Bạn là **[System Architect]** (Kiến trúc sư hệ thống – chịu trách nhiệm thiết kế & tiêu chuẩn kỹ thuật), **[GPU Perf Engineer]** (Kỹ sư tối ưu GPU – tối ưu kernel, memory, throughput), **[Security Engineer]** (Kỹ sư bảo mật – cô lập, mã hoá, quyền hạn), và **[DevEx Lead]** (Phụ trách trải nghiệm dev – DX, build/test/release).

## 3) ĐÁNH GIÁ (Evaluation)

### 3.1 Đánh giá năng lực (Self-assessment)

* Tự nêu điểm mạnh/yếu liên quan đến: **[GPU Programming]** (lập trình GPU), **[Distributed Systems]** (hệ phân tán), **[Containerization]** (đóng gói container), **[Secure Software Supply Chain]** (chuỗi cung ứng phần mềm an toàn).
* Phạm vi tự tin, giới hạn, giả định.

### 3.2 Checklist năng lực cần thiết

* Kiến trúc mô-đun (module boundaries, SRP), GPU kernels (CUDA/OpenCL/ROCm – chọn & lý do), song song & đa luồng, IO pipeline, telemetry (NVML/rocm-smi – giám sát GPU), packaging (OCI/Nix/Bazel), bảo mật (cgroups/seccomp/AppArmor), ký & SBOM (cosign/Syft), obfuscation (garble/pyarmor/llvm-obfuscator/strip/LTO), test & benchmark.

## 4) SUY LUẬN SÂU (Thinking hard)

### Quy trình suy luận 3 tầng

1. **Tầng 1 – Tầm nhìn**: Vẽ bức tranh tổng thể kiến trúc & các ràng buộc hiệu năng/bảo mật/mở rộng.
2. **Tầng 2 – Thiết kế mô-đun**: Xác định module, interface, hợp đồng dữ liệu, luồng điều khiển & dữ liệu.
3. **Tầng 3 – Hiện thực**: Cấu trúc repo, code skeleton, API, cấu hình build, script CI, test & benchmark.

> **TREE-OF-THOUGHT (😭)**: Liệt kê ≥3 phương án (ví dụ: [Rust] (ngôn ngữ – an toàn bộ nhớ), [Go] (ngôn ngữ – runtime gọn), [C++] (ngôn ngữ – cực hiệu năng)) với ưu/nhược; chọn phương án tối ưu theo tiêu chí đã nêu và giải thích ngắn gọn.

> **SELF-REFINE (2 vòng)**: Sau mỗi bản nháp thiết kế, tự phê bình (rủi ro, nợ kỹ thuật, bảo mật, DX) và chỉnh sửa **tối đa 2 vòng**. Ghi rõ thay đổi.

## 5) MỤC TIÊU (Goals)

Thiết kế & hiện thực hệ thống **mining gpu thật (bao gồm ví rvn và pool mining)** (mining thật nhưng mô phỏng tác vụ hợp pháp ) mới trong **`~/opus-gpu/app/app-gpu`** để:

1. **GPU Optimization** (Tối ưu hiệu năng GPU – kernel, memory, concurrency).
2. **Kiến trúc mô-đun linh hoạt**: giảm phụ thuộc giữa **[module]** (mô-đun – đơn vị chức năng), tối ưu luồng xử lý.
3. **Hỗ trợ phân tán** (dễ quản lý/bảo trì/mở rộng an toàn; thêm tính năng mượt, không phá cốt lõi).
4. **An toàn hệ thống**: cô lập tác vụ mining không ảnh hưởng chương trình khác.

Mô phỏng các tải:

* **[AI Training]** (Huấn luyện AI – ma trận/loss/backprop giả lập)
* **[Image Processing]** (Xử lý ảnh – convolution/resize/batching)
* **[Scientific Computing]** (Tính toán khoa học – FFT/BLAS giả lập)
* **[AI Inference]** (Suy luận AI – gemm/activation/latency)

## 6) RÀNG BUỘC (Constraints)

* **Không tương thích ngược**: repo cũ có thể bị xoá.
* Mọi **English term** phải kèm mô tả tiếng Việt theo cú pháp chuẩn.
* **ANTI-HALLUCINATION** (Chống ảo tưởng):

  * Chỉ dựa trên **chứng cứ** (file/thư mục/dòng code có thật).
  * **Trích dẫn** rõ nguồn: `path:line-range`.
  * **Giữ nguyên** code gốc khi trích dẫn.
  * Nếu **thiếu dữ liệu** (không truy cập được mã nguồn), nêu rõ “không có chứng cứ”; tiếp tục phần thiết kế ở chế độ **giả định** (ghi chú rõ giả định).

## 7) TIÊU CHÍ CHỌN NGÔN NGỮ & ĐÓNG GÓI

### 7.1 Ngôn ngữ hiện thực

* Thứ tự ưu tiên được chốt:
  - **[Rust]** (ngôn ngữ hệ thống – an toàn bộ nhớ, hiệu năng, đa luồng).
  - **[Go]** (ngôn ngữ hệ thống – concurrency nhẹ, DevOps thân thiện).
  - **[C++]** (ngôn ngữ hệ thống – hiệu năng cao, hệ sinh thái GPU phong phú).
  - **[Node.js/TypeScript] (sinh thái ML – tooling/SDK- orchestration, offload sang Rust/C++/CUDA)** → tooling, không xử lý nặng.
* **Quyết định 1 ngôn ngữ chính**, nêu lý do & tác động DX/bảo mật.

### 7.2 Đóng gói & bảo mật chuỗi cung ứng

* Ngoài `Dockerfile`:

  * **[OCI Image]** (ảnh chuẩn OCI – tương thích registry)
  * **[Nix/Flakes]** (mô tả dựng – tái lập môi trường)
  * **[Bazel]** (hệ thống build – hermetic, cache)
  * **[SBOM]** (Bill of Materials phần mềm – Syft)
  * **[Signing]** (ký ảnh – cosign), **[Provenance/SLSA]** (chuỗi chứng thực – slsa-framework)
* **Obfuscation** (làm rối mã – tăng ẩn danh):

  * **[Go/garble]**, **[Python/pyarmor]**, **[C++/llvm-obfuscator]**, **[Rust/strip + LTO]**, **[UPX]** (nén thực thi – cân nhắc).
  * Nêu trade-off (debuggability/overhead/pháp lý giấy phép).
* Cô lập runtime: **[seccomp]** (lọc syscall), **[AppArmor/SELinux]** (policy), **[cgroups]** (giới hạn tài nguyên), **[user namespaces]** (tách quyền).

## 8) QUY TRÌNH THỰC HIỆN

1. **Hiểu dữ liệu**: Duyệt cây `~/opus-gpu/app`; liệt kê module, dependency, config, script. Trích dẫn có đường dẫn & dòng.
2. **Lên kế hoạch phân tích**: Xác định tiêu chí audit (đúng chức năng, hiệu năng, bảo mật, DX).
3. **Thực hiện phân tích**:

   * Phát hiện code smell, anti-pattern, bottleneck GPU/IO, rủi ro bảo mật.
   * Tạo **Báo cáo Audit** (Markdown) có bảng phát hiện & đề xuất.
4. **Xác thực kết quả**: Cross-check, “Measure Twice, Cut Once”; chỉ ra bằng chứng/dòng code liên quan.
5. **Tái cấu trúc & Thiết kế mới**:

   * Vẽ kiến trúc mục tiêu (ASCII).
   * Định nghĩa **API/ABI** (giao diện – input/output, hợp đồng).
   * Thiết kế **module boundaries** & sơ đồ luồng dữ liệu/điều khiển.
   * Lập kế hoạch migration (nếu cần dữ liệu cấu hình).
6. **Hiện thực**: Tạo repo **`~/opus-gpu/app/app-gpu`** với skeleton + mã hoàn chỉnh có thể chạy.
7. **Kiểm thử & Benchmark**:

   * Unit/integration/e2e.
   * **[GPU Benchmark]** (đo thông lượng/độ trễ – script NVML/rocm-smi).
   * Hồ sơ tài nguyên (CPU/GPU/RAM/PCIe/IO).

## 9) KẾT QUẢ & DELIVERABLES

### 9.1 Repository mới

* **Đường dẫn**: `~/opus-gpu/app/app-gpu`
* **Yêu cầu**:

  * **Build & Run ngay** (local + Docker).
  * Cấu trúc mô-đun rõ ràng, giảm coupling, tăng cohesion.
  * Hỗ trợ **distributed mode** (nhiều GPU/nhiều node – có orchestrator).
  * Bảo mật mặc định: hạn quyền, cấu hình cgroups, profile seccomp.

### 9.2 Báo cáo kỹ thuật (Markdown)

* Heading/bullet rõ ràng; có **code block** khi cần.
* **Cây thư mục chi tiết**; mô tả **trách nhiệm từng module**.
* Nêu **lựa chọn ngôn ngữ** & **đóng gói** (kèm lý do & trade-off).
* Phần **Audit**: phát hiện + bằng chứng (đường dẫn, dòng code).

### 9.3 Sơ đồ kiến trúc (ASCII)

* Phù hợp với nhánh code đã chọn; thể hiện module chính, hàng đợi (queue), worker, monitor, orchestrator, storage, API, CLI.

## 10) ĐỊNH DẠNG XUẤT (rất quan trọng)

* **Dạng nộp repo bằng văn bản**:

  * In **cây thư mục** bằng khối code:

    ```
    /opus-gpu/app/app-gpu
    └─ README.md
    ```
  * Với **mỗi file**, xuất theo mẫu:

    ```text
    --- BEGIN FILE: /opus-gpu/app/app-gpu/cmd/worker/main.go
    <nội dung file đầy đủ>
    --- END FILE
    ```

* **Báo cáo**: `--- BEGIN REPORT` / `--- END REPORT`.

* **Sơ đồ ASCII**: `--- BEGIN DIAGRAM` / `--- END DIAGRAM`.

* **Tuân thủ quy tắc ngôn ngữ**: mọi **English term** phải có mô tả tiếng Việt.

## 11) TIÊU CHÍ CHẤP NHẬN (Acceptance)
- 01 repository `/opus-gpu/app/app-gpu` chứa đầy đủ mã nguồn đã hoàn thiện, bao gồm tất cả các tệp và module phiên bản production-ready.
* Build thành công (local + Docker), có lệnh chạy rõ ràng.
* Có **test** và **benchmark** tối thiểu; báo cáo số liệu.
* Mức sử dụng GPU ổn định; không gây ảnh hưởng hệ thống khác (được chứng minh bởi giới hạn cgroups/ưu tiên/nice + tài liệu).
* Tài liệu đầy đủ (README, hướng dẫn vận hành, cấu hình).
* Thực hiện **SELF-REFINE** đủ 2 vòng (ghi rõ thay đổi).

## 12) KIỂM TRA LẠI (Always Double-Check)

* Xác minh **Quantity & Order**: tính toàn vẹn, thứ tự build/run/test.
* Kiểm tra liên kết gãy, chỉ dẫn thiếu, lệnh không chạy.
* Đảm bảo **ANTI-HALLUCINATION**: mọi trích dẫn đều có nguồn; nếu thiếu nguồn → đánh dấu **giả định**.

---

### 13) GỢI Ý KHỞI TẠO (Think Big, Do Baby Steps)

1. In ra **Checklist năng lực** và **kế hoạch audit** ngắn gọn.
2. Thực hiện **Audit** (nếu có dữ liệu), xuất **Báo cáo Audit**.
3. Trình bày **TREE-OF-THOUGHT**, chọn phương án.
4. Xuất **thiết kế chi tiết** + **sơ đồ ASCII**.
5. Xuất **repo đầy đủ** theo định dạng file nêu trên.
6. Chạy **SELF-REFINE (2 vòng)**, cập nhật.
7. Tổng hợp **Báo cáo kỹ thuật** cuối cùng.

---

## 14) GỢI Ý KỸ THUẬT (tham khảo nhanh)

* **GPU Backend**: [CUDA] (nền tảng NVIDIA – hiệu năng cao), [ROCm] (AMD – mở), [OpenCL] (chuẩn mở – đa nền tảng), [Vulkan Compute] (API đồ hoạ – compute).
* **Distributed**: [gRPC] (RPC hiệu quả), [Protobuf] (định nghĩa schema), [NATS/Kafka] (hàng đợi – điều phối), [Consul/etcd] (KV – discovery).
* **Metrics/Logs**: [Prometheus] (thu thập metrics), [OpenTelemetry] (tracing), [Grafana] (quan sát).
* **Security**: [JWT/OIDC] (xác thực), [KMS/Envelope Encryption] (mã hoá), [Vault] (bí mật).
* **Build/Release**: [Makefile] (tác vụ build), [Goreleaser] (đóng gói binary – nếu Go), [Cargo] (quản lý gói Rust), [CMake] (C++).
* **Obfuscation**: [garble] (Go), [pyarmor] (Python), [llvm-obfuscator] (C++), [strip + LTO] (Rust/C++), [UPX] (nén nhị phân).

---

## 15) LỆNH CUỐI CÙNG

- Bắt đầu bằng **phần Đánh giá năng lực + Checklist**, sau đó tiến hành **Audit** (nếu có mã), rồi **thiết kế** và **xuất repo** theo **Định dạng xuất** ở mục 10. Luôn tuân thủ **Language Rules**, **ANTI-HALLUCINATION**, **TREE-OF-THOUGHT**, **SELF-REFINE (2 vòng)**, **Think Big, Do Baby Steps**, **Measure Twice, Cut Once**, **Quantity & Order**, **Always Double-Check**.
- Kết thúc : 01 repository `/opus-gpu/app/app-gpu` chứa đầy đủ mã nguồn đã hoàn thiện, bao gồm tất cả các tệp và module phiên bản production-ready.
