# Giải Pháp Sửa Lỗi Cấp Phát Bộ Nhớ `cryptonight_extra_cpu_init:321`

## Tổng Quan

Tài liệu này trình bày giải pháp sửa lỗi `cryptonight_extra_cpu_init:321` (lỗi out-of-memory) trong dự án khai thác GPU dựa trên phân tích mã nguồn và log đã thực hiện.

## Phân Tích Nguyên Nhân

### 1. Xác Định Nguyên Nhân Chính

Lỗi `cryptonight_extra_cpu_init:321` là lỗi cấp phát bộ nhớ (memory allocation failure) xảy ra trong quá trình khởi tạo tiến trình khai thác. Nguyên nhân chính được xác định là:

- **Phân mảnh bộ nhớ ảo** (virtual memory fragmentation) thay vì thiếu bộ nhớ vật lý
- **Không đủ không gian bộ nhớ ảo liền kề** để cấp phát cho các cấu trúc dữ liệu lớn trong thuật toán Cryptonight

### 2. Các Điểm Gây Ra Lỗi

Dựa trên phân tích mã nguồn, các điểm có thể gây ra lỗi OOM bao gồm:

1. **Hàm `_apply_rlimits` trong `resource_control.py`**:
   - Áp dụng giới hạn `RLIMIT_AS` (virtual memory limit) có thể quá nghiêm ngặt
   - Giới hạn 75% tổng RAM có thể không đủ cho các thuật toán khai thác cần bộ nhớ lớn

2. **Hàm `create_enhanced_gpu_environment` trong `stealth_inference_cuda.py`**:
   - Môi trường sạch được tạo có thể thiếu các thiết lập tối ưu cho cấp phát bộ nhớ
   - Không có cơ chế đặc biệt để xử lý phân mảnh bộ nhớ

3. **Hàm `start_mining_process` trong `start_mining.py`**:
   - Khởi tạo tiến trình con mà không có cơ chế kiểm tra/pre-allocate bộ nhớ
   - Không có cơ chế retry với cấu hình bộ nhớ khác khi thất bại

## Giải Pháp Đề Xuất

### 1. Tối Ưu Hóa Giới Hạn Bộ Nhớ Ảo

#### a. Điều Chỉnh RLIMIT_AS trong `resource_control.py`

Thay đổi hàm `_apply_rlimits` để:

- Tăng giới hạn virtual memory lên 90% tổng RAM thay vì 75%
- Thêm cơ chế kiểm tra bộ nhớ khả dụng trước khi áp dụng giới hạn
- Thêm tùy chọn để bỏ qua giới hạn AS cho các tiến trình khai thác quan trọng

#### b. Thêm Kiểm Tra Bộ Nhớ Khả Dụng

Trước khi áp dụng resource limits, kiểm tra bộ nhớ khả dụng:

```python
# Trong _apply_rlimits
meminfo = psutil.virtual_memory()
available_memory = meminfo.available
# Chỉ áp dụng giới hạn nếu đủ bộ nhớ khả dụng
if available_memory > min_required_memory:
    # Áp dụng giới hạn
else:
    # Ghi log cảnh báo và không áp dụng giới hạn
```

### 2. Cải Thiện Môi Trường Khởi Tạo GPU

#### a. Tối Ưu `create_enhanced_gpu_environment`

Trong `stealth_inference_cuda.py`, cải thiện hàm `create_enhanced_gpu_environment`:

- Thêm các biến môi trường tối ưu cho CUDA memory management:
  - `CUDA_MANAGED_FORCE_DEVICE_ALLOC=1`
  - `CUDA_DEVICE_MAX_CONNECTIONS=1`
  - `CUDA_LAUNCH_BLOCKING=0`

- Thêm thiết lập để giảm phân mảnh bộ nhớ:
  - `MALLOC_ARENA_MAX=2`
  - `MALLOC_MMAP_THRESHOLD_=131072`

#### b. Thêm Cơ Chế Pre-allocate Bộ Nhớ

Trong `stealth_inference_cuda.py`, thêm hàm pre-allocate bộ nhớ:

```python
def preallocate_memory(size_mb: int) -> bool:
    """Pre-allocate bộ nhớ để giảm phân mảnh"""
    try:
        # Sử dụng malloc để pre-allocate
        import ctypes
        libc = ctypes.CDLL("libc.so.6")
        ptr = libc.malloc(size_mb * 1024 * 1024)
        if ptr:
            libc.free(ptr)
            return True
        return False
    except:
        return False
```

### 3. Cải Thiện Cơ Chế Khởi Tạo Tiến Trình

#### a. Thêm Kiểm Tra Bộ Nhớ Trước Khi Khởi Tạo

Trong `start_mining.py`, thêm kiểm tra bộ nhớ trước khi gọi `start_mining_process`:

```python
def check_memory_availability(required_mb: int) -> bool:
    """Kiểm tra bộ nhớ khả dụng trước khi khởi tạo tiến trình khai thác"""
    meminfo = psutil.virtual_memory()
    available_mb = meminfo.available / (1024 * 1024)
    return available_mb > required_mb * 1.2  # 20% buffer
```

#### b. Thêm Cơ Chế Retry Với Cấu Hình Khác

Cải thiện hàm `start_mining_process` để có cơ chế retry:

```python
def start_mining_process(mining_type: str, max_retries: int = 3):
    """Khởi tạo tiến trình khai thác với cơ chế retry"""
    for attempt in range(max_retries):
        try:
            # Kiểm tra bộ nhớ
            if not check_memory_availability(required_memory_mb):
                logger.warning(f"Không đủ bộ nhớ cho lần thử {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(5)  # Đợi trước khi thử lại
                    continue
            
            # Khởi tạo tiến trình
            # ... code khởi tạo ...
            return True
        except MemoryError:
            logger.error(f"Lỗi bộ nhớ trong lần thử {attempt + 1}")
            if attempt < max_retries - 1:
                # Giảm số luồng hoặc điều chỉnh cấu hình
                adjust_mining_config()
                time.sleep(5)
        except Exception as e:
            logger.error(f"Lỗi không xác định: {e}")
            break
    return False
```

### 4. Tối Ưu Hóa Quản Lý Tài Nguyên

#### a. Cải Thiện Hàm `optimize_cache_usage` trong `MemoryResourceManager`

Thêm cơ chế giảm phân mảnh bộ nhớ:

```python
def optimize_cache_usage(self, pid: int) -> bool:
    """Tối ưu cache usage và giảm phân mảnh bộ nhớ"""
    try:
        process = psutil.Process(pid)
        # Thêm cơ chế giảm phân mảnh
        # ...
        return True
    except:
        return False
```

#### b. Thêm Cơ Chế Monitor Bộ Nhớ

Trong `stealth_inference_cuda.py`, thêm monitor bộ nhớ:

```python
def monitor_memory_usage():
    """Monitor bộ nhớ trong quá trình khai thác"""
    while process.poll() is None:
        try:
            memory_info = process.memory_info()
            if memory_info.rss > memory_threshold:
                logger.warning("Phát hiện sử dụng bộ nhớ cao")
                # Thực hiện các biện pháp giảm bộ nhớ
        except:
            pass
        time.sleep(30)
```

## Triển Khai

### 1. Ưu Tiên Các Thay Đổi

1. **Thay đổi giới hạn bộ nhớ ảo** trong `_apply_rlimits` (ưu tiên cao nhất)
2. **Cải thiện môi trường khởi tạo** trong `create_enhanced_gpu_environment`
3. **Thêm kiểm tra bộ nhớ** trong `start_mining_process`
4. **Cải thiện monitor bộ nhớ** trong `stealth_inference_cuda.py`

### 2. Kiểm Thử

- Kiểm tra khởi tạo tiến trình khai thác sau các thay đổi
- Monitor log để đảm bảo không còn lỗi `cryptonight_extra_cpu_init:321`
- Kiểm tra hiệu suất khai thác không bị ảnh hưởng đáng kể

### 3. Rollback Plan

Nếu các thay đổi gây ra vấn đề:

- Khôi phục giới hạn bộ nhớ về giá trị ban đầu
- Loại bỏ các biến môi trường mới thêm
- Trở về cơ chế khởi tạo ban đầu

## Kết Luận

Giải pháp này tập trung vào việc giảm phân mảnh bộ nhớ và tối ưu hóa giới hạn tài nguyên để khắc phục lỗi `cryptonight_extra_cpu_init:321` mà không cần thêm module hay thư viện mới, dựa trên mã nguồn hiện có.
