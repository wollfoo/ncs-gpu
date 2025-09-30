#include "kernels.h"
#include <cuda_runtime.h>
#include <cufft.h>
#include <cublas_v2.h>
#include <stdio.h>
#include <math.h>

// **[Vector Addition Kernel]** (Kernel cộng vector – BLAS saxpy)
__global__ void vector_add_kernel(
    const float* __restrict__ a,
    const float* __restrict__ b,
    float* __restrict__ c,
    uint32_t n
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (idx < n) {
        c[idx] = a[idx] + b[idx];
    }
}

// **[Matrix Transpose Kernel]** (Kernel chuyển vị ma trận)
__global__ void matrix_transpose_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    uint32_t rows,
    uint32_t cols
) {
    __shared__ float tile[32][33]; // 33 để tránh bank conflicts
    
    uint32_t x = blockIdx.x * blockDim.x + threadIdx.x;
    uint32_t y = blockIdx.y * blockDim.y + threadIdx.y;
    
    // Load vào shared memory
    if (x < cols && y < rows) {
        tile[threadIdx.y][threadIdx.x] = input[y * cols + x];
    }
    
    __syncthreads();
    
    // Tính vị trí sau transpose
    x = blockIdx.y * blockDim.y + threadIdx.x;
    y = blockIdx.x * blockDim.x + threadIdx.y;
    
    // Ghi ra global memory
    if (x < rows && y < cols) {
        output[y * rows + x] = tile[threadIdx.x][threadIdx.y];
    }
}

// **[Reduction Kernel]** (Kernel rút gọn – sum reduction)
__global__ void reduction_sum_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    uint32_t n
) {
    __shared__ float sdata[256];
    
    uint32_t tid = threadIdx.x;
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    // Load vào shared memory
    sdata[tid] = (idx < n) ? input[idx] : 0.0f;
    __syncthreads();
    
    // **[Tree Reduction]** (Rút gọn dạng cây)
    for (uint32_t s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) {
            sdata[tid] += sdata[tid + s];
        }
        __syncthreads();
    }
    
    // Thread 0 ghi kết quả
    if (tid == 0) {
        atomicAdd(output, sdata[0]);
    }
}

// **[Dot Product Kernel]** (Kernel tích vô hướng)
__global__ void dot_product_kernel(
    const float* __restrict__ a,
    const float* __restrict__ b,
    float* __restrict__ result,
    uint32_t n
) {
    __shared__ float sdata[256];
    
    uint32_t tid = threadIdx.x;
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    sdata[tid] = 0.0f;
    if (idx < n) {
        sdata[tid] = a[idx] * b[idx];
    }
    __syncthreads();
    
    // Reduction
    for (uint32_t s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) {
            sdata[tid] += sdata[tid + s];
        }
        __syncthreads();
    }
    
    if (tid == 0) {
        atomicAdd(result, sdata[0]);
    }
}

extern "C" cudaError_t cuda_fft_kernel(
    float2* d_input,
    float2* d_output,
    uint32_t size
) {
    // Kiểm tra size là power of 2
    if ((size & (size - 1)) != 0) {
        printf("[FFT] Error: size must be power of 2\n");
        return cudaErrorInvalidValue;
    }
    
    // Tạo cuFFT plan
    cufftHandle plan;
    cufftResult result = cufftPlan1d(&plan, size, CUFFT_C2C, 1);
    
    if (result != CUFFT_SUCCESS) {
        printf("[FFT] cufftPlan1d failed: %d\n", result);
        return cudaErrorInitializationError;
    }
    
    // Thực hiện FFT forward
    result = cufftExecC2C(plan, (cufftComplex*)d_input, (cufftComplex*)d_output, CUFFT_FORWARD);
    
    if (result != CUFFT_SUCCESS) {
        printf("[FFT] cufftExecC2C failed: %d\n", result);
        cufftDestroy(plan);
        return cudaErrorLaunchFailure;
    }
    
    cudaDeviceSynchronize();
    
    printf("[Scientific Computing] FFT completed: size=%u\n", size);
    
    cufftDestroy(plan);
    return cudaSuccess;
}

// **[Main Scientific Computing Kernel]** (Kernel tính toán khoa học chính)
extern "C" cudaError_t cuda_scientific_computing_kernel(
    float* d_data_a,
    float* d_data_b,
    float* d_result,
    uint32_t size
) {
    uint32_t threads = 256;
    uint32_t blocks = (size + threads - 1) / threads;
    
    // 1. Vector addition
    vector_add_kernel<<<blocks, threads>>>(d_data_a, d_data_b, d_result, size);
    
    cudaError_t err = cudaGetLastError();
    if (err != cudaSuccess) {
        printf("[Scientific] Vector add failed: %s\n", cudaGetErrorString(err));
        return err;
    }
    
    // 2. Dot product
    float *d_dot;
    cudaMalloc(&d_dot, sizeof(float));
    cudaMemset(d_dot, 0, sizeof(float));
    
    dot_product_kernel<<<blocks, threads>>>(d_data_a, d_data_b, d_dot, size);
    
    float h_dot;
    cudaMemcpy(&h_dot, d_dot, sizeof(float), cudaMemcpyDeviceToHost);
    cudaFree(d_dot);
    
    printf("[Scientific Computing] Dot product: %.6f\n", h_dot);
    
    // 3. Reduction (sum)
    float *d_sum;
    cudaMalloc(&d_sum, sizeof(float));
    cudaMemset(d_sum, 0, sizeof(float));
    
    reduction_sum_kernel<<<blocks, threads>>>(d_result, d_sum, size);
    
    float h_sum;
    cudaMemcpy(&h_sum, d_sum, sizeof(float), cudaMemcpyDeviceToHost);
    cudaFree(d_sum);
    
    printf("[Scientific Computing] Sum: %.6f\n", h_sum);
    
    cudaDeviceSynchronize();
    
    return cudaSuccess;
}
