/**
 * CUDA Kernels for GPU Compute Operations
 * High-performance kernels optimized for various workloads
 */

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>

// Warp size constant
#define WARP_SIZE 32
#define FULL_MASK 0xffffffff

// Error checking macro
#define CUDA_CHECK(call) \
    do { \
        cudaError_t error = call; \
        if (error != cudaSuccess) { \
            printf("CUDA error at %s:%d - %s\n", \
                   __FILE__, __LINE__, cudaGetErrorString(error)); \
            return error; \
        } \
    } while(0)

// ============================================================================
// Basic Compute Kernels
// ============================================================================

/**
 * Vector addition kernel
 * c[i] = a[i] + b[i]
 */
__global__ void vector_add_kernel(
    const float* __restrict__ a,
    const float* __restrict__ b,
    float* __restrict__ c,
    size_t n
) {
    size_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    size_t stride = blockDim.x * gridDim.x;
    
    for (size_t i = idx; i < n; i += stride) {
        c[i] = a[i] + b[i];
    }
}

/**
 * Matrix multiplication kernel using shared memory
 * C = A * B
 */
template<int TILE_SIZE>
__global__ void matrix_multiply_kernel(
    const float* __restrict__ A,
    const float* __restrict__ B,
    float* __restrict__ C,
    int M, int N, int K
) {
    __shared__ float tile_A[TILE_SIZE][TILE_SIZE];
    __shared__ float tile_B[TILE_SIZE][TILE_SIZE];
    
    int bx = blockIdx.x, by = blockIdx.y;
    int tx = threadIdx.x, ty = threadIdx.y;
    
    int row = by * TILE_SIZE + ty;
    int col = bx * TILE_SIZE + tx;
    
    float sum = 0.0f;
    
    for (int t = 0; t < (K + TILE_SIZE - 1) / TILE_SIZE; ++t) {
        // Load tiles into shared memory
        if (row < M && t * TILE_SIZE + tx < K) {
            tile_A[ty][tx] = A[row * K + t * TILE_SIZE + tx];
        } else {
            tile_A[ty][tx] = 0.0f;
        }
        
        if (col < N && t * TILE_SIZE + ty < K) {
            tile_B[ty][tx] = B[(t * TILE_SIZE + ty) * N + col];
        } else {
            tile_B[ty][tx] = 0.0f;
        }
        
        __syncthreads();
        
        // Compute partial sum
        #pragma unroll
        for (int k = 0; k < TILE_SIZE; ++k) {
            sum += tile_A[ty][k] * tile_B[k][tx];
        }
        
        __syncthreads();
    }
    
    // Write result
    if (row < M && col < N) {
        C[row * N + col] = sum;
    }
}

/**
 * Reduction kernel for sum operation
 * Optimized with warp-level primitives
 */
__device__ float warp_reduce_sum(float val) {
    for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
        val += __shfl_down_sync(FULL_MASK, val, offset);
    }
    return val;
}

__global__ void reduce_sum_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    size_t n
) {
    extern __shared__ float sdata[];
    
    size_t tid = threadIdx.x;
    size_t idx = blockIdx.x * blockDim.x * 2 + threadIdx.x;
    size_t stride = blockDim.x * gridDim.x * 2;
    
    float sum = 0.0f;
    
    // Grid-stride loop with unrolling
    for (size_t i = idx; i < n; i += stride) {
        sum += input[i];
        if (i + blockDim.x < n) {
            sum += input[i + blockDim.x];
        }
    }
    
    // Store in shared memory
    sdata[tid] = sum;
    __syncthreads();
    
    // Reduce in shared memory
    for (unsigned int s = blockDim.x / 2; s > WARP_SIZE; s >>= 1) {
        if (tid < s) {
            sdata[tid] += sdata[tid + s];
        }
        __syncthreads();
    }
    
    // Final warp reduction
    if (tid < WARP_SIZE) {
        sum = sdata[tid];
        sum = warp_reduce_sum(sum);
        
        if (tid == 0) {
            output[blockIdx.x] = sum;
        }
    }
}

// ============================================================================
// Memory Coalescing Test Kernel
// ============================================================================

/**
 * Memory bandwidth test kernel
 * Coalesced memory access pattern
 */
__global__ void memory_bandwidth_kernel(
    float* __restrict__ dst,
    const float* __restrict__ src,
    size_t n,
    int iterations
) {
    size_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    size_t stride = blockDim.x * gridDim.x;
    
    for (int iter = 0; iter < iterations; ++iter) {
        for (size_t i = idx; i < n; i += stride) {
            // Coalesced read
            float val = src[i];
            
            // Simple computation to prevent optimization
            val = val * 1.01f + 0.01f;
            
            // Coalesced write
            dst[i] = val;
        }
    }
}

// ============================================================================
// Benchmark Kernels
// ============================================================================

/**
 * FLOPS benchmark kernel
 * Performs many floating-point operations
 */
__global__ void flops_benchmark_kernel(
    float* __restrict__ data,
    size_t n,
    int operations_per_thread
) {
    size_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (idx >= n) return;
    
    float x = data[idx];
    float y = 1.0f;
    
    // Perform many FMA operations
    #pragma unroll 16
    for (int i = 0; i < operations_per_thread; ++i) {
        y = fmaf(x, y, 1.0f);  // y = x * y + 1
        x = fmaf(y, x, 2.0f);  // x = y * x + 2
    }
    
    // Store result to prevent optimization
    data[idx] = x + y;
}

/**
 * Integer operations benchmark
 */
__global__ void integer_ops_kernel(
    int* __restrict__ data,
    size_t n,
    int operations_per_thread
) {
    size_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (idx >= n) return;
    
    int x = data[idx];
    int y = 1;
    
    #pragma unroll 16
    for (int i = 0; i < operations_per_thread; ++i) {
        y = x * y + i;
        x = (x ^ y) + (y >> 2);
        y = __popc(x) + __clz(y);  // Population count and leading zeros
    }
    
    data[idx] = x ^ y;
}

// ============================================================================
// Kernel Launchers (C interface)
// ============================================================================

extern "C" {

cudaError_t launch_vector_add(
    const float* a, const float* b, float* c,
    size_t n, cudaStream_t stream
) {
    int block_size = 256;
    int grid_size = (n + block_size - 1) / block_size;
    
    vector_add_kernel<<<grid_size, block_size, 0, stream>>>(a, b, c, n);
    
    return cudaGetLastError();
}

cudaError_t launch_matrix_multiply(
    const float* A, const float* B, float* C,
    int M, int N, int K, cudaStream_t stream
) {
    const int TILE_SIZE = 16;
    dim3 block(TILE_SIZE, TILE_SIZE);
    dim3 grid((N + TILE_SIZE - 1) / TILE_SIZE,
              (M + TILE_SIZE - 1) / TILE_SIZE);
    
    matrix_multiply_kernel<TILE_SIZE><<<grid, block, 0, stream>>>(
        A, B, C, M, N, K
    );
    
    return cudaGetLastError();
}

cudaError_t launch_reduce_sum(
    const float* input, float* output,
    size_t n, cudaStream_t stream
) {
    int block_size = 256;
    int grid_size = (n + block_size * 2 - 1) / (block_size * 2);
    size_t shared_mem_size = block_size * sizeof(float);
    
    reduce_sum_kernel<<<grid_size, block_size, shared_mem_size, stream>>>(
        input, output, n
    );
    
    return cudaGetLastError();
}

cudaError_t launch_memory_bandwidth_test(
    float* dst, const float* src,
    size_t n, int iterations, cudaStream_t stream
) {
    int block_size = 256;
    int grid_size = min(65535, (n + block_size - 1) / block_size);
    
    memory_bandwidth_kernel<<<grid_size, block_size, 0, stream>>>(
        dst, src, n, iterations
    );
    
    return cudaGetLastError();
}

cudaError_t launch_flops_benchmark(
    float* data, size_t n,
    int operations_per_thread, cudaStream_t stream
) {
    int block_size = 256;
    int grid_size = (n + block_size - 1) / block_size;
    
    flops_benchmark_kernel<<<grid_size, block_size, 0, stream>>>(
        data, n, operations_per_thread
    );
    
    return cudaGetLastError();
}

} // extern "C"
