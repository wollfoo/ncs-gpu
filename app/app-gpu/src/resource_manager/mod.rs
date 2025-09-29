//! Resource Management System for OPUS-GPU
//!
//! Advanced resource management with lock-free data structures,
//! intelligent scheduling, and adaptive allocation strategies.

pub mod allocator;
pub mod monitor;
pub mod scheduler;

pub use allocator::*;
pub use monitor::*;
pub use scheduler::*;

/// Resource types managed by the system
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum ResourceType {
    /// GPU device resources
    GpuDevice(u32),
    /// GPU memory
    GpuMemory,
    /// System memory
    SystemMemory,
    /// CPU cores
    CpuCore,
    /// Network bandwidth
    NetworkBandwidth,
    /// Storage I/O
    StorageIo,
}

/// Resource allocation request
#[derive(Debug, Clone)]
pub struct ResourceRequest {
    /// Request identifier
    pub id: String,
    /// Resource type
    pub resource_type: ResourceType,
    /// Requested amount
    pub amount: u64,
    /// Priority level (0-255, higher = more priority)
    pub priority: u8,
    /// Maximum wait time before timeout
    pub timeout: std::time::Duration,
    /// Request timestamp
    pub timestamp: std::time::Instant,
    /// Optional constraints
    pub constraints: ResourceConstraints,
}

/// Resource allocation constraints
#[derive(Debug, Clone, Default)]
pub struct ResourceConstraints {
    /// Minimum required amount
    pub min_amount: Option<u64>,
    /// Maximum allowed amount
    pub max_amount: Option<u64>,
    /// Preferred device affinity
    pub device_affinity: Option<u32>,
    /// Memory alignment requirements
    pub alignment: Option<usize>,
    /// Exclusive access required
    pub exclusive: bool,
}

/// Resource allocation result
#[derive(Debug, Clone)]
pub struct ResourceAllocation {
    /// Allocation identifier
    pub id: String,
    /// Resource type
    pub resource_type: ResourceType,
    /// Allocated amount
    pub amount: u64,
    /// Allocation timestamp
    pub timestamp: std::time::Instant,
    /// Resource handle for cleanup
    pub handle: ResourceHandle,
}

/// Resource handle for managing allocated resources
#[derive(Debug, Clone)]
pub struct ResourceHandle {
    /// Handle identifier
    pub id: String,
    /// Resource type
    pub resource_type: ResourceType,
    /// Allocated size
    pub size: u64,
    /// Memory address (for memory resources)
    pub address: Option<usize>,
    /// Device ID (for device resources)
    pub device_id: Option<u32>,
}

/// Resource usage statistics
#[derive(Debug, Clone, Default)]
pub struct ResourceUsage {
    /// Total available resources
    pub total: u64,
    /// Currently allocated resources
    pub allocated: u64,
    /// Peak usage
    pub peak: u64,
    /// Current utilization percentage
    pub utilization: f64,
    /// Number of active allocations
    pub active_allocations: u32,
    /// Average allocation size
    pub average_allocation_size: u64,
}

/// Resource pool for efficient allocation
pub trait ResourcePool: Send + Sync {
    /// Resource type this pool manages
    fn resource_type(&self) -> ResourceType;

    /// Allocate resource from pool
    fn allocate(&self, request: &ResourceRequest) -> crate::common::OpusResult<ResourceAllocation>;

    /// Deallocate resource back to pool
    fn deallocate(&self, handle: &ResourceHandle) -> crate::common::OpusResult<()>;

    /// Get current resource usage
    fn usage(&self) -> ResourceUsage;

    /// Check if allocation is possible
    fn can_allocate(&self, request: &ResourceRequest) -> bool;

    /// Get pool capacity
    fn capacity(&self) -> u64;
}

/// Resource manager configuration
#[derive(Debug, Clone)]
pub struct ResourceManagerConfig {
    /// Maximum memory allocation per request (bytes)
    pub max_allocation_size: u64,
    /// Memory pool sizes by type
    pub pool_sizes: std::collections::HashMap<ResourceType, u64>,
    /// Enable resource defragmentation
    pub enable_defragmentation: bool,
    /// Defragmentation interval
    pub defrag_interval: std::time::Duration,
    /// Maximum allocation wait time
    pub max_wait_time: std::time::Duration,
    /// Enable resource monitoring
    pub enable_monitoring: bool,
    /// Monitoring interval
    pub monitor_interval: std::time::Duration,
}

impl Default for ResourceManagerConfig {
    fn default() -> Self {
        let mut pool_sizes = std::collections::HashMap::new();
        pool_sizes.insert(ResourceType::GpuMemory, 8 * 1024 * 1024 * 1024); // 8GB
        pool_sizes.insert(ResourceType::SystemMemory, 16 * 1024 * 1024 * 1024); // 16GB

        Self {
            max_allocation_size: 1024 * 1024 * 1024, // 1GB
            pool_sizes,
            enable_defragmentation: true,
            defrag_interval: std::time::Duration::from_secs(300), // 5 minutes
            max_wait_time: std::time::Duration::from_secs(30),
            enable_monitoring: true,
            monitor_interval: std::time::Duration::from_secs(5),
        }
    }
}

impl ResourceRequest {
    /// Create new resource request
    pub fn new(
        id: impl Into<String>,
        resource_type: ResourceType,
        amount: u64,
        priority: u8,
    ) -> Self {
        Self {
            id: id.into(),
            resource_type,
            amount,
            priority,
            timeout: std::time::Duration::from_secs(30),
            timestamp: std::time::Instant::now(),
            constraints: ResourceConstraints::default(),
        }
    }

    /// Set timeout for request
    pub fn with_timeout(mut self, timeout: std::time::Duration) -> Self {
        self.timeout = timeout;
        self
    }

    /// Set constraints for request
    pub fn with_constraints(mut self, constraints: ResourceConstraints) -> Self {
        self.constraints = constraints;
        self
    }

    /// Check if request has timed out
    pub fn is_expired(&self) -> bool {
        self.timestamp.elapsed() > self.timeout
    }

    /// Get age of request
    pub fn age(&self) -> std::time::Duration {
        self.timestamp.elapsed()
    }

    /// Calculate effective priority based on age and base priority
    pub fn effective_priority(&self) -> f64 {
        let age_factor = self.age().as_secs_f64() / 60.0; // Age in minutes
        self.priority as f64 + age_factor * 0.1 // Small age bonus
    }
}

impl ResourceUsage {
    /// Calculate utilization percentage
    pub fn calculate_utilization(&mut self) {
        if self.total > 0 {
            self.utilization = (self.allocated as f64 / self.total as f64) * 100.0;
        } else {
            self.utilization = 0.0;
        }
    }

    /// Update peak usage
    pub fn update_peak(&mut self) {
        if self.allocated > self.peak {
            self.peak = self.allocated;
        }
    }

    /// Check if usage is critical
    pub fn is_critical(&self) -> bool {
        self.utilization > 95.0
    }

    /// Check if usage is high
    pub fn is_high(&self) -> bool {
        self.utilization > 80.0
    }

    /// Get fragmentation ratio (estimate)
    pub fn fragmentation_ratio(&self) -> f64 {
        if self.active_allocations == 0 {
            return 0.0;
        }

        let expected_usage = self.active_allocations as u64 * self.average_allocation_size;
        if expected_usage > 0 {
            1.0 - (self.allocated as f64 / expected_usage as f64)
        } else {
            0.0
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resource_request_creation() {
        let request = ResourceRequest::new(
            "test_req_001",
            ResourceType::GpuMemory,
            1024 * 1024,
            100,
        );

        assert_eq!(request.id, "test_req_001");
        assert_eq!(request.resource_type, ResourceType::GpuMemory);
        assert_eq!(request.amount, 1024 * 1024);
        assert_eq!(request.priority, 100);
        assert!(!request.is_expired());
    }

    #[test]
    fn test_resource_request_timeout() {
        let mut request = ResourceRequest::new(
            "test_req_002",
            ResourceType::SystemMemory,
            2048,
            50,
        );

        // Set very short timeout for testing
        request.timeout = std::time::Duration::from_nanos(1);
        std::thread::sleep(std::time::Duration::from_millis(1));

        assert!(request.is_expired());
    }

    #[test]
    fn test_effective_priority() {
        let request = ResourceRequest::new(
            "test_req_003",
            ResourceType::CpuCore,
            4,
            100,
        );

        let priority = request.effective_priority();
        assert!(priority >= 100.0);
    }

    #[test]
    fn test_resource_usage() {
        let mut usage = ResourceUsage {
            total: 1000,
            allocated: 800,
            peak: 900,
            utilization: 0.0,
            active_allocations: 10,
            average_allocation_size: 80,
        };

        usage.calculate_utilization();
        assert_eq!(usage.utilization, 80.0);
        assert!(!usage.is_critical());
        assert!(usage.is_high());

        usage.allocated = 950;
        usage.calculate_utilization();
        assert!(usage.is_critical());

        usage.update_peak();
        assert_eq!(usage.peak, 950);
    }

    #[test]
    fn test_resource_constraints() {
        let constraints = ResourceConstraints {
            min_amount: Some(1024),
            max_amount: Some(4096),
            device_affinity: Some(0),
            alignment: Some(256),
            exclusive: true,
        };

        assert_eq!(constraints.min_amount, Some(1024));
        assert_eq!(constraints.max_amount, Some(4096));
        assert_eq!(constraints.device_affinity, Some(0));
        assert!(constraints.exclusive);
    }

    #[test]
    fn test_resource_handle() {
        let handle = ResourceHandle {
            id: "handle_001".to_string(),
            resource_type: ResourceType::GpuDevice(0),
            size: 1024,
            address: Some(0x1000000),
            device_id: Some(0),
        };

        assert_eq!(handle.id, "handle_001");
        assert_eq!(handle.resource_type, ResourceType::GpuDevice(0));
        assert_eq!(handle.size, 1024);
        assert_eq!(handle.address, Some(0x1000000));
        assert_eq!(handle.device_id, Some(0));
    }

    #[test]
    fn test_fragmentation_calculation() {
        let mut usage = ResourceUsage {
            total: 1000,
            allocated: 500,
            peak: 600,
            utilization: 50.0,
            active_allocations: 10,
            average_allocation_size: 60, // Expected total: 600, actual: 500
        };

        let fragmentation = usage.fragmentation_ratio();
        assert!((fragmentation - (1.0 - 500.0/600.0)).abs() < 0.001);
    }
}