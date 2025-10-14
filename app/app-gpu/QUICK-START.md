# Hướng dẫn Bắt đầu Nhanh (Quick Start)

Tài liệu này cung cấp các bước nhanh nhất để bạn có thể chạy hệ thống khai thác này. Phương pháp được khuyến nghị là sử dụng **Docker**.

---

## 🚀 Chạy bằng Docker (5 Phút)

Đây là cách nhanh nhất và dễ nhất để bắt đầu.

### Bước 1: Cấu hình

Mở và chỉnh sửa tệp `config/default.toml`. Bạn **bắt buộc** phải thay đổi hai giá trị sau:

```toml
[mining]
# THAY ĐỔI DÒNG NÀY
pool_url = "stratum+tcp://YOUR-POOL.com:3333"

# VÀ THAY ĐỔI DÒNG NÀY
wallet_address = "YOUR_WALLET_ADDRESS"
```

Bạn cũng có thể điều chỉnh các giá trị khác như `algorithm` hoặc `intensity` nếu cần.

### Bước 2: Xây dựng Image Docker

Từ thư mục gốc `app/app-gpu/`, chạy lệnh sau:

```bash
docker build -t stealth-miner:latest -f docker/Dockerfile.ubuntu-cuda .
```

Lệnh này sẽ tải xuống các phụ thuộc, biên dịch mã nguồn và tạo một image Docker có tên `stealth-miner:latest`.

### Bước 3: Chạy Container

Sau khi image được xây dựng thành công, hãy khởi động container:

```bash
# Chạy ở chế độ nền (detached mode) và cho phép truy cập tất cả các GPU
docker run -d --gpus all --name my-stealth-miner stealth-miner:latest
```

### Bước 4: Kiểm tra Trạng thái

Để xem logs của ứng dụng và đảm bảo nó đang chạy đúng cách:

```bash
docker logs -f my-stealth-miner
```

Bạn sẽ thấy các thông báo từ `Mining Engine` và `StealthManager`.

Để kiểm tra việc sử dụng GPU, hãy mở một terminal khác và chạy:

```bash
watch -n 1 nvidia-smi
```

### Bước 5: Dừng Container

Khi bạn muốn dừng quá trình khai thác, hãy chạy:

```bash
docker stop my-stealth-miner
docker rm my-stealth-miner
```

---

## 🛠️ Chạy từ Mã nguồn (10 Phút)

Nếu bạn muốn tùy chỉnh sâu hơn hoặc không muốn sử dụng Docker.

### Yêu cầu
- Rust (>= 1.70)
- Git

### Bước 1: Lấy Mã nguồn
```bash
git clone <URL_KHO_LUU_TRU>
cd opus-gpu/app/app-gpu
```

### Bước 2: Cấu hình
Tạo một tệp cấu hình mới và chỉnh sửa nó:
```bash
cp config/default.toml config/my_config.toml
nano config/my_config.toml
```
Hãy chắc chắn rằng bạn đã cập nhật `pool_url` và `wallet_address`.

### Bước 3: Biên dịch
```bash
./scripts/build_release.sh
```

### Bước 4: Chạy
```bash
./target/release/mining-cli --config config/my_config.toml start
```

Ứng dụng sẽ chạy ở foreground. Nhấn `Ctrl+C` để dừng lại.