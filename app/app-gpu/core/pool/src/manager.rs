//! Pool management for multi-pool operations and failover

use crate::client::{ClientStats, PoolClient};
use crate::config::{MultiPoolConfig, PoolConfig, PoolSelectionStrategy};
use crate::error::{PoolError, PoolResult};
use async_trait::async_trait;
use dashmap::DashMap;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{mpsc, RwLock};
use tokio::task::JoinHandle;
use tokio::time::interval;
use uuid::Uuid;

/// Pool manager for managing multiple pool connections
pub struct PoolManager {
    /// Pool client
    client: Arc<RwLock<PoolClient>>,
    /// Pool configuration
    config: PoolConfig,
    /// Manager statistics
    stats: Arc<RwLock<ManagerStats>>,
    /// Event sender
    event_sender: mpsc::Sender<crate::PoolEvent>,
    /// Background tasks
    background_tasks: Vec<JoinHandle<()>>,
}

/// Manager statistics
#[derive(Debug, Clone)]
pub struct ManagerStats {
    /// Start time
    pub started_at: Instant,
    /// Total uptime
    pub uptime: Duration,
    /// Connection switches count
    pub connection_switches: u64,
    /// Total errors
    pub total_errors: u64,
    /// Last error
    pub last_error: Option<String>,
    /// Last switch time
    pub last_switch: Option<Instant>,
}

impl PoolManager {
    /// Create a new pool manager
    pub fn new(config: PoolConfig, event_sender: mpsc::Sender<crate::PoolEvent>) -> Self {
        let client = Arc::new(RwLock::new(PoolClient::new(config.clone())));
        let stats = Arc::new(RwLock::new(ManagerStats::new()));

        Self {
            client,
            config,
            stats,
            event_sender,
            background_tasks: Vec::new(),
        }
    }

    /// Start the pool manager
    pub async fn start(&mut self) -> PoolResult<()> {
        // Connect to the pool
        {
            let mut client = self.client.write().await;
            client.full_setup().await?;
        }

        // Start monitoring task
        let monitoring_task = self.spawn_monitoring_task();
        self.background_tasks.push(monitoring_task);

        tracing::info!("Pool manager started for pool: {}", self.config.name);
        Ok(())
    }

    /// Stop the pool manager
    pub async fn stop(&mut self) -> PoolResult<()> {
        // Disconnect from pool
        {
            let mut client = self.client.write().await;
            client.disconnect().await?;
        }

        // Stop background tasks
        for task in self.background_tasks.drain(..) {
            task.abort();
        }

        tracing::info!("Pool manager stopped for pool: {}", self.config.name);
        Ok(())
    }

    /// Submit a mining share
    pub async fn submit_share(&self, share: crate::MiningShare) -> PoolResult<bool> {
        let mut client = self.client.write().await;
        client.submit_share(share).await
    }

    /// Get pool statistics
    pub async fn get_pool_stats(&self) -> PoolResult<crate::PoolStats> {
        let client = self.client.read().await;
        client.get_pool_stats().await
    }

    /// Get manager statistics
    pub async fn get_manager_stats(&self) -> ManagerStats {
        let mut stats = self.stats.write().await;
        stats.uptime = stats.started_at.elapsed();
        stats.clone()
    }

    /// Check if the manager is ready for mining
    pub async fn is_ready(&self) -> bool {
        let client = self.client.read().await;
        client.is_ready().await
    }

    /// Spawn monitoring task
    fn spawn_monitoring_task(&self) -> JoinHandle<()> {
        let client = Arc::clone(&self.client);
        let stats = Arc::clone(&self.stats);
        let event_sender = self.event_sender.clone();
        let pool_id = self.config.id;

        tokio::spawn(async move {
            let mut interval = interval(Duration::from_secs(60));

            loop {
                interval.tick().await;

                // Check client health
                let client_guard = client.read().await;
                if !client_guard.is_ready().await {
                    // Client is not ready, send error event
                    let event = crate::PoolEvent::Error {
                        pool_id,
                        error: "Pool client is not ready".to_string(),
                    };

                    if let Err(e) = event_sender.send(event).await {
                        tracing::warn!("Failed to send error event: {}", e);
                    }

                    // Update error count
                    let mut stats_guard = stats.write().await;
                    stats_guard.total_errors += 1;
                    stats_guard.last_error = Some("Pool client is not ready".to_string());
                }
                drop(client_guard);
            }
        })
    }
}

/// Multi-pool manager for managing multiple pools and automatic switching
pub struct MultiPoolManager {
    /// Configuration
    config: MultiPoolConfig,
    /// Pool managers
    pool_managers: DashMap<Uuid, PoolManager>,
    /// Active pool ID
    active_pool_id: Arc<RwLock<Option<Uuid>>>,
    /// Pool profitability cache
    profitability_cache: Arc<RwLock<HashMap<Uuid, crate::PoolProfitability>>>,
    /// Manager statistics
    stats: Arc<RwLock<MultiManagerStats>>,
    /// Event sender
    event_sender: mpsc::Sender<crate::PoolEvent>,
    /// Background tasks
    background_tasks: Vec<JoinHandle<()>>,
}

/// Multi-manager statistics
#[derive(Debug, Clone)]
pub struct MultiManagerStats {
    /// Start time
    pub started_at: Instant,
    /// Total uptime
    pub uptime: Duration,
    /// Pool switches count
    pub pool_switches: u64,
    /// Total errors across all pools
    pub total_errors: u64,
    /// Pool statistics
    pub pool_stats: HashMap<Uuid, ManagerStats>,
    /// Current active pool
    pub active_pool: Option<Uuid>,
    /// Last profitability check
    pub last_profitability_check: Option<Instant>,
}

impl MultiPoolManager {
    /// Create a new multi-pool manager
    pub fn new(config: MultiPoolConfig) -> Self {
        let (event_sender, _) = mpsc::channel(1000);
        let stats = Arc::new(RwLock::new(MultiManagerStats::new()));

        Self {
            config,
            pool_managers: DashMap::new(),
            active_pool_id: Arc::new(RwLock::new(None)),
            profitability_cache: Arc::new(RwLock::new(HashMap::new())),
            stats,
            event_sender,
            background_tasks: Vec::new(),
        }
    }

    /// Start the multi-pool manager
    pub async fn start(&mut self) -> PoolResult<()> {
        // Initialize pool managers
        for pool_config in &self.config.pools {
            let pool_manager = PoolManager::new(pool_config.clone(), self.event_sender.clone());
            self.pool_managers.insert(pool_config.id, pool_manager);
        }

        // Select initial pool
        let initial_pool_id = self.select_pool().await?;
        self.switch_to_pool(initial_pool_id).await?;

        // Start background tasks
        self.start_background_tasks().await;

        tracing::info!("Multi-pool manager started with {} pools", self.config.pools.len());
        Ok(())
    }

    /// Stop the multi-pool manager
    pub async fn stop(&mut self) -> PoolResult<()> {
        // Stop all pool managers
        for mut manager in self.pool_managers.iter_mut() {
            manager.value_mut().stop().await?;
        }

        // Stop background tasks
        for task in self.background_tasks.drain(..) {
            task.abort();
        }

        tracing::info!("Multi-pool manager stopped");
        Ok(())
    }

    /// Submit a mining share to the active pool
    pub async fn submit_share(&self, share: crate::MiningShare) -> PoolResult<bool> {
        let active_pool_id = self.active_pool_id.read().await
            .ok_or_else(|| PoolError::PoolManager("No active pool".to_string()))?;

        let manager = self.pool_managers.get(&active_pool_id)
            .ok_or_else(|| PoolError::PoolNotFound { pool_id: active_pool_id })?;

        manager.submit_share(share).await
    }

    /// Get statistics for all pools
    pub async fn get_all_pool_stats(&self) -> PoolResult<HashMap<Uuid, crate::PoolStats>> {
        let mut all_stats = HashMap::new();

        for manager_entry in self.pool_managers.iter() {
            let pool_id = *manager_entry.key();
            let manager = manager_entry.value();

            match manager.get_pool_stats().await {
                Ok(stats) => {
                    all_stats.insert(pool_id, stats);
                }
                Err(e) => {
                    tracing::warn!("Failed to get stats for pool {}: {}", pool_id, e);
                }
            }
        }

        Ok(all_stats)
    }

    /// Get multi-manager statistics
    pub async fn get_multi_manager_stats(&self) -> MultiManagerStats {
        let mut stats = self.stats.write().await;
        stats.uptime = stats.started_at.elapsed();

        // Collect pool manager stats
        for manager_entry in self.pool_managers.iter() {
            let pool_id = *manager_entry.key();
            let manager = manager_entry.value();

            if let Ok(manager_stats) = tokio::time::timeout(
                Duration::from_secs(1),
                manager.get_manager_stats(),
            ).await {
                stats.pool_stats.insert(pool_id, manager_stats);
            }
        }

        stats.active_pool = *self.active_pool_id.read().await;
        stats.clone()
    }

    /// Get active pool ID
    pub async fn get_active_pool_id(&self) -> Option<Uuid> {
        *self.active_pool_id.read().await
    }

    /// Check if ready for mining
    pub async fn is_ready(&self) -> bool {
        if let Some(active_pool_id) = *self.active_pool_id.read().await {
            if let Some(manager) = self.pool_managers.get(&active_pool_id) {
                return manager.is_ready().await;
            }
        }
        false
    }

    /// Switch to a specific pool
    pub async fn switch_to_pool(&self, pool_id: Uuid) -> PoolResult<()> {
        // Check if pool exists
        if !self.pool_managers.contains_key(&pool_id) {
            return Err(PoolError::PoolNotFound { pool_id });
        }

        let previous_pool_id = *self.active_pool_id.read().await;

        // Stop previous pool if different
        if let Some(prev_id) = previous_pool_id {
            if prev_id != pool_id {
                if let Some(mut prev_manager) = self.pool_managers.get_mut(&prev_id) {
                    if let Err(e) = prev_manager.stop().await {
                        tracing::warn!("Error stopping previous pool {}: {}", prev_id, e);
                    }
                }
            }
        }

        // Start new pool
        if let Some(mut new_manager) = self.pool_managers.get_mut(&pool_id) {
            new_manager.start().await?;
        }

        // Update active pool
        *self.active_pool_id.write().await = Some(pool_id);

        // Update statistics
        {
            let mut stats = self.stats.write().await;
            if previous_pool_id.is_some() && previous_pool_id != Some(pool_id) {
                stats.pool_switches += 1;
            }
        }

        // Send pool switch event
        if let Some(from_pool_id) = previous_pool_id {
            if from_pool_id != pool_id {
                let event = crate::PoolEvent::PoolSwitched {
                    from: from_pool_id,
                    to: pool_id,
                };
                if let Err(e) = self.event_sender.send(event).await {
                    tracing::warn!("Failed to send pool switch event: {}", e);
                }
            }
        }

        tracing::info!("Switched to pool: {}", pool_id);
        Ok(())
    }

    /// Select the best pool based on strategy
    async fn select_pool(&self) -> PoolResult<Uuid> {
        match &self.config.strategy {
            PoolSelectionStrategy::Priority => {
                // Select pool with highest priority (lowest number)
                self.config.pools
                    .iter()
                    .min_by_key(|p| p.priority)
                    .map(|p| p.id)
                    .ok_or_else(|| PoolError::PoolManager("No pools configured".to_string()))
            }
            PoolSelectionStrategy::Profitability => {
                // Select most profitable pool
                self.select_most_profitable_pool().await
            }
            PoolSelectionStrategy::RoundRobin => {
                // Simple round-robin (could be improved with state tracking)
                self.config.pools
                    .first()
                    .map(|p| p.id)
                    .ok_or_else(|| PoolError::PoolManager("No pools configured".to_string()))
            }
            PoolSelectionStrategy::LowestLatency => {
                // Select pool with lowest latency
                self.select_lowest_latency_pool().await
            }
            PoolSelectionStrategy::Weighted { weights } => {
                // Select pool based on weights (simplified)
                weights.keys()
                    .find(|id| self.pool_managers.contains_key(id))
                    .copied()
                    .ok_or_else(|| PoolError::PoolManager("No valid weighted pools found".to_string()))
            }
        }
    }

    /// Select the most profitable pool
    async fn select_most_profitable_pool(&self) -> PoolResult<Uuid> {
        let profitability = self.profitability_cache.read().await;

        profitability
            .values()
            .max_by(|a, b| a.score.partial_cmp(&b.score).unwrap_or(std::cmp::Ordering::Equal))
            .map(|p| p.pool_id)
            .ok_or_else(|| PoolError::PoolManager("No profitability data available".to_string()))
    }

    /// Select the pool with the lowest latency
    async fn select_lowest_latency_pool(&self) -> PoolResult<Uuid> {
        let mut best_pool_id = None;
        let mut best_latency = f64::INFINITY;

        for manager_entry in self.pool_managers.iter() {
            let pool_id = *manager_entry.key();
            let manager = manager_entry.value();

            if let Ok(stats) = manager.get_pool_stats().await {
                if stats.latency_ms < best_latency {
                    best_latency = stats.latency_ms;
                    best_pool_id = Some(pool_id);
                }
            }
        }

        best_pool_id.ok_or_else(|| PoolError::PoolManager("No pool latency data available".to_string()))
    }

    /// Start background tasks
    async fn start_background_tasks(&mut self) {
        // Profitability monitoring task
        if matches!(self.config.strategy, PoolSelectionStrategy::Profitability) {
            let profitability_task = self.spawn_profitability_task();
            self.background_tasks.push(profitability_task);
        }

        // Health monitoring task
        let health_task = self.spawn_health_monitoring_task();
        self.background_tasks.push(health_task);

        // Failover monitoring task
        if self.config.enable_failover {
            let failover_task = self.spawn_failover_task();
            self.background_tasks.push(failover_task);
        }
    }

    /// Spawn profitability monitoring task
    fn spawn_profitability_task(&self) -> JoinHandle<()> {
        let profitability_cache = Arc::clone(&self.profitability_cache);
        let stats = Arc::clone(&self.stats);
        let check_interval = self.config.profitability_check_interval;
        let pool_configs = self.config.pools.clone();

        tokio::spawn(async move {
            let mut interval = interval(check_interval);

            loop {
                interval.tick().await;

                // Update profitability data (simplified)
                let mut cache = profitability_cache.write().await;
                let mut stats_guard = stats.write().await;

                for pool_config in &pool_configs {
                    // In a real implementation, this would fetch actual profitability data
                    let profitability = crate::PoolProfitability {
                        pool_id: pool_config.id,
                        name: pool_config.name.clone(),
                        reward_per_mhs: 1.0, // Placeholder
                        fee_percent: pool_config.fee_percent,
                        difficulty: 1000.0,   // Placeholder
                        block_reward: 6.25,   // Placeholder
                        score: 1.0 - (pool_config.fee_percent / 100.0), // Simple score
                        updated_at: chrono::Utc::now(),
                    };

                    cache.insert(pool_config.id, profitability);
                }

                stats_guard.last_profitability_check = Some(Instant::now());
                drop(stats_guard);
                drop(cache);

                tracing::debug!("Updated profitability data for {} pools", pool_configs.len());
            }
        })
    }

    /// Spawn health monitoring task
    fn spawn_health_monitoring_task(&self) -> JoinHandle<()> {
        let pool_managers = self.pool_managers.clone();
        let event_sender = self.event_sender.clone();

        tokio::spawn(async move {
            let mut interval = interval(Duration::from_secs(30));

            loop {
                interval.tick().await;

                for manager_entry in pool_managers.iter() {
                    let pool_id = *manager_entry.key();
                    let manager = manager_entry.value();

                    if !manager.is_ready().await {
                        let event = crate::PoolEvent::StatusChanged {
                            pool_id,
                            status: crate::ConnectionStatus::Error,
                        };

                        if let Err(e) = event_sender.send(event).await {
                            tracing::warn!("Failed to send health status event: {}", e);
                        }
                    }
                }
            }
        })
    }

    /// Spawn failover monitoring task
    fn spawn_failover_task(&self) -> JoinHandle<()> {
        let active_pool_id = Arc::clone(&self.active_pool_id);
        let pool_managers = self.pool_managers.clone();
        let stats = Arc::clone(&self.stats);
        let failover_config = self.config.failover.clone();

        tokio::spawn(async move {
            let mut interval = interval(failover_config.health_check_interval);

            loop {
                interval.tick().await;

                if let Some(current_pool_id) = *active_pool_id.read().await {
                    if let Some(manager) = pool_managers.get(&current_pool_id) {
                        if !manager.is_ready().await {
                            tracing::warn!("Active pool {} failed health check, initiating failover", current_pool_id);

                            // Update error count
                            {
                                let mut stats_guard = stats.write().await;
                                stats_guard.total_errors += 1;
                            }

                            // Trigger failover (simplified implementation)
                            // In a real implementation, this would trigger pool switching logic
                        }
                    }
                }
            }
        })
    }
}

impl ManagerStats {
    /// Create new manager statistics
    pub fn new() -> Self {
        Self {
            started_at: Instant::now(),
            uptime: Duration::new(0, 0),
            connection_switches: 0,
            total_errors: 0,
            last_error: None,
            last_switch: None,
        }
    }
}

impl MultiManagerStats {
    /// Create new multi-manager statistics
    pub fn new() -> Self {
        Self {
            started_at: Instant::now(),
            uptime: Duration::new(0, 0),
            pool_switches: 0,
            total_errors: 0,
            pool_stats: HashMap::new(),
            active_pool: None,
            last_profitability_check: None,
        }
    }
}

impl Default for ManagerStats {
    fn default() -> Self {
        Self::new()
    }
}

impl Default for MultiManagerStats {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::StratumVersion;

    fn create_test_pool_config(name: &str, priority: u32) -> PoolConfig {
        PoolConfig {
            id: Uuid::new_v4(),
            name: name.to_string(),
            url: format!("stratum+tcp://{}.pool.com", name.to_lowercase()),
            port: 4444,
            user: "test_user".to_string(),
            worker: "test_worker".to_string(),
            password: "test_pass".to_string(),
            priority,
            fee_percent: 1.0,
            use_tls: false,
            stratum: crate::config::StratumConfig {
                version: StratumVersion::V1,
                user_agent: "OPUS-GPU-Test/1.0".to_string(),
                extra_nonce1_size: 4,
                session_id: None,
                compression: false,
                difficulty: crate::config::DifficultyConfig::default(),
            },
            connection: crate::config::ConnectionConfig::default(),
            settings: HashMap::new(),
        }
    }

    #[tokio::test]
    async fn test_pool_manager_creation() {
        let config = create_test_pool_config("test", 1);
        let (sender, _receiver) = mpsc::channel(100);
        let manager = PoolManager::new(config.clone(), sender);

        assert_eq!(manager.config.name, "test");
    }

    #[tokio::test]
    async fn test_multi_pool_manager_creation() {
        let pool1 = create_test_pool_config("pool1", 1);
        let pool2 = create_test_pool_config("pool2", 2);

        let multi_config = MultiPoolConfig {
            pools: vec![pool1, pool2],
            strategy: PoolSelectionStrategy::Priority,
            ..Default::default()
        };

        let manager = MultiPoolManager::new(multi_config);
        assert_eq!(manager.pool_managers.len(), 0); // Managers are created on start()
    }

    #[tokio::test]
    async fn test_pool_selection_priority() {
        let pool1 = create_test_pool_config("pool1", 2);
        let pool2 = create_test_pool_config("pool2", 1); // Higher priority (lower number)

        let multi_config = MultiPoolConfig {
            pools: vec![pool1, pool2.clone()],
            strategy: PoolSelectionStrategy::Priority,
            ..Default::default()
        };

        let manager = MultiPoolManager::new(multi_config);
        let selected_pool_id = manager.select_pool().await.unwrap();

        assert_eq!(selected_pool_id, pool2.id);
    }

    #[test]
    fn test_manager_stats() {
        let stats = ManagerStats::new();
        assert_eq!(stats.connection_switches, 0);
        assert_eq!(stats.total_errors, 0);
        assert!(stats.last_error.is_none());
    }
}