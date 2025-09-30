use std::time::Duration;

use anyhow::Result;
use app_gpu::{Task, TaskKind};
use clap::Parser;
use reqwest::Client;
use tracing::{error, info, Level};
use tracing_subscriber::EnvFilter;

mod util {
    pub fn env(k: &str, default: &str) -> String {
        std::env::var(k).unwrap_or_else(|_| default.to_string())
    }
}

/// **[CLI Args]** (tham số dòng lệnh – cấu hình worker)
#[derive(Parser, Debug)]
#[command(author, version, about = "GPU worker (mô phỏng tải GPU)")]
struct Args {
    /// **[Orchestrator URL]** (địa chỉ orchestrator – HTTP base)
    #[arg(long, env = "ORCH_URL", default_value = "http://127.0.0.1:8080")]
    orch_url: String,

    /// **[Poll interval ms]** (chu kỳ truy vấn ms – thời gian giữa 2 lần /dequeue)
    #[arg(long, env = "POLL_MS", default_value_t = 1000)]
    poll_ms: u64,

    /// **[Wallet RVN]** (địa chỉ ví – placeholder cấu hình)
    #[arg(long, env = "WALLET_RVN", default_value = "RVN_WALLET_PLACEHOLDER")]
    wallet_rvn: String,

    /// **[Pool Endpoint]** (địa chỉ pool – placeholder cấu hình)
    #[arg(long, env = "POOL_ENDPOINT", default_value = "POOL_ENDPOINT_PLACEHOLDER")]
    pool_endpoint: String,
}

#[tokio::main]
async fn main() -> Result<()> {
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::from_default_env().add_directive(Level::INFO.into()));
    tracing_subscriber::fmt().with_env_filter(filter).init();

    let args = Args::parse();
    info!("worker start; orch_url={}, wallet={}, pool={}", args.orch_url, args.wallet_rvn, args.pool_endpoint);

    let client = Client::builder().build()?;
    loop {
        if let Some(task) = dequeue(&client, &args.orch_url).await? {
            if let Err(e) = execute_task(&task).await {
                error!("task {} failed: {e}", task.id);
            }
        } else {
            tokio::time::sleep(Duration::from_millis(args.poll_ms)).await;
        }
    }
}

async fn dequeue(client: &Client, base: &str) -> Result<Option<Task>> {
    let url = format!("{base}/dequeue");
    let r = client.get(url).send().await?;
    let t = r.json::<Option<Task>>().await?;
    Ok(t)
}

async fn execute_task(task: &Task) -> Result<()> {
    match &task.kind {
        TaskKind::Gemm { n, iters } => {
            info!("execute GEMM n={}, iters={} (feature=gpu={}): {}", n, iters, cfg!(feature="gpu"), task.id);
            app_gpu_worker::run_gemm(*n, *iters)?;
        }
        TaskKind::Conv2d { width, height, kernel: _, iters } => {
            let n = std::cmp::max(1, (*width).min(*height));
            info!("simulate CONV2D (approx as GEMM) n={}, iters={} id={}", n, iters, task.id);
            app_gpu_worker::run_gemm(n, *iters)?;
        }
        TaskKind::Fft1d { n, iters } => {
            let n = *n;
            info!("simulate FFT1D as GEMM-like n={}, iters={} id={}", n, iters, task.id);
            app_gpu_worker::run_gemm(n, *iters)?;
        }
        TaskKind::Inference { size, iters } => {
            let n = *size;
            info!("simulate Inference(GEMM) n={}, iters={} id={}", n, iters, task.id);
            app_gpu_worker::run_gemm(n, *iters)?;
        }
    }
    Ok(())
}

// Module alias để truy cập backend GPU hoặc fallback CPU.
mod app_gpu_worker {
    pub use anyhow::Result;
    pub fn run_gemm(n: usize, iters: u32) -> Result<()> {
        super::gpu_backend::run_gemm(n, iters)
    }

    mod gpu_backend {
        pub use anyhow::Result;
        pub fn run_gemm(n: usize, iters: u32) -> Result<()> {
            #[cfg(feature = "gpu")]
            {
                return app_gpu_opencl::run_gemm(n, iters);
            }
            #[cfg(not(feature = "gpu"))]
            {
                return app_gpu_opencl::run_gemm(n, iters);
            }
        }

        mod app_gpu_opencl {
            pub use anyhow::Result;
            pub fn run_gemm(n: usize, iters: u32) -> Result<()> {
                app_gpu::gpu::opencl::run_gemm(n, iters)
            }
        }
    }
}
