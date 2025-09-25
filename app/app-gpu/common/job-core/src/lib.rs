use std::{
    collections::HashMap,
    env,
    sync::Arc,
    time::{SystemTime, UNIX_EPOCH},
};

use async_trait::async_trait;
#[cfg(feature = "redis-store")]
use redis::{aio::ConnectionManager, AsyncCommands};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use thiserror::Error;
#[cfg(feature = "redis-store")]
use tokio::sync::Mutex;
use tokio::sync::RwLock;
use tracing::warn;

pub type Result<T> = std::result::Result<T, JobError>;

#[derive(Debug, Error)]
pub enum JobError {
    #[error("invalid payload: {0}")]
    InvalidPayload(String),
    #[error("job not found")]
    NotFound,
    #[error("serialization error: {0}")]
    Serialization(String),
    #[error("store failure: {0}")]
    StoreFailure(String),
    #[error("redis error: {0}")]
    Redis(String),
}

#[cfg(feature = "redis-store")]
impl From<redis::RedisError> for JobError {
    fn from(err: redis::RedisError) -> Self {
        JobError::Redis(err.to_string())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobPayload {
    pub kernel: String,
    #[serde(default)]
    pub args: Vec<String>,
    #[serde(default)]
    pub env: HashMap<String, String>,
    #[serde(default)]
    pub stdin: Option<String>,
    #[serde(default)]
    #[serde(flatten)]
    pub extra: HashMap<String, Value>,
}

impl JobPayload {
    pub fn validate(&self) -> Result<()> {
        if self.kernel.trim().is_empty() {
            return Err(JobError::InvalidPayload(
                "kernel không được để trống".into(),
            ));
        }
        Ok(())
    }

    pub fn command_path(&self) -> String {
        self.kernel.clone()
    }
}

impl TryFrom<Value> for JobPayload {
    type Error = JobError;

    fn try_from(value: Value) -> Result<Self> {
        match value {
            Value::String(kernel) => {
                let payload = JobPayload {
                    kernel,
                    args: Vec::new(),
                    env: HashMap::new(),
                    stdin: None,
                    extra: HashMap::new(),
                };
                payload.validate()?;
                Ok(payload)
            }
            Value::Null => {
                let payload = JobPayload {
                    kernel: default_kernel(),
                    args: Vec::new(),
                    env: HashMap::new(),
                    stdin: None,
                    extra: HashMap::new(),
                };
                payload.validate()?;
                Ok(payload)
            }
            other @ Value::Object(_) => {
                let intermediary: PayloadIntermediary = serde_json::from_value(other)
                    .map_err(|err| JobError::InvalidPayload(err.to_string()))?;
                let kernel = intermediary
                    .kernel
                    .or(intermediary.command)
                    .unwrap_or_else(default_kernel);
                let mut env_map = HashMap::new();
                if let Some(env_values) = intermediary.env {
                    for (key, raw) in env_values {
                        match raw {
                            Value::String(value) => {
                                env_map.insert(key, value);
                            }
                            Value::Number(num) => {
                                env_map.insert(key, num.to_string());
                            }
                            Value::Bool(flag) => {
                                env_map.insert(key, flag.to_string());
                            }
                            _ => {
                                return Err(JobError::InvalidPayload(format!(
                                    "env[{key}] phải là string/number/bool"
                                )));
                            }
                        }
                    }
                }

                let payload = JobPayload {
                    kernel,
                    args: intermediary.args.unwrap_or_default(),
                    env: env_map,
                    stdin: intermediary.stdin,
                    extra: intermediary.extra,
                };
                payload.validate()?;
                Ok(payload)
            }
            _ => Err(JobError::InvalidPayload(
                "payload phải là string hoặc object".into(),
            )),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum JobStatus {
    Queued,
    Running,
    Succeeded,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct JobResult {
    pub stdout: Option<String>,
    pub stderr: Option<String>,
    pub exit_code: Option<i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobRecord {
    pub id: String,
    pub status: JobStatus,
    pub payload: JobPayload,
    pub result: Option<JobResult>,
    pub error: Option<String>,
    pub created_at: f64,
    pub updated_at: f64,
    pub duration_secs: Option<f64>,
}

impl JobRecord {
    pub fn new(id: String, payload: JobPayload) -> Self {
        let now = current_timestamp();
        Self {
            id,
            status: JobStatus::Queued,
            payload,
            result: None,
            error: None,
            created_at: now,
            updated_at: now,
            duration_secs: None,
        }
    }

    pub fn apply_update(&mut self, update: JobUpdate) {
        self.status = update.status;
        self.result = update.result;
        self.error = update.error;
        self.duration_secs = update.duration_secs;
        self.updated_at = current_timestamp();
    }
}

#[derive(Debug, Clone)]
pub struct JobUpdate {
    pub status: JobStatus,
    pub result: Option<JobResult>,
    pub error: Option<String>,
    pub duration_secs: Option<f64>,
}

impl JobUpdate {
    pub fn queued() -> Self {
        Self {
            status: JobStatus::Queued,
            result: None,
            error: None,
            duration_secs: None,
        }
    }

    pub fn running() -> Self {
        Self {
            status: JobStatus::Running,
            result: None,
            error: None,
            duration_secs: None,
        }
    }

    pub fn succeeded(result: JobResult, duration_secs: f64) -> Self {
        Self {
            status: JobStatus::Succeeded,
            result: Some(result),
            error: None,
            duration_secs: Some(duration_secs),
        }
    }

    pub fn failed(error: String) -> Self {
        Self {
            status: JobStatus::Failed,
            result: None,
            error: Some(error),
            duration_secs: None,
        }
    }
}

#[async_trait]
pub trait JobStore: Send + Sync {
    async fn create_job(&self, record: JobRecord) -> Result<()>;
    async fn update_job(&self, id: &str, update: JobUpdate) -> Result<JobRecord>;
    async fn get_job(&self, id: &str) -> Result<Option<JobRecord>>;
}

pub type DynJobStore = Arc<dyn JobStore>;

#[derive(Default)]
pub struct InMemoryJobStore {
    inner: RwLock<HashMap<String, JobRecord>>,
}

#[async_trait]
impl JobStore for InMemoryJobStore {
    async fn create_job(&self, record: JobRecord) -> Result<()> {
        let mut guard = self.inner.write().await;
        guard.insert(record.id.clone(), record);
        Ok(())
    }

    async fn update_job(&self, id: &str, update: JobUpdate) -> Result<JobRecord> {
        let mut guard = self.inner.write().await;
        let record = guard.get_mut(id).ok_or(JobError::NotFound)?;
        record.apply_update(update);
        Ok(record.clone())
    }

    async fn get_job(&self, id: &str) -> Result<Option<JobRecord>> {
        let guard = self.inner.read().await;
        Ok(guard.get(id).cloned())
    }
}

#[cfg(feature = "redis-store")]
pub struct RedisJobStore {
    manager: Mutex<ConnectionManager>,
}

#[cfg(feature = "redis-store")]
impl RedisJobStore {
    pub async fn new(url: &str) -> Result<Self> {
        let client = redis::Client::open(url.to_string())?;
        let manager = ConnectionManager::new(client).await?;
        Ok(Self {
            manager: Mutex::new(manager),
        })
    }

    fn key(id: &str) -> String {
        format!("job:{id}")
    }
}

#[cfg(feature = "redis-store")]
#[async_trait]
impl JobStore for RedisJobStore {
    async fn create_job(&self, record: JobRecord) -> Result<()> {
        let mut conn = self.manager.lock().await;
        let json = serde_json::to_string(&record)
            .map_err(|err| JobError::Serialization(err.to_string()))?;
        let key = Self::key(&record.id);
        conn.set(key, json).await.map_err(JobError::from)?;
        Ok(())
    }

    async fn update_job(&self, id: &str, update: JobUpdate) -> Result<JobRecord> {
        let mut conn = self.manager.lock().await;
        let key = Self::key(id);
        let existing: Option<String> = conn.get(&key).await.map_err(JobError::from)?;
        let mut record = existing
            .map(|raw| serde_json::from_str::<JobRecord>(&raw))
            .transpose()
            .map_err(|err| JobError::Serialization(err.to_string()))?
            .ok_or(JobError::NotFound)?;
        record.apply_update(update);
        let serialized = serde_json::to_string(&record)
            .map_err(|err| JobError::Serialization(err.to_string()))?;
        conn.set(key, serialized).await.map_err(JobError::from)?;
        Ok(record)
    }

    async fn get_job(&self, id: &str) -> Result<Option<JobRecord>> {
        let mut conn = self.manager.lock().await;
        let key = Self::key(id);
        let raw: Option<String> = conn.get(key).await.map_err(JobError::from)?;
        match raw {
            Some(json) => {
                let record = serde_json::from_str::<JobRecord>(&json)
                    .map_err(|err| JobError::Serialization(err.to_string()))?;
                Ok(Some(record))
            }
            None => Ok(None),
        }
    }
}

#[derive(Default)]
pub struct JobStoreBuilder {
    url: Option<String>,
}

impl JobStoreBuilder {
    pub fn from_env() -> Self {
        Self {
            url: env::var("JOB_STORE_URL").ok(),
        }
    }

    pub fn with_url(url: Option<String>) -> Self {
        Self { url }
    }

    pub async fn build(self) -> Result<DynJobStore> {
        if let Some(url) = self.url {
            if url.trim().is_empty() {
                warn!("JOB_STORE_URL rỗng, dùng in-memory store");
            } else if url.starts_with("redis://") {
                #[cfg(feature = "redis-store")]
                {
                    let store = RedisJobStore::new(&url).await?;
                    return Ok(Arc::new(store));
                }
                #[cfg(not(feature = "redis-store"))]
                {
                    warn!(
                        "JOB_STORE_URL={url} yêu cầu bật feature redis-store, fallback sang in-memory"
                    );
                }
            } else if url.eq_ignore_ascii_case("memory") {
                warn!("JOB_STORE_URL=memory, dùng in-memory store cho mục đích thử nghiệm");
            } else {
                warn!("JOB_STORE_URL={url} không được hỗ trợ, fallback sang in-memory store");
            }
        } else {
            warn!("JOB_STORE_URL chưa thiết lập, dùng in-memory store (không bền vững)");
        }

        Ok(Arc::new(InMemoryJobStore::default()))
    }
}

#[derive(Deserialize)]
struct PayloadIntermediary {
    #[serde(default)]
    kernel: Option<String>,
    #[serde(default)]
    command: Option<String>,
    #[serde(default)]
    args: Option<Vec<String>>,
    #[serde(default)]
    env: Option<HashMap<String, Value>>,
    #[serde(default)]
    stdin: Option<String>,
    #[serde(default)]
    #[serde(flatten)]
    extra: HashMap<String, Value>,
}

fn current_timestamp() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or_default()
}

fn default_kernel() -> String {
    env::var("GPU_KERNEL_DEFAULT").unwrap_or_else(|_| "inference-cuda".to_string())
}
