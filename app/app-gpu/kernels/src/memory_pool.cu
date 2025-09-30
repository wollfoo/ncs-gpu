#include "kernels.h"
#include <cuda_runtime.h>
#include <stdio.h>
#include <vector>
#include <mutex>

// **[Memory Pool]** (Bể bộ nhớ – pre-allocated GPU memory manager)
struct MemoryPool {
    void* base_ptr;           // Con trỏ base của pool
    size_t total_size;        // Tổng kích thước (bytes)
    size_t used_size;         // Đã dùng (bytes)
    std::vector<void*> free_blocks;  // Danh sách blocks rảnh
    std::mutex mutex;         // Lock cho thread safety
    
    MemoryPool() : base_ptr(nullptr), total_size(0), used_size(0) {}
};

// Global memory pool instance
static MemoryPool g_pool;

extern "C" cudaError_t init_memory_pool(uint32_t pool_size_mb) {
    std::lock_guard<std::mutex> lock(g_pool.mutex);
    
    if (g_pool.base_ptr != nullptr) {
        printf("[Memory Pool] Warning: Pool already initialized\n");
        return cudaSuccess;
    }
    
    g_pool.total_size = (size_t)pool_size_mb * 1024 * 1024;
    
    // Allocate GPU memory
    cudaError_t err = cudaMalloc(&g_pool.base_ptr, g_pool.total_size);
    if (err != cudaSuccess) {
        printf("[Memory Pool] cudaMalloc failed: %s\n", cudaGetErrorString(err));
        return err;
    }
    
    g_pool.used_size = 0;
    g_pool.free_blocks.clear();
    
    printf("[Memory Pool] Initialized: %u MB allocated\n", pool_size_mb);
    
    return cudaSuccess;
}

extern "C" void cleanup_memory_pool() {
    std::lock_guard<std::mutex> lock(g_pool.mutex);
    
    if (g_pool.base_ptr != nullptr) {
        cudaFree(g_pool.base_ptr);
        g_pool.base_ptr = nullptr;
        g_pool.total_size = 0;
        g_pool.used_size = 0;
        g_pool.free_blocks.clear();
        
        printf("[Memory Pool] Cleaned up\n");
    }
}

// **[Allocate from Pool]** (Cấp phát từ pool – custom allocator)
extern "C" void* pool_allocate(size_t size) {
    std::lock_guard<std::mutex> lock(g_pool.mutex);
    
    if (g_pool.base_ptr == nullptr) {
        printf("[Memory Pool] Error: Pool not initialized\n");
        return nullptr;
    }
    
    // Kiểm tra còn đủ memory không
    if (g_pool.used_size + size > g_pool.total_size) {
        printf("[Memory Pool] Error: Out of memory (requested: %zu, available: %zu)\n",
               size, g_pool.total_size - g_pool.used_size);
        return nullptr;
    }
    
    // Tìm free block phù hợp (first-fit strategy)
    for (auto it = g_pool.free_blocks.begin(); it != g_pool.free_blocks.end(); ++it) {
        // TODO: Implement proper block size tracking
        // Hiện tại chỉ demo cơ bản
    }
    
    // Cấp phát từ tail
    void* ptr = (char*)g_pool.base_ptr + g_pool.used_size;
    g_pool.used_size += size;
    
    return ptr;
}

// **[Deallocate to Pool]** (Giải phóng về pool)
extern "C" void pool_deallocate(void* ptr) {
    std::lock_guard<std::mutex> lock(g_pool.mutex);
    
    if (g_pool.base_ptr == nullptr || ptr == nullptr) {
        return;
    }
    
    // Thêm vào free blocks
    g_pool.free_blocks.push_back(ptr);
    
    // TODO: Implement coalescing (gộp các blocks liền kề)
}

// **[Get Pool Stats]** (Lấy thống kê pool)
extern "C" void get_pool_stats(size_t* total, size_t* used, size_t* free) {
    std::lock_guard<std::mutex> lock(g_pool.mutex);
    
    *total = g_pool.total_size;
    *used = g_pool.used_size;
    *free = g_pool.total_size - g_pool.used_size;
}
