//! Integration test for NVML metrics collection
//!
//! Tests graceful fallback behavior when GPU không available.

use opus_gpu_miner::modules::metrics::MetricsCollector;
use opus_gpu_miner::messaging::{MessageBus, GpuMetrics, Message};

#[test]
fn test_metrics_collector_initialization() {
    // Should initialize successfully even without GPU
    let collector = MetricsCollector::new();
    assert!(
        collector.is_ok(),
        "Metrics collector should initialize successfully"
    );
}

#[test]
fn test_metrics_export_format() {
    let collector = MetricsCollector::new().unwrap();
    let exported = collector.export();

    assert!(exported.is_ok(), "Metrics export should succeed");

    let text = exported.unwrap();

    // Verify Prometheus format
    assert!(text.contains("opus_miner_"), "Should contain opus_miner metrics");
    assert!(text.contains("TYPE"), "Should contain TYPE declarations");
    assert!(text.contains("HELP"), "Should contain HELP descriptions");
}

#[test]
fn test_gpu_metrics_struct() {
    // Test that GpuMetrics struct has all required fields
    let metrics = GpuMetrics {
        gpu_id: 0,
        hashrate: 125.5,
        temperature: 65.0,
        power_usage: 150.0,
        utilization: 85.0,
        memory_used_mb: 4096,
        timestamp: 1234567890,
    };

    assert_eq!(metrics.gpu_id, 0);
    assert_eq!(metrics.hashrate, 125.5);
    assert_eq!(metrics.temperature, 65.0);
    assert_eq!(metrics.power_usage, 150.0);
    assert_eq!(metrics.utilization, 85.0);
    assert_eq!(metrics.memory_used_mb, 4096);
    assert_eq!(metrics.timestamp, 1234567890);
}

#[test]
fn test_message_bus_metrics_channel() {
    // Test that message bus can handle metrics messages
    let (bus, handles) = MessageBus::new(1, 100);

    let test_metrics = GpuMetrics {
        gpu_id: 0,
        hashrate: 100.0,
        temperature: 70.0,
        power_usage: 200.0,
        utilization: 90.0,
        memory_used_mb: 5120,
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs(),
    };

    // Send metrics
    let result = bus.send_metrics(test_metrics);
    assert!(result.is_ok(), "Should send metrics successfully");

    // Receive metrics
    let received = handles.metrics_rx.recv_timeout(std::time::Duration::from_secs(1));
    assert!(received.is_ok(), "Should receive metrics message");

    if let Ok(Message::MetricsUpdate(metrics)) = received {
        assert_eq!(metrics.gpu_id, 0);
        assert_eq!(metrics.hashrate, 100.0);
        assert_eq!(metrics.utilization, 90.0);
        assert_eq!(metrics.memory_used_mb, 5120);
    } else {
        panic!("Received wrong message type");
    }
}

#[tokio::test]
async fn test_metrics_collection_graceful_failure() {
    // Test that metrics collection doesn't panic when NVML unavailable
    use opus_gpu_miner::modules::metrics::MetricsConfig;
    use opus_gpu_miner::messaging::MessageBus;
    use tokio_util::sync::CancellationToken;

    let config = MetricsConfig {
        interval_secs: 1,
        enable_gpu_metrics: true,
        enable_system_metrics: false,
    };

    let (_, handles) = MessageBus::new(1, 100);
    let cancel_token = CancellationToken::new();

    // Cancel immediately to test initialization only
    cancel_token.cancel();

    let result = opus_gpu_miner::modules::metrics::start(
        config,
        handles,
        cancel_token,
    ).await;

    // Should complete gracefully even without GPU
    assert!(
        result.is_ok(),
        "Metrics collector should handle missing GPU gracefully"
    );
}
