//! GPU Executor Plugin for OPUS-GPU
//! 
//! High-performance CUDA-based GPU compute engine

pub mod cuda;
pub mod memory;
pub mod task;
pub mod nvml;
pub mod profiling;
pub mod benchmarks;

use std::sync::Arc;
use std::collections::HashMap;
use async_trait::async_trait;
use anyhow::{Result, Context};
use parking_lot::RwLock;
use tracing::{info, debug, warn, error, instrument};

use opus_gpu_core::{
    Plugin, PluginTask, PluginOutput, PluginMetadata,
    plugin::{TaskStatus, HealthStatus},
};

use crate::cuda::CudaContext;
use crate::memory::MemoryManager;
use crate::task::TaskQueue;
use crate::nvml::NvmlMonitor;
use crate::profiling::{GpuProfiler, ProfileLevel, ErrorRecoveryManager};

/// GPU Executor Plugin
pub struct GpuExecutor {
    /// Plugin configuration
    config: GpuExecutorConfig,
    
    /// CUDA context manager
    cuda_context: Arc<RwLock<Option<CudaContext>>>,
    
    /// Memory manager
    memory_manager: Arc<MemoryManager>,
    
    /// Task queue
    task_queue: Arc<TaskQueue>,
    
    /// NVML monitor
    nvml_monitor: Arc<NvmlMonitor>,
    
    /// Performance metrics
    metrics: Arc<RwLock<GpuMetrics>>,
    
    /// Performance profiler
    profiler: Arc<GpuProfiler>,
    
    /// Error recovery manager
    error_recovery: Arc<ErrorRecoveryManager>,
}

/// GPU Executor configuration
#[derive(Debug, Clone, serde::Deserialize, serde::Serialize)]
pub struct GpuExecutorConfig {
    /// GPU device index
    pub device_id: u32,
    
    /// Memory allocation percentage (0.0-1.0)
    pub memory_fraction: f32,
    
    /// Maximum concurrent kernels
    pub max_concurrent_kernels: usize,
    
    /// Enable profiling
    pub enable_profiling: bool,
    
    /// Temperature limit (Celsius)
    pub temperature_limit: u32,
    
    /// Power limit (Watts)
    pub power_limit: Option<u32>,
}

impl Default for GpuExecutorConfig {
    fn default() -> Self {
        Self {
            device_id: 0,
            memory_fraction: 0.9,
            max_concurrent_kernels: 16,
            enable_profiling: false,
            temperature_limit: 80,
            power_limit: None,
        }
    }
}

/// GPU performance metrics
#[derive(Debug, Default, Clone)]
pub struct GpuMetrics {
    pub tasks_completed: u64,
    pub tasks_failed: u64,
    pub total_compute_time_ms: f64,
    pub gpu_utilization_percent: f32,
    pub memory_used_mb: f32,
    pub temperature_celsius: f32,
    pub power_watts: f32,
    pub pcie_throughput_mbps: f32,
}

impl Default for GpuExecutor {
    fn default() -> Self {
        Self {
            config: GpuExecutorConfig::default(),
            cuda_context: Arc::new(RwLock::new(None)),
            memory_manager: Arc::new(MemoryManager::new()),
            task_queue: Arc::new(TaskQueue::new(1000)),
            nvml_monitor: Arc::new(NvmlMonitor::new()),
            metrics: Arc::new(RwLock::new(GpuMetrics::default())),
            profiler: Arc::new(GpuProfiler::new(ProfileLevel::Detailed)),
            error_recovery: Arc::new(ErrorRecoveryManager::new()),
        }
    }
}

#[async_trait]
impl Plugin for GpuExecutor {
    fn metadata(&self) -> PluginMetadata {
        PluginMetadata {
            name: "gpu-executor".to_string(),
            version: "2.0.0".to_string(),
            author: "OPUS-GPU Team".to_string(),
            description: "High-performance CUDA GPU compute engine".to_string(),
            capabilities: vec![
                "compute".to_string(),
                "cuda".to_string(),
                "monitoring".to_string(),
            ],
        }
    }
    
    #[instrument(skip(self))]
    async fn initialize(&mut self) -> Result<()> {
        info!("Initializing GPU Executor plugin");
        
        // Initialize NVML for monitoring
        self.nvml_monitor.init()?;
        
        // Initialize CUDA context
        let cuda_ctx = CudaContext::new(self.config.device_id)?;
        
        // Get device properties
        let device_info = cuda_ctx.get_device_info()?;
        info!("GPU Device: {}", device_info.name);
        info!("Compute Capability: {}.{}", device_info.major, device_info.minor);
        info!("Memory: {} MB", device_info.total_memory_mb);
        info!("Multiprocessors: {}", device_info.multiprocessor_count);
        
        // Initialize memory manager
        let total_memory = (device_info.total_memory_mb as f32 * self.config.memory_fraction) as usize;
        self.memory_manager.initialize(total_memory)?;
        
        // Store CUDA context
        *self.cuda_context.write() = Some(cuda_ctx);
        
        info!("✅ GPU Executor initialized successfully");
        Ok(())
    }
    
    #[instrument(skip(self, task))]
    async fn execute(&self, task: PluginTask) -> Result<PluginOutput> {
        debug!("Executing GPU task: {:?}", task.id);
        
        // Check temperature before executing
        if let Ok(temp) = self.nvml_monitor.get_temperature(self.config.device_id) {
            if temp > self.config.temperature_limit {
                warn!("GPU temperature {} exceeds limit {}, throttling", 
                      temp, self.config.temperature_limit);
                tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
            }
        }
        
        // Add task to queue
        self.task_queue.enqueue(task.clone()).await?;
        
        // Process task
        let start = std::time::Instant::now();
        
        let result = {
            let cuda_guard = self.cuda_context.read();
            let cuda = cuda_guard.as_ref()
                .ok_or_else(|| anyhow::anyhow!("CUDA context not initialized"))?;
            
            // Execute on GPU
            match task.type_.as_str() {
                "compute" => self.execute_compute(cuda, &task).await?,
                "benchmark" => self.execute_benchmark(cuda, &task).await?,
                _ => {
                    return Ok(PluginOutput {
                        task_id: task.id,
                        status: TaskStatus::Failed("Unknown task type".to_string()),
                        result: vec![],
                        metrics: HashMap::new(),
                    });
                }
            }
        };
        
        let elapsed = start.elapsed();
        
        // Update metrics
        {
            let mut metrics = self.metrics.write();
            metrics.tasks_completed += 1;
            metrics.total_compute_time_ms += elapsed.as_millis() as f64;
            
            // Update GPU metrics
            if let Ok(util) = self.nvml_monitor.get_utilization(self.config.device_id) {
                metrics.gpu_utilization_percent = util.gpu as f32;
                metrics.memory_used_mb = (util.memory as f32 / 100.0) * 
                    self.memory_manager.total_memory_mb() as f32;
            }
        }
        
        // Remove from queue
        self.task_queue.dequeue().await?;
        
        Ok(PluginOutput {
            task_id: task.id,
            status: TaskStatus::Success,
            result,
            metrics: {
                let mut m = HashMap::new();
                m.insert("compute_time_ms".to_string(), elapsed.as_millis() as f64);
                m
            },
        })
    }
    
    async fn shutdown(&mut self) -> Result<()> {
        info!("Shutting down GPU Executor plugin");
        
        // Cleanup CUDA context
        if let Some(mut cuda) = self.cuda_context.write().take() {
            cuda.cleanup()?;
        }
        
        // Cleanup memory
        self.memory_manager.cleanup()?;
        
        // Shutdown NVML
        self.nvml_monitor.shutdown()?;
        
        info!("✅ GPU Executor shutdown complete");
        Ok(())
    }
    
    fn health_check(&self) -> HealthStatus {
        let metrics = self.metrics.read();
        
        HealthStatus {
            healthy: metrics.temperature_celsius < self.config.temperature_limit as f32,
            uptime_seconds: 0, // Would track this separately
            tasks_completed: metrics.tasks_completed,
            tasks_failed: metrics.tasks_failed,
            memory_usage_mb: metrics.memory_used_mb,
        }
    }
}

impl GpuExecutor {
    /// Execute compute task
    async fn execute_compute(&self, cuda: &CudaContext, task: &PluginTask) -> Result<Vec<u8>> {
        debug!("Executing compute task on GPU");
        
        // Allocate memory
        let input_size = task.payload.len();
        let output_size = input_size; // For simplicity
        
        let input_mem = self.memory_manager.allocate(input_size)?;
        let output_mem = self.memory_manager.allocate(output_size)?;
        
        // Copy input to GPU
        cuda.copy_to_device(&task.payload, input_mem)?;
        
        // Execute kernel
        cuda.execute_kernel(
            "compute_kernel",
            &[input_mem, output_mem],
            input_size,
        )?;
        
        // Copy output from GPU
        let mut output = vec![0u8; output_size];
        cuda.copy_from_device(output_mem, &mut output)?;
        
        // Free memory
        self.memory_manager.free(input_mem)?;
        self.memory_manager.free(output_mem)?;
        
        Ok(output)
    }
    
    /// Execute benchmark task
    async fn execute_benchmark(&self, cuda: &CudaContext, task: &PluginTask) -> Result<Vec<u8>> {
        debug!("Executing benchmark task on GPU");
        
        // Parse benchmark parameters
        let params: BenchmarkParams = bincode::deserialize(&task.payload)?;
        
        let mut results = Vec::new();
        
        for _ in 0..params.iterations {
            let start = std::time::Instant::now();
            
            // Allocate test memory
            let mem = self.memory_manager.allocate(params.data_size)?;
            
            // Run test kernel
            cuda.execute_kernel(
                "benchmark_kernel",
                &[mem],
                params.data_size,
            )?;
            
            // Sync and measure
            cuda.synchronize()?;
            let elapsed = start.elapsed();
            
            results.push(elapsed.as_micros() as f64);
            
            // Free memory
            self.memory_manager.free(mem)?;
        }
        
        // Calculate statistics
        let avg = results.iter().sum::<f64>() / results.len() as f64;
        let throughput_gbps = (params.data_size as f64 / avg) / 1000.0;
        
        let result = BenchmarkResult {
            average_time_us: avg,
            throughput_gbps,
            iterations: params.iterations,
        };
        
        Ok(bincode::serialize(&result)?)
    }
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
struct BenchmarkParams {
    data_size: usize,
    iterations: usize,
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
struct BenchmarkResult {
    average_time_us: f64,
    throughput_gbps: f64,
    iterations: usize,
}

// Export plugin
opus_gpu_core::export_plugin!(GpuExecutor);
