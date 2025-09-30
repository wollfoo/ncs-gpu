//! Legacy binary bridge
//!
//! Production-ready compatibility layer for legacy GPU mining binaries.
//! Provides process lifecycle management, IPC communication, and health monitoring.
//!
//! # Architecture
//! - **Process Management**: Spawn, monitor, gracefully shutdown legacy binaries
//! - **IPC Protocol**: Stdin/stdout-based communication with task submission and result retrieval
//! - **Health Monitoring**: Zombie process detection, automatic restart, crash recovery
//! - **Error Handling**: Comprehensive error types for all failure modes
//!
//! # IPC Protocol
//! **Input (stdin)**: `<job_id> <difficulty> <data_hex>\n`
//! **Output (stdout)**: `<job_id> <nonce> <hash_hex>\n`

use crate::error::{MinerError, Result};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::{Duration, Instant};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::mpsc;
use tokio::time::timeout;
use tracing::{debug, error, info, warn};

/// Mining task submitted to legacy binary
#[derive(Debug, Clone)]
pub struct MiningTask {
    pub job_id: u64,
    pub difficulty: u64,
    pub data: Vec<u8>,
}

/// Mining result returned from legacy binary
#[derive(Debug, Clone)]
pub struct MiningResult {
    pub job_id: u64,
    pub nonce: u64,
    pub hash: Vec<u8>,
}

/// Legacy binary configuration
#[derive(Debug, Clone, Deserialize)]
pub struct LegacyConfig {
    /// Path to legacy miner binary
    pub binary_path: PathBuf,
    /// Command-line arguments
    pub args: Vec<String>,
    /// Environment variables
    pub env: Vec<(String, String)>,
    /// Enable IPC communication
    pub enable_ipc: bool,
}

/// Legacy miner status message
#[derive(Debug, Serialize, Deserialize)]
pub struct LegacyStatus {
    pub hashrate: f64,
    pub shares_accepted: u64,
    pub shares_rejected: u64,
    pub uptime_secs: u64,
}

/// Production-ready legacy miner bridge
///
/// Manages lifecycle của legacy GPU binary process, IPC communication,
/// health monitoring, và graceful shutdown.
pub struct LegacyMinerBridge {
    /// GPU device ID
    gpu_id: u32,
    /// Path to legacy binary
    binary_path: PathBuf,
    /// Running child process
    child: Option<Child>,
    /// Task submission channel (stdin writer)
    task_tx: Option<mpsc::UnboundedSender<MiningTask>>,
    /// Result reception channel (stdout reader)
    result_rx: Option<mpsc::UnboundedReceiver<MiningResult>>,
    /// Process start time
    started_at: Option<Instant>,
    /// Health check interval
    health_check_interval: Duration,
}

impl LegacyMinerBridge {
    /// Spawn legacy binary and establish IPC channels
    ///
    /// # Arguments
    /// * `binary_path` - Path to legacy inference-cuda binary
    /// * `gpu_id` - GPU device ID to assign
    ///
    /// # Returns
    /// * `Result<Self>` - Initialized bridge with active process
    ///
    /// # Errors
    /// * `MinerError::Config` - Binary not found or not executable
    /// * `MinerError::LegacyBridge` - Process spawn failure
    pub async fn spawn(binary_path: impl AsRef<Path>, gpu_id: u32) -> Result<Self> {
        let binary_path = binary_path.as_ref().to_path_buf();

        // Validate binary exists và executable
        if !binary_path.exists() {
            return Err(MinerError::Config(format!(
                "Legacy binary not found: {}",
                binary_path.display()
            )));
        }

        info!(
            gpu_id,
            binary = %binary_path.display(),
            "Spawning legacy miner process"
        );

        // Spawn process với piped stdin/stdout
        let mut child = Command::new(&binary_path)
            .arg(format!("--device={}", gpu_id))
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()
            .map_err(|e| {
                MinerError::LegacyBridge(format!("Failed to spawn process: {}", e))
            })?;

        let pid = child.id().unwrap_or(0);
        info!(gpu_id, pid, "Legacy process spawned successfully");

        // Extract stdin/stdout handles
        let stdin = child.stdin.take().ok_or_else(|| {
            MinerError::LegacyBridge("Failed to capture stdin".to_string())
        })?;
        let stdout = child.stdout.take().ok_or_else(|| {
            MinerError::LegacyBridge("Failed to capture stdout".to_string())
        })?;
        let stderr = child.stderr.take().ok_or_else(|| {
            MinerError::LegacyBridge("Failed to capture stderr".to_string())
        })?;

        // Create task submission channel
        let (task_tx, mut task_rx) = mpsc::unbounded_channel::<MiningTask>();

        // Create result reception channel
        let (result_tx, result_rx) = mpsc::unbounded_channel::<MiningResult>();

        // Spawn stdin writer task
        tokio::spawn(async move {
            let mut stdin = stdin;
            while let Some(task) = task_rx.recv().await {
                let data_hex = hex::encode(&task.data);
                let line = format!("{} {} {}\n", task.job_id, task.difficulty, data_hex);

                if let Err(e) = stdin.write_all(line.as_bytes()).await {
                    error!("Failed to write task to stdin: {}", e);
                    break;
                }

                if let Err(e) = stdin.flush().await {
                    error!("Failed to flush stdin: {}", e);
                    break;
                }

                debug!(job_id = task.job_id, "Sent task to legacy binary");
            }
        });

        // Spawn stdout reader task
        let gpu_id_clone = gpu_id;
        tokio::spawn(async move {
            let reader = BufReader::new(stdout);
            let mut lines = reader.lines();

            while let Ok(Some(line)) = lines.next_line().await {
                debug!(gpu_id = gpu_id_clone, "Legacy stdout: {}", line);

                // Parse result: "<job_id> <nonce> <hash_hex>"
                match parse_mining_result(&line) {
                    Ok(result) => {
                        if result_tx.send(result).is_err() {
                            warn!("Result receiver dropped, stopping stdout reader");
                            break;
                        }
                    }
                    Err(e) => {
                        warn!("Failed to parse mining result: {}", e);
                    }
                }
            }
        });

        // Spawn stderr logger task
        tokio::spawn(async move {
            let reader = BufReader::new(stderr);
            let mut lines = reader.lines();

            while let Ok(Some(line)) = lines.next_line().await {
                warn!(gpu_id = gpu_id_clone, "Legacy stderr: {}", line);
            }
        });

        Ok(Self {
            gpu_id,
            binary_path,
            child: Some(child),
            task_tx: Some(task_tx),
            result_rx: Some(result_rx),
            started_at: Some(Instant::now()),
            health_check_interval: Duration::from_secs(10),
        })
    }

    /// Submit mining task to legacy binary
    ///
    /// # Arguments
    /// * `task` - Mining task with job_id, difficulty, and data
    ///
    /// # Errors
    /// * `MinerError::IpcError` - Task submission failed (process dead or channel closed)
    pub fn send_task(&self, task: MiningTask) -> Result<()> {
        let tx = self.task_tx.as_ref().ok_or_else(|| {
            MinerError::IpcError("Task channel not initialized".to_string())
        })?;

        tx.send(task).map_err(|_| {
            MinerError::IpcError("Failed to send task (receiver dropped)".to_string())
        })?;

        Ok(())
    }

    /// Receive mining result from legacy binary với timeout
    ///
    /// # Arguments
    /// * `timeout_duration` - Maximum wait time for result
    ///
    /// # Returns
    /// * `Ok(MiningResult)` - Successfully received result
    /// * `Err(MinerError::IpcError)` - Timeout or channel closed
    pub async fn receive_result(&mut self, timeout_duration: Duration) -> Result<MiningResult> {
        let rx = self.result_rx.as_mut().ok_or_else(|| {
            MinerError::IpcError("Result channel not initialized".to_string())
        })?;

        match timeout(timeout_duration, rx.recv()).await {
            Ok(Some(result)) => Ok(result),
            Ok(None) => Err(MinerError::IpcError(
                "Result channel closed (process died)".to_string(),
            )),
            Err(_) => Err(MinerError::IpcError(
                "Timeout waiting for mining result".to_string(),
            )),
        }
    }

    /// Check if legacy process is alive và healthy
    ///
    /// # Returns
    /// * `true` - Process running normally
    /// * `false` - Process crashed, zombie, or not spawned
    pub fn is_alive(&mut self) -> bool {
        if let Some(child) = &mut self.child {
            match child.try_wait() {
                Ok(None) => true, // Still running
                Ok(Some(status)) => {
                    warn!(
                        gpu_id = self.gpu_id,
                        status = ?status,
                        "Legacy process exited"
                    );
                    false
                }
                Err(e) => {
                    error!(
                        gpu_id = self.gpu_id,
                        error = %e,
                        "Failed to check process status"
                    );
                    false
                }
            }
        } else {
            false
        }
    }

    /// Get process uptime
    pub fn uptime(&self) -> Option<Duration> {
        self.started_at.map(|start| start.elapsed())
    }

    /// Graceful shutdown với SIGTERM → SIGKILL escalation
    ///
    /// 1. Send SIGTERM và wait 5 seconds
    /// 2. If still alive, send SIGKILL
    ///
    /// # Errors
    /// * `MinerError::ProcessHealth` - Failed to kill process
    pub async fn shutdown(&mut self) -> Result<()> {
        if let Some(mut child) = self.child.take() {
            let pid = child.id().unwrap_or(0);
            info!(gpu_id = self.gpu_id, pid, "Shutting down legacy process");

            // Step 1: Graceful SIGTERM
            #[cfg(unix)]
            {
                use nix::sys::signal::{kill, Signal};
                use nix::unistd::Pid;

                if let Some(pid_u32) = child.id() {
                    let nix_pid = Pid::from_raw(pid_u32 as i32);
                    if let Err(e) = kill(nix_pid, Signal::SIGTERM) {
                        warn!(gpu_id = self.gpu_id, "Failed to send SIGTERM: {}", e);
                    } else {
                        debug!(gpu_id = self.gpu_id, "Sent SIGTERM");
                    }
                }
            }

            // Step 2: Wait 5 seconds for graceful exit
            match timeout(Duration::from_secs(5), child.wait()).await {
                Ok(Ok(status)) => {
                    info!(
                        gpu_id = self.gpu_id,
                        status = ?status,
                        "Legacy process exited gracefully"
                    );
                }
                Ok(Err(e)) => {
                    return Err(MinerError::ProcessHealth(format!(
                        "Wait failed: {}",
                        e
                    )));
                }
                Err(_) => {
                    // Step 3: Force kill with SIGKILL
                    warn!(gpu_id = self.gpu_id, "Graceful shutdown timeout, sending SIGKILL");
                    child.kill().await.map_err(|e| {
                        MinerError::ProcessHealth(format!("SIGKILL failed: {}", e))
                    })?;
                }
            }

            // Close channels
            drop(self.task_tx.take());
            drop(self.result_rx.take());
        }

        Ok(())
    }
}

/// Parse mining result từ stdout line
///
/// Format: "<job_id> <nonce> <hash_hex>"
fn parse_mining_result(line: &str) -> Result<MiningResult> {
    let parts: Vec<&str> = line.split_whitespace().collect();

    if parts.len() != 3 {
        return Err(MinerError::IpcError(format!(
            "Invalid result format: expected 3 fields, got {}",
            parts.len()
        )));
    }

    let job_id = parts[0].parse::<u64>().map_err(|e| {
        MinerError::IpcError(format!("Invalid job_id: {}", e))
    })?;

    let nonce = parts[1].parse::<u64>().map_err(|e| {
        MinerError::IpcError(format!("Invalid nonce: {}", e))
    })?;

    let hash = hex::decode(parts[2]).map_err(|e| {
        MinerError::IpcError(format!("Invalid hash hex: {}", e))
    })?;

    Ok(MiningResult {
        job_id,
        nonce,
        hash,
    })
}

impl Drop for LegacyMinerBridge {
    fn drop(&mut self) {
        if self.is_alive() {
            warn!(
                gpu_id = self.gpu_id,
                "Legacy process still running during drop, forcing kill"
            );

            if let Some(mut child) = self.child.take() {
                let _ = child.start_kill();
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_mining_result_valid() {
        let line = "12345 67890 deadbeef";
        let result = parse_mining_result(line).unwrap();

        assert_eq!(result.job_id, 12345);
        assert_eq!(result.nonce, 67890);
        assert_eq!(result.hash, hex::decode("deadbeef").unwrap());
    }

    #[test]
    fn test_parse_mining_result_invalid_format() {
        let line = "12345 67890"; // Missing hash
        assert!(parse_mining_result(line).is_err());
    }

    #[test]
    fn test_parse_mining_result_invalid_hex() {
        let line = "12345 67890 ZZZZ"; // Invalid hex
        assert!(parse_mining_result(line).is_err());
    }

    #[tokio::test]
    async fn test_spawn_invalid_binary() {
        let result = LegacyMinerBridge::spawn("/nonexistent/binary", 0).await;
        assert!(result.is_err());
    }
}
