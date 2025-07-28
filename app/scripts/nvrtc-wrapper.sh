#!/bin/bash

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

# Pre-execution verification (only if verbose mode requested)
if [[ "$1" == "--verbose" ]] || [[ "$NVRTC_WRAPPER_VERBOSE" == "1" ]]; then
    echo "[$(date)] NVRTC Enhanced Wrapper - Starting verification..."
    
    # Verify NVRTC libraries are accessible
    if ! ldconfig -p | grep -q nvrtc-builtins; then
        echo "[$(date)] WARNING: NVRTC libraries not found in ldconfig cache, refreshing..."
        ldconfig 2>/dev/null || echo "Warning: ldconfig refresh failed"
    fi
    
    # Check critical NVRTC files exist
    NVRTC_BUILTINS="/usr/local/cuda-12.0/targets/x86_64-linux/lib/libnvrtc-builtins.so.12.0.140"
    if [ ! -f "$NVRTC_BUILTINS" ]; then
        echo "[$(date)] ERROR: NVRTC builtins library not found at $NVRTC_BUILTINS"
        exit 1
    fi
    
    echo "[$(date)] NVRTC Enhanced Wrapper - Verification complete. Starting inference-cuda..."
    echo "[$(date)] LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
    echo "[$(date)] CUDA_PATH: $CUDA_PATH"
fi

# Execute original program with enhanced environment
exec /usr/local/bin/inference-cuda.original "$@"