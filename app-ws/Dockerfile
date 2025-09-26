# Multi-stage build for Opus GPU Engine
# Build stage
FROM rust:1.75-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libssl-dev \
    nvidia-cuda-toolkit \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy Cargo files
COPY Cargo.toml Cargo.lock ./

# Build dependencies (cache layer)
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release && rm -rf src

# Copy source code
COPY src ./src
COPY plugins ./plugins

# Build the application
RUN cargo build --release --features "gpu-metrics cloaking auto-tune"

# Build CUDA plugin
WORKDIR /app/plugins/libmining_cuda
COPY plugins/libmining_cuda/CMakeLists.txt ./
COPY plugins/libmining_cuda/src ./src
COPY plugins/libmining_cuda/include ./include

RUN mkdir build && cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release .. && \
    make -j$(nproc)

# Runtime stage
FROM nvidia/cuda:12.0.0-runtime-ubuntu22.04

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libssl3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 opus

# Copy binary and libraries
COPY --from=builder /app/target/release/opus-gpu /usr/local/bin/
COPY --from=builder /app/plugins/libmining_cuda/build/libmining_cuda.so /usr/local/lib/

# Copy configuration
COPY config /etc/opus-gpu

# Set environment
ENV RUST_LOG=info
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

# Create necessary directories
RUN mkdir -p /var/log/opus-gpu /var/lib/opus-gpu && \
    chown -R opus:opus /var/log/opus-gpu /var/lib/opus-gpu

# Switch to non-root user
USER opus

# Expose metrics port
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9090/metrics || exit 1

# Entry point
ENTRYPOINT ["/usr/local/bin/opus-gpu"]
CMD ["--config", "/etc/opus-gpu/default.toml"]