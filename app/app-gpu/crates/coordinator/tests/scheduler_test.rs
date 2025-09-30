// Integration tests cho scheduler

#[cfg(test)]
mod tests {
    use gpu_coordinator::scheduler::TaskScheduler;
    use gpu_coordinator::worker_registry::WorkerRegistry;
    use gpu_common::*;
    
    #[tokio::test]
    async fn test_submit_task() {
        let registry = WorkerRegistry::new();
        let scheduler = TaskScheduler::new(registry);
        
        let config = WorkloadConfig::default();
        let task_id = scheduler.submit_task(config).await.unwrap();
        
        // Verify task is pending
        let status = scheduler.get_task_status(task_id).await;
        assert_eq!(status, Some(TaskStatus::Pending));
    }
    
    #[tokio::test]
    async fn test_pending_count() {
        let registry = WorkerRegistry::new();
        let scheduler = TaskScheduler::new(registry);
        
        assert_eq!(scheduler.pending_count(), 0);
        
        let config = WorkloadConfig::default();
        scheduler.submit_task(config.clone()).await.unwrap();
        scheduler.submit_task(config.clone()).await.unwrap();
        
        assert_eq!(scheduler.pending_count(), 2);
    }
    
    #[tokio::test]
    async fn test_mark_completed() {
        let registry = WorkerRegistry::new();
        let scheduler = TaskScheduler::new(registry);
        
        let config = WorkloadConfig::default();
        let task_id = scheduler.submit_task(config).await.unwrap();
        
        // Mark as completed
        scheduler.mark_task_completed(task_id).await.unwrap();
        
        // Task should no longer be in active tasks
        assert_eq!(scheduler.active_count(), 0);
    }
    
    #[tokio::test]
    async fn test_mark_failed() {
        let registry = WorkerRegistry::new();
        let scheduler = TaskScheduler::new(registry);
        
        let config = WorkloadConfig::default();
        let task_id = scheduler.submit_task(config).await.unwrap();
        
        // Mark as failed
        let error_msg = "GPU kernel crash".to_string();
        scheduler.mark_task_failed(task_id, error_msg.clone()).await.unwrap();
        
        // Task should be removed from active tasks
        assert_eq!(scheduler.active_count(), 0);
    }
}
