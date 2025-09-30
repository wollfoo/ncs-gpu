# HƯỚNG DẪN SỬ DỤNG HỆ THỐNG GPU MINING V2

**Phiên bản**: 2.0.0  
**Ngày cập nhật**: 2025-09-30

---

## MỤC LỤC

1. [Giới thiệu tổng quan](#1-giới-thiệu)
2. [Yêu cầu hệ thống](#2-yêu-cầu)
3. [Cài đặt](#3-cài-đặt)
4. [Vận hành](#4-vận-hành)
5. [Xử lý sự cố](#5-xử-lý-sự-cố)
6. [Bảo trì](#6-bảo-trì)

---

## 1. GIỚI THIỆU

### 1.1 Tổng quan

**GPU Mining System v2** quản lý **[GPU Workloads]** (khối lượng công việc GPU – tác vụ tính toán GPU):

- 🚀 Tối ưu GPU
- 📊 Giám sát real-time
- 🔒 Bảo mật cao
- 📈 Mở rộng linh hoạt

### 1.2 Kiến trúc

```
CLIENT → COORDINATOR → WORKER → GPU
```

### 1.3 Workloads

- **AI Training**: GEMM, loss
- **Image Processing**: Convolution
- **Scientific**: FFT, BLAS
- **AI Inference**: Forward pass

---

## 2. YÊU CẦU

### 2.1 Phần cứng

- CPU: 4+ cores
- RAM: 8+ GB
- GPU: NVIDIA CUDA 6.0+
- VRAM: 4+ GB

### 2.2 Phần mềm

- Ubuntu 22.04+
- CUDA 12.0+
- Rust 1.75+
- CMake 3.18+

### 2.3 Kiểm tra GPU

```bash
nvidia-smi
```

---

## 3. CÀI ĐẶT

### 3.1 CUDA

```bash
# Tải CUDA 12.2
wget https://developer.download.nvidia.com/compute/cuda/12.2.0/local_installers/cuda_12.2.0_535.54.03_linux.run
sudo sh cuda_12.2.0_535.54.03_linux.run

# Thêm PATH
echo 'export PATH=/usr/local/cuda-12.2/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### 3.2 Rust

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
```

### 3.3 Build

```bash
cd /home/azureuser/opus-gpu/app/app-gpu
make build
```

### 3.4 Test

```bash
make test
```

---

## 4. VẬN HÀNH

### 4.1 Khởi động

**Terminal 1** (Coordinator):
```bash
./target/release/coordinator --config config/default.toml
```

**Terminal 2** (Worker):
```bash
./target/release/worker --coordinator-addr localhost:50051
```

### 4.2 Submit task

```bash
./target/release/gpu-miner submit \
  --workload-type ai-training \
  --duration 60 \
  --batch-size 32
```

### 4.3 Check status

```bash
./target/release/gpu-miner status <TASK_ID>
```

### 4.4 List workers

```bash
./target/release/gpu-miner workers
```

### 4.5 Benchmark

```bash
./target/release/gpu-miner benchmark --num-tasks 10
```

---

## 5. XỬ LÝ SỰ CỐ

### 5.1 "CUDA not found"

```bash
export PATH=/usr/local/cuda-12.2/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-12.2/lib64:$LD_LIBRARY_PATH
```

### 5.2 "NVML init failed"

```bash
sudo ubuntu-drivers autoinstall
sudo reboot
```

### 5.3 "Out of memory"

```bash
# Giảm memory
./target/release/gpu-miner submit --memory-mb 512
```

### 5.4 "No workers available"

```bash
# Restart worker
./target/release/worker --coordinator-addr localhost:50051
```

### 5.5 Debug logs

```bash
RUST_LOG=debug ./target/release/coordinator
```

---

## 6. BẢO TRÌ

### 6.1 Backup

```bash
tar -czf config-backup.tar.gz config/
```

### 6.2 Update

```bash
git pull
make clean
make build
make test
```

### 6.3 Monitor GPU

```bash
watch -n 1 nvidia-smi
```

### 6.4 Performance tuning

**config/default.toml**:
```toml
[gpu]
stream_count = 8
memory_pool_size_mb = 4096

[scheduler]
queue_capacity = 20000
```

---

## PHỤ LỤC

### Lệnh thường dùng

```bash
# Build
make build

# Test
make test

# Clean
make clean

# Benchmark
./scripts/benchmark.sh
```

### Logs

- Coordinator: stdout (JSON)
- Worker: stdout (JSON)
- CUDA: kernels output

### Support

- Docs: `README.md`, `ARCHITECTURE.md`
- Issues: Repository issues
- Email: support@ntv.com.vn

---

**© 2025 NTV.com.vn**
