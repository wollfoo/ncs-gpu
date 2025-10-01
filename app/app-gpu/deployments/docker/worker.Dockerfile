# Multi-stage build for GPU Worker
FROM rust:1.75-bookworm as builder

# Install CUDA toolkit for build
RUN apt-get update && apt-get install -y \
    cuda-toolkit-12-0 \
    opencl-headers \
    ocl-icd-opencl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy source code
COPY cmd/worker/Cargo.toml cmd/worker/Cargo.lock ./
COPY cmd/worker/src ./src

# Build release binary with optimizations
RUN cargo build --release

# Runtime stage
FROM nvidia/cuda:12.0.0-runtime-ubuntu22.04

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    ocl-icd-libopencl1 \
    libnuma1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash miner

# Copy binary from builder
COPY --from=builder /build/target/release/gpu-worker /usr/local/bin/

# Set ownership and permissions
RUN chown miner:miner /usr/local/bin/gpu-worker && \
    chmod 755 /usr/local/bin/gpu-worker

# Create config directory
RUN mkdir -p /etc/gpu-mining && \
    chown miner:miner /etc/gpu-mining

USER miner
WORKDIR /home/miner

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:9090/health || exit 1

# Metrics port
EXPOSE 9090

ENTRYPOINT ["/usr/local/bin/gpu-worker"]
CMD ["--config", "/etc/gpu-mining/worker.toml"]
