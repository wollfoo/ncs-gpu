//! Performance benchmarks for OPUS-GPU Core

use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId, Throughput};
use opus_gpu_core::{IpcManager, Message, config::IpcConfig};
use tokio::runtime::Runtime;

fn benchmark_ipc_throughput(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    
    let mut group = c.benchmark_group("ipc_throughput");
    
    for size in [64, 256, 1024, 4096, 16384].iter() {
        group.throughput(Throughput::Bytes(*size as u64));
        group.bench_with_input(
            BenchmarkId::from_parameter(size),
            size,
            |b, &size| {
                b.to_async(&rt).iter(|| async move {
                    let config = IpcConfig {
                        shared_memory_size_mb: 100,
                        num_segments: 4,
                        bounded_queue: false,
                        queue_size: 0,
                    };
                    
                    let ipc = IpcManager::new(config).await.unwrap();
                    let payload = vec![0u8; size];
                    
                    let message = Message {
                        source: "bench".to_string(),
                        destination: "test".to_string(),
                        payload,
                    };
                    
                    ipc.send_message(message).await.unwrap();
                });
            },
        );
    }
    group.finish();
}

fn benchmark_message_serialization(c: &mut Criterion) {
    c.bench_function("message_serialize", |b| {
        let message = Message {
            source: "source".to_string(),
            destination: "dest".to_string(),
            payload: vec![0u8; 1024],
        };
        
        b.iter(|| {
            black_box(bincode::serialize(&message).unwrap())
        });
    });
    
    c.bench_function("message_deserialize", |b| {
        let message = Message {
            source: "source".to_string(),
            destination: "dest".to_string(),
            payload: vec![0u8; 1024],
        };
        let data = bincode::serialize(&message).unwrap();
        
        b.iter(|| {
            black_box(bincode::deserialize::<Message>(&data).unwrap())
        });
    });
}

fn benchmark_config_loading(c: &mut Criterion) {
    use opus_gpu_core::Config;
    use tempfile::tempdir;
    
    c.bench_function("config_default", |b| {
        b.iter(|| {
            black_box(Config::default())
        });
    });
    
    c.bench_function("config_validate", |b| {
        let config = Config::default();
        b.iter(|| {
            black_box(config.validate()).unwrap()
        });
    });
    
    c.bench_function("config_save_load", |b| {
        let temp = tempdir().unwrap();
        let path = temp.path().join("config.yaml");
        let config = Config::default();
        
        b.iter(|| {
            config.save(&path).unwrap();
            black_box(Config::load().unwrap());
        });
    });
}

criterion_group!(
    benches,
    benchmark_ipc_throughput,
    benchmark_message_serialization,
    benchmark_config_loading
);
criterion_main!(benches);
