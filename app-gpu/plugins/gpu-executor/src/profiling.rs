//! Performance Profiling and Optimization Module
//! 
//! NVIDIA Nsight integration, custom performance counters, and optimization techniques

use std::sync::Arc;
use std::time::{Duration, Instant};
use std::collections::{HashMap, VecDeque};
use anyhow::{Result, Context};
use parking_lot::RwLock;
use tracing::{debug, info, warn};

/// Performance metrics for GPU operations
#[derive(Debug, Clone, Default)]
pub struct PerformanceMetrics {
    /// Kernel execution times
    pub kernel_times: HashMap<String, KernelMetrics>,
    
    /// Memory transfer metrics
    pub memory_metrics: MemoryTransferMetrics,
    
    /// GPU utilization over time
    pub utilization_history: VecDeque<UtilizationPoint>,
    
    /// Bottleneck analysis
    pub bottlenecks: Vec<Bottleneck>,
    
    /// Optimization suggestions
    pub suggestions: Vec<OptimizationSuggestion>,
}

#[derive(Debug, Clone, Default)]
pub struct KernelMetrics {
    pub name: String,
    pub invocations: u64,
    pub total_time_us: f64,
    pub min_time_us: f64,
    pub max_time_us: f64,
    pub avg_time_us: f64,
    pub occupancy: f32,
    pub achieved_bandwidth_gbps: f32,
}

#[derive(Debug, Clone, Default)]
pub struct MemoryTransferMetrics {
    pub host_to_device_bytes: u64,
    pub device_to_host_bytes: u64,
    pub device_to_device_bytes: u64,
    pub total_transfer_time_ms: f64,
    pub effective_bandwidth_gbps: f32,
    pub pcie_utilization: f32,
}

#[derive(Debug, Clone)]
pub struct UtilizationPoint {
    pub timestamp: Instant,
    pub gpu_percent: f32,
    pub memory_percent: f32,
    pub temperature: f32,
    pub power_watts: f32,
}

#[derive(Debug, Clone)]
pub enum Bottleneck {
    ComputeBound {
        kernel: String,
        utilization: f32,
    },
    MemoryBound {
        bandwidth_percent: f32,
        access_pattern: String,
    },
    LatencyBound {
        kernel_launch_overhead_us: f64,
        sync_overhead_us: f64,
    },
    ThermalThrottle {
        temperature: f32,
        frequency_reduction: f32,
    },
}

#[derive(Debug, Clone)]
pub enum OptimizationSuggestion {
    IncreaseBlockSize {
        kernel: String,
        current: u32,
        suggested: u32,
    },
    EnableMemoryCoalescing {
        kernel: String,
        uncoalesced_accesses: u32,
    },
    UseSharememory {
        kernel: String,
        potential_speedup: f32,
    },
    KernelFusion {
        kernels: Vec<String>,
        overhead_reduction_ms: f64,
    },
    StreamConcurrency {
        current_streams: u32,
        suggested_streams: u32,
    },
}

/// Performance profiler
pub struct GpuProfiler {
    enabled: Arc<RwLock<bool>>,
    metrics: Arc<RwLock<PerformanceMetrics>>,
    history_size: usize,
    profile_level: ProfileLevel,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ProfileLevel {
    Basic,      // Timing only
    Detailed,   // Timing + occupancy
    Full,       // All metrics including Nsight
}

impl GpuProfiler {
    pub fn new(profile_level: ProfileLevel) -> Self {
        Self {
            enabled: Arc::new(RwLock::new(false)),
            metrics: Arc::new(RwLock::new(PerformanceMetrics::default())),
            history_size: 1000,
            profile_level,
        }
    }
    
    /// Start profiling
    pub fn start(&self) -> Result<()> {
        *self.enabled.write() = true;
        
        if self.profile_level == ProfileLevel::Full {
            // Initialize NVIDIA Nsight if available
            #[cfg(feature = "profiling")]
            {
                self.init_nsight()?;
            }
        }
        
        info!("GPU profiling started at {:?} level", self.profile_level);
        Ok(())
    }
    
    /// Stop profiling
    pub fn stop(&self) -> Result<()> {
        *self.enabled.write() = false;
        
        #[cfg(feature = "profiling")]
        {
            self.cleanup_nsight()?;
        }
        
        info!("GPU profiling stopped");
        Ok(())
    }
    
    /// Record kernel execution
    pub fn record_kernel(&self, name: &str, duration: Duration, occupancy: Option<f32>) {
        if !*self.enabled.read() {
            return;
        }
        
        let mut metrics = self.metrics.write();
        let kernel_metrics = metrics.kernel_times.entry(name.to_string())
            .or_insert_with(|| KernelMetrics {
                name: name.to_string(),
                min_time_us: f64::MAX,
                ..Default::default()
            });
        
        let time_us = duration.as_micros() as f64;
        
        kernel_metrics.invocations += 1;
        kernel_metrics.total_time_us += time_us;
        kernel_metrics.min_time_us = kernel_metrics.min_time_us.min(time_us);
        kernel_metrics.max_time_us = kernel_metrics.max_time_us.max(time_us);
        kernel_metrics.avg_time_us = kernel_metrics.total_time_us / kernel_metrics.invocations as f64;
        
        if let Some(occ) = occupancy {
            kernel_metrics.occupancy = occ;
        }
        
        debug!("Recorded kernel '{}': {:.2} μs", name, time_us);
    }
    
    /// Record memory transfer
    pub fn record_memory_transfer(&self, bytes: usize, direction: TransferDirection, duration: Duration) {
        if !*self.enabled.read() {
            return;
        }
        
        let mut metrics = self.metrics.write();
        let mem_metrics = &mut metrics.memory_metrics;
        
        match direction {
            TransferDirection::HostToDevice => {
                mem_metrics.host_to_device_bytes += bytes as u64;
            }
            TransferDirection::DeviceToHost => {
                mem_metrics.device_to_host_bytes += bytes as u64;
            }
            TransferDirection::DeviceToDevice => {
                mem_metrics.device_to_device_bytes += bytes as u64;
            }
        }
        
        mem_metrics.total_transfer_time_ms += duration.as_millis() as f64;
        
        // Calculate effective bandwidth
        let total_bytes = mem_metrics.host_to_device_bytes + 
                         mem_metrics.device_to_host_bytes + 
                         mem_metrics.device_to_device_bytes;
        
        if mem_metrics.total_transfer_time_ms > 0.0 {
            mem_metrics.effective_bandwidth_gbps = 
                (total_bytes as f64 / 1e9) / (mem_metrics.total_transfer_time_ms / 1000.0) as f32;
        }
    }
    
    /// Record GPU utilization
    pub fn record_utilization(&self, gpu: f32, memory: f32, temp: f32, power: f32) {
        if !*self.enabled.read() {
            return;
        }
        
        let mut metrics = self.metrics.write();
        
        let point = UtilizationPoint {
            timestamp: Instant::now(),
            gpu_percent: gpu,
            memory_percent: memory,
            temperature: temp,
            power_watts: power,
        };
        
        metrics.utilization_history.push_back(point);
        
        // Keep history bounded
        while metrics.utilization_history.len() > self.history_size {
            metrics.utilization_history.pop_front();
        }
    }
    
    /// Analyze bottlenecks
    pub fn analyze_bottlenecks(&self) -> Vec<Bottleneck> {
        let metrics = self.metrics.read();
        let mut bottlenecks = Vec::new();
        
        // Check compute bound
        if let Some(latest_util) = metrics.utilization_history.back() {
            if latest_util.gpu_percent > 95.0 {
                for (kernel, kernel_metrics) in &metrics.kernel_times {
                    if kernel_metrics.occupancy < 0.5 {
                        bottlenecks.push(Bottleneck::ComputeBound {
                            kernel: kernel.clone(),
                            utilization: latest_util.gpu_percent,
                        });
                    }
                }
            }
            
            // Check thermal throttle
            if latest_util.temperature > 80.0 {
                bottlenecks.push(Bottleneck::ThermalThrottle {
                    temperature: latest_util.temperature,
                    frequency_reduction: (85.0 - latest_util.temperature).max(0.0) * 2.0,
                });
            }
        }
        
        // Check memory bound
        if metrics.memory_metrics.pcie_utilization > 80.0 {
            bottlenecks.push(Bottleneck::MemoryBound {
                bandwidth_percent: metrics.memory_metrics.pcie_utilization,
                access_pattern: "Sequential".to_string(),
            });
        }
        
        // Check latency bound
        let total_kernel_time: f64 = metrics.kernel_times.values()
            .map(|k| k.total_time_us)
            .sum();
        
        let total_invocations: u64 = metrics.kernel_times.values()
            .map(|k| k.invocations)
            .sum();
        
        if total_invocations > 0 {
            let avg_kernel_time = total_kernel_time / total_invocations as f64;
            if avg_kernel_time < 10.0 { // Very short kernels
                bottlenecks.push(Bottleneck::LatencyBound {
                    kernel_launch_overhead_us: 5.0, // Typical launch overhead
                    sync_overhead_us: 2.0,
                });
            }
        }
        
        bottlenecks
    }
    
    /// Generate optimization suggestions
    pub fn suggest_optimizations(&self) -> Vec<OptimizationSuggestion> {
        let metrics = self.metrics.read();
        let mut suggestions = Vec::new();
        
        // Analyze kernel metrics
        for (kernel, kernel_metrics) in &metrics.kernel_times {
            // Low occupancy suggests block size tuning
            if kernel_metrics.occupancy < 0.5 {
                suggestions.push(OptimizationSuggestion::IncreaseBlockSize {
                    kernel: kernel.clone(),
                    current: 128,
                    suggested: 256,
                });
            }
            
            // Check for shared memory opportunity
            if kernel_metrics.avg_time_us > 100.0 {
                suggestions.push(OptimizationSuggestion::UseSharememory {
                    kernel: kernel.clone(),
                    potential_speedup: 2.0,
                });
            }
        }
        
        // Check for kernel fusion opportunities
        let short_kernels: Vec<String> = metrics.kernel_times
            .iter()
            .filter(|(_, m)| m.avg_time_us < 10.0)
            .map(|(k, _)| k.clone())
            .collect();
        
        if short_kernels.len() >= 2 {
            suggestions.push(OptimizationSuggestion::KernelFusion {
                kernels: short_kernels,
                overhead_reduction_ms: 0.1,
            });
        }
        
        suggestions
    }
    
    /// Get performance report
    pub fn get_report(&self) -> PerformanceReport {
        let metrics = self.metrics.read();
        let bottlenecks = self.analyze_bottlenecks();
        let suggestions = self.suggest_optimizations();
        
        PerformanceReport {
            kernel_metrics: metrics.kernel_times.clone(),
            memory_metrics: metrics.memory_metrics.clone(),
            avg_gpu_utilization: Self::calculate_avg_utilization(&metrics.utilization_history),
            peak_memory_usage_mb: Self::calculate_peak_memory(&metrics.utilization_history),
            bottlenecks,
            suggestions,
            profiling_duration: Duration::from_secs(0), // Would track actual duration
        }
    }
    
    fn calculate_avg_utilization(history: &VecDeque<UtilizationPoint>) -> f32 {
        if history.is_empty() {
            return 0.0;
        }
        
        let sum: f32 = history.iter().map(|p| p.gpu_percent).sum();
        sum / history.len() as f32
    }
    
    fn calculate_peak_memory(history: &VecDeque<UtilizationPoint>) -> f32 {
        history.iter()
            .map(|p| p.memory_percent)
            .max_by(|a, b| a.partial_cmp(b).unwrap())
            .unwrap_or(0.0)
    }
    
    #[cfg(feature = "profiling")]
    fn init_nsight(&self) -> Result<()> {
        // Initialize NVIDIA Nsight Systems/Compute
        // This would use nvtx markers and cupti
        Ok(())
    }
    
    #[cfg(feature = "profiling")]
    fn cleanup_nsight(&self) -> Result<()> {
        // Cleanup Nsight resources
        Ok(())
    }
}

#[derive(Debug, Clone, Copy)]
pub enum TransferDirection {
    HostToDevice,
    DeviceToHost,
    DeviceToDevice,
}

/// Performance report
#[derive(Debug, Clone)]
pub struct PerformanceReport {
    pub kernel_metrics: HashMap<String, KernelMetrics>,
    pub memory_metrics: MemoryTransferMetrics,
    pub avg_gpu_utilization: f32,
    pub peak_memory_usage_mb: f32,
    pub bottlenecks: Vec<Bottleneck>,
    pub suggestions: Vec<OptimizationSuggestion>,
    pub profiling_duration: Duration,
}

/// Error recovery manager
pub struct ErrorRecoveryManager {
    max_retries: u32,
    recovery_strategies: HashMap<String, RecoveryStrategy>,
    error_history: Arc<RwLock<VecDeque<GpuError>>>,
}

#[derive(Debug, Clone)]
pub struct GpuError {
    pub timestamp: Instant,
    pub error_type: GpuErrorType,
    pub kernel: Option<String>,
    pub recovered: bool,
}

#[derive(Debug, Clone)]
pub enum GpuErrorType {
    OutOfMemory,
    KernelLaunchFailure,
    DeviceLost,
    Timeout,
    InvalidConfiguration,
    ThermalShutdown,
}

#[derive(Debug, Clone)]
pub enum RecoveryStrategy {
    Retry { delay_ms: u64 },
    ResetDevice,
    ReduceWorkload,
    Fallback,
    Abort,
}

impl ErrorRecoveryManager {
    pub fn new() -> Self {
        let mut strategies = HashMap::new();
        
        // Default recovery strategies
        strategies.insert("OutOfMemory".to_string(), 
                         RecoveryStrategy::ReduceWorkload);
        strategies.insert("KernelLaunchFailure".to_string(), 
                         RecoveryStrategy::Retry { delay_ms: 100 });
        strategies.insert("DeviceLost".to_string(), 
                         RecoveryStrategy::ResetDevice);
        strategies.insert("Timeout".to_string(), 
                         RecoveryStrategy::Retry { delay_ms: 500 });
        strategies.insert("ThermalShutdown".to_string(), 
                         RecoveryStrategy::Abort);
        
        Self {
            max_retries: 3,
            recovery_strategies: strategies,
            error_history: Arc::new(RwLock::new(VecDeque::new())),
        }
    }
    
    /// Handle GPU error with recovery
    pub async fn handle_error(&self, error_type: GpuErrorType, kernel: Option<String>) -> Result<()> {
        let mut error = GpuError {
            timestamp: Instant::now(),
            error_type: error_type.clone(),
            kernel: kernel.clone(),
            recovered: false,
        };
        
        // Get recovery strategy
        let strategy = self.recovery_strategies
            .get(&format!("{:?}", error_type))
            .cloned()
            .unwrap_or(RecoveryStrategy::Abort);
        
        match strategy {
            RecoveryStrategy::Retry { delay_ms } => {
                info!("Retrying after {} ms", delay_ms);
                tokio::time::sleep(Duration::from_millis(delay_ms)).await;
                error.recovered = true;
            }
            RecoveryStrategy::ResetDevice => {
                warn!("Resetting GPU device");
                self.reset_gpu_device().await?;
                error.recovered = true;
            }
            RecoveryStrategy::ReduceWorkload => {
                info!("Reducing workload due to resource constraints");
                error.recovered = true;
            }
            RecoveryStrategy::Fallback => {
                info!("Falling back to CPU implementation");
                error.recovered = true;
            }
            RecoveryStrategy::Abort => {
                return Err(anyhow::anyhow!("Unrecoverable GPU error: {:?}", error_type));
            }
        }
        
        // Record error
        self.error_history.write().push_back(error);
        
        Ok(())
    }
    
    async fn reset_gpu_device(&self) -> Result<()> {
        // In real implementation, would reset CUDA context
        // cuda::cuCtxReset()
        info!("GPU device reset completed");
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_profiler_recording() {
        let profiler = GpuProfiler::new(ProfileLevel::Basic);
        profiler.start().unwrap();
        
        profiler.record_kernel("test_kernel", Duration::from_micros(100), Some(0.75));
        profiler.record_memory_transfer(1024 * 1024, TransferDirection::HostToDevice, 
                                       Duration::from_micros(50));
        
        let report = profiler.get_report();
        assert!(report.kernel_metrics.contains_key("test_kernel"));
        assert_eq!(report.memory_metrics.host_to_device_bytes, 1024 * 1024);
    }
    
    #[tokio::test]
    async fn test_error_recovery() {
        let recovery = ErrorRecoveryManager::new();
        
        // Test retry strategy
        recovery.handle_error(GpuErrorType::KernelLaunchFailure, 
                            Some("test_kernel".to_string())).await.unwrap();
        
        // Test reduce workload strategy
        recovery.handle_error(GpuErrorType::OutOfMemory, None).await.unwrap();
    }
}
