use anyhow::Result;
use app_gpu_domain::{config::AppConfig, JobSpec, ScheduleResult};
use telemetry_hub::EventEmitter;
use tokio::sync::{broadcast, mpsc, oneshot, RwLock};
use tracing::{debug, info, warn};

#[derive(Clone)]
pub struct SchedulerHandle {
    tx: mpsc::Sender<Command>,
    shutdown_tx: broadcast::Sender<()>,
}

impl SchedulerHandle {
    pub async fn schedule(&self, job: JobSpec) -> Result<String> {
        let (tx, rx) = oneshot::channel();
        self.tx.send(Command::Enqueue { job, respond: tx }).await?;
        Ok(rx.await?)
    }

    pub async fn snapshot(&self) -> String {
        "scheduler-ok".to_string()
    }

    pub async fn shutdown_notifier(&self) {
        let mut rx = self.shutdown_tx.subscribe();
        let _ = rx.recv().await;
    }

    pub async fn stop(handle: SchedulerHandle) {
        let _ = handle.shutdown_tx.send(());
    }

    pub async fn wait_for_shutdown(handle: SchedulerHandle) {
        handle.shutdown_notifier().await;
    }
}

pub struct Scheduler {
    cfg: AppConfig,
    emitter: EventEmitter,
}

impl Scheduler {
    pub fn new(cfg: AppConfig) -> Result<Self> {
        Ok(Self {
            emitter: EventEmitter::new("scheduler"),
            cfg,
        })
    }

    pub async fn spawn(self) -> Result<SchedulerHandle> {
        let (tx, mut rx) = mpsc::channel(self.cfg.scheduler.backlog);
        let (shutdown_tx, mut shutdown_rx) = broadcast::channel(2);
        let state = RwLock::new(Vec::<JobSpec>::new());
        let emitter = self.emitter.clone();
        let cfg = self.cfg.clone();

        tokio::spawn(async move {
            let mut tick = tokio::time::interval(std::time::Duration::from_millis(cfg.scheduler.tick_ms));
            loop {
                tokio::select! {
                    Some(cmd) = rx.recv() => {
                        if let Command::Enqueue { job, respond } = cmd {
                            let mut queue = state.write().await;
                            let job_id = format!("job-{}", queue.len() + 1);
                            queue.push(job.clone());
                            let result = ScheduleResult { job_id: job_id.clone(), queued_at: chrono::Utc::now() };
                            let _ = respond.send(job_id.clone());
                            emitter.emit_json("job.queued", &result);
                            debug!(target: "scheduler", %job_id, queue_len = queue.len(), "queued job");
                        }
                    }
                    _ = tick.tick() => {
                        let mut queue = state.write().await;
                        let batch = queue.drain(..cfg.scheduler.batch_size.min(queue.len())).collect::<Vec<_>>();
                        if !batch.is_empty() {
                            info!(target: "scheduler", size = batch.len(), "dispatching batch");
                            // TODO: integrate with GPU executor via gpu_bindings
                        }
                    }
                    _ = shutdown_rx.recv() => {
                        warn!(target: "scheduler", "shutdown signal received");
                        break;
                    }
                }
            }
        });

        Ok(SchedulerHandle { tx, shutdown_tx })
    }
}

#[derive(Debug)]
enum Command {
    Enqueue { job: JobSpec, respond: oneshot::Sender<String> },
}

#[cfg(test)]
mod tests {
    use super::*;
    use app_gpu_domain::config::AppConfig;

    #[tokio::test]
    async fn schedule_returns_job_id() {
        std::env::remove_var("APP_CONFIG_PATH");
        let cfg = AppConfig::load().expect("load config");
        let scheduler = Scheduler::new(cfg).expect("scheduler init");
        let handle = scheduler.spawn().await.expect("spawn scheduler");

        let job = JobSpec {
            wallet: "wallet-test".into(),
            pool_endpoint: "stratum+ssl://pool".into(),
            gpu_index: 0,
            dag_location: "/tmp/dag".into(),
        };

        let job_id = handle.schedule(job).await.expect("schedule job");
        assert!(job_id.starts_with("job-"));

        SchedulerHandle::stop(handle).await;
    }
}
