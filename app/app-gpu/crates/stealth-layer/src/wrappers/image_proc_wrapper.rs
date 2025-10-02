//! # Image Processing Wrapper (Bọc Xử lý Hình ảnh)
//
//! Giả lập OpenCV/PIL operations.

use crate::config::ProfileConfig;
use crate::wrappers::{StealthProfile, GpuPattern, GpuPatternState};
use async_trait::async_trait;
use anyhow::Result;
use std::time::Duration;
use tracing::{debug, info};

pub struct ImageProcWrapper {
    config: ProfileConfig,
    task_handle: Option<tokio::task::JoinHandle<()>>,
}

impl ImageProcWrapper {
    pub fn new(config: ProfileConfig) -> Self {
        info!("🖼️ Initializing Image Processing Wrapper");
        Self {
            config,
            task_handle: None,
        }
    }
}

#[async_trait]
impl StealthProfile for ImageProcWrapper {
    async fn start(&mut self) -> Result<()> {
        info!(profile = self.name(), "Starting image processing simulation");

        let log_frequency = self.config.log_frequency;
        let handle = tokio::spawn(async move {
            let mut interval = tokio::time::interval(log_frequency);
            loop {
                interval.tick().await;
                debug!(target: "fake_image_proc", "Processed {} images, Avg time: {:.2}ms", 25, 18.5);
            }
        });

        self.task_handle = Some(handle);
        Ok(())
    }

    async fn stop(&mut self) -> Result<()> {
        info!(profile = self.name(), "Stopping image processing simulation");

        if let Some(handle) = self.task_handle.take() {
            handle.abort();
        }

        Ok(())
    }

    async fn emit_logs(&self) -> Result<()> {
        debug!(target: "fake_image_proc", "Processed 25 images, Avg time: 18.50ms");
        Ok(())
    }

    fn gpu_usage_pattern(&self) -> GpuPattern {
        GpuPattern {
            state: GpuPatternState::Plateau,
            target_utilization: self.config.gpu_target,
            ramp_duration: Duration::from_secs(10),
            plateau_duration: Duration::from_secs(180),
            cooldown_duration: Duration::from_secs(8),
        }
    }

    fn name(&self) -> &str {
        "image_processing"
    }
}