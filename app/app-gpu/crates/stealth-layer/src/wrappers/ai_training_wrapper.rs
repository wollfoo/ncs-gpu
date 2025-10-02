//! # AI Training Wrapper (Bọc Huấn Luyện AI)
//
//! Giả lập PyTorch/TensorFlow training workload.

use crate::config::ProfileConfig;
use crate::wrappers::{StealthProfile, GpuPattern, GpuPatternState};
use async_trait::async_trait;
use anyhow::Result;
use std::time::Duration;
use tracing::{debug, info};

pub struct AiTrainingWrapper {
    config: ProfileConfig,
    task_handle: Option<tokio::task::JoinHandle<()>>,
    start_time: std::time::Instant,
}

impl AiTrainingWrapper {
    pub fn new(config: ProfileConfig) -> Self {
        info!("🧠 Initializing AI Training Wrapper");
        Self {
            config,
            task_handle: None,
            start_time: std::time::Instant::now(),
        }
    }
}

#[async_trait]
impl StealthProfile for AiTrainingWrapper {
    async fn start(&mut self) -> Result<()> {
        info!(profile = self.name(), "Starting AI training simulation");

        let log_frequency = self.config.log_frequency;
        let handle = tokio::spawn(async move {
            let mut interval = tokio::time::interval(log_frequency);
            loop {
                interval.tick().await;
                // Simulate periodic training logs
                debug!(target: "fake_training", "Epoch {}/{}, Loss: {:.3}, Accuracy: {:.1}%",
                       42, 100, 0.342, 87.5);
            }
        });

        self.task_handle = Some(handle);
        Ok(())
    }

    async fn stop(&mut self) -> Result<()> {
        info!(profile = self.name(), "Stopping AI training simulation");

        if let Some(handle) = self.task_handle.take() {
            handle.abort();
        }

        Ok(())
    }

    async fn emit_logs(&self) -> Result<()> {
        debug!(target: "fake_training", "Epoch 42/100, Loss: 0.342, Accuracy: 87.5%");
        Ok(())
    }

    fn gpu_usage_pattern(&self) -> GpuPattern {
        GpuPattern {
            state: GpuPatternState::Plateau,
            target_utilization: self.config.gpu_target,
            ramp_duration: Duration::from_secs(30),
            plateau_duration: Duration::from_secs(600),
            cooldown_duration: Duration::from_secs(15),
        }
    }

    fn name(&self) -> &str {
        "ai_training"
    }
}