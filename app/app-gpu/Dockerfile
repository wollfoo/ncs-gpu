# Multi-stage Docker build for OPUS-GPU
# Stage 1: Build environment with CUDA and development tools
FROM nvidia/cuda:12.2-devel-ubuntu22.04 AS builder

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH \
    RUST_VERSION=1.75.0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libssl-dev \
    libsqlite3-dev \
    libpq-dev \
    cmake \
    clang \
    llvm-dev \
    libclang-dev \
    ocl-icd-opencl-dev \
    opencl-headers \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain $RUST_VERSION
RUN rustup component add rustfmt clippy

# Verify Rust installation
RUN cargo --version && rustc --version

# Set work directory
WORKDIR /usr/src/opus-gpu

# Copy workspace configuration
COPY Cargo.toml ./
COPY Cargo.lock ./

# Copy source code
COPY src/ ./src/
COPY core/ ./core/
COPY infrastructure/ ./infrastructure/
COPY plugins/ ./plugins/
COPY api/ ./api/
COPY config/ ./config/
COPY tests/ ./tests/

# Create necessary Cargo.toml files for workspace members
RUN mkdir -p core/pool/src && echo 'fn main() {}' > core/pool/src/lib.rs
RUN echo '[package]\nname = "opus-gpu-pool"\nversion = "1.0.0"\nedition = "2021"\n\n[dependencies]\ntokio = { version = "1.40", features = ["full"] }' > core/pool/Cargo.toml

RUN mkdir -p core/wallet/src && echo 'fn main() {}' > core/wallet/src/lib.rs
RUN echo '[package]\nname = "opus-gpu-wallet"\nversion = "1.0.0"\nedition = "2021"\n\n[dependencies]\ntokio = { version = "1.40", features = ["full"] }' > core/wallet/Cargo.toml

RUN mkdir -p core/monitor/src && echo 'fn main() {}' > core/monitor/src/lib.rs
RUN echo '[package]\nname = "opus-gpu-monitor"\nversion = "1.0.0"\nedition = "2021"\n\n[dependencies]\ntokio = { version = "1.40", features = ["full"] }' > core/monitor/Cargo.toml

RUN mkdir -p infrastructure/storage/src && echo 'fn main() {}' > infrastructure/storage/src/lib.rs
RUN echo '[package]\nname = "opus-gpu-storage"\nversion = "1.0.0"\nedition = "2021"\n\n[dependencies]\ntokio = { version = "1.40", features = ["full"] }' > infrastructure/storage/Cargo.toml

# Create placeholder files for plugin system
RUN mkdir -p plugins/api/src plugins/loader/src plugins/registry/src
RUN echo 'fn main() {}' > plugins/api/src/lib.rs
RUN echo 'fn main() {}' > plugins/loader/src/lib.rs
RUN echo 'fn main() {}' > plugins/registry/src/lib.rs
RUN echo '[package]\nname = "opus-gpu-plugin-api"\nversion = "1.0.0"\nedition = "2021"' > plugins/api/Cargo.toml
RUN echo '[package]\nname = "opus-gpu-plugin-loader"\nversion = "1.0.0"\nedition = "2021"' > plugins/loader/Cargo.toml
RUN echo '[package]\nname = "opus-gpu-plugin-registry"\nversion = "1.0.0"\nedition = "2021"' > plugins/registry/Cargo.toml

# Create placeholder files for API layer
RUN mkdir -p api/rest/src api/websocket/src api/grpc/src
RUN echo 'fn main() {}' > api/rest/src/lib.rs
RUN echo 'fn main() {}' > api/websocket/src/lib.rs
RUN echo 'fn main() {}' > api/grpc/src/lib.rs
RUN echo '[package]\nname = "opus-gpu-api-rest"\nversion = "1.0.0"\nedition = "2021"' > api/rest/Cargo.toml
RUN echo '[package]\nname = "opus-gpu-api-websocket"\nversion = "1.0.0"\nedition = "2021"' > api/websocket/Cargo.toml
RUN echo '[package]\nname = "opus-gpu-api-grpc"\nversion = "1.0.0"\nedition = "2021"' > api/grpc/Cargo.toml

# Build the application
RUN cargo build --release --features "cuda,opencl"

# Stage 2: Runtime environment with minimal CUDA runtime
FROM nvidia/cuda:12.2-runtime-ubuntu22.04 AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    libsqlite3-0 \
    libpq5 \
    ocl-icd-libopencl1 \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN useradd --create-home --shell /bin/bash opus-gpu

# Create application directories
RUN mkdir -p /app/config /app/data /app/logs /app/plugins \
    && chown -R opus-gpu:opus-gpu /app

# Copy compiled binary from builder stage
COPY --from=builder /usr/src/opus-gpu/target/release/opus-gpu /app/opus-gpu

# Copy configuration files
COPY config/ /app/config/

# Set permissions
RUN chmod +x /app/opus-gpu \
    && chown -R opus-gpu:opus-gpu /app

# Switch to application user
USER opus-gpu
WORKDIR /app

# Create default configuration if not exists
RUN echo '[mining]\nalgorithm = "SHA256"\nmax_workers = 4\ndifficulty = 1000000\nwork_timeout_secs = 30\nstats_interval_secs = 5\ngpu_devices = [0]\nworker_threads = 1\nbatch_size = 1000\nmemory_size = 536870912\n\n[pool]\nurls = ["stratum+tcp://pool.example.com:4444"]\nusername = "your_wallet_address"\npassword = "worker1"\nretry_attempts = 3\nretry_delay_secs = 5\nconnection_timeout_secs = 10\nkeepalive_interval_secs = 30\n\n[wallet]\nkeystore_dir = "./keystore"\nbackup_dir = "./backup"\nencryption_enabled = true\n\n[monitoring]\nenabled = true\nmetrics_port = 9090\nstats_interval_secs = 10\ntemperature_threshold = 80.0\nmemory_threshold = 90.0\nenable_alerts = false\n\n[storage]\ndata_dir = "./data"\ndatabase_url = "sqlite://opus-gpu.db"\nmax_connections = 10\nbackup_enabled = true\nbackup_interval_hours = 24\nretention_days = 30\n\n[api.rest]\nhost = "0.0.0.0"\nport = 8080\ncors_enabled = true\ncors_origins = ["*"]\nrate_limit = 100\nrequest_timeout_secs = 30\n\n[api.websocket]\nhost = "0.0.0.0"\nport = 8081\nmax_connections = 1000\nmessage_buffer_size = 1000\nheartbeat_interval_secs = 30\n\n[api.grpc]\nhost = "0.0.0.0"\nport = 8082\nmax_message_size = 4194304\nkeepalive_interval_secs = 30\nkeepalive_timeout_secs = 5\n\n[plugins]\ndisabled = false\nplugin_dir = "./plugins"\nmax_plugins = 50\nload_timeout_secs = 30\nwhitelist = []\nblacklist = []\n\n[bus]\nbuffer_size = 1000\nmax_subscribers = 100\nmessage_timeout_secs = 5\nenable_persistence = false\npersistence_file = "./bus_state.json"' > /app/config/default.toml

# Expose ports
EXPOSE 8080 8081 8082 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Set environment variables
ENV RUST_LOG=info
ENV OPUS_GPU_CONFIG_PATH=/app/config/default.toml
ENV OPUS_GPU_DATA_DIR=/app/data
ENV OPUS_GPU_LOG_LEVEL=info

# Default command
CMD ["./opus-gpu", "--config", "config/default.toml"]

# Stage 3: Development image with additional tools
FROM builder AS development

# Install additional development tools
RUN apt-get update && apt-get install -y \
    gdb \
    valgrind \
    strace \
    htop \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Install cargo development tools
RUN cargo install \
    cargo-watch \
    cargo-edit \
    cargo-audit \
    cargo-outdated \
    cargo-tree

# Set development environment
ENV RUST_LOG=debug
ENV RUST_BACKTRACE=1

WORKDIR /usr/src/opus-gpu

# Default development command
CMD ["cargo", "run"]

# Stage 4: Testing image
FROM builder AS testing

# Install testing dependencies
RUN apt-get update && apt-get install -y \
    lcov \
    && rm -rf /var/lib/apt/lists/*

# Install testing tools
RUN cargo install cargo-tarpaulin

# Run tests
RUN cargo test --all-features

# Generate test coverage
RUN cargo tarpaulin --all-features --out html --output-dir coverage/

# Production image (default target)
FROM runtime AS production