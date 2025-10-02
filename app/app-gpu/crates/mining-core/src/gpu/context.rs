//! # CUDA Context Management (Quản lý CUDA Context)
//!
//! **CUDA context lifecycle** (vòng đời CUDA context) với creation, switching, cleanup.

use super::error::{GpuError, GpuResult};
use cuda_runtime_sys::*;
use parking_lot::Mutex;
use std::collections::HashMap;
use std::sync::Arc;
use tracing::{debug, info, warn};

/// **CudaContext** (CUDA context) – manages CUDA context for a device
pub struct CudaContext {
    /// **Device ID** (ID thiết bị) – GPU device index
    device_id: usize,

    /// **Initialized** (đã khởi tạo) – context creation status
    initialized: bool,

    /// **Stream** – CUDA stream handle (optional)
    stream: Option<cudaStream_t>,
}

impl CudaContext {
    /// **Create new context** (tạo context mới) – without initialization
    pub fn new(device_id: usize) -> Self {
        debug!("Creating CUDA context for device {}", device_id);
        Self {
            device_id,
            initialized: false,
            stream: None,
        }
    }

    /// **Initialize context** (khởi tạo context) – set device and create stream
    pub fn initialize(&mut self) -> GpuResult<()> {
        if self.initialized {
            return Err(GpuError::ContextAlreadyExists(self.device_id));
        }

        info!("🔧 Initializing CUDA context for device {}", self.device_id);

        // Set current device (đặt thiết bị hiện tại)
        unsafe {
            let result = cudaSetDevice(self.device_id as i32);
            if result != cudaError::cudaSuccess {
                return Err(GpuError::CudaInitFailed {
                    device_id: self.device_id,
                    reason: format!("cudaSetDevice failed with error code: {:?}", result),
                });
            }
        }

        // Reset device to clear any previous state (reset thiết bị để xóa trạng thái cũ)
        unsafe {
            let result = cudaDeviceReset();
            if result != cudaError::cudaSuccess {
                warn!(
                    "⚠️  cudaDeviceReset failed for device {}: {:?}",
                    self.device_id, result
                );
            }
        }

        // Create CUDA stream (tạo stream CUDA)
        let mut stream: cudaStream_t = std::ptr::null_mut();
        unsafe {
            let result = cudaStreamCreate(&mut stream as *mut _);
            if result != cudaError::cudaSuccess {
                return Err(GpuError::CudaInitFailed {
                    device_id: self.device_id,
                    reason: format!("cudaStreamCreate failed with error code: {:?}", result),
                });
            }
        }

        self.stream = Some(stream);
        self.initialized = true;

        info!("✅ CUDA context initialized for device {}", self.device_id);
        Ok(())
    }

    /// **Is initialized** (đã khởi tạo chưa) – check initialization status
    pub fn is_initialized(&self) -> bool {
        self.initialized
    }

    /// **Get device ID** (lấy ID thiết bị)
    pub fn device_id(&self) -> usize {
        self.device_id
    }

    /// **Get stream** (lấy stream) – CUDA stream handle
    pub fn stream(&self) -> GpuResult<cudaStream_t> {
        self.stream
            .ok_or_else(|| GpuError::ContextNotInitialized(self.device_id))
    }

    /// **Set device current** (đặt thiết bị hiện tại) – switch to this context
    pub fn set_current(&self) -> GpuResult<()> {
        if !self.initialized {
            return Err(GpuError::ContextNotInitialized(self.device_id));
        }

        unsafe {
            let result = cudaSetDevice(self.device_id as i32);
            if result != cudaError::cudaSuccess {
                return Err(GpuError::CudaInitFailed {
                    device_id: self.device_id,
                    reason: format!("cudaSetDevice failed: {:?}", result),
                });
            }
        }

        Ok(())
    }

    /// **Synchronize** (đồng bộ hóa) – wait for all operations to complete
    pub fn synchronize(&self) -> GpuResult<()> {
        if !self.initialized {
            return Err(GpuError::ContextNotInitialized(self.device_id));
        }

        if let Some(stream) = self.stream {
            unsafe {
                let result = cudaStreamSynchronize(stream);
                if result != cudaError::cudaSuccess {
                    return Err(GpuError::Generic(format!(
                        "cudaStreamSynchronize failed: {:?}",
                        result
                    )));
                }
            }
        }

        Ok(())
    }

    /// **Cleanup** (dọn dẹp) – destroy stream and reset device
    pub fn cleanup(&mut self) -> GpuResult<()> {
        if !self.initialized {
            return Ok(());
        }

        info!("🧹 Cleaning up CUDA context for device {}", self.device_id);

        // Destroy stream (hủy stream)
        if let Some(stream) = self.stream.take() {
            unsafe {
                let result = cudaStreamDestroy(stream);
                if result != cudaError::cudaSuccess {
                    warn!(
                        "⚠️  cudaStreamDestroy failed for device {}: {:?}",
                        self.device_id, result
                    );
                }
            }
        }

        // Reset device (reset thiết bị)
        unsafe {
            let result = cudaDeviceReset();
            if result != cudaError::cudaSuccess {
                warn!(
                    "⚠️  cudaDeviceReset failed for device {}: {:?}",
                    self.device_id, result
                );
            }
        }

        self.initialized = false;
        info!("✅ CUDA context cleanup complete for device {}", self.device_id);

        Ok(())
    }
}

impl Drop for CudaContext {
    fn drop(&mut self) {
        if self.initialized {
            let _ = self.cleanup();
        }
    }
}

/// **CudaContextManager** (trình quản lý context CUDA) – manages multiple contexts
pub struct CudaContextManager {
    /// **Contexts** (các context) – map device_id → context
    contexts: Arc<Mutex<HashMap<usize, CudaContext>>>,
}

impl CudaContextManager {
    /// **Create new manager** (tạo trình quản lý mới)
    pub fn new() -> Self {
        Self {
            contexts: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// **Initialize context** (khởi tạo context) – for device
    pub fn initialize_context(&self, device_id: usize) -> GpuResult<()> {
        let mut contexts = self.contexts.lock();

        // Check if already exists (kiểm tra đã tồn tại chưa)
        if contexts.contains_key(&device_id) {
            return Err(GpuError::ContextAlreadyExists(device_id));
        }

        // Create and initialize (tạo và khởi tạo)
        let mut context = CudaContext::new(device_id);
        context.initialize()?;

        contexts.insert(device_id, context);
        Ok(())
    }

    /// **Set current context** (đặt context hiện tại) – for device
    pub fn set_current_context(&self, device_id: usize) -> GpuResult<()> {
        let contexts = self.contexts.lock();
        let context = contexts
            .get(&device_id)
            .ok_or_else(|| GpuError::ContextNotInitialized(device_id))?;

        context.set_current()
    }

    /// **Synchronize device** (đồng bộ thiết bị) – wait for operations
    pub fn synchronize(&self, device_id: usize) -> GpuResult<()> {
        let contexts = self.contexts.lock();
        let context = contexts
            .get(&device_id)
            .ok_or_else(|| GpuError::ContextNotInitialized(device_id))?;

        context.synchronize()
    }

    /// **Cleanup device** (dọn dẹp thiết bị) – destroy context
    pub fn cleanup_device(&self, device_id: usize) -> GpuResult<()> {
        let mut contexts = self.contexts.lock();
        if let Some(mut context) = contexts.remove(&device_id) {
            context.cleanup()?;
        }
        Ok(())
    }

    /// **Cleanup all** (dọn dẹp tất cả) – destroy all contexts
    pub fn cleanup_all(&self) -> GpuResult<()> {
        info!("🧹 Cleaning up all CUDA contexts");

        let mut contexts = self.contexts.lock();
        let device_ids: Vec<usize> = contexts.keys().copied().collect();

        for device_id in device_ids {
            if let Some(mut context) = contexts.remove(&device_id) {
                context.cleanup()?;
            }
        }

        info!("✅ All CUDA contexts cleaned up");
        Ok(())
    }

    /// **Get stream** (lấy stream) – for device
    pub fn get_stream(&self, device_id: usize) -> GpuResult<cudaStream_t> {
        let contexts = self.contexts.lock();
        let context = contexts
            .get(&device_id)
            .ok_or_else(|| GpuError::ContextNotInitialized(device_id))?;

        context.stream()
    }

    /// **Get device count** (lấy số lượng thiết bị) – số contexts đã khởi tạo
    pub fn device_count(&self) -> usize {
        self.contexts.lock().len()
    }
}

impl Default for CudaContextManager {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for CudaContextManager {
    fn drop(&mut self) {
        let _ = self.cleanup_all();
    }
}

// Helper functions (hàm trợ giúp)

/// **Query CUDA device count** (truy vấn số lượng thiết bị CUDA)
pub fn query_cuda_device_count() -> GpuResult<usize> {
    let mut count: i32 = 0;
    unsafe {
        let result = cudaGetDeviceCount(&mut count as *mut _);
        if result != cudaError::cudaSuccess {
            return Err(GpuError::CudaDriverNotFound);
        }
    }
    Ok(count as usize)
}

/// **Query CUDA device properties** (truy vấn thuộc tính thiết bị CUDA)
pub fn query_cuda_device_properties(device_id: usize) -> GpuResult<cudaDeviceProp> {
    let mut props: cudaDeviceProp = unsafe { std::mem::zeroed() };
    unsafe {
        let result = cudaGetDeviceProperties(&mut props as *mut _, device_id as i32);
        if result != cudaError::cudaSuccess {
            return Err(GpuError::DeviceNotFound(device_id));
        }
    }
    Ok(props)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_context_creation() {
        let context = CudaContext::new(0);
        assert_eq!(context.device_id(), 0);
        assert!(!context.is_initialized());
    }

    #[test]
    fn test_context_manager_creation() {
        let manager = CudaContextManager::new();
        assert_eq!(manager.device_count(), 0);
    }

    // Note: Actual initialization tests require CUDA-capable GPU
    // (Lưu ý: test khởi tạo thực sự cần GPU hỗ trợ CUDA)

    #[test]
    #[ignore] // Requires CUDA GPU
    fn test_context_initialization() {
        let mut context = CudaContext::new(0);
        let result = context.initialize();
        // Will fail without GPU, but tests compilation
        if result.is_ok() {
            assert!(context.is_initialized());
        }
    }

    #[test]
    #[ignore] // Requires CUDA GPU
    fn test_device_count_query() {
        let result = query_cuda_device_count();
        // Will fail without GPU, but tests compilation
        if result.is_ok() {
            assert!(result.unwrap() > 0);
        }
    }
}
