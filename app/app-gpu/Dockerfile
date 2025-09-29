# Multi-stage Dockerfile for OPUS-GPU v2.0
# Stage 1: Builder with CUDA support

FROM nvidia/cuda:12.2.0-devel-ubuntu22.04 AS builder

# Install Rust and build dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy source code
COPY Cargo.toml Cargo.lock ./
COPY src ./src

# Build in release mode with CUDA features
RUN cargo build --release --features "cuda,metrics,security,enterprise"

# Stage 2: Runtime with minimal footprint
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash opus

# Copy binary from builder
COPY --from=builder /app/target/release/opus-gpu /usr/local/bin/opus-gpu

# Copy configuration templates
RUN mkdir -p /etc/opus-gpu /var/log/opus-gpu /var/lib/opus-gpu
COPY configs/config.toml.template /etc/opus-gpu/config.toml.template

# Set permissions
RUN chown -R opus:opus /etc/opus-gpu /var/log/opus-gpu /var/lib/opus-gpu

# Switch to non-root user
USER opus

# Set environment variables
ENV RUST_LOG=info
ENV OPUS_CONFIG=/etc/opus-gpu/config.toml

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD opus-gpu diagnose || exit 1

# Expose API port
EXPOSE 8080

# Default command
CMD ["opus-gpu", "mine", "--config", "/etc/opus-gpu/config.toml"]