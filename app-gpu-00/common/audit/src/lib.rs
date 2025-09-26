use std::{
    path::{Path, PathBuf},
    sync::Arc,
};

use serde::Serialize;
use thiserror::Error;
use tokio::{
    fs::{self, OpenOptions},
    io::AsyncWriteExt,
    sync::Mutex,
};
use tracing::warn;

#[derive(Debug, Error)]
pub enum AuditError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("serialize error: {0}")]
    Serialize(#[from] serde_json::Error),
}

type Result<T> = std::result::Result<T, AuditError>;

#[derive(Clone)]
pub struct AuditLogger {
    writer: Arc<Mutex<tokio::fs::File>>,
}

impl AuditLogger {
    pub async fn new(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).await?;
        }
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .await?;
        Ok(Self {
            writer: Arc::new(Mutex::new(file)),
        })
    }

    pub async fn record<T>(&self, entry: &T) -> Result<()>
    where
        T: Serialize,
    {
        let json = serde_json::to_vec(entry)?;
        let mut writer = self.writer.lock().await;
        writer.write_all(&json).await?;
        writer.write_all(b"\n").await?;
        writer.flush().await?;
        Ok(())
    }

    pub async fn record_or_warn<T>(&self, entry: &T)
    where
        T: Serialize,
    {
        if let Err(err) = self.record(entry).await {
            warn!(error = %err, "ghi audit log thất bại");
        }
    }
}

pub fn default_audit_path(name: &str) -> PathBuf {
    PathBuf::from("logs")
        .join("audit")
        .join(format!("{name}.jsonl"))
}
