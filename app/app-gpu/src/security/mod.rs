/*!
 * Security Module - Cryptographic Protection & Runtime Hardening
 *
 * Cung cấp các tính năng bảo mật:
 * - Encrypted configuration với age encryption
 * - Binary signature verification với GPG
 * - Linux capabilities dropping và seccomp filtering
 */

pub mod secrets;
pub mod verification;
pub mod capabilities;

pub use secrets::SecretStore;
pub use verification::verify_binary_signature;
pub use capabilities::{drop_capabilities, apply_seccomp_filter};

use thiserror::Error;

#[derive(Debug, Error)]
pub enum SecurityError {
    #[error("Age encryption error: {0}")]
    AgeError(#[from] age::DecryptError),

    #[error("Invalid signature for binary: {0}")]
    InvalidSignature(String),

    #[error("Capability operation failed: {0}")]
    CapabilityError(String),

    #[error("Seccomp filter application failed: {0}")]
    SeccompError(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Keyring error: {0}")]
    KeyringError(String),

    #[error("TOML parsing error: {0}")]
    TomlError(#[from] toml::de::Error),
}

pub type Result<T> = std::result::Result<T, SecurityError>;
