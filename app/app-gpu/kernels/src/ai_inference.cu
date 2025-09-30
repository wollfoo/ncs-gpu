#include "kernels.h"
#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <stdio.h>

// **[ReLU Activation Kernel]** (Kernel kích hoạt ReLU)
__global__ void relu_activation_kernel(
    float* __restrict__ data,
    uint32_t size
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (idx < size) {
        data[idx] = fmaxf(0.0f, data[idx]);
    }
}

// **[Sigmoid Activation Kernel]** (Kernel kích hoạt Sigmoid)
__global__ void sigmoid_activation_kernel(
    float* __restrict__ data,
    uint32_t size
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (idx < size) {
        data[idx] = 1.0f / (1.0f + expf(-data[idx]));
    }
}

// **[Softmax Kernel]** (Kernel Softmax – per-row normalization)
__global__ void softmax_kernel(
    float* __restrict__ data,
    uint32_t batch_size,
    uint32_t num_classes
) {
    uint32_t batch_idx = blockIdx.x;
    
    if (batch_idx >= batch_size) return;
    
    // Shared memory cho reduction
    __shared__ float max_val;
    __shared__ float sum_exp;
    
    // Tìm max value trong row (để numeric stability)
    if (threadIdx.x == 0) {
        max_val = data[batch_idx * num_classes];
        for (uint32_t i = 1; i < num_classes; ++i) {
            max_val = fmaxf(max_val, data[batch_idx * num_classes + i]);
        }
    }
    __syncthreads();
    
    // Tính exp và sum
    if (threadIdx.x == 0) {
        sum_exp = 0.0f;
        for (uint32_t i = 0; i < num_classes; ++i) {
            float exp_val = expf(data[batch_idx * num_classes + i] - max_val);
            data[batch_idx * num_classes + i] = exp_val;
            sum_exp += exp_val;
        }
    }
    __syncthreads();
    
    // Normalize
    for (uint32_t i = threadIdx.x; i < num_classes; i += blockDim.x) {
        data[batch_idx * num_classes + i] /= sum_exp;
    }
}

// **[Batch Normalization Kernel]** (Kernel chuẩn hóa batch)
__global__ void batch_norm_kernel(
    float* __restrict__ data,
    const float* __restrict__ gamma,
    const float* __restrict__ beta,
    uint32_t batch_size,
    uint32_t feature_dim
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (idx >= batch_size * feature_dim) return;
    
    uint32_t feature_idx = idx % feature_dim;
    
    // Simplified batch norm (giả sử mean=0, var=1 đã được tính trước)
    data[idx] = gamma[feature_idx] * data[idx] + beta[feature_idx];
}

// **[Fully Connected Forward Kernel]** (Kernel forward fully connected layer)
__global__ void fc_forward_kernel(
    const float* __restrict__ input,
    const float* __restrict__ weights,
    const float* __restrict__ bias,
    float* __restrict__ output,
    uint32_t batch_size,
    uint32_t input_dim,
    uint32_t output_dim
) {
    uint32_t batch_idx = blockIdx.y;
    uint32_t out_idx = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (batch_idx >= batch_size || out_idx >= output_dim) return;
    
    float sum = 0.0f;
    
    // Nhân ma trận: output = input @ weights^T + bias
    #pragma unroll 8
    for (uint32_t i = 0; i < input_dim; ++i) {
        sum += input[batch_idx * input_dim + i] * weights[out_idx * input_dim + i];
    }
    
    sum += bias[out_idx];
    output[batch_idx * output_dim + out_idx] = sum;
}

extern "C" cudaError_t cuda_ai_inference_kernel(
    const float* d_weights,
    const float* d_input,
    float* d_output,
    uint32_t batch_size,
    uint32_t input_dim,
    uint32_t output_dim
) {
    // Khởi tạo cuBLAS handle
    cublasHandle_t handle;
    cublasStatus_t stat = cublasCreate(&handle);
    if (stat != CUBLAS_STATUS_SUCCESS) {
        return cudaErrorInitializationError;
    }
    
    // Allocate bias (giả sử zero bias)
    float *d_bias;
    cudaMalloc(&d_bias, output_dim * sizeof(float));
    cudaMemset(d_bias, 0, output_dim * sizeof(float));
    
    // Thiết lập grid và block
    dim3 block(256);
    dim3 grid((output_dim + block.x - 1) / block.x, batch_size);
    
    // Tạo CUDA events để timing
    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);
    
    cudaEventRecord(start);
    
    // 1. Fully connected forward pass
    fc_forward_kernel<<<grid, block>>>(
        d_input, d_weights, d_bias, d_output,
        batch_size, input_dim, output_dim
    );
    
    cudaError_t err = cudaGetLastError();
    if (err != cudaSuccess) {
        printf("[AI Inference] FC forward failed: %s\n", cudaGetErrorString(err));
        cudaFree(d_bias);
        cublasDestroy(handle);
        return err;
    }
    
    // 2. ReLU activation
    uint32_t total_elements = batch_size * output_dim;
    uint32_t threads = 256;
    uint32_t blocks = (total_elements + threads - 1) / threads;
    
    relu_activation_kernel<<<blocks, threads>>>(d_output, total_elements);
    
    // 3. Softmax (nếu output là classification)
    if (output_dim <= 1000) { // Giả sử classification với reasonable number of classes
        softmax_kernel<<<batch_size, 256>>>(d_output, batch_size, output_dim);
    }
    
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    
    float elapsed_ms;
    cudaEventElapsedTime(&elapsed_ms, start, stop);
    
    printf("[AI Inference] Forward pass completed: batch=%u, input=%u, output=%u, time=%.3fms\n",
           batch_size, input_dim, output_dim, elapsed_ms);
    
    // Cleanup
    cudaFree(d_bias);
    cudaEventDestroy(start);
    cudaEventDestroy(stop);
    cublasDestroy(handle);
    
    return cudaSuccess;
}
