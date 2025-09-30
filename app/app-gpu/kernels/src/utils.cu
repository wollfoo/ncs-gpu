#include "kernels.h"
#include <cuda_runtime.h>
#include <stdio.h>

// **[Check CUDA Error]** (Kiểm tra lỗi CUDA – helper function)
extern "C" void check_cuda_error(cudaError_t err, const char* file, int line) {
    if (err != cudaSuccess) {
        printf("[CUDA Error] %s at %s:%d - %s\n",
               cudaGetErrorString(err), file, line, cudaGetErrorName(err));
    }
}

// **[Get Device Properties]** (Lấy thuộc tính thiết bị)
extern "C" cudaError_t get_device_properties(int device_id, cudaDeviceProp* props) {
    return cudaGetDeviceProperties(props, device_id);
}

// **[Set Device]** (Thiết lập thiết bị active)
extern "C" cudaError_t set_active_device(int device_id) {
    return cudaSetDevice(device_id);
}

// **[Device Synchronize]** (Đồng bộ thiết bị)
extern "C" cudaError_t synchronize_device() {
    return cudaDeviceSynchronize();
}

// **[Reset Device]** (Reset thiết bị – cleanup)
extern "C" cudaError_t reset_device() {
    return cudaDeviceReset();
}

// **[Get Device Count]** (Lấy số lượng GPU)
extern "C" cudaError_t get_device_count(int* count) {
    return cudaGetDeviceCount(count);
}

// **[Print Device Info]** (In thông tin thiết bị)
extern "C" void print_device_info(int device_id) {
    cudaDeviceProp props;
    cudaError_t err = cudaGetDeviceProperties(&props, device_id);
    
    if (err != cudaSuccess) {
        printf("[Device Info] Failed to get properties for device %d\n", device_id);
        return;
    }
    
    printf("=== GPU Device %d ===\n", device_id);
    printf("  Name: %s\n", props.name);
    printf("  Compute Capability: %d.%d\n", props.major, props.minor);
    printf("  Total Memory: %.2f GB\n", (float)props.totalGlobalMem / (1024*1024*1024));
    printf("  Multiprocessors: %d\n", props.multiProcessorCount);
    printf("  Max Threads/Block: %d\n", props.maxThreadsPerBlock);
    printf("  Max Block Dimensions: (%d, %d, %d)\n",
           props.maxThreadsDim[0], props.maxThreadsDim[1], props.maxThreadsDim[2]);
    printf("  Max Grid Dimensions: (%d, %d, %d)\n",
           props.maxGridSize[0], props.maxGridSize[1], props.maxGridSize[2]);
    printf("  Warp Size: %d\n", props.warpSize);
    printf("  Memory Clock Rate: %.2f GHz\n", props.memoryClockRate / 1e6);
    printf("  Memory Bus Width: %d-bit\n", props.memoryBusWidth);
    printf("  L2 Cache Size: %.2f MB\n", (float)props.l2CacheSize / (1024*1024));
    printf("  Concurrent Kernels: %s\n", props.concurrentKernels ? "Yes" : "No");
    printf("  ECC Enabled: %s\n", props.ECCEnabled ? "Yes" : "No");
    printf("====================\n");
}
