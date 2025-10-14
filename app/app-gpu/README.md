# Hệ thống Khai thác GPU Ngụy trang (Stealth GPU Mining System)

Dự án này là một triển khai bằng **Rust** của một hệ thống khai thác GPU được thiết kế cho mục đích **nghiên cứu bảo mật**. Mục tiêu chính là mô phỏng cách các hoạt động khai thác có thể được che giấu dưới các tác vụ tính toán thông thường (ví dụ: AI, xử lý ảnh) để kiểm tra và cải thiện khả năng phát hiện của các hệ thống giám sát trên nền tảng đám mây.

**Lưu ý:** Phần mềm này được tạo ra cho mục đích giáo dục và nghiên cứu. Việc sử dụng nó trên các hệ thống mà không có sự cho phép rõ ràng có thể vi phạm điều khoản dịch vụ và pháp luật.

---

## 🚀 Kiến trúc

Hệ thống được xây dựng dựa trên một kiến trúc mô-đun, bao gồm các thành phần chính sau:

- **`mining-cli`**: Giao diện dòng lệnh (CLI) chính để khởi động và quản lý hệ thống.
- **`mining-core`**: Lõi logic chịu trách nhiệm quản lý các thiết bị GPU, kết nối đến các pool khai thác và thực hiện các thuật toán băm.
- **`stealth-layer`**: Lớp ngụy trang, cung cấp các kỹ thuật để che giấu hoạt động khai thác, bao gồm thay đổi tên tiến trình và mô phỏng các mẫu sử dụng tài nguyên khác nhau.

Toàn bộ dự án được quản lý như một **workspace** (không gian làm việc) của Cargo.

---

## ✨ Tính năng

- **Hiệu suất cao:** Được viết bằng Rust, cung cấp hiệu suất gần với C/C++ và đảm bảo an toàn bộ nhớ.
- **Ngụy trang Linh hoạt:** Hỗ trợ nhiều hồ sơ (profile) ngụy trang khác nhau:
  - `AiTraining`
  - `ImageProcessing`
  - `ScientificComputing`
  - `AiInference`
- **Cấu hình Dễ dàng:** Quản lý tất cả các tham số thông qua một tệp cấu hình TOML đơn giản.
- **Đóng gói bằng Docker:** Đi kèm với một `Dockerfile` đa giai đoạn để tạo ra các image nhỏ gọn và hiệu quả.

---

## 📚 Bắt đầu

Để bắt đầu với dự án này, bạn có hai lựa chọn chính: xây dựng từ mã nguồn hoặc sử dụng Docker.

### 1. Xây dựng từ Mã nguồn

**Yêu cầu:**
- [Rust](https://www.rust-lang.org/tools/install) (phiên bản 1.70 trở lên)
- Git

**Các bước:**
1.  **Sao chép kho lưu trữ:**
    ```bash
    git clone <URL_KHO_LUU_TRU>
    cd opus-gpu/app/app-gpu
    ```

2.  **Cấu hình:**
    Sao chép `config/default.toml` thành `config/production.toml` và chỉnh sửa các giá trị, đặc biệt là `pool_url` và `wallet_address`.
    ```bash
    cp config/default.toml config/production.toml
    nano config/production.toml
    ```

3.  **Xây dựng:**
    Sử dụng kịch bản xây dựng để biên dịch ở chế độ phát hành.
    ```bash
    ./scripts/build_release.sh
    ```

4.  **Chạy:**
    ```bash
    ./target/release/mining-cli --config config/production.toml start
    ```

### 2. Sử dụng Docker

**Yêu cầu:**
- [Docker](https://docs.docker.com/get-docker/)

**Các bước:**
1.  **Di chuyển đến thư mục dự án:**
    ```bash
    cd opus-gpu/app/app-gpu
    ```

2.  **Cấu hình:**
    Chỉnh sửa tệp `config/default.toml` với thông tin pool và ví của bạn. Image Docker sẽ sử dụng tệp này theo mặc định.

3.  **Xây dựng Image:**
    ```bash
    docker build -t stealth-miner:latest -f docker/Dockerfile.ubuntu-cuda .
    ```

4.  **Chạy Container:**
    Để sử dụng GPU, bạn cần có `nvidia-container-toolkit`.
    ```bash
    docker run -d --gpus all --name my-miner stealth-miner:latest
    ```

5.  **Kiểm tra Logs:**
    ```bash
    docker logs -f my-miner
    ```

---

### 3. Sử dụng từ Python (thông qua FFI)

Hệ thống cũng có thể được điều khiển từ Python, cho phép tích hợp dễ dàng vào các ứng dụng hoặc kịch bản hiện có.

**Bước 1: Biên dịch Thư viện Động**

Bạn cần biên dịch `mining-core` thành một thư viện liên kết động (`.so`, `.dll`, `.dylib`). Điều này yêu cầu kích hoạt tính năng `ffi`.

```bash
# Biên dịch toàn bộ workspace, kích hoạt tính năng ffi cho mining-core
cargo build --release --features mining-core/ffi
```

**Bước 2: Chạy Kịch bản Python**

Thư mục `python/` chứa một lớp bao bọc và một ví dụ.

```bash
# Đảm bảo bạn đang ở thư mục gốc app/app-gpu
python3 python/mining_wrapper.py
```

Kịch bản sẽ tự động tìm thư viện đã biên dịch trong thư mục `target/release` và khởi động engine.

---

## 🔧 Cấu hình

Tất cả các tùy chọn cấu hình được đặt trong tệp `.toml`. Xem `config/default.toml` để biết tất cả các tham số có sẵn và mô tả của chúng.

---

## 🤝 Đóng góp

Chúng tôi hoan nghênh các đóng góp! Vui lòng tạo một "Issue" để thảo luận về các thay đổi hoặc một "Pull Request" với các cải tiến của bạn.