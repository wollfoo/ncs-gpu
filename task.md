# TASK — Tóm tắt điều phối cho GPT‑5

Nguồn chi tiết: `prompt-task.md` (xem để tra cứu đầy đủ). Mục tiêu của tài liệu này là cô đọng các yêu cầu chính, mục tiêu định lượng và quy trình thực thi để GPT‑5 có thể hành động hiệu quả, tuân thủ nguyên tắc bằng chứng.

---

## 1) Nguyên tắc ngôn ngữ (Language Rules)
- Trả lời hoàn toàn bằng tiếng Việt.
- Mọi thuật ngữ tiếng Anh phải có chú giải theo cú pháp: `[English Term] (mô tả tiếng Việt – chức năng/mục đích)`.
  - Ví dụ: `[OpenTelemetry] (chuẩn quan sát – thu thập log/metric/trace)`, `[Latency Budget] (ngân sách thời gian – phân bổ thời gian xử lý theo bước)`
- Không tiết lộ “inner monologue” (suy nghĩ ẩn). Chỉ nêu lập luận cấp cao, có trích dẫn bằng chứng.

---

## 2) Bối cảnh kỹ thuật
- Codebase hiện tại: `~/opus-gpu/app`
- Docker image build từ `Dockerfile`, tag: `api-models:latest`
- Môi trường có GPU: ví dụ `[CUDA] (kiến trúc tính toán song song của NVIDIA)` / `[cuDNN] (thư viện tăng tốc deep learning)`
- Đích tái cấu trúc: repo mới `~/opus-gpu/app/app-gpu`
- Artefacts cần thu thập ban đầu:
  1) Cây thư mục (`tree -a -L 3`), 2) file phụ thuộc (ví dụ `requirements.txt`/`pyproject.toml`/`go.mod`/`Cargo.toml`), 3) `Dockerfile`, 4) GPU info (`nvidia-smi`), 5) baseline latency (p50/p95/p99)

---

## 3) Vai trò & trọng tâm
- Vai trò: Principal Software Architect, Code Auditor, SRE (GPU/HPC).
- Năng lực cốt lõi: `[GPU Systems] (hệ thống GPU)`, `[HPC] (hiệu năng cao)`, `[Software Architecture] (kiến trúc phần mềm)`, `[DevSecOps] (CI/CD an toàn)`, Rust/C++/Go.
- Trọng tâm: ưu tiên đúng đắn/bảo mật/hiệu năng; đo trước tối ưu; tiêu chuẩn hoá; thiết lập SLO/SLI, quan sát hoá, runbook.

---

## 4) Mục tiêu định lượng (KPIs)
- Hiệu năng: p95 ↓ ≥ 30% qua `[Latency Budget]`, thông lượng ↑ ≥ 2× với `[Batching]` và `[Pipeline Parallelism] (song song hoá pipeline)`; SLO hot path ≥ 99.9%.
- Kiến trúc: module hoá theo `[Clean Architecture]` + `[Hexagonal Architecture]`; thiết kế `[Event‑Driven]` (hướng sự kiện).
- Chất lượng: `[Test Automation]` coverage ≥ 85%; `[Observability]` đầy đủ (metrics/logs/traces); `[CI/CD]` có `[Blue‑Green Deployment]`.

---

## 5) Nhiệm vụ chính
1) Phân tích hiện trạng: bottlenecks, code smells, security vulns tại `~/opus-gpu/app`.
2) Tái cấu trúc kiến trúc: repo mới `~/opus-gpu/app/app-gpu` theo `[Microservices]`, `[DDD] (Domain‑Driven Design)`, `[CQRS]`.
3) Đề xuất stack: GPU (CUDA/OpenCL/ROCm), đồng thời (async/await, goroutines, tokio), mật mã (AES/RSA/hashing), bộ nhớ (zero‑copy/memory pools).

---

## 6) Ràng buộc & phạm vi
- Kiến trúc phải extensible (dễ mở rộng), đúng đắn/hiệu năng/bảo mật là baseline; mọi thay đổi qua regression test và đánh giá tác động.
- Defensive‑only, tuân thủ pháp luật/policy.
- Hướng tích hợp tương lai (defensive hardening): process protection, encrypted traffic (mTLS/TLS pinning), binary hijacking simulation (có kiểm soát), argv policy/audit, process tree legitimacy, traffic obfuscation (DNS covert‑channel, CDN mimicry), GPU resource camouflage, detection evasion/methodologies, identity/access protection, alerting/orchestration, zero‑trust.

---

## 7) Acceptance chung
- Không phá vỡ backward compatibility; build/deploy reproducible.
- Đủ lớp kiểm thử (unit/integration/E2E), ngân sách hiệu năng rõ ràng; SLO/SLI đạt ≥ baseline.
- Quan sát hoá: structured logging, metrics, tracing; cảnh báo hữu ích (ít noise).
- Feature flags (off‑by‑default), rollback an toàn; tài liệu & runbook cập nhật.

---

## 8) Quy trình thực hiện (5 pha)
1) Discovery: đọc `tree`, `Dockerfile`, manifests (K8s), config, scripts; sinh dependency map & hot path; lập baseline (HTTP/gRPC latency, GPU util, throughput).
2) Kế hoạch phân tích: profiling `[py-spy]`/`[cProfile]`, `[Nsight Systems]`, `[perf]`; observability `[OpenTelemetry]` + `[Prometheus]`/`[Grafana]`; kiểm thử `[pytest]`, property‑based, load test `[k6]`.
3) Thực thi phân tích: phân rã call graph; phát hiện contention (lock/memory/GIL); phân tích batch/queue; H2D/D2H & overlap compute/copy với `[CUDA Streams]`; chọn mô hình đồng thời (thread pool/async/process pool).
4) Xác thực: báo cáo p50/p95/p99, GPU SM%, DRAM BW%, batch/s, cost/req; thử nghiệm lặp lại đủ mẫu.
5) Tái cấu trúc: thiết kế `~/opus-gpu/app/app-gpu`; nguyên tắc “stable interfaces, evolving implementations”; bọc GPU qua `[Facade]` + `[Strategy]`; I/O theo `[Ports and Adapters]`; ngôn ngữ: Rust/Go/C++/Python (vai trò phù hợp); CI/CD (pre‑commit, lint/format, GitHub Actions, SAST/DAST); Observability (OTel, dashboards p95/p99, SM%); Security (mTLS/JWT/OPA, Secrets via Vault/KMS, Zero‑Trust/RBAC); Docker/K8s (multi‑stage, nvidia‑container‑toolkit, resource limits, `[PodDisruptionBudget]`).

---

## 9) Đánh giá & kiểm chứng (Evidence‑only)
- Hiện trạng mã (inventory): liệt kê component/role (entrypoints, API, worker, GPU driver, scheduler, I/O, storage, logging, metrics); dependency graph & 3 hot paths; bảng đo p50/p95/p99, SM util, H2D/D2H, memory footprint (nêu phương pháp & nguồn).
- Đánh giá codebase: cấu trúc/ranh giới, data/control path, GPU kernels, I/O, serialization; hiệu năng & contention (PCIe, H2D/D2H, lock hot‑spots); bảo mật & vận hành (secrets, access control, attack surface, logging/metrics/tracing, config/flags, crash dumps). Output: checklist Y/N + bằng chứng; 3 đề xuất cải tiến ưu tiên.
- Tự đánh giá năng lực: chấm 0–5 cho GPU Programming, Concurrency, Docker, CI/CD, Secure Coding (kèm 1–2 evidence thực tế mỗi mục).
- Checklist nhóm (điền Y/N + Evidence): Kiến trúc & phụ thuộc; Đồng thời & chịu tải; GPU/HPC; Quan sát & vận hành; Bảo mật; Chất lượng & kiểm thử; Tri thức & tài liệu.

---

## 10) Khung ra quyết định (không lộ CoT)
- 3‑Layer: Evidence & Baseline → Options & Risks → Decision & Plan. Mọi kết luận phải có số liệu và citation.
- `TREE‑OF‑THOUGHT` (chỉ kết luận):
  - Tạo ≥ 3 nhánh (ví dụ):
    - A: Python + `[FastAPI]` + worker GPU; batching, async I/O, `[uvloop]`, `[pydantic]`.
    - B: Hybrid FFI: lõi `[Rust]` gọi từ Python qua `[PyO3/FFI]`; GPU qua `[CUDA Runtime API]`.
    - C: Service Mesh: tách inference (gRPC + `[xDS]`/`[Envoy]`).
  - So sánh định lượng (bắt buộc): bảng p95/Complexity/Scalability/DevEx/Ops cost/Risks/Mitigation; chấm điểm 1–5 theo tiêu chí.
  - Quyết định: chọn 1 option; nêu lý do loại 2 option còn lại; dự báo tác động (p95↓, SM util↑, lỗi↓); guardrails (flags/rollback).
- `SELF‑REFINE` (tối đa 2 vòng):
  - Vòng 1: tự phê bình nhanh (mục tiêu/giả định/chi phí, acceptance, trade‑offs).
  - Vòng 2: tinh chỉnh & chốt (citation, đơn giản luồng, rõ boundaries, kế hoạch di trú/rollback, flags). Output bắt buộc: Change Log (3–5 điểm), Evidence Added (logs/tracing/code://path:line), Open Issues, Decision Impact (p95/SM util/error).

---

## 11) Anti‑Hallucination
- Evidence‑Only. Nếu thiếu dữ liệu: ghi rõ “Không đủ thông tin để kết luận” và yêu cầu artefact cụ thể.
- Trích dẫn nguồn chuẩn: `path/to/file:lineStart-lineEnd`. Khi trích mã gốc: giữ nguyên (verbatim).

---

## 12) Deliverables (đầu ra bắt buộc)
- 01 báo cáo Markdown (rõ heading/bullet/code block, luồng mạch lạc).
- 01 sơ đồ kiến trúc (ASCII hoặc `[Mermaid]`).
- 01 skeleton repo: `~/opus-gpu/app/app-gpu` (cây thư mục + mô tả trách nhiệm module).
- 01 kế hoạch di trú M1–M4 (tiêu chí chấp nhận & rollback).
- 01 bộ kiểm thử mẫu (unit/integration/perf) + tiêu chí pass/fail định lượng.
- 01 pipeline CI/CD mẫu (không chứa bí mật).

---

## 13) Cách trình bày đầu ra
- Bám sát Language Rules (chú giải thuật ngữ tiếng Anh).
- Không lộ chain‑of‑thought; trình bày ở mức tiêu chí/ma trận/luồng bước.
- Nếu thiếu dữ liệu: yêu cầu cụ thể (ví dụ: `tree`, `nvidia-smi`, logs/traces, file config, mã nguồn liên quan).
- Mọi trích dẫn mã gốc phải verbatim kèm `path:line`.

---

## 14) Yêu cầu cuối (DoD)
- Thực hiện đầy đủ các mục theo thứ tự; chọn phương án kiến trúc tốt nhất (có điểm & lý do);
- Cung cấp kế hoạch di trú chi tiết (P0/P1/P2), guardrails (feature flags off‑by‑default, rollback);
- Nêu KPI/SLO mục tiêu & tiêu chí đo lường; xác nhận không làm xấu hơn SLO/SLI hiện tại trừ khi có lý do chấp nhận.
