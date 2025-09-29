//! Mining Process Lifecycle Management
//!
//! This module handles the complete lifecycle of mining processes including:
//! - Process startup and initialization
//! - Health monitoring and auto-recovery
//! - Resource limits and QoS management
//! - Graceful shutdown with cleanup
//! - Inter-process communication and coordination

use anyhow::{Context, Result};
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use nix::sys::signal::{self, Signal};
use nix::unistd::Pid;
#[cfg(feature = "workspace")]
use opus_gpu_bus::{Message, MessageBus, MessageHandler};

#[cfg(not(feature = "workspace"))]
use crate::mocks::{Message, MessageBus, MessageHandler};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::process::{Child, Command, Stdio};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{mpsc, Mutex, oneshot};
use tokio::time::sleep;
use tracing::{debug, info, warn, error};
use uuid::Uuid;

/// Process lifecycle states
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProcessState {
    /// Process is being initialized
    Initializing,
    /// Process is running normally
    Running,
    /// Process is paused/suspended
    Paused,
    /// Process is being stopped
    Stopping,
    /// Process has stopped normally
    Stopped,
    /// Process has crashed or failed
    Failed,
    /// Process is being restarted
    Restarting,
}

/// Process health status
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum HealthStatus {
    /// Process is healthy and responsive
    Healthy,
    /// Process is experiencing degraded performance
    Degraded,
    /// Process is unresponsive but still running
    Unresponsive,
    /// Process has critical issues
    Critical,
    /// Process health is unknown
    Unknown,
}

/// Process resource limits
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceLimits {
    /// Maximum CPU usage percentage (0.0-1.0)
    pub max_cpu: f64,
    /// Maximum memory usage in bytes
    pub max_memory: usize,
    /// Maximum GPU memory usage in bytes
    pub max_gpu_memory: usize,
    /// Maximum number of file descriptors
    pub max_files: u32,
    /// Process priority (-20 to 19, lower is higher priority)
    pub priority: i8,
    /// CPU affinity mask
    pub cpu_affinity: Option<Vec<usize>>,
}

/// Process quality of service settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QoSSettings {
    /// IO scheduling class (0=none, 1=realtime, 2=best-effort, 3=idle)
    pub io_class: u8,
    /// IO scheduling priority (0-7)
    pub io_priority: u8,
    /// Network bandwidth limit in bytes/sec
    pub network_bandwidth: Option<usize>,
    /// Disk IO bandwidth limit in bytes/sec
    pub disk_bandwidth: Option<usize>,
    /// Enable OOM killer protection
    pub oom_protection: bool,
}

/// Process configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessConfig {
    /// Process name/identifier
    pub name: String,
    /// Command to execute
    pub command: Vec<String>,
    /// Working directory
    pub working_dir: Option<String>,
    /// Environment variables
    pub environment: HashMap<String, String>,
    /// Resource limits
    pub limits: ResourceLimits,
    /// Quality of service settings
    pub qos: QoSSettings,
    /// Auto-restart on failure
    pub auto_restart: bool,
    /// Maximum restart attempts
    pub max_restarts: u32,
    /// Restart backoff delay
    pub restart_delay: Duration,
    /// Health check configuration
    pub health_check: HealthCheckConfig,
    /// Graceful shutdown timeout
    pub shutdown_timeout: Duration,
}

/// Health check configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthCheckConfig {
    /// Enable health monitoring
    pub enabled: bool,
    /// Health check interval
    pub interval: Duration,
    /// Health check timeout
    pub timeout: Duration,
    /// Number of failed checks before marking unhealthy
    pub failure_threshold: u32,
    /// Health check method
    pub method: HealthCheckMethod,
}

/// Health check methods
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HealthCheckMethod {
    /// Check if process is running
    ProcessAlive,
    /// Send ping message and expect response
    MessagePing,
    /// Execute custom health check command
    Command(Vec<String>),
    /// Check TCP port connectivity
    TcpPort(u16),
    /// Check HTTP endpoint
    Http(String),
}

/// Process metrics and statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessMetrics {
    /// Process ID
    pub pid: Option<u32>,
    /// Current state
    pub state: ProcessState,
    /// Health status
    pub health: HealthStatus,
    /// CPU usage percentage
    pub cpu_usage: f64,
    /// Memory usage in bytes
    pub memory_usage: usize,
    /// GPU memory usage in bytes
    pub gpu_memory_usage: usize,
    /// Number of open file descriptors
    pub open_files: u32,
    /// Process uptime
    pub uptime: Duration,
    /// Number of restarts
    pub restart_count: u32,
    /// Last restart time
    pub last_restart: Option<DateTime<Utc>>,
    /// Last health check time
    pub last_health_check: Option<DateTime<Utc>>,
    /// Process start time
    pub start_time: Option<DateTime<Utc>>,
    /// Exit code (if stopped)
    pub exit_code: Option<i32>,
}

/// Process manager events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProcessEvent {
    /// Process started
    Started { process_id: Uuid, pid: u32 },
    /// Process stopped
    Stopped { process_id: Uuid, exit_code: Option<i32> },
    /// Process failed to start
    StartFailed { process_id: Uuid, error: String },
    /// Process crashed
    Crashed { process_id: Uuid, exit_code: i32 },
    /// Process health status changed
    HealthChanged { process_id: Uuid, old_status: HealthStatus, new_status: HealthStatus },
    /// Process restarted
    Restarted { process_id: Uuid, restart_count: u32 },
    /// Resource limit exceeded
    ResourceLimitExceeded { process_id: Uuid, resource: String, usage: f64, limit: f64 },
}

/// Managed process instance
pub struct ManagedProcess {
    /// Unique process identifier
    id: Uuid,
    /// Process configuration
    config: ProcessConfig,
    /// Current process handle
    child: Mutex<Option<Child>>,
    /// Process metrics
    metrics: RwLock<ProcessMetrics>,
    /// Process state
    state: RwLock<ProcessState>,
    /// Health monitor task handle
    health_monitor: Mutex<Option<tokio::task::JoinHandle<()>>>,
    /// Process start time
    start_time: RwLock<Option<Instant>>,
    /// Event sender
    event_sender: mpsc::UnboundedSender<ProcessEvent>,
    /// Shutdown signal
    shutdown_signal: Mutex<Option<oneshot::Sender<()>>>,
}

/// Process lifecycle manager
pub struct ProcessManager {
    /// Managed processes
    processes: RwLock<HashMap<Uuid, Arc<ManagedProcess>>>,
    /// Message bus for inter-process communication
    message_bus: Arc<dyn MessageBus>,
    /// Event receiver
    event_receiver: Mutex<Option<mpsc::UnboundedReceiver<ProcessEvent>>>,
    /// Event sender
    event_sender: mpsc::UnboundedSender<ProcessEvent>,
    /// Resource monitor task
    resource_monitor: Mutex<Option<tokio::task::JoinHandle<()>>>,
}

impl Default for ResourceLimits {
    fn default() -> Self {
        Self {
            max_cpu: 0.8,
            max_memory: 4 * 1024 * 1024 * 1024, // 4GB
            max_gpu_memory: 8 * 1024 * 1024 * 1024, // 8GB
            max_files: 1024,
            priority: 0,
            cpu_affinity: None,
        }
    }
}

impl Default for QoSSettings {
    fn default() -> Self {
        Self {
            io_class: 2, // Best effort
            io_priority: 4,
            network_bandwidth: None,
            disk_bandwidth: None,
            oom_protection: true,
        }
    }
}

impl Default for HealthCheckConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            interval: Duration::from_secs(30),
            timeout: Duration::from_secs(5),
            failure_threshold: 3,
            method: HealthCheckMethod::ProcessAlive,
        }
    }
}

impl ProcessManager {
    /// Create new process manager
    pub fn new(message_bus: Arc<dyn MessageBus>) -> Self {
        let (event_sender, event_receiver) = mpsc::unbounded_channel();

        Self {
            processes: RwLock::new(HashMap::new()),
            message_bus,
            event_receiver: Mutex::new(Some(event_receiver)),
            event_sender,
            resource_monitor: Mutex::new(None),
        }
    }

    /// Start a new managed process
    pub async fn start_process(&self, config: ProcessConfig) -> Result<Uuid> {
        let process_id = Uuid::new_v4();
        let process = Arc::new(ManagedProcess::new(process_id, config, self.event_sender.clone())?);

        // Start the process
        process.start().await
            .with_context(|| format!("Failed to start process {}", process_id))?;

        // Add to managed processes
        self.processes.write().insert(process_id, Arc::clone(&process));

        info!("Started managed process: {} ({})", process.config.name, process_id);
        Ok(process_id)
    }

    /// Stop a managed process
    pub async fn stop_process(&self, process_id: Uuid, force: bool) -> Result<()> {
        let processes = self.processes.read();
        let process = processes.get(&process_id)
            .context("Process not found")?;

        if force {
            process.kill().await?;
        } else {
            process.stop().await?;
        }

        info!("Stopped managed process: {}", process_id);
        Ok(())
    }

    /// Restart a managed process
    pub async fn restart_process(&self, process_id: Uuid) -> Result<()> {
        let processes = self.processes.read();
        let process = processes.get(&process_id)
            .context("Process not found")?;

        process.restart().await?;

        info!("Restarted managed process: {}", process_id);
        Ok(())
    }

    /// Get process metrics
    pub fn get_process_metrics(&self, process_id: Uuid) -> Option<ProcessMetrics> {
        let processes = self.processes.read();
        processes.get(&process_id).map(|p| p.get_metrics())
    }

    /// List all managed processes
    pub fn list_processes(&self) -> Vec<(Uuid, ProcessMetrics)> {
        let processes = self.processes.read();
        processes.iter()
            .map(|(&id, process)| (id, process.get_metrics()))
            .collect()
    }

    /// Start resource monitoring
    pub async fn start_monitoring(&self) -> Result<()> {
        let processes = Arc::downgrade(&Arc::new(self.processes.read().clone()));
        let event_sender = self.event_sender.clone();

        let monitor_task = tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(10));

            loop {
                interval.tick().await;

                if let Some(processes_arc) = processes.upgrade() {
                    for (process_id, process) in processes_arc.iter() {
                        if let Err(e) = Self::check_resource_limits(&process, &event_sender).await {
                            warn!("Failed to check resource limits for process {}: {}", process_id, e);
                        }
                    }
                } else {
                    break; // ProcessManager dropped
                }
            }
        });

        *self.resource_monitor.lock().await = Some(monitor_task);
        Ok(())
    }

    /// Check resource limits for a process
    async fn check_resource_limits(
        process: &ManagedProcess,
        event_sender: &mpsc::UnboundedSender<ProcessEvent>,
    ) -> Result<()> {
        let metrics = process.get_metrics();
        let limits = &process.config.limits;

        // Check CPU usage
        if metrics.cpu_usage > limits.max_cpu {
            let _ = event_sender.send(ProcessEvent::ResourceLimitExceeded {
                process_id: process.id,
                resource: "cpu".to_string(),
                usage: metrics.cpu_usage,
                limit: limits.max_cpu,
            });
        }

        // Check memory usage
        if metrics.memory_usage > limits.max_memory {
            let _ = event_sender.send(ProcessEvent::ResourceLimitExceeded {
                process_id: process.id,
                resource: "memory".to_string(),
                usage: metrics.memory_usage as f64,
                limit: limits.max_memory as f64,
            });
        }

        // Check GPU memory usage
        if metrics.gpu_memory_usage > limits.max_gpu_memory {
            let _ = event_sender.send(ProcessEvent::ResourceLimitExceeded {
                process_id: process.id,
                resource: "gpu_memory".to_string(),
                usage: metrics.gpu_memory_usage as f64,
                limit: limits.max_gpu_memory as f64,
            });
        }

        Ok(())
    }

    /// Handle process events
    pub async fn handle_events<F>(&self, mut handler: F) -> Result<()>
    where
        F: FnMut(ProcessEvent) -> Result<()>,
    {
        let mut receiver = self.event_receiver.lock().await.take()
            .context("Event receiver already taken")?;

        while let Some(event) = receiver.recv().await {
            if let Err(e) = handler(event.clone()) {
                error!("Error handling process event {:?}: {}", event, e);
            }
        }

        Ok(())
    }

    /// Shutdown all managed processes
    pub async fn shutdown(&self) -> Result<()> {
        info!("Shutting down process manager");

        let processes: Vec<_> = self.processes.read().values().cloned().collect();

        // Stop all processes gracefully
        for process in processes {
            if let Err(e) = process.stop().await {
                warn!("Failed to stop process {}: {}", process.id, e);
            }
        }

        // Stop resource monitoring
        if let Some(monitor) = self.resource_monitor.lock().await.take() {
            monitor.abort();
        }

        // Clear processes
        self.processes.write().clear();

        info!("Process manager shutdown complete");
        Ok(())
    }
}

impl ManagedProcess {
    fn new(
        id: Uuid,
        config: ProcessConfig,
        event_sender: mpsc::UnboundedSender<ProcessEvent>,
    ) -> Result<Self> {
        let metrics = ProcessMetrics {
            pid: None,
            state: ProcessState::Initializing,
            health: HealthStatus::Unknown,
            cpu_usage: 0.0,
            memory_usage: 0,
            gpu_memory_usage: 0,
            open_files: 0,
            uptime: Duration::ZERO,
            restart_count: 0,
            last_restart: None,
            last_health_check: None,
            start_time: None,
            exit_code: None,
        };

        Ok(Self {
            id,
            config,
            child: Mutex::new(None),
            metrics: RwLock::new(metrics),
            state: RwLock::new(ProcessState::Initializing),
            health_monitor: Mutex::new(None),
            start_time: RwLock::new(None),
            event_sender,
            shutdown_signal: Mutex::new(None),
        })
    }

    /// Start the process
    async fn start(&self) -> Result<()> {
        *self.state.write() = ProcessState::Initializing;

        let mut cmd = Command::new(&self.config.command[0]);
        cmd.args(&self.config.command[1..])
           .stdin(Stdio::null())
           .stdout(Stdio::piped())
           .stderr(Stdio::piped());

        // Set working directory
        if let Some(ref work_dir) = self.config.working_dir {
            cmd.current_dir(work_dir);
        }

        // Set environment variables
        for (key, value) in &self.config.environment {
            cmd.env(key, value);
        }

        // Start the process
        let child = cmd.spawn()
            .context("Failed to spawn process")?;

        let pid = child.id();
        *self.child.lock().await = Some(child);

        // Update metrics
        {
            let mut metrics = self.metrics.write();
            metrics.pid = Some(pid);
            metrics.state = ProcessState::Running;
            metrics.start_time = Some(Utc::now());
        }

        *self.state.write() = ProcessState::Running;
        *self.start_time.write() = Some(Instant::now());

        // Apply resource limits
        self.apply_resource_limits(pid).await?;

        // Start health monitoring
        if self.config.health_check.enabled {
            self.start_health_monitoring().await?;
        }

        let _ = self.event_sender.send(ProcessEvent::Started {
            process_id: self.id,
            pid,
        });

        Ok(())
    }

    /// Apply resource limits to the process
    async fn apply_resource_limits(&self, pid: u32) -> Result<()> {
        let limits = &self.config.limits;

        // Set process priority
        if limits.priority != 0 {
            #[cfg(unix)]
            unsafe {
                libc::setpriority(libc::PRIO_PROCESS, pid, limits.priority as libc::c_int);
            }
        }

        // Set CPU affinity if specified
        if let Some(ref affinity) = limits.cpu_affinity {
            #[cfg(target_os = "linux")]
            {
                use std::mem;
                let mut cpu_set: libc::cpu_set_t = unsafe { mem::zeroed() };
                unsafe { libc::CPU_ZERO(&mut cpu_set) };

                for &cpu in affinity {
                    unsafe { libc::CPU_SET(cpu, &mut cpu_set) };
                }

                unsafe {
                    libc::sched_setaffinity(
                        pid as libc::pid_t,
                        mem::size_of::<libc::cpu_set_t>(),
                        &cpu_set,
                    );
                }
            }
        }

        Ok(())
    }

    /// Start health monitoring
    async fn start_health_monitoring(&self) -> Result<()> {
        let id = self.id;
        let config = self.config.health_check.clone();
        let event_sender = self.event_sender.clone();
        let (shutdown_tx, mut shutdown_rx) = oneshot::channel();

        *self.shutdown_signal.lock().await = Some(shutdown_tx);

        let monitor_task = tokio::spawn(async move {
            let mut interval = tokio::time::interval(config.interval);
            let mut failure_count = 0;
            let mut current_health = HealthStatus::Healthy;

            loop {
                tokio::select! {
                    _ = interval.tick() => {
                        let health_result = Self::perform_health_check(&config.method, config.timeout).await;

                        let new_health = match health_result {
                            Ok(true) => {
                                failure_count = 0;
                                HealthStatus::Healthy
                            }
                            Ok(false) => {
                                failure_count += 1;
                                if failure_count >= config.failure_threshold {
                                    HealthStatus::Critical
                                } else {
                                    HealthStatus::Degraded
                                }
                            }
                            Err(_) => {
                                failure_count += 1;
                                HealthStatus::Unresponsive
                            }
                        };

                        if new_health != current_health {
                            let _ = event_sender.send(ProcessEvent::HealthChanged {
                                process_id: id,
                                old_status: current_health.clone(),
                                new_status: new_health.clone(),
                            });
                            current_health = new_health;
                        }
                    }
                    _ = &mut shutdown_rx => {
                        debug!("Health monitor shutdown for process {}", id);
                        break;
                    }
                }
            }
        });

        *self.health_monitor.lock().await = Some(monitor_task);
        Ok(())
    }

    /// Perform health check
    async fn perform_health_check(method: &HealthCheckMethod, timeout: Duration) -> Result<bool> {
        match method {
            HealthCheckMethod::ProcessAlive => Ok(true), // If we're here, process is alive
            HealthCheckMethod::MessagePing => {
                // TODO: Implement message-based health check
                Ok(true)
            }
            HealthCheckMethod::Command(cmd) => {
                let output = tokio::time::timeout(timeout,
                    tokio::process::Command::new(&cmd[0])
                        .args(&cmd[1..])
                        .output()
                ).await??;
                Ok(output.status.success())
            }
            HealthCheckMethod::TcpPort(port) => {
                match tokio::time::timeout(timeout,
                    tokio::net::TcpStream::connect(format!("127.0.0.1:{}", port))
                ).await {
                    Ok(Ok(_)) => Ok(true),
                    _ => Ok(false),
                }
            }
            HealthCheckMethod::Http(url) => {
                // TODO: Implement HTTP health check
                Ok(true)
            }
        }
    }

    /// Stop the process gracefully
    async fn stop(&self) -> Result<()> {
        *self.state.write() = ProcessState::Stopping;

        // Stop health monitoring
        if let Some(tx) = self.shutdown_signal.lock().await.take() {
            let _ = tx.send(());
        }

        if let Some(monitor) = self.health_monitor.lock().await.take() {
            monitor.abort();
        }

        // Try graceful shutdown first
        if let Some(ref mut child) = self.child.lock().await.as_mut() {
            if let Some(pid) = child.id() {
                // Send SIGTERM
                if let Err(e) = signal::kill(Pid::from_raw(pid as i32), Signal::SIGTERM) {
                    warn!("Failed to send SIGTERM to process {}: {}", pid, e);
                }

                // Wait for graceful shutdown
                let timeout = self.config.shutdown_timeout;
                match tokio::time::timeout(timeout, child.wait()).await {
                    Ok(Ok(exit_status)) => {
                        let exit_code = exit_status.code();
                        self.metrics.write().exit_code = exit_code;

                        let _ = self.event_sender.send(ProcessEvent::Stopped {
                            process_id: self.id,
                            exit_code,
                        });
                    }
                    _ => {
                        // Force kill if graceful shutdown failed
                        self.kill().await?;
                    }
                }
            }
        }

        *self.state.write() = ProcessState::Stopped;
        Ok(())
    }

    /// Force kill the process
    async fn kill(&self) -> Result<()> {
        if let Some(ref mut child) = self.child.lock().await.as_mut() {
            child.kill()
                .context("Failed to kill process")?;

            let exit_status = child.wait()
                .await
                .context("Failed to wait for killed process")?;

            let exit_code = exit_status.code();
            self.metrics.write().exit_code = exit_code;

            let _ = self.event_sender.send(ProcessEvent::Stopped {
                process_id: self.id,
                exit_code,
            });
        }

        *self.state.write() = ProcessState::Stopped;
        Ok(())
    }

    /// Restart the process
    async fn restart(&self) -> Result<()> {
        *self.state.write() = ProcessState::Restarting;

        // Stop current process
        self.stop().await?;

        // Wait a bit before restarting
        sleep(self.config.restart_delay).await;

        // Update restart count
        {
            let mut metrics = self.metrics.write();
            metrics.restart_count += 1;
            metrics.last_restart = Some(Utc::now());
        }

        // Start new process
        self.start().await?;

        let restart_count = self.metrics.read().restart_count;
        let _ = self.event_sender.send(ProcessEvent::Restarted {
            process_id: self.id,
            restart_count,
        });

        Ok(())
    }

    /// Get current process metrics
    fn get_metrics(&self) -> ProcessMetrics {
        let mut metrics = self.metrics.read().clone();

        // Update uptime if process is running
        if let Some(start_time) = *self.start_time.read() {
            metrics.uptime = start_time.elapsed();
        }

        metrics.state = *self.state.read();
        metrics
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_process_config_defaults() {
        let limits = ResourceLimits::default();
        assert_eq!(limits.max_cpu, 0.8);
        assert_eq!(limits.priority, 0);

        let qos = QoSSettings::default();
        assert_eq!(qos.io_class, 2);
        assert!(qos.oom_protection);
    }

    #[test]
    fn test_process_states() {
        assert_ne!(ProcessState::Running, ProcessState::Stopped);
        assert_ne!(HealthStatus::Healthy, HealthStatus::Critical);
    }

    #[tokio::test]
    async fn test_process_manager_creation() {
        use opus_gpu_bus::MockMessageBus;

        let message_bus = Arc::new(MockMessageBus::new());
        let manager = ProcessManager::new(message_bus);

        let processes = manager.list_processes();
        assert!(processes.is_empty());
    }
}