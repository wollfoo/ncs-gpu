#include "../include/kernels.h"
#include <cuda_runtime.h>
#include <stdio.h>
#include <assert.h>

// **[Test Image Processing Kernel]** (Test kernel xử lý ảnh)
int test_image_processing_kernel() {
    printf("\n=== Testing Image Processing Kernel ===\n");
    
    const uint32_t width = 512;
    const uint32_t height = 512;
    const uint32_t kernel_size = 3;
    
    // Allocate device memory
    float *d_image, *d_output;
    size_t size = width * height * sizeof(float);
    
    cudaError_t err = cudaMalloc(&d_image, size);
    assert(err == cudaSuccess);
    
    err = cudaMalloc(&d_output, size);
    assert(err == cudaSuccess);
    
    // Initialize input image
    float *h_image = (float*)malloc(size);
    for (size_t i = 0; i < width * height; i++) {
        h_image[i] = (float)(i % 256) / 255.0f; // Gradient pattern
    }
    
    cudaMemcpy(d_image, h_image, size, cudaMemcpyHostToDevice);
    
    // Run kernel
    printf("Running image processing kernel (convolution)...\n");
    err = cuda_image_processing_kernel(d_image, d_output, width, height, kernel_size);
    
    if (err != cudaSuccess) {
        printf("FAILED: %s\n", cudaGetErrorString(err));
        cudaFree(d_image);
        cudaFree(d_output);
        free(h_image);
        return 1;
    }
    
    // Verify output
    float *h_output = (float*)malloc(size);
    cudaMemcpy(h_output, d_output, size, cudaMemcpyDeviceToHost);
    
    // Sanity check - output should be different from input
    bool is_different = false;
    for (size_t i = 0; i < width * height; i++) {
        if (fabsf(h_output[i] - h_image[i]) > 0.001f) {
            is_different = true;
            break;
        }
    }
    
    assert(is_different && "Output should be different from input after convolution");
    
    printf("PASSED: Image processing kernel executed successfully\n");
    
    // Cleanup
    cudaFree(d_image);
    cudaFree(d_output);
    free(h_image);
    free(h_output);
    
    return 0;
}

int main(int argc, char** argv) {
    if (argc > 1 && strcmp(argv[1], "image_processing") == 0) {
        return test_image_processing_kernel();
    }
    
    int result = 0;
    result |= test_image_processing_kernel();
    
    if (result == 0) {
        printf("\n=== All Image Processing Tests PASSED ===\n");
    } else {
        printf("\n=== Some Image Processing Tests FAILED ===\n");
    }
    
    return result;
}
