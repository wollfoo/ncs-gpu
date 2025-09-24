# syntax=docker/dockerfile:1.6

FROM rust:1.76-slim AS rust-builder
WORKDIR /workspace
RUN apt-get update && apt-get install -y protobuf-compiler && rm -rf /var/lib/apt/lists/*
COPY Cargo.toml Cargo.lock rust-toolchain.toml ./
COPY cmd cmd
COPY internal internal
COPY pkg pkg
COPY gpu/bindings gpu/bindings
COPY tests/rust tests/rust
COPY api api
RUN rustup component add clippy && \
    cargo build --release --locked --package app-gpu && \
    cargo build --release --locked --package gpu-bindings

FROM golang:1.22-alpine AS go-builder
WORKDIR /workspace
COPY cmd/controller/go.mod cmd/controller/go.sum ./
RUN go mod download
COPY cmd/controller ./controller
RUN cd controller && go build -o /out/controller

FROM nvidia/cuda:12.3.1-runtime-ubuntu22.04 AS runtime
ENV APP_USER=miner
RUN useradd -ms /bin/bash ${APP_USER}
WORKDIR /opt/app

COPY --from=rust-builder /workspace/target/release/app-gpu ./bin/app-gpu
COPY --from=rust-builder /workspace/target/release/libgpu_bindings.so ./lib/libgpu_bindings.so
COPY --from=go-builder /out/controller ./bin/controller
COPY gpu/kernels ./gpu/kernels
COPY configs ./configs
COPY observability ./observability
COPY security ./security
COPY scripts ./scripts

RUN chown -R ${APP_USER}:${APP_USER} /opt/app
USER ${APP_USER}
ENV RUST_LOG=info
ENTRYPOINT ["/opt/app/bin/app-gpu"]
