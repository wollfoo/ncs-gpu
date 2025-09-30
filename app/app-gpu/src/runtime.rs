//! Tokio runtime configuration and utilities
//!
//! Provides optimized async runtime setup for GPU mining operations.

use crate::error::{MinerError, Result};
use tokio::runtime::{Builder, Runtime};
use tracing::{debug, info};

/// Build a production-optimized Tokio runtime
///
/// Creates a multi-threaded runtime with:
/// - Worker threads = num_cpus
/// - Thread stack size = 2MB (for CUDA operations)
/// - Thread naming for debugging
/// - Blocking thread pool for synchronous operations
///
/// # Returns
/// Configured Tokio runtime or error
pub fn build_runtime() -> Result<Runtime> {
    let num_threads = num_cpus::get();
    info!(
        threads = num_threads,
        "Building Tokio runtime for GPU mining"
    );

    Builder::new_multi_thread()
        .worker_threads(num_threads)
        .thread_name("gpu-miner-worker")
        .thread_stack_size(2 * 1024 * 1024) // 2MB stack for CUDA
        .enable_all()
        .build()
        .map_err(|e| MinerError::Runtime(format!("Failed to build runtime: {}", e)))
}

/// Pin current thread to specific CPU core (Linux only)
///
/// # Arguments
/// * `core_id` - CPU core ID to pin to
///
/// # Note
/// This is a platform-specific optimization stub. Full implementation requires:
/// - Linux: `libc::sched_setaffinity`
/// - Windows: `SetThreadAffinityMask`
/// - macOS: `thread_policy_set`
pub fn pin_thread_to_core(core_id: usize) -> Result<()> {
    #[cfg(target_os = "linux")]
    {
        use libc::{cpu_set_t, sched_setaffinity, CPU_SET, CPU_ZERO};
        use std::mem;

        unsafe {
            let mut cpuset: cpu_set_t = mem::zeroed();
            CPU_ZERO(&mut cpuset);
            CPU_SET(core_id, &mut cpuset);

            let result = sched_setaffinity(0, mem::size_of::<cpu_set_t>(), &cpuset);
            if result == 0 {
                debug!(core_id, "Thread pinned to CPU core");
                Ok(())
            } else {
                Err(MinerError::Runtime(format!(
                    "Failed to pin thread to core {}: errno {}",
                    core_id,
                    *libc::__errno_location()
                )))
            }
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        debug!(
            core_id,
            "Thread pinning not implemented for this platform"
        );
        Ok(())
    }
}

/// Get optimal worker thread count for GPU operations
///
/// Returns a reasonable default based on:
/// - Number of CPU cores
/// - Number of GPUs (TODO: integrate with GPU detection)
/// - System resource constraints
pub fn optimal_worker_count() -> usize {
    let cpus = num_cpus::get();
    // Leave some cores for system and GPU driver threads
    let workers = if cpus > 4 { cpus - 2 } else { cpus };
    debug!(cpus, workers, "Calculated optimal worker count");
    workers
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_build_runtime() {
        let rt = build_runtime();
        assert!(rt.is_ok(), "Runtime should build successfully");
    }

    #[test]
    fn test_optimal_worker_count() {
        let count = optimal_worker_count();
        assert!(count > 0, "Worker count should be positive");
        assert!(
            count <= num_cpus::get(),
            "Worker count should not exceed CPU count"
        );
    }
}
