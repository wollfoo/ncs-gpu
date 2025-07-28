#\!/bin/bash

# Enhanced Runtime Library Path for NVRTC
# Giải quyết runtime compilation context issues

# Set CUDA environment paths
export CUDA_PATH=/usr/local/cuda-12.0
export CUDA_ROOT=/usr/local/cuda-12.0
export NVRTC_LIB_PATH=/usr/local/cuda-12.0/targets/x86_64-linux/lib

# Enhanced LD_LIBRARY_PATH with NVRTC priority
export LD_LIBRARY_PATH="$NVRTC_LIB_PATH:$LD_LIBRARY_PATH"

# Additional NVRTC-specific paths
export NVRTC_CUDA_PATH=$CUDA_PATH
export CUDA_INCLUDE_DIRS=$CUDA_PATH/include

# Pre-execution verification
echo "[Mon Jul 28 17:33:19 UTC 2025] NVRTC Enhanced Wrapper - Starting verification..."

# Verify NVRTC libraries are accessible
if \! ldconfig -p | grep -q nvrtc-builtins; then
    echo "[Mon Jul 28 17:33:19 UTC 2025] WARNING: NVRTC libraries not found in ldconfig cache, refreshing..."
    ldconfig 2>/dev/null || echo "Warning: ldconfig refresh failed"
fi

# Check critical NVRTC files exist
NVRTC_BUILTINS="/usr/local/cuda-12.0/targets/x86_64-linux/lib/libnvrtc-builtins.so.12.0.140"
if [ \! -f "$NVRTC_BUILTINS" ]; then
    echo "[Mon Jul 28 17:33:19 UTC 2025] ERROR: NVRTC builtins library not found at $NVRTC_BUILTINS"
    exit 1
fi

# Verify library is readable
if [ \! -r "$NVRTC_BUILTINS" ]; then
    echo "[Mon Jul 28 17:33:19 UTC 2025] ERROR: NVRTC builtins library not readable"
    exit 1
fi

echo "[Mon Jul 28 17:33:19 UTC 2025] NVRTC Enhanced Wrapper - Verification complete. Starting inference-cuda..."
echo "[Mon Jul 28 17:33:19 UTC 2025] LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
echo "[Mon Jul 28 17:33:19 UTC 2025] CUDA_PATH: $CUDA_PATH"

# Execute original program with enhanced environment
exec /app/inference-cuda.original "$@"
