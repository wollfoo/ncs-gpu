//! String Obfuscation Module
//!
//! Provides compile-time and runtime string encryption to protect
//! sensitive string literals from static analysis.

use crate::{ObfuscationError, ObfuscationResult, SourceType};
use anyhow::Result;
use std::collections::HashMap;
use tracing::{debug, warn};
use rand::Rng;
use aes::Aes256;
use cbc::{Decryptor, Encryptor};
use block_modes::{BlockMode, Cbc};

type Aes256Cbc = Cbc<Aes256, cbc::block_padding::Pkcs7>;

/// String obfuscation manager
pub struct StringObfuscator {
    strength: u8,
    encryption_key: [u8; 32],
    obfuscation_patterns: HashMap<String, String>,
}

impl StringObfuscator {
    pub fn new(strength: u8) -> Result<Self> {
        let mut key = [0u8; 32];
        rand::thread_rng().fill(&mut key);

        Ok(Self {
            strength,
            encryption_key: key,
            obfuscation_patterns: HashMap::new(),
        })
    }

    /// Obfuscate strings in source code
    pub async fn obfuscate_strings(&self, source: &str, file_type: SourceType) -> Result<String> {
        match file_type {
            SourceType::Rust => self.obfuscate_rust_strings(source).await,
            SourceType::C | SourceType::Cpp => self.obfuscate_c_strings(source).await,
            _ => Ok(source.to_string()),
        }
    }

    /// Obfuscate Rust string literals
    async fn obfuscate_rust_strings(&self, source: &str) -> Result<String> {
        debug!("Obfuscating Rust strings with strength {}", self.strength);

        let mut obfuscated = source.to_string();

        // Find string literals and replace with obfuscated versions
        let string_regex = regex::Regex::new(r#""([^"\\]*(\\.[^"\\]*)*)""#).unwrap();

        for capture in string_regex.captures_iter(source) {
            if let Some(string_match) = capture.get(0) {
                let original = string_match.as_str();
                let inner = &original[1..original.len()-1]; // Remove quotes

                // Skip empty strings or very short ones
                if inner.len() < 3 {
                    continue;
                }

                // Skip if it looks like a format string or debug string
                if inner.contains("{}") || inner.starts_with("ERROR") ||
                   inner.starts_with("WARN") || inner.starts_with("DEBUG") {
                    continue;
                }

                let obfuscated_call = self.generate_obfuscated_string_call(inner)?;
                obfuscated = obfuscated.replace(original, &obfuscated_call);
            }
        }

        Ok(obfuscated)
    }

    /// Obfuscate C/C++ string literals
    async fn obfuscate_c_strings(&self, source: &str) -> Result<String> {
        debug!("Obfuscating C/C++ strings with strength {}", self.strength);

        let mut obfuscated = source.to_string();

        // Find string literals
        let string_regex = regex::Regex::new(r#""([^"\\]*(\\.[^"\\]*)*)""#).unwrap();

        for capture in string_regex.captures_iter(source) {
            if let Some(string_match) = capture.get(0) {
                let original = string_match.as_str();
                let inner = &original[1..original.len()-1];

                if inner.len() < 3 {
                    continue;
                }

                let obfuscated_call = self.generate_c_obfuscated_string(inner)?;
                obfuscated = obfuscated.replace(original, &obfuscated_call);
            }
        }

        Ok(obfuscated)
    }

    /// Generate obfuscated string call for Rust
    fn generate_obfuscated_string_call(&self, original: &str) -> Result<String> {
        match self.strength {
            1..=3 => self.simple_char_obfuscation(original),
            4..=6 => self.xor_obfuscation(original),
            7..=8 => self.base64_obfuscation(original),
            9..=10 => self.aes_obfuscation(original),
            _ => Ok(format!("\"{}\"", original)),
        }
    }

    /// Simple character-based obfuscation
    fn simple_char_obfuscation(&self, s: &str) -> Result<String> {
        let chars: Vec<String> = s.chars()
            .map(|c| {
                let shifted = ((c as u8).wrapping_add(1)) as char;
                format!("'{}' as u8 - 1", shifted)
            })
            .collect();

        Ok(format!(
            "String::from_utf8(vec![{}]).unwrap()",
            chars.join(", ")
        ))
    }

    /// XOR-based obfuscation
    fn xor_obfuscation(&self, s: &str) -> Result<String> {
        let key = rand::thread_rng().gen::<u8>();
        let xored: Vec<String> = s.bytes()
            .map(|b| format!("{}", b ^ key))
            .collect();

        Ok(format!(
            "String::from_utf8({}.iter().map(|&b| b ^ {}).collect()).unwrap()",
            format!("vec![{}]", xored.join(", ")),
            key
        ))
    }

    /// Base64 obfuscation with simple encoding
    fn base64_obfuscation(&self, s: &str) -> Result<String> {
        let encoded = base64::encode(s.as_bytes());
        Ok(format!(
            "String::from_utf8(base64::decode(\"{}\").unwrap()).unwrap()",
            encoded
        ))
    }

    /// AES encryption obfuscation
    fn aes_obfuscation(&self, s: &str) -> Result<String> {
        let encrypted = self.encrypt_string(s)?;
        let key_array = self.encryption_key
            .iter()
            .map(|b| format!("{}", b))
            .collect::<Vec<_>>()
            .join(", ");

        let encrypted_array = encrypted
            .iter()
            .map(|b| format!("{}", b))
            .collect::<Vec<_>>()
            .join(", ");

        Ok(format!(
            "decrypt_string(&[{}], &[{}])",
            key_array,
            encrypted_array
        ))
    }

    /// Generate obfuscated string for C/C++
    fn generate_c_obfuscated_string(&self, original: &str) -> Result<String> {
        match self.strength {
            1..=5 => self.c_char_array_obfuscation(original),
            6..=10 => self.c_xor_obfuscation(original),
            _ => Ok(format!("\"{}\"", original)),
        }
    }

    /// C character array obfuscation
    fn c_char_array_obfuscation(&self, s: &str) -> Result<String> {
        let chars: Vec<String> = s.chars()
            .map(|c| format!("{}", (c as u8).wrapping_add(1)))
            .collect();

        Ok(format!(
            "deobfuscate_chars((unsigned char[]){{{}}})",
            chars.join(", ")
        ))
    }

    /// C XOR obfuscation
    fn c_xor_obfuscation(&self, s: &str) -> Result<String> {
        let key = rand::thread_rng().gen::<u8>();
        let xored: Vec<String> = s.bytes()
            .map(|b| format!("{}", b ^ key))
            .collect();

        Ok(format!(
            "deobfuscate_xor((unsigned char[]){{{}}, {}})",
            xored.join(", "),
            key
        ))
    }

    /// Encrypt string using AES
    fn encrypt_string(&self, plaintext: &str) -> Result<Vec<u8>> {
        let iv: [u8; 16] = rand::thread_rng().gen();
        let cipher = Aes256Cbc::new_from_slices(&self.encryption_key, &iv)
            .map_err(|e| ObfuscationError::StringObfuscation(format!("Cipher creation failed: {}", e)))?;

        let mut buffer = plaintext.as_bytes().to_vec();
        let encrypted = cipher.encrypt(&mut buffer)
            .map_err(|e| ObfuscationError::StringObfuscation(format!("Encryption failed: {}", e)))?;

        // Prepend IV to encrypted data
        let mut result = iv.to_vec();
        result.extend_from_slice(encrypted);
        Ok(result)
    }

    /// Decrypt string using AES (for runtime)
    pub fn decrypt_string(&self, key: &[u8; 32], encrypted_with_iv: &[u8]) -> Result<String> {
        if encrypted_with_iv.len() < 16 {
            return Err(ObfuscationError::StringObfuscation("Invalid encrypted data".to_string()).into());
        }

        let (iv, encrypted) = encrypted_with_iv.split_at(16);
        let cipher = Aes256Cbc::new_from_slices(key, iv)
            .map_err(|e| ObfuscationError::StringObfuscation(format!("Cipher creation failed: {}", e)))?;

        let mut buffer = encrypted.to_vec();
        let decrypted = cipher.decrypt(&mut buffer)
            .map_err(|e| ObfuscationError::StringObfuscation(format!("Decryption failed: {}", e)))?;

        String::from_utf8(decrypted)
            .map_err(|e| ObfuscationError::StringObfuscation(format!("UTF-8 conversion failed: {}", e)).into())
    }
}

/// Runtime string deobfuscation utilities
pub mod runtime {
    use super::*;

    /// Decrypt AES-encrypted string at runtime
    pub fn decrypt_string(key: &[u8], encrypted_with_iv: &[u8]) -> String {
        if encrypted_with_iv.len() < 16 {
            return String::new();
        }

        let (iv, encrypted) = encrypted_with_iv.split_at(16);

        if let Ok(cipher) = Aes256Cbc::new_from_slices(key, iv) {
            let mut buffer = encrypted.to_vec();
            if let Ok(decrypted) = cipher.decrypt(&mut buffer) {
                if let Ok(string) = String::from_utf8(decrypted) {
                    return string;
                }
            }
        }

        String::new()
    }

    /// Deobfuscate character array (C-style)
    #[no_mangle]
    pub extern "C" fn deobfuscate_chars(chars: *const u8) -> *const i8 {
        // Implementation would depend on the specific obfuscation
        std::ptr::null()
    }

    /// Deobfuscate XOR-encrypted string (C-style)
    #[no_mangle]
    pub extern "C" fn deobfuscate_xor(encrypted: *const u8, key: u8) -> *const i8 {
        // Implementation would depend on the specific obfuscation
        std::ptr::null()
    }
}

/// Compile-time string obfuscation macros
#[macro_export]
macro_rules! obf_str {
    ($s:literal) => {{
        const ENCRYPTED: &[u8] = &encrypt_at_compile_time!($s);
        runtime::decrypt_string(&ENCRYPTION_KEY, ENCRYPTED)
    }};
}

/// Macro for simple XOR obfuscation
#[macro_export]
macro_rules! xor_str {
    ($s:literal) => {{
        const KEY: u8 = $crate::strings::generate_compile_time_key();
        const ENCRYPTED: &[u8] = &$crate::strings::xor_encrypt_compile_time!($s, KEY);
        $crate::strings::runtime::xor_decrypt(ENCRYPTED, KEY)
    }};
}

/// Generate compile-time encryption key
pub const fn generate_compile_time_key() -> u8 {
    // Simple compile-time key generation
    42u8
}

/// XOR decrypt at runtime
pub fn xor_decrypt(encrypted: &[u8], key: u8) -> String {
    let decrypted: Vec<u8> = encrypted.iter().map(|&b| b ^ key).collect();
    String::from_utf8(decrypted).unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_string_obfuscator() {
        let obfuscator = StringObfuscator::new(5).unwrap();

        let source = r#"
            let message = "Hello, World!";
            println!("Debug message");
        "#;

        let obfuscated = obfuscator.obfuscate_strings(source, SourceType::Rust).await.unwrap();
        assert_ne!(source, obfuscated);
        assert!(obfuscated.contains("Hello, World!") ||
                obfuscated.contains("String::from_utf8"));
    }

    #[test]
    fn test_simple_char_obfuscation() {
        let obfuscator = StringObfuscator::new(1).unwrap();
        let result = obfuscator.simple_char_obfuscation("test").unwrap();
        assert!(result.contains("String::from_utf8"));
    }

    #[test]
    fn test_xor_obfuscation() {
        let obfuscator = StringObfuscator::new(5).unwrap();
        let result = obfuscator.xor_obfuscation("test").unwrap();
        assert!(result.contains("map(|&b| b ^"));
    }

    #[test]
    fn test_encrypt_decrypt_string() {
        let obfuscator = StringObfuscator::new(10).unwrap();
        let original = "test string";

        let encrypted = obfuscator.encrypt_string(original).unwrap();
        let decrypted = obfuscator.decrypt_string(&obfuscator.encryption_key, &encrypted).unwrap();

        assert_eq!(original, decrypted);
    }
}