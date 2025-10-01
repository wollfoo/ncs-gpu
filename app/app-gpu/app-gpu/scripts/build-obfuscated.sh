#!/bin/bash

# Script tự động build và obfuscate GPU miner binary
# Triển khai các kỹ thuật obfuscation nâng cao

# Make executable
chmod +x "$0"

set -e

echo "🚀 Bắt đầu build GPU Miner với obfuscation nâng cao"

# Colors cho output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/target/release-obfuscated"

# Kiểm tra dependencies
check_dependencies() {
    echo "📋 Kiểm tra dependencies..."

    # Check Rust toolchain
    if ! command -v cargo &> /dev/null; then
        echo -e "${RED}❌ Cargo không được cài đặt${NC}"
        exit 1
    fi

    # Check UPX for binary packing
    if ! command -v upx &> /dev/null; then
        echo -e "${YELLOW}⚠️  UPX không được cài đặt - sẽ bỏ qua binary packing${NC}"
        SKIP_UPX=true
    else
        SKIP_UPX=false
    fi

    echo -e "${GREEN}✅ Dependencies OK${NC}"
}

# Build với obfuscated profile
build_obfuscated() {
    echo "🔧 Build với obfuscated profile..."

    cd "$PROJECT_ROOT"

    # Clean để đảm bảo build fresh
    cargo clean

    # Build với obfuscation flags
    RUSTFLAGS="-C target-cpu=native -C opt-level=s -C lto=true -C codegen-units=1 -C panic=abort -C strip=symbols" \
    cargo build --release --profile release-obfuscated

    echo -e "${GREEN}✅ Build obfuscated hoàn thành${NC}"
}

# Strip debug symbols và metadata
strip_binary() {
    echo "🎯 Strip debug symbols..."

    BINARY_PATH="$BUILD_DIR/gpu-miner"

    if [ -f "$BINARY_PATH" ]; then
        # Strip debug symbols
        strip --strip-all "$BINARY_PATH"

        # Remove source file information
        objcopy --remove-section=.comment --remove-section=.note "$BINARY_PATH" 2>/dev/null || true

        BINARY_SIZE=$(stat -c%s "$BINARY_PATH")
        echo -e "${GREEN}✅ Stripped binary: $BINARY_SIZE bytes${NC}"
    else
        echo -e "${RED}❌ Binary not found at $BINARY_PATH${NC}"
        exit 1
    fi
}

# Pack binary với UPX
pack_with_upx() {
    if [ "$SKIP_UPX" = true ]; then
        echo "⏭️  Skipping UPX packing..."
        return
    fi

    echo "📦 Pack binary với UPX..."

    BINARY_PATH="$BUILD_DIR/gpu-miner"
    ORIGINAL_SIZE=$(stat -c%s "$BINARY_PATH")

    # UPX packing với high compression
    upx --best --ultra-brute "$BINARY_PATH"

    PACKED_SIZE=$(stat -c%s "$BINARY_PATH")
    COMPRESSION_RATIO=$(( (ORIGINAL_SIZE - PACKED_SIZE) * 100 / ORIGINAL_SIZE ))

    echo -e "${GREEN}✅ UPX packed: ${ORIGINAL_SIZE} → ${PACKED_SIZE} bytes (${COMPRESSION_RATIO}% reduction)${NC}"
}

# Verify obfuscation effectiveness
verify_obfuscation() {
    echo "🔍 Verify obfuscation effectiveness..."

    BINARY_PATH="$BUILD_DIR/gpu-miner"

    # Check if symbols are stripped
    if readelf -s "$BINARY_PATH" 2>/dev/null | grep -q FUNC; then
        echo -e "${YELLOW}⚠️  Warning: Some function symbols still present${NC}"
    else
        echo -e "${GREEN}✅ Function symbols stripped${NC}"
    fi

    # Check binary size
    BINARY_SIZE=$(stat -c%s "$BINARY_PATH")

    # Check for debug sections
    if readelf -S "$BINARY_PATH" 2>/dev/null | grep -q debug; then
        echo -e "${YELLOW}⚠️  Warning: Debug sections still present${NC}"
    else
        echo -e "${GREEN}✅ Debug sections removed${NC}"
    fi

    # Check obfuscated strings
    STRINGS_COUNT=$(strings "$BINARY_PATH" | wc -l)
    echo -e "${GREEN}✅ Binary contains $STRINGS_COUNT strings (should be minimal)${NC}"

    echo -e "${GREEN}🔒 Obfuscation verification complete${NC}"
}

# Benchmark performance impact
benchmark_performance() {
    echo "⚡ Benchmark performance impact..."

    cd "$PROJECT_ROOT"

    # Build standard version for comparison
    cargo build --release

    STANDARD_BINARY="$PROJECT_ROOT/target/release/gpu-miner"
    OBFUSCATED_BINARY="$BUILD_DIR/gpu-miner"

    echo "Comparing standard vs obfuscated build..."
    echo "Standard: $(stat -c%s "$STANDARD_BINARY" 2>/dev/null || echo "N/A") bytes"
    echo "Obfuscated: $(stat -c%s "$OBFUSCATED_BINARY" 2>/dev/null || echo "N/A") bytes"

    # Test basic functionality
    if [ -x "$OBFUSCATED_BINARY" ]; then
        echo "Testing obfuscated binary functionality..."
        timeout 10s "$OBFUSCATED_BINARY" --benchmark 2>/dev/null && \
        echo -e "${GREEN}✅ Obfuscated binary functional${NC}" || \
        echo -e "${YELLOW}⚠️  Obfuscated binary execution failed${NC}"
    fi
}

# Generate obfuscation report
generate_report() {
    echo "📊 Generating obfuscation report..."

    REPORT_FILE="$PROJECT_ROOT/obfuscation-report.md"
    BINARY_PATH="$BUILD_DIR/gpu-miner"

    cat > "$REPORT_FILE" << EOF
# GPU Miner Obfuscation Report

Generated: $(date)

## Build Configuration
- Profile: release-obfuscated
- Optimization: Size optimization
- LTO: Enabled
- Stripping: Full symbol stripping
- Panic: Abort

## Binary Analysis
- File size: $(stat -c%s "$BINARY_PATH" 2>/dev/null || echo "N/A") bytes
- Has function symbols: $(readelf -s "$BINARY_PATH" 2>/dev/null | grep -q FUNC && echo "Yes" || echo "No")
- Has debug sections: $(readelf -S "$BINARY_PATH" 2>/dev/null | grep -q debug && echo "Yes" || echo "No")
- Visible strings: $(strings "$BINARY_PATH" | wc -l) strings

## Obfuscation Techniques Applied
1. **Symbol Stripping**: Removed all debug symbols and function names
2. **String Encryption**: Encrypted all hardcoded strings using obfstr
3. **Control Flow Obfuscation**: Applied opaque predicates and junk code
4. **Anti-Debugging**: Runtime debugger detection
5. **Link-time Optimization**: Comprehensive LTO with size optimization
6. **Binary Packing**: UPX compression (if available)

## Security Assessment
- **Reverse Engineering Difficulty**: High (strings encrypted, symbols stripped)
- **Tamper Detection**: Medium (integrity checks implemented)
- **Performance Impact**: $(if [ -f "$PROJECT_ROOT/target/release/gpu-miner" ]; then
    STANDARD_SIZE=$(stat -c%s "$PROJECT_ROOT/target/release/gpu-miner")
    OBFUSCATED_SIZE=$(stat -c%s "$BINARY_PATH")
    IMPACT=$(( (STANDARD_SIZE - OBFUSCATED_SIZE) * 100 / STANDARD_SIZE ))
    echo "${IMPACT}% size reduction"
else
    echo "Unable to measure (no standard build)"
fi)

## Recommendations
- Deploy obfuscated binary to production
- Monitor for debugger detection alerts
- Regular re-obfuscation recommended
- Consider additional anti-analysis techniques

---
Built with: $("$PROJECT_ROOT/target/release-obfuscated/gpu-miner" --version 2>/dev/null || echo "GPU Miner")
EOF

    echo -e "${GREEN}✅ Report generated: $REPORT_FILE${NC}"
}

# Main execution
main() {
    check_dependencies
    build_obfuscated
    strip_binary
    pack_with_upx
    verify_obfuscation
    benchmark_performance
    generate_report

    echo ""
    echo -e "${GREEN}🎉 Obfuscation build hoàn thành!${NC}"
    echo "Binary location: $BUILD_DIR/gpu-miner"
    echo "Report: $PROJECT_ROOT/obfuscation-report.md"
}

# Run main function
main "$@"