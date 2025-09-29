//! Mnemonic phrase management following BIP39 standard

use crate::{
    types::Mnemonic,
    WalletError, WalletResult,
};
use async_trait::async_trait;
use bip39::{Language, Mnemonic as Bip39Mnemonic};
use rand::{Rng, RngCore};
use std::collections::HashSet;
use zeroize::Zeroize;

/// Mnemonic management interface
#[async_trait]
pub trait MnemonicManagerTrait: Send + Sync {
    /// Generate new mnemonic phrase
    async fn generate_mnemonic(&self, word_count: usize) -> WalletResult<Mnemonic>;

    /// Generate mnemonic with specific language
    async fn generate_mnemonic_with_language(
        &self,
        word_count: usize,
        language: Language,
    ) -> WalletResult<Mnemonic>;

    /// Generate mnemonic from entropy
    async fn generate_from_entropy(&self, entropy: &[u8], language: Language) -> WalletResult<Mnemonic>;

    /// Validate mnemonic phrase
    async fn validate_mnemonic(&self, mnemonic: &Mnemonic) -> WalletResult<()>;

    /// Check mnemonic strength
    async fn check_strength(&self, mnemonic: &Mnemonic) -> WalletResult<MnemonicStrength>;

    /// Convert mnemonic to seed
    async fn mnemonic_to_seed(&self, mnemonic: &Mnemonic, passphrase: Option<&str>) -> WalletResult<Vec<u8>>;

    /// Get supported languages
    fn supported_languages(&self) -> Vec<Language>;

    /// Detect mnemonic language
    async fn detect_language(&self, phrase: &str) -> WalletResult<Language>;

    /// Normalize mnemonic phrase (trim, lowercase, etc.)
    fn normalize_phrase(&self, phrase: &str) -> String;

    /// Split phrase into words
    fn split_words(&self, phrase: &str) -> Vec<String>;

    /// Join words into phrase
    fn join_words(&self, words: &[String]) -> String;
}

/// Mnemonic phrase manager implementation
#[derive(Debug)]
pub struct MnemonicManager {
    /// Supported word counts (128, 160, 192, 224, 256 bits entropy)
    supported_word_counts: HashSet<usize>,
    /// Default language for mnemonic generation
    default_language: Language,
}

impl MnemonicManager {
    /// Create new mnemonic manager
    pub fn new() -> Self {
        let mut supported_word_counts = HashSet::new();
        supported_word_counts.insert(12); // 128 bits
        supported_word_counts.insert(15); // 160 bits
        supported_word_counts.insert(18); // 192 bits
        supported_word_counts.insert(21); // 224 bits
        supported_word_counts.insert(24); // 256 bits

        Self {
            supported_word_counts,
            default_language: Language::English,
        }
    }

    /// Create with custom configuration
    pub fn with_config(default_language: Language) -> Self {
        let mut manager = Self::new();
        manager.default_language = default_language;
        manager
    }

    /// Get entropy bits for word count
    fn entropy_bits_for_word_count(word_count: usize) -> WalletResult<usize> {
        match word_count {
            12 => Ok(128),
            15 => Ok(160),
            18 => Ok(192),
            21 => Ok(224),
            24 => Ok(256),
            _ => Err(WalletError::InvalidInput {
                message: format!("Unsupported word count: {}. Supported: 12, 15, 18, 21, 24", word_count),
            }),
        }
    }

    /// Generate secure random entropy
    fn generate_entropy(bits: usize) -> WalletResult<Vec<u8>> {
        if bits % 8 != 0 {
            return Err(WalletError::InvalidInput {
                message: "Entropy bits must be multiple of 8".to_string(),
            });
        }

        let bytes = bits / 8;
        let mut entropy = vec![0u8; bytes];

        let mut rng = rand::thread_rng();
        rng.fill_bytes(&mut entropy);

        // Ensure we don't have weak entropy (all zeros or all ones)
        if entropy.iter().all(|&x| x == 0) || entropy.iter().all(|&x| x == 0xFF) {
            // Generate new entropy
            rng.fill_bytes(&mut entropy);
        }

        Ok(entropy)
    }

    /// Validate entropy strength
    fn validate_entropy(entropy: &[u8]) -> WalletResult<()> {
        if entropy.is_empty() {
            return Err(WalletError::InvalidSeed {
                reason: "Entropy cannot be empty".to_string(),
            });
        }

        if entropy.len() < 16 || entropy.len() > 32 {
            return Err(WalletError::InvalidSeed {
                reason: "Entropy must be between 16 and 32 bytes".to_string(),
            });
        }

        // Check for weak entropy patterns
        if entropy.iter().all(|&x| x == entropy[0]) {
            return Err(WalletError::InvalidSeed {
                reason: "Entropy shows weak randomness pattern".to_string(),
            });
        }

        Ok(())
    }

    /// Calculate mnemonic checksum
    fn calculate_checksum(&self, entropy: &[u8]) -> u8 {
        use sha2::{Digest, Sha256};
        let hash = Sha256::digest(entropy);
        hash[0]
    }

    /// Validate mnemonic checksum
    fn validate_checksum(&self, mnemonic: &Bip39Mnemonic) -> WalletResult<()> {
        // BIP39 library handles checksum validation internally
        // This is a placeholder for additional validation if needed
        let _entropy = mnemonic.entropy();
        Ok(())
    }

    /// Get word list for language
    fn get_word_list(&self, language: Language) -> &'static [&'static str] {
        match language {
            Language::English => bip39::Language::English.word_list(),
            Language::Japanese => bip39::Language::Japanese.word_list(),
            Language::Korean => bip39::Language::Korean.word_list(),
            Language::Spanish => bip39::Language::Spanish.word_list(),
            Language::French => bip39::Language::French.word_list(),
            Language::Italian => bip39::Language::Italian.word_list(),
            Language::Czech => bip39::Language::Czech.word_list(),
            Language::Portuguese => bip39::Language::Portuguese.word_list(),
            Language::ChineseSimplified => bip39::Language::ChineseSimplified.word_list(),
            Language::ChineseTraditional => bip39::Language::ChineseTraditional.word_list(),
        }
    }
}

#[async_trait]
impl MnemonicManagerTrait for MnemonicManager {
    async fn generate_mnemonic(&self, word_count: usize) -> WalletResult<Mnemonic> {
        self.generate_mnemonic_with_language(word_count, self.default_language).await
    }

    async fn generate_mnemonic_with_language(
        &self,
        word_count: usize,
        language: Language,
    ) -> WalletResult<Mnemonic> {
        if !self.supported_word_counts.contains(&word_count) {
            return Err(WalletError::InvalidInput {
                message: format!("Unsupported word count: {}", word_count),
            });
        }

        let entropy_bits = Self::entropy_bits_for_word_count(word_count)?;
        let entropy = Self::generate_entropy(entropy_bits)?;

        self.generate_from_entropy(&entropy, language).await
    }

    async fn generate_from_entropy(&self, entropy: &[u8], language: Language) -> WalletResult<Mnemonic> {
        Self::validate_entropy(entropy)?;

        let bip39_mnemonic = Bip39Mnemonic::from_entropy(entropy, language)
            .map_err(|e| WalletError::MnemonicGenerationError {
                reason: e.to_string(),
            })?;

        let mnemonic = Mnemonic::from_phrase(
            bip39_mnemonic.phrase().to_string(),
            language,
        )?;

        Ok(mnemonic)
    }

    async fn validate_mnemonic(&self, mnemonic: &Mnemonic) -> WalletResult<()> {
        // First validate using our Mnemonic type
        mnemonic.validate()?;

        // Then validate using BIP39 library for additional checks
        let bip39_mnemonic = Bip39Mnemonic::from_phrase(mnemonic.phrase(), mnemonic.language())
            .map_err(|e| WalletError::InvalidMnemonic {
                reason: e.to_string(),
            })?;

        // Validate checksum
        self.validate_checksum(&bip39_mnemonic)?;

        Ok(())
    }

    async fn check_strength(&self, mnemonic: &Mnemonic) -> WalletResult<MnemonicStrength> {
        self.validate_mnemonic(mnemonic).await?;

        let words: Vec<&str> = mnemonic.phrase().split_whitespace().collect();
        let word_count = words.len();

        let strength = match word_count {
            12 => MnemonicStrength::Low,      // 128 bits
            15 => MnemonicStrength::Medium,   // 160 bits
            18 => MnemonicStrength::High,     // 192 bits
            21 => MnemonicStrength::VeryHigh, // 224 bits
            24 => MnemonicStrength::Maximum,  // 256 bits
            _ => return Err(WalletError::InvalidMnemonic {
                reason: format!("Invalid word count: {}", word_count),
            }),
        };

        Ok(strength)
    }

    async fn mnemonic_to_seed(&self, mnemonic: &Mnemonic, passphrase: Option<&str>) -> WalletResult<Vec<u8>> {
        let seed = mnemonic.to_seed(passphrase)?;
        Ok(seed.as_bytes().to_vec())
    }

    fn supported_languages(&self) -> Vec<Language> {
        vec![
            Language::English,
            Language::Japanese,
            Language::Korean,
            Language::Spanish,
            Language::French,
            Language::Italian,
            Language::Czech,
            Language::Portuguese,
            Language::ChineseSimplified,
            Language::ChineseTraditional,
        ]
    }

    async fn detect_language(&self, phrase: &str) -> WalletResult<Language> {
        let normalized_phrase = self.normalize_phrase(phrase);
        let words = self.split_words(&normalized_phrase);

        if words.is_empty() {
            return Err(WalletError::InvalidMnemonic {
                reason: "Empty mnemonic phrase".to_string(),
            });
        }

        // Try each language and see which one validates
        for language in self.supported_languages() {
            let word_list = self.get_word_list(language);
            let word_set: HashSet<&str> = word_list.iter().copied().collect();

            // Check if all words exist in this language's word list
            let matches = words.iter()
                .filter(|word| word_set.contains(word.as_str()))
                .count();

            // If majority of words match (>75%), consider it this language
            if matches as f32 / words.len() as f32 > 0.75 {
                // Verify by trying to create a mnemonic
                if Bip39Mnemonic::from_phrase(&normalized_phrase, language).is_ok() {
                    return Ok(language);
                }
            }
        }

        // Default to English if detection fails
        Ok(Language::English)
    }

    fn normalize_phrase(&self, phrase: &str) -> String {
        phrase.trim()
            .to_lowercase()
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(" ")
    }

    fn split_words(&self, phrase: &str) -> Vec<String> {
        phrase.split_whitespace()
            .map(|word| word.to_string())
            .collect()
    }

    fn join_words(&self, words: &[String]) -> String {
        words.join(" ")
    }
}

/// Mnemonic strength levels based on entropy bits
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MnemonicStrength {
    /// 128 bits entropy (12 words)
    Low,
    /// 160 bits entropy (15 words)
    Medium,
    /// 192 bits entropy (18 words)
    High,
    /// 224 bits entropy (21 words)
    VeryHigh,
    /// 256 bits entropy (24 words)
    Maximum,
}

impl MnemonicStrength {
    pub fn entropy_bits(&self) -> usize {
        match self {
            MnemonicStrength::Low => 128,
            MnemonicStrength::Medium => 160,
            MnemonicStrength::High => 192,
            MnemonicStrength::VeryHigh => 224,
            MnemonicStrength::Maximum => 256,
        }
    }

    pub fn word_count(&self) -> usize {
        match self {
            MnemonicStrength::Low => 12,
            MnemonicStrength::Medium => 15,
            MnemonicStrength::High => 18,
            MnemonicStrength::VeryHigh => 21,
            MnemonicStrength::Maximum => 24,
        }
    }

    pub fn security_level(&self) -> &'static str {
        match self {
            MnemonicStrength::Low => "Adequate for most use cases",
            MnemonicStrength::Medium => "Good security level",
            MnemonicStrength::High => "High security level",
            MnemonicStrength::VeryHigh => "Very high security level",
            MnemonicStrength::Maximum => "Maximum security level",
        }
    }
}

impl std::fmt::Display for MnemonicStrength {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MnemonicStrength::Low => write!(f, "Low (128-bit)"),
            MnemonicStrength::Medium => write!(f, "Medium (160-bit)"),
            MnemonicStrength::High => write!(f, "High (192-bit)"),
            MnemonicStrength::VeryHigh => write!(f, "Very High (224-bit)"),
            MnemonicStrength::Maximum => write!(f, "Maximum (256-bit)"),
        }
    }
}

/// Secure mnemonic phrase generator with additional entropy sources
pub struct SecureMnemonicGenerator {
    additional_entropy_sources: Vec<Box<dyn EntropySource>>,
}

impl SecureMnemonicGenerator {
    pub fn new() -> Self {
        Self {
            additional_entropy_sources: Vec::new(),
        }
    }

    pub fn add_entropy_source(&mut self, source: Box<dyn EntropySource>) {
        self.additional_entropy_sources.push(source);
    }

    pub fn generate_with_additional_entropy(
        &self,
        word_count: usize,
        language: Language,
    ) -> WalletResult<Mnemonic> {
        let entropy_bits = MnemonicManager::entropy_bits_for_word_count(word_count)?;
        let mut entropy = MnemonicManager::generate_entropy(entropy_bits)?;

        // Mix in additional entropy sources
        for source in &self.additional_entropy_sources {
            let additional = source.get_entropy()?;
            self.mix_entropy(&mut entropy, &additional);
        }

        let manager = MnemonicManager::new();
        futures::executor::block_on(manager.generate_from_entropy(&entropy, language))
    }

    fn mix_entropy(&self, base: &mut [u8], additional: &[u8]) {
        for (i, &byte) in additional.iter().enumerate() {
            if i < base.len() {
                base[i] ^= byte;
            }
        }
    }
}

/// Trait for additional entropy sources
pub trait EntropySource: Send + Sync {
    fn get_entropy(&self) -> WalletResult<Vec<u8>>;
}

/// System entropy source (uses OS random number generator)
pub struct SystemEntropySource;

impl EntropySource for SystemEntropySource {
    fn get_entropy(&self) -> WalletResult<Vec<u8>> {
        let mut entropy = vec![0u8; 32];
        rand::RngCore::fill_bytes(&mut rand::thread_rng(), &mut entropy);
        Ok(entropy)
    }
}

/// Time-based entropy source
pub struct TimeEntropySource;

impl EntropySource for TimeEntropySource {
    fn get_entropy(&self) -> WalletResult<Vec<u8>> {
        use std::time::{SystemTime, UNIX_EPOCH};

        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| WalletError::InternalError {
                message: "Failed to get system time".to_string(),
            })?;

        let nanos = timestamp.as_nanos() as u64;
        Ok(nanos.to_be_bytes().to_vec())
    }
}

impl Default for MnemonicManager {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for MnemonicManager {
    fn drop(&mut self) {
        // Secure cleanup if needed
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_mnemonic_generation() {
        let manager = MnemonicManager::new();

        for &word_count in &[12, 15, 18, 21, 24] {
            let mnemonic = manager.generate_mnemonic(word_count).await.unwrap();
            assert_eq!(mnemonic.phrase().split_whitespace().count(), word_count);
            assert!(manager.validate_mnemonic(&mnemonic).await.is_ok());
        }
    }

    #[tokio::test]
    async fn test_mnemonic_languages() {
        let manager = MnemonicManager::new();
        let languages = manager.supported_languages();

        for language in languages {
            let mnemonic = manager.generate_mnemonic_with_language(12, language).await.unwrap();
            assert_eq!(mnemonic.language(), language);
            assert!(manager.validate_mnemonic(&mnemonic).await.is_ok());
        }
    }

    #[tokio::test]
    async fn test_mnemonic_strength() {
        let manager = MnemonicManager::new();

        let test_cases = vec![
            (12, MnemonicStrength::Low),
            (15, MnemonicStrength::Medium),
            (18, MnemonicStrength::High),
            (21, MnemonicStrength::VeryHigh),
            (24, MnemonicStrength::Maximum),
        ];

        for (word_count, expected_strength) in test_cases {
            let mnemonic = manager.generate_mnemonic(word_count).await.unwrap();
            let strength = manager.check_strength(&mnemonic).await.unwrap();
            assert_eq!(strength, expected_strength);
        }
    }

    #[tokio::test]
    async fn test_mnemonic_to_seed() {
        let manager = MnemonicManager::new();
        let mnemonic = manager.generate_mnemonic(12).await.unwrap();

        let seed1 = manager.mnemonic_to_seed(&mnemonic, None).await.unwrap();
        let seed2 = manager.mnemonic_to_seed(&mnemonic, Some("passphrase")).await.unwrap();

        assert_eq!(seed1.len(), 64); // SHA512 output
        assert_eq!(seed2.len(), 64);
        assert_ne!(seed1, seed2); // Different passphrase should produce different seed
    }

    #[tokio::test]
    async fn test_entropy_validation() {
        let weak_entropy = vec![0u8; 16]; // All zeros
        let result = MnemonicManager::validate_entropy(&weak_entropy);
        assert!(result.is_err());

        let good_entropy = vec![1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16];
        let result = MnemonicManager::validate_entropy(&good_entropy);
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_phrase_normalization() {
        let manager = MnemonicManager::new();

        let original = "  ABANDON   ability   ABLE   about  ";
        let normalized = manager.normalize_phrase(original);
        assert_eq!(normalized, "abandon ability able about");

        let words = manager.split_words(&normalized);
        assert_eq!(words, vec!["abandon", "ability", "able", "about"]);

        let rejoined = manager.join_words(&words);
        assert_eq!(rejoined, normalized);
    }

    #[test]
    fn test_mnemonic_strength_properties() {
        assert_eq!(MnemonicStrength::Low.entropy_bits(), 128);
        assert_eq!(MnemonicStrength::Low.word_count(), 12);

        assert_eq!(MnemonicStrength::Maximum.entropy_bits(), 256);
        assert_eq!(MnemonicStrength::Maximum.word_count(), 24);
    }

    #[test]
    fn test_secure_mnemonic_generator() {
        let mut generator = SecureMnemonicGenerator::new();
        generator.add_entropy_source(Box::new(SystemEntropySource));
        generator.add_entropy_source(Box::new(TimeEntropySource));

        let mnemonic = generator.generate_with_additional_entropy(12, Language::English);
        assert!(mnemonic.is_ok());

        let mnemonic = mnemonic.unwrap();
        assert_eq!(mnemonic.phrase().split_whitespace().count(), 12);
    }
}