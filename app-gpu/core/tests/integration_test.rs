//! Integration tests for OPUS-GPU Core

use opus_gpu_core::{Config, Runtime, IpcManager, Message};
use tempfile::tempdir;
use std::path::PathBuf;

#[tokio::test]
async fn test_runtime_lifecycle() {
    // Create test config
    let temp = tempdir().unwrap();
    let mut config = Config::default();
    config.plugin.plugin_dir = temp.path().to_owned();
    config.ipc.shared_memory_size_mb = 10;
    
    // Create runtime
    let mut runtime = Runtime::new(config).await.unwrap();
    
    // Verify runtime can be created and shutdown
    runtime.shutdown().await.unwrap();
}

#[tokio::test]
async fn test_ipc_communication() {
    use opus_gpu_core::config::IpcConfig;
    
    let config = IpcConfig {
        shared_memory_size_mb: 10,
        num_segments: 2,
        bounded_queue: true,
        queue_size: 100,
    };
    
    let ipc = IpcManager::new(config).await.unwrap();
    
    // Test sending and receiving
    let message = Message {
        source: "test_source".to_string(),
        destination: "test_dest".to_string(),
        payload: vec![1, 2, 3, 4, 5],
    };
    
    ipc.send_message(message.clone()).await.unwrap();
    
    // Should receive the message
    let received = ipc.receive_message().await.unwrap();
    assert!(received.is_some());
    
    let received = received.unwrap();
    assert_eq!(received.source, message.source);
    assert_eq!(received.payload, message.payload);
}

#[tokio::test]
async fn test_ipc_benchmark_performance() {
    use opus_gpu_core::config::IpcConfig;
    
    let config = IpcConfig {
        shared_memory_size_mb: 100,
        num_segments: 4,
        bounded_queue: false,
        queue_size: 0,
    };
    
    let ipc = IpcManager::new(config).await.unwrap();
    
    // Benchmark should achieve > 1GB/s
    let throughput = ipc.benchmark(1024, 1000).await.unwrap();
    assert!(throughput > 1000.0, "IPC throughput {} MB/s is too low", throughput);
}

#[test]
fn test_config_loading() {
    // Test default config
    let config = Config::default();
    assert!(config.validate().is_ok());
    
    // Test environment override
    std::env::set_var("OPUS_WORKERS", "8");
    let config = Config::default();
    // After applying env overrides in real load
    assert_eq!(config.runtime.workers, 4); // Still default without load()
}

#[test]
fn test_error_handling() {
    use opus_gpu_core::error::{OpusError, ErrorContext, ErrorSeverity, DefaultErrorHandler, ErrorHandler};
    
    let error = OpusError::Config("Test error".to_string());
    let context = ErrorContext::new(error, ErrorSeverity::Warning, "test");
    
    assert!(context.is_recoverable());
    assert!(!context.is_critical());
    
    let handler = DefaultErrorHandler;
    handler.log(&context);
}
