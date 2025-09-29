#!/bin/bash
# Build script for App-GPU
# Script build cho App-GPU

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Building App-GPU...${NC}"

# Check Rust installation
if ! command -v cargo &> /dev/null; then
    echo -e "${RED}❌ Rust is not installed. Please install Rust from https://rustup.rs/${NC}"
    exit 1
fi

# Check CUDA installation (optional but recommended)
if ! command -v nvcc &> /dev/null; then
    echo -e "${YELLOW}⚠️  CUDA compiler (nvcc) not found. GPU features may be limited.${NC}"
fi

# Parse arguments
RELEASE=false
TARGET=""
FEATURES=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --release)
            RELEASE=true
            shift
            ;;
        --target)
            TARGET="$2"
            shift 2
            ;;
        --features)
            FEATURES="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build arguments
BUILD_ARGS=""
if [ "$RELEASE" = true ]; then
    BUILD_ARGS="$BUILD_ARGS --release"
    echo -e "${GREEN}📦 Building in RELEASE mode (optimized)${NC}"
else
    echo -e "${YELLOW}🔧 Building in DEBUG mode${NC}"
fi

if [ -n "$TARGET" ]; then
    BUILD_ARGS="$BUILD_ARGS --target $TARGET"
    echo -e "${GREEN}🎯 Target: $TARGET${NC}"
fi

if [ -n "$FEATURES" ]; then
    BUILD_ARGS="$BUILD_ARGS --features $FEATURES"
    echo -e "${GREEN}✨ Features: $FEATURES${NC}"
fi

# Clean previous build (optional)
# cargo clean

# Format code
echo -e "${GREEN}📝 Formatting code...${NC}"
cargo fmt

# Lint code
echo -e "${GREEN}🔍 Running clippy...${NC}"
cargo clippy --all-targets --all-features -- -D warnings

# Build
echo -e "${GREEN}🔨 Building...${NC}"
cargo build $BUILD_ARGS

# Run tests
echo -e "${GREEN}🧪 Running tests...${NC}"
cargo test $BUILD_ARGS

# Success
if [ "$RELEASE" = true ]; then
    BINARY_PATH="target/release/app-gpu"
    if [ -n "$TARGET" ]; then
        BINARY_PATH="target/$TARGET/release/app-gpu"
    fi
    
    echo -e "${GREEN}✅ Build successful!${NC}"
    echo -e "${GREEN}📍 Binary location: $BINARY_PATH${NC}"
    
    # Show binary size
    if [ -f "$BINARY_PATH" ]; then
        SIZE=$(du -h "$BINARY_PATH" | cut -f1)
        echo -e "${GREEN}📏 Binary size: $SIZE${NC}"
    fi
else
    echo -e "${GREEN}✅ Debug build successful!${NC}"
fi

echo -e "${GREEN}🎉 Done!${NC}"
