#include "../include/kernels.h"
#include <cuda_runtime.h>
#include <stdio.h>
#include <assert.h>

// **[Test AI Training Kernel]** (Test kernel huấn luyện AI)
int test_ai_training_kernel() {
    printf("\n=== Testing AI Training Kernel ===\n");
    
    const uint32_t batch_size = 32;
    const uint32_t feature_dim = 256;
    const uint64_t duration_ms = 100; // Short duration for test
    
    // Allocate device memory
    float *d_input, *d_output;
    size_t size = batch_size * feature_dim * sizeof(float);
    
    cudaError_t err = cudaMalloc(&d_input, size);
    assert(err == cudaSuccess);
    
    err = cudaMalloc(&d_output, size);
    assert(err == cudaSuccess);
    
    // Initialize input with random data
    float *h_input = (float*)malloc(size);
    for (size_t i = 0; i < batch_size * feature_dim; i++) {
        h_input[i] = (float)rand() / RAND_MAX;
    }
    
    cudaMemcpy(d_input, h_input, size, cudaMemcpyHostToDevice);
    
    // Run kernel
    printf("Running AI training kernel...\n");
    err = cuda_ai_training_kernel(d_input, d_output, batch_size, feature_dim, duration_ms);
    
    if (err != cudaSuccess) {
        printf("FAILED: %s\n", cudaGetErrorString(err));
        cudaFree(d_input);
        cudaFree(d_output);
        free(h_input);
        return 1;
    }
    
    // Verify output
    float *h_output = (float*)malloc(size);
    cudaMemcpy(h_output, d_output, size, cudaMemcpyDeviceToHost);
    
    // Simple sanity check - output should not be all zeros
    bool has_nonzero = false;
    for (size_t i = 0; i < batch_size * feature_dim; i++) {
        if (h_output[i] != 0.0f) {
            has_nonzero = true;
            break;
        }
    }
    
    assert(has_nonzero && "Output should contain non-zero values");
    
    printf("PASSED: AI Training kernel executed successfully\n");
    
    // Cleanup
    cudaFree(d_input);
    cudaFree(d_output);
    free(h_input);
    free(h_output);
    
    return 0;
}

int main(int argc, char** argv) {
    if (argc > 1 && strcmp(argv[1], "ai_training") == 0) {
        return test_ai_training_kernel();
    }
    
    // Run all tests
    int result = 0;
    result |= test_ai_training_kernel();
    
    if (result == 0) {
        printf("\n=== All AI Training Tests PASSED ===\n");
    } else {
        printf("\n=== Some AI Training Tests FAILED ===\n");
    }
    
    return result;
}
