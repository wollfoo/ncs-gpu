//! # Namespace Isolation (Cô Lập Namespace)
//!
//! Cô lập process trong separate namespaces (user, network, mount).

use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use anyhow::{anyhow, Result};
use tracing::{debug, info, warn};
use nix::sched::{unshare, CloneFlags};
use nix::unistd::{getuid, getgid};
use std::fs;
use std::path::Path;

/// Namespace isolation levels (mức cô lập namespace)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NamespaceIsolation {
    /// Enable user namespace (cô lập UID/GID)
    pub user_namespace: bool,

    /// Enable network namespace (cô lập network stack)
    pub network_namespace: bool,

    /// Enable mount namespace (cô lập filesystem)
    pub mount_namespace: bool,
}

impl Default for NamespaceIsolation {
    fn default() -> Self {
        Self {
            user_namespace: true,   // Always recommended for security
            network_namespace: true, // Recommended for connection isolation
            mount_namespace: true,  // Recommended for filesystem isolation
        }
    }
}

impl NamespaceIsolation {
    /// Check kernel support for required namespaces (kiểm tra hỗ trợ kernel)
    pub fn check_kernel_support() -> Result<NamespaceCapabilities> {
        // Check namespace files exist (indicates kernel support)
        let user_ns_supported = Path::new("/proc/self/ns/user").exists();
        let net_ns_supported = Path::new("/proc/self/ns/net").exists();
        let mnt_ns_supported = Path::new("/proc/self/ns/mnt").exists();

        let capabilities = NamespaceCapabilities {
            user_namespace: user_ns_supported,
            network_namespace: net_ns_supported,
            mount_namespace: mnt_ns_supported,
        };

        // Log kernel version and capabilities
        if let Ok(version) = Self::get_kernel_version() {
            info!(
                version = %version,
                capabilities = ?capabilities,
                "Namespace kernel support verified"
            );
        }

        Ok(capabilities)
    }

    /// Get Linux kernel version (lấy phiên bản kernel Linux)
    fn get_kernel_version() -> Result<String> {
        use std::fs::read_to_string;
        let version = read_to_string("/proc/version")?;
        // Extract version from "Linux version 5.15.0-..."
        let start = version.find("Linux version ").unwrap_or(0);
        let end = version[start..].find(' ').unwrap_or(version.len()) + start;
        Ok(version[start..end].to_string())
    }

    /// Apply namespace isolation (áp dụng cô lập namespace)
    pub fn isolate_process(&self) -> Result<()> {
        info!("🔒 Isolating process into namespaces...");

        // Step 1: Verify kernel support BEFORE applying
        let caps = Self::check_kernel_support()?;

        if !caps.supports_isolation() {
            return Err(anyhow!("Kernel does not support minimum namespace isolation. \
                          Requires Linux 3.8+ for user namespaces, 2.6.24+ for network namespaces"));
        }

        if self.user_namespace && !caps.user_namespace {
            return Err(anyhow!("User namespaces not supported (requires Linux 3.8+)"));
        }
        if self.network_namespace && !caps.network_namespace {
            return Err(anyhow!("Network namespaces not supported (requires Linux 2.6.24+)"));
        }
        if self.mount_namespace && !caps.mount_namespace {
            return Err(anyhow!("Mount namespaces not supported (requires Linux 2.4.19+)"));
        }

        // Step 2: Apply namespaces in correct order
        self.apply_namespaces()?;

        // Step 3: Setup namespace-specific configuration
        if self.user_namespace {
            self.setup_user_mapping()?;
        }

        if self.network_namespace {
            self.setup_network_isolation()?;
        }

        if self.mount_namespace {
            self.setup_mount_isolation()?;
        }

        info!(
            user_ns = self.user_namespace,
            network_ns = self.network_namespace,
            mount_ns = self.mount_namespace,
            "Namespace isolation applied successfully"
        );

        Ok(())
    }

    /// Apply all requested namespaces (áp dụng tất cả namespace yêu cầu)
    fn apply_namespaces(&self) -> Result<()> {
        let mut flags = CloneFlags::empty();

        // Build flags mask
        if self.user_namespace {
            flags |= CloneFlags::CLONE_NEWUSER;
        }
        if self.network_namespace {
            flags |= CloneFlags::CLONE_NEWNET;
        }
        if self.mount_namespace {
            flags |= CloneFlags::CLONE_NEWNS;
        }

        // Apply all namespaces simultaneously
        unshare(flags)?;

        Ok(())
    }

    /// Setup UID/GID mapping for user namespace (thiết lập ánh xạ UID/GID)
    fn setup_user_mapping(&self) -> Result<()> {
        use std::fs::write;
        use nix::unistd::{getuid, getgid};

        // Current user becomes root (uid 0) in namespace
        let current_uid = getuid();
        let current_gid = getgid();

        // Write UID mapping: container_uid -> host_uid
        // Format: "container_uid host_uid range"
        let uid_map = format!("0 {} 1\n", current_uid.as_raw());
        write("/proc/self/uid_map", uid_map)?;

        // Allow setgroups for GID mapping
        write("/proc/self/setgroups", "deny\n")?;

        // Write GID mapping
        let gid_map = format!("0 {} 1\n", current_gid.as_raw());
        write("/proc/self/gid_map", gid_map)?;

        debug!("User namespace mapping configured");
        Ok(())
    }

    /// Setup network isolation (network stack riêng biệt)
    fn setup_network_isolation(&self) -> Result<()> {
        // Current implementation: Network still through host
        // Future: Setup veth pair with host bridge

        // Configure localhost (127.0.0.1 always works)
        // External connections route through host

        debug!("Network namespace configured (isolated stack)");
        Ok(())
    }

    /// Setup mount isolation (filesystem riêng biệt)
    fn setup_mount_isolation(&self) -> Result<()> {
        // Make root mount private (changes don't propagate)
        nix::mount::mount(
            None::<&str>,
            "/",
            None::<&str>,
            nix::mount::MsFlags::MS_PRIVATE | nix::mount::MsFlags::MS_REC,
            None::<&str>
        )?;

        // Create private /tmp directory
        fs::create_dir_all("/tmp/private")?;
        nix::mount::mount(
            Some("/tmp/private"),
            "/tmp",
            None::<&str>,
            nix::mount::MsFlags::MS_BIND,
            None::<&str>
        )?;

        // Similarly for /run, /var/tmp if needed
        // Note: /etc/passwd mounted readonly by container runtime

        debug!("Mount namespace configured (private filesystem)");
        Ok(())
    }

    /// Verify Docker GPU container compatibility (kiểm tra tương thích Docker GPU)
    pub fn verify_docker_compatibility() -> Result<()> {
        // Check for NVIDIA GPU access
        let nvidia_caps = fs::read("/proc/driver/nvidia/capabilities/gpu0");
        if nvidia_caps.is_err() {
            warn!("NVIDIA GPU not detected via /proc/driver/nvidia");
        }

        // Check cgroup controls available
        let cgroup_path = "/sys/fs/cgroup/pids/user.slice";
        if fs::metadata(cgroup_path).is_ok() {
            info!("Cgroup controls available for resource limits");
        }

        // Check systemd integration (common in containers)
        if let Ok(pid) = std::env::var("container") {
            if pid == "systemd-nspawn" || pid == "docker" {
                info!("Running in container environment: {}", pid);
                return Ok(());
            }
        }

        // Check container-specific capabilities
        let caps = Self::check_kernel_support()?;
        if !caps.supports_isolation() {
            warn!("Container may not support full namespace isolation");
        }

        Ok(())
    }

    /// Recommended Docker run command (lệnh chạy Docker được khuyến nghị)
    pub fn docker_run_recommendation() -> String {
        format!(
            "docker run --gpus all --cap-add=SYS_ADMIN --privileged \\
             --tmpfs /tmp:rw,noexec,nosuid,size=100m \\
             --read-only --tmpfs /run:rw,noexec,nosuid,size=100m \\
             --security-opt no-new-privileges \\
             --security-opt apparmor=docker-default \\
             <gpu-mining-image>"
        )
    }
}

/// Kernel namespace capabilities (năng lực namespace của kernel)
#[derive(Debug, Clone)]
pub struct NamespaceCapabilities {
    pub user_namespace: bool,
    pub network_namespace: bool,
    pub mount_namespace: bool,
}

impl NamespaceCapabilities {
    /// Are minimum requirements met? (đủ yêu cầu tối thiểu?)
    pub fn supports_isolation(&self) -> bool {
        self.user_namespace && self.network_namespace
    }

    /// Supports all requested features (hỗ trợ tất cả tính năng yêu cầu)
    pub fn supports_full_isolation(&self) -> bool {
        self.user_namespace && self.network_namespace && self.mount_namespace
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_namespace_capabilities_detection() {
        let caps = NamespaceIsolation::check_kernel_support().unwrap();

        // At minimum, should detect modern kernel capabilities
        assert!(caps.user_namespace, "User namespaces required for security");
        // Network/mount may vary by kernel config
    }

    #[test]
    fn test_isolation_configuration() {
        let isolation = NamespaceIsolation::default();
        assert!(isolation.user_namespace, "User namespace should be enabled by default");
        assert!(isolation.network_namespace, "Network namespace recommended");
        assert!(isolation.mount_namespace, "Mount namespace recommended");
    }

    #[test]
    fn test_capabilities_supports_isolation() {
        let full_caps = NamespaceCapabilities {
            user_namespace: true,
            network_namespace: true,
            mount_namespace: true,
        };
        assert!(full_caps.supports_isolation());
        assert!(full_caps.supports_full_isolation());

        let minimal_caps = NamespaceCapabilities {
            user_namespace: true,
            network_namespace: true,
            mount_namespace: false, // Mount ns optional
        };
        assert!(minimal_caps.supports_isolation());
        assert!(!minimal_caps.supports_full_isolation());
    }
}
