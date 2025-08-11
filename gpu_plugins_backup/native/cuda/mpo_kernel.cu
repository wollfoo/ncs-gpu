// mpo_kernel.cu
// CUDA Memory-Pattern Obfuscation library dành cho GPU Cloaking Manager.
// Biên dịch:  nvcc -Xcompiler -fPIC -shared mpo_kernel.cu -o libmpo.so

#include <cuda.h>
#include <cuda_runtime.h>
#include <thread>
#include <atomic>
#include <chrono>
#include <mutex>
#include <cstdint>
#include <cstdlib>

// ---- CUDA kernel tạo nhiễu truy cập VRAM/L2 ---------------------------------
__device__ __forceinline__ unsigned int xorshift32(unsigned int *state) {
    unsigned int x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

__global__ void mpo_noise_kernel(float *scratch,
                                 size_t elements,
                                 unsigned long long seed,
                                 int *index_tbl,
                                 unsigned int active_mask,
                                 int chase_steps,
                                 int stride) {
    size_t tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= elements) return;
    unsigned int state = static_cast<unsigned int>(seed ^ tid);
    unsigned int idx = xorshift32(&state) & active_mask;
    // Pointer-chasing/mixed access: tăng độ xáo trộn footprint
    for (int s = 0; s < chase_steps; ++s) {
        if (index_tbl) {
            idx = static_cast<unsigned int>(index_tbl[idx]) & active_mask;
        } else {
            idx = (idx + stride) & active_mask; // fallback stride nhỏ
        }
    }
    // Dummy read-modify-write
    float val = scratch[idx];
    scratch[idx] = val + 1.0f;
}

// Khởi tạo bảng chỉ mục cho pointer-chasing
__global__ void init_index_kernel(int *index_tbl,
                                  size_t elements,
                                  unsigned long long seed,
                                  unsigned int mask) {
    size_t i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= elements) return;
    unsigned int st = static_cast<unsigned int>(seed ^ i);
    unsigned int v  = xorshift32(&st);
    index_tbl[i] = static_cast<int>(v & mask);
}

// ---- Worker thread chạy lặp vô hạn ------------------------------------------
static std::atomic<bool> g_stop{false};

// Host-side lightweight RNG (xorshift64) và tiện ích
static inline uint64_t hxorshift64(uint64_t& x) {
    x ^= x << 13; x ^= x >> 7; x ^= x << 17; return x;
}
static inline int hrand_range(uint64_t& s, int lo, int hi) {
    return lo + (int)(hxorshift64(s) % (uint64_t)(hi - lo + 1));
}

struct MPOParams {
    unsigned int active_mask;
    size_t       active_elements;
    int          block_threads;
    int          chase_steps;
    int          stride;
    int          micro_bursts;
    int          jitter_us_min;
    int          jitter_us_max;
};

static void choose_params(MPOParams& p, uint64_t& seed_state, bool profile_train) {
    // Kích thước hoạt động: 64K/128K/256K
    int sel = hrand_range(seed_state, 0, 2);
    size_t elems = (sel == 0 ? (1u<<16) : (sel == 1 ? (1u<<17) : (1u<<18)));
    p.active_elements = elems;
    p.active_mask = (unsigned int)(elems - 1);
    // Block threads: 128/256/512 (bội của 32 để phù hợp warp)
    int bs_sel = hrand_range(seed_state, 0, 2);
    p.block_threads = (bs_sel == 0 ? 128 : (bs_sel == 1 ? 256 : 512));
    // Pointer-chasing steps: train 1-3, infer 0-2
    p.chase_steps = profile_train ? hrand_range(seed_state, 1, 3) : hrand_range(seed_state, 0, 2);
    // Stride fallback: 1/2/4/8
    int stride_pow = hrand_range(seed_state, 0, 3);
    p.stride = 1 << stride_pow;
    // Micro-bursts: train 2-4, infer 1-2
    p.micro_bursts = profile_train ? hrand_range(seed_state, 2, 4) : hrand_range(seed_state, 1, 2);
    // Jitter microseconds
    p.jitter_us_min = 50;
    p.jitter_us_max = 500;
}

static void read_env(bool& profile_train, uint64_t& seed_state) {
    const char* p = getenv("GPUHOOK_PROFILE");
    if (p && (p[0]=='i' || p[0]=='I')) profile_train = false; // infer
    const char* s = getenv("GPUHOOK_SEED");
    if (s) {
        unsigned long long v = strtoull(s, nullptr, 10);
        if (v != 0) seed_state = (uint64_t)v;
    }
    if (seed_state == 0) {
        seed_state = (uint64_t)std::chrono::high_resolution_clock::now().time_since_epoch().count();
    }
}

static void mpo_worker() {
    // Dung lượng tối đa cho các profile 64K/128K/256K
    const size_t kMaxElements = 1u << 18; // 256K
    float *d_scratch = nullptr;
    int   *d_index   = nullptr;
    cudaMalloc(&d_scratch, kMaxElements * sizeof(float));
    cudaMemset(d_scratch, 0, kMaxElements * sizeof(float));
    cudaMalloc(&d_index,   kMaxElements * sizeof(int));

    // Dùng stream để tránh sync đều đặn CPU-GPU
    cudaStream_t stream; cudaStreamCreate(&stream);

    bool     profile_train = true;
    uint64_t seed_state    = 0;
    read_env(profile_train, seed_state);

    while (!g_stop.load()) {
        MPOParams p{};
        choose_params(p, seed_state, profile_train);

        // Khởi tạo bảng index theo active_mask hiện tại
        dim3 iblock(256);
        dim3 igrid((p.active_elements + iblock.x - 1) / iblock.x);
        init_index_kernel<<<igrid, iblock, 0, stream>>>(d_index, p.active_elements,
                                                        (unsigned long long)seed_state, p.active_mask);

        // Thiết lập launch dims
        dim3 block(p.block_threads);
        dim3 grid((p.active_elements + block.x - 1) / block.x);

        // Micro-bursts: nhiều kernel ngắn xen kẽ nghỉ ngẫu nhiên
        int bursts = p.micro_bursts;
        for (int b = 0; b < bursts; ++b) {
            unsigned long long kseed = (unsigned long long)hxorshift64(seed_state);
            mpo_noise_kernel<<<grid, block, 0, stream>>>(d_scratch, p.active_elements, kseed,
                                                         d_index, p.active_mask,
                                                         p.chase_steps, p.stride);
        }

        // Jitter 50-500 µs (thực sự ngẫu nhiên)
        int us = hrand_range(seed_state, p.jitter_us_min, p.jitter_us_max);
        std::this_thread::sleep_for(std::chrono::microseconds(us));

        // Tránh tích lũy hàng đợi quá sâu
        if (cudaStreamQuery(stream) != cudaSuccess) {
            std::this_thread::sleep_for(std::chrono::microseconds(50));
        }
    }

    cudaStreamSynchronize(stream);
    cudaStreamDestroy(stream);
    cudaFree(d_index);
    cudaFree(d_scratch);
}

// ---- API xuất ra cho GPUCloakingManager --------------------------------------
extern "C" void launch_mpo_kernel() {
    // Đảm bảo luồng MPO chỉ được khởi chạy và detach đúng một lần.
    static std::once_flag flag;
    std::call_once(flag, [] {
        std::thread([] { mpo_worker(); }).detach();
    });
}

extern "C" void stop_mpo_kernel() {
    g_stop.store(true);
}