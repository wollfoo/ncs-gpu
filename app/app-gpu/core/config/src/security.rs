//! Security features for configuration management

use crate::errors::{ConfigError, ConfigResult};
use aes_gcm::{
    aead::{Aead, AeadCore, KeyInit},
    Aes256Gcm, Key, Nonce,
};
use base64::{engine::general_purpose, Engine as _};
use ring::digest;
use secrecy::{ExposeSecret, Secret, Zeroize};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};
use tracing::{debug, warn};
use zeroize::ZeroizeOnDrop;

/// Encryption configuration settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptionConfig {
    /// Enable encryption for sensitive configuration values
    pub enabled: bool,
    /// Key derivation method (PBKDF2, Argon2, etc.)
    pub key_derivation: KeyDerivationMethod,
    /// Number of iterations for key derivation
    pub iterations: u32,
    /// Salt length for key derivation
    pub salt_length: usize,
    /// Encryption algorithm
    pub algorithm: EncryptionAlgorithm,
}

impl Default for EncryptionConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            key_derivation: KeyDerivationMethod::Pbkdf2,
            iterations: 100_000,
            salt_length: 32,
            algorithm: EncryptionAlgorithm::Aes256Gcm,
        }
    }
}

/// Supported key derivation methods
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum KeyDerivationMethod {
    Pbkdf2,
    Argon2,
}

/// Supported encryption algorithms
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum EncryptionAlgorithm {
    Aes256Gcm,
}

/// Encrypted data container
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptedData {
    /// Base64-encoded encrypted data
    pub data: String,
    /// Base64-encoded nonce/IV
    pub nonce: String,
    /// Base64-encoded salt used for key derivation
    pub salt: String,
    /// Encryption algorithm used
    pub algorithm: EncryptionAlgorithm,
    /// Key derivation method used
    pub key_derivation: KeyDerivationMethod,
    /// Number of iterations used for key derivation
    pub iterations: u32,
    /// Timestamp when encrypted
    pub timestamp: u64,
}

/// Secret management for configuration values
#[derive(ZeroizeOnDrop)]
pub struct SecretManager {
    /// Master key for encryption/decryption
    master_key: Secret<Vec<u8>>,
    /// Encryption configuration
    config: EncryptionConfig,
    /// Secret storage location
    storage_path: Option<PathBuf>,
    /// In-memory secret cache
    secret_cache: HashMap<String, Secret<String>>,
}

impl SecretManager {
    /// Create new secret manager with password-derived key
    pub fn new(password: &str, config: EncryptionConfig) -> ConfigResult<Self> {
        let salt = generate_random_bytes(config.salt_length);
        let master_key = derive_key(password.as_bytes(), &salt, config.iterations)?;

        Ok(Self {
            master_key: Secret::new(master_key),
            config,
            storage_path: None,
            secret_cache: HashMap::new(),
        })
    }

    /// Create secret manager with explicit key
    pub fn with_key(key: Vec<u8>, config: EncryptionConfig) -> Self {
        Self {
            master_key: Secret::new(key),
            config,
            storage_path: None,
            secret_cache: HashMap::new(),
        }
    }

    /// Set storage path for persistent secrets
    pub fn with_storage_path<P: AsRef<Path>>(mut self, path: P) -> Self {
        self.storage_path = Some(path.as_ref().to_path_buf());
        self
    }

    /// Encrypt a configuration value
    pub fn encrypt_value(&self, value: &str) -> ConfigResult<EncryptedData> {
        let salt = generate_random_bytes(self.config.salt_length);
        let key = derive_key(self.master_key.expose_secret(), &salt, self.config.iterations)?;

        let nonce = generate_random_bytes(12); // AES-GCM standard nonce size
        let encrypted_data = encrypt_data_with_key(value.as_bytes(), &key, &nonce)?;

        Ok(EncryptedData {
            data: general_purpose::STANDARD.encode(encrypted_data),
            nonce: general_purpose::STANDARD.encode(nonce),
            salt: general_purpose::STANDARD.encode(salt),
            algorithm: self.config.algorithm,
            key_derivation: self.config.key_derivation,
            iterations: self.config.iterations,
            timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        })
    }

    /// Decrypt a configuration value
    pub fn decrypt_value(&self, encrypted: &EncryptedData) -> ConfigResult<Secret<String>> {
        let data = general_purpose::STANDARD
            .decode(&encrypted.data)
            .map_err(|e| ConfigError::encryption(format!("Invalid base64 data: {}", e)))?;

        let nonce = general_purpose::STANDARD
            .decode(&encrypted.nonce)
            .map_err(|e| ConfigError::encryption(format!("Invalid base64 nonce: {}", e)))?;

        let salt = general_purpose::STANDARD
            .decode(&encrypted.salt)
            .map_err(|e| ConfigError::encryption(format!("Invalid base64 salt: {}", e)))?;

        let key = derive_key(
            self.master_key.expose_secret(),
            &salt,
            encrypted.iterations,
        )?;

        let decrypted_data = decrypt_data_with_key(&data, &key, &nonce)?;
        let decrypted_str = String::from_utf8(decrypted_data)
            .map_err(|e| ConfigError::encryption(format!("Invalid UTF-8: {}", e)))?;

        Ok(Secret::new(decrypted_str))
    }

    /// Store a secret by name
    pub fn store_secret(&mut self, name: String, value: Secret<String>) -> ConfigResult<()> {
        if self.config.enabled {
            // Store in cache
            self.secret_cache.insert(name.clone(), value);

            // Persist to storage if path is configured
            if let Some(ref storage_path) = self.storage_path {
                self.persist_secrets(storage_path)?;
            }

            debug!("Stored secret: {}", name);
        } else {
            return Err(ConfigError::security("Encryption is disabled"));
        }

        Ok(())
    }

    /// Retrieve a secret by name
    pub fn get_secret(&self, name: &str) -> ConfigResult<Option<Secret<String>>> {
        if let Some(secret) = self.secret_cache.get(name) {
            Ok(Some(secret.clone()))
        } else if let Some(ref storage_path) = self.storage_path {
            // Try to load from storage
            self.load_secret_from_storage(storage_path, name)
        } else {
            Ok(None)
        }
    }

    /// Remove a secret
    pub fn remove_secret(&mut self, name: &str) -> ConfigResult<bool> {
        let removed = self.secret_cache.remove(name).is_some();

        if removed && self.storage_path.is_some() {
            if let Some(ref storage_path) = self.storage_path {
                self.persist_secrets(storage_path)?;
            }
        }

        Ok(removed)
    }

    /// List all secret names
    pub fn list_secrets(&self) -> Vec<String> {
        self.secret_cache.keys().cloned().collect()
    }

    /// Clear all secrets from memory
    pub fn clear_secrets(&mut self) {
        self.secret_cache.clear();
    }

    /// Rotate the master key
    pub fn rotate_master_key(&mut self, new_password: &str) -> ConfigResult<()> {
        let salt = generate_random_bytes(self.config.salt_length);
        let new_master_key = derive_key(new_password.as_bytes(), &salt, self.config.iterations)?;

        // Re-encrypt all cached secrets with new key
        let old_secrets: Vec<(String, Secret<String>)> = self
            .secret_cache
            .drain()
            .collect();

        self.master_key = Secret::new(new_master_key);

        for (name, secret) in old_secrets {
            self.secret_cache.insert(name, secret);
        }

        // Persist with new key
        if let Some(ref storage_path) = self.storage_path {
            self.persist_secrets(storage_path)?;
        }

        debug!("Master key rotated successfully");
        Ok(())
    }

    /// Check if encryption is enabled
    pub fn is_encryption_enabled(&self) -> bool {
        self.config.enabled
    }

    /// Get configuration hash for integrity checking
    pub fn get_config_hash(&self) -> String {
        let digest = digest::digest(&digest::SHA256, self.master_key.expose_secret());
        general_purpose::STANDARD.encode(digest.as_ref())
    }

    fn persist_secrets(&self, storage_path: &Path) -> ConfigResult<()> {
        let mut encrypted_secrets = HashMap::new();

        for (name, secret) in &self.secret_cache {
            let encrypted = self.encrypt_value(secret.expose_secret())?;
            encrypted_secrets.insert(name.clone(), encrypted);
        }

        let serialized = serde_json::to_string_pretty(&encrypted_secrets)?;
        std::fs::write(storage_path, serialized)?;

        debug!("Persisted {} secrets to storage", encrypted_secrets.len());
        Ok(())
    }

    fn load_secret_from_storage(
        &self,
        storage_path: &Path,
        name: &str,
    ) -> ConfigResult<Option<Secret<String>>> {
        if !storage_path.exists() {
            return Ok(None);
        }

        let content = std::fs::read_to_string(storage_path)?;
        let encrypted_secrets: HashMap<String, EncryptedData> = serde_json::from_str(&content)?;

        if let Some(encrypted) = encrypted_secrets.get(name) {
            let decrypted = self.decrypt_value(encrypted)?;
            Ok(Some(decrypted))
        } else {
            Ok(None)
        }
    }
}

/// Encrypt data using AES-256-GCM
pub async fn encrypt_data(data: &[u8], password: &[u8]) -> ConfigResult<Vec<u8>> {
    let salt = generate_random_bytes(32);
    let key = derive_key(password, &salt, 100_000)?;
    let nonce = generate_random_bytes(12);

    let encrypted = encrypt_data_with_key(data, &key, &nonce)?;

    // Prepend salt and nonce to encrypted data
    let mut result = Vec::with_capacity(salt.len() + nonce.len() + encrypted.len());
    result.extend_from_slice(&salt);
    result.extend_from_slice(&nonce);
    result.extend_from_slice(&encrypted);

    Ok(result)
}

/// Decrypt data using AES-256-GCM
pub async fn decrypt_data(encrypted_data: &[u8], password: &[u8]) -> ConfigResult<Vec<u8>> {
    if encrypted_data.len() < 44 {
        // 32 bytes salt + 12 bytes nonce
        return Err(ConfigError::encryption("Invalid encrypted data length"));
    }

    let salt = &encrypted_data[0..32];
    let nonce = &encrypted_data[32..44];
    let ciphertext = &encrypted_data[44..];

    let key = derive_key(password, salt, 100_000)?;
    decrypt_data_with_key(ciphertext, &key, nonce)
}

fn encrypt_data_with_key(data: &[u8], key: &[u8], nonce: &[u8]) -> ConfigResult<Vec<u8>> {
    let key = Key::<Aes256Gcm>::from_slice(key);
    let cipher = Aes256Gcm::new(key);
    let nonce = Nonce::from_slice(nonce);

    cipher
        .encrypt(nonce, data)
        .map_err(|e| ConfigError::encryption(format!("Encryption failed: {}", e)))
}

fn decrypt_data_with_key(data: &[u8], key: &[u8], nonce: &[u8]) -> ConfigResult<Vec<u8>> {
    let key = Key::<Aes256Gcm>::from_slice(key);
    let cipher = Aes256Gcm::new(key);
    let nonce = Nonce::from_slice(nonce);

    cipher
        .decrypt(nonce, data)
        .map_err(|e| ConfigError::encryption(format!("Decryption failed: {}", e)))
}

fn derive_key(password: &[u8], salt: &[u8], iterations: u32) -> ConfigResult<Vec<u8>> {
    use ring::pbkdf2;

    let mut key = vec![0u8; 32]; // 256 bits for AES-256
    pbkdf2::derive(
        pbkdf2::PBKDF2_HMAC_SHA256,
        std::num::NonZeroU32::new(iterations).unwrap(),
        salt,
        password,
        &mut key,
    );

    Ok(key)
}

fn generate_random_bytes(len: usize) -> Vec<u8> {
    use ring::rand::{SystemRandom, SecureRandom};

    let rng = SystemRandom::new();
    let mut bytes = vec![0u8; len];
    rng.fill(&mut bytes).expect("Failed to generate random bytes");
    bytes
}

/// Access control for configuration sections
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccessControl {
    /// Required permissions to read configuration sections
    pub read_permissions: HashMap<String, Vec<String>>,
    /// Required permissions to write configuration sections
    pub write_permissions: HashMap<String, Vec<String>>,
    /// Enable role-based access control
    pub rbac_enabled: bool,
    /// Default permissions for new sections
    pub default_permissions: Vec<String>,
}

impl Default for AccessControl {
    fn default() -> Self {
        Self {
            read_permissions: HashMap::new(),
            write_permissions: HashMap::new(),
            rbac_enabled: false,
            default_permissions: vec!["config.read".to_string()],
        }
    }
}

impl AccessControl {
    /// Check if user has read permission for section
    pub fn can_read(&self, section: &str, user_permissions: &[String]) -> bool {
        if !self.rbac_enabled {
            return true;
        }

        let required = self
            .read_permissions
            .get(section)
            .unwrap_or(&self.default_permissions);

        required.iter().any(|perm| user_permissions.contains(perm))
    }

    /// Check if user has write permission for section
    pub fn can_write(&self, section: &str, user_permissions: &[String]) -> bool {
        if !self.rbac_enabled {
            return true;
        }

        let required = self
            .write_permissions
            .get(section)
            .unwrap_or(&vec!["config.write".to_string()]);

        required.iter().any(|perm| user_permissions.contains(perm))
    }

    /// Add read permission for section
    pub fn add_read_permission(&mut self, section: String, permission: String) {
        self.read_permissions
            .entry(section)
            .or_insert_with(Vec::new)
            .push(permission);
    }

    /// Add write permission for section
    pub fn add_write_permission(&mut self, section: String, permission: String) {
        self.write_permissions
            .entry(section)
            .or_insert_with(Vec::new)
            .push(permission);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_secret_manager_creation() {
        let config = EncryptionConfig::default();
        let manager = SecretManager::new("test_password", config).unwrap();
        assert!(manager.is_encryption_enabled());
    }

    #[tokio::test]
    async fn test_encrypt_decrypt_data() {
        let data = b"sensitive configuration data";
        let password = b"test_password";

        let encrypted = encrypt_data(data, password).await.unwrap();
        let decrypted = decrypt_data(&encrypted, password).await.unwrap();

        assert_eq!(data, decrypted.as_slice());
    }

    #[test]
    fn test_access_control() {
        let mut access_control = AccessControl::default();
        access_control.rbac_enabled = true;
        access_control.add_read_permission("mining".to_string(), "mining.read".to_string());

        let user_perms = vec!["mining.read".to_string()];
        assert!(access_control.can_read("mining", &user_perms));

        let no_perms = vec![];
        assert!(!access_control.can_read("mining", &no_perms));
    }

    #[test]
    fn test_key_derivation() {
        let password = b"test_password";
        let salt = b"test_salt_32_bytes_long_exactly!";
        let key1 = derive_key(password, salt, 1000).unwrap();
        let key2 = derive_key(password, salt, 1000).unwrap();

        assert_eq!(key1, key2);
        assert_eq!(key1.len(), 32);
    }
}