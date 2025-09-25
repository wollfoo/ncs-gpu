use std::{collections::HashMap, path::PathBuf, sync::Arc, time::Duration};

use async_trait::async_trait;
use serde::Deserialize;
use thiserror::Error;
use tokio::{
    fs,
    sync::RwLock,
    time::{Instant, Interval},
};
use tracing::{instrument, warn};

const DEFAULT_TTL_SECS: u64 = 300;

#[derive(Debug, Error)]
pub enum SecretError {
    #[error("secret `{0}` không tồn tại")]
    NotFound(String),
    #[error("secret provider lỗi: {0}")]
    Provider(String),
    #[error("serialisation error: {0}")]
    Serialization(String),
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
}

pub type Result<T> = std::result::Result<T, SecretError>;

#[derive(Debug, Clone)]
pub struct SecretValue {
    pub value: String,
    pub ttl: Option<Duration>,
}

#[async_trait]
pub trait SecretProvider: Send + Sync {
    async fn fetch(&self, key: &str) -> Result<SecretValue>;
}

struct CacheEntry {
    value: String,
    expires_at: Instant,
}

pub struct SecretManager<P: SecretProvider> {
    provider: Arc<P>,
    cache: RwLock<HashMap<String, CacheEntry>>,
    default_ttl: Duration,
}

impl<P: SecretProvider + 'static> SecretManager<P> {
    pub fn new(provider: P) -> Self {
        Self {
            provider: Arc::new(provider),
            cache: RwLock::new(HashMap::new()),
            default_ttl: Duration::from_secs(DEFAULT_TTL_SECS),
        }
    }

    pub fn set_default_ttl(&mut self, ttl: Duration) {
        self.default_ttl = ttl;
    }

    #[instrument(skip(self))]
    pub async fn secret(&self, key: &str) -> Result<String> {
        if let Some(value) = self.current_value(key).await {
            return Ok(value);
        }

        let fetched = self.provider.fetch(key).await?;
        self.update_cache(key, &fetched).await;
        Ok(fetched.value)
    }

    async fn current_value(&self, key: &str) -> Option<String> {
        let guard = self.cache.read().await;
        guard
            .get(key)
            .filter(|entry| Instant::now() < entry.expires_at)
            .map(|entry| entry.value.clone())
    }

    async fn update_cache(&self, key: &str, value: &SecretValue) {
        let ttl = value.ttl.unwrap_or(self.default_ttl);
        let expires_at = Instant::now() + ttl;
        let mut guard = self.cache.write().await;
        guard.insert(
            key.to_string(),
            CacheEntry {
                value: value.value.clone(),
                expires_at,
            },
        );
    }

    async fn refresh_all(&self) {
        let keys: Vec<String> = {
            let guard = self.cache.read().await;
            guard.keys().cloned().collect()
        };

        for key in keys {
            match self.provider.fetch(&key).await {
                Ok(value) => self.update_cache(&key, &value).await,
                Err(err) => warn!(secret = %key, error = ?err, "refresh secret thất bại"),
            }
        }
    }

    fn spawn_refresh_task(self: &Arc<Self>, interval: Duration) {
        let manager = Arc::clone(self);
        tokio::spawn(async move {
            let mut ticker: Interval = tokio::time::interval(interval);
            loop {
                ticker.tick().await;
                manager.refresh_all().await;
            }
        });
    }
}

pub struct EnvSecretProvider {
    prefix: Option<String>,
    file_dir: Option<PathBuf>,
}

impl EnvSecretProvider {
    pub fn new(prefix: Option<String>, file_dir: Option<PathBuf>) -> Self {
        Self { prefix, file_dir }
    }

    fn resolve_var(&self, key: &str) -> String {
        if let Some(prefix) = &self.prefix {
            format!("{}{}", prefix, key)
        } else {
            key.to_string()
        }
    }
}

#[async_trait]
impl SecretProvider for EnvSecretProvider {
    async fn fetch(&self, key: &str) -> Result<SecretValue> {
        let var_name = self.resolve_var(key);
        if let Ok(value) = std::env::var(&var_name) {
            return Ok(SecretValue { value, ttl: None });
        }

        if let Some(dir) = &self.file_dir {
            let path = dir.join(format!("{}.secret", key.to_lowercase()));
            if path.exists() {
                let raw = fs::read_to_string(&path).await?;
                let value = raw.trim().to_string();
                return Ok(SecretValue { value, ttl: None });
            }
        }

        Err(SecretError::NotFound(var_name))
    }
}

#[derive(Debug, Deserialize)]
struct SimulatedVaultSecrets(HashMap<String, SimulatedSecret>);

#[derive(Debug, Deserialize)]
struct SimulatedSecret {
    value: String,
    #[serde(default)]
    ttl_seconds: Option<u64>,
}

pub struct SimulatedVaultProvider {
    file: PathBuf,
}

impl SimulatedVaultProvider {
    pub fn new(file: PathBuf) -> Self {
        Self { file }
    }
}

#[async_trait]
impl SecretProvider for SimulatedVaultProvider {
    async fn fetch(&self, key: &str) -> Result<SecretValue> {
        let raw = fs::read(&self.file).await?;
        let secrets: SimulatedVaultSecrets = serde_json::from_slice(&raw)
            .map_err(|err| SecretError::Serialization(err.to_string()))?;
        match secrets.0.get(key) {
            Some(secret) => Ok(SecretValue {
                value: secret.value.clone(),
                ttl: secret.ttl_seconds.map(Duration::from_secs),
            }),
            None => Err(SecretError::NotFound(key.to_string())),
        }
    }
}

pub struct ChainedSecretProvider {
    providers: Vec<Arc<dyn SecretProvider + Send + Sync>>,
}

impl ChainedSecretProvider {
    pub fn new(providers: Vec<Arc<dyn SecretProvider + Send + Sync>>) -> Self {
        Self { providers }
    }
}

#[async_trait]
impl SecretProvider for ChainedSecretProvider {
    async fn fetch(&self, key: &str) -> Result<SecretValue> {
        let mut last_err = None;
        for provider in &self.providers {
            match provider.fetch(key).await {
                Ok(value) => return Ok(value),
                Err(err) => last_err = Some(err),
            }
        }
        Err(last_err.unwrap_or_else(|| SecretError::NotFound(key.to_string())))
    }
}

pub struct SecretManagerBuilder {
    providers: Vec<Arc<dyn SecretProvider + Send + Sync>>,
    refresh_interval: Option<Duration>,
    default_ttl: Option<Duration>,
}

impl SecretManagerBuilder {
    pub fn new() -> Self {
        Self {
            providers: Vec::new(),
            refresh_interval: None,
            default_ttl: None,
        }
    }

    pub fn with_env_provider(mut self, prefix: Option<String>, dir: Option<PathBuf>) -> Self {
        self.providers
            .push(Arc::new(EnvSecretProvider::new(prefix, dir)));
        self
    }

    pub fn with_simulated_vault(mut self, path: PathBuf) -> Self {
        self.providers
            .push(Arc::new(SimulatedVaultProvider::new(path)));
        self
    }

    pub fn with_refresh_interval(mut self, interval: Duration) -> Self {
        self.refresh_interval = Some(interval);
        self
    }

    pub fn with_default_ttl(mut self, ttl: Duration) -> Self {
        self.default_ttl = Some(ttl);
        self
    }

    pub fn build(self) -> Arc<SecretManager<ChainedSecretProvider>> {
        let provider = ChainedSecretProvider::new(self.providers);
        let mut manager = SecretManager::new(provider);
        if let Some(ttl) = self.default_ttl {
            manager.set_default_ttl(ttl);
        }
        let manager = Arc::new(manager);
        if let Some(interval) = self.refresh_interval {
            manager.spawn_refresh_task(interval);
        }
        manager
    }
}

impl Default for SecretManagerBuilder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct StaticProvider;

    #[async_trait]
    impl SecretProvider for StaticProvider {
        async fn fetch(&self, key: &str) -> Result<SecretValue> {
            Ok(SecretValue {
                value: format!("{key}-value"),
                ttl: Some(Duration::from_millis(10)),
            })
        }
    }

    #[tokio::test]
    async fn secret_manager_caches_and_refreshes() {
        let manager = SecretManager::new(StaticProvider);
        let value1 = manager.secret("demo").await.unwrap();
        assert_eq!(value1, "demo-value");
        tokio::time::sleep(Duration::from_millis(20)).await;
        let value2 = manager.secret("demo").await.unwrap();
        assert_eq!(value2, "demo-value");
    }
}
