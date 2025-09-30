#include "kernels.h"
#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <stdio.h>

// **[GEMM Kernel]** (Kernel nhân ma trận – General Matrix Multiply)
__global__ void gemm_kernel(
    const float* __restrict__ A,
    const float* __restrict__ B,
    float* __restrict__ C,
    uint32_t M,
    uint32_t N,
    uint32_t K
) {
    // Tính toán **[Thread Index]** (chỉ số luồng)
    uint32_t row = blockIdx.y * blockDim.y + threadIdx.y;
    uint32_t col = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (row < M && col < N) {
        float sum = 0.0f;
        
        // Tính tích vô hướng
        #pragma unroll 8
        for (uint32_t k = 0; k < K; ++k) {
            sum += A[row * K + k] * B[k * N + col];
        }
        
        C[row * N + col] = sum;
    }
}

// **[Loss Computation Kernel]** (Kernel tính loss – MSE loss)
__global__ void compute_loss_kernel(
    const float* __restrict__ predictions,
    const float* __restrict__ targets,
    float* __restrict__ loss,
    uint32_t size
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (idx < size) {
        float diff = predictions[idx] - targets[idx];
        atomicAdd(loss, diff * diff);
    }
}

// **[Activation Kernel]** (Kernel activation – ReLU)
__global__ void relu_kernel(float* __restrict__ data, uint32_t size) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (idx < size) {
        data[idx] = fmaxf(0.0f, data[idx]);
    }
}

extern "C" cudaError_t cuda_ai_training_kernel(
    float* d_input,
    float* d_output,
    uint32_t batch_size,
    uint32_t feature_dim,
    uint64_t duration_ms
) {
    // Khởi tạo cuBLAS handle
    cublasHandle_t handle;
    cublasStatus_t stat = cublasCreate(&handle);
    if (stat != CUBLAS_STATUS_SUCCESS) {
        return cudaErrorInitializationError;
    }
    
    // Thiết lập **[Grid và Block Dimensions]** (kích thước lưới và khối)
    dim3 block(16, 16);
    dim3 grid((feature_dim + block.x - 1) / block.x, 
              (batch_size + block.y - 1) / block.y);
    
    // Tạo **[CUDA Events]** (sự kiện CUDA – timing)
    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);
    
    cudaEventRecord(start);
    
    // Allocate temporary buffers
    float *d_weights, *d_temp;
    cudaMalloc(&d_weights, feature_dim * feature_dim * sizeof(float));
    cudaMalloc(&d_temp, batch_size * feature_dim * sizeof(float));
    
    // Khởi tạo weights random (giả lập)
    // Trong thực tế sẽ load từ file hoặc generate
    
    // Vòng lặp training simulation
    uint64_t iterations = 0;
    float elapsed_ms = 0.0f;
    
    while (elapsed_ms < duration_ms) {
        // Forward pass: GEMM
        gemm_kernel<<<grid, block>>>(
            d_input, d_weights, d_temp,
            batch_size, feature_dim, feature_dim
        );
        
        // Activation: ReLU
        uint32_t total_elements = batch_size * feature_dim;
        uint32_t threads = 256;
        uint32_t blocks = (total_elements + threads - 1) / threads;
        relu_kernel<<<blocks, threads>>>(d_temp, total_elements);
        
        // Loss computation (giả lập)
        float *d_loss;
        cudaMalloc(&d_loss, sizeof(float));
        cudaMemset(d_loss, 0, sizeof(float));
        
        compute_loss_kernel<<<blocks, threads>>>(
            d_temp, d_output, d_loss, total_elements
        );
        
        cudaFree(d_loss);
        
        // Synchronize và tính elapsed time
        cudaEventRecord(stop);
        cudaEventSynchronize(stop);
        cudaEventElapsedTime(&elapsed_ms, start, stop);
        
        iterations++;
    }
    
    printf("[AI Training] Completed %lu iterations in %.2f ms\n", iterations, elapsed_ms);
    
    // Cleanup
    cudaFree(d_weights);
    cudaFree(d_temp);
    cudaEventDestroy(start);
    cudaEventDestroy(stop);
    cublasDestroy(handle);
    
    return cudaGetLastError();
}
