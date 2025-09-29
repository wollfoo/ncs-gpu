#!/bin/bash
# OPUS-GPU v2.0 Production Start Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default configuration
PORT="${PORT:-8080}"
WORKERS="${WORKERS:-4}"
ALGORITHM="${ALGORITHM:-sha256}"

# Start production system
cd "$PROJECT_ROOT"

echo "🚀 Starting OPUS-GPU v2.0 Production System"
echo "   Port: $PORT"
echo "   Workers: $WORKERS"
echo "   Algorithm: $ALGORITHM"

./target/release/opus-production \
    --port "$PORT" \
    --workers "$WORKERS" \
    --algorithm "$ALGORITHM"