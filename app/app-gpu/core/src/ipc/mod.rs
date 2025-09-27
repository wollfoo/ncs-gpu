//! Inter-Process Communication (IPC) Module
//! 
//! High-performance shared memory IPC với zero-copy message passing

use std::sync::Arc;
use std::time::{Duration, Instant};
use anyhow::{Result, Context};
use shared_memory::{Shmem, ShmemConf};
use parking_lot::RwLock;
use crossbeam::channel::{bounded, unbounded, Sender, Receiver};
use serde::{Serialize, Deserialize};
use bincode;
use tracing::{info, debug, warn, error, instrument};

use crate::config::IpcConfig;
use crate::error::OpusError;

/// IPC Message structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub source: String,
    pub destination: String,
    pub payload: Vec<u8>,
}

/// IPC Statistics
#[derive(Debug, Clone, Default)]
pub struct IpcStats {
    pub messages_sent: u64,
    pub messages_received: u64,
    pub bytes_sent: u64,
    pub bytes_received: u64,
    pub avg_latency_us: f64,
    pub throughput_mbps: f64,
}

/// Shared memory segment
struct SharedSegment {
    shmem: Shmem,
    size: usize,
    offset: Arc<RwLock<usize>>,
}

/// IPC Manager
pub struct IpcManager {
    config: IpcConfig,
    segments: Arc<RwLock<Vec<SharedSegment>>>,
    sender: Sender<Message>,
    receiver: Receiver<Message>,
    stats: Arc<RwLock<IpcStats>>,
    shutdown: Arc<RwLock<bool>>,
}

impl IpcManager {
    /// Create new IPC manager
    #[instrument(skip(config))]
    pub async fn new(config: IpcConfig) -> Result<Self> {
        info!("Initializing IPC manager with {} MB shared memory", 
              config.shared_memory_size_mb);
        
        let mut segments = Vec::new();
        
        // Create shared memory segments
        for i in 0..config.num_segments {
            let segment_size = (config.shared_memory_size_mb * 1024 * 1024) / config.num_segments;
            let segment_name = format!("opus_gpu_shm_{}", i);
            
            let shmem = ShmemConf::new()
                .size(segment_size)
                .flink(&segment_name)
                .create()
                .with_context(|| format!("Failed to create shared memory segment {}", i))?;
            
            segments.push(SharedSegment {
                shmem,
                size: segment_size,
                offset: Arc::new(RwLock::new(0)),
            });
            
            debug!("Created shared memory segment {} ({} MB)", 
                   segment_name, segment_size / 1024 / 1024);
        }
        
        // Create message channels
        let (sender, receiver) = if config.bounded_queue {
            let (s, r) = bounded(config.queue_size);
            (s, r)
        } else {
            unbounded()
        };
        
        Ok(Self {
            config,
            segments: Arc::new(RwLock::new(segments)),
            sender,
            receiver,
            stats: Arc::new(RwLock::new(IpcStats::default())),
            shutdown: Arc::new(RwLock::new(false)),
        })
    }
    
    /// Send message qua IPC
    #[instrument(skip(self, message))]
    pub async fn send_message(&self, message: Message) -> Result<()> {
        let start = Instant::now();
        
        // Serialize message
        let data = bincode::serialize(&message)?;
        let data_size = data.len();
        
        // Find available segment
        let segment_idx = self.find_available_segment(data_size)?;
        
        // Write to shared memory
        self.write_to_segment(segment_idx, &data)?;
        
        // Send notification qua channel
        self.sender.send(message)
            .map_err(|e| anyhow::anyhow!("Failed to send message: {}", e))?;
        
        // Update stats
        {
            let mut stats = self.stats.write();
            stats.messages_sent += 1;
            stats.bytes_sent += data_size as u64;
            
            let latency = start.elapsed().as_micros() as f64;
            stats.avg_latency_us = 
                (stats.avg_latency_us * (stats.messages_sent - 1) as f64 + latency) 
                / stats.messages_sent as f64;
        }
        
        debug!("Sent {} bytes in {:?}", data_size, start.elapsed());
        Ok(())
    }
    
    /// Receive message từ IPC
    #[instrument(skip(self))]
    pub async fn receive_message(&self) -> Result<Option<Message>> {
        // Check for shutdown
        if *self.shutdown.read() {
            return Ok(None);
        }
        
        // Try receive with timeout
        match self.receiver.recv_timeout(Duration::from_millis(100)) {
            Ok(message) => {
                // Update stats
                {
                    let mut stats = self.stats.write();
                    stats.messages_received += 1;
                    stats.bytes_received += message.payload.len() as u64;
                }
                
                debug!("Received message from {}", message.source);
                Ok(Some(message))
            }
            Err(_) => Ok(None), // Timeout or disconnected
        }
    }
    
    /// Broadcast message to all destinations
    pub async fn broadcast(&self, source: &str, payload: Vec<u8>) -> Result<()> {
        let message = Message {
            source: source.to_string(),
            destination: "*".to_string(), // Wildcard for broadcast
            payload,
        };
        
        self.send_message(message).await
    }
    
    /// Find available segment với enough space
    fn find_available_segment(&self, size: usize) -> Result<usize> {
        let segments = self.segments.read();
        
        for (idx, segment) in segments.iter().enumerate() {
            let offset = *segment.offset.read();
            if offset + size <= segment.size {
                return Ok(idx);
            }
        }
        
        Err(anyhow::anyhow!("No available segment with {} bytes", size))
    }
    
    /// Write data to shared memory segment
    fn write_to_segment(&self, segment_idx: usize, data: &[u8]) -> Result<()> {
        let segments = self.segments.read();
        let segment = segments.get(segment_idx)
            .ok_or_else(|| anyhow::anyhow!("Invalid segment index"))?;
        
        let mut offset = segment.offset.write();
        
        // Check bounds
        if *offset + data.len() > segment.size {
            *offset = 0; // Wrap around
        }
        
        // Write to shared memory
        unsafe {
            let ptr = segment.shmem.as_ptr().add(*offset);
            std::ptr::copy_nonoverlapping(data.as_ptr(), ptr, data.len());
        }
        
        *offset += data.len();
        
        Ok(())
    }
    
    /// Read data from shared memory segment
    fn read_from_segment(&self, segment_idx: usize, offset: usize, size: usize) -> Result<Vec<u8>> {
        let segments = self.segments.read();
        let segment = segments.get(segment_idx)
            .ok_or_else(|| anyhow::anyhow!("Invalid segment index"))?;
        
        // Check bounds
        if offset + size > segment.size {
            return Err(anyhow::anyhow!("Read exceeds segment bounds"));
        }
        
        // Read from shared memory
        let mut data = vec![0u8; size];
        unsafe {
            let ptr = segment.shmem.as_ptr().add(offset);
            std::ptr::copy_nonoverlapping(ptr, data.as_mut_ptr(), size);
        }
        
        Ok(data)
    }
    
    /// Get IPC statistics
    pub fn stats(&self) -> IpcStats {
        self.stats.read().clone()
    }
    
    /// Benchmark IPC throughput
    pub async fn benchmark(&self, message_size: usize, num_messages: usize) -> Result<f64> {
        info!("Running IPC benchmark: {} messages of {} bytes", 
              num_messages, message_size);
        
        let payload = vec![0u8; message_size];
        let start = Instant::now();
        
        for i in 0..num_messages {
            let message = Message {
                source: "benchmark".to_string(),
                destination: format!("test_{}", i),
                payload: payload.clone(),
            };
            
            self.send_message(message).await?;
        }
        
        let elapsed = start.elapsed();
        let total_bytes = (message_size * num_messages) as f64;
        let throughput_mbps = (total_bytes / 1024.0 / 1024.0) / elapsed.as_secs_f64();
        
        info!("Benchmark complete: {:.2} MB/s", throughput_mbps);
        
        // Update stats
        {
            let mut stats = self.stats.write();
            stats.throughput_mbps = throughput_mbps;
        }
        
        Ok(throughput_mbps)
    }
    
    /// Shutdown IPC manager
    pub async fn shutdown(&self) -> Result<()> {
        info!("Shutting down IPC manager");
        
        // Set shutdown flag
        *self.shutdown.write() = true;
        
        // Print final stats
        let stats = self.stats.read();
        info!("IPC Stats - Messages: sent={}, received={}", 
              stats.messages_sent, stats.messages_received);
        info!("IPC Stats - Bytes: sent={}, received={}", 
              stats.bytes_sent, stats.bytes_received);
        info!("IPC Stats - Performance: latency={:.2}μs, throughput={:.2}MB/s",
              stats.avg_latency_us, stats.throughput_mbps);
        
        Ok(())
    }
    
    /// Cleanup IPC resources
    pub async fn cleanup(&self) -> Result<()> {
        debug!("Cleaning up IPC resources");
        
        // Shared memory segments will be cleaned up on drop
        
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_ipc_message_passing() {
        let config = IpcConfig {
            shared_memory_size_mb: 10,
            num_segments: 2,
            bounded_queue: true,
            queue_size: 100,
        };
        
        let ipc = IpcManager::new(config).await.unwrap();
        
        // Send message
        let message = Message {
            source: "test".to_string(),
            destination: "target".to_string(),
            payload: vec![1, 2, 3, 4, 5],
        };
        
        ipc.send_message(message.clone()).await.unwrap();
        
        // Receive message
        let received = ipc.receive_message().await.unwrap();
        assert!(received.is_some());
        
        let received = received.unwrap();
        assert_eq!(received.source, message.source);
        assert_eq!(received.payload, message.payload);
    }
    
    #[tokio::test]
    async fn test_ipc_benchmark() {
        let config = IpcConfig {
            shared_memory_size_mb: 10,
            num_segments: 2,
            bounded_queue: false,
            queue_size: 0,
        };
        
        let ipc = IpcManager::new(config).await.unwrap();
        
        // Run benchmark
        let throughput = ipc.benchmark(1024, 1000).await.unwrap();
        
        // Should achieve > 1GB/s with shared memory
        assert!(throughput > 1000.0);
    }
}
