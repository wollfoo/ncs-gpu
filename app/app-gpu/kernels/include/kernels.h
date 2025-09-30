#ifndef GPU_MINING_KERNELS_H
#define GPU_MINING_KERNELS_H

#include <cuda_runtime.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// AI Training Kernels - Huấn luyện AI (GEMM, loss, backprop simulation)
// ============================================================================

/**
 * **[CUDA AI Training Kernel]** (Kernel huấn luyện AI – GEMM + loss computation)
 * 
 * @param d_input: Device pointer đầu vào
 * @param d_output: Device pointer đầu ra
 * @param batch_size: Kích thước batch
 * @param feature_dim: Số chiều đặc trưng
 * @param duration_ms: Thời gian chạy (milliseconds)
 */
cudaError_t cuda_ai_training_kernel(
    float* d_input,
    float* d_output,
    uint32_t batch_size,
    uint32_t feature_dim,
    uint64_t duration_ms
);

// ============================================================================
// Image Processing Kernels - Xử lý ảnh (convolution, resize, batching)
// ============================================================================

/**
 * **[CUDA Image Processing Kernel]** (Kernel xử lý ảnh – convolution 2D)
 * 
 * @param d_image: Device pointer ảnh đầu vào
 * @param d_output: Device pointer ảnh đầu ra
 * @param width: Chiều rộng ảnh
 * @param height: Chiều cao ảnh
 * @param kernel_size: Kích thước kernel convolution
 */
cudaError_t cuda_image_processing_kernel(
    float* d_image,
    float* d_output,
    uint32_t width,
    uint32_t height,
    uint32_t kernel_size
);

// ============================================================================
// Scientific Computing Kernels - Tính toán khoa học (FFT, BLAS)
// ============================================================================

/**
 * **[CUDA FFT Kernel]** (Kernel FFT – Fast Fourier Transform)
 * 
 * @param d_input: Device pointer complex input
 * @param d_output: Device pointer complex output
 * @param size: Kích thước FFT (power of 2)
 */
cudaError_t cuda_fft_kernel(
    float2* d_input,
    float2* d_output,
    uint32_t size
);

// ============================================================================
// AI Inference Kernels - Suy luận AI (forward pass, activation)
// ============================================================================

/**
 * **[CUDA AI Inference Kernel]** (Kernel suy luận AI – forward pass)
 * 
 * @param d_weights: Device pointer trọng số
 * @param d_input: Device pointer đầu vào
 * @param d_output: Device pointer đầu ra
 * @param batch_size: Kích thước batch
 * @param input_dim: Số chiều đầu vào
 * @param output_dim: Số chiều đầu ra
 */
cudaError_t cuda_ai_inference_kernel(
    const float* d_weights,
    const float* d_input,
    float* d_output,
    uint32_t batch_size,
    uint32_t input_dim,
    uint32_t output_dim
);

// ============================================================================
// Memory Pool - Quản lý bộ nhớ (memory pooling for allocations)
// ============================================================================

/**
 * **[Initialize Memory Pool]** (Khởi tạo memory pool – pre-allocate GPU memory)
 * 
 * @param pool_size_mb: Kích thước pool (MB)
 * @return cudaError_t
 */
cudaError_t init_memory_pool(uint32_t pool_size_mb);

/**
 * **[Cleanup Memory Pool]** (Dọn dẹp memory pool – free GPU memory)
 */
void cleanup_memory_pool();

#ifdef __cplusplus
}
#endif

#endif // GPU_MINING_KERNELS_H
