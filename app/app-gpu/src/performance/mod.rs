//! Performance optimization utilities
//!
//! Provides tools for performance monitoring and optimization:
//! - CPU affinity management
//! - Memory allocation strategies
//! - Lock-free data structures
//! - Performance profiling helpers

use crate::error::{MinerError, Result};
use tracing::debug;

/// Set CPU affinity for current thread (Linux only)
///
/// # Arguments
/// * `core_ids` - Vector of CPU core IDs to pin to
pub fn set_cpu_affinity(core_ids: &[usize]) -> Result<()> {
    #[cfg(target_os = "linux")]
    {
        use libc::{cpu_set_t, sched_setaffinity, CPU_SET, CPU_ZERO};
        use std::mem;

        unsafe {
            let mut cpuset: cpu_set_t = mem::zeroed();
            CPU_ZERO(&mut cpuset);

            for &core_id in core_ids {
                CPU_SET(core_id, &mut cpuset);
            }

            let result = sched_setaffinity(0, mem::size_of::<cpu_set_t>(), &cpuset);
            if result == 0 {
                debug!(?core_ids, "Thread CPU affinity set");
                Ok(())
            } else {
                Err(MinerError::Runtime(format!(
                    "Failed to set CPU affinity: errno {}",
                    *libc::__errno_location()
                )))
            }
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        debug!(?core_ids, "CPU affinity not supported on this platform");
        Ok(())
    }
}

/// Get current thread's CPU affinity (Linux only)
pub fn get_cpu_affinity() -> Result<Vec<usize>> {
    #[cfg(target_os = "linux")]
    {
        use libc::{cpu_set_t, sched_getaffinity, CPU_ISSET};
        use std::mem;

        unsafe {
            let mut cpuset: cpu_set_t = mem::zeroed();
            let result = sched_getaffinity(0, mem::size_of::<cpu_set_t>(), &mut cpuset);

            if result == 0 {
                let mut cores = Vec::new();
                for core_id in 0..num_cpus::get() {
                    if CPU_ISSET(core_id, &cpuset) {
                        cores.push(core_id);
                    }
                }
                debug!(?cores, "Current CPU affinity");
                Ok(cores)
            } else {
                Err(MinerError::Runtime(format!(
                    "Failed to get CPU affinity: errno {}",
                    *libc::__errno_location()
                )))
            }
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        debug!("CPU affinity not supported on this platform");
        Ok((0..num_cpus::get()).collect())
    }
}

/// Configure huge pages for memory allocation (Linux only)
///
/// Huge pages can improve performance for large memory allocations by reducing TLB misses.
pub fn enable_huge_pages() -> Result<()> {
    #[cfg(target_os = "linux")]
    {
        // TODO: Implement madvise(MADV_HUGEPAGE) for allocations
        debug!("Huge pages support: stub implementation");
    }

    #[cfg(not(target_os = "linux"))]
    {
        debug!("Huge pages not supported on this platform");
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_cpu_affinity() {
        let affinity = get_cpu_affinity();
        assert!(affinity.is_ok(), "Should get CPU affinity");
    }

    #[test]
    #[cfg(target_os = "linux")]
    fn test_set_single_core_affinity() {
        let result = set_cpu_affinity(&[0]);
        assert!(result.is_ok(), "Should set CPU affinity to core 0");
    }
}
