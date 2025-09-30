cmake_minimum_required(VERSION 3.18)
project(gpu_mining_kernels CUDA CXX)

# Yêu cầu CUDA 12.0+
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CXX_STANDARD 17)

# Tìm CUDA Toolkit
find_package(CUDAToolkit REQUIRED)

# Thiết lập CUDA architecture (compute capability)
# Hỗ trợ: Ampere (8.0), Ada Lovelace (8.9), Hopper (9.0)
set(CMAKE_CUDA_ARCHITECTURES 80 89 90)

# Include directories
include_directories(${CMAKE_CUDA_TOOLKIT_INCLUDE_DIRECTORIES})
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# Source files
set(KERNEL_SOURCES
    src/ai_training.cu
    src/image_processing.cu
    src/scientific_computing.cu
    src/ai_inference.cu
    src/memory_pool.cu
    src/utils.cu
)

# Build shared library
add_library(gpu_mining_kernels SHARED ${KERNEL_SOURCES})

# Link CUDA libraries
target_link_libraries(gpu_mining_kernels
    CUDA::cudart
    CUDA::cublas
    CUDA::cufft
)

# Compiler flags
target_compile_options(gpu_mining_kernels PRIVATE
    $<$<COMPILE_LANGUAGE:CUDA>:
        --use_fast_math
        --maxrregcount=64
        -O3
    >
)

# Install
install(TARGETS gpu_mining_kernels
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)

# Tests
enable_testing()
add_subdirectory(tests)
