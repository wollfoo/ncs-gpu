//! Pool client implementation with high-level API

use crate::config::{ConnectionConfig, PoolConfig, StratumConfig};
use crate::connection::{ConnectionManager, ConnectionEvent};
use crate::error::{PoolError, PoolResult};
use crate::stratum::StratumFactory;
use async_trait::async_trait;
use std::sync::Arc;
use tokio::sync::{mpsc, RwLock};
use tokio::task::JoinHandle;
use tokio::time::{interval, Duration, Instant};

/// High-level pool client
pub struct PoolClient {
    /// Pool configuration
    config: PoolConfig,
    /// Stratum implementation
    stratum: Option<Box<dyn crate::PoolCommunication>>,
    /// Connection manager
    connection_manager: Option<ConnectionManager>,
    /// Client state
    state: Arc<RwLock<ClientState>>,
    /// Event sender
    event_sender: mpsc::Sender<crate::PoolEvent>,
    /// Event receiver (for external consumption)
    event_receiver: Option<mpsc::Receiver<crate::PoolEvent>>,
    /// Background tasks
    background_tasks: Vec<JoinHandle<()>>,
    /// Statistics
    stats: Arc<RwLock<ClientStats>>,
}

/// Client state
#[derive(Debug, Clone, PartialEq)]
pub enum ClientState {
    Disconnected,
    Connecting,
    Connected,
    Authenticated,
    Subscribed,
    Error(String),
}

/// Client statistics
#[derive(Debug, Clone)]
pub struct ClientStats {
    /// Total connection attempts
    pub connection_attempts: u64,
    /// Successful connections
    pub successful_connections: u64,
    /// Failed connections
    pub failed_connections: u64,
    /// Total shares submitted
    pub shares_submitted: u64,
    /// Shares accepted
    pub shares_accepted: u64,
    /// Shares rejected
    pub shares_rejected: u64,
    /// Average latency (milliseconds)
    pub avg_latency_ms: f64,
    /// Uptime duration
    pub uptime: Duration,
    /// Last connection time
    pub last_connected: Option<Instant>,
    /// Last error
    pub last_error: Option<String>,
}

impl PoolClient {
    /// Create a new pool client
    pub fn new(config: PoolConfig) -> Self {
        let (event_sender, event_receiver) = mpsc::channel(1000);

        Self {
            config,
            stratum: None,
            connection_manager: None,
            state: Arc::new(RwLock::new(ClientState::Disconnected)),
            event_sender,
            event_receiver: Some(event_receiver),
            background_tasks: Vec::new(),
            stats: Arc::new(RwLock::new(ClientStats::new())),
        }
    }

    /// Connect to the mining pool
    pub async fn connect(&mut self) -> PoolResult<()> {
        self.set_state(ClientState::Connecting).await;
        self.increment_connection_attempts().await;

        // Create connection manager
        let (connection_event_sender, connection_event_receiver) = mpsc::channel(100);
        let connection_manager = ConnectionManager::new(
            self.config.connection.clone(),
            connection_event_sender,
        );

        // Create Stratum implementation
        let mut stratum = StratumFactory::create(
            self.config.stratum.clone(),
            connection_manager,
        );

        // Attempt connection
        match stratum.connect().await {
            Ok(()) => {
                self.set_state(ClientState::Connected).await;
                self.increment_successful_connections().await;
                self.stratum = Some(stratum);

                // Start background tasks
                self.start_background_tasks(connection_event_receiver).await;

                tracing::info!("Successfully connected to pool: {}", self.config.name);
                Ok(())
            }
            Err(e) => {
                self.set_state(ClientState::Error(e.to_string())).await;
                self.increment_failed_connections().await;
                self.set_last_error(e.to_string()).await;

                tracing::error!("Failed to connect to pool {}: {}", self.config.name, e);
                Err(e)
            }
        }
    }

    /// Disconnect from the mining pool
    pub async fn disconnect(&mut self) -> PoolResult<()> {
        if let Some(mut stratum) = self.stratum.take() {
            stratum.disconnect().await?;
        }

        // Stop background tasks
        for task in self.background_tasks.drain(..) {
            task.abort();
        }

        self.set_state(ClientState::Disconnected).await;
        tracing::info!("Disconnected from pool: {}", self.config.name);
        Ok(())
    }

    /// Subscribe to mining work
    pub async fn subscribe(&mut self) -> PoolResult<()> {
        let stratum = self.stratum.as_mut()
            .ok_or_else(|| PoolError::connection("Not connected to pool"))?;

        stratum.subscribe(
            &self.config.stratum.user_agent,
            self.config.stratum.extra_nonce1_size,
        ).await?;

        self.set_state(ClientState::Subscribed).await;
        tracing::info!("Successfully subscribed to mining work");
        Ok(())
    }

    /// Authorize worker
    pub async fn authorize(&mut self) -> PoolResult<()> {
        let stratum = self.stratum.as_mut()
            .ok_or_else(|| PoolError::connection("Not connected to pool"))?;

        stratum.authorize(&self.config.user, &self.config.password).await?;

        self.set_state(ClientState::Authenticated).await;
        tracing::info!("Worker authorized successfully: {}", self.config.worker);
        Ok(())
    }

    /// Submit a mining share
    pub async fn submit_share(&mut self, share: crate::MiningShare) -> PoolResult<bool> {
        let stratum = self.stratum.as_mut()
            .ok_or_else(|| PoolError::connection("Not connected to pool"))?;

        self.increment_shares_submitted().await;

        let start_time = Instant::now();
        let result = stratum.submit_share(share).await?;
        let latency = start_time.elapsed().as_millis() as f64;

        // Update latency statistics
        self.update_latency(latency).await;

        if result {
            self.increment_shares_accepted().await;
        } else {
            self.increment_shares_rejected().await;
        }

        Ok(result)
    }

    /// Get current pool statistics
    pub async fn get_pool_stats(&self) -> PoolResult<crate::PoolStats> {
        let stratum = self.stratum.as_ref()
            .ok_or_else(|| PoolError::connection("Not connected to pool"))?;

        stratum.get_stats().await
    }

    /// Get client statistics
    pub async fn get_client_stats(&self) -> ClientStats {
        self.stats.read().await.clone()
    }

    /// Get current client state
    pub async fn get_state(&self) -> ClientState {
        self.state.read().await.clone()
    }

    /// Check if client is connected and authenticated
    pub async fn is_ready(&self) -> bool {
        matches!(
            *self.state.read().await,
            ClientState::Authenticated | ClientState::Subscribed
        )
    }

    /// Get event receiver for external consumption
    pub fn take_event_receiver(&mut self) -> Option<mpsc::Receiver<crate::PoolEvent>> {
        self.event_receiver.take()
    }

    /// Perform full connection setup (connect, subscribe, authorize)
    pub async fn full_setup(&mut self) -> PoolResult<()> {
        self.connect().await?;
        self.subscribe().await?;
        self.authorize().await?;
        Ok(())
    }

    /// Reconnect with exponential backoff
    pub async fn reconnect(&mut self) -> PoolResult<()> {
        tracing::info!("Attempting to reconnect to pool: {}", self.config.name);

        // Disconnect first if needed
        if !matches!(*self.state.read().await, ClientState::Disconnected) {
            if let Err(e) = self.disconnect().await {
                tracing::warn!("Error during disconnect before reconnect: {}", e);
            }
        }

        // Attempt full setup
        self.full_setup().await
    }

    /// Start background tasks
    async fn start_background_tasks(&mut self, connection_event_receiver: mpsc::Receiver<ConnectionEvent>) {
        // Health check task
        let health_check_task = self.spawn_health_check_task();
        self.background_tasks.push(health_check_task);

        // Connection event handler task
        let connection_event_task = self.spawn_connection_event_task(connection_event_receiver);
        self.background_tasks.push(connection_event_task);

        // Statistics update task
        let stats_task = self.spawn_statistics_task();
        self.background_tasks.push(stats_task);
    }

    /// Spawn health check task
    fn spawn_health_check_task(&self) -> JoinHandle<()> {
        let state = Arc::clone(&self.state);
        let event_sender = self.event_sender.clone();
        let pool_id = self.config.id;

        tokio::spawn(async move {
            let mut interval = interval(Duration::from_secs(30));

            loop {
                interval.tick().await;

                let current_state = state.read().await.clone();
                match current_state {
                    ClientState::Connected | ClientState::Authenticated | ClientState::Subscribed => {
                        // Connection is healthy, continue monitoring
                    }
                    ClientState::Error(error) => {
                        // Send error event
                        let event = crate::PoolEvent::Error {
                            pool_id,
                            error: error.clone(),
                        };
                        if let Err(e) = event_sender.send(event).await {
                            tracing::warn!("Failed to send error event: {}", e);
                        }
                    }
                    ClientState::Disconnected => {
                        // Connection is down, this is expected if we're not trying to connect
                        break;
                    }
                    ClientState::Connecting => {
                        // Still connecting, wait
                        continue;
                    }
                }
            }
        })
    }

    /// Spawn connection event handler task
    fn spawn_connection_event_task(&self, mut connection_event_receiver: mpsc::Receiver<ConnectionEvent>) -> JoinHandle<()> {
        let event_sender = self.event_sender.clone();
        let pool_id = self.config.id;

        tokio::spawn(async move {
            while let Some(connection_event) = connection_event_receiver.recv().await {
                let pool_event = match connection_event {
                    ConnectionEvent::Connected { address } => {
                        tracing::info!("Connection established to: {}", address);
                        crate::PoolEvent::StatusChanged {
                            pool_id,
                            status: crate::ConnectionStatus::Connected,
                        }
                    }
                    ConnectionEvent::Disconnected { address, reason } => {
                        tracing::warn!("Connection lost to {}: {}", address, reason);
                        crate::PoolEvent::StatusChanged {
                            pool_id,
                            status: crate::ConnectionStatus::Disconnected,
                        }
                    }
                    ConnectionEvent::Reconnecting { address, attempt } => {
                        tracing::info!("Reconnecting to {} (attempt {})", address, attempt);
                        crate::PoolEvent::StatusChanged {
                            pool_id,
                            status: crate::ConnectionStatus::Connecting,
                        }
                    }
                    ConnectionEvent::ReconnectFailed { address, error } => {
                        tracing::error!("Reconnection to {} failed: {}", address, error);
                        crate::PoolEvent::Error {
                            pool_id,
                            error: format!("Reconnection failed: {}", error),
                        }
                    }
                    ConnectionEvent::Error { address, error } => {
                        tracing::error!("Connection error for {}: {}", address, error);
                        crate::PoolEvent::Error {
                            pool_id,
                            error: format!("Connection error: {}", error),
                        }
                    }
                };

                if let Err(e) = event_sender.send(pool_event).await {
                    tracing::warn!("Failed to send pool event: {}", e);
                }
            }
        })
    }

    /// Spawn statistics update task
    fn spawn_statistics_task(&self) -> JoinHandle<()> {
        let stats = Arc::clone(&self.stats);

        tokio::spawn(async move {
            let mut interval = interval(Duration::from_secs(60));
            let start_time = Instant::now();

            loop {
                interval.tick().await;

                // Update uptime
                let mut stats_guard = stats.write().await;
                stats_guard.uptime = start_time.elapsed();
                drop(stats_guard);
            }
        })
    }

    /// Update client state
    async fn set_state(&self, new_state: ClientState) {
        let mut state = self.state.write().await;
        if *state != new_state {
            tracing::debug!("Pool client state changed: {:?} -> {:?}", *state, new_state);
            *state = new_state;
        }
    }

    /// Increment connection attempts
    async fn increment_connection_attempts(&self) {
        let mut stats = self.stats.write().await;
        stats.connection_attempts += 1;
    }

    /// Increment successful connections
    async fn increment_successful_connections(&self) {
        let mut stats = self.stats.write().await;
        stats.successful_connections += 1;
        stats.last_connected = Some(Instant::now());
    }

    /// Increment failed connections
    async fn increment_failed_connections(&self) {
        let mut stats = self.stats.write().await;
        stats.failed_connections += 1;
    }

    /// Increment shares submitted
    async fn increment_shares_submitted(&self) {
        let mut stats = self.stats.write().await;
        stats.shares_submitted += 1;
    }

    /// Increment shares accepted
    async fn increment_shares_accepted(&self) {
        let mut stats = self.stats.write().await;
        stats.shares_accepted += 1;
    }

    /// Increment shares rejected
    async fn increment_shares_rejected(&self) {
        let mut stats = self.stats.write().await;
        stats.shares_rejected += 1;
    }

    /// Update latency statistics
    async fn update_latency(&self, latency_ms: f64) {
        let mut stats = self.stats.write().await;
        // Simple moving average (could be improved with exponential weighted average)
        let total_submissions = stats.shares_submitted;
        if total_submissions > 0 {
            stats.avg_latency_ms = ((stats.avg_latency_ms * (total_submissions - 1) as f64) + latency_ms) / total_submissions as f64;
        } else {
            stats.avg_latency_ms = latency_ms;
        }
    }

    /// Set last error
    async fn set_last_error(&self, error: String) {
        let mut stats = self.stats.write().await;
        stats.last_error = Some(error);
    }
}

impl ClientStats {
    /// Create new client statistics
    pub fn new() -> Self {
        Self {
            connection_attempts: 0,
            successful_connections: 0,
            failed_connections: 0,
            shares_submitted: 0,
            shares_accepted: 0,
            shares_rejected: 0,
            avg_latency_ms: 0.0,
            uptime: Duration::new(0, 0),
            last_connected: None,
            last_error: None,
        }
    }

    /// Calculate acceptance rate as percentage
    pub fn acceptance_rate(&self) -> f64 {
        if self.shares_submitted > 0 {
            (self.shares_accepted as f64 / self.shares_submitted as f64) * 100.0
        } else {
            0.0
        }
    }

    /// Calculate rejection rate as percentage
    pub fn rejection_rate(&self) -> f64 {
        if self.shares_submitted > 0 {
            (self.shares_rejected as f64 / self.shares_submitted as f64) * 100.0
        } else {
            0.0
        }
    }

    /// Calculate connection success rate as percentage
    pub fn connection_success_rate(&self) -> f64 {
        if self.connection_attempts > 0 {
            (self.successful_connections as f64 / self.connection_attempts as f64) * 100.0
        } else {
            0.0
        }
    }
}

impl Default for ClientStats {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for PoolClient {
    fn drop(&mut self) {
        // Abort all background tasks
        for task in self.background_tasks.drain(..) {
            task.abort();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{StratumVersion, DifficultyConfig};

    fn create_test_config() -> PoolConfig {
        PoolConfig {
            id: uuid::Uuid::new_v4(),
            name: "Test Pool".to_string(),
            url: "stratum+tcp://test.pool.com".to_string(),
            port: 4444,
            user: "test_user".to_string(),
            worker: "test_worker".to_string(),
            password: "test_pass".to_string(),
            priority: 1,
            fee_percent: 1.0,
            use_tls: false,
            stratum: StratumConfig {
                version: StratumVersion::V1,
                user_agent: "OPUS-GPU-Test/1.0".to_string(),
                extra_nonce1_size: 4,
                session_id: None,
                compression: false,
                difficulty: DifficultyConfig::default(),
            },
            connection: ConnectionConfig::default(),
            settings: std::collections::HashMap::new(),
        }
    }

    #[tokio::test]
    async fn test_pool_client_creation() {
        let config = create_test_config();
        let client = PoolClient::new(config.clone());

        assert_eq!(client.config.name, "Test Pool");
        assert_eq!(client.get_state().await, ClientState::Disconnected);
        assert!(!client.is_ready().await);
    }

    #[tokio::test]
    async fn test_client_stats() {
        let mut stats = ClientStats::new();
        assert_eq!(stats.acceptance_rate(), 0.0);
        assert_eq!(stats.connection_success_rate(), 0.0);

        stats.connection_attempts = 10;
        stats.successful_connections = 8;
        assert_eq!(stats.connection_success_rate(), 80.0);

        stats.shares_submitted = 100;
        stats.shares_accepted = 95;
        stats.shares_rejected = 5;
        assert_eq!(stats.acceptance_rate(), 95.0);
        assert_eq!(stats.rejection_rate(), 5.0);
    }

    #[tokio::test]
    async fn test_state_transitions() {
        let config = create_test_config();
        let client = PoolClient::new(config);

        assert_eq!(client.get_state().await, ClientState::Disconnected);

        client.set_state(ClientState::Connecting).await;
        assert_eq!(client.get_state().await, ClientState::Connecting);

        client.set_state(ClientState::Connected).await;
        assert_eq!(client.get_state().await, ClientState::Connected);

        client.set_state(ClientState::Authenticated).await;
        assert!(client.is_ready().await);
    }
}