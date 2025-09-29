//! Password management and validation

use crate::{types::SecurityConfig, WalletError, WalletResult};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// Password strength levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum PasswordStrength {
    VeryWeak,
    Weak,
    Fair,
    Good,
    Strong,
    VeryStrong,
}

impl PasswordStrength {
    /// Get numeric score (0-100)
    pub fn score(&self) -> u8 {
        match self {
            PasswordStrength::VeryWeak => 10,
            PasswordStrength::Weak => 25,
            PasswordStrength::Fair => 40,
            PasswordStrength::Good => 60,
            PasswordStrength::Strong => 80,
            PasswordStrength::VeryStrong => 100,
        }
    }

    /// Get description
    pub fn description(&self) -> &'static str {
        match self {
            PasswordStrength::VeryWeak => "Very weak - not recommended",
            PasswordStrength::Weak => "Weak - consider strengthening",
            PasswordStrength::Fair => "Fair - acceptable for low security",
            PasswordStrength::Good => "Good - recommended minimum",
            PasswordStrength::Strong => "Strong - good security",
            PasswordStrength::VeryStrong => "Very strong - excellent security",
        }
    }

    /// Check if strength meets minimum requirement
    pub fn meets_minimum(&self, minimum: PasswordStrength) -> bool {
        *self >= minimum
    }
}

impl std::fmt::Display for PasswordStrength {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PasswordStrength::VeryWeak => write!(f, "Very Weak"),
            PasswordStrength::Weak => write!(f, "Weak"),
            PasswordStrength::Fair => write!(f, "Fair"),
            PasswordStrength::Good => write!(f, "Good"),
            PasswordStrength::Strong => write!(f, "Strong"),
            PasswordStrength::VeryStrong => write!(f, "Very Strong"),
        }
    }
}

/// Password policy configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PasswordPolicy {
    /// Minimum password length
    pub min_length: usize,
    /// Maximum password length
    pub max_length: usize,
    /// Require uppercase letters
    pub require_uppercase: bool,
    /// Require lowercase letters
    pub require_lowercase: bool,
    /// Require digits
    pub require_digits: bool,
    /// Require special characters
    pub require_special: bool,
    /// Minimum strength requirement
    pub min_strength: PasswordStrength,
    /// Disallow common passwords
    pub disallow_common: bool,
    /// Disallow personal information
    pub disallow_personal: bool,
    /// Maximum repeated characters
    pub max_repeated: usize,
}

impl Default for PasswordPolicy {
    fn default() -> Self {
        Self {
            min_length: 12,
            max_length: 128,
            require_uppercase: true,
            require_lowercase: true,
            require_digits: true,
            require_special: true,
            min_strength: PasswordStrength::Good,
            disallow_common: true,
            disallow_personal: true,
            max_repeated: 3,
        }
    }
}

impl PasswordPolicy {
    /// Create password policy from security config
    pub fn from_config(config: &SecurityConfig) -> Self {
        Self {
            min_length: 12,
            max_length: 128,
            require_uppercase: true,
            require_lowercase: true,
            require_digits: true,
            require_special: true,
            min_strength: PasswordStrength::Good,
            disallow_common: true,
            disallow_personal: true,
            max_repeated: 3,
        }
    }

    /// Create relaxed policy for testing
    pub fn relaxed() -> Self {
        Self {
            min_length: 8,
            max_length: 128,
            require_uppercase: false,
            require_lowercase: true,
            require_digits: false,
            require_special: false,
            min_strength: PasswordStrength::Fair,
            disallow_common: false,
            disallow_personal: false,
            max_repeated: 5,
        }
    }

    /// Create strict policy for high security
    pub fn strict() -> Self {
        Self {
            min_length: 16,
            max_length: 128,
            require_uppercase: true,
            require_lowercase: true,
            require_digits: true,
            require_special: true,
            min_strength: PasswordStrength::Strong,
            disallow_common: true,
            disallow_personal: true,
            max_repeated: 2,
        }
    }
}

/// Password manager for validation and strength checking
#[derive(Debug)]
pub struct PasswordManager {
    policy: PasswordPolicy,
    common_passwords: HashSet<String>,
}

impl PasswordManager {
    /// Create new password manager
    pub fn new(policy: PasswordPolicy) -> Self {
        let common_passwords = Self::load_common_passwords();
        Self {
            policy,
            common_passwords,
        }
    }

    /// Load common passwords list
    fn load_common_passwords() -> HashSet<String> {
        let mut passwords = HashSet::new();

        // Add most common passwords
        let common = [
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "1234567890", "abc123",
            "password1", "123456789", "welcome123", "admin123", "root",
            "guest", "user", "test", "demo", "temp", "bitcoin", "wallet",
            "crypto", "ethereum", "blockchain", "satoshi", "hodl",
            "mining", "gpu", "opus", "secret", "private", "key",
        ];

        for password in &common {
            passwords.insert(password.to_lowercase());
        }

        passwords
    }

    /// Check password strength
    pub fn check_strength(&self, password: &str) -> WalletResult<PasswordStrength> {
        let mut score = 0;

        // Length scoring
        match password.len() {
            0..=4 => score += 0,
            5..=7 => score += 10,
            8..=11 => score += 20,
            12..=15 => score += 30,
            16..=19 => score += 40,
            _ => score += 50,
        }

        // Character diversity
        let has_lower = password.chars().any(|c| c.is_ascii_lowercase());
        let has_upper = password.chars().any(|c| c.is_ascii_uppercase());
        let has_digit = password.chars().any(|c| c.is_ascii_digit());
        let has_special = password.chars().any(|c| !c.is_alphanumeric());

        if has_lower { score += 5; }
        if has_upper { score += 5; }
        if has_digit { score += 5; }
        if has_special { score += 10; }

        // Bonus for having all character types
        if has_lower && has_upper && has_digit && has_special {
            score += 10;
        }

        // Character set size bonus
        let unique_chars: HashSet<char> = password.chars().collect();
        match unique_chars.len() {
            0..=5 => {},
            6..=10 => score += 5,
            11..=15 => score += 10,
            _ => score += 15,
        }

        // Pattern penalties
        if self.has_common_patterns(password) {
            score = score.saturating_sub(20);
        }

        if self.has_repeated_characters(password) {
            score = score.saturating_sub(10);
        }

        if self.common_passwords.contains(&password.to_lowercase()) {
            score = score.saturating_sub(30);
        }

        // Sequential characters penalty
        if self.has_sequential_characters(password) {
            score = score.saturating_sub(10);
        }

        let strength = match score {
            0..=20 => PasswordStrength::VeryWeak,
            21..=40 => PasswordStrength::Weak,
            41..=60 => PasswordStrength::Fair,
            61..=80 => PasswordStrength::Good,
            81..=95 => PasswordStrength::Strong,
            _ => PasswordStrength::VeryStrong,
        };

        Ok(strength)
    }

    /// Validate password against policy
    pub fn validate_password(&self, password: &str) -> WalletResult<()> {
        // Check length
        if password.len() < self.policy.min_length {
            return Err(WalletError::SecurityPolicyViolation {
                reason: format!("Password must be at least {} characters", self.policy.min_length),
            });
        }

        if password.len() > self.policy.max_length {
            return Err(WalletError::SecurityPolicyViolation {
                reason: format!("Password must be at most {} characters", self.policy.max_length),
            });
        }

        // Check character requirements
        if self.policy.require_uppercase && !password.chars().any(|c| c.is_ascii_uppercase()) {
            return Err(WalletError::SecurityPolicyViolation {
                reason: "Password must contain uppercase letters".to_string(),
            });
        }

        if self.policy.require_lowercase && !password.chars().any(|c| c.is_ascii_lowercase()) {
            return Err(WalletError::SecurityPolicyViolation {
                reason: "Password must contain lowercase letters".to_string(),
            });
        }

        if self.policy.require_digits && !password.chars().any(|c| c.is_ascii_digit()) {
            return Err(WalletError::SecurityPolicyViolation {
                reason: "Password must contain digits".to_string(),
            });
        }

        if self.policy.require_special && !password.chars().any(|c| !c.is_alphanumeric()) {
            return Err(WalletError::SecurityPolicyViolation {
                reason: "Password must contain special characters".to_string(),
            });
        }

        // Check common passwords
        if self.policy.disallow_common && self.common_passwords.contains(&password.to_lowercase()) {
            return Err(WalletError::SecurityPolicyViolation {
                reason: "Password is too common".to_string(),
            });
        }

        // Check repeated characters
        if self.has_too_many_repeated_characters(password) {
            return Err(WalletError::SecurityPolicyViolation {
                reason: format!("Password has too many repeated characters (max {})", self.policy.max_repeated),
            });
        }

        // Check strength requirement
        let strength = self.check_strength(password)?;
        if !strength.meets_minimum(self.policy.min_strength) {
            return Err(WalletError::SecurityPolicyViolation {
                reason: format!("Password strength {} is below minimum {}", strength, self.policy.min_strength),
            });
        }

        Ok(())
    }

    /// Generate password suggestions
    pub fn generate_suggestions(&self, base_length: usize) -> Vec<String> {
        let mut suggestions = Vec::new();

        // Generate a few different patterns
        for i in 0..3 {
            let suggestion = self.generate_password(base_length + i * 2);
            suggestions.push(suggestion);
        }

        suggestions
    }

    /// Generate random password that meets policy
    pub fn generate_password(&self, length: usize) -> String {
        use rand::{Rng, thread_rng};

        let length = length.max(self.policy.min_length).min(self.policy.max_length);
        let mut rng = thread_rng();
        let mut password = String::new();

        // Character sets
        let lowercase = "abcdefghijklmnopqrstuvwxyz";
        let uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
        let digits = "0123456789";
        let special = "!@#$%^&*()_+-=[]{}|;:,.<>?";

        let mut char_sets = Vec::new();

        if self.policy.require_lowercase { char_sets.push(lowercase); }
        if self.policy.require_uppercase { char_sets.push(uppercase); }
        if self.policy.require_digits { char_sets.push(digits); }
        if self.policy.require_special { char_sets.push(special); }

        // If no requirements, use all sets
        if char_sets.is_empty() {
            char_sets.extend_from_slice(&[lowercase, uppercase, digits, special]);
        }

        // First, ensure we have at least one character from each required set
        for &char_set in &char_sets {
            if password.len() < length {
                let chars: Vec<char> = char_set.chars().collect();
                let ch = chars[rng.gen_range(0..chars.len())];
                password.push(ch);
            }
        }

        // Fill remaining length with random characters from all sets
        let all_chars: String = char_sets.join("");
        let all_chars: Vec<char> = all_chars.chars().collect();

        while password.len() < length {
            let ch = all_chars[rng.gen_range(0..all_chars.len())];
            password.push(ch);
        }

        // Shuffle the password
        let mut chars: Vec<char> = password.chars().collect();
        for i in 0..chars.len() {
            let j = rng.gen_range(0..chars.len());
            chars.swap(i, j);
        }

        chars.into_iter().collect()
    }

    /// Check for common patterns
    fn has_common_patterns(&self, password: &str) -> bool {
        let lower = password.to_lowercase();

        // Common patterns
        let patterns = [
            "123", "abc", "qwe", "asd", "zxc", "password", "admin",
            "login", "user", "guest", "welcome", "secret",
        ];

        patterns.iter().any(|&pattern| lower.contains(pattern))
    }

    /// Check for repeated characters
    fn has_repeated_characters(&self, password: &str) -> bool {
        let chars: Vec<char> = password.chars().collect();

        for window in chars.windows(3) {
            if window[0] == window[1] && window[1] == window[2] {
                return true;
            }
        }

        false
    }

    /// Check for too many repeated characters
    fn has_too_many_repeated_characters(&self, password: &str) -> bool {
        let chars: Vec<char> = password.chars().collect();
        let mut count = 1;
        let mut max_count = 1;

        for i in 1..chars.len() {
            if chars[i] == chars[i-1] {
                count += 1;
                max_count = max_count.max(count);
            } else {
                count = 1;
            }
        }

        max_count > self.policy.max_repeated
    }

    /// Check for sequential characters
    fn has_sequential_characters(&self, password: &str) -> bool {
        let chars: Vec<char> = password.chars().collect();

        for window in chars.windows(3) {
            let c1 = window[0] as u8;
            let c2 = window[1] as u8;
            let c3 = window[2] as u8;

            // Check for ascending sequence
            if c2 == c1 + 1 && c3 == c2 + 1 {
                return true;
            }

            // Check for descending sequence
            if c2 == c1.saturating_sub(1) && c3 == c2.saturating_sub(1) {
                return true;
            }
        }

        false
    }

    /// Get password policy
    pub fn policy(&self) -> &PasswordPolicy {
        &self.policy
    }

    /// Update password policy
    pub fn update_policy(&mut self, policy: PasswordPolicy) {
        self.policy = policy;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_password_strength() {
        let manager = PasswordManager::new(PasswordPolicy::default());

        // Very weak passwords
        assert_eq!(manager.check_strength("123").unwrap(), PasswordStrength::VeryWeak);
        assert_eq!(manager.check_strength("password").unwrap(), PasswordStrength::VeryWeak);

        // Weak passwords
        assert_eq!(manager.check_strength("password1").unwrap(), PasswordStrength::Weak);

        // Good passwords
        assert!(manager.check_strength("MySecurePass123!").unwrap() >= PasswordStrength::Good);

        // Strong passwords
        assert!(manager.check_strength("Th!s1sAV3ryStr0ngP@ssw0rd").unwrap() >= PasswordStrength::Strong);
    }

    #[test]
    fn test_password_validation() {
        let manager = PasswordManager::new(PasswordPolicy::default());

        // Too short
        assert!(manager.validate_password("short").is_err());

        // Missing requirements
        assert!(manager.validate_password("alllowercase12345").is_err()); // No uppercase
        assert!(manager.validate_password("ALLUPPERCASE12345").is_err()); // No lowercase
        assert!(manager.validate_password("NoDigitsHere!").is_err()); // No digits
        assert!(manager.validate_password("NoSpecialChars123").is_err()); // No special chars

        // Common password
        assert!(manager.validate_password("password123").is_err());

        // Valid password
        assert!(manager.validate_password("MySecurePass123!").is_ok());
    }

    #[test]
    fn test_relaxed_policy() {
        let manager = PasswordManager::new(PasswordPolicy::relaxed());

        // Should pass with relaxed policy
        assert!(manager.validate_password("simplepass").is_ok());
        assert!(manager.validate_password("password123").is_ok()); // Common but allowed
    }

    #[test]
    fn test_strict_policy() {
        let manager = PasswordManager::new(PasswordPolicy::strict());

        // Should fail with strict policy
        assert!(manager.validate_password("MySecurePass123!").is_err()); // Too short for strict

        // Should pass with strict policy
        assert!(manager.validate_password("ThisIsAVerySecurePassword123!").is_ok());
    }

    #[test]
    fn test_password_generation() {
        let manager = PasswordManager::new(PasswordPolicy::default());

        let password = manager.generate_password(16);
        assert_eq!(password.len(), 16);
        assert!(manager.validate_password(&password).is_ok());

        // Test multiple generations are different
        let password2 = manager.generate_password(16);
        assert_ne!(password, password2);
    }

    #[test]
    fn test_pattern_detection() {
        let manager = PasswordManager::new(PasswordPolicy::default());

        assert!(manager.has_common_patterns("mypassword123"));
        assert!(manager.has_common_patterns("admin123"));
        assert!(!manager.has_common_patterns("randomtext987"));

        assert!(manager.has_repeated_characters("aaabbb"));
        assert!(manager.has_repeated_characters("password111"));
        assert!(!manager.has_repeated_characters("password12"));

        assert!(manager.has_sequential_characters("abc123"));
        assert!(manager.has_sequential_characters("xyz789"));
        assert!(!manager.has_sequential_characters("random123"));
    }

    #[test]
    fn test_password_suggestions() {
        let manager = PasswordManager::new(PasswordPolicy::default());

        let suggestions = manager.generate_suggestions(12);
        assert_eq!(suggestions.len(), 3);

        for suggestion in &suggestions {
            assert!(suggestion.len() >= 12);
            assert!(manager.validate_password(suggestion).is_ok());
        }

        // All suggestions should be different
        assert_ne!(suggestions[0], suggestions[1]);
        assert_ne!(suggestions[1], suggestions[2]);
    }

    #[test]
    fn test_strength_levels() {
        assert_eq!(PasswordStrength::VeryWeak.score(), 10);
        assert_eq!(PasswordStrength::VeryStrong.score(), 100);

        assert!(PasswordStrength::Good.meets_minimum(PasswordStrength::Fair));
        assert!(!PasswordStrength::Fair.meets_minimum(PasswordStrength::Good));

        assert_eq!(PasswordStrength::Strong.description(), "Strong - good security");
    }
}