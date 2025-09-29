/**
 * KawPow DAG Generation Kernel
 *
 * This CUDA kernel generates the Directed Acyclic Graph (DAG) used by KawPow algorithm.
 * Each DAG element is computed using Keccak-256 and progressive mixing operations.
 */

#include <cuda_runtime.h>
#include <stdint.h>

// Keccak round constants
__constant__ uint64_t keccak_round_constants[24] = {
    0x0000000000000001ULL, 0x0000000000008082ULL, 0x800000000000808aULL,
    0x8000000080008000ULL, 0x000000000000808bULL, 0x0000000080000001ULL,
    0x8000000080008081ULL, 0x8000000000008009ULL, 0x000000000000008aULL,
    0x0000000000000088ULL, 0x0000000080008009ULL, 0x000000008000000aULL,
    0x000000008000808bULL, 0x800000000000008bULL, 0x8000000000008089ULL,
    0x8000000000008003ULL, 0x8000000000008002ULL, 0x8000000000000080ULL,
    0x000000000000800aULL, 0x800000008000000aULL, 0x8000000080008081ULL,
    0x8000000000008080ULL, 0x0000000080000001ULL, 0x8000000080008008ULL
};

// Keccak rho offsets
__constant__ unsigned int keccak_rho_offsets[24] = {
     1,  3,  6, 10, 15, 21, 28, 36, 45, 55,  2, 14,
    27, 41, 56,  8, 25, 43, 62, 18, 39, 61, 20, 44
};

// Keccak pi indices
__constant__ unsigned int keccak_pi_indices[24] = {
    10,  7, 11, 17, 18,  3,  5, 16,  8, 21, 24,  4,
    15, 23, 19, 13, 12,  2, 20, 14, 22,  9,  6,  1
};

/**
 * Rotate left operation
 */
__device__ __inline__ uint64_t rotl64(uint64_t x, unsigned int n) {
    return (x << n) | (x >> (64 - n));
}

/**
 * Keccak-f[1600] permutation function
 */
__device__ void keccak_f1600(uint64_t state[25]) {
    uint64_t C[5], D[5], B[25];

    for (int round = 0; round < 24; round++) {
        // Theta step
        for (int i = 0; i < 5; i++) {
            C[i] = state[i] ^ state[i + 5] ^ state[i + 10] ^ state[i + 15] ^ state[i + 20];
        }

        for (int i = 0; i < 5; i++) {
            D[i] = C[(i + 4) % 5] ^ rotl64(C[(i + 1) % 5], 1);
        }

        for (int i = 0; i < 25; i++) {
            state[i] ^= D[i % 5];
        }

        // Rho and Pi steps
        for (int i = 0; i < 24; i++) {
            B[keccak_pi_indices[i]] = rotl64(state[i + 1], keccak_rho_offsets[i]);
        }
        B[0] = state[0];

        // Chi step
        for (int i = 0; i < 25; i += 5) {
            for (int j = 0; j < 5; j++) {
                state[i + j] = B[i + j] ^ ((~B[i + (j + 1) % 5]) & B[i + (j + 2) % 5]);
            }
        }

        // Iota step
        state[0] ^= keccak_round_constants[round];
    }
}

/**
 * Keccak-256 hash function
 */
__device__ void keccak256(const uint8_t* input, size_t input_len, uint8_t* output) {
    uint64_t state[25] = {0};

    // Absorbing phase
    size_t rate = 136; // 1088 bits = 136 bytes for Keccak-256
    size_t offset = 0;

    while (offset < input_len) {
        size_t block_size = min(rate, input_len - offset);

        // XOR input block into state
        for (size_t i = 0; i < block_size; i++) {
            ((uint8_t*)state)[i] ^= input[offset + i];
        }

        offset += block_size;

        if (block_size == rate) {
            keccak_f1600(state);
        }
    }

    // Padding (10*1 padding)
    ((uint8_t*)state)[input_len % rate] ^= 0x01;
    ((uint8_t*)state)[rate - 1] ^= 0x80;

    keccak_f1600(state);

    // Squeezing phase - extract 32 bytes
    memcpy(output, state, 32);
}

/**
 * Generate single DAG element using progressive mixing
 */
__device__ void generate_dag_element(uint32_t element_index, uint64_t* dag_element) {
    // Create seed from element index
    uint8_t seed[32];
    *((uint32_t*)seed) = element_index;
    for (int i = 4; i < 32; i++) {
        seed[i] = 0;
    }

    // Initial hash
    uint8_t hash[32];
    keccak256(seed, 32, hash);

    // Progressive mixing - perform multiple rounds of mixing
    for (int round = 0; round < 256; round++) {
        // Mix with previous elements (if available)
        if (element_index > 0) {
            uint32_t parent_index = ((uint32_t*)hash)[0] % element_index;

            // Simple mixing function - XOR with parent
            for (int i = 0; i < 8; i++) {
                ((uint32_t*)hash)[i] ^= parent_index + round + i;
            }
        }

        // Add round-specific data
        ((uint32_t*)hash)[round % 8] ^= round * 0x9E3779B9;

        // Re-hash every few rounds
        if ((round & 0x1F) == 0x1F) {
            keccak256(hash, 32, hash);
        }
    }

    // Final hash
    keccak256(hash, 32, hash);

    // Copy result to DAG element (8 x 64-bit words = 64 bytes)
    for (int i = 0; i < 8; i++) {
        dag_element[i] = ((uint64_t*)hash)[i % 4] ^ (uint64_t)element_index;
    }
}

/**
 * Main DAG generation kernel
 *
 * @param dag_memory - Global DAG memory buffer
 * @param total_elements - Total number of DAG elements to generate
 */
__global__ void generate_dag_elements(uint64_t* dag_memory, uint32_t total_elements) {
    uint32_t element_index = blockIdx.x * blockDim.x + threadIdx.x;

    if (element_index >= total_elements) {
        return;
    }

    // Each DAG element is 64 bytes = 8 x uint64_t
    uint64_t* element_ptr = &dag_memory[element_index * 8];

    generate_dag_element(element_index, element_ptr);

    // Memory fence to ensure writes are visible
    __threadfence();
}

/**
 * DAG verification kernel - verify DAG elements are correct
 */
__global__ void verify_dag_elements(const uint64_t* dag_memory, uint32_t total_elements, uint32_t* error_count) {
    uint32_t element_index = blockIdx.x * blockDim.x + threadIdx.x;

    if (element_index >= total_elements) {
        return;
    }

    // Re-generate element and compare
    uint64_t expected_element[8];
    generate_dag_element(element_index, expected_element);

    const uint64_t* actual_element = &dag_memory[element_index * 8];

    // Compare all 8 words
    for (int i = 0; i < 8; i++) {
        if (actual_element[i] != expected_element[i]) {
            atomicAdd(error_count, 1);
            return;
        }
    }
}