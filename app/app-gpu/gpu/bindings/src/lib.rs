use anyhow::{Context, Result};
use serde::Serialize;
use tracing::info;

#[derive(Debug, Clone, Serialize)]
pub struct GpuJob {
    pub kernel: String,
    pub block_size: u32,
    pub grid_size: u32,
}

pub fn execute(job: &GpuJob) -> Result<()> {
    info!(target: "gpu", job = serde_json::to_string(job).unwrap(), "dispatch");
    // TODO: integrate real CUDA launch via ffi
    Ok(())
}

pub fn compile_kernel(path: &str) -> Result<()> {
    std::fs::metadata(path).context("kernel path invalid")?;
    Ok(())
}
