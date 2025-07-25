# Khắc Phục Lỗi Build Docker: nvidia-container-toolkit

## Mục Tiêu
Giải quyết lỗi **build Images** (xây dựng hình ảnh Docker) do không thể cài đặt **nvidia-container-toolkit** (công cụ container NVIDIA) từ **Ubuntu repositories** (kho phần mềm Ubuntu). Lỗi xuất hiện tại `Dockerfile:69` với thông báo "E: Unable to locate package nvidia-container-toolkit".

## Kế Hoạch Triển Khai

### 1. **Phân Tích Nguyên Nhân Lỗi Chính**
- **Dependencies**: Không có
- **Ghi chú**: **NVIDIA Container Toolkit** không có sẵn trong **Ubuntu 22.04 default repositories** (kho mặc định). Package này cần được cài đặt từ **NVIDIA official repository** (kho chính thức NVIDIA) hoặc có thể không cần thiết trong container.
- **Files**: `Dockerfile:69`
- **Trạng thái**: Chưa bắt đầu

### 2. **Đánh Giá Tính Cần Thiết Của nvidia-container-toolkit**
- **Dependencies**: Task 1
- **Ghi chú**: **Base image** `nvcr.io/nvidia/cuda:12.0.0-cudnn8-devel-ubuntu22.04` đã bao gồm **CUDA runtime** (môi trường chạy CUDA). **NVIDIA Container Toolkit** thường được cài đặt trên **host system** (hệ thống chủ), không phải trong container.
- **Files**: `Dockerfile:1`, `Dockerfile:69`
- **Trạng thái**: Chưa bắt đầu

### 3. **Kiểm Tra GPU Dependencies Trong Application**
- **Dependencies**: Task 2
- **Ghi chú**: Phân tích code trong `mining_environment/gpu_plugins/` để xác định **GPU libraries** (thư viện GPU) nào thực sự cần thiết cho **GPU cloaking** (che giấu GPU) và **mining functionality** (chức năng mining).
- **Files**: `mining_environment/gpu_plugins/`, `requirements.txt`
- **Trạng thái**: Chưa bắt đầu

### 4. **Đánh Giá Ba Giải Pháp Thay Thế**
- **Dependencies**: Task 1, 2, 3
- **Ghi chú**: 
  - **Solution A**: Loại bỏ `nvidia-container-toolkit` khỏi package list (an toàn nhất)
  - **Solution B**: Thêm **NVIDIA repository** trước khi cài đặt (đầy đủ tính năng)
  - **Solution C**: Thay thế bằng **alternative packages** như `libnvidia-ml-dev`
- **Files**: `Dockerfile:55-75`
- **Trạng thái**: Chưa bắt đầu

### 5. **Tối Ưu Hóa Package Installation**
- **Dependencies**: Task 4
- **Ghi chú**: Phân tích 70+ packages được cài đặt cùng lúc để tránh **dependency conflicts** (xung đột phụ thuộc) và tối ưu **layer caching** (bộ nhớ đệm layer).
- **Files**: `Dockerfile:61-74`
- **Trạng thái**: Chưa bắt đầu

### 6. **Tạo Validation Strategy**
- **Dependencies**: Task 5
- **Ghi chú**: Xác định cách kiểm tra **GPU functionality** sau khi áp dụng fix, bao gồm **NVML access** (truy cập NVML), **CUDA operations** (thao tác CUDA), và **eBPF programs** (chương trình eBPF).
- **Files**: `gpu-debug.sh`, `mining_environment/gpu_plugins/`
- **Trạng thái**: Chưa bắt đầu

## Tiêu Chí Xác Minh

- **Docker build** hoàn thành thành công không có lỗi exit code 100
- **GPU access** hoạt động bình thường trong container với `nvidia-smi`
- **Python GPU libraries** (pynvml, torch) import và chạy được
- **eBPF programs** load thành công với **BPF filesystem** mounted
- **Mining application** khởi động và detect GPU hardware
- **Container size** không tăng đáng kể so với hiện tại

## Rủi Ro Tiềm Ẩn và Giải Pháp Giảm Thiểu

### 1. **Mất GPU Management Functionality**
**Giải pháp giảm thiểu**: Kiểm tra kỹ các **NVML functions** được sử dụng trong code và đảm bảo `libnvidia-ml-dev` cung cấp đủ APIs cần thiết.

### 2. **Breaking Changes Với Existing Code**
**Giải pháp giảm thiểu**: Tạo **compatibility layer** trong Python code để handle các **GPU library imports** một cách graceful khi packages không có sẵn.

### 3. **Performance Impact From Package Changes**
**Giải pháp giảm thiểu**: **Benchmark GPU operations** trước và sau khi thay đổi để đảm bảo không có **performance regression**.

### 4. **Container Runtime Compatibility Issues**
**Giải pháp giảm thiểu**: Test container với nhiều **runtime environments** khác nhau (Docker, Podman, Kubernetes) để đảm bảo **cross-platform compatibility**.

## Các Phương Án Thay Thế

### 1. **Minimal Fix Approach**: Loại bỏ `nvidia-container-toolkit` khỏi package list và rely on base image capabilities

### 2. **Repository Addition Approach**: Thêm NVIDIA official repository và cài đặt đầy đủ toolkit với proper GPG keys

### 3. **Hybrid Approach**: Sử dụng `libnvidia-ml-dev` và các lightweight alternatives thay vì full toolkit

### 4. **Multi-stage Build Approach**: Tách riêng GPU dependencies vào separate stage để tối ưu image size và build time