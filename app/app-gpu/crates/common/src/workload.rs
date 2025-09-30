use serde::{Deserialize, Serialize};

/// **[Workload Type]** (Loại khối lượng công việc – các loại tải GPU hỗ trợ)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WorkloadType {
    /// **[AI Training]** (Huấn luyện AI – GEMM, loss, backprop simulation)
    AiTraining,
    
    /// **[Image Processing]** (Xử lý ảnh – convolution, resize, batching)
    ImageProcessing,
    
    /// **[Scientific Computing]** (Tính toán khoa học – FFT, BLAS operations)
    ScientificComputing,
    
    /// **[AI Inference]** (Suy luận AI – forward pass, activation)
    AiInference,
}

/// **[Workload Config]** (Cấu hình workload – parameters cho task execution)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkloadConfig {
    /// **[Workload Type]** (Loại workload)
    pub workload_type: WorkloadType,
    
    /// **[Duration]** (Thời gian – execution time in seconds)
    pub duration_secs: u64,
    
    /// **[Batch Size]** (Kích thước batch – number of items per batch)
    pub batch_size: u32,
    
    /// **[GPU Utilization Target]** (Mục tiêu sử dụng GPU – target utilization %)
    pub gpu_utilization_target: f32,
    
    /// **[Memory Size]** (Kích thước bộ nhớ – GPU memory allocation in MB)
    pub memory_size_mb: u32,
}

impl Default for WorkloadConfig {
    fn default() -> Self {
        Self {
            workload_type: WorkloadType::AiTraining,
            duration_secs: 60,
            batch_size: 32,
            gpu_utilization_target: 80.0,
            memory_size_mb: 1024,
        }
    }
}

/// **[Workload Result]** (Kết quả workload – metrics sau khi execute)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkloadResult {
    /// **[Throughput]** (Thông lượng – operations per second)
    pub throughput: f64,
    
    /// **[Average Latency]** (Độ trễ trung bình – milliseconds)
    pub avg_latency_ms: f64,
    
    /// **[P95 Latency]** (Độ trễ P95 – 95th percentile latency)
    pub p95_latency_ms: f64,
    
    /// **[P99 Latency]** (Độ trễ P99 – 99th percentile latency)
    pub p99_latency_ms: f64,
    
    /// **[GPU Utilization]** (Sử dụng GPU – average % during execution)
    pub gpu_utilization: f32,
    
    /// **[Memory Used]** (Bộ nhớ đã dùng – peak memory usage in MB)
    pub memory_used_mb: u32,
    
    /// **[Total Operations]** (Tổng số phép toán – completed operations)
    pub total_operations: u64,
}

impl WorkloadResult {
    /// **[New Empty]** (Tạo mới rỗng – khởi tạo với giá trị mặc định)
    pub fn empty() -> Self {
        Self {
            throughput: 0.0,
            avg_latency_ms: 0.0,
            p95_latency_ms: 0.0,
            p99_latency_ms: 0.0,
            gpu_utilization: 0.0,
            memory_used_mb: 0,
            total_operations: 0,
        }
    }
}
