// CLI Tool cho GPU Mining System
// Công cụ dòng lệnh để submit tasks, query status, list workers

use anyhow::Result;
use clap::{Parser, Subcommand};
use colored::*;
use comfy_table::{Table, presets::UTF8_FULL};
use gpu_common::{WorkloadType, WorkloadConfig};

mod client;
use client::MiningClient;

/// **[GPU Miner CLI]** (Công cụ dòng lệnh GPU Miner)
#[derive(Parser)]
#[command(name = "gpu-miner")]
#[command(about = "GPU Mining System CLI - Công cụ quản lý khai thác GPU", long_about = None)]
#[command(version)]
struct Cli {
    /// **[Coordinator Address]** (Địa chỉ coordinator – gRPC endpoint)
    #[arg(short, long, default_value = "http://localhost:50051", global = true)]
    coordinator: String,
    
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// **[Submit Task]** (Gửi tác vụ – submit workload to coordinator)
    Submit {
        /// **[Workload Type]** (Loại workload)
        #[arg(short = 't', long, value_enum)]
        workload_type: WorkloadTypeArg,
        
        /// **[Duration]** (Thời gian – seconds)
        #[arg(short, long, default_value = "60")]
        duration: u64,
        
        /// **[Batch Size]** (Kích thước batch)
        #[arg(short, long, default_value = "32")]
        batch_size: u32,
        
        /// **[GPU Utilization Target]** (Mục tiêu sử dụng GPU – percentage)
        #[arg(short = 'u', long, default_value = "80.0")]
        gpu_utilization: f32,
        
        /// **[Memory Size]** (Kích thước bộ nhớ – MB)
        #[arg(short, long, default_value = "1024")]
        memory_mb: u32,
    },
    
    /// **[Get Status]** (Lấy trạng thái – query task status)
    Status {
        /// **[Task ID]** (ID tác vụ – UUID)
        task_id: String,
    },
    
    /// **[List Workers]** (Liệt kê workers – show all registered workers)
    Workers,
    
    /// **[Benchmark]** (Benchmark – run performance test)
    Benchmark {
        /// **[Number of Tasks]** (Số lượng tác vụ)
        #[arg(short, long, default_value = "10")]
        num_tasks: u32,
        
        /// **[Concurrent]** (Đồng thời – submit all at once)
        #[arg(short, long)]
        concurrent: bool,
    },
}

#[derive(clap::ValueEnum, Clone, Debug)]
enum WorkloadTypeArg {
    AiTraining,
    ImageProcessing,
    ScientificComputing,
    AiInference,
}

impl From<WorkloadTypeArg> for WorkloadType {
    fn from(arg: WorkloadTypeArg) -> Self {
        match arg {
            WorkloadTypeArg::AiTraining => WorkloadType::AiTraining,
            WorkloadTypeArg::ImageProcessing => WorkloadType::ImageProcessing,
            WorkloadTypeArg::ScientificComputing => WorkloadType::ScientificComputing,
            WorkloadTypeArg::AiInference => WorkloadType::AiInference,
        }
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    
    // Khởi tạo client
    let mut client = MiningClient::connect(&cli.coordinator).await?;
    
    match cli.command {
        Commands::Submit {
            workload_type,
            duration,
            batch_size,
            gpu_utilization,
            memory_mb,
        } => {
            handle_submit(
                &mut client,
                workload_type,
                duration,
                batch_size,
                gpu_utilization,
                memory_mb,
            ).await?;
        }
        
        Commands::Status { task_id } => {
            handle_status(&mut client, &task_id).await?;
        }
        
        Commands::Workers => {
            handle_workers(&mut client).await?;
        }
        
        Commands::Benchmark { num_tasks, concurrent } => {
            handle_benchmark(&mut client, num_tasks, concurrent).await?;
        }
    }
    
    Ok(())
}

/// **[Handle Submit]** (Xử lý submit – gửi task)
async fn handle_submit(
    client: &mut MiningClient,
    workload_type: WorkloadTypeArg,
    duration: u64,
    batch_size: u32,
    gpu_utilization: f32,
    memory_mb: u32,
) -> Result<()> {
    let config = WorkloadConfig {
        workload_type: workload_type.clone().into(),
        duration_secs: duration,
        batch_size,
        gpu_utilization_target: gpu_utilization,
        memory_size_mb: memory_mb,
    };
    
    println!("{}", "Submitting task...".bright_cyan());
    println!("  Workload: {:?}", workload_type);
    println!("  Duration: {}s", duration);
    println!("  Batch Size: {}", batch_size);
    println!("  GPU Target: {:.1}%", gpu_utilization);
    println!("  Memory: {} MB", memory_mb);
    println!();
    
    let task_id = client.submit_task(config).await?;
    
    println!("{}", "✓ Task submitted successfully!".bright_green().bold());
    println!("  Task ID: {}", task_id.to_string().bright_yellow());
    println!();
    println!("Use {} to check status", 
             format!("gpu-miner status {}", task_id).bright_cyan());
    
    Ok(())
}

/// **[Handle Status]** (Xử lý status – query task)
async fn handle_status(client: &mut MiningClient, task_id: &str) -> Result<()> {
    println!("{}", format!("Querying task {}...", task_id).bright_cyan());
    println!();
    
    let (status, result, error) = client.get_task_status(task_id).await?;
    
    // Status table
    let mut table = Table::new();
    table.load_preset(UTF8_FULL);
    table.set_header(vec!["Field", "Value"]);
    
    let status_str = match status {
        gpu_common::TaskStatus::Pending => "Pending".yellow(),
        gpu_common::TaskStatus::Running => "Running".bright_cyan(),
        gpu_common::TaskStatus::Completed => "Completed".bright_green(),
        gpu_common::TaskStatus::Failed => "Failed".bright_red(),
        gpu_common::TaskStatus::Cancelled => "Cancelled".bright_black(),
    };
    
    table.add_row(vec!["Task ID", task_id]);
    table.add_row(vec!["Status", &status_str.to_string()]);
    
    if let Some(err) = error {
        table.add_row(vec!["Error", &err.bright_red().to_string()]);
    }
    
    if let Some(res) = result {
        table.add_row(vec!["Throughput", &format!("{:.2} ops/s", res.throughput)]);
        table.add_row(vec!["Avg Latency", &format!("{:.2} ms", res.avg_latency_ms)]);
        table.add_row(vec!["P95 Latency", &format!("{:.2} ms", res.p95_latency_ms)]);
        table.add_row(vec!["P99 Latency", &format!("{:.2} ms", res.p99_latency_ms)]);
        table.add_row(vec!["GPU Utilization", &format!("{:.1}%", res.gpu_utilization)]);
        table.add_row(vec!["Memory Used", &format!("{} MB", res.memory_used_mb)]);
        table.add_row(vec!["Total Ops", &format!("{}", res.total_operations)]);
    }
    
    println!("{table}");
    
    Ok(())
}

/// **[Handle Workers]** (Xử lý workers – list workers)
async fn handle_workers(client: &mut MiningClient) -> Result<()> {
    println!("{}", "Fetching workers...".bright_cyan());
    println!();
    
    let workers = client.list_workers().await?;
    
    if workers.is_empty() {
        println!("{}", "No workers registered".yellow());
        return Ok(());
    }
    
    // Workers table
    let mut table = Table::new();
    table.load_preset(UTF8_FULL);
    table.set_header(vec!["Worker ID", "GPUs", "Status", "Last Heartbeat"]);
    
    for worker in workers {
        let status = if worker.is_busy {
            "Busy".yellow()
        } else {
            "Available".bright_green()
        };
        
        table.add_row(vec![
            &worker.worker_id.to_string()[..8],
            &worker.gpu_devices.len().to_string(),
            &status.to_string(),
            &format_timestamp(worker.last_heartbeat_unix),
        ]);
        
        // GPU details
        for gpu in &worker.gpu_devices {
            table.add_row(vec![
                "",
                &format!("  └─ GPU {}: {}", gpu.index, gpu.name),
                "",
                &format!("{} MB", gpu.total_memory / 1024 / 1024),
            ]);
        }
    }
    
    println!("{table}");
    println!("\n{} worker(s) registered", workers.len().to_string().bright_cyan());
    
    Ok(())
}

/// **[Handle Benchmark]** (Xử lý benchmark)
async fn handle_benchmark(
    client: &mut MiningClient,
    num_tasks: u32,
    concurrent: bool,
) -> Result<()> {
    println!("{}", "Running benchmark...".bright_cyan().bold());
    println!("  Tasks: {}", num_tasks);
    println!("  Mode: {}", if concurrent { "Concurrent" } else { "Sequential" });
    println!();
    
    use indicatif::{ProgressBar, ProgressStyle};
    
    let pb = ProgressBar::new(num_tasks as u64);
    pb.set_style(
        ProgressStyle::default_bar()
            .template("[{elapsed_precise}] {bar:40.cyan/blue} {pos}/{len} {msg}")?
            .progress_chars("=>-"),
    );
    
    let start = std::time::Instant::now();
    
    if concurrent {
        // Submit all tasks at once
        let mut handles = vec![];
        
        for i in 0..num_tasks {
            let mut client_clone = client.clone();
            let handle = tokio::spawn(async move {
                let config = WorkloadConfig::default();
                client_clone.submit_task(config).await
            });
            handles.push(handle);
        }
        
        for handle in handles {
            let _ = handle.await?;
            pb.inc(1);
        }
    } else {
        // Submit tasks sequentially
        for i in 0..num_tasks {
            let config = WorkloadConfig::default();
            let _ = client.submit_task(config).await?;
            pb.inc(1);
        }
    }
    
    pb.finish_with_message("Done");
    
    let elapsed = start.elapsed();
    let throughput = num_tasks as f64 / elapsed.as_secs_f64();
    
    println!();
    println!("{}", "Benchmark Results:".bright_green().bold());
    println!("  Total Tasks: {}", num_tasks);
    println!("  Total Time: {:.2}s", elapsed.as_secs_f64());
    println!("  Throughput: {:.2} tasks/s", throughput);
    
    Ok(())
}

/// **[Format Timestamp]** (Định dạng timestamp)
fn format_timestamp(unix_timestamp: i64) -> String {
    use chrono::{DateTime, Utc};
    let dt = DateTime::<Utc>::from_timestamp(unix_timestamp, 0)
        .unwrap_or_else(|| Utc::now());
    dt.format("%Y-%m-%d %H:%M:%S").to_string()
}
