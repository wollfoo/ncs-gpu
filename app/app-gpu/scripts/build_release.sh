#!/bin/bash
# Build Release Script (Script dựng bản phát hành)
# Biên dịch Rust binary với full optimization

set -euo pipefail

echo "🔨 Building Opus GPU Mining System (Release Mode)"
echo "=================================================="

# Colors (màu sắc cho terminal)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Rust installation (kiểm tra cài đặt Rust)
if ! command -v cargo &> /dev/null; then
    echo -e "${RED}❌ Rust is not installed${NC}"
    echo "Install with: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

echo -e "${GREEN}✅ Rust $(rustc --version) detected${NC}"

# Check CUDA installation (kiểm tra cài đặt CUDA)
if ! command -v nvcc &> /dev/null; then
    echo -e "${YELLOW}⚠️ CUDA not detected, GPU features will be disabled${NC}"
else
    echo -e "${GREEN}✅ CUDA $(nvcc --version | grep release | awk '{print $5}') detected${NC}"
fi

# Clean previous builds (xóa build cũ)
echo ""
echo "🧹 Cleaning previous builds..."
cargo clean

# Build release binary (dựng binary phát hành)
echo ""
echo "⚙️ Building release binary (this may take a few minutes)..."
echo "   Optimization level: 3 (maximum)"
echo "   LTO: fat (aggressive inlining)"
echo "   Strip: true (remove debug symbols)"
echo ""

if cargo build --release; then
    echo -e "${GREEN}✅ Build successful!${NC}"
else
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi

# Display binary info (hiển thị thông tin binary)
echo ""
echo "📦 Binary Information:"
BINARY_PATH="target/release/mining-cli"

if [ -f "$BINARY_PATH" ]; then
    echo "   Path: $BINARY_PATH"
    echo "   Size: $(du -h $BINARY_PATH | awk '{print $1}')"
    echo "   Type: $(file $BINARY_PATH | cut -d':' -f2-)"
else
    echo -e "${RED}❌ Binary not found at $BINARY_PATH${NC}"
    exit 1
fi

# Run tests (chạy kiểm thử)
echo ""
read -p "Run tests? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧪 Running tests..."
    cargo test --release
    echo -e "${GREEN}✅ All tests passed!${NC}"
fi

# Optional: Strip and compress (tùy chọn: loại bỏ symbols và nén)
echo ""
read -p "Apply additional optimization (UPX compression)? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v upx &> /dev/null; then
        echo "🗜️ Compressing with UPX..."
        cp $BINARY_PATH ${BINARY_PATH}.backup
        upx --best --lzma $BINARY_PATH
        echo -e "${GREEN}✅ Compressed! New size: $(du -h $BINARY_PATH | awk '{print $1}')${NC}"
    else
        echo -e "${YELLOW}⚠️ UPX not installed, skipping compression${NC}"
        echo "Install with: sudo apt-get install upx"
    fi
fi

echo ""
echo "=================================================="
echo -e "${GREEN}🎉 Build Complete!${NC}"
echo ""
echo "To run the mining system:"
echo "   ./target/release/mining-cli start --config config/default.toml"
echo ""
echo "To view usage:"
echo "   ./target/release/mining-cli --help"
echo ""
