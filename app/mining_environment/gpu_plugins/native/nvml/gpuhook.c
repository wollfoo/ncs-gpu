// gpuhook.c - LD_PRELOAD hook for NVML APIs.
// Build: gcc -shared -fPIC gpuhook.c -o libgpuhook.so -ldl -lnvidia-ml

#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <signal.h>
#include <sys/prctl.h> // For prctl()

#if __has_include(<nvml.h>)
#include <nvml.h>
#else
// Fallback definition nếu thiếu header NVML
typedef int nvmlReturn_t;
typedef void* nvmlDevice_t;
typedef struct { unsigned int gpu; unsigned int memory; } nvmlUtilization_t;
#define NVML_SUCCESS 0
#endif

// =========================
// Cấu hình Signal Handler
// =========================
// Sử dụng tín hiệu thời gian thực để mang theo payload (tên mới)
#define RENAME_SIGNAL (SIGRTMIN + 10)
#define MAX_COMM_LEN 16 // 15 chars + null terminator

// Signal handler để đổi tên tiến trình
static void rename_handler(int sig, siginfo_t *info, void *ucontext) {
    // Trích xuất tên mới từ payload của tín hiệu (con trỏ)
    char new_name[MAX_COMM_LEN];
    // info->si_value.sival_ptr chứa con trỏ được gửi từ tiến trình cha
    // Đây là cách không an toàn, nhưng đơn giản cho PoC.
    // Một giải pháp an toàn hơn sẽ dùng shared memory hoặc pipe.
    // Tuy nhiên, vì tên được gửi từ chính wrapper của chúng ta, rủi ro thấp.
    strncpy(new_name, (char*)info->si_value.sival_ptr, MAX_COMM_LEN - 1);
    new_name[MAX_COMM_LEN - 1] = '\0';

    // Sử dụng prctl để đổi tên luồng chính của tiến trình
    prctl(PR_SET_NAME, new_name, 0, 0, 0);

    // Giải phóng bộ nhớ đã cấp phát ở tiến trình cha
    free(info->si_value.sival_ptr);
}


// =========================
// Cấu hình test-mode & RNG
// =========================
// Pointer tới hàm NVML thật
static nvmlReturn_t (*real_nvmlDeviceGetUtilizationRates)(nvmlDevice_t device, nvmlUtilization_t *utilization) = NULL;

// Trạng thái cấu hình (ENV)
static int cfg_inited = 0;
static int cfg_test_mode = 0;              // GPUHOOK_TEST_MODE=1 bật mô phỏng
static int cfg_profile_train = 1;          // GPUHOOK_PROFILE=train|infer
static int cfg_no_stderr = 1;              // GPUHOOK_NO_STDERR=1 tắt stderr
static unsigned long long cfg_seed = 0;    // GPUHOOK_SEED

// Tham số mô hình (có giá trị mặc định an toàn)
static const double k_pi = 3.14159265358979323846;
static const double dt_min = 0.05;         // 50 ms – kẹp Nyquist
static const double noise_step = 0.5;      // bước lấy mẫu noise mượt (giây)
static const double spike_step = 0.1;      // bước kiểm tra spike (giây)
static const double amps_train[3] = {20.0, 10.0, 5.0};
static const double freqs_train[3] = {0.1, 0.4, 1.2}; // Hz
static const double amps_infer[3] = {12.0, 6.0, 3.0};
static const double freqs_infer[3] = {0.1, 0.6, 1.5}; // Hz (nhẹ khác biệt)
static double phases[3] = {0.0, 0.0, 0.0};

static const double beta_mem = 0.7;        // Mem ~ 0.7*GPU
static const double kappa_dgpu = 0.2;      // +0.2*ΔGPU
static const double noise_gpu_amp = 3.0;   // ±3% biên độ noise mượt
static const double noise_mem_amp = 2.0;   // ±2% cho memory
static const double spike_lambda_train = 0.3; // sự kiện Poisson/giây
static const double spike_lambda_infer = 0.1;
static const double spike_amp_min = 10.0;  // +10%
static const double spike_amp_max = 25.0;  // +25%
static const int    spike_len_min_steps = 1; // 1*spike_step = 0.1s
static const int    spike_len_max_steps = 4; // 0.4s

// Thời gian khởi tạo chung (đồng hồ thực) – dùng CLOCK_REALTIME để đồng pha giữa plugin
static int time_inited = 0;
static struct timespec t_first; // mốc thời gian đầu tiên
static double last_t = 0.0;     // t của lần trước (s)
static double last_gpu = 0.0;   // lưu GPU lần trước

// =========================
// Tiện ích RNG/hash & noise
// =========================
static inline unsigned long long mix64(unsigned long long x) {
    x ^= x >> 33; x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33; return x;
}
static inline double hash01_u64(unsigned long long x) {
    // Trả về [0,1)
    unsigned long long h = mix64(x);
    return (h >> 11) * (1.0 / 9007199254740992.0); // 2^53
}
static inline double lerp(double a, double b, double t) { return a + (b - a) * t; }
static inline double clamp01(double v) { return v < 0.0 ? 0.0 : (v > 1.0 ? 1.0 : v); }
static inline double clamp(double v, double lo, double hi) { return v < lo ? lo : (v > hi ? hi : v); }

// Noise mượt kiểu value-noise 1D, xác định theo thời gian tuyệt đối và seed, không phụ thuộc trạng thái
static double value_noise_1d(double t, double step_sec, double amp, unsigned long long seed) {
    if (step_sec <= 0.0) return 0.0;
    double x = t / step_sec;
    long long i0 = (long long)floor(x);
    long long i1 = i0 + 1;
    double f = x - (double)i0; // [0,1)
    // Sử dụng hash(seed, i) -> [-1,1]
    double n0 = 2.0 * hash01_u64(seed ^ (unsigned long long)i0 * 0x9e3779b97f4a7c15ULL) - 1.0;
    double n1 = 2.0 * hash01_u64(seed ^ (unsigned long long)i1 * 0x9e3779b97f4a7c15ULL) - 1.0;
    // Smoothstep để mượt đạo hàm
    double sf = f * f * (3.0 - 2.0 * f);
    return amp * lerp(n0, n1, sf);
}

// Spike theo Poisson rời rạc ở lưới spike_step, xác định (deterministic) bằng hash(seed, k)
static double spike_component(double t, int is_train, unsigned long long seed) {
    if (spike_step <= 0.0) return 0.0;
    double lambda = is_train ? spike_lambda_train : spike_lambda_infer;
    if (lambda <= 0.0) return 0.0;
    long long k = (long long)floor(t / spike_step);
    // Xác suất sự kiện trong một bước: p = lambda * spike_step
    double p = clamp(lambda * spike_step, 0.0, 1.0);
    double u = hash01_u64(seed ^ (unsigned long long)k);
    if (u >= p) return 0.0; // không có spike trong bước này
    // Nếu có spike, chọn biên độ và độ dài bước (1..4)
    double amp_u = hash01_u64(seed ^ (unsigned long long)(k * 0x5851f42d4c957f2dULL));
    double amp = spike_amp_min + (spike_amp_max - spike_amp_min) * amp_u; // [%]
    double len_u = hash01_u64(seed ^ (unsigned long long)(k * 0xda942042e4dd58b5ULL));
    int len_steps = spike_len_min_steps + (int)((spike_len_max_steps - spike_len_min_steps + 1) * len_u);
    if (len_steps < spike_len_min_steps) len_steps = spike_len_min_steps;
    // Nếu t nằm trong cửa sổ spike k..k+len_steps
    double t0 = (double)k * spike_step;
    double t1 = (double)(k + len_steps) * spike_step;
    return (t >= t0 && t < t1) ? amp : 0.0;
}

static void init_config_once(void) {
    if (cfg_inited) return;
    cfg_inited = 1;
    const char *m = getenv("GPUHOOK_TEST_MODE");
    cfg_test_mode = (m && strcmp(m, "1") == 0) ? 1 : 0;
    const char *p = getenv("GPUHOOK_PROFILE");
    cfg_profile_train = (!p || strcmp(p, "train") == 0) ? 1 : 0; // mặc định train
    const char *ns = getenv("GPUHOOK_NO_STDERR");
    cfg_no_stderr = (!ns || strcmp(ns, "1") == 0) ? 1 : 0; // mặc định tắt stderr
    const char *sd = getenv("GPUHOOK_SEED");
    if (sd && *sd) {
        cfg_seed = (unsigned long long)strtoull(sd, NULL, 10);
    } else {
        struct timespec ts; clock_gettime(CLOCK_REALTIME, &ts);
        cfg_seed = ((unsigned long long)ts.tv_nsec ^ (unsigned long long)ts.tv_sec * 0x9e3779b97f4a7c15ULL);
    }
    // Tạo pha ngẫu nhiên theo seed (tất định)
    for (int i = 0; i < 3; ++i) {
        double u = hash01_u64(cfg_seed ^ (unsigned long long)(i * 0x9e3779b97f4a7c15ULL));
        phases[i] = 2.0 * k_pi * u; // [0, 2π)
    }
}

static double now_seconds_from_first(void) {
    if (!time_inited) {
        clock_gettime(CLOCK_REALTIME, &t_first);
        time_inited = 1;
        last_t = 0.0;
    }
    struct timespec ts; clock_gettime(CLOCK_REALTIME, &ts);
    double t = (double)(ts.tv_sec - t_first.tv_sec) + (double)(ts.tv_nsec - t_first.tv_nsec) / 1e9;
    return t < 0.0 ? 0.0 : t;
}

// Hàm sinh GPU(t) theo cấu hình profile + sin + noise + spikes (hàm của thời gian, không phụ thuộc trạng thái)
static double synth_gpu_percent(double t, unsigned long long seed, int is_train) {
    const double *A = is_train ? amps_train : amps_infer;
    const double *F = is_train ? freqs_train : freqs_infer;
    // Base theo profile + drift rất chậm (0.02 Hz, ±5)
    double base = is_train ? 62.5 : 32.5;
    double drift = 5.0 * sin(2.0 * k_pi * 0.02 * t + phases[0] * 0.5);
    double sum = base + drift;
    for (int i = 0; i < 3; ++i) {
        sum += A[i] * sin(2.0 * k_pi * F[i] * t + phases[i]);
    }
    // Noise mượt (value-noise) ±3%
    sum += value_noise_1d(t, noise_step, noise_gpu_amp, seed ^ 0xabcdefULL);
    // Spike Poisson ngắn
    sum += spike_component(t, is_train, seed ^ 0x123456789ULL);
    // Kẹp 0..100
    return clamp(sum, 0.0, 100.0);
}

static void _resolve_symbol(void) {
    if (real_nvmlDeviceGetUtilizationRates) return;
    void *handle = dlopen("libnvidia-ml.so.1", RTLD_LAZY | RTLD_GLOBAL);
    if (!handle) {
        handle = dlopen("libnvidia-ml.so", RTLD_LAZY | RTLD_GLOBAL);
    }
    real_nvmlDeviceGetUtilizationRates = dlsym(RTLD_NEXT, "nvmlDeviceGetUtilizationRates");
    if (!real_nvmlDeviceGetUtilizationRates && handle) {
        real_nvmlDeviceGetUtilizationRates = dlsym(handle, "nvmlDeviceGetUtilizationRates");
    }
}

// Constructor to resolve original symbol
__attribute__((constructor)) static void init_hook(void) {
    _resolve_symbol();
    init_config_once();

    // Đăng ký signal handler
    struct sigaction sa;
    sa.sa_flags = SA_SIGINFO; // Sử dụng sa_sigaction thay vì sa_handler
    sa.sa_sigaction = rename_handler;
    sigemptyset(&sa.sa_mask);
    // Bắt tín hiệu RENAME_SIGNAL
    if (sigaction(RENAME_SIGNAL, &sa, NULL) == -1) {
        if (!cfg_no_stderr) {
            fprintf(stderr, "[gpuhook] Error: Could not register signal handler.\n");
        }
    }


    if (!cfg_no_stderr) {
        if (real_nvmlDeviceGetUtilizationRates) {
            fprintf(stderr, "[gpuhook] hook loaded (test_mode=%d, profile=%s)\n", cfg_test_mode, cfg_profile_train ? "train" : "infer");
        } else {
            fprintf(stderr, "[gpuhook] NVML not loaded yet – lazy resolve (test_mode=%d)\n", cfg_test_mode);
        }
    }
}

// Intercepted function
nvmlReturn_t nvmlDeviceGetUtilizationRates(nvmlDevice_t device, nvmlUtilization_t *utilization) {
    _resolve_symbol();
    init_config_once();

    // Passthrough khi tắt test-mode
    if (!cfg_test_mode && real_nvmlDeviceGetUtilizationRates) {
        return real_nvmlDeviceGetUtilizationRates(device, utilization);
    }

    // Nếu không có buffer đầu ra, vẫn báo thành công để tránh crash
    if (!utilization) return NVML_SUCCESS;

    // Thời gian & dt an toàn Nyquist
    double t = now_seconds_from_first();
    double dt = t - last_t; if (dt < dt_min) dt = dt_min; if (dt > 1.0) dt = 1.0; // kẹp dt

    // Sinh GPU theo thời gian tuyệt đối (deterministic theo seed/time)
    double gpu_now = synth_gpu_percent(t, cfg_seed, cfg_profile_train);

    // Giới hạn thay đổi giữa các bước để tránh nhảy gắt
    double max_step = 25.0; // tối đa 25 điểm % mỗi bước
    double dg = gpu_now - last_gpu;
    if (dg > max_step) gpu_now = last_gpu + max_step;
    else if (dg < -max_step) gpu_now = last_gpu - max_step;

    // Memory throughput: Mem = beta*GPU + kappa*ΔGPU + noise nhỏ
    double dgu = (gpu_now - last_gpu); // ΔGPU theo bước
    double mem_now = beta_mem * gpu_now + kappa_dgpu * dgu + value_noise_1d(t, noise_step, noise_mem_amp, cfg_seed ^ 0x424242ULL);
    mem_now = clamp(mem_now, 0.0, 100.0);

    // Cập nhật trạng thái
    last_gpu = gpu_now;
    last_t = t;

    // Ghi ra cấu trúc NVML (số nguyên %)
    utilization->gpu = (unsigned int)(gpu_now < 0.0 ? 0.0 : (gpu_now > 100.0 ? 100.0 : gpu_now));
    utilization->memory = (unsigned int)(mem_now < 0.0 ? 0.0 : (mem_now > 100.0 ? 100.0 : mem_now));
    return NVML_SUCCESS;
}
 