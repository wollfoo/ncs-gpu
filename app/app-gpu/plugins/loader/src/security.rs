//! Plugin security and sandboxing implementation

use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use uuid::Uuid;

/// Security policy for plugin execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityPolicy {
    /// Allow network access
    pub allow_network: bool,
    /// Allow file system access
    pub allow_filesystem: bool,
    /// Allowed file paths (if filesystem access is enabled)
    pub allowed_paths: Vec<PathBuf>,
    /// Allow system calls
    pub allow_syscalls: bool,
    /// Allowed syscalls (if syscall access is enabled)
    pub allowed_syscalls: Vec<String>,
    /// Allow process creation
    pub allow_process_creation: bool,
    /// Maximum memory usage (bytes)
    pub max_memory: Option<u64>,
    /// Maximum CPU time (seconds)
    pub max_cpu_time: Option<u64>,
    /// Allow dynamic library loading
    pub allow_dynamic_loading: bool,
    /// Allowed network hosts (if network access is enabled)
    pub allowed_hosts: Vec<String>,
    /// Allowed network ports (if network access is enabled)
    pub allowed_ports: Vec<u16>,
    /// Enable audit logging
    pub enable_audit: bool,
    /// Audit log level
    pub audit_level: AuditLevel,
}

/// Audit logging levels
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum AuditLevel {
    None,
    Basic,
    Detailed,
    Verbose,
}

/// Security violation types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SecurityViolation {
    /// Unauthorized network access
    UnauthorizedNetworkAccess {
        host: String,
        port: u16,
    },
    /// Unauthorized file access
    UnauthorizedFileAccess {
        path: PathBuf,
        operation: String,
    },
    /// Unauthorized syscall
    UnauthorizedSyscall {
        syscall: String,
    },
    /// Memory limit exceeded
    MemoryLimitExceeded {
        limit: u64,
        actual: u64,
    },
    /// CPU time limit exceeded
    CpuTimeLimitExceeded {
        limit: u64,
        actual: u64,
    },
    /// Unauthorized process creation
    UnauthorizedProcessCreation {
        command: String,
    },
    /// Unauthorized dynamic loading
    UnauthorizedDynamicLoading {
        library: String,
    },
    /// Malicious behavior detected
    MaliciousBehavior {
        description: String,
        evidence: String,
    },
}

/// Security audit log entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditLogEntry {
    /// Log entry ID
    pub id: Uuid,
    /// Plugin ID
    pub plugin_id: Uuid,
    /// Timestamp
    pub timestamp: DateTime<Utc>,
    /// Event type
    pub event_type: String,
    /// Event details
    pub details: HashMap<String, String>,
    /// Severity level
    pub severity: AuditSeverity,
    /// Whether this was allowed or blocked
    pub allowed: bool,
}

/// Audit severity levels
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum AuditSeverity {
    Info,
    Warning,
    Error,
    Critical,
}

/// Plugin sandbox implementation
pub struct PluginSandbox {
    plugin_id: Uuid,
    policy: SecurityPolicy,
    audit_log: Vec<AuditLogEntry>,
    violations: Vec<SecurityViolation>,
    start_time: DateTime<Utc>,
}

impl PluginSandbox {
    /// Create a new plugin sandbox
    pub fn new(plugin_id: Uuid, policy: SecurityPolicy) -> Result<Self> {
        Ok(Self {
            plugin_id,
            policy,
            audit_log: Vec::new(),
            violations: Vec::new(),
            start_time: Utc::now(),
        })
    }

    /// Check if network access is allowed
    pub fn check_network_access(&mut self, host: &str, port: u16) -> Result<bool> {
        let allowed = self.policy.allow_network &&
            (self.policy.allowed_hosts.is_empty() ||
             self.policy.allowed_hosts.iter().any(|h| h == host || host.contains(h))) &&
            (self.policy.allowed_ports.is_empty() ||
             self.policy.allowed_ports.contains(&port));

        self.log_audit_event(
            \"network_access\",
            &[(\"host\".to_string(), host.to_string()),
              (\"port\".to_string(), port.to_string())],
            if allowed { AuditSeverity::Info } else { AuditSeverity::Warning },
            allowed,
        );

        if !allowed {
            let violation = SecurityViolation::UnauthorizedNetworkAccess {
                host: host.to_string(),
                port,
            };
            self.violations.push(violation);
        }

        Ok(allowed)
    }

    /// Check if file access is allowed
    pub fn check_file_access(&mut self, path: &std::path::Path, operation: &str) -> Result<bool> {
        let allowed = self.policy.allow_filesystem &&
            (self.policy.allowed_paths.is_empty() ||
             self.policy.allowed_paths.iter().any(|allowed_path| {
                 path.starts_with(allowed_path)
             }));

        self.log_audit_event(
            \"file_access\",
            &[(\"path\".to_string(), path.to_string_lossy().to_string()),
              (\"operation\".to_string(), operation.to_string())],
            if allowed { AuditSeverity::Info } else { AuditSeverity::Warning },
            allowed,
        );

        if !allowed {
            let violation = SecurityViolation::UnauthorizedFileAccess {
                path: path.to_path_buf(),
                operation: operation.to_string(),
            };
            self.violations.push(violation);
        }

        Ok(allowed)
    }

    /// Check if syscall is allowed
    pub fn check_syscall(&mut self, syscall: &str) -> Result<bool> {
        let allowed = self.policy.allow_syscalls &&
            (self.policy.allowed_syscalls.is_empty() ||
             self.policy.allowed_syscalls.contains(&syscall.to_string()));

        self.log_audit_event(
            \"syscall\",
            &[(\"syscall\".to_string(), syscall.to_string())],
            if allowed { AuditSeverity::Info } else { AuditSeverity::Error },
            allowed,
        );

        if !allowed {
            let violation = SecurityViolation::UnauthorizedSyscall {
                syscall: syscall.to_string(),
            };
            self.violations.push(violation);
        }

        Ok(allowed)
    }

    /// Check if process creation is allowed
    pub fn check_process_creation(&mut self, command: &str) -> Result<bool> {
        let allowed = self.policy.allow_process_creation;

        self.log_audit_event(
            \"process_creation\",
            &[(\"command\".to_string(), command.to_string())],
            if allowed { AuditSeverity::Info } else { AuditSeverity::Error },
            allowed,
        );

        if !allowed {
            let violation = SecurityViolation::UnauthorizedProcessCreation {
                command: command.to_string(),
            };
            self.violations.push(violation);
        }

        Ok(allowed)
    }

    /// Check if dynamic library loading is allowed
    pub fn check_dynamic_loading(&mut self, library: &str) -> Result<bool> {
        let allowed = self.policy.allow_dynamic_loading;

        self.log_audit_event(
            \"dynamic_loading\",
            &[(\"library\".to_string(), library.to_string())],
            if allowed { AuditSeverity::Info } else { AuditSeverity::Warning },
            allowed,
        );

        if !allowed {
            let violation = SecurityViolation::UnauthorizedDynamicLoading {
                library: library.to_string(),
            };
            self.violations.push(violation);
        }

        Ok(allowed)
    }

    /// Check memory usage
    pub fn check_memory_usage(&mut self, current_memory: u64) -> Result<bool> {
        if let Some(limit) = self.policy.max_memory {
            let allowed = current_memory <= limit;

            if !allowed {
                self.log_audit_event(
                    \"memory_limit_exceeded\",
                    &[(\"limit\".to_string(), limit.to_string()),
                      (\"actual\".to_string(), current_memory.to_string())],
                    AuditSeverity::Critical,
                    false,
                );

                let violation = SecurityViolation::MemoryLimitExceeded {
                    limit,
                    actual: current_memory,
                };
                self.violations.push(violation);
            }

            Ok(allowed)
        } else {
            Ok(true)
        }
    }

    /// Check CPU time usage
    pub fn check_cpu_time(&mut self, cpu_time_seconds: u64) -> Result<bool> {
        if let Some(limit) = self.policy.max_cpu_time {
            let allowed = cpu_time_seconds <= limit;

            if !allowed {
                self.log_audit_event(
                    \"cpu_time_limit_exceeded\",
                    &[(\"limit\".to_string(), limit.to_string()),
                      (\"actual\".to_string(), cpu_time_seconds.to_string())],
                    AuditSeverity::Critical,
                    false,
                );

                let violation = SecurityViolation::CpuTimeLimitExceeded {
                    limit,
                    actual: cpu_time_seconds,
                };
                self.violations.push(violation);
            }

            Ok(allowed)
        } else {
            Ok(true)
        }
    }

    /// Report malicious behavior
    pub fn report_malicious_behavior(&mut self, description: &str, evidence: &str) {
        self.log_audit_event(
            \"malicious_behavior\",
            &[(\"description\".to_string(), description.to_string()),
              (\"evidence\".to_string(), evidence.to_string())],
            AuditSeverity::Critical,
            false,
        );

        let violation = SecurityViolation::MaliciousBehavior {
            description: description.to_string(),
            evidence: evidence.to_string(),
        };
        self.violations.push(violation);
    }

    /// Get all security violations
    pub fn get_violations(&self) -> &[SecurityViolation] {
        &self.violations
    }

    /// Get audit log
    pub fn get_audit_log(&self) -> &[AuditLogEntry] {
        &self.audit_log
    }

    /// Clear violations (after handling)
    pub fn clear_violations(&mut self) {
        self.violations.clear();
    }

    /// Update security policy
    pub fn update_policy(&mut self, policy: SecurityPolicy) -> Result<()> {
        self.log_audit_event(
            \"policy_update\",
            &[(\"old_policy\".to_string(), serde_json::to_string(&self.policy)?),
              (\"new_policy\".to_string(), serde_json::to_string(&policy)?)],
            AuditSeverity::Info,
            true,
        );

        self.policy = policy;
        Ok(())
    }

    /// Get security statistics
    pub fn get_security_stats(&self) -> SecurityStats {
        let mut violation_counts = HashMap::new();

        for violation in &self.violations {
            let violation_type = match violation {
                SecurityViolation::UnauthorizedNetworkAccess { .. } => \"network\",
                SecurityViolation::UnauthorizedFileAccess { .. } => \"filesystem\",
                SecurityViolation::UnauthorizedSyscall { .. } => \"syscall\",
                SecurityViolation::MemoryLimitExceeded { .. } => \"memory\",
                SecurityViolation::CpuTimeLimitExceeded { .. } => \"cpu\",
                SecurityViolation::UnauthorizedProcessCreation { .. } => \"process\",
                SecurityViolation::UnauthorizedDynamicLoading { .. } => \"dynamic_loading\",
                SecurityViolation::MaliciousBehavior { .. } => \"malicious\",
            };

            *violation_counts.entry(violation_type.to_string()).or_insert(0) += 1;
        }

        SecurityStats {
            plugin_id: self.plugin_id,
            total_violations: self.violations.len(),
            violation_counts,
            audit_entries: self.audit_log.len(),
            uptime: Utc::now().signed_duration_since(self.start_time).to_std().unwrap_or_default(),
            policy_version: serde_json::to_string(&self.policy).unwrap_or_default(),
        }
    }

    /// Log audit event
    fn log_audit_event(
        &mut self,
        event_type: &str,
        details: &[(String, String)],
        severity: AuditSeverity,
        allowed: bool,
    ) {
        if !self.policy.enable_audit ||
           !self.should_log_severity(&severity) {
            return;
        }

        let entry = AuditLogEntry {
            id: Uuid::new_v4(),
            plugin_id: self.plugin_id,
            timestamp: Utc::now(),
            event_type: event_type.to_string(),
            details: details.iter().cloned().collect(),
            severity,
            allowed,
        };

        self.audit_log.push(entry);

        // Keep audit log size manageable (keep last 1000 entries)
        if self.audit_log.len() > 1000 {
            self.audit_log.drain(0..self.audit_log.len() - 1000);
        }
    }

    /// Check if severity level should be logged
    fn should_log_severity(&self, severity: &AuditSeverity) -> bool {
        match self.policy.audit_level {
            AuditLevel::None => false,
            AuditLevel::Basic => matches!(severity, AuditSeverity::Error | AuditSeverity::Critical),
            AuditLevel::Detailed => !matches!(severity, AuditSeverity::Info),
            AuditLevel::Verbose => true,
        }
    }

    /// Cleanup sandbox resources
    pub async fn cleanup(&self) -> Result<()> {
        // TODO: Implement actual sandbox cleanup
        // This would involve:
        // - Terminating any spawned processes
        // - Cleaning up temporary files
        // - Releasing network resources
        // - Clearing memory mappings
        // - etc.

        tracing::info!(\"🧹 Cleaning up security sandbox for plugin {}\", self.plugin_id);
        Ok(())
    }
}

/// Security statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityStats {
    /// Plugin ID
    pub plugin_id: Uuid,
    /// Total number of violations
    pub total_violations: usize,
    /// Violation counts by type
    pub violation_counts: HashMap<String, usize>,
    /// Number of audit log entries
    pub audit_entries: usize,
    /// Plugin uptime
    pub uptime: std::time::Duration,
    /// Security policy version
    pub policy_version: String,
}

impl Default for SecurityPolicy {
    fn default() -> Self {
        Self {
            allow_network: false,
            allow_filesystem: false,
            allowed_paths: vec![],
            allow_syscalls: false,
            allowed_syscalls: vec![],
            allow_process_creation: false,
            max_memory: Some(512 * 1024 * 1024), // 512MB default
            max_cpu_time: Some(60), // 60 seconds default
            allow_dynamic_loading: false,
            allowed_hosts: vec![],
            allowed_ports: vec![],
            enable_audit: true,
            audit_level: AuditLevel::Basic,
        }
    }
}

impl std::fmt::Display for SecurityViolation {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SecurityViolation::UnauthorizedNetworkAccess { host, port } => {
                write!(f, \"Unauthorized network access to {}:{}\", host, port)
            }
            SecurityViolation::UnauthorizedFileAccess { path, operation } => {
                write!(f, \"Unauthorized file access: {} on {:?}\", operation, path)
            }
            SecurityViolation::UnauthorizedSyscall { syscall } => {
                write!(f, \"Unauthorized syscall: {}\", syscall)
            }
            SecurityViolation::MemoryLimitExceeded { limit, actual } => {
                write!(f, \"Memory limit exceeded: {} > {}\", actual, limit)
            }
            SecurityViolation::CpuTimeLimitExceeded { limit, actual } => {
                write!(f, \"CPU time limit exceeded: {} > {}\", actual, limit)
            }
            SecurityViolation::UnauthorizedProcessCreation { command } => {
                write!(f, \"Unauthorized process creation: {}\", command)
            }
            SecurityViolation::UnauthorizedDynamicLoading { library } => {
                write!(f, \"Unauthorized dynamic loading: {}\", library)
            }
            SecurityViolation::MaliciousBehavior { description, .. } => {
                write!(f, \"Malicious behavior detected: {}\", description)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[test]
    fn test_security_policy_default() {
        let policy = SecurityPolicy::default();

        assert!(!policy.allow_network);
        assert!(!policy.allow_filesystem);
        assert!(!policy.allow_syscalls);
        assert!(!policy.allow_process_creation);
        assert!(!policy.allow_dynamic_loading);
        assert!(policy.enable_audit);
        assert_eq!(policy.audit_level, AuditLevel::Basic);
    }

    #[test]
    fn test_plugin_sandbox_creation() {
        let plugin_id = Uuid::new_v4();
        let policy = SecurityPolicy::default();
        let sandbox = PluginSandbox::new(plugin_id, policy).unwrap();

        assert_eq!(sandbox.plugin_id, plugin_id);
        assert_eq!(sandbox.violations.len(), 0);
        assert_eq!(sandbox.audit_log.len(), 0);
    }

    #[test]
    fn test_network_access_check() {
        let plugin_id = Uuid::new_v4();
        let mut policy = SecurityPolicy::default();
        policy.allow_network = true;
        policy.allowed_hosts = vec![\"example.com\".to_string()];
        policy.allowed_ports = vec![80, 443];

        let mut sandbox = PluginSandbox::new(plugin_id, policy).unwrap();

        // Allowed access
        assert!(sandbox.check_network_access(\"example.com\", 80).unwrap());
        assert_eq!(sandbox.violations.len(), 0);

        // Disallowed host
        assert!(!sandbox.check_network_access(\"malicious.com\", 80).unwrap());
        assert_eq!(sandbox.violations.len(), 1);

        // Disallowed port
        assert!(!sandbox.check_network_access(\"example.com\", 22).unwrap());
        assert_eq!(sandbox.violations.len(), 2);
    }

    #[test]
    fn test_file_access_check() {
        let plugin_id = Uuid::new_v4();
        let mut policy = SecurityPolicy::default();
        policy.allow_filesystem = true;
        policy.allowed_paths = vec![PathBuf::from(\"/tmp\"), PathBuf::from(\"/var/log\")];

        let mut sandbox = PluginSandbox::new(plugin_id, policy).unwrap();

        // Allowed access
        assert!(sandbox.check_file_access(Path::new(\"/tmp/test.txt\"), \"read\").unwrap());
        assert_eq!(sandbox.violations.len(), 0);

        // Disallowed path
        assert!(!sandbox.check_file_access(Path::new(\"/etc/passwd\"), \"read\").unwrap());
        assert_eq!(sandbox.violations.len(), 1);
    }

    #[test]
    fn test_memory_limit_check() {
        let plugin_id = Uuid::new_v4();
        let mut policy = SecurityPolicy::default();
        policy.max_memory = Some(1024 * 1024); // 1MB

        let mut sandbox = PluginSandbox::new(plugin_id, policy).unwrap();

        // Within limit
        assert!(sandbox.check_memory_usage(500 * 1024).unwrap());
        assert_eq!(sandbox.violations.len(), 0);

        // Exceeds limit
        assert!(!sandbox.check_memory_usage(2 * 1024 * 1024).unwrap());
        assert_eq!(sandbox.violations.len(), 1);
    }

    #[test]
    fn test_security_stats() {
        let plugin_id = Uuid::new_v4();
        let policy = SecurityPolicy::default();
        let mut sandbox = PluginSandbox::new(plugin_id, policy).unwrap();

        // Generate some violations
        sandbox.check_network_access(\"malicious.com\", 80).unwrap();
        sandbox.check_file_access(Path::new(\"/etc/passwd\"), \"read\").unwrap();

        let stats = sandbox.get_security_stats();
        assert_eq!(stats.plugin_id, plugin_id);
        assert_eq!(stats.total_violations, 2);
        assert!(stats.violation_counts.contains_key(\"network\"));
        assert!(stats.violation_counts.contains_key(\"filesystem\"));
    }
}