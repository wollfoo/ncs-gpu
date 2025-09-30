cmake_minimum_required(VERSION 3.18)

# Test executable cho CUDA kernels
add_executable(kernel_tests
    test_ai_training.cu
    test_image_processing.cu
    test_memory_pool.cu
)

target_link_libraries(kernel_tests
    gpu_mining_kernels
    CUDA::cudart
    CUDA::cublas
    CUDA::cufft
)

# Add tests
add_test(NAME AITrainingTest COMMAND kernel_tests ai_training)
add_test(NAME ImageProcessingTest COMMAND kernel_tests image_processing)
add_test(NAME MemoryPoolTest COMMAND kernel_tests memory_pool)
