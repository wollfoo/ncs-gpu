/*!
 * Linux Capabilities & Seccomp - Runtime Privilege Reduction
 *
 * Giảm thiểu attack surface bằng cách:
 * - Drop unnecessary Linux capabilities
 * - Apply seccomp syscall filtering
 * - Restrict process privileges theo principle of least privilege
 */

use super::{Result, SecurityError};
use tracing::info;

/// Drop all unnecessary Linux capabilities
///
/// Chỉ giữ lại các capabilities cần thiết cho GPU mining:
/// - CAP_SYS_NICE: GPU scheduling và thread priority
///
/// # Safety
/// Phải được gọi TRƯỚC khi load bất kỳ sensitive binaries nào
pub fn drop_capabilities() -> Result<()> {
    #[cfg(target_os = "linux")]
    {
        use caps::{Capability, CapSet};

        info!("🔒 Dropping unnecessary Linux capabilities...");

        // Get current capabilities
        let current_caps = caps::read(None, CapSet::Effective)
            .map_err(|e| SecurityError::CapabilityError(format!("Failed to read capabilities: {}", e)))?;

        info!("📋 Current capabilities: {:?}", current_caps);

        // Clear ALL capabilities first
        caps::clear(None, CapSet::Permitted)
            .map_err(|e| SecurityError::CapabilityError(format!("Failed to clear permitted caps: {}", e)))?;

        caps::clear(None, CapSet::Effective)
            .map_err(|e| SecurityError::CapabilityError(format!("Failed to clear effective caps: {}", e)))?;

        caps::clear(None, CapSet::Inheritable)
            .map_err(|e| SecurityError::CapabilityError(format!("Failed to clear inheritable caps: {}", e)))?;

        // Add back only needed capabilities
        use std::collections::HashSet;
        let mut needed_caps = HashSet::new();
        needed_caps.insert(Capability::CAP_SYS_NICE); // GPU scheduling

        caps::set(None, CapSet::Permitted, &needed_caps)
            .map_err(|e| SecurityError::CapabilityError(format!("Failed to set permitted caps: {}", e)))?;

        caps::set(None, CapSet::Effective, &needed_caps)
            .map_err(|e| SecurityError::CapabilityError(format!("Failed to activate effective caps: {}", e)))?;

        info!("✅ Capabilities reduced to: {:?}", needed_caps);
        Ok(())
    }

    #[cfg(not(target_os = "linux"))]
    {
        warn!("⚠️  Capability dropping only supported on Linux. Skipping.");
        Ok(())
    }
}

/// Apply seccomp syscall filtering
///
/// Whitelist only syscalls cần thiết cho GPU mining operations:
/// - Memory: mmap, munmap, mprotect, brk
/// - File I/O: read, write, open, close, stat
/// - GPU: ioctl (for /dev/nvidia*)
/// - Network: socket, connect, send, recv (cho pool communication)
/// - Threading: clone, futex, sched_setaffinity
///
/// Block dangerous syscalls:
/// - Process manipulation: ptrace, kexec_load, reboot
/// - Module loading: init_module, delete_module
/// - System admin: swapon, swapoff, mount, umount
pub fn apply_seccomp_filter() -> Result<()> {
    #[cfg(target_os = "linux")]
    {
        info!("🔒 Applying seccomp syscall filter...");

        // Tạo seccomp filter với allowed syscalls
        let bpf_program = create_mining_seccomp_filter()?;

        // Apply filter via seccomp syscall
        use seccompiler::apply_filter;
        apply_filter(&bpf_program)
            .map_err(|e| SecurityError::SeccompError(format!("Failed to apply seccomp: {:?}", e)))?;

        info!("✅ Seccomp filter applied successfully");
        Ok(())
    }

    #[cfg(not(target_os = "linux"))]
    {
        warn!("⚠️  Seccomp filtering only supported on Linux. Skipping.");
        Ok(())
    }
}

#[cfg(target_os = "linux")]
fn create_mining_seccomp_filter() -> Result<seccompiler::BpfProgram> {
    use seccompiler::{
        SeccompAction, SeccompFilter, SeccompRule,
    };
    use std::collections::BTreeMap;

    // Define allowed syscalls
    let mut rules: BTreeMap<i64, Vec<SeccompRule>> = BTreeMap::new();

    // Essential syscalls (always allow)
    let essential = vec![
        libc::SYS_read,
        libc::SYS_write,
        libc::SYS_open,
        libc::SYS_openat,
        libc::SYS_close,
        libc::SYS_stat,
        libc::SYS_fstat,
        libc::SYS_lstat,
        libc::SYS_poll,
        libc::SYS_lseek,
        libc::SYS_mmap,
        libc::SYS_mprotect,
        libc::SYS_munmap,
        libc::SYS_brk,
        libc::SYS_rt_sigaction,
        libc::SYS_rt_sigprocmask,
        libc::SYS_rt_sigreturn,
        libc::SYS_ioctl, // Critical for GPU access
        libc::SYS_access,
        libc::SYS_pipe,
        libc::SYS_select,
        libc::SYS_sched_yield,
        libc::SYS_mremap,
        libc::SYS_dup,
        libc::SYS_dup2,
        libc::SYS_nanosleep,
        libc::SYS_getpid,
        libc::SYS_clone, // Threading
        libc::SYS_fork,
        libc::SYS_execve,
        libc::SYS_exit,
        libc::SYS_exit_group,
        libc::SYS_wait4,
        libc::SYS_kill,
        libc::SYS_uname,
        libc::SYS_fcntl,
        libc::SYS_flock,
        libc::SYS_fsync,
        libc::SYS_getcwd,
        libc::SYS_chdir,
        libc::SYS_getdents,
        libc::SYS_getdents64,
        libc::SYS_readlink,
        libc::SYS_gettimeofday,
        libc::SYS_getrlimit,
        libc::SYS_getrusage,
        libc::SYS_sysinfo,
        libc::SYS_times,
        libc::SYS_getuid,
        libc::SYS_getgid,
        libc::SYS_geteuid,
        libc::SYS_getegid,
        libc::SYS_getppid,
        libc::SYS_getpgrp,
        libc::SYS_setsid,
        libc::SYS_setpgid,
        libc::SYS_getsid,
        libc::SYS_capget,
        libc::SYS_capset,
        libc::SYS_prctl,
        libc::SYS_arch_prctl,
        libc::SYS_setrlimit,
        libc::SYS_chroot,
        libc::SYS_sync,
        libc::SYS_gettid,
        libc::SYS_futex, // Thread synchronization
        libc::SYS_sched_setaffinity, // CPU pinning for performance
        libc::SYS_sched_getaffinity,
        libc::SYS_set_tid_address,
        libc::SYS_clock_gettime,
        libc::SYS_clock_getres,
        libc::SYS_clock_nanosleep,
        libc::SYS_tgkill,
        libc::SYS_set_robust_list,
        libc::SYS_get_robust_list,
    ];

    // Network syscalls (cho pool connection)
    let network = vec![
        libc::SYS_socket,
        libc::SYS_connect,
        libc::SYS_accept,
        libc::SYS_sendto,
        libc::SYS_recvfrom,
        libc::SYS_sendmsg,
        libc::SYS_recvmsg,
        libc::SYS_bind,
        libc::SYS_listen,
        libc::SYS_getsockname,
        libc::SYS_getpeername,
        libc::SYS_socketpair,
        libc::SYS_setsockopt,
        libc::SYS_getsockopt,
    ];

    // Add all allowed syscalls
    for syscall in essential.into_iter().chain(network.into_iter()) {
        rules.insert(syscall, vec![]);
    }

    // Create filter with default DENY action
    let filter = SeccompFilter::new(
        rules,
        SeccompAction::Errno(libc::EPERM as u32), // Default: deny with EPERM
        SeccompAction::Allow, // Matched rules: allow
        std::env::consts::ARCH.try_into()
            .map_err(|e| SecurityError::SeccompError(format!("Unsupported architecture: {:?}", e)))?,
    )
    .map_err(|e| SecurityError::SeccompError(format!("Failed to create filter: {}", e)))?;

    // Compile to BPF program
    filter.try_into()
        .map_err(|e| SecurityError::SeccompError(format!("Failed to compile filter: {:?}", e)))
}

/// Test if process has specific capability
#[cfg(target_os = "linux")]
pub fn has_capability(cap: caps::Capability) -> bool {
    caps::has_cap(None, caps::CapSet::Effective, cap).unwrap_or(false)
}

/// Get current effective capabilities as string
#[cfg(target_os = "linux")]
pub fn get_capabilities_string() -> String {
    match caps::read(None, caps::CapSet::Effective) {
        Ok(caps) => format!("{:?}", caps),
        Err(e) => format!("Error reading capabilities: {}", e),
    }
}

#[cfg(not(target_os = "linux"))]
pub fn has_capability(_cap: ()) -> bool {
    false
}

#[cfg(not(target_os = "linux"))]
pub fn get_capabilities_string() -> String {
    "N/A (non-Linux system)".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[cfg(target_os = "linux")]
    fn test_capability_operations() {
        // Note: This test may require elevated privileges
        // Run with: cargo test --features test-privileged

        // Just test that functions don't panic
        let _ = get_capabilities_string();
        let _ = has_capability(caps::Capability::CAP_SYS_NICE);
    }

    #[test]
    fn test_cross_platform_compatibility() {
        // Should not panic on any platform
        let result = drop_capabilities();
        assert!(result.is_ok());

        let result = apply_seccomp_filter();
        assert!(result.is_ok());
    }
}
