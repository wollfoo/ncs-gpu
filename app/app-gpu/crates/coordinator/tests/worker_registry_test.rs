// Integration tests cho worker registry

#[cfg(test)]
mod tests {
    use gpu_coordinator::worker_registry::WorkerRegistry;
    use gpu_common::*;
    use std::time::Duration;
    
    #[tokio::test]
    async fn test_register_worker() {
        let registry = WorkerRegistry::new();
        let worker_id = WorkerId::new();
        let gpu_devices = vec![
            GpuDevice {
                index: 0,
                name: "NVIDIA RTX 4090".to_string(),
                total_memory: 24 * 1024 * 1024 * 1024,
                compute_capability: (8, 9),
                uuid: "GPU-12345678".to_string(),
            }
        ];
        
        registry.register_worker(worker_id, gpu_devices.clone()).await;
        
        assert_eq!(registry.active_worker_count(), 1);
        
        let info = registry.get_worker_info(worker_id).await;
        assert!(info.is_some());
        assert_eq!(info.unwrap().gpu_devices.len(), 1);
    }
    
    #[tokio::test]
    async fn test_unregister_worker() {
        let registry = WorkerRegistry::new();
        let worker_id = WorkerId::new();
        let gpu_devices = vec![];
        
        registry.register_worker(worker_id, gpu_devices).await;
        assert_eq!(registry.active_worker_count(), 1);
        
        registry.unregister_worker(worker_id).await;
        assert_eq!(registry.active_worker_count(), 0);
    }
    
    #[tokio::test]
    async fn test_heartbeat_update() {
        let registry = WorkerRegistry::new();
        let worker_id = WorkerId::new();
        let gpu_devices = vec![];
        
        registry.register_worker(worker_id, gpu_devices).await;
        
        // Wait a bit
        tokio::time::sleep(Duration::from_millis(100)).await;
        
        // Update heartbeat
        registry.update_heartbeat(worker_id).await;
        
        let info = registry.get_worker_info(worker_id).await.unwrap();
        // Heartbeat should be recent
        assert!(info.last_heartbeat.elapsed() < Duration::from_secs(1));
    }
    
    #[tokio::test]
    async fn test_get_available_worker() {
        let registry = WorkerRegistry::new();
        let worker_id = WorkerId::new();
        let gpu_devices = vec![];
        
        // No workers initially
        assert!(registry.get_available_worker().await.is_none());
        
        // Register a worker
        registry.register_worker(worker_id, gpu_devices).await;
        
        // Should find the worker
        let available = registry.get_available_worker().await;
        assert!(available.is_some());
        assert_eq!(available.unwrap(), worker_id);
        
        // Mark as busy
        registry.mark_worker_busy(worker_id, true).await;
        
        // Should not find available worker
        assert!(registry.get_available_worker().await.is_none());
    }
    
    #[tokio::test]
    async fn test_remove_dead_workers() {
        let registry = WorkerRegistry::new();
        let worker_id = WorkerId::new();
        let gpu_devices = vec![];
        
        registry.register_worker(worker_id, gpu_devices).await;
        assert_eq!(registry.active_worker_count(), 1);
        
        // Wait for timeout (simulate dead worker)
        tokio::time::sleep(Duration::from_millis(100)).await;
        
        // Remove workers with very short timeout
        let removed = registry.remove_dead_workers(Duration::from_millis(50)).await;
        
        assert_eq!(removed, 1);
        assert_eq!(registry.active_worker_count(), 0);
    }
    
    #[tokio::test]
    async fn test_list_all_workers() {
        let registry = WorkerRegistry::new();
        
        // Register multiple workers
        for _ in 0..3 {
            let worker_id = WorkerId::new();
            registry.register_worker(worker_id, vec![]).await;
        }
        
        let workers = registry.list_all_workers().await;
        assert_eq!(workers.len(), 3);
    }
}
