# Production Dockerfile for App-GPU
# Multi-stage build for optimized production image

#==============================================================================
# Build Stage - Rust compilation
#==============================================================================
FROM rust:1.75-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    ca-certificates \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install CUDA toolkit for compilation (build-time only)
RUN curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-keyring_1.1-1_all.deb \
    -o cuda-keyring.deb && \
    dpkg -i cuda-keyring.deb && \
    apt-get update && apt-get install -y \
    cuda-compiler-12-3 \
    cuda-libraries-dev-12-3 \
    cuda-minimal-build-12-3 \
    && rm -rf /var/lib/apt/lists/* cuda-keyring.deb

# Set CUDA environment for building
ENV CUDA_ROOT=/usr/local/cuda-12.3
ENV PATH=${CUDA_ROOT}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_ROOT}/lib64:${LD_LIBRARY_PATH}

# Create app user and directory
RUN useradd -m -u 1000 appuser
WORKDIR /app
RUN chown -R appuser:appuser /app
USER appuser

# Copy dependency manifests first (for better Docker layer caching)
COPY --chown=appuser:appuser Cargo.toml Cargo.lock ./

# Create stub src/main.rs to satisfy Cargo
RUN mkdir src && echo "fn main() {}" > src/main.rs

# Download and compile dependencies (cached layer)
RUN cargo build --release --locked && rm -rf src/

# Copy actual source code
COPY --chown=appuser:appuser src/ ./src/

# Build the actual application
RUN cargo build --release --locked --bin app-gpu

# Strip binary for smaller size
RUN strip target/release/app-gpu

#==============================================================================
# Runtime Stage - Minimal production image with NVIDIA runtime
#==============================================================================
FROM nvidia/cuda:12.3-runtime-ubuntu20.04

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    tzdata \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Create app user (security best practice)
RUN useradd -m -u 1000 appuser

# Create required directories
RUN mkdir -p /app/logs /app/config /app/data && \
    chown -R appuser:appuser /app

# Copy binary from builder stage
COPY --from=builder /app/target/release/app-gpu /usr/local/bin/app-gpu
RUN chmod +x /usr/local/bin/app-gpu

# Copy configuration template
COPY --chown=appuser:appuser docker/config.toml /app/config/config.toml

# Switch to app user
USER appuser
WORKDIR /app

# Runtime configuration
ENV RUST_LOG=info
ENV RUST_BACKTRACE=1
ENV LOG_LEVEL=info
ENV LOG_FORMAT=json
ENV ENVIRONMENT=production

# GPU configuration
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Network ports
EXPOSE 8080 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9090/health || exit 1

# Use tini for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["app-gpu", "--config", "/app/config/config.toml"]

# Metadata
LABEL maintainer="App-GPU Team" \
      version="0.1.0" \
      description="High-performance GPU mining with event-driven architecture" \
      org.opencontainers.image.title="App-GPU" \
      org.opencontainers.image.description="High-performance GPU mining with event-driven architecture" \
      org.opencontainers.image.vendor="App-GPU Team" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.schema-version="1.0"
