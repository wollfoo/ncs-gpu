//! **Cryptography Utilities** (tiện ích mật mã – công cụ mã hóa)

use aes_gcm::{
    aead::{Aead, AeadCore, KeyInit, OsRng},
    Aes256Gcm, Key, Nonce,
};
use anyhow::{Context, Result};
use argon2::{
    password_hash::{rand_core::OsRng as ArgonOsRng, PasswordHash, PasswordHasher, PasswordVerifier, SaltString},
    Argon2,
};
use base64::{engine::general_purpose, Engine as _};
use ring::digest::{Context as DigestContext, SHA256};
use zeroize::Zeroize;

/// **Encryption key size** (kích thước khóa mã hóa – độ dài khóa bảo mật)
pub const KEY_SIZE: usize = 32; // 256 bits

/// **Nonce size** (kích thước nonce – độ dài số ngẫu nhiên)
pub const NONCE_SIZE: usize = 12; // 96 bits

/// **Encrypted data** (dữ liệu đã mã hóa – thông tin được bảo vệ)
#[derive(Debug, Clone)]
pub struct EncryptedData {
    /// Encrypted bytes
    pub ciphertext: Vec<u8>,
    /// Nonce used for encryption
    pub nonce: [u8; NONCE_SIZE],
}

impl Drop for EncryptedData {
    fn drop(&mut self) {
        self.ciphertext.zeroize();
        self.nonce.zeroize();
    }
}

/// **Generate random key** (tạo khóa ngẫu nhiên – sinh khóa bảo mật)
pub fn generate_key() -> [u8; KEY_SIZE] {
    let key = Aes256Gcm::generate_key(&mut OsRng);
    let mut key_bytes = [0u8; KEY_SIZE];
    key_bytes.copy_from_slice(&key);
    key_bytes
}

/// **Encrypt data** (mã hóa dữ liệu – bảo vệ thông tin)
pub fn encrypt(data: &[u8], key: &[u8; KEY_SIZE]) -> Result<EncryptedData> {
    let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(key));
    let nonce = Aes256Gcm::generate_nonce(&mut OsRng);
    
    let ciphertext = cipher
        .encrypt(&nonce, data)
        .context("Encryption failed")?;

    let mut nonce_bytes = [0u8; NONCE_SIZE];
    nonce_bytes.copy_from_slice(&nonce);

    Ok(EncryptedData {
        ciphertext,
        nonce: nonce_bytes,
    })
}

/// **Decrypt data** (giải mã dữ liệu – khôi phục thông tin)
pub fn decrypt(encrypted: &EncryptedData, key: &[u8; KEY_SIZE]) -> Result<Vec<u8>> {
    let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(key));
    let nonce = Nonce::from_slice(&encrypted.nonce);

    let plaintext = cipher
        .decrypt(nonce, encrypted.ciphertext.as_ref())
        .context("Decryption failed")?;

    Ok(plaintext)
}

/// **Hash data with SHA256** (băm dữ liệu với SHA256 – tạo mã băm)
pub fn hash(data: &[u8]) -> [u8; 32] {
    let mut context = DigestContext::new(&SHA256);
    context.update(data);
    let digest = context.finish();

    let mut hash_bytes = [0u8; 32];
    hash_bytes.copy_from_slice(digest.as_ref());
    hash_bytes
}

/// **Hash password with Argon2** (băm mật khẩu với Argon2 – mã hóa mật khẩu)
pub fn hash_password(password: &str) -> Result<String> {
    let salt = SaltString::generate(&mut ArgonOsRng);
    let argon2 = Argon2::default();

    let password_hash = argon2
        .hash_password(password.as_bytes(), &salt)
        .context("Failed to hash password")?;

    Ok(password_hash.to_string())
}

/// **Verify password** (xác minh mật khẩu – kiểm tra mật khẩu)
pub fn verify_password(password: &str, hash: &str) -> Result<bool> {
    let parsed_hash = PasswordHash::new(hash)
        .context("Failed to parse password hash")?;

    let argon2 = Argon2::default();
    
    match argon2.verify_password(password.as_bytes(), &parsed_hash) {
        Ok(()) => Ok(true),
        Err(_) => Ok(false),
    }
}

/// **Encode to base64** (mã hóa sang base64 – chuyển đổi định dạng)
pub fn encode_base64(data: &[u8]) -> String {
    general_purpose::STANDARD.encode(data)
}

/// **Decode from base64** (giải mã từ base64 – khôi phục định dạng)
pub fn decode_base64(encoded: &str) -> Result<Vec<u8>> {
    general_purpose::STANDARD
        .decode(encoded)
        .context("Failed to decode base64")
}

/// **Generate secure random bytes** (tạo byte ngẫu nhiên an toàn – sinh số ngẫu nhiên bảo mật)
pub fn random_bytes(size: usize) -> Vec<u8> {
    use rand::RngCore;
    let mut bytes = vec![0u8; size];
    OsRng.fill_bytes(&mut bytes);
    bytes
}

/// **Constant-time comparison** (so sánh thời gian hằng – kiểm tra an toàn)
pub fn secure_compare(a: &[u8], b: &[u8]) -> bool {
    use ring::constant_time::verify_slices_are_equal;
    verify_slices_are_equal(a, b).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encryption_decryption() {
        let key = generate_key();
        let data = b"Hello, Opus GPU!";

        let encrypted = encrypt(data, &key).unwrap();
        let decrypted = decrypt(&encrypted, &key).unwrap();

        assert_eq!(data, &decrypted[..]);
    }

    #[test]
    fn test_hash() {
        let data = b"Test data";
        let hash1 = hash(data);
        let hash2 = hash(data);

        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_password_hashing() {
        let password = "SecurePassword123!";
        let hash = hash_password(password).unwrap();

        assert!(verify_password(password, &hash).unwrap());
        assert!(!verify_password("WrongPassword", &hash).unwrap());
    }

    #[test]
    fn test_base64_encoding() {
        let data = b"Test encoding";
        let encoded = encode_base64(data);
        let decoded = decode_base64(&encoded).unwrap();

        assert_eq!(data, &decoded[..]);
    }
}