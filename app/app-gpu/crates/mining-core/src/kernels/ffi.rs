//! # CUDA Kernel FFI Bindings (Liên kết FFI CUDA)
//! 
//! **Safe Rust wrappers** (wrapper Rust an toàn) cho CUDA kernels với:
//! - Type-safe parameter passing (truyền tham số type-safe)
//! - Error handling (xử lý lỗi CUDA)
//! - Memory management (quản lý bộ nhớ GPU)
//! - Lifetime tracking (theo dõi thời gian sống)

use cuda_runtime_sys::*;
use std::ffi::c_void;
use std::ptr;
use thiserror::Error;

/// **CUDA Error Type** (Kiểu lỗi CUDA) – wrapper cho cudaError_t
#[derive(Debug, Error)]
pub enum CudaError {
    #[error("CUDA runtime error: {0}")]
    Runtime(String),
    
    #[error("CUDA out of memory")]
    OutOfMemory,
    
    #[error("CUDA invalid value")]
    InvalidValue,
    
    #[error("CUDA launch failed")]
    LaunchFailed,
    
    #[error("CUDA device unavailable")]
    DeviceUnavailable,
    
    #[error("Unknown CUDA error: {0}")]
    Unknown(i32),
}

impl CudaError {
    /// Convert cudaError_t to CudaError
    pub fn from_cuda(code: cudaError_t) -> Self {
        match code {
            cudaError::cudaSuccess => unreachable!("Success is not an error"),
            cudaError::cudaErrorMemoryAllocation => CudaError::OutOfMemory,
            cudaError::cudaErrorInvalidValue => CudaError::InvalidValue,
            cudaError::cudaErrorLaunchFailure => CudaError::LaunchFailed,
            cudaError::cudaErrorNoDevice | cudaError::cudaErrorInsufficientDriver => {
                CudaError::DeviceUnavailable
            }
            other => {
                let msg = unsafe {
                    let c_str = cudaGetErrorString(other);
                    if c_str.is_null() {
                        format!("CUDA error code: {}", other as i32)
                    } else {
                        std::ffi::CStr::from_ptr(c_str)
                            .to_string_lossy()
                            .into_owned()
                    }
                };
                CudaError::Runtime(msg)
            }
        }
    }
}

pub type CudaResult<T> = Result<T, CudaError>;

/// Check CUDA error và convert thành Result
#[inline]
fn check_cuda(code: cudaError_t) -> CudaResult<()> {
    if code == cudaError::cudaSuccess {
        Ok(())
    } else {
        Err(CudaError::from_cuda(code))
    }
}

// ============================================================================
// External CUDA Kernel Functions
// ============================================================================

extern "C" {
    /// Launch Ethash search kernel (từ ethash.cu)
    fn launch_ethash_search(
        d_dag: *const u64,
        dag_size: u64,
        d_header_hash: *const u8,
        nonce_start: u64,
        num_threads: u64,
        d_target: *const u8,
        d_solutions: *mut u64,
        d_solution_count: *mut u32,
        stream: cudaStream_t,
    ) -> cudaError_t;
    
    /// Get optimal Ethash kernel configuration
    fn get_ethash_optimal_config(
        block_size: *mut i32,
        num_blocks: *mut i32,
        num_threads: u64,
    ) -> cudaError_t;
}

// ============================================================================
// Safe Rust Wrappers
// ============================================================================

/// **GPU Memory Buffer** (Bộ đệm bộ nhớ GPU) – RAII wrapper cho device memory
pub struct DeviceBuffer<T> {
    ptr: *mut T,
    len: usize,
}

impl<T> DeviceBuffer<T> {
    /// Allocate device memory (cấp phát bộ nhớ GPU)
    pub fn new(len: usize) -> CudaResult<Self> {
        let mut ptr: *mut T = ptr::null_mut();
        let size_bytes = len * std::mem::size_of::<T>();
        
        let result = unsafe {
            cudaMalloc(
                &mut ptr as *mut *mut T as *mut *mut c_void,
                size_bytes,
            )
        };
        
        check_cuda(result)?;
        
        Ok(Self { ptr, len })
    }
    
    /// Allocate and copy from host (cấp phát và copy từ CPU)
    pub fn from_slice(data: &[T]) -> CudaResult<Self> {
        let buffer = Self::new(data.len())?;
        buffer.copy_from_host(data)?;
        Ok(buffer)
    }
    
    /// Copy data from host to device (copy từ CPU sang GPU)
    pub fn copy_from_host(&self, data: &[T]) -> CudaResult<()> {
        assert!(data.len() <= self.len, "Data length exceeds buffer capacity");
        
        let result = unsafe {
            cudaMemcpy(
                self.ptr as *mut c_void,
                data.as_ptr() as *const c_void,
                data.len() * std::mem::size_of::<T>(),
                cudaMemcpyKind::cudaMemcpyHostToDevice,
            )
        };
        
        check_cuda(result)
    }
    
    /// Copy data from device to host (copy từ GPU về CPU)
    pub fn copy_to_host(&self, data: &mut [T]) -> CudaResult<()> {
        assert!(data.len() <= self.len, "Data length exceeds buffer capacity");
        
        let result = unsafe {
            cudaMemcpy(
                data.as_mut_ptr() as *mut c_void,
                self.ptr as *const c_void,
                data.len() * std::mem::size_of::<T>(),
                cudaMemcpyKind::cudaMemcpyDeviceToHost,
            )
        };
        
        check_cuda(result)
    }
    
    /// Get raw device pointer (lấy con trỏ GPU thô)
    pub fn as_ptr(&self) -> *const T {
        self.ptr
    }
    
    /// Get mutable raw device pointer (lấy con trỏ GPU mutable)
    pub fn as_mut_ptr(&mut self) -> *mut T {
        self.ptr
    }
    
    /// Get buffer length (lấy độ dài buffer)
    pub fn len(&self) -> usize {
        self.len
    }
    
    /// Check if buffer is empty
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }
    
    /// Zero out device memory (xóa sạch bộ nhớ GPU)
    pub fn zero(&mut self) -> CudaResult<()> {
        let result = unsafe {
            cudaMemset(
                self.ptr as *mut c_void,
                0,
                self.len * std::mem::size_of::<T>(),
            )
        };
        check_cuda(result)
    }
}

impl<T> Drop for DeviceBuffer<T> {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            unsafe {
                // Best effort free - ignore errors in destructor
                let _ = cudaFree(self.ptr as *mut c_void);
            }
        }
    }
}

// Safety: DeviceBuffer can be sent between threads
unsafe impl<T> Send for DeviceBuffer<T> {}

/// **CUDA Stream** (Luồng CUDA) – RAII wrapper cho cudaStream_t
pub struct CudaStream {
    stream: cudaStream_t,
}

impl CudaStream {
    /// Create new CUDA stream (tạo stream mới)
    pub fn new() -> CudaResult<Self> {
        let mut stream: cudaStream_t = ptr::null_mut();
        let result = unsafe { cudaStreamCreate(&mut stream) };
        check_cuda(result)?;
        Ok(Self { stream })
    }
    
    /// Synchronize stream (đợi stream hoàn thành)
    pub fn synchronize(&self) -> CudaResult<()> {
        let result = unsafe { cudaStreamSynchronize(self.stream) };
        check_cuda(result)
    }
    
    /// Get raw stream handle (lấy handle stream thô)
    pub fn as_raw(&self) -> cudaStream_t {
        self.stream
    }
}

impl Drop for CudaStream {
    fn drop(&mut self) {
        if !self.stream.is_null() {
            unsafe {
                let _ = cudaStreamDestroy(self.stream);
            }
        }
    }
}

unsafe impl Send for CudaStream {}
unsafe impl Sync for CudaStream {}

// ============================================================================
// High-Level Kernel Wrappers
// ============================================================================

/// **Ethash Kernel Configuration** (Cấu hình kernel Ethash)
#[derive(Debug, Clone)]
pub struct EthashConfig {
    pub block_size: i32,
    pub num_blocks: i32,
}

impl EthashConfig {
    /// Get optimal configuration for given thread count
    pub fn optimal(num_threads: u64) -> CudaResult<Self> {
        let mut block_size: i32 = 0;
        let mut num_blocks: i32 = 0;
        
        let result = unsafe {
            get_ethash_optimal_config(
                &mut block_size,
                &mut num_blocks,
                num_threads,
            )
        };
        
        check_cuda(result)?;
        
        Ok(Self {
            block_size,
            num_blocks,
        })
    }
}

/// **Ethash Search Parameters** (Tham số tìm kiếm Ethash)
pub struct EthashSearchParams<'a> {
    pub dag: &'a DeviceBuffer<u64>,
    pub dag_size: u64,
    pub header_hash: &'a DeviceBuffer<u8>,
    pub nonce_start: u64,
    pub num_threads: u64,
    pub target: &'a DeviceBuffer<u8>,
    pub solutions: &'a mut DeviceBuffer<u64>,
    pub solution_count: &'a mut DeviceBuffer<u32>,
}

/// Launch Ethash search kernel (safe wrapper)
pub fn ethash_search(
    params: EthashSearchParams,
    stream: &CudaStream,
) -> CudaResult<()> {
    // Validate parameters
    assert!(params.header_hash.len() >= 32, "Header hash must be 32 bytes");
    assert!(params.target.len() >= 32, "Target must be 32 bytes");
    assert!(params.solutions.len() >= 8, "Solutions buffer too small");
    assert!(params.solution_count.len() >= 1, "Solution count buffer too small");
    
    let result = unsafe {
        launch_ethash_search(
            params.dag.as_ptr(),
            params.dag_size,
            params.header_hash.as_ptr(),
            params.nonce_start,
            params.num_threads,
            params.target.as_ptr(),
            params.solutions.as_mut_ptr(),
            params.solution_count.as_mut_ptr(),
            stream.as_raw(),
        )
    };
    
    check_cuda(result)
}

/// Initialize CUDA device (khởi tạo thiết bị CUDA)
pub fn cuda_init(device_id: i32) -> CudaResult<()> {
    let result = unsafe { cudaSetDevice(device_id) };
    check_cuda(result)
}

/// Get CUDA device count (lấy số lượng GPU)
pub fn cuda_device_count() -> CudaResult<i32> {
    let mut count: i32 = 0;
    let result = unsafe { cudaGetDeviceCount(&mut count) };
    check_cuda(result)?;
    Ok(count)
}

/// Synchronize device (đợi tất cả operations hoàn thành)
pub fn cuda_device_synchronize() -> CudaResult<()> {
    let result = unsafe { cudaDeviceSynchronize() };
    check_cuda(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_device_buffer_allocation() {
        if cuda_device_count().is_err() {
            println!("No CUDA device available, skipping test");
            return;
        }
        
        cuda_init(0).expect("Failed to initialize CUDA");
        
        let buffer: DeviceBuffer<u32> = DeviceBuffer::new(1024)
            .expect("Failed to allocate device buffer");
        
        assert_eq!(buffer.len(), 1024);
        assert!(!buffer.as_ptr().is_null());
    }
    
    #[test]
    fn test_host_device_copy() {
        if cuda_device_count().is_err() {
            println!("No CUDA device available, skipping test");
            return;
        }
        
        cuda_init(0).expect("Failed to initialize CUDA");
        
        // Allocate and copy data
        let host_data: Vec<u32> = (0..1024).collect();
        let buffer = DeviceBuffer::from_slice(&host_data)
            .expect("Failed to copy data to device");
        
        // Copy back and verify
        let mut result = vec![0u32; 1024];
        buffer.copy_to_host(&mut result)
            .expect("Failed to copy data from device");
        
        assert_eq!(host_data, result);
    }
    
    #[test]
    fn test_cuda_stream() {
        if cuda_device_count().is_err() {
            println!("No CUDA device available, skipping test");
            return;
        }
        
        cuda_init(0).expect("Failed to initialize CUDA");
        
        let stream = CudaStream::new().expect("Failed to create stream");
        stream.synchronize().expect("Failed to synchronize stream");
    }
}
