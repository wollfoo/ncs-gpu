//! # GPU Emulator (Giả Lập GPU)
//!
//! **Fake GPU implementation** (implementation GPU giả) cho integration testing
//! mà không cần CUDA hardware thật.

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{sleep, Duration};
use tracing::{debug, info};

/// **GpuEmulator** (giả lập GPU) – fake GPU devices với metrics
#[derive(Clone)]
pub struct GpuEmulator {
    /// **Device count** (số lượng thiết bị) – tổng số GPU giả lập
    device_count: usize,

    /// **Hashrate** (tốc độ băm) – MH/s per device
    hashrate_mhs: Arc<RwLock<HashMap<usize, f64>>>,

    /// **Temperature** (nhiệt độ) – độ C per device
    temperature_c: Arc<RwLock<HashMap<usize, u32>>>,

    /// **Utilization** (sử dụng) – phần trăm per device
    utilization_percent: Arc<RwLock<HashMap<usize, u8>>>,

    /// **Memory usage** (sử dụng bộ nhớ) – MB per device
    memory_mb: Arc<RwLock<HashMap<usize, u64>>>,

    /// **Initialization status** (trạng thái khởi tạo)
    is_initialized: Arc<AtomicBool>,

    /// **Total shares generated** (tổng share tạo ra)
    total_shares: Arc<RwLock<u64>>,
}

impl GpuEmulator {
    /// **Create new emulator** (tạo emulator mới)
    ///
    /// # Arguments (Tham số)
    /// - `device_count`: Số lượng GPU giả lập (1-8 thông thường)
    ///
    /// # Returns (Trả về)
    /// - Emulator instance chưa initialize
    pub fn new(device_count: usize) -> Self {
        info!("🎮 Creating GPU emulator with {} devices", device_count);

        Self {
            device_count,
            hashrate_mhs: Arc::new(RwLock::new(HashMap::new())),
            temperature_c: Arc::new(RwLock::new(HashMap::new())),
            utilization_percent: Arc::new(RwLock::new(HashMap::new())),
            memory_mb: Arc::new(RwLock::new(HashMap::new())),
            is_initialized: Arc::new(AtomicBool::new(false)),
            total_shares: Arc::new(RwLock::new(0)),
        }
    }

    /// **Initialize GPUs** (khởi tạo GPU) – fake initialization với delay
    ///
    /// Simulate CUDA initialization time (500ms) và set default values.
    ///
    /// # Returns (Trả về)
    /// - `Ok(())`: Init thành công
    /// - `Err`: Lỗi (hiếm, chỉ khi logic error)
    pub async fn initialize(&mut self) -> Result<(), String> {
        if self.is_initialized() {
            return Err("Already initialized".to_string());
        }

        info!("⚙️  Initializing {} GPU devices...", self.device_count);

        // Simulate CUDA init time
        sleep(Duration::from_millis(500)).await;

        // Set default metrics cho mỗi device
        for device_id in 0..self.device_count {
            self.hashrate_mhs
                .write()
                .await
                .insert(device_id, 25.0); // 25 MH/s default

            self.temperature_c.write().await.insert(device_id, 65); // 65°C

            self.utilization_percent
                .write()
                .await
                .insert(device_id, 85); // 85%

            self.memory_mb
                .write()
                .await
                .insert(device_id, 4096); // 4GB
        }

        self.is_initialized.store(true, Ordering::SeqCst);
        info!("✅ GPU emulator initialized successfully");

        Ok(())
    }

    /// **Get device count** (lấy số thiết bị)
    pub fn get_device_count(&self) -> usize {
        self.device_count
    }

    /// **Get hashrate** (lấy tốc độ băm) – MH/s cho device cụ thể
    ///
    /// # Arguments (Tham số)
    /// - `device_id`: GPU ID (0-based)
    ///
    /// # Returns (Trả về)
    /// - `Ok(f64)`: Hashrate in MH/s
    /// - `Err`: Device ID không hợp lệ
    pub async fn get_hashrate(&self, device_id: usize) -> Result<f64, String> {
        if device_id >= self.device_count {
            return Err(format!(
                "Invalid device_id: {} (max: {})",
                device_id,
                self.device_count - 1
            ));
        }

        let hashrates = self.hashrate_mhs.read().await;
        Ok(*hashrates.get(&device_id).unwrap_or(&0.0))
    }

    /// **Set hashrate** (đặt tốc độ băm) – update fake hashrate
    ///
    /// # Arguments (Tham số)
    /// - `device_id`: GPU ID
    /// - `mhs`: Hashrate in MH/s
    pub async fn set_hashrate(&self, device_id: usize, mhs: f64) {
        if device_id < self.device_count {
            self.hashrate_mhs.write().await.insert(device_id, mhs);
            debug!("📊 GPU {} hashrate set to {} MH/s", device_id, mhs);
        }
    }

    /// **Get temperature** (lấy nhiệt độ) – độ C cho device cụ thể
    ///
    /// # Arguments (Tham số)
    /// - `device_id`: GPU ID
    ///
    /// # Returns (Trả về)
    /// - `Ok(u32)`: Temperature in Celsius
    /// - `Err`: Device ID không hợp lệ
    pub async fn get_temperature(&self, device_id: usize) -> Result<u32, String> {
        if device_id >= self.device_count {
            return Err(format!(
                "Invalid device_id: {} (max: {})",
                device_id,
                self.device_count - 1
            ));
        }

        let temps = self.temperature_c.read().await;
        Ok(*temps.get(&device_id).unwrap_or(&0))
    }

    /// **Set temperature** (đặt nhiệt độ) – update fake temperature
    pub async fn set_temperature(&self, device_id: usize, celsius: u32) {
        if device_id < self.device_count {
            self.temperature_c
                .write()
                .await
                .insert(device_id, celsius);
            debug!("🌡️  GPU {} temperature set to {}°C", device_id, celsius);
        }
    }

    /// **Get utilization** (lấy mức sử dụng) – % cho device cụ thể
    pub async fn get_utilization(&self, device_id: usize) -> Result<u8, String> {
        if device_id >= self.device_count {
            return Err(format!(
                "Invalid device_id: {} (max: {})",
                device_id,
                self.device_count - 1
            ));
        }

        let utils = self.utilization_percent.read().await;
        Ok(*utils.get(&device_id).unwrap_or(&0))
    }

    /// **Get memory usage** (lấy sử dụng bộ nhớ) – MB cho device cụ thể
    pub async fn get_memory_usage(&self, device_id: usize) -> Result<u64, String> {
        if device_id >= self.device_count {
            return Err(format!(
                "Invalid device_id: {} (max: {})",
                device_id,
                self.device_count - 1
            ));
        }

        let mem = self.memory_mb.read().await;
        Ok(*mem.get(&device_id).unwrap_or(&0))
    }

    /// **Simulate mining** (giả lập khai thác) – generate fake shares
    ///
    /// # Arguments (Tham số)
    /// - `duration_secs`: Thời gian mining (giây)
    ///
    /// Simulate mining process:
    /// - Generate shares based on hashrate
    /// - Update metrics (temp tăng, util dao động)
    pub async fn simulate_mining(&self, duration_secs: u64) {
        if !self.is_initialized() {
            tracing::warn!("⚠️  Cannot mine: emulator not initialized");
            return;
        }

        info!("⛏️  Starting mining simulation for {}s", duration_secs);

        let start = std::time::Instant::now();
        let mut shares = 0u64;

        while start.elapsed().as_secs() < duration_secs {
            // Generate shares dựa trên hashrate
            for device_id in 0..self.device_count {
                let hashrate = self.get_hashrate(device_id).await.unwrap_or(0.0);

                // Giả định: 1 share mỗi 100M hash (Ethash difficulty)
                let shares_per_sec = hashrate / 100.0;

                if rand::random::<f64>() < shares_per_sec {
                    shares += 1;
                }

                // Simulate nhiệt độ tăng nhẹ khi mining
                if let Ok(temp) = self.get_temperature(device_id).await {
                    let new_temp = (temp + 1).min(85); // Cap ở 85°C
                    self.set_temperature(device_id, new_temp).await;
                }
            }

            sleep(Duration::from_secs(1)).await;
        }

        // Update total shares
        *self.total_shares.write().await += shares;

        info!(
            "✅ Mining simulation complete: {} shares generated",
            shares
        );
    }

    /// **Check initialization** (kiểm tra khởi tạo)
    pub fn is_initialized(&self) -> bool {
        self.is_initialized.load(Ordering::SeqCst)
    }

    /// **Get total shares** (lấy tổng share)
    pub async fn get_total_shares(&self) -> u64 {
        *self.total_shares.read().await
    }

    /// **Reset emulator** (đặt lại emulator) – clear state
    pub async fn reset(&mut self) {
        self.hashrate_mhs.write().await.clear();
        self.temperature_c.write().await.clear();
        self.utilization_percent.write().await.clear();
        self.memory_mb.write().await.clear();
        self.is_initialized.store(false, Ordering::SeqCst);
        *self.total_shares.write().await = 0;

        info!("🔄 GPU emulator reset");
    }
}

// ============================================================================
// Test Helper Functions (Hàm Helper Kiểm Thử)
// ============================================================================

/// **Create default emulator** (tạo emulator mặc định)
///
/// Config:
/// - 2 GPUs
/// - 25 MH/s each
/// - 65°C temperature
/// - 85% utilization
pub async fn create_default_emulator() -> GpuEmulator {
    let mut emulator = GpuEmulator::new(2);
    emulator.initialize().await.expect("Init failed");
    emulator
}

/// **Create high temperature emulator** (tạo emulator nhiệt độ cao)
///
/// For testing thermal alerts:
/// - 2 GPUs
/// - 90°C temperature (near throttle threshold)
pub async fn create_high_temp_emulator() -> GpuEmulator {
    let mut emulator = GpuEmulator::new(2);
    emulator.initialize().await.expect("Init failed");

    // Set high temperature
    for device_id in 0..2 {
        emulator.set_temperature(device_id, 90).await;
    }

    emulator
}

/// **Create low hashrate emulator** (tạo emulator hashrate thấp)
///
/// For testing performance alerts:
/// - 2 GPUs
/// - 5 MH/s each (very low)
pub async fn create_low_hashrate_emulator() -> GpuEmulator {
    let mut emulator = GpuEmulator::new(2);
    emulator.initialize().await.expect("Init failed");

    // Set low hashrate
    for device_id in 0..2 {
        emulator.set_hashrate(device_id, 5.0).await;
    }

    emulator
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_emulator_initialization() {
        let mut emulator = GpuEmulator::new(2);

        assert!(!emulator.is_initialized());

        emulator.initialize().await.expect("Init failed");

        assert!(emulator.is_initialized());
        assert_eq!(emulator.get_device_count(), 2);
    }

    #[tokio::test]
    async fn test_hashrate_operations() {
        let emulator = create_default_emulator().await;

        let hashrate = emulator.get_hashrate(0).await.expect("Get failed");
        assert_eq!(hashrate, 25.0);

        emulator.set_hashrate(0, 30.0).await;
        let new_hashrate = emulator.get_hashrate(0).await.expect("Get failed");
        assert_eq!(new_hashrate, 30.0);
    }

    #[tokio::test]
    async fn test_temperature_operations() {
        let emulator = create_default_emulator().await;

        let temp = emulator.get_temperature(0).await.expect("Get failed");
        assert_eq!(temp, 65);

        emulator.set_temperature(0, 75).await;
        let new_temp = emulator.get_temperature(0).await.expect("Get failed");
        assert_eq!(new_temp, 75);
    }

    #[tokio::test]
    async fn test_invalid_device_id() {
        let emulator = create_default_emulator().await;

        let result = emulator.get_hashrate(999).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_helper_functions() {
        let default_emu = create_default_emulator().await;
        assert_eq!(default_emu.get_device_count(), 2);
        assert!(default_emu.is_initialized());

        let high_temp_emu = create_high_temp_emulator().await;
        let temp = high_temp_emu.get_temperature(0).await.unwrap();
        assert_eq!(temp, 90);

        let low_hash_emu = create_low_hashrate_emulator().await;
        let hashrate = low_hash_emu.get_hashrate(0).await.unwrap();
        assert_eq!(hashrate, 5.0);
    }
}
