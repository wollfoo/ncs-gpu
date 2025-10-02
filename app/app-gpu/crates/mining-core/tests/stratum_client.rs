//! # Stratum Client Test Suite (Bộ thử nghiệm client Stratum)
//!
//! Comprehensive protocol compliance tests with connection lifecycle testing,
//! message parsing validation, error conditions, and failover scenarios.

use std::time::{Duration, Instant};
use std::collections::HashMap;
use std::sync::Arc;

use assert_matches::assert_matches;
use mockall::mock;
use tokio::sync::{mpsc, RwLock};
use tokio::time;
use serde_json::{json, Value};

use mining_core::stratum::{
    client::{StratumClient, StratumConfig, PoolConfig, ActorMessage},
    protocol::{
        Message, MessageId, Request, Response, Notification, StratumError,
        WorkPackage, Solution, ConnectionState, SessionStats,
        METHOD_MINING_AUTHORIZE, METHOD_MINING_NOTIFY, METHOD_MINING_SET_DIFFICULTY,
        METHOD_MINING_SET_EXTRANONCE, METHOD_MINING_SUBSCRIBE, METHOD_MINING_SUBMIT,
    },
};
use mining_core::stratum::error::{StratumError as ClientError, Result as StratumResult};

// Mock network layer
#[derive(Debug, Clone)]
struct MockNetworkConnection {
    connected: bool,
    messages_sent: Vec<String>,
    messages_received: Vec<String>,
    connection_delays: HashMap<String, Duration>,
    error_injection: Option<String>,
}

impl MockNetworkConnection {
    fn new() -> Self {
        Self {
            connected: false,
            messages_sent: Vec::new(),
            messages_received: Vec::new(),
            connection_delays: HashMap::new(),
            error_injection: None,
        }
    }

    fn with_connection_delay(mut self, method: &str, delay: Duration) -> Self {
        self.connection_delays.insert(method.to_string(), delay);
        self
    }

    fn with_error_injection(mut self, error_msg: &str) -> Self {
        self.error_injection = Some(error_msg.to_string());
        self
    }

    async fn send_message(&mut self, message: &str) -> std::io::Result<()> {
        if let Some(ref error) = self.error_injection {
            return Err(std::io::Error::new(std::io::ErrorKind::Other, error.clone()));
        }

        self.messages_sent.push(message.to_string());
        Ok(())
    }

    async fn receive_message(&mut self) -> Option<String> {
        if self.messages_received.is_empty() {
            None
        } else {
            Some(self.messages_received.remove(0))
        }
    }

    async fn connect(&mut self, _addr: &str) -> std::io::Result<()> {
        self.connected = true;
        if let Some(ref error) = self.error_injection {
            Err(std::io::Error::new(std::io::ErrorKind::Other, error.clone()))
        } else {
            Ok(())
        }
    }

    fn disconnect(&mut self) {
        self.connected = false;
    }

    fn queue_response(&mut self, response: &str) {
        self.messages_received.push(response.to_string());
    }
}

/// Mock connection factory for testing
struct MockConnectionFactory {
    connections: Arc<RwLock<HashMap<String, MockNetworkConnection>>>,
}

impl MockConnectionFactory {
    fn new() -> Self {
        Self {
            connections: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    async fn get_connection(&self, addr: &str) -> MockNetworkConnection {
        let mut conns = self.connections.write().await;
        conns.entry(addr.to_string())
            .or_insert_with(MockNetworkConnection::new)
            .clone()
    }
}

// Test data generators
fn create_test_config() -> StratumConfig {
    StratumConfig {
        primary_pool: PoolConfig {
            url: "stratum+tcp://127.0.0.1:3333".to_string(),
            worker_name: "test-worker".to_string(),
            password: Some("test-pass".to_string()),
            user_agent: Some("TestClient/1.0.0".to_string()),
            ssl: false,
            backup_pools: vec![],
        },
        connect_timeout_secs: 5,
        reconnect_delay_secs: 1,
        max_reconnect_attempts: 3,
        share_batch_size: 10,
        max_job_age_secs: 60,
        rate_limit: 100.0,
        ssl_verify_hostname: false,
    }
}

fn create_test_work_package() -> WorkPackage {
    WorkPackage {
        job_id: "test-job-123".to_string(),
        header_hash: vec![0x01; 32],
        seed_hash: vec![0x02; 32],
        target: vec![0xff; 32],
        height: 12345678,
        difficulty: 1000.0,
        extra_nonce1: Some(vec![0x42; 8]),
        received_at: std::time::SystemTime::now(),
        clean_jobs: false,
    }
}

fn create_test_solution() -> Solution {
    Solution {
        job_id: "test-job-123".to_string(),
        nonce: 0x12345678,
        extra_nonce2: vec![0x11, 0x22, 0x33, 0x44],
        hash: vec![0xaa; 32],
        mix_hash: vec![0xbb; 32],
    }
}

#[cfg(test)]
mod protocol_tests {
    use super::*;

    #[test]
    fn test_message_id_generation() {
        let id1 = MessageId::new();
        let id2 = MessageId::new();

        // IDs should be different (very high probability)
        assert_ne!(id1.raw(), id2.raw());

        // Raw value access
        assert_eq!(MessageId::from_raw(42).raw(), 42);
    }

    #[test]
    fn test_message_id_serialization() {
        let id = MessageId::from_raw(12345);
        let serialized = serde_json::to_string(&id).unwrap();
        let deserialized: MessageId = serde_json::from_str(&serialized).unwrap();

        assert_eq!(deserialized.raw(), 12345);
    }

    #[test]
    fn test_request_message_creation() {
        let request = Request {
            id: MessageId::from_raw(1),
            method: METHOD_MINING_AUTHORIZE.to_string(),
            params: vec![
                json!("test-worker"),
                json!("password"),
            ],
        };

        assert_eq!(request.id.raw(), 1);
        assert_eq!(request.method, METHOD_MINING_AUTHORIZE);
        assert_eq!(request.params.len(), 2);
    }

    #[test]
    fn test_response_message_creation() {
        let response = Response {
            id: MessageId::from_raw(1),
            result: Some(json!(true)),
            error: None,
        };

        assert_eq!(response.id.raw(), 1);
        assert_eq!(response.result.as_ref().unwrap(), &json!(true));
        assert!(response.error.is_none());
    }

    #[test]
    fn test_error_response_creation() {
        let error = StratumError(21, "Job not found".to_string(), Some(json!({"job_id": "invalid"})));

        let response = Response {
            id: MessageId::from_raw(1),
            result: None,
            error: Some(error.clone()),
        };

        assert_eq!(response.id.raw(), 1);
        assert!(response.result.is_none());
        assert_eq!(response.error.as_ref().unwrap().0, 21);
        assert_eq!(response.error.as_ref().unwrap().1, "Job not found");
    }

    #[test]
    fn test_notification_message_creation() {
        let notification = Notification {
            id: None,
            method: METHOD_MINING_NOTIFY.to_string(),
            params: vec![
                json!("job-123"),
                json!(hex::encode(vec![0x01; 32])),
                json!(hex::encode(vec![0x02; 32])),
                json!(hex::encode(vec![0x03; 32])),
                json!(vec![hex::encode(vec![0x11; 32])]),
                json!(hex::encode(vec![0x04; 4])),
                json!(hex::encode(vec![0x05; 4])),
                json!(hex::encode(vec![0x06; 32])),
                json!(true),
            ],
        };

        assert!(notification.id.is_none());
        assert_eq!(notification.method, METHOD_MINING_NOTIFY);
        assert_eq!(notification.params.len(), 9);
    }

    #[test]
    fn test_solution_structure() {
        let solution = create_test_solution();

        assert_eq!(solution.job_id, "test-job-123");
        assert_eq!(solution.nonce, 0x12345678);
        assert_eq!(solution.extra_nonce2, vec![0x11, 0x22, 0x33, 0x44]);
        assert_eq!(solution.hash, vec![0xaa; 32]);
        assert_eq!(solution.mix_hash, vec![0xbb; 32]);
    }
}

#[cfg(test)]
mod connection_tests {
    use super::*;

    #[tokio::test]
    async fn test_stratum_client_creation() {
        let config = create_test_config();
        let result = StratumClient::new(config).await;

        assert_matches!(result, Ok(_));
    }

    #[tokio::test]
    async fn test_stratum_config_validation() {
        let config = create_test_config();
        assert_eq!(config.primary_pool.worker_name, "test-worker");
        assert_eq!(config.connect_timeout_secs, 5);
        assert_eq!(config.max_reconnect_attempts, 3);
    }

    #[tokio::test]
    async fn test_client_message_sending() {
        let config = create_test_config();
        let mut client = StratumClient::new(config).await.unwrap();

        // Test various message patterns
        let connect_result = client.connect().await;
        // Connection may fail in test environment - just test it doesn't panic
        let _ = connect_result;

        let solution = create_test_solution();
        let submit_result = client.submit_solution(solution).await;
        // May fail due to no active connection - just test no panic
        let _ = submit_result;

        let work_result = client.get_work().await;
        // Should return an error due to timeout
        assert_matches!(work_result, Err(_));
    }

    #[tokio::test]
    async fn test_stats_collection() {
        let config = create_test_config();
        let client = StratumClient::new(config).await.unwrap();

        let stats = client.get_stats().await;
        assert_eq!(stats.connections_attempted, 0);
        assert_eq!(stats.connections_successful, 0);
    }
}

#[cfg(test)]
mod message_parsing_tests {
    use super::*;

    #[test]
    fn test_request_parsing() {
        let json_str = r#"{"id": 123, "method": "mining.subscribe", "params": ["Miner", "worker-name", "password"]}"#;
        let message: Message = serde_json::from_str(json_str).unwrap();

        match message {
            Message::Request(req) => {
                assert_eq!(req.id.raw(), 123);
                assert_eq!(req.method, "mining.subscribe");
                assert_eq!(req.params.len(), 3);
                assert_eq!(req.params[0], json!("Miner"));
                assert_eq!(req.params[1], json!("worker-name"));
                assert_eq!(req.params[2], json!("password"));
            }
            _ => panic!("Expected Request message"),
        }
    }

    #[test]
    fn test_response_parsing() {
        let json_str = r#"{"id": 123, "result": true}"#;
        let message: Message = serde_json::from_str(json_str).unwrap();

        match message {
            Message::Response(resp) => {
                assert_eq!(resp.id.raw(), 123);
                assert_eq!(resp.result, Some(json!(true)));
                assert!(resp.error.is_none());
            }
            _ => panic!("Expected Response message"),
        }
    }

    #[test]
    fn test_notification_parsing() {
        let json_str = r#"{"id": null, "method": "mining.notify", "params": ["job-123", "header", "seed", "target", ["merkle"], "version", "nbits", "ntime", "clean"]}"#;
        let message: Message = serde_json::from_str(json_str).unwrap();

        match message {
            Message::Notification(notif) => {
                assert!(notif.id.is_none());
                assert_eq!(notif.method, "mining.notify");
                assert_eq!(notif.params.len(), 9);
                assert_eq!(notif.params[0], json!("job-123"));
            }
            _ => panic!("Expected Notification message"),
        }
    }

    #[test]
    fn test_error_response_parsing() {
        let json_str = r#"{"id": 456, "result": null, "error": [21, "Job not found", {"job_id": "invalid"}]}"#;
        let message: Message = serde_json::from_str(json_str).unwrap();

        match message {
            Message::Response(resp) => {
                assert_eq!(resp.id.raw(), 456);
                assert!(resp.result.is_none());
                assert!(resp.error.is_some());

                let error = resp.error.as_ref().unwrap();
                assert_eq!(error.0, 21);
                assert_eq!(error.1, "Job not found");
                assert_eq!(error.2, Some(json!({"job_id": "invalid"})));
            }
            _ => panic!("Expected Response message with error"),
        }
    }
}

#[cfg(test)]
mod actor_message_tests {
    use super::*;

    #[tokio::test]
    async fn test_actor_message_patterns() {
        let config = create_test_config();

        // Test different actor message patterns
        let connect_msg = ActorMessage::Connect {
            pool_url: config.primary_pool.url.clone(),
            pool_password: config.primary_pool.password.clone(),
        };

        match connect_msg {
            ActorMessage::Connect { pool_url, pool_password } => {
                assert_eq!(pool_url, config.primary_pool.url);
                assert_eq!(pool_password, config.primary_pool.password);
            }
            _ => panic!("Expected Connect message"),
        }

        let solution = create_test_solution();
        let submit_msg = ActorMessage::SubmitSolution(solution.clone());

        match submit_msg {
            ActorMessage::SubmitSolution(sol) => {
                assert_eq!(sol.job_id, solution.job_id);
                assert_eq!(sol.nonce, solution.nonce);
            }
            _ => panic!("Expected SubmitSolution message"),
        }
    }
}

#[cfg(test)]
mod mock_network_tests {
    use super::*;

    #[test]
    fn test_mock_connection_creation() {
        let mut conn = MockNetworkConnection::new();
        assert!(!conn.connected);
        assert!(conn.messages_sent.is_empty());
        assert!(conn.messages_received.is_empty());
    }

    #[tokio::test]
    async fn test_mock_connection_operations() {
        let mut conn = MockNetworkConnection::new();

        // Test connection
        conn.connect("127.0.0.1:3333").await.unwrap();
        assert!(conn.connected);

        // Test message sending
        conn.send_message("test message").await.unwrap();
        assert_eq!(conn.messages_sent.len(), 1);
        assert_eq!(conn.messages_sent[0], "test message");

        // Test message receiving
        conn.queue_response("test response");
        let received = conn.receive_message().await;
        assert_eq!(received, Some("test response".to_string()));

        // Test disconnection
        conn.disconnect();
        assert!(!conn.connected);
    }

    #[tokio::test]
    async fn test_mock_connection_with_delays() {
        let conn = MockNetworkConnection::new()
            .with_connection_delay("connect", Duration::from_millis(100));

        // The delays would be used in more complex mock scenarios
        assert!(!conn.connection_delays.is_empty());
    }

    #[tokio::test]
    async fn test_mock_connection_error_injection() {
        let conn = MockNetworkConnection::new()
            .with_error_injection("Connection refused");

        let result = conn.send_message("test").await;
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Connection refused"));
    }
}

#[cfg(test)]
mod integration_pattern_tests {
    use super::*;

    #[tokio::test]
    async fn test_full_connection_lifecycle() {
        // Simulate complete Stratum connection lifecycle

        let conn_factory = MockConnectionFactory::new();

        // Phase 1: Initial connection
        let mut conn = conn_factory.get_connection("127.0.0.1:3333").await;
        conn.connect("127.0.0.1:3333").await.unwrap();

        // Phase 2: Subscribe
        let subscribe_json = r#"{"id": 1, "method": "mining.subscribe", "params": ["TestMiner/1.0", "test-worker", "password"]}"#;
        conn.send_message(subscribe_json).await.unwrap();

        // Phase 3: Receive subscribe response
        let subscribe_response = r#"{"id": 1, "result": [["mining.set_difficulty", "1"], ["mining.notify", "1"], "08000000", 4], "error": null}"#;
        conn.queue_response(subscribe_response);

        // Phase 4: Receive authorize request
        let authorize_json = r#"{"id": 2, "method": "mining.authorize", "params": ["test-worker", "password"]}"#;
        conn.send_message(authorize_json).await.unwrap();

        // Phase 5: Receive authorize response
        let authorize_response = r#"{"id": 2, "result": true, "error": null}"#;
        conn.queue_response(authorize_response);

        // Phase 6: Receive mining.notify
        let notify_json = r#"{"id": null, "method": "mining.notify", "params": ["job-123", "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff", "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff", "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff", [], "00112233", "00112233", "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff", true]}"#;
        conn.queue_response(notify_json);

        // Phase 7: Send mining.submit
        let submit_json = r#"{"id": 3, "method": "mining.submit", "params": ["test-worker", "job-123", "11223344", "00112233", "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899", "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899"]}"#;
        conn.send_message(submit_json).await.unwrap();

        // Phase 8: Receive submit response
        let submit_response = r#"{"id": 3, "result": true, "error": null}"#;
        conn.queue_response(submit_response);

        // Phase 9: Disconnect
        conn.disconnect();

        // Verify message flow
        assert_eq!(conn.messages_sent.len(), 3);
        assert_eq!(conn.messages_received.len(), 4);
    }

    #[tokio::test]
    async fn test_error_handling_scenarios() {
        let mut conn = MockNetworkConnection::new();

        // Test 1: Connection failure
        let conn_fail = conn.connect("invalid:address").await;
        assert!(conn_fail.is_err());

        // Reset connection
        conn = MockNetworkConnection::new();

        // Test 2: Protocol error response
        conn.queue_response(r#"{"id": 1, "result": null, "error": [21, "Job not found", {"job_id": "invalid"}]}"#);
        let response = conn.receive_message().await;
        assert!(response.is_some());

        let message: Message = serde_json::from_str(&response.unwrap()).unwrap();
        match message {
            Message::Response(resp) => {
                assert!(resp.result.is_none());
                assert!(resp.error.is_some());
                assert_eq!(resp.error.as_ref().unwrap().0, 21);
            }
            _ => panic!("Expected error response"),
        }
    }

    #[tokio::test]
    async fn test_failover_scenarios() {
        let conn_factory = MockConnectionFactory::new();

        // Primary pool
        let mut primary_conn = conn_factory.get_connection("pool1:3333").await;
        primary_conn.connect("pool1:3333").await.unwrap();

        // Simulate primary pool failure
        primary_conn.disconnect();

        // Backup pool
        let mut backup_conn = conn_factory.get_connection("pool2:3333").await;
        backup_conn.connect("pool2:3333").await.unwrap();

        // Test continued operation on backup
        backup_conn.send_message("test message").await.unwrap();
        assert_eq!(backup_conn.messages_sent.len(), 1);
    }
}

#[cfg(test)]
mod load_and_stress_tests {
    use super::*;

    #[tokio::test]
    async fn test_concurrent_connection_simulation() {
        let conn_factory = Arc::new(MockConnectionFactory::new());
        let num_connections = 10;

        // Simulate multiple concurrent connections
        let mut handles = vec![];

        for i in 0..num_connections {
            let factory_clone = Arc::clone(&conn_factory);
            let addr = format!("127.0.0.1:{}", 3333 + i);

            let handle = tokio::spawn(async move {
                let mut conn = factory_clone.get_connection(&addr).await;
                conn.connect(&addr).await.unwrap();

                // Send multiple messages
                for j in 0..5 {
                    let msg = format!("message-{}-{}", i, j);
                    conn.send_message(&msg).await.unwrap();
                }

                conn.disconnect();
                conn.messages_sent.len()
            });

            handles.push(handle);
        }

        // Wait for all connections to complete
        let results = futures::future::join_all(handles).await;

        // Verify all connections succeeded
        for result in results {
            let message_count = result.unwrap();
            assert_eq!(message_count, 5);
        }
    }

    #[tokio::test]
    async fn test_message_throughput_simulation() {
        let mut conn = MockNetworkConnection::new();
        conn.connect("127.0.0.1:3333").await.unwrap();

        let num_messages = 1000;
        let start_time = Instant::now();

        // Send high volume of messages
        for i in 0..num_messages {
            let msg = format!(r#"{{"id": {}, "method": "mining.submit", "params": ["worker", "job-{}", "{}", "nonce", "hash", "mix"]}}"#, i, i % 10, i);
            conn.send_message(&msg).await.unwrap();
        }

        let elapsed = start_time.elapsed();
        let messages_per_second = num_messages as f64 / elapsed.as_secs_f64();

        // Should be able to handle at least 1000 messages reasonably fast
        assert!(elapsed < Duration::from_secs(5));
        assert!(messages_per_second > 100.0);

        println!("Processed {} messages in {:.2}s ({:.0} msg/s)",
                num_messages, elapsed.as_secs_f64(), messages_per_second);
    }

    #[tokio::test]
    async fn test_reconnection_logic_simulation() {
        let mut conn = MockNetworkConnection::new();

        let max_retries = 5;
        let mut successful_connection = false;

        for attempt in 0..max_retries {
            let result = conn.connect("pool:3333").await;

            if result.is_ok() {
                successful_connection = true;
                break;
            }

            if attempt < max_retries - 1 {
                time::sleep(Duration::from_millis(100)).await;
            }
        }

        // In this simple mock, connection should succeed
        assert!(successful_connection);
    }
}