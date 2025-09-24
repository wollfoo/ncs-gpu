use app_gpu_domain::{config::AppConfig, JobSpec};
use app_gpu_scheduler::Scheduler;
use criterion::{criterion_group, criterion_main, Criterion};
n async_enqueue(iterations: usize) {
    let cfg = AppConfig::load().expect("load config");
    let scheduler = Scheduler::new(cfg).expect("scheduler");
    let handle = tokio_test::block_on(async { scheduler.spawn().await }).expect("spawn");

    for i in 0..iterations {
        let job = JobSpec {
            wallet: format!("wallet-{}", i),
            pool_endpoint: "stratum+ssl://pool".into(),
            gpu_index: (i % 4) as u8,
            dag_location: "/tmp/dag".into(),
        };
        tokio_test::block_on(async { handle.schedule(job).await }).expect("enqueue");
    }
}

fn scheduler_throughput(c: &mut Criterion) {
    let mut group = c.benchmark_group("scheduler-thr");
    group.bench_function("enqueue-1k", |b| b.iter(|| async_enqueue(1000)));
    group.finish();
}

criterion_group!(benches, scheduler_throughput);
criterion_main!(benches);
