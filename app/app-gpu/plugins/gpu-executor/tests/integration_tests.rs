//! Integration tests for GPU Executor Plugin

use opus_gpu_executor::{GpuExecutor, GpuExecutorConfig};
use opus_gpu_core::{Plugin, PluginTask};
use uuid::Uuid;

#[tokio::test]
#[ignore] // Requires GPU hardware
async fn test_gpu_executor_lifecycle() {
    let config = GpuExecutorConfig::default();
    let mut executor = GpuExecutor::default();
    
    // Initialize
    executor.initialize().await.unwrap();
    
    // Get metadata
    let metadata = executor.metadata();
    assert_eq!(metadata.name, "gpu-executor");
    assert!(metadata.capabilities.contains(&"cuda".to_string()));
    
    // Health check
    let health = executor.health_check();
    assert!(health.healthy);
    
    // Shutdown
    executor.shutdown().await.unwrap();
}

#[tokio::test] 
#[ignore] // Requires GPU hardware
async fn test_task_execution() {
    let mut executor = GpuExecutor::default();
    executor.initialize().await.unwrap();
    
    // Create test task
    let task = PluginTask {
        id: Uuid::new_v4(),
        type_: "compute".to_string(),
        payload: vec![1, 2, 3, 4, 5],
        priority: 100,
    };
    
    // Execute task
    let output = executor.execute(task.clone()).await.unwrap();
    
    assert_eq!(output.task_id, task.id);
    assert!(matches!(output.status, opus_gpu_core::plugin::TaskStatus::Success));
    assert!(!output.result.is_empty());
    
    executor.shutdown().await.unwrap();
}

#[tokio::test]
#[ignore] // Requires GPU hardware
async fn test_benchmark_task() {
    use opus_gpu_executor::{BenchmarkParams, BenchmarkResult};
    
    let mut executor = GpuExecutor::default();
    executor.initialize().await.unwrap();
    
    // Create benchmark task
    let params = BenchmarkParams {
        data_size: 1024 * 1024, // 1MB
        iterations: 100,
    };
    
    let task = PluginTask {
        id: Uuid::new_v4(),
        type_: "benchmark".to_string(),
        payload: bincode::serialize(&params).unwrap(),
        priority: 200,
    };
    
    // Execute benchmark
    let output = executor.execute(task).await.unwrap();
    
    // Parse results
    let result: BenchmarkResult = bincode::deserialize(&output.result).unwrap();
    
    assert!(result.throughput_gbps > 0.0);
    assert_eq!(result.iterations, 100);
    
    println!("Benchmark results:");
    println!("  Average time: {:.2} μs", result.average_time_us);
    println!("  Throughput: {:.2} GB/s", result.throughput_gbps);
    
    executor.shutdown().await.unwrap();
}
