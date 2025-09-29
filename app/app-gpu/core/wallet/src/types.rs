//! Core types and data structures for wallet operations

use crate::WalletError;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use uuid::Uuid;
use zeroize::{Zeroize, ZeroizeOnDrop};

/// Unique wallet identifier
pub type WalletId = Uuid;

/// Wallet configuration settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalletConfig {
    /// Storage directory path
    pub storage_path: PathBuf,

    /// Database configuration
    pub database: DatabaseConfig,

    /// Security configuration
    pub security: SecurityConfig,

    /// Network configuration for different coin types
    pub networks: HashMap<CoinType, NetworkConfig>,

    /// Cache settings
    pub cache: CacheConfig,

    /// Hardware wallet settings
    #[cfg(feature = "hardware-wallet")]
    pub hardware_wallet: HardwareWalletConfig,
}

impl WalletConfig {
    pub fn default_with_path(path: PathBuf) -> Self {
        Self {
            storage_path: path,
            database: DatabaseConfig::default(),
            security: SecurityConfig::default(),
            networks: Self::default_networks(),
            cache: CacheConfig::default(),
            #[cfg(feature = "hardware-wallet")]
            hardware_wallet: HardwareWalletConfig::default(),
        }
    }

    fn default_networks() -> HashMap<CoinType, NetworkConfig> {
        let mut networks = HashMap::new();
        networks.insert(CoinType::Bitcoin, NetworkConfig::bitcoin_mainnet());
        networks.insert(CoinType::Ethereum, NetworkConfig::ethereum_mainnet());
        networks.insert(CoinType::Litecoin, NetworkConfig::litecoin_mainnet());
        networks.insert(CoinType::BitcoinCash, NetworkConfig::bitcoin_cash_mainnet());
        networks
    }
}

impl Default for WalletConfig {
    fn default() -> Self {
        Self::default_with_path(PathBuf::from("./wallet_data"))
    }
}

/// Database configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatabaseConfig {
    pub max_connections: u32,
    pub connection_timeout_ms: u64,
    pub max_memory_usage_mb: usize,
    pub enable_wal: bool,
    pub sync_mode: String,
}

impl Default for DatabaseConfig {
    fn default() -> Self {
        Self {
            max_connections: 10,
            connection_timeout_ms: 5000,
            max_memory_usage_mb: 256,
            enable_wal: true,
            sync_mode: "NORMAL".to_string(),
        }
    }
}

/// Security configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityConfig {
    pub encryption_algorithm: String,
    pub key_derivation_algorithm: String,
    pub key_derivation_iterations: u32,
    pub session_timeout_minutes: u32,
    pub max_failed_attempts: u32,
    pub require_secure_enclave: bool,
}

impl Default for SecurityConfig {
    fn default() -> Self {
        Self {
            encryption_algorithm: "AES-256-GCM".to_string(),
            key_derivation_algorithm: "Argon2id".to_string(),
            key_derivation_iterations: 600_000,
            session_timeout_minutes: 30,
            max_failed_attempts: 3,
            require_secure_enclave: false,
        }
    }
}

/// Network configuration for blockchain connections
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkConfig {
    pub name: String,
    pub rpc_urls: Vec<String>,
    pub explorer_urls: Vec<String>,
    pub chain_id: u64,
    pub native_currency: CurrencyInfo,
    pub confirmation_blocks: u32,
    pub gas_limit: Option<u64>,
}

impl NetworkConfig {
    pub fn bitcoin_mainnet() -> Self {
        Self {
            name: "Bitcoin Mainnet".to_string(),
            rpc_urls: vec!["https://bitcoin-rpc.example.com".to_string()],
            explorer_urls: vec!["https://blockstream.info".to_string()],
            chain_id: 0,
            native_currency: CurrencyInfo {
                name: "Bitcoin".to_string(),
                symbol: "BTC".to_string(),
                decimals: 8,
            },
            confirmation_blocks: 6,
            gas_limit: None,
        }
    }

    pub fn ethereum_mainnet() -> Self {
        Self {
            name: "Ethereum Mainnet".to_string(),
            rpc_urls: vec!["https://eth-rpc.example.com".to_string()],
            explorer_urls: vec!["https://etherscan.io".to_string()],
            chain_id: 1,
            native_currency: CurrencyInfo {
                name: "Ether".to_string(),
                symbol: "ETH".to_string(),
                decimals: 18,
            },
            confirmation_blocks: 12,
            gas_limit: Some(21000),
        }
    }

    pub fn litecoin_mainnet() -> Self {
        Self {
            name: "Litecoin Mainnet".to_string(),
            rpc_urls: vec!["https://litecoin-rpc.example.com".to_string()],
            explorer_urls: vec!["https://blockchair.com/litecoin".to_string()],
            chain_id: 2,
            native_currency: CurrencyInfo {
                name: "Litecoin".to_string(),
                symbol: "LTC".to_string(),
                decimals: 8,
            },
            confirmation_blocks: 6,
            gas_limit: None,
        }
    }

    pub fn bitcoin_cash_mainnet() -> Self {
        Self {
            name: "Bitcoin Cash Mainnet".to_string(),
            rpc_urls: vec!["https://bitcoin-cash-rpc.example.com".to_string()],
            explorer_urls: vec!["https://blockchair.com/bitcoin-cash".to_string()],
            chain_id: 3,
            native_currency: CurrencyInfo {
                name: "Bitcoin Cash".to_string(),
                symbol: "BCH".to_string(),
                decimals: 8,
            },
            confirmation_blocks: 6,
            gas_limit: None,
        }
    }
}

/// Currency information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CurrencyInfo {
    pub name: String,
    pub symbol: String,
    pub decimals: u8,
}

/// Cache configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheConfig {
    pub balance_cache_ttl_seconds: u64,
    pub address_cache_ttl_seconds: u64,
    pub transaction_cache_ttl_seconds: u64,
    pub max_cached_wallets: usize,
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            balance_cache_ttl_seconds: 300,    // 5 minutes
            address_cache_ttl_seconds: 3600,   // 1 hour
            transaction_cache_ttl_seconds: 1800, // 30 minutes
            max_cached_wallets: 100,
        }
    }
}

/// Hardware wallet configuration
#[cfg(feature = "hardware-wallet")]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareWalletConfig {
    pub enable_ledger: bool,
    pub enable_trezor: bool,
    pub connection_timeout_ms: u64,
    pub auto_discovery: bool,
}

#[cfg(feature = "hardware-wallet")]
impl Default for HardwareWalletConfig {
    fn default() -> Self {
        Self {
            enable_ledger: true,
            enable_trezor: true,
            connection_timeout_ms: 10000,
            auto_discovery: true,
        }
    }
}

/// Supported cryptocurrency types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum CoinType {
    Bitcoin,
    Ethereum,
    Litecoin,
    BitcoinCash,
    Dogecoin,
    Dash,
    Monero,
    Zcash,
    EthereumClassic,
    Ripple,
}

impl CoinType {
    /// Get BIP44 coin type number
    pub fn bip44_coin_type(&self) -> u32 {
        match self {
            CoinType::Bitcoin => 0,
            CoinType::Ethereum => 60,
            CoinType::Litecoin => 2,
            CoinType::BitcoinCash => 145,
            CoinType::Dogecoin => 3,
            CoinType::Dash => 5,
            CoinType::Monero => 128,
            CoinType::Zcash => 133,
            CoinType::EthereumClassic => 61,
            CoinType::Ripple => 144,
        }
    }

    /// Get default derivation path for coin type
    pub fn default_derivation_path(&self) -> String {
        format!("m/44'/{}'/0'/0", self.bip44_coin_type())
    }

    /// Get address format for coin type
    pub fn address_format(&self) -> AddressFormat {
        match self {
            CoinType::Bitcoin | CoinType::Litecoin | CoinType::BitcoinCash | CoinType::Dogecoin | CoinType::Dash => AddressFormat::Base58,
            CoinType::Ethereum | CoinType::EthereumClassic => AddressFormat::Hex,
            CoinType::Monero => AddressFormat::Monero,
            CoinType::Zcash => AddressFormat::Zcash,
            CoinType::Ripple => AddressFormat::Base58,
        }
    }

    /// Check if coin type supports smart contracts
    pub fn supports_smart_contracts(&self) -> bool {
        matches!(self, CoinType::Ethereum | CoinType::EthereumClassic)
    }

    /// Get minimum confirmations required
    pub fn min_confirmations(&self) -> u32 {
        match self {
            CoinType::Bitcoin | CoinType::Litecoin | CoinType::BitcoinCash => 6,
            CoinType::Ethereum | CoinType::EthereumClassic => 12,
            CoinType::Dogecoin => 20,
            CoinType::Dash => 6,
            CoinType::Monero => 10,
            CoinType::Zcash => 6,
            CoinType::Ripple => 1,
        }
    }
}

impl std::fmt::Display for CoinType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CoinType::Bitcoin => write!(f, "Bitcoin"),
            CoinType::Ethereum => write!(f, "Ethereum"),
            CoinType::Litecoin => write!(f, "Litecoin"),
            CoinType::BitcoinCash => write!(f, "Bitcoin Cash"),
            CoinType::Dogecoin => write!(f, "Dogecoin"),
            CoinType::Dash => write!(f, "Dash"),
            CoinType::Monero => write!(f, "Monero"),
            CoinType::Zcash => write!(f, "Zcash"),
            CoinType::EthereumClassic => write!(f, "Ethereum Classic"),
            CoinType::Ripple => write!(f, "Ripple"),
        }
    }
}

/// Address format types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AddressFormat {
    Base58,
    Hex,
    Bech32,
    Monero,
    Zcash,
}

/// Wallet types supported
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WalletType {
    /// Hierarchical Deterministic wallet (BIP32/39/44)
    HD,
    /// Multi-signature wallet
    MultiSignature,
    /// Hardware wallet
    #[cfg(feature = "hardware-wallet")]
    Hardware,
    /// Watch-only wallet (no private keys)
    WatchOnly,
}

/// Wallet information and metadata
#[derive(Debug, Clone, Serialize, Deserialize, Zeroize, ZeroizeOnDrop)]
pub struct WalletInfo {
    pub id: WalletId,
    pub name: String,
    pub wallet_type: WalletType,
    pub supported_coins: Vec<CoinType>,
    pub created_at: DateTime<Utc>,
    pub last_accessed: Option<DateTime<Utc>>,
    pub encrypted: bool,
    pub backup_created: bool,
    /// Total number of addresses generated
    pub address_count: HashMap<CoinType, u32>,
    /// Last known balances (may be cached)
    pub cached_balances: HashMap<CoinType, Balance>,
    /// Wallet metadata
    pub metadata: WalletMetadata,
}

/// Additional wallet metadata
#[derive(Debug, Clone, Serialize, Deserialize, Zeroize, ZeroizeOnDrop)]
pub struct WalletMetadata {
    pub description: Option<String>,
    pub tags: Vec<String>,
    pub favorite: bool,
    pub color: Option<String>,
    pub currency_preference: Option<String>,
}

impl Default for WalletMetadata {
    fn default() -> Self {
        Self {
            description: None,
            tags: Vec::new(),
            favorite: false,
            color: None,
            currency_preference: None,
        }
    }
}

/// Cryptocurrency address
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Hash)]
pub struct Address {
    pub value: String,
    pub coin_type: CoinType,
    pub format: AddressFormat,
    pub derivation_path: Option<String>,
    pub index: Option<u32>,
    pub created_at: DateTime<Utc>,
}

impl Address {
    pub fn new(
        value: String,
        coin_type: CoinType,
        derivation_path: Option<String>,
        index: Option<u32>,
    ) -> Self {
        Self {
            value,
            coin_type,
            format: coin_type.address_format(),
            derivation_path,
            index,
            created_at: Utc::now(),
        }
    }

    /// Validate address format
    pub fn validate(&self) -> Result<(), WalletError> {
        if self.value.is_empty() {
            return Err(WalletError::InvalidAddress {
                address: self.value.clone(),
            });
        }

        // Basic validation based on format
        match self.format {
            AddressFormat::Base58 => {
                if self.value.len() < 26 || self.value.len() > 35 {
                    return Err(WalletError::InvalidAddress {
                        address: self.value.clone(),
                    });
                }
            }
            AddressFormat::Hex => {
                if !self.value.starts_with("0x") || self.value.len() != 42 {
                    return Err(WalletError::InvalidAddress {
                        address: self.value.clone(),
                    });
                }
            }
            AddressFormat::Bech32 => {
                if !self.value.starts_with("bc1") && !self.value.starts_with("ltc1") {
                    return Err(WalletError::InvalidAddress {
                        address: self.value.clone(),
                    });
                }
            }
            AddressFormat::Monero => {
                if self.value.len() != 95 {
                    return Err(WalletError::InvalidAddress {
                        address: self.value.clone(),
                    });
                }
            }
            AddressFormat::Zcash => {
                if !self.value.starts_with('t') && !self.value.starts_with('z') {
                    return Err(WalletError::InvalidAddress {
                        address: self.value.clone(),
                    });
                }
            }
        }

        Ok(())
    }
}

impl std::fmt::Display for Address {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.value)
    }
}

/// Balance information for a cryptocurrency
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Balance {
    pub coin_type: CoinType,
    /// Confirmed balance in smallest unit (satoshis, wei, etc.)
    pub confirmed: u64,
    /// Unconfirmed balance in smallest unit
    pub unconfirmed: u64,
    /// Locked/frozen balance (e.g., in staking)
    pub locked: u64,
    /// Last update timestamp
    pub last_updated: DateTime<Utc>,
}

impl Balance {
    pub fn new(coin_type: CoinType) -> Self {
        Self {
            coin_type,
            confirmed: 0,
            unconfirmed: 0,
            locked: 0,
            last_updated: Utc::now(),
        }
    }

    /// Get total available balance (confirmed + unconfirmed - locked)
    pub fn total(&self) -> u64 {
        self.confirmed.saturating_add(self.unconfirmed).saturating_sub(self.locked)
    }

    /// Get spendable balance (confirmed - locked)
    pub fn spendable(&self) -> u64 {
        self.confirmed.saturating_sub(self.locked)
    }

    /// Convert to decimal representation
    pub fn to_decimal(&self, amount: u64) -> f64 {
        let decimals = match self.coin_type {
            CoinType::Bitcoin | CoinType::Litecoin | CoinType::BitcoinCash | CoinType::Dogecoin | CoinType::Dash | CoinType::Zcash => 8,
            CoinType::Ethereum | CoinType::EthereumClassic => 18,
            CoinType::Monero => 12,
            CoinType::Ripple => 6,
        };
        amount as f64 / 10_f64.powi(decimals)
    }

    /// Convert from decimal representation
    pub fn from_decimal(&self, amount: f64) -> u64 {
        let decimals = match self.coin_type {
            CoinType::Bitcoin | CoinType::Litecoin | CoinType::BitcoinCash | CoinType::Dogecoin | CoinType::Dash | CoinType::Zcash => 8,
            CoinType::Ethereum | CoinType::EthereumClassic => 18,
            CoinType::Monero => 12,
            CoinType::Ripple => 6,
        };
        (amount * 10_f64.powi(decimals)) as u64
    }
}

/// Private key representation
#[derive(Clone, Serialize, Deserialize, Zeroize, ZeroizeOnDrop)]
pub struct PrivateKey {
    #[zeroize(skip)]
    pub coin_type: CoinType,
    pub key_data: Vec<u8>,
    pub derivation_path: Option<String>,
}

impl PrivateKey {
    pub fn new(coin_type: CoinType, key_data: Vec<u8>, derivation_path: Option<String>) -> Self {
        Self {
            coin_type,
            key_data,
            derivation_path,
        }
    }

    /// Get public key from private key
    pub fn public_key(&self) -> Result<PublicKey, WalletError> {
        match self.coin_type {
            CoinType::Bitcoin | CoinType::Litecoin | CoinType::BitcoinCash | CoinType::Dogecoin | CoinType::Dash => {
                if self.key_data.len() != 32 {
                    return Err(WalletError::InvalidPrivateKey {
                        reason: "Invalid key length for Bitcoin-like coin".to_string(),
                    });
                }

                let secret_key = secp256k1::SecretKey::from_slice(&self.key_data)?;
                let secp = secp256k1::Secp256k1::new();
                let public_key = secp256k1::PublicKey::from_secret_key(&secp, &secret_key);

                Ok(PublicKey::new(
                    self.coin_type,
                    public_key.serialize().to_vec(),
                    self.derivation_path.clone(),
                ))
            }
            CoinType::Ethereum | CoinType::EthereumClassic => {
                if self.key_data.len() != 32 {
                    return Err(WalletError::InvalidPrivateKey {
                        reason: "Invalid key length for Ethereum".to_string(),
                    });
                }

                let secret_key = secp256k1::SecretKey::from_slice(&self.key_data)?;
                let secp = secp256k1::Secp256k1::new();
                let public_key = secp256k1::PublicKey::from_secret_key(&secp, &secret_key);

                Ok(PublicKey::new(
                    self.coin_type,
                    public_key.serialize_uncompressed()[1..].to_vec(),
                    self.derivation_path.clone(),
                ))
            }
            _ => Err(WalletError::UnsupportedCoinType {
                coin_type: self.coin_type.to_string(),
            }),
        }
    }
}

// Implement Debug manually to avoid exposing private key data
impl std::fmt::Debug for PrivateKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("PrivateKey")
            .field("coin_type", &self.coin_type)
            .field("key_data", &"[REDACTED]")
            .field("derivation_path", &self.derivation_path)
            .finish()
    }
}

/// Public key representation
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PublicKey {
    pub coin_type: CoinType,
    pub key_data: Vec<u8>,
    pub derivation_path: Option<String>,
}

impl PublicKey {
    pub fn new(coin_type: CoinType, key_data: Vec<u8>, derivation_path: Option<String>) -> Self {
        Self {
            coin_type,
            key_data,
            derivation_path,
        }
    }

    /// Generate address from public key
    pub fn to_address(&self) -> Result<Address, WalletError> {
        match self.coin_type {
            CoinType::Bitcoin | CoinType::Litecoin | CoinType::BitcoinCash | CoinType::Dogecoin | CoinType::Dash => {
                // Bitcoin-like address generation (simplified)
                let hash = sha2::Sha256::digest(&self.key_data);
                let hash = ripemd::Ripemd160::digest(&hash);
                let encoded = base58::encode(&hash);

                Ok(Address::new(
                    encoded,
                    self.coin_type,
                    self.derivation_path.clone(),
                    None,
                ))
            }
            CoinType::Ethereum | CoinType::EthereumClassic => {
                // Ethereum address generation (simplified)
                let hash = sha3::Keccak256::digest(&self.key_data);
                let address = format!("0x{}", hex::encode(&hash[12..]));

                Ok(Address::new(
                    address,
                    self.coin_type,
                    self.derivation_path.clone(),
                    None,
                ))
            }
            _ => Err(WalletError::UnsupportedCoinType {
                coin_type: self.coin_type.to_string(),
            }),
        }
    }
}

/// Key pair (private + public key)
#[derive(Debug, Clone, Serialize, Deserialize, Zeroize, ZeroizeOnDrop)]
pub struct KeyPair {
    pub private_key: PrivateKey,
    pub public_key: PublicKey,
}

impl KeyPair {
    pub fn new(private_key: PrivateKey) -> Result<Self, WalletError> {
        let public_key = private_key.public_key()?;
        Ok(Self {
            private_key,
            public_key,
        })
    }

    /// Generate address from key pair
    pub fn address(&self) -> Result<Address, WalletError> {
        self.public_key.to_address()
    }
}

/// Mnemonic phrase for HD wallets
#[derive(Clone, Serialize, Deserialize, Zeroize, ZeroizeOnDrop)]
pub struct Mnemonic {
    phrase: String,
    language: bip39::Language,
}

impl Mnemonic {
    /// Create mnemonic from string
    pub fn from_phrase(phrase: String, language: bip39::Language) -> Result<Self, WalletError> {
        let _mnemonic = bip39::Mnemonic::from_phrase(&phrase, language)?;
        Ok(Self { phrase, language })
    }

    /// Generate new random mnemonic
    pub fn generate(word_count: usize, language: bip39::Language) -> Result<Self, WalletError> {
        let entropy_bits = match word_count {
            12 => 128,
            15 => 160,
            18 => 192,
            21 => 224,
            24 => 256,
            _ => return Err(WalletError::InvalidInput {
                message: "Word count must be 12, 15, 18, 21, or 24".to_string(),
            }),
        };

        let mut entropy = vec![0u8; entropy_bits / 8];
        rand::RngCore::fill_bytes(&mut rand::thread_rng(), &mut entropy);

        let mnemonic = bip39::Mnemonic::from_entropy(&entropy, language)?;
        Ok(Self {
            phrase: mnemonic.phrase().to_string(),
            language,
        })
    }

    /// Get phrase string
    pub fn phrase(&self) -> &str {
        &self.phrase
    }

    /// Get language
    pub fn language(&self) -> bip39::Language {
        self.language
    }

    /// Convert to seed with optional passphrase
    pub fn to_seed(&self, passphrase: Option<&str>) -> Result<Seed, WalletError> {
        let mnemonic = bip39::Mnemonic::from_phrase(&self.phrase, self.language)?;
        let seed_bytes = mnemonic.to_seed(passphrase.unwrap_or(""));
        Ok(Seed::from_bytes(seed_bytes.to_vec()))
    }

    /// Validate mnemonic phrase
    pub fn validate(&self) -> Result<(), WalletError> {
        let _mnemonic = bip39::Mnemonic::from_phrase(&self.phrase, self.language)?;
        Ok(())
    }
}

// Implement Debug manually to avoid exposing mnemonic phrase
impl std::fmt::Debug for Mnemonic {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Mnemonic")
            .field("phrase", &"[REDACTED]")
            .field("language", &self.language)
            .finish()
    }
}

/// Seed for HD wallet generation
#[derive(Clone, Serialize, Deserialize, Zeroize, ZeroizeOnDrop)]
pub struct Seed {
    data: Vec<u8>,
}

impl Seed {
    pub fn from_bytes(data: Vec<u8>) -> Self {
        Self { data }
    }

    pub fn as_bytes(&self) -> &[u8] {
        &self.data
    }

    pub fn len(&self) -> usize {
        self.data.len()
    }

    pub fn is_empty(&self) -> bool {
        self.data.is_empty()
    }
}

// Implement Debug manually to avoid exposing seed data
impl std::fmt::Debug for Seed {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Seed")
            .field("data", &"[REDACTED]")
            .field("len", &self.data.len())
            .finish()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_coin_type_bip44() {
        assert_eq!(CoinType::Bitcoin.bip44_coin_type(), 0);
        assert_eq!(CoinType::Ethereum.bip44_coin_type(), 60);
        assert_eq!(CoinType::Litecoin.bip44_coin_type(), 2);
    }

    #[test]
    fn test_address_validation() {
        let addr = Address::new(
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2".to_string(),
            CoinType::Bitcoin,
            None,
            None,
        );
        assert!(addr.validate().is_ok());

        let invalid_addr = Address::new(
            "invalid".to_string(),
            CoinType::Bitcoin,
            None,
            None,
        );
        assert!(invalid_addr.validate().is_err());
    }

    #[test]
    fn test_balance_calculations() {
        let balance = Balance {
            coin_type: CoinType::Bitcoin,
            confirmed: 100_000_000, // 1 BTC
            unconfirmed: 50_000_000, // 0.5 BTC
            locked: 10_000_000,      // 0.1 BTC
            last_updated: Utc::now(),
        };

        assert_eq!(balance.total(), 140_000_000); // 1.4 BTC
        assert_eq!(balance.spendable(), 90_000_000); // 0.9 BTC
        assert_eq!(balance.to_decimal(100_000_000), 1.0); // 1 BTC
    }

    #[test]
    fn test_mnemonic_generation() {
        let mnemonic = Mnemonic::generate(12, bip39::Language::English);
        assert!(mnemonic.is_ok());

        let mnemonic = mnemonic.unwrap();
        assert_eq!(mnemonic.phrase().split_whitespace().count(), 12);
        assert!(mnemonic.validate().is_ok());
    }

    #[test]
    fn test_wallet_config_default() {
        let config = WalletConfig::default();
        assert!(!config.networks.is_empty());
        assert!(config.networks.contains_key(&CoinType::Bitcoin));
        assert!(config.networks.contains_key(&CoinType::Ethereum));
    }
}