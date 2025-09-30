#include "../include/kernels.h"
#include <cuda_runtime.h>
#include <stdio.h>
#include <assert.h>

// **[Test Memory Pool]** (Test bể bộ nhớ)
int test_memory_pool() {
    printf("\n=== Testing Memory Pool ===\n");
    
    const uint32_t pool_size_mb = 128;
    
    // Initialize pool
    printf("Initializing memory pool (%u MB)...\n", pool_size_mb);
    cudaError_t err = init_memory_pool(pool_size_mb);
    assert(err == cudaSuccess);
    
    // Get stats
    size_t total, used, free;
    get_pool_stats(&total, &used, &free);
    
    printf("Pool stats: total=%zu MB, used=%zu MB, free=%zu MB\n",
           total / 1024 / 1024, used / 1024 / 1024, free / 1024 / 1024);
    
    assert(total == (size_t)pool_size_mb * 1024 * 1024);
    assert(used == 0);
    assert(free == total);
    
    // Allocate from pool
    size_t alloc_size = 10 * 1024 * 1024; // 10 MB
    void* ptr = pool_allocate(alloc_size);
    assert(ptr != nullptr);
    
    printf("Allocated %zu MB from pool\n", alloc_size / 1024 / 1024);
    
    get_pool_stats(&total, &used, &free);
    printf("After allocation: used=%zu MB, free=%zu MB\n",
           used / 1024 / 1024, free / 1024 / 1024);
    
    assert(used >= alloc_size);
    
    // Deallocate
    pool_deallocate(ptr);
    printf("Deallocated memory\n");
    
    // Cleanup pool
    cleanup_memory_pool();
    printf("Memory pool cleaned up\n");
    
    printf("PASSED: Memory pool tests\n");
    
    return 0;
}

int main(int argc, char** argv) {
    if (argc > 1 && strcmp(argv[1], "memory_pool") == 0) {
        return test_memory_pool();
    }
    
    int result = 0;
    result |= test_memory_pool();
    
    if (result == 0) {
        printf("\n=== All Memory Pool Tests PASSED ===\n");
    } else {
        printf("\n=== Some Memory Pool Tests FAILED ===\n");
    }
    
    return result;
}
