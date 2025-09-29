//! Configuration structures for pool communication

use crate::error::PoolResult;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::Duration;
use uuid::Uuid;

/// Pool configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoolConfig {
    /// Unique pool identifier
    pub id: Uuid,
    /// Pool name for display
    pub name: String,
    /// Pool server URL
    pub url: String,
    /// Pool server port
    pub port: u16,
    /// User/wallet address
    pub user: String,
    /// Worker name
    pub worker: String,
    /// Worker password
    pub password: String,
    /// Pool priority (lower number = higher priority)
    pub priority: u32,
    /// Pool fee percentage
    pub fee_percent: f64,
    /// Enable TLS/SSL
    pub use_tls: bool,
    /// Stratum protocol configuration
    pub stratum: StratumConfig,
    /// Connection configuration
    pub connection: ConnectionConfig,
    /// Pool-specific settings
    pub settings: HashMap<String, serde_json::Value>,
}

/// Stratum protocol configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StratumConfig {
    /// Stratum protocol version (1 or 2)
    pub version: StratumVersion,
    /// User agent string
    pub user_agent: String,
    /// Extra nonce 1 size for Stratum v1
    pub extra_nonce1_size: usize,
    /// Session ID for Stratum v2
    pub session_id: Option<String>,
    /// Enable compression
    pub compression: bool,
    /// Difficulty adjustment settings
    pub difficulty: DifficultyConfig,
}

/// Stratum protocol version
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum StratumVersion {
    #[serde(rename = "1")]
    V1,
    #[serde(rename = "2")]
    V2,
}

impl std::fmt::Display for StratumVersion {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            StratumVersion::V1 => write!(f, "1"),
            StratumVersion::V2 => write!(f, "2"),
        }
    }
}

/// Difficulty configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DifficultyConfig {
    /// Initial difficulty
    pub initial: f64,
    /// Minimum difficulty
    pub minimum: f64,
    /// Maximum difficulty
    pub maximum: f64,
    /// Difficulty adjustment variance threshold
    pub variance_percent: f64,
    /// Target time between shares (seconds)
    pub target_time: u32,
    /// Retarget period (number of shares)
    pub retarget_period: u32,
}

/// Connection configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionConfig {
    /// Connection timeout duration
    pub timeout: Duration,
    /// Maximum number of reconnection attempts
    pub max_reconnects: u32,
    /// Reconnection delay (exponential backoff base)
    pub reconnect_delay: Duration,
    /// Maximum reconnection delay
    pub max_reconnect_delay: Duration,
    /// Keep-alive interval
    pub keepalive_interval: Duration,
    /// Maximum idle time before reconnection
    pub max_idle_time: Duration,
    /// Enable connection pooling
    pub enable_pooling: bool,
    /// Maximum connections in pool
    pub pool_size: usize,
    /// Connection pool timeout
    pub pool_timeout: Duration,
}

/// Multi-pool management configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MultiPoolConfig {
    /// List of pool configurations
    pub pools: Vec<PoolConfig>,
    /// Pool selection strategy
    pub strategy: PoolSelectionStrategy,
    /// Profitability check interval
    pub profitability_check_interval: Duration,
    /// Switch threshold (percentage improvement required)
    pub switch_threshold_percent: f64,
    /// Minimum time before switching pools again
    pub switch_cooldown: Duration,
    /// Enable automatic failover
    pub enable_failover: bool,
    /// Failover detection settings
    pub failover: FailoverConfig,
}

/// Pool selection strategy
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PoolSelectionStrategy {
    /// Use pools in priority order
    #[serde(rename = "priority")]
    Priority,
    /// Switch based on profitability
    #[serde(rename = "profitability")]
    Profitability,
    /// Round-robin between pools
    #[serde(rename = "round_robin")]
    RoundRobin,
    /// Choose pool with lowest latency
    #[serde(rename = "lowest_latency")]
    LowestLatency,
    /// Load balancing with weights
    #[serde(rename = "weighted")]
    Weighted { weights: HashMap<Uuid, f64> },
}

/// Failover configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FailoverConfig {
    /// Maximum consecutive errors before failover
    pub max_errors: u32,
    /// Timeout threshold for failover (seconds)
    pub timeout_threshold: u32,
    /// Minimum hashrate threshold (percentage of expected)
    pub hashrate_threshold_percent: f64,
    /// Health check interval
    pub health_check_interval: Duration,
    /// Recovery check interval
    pub recovery_check_interval: Duration,
}

impl Default for PoolConfig {
    fn default() -> Self {
        Self {
            id: Uuid::new_v4(),
            name: "Default Pool".to_string(),
            url: "stratum+tcp://pool.example.com".to_string(),
            port: 4444,
            user: "wallet_address".to_string(),
            worker: "opus-gpu".to_string(),
            password: "x".to_string(),
            priority: 1,
            fee_percent: 1.0,
            use_tls: false,
            stratum: StratumConfig::default(),
            connection: ConnectionConfig::default(),
            settings: HashMap::new(),
        }
    }
}

impl Default for StratumConfig {
    fn default() -> Self {
        Self {
            version: StratumVersion::V1,
            user_agent: "OPUS-GPU/1.0.0".to_string(),
            extra_nonce1_size: 4,
            session_id: None,
            compression: false,
            difficulty: DifficultyConfig::default(),
        }
    }
}

impl Default for DifficultyConfig {
    fn default() -> Self {
        Self {
            initial: 1.0,
            minimum: 0.1,
            maximum: 1000000.0,
            variance_percent: 20.0,
            target_time: 30,
            retarget_period: 10,
        }
    }
}

impl Default for ConnectionConfig {
    fn default() -> Self {
        Self {
            timeout: Duration::from_secs(30),
            max_reconnects: 5,
            reconnect_delay: Duration::from_secs(1),
            max_reconnect_delay: Duration::from_secs(60),
            keepalive_interval: Duration::from_secs(60),
            max_idle_time: Duration::from_secs(300),
            enable_pooling: true,
            pool_size: 10,
            pool_timeout: Duration::from_secs(10),
        }
    }
}

impl Default for MultiPoolConfig {
    fn default() -> Self {
        Self {
            pools: vec![PoolConfig::default()],
            strategy: PoolSelectionStrategy::Priority,
            profitability_check_interval: Duration::from_secs(300),
            switch_threshold_percent: 5.0,
            switch_cooldown: Duration::from_secs(600),
            enable_failover: true,
            failover: FailoverConfig::default(),
        }
    }
}

impl Default for FailoverConfig {
    fn default() -> Self {
        Self {
            max_errors: 5,
            timeout_threshold: 30,
            hashrate_threshold_percent: 80.0,
            health_check_interval: Duration::from_secs(30),
            recovery_check_interval: Duration::from_secs(60),
        }
    }
}

impl PoolConfig {
    /// Create a new pool configuration
    pub fn new(name: &str, url: &str, port: u16, user: &str) -> Self {
        Self {
            id: Uuid::new_v4(),
            name: name.to_string(),
            url: url.to_string(),
            port,
            user: user.to_string(),
            ..Default::default()
        }
    }

    /// Set worker name
    pub fn with_worker(mut self, worker: &str) -> Self {
        self.worker = worker.to_string();
        self
    }

    /// Set password
    pub fn with_password(mut self, password: &str) -> Self {
        self.password = password.to_string();
        self
    }

    /// Enable TLS
    pub fn with_tls(mut self, use_tls: bool) -> Self {
        self.use_tls = use_tls;
        self
    }

    /// Set priority
    pub fn with_priority(mut self, priority: u32) -> Self {
        self.priority = priority;
        self
    }

    /// Set Stratum version
    pub fn with_stratum_version(mut self, version: StratumVersion) -> Self {
        self.stratum.version = version;
        self
    }

    /// Get the full server address
    pub fn server_address(&self) -> String {
        format!("{}:{}", self.url, self.port)
    }

    /// Validate configuration
    pub fn validate(&self) -> PoolResult<()> {
        if self.name.is_empty() {
            return Err(crate::error::PoolError::invalid_config("Pool name cannot be empty"));
        }

        if self.url.is_empty() {
            return Err(crate::error::PoolError::invalid_config("Pool URL cannot be empty"));
        }

        if self.port == 0 {
            return Err(crate::error::PoolError::invalid_config("Pool port cannot be zero"));
        }

        if self.user.is_empty() {
            return Err(crate::error::PoolError::invalid_config("User/wallet address cannot be empty"));
        }

        if self.worker.is_empty() {
            return Err(crate::error::PoolError::invalid_config("Worker name cannot be empty"));
        }

        if !(0.0..=100.0).contains(&self.fee_percent) {
            return Err(crate::error::PoolError::invalid_config("Fee percentage must be between 0 and 100"));
        }

        Ok(())
    }
}

impl MultiPoolConfig {
    /// Create a new multi-pool configuration
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a pool configuration
    pub fn add_pool(mut self, pool: PoolConfig) -> Self {
        self.pools.push(pool);
        self
    }

    /// Set selection strategy
    pub fn with_strategy(mut self, strategy: PoolSelectionStrategy) -> Self {
        self.strategy = strategy;
        self
    }

    /// Enable failover
    pub fn with_failover(mut self, enable: bool) -> Self {
        self.enable_failover = enable;
        self
    }

    /// Validate multi-pool configuration
    pub fn validate(&self) -> PoolResult<()> {
        if self.pools.is_empty() {
            return Err(crate::error::PoolError::invalid_config("At least one pool must be configured"));
        }

        for pool in &self.pools {
            pool.validate()?;
        }

        if self.switch_threshold_percent < 0.0 || self.switch_threshold_percent > 100.0 {
            return Err(crate::error::PoolError::invalid_config("Switch threshold must be between 0 and 100"));
        }

        Ok(())
    }

    /// Get pools sorted by priority
    pub fn get_pools_by_priority(&self) -> Vec<&PoolConfig> {
        let mut pools: Vec<&PoolConfig> = self.pools.iter().collect();
        pools.sort_by_key(|p| p.priority);
        pools
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pool_config_creation() {
        let config = PoolConfig::new("Test Pool", "stratum+tcp://test.com", 4444, "test_user");
        assert_eq!(config.name, "Test Pool");
        assert_eq!(config.url, "stratum+tcp://test.com");
        assert_eq!(config.port, 4444);
        assert_eq!(config.user, "test_user");
    }

    #[test]
    fn test_pool_config_validation() {
        let mut config = PoolConfig::default();
        assert!(config.validate().is_ok());

        config.name = String::new();
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_multi_pool_config() {
        let pool1 = PoolConfig::new("Pool 1", "stratum+tcp://pool1.com", 4444, "user1");
        let pool2 = PoolConfig::new("Pool 2", "stratum+tcp://pool2.com", 4444, "user2")
            .with_priority(2);

        let config = MultiPoolConfig::new()
            .add_pool(pool1)
            .add_pool(pool2)
            .with_strategy(PoolSelectionStrategy::Priority);

        assert!(config.validate().is_ok());
        assert_eq!(config.pools.len(), 2);

        let sorted_pools = config.get_pools_by_priority();
        assert_eq!(sorted_pools[0].priority, 1);
        assert_eq!(sorted_pools[1].priority, 2);
    }

    #[test]
    fn test_stratum_version_display() {
        assert_eq!(StratumVersion::V1.to_string(), "1");
        assert_eq!(StratumVersion::V2.to_string(), "2");
    }
}