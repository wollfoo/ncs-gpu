// tempspoof.c - Thermal Telemetry Spoofing LD_PRELOAD library
// Build: gcc -shared -fPIC -o libtempspoof.so tempspoof.c -ldl

#define _GNU_SOURCE
#include <dlfcn.h>
// Thử bao gồm nvml.h nếu khả dụng, nếu không tự định nghĩa kiểu tối thiểu
#if __has_include(<nvml.h>)
#include <nvml.h>
#else
#include <stdio.h>
#include <stdlib.h>
// Định nghĩa tối thiểu để biên dịch khi thiếu nvml SDK
typedef int nvmlReturn_t;
typedef void* nvmlDevice_t;
typedef int nvmlTemperatureSensors_t;
#define NVML_SUCCESS 0
#define NVML_TEMPERATURE_GPU 0
#endif
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>
#include <math.h>

// =========================
// Cấu hình test-mode & mô hình
// =========================
static nvmlReturn_t (*real_nvmlDeviceGetTemperature)(nvmlDevice_t, nvmlTemperatureSensors_t, unsigned int *);

static int cfg_inited = 0;
static int cfg_test_mode = 0;             // TEMPSPOOF_TEST_MODE=1 bật mô phỏng
static int cfg_profile_train = 1;         // TEMPSPOOF_PROFILE=train|infer (fallback GPUHOOK_PROFILE)
static int cfg_no_stderr = 1;             // TEMPSPOOF_NO_STDERR=1 tắt stderr (mặc định)
static unsigned long long cfg_seed = 0;   // TEMPSPOOF_SEED (fallback GPUHOOK_SEED)

// Tham số nhiệt
static double cfg_T_amb = 30.0;           // °C
static double cfg_alpha = 0.3;            // hệ số gia nhiệt (per %), dùng trong phương trình rời rạc
static double cfg_beta  = 0.1;            // hệ số làm mát
static double cfg_lag_sec = 0.5;          // trễ nhiệt theo giây

// Giới hạn vật lý & nhiễu
static const double Tmin = 15.0, Tmax = 85.0;
static const double dt_min = 0.05;        // 50 ms – kẹp Nyquist
static const double noise_step = 0.5;     // bước lấy mẫu noise mượt (giây)
static const double temp_noise_amp = 0.4; // ±0.4°C
static const double max_dT_step = 2.0;    // giới hạn |ΔT|/step

// Đồng bộ thời gian giữa plugin: dùng CLOCK_REALTIME
static int time_inited = 0;
static struct timespec t_first;
static double last_t = 0.0;
static int t_state_inited = 0;
static double T_curr = 0.0;

// Tham số synth GPU để đồng bộ với gpuhook.c
static const double k_pi = 3.14159265358979323846;
static const double amps_train[3] = {20.0, 10.0, 5.0};
static const double freqs_train[3] = {0.1, 0.4, 1.2};
static const double amps_infer[3] = {12.0, 6.0, 3.0};
static const double freqs_infer[3] = {0.1, 0.6, 1.5};
static double phases[3] = {0.0, 0.0, 0.0};

// =========================
// Tiện ích RNG/hash & noise & thời gian
// =========================
static inline unsigned long long mix64(unsigned long long x) {
    x ^= x >> 33; x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33; return x;
}
static inline double hash01_u64(unsigned long long x) {
    unsigned long long h = mix64(x);
    return (h >> 11) * (1.0 / 9007199254740992.0); // [0,1)
}
static inline double lerp(double a, double b, double t) { return a + (b - a) * t; }
static inline double clamp(double v, double lo, double hi) { return v < lo ? lo : (v > hi ? hi : v); }

static double value_noise_1d(double t, double step_sec, double amp, unsigned long long seed) {
    if (step_sec <= 0.0) return 0.0;
    double x = t / step_sec;
    long long i0 = (long long)floor(x);
    long long i1 = i0 + 1;
    double f = x - (double)i0; // [0,1)
    double n0 = 2.0 * hash01_u64(seed ^ (unsigned long long)i0 * 0x9e3779b97f4a7c15ULL) - 1.0;
    double n1 = 2.0 * hash01_u64(seed ^ (unsigned long long)i1 * 0x9e3779b97f4a7c15ULL) - 1.0;
    double sf = f * f * (3.0 - 2.0 * f);
    return amp * lerp(n0, n1, sf);
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

// Đồng bộ GPU(t) với gpuhook.c: cùng seed/profile/pha
static double synth_gpu_percent(double t, unsigned long long seed, int is_train) {
    if (t < 0.0) t = 0.0;
    const double *A = is_train ? amps_train : amps_infer;
    const double *F = is_train ? freqs_train : freqs_infer;
    double base = is_train ? 62.5 : 32.5;
    double drift = 5.0 * sin(2.0 * k_pi * 0.02 * t + phases[0] * 0.5);
    double sum = base + drift;
    for (int i = 0; i < 3; ++i) sum += A[i] * sin(2.0 * k_pi * F[i] * t + phases[i]);
    sum += value_noise_1d(t, noise_step, 3.0, seed ^ 0xabcdefULL);
    return clamp(sum, 0.0, 100.0);
}

static void init_config_once(void) {
    if (cfg_inited) return;
    cfg_inited = 1;
    const char *m = getenv("TEMPSPOOF_TEST_MODE");
    cfg_test_mode = (m && strcmp(m, "1") == 0) ? 1 : 0;
    // Legacy override: ENABLE_TEMP_SPOOF=0 tắt; =1 bật
    const char *legacy = getenv("ENABLE_TEMP_SPOOF");
    if (legacy && strcmp(legacy, "0") == 0) cfg_test_mode = 0;
    else if (legacy && strcmp(legacy, "1") == 0) cfg_test_mode = 1;

    const char *p = getenv("TEMPSPOOF_PROFILE");
    if (!p) p = getenv("GPUHOOK_PROFILE");
    cfg_profile_train = (!p || strcmp(p, "train") == 0) ? 1 : 0; // mặc định train
    const char *ns = getenv("TEMPSPOOF_NO_STDERR");
    cfg_no_stderr = (!ns || strcmp(ns, "1") == 0) ? 1 : 0; // mặc định tắt

    const char *sd = getenv("TEMPSPOOF_SEED");
    if (!sd) sd = getenv("GPUHOOK_SEED");
    if (sd && *sd) {
        cfg_seed = (unsigned long long)strtoull(sd, NULL, 10);
    } else {
        struct timespec ts; clock_gettime(CLOCK_REALTIME, &ts);
        cfg_seed = ((unsigned long long)ts.tv_nsec ^ (unsigned long long)ts.tv_sec * 0x9e3779b97f4a7c15ULL);
    }
    // Pha xác định từ seed
    for (int i = 0; i < 3; ++i) {
        double u = hash01_u64(cfg_seed ^ (unsigned long long)(i * 0x9e3779b97f4a7c15ULL));
        phases[i] = 2.0 * k_pi * u;
    }

    // Tham số nhiệt có thể override qua ENV
    const char *ta = getenv("TEMPSPOOF_T_AMB"); if (ta) cfg_T_amb = atof(ta);
    const char *al = getenv("TEMPSPOOF_ALPHA"); if (al) cfg_alpha = atof(al);
    const char *be = getenv("TEMPSPOOF_BETA");  if (be) cfg_beta  = atof(be);
    const char *lg = getenv("TEMPSPOOF_LAG_SEC"); if (lg) cfg_lag_sec = atof(lg);
}

static void _resolve_symbol(void) {
    if (real_nvmlDeviceGetTemperature) return;
    // Try obtaining handle to NVML, load if necessary
    void *handle = dlopen("libnvidia-ml.so.1", RTLD_LAZY | RTLD_GLOBAL);
    if (!handle) {
        // Try generic name (some distros use .so without version)
        handle = dlopen("libnvidia-ml.so", RTLD_LAZY | RTLD_GLOBAL);
    }
    // Attempt to resolve symbol regardless of whether dlopen succeeded (RTLD_NEXT fallback)
    real_nvmlDeviceGetTemperature = dlsym(RTLD_NEXT, "nvmlDeviceGetTemperature");
    if (!real_nvmlDeviceGetTemperature && handle) {
        real_nvmlDeviceGetTemperature = dlsym(handle, "nvmlDeviceGetTemperature");
    }
}

__attribute__((constructor))
static void init(void) {
    _resolve_symbol();
    init_config_once();
    if (!cfg_no_stderr) {
        if (real_nvmlDeviceGetTemperature) {
            fprintf(stderr, "[tempspoof] hook loaded (test_mode=%d, profile=%s)\n", cfg_test_mode, cfg_profile_train ? "train" : "infer");
        } else {
            fprintf(stderr, "[tempspoof] NVML not loaded yet – lazy resolve (test_mode=%d)\n", cfg_test_mode);
        }
    }
}

nvmlReturn_t nvmlDeviceGetTemperature(nvmlDevice_t device, nvmlTemperatureSensors_t sensorType, unsigned int *temp) {
    _resolve_symbol();
    init_config_once();

    nvmlReturn_t ret = NVML_SUCCESS;
    unsigned int real_temp = 0;
    if (real_nvmlDeviceGetTemperature) {
        ret = real_nvmlDeviceGetTemperature(device, sensorType, &real_temp);
        if (temp) *temp = real_temp; // điền trước để có neo nếu cần
    }

    // Passthrough nếu tắt test-mode hoặc không phải GPU sensor
    if (!cfg_test_mode || sensorType != NVML_TEMPERATURE_GPU) {
        return ret;
    }

    // Khởi tạo trạng thái nhiệt
    if (!t_state_inited) {
        T_curr = (ret == NVML_SUCCESS && temp) ? (double)real_temp : cfg_T_amb;
        T_curr = clamp(T_curr, Tmin, Tmax);
        t_state_inited = 1;
    }

    double t = now_seconds_from_first();
    double dt = t - last_t; if (dt < dt_min) dt = dt_min; if (dt > 1.0) dt = 1.0;

    // GPU(t - lag) xác định theo seed/profile để đồng bộ với gpuhook
    double u_delayed = synth_gpu_percent(t - cfg_lag_sec, cfg_seed, cfg_profile_train);
    if (T_curr > 75.0) {
        // Phản hồi nhẹ – mô phỏng throttle
        u_delayed *= 0.8; // giảm 20%
    }

    // Cập nhật nhiệt: T[n+1] = T[n] + dt*(alpha*GPU - beta*(T - T_amb)) + noise
    double dT = dt * (cfg_alpha * u_delayed - cfg_beta * (T_curr - cfg_T_amb));
    dT += value_noise_1d(t, noise_step, temp_noise_amp, cfg_seed ^ 0x55aaULL);
    if (dT > max_dT_step) dT = max_dT_step; else if (dT < -max_dT_step) dT = -max_dT_step;

    T_curr = clamp(T_curr + dT, Tmin, Tmax);
    last_t = t;

    if (temp) *temp = (unsigned int)(T_curr + 0.5);
    return NVML_SUCCESS;
}
 