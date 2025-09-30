#include "kernels.h"
#include <cuda_runtime.h>
#include <stdio.h>

// **[Convolution 2D Kernel]** (Kernel tích chập 2D – image filtering)
__global__ void convolution_2d_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    const float* __restrict__ kernel,
    uint32_t width,
    uint32_t height,
    uint32_t kernel_size
) {
    uint32_t x = blockIdx.x * blockDim.x + threadIdx.x;
    uint32_t y = blockIdx.y * blockDim.y + threadIdx.y;
    
    if (x >= width || y >= height) return;
    
    int half_kernel = kernel_size / 2;
    float sum = 0.0f;
    
    // Tích chập với kernel
    #pragma unroll
    for (int ky = -half_kernel; ky <= half_kernel; ++ky) {
        #pragma unroll
        for (int kx = -half_kernel; kx <= half_kernel; ++kx) {
            int nx = x + kx;
            int ny = y + ky;
            
            // **[Boundary Handling]** (Xử lý biên – clamp to edge)
            nx = max(0, min((int)width - 1, nx));
            ny = max(0, min((int)height - 1, ny));
            
            int kernel_idx = (ky + half_kernel) * kernel_size + (kx + half_kernel);
            sum += input[ny * width + nx] * kernel[kernel_idx];
        }
    }
    
    output[y * width + x] = sum;
}

// **[Gaussian Blur Kernel]** (Kernel làm mờ Gaussian)
__global__ void gaussian_blur_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    uint32_t width,
    uint32_t height,
    float sigma
) {
    uint32_t x = blockIdx.x * blockDim.x + threadIdx.x;
    uint32_t y = blockIdx.y * blockDim.y + threadIdx.y;
    
    if (x >= width || y >= height) return;
    
    int radius = (int)(3.0f * sigma);
    float sum = 0.0f;
    float weight_sum = 0.0f;
    
    for (int dy = -radius; dy <= radius; ++dy) {
        for (int dx = -radius; dx <= radius; ++dx) {
            int nx = x + dx;
            int ny = y + dy;
            
            if (nx >= 0 && nx < (int)width && ny >= 0 && ny < (int)height) {
                float dist = sqrtf((float)(dx * dx + dy * dy));
                float weight = expf(-(dist * dist) / (2.0f * sigma * sigma));
                
                sum += input[ny * width + nx] * weight;
                weight_sum += weight;
            }
        }
    }
    
    output[y * width + x] = sum / weight_sum;
}

// **[Resize Kernel]** (Kernel thay đổi kích thước – bilinear interpolation)
__global__ void resize_bilinear_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    uint32_t src_width,
    uint32_t src_height,
    uint32_t dst_width,
    uint32_t dst_height
) {
    uint32_t x = blockIdx.x * blockDim.x + threadIdx.x;
    uint32_t y = blockIdx.y * blockDim.y + threadIdx.y;
    
    if (x >= dst_width || y >= dst_height) return;
    
    // Tính vị trí trong ảnh gốc
    float src_x = ((float)x + 0.5f) * (float)src_width / (float)dst_width - 0.5f;
    float src_y = ((float)y + 0.5f) * (float)src_height / (float)dst_height - 0.5f;
    
    int x0 = (int)floorf(src_x);
    int y0 = (int)floorf(src_y);
    int x1 = x0 + 1;
    int y1 = y0 + 1;
    
    // Clamp to boundaries
    x0 = max(0, min((int)src_width - 1, x0));
    x1 = max(0, min((int)src_width - 1, x1));
    y0 = max(0, min((int)src_height - 1, y0));
    y1 = max(0, min((int)src_height - 1, y1));
    
    float dx = src_x - x0;
    float dy = src_y - y0;
    
    // **[Bilinear Interpolation]** (Nội suy song tuyến)
    float v00 = input[y0 * src_width + x0];
    float v10 = input[y0 * src_width + x1];
    float v01 = input[y1 * src_width + x0];
    float v11 = input[y1 * src_width + x1];
    
    float v0 = v00 * (1.0f - dx) + v10 * dx;
    float v1 = v01 * (1.0f - dx) + v11 * dx;
    float result = v0 * (1.0f - dy) + v1 * dy;
    
    output[y * dst_width + x] = result;
}

extern "C" cudaError_t cuda_image_processing_kernel(
    float* d_image,
    float* d_output,
    uint32_t width,
    uint32_t height,
    uint32_t kernel_size
) {
    // Thiết lập grid và block dimensions
    dim3 block(16, 16);
    dim3 grid((width + block.x - 1) / block.x, 
              (height + block.y - 1) / block.y);
    
    // Tạo Gaussian kernel trên device
    float *d_kernel;
    cudaMalloc(&d_kernel, kernel_size * kernel_size * sizeof(float));
    
    // Khởi tạo Gaussian kernel (simplified)
    float h_kernel[25]; // Max 5x5 kernel
    float sigma = 1.0f;
    int half = kernel_size / 2;
    float sum = 0.0f;
    
    for (int y = 0; y < (int)kernel_size; ++y) {
        for (int x = 0; x < (int)kernel_size; ++x) {
            int dx = x - half;
            int dy = y - half;
            float dist = sqrtf((float)(dx * dx + dy * dy));
            h_kernel[y * kernel_size + x] = expf(-(dist * dist) / (2.0f * sigma * sigma));
            sum += h_kernel[y * kernel_size + x];
        }
    }
    
    // Normalize
    for (uint32_t i = 0; i < kernel_size * kernel_size; ++i) {
        h_kernel[i] /= sum;
    }
    
    cudaMemcpy(d_kernel, h_kernel, kernel_size * kernel_size * sizeof(float), cudaMemcpyHostToDevice);
    
    // Launch convolution kernel
    convolution_2d_kernel<<<grid, block>>>(
        d_image, d_output, d_kernel,
        width, height, kernel_size
    );
    
    cudaError_t err = cudaGetLastError();
    if (err != cudaSuccess) {
        printf("[Image Processing] Kernel launch failed: %s\n", cudaGetErrorString(err));
        cudaFree(d_kernel);
        return err;
    }
    
    // Synchronize
    cudaDeviceSynchronize();
    
    printf("[Image Processing] Convolution completed: %dx%d image, %dx%d kernel\n",
           width, height, kernel_size, kernel_size);
    
    cudaFree(d_kernel);
    return cudaSuccess;
}
