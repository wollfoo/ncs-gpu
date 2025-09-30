// Worker - Node thực thi GPU workloads
// Chịu trách nhiệm: execute CUDA kernels, report metrics, heartbeat

use anyhow::Result;
use clap::Parser;
use gpu_common::{WorkerId, GpuDevice};
use tracing::{info, error};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod executor;
mod gpu_monitor;

use executor::WorkloadExecutor;
use gpu_monitor::GpuMonitor;

/// **[CLI Arguments]** (Tham số dòng lệnh)
#[derive(Parser, Debug)]
#[command(name = "worker")]
#[command(about = "GPU Mining Worker - Worker khai thác GPU", long_about = None)]
struct Args {
    /// **[Coordinator Address]** (Địa chỉ coordinator – gRPC endpoint)
    #[arg(short, long, default_value = "localhost:50051")]
    coordinator_addr: String,
    
    /// **[GPU Index]** (Chỉ số GPU – which GPU to use, -1 for all)
    #[arg(short, long, default_value = "0")]
    gpu_index: i32,
}

#[tokio::main]
async fn main() -> Result<()> {
    // Khởi tạo **[Tracing]** (tracing – structured logging)
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "worker=info".into()),
        )
        .with(tracing_subscriber::fmt::layer().json())
        .init();

    let args = Args::parse();
    
    info!("🚀 Khởi động Worker...");
    info!("🔗 Coordinator: {}", args.coordinator_addr);
    
    // Tạo **[Worker ID]** (ID worker – unique identifier)
    let worker_id = WorkerId::new();
    info!("🆔 Worker ID: {:?}", worker_id);
    
    // Khởi tạo **[GPU Monitor]** (giám sát GPU – NVML wrapper)
    let gpu_monitor = GpuMonitor::new()?;
    let gpu_devices = gpu_monitor.enumerate_devices()?;
    
    info!("🖥️  Phát hiện {} GPU(s):", gpu_devices.len());
    for device in &gpu_devices {
        info!("   - GPU {}: {} ({} MB)", 
            device.index, 
            device.name, 
            device.total_memory / 1024 / 1024
        );
    }
    
    // Khởi tạo **[Workload Executor]** (bộ thực thi workload – CUDA kernel launcher)
    let executor = WorkloadExecutor::new(args.gpu_index)?;
    info!("⚙️  Workload Executor đã sẵn sàng");
    
    // TODO: Đăng ký với coordinator qua gRPC
    // register_with_coordinator(&args.coordinator_addr, worker_id, gpu_devices).await?;
    
    // Khởi động **[Heartbeat Loop]** (vòng heartbeat – keep-alive signal)
    let heartbeat_handle = tokio::spawn({
        let coordinator_addr = args.coordinator_addr.clone();
        async move {
            heartbeat_loop(coordinator_addr, worker_id).await;
        }
    });
    
    // Khởi động **[Work Loop]** (vòng làm việc – poll tasks from coordinator)
    info!("🔄 Worker đang chờ tác vụ...");
    work_loop(worker_id, executor, gpu_monitor).await?;
    
    heartbeat_handle.await?;
    
    Ok(())
}

/// **[Heartbeat Loop]** (Vòng heartbeat – gửi keep-alive mỗi 10s)
async fn heartbeat_loop(coordinator_addr: String, worker_id: WorkerId) {
    let mut interval = tokio::time::interval(std::time::Duration::from_secs(10));
    
    loop {
        interval.tick().await;
        
        // TODO: Gửi heartbeat tới coordinator qua gRPC
        info!("💓 Heartbeat gửi tới {}", coordinator_addr);
    }
}

/// **[Work Loop]** (Vòng làm việc – poll và execute tasks)
async fn work_loop(
    worker_id: WorkerId,
    mut executor: WorkloadExecutor,
    gpu_monitor: GpuMonitor,
) -> Result<()> {
    loop {
        // TODO: Poll task từ coordinator
        // let task = poll_task_from_coordinator().await?;
        
        // Demo: Sleep để giả lập polling
        tokio::time::sleep(std::time::Duration::from_secs(5)).await;
        
        // TODO: Execute task
        // let result = executor.execute_workload(task.config).await?;
        
        // TODO: Report result về coordinator
        // report_result_to_coordinator(task.id, result).await?;
        
        // Log GPU stats
        if let Ok(stats) = gpu_monitor.get_gpu_stats(0) {
            info!("📊 GPU 0: {}% utilization, {} MB used", 
                stats.utilization, 
                stats.memory_used_mb
            );
        }
    }
}
