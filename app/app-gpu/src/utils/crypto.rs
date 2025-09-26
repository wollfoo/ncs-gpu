/*!
# Cryptographic Utilities

**Memory-safe cryptographic operations** cho App-GPU security features.

## Features

- **Memory encryption** cho sensitive data
- **Key derivation** từ passwords/passphrases
- **Secure random generation**
- **Zero-copy operations** khi possible
- **Zeroize on drop** cho security

## Example

```rust
use app_gpu::utils::crypto::{generate_key, encrypt_data, decrypt_data};

let key = generate_key()?;
let plaintext = b"sensitive GPU data";

let ciphertext = encrypt_data(&key, plaintext)?;
let decrypted = decrypt_data(&key, &ciphertext)?;

assert_eq!(plaintext, &decrypted[..]);
```
*/

use anyhow::{Context, Result};
use ring::{
    aead::{self, AES_256_GCM, Aad, LessSafeKey, Nonce, UnboundKey},
    pbkdf2::{self, PBKDF2_HMAC_SHA256},
    rand::{SecureRandom, SystemRandom},
};
use std::num::NonZeroU32;
use zeroize::{Zeroize, ZeroizeOnDrop};

/// **Encryption Key** (khóa mã hóa)
#[derive(ZeroizeOnDrop)]
pub struct EncryptionKey {
    key: LessSafeKey,
}

/// **Encrypted Data** (dữ liệu đã mã hóa)
#[derive(Debug, Clone)]
pub struct EncryptedData {
    pub nonce: [u8; 12], // 96-bit nonce for AES-GCM
    pub ciphertext: Vec<u8>,
}

/// **Key Derivation Parameters** (tham số tạo khóa)
pub struct KeyDerivationParams {
    pub salt: [u8; 32],
    pub iterations: NonZeroU32,
}

impl EncryptionKey {
    /// **Create key from raw bytes** (tạo khóa từ bytes thô)
    pub fn from_bytes(key_bytes: &[u8]) -> Result<Self> {
        if key_bytes.len() != 32 {
            anyhow::bail!("Key must be exactly 32 bytes");
        }
        
        let unbound_key = UnboundKey::new(&AES_256_GCM, key_bytes)
            .context("Failed to create unbound key")?;
        
        let key = LessSafeKey::new(unbound_key);
        
        Ok(Self { key })
    }
    
    /// **Encrypt data** (mã hóa dữ liệu)
    pub fn encrypt(&self, plaintext: &[u8]) -> Result<EncryptedData> {
        let rng = SystemRandom::new();
        
        // Generate random nonce
        let mut nonce_bytes = [0u8; 12];
        rng.fill(&mut nonce_bytes)
            .context("Failed to generate nonce")?;
        
        let nonce = Nonce::assume_unique_for_key(nonce_bytes);
        
        // Encrypt data
        let mut ciphertext = plaintext.to_vec();
        self.key
            .seal_in_place_append_tag(nonce, Aad::empty(), &mut ciphertext)
            .context("Encryption failed")?;
        
        Ok(EncryptedData {
            nonce: nonce_bytes,
            ciphertext,
        })
    }
    
    /// **Decrypt data** (giải mã dữ liệu)
    pub fn decrypt(&self, encrypted: &EncryptedData) -> Result<Vec<u8>> {
        let nonce = Nonce::assume_unique_for_key(encrypted.nonce);
        
        let mut plaintext = encrypted.ciphertext.clone();
        let decrypted_len = self.key
            .open_in_place(nonce, Aad::empty(), &mut plaintext)
            .context("Decryption failed")?
            .len();
        
        plaintext.truncate(decrypted_len);
        Ok(plaintext)
    }
}

/// **Generate random encryption key** (tạo khóa mã hóa ngẫu nhiên)
pub fn generate_key() -> Result<EncryptionKey> {
    let rng = SystemRandom::new();
    let mut key_bytes = [0u8; 32];
    
    rng.fill(&mut key_bytes)
        .context("Failed to generate random key")?;
    
    let result = EncryptionKey::from_bytes(&key_bytes);
    
    // Clear sensitive data
    key_bytes.zeroize();
    
    result
}

/// **Derive key from password** (tạo khóa từ mật khẩu)
pub fn derive_key_from_password(
    password: &str,
    params: &KeyDerivationParams,
) -> Result<EncryptionKey> {
    let mut key_bytes = [0u8; 32];
    
    pbkdf2::derive(
        PBKDF2_HMAC_SHA256,
        params.iterations,
        &params.salt,
        password.as_bytes(),
        &mut key_bytes,
    );
    
    let result = EncryptionKey::from_bytes(&key_bytes);
    
    // Clear sensitive data
    key_bytes.zeroize();
    
    result
}

/// **Generate key derivation parameters** (tạo tham số tạo khóa)
pub fn generate_key_derivation_params() -> Result<KeyDerivationParams> {
    let rng = SystemRandom::new();
    let mut salt = [0u8; 32];
    
    rng.fill(&mut salt)
        .context("Failed to generate salt")?;
    
    Ok(KeyDerivationParams {
        salt,
        iterations: NonZeroU32::new(100_000).unwrap(), // OWASP recommended minimum
    })
}

/// **Encrypt data with generated key** (mã hóa dữ liệu với khóa được tạo)
pub fn encrypt_data(key: &EncryptionKey, plaintext: &[u8]) -> Result<EncryptedData> {
    key.encrypt(plaintext)
}

/// **Decrypt data** (giải mã dữ liệu)
pub fn decrypt_data(key: &EncryptionKey, encrypted: &EncryptedData) -> Result<Vec<u8>> {
    key.decrypt(encrypted)
}

/// **Generate secure random bytes** (tạo bytes ngẫu nhiên bảo mật)
pub fn generate_random_bytes(size: usize) -> Result<Vec<u8>> {
    let rng = SystemRandom::new();
    let mut bytes = vec![0u8; size];
    
    rng.fill(&mut bytes)
        .context("Failed to generate random bytes")?;
    
    Ok(bytes)
}

/// **Generate secure random string** (tạo chuỗi ngẫu nhiên bảo mật)
pub fn generate_random_string(length: usize) -> Result<String> {
    const CHARSET: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    
    let rng = SystemRandom::new();
    let mut result = Vec::with_capacity(length);
    
    for _ in 0..length {
        let mut byte = [0u8; 1];
        rng.fill(&mut byte)
            .context("Failed to generate random byte")?;
        
        let idx = (byte[0] as usize) % CHARSET.len();
        result.push(CHARSET[idx]);
    }
    
    String::from_utf8(result)
        .context("Failed to create UTF-8 string")
}

/// **Secure memory for sensitive data** (bộ nhớ an toàn cho dữ liệu nhạy cảm)
#[derive(ZeroizeOnDrop)]
pub struct SecureBuffer {
    data: Vec<u8>,
}

impl SecureBuffer {
    /// **Create new secure buffer** (tạo buffer an toàn mới)
    pub fn new(size: usize) -> Self {
        Self {
            data: vec![0u8; size],
        }
    }
    
    /// **Create from data** (tạo từ dữ liệu)
    pub fn from_data(data: Vec<u8>) -> Self {
        Self { data }
    }
    
    /// **Get data as slice** (lấy dữ liệu dạng slice)
    pub fn as_slice(&self) -> &[u8] {
        &self.data
    }
    
    /// **Get mutable data** (lấy dữ liệu có thể thay đổi)
    pub fn as_mut_slice(&mut self) -> &mut [u8] {
        &mut self.data
    }
    
    /// **Get length** (lấy độ dài)
    pub fn len(&self) -> usize {
        self.data.len()
    }
    
    /// **Check if empty** (kiểm tra rỗng)
    pub fn is_empty(&self) -> bool {
        self.data.is_empty()
    }
    
    /// **Fill with random data** (điền dữ liệu ngẫu nhiên)
    pub fn fill_random(&mut self) -> Result<()> {
        let rng = SystemRandom::new();
        rng.fill(&mut self.data)
            .context("Failed to fill buffer with random data")
    }
    
    /// **Copy data into buffer** (sao chép dữ liệu vào buffer)
    pub fn copy_from_slice(&mut self, data: &[u8]) -> Result<()> {
        if data.len() != self.data.len() {
            anyhow::bail!("Data length mismatch: {} != {}", data.len(), self.data.len());
        }
        
        self.data.copy_from_slice(data);
        Ok(())
    }
}

impl std::fmt::Debug for SecureBuffer {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SecureBuffer")
            .field("len", &self.data.len())
            .field("data", &"<redacted>")
            .finish()
    }
}

/// **Hash data with SHA-256** (hash dữ liệu với SHA-256)
pub fn hash_data(data: &[u8]) -> [u8; 32] {
    use ring::digest;
    
    let digest = digest::digest(&digest::SHA256, data);
    let mut result = [0u8; 32];
    result.copy_from_slice(digest.as_ref());
    result
}

/// **Verify data hash** (xác minh hash dữ liệu)
pub fn verify_data_hash(data: &[u8], expected_hash: &[u8; 32]) -> bool {
    let actual_hash = hash_data(data);
    
    // Use constant-time comparison
    use ring::constant_time;
    constant_time::verify_slices_are_equal(&actual_hash, expected_hash).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_key_generation_and_encryption() -> Result<()> {
        let key = generate_key()?;
        let plaintext = b"Hello, secure world!";
        
        let encrypted = key.encrypt(plaintext)?;
        let decrypted = key.decrypt(&encrypted)?;
        
        assert_eq!(plaintext, &decrypted[..]);
        Ok(())
    }
    
    #[test]
    fn test_password_key_derivation() -> Result<()> {
        let password = "super_secure_password";
        let params = generate_key_derivation_params()?;
        
        let key1 = derive_key_from_password(password, &params)?;
        let key2 = derive_key_from_password(password, &params)?;
        
        // Keys derived from same password and params should work the same
        let plaintext = b"test data";
        let encrypted = key1.encrypt(plaintext)?;
        let decrypted = key2.decrypt(&encrypted)?;
        
        assert_eq!(plaintext, &decrypted[..]);
        Ok(())
    }
    
    #[test]
    fn test_secure_buffer() -> Result<()> {
        let mut buffer = SecureBuffer::new(32);
        buffer.fill_random()?;
        
        assert_eq!(buffer.len(), 32);
        assert!(!buffer.is_empty());
        
        // Buffer should be zeroized on drop
        Ok(())
    }
    
    #[test]
    fn test_random_generation() -> Result<()> {
        let bytes = generate_random_bytes(32)?;
        assert_eq!(bytes.len(), 32);
        
        let string = generate_random_string(16)?;
        assert_eq!(string.len(), 16);
        assert!(string.chars().all(|c| c.is_ascii_alphanumeric()));
        
        Ok(())
    }
    
    #[test]
    fn test_data_hashing() {
        let data = b"test data for hashing";
        let hash1 = hash_data(data);
        let hash2 = hash_data(data);
        
        assert_eq!(hash1, hash2);
        assert!(verify_data_hash(data, &hash1));
        
        let wrong_hash = [0u8; 32];
        assert!(!verify_data_hash(data, &wrong_hash));
    }
}
