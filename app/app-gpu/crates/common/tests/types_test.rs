// Unit tests cho common types

#[cfg(test)]
mod tests {
    use gpu_common::*;
    
    #[test]
    fn test_worker_id_creation() {
        let id1 = WorkerId::new();
        let id2 = WorkerId::new();
        
        assert_ne!(id1, id2, "Worker IDs should be unique");
    }
    
    #[test]
    fn test_task_id_creation() {
        let id1 = TaskId::new();
        let id2 = TaskId::new();
        
        assert_ne!(id1, id2, "Task IDs should be unique");
    }
    
    #[test]
    fn test_task_metadata_lifecycle() {
        let task_id = TaskId::new();
        let worker_id = WorkerId::new();
        
        let mut metadata = types::TaskMetadata::new(task_id);
        
        // Initial state
        assert_eq!(metadata.status, TaskStatus::Pending);
        assert!(metadata.worker_id.is_none());
        
        // Mark running
        metadata.mark_running(worker_id);
        assert_eq!(metadata.status, TaskStatus::Running);
        assert_eq!(metadata.worker_id, Some(worker_id));
        assert!(metadata.started_at.is_some());
        
        // Mark completed
        metadata.mark_completed();
        assert_eq!(metadata.status, TaskStatus::Completed);
        assert!(metadata.completed_at.is_some());
    }
    
    #[test]
    fn test_task_metadata_failure() {
        let task_id = TaskId::new();
        let mut metadata = types::TaskMetadata::new(task_id);
        
        metadata.mark_failed("GPU out of memory".to_string());
        
        assert_eq!(metadata.status, TaskStatus::Failed);
        assert_eq!(metadata.error_message, Some("GPU out of memory".to_string()));
        assert!(metadata.completed_at.is_some());
    }
    
    #[test]
    fn test_workload_config_default() {
        let config = WorkloadConfig::default();
        
        assert_eq!(config.workload_type, WorkloadType::AiTraining);
        assert_eq!(config.duration_secs, 60);
        assert_eq!(config.batch_size, 32);
        assert_eq!(config.gpu_utilization_target, 80.0);
        assert_eq!(config.memory_size_mb, 1024);
    }
    
    #[test]
    fn test_workload_result_empty() {
        let result = WorkloadResult::empty();
        
        assert_eq!(result.throughput, 0.0);
        assert_eq!(result.total_operations, 0);
    }
    
    #[test]
    fn test_gpu_device_serialization() {
        let device = GpuDevice {
            index: 0,
            name: "NVIDIA RTX 4090".to_string(),
            total_memory: 24 * 1024 * 1024 * 1024,
            compute_capability: (8, 9),
            uuid: "GPU-12345678".to_string(),
        };
        
        // Test serialization
        let json = serde_json::to_string(&device).unwrap();
        let deserialized: GpuDevice = serde_json::from_str(&json).unwrap();
        
        assert_eq!(device.index, deserialized.index);
        assert_eq!(device.name, deserialized.name);
    }
}
