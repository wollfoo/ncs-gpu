# **[Dockerfile]** (đóng gói OCI – build multi-stage)
# Stage 1: Build
FROM nvidia/cuda:12.0.0-devel-ubuntu22.04 AS build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates pkg-config build-essential git clang && rm -rf /var/lib/apt/lists/*
# Rustup
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH=/root/.cargo/bin:$PATH
WORKDIR /work
COPY Cargo.toml ./
COPY .cargo ./.cargo
RUN mkdir -p src/bin src/gpu kernels config scripts tests && echo "fn main(){}" > src/bin/orchestrator.rs && echo "fn main(){}" > src/bin/worker.rs && echo "pub mod gpu { pub mod opencl; }" > src/lib.rs && echo "__kernel void gemm_naive(__global const float* A,__global const float* B,__global float* C,int N){}" > kernels/gemm.cl
COPY . .
# Tùy chọn: bật GPU feature khi môi trường có OpenCL dev
RUN cargo build --release

# Stage 2: Runtime
FROM nvidia/cuda:12.0.0-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends ocl-icd-libopencl1 ca-certificates wget && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /work/target/release/orchestrator /usr/local/bin/orchestrator
COPY --from=build /work/target/release/worker /usr/local/bin/worker
COPY config ./config
COPY scripts ./scripts
COPY scripts/seccomp-profile.json /seccomp.json
EXPOSE 8080
USER 1000:1000
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["/usr/local/bin/orchestrator"]
