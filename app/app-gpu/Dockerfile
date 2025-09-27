# Multi-stage Dockerfile for OPUS-GPU v2.0
# Stage 1: Builder
FROM rust:1.75-bullseye AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    cmake \
    pkg-config \
    libssl-dev \
    clang \
    llvm \
    && rm -rf /var/lib/apt/lists/*

# Install CUDA toolkit for build
RUN wget https://developer.download.nvidia.com/compute/cuda/repos/debian11/x86_64/cuda-keyring_1.0-1_all.deb \
    && dpkg -i cuda-keyring_1.0-1_all.deb \
    && apt-get update \
    && apt-get install -y cuda-toolkit-12-0 \
    && rm -rf /var/lib/apt/lists/*

# Set CUDA paths
ENV PATH=/usr/local/cuda-12.0/bin:${PATH}
ENV LD_LIBRARY_PATH=/usr/local/cuda-12.0/lib64:${LD_LIBRARY_PATH}

# Create app directory
WORKDIR /build

# Copy workspace files
COPY Cargo.toml Cargo.lock ./
COPY core ./core
COPY plugins ./plugins
COPY shared ./shared

# Build in release mode with optimizations
RUN cargo build --release --features cuda

# Strip debug symbols
RUN strip /build/target/release/opus-gpu

# Stage 2: Runtime
FROM nvidia/cuda:12.0.0-runtime-ubuntu22.04

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libssl3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r opus && useradd -r -g opus opus

# Create necessary directories
RUN mkdir -p /app/plugins /app/logs /app/config \
    && chown -R opus:opus /app

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/target/release/opus-gpu /app/
COPY --from=builder /build/target/release/*.so /app/plugins/

# Copy configuration
COPY config.yaml /app/config/

# Set environment
ENV RUST_LOG=info
ENV OPUS_CONFIG_PATH=/app/config/config.yaml
ENV OPUS_PLUGIN_DIR=/app/plugins

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["/app/opus-gpu", "--health-check"]

# Switch to non-root user
USER opus

# Expose metrics port
EXPOSE 9090

# Entry point
ENTRYPOINT ["/app/opus-gpu"]
CMD ["--config", "/app/config/config.yaml"]
