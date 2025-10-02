//! # AI Inference Wrapper (Bọc Suy luận AI)
//
//! Giả lập AI inference workloads như TensorFlow Serving, TorchServe.

use crate::config::ProfileConfig;
use crate::wrappers::{StealthProfile, GpuPattern, GpuPatternState};
use async_trait::async_trait;
use anyhow::Result;
use std::time::Duration;
use tracing::{debug, info};

pub struct AiInferenceWrapper {
    config: ProfileConfig,
    task_handle: Option<tokio::task::JoinHandle<()>>,
}

impl AiInferenceWrapper {
    pub fn new(config: ProfileConfig) -> Self {
        info!("🧠 Initializing AI Inference Wrapper");
        Self {
            config,
            task_handle: None,
        }
    }
}

#[async_trait]
impl StealthProfile for AiInferenceWrapper {
    async fn start(&mut self) -> Result<()> {
        info!(profile = self.name(), "Starting AI inference simulation");

        let log_frequency = self.config.log_frequency;
        let handle = tokio::spawn(async move {
            let mut interval = tokio::time::interval(log_frequency);
            loop {
                interval.tick().await;
                // Simulate periodic inference logs
                debug!(target: "fake_inference", "Processed {}/{} batches, Latency: {:.2}ms, Throughput: {}/s",
                       15, 20, 12.5, 80);
            }
        });

        self.task_handle = Some(handle);
        Ok(())
    }

    async fn stop(&mut self) -> Result<()> {
        info!(profile = self.name(), "Stopping AI inference simulation");

        if let Some(handle) = self.task_handle.take() {
            handle.abort();
        }

        Ok(())
    }

    async fn emit_logs(&self) -> Result<()> {
        debug!(target: "fake_inference", "Processed 15/20 batches, Latency: 12.50ms, Throughput: 80/s");
        Ok(())
    }

    fn gpu_usage_pattern(&self) -> GpuPattern {
        GpuPattern {
            state: GpuPatternState::Plateau,
            target_utilization: self.config.gpu_target,
            ramp_duration: Duration::from_secs(5),
            plateau_duration: Duration::from_secs(300),
            cooldown_duration: Duration::from_secs(5),
        }
    }

    fn name(&self) -> &str {
        "ai_inference"
    }
}
