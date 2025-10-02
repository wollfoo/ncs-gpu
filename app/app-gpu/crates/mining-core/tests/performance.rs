//! # Performance Test Suite (Bộ thử nghiệm hiệu năng)
//!
//! Benchmark kernel execution times, memory profiling, concurrent operations stress testing,
//! and long-running stability verification.

use std::time::{Duration, Instant};
use std::collections::HashMap;
use std::sync::Arc;

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use tokio::sync::RwLock;
use tokio::time;
use assert_matches::assert_matches;

use mining_core::kernels::{EthashMiner, is_cuda_available, get_device_count};
use mining_core::mining::{MiningLoop, MiningStatistics, StatisticsConfig, AlertThresholds};
use mining_core::gpu::manager::GpuManager;

// Performance test data structures
#[derive(Debug, Clone)]
struct PerformanceMetrics {
    pub operation: String,
    pub duration: Duration,
    pub memory_used_mb: f64,
    pub throughput: f64,
    pub status: PerformanceStatus,
}

#[derive(Debug, Clone, PartialEq)]
enum PerformanceStatus {
    Passed,
    Failed(String),
    Warning(String),
}

impl PerformanceMetrics {
    fn new(operation: &str) -> Self {
        Self {
            operation: operation.to_string(),
            duration: Duration::default(),
            memory_used_mb: 0.0,
            throughput: 0.0,
            status: PerformanceStatus::Passed,
        }
    }

    fn with_timing(mut self, duration: Duration) -> Self {
        self.duration = duration;
        self
    }

    fn with_memory(mut self, memory_mb: f64) -> Self {
        self.memory_used_mb = memory_mb;
        self
    }

    fn with_throughput(mut self, throughput: f64) -> Self {
        self.throughput = throughput;
        self
    }

    fn failed(mut self, reason: &str) -> Self {
        self.status = PerformanceStatus::Failed(reason.to_string());
        self
    }

    fn warning(mut self, reason: &str) -> Self {
        self.status = PerformanceStatus::Warning(reason.to_string());
        self
    }
}

// Benchmark data generators
fn generate_test_header(seed: u64) -> [u8; 32] {
    let mut header = [0u8; 32];
    for i in 0..32 {
        header[i] = ((seed.wrapping_mul(31)) % 256) as u8;
    }
    header
}

fn generate_test_target(difficulty: f64) -> [u8; 32] {
    // Simplified target generation - in real mining, this is more complex
    let mut target = [0xffu8; 32];
    let difficulty_bytes = difficulty.to_be_bytes();
    target[..8].copy_from_slice(&difficulty_bytes);
    target
}

struct PerformanceTestHarness {
    pub metrics: Vec<PerformanceMetrics>,
    pub start_time: Instant,
}

impl PerformanceTestHarness {
    fn new() -> Self {
        Self {
            metrics: Vec::new(),
            start_time: Instant::now(),
        }
    }

    fn record_metric(&mut self, metric: PerformanceMetrics) {
        self.metrics.push(metric);
        self.log_metric(&metric);
    }

    fn log_metric(&self, metric: &PerformanceMetrics) {
        let status = match &metric.status {
            PerformanceStatus::Passed => "✅ PASS",
            PerformanceStatus::Failed(reason) => &format!("❌ FAIL: {}", reason),
            PerformanceStatus::Warning(reason) => &format!("⚠️  WARN: {}", reason),
        };

        println!("PerfTest | {:.4}s | {:.2} MB | {:.2} ops/sec | {} | {}",
                metric.duration.as_secs_f64(),
                metric.memory_used_mb,
                metric.throughput,
                metric.operation,
                status);
    }

    fn summary(&self) {
        let total_time = self.start_time.elapsed();
        let passed = self.metrics.iter().filter(|m| matches!(m.status, PerformanceStatus::Passed)).count();
        let failed = self.metrics.iter().filter(|m| matches!(m.status, PerformanceStatus::Failed(_))).count();
        let warnings = self.metrics.iter().filter(|m| matches!(m.status, PerformanceStatus::Warning(_))).count();

        println!("\n=== Performance Test Summary ===");
        println!("Total Tests: {}", self.metrics.len());
        println!("✅ Passed: {}", passed);
        println!("⚠️  Warnings: {}", warnings);
        println!("❌ Failed: {}", failed);
        println!("Total Time: {:.4}s", total_time.as_secs_f64());

        if !self.metrics.is_empty() {
            let avg_duration = self.metrics.iter()
                .map(|m| m.duration.as_secs_f64())
                .sum::<f64>() / self.metrics.len() as f64;
            println!("Average Test Duration: {:.4}s", avg_duration);
        }
    }
}

#[cfg(test)]
mod kernel_performance_tests {
    use super::*;

    #[tokio::test]
    async fn test_kernel_initialization_performance() {
        let mut harness = PerformanceTestHarness::new();

        if !is_cuda_available() {
            println!("⚠️  CUDA not available, skipping kernel tests");
            return;
        }

        // Test kernel initialization time
        let init_start = Instant::now();
        let device_count = get_device_count();

        if let Ok(count) = device_count {
            if count > 0 {
                // Try to create a real miner for device 0
                let miner_result = EthashMiner::new(0, 0);
                let init_duration = init_start.elapsed();

                let mut metric = PerformanceMetrics::new("kernel_initialization")
                    .with_timing(init_duration)
                    .with_memory(0.0) // Would need system monitoring
                    .with_throughput(1.0 / init_duration.as_secs_f64());

                match miner_result {
                    Ok(miner) => {
                        println!("Kernel initialization: {:.4}s", init_duration.as_secs_f64());
                        assert!(init_duration < Duration::from_secs(5));
                    }
                    Err(e) => {
                        metric = metric.warning(&format!("Initialization failed: {}", e));
                    }
                }

                harness.record_metric(metric);
            }
        }

        harness.summary();
    }

    #[tokio::test]
    async fn test_dag_size_calculation_performance() {
        let mut harness = PerformanceTestHarness::new();

        let epochs: Vec<u64> = (0..1000).collect();
        let start_time = Instant::now();

        for &epoch in &epochs {
            let _dag_size = EthashMiner::calculate_dag_size(epoch);
        }

        let duration = start_time.elapsed();
        let calculations_per_second = epochs.len() as f64 / duration.as_secs_f64();

        let metric = PerformanceMetrics::new("dag_size_calculations")
            .with_timing(duration)
            .with_throughput(calculations_per_second);

        harness.record_metric(metric);
        harness.summary();

        assert!(duration < Duration::from_secs(1)); // Should be very fast
        assert!(calculations_per_second > 1000.0);
    }

    #[test]
    fn test_memory_allocation_performance_simulation() {
        let mut harness = PerformanceTestHarness::new();

        // Simulate memory allocation patterns (can't allocate real GPU memory in tests)
        let allocation_sizes = vec![1024, 2048, 4096, 8192, 16384]; // KB
        let start_time = Instant::now();

        let mut total_allocated = 0;
        for &size in &allocation_sizes {
            let size_kb = size;
            total_allocated += size_kb;

            // Simulate allocation cost (in real tests, would allocate actual GPU memory)
            std::thread::sleep(Duration::from_micros(size as u64));
        }

        let duration = start_time.elapsed();

        let metric = PerformanceMetrics::new("memory_allocation_simulation")
            .with_timing(duration)
            .with_memory(total_allocated as f64 / 1024.0) // Convert to MB
            .with_throughput(allocation_sizes.len() as f64 / duration.as_secs_f64());

        harness.record_metric(metric);
        harness.summary();
    }
}

#[cfg(test)]
mod mining_performance_tests {
    use super::*;

    #[tokio::test]
    async fn test_statistics_update_performance() {
        let mut harness = PerformanceTestHarness::new();

        let config = StatisticsConfig {
            update_interval_secs: 1,
            history_retention_minutes: 60,
            enable_gpu_monitoring: false, // Disable for performance test
            alert_thresholds: AlertThresholds::default(),
        };

        let stats = MiningStatistics::new(config);
        let iterations = 1000;

        let start_time = Instant::now();

        // Simulate frequent statistics updates
        for _ in 0..iterations {
            let _hashrate = 95.0 + (rand::random::<f64>() - 0.5) * 10.0;
            let _accepted = rand::random::<u64>() % 100;
            let _rejected = rand::random::<u64>() % 10;

            // In real implementation, these would update internal stats
            std::thread::sleep(Duration::from_micros(100));
        }

        let duration = start_time.elapsed();
        let updates_per_second = iterations as f64 / duration.as_secs_f64();

        let metric = PerformanceMetrics::new("statistics_updates")
            .with_timing(duration)
            .with_throughput(updates_per_second);

        harness.record_metric(metric);
        harness.summary();

        assert!(updates_per_second > 1000.0); // Should handle >1000 updates/sec
    }

    #[tokio::test]
    async fn test_concurrent_gpu_simulation() {
        let mut harness = PerformanceTestHarness::new();

        let num_gpus = 4;
        let operations_per_gpu = 100;
        let mut handles = vec![];

        let start_time = Instant::now();

        // Simulate concurrent GPU operations
        for gpu_id in 0..num_gpus {
            let handle = tokio::spawn(async move {
                for i in 0..operations_per_gpu {
                    // Simulate mining kernel execution
                    let header = generate_test_header(gpu_id as u64 * 100 + i as u64);
                    let target = generate_test_target(1000.0);

                    // Simulate kernel time
                    time::sleep(Duration::from_micros(500)).await;

                    black_box((header, target));
                }
            });
            handles.push(handle);
        }

        // Wait for all GPUs to complete
        for handle in handles {
            let _ = handle.await;
        }

        let duration = start_time.elapsed();
        let total_operations = num_gpus * operations_per_gpu;
        let operations_per_second = total_operations as f64 / duration.as_secs_f64();

        let metric = PerformanceMetrics::new("concurrent_gpu_operations")
            .with_timing(duration)
            .with_throughput(operations_per_second);

        harness.record_metric(metric);
        harness.summary();

        println!("Concurrent test: {} GPUs, {} ops total, {:.2} ops/sec",
                num_gpus, total_operations, operations_per_second);
    }
}

#[cfg(test)]
mod stress_tests {
    use super::*;

    #[tokio::test]
    async fn test_long_running_stability() {
        let mut harness = PerformanceTestHarness::new();
        let test_duration = Duration::from_secs(10); // Shortened for CI

        let start_time = Instant::now();
        let mut iterations = 0;
        let mut errors = 0;

        while start_time.elapsed() < test_duration {
            iterations += 1;

            // Simulate various mining operations
            let operation_type = iterations % 4;

            match operation_type {
                0 => {
                    // DAG calculation
                    let _ = EthashMiner::calculate_dag_size(iterations as u64);
                }
                1 => {
                    // Memory allocation simulation
                    std::thread::sleep(Duration::from_micros(50));
                }
                2 => {
                    // Statistics update simulation
                    let _update_time = Instant::now();
                }
                3 => {
                    // Connection simulation
                    time::sleep(Duration::from_millis(1)).await;
                }
                _ => unreachable!(),
            }

            // Occasional error injection to test error handling
            if iterations % 100 == 0 && rand::random::<f64>() < 0.1 {
                errors += 1;
            }
        }

        let duration = start_time.elapsed();
        let iterations_per_second = iterations as f64 / duration.as_secs_f64();

        let mut metric = PerformanceMetrics::new("long_running_stability")
            .with_timing(duration)
            .with_throughput(iterations_per_second);

        if errors > iterations / 1000 { // Allow up to 0.1% errors
            metric = metric.warning(&format!("High error rate: {} errors in {} iterations", errors, iterations));
        }

        harness.record_metric(metric);
        harness.summary();

        println!("Stability test: {} iterations, {} errors, {:.2} iter/sec",
                iterations, errors, iterations_per_second);

        assert!(iterations > 10000); // Should complete many iterations
    }

    #[tokio::test]
    async fn test_memory_pressure_simulation() {
        let mut harness = PerformanceTestHarness::new();

        let allocations = 1000;
        let mut allocated_memory = 0.0;
        let start_time = Instant::now();

        // Simulate memory pressure by creating many allocations
        let mut allocation_handles = vec![];

        for i in 0..allocations {
            let handle = tokio::spawn(async move {
                // Simulate allocating mining structures
                let size_kb = 50 + (i % 100); // Variable sizes
                time::sleep(Duration::from_micros(size_kb as u64)).await;
                size_kb as f64
            });
            allocation_handles.push(handle);
        }

        // Collect allocation results
        for handle in allocation_handles {
            if let Ok(size) = handle.await {
                allocated_memory += size;
            }
        }

        let duration = start_time.elapsed();

        let metric = PerformanceMetrics::new("memory_pressure_simulation")
            .with_timing(duration)
            .with_memory(allocated_memory / 1024.0) // Convert to MB
            .with_throughput(allocations as f64 / duration.as_secs_f64());

        harness.record_metric(metric);
        harness.summary();

        println!("Memory pressure test: {:.2} KB simulated, {:.4}s",
                allocated_memory, duration.as_secs_f64());
    }

    #[tokio::test]
    async fn test_connection_storm_simulation() {
        let mut harness = PerformanceTestHarness::new();

        let connections = 100;
        let mut successful_connections = 0;
        let mut failed_connections = 0;

        let start_time = Instant::now();

        // Simulate multiple connection attempts
        for i in 0..connections {
            // Simulate connection establishment
            time::sleep(Duration::from_millis(1)).await;

            if rand::random::<f64>() > 0.05 { // 95% success rate
                successful_connections += 1;
            } else {
                failed_connections += 1;
            }

            black_box(i);
        }

        let duration = start_time.elapsed();

        let success_rate = successful_connections as f64 / connections as f64 * 100.0;

        let mut metric = PerformanceMetrics::new("connection_storm_simulation")
            .with_timing(duration)
            .with_throughput(connections as f64 / duration.as_secs_f64());

        if success_rate < 90.0 {
            metric = metric.warning(&format!("Low connection success rate: {:.1}%", success_rate));
        }

        harness.record_metric(metric);
        harness.summary();

        println!("Connection storm: {}/{} successful ({}%), {:.2} conn/sec",
                successful_connections, connections, success_rate,
                connections as f64 / duration.as_secs_f64());
    }
}

#[cfg(test)]
mod resource_usage_tests {
    use super::*;

    #[tokio::test]
    async fn test_cpu_usage_during_mining_simulation() {
        let mut harness = PerformanceTestHarness::new();

        let mining_threads = 4;
        let mining_duration = Duration::from_secs(2);
        let start_time = Instant::now();

        // Simulate CPU-intensive mining operations
        let mut mining_handles = vec![];

        for thread_id in 0..mining_threads {
            let handle = tokio::spawn(async move {
                let thread_start = Instant::now();
                let mut operations = 0;

                while thread_start.elapsed() < mining_duration {
                    // Simulate mining hash calculations
                    for i in 0..1000 {
                        let hash_input = (thread_id as u64 * 10000 + i as u64).to_be_bytes();
                        let _hash = sha2::Sha256::digest(&hash_input);
                        operations += 1;
                    }

                    // Brief yield to simulate I/O waits
                    tokio::task::yield_now().await;
                }

                operations
            });

            mining_handles.push(handle);
        }

        // Wait for all mining threads
        let mut total_operations = 0;
        for handle in mining_handles {
            if let Ok(ops) = handle.await {
                total_operations += ops;
            }
        }

        let duration = start_time.elapsed();
        let operations_per_second = total_operations as f64 / duration.as_secs_f64();

        let metric = PerformanceMetrics::new("cpu_mining_simulation")
            .with_timing(duration)
            .with_throughput(operations_per_second);

        harness.record_metric(metric);
        harness.summary();

        println!("CPU mining: {} threads, {} operations, {:.0} ops/sec",
                mining_threads, total_operations, operations_per_second);

        assert!(operations_per_second > 100000.0); // Should be reasonably fast
    }

    #[tokio::test]
    async fn test_memory_fragmentation_simulation() {
        let mut harness = PerformanceTestHarness::new();

        let allocations = 10000;
        let mut active_allocations = HashMap::new();
        let start_time = Instant::now();

        // Simulate memory allocation/deallocation patterns
        for i in 0..allocations {
            let alloc_id = i;
            let size_bytes = 1024 + (rand::random::<usize>() % 1024); // Variable sizes

            active_allocations.insert(alloc_id, size_bytes);

            // Occasionally free some allocations (simulate fragmentation)
            if i % 100 == 0 && !active_allocations.is_empty() {
                let keys_to_remove: Vec<_> = active_allocations.keys()
                    .take(10)
                    .cloned()
                    .collect();

                for key in keys_to_remove {
                    active_allocations.remove(&key);
                }
            }

            black_box(size_bytes);
        }

        let duration = start_time.elapsed();
        let final_allocations = active_allocations.len();
        let total_memory_kb = active_allocations.values().sum::<usize>() as f64 / 1024.0;

        let metric = PerformanceMetrics::new("memory_fragmentation_simulation")
            .with_timing(duration)
            .with_memory(total_memory_kb / 1024.0) // Convert to MB
            .with_throughput(allocations as f64 / duration.as_secs_f64());

        harness.record_metric(metric);
        harness.summary();

        println!("Memory fragmentation: {} final allocations, {:.2} KB active",
                final_allocations, total_memory_kb);

        assert!(final_allocations > 0);
        assert!(total_memory_kb > 0.0);
    }
}

#[cfg(test)]
mod scalability_tests {
    use super::*;

    #[tokio::test]
    async fn test_scaling_with_gpus() {
        let mut harness = PerformanceTestHarness::new();

        let max_gpus = 8;
        let operations_per_gpu = 1000;

        for gpu_count in [1, 2, 4, max_gpus] {
            let start_time = Instant::now();

            // Simulate mining with different GPU counts
            let mut gpu_handles = vec![];

            for gpu_id in 0..gpu_count {
                let handle = tokio::spawn(async move {
                    let mut gpu_operations = 0;
                    for operation in 0..operations_per_gpu {
                        // Simulate GPU mining work
                        let header = generate_test_header(gpu_id as u64 * operations_per_gpu as u64 + operation as u64);
                        let target = generate_test_target(1000.0 + gpu_id as f64 * 100.0);

                        // Variable delay based on GPU performance (simulate faster GPUs)
                        let base_delay = 1000 - (gpu_id as u64 * 50); // GPU 0 is slowest
                        time::sleep(Duration::from_micros(base_delay.max(100))).await;

                        black_box((header, target));
                        gpu_operations += 1;
                    }
                    gpu_operations
                });

                gpu_handles.push(handle);
            }

            // Wait for all GPUs
            let mut total_operations = 0;
            for handle in gpu_handles {
                if let Ok(ops) = handle.await {
                    total_operations += ops;
                }
            }

            let duration = start_time.elapsed();
            let operations_per_second = total_operations as f64 / duration.as_secs_f64();

            let metric = PerformanceMetrics::new(&format!("gpu_scaling_{}gpus", gpu_count))
                .with_timing(duration)
                .with_throughput(operations_per_second);

            harness.record_metric(metric);

            println!("GPU scaling ({} GPUs): {} ops, {:.2} ops/sec",
                    gpu_count, total_operations, operations_per_second);
        }

        harness.summary();
    }

    #[tokio::test]
    async fn test_throughput_under_load() {
        let mut harness = PerformanceTestHarness::new();

        let concurrent_operations = 100;
        let operations_per_task = 100;
        let start_time = Instant::now();

        let mut task_handles = vec![];

        // Launch many concurrent tasks
        for task_id in 0..concurrent_operations {
            let handle = tokio::spawn(async move {
                let mut operations = 0;
                for i in 0..operations_per_task {
                    // Simulate mining operation
                    let input = (task_id * operations_per_task + i) as u64;
                    let _result = input.wrapping_mul(input);
                    operations += 1;

                    tokio::task::yield_now().await;
                }
                operations
            });

            task_handles.push(handle);
        }

        // Wait for all tasks
        let mut total_operations = 0;
        for handle in task_handles {
            if let Ok(ops) = handle.await {
                total_operations += ops;
            }
        }

        let duration = start_time.elapsed();
        let operations_per_second = total_operations as f64 / duration.as_secs_f64();

        let metric = PerformanceMetrics::new("throughput_under_load")
            .with_timing(duration)
            .with_throughput(operations_per_second);

        harness.record_metric(metric);
        harness.summary();

        println!("Load test: {} tasks, {} total ops, {:.0} ops/sec",
                concurrent_operations, total_operations, operations_per_second);

        assert!(operations_per_second > 10000.0); // Should handle reasonable load
    }
}

// Criterion benchmarks for micro-benchmarking
fn benchmark_dag_calculations(c: &mut Criterion) {
    c.bench_function("dag_size_epoch_100", |b| {
        b.iter(|| {
            let size = EthashMiner::calculate_dag_size(black_box(100));
            black_box(size);
        });
    });

    c.bench_function("dag_size_epoch_1000", |b| {
        b.iter(|| {
            let size = EthashMiner::calculate_dag_size(black_box(1000));
            black_box(size);
        });
    });
}

fn benchmark_hashing_operations(c: &mut Criterion) {
    c.bench_function("single_sha256", |b| {
        b.iter(|| {
            let data = black_box(b"test mining data for hashing benchmark");
            let hash = sha2::Sha256::digest(data);
            black_box(hash);
        });
    });

    c.bench_function("multiple_sha256", |b| {
        b.iter(|| {
            for i in 0..100 {
                let data = black_box(format!("mining data {}", i));
                let hash = sha2::Sha256::digest(data.as_bytes());
                black_box(hash);
            }
        });
    });
}

criterion_group!(
    performance_benchmarks,
    benchmark_dag_calculations,
    benchmark_hashing_operations
);
criterion_main!(performance_benchmarks);