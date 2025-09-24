pub mod config;
pub mod telemetry;
pub mod proto {
    include!("generated.rs");
}

use chrono::Utc;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct JobSpec {
    pub wallet: String,
    pub pool_endpoint: String,
    pub gpu_index: u8,
    pub dag_location: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct ScheduleResult {
    pub job_id: String,
    pub queued_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum ApiMode {
    Rest,
    Grpc,
}
