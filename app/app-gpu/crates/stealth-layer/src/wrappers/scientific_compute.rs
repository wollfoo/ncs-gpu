//! # Scientific Computing Wrapper (Bọc Tính toán Khoa học)
//
//! Giả lập CUDA simulation workloads.

use crate::config::ProfileConfig;
use crate::wrappers::{StealthProfile, GpuPattern, GpuPatternState};
use async_trait::async_trait;
use anyhow::Result;
use std::time::Duration;
use tracing::{debug, info};

pub struct ScientificComputeWrapper {
    config: ProfileConfig,
    task_handle: Option<tokio::task::JoinHandle<()>>,
}

impl ScientificComputeWrapper {
    pub fn new(config: ProfileConfig) -> Self {
        info!("🔬 Initializing Scientific Computing Wrapper");
        Self {
            config,
            task_handle: None,
        }
    }
}

#[async_trait]
impl StealthProfile for ScientificComputeWrapper {
    async fn start(&mut self) -> Result<()> {
        info!(profile = self.name(), "Starting scientific computing simulation");

        let log_frequency = self.config.log_frequency;
        let handle = tokio::spawn(async move {
            let mut interval = tokio::time::interval(log_frequency);
            loop {
                interval.tick().await;
                debug!(target: "fake_scientific", "Iteration {}, Energy: {:.6}, Time step: {}", 1500, 42.7, 0.001);
            }
        });

        self.task_handle = Some(handle);
        Ok(())
    }

    async fn stop(&mut self) -> Result<()> {
        info!(profile = self.name(), "Stopping scientific computing simulation");

        if let Some(handle) = self.task_handle.take() {
            handle.abort();
        }

        Ok(())
    }

    async fn emit_logs(&self) -> Result<()> {
        debug!(target: "fake_scientific", "Iteration 1500, Energy: 42.700000, Time step: 0.001");
        Ok(())
    }

    fn gpu_usage_pattern(&self) -> GpuPattern {
        GpuPattern {
            state: GpuPatternState::Plateau,
            target_utilization: self.config.gpu_target,
            ramp_duration: Duration::from_secs(45),
            plateau_duration: Duration::from_secs(1200),
            cooldown_duration: Duration::from_secs(30),
        }
    }

    fn name(&self) -> &str {
        "scientific"
    }
}