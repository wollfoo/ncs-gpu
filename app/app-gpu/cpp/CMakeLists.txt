cmake_minimum_required(VERSION 3.20)
project(gpu_kernel_stub LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(gpu_kernel_stub STATIC src/gpu_kernel_stub.cpp)
target_compile_definitions(gpu_kernel_stub PRIVATE GPU_KERNEL_STUB)
