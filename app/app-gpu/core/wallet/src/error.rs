//! Error types and handling for wallet operations

use thiserror::Error;

/// Main wallet error type with comprehensive error categories
#[derive(Error, Debug, Clone)]
pub enum WalletError {
    // Cryptography Errors
    #[error("Cryptographic operation failed: {message}")]
    CryptographyError { message: String },

    #[error("Invalid private key format: {reason}")]
    InvalidPrivateKey { reason: String },

    #[error("Invalid public key format: {reason}")]
    InvalidPublicKey { reason: String },

    #[error("Invalid signature: {reason}")]
    InvalidSignature { reason: String },

    #[error("Key derivation failed: {reason}")]
    KeyDerivationError { reason: String },

    // Mnemonic & Seed Errors
    #[error("Invalid mnemonic phrase: {reason}")]
    InvalidMnemonic { reason: String },

    #[error("Invalid seed: {reason}")]
    InvalidSeed { reason: String },

    #[error("Mnemonic generation failed: {reason}")]
    MnemonicGenerationError { reason: String },

    // Wallet Management Errors
    #[error("Wallet not found: {wallet_id}")]
    WalletNotFound { wallet_id: String },

    #[error("Wallet already exists: {name}")]
    WalletAlreadyExists { name: String },

    #[error("Invalid wallet password")]
    InvalidPassword,

    #[error("Wallet is locked")]
    WalletLocked,

    #[error("Wallet corruption detected: {reason}")]
    WalletCorruption { reason: String },

    #[error("Invalid wallet format: {reason}")]
    InvalidWalletFormat { reason: String },

    // Address & Transaction Errors
    #[error("Invalid address format: {address}")]
    InvalidAddress { address: String },

    #[error("Invalid transaction format: {reason}")]
    InvalidTransaction { reason: String },

    #[error("Transaction signing failed: {reason}")]
    TransactionSigningError { reason: String },

    #[error("Insufficient funds: required {required}, available {available}")]
    InsufficientFunds { required: u64, available: u64 },

    #[error("Invalid fee: {fee}")]
    InvalidFee { fee: u64 },

    // Coin Type Errors
    #[error("Unsupported coin type: {coin_type}")]
    UnsupportedCoinType { coin_type: String },

    #[error("Invalid derivation path: {path}")]
    InvalidDerivationPath { path: String },

    // Storage Errors
    #[error("Storage error: {message}")]
    StorageError { message: String },

    #[error("Database error: {message}")]
    DatabaseError { message: String },

    #[error("Serialization error: {message}")]
    SerializationError { message: String },

    #[error("Deserialization error: {message}")]
    DeserializationError { message: String },

    // Security Errors
    #[error("Encryption failed: {reason}")]
    EncryptionError { reason: String },

    #[error("Decryption failed: {reason}")]
    DecryptionError { reason: String },

    #[error("Authentication failed: {reason}")]
    AuthenticationError { reason: String },

    #[error("Security policy violation: {reason}")]
    SecurityPolicyViolation { reason: String },

    // Hardware Wallet Errors
    #[cfg(feature = "hardware-wallet")]
    #[error("Hardware wallet error: {message}")]
    HardwareWalletError { message: String },

    #[cfg(feature = "hardware-wallet")]
    #[error("Hardware wallet not connected")]
    HardwareWalletNotConnected,

    #[cfg(feature = "hardware-wallet")]
    #[error("Hardware wallet operation cancelled")]
    HardwareWalletCancelled,

    // Multi-signature Errors
    #[error("Multi-signature error: {message}")]
    MultiSignatureError { message: String },

    #[error("Insufficient signatures: required {required}, provided {provided}")]
    InsufficientSignatures { required: usize, provided: usize },

    #[error("Invalid signature threshold: {threshold}")]
    InvalidSignatureThreshold { threshold: usize },

    // Network & Communication Errors
    #[error("Network error: {message}")]
    NetworkError { message: String },

    #[error("Timeout error: operation timed out after {seconds} seconds")]
    TimeoutError { seconds: u64 },

    #[error("Rate limit exceeded: {message}")]
    RateLimitError { message: String },

    // Configuration Errors
    #[error("Invalid configuration: {field} = {value}")]
    InvalidConfiguration { field: String, value: String },

    #[error("Missing required configuration: {field}")]
    MissingConfiguration { field: String },

    // General Errors
    #[error("Invalid input: {message}")]
    InvalidInput { message: String },

    #[error("Operation not supported: {operation}")]
    OperationNotSupported { operation: String },

    #[error("Internal error: {message}")]
    InternalError { message: String },

    #[error("Unknown error: {message}")]
    Unknown { message: String },
}

/// Result type alias for wallet operations
pub type WalletResult<T> = Result<T, WalletError>;

impl WalletError {
    /// Check if error is recoverable (can be retried)
    pub fn is_recoverable(&self) -> bool {
        match self {
            // Temporary/network errors are recoverable
            WalletError::NetworkError { .. } => true,
            WalletError::TimeoutError { .. } => true,
            WalletError::RateLimitError { .. } => true,
            WalletError::StorageError { .. } => true,
            WalletError::DatabaseError { .. } => true,

            // Hardware wallet cancellation is recoverable
            #[cfg(feature = "hardware-wallet")]
            WalletError::HardwareWalletCancelled => true,

            // Most other errors are not recoverable
            _ => false,
        }
    }

    /// Check if error is related to security
    pub fn is_security_related(&self) -> bool {
        match self {
            WalletError::InvalidPassword => true,
            WalletError::WalletLocked => true,
            WalletError::EncryptionError { .. } => true,
            WalletError::DecryptionError { .. } => true,
            WalletError::AuthenticationError { .. } => true,
            WalletError::SecurityPolicyViolation { .. } => true,
            WalletError::InvalidSignature { .. } => true,
            _ => false,
        }
    }

    /// Get error category for logging and monitoring
    pub fn category(&self) -> &'static str {
        match self {
            WalletError::CryptographyError { .. }
            | WalletError::InvalidPrivateKey { .. }
            | WalletError::InvalidPublicKey { .. }
            | WalletError::InvalidSignature { .. }
            | WalletError::KeyDerivationError { .. } => "cryptography",

            WalletError::InvalidMnemonic { .. }
            | WalletError::InvalidSeed { .. }
            | WalletError::MnemonicGenerationError { .. } => "mnemonic",

            WalletError::WalletNotFound { .. }
            | WalletError::WalletAlreadyExists { .. }
            | WalletError::InvalidPassword
            | WalletError::WalletLocked
            | WalletError::WalletCorruption { .. }
            | WalletError::InvalidWalletFormat { .. } => "wallet_management",

            WalletError::InvalidAddress { .. }
            | WalletError::InvalidTransaction { .. }
            | WalletError::TransactionSigningError { .. }
            | WalletError::InsufficientFunds { .. }
            | WalletError::InvalidFee { .. } => "transaction",

            WalletError::UnsupportedCoinType { .. }
            | WalletError::InvalidDerivationPath { .. } => "coin_type",

            WalletError::StorageError { .. }
            | WalletError::DatabaseError { .. }
            | WalletError::SerializationError { .. }
            | WalletError::DeserializationError { .. } => "storage",

            WalletError::EncryptionError { .. }
            | WalletError::DecryptionError { .. }
            | WalletError::AuthenticationError { .. }
            | WalletError::SecurityPolicyViolation { .. } => "security",

            #[cfg(feature = "hardware-wallet")]
            WalletError::HardwareWalletError { .. }
            | WalletError::HardwareWalletNotConnected
            | WalletError::HardwareWalletCancelled => "hardware_wallet",

            WalletError::MultiSignatureError { .. }
            | WalletError::InsufficientSignatures { .. }
            | WalletError::InvalidSignatureThreshold { .. } => "multi_signature",

            WalletError::NetworkError { .. }
            | WalletError::TimeoutError { .. }
            | WalletError::RateLimitError { .. } => "network",

            WalletError::InvalidConfiguration { .. }
            | WalletError::MissingConfiguration { .. } => "configuration",

            WalletError::InvalidInput { .. }
            | WalletError::OperationNotSupported { .. }
            | WalletError::InternalError { .. }
            | WalletError::Unknown { .. } => "general",
        }
    }
}

// Standard error conversions for commonly used libraries

impl From<bip39::Error> for WalletError {
    fn from(err: bip39::Error) -> Self {
        WalletError::InvalidMnemonic {
            reason: err.to_string(),
        }
    }
}

impl From<bip32::Error> for WalletError {
    fn from(err: bip32::Error) -> Self {
        WalletError::KeyDerivationError {
            reason: err.to_string(),
        }
    }
}

impl From<secp256k1::Error> for WalletError {
    fn from(err: secp256k1::Error) -> Self {
        WalletError::CryptographyError {
            message: err.to_string(),
        }
    }
}

impl From<serde_json::Error> for WalletError {
    fn from(err: serde_json::Error) -> Self {
        WalletError::SerializationError {
            message: err.to_string(),
        }
    }
}

impl From<rocksdb::Error> for WalletError {
    fn from(err: rocksdb::Error) -> Self {
        WalletError::DatabaseError {
            message: err.to_string(),
        }
    }
}

impl From<aes_gcm::Error> for WalletError {
    fn from(_err: aes_gcm::Error) -> Self {
        WalletError::EncryptionError {
            reason: "AES-GCM encryption/decryption failed".to_string(),
        }
    }
}

impl From<argon2::Error> for WalletError {
    fn from(err: argon2::Error) -> Self {
        WalletError::CryptographyError {
            message: format!("Argon2 error: {}", err),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_categories() {
        assert_eq!(
            WalletError::InvalidPrivateKey {
                reason: "test".to_string()
            }
            .category(),
            "cryptography"
        );

        assert_eq!(
            WalletError::WalletNotFound {
                wallet_id: "test".to_string()
            }
            .category(),
            "wallet_management"
        );

        assert_eq!(
            WalletError::NetworkError {
                message: "test".to_string()
            }
            .category(),
            "network"
        );
    }

    #[test]
    fn test_error_recoverability() {
        assert!(WalletError::NetworkError {
            message: "test".to_string()
        }
        .is_recoverable());

        assert!(!WalletError::InvalidPrivateKey {
            reason: "test".to_string()
        }
        .is_recoverable());
    }

    #[test]
    fn test_security_related() {
        assert!(WalletError::InvalidPassword.is_security_related());
        assert!(WalletError::WalletLocked.is_security_related());

        assert!(!WalletError::NetworkError {
            message: "test".to_string()
        }
        .is_security_related());
    }

    #[test]
    fn test_error_conversions() {
        let bip39_err = bip39::Error::BadWordCount(24);
        let wallet_err: WalletError = bip39_err.into();
        assert!(matches!(wallet_err, WalletError::InvalidMnemonic { .. }));

        let secp_err = secp256k1::Error::InvalidPublicKey;
        let wallet_err: WalletError = secp_err.into();
        assert!(matches!(wallet_err, WalletError::CryptographyError { .. }));
    }
}