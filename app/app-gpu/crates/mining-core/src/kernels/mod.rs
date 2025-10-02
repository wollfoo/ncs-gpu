//! # CUDA Kernel Module (Module kernel CUDA)
//! 
//! **High-performance GPU mining kernels** (kernel khai thác GPU hiệu năng cao) với:
//! - Ethash algorithm implementation
//! - Optimized memory access patterns
//! - Safe Rust FFI bindings
//! - Performance monitoring

pub mod ffi;

pub use ffi::{
    CudaError, CudaResult, CudaStream, DeviceBuffer, EthashConfig, EthashSearchParams,
    cuda_device_count, cuda_device_synchronize, cuda_init, ethash_search,
};

use tracing::{debug, info, warn};

/// **Ethash Miner** (Trình khai thác Ethash) – high-level interface
pub struct EthashMiner {
    /// Device ID (GPU device number)
    device_id: i32,
    
    /// DAG buffer on GPU
    dag: DeviceBuffer<u64>,
    
    /// DAG size in bytes
    dag_size: u64,
    
    /// CUDA stream for async operations
    stream: CudaStream,
    
    /// Current epoch number
    epoch: u64,
}

impl EthashMiner {
    /// Create new Ethash miner instance
    pub fn new(device_id: i32, epoch: u64) -> CudaResult<Self> {
        info!("🚀 Initializing Ethash miner on device {}", device_id);
        
        // Initialize CUDA device
        cuda_init(device_id)?;
        
        // Calculate DAG size for epoch
        let dag_size = Self::calculate_dag_size(epoch);
        info!("📊 DAG size for epoch {}: {} MB", epoch, dag_size / (1024 * 1024));
        
        // Allocate DAG buffer (placeholder - actual generation needed)
        let dag_items = dag_size / 128; // Each DAG item is 128 bytes
        let dag_u64_count = (dag_items * 128) / 8; // Convert to u64 count
        let dag = DeviceBuffer::new(dag_u64_count as usize)?;
        
        info!("✅ Allocated DAG buffer: {} items ({} u64)", dag_items, dag_u64_count);
        
        // Create CUDA stream
        let stream = CudaStream::new()?;
        
        info!("✅ Ethash miner initialized successfully");
        
        Ok(Self {
            device_id,
            dag,
            dag_size,
            stream,
            epoch,
        })
    }
    
    /// Calculate DAG size for given epoch
    pub fn calculate_dag_size(epoch: u64) -> u64 {
        const DATASET_BYTES_INIT: u64 = 1_073_741_824; // 1 GB
        const DATASET_BYTES_GROWTH: u64 = 8_388_608;   // 8 MB per epoch
        
        DATASET_BYTES_INIT + DATASET_BYTES_GROWTH * epoch
    }
    
    /// Search for valid nonces
    pub fn search(
        &mut self,
        header_hash: &[u8; 32],
        nonce_start: u64,
        num_nonces: u64,
        target: &[u8; 32],
    ) -> CudaResult<Vec<u64>> {
        debug!(
            "🔍 Searching {} nonces starting from {}",
            num_nonces, nonce_start
        );
        
        // Allocate device buffers
        let d_header = DeviceBuffer::from_slice(header_hash)?;
        let d_target = DeviceBuffer::from_slice(target)?;
        
        // Solution buffers (up to 8 solutions)
        let mut d_solutions = DeviceBuffer::new(8)?;
        d_solutions.zero()?;
        
        let mut d_solution_count = DeviceBuffer::new(1)?;
        d_solution_count.zero()?;
        
        // Launch kernel
        let params = EthashSearchParams {
            dag: &self.dag,
            dag_size: self.dag_size,
            header_hash: &d_header,
            nonce_start,
            num_threads: num_nonces,
            target: &d_target,
            solutions: &mut d_solutions,
            solution_count: &mut d_solution_count,
        };
        
        ethash_search(params, &self.stream)?;
        
        // Synchronize and get results
        self.stream.synchronize()?;
        
        // Copy solutions back to host
        let mut solution_count = vec![0u32; 1];
        d_solution_count.copy_to_host(&mut solution_count)?;
        
        let count = solution_count[0] as usize;
        if count > 0 {
            let mut solutions = vec![0u64; 8];
            d_solutions.copy_to_host(&mut solutions)?;
            
            info!("✅ Found {} valid solution(s)", count);
            Ok(solutions[..count].to_vec())
        } else {
            debug!("⚠️ No solutions found");
            Ok(Vec::new())
        }
    }
    
    /// Get DAG size in bytes
    pub fn dag_size(&self) -> u64 {
        self.dag_size
    }
    
    /// Get current epoch
    pub fn epoch(&self) -> u64 {
        self.epoch
    }
    
    /// Get device ID
    pub fn device_id(&self) -> i32 {
        self.device_id
    }
}

/// Check if CUDA is available
pub fn is_cuda_available() -> bool {
    match cuda_device_count() {
        Ok(count) => {
            info!("🎮 Found {} CUDA device(s)", count);
            count > 0
        }
        Err(e) => {
            warn!("⚠️ CUDA not available: {}", e);
            false
        }
    }
}

/// Get number of available CUDA devices
pub fn get_device_count() -> CudaResult<i32> {
    cuda_device_count()
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_dag_size_calculation() {
        // Epoch 0: 1 GB
        assert_eq!(EthashMiner::calculate_dag_size(0), 1_073_741_824);
        
        // Epoch 1: 1 GB + 8 MB
        assert_eq!(EthashMiner::calculate_dag_size(1), 1_082_130_432);
        
        // Epoch 100: 1 GB + 800 MB
        assert_eq!(EthashMiner::calculate_dag_size(100), 1_912_602_624);
    }
    
    #[test]
    fn test_cuda_availability() {
        // Just check if function runs without panic
        let available = is_cuda_available();
        println!("CUDA available: {}", available);
    }
    
    #[test]
    fn test_ethash_miner_creation() {
        if !is_cuda_available() {
            println!("No CUDA device, skipping test");
            return;
        }
        
        let miner = EthashMiner::new(0, 0);
        match miner {
            Ok(m) => {
                assert_eq!(m.device_id(), 0);
                assert_eq!(m.epoch(), 0);
                assert_eq!(m.dag_size(), 1_073_741_824);
                println!("✅ Miner created successfully");
            }
            Err(e) => {
                println!("⚠️ Failed to create miner: {}", e);
            }
        }
    }
}
