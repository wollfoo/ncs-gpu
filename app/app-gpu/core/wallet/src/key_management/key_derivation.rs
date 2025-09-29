//! Key derivation utilities and BIP32 path handling

use crate::{
    types::CoinType,
    WalletError, WalletResult,
};
use serde::{Deserialize, Serialize};
use std::fmt;

/// BIP32 derivation path representation
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DerivationPath {
    indices: Vec<u32>,
}

impl DerivationPath {
    /// Create new derivation path from indices
    pub fn new(indices: Vec<u32>) -> Self {
        Self { indices }
    }

    /// Parse derivation path from string (e.g., "m/44'/0'/0'/0/0")
    pub fn from_str(path: &str) -> WalletResult<Self> {
        let path = path.trim();

        if !path.starts_with('m') {
            return Err(WalletError::InvalidDerivationPath {
                path: path.to_string(),
            });
        }

        let parts: Vec<&str> = path.split('/').collect();
        if parts.len() < 2 {
            return Err(WalletError::InvalidDerivationPath {
                path: path.to_string(),
            });
        }

        let mut indices = Vec::new();

        for part in parts.iter().skip(1) { // Skip 'm'
            if part.is_empty() {
                continue;
            }

            let (index_str, hardened) = if part.ends_with('\'') || part.ends_with('h') {
                (&part[..part.len()-1], true)
            } else {
                (part, false)
            };

            let index: u32 = index_str.parse().map_err(|_| {
                WalletError::InvalidDerivationPath {
                    path: path.to_string(),
                }
            })?;

            let final_index = if hardened {
                index.checked_add(0x80000000).ok_or_else(|| {
                    WalletError::InvalidDerivationPath {
                        path: path.to_string(),
                    }
                })?
            } else {
                index
            };

            indices.push(final_index);
        }

        if indices.is_empty() {
            return Err(WalletError::InvalidDerivationPath {
                path: path.to_string(),
            });
        }

        Ok(Self::new(indices))
    }

    /// Create BIP44 derivation path: m/44'/coin_type'/account'/change/address_index
    pub fn bip44(coin_type: CoinType, account: u32, change: u32, address_index: u32) -> Self {
        let mut indices = vec![
            44 + 0x80000000,                           // Purpose: 44' (BIP44)
            coin_type.bip44_coin_type() + 0x80000000,  // Coin type (hardened)
            account + 0x80000000,                      // Account (hardened)
        ];

        indices.push(change);        // Change (not hardened)
        indices.push(address_index); // Address index (not hardened)

        Self::new(indices)
    }

    /// Create BIP44 account path: m/44'/coin_type'/account'
    pub fn bip44_account(coin_type: CoinType, account: u32) -> Self {
        Self::new(vec![
            44 + 0x80000000,                           // Purpose: 44'
            coin_type.bip44_coin_type() + 0x80000000,  // Coin type'
            account + 0x80000000,                      // Account'
        ])
    }

    /// Create BIP44 change path: m/44'/coin_type'/account'/change
    pub fn bip44_change(coin_type: CoinType, account: u32, change: u32) -> Self {
        Self::new(vec![
            44 + 0x80000000,                           // Purpose: 44'
            coin_type.bip44_coin_type() + 0x80000000,  // Coin type'
            account + 0x80000000,                      // Account'
            change,                                    // Change
        ])
    }

    /// Create BIP49 derivation path (P2SH-P2WPKH): m/49'/coin_type'/account'/change/address_index
    pub fn bip49(coin_type: CoinType, account: u32, change: u32, address_index: u32) -> Self {
        Self::new(vec![
            49 + 0x80000000,                           // Purpose: 49' (BIP49)
            coin_type.bip44_coin_type() + 0x80000000,  // Coin type'
            account + 0x80000000,                      // Account'
            change,                                    // Change
            address_index,                             // Address index
        ])
    }

    /// Create BIP84 derivation path (P2WPKH): m/84'/coin_type'/account'/change/address_index
    pub fn bip84(coin_type: CoinType, account: u32, change: u32, address_index: u32) -> Self {
        Self::new(vec![
            84 + 0x80000000,                           // Purpose: 84' (BIP84)
            coin_type.bip44_coin_type() + 0x80000000,  // Coin type'
            account + 0x80000000,                      // Account'
            change,                                    // Change
            address_index,                             // Address index
        ])
    }

    /// Create custom derivation path
    pub fn custom(path: &str) -> WalletResult<Self> {
        Self::from_str(path)
    }

    /// Get indices
    pub fn indices(&self) -> &[u32] {
        &self.indices
    }

    /// Get depth (number of derivation levels)
    pub fn depth(&self) -> usize {
        self.indices.len()
    }

    /// Check if index is hardened
    pub fn is_hardened(&self, level: usize) -> bool {
        if level >= self.indices.len() {
            false
        } else {
            self.indices[level] >= 0x80000000
        }
    }

    /// Get unhardened index at level
    pub fn unhardened_index(&self, level: usize) -> Option<u32> {
        if level >= self.indices.len() {
            None
        } else {
            let index = self.indices[level];
            if index >= 0x80000000 {
                Some(index - 0x80000000)
            } else {
                Some(index)
            }
        }
    }

    /// Get coin type from BIP44 path
    pub fn coin_type(&self) -> Option<CoinType> {
        if self.indices.len() >= 2 && self.is_hardened(0) && self.is_hardened(1) {
            let purpose = self.unhardened_index(0)?;
            if purpose == 44 || purpose == 49 || purpose == 84 {
                let coin_type_num = self.unhardened_index(1)?;
                return CoinType::from_bip44_coin_type(coin_type_num);
            }
        }
        None
    }

    /// Get account number from BIP44 path
    pub fn account(&self) -> Option<u32> {
        if self.indices.len() >= 3 && self.is_hardened(2) {
            self.unhardened_index(2)
        } else {
            None
        }
    }

    /// Get change index from BIP44 path (0 = external, 1 = internal)
    pub fn change(&self) -> Option<u32> {
        if self.indices.len() >= 4 {
            Some(self.indices[3])
        } else {
            None
        }
    }

    /// Get address index from BIP44 path
    pub fn address_index(&self) -> Option<u32> {
        if self.indices.len() >= 5 {
            Some(self.indices[4])
        } else {
            None
        }
    }

    /// Check if this is a valid BIP44 path
    pub fn is_bip44(&self) -> bool {
        self.indices.len() >= 3 &&
        self.is_hardened(0) &&
        self.unhardened_index(0) == Some(44) &&
        self.is_hardened(1) &&
        self.is_hardened(2)
    }

    /// Check if this is a valid BIP49 path
    pub fn is_bip49(&self) -> bool {
        self.indices.len() >= 3 &&
        self.is_hardened(0) &&
        self.unhardened_index(0) == Some(49) &&
        self.is_hardened(1) &&
        self.is_hardened(2)
    }

    /// Check if this is a valid BIP84 path
    pub fn is_bip84(&self) -> bool {
        self.indices.len() >= 3 &&
        self.is_hardened(0) &&
        self.unhardened_index(0) == Some(84) &&
        self.is_hardened(1) &&
        self.is_hardened(2)
    }

    /// Validate derivation path
    pub fn validate(&self) -> WalletResult<()> {
        if self.indices.is_empty() {
            return Err(WalletError::InvalidDerivationPath {
                path: self.to_string(),
            });
        }

        // Check maximum depth (BIP32 specifies max 255)
        if self.depth() > 255 {
            return Err(WalletError::InvalidDerivationPath {
                path: "Path too deep (max 255 levels)".to_string(),
            });
        }

        // Validate BIP44 structure if it claims to be BIP44
        if self.indices.len() >= 1 {
            let purpose = self.unhardened_index(0);

            if let Some(44) = purpose {
                if !self.is_bip44() {
                    return Err(WalletError::InvalidDerivationPath {
                        path: "Invalid BIP44 path structure".to_string(),
                    });
                }
            } else if let Some(49) = purpose {
                if !self.is_bip49() {
                    return Err(WalletError::InvalidDerivationPath {
                        path: "Invalid BIP49 path structure".to_string(),
                    });
                }
            } else if let Some(84) = purpose {
                if !self.is_bip84() {
                    return Err(WalletError::InvalidDerivationPath {
                        path: "Invalid BIP84 path structure".to_string(),
                    });
                }
            }
        }

        Ok(())
    }

    /// Get parent path by removing the last index
    pub fn parent(&self) -> Option<Self> {
        if self.indices.len() <= 1 {
            None
        } else {
            let mut parent_indices = self.indices.clone();
            parent_indices.pop();
            Some(Self::new(parent_indices))
        }
    }

    /// Extend path with additional index
    pub fn child(&self, index: u32) -> Self {
        let mut child_indices = self.indices.clone();
        child_indices.push(index);
        Self::new(child_indices)
    }

    /// Extend path with hardened index
    pub fn hardened_child(&self, index: u32) -> WalletResult<Self> {
        let hardened_index = index.checked_add(0x80000000)
            .ok_or_else(|| WalletError::InvalidDerivationPath {
                path: format!("Index {} too large for hardened derivation", index),
            })?;

        Ok(self.child(hardened_index))
    }
}

impl fmt::Display for DerivationPath {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "m")?;

        for &index in &self.indices {
            if index >= 0x80000000 {
                write!(f, "/{}'", index - 0x80000000)?;
            } else {
                write!(f, "/{}", index)?;
            }
        }

        Ok(())
    }
}

impl CoinType {
    /// Get CoinType from BIP44 coin type number
    pub fn from_bip44_coin_type(coin_type: u32) -> Option<CoinType> {
        match coin_type {
            0 => Some(CoinType::Bitcoin),
            60 => Some(CoinType::Ethereum),
            2 => Some(CoinType::Litecoin),
            145 => Some(CoinType::BitcoinCash),
            3 => Some(CoinType::Dogecoin),
            5 => Some(CoinType::Dash),
            128 => Some(CoinType::Monero),
            133 => Some(CoinType::Zcash),
            61 => Some(CoinType::EthereumClassic),
            144 => Some(CoinType::Ripple),
            _ => None,
        }
    }
}

/// Key derivation trait for different derivation schemes
pub trait KeyDerivation {
    /// Derive child key from parent key and index
    fn derive_child(&self, parent_key: &[u8], index: u32) -> WalletResult<Vec<u8>>;

    /// Derive key from path
    fn derive_from_path(&self, master_key: &[u8], path: &DerivationPath) -> WalletResult<Vec<u8>>;
}

/// Standard BIP32 key derivation
pub struct Bip32KeyDerivation;

impl KeyDerivation for Bip32KeyDerivation {
    fn derive_child(&self, parent_key: &[u8], index: u32) -> WalletResult<Vec<u8>> {
        // This is a simplified implementation
        // In a real implementation, you would use proper BIP32 derivation

        if parent_key.len() != 32 {
            return Err(WalletError::InvalidPrivateKey {
                reason: "Parent key must be 32 bytes".to_string(),
            });
        }

        // Use SHA256 for simplicity (real implementation uses HMAC-SHA512)
        let mut data = Vec::new();
        data.extend_from_slice(parent_key);
        data.extend_from_slice(&index.to_be_bytes());

        let hash = sha2::Sha256::digest(&data);
        Ok(hash.to_vec())
    }

    fn derive_from_path(&self, master_key: &[u8], path: &DerivationPath) -> WalletResult<Vec<u8>> {
        let mut current_key = master_key.to_vec();

        for &index in path.indices() {
            current_key = self.derive_child(&current_key, index)?;
        }

        Ok(current_key)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_derivation_path_parsing() {
        let path = DerivationPath::from_str("m/44'/0'/0'/0/0").unwrap();
        assert_eq!(path.depth(), 5);
        assert!(path.is_hardened(0));
        assert!(path.is_hardened(1));
        assert!(path.is_hardened(2));
        assert!(!path.is_hardened(3));
        assert!(!path.is_hardened(4));

        assert_eq!(path.unhardened_index(0), Some(44));
        assert_eq!(path.unhardened_index(1), Some(0));
        assert_eq!(path.account(), Some(0));
        assert_eq!(path.change(), Some(0));
        assert_eq!(path.address_index(), Some(0));
    }

    #[test]
    fn test_bip44_path_creation() {
        let path = DerivationPath::bip44(CoinType::Bitcoin, 1, 0, 5);
        assert_eq!(path.to_string(), "m/44'/0'/1'/0/5");
        assert!(path.is_bip44());
        assert_eq!(path.coin_type(), Some(CoinType::Bitcoin));
        assert_eq!(path.account(), Some(1));
        assert_eq!(path.change(), Some(0));
        assert_eq!(path.address_index(), Some(5));
    }

    #[test]
    fn test_derivation_path_validation() {
        let valid_path = DerivationPath::bip44(CoinType::Ethereum, 0, 0, 0);
        assert!(valid_path.validate().is_ok());

        let empty_path = DerivationPath::new(vec![]);
        assert!(empty_path.validate().is_err());
    }

    #[test]
    fn test_path_operations() {
        let path = DerivationPath::bip44(CoinType::Bitcoin, 0, 0, 0);

        let parent = path.parent().unwrap();
        assert_eq!(parent.depth(), path.depth() - 1);

        let child = path.child(10);
        assert_eq!(child.depth(), path.depth() + 1);
        assert_eq!(child.indices()[child.depth() - 1], 10);

        let hardened_child = path.hardened_child(5).unwrap();
        assert_eq!(hardened_child.indices()[hardened_child.depth() - 1], 5 + 0x80000000);
    }

    #[test]
    fn test_bip49_and_bip84_paths() {
        let bip49_path = DerivationPath::bip49(CoinType::Bitcoin, 0, 0, 0);
        assert!(bip49_path.is_bip49());
        assert_eq!(bip49_path.to_string(), "m/49'/0'/0'/0/0");

        let bip84_path = DerivationPath::bip84(CoinType::Bitcoin, 0, 0, 0);
        assert!(bip84_path.is_bip84());
        assert_eq!(bip84_path.to_string(), "m/84'/0'/0'/0/0");
    }

    #[test]
    fn test_coin_type_lookup() {
        assert_eq!(CoinType::from_bip44_coin_type(0), Some(CoinType::Bitcoin));
        assert_eq!(CoinType::from_bip44_coin_type(60), Some(CoinType::Ethereum));
        assert_eq!(CoinType::from_bip44_coin_type(999), None);
    }

    #[test]
    fn test_key_derivation() {
        let derivation = Bip32KeyDerivation;
        let master_key = vec![1u8; 32];

        let child_key = derivation.derive_child(&master_key, 0).unwrap();
        assert_eq!(child_key.len(), 32);
        assert_ne!(child_key, master_key);

        let path = DerivationPath::new(vec![0, 1]);
        let derived_key = derivation.derive_from_path(&master_key, &path).unwrap();
        assert_eq!(derived_key.len(), 32);
    }

    #[test]
    fn test_invalid_derivation_paths() {
        assert!(DerivationPath::from_str("").is_err());
        assert!(DerivationPath::from_str("44'/0'/0'").is_err()); // Missing 'm'
        assert!(DerivationPath::from_str("m/").is_err());
        assert!(DerivationPath::from_str("m/abc").is_err()); // Invalid index
    }
}