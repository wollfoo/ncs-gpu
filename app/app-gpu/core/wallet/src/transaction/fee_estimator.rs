//! Fee estimation for cryptocurrency transactions

use crate::{
    types::CoinType,
    WalletError, WalletResult,
};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::{Duration, Instant};

/// Fee rate representation
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct FeeRate {
    /// Satoshis per byte (or wei per gas for Ethereum)
    rate: u64,
}

impl FeeRate {
    /// Create new fee rate
    pub fn new(rate: u64) -> Self {
        Self { rate }
    }

    /// Get rate in satoshis per byte
    pub fn satoshis_per_byte(&self) -> u64 {
        self.rate
    }

    /// Get rate in BTC per byte
    pub fn btc_per_byte(&self) -> f64 {
        self.rate as f64 / 100_000_000.0
    }

    /// Create fee rate from BTC per byte
    pub fn from_btc_per_byte(btc_per_byte: f64) -> Self {
        Self::new((btc_per_byte * 100_000_000.0) as u64)
    }

    /// Create fee rate for Ethereum (wei per gas)
    pub fn from_gwei(gwei: f64) -> Self {
        Self::new((gwei * 1_000_000_000.0) as u64)
    }

    /// Get rate in Gwei (for Ethereum)
    pub fn to_gwei(&self) -> f64 {
        self.rate as f64 / 1_000_000_000.0
    }

    /// Check if fee rate is dust
    pub fn is_dust(&self) -> bool {
        self.rate == 0
    }

    /// Check if fee rate is reasonable
    pub fn is_reasonable(&self, coin_type: CoinType) -> bool {
        match coin_type {
            CoinType::Bitcoin => self.rate >= 1 && self.rate <= 1000, // 1-1000 sat/byte
            CoinType::Ethereum | CoinType::EthereumClassic => {
                let gwei = self.to_gwei();
                gwei >= 1.0 && gwei <= 500.0 // 1-500 Gwei
            }
            CoinType::Litecoin => self.rate >= 1 && self.rate <= 500, // 1-500 lit/byte
            _ => self.rate > 0,
        }
    }
}

impl std::fmt::Display for FeeRate {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{} sat/byte", self.rate)
    }
}

/// Fee estimation strategy
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum FeeStrategy {
    /// Minimum fee (slow confirmation)
    Economy,
    /// Standard fee (normal confirmation)
    Standard,
    /// High priority fee (fast confirmation)
    Priority,
    /// Maximum fee (fastest confirmation)
    Urgent,
    /// Custom fee rate
    Custom(u64),
}

impl FeeStrategy {
    /// Get confirmation target in blocks
    pub fn confirmation_target(&self, coin_type: CoinType) -> u32 {
        match (self, coin_type) {
            (FeeStrategy::Economy, CoinType::Bitcoin) => 144,   // ~24 hours
            (FeeStrategy::Standard, CoinType::Bitcoin) => 6,    // ~1 hour
            (FeeStrategy::Priority, CoinType::Bitcoin) => 3,    // ~30 minutes
            (FeeStrategy::Urgent, CoinType::Bitcoin) => 1,      // ~10 minutes

            (FeeStrategy::Economy, CoinType::Ethereum) => 50,   // ~10 minutes
            (FeeStrategy::Standard, CoinType::Ethereum) => 20,  // ~4 minutes
            (FeeStrategy::Priority, CoinType::Ethereum) => 5,   // ~1 minute
            (FeeStrategy::Urgent, CoinType::Ethereum) => 1,     // next block

            (FeeStrategy::Economy, CoinType::Litecoin) => 24,   // ~6 hours
            (FeeStrategy::Standard, CoinType::Litecoin) => 6,   // ~15 minutes
            (FeeStrategy::Priority, CoinType::Litecoin) => 3,   // ~7.5 minutes
            (FeeStrategy::Urgent, CoinType::Litecoin) => 1,     // ~2.5 minutes

            (FeeStrategy::Custom(_), _) => 6, // Default to standard

            (_, _) => 6, // Default fallback
        }
    }

    /// Get description
    pub fn description(&self) -> &'static str {
        match self {
            FeeStrategy::Economy => "Economy (slow)",
            FeeStrategy::Standard => "Standard (normal)",
            FeeStrategy::Priority => "Priority (fast)",
            FeeStrategy::Urgent => "Urgent (fastest)",
            FeeStrategy::Custom(_) => "Custom",
        }
    }

    /// Get expected confirmation time in minutes
    pub fn estimated_time_minutes(&self, coin_type: CoinType) -> u32 {
        let blocks = self.confirmation_target(coin_type);
        let block_time = match coin_type {
            CoinType::Bitcoin => 10,
            CoinType::Ethereum | CoinType::EthereumClassic => 12, // seconds -> convert to minutes
            CoinType::Litecoin => 2.5 as u32,
            CoinType::Dogecoin => 1,
            _ => 10,
        };

        if coin_type == CoinType::Ethereum || coin_type == CoinType::EthereumClassic {
            blocks * block_time / 60 // Convert seconds to minutes
        } else {
            blocks * block_time
        }
    }
}

impl std::fmt::Display for FeeStrategy {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.description())
    }
}

/// Fee estimation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeeEstimate {
    /// Fee strategy used
    pub strategy: FeeStrategy,
    /// Estimated fee rate
    pub fee_rate: FeeRate,
    /// Total fee amount
    pub total_fee: u64,
    /// Transaction size in bytes
    pub transaction_size: u64,
    /// Confirmation target in blocks
    pub confirmation_target: u32,
    /// Estimated confirmation time
    pub estimated_time_minutes: u32,
    /// Timestamp of estimation
    pub timestamp: std::time::SystemTime,
}

impl FeeEstimate {
    pub fn new(
        strategy: FeeStrategy,
        fee_rate: FeeRate,
        total_fee: u64,
        transaction_size: u64,
        coin_type: CoinType,
    ) -> Self {
        Self {
            strategy,
            fee_rate,
            total_fee,
            transaction_size,
            confirmation_target: strategy.confirmation_target(coin_type),
            estimated_time_minutes: strategy.estimated_time_minutes(coin_type),
            timestamp: std::time::SystemTime::now(),
        }
    }

    /// Check if estimate is fresh (within last 5 minutes)
    pub fn is_fresh(&self) -> bool {
        if let Ok(age) = self.timestamp.elapsed() {
            age < Duration::from_secs(300) // 5 minutes
        } else {
            false
        }
    }
}

/// Fee estimator interface
#[async_trait]
pub trait FeeEstimator: Send + Sync {
    /// Estimate fee for transaction
    async fn estimate_fee(
        &self,
        coin_type: CoinType,
        transaction_size: u64,
        strategy: FeeStrategy,
    ) -> WalletResult<FeeEstimate>;

    /// Estimate fee rate for confirmation target
    async fn estimate_fee_rate(
        &self,
        coin_type: CoinType,
        confirmation_target: u32,
    ) -> WalletResult<FeeRate>;

    /// Get current network fee rates
    async fn get_network_fees(&self, coin_type: CoinType) -> WalletResult<NetworkFees>;

    /// Get fee rate recommendations
    async fn get_fee_recommendations(&self, coin_type: CoinType) -> WalletResult<FeeRecommendations>;

    /// Update fee data from network
    async fn update_fee_data(&self, coin_type: CoinType) -> WalletResult<()>;
}

/// Network fee information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkFees {
    /// Coin type
    pub coin_type: CoinType,
    /// Minimum relay fee
    pub min_relay_fee: FeeRate,
    /// Current average fee
    pub average_fee: FeeRate,
    /// Recommended fees by strategy
    pub recommended_fees: HashMap<FeeStrategy, FeeRate>,
    /// Mempool statistics
    pub mempool_stats: MempoolStats,
    /// Last update timestamp
    pub last_updated: std::time::SystemTime,
}

/// Mempool statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MempoolStats {
    /// Number of pending transactions
    pub pending_transactions: u64,
    /// Total mempool size in bytes
    pub mempool_size_bytes: u64,
    /// Fee rate percentiles
    pub fee_percentiles: HashMap<u8, FeeRate>, // percentile -> fee rate
}

/// Fee recommendations for different strategies
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeeRecommendations {
    pub economy: FeeRate,
    pub standard: FeeRate,
    pub priority: FeeRate,
    pub urgent: FeeRate,
}

impl FeeRecommendations {
    pub fn get_rate(&self, strategy: FeeStrategy) -> FeeRate {
        match strategy {
            FeeStrategy::Economy => self.economy,
            FeeStrategy::Standard => self.standard,
            FeeStrategy::Priority => self.priority,
            FeeStrategy::Urgent => self.urgent,
            FeeStrategy::Custom(rate) => FeeRate::new(rate),
        }
    }
}

/// Smart fee estimator implementation
#[derive(Debug)]
pub struct SmartFeeEstimator {
    /// Cached network fees
    fee_cache: tokio::sync::RwLock<HashMap<CoinType, (NetworkFees, Instant)>>,
    /// Cache TTL
    cache_ttl: Duration,
    /// Fee data sources
    data_sources: Vec<Box<dyn FeeDataSource>>,
}

impl SmartFeeEstimator {
    /// Create new smart fee estimator
    pub fn new(cache_ttl: Duration) -> Self {
        Self {
            fee_cache: tokio::sync::RwLock::new(HashMap::new()),
            cache_ttl,
            data_sources: Vec::new(),
        }
    }

    /// Add fee data source
    pub fn add_data_source(&mut self, source: Box<dyn FeeDataSource>) {
        self.data_sources.push(source);
    }

    /// Get cached network fees if fresh
    async fn get_cached_fees(&self, coin_type: CoinType) -> Option<NetworkFees> {
        let cache = self.fee_cache.read().await;
        if let Some((fees, timestamp)) = cache.get(&coin_type) {
            if timestamp.elapsed() < self.cache_ttl {
                return Some(fees.clone());
            }
        }
        None
    }

    /// Cache network fees
    async fn cache_fees(&self, coin_type: CoinType, fees: NetworkFees) {
        let mut cache = self.fee_cache.write().await;
        cache.insert(coin_type, (fees, Instant::now()));
    }

    /// Fetch fresh fee data from sources
    async fn fetch_fresh_fees(&self, coin_type: CoinType) -> WalletResult<NetworkFees> {
        let mut best_fees: Option<NetworkFees> = None;

        // Try each data source until we get valid data
        for source in &self.data_sources {
            match source.get_network_fees(coin_type).await {
                Ok(fees) => {
                    best_fees = Some(fees);
                    break;
                }
                Err(_) => continue, // Try next source
            }
        }

        match best_fees {
            Some(fees) => {
                self.cache_fees(coin_type, fees.clone()).await;
                Ok(fees)
            }
            None => {
                // Fallback to default fees if all sources fail
                Ok(self.get_fallback_fees(coin_type))
            }
        }
    }

    /// Get fallback fees when network data is unavailable
    fn get_fallback_fees(&self, coin_type: CoinType) -> NetworkFees {
        let (min_fee, avg_fee, economy, standard, priority, urgent) = match coin_type {
            CoinType::Bitcoin => (1, 20, 5, 20, 50, 100),
            CoinType::Ethereum | CoinType::EthereumClassic => {
                // Values in Gwei, converted to wei
                (1_000_000_000, 20_000_000_000, 5_000_000_000, 20_000_000_000, 50_000_000_000, 100_000_000_000)
            }
            CoinType::Litecoin => (1, 10, 2, 10, 25, 50),
            _ => (1, 10, 2, 10, 25, 50),
        };

        let mut recommended_fees = HashMap::new();
        recommended_fees.insert(FeeStrategy::Economy, FeeRate::new(economy));
        recommended_fees.insert(FeeStrategy::Standard, FeeRate::new(standard));
        recommended_fees.insert(FeeStrategy::Priority, FeeRate::new(priority));
        recommended_fees.insert(FeeStrategy::Urgent, FeeRate::new(urgent));

        NetworkFees {
            coin_type,
            min_relay_fee: FeeRate::new(min_fee),
            average_fee: FeeRate::new(avg_fee),
            recommended_fees,
            mempool_stats: MempoolStats {
                pending_transactions: 0,
                mempool_size_bytes: 0,
                fee_percentiles: HashMap::new(),
            },
            last_updated: std::time::SystemTime::now(),
        }
    }
}

#[async_trait]
impl FeeEstimator for SmartFeeEstimator {
    async fn estimate_fee(
        &self,
        coin_type: CoinType,
        transaction_size: u64,
        strategy: FeeStrategy,
    ) -> WalletResult<FeeEstimate> {
        let fee_rate = match strategy {
            FeeStrategy::Custom(rate) => FeeRate::new(rate),
            _ => {
                let network_fees = self.get_network_fees(coin_type).await?;
                network_fees.recommended_fees.get(&strategy)
                    .copied()
                    .unwrap_or_else(|| self.get_fallback_fees(coin_type).recommended_fees[&strategy])
            }
        };

        let total_fee = transaction_size * fee_rate.satoshis_per_byte();

        Ok(FeeEstimate::new(
            strategy,
            fee_rate,
            total_fee,
            transaction_size,
            coin_type,
        ))
    }

    async fn estimate_fee_rate(
        &self,
        coin_type: CoinType,
        confirmation_target: u32,
    ) -> WalletResult<FeeRate> {
        let network_fees = self.get_network_fees(coin_type).await?;

        // Map confirmation target to strategy
        let strategy = match confirmation_target {
            1..=2 => FeeStrategy::Urgent,
            3..=6 => FeeStrategy::Priority,
            7..=12 => FeeStrategy::Standard,
            _ => FeeStrategy::Economy,
        };

        Ok(network_fees.recommended_fees.get(&strategy)
            .copied()
            .unwrap_or(network_fees.average_fee))
    }

    async fn get_network_fees(&self, coin_type: CoinType) -> WalletResult<NetworkFees> {
        // Try cache first
        if let Some(cached_fees) = self.get_cached_fees(coin_type).await {
            return Ok(cached_fees);
        }

        // Fetch fresh data
        self.fetch_fresh_fees(coin_type).await
    }

    async fn get_fee_recommendations(&self, coin_type: CoinType) -> WalletResult<FeeRecommendations> {
        let network_fees = self.get_network_fees(coin_type).await?;

        Ok(FeeRecommendations {
            economy: network_fees.recommended_fees[&FeeStrategy::Economy],
            standard: network_fees.recommended_fees[&FeeStrategy::Standard],
            priority: network_fees.recommended_fees[&FeeStrategy::Priority],
            urgent: network_fees.recommended_fees[&FeeStrategy::Urgent],
        })
    }

    async fn update_fee_data(&self, coin_type: CoinType) -> WalletResult<()> {
        // Force refresh by removing from cache and fetching fresh data
        {
            let mut cache = self.fee_cache.write().await;
            cache.remove(&coin_type);
        }

        self.fetch_fresh_fees(coin_type).await?;
        Ok(())
    }
}

/// Fee data source trait
#[async_trait]
pub trait FeeDataSource: Send + Sync {
    /// Get network fees from this source
    async fn get_network_fees(&self, coin_type: CoinType) -> WalletResult<NetworkFees>;

    /// Get source name
    fn name(&self) -> &'static str;

    /// Check if source supports coin type
    fn supports_coin(&self, coin_type: CoinType) -> bool;
}

/// Mock fee data source for testing
#[derive(Debug)]
pub struct MockFeeDataSource {
    fees: HashMap<CoinType, NetworkFees>,
}

impl MockFeeDataSource {
    pub fn new() -> Self {
        let mut fees = HashMap::new();

        // Add mock Bitcoin fees
        let mut btc_recommended = HashMap::new();
        btc_recommended.insert(FeeStrategy::Economy, FeeRate::new(5));
        btc_recommended.insert(FeeStrategy::Standard, FeeRate::new(20));
        btc_recommended.insert(FeeStrategy::Priority, FeeRate::new(50));
        btc_recommended.insert(FeeStrategy::Urgent, FeeRate::new(100));

        fees.insert(CoinType::Bitcoin, NetworkFees {
            coin_type: CoinType::Bitcoin,
            min_relay_fee: FeeRate::new(1),
            average_fee: FeeRate::new(20),
            recommended_fees: btc_recommended,
            mempool_stats: MempoolStats {
                pending_transactions: 5000,
                mempool_size_bytes: 50_000_000,
                fee_percentiles: HashMap::new(),
            },
            last_updated: std::time::SystemTime::now(),
        });

        Self { fees }
    }
}

#[async_trait]
impl FeeDataSource for MockFeeDataSource {
    async fn get_network_fees(&self, coin_type: CoinType) -> WalletResult<NetworkFees> {
        self.fees.get(&coin_type)
            .cloned()
            .ok_or_else(|| WalletError::UnsupportedCoinType {
                coin_type: coin_type.to_string(),
            })
    }

    fn name(&self) -> &'static str {
        "Mock Fee Data Source"
    }

    fn supports_coin(&self, coin_type: CoinType) -> bool {
        self.fees.contains_key(&coin_type)
    }
}

impl Default for MockFeeDataSource {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[test]
    fn test_fee_rate() {
        let fee_rate = FeeRate::new(20);
        assert_eq!(fee_rate.satoshis_per_byte(), 20);
        assert_eq!(fee_rate.btc_per_byte(), 0.0000002);

        let btc_rate = FeeRate::from_btc_per_byte(0.0000001);
        assert_eq!(btc_rate.satoshis_per_byte(), 10);

        let gwei_rate = FeeRate::from_gwei(20.0);
        assert_eq!(gwei_rate.to_gwei(), 20.0);
    }

    #[test]
    fn test_fee_strategy() {
        let strategy = FeeStrategy::Standard;
        assert_eq!(strategy.confirmation_target(CoinType::Bitcoin), 6);
        assert_eq!(strategy.estimated_time_minutes(CoinType::Bitcoin), 60);

        let custom_strategy = FeeStrategy::Custom(50);
        assert_eq!(custom_strategy.confirmation_target(CoinType::Bitcoin), 6);
    }

    #[test]
    fn test_fee_estimate() {
        let fee_rate = FeeRate::new(20);
        let estimate = FeeEstimate::new(
            FeeStrategy::Standard,
            fee_rate,
            4000,
            200,
            CoinType::Bitcoin,
        );

        assert_eq!(estimate.strategy, FeeStrategy::Standard);
        assert_eq!(estimate.fee_rate, fee_rate);
        assert_eq!(estimate.total_fee, 4000);
        assert!(estimate.is_fresh());
    }

    #[tokio::test]
    async fn test_smart_fee_estimator() {
        let mut estimator = SmartFeeEstimator::new(Duration::from_secs(300));
        estimator.add_data_source(Box::new(MockFeeDataSource::new()));

        let estimate = estimator.estimate_fee(
            CoinType::Bitcoin,
            200,
            FeeStrategy::Standard,
        ).await.unwrap();

        assert_eq!(estimate.strategy, FeeStrategy::Standard);
        assert_eq!(estimate.transaction_size, 200);
        assert!(estimate.total_fee > 0);
    }

    #[tokio::test]
    async fn test_fee_recommendations() {
        let mut estimator = SmartFeeEstimator::new(Duration::from_secs(300));
        estimator.add_data_source(Box::new(MockFeeDataSource::new()));

        let recommendations = estimator.get_fee_recommendations(CoinType::Bitcoin).await.unwrap();

        assert!(recommendations.economy.satoshis_per_byte() < recommendations.standard.satoshis_per_byte());
        assert!(recommendations.standard.satoshis_per_byte() < recommendations.priority.satoshis_per_byte());
        assert!(recommendations.priority.satoshis_per_byte() < recommendations.urgent.satoshis_per_byte());
    }

    #[tokio::test]
    async fn test_fallback_fees() {
        let estimator = SmartFeeEstimator::new(Duration::from_secs(300));
        // No data sources added, should use fallback

        let network_fees = estimator.get_network_fees(CoinType::Bitcoin).await.unwrap();
        assert!(network_fees.min_relay_fee.satoshis_per_byte() > 0);
        assert!(network_fees.average_fee.satoshis_per_byte() > 0);
        assert!(!network_fees.recommended_fees.is_empty());
    }
}