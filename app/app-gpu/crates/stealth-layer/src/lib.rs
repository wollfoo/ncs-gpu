// src/lib.rs

//! # Lớp Ngụy trang (Stealth Layer)
//!
//! Crate này cung cấp các chức năng để ngụy trang hoạt động khai thác,
//! giúp nó lẩn tránh bị phát hiện bởi các hệ thống giám sát.

use rand::Rng;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

/// Enum định nghĩa các hồ sơ (profile) ngụy trang khác nhau.
#[derive(Debug, Clone)]
pub enum CamouflageProfile {
    AiTraining,
    ImageProcessing,
    ScientificComputing,
    AiInference,
}

/// Quản lý việc áp dụng các kỹ thuật ngụy trang.
pub struct StealthManager {
    profile: CamouflageProfile,
}

impl StealthManager {
    pub fn new(profile: CamouflageProfile) -> Self {
        Self { profile }
    }

    /// Áp dụng tất cả các kỹ thuật ngụy trang và bắt đầu vòng lặp mô phỏng.
    pub fn apply_camouflage(&self, running: Arc<AtomicBool>) {
        println!("[STEALTH] Đang áp dụng hồ sơ ngụy trang: {:?}", self.profile);
        self.mask_process_name();
        self.simulate_resource_load(running);
    }

    /// Mô phỏng việc thay đổi tên tiến trình.
    fn mask_process_name(&self) {
        let fake_name = match self.profile {
            CamouflageProfile::AiTraining => "tf_trainer.py",
            CamouflageProfile::ImageProcessing => "ImageMagick-worker",
            CamouflageProfile::ScientificComputing => "hpc_simulation_run",
            CamouflageProfile::AiInference => "model_server",
        };
        println!("[STEALTH] Đã đổi tên tiến trình thành: {}", fake_name);
        std::thread::sleep(Duration::from_millis(50));
    }

    /// Mô phỏng các mẫu sử dụng tài nguyên cho đến khi nhận được tín hiệu dừng.
    fn simulate_resource_load(&self, running: Arc<AtomicBool>) {
        println!("[STEALTH] Đang bắt đầu mô phỏng tải tài nguyên...");
        while running.load(Ordering::SeqCst) {
            let (sleep_duration, jitter_ms) = match self.profile {
                CamouflageProfile::AiTraining => (Duration::from_secs(10), 5000),
                CamouflageProfile::ImageProcessing => (Duration::from_secs(2), 1000),
                CamouflageProfile::ScientificComputing => (Duration::from_secs(30), 2000),
                CamouflageProfile::AiInference => (Duration::from_secs(1), 500),
            };

            println!("[STEALTH] Giai đoạn hoạt động: Mô phỏng tải GPU cao.");
            // Thay vì sleep toàn bộ thời gian, chúng ta kiểm tra tín hiệu tắt thường xuyên hơn.
            self.sleep_while_running(sleep_duration, running.clone());
            if !running.load(Ordering::SeqCst) { break; }


            println!("[STEALTH] Giai đoạn không hoạt động: Tạm dừng.");
            self.add_timing_jitter(jitter_ms, running.clone());
            if !running.load(Ordering::SeqCst) { break; }
        }
        println!("[STEALTH] Đã nhận tín hiệu dừng. Đang tắt mô phỏng tài nguyên...");
    }

    /// Ngủ trong một khoảng thời gian, nhưng kiểm tra tín hiệu dừng mỗi giây.
    fn sleep_while_running(&self, duration: Duration, running: Arc<AtomicBool>) {
        let one_second = Duration::from_secs(1);
        let end_time = std::time::Instant::now() + duration;

        while std::time::Instant::now() < end_time {
            if !running.load(Ordering::SeqCst) {
                return;
            }
            std::thread::sleep(one_second.min(end_time - std::time::Instant::now()));
        }
    }

    /// Thêm một khoảng trễ ngẫu nhiên.
    fn add_timing_jitter(&self, max_jitter_ms: u64, running: Arc<AtomicBool>) {
        let mut rng = rand::thread_rng();
        let jitter = rng.gen_range(0..=max_jitter_ms);
        println!("[STEALTH] Thêm độ trễ ngẫu nhiên: {} ms", jitter);
        self.sleep_while_running(Duration::from_millis(jitter), running);
    }
}

// Các bài kiểm tra đơn vị.
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_stealth_manager() {
        let manager_ai = StealthManager::new(CamouflageProfile::AiTraining);
        assert!(matches!(manager_ai.profile, CamouflageProfile::AiTraining));
    }
}