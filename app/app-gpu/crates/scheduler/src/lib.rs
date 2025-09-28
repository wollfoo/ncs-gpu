use common::job::JobSpec;
use std::cmp::Ordering;
use std::collections::BinaryHeap;
use std::time::{Duration, Instant};
use tokio::sync::{mpsc, oneshot};
use tokio::task::JoinHandle;
use tokio::time::{self, MissedTickBehavior};
use tokio_stream::StreamExt;
use anyhow::Result;

/// Cấu hình cho scheduler.
#[derive(Clone, Debug)]
pub struct SchedulerConfig {
    pub queue_capacity: usize,
    pub burst_capacity: u32,
    pub refill_amount: u32,
    pub refill_interval: Duration,
}

impl Default for SchedulerConfig {
    fn default() -> Self {
        Self {
            queue_capacity: 256,
            burst_capacity: 32,
            refill_amount: 16,
            refill_interval: Duration::from_millis(50),
        }
    }
}

/// Thông tin job được dispatch.
#[derive(Clone, Debug)]
pub struct DispatchedJob {
    pub job: JobSpec,
    pub attempt: u8,
    pub latency: Duration,
}

/// Lỗi khi enqueue job.
#[derive(thiserror::Error, Debug)]
pub enum SchedulerError {
    #[error("scheduler channel closed")]
    ChannelClosed,
}

/// Đối tượng phía producer gửi job vào scheduler.
#[derive(Clone)]
pub struct Scheduler {
    submit_tx: mpsc::Sender<JobEnvelope>,
}

impl Scheduler {
    pub async fn submit(&self, job: JobSpec) -> Result<(), SchedulerError> {
        let envelope = JobEnvelope {
            job,
            submitted_at: Instant::now(),
            attempt: 0,
        };
        self.submit_tx
            .send(envelope)
            .await
            .map_err(|_| SchedulerError::ChannelClosed)
    }
}

/// Handle dùng để shutdown goroutine scheduler.
pub struct SchedulerController {
    shutdown_tx: Option<oneshot::Sender<()>>,
    join_handle: JoinHandle<()>,
}

impl SchedulerController {
    pub async fn shutdown(mut self) {
        if let Some(tx) = self.shutdown_tx.take() {
            let _ = tx.send(());
        }
        let _ = self.join_handle.await;
    }
}

/// Khởi động scheduler: trả về producer, receiver và controller.
pub fn start_scheduler(
    config: SchedulerConfig,
) -> (
    Scheduler,
    mpsc::Receiver<DispatchedJob>,
    SchedulerController,
) {
    let (submit_tx, submit_rx) = mpsc::channel(config.queue_capacity);
    let (dispatch_tx, dispatch_rx) = mpsc::channel(config.queue_capacity);
    let (shutdown_tx, shutdown_rx) = oneshot::channel();

    let runtime_config = config.clone();

    let join_handle = tokio::spawn(async move {
        run_scheduler(runtime_config, submit_rx, dispatch_tx, shutdown_rx).await;
    });

    let scheduler = Scheduler { submit_tx };
    let controller = SchedulerController {
        shutdown_tx: Some(shutdown_tx),
        join_handle,
    };

    (scheduler, dispatch_rx, controller)
}

/// Tiện ích lấy job từ một stream sự kiện (ví dụ NATS/Kafka) và enqueue vào scheduler.
pub async fn consume_stream<S>(scheduler: &Scheduler, mut stream: S) -> Result<()>
where
    S: tokio_stream::Stream<Item = JobSpec> + Unpin + Send,
{
    while let Some(job) = stream.next().await {
        scheduler
            .submit(job)
            .await
            .map_err(|err| anyhow::Error::new(err))?;
    }
    Ok(())
}

struct JobEnvelope {
    job: JobSpec,
    submitted_at: Instant,
    attempt: u8,
}

struct QueuedJob {
    envelope: JobEnvelope,
    deadline_at: Instant,
}

impl QueuedJob {
    fn new(envelope: JobEnvelope) -> Self {
        let deadline_at = envelope.submitted_at + envelope.job.soft_deadline();
        Self {
            envelope,
            deadline_at,
        }
    }
}

impl Ord for QueuedJob {
    fn cmp(&self, other: &Self) -> Ordering {
        match self
            .envelope
            .job
            .qos
            .priority
            .cmp(&other.envelope.job.qos.priority)
        {
            Ordering::Equal => match other.deadline_at.cmp(&self.deadline_at) {
                Ordering::Equal => self.envelope.submitted_at.cmp(&other.envelope.submitted_at),
                ord => ord,
            },
            ord => ord,
        }
    }
}

impl PartialOrd for QueuedJob {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl PartialEq for QueuedJob {
    fn eq(&self, other: &Self) -> bool {
        self.envelope.job.id == other.envelope.job.id
    }
}

impl Eq for QueuedJob {}

#[derive(Debug)]
struct TokenBucket {
    capacity: u32,
    tokens: u32,
    refill_amount: u32,
}

impl TokenBucket {
    fn new(capacity: u32, refill_amount: u32) -> Self {
        Self {
            capacity,
            tokens: capacity,
            refill_amount,
        }
    }

    fn take(&mut self, cost: u32) -> bool {
        if self.tokens < cost {
            return false;
        }
        self.tokens -= cost;
        true
    }

    fn refill(&mut self) {
        self.tokens = (self.tokens + self.refill_amount).min(self.capacity);
    }

    fn available(&self) -> u32 {
        self.tokens
    }
}

async fn run_scheduler(
    config: SchedulerConfig,
    mut submit_rx: mpsc::Receiver<JobEnvelope>,
    dispatch_tx: mpsc::Sender<DispatchedJob>,
    mut shutdown_rx: oneshot::Receiver<()>,
) {
    let mut heap = BinaryHeap::new();
    let mut bucket = TokenBucket::new(config.burst_capacity, config.refill_amount);
    let mut refill = time::interval(config.refill_interval);
    refill.set_missed_tick_behavior(MissedTickBehavior::Skip);

    loop {
        tokio::select! {
            biased;
            _ = &mut shutdown_rx => {
                break;
            }
            _ = refill.tick() => {
                bucket.refill();
            }
            maybe_job = submit_rx.recv() => {
                match maybe_job {
                    Some(job) => heap.push(QueuedJob::new(job)),
                    None => break,
                }
            }
        }

        while bucket.available() > 0 {
            let mut queued = match heap.pop() {
                Some(job) => job,
                None => break,
            };

            let cost = queued.envelope.job.batch_size.max(1);
            if !bucket.take(cost) {
                heap.push(queued);
                break;
            }

            queued.envelope.attempt += 1;
            let latency = queued.envelope.submitted_at.elapsed();
            let dispatched = DispatchedJob {
                job: queued.envelope.job.clone(),
                attempt: queued.envelope.attempt,
                latency,
            };

            if dispatch_tx.send(dispatched).await.is_err() {
                return;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use common::job::{JobSpec, PriorityClass, QosPolicy};
    use tokio_stream::iter;

    fn percentile(latencies: &mut [Duration], pct: f64) -> Option<Duration> {
        if latencies.is_empty() {
            return None;
        }
        latencies.sort_unstable();
        let rank = (latencies.len() as f64 * pct).ceil() as usize;
        let idx = rank.saturating_sub(1).min(latencies.len() - 1);
        Some(latencies[idx])
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 4)]
    async fn scheduler_dispatch_p95_under_150ms() {
        let config = SchedulerConfig {
            queue_capacity: 128,
            burst_capacity: 32,
            refill_amount: 16,
            refill_interval: Duration::from_millis(20),
        };

        let (scheduler, mut rx, controller) = start_scheduler(config);

        let total_jobs = 60u32;

        for i in 0..total_jobs {
            let priority = if i % 5 == 0 {
                PriorityClass::Critical
            } else {
                PriorityClass::High
            };
            let qos = QosPolicy {
                priority,
                soft_deadline_ms: 200,
                max_retries: 2,
            };
            let job = JobSpec::new(format!("job-{i}"), qos, 4);
            scheduler.submit(job).await.unwrap();
            tokio::time::sleep(Duration::from_millis(3)).await;
        }

        let mut latencies: Vec<Duration> = Vec::with_capacity(total_jobs as usize);
        for _ in 0..total_jobs {
            let dispatched = rx.recv().await.expect("receive job");
            latencies.push(dispatched.latency);
        }

        controller.shutdown().await;

        let p95 = percentile(&mut latencies[..], 0.95).expect("p95 value");
        assert!(
            p95 < Duration::from_millis(150),
            "P95 latency {p95:?} exceeded target"
        );
    }

    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn consume_stream_enqueues_jobs() {
        let (scheduler, mut rx, controller) = start_scheduler(SchedulerConfig::default());

        let qos = QosPolicy {
            priority: PriorityClass::High,
            soft_deadline_ms: 250,
            max_retries: 1,
        };

        let jobs: Vec<JobSpec> = (0..10)
            .map(|i| JobSpec::new(format!("stream-job-{i}"), qos.clone(), 2))
            .collect();

        consume_stream(&scheduler, iter(jobs.clone())).await.unwrap();

        let mut received = Vec::new();
        for _ in 0..jobs.len() {
            let dispatched = rx.recv().await.expect("dispatch");
            received.push(dispatched.job.id.0);
        }

        controller.shutdown().await;

        assert_eq!(received.len(), jobs.len());
    }
}
