//! Connection management for pool communication

use crate::config::ConnectionConfig;
use crate::error::{PoolError, PoolResult};
use async_trait::async_trait;
use parking_lot::RwLock;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;
use tokio::sync::{mpsc, Mutex, Semaphore};
use tokio::time::timeout;
use tokio_native_tls::{TlsConnector, TlsStream};
use uuid::Uuid;

/// Connection trait for different connection types
#[async_trait]
pub trait Connection: Send + Sync {
    /// Send data over the connection
    async fn send(&mut self, data: &[u8]) -> PoolResult<()>;

    /// Receive data from the connection
    async fn receive(&mut self) -> PoolResult<Vec<u8>>;

    /// Check if connection is alive
    async fn is_alive(&self) -> bool;

    /// Close the connection
    async fn close(&mut self) -> PoolResult<()>;

    /// Get connection statistics
    fn stats(&self) -> ConnectionStats;
}

/// Connection statistics
#[derive(Debug, Clone)]
pub struct ConnectionStats {
    /// Connection ID
    pub id: Uuid,
    /// Connection type
    pub connection_type: ConnectionType,
    /// Connection status
    pub status: ConnectionStatus,
    /// Bytes sent
    pub bytes_sent: u64,
    /// Bytes received
    pub bytes_received: u64,
    /// Connection start time
    pub connected_at: Instant,
    /// Last activity time
    pub last_activity: Instant,
    /// Number of errors
    pub error_count: u64,
}

/// Connection type enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConnectionType {
    Tcp,
    TcpTls,
    WebSocket,
    WebSocketTls,
}

/// Connection status
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConnectionStatus {
    Idle,
    Active,
    Closed,
    Error,
}

/// TCP connection implementation
pub struct TcpConnection {
    /// Connection ID
    id: Uuid,
    /// TCP stream
    stream: TcpStream,
    /// Connection statistics
    stats: Arc<RwLock<ConnectionStats>>,
    /// Buffer for receiving data
    buffer: Vec<u8>,
}

impl TcpConnection {
    /// Create a new TCP connection
    pub async fn new(address: &str, config: &ConnectionConfig) -> PoolResult<Self> {
        let stream = timeout(config.timeout, TcpStream::connect(address))
            .await
            .map_err(|_| PoolError::timeout("Connection timeout"))?
            .map_err(|e| PoolError::connection(format!("Failed to connect: {}", e)))?;

        let id = Uuid::new_v4();
        let stats = Arc::new(RwLock::new(ConnectionStats {
            id,
            connection_type: ConnectionType::Tcp,
            status: ConnectionStatus::Active,
            bytes_sent: 0,
            bytes_received: 0,
            connected_at: Instant::now(),
            last_activity: Instant::now(),
            error_count: 0,
        }));

        Ok(Self {
            id,
            stream,
            stats,
            buffer: Vec::with_capacity(8192),
        })
    }
}

#[async_trait]
impl Connection for TcpConnection {
    async fn send(&mut self, data: &[u8]) -> PoolResult<()> {
        self.stream.write_all(data).await
            .map_err(|e| PoolError::connection(format!("Failed to send data: {}", e)))?;

        self.stream.flush().await
            .map_err(|e| PoolError::connection(format!("Failed to flush stream: {}", e)))?;

        // Update statistics
        {
            let mut stats = self.stats.write();
            stats.bytes_sent += data.len() as u64;
            stats.last_activity = Instant::now();
        }

        Ok(())
    }

    async fn receive(&mut self) -> PoolResult<Vec<u8>> {
        self.buffer.clear();
        self.buffer.resize(8192, 0);

        let bytes_read = self.stream.read(&mut self.buffer).await
            .map_err(|e| PoolError::connection(format!("Failed to receive data: {}", e)))?;

        if bytes_read == 0 {
            return Err(PoolError::connection("Connection closed by remote"));
        }

        self.buffer.truncate(bytes_read);

        // Update statistics
        {
            let mut stats = self.stats.write();
            stats.bytes_received += bytes_read as u64;
            stats.last_activity = Instant::now();
        }

        Ok(self.buffer.clone())
    }

    async fn is_alive(&self) -> bool {
        // Check if the connection is still readable
        let mut buf = [0u8; 1];
        match self.stream.try_read(&mut buf) {
            Ok(0) => false, // EOF
            Ok(_) => true,  // Data available
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => true, // No data, but connection is alive
            Err(_) => false, // Error
        }
    }

    async fn close(&mut self) -> PoolResult<()> {
        self.stream.shutdown().await
            .map_err(|e| PoolError::connection(format!("Failed to close connection: {}", e)))?;

        {
            let mut stats = self.stats.write();
            stats.status = ConnectionStatus::Closed;
        }

        Ok(())
    }

    fn stats(&self) -> ConnectionStats {
        self.stats.read().clone()
    }
}

/// TLS connection implementation
pub struct TlsConnection {
    /// Connection ID
    id: Uuid,
    /// TLS stream
    stream: TlsStream<TcpStream>,
    /// Connection statistics
    stats: Arc<RwLock<ConnectionStats>>,
    /// Buffer for receiving data
    buffer: Vec<u8>,
}

impl TlsConnection {
    /// Create a new TLS connection
    pub async fn new(address: &str, config: &ConnectionConfig) -> PoolResult<Self> {
        // Parse address to get hostname for TLS
        let (hostname, _) = address.split_once(':').unwrap_or((address, ""));

        let connector = TlsConnector::from(
            native_tls::TlsConnector::new()
                .map_err(|e| PoolError::tls(format!("Failed to create TLS connector: {}", e)))?
        );

        let tcp_stream = timeout(config.timeout, TcpStream::connect(address))
            .await
            .map_err(|_| PoolError::timeout("Connection timeout"))?
            .map_err(|e| PoolError::connection(format!("Failed to connect: {}", e)))?;

        let tls_stream = timeout(config.timeout, connector.connect(hostname, tcp_stream))
            .await
            .map_err(|_| PoolError::timeout("TLS handshake timeout"))?
            .map_err(|e| PoolError::tls(format!("TLS handshake failed: {}", e)))?;

        let id = Uuid::new_v4();
        let stats = Arc::new(RwLock::new(ConnectionStats {
            id,
            connection_type: ConnectionType::TcpTls,
            status: ConnectionStatus::Active,
            bytes_sent: 0,
            bytes_received: 0,
            connected_at: Instant::now(),
            last_activity: Instant::now(),
            error_count: 0,
        }));

        Ok(Self {
            id,
            stream: tls_stream,
            stats,
            buffer: Vec::with_capacity(8192),
        })
    }
}

#[async_trait]
impl Connection for TlsConnection {
    async fn send(&mut self, data: &[u8]) -> PoolResult<()> {
        self.stream.write_all(data).await
            .map_err(|e| PoolError::connection(format!("Failed to send data: {}", e)))?;

        self.stream.flush().await
            .map_err(|e| PoolError::connection(format!("Failed to flush stream: {}", e)))?;

        // Update statistics
        {
            let mut stats = self.stats.write();
            stats.bytes_sent += data.len() as u64;
            stats.last_activity = Instant::now();
        }

        Ok(())
    }

    async fn receive(&mut self) -> PoolResult<Vec<u8>> {
        self.buffer.clear();
        self.buffer.resize(8192, 0);

        let bytes_read = self.stream.read(&mut self.buffer).await
            .map_err(|e| PoolError::connection(format!("Failed to receive data: {}", e)))?;

        if bytes_read == 0 {
            return Err(PoolError::connection("Connection closed by remote"));
        }

        self.buffer.truncate(bytes_read);

        // Update statistics
        {
            let mut stats = self.stats.write();
            stats.bytes_received += bytes_read as u64;
            stats.last_activity = Instant::now();
        }

        Ok(self.buffer.clone())
    }

    async fn is_alive(&self) -> bool {
        // For TLS connections, we need to check the underlying TCP stream
        true // Simplified implementation
    }

    async fn close(&mut self) -> PoolResult<()> {
        self.stream.shutdown().await
            .map_err(|e| PoolError::connection(format!("Failed to close connection: {}", e)))?;

        {
            let mut stats = self.stats.write();
            stats.status = ConnectionStatus::Closed;
        }

        Ok(())
    }

    fn stats(&self) -> ConnectionStats {
        self.stats.read().clone()
    }
}

/// Connection pool for managing multiple connections
pub struct ConnectionPool {
    /// Pool configuration
    config: ConnectionConfig,
    /// Available connections
    connections: Arc<Mutex<Vec<Box<dyn Connection>>>>,
    /// Connection semaphore for limiting concurrent connections
    semaphore: Arc<Semaphore>,
    /// Pool statistics
    stats: Arc<RwLock<PoolStats>>,
}

/// Pool statistics
#[derive(Debug, Clone)]
pub struct PoolStats {
    /// Total connections created
    pub total_connections: u64,
    /// Active connections count
    pub active_connections: u64,
    /// Idle connections count
    pub idle_connections: u64,
    /// Failed connections count
    pub failed_connections: u64,
    /// Total bytes sent
    pub total_bytes_sent: u64,
    /// Total bytes received
    pub total_bytes_received: u64,
}

impl ConnectionPool {
    /// Create a new connection pool
    pub fn new(config: ConnectionConfig) -> Self {
        let semaphore = Arc::new(Semaphore::new(config.pool_size));
        let stats = Arc::new(RwLock::new(PoolStats {
            total_connections: 0,
            active_connections: 0,
            idle_connections: 0,
            failed_connections: 0,
            total_bytes_sent: 0,
            total_bytes_received: 0,
        }));

        Self {
            config,
            connections: Arc::new(Mutex::new(Vec::new())),
            semaphore,
            stats,
        }
    }

    /// Get a connection from the pool
    pub async fn get_connection(&self, address: &str, use_tls: bool) -> PoolResult<Box<dyn Connection>> {
        // Try to acquire a permit
        let _permit = self.semaphore.clone()
            .acquire_owned()
            .await
            .map_err(|_| PoolError::PoolExhausted)?;

        // Check for available connection in the pool
        {
            let mut connections = self.connections.lock().await;
            if let Some(connection) = connections.pop() {
                if connection.is_alive().await {
                    self.update_stats_on_acquire();
                    return Ok(connection);
                }
            }
        }

        // Create new connection
        let connection: Box<dyn Connection> = if use_tls {
            Box::new(TlsConnection::new(address, &self.config).await?)
        } else {
            Box::new(TcpConnection::new(address, &self.config).await?)
        };

        self.update_stats_on_create();

        Ok(connection)
    }

    /// Return a connection to the pool
    pub async fn return_connection(&self, mut connection: Box<dyn Connection>) -> PoolResult<()> {
        if connection.is_alive().await {
            let mut connections = self.connections.lock().await;
            connections.push(connection);
            self.update_stats_on_return();
        } else {
            connection.close().await?;
            self.update_stats_on_close();
        }

        Ok(())
    }

    /// Get pool statistics
    pub fn get_stats(&self) -> PoolStats {
        self.stats.read().clone()
    }

    /// Update statistics when creating a new connection
    fn update_stats_on_create(&self) {
        let mut stats = self.stats.write();
        stats.total_connections += 1;
        stats.active_connections += 1;
    }

    /// Update statistics when acquiring a connection
    fn update_stats_on_acquire(&self) {
        let mut stats = self.stats.write();
        stats.active_connections += 1;
        stats.idle_connections = stats.idle_connections.saturating_sub(1);
    }

    /// Update statistics when returning a connection
    fn update_stats_on_return(&self) {
        let mut stats = self.stats.write();
        stats.active_connections = stats.active_connections.saturating_sub(1);
        stats.idle_connections += 1;
    }

    /// Update statistics when closing a connection
    fn update_stats_on_close(&self) {
        let mut stats = self.stats.write();
        stats.active_connections = stats.active_connections.saturating_sub(1);
        stats.failed_connections += 1;
    }
}

/// Connection manager with reconnection and failover capabilities
pub struct ConnectionManager {
    /// Connection configuration
    config: ConnectionConfig,
    /// Current connection
    current_connection: Option<Box<dyn Connection>>,
    /// Connection pool
    pool: Arc<ConnectionPool>,
    /// Reconnection state
    reconnect_attempts: u32,
    /// Last connection attempt time
    last_attempt: Option<Instant>,
    /// Event sender for connection events
    event_sender: mpsc::Sender<ConnectionEvent>,
}

/// Connection events
#[derive(Debug, Clone)]
pub enum ConnectionEvent {
    Connected { address: String },
    Disconnected { address: String, reason: String },
    Reconnecting { address: String, attempt: u32 },
    ReconnectFailed { address: String, error: String },
    Error { address: String, error: String },
}

impl ConnectionManager {
    /// Create a new connection manager
    pub fn new(
        config: ConnectionConfig,
        event_sender: mpsc::Sender<ConnectionEvent>,
    ) -> Self {
        let pool = Arc::new(ConnectionPool::new(config.clone()));

        Self {
            config,
            current_connection: None,
            pool,
            reconnect_attempts: 0,
            last_attempt: None,
            event_sender,
        }
    }

    /// Connect to the specified address
    pub async fn connect(&mut self, address: &str, use_tls: bool) -> PoolResult<()> {
        match self.pool.get_connection(address, use_tls).await {
            Ok(connection) => {
                self.current_connection = Some(connection);
                self.reconnect_attempts = 0;
                self.last_attempt = Some(Instant::now());

                // Send connected event
                let event = ConnectionEvent::Connected {
                    address: address.to_string(),
                };
                if let Err(e) = self.event_sender.send(event).await {
                    tracing::warn!("Failed to send connection event: {}", e);
                }

                Ok(())
            }
            Err(e) => {
                self.reconnect_attempts += 1;

                // Send connection failed event
                let event = ConnectionEvent::ReconnectFailed {
                    address: address.to_string(),
                    error: e.to_string(),
                };
                if let Err(err) = self.event_sender.send(event).await {
                    tracing::warn!("Failed to send connection event: {}", err);
                }

                Err(e)
            }
        }
    }

    /// Disconnect from the current connection
    pub async fn disconnect(&mut self) -> PoolResult<()> {
        if let Some(mut connection) = self.current_connection.take() {
            connection.close().await?;
        }
        Ok(())
    }

    /// Send data through the current connection
    pub async fn send(&mut self, data: &[u8]) -> PoolResult<()> {
        match &mut self.current_connection {
            Some(connection) => connection.send(data).await,
            None => Err(PoolError::connection("No active connection")),
        }
    }

    /// Receive data from the current connection
    pub async fn receive(&mut self) -> PoolResult<Vec<u8>> {
        match &mut self.current_connection {
            Some(connection) => connection.receive().await,
            None => Err(PoolError::connection("No active connection")),
        }
    }

    /// Check if there's an active connection
    pub async fn is_connected(&self) -> bool {
        match &self.current_connection {
            Some(connection) => connection.is_alive().await,
            None => false,
        }
    }

    /// Attempt to reconnect with exponential backoff
    pub async fn reconnect(&mut self, address: &str, use_tls: bool) -> PoolResult<()> {
        if self.reconnect_attempts >= self.config.max_reconnects {
            return Err(PoolError::connection("Maximum reconnection attempts reached"));
        }

        // Calculate backoff delay
        let delay = std::cmp::min(
            self.config.reconnect_delay * (2_u32.pow(self.reconnect_attempts)),
            self.config.max_reconnect_delay,
        );

        // Check if enough time has passed since last attempt
        if let Some(last_attempt) = self.last_attempt {
            let elapsed = last_attempt.elapsed();
            if elapsed < delay {
                tokio::time::sleep(delay - elapsed).await;
            }
        }

        // Send reconnecting event
        let event = ConnectionEvent::Reconnecting {
            address: address.to_string(),
            attempt: self.reconnect_attempts + 1,
        };
        if let Err(e) = self.event_sender.send(event).await {
            tracing::warn!("Failed to send reconnecting event: {}", e);
        }

        self.connect(address, use_tls).await
    }

    /// Get connection statistics
    pub fn stats(&self) -> Option<ConnectionStats> {
        self.current_connection.as_ref().map(|c| c.stats())
    }

    /// Get pool statistics
    pub fn pool_stats(&self) -> PoolStats {
        self.pool.get_stats()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::sync::mpsc;

    #[tokio::test]
    async fn test_connection_pool_creation() {
        let config = ConnectionConfig::default();
        let pool = ConnectionPool::new(config);
        let stats = pool.get_stats();

        assert_eq!(stats.total_connections, 0);
        assert_eq!(stats.active_connections, 0);
    }

    #[tokio::test]
    async fn test_connection_manager_creation() {
        let config = ConnectionConfig::default();
        let (sender, _receiver) = mpsc::channel(100);
        let manager = ConnectionManager::new(config, sender);

        assert!(!manager.is_connected().await);
    }

    #[test]
    fn test_connection_stats() {
        let stats = ConnectionStats {
            id: Uuid::new_v4(),
            connection_type: ConnectionType::Tcp,
            status: ConnectionStatus::Active,
            bytes_sent: 100,
            bytes_received: 200,
            connected_at: Instant::now(),
            last_activity: Instant::now(),
            error_count: 0,
        };

        assert_eq!(stats.connection_type, ConnectionType::Tcp);
        assert_eq!(stats.bytes_sent, 100);
        assert_eq!(stats.bytes_received, 200);
    }
}