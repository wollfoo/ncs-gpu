//! GPU Memory Management
//! 
//! Efficient memory allocation and pooling for CUDA operations

use std::sync::Arc;
use std::collections::{HashMap, VecDeque};
use anyhow::{Result, bail};
use parking_lot::RwLock;
use tracing::{debug, info, warn};

/// Memory allocation handle
pub type MemoryHandle = *mut u8;

/// Memory allocation metadata
#[derive(Debug, Clone)]
struct Allocation {
    ptr: MemoryHandle,
    size: usize,
    in_use: bool,
    allocated_at: std::time::Instant,
}

/// Memory pool for efficient allocation
pub struct MemoryPool {
    /// Total pool size in bytes
    total_size: usize,
    
    /// Available memory in bytes
    available: usize,
    
    /// Free blocks organized by size
    free_blocks: HashMap<usize, VecDeque<MemoryHandle>>,
    
    /// All allocations
    allocations: HashMap<MemoryHandle, Allocation>,
    
    /// Allocation statistics
    stats: AllocationStats,
}

#[derive(Debug, Default, Clone)]
pub struct AllocationStats {
    pub total_allocations: u64,
    pub total_deallocations: u64,
    pub current_allocations: usize,
    pub peak_memory_usage: usize,
    pub fragmentation_ratio: f32,
}

/// GPU Memory Manager
pub struct MemoryManager {
    /// Memory pools by size class
    pools: Arc<RwLock<HashMap<SizeClass, MemoryPool>>>,
    
    /// Unified memory support
    use_unified_memory: bool,
    
    /// Total memory limit in MB
    memory_limit_mb: usize,
    
    /// Current memory usage in bytes
    current_usage: Arc<RwLock<usize>>,
}

/// Size classes for memory pooling
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum SizeClass {
    Tiny,      // < 1KB
    Small,     // 1KB - 64KB
    Medium,    // 64KB - 1MB
    Large,     // 1MB - 16MB
    Huge,      // > 16MB
}

impl SizeClass {
    fn from_size(size: usize) -> Self {
        match size {
            0..=1024 => SizeClass::Tiny,
            1025..=65536 => SizeClass::Small,
            65537..=1048576 => SizeClass::Medium,
            1048577..=16777216 => SizeClass::Large,
            _ => SizeClass::Huge,
        }
    }
    
    fn pool_size(&self) -> usize {
        match self {
            SizeClass::Tiny => 1024 * 1024,        // 1MB pool
            SizeClass::Small => 16 * 1024 * 1024,  // 16MB pool
            SizeClass::Medium => 64 * 1024 * 1024, // 64MB pool
            SizeClass::Large => 256 * 1024 * 1024, // 256MB pool
            SizeClass::Huge => 512 * 1024 * 1024,  // 512MB pool
        }
    }
}

impl MemoryManager {
    /// Create new memory manager
    pub fn new() -> Self {
        Self {
            pools: Arc::new(RwLock::new(HashMap::new())),
            use_unified_memory: false,
            memory_limit_mb: 0,
            current_usage: Arc::new(RwLock::new(0)),
        }
    }
    
    /// Initialize memory manager with limit
    pub fn initialize(&self, memory_limit_mb: usize) -> Result<()> {
        info!("Initializing memory manager with {} MB limit", memory_limit_mb);
        
        // Update limit
        let mut pools = self.pools.write();
        
        // Pre-allocate pools for each size class
        for size_class in [
            SizeClass::Tiny,
            SizeClass::Small,
            SizeClass::Medium,
            SizeClass::Large,
            SizeClass::Huge,
        ] {
            let pool_size = size_class.pool_size().min(memory_limit_mb * 1024 * 1024 / 5);
            
            pools.insert(size_class, MemoryPool::new(pool_size));
            
            debug!("Created {:?} pool with {} MB", 
                   size_class, pool_size / 1024 / 1024);
        }
        
        Ok(())
    }
    
    /// Allocate GPU memory
    pub fn allocate(&self, size: usize) -> Result<MemoryHandle> {
        // Check memory limit
        {
            let current = *self.current_usage.read();
            if current + size > self.memory_limit_mb * 1024 * 1024 {
                bail!("Memory allocation would exceed limit");
            }
        }
        
        let size_class = SizeClass::from_size(size);
        let mut pools = self.pools.write();
        
        // Get or create pool for size class
        let pool = pools.entry(size_class)
            .or_insert_with(|| MemoryPool::new(size_class.pool_size()));
        
        // Try to allocate from pool
        if let Some(ptr) = pool.allocate(size)? {
            // Update usage
            *self.current_usage.write() += size;
            
            debug!("Allocated {} bytes from {:?} pool", size, size_class);
            return Ok(ptr);
        }
        
        // Pool allocation failed, try direct allocation
        let ptr = self.allocate_direct(size)?;
        
        // Track allocation
        pool.track_external_allocation(ptr, size);
        
        // Update usage
        *self.current_usage.write() += size;
        
        Ok(ptr)
    }
    
    /// Free GPU memory
    pub fn free(&self, ptr: MemoryHandle) -> Result<()> {
        let mut pools = self.pools.write();
        
        // Find which pool owns this allocation
        for (size_class, pool) in pools.iter_mut() {
            if let Some(size) = pool.free(ptr) {
                // Update usage
                *self.current_usage.write() -= size;
                
                debug!("Freed {} bytes to {:?} pool", size, size_class);
                return Ok(());
            }
        }
        
        warn!("Attempted to free untracked pointer: {:?}", ptr);
        Ok(())
    }
    
    /// Allocate memory directly from CUDA
    fn allocate_direct(&self, size: usize) -> Result<MemoryHandle> {
        // In actual implementation, would use cuMemAlloc
        // For now, use standard allocation as placeholder
        
        let layout = std::alloc::Layout::from_size_align(size, 256)
            .map_err(|e| anyhow::anyhow!("Invalid layout: {}", e))?;
        
        let ptr = unsafe {
            std::alloc::alloc(layout)
        };
        
        if ptr.is_null() {
            bail!("Failed to allocate {} bytes", size);
        }
        
        Ok(ptr)
    }
    
    /// Free memory directly to CUDA
    fn free_direct(&self, ptr: MemoryHandle, size: usize) -> Result<()> {
        // In actual implementation, would use cuMemFree
        
        let layout = std::alloc::Layout::from_size_align(size, 256)
            .map_err(|e| anyhow::anyhow!("Invalid layout: {}", e))?;
        
        unsafe {
            std::alloc::dealloc(ptr, layout);
        }
        
        Ok(())
    }
    
    /// Get total memory in MB
    pub fn total_memory_mb(&self) -> usize {
        self.memory_limit_mb
    }
    
    /// Get current usage in MB
    pub fn current_usage_mb(&self) -> usize {
        *self.current_usage.read() / 1024 / 1024
    }
    
    /// Get memory statistics
    pub fn get_stats(&self) -> HashMap<String, AllocationStats> {
        let pools = self.pools.read();
        let mut stats = HashMap::new();
        
        for (size_class, pool) in pools.iter() {
            stats.insert(format!("{:?}", size_class), pool.stats.clone());
        }
        
        stats
    }
    
    /// Cleanup memory manager
    pub fn cleanup(&self) -> Result<()> {
        info!("Cleaning up memory manager");
        
        let mut pools = self.pools.write();
        
        for (size_class, pool) in pools.iter_mut() {
            pool.cleanup()?;
            debug!("Cleaned up {:?} pool", size_class);
        }
        
        pools.clear();
        *self.current_usage.write() = 0;
        
        Ok(())
    }
}

impl MemoryPool {
    fn new(total_size: usize) -> Self {
        Self {
            total_size,
            available: total_size,
            free_blocks: HashMap::new(),
            allocations: HashMap::new(),
            stats: AllocationStats::default(),
        }
    }
    
    fn allocate(&mut self, size: usize) -> Result<Option<MemoryHandle>> {
        // Round up to alignment
        let aligned_size = (size + 255) & !255;
        
        // Check if we have a free block of this size
        if let Some(queue) = self.free_blocks.get_mut(&aligned_size) {
            if let Some(ptr) = queue.pop_front() {
                // Mark as in use
                if let Some(alloc) = self.allocations.get_mut(&ptr) {
                    alloc.in_use = true;
                    alloc.allocated_at = std::time::Instant::now();
                }
                
                self.available -= aligned_size;
                self.stats.current_allocations += 1;
                self.stats.total_allocations += 1;
                
                return Ok(Some(ptr));
            }
        }
        
        // No suitable block found
        Ok(None)
    }
    
    fn free(&mut self, ptr: MemoryHandle) -> Option<usize> {
        if let Some(alloc) = self.allocations.get_mut(&ptr) {
            if !alloc.in_use {
                warn!("Double free detected for {:?}", ptr);
                return None;
            }
            
            alloc.in_use = false;
            let size = alloc.size;
            
            // Add to free list
            self.free_blocks
                .entry(size)
                .or_insert_with(VecDeque::new)
                .push_back(ptr);
            
            self.available += size;
            self.stats.current_allocations -= 1;
            self.stats.total_deallocations += 1;
            
            return Some(size);
        }
        
        None
    }
    
    fn track_external_allocation(&mut self, ptr: MemoryHandle, size: usize) {
        self.allocations.insert(ptr, Allocation {
            ptr,
            size,
            in_use: true,
            allocated_at: std::time::Instant::now(),
        });
        
        self.stats.current_allocations += 1;
        self.stats.total_allocations += 1;
    }
    
    fn cleanup(&mut self) -> Result<()> {
        // Free all allocations
        for (ptr, alloc) in self.allocations.iter() {
            if alloc.in_use {
                warn!("Memory leak detected: {} bytes at {:?}", alloc.size, ptr);
            }
            // Would call cuMemFree here
        }
        
        self.allocations.clear();
        self.free_blocks.clear();
        self.available = self.total_size;
        
        Ok(())
    }
}

/// Unified memory allocation
pub struct UnifiedMemory {
    ptr: MemoryHandle,
    size: usize,
    is_device_accessible: bool,
    is_host_accessible: bool,
}

impl UnifiedMemory {
    /// Allocate unified memory accessible by both CPU and GPU
    pub fn allocate(size: usize) -> Result<Self> {
        // In actual implementation, would use cudaMallocManaged
        
        let layout = std::alloc::Layout::from_size_align(size, 256)
            .map_err(|e| anyhow::anyhow!("Invalid layout: {}", e))?;
        
        let ptr = unsafe {
            std::alloc::alloc_zeroed(layout)
        };
        
        if ptr.is_null() {
            bail!("Failed to allocate unified memory");
        }
        
        Ok(Self {
            ptr,
            size,
            is_device_accessible: true,
            is_host_accessible: true,
        })
    }
    
    /// Get pointer for CPU access
    pub fn host_ptr(&self) -> *mut u8 {
        self.ptr
    }
    
    /// Get pointer for GPU access
    pub fn device_ptr(&self) -> *mut u8 {
        self.ptr
    }
    
    /// Prefetch to device
    pub fn prefetch_to_device(&self, device_id: u32) -> Result<()> {
        // Would call cudaMemPrefetchAsync
        debug!("Prefetching {} bytes to device {}", self.size, device_id);
        Ok(())
    }
    
    /// Prefetch to host
    pub fn prefetch_to_host(&self) -> Result<()> {
        // Would call cudaMemPrefetchAsync with CPU device
        debug!("Prefetching {} bytes to host", self.size);
        Ok(())
    }
}

impl Drop for UnifiedMemory {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            let layout = std::alloc::Layout::from_size_align(self.size, 256).unwrap();
            unsafe {
                std::alloc::dealloc(self.ptr, layout);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_memory_allocation() {
        let manager = MemoryManager::new();
        manager.initialize(100).unwrap();
        
        // Allocate small buffer
        let ptr1 = manager.allocate(1024).unwrap();
        assert!(!ptr1.is_null());
        
        // Allocate medium buffer
        let ptr2 = manager.allocate(65536).unwrap();
        assert!(!ptr2.is_null());
        
        // Free buffers
        manager.free(ptr1).unwrap();
        manager.free(ptr2).unwrap();
        
        // Check stats
        let stats = manager.get_stats();
        assert!(!stats.is_empty());
    }
    
    #[test]
    fn test_unified_memory() {
        let mem = UnifiedMemory::allocate(1024).unwrap();
        
        assert!(!mem.host_ptr().is_null());
        assert_eq!(mem.host_ptr(), mem.device_ptr());
        
        mem.prefetch_to_device(0).unwrap();
        mem.prefetch_to_host().unwrap();
    }
}
