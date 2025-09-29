//! # OPUS-GPU Security Module
//!
//! Comprehensive security hardening module providing:
//! - Memory protection with secure allocation and zeroing
//! - Process isolation with sandboxing and capability dropping
//! - Network security with TLS/mTLS and certificate pinning
//! - Authentication with JWT/OAuth2 and API key management
//! - Encryption with AES-256-GCM and ChaCha20-Poly1305
//! - Anti-tampering with integrity checks and binary verification

pub mod memory;
pub mod process;
pub mod network;
pub mod auth;
pub mod crypto;
pub mod integrity;
pub mod config;

pub use memory::*;
pub use process::*;
pub use network::*;
pub use auth::*;
pub use crypto::*;
pub use integrity::*;
pub use config::*;

use anyhow::Result;
use tracing::{info, warn, error};

/// Security hardening configuration
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct SecurityConfig {
    /// Enable memory protection features
    pub memory_protection: bool,
    /// Enable process isolation features
    pub process_isolation: bool,
    /// Enable network security features
    pub network_security: bool,
    /// Enable anti-tampering features
    pub anti_tampering: bool,
    /// Strict mode enables all security features
    pub strict_mode: bool,
    /// Security log level
    pub log_level: String,
}

impl Default for SecurityConfig {
    fn default() -> Self {
        Self {
            memory_protection: true,
            process_isolation: true,
            network_security: true,
            anti_tampering: true,
            strict_mode: false,
            log_level: "INFO".to_string(),
        }
    }
}

/// Main security hardening manager
pub struct SecurityManager {
    config: SecurityConfig,
    memory_manager: Option<memory::MemoryManager>,
    process_manager: Option<process::ProcessManager>,
    network_manager: Option<network::NetworkManager>,
    integrity_manager: Option<integrity::IntegrityManager>,
}

impl SecurityManager {
    /// Create new security manager with configuration
    pub fn new(config: SecurityConfig) -> Result<Self> {
        info!("Initializing OPUS-GPU Security Manager");

        let mut manager = Self {
            config: config.clone(),
            memory_manager: None,
            process_manager: None,
            network_manager: None,
            integrity_manager: None,
        };

        // Initialize components based on configuration
        if config.memory_protection || config.strict_mode {
            manager.memory_manager = Some(memory::MemoryManager::new()?);
            info!("Memory protection enabled");
        }

        if config.process_isolation || config.strict_mode {
            manager.process_manager = Some(process::ProcessManager::new()?);
            info!("Process isolation enabled");
        }

        if config.network_security || config.strict_mode {
            manager.network_manager = Some(network::NetworkManager::new()?);
            info!("Network security enabled");
        }

        if config.anti_tampering || config.strict_mode {
            manager.integrity_manager = Some(integrity::IntegrityManager::new()?);
            info!("Anti-tampering protection enabled");
        }

        Ok(manager)
    }

    /// Initialize all security hardening features
    pub async fn initialize(&mut self) -> Result<()> {
        info!("Starting security hardening initialization");

        // Memory protection initialization
        if let Some(ref mut memory_mgr) = self.memory_manager {
            memory_mgr.initialize().await?;
            info!("Memory protection initialized");
        }

        // Process isolation initialization
        if let Some(ref mut process_mgr) = self.process_manager {
            process_mgr.initialize().await?;
            info!("Process isolation initialized");
        }

        // Network security initialization
        if let Some(ref mut network_mgr) = self.network_manager {
            network_mgr.initialize().await?;
            info!("Network security initialized");
        }

        // Anti-tampering initialization
        if let Some(ref mut integrity_mgr) = self.integrity_manager {
            integrity_mgr.initialize().await?;
            info!("Anti-tampering protection initialized");
        }

        info!("Security hardening initialization completed successfully");
        Ok(())
    }

    /// Perform security health check
    pub async fn health_check(&self) -> Result<SecurityStatus> {
        let mut status = SecurityStatus::default();

        // Check memory protection
        if let Some(ref memory_mgr) = self.memory_manager {
            status.memory_protection = memory_mgr.health_check().await?;
        }

        // Check process isolation
        if let Some(ref process_mgr) = self.process_manager {
            status.process_isolation = process_mgr.health_check().await?;
        }

        // Check network security
        if let Some(ref network_mgr) = self.network_manager {
            status.network_security = network_mgr.health_check().await?;
        }

        // Check integrity protection
        if let Some(ref integrity_mgr) = self.integrity_manager {
            status.integrity_protection = integrity_mgr.health_check().await?;
        }

        Ok(status)
    }

    /// Shutdown security manager gracefully
    pub async fn shutdown(&mut self) -> Result<()> {
        info!("Shutting down security manager");

        if let Some(ref mut integrity_mgr) = self.integrity_manager {
            integrity_mgr.shutdown().await?;
        }

        if let Some(ref mut network_mgr) = self.network_manager {
            network_mgr.shutdown().await?;
        }

        if let Some(ref mut process_mgr) = self.process_manager {
            process_mgr.shutdown().await?;
        }

        if let Some(ref mut memory_mgr) = self.memory_manager {
            memory_mgr.shutdown().await?;
        }

        info!("Security manager shutdown completed");
        Ok(())
    }
}

/// Security system status
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct SecurityStatus {
    pub memory_protection: bool,
    pub process_isolation: bool,
    pub network_security: bool,
    pub integrity_protection: bool,
    pub overall_status: bool,
}

impl Default for SecurityStatus {
    fn default() -> Self {
        Self {
            memory_protection: false,
            process_isolation: false,
            network_security: false,
            integrity_protection: false,
            overall_status: false,
        }
    }
}

impl SecurityStatus {
    pub fn is_healthy(&self) -> bool {
        self.memory_protection &&
        self.process_isolation &&
        self.network_security &&
        self.integrity_protection
    }
}

/// Security error types
#[derive(thiserror::Error, Debug)]
pub enum SecurityError {
    #[error("Memory protection error: {0}")]
    MemoryProtection(String),

    #[error("Process isolation error: {0}")]
    ProcessIsolation(String),

    #[error("Network security error: {0}")]
    NetworkSecurity(String),

    #[error("Integrity check failed: {0}")]
    IntegrityCheck(String),

    #[error("Authentication failed: {0}")]
    Authentication(String),

    #[error("Encryption error: {0}")]
    Encryption(String),

    #[error("Configuration error: {0}")]
    Configuration(String),
}

pub type SecurityResult<T> = Result<T, SecurityError>;