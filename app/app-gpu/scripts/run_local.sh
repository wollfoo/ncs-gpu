#!/usr/bin/env bash
set -euo pipefail

# **[Run Local]** (chạy cục bộ – orchestrator + worker)
RUST_LOG=${RUST_LOG:-info}

# Orchestrator
( RUST_LOG=$RUST_LOG ORCH_ADDR=127.0.0.1:8080 cargo run --release --bin orchestrator ) &
ORCH_PID=$!

# Đảm bảo orchestrator lắng nghe
sleep 1

# Worker
RUST_LOG=$RUST_LOG ORCH_URL=http://127.0.0.1:8080 cargo run --release --bin worker

trap "kill ${ORCH_PID} || true" EXIT
