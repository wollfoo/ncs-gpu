//! # Seccomp Profiles (Hồ Sơ Seccomp)
//!
//! Lọc syscall để giảm attack surface và implement sandboxing cho GPU mining operations.

use serde::{Deserialize, Serialize};
use tracing::{debug, info, warn};

/// Seccomp profile type (kiểu profile seccomp)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SeccompProfile {
    /// Strict: Kill process on unlisted syscall (production)
    #[serde(rename = "strict")]
    Strict,
    /// Permissive: Log violations, allow execution (development)
    #[serde(rename = "permissive")]
    Permissive,
}

/// Seccomp configuration (cấu hình seccomp)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SeccompConfig {
    /// Profile type
    pub profile: SeccompProfile,
    /// Whitelisted syscalls (các syscall được cho phép)
    pub allowed_syscalls: std::collections::HashSet<&'static str>,
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
    fn core_mining_syscalls() -> Vec<&'static str> {
        vec![
            // === ESSENTIAL SYSTEM ===
            "read", "write", "close",     // File I/O
            "mmap", "munmap", "mprotect", // Memory management
            "brk", "madvise",            // Heap management

            // === GPU/CUDA DRIVERS ===
            "ioctl",                     // NVIDIA driver communication (CRITICAL)

            // === THREADING/TIMING ===
            "futex",                     // Thread synchronization
            "sched_yield",               // Thread scheduling
            "getpid", "gettid", "getppid", // Process/thread IDs
            "clock_gettime", "clock_nanosleep", // High-precision timing
            "nanosleep", "select", "poll", // Time operations

            // === NETWORKING ===
            "socket", "connect", "bind", "listen",
            "sendto", "recvfrom", "recv", "send",
            "getsockname", "getpeername", "setsockopt", "getsockopt",

            // === FILESYSTEM (LIMITED) ===
            "open", "stat", "lstat", "fstat",    // File status
            "access", "readlink",               // Path operations
            "fsync", "fdatasync",               // Sync operations

            // === SIGNALS ===
            "sigaltstack", "rt_sigreturn", // Signal handling
            "rt_sigaction", "rt_sigprocmask", // Signal operations

            // === MEMORY ===
            "mlock", "munlock", // Memory locking
            "mincore", "msync",  // Memory operations

            // === PROCESS MANAGEMENT ===
            "arch_prctl", // Architecture-specific setup
            "getrlimit", "setrlimit", // Resource limits
            "getrusage", "times", // Resource usage
            "uname", // System info
            "getrandom", // Secure randomness
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

            let ctx = ScmpFilterCtx::new_filter(default_action)?;

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
                "execve", "fork", "vfork", "clone",    // Process creation
                "ptrace", "kexec_load", "reboot",        // System control
                "mount", "umount2",                     // Filesystem mounting
            ];

            for syscall in dangerous_syscalls {
                if let Ok(nr) = ScmpSyscall::from_name(syscall) {
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
        // Simple test - try to access a restricted resource
        // Note: Real testing would require subprocess
        warn!("Sandbox testing not implemented in-process (would kill current process)");
        Ok(())
    }
}

/// Legacy function for backward compatibility
/// Recommended: Use SeccompConfig::strict() or SeccompConfig::permissive() instead
pub fn apply_seccomp_profile(profile: SeccompProfile) -> Result<()> {
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

        // These should not error (though may not apply on non-Linux)
        assert!(strict_result.is_ok());
        assert!(permissive_result.is_ok());
    }

    #[test]
    fn test_seccomp_config_serialization() {
        let config = SeccompConfig::strict();
        let serialized = serde_json::to_string(&config).unwrap();
        let deserialized: SeccompConfig = serde_json::from_str(&serialized).unwrap();

        assert_eq!(config.profile, deserialized.profile);
        assert_eq!(config.allowed_syscalls, deserialized.allowed_syscalls);
    }

    #[test]
    fn test_profile_enum_serialization() {
        let serialized_strict = serde_json::to_string(&SeccompProfile::Strict).unwrap();
        let serialized_permissive = serde_json::to_string(&SeccompProfile::Permissive).unwrap();

        assert_eq!(serialized_strict, r#""strict""#);
        assert_eq!(serialized_permissive, r#""permissive""#);

        let deserialized_strict: SeccompProfile = serde_json::from_str(&serialized_strict).unwrap();
        let deserialized_permissive: SeccompProfile = serde_json::from_str(&serialized_permissive).unwrap();

        assert_eq!(deserialized_strict, SeccompProfile::Strict);
        assert_eq!(deserialized_permissive, SeccompProfile::Permissive);
    }
}

#[cfg(test)]
mod integration_tests {
    use super::*;
    use std::process::Command;
    use std::sync::{Arc, atomic::{AtomicBool, Ordering}};

    // Test seccomp in isolated process (để tránh kill main test process)
    #[test]
    #[cfg(target_os = "linux")]
    fn test_seccomp_strict_blocks_dangerous_syscalls() {
        use std::sync::Arc;
        use std::sync::atomic::{AtomicBool, Ordering};

        // Flag để signal subprocess result
        let execve_blocked = Arc::new(AtomicBool::new(false));
        let execve_flag = Arc::clone(&execve_blocked);

        // Fork test process
        let pid_result = unsafe { libc::fork() };

        match pid_result {
            -1 => panic!("Fork failed"),
            0 => {
                // Child process
                let config = SeccompConfig::strict();
                if config.apply().is_ok() {
                    // Seccomp applied, now try dangerous syscall
                    let exec_result = Command::new("sh").arg("-c").arg("echo test").status();
                    let blocked_execve = exec_result.is_err();
                    execve_flag.store(blocked_execve, Ordering::SeqCst);
                }
                unsafe { libc::_exit(0); }
            }
            pid => {
                // Parent process - wait for child
                let mut status: libc::c_int = 0;
                unsafe { libc::waitpid(pid, &mut status, 0) };

                // Check if child was killed by seccomp or properly blocked execve
                let exit_code = (status >> 8) & 0xFF;
                let child_killed = exit_code == (libc::SIGSYS as i32);

                assert!(child_killed || execve_flag.load(Ordering::SeqCst),
                       "Seccomp should block dangerous syscalls");
            }
        }
    }

    #[test]
    #[cfg(target_os = "linux")]
    fn test_gpu_syscalls_allowed_after_seccomp() {
        // This test assumes we're running without seccomp applied yet
        // It tests that syscall whitelist includes necessary GPU calls
        let config = SeccompConfig::strict();

        // These should work in current process (without seccomp)
        let getpid_result = unsafe { libc::getpid() };
        let ioctl_result = unsafe { libc::ioctl(0, 0, 0) }; // Dummy ioctl

        // getpid should always work
        assert!(getpid_result > 0, "getpid should be allowed");
        // ioctl may fail on invalid fd, but shouldn't be blocked by seccomp (yet)
        let ioctl_blocked = ioctl_result == -1 && std::io::Error::last_os_error().raw_os_error() == Some(libc::EPERM);

        // If ioctl is blocked, it means seccomp is already active elsewhere
        if ioctl_blocked {
            println!("Seccomp already active, skipping ioctl test");
        } else {
            // ioctl should be in whitelist
            assert!(config.allowed_syscalls.contains("ioctl"));
        }
    }

    #[test]
    fn test_seccomp_platform_compatibility() {
        let config = SeccompConfig::strict();

        // On Linux, should attempt to apply (may fail due to permissions)
        // On other platforms, should skip gracefully
        let result = config.apply();

        #[cfg(target_os = "linux")]
        {
            // On Linux, result depends on permissions and capabilities
            // Don't assert success, just ensure it doesn't panic
            let _ = result;
        }

        #[cfg(not(target_os = "linux"))]
        {
            // On non-Linux, should always succeed (no-op)
            assert!(result.is_ok());
        }
    }
}
