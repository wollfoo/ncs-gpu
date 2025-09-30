# Multi-stage build cho GPU Mining System
# Stage 1: Builder
FROM nvidia/cuda:12.2.0-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH=/usr/local/cargo/bin:$PATH

# Cài Rust và build tools
RUN apt-get update && apt-get install -y \
    curl build-essential cmake pkg-config libssl-dev \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency manifests
COPY Cargo.toml Cargo.lock ./
COPY crates ./crates

# Build Rust workspace
RUN cargo build --release

# Build CUDA kernels
COPY kernels ./kernels
RUN cd kernels && \
    cmake -B build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build

# Stage 2: Runtime
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    ca-certificates libssl3 && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r gpuminer && useradd -r -g gpuminer -u 1000 gpuminer

WORKDIR /app

# Copy binaries từ builder
COPY --from=builder /build/target/release/coordinator /app/bin/
COPY --from=builder /build/target/release/worker /app/bin/
COPY --from=builder /build/target/release/gpu-miner /app/bin/
COPY --from=builder /build/kernels/build/*.so /app/lib/

# Copy configs
COPY config /app/config

# Set ownership
RUN chown -R gpuminer:gpuminer /app

USER gpuminer

ENV LD_LIBRARY_PATH=/app/lib:$LD_LIBRARY_PATH
ENV RUST_LOG=info

EXPOSE 50051 9090

ENTRYPOINT ["/app/bin/coordinator"]
CMD ["--config", "/app/config/default.toml"]
