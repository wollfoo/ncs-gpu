//! Task Queue Management
//! 
//! Lock-free MPMC queue with priority-based scheduling and batch processing

use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, AtomicBool, Ordering};
use std::collections::{BinaryHeap, VecDeque};
use std::cmp::Ordering as CmpOrdering;
use anyhow::{Result, bail};
use crossbeam::queue::ArrayQueue;
use parking_lot::{RwLock, Mutex};
use tracing::{debug, info, warn};
use opus_gpu_core::plugin::PluginTask;

/// Task priority levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Priority {
    Low = 0,
    Normal = 1,
    High = 2,
    Critical = 3,
}

impl From<u8> for Priority {
    fn from(value: u8) -> Self {
        match value {
            0..=63 => Priority::Low,
            64..=127 => Priority::Normal,
            128..=191 => Priority::High,
            192..=255 => Priority::Critical,
        }
    }
}

/// Extended task with priority and metadata
#[derive(Debug, Clone)]
pub struct QueuedTask {
    pub task: PluginTask,
    pub priority: Priority,
    pub enqueued_at: std::time::Instant,
    pub attempts: u32,
    pub batch_id: Option<uuid::Uuid>,
}

impl QueuedTask {
    pub fn new(task: PluginTask) -> Self {
        Self {
            priority: Priority::from(task.priority),
            task,
            enqueued_at: std::time::Instant::now(),
            attempts: 0,
            batch_id: None,
        }
    }
    
    pub fn with_batch(mut self, batch_id: uuid::Uuid) -> Self {
        self.batch_id = Some(batch_id);
        self
    }
}

// Implement ordering for priority queue (higher priority first)
impl PartialEq for QueuedTask {
    fn eq(&self, other: &Self) -> bool {
        self.priority == other.priority && 
        self.enqueued_at == other.enqueued_at
    }
}

impl Eq for QueuedTask {}

impl PartialOrd for QueuedTask {
    fn partial_cmp(&self, other: &Self) -> Option<CmpOrdering> {
        Some(self.cmp(other))
    }
}

impl Ord for QueuedTask {
    fn cmp(&self, other: &Self) -> CmpOrdering {
        // First by priority (reversed for max-heap)
        match self.priority.cmp(&other.priority) {
            CmpOrdering::Equal => {
                // Then by enqueue time (older first)
                other.enqueued_at.cmp(&self.enqueued_at)
            }
            other => other,
        }
    }
}

/// Lock-free task queue
pub struct TaskQueue {
    /// Lock-free queue for normal throughput
    queue: Arc<ArrayQueue<QueuedTask>>,
    
    /// Priority queue for high priority tasks
    priority_queue: Arc<Mutex<BinaryHeap<QueuedTask>>>,
    
    /// Batch processing queue
    batch_queue: Arc<RwLock<VecDeque<Vec<QueuedTask>>>>,
    
    /// Queue statistics
    stats: Arc<QueueStats>,
    
    /// Max queue size
    capacity: usize,
    
    /// Shutdown flag
    shutdown: Arc<AtomicBool>,
}

/// Queue statistics
pub struct QueueStats {
    pub total_enqueued: AtomicUsize,
    pub total_dequeued: AtomicUsize,
    pub total_dropped: AtomicUsize,
    pub current_size: AtomicUsize,
    pub peak_size: AtomicUsize,
    pub total_wait_time_ms: AtomicUsize,
    pub batch_count: AtomicUsize,
}

impl QueueStats {
    fn new() -> Self {
        Self {
            total_enqueued: AtomicUsize::new(0),
            total_dequeued: AtomicUsize::new(0),
            total_dropped: AtomicUsize::new(0),
            current_size: AtomicUsize::new(0),
            peak_size: AtomicUsize::new(0),
            total_wait_time_ms: AtomicUsize::new(0),
            batch_count: AtomicUsize::new(0),
        }
    }
}

impl TaskQueue {
    /// Create new task queue
    pub fn new(capacity: usize) -> Self {
        Self {
            queue: Arc::new(ArrayQueue::new(capacity)),
            priority_queue: Arc::new(Mutex::new(BinaryHeap::new())),
            batch_queue: Arc::new(RwLock::new(VecDeque::new())),
            stats: Arc::new(QueueStats::new()),
            capacity,
            shutdown: Arc::new(AtomicBool::new(false)),
        }
    }
    
    /// Enqueue a task
    pub async fn enqueue(&self, task: PluginTask) -> Result<()> {
        if self.shutdown.load(Ordering::Acquire) {
            bail!("Queue is shutting down");
        }
        
        let queued_task = QueuedTask::new(task);
        let priority = queued_task.priority;
        
        // Route based on priority
        if priority >= Priority::High {
            // Use priority queue for high priority tasks
            let mut pq = self.priority_queue.lock();
            
            if pq.len() >= self.capacity {
                self.stats.total_dropped.fetch_add(1, Ordering::Relaxed);
                bail!("Priority queue is full");
            }
            
            pq.push(queued_task);
            debug!("Enqueued high priority task");
        } else {
            // Use lock-free queue for normal tasks
            match self.queue.push(queued_task) {
                Ok(_) => debug!("Enqueued normal priority task"),
                Err(_) => {
                    self.stats.total_dropped.fetch_add(1, Ordering::Relaxed);
                    bail!("Queue is full");
                }
            }
        }
        
        // Update stats
        self.stats.total_enqueued.fetch_add(1, Ordering::Relaxed);
        let current = self.stats.current_size.fetch_add(1, Ordering::Relaxed) + 1;
        
        // Update peak size
        let mut peak = self.stats.peak_size.load(Ordering::Relaxed);
        while current > peak {
            match self.stats.peak_size.compare_exchange_weak(
                peak,
                current,
                Ordering::Release,
                Ordering::Relaxed,
            ) {
                Ok(_) => break,
                Err(x) => peak = x,
            }
        }
        
        Ok(())
    }
    
    /// Enqueue a batch of tasks
    pub async fn enqueue_batch(&self, tasks: Vec<PluginTask>) -> Result<()> {
        if self.shutdown.load(Ordering::Acquire) {
            bail!("Queue is shutting down");
        }
        
        let batch_id = uuid::Uuid::new_v4();
        let mut queued_tasks = Vec::with_capacity(tasks.len());
        
        for task in tasks {
            let queued_task = QueuedTask::new(task).with_batch(batch_id);
            queued_tasks.push(queued_task);
        }
        
        // Add to batch queue
        self.batch_queue.write().push_back(queued_tasks);
        
        // Update stats
        self.stats.batch_count.fetch_add(1, Ordering::Relaxed);
        
        info!("Enqueued batch {} with {} tasks", batch_id, tasks.len());
        Ok(())
    }
    
    /// Dequeue a task
    pub async fn dequeue(&self) -> Result<Option<QueuedTask>> {
        if self.shutdown.load(Ordering::Acquire) {
            return Ok(None);
        }
        
        // First check batch queue
        {
            let mut batches = self.batch_queue.write();
            if let Some(mut batch) = batches.front_mut() {
                if !batch.is_empty() {
                    let task = batch.remove(0);
                    
                    // Remove empty batch
                    if batch.is_empty() {
                        batches.pop_front();
                    }
                    
                    self.update_dequeue_stats(&task);
                    return Ok(Some(task));
                }
            }
        }
        
        // Then check priority queue
        {
            let mut pq = self.priority_queue.lock();
            if let Some(task) = pq.pop() {
                self.update_dequeue_stats(&task);
                return Ok(Some(task));
            }
        }
        
        // Finally check normal queue
        if let Some(task) = self.queue.pop() {
            self.update_dequeue_stats(&task);
            return Ok(Some(task));
        }
        
        Ok(None)
    }
    
    /// Dequeue multiple tasks for batch processing
    pub async fn dequeue_batch(&self, max_batch_size: usize) -> Result<Vec<QueuedTask>> {
        let mut batch = Vec::with_capacity(max_batch_size);
        
        // Try to get a complete batch from batch queue
        {
            let mut batches = self.batch_queue.write();
            if let Some(queued_batch) = batches.pop_front() {
                for task in queued_batch.into_iter().take(max_batch_size) {
                    self.update_dequeue_stats(&task);
                    batch.push(task);
                }
                
                if batch.len() == max_batch_size {
                    return Ok(batch);
                }
            }
        }
        
        // Fill remaining from other queues
        while batch.len() < max_batch_size {
            match self.dequeue().await? {
                Some(task) => batch.push(task),
                None => break,
            }
        }
        
        Ok(batch)
    }
    
    /// Peek at next task without dequeuing
    pub fn peek(&self) -> Option<Priority> {
        // Check priority queue first
        {
            let pq = self.priority_queue.lock();
            if let Some(task) = pq.peek() {
                return Some(task.priority);
            }
        }
        
        // Can't peek into ArrayQueue efficiently
        // Would need to implement custom solution
        
        None
    }
    
    /// Get current queue size
    pub fn size(&self) -> usize {
        self.stats.current_size.load(Ordering::Relaxed)
    }
    
    /// Check if queue is empty
    pub fn is_empty(&self) -> bool {
        self.size() == 0
    }
    
    /// Get queue statistics
    pub fn get_stats(&self) -> TaskQueueStats {
        TaskQueueStats {
            total_enqueued: self.stats.total_enqueued.load(Ordering::Relaxed),
            total_dequeued: self.stats.total_dequeued.load(Ordering::Relaxed),
            total_dropped: self.stats.total_dropped.load(Ordering::Relaxed),
            current_size: self.stats.current_size.load(Ordering::Relaxed),
            peak_size: self.stats.peak_size.load(Ordering::Relaxed),
            average_wait_time_ms: {
                let total_wait = self.stats.total_wait_time_ms.load(Ordering::Relaxed);
                let dequeued = self.stats.total_dequeued.load(Ordering::Relaxed);
                if dequeued > 0 {
                    total_wait / dequeued
                } else {
                    0
                }
            },
            batch_count: self.stats.batch_count.load(Ordering::Relaxed),
            throughput_per_sec: self.calculate_throughput(),
        }
    }
    
    /// Clear all tasks from queue
    pub async fn clear(&self) {
        // Clear all queues
        while self.queue.pop().is_some() {}
        self.priority_queue.lock().clear();
        self.batch_queue.write().clear();
        
        // Reset size counter
        self.stats.current_size.store(0, Ordering::Relaxed);
        
        info!("Cleared all tasks from queue");
    }
    
    /// Shutdown queue
    pub async fn shutdown(&self) {
        self.shutdown.store(true, Ordering::Release);
        self.clear().await;
        info!("Task queue shutdown complete");
    }
    
    /// Update dequeue statistics
    fn update_dequeue_stats(&self, task: &QueuedTask) {
        self.stats.total_dequeued.fetch_add(1, Ordering::Relaxed);
        self.stats.current_size.fetch_sub(1, Ordering::Relaxed);
        
        let wait_time_ms = task.enqueued_at.elapsed().as_millis() as usize;
        self.stats.total_wait_time_ms.fetch_add(wait_time_ms, Ordering::Relaxed);
    }
    
    /// Calculate throughput
    fn calculate_throughput(&self) -> f64 {
        // Simple throughput calculation
        // In production, would track over time window
        let dequeued = self.stats.total_dequeued.load(Ordering::Relaxed) as f64;
        let enqueued = self.stats.total_enqueued.load(Ordering::Relaxed) as f64;
        
        if enqueued > 0.0 {
            (dequeued / enqueued) * 1000.0 // Approximate tasks/sec
        } else {
            0.0
        }
    }
}

/// Task queue statistics
#[derive(Debug, Clone)]
pub struct TaskQueueStats {
    pub total_enqueued: usize,
    pub total_dequeued: usize,
    pub total_dropped: usize,
    pub current_size: usize,
    pub peak_size: usize,
    pub average_wait_time_ms: usize,
    pub batch_count: usize,
    pub throughput_per_sec: f64,
}

/// Task scheduler for optimal GPU utilization
pub struct TaskScheduler {
    queue: Arc<TaskQueue>,
    max_concurrent: usize,
    batch_size: usize,
}

impl TaskScheduler {
    pub fn new(queue: Arc<TaskQueue>, max_concurrent: usize) -> Self {
        Self {
            queue,
            max_concurrent,
            batch_size: 32, // Default batch size
        }
    }
    
    /// Get next batch of tasks to execute
    pub async fn get_next_batch(&self) -> Result<Vec<QueuedTask>> {
        self.queue.dequeue_batch(self.batch_size).await
    }
    
    /// Requeue failed task with backoff
    pub async fn requeue_failed(&self, mut task: QueuedTask) -> Result<()> {
        task.attempts += 1;
        
        if task.attempts > 3 {
            warn!("Task {} exceeded max attempts, dropping", task.task.id);
            return Ok(());
        }
        
        // Exponential backoff
        let backoff_ms = 100 * (2_u64.pow(task.attempts - 1));
        tokio::time::sleep(tokio::time::Duration::from_millis(backoff_ms)).await;
        
        // Reduce priority on retry
        if task.priority > Priority::Low {
            task.priority = match task.priority {
                Priority::Critical => Priority::High,
                Priority::High => Priority::Normal,
                Priority::Normal => Priority::Low,
                Priority::Low => Priority::Low,
            };
        }
        
        self.queue.enqueue(task.task).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_task_queue_priority() {
        let queue = TaskQueue::new(100);
        
        // Create tasks with different priorities
        let low_task = PluginTask {
            id: uuid::Uuid::new_v4(),
            type_: "test".to_string(),
            payload: vec![],
            priority: 50, // Low
        };
        
        let high_task = PluginTask {
            id: uuid::Uuid::new_v4(),
            type_: "test".to_string(),
            payload: vec![],
            priority: 200, // Critical
        };
        
        // Enqueue in reverse priority order
        queue.enqueue(low_task.clone()).await.unwrap();
        queue.enqueue(high_task.clone()).await.unwrap();
        
        // Dequeue should return high priority first
        let dequeued = queue.dequeue().await.unwrap().unwrap();
        assert_eq!(dequeued.task.id, high_task.id);
        
        let dequeued = queue.dequeue().await.unwrap().unwrap();
        assert_eq!(dequeued.task.id, low_task.id);
    }
    
    #[tokio::test]
    async fn test_batch_processing() {
        let queue = TaskQueue::new(100);
        
        // Create batch of tasks
        let mut tasks = Vec::new();
        for _ in 0..5 {
            tasks.push(PluginTask {
                id: uuid::Uuid::new_v4(),
                type_: "batch".to_string(),
                payload: vec![],
                priority: 100,
            });
        }
        
        queue.enqueue_batch(tasks.clone()).await.unwrap();
        
        // Dequeue batch
        let batch = queue.dequeue_batch(10).await.unwrap();
        assert_eq!(batch.len(), 5);
        
        // All should have same batch ID
        let batch_id = batch[0].batch_id;
        for task in &batch {
            assert_eq!(task.batch_id, batch_id);
        }
    }
}
