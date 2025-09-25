//! Job Core - Shared job abstractions and types
//!
//! Provides common data structures and validation logic
//! used across scheduler and executor components

use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;
use validator::{Validate, ValidationError};

/// Job priority levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum JobPriority {
    Low = 1,
    Normal = 5,
    High = 8,
    Critical = 10,
}

/// Job execution status
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum JobStatus {
    Pending,
    Queued,
    Scheduled { worker_id: String, gpu_id: u32 },
    Running { worker_id: String, gpu_id: u32, started_at: DateTime<Utc> },
    Completed { completed_at: DateTime<Utc>, result: JobResult },
    Failed { failed_at: DateTime<Utc>, error: String, retryable: bool },
    Cancelled { cancelled_at: DateTime<Utc>, reason: String },
    Timeout { timeout_at: DateTime<Utc> },
}

/// GPU resource requirements
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct GpuRequirements {
    /// Required memory in MB
    #[validate(range(min = 1, max = 81920))] // Max 80GB
    pub memory_mb: u64,
    
    /// Compute units required (0.0-1.0)
    #[validate(range(min = 0.0, max = 1.0))]
    pub compute_units: f32,
    
    /// Minimum GPU memory in GB
    #[validate(range(min = 1, max = 80))]
    pub min_gpu_memory_gb: Option<u32>,
    
    /// Preferred GPU architecture
    pub preferred_arch: Option<String>,
    
    /// Requires exclusive GPU access
    pub exclusive_access: bool,
    
    /// CUDA compute capability requirement
    pub min_compute_capability: Option<String>,
}

/// Job payload containing operation details
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct JobPayload {
    /// Operation type identifier
    #[validate(length(min = 1, max = 64))]
    pub operation: String,
    
    /// Operation parameters
    pub params: HashMap<String, serde_json::Value>,
    
    /// Input data (base64 encoded for JSON transport)
    pub input_data: Option<String>,
    
    /// Expected output format
    pub output_format: Option<String>,
}

/// Complete job definition
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct Job {
    /// Unique job identifier
    pub id: String,
    
    /// Job priority
    pub priority: JobPriority,
    
    /// GPU resource requirements
    #[validate]
    pub gpu_requirements: GpuRequirements,
    
    /// Estimated execution duration in milliseconds
    #[validate(range(min = 1, max = 3600000))] // Max 1 hour
    pub estimated_duration_ms: Option<u64>,
    
    /// Job deadline
    pub deadline: Option<DateTime<Utc>>,
    
    /// Current retry count
    pub retry_count: u32,
    
    /// Maximum retry attempts
    #[validate(range(min = 0, max = 10))]
    pub max_retries: u32,
    
    /// Job payload
    #[validate]
    pub payload: JobPayload,
    
    /// Job metadata
    pub metadata: HashMap<String, String>,
    
    /// Job creation timestamp
    pub created_at: DateTime<Utc>,
    
    /// Job submission timestamp
    pub submitted_at: Option<DateTime<Utc>>,
}

/// Job execution result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobResult {
    /// Output data (base64 encoded)
    pub output_data: Option<String>,
    
    /// Execution metrics
    pub metrics: ExecutionMetrics,
    
    /// Additional result metadata
    pub metadata: HashMap<String, String>,
}

/// Execution performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionMetrics {
    /// Average GPU utilization during execution
    pub gpu_utilization_avg: f32,
    
    /// Peak memory usage in MB
    pub memory_peak_mb: u64,
    
    /// Total kernel execution time in milliseconds
    pub kernel_time_ms: u64,
    
    /// Memory copy time in milliseconds
    pub memory_copy_time_ms: u64,
    
    /// Total wall-clock time in milliseconds
    pub total_time_ms: u64,
    
    /// Memory bandwidth achieved in GB/s
    pub memory_bandwidth_gbps: f64,
    
    /// Power consumption in watts (if available)
    pub power_consumption_watts: Option<f32>,
    
    /// Temperature metrics
    pub temperature_celsius: Option<f32>,
}

/// Worker capabilities and status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerInfo {
    pub id: String,
    pub gpu_id: u32,
    pub status: WorkerStatus,
    pub capabilities: WorkerCapabilities,
    pub current_job: Option<String>,
    pub last_heartbeat: DateTime<Utc>,
    pub worker_version: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum WorkerStatus {
    Idle,
    Busy,
    Draining,    // Finishing current jobs, not accepting new ones
    Offline,
    Error(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerCapabilities {
    /// Maximum memory available in MB
    pub max_memory_mb: u64,
    
    /// CUDA compute capability
    pub compute_capability: String,
    
    /// Number of CUDA cores
    pub cuda_cores: u32,
    
    /// GPU architecture
    pub architecture: String,
    
    /// Supported data types
    pub supports_fp16: bool,
    pub supports_int8: bool,
    pub supports_tf32: bool,
    
    /// Supported operations
    pub supported_operations: Vec<String>,
    
    /// Hardware generation info
    pub gpu_generation: Option<String>,
}

impl Job {
    /// Create new job with generated ID
    pub fn new(
        priority: JobPriority,
        gpu_requirements: GpuRequirements,
        payload: JobPayload,
    ) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            priority,
            gpu_requirements,
            estimated_duration_ms: None,
            deadline: None,
            retry_count: 0,
            max_retries: 3,
            payload,
            metadata: HashMap::new(),
            created_at: Utc::now(),
            submitted_at: None,
        }
    }
    
    /// Mark job as submitted
    pub fn mark_submitted(&mut self) {
        self.submitted_at = Some(Utc::now());
    }
    
    /// Check if job has deadline passed
    pub fn is_deadline_passed(&self) -> bool {
        self.deadline
            .map(|deadline| Utc::now() > deadline)
            .unwrap_or(false)
    }
    
    /// Check if job can be retried
    pub fn can_retry(&self) -> bool {
        self.retry_count < self.max_retries
    }
    
    /// Increment retry count
    pub fn increment_retry(&mut self) {
        self.retry_count += 1;
    }
    
    /// Validate job constraints
    pub fn validate_constraints(&self) -> Result<()> {
        // Run validator
        self.validate()
            .map_err(|e| anyhow::anyhow!("Job validation failed: {:?}", e))?;
        
        // Custom business logic validation
        if let Some(deadline) = self.deadline {
            if deadline <= Utc::now() {
                anyhow::bail!("Job deadline is in the past");
            }
        }
        
        // Validate operation is supported
        if self.payload.operation.is_empty() {
            anyhow::bail!("Job operation cannot be empty");
        }
        
        Ok(())
    }
}

impl GpuRequirements {
    /// Create minimal GPU requirements
    pub fn minimal() -> Self {
        Self {
            memory_mb: 512,
            compute_units: 0.1,
            min_gpu_memory_gb: Some(1),
            preferred_arch: None,
            exclusive_access: false,
            min_compute_capability: None,
        }
    }
    
    /// Create high-performance requirements
    pub fn high_performance() -> Self {
        Self {
            memory_mb: 8192,
            compute_units: 0.8,
            min_gpu_memory_gb: Some(8),
            preferred_arch: Some("Ampere".to_string()),
            exclusive_access: true,
            min_compute_capability: Some("8.0".to_string()),
        }
    }
    
    /// Check if requirements are compatible with worker
    pub fn is_compatible_with(&self, worker: &WorkerCapabilities) -> bool {
        // Memory check
        if self.memory_mb > worker.max_memory_mb {
            return false;
        }
        
        // Architecture preference
        if let Some(ref preferred) = self.preferred_arch {
            if !worker.architecture.contains(preferred) {
                return false;
            }
        }
        
        // Compute capability check
        if let Some(ref min_cc) = self.min_compute_capability {
            if worker.compute_capability < *min_cc {
                return false;
            }
        }
        
        true
    }
}

impl JobPayload {
    /// Create new job payload
    pub fn new(operation: String) -> Self {
        Self {
            operation,
            params: HashMap::new(),
            input_data: None,
            output_format: None,
        }
    }
    
    /// Add parameter to payload
    pub fn with_param<T: Serialize>(mut self, key: &str, value: T) -> Result<Self> {
        let json_value = serde_json::to_value(value)
            .context("Failed to serialize parameter")?;
        self.params.insert(key.to_string(), json_value);
        Ok(self)
    }
    
    /// Set input data (will be base64 encoded)
    pub fn with_input_data(mut self, data: &[u8]) -> Self {
        self.input_data = Some(base64::encode(data));
        self
    }
    
    /// Get parameter as typed value
    pub fn get_param<T: for<'de> Deserialize<'de>>(&self, key: &str) -> Result<Option<T>> {
        if let Some(value) = self.params.get(key) {
            let typed_value = serde_json::from_value(value.clone())
                .context("Failed to deserialize parameter")?;
            Ok(Some(typed_value))
        } else {
            Ok(None)
        }
    }
    
    /// Get input data (base64 decoded)
    pub fn get_input_data(&self) -> Result<Option<Vec<u8>>> {
        if let Some(ref encoded) = self.input_data {
            let decoded = base64::decode(encoded)
                .context("Failed to decode input data")?;
            Ok(Some(decoded))
        } else {
            Ok(None)
        }
    }
}

/// Helper functions for creating common job types
pub mod job_builders {
    use super::*;
    
    /// Create matrix multiplication job
    pub fn matrix_multiply(size: u32, precision: &str) -> Result<Job> {
        let gpu_reqs = if size > 1024 {
            GpuRequirements::high_performance()
        } else {
            GpuRequirements::minimal()
        };
        
        let payload = JobPayload::new("matrix_multiply".to_string())
            .with_param("matrix_size", size)?
            .with_param("precision", precision)?;
        
        let mut job = Job::new(JobPriority::Normal, gpu_reqs, payload);
        job.estimated_duration_ms = Some((size as u64).pow(3) / 1000); // Rough estimate
        
        Ok(job)
    }
    
    /// Create neural network inference job
    pub fn neural_inference(
        model_name: &str,
        batch_size: u32,
        input_shape: Vec<u32>,
    ) -> Result<Job> {
        let memory_estimate = batch_size as u64 * input_shape.iter().product::<u32>() as u64 * 4 / (1024 * 1024); // 4 bytes per float32
        
        let gpu_reqs = GpuRequirements {
            memory_mb: memory_estimate.max(512),
            compute_units: 0.6,
            min_gpu_memory_gb: Some(4),
            preferred_arch: Some("Turing".to_string()),
            exclusive_access: false,
            min_compute_capability: Some("7.5".to_string()),
        };
        
        let payload = JobPayload::new("neural_inference".to_string())
            .with_param("model_name", model_name)?
            .with_param("batch_size", batch_size)?
            .with_param("input_shape", input_shape)?;
        
        let mut job = Job::new(JobPriority::High, gpu_reqs, payload);
        job.estimated_duration_ms = Some(batch_size as u64 * 100); // ~100ms per batch item
        
        Ok(job)
    }
    
    /// Create custom compute job
    pub fn custom_compute(
        operation: &str,
        params: HashMap<String, serde_json::Value>,
        memory_mb: u64,
        priority: JobPriority,
    ) -> Result<Job> {
        let gpu_reqs = GpuRequirements {
            memory_mb,
            compute_units: 0.5,
            min_gpu_memory_gb: None,
            preferred_arch: None,
            exclusive_access: false,
            min_compute_capability: None,
        };
        
        let mut payload = JobPayload::new(operation.to_string());
        payload.params = params;
        
        Ok(Job::new(priority, gpu_reqs, payload))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::job_builders::*;
    
    #[test]
    fn test_job_creation() {
        let job = matrix_multiply(512, "fp32").unwrap();
        assert_eq!(job.payload.operation, "matrix_multiply");
        assert!(job.validate_constraints().is_ok());
    }
    
    #[test]
    fn test_gpu_requirements_compatibility() {
        let reqs = GpuRequirements::minimal();
        
        let worker = WorkerCapabilities {
            max_memory_mb: 8192,
            compute_capability: "7.5".to_string(),
            cuda_cores: 2048,
            architecture: "Turing".to_string(),
            supports_fp16: true,
            supports_int8: true,
            supports_tf32: true,
            supported_operations: vec!["matrix_multiply".to_string()],
            gpu_generation: Some("RTX 20XX".to_string()),
        };
        
        assert!(reqs.is_compatible_with(&worker));
    }
    
    #[test]
    fn test_job_payload_params() {
        let mut payload = JobPayload::new("test_op".to_string());
        payload = payload.with_param("size", 1024u32).unwrap();
        payload = payload.with_param("name", "test".to_string()).unwrap();
        
        let size: u32 = payload.get_param("size").unwrap().unwrap();
        let name: String = payload.get_param("name").unwrap().unwrap();
        
        assert_eq!(size, 1024);
        assert_eq!(name, "test");
    }
}

// Re-export for convenience
pub use job_builders::*;

// Add base64 dependency
use base64;
