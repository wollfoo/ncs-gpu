#!/bin/bash

# Test script để kiểm tra obfuscation code compiles correctly
# Chạy quick check trên các thay đổi obfuscation

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🧪 Testing obfuscation implementation..."

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

# Test 1: Check syntax
echo -n "Testing code syntax... "
if cargo check --quiet 2>/dev/null; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL - Syntax errors found${NC}"
    cargo check
    exit 1
fi

# Test 2: Check obfuscated build profile
echo -n "Testing obfuscated build profile... "
if cargo check --profile release-obfuscated --quiet 2>/dev/null; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL - Obfuscated profile issues${NC}"
    exit 1
fi

# Test 3: Check dependencies
echo -n "Testing obfuscation dependencies... "
if cargo tree | grep -q obfstr; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL - obfstr not found${NC}"
    exit 1
fi

# Test 4: Quick build test (debug mode cho speed)
echo -n "Testing debug build with obfuscation... "
if cargo build --quiet 2>/dev/null; then
    echo -e "${GREEN}✅ PASS${NC}"

    # Test execution
    echo -n "Testing execution with obfuscation... "
    if timeout 5s cargo run -- --help >/dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}"
    else
        echo -e "${RED}❌ FAIL - Execution failed${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ FAIL - Build failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 All obfuscation tests passed!${NC}"
echo "The obfuscation implementation is syntactically correct and functional."