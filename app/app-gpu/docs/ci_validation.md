# Kết quả xác thực CI nội bộ

## Python Lint & Test

- `make lint` → ruff + black pass (không còn cảnh báo).
- `make test` → 4 testcase pass (`tests/unit` + `tests/integration`).
- `make perf` → benchmark `test_batch_throughput_benchmark` mean ≈ 2.25 ms.

## Go / Rust / C++ Build

- `PATH=/usr/local/go/bin:$PATH make go-build` → build thành công control-plane.
- `make rust-build` → `cargo build --release` hoàn tất.
- `make cpp-build` → tạo `libgpu_kernel_stub.a` bằng CMake.

## Artefact log

- Chi tiết pytest: `/tmp/make-test.log` và `/tmp/make-perf.log`.
- Log benchmark chứa OPS ~445 ops/s.
