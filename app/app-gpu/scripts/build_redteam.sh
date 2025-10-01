#!/bin/bash
# build_redteam.sh - Build Red Team Research Miner
# RED TEAM RESEARCH - Compilation script for detection research

set -e

# ============================================================================
# Configuration
# ============================================================================
BUILD_TYPE="${BUILD_TYPE:-Release}"
ENABLE_OBFUSCATION="${ENABLE_OBFUSCATION:-ON}"
ENABLE_ANTI_DEBUG="${ENABLE_ANTI_DEBUG:-ON}"
STRIP_SYMBOLS="${STRIP_SYMBOLS:-ON}"
CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES:-75;86;89}"
BUILD_DIR="${BUILD_DIR:-build}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# Functions
# ============================================================================
print_header() {
    echo -e "${GREEN}========================================"
    echo -e "Red Team GPU Miner - Build Script"
    echo -e "========================================${NC}"
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    print_info "Checking dependencies..."

    local missing_deps=()

    # Check for CMake
    if ! command -v cmake &>/dev/null; then
        missing_deps+=("cmake")
    fi

    # Check for CUDA
    if ! command -v nvcc &>/dev/null; then
        missing_deps+=("nvidia-cuda-toolkit")
    fi

    # Check for OpenSSL
    if ! pkg-config --exists openssl; then
        missing_deps+=("libssl-dev")
    fi

    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_error "Missing dependencies: ${missing_deps[*]}"
        echo ""
        echo "Install with:"
        echo "  sudo apt-get install ${missing_deps[*]}"
        exit 1
    fi

    print_info "All dependencies satisfied"
}

configure_build() {
    print_info "Configuring build..."
    print_info "  Build Type: $BUILD_TYPE"
    print_info "  Obfuscation: $ENABLE_OBFUSCATION"
    print_info "  Anti-Debug: $ENABLE_ANTI_DEBUG"
    print_info "  Strip Symbols: $STRIP_SYMBOLS"
    print_info "  CUDA Architectures: $CUDA_ARCHITECTURES"

    cmake -B "$BUILD_DIR" -G Ninja \
        -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
        -DENABLE_OBFUSCATION="$ENABLE_OBFUSCATION" \
        -DENABLE_ANTI_DEBUG="$ENABLE_ANTI_DEBUG" \
        -DSTRIP_SYMBOLS="$STRIP_SYMBOLS" \
        -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCHITECTURES"
}

build_project() {
    print_info "Building project..."

    local cpu_cores
    cpu_cores=$(nproc)
    print_info "Using $cpu_cores CPU cores"

    cmake --build "$BUILD_DIR" --parallel "$cpu_cores"
}

display_results() {
    print_info "Build completed successfully!"
    echo ""
    print_info "Binary location: $BUILD_DIR/redteam-miner"

    if [ -f "$BUILD_DIR/redteam-miner" ]; then
        local binary_size
        binary_size=$(du -h "$BUILD_DIR/redteam-miner" | cut -f1)
        print_info "Binary size: $binary_size"

        # Check if symbols were stripped
        if ! file "$BUILD_DIR/redteam-miner" | grep -q "not stripped"; then
            print_info "Symbols: Stripped ✓"
        else
            print_warning "Symbols: Not stripped"
        fi
    fi

    echo ""
    print_info "To run the miner:"
    echo "  cd $BUILD_DIR"
    echo "  ./redteam-miner --config ../config/miner_config.json"
}

# ============================================================================
# Main Execution
# ============================================================================
main() {
    print_header

    # Research context warning
    echo ""
    print_warning "⚠️  RED TEAM RESEARCH BUILD"
    print_warning "This tool is for authorized security research only"
    echo ""

    check_dependencies
    configure_build
    build_project
    display_results

    echo ""
    print_info "Build process complete!"
}

# Run main function
main "$@"
