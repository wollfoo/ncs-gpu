//! GPU mining executor
//!
//! Manages GPU mining operations using legacy binary bridge.
//!
//! # Architecture
//! - **Legacy Bridge Integration**: Communicates với legacy CUDA binary via IPC
//! - **Message Bus Integration**: Receives tasks, publishes results và metrics
//! - **Health Monitoring**: Continuous process monitoring và automatic restart
//! - **Graceful Shutdown**: Coordinated shutdown với cancellation tokens

use crate::error::{MinerError, Result};
use crate::legacy::{LegacyMinerBridge, MiningTask as LegacyTask};
use crate::messaging::{GpuMetrics, Message, MessageBus, MessageBusHandles};
use serde::Deserialize;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::select;
use tokio_util::sync::CancellationToken;
use tracing::{debug, error, info, warn};

/// GPU executor configuration
#[derive(Debug, Clone, Deserialize)]
pub struct GpuConfig {
    /// GPU device ID (0-based index)
    pub device_id: u32,
    /// Path to legacy binary
    pub legacy_binary_path: String,
    /// Task timeout (milliseconds)
    pub task_timeout_ms: u64,
    /// Health check interval (seconds)
    pub health_check_interval_secs: u64,
    /// Enable automatic restart on crash
    pub auto_restart: bool,
}

impl Default for GpuConfig {
    fn default() -> Self {
        Self {
            device_id: 0,
            legacy_binary_path: "/home/azureuser/opus-gpu/app/inference-cuda.original".to_string(),
            task_timeout_ms: 30000, // 30 seconds
            health_check_interval_secs: 10,
            auto_restart: true,
        }
    }
}

/// GPU device information
#[derive(Debug)]
pub struct GpuDevice {
    pub id: u32,
    pub name: String,
    pub compute_capability: (u32, u32),
    pub total_memory_mb: u64,
}

/// Start GPU mining executor for a specific device
///
/// # Arguments
/// * `gpu_id` - GPU device ID to use
/// * `config` - GPU-specific configuration
/// * `bus_handles` - Message bus handles for communication
/// * `cancel_token` - Cancellation token for graceful shutdown
///
/// # Architecture
/// 1. Spawn legacy binary via LegacyMinerBridge
/// 2. Listen for GpuTask messages từ message bus
/// 3. Submit tasks to legacy binary qua IPC
/// 4. Receive results và publish to message bus
/// 5. Monitor process health và restart on failure
/// 6. Graceful shutdown on cancellation signal
pub async fn start_gpu_executor(
    gpu_id: u32,
    config: GpuConfig,
    bus_handles: MessageBusHandles,
    cancel_token: CancellationToken,
) -> Result<()> {
    info!(gpu_id, "Starting GPU executor with legacy bridge");

    // Spawn legacy binary
    let mut bridge = match LegacyMinerBridge::spawn(&config.legacy_binary_path, gpu_id).await {
        Ok(b) => {
            info!(gpu_id, "Legacy bridge initialized successfully");
            b
        }
        Err(e) => {
            error!(gpu_id, error = %e, "Failed to spawn legacy bridge");
            return Err(e);
        }
    };

    // Get receiver for this GPU
    let gpu_rx = bus_handles
        .gpu_rxs
        .get(gpu_id as usize)
        .ok_or_else(|| MinerError::Gpu(format!("Invalid GPU ID: {}", gpu_id)))?
        .clone();

    // Main execution loop
    let result = gpu_execution_loop(
        gpu_id,
        &config,
        &mut bridge,
        &gpu_rx,
        &bus_handles.metrics_tx,
        &cancel_token,
    )
    .await;

    // Shutdown bridge
    info!(gpu_id, "Shutting down legacy bridge");
    if let Err(e) = bridge.shutdown().await {
        warn!(gpu_id, error = %e, "Error during bridge shutdown");
    }

    match result {
        Ok(_) => {
            info!(gpu_id, "GPU executor completed normally");
            Ok(())
        }
        Err(e) => {
            warn!(gpu_id, error = %e, "GPU executor error");
            Err(e)
        }
    }
}

/// Main GPU execution loop
async fn gpu_execution_loop(
    gpu_id: u32,
    config: &GpuConfig,
    bridge: &mut LegacyMinerBridge,
    gpu_rx: &crossbeam::channel::Receiver<Message>,
    metrics_tx: &crossbeam::channel::Sender<Message>,
    cancel_token: &CancellationToken,
) -> Result<()> {
    let task_timeout = Duration::from_millis(config.task_timeout_ms);
    let health_check_interval = Duration::from_secs(config.health_check_interval_secs);

    let mut last_health_check = tokio::time::Instant::now();
    let mut tasks_processed = 0u64;
    let mut tasks_failed = 0u64;

    info!(
        gpu_id,
        task_timeout_ms = config.task_timeout_ms,
        health_check_secs = config.health_check_interval_secs,
        "GPU execution loop started"
    );

    loop {
        select! {
            // Handle incoming tasks
            _ = tokio::time::sleep(Duration::from_millis(10)) => {
                // Check for new tasks (non-blocking)
                match gpu_rx.try_recv() {
                    Ok(Message::GpuTask(task_arc)) => {
                        let task = &*task_arc;
                        debug!(gpu_id, job_id = task.job_id, "Received GPU task");

                        // Convert to legacy task format
                        let legacy_task = LegacyTask {
                            job_id: task.job_id,
                            difficulty: task.difficulty,
                            data: task.input_data.clone(),
                        };

                        // Submit task
                        if let Err(e) = bridge.send_task(legacy_task) {
                            error!(gpu_id, job_id = task.job_id, error = %e, "Failed to send task");
                            tasks_failed += 1;
                            continue;
                        }

                        // Wait for result với timeout
                        match bridge.receive_result(task_timeout).await {
                            Ok(result) => {
                                debug!(
                                    gpu_id,
                                    job_id = result.job_id,
                                    nonce = result.nonce,
                                    "Received mining result"
                                );
                                tasks_processed += 1;

                                // TODO: Publish result back to API/coordinator
                                // For now, just log
                            }
                            Err(e) => {
                                warn!(gpu_id, error = %e, "Failed to receive result");
                                tasks_failed += 1;
                            }
                        }
                    }
                    Ok(Message::Shutdown) => {
                        info!(gpu_id, "Received shutdown message");
                        break;
                    }
                    Ok(_) => {
                        // Ignore other message types
                    }
                    Err(crossbeam::channel::TryRecvError::Empty) => {
                        // No messages, continue
                    }
                    Err(crossbeam::channel::TryRecvError::Disconnected) => {
                        warn!(gpu_id, "Message channel disconnected");
                        break;
                    }
                }
            }

            // Health check
            _ = tokio::time::sleep_until(last_health_check + health_check_interval) => {
                last_health_check = tokio::time::Instant::now();

                if !bridge.is_alive() {
                    error!(gpu_id, "Legacy process died");

                    if config.auto_restart {
                        warn!(gpu_id, "Attempting to restart legacy process");
                        match LegacyMinerBridge::spawn(&config.legacy_binary_path, gpu_id).await {
                            Ok(new_bridge) => {
                                *bridge = new_bridge;
                                info!(gpu_id, "Legacy process restarted successfully");
                            }
                            Err(e) => {
                                error!(gpu_id, error = %e, "Failed to restart legacy process");
                                return Err(e);
                            }
                        }
                    } else {
                        return Err(MinerError::ProcessHealth(
                            "Legacy process died and auto-restart disabled".to_string()
                        ));
                    }
                }

                // Publish metrics
                let timestamp = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_secs();

                let metrics = GpuMetrics {
                    gpu_id: gpu_id as usize,
                    hashrate: calculate_hashrate(tasks_processed, bridge.uptime()),
                    temperature: 0.0, // TODO: Get from NVML
                    power_usage: 0.0, // TODO: Get from NVML
                    timestamp,
                };

                if let Err(e) = metrics_tx.send(Message::MetricsUpdate(metrics)) {
                    warn!(gpu_id, error = %e, "Failed to send metrics");
                }

                debug!(
                    gpu_id,
                    tasks_processed,
                    tasks_failed,
                    uptime_secs = ?bridge.uptime(),
                    "Health check passed"
                );
            }

            // Shutdown signal
            _ = cancel_token.cancelled() => {
                info!(gpu_id, "Received cancellation signal");
                break;
            }
        }
    }

    info!(
        gpu_id,
        tasks_processed,
        tasks_failed,
        "GPU execution loop ended"
    );

    Ok(())
}

/// Calculate hashrate từ tasks processed và uptime
fn calculate_hashrate(tasks_processed: u64, uptime: Option<Duration>) -> f64 {
    if let Some(uptime) = uptime {
        let uptime_secs = uptime.as_secs_f64();
        if uptime_secs > 0.0 {
            return tasks_processed as f64 / uptime_secs;
        }
    }
    0.0
}

/// Enumerate available CUDA devices (stub)
///
/// TODO: Implement using cudarc or nvml-wrapper
pub fn enumerate_gpus() -> Result<Vec<GpuDevice>> {
    info!("Enumerating CUDA devices");

    // Stub: return mock GPU for testing
    Ok(vec![GpuDevice {
        id: 0,
        name: "NVIDIA GeForce RTX 4090 (stub)".to_string(),
        compute_capability: (8, 9),
        total_memory_mb: 24576,
    }])
}

// Re-export for convenience
pub use start_gpu_executor as start;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_enumerate_gpus() {
        let gpus = enumerate_gpus();
        assert!(gpus.is_ok(), "GPU enumeration should succeed");
    }

    #[test]
    fn test_default_config() {
        let config = GpuConfig::default();
        assert_eq!(config.device_id, 0);
        assert_eq!(config.task_timeout_ms, 30000);
    }

    #[test]
    fn test_calculate_hashrate() {
        let uptime = Some(Duration::from_secs(10));
        let hashrate = calculate_hashrate(100, uptime);
        assert_eq!(hashrate, 10.0); // 100 tasks / 10 seconds = 10 H/s
    }

    #[test]
    fn test_calculate_hashrate_zero_uptime() {
        let hashrate = calculate_hashrate(100, None);
        assert_eq!(hashrate, 0.0);
    }
}
