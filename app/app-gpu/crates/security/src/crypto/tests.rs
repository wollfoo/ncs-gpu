#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_nonce_uniqueness() {
        let protector = WalletProtector::with_password("test_password").unwrap();
        let data = b"test wallet data";

        // Encrypt 2 times
        let enc1 = protector.encrypt_wallet(data).unwrap();
        let enc2 = protector.encrypt_wallet(data).unwrap();

        // CRITICAL CHECK: Nonces must differ
        assert_ne!(enc1.nonce, enc2.nonce, "Nonces must be unique per encryption");

        // CRITICAL CHECK: Ciphertexts must differ
        assert_ne!(enc1.ciphertext, enc2.ciphertext, "Ciphertexts must differ with unique nonces");
    }

    #[test]
    fn test_encrypt_decrypt_round_trip() {
        let protector = WalletProtector::with_password("test_password").unwrap();
        let original = b"wallet data to encrypt";

        // Encrypt
        let encrypted = protector.encrypt_wallet(original).unwrap();

        // Decrypt
        let decrypted = protector.decrypt_wallet(&encrypted).unwrap();

        assert_eq!(original.as_slice(), decrypted.as_slice());
    }

    #[test]
    fn test_v3_phase3_requirement_1000_decrypts() {
        let protector = WalletProtector::with_password("test_password").unwrap();
        let data = b"test wallet data";

        // Encrypt once
        let encrypted = protector.encrypt_wallet(data).unwrap();

        // Phase 3.3: Pass 1000 decrypt test cycles
        for i in 0..1000 {
            let decrypted = protector.decrypt_wallet(&encrypted).unwrap();
            assert_eq!(data.as_slice(), decrypted.as_slice(), "Decrypt cycle {} failed", i);
        }

        println!("✅ Phase 3.3 Validation: 1000 decrypt cycles PASSED");
    }

    #[test]
    fn test_wrong_password_fails() {
        let protector1 = WalletProtector::with_password("password1").unwrap();
        let protector2 = WalletProtector::with_password("password2").unwrap();

        let data = b"secret wallet data";
        let encrypted = protector1.encrypt_wallet(data).unwrap();

        // Should fail decryption with wrong password
        assert!(protector2.decrypt_wallet(&encrypted).is_err(),
            "Wrong password should fail decryption");
    }

    #[test]
    fn test_nonce_entropy() {
        // Test randomness quality of 1000 nonces
        let mut nonces = Vec::new();
        for _ in 0..1000 {
            nonces.push(generate_secure_random_nonce());
        }

        // Statistical tests for randomness
        // Check no duplicates
        let unique_nonces: std::collections::HashSet<_> = nonces.iter().collect();
        assert_eq!(unique_nonces.len(), 1000, "All nonces must be unique");

        // Check entropy (no obvious patterns)
        // Additional statistical tests could be added here
    }

    #[tokio::test]
    async fn test_wallet_persistence_simulation() {
        // Simulate wallet load/save/suspend/resume cycle (common in production)

        let protector = WalletProtector::with_password("complex_password!123").unwrap();

        // Original wallet data (simulate real wallet)
        let wallet_data = b"mock wallet data for testing";

        // Encrypt for storage
        let encrypted = protector.encrypt_wallet(wallet_data).unwrap();

        // Serialize to JSON (simulate persistence)
        let serialized = serde_json::to_string(&encrypted).unwrap();

        // Deserialize from JSON (simulate load)
        let deserialized: EncryptedWallet = serde_json::from_str(&serialized).unwrap();

        // Decrypt và verify
        let recovered = protector.decrypt_wallet(&deserialized).unwrap();
        assert_eq!(wallet_data.as_slice(), recovered.as_slice());

        println!("✅ Wallet persistence cycle PASSED");
    }
}