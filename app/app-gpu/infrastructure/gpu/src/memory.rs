use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap, VecDeque};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};
use uuid::Uuid;

use crate::GpuError;

/// GPU memory allocation information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuMemory {
    /// Unique allocation ID
    pub id: Uuid,
    /// Size in bytes
    pub size: u64,
    /// Device memory pointer (platform-specific)
    pub device_ptr: u64,
    /// Host memory pointer (if pinned)
    pub host_ptr: Option<u64>,
    /// Whether memory is currently allocated
    pub allocated: bool,
    /// Allocation timestamp
    pub allocated_at: DateTime<Utc>,
    /// Memory type
    pub memory_type: MemoryType,
    /// Allocation tags for debugging
    pub tags: Vec<String>,
}

/// Memory type enumeration
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum MemoryType {
    /// Device memory
    Device,
    /// Host pinned memory
    HostPinned,
    /// Unified memory (CUDA)
    Unified,
    /// Mapped memory
    Mapped,
}

/// Memory allocation request
#[derive(Debug, Clone)]
pub struct MemoryRequest {
    /// Requested size in bytes
    pub size: u64,
    /// Preferred memory type
    pub memory_type: MemoryType,
    /// Alignment requirement (power of 2)
    pub alignment: u64,
    /// Tags for tracking
    pub tags: Vec<String>,
    /// Whether allocation is temporary
    pub temporary: bool,
}

/// Memory pool configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryPoolConfig {
    /// Device ID this pool belongs to
    pub device_id: Uuid,
    /// Total pool size
    pub total_size: u64,
    /// Block size for allocation granularity
    pub block_size: u64,
    /// Maximum number of free blocks to cache
    pub max_cached_blocks: usize,
    /// Enable memory defragmentation
    pub enable_defragmentation: bool,
    /// Memory usage warning threshold (percentage)
    pub warning_threshold: f32,
    /// Memory usage critical threshold (percentage)
    pub critical_threshold: f32,
}

/// Memory pool statistics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MemoryPoolStats {
    /// Total pool size
    pub total_size: u64,
    /// Currently allocated size
    pub allocated_size: u64,
    /// Available size
    pub available_size: u64,
    /// Number of allocations
    pub allocation_count: usize,
    /// Number of free blocks
    pub free_block_count: usize,
    /// Largest free block size
    pub largest_free_block: u64,
    /// Memory fragmentation percentage
    pub fragmentation_percent: f32,
    /// Peak memory usage
    pub peak_usage: u64,
    /// Total allocations made
    pub total_allocations: u64,
    /// Total deallocations made
    pub total_deallocations: u64,
    /// Memory allocation failures
    pub allocation_failures: u64,
}

/// Free memory block
#[derive(Debug, Clone)]
struct FreeBlock {
    offset: u64,
    size: u64,
}

/// Advanced GPU memory pool with pooling and defragmentation
pub struct MemoryPool {
    config: MemoryPoolConfig,
    /// Allocated memory blocks (offset -> allocation)
    allocated_blocks: Arc<RwLock<BTreeMap<u64, GpuMemory>>>,
    /// Free memory blocks sorted by size
    free_blocks: Arc<RwLock<BTreeMap<u64, Vec<FreeBlock>>>>,
    /// Quick lookup for allocations by ID
    allocation_lookup: Arc<RwLock<HashMap<Uuid, u64>>>,
    /// Pool statistics
    stats: Arc<RwLock<MemoryPoolStats>>,
    /// Cache for recently freed blocks
    cached_blocks: Arc<RwLock<VecDeque<FreeBlock>>>,
}

impl MemoryPool {
    /// Create a new memory pool
    pub fn new(config: MemoryPoolConfig) -> Self {
        info!(
            "💾 Creating memory pool for device {} with size: {} MB",
            config.device_id,
            config.total_size / (1024 * 1024)
        );

        let initial_free_block = FreeBlock {
            offset: 0,
            size: config.total_size,
        };

        let mut free_blocks = BTreeMap::new();
        free_blocks.insert(config.total_size, vec![initial_free_block]);

        let stats = MemoryPoolStats {
            total_size: config.total_size,
            available_size: config.total_size,
            largest_free_block: config.total_size,
            ..Default::default()
        };

        Self {
            config,
            allocated_blocks: Arc::new(RwLock::new(BTreeMap::new())),
            free_blocks: Arc::new(RwLock::new(free_blocks)),
            allocation_lookup: Arc::new(RwLock::new(HashMap::new())),
            stats: Arc::new(RwLock::new(stats)),
            cached_blocks: Arc::new(RwLock::new(VecDeque::new())),
        }
    }

    /// Allocate memory from the pool
    pub async fn allocate(&self, request: MemoryRequest) -> Result<GpuMemory> {
        let aligned_size = self.align_size(request.size, request.alignment);

        debug!(
            "🔍 Allocating {} bytes (aligned: {}, type: {:?})",
            request.size, aligned_size, request.memory_type
        );

        // Find suitable free block
        let block_offset = self.find_free_block(aligned_size).await?;

        // Create allocation
        let allocation = GpuMemory {
            id: Uuid::new_v4(),
            size: aligned_size,
            device_ptr: block_offset,
            host_ptr: None,
            allocated: true,
            allocated_at: Utc::now(),
            memory_type: request.memory_type,
            tags: request.tags,
        };

        // Update tracking structures
        {
            let mut allocated = self.allocated_blocks.write().await;
            allocated.insert(block_offset, allocation.clone());

            let mut lookup = self.allocation_lookup.write().await;
            lookup.insert(allocation.id, block_offset);
        }

        // Update statistics
        self.update_stats_on_allocate(aligned_size).await;

        // Check memory pressure
        self.check_memory_pressure().await;

        info!(
            "✅ Allocated {} bytes at offset {} (ID: {})",
            aligned_size, block_offset, allocation.id
        );

        Ok(allocation)
    }

    /// Deallocate memory back to the pool
    pub async fn deallocate(&self, allocation_id: Uuid) -> Result<()> {
        debug!("🗑️ Deallocating memory: {}", allocation_id);

        // Find allocation
        let (offset, allocation) = {
            let lookup = self.allocation_lookup.read().await;
            let offset = lookup.get(&allocation_id)
                .ok_or_else(|| GpuError::MemoryAllocationFailed("Allocation not found".to_string()))?;

            let allocated = self.allocated_blocks.read().await;
            let allocation = allocated.get(offset)
                .ok_or_else(|| GpuError::MemoryAllocationFailed("Allocation block not found".to_string()))?
                .clone();

            (*offset, allocation)
        };

        // Remove from tracking
        {
            let mut allocated = self.allocated_blocks.write().await;
            allocated.remove(&offset);

            let mut lookup = self.allocation_lookup.write().await;
            lookup.remove(&allocation_id);
        }

        // Return block to free list
        self.return_free_block(offset, allocation.size).await;

        // Update statistics
        self.update_stats_on_deallocate(allocation.size).await;

        info!(
            "✅ Deallocated {} bytes at offset {} (ID: {})",
            allocation.size, offset, allocation_id
        );

        Ok(())
    }

    /// Find a suitable free block for allocation
    async fn find_free_block(&self, size: u64) -> Result<u64> {
        let mut free_blocks = self.free_blocks.write().await;

        // Try to find exact or larger block
        for (&block_size, blocks) in free_blocks.range_mut(size..) {
            if let Some(block) = blocks.pop() {
                let offset = block.offset;

                // If block is larger, split it
                if block.size > size {
                    let remaining_size = block.size - size;
                    let remaining_block = FreeBlock {
                        offset: offset + size,
                        size: remaining_size,
                    };

                    free_blocks
                        .entry(remaining_size)
                        .or_insert_with(Vec::new)
                        .push(remaining_block);
                }

                // Remove empty block list
                if blocks.is_empty() {
                    free_blocks.remove(&block_size);
                }

                return Ok(offset);
            }
        }

        // Try cached blocks if no suitable block found
        {
            let mut cached = self.cached_blocks.write().await;
            while let Some(block) = cached.pop_front() {
                if block.size >= size {
                    // Return to free blocks
                    free_blocks
                        .entry(block.size)
                        .or_insert_with(Vec::new)
                        .push(block);

                    // Retry allocation
                    drop(cached);
                    drop(free_blocks);
                    return self.find_free_block(size).await;
                }
            }
        }

        // Try defragmentation if enabled
        if self.config.enable_defragmentation {
            self.defragment().await?;
            drop(free_blocks);
            return self.find_free_block(size).await;
        }

        Err(GpuError::InsufficientMemory {
            required: size,
            available: self.get_largest_free_block().await,
        }.into())
    }

    /// Return a block to the free list
    async fn return_free_block(&self, offset: u64, size: u64) {
        let block = FreeBlock { offset, size };

        // Try to cache the block for quick reuse
        {
            let mut cached = self.cached_blocks.write().await;
            if cached.len() < self.config.max_cached_blocks {
                cached.push_back(block);
                return;
            }
        }

        // Add to free blocks
        let mut free_blocks = self.free_blocks.write().await;
        free_blocks
            .entry(size)
            .or_insert_with(Vec::new)
            .push(block);

        // Try to coalesce adjacent blocks
        drop(free_blocks);
        self.coalesce_free_blocks().await;
    }

    /// Coalesce adjacent free blocks to reduce fragmentation
    async fn coalesce_free_blocks(&self) {
        let mut free_blocks = self.free_blocks.write().await;
        let mut all_blocks: Vec<FreeBlock> = Vec::new();

        // Collect all free blocks
        for blocks in free_blocks.values() {
            all_blocks.extend(blocks.iter().cloned());
        }

        // Sort by offset
        all_blocks.sort_by_key(|block| block.offset);

        // Coalesce adjacent blocks
        let mut coalesced = Vec::new();
        let mut current_block: Option<FreeBlock> = None;

        for block in all_blocks {
            match current_block {
                None => current_block = Some(block),
                Some(mut current) => {
                    if current.offset + current.size == block.offset {
                        // Adjacent blocks, merge them
                        current.size += block.size;
                        current_block = Some(current);
                    } else {
                        // Not adjacent, save current and start new
                        coalesced.push(current);
                        current_block = Some(block);
                    }
                }
            }
        }

        if let Some(block) = current_block {
            coalesced.push(block);
        }

        // Rebuild free blocks map
        free_blocks.clear();
        for block in coalesced {
            free_blocks
                .entry(block.size)
                .or_insert_with(Vec::new)
                .push(block);
        }

        debug!("🔧 Coalesced free blocks, {} blocks remaining", free_blocks.len());
    }

    /// Defragment memory pool
    async fn defragment(&self) -> Result<()> {
        warn!("🔧 Starting memory defragmentation");

        // This is a simplified defragmentation
        // In a real implementation, you would need to:
        // 1. Track movable allocations
        // 2. Compact memory by moving allocations
        // 3. Update device pointers
        // 4. Notify allocation owners of new addresses

        self.coalesce_free_blocks().await;

        info!("✅ Memory defragmentation completed");
        Ok(())
    }

    /// Align size to specified alignment
    fn align_size(&self, size: u64, alignment: u64) -> u64 {
        if alignment <= 1 {
            return (size + self.config.block_size - 1) & !(self.config.block_size - 1);
        }

        (size + alignment - 1) & !(alignment - 1)
    }

    /// Get largest available free block
    async fn get_largest_free_block(&self) -> u64 {
        let free_blocks = self.free_blocks.read().await;
        free_blocks.keys().last().cloned().unwrap_or(0)
    }

    /// Update statistics on allocation
    async fn update_stats_on_allocate(&self, size: u64) {
        let mut stats = self.stats.write().await;
        stats.allocated_size += size;
        stats.available_size = stats.total_size - stats.allocated_size;
        stats.allocation_count += 1;
        stats.total_allocations += 1;
        stats.peak_usage = stats.peak_usage.max(stats.allocated_size);

        // Update largest free block
        drop(stats);
        let largest = self.get_largest_free_block().await;
        let mut stats = self.stats.write().await;
        stats.largest_free_block = largest;

        // Calculate fragmentation
        if stats.available_size > 0 {
            stats.fragmentation_percent =
                (1.0 - (largest as f32 / stats.available_size as f32)) * 100.0;
        }
    }

    /// Update statistics on deallocation
    async fn update_stats_on_deallocate(&self, size: u64) {
        let mut stats = self.stats.write().await;
        stats.allocated_size -= size;
        stats.available_size = stats.total_size - stats.allocated_size;
        stats.allocation_count -= 1;
        stats.total_deallocations += 1;

        // Update free block count
        let free_blocks = self.free_blocks.read().await;
        stats.free_block_count = free_blocks.values().map(|v| v.len()).sum();
        drop(free_blocks);

        // Update largest free block and fragmentation
        drop(stats);
        let largest = self.get_largest_free_block().await;
        let mut stats = self.stats.write().await;
        stats.largest_free_block = largest;

        if stats.available_size > 0 {
            stats.fragmentation_percent =
                (1.0 - (largest as f32 / stats.available_size as f32)) * 100.0;
        }
    }

    /// Check memory pressure and warn if necessary
    async fn check_memory_pressure(&self) {
        let stats = self.stats.read().await;
        let usage_percent = (stats.allocated_size as f32 / stats.total_size as f32) * 100.0;

        if usage_percent >= self.config.critical_threshold {
            error!(
                "🚨 Critical memory pressure: {:.1}% used ({} MB / {} MB)",
                usage_percent,
                stats.allocated_size / (1024 * 1024),
                stats.total_size / (1024 * 1024)
            );
        } else if usage_percent >= self.config.warning_threshold {
            warn!(
                "⚠️ High memory usage: {:.1}% used ({} MB / {} MB)",
                usage_percent,
                stats.allocated_size / (1024 * 1024),
                stats.total_size / (1024 * 1024)
            );
        }
    }

    /// Get current pool statistics
    pub async fn get_stats(&self) -> MemoryPoolStats {
        let mut stats = self.stats.read().await.clone();

        // Update real-time values
        let free_blocks = self.free_blocks.read().await;
        stats.free_block_count = free_blocks.values().map(|v| v.len()).sum();
        stats.largest_free_block = free_blocks.keys().last().cloned().unwrap_or(0);

        if stats.available_size > 0 {
            stats.fragmentation_percent =
                (1.0 - (stats.largest_free_block as f32 / stats.available_size as f32)) * 100.0;
        }

        stats
    }

    /// Get allocation by ID
    pub async fn get_allocation(&self, allocation_id: Uuid) -> Result<GpuMemory> {
        let lookup = self.allocation_lookup.read().await;
        let offset = lookup.get(&allocation_id)
            .ok_or_else(|| GpuError::MemoryAllocationFailed("Allocation not found".to_string()))?;

        let allocated = self.allocated_blocks.read().await;
        let allocation = allocated.get(offset)
            .ok_or_else(|| GpuError::MemoryAllocationFailed("Allocation block not found".to_string()))?
            .clone();

        Ok(allocation)
    }

    /// List all current allocations
    pub async fn list_allocations(&self) -> Vec<GpuMemory> {
        let allocated = self.allocated_blocks.read().await;
        allocated.values().cloned().collect()
    }

    /// Clear all allocations (for testing/cleanup)
    pub async fn clear(&self) -> Result<()> {
        warn!("🧹 Clearing all memory pool allocations");

        {
            let mut allocated = self.allocated_blocks.write().await;
            allocated.clear();

            let mut lookup = self.allocation_lookup.write().await;
            lookup.clear();

            let mut cached = self.cached_blocks.write().await;
            cached.clear();
        }

        // Reset free blocks to initial state
        {
            let mut free_blocks = self.free_blocks.write().await;
            free_blocks.clear();

            let initial_block = FreeBlock {
                offset: 0,
                size: self.config.total_size,
            };
            free_blocks.insert(self.config.total_size, vec![initial_block]);
        }

        // Reset statistics
        {
            let mut stats = self.stats.write().await;
            *stats = MemoryPoolStats {
                total_size: self.config.total_size,
                available_size: self.config.total_size,
                largest_free_block: self.config.total_size,
                ..Default::default()
            };
        }

        info!("✅ Memory pool cleared");
        Ok(())
    }
}

impl Default for MemoryPoolConfig {
    fn default() -> Self {
        Self {
            device_id: Uuid::new_v4(),
            total_size: 1024 * 1024 * 1024, // 1GB default
            block_size: 256, // 256-byte alignment
            max_cached_blocks: 100,
            enable_defragmentation: true,
            warning_threshold: 80.0,
            critical_threshold: 95.0,
        }
    }
}

impl Default for MemoryRequest {
    fn default() -> Self {
        Self {
            size: 0,
            memory_type: MemoryType::Device,
            alignment: 256,
            tags: Vec::new(),
            temporary: false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_memory_pool_basic_allocation() {
        let config = MemoryPoolConfig {
            total_size: 1024 * 1024, // 1MB
            block_size: 256,
            ..Default::default()
        };

        let pool = MemoryPool::new(config);

        let request = MemoryRequest {
            size: 1024,
            ..Default::default()
        };

        let allocation = pool.allocate(request).await.unwrap();
        assert_eq!(allocation.size, 1024);
        assert!(allocation.allocated);

        let stats = pool.get_stats().await;
        assert_eq!(stats.allocation_count, 1);
        assert_eq!(stats.allocated_size, 1024);

        pool.deallocate(allocation.id).await.unwrap();

        let stats = pool.get_stats().await;
        assert_eq!(stats.allocation_count, 0);
        assert_eq!(stats.allocated_size, 0);
    }

    #[tokio::test]
    async fn test_memory_pool_fragmentation() {
        let config = MemoryPoolConfig {
            total_size: 1024,
            block_size: 64,
            ..Default::default()
        };

        let pool = MemoryPool::new(config);

        // Allocate several blocks
        let mut allocations = Vec::new();
        for _ in 0..5 {
            let request = MemoryRequest {
                size: 64,
                ..Default::default()
            };
            let allocation = pool.allocate(request).await.unwrap();
            allocations.push(allocation);
        }

        // Deallocate every other block
        for (i, allocation) in allocations.iter().enumerate() {
            if i % 2 == 0 {
                pool.deallocate(allocation.id).await.unwrap();
            }
        }

        let stats = pool.get_stats().await;
        assert!(stats.fragmentation_percent > 0.0);
    }
}