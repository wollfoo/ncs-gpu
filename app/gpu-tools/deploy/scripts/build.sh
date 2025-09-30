#!/bin/bash
# Build script for OPUS-GPU tools
# Builds both Rust miner và Go tools

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"
VERSION="${VERSION:-dev}"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GIT_COMMIT="${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}OPUS-GPU Build Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo "Version: $VERSION"
echo "Build date: $BUILD_DATE"
echo "Git commit: $GIT_COMMIT"
echo ""

# ============================================================================
# Build Rust miner binary
# ============================================================================
build_rust() {
    echo -e "${YELLOW}Building Rust miner binary...${NC}"

    cd "$ROOT_DIR/app"

    if [ ! -f "Cargo.toml" ]; then
        echo -e "${RED}Error: Cargo.toml not found${NC}"
        exit 1
    fi

    # Clean previous build
    cargo clean

    # Build release binary
    cargo build --release --bin gpu-miner

    # Strip binary
    strip target/release/gpu-miner

    # Copy to build directory
    mkdir -p "$BUILD_DIR/bin"
    cp target/release/gpu-miner "$BUILD_DIR/bin/"

    echo -e "${GREEN}✓ Rust binary built successfully${NC}"
    ls -lh "$BUILD_DIR/bin/gpu-miner"
}

# ============================================================================
# Build Go tools
# ============================================================================
build_go_tools() {
    echo -e "${YELLOW}Building Go tools...${NC}"

    cd "$ROOT_DIR/gpu-tools"

    # Download dependencies
    go mod download
    go mod verify

    # Build flags
    LDFLAGS="-s -w -X main.Version=$VERSION -X main.BuildDate=$BUILD_DATE -X main.GitCommit=$GIT_COMMIT"

    # Build gpu-ctl
    echo "Building gpu-ctl..."
    CGO_ENABLED=0 go build -ldflags="$LDFLAGS" -o "$BUILD_DIR/bin/gpu-ctl" ./cmd/gpu-ctl

    # Build gpu-watchdog
    echo "Building gpu-watchdog..."
    CGO_ENABLED=0 go build -ldflags="$LDFLAGS" -o "$BUILD_DIR/bin/gpu-watchdog" ./cmd/gpu-watchdog

    # Build metrics-aggregator
    echo "Building metrics-aggregator..."
    CGO_ENABLED=0 go build -ldflags="$LDFLAGS" -o "$BUILD_DIR/bin/metrics-aggregator" ./cmd/metrics-aggregator

    echo -e "${GREEN}✓ Go tools built successfully${NC}"
    ls -lh "$BUILD_DIR/bin/gpu-"*
}

# ============================================================================
# Build Docker image
# ============================================================================
build_docker() {
    echo -e "${YELLOW}Building Docker image...${NC}"

    cd "$ROOT_DIR"

    IMAGE_NAME="opus-gpu:$VERSION"

    docker build \
        -t "$IMAGE_NAME" \
        -t "opus-gpu:latest" \
        -f gpu-tools/deploy/docker/Dockerfile.miner \
        --build-arg VERSION="$VERSION" \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg GIT_COMMIT="$GIT_COMMIT" \
        .

    echo -e "${GREEN}✓ Docker image built successfully${NC}"
    docker images opus-gpu
}

# ============================================================================
# Run tests
# ============================================================================
run_tests() {
    echo -e "${YELLOW}Running tests...${NC}"

    # Rust tests
    echo "Running Rust tests..."
    cd "$ROOT_DIR/app"
    cargo test --release

    # Go tests
    echo "Running Go tests..."
    cd "$ROOT_DIR/gpu-tools"
    go test -v ./...

    echo -e "${GREEN}✓ All tests passed${NC}"
}

# ============================================================================
# Main build process
# ============================================================================
main() {
    local BUILD_RUST=true
    local BUILD_GO=true
    local BUILD_DOCKER=false
    local RUN_TESTS=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --rust-only)
                BUILD_GO=false
                shift
                ;;
            --go-only)
                BUILD_RUST=false
                shift
                ;;
            --docker)
                BUILD_DOCKER=true
                shift
                ;;
            --test)
                RUN_TESTS=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --rust-only    Build only Rust binary"
                echo "  --go-only      Build only Go tools"
                echo "  --docker       Build Docker image"
                echo "  --test         Run tests"
                echo "  --help         Show this help"
                exit 0
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                exit 1
                ;;
        esac
    done

    # Clean build directory
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR/bin"

    # Build components
    if [ "$BUILD_RUST" = true ]; then
        build_rust
    fi

    if [ "$BUILD_GO" = true ]; then
        build_go_tools
    fi

    if [ "$BUILD_DOCKER" = true ]; then
        build_docker
    fi

    if [ "$RUN_TESTS" = true ]; then
        run_tests
    fi

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Build completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "Binaries location: $BUILD_DIR/bin"
    echo ""
}

# Run main function
main "$@"
