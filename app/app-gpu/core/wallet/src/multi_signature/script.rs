//! Multi-signature script implementation

use crate::{types::PublicKey, WalletError, WalletResult};
use serde::{Deserialize, Serialize};

/// Multi-signature script builder and manager
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MultiSigScript {
    /// Required threshold
    pub threshold: u32,
    /// Public keys
    pub public_keys: Vec<PublicKey>,
    /// Compiled script
    pub script: Vec<u8>,
}

impl MultiSigScript {
    /// Create new multi-signature script
    pub fn new(threshold: u32, public_keys: Vec<PublicKey>) -> WalletResult<Self> {
        if threshold == 0 || threshold > public_keys.len() as u32 {
            return Err(WalletError::InvalidSignatureThreshold { threshold });
        }

        let script = Self::build_script(threshold, &public_keys)?;

        Ok(Self {
            threshold,
            public_keys,
            script,
        })
    }

    /// Build the actual script bytes
    fn build_script(threshold: u32, public_keys: &[PublicKey]) -> WalletResult<Vec<u8>> {
        let mut script = Vec::new();

        // Push threshold
        script.push(Self::encode_number(threshold));

        // Push public keys
        for public_key in public_keys {
            script.push(public_key.key_data.len() as u8);
            script.extend_from_slice(&public_key.key_data);
        }

        // Push number of public keys
        script.push(Self::encode_number(public_keys.len() as u32));

        // OP_CHECKMULTISIG
        script.push(0xae);

        Ok(script)
    }

    /// Encode number as script opcode
    fn encode_number(n: u32) -> u8 {
        match n {
            0 => 0x00,      // OP_0
            1..=16 => 0x50 + n as u8, // OP_1 through OP_16
            _ => panic!("Number too large for script encoding"),
        }
    }

    /// Get script bytes
    pub fn to_bytes(&self) -> WalletResult<Vec<u8>> {
        Ok(self.script.clone())
    }

    /// Get script hash (for P2SH addresses)
    pub fn script_hash(&self) -> WalletResult<[u8; 20]> {
        use sha2::{Digest, Sha256};

        let hash = Sha256::digest(&self.script);
        let hash = ripemd::Ripemd160::digest(&hash);

        let mut result = [0u8; 20];
        result.copy_from_slice(&hash);
        Ok(result)
    }

    /// Validate script
    pub fn validate(&self) -> WalletResult<()> {
        if self.threshold == 0 {
            return Err(WalletError::InvalidSignatureThreshold {
                threshold: self.threshold,
            });
        }

        if self.threshold > self.public_keys.len() as u32 {
            return Err(WalletError::InvalidSignatureThreshold {
                threshold: self.threshold,
            });
        }

        if self.public_keys.is_empty() {
            return Err(WalletError::InvalidInput {
                message: "No public keys provided".to_string(),
            });
        }

        Ok(())
    }
}

/// Script builder for creating various script types
pub struct ScriptBuilder {
    script: Vec<u8>,
}

impl ScriptBuilder {
    /// Create new script builder
    pub fn new() -> Self {
        Self {
            script: Vec::new(),
        }
    }

    /// Push data to script
    pub fn push_data(mut self, data: &[u8]) -> Self {
        if data.len() <= 75 {
            self.script.push(data.len() as u8);
        } else {
            // For larger data, use OP_PUSHDATA1, OP_PUSHDATA2, etc.
            self.script.push(0x4c); // OP_PUSHDATA1
            self.script.push(data.len() as u8);
        }
        self.script.extend_from_slice(data);
        self
    }

    /// Push opcode to script
    pub fn push_opcode(mut self, opcode: u8) -> Self {
        self.script.push(opcode);
        self
    }

    /// Push number to script
    pub fn push_number(mut self, n: u32) -> Self {
        match n {
            0 => self.script.push(0x00),
            1..=16 => self.script.push(0x50 + n as u8),
            _ => {
                // For larger numbers, push as data
                let bytes = n.to_le_bytes();
                self = self.push_data(&bytes);
            }
        }
        self
    }

    /// Build the final script
    pub fn build(self) -> Vec<u8> {
        self.script
    }

    /// Create P2PKH script
    pub fn p2pkh(public_key_hash: &[u8; 20]) -> Vec<u8> {
        ScriptBuilder::new()
            .push_opcode(0x76) // OP_DUP
            .push_opcode(0xa9) // OP_HASH160
            .push_data(public_key_hash)
            .push_opcode(0x88) // OP_EQUALVERIFY
            .push_opcode(0xac) // OP_CHECKSIG
            .build()
    }

    /// Create P2SH script
    pub fn p2sh(script_hash: &[u8; 20]) -> Vec<u8> {
        ScriptBuilder::new()
            .push_opcode(0xa9) // OP_HASH160
            .push_data(script_hash)
            .push_opcode(0x87) // OP_EQUAL
            .build()
    }

    /// Create multi-signature script
    pub fn multisig(threshold: u32, public_keys: &[PublicKey]) -> WalletResult<Vec<u8>> {
        if threshold == 0 || threshold > public_keys.len() as u32 {
            return Err(WalletError::InvalidSignatureThreshold { threshold });
        }

        let mut builder = ScriptBuilder::new().push_number(threshold);

        for public_key in public_keys {
            builder = builder.push_data(&public_key.key_data);
        }

        builder = builder
            .push_number(public_keys.len() as u32)
            .push_opcode(0xae); // OP_CHECKMULTISIG

        Ok(builder.build())
    }
}

impl Default for ScriptBuilder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::CoinType;

    fn create_test_public_key(index: u8) -> PublicKey {
        PublicKey::new(
            CoinType::Bitcoin,
            vec![index; 33], // Compressed public key length
            None,
        )
    }

    #[test]
    fn test_multisig_script_creation() {
        let public_keys = vec![
            create_test_public_key(1),
            create_test_public_key(2),
            create_test_public_key(3),
        ];

        let script = MultiSigScript::new(2, public_keys.clone()).unwrap();
        assert_eq!(script.threshold, 2);
        assert_eq!(script.public_keys.len(), 3);
        assert!(!script.script.is_empty());
    }

    #[test]
    fn test_script_validation() {
        let public_keys = vec![create_test_public_key(1)];

        // Valid script
        let script = MultiSigScript::new(1, public_keys.clone()).unwrap();
        assert!(script.validate().is_ok());

        // Invalid threshold (too high)
        let result = MultiSigScript::new(2, public_keys);
        assert!(result.is_err());

        // Invalid threshold (zero)
        let result = MultiSigScript::new(0, vec![create_test_public_key(1)]);
        assert!(result.is_err());
    }

    #[test]
    fn test_script_builder() {
        let builder = ScriptBuilder::new();
        let script = builder
            .push_number(2)
            .push_data(&[1, 2, 3])
            .push_opcode(0xae)
            .build();

        assert!(!script.is_empty());
        assert_eq!(script[0], 0x52); // OP_2
    }

    #[test]
    fn test_p2pkh_script() {
        let hash = [1u8; 20];
        let script = ScriptBuilder::p2pkh(&hash);

        // Should be: OP_DUP OP_HASH160 <20-byte-hash> OP_EQUALVERIFY OP_CHECKSIG
        assert_eq!(script.len(), 25);
        assert_eq!(script[0], 0x76); // OP_DUP
        assert_eq!(script[1], 0xa9); // OP_HASH160
        assert_eq!(script[2], 20);   // Push 20 bytes
        assert_eq!(script[23], 0x88); // OP_EQUALVERIFY
        assert_eq!(script[24], 0xac); // OP_CHECKSIG
    }

    #[test]
    fn test_p2sh_script() {
        let hash = [1u8; 20];
        let script = ScriptBuilder::p2sh(&hash);

        // Should be: OP_HASH160 <20-byte-hash> OP_EQUAL
        assert_eq!(script.len(), 23);
        assert_eq!(script[0], 0xa9); // OP_HASH160
        assert_eq!(script[1], 20);   // Push 20 bytes
        assert_eq!(script[22], 0x87); // OP_EQUAL
    }

    #[test]
    fn test_script_hash() {
        let public_keys = vec![
            create_test_public_key(1),
            create_test_public_key(2),
        ];

        let script = MultiSigScript::new(2, public_keys).unwrap();
        let hash = script.script_hash().unwrap();

        assert_eq!(hash.len(), 20);
    }
}