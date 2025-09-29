# Multi-stage Dockerfile for App-GPU
# Stage 1: Rust Builder
# Stage 2: CUDA Kernel Builder  
# Stage 3: Runtime (slim)

# ============================================================================
# Stage 1: Rust Builder
# ============================================================================
FROM rust:1.75-slim AS rust-builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy Cargo files for dependency caching
COPY Cargo.toml Cargo.lock ./
COPY crates/ ./crates/

# Build dependencies (cached layer)
RUN cargo build --release --locked

# Build application
RUN cargo build --release --locked

# Strip binary to reduce size
RUN strip target/release/app-gpu

# ============================================================================
# Stage 2: CUDA Kernel Builder
# ============================================================================
FROM nvidia/cuda:12.0.0-devel-ubuntu22.04 AS cuda-builder

# Install build tools
RUN apt-get update && apt-get install -y \
    cmake \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy CUDA kernel source
COPY cuda-kernels/ ./cuda-kernels/

# Build CUDA kernels
WORKDIR /build/cuda-kernels
RUN cmake -DCMAKE_BUILD_TYPE=Release . && make -j$(nproc)

# ============================================================================
# Stage 3: Runtime (slim)
# ============================================================================
FROM nvidia/cuda:12.0.0-runtime-ubuntu22.04

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user (non-root for security)
RUN groupadd -r appgpu && useradd -r -g appgpu appgpu

# Create directories
RUN mkdir -p /etc/app-gpu /var/log/app-gpu /var/lib/app-gpu && \
    chown -R appgpu:appgpu /var/log/app-gpu /var/lib/app-gpu

# Copy binary from rust-builder
COPY --from=rust-builder /build/target/release/app-gpu /usr/local/bin/app-gpu
RUN chmod +x /usr/local/bin/app-gpu

# Copy CUDA libraries from cuda-builder
COPY --from=cuda-builder /build/cuda-kernels/*.so /usr/local/lib/
RUN ldconfig

# Copy configuration
COPY config/ /etc/app-gpu/

# Set environment variables
ENV RUST_LOG=info \
    RUST_BACKTRACE=1 \
    CUDA_VISIBLE_DEVICES=all \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Expose Prometheus metrics port
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9090/health || exit 1

# Switch to non-root user
USER appgpu

# Set working directory
WORKDIR /var/lib/app-gpu

# Entry point
ENTRYPOINT ["/usr/local/bin/app-gpu"]

# Default arguments
CMD ["--config", "/etc/app-gpu/config.toml"]
