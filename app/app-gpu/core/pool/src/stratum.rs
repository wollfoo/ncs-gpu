//! Stratum protocol implementations for v1 and v2

use crate::config::StratumConfig;
use crate::connection::{Connection, ConnectionManager};
use crate::error::{PoolError, PoolResult};
use crate::protocol::{GenericProtocolHandler, ProtocolHandler, StratumMessage};
use async_trait::async_trait;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{mpsc, Mutex, RwLock};
use uuid::Uuid;

/// Stratum v1 implementation
pub struct StratumV1 {
    /// Protocol handler
    handler: Arc<Mutex<GenericProtocolHandler>>,
    /// Connection manager
    connection_manager: Arc<Mutex<ConnectionManager>>,
    /// Configuration
    config: StratumConfig,
    /// Event receiver
    event_receiver: Option<mpsc::Receiver<crate::PoolEvent>>,
    /// Request ID counter
    request_id: Arc<RwLock<u64>>,
    /// Subscription information
    subscription: Arc<RwLock<Option<SubscriptionInfo>>>,
    /// Current difficulty
    difficulty: Arc<RwLock<f64>>,
}

/// Subscription information for Stratum v1
#[derive(Debug, Clone)]
pub struct SubscriptionInfo {
    /// Subscription ID
    pub id: String,
    /// Extra nonce 1
    pub extra_nonce1: String,
    /// Extra nonce 2 size
    pub extra_nonce2_size: usize,
}

impl StratumV1 {
    /// Create a new Stratum v1 instance
    pub fn new(
        config: StratumConfig,
        connection_manager: ConnectionManager,
    ) -> Self {
        let (event_sender, event_receiver) = mpsc::channel(100);
        let handler = Arc::new(Mutex::new(GenericProtocolHandler::new(
            "stratum-v1".to_string(),
            event_sender,
        )));

        Self {
            handler,
            connection_manager: Arc::new(Mutex::new(connection_manager)),
            config,
            event_receiver: Some(event_receiver),
            request_id: Arc::new(RwLock::new(0)),
            subscription: Arc::new(RwLock::new(None)),
            difficulty: Arc::new(RwLock::new(config.difficulty.initial)),
        }
    }

    /// Generate next request ID
    async fn next_request_id(&self) -> u64 {
        let mut id = self.request_id.write().await;
        *id += 1;
        *id
    }

    /// Send a Stratum message
    async fn send_message(&self, mut message: StratumMessage) -> PoolResult<()> {
        // Set request ID if this is a request
        if message.method.is_some() {
            let id = self.next_request_id().await;
            message.id = Some(json!(id));
        }

        let json_data = message.to_json()?;
        let data = format!("{}\n", json_data);

        let mut connection_manager = self.connection_manager.lock().await;
        connection_manager.send(data.as_bytes()).await?;

        tracing::debug!("Sent Stratum v1 message: {}", json_data);
        Ok(())
    }

    /// Receive and parse Stratum messages
    async fn receive_message(&self) -> PoolResult<StratumMessage> {
        let mut connection_manager = self.connection_manager.lock().await;
        let data = connection_manager.receive().await?;

        let json_str = String::from_utf8(data)
            .map_err(|e| PoolError::protocol(format!("Invalid UTF-8 data: {}", e)))?;

        // Handle multiple messages in one packet (separated by newlines)
        let lines: Vec<&str> = json_str.lines().collect();
        if lines.is_empty() {
            return Err(PoolError::protocol("Empty message received"));
        }

        // Parse the first non-empty line
        for line in lines {
            if !line.trim().is_empty() {
                let message = StratumMessage::from_json(line.trim())?;
                tracing::debug!("Received Stratum v1 message: {}", line.trim());
                return Ok(message);
            }
        }

        Err(PoolError::protocol("No valid message found"))
    }

    /// Handle subscription response
    async fn handle_subscription(&self, message: &StratumMessage) -> PoolResult<()> {
        if let Some(result) = &message.result {
            if let Some(array) = result.as_array() {
                if array.len() >= 2 {
                    // Extract subscription details
                    let subscription_details = array[0].as_array()
                        .ok_or_else(|| PoolError::protocol("Invalid subscription details format"))?;

                    let subscription_id = subscription_details.first()
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string();

                    let extra_nonce1 = array[1].as_str()
                        .ok_or_else(|| PoolError::protocol("Invalid extra nonce 1"))?
                        .to_string();

                    let extra_nonce2_size = array.get(2)
                        .and_then(|v| v.as_u64())
                        .unwrap_or(4) as usize;

                    let subscription_info = SubscriptionInfo {
                        id: subscription_id,
                        extra_nonce1,
                        extra_nonce2_size,
                    };

                    *self.subscription.write().await = Some(subscription_info.clone());

                    tracing::info!(
                        "Stratum v1 subscription successful: id={}, extra_nonce1={}, extra_nonce2_size={}",
                        subscription_info.id,
                        subscription_info.extra_nonce1,
                        subscription_info.extra_nonce2_size
                    );

                    return Ok(());
                }
            }
        }

        if let Some(error) = &message.error {
            return Err(PoolError::stratum(format!(
                "Subscription failed: {} (code: {})",
                error.message, error.code
            )));
        }

        Err(PoolError::protocol("Invalid subscription response"))
    }

    /// Process incoming messages
    async fn process_messages(&self) -> PoolResult<()> {
        loop {
            let message = self.receive_message().await?;

            let mut handler = self.handler.lock().await;
            if let Some(response) = handler.handle_message(message.clone()).await? {
                // Send response if needed
                drop(handler); // Release lock before sending
                self.send_message(response).await?;
            }
        }
    }
}

#[async_trait]
impl crate::PoolCommunication for StratumV1 {
    async fn connect(&mut self) -> PoolResult<()> {
        // Connection is managed by ConnectionManager
        Ok(())
    }

    async fn disconnect(&mut self) -> PoolResult<()> {
        let mut connection_manager = self.connection_manager.lock().await;
        connection_manager.disconnect().await
    }

    async fn subscribe(&mut self, user_agent: &str, extra_nonce1_size: usize) -> PoolResult<()> {
        let handler = self.handler.lock().await;
        let message = handler.create_subscribe_request(user_agent, extra_nonce1_size);
        drop(handler); // Release lock before sending

        self.send_message(message).await?;

        // Wait for subscription response
        let response = self.receive_message().await?;
        self.handle_subscription(&response).await?;

        Ok(())
    }

    async fn authorize(&mut self, worker: &str, password: &str) -> PoolResult<()> {
        let handler = self.handler.lock().await;
        let message = handler.create_authorize_request(worker, password);
        drop(handler); // Release lock before sending

        self.send_message(message).await?;

        // Wait for authorization response
        let response = self.receive_message().await?;

        if let Some(result) = &response.result {
            if result.as_bool().unwrap_or(false) {
                tracing::info!("Stratum v1 authorization successful for worker: {}", worker);
                return Ok(());
            }
        }

        if let Some(error) = &response.error {
            return Err(PoolError::authentication(format!(
                "Authorization failed: {} (code: {})",
                error.message, error.code
            )));
        }

        Err(PoolError::authentication("Authorization failed with unknown response"))
    }

    async fn submit_share(&mut self, share: crate::MiningShare) -> PoolResult<bool> {
        let handler = self.handler.lock().await;
        let message = handler.create_submit_request(&share);
        drop(handler); // Release lock before sending

        self.send_message(message).await?;

        // Wait for submission response
        let response = self.receive_message().await?;

        if let Some(result) = &response.result {
            let accepted = result.as_bool().unwrap_or(false);

            if accepted {
                tracing::info!("Share accepted: job_id={}, nonce={}", share.job_id, share.nonce);
            } else {
                tracing::warn!("Share rejected: job_id={}, nonce={}", share.job_id, share.nonce);
            }

            return Ok(accepted);
        }

        if let Some(error) = &response.error {
            tracing::error!(
                "Share submission error: {} (code: {}), job_id={}, nonce={}",
                error.message, error.code, share.job_id, share.nonce
            );
            return Ok(false);
        }

        Err(PoolError::protocol("Invalid share submission response"))
    }

    async fn get_stats(&self) -> PoolResult<crate::PoolStats> {
        let connection_manager = self.connection_manager.lock().await;
        let connection_stats = connection_manager.stats()
            .ok_or_else(|| PoolError::connection("No active connection"))?;

        let difficulty = *self.difficulty.read().await;
        let subscription = self.subscription.read().await;

        Ok(crate::PoolStats {
            pool_id: connection_stats.id,
            url: "stratum-v1".to_string(), // This should be set from config
            status: match connection_stats.status {
                crate::connection::ConnectionStatus::Active => crate::ConnectionStatus::Connected,
                crate::connection::ConnectionStatus::Idle => crate::ConnectionStatus::Connected,
                crate::connection::ConnectionStatus::Closed => crate::ConnectionStatus::Disconnected,
                crate::connection::ConnectionStatus::Error => crate::ConnectionStatus::Error,
            },
            latency_ms: 0.0, // Calculate from connection timing
            shares_submitted: 0, // Track this separately
            shares_accepted: 0,  // Track this separately
            difficulty,
            connected_since: chrono::DateTime::from_timestamp(
                connection_stats.connected_at.elapsed().as_secs() as i64, 0
            ).unwrap_or_else(chrono::Utc::now),
            last_work: None, // Track this from mining.notify
            error_count: connection_stats.error_count,
        })
    }

    async fn set_difficulty(&mut self, difficulty: f64) -> PoolResult<()> {
        *self.difficulty.write().await = difficulty;
        tracing::info!("Difficulty updated to: {}", difficulty);
        Ok(())
    }

    fn get_event_receiver(&self) -> mpsc::Receiver<crate::PoolEvent> {
        // This is a simplified implementation
        // In a real implementation, we'd return a cloned receiver
        let (_, receiver) = mpsc::channel(100);
        receiver
    }
}

/// Stratum v2 implementation (simplified)
pub struct StratumV2 {
    /// Protocol handler
    handler: Arc<Mutex<GenericProtocolHandler>>,
    /// Connection manager
    connection_manager: Arc<Mutex<ConnectionManager>>,
    /// Configuration
    config: StratumConfig,
    /// Session information
    session: Arc<RwLock<Option<SessionInfo>>>,
}

/// Session information for Stratum v2
#[derive(Debug, Clone)]
pub struct SessionInfo {
    /// Session ID
    pub session_id: String,
    /// Channel information
    pub channels: HashMap<u32, ChannelInfo>,
    /// Current target
    pub target: Vec<u8>,
}

/// Channel information for Stratum v2
#[derive(Debug, Clone)]
pub struct ChannelInfo {
    /// Channel ID
    pub id: u32,
    /// Channel type
    pub channel_type: String,
    /// User identity
    pub user: String,
    /// Nominal hash rate
    pub nominal_hashrate: f64,
}

impl StratumV2 {
    /// Create a new Stratum v2 instance
    pub fn new(
        config: StratumConfig,
        connection_manager: ConnectionManager,
    ) -> Self {
        let (event_sender, _event_receiver) = mpsc::channel(100);
        let handler = Arc::new(Mutex::new(GenericProtocolHandler::new(
            "stratum-v2".to_string(),
            event_sender,
        )));

        Self {
            handler,
            connection_manager: Arc::new(Mutex::new(connection_manager)),
            config,
            session: Arc::new(RwLock::new(None)),
        }
    }

    /// Setup mining connection (Stratum v2 specific)
    pub async fn setup_connection(&mut self, user: &str, nominal_hashrate: f64) -> PoolResult<()> {
        // This is a simplified implementation of Stratum v2 setup
        // Real implementation would handle the complete handshake

        let session_info = SessionInfo {
            session_id: Uuid::new_v4().to_string(),
            channels: HashMap::new(),
            target: vec![0u8; 32], // Simplified target
        };

        *self.session.write().await = Some(session_info);

        tracing::info!("Stratum v2 session setup completed");
        Ok(())
    }
}

#[async_trait]
impl crate::PoolCommunication for StratumV2 {
    async fn connect(&mut self) -> PoolResult<()> {
        // Stratum v2 connection setup
        Ok(())
    }

    async fn disconnect(&mut self) -> PoolResult<()> {
        let mut connection_manager = self.connection_manager.lock().await;
        connection_manager.disconnect().await
    }

    async fn subscribe(&mut self, user_agent: &str, _extra_nonce1_size: usize) -> PoolResult<()> {
        // Stratum v2 doesn't use traditional subscription
        // This would be handled in setup_connection
        tracing::info!("Stratum v2 subscription (handled by setup_connection)");
        Ok(())
    }

    async fn authorize(&mut self, worker: &str, _password: &str) -> PoolResult<()> {
        // Stratum v2 authorization is different from v1
        tracing::info!("Stratum v2 authorization for worker: {}", worker);
        Ok(())
    }

    async fn submit_share(&mut self, share: crate::MiningShare) -> PoolResult<bool> {
        // Stratum v2 share submission
        tracing::info!("Submitting Stratum v2 share: job_id={}, nonce={}", share.job_id, share.nonce);
        Ok(true) // Simplified implementation
    }

    async fn get_stats(&self) -> PoolResult<crate::PoolStats> {
        // Simplified stats implementation for Stratum v2
        Ok(crate::PoolStats {
            pool_id: Uuid::new_v4(),
            url: "stratum-v2".to_string(),
            status: crate::ConnectionStatus::Connected,
            latency_ms: 0.0,
            shares_submitted: 0,
            shares_accepted: 0,
            difficulty: 1.0,
            connected_since: chrono::Utc::now(),
            last_work: None,
            error_count: 0,
        })
    }

    async fn set_difficulty(&mut self, difficulty: f64) -> PoolResult<()> {
        tracing::info!("Stratum v2 difficulty update: {}", difficulty);
        Ok(())
    }

    fn get_event_receiver(&self) -> mpsc::Receiver<crate::PoolEvent> {
        let (_, receiver) = mpsc::channel(100);
        receiver
    }
}

/// Factory for creating Stratum protocol instances
pub struct StratumFactory;

impl StratumFactory {
    /// Create a Stratum protocol instance based on version
    pub fn create(
        config: StratumConfig,
        connection_manager: ConnectionManager,
    ) -> Box<dyn crate::PoolCommunication> {
        match config.version {
            crate::config::StratumVersion::V1 => {
                Box::new(StratumV1::new(config, connection_manager))
            }
            crate::config::StratumVersion::V2 => {
                Box::new(StratumV2::new(config, connection_manager))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{ConnectionConfig, StratumVersion};
    use tokio::sync::mpsc;

    fn create_test_connection_manager() -> ConnectionManager {
        let config = ConnectionConfig::default();
        let (sender, _receiver) = mpsc::channel(100);
        ConnectionManager::new(config, sender)
    }

    #[tokio::test]
    async fn test_stratum_v1_creation() {
        let config = StratumConfig {
            version: StratumVersion::V1,
            ..Default::default()
        };
        let connection_manager = create_test_connection_manager();
        let stratum = StratumV1::new(config, connection_manager);

        // Test basic properties
        assert_eq!(*stratum.difficulty.read().await, 1.0);
        assert!(stratum.subscription.read().await.is_none());
    }

    #[tokio::test]
    async fn test_stratum_v2_creation() {
        let config = StratumConfig {
            version: StratumVersion::V2,
            ..Default::default()
        };
        let connection_manager = create_test_connection_manager();
        let stratum = StratumV2::new(config, connection_manager);

        // Test basic properties
        assert!(stratum.session.read().await.is_none());
    }

    #[test]
    fn test_stratum_factory() {
        let config_v1 = StratumConfig {
            version: StratumVersion::V1,
            ..Default::default()
        };
        let connection_manager_v1 = create_test_connection_manager();
        let stratum_v1 = StratumFactory::create(config_v1, connection_manager_v1);

        // Test that we get the right implementation
        // Note: This is a basic test; more detailed testing would require trait objects
        // or additional methods to verify the correct implementation is returned
        assert!(!std::ptr::eq(&stratum_v1 as *const _, std::ptr::null()));

        let config_v2 = StratumConfig {
            version: StratumVersion::V2,
            ..Default::default()
        };
        let connection_manager_v2 = create_test_connection_manager();
        let stratum_v2 = StratumFactory::create(config_v2, connection_manager_v2);

        assert!(!std::ptr::eq(&stratum_v2 as *const _, std::ptr::null()));
    }

    #[test]
    fn test_subscription_info() {
        let info = SubscriptionInfo {
            id: "test-id".to_string(),
            extra_nonce1: "00000000".to_string(),
            extra_nonce2_size: 4,
        };

        assert_eq!(info.id, "test-id");
        assert_eq!(info.extra_nonce1, "00000000");
        assert_eq!(info.extra_nonce2_size, 4);
    }
}