#!/bin/bash
# Kịch bản này biên dịch dự án Rust ở chế độ phát hành (release mode).
# (This script compiles the Rust project in release mode.)

# Dừng lại nếu có bất kỳ lệnh nào thất bại.
# (Stop if any command fails.)
set -e

echo "Bắt đầu quá trình xây dựng bản phát hành..."

# Di chuyển đến thư mục gốc của dự án (nơi chứa tệp Cargo.toml của workspace).
# (Navigate to the project's root directory (where the workspace's Cargo.toml is located).)
cd "$(dirname "$0")/.."

# Chạy lệnh `cargo build` với cờ `--release`.
# (Run the `cargo build` command with the `--release` flag.)
# Cờ này kích hoạt các tối ưu hóa và tạo ra một tệp nhị phân hiệu suất cao.
# (This flag enables optimizations and produces a high-performance binary.)
cargo build --release

echo "Quá trình xây dựng hoàn tất!"
echo "Tệp nhị phân có thể được tìm thấy tại: ./target/release/mining-cli"