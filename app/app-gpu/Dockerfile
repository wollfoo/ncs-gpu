# Multi-stage Dockerfile cho GPU Mining System
# Optimized cho security và performance

# Stage 1: Builder - Biên dịch Rust code
FROM rust:1.75-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    cmake \
    g++ \
    cuda-toolkit-11-8 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy Cargo files first cho layer caching
COPY Cargo.toml Cargo.lock ./

# Build dependencies (cache layer)
RUN mkdir src && \
    echo "fn main() {}" > src/main.rs && \
    cargo build --release && \
    rm -rf src

# Copy actual source code
COPY src ./src

# Build final binary với optimizations
RUN cargo build --release --target-dir ./target

# Strip debug symbols để giảm size
RUN strip /build/target/release/gpu-miner

# Stage 2: Runtime - Minimal image cho production
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

# Metadata
LABEL maintainer="Security Research Team" \
      description="GPU Mining System for Security Research" \
      version="0.1.0"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user cho security
RUN groupadd -r miner && \
    useradd -r -g miner -u 1000 \
    -d /home/miner \
    -s /sbin/nologin \
    -c "Mining user" miner

# Create necessary directories
RUN mkdir -p /app/config /app/logs /app/data && \
    chown -R miner:miner /app

# Set working directory
WORKDIR /app

# Copy binary từ builder stage
COPY --from=builder --chown=miner:miner /build/target/release/gpu-miner /app/gpu-miner

# Copy configuration template
COPY --chown=miner:miner config.toml.example /app/config/config.toml.example

# Copy entrypoint script
COPY --chown=miner:miner docker-entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Switch to non-root user
USER miner

# Environment variables với default values
ENV RUST_LOG=info \
    MINING_ALGO=kawpow \
    STEALTH_MODE=true \
    GPU_INDICES=0 \
    INTENSITY=75 \
    CONFIG_PATH=/app/config/config.toml

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["/app/gpu-miner", "--health-check"] || exit 1

# Volumes cho persistent data
VOLUME ["/app/config", "/app/logs", "/app/data"]

# Expose metrics port (optional)
EXPOSE 9090

# Entrypoint với signal handling
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["--config", "/app/config/config.toml"]
