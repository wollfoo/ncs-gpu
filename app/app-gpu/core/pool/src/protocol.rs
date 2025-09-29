//! Protocol handling for Stratum communication

use crate::error::{PoolError, PoolResult};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use tokio::sync::mpsc;
use uuid::Uuid;

/// Stratum message structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StratumMessage {
    /// Message ID (for request/response matching)
    pub id: Option<Value>,
    /// Method name (for requests)
    pub method: Option<String>,
    /// Parameters (for requests)
    pub params: Option<Value>,
    /// Result (for responses)
    pub result: Option<Value>,
    /// Error (for error responses)
    pub error: Option<StratumError>,
}

/// Stratum error structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StratumError {
    /// Error code
    pub code: i32,
    /// Error message
    pub message: String,
    /// Additional error data
    pub data: Option<Value>,
}

/// Protocol handler trait for different Stratum versions
#[async_trait]
pub trait ProtocolHandler: Send + Sync {
    /// Handle incoming message
    async fn handle_message(&mut self, message: StratumMessage) -> PoolResult<Option<StratumMessage>>;

    /// Create subscription request
    fn create_subscribe_request(&self, user_agent: &str, extra_nonce1_size: usize) -> StratumMessage;

    /// Create authorization request
    fn create_authorize_request(&self, user: &str, password: &str) -> StratumMessage;

    /// Create share submission request
    fn create_submit_request(&self, share: &crate::MiningShare) -> StratumMessage;

    /// Parse mining work from notification
    fn parse_mining_work(&self, message: &StratumMessage) -> PoolResult<Option<crate::MiningWork>>;

    /// Parse difficulty change notification
    fn parse_difficulty_change(&self, message: &StratumMessage) -> PoolResult<Option<f64>>;

    /// Get protocol version
    fn version(&self) -> &str;
}

/// Generic protocol handler implementation
pub struct GenericProtocolHandler {
    /// Protocol version
    version: String,
    /// Request ID counter
    request_id: u64,
    /// Pending requests
    pending_requests: HashMap<u64, String>,
    /// Event sender
    event_sender: mpsc::Sender<crate::PoolEvent>,
    /// Session information
    session: SessionInfo,
}

/// Session information for protocol handling
#[derive(Debug, Clone)]
pub struct SessionInfo {
    /// Session ID
    pub id: Option<String>,
    /// Extra nonce 1
    pub extra_nonce1: Option<String>,
    /// Extra nonce 2 size
    pub extra_nonce2_size: usize,
    /// Current difficulty
    pub difficulty: f64,
    /// Subscription details
    pub subscription_details: Option<SubscriptionDetails>,
}

/// Subscription details
#[derive(Debug, Clone)]
pub struct SubscriptionDetails {
    /// Subscription ID
    pub id: String,
    /// Extra nonce 1
    pub extra_nonce1: String,
    /// Extra nonce 2 size
    pub extra_nonce2_size: usize,
}

impl GenericProtocolHandler {
    /// Create a new generic protocol handler
    pub fn new(
        version: String,
        event_sender: mpsc::Sender<crate::PoolEvent>,
    ) -> Self {
        Self {
            version,
            request_id: 0,
            pending_requests: HashMap::new(),
            event_sender,
            session: SessionInfo {
                id: None,
                extra_nonce1: None,
                extra_nonce2_size: 4,
                difficulty: 1.0,
                subscription_details: None,
            },
        }
    }

    /// Generate next request ID
    fn next_request_id(&mut self) -> u64 {
        self.request_id += 1;
        self.request_id
    }

    /// Handle subscription response
    async fn handle_subscription_response(&mut self, message: &StratumMessage) -> PoolResult<()> {
        if let Some(result) = &message.result {
            if let Some(array) = result.as_array() {
                if array.len() >= 2 {
                    // Extract subscription details
                    let subscription_id = array[0].as_array()
                        .and_then(|arr| arr.first())
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string();

                    let extra_nonce1 = array[1].as_str().unwrap_or("").to_string();
                    let extra_nonce2_size = array.get(2)
                        .and_then(|v| v.as_u64())
                        .unwrap_or(4) as usize;

                    self.session.subscription_details = Some(SubscriptionDetails {
                        id: subscription_id,
                        extra_nonce1: extra_nonce1.clone(),
                        extra_nonce2_size,
                    });

                    self.session.extra_nonce1 = Some(extra_nonce1);
                    self.session.extra_nonce2_size = extra_nonce2_size;

                    tracing::info!("Subscription successful: extra_nonce1={}, extra_nonce2_size={}",
                        self.session.extra_nonce1.as_ref().unwrap_or(&"none".to_string()),
                        self.session.extra_nonce2_size
                    );
                }
            }
        } else if let Some(error) = &message.error {
            return Err(PoolError::stratum(format!(
                "Subscription failed: {} (code: {})",
                error.message, error.code
            )));
        }

        Ok(())
    }

    /// Handle authorization response
    async fn handle_authorization_response(&mut self, message: &StratumMessage) -> PoolResult<()> {
        if let Some(result) = &message.result {
            if result.as_bool().unwrap_or(false) {
                tracing::info!("Worker authorization successful");
            } else {
                return Err(PoolError::authentication("Worker authorization failed"));
            }
        } else if let Some(error) = &message.error {
            return Err(PoolError::authentication(format!(
                "Authorization failed: {} (code: {})",
                error.message, error.code
            )));
        }

        Ok(())
    }

    /// Handle share submission response
    async fn handle_submit_response(&mut self, message: &StratumMessage) -> PoolResult<()> {
        let accepted = if let Some(result) = &message.result {
            result.as_bool().unwrap_or(false)
        } else {
            false
        };

        let reason = message.error.as_ref().map(|e| e.message.clone());

        // Send share result event
        let event = crate::PoolEvent::ShareResult {
            id: message.id.as_ref()
                .and_then(|v| v.as_str())
                .unwrap_or("unknown")
                .to_string(),
            accepted,
            reason,
        };

        if let Err(e) = self.event_sender.send(event).await {
            tracing::warn!("Failed to send share result event: {}", e);
        }

        Ok(())
    }

    /// Handle mining notification
    async fn handle_mining_notify(&mut self, message: &StratumMessage) -> PoolResult<Option<crate::MiningWork>> {
        if message.method.as_deref() != Some("mining.notify") {
            return Ok(None);
        }

        let params = message.params.as_ref()
            .and_then(|p| p.as_array())
            .ok_or_else(|| PoolError::protocol("Invalid mining.notify parameters"))?;

        if params.len() < 8 {
            return Err(PoolError::protocol("Insufficient parameters for mining.notify"));
        }

        let job_id = params[0].as_str()
            .ok_or_else(|| PoolError::protocol("Invalid job ID"))?
            .to_string();

        let previous_hash = params[1].as_str()
            .ok_or_else(|| PoolError::protocol("Invalid previous hash"))?;

        let coinb1 = params[2].as_str()
            .ok_or_else(|| PoolError::protocol("Invalid coinbase1"))?;

        let coinb2 = params[3].as_str()
            .ok_or_else(|| PoolError::protocol("Invalid coinbase2"))?;

        let merkle_branches = params[4].as_array()
            .ok_or_else(|| PoolError::protocol("Invalid merkle branches"))?;

        let version = params[5].as_str()
            .ok_or_else(|| PoolError::protocol("Invalid version"))?;

        let nbits = params[6].as_str()
            .ok_or_else(|| PoolError::protocol("Invalid nbits"))?;

        let ntime = params[7].as_str()
            .ok_or_else(|| PoolError::protocol("Invalid ntime"))?;

        let clean_jobs = params.get(8)
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        // Create mining work
        let work = crate::MiningWork {
            id: Uuid::new_v4().to_string(),
            data: format!("{}{}{}{}{}{}{}", previous_hash, coinb1, coinb2,
                         merkle_branches.iter().map(|b| b.as_str().unwrap_or(""))
                         .collect::<Vec<_>>().join(""), version, nbits, ntime).into_bytes(),
            target: self.difficulty_to_target(self.session.difficulty),
            job_id: Some(job_id),
            extra_nonce: self.session.extra_nonce1.as_ref().map(|s| s.as_bytes().to_vec()),
            clean_jobs,
            timestamp: chrono::Utc::now(),
        };

        Ok(Some(work))
    }

    /// Handle difficulty change notification
    async fn handle_difficulty_change(&mut self, message: &StratumMessage) -> PoolResult<Option<f64>> {
        if message.method.as_deref() != Some("mining.set_difficulty") {
            return Ok(None);
        }

        let params = message.params.as_ref()
            .and_then(|p| p.as_array())
            .ok_or_else(|| PoolError::protocol("Invalid set_difficulty parameters"))?;

        if params.is_empty() {
            return Err(PoolError::protocol("Missing difficulty parameter"));
        }

        let difficulty = params[0].as_f64()
            .ok_or_else(|| PoolError::protocol("Invalid difficulty value"))?;

        self.session.difficulty = difficulty;

        tracing::info!("Difficulty changed to: {}", difficulty);

        Ok(Some(difficulty))
    }

    /// Convert difficulty to target
    fn difficulty_to_target(&self, difficulty: f64) -> Vec<u8> {
        // Simplified target calculation
        // In real implementation, this would use proper difficulty-to-target conversion
        let target_value = (0xFFFF_u64 << 208) / (difficulty as u64).max(1);
        target_value.to_be_bytes().to_vec()
    }
}

#[async_trait]
impl ProtocolHandler for GenericProtocolHandler {
    async fn handle_message(&mut self, message: StratumMessage) -> PoolResult<Option<StratumMessage>> {
        tracing::debug!("Handling message: {:?}", message);

        // Handle responses to our requests
        if message.id.is_some() && message.method.is_none() {
            // This is a response
            if let Some(id) = message.id.as_ref().and_then(|v| v.as_u64()) {
                if let Some(method) = self.pending_requests.get(&id) {
                    match method.as_str() {
                        "mining.subscribe" => {
                            self.handle_subscription_response(&message).await?;
                        }
                        "mining.authorize" => {
                            self.handle_authorization_response(&message).await?;
                        }
                        "mining.submit" => {
                            self.handle_submit_response(&message).await?;
                        }
                        _ => {
                            tracing::warn!("Unknown response method: {}", method);
                        }
                    }
                    self.pending_requests.remove(&id);
                }
            }
            return Ok(None);
        }

        // Handle notifications from the pool
        if let Some(method) = &message.method {
            match method.as_str() {
                "mining.notify" => {
                    if let Some(work) = self.handle_mining_notify(&message).await? {
                        // Send new work event
                        let event = crate::PoolEvent::NewWork(work);
                        if let Err(e) = self.event_sender.send(event).await {
                            tracing::warn!("Failed to send new work event: {}", e);
                        }
                    }
                }
                "mining.set_difficulty" => {
                    if let Some(difficulty) = self.handle_difficulty_change(&message).await? {
                        // Send difficulty change event
                        let event = crate::PoolEvent::DifficultyChanged(difficulty);
                        if let Err(e) = self.event_sender.send(event).await {
                            tracing::warn!("Failed to send difficulty change event: {}", e);
                        }
                    }
                }
                _ => {
                    tracing::warn!("Unhandled notification method: {}", method);
                }
            }
        }

        Ok(None)
    }

    fn create_subscribe_request(&self, user_agent: &str, extra_nonce1_size: usize) -> StratumMessage {
        let id = self.request_id + 1; // Will be incremented by caller
        StratumMessage {
            id: Some(json!(id)),
            method: Some("mining.subscribe".to_string()),
            params: Some(json!([user_agent, null, null, extra_nonce1_size])),
            result: None,
            error: None,
        }
    }

    fn create_authorize_request(&self, user: &str, password: &str) -> StratumMessage {
        let id = self.request_id + 1; // Will be incremented by caller
        StratumMessage {
            id: Some(json!(id)),
            method: Some("mining.authorize".to_string()),
            params: Some(json!([user, password])),
            result: None,
            error: None,
        }
    }

    fn create_submit_request(&self, share: &crate::MiningShare) -> StratumMessage {
        let id = self.request_id + 1; // Will be incremented by caller
        StratumMessage {
            id: Some(json!(id)),
            method: Some("mining.submit".to_string()),
            params: Some(json!([
                share.worker,
                share.job_id,
                hex::encode(&share.extra_nonce2),
                share.timestamp,
                format!("{:08x}", share.nonce)
            ])),
            result: None,
            error: None,
        }
    }

    fn parse_mining_work(&self, message: &StratumMessage) -> PoolResult<Option<crate::MiningWork>> {
        // This method is used for parsing work from responses
        // The actual work parsing is handled in handle_mining_notify
        Ok(None)
    }

    fn parse_difficulty_change(&self, message: &StratumMessage) -> PoolResult<Option<f64>> {
        // This method is used for parsing difficulty from responses
        // The actual difficulty parsing is handled in handle_difficulty_change
        Ok(None)
    }

    fn version(&self) -> &str {
        &self.version
    }
}

impl StratumMessage {
    /// Create a new request message
    pub fn new_request(id: u64, method: String, params: Value) -> Self {
        Self {
            id: Some(json!(id)),
            method: Some(method),
            params: Some(params),
            result: None,
            error: None,
        }
    }

    /// Create a new response message
    pub fn new_response(id: Option<Value>, result: Value) -> Self {
        Self {
            id,
            method: None,
            params: None,
            result: Some(result),
            error: None,
        }
    }

    /// Create a new error response message
    pub fn new_error(id: Option<Value>, code: i32, message: String) -> Self {
        Self {
            id,
            method: None,
            params: None,
            result: None,
            error: Some(StratumError {
                code,
                message,
                data: None,
            }),
        }
    }

    /// Serialize to JSON string
    pub fn to_json(&self) -> PoolResult<String> {
        serde_json::to_string(self).map_err(|e| PoolError::Serialization(e))
    }

    /// Deserialize from JSON string
    pub fn from_json(json: &str) -> PoolResult<Self> {
        serde_json::from_str(json).map_err(|e| PoolError::Serialization(e))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::sync::mpsc;

    #[test]
    fn test_stratum_message_creation() {
        let msg = StratumMessage::new_request(1, "mining.subscribe".to_string(), json!(["test"]));
        assert_eq!(msg.id, Some(json!(1)));
        assert_eq!(msg.method, Some("mining.subscribe".to_string()));
    }

    #[test]
    fn test_stratum_message_serialization() {
        let msg = StratumMessage::new_request(1, "test.method".to_string(), json!(["param1"]));
        let json_str = msg.to_json().unwrap();
        let parsed = StratumMessage::from_json(&json_str).unwrap();

        assert_eq!(msg.id, parsed.id);
        assert_eq!(msg.method, parsed.method);
    }

    #[tokio::test]
    async fn test_protocol_handler_creation() {
        let (sender, _receiver) = mpsc::channel(100);
        let handler = GenericProtocolHandler::new("1.0".to_string(), sender);
        assert_eq!(handler.version(), "1.0");
    }
}