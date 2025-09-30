#!/bin/bash
# Build script cho GPU Mining System

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== GPU Mining System Build Script ==="
echo ""

# Check dependencies
echo "--- Checking Dependencies ---"

# Rust
if ! command -v cargo &> /dev/null; then
    echo "ERROR: Rust not installed. Install from https://rustup.rs"
    exit 1
fi
echo "✓ Rust: $(rustc --version)"

# CUDA
if ! command -v nvcc &> /dev/null; then
    echo "ERROR: CUDA not installed. Install CUDA Toolkit 12.0+"
    exit 1
fi
echo "✓ CUDA: $(nvcc --version | grep release)"

# CMake
if ! command -v cmake &> /dev/null; then
    echo "ERROR: CMake not installed. Install CMake 3.18+"
    exit 1
fi
echo "✓ CMake: $(cmake --version | head -n1)"

echo ""

# Build Rust workspace
echo "--- Building Rust Workspace ---"
cd "$PROJECT_ROOT"
cargo build --release
echo "✓ Rust build complete"
echo ""

# Build CUDA kernels
echo "--- Building CUDA Kernels ---"
cd "$PROJECT_ROOT/kernels"
mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --config Release
echo "✓ CUDA kernels build complete"
echo ""

# Run tests (optional)
if [ "$1" == "--with-tests" ]; then
    echo "--- Running Tests ---"
    cd "$PROJECT_ROOT"
    cargo test --release
    
    cd "$PROJECT_ROOT/kernels/build"
    ctest --output-on-failure
    echo "✓ All tests passed"
    echo ""
fi

echo "=== Build Complete ==="
echo ""
echo "Binaries:"
echo "  - Coordinator: $PROJECT_ROOT/target/release/coordinator"
echo "  - Worker: $PROJECT_ROOT/target/release/worker"
echo "  - CLI: $PROJECT_ROOT/target/release/gpu-miner"
echo "  - Kernels: $PROJECT_ROOT/kernels/build/libgpu_mining_kernels.so"
echo ""
echo "Run 'make install' to install binaries system-wide."
