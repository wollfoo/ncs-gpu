//! Encryption implementation for secure data storage

use crate::{WalletError, WalletResult};
use aes_gcm::{
    aead::{Aead, AeadCore, KeyInit, OsRng},
    Aes256Gcm, Nonce,
};
use argon2::{Argon2, PasswordHash, PasswordHasher, PasswordVerifier, Salt};
use chacha20poly1305::{ChaCha20Poly1305, Key};
use rand::{RngCore, thread_rng};
use serde::{Deserialize, Serialize};
use zeroize::{Zeroize, ZeroizeOnDrop};

/// Encryption method enumeration
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum EncryptionMethod {
    /// AES-256-GCM encryption
    Aes256Gcm,
    /// ChaCha20-Poly1305 encryption
    ChaCha20Poly1305,
}

impl Default for EncryptionMethod {
    fn default() -> Self {
        EncryptionMethod::Aes256Gcm
    }
}

impl std::str::FromStr for EncryptionMethod {
    type Err = WalletError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "aes-256-gcm" | "aes256gcm" => Ok(EncryptionMethod::Aes256Gcm),
            "chacha20-poly1305" | "chacha20poly1305" => Ok(EncryptionMethod::ChaCha20Poly1305),
            _ => Err(WalletError::InvalidConfiguration {
                field: "encryption_method".to_string(),
                value: s.to_string(),
            }),
        }
    }
}

impl std::fmt::Display for EncryptionMethod {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EncryptionMethod::Aes256Gcm => write!(f, "AES-256-GCM"),
            EncryptionMethod::ChaCha20Poly1305 => write!(f, "ChaCha20-Poly1305"),
        }
    }
}

/// Encryption manager for handling cryptographic operations
#[derive(Debug)]
pub struct EncryptionManager {
    method: EncryptionMethod,
    argon2: Argon2<'static>,
}

impl EncryptionManager {
    /// Create new encryption manager
    pub fn new(method_str: String) -> WalletResult<Self> {
        let method = method_str.parse()?;
        let argon2 = Argon2::default();

        Ok(Self { method, argon2 })
    }

    /// Initialize encryption manager
    pub async fn initialize(&self) -> WalletResult<()> {
        tracing::info!("Initializing encryption manager with method: {}", self.method);

        // Test encryption/decryption to ensure everything works
        let test_data = b"test";
        let test_key = self.generate_key();
        let encrypted = self.encrypt(test_data, &test_key).await?;
        let decrypted = self.decrypt(&encrypted, &test_key).await?;

        if decrypted != test_data {
            return Err(WalletError::EncryptionError {
                reason: "Encryption test failed".to_string(),
            });
        }

        tracing::info!("Encryption manager initialized successfully");
        Ok(())
    }

    /// Generate random encryption key
    pub fn generate_key(&self) -> Vec<u8> {
        match self.method {
            EncryptionMethod::Aes256Gcm => {
                let key = Aes256Gcm::generate_key(&mut OsRng);
                key.to_vec()
            }
            EncryptionMethod::ChaCha20Poly1305 => {
                let key = ChaCha20Poly1305::generate_key(&mut OsRng);
                key.to_vec()
            }
        }
    }

    /// Generate random salt
    pub fn generate_salt(&self) -> [u8; 32] {
        let mut salt = [0u8; 32];
        thread_rng().fill_bytes(&mut salt);
        salt
    }

    /// Derive key from password using Argon2
    pub async fn derive_key_from_password(
        &self,
        password: &str,
        salt: &[u8],
        iterations: u32,
    ) -> WalletResult<Vec<u8>> {
        if salt.len() < 16 {
            return Err(WalletError::InvalidInput {
                message: "Salt must be at least 16 bytes".to_string(),
            });
        }

        let salt = Salt::from_b64(&base64::encode(salt))
            .map_err(|e| WalletError::CryptographyError {
                message: format!("Invalid salt: {}", e),
            })?;

        // Use custom Argon2 parameters for more iterations
        let argon2 = Argon2::new(
            argon2::Algorithm::Argon2id,
            argon2::Version::V0x13,
            argon2::Params::new(
                65536,                    // memory cost (64 MB)
                iterations,               // time cost
                1,                        // parallelism
                Some(32),                 // output length
            ).map_err(|e| WalletError::CryptographyError {
                message: format!("Invalid Argon2 params: {}", e),
            })?,
        );

        let mut output = [0u8; 32];
        argon2.hash_password_into(password.as_bytes(), salt.as_bytes(), &mut output)
            .map_err(|e| WalletError::CryptographyError {
                message: format!("Key derivation failed: {}", e),
            })?;

        Ok(output.to_vec())
    }

    /// Hash password for storage
    pub fn hash_password(&self, password: &str) -> WalletResult<String> {
        let salt = Salt::generate(&mut OsRng);
        let password_hash = self.argon2
            .hash_password(password.as_bytes(), &salt)
            .map_err(|e| WalletError::CryptographyError {
                message: format!("Password hashing failed: {}", e),
            })?;

        Ok(password_hash.to_string())
    }

    /// Verify password against hash
    pub fn verify_password(&self, password: &str, hash: &str) -> WalletResult<bool> {
        let parsed_hash = PasswordHash::new(hash)
            .map_err(|e| WalletError::CryptographyError {
                message: format!("Invalid password hash: {}", e),
            })?;

        match self.argon2.verify_password(password.as_bytes(), &parsed_hash) {
            Ok(()) => Ok(true),
            Err(argon2::password_hash::Error::Password) => Ok(false),
            Err(e) => Err(WalletError::CryptographyError {
                message: format!("Password verification failed: {}", e),
            }),
        }
    }

    /// Encrypt data with given key
    pub async fn encrypt(&self, data: &[u8], key: &[u8]) -> WalletResult<Vec<u8>> {
        match self.method {
            EncryptionMethod::Aes256Gcm => self.encrypt_aes_gcm(data, key).await,
            EncryptionMethod::ChaCha20Poly1305 => self.encrypt_chacha20poly1305(data, key).await,
        }
    }

    /// Decrypt data with given key
    pub async fn decrypt(&self, encrypted_data: &[u8], key: &[u8]) -> WalletResult<Vec<u8>> {
        match self.method {
            EncryptionMethod::Aes256Gcm => self.decrypt_aes_gcm(encrypted_data, key).await,
            EncryptionMethod::ChaCha20Poly1305 => self.decrypt_chacha20poly1305(encrypted_data, key).await,
        }
    }

    /// Encrypt using AES-256-GCM
    async fn encrypt_aes_gcm(&self, data: &[u8], key: &[u8]) -> WalletResult<Vec<u8>> {
        if key.len() != 32 {
            return Err(WalletError::InvalidInput {
                message: "AES-256 key must be 32 bytes".to_string(),
            });
        }

        let key = aes_gcm::Key::<Aes256Gcm>::from_slice(key);
        let cipher = Aes256Gcm::new(key);
        let nonce = Aes256Gcm::generate_nonce(&mut OsRng);

        let ciphertext = cipher
            .encrypt(&nonce, data)
            .map_err(|_| WalletError::EncryptionError {
                reason: "AES-GCM encryption failed".to_string(),
            })?;

        // Prepend nonce to ciphertext
        let mut result = nonce.to_vec();
        result.extend_from_slice(&ciphertext);

        Ok(result)
    }

    /// Decrypt using AES-256-GCM
    async fn decrypt_aes_gcm(&self, encrypted_data: &[u8], key: &[u8]) -> WalletResult<Vec<u8>> {
        if key.len() != 32 {
            return Err(WalletError::InvalidInput {
                message: "AES-256 key must be 32 bytes".to_string(),
            });
        }

        if encrypted_data.len() < 12 {
            return Err(WalletError::DecryptionError {
                reason: "Encrypted data too short for AES-GCM".to_string(),
            });
        }

        let key = aes_gcm::Key::<Aes256Gcm>::from_slice(key);
        let cipher = Aes256Gcm::new(key);

        // Extract nonce and ciphertext
        let (nonce_bytes, ciphertext) = encrypted_data.split_at(12);
        let nonce = Nonce::from_slice(nonce_bytes);

        let plaintext = cipher
            .decrypt(nonce, ciphertext)
            .map_err(|_| WalletError::DecryptionError {
                reason: "AES-GCM decryption failed".to_string(),
            })?;

        Ok(plaintext)
    }

    /// Encrypt using ChaCha20-Poly1305
    async fn encrypt_chacha20poly1305(&self, data: &[u8], key: &[u8]) -> WalletResult<Vec<u8>> {
        if key.len() != 32 {
            return Err(WalletError::InvalidInput {
                message: "ChaCha20 key must be 32 bytes".to_string(),
            });
        }

        let key = Key::from_slice(key);
        let cipher = ChaCha20Poly1305::new(key);
        let nonce = ChaCha20Poly1305::generate_nonce(&mut OsRng);

        let ciphertext = cipher
            .encrypt(&nonce, data)
            .map_err(|_| WalletError::EncryptionError {
                reason: "ChaCha20-Poly1305 encryption failed".to_string(),
            })?;

        // Prepend nonce to ciphertext
        let mut result = nonce.to_vec();
        result.extend_from_slice(&ciphertext);

        Ok(result)
    }

    /// Decrypt using ChaCha20-Poly1305
    async fn decrypt_chacha20poly1305(&self, encrypted_data: &[u8], key: &[u8]) -> WalletResult<Vec<u8>> {
        if key.len() != 32 {
            return Err(WalletError::InvalidInput {
                message: "ChaCha20 key must be 32 bytes".to_string(),
            });
        }

        if encrypted_data.len() < 12 {
            return Err(WalletError::DecryptionError {
                reason: "Encrypted data too short for ChaCha20-Poly1305".to_string(),
            });
        }

        let key = Key::from_slice(key);
        let cipher = ChaCha20Poly1305::new(key);

        // Extract nonce and ciphertext
        let (nonce_bytes, ciphertext) = encrypted_data.split_at(12);
        let nonce = chacha20poly1305::Nonce::from_slice(nonce_bytes);

        let plaintext = cipher
            .decrypt(nonce, ciphertext)
            .map_err(|_| WalletError::DecryptionError {
                reason: "ChaCha20-Poly1305 decryption failed".to_string(),
            })?;

        Ok(plaintext)
    }

    /// Get encryption method
    pub fn method(&self) -> &EncryptionMethod {
        &self.method
    }

    /// Check if method supports streaming
    pub fn supports_streaming(&self) -> bool {
        // Both AES-GCM and ChaCha20-Poly1305 can be adapted for streaming
        true
    }

    /// Get key size for current method
    pub fn key_size(&self) -> usize {
        match self.method {
            EncryptionMethod::Aes256Gcm => 32,          // 256 bits
            EncryptionMethod::ChaCha20Poly1305 => 32,   // 256 bits
        }
    }

    /// Get nonce size for current method
    pub fn nonce_size(&self) -> usize {
        match self.method {
            EncryptionMethod::Aes256Gcm => 12,          // 96 bits
            EncryptionMethod::ChaCha20Poly1305 => 12,   // 96 bits
        }
    }
}

/// Secure key container that zeroizes on drop
#[derive(Clone, Zeroize, ZeroizeOnDrop)]
pub struct SecureKey {
    key: Vec<u8>,
}

impl SecureKey {
    /// Create new secure key
    pub fn new(key: Vec<u8>) -> Self {
        Self { key }
    }

    /// Generate random secure key
    pub fn generate(method: &EncryptionMethod) -> Self {
        let manager = EncryptionManager::new(method.to_string()).unwrap();
        let key = manager.generate_key();
        Self::new(key)
    }

    /// Get key bytes (use carefully)
    pub fn as_bytes(&self) -> &[u8] {
        &self.key
    }

    /// Get key length
    pub fn len(&self) -> usize {
        self.key.len()
    }

    /// Check if key is empty
    pub fn is_empty(&self) -> bool {
        self.key.is_empty()
    }
}

impl std::fmt::Debug for SecureKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SecureKey")
            .field("len", &self.key.len())
            .field("key", &"[REDACTED]")
            .finish()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_encryption_manager_creation() {
        let manager = EncryptionManager::new("AES-256-GCM".to_string()).unwrap();
        assert_eq!(manager.method, EncryptionMethod::Aes256Gcm);

        let manager = EncryptionManager::new("ChaCha20-Poly1305".to_string()).unwrap();
        assert_eq!(manager.method, EncryptionMethod::ChaCha20Poly1305);
    }

    #[tokio::test]
    async fn test_aes_gcm_encryption() {
        let manager = EncryptionManager::new("AES-256-GCM".to_string()).unwrap();
        let key = manager.generate_key();
        let data = b"test data for encryption";

        let encrypted = manager.encrypt(data, &key).await.unwrap();
        assert_ne!(encrypted, data);
        assert!(encrypted.len() > data.len()); // Should be larger due to nonce + auth tag

        let decrypted = manager.decrypt(&encrypted, &key).await.unwrap();
        assert_eq!(decrypted, data);
    }

    #[tokio::test]
    async fn test_chacha20poly1305_encryption() {
        let manager = EncryptionManager::new("ChaCha20-Poly1305".to_string()).unwrap();
        let key = manager.generate_key();
        let data = b"test data for encryption";

        let encrypted = manager.encrypt(data, &key).await.unwrap();
        assert_ne!(encrypted, data);
        assert!(encrypted.len() > data.len());

        let decrypted = manager.decrypt(&encrypted, &key).await.unwrap();
        assert_eq!(decrypted, data);
    }

    #[tokio::test]
    async fn test_password_derivation() {
        let manager = EncryptionManager::new("AES-256-GCM".to_string()).unwrap();
        let password = "test_password_123";
        let salt = manager.generate_salt();

        let key1 = manager.derive_key_from_password(password, &salt, 100).await.unwrap();
        let key2 = manager.derive_key_from_password(password, &salt, 100).await.unwrap();

        assert_eq!(key1, key2); // Same password + salt should produce same key
        assert_eq!(key1.len(), 32); // Should be 256 bits

        // Different salt should produce different key
        let different_salt = manager.generate_salt();
        let key3 = manager.derive_key_from_password(password, &different_salt, 100).await.unwrap();
        assert_ne!(key1, key3);
    }

    #[tokio::test]
    async fn test_password_hashing() {
        let manager = EncryptionManager::new("AES-256-GCM".to_string()).unwrap();
        let password = "test_password_123";

        let hash = manager.hash_password(password).unwrap();
        assert!(!hash.is_empty());

        assert!(manager.verify_password(password, &hash).unwrap());
        assert!(!manager.verify_password("wrong_password", &hash).unwrap());
    }

    #[test]
    fn test_encryption_method_parsing() {
        assert_eq!("aes-256-gcm".parse::<EncryptionMethod>().unwrap(), EncryptionMethod::Aes256Gcm);
        assert_eq!("chacha20-poly1305".parse::<EncryptionMethod>().unwrap(), EncryptionMethod::ChaCha20Poly1305);
        assert!("invalid".parse::<EncryptionMethod>().is_err());
    }

    #[test]
    fn test_secure_key() {
        let key_data = vec![1, 2, 3, 4];
        let secure_key = SecureKey::new(key_data.clone());

        assert_eq!(secure_key.as_bytes(), &key_data);
        assert_eq!(secure_key.len(), key_data.len());
        assert!(!secure_key.is_empty());

        // Test debug output doesn't leak key
        let debug_str = format!("{:?}", secure_key);
        assert!(debug_str.contains("[REDACTED]"));
        assert!(!debug_str.contains("1, 2, 3, 4"));
    }

    #[tokio::test]
    async fn test_encryption_with_wrong_key() {
        let manager = EncryptionManager::new("AES-256-GCM".to_string()).unwrap();
        let key1 = manager.generate_key();
        let key2 = manager.generate_key();
        let data = b"test data";

        let encrypted = manager.encrypt(data, &key1).await.unwrap();

        // Try to decrypt with wrong key
        let result = manager.decrypt(&encrypted, &key2).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_invalid_key_sizes() {
        let manager = EncryptionManager::new("AES-256-GCM".to_string()).unwrap();
        let data = b"test data";
        let wrong_key = vec![1u8; 16]; // Too short for AES-256

        let result = manager.encrypt(data, &wrong_key).await;
        assert!(result.is_err());
    }
}