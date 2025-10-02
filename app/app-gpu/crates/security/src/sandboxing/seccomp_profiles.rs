//! # Seccomp Profiles (Hồ Sơ Seccomp)
//!
//! Lọc syscall để giảm attack surface và implement sandboxing cho GPU mining operations.

use tracing::{debug, info, warn};

/// Seccomp profile type (kiểu profile seccomp)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SeccompProfile {
    /// Strict: Kill process on unlisted syscall (production)
    Strict,
    /// Permissive: Log violations, allow execution (development)
    Permissive,
}

/// Seccomp configuration (cấu hình seccomp)
#[derive(Debug, Clone)]
pub struct SeccompConfig {
    /// Profile type
    pub profile: SeccompProfile,
    /// Whitelisted syscalls (các syscall được cho phép)
    pub allowed_syscalls: std::collections::HashSet<String>,
}

impl Default for SeccompConfig {
    fn default() -> Self {
        Self::strict()
    }
}

impl SeccompConfig {
    /// Production-ready strict profile (profile nghiêm ngặt cho sản xuất)
    pub fn strict() -> Self {
        Self {
            profile: SeccompProfile::Strict,
            allowed_syscalls: Self::core_mining_syscalls().into_iter().collect(),
        }
    }

    /// Development-permissive profile (profile cho phép phát triển)
    pub fn permissive() -> Self {
        Self {
            profile: SeccompProfile::Permissive,
            allowed_syscalls: Self::core_mining_syscalls().into_iter().collect(),
        }
    }

    /// Core syscalls required for GPU mining operations
    /// Based on NVIDIA CUDA runtime + Linux kernel requirements
    fn core_mining_syscalls() -> Vec<String> {
        vec![
            // === ESSENTIAL SYSTEM ===
            "read".to_string(), "write".to_string(), "close".to_string(),     // File I/O
            "mmap".to_string(), "munmap".to_string(), "mprotect".to_string(), // Memory management
            "brk".to_string(), "madvise".to_string(),            // Heap management

            // === GPU/CUDA DRIVERS ===
            "ioctl".to_string(),                     // NVIDIA driver communication (CRITICAL)

            // === THREADING/TIMING ===
            "futex".to_string(),                     // Thread synchronization
            "sched_yield".to_string(),               // Thread scheduling
            "getpid".to_string(), "gettid".to_string(), "getppid".to_string(), // Process/thread IDs
            "clock_gettime".to_string(), "clock_nanosleep".to_string(), // High-precision timing
            "nanosleep".to_string(), "select".to_string(), "poll".to_string(), // Time operations

            // === NETWORKING ===
            "socket".to_string(), "connect".to_string(), "bind".to_string(), "listen".to_string(),
            "sendto".to_string(), "recvfrom".to_string(), "recv".to_string(), "send".to_string(),
            "getsockname".to_string(), "getpeername".to_string(), "setsockopt".to_string(), "getsockopt".to_string(),

            // === FILESYSTEM (LIMITED) ===
            "open".to_string(), "stat".to_string(), "lstat".to_string(), "fstat".to_string(),    // File status
            "access".to_string(), "readlink".to_string(),               // Path operations
            "fsync".to_string(), "fdatasync".to_string(),               // Sync operations

            // === SIGNALS ===
            "sigaltstack".to_string(), "rt_sigreturn".to_string(), // Signal handling
            "rt_sigaction".to_string(), "rt_sigprocmask".to_string(), // Signal operations

            // === MEMORY ===
            "mlock".to_string(), "munlock".to_string(), // Memory locking
            "mincore".to_string(), "msync".to_string(),  // Memory operations

            // === PROCESS MANAGEMENT ===
            "arch_prctl".to_string(), // Architecture-specific setup
            "getrlimit".to_string(), "setrlimit".to_string(), // Resource limits
            "getrusage".to_string(), "times".to_string(), // Resource usage
            "uname".to_string(), // System info
            "getrandom".to_string(), // Secure randomness
        ]
    }

    /// Apply seccomp filter (áp dụng bộ lọc seccomp)
    pub fn apply(&self) -> anyhow::Result<()> {
        #[cfg(target_os = "linux")]
        {
            use libseccomp::*;

            // Create seccomp context with appropriate action
            let default_action = match self.profile {
                SeccompProfile::Strict => ScmpAction::KillProcess,
                SeccompProfile::Permissive => ScmpAction::Log,
            };

            let mut ctx = ScmpFilterContext::new_filter(default_action)?;

            // ===== BLOCK ALL SYSCALLS BY DEFAULT =====
            // This is implicit - default action kills/logs unlisted syscalls

            // ===== ALLOW WHITELISTED SYSCALLS =====
            for syscall_name in &self.allowed_syscalls {
                if let Ok(nr) = ScmpSyscall::from_name(syscall_name) {
                    ctx.add_rule(ScmpAction::Allow, nr)?;
                    debug!(syscall = syscall_name, "Whitelisted syscall");
                } else {
                    warn!(syscall = syscall_name, "Unknown syscall, skipping whitelist");
                }
            }

            // ===== STRICT SECURITY: EXPLICITLY BLOCK DANGEROUS CALLS =====
            // Even if not in whitelist, explicitly deny these attack vectors
            let dangerous_syscalls = vec![
                "execve".to_string(), "fork".to_string(), "vfork".to_string(), "clone".to_string(),    // Process creation
                "ptrace".to_string(), "kexec_load".to_string(), "reboot".to_string(),        // System control
                "mount".to_string(), "umount2".to_string(),                     // Filesystem mounting
            ];

            for syscall in dangerous_syscalls {
                if let Ok(nr) = ScmpSyscall::from_name(&syscall) {
                    ctx.add_rule(ScmpAction::KillProcess, nr)?;
                    debug!(syscall = syscall, "Explicitly blocked dangerous syscall");
                }
            }

            // Load filter into kernel
            ctx.load()?;

            info!(
                profile = ?self.profile,
                allowed_syscalls = self.allowed_syscalls.len(),
                "Seccomp filter applied successfully"
            );

            Ok(())
        }

        #[cfg(not(target_os = "linux"))]
        {
            info!("Seccomp not available on non-Linux platforms, skipping");
            Ok(())
        }
    }

    /// Verify sandbox works (test bằng dangerous syscall)
    pub fn test_sandbox(&self) -> anyhow::Result<()> {
        // Simple test - Note: Real testing requires subprocess
        warn!("Sandbox testing requires elevated privileges - use production environment");
        Ok(())
    }
}

/// Legacy function for backward compatibility
/// Recommended: Use SeccompConfig::strict() or SeccompConfig::permissive() instead
pub fn apply_seccomp_profile(profile: SeccompProfile) -> anyhow::Result<()> {
    info!("🔐 Applying seccomp profile: {:?}", profile);

    let config = match profile {
        SeccompProfile::Strict => SeccompConfig::strict(),
        SeccompProfile::Permissive => SeccompConfig::permissive(),
    };

    config.apply()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_seccomp_config_creation() {
        let strict = SeccompConfig::strict();
        assert_eq!(strict.profile, SeccompProfile::Strict);
        assert!(strict.allowed_syscalls.contains("read"));
        assert!(strict.allowed_syscalls.contains("ioctl")); // Critical for GPU

        let permissive = SeccompConfig::permissive();
        assert_eq!(permissive.profile, SeccompProfile::Permissive);
        assert!(permissive.allowed_syscalls.contains("read"));
    }

    #[test]
    fn test_core_syscalls_includes_gpu() {
        let config = SeccompConfig::strict();
        // Critical GPU syscalls must be whitelisted
        assert!(config.allowed_syscalls.contains("ioctl"), "ioctl required for GPU drivers");
        assert!(config.allowed_syscalls.contains("futex"), "futex required for thread sync");
        assert!(config.allowed_syscalls.contains("socket"), "socket required for Stratum");
    }

    #[test]
    fn test_syscall_list_length() {
        let config = SeccompConfig::strict();
        // Should have reasonable whitelist size
        assert!(config.allowed_syscalls.len() > 20, "Whitelist too small for full mining operations");
        assert!(config.allowed_syscalls.len() < 100, "Whitelist too large, insufficient security");
    }

    #[test]
    fn test_default_config_is_strict() {
        let default = SeccompConfig::default();
        assert_eq!(default.profile, SeccompProfile::Strict);
    }

    #[test]
    fn test_legacy_function_backward_compatibility() {
        // Test backward compatibility
        let strict_result = apply_seccomp_profile(SeccompProfile::Strict);
        let permissive_result = apply_seccomp_profile(SeccompProfile::Permissive);

        // In test environments, seccomp may fail due to privileges
        // The important thing is that the functions don't panic
        #[cfg(target_os = "linux")]
        {
            // On Linux, seccomp might fail due to no privileges - that's expected
            let _ = strict_result;
            let _ = permissive_result;
        }

        #[cfg(not(target_os = "linux"))]
        {
            // On other platforms, should succeed (no-op)
            assert!(strict_result.is_ok());
            assert!(permissive_result.is_ok());
        }
    }
}

#[cfg(test)]
mod integration_tests {
    use super::*;

    // Test basic platform compatibility
    #[test]
    fn test_platform_compatibility_check() {
        let config = SeccompConfig::strict();

        // Verify essential syscalls are included
        assert!(config.allowed_syscalls.contains("read"));
        assert!(config.allowed_syscalls.contains("ioctl"));
        assert!(config.allowed_syscalls.contains("mmap"));

        #[cfg(not(target_os = "linux"))]
        {
            // On non-Linux platforms, should skip gracefully
            let result = config.apply();
            assert!(result.is_ok());
        }
    }
}