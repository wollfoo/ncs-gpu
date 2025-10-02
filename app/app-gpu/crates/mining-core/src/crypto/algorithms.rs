//! # Mining Algorithms (Thuật Toán Khai Thác)
//!
//! Hash algorithm implementations và utilities.

use anyhow::Result;
use sha2::{Sha256, Digest};
use blake3::Hasher as Blake3Hasher;

/// Compute SHA-256 hash
pub fn sha256(data: &[u8]) -> Vec<u8> {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hasher.finalize().to_vec()
}

/// Compute Blake3 hash
pub fn blake3(data: &[u8]) -> Vec<u8> {
    let mut hasher = Blake3Hasher::new();
    hasher.update(data);
    hasher.finalize().as_bytes().to_vec()
}

/// Verify solution hash meets target
pub fn verify_solution(hash: &[u8], target: &[u8]) -> bool {
    // Hash must be less than target (big-endian comparison)
    hash.iter()
        .zip(target.iter())
        .all(|(h, t)| h <= t)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sha256() {
        let data = b"hello world";
        let hash = sha256(data);
        assert_eq!(hash.len(), 32);
    }

    #[test]
    fn test_blake3() {
        let data = b"test data";
        let hash = blake3(data);
        assert_eq!(hash.len(), 32);
    }

    #[test]
    fn test_verify_solution() {
        let hash = vec![0x00, 0x00, 0xFF];
        let target = vec![0x00, 0x01, 0x00];
        assert!(verify_solution(&hash, &target));

        let hash2 = vec![0x00, 0x02, 0x00];
        assert!(!verify_solution(&hash2, &target));
    }
}
