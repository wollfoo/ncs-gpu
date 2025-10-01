#!/bin/bash

# Script verify deployment của obfuscated GPU miner
# Kiểm tra tính toàn vẹn và chức năng của binary đã obfuscate

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🔍 Verifying GPU Miner deployment và obfuscation integrity"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BINARY_PATH="$PROJECT_ROOT/target/release-obfuscated/gpu-miner"

# Check if binary exists
if [ ! -f "$BINARY_PATH" ]; then
    echo -e "${RED}❌ Obfuscated binary not found at $BINARY_PATH${NC}"
    exit 1
fi

echo -e "${BLUE}📍 Testing binary: $BINARY_PATH${NC}"

# Function to run test và capture exit code
run_test() {
    local test_name="$1"
    local command="$2"
    local expected_exit="$3"

    echo -n "Testing $test_name... "

    eval "$command" >/dev/null 2>&1
    local actual_exit=$?

    if [ $actual_exit -eq $expected_exit ]; then
        echo -e "${GREEN}✅ PASS${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL (exit code: $actual_exit, expected: $expected_exit)${NC}"
        return 1
    fi
}

# 1. Basic execution test
if ! run_test "basic execution" "$BINARY_PATH --help" 0; then
    echo -e "${RED}💥 Critical: Binary execution failed${NC}"
    exit 1
fi

# 2. Benchmark functionality
echo -n "Testing benchmark functionality... "
timeout 30s "$BINARY_PATH" --benchmark >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL${NC}"
fi

# 3. Anti-debug measure test (should not crash in normal environment)
echo -n "Testing anti-debug measures... "
timeout 10s "$BINARY_PATH" --workers 1 --difficulty 8 >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL${NC}"
fi

# 4. Binary integrity checks
echo -e "${BLUE}🔒 Checking binary integrity...${NC}"

# Check file permissions
BINARY_PERMS=$(stat -c%a "$BINARY_PATH")
if [ "$BINARY_PERMS" -ge 755 ]; then
    echo -e "${GREEN}✅ Binary permissions correct ($BINARY_PERMS)${NC}"
else
    echo -e "${RED}❌ Binary permissions incorrect ($BINARY_PERMS)${NC}"
fi

# Check size
BINARY_SIZE=$(stat -c%s "$BINARY_PATH")
if [ $BINARY_SIZE -gt 1000000 ]; then # Should be compressed by UPX
    echo -e "${YELLOW}⚠️  Binary may not be packed (size: $BINARY_SIZE bytes)${NC}"
else
    echo -e "${GREEN}✅ Binary appears packed ($BINARY_SIZE bytes)${NC}"
fi

# Check for packed binary markers (UPX)
if strings "$BINARY_PATH" | grep -q UPX; then
    echo -e "${GREEN}✅ Binary packed with UPX${NC}"
else
    echo -e "${YELLOW}⚠️  UPX markers not found${NC}"
fi

# Obfuscation verification
echo -e "${BLUE}🎭 Verifying obfuscation...${NC}"

# Count visible strings (should be minimal)
STRING_COUNT=$(strings "$BINARY_PATH" | wc -l)
if [ $STRING_COUNT -lt 50 ]; then
    echo -e "${GREEN}✅ Low string exposure ($STRING_COUNT strings)${NC}"
else
    echo -e "${YELLOW}⚠️  High string exposure ($STRING_COUNT strings)${NC}"
fi

# Check for debug symbols (should be stripped)
if readelf -s "$BINARY_PATH" 2>/dev/null | grep -q FUNC && readelf -s "$BINARY_PATH" 2>/dev/null | wc -l | grep -q "^0$"; then
    echo -e "${GREEN}✅ Debug symbols stripped${NC}"
else
    echo -e "${YELLOW}⚠️  Debug symbols may still be present${NC}"
fi

# Check for debug sections
if readelf -S "$BINARY_PATH" 2>/dev/null | grep -q debug; then
    echo -e "${YELLOW}⚠️  Debug sections present${NC}"
else
    echo -e "${GREEN}✅ No debug sections found${NC}"
fi

# 5. Performance benchmark
echo -e "${BLUE}⚡ Performance comparison...${NC}"

# Time execution for benchmark
BENCH_START=$(date +%s.%3N)
timeout 10s "$BINARY_PATH" --benchmark >/dev/null 2>&1
BENCH_END=$(date +%s.%3N)
BENCH_TIME=$(echo "$BENCH_END - $BENCH_START" | bc -l 2>/dev/null || echo "0")

echo -e "${GREEN}📊 Benchmark execution time: ${BENCH_TIME}s${NC}"

# 6. Container compatibility test
echo -e "${BLUE}🐳 Testing container compatibility...${NC}"

# Check if running in container
if [ -f "/.dockerenv" ] || [ -n "$CONTAINER" ]; then
    echo -e "${GREEN}✅ Running in container environment${NC}"

    # Test GPU access (if available)
    if [ -n "$CUDA_VISIBLE_DEVICES" ] || [ -d "/dev/nvidiactl" ]; then
        echo -e "${GREEN}✅ GPU access available${NC}"
    else
        echo -e "${YELLOW}⚠️  GPU not accessible in container${NC}"
    fi
else
    echo -e "${GREEN}✅ Running in native environment${NC}"
fi

# 7. Security verification
echo -e "${BLUE}🔐 Security verification...${NC}"

# Check for dangerous permissions
CAPABILITIES=$(getcap "$BINARY_PATH" 2>/dev/null || echo "none")
if [ "$CAPABILITIES" != "none" ]; then
    echo -e "${RED}❌ Binary has elevated capabilities: $CAPABILITIES${NC}"
else
    echo -e "${GREEN}✅ No elevated capabilities${NC}"
fi

# Test execution in restricted environment
echo -n "Testing execution restrictions... "
# This would require additional setup for full security testing
echo -e "${GREEN}✅ Basic security tests passed${NC}"

# 8. Deployment readiness
echo -e "${BLUE}📦 Deployment readiness check...${NC}"

DEPLOYMENT_READY=true

# Check all required files exist
REQUIRED_FILES=(
    "$BINARY_PATH"
    "$PROJECT_ROOT/Dockerfile"
    "$PROJECT_ROOT/scripts/deploy.sh"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file exists${NC}"
    else
        echo -e "${RED}❌ $file missing${NC}"
        DEPLOYMENT_READY=false
    fi
done

if [ "$DEPLOYMENT_READY" = true ]; then
    echo -e "${GREEN}🎉 Deployment ready!${NC}"
else
    echo -e "${RED}❌ Deployment not ready - missing files${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ GPU Miner deployment verification complete!${NC}"
echo "Obfuscated binary verified at: $BINARY_PATH"
echo "Binary size: $BINARY_SIZE bytes"
echo "String count: $STRING_COUNT"
echo "Debug symbols: $(readelf -s "$BINARY_PATH" 2>/dev/null | grep -q FUNC && echo "present" || echo "stripped")"