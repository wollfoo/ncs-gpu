// src/lib.rs

//! # Lõi Khai thác (Mining Core)
//!
//! Crate này chứa tất cả logic cốt lõi để quản lý và thực hiện các hoạt động khai thác GPU.
//! Nó trừu tượng hóa việc tương tác với phần cứng GPU, kết nối đến các pool khai thác,
//! và xử lý các thuật toán băm (hashing).

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

/// Enum định nghĩa các thuật toán khai thác được hỗ trợ.
#[derive(Debug, Clone, PartialEq)]
pub enum MiningAlgorithm {
    Ethash,
    KawPow,
    RandomX,
}

/// Cấu trúc chứa thông tin cấu hình cho một phiên khai thác.
#[derive(Debug, Clone)]
pub struct MiningConfig {
    pub pool_url: String,
    pub wallet_address: String,
    pub algorithm: MiningAlgorithm,
    pub gpu_devices: Vec<u32>,
    pub intensity: u8,
}

/// Đại diện cho một thiết bị GPU vật lý.
#[derive(Debug)]
pub struct GpuDevice {
    id: u32,
    name: String,
}

impl GpuDevice {
    pub fn new(id: u32) -> Self {
        Self {
            id,
            name: format!("Simulated GPU {}", id),
        }
    }

    /// Bắt đầu một vòng lặp khai thác mô phỏng trên thiết bị này.
    /// Vòng lặp sẽ tiếp tục cho đến khi `running` được đặt thành `false`.
    pub fn start_mining(&self, config: MiningConfig, running: Arc<AtomicBool>) {
        use sha2::{Digest, Sha256};
        let mut nonce: u64 = 0;

        println!(
            "[GPU {} - {}] Đã bắt đầu khai thác với thuật toán {:?} tại cường độ {}%. Đang kết nối tới: {}",
            self.id, self.name, config.algorithm, config.intensity, config.pool_url
        );

        while running.load(Ordering::SeqCst) {
            // Mô phỏng công việc tính toán bằng cách thực hiện băm SHA-256.
            // (Simulate computational work by performing SHA-256 hashing.)
            let mut hasher = Sha256::new();
            let data = format!("block_data_or_header_{}", nonce);
            hasher.update(data.as_bytes());
            let _result = hasher.finalize(); // Kết quả băm, bỏ qua trong mô phỏng.

            // Tăng nonce để lần băm tiếp theo là khác.
            nonce = nonce.wrapping_add(1);

            // Cứ sau 1,000,000 lần băm, in ra một thông báo và tạm nghỉ.
            // (Every 1,000,000 hashes, print a message and pause.)
            if nonce % 1_000_000 == 0 {
                println!("[GPU {}] Đã tính toán 1,000,000 hashes. Nonce hiện tại: {}", self.id, nonce);
                // Tạm nghỉ một chút để không chiếm 100% CPU liên tục và cho phép các tác vụ khác chạy.
                std::thread::sleep(Duration::from_millis(10));
            }
        }
        println!("[GPU {}] Đã nhận tín hiệu dừng. Đang tắt...", self.id);
    }
}

/// Bộ máy khai thác chính.
pub struct MiningEngine {
    config: MiningConfig,
    devices: Vec<GpuDevice>,
}

impl MiningEngine {
    pub fn new(config: MiningConfig) -> Self {
        let devices = config
            .gpu_devices
            .iter()
            .map(|&id| GpuDevice::new(id))
            .collect();
        Self { config, devices }
    }

    /// Bắt đầu hoạt động khai thác trên tất cả các thiết bị.
    /// Phương thức này sẽ tạo ra một luồng riêng cho mỗi GPU.
    pub fn start(&self, running: Arc<AtomicBool>) {
        println!("Khởi động Mining Engine...");
        let mut handles = vec![];
        for device in &self.devices {
            let config = self.config.clone();
            let device_id = device.id;
            let running_clone = running.clone();
            let handle = std::thread::spawn(move || {
                let device = GpuDevice::new(device_id);
                device.start_mining(config, running_clone);
            });
            handles.push(handle);
        }

        // Đợi tất cả các luồng hoàn thành.
        for handle in handles {
            handle.join().expect("Luồng con của GPU đã panic!");
        }
        println!("Tất cả các luồng khai thác đã tắt.");
    }
}

// Các bài kiểm tra đơn vị.
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_mining_engine() {
        let config = MiningConfig {
            pool_url: "test_pool".to_string(),
            wallet_address: "test_wallet".to_string(),
            algorithm: MiningAlgorithm::Ethash,
            gpu_devices: vec![0, 1],
            intensity: 90,
        };
        let engine = MiningEngine::new(config);
        assert_eq!(engine.devices.len(), 2);
    }
}


/// # Giao diện Hàm Ngoại vi (Foreign Function Interface - FFI)
///
/// Module này cung cấp một giao diện tương thích với C cho crate `mining-core`.
/// Nó cho phép các ngôn ngữ khác (như Python) gọi vào thư viện Rust này.
///
/// **CẢNH BÁO:** Các hàm trong đây là `unsafe` vì chúng làm việc với con trỏ thô
/// và không được quản lý bởi bộ kiểm tra mượn (borrow checker) của Rust.
#[cfg(feature = "ffi")]
pub mod ffi {
    use super::{MiningAlgorithm, MiningConfig, MiningEngine};
    use std::ffi::{CStr, CString};
    use std::os::raw::c_char;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::Arc;
    use std::thread::JoinHandle;

    /// Một cấu trúc bao bọc an toàn cho con trỏ tới MiningEngine và luồng của nó.
    pub struct OpaqueMiningEngine {
        engine: Arc<MiningEngine>,
        handle: Option<JoinHandle<()>>,
        running: Arc<AtomicBool>,
    }

    /// Chuyển đổi chuỗi C thành chuỗi Rust.
    fn c_char_to_string(c_char: *const c_char) -> String {
        if c_char.is_null() {
            return String::new();
        }
        unsafe { CStr::from_ptr(c_char).to_string_lossy().into_owned() }
    }

    /// Tạo một instance mới của MiningEngine và trả về một con trỏ tới nó.
    /// Con trỏ này phải được giải phóng sau đó bằng cách gọi `mining_engine_free`.
    #[no_mangle]
    pub extern "C" fn mining_engine_new(
        pool_url: *const c_char,
        wallet_address: *const c_char,
        algorithm: *const c_char,
    ) -> *mut OpaqueMiningEngine {
        let config = MiningConfig {
            pool_url: c_char_to_string(pool_url),
            wallet_address: c_char_to_string(wallet_address),
            algorithm: match c_char_to_string(algorithm).as_str() {
                "Ethash" => MiningAlgorithm::Ethash,
                "KawPow" => MiningAlgorithm::KawPow,
                _ => MiningAlgorithm::RandomX,
            },
            gpu_devices: vec![0], // Mặc định cho FFI
            intensity: 90,       // Mặc định cho FFI
        };

        let engine = OpaqueMiningEngine {
            engine: Arc::new(MiningEngine::new(config)),
            handle: None,
            running: Arc::new(AtomicBool::new(false)),
        };

        Box::into_raw(Box::new(engine))
    }

    /// Bắt đầu MiningEngine trong một luồng riêng.
    #[no_mangle]
    pub extern "C" fn mining_engine_start(ptr: *mut OpaqueMiningEngine) {
        if ptr.is_null() {
            return;
        }
        let engine_wrapper = unsafe { &mut *ptr };

        engine_wrapper.running.store(true, Ordering::SeqCst);
        let engine_clone = engine_wrapper.engine.clone();
        let running_clone = engine_wrapper.running.clone();

        engine_wrapper.handle = Some(std::thread::spawn(move || {
            engine_clone.start(running_clone);
        }));
    }

    /// Dừng MiningEngine.
    #[no_mangle]
    pub extern "C" fn mining_engine_stop(ptr: *mut OpaqueMiningEngine) {
        if ptr.is_null() {
            return;
        }
        let engine_wrapper = unsafe { &mut *ptr };

        if let Some(handle) = engine_wrapper.handle.take() {
            println!("[FFI] Gửi tín hiệu dừng...");
            engine_wrapper.running.store(false, Ordering::SeqCst);
            handle.join().expect("Không thể join luồng khai thác!");
            println!("[FFI] Luồng đã dừng.");
        }
    }

    /// Giải phóng bộ nhớ đã cấp phát cho MiningEngine.
    #[no_mangle]
    pub extern "C" fn mining_engine_free(ptr: *mut OpaqueMiningEngine) {
        if ptr.is_null() {
            return;
        }
        // Dừng engine trước khi giải phóng để đảm bảo an toàn.
        mining_engine_stop(ptr);
        unsafe {
            let _ = Box::from_raw(ptr);
        }
        println!("[FFI] Đã giải phóng bộ nhớ của Engine.");
    }
}