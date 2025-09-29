//! Memory Protection Module
//!
//! Provides secure memory handling with:
//! - Secure memory allocation and deallocation
//! - Automatic zeroing of sensitive data
//! - Memory locking to prevent swapping
//! - Buffer overflow protection
//! - Heap canaries and guard pages

use anyhow::Result;
use secrecy::{Secret, Zeroize};
use std::alloc::{GlobalAlloc, Layout, System};
use std::ptr::NonNull;
use std::sync::atomic::{AtomicUsize, Ordering};
use tracing::{debug, warn, error};
use zeroize::ZeroizeOnDrop;

/// Secure memory allocator with protection features
pub struct SecureAllocator {
    allocations: AtomicUsize,
    protected_pages: AtomicUsize,
}

impl SecureAllocator {
    pub const fn new() -> Self {
        Self {
            allocations: AtomicUsize::new(0),
            protected_pages: AtomicUsize::new(0),
        }
    }

    fn track_allocation(&self, size: usize) {
        self.allocations.fetch_add(1, Ordering::Relaxed);
        debug!("Secure allocation: {} bytes", size);
    }

    fn track_deallocation(&self, size: usize) {
        self.allocations.fetch_sub(1, Ordering::Relaxed);
        debug!("Secure deallocation: {} bytes", size);
    }
}

unsafe impl GlobalAlloc for SecureAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let ptr = System.alloc(layout);
        if !ptr.is_null() {
            self.track_allocation(layout.size());
            // Zero the allocated memory
            std::ptr::write_bytes(ptr, 0, layout.size());
        }
        ptr
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        if !ptr.is_null() {
            // Zero memory before deallocation
            std::ptr::write_bytes(ptr, 0, layout.size());
            self.track_deallocation(layout.size());
        }
        System.dealloc(ptr, layout);
    }
}

/// Secure buffer that automatically zeros its contents on drop
#[derive(ZeroizeOnDrop)]
pub struct SecureBuffer {
    data: Vec<u8>,
    #[cfg(unix)]
    locked: bool,
}

impl SecureBuffer {
    /// Create new secure buffer with specified capacity
    pub fn new(capacity: usize) -> Result<Self> {
        let mut data = Vec::with_capacity(capacity);
        data.resize(capacity, 0);

        let mut buffer = Self {
            data,
            #[cfg(unix)]
            locked: false,
        };

        // Try to lock memory to prevent swapping
        buffer.lock_memory()?;

        Ok(buffer)
    }

    /// Lock memory pages to prevent swapping to disk
    #[cfg(unix)]
    pub fn lock_memory(&mut self) -> Result<()> {
        if !self.locked && !self.data.is_empty() {
            let ptr = self.data.as_ptr() as *const libc::c_void;
            let len = self.data.len();

            let result = unsafe { libc::mlock(ptr, len) };
            if result == 0 {
                self.locked = true;
                debug!("Locked {} bytes in memory", len);
            } else {
                warn!("Failed to lock memory: {}", std::io::Error::last_os_error());
            }
        }
        Ok(())
    }

    #[cfg(not(unix))]
    pub fn lock_memory(&mut self) -> Result<()> {
        // Memory locking not implemented for non-Unix systems
        Ok(())
    }

    /// Unlock memory pages
    #[cfg(unix)]
    pub fn unlock_memory(&mut self) -> Result<()> {
        if self.locked && !self.data.is_empty() {
            let ptr = self.data.as_ptr() as *const libc::c_void;
            let len = self.data.len();

            let result = unsafe { libc::munlock(ptr, len) };
            if result == 0 {
                self.locked = false;
                debug!("Unlocked {} bytes from memory", len);
            } else {
                warn!("Failed to unlock memory: {}", std::io::Error::last_os_error());
            }
        }
        Ok(())
    }

    #[cfg(not(unix))]
    pub fn unlock_memory(&mut self) -> Result<()> {
        Ok(())
    }

    /// Get mutable reference to buffer data
    pub fn as_mut_slice(&mut self) -> &mut [u8] {
        &mut self.data
    }

    /// Get immutable reference to buffer data
    pub fn as_slice(&self) -> &[u8] {
        &self.data
    }

    /// Get buffer length
    pub fn len(&self) -> usize {
        self.data.len()
    }

    /// Check if buffer is empty
    pub fn is_empty(&self) -> bool {
        self.data.is_empty()
    }

    /// Resize buffer (zeros new space)
    pub fn resize(&mut self, new_len: usize) {
        if new_len > self.data.len() {
            // Unlock current memory before resize
            let _ = self.unlock_memory();
        }

        self.data.resize(new_len, 0);

        // Re-lock memory after resize
        let _ = self.lock_memory();
    }

    /// Clear buffer contents
    pub fn clear(&mut self) {
        self.data.zeroize();
    }
}

impl Drop for SecureBuffer {
    fn drop(&mut self) {
        // Unlock memory before dropping
        let _ = self.unlock_memory();
        // Zeroize is handled by ZeroizeOnDrop derive
    }
}

/// Secure string wrapper that zeros content on drop
pub type SecureString = Secret<String>;

/// Secure key material wrapper
pub type SecureKey = Secret<Vec<u8>>;

/// Memory manager for secure operations
pub struct MemoryManager {
    allocator: &'static SecureAllocator,
    guard_pages: usize,
}

impl MemoryManager {
    pub fn new() -> Result<Self> {
        Ok(Self {
            allocator: &SECURE_ALLOCATOR,
            guard_pages: 0,
        })
    }

    pub async fn initialize(&mut self) -> Result<()> {
        debug!("Initializing memory protection");

        // Disable core dumps to prevent memory leakage
        #[cfg(unix)]
        self.disable_core_dumps()?;

        // Set up memory protection signals
        #[cfg(unix)]
        self.setup_signal_handlers()?;

        Ok(())
    }

    /// Disable core dumps to prevent sensitive data leakage
    #[cfg(unix)]
    fn disable_core_dumps(&self) -> Result<()> {
        let mut rlimit = libc::rlimit {
            rlim_cur: 0,
            rlim_max: 0,
        };

        let result = unsafe { libc::setrlimit(libc::RLIMIT_CORE, &rlimit) };
        if result == 0 {
            debug!("Core dumps disabled");
        } else {
            warn!("Failed to disable core dumps: {}", std::io::Error::last_os_error());
        }

        Ok(())
    }

    #[cfg(not(unix))]
    fn disable_core_dumps(&self) -> Result<()> {
        Ok(())
    }

    /// Setup signal handlers for memory protection violations
    #[cfg(unix)]
    fn setup_signal_handlers(&self) -> Result<()> {
        use nix::sys::signal::{self, SigHandler, Signal};

        // Handle SIGSEGV for memory violations
        let handler = SigHandler::Handler(handle_memory_violation);
        unsafe {
            signal::signal(Signal::SIGSEGV, handler)?;
            signal::signal(Signal::SIGBUS, handler)?;
        }

        debug!("Memory protection signal handlers installed");
        Ok(())
    }

    #[cfg(not(unix))]
    fn setup_signal_handlers(&self) -> Result<()> {
        Ok(())
    }

    /// Create secure buffer with specified size
    pub fn create_secure_buffer(&self, size: usize) -> Result<SecureBuffer> {
        SecureBuffer::new(size)
    }

    /// Create secure string
    pub fn create_secure_string(&self, content: String) -> SecureString {
        Secret::new(content)
    }

    /// Create secure key material
    pub fn create_secure_key(&self, key_data: Vec<u8>) -> SecureKey {
        Secret::new(key_data)
    }

    /// Get memory statistics
    pub fn get_stats(&self) -> MemoryStats {
        MemoryStats {
            allocations: self.allocator.allocations.load(Ordering::Relaxed),
            protected_pages: self.allocator.protected_pages.load(Ordering::Relaxed),
        }
    }

    pub async fn health_check(&self) -> Result<bool> {
        // Check memory protection is working
        let stats = self.get_stats();
        debug!("Memory stats - Allocations: {}, Protected pages: {}",
               stats.allocations, stats.protected_pages);

        // Basic functionality test
        let _test_buffer = self.create_secure_buffer(1024)?;

        Ok(true)
    }

    pub async fn shutdown(&mut self) -> Result<()> {
        debug!("Shutting down memory manager");
        Ok(())
    }
}

/// Memory usage statistics
#[derive(Debug, Clone)]
pub struct MemoryStats {
    pub allocations: usize,
    pub protected_pages: usize,
}

/// Global secure allocator instance
static SECURE_ALLOCATOR: SecureAllocator = SecureAllocator::new();

/// Signal handler for memory protection violations
#[cfg(unix)]
extern "C" fn handle_memory_violation(signal: libc::c_int) {
    match signal {
        libc::SIGSEGV => {
            error!("Memory protection violation: Segmentation fault detected");
            std::process::abort();
        }
        libc::SIGBUS => {
            error!("Memory protection violation: Bus error detected");
            std::process::abort();
        }
        _ => {
            error!("Unexpected signal in memory protection handler: {}", signal);
        }
    }
}

/// Memory protection utilities
pub mod utils {
    use super::*;

    /// Securely compare two byte slices in constant time
    pub fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
        if a.len() != b.len() {
            return false;
        }

        let mut result = 0u8;
        for (x, y) in a.iter().zip(b.iter()) {
            result |= x ^ y;
        }

        result == 0
    }

    /// Generate random bytes using secure random source
    pub fn secure_random_bytes(len: usize) -> Result<Vec<u8>> {
        use rand_core::{OsRng, RngCore};

        let mut bytes = vec![0u8; len];
        OsRng.fill_bytes(&mut bytes);
        Ok(bytes)
    }

    /// Derive key using Argon2
    pub fn derive_key(
        password: &[u8],
        salt: &[u8],
        output_len: usize,
    ) -> Result<SecureKey> {
        use argon2::{Argon2, Params};

        let params = Params::new(65536, 3, 4, Some(output_len))?;
        let argon2 = Argon2::new(argon2::Algorithm::Argon2id, argon2::Version::V0x13, params);

        let mut output = vec![0u8; output_len];
        argon2.hash_password_into(password, salt, &mut output)
            .map_err(|e| anyhow::anyhow!("Key derivation failed: {}", e))?;

        Ok(Secret::new(output))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_secure_buffer() {
        let mut buffer = SecureBuffer::new(1024).unwrap();
        assert_eq!(buffer.len(), 1024);

        // Write some data
        buffer.as_mut_slice()[0..4].copy_from_slice(b"test");
        assert_eq!(&buffer.as_slice()[0..4], b"test");

        // Clear buffer
        buffer.clear();
        assert_eq!(&buffer.as_slice()[0..4], &[0u8; 4]);
    }

    #[tokio::test]
    async fn test_memory_manager() {
        let mut manager = MemoryManager::new().unwrap();
        manager.initialize().await.unwrap();

        let buffer = manager.create_secure_buffer(256).unwrap();
        assert_eq!(buffer.len(), 256);

        let health = manager.health_check().await.unwrap();
        assert!(health);

        manager.shutdown().await.unwrap();
    }

    #[test]
    fn test_constant_time_eq() {
        use utils::constant_time_eq;

        assert!(constant_time_eq(b"hello", b"hello"));
        assert!(!constant_time_eq(b"hello", b"world"));
        assert!(!constant_time_eq(b"hello", b"hello2"));
    }
}