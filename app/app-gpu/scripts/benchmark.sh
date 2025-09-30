#!/bin/bash
# GPU Mining System Benchmark Script
# Đo hiệu năng GPU và throughput của hệ thống

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== GPU Mining System Benchmark ==="
echo "Timestamp: $(date)"
echo ""

# Kiểm tra CUDA
if ! command -v nvidia-smi &> /dev/null; then
    echo "ERROR: nvidia-smi not found. CUDA required."
    exit 1
fi

echo "--- GPU Information ---"
nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv
echo ""

# Kiểm tra binaries
COORDINATOR_BIN="$PROJECT_ROOT/target/release/coordinator"
WORKER_BIN="$PROJECT_ROOT/target/release/worker"
CLI_BIN="$PROJECT_ROOT/target/release/gpu-miner"

if [ ! -f "$COORDINATOR_BIN" ]; then
    echo "ERROR: Coordinator binary not found. Run 'make build' first."
    exit 1
fi

# Khởi động coordinator (background)
echo "--- Starting Coordinator ---"
"$COORDINATOR_BIN" --config "$PROJECT_ROOT/config/default.toml" &
COORDINATOR_PID=$!
echo "Coordinator PID: $COORDINATOR_PID"

# Đợi coordinator khởi động
sleep 2

# Khởi động worker (background)
echo ""
echo "--- Starting Worker ---"
"$WORKER_BIN" --coordinator-addr localhost:50051 &
WORKER_PID=$!
echo "Worker PID: $WORKER_PID"

# Đợi worker đăng ký
sleep 3

# Cleanup function
cleanup() {
    echo ""
    echo "--- Shutting down ---"
    kill $WORKER_PID 2>/dev/null || true
    kill $COORDINATOR_PID 2>/dev/null || true
    wait
}
trap cleanup EXIT

# Run benchmarks
echo ""
echo "--- Running Benchmarks ---"
echo ""

# Benchmark 1: Sequential submission
echo "Benchmark 1: Sequential Task Submission (10 tasks)"
"$CLI_BIN" --coordinator http://localhost:50051 benchmark --num-tasks 10
echo ""

# Benchmark 2: Concurrent submission
echo "Benchmark 2: Concurrent Task Submission (20 tasks)"
"$CLI_BIN" --coordinator http://localhost:50051 benchmark --num-tasks 20 --concurrent
echo ""

# Benchmark 3: Different workload types
echo "Benchmark 3: Workload Type Performance"
for workload in ai-training image-processing scientific-computing ai-inference; do
    echo "  Testing $workload..."
    "$CLI_BIN" --coordinator http://localhost:50051 submit \
        --workload-type "$workload" \
        --duration 10 \
        --batch-size 32 \
        --gpu-utilization 80.0 \
        --memory-mb 512
    sleep 1
done
echo ""

# GPU metrics during benchmark
echo "--- GPU Metrics ---"
nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,temperature.gpu,power.draw --format=csv
echo ""

echo "=== Benchmark Complete ==="
