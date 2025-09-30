/*!
 * Secrets Management - Encrypted Configuration Handling
 *
 * Sử dụng age encryption để bảo vệ sensitive configuration.
 * Master key được lưu trong OS keyring (graceful fallback nếu không có).
 */

use super::{Result, SecurityError};
use age::{Decryptor, Encryptor, x25519, secrecy::ExposeSecret};
use std::fs;
use std::io::{Read, Write};
use std::path::Path;
use tracing::{info, warn};

/// SecretStore - Quản lý encrypted configuration files
pub struct SecretStore {
    master_key: Option<x25519::Identity>,
}

impl SecretStore {
    /// Tạo mới SecretStore với master key từ OS keyring hoặc generate mới
    pub fn new() -> Result<Self> {
        let master_key = match Self::load_master_key_from_keyring() {
            Ok(key) => {
                info!("✅ Loaded master key from OS keyring");
                Some(key)
            }
            Err(e) => {
                warn!("⚠️  Could not load master key from keyring: {}. Generating ephemeral key.", e);
                warn!("⚠️  Config encryption will be session-only (not persisted)");
                Some(x25519::Identity::generate())
            }
        };

        Ok(Self { master_key })
    }

    /// Load encrypted configuration file
    pub fn load_encrypted_config<T>(&self, path: &Path) -> Result<T>
    where
        T: serde::de::DeserializeOwned,
    {
        // Nếu file không tồn tại hoặc không có master key, fallback to plaintext
        if !path.exists() {
            warn!("⚠️  Encrypted config not found: {:?}, falling back to plaintext", path);
            return self.load_plaintext_config(path);
        }

        let master_key = match &self.master_key {
            Some(key) => key,
            None => {
                warn!("⚠️  No master key available, falling back to plaintext config");
                return self.load_plaintext_config(path);
            }
        };

        info!("🔓 Decrypting configuration from {:?}", path);

        // Read encrypted file
        let encrypted_data = fs::read(path)?;

        // Decrypt với age
        let decryptor = match Decryptor::new(&encrypted_data[..]) {
            Ok(Decryptor::Recipients(d)) => d,
            Ok(_) => {
                warn!("⚠️  Unsupported age format, falling back to plaintext");
                return self.load_plaintext_config(path);
            }
            Err(e) => {
                warn!("⚠️  Age decryption failed: {}, falling back to plaintext", e);
                return self.load_plaintext_config(path);
            }
        };

        let mut decrypted_data = Vec::new();
        match decryptor.decrypt(std::iter::once(master_key as &dyn age::Identity)) {
            Ok(mut reader) => {
                reader.read_to_end(&mut decrypted_data)?;
            }
            Err(e) => {
                warn!("⚠️  Age decryption failed: {}, falling back to plaintext", e);
                return self.load_plaintext_config(path);
            }
        }

        let decrypted = decrypted_data;

        // Parse TOML
        let config_str = String::from_utf8(decrypted)
            .map_err(|e| SecurityError::IoError(std::io::Error::new(std::io::ErrorKind::InvalidData, e)))?;

        let config: T = toml::from_str(&config_str)?;

        info!("✅ Configuration decrypted successfully");
        Ok(config)
    }

    /// Save encrypted configuration
    pub fn save_encrypted_config<T>(&self, config: &T, path: &Path) -> Result<()>
    where
        T: serde::Serialize,
    {
        let master_key = match &self.master_key {
            Some(key) => key,
            None => {
                warn!("⚠️  No master key, saving plaintext config");
                return self.save_plaintext_config(config, path);
            }
        };

        info!("🔐 Encrypting configuration to {:?}", path);

        // Serialize to TOML
        let config_str = toml::to_string_pretty(config)
            .map_err(|e| SecurityError::IoError(std::io::Error::new(std::io::ErrorKind::InvalidData, e)))?;

        // Encrypt với age
        let encryptor = Encryptor::with_recipients(vec![Box::new(master_key.to_public())])
            .ok_or_else(|| SecurityError::IoError(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "No recipients provided for encryption"
            )))?;

        let mut encrypted_data = Vec::new();
        let mut writer = encryptor.wrap_output(&mut encrypted_data)
            .map_err(|e| SecurityError::IoError(std::io::Error::new(std::io::ErrorKind::Other, e)))?;
        writer.write_all(config_str.as_bytes())?;
        writer.finish()
            .map_err(|e| SecurityError::IoError(std::io::Error::new(std::io::ErrorKind::Other, e)))?;

        // Write to file
        fs::write(path, encrypted_data)?;

        info!("✅ Configuration encrypted and saved");
        Ok(())
    }

    /// Fallback: Load plaintext config nếu encryption fails
    fn load_plaintext_config<T>(&self, path: &Path) -> Result<T>
    where
        T: serde::de::DeserializeOwned,
    {
        // Try thay đổi extension .encrypted -> .toml
        let plaintext_path = path.with_extension("toml");

        if plaintext_path.exists() {
            warn!("📄 Loading plaintext config from {:?}", plaintext_path);
            let content = fs::read_to_string(&plaintext_path)?;
            let config: T = toml::from_str(&content)?;
            Ok(config)
        } else {
            Err(SecurityError::IoError(std::io::Error::new(
                std::io::ErrorKind::NotFound,
                format!("Neither encrypted nor plaintext config found: {:?}", path),
            )))
        }
    }

    /// Fallback: Save plaintext config
    fn save_plaintext_config<T>(&self, config: &T, path: &Path) -> Result<()>
    where
        T: serde::Serialize,
    {
        let plaintext_path = path.with_extension("toml");
        warn!("📄 Saving plaintext config to {:?}", plaintext_path);

        let config_str = toml::to_string_pretty(config)
            .map_err(|e| SecurityError::IoError(std::io::Error::new(std::io::ErrorKind::InvalidData, e)))?;

        fs::write(plaintext_path, config_str)?;
        Ok(())
    }

    /// Load master key from OS keyring (Linux keyctl hoặc file-based fallback)
    fn load_master_key_from_keyring() -> Result<x25519::Identity> {
        // TODO: Implement actual keyring integration
        // For now, use file-based storage as fallback

        let key_path = dirs::home_dir()
            .ok_or_else(|| SecurityError::KeyringError("Cannot determine home directory".into()))?
            .join(".opus-gpu")
            .join("master.key");

        if key_path.exists() {
            let key_str = fs::read_to_string(&key_path)?;
            let key: x25519::Identity = key_str.trim().parse()
                .map_err(|e| SecurityError::KeyringError(format!("Invalid key format: {}", e)))?;
            Ok(key)
        } else {
            // Generate new key and save
            warn!("🔑 Generating new master key and saving to {:?}", key_path);
            fs::create_dir_all(key_path.parent().unwrap())?;

            let key = x25519::Identity::generate();
            let key_str = key.to_string();
            fs::write(&key_path, key_str.expose_secret().as_bytes())?;

            // Secure permissions (Unix only)
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                let mut perms = fs::metadata(&key_path)?.permissions();
                perms.set_mode(0o600); // rw-------
                fs::set_permissions(&key_path, perms)?;
            }

            Ok(key)
        }
    }
}

impl Default for SecretStore {
    fn default() -> Self {
        Self::new().unwrap_or_else(|_| Self { master_key: None })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::{Deserialize, Serialize};
    use tempfile::NamedTempFile;

    #[derive(Debug, Serialize, Deserialize, PartialEq)]
    struct TestConfig {
        api_key: String,
        secret: String,
    }

    #[test]
    fn test_encrypt_decrypt_roundtrip() {
        let store = SecretStore::new().unwrap();
        let config = TestConfig {
            api_key: "test-key-123".into(),
            secret: "super-secret-value".into(),
        };

        let temp_file = NamedTempFile::new().unwrap();
        let path = temp_file.path();

        // Encrypt and save
        store.save_encrypted_config(&config, path).unwrap();

        // Decrypt and load
        let loaded: TestConfig = store.load_encrypted_config(path).unwrap();

        assert_eq!(config, loaded);
    }
}
