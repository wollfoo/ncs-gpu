# app-gpu – Hệ thống orchestrator/worker mô phỏng tải GPU (Rust)
(English) Distributed Orchestrator/worker with GPU load simulation (OpenCL/CPU fallback), secure container defaults.

## Tính năng
- **[Orchestrator]** (máy chủ điều phối – HTTP/Axum): `/enqueue`, `/dequeue`, `/metrics`, `/healthz`.
- **[Worker]** (tác nhân – nhận việc và chạy GPU): Poll `/dequeue`, chạy GEMM giả lập qua **[OpenCL]** (hậu phương GPU) hoặc **[CPU fallback]** (lùi CPU) nếu không có OpenCL.
    - **[Security]** (bảo mật – mặc định an toàn): non-root, seccomp profile mẫu.
    - **[Supply Chain]** (chuỗi cung ứng – SBOM/ký): Make target `sbom`, `sign`.
    - **[Distributed]** (phân tán – nhiều worker): nhiều worker trỏ về 1 Orchestrator.
    
    ## Sơ đồ ASCII – Luồng khai thác GPU
    
    ### Sơ đồ 1: GPU → Thuật toán → Xử lý song song → Kết quả
    ```text
    +--------+    +------------+    +------------------+    +-----------+
    |  GPU   | -> | Thuật toán | -> | Xử lý song song  | -> |  Kết quả  |
    +--------+    +------------+    +------------------+    +-----------+
    ```
    
    ### Sơ đồ 2: Dữ liệu đầu vào → Phân chia tác vụ → GPU xử lý → Tổng hợp kết quả
    ```text
      +-------------+    +------------+    +------------------+    +-------------------+
      |   Dữ liệu   | -> | Phân chia  | -> |  GPU xử lý       | -> | Tổng hợp kết quả  |
      |   đầu vào   |    |  tác vụ    |    | (Song song)      |    | (Reduce/Aggreg.)  |
      +-------------+    +------------+    +------------------+    +-------------------+
              ^                                                               |
              |                                                               v
      +-------------+                                                 +----------------------+
      |  Cấu hình   |                                                 |  Hiệu suất khai thác |
      |  hệ thống   |                                                 |  (metrics/logs)      |
      +-------------+                                                 +----------------------+
    ```
    
    ## Sơ đồ ASCII – Luồng mining GPU qua các module (từ khởi tạo → hoàn thành)
    ```text
    ┌───────────────────────────────────────────────────────────────────────────────────────────┐
    │ 0) Khởi tạo hệ thống                                                                      │
    │   - Orchestrator: đọc cấu hình (env/file), khởi tạo HTTP server Axum                      │
    │   - Worker: đọc CLI/ENV (Clap), khởi tạo HTTP client, đặt chu kỳ poll                     │
    └───────────────────────────────────────────────────────────────────────────────────────────┘
    
          Orchestrator (HTTP/Axum)                           Worker (CLI/Reqwest)                 GPU Backend
    ┌───────────────────────────────────────────┐     ┌──────────────────────────────────┐     ┌───────────────────────┐
    │ 1) Start server                           │     │ 2) Start worker                  │     │ (Chỉ khi bật feature) │
    │    - Routes: /enqueue /dequeue            │     │    - Parse Args (Clap)           │     │    OpenCL / CPU        │
    │             /metrics /healthz             │     │    - Tạo HTTP client (Reqwest)  │     │    fallback            │
    │    - Hàng đợi: VecDeque<Task>             │     │    - POLL_MS (chu kỳ truy vấn)   │     └─────────┬───────────┘
    └───────────────┬───────────────────────────┘     └───────────────┬──────────────────┘               │
                    │ 3) POST /enqueue (Task)                         │ 4) GET /dequeue                  │
                    │  (đẩy Task vào queue)                            │  (rút Task từ queue)            │
                    v                                                  │                                  │
            ┌───────────────────────┐                                  │                                  │
            │ In-memory Queue       │◄─────────────────────────────────┘                                  │
            │ push/pop Task         │                                                                     │
            └─────────┬─────────────┘                                                                     │
                      │ 5) Thực thi tác vụ (tại Worker)                                                   │
                      v                                                                                   v
            ┌────────────────────────────┐                    ┌────────────────────────┐       ┌────────────────────────┐
            │ Task { kind, params, ... } │                    │ Chọn Backend           │       │ 5a) GPU (OpenCL/ocl)  │
            │ (serde – src/lib.rs)       │──────────────────► │ feature "gpu"?         │──────►│  - nạp kernel         │
            └────────────────────────────┘                    │  - Yes: OpenCL         │       │    kernels/gemm.cl     │
                                                             │  - No : CPU fallback   │       │  - enqueue kernel      │
                                                             └──────────┬─────────────┘       │    gemm_naive          │
                                                                        │                     └────────────────────────┘
                                                                        │                     ┌────────────────────────┐
                                                                        │                     │ 5b) CPU fallback       │
                                                                        └────────────────────►│  - vòng lặp GEMM naive │
                                                                                              │    (Rust)              │
                                                                                              └────────────────────────┘
    
                                                          6) Hoàn tất tính toán (local tại Worker)
                                                          ┌───────────────────────────────────────┐
                                                          │ - Ghi logs (Tracing)                  │
                                                          │ - (Tùy chọn) đo đếm hiệu năng         │
                                                          │ - Orchestrator: /metrics -> queue_len │
                                                          └───────────────────────────────────────┘
    
                                                          7) Kết thúc chu kỳ tác vụ
                                                          ┌───────────────────────────────────────┐
                                                          │ - Worker sẵn sàng poll tác vụ tiếp    │
                                                          │ - Orchestrator tiếp tục phục vụ API    │
                                                          └───────────────────────────────────────┘
    ```
    
    ## Build & Run (Local)
    ```bash
    # Build
    cargo build --release
# Run Orchestrator
RUST_LOG=info ORCH_ADDR=0.0.0.0:8080 cargo run --release --bin orchestrator
# Run worker (có thể mở nhiều terminal)
RUST_LOG=info ORCH_URL=http://127.0.0.1:8080 cargo run --release --bin worker
## Docker (OCI)
```bash
# Build image
docker build -t api-models:latest -f Dockerfile .
# Run orchestrator (non-root + seccomp)
docker run --rm -it --gpus all --user 1000:1000 \
  --security-opt seccomp=$(pwd)/scripts/seccomp-profile.json \
  -p 8080:8080 api-models:latest
```

## Enqueue Task
```bash
curl -X POST http://127.0.0.1:8080/enqueue \
  -H 'content-type: application/json' \
  -d '{"kind":{"gemm":{"n":512,"iters":5}}}'
```

## Cấu hình & Bảo mật
- **[Non-root]** (không đặc quyền – user 1000).
- **[Seccomp]** (lọc syscall – profile mẫu trong `scripts/seccomp-profile.json`).
- **[cgroups]** (giới hạn tài nguyên – cấu hình docker `--cpus`, `--memory`, `--gpus`).
- **[SBOM]**: `make sbom` (Syft).
- **[Signing]**: `make sign` (cosign).

## Ghi chú GPU
- Bật tính năng GPU qua feature khi build nếu cần: `cargo build --release --features gpu`.
- Nếu thiếu OpenCL dev, binary vẫn chạy với **[CPU fallback]** (mô phỏng).

## Test
```bash
cargo test --all
```
