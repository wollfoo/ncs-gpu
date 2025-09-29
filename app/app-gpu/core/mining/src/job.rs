use serde::{Deserialize, Serialize};
use std::time::{Duration, SystemTime};
use uuid::Uuid;

/// Mining job status
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum JobStatus {
    Pending,
    InProgress,
    Completed,
    Failed,
    Cancelled,
}

/// Mining job definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningJob {
    /// Unique job identifier
    pub id: Uuid,
    /// Job data to mine
    pub data: Vec<u8>,
    /// Target difficulty
    pub difficulty: u64,
    /// Nonce range start
    pub nonce_start: u64,
    /// Nonce range end
    pub nonce_end: u64,
    /// Job creation time
    pub created_at: SystemTime,
    /// Job deadline
    pub deadline: SystemTime,
    /// Current status
    pub status: JobStatus,
    /// Additional metadata
    pub metadata: serde_json::Value,
}

/// Result of a completed mining job
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobResult {
    /// Job ID this result is for
    pub job_id: Uuid,
    /// Found nonce (if any)
    pub nonce: Option<u64>,
    /// Computed hash
    pub hash: Vec<u8>,
    /// Number of hashes computed
    pub hashes_computed: u64,
    /// Time taken to complete
    pub duration: Duration,
    /// Whether result meets difficulty target
    pub meets_target: bool,
    /// Worker ID that produced this result
    pub worker_id: Uuid,
    /// Completion timestamp
    pub completed_at: SystemTime,
}

impl MiningJob {
    /// Create a new mining job
    pub fn new(
        data: Vec<u8>,
        difficulty: u64,
        nonce_start: u64,
        nonce_end: u64,
        deadline: SystemTime,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            data,
            difficulty,
            nonce_start,
            nonce_end,
            created_at: SystemTime::now(),
            deadline,
            status: JobStatus::Pending,
            metadata: serde_json::Value::Null,
        }
    }

    /// Check if job is expired
    pub fn is_expired(&self) -> bool {
        SystemTime::now() > self.deadline
    }

    /// Get job duration
    pub fn duration(&self) -> Duration {
        SystemTime::now()
            .duration_since(self.created_at)
            .unwrap_or(Duration::ZERO)
    }

    /// Get nonce range size
    pub fn nonce_range_size(&self) -> u64 {
        self.nonce_end.saturating_sub(self.nonce_start)
    }

    /// Set job status
    pub fn set_status(&mut self, status: JobStatus) {
        self.status = status;
    }

    /// Add metadata
    pub fn add_metadata(&mut self, key: &str, value: serde_json::Value) {
        if self.metadata.is_null() {
            self.metadata = serde_json::json!({});
        }
        if let Some(obj) = self.metadata.as_object_mut() {
            obj.insert(key.to_string(), value);
        }
    }
}

impl JobResult {
    /// Create a new job result
    pub fn new(
        job_id: Uuid,
        nonce: Option<u64>,
        hash: Vec<u8>,
        hashes_computed: u64,
        duration: Duration,
        meets_target: bool,
        worker_id: Uuid,
    ) -> Self {
        Self {
            job_id,
            nonce,
            hash,
            hashes_computed,
            duration,
            meets_target,
            worker_id,
            completed_at: SystemTime::now(),
        }
    }

    /// Get hashrate for this result
    pub fn hashrate(&self) -> f64 {
        if self.duration.as_secs_f64() > 0.0 {
            self.hashes_computed as f64 / self.duration.as_secs_f64()
        } else {
            0.0
        }
    }

    /// Check if result is a valid share
    pub fn is_valid_share(&self) -> bool {
        self.meets_target && self.nonce.is_some()
    }
}

impl Default for MiningJob {
    fn default() -> Self {
        Self {
            id: Uuid::new_v4(),
            data: Vec::new(),
            difficulty: 1000000,
            nonce_start: 0,
            nonce_end: u32::MAX as u64,
            created_at: SystemTime::now(),
            deadline: SystemTime::now() + Duration::from_secs(300), // 5 minutes
            status: JobStatus::Pending,
            metadata: serde_json::Value::Null,
        }
    }
}

impl Default for JobResult {
    fn default() -> Self {
        Self {
            job_id: Uuid::new_v4(),
            nonce: None,
            hash: Vec::new(),
            hashes_computed: 0,
            duration: Duration::ZERO,
            meets_target: false,
            worker_id: Uuid::new_v4(),
            completed_at: SystemTime::now(),
        }
    }
}