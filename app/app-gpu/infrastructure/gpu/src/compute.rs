use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComputeKernel {
    pub id: String,
    pub name: String,
    pub source_code: String,
    pub entry_point: String,
    pub work_group_size: (u32, u32, u32),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComputeProgram {
    pub id: Uuid,
    pub name: String,
    pub source_code: String,
    pub compiled: bool,
    pub device_id: Uuid,
}

impl ComputeKernel {
    pub fn new(id: String, name: String, source_code: String) -> Self {
        Self {
            id,
            name,
            source_code,
            entry_point: "main".to_string(),
            work_group_size: (256, 1, 1),
        }
    }
}