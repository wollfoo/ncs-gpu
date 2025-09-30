#!/bin/bash
#
# OPUS-GPU Build Script
# Builds Rust binary, Go tools, and Docker image
#
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Default values
BUILD_TYPE="${BUILD_TYPE:-release}"
DOCKER_TAG="${DOCKER_TAG:-opus-gpu:latest}"
SKIP_TESTS="${SKIP_TESTS:-false}"
VERBOSE="${VERBOSE:-false}"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

check_dependencies() {
    log_info "Checking build dependencies..."

    local deps=("cargo" "go" "docker")
    local missing=()

    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing+=("$dep")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        log_error "Please install missing dependencies and try again"
        exit 1
    fi

    log_success "All dependencies found"
}

build_rust_binary() {
    log_info "Building Rust binary (gpu-miner)..."

    cd "$PROJECT_ROOT"

    if [ "$BUILD_TYPE" = "release" ]; then
        log_info "Building in RELEASE mode..."
        cargo build --release --bin gpu-miner
        BINARY_PATH="$PROJECT_ROOT/target/release/gpu-miner"
    else
        log_info "Building in DEBUG mode..."
        cargo build --bin gpu-miner
        BINARY_PATH="$PROJECT_ROOT/target/debug/gpu-miner"
    fi

    if [ -f "$BINARY_PATH" ]; then
        log_success "Rust binary built successfully"
        log_info "Binary location: $BINARY_PATH"
        log_info "Binary size: $(du -h "$BINARY_PATH" | cut -f1)"
    else
        log_error "Failed to build Rust binary"
        exit 1
    fi
}

run_rust_tests() {
    if [ "$SKIP_TESTS" = "true" ]; then
        log_warning "Skipping Rust tests (SKIP_TESTS=true)"
        return
    fi

    log_info "Running Rust tests..."

    cd "$PROJECT_ROOT"

    if cargo test --lib --bins; then
        log_success "Rust tests passed"
    else
        log_error "Rust tests failed"
        exit 1
    fi
}

build_go_tools() {
    log_info "Building Go tools..."

    cd "$PROJECT_ROOT/gpu-tools"

    local tools=("gpu-ctl" "gpu-watchdog" "gpu-monitor")

    mkdir -p bin

    for tool in "${tools[@]}"; do
        log_info "Building $tool..."

        if go build -o "bin/$tool" -ldflags="-s -w" "cmd/$tool/main.go"; then
            log_success "Built $tool"
            log_info "Binary size: $(du -h "bin/$tool" | cut -f1)"
        else
            log_error "Failed to build $tool"
            exit 1
        fi
    done

    log_success "All Go tools built successfully"
}

run_go_tests() {
    if [ "$SKIP_TESTS" = "true" ]; then
        log_warning "Skipping Go tests (SKIP_TESTS=true)"
        return
    fi

    log_info "Running Go tests..."

    cd "$PROJECT_ROOT/gpu-tools"

    if go test ./...; then
        log_success "Go tests passed"
    else
        log_error "Go tests failed"
        exit 1
    fi
}

build_docker_image() {
    log_info "Building Docker image: $DOCKER_TAG..."

    cd "$PROJECT_ROOT"

    # Check if Dockerfile exists
    if [ ! -f "Dockerfile" ]; then
        log_error "Dockerfile not found at $PROJECT_ROOT/Dockerfile"
        exit 1
    fi

    local docker_args=()

    if [ "$VERBOSE" = "true" ]; then
        docker_args+=("--progress=plain")
    fi

    docker_args+=(
        "-t" "$DOCKER_TAG"
        "-f" "Dockerfile"
        "."
    )

    if docker build "${docker_args[@]}"; then
        log_success "Docker image built successfully: $DOCKER_TAG"

        # Show image info
        log_info "Image details:"
        docker images "$DOCKER_TAG" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    else
        log_error "Failed to build Docker image"
        exit 1
    fi
}

show_build_summary() {
    log_info "==================================="
    log_success "Build Summary"
    log_info "==================================="

    echo ""
    echo "Rust Binary:"
    if [ -f "$PROJECT_ROOT/target/release/gpu-miner" ]; then
        ls -lh "$PROJECT_ROOT/target/release/gpu-miner"
    fi

    echo ""
    echo "Go Tools:"
    if [ -d "$PROJECT_ROOT/gpu-tools/bin" ]; then
        ls -lh "$PROJECT_ROOT/gpu-tools/bin"
    fi

    echo ""
    echo "Docker Image:"
    docker images "$DOCKER_TAG" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

    log_info "==================================="
}

# Main execution
main() {
    log_info "Starting OPUS-GPU build process..."
    log_info "Build type: $BUILD_TYPE"
    log_info "Docker tag: $DOCKER_TAG"
    log_info "Skip tests: $SKIP_TESTS"

    check_dependencies

    # Build Rust binary
    build_rust_binary
    run_rust_tests

    # Build Go tools
    build_go_tools
    run_go_tests

    # Build Docker image
    build_docker_image

    # Show summary
    show_build_summary

    log_success "Build completed successfully!"
}

# Run main function
main "$@"
