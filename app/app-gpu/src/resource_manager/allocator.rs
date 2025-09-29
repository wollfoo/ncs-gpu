//! Advanced memory allocator with lock-free data structures
//!
//! High-performance memory allocation system optimized for GPU mining
//! with pool-based allocation, defragmentation, and zero-copy transfers.

use std::alloc::{alloc, dealloc, Layout};
use std::collections::BTreeMap;
use std::ptr::NonNull;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::Arc;
use crossbeam::queue::SegQueue;
use parking_lot::{RwLock, Mutex};

use crate::common::error::{OpusError, OpusResult};
use crate::common::metrics::OpusMetrics;
use crate::resource_manager::{
    ResourcePool, ResourceRequest, ResourceAllocation, ResourceHandle,
    ResourceUsage, ResourceType, ResourceConstraints,
};

/// Lock-free memory allocator with pool management
pub struct LockFreeAllocator {
    /// Memory pools by size class
    size_pools: Vec<MemoryPool>,
    /// Large allocation tracker
    large_allocations: Arc<RwLock<BTreeMap<usize, LargeAllocation>>>,
    /// Total allocated bytes
    total_allocated: AtomicU64,
    /// Peak allocated bytes
    peak_allocated: AtomicU64,
    /// Allocation counter
    allocation_count: AtomicU64,
    /// Metrics collector
    metrics: Option<Arc<OpusMetrics>>,
    /// Allocator configuration
    config: AllocatorConfig,
}

/// Memory pool for specific size class
struct MemoryPool {
    /// Pool size class (bytes)
    size_class: usize,
    /// Free blocks queue
    free_blocks: SegQueue<NonNull<u8>>,
    /// Total blocks in pool
    total_blocks: AtomicUsize,
    /// Allocated blocks counter
    allocated_blocks: AtomicUsize,
    /// Pool metadata
    metadata: Mutex<PoolMetadata>,
}

/// Large allocation tracking
#[derive(Debug)]
struct LargeAllocation {
    /// Pointer to allocation
    ptr: NonNull<u8>,
    /// Allocation size
    size: usize,
    /// Allocation layout
    layout: Layout,
    /// Allocation timestamp
    timestamp: std::time::Instant,
}

/// Pool metadata for management
#[derive(Debug)]
struct PoolMetadata {
    /// Pool capacity in bytes
    capacity: usize,
    /// Number of allocations from this pool
    allocation_count: u64,
    /// Last cleanup timestamp
    last_cleanup: std::time::Instant,
}

/// Allocator configuration
#[derive(Debug, Clone)]
pub struct AllocatorConfig {
    /// Size classes for pools (in bytes)
    pub size_classes: Vec<usize>,
    /// Initial blocks per pool
    pub initial_blocks_per_pool: usize,
    /// Maximum blocks per pool
    pub max_blocks_per_pool: usize,
    /// Large allocation threshold
    pub large_allocation_threshold: usize,
    /// Enable memory alignment
    pub enable_alignment: bool,
    /// Default alignment
    pub default_alignment: usize,
    /// Enable pool expansion
    pub enable_pool_expansion: bool,
    /// Pool expansion factor
    pub pool_expansion_factor: f64,
}

impl Default for AllocatorConfig {
    fn default() -> Self {
        Self {
            size_classes: vec![
                64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536,
                131072, 262144, 524288, 1048576, // 1MB
            ],
            initial_blocks_per_pool: 1024,
            max_blocks_per_pool: 8192,
            large_allocation_threshold: 2 * 1024 * 1024, // 2MB
            enable_alignment: true,
            default_alignment: 64, // Cache line alignment
            enable_pool_expansion: true,
            pool_expansion_factor: 1.5,
        }
    }
}

impl LockFreeAllocator {
    /// Create new lock-free allocator
    pub fn new(config: AllocatorConfig, metrics: Option<Arc<OpusMetrics>>) -> OpusResult<Self> {
        let mut size_pools = Vec::with_capacity(config.size_classes.len());

        // Create memory pools for each size class
        for &size_class in &config.size_classes {
            let pool = MemoryPool::new(size_class, &config)?;
            size_pools.push(pool);
        }

        Ok(Self {
            size_pools,
            large_allocations: Arc::new(RwLock::new(BTreeMap::new())),
            total_allocated: AtomicU64::new(0),
            peak_allocated: AtomicU64::new(0),
            allocation_count: AtomicU64::new(0),
            metrics,
            config,
        })
    }

    /// Allocate memory with specified size and alignment
    pub fn allocate(&self, size: usize, alignment: Option<usize>) -> OpusResult<NonNull<u8>> {
        let start_time = std::time::Instant::now();

        // Determine effective alignment
        let align = alignment.unwrap_or(self.config.default_alignment);
        let aligned_size = align_size(size, align);

        let ptr = if aligned_size >= self.config.large_allocation_threshold {
            self.allocate_large(aligned_size, align)?
        } else {
            self.allocate_from_pool(aligned_size, align)?
        };

        // Update statistics
        self.total_allocated.fetch_add(aligned_size as u64, Ordering::Relaxed);
        self.allocation_count.fetch_add(1, Ordering::Relaxed);

        // Update peak allocation
        let current = self.total_allocated.load(Ordering::Relaxed);
        let mut peak = self.peak_allocated.load(Ordering::Relaxed);
        while current > peak {
            match self.peak_allocated.compare_exchange_weak(
                peak, current, Ordering::Relaxed, Ordering::Relaxed
            ) {
                Ok(_) => break,
                Err(actual) => peak = actual,
            }
        }

        // Record metrics
        if let Some(metrics) = &self.metrics {
            metrics.allocation_time.observe(start_time.elapsed().as_secs_f64());
        }

        Ok(ptr)
    }

    /// Deallocate memory
    pub fn deallocate(&self, ptr: NonNull<u8>, size: usize) -> OpusResult<()> {
        let aligned_size = align_size(size, self.config.default_alignment);

        if aligned_size >= self.config.large_allocation_threshold {
            self.deallocate_large(ptr)?;
        } else {
            self.deallocate_to_pool(ptr, aligned_size)?;
        }

        // Update statistics
        self.total_allocated.fetch_sub(aligned_size as u64, Ordering::Relaxed);

        Ok(())
    }

    /// Get current allocation statistics
    pub fn statistics(&self) -> AllocationStatistics {
        let total_allocated = self.total_allocated.load(Ordering::Relaxed);
        let peak_allocated = self.peak_allocated.load(Ordering::Relaxed);
        let allocation_count = self.allocation_count.load(Ordering::Relaxed);

        let mut pool_stats = Vec::new();
        for pool in &self.size_pools {
            let total_blocks = pool.total_blocks.load(Ordering::Relaxed);
            let allocated_blocks = pool.allocated_blocks.load(Ordering::Relaxed);
            let pool_utilization = if total_blocks > 0 {
                (allocated_blocks as f64 / total_blocks as f64) * 100.0
            } else {
                0.0
            };

            pool_stats.push(PoolStatistics {
                size_class: pool.size_class,
                total_blocks,
                allocated_blocks,
                utilization: pool_utilization,
            });
        }

        let large_allocations_count = self.large_allocations.read().len();

        AllocationStatistics {
            total_allocated,
            peak_allocated,
            allocation_count,
            pool_statistics: pool_stats,
            large_allocations_count,
        }
    }

    /// Allocate from appropriate pool
    fn allocate_from_pool(&self, size: usize, alignment: usize) -> OpusResult<NonNull<u8>> {
        // Find appropriate size class
        let pool_index = self.find_pool_index(size)?;
        let pool = &self.size_pools[pool_index];

        // Try to get block from pool
        if let Some(ptr) = pool.free_blocks.pop() {
            pool.allocated_blocks.fetch_add(1, Ordering::Relaxed);
            return Ok(ptr);
        }

        // Pool is empty, try to expand if enabled
        if self.config.enable_pool_expansion {
            self.expand_pool(pool_index)?;
            if let Some(ptr) = pool.free_blocks.pop() {
                pool.allocated_blocks.fetch_add(1, Ordering::Relaxed);
                return Ok(ptr);
            }
        }

        // Fall back to system allocation
        self.allocate_large(size, alignment)
    }

    /// Deallocate to appropriate pool
    fn deallocate_to_pool(&self, ptr: NonNull<u8>, size: usize) -> OpusResult<()> {
        let pool_index = self.find_pool_index(size)?;
        let pool = &self.size_pools[pool_index];

        // Return block to pool
        pool.free_blocks.push(ptr);
        pool.allocated_blocks.fetch_sub(1, Ordering::Relaxed);

        Ok(())
    }

    /// Allocate large memory block
    fn allocate_large(&self, size: usize, alignment: usize) -> OpusResult<NonNull<u8>> {
        let layout = Layout::from_size_align(size, alignment).map_err(|_| {
            OpusError::memory_error("Invalid layout for large allocation", size)
        })?;

        let ptr = unsafe { alloc(layout) };
        let non_null = NonNull::new(ptr).ok_or_else(|| {
            OpusError::memory_error("Failed to allocate large memory block", size)
        })?;

        // Track large allocation
        let allocation = LargeAllocation {
            ptr: non_null,
            size,
            layout,
            timestamp: std::time::Instant::now(),
        };

        self.large_allocations.write().insert(ptr as usize, allocation);

        Ok(non_null)
    }

    /// Deallocate large memory block
    fn deallocate_large(&self, ptr: NonNull<u8>) -> OpusResult<()> {
        let mut large_allocs = self.large_allocations.write();
        let allocation = large_allocs.remove(&(ptr.as_ptr() as usize)).ok_or_else(|| {
            OpusError::memory_error("Large allocation not found for deallocation", 0)
        })?;

        unsafe {
            dealloc(ptr.as_ptr(), allocation.layout);
        }

        Ok(())
    }

    /// Find appropriate pool index for size
    fn find_pool_index(&self, size: usize) -> OpusResult<usize> {
        for (i, &pool_size) in self.config.size_classes.iter().enumerate() {
            if size <= pool_size {
                return Ok(i);
            }
        }

        Err(OpusError::memory_error(
            "Size too large for pools",
            size,
        ))
    }

    /// Expand pool capacity
    fn expand_pool(&self, pool_index: usize) -> OpusResult<()> {
        let pool = &self.size_pools[pool_index];
        let current_blocks = pool.total_blocks.load(Ordering::Relaxed);

        if current_blocks >= self.config.max_blocks_per_pool {
            return Err(OpusError::memory_error(
                "Pool at maximum capacity",
                pool.size_class,
            ));
        }

        let additional_blocks = ((current_blocks as f64 * self.config.pool_expansion_factor) as usize)
            .min(self.config.max_blocks_per_pool - current_blocks)
            .max(1);

        pool.add_blocks(additional_blocks)?;

        Ok(())
    }

    /// Cleanup unused allocations
    pub fn cleanup(&self) -> OpusResult<()> {
        let now = std::time::Instant::now();
        let cleanup_threshold = std::time::Duration::from_secs(300); // 5 minutes

        // Cleanup old large allocations (this would be more sophisticated in practice)
        let large_allocs = self.large_allocations.read();
        let old_count = large_allocs.len();
        drop(large_allocs);

        // Pool cleanup would go here
        for pool in &self.size_pools {
            let mut metadata = pool.metadata.lock();
            if now.duration_since(metadata.last_cleanup) > cleanup_threshold {
                // Perform pool maintenance
                metadata.last_cleanup = now;
            }
        }

        Ok(())
    }
}

impl MemoryPool {
    /// Create new memory pool
    fn new(size_class: usize, config: &AllocatorConfig) -> OpusResult<Self> {
        let pool = Self {
            size_class,
            free_blocks: SegQueue::new(),
            total_blocks: AtomicUsize::new(0),
            allocated_blocks: AtomicUsize::new(0),
            metadata: Mutex::new(PoolMetadata {
                capacity: 0,
                allocation_count: 0,
                last_cleanup: std::time::Instant::now(),
            }),
        };

        // Pre-allocate initial blocks
        pool.add_blocks(config.initial_blocks_per_pool)?;

        Ok(pool)
    }

    /// Add blocks to pool
    fn add_blocks(&self, count: usize) -> OpusResult<()> {
        let layout = Layout::from_size_align(self.size_class, 64).map_err(|_| {
            OpusError::memory_error("Invalid layout for pool allocation", self.size_class)
        })?;

        for _ in 0..count {
            let ptr = unsafe { alloc(layout) };
            let non_null = NonNull::new(ptr).ok_or_else(|| {
                OpusError::memory_error("Failed to allocate pool block", self.size_class)
            })?;

            self.free_blocks.push(non_null);
        }

        self.total_blocks.fetch_add(count, Ordering::Relaxed);

        // Update metadata
        let mut metadata = self.metadata.lock();
        metadata.capacity += count * self.size_class;

        Ok(())
    }
}

/// GPU memory allocator for CUDA operations
pub struct GpuMemoryAllocator {
    /// Device ID
    device_id: u32,
    /// System allocator for fallback
    system_allocator: Arc<LockFreeAllocator>,
    /// GPU memory usage
    gpu_usage: AtomicU64,
    /// GPU memory capacity
    gpu_capacity: u64,
    /// Metrics collector
    metrics: Option<Arc<OpusMetrics>>,
}

impl GpuMemoryAllocator {
    /// Create new GPU memory allocator
    pub fn new(
        device_id: u32,
        gpu_capacity: u64,
        system_allocator: Arc<LockFreeAllocator>,
        metrics: Option<Arc<OpusMetrics>>,
    ) -> Self {
        Self {
            device_id,
            system_allocator,
            gpu_usage: AtomicU64::new(0),
            gpu_capacity,
            metrics,
        }
    }

    /// Allocate GPU memory
    pub fn allocate_gpu(&self, size: usize) -> OpusResult<GpuMemoryHandle> {
        let current_usage = self.gpu_usage.load(Ordering::Relaxed);
        if current_usage + size as u64 > self.gpu_capacity {
            return Err(OpusError::memory_error(
                "Insufficient GPU memory",
                size,
            ));
        }

        // This would use actual CUDA allocation in practice
        let handle = GpuMemoryHandle {
            device_id: self.device_id,
            size,
            address: 0x1000000 + current_usage, // Simulated GPU address
        };

        self.gpu_usage.fetch_add(size as u64, Ordering::Relaxed);

        // Record metrics
        if let Some(metrics) = &self.metrics {
            let device_id_str = self.device_id.to_string();
            metrics.gpu_memory_used
                .with_label_values(&[&device_id_str, "unknown"])
                .set(self.gpu_usage.load(Ordering::Relaxed) as f64);
        }

        Ok(handle)
    }

    /// Deallocate GPU memory
    pub fn deallocate_gpu(&self, handle: &GpuMemoryHandle) -> OpusResult<()> {
        self.gpu_usage.fetch_sub(handle.size as u64, Ordering::Relaxed);

        // Update metrics
        if let Some(metrics) = &self.metrics {
            let device_id_str = self.device_id.to_string();
            metrics.gpu_memory_used
                .with_label_values(&[&device_id_str, "unknown"])
                .set(self.gpu_usage.load(Ordering::Relaxed) as f64);
        }

        Ok(())
    }

    /// Get GPU memory usage
    pub fn gpu_usage(&self) -> f64 {
        let usage = self.gpu_usage.load(Ordering::Relaxed);
        (usage as f64 / self.gpu_capacity as f64) * 100.0
    }
}

/// GPU memory handle
#[derive(Debug, Clone)]
pub struct GpuMemoryHandle {
    pub device_id: u32,
    pub size: usize,
    pub address: u64,
}

/// Allocation statistics
#[derive(Debug)]
pub struct AllocationStatistics {
    pub total_allocated: u64,
    pub peak_allocated: u64,
    pub allocation_count: u64,
    pub pool_statistics: Vec<PoolStatistics>,
    pub large_allocations_count: usize,
}

/// Pool-specific statistics
#[derive(Debug)]
pub struct PoolStatistics {
    pub size_class: usize,
    pub total_blocks: usize,
    pub allocated_blocks: usize,
    pub utilization: f64,
}

/// Resource pool implementation for memory
pub struct MemoryResourcePool {
    allocator: Arc<LockFreeAllocator>,
    resource_type: ResourceType,
    total_capacity: u64,
}

impl MemoryResourcePool {
    /// Create new memory resource pool
    pub fn new(
        allocator: Arc<LockFreeAllocator>,
        resource_type: ResourceType,
        capacity: u64,
    ) -> Self {
        Self {
            allocator,
            resource_type,
            total_capacity: capacity,
        }
    }
}

impl ResourcePool for MemoryResourcePool {
    fn resource_type(&self) -> ResourceType {
        self.resource_type.clone()
    }

    fn allocate(&self, request: &ResourceRequest) -> OpusResult<ResourceAllocation> {
        let alignment = request.constraints.alignment.unwrap_or(64);
        let ptr = self.allocator.allocate(request.amount as usize, Some(alignment))?;

        let handle = ResourceHandle {
            id: format!("mem_{}", uuid::Uuid::new_v4()),
            resource_type: request.resource_type.clone(),
            size: request.amount,
            address: Some(ptr.as_ptr() as usize),
            device_id: None,
        };

        Ok(ResourceAllocation {
            id: request.id.clone(),
            resource_type: request.resource_type.clone(),
            amount: request.amount,
            timestamp: std::time::Instant::now(),
            handle,
        })
    }

    fn deallocate(&self, handle: &ResourceHandle) -> OpusResult<()> {
        if let Some(address) = handle.address {
            let ptr = NonNull::new(address as *mut u8).ok_or_else(|| {
                OpusError::memory_error("Invalid memory address for deallocation", handle.size)
            })?;

            self.allocator.deallocate(ptr, handle.size as usize)?;
        }

        Ok(())
    }

    fn usage(&self) -> ResourceUsage {
        let stats = self.allocator.statistics();
        ResourceUsage {
            total: self.total_capacity,
            allocated: stats.total_allocated,
            peak: stats.peak_allocated,
            utilization: (stats.total_allocated as f64 / self.total_capacity as f64) * 100.0,
            active_allocations: stats.allocation_count as u32,
            average_allocation_size: if stats.allocation_count > 0 {
                stats.total_allocated / stats.allocation_count
            } else {
                0
            },
        }
    }

    fn can_allocate(&self, request: &ResourceRequest) -> bool {
        let stats = self.allocator.statistics();
        let available = self.total_capacity.saturating_sub(stats.total_allocated);
        available >= request.amount
    }

    fn capacity(&self) -> u64 {
        self.total_capacity
    }
}

/// Align size to specified alignment
fn align_size(size: usize, alignment: usize) -> usize {
    (size + alignment - 1) & !(alignment - 1)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_align_size() {
        assert_eq!(align_size(100, 64), 128);
        assert_eq!(align_size(64, 64), 64);
        assert_eq!(align_size(65, 64), 128);
        assert_eq!(align_size(1, 64), 64);
    }

    #[test]
    fn test_allocator_config() {
        let config = AllocatorConfig::default();
        assert!(!config.size_classes.is_empty());
        assert!(config.large_allocation_threshold > 0);
        assert!(config.initial_blocks_per_pool > 0);
    }

    #[test]
    fn test_allocator_creation() {
        let config = AllocatorConfig::default();
        let allocator = LockFreeAllocator::new(config, None).unwrap();

        let stats = allocator.statistics();
        assert_eq!(stats.total_allocated, 0);
        assert_eq!(stats.allocation_count, 0);
    }

    #[test]
    fn test_small_allocation() {
        let config = AllocatorConfig::default();
        let allocator = LockFreeAllocator::new(config, None).unwrap();

        let ptr = allocator.allocate(128, None).unwrap();
        assert!(!ptr.as_ptr().is_null());

        allocator.deallocate(ptr, 128).unwrap();

        let stats = allocator.statistics();
        assert_eq!(stats.total_allocated, 0);
    }

    #[test]
    fn test_gpu_memory_allocator() {
        let config = AllocatorConfig::default();
        let system_allocator = Arc::new(LockFreeAllocator::new(config, None).unwrap());

        let gpu_allocator = GpuMemoryAllocator::new(
            0,
            8 * 1024 * 1024 * 1024, // 8GB
            system_allocator,
            None,
        );

        let handle = gpu_allocator.allocate_gpu(1024 * 1024).unwrap();
        assert_eq!(handle.device_id, 0);
        assert_eq!(handle.size, 1024 * 1024);

        let usage_before = gpu_allocator.gpu_usage();
        gpu_allocator.deallocate_gpu(&handle).unwrap();
        let usage_after = gpu_allocator.gpu_usage();

        assert!(usage_before > usage_after);
    }

    #[test]
    fn test_memory_resource_pool() {
        let config = AllocatorConfig::default();
        let allocator = Arc::new(LockFreeAllocator::new(config, None).unwrap());

        let pool = MemoryResourcePool::new(
            allocator,
            ResourceType::SystemMemory,
            16 * 1024 * 1024 * 1024, // 16GB
        );

        let request = ResourceRequest::new(
            "test_alloc",
            ResourceType::SystemMemory,
            1024 * 1024,
            100,
        );

        assert!(pool.can_allocate(&request));

        let allocation = pool.allocate(&request).unwrap();
        assert_eq!(allocation.amount, 1024 * 1024);

        let usage = pool.usage();
        assert!(usage.allocated > 0);

        pool.deallocate(&allocation.handle).unwrap();
    }
}